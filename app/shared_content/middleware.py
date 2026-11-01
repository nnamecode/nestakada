"""Owner admission before CSRF/body on closed shared editor POST endpoints."""
import re
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from accounts.services import require_session, is_owner, note_denial
from accounts.views import private
from editor_runtime.guards import EditorFault, BodyTooLarge, BodyMalformed, LengthRequired

PATH = re.compile(r'^/manage/shared/(header|footer)/(check|draft|apply|restore/prepare)/$')
CANCEL_PATH = re.compile(r'^/manage/shared/(header|footer)/stages/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/cancel/$')


class SharedAdmissionMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        cancel = CANCEL_PATH.fullmatch(request.path_info)
        if request.method == 'POST' and (PATH.fullmatch(request.path_info) or cancel):
            try:
                actor = require_session(request, touch=False)
                if not is_owner(actor):
                    note_denial(request, 'owner')
                    return private(JsonResponse({'ok': False, 'code': 'SHARED_OWNER_REQUIRED', 'operationNotStarted': True}, status=403))
                if request.content_type != 'application/json':
                    return private(JsonResponse({'ok': False, 'code': 'EDITOR_JSON_REQUIRED', 'operationNotStarted': True}, status=415))
                if cancel:
                    if request.META.get('QUERY_STRING'):
                        return private(JsonResponse({'ok': False, 'code': 'SHARED_INPUT_REJECTED', 'operationNotStarted': True}, status=400))
                    if request.META.get('HTTP_TRANSFER_ENCODING'):
                        raise BodyMalformed()
                    length = request.META.get('CONTENT_LENGTH', '')
                    if not length:
                        raise LengthRequired()
                    if not length.isascii() or not length.isdecimal():
                        raise BodyMalformed()
                    try:
                        size = int(length)
                    except ValueError:
                        raise BodyMalformed() from None
                    if size > 16384:
                        raise BodyTooLarge()
            except PermissionDenied:
                return private(JsonResponse({'ok': False, 'code': 'SHARED_SESSION_ENDED', 'operationNotStarted': True}, status=401))
            except DatabaseError:
                return private(JsonResponse({'ok': False, 'code': 'SHARED_UNAVAILABLE', 'operationNotStarted': True}, status=503))
            except EditorFault as exc:
                return private(JsonResponse({'ok': False, 'code': exc.code, 'operationNotStarted': True}, status=exc.status))
        return None
