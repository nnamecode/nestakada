from __future__ import annotations

import uuid
from urllib.parse import urlencode
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from modules.accounts.api import SESSION_GENERATION_KEY
from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent

from ..models import Page, PageGrant, SiteSettings
from .test_publication import PASSWORD, PublicationFixture


class PageRenameHttpTests(PublicationFixture, TestCase):
    def setUp(self) -> None:
        self.owner, self.settings, self.page = self.make_fixture()
        self.employee = User.objects.create_user(
            username="editor", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        self.path = f"/manage/pages/{self.page.id}/rename/"

    def _login(self, actor: User) -> Client:
        client = Client(enforce_csrf_checks=True)
        client.force_login(actor)
        session = client.session
        session[SESSION_GENERATION_KEY] = actor.generation
        session.save()
        return client

    def _form(self, client: Client):
        response = client.get(self.path)
        return response, response.cookies["csrftoken"].value

    def _post(self, client: Client, data: dict[str, object]):
        return client.post(
            self.path, data=urlencode(data, doseq=True),
            content_type="application/x-www-form-urlencoded",
        )

    def test_access_get_and_owner_only_editor_link_are_exact(self) -> None:
        anonymous = Client().get(self.path)
        self.assertEqual((anonymous.status_code, anonymous["Location"]), (302, "/manage/login/"))
        self.assertEqual(anonymous["Cache-Control"], "private, no-store")
        employee = self._login(self.employee)
        with patch("modules.pages.web.SiteSettings.objects.select_for_update") as query:
            denied_get = employee.get(self.path)
        self.assertEqual((denied_get.status_code, denied_get.content), (403, b"FORBIDDEN"))
        self.assertEqual(denied_get["Cache-Control"], "private, no-store")
        query.assert_not_called()
        employee.cookies["csrftoken"] = "a" * 32
        with patch("modules.pages.web.rename_page") as command:
            denied_post = self._post(employee, {
                "csrfmiddlewaretoken": "a" * 32,
                "base_structure_generation": "1", "name": "Employee secret",
            })
        self.assertEqual((denied_post.status_code, denied_post.content), (403, b"FORBIDDEN"))
        self.assertEqual(denied_post["Cache-Control"], "private, no-store")
        command.assert_not_called()
        PageGrant.objects.create(staff=self.employee, page=self.page, groups=["text"])
        self.assertNotContains(employee.get(f"/manage/pages/{self.page.id}/"), self.path)
        owner = self._login(self.owner)
        response, token = self._form(owner)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="base_structure_generation" value="1"')
        self.assertContains(response, 'name="name" maxlength="500" required value="Article"')
        self.assertContains(owner.get(f"/manage/pages/{self.page.id}/"), self.path)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_success_conflict_unknown_and_unavailable_have_fixed_outcomes(self) -> None:
        client = self._login(self.owner)
        response, token = self._form(client)
        success = self._post(client, {
            "csrfmiddlewaretoken": token,
            "base_structure_generation": "1", "name": "Новое имя",
        })
        self.assertRedirects(success, f"/manage/pages/{self.page.id}/", fetch_redirect_response=False)
        self.assertEqual(success["Cache-Control"], "private, no-store")
        self.assertEqual(Page.objects.get(pk=self.page.id).name, "Новое имя")
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_RENAMED).count(), 1)
        for basis, name in (("1", "Again"), ("2", "Новое имя")):
            conflict = self._post(client, {
                "csrfmiddlewaretoken": token, "base_structure_generation": basis, "name": name,
            })
            self.assertEqual(conflict.status_code, 409)
            self.assertNotContains(conflict, name, status_code=409)
            self.assertContains(
                conflict,
                "<h1>Название страницы уже изменилось</h1>",
                status_code=409,
                html=True,
            )
            exact_reload = f'<a href="{self.path}">Перезагрузить состояние</a>'.encode()
            self.assertEqual(conflict.content.count(exact_reload), 1)
            self.assertEqual(conflict.content.count(self.path.encode()), 1)
            self.assertEqual(conflict["Cache-Control"], "private, no-store")
        unknown = client.get(f"/manage/pages/{uuid.uuid4()}/rename/")
        self.assertEqual((unknown.status_code, unknown.content), (404, b"PAGE_NOT_FOUND"))
        self.assertEqual(unknown["Cache-Control"], "private, no-store")
        SiteSettings.objects.all().delete()
        unavailable = client.get(self.path)
        self.assertEqual((unavailable.status_code, unavailable.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
        self.assertEqual(unavailable["Cache-Control"], "private, no-store")

    def test_closed_wire_csrf_body_cap_and_valid_csrf_put(self) -> None:
        client = self._login(self.owner)
        response, token = self._form(client)
        with patch("modules.pages.web.rename_page") as command:
            missing_csrf = self._post(client, {"base_structure_generation": "1", "name": "New"})
            invalid_csrf = client.post(
                self.path,
                data=urlencode({"csrfmiddlewaretoken": "b" * 32, "base_structure_generation": "1", "name": "New"}),
                content_type="application/x-www-form-urlencoded",
                HTTP_X_CSRFTOKEN="b" * 32,
            )
        self.assertEqual((missing_csrf.status_code, invalid_csrf.status_code), (403, 403))
        self.assertEqual(missing_csrf["Cache-Control"], "private, no-store")
        self.assertEqual(invalid_csrf["Cache-Control"], "private, no-store")
        command.assert_not_called()
        invalid = (
            {"csrfmiddlewaretoken": token, "base_structure_generation": "01", "name": "New"},
            {"csrfmiddlewaretoken": token, "base_structure_generation": "1", "name": " New"},
            {"csrfmiddlewaretoken": token, "base_structure_generation": ["1", "1"], "name": "New"},
            {"csrfmiddlewaretoken": token, "base_structure_generation": "1", "name": ["New", "Other"]},
            {"csrfmiddlewaretoken": token, "base_structure_generation": "1", "name": "New", "x": "1"},
        )
        for data in invalid:
            with self.subTest(data=data), patch("modules.pages.web.rename_page") as command:
                invalid_response = self._post(client, data)
                self.assertEqual((invalid_response.status_code, invalid_response.content), (400, b"INVALID_PAGE_RENAME_INPUT"))
                self.assertEqual(invalid_response["Cache-Control"], "private, no-store")
                command.assert_not_called()
        with patch("modules.pages.web.rename_page") as command:
            multipart = client.post(self.path, {
                "csrfmiddlewaretoken": token, "base_structure_generation": "1", "name": "New",
            })
            uploaded = client.post(self.path, {
                "csrfmiddlewaretoken": token, "base_structure_generation": "1", "name": "New",
                "file": SimpleUploadedFile("x.txt", b"x"),
            })
        for invalid_response in (multipart, uploaded):
            self.assertEqual((invalid_response.status_code, invalid_response.content), (400, b"INVALID_PAGE_RENAME_INPUT"))
            self.assertEqual(invalid_response["Cache-Control"], "private, no-store")
        command.assert_not_called()
        with patch("modules.pages.web.rename_page") as command:
            capped = client.post(
                self.path, data=b"x", content_type="application/x-www-form-urlencoded",
                CONTENT_LENGTH="4194305", HTTP_X_CSRFTOKEN=token,
            )
        self.assertEqual((capped.status_code, capped.content), (400, b"INVALID_PAGE_RENAME_INPUT"))
        self.assertEqual(capped["Cache-Control"], "private, no-store")
        command.assert_not_called()
        with patch("modules.pages.web.rename_page") as command:
            put = client.put(self.path, data=b"", content_type="application/x-www-form-urlencoded", HTTP_X_CSRFTOKEN=token)
        self.assertEqual((put.status_code, put["Allow"]), (405, "GET, POST"))
        self.assertEqual(put["Cache-Control"], "private, no-store")
        command.assert_not_called()

    def test_valid_csrf_employee_stale_session_and_fault_do_not_disclose_name(self) -> None:
        owner = self._login(self.owner)
        response, token = self._form(owner)
        session = owner.session; session[SESSION_GENERATION_KEY] = 999; session.save()
        with patch("modules.pages.web.rename_page") as command:
            stale = self._post(owner, {
                "csrfmiddlewaretoken": token, "base_structure_generation": "1", "name": "Secret",
            })
        self.assertEqual((stale.status_code, stale["Location"]), (302, "/manage/login/"))
        self.assertEqual(stale["Cache-Control"], "private, no-store")
        command.assert_not_called()
        owner = self._login(self.owner); response, token = self._form(owner)
        with patch("modules.pages.web.rename_page", side_effect=RuntimeError("Secret")):
            fault = self._post(owner, {
                "csrfmiddlewaretoken": token, "base_structure_generation": "1", "name": "Secret",
            })
        self.assertEqual((fault.status_code, fault.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
        self.assertEqual(fault["Cache-Control"], "private, no-store")
        self.assertNotContains(fault, "Secret", status_code=503)
