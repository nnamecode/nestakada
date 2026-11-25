from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from django.db import transaction
from django.utils import timezone

from modules.accounts.api import StaffAccessError, StaffRole, lock_staff_session
from modules.audit.api import Action, ActorRef, TargetType, append_event

from .ledger import (
    IndependentLedger,
    LedgerError,
    LedgerReason,
    LedgerState,
    PrimaryLedger,
    assess_ledger_state,
)
from .models import ServiceRequest, ServiceRequestDeletionProjection


class ServiceRequestDeleteError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ServiceRequestDeleteResult:
    request_id: uuid.UUID
    sequence: int
    replayed: bool


def _projection() -> tuple[tuple[int, uuid.UUID], ...]:
    return tuple(
        ServiceRequestDeletionProjection.objects.select_for_update()
        .order_by("sequence")
        .values_list("sequence", "request_id")
    )


def _lock_owner_request(
    *,
    actor_id: object,
    session_generation: object,
    request_id: uuid.UUID,
    expected_created_at: datetime,
):
    actor = lock_staff_session(actor_id=actor_id, session_generation=session_generation)
    if (
        actor.role != StaffRole.OWNER
        or actor.username != "nesadmin"
        or not actor.is_superuser
    ):
        raise ServiceRequestDeleteError("FORBIDDEN")
    row = ServiceRequest.objects.select_for_update().filter(pk=request_id).first()
    if row is None:
        raise ServiceRequestDeleteError("REQUEST_NOT_FOUND")
    if row.created_at != expected_created_at:
        raise ServiceRequestDeleteError("CONFIRMATION_STALE")
    return actor, row


def _ledger_db_state(snapshot):
    projection = _projection()
    ids = tuple(record.request_id for record in snapshot.records)
    live_ids = tuple(
        ServiceRequest.objects.select_for_update()
        .filter(pk__in=ids)
        .order_by("id")
        .values_list("id", flat=True)
    )
    return projection, live_ids


def delete_service_request(
    *,
    actor_id: object,
    session_generation: object,
    request_id: object,
    expected_created_at: object,
    ledger: PrimaryLedger,
    independent: IndependentLedger,
) -> ServiceRequestDeleteResult:
    if (
        type(request_id) is not uuid.UUID
        or type(expected_created_at) is not datetime
        or expected_created_at.tzinfo is not UTC
        or expected_created_at.utcoffset() is None
    ):
        raise ServiceRequestDeleteError("INVALID_DELETE_CONFIRMATION")
    authority_changed = False
    try:
        # Authorization and exact confirmation happen before the filesystem is touched.
        with transaction.atomic():
            _lock_owner_request(
                actor_id=actor_id,
                session_generation=session_generation,
                request_id=request_id,
                expected_created_at=expected_created_at,
            )
        with ledger.locked() as ledger_session:
            snapshot = ledger_session.snapshot()
            with transaction.atomic():
                projection, live_ids = _ledger_db_state(snapshot)
            receipt = independent.current_receipt()
            if not snapshot.records and receipt is None:
                if projection or live_ids:
                    raise LedgerError("AMBIGUOUS_GENESIS")
                receipt = independent.publish_and_verify(snapshot)
                if receipt is None:
                    raise ServiceRequestDeleteError("INDEPENDENT_UNAVAILABLE")
            state = assess_ledger_state(snapshot, receipt, projection, live_ids)
            replayed = state != LedgerState.PROJECTED
            if state == LedgerState.PROJECTED:
                authority_changed = True
                snapshot = ledger_session.append(
                    ((request_id, timezone.now(), LedgerReason.OWNER),)
                )
            else:
                authority_changed = True
                if (
                    not snapshot.records
                    or snapshot.records[-1].request_id != request_id
                    or snapshot.records[-1].reason != LedgerReason.OWNER
                    or tuple(projection)
                    != tuple(
                        (record.sequence, record.request_id)
                        for record in snapshot.records[:-1]
                    )
                    or request_id not in live_ids
                ):
                    raise LedgerError("AMBIGUOUS_PENDING_DELETE")
                if receipt is None:
                    if snapshot.generation != 1:
                        raise LedgerError("AMBIGUOUS_PENDING_RECEIPT")
                elif receipt.generation not in {
                    snapshot.generation - 1,
                    snapshot.generation,
                }:
                    raise LedgerError("AMBIGUOUS_PENDING_RECEIPT")
            if receipt is None or receipt.generation != snapshot.generation:
                receipt = independent.publish_and_verify(snapshot)
                if receipt is None:
                    raise ServiceRequestDeleteError("INDEPENDENT_UNAVAILABLE")
            state = assess_ledger_state(
                snapshot,
                receipt,
                projection,
                live_ids or (request_id,),
            )
            if state != LedgerState.INDEPENDENT_VERIFIED:
                raise LedgerError("DELETE_NOT_INDEPENDENTLY_VERIFIED")
            record = snapshot.records[-1]
            # Only this final, short transaction mutates PostgreSQL.
            with transaction.atomic():
                actor, row = _lock_owner_request(
                    actor_id=actor_id,
                    session_generation=session_generation,
                    request_id=request_id,
                    expected_created_at=expected_created_at,
                )
                final_projection, final_live_ids = _ledger_db_state(snapshot)
                if assess_ledger_state(
                    snapshot,
                    receipt,
                    final_projection,
                    final_live_ids,
                ) != LedgerState.INDEPENDENT_VERIFIED:
                    raise LedgerError("DELETE_AUTHORITY_CHANGED")
                ServiceRequestDeletionProjection.objects.create(
                    sequence=record.sequence,
                    request_id=record.request_id,
                )
                row.delete()
                append_event(
                    action=Action.SERVICE_REQUEST_DELETED,
                    actor=ActorRef.user(actor.id, actor.role),
                    target_type=TargetType.SERVICE_REQUEST,
                    target_uuid=record.request_id,
                    detail={"reason": "OWNER"},
                )
                final_projection = _projection()
                all_ids = tuple(item.request_id for item in snapshot.records)
                final_live_ids = tuple(
                    ServiceRequest.objects.select_for_update()
                    .filter(pk__in=all_ids)
                    .order_by("id")
                    .values_list("id", flat=True)
                )
                if assess_ledger_state(
                    snapshot,
                    receipt,
                    final_projection,
                    final_live_ids,
                ) != LedgerState.PROJECTED:
                    raise LedgerError("DELETE_NOT_PROJECTED")
            return ServiceRequestDeleteResult(record.request_id, record.sequence, replayed)
    except ServiceRequestDeleteError as exc:
        if authority_changed and exc.code != "INDEPENDENT_UNAVAILABLE":
            raise ServiceRequestDeleteError("RECONCILIATION_REQUIRED") from None
        raise
    except StaffAccessError as exc:
        if authority_changed:
            raise ServiceRequestDeleteError("RECONCILIATION_REQUIRED") from None
        raise ServiceRequestDeleteError(exc.code) from None
    except Exception:
        if authority_changed:
            raise ServiceRequestDeleteError("RECONCILIATION_REQUIRED") from None
        raise ServiceRequestDeleteError("DELETE_UNAVAILABLE") from None
