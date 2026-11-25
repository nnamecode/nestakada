from __future__ import annotations

import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.db import DatabaseError, close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent
from modules.service_requests.delete import (
    ServiceRequestDeleteError,
    delete_service_request,
)
from modules.service_requests.ledger import (
    DisabledIndependentLedger,
    LedgerReason,
    PrimaryLedger,
    SyntheticIndependentLedger,
)
from modules.service_requests.models import ServiceRequest, ServiceRequestDeletionProjection


REQUEST_ID = uuid.UUID("12345678-1234-4abc-8def-1234567890ab")


class ServiceRequestDeleteTests(TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.ledger = PrimaryLedger(Path(self.temporary.name))
        self.independent = SyntheticIndependentLedger()
        self.owner = User.objects.create_user(
            username="nesadmin",
            password="owner-password",
            role=StaffRole.OWNER,
            is_staff=True,
            is_superuser=True,
        )
        self.employee = User.objects.create_user(
            username="employee",
            password="employee-password",
            role=StaffRole.EMPLOYEE,
            is_staff=True,
            is_superuser=False,
        )
        self.request = ServiceRequest.objects.create(
            id=REQUEST_ID,
            name="Иван",
            phone="+79991234567",
            vehicle_make="Лада",
            vehicle_model="Веста",
            vehicle_year="2024",
            comment="Не заводится",
            consent_text_version="consent-v1",
            consent_text_sha256="a" * 64,
            consented_at=timezone.now(),
        )

    def _delete(self, *, actor: User | None = None, adapter=None):
        return delete_service_request(
            actor_id=(actor or self.owner).id,
            session_generation=(actor or self.owner).generation,
            request_id=self.request.id,
            expected_created_at=self.request.created_at,
            ledger=self.ledger,
            independent=adapter or self.independent,
        )

    def test_owner_delete_orders_ledger_projection_row_and_safe_audit(self) -> None:
        result = self._delete()
        self.assertEqual((result.request_id, result.sequence, result.replayed), (REQUEST_ID, 1, False))
        self.assertFalse(ServiceRequest.objects.filter(pk=REQUEST_ID).exists())
        self.assertEqual(
            tuple(ServiceRequestDeletionProjection.objects.values_list("sequence", "request_id")),
            ((1, REQUEST_ID),),
        )
        event = AuditEvent.objects.get(action=Action.SERVICE_REQUEST_DELETED)
        self.assertEqual(event.target_uuid, REQUEST_ID)
        self.assertEqual(event.actor_uuid, self.owner.id)
        self.assertEqual(event.detail, {"reason": "OWNER"})
        with self.ledger.locked() as session:
            snapshot = session.snapshot()
        self.assertEqual((snapshot.generation, snapshot.records[0].request_id), (1, REQUEST_ID))
        self.assertEqual(self.independent.current_receipt().digest, snapshot.digest)

    def test_employee_and_stale_confirmation_do_not_append(self) -> None:
        for actor, created_at, code in (
            (self.employee, self.request.created_at, "FORBIDDEN"),
            (self.owner, self.request.created_at + timedelta(microseconds=1), "CONFIRMATION_STALE"),
        ):
            with self.subTest(code=code), self.assertRaises(ServiceRequestDeleteError) as raised:
                delete_service_request(
                    actor_id=actor.id,
                    session_generation=actor.generation,
                    request_id=self.request.id,
                    expected_created_at=created_at,
                    ledger=self.ledger,
                    independent=self.independent,
                )
            self.assertEqual(raised.exception.code, code)
            with self.ledger.locked() as session:
                self.assertEqual(session.snapshot().generation, 0)
        self.assertTrue(ServiceRequest.objects.filter(pk=REQUEST_ID).exists())
        self.assertFalse(AuditEvent.objects.filter(action=Action.SERVICE_REQUEST_DELETED).exists())

    def test_unauthorized_or_stale_precheck_never_acquires_ledger_lock(self) -> None:
        class HostileDateTime(type(self.request.created_at)):
            pass

        for actor, created_at in (
            (self.employee, self.request.created_at),
            (self.owner, self.request.created_at + timedelta(microseconds=1)),
            (self.owner, self.request.created_at.replace(tzinfo=None)),
            (
                self.owner,
                HostileDateTime.fromtimestamp(
                    self.request.created_at.timestamp(),
                    tz=self.request.created_at.tzinfo,
                ),
            ),
        ):
            with self.subTest(actor=actor.username), patch.object(
                self.ledger,
                "locked",
            ) as locked, self.assertRaises(ServiceRequestDeleteError):
                delete_service_request(
                    actor_id=actor.id,
                    session_generation=actor.generation,
                    request_id=self.request.id,
                    expected_created_at=created_at,
                    ledger=self.ledger,
                    independent=self.independent,
                )
            locked.assert_not_called()

    def test_independent_refusal_leaves_primary_pending_and_exact_retry_recovers(self) -> None:
        with self.assertRaises(ServiceRequestDeleteError) as raised:
            self._delete(adapter=DisabledIndependentLedger())
        self.assertEqual(raised.exception.code, "INDEPENDENT_UNAVAILABLE")
        self.assertTrue(ServiceRequest.objects.filter(pk=REQUEST_ID).exists())
        self.assertFalse(ServiceRequestDeletionProjection.objects.exists())
        with self.ledger.locked() as session:
            self.assertEqual(session.snapshot().generation, 0)

        class RefuseAfterAppend(SyntheticIndependentLedger):
            def publish_and_verify(self, snapshot):
                if snapshot.generation == 0:
                    return super().publish_and_verify(snapshot)
                return None

        refusing = RefuseAfterAppend()
        with self.assertRaises(ServiceRequestDeleteError) as raised:
            self._delete(adapter=refusing)
        self.assertEqual(raised.exception.code, "INDEPENDENT_UNAVAILABLE")
        with self.ledger.locked() as session:
            self.assertEqual(session.snapshot().generation, 1)
        self.assertTrue(ServiceRequest.objects.filter(pk=REQUEST_ID).exists())
        self.assertFalse(ServiceRequestDeletionProjection.objects.exists())

        recovered = self._delete(adapter=self.independent)
        self.assertEqual((recovered.sequence, recovered.replayed), (1, True))
        self.assertFalse(ServiceRequest.objects.filter(pk=REQUEST_ID).exists())

    def test_db_failure_after_verified_ledger_is_recoverable_without_duplicate(self) -> None:
        with (
            patch(
                "modules.service_requests.delete.append_event",
                side_effect=RuntimeError("private database detail"),
            ),
            self.assertRaises(ServiceRequestDeleteError) as raised,
        ):
            self._delete()
        self.assertEqual(raised.exception.code, "RECONCILIATION_REQUIRED")
        self.assertTrue(ServiceRequest.objects.filter(pk=REQUEST_ID).exists())
        self.assertFalse(ServiceRequestDeletionProjection.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(action=Action.SERVICE_REQUEST_DELETED).exists())
        with self.ledger.locked() as session:
            self.assertEqual(session.snapshot().generation, 1)

        recovered = self._delete()
        self.assertEqual((recovered.sequence, recovered.replayed), (1, True))
        with self.ledger.locked() as session:
            self.assertEqual(session.snapshot().generation, 1)
        self.assertEqual(ServiceRequestDeletionProjection.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action=Action.SERVICE_REQUEST_DELETED).count(), 1)

    def test_wrong_pending_uuid_or_reason_is_not_published(self) -> None:
        cases = (
            (uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), LedgerReason.OWNER),
            (REQUEST_ID, LedgerReason.RETENTION),
        )
        for pending_id, reason in cases:
            with self.subTest(pending_id=pending_id, reason=reason), tempfile.TemporaryDirectory() as directory:
                ledger = PrimaryLedger(Path(directory))
                independent = SyntheticIndependentLedger()
                with ledger.locked() as session:
                    empty = session.snapshot()
                    independent.publish_and_verify(empty)
                    session.append(((pending_id, timezone.now(), reason),))
                with self.assertRaises(ServiceRequestDeleteError) as raised:
                    delete_service_request(
                        actor_id=self.owner.id,
                        session_generation=self.owner.generation,
                        request_id=self.request.id,
                        expected_created_at=self.request.created_at,
                        ledger=ledger,
                        independent=independent,
                    )
                self.assertEqual(raised.exception.code, "RECONCILIATION_REQUIRED")
                self.assertEqual(independent.current_receipt().generation, 0)
                self.assertTrue(ServiceRequest.objects.filter(pk=REQUEST_ID).exists())

    def test_owner_generation_change_after_publish_requires_reconciliation(self) -> None:
        owner_id = self.owner.id

        class BumpOwnerAfterPublish(SyntheticIndependentLedger):
            def publish_and_verify(self, snapshot):
                receipt = super().publish_and_verify(snapshot)
                if snapshot.generation == 1:
                    User.objects.filter(pk=owner_id).update(generation=2)
                return receipt

        adapter = BumpOwnerAfterPublish()
        with self.assertRaises(ServiceRequestDeleteError) as raised:
            self._delete(adapter=adapter)
        self.assertEqual(raised.exception.code, "RECONCILIATION_REQUIRED")
        self.assertTrue(ServiceRequest.objects.filter(pk=REQUEST_ID).exists())
        self.assertFalse(ServiceRequestDeletionProjection.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(action=Action.SERVICE_REQUEST_DELETED).exists())
        with self.ledger.locked() as session:
            self.assertEqual(session.snapshot().generation, 1)
        self.assertEqual(adapter.current_receipt().generation, 1)


