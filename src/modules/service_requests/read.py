from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from django.db import transaction
from django.db.models import Q

from modules.accounts.api import StaffAccessError, lock_staff_session

from .ledger import IndependentLedger, LedgerError, LedgerState, PrimaryLedger, assess_ledger_state
from .models import ServiceRequest, ServiceRequestDeletionProjection

PAGE_SIZE = 50


class ServiceRequestReadError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class RequestPage:
    rows: tuple[ServiceRequest, ...]
    next_cursor: tuple[datetime, uuid.UUID] | None


def _guarded(*, actor_id, session_generation, ledger, independent, callback):
    try:
        with transaction.atomic():
            lock_staff_session(actor_id=actor_id, session_generation=session_generation)
        with ledger.locked() as session:
            snapshot = session.snapshot()
            receipt = independent.current_receipt()
            with transaction.atomic():
                lock_staff_session(actor_id=actor_id, session_generation=session_generation)
                projection = tuple(
                    ServiceRequestDeletionProjection.objects.select_for_update()
                    .order_by("sequence").values_list("sequence", "request_id")
                )
                ids = tuple(record.request_id for record in snapshot.records)
                live_ids = tuple(
                    ServiceRequest.objects.select_for_update().filter(pk__in=ids)
                    .order_by("id").values_list("id", flat=True)
                )
                if assess_ledger_state(snapshot, receipt, projection, live_ids) != LedgerState.PROJECTED:
                    raise LedgerError("REQUESTS_NOT_READY")
                return callback()
    except StaffAccessError as exc:
        raise ServiceRequestReadError(exc.code) from None
    except ServiceRequestReadError:
        raise
    except Exception:
        raise ServiceRequestReadError("PRIVATE_DATA_UNAVAILABLE") from None


def load_request_page(*, actor_id, session_generation, ledger, independent, before=None) -> RequestPage:
    if before is not None and (
        type(before) is not tuple or len(before) != 2
        or type(before[0]) is not datetime or before[0].tzinfo is not UTC
        or type(before[1]) is not uuid.UUID
    ):
        raise ServiceRequestReadError("INVALID_CURSOR")

    def selected() -> RequestPage:
        rows = ServiceRequest.objects.all()
        if before is not None:
            timestamp, request_id = before
            rows = rows.filter(Q(created_at__lt=timestamp) | Q(created_at=timestamp, id__lt=request_id))
        values = tuple(rows.order_by("-created_at", "-id")[: PAGE_SIZE + 1])
        visible = values[:PAGE_SIZE]
        cursor = (visible[-1].created_at, visible[-1].id) if len(values) > PAGE_SIZE else None
        return RequestPage(visible, cursor)

    return _guarded(actor_id=actor_id, session_generation=session_generation,
                    ledger=ledger, independent=independent, callback=selected)
def load_request_detail(*, actor_id, session_generation, request_id, ledger, independent):
    if type(request_id) is not uuid.UUID:
        raise ServiceRequestReadError("REQUEST_NOT_FOUND")

    def selected():
        try:
            return ServiceRequest.objects.get(pk=request_id)
        except ServiceRequest.DoesNotExist:
            raise ServiceRequestReadError("REQUEST_NOT_FOUND") from None

    return _guarded(actor_id=actor_id, session_generation=session_generation,
                    ledger=ledger, independent=independent, callback=selected)
