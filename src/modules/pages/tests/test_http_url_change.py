from __future__ import annotations

from urllib.parse import urlencode
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from modules.accounts.api import SESSION_GENERATION_KEY
from modules.accounts.models import StaffRole, User

from ..models import Page, Route, RouteMode
from .test_publication import PASSWORD, PublicationFixture


class PageUrlChangeHttpTests(PublicationFixture, TestCase):
    def setUp(self) -> None:
        self.owner, self.settings, self.page = self.make_fixture()
        self.page.primary_url_mutable = True
        self.page.save(update_fields=("primary_url_mutable",))
        self.employee = User.objects.create_user(
            username="url-editor", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        self.path = f"/manage/pages/{self.page.id}/url/"

    def _login(self, actor: User) -> Client:
        client = Client(enforce_csrf_checks=True); client.force_login(actor)
        session = client.session; session[SESSION_GENERATION_KEY] = actor.generation; session.save()
        return client

    def _form(self, client: Client):
        response = client.get(self.path)
        return response, response.cookies["csrftoken"].value

    def _post(self, client: Client, data):
        return client.post(self.path, data=urlencode(data, doseq=True),
                           content_type="application/x-www-form-urlencoded")

    def test_access_owner_link_and_legacy_visibility_are_closed(self):
        anonymous = Client().get(self.path)
        self.assertEqual((anonymous.status_code, anonymous["Location"]), (302, "/manage/login/"))
        employee = self._login(self.employee)
        with patch("modules.pages.web.SiteSettings.objects.select_for_update") as query:
            denied = employee.get(self.path)
        self.assertEqual((denied.status_code, denied.content), (403, b"FORBIDDEN")); query.assert_not_called()
        employee.cookies["csrftoken"] = "a" * 32
        with (
            patch("modules.pages.web.SiteSettings.objects.select_for_update") as query,
            patch("modules.pages.web.change_primary_url") as command,
        ):
            denied_post = self._post(employee, {"csrfmiddlewaretoken": "a" * 32,
                "base_structure_generation": "1", "new_path": "/employee-secret/"})
        self.assertEqual((denied_post.status_code, denied_post.content), (403, b"FORBIDDEN"))
        query.assert_not_called(); command.assert_not_called()
        owner = self._login(self.owner)
        self.assertContains(owner.get(f"/manage/pages/{self.page.id}/"), self.path)
        self.page.primary_url_mutable = False; self.page.save(update_fields=("primary_url_mutable",))
        self.assertNotContains(owner.get(f"/manage/pages/{self.page.id}/"), self.path)
        protected = owner.get(self.path)
        self.assertEqual((protected.status_code, protected.content), (403, b"LEGACY_URL_PROTECTED"))

    def test_success_conflicts_unknown_and_unavailable_are_fixed(self):
        client = self._login(self.owner); response, token = self._form(client)
        self.assertContains(response, 'name="new_path" maxlength="2048" required value="/article/"')
        success = self._post(client, {"csrfmiddlewaretoken": token,
            "base_structure_generation": "1", "new_path": "/changed/"})
        self.assertRedirects(success, f"/manage/pages/{self.page.id}/", fetch_redirect_response=False)
        for basis, path in (("1", "/stale/"), ("2", "/changed/")):
            conflict = self._post(client, {"csrfmiddlewaretoken": token,
                "base_structure_generation": basis, "new_path": path})
            self.assertEqual(conflict.status_code, 409); self.assertNotContains(conflict, path, status_code=409)
        other = Page.objects.create(name="Occupied", kind=self.page.kind, position=2)
        Route.objects.create(page=other, target="/occupied-http/", mode=RouteMode.PRIMARY,
                             outcome=other.kind)
        occupied = self._post(client, {"csrfmiddlewaretoken": token,
            "base_structure_generation": "2", "new_path": "/occupied-http/"})
        self.assertEqual(occupied.status_code, 409)
        self.assertNotContains(occupied, "/occupied-http/", status_code=409)
        unknown = client.get(f"/manage/pages/00000000-0000-4000-8000-000000000999/url/")
        self.assertEqual((unknown.status_code, unknown.content), (404, b"PAGE_NOT_FOUND"))
        Route.objects.bulk_create([Route(page=self.page, target=f"/cap-{i}/",
            mode=RouteMode.REDIRECT, outcome=self.page.kind) for i in range(510)])
        self.assertEqual(client.get(self.path).status_code, 503)

    def test_wire_csrf_body_cap_and_put_are_closed(self):
        client = self._login(self.owner); response, token = self._form(client)
        self.assertEqual(self._post(client, {"base_structure_generation": "1", "new_path": "/x/"}).status_code, 403)
        invalid_csrf = client.post(
            self.path,
            data=urlencode({"csrfmiddlewaretoken": "b" * 32,
                "base_structure_generation": "1", "new_path": "/x/"}),
            content_type="application/x-www-form-urlencoded",
            HTTP_X_CSRFTOKEN="b" * 32,
        )
        self.assertEqual(invalid_csrf.status_code, 403)
        invalid = (
            {"csrfmiddlewaretoken": token, "base_structure_generation": "01", "new_path": "/x/"},
            {"csrfmiddlewaretoken": token, "base_structure_generation": "1", "new_path": ["/x/", "/y/"]},
            {"csrfmiddlewaretoken": token, "base_structure_generation": "1", "new_path": "/x/", "x": "1"},
        )
        for data in invalid:
            result = self._post(client, data)
            self.assertEqual((result.status_code, result.content), (400, b"INVALID_PAGE_URL_INPUT"))
        duplicate_csrf = client.post(
            self.path,
            data=urlencode({"csrfmiddlewaretoken": [token, token],
                "base_structure_generation": "1", "new_path": "/x/"}, doseq=True),
            content_type="application/x-www-form-urlencoded",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual((duplicate_csrf.status_code, duplicate_csrf.content),
                         (400, b"INVALID_PAGE_URL_INPUT"))
        json_response = client.post(
            self.path, data='{"new_path":"/x/"}', content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual((json_response.status_code, json_response.content),
                         (400, b"INVALID_PAGE_URL_INPUT"))
        uploaded = client.post(self.path, {"csrfmiddlewaretoken": token,
            "base_structure_generation": "1", "new_path": "/x/",
            "file": SimpleUploadedFile("x", b"x")})
        self.assertEqual(uploaded.status_code, 400)
        capped = client.post(self.path, data=b"x", content_type="application/x-www-form-urlencoded",
            CONTENT_LENGTH="4194305", HTTP_X_CSRFTOKEN=token)
        self.assertEqual((capped.status_code, capped.content), (400, b"INVALID_PAGE_URL_INPUT"))
        put = client.put(self.path, data=b"", content_type="application/x-www-form-urlencoded",
                         HTTP_X_CSRFTOKEN=token)
        self.assertEqual((put.status_code, put["Allow"]), (405, "GET, POST"))

    def test_stale_session_and_fault_are_private_and_do_not_reflect_path(self):
        client = self._login(self.owner); response, token = self._form(client)
        session = client.session; session[SESSION_GENERATION_KEY] = 999; session.save()
        stale = self._post(client, {"csrfmiddlewaretoken": token,
            "base_structure_generation": "1", "new_path": "/secret/"})
        self.assertEqual((stale.status_code, stale["Location"]), (302, "/manage/login/"))
        client = self._login(self.owner); response, token = self._form(client)
        with patch("modules.pages.web.change_primary_url", side_effect=RuntimeError("/secret/")):
            fault = self._post(client, {"csrfmiddlewaretoken": token,
                "base_structure_generation": "1", "new_path": "/secret/"})
        self.assertEqual((fault.status_code, fault.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
        self.assertNotContains(fault, "/secret/", status_code=503)
        self.assertEqual(fault["Cache-Control"], "private, no-store")
