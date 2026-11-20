from __future__ import annotations

import uuid
from urllib.parse import urlencode
from unittest.mock import patch

from django.test import Client, TestCase

from modules.accounts.api import SESSION_GENERATION_KEY
from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent

from ..models import Page, PageGrant, PageKind


PASSWORD_A = "Unique!Employee-Alpha-2026"
PASSWORD_B = "Unique!Employee-Beta-2026"


class StaffLifecycleHttpTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner = User.objects.create_user(
            username="nesadmin", password=PASSWORD_A, role=StaffRole.OWNER
        )
        cls.employee = User.objects.create_user(
            username="editor", password=PASSWORD_A, role=StaffRole.EMPLOYEE
        )
        cls.inactive = User.objects.create_user(
            username="inactive", password=PASSWORD_A, role=StaffRole.EMPLOYEE, is_active=False
        )

    def _login(self, actor: User) -> Client:
        client = Client(enforce_csrf_checks=True)
        client.force_login(actor)
        session = client.session
        session[SESSION_GENERATION_KEY] = actor.generation
        session.save()
        return client

    def _post(self, client: Client, path: str, data: dict[str, object]):
        return client.post(
            path,
            data=urlencode(data, doseq=True),
            content_type="application/x-www-form-urlencoded",
        )

    def test_anonymous_and_employee_cannot_read_staff_projection(self) -> None:
        anonymous = Client().get("/manage/staff/")
        self.assertEqual(anonymous.status_code, 302)
        self.assertNotContains(anonymous, "editor", status_code=302)
        denied = self._login(self.employee).get("/manage/staff/")
        self.assertEqual(denied.status_code, 403)
        self.assertNotContains(denied, "inactive", status_code=403)
        self.assertEqual(denied["Cache-Control"], "private, no-store")

    def test_employee_is_denied_each_mutation_endpoint(self) -> None:
        client = self._login(self.employee)
        paths = (
            "/manage/staff/new/",
            f"/manage/staff/{self.employee.id}/password/",
            f"/manage/staff/{self.employee.id}/deactivate/",
            f"/manage/staff/{self.inactive.id}/reactivate/",
        )
        for path in paths:
            response = client.get(path)
            self.assertEqual(response.status_code, 403)
            self.assertNotContains(response, "inactive", status_code=403)
            posted = client.post(path, {})
            self.assertEqual(posted.status_code, 403)
        self.assertFalse(AuditEvent.objects.exists())

    def test_owner_list_is_stable_private_and_bounded(self) -> None:
        client = self._login(self.owner)
        response = client.get("/manage/staff/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "editor")
        self.assertContains(response, "inactive")
        self.assertLess(response.content.index(b"editor"), response.content.index(b"inactive"))
        self.assertNotContains(response, PASSWORD_A)
        extras = [
            User(
                username=f"extra-{index:03d}",
                password="!",
                role=StaffRole.EMPLOYEE,
                is_staff=True,
                is_superuser=False,
            )
            for index in range(99)
        ]
        User.objects.bulk_create(extras)
        capped = client.get("/manage/staff/")
        self.assertEqual(capped.status_code, 503)
        self.assertNotContains(capped, "editor", status_code=503)

    def test_owner_creates_employee_once_and_conflict_is_409(self) -> None:
        client = self._login(self.owner)
        form = client.get("/manage/staff/new/")
        token = form.cookies["csrftoken"].value
        employee_id = str(form.context["employee_id"])
        data = {
            "csrfmiddlewaretoken": token,
            "employee_id": employee_id,
            "username": "new-editor",
            "password": PASSWORD_A,
            "password_confirmation": PASSWORD_A,
        }
        response = self._post(client, "/manage/staff/new/", data)
        self.assertRedirects(response, "/manage/staff/", fetch_redirect_response=False)
        created = User.objects.get(pk=uuid.UUID(employee_id))
        self.assertTrue(created.check_password(PASSWORD_A))
        self.assertEqual(AuditEvent.objects.filter(action=Action.STAFF_CREATED).count(), 1)
        stale = self._post(client, "/manage/staff/new/", data)
        self.assertEqual(stale.status_code, 409)
        self.assertNotContains(stale, PASSWORD_A, status_code=409)
        self.assertEqual(AuditEvent.objects.filter(action=Action.STAFF_CREATED).count(), 1)

    def test_password_change_invalidates_employee_session_and_never_reflects_password(self) -> None:
        employee_client = self._login(self.employee)
        client = self._login(self.owner)
        path = f"/manage/staff/{self.employee.id}/password/"
        form = client.get(path)
        token = form.cookies["csrftoken"].value
        response = self._post(
            client,
            path,
            {
                "csrfmiddlewaretoken": token,
                "base_user_generation": "1",
                "password": PASSWORD_B,
                "password_confirmation": PASSWORD_B,
            },
        )
        self.assertRedirects(response, "/manage/staff/", fetch_redirect_response=False)
        self.assertTrue(User.objects.get(pk=self.employee.id).check_password(PASSWORD_B))
        self.assertNotContains(response, PASSWORD_B, status_code=302)
        denied = employee_client.get("/manage/pages/")
        self.assertRedirects(denied, "/manage/login/", fetch_redirect_response=False)

    def test_deactivate_removes_grants_then_reactivate_restores_none(self) -> None:
        page = Page.objects.create(name="Service", kind=PageKind.SERVICE_DETAIL, position=1)
        PageGrant.objects.create(staff=self.employee, page=page, groups=["text"])
        client = self._login(self.owner)
        deactivate_path = f"/manage/staff/{self.employee.id}/deactivate/"
        form = client.get(deactivate_path)
        self.assertContains(form, "1")
        token = form.cookies["csrftoken"].value
        response = self._post(
            client,
            deactivate_path,
            {
                "csrfmiddlewaretoken": token,
                "base_user_generation": "1",
                "base_grants_digest": form.context["base_grants_digest"],
            },
        )
        self.assertRedirects(response, "/manage/staff/", fetch_redirect_response=False)
        self.assertFalse(User.objects.get(pk=self.employee.id).is_active)
        self.assertFalse(PageGrant.objects.filter(staff=self.employee).exists())
        reactivate_path = f"/manage/staff/{self.employee.id}/reactivate/"
        form = client.get(reactivate_path)
        token = form.cookies["csrftoken"].value
        response = self._post(
            client,
            reactivate_path,
            {"csrfmiddlewaretoken": token, "base_user_generation": "2"},
        )
        self.assertEqual(response.status_code, 302)
        refreshed = User.objects.get(pk=self.employee.id)
        self.assertTrue(refreshed.is_active)
        self.assertEqual(refreshed.generation, 3)
        self.assertFalse(PageGrant.objects.filter(staff=self.employee).exists())

    def test_csrf_unknown_keys_and_stale_basis_fail_closed(self) -> None:
        client = self._login(self.owner)
        path = f"/manage/staff/{self.employee.id}/password/"
        self.assertEqual(client.post(path, {}).status_code, 403)
        form = client.get(path)
        token = form.cookies["csrftoken"].value
        bad = self._post(
            client,
            path,
            {
                "csrfmiddlewaretoken": token,
                "base_user_generation": "1",
                "password": PASSWORD_B,
                "password_confirmation": PASSWORD_B,
                "unknown": "1",
            },
        )
        self.assertEqual(bad.status_code, 400)
        stale = self._post(
            client,
            path,
            {
                "csrfmiddlewaretoken": token,
                "base_user_generation": "2",
                "password": PASSWORD_B,
                "password_confirmation": PASSWORD_B,
            },
        )
        self.assertEqual(stale.status_code, 409)
        self.assertTrue(User.objects.get(pk=self.employee.id).check_password(PASSWORD_A))
        self.assertFalse(AuditEvent.objects.filter(action=Action.AUTH_PASSWORD_CHANGED).exists())

    def test_exact_body_cap_rejects_before_password_validation(self) -> None:
        client = self._login(self.owner)
        path = f"/manage/staff/{self.employee.id}/password/"
        with patch("modules.accounts.staff.validate_password") as validator:
            response = client.post(
                path,
                data=b"x",
                content_type="application/x-www-form-urlencoded",
                CONTENT_LENGTH="4194305",
            )
        self.assertEqual(response.status_code, 400)
        validator.assert_not_called()
        self.assertTrue(User.objects.get(pk=self.employee.id).check_password(PASSWORD_A))
