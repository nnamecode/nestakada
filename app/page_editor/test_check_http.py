"""Framework HTTP/PG + real child. Not Nginx/WSGI socket transport evidence."""
from dataclasses import replace
import hashlib
import json
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from django.conf import settings
from django.core import signing
from django.db import connection
from django.test import Client, TransactionTestCase, override_settings
from django.urls import include, path

from accounts.models import AuthSession
from accounts.services import bootstrap_owner, create_employee, set_grant, set_active, AUTH_LOCK
from audit.constants import Result
from audit.models import AuditEvent
from content.models import Page, Route, CONTENT_LOCK
from editor_runtime.guards import EditorBusy, BodyTooLarge
from editor_runtime.processing import normalize_input, ProcessingUnavailable
from media_library.models import AssetUsage
from page_versions import services as V, schema as S
from page_versions.models import (PageRevision, PageContentState, OwnerDraft,
                                  RestoreStage, OperationReceipt)
from page_editor.checks import (CheckFault, inspect_context, verify_check_receipt,
                                SALT)

# Explicit test-only wiring: global product URLconf is untouched.
urlpatterns = [path("manage/pages/<uuid:page_id>/edit/", include("page_editor.http_urls")),
               path("", include("estakada.urls"))]
TEST_MIDDLEWARE = list(settings.MIDDLEWARE)
TEST_MIDDLEWARE.insert(TEST_MIDDLEWARE.index("django.middleware.csrf.CsrfViewMiddleware"),
                       "page_editor.middleware.EditorAdmissionMiddleware")

OWNER_PASSWORD = "Synthetic-check-owner-password"
EMPLOYEE_PASSWORD = "Synthetic-check-employee-password"


