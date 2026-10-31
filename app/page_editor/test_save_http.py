"""Current-only save: real PG/session/child/engine; Client reader seam only."""
import json
from unittest.mock import patch
from uuid import uuid4

from django.db import DatabaseError
from django.test import TransactionTestCase, override_settings

from accounts.models import AuthSession
from accounts.services import set_grant
from audit.models import AuditEvent
from content.models import Route
from page_versions import engine as E, schema as S, services as V
from page_versions.models import PageRevision, PageContentState, OperationReceipt, OwnerDraft
from page_editor import test_check_http as H


@override_settings(ROOT_URLCONF="page_editor.test_check_http", MIDDLEWARE=H.TEST_MIDDLEWARE,
                   AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EditorSaveHttpTests(TransactionTestCase):
    # Reuse fixture helpers explicitly, without inheriting the20 check tests.
    setUp = H.EditorCheckHttpTests.setUp
    login = H.EditorCheckHttpTests.login
    payload = H.EditorCheckHttpTests.payload
    raw = H.EditorCheckHttpTests.raw
    post = H.EditorCheckHttpTests.post
    state = H.EditorCheckHttpTests.state
    assert_error = H.EditorCheckHttpTests.assert_error

    def current(self):
        return PageContentState.objects.get(page=self.page).current_revision_id

    def prepare(self, client=None, changes=None):
        client = client or self.owner_client
        value = self.payload(changes, baseRevisionId=str(self.current()))
        checked = self.post(client, value)
        self.assertEqual(checked.status_code, 200)
        result = checked.json()
        return {**value, "changes":result["normalisedChanges"],
                "operationId":str(uuid4()), "checkReceipt":result["checkReceipt"]}

    def save(self, value, client=None, *, raw=None, csrf=True, reader=None):
        original = self.url
        self.url = original.replace("/check/", "/save/")
        try:
            return self.post(client or self.owner_client, value, raw=raw, csrf=csrf, reader=reader)
        finally:
            self.url = original

    def test_owner_real_automatic_and_protected_fields_draft_route_unchanged(self):
        base = PageRevision.objects.get(pk=self.current())
        drafts = list(OwnerDraft.objects.values())
        routes = list(Route.objects.values())
        before = PageRevision.objects.count()
        value = self.prepare(changes={"main_text":"<p><b>NEW 😀</b></p>", "description":""})
        response = self.save(value)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(set(result), {"operation_id","action","result_id","result_code","gone","replay"})
        self.assertEqual(result["operation_id"], value["operationId"])
        self.assertEqual(result["action"], "commit_owner")
        self.assertFalse(result["replay"])
        self.assertFalse(result["gone"])
        row = PageRevision.objects.get(pk=result["result_id"])
        self.assertEqual(str(self.current()), str(row.pk))
        self.assertEqual(PageRevision.objects.count(), before + 1)
        self.assertEqual(row.kind, "automatic")
        self.assertEqual(row.author_id, self.owner.pk)
        self.assertEqual(str(row.source_revision_id), str(base.pk))
        self.assertEqual(row.payload["main_text"], "<p><strong>NEW 😀</strong></p>")
        self.assertEqual(row.payload["h1"], base.payload["h1"])
        self.assertNotIn("OWNER_DRAFT_PRIVATE_CANARY", row.payload["main_text"])
        self.assertEqual(list(OwnerDraft.objects.values()), drafts)
        self.assertEqual(list(Route.objects.values()), routes)
        receipt = OperationReceipt.objects.get(pk=value["operationId"])
        self.assertEqual(len(receipt.editor_request_fingerprint), 64)
        self.assertIn("no-store", response["Cache-Control"])

    def test_employee_real_text_save_keeps_owner_fields(self):
        base = PageRevision.objects.get(pk=self.current()).payload
        value = self.prepare(self.employee_client, {"main_text":"<p>EMPLOYEE</p>"})
        response = self.save(value, self.employee_client)
        self.assertEqual(response.status_code, 200)
        row = PageRevision.objects.get(pk=response.json()["result_id"])
        self.assertEqual(row.author_id, self.employee.pk)
        self.assertEqual(response.json()["action"], "commit_employee")
        self.assertEqual(row.payload, {**base, "main_text":"<p>EMPLOYEE</p>"})

    def test_price_granted_employee_real_decimal_save(self):
        column, row = str(uuid4()), str(uuid4())
        price = {"columns":[{"id":column,"label":"Цена"}],
                 "rows":[{"id":row,"label":"Работа","cells":[{"column_id":column,
                           "kind":"amount","amount":"12.50","from":True}]}]}
        value = self.prepare(self.price_client, {"price":price})
        response = self.save(value, self.price_client)
        self.assertEqual(response.status_code, 200)
        saved = PageRevision.objects.get(pk=response.json()["result_id"])
        self.assertEqual(saved.payload["price"]["rows"][0]["cells"][0]["amount"], "12.5")
        self.assertEqual(saved.payload["price"]["rows"][0]["id"], row)

    def test_exact_two_submit_replay_one_revision_receipt_audit(self):
        value = self.prepare()
        first = self.save(value)
        self.assertEqual(first.status_code, 200)
        before = self.state()
        audit = AuditEvent.objects.filter(code="VERSION_COMMIT_OWNER").count()
        second = self.save(value)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), {**first.json(), "replay":True})
        self.assertEqual(self.state(), before)
        self.assertEqual(AuditEvent.objects.filter(code="VERSION_COMMIT_OWNER").count(), audit)

    def test_json_order_and_whitespace_do_not_change_exact_replay(self):
        value = self.prepare(changes={"main_text":"<p>ORDER</p>","description":""})
        first = self.save(value)
        self.assertEqual(first.status_code, 200)
        reordered = dict(reversed(list(value.items())))
        reordered["changes"] = dict(reversed(list(value["changes"].items())))
        raw = json.dumps(reordered, ensure_ascii=False, indent=2).encode()
        before = self.state()
        second = self.save(value, raw=raw)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["result_id"], first.json()["result_id"])
        self.assertTrue(second.json()["replay"])
        self.assertEqual(self.state(), before)

    def test_changed_input_same_operation_conflicts(self):
        value = self.prepare()
        self.assertEqual(self.save(value).status_code, 200)
        before = self.state()
        for changed in ({**value,"changes":{"main_text":"<p>OTHER</p>"}},
                        {**value,"checkReceipt":value["checkReceipt"] + "x"},
                        {**value,"baseRevisionId":str(uuid4())}):
            self.assert_error(self.save(changed), 409, "EDITOR_OPERATION_CONFLICT")
        self.assertEqual(self.state(), before)

    def test_replay_after_later_save_does_not_rewind_current(self):
        first_value = self.prepare()
        first = self.save(first_value).json()
        later_value = self.prepare(changes={"main_text":"<p>LATER</p>"})
        later = self.save(later_value)
        self.assertEqual(later.status_code, 200)
        before = self.state()
        replay = self.save(first_value)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json()["result_id"], first["result_id"])
        self.assertTrue(replay.json()["replay"])
        self.assertEqual(self.state(), before)

    def test_pruned_result_remains_consumed_gone_not_reexecuted(self):
        value = self.prepare()
        first = self.save(value)
        self.assertEqual(first.status_code, 200)
        result_id = first.json()["result_id"]
        for index in range(12):
            V.commit_owner(actor=self.owner, page_id=self.page.pk, base_revision=self.current(),
                snapshot=S.snapshot_v1(self.page.kind, main_text="<p>Later %s</p>" % index),
                expected_generation=1, operation_id=uuid4())
        self.assertFalse(PageRevision.objects.filter(pk=result_id).exists())
        before = self.state()
        replay = self.save(value)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json()["result_id"], result_id)
        self.assertTrue(replay.json()["gone"])
        self.assertTrue(replay.json()["replay"])
        self.assertEqual(self.state(), before)

    def test_blank_legacy_commit_receipt_cannot_be_editor_replay(self):
        value = self.prepare(changes={"main_text":"<p>LEGACY</p>"})
        V.commit_owner(actor=self.owner, page_id=self.page.pk, base_revision=self.current(),
            snapshot=S.snapshot_v1(self.page.kind, main_text="<p>LEGACY</p>"),
            expected_generation=1, operation_id=value["operationId"])
        self.assertEqual(OperationReceipt.objects.get(pk=value["operationId"]).editor_request_fingerprint, "")
        before = self.state()
        self.assert_error(self.save(value), 409, "EDITOR_OPERATION_CONFLICT")
        self.assertEqual(self.state(), before)

    def test_new_operation_wrong_proof_or_unaccepted_normalization_no_commit(self):
        value = self.prepare(changes={"main_text":"<p><b>B</b></p>"})
        before = self.state()
        self.assert_error(self.save({**value,"checkReceipt":value["checkReceipt"] + "x"}),
                          409, "EDITOR_CHECK_RECEIPT_INVALID")
        self.assert_error(self.save({**value,"changes":{"main_text":"<p><b>B</b></p>"}}),
                          409, "EDITOR_NORMALIZATION_REQUIRED")
        self.assertEqual(self.state(), before)

    def test_replay_rechecks_actual_rights(self):
        value = self.prepare(self.employee_client)
        self.assertEqual(self.save(value, self.employee_client).status_code, 200)
        set_grant(actor=self.owner, employee=self.employee, page=self.page, revoke=True)
        before = self.state()
        self.assert_error(self.save(value, self.employee_client), 403, "EDITOR_FIELDS_FORBIDDEN")
        self.assertEqual(self.state(), before)

    def test_early_visitor_foreign_csrf_no_body_or_engine(self):
        value = self.prepare()
        for client, csrf, status in ((self.visitor,False,401),(self.other_client,True,403),
                                     (self.owner_client,False,403)):
            with patch("page_editor.views.commit_checked", side_effect=AssertionError("engine reached")):
                response = self.save(value, client, csrf=csrf,
                    reader=lambda *_: (_ for _ in ()).throw(AssertionError("body reached")))
            self.assertEqual(response.status_code, status)
            self.assertIn("no-store", response["Cache-Control"])

    def test_draft_stage_media_explicitly_unsupported(self):
        value = self.prepare()
        before = self.state()
        for changed in ({**value,"editingFrom":"owner-draft","draftBasis":{"id":str(uuid4()),"revision":1}},
                        {**value,"editingFrom":"restore-stage","stageId":str(uuid4())},
                        {**value,"changes":{"main_image":None}}):
            self.assert_error(self.save(changed), 409, "EDITOR_CAPABILITY_UNAVAILABLE")
        self.assertEqual(self.state(), before)

    def test_atomic_fault_after_real_ledger_audit_rolls_back_everything(self):
        value = self.prepare()
        before = self.state()
        audit_count = AuditEvent.objects.count()
        actual = E.finish
        def after_sql(*args, **kwargs):
            actual(*args, **kwargs)
            raise DatabaseError("synthetic post-ledger fault")
        with patch("page_versions.engine.finish", side_effect=after_sql):
            response = self.save(value)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.state(), before)
        self.assertEqual(AuditEvent.objects.count(), audit_count)
        self.assertEqual(self.save(value).status_code, 200)

    def test_logout_during_real_preflight_prevents_second_atomic_commit(self):
        value = self.prepare()
        before = self.state()
        actual = E.preflight
        session_key = self.owner_client.session.session_key
        def logout(payload):
            evidence = actual(payload)
            AuthSession.objects.filter(pk=session_key).delete()
            return evidence
        with patch("page_versions.engine.preflight", side_effect=logout):
            response = self.save(value)
        self.assert_error(response, 401, "EDITOR_SESSION_ENDED")
        self.assertEqual(self.state(), before)

    def test_revoke_during_real_preflight_prevents_commit(self):
        value = self.prepare(self.employee_client)
        before = self.state()
        actual = E.preflight
        def revoke(payload):
            evidence = actual(payload)
            set_grant(actor=self.owner, employee=self.employee, page=self.page, revoke=True)
            return evidence
        with patch("page_versions.engine.preflight", side_effect=revoke):
            response = self.save(value, self.employee_client)
        self.assert_error(response, 403, "EDITOR_FIELDS_FORBIDDEN")
        self.assertEqual(self.state(), before)
