from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable

from django.db import transaction
from django.utils import timezone

from modules.accounts.api import StaffRole, lock_staff_session
from modules.audit.api import Action, ActorRef, TargetType, append_event

from .ledger import (
    IndependentLedger,
    IndependentReceipt,
    LedgerError,
    LedgerReason,
    LedgerSnapshot,
    LedgerState,
    PrimaryLedger,
    assess_ledger_state,
)
from .models import ServiceRequest, ServiceRequestDeletionProjection


RETENTION_DAYS = 30
RETENTION_BATCH_SIZE = 100
RECONCILIATION_BATCH_SIZE = 100


class RequestLifecycleError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class RetentionResult:
    cutoff: datetime
    deleted_count: int
    replayed: bool


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    applied_count: int
    ready: bool


def _projection() -> tuple[tuple[int, uuid.UUID], ...]:
    return tuple(
        ServiceRequestDeletionProjection.objects.select_for_update()
        .order_by("sequence")
        .values_list("sequence", "request_id")
    )


def _live_ids(snapshot: LedgerSnapshot) -> tuple[uuid.UUID, ...]:
    identifiers = tuple(record.request_id for record in snapshot.records)
    return tuple(
        ServiceRequest.objects.select_for_update()
        .filter(pk__in=identifiers)
        .order_by("id")
        .values_list("id", flat=True)
    )


def _db_state(snapshot: LedgerSnapshot):
    return _projection(), _live_ids(snapshot)


def _full_receipt(snapshot: LedgerSnapshot, independent: IndependentLedger):
    receipt = independent.current_receipt()
    if (
        type(receipt) is not IndependentReceipt
        or type(receipt.generation) is not int
        or type(receipt.digest) is not str
        or receipt.generation != snapshot.generation
        or receipt.digest != snapshot.digest
    ):
        raise LedgerError("INDEPENDENT_NOT_LATEST")
    return receipt


def requests_ready(*, ledger: PrimaryLedger, independent: IndependentLedger) -> bool:
    try:
        with ledger.locked() as session:
            snapshot = session.snapshot()
            receipt = _full_receipt(snapshot, independent)
            with transaction.atomic():
                projection, live_ids = _db_state(snapshot)
                return assess_ledger_state(
                    snapshot, receipt, projection, live_ids
                ) == LedgerState.PROJECTED
    except Exception:
        return False


def run_retention(
    *,
    ledger: PrimaryLedger,
    independent: IndependentLedger,
    now: datetime | None = None,
) -> RetentionResult:
    captured = timezone.now() if now is None else now
    if (
        type(captured) is not datetime
        or captured.tzinfo is None
        or captured.utcoffset() is None
    ):
        raise RequestLifecycleError("RETENTION_UNAVAILABLE")
    captured = captured.astimezone(UTC)
    cutoff = captured - timedelta(days=RETENTION_DAYS)
    authority_changed = False
    try:
        with ledger.locked() as session:
            snapshot = session.snapshot()
            receipt = independent.current_receipt()
            with transaction.atomic():
                projection, live_ids = _db_state(snapshot)
                state = assess_ledger_state(snapshot, receipt, projection, live_ids)
            replayed = state != LedgerState.PROJECTED
            if state == LedgerState.PROJECTED:
                with transaction.atomic():
                    selected = tuple(
                        ServiceRequest.objects.select_for_update()
                        .filter(created_at__lt=cutoff)
                        .order_by("created_at", "id")
                        .values_list("id", flat=True)[:RETENTION_BATCH_SIZE]
                    )
                if not selected:
                    return RetentionResult(cutoff, 0, False)
                snapshot = session.append(tuple(
                    (request_id, captured, LedgerReason.RETENTION)
                    for request_id in selected
                ))
                authority_changed = True
                pending = snapshot.records[-len(selected):]
            else:
                authority_changed = True
                prefix = len(projection)
                pending = snapshot.records[prefix:]
                if (
                    not pending
                    or len(pending) > RETENTION_BATCH_SIZE
                    or any(record.reason != LedgerReason.RETENTION for record in pending)
                    or frozenset(live_ids)
                    != frozenset(record.request_id for record in pending)
                ):
                    raise LedgerError("AMBIGUOUS_PENDING_RETENTION")
            if receipt is None or receipt.generation != snapshot.generation:
                receipt = independent.publish_and_verify(snapshot)
            if receipt is None:
                raise LedgerError("INDEPENDENT_UNAVAILABLE")
            with transaction.atomic():
                projection, live_ids = _db_state(snapshot)
                if assess_ledger_state(
                    snapshot, receipt, projection, live_ids
                ) != LedgerState.INDEPENDENT_VERIFIED:
                    raise LedgerError("RETENTION_NOT_VERIFIED")
                pending_ids = tuple(record.request_id for record in pending)
                rows = tuple(
                    ServiceRequest.objects.select_for_update()
                    .filter(pk__in=pending_ids)
                    .order_by("id")
                )
                if (
                    len(rows) != len(pending_ids)
                    or {row.id for row in rows} != set(pending_ids)
                    or any(row.created_at >= cutoff for row in rows)
                ):
                    raise LedgerError("RETENTION_SELECTION_CHANGED")
                ServiceRequestDeletionProjection.objects.bulk_create(tuple(
                    ServiceRequestDeletionProjection(
                        sequence=record.sequence,
                        request_id=record.request_id,
                    )
                    for record in pending
                ))
                ServiceRequest.objects.filter(pk__in=pending_ids).delete()
                append_event(
                    action=Action.SERVICE_REQUEST_RETENTION_BATCH,
                    actor=ActorRef.system(),
                    target_type=TargetType.SERVICE_REQUEST,
                    target_uuid=None,
                    detail={"reason": "RETENTION", "count": len(pending)},
                )
                final_projection, final_live_ids = _db_state(snapshot)
                if assess_ledger_state(
                    snapshot, receipt, final_projection, final_live_ids
                ) != LedgerState.PROJECTED:
                    raise LedgerError("RETENTION_NOT_PROJECTED")
            return RetentionResult(cutoff, len(pending), replayed)
    except Exception:
        code = "RECONCILIATION_REQUIRED" if authority_changed else "RETENTION_UNAVAILABLE"
        raise RequestLifecycleError(code) from None


