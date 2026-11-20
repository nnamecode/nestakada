from __future__ import annotations

import inspect
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.db import DatabaseError, close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent
from modules.media.api import verify_page_current_usages
from modules.media.models import Asset, AssetPurpose, AssetState, AssetUsage, UsageScope

from ..commands import PageCommandError, set_page_publication
from ..content import canonical_payload_hash
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


PASSWORD = "Unique!Publication-2026"


def _payload(asset_id: uuid.UUID | None = None) -> dict:
    return {
        "schema": "estakada.page-content",
        "schema_version": 1,
        "kind": PageKind.ARTICLE,
        "fields": {
            "seo": {"title": "Title", "description": "", "allow_index": True},
            "heading": {"h1": "Heading"},
            "intro": "<p>Intro</p>",
            "body": "<p>Body</p>",
            "media": {
                "hero": None,
                "body": [] if asset_id is None else [str(asset_id)],
                "works": [],
            },
        },
    }


class PublicationFixture:
    def make_fixture(self, *, published: bool = False, asset: Asset | None = None):
        owner = User.objects.create_user(
            username="nesadmin", password=PASSWORD, role=StaffRole.OWNER
        )
        logo = Asset.objects.create(
            purpose=AssetPurpose.SITE_ASSET,
            state=AssetState.READY,
            source_sha256="1" * 64,
        )
        settings = SiteSettings.objects.create(
            organization_name="Эстакада",
            phone_display="+7 499 110-25-52",
            phone_e164="+74991102552",
            address="Москва",
            opening_hours="Ежедневно",
            contact_email="owner@example.test",
            map_url="https://example.test/map",
            logo_asset=logo,
        )
        page = Page.objects.create(
            name="Article",
            kind=PageKind.ARTICLE,
            position=1,
            is_published=published,
        )
        Route.objects.create(
            page=page,
            target="/article/",
            mode=RouteMode.PRIMARY,
            outcome=RouteOutcome.ARTICLE,
        )
        payload = _payload(None if asset is None else asset.id)
        PageContent.objects.create(
            page=page,
            current_payload=payload,
            current_hash=canonical_payload_hash(payload),
            current_author=owner,
            current_created_at=timezone.now(),
        )
        if asset is not None:
            AssetUsage.objects.create(
                asset=asset,
                scope=UsageScope.PAGE_CURRENT,
                target_uuid=page.id,
                slot="body",
                position=0,
            )
        return owner, settings, page


