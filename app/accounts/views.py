from functools import wraps
import hashlib
import os
import stat
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.db import DatabaseError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_GET, require_POST, require_safe
from content.models import Page
from . import services
from .page_projection import (workshop_pages, dashboard_page,
                              ProjectionInput, ProjectionOverflow)
from .models import PageGrant, UserProfile

LOGIN_ERROR = 'Не удалось войти. Проверьте логин и пароль или повторите попытку позже.'
BRAND_LOGO_PATH = Path(__file__).parent/'assets/brand-logo.png'
BRAND_LOGO_SIZE = 30190
BRAND_LOGO_SHA256 = '39feb78ac1cc832b5819e886311e8424472412cc00bd2dcfd880f308f8f319f5'

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
    username='nesadmin' if settings.ENVIRONMENT == 'dev' else ''
    if request.method=='POST':
        try:
            data=fields(request,['username','password'])
            submitted=data.get('username','')
            username=submitted.strip() if isinstance(submitted,str) else ''
            if services.authenticate_request(request,username,data.get('password','')):
                response=private(redirect_to('accounts:dashboard'))
                response['X-Request-ID']=str(request.auth_request_id)
                return response
        except (ValidationError,services.AuthUnavailable,DatabaseError):
            pass
        error=LOGIN_ERROR
    response=private(render(request,'accounts/login.html',{'error':error,'username':username}))
    if hasattr(request,'auth_request_id'):response['X-Request-ID']=str(request.auth_request_id)
    return response

@require_GET
@gate()
def dashboard(request):
    owner=services.is_owner(request.user)
    try:
        projection=workshop_pages(request.user)
        listing=dashboard_page(projection,request.GET)
    except ProjectionInput:
        return render(request,'accounts/dashboard.html',{'owner':owner,'query_error':True},status=400)
    except ProjectionOverflow:
        return render(request,'accounts/unavailable.html',{'owner':owner},status=503)
    shared_count=None
    if owner:
        from shared_content.models import SharedBlock
        shared_count=SharedBlock.objects.count()
    return render(request,'accounts/dashboard.html',{
        'owner':owner,'projection':projection,'listing':listing,
        'shared_count':shared_count})

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

@require_safe
def brand_logo(request):
    descriptor=None
    try:
        descriptor=os.open(BRAND_LOGO_PATH,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
        info=os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1
                or info.st_size!=BRAND_LOGO_SIZE):
            raise OSError('logo identity rejected')
        chunks=[];remaining=BRAND_LOGO_SIZE
        while remaining:
            chunk=os.read(descriptor,min(65536,remaining))
            if not chunk:raise OSError('logo read rejected')
            chunks.append(chunk);remaining-=len(chunk)
        if os.read(descriptor,1):raise OSError('logo size changed')
        payload=b''.join(chunks)
        if hashlib.sha256(payload).hexdigest()!=BRAND_LOGO_SHA256:
            raise OSError('logo digest rejected')
    except OSError:
        return private(HttpResponse(status=404))
    finally:
        if descriptor is not None:os.close(descriptor)
    response=HttpResponse(payload if request.method=='GET' else b'',content_type='image/png')
    response['Content-Length']=str(BRAND_LOGO_SIZE)
    response['X-Content-Type-Options']='nosniff'
    return private(response)


@require_GET
@gate(owner=True)
def page_tree(request):
    from content.admin_tree import parent_key, branch
    try:
        context = branch(parent_key(request.GET))
    except (ValueError, TypeError, AttributeError):
        return render(request, 'accounts/tree_error.html', {'owner': True}, status=400)
    except Page.DoesNotExist:
        return render(request, 'accounts/tree_error.html', {'owner': True, 'missing': True}, status=404)
    except ValidationError:
        return render(request, 'accounts/unavailable.html', status=503)
    from django.conf import settings
    return render(request, 'accounts/tree.html', {'owner': True, **context,
        'can_create': settings.DEV29_LOCAL_CREATE_ENABLED is True and settings.ENVIRONMENT == 'test'})
