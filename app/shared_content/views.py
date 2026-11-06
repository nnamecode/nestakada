"""Private shared editor HTTP. Stored HTML is shown as escaped data."""
from functools import wraps
from pathlib import Path
from uuid import UUID

from django.core.exceptions import PermissionDenied, ObjectDoesNotExist, ValidationError
from django.http import JsonResponse, FileResponse, Http404
from django.db import DatabaseError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from accounts.views import gate
from accounts.services import require_session
from editor_runtime.guards import EditorFault, EditorSlot, InputProfile, input_profile, read_json_bytes
from editor_runtime.processing import normalize_input, strict_json, ProcessingRejected
from . import services as S, commands as C
from .faults import SharedFault
from .models import SharedRevision, SharedReceipt
from .policy import PROTOCOL, canonical_uuid
from .content import content_html, descriptor_for


def guarded(view):
    @wraps(view)
    @gate(owner=True)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except SharedFault as exc:
            value = {'ok': False, 'code': exc.code}
            if exc.operation_not_started:
                value['operationNotStarted'] = True
            if exc.operation_id is not None:
                value['operationId'] = str(exc.operation_id)
            if type(exc.outcome_known) is bool:
                value['outcomeKnown'] = exc.outcome_known
            return JsonResponse(value, status=exc.status)
        except ProcessingRejected:
            return JsonResponse({'ok': False, 'code': 'SHARED_INPUT_REJECTED'}, status=400)
        except EditorFault as exc:
            return JsonResponse({'ok': False, 'code': exc.code}, status=exc.status)
        except PermissionDenied:
            return JsonResponse({'ok': False, 'code': 'SHARED_SESSION_ENDED'}, status=401)
        except ObjectDoesNotExist:
            return JsonResponse({'ok': False, 'code': 'SHARED_OBJECT_UNAVAILABLE'}, status=404)
        except ValidationError:
            return JsonResponse({'ok': False, 'code': 'SHARED_CONTEXT_CONFLICT'}, status=409)
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            return JsonResponse({'ok': False, 'code': 'SHARED_INPUT_REJECTED'}, status=400)
    return wrapped


def operation_response(value):
    return JsonResponse(value, status=409 if value.get('code') == 'SHARED_OPERATION_ABORTED'
                        and value.get('outcomeKnown') is True else 200)