@override_settings(ROOT_URLCONF=__name__, MIDDLEWARE=TEST_MIDDLEWARE, AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EditorCheckHttpTests(TransactionTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        media = override_settings(MEDIA_LIBRARY_ROOT=self.temp.name)
        media.enable()
        self.addCleanup(media.disable)
        self.owner = bootstrap_owner(OWNER_PASSWORD)
        self.employee = create_employee(actor=self.owner, username="check-text", password=EMPLOYEE_PASSWORD)
        self.price_employee = create_employee(actor=self.owner, username="check-price", password=EMPLOYEE_PASSWORD)
        self.other = create_employee(actor=self.owner, username="check-other", password=EMPLOYEE_PASSWORD)
        self.page = Page.objects.create(kind=Page.Kind.ARTICLE, name="Check fixture")
        Route.objects.create(page=self.page, kind=Route.Kind.PRIMARY, target="/services/check/")
        set_grant(actor=self.owner, employee=self.employee, page=self.page, intro_text=True, main_text=True)
        set_grant(actor=self.owner, employee=self.price_employee, page=self.page, main_text=True, price=True)
        self.initial = V.initialize(actor=self.owner, page_id=self.page.pk,
            snapshot=S.snapshot_v1(self.page.kind, main_text="<p>SAVED</p>", h1="Protected heading"),
            expected_generation=1, operation_id=uuid4())["result_id"]
        V.save_owner_draft(actor=self.owner, page_id=self.page.pk, base_revision=self.initial,
            snapshot=S.snapshot_v1(self.page.kind, main_text="OWNER_DRAFT_PRIVATE_CANARY"),
            expected_generation=1, operation_id=uuid4())
        self.owner_client = self.login("nesadmin", OWNER_PASSWORD)
        self.employee_client = self.login(self.employee.username, EMPLOYEE_PASSWORD)
        self.price_client = self.login(self.price_employee.username, EMPLOYEE_PASSWORD)
        self.other_client = self.login(self.other.username, EMPLOYEE_PASSWORD)
        self.visitor = Client(enforce_csrf_checks=True, HTTP_HOST="localhost")
        self.url = "/manage/pages/%s/edit/check/" % self.page.pk

    def login(self, username, password):
        client = Client(enforce_csrf_checks=True, HTTP_HOST="localhost")
        self.assertEqual(client.get("/manage/login/").status_code, 200)
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        response = client.post("/manage/login/", urlencode({"username":username,
            "password":password, "csrfmiddlewaretoken":token}),
            content_type="application/x-www-form-urlencoded")
        self.assertEqual(response.status_code, 303)
        return client

    def payload(self, changes=None, **kwargs):
        result = {"protocol":"page-editor-v1", "generation":1,
                  "baseRevisionId":str(self.initial), "editingFrom":"current",
                  "draftBasis":None, "stageId":None,
                  "changes":changes if changes is not None else {"main_text":"<p>NEW 😀</p>"}}
        result.update(kwargs)
        return result

    def raw(self, value):
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()

    def post(self, client, value=None, *, raw=None, csrf=True, reader=None, origin=None):
        data = self.raw(self.payload() if value is None else value) if raw is None else raw
        headers = {}
        if csrf and settings.CSRF_COOKIE_NAME in client.cookies:
            headers["HTTP_X_CSRFTOKEN"] = client.cookies[settings.CSRF_COOKIE_NAME].value
        if origin is not None:
            headers["HTTP_ORIGIN"] = origin
        # Django Client has no approved interruptible WSGI socket. Only replace
        # that transport seam; the real child/normalizer is never faked here.
        with patch("page_editor.views.read_json_bytes", side_effect=reader or (lambda request, profile: request.body)):
            return client.post(self.url, data=data, content_type="application/json", **headers)

    def state(self):
        return {
            "state":list(PageContentState.objects.values()),
            "revisions":list(PageRevision.objects.order_by("id").values()),
            "drafts":list(OwnerDraft.objects.order_by("id").values()),
            "stages":list(RestoreStage.objects.order_by("id").values()),
            "refs":list(AssetUsage.objects.order_by("id").values()),
            "operations":list(OperationReceipt.objects.order_by("id").values()),
        }

    def context(self, actor=None):
        return inspect_context(actor=actor or self.owner, page_id=self.page.pk,
                               generation=1, origin="http://localhost")

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.json(), {"ok":False, "code":code})
        self.assertIn("no-store", response["Cache-Control"])

    def test_real_child_owner_check_signed_proof_and_no_mutation(self):
        before = self.state()
        payload = self.payload({"main_text":"<p><b>NEW 😀</b></p>", "title":"T", "description":""})
        response = self.post(self.owner_client, payload)
        self.assertEqual(response.status_code, 200)
        value = response.json()
        self.assertEqual(set(value), {"protocol", "inputFingerprint", "normalisedChanges",
                         "normalisationChanged", "fieldWarnings", "checkReceipt", "baseRevisionId"})
        self.assertEqual(value["protocol"], "page-editor-v1")
        self.assertEqual(value["normalisedChanges"], {"main_text":"<p><strong>NEW 😀</strong></p>", "title":"T", "description":""})
        self.assertTrue(value["normalisationChanged"])
        self.assertEqual(value["inputFingerprint"], hashlib.sha256(self.raw(payload)).hexdigest())
        self.assertEqual(value["baseRevisionId"], str(self.initial))
        self.assertTrue(all(set(w) == {"field", "code"} for w in value["fieldWarnings"]))
        verified = verify_check_receipt(value["checkReceipt"], context=self.context(), changes=value["normalisedChanges"])
        self.assertEqual(verified["actorId"], self.owner.pk)
        self.assertEqual(verified["inputFingerprint"], value["inputFingerprint"])
        self.assertNotIn("OWNER_DRAFT_PRIVATE_CANARY", response.content.decode())
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.state(), before)

    def test_multipart_admission_and_bad_origin_before_body(self):
        before = self.state()
        for client in (self.owner_client, self.other_client):
            with patch("django.http.request.HttpRequest.read", side_effect=AssertionError("body read")), \
                 patch("page_editor.views.normalize_input", side_effect=AssertionError("child reached")):
                response = client.post(self.url, data=b"NOT_A_FORM", content_type="multipart/form-data; boundary=synthetic")
            self.assert_error(response, 415, "EDITOR_JSON_REQUIRED")
        with patch("page_editor.views.normalize_input", side_effect=AssertionError("child reached")):
            response = self.post(self.owner_client, origin="https://outside.invalid",
                reader=lambda *_: (_ for _ in ()).throw(AssertionError("body reached")))
        self.assertEqual(response.status_code, 403)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.state(), before)

    def test_real_child_employee_text_and_price_positives(self):
        before = self.state()
        response = self.post(self.employee_client, self.payload({"intro_text":"<p>INTRO</p>", "main_text":"<p>BODY</p>"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()["normalisedChanges"]), {"intro_text", "main_text"})
        column, row = str(uuid4()), str(uuid4())
        price = {"columns":[{"id":column, "label":"Цена"}],
                 "rows":[{"id":row, "label":"Работа", "cells":[{"column_id":column,
                           "kind":"amount", "amount":"12.50", "from":True}]}]}
        response = self.post(self.price_client, self.payload({"price":price}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["normalisedChanges"]["price"]["rows"][0]["cells"][0]["amount"], "12.5")
        self.assertNotIn("OWNER_DRAFT_PRIVATE_CANARY", response.content.decode())
        self.assertEqual(self.state(), before)

    def test_early_visitor_foreign_and_csrf_never_reader_or_child(self):
        before = self.state()
        for client, csrf, status in ((self.visitor, False, 401), (self.other_client, True, 403),
                                     (self.owner_client, False, 403)):
            with self.subTest(status=status, csrf=csrf):
                with patch("page_editor.views.normalize_input", side_effect=AssertionError("child reached")):
                    response = self.post(client, csrf=csrf,
                        reader=lambda *_: (_ for _ in ()).throw(AssertionError("body reached")))
                self.assertEqual(response.status_code, status)
                self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.state(), before)

    def test_employee_forbidden_fields_and_no_receipt(self):
        before = self.state()
        for changes in ({"title":"old"}, {"main_image":None}, {"price":None},
                        {"main_text":"<p>X</p>", "h1":"Protected heading"},
                        {"layout":[]}, {"embedded_images":[]}):
            with self.subTest(fields=sorted(changes)):
                self.assert_error(self.post(self.employee_client, self.payload(changes)), 403, "EDITOR_FIELDS_FORBIDDEN")
        self.assertEqual(self.state(), before)

    def test_repeated_forbidden_field_posts_increment_session_and_bound_audit(self):
        before = self.state()
        session = AuthSession.objects.get(pk=self.employee_client.session.session_key)
        initial_count = session.denied_page_count
        self.assertEqual(initial_count, 0)
        events = AuditEvent.objects.filter(code="SEC_PERMISSION_DENIED", actor_id=self.employee.pk)
        initial_events = events.count()
        canary = "FORBIDDEN_FIELD_SYNTHETIC_INPUT_CANARY"
        for index in range(3):
            response = self.post(self.employee_client, self.payload({"title":canary}))
            self.assert_error(response, 403, "EDITOR_FIELDS_FORBIDDEN")
            self.assertNotIn("checkReceipt", response.json())
            session.refresh_from_db()
            self.assertEqual(session.denied_page_count, initial_count + index + 1)
            self.assertFalse(session.denial_count_lower_bound)
            self.assertEqual(events.count(), initial_events + 1)
        event = events.latest("id")
        self.assertEqual(event.occurrence_count, 1)
        self.assertFalse(event.count_is_lower_bound)
        self.assertEqual(event.result, Result.DENIED)
        self.assertNotIn(canary, str(list(events.values())))
        self.assertEqual(self.state(), before)

    def test_current_only_draft_stage_and_media_explicit_capability_refusal(self):
        before = self.state()
        variants = [self.payload(editingFrom="owner-draft", draftBasis={"id":str(uuid4()), "revision":1}),
                    self.payload(editingFrom="restore-stage", stageId=str(uuid4())),
                    self.payload({"main_image":None})]
        for value in variants:
            self.assert_error(self.post(self.owner_client, value), 409, "EDITOR_CAPABILITY_UNAVAILABLE")
        self.assertEqual(self.state(), before)

    def test_generation_and_base_conflicts_real_child(self):
        before = self.state()
        self.assert_error(self.post(self.owner_client, self.payload(generation=2)), 403, "EDITOR_IDENTITY_CHANGED")
        self.assert_error(self.post(self.owner_client, self.payload(baseRevisionId=str(uuid4()))), 409, "EDITOR_BASE_CONFLICT")
        self.assertEqual(self.state(), before)

    def test_malformed_closed_dto_and_unsafe_html_real_child(self):
        before = self.state()
        valid = self.payload()
        variants = [self.raw({**valid, "extra":True}), self.raw({**valid, "generation":True}),
                    self.raw({**valid, "changes":{}}), self.raw({**valid, "protocol":"other"}),
                    self.raw(valid)[:-1] + b',"generation":1}', b'{"x":NaN}', b'\xff', b'[]',
                    self.raw(self.payload({"main_text":"<p>SAFE</p><script>alert(1)</script>"})),
                    self.raw(self.payload({"main_text":'<a href="javascript:alert(1)'}))]
        for index, raw in enumerate(variants):
            with self.subTest(index=index):
                self.assert_error(self.post(self.owner_client, raw=raw), 400, "EDITOR_INPUT_REJECTED")
        self.assertEqual(self.state(), before)

    def test_server_owned_profile_and_reader_budget_failure(self):
        for client, expected in ((self.owner_client,64 * 1024 * 1024),
                                 (self.price_client,64 * 1024 * 1024),
                                 (self.employee_client,5 * 1024 * 1024)):
            seen = []
            def reader(request, profile):
                seen.append(profile.byte_budget)
                return request.body
            self.assertEqual(self.post(client, reader=reader).status_code, 200)
            self.assertEqual(seen, [expected])
        before = self.state()
        def over_budget(*_):
            raise BodyTooLarge()
        self.assert_error(self.post(self.owner_client, reader=over_budget), 413, "EDITOR_BODY_TOO_LARGE")
        self.assertEqual(self.state(), before)

    def test_permission_revoke_after_child_cannot_issue_receipt(self):
        actual = normalize_input
        def revoke(raw, context):
            result = actual(raw, context)
            set_grant(actor=self.owner, employee=self.employee, page=self.page, revoke=True)
            return result
        before = self.state()
        with patch("page_editor.views.normalize_input", side_effect=revoke):
            response = self.post(self.employee_client)
        self.assert_error(response, 403, "EDITOR_FIELDS_FORBIDDEN")
        self.assertEqual(self.state(), before)

    def test_current_change_during_child_conflicts_without_check_mutation(self):
        actual = normalize_input
        after_commit = []
        def advance(raw, context):
            result = actual(raw, context)
            V.commit_owner(actor=self.owner, page_id=self.page.pk, base_revision=self.initial,
                snapshot=S.snapshot_v1(self.page.kind, main_text="<p>CONCURRENT</p>"),
                expected_generation=1, operation_id=uuid4())
            after_commit.append(self.state())
            return result
        with patch("page_editor.views.normalize_input", side_effect=advance):
            response = self.post(self.owner_client)
        self.assert_error(response, 409, "EDITOR_CONTEXT_CHANGED")
        self.assertEqual(self.state(), after_commit[0])

    def test_late_session_invalidation_after_real_child_returns_401(self):
        before = self.state()
        def invalidate(raw, context):
            result = normalize_input(raw, context)
            set_active(actor=self.owner, employee=self.employee, active=False)
            return result
        with patch("page_editor.views.normalize_input", side_effect=invalidate):
            response = self.post(self.employee_client)
        self.assert_error(response, 401, "EDITOR_SESSION_ENDED")
        self.assertEqual(self.state(), before)

    def test_disabled_session_refused_before_body_and_child(self):
        set_active(actor=self.owner, employee=self.employee, active=False)
        with patch("page_editor.views.normalize_input", side_effect=AssertionError("child reached")):
            response = self.post(self.employee_client,
                reader=lambda *_: (_ for _ in ()).throw(AssertionError("body reached")))
        self.assertEqual(response.status_code, 401)
        self.assertIn("no-store", response["Cache-Control"])

    def test_no_transaction_or_domain_advisory_locks_during_reader_and_real_child(self):
        observations = []
        def observe(label):
            self.assertFalse(connection.in_atomic_block)
            probe = connection.copy(alias="editor_check_lock_probe")
            try:
                probe.ensure_connection()
                with probe.cursor() as cursor:
                    for key in (CONTENT_LOCK, AUTH_LOCK):
                        cursor.execute("SELECT pg_try_advisory_lock(%s)", [key])
                        self.assertTrue(cursor.fetchone()[0])
                    cursor.execute("SELECT pg_advisory_unlock_all()")
            finally:
                probe.close()
            observations.append(label)
        def reader(request, profile):
            observe("reader")
            return request.body
        def child(raw, context):
            observe("child")
            return normalize_input(raw, context)
        with patch("page_editor.views.normalize_input", side_effect=child):
            response = self.post(self.owner_client, reader=reader)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(observations, ["reader", "child"])

    def test_signed_receipt_tamper_actor_base_permissions_policy_and_changes(self):
        result = self.post(self.owner_client).json()
        token, changes = result["checkReceipt"], result["normalisedChanges"]
        context = self.context()
        claims = verify_check_receipt(token, context=context, changes=changes)
        with self.assertRaises(CheckFault):
            verify_check_receipt(token + "x", context=context, changes=changes)
        with self.assertRaises(CheckFault):
            verify_check_receipt(token, context=context, changes={"main_text":"DIFFERENT"})
        altered_contexts = [replace(context, actor_id=self.employee.pk),
                            replace(context, permission_hash="changed"), replace(context, stamp="changed")]
        for key, value in (("generation",2), ("page_id",str(uuid4())), ("base_revision_id",str(uuid4()))):
            altered_contexts.append(replace(context, child={**context.child, key:value}))
        for changed in altered_contexts:
            with self.assertRaises(CheckFault):
                verify_check_receipt(token, context=changed, changes=changes)
        for key, value in (("protocol","other"), ("editingFrom","owner-draft"), ("inputFingerprint","not-a-hash")):
            # Valid signature with invalid claims exercises closed proof schema.
            bad_token = signing.dumps({**claims, key:value}, salt=SALT, compress=False)
            with self.assertRaises(CheckFault):
                verify_check_receipt(bad_token, context=context, changes=changes)

    def test_old_receipt_fails_after_actual_grant_change(self):
        response = self.post(self.employee_client).json()
        set_grant(actor=self.owner, employee=self.employee, page=self.page, main_text=True, price=True)
        with self.assertRaises(CheckFault):
            verify_check_receipt(response["checkReceipt"], context=self.context(self.employee),
                                 changes=response["normalisedChanges"])
        self.assertEqual(self.post(self.employee_client).status_code, 200)

    def test_old_receipt_fails_after_semantic_policy_change(self):
        response = self.post(self.owner_client).json()
        context = self.context()
        with patch("page_editor.policy_constants.POLICY_VERSION", "independent-new-policy"):
            with self.assertRaises(CheckFault) as caught:
                verify_check_receipt(response["checkReceipt"], context=context,
                                     changes=response["normalisedChanges"])
            self.assertEqual(caught.exception.status, 409)
            with self.assertRaises(CheckFault):
                verify_check_receipt(response["checkReceipt"], context=self.context(),
                                     changes=response["normalisedChanges"])

    def test_busy_and_worker_failure_no_content_mutation_then_explicit_retry(self):
        before = self.state()
        with patch("page_editor.views.EditorSlot.__enter__", side_effect=EditorBusy()):
            with patch("page_editor.views.normalize_input", side_effect=AssertionError("child reached")):
                self.assert_error(self.post(self.owner_client,
                    reader=lambda *_: (_ for _ in ()).throw(AssertionError("reader reached"))), 503, "EDITOR_BUSY")
        with patch("page_editor.views.normalize_input", side_effect=ProcessingUnavailable()):
            self.assert_error(self.post(self.owner_client), 503, "EDITOR_PROCESS_UNAVAILABLE")
        self.assertEqual(self.state(), before)
        self.assertEqual(self.post(self.owner_client).status_code, 200)
        self.assertEqual(self.state(), before)

    def test_failure_diagnostics_do_not_echo_synthetic_input(self):
        canary = "CHECK_SECRETLIKE_SYNTHETIC_CANARY"
        before = self.state()
        response = self.post(self.owner_client, self.payload({"main_text":"<script>" + canary + "</script>"}))
        self.assert_error(response, 400, "EDITOR_INPUT_REJECTED")
        self.assertNotIn(canary.encode(), response.content)
        self.assertEqual(self.state(), before)
        # This checks bounded response diagnostics only; full app/Nginx/audit/
        # tmp/input-log inspection remains H07-025 runtime evidence.
