from __future__ import annotations

import uuid
from urllib.parse import urlencode
from unittest.mock import patch

from django.test import Client, TestCase

from modules.accounts.api import SESSION_GENERATION_KEY
from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent

from ..models import Page, PageGrant, SiteSettings
from .test_publication import PASSWORD, PublicationFixture


class PublicationHttpTests(PublicationFixture, TestCase):
    def setUp(self) -> None:
        self.owner, self.settings, self.page = self.make_fixture()
        self.employee = User.objects.create_user(
            username="editor", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        self.path = f"/manage/pages/{self.page.id}/publication/"

    def _login(self, actor: User) -> Client:
        client = Client(enforce_csrf_checks=True)
        client.force_login(actor)
        session = client.session
        session[SESSION_GENERATION_KEY] = actor.generation
        session.save()
        return client

    def _post(self, client: Client, data: dict[str, object]):
        return client.post(
            self.path,
            data=urlencode(data, doseq=True),
            content_type="application/x-www-form-urlencoded",
        )

    def _form(self, client: Client):
        response = client.get(self.path)
        return response, response.cookies["csrftoken"].value

    def test_anonymous_and_employee_are_denied_without_projection_or_mutation(self) -> None:
        anonymous = Client().get(self.path)
        self.assertEqual(anonymous.status_code, 302)
        employee = self._login(self.employee)
        self.assertEqual(employee.get(self.path).status_code, 403)
        self.assertEqual(employee.post(self.path, {}).status_code, 403)
        self.assertFalse(AuditEvent.objects.exists())

    def test_owner_get_and_editor_expose_only_fixed_publication_control(self) -> None:
        client = self._login(self.owner)
        response, token = self._form(client)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="base_structure_generation" value="1"')
        self.assertContains(response, 'name="desired_published" value="1"')
        self.assertEqual(response["Cache-Control"], "private, no-store")
        editor = client.get(f"/manage/pages/{self.page.id}/")
        self.assertContains(editor, self.path)
        PageGrant.objects.create(staff=self.employee, page=self.page, groups=["text"])
        employee_editor = self._login(self.employee).get(f"/manage/pages/{self.page.id}/")
        self.assertNotContains(employee_editor, self.path)

    def test_owner_publishes_then_hides_through_exact_urlencoded_wire(self) -> None:
        client = self._login(self.owner)
        response, token = self._form(client)
        published = self._post(client, {
            "csrfmiddlewaretoken": token,
            "base_structure_generation": "1",
            "desired_published": "1",
        })
        self.assertRedirects(
            published,
            f"/manage/pages/{self.page.id}/",
            fetch_redirect_response=False,
        )
        self.assertTrue(Page.objects.get(pk=self.page.id).is_published)
        response, token = self._form(client)
        hidden = self._post(client, {
            "csrfmiddlewaretoken": token,
            "base_structure_generation": "2",
            "desired_published": "0",
        })
        self.assertEqual(hidden.status_code, 302)
        self.assertFalse(Page.objects.get(pk=self.page.id).is_published)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_PUBLICATION_CHANGED).count(), 2)

    def test_stale_and_no_change_return_private_conflict(self) -> None:
        client = self._login(self.owner)
        response, token = self._form(client)
        stale = self._post(client, {
            "csrfmiddlewaretoken": token,
            "base_structure_generation": "2",
            "desired_published": "1",
        })
        self.assertEqual(stale.status_code, 409)
        no_change = self._post(client, {
            "csrfmiddlewaretoken": token,
            "base_structure_generation": "1",
            "desired_published": "0",
        })
        self.assertEqual(no_change.status_code, 409)
        self.assertFalse(AuditEvent.objects.exists())

    def test_unknown_duplicate_noncanonical_and_wrong_content_type_are_400(self) -> None:
        client = self._login(self.owner)
        response, token = self._form(client)
        for data in (
            {"csrfmiddlewaretoken": token, "base_structure_generation": "01", "desired_published": "1"},
            {"csrfmiddlewaretoken": token, "base_structure_generation": "1", "desired_published": "true"},
            {"csrfmiddlewaretoken": token, "base_structure_generation": "1", "desired_published": "1", "unknown": "x"},
            {"csrfmiddlewaretoken": token, "base_structure_generation": ["1", "1"], "desired_published": "1"},
        ):
            with self.subTest(data=data):
                self.assertEqual(self._post(client, data).status_code, 400)
        multipart = client.post(self.path, {
            "csrfmiddlewaretoken": token,
            "base_structure_generation": "1",
            "desired_published": "1",
        })
        self.assertEqual(multipart.status_code, 400)

    def test_csrf_and_exact_body_cap_stop_before_command(self) -> None:
        client = self._login(self.owner)
        self.assertEqual(self._post(client, {
            "base_structure_generation": "1", "desired_published": "1",
        }).status_code, 403)
        with patch("modules.pages.web.set_page_publication") as command:
            capped = client.post(
                self.path,
                data=b"x",
                content_type="application/x-www-form-urlencoded",
                CONTENT_LENGTH="4194305",
            )
        self.assertEqual(capped.status_code, 400)
        command.assert_not_called()

    def test_unknown_page_and_missing_settings_fail_without_disclosure(self) -> None:
        client = self._login(self.owner)
        unknown = client.get(f"/manage/pages/{uuid.uuid4()}/publication/")
        self.assertEqual(unknown.status_code, 404)
        SiteSettings.objects.all().delete()
        unavailable = client.get(self.path)
        self.assertEqual(unavailable.status_code, 503)
        self.assertNotContains(unavailable, self.page.name, status_code=503)