class ServiceRequestDeleteConcurrencyTests(TransactionTestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.ledger = PrimaryLedger(Path(self.temporary.name))
        self.independent = SyntheticIndependentLedger()
        self.owner = User.objects.create_user(
            username="nesadmin",
            password="owner-password",
            role=StaffRole.OWNER,
            is_staff=True,
            is_superuser=True,
        )
        self.request = ServiceRequest.objects.create(
            id=REQUEST_ID,
            name="Иван",
            phone="+79991234567",
            consent_text_version="consent-v1",
            consent_text_sha256="a" * 64,
            consented_at=timezone.now(),
        )

    def test_two_connections_never_duplicate_destructive_authority(self) -> None:
        barrier = threading.Barrier(2)
        owner_id = self.owner.id
        generation = self.owner.generation
        request_id = self.request.id
        created_at = self.request.created_at

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                result = delete_service_request(
                    actor_id=owner_id,
                    session_generation=generation,
                    request_id=request_id,
                    expected_created_at=created_at,
                    ledger=self.ledger,
                    independent=self.independent,
                )
                return "OK" if result.sequence == 1 else "BAD_SEQUENCE"
            except ServiceRequestDeleteError as exc:
                return exc.code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [future.result(timeout=20) for future in (pool.submit(worker), pool.submit(worker))]
        self.assertEqual(outcomes.count("OK"), 1)
        self.assertTrue(
            set(outcomes)
            <= {"OK", "DELETE_UNAVAILABLE", "REQUEST_NOT_FOUND", "RECONCILIATION_REQUIRED"}
        )
        with self.ledger.locked() as session:
            self.assertEqual(session.snapshot().generation, 1)
        self.assertEqual(ServiceRequestDeletionProjection.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action=Action.SERVICE_REQUEST_DELETED).count(), 1)
        self.assertFalse(ServiceRequest.objects.filter(pk=REQUEST_ID).exists())

    def test_final_commit_failure_rolls_back_db_but_keeps_verified_authority(self) -> None:
        real_commit = connection.commit
        commits = 0

        def fail_final_commit():
            nonlocal commits
            commits += 1
            if commits == 3:
                raise DatabaseError("synthetic final commit failure")
            return real_commit()

        with patch.object(connection, "commit", side_effect=fail_final_commit):
            with self.assertRaises(ServiceRequestDeleteError) as raised:
                delete_service_request(
                    actor_id=self.owner.id,
                    session_generation=self.owner.generation,
                    request_id=self.request.id,
                    expected_created_at=self.request.created_at,
                    ledger=self.ledger,
                    independent=self.independent,
                )
        self.assertEqual(raised.exception.code, "RECONCILIATION_REQUIRED")
        self.assertEqual(commits, 3)
        self.assertTrue(ServiceRequest.objects.filter(pk=REQUEST_ID).exists())
        self.assertFalse(ServiceRequestDeletionProjection.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(action=Action.SERVICE_REQUEST_DELETED).exists())
        with self.ledger.locked() as session:
            snapshot = session.snapshot()
        self.assertEqual(snapshot.generation, 1)
        self.assertEqual(self.independent.current_receipt().generation, 1)

    def test_independently_committed_prior_live_row_blocks_final_projected(self) -> None:
        prior_id = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        with self.ledger.locked() as session:
            empty = session.snapshot()
            self.independent.publish_and_verify(empty)
            first = session.append(((prior_id, timezone.now(), LedgerReason.OWNER),))
            self.independent.publish_and_verify(first)
        ServiceRequestDeletionProjection.objects.create(sequence=1, request_id=prior_id)

        from modules.service_requests import delete as delete_module

        original = delete_module._lock_owner_request
        calls = 0

        def insert_prior_in_other_connection() -> None:
            close_old_connections()
            try:
                ServiceRequest.objects.create(
                    id=prior_id,
                    name="Prior",
                    phone="+79991234568",
                    consent_text_version="consent-v1",
                    consent_text_sha256="b" * 64,
                    consented_at=timezone.now(),
                )
            finally:
                close_old_connections()

        def inject_prior_live(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                thread = threading.Thread(target=insert_prior_in_other_connection)
                thread.start()
                thread.join(timeout=10)
                if thread.is_alive():
                    raise AssertionError("prior live insertion blocked")
            return original(**kwargs)

        with patch.object(delete_module, "_lock_owner_request", side_effect=inject_prior_live):
            with self.assertRaises(ServiceRequestDeleteError) as raised:
                delete_service_request(
                    actor_id=self.owner.id,
                    session_generation=self.owner.generation,
                    request_id=self.request.id,
                    expected_created_at=self.request.created_at,
                    ledger=self.ledger,
                    independent=self.independent,
                )
        self.assertEqual(raised.exception.code, "RECONCILIATION_REQUIRED")
        self.assertTrue(ServiceRequest.objects.filter(pk=REQUEST_ID).exists())
        self.assertTrue(ServiceRequest.objects.filter(pk=prior_id).exists())
        self.assertEqual(ServiceRequestDeletionProjection.objects.count(), 1)
        self.assertFalse(
            AuditEvent.objects.filter(
                action=Action.SERVICE_REQUEST_DELETED,
                target_uuid=REQUEST_ID,
            ).exists()
        )
