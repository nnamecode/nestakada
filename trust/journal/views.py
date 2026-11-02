import threading
from functools import wraps
from django.core.exceptions import SuspiciousOperation
from django.db import DatabaseError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from . import auth, services
from .protocol import Fault, MAX_BODY, integer, parse, validate
from .safe_logging import failure

_slots=threading.BoundedSemaphore(4)
def response(value,status=200):
    result=JsonResponse(value,status=status,json_dumps_params={'ensure_ascii':False})
    result['Cache-Control']='no-store'
    result['X-Content-Type-Options']='nosniff'
    return result
def endpoint(method,role,phase=None):
    def decorate(function):
        @csrf_exempt
        @wraps(function)
        def call(request,*args,**kwargs):
            if request.method!=method: return response({'ok':False,'code':'METHOD_REJECTED'},405)
            if not _slots.acquire(blocking=False): return response({'ok':False,'code':'BUSY'},429)
            try:
                actor=auth.authenticate(request.headers.get('Authorization'),role)
                body=None
                if phase:
                    if request.content_type!='application/json' or request.GET: raise Fault('INPUT_REJECTED',400)
                    length=request.META.get('CONTENT_LENGTH','')
                    if not length.isdecimal(): raise Fault('LENGTH_REQUIRED',411)
                    if int(length)>MAX_BODY: raise Fault('BODY_TOO_LARGE',413)
                    raw=request.read(MAX_BODY+1)
                    parsed=parse(raw)
                    if phase in ('fence','activate'):
                        from .recovery import validate as validate_recovery
                        body=validate_recovery(parsed,phase)
                    else: body=validate(parsed,phase)
                return response(function(request,actor,body,*args,**kwargs))
            except Fault as fault:
                if fault.code in ('IDENTITY_UNAVAILABLE','IDENTITY_MISMATCH','TRUST_FROZEN'): event='IDENTITY_FAILURE'
                elif fault.status in (401,403): event='AUTH_REJECTED'
                elif fault.status==400: event='INPUT_REJECTED'
                else: event='WRITE_REJECTED'
                failure(event)
                return response({'ok':False,'code':fault.code},fault.status)
            except (SuspiciousOperation,ValueError,TypeError,OverflowError,UnicodeError):
                failure('INPUT_REJECTED')
                return response({'ok':False,'code':'INPUT_REJECTED'},400)
            except (DatabaseError,OSError):
                failure('TRUST_UNAVAILABLE')
                return response({'ok':False,'code':'TRUST_UNAVAILABLE'},503)
            except Exception:
                failure('UNEXPECTED_FAILURE')
                return response({'ok':False,'code':'UNEXPECTED_FAILURE'},500)
            finally: _slots.release()
        return call
    return decorate

@endpoint('GET','reader')
def head(request,actor,body):
    if request.GET: raise Fault('INPUT_REJECTED',400)
    return {'ok':True,'head':services.read_head(actor)}
@endpoint('GET','reader')
def operation(request,actor,body,operation_id):
    if request.GET: raise Fault('INPUT_REJECTED',400)
    return {'ok':True,**services.operation_status(actor,operation_id)}
@endpoint('GET','reader')
def snapshot_manifest(request,actor,body):
    if request.GET: raise Fault('INPUT_REJECTED',400)
    return {'ok':True,**services.snapshot_manifest(actor)}
@endpoint('GET','reader')
def snapshot(request,actor,body):
    if set(request.GET)-{'generation','cursor'} or any(len(request.GET.getlist(k))!=1 for k in request.GET): raise Fault('INPUT_REJECTED',400)
    generation=request.GET.get('generation')
    if generation is not None: integer(generation)
    cursor=integer(request.GET.get('cursor','0'))
    if cursor>60000 or (cursor and generation is None): raise Fault('INPUT_REJECTED',400)
    return {'ok':True,**services.snapshot(actor,generation,cursor)}
@endpoint('POST','writer','prepare')
def prepare(request,actor,body): return services.mutate(actor,body,'prepare')
@endpoint('POST','writer','report')
def report(request,actor,body): return services.mutate(actor,body,'report')

@endpoint('POST','recovery','fence')
def fence(request,actor,body):
    from .recovery import mutate
    return mutate(actor,body,'fence')

@endpoint('POST','recovery','activate')
def activate(request,actor,body):
    from .recovery import mutate
    return mutate(actor,body,'activate')
