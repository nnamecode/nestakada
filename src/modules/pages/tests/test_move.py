from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.db import DatabaseError, close_old_connections
from django.test import TestCase, TransactionTestCase

from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent
from modules.gallery.models import GalleryAlbum, GalleryPhoto
from modules.media.models import Asset, AssetPurpose, AssetState, AssetUsage, UsageScope

from ..commands import PageCommandError, move_page
from ..models import Page, PageContent, PageGrant, PageKind, Route, SiteSettings
from ..public import project_public_navigation
from .test_publication import PASSWORD, PublicationFixture


class MoveFixture(PublicationFixture):
    def make_move_fixture(self):
        owner, settings, target = self.make_fixture(published=True)
        source = Page.objects.create(
            name="Source", kind=PageKind.ARTICLE, position=2, is_published=False
        )
        destination = Page.objects.create(
            name="Destination", kind=PageKind.ARTICLE, position=3, is_published=False
        )
        Page.objects.filter(pk=target.id).update(parent=source, position=0)
        target.refresh_from_db()
        source_other = Page.objects.create(
            name="Source other", kind=PageKind.ARTICLE, parent=source, position=1
        )
        destination_first = Page.objects.create(
            name="Destination first", kind=PageKind.ARTICLE,
            parent=destination, position=0,
        )
        return owner, settings, target, source, destination, source_other, destination_first


