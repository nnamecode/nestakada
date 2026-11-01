"""D07 actual PG interleavings: one heavy HTTP writer versus trusted domain API."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident
from unittest.mock import patch
from uuid import uuid4

from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings

from accounts.services import AUTH_LOCK
from audit.models import AuditEvent
from content.models import CONTENT_LOCK
from page_versions import engine as E, services as V, schema as S
from page_versions.models import OwnerDraft, OperationReceipt
from page_editor import test_check_http as H
from page_editor import test_draft_restore_http as D


@override_settings(ROOT_URLCONF="page_editor.test_check_http", MIDDLEWARE=H.TEST_MIDDLEWARE,
                   AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class DraftRestoreConcurrencyTests(TransactionTestCase):
    # Explicit helper aliases: do not inherit/rediscover either existing suite.
    setUp = H.EditorCheckHttpTests.setUp
    login = H.EditorCheckHttpTests.login
    payload = H.EditorCheckHttpTests.payload
    raw = H.EditorCheckHttpTests.raw
    post = H.EditorCheckHttpTests.post
    current = D.DraftRestoreEditorHttpTests.current
    draft = D.DraftRestoreEditorHttpTests.draft
    state = D.DraftRestoreEditorHttpTests.state
    selector = D.DraftRestoreEditorHttpTests.selector
    path = D.DraftRestoreEditorHttpTests.path
    send = D.DraftRestoreEditorHttpTests.send
    checked = D.DraftRestoreEditorHttpTests.checked
    remove_initial_draft = D.DraftRestoreEditorHttpTests.remove_initial_draft
    advance = D.DraftRestoreEditorHttpTests.advance
    seed_stage = D.DraftRestoreEditorHttpTests.seed_stage

    def interleave(self, action, value, selector, competitor, *, client=None):
        entered, release = Event(), Event()
        first_thread = {"id":None, "paused":False, "pid":None}
        real_preflight = E.preflight
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            main_pid = cursor.fetchone()[0]
            cursor.execute("SET lock_timeout = '3000ms'")

        def gated_preflight(payload):
            evidence = real_preflight(payload)
            if get_ident() == first_thread["id"] and not first_thread["paused"]:
                first_thread["paused"] = True
                if connection.in_atomic_block:
                    raise AssertionError("HTTP_PREFLIGHT_IN_TRANSACTION")
                entered.set()
                if not release.wait(15):
                    raise AssertionError("HTTP_PREFLIGHT_RELEASE_TIMEOUT")
            return evidence

        def first_http():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '3000ms'")
                    cursor.execute("SELECT pg_backend_pid()")
                    first_thread["pid"] = cursor.fetchone()[0]
                first_thread["id"] = get_ident()
                return self.send(action, value, selector=selector, client=client)
            finally:
                close_old_connections()

        try:
            with patch("page_versions.engine.preflight", side_effect=gated_preflight):
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(first_http)
                    try:
                        self.assertTrue(entered.wait(30), "HTTP_PREFLIGHT_NOT_REACHED")
                        self.assertNotEqual(first_thread["pid"], main_pid)
                        # A distinct live PG connection actually obtains domain
                        # locks while the HTTP request is paused outside atomic.
                        with connection.cursor() as cursor:
                            for key in (CONTENT_LOCK, AUTH_LOCK):
                                cursor.execute("SELECT pg_try_advisory_lock(%s)", [key])
                                acquired = cursor.fetchone()[0]
                                try:
                                    self.assertTrue(acquired, "HTTP_RETAINED_DOMAIN_LOCK")
                                finally:
                                    if acquired:
                                        cursor.execute("SELECT pg_advisory_unlock(%s)", [key])
                        winner = competitor()
                        after_winner = self.state()
                        audit_after_winner = list(AuditEvent.objects.order_by("id").values())
                    finally:
                        release.set()
                    response = future.result(timeout=20)
            self.assertEqual(response.status_code, 409)
            self.assertNotIn("result_id", response.json())
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(self.state(), after_winner)
            self.assertEqual(list(AuditEvent.objects.order_by("id").values()), audit_after_winner)
            self.assertFalse(OperationReceipt.objects.filter(pk=value["operationId"]).exists())
            return winner
        finally:
            release.set()
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '0'")

    def test_http_draft_create_loses_to_actual_second_connection_create(self):
        self.remove_initial_draft()
        value, selector, _ = self.checked({"main_text":"<p>HTTP CREATE</p>"})
        base = self.current()
        def competitor():
            return V.save_owner_draft(actor=self.owner,page_id=self.page.pk,base_revision=base,
                snapshot=S.snapshot_v1(self.page.kind,main_text="WINNER CREATE"),
                expected_generation=1,operation_id=uuid4())
        winner = self.interleave("draft",{**value,"rebase":False},selector,competitor)
        draft = self.draft()
        self.assertEqual(str(draft.pk),winner["result_id"])
        self.assertEqual(draft.revision,1)
        self.assertEqual(draft.payload["main_text"],"WINNER CREATE")
        self.assertEqual(self.current(),base)

    def test_http_draft_update_loses_to_actual_second_connection_update(self):
        draft = self.draft()
        value, selector, _ = self.checked({"main_text":"<p>HTTP UPDATE</p>"},draft=draft)
        def competitor():
            return V.save_owner_draft(actor=self.owner,page_id=self.page.pk,base_revision=draft.base_revision_id,
                snapshot=S.snapshot_v1(self.page.kind,main_text="WINNER UPDATE"),draft_revision=draft.revision,
                expected_generation=1,operation_id=uuid4())
        self.interleave("draft",{**value,"rebase":False},selector,competitor)
        current_draft = self.draft()
        self.assertEqual(current_draft.revision,draft.revision+1)
        self.assertEqual(current_draft.payload["main_text"],"WINNER UPDATE")

    def test_http_edited_draft_publish_loses_to_actual_cancel(self):
        draft = self.draft()
        value, selector, _ = self.checked({"main_text":"<p>HTTP PUBLISH</p>"},draft=draft)
        base = self.current()
        def competitor():
            return V.cancel_owner_draft(actor=self.owner,page_id=self.page.pk,draft_id=draft.pk,
                draft_revision=draft.revision,expected_generation=1,operation_id=uuid4())
        self.interleave("save",value,selector,competitor)
        self.assertFalse(OwnerDraft.objects.filter(pk=draft.pk).exists())
        self.assertEqual(self.current(),base)

    def test_http_rebase_loses_to_actual_draft_revision_update(self):
        draft = self.draft()
        target = self.advance()
        value, selector, _ = self.checked({"main_text":"<p>HTTP REBASE</p>"},draft=draft,target=target)
        def competitor():
            return V.save_owner_draft(actor=self.owner,page_id=self.page.pk,base_revision=draft.base_revision_id,
                snapshot=S.snapshot_v1(self.page.kind,main_text="WINNER ON OLD BASIS"),draft_revision=draft.revision,
                expected_generation=1,operation_id=uuid4())
        self.interleave("draft",{**value,"rebase":True},selector,competitor)
        current_draft = self.draft()
        self.assertEqual(current_draft.revision,draft.revision+1)
        self.assertEqual(current_draft.base_revision_id,draft.base_revision_id)
        self.assertEqual(str(self.current()),str(target))

    def test_http_stage_publish_loses_to_actual_employee_current_commit(self):
        stage = self.seed_stage()
        value, selector, _ = self.checked({"intro_text":"","main_text":"<p>HTTP STAGE</p>"},
                                          stage=stage,client=self.employee_client)
        base = self.current()
        def competitor():
            return V.commit_employee(actor=self.employee,page_id=self.page.pk,base_revision=base,
                patch=S.TextPricePatch(main_text="WINNER CURRENT"),expected_generation=1,operation_id=uuid4())
        winner = self.interleave("save",value,selector,competitor,client=self.employee_client)
        self.assertEqual(str(self.current()),winner["result_id"])
        stage.refresh_from_db()
        self.assertEqual(stage.status,"invalidated")
