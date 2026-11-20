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
from modules.accounts.api import StaffRole, User
from modules.audit.models import Action, AuditEvent

from ..commands import PageCommandError, save_page_content
from ..content import canonical_payload_hash
from ..grants import (
    GrantCommandError,
    grant_state_hash,
    revoke_page_grant,
    set_page_grant,
)
from ..models import Page, PageContent, PageGrant, PageKind


def _payload(*, intro: str = "<p>Intro</p>") -> dict:
    return {
        "schema": "estakada.page-content",
        "schema_version": 1,
        "kind": "service_detail",
        "fields": {
            "seo": {"title": "Title", "description": "", "allow_index": True},
            "heading": {"h1": "Heading"},
            "intro": intro,
            "body": "<p>Body</p>",
            "price_rows": {"columns": [], "rows": []},
            "media": {"hero": None, "body": [], "works": []},
        },
    }


class PageGrantCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner = User.objects.create_user(
            username="nesadmin", password=None, role=StaffRole.OWNER
        )
        cls.employee = User.objects.create_user(
            username="editor", password=None, role=StaffRole.EMPLOYEE
        )
        cls.page = Page.objects.create(
            name="Service", kind=PageKind.SERVICE_DETAIL, position=1
        )

    def _absent_hash(self) -> str:
        return grant_state_hash(self.employee.id, self.page.id, ())

    def test_hash_uses_exact_present_and_absent_envelopes(self) -> None:
        absent_bytes = (
            f'{{"domain":"estakada.page-grant.v1","staff_id":"{self.employee.id}",'
            f'"page_id":"{self.page.id}","state":"ABSENT","groups":[]}}\n'
        ).encode("ascii")
        present_bytes = (
            f'{{"domain":"estakada.page-grant.v1","staff_id":"{self.employee.id}",'
            f'"page_id":"{self.page.id}","state":"PRESENT","groups":["text","prices"]}}\n'
        ).encode("ascii")
        self.assertEqual(grant_state_hash(self.employee.id, self.page.id, ()), hashlib.sha256(absent_bytes).hexdigest())
        self.assertEqual(
            grant_state_hash(self.employee.id, self.page.id, ("text", "prices")),
            hashlib.sha256(present_bytes).hexdigest(),
        )
        self.assertNotEqual(hashlib.sha256(absent_bytes).digest(), hashlib.sha256(present_bytes).digest())

    def test_set_change_and_revoke_are_atomic_and_revoke_sessions(self) -> None:
        result = set_page_grant(
            actor_id=self.owner.id,
            session_generation=1,
            staff_id=self.employee.id,
            page_id=self.page.id,
            desired_groups=["text"],
            base_user_generation=1,
            base_grant_hash=self._absent_hash(),
        )
        self.assertEqual((result.user_generation, result.groups), (2, ("text",)))
        self.assertEqual(PageGrant.objects.get(staff=self.employee, page=self.page).groups, ["text"])
        self.assertEqual(User.objects.get(pk=self.employee.id).generation, 2)
        event = AuditEvent.objects.get(action=Action.PAGE_GRANT_SET)
        self.assertEqual(event.target_uuid, self.page.id)
        self.assertEqual(event.secondary_uuid, self.employee.id)
        self.assertEqual(event.detail, {"generation": 2, "groups": ["text"]})

        changed = set_page_grant(
            actor_id=self.owner.id,
            session_generation=1,
            staff_id=self.employee.id,
            page_id=self.page.id,
            desired_groups=["text", "prices"],
            base_user_generation=2,
            base_grant_hash=result.grant_hash,
        )
        self.assertEqual(changed.user_generation, 3)
        self.assertEqual(PageGrant.objects.get(staff=self.employee, page=self.page).groups, ["text", "prices"])

        revoked = revoke_page_grant(
            actor_id=self.owner.id,
            session_generation=1,
            staff_id=self.employee.id,
            page_id=self.page.id,
            base_user_generation=3,
            base_grant_hash=changed.grant_hash,
        )
        self.assertEqual((revoked.user_generation, revoked.groups), (4, ()))
        self.assertFalse(PageGrant.objects.filter(staff=self.employee, page=self.page).exists())
        self.assertEqual(User.objects.get(pk=self.employee.id).generation, 4)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_GRANT_SET).count(), 2)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_GRANT_REVOKED).count(), 1)

    def test_stale_retry_is_409_semantics_without_second_mutation(self) -> None:
        basis = self._absent_hash()
        set_page_grant(
            actor_id=self.owner.id,
            session_generation=1,
            staff_id=self.employee.id,
            page_id=self.page.id,
            desired_groups=["text"],
            base_user_generation=1,
            base_grant_hash=basis,
        )
        with self.assertRaises(GrantCommandError) as raised:
            set_page_grant(
                actor_id=self.owner.id,
                session_generation=1,
                staff_id=self.employee.id,
                page_id=self.page.id,
                desired_groups=["text"],
                base_user_generation=1,
                base_grant_hash=basis,
            )
        self.assertEqual(raised.exception.code, "STALE_GRANT")
        self.assertEqual(User.objects.get(pk=self.employee.id).generation, 2)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_GRANT_SET).count(), 1)

    def test_fresh_no_change_is_rejected_without_generation_or_audit(self) -> None:
        grant = PageGrant.objects.create(staff=self.employee, page=self.page, groups=["text"])
        basis = grant_state_hash(self.employee.id, self.page.id, ("text",))
        with self.assertRaises(GrantCommandError) as raised:
            set_page_grant(
                actor_id=self.owner.id,
                session_generation=1,
                staff_id=self.employee.id,
                page_id=self.page.id,
                desired_groups=["text"],
                base_user_generation=1,
                base_grant_hash=basis,
            )
        self.assertEqual(raised.exception.code, "NO_CHANGE")
        self.assertEqual(PageGrant.objects.get(pk=grant.pk).groups, ["text"])
        self.assertEqual(User.objects.get(pk=self.employee.id).generation, 1)
        self.assertFalse(AuditEvent.objects.exists())

    def test_role_kind_group_and_no_change_fail_closed(self) -> None:
        invalid_page = Page.objects.create(
            name="Read only", kind=PageKind.LEGACY_EMPTY_MAIN, position=2
        )
        cases = (
            (self.employee.id, self.page, ["text"], "FORBIDDEN"),
            (self.owner.id, invalid_page, ["text"], "INVALID_GROUPS"),
            (self.owner.id, self.page, ["prices", "text"], "INVALID_GROUPS"),
        )
        for actor_id, page, groups, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(GrantCommandError) as raised:
                    set_page_grant(
                        actor_id=actor_id,
                        session_generation=1,
                        staff_id=self.employee.id,
                        page_id=page.id,
                        desired_groups=groups,
                        base_user_generation=1,
                        base_grant_hash=grant_state_hash(self.employee.id, page.id, ()),
                    )
                self.assertEqual(raised.exception.code, code)
        self.assertEqual(PageGrant.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_audit_fault_rolls_back_grant_and_generation(self) -> None:
        with patch("modules.pages.grants.append_event", side_effect=RuntimeError("audit-fault")):
            with self.assertRaises(RuntimeError):
                set_page_grant(
                    actor_id=self.owner.id,
                    session_generation=1,
                    staff_id=self.employee.id,
                    page_id=self.page.id,
                    desired_groups=["text"],
                    base_user_generation=1,
                    base_grant_hash=self._absent_hash(),
                )
        self.assertFalse(PageGrant.objects.exists())
        self.assertEqual(User.objects.get(pk=self.employee.id).generation, 1)
        self.assertFalse(AuditEvent.objects.exists())

    def test_actual_query_order_is_users_page_grant_then_audit_and_dag_has_no_reverse_edge(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL FOR UPDATE semantics required.")
        with CaptureQueriesContext(connection) as captured:
            set_page_grant(
                actor_id=self.owner.id,
                session_generation=1,
                staff_id=self.employee.id,
                page_id=self.page.id,
                desired_groups=["text"],
                base_user_generation=1,
                base_grant_hash=self._absent_hash(),
            )
        statements = [item["sql"].lower() for item in captured.captured_queries]

        def first_locked(fragment: str) -> int:
            return next(
                index
                for index, sql in enumerate(statements)
                if fragment in sql and "select" in sql and "for update" in sql
            )

        user_lock = first_locked('"accounts_user"')
        page_lock = first_locked('"pages_page"')
        grant_lock = first_locked('"pages_pagegrant"')
        audit_write = next(
            index
            for index, sql in enumerate(statements)
            if '"audit_auditevent"' in sql and "insert" in sql
        )
        self.assertIn('order by "accounts_user"."id" asc', statements[user_lock])
        self.assertLess(user_lock, page_lock)
        self.assertLess(page_lock, grant_lock)
        self.assertLess(grant_lock, audit_write)
        self.assertNotIn("modules.pages", inspect.getsource(accounts_api))


class PageGrantConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="nesadmin", password=None, role=StaffRole.OWNER)
        self.employee = User.objects.create_user(username="editor", password=None, role=StaffRole.EMPLOYEE)
        self.page = Page.objects.create(name="Service", kind=PageKind.SERVICE_DETAIL, position=1)
        initial = _payload()
        self.content = PageContent.objects.create(
            page=self.page,
            generation=1,
            current_payload=initial,
            current_hash=canonical_payload_hash(initial),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )
        PageGrant.objects.create(staff=self.employee, page=self.page, groups=["text"])

    def test_two_commands_on_one_basis_have_one_winner_and_one_stale(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics required.")
        basis_hash = grant_state_hash(self.employee.id, self.page.id, ("text",))
        barrier = threading.Barrier(2)

        def run(groups: list[str]):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return set_page_grant(
                    actor_id=self.owner.id,
                    session_generation=1,
                    staff_id=self.employee.id,
                    page_id=self.page.id,
                    desired_groups=groups,
                    base_user_generation=1,
                    base_grant_hash=basis_hash,
                )
            except GrantCommandError as exc:
                return exc
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(run, (["prices"], ["text", "prices"])))
        successes = [item for item in outcomes if not isinstance(item, GrantCommandError)]
        failures = [item for item in outcomes if isinstance(item, GrantCommandError)]
        self.assertEqual(len(successes), 1)
        self.assertEqual([item.code for item in failures], ["STALE_GRANT"])
        self.assertEqual(User.objects.get(pk=self.employee.id).generation, 2)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_GRANT_SET).count(), 1)

    def _save(self):
        return save_page_content(
            actor_id=self.employee.id,
            session_generation=1,
            page_id=self.page.id,
            operation_id=uuid.uuid4(),
            base_generation=1,
            base_current_hash=self.content.current_hash,
            changes={"text": {"intro": "<p>Changed</p>", "body": "<p>Body</p>"}},
        )

    def _revoke(self):
        return revoke_page_grant(
            actor_id=self.owner.id,
            session_generation=1,
            staff_id=self.employee.id,
            page_id=self.page.id,
            base_user_generation=1,
            base_grant_hash=grant_state_hash(self.employee.id, self.page.id, ("text",)),
        )

    def test_save_first_then_revoke_allows_one_authorized_save(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics required.")
        save_locked = threading.Event()
        release_save = threading.Event()
        revoke_started = threading.Event()
        original = accounts_api.lock_staff_session

        def gated_save_lock(**kwargs):
            actor = original(**kwargs)
            save_locked.set()
            if not release_save.wait(timeout=5):
                raise RuntimeError("save gate timeout")
            return actor

        def run_revoke():
            close_old_connections()
            try:
                revoke_started.set()
                return self._revoke()
            finally:
                close_old_connections()

        def run_save():
            close_old_connections()
            try:
                return self._save()
            finally:
                close_old_connections()

        with patch("modules.pages.commands.lock_staff_session", side_effect=gated_save_lock):
            with ThreadPoolExecutor(max_workers=2) as pool:
                save_future = pool.submit(run_save)
                self.assertTrue(save_locked.wait(timeout=5))
                revoke_future = pool.submit(run_revoke)
                self.assertTrue(revoke_started.wait(timeout=5))
                release_save.set()
                save_result = save_future.result(timeout=10)
                revoke_result = revoke_future.result(timeout=10)
        self.assertEqual(save_result.generation, 2)
        self.assertEqual(revoke_result.user_generation, 2)
        self.assertFalse(PageGrant.objects.filter(staff=self.employee, page=self.page).exists())
        self.assertEqual(PageContent.objects.get(page=self.page).generation, 2)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CONTENT_SAVED).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_GRANT_REVOKED).count(), 1)

    def test_revoke_first_makes_waiting_save_stale_session(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics required.")
        revoke_locked = threading.Event()
        release_revoke = threading.Event()
        save_started = threading.Event()
        original = accounts_api.lock_owner_and_employee

        def gated_grant_lock(**kwargs):
            actors = original(**kwargs)
            revoke_locked.set()
            if not release_revoke.wait(timeout=5):
                raise RuntimeError("revoke gate timeout")
            return actors

        def run_save():
            close_old_connections()
            try:
                save_started.set()
                return self._save()
            except PageCommandError as exc:
                return exc
            finally:
                close_old_connections()

        def run_revoke():
            close_old_connections()
            try:
                return self._revoke()
            finally:
                close_old_connections()

        with patch("modules.pages.grants.lock_owner_and_employee", side_effect=gated_grant_lock):
            with ThreadPoolExecutor(max_workers=2) as pool:
                revoke_future = pool.submit(run_revoke)
                self.assertTrue(revoke_locked.wait(timeout=5))
                save_future = pool.submit(run_save)
                self.assertTrue(save_started.wait(timeout=5))
                release_revoke.set()
                revoke_result = revoke_future.result(timeout=10)
                save_result = save_future.result(timeout=10)
        self.assertEqual(revoke_result.user_generation, 2)
        self.assertIsInstance(save_result, PageCommandError)
        self.assertEqual(save_result.code, "STALE_SESSION")
        self.assertFalse(PageGrant.objects.filter(staff=self.employee, page=self.page).exists())
        self.assertEqual(PageContent.objects.get(page=self.page).generation, 1)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CONTENT_SAVED).count(), 0)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_GRANT_REVOKED).count(), 1)
