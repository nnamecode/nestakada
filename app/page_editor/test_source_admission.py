"""Actual SQL guard: source payload admission must follow heavy-slot acquisition."""
import re
from unittest.mock import patch
from urllib.parse import urlencode

from django.conf import settings
from django.db import connection
from django.test import TransactionTestCase, override_settings

from editor_runtime.guards import EditorBusy
from page_versions.models import OwnerDraft, PageRevision
from page_editor import test_check_http as H


def no_payload_sql(execute, sql, params, many, context):
    # Do not print or retain SQL parameters. Reject even JSON-path projections:
    # metadata admission has no need to touch the large payload column at all.
    if sql.lstrip().upper().startswith("SELECT") and re.search(r'"payload"', sql):
        raise AssertionError("PAYLOAD_SQL_BEFORE_ADMISSION")
    return execute(sql, params, many, context)


@override_settings(ROOT_URLCONF="page_editor.test_check_http", MIDDLEWARE=H.TEST_MIDDLEWARE,
                   AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SourceAdmissionTests(TransactionTestCase):
    setUp=H.EditorCheckHttpTests.setUp
    login=H.EditorCheckHttpTests.login
    raw=H.EditorCheckHttpTests.raw
    payload=H.EditorCheckHttpTests.payload

    def prefix(self):
        return "/manage/pages/%s/edit/" % self.page.pk

    def test_default_state_metadata_has_no_payload_sql_with_real_detector_control(self):
        with connection.execute_wrapper(no_payload_sql), \
             patch("page_editor.editor_page.context_for",side_effect=AssertionError("FULL_CONTEXT_REACHED")):
            for client in (self.owner_client,self.employee_client):
                response=client.get(self.prefix()+"state/")
                self.assertEqual(response.status_code,200)
                value=response.json()
                self.assertEqual(value["baseRevisionId"],str(self.initial))
                self.assertIsInstance(value["fields"],list)
                self.assertIn("main_text",value["fields"])
                self.assertNotIn("payload",value)
                self.assertNotIn("values",value)
                self.assertNotIn("OWNER_DRAFT_PRIVATE_CANARY",response.content.decode())
                self.assertIn("no-store",response["Cache-Control"])
        # Prove the instrumentation rejects a genuine source SELECT rather than
        # passing because a guessed accessor/SQL hook was never invoked.
        with self.assertRaisesMessage(AssertionError,"PAYLOAD_SQL_BEFORE_ADMISSION"):
            with connection.execute_wrapper(no_payload_sql):
                PageRevision.objects.values_list("payload",flat=True).get(pk=self.initial)

    def test_cancel_denials_never_load_draft_or_current_payload(self):
        url=self.prefix()+"draft/cancel/"
        cases=[(self.employee_client,"multipart/form-data; boundary=x",403),
               (self.other_client,"multipart/form-data; boundary=x",403),
               (self.visitor,"multipart/form-data; boundary=x",401),
               (self.owner_client,"multipart/form-data; boundary=x",415)]
        with connection.execute_wrapper(no_payload_sql), \
             patch("page_editor.views.request_context",side_effect=AssertionError("FULL_CONTEXT_REACHED")), \
             patch("django.http.request.HttpRequest.read",side_effect=AssertionError("BODY_READ_REACHED")), \
             patch("page_versions.engine.cancel_owner_draft",side_effect=AssertionError("CANCEL_ENGINE_REACHED")):
            for client,content_type,status in cases:
                response=client.post(url,data=b"{}",content_type=content_type)
                self.assertEqual(response.status_code,status)
                self.assertIn("no-store",response["Cache-Control"])

    def test_busy_check_save_draft_refuse_before_full_context_body_child(self):
        token=self.owner_client.cookies[settings.CSRF_COOKIE_NAME].value
        with connection.execute_wrapper(no_payload_sql), \
             patch("page_editor.views.request_context",side_effect=AssertionError("FULL_CONTEXT_REACHED")), \
             patch("page_editor.views.EditorSlot",side_effect=EditorBusy()), \
             patch("page_editor.views.read_json_bytes",side_effect=AssertionError("BODY_READER_REACHED")), \
             patch("page_editor.views.normalize_input",side_effect=AssertionError("CHILD_REACHED")):
            for action in ("check","save","draft"):
                response=self.owner_client.post(self.prefix()+action+"/",data=self.raw(self.payload()),
                    content_type="application/json",HTTP_X_CSRFTOKEN=token)
                self.assertEqual(response.status_code,503)
                self.assertEqual(response.json(),{"ok":False,"code":"EDITOR_BUSY"})

    def test_busy_selected_state_and_editor_get_refuse_before_source_payload(self):
        draft=OwnerDraft.objects.get(page=self.page)
        selected="?"+urlencode({"source":"owner-draft","draftId":str(draft.pk),"draftRevision":draft.revision})
        with connection.execute_wrapper(no_payload_sql), \
             patch("page_editor.editor_page.context_for",side_effect=AssertionError("FULL_CONTEXT_REACHED")), \
             patch("page_editor.editor_page.EditorSlot",side_effect=EditorBusy()):
            for path in (self.prefix(),self.prefix()+selected,self.prefix()+"state/"+selected):
                response=self.owner_client.get(path)
                self.assertEqual(response.status_code,503)
                self.assertEqual(response.json(),{"ok":False,"code":"EDITOR_BUSY"})
                self.assertIn("no-store",response["Cache-Control"])
