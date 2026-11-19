from __future__ import annotations

from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from modules.accounts.api import SESSION_GENERATION_KEY, StaffRole, User

from ..models import Page, PageContent, PageGrant, PageKind, Route, RouteMode


class AuthorizedPageListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="nesadmin",
            password="owner-password",
            role=StaffRole.OWNER,
        )
        cls.employee = User.objects.create_user(
            username="editor",
            password="employee-password",
            role=StaffRole.EMPLOYEE,
        )
        cls.first = cls._page("Первая", "/first/", 1)
        cls.second = cls._page("Вторая", "/second/", 2)
        PageGrant.objects.create(staff=cls.employee, page=cls.second, groups=["text"])

    @classmethod
    def _page(cls, name: str, target: str, position: int) -> Page:
        page = Page.objects.create(
            name=name,
            kind=PageKind.LEGACY_EMPTY_MAIN,
            position=position,
            is_published=True,
        )
        Route.objects.create(
            page=page,
            target=target,
            mode=RouteMode.PRIMARY,
            outcome=PageKind.LEGACY_EMPTY_MAIN,
        )
        PageContent.objects.create(
            page=page,
            generation=position,
            current_payload={"private_marker": f"payload-{position}"},
            current_hash=str(position) * 64,
            current_author=cls.owner,
            current_created_at=timezone.now(),
        )
        return page

    def _login(self, actor: User) -> Client:
        client = Client(enforce_csrf_checks=True)
        client.force_login(actor)
        session = client.session
        session[SESSION_GENERATION_KEY] = actor.generation
        session.save()
        return client

    def test_owner_sees_all_rows_without_payload_or_hash(self):
        response = self._login(self.owner).get("/manage/pages/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Первая")
        self.assertContains(response, "Вторая")
        self.assertContains(response, "/first/")
        self.assertContains(response, "all", count=2)
        self.assertNotContains(response, "private_marker")
        self.assertNotContains(response, "1" * 64)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_employee_sees_only_exact_granted_page_and_groups(self):
        response = self._login(self.employee).get("/manage/pages/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Первая")
        self.assertContains(response, "Вторая")
        self.assertContains(response, "text")
        self.assertNotContains(response, "payload-2")

    def test_generation_drift_flushes_before_page_query(self):
        client = self._login(self.employee)
        User.objects.filter(pk=self.employee.pk).update(generation=self.employee.generation + 1)
        with CaptureQueriesContext(connection) as queries:
            response = client.get("/manage/pages/")
        self.assertFalse(any('"pages_page"' in query["sql"] for query in queries))
        self.assertRedirects(response, "/manage/login/", fetch_redirect_response=False)
        self.assertNotContains(response, "Вторая", status_code=302)
        self.assertNotIn("_auth_user_id", client.session)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_inactive_user_flushes_before_page_query(self):
        client = self._login(self.employee)
        User.objects.filter(pk=self.employee.pk).update(is_active=False)
        with CaptureQueriesContext(connection) as queries:
            response = client.get("/manage/pages/")
        self.assertFalse(any('"pages_page"' in query["sql"] for query in queries))
        self.assertRedirects(response, "/manage/login/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", client.session)
        self.assertNotIn(SESSION_GENERATION_KEY, client.session)

    def test_password_drift_flushes_before_page_query(self):
        client = self._login(self.employee)
        User.objects.filter(pk=self.employee.pk).update(password="changed-outside-session")
        with CaptureQueriesContext(connection) as queries:
            response = client.get("/manage/pages/")
        self.assertFalse(any('"pages_page"' in query["sql"] for query in queries))
        self.assertRedirects(response, "/manage/login/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", client.session)

    def test_anonymous_redirect_is_private_and_contains_no_page_data(self):
        response = Client().get("/manage/pages/")
        self.assertRedirects(response, "/manage/login/", fetch_redirect_response=False)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertNotContains(response, "Первая", status_code=302)

    def test_incomplete_composition_fails_without_partial_rows(self):
        PageContent.objects.filter(page=self.second).delete()
        response = self._login(self.owner).get("/manage/pages/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b"PRIVATE_DATA_UNAVAILABLE")
        self.assertNotContains(response, "Первая", status_code=503)
        self.assertNotContains(response, "Вторая", status_code=503)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_missing_primary_route_fails_without_partial_rows(self):
        Route.objects.filter(page=self.second, mode=RouteMode.PRIMARY).delete()
        response = self._login(self.owner).get("/manage/pages/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b"PRIVATE_DATA_UNAVAILABLE")
        self.assertNotContains(response, "Первая", status_code=503)
        self.assertNotContains(response, "Вторая", status_code=503)

    def test_pages_endpoint_is_get_only_and_private(self):
        client = self._login(self.owner)
        get_response = client.get("/manage/pages/")
        self.assertEqual(get_response.status_code, 200)
        token = client.cookies["csrftoken"].value
        response = client.post("/manage/pages/", {"csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Cache-Control"], "private, no-store")
