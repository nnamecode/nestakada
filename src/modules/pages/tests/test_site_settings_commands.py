from __future__ import annotations

import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.db import DatabaseError, close_old_connections, connection
from django.test import TransactionTestCase

from modules.accounts.models import StaffRole, User
from modules.audit.models import Action, AuditEvent
from modules.media.api import (
    MediaUsageError,
    lock_site_logo_usage,
    project_site_logo_options,
    replace_site_logo_usage,
)
from modules.media.models import (
    Asset,
    AssetFile,
    AssetPurpose,
    AssetState,
    AssetUsage,
    FileKind,
    MediaType,
    UsageScope,
)

from ..models import SiteSettings
from ..site_settings import SiteSettingsCommandError, update_site_settings


PASSWORD = "Unique!Settings-2026"


class SiteSettingsFixture:
    def make_asset(
        self,
        marker: str,
        *,
        purpose: str = AssetPurpose.SITE_ASSET,
        state: str = AssetState.READY,
        main: bool = True,
    ) -> Asset:
        asset = Asset.objects.create(
            purpose=purpose,
            state=state,
            source_sha256=marker * 64,
        )
        if main:
            AssetFile.objects.create(
                asset=asset,
                kind=FileKind.MAIN,
                storage_key=f"img/{asset.id}/main.png",
                sha256=marker * 64,
                byte_size=10,
                mime_type=MediaType.PNG,
                width=20,
                height=10,
            )
        return asset

    def make_fixture(self):
        owner = User.objects.create_user(
            username="nesadmin", password=PASSWORD, role=StaffRole.OWNER
        )
        logo = self.make_asset("1")
        settings = SiteSettings.objects.create(
            organization_name="Эстакада",
            legal_name="ООО Эстакада",
            phone_display="+7 499 110-25-52",
            phone_e164="+74991102552",
            address="Москва",
            opening_hours="Ежедневно",
            contact_email="owner@example.test",
            map_url="https://example.test/map",
            max_url="https://max.example.test/chat",
            telegram_url="https://t.me/example",
            logo_asset=logo,
        )
        AssetUsage.objects.create(
            asset=logo,
            scope=UsageScope.SITE_SETTINGS,
            target_uuid=settings.id,
            slot="logo",
            position=0,
        )
        return owner, settings, logo

    def values(self, settings: SiteSettings, logo: Asset, **changes):
        values = {
            "actor_id": self.owner.id,
            "session_generation": self.owner.generation,
            "base_settings_generation": settings.settings_generation,
            "organization_name": settings.organization_name,
            "phone_display": settings.phone_display,
            "phone_e164": settings.phone_e164,
            "address": settings.address,
            "opening_hours": settings.opening_hours,
            "contact_email": settings.contact_email,
            "map_url": settings.map_url,
            "logo_asset_id": logo.id,
        }
        values.update(changes)
        return values


