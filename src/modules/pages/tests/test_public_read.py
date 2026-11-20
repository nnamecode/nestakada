from __future__ import annotations

import inspect
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from modules.media.models import Asset, AssetPurpose, AssetState

from .. import public as public_api
from ..models import Page, PageKind, Route, RouteMode, RouteOutcome, SiteSettings
from ..public import (
    PublicBlank,
    PublicPage,
    PublicReadError,
    PublicRedirect,
    project_public_navigation,
    resolve_public_target,
)


class PublicReadFixture:
    def make_settings(self) -> SiteSettings:
        logo = Asset.objects.create(
            purpose=AssetPurpose.SITE_ASSET,
            state=AssetState.READY,
            source_sha256="9" * 64,
        )
        return SiteSettings.objects.create(
            organization_name="Эстакада",
            phone_display="+7 499 110-25-52",
            phone_e164="+74991102552",
            address="Москва",
            opening_hours="Ежедневно",
            contact_email="owner@example.test",
            map_url="https://example.test/map",
            logo_asset=logo,
        )

    def make_page(
        self,
        *,
        name: str,
        target: str | None,
        position: int,
        parent: Page | None = None,
        published: bool = True,
    ) -> Page:
        page = Page.objects.create(
            name=name,
            kind=PageKind.ARTICLE,
            parent=parent,
            position=position,
            is_published=published,
        )
        if target is not None:
            Route.objects.create(
                page=page,
                target=target,
                mode=RouteMode.PRIMARY,
                outcome=RouteOutcome.ARTICLE,
            )
        return page


class PublicReadTests(PublicReadFixture, TestCase):
    def setUp(self) -> None:
        self.settings = self.make_settings()

    def test_hidden_primary_and_alias_are_fieldless_one_statement_blank(self) -> None:
        page = self.make_page(name="Private", target="/private/", position=1, published=False)
        Route.objects.create(
            page=page,
            target="/private-alias/?x=1",
            mode=RouteMode.ALIAS,
            outcome=RouteOutcome.ARTICLE,
        )
        for target in ("/private/", "/private-alias/?x=1"):
            with self.subTest(target=target), CaptureQueriesContext(connection) as captured:
                result = resolve_public_target(target)
            self.assertIsInstance(result, PublicBlank)
            self.assertFalse(hasattr(result, "__dict__"))
            self.assertEqual(len(captured), 1)
            self.assertNotIn("pages_pagecontent", captured[0]["sql"].lower())

    def test_published_primary_and_alias_return_exact_page_in_three_statements(self) -> None:
        page = self.make_page(name="Article", target="/article/", position=1)
        Route.objects.create(
            page=page,
            target="/article-alias/?page=2",
            mode=RouteMode.ALIAS,
            outcome=RouteOutcome.ARTICLE,
        )
        with CaptureQueriesContext(connection) as captured:
            result = resolve_public_target("/article-alias/?page=2")
        self.assertEqual(len(captured), 3)
        self.assertEqual(
            result,
            PublicPage(
                page.id,
                PageKind.ARTICLE,
                "/article-alias/?page=2",
                "/article/",
                RouteMode.ALIAS,
            ),
        )

    def test_redirect_is_direct_to_same_page_primary_even_when_hidden(self) -> None:
        page = self.make_page(
            name="Hidden", target="/current/", position=1, published=False
        )
        Route.objects.create(
            page=page,
            target="/old/",
            mode=RouteMode.REDIRECT,
            outcome=RouteOutcome.ARTICLE,
        )
        with CaptureQueriesContext(connection) as captured:
            result = resolve_public_target("/old/")
        self.assertEqual(result, PublicRedirect("/current/"))
        self.assertEqual(len(captured), 3)

    def test_malformed_and_unknown_targets_are_not_found_without_approximation(self) -> None:
        for target in (
            "", "relative/", "//host/", "//[", "/a/../b/", "/bad%2/", "/white space/",
        ):
            with self.subTest(target=target), CaptureQueriesContext(connection) as captured:
                with self.assertRaises(PublicReadError) as raised:
                    resolve_public_target(target)
            self.assertEqual(raised.exception.code, "NOT_FOUND")
            self.assertEqual(len(captured), 0)
        with CaptureQueriesContext(connection) as captured:
            with self.assertRaises(PublicReadError) as raised:
                resolve_public_target("/unknown/")
        self.assertEqual(raised.exception.code, "NOT_FOUND")
        self.assertEqual(len(captured), 1)

    def test_missing_or_wrong_primary_fails_closed(self) -> None:
        page = self.make_page(name="Article", target=None, position=1)
        Route.objects.create(
            page=page,
            target="/alias/",
            mode=RouteMode.ALIAS,
            outcome=RouteOutcome.ARTICLE,
        )
        with self.assertRaises(PublicReadError) as raised:
            resolve_public_target("/alias/")
        self.assertEqual(raised.exception.code, "UNAVAILABLE")
        primary = Route.objects.create(
            page=page,
            target="/article/",
            mode=RouteMode.PRIMARY,
            outcome=RouteOutcome.CONTACTS,
        )
        with self.assertRaises(PublicReadError) as raised:
            resolve_public_target("/alias/")
        self.assertEqual(raised.exception.code, "UNAVAILABLE")
        self.assertTrue(Route.objects.filter(pk=primary.id).exists())

    def test_navigation_has_only_published_pages_in_position_uuid_order(self) -> None:
        later = self.make_page(name="Later", target="/later/", position=2)
        first = self.make_page(name="First", target="/first/", position=1)
        child = self.make_page(
            name="Child", target="/child/", position=0, parent=later
        )
        self.make_page(
            name="Hidden", target=None, position=3, published=False
        )
        with CaptureQueriesContext(connection) as captured:
            result = project_public_navigation()
        self.assertEqual(len(captured), 4)
        self.assertEqual([item.page_id for item in result], [first.id, later.id])
        self.assertEqual(result[1].children[0].page_id, child.id)

    def test_navigation_promotes_through_multiple_hidden_ancestors(self) -> None:
        visible = self.make_page(name="Visible", target="/visible/", position=1)
        hidden1 = self.make_page(
            name="Hidden1", target=None, position=0, parent=visible, published=False
        )
        hidden2 = self.make_page(
            name="Hidden2", target=None, position=0, parent=hidden1, published=False
        )
        leaf = self.make_page(
            name="Leaf", target="/leaf/", position=0, parent=hidden2
        )
        root_hidden = self.make_page(
            name="Root hidden", target=None, position=2, published=False
        )
        promoted_root = self.make_page(
            name="Promoted root", target="/promoted/", position=0,
            parent=root_hidden,
        )
        result = project_public_navigation()
        self.assertEqual(result[0].page_id, promoted_root.id)
        self.assertEqual(result[1].page_id, visible.id)
        self.assertEqual(result[1].children[0].page_id, leaf.id)
        self.assertEqual(Page.objects.get(pk=leaf.id).parent_id, hidden2.id)

    def test_navigation_cycle_and_cap_plus_one_fail_without_partial_tree(self) -> None:
        first = self.make_page(name="First", target="/first/", position=1)
        second = self.make_page(
            name="Second", target="/second/", position=0, parent=first
        )
        Page.objects.filter(pk=first.id).update(parent=second)
        with self.assertRaises(PublicReadError) as raised:
            project_public_navigation()
        self.assertEqual(raised.exception.code, "UNAVAILABLE")
        Page.objects.filter(pk=first.id).update(parent=None)
        for position in range(2, 513):
            self.make_page(
                name=f"Page {position}", target=None, position=position,
                published=False,
            )
        with self.assertRaises(PublicReadError) as raised:
            project_public_navigation()
        self.assertEqual(raised.exception.code, "UNAVAILABLE")

    def test_faults_are_closed_writes_are_zero_and_dag_stays_one_way(self) -> None:
        with patch.object(public_api, "_exact_generation", side_effect=DatabaseError("fault")):
            with self.assertRaises(PublicReadError) as raised:
                project_public_navigation()
        self.assertEqual(raised.exception.code, "UNAVAILABLE")
        source = inspect.getsource(public_api)
        self.assertNotIn("modules.media", source)
        self.assertNotIn("modules.pages.web", source)
        self.assertNotIn("transaction.atomic", source)
        self.assertNotIn("select_for_update", source)
        self.assertNotIn(".save(", source)
        self.assertNotIn(".create(", source)


