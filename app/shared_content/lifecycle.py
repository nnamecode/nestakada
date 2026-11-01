"""Owner-confirmed single-version lifecycle; durable intent precedes metadata deletion."""
from uuid import UUID, uuid4
from functools import wraps
from django.core import signing
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from accounts.models import UserProfile
from page_versions.engine import check_editor_session
from media_library import services as media
from media_library.models import AssetUsage
from . import services as S, commands as C, quota, profiles, reservations as R
from .models import (SharedBlock, SharedRevision, SharedDraft, SharedRestoreStage,
    SharedBasePin, SharedIdentityReservation, SharedCleanupJob, SharedReceipt, SharedBudget)
from .storage import SharedStorage
from .content import descriptor_for
from .faults import SharedFault

SALT = 'shared.cleanup.confirm.v1'
TOKEN_AGE = 300


def _fault_boundary(phase):
    """Deterministic local failure boundary, never an external control channel."""


def _unsafe_guard(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except R.UnsafeMeasurement:
            try: R.latch_fault()
            except Exception: pass
            raise SharedFault('SHARED_CLEANUP_UNCERTAIN', 503, outcome_known=False) from None
    return guarded


def require_no_pending():
    if SharedCleanupJob.objects.exclude(phase='complete').exists():
        raise SharedFault('SHARED_CLEANUP_PENDING', 409, operation_not_started=True)


def write_blob(html):
    # Producers and cleanup share the pinned session lease; no key can be retired
    # between this check and immutable file creation.
    R.assert_connection()
    identity = uuid4()
    key = SharedStorage.new_key(identity)
    if SharedCleanupJob.objects.filter(file_key=key).exists():
        raise SharedFault('SHARED_BLOB_KEY_RETIRED', 409)
    return SharedStorage().write_new(html, blob_id=identity)


def _owner(*, actor, kind, generation, session_key):
    context = S.admission_locked(actor=actor, kind=kind, generation=generation)
    check_editor_session(actor, generation, session_key)
    return context


def _password(actor, kind, generation, session_key, password):
    if type(password) is not str or not 0 < len(password) <= 4096:
        raise SharedFault('SHARED_PASSWORD_REQUIRED', 403)
    with transaction.atomic():
        _owner(actor=actor, kind=kind, generation=generation, session_key=session_key)
        user = UserProfile.objects.select_related('user').get(user_id=actor.pk).user
        hashed = user.password
    if not check_password(password, hashed):
        raise SharedFault('SHARED_PASSWORD_INVALID', 403)
    return hashed


def _fresh(actor, kind, generation, session_key, hashed=None):
    context = _owner(actor=actor, kind=kind, generation=generation, session_key=session_key)
    if hashed is not None and UserProfile.objects.select_related('user').get(user_id=actor.pk).user.password != hashed:
        raise SharedFault('SHARED_CONFIRMATION_STALE')
    return context


def _target(block_id, target_id):
    row = SharedRevision.objects.get(block_id=block_id, pk=target_id)
    reasons = []
    if row.storage_kind != 'file': reasons.append('LEGACY_INLINE')
    block = SharedBlock.objects.get(pk=block_id)
    if row.schema_version != block.kind + '-v1': reasons.append('UNSUPPORTED_SCHEMA')
    identity = SharedIdentityReservation.objects.filter(pk=row.pk, block_id=block_id, kind='sharedrevision').exists()
    if not identity: reasons.append('UNKNOWN_PROVENANCE')
    current = list(SharedBlock.objects.filter(current_revision_id=row.pk).values_list('id', flat=True))
    drafts = list(SharedDraft.objects.filter(base_revision_id=row.pk).values_list('id', flat=True))
    stages = list(SharedRestoreStage.objects.filter(Q(source_revision_id=row.pk) | Q(base_revision_id=row.pk))
                  .order_by('id').values_list('id', 'status', 'source_revision_id', 'base_revision_id'))
    pins = list(SharedBasePin.objects.filter(revision_id=row.pk).order_by('id').values_list('id', 'holder_kind', 'holder_id'))
    if current: reasons.append('CURRENT')
    if drafts: reasons.append('DRAFT_BASE')
    if stages: reasons.append('RESTORE_STAGE')
    if pins: reasons.append('PINNED')
    usages = list(AssetUsage.objects.filter(consumer_id=row.pk).order_by('id').values_list('id', 'kind', 'slot', 'asset_id'))
    if any(item[1] != 'shared_block' for item in usages): reasons.append('UNKNOWN_PROTECTION')
    stamp = S.digest({'target': str(row.pk), 'block': str(block_id), 'descriptor': descriptor_for(row),
        'sequence': row.sequence, 'schema': row.schema_version, 'hash': row.payload_hash,
        'current': list(map(str, current)), 'drafts': list(map(str, drafts)),
        'stages': [[str(x) for x in item] for item in stages],
        'pins': [[str(x) for x in item] for item in pins], 'usages': [[str(x) for x in item] for item in usages]})
    return row, reasons, stamp


def _projection(job):
    return {'operationId': str(job.pk), 'targetId': str(job.target_id), 'phase': job.phase,
        'historyDeleted': job.phase in ('metadata_deleted', 'complete'),
        'fileDeleted': job.file_deleted, 'complete': job.phase == 'complete'}


def _token_payload(actor, generation, session_key, kind, target_id, stamp, job=None):
    return {'actor': actor.pk, 'generation': generation, 'session': S.digest(session_key), 'kind': kind,
        'target': str(target_id), 'stamp': stamp, 'job': str(job.pk) if job else None,
        'phase': job.phase if job else None}


def preview(*, actor, kind, generation, session_key, target_id=None, job_id=None):
    with transaction.atomic():
        context = _owner(actor=actor, kind=kind, generation=generation, session_key=session_key)
        job = SharedCleanupJob.objects.get(pk=job_id, block_id=context.block_id) if job_id else None
        if job is not None and job.phase != 'prepared':
            row, reasons, stamp = None, [], job.source_stamp
        else:
            row, reasons, stamp = _target(context.block_id, job.target_id if job else target_id)
        selected = job.target_id if job else row.pk
        value = {'kind': kind, 'blockId': context.block_id, 'targetId': str(selected),
            'sequence': job.sequence if job else row.sequence, 'authorId': row.author_id if row else None,
            'createdAt': row.created_at.isoformat() if row else None,
            'byteSize': job.byte_size if job else row.byte_size, 'fileKey': job.file_key if job else row.file_key,
            'reasons': reasons, 'canConfirm': not reasons,
            'jobId': str(job.pk) if job else None, 'phase': job.phase if job else None}
        payload = _token_payload(actor, generation, session_key, kind, selected, stamp, job)
    # Never read/hash content while holding the content SQL lock.
    if row is not None and not reasons:
        SharedStorage().read(_descriptor(row))
    value['confirmationToken'] = signing.dumps(payload, salt=SALT, compress=False)
    return value


def _verify(token, expected):
    try:
        if type(token) is not str or len(token) > 4096 or signing.loads(token, salt=SALT, max_age=TOKEN_AGE) != expected:
            raise ValueError()
    except (signing.BadSignature, ValueError, TypeError):
        raise SharedFault('SHARED_CONFIRMATION_STALE') from None


def _measure_locked():
    try:
        value = quota.measure_locked(held_books=[])
        if not value['profileAvailable']:
            raise SharedFault('SHARED_BUDGET_PROFILE_UNAVAILABLE', 503)
        R.check_measurement(value)
        return value
    except Exception:
        raise R.UnsafeMeasurement() from None


def _measure(phase):
    try:
        with transaction.atomic():
            value = _measure_locked()
    except Exception:
        raise R.UnsafeMeasurement() from None
    report = profiles.evidence()
    if report is not None: report['events'].append({'phase': phase, 'measurement': value})
    return value


def _descriptor(job):
    return {'storage_kind': 'file', 'file_key': job.file_key,
            'byte_size': job.byte_size, 'file_sha256': job.file_sha256}


def _continue(lease, job_id, *, actor, kind, generation, session_key, hashed):
    R.require_lease(lease)
    with transaction.atomic():
        context = _fresh(actor, kind, generation, session_key, hashed)
        job = SharedCleanupJob.objects.get(pk=job_id, block_id=context.block_id)
        if job.phase == 'complete': return _projection(job)
        if job.phase == 'prepared':
            row, reasons, stamp = _target(context.block_id, job.target_id)
            if reasons or stamp != job.source_stamp: raise SharedFault('SHARED_CLEANUP_PROTECTED')
    if job.phase == 'prepared':
        SharedStorage().read(_descriptor(job))
    _measure('cleanup_before_delete')
    if job.phase == 'prepared':
        _fault_boundary('before_metadata_delete')
        with transaction.atomic():
            _fresh(actor, kind, generation, session_key, hashed)
            row, reasons, stamp = _target(job.block_id, job.target_id)
            if reasons or stamp != job.source_stamp: raise SharedFault('SHARED_CLEANUP_PROTECTED')
            for usage in list(AssetUsage.objects.filter(kind='shared_block', consumer_id=row.pk)):
                media.detach(kind='shared_block', consumer_id=row.pk, slot=usage.slot)
            C.raw(SharedRevision).filter(pk=row.pk, block_id=job.block_id).delete()
            C.raw(SharedCleanupJob).filter(pk=job.pk, phase='prepared').update(phase='metadata_deleted', updated_at=timezone.now())
            C.record_event(category=C.Category.USER_ACTIONS, event_code='SHARED_HISTORY_DELETE', level=C.Level.INFO,
                source=C.Source.APPLICATION, result=C.Result.SUCCESS, actor_id=actor.pk,
                object_kind='shared_block', object_ref=job.block_id)
            _measure_locked()
        job.phase = 'metadata_deleted'
        _fault_boundary('metadata_deleted')
    _measure('cleanup_metadata_deleted')
    with transaction.atomic():
        _fresh(actor, kind, generation, session_key, hashed)
        # Never unlink any key still referenced by a live content owner.
        referenced = (SharedRevision.objects.filter(file_key=job.file_key, storage_kind='file').exists()
                      or SharedDraft.objects.filter(file_key=job.file_key, storage_kind='file').exists())
        if SharedRevision.objects.filter(pk=job.target_id).exists(): raise SharedFault('SHARED_CLEANUP_PHASE_CONFLICT')
    if not referenced:
        SharedStorage().unlink_verified(_descriptor(job), allow_missing=True)
    _fault_boundary('file_unlinked')
    _measure('cleanup_file_unlinked')
    with transaction.atomic():
        _fresh(actor, kind, generation, session_key, hashed)
        C.raw(SharedCleanupJob).filter(pk=job.pk, phase='metadata_deleted').update(
            phase='complete', file_deleted=not referenced, updated_at=timezone.now())
        _measure_locked()
    _fault_boundary('job_completed')
    _measure('cleanup_complete')
    job.phase = 'complete'
    job.file_deleted = not referenced
    return _projection(job)


@_unsafe_guard
def confirm(*, actor, kind, generation, session_key, operation_id, target_id, confirmation_token, password):
    operation_id, target_id = UUID(str(operation_id)), UUID(str(target_id))
    hashed = _password(actor, kind, generation, session_key, password)
    with R.session_lease() as lease:
        R.reconcile_pending(lease, actor=actor, generation=generation, session_key=session_key)
        with transaction.atomic():
            context = _fresh(actor, kind, generation, session_key, hashed)
            prior = SharedCleanupJob.objects.filter(pk=operation_id).first()
            row, reasons, stamp = _target(context.block_id, target_id) if prior is None else (None, [], prior.source_stamp)
            expected = _token_payload(actor, generation, session_key, kind, target_id, stamp)
            _verify(confirmation_token, expected)
            fingerprint = S.digest({'block': context.block_id, 'target': str(target_id), 'stamp': stamp})
            if prior:
                if prior.block_id != UUID(context.block_id) or prior.target_id != target_id or prior.fingerprint != fingerprint:
                    raise SharedFault('SHARED_OPERATION_COLLISION')
            else:
                require_no_pending()
                if reasons: raise SharedFault('SHARED_CLEANUP_PROTECTED')
                active = profiles.profile()
                measured = quota.measure_locked(held_books=[])
                if active is None or not measured['profileAvailable']:
                    raise SharedFault('SHARED_BUDGET_PROFILE_UNAVAILABLE', 503)
                # Candidate 2MiB hold plus bounded 128KiB growth headroom; vetted by actual calibration.
                if measured['usedBytes'] + active.maintenance_reserve + 131072 > quota.BYTE_LIMIT:
                    raise SharedFault('SHARED_HISTORY_BYTES_FULL')
                prior = SharedCleanupJob.objects.create(id=operation_id, block_id=context.block_id,
                    target_id=target_id, sequence=row.sequence, actor_id=actor.pk, actor_generation=generation,
                    fingerprint=fingerprint, source_stamp=stamp, file_key=row.file_key, byte_size=row.byte_size,
                    file_sha256=row.file_sha256, reserved_bytes=active.maintenance_reserve)
                _measure_locked()
        _fault_boundary('job_durable')
        return _run_continue(lease, prior.pk, actor=actor, kind=kind, generation=generation,
                             session_key=session_key, hashed=hashed)


def _run_continue(lease, job_id, **kwargs):
    try:
        return _continue(lease, job_id, **kwargs)
    except R.UnsafeMeasurement:
        try: R.latch_fault()
        except Exception: pass
        raise SharedFault('SHARED_CLEANUP_UNCERTAIN', 503, operation_id=str(job_id), outcome_known=False) from None
    except (OSError, SharedFault):
        job = SharedCleanupJob.objects.get(pk=job_id)
        if job.phase == 'metadata_deleted':
            value = _projection(job)
            value['code'] = 'SHARED_CLEANUP_PARTIAL'
            return value
        raise


@_unsafe_guard
def resume(*, actor, kind, generation, session_key, job_id, confirmation_token, password):
    hashed = _password(actor, kind, generation, session_key, password)
    with R.session_lease() as lease:
        R.reconcile_pending(lease, actor=actor, generation=generation, session_key=session_key)
        with transaction.atomic():
            context = _fresh(actor, kind, generation, session_key, hashed)
            job = SharedCleanupJob.objects.get(pk=job_id, block_id=context.block_id)
            stamp = _target(context.block_id, job.target_id)[2] if job.phase == 'prepared' else job.source_stamp
            _verify(confirmation_token, _token_payload(actor, generation, session_key, kind, job.target_id, stamp, job))
        return _run_continue(lease, job.pk, actor=actor, kind=kind, generation=generation,
                             session_key=session_key, hashed=hashed)


def status(*, actor, kind, generation, session_key, job_id):
    with transaction.atomic():
        context = _owner(actor=actor, kind=kind, generation=generation, session_key=session_key)
        return _projection(SharedCleanupJob.objects.get(pk=job_id, block_id=context.block_id))


def diagnostics(*, actor, kind, generation, session_key, operation_id):
    with transaction.atomic():
        context = _owner(actor=actor, kind=kind, generation=generation, session_key=session_key)
        receipt = SharedReceipt.objects.filter(pk=operation_id, block_id=context.block_id).first()
        job = SharedCleanupJob.objects.filter(pk=operation_id, block_id=context.block_id).first()
    book, book_state = None, 'unknown'
    try:
        from .journal import SharedJournal
        inventory = SharedStorage().inventory()
        key = 'journal/' + UUID(str(operation_id)).hex + '.json'
        if any(item['key'] == key for item in inventory['files']):
            record = SharedJournal().read(UUID(str(operation_id)))
            if record['book']['blockId'] != context.block_id: raise ValueError()
            book = record['book']; book_state = 'verified'
        else: book_state = 'absent'
    except (SharedFault, ValueError, OSError): pass
    match = receipt is not None and book is not None and R._book_matches(receipt, record)
    try:
        if match:
            with transaction.atomic():
                _owner(actor=actor, kind=kind, generation=generation, session_key=session_key)
                measured = quota.measure_locked(held_books=[record], resolved=True)
                R.check_measurement(measured)
        else:
            measured = quota.measure()
    except Exception:
        measured = None
    return {'operationId': str(operation_id), 'receipt': C.result_for(receipt, replay=True) if receipt else None,
        'book': book, 'bookState': book_state, 'quota': measured, 'quotaKnown': measured is not None,
        'job': _projection(job) if job else None,
        'reconcileAvailable': bool(match and measured and measured['profileAvailable'])}


def reconcile_known(*, actor, kind, generation, session_key, operation_id, password):
    hashed = _password(actor, kind, generation, session_key, password)
    with R.session_lease() as lease:
        with transaction.atomic():
            context = _fresh(actor, kind, generation, session_key, hashed)
            receipt = SharedReceipt.objects.get(pk=operation_id, block_id=context.block_id)
        from .journal import SharedJournal
        record = SharedJournal().read(UUID(str(operation_id)))
        if not R._book_matches(receipt, record): raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503)
        R.reconcile_pending(lease, actor=actor, generation=generation, session_key=session_key)
    return diagnostics(actor=actor, kind=kind, generation=generation, session_key=session_key, operation_id=operation_id)
