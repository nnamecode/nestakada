from __future__ import annotations

from urllib.parse import urlencode
from unittest.mock import patch

from django.test import Client, TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from modules.accounts.api import SESSION_GENERATION_KEY
from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent

from ..commands import PageCommandError
from ..models import Page, PageGrant, PageKind
from .test_publication import PASSWORD, PublicationFixture


class PageDeleteHttpTests(PublicationFixture, TestCase):
    def setUp(self):
        self.owner, self.settings, self.page = self.make_fixture()
        self.employee = User.objects.create_user(username="delete-http", password=PASSWORD, role=StaffRole.EMPLOYEE)
        self.path = f"/manage/pages/{self.page.id}/delete/"

    def _login(self, actor):
        client = Client(enforce_csrf_checks=True); client.force_login(actor)
        session = client.session; session[SESSION_GENERATION_KEY] = actor.generation; session.save()
        return client

    def _form(self, client):
        response = client.get(self.path)
        return response, response.cookies["csrftoken"].value

    def _data(self, response, token, **changes):
        preview = response.context["preview"]
        values = {
            "csrfmiddlewaretoken": token,
            "base_structure_generation": str(preview.structure_generation),
            "composition_digest": preview.composition_digest,
            "expected_name": preview.name,
            "expected_primary_path": preview.primary_path,
            "current_password": PASSWORD,
            "confirm_delete": "1",
        }
        values.update(changes); return values

    def _post(self, client, data):
        return client.post(self.path, data=urlencode(data, doseq=True), content_type="application/x-www-form-urlencoded")

    def test_access_link_and_preview_are_owner_only(self):
        self.assertEqual(Client().get(self.path).status_code, 302)
        employee = self._login(self.employee)
        with patch("modules.pages.web.load_page_delete_preview") as projection:
            self.assertEqual(employee.get(self.path).status_code, 403)
        projection.assert_not_called()
        employee.cookies["csrftoken"] = "a" * 32
        with patch("modules.pages.web.delete_leaf_page") as command:
            denied = self._post(employee, {"csrfmiddlewaretoken": "a" * 32})
        self.assertEqual(denied.status_code, 403); command.assert_not_called()
        PageGrant.objects.create(staff=self.employee, page=self.page, groups=["text"])
        self.assertNotContains(employee.get(f"/manage/pages/{self.page.id}/"), self.path)
        owner = self._login(self.owner); response, token = self._form(owner)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="composition_digest"')
        self.assertContains(response, "PRIMARY: 1")
        self.assertContains(owner.get(f"/manage/pages/{self.page.id}/"), self.path)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_success_wrong_password_conflict_and_replay(self):
        client = self._login(self.owner); response, token = self._form(client)
        wrong = self._post(client, self._data(response, token, current_password="secret-never-reflect"))
        self.assertEqual((wrong.status_code, wrong.content), (403, b"FORBIDDEN"))
        self.assertNotContains(wrong, "secret-never-reflect", status_code=403)
        with patch("modules.pages.web.delete_leaf_page", side_effect=PageCommandError("GALLERY_DELETE_REQUIRED")):
            gallery_post = self._post(client, self._data(response, token))
        self.assertEqual((gallery_post.status_code, gallery_post.content), (409, b"GALLERY_DELETE_REQUIRED"))
        stale = self._post(client, self._data(response, token, expected_name="changed"))
        self.assertEqual(stale.status_code, 409)
        self.assertNotContains(stale, "changed", status_code=409)
        success = self._post(client, self._data(response, token))
        self.assertEqual((success.status_code, success["Location"]), (302, "/manage/pages/"))
        replay = self._post(client, self._data(response, token))
        self.assertEqual((replay.status_code, replay["Location"]), (302, "/manage/pages/"))
        self.assertFalse(Page.objects.filter(pk=self.page.id).exists())
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_DELETED).count(), 1)

    def test_wire_csrf_cap_and_method_are_closed(self):
        client = self._login(self.owner); response, token = self._form(client)
        self.assertEqual(self._post(client, {k: v for k, v in self._data(response, token).items() if k != "csrfmiddlewaretoken"}).status_code, 403)
        for changes in (
            {"confirm_delete": "0"}, {"base_structure_generation": "01"}, {"x": "1"},
            {"composition_digest": "x" * 64}, {"current_password": ""},
            {"expected_name": "x" * 501}, {"expected_primary_path": "x" * 2049},
            {"expected_name": ["Article", "Article"]},
            {"csrfmiddlewaretoken": [token, token]},
        ):
            data = self._data(response, token); data.update(changes)
            invalid = self._post(client, data)
            self.assertEqual((invalid.status_code, invalid.content), (400, b"INVALID_PAGE_DELETE_INPUT"))
        multipart = client.post(self.path, self._data(response, token))
        self.assertEqual((multipart.status_code, multipart.content), (400, b"INVALID_PAGE_DELETE_INPUT"))
        uploaded = client.post(self.path, {**self._data(response, token), "file": SimpleUploadedFile("x.txt", b"x")})
        self.assertEqual((uploaded.status_code, uploaded.content), (400, b"INVALID_PAGE_DELETE_INPUT"))
        capped = client.post(self.path, data=b"x", content_type="application/x-www-form-urlencoded", CONTENT_LENGTH="4194305", HTTP_X_CSRFTOKEN=token)
        self.assertEqual((capped.status_code, capped.content), (400, b"INVALID_PAGE_DELETE_INPUT"))
        put = client.put(self.path, data=b"", content_type="application/x-www-form-urlencoded", HTTP_X_CSRFTOKEN=token)
        self.assertEqual((put.status_code, put["Allow"]), (405, "GET, POST"))

    def test_unknown_fault_and_private_errors_are_fixed(self):
        client = self._login(self.owner)
        response, token = self._form(client)
        session = client.session; session[SESSION_GENERATION_KEY] = 999; session.save()
        stale_session = self._post(client, self._data(response, token))
        self.assertEqual((stale_session.status_code, stale_session["Location"]), (302, "/manage/login/"))
        client = self._login(self.owner)
        unknown = client.get("/manage/pages/00000000-0000-0000-0000-000000000001/delete/")
        self.assertEqual((unknown.status_code, unknown.content), (404, b"PAGE_NOT_FOUND"))
        self.page.kind = PageKind.GALLERY_ALBUM; self.page.save(update_fields=("kind",))
        gallery = client.get(self.path)
        self.assertEqual((gallery.status_code, gallery.content), (409, b"GALLERY_DELETE_REQUIRED"))
        self.page.kind = PageKind.ARTICLE; self.page.save(update_fields=("kind",))
        with patch("modules.pages.web.load_page_delete_preview", side_effect=RuntimeError("secret")):
            fault = client.get(self.path)
        self.assertEqual((fault.status_code, fault.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
        self.assertNotContains(fault, "secret", status_code=503)
        self.assertEqual(fault["Cache-Control"], "private, no-store")
