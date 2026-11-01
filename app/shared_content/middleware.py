"""Owner admission before CSRF/body on closed shared editor POST endpoints."""
import re
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from accounts.services import require_session, is_owner, note_denial
from accounts.views import private

PATH = re.compile(r'^/manage/shared/(header|footer)/(check|draft|apply|restore/prepare)/$')


class SharedAdmissionMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method == 'POST' and PATH.fullmatch(request.path_info):
            try:
                actor = require_session(request, touch=False)
                if not is_owner(actor):
                    note_denial(request, 'owner')
                    return private(JsonResponse({'ok': False, 'code': 'SHARED_OWNER_REQUIRED', 'operationNotStarted': True}, status=403))
                if request.content_type != 'application/json':
                    return private(JsonResponse({'ok': False, 'code': 'EDITOR_JSON_REQUIRED', 'operationNotStarted': True}, status=415))
            except PermissionDenied:
                return private(JsonResponse({'ok': False, 'code': 'SHARED_SESSION_ENDED', 'operationNotStarted': True}, status=401))
            except DatabaseError:
                return private(JsonResponse({'ok': False, 'code': 'SHARED_UNAVAILABLE', 'operationNotStarted': True}, status=503))
        return None
