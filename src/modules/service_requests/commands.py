from __future__ import annotations

import uuid
from collections.abc import Callable
from enum import StrEnum

from django.db import IntegrityError, transaction
from django.utils import timezone

from modules.audit.api import Action, ActorRef, TargetType, append_event

from .intake import CanonicalSubmission, canonical_fingerprint
from .ledger import IndependentLedger, LedgerState, PrimaryLedger, assess_ledger_state
from .models import ServiceRequest, ServiceRequestDeletionProjection


class IntakeResult(StrEnum):
    ACCEPTED = "ACCEPTED"
    ACCEPTED_REPLAY = "ACCEPTED_REPLAY"
    CONFLICT = "CONFLICT"


class IntakePersistenceError(RuntimeError):
    pass


_PRIMARY_KEY_CONSTRAINT = "service_requests_servicerequest_pkey"


def _is_primary_key_conflict(error: IntegrityError) -> bool:
    cause = error.__cause__
    diagnostics = getattr(cause, "diag", None)
    return getattr(diagnostics, "constraint_name", None) == _PRIMARY_KEY_CONSTRAINT


def _run_after_commit_safely(
    callback: Callable[[uuid.UUID], None],
    request_id: uuid.UUID,
) -> None:
    try:
        callback(request_id)
    except Exception:
        # Acceptance is already committed. Transport failures are persisted by the
        # callback itself and must never be logged here with request content.
        return


def _row_fingerprint(row: ServiceRequest) -> str:
    return canonical_fingerprint(
        CanonicalSubmission(
            submission_id=row.id,
            name=row.name,
            phone=row.phone,
            vehicle_make=row.vehicle_make,
            vehicle_model=row.vehicle_model,
            vehicle_year=row.vehicle_year,
            comment=row.comment,
            consent_text_version=row.consent_text_version,
            consent_text_sha256=row.consent_text_sha256,
        )
    )


def accept_submission(
    submission: CanonicalSubmission,
    *,
    after_commit: Callable[[uuid.UUID], None],
) -> IntakeResult:
    expected_fingerprint = canonical_fingerprint(submission)
    with transaction.atomic():
        try:
            with transaction.atomic():
                row = ServiceRequest.objects.create(
                    id=submission.submission_id,
                    name=submission.name,
                    phone=submission.phone,
                    vehicle_make=submission.vehicle_make,
                    vehicle_model=submission.vehicle_model,
                    vehicle_year=submission.vehicle_year,
                    comment=submission.comment,
                    consent_text_version=submission.consent_text_version,
                    consent_text_sha256=submission.consent_text_sha256,
                    consented_at=timezone.now(),
                )
        except IntegrityError as exc:
            if not _is_primary_key_conflict(exc):
                raise IntakePersistenceError("PERSISTENCE_FAILURE") from None
            row = ServiceRequest.objects.select_for_update().get(pk=submission.submission_id)
            if _row_fingerprint(row) != expected_fingerprint:
                return IntakeResult.CONFLICT
            return IntakeResult.ACCEPTED_REPLAY
        append_event(
            action=Action.SERVICE_REQUEST_ACCEPTED,
            actor=ActorRef.anonymous(),
            target_type=TargetType.SERVICE_REQUEST,
            target_uuid=row.id,
        )
        transaction.on_commit(lambda: _run_after_commit_safely(after_commit, row.id))
    return IntakeResult.ACCEPTED


def accept_submission_guarded(
    submission: CanonicalSubmission,
    *,
    after_commit: Callable[[uuid.UUID], None],
    ledger: PrimaryLedger,
    independent: IndependentLedger,
) -> IntakeResult:
    try:
        # The transaction is outside the ledger context so on_commit callbacks
        # run only after the outermost caller transaction and after lock release.
        with transaction.atomic():
            with ledger.locked() as ledger_session:
                snapshot = ledger_session.snapshot()
                receipt = independent.current_receipt()
                projection = tuple(
                    ServiceRequestDeletionProjection.objects.select_for_update()
                    .order_by("sequence")
                    .values_list("sequence", "request_id")
                )
                tombstoned_ids = tuple(record.request_id for record in snapshot.records)
                live_ids = tuple(
                    ServiceRequest.objects.select_for_update()
                    .filter(pk__in=tombstoned_ids)
                    .order_by("id")
                    .values_list("id", flat=True)
                )
                if assess_ledger_state(
                    snapshot, receipt, projection, live_ids
                ) != LedgerState.PROJECTED:
                    raise IntakePersistenceError("REQUESTS_UNAVAILABLE")
                result = accept_submission(submission, after_commit=after_commit)
    except IntakePersistenceError:
        raise
    except Exception:
        raise IntakePersistenceError("REQUESTS_UNAVAILABLE") from None
    return result