class SiteSettingsCommandTests(SiteSettingsFixture, TransactionTestCase):
    def setUp(self) -> None:
        self.owner, self.settings, self.logo = self.make_fixture()

    def test_scalar_and_logo_updates_change_only_core8_generation_usage_and_audit(self) -> None:
        replacement = self.make_asset("2")
        preserved = (
            self.settings.structure_generation,
            self.settings.legal_name,
            self.settings.max_url,
            self.settings.telegram_url,
        )
        result = update_site_settings(**self.values(
            self.settings,
            replacement,
            organization_name="Новая Эстакада",
        ))
        self.settings.refresh_from_db()
        self.assertEqual(result.settings_generation, 2)
        self.assertEqual(self.settings.organization_name, "Новая Эстакада")
        self.assertEqual(self.settings.logo_asset_id, replacement.id)
        self.assertEqual(
            (
                self.settings.structure_generation,
                self.settings.legal_name,
                self.settings.max_url,
                self.settings.telegram_url,
            ),
            preserved,
        )
        self.assertEqual(
            list(AssetUsage.objects.filter(scope=UsageScope.SITE_SETTINGS).values_list(
                "slot", "position", "asset_id"
            )),
            [("logo", 0, replacement.id)],
        )
        event = AuditEvent.objects.get(action=Action.SITE_SETTINGS_CHANGED)
        self.assertIsNone(event.target_uuid)
        self.assertEqual(event.detail, {"generation": 2})

    def test_stale_and_identical_are_conflicts_without_mutation(self) -> None:
        for changes, code in (
            ({"base_settings_generation": 2}, "STALE_SETTINGS"),
            ({}, "NO_CHANGE"),
        ):
            with self.subTest(code=code), self.assertRaises(SiteSettingsCommandError) as raised:
                update_site_settings(**self.values(self.settings, self.logo, **changes))
            self.assertEqual(raised.exception.code, code)
        self.assertFalse(AuditEvent.objects.exists())
        self.assertEqual(SiteSettings.objects.get().settings_generation, 1)

    def test_employee_and_stale_session_are_denied(self) -> None:
        employee = User.objects.create_user(
            username="editor", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        for changes, code in (
            ({"actor_id": employee.id}, "FORBIDDEN"),
            ({"session_generation": 2}, "STALE_SESSION"),
        ):
            with self.subTest(code=code), self.assertRaises(SiteSettingsCommandError) as raised:
                update_site_settings(**self.values(self.settings, self.logo, **changes))
            self.assertEqual(raised.exception.code, code)

    def test_invalid_scalar_and_non_ready_or_wrong_purpose_logo_are_rejected(self) -> None:
        staged = self.make_asset("2", state=AssetState.STAGED)
        content = self.make_asset("3", purpose=AssetPurpose.CONTENT)
        with patch("modules.pages.site_settings.replace_site_logo_usage") as replacement:
            with self.assertRaises(SiteSettingsCommandError) as raised:
                update_site_settings(**self.values(
                    self.settings, self.logo, organization_name=""
                ))
        self.assertEqual(raised.exception.code, "INVALID_SETTINGS")
        replacement.assert_not_called()
        cases = (
            ({"logo_asset_id": staged.id}, "MEDIA_NOT_READY"),
            ({"logo_asset_id": content.id}, "MEDIA_NOT_READY"),
            ({"logo_asset_id": uuid.uuid4()}, "MEDIA_NOT_READY"),
        )
        for changes, code in cases:
            with self.subTest(code=code), self.assertRaises(SiteSettingsCommandError) as raised:
                update_site_settings(**self.values(self.settings, self.logo, **changes))
            self.assertEqual(raised.exception.code, code)

    def test_full_usage_drift_and_audit_failure_roll_back(self) -> None:
        AssetUsage.objects.filter(scope=UsageScope.SITE_SETTINGS).update(slot="other")
        with self.assertRaises(SiteSettingsCommandError) as raised:
            update_site_settings(**self.values(
                self.settings, self.logo, organization_name="Другая Эстакада"
            ))
        self.assertEqual(raised.exception.code, "MEDIA_USAGE_MISMATCH")
        AssetUsage.objects.filter(scope=UsageScope.SITE_SETTINGS).update(slot="logo")
        extra = self.make_asset("2")
        extra_usage = AssetUsage.objects.create(
            asset=extra,
            scope=UsageScope.SITE_SETTINGS,
            target_uuid=self.settings.id,
            slot="extra",
            position=0,
        )
        with self.assertRaises(SiteSettingsCommandError) as raised:
            update_site_settings(**self.values(
                self.settings, self.logo, organization_name="Другая Эстакада"
            ))
        self.assertEqual(raised.exception.code, "MEDIA_USAGE_MISMATCH")
        extra_usage.delete()
        replacement = self.make_asset("3")
        with patch("modules.pages.site_settings.append_event", side_effect=DatabaseError):
            with self.assertRaises(DatabaseError):
                update_site_settings(**self.values(
                    self.settings, replacement, organization_name="Другая Эстакада"
                ))
        persisted = SiteSettings.objects.get()
        self.assertEqual(
            (persisted.organization_name, persisted.settings_generation, persisted.logo_asset_id),
            ("Эстакада", 1, self.logo.id),
        )
        self.assertEqual(
            list(AssetUsage.objects.filter(
                scope=UsageScope.SITE_SETTINGS,
                target_uuid=self.settings.id,
            ).values_list("slot", "position", "asset_id")),
            [("logo", 0, self.logo.id)],
        )
        self.assertFalse(AuditEvent.objects.exists())

    def test_projection_is_bounded_exact_and_exposes_only_public_metadata(self) -> None:
        projected = project_site_logo_options(
            settings_id=self.settings.id,
            current_logo_id=self.logo.id,
            include_options=True,
        )
        self.assertEqual(len(projected), 1)
        self.assertEqual(
            set(projected[0].__dataclass_fields__),
            {"asset_id", "mime_type", "width", "height"},
        )
        for _ in range(63):
            self.make_asset("2")
        bounded = project_site_logo_options(
            settings_id=self.settings.id,
            current_logo_id=self.logo.id,
            include_options=True,
        )
        self.assertEqual(len(bounded), 64)
        extra = self.make_asset("3")
        with self.assertRaises(MediaUsageError) as raised:
            project_site_logo_options(
                settings_id=self.settings.id,
                current_logo_id=self.logo.id,
                include_options=True,
            )
        self.assertEqual(raised.exception.code, "SITE_LOGO_UNAVAILABLE")
        Asset.objects.filter(pk=extra.id).delete()
        current_only = project_site_logo_options(
            settings_id=self.settings.id,
            current_logo_id=self.logo.id,
            include_options=False,
        )
        self.assertEqual([item.asset_id for item in current_only], [self.logo.id])
        Asset.objects.exclude(pk=self.logo.id).delete()
        self.logo.state = AssetState.STAGED
        self.logo.save(update_fields=("state",))
        with self.assertRaises(MediaUsageError) as raised:
            project_site_logo_options(
                settings_id=self.settings.id,
                current_logo_id=self.logo.id,
                include_options=True,
            )
        self.assertEqual(raised.exception.code, "SITE_LOGO_UNAVAILABLE")
        self.logo.state = AssetState.READY
        self.logo.save(update_fields=("state",))
        self.logo.files.filter(kind=FileKind.MAIN).delete()
        with self.assertRaises(MediaUsageError):
            project_site_logo_options(
                settings_id=self.settings.id,
                current_logo_id=self.logo.id,
                include_options=False,
            )

    def test_media_atomic_boundary_and_two_updates_have_one_winner(self) -> None:
        with self.assertRaises(RuntimeError):
            lock_site_logo_usage(
                settings_id=self.settings.id,
                current_asset_id=self.logo.id,
                new_asset_id=self.logo.id,
            )
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics required.")
        barrier = threading.Barrier(2)

        def run(name: str):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return update_site_settings(**self.values(
                    self.settings,
                    self.logo,
                    organization_name=name,
                ))
            except SiteSettingsCommandError as exc:
                return exc
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = (
                pool.submit(run, "Первая Эстакада"),
                pool.submit(run, "Вторая Эстакада"),
            )
            outcomes = [future.result(timeout=10) for future in futures]
        self.assertEqual(sum(not isinstance(item, Exception) for item in outcomes), 1)
        self.assertEqual(
            [item.code for item in outcomes if isinstance(item, SiteSettingsCommandError)],
            ["STALE_SETTINGS"],
        )
        self.assertEqual(
            AuditEvent.objects.filter(action=Action.SITE_SETTINGS_CHANGED).count(), 1
        )
