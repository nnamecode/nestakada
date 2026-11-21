from __future__ import annotations

import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import Client, TransactionTestCase

from modules.accounts.api import SESSION_GENERATION_KEY
from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent

from ..commands import move_page
from ..models import Page, PageGrant, PageKind, SiteSettings
from .test_publication import PASSWORD, PublicationFixture


class PageMoveHttpTests(PublicationFixture, TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        self.owner, self.settings, self.page = self.make_fixture()
        self.employee = User.objects.create_user(
            username="editor-move-http", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        self.other = Page.objects.create(
            name="Other <page>", kind=PageKind.ARTICLE, position=2
        )
        self.path = f"/manage/pages/{self.page.id}/move/"

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

    def test_access_editor_link_and_owner_form_slots_are_exact(self) -> None:
        anonymous = Client().get(self.path)
        self.assertEqual((anonymous.status_code, anonymous["Location"]), (302, "/manage/login/"))
        employee = self._login(self.employee)
        with patch("modules.pages.web.SiteSettings.objects.select_for_update") as settings_lock:
            denied = employee.get(self.path)
        self.assertEqual((denied.status_code, denied.content), (403, b"FORBIDDEN"))
        settings_lock.assert_not_called()
        employee.cookies["csrftoken"] = "a" * 32
        with patch("modules.pages.web.move_page") as command:
            denied_post = self._post(employee, {
                "csrfmiddlewaretoken": "a" * 32,
                "base_structure_generation": "1", "placement": "root|end",
            })
        self.assertEqual((denied_post.status_code, denied_post.content), (403, b"FORBIDDEN"))
        command.assert_not_called()
        PageGrant.objects.create(staff=self.employee, page=self.page, groups=["text"])
        self.assertNotContains(employee.get(f"/manage/pages/{self.page.id}/"), self.path)
        owner = self._login(self.owner)
        form, token = self._form(owner)
        self.assertEqual(form.status_code, 200)
        self.assertContains(form, 'name="base_structure_generation" value="1"')
        self.assertContains(form, 'select name="placement" required')
        self.assertContains(form, "Other &lt;page&gt;")
        self.assertNotContains(form, f"root|{self.page.id}")
        self.assertContains(owner.get(f"/manage/pages/{self.page.id}/"), self.path)
        self.assertEqual(form["Cache-Control"], "private, no-store")

    def test_success_conflict_unknown_and_unavailable_are_fixed(self) -> None:
        client = self._login(self.owner)
        form, token = self._form(client)
        success = self._post(client, {
            "csrfmiddlewaretoken": token,
            "base_structure_generation": "1", "placement": "root|end",
        })
        self.assertRedirects(success, f"/manage/pages/{self.page.id}/", fetch_redirect_response=False)
        self.assertEqual(Page.objects.get(pk=self.page.id).position, 1)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_MOVED).count(), 1)
        conflict = self._post(client, {
            "csrfmiddlewaretoken": token,
            "base_structure_generation": "1", "placement": "root|end",
        })
        self.assertEqual(conflict.status_code, 409)
        exact_reload = f'<a href="{self.path}">Перезагрузить состояние</a>'.encode()
        self.assertEqual(conflict.content.count(exact_reload), 1)
        self.assertEqual(conflict.content.count(self.path.encode()), 1)
        unknown = client.get(f"/manage/pages/{uuid.uuid4()}/move/")
        self.assertEqual((unknown.status_code, unknown.content), (404, b"PAGE_NOT_FOUND"))
        SiteSettings.objects.all().delete()
        unavailable = client.get(self.path)
        self.assertEqual((unavailable.status_code, unavailable.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))

    def test_closed_wire_csrf_body_cap_and_method_contract(self) -> None:
        client = self._login(self.owner)
        form, token = self._form(client)
        with patch("modules.pages.web.move_page") as command:
            missing = self._post(client, {"base_structure_generation": "1", "placement": "root|end"})
            invalid_csrf = client.post(
                self.path,
                data=urlencode({
                    "csrfmiddlewaretoken": "b" * 32,
                    "base_structure_generation": "1", "placement": "root|end",
                }),
                content_type="application/x-www-form-urlencoded",
                HTTP_X_CSRFTOKEN="b" * 32,
            )
        self.assertEqual((missing.status_code, invalid_csrf.status_code), (403, 403))
        command.assert_not_called()
        upper = str(self.other.id).upper()
        invalid = (
            {"csrfmiddlewaretoken": token, "base_structure_generation": "01", "placement": "root|end"},
            {"csrfmiddlewaretoken": token, "base_structure_generation": "1", "placement": f"root|{upper}"},
            {"csrfmiddlewaretoken": token, "base_structure_generation": "1", "placement": "root|bad"},
            {"csrfmiddlewaretoken": token, "base_structure_generation": ["1", "1"], "placement": "root|end"},
            {"csrfmiddlewaretoken": token, "base_structure_generation": "1", "placement": ["root|end", "root|end"]},
            {"csrfmiddlewaretoken": token, "base_structure_generation": "1", "placement": "root|end", "x": "1"},
        )
        for data in invalid:
            with self.subTest(data=data), patch("modules.pages.web.move_page") as command:
                response = self._post(client, data)
                self.assertEqual((response.status_code, response.content), (400, b"INVALID_PAGE_MOVE_INPUT"))
                command.assert_not_called()
        with patch("modules.pages.web.move_page") as command:
            multipart = client.post(self.path, {
                "csrfmiddlewaretoken": token, "base_structure_generation": "1", "placement": "root|end",
            })
            uploaded = client.post(self.path, {
                "csrfmiddlewaretoken": token, "base_structure_generation": "1", "placement": "root|end",
                "file": SimpleUploadedFile("x.txt", b"x"),
            })
            capped = client.post(
                self.path, data=b"x", content_type="application/x-www-form-urlencoded",
                CONTENT_LENGTH="4194305", HTTP_X_CSRFTOKEN=token,
            )
            put = client.put(
                self.path, data=b"", content_type="application/x-www-form-urlencoded",
                HTTP_X_CSRFTOKEN=token,
            )
        for response in (multipart, uploaded, capped):
            self.assertEqual((response.status_code, response.content), (400, b"INVALID_PAGE_MOVE_INPUT"))
        self.assertEqual((put.status_code, put["Allow"]), (405, "GET, POST"))
        command.assert_not_called()

    def test_coherent_graph_cap_corruption_stale_session_and_fault_are_private(self) -> None:
        owner = self._login(self.owner)
        form, token = self._form(owner)
        session = owner.session; session[SESSION_GENERATION_KEY] = 999; session.save()
        with patch("modules.pages.web.move_page") as command:
            stale = self._post(owner, {
                "csrfmiddlewaretoken": token,
                "base_structure_generation": "1", "placement": "root|end",
            })
        self.assertEqual((stale.status_code, stale["Location"]), (302, "/manage/login/"))
        command.assert_not_called()
        owner = self._login(self.owner); form, token = self._form(owner)
        with patch("modules.pages.web.move_page", side_effect=RuntimeError("Secret placement")):
            fault = self._post(owner, {
                "csrfmiddlewaretoken": token,
                "base_structure_generation": "1", "placement": "root|end",
            })
        self.assertEqual((fault.status_code, fault.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
        self.assertNotContains(fault, "Secret", status_code=503)

        concurrent_client = self._login(self.owner)
        pages_read = threading.Event()
        release_get = threading.Event()
        move_started = threading.Event()

        def run_get():
            close_old_connections()
            intercepted = False

            def fence(execute, sql, params, many, context):
                nonlocal intercepted
                result = execute(sql, params, many, context)
                if not intercepted and 'from "pages_page"' in sql.lower():
                    intercepted = True
                    pages_read.set()
                    if not release_get.wait(timeout=5):
                        raise RuntimeError("move-form-release-timeout")
                return result

            try:
                with connection.execute_wrapper(fence):
                    return concurrent_client.get(self.path)
            finally:
                close_old_connections()

        def run_move():
            close_old_connections()
            move_started.set()
            try:
                return move_page(
                    actor_id=self.owner.id, session_generation=1,
                    page_id=self.page.id, base_structure_generation=1,
                    destination_parent_id=self.other.id, before_page_id=None,
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            get_future = pool.submit(run_get)
            self.assertTrue(pages_read.wait(timeout=5))
            move_future = pool.submit(run_move)
            self.assertTrue(move_started.wait(timeout=5))
            self.assertFalse(move_future.done())
            release_get.set()
            old_form = get_future.result(timeout=10)
            move_result = move_future.result(timeout=10)
        self.assertEqual(old_form.status_code, 200)
        self.assertContains(old_form, 'name="base_structure_generation" value="1"')
        self.assertContains(old_form, f'value="root|{self.other.id}"')
        self.assertEqual(move_result.structure_generation, 2)
        new_form = concurrent_client.get(self.path)
        self.assertContains(new_form, 'name="base_structure_generation" value="2"')

        missing_parent_graph = list(Page.objects.order_by("id"))
        missing_parent_graph[0].parent_id = uuid.uuid4()
        with patch(
            "modules.pages.web.Page.objects.order_by",
            return_value=missing_parent_graph,
        ):
            missing_parent = concurrent_client.get(self.path)
        self.assertEqual(
            (missing_parent.status_code, missing_parent.content),
            (503, b"PRIVATE_DATA_UNAVAILABLE"),
        )
        cycle_graph = list(Page.objects.order_by("id"))
        cycle_by_id = {page.id: page for page in cycle_graph}
        cycle_by_id[self.page.id].parent_id = self.other.id
        cycle_by_id[self.other.id].parent_id = self.page.id
        with patch(
            "modules.pages.web.Page.objects.order_by",
            return_value=cycle_graph,
        ):
            cycle = concurrent_client.get(self.path)
        self.assertEqual((cycle.status_code, cycle.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))

        Page.objects.bulk_create([
            Page(name=f"Cap {index}", kind=PageKind.ARTICLE, position=index + 3)
            for index in range(510)
        ])
        accepted = concurrent_client.get(self.path)
        self.assertEqual(accepted.status_code, 200)
        Page.objects.create(name="Cap overflow", kind=PageKind.ARTICLE, position=513)
        overflow = concurrent_client.get(self.path)
        self.assertEqual((overflow.status_code, overflow.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
