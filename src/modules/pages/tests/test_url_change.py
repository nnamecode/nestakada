from __future__ import annotations

import uuid
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase

from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent
from modules.media.models import Asset, AssetPurpose, AssetState, AssetUsage, UsageScope

from ..commands import (
    PageCommandError,
    change_primary_url,
    create_page,
    delete_leaf_page,
    load_page_delete_preview,
    validate_page_create_input,
)
from ..models import Page, PageContent, PageGrant, PageKind, Route, RouteMode, RouteOutcome, SiteSettings
from ..public import PublicBlank, PublicRedirect, resolve_public_target
from .test_publication import PASSWORD, PublicationFixture


class PageUrlChangeCommandTests(PublicationFixture, TestCase):
    def setUp(self) -> None:
        self.owner, self.settings, self.page = self.make_fixture(published=True)
        self.page.primary_url_mutable = True
        self.page.save(update_fields=("primary_url_mutable",))

    def _change(self, path: str, *, basis: int | None = None):
        return change_primary_url(
            actor_id=self.owner.id,
            session_generation=1,
            page_id=self.page.id,
            base_structure_generation=(
                SiteSettings.objects.get().structure_generation if basis is None else basis
            ),
            new_path=path,
        )

    def test_owner_change_preserves_page_and_writes_one_redirect_generation_and_audit(self):
        child = Page.objects.create(
            name="Child", kind=PageKind.ARTICLE, parent=self.page, position=0
        )
        employee = User.objects.create_user(
            username="url-grantee", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        PageGrant.objects.create(staff=employee, page=self.page, groups=["text"])
        asset = Asset.objects.create(
            purpose=AssetPurpose.CONTENT, state=AssetState.READY, source_sha256="9" * 64
        )
        AssetUsage.objects.create(
            asset=asset, scope=UsageScope.PAGE_CURRENT, target_uuid=self.page.id,
            slot="unrelated", position=0,
        )
        Route.objects.create(
            page=self.page, target="/article-alias/", mode=RouteMode.ALIAS,
            outcome=self.page.kind,
        )
        before = Page.objects.values().get(pk=self.page.id)
        content_before = PageContent.objects.values().get(page=self.page)
        grants_before = list(PageGrant.objects.filter(page=self.page).values())
        usages_before = list(AssetUsage.objects.filter(target_uuid=self.page.id).values())
        settings_before = SiteSettings.objects.values().get()
        result = self._change("/article-new/")
        self.page.refresh_from_db(); self.settings.refresh_from_db()
        routes = list(
            Route.objects.filter(page=self.page)
            .exclude(mode=RouteMode.ALIAS)
            .order_by("mode", "target")
        )
        self.assertEqual(
            (result.structure_generation, result.primary_path, result.redirect_path),
            (2, "/article-new/", "/article/"),
        )
        self.assertEqual([(row.mode, row.target) for row in routes], [
            (RouteMode.PRIMARY, "/article-new/"),
            (RouteMode.REDIRECT, "/article/"),
        ])
        after = Page.objects.values().get(pk=self.page.id)
        self.assertEqual(after, before)
        self.assertEqual(Page.objects.values().get(pk=child.id)["parent_id"], self.page.id)
        self.assertEqual(PageContent.objects.values().get(page=self.page), content_before)
        self.assertEqual(list(PageGrant.objects.filter(page=self.page).values()), grants_before)
        self.assertEqual(list(AssetUsage.objects.filter(target_uuid=self.page.id).values()), usages_before)
        settings_after = SiteSettings.objects.values().get()
        self.assertEqual(
            {key: value for key, value in settings_after.items() if key != "structure_generation"},
            {key: value for key, value in settings_before.items() if key != "structure_generation"},
        )
        self.assertTrue(Route.objects.filter(page=self.page, target="/article-alias/", mode=RouteMode.ALIAS).exists())
        event = AuditEvent.objects.get(action=Action.PAGE_URL_CHANGED)
        self.assertEqual((event.target_uuid, event.detail), (self.page.id, {"generation": 2}))

    def test_two_changes_keep_direct_redirects_to_current_primary(self):
        self._change("/article-b/")
        self._change("/article-c/")
        for old in ("/article/", "/article-b/"):
            resolved = resolve_public_target(old)
            self.assertIsInstance(resolved, PublicRedirect)
            self.assertEqual(resolved.primary_target, "/article-c/")
        self.page.is_published = False; self.page.save(update_fields=("is_published",))
        self.assertIsInstance(resolve_public_target("/article/"), PublicRedirect)
        self.assertIsInstance(resolve_public_target("/article-c/"), PublicBlank)

    def test_legacy_is_protected_while_create_and_exact_replay_are_mutable(self):
        self.page.primary_url_mutable = False
        self.page.save(update_fields=("primary_url_mutable",))
        with self.assertRaises(PageCommandError) as raised:
            self._change("/blocked/")
        self.assertEqual(raised.exception.code, "LEGACY_URL_PROTECTED")
        page_id = uuid.uuid4()
        values = dict(
            actor_id=self.owner.id, session_generation=1, page_id=page_id,
            base_structure_generation=1, kind=PageKind.ARTICLE, name="Created",
            parent_id=None, primary_path="/created-url/",
        )
        first = create_page(**values); replay = create_page(**values)
        self.assertTrue(Page.objects.get(pk=page_id).primary_url_mutable)
        self.assertFalse(first.replayed); self.assertTrue(replay.replayed)
        preview = load_page_delete_preview(
            actor_id=self.owner.id, session_generation=1, page_id=page_id,
        )
        delete_leaf_page(
            actor_id=self.owner.id, session_generation=1, page_id=page_id,
            base_structure_generation=2, expected_name=preview.name,
            expected_primary_path=preview.primary_path,
            expected_composition_digest=preview.composition_digest,
            current_password=PASSWORD,
        )
        recreated = create_page(**{**values, "base_structure_generation": 3})
        self.assertFalse(recreated.replayed)
        self.assertTrue(Page.objects.get(pk=page_id).primary_url_mutable)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CREATED, target_uuid=page_id).count(), 2)

    def test_shared_invalid_path_matrix_has_no_write(self):
        invalid = (
            "article", "//host/path", "/x/?q=1", "/x/#f", "/manage/",
            "/%6danage/x", "/%2Fmanage/x", "/%2fMaNaGe/x", "/x/%2e%2e/y",
            "/bad%2", "/bad\\path", "/bad path", "/bad\x01/",
            "/e\u0301/", "/" + "x" * 2048,
        )
        for path in invalid:
            with self.subTest(path=path), self.assertRaises(PageCommandError) as raised:
                self._change(path)
            self.assertEqual(raised.exception.code, "INVALID_PAGE_URL")
        self.assertEqual(Route.objects.get(page=self.page).target, "/article/")
        self.assertEqual(SiteSettings.objects.get().structure_generation, 1)
        for path in ("/%2Fmanage/x", "/%2fMaNaGe/x"):
            with self.assertRaises(PageCommandError) as raised:
                validate_page_create_input(PageKind.ARTICLE, "Created", path)
            self.assertEqual(raised.exception.code, "INVALID_PAGE_CREATE")
        for invalid_id in (self.page.id.hex, str(self.page.id).upper()):
            with self.assertRaises(PageCommandError) as raised:
                change_primary_url(
                    actor_id=self.owner.id, session_generation=1, page_id=invalid_id,
                    base_structure_generation=1, new_path="/canonical/",
                )
            self.assertEqual(raised.exception.code, "PAGE_NOT_FOUND")

    def test_no_change_and_every_occupied_route_mode_are_conflicts_without_write(self):
        with self.assertRaises(PageCommandError) as raised:
            self._change("/article/")
        self.assertEqual(raised.exception.code, "NO_CHANGE")
        other = Page.objects.create(name="Other", kind=PageKind.ARTICLE, position=2)
        for index, mode in enumerate((RouteMode.PRIMARY, RouteMode.ALIAS, RouteMode.REDIRECT)):
            path = f"/occupied-{index}/"
            Route.objects.create(page=other, target=path, mode=mode, outcome=other.kind)
            with self.assertRaises(PageCommandError) as raised:
                self._change(path)
            self.assertEqual(raised.exception.code, "PATH_OCCUPIED")
        wash = Page.objects.create(
            name="Wash", kind=PageKind.SERVICE_DETAIL, position=3,
            primary_url_mutable=True,
        )
        Route.objects.create(page=wash, target="/wash/", mode=RouteMode.PRIMARY,
                             outcome=RouteOutcome.SERVICE_DETAIL)
        Route.objects.create(page=wash, target="/wash.php", mode=RouteMode.ALIAS,
                             outcome=RouteOutcome.SERVICE_WASH_LEGACY_ALIAS)
        changed = change_primary_url(
            actor_id=self.owner.id, session_generation=1, page_id=wash.id,
            base_structure_generation=1, new_path="/wash-new/",
        )
        self.assertEqual(changed.primary_path, "/wash-new/")

    def test_route_ceiling_allows_511_to_512_and_refuses_512(self):
        Route.objects.bulk_create([
            Route(page=self.page, target=f"/old-{index}/", mode=RouteMode.REDIRECT,
                  outcome=self.page.kind)
            for index in range(510)
        ])
        self._change("/at-cap/")
        self.assertEqual(Route.objects.filter(page=self.page).count(), 512)
        with self.assertRaises(PageCommandError) as raised:
            self._change("/over-cap/")
        self.assertEqual(raised.exception.code, "URL_CHANGE_UNAVAILABLE")
        Route.objects.create(page=self.page, target="/pre-existing-513/",
                             mode=RouteMode.REDIRECT, outcome=self.page.kind)
        with self.assertRaises(PageCommandError) as raised:
            self._change("/still-over-cap/")
        self.assertEqual(raised.exception.code, "URL_CHANGE_UNAVAILABLE")

    def test_stale_basis_and_audit_fault_have_at_most_one_committed_winner(self):
        self._change("/winner/", basis=1)
        with self.assertRaises(PageCommandError) as raised:
            self._change("/loser/", basis=1)
        self.assertEqual(raised.exception.code, "STALE_STRUCTURE")
        for index, target in enumerate((
            "modules.pages.commands.Route.clean",
            "modules.pages.commands.Route.save",
            "modules.pages.commands.SiteSettings.save",
            "modules.pages.commands.append_event",
        )):
            before = list(Route.objects.filter(page=self.page).values("target", "mode"))
            with self.subTest(target=target), patch(target, side_effect=DatabaseError("fault")):
                with self.assertRaises(DatabaseError):
                    self._change(f"/rolled-back-{index}/", basis=2)
            self.assertEqual(list(Route.objects.filter(page=self.page).values("target", "mode")), before)
            self.assertEqual(SiteSettings.objects.get().structure_generation, 2)

    def test_delete_composition_digest_covers_mutability_marker(self):
        first = load_page_delete_preview(
            actor_id=self.owner.id, session_generation=1, page_id=self.page.id,
        )
        self.page.primary_url_mutable = False
        self.page.save(update_fields=("primary_url_mutable",))
        second = load_page_delete_preview(
            actor_id=self.owner.id, session_generation=1, page_id=self.page.id,
        )
        self.assertNotEqual(first.composition_digest, second.composition_digest)
