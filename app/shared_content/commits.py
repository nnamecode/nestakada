"""One leased durable-book/file/atomic-metadata pipeline for real owner commands."""
from uuid import UUID
from django.db import transaction, models
from django.utils import timezone
from page_versions.engine import check_editor_session
from . import commands as C, services as S, reservations as R, quota, profiles
from .faults import SharedFault
from .storage import SharedStorage
from .models import SharedBlock, SharedRevision, SharedDraft, SharedRestoreStage, SharedBasePin
from .policy import POLICY, canonical_uuid


def _context(actor, kind, generation, before, session_key):
    R.assert_connection()
    after = S.context_locked(actor=actor, kind=kind, generation=generation,
        source_mode=before.child['sourceMode'], draft_basis=before.child['draftBasis'], stage_id=before.child['stageId'])
    check_editor_session(actor, generation, session_key)
    if after.stamp != before.stamp or after.current_id != before.child['baseRevisionId']:
        raise SharedFault('SHARED_CONTEXT_CONFLICT')
    return after


def _checkpoint(phase, record):
    try:
        value = quota.measure_locked(held_books=[record])
    except Exception:
        raise R.UnsafeMeasurement() from None
    if not value['profileAvailable']:
        raise SharedFault('SHARED_BUDGET_PROFILE_UNAVAILABLE', 503)
    R.check_measurement(value)
    evidence = profiles.evidence()
    if evidence is not None:
        evidence['events'].append({'phase': phase, 'measurement': value})
    return value


def _run(*, actor, kind, generation, before, session_key, action, operation_id, fingerprint,
         new_refs, validate, mutate, html=None):
    committed, record = False, None
    try:
        prior = C.lookup_replay(actor=actor, kind=kind, generation=generation, action=action,
            operation_id=operation_id, fingerprint=fingerprint, session_key=session_key)
        if prior is not None:
            return C.reconcile_replay(actor=actor, generation=generation, session_key=session_key, value=prior)
        with R.session_lease() as lease:
            # Reconcile before a new source can be required; terminal operations never run twice.
            R.reconcile_pending(lease, actor=actor, generation=generation, session_key=session_key)
            from .lifecycle import require_no_pending
            require_no_pending()
            prior = C.lookup_replay(actor=actor, kind=kind, generation=generation, action=action,
                operation_id=operation_id, fingerprint=fingerprint, session_key=session_key)
            if prior is not None:
                return prior
            try:
                with transaction.atomic():
                    after = _context(actor, kind, generation, before, session_key)
                    validate(after)
            except SharedFault as exc:
                exc.operation_not_started = True
                raise
            R.sample('admission', held_books=[])
            attempt = R.begin_attempt(lease, actor=actor, generation=generation, before=before,
                action=action, operation_id=operation_id, fingerprint=fingerprint)
            try:
                record = R.reserve(lease, actor=actor, generation=generation, session_key=session_key,
                    before=before, action=action, operation_id=operation_id, fingerprint=fingerprint, new_refs=new_refs)
                descriptor = None
                if html is not None:
                    from .lifecycle import write_blob
                    descriptor = write_blob(html)
                    R._fault_boundary('blob_durable')
                    R.check_measurement(R.sample('blob', held_books=[record]))
                R.require_lease(lease)
                with transaction.atomic():
                    after = _context(actor, kind, generation, before, session_key)
                    validate(after)
                    _checkpoint('before_metadata', record)
                    R._fault_boundary('before_metadata')
                    result_id, source_id, result_revision = mutate(after, descriptor, record)
                    receipt = C.finish(actor=actor, generation=generation, context=after, action=action,
                        operation_id=operation_id, fingerprint=fingerprint, result_id=result_id,
                        source_id=source_id, result_revision=result_revision, reservation=record)
                    R._fault_boundary('metadata_written')
                committed = True
                R._fault_boundary('db_committed')
                R.check_measurement(R.sample('postcommit', held_books=[record]))
                R.reconcile_pending(lease, actor=actor, generation=generation, session_key=session_key)
                R.sample('released', held_books=[])
                return C.result_for(receipt)
            except Exception as exc:
                if isinstance(exc, R.UnsafeMeasurement):
                    # Persist only after the surrounding metadata TX rolled back.
                    # A failed latch never proceeds to settlement/release here.
                    try:
                        R.latch_fault()
                    except Exception:
                        pass
                    raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503,
                        operation_id=str(operation_id), outcome_known=False) from None
                if committed:
                    # A committed receipt is never reported as a rolled-back failure.
                    raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503,
                        operation_id=str(operation_id), outcome_known=False) from None
                if isinstance(exc, SharedFault) and exc.operation_not_started:
                    raise
                try:
                    inventory = SharedStorage().inventory()
                    if record is None and inventory['journalCount'] == 0:
                        raise SharedFault('SHARED_RESERVATION_UNAVAILABLE', 503, operation_not_started=True)
                    settled = R.settle_live_abort(lease, attempt, actor=actor,
                        generation=generation, session_key=session_key)
                    if settled is not None and settled.pk == operation_id and settled.result_code == 'aborted':
                        return C.result_for(settled, replay=False)
                except SharedFault as recovery:
                    if recovery.operation_not_started:
                        raise
                except Exception:
                    pass
                raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503,
                    operation_id=str(operation_id), outcome_known=False) from None
            finally:
                R.end_attempt(lease, attempt)
    except SharedFault as exc:
        if committed:
            raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503,
                operation_id=str(operation_id), outcome_known=False) from None
        raise


