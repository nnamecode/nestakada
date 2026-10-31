from django.utils.cache import patch_vary_headers
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError

class PrivateCacheMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        response=self.get_response(request)
        if request.path=='/manage' or request.path.startswith('/manage/'):
            response['Cache-Control']='private, no-store'
            patch_vary_headers(response,['Cookie'])
        return response

class PrivateAccessMiddleware:
    """Deny closed requests before CSRF parses their bodies; never touch idle time."""
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        path=request.path
        if path.startswith('/manage/') and path not in ('/manage/login/','/manage/assets/manage.css'):
            if not (path=='/manage/session/' and request.method=='GET'):
                from .services import require_session
                try:require_session(request,touch=False)
                except PermissionDenied:
                    return HttpResponse('<!doctype html><html lang="ru"><meta charset="utf-8"><p>Сессия завершена. Войдите снова, чтобы продолжить.</p><a href="/manage/login/">Войти снова</a></html>',status=401)
                except DatabaseError:
                    return HttpResponse('Не удалось выполнить действие. Повторите позже.',status=503)
        return self.get_response(request)
