from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from modules.accounts.models import StaffRole, User
from modules.service_requests.ledger import LedgerReason, PrimaryLedger, SyntheticIndependentLedger
from modules.service_requests.models import ServiceRequest
from modules.service_requests.read import PAGE_SIZE, ServiceRequestReadError, load_request_detail, load_request_page


class ServiceRequestReadTests(TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.ledger = PrimaryLedger(Path(self.temporary.name)); self.independent = SyntheticIndependentLedger()
        with self.ledger.locked() as session: self.independent.publish_and_verify(session.snapshot())
        self.owner = User.objects.create_user(username="nesadmin", password="owner", role=StaffRole.OWNER,
                                              is_staff=True, is_superuser=True)
        self.employee = User.objects.create_user(username="employee", password="employee", role=StaffRole.EMPLOYEE,
                                                 is_staff=True, is_superuser=False)
        self.request = ServiceRequest.objects.create(id=uuid.uuid4(), name="Иван", phone="+79991234567",
            consent_text_version="v1", consent_text_sha256="a" * 64, consented_at=timezone.now())

    def test_active_owner_and_employee_receive_bounded_read_only_projection(self) -> None:
        for actor in (self.owner, self.employee):
            page = load_request_page(actor_id=actor.id, session_generation=actor.generation,
                ledger=self.ledger, independent=self.independent)
            self.assertEqual(page.rows, (self.request,))
            detail = load_request_detail(actor_id=actor.id, session_generation=actor.generation,
                request_id=self.request.id, ledger=self.ledger, independent=self.independent)
            self.assertEqual(detail.id, self.request.id)

    def test_fixed_page_size_and_keyset_cursor(self) -> None:
        for index in range(PAGE_SIZE):
            ServiceRequest.objects.create(id=uuid.uuid4(), name=f"Client {index}", phone=f"+7999{index:07d}",
                consent_text_version="v1", consent_text_sha256="a" * 64, consented_at=timezone.now())
        first = load_request_page(actor_id=self.owner.id, session_generation=1,
            ledger=self.ledger, independent=self.independent)
        self.assertEqual(len(first.rows), PAGE_SIZE); self.assertIsNotNone(first.next_cursor)
        second = load_request_page(actor_id=self.owner.id, session_generation=1, before=first.next_cursor,
            ledger=self.ledger, independent=self.independent)
        self.assertEqual(len(second.rows), 1)
        combined = first.rows + second.rows
        self.assertEqual(len({row.id for row in combined}), PAGE_SIZE + 1)
        self.assertEqual(
            tuple((row.created_at, row.id) for row in combined),
            tuple(sorted(((row.created_at, row.id) for row in combined), reverse=True)),
        )

    def test_inactive_or_ledger_mismatch_closes_all_reads(self) -> None:
        User.objects.filter(pk=self.employee.id).update(is_active=False)
        with self.assertRaises(ServiceRequestReadError):
            load_request_page(actor_id=self.employee.id, session_generation=1,
                ledger=self.ledger, independent=self.independent)
        with self.ledger.locked() as session:
            session.append(((uuid.uuid4(), timezone.now(), LedgerReason.OWNER),))
        with self.assertRaises(ServiceRequestReadError) as raised:
            load_request_detail(actor_id=self.owner.id, session_generation=1, request_id=self.request.id,
                ledger=self.ledger, independent=self.independent)
        self.assertEqual(raised.exception.code, "PRIVATE_DATA_UNAVAILABLE")

    def test_invalid_session_never_touches_ledger_or_independent_storage(self) -> None:
        User.objects.filter(pk=self.employee.id).update(is_active=False)
        independent = Mock(wraps=self.independent)
        with patch.object(self.ledger, "locked") as locked, self.assertRaises(ServiceRequestReadError):
            load_request_page(actor_id=self.employee.id, session_generation=1,
                ledger=self.ledger, independent=independent)
        locked.assert_not_called()
        independent.current_receipt.assert_not_called()

    def test_unready_guard_never_executes_pii_query_callback(self) -> None:
        with self.ledger.locked() as session:
            session.append(((uuid.uuid4(), timezone.now(), LedgerReason.OWNER),))
        with patch.object(ServiceRequest.objects, "all", wraps=ServiceRequest.objects.all) as all_rows:
            with self.assertRaises(ServiceRequestReadError):
                load_request_page(actor_id=self.owner.id, session_generation=1,
                    ledger=self.ledger, independent=self.independent)
        all_rows.assert_not_called()
        with patch.object(ServiceRequest.objects, "get", wraps=ServiceRequest.objects.get) as detail:
            with self.assertRaises(ServiceRequestReadError):
                load_request_detail(actor_id=self.owner.id, session_generation=1,
                    request_id=self.request.id, ledger=self.ledger, independent=self.independent)
        detail.assert_not_called()

    def test_invalid_cursor_and_missing_detail_are_constant(self) -> None:
        for cursor in ((timezone.now(), str(uuid.uuid4())), ("bad", uuid.uuid4()), (), object()):
            with self.subTest(cursor=cursor), self.assertRaises(ServiceRequestReadError) as raised:
                load_request_page(actor_id=self.owner.id, session_generation=1, before=cursor,
                    ledger=self.ledger, independent=self.independent)
            self.assertEqual(raised.exception.code, "INVALID_CURSOR")
        with self.assertRaises(ServiceRequestReadError) as raised:
            load_request_detail(actor_id=self.owner.id, session_generation=1,
                request_id=uuid.uuid4(), ledger=self.ledger, independent=self.independent)
        self.assertEqual(raised.exception.code, "REQUEST_NOT_FOUND")

    def test_concurrent_writer_lock_makes_read_fail_closed_without_pii_query(self) -> None:
        with self.ledger.locked(), patch.object(
            ServiceRequest.objects,
            "all",
            wraps=ServiceRequest.objects.all,
        ) as all_rows:
            with self.assertRaises(ServiceRequestReadError) as raised:
                load_request_page(actor_id=self.owner.id, session_generation=1,
                    ledger=self.ledger, independent=self.independent)
        self.assertEqual(raised.exception.code, "PRIVATE_DATA_UNAVAILABLE")
        all_rows.assert_not_called()
