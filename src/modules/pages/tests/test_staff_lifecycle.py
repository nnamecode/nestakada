from __future__ import annotations

import hashlib
import inspect
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from modules.accounts import api as accounts_api
from modules.accounts.models import StaffRole, User
from modules.accounts.staff import (
    StaffCommandError,
    create_employee,
    set_employee_password,
)
from modules.audit.models import Action, AuditEvent

from ..commands import PageCommandError, save_page_content
from ..content import canonical_payload_hash
from ..models import Page, PageContent, PageGrant, PageKind
from ..staff import (
    StaffLifecycleError,
    deactivate_employee,
    reactivate_employee,
    staff_grants_digest,
)


PASSWORD_A = "Unique!Employee-Alpha-2026"
PASSWORD_B = "Unique!Employee-Beta-2026"


def _payload() -> dict:
    return {
        "schema": "estakada.page-content",
        "schema_version": 1,
        "kind": PageKind.ARTICLE,
        "fields": {
            "seo": {"title": "T", "description": "D", "allow_index": True},
            "heading": {"h1": "H"},
            "intro": "<p>Intro</p>",
            "body": "<p>Body</p>",
            "media": {"hero": None, "body": [], "works": []},
        },
    }


class StaffLifecycleTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="nesadmin", password=PASSWORD_A, role=StaffRole.OWNER
        )
        self.employee = User.objects.create_user(
            username="editor", password=PASSWORD_A, role=StaffRole.EMPLOYEE
        )
        self.inactive = User.objects.create_user(
            username="inactive", password=PASSWORD_A, role=StaffRole.EMPLOYEE, is_active=False
        )

    def test_create_employee_is_exact_and_existing_uuid_or_username_conflicts(self) -> None:
        employee_id = uuid.uuid4()
        result = create_employee(
            actor_id=self.owner.id,
            session_generation=1,
            employee_id=employee_id,
            username="new-editor",
            password=PASSWORD_A,
            confirmation=PASSWORD_A,
        )
        created = User.objects.get(pk=employee_id)
        self.assertEqual((result.generation, result.is_active), (1, True))
        self.assertEqual((created.role, created.is_staff, created.is_superuser), ("EMPLOYEE", True, False))
        self.assertTrue(created.check_password(PASSWORD_A))
        self.assertEqual(AuditEvent.objects.filter(action=Action.STAFF_CREATED).count(), 1)
        for other_id, username in ((employee_id, "new-editor"), (uuid.uuid4(), "new-editor")):
            with self.assertRaises(StaffCommandError) as raised:
                create_employee(
                    actor_id=self.owner.id,
                    session_generation=1,
                    employee_id=other_id,
                    username=username,
                    password=PASSWORD_A,
                    confirmation=PASSWORD_A,
                )
            self.assertEqual(raised.exception.code, "CONFLICT")
        self.assertEqual(AuditEvent.objects.filter(action=Action.STAFF_CREATED).count(), 1)

    def test_create_validation_and_audit_fault_are_atomic(self) -> None:
        for username, password, confirmation in (
            (" nesadmin", PASSWORD_A, PASSWORD_A),
            ("nesadmin", PASSWORD_A, PASSWORD_A),
            ("valid-editor", "short", "short"),
            ("valid-editor", PASSWORD_A, PASSWORD_B),
        ):
            with self.assertRaises(StaffCommandError):
                create_employee(
                    actor_id=self.owner.id,
                    session_generation=1,
                    employee_id=uuid.uuid4(),
                    username=username,
                    password=password,
                    confirmation=confirmation,
                )
        target = uuid.uuid4()
        with patch("modules.accounts.staff.append_event", side_effect=RuntimeError("audit")):
            with self.assertRaises(RuntimeError):
                create_employee(
                    actor_id=self.owner.id,
                    session_generation=1,
                    employee_id=target,
                    username="rollback-editor",
                    password=PASSWORD_A,
                    confirmation=PASSWORD_A,
                )
        self.assertFalse(User.objects.filter(pk=target).exists())

    def test_password_change_bumps_generation_and_rejects_stale_same_and_owner(self) -> None:
        result = set_employee_password(
            actor_id=self.owner.id,
            session_generation=1,
            employee_id=self.employee.id,
            base_user_generation=1,
            password=PASSWORD_B,
            confirmation=PASSWORD_B,
        )
        self.assertEqual(result.generation, 2)
        changed = User.objects.get(pk=self.employee.id)
        self.assertTrue(changed.check_password(PASSWORD_B))
        self.assertEqual(AuditEvent.objects.filter(action=Action.AUTH_PASSWORD_CHANGED).count(), 1)
        for target, generation, password, code in (
            (self.employee.id, 1, PASSWORD_A, "STALE_STAFF"),
            (self.employee.id, 2, PASSWORD_B, "NO_CHANGE"),
            (self.owner.id, 1, PASSWORD_B, "FORBIDDEN"),
        ):
            with self.assertRaises(StaffCommandError) as raised:
                set_employee_password(
                    actor_id=self.owner.id,
                    session_generation=1,
                    employee_id=target,
                    base_user_generation=generation,
                    password=password,
                    confirmation=password,
                )
            self.assertEqual(raised.exception.code, code)

    def test_digest_exact_vectors_and_deactivate_removes_all_grants(self) -> None:
        page_b = Page.objects.create(name="B", kind=PageKind.ARTICLE, position=2)
        page_a = Page.objects.create(name="A", kind=PageKind.SERVICE_DETAIL, position=1)
        PageGrant.objects.create(staff=self.employee, page=page_b, groups=["text"])
        PageGrant.objects.create(staff=self.employee, page=page_a, groups=["text", "prices"])
        pairs = [(page_b.id, ("text",)), (page_a.id, ("text", "prices"))]
        empty_literal = (
            f'{{"domain":"estakada.staff-grants.v1","staff_id":"{self.employee.id}",'
            '"grants":[]}\n'
        )
        self.assertEqual(
            staff_grants_digest(self.employee.id, ()),
            hashlib.sha256(empty_literal.encode()).hexdigest(),
        )
        one_literal = (
            f'{{"domain":"estakada.staff-grants.v1","staff_id":"{self.employee.id}",'
            f'"grants":[{{"page_id":"{page_b.id}","groups":["text"]}}]}}\n'
        )
        self.assertEqual(
            staff_grants_digest(self.employee.id, ((page_b.id, ("text",)),)),
            hashlib.sha256(one_literal.encode()).hexdigest(),
        )
        ordered = sorted(pairs, key=lambda item: str(item[0]))
        literal = (
            f'{{"domain":"estakada.staff-grants.v1","staff_id":"{self.employee.id}",'
            f'"grants":[{{"page_id":"{ordered[0][0]}","groups":['
            + ",".join(f'"{value}"' for value in ordered[0][1])
            + f']}},{{"page_id":"{ordered[1][0]}","groups":['
            + ",".join(f'"{value}"' for value in ordered[1][1])
            + "]}]}\n"
        )
        digest = hashlib.sha256(literal.encode()).hexdigest()
        self.assertEqual(staff_grants_digest(self.employee.id, pairs), digest)
        result = deactivate_employee(
            actor_id=self.owner.id,
            session_generation=1,
            employee_id=self.employee.id,
            base_user_generation=1,
            base_grants_digest=digest,
        )
        self.assertEqual((result.generation, result.is_active, result.removed_grants), (2, False, 2))
        self.assertFalse(PageGrant.objects.filter(staff=self.employee).exists())
        event = AuditEvent.objects.get(action=Action.STAFF_DEACTIVATED)
        self.assertEqual(event.detail, {"generation": 2, "count": 2})

    def test_deactivate_stale_and_audit_fault_mutate_nothing(self) -> None:
        page = Page.objects.create(name="A", kind=PageKind.ARTICLE, position=1)
        grant = PageGrant.objects.create(staff=self.employee, page=page, groups=["text"])
        digest = staff_grants_digest(self.employee.id, [(page.id, ("text",))])
        with self.assertRaises(StaffLifecycleError) as raised:
            deactivate_employee(
                actor_id=self.owner.id,
                session_generation=1,
                employee_id=self.employee.id,
                base_user_generation=1,
                base_grants_digest="0" * 64,
            )
        self.assertEqual(raised.exception.code, "STALE_STAFF")
        with patch("modules.pages.staff.append_event", side_effect=RuntimeError("audit")):
            with self.assertRaises(RuntimeError):
                deactivate_employee(
                    actor_id=self.owner.id,
                    session_generation=1,
                    employee_id=self.employee.id,
                    base_user_generation=1,
                    base_grants_digest=digest,
                )
        self.assertTrue(PageGrant.objects.filter(pk=grant.pk).exists())
        self.assertTrue(User.objects.get(pk=self.employee.id).is_active)

    def test_reactivate_requires_inactive_zero_grants_and_restores_none(self) -> None:
        result = reactivate_employee(
            actor_id=self.owner.id,
            session_generation=1,
            employee_id=self.inactive.id,
            base_user_generation=1,
        )
        self.assertEqual((result.generation, result.is_active, result.removed_grants), (2, True, 0))
        self.assertFalse(PageGrant.objects.filter(staff=self.inactive).exists())
        self.assertEqual(AuditEvent.objects.filter(action=Action.STAFF_REACTIVATED).count(), 1)
        self.assertNotIn("modules.pages", inspect.getsource(accounts_api))

    def test_reactivate_rejects_corrupt_existing_grant(self) -> None:
        page = Page.objects.create(name="A", kind=PageKind.ARTICLE, position=1)
        PageGrant.objects.create(staff=self.inactive, page=page, groups=["text"])
        with self.assertRaises(StaffLifecycleError) as raised:
            reactivate_employee(
                actor_id=self.owner.id,
                session_generation=1,
                employee_id=self.inactive.id,
                base_user_generation=1,
            )
        self.assertEqual(raised.exception.code, "GRANT_CORRUPT")
        self.assertFalse(User.objects.get(pk=self.inactive.id).is_active)

    def test_deactivate_actual_lock_order_is_users_pages_grants_audit(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL FOR UPDATE semantics required.")
        pages = [
            Page.objects.create(name=f"P{index}", kind=PageKind.ARTICLE, position=index)
            for index in (2, 1)
        ]
        for page in pages:
            PageGrant.objects.create(staff=self.employee, page=page, groups=["text"])
        pairs = [(page.id, ("text",)) for page in pages]
        with CaptureQueriesContext(connection) as captured:
            deactivate_employee(
                actor_id=self.owner.id,
                session_generation=1,
                employee_id=self.employee.id,
                base_user_generation=1,
                base_grants_digest=staff_grants_digest(self.employee.id, pairs),
            )
        sql = [item["sql"].lower() for item in captured.captured_queries]

        def locked(fragment: str) -> int:
            return next(i for i, statement in enumerate(sql) if fragment in statement and "for update" in statement)

        users = locked('"accounts_user"')
        page_rows = locked('"pages_page"')
        grants = locked('"pages_pagegrant"')
        audit = next(i for i, statement in enumerate(sql) if 'insert into "audit_auditevent"' in statement)
        self.assertLess(users, page_rows)
        self.assertLess(page_rows, grants)
        self.assertLess(grants, audit)
        self.assertNotIn("modules.pages", inspect.getsource(accounts_api))


class StaffLifecycleConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="nesadmin", password=PASSWORD_A, role=StaffRole.OWNER
        )
        self.employee = User.objects.create_user(
            username="editor", password=PASSWORD_A, role=StaffRole.EMPLOYEE
        )

    def _concurrent_create(self, first_id, first_name, second_id, second_name):
        barrier = threading.Barrier(2)

        def run(args):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return create_employee(
                    actor_id=self.owner.id,
                    session_generation=1,
                    employee_id=args[0],
                    username=args[1],
                    password=PASSWORD_B,
                    confirmation=PASSWORD_B,
                )
            except StaffCommandError as exc:
                return exc
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, ((first_id, first_name), (second_id, second_name))))

    def test_concurrent_create_uuid_and_username_collisions_have_one_winner(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics required.")
        same_id = uuid.uuid4()
        different_id = uuid.uuid4()
        scenarios = (
            (same_id, "same", same_id, "same"),
            (different_id, "first", different_id, "second"),
            (uuid.uuid4(), "shared-two", uuid.uuid4(), "shared-two"),
        )
        for first_id, first_name, second_id, second_name in scenarios:
            outcomes = self._concurrent_create(first_id, first_name, second_id, second_name)
            self.assertEqual(sum(not isinstance(item, StaffCommandError) for item in outcomes), 1)
            self.assertEqual([item.code for item in outcomes if isinstance(item, StaffCommandError)], ["CONFLICT"])

    def test_two_password_changes_on_one_generation_have_one_winner(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics required.")
        barrier = threading.Barrier(2)

        def run(password: str):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return set_employee_password(
                    actor_id=self.owner.id,
                    session_generation=1,
                    employee_id=self.employee.id,
                    base_user_generation=1,
                    password=password,
                    confirmation=password,
                )
            except StaffCommandError as exc:
                return exc
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(run, (PASSWORD_B, "Unique!Employee-Gamma-2026")))
        self.assertEqual(sum(not isinstance(item, StaffCommandError) for item in outcomes), 1)
        self.assertEqual([item.code for item in outcomes if isinstance(item, StaffCommandError)], ["STALE_STAFF"])
        self.assertEqual(AuditEvent.objects.filter(action=Action.AUTH_PASSWORD_CHANGED).count(), 1)

    def test_reactivate_serializes_against_grant_and_deactivate(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics required.")
        inactive = User.objects.create_user(
            username="inactive", password=PASSWORD_A, role=StaffRole.EMPLOYEE, is_active=False
        )
        page = Page.objects.create(name="A", kind=PageKind.ARTICLE, position=1)
        barrier = threading.Barrier(2)

        def run_reactivate():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return reactivate_employee(
                    actor_id=self.owner.id,
                    session_generation=1,
                    employee_id=inactive.id,
                    base_user_generation=1,
                )
            except StaffLifecycleError as exc:
                return exc
            finally:
                close_old_connections()

        def run_grant():
            from ..grants import GrantCommandError, grant_state_hash, set_page_grant

            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return set_page_grant(
                    actor_id=self.owner.id,
                    session_generation=1,
                    staff_id=inactive.id,
                    page_id=page.id,
                    desired_groups=["text"],
                    base_user_generation=1,
                    base_grant_hash=grant_state_hash(inactive.id, page.id, ()),
                )
            except GrantCommandError as exc:
                return exc
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [pool.submit(run_reactivate), pool.submit(run_grant)]
            results = [future.result(timeout=10) for future in outcomes]
        self.assertEqual(sum(not isinstance(item, Exception) for item in results), 1)
        self.assertTrue(User.objects.get(pk=inactive.id).is_active)
        self.assertFalse(PageGrant.objects.filter(staff=inactive).exists())

        inactive_two = User.objects.create_user(
            username="inactive-two",
            password=PASSWORD_A,
            role=StaffRole.EMPLOYEE,
            is_active=False,
        )
        barrier_two = threading.Barrier(2)

        def run_reactivate_two():
            close_old_connections()
            try:
                barrier_two.wait(timeout=5)
                return reactivate_employee(
                    actor_id=self.owner.id,
                    session_generation=1,
                    employee_id=inactive_two.id,
                    base_user_generation=1,
                )
            except StaffLifecycleError as exc:
                return exc
            finally:
                close_old_connections()

        def run_deactivate_two():
            close_old_connections()
            try:
                barrier_two.wait(timeout=5)
                return deactivate_employee(
                    actor_id=self.owner.id,
                    session_generation=1,
                    employee_id=inactive_two.id,
                    base_user_generation=1,
                    base_grants_digest=staff_grants_digest(inactive_two.id, ()),
                )
            except StaffLifecycleError as exc:
                return exc
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run_reactivate_two), pool.submit(run_deactivate_two)]
            results = [future.result(timeout=10) for future in futures]
        self.assertEqual(sum(not isinstance(item, Exception) for item in results), 1)
        self.assertTrue(User.objects.get(pk=inactive_two.id).is_active)
        self.assertFalse(PageGrant.objects.filter(staff=inactive_two).exists())

    def _page_with_content_and_grant(self):
        page = Page.objects.create(name="A", kind=PageKind.ARTICLE, position=1)
        payload = _payload()
        content = PageContent.objects.create(
            page=page,
            generation=1,
            current_payload=payload,
            current_hash=canonical_payload_hash(payload),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )
        PageGrant.objects.create(staff=self.employee, page=page, groups=["text"])
        digest = staff_grants_digest(self.employee.id, ((page.id, ("text",)),))
        return page, content, digest

    def test_save_first_then_deactivate_allows_only_the_locked_save(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics required.")
        page, content, digest = self._page_with_content_and_grant()
        save_locked = threading.Event()
        release = threading.Event()
        original = accounts_api.lock_staff_session

        def gated(**kwargs):
            actor = original(**kwargs)
            save_locked.set()
            if not release.wait(timeout=5):
                raise RuntimeError("gate")
            return actor

        def save():
            close_old_connections()
            try:
                return save_page_content(
                    actor_id=self.employee.id,
                    session_generation=1,
                    page_id=page.id,
                    operation_id=uuid.uuid4(),
                    base_generation=1,
                    base_current_hash=content.current_hash,
                    changes={"text": {"intro": "<p>X</p>", "body": "<p>Y</p>"}},
                )
            finally:
                close_old_connections()

        def deactivate():
            close_old_connections()
            try:
                return deactivate_employee(
                    actor_id=self.owner.id,
                    session_generation=1,
                    employee_id=self.employee.id,
                    base_user_generation=1,
                    base_grants_digest=digest,
                )
            finally:
                close_old_connections()

        with patch("modules.pages.commands.lock_staff_session", side_effect=gated):
            with ThreadPoolExecutor(max_workers=2) as pool:
                save_future = pool.submit(save)
                self.assertTrue(save_locked.wait(timeout=5))
                deactivate_future = pool.submit(deactivate)
                release.set()
                self.assertEqual(save_future.result(timeout=10).generation, 2)
                self.assertEqual(deactivate_future.result(timeout=10).generation, 2)
        self.assertFalse(User.objects.get(pk=self.employee.id).is_active)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CONTENT_SAVED).count(), 1)

    def test_deactivate_first_makes_waiting_save_stale(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics required.")
        page, content, digest = self._page_with_content_and_grant()
        deactivate_locked = threading.Event()
        release = threading.Event()
        original = accounts_api.lock_owner_and_employee_state

        def gated(**kwargs):
            pair = original(**kwargs)
            deactivate_locked.set()
            if not release.wait(timeout=5):
                raise RuntimeError("gate")
            return pair

        def deactivate():
            close_old_connections()
            try:
                return deactivate_employee(
                    actor_id=self.owner.id,
                    session_generation=1,
                    employee_id=self.employee.id,
                    base_user_generation=1,
                    base_grants_digest=digest,
                )
            finally:
                close_old_connections()

        def save():
            close_old_connections()
            try:
                return save_page_content(
                    actor_id=self.employee.id,
                    session_generation=1,
                    page_id=page.id,
                    operation_id=uuid.uuid4(),
                    base_generation=1,
                    base_current_hash=content.current_hash,
                    changes={"text": {"intro": "<p>X</p>", "body": "<p>Y</p>"}},
                )
            except PageCommandError as exc:
                return exc
            finally:
                close_old_connections()

        with patch("modules.pages.staff.lock_owner_and_employee_state", side_effect=gated):
            with ThreadPoolExecutor(max_workers=2) as pool:
                deactivation = pool.submit(deactivate)
                self.assertTrue(deactivate_locked.wait(timeout=5))
                saving = pool.submit(save)
                release.set()
                deactivation.result(timeout=10)
                save_result = saving.result(timeout=10)
        self.assertIsInstance(save_result, PageCommandError)
        self.assertEqual(save_result.code, "STALE_SESSION")
        self.assertEqual(PageContent.objects.get(pk=content.pk).generation, 1)
