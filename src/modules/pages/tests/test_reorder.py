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

from ..commands import PageCommandError, rename_page, reorder_children
from ..models import Page, PageContent, PageGrant, PageKind, Route, RouteMode, SiteSettings
from ..public import project_public_navigation
from .test_publication import PASSWORD, PublicationFixture


class ReorderFixture(PublicationFixture):
    def make_reorder_fixture(self):
        owner, settings, first = self.make_fixture(published=True)
        second = Page.objects.create(
            name="Second", kind=PageKind.ARTICLE, position=2, is_published=False
        )
        third = Page.objects.create(
            name="Third", kind=PageKind.ARTICLE, position=3, is_published=False
        )
        parent = Page.objects.create(
            name="Parent", kind=PageKind.ARTICLE, position=4, is_published=False
        )
        child_a = Page.objects.create(
            name="Child A", kind=PageKind.ARTICLE, parent=parent, position=0
        )
        child_b = Page.objects.create(
            name="Child B", kind=PageKind.ARTICLE, parent=parent, position=1
        )
        return owner, settings, first, second, third, parent, child_a, child_b


class PageReorderCommandTests(ReorderFixture, TestCase):
    def test_root_and_nonroot_success_write_exact_order_and_safe_audit(self) -> None:
        owner, settings, first, second, third, parent, child_a, child_b = self.make_reorder_fixture()
        root_ids = [page.id for page in Page.objects.filter(parent=None).order_by("position", "id")]
        desired_root = tuple(reversed(root_ids))
        result = reorder_children(
            actor_id=owner.id, session_generation=1,
            base_structure_generation=1, parent_id=None,
            ordered_child_ids=desired_root,
        )
        self.assertEqual((result.structure_generation, result.parent_id, result.count), (2, None, 4))
        self.assertEqual(
            list(Page.objects.filter(parent=None).order_by("position").values_list("id", flat=True)),
            list(desired_root),
        )
        root_event = AuditEvent.objects.get(action=Action.PAGE_REORDERED)
        self.assertEqual(
            (root_event.target_uuid, root_event.detail),
            (desired_root[0], {"generation": 2, "count": 4}),
        )
        nested = reorder_children(
            actor_id=owner.id, session_generation=1,
            base_structure_generation=2, parent_id=parent.id,
            ordered_child_ids=(child_b.id, child_a.id),
        )
        self.assertEqual((nested.structure_generation, nested.parent_id, nested.count), (3, parent.id, 2))
        self.assertEqual(
            list(Page.objects.filter(parent=parent).order_by("position").values_list("id", flat=True)),
            [child_b.id, child_a.id],
        )
        nested_event = AuditEvent.objects.get(
            action=Action.PAGE_REORDERED, detail__generation=3
        )
        self.assertEqual(
            (nested_event.target_uuid, nested_event.detail),
            (child_b.id, {"generation": 3, "count": 2}),
        )

    def test_access_and_input_shape_fail_before_structural_reads(self) -> None:
        owner, settings, first, second, third, parent, child_a, child_b = self.make_reorder_fixture()
        employee = User.objects.create_user(
            username="reorder-employee", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        with patch("modules.pages.commands.SiteSettings.objects.select_for_update") as settings_lock:
            with self.assertRaises(PageCommandError) as raised:
                reorder_children(
                    actor_id=employee.id, session_generation=1,
                    base_structure_generation=1, parent_id=parent.id,
                    ordered_child_ids=(child_a.id, child_b.id),
                )
        self.assertEqual(raised.exception.code, "FORBIDDEN")
        settings_lock.assert_not_called()
        invalid = (
            (True, parent.id, (child_a.id, child_b.id)),
            (1, str(parent.id), (child_a.id, child_b.id)),
            (1, parent.id, (child_a.id, child_a.id)),
            (1, parent.id, (str(child_a.id), child_b.id)),
        )
        for basis, parent_id, children in invalid:
            with self.subTest(basis=basis, parent_id=parent_id), patch(
                "modules.pages.commands.lock_staff_session"
            ) as actor_lock, self.assertRaises(PageCommandError) as raised:
                reorder_children(
                    actor_id=owner.id, session_generation=1,
                    base_structure_generation=basis, parent_id=parent_id,
                    ordered_child_ids=children,
                )
            self.assertEqual(raised.exception.code, "INVALID_PAGE_REORDER")
            actor_lock.assert_not_called()

    def test_noop_empty_and_gapped_single_or_same_order_are_exact(self) -> None:
        owner, settings, first, second, third, parent, child_a, child_b = self.make_reorder_fixture()
        with self.assertRaises(PageCommandError) as raised:
            reorder_children(
                actor_id=owner.id, session_generation=1,
                base_structure_generation=1, parent_id=parent.id,
                ordered_child_ids=(child_a.id, child_b.id),
            )
        self.assertEqual((raised.exception.code, raised.exception.generation), ("NO_CHANGE", 1))
        empty_parent = Page.objects.create(
            name="Empty", kind=PageKind.ARTICLE, position=5
        )
        with self.assertRaises(PageCommandError) as raised:
            reorder_children(
                actor_id=owner.id, session_generation=1,
                base_structure_generation=1, parent_id=empty_parent.id,
                ordered_child_ids=(),
            )
        self.assertEqual(raised.exception.code, "NO_CHANGE")
        Page.objects.filter(pk=child_a.id).update(position=5)
        normalized = reorder_children(
            actor_id=owner.id, session_generation=1,
            base_structure_generation=1, parent_id=parent.id,
            ordered_child_ids=(child_b.id, child_a.id),
        )
        child_a.refresh_from_db(); child_b.refresh_from_db()
        self.assertEqual((normalized.structure_generation, child_b.position, child_a.position), (2, 0, 1))
        event = AuditEvent.objects.get(action=Action.PAGE_REORDERED)
        self.assertEqual(
            (event.target_uuid, event.detail),
            (child_b.id, {"generation": 2, "count": 2}),
        )

    def test_parent_and_exact_child_set_conflicts_are_closed(self) -> None:
        owner, settings, first, second, third, parent, child_a, child_b = self.make_reorder_fixture()
        with self.assertRaises(PageCommandError) as raised:
            reorder_children(
                actor_id=owner.id, session_generation=1,
                base_structure_generation=1, parent_id=uuid.uuid4(),
                ordered_child_ids=(),
            )
        self.assertEqual(raised.exception.code, "PARENT_NOT_FOUND")
        for children in ((child_a.id,), (child_a.id, child_b.id, first.id)):
            with self.subTest(children=children), self.assertRaises(PageCommandError) as raised:
                reorder_children(
                    actor_id=owner.id, session_generation=1,
                    base_structure_generation=1, parent_id=parent.id,
                    ordered_child_ids=children,
                )
            self.assertEqual(raised.exception.code, "CHILD_SET_CONFLICT")
        discovered = (
            (parent.id, parent.parent_id, parent.position),
            ((child_a.id, parent.id, 0), (child_b.id, parent.id, 1)),
        )
        drifted = (
            discovered[0],
            ((child_a.id, parent.id, 0), (child_b.id, parent.id, 2)),
        )
        with patch(
            "modules.pages.commands._reorder_snapshot",
            side_effect=(discovered, drifted),
        ), self.assertRaises(PageCommandError) as raised:
            reorder_children(
                actor_id=owner.id, session_generation=1,
                base_structure_generation=1, parent_id=parent.id,
                ordered_child_ids=(child_b.id, child_a.id),
            )
        self.assertEqual(raised.exception.code, "REORDER_UNAVAILABLE")
        cap_parent = Page.objects.create(
            name="Cap parent", kind=PageKind.ARTICLE, position=5
        )
        Page.objects.bulk_create([
            Page(
                name=f"Cap child {index}", kind=PageKind.ARTICLE,
                parent=cap_parent, position=index,
            )
            for index in range(513)
        ])
        with self.assertRaises(PageCommandError) as raised:
            reorder_children(
                actor_id=owner.id, session_generation=1,
                base_structure_generation=1, parent_id=cap_parent.id,
                ordered_child_ids=(),
            )
        self.assertEqual(raised.exception.code, "REORDER_UNAVAILABLE")
        self.assertEqual(SiteSettings.objects.get().structure_generation, 1)
        self.assertFalse(AuditEvent.objects.exists())

    def test_preserves_parent_routes_content_and_other_groups(self) -> None:
        owner, settings, first, second, third, parent, child_a, child_b = self.make_reorder_fixture()
        Page.objects.filter(pk__in=(child_a.id, child_b.id)).update(is_published=True)
        Route.objects.create(
            page=child_a, target="/child-a/", mode=RouteMode.PRIMARY,
            outcome=PageKind.ARTICLE,
        )
        Route.objects.create(
            page=child_b, target="/child-b/", mode=RouteMode.PRIMARY,
            outcome=PageKind.ARTICLE,
        )
        content = PageContent.objects.get(page=first)
        content.previous_payload = content.current_payload
        content.previous_hash = content.current_hash
        content.previous_author = owner
        content.previous_created_at = content.current_created_at
        content.save()
        employee = User.objects.create_user(
            username="reorder-preserved", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        grant = PageGrant.objects.create(staff=employee, page=first, groups=["text"])
        asset = Asset.objects.create(
            purpose=AssetPurpose.GALLERY_ORIGINAL,
            state=AssetState.READY,
            source_sha256="8" * 64,
        )
        usage = AssetUsage.objects.create(
            asset=asset, scope=UsageScope.PAGE_PREVIOUS,
            target_uuid=first.id, slot="body", position=0,
        )
        album = GalleryAlbum.objects.create(page=first, position=0)
        photo = GalleryPhoto.objects.create(
            album=album, asset=asset, position=0, alt="Preserved"
        )
        before = {
            page.id: Page.objects.values().get(pk=page.id)
            for page in (first, second, third, parent, child_a, child_b)
        }
        routes_before = list(Route.objects.order_by("id").values())
        content_before = PageContent.objects.values().get(page=first)
        grant_before = PageGrant.objects.values().get(pk=grant.id)
        usage_before = AssetUsage.objects.values().get(pk=usage.id)
        gallery_before = (
            GalleryAlbum.objects.values().get(pk=album.id),
            GalleryPhoto.objects.values().get(pk=photo.id),
        )
        settings_before = SiteSettings.objects.values().get(pk=settings.id)
        navigation_before = [item.page_id for item in project_public_navigation()]
        self.assertLess(navigation_before.index(child_a.id), navigation_before.index(child_b.id))
        reorder_children(
            actor_id=owner.id, session_generation=1,
            base_structure_generation=1, parent_id=parent.id,
            ordered_child_ids=(child_b.id, child_a.id),
        )
        for page in (first, second, third, parent):
            self.assertEqual(Page.objects.values().get(pk=page.id), before[page.id])
        for page in (child_a, child_b):
            after = Page.objects.values().get(pk=page.id)
            after["position"] = before[page.id]["position"]
            self.assertEqual(after, before[page.id])
        self.assertEqual(list(Route.objects.order_by("id").values()), routes_before)
        self.assertEqual(PageContent.objects.values().get(page=first), content_before)
        self.assertEqual(PageGrant.objects.values().get(pk=grant.id), grant_before)
        self.assertEqual(AssetUsage.objects.values().get(pk=usage.id), usage_before)
        self.assertEqual(
            (
                GalleryAlbum.objects.values().get(pk=album.id),
                GalleryPhoto.objects.values().get(pk=photo.id),
            ),
            gallery_before,
        )
        settings_after = SiteSettings.objects.values().get(pk=settings.id)
        settings_after["structure_generation"] = settings_before["structure_generation"]
        self.assertEqual(settings_after, settings_before)
        navigation_after = [item.page_id for item in project_public_navigation()]
        self.assertCountEqual(navigation_after, navigation_before)
        self.assertLess(navigation_after.index(child_b.id), navigation_after.index(child_a.id))
        ordered_children = list(
            Page.objects.filter(pk__in=(child_a.id, child_b.id)).order_by("id")
        )
        self.assertEqual(
            [page.parent_id for page in ordered_children],
            [before[page.id]["parent_id"] for page in ordered_children],
        )

    def test_position_headroom_is_checked_before_writes(self) -> None:
        owner, settings, first, second, third, parent, child_a, child_b = self.make_reorder_fixture()
        Page.objects.filter(pk=child_a.id).update(position=2_147_483_644)
        Page.objects.filter(pk=child_b.id).update(position=2_147_483_645)
        boundary = reorder_children(
            actor_id=owner.id, session_generation=1,
            base_structure_generation=1, parent_id=parent.id,
            ordered_child_ids=(child_b.id, child_a.id),
        )
        self.assertEqual((boundary.structure_generation, boundary.count), (2, 2))
        child_b.delete()
        Page.objects.filter(pk=child_a.id).update(position=2_147_483_647)
        with self.assertRaises(PageCommandError) as raised:
            reorder_children(
                actor_id=owner.id, session_generation=1,
                base_structure_generation=2, parent_id=parent.id,
                ordered_child_ids=(child_a.id,),
            )
        self.assertEqual(raised.exception.code, "REORDER_UNAVAILABLE")
        child_a.refresh_from_db()
        self.assertEqual(child_a.position, 2_147_483_647)
        self.assertEqual(SiteSettings.objects.get().structure_generation, 2)
        root_ids = tuple(
            Page.objects.filter(parent=None)
            .order_by("position", "id")
            .values_list("id", flat=True)
        )
        Page.objects.filter(pk=third.id).update(position=2_147_483_647)
        with self.assertRaises(PageCommandError) as raised:
            reorder_children(
                actor_id=owner.id, session_generation=1,
                base_structure_generation=2, parent_id=None,
                ordered_child_ids=tuple(reversed(root_ids)),
            )
        self.assertEqual(raised.exception.code, "REORDER_UNAVAILABLE")
        bulk_parent = Page.objects.create(
            name="Bulk parent", kind=PageKind.ARTICLE, position=6
        )
        bulk_children = Page.objects.bulk_create([
            Page(
                name=f"Bulk child {index}", kind=PageKind.ARTICLE,
                parent=bulk_parent, position=index,
            )
            for index in range(512)
        ])
        result = reorder_children(
            actor_id=owner.id, session_generation=1,
            base_structure_generation=2, parent_id=bulk_parent.id,
            ordered_child_ids=tuple(page.id for page in reversed(bulk_children)),
        )
        self.assertEqual((result.structure_generation, result.count), (3, 512))
        self.assertEqual(
            list(
                Page.objects.filter(parent=bulk_parent)
                .order_by("position")
                .values_list("id", flat=True)
            ),
            [page.id for page in reversed(bulk_children)],
        )
        Page.objects.filter(parent=bulk_parent).delete()
        bulk_parent.delete()
        child_a.delete()
        parent.delete()
        second.delete()
        third.delete()
        Page.objects.filter(pk=first.id).update(position=0)
        root_children = [first, *Page.objects.bulk_create([
            Page(name=f"Root child {index}", kind=PageKind.ARTICLE, position=index)
            for index in range(1, 512)
        ])]
        root_result = reorder_children(
            actor_id=owner.id, session_generation=1,
            base_structure_generation=3, parent_id=None,
            ordered_child_ids=tuple(page.id for page in reversed(root_children)),
        )
        self.assertEqual((root_result.structure_generation, root_result.count), (4, 512))
        self.assertEqual(
            list(Page.objects.order_by("position").values_list("id", flat=True)),
            [page.id for page in reversed(root_children)],
        )

    def test_page_settings_and_audit_faults_roll_back_all_positions(self) -> None:
        owner, settings, first, second, third, parent, child_a, child_b = self.make_reorder_fixture()
        before = list(Page.objects.order_by("id").values_list("id", "parent_id", "position"))
        for target in (
            "modules.pages.commands.Page.save",
            "modules.pages.commands.SiteSettings.save",
            "modules.pages.commands.append_event",
        ):
            with self.subTest(target=target), patch(target, side_effect=DatabaseError("fault")):
                with self.assertRaises(DatabaseError):
                    reorder_children(
                        actor_id=owner.id, session_generation=1,
                        base_structure_generation=1, parent_id=parent.id,
                        ordered_child_ids=(child_b.id, child_a.id),
                    )
            self.assertEqual(
                list(Page.objects.order_by("id").values_list("id", "parent_id", "position")),
                before,
            )
            self.assertEqual(SiteSettings.objects.get().structure_generation, 1)
            self.assertFalse(AuditEvent.objects.exists())


class PageReorderConcurrencyTests(ReorderFixture, TransactionTestCase):
    reset_sequences = True

    def test_one_structure_base_has_one_reorder_winner(self) -> None:
        owner, settings, first, second, third, parent, child_a, child_b = self.make_reorder_fixture()
        barrier = threading.Barrier(2, timeout=10)

        def run_reorder() -> str:
            close_old_connections()
            try:
                barrier.wait()
                reorder_children(
                    actor_id=owner.id, session_generation=1,
                    base_structure_generation=1, parent_id=parent.id,
                    ordered_child_ids=(child_b.id, child_a.id),
                )
                return "OK"
            except PageCommandError as exc:
                return exc.code
            finally:
                close_old_connections()

        def run_rename() -> str:
            close_old_connections()
            try:
                barrier.wait()
                rename_page(
                    actor_id=owner.id, session_generation=1,
                    page_id=parent.id, base_structure_generation=1,
                    name="Renamed parent",
                )
                return "OK"
            except PageCommandError as exc:
                return exc.code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            reorder_future = pool.submit(run_reorder)
            rename_future = pool.submit(run_rename)
            outcomes = [reorder_future.result(timeout=15), rename_future.result(timeout=15)]
        self.assertCountEqual(outcomes, ["OK", "STALE_STRUCTURE"])
        self.assertEqual(SiteSettings.objects.get().structure_generation, 2)
        self.assertEqual(
            AuditEvent.objects.filter(
                action__in=(Action.PAGE_REORDERED, Action.PAGE_RENAMED)
            ).count(),
            1,
        )
