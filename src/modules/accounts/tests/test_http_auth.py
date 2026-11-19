from __future__ import annotations

from urllib.parse import urlencode
from unittest.mock import patch

from django.contrib.auth import SESSION_KEY as AUTH_SESSION_KEY
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase

from modules.audit.api import Action, AuditEvent

from ..api import SESSION_GENERATION_KEY, current_staff_session
from ..middleware import PrivateIngressMiddleware
from ..models import StaffRole, User


class PrivateIngressMiddlewareTests(TestCase):
    page_save_path = "/manage/pages/00000000-0000-0000-0000-000000000001/save/"

    def test_invalid_login_ingress_stops_before_downstream_or_body(self):
        class BodyTrapRequest:
            method = "POST"
            path_info = "/manage/login/"
            META: dict[str, object] = {}

            @property
            def body(self):
                raise AssertionError("invalid ingress read the request body")

        request = BodyTrapRequest()

        def forbidden_downstream(_request):
            raise AssertionError("invalid ingress reached the body-capable middleware chain")

        response = PrivateIngressMiddleware(forbidden_downstream)(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b"INVALID_INGRESS")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_canonical_addresses_reach_downstream_without_reflection(self):
        for address in ("203.0.113.8", "2001:db8::1"):
            with self.subTest(address=address):
                request = RequestFactory().generic(
                    "POST",
                    "/manage/login/",
                    data=b"",
                    content_type="application/x-www-form-urlencoded",
                    HTTP_X_ESTAKADA_CLIENT_IP=address,
                )
                response = PrivateIngressMiddleware(
                    lambda _request: HttpResponse("NEXT")
                )(request)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, address)

    def test_noncanonical_or_spoofed_projections_are_rejected(self):
        invalid_meta = (
            {},
            {"HTTP_X_ESTAKADA_CLIENT_IP": ["203.0.113.8"]},
            {"HTTP_X_ESTAKADA_CLIENT_IP": "203.0.113.8:443"},
            {"HTTP_X_ESTAKADA_CLIENT_IP": "fe80::1%3"},
            {"HTTP_X_ESTAKADA_CLIENT_IP": " 203.0.113.8"},
            {"HTTP_X_ESTAKADA_CLIENT_IP": "203.0.113.8,198.51.100.2"},
            {
                "HTTP_X_ESTAKADA_CLIENT_IP": "203.0.113.8",
                "HTTP_FORWARDED": "for=203.0.113.8",
            },
            {
                "HTTP_X_ESTAKADA_CLIENT_IP": "203.0.113.8",
                "HTTP_X_FORWARDED_FOR": "203.0.113.8",
            },
            {
                "HTTP_X_ESTAKADA_CLIENT_IP": "203.0.113.8",
                "HTTP_X_REAL_IP": "203.0.113.8",
            },
        )
        for meta in invalid_meta:
            with self.subTest(meta=meta):
                request = RequestFactory().generic(
                    "POST",
                    "/manage/login/",
                    data=b"unread",
                    content_type="application/x-www-form-urlencoded",
                )
                request.META.update(meta)
                response = PrivateIngressMiddleware(
                    lambda _request: (_ for _ in ()).throw(
                        AssertionError("invalid ingress reached downstream")
                    )
                )(request)
                self.assertEqual(response.status_code, 400)

    def test_page_save_body_cap_rejects_before_body_and_downstream(self):
        class BodyTrapRequest:
            method = "POST"
            path_info = self.page_save_path
            META: dict[str, object]

            def __init__(self, length):
                self.META = {} if length is None else {"CONTENT_LENGTH": length}

            @property
            def body(self):
                raise AssertionError("invalid price body boundary read request body")

        for length in (None, 4_194_305, "4194305", "04", "x"):
            with self.subTest(length=length):
                response = PrivateIngressMiddleware(
                    lambda _request: (_ for _ in ()).throw(
                        AssertionError("invalid price body boundary reached downstream")
                    )
                )(BodyTrapRequest(length))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.content, b"INVALID_EDITOR_INPUT")
                self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_canonical_page_save_body_length_reaches_downstream(self):
        request = RequestFactory().generic(
            "POST",
            self.page_save_path,
            data=b"x" * 16,
            content_type="multipart/form-data; boundary=x",
        )
        request.META["CONTENT_LENGTH"] = "4194304"
        response = PrivateIngressMiddleware(lambda _request: HttpResponse("NEXT"))(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")


class LoginLogoutHttpTests(TestCase):
    ingress = "203.0.113.8"

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="nesadmin",
            password="correct horse battery staple",
            role=StaffRole.OWNER,
        )

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def _csrf(self) -> str:
        response = self.client.get("/manage/login/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertContains(response, 'name="username"', count=1)
        self.assertContains(response, 'name="password"', count=1)
        self.assertContains(response, 'name="csrfmiddlewaretoken"', count=1)
        return self.client.cookies["csrftoken"].value

    def _post_login(self, pairs: list[tuple[str, str]]):
        return self.client.post(
            "/manage/login/",
            data=urlencode(pairs),
            content_type="application/x-www-form-urlencoded",
            HTTP_X_ESTAKADA_CLIENT_IP=self.ingress,
        )

    def test_malformed_wire_does_not_authenticate_or_audit(self):
        token = self._csrf()
        malformed = [
            [("csrfmiddlewaretoken", token), ("username", "nesadmin"), ("username", "again"), ("password", "x")],
            [("csrfmiddlewaretoken", token), ("username", "nesadmin"), ("password", "x"), ("password", "again")],
            [
                ("csrfmiddlewaretoken", token),
                ("csrfmiddlewaretoken", token),
                ("username", "nesadmin"),
                ("password", "x"),
            ],
            [("csrfmiddlewaretoken", token), ("username", "nesadmin"), ("password", "x"), ("extra", "x")],
            [("csrfmiddlewaretoken", token), ("username", ""), ("password", "x")],
            [("csrfmiddlewaretoken", token), ("username", "x" * 151), ("password", "x")],
            [("csrfmiddlewaretoken", token), ("username", "nesadmin"), ("password", "x" * 4097)],
        ]
        for pairs in malformed:
            with self.subTest(pairs=pairs), patch("modules.accounts.web.authenticate") as authenticate:
                response = self._post_login(pairs)
                self.assertEqual(response.status_code, 200)
                authenticate.assert_not_called()
        self.assertEqual(AuditEvent.objects.count(), 0)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_file_form_is_rejected_before_authentication(self):
        token = self._csrf()
        with patch("modules.accounts.web.authenticate") as authenticate:
            response = self.client.post(
                "/manage/login/",
                data={
                    "csrfmiddlewaretoken": token,
                    "username": "nesadmin",
                    "password": "x",
                    "upload": SimpleUploadedFile("x.txt", b"x"),
                },
                HTTP_X_ESTAKADA_CLIENT_IP=self.ingress,
            )
        self.assertEqual(response.status_code, 200)
        authenticate.assert_not_called()
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_json_is_rejected_before_authentication(self):
        token = self._csrf()
        with patch("modules.accounts.web.authenticate") as authenticate:
            response = self.client.post(
                "/manage/login/",
                data='{"username":"nesadmin","password":"x"}',
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
                HTTP_X_ESTAKADA_CLIENT_IP=self.ingress,
            )
        self.assertEqual(response.status_code, 200)
        authenticate.assert_not_called()
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_valid_invalid_credentials_write_one_safe_audit(self):
        token = self._csrf()
        response = self._post_login([
            ("csrfmiddlewaretoken", token),
            ("username", "nesadmin"),
            ("password", "wrong"),
        ])
        self.assertEqual(response.status_code, 200)
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, Action.AUTH_LOGIN_FAILED)
        self.assertIsNone(event.target_uuid)
        self.assertEqual(event.detail, {"reason": "INVALID_CREDENTIALS"})
        self.assertNotContains(response, "wrong")
        self.assertNotContains(response, self.ingress)

    def test_failed_login_audit_fault_denies_session(self):
        token = self._csrf()
        with patch("modules.accounts.web.append_event", side_effect=RuntimeError("audit")):
            response = self._post_login([
                ("csrfmiddlewaretoken", token),
                ("username", "nesadmin"),
                ("password", "wrong"),
            ])
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b"AUTH_UNAVAILABLE")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_success_commits_audit_and_exact_generation_before_redirect(self):
        token = self._csrf()
        response = self._post_login([
            ("csrfmiddlewaretoken", token),
            ("username", "nesadmin"),
            ("password", "correct horse battery staple"),
        ])
        self.assertRedirects(response, "/manage/pages/", fetch_redirect_response=False)
        session = self.client.session
        self.assertEqual(session[SESSION_GENERATION_KEY], self.owner.generation)
        self.assertEqual(session["_auth_user_id"], str(self.owner.id))
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, Action.AUTH_LOGIN_SUCCEEDED)
        self.assertEqual(event.target_uuid, self.owner.id)

    def test_success_audit_fault_leaves_session_anonymous(self):
        token = self._csrf()
        with patch("modules.accounts.web.append_event", side_effect=RuntimeError("audit")):
            response = self._post_login([
                ("csrfmiddlewaretoken", token),
                ("username", "nesadmin"),
                ("password", "correct horse battery staple"),
            ])
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_is_post_only_and_clears_even_when_audit_fails(self):
        self.client.force_login(self.owner)
        session = self.client.session
        session[SESSION_GENERATION_KEY] = self.owner.generation
        session.save()
        page_response = self.client.get("/manage/pages/")
        self.assertEqual(page_response.status_code, 200)
        token = self.client.cookies["csrftoken"].value

        get_response = self.client.get("/manage/logout/")
        self.assertEqual(get_response.status_code, 405)
        self.assertEqual(get_response["Cache-Control"], "private, no-store")
        self.assertIn("_auth_user_id", self.client.session)

        with patch("modules.accounts.web.append_event", side_effect=RuntimeError("audit")):
            response = self.client.post(
                "/manage/logout/",
                data=urlencode([("csrfmiddlewaretoken", token)]),
                content_type="application/x-www-form-urlencoded",
            )
        self.assertRedirects(response, "/manage/login/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_csrf_failure_mutates_neither_session_nor_audit(self):
        self.client.force_login(self.owner)
        session = self.client.session
        session[SESSION_GENERATION_KEY] = self.owner.generation
        session.save()
        response = self.client.post("/manage/logout/")
        self.assertEqual(response.status_code, 403)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_successful_logout_writes_one_actor_audit(self):
        self.client.force_login(self.owner)
        session = self.client.session
        session[SESSION_GENERATION_KEY] = self.owner.generation
        session.save()
        self.client.get("/manage/pages/")
        token = self.client.cookies["csrftoken"].value
        response = self.client.post(
            "/manage/logout/",
            data=urlencode([("csrfmiddlewaretoken", token)]),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 302)
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, Action.AUTH_LOGOUT)
        self.assertEqual(event.actor_uuid, self.owner.id)
        self.assertNotIn(AUTH_SESSION_KEY, self.client.session)

    def test_invalid_role_flushes_existing_auth_session(self):
        request = RequestFactory().get("/manage/pages/")
        SessionMiddleware(lambda _request: HttpResponse()).process_request(request)
        request.session[AUTH_SESSION_KEY] = str(self.owner.id)
        request.session[SESSION_GENERATION_KEY] = self.owner.generation
        request.user = self.owner
        request.user.role = "INVALID"

        self.assertIsNone(current_staff_session(request))
        self.assertNotIn(AUTH_SESSION_KEY, request.session)
        self.assertNotIn(SESSION_GENERATION_KEY, request.session)
