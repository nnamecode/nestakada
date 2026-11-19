from __future__ import annotations

import copy
import json
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
from django.urls import reverse
from django.utils import timezone

from modules.accounts.api import SESSION_GENERATION_KEY, StaffRole
from modules.audit.api import Action, AuditEvent
from modules.media.models import Asset, AssetPurpose, AssetState, AssetUsage, UsageScope

from ..commands import save_page_content
from ..content import FIELD_SETS, MEDIA_SLOTS, RICH_BY_KIND, canonical_payload_hash, validate_payload
from ..models import Page, PageContent, PageGrant, PageKind, Route, RouteMode, RouteOutcome


User = get_user_model()


def payload(*, intro: str = "<p>Intro</p>", body: str = "<p>Body</p>") -> dict:
    return {
        "schema": "estakada.page-content",
        "schema_version": 1,
        "kind": "service_detail",
        "fields": {
            "seo": {"title": "Title", "description": "Description", "allow_index": True},
            "heading": {"h1": "Heading"},
            "intro": intro,
            "body": body,
            "price_rows": {"columns": [], "rows": []},
            "media": {"hero": None, "body": [], "works": []},
        },
    }


def minimal_payload(kind: str) -> dict:
    fields = {
        "seo": {"title": "Title", "description": "", "allow_index": True},
        "heading": {"h1": "Heading"},
    }
    for name in RICH_BY_KIND.get(kind, set()):
        fields[name] = "<p>Text</p>"
    for name in (
        "service_refs", "brand_refs", "review_refs", "process_steps", "actions", "reviews", "links",
    ):
        if name in FIELD_SETS[kind]:
            fields[name] = []
    if "price_rows" in FIELD_SETS[kind]:
        fields["price_rows"] = {"columns": [], "rows": []}
    if "media" in FIELD_SETS[kind]:
        fields["media"] = {
            slot: (None if slot == "hero" else [])
            for slot in MEDIA_SLOTS[kind]
        }
    return {"schema": "estakada.page-content", "schema_version": 1, "kind": kind, "fields": fields}


class TypedEditorHttpTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner = User.objects.create_superuser(username="nesadmin", password=None)
        cls.employee = User.objects.create_user(
            username="editor",
            role=StaffRole.EMPLOYEE,
            password=None,
        )
        cls.page = Page.objects.create(
            name="Service page",
            kind=PageKind.SERVICE_DETAIL,
            position=1,
            is_published=True,
        )
        Route.objects.create(
            page=cls.page,
            target="/service/",
            mode=RouteMode.PRIMARY,
            outcome=RouteOutcome.SERVICE_DETAIL,
        )
        cls.initial = payload()
        PageContent.objects.create(
            page=cls.page,
            generation=1,
            current_payload=cls.initial,
            current_hash=canonical_payload_hash(cls.initial),
            current_author=cls.owner,
            current_created_at=timezone.now(),
        )
        PageGrant.objects.create(staff=cls.employee, page=cls.page, groups=["text"])

    def _client(self, actor) -> Client:
        client = Client(enforce_csrf_checks=True)
        client.force_login(actor)
        session = client.session
        session[SESSION_GENERATION_KEY] = actor.generation
        session.save()
        return client

    def _get(self, client: Client):
        return client.get(reverse("manage-page-editor", args=(self.page.id,)))

    def _save_data(self, response, *, rich: dict[str, str] | None = None) -> dict:
        rich = rich or {}
        data = {
            "csrfmiddlewaretoken": response.client.cookies["csrftoken"].value,
            "operation_id": str(response.context["save_operation_id"]),
            "base_generation": str(response.context["generation"]),
            "base_current_hash": response.context["base_current_hash"],
            "seo.title": "Changed title",
            "seo.description": "Changed description",
            "seo.allow_index": "0",
            "heading.h1": "Changed heading",
        }
        for name in ("intro", "body"):
            data[f"rich.{name}.changed"] = "1" if name in rich else "0"
            if name in rich:
                data[f"rich.{name}.value"] = rich[name]
        if response.context["price_control"] is not None:
            data["price.changed"] = "0"
        return data

    def _employee_data(self, response, *, rich: dict[str, str] | None = None) -> dict:
        data = self._save_data(response, rich=rich)
        for key in ("seo.title", "seo.description", "seo.allow_index", "heading.h1"):
            data.pop(key)
        return data

    def _post_save(self, client: Client, data: dict):
        return client.post(reverse("manage-page-save", args=(self.page.id,)), data=data)

    def _home(self, *, steps: list[dict[str, str]] | None = None):
        page = Page.objects.create(name="Home page", kind=PageKind.HOME, position=2, is_published=True)
        Route.objects.create(
            page=page,
            target="/",
            mode=RouteMode.PRIMARY,
            outcome=RouteOutcome.HOME,
        )
        value = minimal_payload(PageKind.HOME)
        value["fields"]["process_steps"] = steps or []
        PageContent.objects.create(
            page=page,
            generation=1,
            current_payload=value,
            current_hash=canonical_payload_hash(value),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )
        return page, value

    def _home_save_data(self, response, *, changed: str = "0", steps=()) -> dict:
        data = {
            "csrfmiddlewaretoken": response.client.cookies["csrftoken"].value,
            "operation_id": str(response.context["save_operation_id"]),
            "base_generation": str(response.context["generation"]),
            "base_current_hash": response.context["base_current_hash"],
            "seo.title": "Home title",
            "seo.description": "Home description",
            "seo.allow_index": "1",
            "heading.h1": "Home heading",
            "rich.about.changed": "0",
            "rich.contact_text.changed": "0",
            "rich.lead.changed": "0",
            "process.changed": changed,
        }
        if changed == "1":
            data["process.step"] = list(steps)
        return data

    def _partner_page(self, *, links: list[dict[str, str]] | None = None):
        page = Page.objects.create(
            name="Partner links",
            kind=PageKind.LEGACY_PARTNER_LINKS,
            position=3,
            is_published=True,
        )
        Route.objects.create(
            page=page,
            target="/partners",
            mode=RouteMode.PRIMARY,
            outcome=RouteOutcome.LEGACY_PARTNER_LINKS,
        )
        value = minimal_payload(PageKind.LEGACY_PARTNER_LINKS)
        value["fields"]["links"] = links or []
        PageContent.objects.create(
            page=page,
            generation=1,
            current_payload=value,
            current_hash=canonical_payload_hash(value),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )
        return page, value

    def _partner_save_data(self, response, *, changed: str = "0", links=()) -> dict:
        data = {
            "csrfmiddlewaretoken": response.client.cookies["csrftoken"].value,
            "operation_id": str(response.context["save_operation_id"]),
            "base_generation": str(response.context["generation"]),
            "base_current_hash": response.context["base_current_hash"],
            "seo.title": "Partners title",
            "seo.description": "Partners description",
            "seo.allow_index": "1",
            "heading.h1": "Partners heading",
            "links.changed": changed,
        }
        if changed == "1":
            data["links.item"] = list(links)
        return data

    def test_price_multipart_limits_cover_exact_contract_without_unbounded_parser(self):
        exact_fields = 1 + 3 + 4 + 2 + 2 + 1 + 32 + 500 + 10_000
        self.assertEqual(exact_fields, 10_545)
        self.assertEqual(settings.DATA_UPLOAD_MAX_NUMBER_FIELDS, 10_600)
        self.assertEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 4_194_304)

        column_ids = [str(uuid.UUID(int=index + 1)) for index in range(32)]
        row_ids = [str(uuid.UUID(int=index + 1000)) for index in range(500)]

        def candidate_with(cell_count: int):
            value = payload()
            value["fields"]["price_rows"] = {
                "columns": [{"id": item, "label": "C"} for item in column_ids],
                "rows": [
                    {
                        "id": row_id,
                        "label": "R",
                        "cells": [
                            {"column_id": column_ids[column], "kind": "text", "text": ""}
                            for column in range(32)
                            if row * 32 + column < cell_count
                        ],
                    }
                    for row, row_id in enumerate(row_ids)
                ],
            }
            return value

        low, high = 0, 10_000
        while low < high:
            middle = (low + high + 1) // 2
            encoded = json.dumps(
                candidate_with(middle),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(encoded) <= 1_048_576:
                low = middle
            else:
                high = middle - 1
        candidate = candidate_with(low)
        validate_payload(candidate, PageKind.SERVICE_DETAIL)
        candidate_bytes = len(json.dumps(
            candidate,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"))
        self.assertLessEqual(candidate_bytes, 1_048_576)
        if low < 10_000:
            next_bytes = len(json.dumps(
                candidate_with(low + 1),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"))
            self.assertGreater(next_bytes, 1_048_576)

        pairs = [
            ("csrfmiddlewaretoken", "x" * 64),
            ("operation_id", str(uuid.UUID(int=999_999))),
            ("base_generation", "1"),
            ("base_current_hash", "a" * 64),
            ("seo.title", "Title"),
            ("seo.description", ""),
            ("seo.allow_index", "1"),
            ("heading.h1", "Heading"),
            ("rich.intro.changed", "1"),
            ("rich.intro.value", "<p>Intro</p>"),
            ("rich.body.changed", "1"),
            ("rich.body.value", "<p>Body</p>"),
            ("price.changed", "1"),
            *[("price.column", f"{item}\tC") for item in column_ids],
            *[("price.row", f"{item}\tR") for item in row_ids],
        ]
        for row_index, row_id in enumerate(row_ids):
            for column_index, column_id in enumerate(column_ids):
                if row_index * 32 + column_index >= low:
                    break
                pairs.append(("price.cell", f"{row_id}\t{column_id}\ttext\t"))

        boundary = b"b" * 70
        body = bytearray()
        for name, value in pairs:
            body.extend(b"--" + boundary + b"\r\n")
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"))
            body.extend(value.encode("utf-8"))
            body.extend(b"\r\n")
        body.extend(b"--" + boundary + b"--\r\n")
        self.assertEqual(len(pairs), 545 + low)
        self.assertLessEqual(len(pairs), settings.DATA_UPLOAD_MAX_NUMBER_FIELDS)
        self.assertLessEqual(len(body), settings.DATA_UPLOAD_MAX_MEMORY_SIZE)

        # Independent conservative bound covers all10,000 records, not only the
        # maximum-field canonical envelope constructed above.
        per_part_overhead = 200
        repeated_row_identity = 37 * 10_000
        fixed_wire_values = 4_096
        self.assertLessEqual(
            1_048_576 + exact_fields * per_part_overhead + repeated_row_identity + fixed_wire_values,
            4_194_304,
        )

    def test_home_process_wire_exact27_fits_existing_body_cap(self):
        astral = "\U0001f600"
        pairs = [
            ("csrfmiddlewaretoken", "x" * 64),
            ("operation_id", str(uuid.UUID(int=1))),
            ("base_generation", str(2**63 - 1)),
            ("base_current_hash", "a" * 64),
            ("seo.title", astral * 255),
            ("seo.description", astral * 1000),
            ("seo.allow_index", "1"),
            ("heading.h1", astral * 255),
            ("rich.about.changed", "1"),
            ("rich.about.value", "x" * 1_048_576),
            ("rich.contact_text.changed", "1"),
            ("rich.contact_text.value", "x" * 1_048_576),
            ("rich.lead.changed", "1"),
            ("rich.lead.value", "x" * 1_048_576),
            ("process.changed", "1"),
            *[("process.step", f"{astral * 500}\t{astral * 4000}") for _ in range(12)],
        ]
        boundary = b"b" * 70
        body = bytearray()
        for name, value in pairs:
            body.extend(b"--" + boundary + b"\r\n")
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"))
            body.extend(value.encode("utf-8"))
            body.extend(b"\r\n")
        body.extend(b"--" + boundary + b"--\r\n")
        self.assertEqual(len(pairs), 27)
        self.assertEqual(sum(len(value.encode("utf-8")) for _, value in pairs), 3_367_968)
        self.assertLessEqual(len(body), settings.DATA_UPLOAD_MAX_MEMORY_SIZE)
        self.assertEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE + 1, 4_194_305)

    def test_home_process_owner_projection_is_escaped_and_employee_disclosure_is_zero(self):
        page, _ = self._home(steps=[{"title": "<Этап>", "body": "A > B"}])
        owner = self._client(self.owner)
        response = owner.get(reverse("manage-page-editor", args=(page.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="process.changed"')
        self.assertContains(response, 'value="&lt;Этап&gt;"')
        self.assertContains(response, 'value="A &gt; B"')
        self.assertEqual(len(response.context["process_control"].steps), 1)
        self.assertNotIn("Этапы работы", [field.label for field in response.context["deferred_fields"]])

        PageGrant.objects.create(staff=self.employee, page=page, groups=["text"])
        employee = self._client(self.employee)
        hidden = employee.get(reverse("manage-page-editor", args=(page.id,)))
        self.assertEqual(hidden.status_code, 200)
        for forbidden in ("process.changed", "data-process-control", "<Этап>", "A &gt; B", "Этапы работы"):
            self.assertNotContains(hidden, forbidden)
        direct = employee.post(
            reverse("manage-page-save", args=(page.id,)),
            data={
                "csrfmiddlewaretoken": employee.cookies["csrftoken"].value,
                "process.changed": "1",
                "process.step": "Crafted\tbody",
            },
        )
        self.assertEqual(direct.status_code, 403)

    def test_home_process_unchanged_then_changed_preserves_unrelated_fields_and_replays(self):
        initial_steps = [{"title": "Диагностика", "body": "Проверка"}]
        page, initial = self._home(steps=initial_steps)
        client = self._client(self.owner)
        editor = client.get(reverse("manage-page-editor", args=(page.id,)))
        unchanged = self._home_save_data(editor)
        first = client.post(reverse("manage-page-save", args=(page.id,)), data=unchanged)
        self.assertEqual(first.status_code, 302)
        content = PageContent.objects.get(page=page)
        self.assertEqual(content.current_payload["fields"]["process_steps"], initial_steps)

        editor = client.get(reverse("manage-page-editor", args=(page.id,)))
        changed = self._home_save_data(
            editor,
            changed="1",
            steps=("<Приём>\tA > B", "Ремонт\t"),
        )
        saved = client.post(reverse("manage-page-save", args=(page.id,)), data=changed)
        replay = dict(changed)
        replay["process.step"] = ["Другое\tЗначение"]
        retained = client.post(reverse("manage-page-save", args=(page.id,)), data=replay)
        self.assertEqual((saved.status_code, retained.status_code), (302, 302))
        content.refresh_from_db()
        self.assertEqual(content.generation, 3)
        self.assertEqual(
            content.current_payload["fields"]["process_steps"],
            [{"title": "<Приём>", "body": "A > B"}, {"title": "Ремонт", "body": ""}],
        )
        for name in ("service_refs", "brand_refs", "review_refs", "media"):
            self.assertEqual(content.current_payload["fields"][name], initial["fields"][name])
        self.assertEqual(content.previous_payload["fields"]["process_steps"], initial_steps)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CONTENT_SAVED).count(), 2)

    def test_home_process_malformed_wire_never_invokes_command(self):
        page, _ = self._home(steps=[{"title": "One", "body": "Body"}])
        client = self._client(self.owner)
        editor = client.get(reverse("manage-page-editor", args=(page.id,)))
        base = self._home_save_data(editor, changed="1", steps=("Valid\tBody",))
        cases = []
        missing = dict(base); missing.pop("process.changed"); missing.pop("process.step")
        cases.append(missing)
        cases.extend((
            {**base, "process.changed": ["1", "1"]},
            {**base, "process.changed": "0"},
            {**base, "process.step": "missing-separator"},
            {**base, "process.step": "too\tmany\tseparators"},
            {**base, "process.step": [f"T{index}\tB" for index in range(13)]},
            {**base, "process.step": "\tbody"},
            {**base, "process.step": f"{'x' * 501}\tbody"},
            {**base, "process.step": f"title\t{'x' * 4001}"},
            {**base, "process.step": "title\tbad\nbody"},
            {**base, "process.step": "e\u0301\tbody"},
        ))
        for invalid in cases:
            with self.subTest(keys=tuple(invalid)), patch("modules.pages.web.save_page_content") as command:
                response = client.post(reverse("manage-page-save", args=(page.id,)), data=invalid)
                self.assertEqual(response.status_code, 400)
                command.assert_not_called()

        service = self._save_data(self._get(client))
        service.update({"process.changed": "1", "process.step": "Forged\tbody"})
        with patch("modules.pages.web.save_page_content") as command:
            response = self._post_save(client, service)
        self.assertEqual(response.status_code, 400)
        command.assert_not_called()

    def test_partner_links_wire_exact73_fits_existing_body_cap(self):
        astral = "\U0001f600"
        pairs = [
            ("csrfmiddlewaretoken", "x" * 64),
            ("operation_id", str(uuid.UUID(int=1))),
            ("base_generation", str(2**63 - 1)),
            ("base_current_hash", "a" * 64),
            ("seo.title", astral * 255),
            ("seo.description", astral * 1000),
            ("seo.allow_index", "1"),
            ("heading.h1", astral * 255),
            ("links.changed", "1"),
            *[("links.item", f"{astral * 500}\t{astral * 2048}") for _ in range(64)],
        ]
        boundary = b"b" * 70
        body = bytearray()
        for name, value in pairs:
            body.extend(b"--" + boundary + b"\r\n")
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"))
            body.extend(value.encode("utf-8"))
            body.extend(b"\r\n")
        body.extend(b"--" + boundary + b"--\r\n")
        self.assertEqual(len(pairs), 73)
        self.assertEqual(sum(len(value.encode("utf-8")) for _, value in pairs), 658_577)
        self.assertLessEqual(len(body), 677_341)
        self.assertLessEqual(len(body), settings.DATA_UPLOAD_MAX_MEMORY_SIZE)

    def test_partner_links_owner_projection_is_escaped_and_employee_disclosure_is_zero(self):
        links = [
            {"label": "<Партнёр>", "https_url": "https://example.test/path?a=1&b=2"},
            {"label": "Второй", "https_url": "https://two.example.test/path"},
            {"label": "Третий", "https_url": "https://three.example.test/path"},
            {"label": "Четвёртый", "https_url": "https://four.example.test/path"},
            {"label": "Пятый", "https_url": "https://five.example.test/path"},
            {"label": "Шестой", "https_url": "https://six.example.test/path"},
        ]
        page, _ = self._partner_page(links=links)
        owner = self._client(self.owner)
        response = owner.get(reverse("manage-page-editor", args=(page.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="links.changed"')
        self.assertContains(response, 'value="&lt;Партнёр&gt;"')
        self.assertContains(response, 'value="https://example.test/path?a=1&amp;b=2"')
        self.assertEqual(
            [(item.label, item.https_url) for item in response.context["partner_links_control"].links],
            [(item["label"], item["https_url"]) for item in links],
        )
        self.assertNotIn("Ссылки", [field.label for field in response.context["deferred_fields"]])

        PageGrant.objects.create(staff=self.employee, page=page, groups=["text"])
        employee = self._client(self.employee)
        hidden = employee.get(reverse("manage-page-editor", args=(page.id,)))
        self.assertEqual(hidden.status_code, 200)
        for forbidden in ("links.changed", "data-links-control", "<Партнёр>", "example.test", "Партнёрские ссылки"):
            self.assertNotContains(hidden, forbidden)
        direct = employee.post(
            reverse("manage-page-save", args=(page.id,)),
            data={
                "csrfmiddlewaretoken": employee.cookies["csrftoken"].value,
                "links.changed": "1",
                "links.item": "Crafted\thttps://example.test/x",
            },
        )
        self.assertEqual(direct.status_code, 403)

    def test_partner_links_unchanged_then_changed_preserves_pagecas_and_query_policy(self):
        initial_links = [{"label": "Первый", "https_url": "https://example.test/one"}]
        page, _ = self._partner_page(links=initial_links)
        client = self._client(self.owner)
        editor = client.get(reverse("manage-page-editor", args=(page.id,)))
        first = client.post(
            reverse("manage-page-save", args=(page.id,)),
            data=self._partner_save_data(editor),
        )
        self.assertEqual(first.status_code, 302)
        content = PageContent.objects.get(page=page)
        self.assertEqual(content.current_payload["fields"]["links"], initial_links)

        editor = client.get(reverse("manage-page-editor", args=(page.id,)))
        changed = self._partner_save_data(
            editor,
            changed="1",
            links=(
                "<Новый>\thttps://example.test/new?q=\\literal",
                "Второй\thttps://sub.example.test/two?page=1",
            ),
        )
        saved = client.post(reverse("manage-page-save", args=(page.id,)), data=changed)
        replay = dict(changed)
        replay["links.item"] = ["Другое\thttps://example.test/other"]
        retained = client.post(reverse("manage-page-save", args=(page.id,)), data=replay)
        self.assertEqual((saved.status_code, retained.status_code), (302, 302))
        content.refresh_from_db()
        self.assertEqual(content.generation, 3)
        self.assertEqual(
            content.current_payload["fields"]["links"],
            [
                {"label": "<Новый>", "https_url": "https://example.test/new?q=\\literal"},
                {"label": "Второй", "https_url": "https://sub.example.test/two?page=1"},
            ],
        )
        self.assertEqual(content.previous_payload["fields"]["links"], initial_links)

        editor = client.get(reverse("manage-page-editor", args=(page.id,)))
        emptied = client.post(
            reverse("manage-page-save", args=(page.id,)),
            data=self._partner_save_data(editor, changed="1", links=()),
        )
        self.assertEqual(emptied.status_code, 302)
        content.refresh_from_db()
        self.assertEqual(content.current_payload["fields"]["links"], [])

        exact64 = tuple(
            f"Link {index}\thttps://example.test/link-{index}"
            for index in range(64)
        )
        editor = client.get(reverse("manage-page-editor", args=(page.id,)))
        full = client.post(
            reverse("manage-page-save", args=(page.id,)),
            data=self._partner_save_data(editor, changed="1", links=exact64),
        )
        self.assertEqual(full.status_code, 302)
        content.refresh_from_db()
        self.assertEqual(
            content.current_payload["fields"]["links"],
            [
                {"label": f"Link {index}", "https_url": f"https://example.test/link-{index}"}
                for index in range(64)
            ],
        )
        self.assertEqual(content.previous_payload["fields"]["links"], [])
        self.assertEqual(content.generation, 5)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CONTENT_SAVED).count(), 4)

    def test_partner_links_malformed_and_invalid_https_never_invoke_command(self):
        page, _ = self._partner_page(
            links=[{"label": "One", "https_url": "https://example.test/one"}],
        )
        client = self._client(self.owner)
        editor = client.get(reverse("manage-page-editor", args=(page.id,)))
        base = self._partner_save_data(
            editor,
            changed="1",
            links=("Valid\thttps://example.test/path",),
        )
        cases = []
        missing = dict(base); missing.pop("links.changed"); missing.pop("links.item")
        cases.append(missing)
        invalid_urls = (
            "http://example.test/x",
            "https://user@example.test/x",
            "https://example.test:443/x",
            "https://example.test/x#fragment",
            "https://example.test/%GG",
            "https://example.test/a\\b",
            "https://exa\\mple.test/x",
            "https://example.test/x?q=%20",
        )
        cases.extend((
            {**base, "links.changed": ["1", "1"]},
            {**base, "links.changed": "0"},
            {**base, "links.item": "missing-separator"},
            {**base, "links.item": "too\tmany\tseparators"},
            {**base, "links.item": [f"L{index}\thttps://example.test/{index}" for index in range(65)]},
            {**base, "links.item": "\thttps://example.test/x"},
            {**base, "links.item": f"{'x' * 501}\thttps://example.test/x"},
            {**base, "links.item": "e\u0301\thttps://example.test/x"},
            {**base, "links.item": "bad\nlabel\thttps://example.test/x"},
            {**base, "links.item": "Label\t"},
            {**base, "links.item": f"Label\thttps://example.test/{'x' * 2030}"},
            *({**base, "links.item": f"Label\t{url}"} for url in invalid_urls),
        ))
        for invalid in cases:
            with self.subTest(keys=tuple(invalid)), patch("modules.pages.web.save_page_content") as command:
                response = client.post(reverse("manage-page-save", args=(page.id,)), data=invalid)
                self.assertEqual(response.status_code, 400)
                command.assert_not_called()

        service = self._save_data(self._get(client))
        service.update({"links.changed": "1", "links.item": "Forged\thttps://example.test/x"})
        with patch("modules.pages.web.save_page_content") as command:
            response = self._post_save(client, service)
        self.assertEqual(response.status_code, 400)
        command.assert_not_called()

    def test_owner_get_has_only_supported_controls_and_deferred_counts(self):
        response = self._get(self._client(self.owner))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="seo.title"')
        self.assertContains(response, 'name="heading.h1"')
        self.assertContains(response, 'name="rich.intro.changed"')
        self.assertContains(response, 'name="rich.body.changed"')
        self.assertContains(response, "Прайс")
        self.assertContains(response, "Медиа")
        self.assertNotContains(response, "current_payload")
        self.assertNotContains(response, "source_sha256")
        self.assertNotContains(response, "previous_hash")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_owner_get_supports_exact_nineteen_kind_field_map(self):
        client = self._client(self.owner)
        self.assertEqual(len(FIELD_SETS), 19)
        for position, kind in enumerate(sorted(FIELD_SETS), start=20):
            with self.subTest(kind=kind):
                page = Page.objects.create(name=kind, kind=kind, position=position)
                Route.objects.create(
                    page=page,
                    target=f"/kind-{position}/",
                    mode=RouteMode.PRIMARY,
                    outcome=kind,
                )
                value = minimal_payload(kind)
                PageContent.objects.create(
                    page=page,
                    current_payload=value,
                    current_hash=canonical_payload_hash(value),
                    current_author=self.owner,
                    current_created_at=timezone.now(),
                )
                response = client.get(reverse("manage-page-editor", args=(page.id,)))
                self.assertEqual(response.status_code, 200)
                actual = {control.name for control in response.context["rich_controls"]}
                self.assertEqual(actual, RICH_BY_KIND.get(kind, set()))

    def test_employee_dom_contains_only_header_and_granted_rich_fields(self):
        response = self._get(self._client(self.employee))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="rich.intro.changed"')
        self.assertContains(response, 'name="rich.body.changed"')
        for forbidden in ('name="seo.title"', 'name="heading.h1"', "Прайс", "Медиа"):
            self.assertNotContains(response, forbidden)

    def test_foreign_employee_uuid_is_constant_forbidden_without_page_data(self):
        foreign = Page.objects.create(
            name="Foreign secret",
            kind=PageKind.LEGACY_EMPTY_MAIN,
            position=2,
        )
        response = self._client(self.employee).get(reverse("manage-page-editor", args=(foreign.id,)))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b"FORBIDDEN")
        self.assertNotContains(response, "Foreign secret", status_code=403)

    def test_corrupt_current_or_previous_fails_before_render(self):
        client = self._client(self.owner)
        content = PageContent.objects.get(page=self.page)
        content.current_hash = "f" * 64
        content.save(update_fields=("current_hash",))
        response = self._get(client)
        self.assertEqual(response.status_code, 503)

        content.current_hash = canonical_payload_hash(content.current_payload)
        content.previous_payload = payload(intro="<p>Previous</p>")
        content.previous_hash = "e" * 64
        content.previous_author = self.owner
        content.previous_created_at = timezone.now()
        content.save()
        response = self._get(client)
        self.assertEqual(response.status_code, 503)

    def test_owner_save_preserves_structured_media_and_replays_once(self):
        client = self._client(self.owner)
        get_response = self._get(client)
        data = self._save_data(get_response, rich={"intro": "<p>Changed</p>"})
        first = self._post_save(client, data)
        replay = dict(data)
        replay_column, replay_row = uuid.uuid4(), uuid.uuid4()
        replay.update({
            "price.changed": "1",
            "price.column": f"{replay_column}\tДругая цена",
            "price.row": f"{replay_row}\tДругая строка",
            "price.cell": f"{replay_row}\t{replay_column}\tamount\t999\t0",
        })
        second = self._post_save(client, replay)
        self.assertEqual((first.status_code, second.status_code), (302, 302))
        content = PageContent.objects.get(page=self.page)
        self.assertEqual(content.generation, 2)
        self.assertEqual(content.current_payload["fields"]["intro"], "<p>Changed</p>")
        self.assertEqual(content.current_payload["fields"]["body"], "<p>Body</p>")
        self.assertEqual(content.current_payload["fields"]["price_rows"], self.initial["fields"]["price_rows"])
        self.assertEqual(content.current_payload["fields"]["media"], self.initial["fields"]["media"])
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CONTENT_SAVED).count(), 1)

    def test_employee_save_changes_only_text_and_rejects_protected_key(self):
        client = self._client(self.employee)
        get_response = self._get(client)
        data = self._employee_data(get_response, rich={"body": "<p>Employee</p>"})
        response = self._post_save(client, data)
        self.assertEqual(response.status_code, 302)
        content = PageContent.objects.get(page=self.page)
        self.assertEqual(content.current_payload["fields"]["intro"], "<p>Intro</p>")
        self.assertEqual(content.current_payload["fields"]["body"], "<p>Employee</p>")
        self.assertEqual(content.current_payload["fields"]["seo"], self.initial["fields"]["seo"])

        fresh = self._get(client)
        crafted = self._employee_data(fresh)
        crafted["seo.title"] = "Forbidden"
        rejected = self._post_save(client, crafted)
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(PageContent.objects.get(page=self.page).generation, 2)

    def test_price_only_employee_get_and_save_change_only_prices(self):
        PageGrant.objects.filter(staff=self.employee, page=self.page).update(groups=["prices"])
        client = self._client(self.employee)
        response = self._get(client)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-editor-form")
        self.assertContains(response, "data-prices-only")
        self.assertContains(response, 'name="price.changed"')
        self.assertNotContains(response, 'name="rich.intro.changed"')
        self.assertNotContains(response, 'name="seo.title"')

        column_a, column_b, row_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        data = {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            "operation_id": str(response.context["save_operation_id"]),
            "base_generation": str(response.context["generation"]),
            "base_current_hash": response.context["base_current_hash"],
            "price.changed": "1",
            "price.column": [f"{column_a}\tРабота", f"{column_b}\tЦена"],
            "price.row": f"{row_id}\tЗамена",
            "price.cell": [
                f"{row_id}\t{column_b}\tamount\t1250.50\t1",
                f"{row_id}\t{column_a}\ttext\tКомплект",
            ],
        }
        first = self._post_save(client, data)
        second = self._post_save(client, data)
        self.assertEqual((first.status_code, second.status_code), (302, 302))
        content = PageContent.objects.get(page=self.page)
        self.assertEqual(content.generation, 2)
        self.assertEqual(content.current_payload["fields"]["seo"], self.initial["fields"]["seo"])
        price = content.current_payload["fields"]["price_rows"]
        self.assertEqual([item["id"] for item in price["columns"]], [str(column_a), str(column_b)])
        self.assertEqual(
            [item["column_id"] for item in price["rows"][0]["cells"]],
            [str(column_a), str(column_b)],
        )
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CONTENT_SAVED).count(), 1)

    def test_price_only_unchanged_and_malformed_wire_invoke_no_command(self):
        PageGrant.objects.filter(staff=self.employee, page=self.page).update(groups=["prices"])
        client = self._client(self.employee)
        editor = self._get(client)
        base = {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            "operation_id": str(editor.context["save_operation_id"]),
            "base_generation": str(editor.context["generation"]),
            "base_current_hash": editor.context["base_current_hash"],
        }
        with patch("modules.pages.web.save_page_content") as command:
            response = self._post_save(client, {**base, "price.changed": "0"})
        self.assertEqual(response.status_code, 400)
        command.assert_not_called()

        column_id, row_id = uuid.uuid4(), uuid.uuid4()
        valid = {
            **base,
            "price.changed": "1",
            "price.column": f"{column_id}\tA",
            "price.row": f"{row_id}\tRow",
            "price.cell": f"{row_id}\t{column_id}\tamount\t100\t0",
        }
        other_id = uuid.uuid4()
        bad_cases = (
            {**valid, "price.column": [valid["price.column"], valid["price.column"]]},
            {**valid, "price.row": [valid["price.row"], valid["price.row"]]},
            {**valid, "price.cell": [valid["price.cell"], valid["price.cell"]]},
            {**valid, "price.row": f"{column_id}\tCross-set"},
            {**valid, "price.cell": f"{row_id}\t{other_id}\ttext\tOrphan"},
            {**valid, "price.cell": f"{row_id}\t{column_id}\ttext"},
            {**valid, "price.cell": f"{row_id}\t{column_id}\tamount\t01\t0"},
            {**valid, "price.cell": f"{row_id}\t{column_id}\tamount\t100\t2"},
            {
                **valid,
                "price.column": [f"{uuid.UUID(int=index + 1)}\tC" for index in range(33)],
                "price.cell": [],
            },
            {
                **valid,
                "price.row": [f"{uuid.UUID(int=index + 1000)}\tR" for index in range(501)],
                "price.cell": [],
            },
            {**valid, "price.cell": [valid["price.cell"]] * 10_001},
        )
        for index, bad in enumerate(bad_cases):
            with self.subTest(index=index), patch("modules.pages.web.save_page_content") as command:
                response = self._post_save(client, bad)
                self.assertEqual(response.status_code, 400)
                command.assert_not_called()

    def test_text_and_prices_employee_may_submit_both_literal_groups(self):
        PageGrant.objects.filter(staff=self.employee, page=self.page).update(groups=["text", "prices"])
        client = self._client(self.employee)
        editor = self._get(client)
        column_id, row_id = uuid.uuid4(), uuid.uuid4()
        data = self._employee_data(editor, rich={"intro": "<p>Both groups</p>"})
        data.update({
            "price.changed": "1",
            "price.column": f"{column_id}\tЦена",
            "price.row": f"{row_id}\tДиагностика",
            "price.cell": f"{row_id}\t{column_id}\tamount\t500\t0",
        })
        response = self._post_save(client, data)
        self.assertEqual(response.status_code, 302)
        fields = PageContent.objects.get(page=self.page).current_payload["fields"]
        self.assertEqual(fields["intro"], "<p>Both groups</p>")
        self.assertEqual(fields["price_rows"]["rows"][0]["cells"][0]["amount"], "500")

    def test_revoked_and_foreign_price_access_mutate_nothing(self):
        PageGrant.objects.filter(staff=self.employee, page=self.page).update(groups=["prices"])
        client = self._client(self.employee)
        editor = self._get(client)
        column_id, row_id = uuid.uuid4(), uuid.uuid4()
        data = {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            "operation_id": str(editor.context["save_operation_id"]),
            "base_generation": str(editor.context["generation"]),
            "base_current_hash": editor.context["base_current_hash"],
            "price.changed": "1",
            "price.column": f"{column_id}\tЦена",
            "price.row": f"{row_id}\tРабота",
            "price.cell": f"{row_id}\t{column_id}\tamount\t100\t0",
        }
        PageGrant.objects.filter(staff=self.employee, page=self.page).update(groups=["text"])
        with patch("modules.pages.web.save_page_content") as command:
            revoked = self._post_save(client, data)
        self.assertEqual(revoked.status_code, 400)
        command.assert_not_called()

        foreign = Page.objects.create(name="Foreign prices", kind=PageKind.SERVICE_DETAIL, position=88)
        Route.objects.create(
            page=foreign,
            target="/foreign-prices/",
            mode=RouteMode.PRIMARY,
            outcome=RouteOutcome.SERVICE_DETAIL,
        )
        foreign_payload = payload()
        PageContent.objects.create(
            page=foreign,
            current_payload=foreign_payload,
            current_hash=canonical_payload_hash(foreign_payload),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )
        foreign_response = client.post(reverse("manage-page-save", args=(foreign.id,)), data=data)
        self.assertEqual(foreign_response.status_code, 403)
        self.assertEqual(PageContent.objects.get(page=self.page).generation, 1)
        self.assertEqual(PageContent.objects.get(page=foreign).generation, 1)

    def test_owner_price_save_preserves_media_usages_and_price_fault_rolls_back(self):
        asset = Asset.objects.create(
            purpose=AssetPurpose.CONTENT,
            source_sha256="a" * 64,
            state=AssetState.READY,
        )
        current = payload()
        current["fields"]["media"]["hero"] = str(asset.id)
        PageContent.objects.filter(page=self.page).update(
            current_payload=current,
            current_hash=canonical_payload_hash(current),
        )
        client = self._client(self.owner)
        editor = self._get(client)
        column_id, row_id = uuid.uuid4(), uuid.uuid4()
        data = self._save_data(editor)
        data.update({
            "price.changed": "1",
            "price.column": f"{column_id}\tЦена",
            "price.row": f"{row_id}\tРабота",
            "price.cell": f"{row_id}\t{column_id}\tamount\t1500\t1",
        })
        response = self._post_save(client, data)
        self.assertEqual(response.status_code, 302)
        usages = set(AssetUsage.objects.values_list("scope", "asset_id", "slot", "position"))
        self.assertEqual(usages, {
            (UsageScope.PAGE_CURRENT, asset.id, "hero", 0),
            (UsageScope.PAGE_PREVIOUS, asset.id, "hero", 0),
        })

        before = PageContent.objects.get(page=self.page)
        before_state = (before.generation, copy.deepcopy(before.current_payload), before.current_hash)
        before_usages = set(AssetUsage.objects.values_list("scope", "asset_id", "slot", "position"))
        retry = self._save_data(self._get(client))
        retry.update({
            "price.changed": "1",
            "price.column": f"{column_id}\tНовая цена",
            "price.row": f"{row_id}\tНовая работа",
            "price.cell": f"{row_id}\t{column_id}\tamount\t2000\t0",
        })
        with patch("modules.pages.commands.append_event", side_effect=RuntimeError("audit")):
            failed = self._post_save(client, retry)
        self.assertEqual(failed.status_code, 503)
        after = PageContent.objects.get(page=self.page)
        self.assertEqual((after.generation, after.current_payload, after.current_hash), before_state)
        self.assertEqual(
            set(AssetUsage.objects.values_list("scope", "asset_id", "slot", "position")),
            before_usages,
        )

    def test_text_grant_on_wrong_kind_has_no_save_and_direct_post_is_forbidden(self):
        page = Page.objects.create(
            name="No text group kind",
            kind=PageKind.LEGACY_EMPTY_MAIN,
            position=3,
        )
        Route.objects.create(
            page=page,
            target="/no-text/",
            mode=RouteMode.PRIMARY,
            outcome=RouteOutcome.LEGACY_EMPTY_MAIN,
        )
        value = minimal_payload(PageKind.LEGACY_EMPTY_MAIN)
        PageContent.objects.create(
            page=page,
            current_payload=value,
            current_hash=canonical_payload_hash(value),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )
        PageGrant.objects.create(staff=self.employee, page=page, groups=["text"])
        client = self._client(self.employee)
        response = client.get(reverse("manage-page-editor", args=(page.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "data-editor-form")
        direct = client.post(
            reverse("manage-page-save", args=(page.id,)),
            data={"csrfmiddlewaretoken": client.cookies["csrftoken"].value},
        )
        self.assertEqual(direct.status_code, 403)

    def test_stale_distinct_operation_returns_private_conflict(self):
        client = self._client(self.owner)
        stale_get = self._get(client)
        current = PageContent.objects.get(page=self.page)
        save_page_content(
            actor_id=self.owner.id,
            session_generation=self.owner.generation,
            page_id=self.page.id,
            operation_id=uuid.uuid4(),
            base_generation=current.generation,
            base_current_hash=current.current_hash,
            changes=payload(intro="<p>Other</p>"),
        )
        response = self._post_save(client, self._save_data(stale_get))
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "Перезагрузить редактор", status_code=409)
        self.assertEqual(PageContent.objects.get(page=self.page).generation, 2)

    def test_owner_undo_uses_independent_operation_and_employee_is_denied(self):
        client = self._client(self.owner)
        saved = self._post_save(client, self._save_data(self._get(client), rich={"intro": "<p>New</p>"}))
        self.assertEqual(saved.status_code, 302)
        editor = self._get(client)
        self.assertNotEqual(editor.context["save_operation_id"], editor.context["undo_operation_id"])
        undo = client.post(
            reverse("manage-page-undo", args=(self.page.id,)),
            data={
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
                "operation_id": str(editor.context["undo_operation_id"]),
                "base_generation": str(editor.context["generation"]),
                "base_current_hash": editor.context["base_current_hash"],
            },
        )
        self.assertEqual(undo.status_code, 302)
        self.assertEqual(PageContent.objects.get(page=self.page).current_payload, self.initial)
        employee_client = self._client(self.employee)
        self._get(employee_client)
        employee = employee_client.post(
            reverse("manage-page-undo", args=(self.page.id,)),
            data={"csrfmiddlewaretoken": employee_client.cookies["csrftoken"].value},
        )
        self.assertEqual(employee.status_code, 403)

    def test_invalid_content_file_and_wrong_content_types_fail_closed(self):
        client = self._client(self.owner)
        editor = self._get(client)
        invalid = self._save_data(editor, rich={"intro": '<p onclick="x">Bad</p>'})
        response = self._post_save(client, invalid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AuditEvent.objects.count(), 0)

        file_data = self._save_data(editor)
        file_data["upload"] = SimpleUploadedFile("x.txt", b"x")
        response = self._post_save(client, file_data)
        self.assertEqual(response.status_code, 400)

        urlencoded = client.post(
            reverse("manage-page-save", args=(self.page.id,)),
            data="operation_id=x",
            content_type="application/x-www-form-urlencoded",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(urlencoded.status_code, 400)
        json_response = client.post(
            reverse("manage-page-save", args=(self.page.id,)),
            data="{}",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(json_response.status_code, 400)

    def test_missing_duplicate_and_cap_violations_invoke_no_command(self):
        client = self._client(self.owner)
        editor = self._get(client)

        missing = self._save_data(editor)
        missing.pop("operation_id")
        with patch("modules.pages.web.save_page_content") as command:
            response = self._post_save(client, missing)
        self.assertEqual(response.status_code, 400)
        command.assert_not_called()

        duplicated = self._save_data(editor)
        duplicated.pop("csrfmiddlewaretoken")
        duplicated["operation_id"] = [duplicated["operation_id"], str(uuid.uuid4())]
        body = encode_multipart(BOUNDARY, duplicated)
        with patch("modules.pages.web.save_page_content") as command:
            response = client.generic(
                "POST",
                reverse("manage-page-save", args=(self.page.id,)),
                body,
                content_type=MULTIPART_CONTENT,
                HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
            )
        self.assertEqual(response.status_code, 400)
        command.assert_not_called()

        for field, value in (
            ("seo.title", "x" * 256),
            ("heading.h1", "bad\nheading"),
            ("seo.description", "e\u0301"),
        ):
            with self.subTest(field=field), patch("modules.pages.web.save_page_content") as command:
                invalid = self._save_data(editor)
                invalid[field] = value
                response = self._post_save(client, invalid)
                self.assertEqual(response.status_code, 400)
                command.assert_not_called()

        with patch("modules.pages.web.save_page_content") as command:
            oversized = self._save_data(editor, rich={"intro": "x" * 1_048_577})
            response = self._post_save(client, oversized)
        self.assertEqual(response.status_code, 400)
        command.assert_not_called()

    def test_operation_conflict_missing_previous_and_undo_method_are_closed(self):
        client = self._client(self.owner)
        editor = self._get(client)
        save_data = self._save_data(editor, rich={"intro": "<p>Saved</p>"})
        saved = self._post_save(client, save_data)
        self.assertEqual(saved.status_code, 302)

        conflict = client.post(
            reverse("manage-page-undo", args=(self.page.id,)),
            data={
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
                "operation_id": save_data["operation_id"],
                "base_generation": save_data["base_generation"],
                "base_current_hash": save_data["base_current_hash"],
            },
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(PageContent.objects.get(page=self.page).generation, 2)

        content = PageContent.objects.get(page=self.page)
        content.previous_payload = None
        content.previous_hash = None
        content.previous_author = None
        content.previous_created_at = None
        content.save()
        no_previous = client.post(
            reverse("manage-page-undo", args=(self.page.id,)),
            data={
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
                "operation_id": str(uuid.uuid4()),
                "base_generation": str(content.generation),
                "base_current_hash": content.current_hash,
            },
        )
        self.assertEqual(no_previous.status_code, 409)
        self.assertEqual(no_previous.content, b"NO_PREVIOUS")

        with patch("modules.pages.web.undo_page_content") as command:
            method = client.get(reverse("manage-page-undo", args=(self.page.id,)))
        self.assertEqual(method.status_code, 405)
        command.assert_not_called()

        with patch("modules.pages.web.undo_page_content") as command:
            csrf_failure = client.post(reverse("manage-page-undo", args=(self.page.id,)), data={})
        self.assertEqual(csrf_failure.status_code, 403)
        command.assert_not_called()

    def test_missing_ready_media_maps_to_constant_503(self):
        value = payload()
        value["fields"]["media"]["hero"] = str(uuid.uuid4())
        PageContent.objects.filter(page=self.page).update(
            current_payload=value,
            current_hash=canonical_payload_hash(value),
        )
        client = self._client(self.owner)
        response = self._post_save(client, self._save_data(self._get(client)))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b"PRIVATE_DATA_UNAVAILABLE")
        self.assertEqual(PageContent.objects.get(page=self.page).generation, 1)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_audit_fault_is_constant_503_and_rolls_back(self):
        client = self._client(self.owner)
        before = copy.deepcopy(PageContent.objects.get(page=self.page).current_payload)
        with patch("modules.pages.commands.append_event", side_effect=RuntimeError("audit")):
            response = self._post_save(client, self._save_data(self._get(client)))
        self.assertEqual(response.status_code, 503)
        content = PageContent.objects.get(page=self.page)
        self.assertEqual(content.current_payload, before)
        self.assertEqual(content.generation, 1)

    def test_csrf_failure_invokes_no_command(self):
        client = self._client(self.owner)
        with patch("modules.pages.web.save_page_content") as command:
            response = client.post(reverse("manage-page-save", args=(self.page.id,)), data={})
        self.assertEqual(response.status_code, 403)
        command.assert_not_called()
