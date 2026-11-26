from __future__ import annotations

import ast
import dataclasses
import importlib.util
import inspect
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from modules.media.models import Asset, AssetPurpose, AssetState

from .. import public as public_api
from ..content import canonical_payload_hash
from ..models import Page, PageContent, PageKind, Route, RouteMode, RouteOutcome, SiteSettings
from ..public import (
    PublicBlank,
    PublicEmptyDocument,
    PublicLegacyTextDocument,
    PublicPage,
    PublicPartnerLinksDocument,
    PublicReadError,
    project_legacy_plain,
)


User = get_user_model()


def _payload(kind: str, *, links: int = 0) -> dict:
    fields: dict[str, object] = {
        "seo": {"title": f"SEO {kind}", "description": "Описание", "allow_index": True},
        "heading": {"h1": f"H1 {kind}"},
    }
    if kind == PageKind.LEGACY_PARTNER_LINKS:
        fields["links"] = [
            {"label": f"Партнёр {index}", "https_url": f"https://p{index}.example.test/path"}
            for index in range(links)
        ]
    elif kind in {
        PageKind.LEGACY_UNDER_CONSTRUCTION,
        PageKind.LEGACY_CAMERA_SCHEDULE_TEXT,
    }:
        fields.update({"intro": "<p>Вступление</p>", "body": "<p>Основной текст</p>"})
    return {
        "schema": "estakada.page-content",
        "schema_version": 1,
        "kind": kind,
        "fields": fields,
    }


class LegacyPlainFixture:
    def make_base(self) -> None:
        self.owner = User.objects.create_superuser(username="nesadmin", password=None)
        logo = Asset.objects.create(
            purpose=AssetPurpose.SITE_ASSET,
            state=AssetState.READY,
            source_sha256="8" * 64,
        )
        self.settings = SiteSettings.objects.create(
            organization_name="Эстакада",
            phone_display="+7 499 110-25-52",
            phone_e164="+74991102552",
            address="Москва",
            opening_hours="Ежедневно",
            contact_email="owner@example.test",
            map_url="https://example.test/map",
            logo_asset=logo,
        )
        self.position = 0

    def make_page(
        self,
        kind: str,
        *,
        payload: dict | None = None,
        published: bool = True,
        alias: bool = False,
    ) -> tuple[Page, PublicPage]:
        self.position += 1
        page = Page.objects.create(
            name=f"Page {self.position}",
            kind=kind,
            position=self.position,
            is_published=published,
        )
        primary = f"/plain-{self.position}/"
        Route.objects.create(
            page=page,
            target=primary,
            mode=RouteMode.PRIMARY,
            outcome=kind,
        )
        requested = primary
        requested_mode = RouteMode.PRIMARY
        if alias:
            requested = f"/plain-{self.position}-alias/"
            requested_mode = RouteMode.ALIAS
            Route.objects.create(
                page=page,
                target=requested,
                mode=requested_mode,
                outcome=kind,
            )
        value = payload if payload is not None else _payload(kind)
        PageContent.objects.create(
            page=page,
            current_payload=value,
            current_hash=canonical_payload_hash(value),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )
        return page, PublicPage(page.id, kind, requested, primary, requested_mode)


