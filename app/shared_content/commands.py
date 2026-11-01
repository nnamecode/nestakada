"""Atomic shared write pipelines; admission stays closed without a vetted profile."""
from uuid import UUID, uuid4

from django.db import models, transaction
from django.utils import timezone
from audit.constants import Category, Level, Source, Result
from audit.services import record_event
from media_library import services as media
from media_library.models import AssetUsage
from page_versions.engine import check_editor_session
from editor_runtime.processing import strict_json
from . import quota, services as S
from .faults import SharedFault
from .models import (SharedBlock, SharedRevision, SharedDraft, SharedRestoreStage,
                     SharedReceipt, SharedBasePin, SharedBudget)
from .policy import canonical_uuid, POLICY


def parse_write_request(raw_input):
    """Bounded closed DTO, without HTML normalization or current/source reads."""
    if type(raw_input) is not bytes or len(raw_input) > 4 * 1024 * 1024:
        raise SharedFault('SHARED_INPUT_REJECTED', 400)
    try:
        value = strict_json(raw_input.decode('utf-8'))
        if (type(value) is not dict or set(value) != {'protocol', 'generation', 'baseRevisionId',
                'sourceMode', 'draftBasis', 'stageId', 'html', 'operationId', 'checkReceipt'}
                or value['protocol'] != 'shared-editor-v1' or type(value['generation']) is not int
                or value['generation'] < 1 or type(value['html']) is not str
                or len(value['html'].encode('utf-8')) > 1048576
                or type(value['checkReceipt']) is not str or len(value['checkReceipt']) > 16384):
            raise ValueError()
        canonical_uuid(value['operationId'])
        if value['baseRevisionId'] is not None:
            canonical_uuid(value['baseRevisionId'])
        if value['sourceMode'] == 'current':
            if value['draftBasis'] is not None or value['stageId'] is not None:
                raise ValueError()
        elif value['sourceMode'] == 'owner-draft':
            basis = value['draftBasis']
            if (type(basis) is not dict or set(basis) != {'id', 'revision'}
                    or type(basis['revision']) is not int or basis['revision'] < 1 or value['stageId'] is not None):
                raise ValueError()
            canonical_uuid(basis['id'])
        elif value['sourceMode'] == 'restore-stage':
            if value['draftBasis'] is not None:
                raise ValueError()
            canonical_uuid(value['stageId'])
        else:
            raise ValueError()
        return value
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise SharedFault('SHARED_INPUT_REJECTED', 400) from None


def raw(model):
    return models.QuerySet(model=model, using='default')


def sync_assets(kind, consumer_id, bindings):
    wanted = {item['slot']: item['assetId'] for item in bindings}
    for usage in list(AssetUsage.objects.filter(kind=kind, consumer_id=consumer_id)):
        if wanted.get(usage.slot) != str(usage.asset_id):
            media.detach(kind=kind, consumer_id=consumer_id, slot=usage.slot)
    for slot, asset_id in wanted.items():
        if not AssetUsage.objects.filter(kind=kind, consumer_id=consumer_id, slot=slot, asset_id=asset_id).exists():
            media.attach(kind=kind, consumer_id=consumer_id, slot=slot, asset_id=asset_id)


def result_for(receipt, replay=False):
    if receipt.result_code == 'aborted':
        return {'ok': False, 'code': 'SHARED_OPERATION_ABORTED', 'operationId': str(receipt.pk),
            'outcomeKnown': True, 'resultId': None, 'resultCode': 'aborted',
            'replay': replay, 'gone': False, 'editorContext': None}
    kinds = {'sharedrevision': SharedRevision, 'shareddraft': SharedDraft, 'sharedrestorestage': SharedRestoreStage}
    gone = False
    if receipt.result_id is not None:
        model = kinds.get(receipt.result_identity_kind)
        if model is None:
            raise SharedFault('SHARED_RESULT_UNAVAILABLE', 503)
        gone = not model.objects.filter(pk=receipt.result_id, block_id=receipt.block_id).exists()
    editor_context = None
    if not gone and receipt.result_id is not None:
        if receipt.action == 'apply':
            editor_context = {'baseRevisionId': str(receipt.result_id), 'sourceMode': 'current',
                'draftBasis': None, 'stageId': None}
        elif receipt.action == 'draft' and receipt.result_revision is not None:
            editor_context = {'baseRevisionId': str(receipt.base_revision_id) if receipt.base_revision_id else None,
                'sourceMode': 'owner-draft', 'draftBasis': {'id': str(receipt.result_id),
                    'revision': receipt.result_revision}, 'stageId': None}
        elif receipt.action == 'restore_prepare':
            editor_context = {'baseRevisionId': str(receipt.base_revision_id) if receipt.base_revision_id else None,
                'sourceMode': 'restore-stage', 'draftBasis': None, 'stageId': str(receipt.result_id)}
    return {'ok': True, 'operationId': str(receipt.pk), 'resultId': str(receipt.result_id)
        if receipt.result_id else None, 'resultCode': receipt.result_code, 'replay': replay,
        'gone': gone, 'editorContext': editor_context}


