from __future__ import annotations

import copy
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from modules.audit.models import Action, AuditEvent
from modules.media.models import Asset, AssetPurpose, AssetState, AssetUsage, UsageScope
from modules.pages.commands import PageCommandError, save_page_content, undo_page_content
from modules.pages.content import canonical_payload_hash
from modules.pages.models import Page, PageContent, PageGrant, PageKind


User = get_user_model()


def payload(*, intro: str = "<p>Intro</p>", hero: str | None = None) -> dict:
    return {
        "schema": "estakada.page-content",
        "schema_version": 1,
        "kind": "service_detail",
        "fields": {
            "seo": {"title": "Title", "description": "", "allow_index": True},
            "heading": {"h1": "Heading"},
            "intro": intro,
            "body": "<p>Body</p>",
            "price_rows": {"columns": [], "rows": []},
            "media": {"hero": hero, "body": [], "works": []},
        },
    }


class PageCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner = User.objects.create_superuser(username="nesadmin", password=None)
        cls.employee = User.objects.create_user(
            username="worker",
            role="EMPLOYEE",
            password=None,
        )
        cls.page = Page.objects.create(
            name="Service",
            kind=PageKind.SERVICE_DETAIL,
            position=0,
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
        PageGrant.objects.create(
            staff=cls.employee,
            page=cls.page,
            groups=["text", "prices"],
        )

    def _save(self, *, operation_id=None, changes=None, actor=None, **basis):
        actor = actor or self.owner
        current = PageContent.objects.get(page=self.page)
        return save_page_content(
            actor_id=actor.id,
            session_generation=actor.generation,
            page_id=self.page.id,
            operation_id=operation_id or uuid.uuid4(),
            base_generation=basis.get("base_generation", current.generation),
            base_current_hash=basis.get("base_current_hash", current.current_hash),
            changes=changes or payload(intro="<p>Changed</p>"),
        )

    def _undo(self, *, operation_id=None, actor=None, **basis):
        actor = actor or self.owner
        current = PageContent.objects.get(page=self.page)
        return undo_page_content(
            actor_id=actor.id,
            session_generation=actor.generation,
            page_id=self.page.id,
            operation_id=operation_id or uuid.uuid4(),
            base_generation=basis.get("base_generation", current.generation),
            base_current_hash=basis.get("base_current_hash", current.current_hash),
        )

    def test_owner_save_and_same_action_retry_mutate_once(self) -> None:
        operation_id = uuid.uuid4()
        result = self._save(operation_id=operation_id)
        replay = self._save(operation_id=operation_id, changes={"invalid": True})

        content = PageContent.objects.get(page=self.page)
        self.assertEqual((result.generation, replay.generation), (2, 2))
        self.assertTrue(replay.replayed)
        self.assertEqual(content.previous_payload, self.initial)
        self.assertEqual(content.last_operation_id, operation_id)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CONTENT_SAVED).count(), 1)

    def test_same_operation_id_with_other_action_fails_closed(self) -> None:
        operation_id = uuid.uuid4()
        self._save(operation_id=operation_id)
        with self.assertRaises(PageCommandError) as raised:
            self._undo(operation_id=operation_id)
        self.assertEqual(raised.exception.code, "OPERATION_CONFLICT")
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_different_operation_with_stale_basis_returns_current_result(self) -> None:
        original = PageContent.objects.get(page=self.page)
        self._save()
        with self.assertRaises(PageCommandError) as raised:
            self._save(
                base_generation=original.generation,
                base_current_hash=original.current_hash,
            )
        current = PageContent.objects.get(page=self.page)
        self.assertEqual(raised.exception.code, "STALE_CONTENT")
        self.assertEqual(raised.exception.generation, current.generation)
        self.assertEqual(raised.exception.current_hash, current.current_hash)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_employee_text_patch_preserves_every_protected_field(self) -> None:
        before = PageContent.objects.get(page=self.page).current_payload
        self._save(
            actor=self.employee,
            changes={"text": {"intro": "<p>Employee</p>", "body": "<p>New body</p>"}},
        )
        after = PageContent.objects.get(page=self.page).current_payload
        self.assertEqual(after["fields"]["intro"], "<p>Employee</p>")
        self.assertEqual(after["fields"]["body"], "<p>New body</p>")
        for field in ("seo", "heading", "price_rows", "media"):
            self.assertEqual(after["fields"][field], before["fields"][field])

    def test_employee_forbidden_group_changes_nothing(self) -> None:
        before = PageContent.objects.get(page=self.page)
        with self.assertRaises(PageCommandError) as raised:
            self._save(actor=self.employee, changes={"media": {"hero": None}})
        after = PageContent.objects.get(page=self.page)
        self.assertEqual(raised.exception.code, "FORBIDDEN")
        self.assertEqual(after.generation, before.generation)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_invalid_session_wins_over_malformed_basis(self) -> None:
        with self.assertRaises(PageCommandError) as raised:
            save_page_content(
                actor_id=self.owner.id,
                session_generation=self.owner.generation + 1,
                page_id=self.page.id,
                operation_id="not-a-uuid",
                base_generation="bad",
                base_current_hash="bad",
                changes={},
            )
        self.assertEqual(raised.exception.code, "STALE_SESSION")

    def test_missing_grant_wins_over_malformed_basis(self) -> None:
        PageGrant.objects.filter(staff=self.employee, page=self.page).delete()
        with self.assertRaises(PageCommandError) as raised:
            save_page_content(
                actor_id=self.employee.id,
                session_generation=self.employee.generation,
                page_id=self.page.id,
                operation_id="not-a-uuid",
                base_generation="bad",
                base_current_hash="bad",
                changes={},
            )
        self.assertEqual(raised.exception.code, "FORBIDDEN")

    def test_owner_undo_swaps_payload_hash_and_provenance(self) -> None:
        initial_content = PageContent.objects.get(page=self.page)
        initial_hash = initial_content.current_hash
        initial_created_at = initial_content.current_created_at
        self._save()
        saved = PageContent.objects.get(page=self.page)
        saved_hash = saved.current_hash

        result = self._undo()
        undone = PageContent.objects.get(page=self.page)
        self.assertEqual(result.generation, 3)
        self.assertEqual(undone.current_payload, self.initial)
        self.assertEqual(undone.current_hash, initial_hash)
        self.assertEqual(undone.current_created_at, initial_created_at)
        self.assertEqual(undone.previous_hash, saved_hash)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CONTENT_UNDONE).count(), 1)

    def test_employee_cannot_undo(self) -> None:
        self._save()
        with self.assertRaises(PageCommandError) as raised:
            self._undo(actor=self.employee)
        self.assertEqual(raised.exception.code, "FORBIDDEN")
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_save_replaces_current_and_previous_media_usages(self) -> None:
        old_asset = Asset.objects.create(
            purpose=AssetPurpose.CONTENT,
            source_sha256="a" * 64,
            state=AssetState.READY,
        )
        new_asset = Asset.objects.create(
            purpose=AssetPurpose.CONTENT,
            source_sha256="b" * 64,
            state=AssetState.READY,
        )
        content = PageContent.objects.get(page=self.page)
        content.current_payload = payload(hero=str(old_asset.id))
        content.current_hash = canonical_payload_hash(content.current_payload)
        content.save(update_fields=("current_payload", "current_hash"))

        self._save(changes=payload(hero=str(new_asset.id)))
        usages = set(AssetUsage.objects.values_list("scope", "asset_id", "slot", "position"))
        self.assertEqual(usages, {
            (UsageScope.PAGE_CURRENT, new_asset.id, "hero", 0),
            (UsageScope.PAGE_PREVIOUS, old_asset.id, "hero", 0),
        })

        self._undo()
        usages = set(AssetUsage.objects.values_list("scope", "asset_id", "slot", "position"))
        self.assertEqual(usages, {
            (UsageScope.PAGE_CURRENT, old_asset.id, "hero", 0),
            (UsageScope.PAGE_PREVIOUS, new_asset.id, "hero", 0),
        })

    def test_missing_staged_and_wrong_purpose_media_fail_closed(self) -> None:
        staged = Asset.objects.create(
            purpose=AssetPurpose.CONTENT,
            source_sha256="c" * 64,
            state=AssetState.STAGED,
        )
        wrong = Asset.objects.create(
            purpose=AssetPurpose.SITE_ASSET,
            source_sha256="d" * 64,
            state=AssetState.READY,
        )
        for asset_id in (uuid.uuid4(), staged.id, wrong.id):
            with self.subTest(asset_id=asset_id):
                before = PageContent.objects.get(page=self.page)
                with self.assertRaises(PageCommandError) as raised:
                    self._save(changes=payload(hero=str(asset_id)))
                after = PageContent.objects.get(page=self.page)
                self.assertEqual(raised.exception.code, "MEDIA_NOT_READY")
                self.assertEqual(after.generation, before.generation)
                self.assertEqual(after.current_hash, before.current_hash)
                self.assertEqual(AuditEvent.objects.count(), 0)
                self.assertEqual(AssetUsage.objects.count(), 0)

    def test_audit_fault_rolls_back_content_and_usages(self) -> None:
        before = PageContent.objects.get(page=self.page)
        snapshot = (before.generation, copy.deepcopy(before.current_payload), before.current_hash)
        with patch("modules.pages.commands.append_event", side_effect=RuntimeError("audit-fault")):
            with self.assertRaises(RuntimeError):
                self._save()
        after = PageContent.objects.get(page=self.page)
        self.assertEqual((after.generation, after.current_payload, after.current_hash), snapshot)
        self.assertEqual(AssetUsage.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)


class PageCommandConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self) -> None:
        self.owner = User.objects.create_superuser(username="nesadmin", password=None)
        self.page = Page.objects.create(
            name="Concurrent service",
            kind=PageKind.SERVICE_DETAIL,
            position=0,
        )
        initial = payload()
        self.content = PageContent.objects.create(
            page=self.page,
            generation=1,
            current_payload=initial,
            current_hash=canonical_payload_hash(initial),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )

    def test_two_saves_on_one_basis_have_one_winner_and_one_stale(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics required.")
        barrier = threading.Barrier(2)

        def run(index: int):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return save_page_content(
                    actor_id=self.owner.id,
                    session_generation=self.owner.generation,
                    page_id=self.page.id,
                    operation_id=uuid.uuid4(),
                    base_generation=1,
                    base_current_hash=self.content.current_hash,
                    changes=payload(intro=f"<p>Winner {index}</p>"),
                )
            except PageCommandError as exc:
                return exc
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(run, (1, 2)))
        successes = [item for item in outcomes if not isinstance(item, PageCommandError)]
        failures = [item for item in outcomes if isinstance(item, PageCommandError)]
        self.assertEqual(len(successes), 1)
        self.assertEqual([item.code for item in failures], ["STALE_CONTENT"])
        self.assertEqual(PageContent.objects.get(page=self.page).generation, 2)
        self.assertEqual(AuditEvent.objects.filter(action=Action.PAGE_CONTENT_SAVED).count(), 1)