def before_book(function):
    """Used ONLY by pure request/source preparation, never by reconcile/commit."""
    @wraps(function)
    def prepared(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except SharedFault as exc:
            exc.operation_not_started = True
            raise
        except ProcessingRejected:
            raise SharedFault('SHARED_INPUT_REJECTED', 400, operation_not_started=True) from None
        except EditorFault as exc:
            raise SharedFault(exc.code, exc.status, operation_not_started=True) from None
        except PermissionDenied:
            raise SharedFault('SHARED_SESSION_ENDED', 401, operation_not_started=True) from None
        except ObjectDoesNotExist:
            raise SharedFault('SHARED_OBJECT_UNAVAILABLE', 404, operation_not_started=True) from None
        except ValidationError:
            raise SharedFault('SHARED_CONTEXT_CONFLICT', operation_not_started=True) from None
        except DatabaseError:
            raise SharedFault('SHARED_UNAVAILABLE', 503, operation_not_started=True) from None
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            raise SharedFault('SHARED_INPUT_REJECTED', 400, operation_not_started=True) from None
    return prepared


@before_book
def write_input(request, kind, action):
    generation = request.auth_generation
    S.inspect_admission(actor=request.user, kind=kind, generation=generation)
    selected = selector(request)
    raw = read_json_bytes(request, input_profile(owner=True, shared=True))
    value = C.parse_write_request(raw)
    if (value['generation'] != generation or value['sourceMode'] != selected['source_mode']
            or value['draftBasis'] != selected['draft_basis'] or value['stageId'] != selected['stage_id']):
        raise SharedFault('SHARED_INPUT_REJECTED', 400)
    replay = C.lookup_replay(actor=request.user, kind=kind, generation=generation, action=action,
        operation_id=UUID(value['operationId']), fingerprint=S.digest(value), session_key=request.session.session_key)
    return generation, selected, raw, value, replay


@before_book
def write_content(request, kind, selected, raw, value):
    before = inspect(request, kind, selected=selected)
    if value['baseRevisionId'] != before.child['baseRevisionId']:
        raise SharedFault('SHARED_CONTEXT_CONFLICT')
    result = S.validate_result(normalize_input(raw, before.child), raw)
    media_stamp = S.asset_evidence(result['bindings'])
    late_context(request, kind, before, media_stamp, result)
    return before, result, media_stamp


@before_book
def restore_input(request, kind):
    generation = request.auth_generation
    S.inspect_admission(actor=request.user, kind=kind, generation=generation)
    if request.GET:
        raise ValueError()
    raw = read_json_bytes(request, input_profile(owner=True, shared=True))
    value = strict_json(raw.decode())
    if (type(value) is not dict or set(value) != {'protocol', 'generation', 'baseRevisionId',
            'sourceRevisionId', 'operationId', 'confirmReplace'} or value['protocol'] != PROTOCOL
            or type(value['generation']) is not int or value['generation'] != generation):
        raise ValueError()
    canonical_uuid(value['sourceRevisionId']); canonical_uuid(value['operationId'])
    if value['baseRevisionId'] is not None:
        canonical_uuid(value['baseRevisionId'])
    if value['confirmReplace'] is not True:
        raise SharedFault('SHARED_REPLACE_CONFIRMATION_REQUIRED')
    replay = C.lookup_replay(actor=request.user, kind=kind, generation=generation, action='restore_prepare',
        operation_id=UUID(value['operationId']), session_key=request.session.session_key,
        fingerprint=S.digest({'source': value['sourceRevisionId'], 'base': value['baseRevisionId'], 'confirmed': True}))
    return generation, value, replay


@before_book
def restore_content(request, kind, value):
    before = inspect(request, kind)
    if value['baseRevisionId'] != before.current_id:
        raise SharedFault('SHARED_CONTEXT_CONFLICT')
    source = SharedRevision.objects.get(pk=UUID(value['sourceRevisionId']), block_id=before.block_id)
    if source.schema_version != kind + '-v1':
        raise SharedFault('SHARED_VERSION_INCOMPATIBLE')
    import json
    candidate = {'protocol': PROTOCOL, 'generation': before.generation,
        'baseRevisionId': before.current_id, 'sourceMode': 'current', 'draftBasis': None,
        'stageId': None, 'html': content_html(source)}
    wire = json.dumps(candidate, ensure_ascii=False).encode()
    result = S.validate_result(normalize_input(wire, before.child), wire)
    media_stamp = S.asset_evidence(result['bindings'])
    late_context(request, kind, before, media_stamp, result)
    return before


def validated_restore_source(request, kind, source_id, expected_current_id):
    """Revalidate a historical revision against today's policy and media."""
    import json
    before = inspect(request, kind)
    expected = canonical_uuid(expected_current_id) if expected_current_id is not None else None
    if expected != before.current_id:
        raise SharedFault('SHARED_CONTEXT_CONFLICT')
    source = SharedRevision.objects.get(pk=UUID(canonical_uuid(str(source_id))),
                                        block_id=before.block_id)
    if source.schema_version != kind + '-v1':
        raise SharedFault('SHARED_VERSION_INCOMPATIBLE')
    descriptor = descriptor_for(source)
    candidate = {
        'protocol': PROTOCOL, 'generation': before.generation,
        'baseRevisionId': before.current_id, 'sourceMode': 'current',
        'draftBasis': None, 'stageId': None, 'html': content_html(descriptor),
    }
    wire = json.dumps(candidate, ensure_ascii=False).encode()
    result = S.validate_result(normalize_input(wire, before.child), wire)
    if result['changed']:
        raise SharedFault('SHARED_NORMALIZATION_REQUIRED')
    media_stamp = S.asset_evidence(result['bindings'])
    from media_library.models import AssetUsage
    stored = [
        {'assetId': str(asset_id), 'slot': slot}
        for asset_id, slot in AssetUsage.objects.filter(
            kind=AssetUsage.Kind.SHARED_BLOCK, consumer_id=source.pk
        ).order_by('slot').values_list('asset_id', 'slot')
    ]
    if sorted(stored, key=lambda item: item['slot']) != sorted(
            result['bindings'], key=lambda item: item['slot']):
        raise SharedFault('SHARED_MEDIA_UNAVAILABLE')
    late_context(request, kind, before, media_stamp, result)
    return before, source, descriptor, result


def selector(request):
    if any(len(request.GET.getlist(key)) != 1 for key in request.GET):
        raise ValueError()
    if not request.GET:
        return {'source_mode': 'current', 'draft_basis': None, 'stage_id': None}
    value = request.GET
    if set(value) == {'source', 'draftId', 'draftRevision'} and value['source'] == 'owner-draft':
        return {'source_mode': 'owner-draft', 'draft_basis': {
            'id': canonical_uuid(value['draftId']), 'revision': int(value['draftRevision'])}, 'stage_id': None}
    if set(value) == {'source', 'stageId'} and value['source'] == 'restore-stage':
        return {'source_mode': 'restore-stage', 'draft_basis': None, 'stage_id': canonical_uuid(value['stageId'])}
    raise ValueError()


def inspect(request, kind, selected=None):
    return S.inspect_context(actor=request.user, kind=kind, generation=request.auth_generation,
                             **(selector(request) if selected is None else selected))


def late_context(request, kind, before, media_stamp, result):
    actor = require_session(request, touch=False)
    if actor.pk != before.actor_id or request.auth_generation != before.generation:
        raise SharedFault('SHARED_IDENTITY_CHANGED', 403)
    from django.db import transaction
    from page_versions.engine import check_editor_session
    if before.source_descriptor is not None:
        content_html(before.source_descriptor)  # Recheck immutable source bytes outside locks.
    with transaction.atomic():
        after = S.context_locked(actor=actor, kind=kind, generation=before.generation,
            source_mode=before.child['sourceMode'], draft_basis=before.child['draftBasis'], stage_id=before.child['stageId'])
        check_editor_session(actor, before.generation, request.session.session_key)
        if after.stamp != before.stamp:
            raise SharedFault('SHARED_CONTEXT_CONFLICT')
        if S.asset_evidence(result['bindings'], physical=False) != media_stamp:
            raise SharedFault('SHARED_MEDIA_UNAVAILABLE')
    return after


@require_POST
@guarded
def check(request, kind):
    with EditorSlot():
        before = inspect(request, kind)
        raw = read_json_bytes(request, input_profile(owner=True, shared=True))
        result = S.validate_result(normalize_input(raw, before.child), raw)
        # Check has no operation authority; mutation-only fields are not accepted.
        if set(strict_json(raw.decode())) != {'protocol', 'generation', 'baseRevisionId',
                'sourceMode', 'draftBasis', 'stageId', 'html'}:
            raise ValueError()
        media_stamp = S.asset_evidence(result['bindings'])
        after = late_context(request, kind, before, media_stamp, result)
        proof = S.issue_proof(after, result, media_stamp)
    return JsonResponse({'protocol': PROTOCOL, 'normalisedHtml': result['html'],
        'inputFingerprint': result['inputFingerprint'], 'normalisationChanged': result['changed'],
        'checkReceipt': proof, 'baseRevisionId': after.child['baseRevisionId']},
        json_dumps_params={'ensure_ascii': False})


def write(request, kind, action):
    with EditorSlot():
        generation, selected, raw, value, replay = write_input(request, kind, action)
        if replay is not None:
            replay = C.reconcile_replay(actor=request.user, generation=generation,
                session_key=request.session.session_key, value=replay)
            return operation_response(replay)
        before, result, media_stamp = write_content(request, kind, selected, raw, value)
        value = C.write_checked(actor=request.user, kind=kind, generation=before.generation,
            before=before, raw_input=raw, result=result, media_stamp=media_stamp,
            session_key=request.session.session_key, action=action)
    return operation_response(value)


@before_book
def simple_write_input(request, kind):
    """Parse a current/inline-draft write without legacy operation books."""
    generation = request.auth_generation
    S.inspect_admission(actor=request.user, kind=kind, generation=generation)
    selected = selector(request)
    if selected['source_mode'] not in ('current', 'owner-draft'):
        raise SharedFault('SHARED_INPUT_REJECTED', 400)
    raw = read_json_bytes(request, input_profile(owner=True, shared=True))
    value = C.parse_write_request(raw)
    if (value['generation'] != generation
            or value['sourceMode'] != selected['source_mode']
            or value['draftBasis'] != selected['draft_basis']
            or value['stageId'] is not None):
        raise SharedFault('SHARED_INPUT_REJECTED', 400)
    return selected, raw, value


def simple_write(request, kind, action):
    """REF-3 current/inline-draft write with the existing safe normalizer."""
    with EditorSlot():
        selected, raw, value = simple_write_input(request, kind)
        before, result, media_stamp = write_content(request, kind, selected, raw, value)
        from .simple_commands import (commit_normalized_current,
                                      commit_normalized_draft,
                                      save_normalized_draft)
        common = {
            'actor': request.user, 'kind': kind,
            'expected_generation': before.generation,
            'session_key': request.session.session_key,
            'expected_current_id': before.current_id,
            'html': result['html'], 'bindings': result['bindings'],
        }
        basis = selected['draft_basis']
        if action == 'draft':
            row = save_normalized_draft(
                **common,
                draft_id=basis['id'] if basis else None,
                draft_revision=basis['revision'] if basis else None)
            editor_context = {
                'baseRevisionId': str(row.base_revision_id) if row.base_revision_id else None,
                'sourceMode': 'owner-draft',
                'draftBasis': {'id': str(row.pk), 'revision': row.revision},
                'stageId': None,
            }
        elif action == 'apply' and basis is not None:
            row = commit_normalized_draft(
                **common, draft_id=basis['id'], draft_revision=basis['revision'])
            editor_context = {'baseRevisionId': str(row.pk), 'sourceMode': 'current',
                              'draftBasis': None, 'stageId': None}
        elif action == 'apply':
            row = commit_normalized_current(**common)
            editor_context = {'baseRevisionId': str(row.pk), 'sourceMode': 'current',
                              'draftBasis': None, 'stageId': None}
        else:
            raise SharedFault('SHARED_INPUT_REJECTED', 400)
    return operation_response({
        'ok': True,
        'operationId': value['operationId'],
        'resultId': str(row.pk),
        'resultCode': 'applied',
        'replay': False,
        'gone': False,
        'editorContext': editor_context,
    })


def legacy_selected(request):
    """Keep pre-REF-3 file drafts/stages usable until their data migration."""
    selected = selector(request)
    if selected['source_mode'] == 'restore-stage':
        return True
    if selected['source_mode'] != 'owner-draft':
        return False
    from .models import SharedDraft
    basis = selected['draft_basis']
    return SharedDraft.objects.filter(
        pk=basis['id'], revision=basis['revision'], storage_kind='file').exists()


@require_POST
@guarded
def draft(request, kind):
    return write(request, kind, 'draft') if legacy_selected(request) else simple_write(request, kind, 'draft')


@require_POST
@guarded
def apply(request, kind):
    return write(request, kind, 'apply') if legacy_selected(request) else simple_write(request, kind, 'apply')


@require_POST
@guarded
def restore_cancel(request, kind, stage_id):
    with EditorSlot():
        value = cancel_input(request, kind)
        return operation_response(C.cancel_restore_stage(actor=request.user, kind=kind,
            generation=request.auth_generation, stage_id=stage_id, operation_id=value['operationId'],
            confirmed=value['confirmCancel'], session_key=request.session.session_key))


@before_book
def cancel_input(request, kind):
    if request.META.get('QUERY_STRING'):
        raise SharedFault('SHARED_INPUT_REJECTED', 400)
    S.inspect_admission(actor=request.user, kind=kind, generation=request.auth_generation)
    raw = read_json_bytes(request, InputProfile(16384))
    return C.parse_cancel_request(raw, generation=request.auth_generation)


@require_POST
@guarded
def restore_prepare(request, kind):
    # New restores use restore_version().  Keep the URL closed so no new
    # legacy stages/files can appear while existing terminal history remains.
    raise SharedFault('SHARED_LEGACY_RESTORE_DISABLED', 410, operation_not_started=True)


@require_GET
@guarded
def editor(request, kind):
    context = inspect(request, kind)
    return render(request, 'shared_content/editor.html', {'owner': True, 'context': context,
        'base_id': context.child['baseRevisionId'] or ''})


@require_GET
@guarded
def history(request, kind):
    if set(request.GET) - {'page'}:
        raise ValueError()
    data = S.history(actor=request.user, kind=kind, generation=request.auth_generation,
                     page=int(request.GET.get('page', '1')))
    data['owner'] = True
    from .models import SharedCleanupJob
    data['cleanup_jobs'] = list(SharedCleanupJob.objects.filter(block_id=data['context'].block_id)
        .order_by('-created_at', '-id').values('id', 'sequence', 'phase')[:20])
    return render(request, 'shared_content/history.html', data)


@require_GET
@guarded
def version(request, kind, version_id):
    if request.GET:
        raise ValueError()
    context = inspect(request, kind, selected={})
    row = SharedRevision.objects.get(block_id=context.block_id, pk=version_id)
    return render(request, 'shared_content/version.html', {'owner': True, 'context': context, 'row': row,
        'saved_html': content_html(row),
        'compatible': row.schema_version == kind + '-v1'})


@require_POST
@guarded
def restore_version(request, kind, version_id):
    fields = set(request.POST)
    if 'csrfmiddlewaretoken' in fields:
        fields.remove('csrfmiddlewaretoken')
    if (fields != {'expectedCurrentId', 'confirmed'}
            or any(len(request.POST.getlist(key)) != 1 for key in request.POST)
            or request.POST['confirmed'] != 'yes'):
        raise SharedFault('SHARED_REPLACE_CONFIRMATION_REQUIRED', 400)
    expected = request.POST['expectedCurrentId'] or None
    before, source, descriptor, result = validated_restore_source(
        request, kind, version_id, expected)
    from .simple_commands import restore_normalized_current
    restore_normalized_current(
        actor=request.user, kind=kind, expected_generation=request.auth_generation,
        session_key=request.session.session_key, expected_current_id=before.current_id,
        source_revision_id=source.pk, source_descriptor=descriptor,
        html=result['html'], bindings=result['bindings'])
    return redirect('shared_content:editor', kind=kind)


@require_GET
@guarded
def compare(request, kind):
    if set(request.GET) != {'versionId'} or len(request.GET.getlist('versionId')) != 1:
        raise ValueError()
    context = inspect(request, kind, selected={})
    row = SharedRevision.objects.get(block_id=context.block_id, pk=UUID(canonical_uuid(request.GET['versionId'])))
    return render(request, 'shared_content/compare.html', {'owner': True, 'context': context,
        'row': row, 'saved_html': content_html(row)})


@require_GET
@guarded
def result(request, kind, operation_id):
    if request.GET:
        raise ValueError()
    return operation_response(C.lookup_result(actor=request.user, kind=kind, generation=request.auth_generation,
        operation_id=operation_id, session_key=request.session.session_key))


def _cleanup_args(request, kind):
    if request.GET:
        raise ValueError()
    return {'actor': request.user, 'kind': kind, 'generation': request.auth_generation,
            'session_key': request.session.session_key}


def _cleanup_post(request):
    if (set(request.POST) != {'csrfmiddlewaretoken', 'confirmation', 'operationId', 'password', 'confirmed'}
            or any(len(request.POST.getlist(key)) != 1 for key in request.POST)
            or request.POST['confirmed'] != 'yes'):
        raise SharedFault('SHARED_CONFIRMATION_REQUIRED', 400)
    canonical_uuid(request.POST['operationId'])
    return {'operation_id': UUID(request.POST['operationId']),
            'confirmation_token': request.POST['confirmation'], 'password': request.POST['password']}


@require_http_methods(['GET', 'POST'])
@guarded
def cleanup_preview(request, kind, version_id):
    from . import lifecycle as L
    from uuid import uuid4
    args = _cleanup_args(request, kind)
    if request.method == 'POST':
        value = L.confirm(**args, target_id=version_id, **_cleanup_post(request))
        return render(request, 'shared_content/cleanup_status.html', {'owner': True, 'kind': kind, 'state': value})
    value = L.preview(**args, target_id=version_id)
    return render(request, 'shared_content/cleanup.html', {'owner': True, 'preview': value,
        'operation_id': str(uuid4()), 'resume': False})


@require_GET
@guarded
def cleanup_status(request, kind, operation_id):
    from . import lifecycle as L
    args = _cleanup_args(request, kind)
    state = L.status(**args, job_id=operation_id)
    preview = L.preview(**args, job_id=operation_id) if not state['complete'] else None
    return render(request, 'shared_content/cleanup_status.html', {'owner': True, 'kind': kind,
        'state': state, 'preview': preview, 'operation_id': str(operation_id), 'resume': True})


@require_POST
@guarded
def cleanup_resume(request, kind, operation_id):
    from . import lifecycle as L
    args = _cleanup_args(request, kind)
    supplied = _cleanup_post(request)
    if supplied.pop('operation_id') != operation_id:
        raise SharedFault('SHARED_OPERATION_COLLISION')
    state = L.resume(**args, job_id=operation_id, **supplied)
    return render(request, 'shared_content/cleanup_status.html', {'owner': True, 'kind': kind, 'state': state})


@require_GET
@guarded
def diagnostics(request, kind, operation_id):
    from . import lifecycle as L
    value = L.diagnostics(**_cleanup_args(request, kind), operation_id=operation_id)
    return render(request, 'shared_content/diagnostics.html', {'owner': True, 'kind': kind, 'diagnostic': value})


@require_POST
@guarded
def diagnostic_reconcile(request, kind, operation_id):
    from . import lifecycle as L
    if (set(request.POST) != {'csrfmiddlewaretoken', 'password', 'confirmed'}
            or any(len(request.POST.getlist(key)) != 1 for key in request.POST)
            or request.POST['confirmed'] != 'yes'):
        raise SharedFault('SHARED_CONFIRMATION_REQUIRED', 400)
    value = L.reconcile_known(**_cleanup_args(request, kind), operation_id=operation_id, password=request.POST['password'])
    return render(request, 'shared_content/diagnostics.html', {'owner': True, 'kind': kind, 'diagnostic': value})


@require_GET
@gate(owner=True)
def asset(request, name):
    files = {'editor.js': ('editor.js', 'text/javascript'), 'editor.css': ('editor.css', 'text/css')}
    if name not in files:
        raise Http404()
    filename, content_type = files[name]
    return FileResponse((Path(__file__).parent / 'assets' / filename).open('rb'), content_type=content_type)
