"""Session writer lease and durable outcome reconciliation; never a pending DB model."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from uuid import UUID

from django.db import connection, transaction, models
from accounts.services import require_session
from content.models import lock_content
from page_versions.engine import check_editor_session
from .faults import SharedFault
from .models import SharedBlock, SharedReceipt, SharedBudget, SharedIdentityReservation
from .journal import SharedJournal
from .storage import SharedStorage, READ_FLAGS
from . import profiles, services as S

LEASE_KEY = 7342810601
_LEASE = ContextVar('shared_session_writer_lease', default=None)


class UnsafeMeasurement(SharedFault):
    """Observed post-book profile violation; settle/release must not hide it."""
    def __init__(self):
        super().__init__('SHARED_PROFILE_VIOLATION', 503, outcome_known=False)


def _fault_boundary(phase):
    """Fixed phase fault seam; no user-controlled callbacks or authority."""


@dataclass
class Lease:
    backend: object
    pid: int
    active_attempt: object = None

    def assert_current(self):
        if connection.connection is not self.backend or self.backend.closed:
            raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_backend_pid()')
            if cursor.fetchone()[0] != self.pid:
                raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)


@contextmanager
def session_lease():
    if _LEASE.get() is not None or connection.in_atomic_block or not connection.get_autocommit():
        raise SharedFault('SHARED_RESERVATION_BUSY', 503, operation_not_started=True)
    connection.ensure_connection()  # get_autocommit above already connects; pin explicitly.
    backend = connection.connection
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_backend_pid(),pg_try_advisory_lock(%s)', [LEASE_KEY])
        pid, acquired = cursor.fetchone()
    if not acquired:
        raise SharedFault('SHARED_RESERVATION_BUSY', 503, operation_not_started=True)
    lease = Lease(backend, pid)
    token = _LEASE.set(lease)
    try:
        yield lease
    finally:
        try:
            lease.assert_current()
            if connection.in_atomic_block:
                raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_backend_pid(),pg_advisory_unlock(%s)', [LEASE_KEY])
                actual_pid, unlocked = cursor.fetchone()
            if actual_pid != pid or unlocked is not True:
                raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
        except Exception:
            # Never reconnect/retry an uncertain lease. Close only its own backend.
            if connection.connection is backend:
                connection.close()
            elif not backend.closed:
                backend.close()
            raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False) from None
        finally:
            _LEASE.reset(token)


def require_lease(lease):
    if _LEASE.get() is not lease:
        raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
    lease.assert_current()


def assert_connection():
    lease = _LEASE.get()
    if lease is not None:
        require_lease(lease)


@dataclass(frozen=True)
class LiveAttempt:
    actor_id: int
    generation: int
    block_id: str
    operation_id: UUID
    action: str
    fingerprint: str
    source_stamp: str
    profile: object


def begin_attempt(lease, *, actor, generation, before, action, operation_id, fingerprint):
    require_lease(lease)
    if lease.active_attempt is not None:
        raise SharedFault('SHARED_RESERVATION_BUSY', 503, operation_not_started=True)
    profile = profiles.profile()
    if profile is None:
        raise SharedFault('SHARED_BUDGET_PROFILE_UNAVAILABLE', 503, operation_not_started=True)
    attempt = LiveAttempt(actor.pk, generation, before.block_id, operation_id, action,
                          fingerprint, before.stamp, profile)
    lease.active_attempt = attempt
    return attempt


def end_attempt(lease, attempt):
    if lease.active_attempt is attempt:
        lease.active_attempt = None


def sample(phase, *, held_books=None, resolved=False):
    from .quota import measure_locked
    try:
        with transaction.atomic():
            lock_content('default')
            value = measure_locked(held_books=held_books, resolved=resolved)
    except Exception:
        if phase != 'admission':
            raise UnsafeMeasurement() from None
        raise SharedFault('SHARED_MEASUREMENT_UNAVAILABLE', 503, operation_not_started=True) from None
    evidence = profiles.evidence()
    if evidence is not None:
        evidence['events'].append({'phase': phase, 'measurement': value})
    return value


def _budget_raw():
    return models.QuerySet(model=SharedBudget, using='default')


def latch_fault():
    lease = _LEASE.get()
    if lease is not None:
        lease.assert_current()  # Never reconnect an uncertain pinned lease to write a latch.
    with transaction.atomic():
        lock_content('default')
        _budget_raw().filter(singleton=True).update(accounting_version='faulted')


def check_measurement(value):
    from .quota import BYTE_LIMIT, SNAPSHOT_LIMIT
    if (value['effectiveUsedBytes'] is None or value['effectiveUsedBytes'] > BYTE_LIMIT
            or value['snapshotCount'] > SNAPSHOT_LIMIT):
        raise UnsafeMeasurement()


def _book_matches(receipt, record):
    book = record['book']
    return (receipt.actor_id == book['actorId'] and receipt.actor_generation == book['generation']
        and str(receipt.block_id) == book['blockId'] and receipt.action == book['action']
        and receipt.fingerprint == book['inputFingerprint'] and receipt.source_stamp == book['sourceStamp']
        and receipt.reservation_profile == book['profileId']
        and receipt.reservation_book_sha256 == record['sha256'])


def release_verified(lease, record, *, actor, generation, session_key):
    """Only a durable exact outcome may retire its journal entry, never a blob."""
    require_lease(lease)
    journal, fd, locked = SharedJournal(), None, False
    operation_id = UUID(record['book']['operationId'])
    try:
        with journal.storage._journal_parent(operation_id) as (root, parent, leaf):
            fd = os.open(leaf, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
            journal._regular(fd)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            book, wire = journal._read(fd, parent, leaf, operation_id)
            if book != record['book'] or hashlib.sha256(wire).hexdigest() != record['sha256']:
                raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
            with transaction.atomic():
                require_lease(lease)
                S.owner_locked(actor, generation)
                check_editor_session(actor, generation, session_key)
                receipt = SharedReceipt.objects.get(pk=operation_id)
                if not _book_matches(receipt, record):
                    raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
                from .quota import measure_locked
                check_measurement(measure_locked(held_books=[record], resolved=True))
            require_lease(lease)
            journal._read(fd, parent, leaf, operation_id)
            journal.storage._journal_identity(root, parent)
            os.unlink(leaf, dir_fd=parent)
            journal.storage._sync_journal_chain(root, parent)
        # The file lock outlives parent/root named-anchor exit checks.
    finally:
        if fd is not None:
            try:
                if locked:
                    fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)


def reconcile_pending(lease, *, actor, generation, session_key):
    try:
        return _reconcile_pending(lease, actor=actor, generation=generation, session_key=session_key)
    except SharedFault as exc:
        if not isinstance(exc, UnsafeMeasurement) and exc.code not in (
                'SHARED_MEASUREMENT_UNAVAILABLE', 'SHARED_PROFILE_SCHEMA_CHANGED'):
            raise
        try:
            latch_fault()
        except Exception:
            pass
        raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False) from None


def _reconcile_pending(lease, *, actor, generation, session_key):
    require_lease(lease)
    profile = profiles.profile()
    if profile is None:
        raise SharedFault('SHARED_BUDGET_PROFILE_UNAVAILABLE', 503, operation_not_started=True)
    inventory = SharedStorage().inventory()
    names = [row['key'] for row in inventory['files'] if row['kind'] == 'journal']
    if len(names) > 1:
        raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
    if not names:
        return None
    journal = SharedJournal()
    operation_id = UUID(hex=names[0].split('/')[-1][:-5])
    record = journal.read(operation_id)
    book = record['book']
    if profiles.ADMITTED_BOOK_RESERVES.get(book['profileId']) != book['reservedBytes']:
        raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
    with transaction.atomic():
        require_lease(lease)
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout='5s'")
        S.owner_locked(actor, generation)
        check_editor_session(actor, generation, session_key)
        if SharedBudget.objects.get(singleton=True).accounting_version == 'faulted':
            raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
        if not SharedBlock.objects.filter(pk=book['blockId']).exists():
            raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
        receipt = SharedReceipt.objects.filter(pk=operation_id).first()
        if receipt is not None:
            if not _book_matches(receipt, record):
                raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
        else:
            # Restart/re-entry cannot distinguish an ordinary crash from a
            # failed persistent fault latch. Absence alone never authorizes release.
            raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
        from .quota import measure_locked
        try:
            check_measurement(measure_locked(held_books=[record], resolved=True))
        except Exception:
            raise UnsafeMeasurement() from None
    try:
        measured = sample('settled', held_books=[record], resolved=True)
        check_measurement(measured)
        _fault_boundary('before_release')
        require_lease(lease)
        release_verified(lease, record, actor=actor, generation=generation, session_key=session_key)
        _fault_boundary('journal_released')
    except Exception:
        # Keep the book unless its exact, durably confirmed release succeeded.
        try:
            latch_fault()
        except Exception:
            pass
        raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503,
            operation_id=str(operation_id), outcome_known=False) from None
    return receipt


def settle_live_abort(lease, attempt, *, actor, generation, session_key):
    """Only the original live run, AFTER its proved rollback, may create abort."""
    require_lease(lease)
    if (lease.active_attempt is not attempt or connection.in_atomic_block or not connection.get_autocommit()
            or attempt.actor_id != actor.pk or attempt.generation != generation):
        raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
    record = SharedJournal().read(attempt.operation_id)
    book = record['book']
    if (book['actorId'] != attempt.actor_id or book['generation'] != attempt.generation
            or book['blockId'] != attempt.block_id or book['action'] != attempt.action
            or book['inputFingerprint'] != attempt.fingerprint or book['sourceStamp'] != attempt.source_stamp
            or book['profileId'] != attempt.profile.identifier or book['reservedBytes'] != attempt.profile.reserve_bytes):
        raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
    try:
        with transaction.atomic():
            require_lease(lease)
            S.owner_locked(actor, generation)
            check_editor_session(actor, generation, session_key)
            receipt = SharedReceipt.objects.filter(pk=attempt.operation_id).first()
            if receipt is not None:
                if not _book_matches(receipt, record):
                    raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
            else:
                if SharedIdentityReservation.objects.filter(pk=attempt.operation_id).exists():
                    raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False)
                receipt = SharedReceipt.objects.create(id=attempt.operation_id, action=book['action'],
                    actor_id=book['actorId'], actor_generation=book['generation'], block_id=book['blockId'],
                    fingerprint=book['inputFingerprint'], source_stamp=book['sourceStamp'],
                    reservation_profile=book['profileId'], reservation_book_sha256=record['sha256'],
                    result_code='aborted', result_id=None)
                budget = SharedBudget.objects.select_for_update().get(singleton=True)
                _budget_raw().filter(singleton=True).update(
                    retained_debt_bytes=budget.retained_debt_bytes + attempt.profile.usage_abort_debt_allowance)
            from .quota import measure_locked
            try:
                check_measurement(measure_locked(held_books=[record], resolved=True))
            except Exception:
                raise UnsafeMeasurement() from None
    except UnsafeMeasurement:
        try:
            latch_fault()
        except Exception:
            pass
        raise SharedFault('SHARED_RESERVATION_UNCERTAIN', 503, outcome_known=False) from None
    return reconcile_pending(lease, actor=actor, generation=generation, session_key=session_key)


def reserve(lease, *, actor, generation, session_key, before, action, operation_id, fingerprint, new_refs):
    require_lease(lease)
    profile = profiles.profile()
    if profile is None:
        raise SharedFault('SHARED_BUDGET_PROFILE_UNAVAILABLE', 503, operation_not_started=True)
    reconcile_pending(lease, actor=actor, generation=generation, session_key=session_key)
    from .quota import admit_locked
    with transaction.atomic():
        require_lease(lease)
        S.owner_locked(actor, generation)
        check_editor_session(actor, generation, session_key)
        existing = SharedReceipt.objects.filter(pk=operation_id).first()
        if existing is not None:
            if existing.result_code == 'aborted':
                raise SharedFault('SHARED_OPERATION_ABORTED', operation_id=str(operation_id), outcome_known=True)
            raise SharedFault('SHARED_OPERATION_CONFLICT', operation_not_started=True)
        if SharedIdentityReservation.objects.filter(pk=operation_id).exists():
            raise SharedFault('SHARED_OPERATION_CONFLICT', operation_not_started=True)
        admit_locked(snapshot_increment=1 if action == 'apply' else 0, new_refs=new_refs)
    record = SharedJournal().create_or_replay({'bookSchema': 'shared-held-book-v1',
        'profileId': profile.identifier, 'operationId': str(operation_id), 'blockId': before.block_id,
        'action': action, 'actorId': actor.pk, 'generation': generation,
        'inputFingerprint': fingerprint, 'sourceStamp': before.stamp,
        'reservedBytes': profile.reserve_bytes, 'snapshotIncrement': 1 if action == 'apply' else 0})
    _fault_boundary('book_durable')
    check_measurement(sample('book', held_books=[record]))
    return record
