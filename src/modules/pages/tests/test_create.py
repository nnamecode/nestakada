from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.db import DatabaseError, close_old_connections
from django.test import TestCase, TransactionTestCase

from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent
from modules.media.models import Asset, AssetPurpose, AssetState, AssetUsage, UsageScope

from ..commands import PageCommandError, create_page, rename_page
from ..content import validate_payload
from ..models import Page, PageContent, PageKind, Route, RouteMode, SiteSettings
from .test_publication import PASSWORD, PublicationFixture


class PageCreateCommandTests(PublicationFixture, TestCase):
    def test_all_exact_nineteen_kinds_create_closed_empty_aggregate(self) -> None:
        owner, settings, _ = self.make_fixture()
        self.assertEqual(len(PageKind.values), 19)
        for index, kind in enumerate(PageKind.values, start=1):
            page_id = uuid.uuid4()
            result = create_page(
                actor_id=owner.id, session_generation=1, page_id=page_id,
                base_structure_generation=index, kind=kind, name=f"Page {index}",
                parent_id=None, primary_path=f"/created-{index}/",
            )
            page = Page.objects.get(pk=page_id)
            route = Route.objects.get(page=page)
            content = PageContent.objects.get(page=page)
            self.assertEqual(
                (result.page_id, result.structure_generation, result.content_generation, result.replayed),
                (page_id, index + 1, 1, False),
            )
            self.assertEqual((page.kind, page.is_published), (kind, False))
            self.assertEqual((route.mode, route.outcome), (RouteMode.PRIMARY, kind))
            self.assertFalse(any(validate_payload(content.current_payload, kind).values()))
            self.assertFalse(content.current_payload["fields"]["seo"]["allow_index"])
            self.assertIsNone(content.previous_payload)
            self.assertFalse(AssetUsage.objects.filter(target_uuid=page_id).exists())
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CREATED).count(), 19)

    def test_root_parent_empty_and_gapped_groups_append_without_normalization(self) -> None:
        owner, settings, existing = self.make_fixture()
        existing.position = 7; existing.save(update_fields=("position",))
        child = Page.objects.create(
            name="Child", kind=PageKind.ARTICLE, parent=existing, position=4
        )
        root_id, child_id = uuid.uuid4(), uuid.uuid4()
        create_page(
            actor_id=owner.id, session_generation=1, page_id=root_id,
            base_structure_generation=1, kind=PageKind.ARTICLE, name="Root",
            parent_id=None, primary_path="/root-new/",
        )
        create_page(
            actor_id=owner.id, session_generation=1, page_id=child_id,
            base_structure_generation=2, kind=PageKind.ARTICLE, name="Nested",
            parent_id=existing.id, primary_path="/nested-new/",
        )
        self.assertEqual(Page.objects.get(pk=root_id).position, 8)
        self.assertEqual(Page.objects.get(pk=child_id).position, 5)
        self.assertEqual(Page.objects.get(pk=child.id).position, 4)

    def test_old_base_exact_uuid_replay_is_proven_and_mismatch_is_closed(self) -> None:
        owner, settings, original = self.make_fixture()
        page_id = uuid.uuid4()
        values = dict(
            actor_id=owner.id, session_generation=1, page_id=page_id,
            base_structure_generation=1, kind=PageKind.ARTICLE, name="Replay",
            parent_id=None, primary_path="/replay/",
        )
        first = create_page(**values)
        replay = create_page(**values)
        self.assertEqual((first.structure_generation, replay.structure_generation), (2, 2))
        self.assertTrue(replay.replayed)
        self.assertEqual(SiteSettings.objects.get().structure_generation, 2)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CREATED).count(), 1)
        for changes in (
            {"name": "Mismatch"}, {"kind": PageKind.CONTACTS},
            {"parent_id": original.id}, {"primary_path": "/other/"},
        ):
            with self.subTest(changes=changes), self.assertRaises(PageCommandError) as raised:
                create_page(**{**values, **changes})
            self.assertEqual(raised.exception.code, "PAGE_ID_CONFLICT")
        page = Page.objects.get(pk=page_id); content = PageContent.objects.get(page=page)
        page.is_published = True; page.save(update_fields=("is_published",))
        with self.assertRaises(PageCommandError) as raised: create_page(**values)
        self.assertEqual(raised.exception.code, "PAGE_ID_CONFLICT")
        page.is_published = False; page.save(update_fields=("is_published",))
        original_payload = content.current_payload
        content.current_payload = {**original_payload, "schema_version": 2}
        content.save(update_fields=("current_payload",))
        with self.assertRaises(PageCommandError) as raised: create_page(**values)
        self.assertEqual(raised.exception.code, "PAGE_ID_CONFLICT")
        content.current_payload = original_payload; content.save(update_fields=("current_payload",))
        asset = Asset.objects.create(
            purpose=AssetPurpose.CONTENT, state=AssetState.READY, source_sha256="9" * 64
        )
        usage = AssetUsage.objects.create(
            asset=asset, scope=UsageScope.PAGE_CURRENT, target_uuid=page_id,
            slot="body", position=0,
        )
        with self.assertRaises(PageCommandError) as raised: create_page(**values)
        self.assertEqual(raised.exception.code, "CREATE_UNAVAILABLE"); usage.delete()
        event = AuditEvent.objects.get(action=Action.PAGE_CREATED, target_uuid=page_id)
        event.detail = {"generation": 99}; event.save(update_fields=("detail",))
        with self.assertRaises(PageCommandError) as raised: create_page(**values)
        self.assertEqual(raised.exception.code, "PAGE_ID_CONFLICT")
        event.detail = {"generation": 2}; event.save(update_fields=("detail",))
        route = Route.objects.get(page=page); route.delete()
        with self.assertRaises(PageCommandError) as raised: create_page(**values)
        self.assertEqual(raised.exception.code, "PAGE_ID_CONFLICT")

    def test_name_kind_path_and_namespace_validation_are_closed(self) -> None:
        owner, settings, _ = self.make_fixture()
        invalid = (
            ("x" * 256, PageKind.ARTICLE, "/valid/"),
            ("Valid", "unknown", "/valid/"),
            ("Valid", PageKind.ARTICLE, "/manage/new/"),
            ("Valid", PageKind.ARTICLE, "/%6danage/new/"),
            ("Valid", PageKind.ARTICLE, "/manage%2Fnew/"),
            ("Valid", PageKind.ARTICLE, "/a/?x=1"),
            ("Valid", PageKind.ARTICLE, "/a/../b/"),
        )
        for name, kind, path in invalid:
            with self.subTest(path=path), self.assertRaises(PageCommandError):
                create_page(
                    actor_id=owner.id, session_generation=1, page_id=uuid.uuid4(),
                    base_structure_generation=1, kind=kind, name=name,
                    parent_id=None, primary_path=path,
                )
        self.assertEqual(Page.objects.count(), 1)
        with patch.dict(
            "modules.pages.commands.RICH_BY_KIND",
            {PageKind.ARTICLE: {"invalid_rich_field"}},
        ):
            with self.assertRaises(PageCommandError) as raised:
                create_page(
                    actor_id=owner.id, session_generation=1, page_id=uuid.uuid4(),
                    base_structure_generation=1, kind=PageKind.ARTICLE, name="Valid",
                    parent_id=None, primary_path="/registry-drift/",
                )
        self.assertEqual(raised.exception.code, "CREATE_UNAVAILABLE")

    def test_employee_stale_parent_path_and_graph_fail_without_partial_write(self) -> None:
        owner, settings, page = self.make_fixture()
        employee = User.objects.create_user(
            username="employee", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        values = dict(
            session_generation=1, page_id=uuid.uuid4(), base_structure_generation=1,
            kind=PageKind.ARTICLE, name="Create", parent_id=None, primary_path="/create/",
        )
        with patch("modules.pages.commands.SiteSettings.objects.select_for_update") as lock:
            with self.assertRaises(PageCommandError) as raised:
                create_page(actor_id=employee.id, **values)
        self.assertEqual(raised.exception.code, "FORBIDDEN"); lock.assert_not_called()
        for changes, code in (
            ({"base_structure_generation": 2}, "STALE_STRUCTURE"),
            ({"parent_id": uuid.uuid4()}, "INVALID_PARENT"),
            ({"primary_path": "/article/"}, "PATH_OCCUPIED"),
            ({"parent_id": values["page_id"]}, "INVALID_PARENT"),
        ):
            with self.subTest(code=code), self.assertRaises(PageCommandError) as raised:
                create_page(actor_id=owner.id, **{**values, **changes})
            self.assertEqual(raised.exception.code, code)
        self.assertFalse(Page.objects.filter(pk=values["page_id"]).exists())
        cycle_a = Page.objects.create(name="Cycle A", kind=PageKind.ARTICLE, position=20)
        cycle_b = Page.objects.create(name="Cycle B", kind=PageKind.ARTICLE, parent=cycle_a, position=0)
        Page.objects.filter(pk=cycle_a.id).update(parent=cycle_b)
        with self.assertRaises(PageCommandError) as raised:
            create_page(actor_id=owner.id, **values)
        self.assertEqual(raised.exception.code, "CREATE_UNAVAILABLE")
        Page.objects.filter(pk=cycle_a.id).update(parent=None)
        cycle_b.delete(); cycle_a.delete()
        page.position = 2_147_483_647; page.save(update_fields=("position",))
        with self.assertRaises(PageCommandError) as raised:
            create_page(actor_id=owner.id, **values)
        self.assertEqual(raised.exception.code, "CREATE_UNAVAILABLE")
        page.position = 1; page.save(update_fields=("position",))
        Page.objects.bulk_create([
            Page(name=f"Cap {index}", kind=PageKind.ARTICLE, position=index + 100)
            for index in range(511)
        ])
        boundary_id = uuid.uuid4()
        create_page(actor_id=owner.id, **{
            **values, "page_id": boundary_id, "primary_path": "/boundary-512/",
        })
        with self.assertRaises(PageCommandError) as raised:
            create_page(actor_id=owner.id, **{
                **values, "page_id": uuid.uuid4(), "base_structure_generation": 2,
                "primary_path": "/boundary-513/",
            })
        self.assertEqual(raised.exception.code, "CREATE_UNAVAILABLE")

    def test_page_route_content_settings_and_audit_faults_roll_back(self) -> None:
        owner, settings, _ = self.make_fixture()
        targets = (
            "modules.pages.commands.Page.save",
            "modules.pages.commands.Route.save",
            "modules.pages.commands.PageContent.save",
            "modules.pages.commands.SiteSettings.save",
            "modules.pages.commands.append_event",
        )
        for index, target in enumerate(targets):
            page_id = uuid.uuid4(); path = f"/fault-{index}/"
            with self.subTest(target=target), patch(target, side_effect=DatabaseError("fault")):
                with self.assertRaises(DatabaseError):
                    create_page(
                        actor_id=owner.id, session_generation=1, page_id=page_id,
                        base_structure_generation=1, kind=PageKind.ARTICLE,
                        name="Fault", parent_id=None, primary_path=path,
                    )
            self.assertFalse(Page.objects.filter(pk=page_id).exists())
            self.assertFalse(Route.objects.filter(target=path).exists())
            self.assertEqual(SiteSettings.objects.get().structure_generation, 1)
            self.assertFalse(AuditEvent.objects.filter(action=Action.PAGE_CREATED).exists())

    def test_existing_content_routes_and_publication_are_preserved(self) -> None:
        owner, settings, original = self.make_fixture(published=True)
        before_page = Page.objects.values().get(pk=original.id)
        before_route = Route.objects.values().get(page=original)
        before_content = PageContent.objects.values().get(page=original)
        created = uuid.uuid4()
        create_page(
            actor_id=owner.id, session_generation=1, page_id=created,
            base_structure_generation=1, kind=PageKind.ARTICLE, name="Hidden",
            parent_id=None, primary_path="/hidden-created/",
        )
        self.assertEqual(Page.objects.values().get(pk=original.id), before_page)
        self.assertEqual(Route.objects.values().get(page=original), before_route)
        self.assertEqual(PageContent.objects.values().get(page=original), before_content)
        self.assertFalse(Page.objects.get(pk=created).is_published)


class PageCreateConcurrencyTests(PublicationFixture, TransactionTestCase):
    reset_sequences = True

    def test_one_global_base_has_one_create_winner_and_one_stale_loser(self) -> None:
        owner, settings, _ = self.make_fixture()
        barrier = threading.Barrier(2, timeout=10)

        def worker(index: int) -> str:
            close_old_connections(); barrier.wait()
            try:
                create_page(
                    actor_id=owner.id, session_generation=1, page_id=uuid.uuid4(),
                    base_structure_generation=1, kind=PageKind.ARTICLE,
                    name=f"Concurrent {index}", parent_id=None,
                    primary_path=f"/concurrent-{index}/",
                )
                return "OK"
            except PageCommandError as exc:
                return exc.code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result(timeout=20) for future in (
                pool.submit(worker, 1), pool.submit(worker, 2)
            )]
        self.assertCountEqual(results, ["OK", "STALE_STRUCTURE"])
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CREATED).count(), 1)
        self.assertEqual(SiteSettings.objects.get().structure_generation, 2)

        barrier = threading.Barrier(2, timeout=10)

        def create_worker() -> str:
            close_old_connections(); barrier.wait()
            try:
                create_page(
                    actor_id=owner.id, session_generation=1, page_id=uuid.uuid4(),
                    base_structure_generation=2, kind=PageKind.ARTICLE,
                    name="Create versus rename", parent_id=None,
                    primary_path="/create-versus-rename/",
                )
                return "CREATE_OK"
            except PageCommandError as exc:
                return exc.code
            finally:
                close_old_connections()

        def rename_worker() -> str:
            close_old_connections(); barrier.wait()
            try:
                rename_page(
                    actor_id=owner.id, session_generation=1, page_id=Page.objects.order_by("id").first().id,
                    base_structure_generation=2, name="Structural winner",
                )
                return "RENAME_OK"
            except PageCommandError as exc:
                return exc.code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result(timeout=20) for future in (
                pool.submit(create_worker), pool.submit(rename_worker)
            )]
        self.assertIn(results, (["CREATE_OK", "STALE_STRUCTURE"], ["STALE_STRUCTURE", "RENAME_OK"]))
        self.assertEqual(SiteSettings.objects.get().structure_generation, 3)
        self.assertEqual(
            AuditEvent.objects.filter(action__in=(Action.PAGE_CREATED, Action.PAGE_RENAMED)).count(),
            2,
        )