def receipt_for(*, actor, generation, context, action, operation_id, fingerprint):
    row = SharedReceipt.objects.filter(pk=operation_id).first()
    if row is not None:
        if (row.actor_id != actor.pk or row.actor_generation != generation or str(row.block_id) != context.block_id
                or row.action != action or row.fingerprint != fingerprint):
            raise SharedFault('SHARED_OPERATION_CONFLICT')
        return row
    return None


def lookup_replay(*, actor, kind, generation, action, operation_id, fingerprint, session_key):
    with transaction.atomic():
        admission = S.admission_locked(actor=actor, kind=kind, generation=generation)
        check_editor_session(actor, generation, session_key)
        row = receipt_for(actor=actor, generation=generation, context=admission, action=action,
                          operation_id=operation_id, fingerprint=fingerprint)
        return result_for(row, replay=True) if row is not None else None


def lookup_result(*, actor, kind, generation, operation_id, session_key):
    with transaction.atomic():
        admission = S.admission_locked(actor=actor, kind=kind, generation=generation)
        check_editor_session(actor, generation, session_key)
        row = SharedReceipt.objects.get(pk=operation_id, block_id=admission.block_id,
            actor_id=actor.pk, actor_generation=generation)
        return result_for(row, replay=True)


def reconcile_replay(*, actor, generation, session_key, value):
    from . import profiles, reservations as R
    if profiles.profile() is not None:
        try:
            with R.session_lease() as lease:
                R.reconcile_pending(lease, actor=actor, generation=generation, session_key=session_key)
        except Exception:
            raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503,
                operation_id=value['operationId'], outcome_known=False) from None
    return value


def finish(*, actor, generation, context, action, operation_id, fingerprint, result_id,
           reservation, source_id=None, result_revision=None):
    from . import reservations as R, profiles
    receipt = SharedReceipt.objects.create(id=operation_id, action=action, actor_id=actor.pk,
        actor_generation=generation, block_id=context.block_id, source_revision_id=source_id,
        base_revision_id=context.child['baseRevisionId'], fingerprint=fingerprint,
        result_code='applied', result_id=result_id, result_revision=result_revision,
        source_stamp=reservation['book']['sourceStamp'], reservation_profile=reservation['book']['profileId'],
        reservation_book_sha256=reservation['sha256'])
    record_event(category=Category.USER_ACTIONS, event_code='SHARED_' + action.upper(), level=Level.INFO,
        source=Source.APPLICATION, result=Result.SUCCESS, actor_id=actor.pk,
        object_kind='shared_block', object_ref=UUID(context.block_id))
    try:
        measured = quota.measure_locked(held_books=[reservation])
    except Exception:
        raise R.UnsafeMeasurement() from None
    raw(SharedBudget).filter(singleton=True).update(snapshot_count=measured['snapshotCount'], charged_bytes=measured['usedBytes'])
    try:
        measured = quota.measure_locked(held_books=[reservation])
    except Exception:
        raise R.UnsafeMeasurement() from None
    R.check_measurement(measured)
    evidence = profiles.evidence()
    if evidence is not None:
        evidence['events'].append({'phase': 'precommit', 'measurement': measured})
    return receipt


def write_checked(*, actor, kind, generation, before, raw_input, result, media_stamp, session_key, action):
    from .commits import write_checked as commit
    return commit(actor=actor, kind=kind, generation=generation, before=before, raw_input=raw_input,
        result=result, media_stamp=media_stamp, session_key=session_key, action=action)


def prepare_restore(*, actor, kind, generation, before, source_id, operation_id, confirmed, session_key):
    from .commits import prepare_restore as prepare
    return prepare(actor=actor, kind=kind, generation=generation, before=before, source_id=source_id,
        operation_id=operation_id, confirmed=confirmed, session_key=session_key)
