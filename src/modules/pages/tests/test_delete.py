from __future__ import annotations

import copy
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.db import DatabaseError, IntegrityError, close_old_connections, connection, models
from django.test import TransactionTestCase
from django.utils import timezone

from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent
from modules.gallery.models import GalleryAlbum
from modules.media.models import Asset, AssetFile, AssetPurpose, AssetState, AssetUsage, FileKind, MediaType, UsageScope
from modules.media import api as media_api

from .. import commands as page_commands
from ..commands import PageCommandError, delete_leaf_page, load_page_delete_preview, rename_page, save_page_content, undo_page_content
from ..content import canonical_payload_hash
from ..models import Page, PageContent, PageGrant, PageKind, Route, SiteSettings
from .test_publication import PASSWORD, PublicationFixture


class PageDeleteCommandTests(PublicationFixture, TransactionTestCase):
    reset_sequences = True
    def _values(self):
        owner, settings, page = self.make_fixture()
        preview = load_page_delete_preview(
            actor_id=owner.id, session_generation=1, page_id=page.id,
        )
        return owner, settings, page, preview, {
            "actor_id": owner.id, "session_generation": 1, "page_id": page.id,
            "base_structure_generation": preview.structure_generation,
            "expected_name": preview.name, "expected_primary_path": preview.primary_path,
            "expected_composition_digest": preview.composition_digest,
            "current_password": PASSWORD,
        }

    def test_success_removes_exact_aggregate_and_preserves_assets(self):
        owner, settings, page, preview, values = self._values()
        employee = User.objects.create_user(username="delete-grant", password=PASSWORD, role=StaffRole.EMPLOYEE)
        PageGrant.objects.create(staff=employee, page=page, groups=["text"])
        current_asset = Asset.objects.create(purpose=AssetPurpose.CONTENT, state=AssetState.READY, source_sha256="7" * 64)
        previous_asset = Asset.objects.create(purpose=AssetPurpose.CONTENT, state=AssetState.READY, source_sha256="8" * 64)
        file = AssetFile.objects.create(
            asset=current_asset, kind=FileKind.MAIN,
            storage_key=f"img/{current_asset.id}/main.png", sha256="9" * 64,
            byte_size=1, mime_type=MediaType.PNG,
        )
        content = PageContent.objects.get(page=page)
        current = content.current_payload.copy(); current["fields"] = content.current_payload["fields"].copy()
        current["fields"]["media"] = {"hero": str(current_asset.id), "body": [], "works": []}
        previous = current.copy(); previous["fields"] = current["fields"].copy()
        previous["fields"]["media"] = {"hero": str(previous_asset.id), "body": [], "works": []}
        content.current_payload = current; content.current_hash = canonical_payload_hash(current)
        content.previous_payload = previous; content.previous_hash = canonical_payload_hash(previous)
        content.previous_author = owner; content.previous_created_at = timezone.now()
        content.save()
        for scope, asset in ((UsageScope.PAGE_CURRENT, current_asset), (UsageScope.PAGE_PREVIOUS, previous_asset)):
            AssetUsage.objects.create(asset=asset, scope=scope, target_uuid=page.id, slot="hero", position=0)
        unrelated = AssetUsage.objects.create(asset=current_asset, scope=UsageScope.SITE_SETTINGS, target_uuid=uuid.uuid4(), slot="logo", position=0)
        preview = load_page_delete_preview(actor_id=owner.id, session_generation=1, page_id=page.id)
        values.update(expected_composition_digest=preview.composition_digest)
        result = delete_leaf_page(**values)
        self.assertEqual((result.page_id, result.structure_generation, result.already_deleted), (page.id, 2, False))
        self.assertFalse(Page.objects.filter(pk=page.id).exists())
        self.assertFalse(Route.objects.filter(page_id=page.id).exists())
        self.assertFalse(PageContent.objects.filter(page_id=page.id).exists())
        self.assertFalse(PageGrant.objects.filter(page_id=page.id).exists())
        self.assertEqual(Asset.objects.filter(pk__in=(current_asset.id, previous_asset.id)).count(), 2)
        self.assertTrue(AssetFile.objects.filter(pk=file.id).exists())
        self.assertFalse(AssetUsage.objects.filter(target_uuid=page.id).exists())
        self.assertTrue(AssetUsage.objects.filter(pk=unrelated.id).exists())
        event = AuditEvent.objects.get(action=Action.PAGE_DELETED)
        self.assertEqual((event.target_uuid, event.detail), (page.id, {"generation": 2}))

    def test_password_role_stale_and_confirmation_are_closed(self):
        owner, settings, page, preview, values = self._values()
        employee = User.objects.create_user(username="delete-employee", password=PASSWORD, role=StaffRole.EMPLOYEE)
        for changes, code in (
            ({"actor_id": employee.id}, "FORBIDDEN"),
            ({"current_password": "wrong"}, "CURRENT_PASSWORD_INVALID"),
            ({"base_structure_generation": 2}, "STALE_STRUCTURE"),
            ({"expected_name": "wrong"}, "DELETE_CONFIRMATION_STALE"),
            ({"expected_primary_path": "/wrong/"}, "DELETE_CONFIRMATION_STALE"),
            ({"expected_composition_digest": "0" * 64}, "DELETE_CONFIRMATION_STALE"),
        ):
            with self.subTest(code=code), self.assertRaises(PageCommandError) as raised:
                delete_leaf_page(**{**values, **changes})
            self.assertEqual(raised.exception.code, code)
        self.assertTrue(Page.objects.filter(pk=page.id).exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_child_and_gallery_are_refused(self):
        owner, settings, page, preview, values = self._values()
        Page.objects.create(name="Child", kind=PageKind.ARTICLE, parent=page, position=0)
        with self.assertRaises(PageCommandError) as raised:
            delete_leaf_page(**values)
        self.assertEqual(raised.exception.code, "PAGE_HAS_CHILDREN")
        Page.objects.filter(parent=page).delete()
        album = GalleryAlbum.objects.create(page=page, position=0)
        with self.assertRaises(PageCommandError) as raised:
            delete_leaf_page(**values)
        self.assertEqual(raised.exception.code, "DELETE_UNAVAILABLE")
        self.assertTrue(Page.objects.filter(pk=page.id).exists())
        self.assertTrue(PageContent.objects.filter(page=page).exists())
        album.delete()
        page.kind = PageKind.GALLERY_ALBUM; page.save(update_fields=("kind",))
        with self.assertRaises(PageCommandError) as raised:
            load_page_delete_preview(actor_id=owner.id, session_generation=1, page_id=page.id)
        self.assertEqual(raised.exception.code, "GALLERY_DELETE_REQUIRED")

    def test_lost_response_replay_is_uuid_and_audit_bound(self):
        owner, settings, page, preview, values = self._values()
        first = delete_leaf_page(**values)
        second = delete_leaf_page(**values)
        self.assertTrue(second.already_deleted)
        self.assertEqual(second.structure_generation, first.structure_generation)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_DELETED).count(), 1)
        event = AuditEvent.objects.get(action=Action.PAGE_DELETED)
        event.actor_role = StaffRole.EMPLOYEE; event.save(update_fields=("actor_role",))
        with self.assertRaises(PageCommandError) as raised:
            delete_leaf_page(**values)
        self.assertEqual(raised.exception.code, "DELETE_UNAVAILABLE")
        event.actor_role = StaffRole.OWNER; event.actor_uuid = uuid.uuid4()
        event.save(update_fields=("actor_role", "actor_uuid"))
        with self.assertRaises(PageCommandError) as raised:
            delete_leaf_page(**values)
        self.assertEqual(raised.exception.code, "DELETE_UNAVAILABLE")
        with self.assertRaises(PageCommandError) as raised:
            delete_leaf_page(**{**values, "page_id": uuid.uuid4()})
        self.assertEqual(raised.exception.code, "PAGE_NOT_FOUND")

    def test_composition_drift_and_corruption_fail_closed(self):
        owner, settings, page, preview, values = self._values()
        Route.objects.filter(page=page).update(target="/changed/")
        with self.assertRaises(PageCommandError) as raised:
            delete_leaf_page(**values)
        self.assertEqual(raised.exception.code, "DELETE_CONFIRMATION_STALE")
        Route.objects.filter(page=page).delete()
        with self.assertRaises(PageCommandError) as raised:
            load_page_delete_preview(actor_id=owner.id, session_generation=1, page_id=page.id)
        self.assertEqual(raised.exception.code, "DELETE_UNAVAILABLE")
        Route.objects.create(page=page, target="/home/", mode="PRIMARY", outcome=PageKind.HOME)
        page.kind = PageKind.HOME; page.save(update_fields=("kind",))
        content = PageContent.objects.get(page=page)
        empty = page_commands._initial_payload(PageKind.HOME, "Home")
        content.current_payload = empty; content.current_hash = canonical_payload_hash(empty)
        content.previous_payload = copy.deepcopy(empty); content.previous_hash = canonical_payload_hash(empty)
        content.previous_author = owner; content.previous_created_at = timezone.now(); content.save()
        for ref_name in ("service_refs", "brand_refs", "review_refs"):
            candidate = copy.deepcopy(empty); candidate["fields"][ref_name] = [str(uuid.uuid4())]
            with self.subTest(writer="save", ref=ref_name), self.assertRaises(PageCommandError) as raised:
                save_page_content(
                    actor_id=owner.id, session_generation=1, page_id=page.id,
                    operation_id=uuid.uuid4(), base_generation=content.generation,
                    base_current_hash=content.current_hash, changes=candidate,
                )
            self.assertEqual(raised.exception.code, "INVALID_CONTENT")
        content.refresh_from_db()
        previous = copy.deepcopy(empty); previous["fields"]["service_refs"] = [str(uuid.uuid4())]
        content.previous_payload = previous; content.previous_hash = canonical_payload_hash(previous); content.save()
        with self.assertRaises(PageCommandError) as raised:
            undo_page_content(
                actor_id=owner.id, session_generation=1, page_id=page.id,
                operation_id=uuid.uuid4(), base_generation=content.generation,
                base_current_hash=content.current_hash,
            )
        self.assertEqual(raised.exception.code, "INVALID_CONTENT")

    def test_fault_rolls_back_everything(self):
        owner, settings, page, preview, values = self._values()
        with patch("modules.pages.commands.append_event", side_effect=DatabaseError("fault")):
            with self.assertRaises(DatabaseError):
                delete_leaf_page(**values)
        self.assertTrue(Page.objects.filter(pk=page.id).exists())
        self.assertTrue(Route.objects.filter(page=page).exists())
        self.assertTrue(PageContent.objects.filter(page=page).exists())
        self.assertEqual(SiteSettings.objects.get().structure_generation, 1)

    def test_invalid_input_and_missing_settings_are_closed(self):
        owner, settings, page, preview, values = self._values()
        for changes in ({"base_structure_generation": True}, {"expected_composition_digest": "x"}, {"current_password": ""}):
            with self.assertRaises(PageCommandError):
                delete_leaf_page(**{**values, **changes})
        Route.objects.create(page=page, target="/extra/", mode="ALIAS", outcome=page.kind)
        with patch("modules.pages.commands._DELETE_ROUTE_CAP", 1), self.assertRaises(PageCommandError) as raised:
            load_page_delete_preview(actor_id=owner.id, session_generation=1, page_id=page.id)
        self.assertEqual(raised.exception.code, "DELETE_UNAVAILABLE")
        self.assertEqual(page_commands._DELETE_ROUTE_CAP, 512)
        self.assertEqual(page_commands._DELETE_GRANT_CAP, 100)
        self.assertEqual(media_api._PAGE_DELETE_USAGE_CAP, 128)
        Route.objects.filter(page=page, mode="ALIAS").delete()
        employees = [
            User(username=f"cap-{index}", password="!", role=StaffRole.EMPLOYEE,
                 is_staff=True, is_active=True, is_superuser=False)
            for index in range(2)
        ]
        User.objects.bulk_create(employees)
        PageGrant.objects.bulk_create([
            PageGrant(staff=employee, page=page, groups=["text"]) for employee in employees
        ])
        with patch("modules.pages.commands._DELETE_GRANT_CAP", 1), self.assertRaises(PageCommandError) as raised:
            load_page_delete_preview(actor_id=owner.id, session_generation=1, page_id=page.id)
        self.assertEqual(raised.exception.code, "DELETE_UNAVAILABLE")
        PageGrant.objects.filter(page=page).delete(); User.objects.filter(pk__in=[row.pk for row in employees]).delete()
        assets = [
            Asset(purpose=AssetPurpose.CONTENT, state=AssetState.READY, source_sha256=f"{index + 1}" * 64)
            for index in range(2)
        ]
        Asset.objects.bulk_create(assets)
        content = PageContent.objects.get(page=page)
        payload = content.current_payload.copy(); payload["fields"] = content.current_payload["fields"].copy()
        payload["fields"]["media"] = {"hero": None, "body": [str(row.id) for row in assets], "works": []}
        content.current_payload = payload; content.current_hash = canonical_payload_hash(payload); content.save()
        AssetUsage.objects.bulk_create([
            AssetUsage(asset=asset, scope=UsageScope.PAGE_CURRENT, target_uuid=page.id, slot="body", position=index)
            for index, asset in enumerate(assets)
        ])
        with patch("modules.media.api._PAGE_DELETE_USAGE_CAP", 1), self.assertRaises(PageCommandError) as raised:
            load_page_delete_preview(actor_id=owner.id, session_generation=1, page_id=page.id)
        self.assertEqual(raised.exception.code, "DELETE_UNAVAILABLE")
        with patch("modules.media.api._PAGE_DELETE_USAGE_CAP", 2):
            self.assertEqual(load_page_delete_preview(actor_id=owner.id, session_generation=1, page_id=page.id).current_usage_count, 2)
        initial = page_commands._initial_payload(PageKind.HOME, "Home")
        self.assertEqual([initial["fields"][key] for key in ("service_refs", "brand_refs", "review_refs")], [[], [], []])
        settings.delete()
        with self.assertRaises(PageCommandError) as raised:
            delete_leaf_page(**values)
        self.assertEqual(raised.exception.code, "SETTINGS_MISSING")

    def test_page_reverse_relation_allowlist_is_exact(self):
        actual = {
            relation.get_accessor_name(): relation.field.remote_field.on_delete
            for relation in Page._meta.related_objects
        }
        self.assertEqual(set(actual), {"children", "routes", "content", "grants", "gallery_album"})
        self.assertIs(actual["children"], models.PROTECT)
        self.assertIs(actual["gallery_album"], models.PROTECT)
        for name in ("routes", "content", "grants"):
            self.assertIs(actual[name], models.CASCADE)
        if connection.vendor != "postgresql":
            return
        owner, settings, page, preview, values = self._values()
        barrier = threading.Barrier(2, timeout=10)
        def run_delete():
            close_old_connections(); barrier.wait()
            try:
                delete_leaf_page(**values); return "OK"
            except PageCommandError as exc:
                return exc.code
            finally:
                close_old_connections()
        def run_rename():
            close_old_connections(); barrier.wait()
            try:
                rename_page(actor_id=owner.id, session_generation=1, page_id=page.id,
                            base_structure_generation=1, name="Concurrent"); return "OK"
            except PageCommandError as exc:
                return exc.code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [pool.submit(run_delete), pool.submit(run_rename)]
            outcomes = [future.result(timeout=20) for future in outcomes]
        self.assertEqual(outcomes.count("OK"), 1)
        self.assertTrue(set(outcomes) <= {"OK", "STALE_STRUCTURE", "PAGE_NOT_FOUND"})
        self.assertEqual(SiteSettings.objects.get().structure_generation, 2)
        Page.objects.all().delete(); SiteSettings.objects.all().delete(); AuditEvent.objects.all().delete(); User.objects.all().delete()
        owner, settings, page, preview, values = self._values()
        delete_locked = threading.Event(); child_started = threading.Event()
        original_delete_usages = page_commands.delete_locked_page_usage_snapshot
        def gated_delete(snapshot):
            delete_locked.set()
            if not child_started.wait(timeout=10):
                raise AssertionError("late child did not start")
            return original_delete_usages(snapshot)
        def delete_worker():
            close_old_connections()
            try:
                with patch("modules.pages.commands.delete_locked_page_usage_snapshot", side_effect=gated_delete):
                    delete_leaf_page(**values)
                return "DELETE_OK"
            finally:
                close_old_connections()
        def child_worker():
            close_old_connections(); delete_locked.wait(timeout=10); child_started.set()
            try:
                Page.objects.create(name="Late", kind=PageKind.ARTICLE, parent_id=page.id, position=0)
                return "CHILD_OK"
            except IntegrityError:
                return "FK_REFUSED"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [pool.submit(delete_worker), pool.submit(child_worker)]
            outcomes = [future.result(timeout=20) for future in outcomes]
        self.assertCountEqual(outcomes, ["DELETE_OK", "FK_REFUSED"])
        self.assertFalse(Page.objects.filter(pk=page.id).exists())
        self.assertFalse(Page.objects.filter(parent_id=page.id).exists())