class PublicReadConcurrencyTests(PublicReadFixture, TransactionTestCase):
    reset_sequences = False

    def test_structure_commit_between_capture_statements_is_unavailable(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL statement snapshots required.")
        settings = self.make_settings()
        page = self.make_page(name="Article", target="/old/", position=1)
        initial_read = threading.Event()
        mutation_done = threading.Event()

        def run_resolver() -> str:
            close_old_connections()
            intercepted = False

            def fence(execute, sql, params, many, context):
                nonlocal intercepted
                result = execute(sql, params, many, context)
                if not intercepted and 'from "pages_route"' in sql.lower():
                    intercepted = True
                    initial_read.set()
                    if not mutation_done.wait(timeout=5):
                        raise RuntimeError("mutation-timeout")
                return result

            try:
                with connection.execute_wrapper(fence):
                    resolve_public_target("/old/")
            except PublicReadError as exc:
                return exc.code
            finally:
                close_old_connections()
            return "ACCEPTED_HYBRID"

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run_resolver)
            self.assertTrue(initial_read.wait(timeout=5))
            with transaction.atomic():
                Route.objects.filter(page=page, mode=RouteMode.PRIMARY).update(
                    target="/new/"
                )
                Route.objects.create(
                    page=page,
                    target="/old/",
                    mode=RouteMode.REDIRECT,
                    outcome=RouteOutcome.ARTICLE,
                )
                locked = SiteSettings.objects.select_for_update().get(pk=settings.pk)
                locked.structure_generation += 1
                locked.save(update_fields=("structure_generation",))
            mutation_done.set()
            self.assertEqual(future.result(timeout=10), "UNAVAILABLE")

        navigation_read = threading.Event()
        navigation_mutation_done = threading.Event()

        def run_navigation() -> str:
            close_old_connections()
            intercepted = False

            def fence(execute, sql, params, many, context):
                nonlocal intercepted
                result = execute(sql, params, many, context)
                if not intercepted and 'from "pages_page"' in sql.lower():
                    intercepted = True
                    navigation_read.set()
                    if not navigation_mutation_done.wait(timeout=5):
                        raise RuntimeError("navigation-mutation-timeout")
                return result

            try:
                with connection.execute_wrapper(fence):
                    project_public_navigation()
            except PublicReadError as exc:
                return exc.code
            finally:
                close_old_connections()
            return "ACCEPTED_HYBRID"

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run_navigation)
            self.assertTrue(navigation_read.wait(timeout=5))
            with transaction.atomic():
                Page.objects.filter(pk=page.id).update(position=2)
                locked = SiteSettings.objects.select_for_update().get(pk=settings.pk)
                locked.structure_generation += 1
                locked.save(update_fields=("structure_generation",))
            navigation_mutation_done.set()
            self.assertEqual(future.result(timeout=10), "UNAVAILABLE")
