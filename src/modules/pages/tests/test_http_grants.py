from __future__ import annotations

from django.test import Client, TestCase

from modules.accounts.api import SESSION_GENERATION_KEY, StaffRole, User
from modules.audit.models import Action, AuditEvent

from ..grants import grant_state_hash
from ..models import Page, PageGrant, PageKind, Route, RouteMode


class PageGrantHttpTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner = User.objects.create_user(
            username="nesadmin", password="owner-password", role=StaffRole.OWNER
        )
        cls.employee = User.objects.create_user(
            username="editor", password="employee-password", role=StaffRole.EMPLOYEE
        )
        cls.other = User.objects.create_user(
            username="other", password="other-password", role=StaffRole.EMPLOYEE
        )
        cls.service = cls._page("Service", PageKind.SERVICE_DETAIL, "/service/", 1)
        cls.article = cls._page("Article", PageKind.ARTICLE, "/article/", 2)
        cls.read_only = cls._page("Read only", PageKind.LEGACY_EMPTY_MAIN, "/read-only/", 3)

    @classmethod
    def _page(cls, name: str, kind: str, target: str, position: int) -> Page:
        page = Page.objects.create(name=name, kind=kind, position=position)
        Route.objects.create(page=page, target=target, mode=RouteMode.PRIMARY, outcome=kind)
        return page

    def _login(self, actor: User) -> Client:
        client = Client(enforce_csrf_checks=True)
        client.force_login(actor)
        session = client.session
        session[SESSION_GENERATION_KEY] = actor.generation
        session.save()
        return client

    def _form(self, client: Client, page: Page | None = None):
        return client.get(f"/manage/grants/{self.employee.id}/{(page or self.service).id}/")

    def test_anonymous_and_employee_cannot_read_private_projection(self) -> None:
        anonymous = Client().get("/manage/grants/")
        self.assertEqual(anonymous.status_code, 302)
        self.assertNotContains(anonymous, "editor", status_code=302)
        employee = self._login(self.employee).get("/manage/grants/")
        self.assertEqual(employee.status_code, 403)
        self.assertNotContains(employee, "other", status_code=403)
        self.assertEqual(employee["Cache-Control"], "private, no-store")

    def test_owner_staff_and_page_lists_are_bounded_and_eligible_only(self) -> None:
        client = self._login(self.owner)
        staff = client.get("/manage/grants/")
        self.assertEqual(staff.status_code, 200)
        self.assertContains(staff, "editor")
        self.assertContains(staff, "other")
        detail = client.get(f"/manage/grants/{self.employee.id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Service")
        self.assertContains(detail, "Article")
        self.assertNotContains(detail, "Read only")
        self.assertNotContains(detail, "/read-only/")
        self.assertNotContains(staff, "owner-password")
        self.assertNotContains(staff, self.employee.password)

    def test_staff_and_page_cap_plus_one_fail_without_partial_projection(self) -> None:
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
        client = self._login(self.owner)
        staff = client.get("/manage/grants/")
        self.assertEqual(staff.status_code, 503)
        self.assertNotContains(staff, "editor", status_code=503)

        pages = [
            Page(
                name=f"Article {index}",
                kind=PageKind.ARTICLE,
                position=index + 10,
            )
            for index in range(499)
        ]
        Page.objects.bulk_create(pages)
        Route.objects.bulk_create([
            Route(
                page=page,
                target=f"/article-extra-{index}/",
                mode=RouteMode.PRIMARY,
                outcome=PageKind.ARTICLE,
            )
            for index, page in enumerate(pages)
        ])
        detail = client.get(f"/manage/grants/{self.employee.id}/")
        self.assertEqual(detail.status_code, 503)
        self.assertNotContains(detail, "Service", status_code=503)

    def test_form_exposes_only_kind_compatible_groups_and_exact_basis(self) -> None:
        client = self._login(self.owner)
        service = self._form(client)
        self.assertEqual(service.status_code, 200)
        self.assertContains(service, 'value="text"')
        self.assertContains(service, 'value="prices"')
        self.assertContains(service, grant_state_hash(self.employee.id, self.service.id, ()))
        article = self._form(client, self.article)
        self.assertContains(article, 'value="text"')
        self.assertNotContains(article, 'value="prices"')

    def test_owner_sets_and_revokes_one_grant_with_csrf(self) -> None:
        client = self._login(self.owner)
        form = self._form(client)
        token = form.cookies["csrftoken"].value
        response = client.post(
            f"/manage/grants/{self.employee.id}/{self.service.id}/",
            {
                "csrfmiddlewaretoken": token,
                "base_user_generation": "1",
                "base_grant_hash": grant_state_hash(self.employee.id, self.service.id, ()),
                "group": ["text", "prices"],
            },
        )
        self.assertRedirects(
            response, f"/manage/grants/{self.employee.id}/", fetch_redirect_response=False
        )
        grant = PageGrant.objects.get(staff=self.employee, page=self.service)
        self.assertEqual(grant.groups, ["text", "prices"])
        self.assertEqual(User.objects.get(pk=self.employee.id).generation, 2)

        form = self._form(client)
        token = form.cookies["csrftoken"].value
        response = client.post(
            f"/manage/grants/{self.employee.id}/{self.service.id}/",
            {
                "csrfmiddlewaretoken": token,
                "base_user_generation": "2",
                "base_grant_hash": grant_state_hash(
                    self.employee.id, self.service.id, ("text", "prices")
                ),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PageGrant.objects.filter(pk=grant.pk).exists())
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_GRANT_REVOKED).count(), 1)

    def test_stale_retry_returns_409_without_second_mutation(self) -> None:
        client = self._login(self.owner)
        form = self._form(client)
        token = form.cookies["csrftoken"].value
        basis = grant_state_hash(self.employee.id, self.service.id, ())
        data = {
            "csrfmiddlewaretoken": token,
            "base_user_generation": "1",
            "base_grant_hash": basis,
            "group": "text",
        }
        self.assertEqual(client.post(form.request["PATH_INFO"], data).status_code, 302)
        stale = client.post(form.request["PATH_INFO"], data)
        self.assertEqual(stale.status_code, 409)
        self.assertContains(stale, "Перезагрузить доступ", status_code=409)
        self.assertEqual(User.objects.get(pk=self.employee.id).generation, 2)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_GRANT_SET).count(), 1)

    def test_wire_csrf_method_and_incomplete_projection_fail_closed(self) -> None:
        client = self._login(self.owner)
        path = f"/manage/grants/{self.employee.id}/{self.service.id}/"
        self.assertEqual(client.post(path, {}).status_code, 403)
        form = client.get(path)
        token = form.cookies["csrftoken"].value
        bad = client.post(
            path,
            {
                "csrfmiddlewaretoken": token,
                "base_user_generation": "1",
                "base_grant_hash": grant_state_hash(self.employee.id, self.service.id, ()),
                "group": "text",
                "unknown": "1",
            },
        )
        self.assertEqual(bad.status_code, 400)
        self.assertFalse(PageGrant.objects.exists())
        Route.objects.filter(page=self.article, mode=RouteMode.PRIMARY).delete()
        broken = client.get(f"/manage/grants/{self.employee.id}/")
        self.assertEqual(broken.status_code, 503)
        self.assertNotContains(broken, "Service", status_code=503)

    def test_committed_grant_invalidates_old_employee_session(self) -> None:
        employee_client = self._login(self.employee)
        owner_client = self._login(self.owner)
        form = self._form(owner_client)
        token = form.cookies["csrftoken"].value
        response = owner_client.post(
            form.request["PATH_INFO"],
            {
                "csrfmiddlewaretoken": token,
                "base_user_generation": "1",
                "base_grant_hash": grant_state_hash(self.employee.id, self.service.id, ()),
                "group": "text",
            },
        )
        self.assertEqual(response.status_code, 302)
        denied = employee_client.get("/manage/pages/")
        self.assertRedirects(denied, "/manage/login/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", employee_client.session)