def write_checked(*, actor, kind, generation, before, raw_input, result, media_stamp, session_key, action):
    if action not in ('draft', 'apply'):
        raise SharedFault('SHARED_INPUT_REJECTED', 400, operation_not_started=True)
    value = C.parse_write_request(raw_input)
    operation_id, fingerprint = UUID(value['operationId']), S.digest(value)

    def validate(after):
        S.verify_proof(value['checkReceipt'], after, result, media_stamp)
        if result['changed']:
            raise SharedFault('SHARED_NORMALIZATION_REQUIRED')
        if S.asset_evidence(result['bindings'], physical=False) != media_stamp:
            raise SharedFault('SHARED_MEDIA_UNAVAILABLE')
        existing = SharedDraft.objects.filter(block_id=after.block_id).first()
        if action == 'draft' and existing is not None:
            basis = before.child['draftBasis']
            if (before.child['sourceMode'] != 'owner-draft' or basis is None
                    or str(existing.pk) != basis['id'] or existing.revision != basis['revision']):
                raise SharedFault('SHARED_DRAFT_BASIS_REQUIRED')

    def mutate(after, descriptor, record):
        if descriptor['file_sha256'] != result['payloadHash']:
            raise SharedFault('SHARED_CONTENT_UNAVAILABLE', 503)
        if action == 'draft':
            row = SharedDraft.objects.select_for_update().filter(block_id=after.block_id).first()
            if row is None:
                row = SharedDraft.objects.create(block_id=after.block_id,
                    base_revision_id=after.child['baseRevisionId'], html='', **descriptor,
                    payload_hash=result['payloadHash'], author_id=actor.pk)
            else:
                C.raw(SharedDraft).filter(pk=row.pk).update(revision=row.revision + 1, html='', **descriptor,
                    payload_hash=result['payloadHash'], updated_at=timezone.now(), author_id=actor.pk)
                row.revision += 1
            C.sync_assets('draft', row.pk, result['bindings'])
            _checkpoint('bindings_written', record)
            if row.base_revision_id and not SharedBasePin.objects.filter(
                    revision_id=row.base_revision_id, holder_kind='draft', holder_id=row.pk).exists():
                SharedBasePin.objects.create(revision_id=row.base_revision_id, holder_kind='draft', holder_id=row.pk)
            return row.pk, None, row.revision
        sequence = SharedRevision.objects.filter(block_id=after.block_id).aggregate(value=models.Max('sequence'))['value'] or 0
        stage = None
        if before.child['sourceMode'] == 'restore-stage':
            stage = SharedRestoreStage.objects.select_for_update().get(pk=before.child['stageId'], status='held')
        row = SharedRevision.objects.create(block_id=after.block_id, sequence=sequence + 1,
            schema_version=result['schemaVersion'], html='', **descriptor, payload_hash=result['payloadHash'],
            author_id=actor.pk, source_revision_id=stage.source_revision_id if stage else None)
        C.sync_assets('shared_block', row.pk, result['bindings'])
        _checkpoint('bindings_written', record)
        block = SharedBlock.objects.get(pk=after.block_id)
        C.raw(SharedBlock).filter(pk=block.pk).update(current_revision=row, generation=block.generation + 1)
        if stage is not None:
            C.raw(SharedRestoreStage).filter(pk=stage.pk).update(status='consumed',
                terminal_operation_id=operation_id, terminal_actor_id=actor.pk)
            C.raw(SharedBasePin).filter(holder_kind='restore_stage', holder_id=stage.pk).delete()
        if before.child['sourceMode'] == 'owner-draft':
            draft = SharedDraft.objects.get(pk=before.child['draftBasis']['id'], block=block)
            C.sync_assets('draft', draft.pk, [])
            C.raw(SharedBasePin).filter(holder_kind='draft', holder_id=draft.pk).delete()
            C.raw(SharedDraft).filter(pk=draft.pk).delete()
        return row.pk, stage.source_revision_id if stage else None, None

    return _run(actor=actor, kind=kind, generation=generation, before=before, session_key=session_key,
        action=action, operation_id=operation_id, fingerprint=fingerprint, new_refs=len(result['bindings']),
        validate=validate, mutate=mutate, html=result['html'])


def prepare_restore(*, actor, kind, generation, before, source_id, operation_id, confirmed, session_key):
    if confirmed is not True:
        raise SharedFault('SHARED_REPLACE_CONFIRMATION_REQUIRED', operation_not_started=True)
    source_id, operation_id = UUID(canonical_uuid(source_id)), UUID(canonical_uuid(operation_id))
    fingerprint = S.digest({'source': str(source_id), 'base': before.child['baseRevisionId'], 'confirmed': True})

    def validate(after):
        source = SharedRevision.objects.get(pk=source_id, block_id=after.block_id)
        if source.schema_version != kind + '-v1':
            raise SharedFault('SHARED_VERSION_INCOMPATIBLE')

    def mutate(after, descriptor, record):
        source = SharedRevision.objects.get(pk=source_id, block_id=after.block_id)
        stage = SharedRestoreStage.objects.create(block_id=after.block_id, actor_id=actor.pk,
            actor_generation=generation, source_revision=source, base_revision_id=after.current_id,
            schema_version=source.schema_version, policy_version=POLICY)
        for revision_id in {source.pk, UUID(after.current_id) if after.current_id else None} - {None}:
            SharedBasePin.objects.create(revision_id=revision_id, holder_kind='restore_stage', holder_id=stage.pk)
        return stage.pk, source.pk, None

    return _run(actor=actor, kind=kind, generation=generation, before=before, session_key=session_key,
        action='restore_prepare', operation_id=operation_id, fingerprint=fingerprint,
        new_refs=0, validate=validate, mutate=mutate)
