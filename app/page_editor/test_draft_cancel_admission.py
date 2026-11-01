"""Small draft/cancel admission before genuine CSRF multipart/body parsing."""
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.test import TransactionTestCase, override_settings

from page_versions.models import OwnerDraft, VersionBasePin
from page_editor import test_check_http as H


@override_settings(ROOT_URLCONF="page_editor.test_check_http", MIDDLEWARE=H.TEST_MIDDLEWARE,
                   AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class DraftCancelAdmissionTests(TransactionTestCase):
    setUp=H.EditorCheckHttpTests.setUp
    login=H.EditorCheckHttpTests.login
    raw=H.EditorCheckHttpTests.raw
    post=H.EditorCheckHttpTests.post

    def url_cancel(self):
        return "/manage/pages/%s/edit/draft/cancel/" % self.page.pk

    def state(self):
        return {**H.EditorCheckHttpTests.state(self),
                "pins":list(VersionBasePin.objects.order_by("id").values())}

    def body(self):
        draft=OwnerDraft.objects.get(page=self.page)
        return {"generation":1,"draftId":str(draft.pk),"draftRevision":draft.revision,"operationId":str(uuid4())}

    def early(self,client,*,content_type="application/json",**headers):
        with patch("django.http.request.HttpRequest._load_post_and_files",side_effect=AssertionError("POST_PARSE_REACHED")), \
             patch("django.http.request.HttpRequest.read",side_effect=AssertionError("BODY_READ_REACHED")), \
             patch("page_versions.engine.cancel_owner_draft",side_effect=AssertionError("CANCEL_ENGINE_REACHED")), \
             patch("page_editor.views.EditorSlot",side_effect=AssertionError("HEAVY_SLOT_REACHED")):
            return client.post(self.url_cancel(),data=b"{}",content_type=content_type,**headers)

    def test_employee_foreign_visitor_multipart_denied_before_post_or_body(self):
        before=self.state()
        for client,status in ((self.employee_client,403),(self.other_client,403),(self.visitor,401)):
            with self.subTest(status=status):
                response=self.early(client,content_type="multipart/form-data; boundary=synthetic")
                self.assertEqual(response.status_code,status)
                self.assertIn("no-store",response["Cache-Control"])
        self.assertEqual(self.state(),before)

    def test_owner_type_size_length_transfer_encoding_denied_before_csrf_parse(self):
        before=self.state()
        cases=[({"content_type":"multipart/form-data; boundary=synthetic"},415,"EDITOR_JSON_REQUIRED"),
               ({"CONTENT_LENGTH":"16385"},413,"EDITOR_BODY_TOO_LARGE"),
               ({"CONTENT_LENGTH":""},411,"EDITOR_LENGTH_REQUIRED"),
               ({"CONTENT_LENGTH":"-1"},400,"EDITOR_BODY_INVALID"),
               ({"HTTP_TRANSFER_ENCODING":"chunked"},400,"EDITOR_BODY_INVALID")]
        for headers,status,code in cases:
            with self.subTest(status=status,code=code):
                response=self.early(self.owner_client,**headers)
                self.assertEqual(response.status_code,status)
                self.assertEqual(response.json(),{"ok":False,"code":code})
                self.assertIn("no-store",response["Cache-Control"])
        self.assertEqual(self.state(),before)

    def test_real_csrf_remains_required_after_small_json_admission(self):
        before=self.state()
        with patch("django.http.request.HttpRequest.read",side_effect=AssertionError("BODY_READ_REACHED")), \
             patch("page_versions.engine.cancel_owner_draft",side_effect=AssertionError("CANCEL_ENGINE_REACHED")):
            response=self.owner_client.post(self.url_cancel(),data=self.raw(self.body()),content_type="application/json")
        self.assertEqual(response.status_code,403)
        self.assertIn("no-store",response["Cache-Control"])
        self.assertEqual(self.state(),before)

    def test_owner_header_csrf_actual_small_cancel_never_uses_heavy_slot(self):
        body=self.body()
        token=self.owner_client.cookies[settings.CSRF_COOKIE_NAME].value
        before=H.EditorCheckHttpTests.state(self)
        with patch("page_editor.views.EditorSlot",side_effect=AssertionError("HEAVY_SLOT_REACHED")):
            response=self.owner_client.post(self.url_cancel(),data=self.raw(body),content_type="application/json",HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["result_id"],body["draftId"])
        self.assertEqual(response.json()["action"],"cancel_draft")
        self.assertFalse(OwnerDraft.objects.filter(pk=body["draftId"]).exists())
        self.assertFalse(VersionBasePin.objects.filter(holder_id=body["draftId"]).exists())
        after=H.EditorCheckHttpTests.state(self)
        self.assertEqual(after["state"],before["state"])
        self.assertEqual(after["revisions"],before["revisions"])
