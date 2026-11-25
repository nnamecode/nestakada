from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent
from modules.service_requests.ledger import (
    IndependentReceipt,
    LedgerReason,
    PrimaryLedger,
    SyntheticIndependentLedger,
)
from modules.service_requests.lifecycle import (
    RECONCILIATION_BATCH_SIZE,
    RETENTION_BATCH_SIZE,
    RequestLifecycleError,
    reconcile_live,
    reconcile_restore,
    requests_ready,
    run_retention,
)
from modules.service_requests.models import (
    ServiceRequest,
    ServiceRequestDeletionProjection,
)


class _FailPublish:
    def __init__(self, receipt: IndependentReceipt):
        self.receipt = receipt

    def current_receipt(self):
        return self.receipt

    def publish_and_verify(self, snapshot):
        del snapshot
        return None


class _ReceiptOnly:
    def __init__(self, receipt):
        self.receipt = receipt

    def current_receipt(self):
        return self.receipt

    def publish_and_verify(self, snapshot):
        del snapshot
        return self.receipt


class _ReceiptLookalike:
    def __init__(self, receipt: IndependentReceipt):
        self.generation = receipt.generation
        self.digest = receipt.digest

class ServiceRequestLifecycleTests(TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.ledger = PrimaryLedger(self.root)
        self.independent = SyntheticIndependentLedger()
        with self.ledger.locked() as session:
            self.independent.publish_and_verify(session.snapshot())
        self.now = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)

    def _request(self, created_at: datetime) -> ServiceRequest:
        row = ServiceRequest.objects.create(
            id=uuid.uuid4(),
            name="Synthetic",
            phone="+79991234567",
            consent_text_version="v1",
            consent_text_sha256="a" * 64,
            consented_at=self.now,
        )
        ServiceRequest.objects.filter(pk=row.id).update(created_at=created_at)
        row.refresh_from_db()
        return row

    def _publish_tombstones(self, rows, *, reason=LedgerReason.RETENTION):
        with self.ledger.locked() as session:
            snapshot = session.append(tuple(
                (row.id, self.now, reason) for row in rows
            ))
            self.independent.publish_and_verify(snapshot)
        return snapshot

    def test_retention_uses_exact_cutoff_fixed_batches_and_one_aggregate_audit(self) -> None:
        cutoff = self.now - timedelta(days=30)
        old = tuple(
            self._request(cutoff - timedelta(seconds=index + 1))
            for index in range(RETENTION_BATCH_SIZE + 2)
        )
        boundary = self._request(cutoff)
        newer = self._request(cutoff + timedelta(microseconds=1))

        first = run_retention(
            ledger=self.ledger,
            independent=self.independent,
            now=self.now,
        )
        self.assertEqual((first.deleted_count, first.replayed), (RETENTION_BATCH_SIZE, False))
        self.assertEqual(ServiceRequest.objects.filter(pk__in=[row.id for row in old]).count(), 2)
        self.assertTrue(ServiceRequest.objects.filter(pk=boundary.id).exists())
        self.assertTrue(ServiceRequest.objects.filter(pk=newer.id).exists())
        event = AuditEvent.objects.get(action=Action.SERVICE_REQUEST_RETENTION_BATCH)
        self.assertEqual(event.detail, {"reason": "RETENTION", "count": RETENTION_BATCH_SIZE})

        second = run_retention(
            ledger=self.ledger,
            independent=self.independent,
            now=self.now,
        )
        self.assertEqual(second.deleted_count, 2)
        self.assertEqual(ServiceRequestDeletionProjection.objects.count(), len(old))
        self.assertEqual(
            AuditEvent.objects.filter(action=Action.SERVICE_REQUEST_RETENTION_BATCH).count(),
            2,
        )
        self.assertTrue(requests_ready(ledger=self.ledger, independent=self.independent))

    def test_retention_publish_failure_closes_then_exact_replay_recovers(self) -> None:
        old = self._request(self.now - timedelta(days=31))
        receipt = self.independent.current_receipt()
        assert receipt is not None
        with self.assertRaisesMessage(RequestLifecycleError, "RECONCILIATION_REQUIRED"):
            run_retention(
                ledger=self.ledger,
                independent=_FailPublish(receipt),
                now=self.now,
            )
        self.assertTrue(ServiceRequest.objects.filter(pk=old.id).exists())
        self.assertFalse(ServiceRequestDeletionProjection.objects.exists())
        self.assertFalse(requests_ready(ledger=self.ledger, independent=self.independent))

        recovered = run_retention(
            ledger=self.ledger,
            independent=self.independent,
            now=self.now,
        )
        self.assertEqual((recovered.deleted_count, recovered.replayed), (1, True))
        self.assertFalse(ServiceRequest.objects.filter(pk=old.id).exists())
        self.assertTrue(requests_ready(ledger=self.ledger, independent=self.independent))

    def test_live_reconciliation_is_bounded_idempotent_and_readiness_stays_closed(self) -> None:
        rows = tuple(
            self._request(self.now - timedelta(days=31, seconds=index))
            for index in range(RECONCILIATION_BATCH_SIZE + 1)
        )
        self._publish_tombstones(rows)
        self.assertFalse(requests_ready(ledger=self.ledger, independent=self.independent))

        first = reconcile_live(ledger=self.ledger, independent=self.independent)
        self.assertEqual((first.applied_count, first.ready), (RECONCILIATION_BATCH_SIZE, False))
        first_audit = AuditEvent.objects.get(action=Action.SERVICE_REQUEST_RETENTION_BATCH)
        self.assertEqual(
            first_audit.detail,
            {"reason": "RETENTION", "count": RECONCILIATION_BATCH_SIZE},
        )
        self.assertFalse(requests_ready(ledger=self.ledger, independent=self.independent))
        second = reconcile_live(ledger=self.ledger, independent=self.independent)
        self.assertEqual((second.applied_count, second.ready), (1, True))
        replay = reconcile_live(ledger=self.ledger, independent=self.independent)
        self.assertEqual((replay.applied_count, replay.ready), (0, True))
        self.assertEqual(
            AuditEvent.objects.filter(action=Action.SERVICE_REQUEST_RETENTION_BATCH).count(),
            2,
        )
        self.assertFalse(ServiceRequest.objects.filter(pk__in=[row.id for row in rows]).exists())

    def test_owner_live_reconciliation_requires_and_preserves_owner_attribution(self) -> None:
        row = self._request(self.now)
        self._publish_tombstones((row,), reason=LedgerReason.OWNER)
        with self.assertRaisesMessage(RequestLifecycleError, "RECONCILIATION_UNAVAILABLE"):
            reconcile_live(ledger=self.ledger, independent=self.independent)
        self.assertTrue(ServiceRequest.objects.filter(pk=row.id).exists())
        self.assertFalse(ServiceRequestDeletionProjection.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

        owner = User.objects.create_user(
            username="nesadmin",
            password="owner",
            role=StaffRole.OWNER,
            is_staff=True,
            is_superuser=True,
        )
        result = reconcile_live(
            ledger=self.ledger,
            independent=self.independent,
            actor_id=owner.id,
            session_generation=owner.generation,
        )
        self.assertEqual((result.applied_count, result.ready), (1, True))
        event = AuditEvent.objects.get(action=Action.SERVICE_REQUEST_DELETED)
        self.assertEqual((event.actor_uuid, event.actor_role, event.target_uuid),
                         (owner.id, StaffRole.OWNER, row.id))
        self.assertEqual(event.detail, {"reason": "OWNER"})
        replay = reconcile_live(
            ledger=self.ledger,
            independent=self.independent,
            actor_id=owner.id,
            session_generation=owner.generation,
        )
        self.assertEqual((replay.applied_count, replay.ready), (0, True))
        self.assertEqual(
            AuditEvent.objects.filter(action=Action.SERVICE_REQUEST_DELETED).count(),
            1,
        )

    def test_restore_is_one_transaction_rolls_back_late_and_preserves_audit(self) -> None:
        rows = (self._request(self.now), self._request(self.now))
        snapshot = self._publish_tombstones(rows, reason=LedgerReason.OWNER)
        existing = ServiceRequestDeletionProjection.objects.create(
            sequence=snapshot.generation + 10,
            request_id=uuid.uuid4(),
        )
        audit_before = AuditEvent.objects.count()

        def fail(stage: str) -> None:
            if stage == "after_delete":
                raise RuntimeError("synthetic late failure")

        with self.assertRaisesMessage(
            RequestLifecycleError, "RESTORE_RECONCILIATION_UNAVAILABLE"
        ):
            reconcile_restore(
                ledger=self.ledger,
                independent=self.independent,
                failure_probe=fail,
            )
        self.assertEqual(ServiceRequest.objects.filter(pk__in=[row.id for row in rows]).count(), 2)
        self.assertEqual(
            tuple(ServiceRequestDeletionProjection.objects.values_list("sequence", "request_id")),
            ((existing.sequence, existing.request_id),),
        )
        self.assertEqual(AuditEvent.objects.count(), audit_before)

        result = reconcile_restore(ledger=self.ledger, independent=self.independent)
        self.assertEqual((result.applied_count, result.ready), (2, True))
        self.assertFalse(ServiceRequest.objects.filter(pk__in=[row.id for row in rows]).exists())
        self.assertEqual(AuditEvent.objects.count(), audit_before)
        self.assertTrue(requests_ready(ledger=self.ledger, independent=self.independent))

    def test_restore_rejects_receipt_lookalike_before_any_mutation(self) -> None:
        row = self._request(self.now)
        snapshot = self._publish_tombstones((row,), reason=LedgerReason.OWNER)
        existing = ServiceRequestDeletionProjection.objects.create(
            sequence=snapshot.generation + 10,
            request_id=uuid.uuid4(),
        )
        receipt = self.independent.current_receipt()
        assert receipt is not None
        with self.assertRaisesMessage(
            RequestLifecycleError, "RESTORE_RECONCILIATION_UNAVAILABLE"
        ):
            reconcile_restore(
                ledger=self.ledger,
                independent=_ReceiptOnly(_ReceiptLookalike(receipt)),
            )
        self.assertTrue(ServiceRequest.objects.filter(pk=row.id).exists())
        self.assertEqual(
            tuple(ServiceRequestDeletionProjection.objects.values_list("sequence", "request_id")),
            ((existing.sequence, existing.request_id),),
        )
        self.assertFalse(AuditEvent.objects.exists())

    def test_missing_stale_and_corrupt_authority_never_report_ready(self) -> None:
        self.assertFalse(requests_ready(
            ledger=self.ledger,
            independent=_ReceiptOnly(None),
        ))
        stale = IndependentReceipt(0, "f" * 64)
        self.assertFalse(requests_ready(
            ledger=self.ledger,
            independent=_ReceiptOnly(stale),
        ))
        ledger_path = self.root / "service-request-deletions.jsonl"
        ledger_path.write_bytes(b"corrupt\n")
        self.assertFalse(requests_ready(
            ledger=self.ledger,
            independent=self.independent,
        ))

    def test_management_command_has_no_runtime_authority_or_sensitive_output(self) -> None:
        with self.assertRaisesMessage(CommandError, "RETENTION_UNAVAILABLE"):
            call_command("cleanup_service_requests", verbosity=0)
