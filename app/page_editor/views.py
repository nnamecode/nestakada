"""Private read-only normalization endpoint; not wired into global URLs yet."""
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from accounts.views import gate
from accounts.services import require_session, note_denial
from editor_runtime.guards import EditorFault, EditorSlot, read_json_bytes
from editor_runtime.processing import normalize_input
from .checks import inspect_context, check_worker_result, issue_check_receipt, CheckFault
from .saving import commit_checked


@require_POST
@gate()
def check(request, page_id):
    try:
        generation = request.auth_generation
        actor = request.user
        origin = request.build_absolute_uri('/').rstrip('/')
        before = inspect_context(actor=actor, page_id=page_id, generation=generation, origin=origin)
        with EditorSlot():
            raw = read_json_bytes(request, before.profile)
            result = check_worker_result(normalize_input(raw, before.child), raw=raw, context=before)
            try:
                current_actor = require_session(request, touch=False)
            except PermissionDenied:
                raise CheckFault('EDITOR_SESSION_ENDED') from None
            if current_actor.pk != actor.pk or request.auth_generation != generation:
                raise CheckFault('EDITOR_IDENTITY_CHANGED')
            after = inspect_context(actor=current_actor, page_id=page_id, generation=generation, origin=origin)
            if after.stamp != before.stamp:
                raise CheckFault('EDITOR_CONTEXT_CHANGED')
            receipt = issue_check_receipt(context=after, result=result)
        return JsonResponse({'protocol': 'page-editor-v1',
            'inputFingerprint': result['input_fingerprint'], 'normalisedChanges': result['changes'],
            'normalisationChanged': result['changed'], 'fieldWarnings': result['warnings'],
            'checkReceipt': receipt, 'baseRevisionId': after.child['base_revision_id']},
            json_dumps_params={'ensure_ascii': False, 'allow_nan': False, 'separators': (',', ':')})
    except EditorFault as exc:
        if exc.code == 'EDITOR_FIELDS_FORBIDDEN':
            note_denial(request, 'page')
        return JsonResponse({'ok': False, 'code': exc.code}, status=exc.status)
    except PermissionDenied:
        note_denial(request, 'page')
        return JsonResponse({'ok': False, 'code': 'EDITOR_FIELDS_FORBIDDEN'}, status=403)
    except ObjectDoesNotExist:
        return JsonResponse({'ok': False, 'code': 'EDITOR_PAGE_UNAVAILABLE'}, status=404)


@require_POST
@gate()
def save(request, page_id):
    try:
        actor = request.user
        generation = request.auth_generation
        origin = request.build_absolute_uri('/').rstrip('/')
        before = inspect_context(actor=actor, page_id=page_id, generation=generation, origin=origin)
        with EditorSlot():
            raw = read_json_bytes(request, before.profile)
            result = normalize_input(raw, dict(before.child, action='save'))
            try:
                current_actor = require_session(request, touch=False)
            except PermissionDenied:
                raise CheckFault('EDITOR_SESSION_ENDED') from None
            if current_actor.pk != actor.pk or request.auth_generation != generation:
                raise CheckFault('EDITOR_IDENTITY_CHANGED')
            committed = commit_checked(actor=current_actor, page_id=page_id, generation=generation,
                origin=origin, before=before, raw=raw, result=result, session_key=request.session.session_key)
        return JsonResponse(committed, json_dumps_params={'ensure_ascii': False})
    except EditorFault as exc:
        if exc.code == 'EDITOR_FIELDS_FORBIDDEN':
            note_denial(request, 'page')
        return JsonResponse({'ok': False, 'code': exc.code}, status=exc.status)
    except PermissionDenied:
        note_denial(request, 'page')
        return JsonResponse({'ok': False, 'code': 'EDITOR_FIELDS_FORBIDDEN'}, status=403)
    except ObjectDoesNotExist:
        return JsonResponse({'ok': False, 'code': 'EDITOR_PAGE_UNAVAILABLE'}, status=404)