class PageMoveCommandTests(MoveFixture, TestCase):
    def test_cross_parent_success_preserves_non_structure_and_writes_safe_audit(self) -> None:
        owner, settings, target, source, destination, source_other, destination_first = self.make_move_fixture()
        employee = User.objects.create_user(
            username="preserved-editor", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        grant = target.grants.create(staff=employee, groups=["text"])
        content = PageContent.objects.get(page=target)
        content.previous_payload = content.current_payload
        content.previous_hash = content.current_hash
        content.previous_author = owner
        content.previous_created_at = content.current_created_at
        content.save()
        Route.objects.create(
            page=target, target="/article-alias/", mode="ALIAS", outcome=PageKind.ARTICLE
        )
        Route.objects.create(
            page=target, target="/article-old/", mode="REDIRECT", outcome=PageKind.ARTICLE
        )
        descendant = Page.objects.create(
            name="Descendant", kind=PageKind.ARTICLE, parent=target,
            position=0, is_published=True,
        )
        for route_target, mode in (
            ("/descendant/", "PRIMARY"),
            ("/descendant-alias/", "ALIAS"),
            ("/descendant-old/", "REDIRECT"),
        ):
            Route.objects.create(
                page=descendant, target=route_target, mode=mode,
                outcome=PageKind.ARTICLE,
            )
        asset = Asset.objects.create(
            purpose=AssetPurpose.GALLERY_ORIGINAL,
            state=AssetState.READY,
            source_sha256="7" * 64,
        )
        AssetUsage.objects.create(
            asset=asset, scope=UsageScope.PAGE_PREVIOUS,
            target_uuid=target.id, slot="body", position=0,
        )
        album = GalleryAlbum.objects.create(page=descendant, position=0)
        GalleryPhoto.objects.create(album=album, asset=asset, position=0, alt="Work")
        unrelated = Page.objects.create(
            name="Unrelated", kind=PageKind.ARTICLE, position=4
        )
        page_before = Page.objects.values().get(pk=target.id)
        route_before = list(
            Route.objects.filter(page_id__in=(target.id, descendant.id)).order_by("id").values()
        )
        content_before = PageContent.objects.values().get(page=target)
        grant_before = PageGrant.objects.values().get(pk=grant.id)
        usage_before = list(AssetUsage.objects.filter(target_uuid=target.id).values())
        gallery_before = (
            GalleryAlbum.objects.values().get(pk=album.id),
            list(GalleryPhoto.objects.filter(album=album).values()),
        )
        descendant_before = Page.objects.values().get(pk=descendant.id)
        unrelated_before = Page.objects.values().get(pk=unrelated.id)
        settings_before = SiteSettings.objects.values().get(pk=settings.id)

        result = move_page(
            actor_id=owner.id, session_generation=owner.generation,
            page_id=target.id, base_structure_generation=1,
            destination_parent_id=destination.id,
            before_page_id=destination_first.id,
        )

        target.refresh_from_db(); source_other.refresh_from_db(); destination_first.refresh_from_db()
        self.assertEqual((result.structure_generation, result.parent_id, result.position), (2, destination.id, 0))
        self.assertEqual((target.parent_id, target.position), (destination.id, 0))
        self.assertEqual((destination_first.parent_id, destination_first.position), (destination.id, 1))
        self.assertEqual(source_other.position, 0)
        page_after = Page.objects.values().get(pk=target.id)
        self.assertEqual(
            {**page_after, "parent_id": page_before["parent_id"], "position": page_before["position"]},
            page_before,
        )
        self.assertEqual(
            list(Route.objects.filter(page_id__in=(target.id, descendant.id)).order_by("id").values()),
            route_before,
        )
        self.assertEqual(PageContent.objects.values().get(page=target), content_before)
        self.assertEqual(PageGrant.objects.values().get(pk=grant.id), grant_before)
        self.assertEqual(list(AssetUsage.objects.filter(target_uuid=target.id).values()), usage_before)
        self.assertEqual(
            (
                GalleryAlbum.objects.values().get(pk=album.id),
                list(GalleryPhoto.objects.filter(album=album).values()),
            ),
            gallery_before,
        )
        self.assertEqual(Page.objects.values().get(pk=descendant.id), descendant_before)
        self.assertEqual(Page.objects.values().get(pk=unrelated.id), unrelated_before)
        settings_after = SiteSettings.objects.values().get(pk=settings.id)
        self.assertEqual(
            {**settings_after, "structure_generation": settings_before["structure_generation"]},
            settings_before,
        )
        event = AuditEvent.objects.get(action=Action.PAGE_MOVED)
        self.assertEqual((event.target_uuid, event.detail), (target.id, {"generation": 2}))

    def test_same_parent_move_noop_and_gapped_same_order_normalization(self) -> None:
        owner, settings, target, source, destination, source_other, destination_first = self.make_move_fixture()
        moved = move_page(
            actor_id=owner.id, session_generation=1, page_id=target.id,
            base_structure_generation=1, destination_parent_id=source.id,
            before_page_id=None,
        )
        self.assertEqual((moved.structure_generation, moved.position), (2, 1))
        with self.assertRaises(PageCommandError) as raised:
            move_page(
                actor_id=owner.id, session_generation=1, page_id=target.id,
                base_structure_generation=2, destination_parent_id=source.id,
                before_page_id=None,
            )
        self.assertEqual((raised.exception.code, raised.exception.generation), ("NO_CHANGE", 2))
        Page.objects.filter(pk=target.id).update(position=5)
        normalized = move_page(
            actor_id=owner.id, session_generation=1, page_id=target.id,
            base_structure_generation=2, destination_parent_id=source.id,
            before_page_id=None,
        )
        target.refresh_from_db(); source_other.refresh_from_db()
        self.assertEqual((normalized.structure_generation, source_other.position, target.position), (3, 0, 1))
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_MOVED).count(), 2)
    def test_access_basis_stale_and_missing_target_fail_closed(self) -> None:
        owner, settings, target, source, destination, source_other, destination_first = self.make_move_fixture()
        employee = User.objects.create_user(
            username="editor-move", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        with patch("modules.pages.commands.SiteSettings.objects.select_for_update") as settings_lock:
            with self.assertRaises(PageCommandError) as raised:
                move_page(
                    actor_id=employee.id, session_generation=1, page_id=target.id,
                    base_structure_generation=1, destination_parent_id=None,
                    before_page_id=None,
                )
        self.assertEqual(raised.exception.code, "FORBIDDEN")
        settings_lock.assert_not_called()
        for basis in (True, 0, "1"):
            with self.subTest(basis=basis), self.assertRaises(PageCommandError) as raised:
                move_page(
                    actor_id=owner.id, session_generation=1, page_id=target.id,
                    base_structure_generation=basis, destination_parent_id=None,
                    before_page_id=None,
                )
            self.assertEqual(raised.exception.code, "INVALID_BASIS")
        with self.assertRaises(PageCommandError) as raised:
            move_page(
                actor_id=owner.id, session_generation=1, page_id=target.id,
                base_structure_generation=2, destination_parent_id=None,
                before_page_id=None,
            )
        self.assertEqual((raised.exception.code, raised.exception.generation), ("STALE_STRUCTURE", 1))
        target.delete()
        with self.assertRaises(PageCommandError) as raised:
            move_page(
                actor_id=owner.id, session_generation=1, page_id=target.id,
                base_structure_generation=1, destination_parent_id=None,
                before_page_id=None,
            )
        self.assertEqual(raised.exception.code, "PAGE_NOT_FOUND")
        self.assertFalse(AuditEvent.objects.exists())

    def test_self_descendant_foreign_before_unknown_and_corrupt_ancestry_are_closed(self) -> None:
        owner, settings, target, source, destination, source_other, destination_first = self.make_move_fixture()
        descendant = Page.objects.create(
            name="Descendant", kind=PageKind.ARTICLE, parent=target, position=0
        )
        cases = (
            (target.id, None),
            (descendant.id, None),
            (destination.id, source_other.id),
            (uuid.uuid4(), None),
            (destination.id, uuid.uuid4()),
        )
        for parent_id, before_id in cases:
            with self.subTest(parent_id=parent_id, before_id=before_id), self.assertRaises(PageCommandError) as raised:
                move_page(
                    actor_id=owner.id, session_generation=1, page_id=target.id,
                    base_structure_generation=1, destination_parent_id=parent_id,
                    before_page_id=before_id,
                )
            self.assertIn(raised.exception.code, {"INVALID_PLACEMENT", "TREE_UNAVAILABLE"})
        cycle_peer = Page.objects.create(
            name="Cycle peer", kind=PageKind.ARTICLE, parent=destination, position=1
        )
        Page.objects.filter(pk=destination.id).update(parent=cycle_peer, position=0)
        with self.assertRaises(PageCommandError) as raised:
            move_page(
                actor_id=owner.id, session_generation=1, page_id=target.id,
                base_structure_generation=1, destination_parent_id=destination.id,
                before_page_id=destination_first.id,
            )
        self.assertEqual(raised.exception.code, "TREE_UNAVAILABLE")
        self.assertEqual(SiteSettings.objects.get().structure_generation, 1)
        self.assertFalse(AuditEvent.objects.exists())

    def test_staging_boundaries_root_and_headroom_are_exact(self) -> None:
        owner, settings, target, source, destination, source_other, destination_first = self.make_move_fixture()
        source_other.delete(); destination_first.delete()
        first = move_page(
            actor_id=owner.id, session_generation=1, page_id=target.id,
            base_structure_generation=1, destination_parent_id=destination.id,
            before_page_id=None,
        )
        self.assertEqual((first.parent_id, first.position), (destination.id, 0))
        root_move = move_page(
            actor_id=owner.id, session_generation=1, page_id=target.id,
            base_structure_generation=2, destination_parent_id=None,
            before_page_id=None,
        )
        self.assertIsNone(root_move.parent_id)
        Page.objects.filter(pk=source.id).update(position=10)
        Page.objects.filter(pk=destination.id).update(position=0)
        boundary_target = Page.objects.create(
            name="Boundary target", kind=PageKind.ARTICLE, parent=source, position=0
        )
        boundary_destination_child = Page.objects.create(
            name="Boundary destination child", kind=PageKind.ARTICLE,
            parent=destination, position=0,
        )
        boundary = move_page(
            actor_id=owner.id, session_generation=1, page_id=boundary_target.id,
            base_structure_generation=3,
            destination_parent_id=destination.id, before_page_id=None,
        )
        boundary_target.refresh_from_db(); boundary_destination_child.refresh_from_db()
        self.assertEqual(
            (boundary.structure_generation, boundary_destination_child.position, boundary_target.position),
            (4, 0, 1),
        )
        blocked_source = Page.objects.create(
            name="Blocked source", kind=PageKind.ARTICLE, position=11
        )
        blocked_target = Page.objects.create(
            name="Blocked target", kind=PageKind.ARTICLE,
            parent=blocked_source, position=2_147_483_647,
        )
        blocked_destination = Page.objects.create(
            name="Blocked destination", kind=PageKind.ARTICLE, position=12
        )
        with self.assertRaises(PageCommandError) as raised:
            move_page(
                actor_id=owner.id, session_generation=1, page_id=blocked_target.id,
                base_structure_generation=4,
                destination_parent_id=blocked_destination.id, before_page_id=None,
            )
        self.assertEqual(raised.exception.code, "POSITION_UNAVAILABLE")
        blocked_target.refresh_from_db()
        self.assertEqual((blocked_target.parent_id, blocked_target.position), (blocked_source.id, 2_147_483_647))
        self.assertEqual(SiteSettings.objects.get().structure_generation, 4)

    def test_page_settings_and_audit_faults_roll_back_the_aggregate(self) -> None:
        owner, settings, target, source, destination, source_other, destination_first = self.make_move_fixture()
        before = list(Page.objects.order_by("id").values_list("id", "parent_id", "position"))
        for target_name in (
            "modules.pages.commands.Page.save",
            "modules.pages.commands.SiteSettings.save",
            "modules.pages.commands.append_event",
        ):
            with self.subTest(target=target_name), patch(target_name, side_effect=DatabaseError("fault")):
                with self.assertRaises(DatabaseError):
                    move_page(
                        actor_id=owner.id, session_generation=1, page_id=target.id,
                        base_structure_generation=1,
                        destination_parent_id=destination.id,
                        before_page_id=destination_first.id,
                    )
            self.assertEqual(
                list(Page.objects.order_by("id").values_list("id", "parent_id", "position")),
                before,
            )
            self.assertEqual(SiteSettings.objects.get().structure_generation, 1)
            self.assertFalse(AuditEvent.objects.exists())

    def test_public_navigation_changes_parent_but_preserves_exact_route(self) -> None:
        owner, settings, target = self.make_fixture(published=True)
        source = Page.objects.create(
            name="Hidden", kind=PageKind.ARTICLE, position=2, is_published=False
        )
        destination = Page.objects.create(
            name="Published", kind=PageKind.ARTICLE, position=3, is_published=True
        )
        Route.objects.create(
            page=destination, target="/destination/", mode="PRIMARY", outcome=PageKind.ARTICLE
        )
        Page.objects.filter(pk=target.id).update(parent=source, position=0)
        route_before = Route.objects.get(page=target).target
        before = project_public_navigation()
        self.assertIn(target.id, [item.page_id for item in before])
        move_page(
            actor_id=owner.id, session_generation=1, page_id=target.id,
            base_structure_generation=1,
            destination_parent_id=destination.id, before_page_id=None,
        )
        after = project_public_navigation()
        destination_item = next(item for item in after if item.page_id == destination.id)
        self.assertEqual([item.page_id for item in destination_item.children], [target.id])
        self.assertEqual(Route.objects.get(page=target).target, route_before)


class PageMoveConcurrencyTests(MoveFixture, TransactionTestCase):
    reset_sequences = True

    def test_one_structure_base_has_at_most_one_winner(self) -> None:
        owner, settings, target, source, destination, source_other, destination_first = self.make_move_fixture()
        other_destination = Page.objects.create(
            name="Other destination", kind=PageKind.ARTICLE, position=4
        )
        barrier = threading.Barrier(2, timeout=10)

        def run(destination_id: uuid.UUID) -> str:
            close_old_connections()
            try:
                barrier.wait()
                move_page(
                    actor_id=owner.id, session_generation=1, page_id=target.id,
                    base_structure_generation=1,
                    destination_parent_id=destination_id, before_page_id=None,
                )
                return "OK"
            except PageCommandError as exc:
                return exc.code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(run, (destination.id, other_destination.id)))
        self.assertCountEqual(outcomes, ["OK", "STALE_STRUCTURE"])
        self.assertEqual(SiteSettings.objects.get().structure_generation, 2)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_MOVED).count(), 1)
        unrelated = Page.objects.create(
            name="Unrelated branch", kind=PageKind.ARTICLE, position=5
        )
        unrelated_destination = Page.objects.create(
            name="Unrelated destination", kind=PageKind.ARTICLE, position=6
        )
        move_page(
            actor_id=owner.id, session_generation=1, page_id=unrelated.id,
            base_structure_generation=2,
            destination_parent_id=unrelated_destination.id, before_page_id=None,
        )
        target_before_stale = Page.objects.values().get(pk=target.id)
        with self.assertRaises(PageCommandError) as raised:
            move_page(
                actor_id=owner.id, session_generation=1, page_id=target.id,
                base_structure_generation=2,
                destination_parent_id=source.id, before_page_id=None,
            )
        self.assertEqual((raised.exception.code, raised.exception.generation), ("STALE_STRUCTURE", 3))
        self.assertEqual(Page.objects.values().get(pk=target.id), target_before_stale)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_MOVED).count(), 2)
