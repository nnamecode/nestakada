"""Exact editor JSON admission before CSRF can parse a multipart body."""
import re
from uuid import UUID
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.db import DatabaseError
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from accounts.services import require_session, note_denial
from .checks import inspect_context
from editor_runtime.guards import EditorFault

CHECK_PATH = re.compile(r'^/manage/pages/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/edit/(?:check|save)/$')


class EditorAdmissionMiddleware(MiddlewareMixin):
    # Install BEFORE CsrfViewMiddleware. This process_view runs only after the
    # complete middleware chain established request.session and request.user.
    def process_view(self, request, view_func, view_args, view_kwargs):
        match = CHECK_PATH.fullmatch(request.path)
        if request.method != 'POST' or match is None:
            return None
        try:
            actor = require_session(request, touch=False)
            if request.content_type != 'application/json':
                return JsonResponse({'ok': False, 'code': 'EDITOR_JSON_REQUIRED'}, status=415)
            origin = request.build_absolute_uri('/').rstrip('/')
            inspect_context(actor=actor, page_id=UUID(match.group(1)),
                            generation=request.auth_generation, origin=origin)
        except PermissionDenied:
            note_denial(request, 'page')
            return JsonResponse({'ok': False, 'code': 'EDITOR_FIELDS_FORBIDDEN'}, status=403)
        except ObjectDoesNotExist:
            return JsonResponse({'ok': False, 'code': 'EDITOR_PAGE_UNAVAILABLE'}, status=404)
        except EditorFault as exc:
            return JsonResponse({'ok': False, 'code': exc.code}, status=exc.status)
        except DatabaseError:
            return JsonResponse({'ok': False, 'code': 'EDITOR_UNAVAILABLE'}, status=503)
        # Keep the genuine CSRF middleware and its header verification active.
        return None
