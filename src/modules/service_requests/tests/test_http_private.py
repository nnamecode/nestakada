from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

from django.core import signing
from django.test import Client, TestCase
from django.utils import timezone

from modules.accounts.api import SESSION_GENERATION_KEY
from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent
from modules.service_requests.ledger import PrimaryLedger, SyntheticIndependentLedger
from modules.service_requests.models import ServiceRequest, ServiceRequestDeletionProjection


class ServiceRequestPrivateHttpTests(TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.ledger = PrimaryLedger(Path(self.temporary.name)); self.independent = SyntheticIndependentLedger()
        with self.ledger.locked() as session: self.independent.publish_and_verify(session.snapshot())
        self.owner = User.objects.create_user(username="nesadmin", password="owner", role=StaffRole.OWNER,
                                              is_staff=True, is_superuser=True)
        self.employee = User.objects.create_user(username="employee", password="employee", role=StaffRole.EMPLOYEE,
                                                 is_staff=True, is_superuser=False)
        self.row = ServiceRequest.objects.create(id=uuid.uuid4(), name="<Иван>", phone="+79991234567",
            comment="<script>PRIVATE-COMMENT</script>", consent_text_version="v1", consent_text_sha256="a" * 64,
            consented_at=timezone.now())
        self.authority = patch("modules.service_requests.web._request_authority",
                               return_value=(self.ledger, self.independent))
        self.authority.start(); self.addCleanup(self.authority.stop)

    def _login(self, actor: User) -> Client:
        client = Client(enforce_csrf_checks=True); client.force_login(actor)
        session = client.session; session[SESSION_GENERATION_KEY] = actor.generation; session.save()
        return client

    def _post(self, client: Client, path: str, data, *, csrf: str | None = None):
        headers = {"HTTP_X_CSRFTOKEN": csrf} if csrf is not None else {}
        return client.post(
            path,
            urlencode(data, doseq=True),
            content_type="application/x-www-form-urlencoded",
            **headers,
        )

    def test_owner_and_employee_read_private_escaped_pages_but_employee_has_no_delete(self) -> None:
        for actor in (self.owner, self.employee):
            client = self._login(actor)
            listing = client.get("/manage/requests/")
            self.assertEqual((listing.status_code, listing["Cache-Control"]), (200, "private, no-store"))
            self.assertContains(listing, "&lt;Иван&gt;")
            detail = client.get(f"/manage/requests/{self.row.id}/")
            self.assertEqual((detail.status_code, detail["Cache-Control"]), (200, "private, no-store"))
            self.assertContains(detail, "&lt;script&gt;PRIVATE-COMMENT&lt;/script&gt;")
            if actor.role == StaffRole.OWNER:
                self.assertContains(detail, "Удалить заявку")
            else:
                self.assertNotContains(detail, "confirmation")
                token = client.cookies["csrftoken"].value
                denied = self._post(
                    client,
                    f"/manage/requests/{self.row.id}/delete/",
                    {"confirmation": "employee-denied-before-parse"},
                    csrf=token,
                )
                self.assertEqual((denied.status_code, denied.content), (403, b"FORBIDDEN"))
                self.assertTrue(ServiceRequest.objects.filter(pk=self.row.id).exists())
                self.assertFalse(ServiceRequestDeletionProjection.objects.exists())

    def test_owner_delete_requires_csrf_and_exact_signed_confirmation(self) -> None:
        client = self._login(self.owner)
        detail = client.get(f"/manage/requests/{self.row.id}/")
        confirmation = detail.context["delete_confirmation"]
        no_csrf = self._post(
            client,
            f"/manage/requests/{self.row.id}/delete/",
            {"confirmation": confirmation},
        )
        self.assertEqual(no_csrf.status_code, 403)
        token = client.cookies["csrftoken"].value
        tampered = self._post(client, f"/manage/requests/{self.row.id}/delete/",
            {"confirmation": confirmation + "x"}, csrf=token)
        self.assertEqual((tampered.status_code, tampered.content), (400, b"INVALID_DELETE_CONFIRMATION"))
        self.assertTrue(ServiceRequest.objects.filter(pk=self.row.id).exists())
        accepted = self._post(client, f"/manage/requests/{self.row.id}/delete/",
            {"confirmation": confirmation}, csrf=token)
        self.assertEqual((accepted.status_code, accepted["Location"]), (302, "/manage/requests/"))
        self.assertFalse(ServiceRequest.objects.filter(pk=self.row.id).exists())
        self.assertEqual(ServiceRequestDeletionProjection.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action=Action.SERVICE_REQUEST_DELETED).count(), 1)

    def test_confirmation_binding_wire_and_body_cap_fail_closed(self) -> None:
        client = self._login(self.owner)
        detail = client.get(f"/manage/requests/{self.row.id}/")
        confirmation = detail.context["delete_confirmation"]
        token = client.cookies["csrftoken"].value
        from modules.service_requests.web import _confirmation
        for data in (
            {"confirmation": _confirmation(uuid.uuid4(), self.row.created_at)},
            {"confirmation": confirmation, "extra": "PRIVATE"},
        ):
            response = self._post(
                client, f"/manage/requests/{self.row.id}/delete/", data, csrf=token
            )
            self.assertEqual(response.status_code, 400)
        duplicate = client.post(f"/manage/requests/{self.row.id}/delete/",
            "confirmation=a&confirmation=b", content_type="application/x-www-form-urlencoded",
            HTTP_X_CSRFTOKEN=token)
        self.assertEqual(duplicate.status_code, 400)
        oversized = client.post(f"/manage/requests/{self.row.id}/delete/", b"x",
            content_type="application/x-www-form-urlencoded", CONTENT_LENGTH="2049",
            HTTP_X_CSRFTOKEN=token)
        self.assertEqual((oversized.status_code, oversized.content),
                         (400, b"INVALID_DELETE_CONFIRMATION"))
        self.assertTrue(ServiceRequest.objects.filter(pk=self.row.id).exists())
        self.assertFalse(ServiceRequestDeletionProjection.objects.exists())

    def test_expired_stale_and_method_errors_are_private(self) -> None:
        client = self._login(self.owner)
        detail = client.get(f"/manage/requests/{self.row.id}/")
        confirmation = detail.context["delete_confirmation"]
        token = client.cookies["csrftoken"].value
        with patch("modules.service_requests.web._SIGNER.unsign",
                   side_effect=signing.SignatureExpired):
            expired = self._post(client, f"/manage/requests/{self.row.id}/delete/",
                {"confirmation": confirmation}, csrf=token)
        self.assertEqual(expired.status_code, 400)
        ServiceRequest.objects.filter(pk=self.row.id).update(created_at=timezone.now())
        stale = self._post(client, f"/manage/requests/{self.row.id}/delete/",
            {"confirmation": confirmation}, csrf=token)
        self.assertEqual((stale.status_code, stale.content), (409, b"DELETE_CONFLICT"))
        for method in ("get", "put", "patch"):
            headers = {"HTTP_X_CSRFTOKEN": token} if method != "get" else {}
            response = getattr(client, method)(
                f"/manage/requests/{self.row.id}/delete/",
                data="",
                content_type="application/x-www-form-urlencoded",
                **headers,
            )
            self.assertEqual(response.status_code, 405)
            self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_anonymous_and_missing_authority_disclose_nothing(self) -> None:
        anonymous = Client().get("/manage/requests/")
        self.assertEqual((anonymous.status_code, anonymous["Location"]), (302, "/manage/login/"))
        with patch("modules.service_requests.web._request_authority", return_value=None):
            closed = self._login(self.owner).get("/manage/requests/")
        self.assertEqual((closed.status_code, closed.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
        self.assertNotContains(closed, "PRIVATE-COMMENT", status_code=503)
