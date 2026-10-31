"""Current-only checked saves; original DEV05 atomic engine and permanent ledger."""
import re
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from page_versions import engine as E, schema as S
from page_versions.models import OperationReceipt
from .checks import CheckFault, check_worker_result, verify_check_receipt, inspect_context


def save_request(result):
    if type(result) is not dict or type(result.get('save_request')) is not dict:
        raise CheckFault('EDITOR_WORKER_PROTOCOL')
    meta = result['save_request']
    if (set(meta) != {'operationId', 'checkReceipt', 'baseRevisionId', 'generation', 'fields', 'editingFrom', 'fingerprint'}
            or type(meta['fields']) is not list or any(type(field) is not str for field in meta['fields'])
            or type(meta['fingerprint']) is not str or re.fullmatch('[a-f0-9]{64}', meta['fingerprint']) is None
            or type(meta['checkReceipt']) is not str or len(meta['checkReceipt']) > 8192):
        raise CheckFault('EDITOR_WORKER_PROTOCOL')
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
        action = 'commit_owner' if owner else 'commit_employee'
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
    after = inspect_context(actor=actor, page_id=page_id, generation=generation, origin=origin)
    if before.stamp != after.stamp or meta['baseRevisionId'] != after.child['base_revision_id']:
        # A concurrent identical commit may have advanced current since replay.
        replay = replay_checked(actor=actor, page_id=page_id, generation=generation, meta=meta, session_key=session_key)
        if replay is not None:
            return replay
        raise CheckFault('EDITOR_BASE_CONFLICT')
    verify_check_receipt(meta['checkReceipt'], context=after, changes=worker['changes'])
    if meta['editingFrom'] != 'current':
        raise CheckFault('EDITOR_CAPABILITY_UNAVAILABLE')
    try:
        if after.child['owner']:
            # Preserve every server-owned field of the actual immutable base.
            from content.models import Page
            page = Page.objects.get(pk=E.uid(page_id))
            payload = E.revision(page, meta['baseRevisionId']).payload.copy()
            payload.update(worker['changes'])
            snapshot = S.Snapshot.trusted(payload, page.kind)
            return E.commit_owner(actor=actor, page_id=page_id, base_revision=meta['baseRevisionId'],
                snapshot=snapshot, expected_generation=generation, operation_id=meta['operationId'],
                editor_request_fingerprint=meta['fingerprint'], editor_session_key=session_key)
        return E.commit_employee(actor=actor, page_id=page_id, base_revision=meta['baseRevisionId'],
            patch=S.TextPricePatch(**worker['changes']), expected_generation=generation,
            operation_id=meta['operationId'], editor_request_fingerprint=meta['fingerprint'], editor_session_key=session_key)
    except ValidationError as exc:
        if 'EDITOR_SESSION_ENDED' in str(exc):
            raise CheckFault('EDITOR_SESSION_ENDED') from None
        replay = replay_checked(actor=actor, page_id=page_id, generation=generation, meta=meta, session_key=session_key)
        if replay is not None:
            return replay
        raise CheckFault('EDITOR_OPERATION_CONFLICT') from None
