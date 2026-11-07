"""D07: closed HTTP expectations, real PG/session/CSRF/child/DEV05 fixture APIs."""
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from django.db import DatabaseError
from django.contrib.sessions.models import Session
from django.test import TransactionTestCase, override_settings

from accounts.services import set_grant
from audit.models import AuditEvent
from page_versions import engine as E, services as V, schema as S
from page_versions.models import (PageRevision, PageContentState, OwnerDraft,
                                  RestoreStage, VersionBasePin, OperationReceipt)
from page_editor import test_check_http as H
from page_editor.input_policy import fingerprint


@override_settings(ROOT_URLCONF="page_editor.test_check_http", MIDDLEWARE=H.TEST_MIDDLEWARE,
                   AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class DraftRestoreEditorHttpTests(TransactionTestCase):
    setUp = H.EditorCheckHttpTests.setUp
    login = H.EditorCheckHttpTests.login
    payload = H.EditorCheckHttpTests.payload
    raw = H.EditorCheckHttpTests.raw
    post = H.EditorCheckHttpTests.post

    def current(self):
        return PageContentState.objects.get(page=self.page).current_revision_id

    def draft(self):
        return OwnerDraft.objects.get(page=self.page)

    def state(self):
        return {**H.EditorCheckHttpTests.state(self),
                "pins":list(VersionBasePin.objects.order_by("id").values())}

    def selector(self, draft=None, stage=None, target=None):
        if draft is not None:
            value = {"source":"owner-draft", "draftId":str(draft.pk), "draftRevision":draft.revision}
            if target is not None:
                value.update(rebase="1", targetCurrentId=str(target))
            return value
        if stage is not None:
            return {"source":"restore-stage", "stageId":str(stage.pk)}
        return {}

    def path(self, action, selector=None):
        prefix = "/manage/pages/%s/edit/" % self.page.pk
        return prefix + action + ("/" if action else "") + ("?" + urlencode(selector) if selector else "")

    def send(self, action, value, *, selector=None, client=None):
        original = self.url
        self.url = self.path(action, selector)
        try:
            return self.post(client or self.owner_client, value)
        finally:
            self.url = original

    def checked(self, changes=None, *, draft=None, stage=None, target=None, client=None):
        selector = self.selector(draft=draft, stage=stage, target=target)
        value = self.payload(changes, baseRevisionId=str(self.current()))
        if draft is not None:
            value.update(editingFrom="owner-draft", draftBasis={"id":str(draft.pk), "revision":draft.revision},
                         baseRevisionId=str(draft.base_revision_id))
        if stage is not None:
            value.update(editingFrom="restore-stage", stageId=str(stage.pk),
                         baseRevisionId=str(stage.base_revision_id))
        response = self.send("check", value, selector=selector, client=client)
        self.assertEqual(response.status_code, 200)
        checked = response.json()
        return {**value, "changes":checked["normalisedChanges"],
                "operationId":str(uuid4()), "checkReceipt":checked["checkReceipt"]}, selector, checked

    def reject(self, response, status=409):
        self.assertEqual(response.status_code, status)
        self.assertNotIn("result_id", response.json())
        self.assertNotIn("checkReceipt", response.json())
        self.assertIn("no-store", response["Cache-Control"])

    def remove_initial_draft(self):
        draft = self.draft()
        V.cancel_owner_draft(actor=self.owner, page_id=self.page.pk, draft_id=draft.pk,
            draft_revision=draft.revision, expected_generation=1, operation_id=uuid4())

    def advance(self, text="CURRENT ADVANCED"):
        return V.commit_owner(actor=self.owner, page_id=self.page.pk, base_revision=self.current(),
            snapshot=S.snapshot_v1(self.page.kind, main_text="<p>" + text + "</p>"),
            expected_generation=1, operation_id=uuid4())["result_id"]

    def seed_stage(self):
        source = self.current()
        self.advance()
        prepared = V.prepare_restore(actor=self.employee, page_id=self.page.pk,
            version_id=source, expected_generation=1)
        result = V.stage_restore(actor=self.employee, page_id=self.page.pk,
            preparation=prepared["preparation"], confirm_input_replacement=True,
            expected_generation=1, operation_id=uuid4())
        return RestoreStage.objects.get(pk=result["result_id"])

    def test_current_source_legacy_shape_and_selected_draft_privacy(self):
        response = self.send("check", self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"protocol","inputFingerprint","normalisedChanges",
                         "normalisationChanged","fieldWarnings","checkReceipt","baseRevisionId"})
        draft = self.draft()
        selected = self.owner_client.get(self.path("state", self.selector(draft=draft)))
        self.assertEqual(selected.status_code, 200)
        self.assertTrue(selected.json()["canReadSource"])
        self.assertEqual(selected.json()["sourceContext"]["draftBasis"], {"id":str(draft.pk),"revision":draft.revision})
        for client, status in ((self.employee_client,403),(self.other_client,403),(self.visitor,401)):
            response = client.get(self.path("state", self.selector(draft=draft)))
            self.assertEqual(response.status_code, status)
            self.assertNotIn(b"OWNER_DRAFT_PRIVATE_CANARY", response.content)
        for query in ("source=current", "source=owner-draft&source=owner-draft",
                      "source=restore-stage&stageId=" + str(uuid4()) + "&extra=1",
                      "x=" + "a" * 255):
            self.assertEqual(self.owner_client.get(self.path("state") + "?" + query).status_code,400)

    def test_current_owner_save_uses_simple_commit_and_preserves_private_draft(self):
        draft = self.draft()
        base = self.current()
        value, selector, _ = self.checked(
            {"main_text":"<p>SIMPLE CURRENT SAVE</p>"})
        receipt_count = OperationReceipt.objects.count()
        response = self.send("save", value, selector=selector)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        row = PageRevision.objects.get(pk=result["result_id"])
        self.assertEqual(row.source_revision_id, base)
        self.assertEqual(row.payload["main_text"], "<p>SIMPLE CURRENT SAVE</p>")
        self.assertEqual(self.current(), row.pk)
        self.assertFalse(OperationReceipt.objects.filter(
            pk=value["operationId"]).exists())
        self.assertEqual(OperationReceipt.objects.count(), receipt_count)
        self.assertTrue(OwnerDraft.objects.filter(pk=draft.pk).exists())
        self.assertTrue(VersionBasePin.objects.filter(
            holder_kind="owner_draft", holder_id=draft.pk,
            revision_id=base).exists())

    def test_new_owner_draft_creates_no_automatic_or_current_mutation(self):
        self.remove_initial_draft()
        value, selector, _ = self.checked({"main_text":"<p>NEW DRAFT</p>"})
        current, count = self.current(), PageRevision.objects.count()
        response = self.send("draft", {**value,"rebase":False}, selector=selector)
        self.assertEqual(response.status_code, 200)
        draft = self.draft()
        self.assertEqual(draft.payload["main_text"], "<p>NEW DRAFT</p>")
        self.assertEqual(draft.revision, 1)
        self.assertEqual(response.json()["draftBasis"], {"id":str(draft.pk),"revision":1})
        self.assertEqual(self.current(), current)
        self.assertEqual(PageRevision.objects.count(), count)
        self.assertFalse(VersionBasePin.objects.filter(
            holder_kind="owner_draft", holder_id=draft.pk).exists())
        self.assertFalse(OperationReceipt.objects.filter(
            pk=value["operationId"]).exists())

    def test_owner_draft_update_then_repeat_conflicts_without_second_increment(self):
        draft = self.draft()
        value, selector, _ = self.checked({"main_text":"<p>UPDATED DRAFT</p>"}, draft=draft)
        count, current = PageRevision.objects.count(), self.current()
        first = self.send("draft", {**value,"rebase":False}, selector=selector)
        self.assertEqual(first.status_code, 200)
        changed = self.draft()
        self.assertEqual(changed.pk, draft.pk)
        self.assertEqual(changed.revision, draft.revision + 1)
        before = self.state()
        replay = self.send("draft", {**value,"rebase":False}, selector=selector)
        self.reject(replay)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.current(), current)
        self.assertEqual(PageRevision.objects.count(), count)
        self.assertFalse(OperationReceipt.objects.filter(
            pk=value["operationId"]).exists())
        self.assertFalse(VersionBasePin.objects.filter(
            holder_kind="owner_draft", holder_id=draft.pk).exists())

    def test_legacy_save_draft_receipt_replays_through_simple_routing(self):
        draft = self.draft()
        value, selector, _ = self.checked(
            {"main_text":"<p>LEGACY SAVE DRAFT</p>"}, draft=draft)
        request_value = {**value, "rebase":False}
        payload = {**draft.payload, **value["changes"]}
        original = E.save_owner_draft(
            actor=self.owner, page_id=self.page.pk,
            base_revision=draft.base_revision_id,
            snapshot=S.Snapshot.trusted(payload, self.page.kind),
            expected_generation=1, operation_id=value["operationId"],
            draft_revision=draft.revision, draft_id=draft.pk,
            expected_draft_hash=S.digest(draft.payload),
            expected_draft_base=draft.base_revision_id,
            editor_request_fingerprint=fingerprint({
                "input":request_value,
                "source":{
                    "editingFrom":"owner-draft",
                    "draftBasis":{"id":str(draft.pk), "revision":draft.revision},
                    "stageId":None, "rebase":False, "targetCurrentId":None,
                },
            }),
            editor_session_key=self.owner_client.session.session_key)
        before = self.state()
        audit = list(AuditEvent.objects.order_by("id").values())
        response = self.send("draft", request_value, selector=selector)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["replay"])
        self.assertEqual(response.json()["result_id"], original["result_id"])
        self.assertEqual(response.json()["draftBasis"], {
            "id":original["result_id"], "revision":draft.revision + 1})
        self.assertEqual(response.json()["baseRevisionId"],
                         str(draft.base_revision_id))
        self.assertEqual(self.state(), before)
        self.assertEqual(list(AuditEvent.objects.order_by("id").values()), audit)

    def test_legacy_rebase_draft_receipt_replays_through_simple_routing(self):
        draft = self.draft()
        target = self.advance("LEGACY REBASE TARGET")
        value, selector, _ = self.checked(
            {"main_text":"<p>LEGACY REBASE DRAFT</p>"},
            draft=draft, target=target)
        request_value = {**value, "rebase":True}
        payload = {**draft.payload, **value["changes"]}
        original = E.save_owner_draft(
            actor=self.owner, page_id=self.page.pk,
            base_revision=target,
            snapshot=S.Snapshot.trusted(payload, self.page.kind),
            expected_generation=1, operation_id=value["operationId"],
            draft_revision=draft.revision, rebase=True, draft_id=draft.pk,
            expected_draft_hash=S.digest(draft.payload),
            expected_draft_base=draft.base_revision_id,
            editor_request_fingerprint=fingerprint({
                "input":request_value,
                "source":{
                    "editingFrom":"owner-draft",
                    "draftBasis":{"id":str(draft.pk), "revision":draft.revision},
                    "stageId":None, "rebase":True, "targetCurrentId":str(target),
                },
            }),
            editor_session_key=self.owner_client.session.session_key)
        before = self.state()
        audit = list(AuditEvent.objects.order_by("id").values())
        response = self.send("draft", request_value, selector=selector)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["replay"])
        self.assertEqual(response.json()["result_id"], original["result_id"])
        self.assertEqual(response.json()["draftBasis"], {
            "id":original["result_id"], "revision":draft.revision + 1})
        self.assertEqual(response.json()["baseRevisionId"], str(target))
        self.assertEqual(self.state(), before)
        self.assertEqual(list(AuditEvent.objects.order_by("id").values()), audit)

    def test_edited_draft_publish_atomic_consume_and_repeat_conflicts(self):
        draft = self.draft()
        value, selector, _ = self.checked({"main_text":"<p>EDITED BEFORE PUBLISH</p>"}, draft=draft)
        count = PageRevision.objects.count()
        response = self.send("save", value, selector=selector)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        row = PageRevision.objects.get(pk=result["result_id"])
        self.assertEqual(row.payload["main_text"], "<p>EDITED BEFORE PUBLISH</p>")
        self.assertEqual(self.current(), row.pk)
        self.assertEqual(PageRevision.objects.count(), count + 1)
        self.assertFalse(OwnerDraft.objects.filter(pk=draft.pk).exists())
        self.assertFalse(VersionBasePin.objects.filter(holder_id=draft.pk).exists())
        self.assertFalse(OperationReceipt.objects.filter(
            pk=value["operationId"]).exists())
        before = self.state()
        missing = self.owner_client.get(self.path("state", selector))
        self.reject(missing)
        replay = self.send("save", value, selector=selector)
        self.reject(replay)
        self.assertEqual(self.state(), before)

    def test_legacy_draft_publish_receipt_replays_through_simple_routing(self):
        draft = self.draft()
        value, selector, _ = self.checked(
            {"main_text":"<p>LEGACY PUBLISH</p>"}, draft=draft)
        request_fingerprint = fingerprint({
            "input":value,
            "source":{
                "editingFrom":"owner-draft",
                "draftBasis":{"id":str(draft.pk), "revision":draft.revision},
                "stageId":None, "rebase":False, "targetCurrentId":None,
            },
        })
        payload = {**draft.payload, **value["changes"]}
        original = E.commit_owner(
            actor=self.owner, page_id=self.page.pk,
            base_revision=draft.base_revision_id,
            snapshot=S.Snapshot.trusted(payload, self.page.kind),
            expected_generation=1, operation_id=value["operationId"],
            draft_id=draft.pk, draft_revision=draft.revision,
            expected_draft_hash=S.digest(draft.payload),
            editor_request_fingerprint=request_fingerprint,
            editor_session_key=self.owner_client.session.session_key)
        before = self.state()
        audit = list(AuditEvent.objects.order_by("id").values())
        response = self.send("save", value, selector=selector)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["replay"])
        self.assertEqual(response.json()["result_id"], original["result_id"])
        self.assertEqual(self.state(), before)
        self.assertEqual(list(AuditEvent.objects.order_by("id").values()), audit)

    def test_actual_draft_revision_change_conflicts_with_old_checked_publish(self):
        draft = self.draft()
        value, selector, _ = self.checked({"main_text":"<p>OLD TAB</p>"}, draft=draft)
        V.save_owner_draft(actor=self.owner,page_id=self.page.pk,base_revision=draft.base_revision_id,
            snapshot=S.snapshot_v1(self.page.kind,main_text="OTHER TAB"),draft_revision=draft.revision,
            expected_generation=1,operation_id=uuid4())
        before = self.state()
        self.reject(self.send("save",value,selector=selector))
        self.assertEqual(self.state(),before)

    def test_normal_draft_proof_cannot_be_converted_into_rebase(self):
        draft = self.draft()
        value, _, _ = self.checked({"main_text":"<p>NORMAL DRAFT CHECK</p>"},draft=draft)
        target = self.advance()
        selector = self.selector(draft=draft,target=target)
        before = self.state()
        self.reject(self.send("draft",{**value,"rebase":True},selector=selector))
        self.assertEqual(self.state(),before)

    def test_explicit_rebase_proof_moves_basis_without_publication(self):
        draft = self.draft()
        target = self.advance()
        value, selector, _ = self.checked({"main_text":"<p>EXPLICIT REBASE</p>"},draft=draft,target=target)
        count = PageRevision.objects.count()
        response = self.send("draft",{**value,"rebase":True},selector=selector)
        self.assertEqual(response.status_code,200)
        changed = self.draft()
        self.assertEqual(changed.pk,draft.pk)
        self.assertEqual(str(changed.base_revision_id),str(target))
        self.assertEqual(changed.revision,draft.revision+1)
        self.assertEqual(str(self.current()),str(target))
        self.assertEqual(PageRevision.objects.count(),count)
        self.assertFalse(VersionBasePin.objects.filter(
            holder_kind="owner_draft", holder_id=draft.pk).exists())

    def test_rebase_target_change_after_compare_is_conflict(self):
        draft = self.draft()
        target = self.advance()
        value, selector, _ = self.checked({"main_text":"<p>REBASE OLD TARGET</p>"},draft=draft,target=target)
        self.advance("NEWER TARGET")
        before = self.state()
        self.reject(self.send("draft",{**value,"rebase":True},selector=selector))
        self.assertEqual(self.state(),before)

    def test_cancel_draft_stale_revision_then_actual_cancel_repeat_conflicts(self):
        draft = self.draft()
        V.save_owner_draft(actor=self.owner,page_id=self.page.pk,base_revision=draft.base_revision_id,
            snapshot=S.snapshot_v1(self.page.kind,main_text="NEXT DRAFT"),draft_revision=draft.revision,
            expected_generation=1,operation_id=uuid4())
        value={"generation":1,"draftId":str(draft.pk),"draftRevision":draft.revision,"operationId":str(uuid4())}
        before=self.state()
        self.reject(self.send("draft/cancel",value))
        self.assertEqual(self.state(),before)
        value.update(draftRevision=draft.revision+1,operationId=str(uuid4()))
        response=self.send("draft/cancel",value)
        self.assertEqual(response.status_code,200)
        self.assertFalse(OwnerDraft.objects.filter(pk=draft.pk).exists())
        before=self.state()
        replay=self.send("draft/cancel",value)
        self.reject(replay)
        self.assertEqual(self.state(),before)

    def test_stage_selected_load_check_do_not_publish(self):
        stage=self.seed_stage()
        before=self.state()
        selector=self.selector(stage=stage)
        state=self.employee_client.get(self.path("state",selector))
        self.assertEqual(state.status_code,200)
        self.assertTrue(state.json()["canReadSource"])
        self.assertEqual(state.json()["sourceContext"]["stageId"],str(stage.pk))
        self.checked({"intro_text":"","main_text":"<p>STAGED RAM</p>"},stage=stage,client=self.employee_client)
        self.assertEqual(self.state(),before)

    def test_edited_stage_employee_save_preserves_projection_and_consumes(self):
        stage=self.seed_stage()
        current=PageRevision.objects.get(pk=self.current()).payload
        value,selector,_=self.checked({"intro_text":"","main_text":"<p>EDITED STAGE</p>"},stage=stage,client=self.employee_client)
        response=self.send("save",value,selector=selector,client=self.employee_client)
        self.assertEqual(response.status_code,200)
        row=PageRevision.objects.get(pk=response.json()["result_id"])
        self.assertEqual(row.payload,{**current,"intro_text":"","main_text":"<p>EDITED STAGE</p>"})
        self.assertEqual(row.source_revision_id,stage.source_revision_id)
        stage.refresh_from_db()
        self.assertEqual(stage.status,"consumed")
        self.assertFalse(VersionBasePin.objects.filter(holder_id=stage.pk).exists())
        before=self.state()
        replay=self.send("save",value,selector=selector,client=self.employee_client)
        self.assertEqual(replay.status_code,200)
        self.assertTrue(replay.json()["replay"])
        self.assertEqual(self.state(),before)

    def test_stage_foreign_actor_and_query_body_mismatch_denied(self):
        stage=self.seed_stage()
        value,selector,_=self.checked({"intro_text":"","main_text":"<p>STAGE</p>"},stage=stage,client=self.employee_client)
        before=self.state()
        self.reject(self.send("save",value,selector=selector,client=self.other_client),403)
        self.reject(self.send("save",value,selector={"source":"restore-stage","stageId":str(uuid4())},client=self.employee_client),400)
        self.assertEqual(self.state(),before)

    def test_stage_revoke_after_check_cannot_save(self):
        stage=self.seed_stage()
        value,selector,_=self.checked({"intro_text":"","main_text":"<p>REVOKED</p>"},stage=stage,client=self.employee_client)
        set_grant(actor=self.owner,employee=self.employee,page=self.page,revoke=True)
        before=self.state()
        response=self.send("save",value,selector=selector,client=self.employee_client)
        self.assertEqual(response.status_code,401)
        self.assertIn("no-store",response["Cache-Control"])
        self.assertEqual(self.state(),before)

    def test_draft_audit_fault_rolls_back_payload_refs_and_legacy_pin(self):
        draft=self.draft()
        value,selector,_=self.checked({"main_text":"<p>FAULT DRAFT</p>"},draft=draft)
        before=self.state();audit=AuditEvent.objects.count();actual=E.event
        def fault(*args,**kwargs):
            actual(*args,**kwargs)
            raise DatabaseError("synthetic draft post-audit fault")
        with patch("page_versions.engine.event",side_effect=fault):
            response=self.send("draft",{**value,"rebase":False},selector=selector)
        self.assertEqual(response.status_code,503)
        self.assertEqual(self.state(),before)
        self.assertEqual(AuditEvent.objects.count(),audit)

    def test_stage_publish_finish_fault_rolls_back_current_consume_pins(self):
        stage=self.seed_stage()
        value,selector,_=self.checked({"intro_text":"","main_text":"<p>FAULT STAGE</p>"},stage=stage,client=self.employee_client)
        before=self.state();actual=E.finish
        def fault(*args,**kwargs):
            actual(*args,**kwargs)
            raise DatabaseError("synthetic stage post-ledger fault")
        with patch("page_versions.engine.finish",side_effect=fault):
            response=self.send("save",value,selector=selector,client=self.employee_client)
        self.assertEqual(response.status_code,503)
        self.assertEqual(self.state(),before)

    def test_draft_session_deleted_during_real_preflight_cannot_update(self):
        draft=self.draft()
        value,selector,_=self.checked({"main_text":"<p>LATE SESSION</p>"},draft=draft)
        before=self.state();actual=E.preflight;key=self.owner_client.session.session_key
        def logout(payload):
            evidence=actual(payload)
            Session.objects.filter(pk=key).delete()
            return evidence
        with patch("page_versions.engine.preflight",side_effect=logout):
            response=self.send("draft",{**value,"rebase":False},selector=selector)
        self.reject(response,401)
        self.assertEqual(self.state(),before)

    def test_pre_d07_current_editor_fingerprint_receipt_replays_without_recommit(self):
        value, selector, _ = self.checked({"main_text":"<p>LEGACY CURRENT EDITOR SAVE</p>"})
        self.assertEqual(selector,{})
        base=PageRevision.objects.get(pk=self.current())
        payload=base.payload.copy()
        payload.update(value["changes"])
        original=E.commit_owner(actor=self.owner,page_id=self.page.pk,base_revision=base.pk,
            snapshot=S.Snapshot.trusted(payload,self.page.kind),expected_generation=1,
            operation_id=value["operationId"],editor_request_fingerprint=fingerprint(value),
            editor_session_key=self.owner_client.session.session_key)
        self.advance("CURRENT AFTER LEGACY EDITOR COMMIT")
        before=self.state()
        audit=list(AuditEvent.objects.order_by("id").values())
        response=self.send("save",value,selector=selector)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()["replay"])
        self.assertEqual(response.json()["result_id"],original["result_id"])
        self.assertEqual(self.state(),before)
        self.assertEqual(list(AuditEvent.objects.order_by("id").values()),audit)
