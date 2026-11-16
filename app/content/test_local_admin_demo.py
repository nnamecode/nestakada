import os
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode
from uuid import uuid4

from django.db import models
from django.core.exceptions import ValidationError
from django.test import Client, TransactionTestCase, override_settings

from accounts.services import recover_owner
from audit.constants import Category, Level, Result, Source
from audit.models import AuditEvent
from audit.services import record_event
from shared_content.models import SharedBlock, SharedBudget

from .local_admin_demo import (
    EXPECTED_MEDIA_BYTES, EXPECTED_MEDIA_COUNT, FOOTER_BLOCK_ID,
    HEADER_BLOCK_ID, _counts, _raw, assemble_demo,
)
from . import local_admin_demo as demo
from . import dev09_migration_apply as migration
from . import dev10_gallery_apply as gallery
from . import dev12_home_apply as home
from .models import Route


@override_settings(ENVIRONMENT="dev", AUTH_TRUSTED_PROXY_HOST=None)
class LocalAdminDemoTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.original_guards = {
            (module, name): getattr(module, name)
            for module in (migration, gallery, home)
            for name in ("_enabled", "_identity")
        }
        for identity, kind in ((HEADER_BLOCK_ID, "header"),
                               (FOOTER_BLOCK_ID, "footer")):
            SharedBlock(id=identity, kind=kind).save()
        SharedBudget.objects.create(singleton=True)
        _raw(Route).bulk_create([Route(
            id=uuid4(), target="/manage/", kind=Route.Kind.SYSTEM,
            page=None, is_legacy=False,
        )])
        self.baseline_audit = record_event(
            category=Category.ENVIRONMENT, event_code="LOCAL_DEMO_BASELINE_TEST",
            level=Level.INFO, source=Source.APPLICATION, result=Result.SUCCESS,
        )
        self.logo = Path(os.environ["ESTAKADA_LOCAL_DEMO_LOGO_TEST"])

    def _assemble(self, state, **kwargs):
        with patch.dict(os.environ, {"ESTAKADA_LOCAL_DEMO_APPLY_ENABLED": "1"}):
            return assemble_demo(
                state_root=state, logo_path=self.logo,
                run_id=str(uuid4()), test_mode=True, **kwargs,
            )

    def assert_producer_guards_closed(self):
        for module, code in ((migration, "MIGRATION_APPLY_DISABLED"),
                             (gallery, "GALLERY_APPLY_DISABLED"),
                             (home, "HOME_APPLY_DISABLED")):
            self.assertIs(module._enabled, self.original_guards[(module, "_enabled")])
            self.assertIs(module._identity, self.original_guards[(module, "_identity")])
            with self.assertRaisesRegex(ValidationError, code):
                module._enabled()
            cursor = MagicMock()
            cursor.__enter__.return_value.fetchone.return_value = (
                "estakada_foundation", "app_runtime")
            with patch.object(module.connection, "cursor", return_value=cursor):
                with self.assertRaisesRegex(ValidationError, code):
                    module._identity()

    def test_lad_001_success_recovery_http_and_replay_refusal(self):
        with TemporaryDirectory(prefix="local-admin-demo-", dir="/tmp") as root:
            state = Path(root)
            self.assert_producer_guards_closed()
            result = self._assemble(state)
            self.assert_producer_guards_closed()
            self.assertEqual(result["owner"], "nesadmin")
            self.assertEqual(result["socialLinks"], 0)
            self.assertRegex(result["sourceManifestSha256"], r"^[a-f0-9]{64}$")
            self.assertRegex(result["routeMapSha256"], r"^[a-f0-9]{64}$")
            self.assertRegex(result["mediaProjectionSha256"], r"^[a-f0-9]{64}$")
            self.assertRegex(result["databaseProjectionSha256"], r"^[a-f0-9]{64}$")
            self.assertEqual(result["media"], {
                "count": EXPECTED_MEDIA_COUNT, "bytes": EXPECTED_MEDIA_BYTES,
            })
            counts = _counts()
            self.assertTrue(AuditEvent.objects.filter(
                pk=self.baseline_audit.pk, event_id=self.baseline_audit.event_id).exists())
            self.assertEqual(
                (counts["pages"], counts["routes"], counts["assets"],
                 counts["files"], counts["requests"], counts["users"]),
                (112, 115, 238, 238, 0, 2),
            )
            current = state / "media"
            self.assertTrue(current.is_dir())
            with override_settings(MEDIA_LIBRARY_ROOT=str(current)):
                browser = Client(REMOTE_ADDR="192.0.2.20")
                self.assertEqual(browser.get("/").status_code, 200)
                self.assertEqual(browser.get("/contacts").status_code, 200)
                login = browser.get("/manage/login/")
                self.assertEqual(login.status_code, 200)
                self.assertIn("no-store", login.get("Cache-Control", ""))
                password = secrets.token_urlsafe(32)
                recover_owner(password)
                response = browser.post(
                    "/manage/login/",
                    urlencode({"username": "nesadmin", "password": password}),
                    content_type="application/x-www-form-urlencoded",
                )
                self.assertEqual(response.status_code, 303)
                self.assertEqual(response["Location"], "/manage/")
                dashboard = browser.get("/manage/")
                self.assertEqual(dashboard.status_code, 200)
                self.assertIn("no-store", dashboard.get("Cache-Control", ""))
            before = _counts()
            with self.assertRaisesRegex(RuntimeError, "LOCAL_DEMO_MEDIA_ALREADY_EXISTS"):
                self._assemble(state)
            self.assertEqual(_counts(), before)

    def test_lad_002_late_failure_rolls_back_database_and_files(self):
        with TemporaryDirectory(prefix="local-admin-demo-failure-", dir="/tmp") as root:
            state = Path(root)
            self.assert_producer_guards_closed()
            before = _counts()
            with self.assertRaisesRegex(RuntimeError, "LOCAL_DEMO_CONTROLLED_FAILURE"):
                self._assemble(state, fail_after_publish=True)
            self.assertEqual(_counts(), before)
            self.assertEqual(Route.objects.get().target, "/manage/")
            self.assertTrue(AuditEvent.objects.filter(pk=self.baseline_audit.pk).exists())
            self.assertFalse((state / "media").exists())
            staging = state / "local-admin-demo-staging"
            self.assertFalse(staging.exists() and any(staging.iterdir()))
            self.assert_producer_guards_closed()

    def test_lad_003_undeclared_staging_object_rolls_back(self):
        with TemporaryDirectory(prefix="local-admin-demo-extra-", dir="/tmp") as root:
            state = Path(root)
            original = demo._copy_declared_media

            def add_extra(source_root, staging):
                result = original(source_root, staging)
                (staging / "undeclared.bin").write_bytes(b"not admitted")
                return result

            before = _counts()
            with patch("content.local_admin_demo._copy_declared_media", side_effect=add_extra):
                with self.assertRaisesRegex(RuntimeError, "LOCAL_DEMO_STAGING_INVENTORY_MISMATCH"):
                    self._assemble(state)
            self.assertEqual(_counts(), before)
            self.assertFalse((state / "media").exists())

    def test_lad_004_populated_shared_seed_refuses_without_mutation(self):
        with TemporaryDirectory(prefix="local-admin-demo-seed-", dir="/tmp") as root:
            state = Path(root)
            models.QuerySet(model=SharedBlock, using="default").filter(
                pk=HEADER_BLOCK_ID).update(generation=2)
            before = _counts()
            with self.assertRaisesRegex(RuntimeError, "LOCAL_DEMO_SHARED_SEED_MISMATCH"):
                self._assemble(state)
            self.assertEqual(_counts(), before)
            self.assertEqual(list(state.iterdir()), [])

    def test_lad_005_guard_seam_restores_after_inner_exception(self):
        with TemporaryDirectory(prefix="local-admin-demo-guard-", dir="/tmp") as root:
            state = Path(root)
            self.assert_producer_guards_closed()
            before = _counts()
            with patch("content.local_admin_demo._copy_declared_media",
                       side_effect=RuntimeError("LOCAL_DEMO_INNER_FAILURE")):
                with self.assertRaisesRegex(RuntimeError, "LOCAL_DEMO_INNER_FAILURE"):
                    self._assemble(state)
            self.assert_producer_guards_closed()
            self.assertEqual(_counts(), before)
            self.assertFalse((state / "media").exists())
            staging = state / "local-admin-demo-staging"
            self.assertFalse(staging.exists() and any(staging.iterdir()))

    def test_lad_006_wrong_sql_database_or_role_refuses_pre_mutation(self):
        for actual in (("foreign_database", "app_migrator"),
                       ("estakada_foundation_unit", "foreign_role")):
            with self.subTest(actual=actual), TemporaryDirectory(
                    prefix="local-admin-demo-identity-", dir="/tmp") as root:
                state = Path(root)
                before = _counts()
                cursor = MagicMock()
                cursor.__enter__.return_value.fetchone.return_value = actual
                with patch.object(demo.connection, "cursor", return_value=cursor):
                    with self.assertRaisesRegex(
                            RuntimeError, "LOCAL_DEMO_DATABASE_IDENTITY_REJECTED"):
                        self._assemble(state)
                self.assertEqual(_counts(), before)
                self.assertEqual(list(state.iterdir()), [])