class LegacyPlainProjectionTests(LegacyPlainFixture, TestCase):
    def setUp(self) -> None:
        self.make_base()

    def test_hidden_stale_public_page_returns_fieldless_blank(self) -> None:
        page, public = self.make_page(PageKind.LEGACY_EMPTY_MAIN, published=False)
        result = project_legacy_plain(public)
        self.assertEqual(result, PublicBlank())
        self.assertFalse(hasattr(result, "page_id"))
        self.assertFalse(hasattr(result, "__dict__"))
        self.assertTrue(PageContent.objects.filter(page=page).exists())

    def test_partner_links_zero_six_and_sixty_four_are_frozen_and_ordered(self) -> None:
        for count in (0, 6, 64):
            with self.subTest(count=count):
                _, public = self.make_page(
                    PageKind.LEGACY_PARTNER_LINKS,
                    payload=_payload(PageKind.LEGACY_PARTNER_LINKS, links=count),
                )
                result = project_legacy_plain(public)
                self.assertIsInstance(result, PublicPartnerLinksDocument)
                self.assertEqual(len(result.links), count)
                self.assertEqual(
                    [(link.label, link.https_url) for link in result.links],
                    [
                        (f"Партнёр {index}", f"https://p{index}.example.test/path")
                        for index in range(count)
                    ],
                )
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    result.h1 = "changed"

    def test_empty_document_contains_only_identity_seo_and_h1(self) -> None:
        page, public = self.make_page(PageKind.LEGACY_EMPTY_MAIN)
        result = project_legacy_plain(public)
        self.assertEqual(
            result,
            PublicEmptyDocument(
                page_id=page.id,
                primary_target=public.primary_target,
                h1="H1 legacy_empty_main",
                seo=public_api.PublicSeo("SEO legacy_empty_main", "Описание", True),
                breadcrumbs=(
                    public_api.PublicServiceLink(page.name, public.primary_target),
                ),
            ),
        )
        self.assertFalse(hasattr(result, "body"))

    def test_both_text_kinds_retain_literal_kind_and_canonical_rich_text(self) -> None:
        for kind in (
            PageKind.LEGACY_UNDER_CONSTRUCTION,
            PageKind.LEGACY_CAMERA_SCHEDULE_TEXT,
        ):
            with self.subTest(kind=kind):
                _, public = self.make_page(kind)
                result = project_legacy_plain(public)
                self.assertIsInstance(result, PublicLegacyTextDocument)
                self.assertEqual((result.kind, result.intro, result.body), (
                    kind, "<p>Вступление</p>", "<p>Основной текст</p>",
                ))

    def test_unsupported_kind_and_caller_identity_drift_fail_closed(self) -> None:
        page, public = self.make_page(PageKind.LEGACY_EMPTY_MAIN)
        cases = (
            PublicPage(page.id, PageKind.ARTICLE, public.requested_target, public.primary_target, public.requested_mode),
            PublicPage(page.id, public.kind, public.requested_target, "/wrong/", public.requested_mode),
            object(),
        )
        for value in cases:
            with self.subTest(value=value), self.assertRaises(PublicReadError) as raised:
                project_legacy_plain(value)
            self.assertEqual(raised.exception.code, "UNAVAILABLE")

    def test_missing_content_bad_hash_invalid_payload_and_kind_mismatch_fail_closed(self) -> None:
        page, public = self.make_page(PageKind.LEGACY_EMPTY_MAIN)
        content = PageContent.objects.get(page=page)
        mutations = (
            {"current_hash": "0" * 64},
            {"current_payload": {"bad": True}, "current_hash": canonical_payload_hash({"bad": True})},
            {"current_payload": _payload(PageKind.LEGACY_PARTNER_LINKS), "current_hash": canonical_payload_hash(_payload(PageKind.LEGACY_PARTNER_LINKS))},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                PageContent.objects.filter(pk=content.pk).update(**mutation)
                with self.assertRaises(PublicReadError) as raised:
                    project_legacy_plain(public)
                self.assertEqual(raised.exception.code, "UNAVAILABLE")
                PageContent.objects.filter(pk=content.pk).update(
                    current_payload=_payload(PageKind.LEGACY_EMPTY_MAIN),
                    current_hash=canonical_payload_hash(_payload(PageKind.LEGACY_EMPTY_MAIN)),
                )
        PageContent.objects.filter(pk=content.pk).delete()
        with self.assertRaises(PublicReadError) as raised:
            project_legacy_plain(public)
        self.assertEqual(raised.exception.code, "UNAVAILABLE")

    def test_primary_and_requested_route_authority_are_revalidated(self) -> None:
        page, public = self.make_page(PageKind.LEGACY_EMPTY_MAIN, alias=True)
        alias = Route.objects.get(page=page, mode=RouteMode.ALIAS)
        cases = (
            ("alias-removed", lambda: alias.delete()),
            ("alias-retargeted", lambda: Route.objects.filter(pk=alias.pk).update(target="/other/")),
            ("alias-mode-changed", lambda: Route.objects.filter(pk=alias.pk).update(mode=RouteMode.REDIRECT)),
            ("primary-drift", lambda: Route.objects.filter(page=page, mode=RouteMode.PRIMARY).update(target="/new-primary/")),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                Route.objects.filter(page=page).exclude(mode=RouteMode.PRIMARY).delete()
                alias = Route.objects.create(
                    page=page,
                    target=public.requested_target,
                    mode=RouteMode.ALIAS,
                    outcome=page.kind,
                )
                Route.objects.filter(page=page, mode=RouteMode.PRIMARY).update(target=public.primary_target)
                mutate()
                with self.assertRaises(PublicReadError) as raised:
                    project_legacy_plain(public)
                self.assertEqual(raised.exception.code, "UNAVAILABLE")

    def test_missing_settings_faults_and_visible_success_use_read_only_queries(self) -> None:
        _, public = self.make_page(PageKind.LEGACY_EMPTY_MAIN)
        with CaptureQueriesContext(connection) as captured:
            project_legacy_plain(public)
        self.assertGreaterEqual(len(captured), 3)
        self.assertTrue(all(sql["sql"].lstrip().upper().startswith("SELECT") for sql in captured))
        with patch.object(
            public_api,
            "_exact_generation",
            side_effect=DatabaseError("fault"),
        ) as exact_generation:
            with self.assertRaises(PublicReadError) as raised:
                project_legacy_plain(public)
        self.assertEqual(raised.exception.code, "UNAVAILABLE")
        self.assertGreaterEqual(exact_generation.call_count, 1)
        SiteSettings.objects.all().delete()
        with self.assertRaises(PublicReadError) as raised:
            project_legacy_plain(public)
        self.assertEqual(raised.exception.code, "UNAVAILABLE")

    def test_static_scope_has_no_http_media_storage_or_write_layer(self) -> None:
        source = inspect.getsource(public_api)
        projection = inspect.getsource(project_legacy_plain)
        self.assertNotIn("modules.pages.web", source)
        tree = ast.parse(source)
        imported_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                dotted = "." * node.level + (node.module or "")
                module = importlib.util.resolve_name(dotted, public_api.__package__)
                imported_modules.append(module)
                if module in {"modules", "modules.media"}:
                    imported_modules.extend(f"{module}.{alias.name}" for alias in node.names)
        media_imports = sorted(
            name for name in imported_modules
            if name == "modules.media" or name.startswith("modules.media.")
        )
        self.assertEqual(media_imports, ["modules.media.api"])
        self.assertNotIn("transaction.atomic", projection)
        self.assertNotIn("select_for_update", projection)
        self.assertNotIn(".save(", projection)
        self.assertNotIn(".create(", projection)


class LegacyPlainProjectionConcurrencyTests(LegacyPlainFixture, TransactionTestCase):
    reset_sequences = False

    def setUp(self) -> None:
        self.make_base()

    def test_hide_committed_before_final_generation_check_is_unavailable(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL statement snapshots required.")
        page, public = self.make_page(PageKind.LEGACY_EMPTY_MAIN)
        initial_read = threading.Event()
        mutation_done = threading.Event()

        def reader() -> str:
            close_old_connections()
            intercepted = False

            def fence(execute, sql, params, many, context):
                nonlocal intercepted
                result = execute(sql, params, many, context)
                if not intercepted and 'from "pages_page"' in sql.lower():
                    intercepted = True
                    initial_read.set()
                    if not mutation_done.wait(timeout=5):
                        raise RuntimeError("mutation-timeout")
                return result

            try:
                with connection.execute_wrapper(fence):
                    project_legacy_plain(public)
            except PublicReadError as exc:
                return exc.code
            finally:
                close_old_connections()
            return "ACCEPTED_STALE"

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(reader)
            self.assertTrue(initial_read.wait(timeout=5))
            with transaction.atomic():
                Page.objects.filter(pk=page.pk).update(is_published=False)
                locked = SiteSettings.objects.select_for_update().get(pk=self.settings.pk)
                locked.structure_generation += 1
                locked.save(update_fields=("structure_generation",))
            mutation_done.set()
            self.assertEqual(future.result(timeout=10), "UNAVAILABLE")
