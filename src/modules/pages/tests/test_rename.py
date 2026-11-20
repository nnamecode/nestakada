from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.db import DatabaseError, close_old_connections
from django.test import TestCase, TransactionTestCase

from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent

from ..commands import PageCommandError, rename_page
from ..models import Page, SiteSettings
from .test_publication import PASSWORD, PublicationFixture


class PageRenameCommandTests(PublicationFixture, TestCase):
    def test_success_changes_only_name_generation_and_safe_audit(self) -> None:
        owner, settings, page = self.make_fixture()
        page_before = Page.objects.values().get(pk=page.id)
        settings_before = SiteSettings.objects.values().get(pk=settings.id)
        result = rename_page(
            actor_id=owner.id, session_generation=owner.generation, page_id=page.id,
            base_structure_generation=1, name="Новое имя",
        )
        page_after = Page.objects.values().get(pk=page.id)
        settings_after = SiteSettings.objects.values().get(pk=settings.id)
        self.assertEqual((result.structure_generation, result.name), (2, "Новое имя"))
        self.assertEqual({**page_after, "name": page_before["name"]}, page_before)
        self.assertEqual(
            {**settings_after, "structure_generation": settings_before["structure_generation"]},
            settings_before,
        )
        event = AuditEvent.objects.get(action=Action.PAGE_RENAMED)
        self.assertEqual((event.target_uuid, event.detail), (page.id, {"generation": 2}))

    def test_invalid_names_are_closed_without_normalization(self) -> None:
        owner, settings, page = self.make_fixture()
        for name in (None, "", " ", " lead", "trail ", "e\u0301", "bad\nname", "x" * 501):
            with self.subTest(name=repr(name)), self.assertRaises(PageCommandError) as raised:
                rename_page(
                    actor_id=owner.id, session_generation=1, page_id=page.id,
                    base_structure_generation=1, name=name,
                )
            self.assertEqual(raised.exception.code, "INVALID_PAGE_NAME")
        self.assertEqual(Page.objects.get(pk=page.id).name, "Article")
        self.assertFalse(AuditEvent.objects.exists())

    def test_employee_stale_no_change_and_missing_rows_are_closed(self) -> None:
        owner, settings, page = self.make_fixture()
        employee = User.objects.create_user(
            username="editor", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        with patch("modules.pages.commands.SiteSettings.objects.select_for_update") as settings_lock:
            with self.assertRaises(PageCommandError) as raised:
                rename_page(
                    actor_id=employee.id, session_generation=1, page_id=page.id,
                    base_structure_generation=1, name="Employee",
                )
        self.assertEqual(raised.exception.code, "FORBIDDEN")
        settings_lock.assert_not_called()
        for basis, name, code in ((2, "New", "STALE_STRUCTURE"), (1, "Article", "NO_CHANGE")):
            with self.subTest(code=code), self.assertRaises(PageCommandError) as raised:
                rename_page(
                    actor_id=owner.id, session_generation=1, page_id=page.id,
                    base_structure_generation=basis, name=name,
                )
            self.assertEqual(raised.exception.code, code)
        page.delete()
        with self.assertRaises(PageCommandError) as raised:
            rename_page(
                actor_id=owner.id, session_generation=1, page_id=page.id,
                base_structure_generation=1, name="Missing",
            )
        self.assertEqual(raised.exception.code, "PAGE_NOT_FOUND")

    def test_missing_settings_and_invalid_basis_fail_closed(self) -> None:
        owner, settings, page = self.make_fixture()
        for basis in (True, 0, "1"):
            with self.subTest(basis=basis), self.assertRaises(PageCommandError) as raised:
                rename_page(
                    actor_id=owner.id, session_generation=1, page_id=page.id,
                    base_structure_generation=basis, name="New",
                )
            self.assertEqual(raised.exception.code, "INVALID_BASIS")
        settings.delete()
        with self.assertRaises(PageCommandError) as raised:
            rename_page(
                actor_id=owner.id, session_generation=1, page_id=page.id,
                base_structure_generation=1, name="New",
            )
        self.assertEqual(raised.exception.code, "SETTINGS_MISSING")
        with self.assertRaises(PageCommandError) as raised:
            rename_page(
                actor_id=owner.id, session_generation=1, page_id="not-a-uuid",
                base_structure_generation=1, name="New",
            )
        self.assertEqual(raised.exception.code, "PAGE_NOT_FOUND")

    def test_audit_or_database_fault_rolls_back_aggregate(self) -> None:
        owner, settings, page = self.make_fixture()
        for target in (
            "modules.pages.commands.Page.save",
            "modules.pages.commands.SiteSettings.save",
            "modules.pages.commands.append_event",
        ):
            with self.subTest(target=target), patch(target, side_effect=DatabaseError("fault")):
                with self.assertRaises(DatabaseError):
                    rename_page(
                        actor_id=owner.id, session_generation=1, page_id=page.id,
                        base_structure_generation=1, name="New",
                    )
            self.assertEqual(Page.objects.get(pk=page.id).name, "Article")
            self.assertEqual(SiteSettings.objects.get(pk=settings.id).structure_generation, 1)
            self.assertFalse(AuditEvent.objects.exists())


class PageRenameConcurrencyTests(PublicationFixture, TransactionTestCase):
    reset_sequences = True

    def test_one_base_has_one_winner_and_one_stale_loser(self) -> None:
        owner, settings, page = self.make_fixture()
        barrier = threading.Barrier(2, timeout=10)

        def worker(name: str) -> str:
            close_old_connections(); barrier.wait()
            try:
                rename_page(
                    actor_id=owner.id, session_generation=1, page_id=page.id,
                    base_structure_generation=1, name=name,
                )
                return "OK"
            except PageCommandError as exc:
                return exc.code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, name) for name in ("One", "Two")]
            results = [future.result(timeout=20) for future in futures]
        self.assertCountEqual(results, ["OK", "STALE_STRUCTURE"])
        self.assertEqual(SiteSettings.objects.get().structure_generation, 2)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_RENAMED).count(), 1)

        current_name = Page.objects.get(pk=page.id).name
        client = self.client_class()
        client.force_login(owner)
        session = client.session
        session["staff_generation"] = owner.generation
        session.save()
        reader_before_page = threading.Event()
        allow_page_read = threading.Event()
        writer_at_settings_lock = threading.Event()
        writer_acquired_settings = threading.Event()
        original_site_select = SiteSettings.objects.select_for_update
        original_page_select = Page.objects.select_for_update

        class WriterSettingsQuery:
            def __init__(self, queryset):
                self.queryset = queryset

            def get(self, *args, **kwargs):
                writer_at_settings_lock.set()
                result = self.queryset.get(*args, **kwargs)
                writer_acquired_settings.set()
                return result

        def site_select(*args, **kwargs):
            queryset = original_site_select(*args, **kwargs)
            if threading.current_thread().name.startswith("rename-writer"):
                return WriterSettingsQuery(queryset)
            return queryset

        def page_select(*args, **kwargs):
            if threading.current_thread().name.startswith("rename-get"):
                reader_before_page.set()
                if not allow_page_read.wait(timeout=10):
                    raise AssertionError("GET Page read was not released")
            return original_page_select(*args, **kwargs)

        def get_worker() -> bytes:
            close_old_connections()
            try:
                response = client.get(f"/manage/pages/{page.id}/rename/")
                self.assertEqual(response.status_code, 200)
                return response.content
            finally:
                close_old_connections()

        def rename_worker() -> str:
            close_old_connections()
            try:
                result = rename_page(
                    actor_id=owner.id, session_generation=1, page_id=page.id,
                    base_structure_generation=2, name="Final",
                )
                return result.name
            finally:
                close_old_connections()

        with (
            patch.object(SiteSettings.objects, "select_for_update", side_effect=site_select),
            patch.object(Page.objects, "select_for_update", side_effect=page_select),
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="rename-get") as get_pool,
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="rename-writer") as writer_pool,
        ):
            get_future = get_pool.submit(get_worker)
            self.assertTrue(reader_before_page.wait(timeout=10))
            rename_future = writer_pool.submit(rename_worker)
            self.assertTrue(writer_at_settings_lock.wait(timeout=10))
            self.assertFalse(writer_acquired_settings.wait(timeout=1))
            allow_page_read.set()
            body = get_future.result(timeout=20)
            self.assertEqual(rename_future.result(timeout=20), "Final")
        old_pair = (
            f'name="base_structure_generation" value="2"'.encode() in body
            and f'value="{current_name}"'.encode() in body
        )
        new_pair = (
            b'name="base_structure_generation" value="3"' in body
            and b'value="Final"' in body
        )
        self.assertTrue(old_pair)
        self.assertFalse(new_pair)
