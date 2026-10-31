from functools import wraps
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.db import DatabaseError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from content.models import Page
from . import services
from .models import PageGrant, UserProfile

LOGIN_ERROR = 'Не удалось войти. Проверьте логин и пароль или повторите попытку позже.'

def private(response):
    response['Cache-Control']='private, no-store'
    response['Vary']='Cookie'
    return response

def fields(request, allowed):
    try:
        if request.content_type != 'application/x-www-form-urlencoded':
            if not request.content_type and not request.body:
                return request.POST
            raise ValueError()
        if int(request.META.get('CONTENT_LENGTH') or 0)>16384 or len(request.body)>16384:
            raise ValueError()
        if any(k not in set(allowed)|{'csrfmiddlewaretoken'} or len(request.POST.getlist(k))!=1 for k in request.POST):
            raise ValueError()
        return request.POST
    except (ValueError, TypeError):
        raise ValidationError('AUTH_INVALID_FORM') from None

def denied(request):
    return private(render(request,'accounts/denied.html',status=401))

def gate(*, owner=False, touch=True):
    def decorate(view):
        @wraps(view)
        def secured(request,*args,**kwargs):
            try:
                request.user=services.require_session(request,touch=touch)
                if owner and not services.is_owner(request.user):
                    services.note_denial(request,'owner')
                    return private(render(request,'accounts/forbidden.html',status=403))
            except PermissionDenied:
                return denied(request)
            except DatabaseError:
                return private(render(request,'accounts/unavailable.html',status=503))
            try:
                return private(view(request,*args,**kwargs))
            except DatabaseError:
                return private(render(request,'accounts/unavailable.html',status=503))
        return secured
    return decorate

def redirect_to(name):
    response=HttpResponse(status=303);response['Location']=reverse(name);return response

@require_http_methods(['GET','POST'])
def login_view(request):
    error=None
    if request.method=='POST':
        try:
            data=fields(request,['username','password'])
            if services.authenticate_request(request,data.get('username',''),data.get('password','')):
                response=private(redirect_to('accounts:dashboard'))
                response['X-Request-ID']=str(request.auth_request_id)
                return response
        except (ValidationError,services.AuthUnavailable,DatabaseError):
            pass
        error=LOGIN_ERROR
    response=private(render(request,'accounts/login.html',{'error':error}))
    if hasattr(request,'auth_request_id'):response['X-Request-ID']=str(request.auth_request_id)
    return response

@require_GET
@gate()
def dashboard(request):
    owner=services.is_owner(request.user)
    pages=Page.objects.all() if owner else Page.objects.filter(employee_grants__user=request.user)
    return render(request,'accounts/dashboard.html',{'owner':owner,'pages':pages})

@require_POST
@gate()
def logout_view(request):
    try:fields(request,[])
    except ValidationError:return private(render(request,'accounts/error.html',status=400))
    services.logout_request(request)
    return redirect_to('accounts:login')

@require_GET
def session_state(request):
    try:
        user=services.require_session(request,touch=False)
    except PermissionDenied:
        return private(JsonResponse({'authenticated':False},status=401))
    except DatabaseError:
        return private(JsonResponse({'authenticated':False},status=503))
    return private(JsonResponse({'authenticated':True,'userId':str(user.pk)}))

@require_GET
@gate()
def assigned_page(request,page_id):
    page=get_object_or_404(Page,pk=page_id)
    try: allowed=services.allowed_fields(request.user,page)
    except PermissionDenied:
        services.note_denial(request,'page')
        return private(render(request,'accounts/forbidden.html',status=403))
    return render(request,'accounts/page_access.html',{'page':page,'allowed':allowed,'owner':services.is_owner(request.user)})

@require_http_methods(['GET','POST'])
@gate(owner=True)
def employees(request):
    error=None
    if request.method=='POST':
        try:
            data=fields(request,['username','password'])
            services.create_employee(actor=request.user,username=data.get('username',''),password=data.get('password',''),expected_generation=request.auth_generation)
            return redirect_to('accounts:employees')
        except (ValidationError,DatabaseError):error='Не удалось создать сотрудника. Проверьте логин и пароль.'
        except PermissionDenied:return private(render(request,'accounts/forbidden.html',status=403))
    profiles=UserProfile.objects.select_related('user').filter(role='employee').order_by('user__username')
    assignable=Page.objects.filter(kind__in=[Page.Kind.SERVICE,Page.Kind.ARTICLE,Page.Kind.NEWS_ARTICLE,Page.Kind.WASH])
    return render(request,'accounts/employees.html',{'profiles':profiles,'assignable':assignable,'owner':True,'error':error})

@require_POST
@gate(owner=True)
def employee_password(request,user_id):
    employee=get_object_or_404(get_user_model(),pk=user_id)
    try:
        data=fields(request,['password'])
        services.reset_password(actor=request.user,employee=employee,password=data.get('password',''),expected_generation=request.auth_generation)
    except PermissionDenied:return private(render(request,'accounts/forbidden.html',status=403))
    except (ValidationError,DatabaseError,ObjectDoesNotExist):return private(render(request,'accounts/error.html',status=400))
    return redirect_to('accounts:employees')

@require_POST
@gate(owner=True)
def employee_active(request,user_id):
    employee=get_object_or_404(get_user_model(),pk=user_id)
    try:
        data=fields(request,['action'])
        if data.get('action') not in ['disable','enable']:raise ValidationError('AUTH_INVALID_ACTION')
        services.set_active(actor=request.user,employee=employee,active=data['action']=='enable',expected_generation=request.auth_generation)
    except PermissionDenied:return private(render(request,'accounts/forbidden.html',status=403))
    except (ValidationError,DatabaseError,ObjectDoesNotExist):return private(render(request,'accounts/error.html',status=400))
    return redirect_to('accounts:employees')

@require_POST
@gate(owner=True)
def employee_grant(request,user_id):
    employee=get_object_or_404(get_user_model(),pk=user_id)
    try:
        data=fields(request,['page','intro_text','main_text','price','action'])
        page=Page.objects.get(pk=data.get('page'))
        if data.get('action') not in ['set','revoke']:raise ValidationError('AUTH_INVALID_ACTION')
        if any(data.get(k,'') not in ['','on'] for k in ['intro_text','main_text','price']):raise ValidationError('AUTH_INVALID_CAPABILITY')
        services.set_grant(actor=request.user,employee=employee,page=page,intro_text=data.get('intro_text')=='on',main_text=data.get('main_text')=='on',price=data.get('price')=='on',revoke=data['action']=='revoke',expected_generation=request.auth_generation)
    except PermissionDenied:return private(render(request,'accounts/forbidden.html',status=403))
    except (ValidationError,DatabaseError,ObjectDoesNotExist,ValueError):return private(render(request,'accounts/error.html',status=400))
    return redirect_to('accounts:employees')

@require_GET
def stylesheet(request):
    return private(HttpResponse((Path(__file__).parent/'assets/manage.css').read_text(encoding='utf-8'),content_type='text/css'))