def reconcile_live(
    *,
    ledger: PrimaryLedger,
    independent: IndependentLedger,
    actor_id: object = None,
    session_generation: object = None,
) -> ReconciliationResult:
    try:
        with ledger.locked() as session:
            snapshot = session.snapshot()
            receipt = _full_receipt(snapshot, independent)
            with transaction.atomic():
                projection, live_ids = _db_state(snapshot)
                state = assess_ledger_state(snapshot, receipt, projection, live_ids)
                if state == LedgerState.PROJECTED:
                    return ReconciliationResult(0, True)
                if state != LedgerState.INDEPENDENT_VERIFIED:
                    raise LedgerError("RECONCILIATION_NOT_VERIFIED")
                pending = snapshot.records[
                    len(projection):len(projection) + RECONCILIATION_BATCH_SIZE
                ]
                reasons = frozenset(record.reason for record in pending)
                if not pending or len(reasons) != 1:
                    raise LedgerError("EMPTY_RECONCILIATION")
                reason = pending[0].reason
                actor = None
                if reason == LedgerReason.OWNER:
                    if len(pending) != 1:
                        raise LedgerError("AMBIGUOUS_OWNER_RECONCILIATION")
                    actor = lock_staff_session(
                        actor_id=actor_id,
                        session_generation=session_generation,
                    )
                    if (
                        actor.role != StaffRole.OWNER
                        or actor.username != "nesadmin"
                        or not actor.is_superuser
                    ):
                        raise LedgerError("OWNER_RECONCILIATION_FORBIDDEN")
                ServiceRequestDeletionProjection.objects.bulk_create(tuple(
                    ServiceRequestDeletionProjection(
                        sequence=record.sequence,
                        request_id=record.request_id,
                    )
                    for record in pending
                ))
                ServiceRequest.objects.filter(
                    pk__in=tuple(record.request_id for record in pending)
                ).delete()
                if reason == LedgerReason.RETENTION:
                    append_event(
                        action=Action.SERVICE_REQUEST_RETENTION_BATCH,
                        actor=ActorRef.system(),
                        target_type=TargetType.SERVICE_REQUEST,
                        target_uuid=None,
                        detail={"reason": "RETENTION", "count": len(pending)},
                    )
                else:
                    assert actor is not None
                    append_event(
                        action=Action.SERVICE_REQUEST_DELETED,
                        actor=ActorRef.user(actor.id, actor.role),
                        target_type=TargetType.SERVICE_REQUEST,
                        target_uuid=pending[0].request_id,
                        detail={"reason": "OWNER"},
                    )
                final_projection, final_live_ids = _db_state(snapshot)
                final_state = assess_ledger_state(
                    snapshot, receipt, final_projection, final_live_ids
                )
                if final_state not in {
                    LedgerState.INDEPENDENT_VERIFIED,
                    LedgerState.PROJECTED,
                }:
                    raise LedgerError("RECONCILIATION_INVALID_RESULT")
            return ReconciliationResult(
                len(pending), final_state == LedgerState.PROJECTED
            )
    except Exception:
        raise RequestLifecycleError("RECONCILIATION_UNAVAILABLE") from None


def reconcile_restore(
    *,
    ledger: PrimaryLedger,
    independent: IndependentLedger,
    failure_probe: Callable[[str], None] | None = None,
) -> ReconciliationResult:
    probe = failure_probe or (lambda _stage: None)
    try:
        with ledger.locked() as session:
            snapshot = session.snapshot()
            receipt = _full_receipt(snapshot, independent)
            # Full-chain validity is established by snapshot(); receipt equality
            # above proves this exact latest generation independently verified.
            with transaction.atomic():
                ServiceRequestDeletionProjection.objects.all().delete()
                ServiceRequestDeletionProjection.objects.bulk_create(tuple(
                    ServiceRequestDeletionProjection(
                        sequence=record.sequence,
                        request_id=record.request_id,
                    )
                    for record in snapshot.records
                ))
                probe("after_projection")
                ServiceRequest.objects.filter(
                    pk__in=tuple(record.request_id for record in snapshot.records)
                ).delete()
                probe("after_delete")
            # Read after commit: readiness is never inferred from in-transaction state.
            with transaction.atomic():
                projection, live_ids = _db_state(snapshot)
                if assess_ledger_state(
                    snapshot, receipt, projection, live_ids
                ) != LedgerState.PROJECTED:
                    raise LedgerError("RESTORE_NOT_READY")
            return ReconciliationResult(snapshot.generation, True)
    except Exception:
        raise RequestLifecycleError("RESTORE_RECONCILIATION_UNAVAILABLE") from None