class PublicationCommandTests(PublicationFixture, TestCase):
    def test_publish_changes_only_flag_generation_and_one_safe_audit(self) -> None:
        asset = Asset.objects.create(
            purpose=AssetPurpose.CONTENT, state=AssetState.READY, source_sha256="2" * 64
        )
        owner, settings, page = self.make_fixture(asset=asset)
        employee = User.objects.create_user(
            username="editor", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        grant = PageGrant.objects.create(staff=employee, page=page, groups=["text"])
        child = Page.objects.create(
            name="Child", kind=PageKind.ARTICLE, parent=page, position=0, is_published=True
        )
        content_before = PageContent.objects.values().get(page=page)
        routes_before = list(Route.objects.filter(page=page).values())
        grant_before = PageGrant.objects.values().get(pk=grant.id)
        usages_before = list(AssetUsage.objects.filter(target_uuid=page.id).values())
        result = set_page_publication(
            actor_id=owner.id,
            session_generation=1,
            page_id=page.id,
            base_structure_generation=1,
            desired_published=True,
        )
        page.refresh_from_db(); settings.refresh_from_db()
        self.assertEqual((result.structure_generation, result.is_published), (2, True))
        self.assertTrue(page.is_published)
        self.assertEqual(settings.structure_generation, 2)
        event = AuditEvent.objects.get(action=Action.PAGE_PUBLICATION_CHANGED)
        self.assertEqual(event.detail, {"generation": 2, "state": "PUBLISHED"})
        self.assertEqual(PageContent.objects.values().get(page=page), content_before)
        self.assertEqual(list(Route.objects.filter(page=page).values()), routes_before)
        self.assertEqual(PageGrant.objects.values().get(pk=grant.id), grant_before)
        self.assertEqual(
            list(AssetUsage.objects.filter(target_uuid=page.id).values()), usages_before
        )
        child.refresh_from_db()
        self.assertTrue(child.is_published)

    def test_hide_bypasses_route_content_and_media_integrity(self) -> None:
        owner, settings, page = self.make_fixture(published=True)
        Route.objects.filter(page=page).delete()
        PageContent.objects.filter(page=page).delete()
        with patch("modules.pages.commands.verify_page_current_usages") as verifier:
            result = set_page_publication(
                actor_id=owner.id, session_generation=1, page_id=page.id,
                base_structure_generation=1, desired_published=False,
            )
        self.assertFalse(result.is_published)
        verifier.assert_not_called()

    def test_stale_no_change_invalid_basis_and_employee_are_closed(self) -> None:
        owner, settings, page = self.make_fixture()
        employee = User.objects.create_user(
            username="editor", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        cases = (
            (owner.id, 2, True, "STALE_STRUCTURE"),
            (owner.id, 1, False, "NO_CHANGE"),
            (owner.id, True, True, "INVALID_BASIS"),
            (employee.id, 1, True, "FORBIDDEN"),
        )
        for actor_id, basis, desired, code in cases:
            with self.subTest(code=code), self.assertRaises(PageCommandError) as raised:
                set_page_publication(
                    actor_id=actor_id, session_generation=1, page_id=page.id,
                    base_structure_generation=basis, desired_published=desired,
                )
            self.assertEqual(raised.exception.code, code)
        self.assertFalse(AuditEvent.objects.exists())

    def test_publish_rejects_missing_or_corrupt_content_and_primary(self) -> None:
        owner, settings, page = self.make_fixture()
        content = PageContent.objects.get(page=page)
        original_payload = content.current_payload
        original_hash = content.current_hash

        def publish_error(code: str) -> None:
            with self.assertRaises(PageCommandError) as raised:
                set_page_publication(
                    actor_id=owner.id, session_generation=1, page_id=page.id,
                    base_structure_generation=1, desired_published=True,
                )
            self.assertEqual(raised.exception.code, code)
            self.assertFalse(Page.objects.get(pk=page.id).is_published)

        PageContent.objects.filter(page=page).update(current_hash="0" * 64)
        publish_error("CONTENT_CORRUPT")
        corrupt_payload = {"schema": "wrong"}
        PageContent.objects.filter(page=page).update(
            current_payload=corrupt_payload,
            current_hash=canonical_payload_hash(corrupt_payload),
        )
        publish_error("INVALID_CONTENT")
        PageContent.objects.filter(page=page).update(
            current_payload=original_payload, current_hash=original_hash
        )
        Route.objects.filter(page=page).update(outcome=PageKind.CONTACTS)
        publish_error("ROUTE_CORRUPT")
        Route.objects.filter(page=page).update(outcome=PageKind.ARTICLE)
        Route.objects.filter(page=page).delete()
        publish_error("ROUTE_CORRUPT")
        Route.objects.create(
            page=page, target="/article/", mode=RouteMode.PRIMARY,
            outcome=PageKind.ARTICLE,
        )
        PageContent.objects.filter(page=page).delete()
        publish_error("CONTENT_MISSING")
        self.assertFalse(AuditEvent.objects.exists())

    def test_media_participant_requires_exact_full_projection_and_ready_content(self) -> None:
        asset = Asset.objects.create(
            purpose=AssetPurpose.CONTENT, state=AssetState.READY, source_sha256="2" * 64
        )
        owner, settings, page = self.make_fixture(asset=asset)

        def publish_error(code: str) -> None:
            with self.assertRaises(PageCommandError) as raised:
                set_page_publication(
                    actor_id=owner.id, session_generation=1, page_id=page.id,
                    base_structure_generation=1, desired_published=True,
                )
            self.assertEqual(raised.exception.code, code)
            self.assertFalse(Page.objects.get(pk=page.id).is_published)

        AssetUsage.objects.filter(target_uuid=page.id).update(position=1)
        publish_error("MEDIA_USAGE_MISMATCH")
        AssetUsage.objects.filter(target_uuid=page.id).update(position=0, slot="wrong")
        publish_error("MEDIA_USAGE_MISMATCH")
        AssetUsage.objects.filter(target_uuid=page.id).update(slot="body")
        AssetUsage.objects.filter(target_uuid=page.id).delete()
        publish_error("MEDIA_USAGE_MISMATCH")
        AssetUsage.objects.create(
            asset=asset, scope=UsageScope.PAGE_CURRENT, target_uuid=page.id,
            slot="body", position=0,
        )
        extra = Asset.objects.create(
            purpose=AssetPurpose.CONTENT, state=AssetState.READY, source_sha256="3" * 64
        )
        AssetUsage.objects.create(
            asset=extra, scope=UsageScope.PAGE_CURRENT, target_uuid=page.id,
            slot="works", position=0,
        )
        publish_error("MEDIA_USAGE_MISMATCH")
        AssetUsage.objects.filter(asset=extra).delete()
        asset.purpose = AssetPurpose.SITE_ASSET
        asset.save(update_fields=("purpose",))
        publish_error("MEDIA_NOT_READY")
        asset.purpose = AssetPurpose.CONTENT
        asset.state = AssetState.STAGED
        asset.save(update_fields=("purpose", "state"))
        publish_error("MEDIA_NOT_READY")
        asset.state = AssetState.READY
        asset.save(update_fields=("state",))
        missing_id = uuid.uuid4()
        missing_payload = _payload(missing_id)
        PageContent.objects.filter(page=page).update(
            current_payload=missing_payload,
            current_hash=canonical_payload_hash(missing_payload),
        )
        publish_error("MEDIA_NOT_READY")
        self.assertFalse(AuditEvent.objects.exists())

    def test_media_and_audit_faults_roll_back_flag_and_generation(self) -> None:
        owner, settings, page = self.make_fixture()
        for target in (
            "modules.pages.commands.verify_page_current_usages",
            "modules.pages.commands.append_event",
        ):
            with self.subTest(target=target), patch(target, side_effect=RuntimeError("fault")):
                with self.assertRaises(RuntimeError):
                    set_page_publication(
                        actor_id=owner.id, session_generation=1, page_id=page.id,
                        base_structure_generation=1, desired_published=True,
                    )
            page.refresh_from_db(); settings.refresh_from_db()
            self.assertFalse(page.is_published)
            self.assertEqual(settings.structure_generation, 1)
        with patch(
            "modules.pages.commands.SiteSettings.save",
            side_effect=DatabaseError("fault"),
        ):
            with self.assertRaises(DatabaseError):
                set_page_publication(
                    actor_id=owner.id, session_generation=1, page_id=page.id,
                    base_structure_generation=1, desired_published=True,
                )
        page.refresh_from_db(); settings.refresh_from_db()
        self.assertFalse(page.is_published)
        self.assertEqual(settings.structure_generation, 1)
        self.assertFalse(AuditEvent.objects.exists())

    def test_query_order_and_module_dag_are_literal(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL FOR UPDATE semantics required.")
        asset = Asset.objects.create(
            purpose=AssetPurpose.CONTENT, state=AssetState.READY, source_sha256="2" * 64
        )
        owner, settings, page = self.make_fixture(asset=asset)
        with CaptureQueriesContext(connection) as queries:
            set_page_publication(
                actor_id=owner.id, session_generation=1, page_id=page.id,
                base_structure_generation=1, desired_published=True,
            )
        statements = [query["sql"].lower() for query in queries.captured_queries]

        def locked(fragment: str) -> int:
            return next(
                index for index, statement in enumerate(statements)
                if fragment in statement and "select" in statement and "for update" in statement
            )

        user = locked('"accounts_user"')
        site = locked('"pages_sitesettings"')
        page_row = locked('"pages_page"')
        route = locked('"pages_route"')
        content = locked('"pages_pagecontent"')
        media_asset = locked('"media_asset"')
        usage = locked('"media_assetusage"')
        audit = next(
            index for index, statement in enumerate(statements)
            if 'insert into "audit_auditevent"' in statement
        )
        self.assertLess(user, site)
        self.assertLess(site, page_row)
        self.assertLess(page_row, route)
        self.assertLess(route, content)
        self.assertLess(content, media_asset)
        self.assertLess(media_asset, usage)
        self.assertLess(usage, audit)
        self.assertIn('order by "pages_route"."id" asc', statements[route])
        self.assertIn('order by "media_asset"."id" asc', statements[media_asset])
        self.assertIn(
            'order by "media_assetusage"."slot" asc, '
            '"media_assetusage"."position" asc, '
            '"media_assetusage"."asset_id" asc, '
            '"media_assetusage"."id" asc',
            statements[usage],
        )
        self.assertNotIn("modules.pages", inspect.getsource(__import__("modules.accounts.api", fromlist=["*"])))
        self.assertNotIn("modules.pages", inspect.getsource(__import__("modules.media.api", fromlist=["*"])))


class PublicationConcurrencyTests(PublicationFixture, TransactionTestCase):
    reset_sequences = True

    def test_two_publish_commands_on_one_structure_basis_have_one_winner(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics required.")
        with self.assertRaises(RuntimeError):
            verify_page_current_usages(page_id=uuid.uuid4(), expected_media={})
        owner, settings, page = self.make_fixture()
        barrier = threading.Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return set_page_publication(
                    actor_id=owner.id, session_generation=1, page_id=page.id,
                    base_structure_generation=1, desired_published=True,
                )
            except PageCommandError as exc:
                return exc
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [future.result(timeout=10) for future in (pool.submit(run), pool.submit(run))]
        self.assertEqual(sum(not isinstance(item, Exception) for item in outcomes), 1)
        self.assertEqual([item.code for item in outcomes if isinstance(item, PageCommandError)], ["STALE_STRUCTURE"])
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_PUBLICATION_CHANGED).count(), 1)
