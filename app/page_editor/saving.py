"""Current-only checked saves; original DEV05 atomic engine and permanent ledger."""
import re
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from page_versions import engine as E, schema as S
from page_versions.models import OperationReceipt
from .checks import CheckFault, check_worker_result, verify_check_receipt, inspect_context
from .input_policy import validate_source
from . import media
from . import embedded


def save_request(result):
    if type(result) is not dict or type(result.get('save_request')) is not dict:
        raise CheckFault('EDITOR_WORKER_PROTOCOL')
    meta = result['save_request']
    if (set(meta) != {'operationId', 'checkReceipt', 'baseRevisionId', 'generation', 'fields', 'editingFrom', 'fingerprint', 'source', 'action'}
            or type(meta['fields']) is not list or any(type(field) is not str for field in meta['fields'])
            or type(meta['fingerprint']) is not str or re.fullmatch('[a-f0-9]{64}', meta['fingerprint']) is None
            or type(meta['checkReceipt']) is not str or len(meta['checkReceipt']) > 8192):
        raise CheckFault('EDITOR_WORKER_PROTOCOL')
    try:
        validate_source(meta['source'])
        if (type(meta['generation']) is not int or meta['generation'] <= 0
                or type(meta['action']) is not str or meta['action'] not in ('save', 'draft')
                or not meta['fields'] or len(meta['fields']) != len(set(meta['fields']))):
            raise ValueError()
    except (ValueError, TypeError):
        raise CheckFault('EDITOR_WORKER_PROTOCOL') from None
    if meta['editingFrom'] != meta['source']['editingFrom']:
        raise CheckFault('EDITOR_INPUT_REJECTED')
    for field in ('operationId', 'baseRevisionId'):
        if type(meta[field]) is not str or str(E.uid(meta[field])) != meta[field]:
            raise CheckFault('EDITOR_WORKER_PROTOCOL')
    return meta


def replay_checked(*, actor, page_id, generation, meta, session_key):
    """No payload/history lookup: result remains available after ordinary prune."""
    with transaction.atomic():
        page, profile, fields, owner, state = E.enter(actor, page_id, generation)
        try:
            E.check_editor_session(actor, generation, session_key)
        except ValidationError:
            raise CheckFault('EDITOR_SESSION_ENDED') from None
        if generation != meta['generation'] or not set(meta['fields']) <= set(fields):
            raise PermissionDenied('EDITOR_FIELDS_FORBIDDEN')
        row = OperationReceipt.objects.filter(pk=E.uid(meta['operationId'])).first()
        if row is None:
            return None
        action = ('rebase_draft' if meta['source']['rebase'] else 'save_draft') if meta['action'] == 'draft' else ('commit_owner' if owner else 'commit_employee')
        if meta['action'] == 'draft' and not owner:
            raise PermissionDenied('EDITOR_FIELDS_FORBIDDEN')
        if (row.action != action or row.actor_id != actor.pk or row.actor_generation != generation
                or row.page_id != page.pk or not row.editor_request_fingerprint
                or row.editor_request_fingerprint != meta['fingerprint']):
            raise CheckFault('EDITOR_OPERATION_CONFLICT')
        return E.result(row, True)


