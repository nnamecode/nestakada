from __future__ import annotations

import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.test import Client, TransactionTestCase

from modules.accounts.api import SESSION_GENERATION_KEY
from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent

from ..commands import rename_page
from ..models import Page, PageGrant, PageKind, SiteSettings
from .test_publication import PASSWORD, PublicationFixture


class PageCreateHttpTests(PublicationFixture, TransactionTestCase):
    reset_sequences = True
    path = "/manage/pages/new/"

    def setUp(self) -> None:
        self.owner, self.settings, self.existing = self.make_fixture()
        self.employee = User.objects.create_user(
            username="editor", password=PASSWORD, role=StaffRole.EMPLOYEE
        )

    def _login(self, actor: User) -> Client:
        client = Client(enforce_csrf_checks=True); client.force_login(actor)
        session = client.session; session[SESSION_GENERATION_KEY] = actor.generation; session.save()
        return client

    def _form(self, client: Client):
        response = client.get(self.path)
        match = re.search(rb'name="page_id" value="([0-9a-f-]{36})"', response.content)
        return response, response.cookies["csrftoken"].value, match.group(1).decode()

    def _post(self, client: Client, data):
        return client.post(
            self.path, data=urlencode(data, doseq=True),
            content_type="application/x-www-form-urlencoded",
        )

    def test_access_owner_form_and_owner_only_list_link_are_exact(self) -> None:
        anonymous = Client().get(self.path)
        self.assertEqual((anonymous.status_code, anonymous["Location"]), (302, "/manage/login/"))
        employee = self._login(self.employee)
        with patch("modules.pages.web.SiteSettings.objects.select_for_update") as query:
            denied = employee.get(self.path)
        self.assertEqual((denied.status_code, denied.content), (403, b"FORBIDDEN")); query.assert_not_called()
        PageGrant.objects.create(staff=self.employee, page=self.existing, groups=["text"])
        self.assertNotContains(employee.get("/manage/pages/"), self.path)
        owner = self._login(self.owner)
        response, token, page_id = self._form(owner)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="name" maxlength="255" required')
        self.assertContains(response, 'name="base_structure_generation" value="1"')
        self.assertEqual(len(response.context["kinds"]), 19)
        self.assertContains(owner.get("/manage/pages/"), self.path)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_success_replay_conflicts_and_unavailable_have_closed_outcomes(self) -> None:
        client = self._login(self.owner); response, token, page_id = self._form(client)
        data = {
            "csrfmiddlewaretoken": token, "page_id": page_id,
            "base_structure_generation": "1", "kind": PageKind.ARTICLE,
            "name": "Created", "parent_id": "root", "primary_path": "/created/",
        }
        success = self._post(client, data)
        self.assertRedirects(success, f"/manage/pages/{page_id}/", fetch_redirect_response=False)
        replay = self._post(client, data)
        self.assertRedirects(replay, f"/manage/pages/{page_id}/", fetch_redirect_response=False)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CREATED).count(), 1)
        for changes in (
            {"page_id": str(uuid.uuid4()), "base_structure_generation": "1", "primary_path": "/other/"},
            {"page_id": str(uuid.uuid4()), "base_structure_generation": "2", "primary_path": "/article/"},
            {"page_id": str(uuid.uuid4()), "base_structure_generation": "2", "parent_id": str(uuid.uuid4()), "primary_path": "/other/"},
            {"name": "Mismatch"},
        ):
            conflict = self._post(client, {**data, **changes})
            self.assertEqual(conflict.status_code, 409)
            self.assertEqual(conflict.content.count(self.path.encode()), 1)
            self.assertNotContains(conflict, changes.get("name", "secret"), status_code=409)
        SiteSettings.objects.all().delete()
        unavailable = client.get(self.path)
        self.assertEqual((unavailable.status_code, unavailable.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))

    def test_closed_wire_domain_csrf_body_cap_and_put_matrix(self) -> None:
        client = self._login(self.owner); response, token, page_id = self._form(client)
        base = {
            "csrfmiddlewaretoken": token, "page_id": page_id,
            "base_structure_generation": "1", "kind": PageKind.ARTICLE,
            "name": "Created", "parent_id": "root", "primary_path": "/created/",
        }
        with patch("modules.pages.web.create_page") as command:
            missing = self._post(client, {key: value for key, value in base.items() if key != "csrfmiddlewaretoken"})
        self.assertEqual(missing.status_code, 403); command.assert_not_called()
        invalid = (
            {"page_id": page_id.upper()}, {"base_structure_generation": "01"},
            {"kind": "unknown"}, {"name": "x" * 256},
            {"primary_path": "/%6danage/new/"}, {"parent_id": "bad"},
            {"name": ["One", "Two"]}, {"extra": "x"},
        )
        for changes in invalid:
            with self.subTest(changes=changes), patch("modules.pages.web.create_page") as command:
                result = self._post(client, {**base, **changes})
                self.assertEqual((result.status_code, result.content), (400, b"INVALID_PAGE_CREATE_INPUT"))
                command.assert_not_called()
        with patch("modules.pages.web.create_page") as command:
            multipart = client.post(self.path, base)
            uploaded = client.post(self.path, {**base, "file": SimpleUploadedFile("x", b"x")})
            capped = client.post(
                self.path, data=b"x", content_type="application/x-www-form-urlencoded",
                CONTENT_LENGTH="4194305", HTTP_X_CSRFTOKEN=token,
            )
            put = client.put(self.path, data=b"", HTTP_X_CSRFTOKEN=token)
        self.assertTrue(all(response.status_code == 400 for response in (multipart, uploaded, capped)))
        self.assertEqual((put.status_code, put["Allow"]), (405, "GET, POST")); command.assert_not_called()

    def test_stale_session_employee_post_graph_cap_and_fault_hide_submitted_values(self) -> None:
        employee = self._login(self.employee); employee.cookies["csrftoken"] = "a" * 32
        with patch("modules.pages.web.create_page") as command:
            denied = self._post(employee, {
                "csrfmiddlewaretoken": "a" * 32, "page_id": str(uuid.uuid4()),
                "base_structure_generation": "1", "kind": PageKind.ARTICLE,
                "name": "Employee secret", "parent_id": "root", "primary_path": "/secret/",
            })
        self.assertEqual(denied.status_code, 403); command.assert_not_called()
        owner = self._login(self.owner); response, token, page_id = self._form(owner)
        session = owner.session; session[SESSION_GENERATION_KEY] = 999; session.save()
        stale = self._post(owner, {
            "csrfmiddlewaretoken": token, "page_id": page_id, "base_structure_generation": "1",
            "kind": PageKind.ARTICLE, "name": "Secret", "parent_id": "root", "primary_path": "/secret/",
        })
        self.assertEqual((stale.status_code, stale["Location"]), (302, "/manage/login/"))
        owner = self._login(self.owner); response, token, page_id = self._form(owner)
        with patch("modules.pages.web.create_page", side_effect=RuntimeError("Secret")):
            fault = self._post(owner, {
                "csrfmiddlewaretoken": token, "page_id": page_id, "base_structure_generation": "1",
                "kind": PageKind.ARTICLE, "name": "Secret", "parent_id": "root", "primary_path": "/secret/",
            })
        self.assertEqual((fault.status_code, fault.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
        self.assertNotContains(fault, "Secret", status_code=503)

        coherent_client = self._login(self.owner)
        read_started = threading.Event(); release_read = threading.Event(); writer_done = threading.Event()
        original_order_by = Page.objects.order_by

        def delayed_order_by(*args, **kwargs):
            queryset = original_order_by(*args, **kwargs)
            if threading.current_thread().name.startswith("create-get"):
                read_started.set()
                if not release_read.wait(timeout=10):
                    raise AssertionError("GET graph read was not released")
            return queryset

        def get_worker() -> bytes:
            close_old_connections()
            try:
                response = coherent_client.get(self.path)
                self.assertEqual(response.status_code, 200)
                return response.content
            finally:
                close_old_connections()

        def writer() -> str:
            close_old_connections()
            try:
                result = rename_page(
                    actor_id=self.owner.id, session_generation=1,
                    page_id=self.existing.id, base_structure_generation=1,
                    name="Coherent renamed",
                )
                return result.name
            finally:
                writer_done.set(); close_old_connections()

        with (
            patch.object(Page.objects, "order_by", side_effect=delayed_order_by),
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="create-get") as get_pool,
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="create-writer") as writer_pool,
        ):
            get_future = get_pool.submit(get_worker)
            self.assertTrue(read_started.wait(timeout=10))
            writer_future = writer_pool.submit(writer)
            self.assertFalse(writer_done.wait(timeout=1))
            release_read.set()
            body = get_future.result(timeout=20)
            self.assertEqual(writer_future.result(timeout=20), "Coherent renamed")
        self.assertIn(b'name="base_structure_generation" value="1"', body)
        self.assertIn(f'<option value="{self.existing.id}">Article</option>'.encode(), body)
        self.assertNotIn(b"Coherent renamed", body)

        cycle_a = Page.objects.create(name="Cycle A", kind=PageKind.ARTICLE, position=20)
        cycle_b = Page.objects.create(
            name="Cycle B", kind=PageKind.ARTICLE, parent=cycle_a, position=0
        )
        Page.objects.filter(pk=cycle_a.id).update(parent=cycle_b)
        corrupt = coherent_client.get(self.path)
        self.assertEqual((corrupt.status_code, corrupt.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
        Page.objects.filter(pk=cycle_a.id).update(parent=None)
        cycle_b.delete(); cycle_a.delete()
        Page.objects.bulk_create([
            Page(name=f"Cap {index}", kind=PageKind.ARTICLE, position=index + 100)
            for index in range(511)
        ])
        self.assertEqual(coherent_client.get(self.path).status_code, 200)
        Page.objects.create(name="Cap overflow", kind=PageKind.ARTICLE, position=1000)
        capped = coherent_client.get(self.path)
        self.assertEqual((capped.status_code, capped.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
