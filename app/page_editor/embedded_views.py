"""Small owner issuance: no content write, no signing key in the child."""
import json
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from accounts.views import gate
from accounts.services import require_session, note_denial
from editor_runtime.guards import EditorSlot, EditorFault
from editor_runtime.processing import normalize_input
from .views import request_context
from .checks import CheckFault
from .input_policy import _pairs, _no_constant, identifier, image_reference
from . import embedded, media


@require_POST
@gate(owner=True)
def issue(request, page_id):
    try:
        with EditorSlot():
            before = request_context(request, page_id)
            if request.content_type != 'application/json' or request.META.get('HTTP_TRANSFER_ENCODING'):
                raise CheckFault('EDITOR_EMBEDDED_INVALID')
            length = request.META.get('CONTENT_LENGTH', '')
            if not length.isascii() or not length.isdecimal() or not 0 < int(length) <= 16384:
                raise CheckFault('EDITOR_EMBEDDED_INVALID')
            raw = request.body
            if len(raw) != int(length):
                raise CheckFault('EDITOR_EMBEDDED_INVALID')
            value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_no_constant)
            if (type(value) is not dict or set(value) != {'generation', 'baseRevisionId', 'field', 'action', 'image', 'markerId', 'priorPermit'}
                    or type(value['generation']) is not int or value['generation'] != request.auth_generation
                    or value['baseRevisionId'] != before.child['base_revision_id']
                    or type(value['field']) is not str or value['field'] not in embedded.FIELDS
                    or type(value['action']) is not str or value['action'] not in ('insert', 'replace')):
                raise CheckFault('EDITOR_EMBEDDED_INVALID')
            identifier(value['baseRevisionId'])
            value['image'] = image_reference(value['image'])
            if value['image'] is None:
                raise CheckFault('EDITOR_EMBEDDED_INVALID')
            if value['action'] == 'insert':
                if value['markerId'] is not None or value['priorPermit'] is not None:
                    raise CheckFault('EDITOR_EMBEDDED_INVALID')
            else:
                identifier(value['markerId'])
                if value['priorPermit'] is not None:
                    embedded.load_permit(value['priorPermit'], before)
            result = normalize_input(raw, dict(before.child, action='embedded-issue'))
            if type(result) is not dict or set(result) != {'sourceBindings'} or type(result['sourceBindings']) is not list:
                raise CheckFault('EDITOR_WORKER_PROTOCOL')
            claims = embedded.issue(before, value, result['sourceBindings'])
            embedded.validate_binding(claims)
            derived = {'embedded_images': [*before.payload['embedded_images'], {'id': claims['ids']['imageId'], **claims['image']}]}
            evidence = media.prepare(before, {}, derived=derived)
            actor = require_session(request, touch=False)
            if actor.pk != before.actor_id:
                raise CheckFault('EDITOR_IDENTITY_CHANGED')
            media.late_context(actor=actor, page_id=page_id, generation=value['generation'],
                session_key=request.session.session_key, origin=request.build_absolute_uri('/').rstrip('/'),
                before=before, evidence=evidence)
            return JsonResponse(embedded.sign_issue(claims), json_dumps_params={'ensure_ascii': False})
    except (ValueError, TypeError, UnicodeError, ValidationError):
        return JsonResponse({'ok': False, 'code': 'EDITOR_EMBEDDED_INVALID'}, status=400)
    except PermissionDenied:
        note_denial(request, 'owner')
        return JsonResponse({'ok': False, 'code': 'EDITOR_FIELDS_FORBIDDEN'}, status=403)
    except ObjectDoesNotExist:
        return JsonResponse({'ok': False, 'code': 'EDITOR_MEDIA_UNAVAILABLE'}, status=409)
    except EditorFault as exc:
        return JsonResponse({'ok': False, 'code': exc.code}, status=exc.status)
