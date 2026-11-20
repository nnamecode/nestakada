from __future__ import annotations

from urllib.parse import urlencode
from unittest.mock import patch

from django.test import Client, TestCase

from modules.accounts.api import SESSION_GENERATION_KEY
from modules.accounts.models import StaffRole, User
from modules.media.models import AssetUsage, UsageScope

from ..models import SiteSettings
from .test_site_settings_commands import PASSWORD, SiteSettingsFixture


class SiteSettingsHttpTests(SiteSettingsFixture, TestCase):
    def setUp(self) -> None:
        self.owner, self.settings, self.logo = self.make_fixture()
        self.employee = User.objects.create_user(
            username="editor", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        self.path = "/manage/settings/"

    def login(self, actor: User) -> Client:
        client = Client(enforce_csrf_checks=True)
        client.force_login(actor)
        session = client.session
        session[SESSION_GENERATION_KEY] = actor.generation
        session.save()
        return client

    def form(self, client: Client):
        response = client.get(self.path)
        return response, response.cookies["csrftoken"].value

    def payload(self, token: str, **changes):
        data = {
            "csrfmiddlewaretoken": token,
            "base_settings_generation": "1",
            "organization_name": "Эстакада",
            "phone_display": "+7 499 110-25-52",
            "phone_e164": "+74991102552",
            "address": "Москва",
            "opening_hours": "Ежедневно",
            "contact_email": "owner@example.test",
            "map_url": "https://example.test/map",
            "logo_asset_id": str(self.logo.id),
        }
        data.update(changes)
        return data

    def post(self, client: Client, data):
        return client.post(
            self.path,
            data=urlencode(data, doseq=True),
            content_type="application/x-www-form-urlencoded",
        )

    def test_get_is_owner_editable_employee_read_only_and_anonymous_redirected(self) -> None:
        self.assertEqual(Client().get(self.path).status_code, 302)
        owner = self.login(self.owner).get(self.path)
        self.assertContains(owner, 'name="organization_name"')
        self.assertContains(owner, 'name="logo_asset_id"')
        employee = self.login(self.employee).get(self.path)
        self.assertNotContains(employee, 'name="base_settings_generation"')
        self.assertNotContains(employee, 'name="organization_name"')
        self.assertNotContains(employee, 'name="logo_asset_id"')
        for forbidden in ("legal_name", "max_url", "telegram_url", "storage_key", "sha256"):
            self.assertNotContains(owner, forbidden)
            self.assertNotContains(employee, forbidden)

    def test_owner_post_same_logo_scalar_change_redirects_exactly(self) -> None:
        client = self.login(self.owner)
        _, token = self.form(client)
        response = self.post(client, self.payload(token, organization_name="Новая Эстакада"))
        self.assertRedirects(response, self.path, fetch_redirect_response=False)
        self.assertEqual(SiteSettings.objects.get().organization_name, "Новая Эстакада")

    def test_wire_duplicates_content_type_uuid_and_body_cap_are_400(self) -> None:
        client = self.login(self.owner)
        _, token = self.form(client)
        cases = (
            self.payload(token, base_settings_generation="01"),
            self.payload(token, logo_asset_id=str(self.logo.id).upper()),
            self.payload(token, organization_name=["a", "b"]),
            {**self.payload(token), "unknown": "x"},
        )
        for data in cases:
            with self.subTest(data=data), patch("modules.pages.web.update_site_settings") as command:
                response = self.post(client, data)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.content, b"INVALID_SETTINGS_INPUT")
            self.assertEqual(response["Cache-Control"], "private, no-store")
            command.assert_not_called()
        with patch("modules.pages.web.update_site_settings") as command:
            multipart = client.post(self.path, self.payload(token))
        self.assertEqual(multipart.status_code, 400)
        self.assertEqual(multipart.content, b"INVALID_SETTINGS_INPUT")
        self.assertEqual(multipart["Cache-Control"], "private, no-store")
        command.assert_not_called()
        with patch("modules.pages.web.update_site_settings") as command:
            capped = client.post(
                self.path,
                data=b"x",
                content_type="application/x-www-form-urlencoded",
                CONTENT_LENGTH="4194305",
            )
        self.assertEqual(capped.status_code, 400)
        self.assertEqual(capped.content, b"INVALID_SETTINGS_INPUT")
        self.assertEqual(capped["Cache-Control"], "private, no-store")
        command.assert_not_called()

    def test_conflict_media_csrf_method_and_stale_session_map_exactly(self) -> None:
        client = self.login(self.owner)
        _, token = self.form(client)
        identical = self.post(client, self.payload(token))
        self.assertEqual(identical.status_code, 409)
        self.assertContains(identical, "SETTINGS_CONFLICT", status_code=409)
        self.assertContains(identical, 'href="/manage/settings/"', status_code=409)
        self.assertEqual(identical["Cache-Control"], "private, no-store")
        AssetUsage.objects.filter(scope=UsageScope.SITE_SETTINGS).delete()
        unavailable = client.get(self.path)
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.content, b"PRIVATE_DATA_UNAVAILABLE")
        self.assertEqual(unavailable["Cache-Control"], "private, no-store")
        with patch("modules.pages.web.update_site_settings") as command:
            csrf = self.post(client, {
                key: value
                for key, value in self.payload(token).items()
                if key != "csrfmiddlewaretoken"
            })
        self.assertEqual(csrf.status_code, 403)
        self.assertEqual(csrf["Cache-Control"], "private, no-store")
        command.assert_not_called()
        with patch("modules.pages.web.update_site_settings") as command:
            method = client.put(self.path, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(method.status_code, 405)
        self.assertEqual(method["Allow"], "GET, POST")
        self.assertEqual(method["Cache-Control"], "private, no-store")
        command.assert_not_called()
        session = client.session
        session[SESSION_GENERATION_KEY] = 99
        session.save()
        with patch("modules.pages.web.update_site_settings") as command:
            stale = self.post(client, self.payload(token))
        self.assertEqual(stale.status_code, 302)
        self.assertEqual(stale["Location"], "/manage/login/")
        self.assertEqual(stale["Cache-Control"], "private, no-store")
        command.assert_not_called()

    def test_employee_post_is_403_and_fixed_scope_has_no_gated_fields(self) -> None:
        employee = self.login(self.employee)
        _, token = self.form(employee)
        with patch("modules.pages.web.update_site_settings") as command:
            response = self.post(employee, self.payload(token))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b"FORBIDDEN")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        command.assert_not_called()
        self.assertEqual(SiteSettings.objects.get().settings_generation, 1)
        inspect = __import__("inspect")
        source = inspect.getsource(__import__("modules.pages.web", fromlist=["x"]))
        settings_view = source[source.index("def site_settings_view"):]
        self.assertNotIn('"legal_name"', settings_view)
        self.assertNotIn('"max_url"', settings_view)
        self.assertNotIn('"telegram_url"', settings_view)
        media_source = inspect.getsource(__import__("modules.media.api", fromlist=["x"]))
        self.assertNotIn("modules.pages", media_source)
        projection = media_source[
            media_source.index("def project_site_logo_options"):
            media_source.index("def replace_site_logo_usage")
        ]
        for private_name in ("storage_key", "sha256", "byte_size", "PRIVATE_SOURCE"):
            self.assertNotIn(private_name, projection)
