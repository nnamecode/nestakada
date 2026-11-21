from __future__ import annotations

import uuid
from urllib.parse import urlencode
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TransactionTestCase
from django.utils import timezone

from modules.accounts.api import SESSION_GENERATION_KEY
from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent

from ..commands import PageCommandError
from ..models import (
    Page,
    PageContent,
    PageGrant,
    PageKind,
    Route,
    RouteMode,
    RouteOutcome,
    SiteSettings,
)
from .test_publication import PASSWORD, PublicationFixture


class PageReorderHttpTests(PublicationFixture, TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        self.owner, self.settings, self.first = self.make_fixture()
        self.employee = User.objects.create_user(
            username="editor-reorder-http", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        self.second = Page.objects.create(
            name="Second <page>", kind=PageKind.ARTICLE, position=2
        )
        self.parent = Page.objects.create(
            name="Parent <group>", kind=PageKind.ARTICLE, position=3
        )
        self.child = Page.objects.create(
            name="Child", kind=PageKind.ARTICLE, parent=self.parent, position=0
        )
        for page, target in (
            (self.second, "/second/"),
            (self.parent, "/parent/"),
            (self.child, "/parent/child/"),
        ):
            Route.objects.create(
                page=page,
                target=target,
                mode=RouteMode.PRIMARY,
                outcome=RouteOutcome.ARTICLE,
            )
            PageContent.objects.create(
                page=page,
                current_payload=self.first.content.current_payload,
                current_hash=self.first.content.current_hash,
                current_author=self.owner,
                current_created_at=timezone.now(),
            )
        self.path = "/manage/pages/reorder/"

    def _login(self, actor: User) -> Client:
        client = Client(enforce_csrf_checks=True)
        client.force_login(actor)
        session = client.session
        session[SESSION_GENERATION_KEY] = actor.generation
        session.save()
        return client

    def _form(self, client: Client, parent: str = "root"):
        response = client.get(self.path, {"parent": parent})
        return response, response.cookies["csrftoken"].value

    def _post(self, client: Client, data: dict[str, object]):
        return client.post(
            self.path, data=urlencode(data, doseq=True),
            content_type="application/x-www-form-urlencoded",
        )

    def test_access_owner_links_and_root_nonroot_forms_are_exact(self) -> None:
        anonymous = Client().get(self.path, {"parent": "root"})
        self.assertEqual((anonymous.status_code, anonymous["Location"]), (302, "/manage/login/"))
        self.assertEqual(anonymous["Cache-Control"], "private, no-store")
        anonymous_post = Client(enforce_csrf_checks=True)
        anonymous_post.cookies["csrftoken"] = "a" * 32
        with patch("modules.pages.web.reorder_children") as command:
            denied_anonymous_post = self._post(anonymous_post, {
                "csrfmiddlewaretoken": "a" * 32,
                "base_structure_generation": "1", "parent": "root",
                "child_id": [str(self.first.id), str(self.second.id), str(self.parent.id)],
                "move": f"{self.second.id}|up",
            })
        self.assertEqual(
            (denied_anonymous_post.status_code, denied_anonymous_post["Location"]),
            (302, "/manage/login/"),
        )
        command.assert_not_called()
        employee = self._login(self.employee)
        with patch("modules.pages.web.SiteSettings.objects.select_for_update") as settings_lock:
            denied = employee.get(self.path, {"parent": "root"})
        self.assertEqual((denied.status_code, denied.content), (403, b"FORBIDDEN"))
        self.assertEqual(denied["Cache-Control"], "private, no-store")
        settings_lock.assert_not_called()
        employee.cookies["csrftoken"] = "a" * 32
        with patch("modules.pages.web.reorder_children") as command:
            denied_post = self._post(employee, {
                "csrfmiddlewaretoken": "a" * 32,
                "base_structure_generation": "1", "parent": "root",
                "child_id": [str(self.first.id), str(self.second.id), str(self.parent.id)],
                "move": f"{self.second.id}|up",
            })
        self.assertEqual((denied_post.status_code, denied_post.content), (403, b"FORBIDDEN"))
        command.assert_not_called()
        PageGrant.objects.create(staff=self.employee, page=self.first, groups=["text"])
        self.assertNotContains(employee.get("/manage/pages/"), "Упорядочить корневые страницы")
        self.assertNotContains(
            employee.get(f"/manage/pages/{self.first.id}/"),
            "Упорядочить дочерние страницы",
        )

        owner = self._login(self.owner)
        root, token = self._form(owner)
        self.assertEqual(root.status_code, 200)
        self.assertContains(root, 'name="base_structure_generation" value="1"')
        self.assertContains(root, f'name="child_id" value="{self.first.id}"')
        self.assertContains(root, f'value="{self.second.id}|up"')
        self.assertContains(root, "Second &lt;page&gt;")
        self.assertContains(owner.get("/manage/pages/"), f"{self.path}?parent=root")
        nested, _ = self._form(owner, str(self.parent.id))
        self.assertContains(nested, f'name="child_id" value="{self.child.id}"')
        self.assertContains(nested, "Parent &lt;group&gt;")
        self.assertContains(
            owner.get(f"/manage/pages/{self.parent.id}/"),
            f"{self.path}?parent={self.parent.id}",
        )
        self.assertEqual(root["Cache-Control"], "private, no-store")
        User.objects.filter(pk=self.owner.id).update(role=StaffRole.EMPLOYEE)
        with patch("modules.pages.web.reorder_children") as command:
            role_race = self._post(owner, {
                "csrfmiddlewaretoken": token,
                "base_structure_generation": "1", "parent": "root",
                "child_id": [str(self.first.id), str(self.second.id), str(self.parent.id)],
                "move": f"{self.second.id}|up",
            })
        self.assertEqual((role_race.status_code, role_race.content), (403, b"FORBIDDEN"))
        self.assertEqual(role_race["Cache-Control"], "private, no-store")
        command.assert_not_called()

    def test_success_repeat_conflict_parent_missing_and_unavailable_are_fixed(self) -> None:
        client = self._login(self.owner)
        form, token = self._form(client)
        root_ids = list(
            Page.objects.filter(parent=None).order_by("position", "id").values_list("id", flat=True)
        )
        success = self._post(client, {
            "csrfmiddlewaretoken": token,
            "base_structure_generation": "1",
            "parent": "root",
            "child_id": [str(value) for value in root_ids],
            "move": f"{self.second.id}|up",
        })
        self.assertEqual((success.status_code, success["Location"]), (302, f"{self.path}?parent=root"))
        self.assertEqual(
            list(Page.objects.filter(parent=None).order_by("position").values_list("id", flat=True))[:2],
            [self.second.id, self.first.id],
        )
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_REORDERED).count(), 1)
        repeat = self._post(client, {
            "csrfmiddlewaretoken": token,
            "base_structure_generation": "1", "parent": "root",
            "child_id": [str(value) for value in root_ids],
            "move": f"{self.second.id}|up",
        })
        self.assertEqual(repeat.status_code, 409)
        self.assertEqual(repeat["Cache-Control"], "private, no-store")
        self.assertEqual(repeat.content.count(f'href="{self.path}?parent=root"'.encode()), 1)
        missing = client.get(self.path, {"parent": str(uuid.uuid4())})
        self.assertEqual((missing.status_code, missing.content), (404, b"PARENT_NOT_FOUND"))
        SiteSettings.objects.all().delete()
        unavailable = client.get(self.path, {"parent": "root"})
        self.assertEqual((unavailable.status_code, unavailable.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
        self.assertEqual(unavailable["Cache-Control"], "private, no-store")

    def test_closed_query_wire_csrf_body_cap_and_method_contract(self) -> None:
        client = self._login(self.owner)
        form, token = self._form(client)
        root_ids = [str(value) for value in Page.objects.filter(parent=None).order_by("position", "id").values_list("id", flat=True)]
        for query in ({}, {"parent": "ROOT"}, {"parent": ["root", "root"]}, {"parent": "root", "x": "1"}):
            with self.subTest(query=query), patch("modules.pages.web._reorder_form_context") as projection:
                response = client.get(self.path, query)
                self.assertEqual((response.status_code, response.content), (400, b"INVALID_PAGE_REORDER_INPUT"))
                projection.assert_not_called()
        missing_csrf = self._post(client, {
            "base_structure_generation": "1", "parent": "root",
            "child_id": root_ids, "move": f"{self.second.id}|up",
        })
        self.assertEqual(missing_csrf.status_code, 403)
        invalid = (
            {"base_structure_generation": "01", "parent": "root", "child_id": root_ids, "move": f"{self.second.id}|up"},
            {"base_structure_generation": "1", "parent": "root", "child_id": root_ids, "move": f"{str(self.second.id).upper()}|up"},
            {"base_structure_generation": "1", "parent": "root", "child_id": root_ids, "move": f"{self.second.id}|left"},
            {"base_structure_generation": "1", "parent": "root", "child_id": [root_ids[0], root_ids[0]], "move": f"{self.first.id}|up"},
            {"base_structure_generation": "1", "parent": "root", "child_id": root_ids, "move": f"{root_ids[0]}|up", "x": "1"},
        )
        for data in invalid:
            data = {"csrfmiddlewaretoken": token, **data}
            with self.subTest(data=data), patch("modules.pages.web.reorder_children") as command:
                response = self._post(client, data)
                self.assertEqual((response.status_code, response.content), (400, b"INVALID_PAGE_REORDER_INPUT"))
                self.assertEqual(response["Cache-Control"], "private, no-store")
                command.assert_not_called()
        multipart = client.post(self.path, {
            "csrfmiddlewaretoken": token, "base_structure_generation": "1",
            "parent": "root", "child_id": root_ids, "move": f"{self.second.id}|up",
        })
        uploaded = client.post(self.path, {
            "csrfmiddlewaretoken": token, "base_structure_generation": "1",
            "parent": "root", "child_id": root_ids, "move": f"{self.second.id}|up",
            "file": SimpleUploadedFile("x.txt", b"x"),
        })
        capped = client.post(
            self.path, data=b"x", content_type="application/x-www-form-urlencoded",
            CONTENT_LENGTH="4194305", HTTP_X_CSRFTOKEN=token,
        )
        for response in (multipart, uploaded, capped):
            self.assertEqual((response.status_code, response.content), (400, b"INVALID_PAGE_REORDER_INPUT"))
        put = client.put(
            self.path, data=b"", content_type="application/x-www-form-urlencoded",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual((put.status_code, put["Allow"]), (405, "GET, POST"))
        self.assertEqual(put["Cache-Control"], "private, no-store")

    def test_session_role_command_conflicts_and_faults_remain_private(self) -> None:
        client = self._login(self.owner)
        form, token = self._form(client)
        root_ids = [str(value) for value in Page.objects.filter(parent=None).order_by("position", "id").values_list("id", flat=True)]
        data = {
            "csrfmiddlewaretoken": token, "base_structure_generation": "1",
            "parent": "root", "child_id": root_ids,
            "move": f"{self.second.id}|up",
        }
        session = client.session; session[SESSION_GENERATION_KEY] = 999; session.save()
        with patch("modules.pages.web.reorder_children") as command:
            stale = self._post(client, data)
        self.assertEqual((stale.status_code, stale["Location"]), (302, "/manage/login/"))
        command.assert_not_called()

        client = self._login(self.owner); form, token = self._form(client)
        data["csrfmiddlewaretoken"] = token
        for code, status in (("CHILD_SET_CONFLICT", 409), ("NO_CHANGE", 409), ("REORDER_UNAVAILABLE", 503)):
            with self.subTest(code=code), patch(
                "modules.pages.web.reorder_children", side_effect=PageCommandError(code)
            ):
                response = self._post(client, data)
                self.assertEqual(response.status_code, status)
                self.assertNotContains(response, str(self.second.id), status_code=status)
        with patch("modules.pages.web.reorder_children", side_effect=RuntimeError("Secret order")):
            fault = self._post(client, data)
        self.assertEqual((fault.status_code, fault.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
        self.assertEqual(fault["Cache-Control"], "private, no-store")
        self.assertNotContains(fault, "Secret", status_code=503)
