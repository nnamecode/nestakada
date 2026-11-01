"""Private read-only normalization endpoint; not wired into global URLs yet."""
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist, ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from accounts.views import gate
from accounts.services import require_session, note_denial
from editor_runtime.guards import EditorFault, EditorSlot, read_json_bytes
from editor_runtime.processing import normalize_input
from .checks import inspect_context, check_worker_result, issue_check_receipt, CheckFault
from .saving import commit_checked
from .source_context import selector_for
from . import media
from . import embedded


def source_response(context):
    return {**context.child['source'], 'baseRevisionId': context.child['base_revision_id'],
            'currentRevisionId': context.child['current_revision_id']}


def request_context(request, page_id, *, allow_unavailable=False):
    try:
        selector = selector_for(request)
    except ValidationError:
        raise CheckFault('EDITOR_INPUT_REJECTED') from None
    return inspect_context(actor=request.user, page_id=page_id, generation=request.auth_generation,
        origin=request.build_absolute_uri('/').rstrip('/'), selector=selector,
        allow_unavailable=allow_unavailable)


@require_POST
@gate()
def check(request, page_id):
    try:
        generation = request.auth_generation
        actor = request.user
        origin = request.build_absolute_uri('/').rstrip('/')
        with EditorSlot():
            before = request_context(request, page_id)
            raw = read_json_bytes(request, before.profile)
            result = check_worker_result(normalize_input(raw, before.child), raw=raw, context=before)
            map_hash = None
            if 'derived' in result:
                _, map_hash = embedded.validate_derived(before, result)
            media_evidence = media.prepare(before, result['changes'], derived=result.get('derived'))
            try:
                current_actor = require_session(request, touch=False)
            except PermissionDenied:
                raise CheckFault('EDITOR_SESSION_ENDED') from None
            if current_actor.pk != actor.pk or request.auth_generation != generation:
                raise CheckFault('EDITOR_IDENTITY_CHANGED')
            after = request_context(request, page_id)
            if after.stamp != before.stamp:
                raise CheckFault('EDITOR_CONTEXT_CHANGED')
            if media_evidence is not None:
                after = media.late_context(actor=current_actor, page_id=page_id, generation=generation,
                    session_key=request.session.session_key, origin=origin, before=before, evidence=media_evidence)
            receipt = issue_check_receipt(context=after, result=result,
                media_evidence=media_evidence.proof if media_evidence else None, derived_map_hash=map_hash)
            response = {'protocol': 'page-editor-v1',
                'inputFingerprint': result['input_fingerprint'], 'normalisedChanges': result['changes'],
                'normalisationChanged': result['changed'], 'fieldWarnings': result['warnings'],
                'checkReceipt': receipt, 'baseRevisionId': after.child['base_revision_id']}
            if after.child['source']['editingFrom'] != 'current':
                response['sourceContext'] = source_response(after)
            if map_hash is not None:
                response['embeddedMedia'] = embedded.preview_mapping(after, None, result['intentBindings'])
            return JsonResponse(response,
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
    return write(request, page_id, action='save')


@require_POST
@gate()
def draft(request, page_id):
    return write(request, page_id, action='draft')


def write(request, page_id, *, action):
    try:
        actor = request.user
        generation = request.auth_generation
        origin = request.build_absolute_uri('/').rstrip('/')
        with EditorSlot():
            before = request_context(request, page_id, allow_unavailable=True)
            if action == 'draft' and not before.child['owner']:
                raise PermissionDenied('EDITOR_FIELDS_FORBIDDEN')
            raw = read_json_bytes(request, before.profile)
            result = normalize_input(raw, dict(before.child, action=action))
            try:
                current_actor = require_session(request, touch=False)
            except PermissionDenied:
                raise CheckFault('EDITOR_SESSION_ENDED') from None
            if current_actor.pk != actor.pk or request.auth_generation != generation:
                raise CheckFault('EDITOR_IDENTITY_CHANGED')
            committed = commit_checked(actor=current_actor, page_id=page_id, generation=generation,
                origin=origin, before=before, raw=raw, result=result, session_key=request.session.session_key)
            if action == 'draft':
                from page_versions.models import OperationReceipt
                from page_versions import engine as E
                meta = result['save_request']
                receipt = OperationReceipt.objects.get(pk=E.uid(meta['operationId']))
                basis = meta['source']['draftBasis']
                committed = {**committed, 'draftBasis': {'id': str(receipt.result_id),
                    'revision': basis['revision'] + 1 if basis else 1},
                    'baseRevisionId': str(receipt.source_revision_id)}
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


@require_POST
@gate(owner=True)
def cancel_draft(request, page_id):
    from .input_policy import _pairs, _no_constant, identifier, fingerprint
    from page_versions import engine as E
    import json
    try:
        if request.META.get('QUERY_STRING') or request.content_type != 'application/json':
            raise CheckFault('EDITOR_INPUT_REJECTED')
        length = request.META.get('CONTENT_LENGTH', '')
        if not length.isascii() or not length.isdecimal() or int(length) > 16384:
            raise CheckFault('EDITOR_INPUT_REJECTED')
        raw = request.body
        if len(raw) > 16384:
            raise CheckFault('EDITOR_INPUT_REJECTED')
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_no_constant)
        if (type(value) is not dict or set(value) != {'generation', 'draftId', 'draftRevision', 'operationId'}
                or type(value['generation']) is not int or value['generation'] != request.auth_generation
                or type(value['draftRevision']) is not int or value['draftRevision'] <= 0):
            raise CheckFault('EDITOR_INPUT_REJECTED')
        identifier(value['draftId']); identifier(value['operationId'])
        result = E.cancel_owner_draft(actor=request.user, page_id=page_id, draft_id=value['draftId'],
            draft_revision=value['draftRevision'], expected_generation=value['generation'],
            operation_id=value['operationId'], editor_request_fingerprint=fingerprint(value),
            editor_session_key=request.session.session_key)
        return JsonResponse(result)
    except (ValueError, UnicodeError):
        return JsonResponse({'ok': False, 'code': 'EDITOR_INPUT_REJECTED'}, status=400)
    except ValidationError as exc:
        code = 'EDITOR_SESSION_ENDED' if 'EDITOR_SESSION_ENDED' in str(exc) else 'EDITOR_OPERATION_CONFLICT'
        return JsonResponse({'ok': False, 'code': code}, status=401 if code == 'EDITOR_SESSION_ENDED' else 409)
    except EditorFault as exc:
        return JsonResponse({'ok': False, 'code': exc.code}, status=exc.status)
    except PermissionDenied:
        note_denial(request, 'owner')
        return JsonResponse({'ok': False, 'code': 'EDITOR_FIELDS_FORBIDDEN'}, status=403)
    except ObjectDoesNotExist:
        return JsonResponse({'ok': False, 'code': 'EDITOR_PAGE_UNAVAILABLE'}, status=404)