def commit_checked(*, actor, page_id, generation, origin, before, raw, result, session_key):
    E.outside()
    meta = save_request(result)
    replay = replay_checked(actor=actor, page_id=page_id, generation=generation, meta=meta, session_key=session_key)
    if replay is not None:
        return replay
    worker = {key: value for key, value in result.items() if key != 'save_request'}
    worker = check_worker_result(worker, raw=raw, context=before)
    if worker['changed']:
        raise CheckFault('EDITOR_NORMALIZATION_REQUIRED')
    try:
        after = inspect_context(actor=actor, page_id=page_id, generation=generation, origin=origin,
                                selector=meta['source'])
    except CheckFault:
        replay = replay_checked(actor=actor, page_id=page_id, generation=generation, meta=meta, session_key=session_key)
        if replay is not None:
            return replay
        raise
    if before.stamp != after.stamp or meta['baseRevisionId'] != after.child['base_revision_id']:
        # A concurrent identical commit may have advanced current since replay.
        replay = replay_checked(actor=actor, page_id=page_id, generation=generation, meta=meta, session_key=session_key)
        if replay is not None:
            return replay
        raise CheckFault('EDITOR_BASE_CONFLICT')
    derived_payload, map_hash = None, None
    if 'derived' in worker:
        derived_payload, map_hash = embedded.validate_derived(after, worker, save=True)
    # Authentic receipt/context/canonical map authority precedes new FS work.
    verify_check_receipt(meta['checkReceipt'], context=after, changes=worker['changes'],
        derived_map_hash=map_hash, _before_fs=True)
    media_evidence = media.prepare(after, worker['changes'], derived=worker.get('derived'))
    if media_evidence is not None:
        after = media.late_context(actor=actor, page_id=page_id, generation=generation,
            session_key=session_key, origin=origin, before=after, evidence=media_evidence)
    verify_check_receipt(meta['checkReceipt'], context=after, changes=worker['changes'],
                         media_evidence=media_evidence.proof if media_evidence else None, derived_map_hash=map_hash)
    try:
        source = meta['source']
        if source['rebase'] and meta['action'] != 'draft':
            raise CheckFault('EDITOR_OPERATION_CONFLICT')
        if after.child['owner']:
            # Preserve every server-owned field of the actual immutable base.
            from content.models import Page
            page = Page.objects.get(pk=E.uid(page_id))
            payload = derived_payload if derived_payload is not None else {**after.payload, **worker['changes']}
            snapshot = S.Snapshot.trusted(payload, page.kind)
            if meta['action'] == 'draft':
                if source['editingFrom'] == 'restore-stage':
                    raise CheckFault('EDITOR_CAPABILITY_UNAVAILABLE')
                return E.save_owner_draft(actor=actor, page_id=page_id,
                    base_revision=source['targetCurrentId'] if source['rebase'] else meta['baseRevisionId'],
                    snapshot=snapshot, expected_generation=generation, operation_id=meta['operationId'],
                    draft_revision=source['draftBasis']['revision'] if source['draftBasis'] else None,
                    rebase=source['rebase'], draft_id=source['draftBasis']['id'] if source['draftBasis'] else None,
                    expected_draft_hash=S.digest(after.payload) if source['draftBasis'] else None,
                    expected_draft_base=meta['baseRevisionId'] if source['draftBasis'] else None,
                    editor_request_fingerprint=meta['fingerprint'], editor_session_key=session_key)
            return E.commit_owner(actor=actor, page_id=page_id, base_revision=meta['baseRevisionId'],
                snapshot=snapshot, expected_generation=generation, operation_id=meta['operationId'],
                stage_id=source['stageId'],
                draft_id=source['draftBasis']['id'] if source['draftBasis'] else None,
                draft_revision=source['draftBasis']['revision'] if source['draftBasis'] else None,
                expected_draft_hash=S.digest(after.payload) if source['draftBasis'] else None,
                editor_request_fingerprint=meta['fingerprint'], editor_session_key=session_key)
        return E.commit_employee(actor=actor, page_id=page_id, base_revision=meta['baseRevisionId'],
            patch=S.TextPricePatch(**worker['changes']), expected_generation=generation,
            operation_id=meta['operationId'], stage_id=source['stageId'],
            editor_request_fingerprint=meta['fingerprint'], editor_session_key=session_key)
    except ValidationError as exc:
        if 'EDITOR_SESSION_ENDED' in str(exc):
            raise CheckFault('EDITOR_SESSION_ENDED') from None
        replay = replay_checked(actor=actor, page_id=page_id, generation=generation, meta=meta, session_key=session_key)
        if replay is not None:
            return replay
        raise CheckFault('EDITOR_OPERATION_CONFLICT') from None
