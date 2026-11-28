from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import rebuild7_owner_preview_projection as projection


def row(index: int, payload: bytes) -> dict[str, object]:
    asset_id = uuid.uuid5(uuid.NAMESPACE_URL, f"asset-{index}")
    return {
        "page_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"page-{index}")),
        "asset_id": str(asset_id),
        "file_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"file-{index}")),
        "source_path": f"media/design-concepts/services-v4/file-{index}.webp",
        "byte_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


class ProjectionFilesystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.restore = self.root / "restore"
        self.authority = self.root / "authority"
        self.baseline = self.root / "projection" / "baseline.json"
        (self.source / "media" / "design-concepts" / "services-v4").mkdir(parents=True)
        (self.restore / "img").mkdir(parents=True)
        self.authority.mkdir()
        self.baseline.parent.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_exact58_copy_and_full_inventory_drift(self) -> None:
        base_payload = b"base"
        base_path = self.restore / "img" / str(uuid.uuid4()) / "main.webp"
        base_path.parent.mkdir()
        base_path.write_bytes(base_payload)
        base_row = {
            "path": base_path.relative_to(self.restore).as_posix(),
            "bytes": len(base_payload),
            "sha256": hashlib.sha256(base_payload).hexdigest(),
        }
        (self.authority / "media-inventory.json").write_text(
            json.dumps([base_row], separators=(",", ":")), encoding="utf-8"
        )
        rows = []
        added_bytes = 0
        for index in range(58):
            payload = f"payload-{index}".encode()
            item = row(index, payload)
            path = self.source.joinpath(*Path(str(item["source_path"])).parts)
            path.write_bytes(payload)
            rows.append(item)
            added_bytes += len(payload)
        with (
            patch.object(projection, "PROJECT", self.source),
            patch.object(projection, "RESTORED_MEDIA", self.restore),
            patch.object(projection, "BASE_INVENTORY", self.authority / "media-inventory.json"),
            patch.object(projection, "EXPECTED_BASE_FILES", 1),
            patch.object(projection, "EXPECTED_BASE_BYTES", len(base_payload)),
            patch.object(projection, "EXPECTED_ADDED_BYTES", added_bytes),
        ):
            projection.copy_files(tuple(rows))
            files, byte_count, digest = projection.verify_files(tuple(rows))
            self.assertEqual((files, byte_count), (59, len(base_payload) + added_bytes))
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            base_path.write_bytes(b"drift")
            with self.assertRaisesRegex(RuntimeError, "R7_OWNER_PROJECTION_UNAVAILABLE"):
                projection.verify_files(tuple(rows))

    def test_existing_destination_and_symlink_fail_closed(self) -> None:
        payload = b"payload"
        item = row(0, payload)
        source_path = self.source.joinpath(*Path(str(item["source_path"])).parts)
        source_path.write_bytes(payload)
        with (
            patch.object(projection, "PROJECT", self.source),
            patch.object(projection, "RESTORED_MEDIA", self.restore),
        ):
            projection.copy_files((item,))
            with self.assertRaisesRegex(RuntimeError, "R7_OWNER_PROJECTION_UNAVAILABLE"):
                projection.copy_files((item,))
        source_path.unlink()
        source_path.symlink_to(self.root / "outside.webp")
        with patch.object(projection, "PROJECT", self.source):
            with self.assertRaisesRegex(RuntimeError, "R7_OWNER_PROJECTION_UNAVAILABLE"):
                projection.checked_source(item)

    def test_baseline_is_canonical_exclusive_and_drift_visible(self) -> None:
        value = {
            "schema": "estakada.r7-owner-projection-baseline-v2",
            "map019_infographic_preserved": False,
            "pages": {
                str(uuid.uuid4()): {
                    "kind": "service_detail",
                    "untouched_sha256": "a" * 64,
                    "projected_current_sha256": "b" * 64,
                }
                for _ in range(58)
            },
        }
        with patch.object(projection, "BASELINE", self.baseline):
            projection.write_baseline(value)
            self.assertEqual(projection.read_baseline(), value)
            with self.assertRaisesRegex(RuntimeError, "R7_OWNER_PROJECTION_UNAVAILABLE"):
                projection.write_baseline(value)
            self.baseline.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "R7_OWNER_PROJECTION_UNAVAILABLE"):
                projection.read_baseline()

    def test_ids_and_storage_keys_are_deterministic(self) -> None:
        payload = b"payload"
        item = row(0, payload)
        self.assertEqual(
            projection.storage_key(item),
            f"img/{item['asset_id']}/main.webp",
        )
        self.assertEqual(projection.usage_id(item), projection.usage_id(dict(item)))

    def test_source_and_harness_retain_closed_contracts(self) -> None:
        helper = Path(projection.__file__).read_text(encoding="utf-8")
        harness_path = Path(os.environ["R7_OWNER_PROJECTION_HARNESS"])
        harness = harness_path.read_text(encoding="utf-8")
        for token in (
            "transaction.atomic()",
            'content.save(update_fields=("current_payload", "current_hash"))',
            "select_for_update()",
            'content_queryset = PageContent.objects.select_related("page")',
            "if apply:\n            content_queryset = content_queryset.select_for_update()",
            "write_baseline",
            "untouched_digest",
            'baseline_row["projected_current_sha256"] != content.current_hash',
            "INFOGRAPHIC_ASSET_ID",
            '"map019_infographic_preserved": map019_infographic_preserved',
            'if baseline["map019_infographic_preserved"]:',
            "elif infographic_usage.exists():",
            "expected_map019_body",
            "database_rollback_probe",
        ):
            self.assertIn(token, helper)
        self.assertIn("$restoredMediaMount += ',readonly'", harness)
        self.assertIn("$projectionAuthorityMount += ',readonly'", harness)
        self.assertIn("owner-projection-post-verify", harness)
        self.assertIn("owner-projection-probe", harness)

    def test_owner_capture_clone_precedes_generation_and_cleans_exactly(self) -> None:
        harness_path = Path(os.environ["R7_OWNER_PROJECTION_HARNESS"])
        harness = harness_path.read_text(encoding="utf-8")
        ordered = (
            "owner-capture-source-guard-before",
            "New-CaptureCloneDatabase",
            "Invoke-CaptureCloneMigration",
            "Assert-CaptureCloneMigrationState",
            "$captureDatabase = $captureCloneDatabase",
            "$captureLine = Invoke-AppHelper",
            "owner-capture-source-guard-after",
            "Complete-OwnerSourceGuardAfter",
            "owner-capture-clone-drop",
            "Remove-CaptureCloneDatabase",
        )
        cursor = harness.index("owner-capture-source-guard-before")
        for token in ordered:
            cursor = harness.index(token, cursor) + len(token)
        for token in (
            "estakada.r7-owner-capture:",
            "shobj_description",
            "R7_OWNER_CAPTURE_CLONE_OWNERSHIP_UNCERTAIN",
            "R7_OWNER_CAPTURE_MIGRATION_OWNERSHIP_UNCERTAIN",
            "service_requests_servicerequestdeletionprojection",
            "Assert-FileEqual (Join-Path $sourceGuardBefore 'source-guard.json')",
            "$sourceGuardAfterAttempted = $false",
            "if ($OwnerInteractivePreview -and $sourceGuardBeforeComplete -and !$sourceGuardAfterComplete)",
            "Wait-CaptureCloneZeroClients\n    Assert-CaptureCloneOwned\n    Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'dropdb'",
            "if ($captureMigrationMayExist)",
            "if ($captureCloneMayExist)",
            "$dbStartMayHaveOccurred",
            "Invoke-DockerBounded",
            "Wait-DatabaseReady",
            "Restore-DatabaseBitmap",
            "[string]$db.State.Status -cne 'exited'",
            "Invoke-RetainedPreviewRecovery",
            "RecoverPreviewNetworkId",
            "R7_OWNER_PREVIEW_RECOVERY_PASS containers=0 networks=0 database=0 staging=0 lock=0 bitmap=exact",
        ):
            self.assertIn(token, harness)

    def test_diagnostic_stage_is_closed_and_preserved(self) -> None:
        projection.set_stage("DB_CONTENT_PRESTATE")
        with self.assertRaisesRegex(
            RuntimeError, "R7_OWNER_PROJECTION_DB_CONTENT_PRESTATE_UNAVAILABLE"
        ):
            projection.fail()
        with self.assertRaisesRegex(
            RuntimeError, "R7_OWNER_PROJECTION_DIAGNOSTIC_UNAVAILABLE"
        ):
            projection.set_stage("bad-stage")
        with self.assertRaisesRegex(
            RuntimeError, "R7_OWNER_PROJECTION_DIAGNOSTIC_UNAVAILABLE"
        ):
            projection.set_stage("UNKNOWN_STAGE")
        projection.set_stage("UNAVAILABLE")
        self.assertEqual(
            projection.normalized_failure(
                RuntimeError("R7_OWNER_PROJECTION_UNKNOWN_STAGE_UNAVAILABLE")
            ),
            "R7_OWNER_PROJECTION_UNAVAILABLE",
        )


if __name__ == "__main__":
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProjectionFilesystemTests)
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    if not result.wasSuccessful() or result.testsRun != 7:
        raise RuntimeError("R7_OWNER_PROJECTION_TESTS_UNAVAILABLE")
    print("R7_OWNER_PROJECTION_TESTS_OK cases=7")
