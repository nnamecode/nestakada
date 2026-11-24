from __future__ import annotations

import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

import rebuild7_selector as selector


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
CONTAINER_A = "1" * 64
CONTAINER_B = "2" * 64
CONTAINER_C = "3" * 64


def journal_payload(scope: str = "rehearsal:" + "3" * 32) -> dict[str, object]:
    return {
        "schema": "estakada.r7c-journal-v1",
        "scope": scope,
        "runId": "4" * 32,
        "phase": "PREPARED",
        "ingressId": CONTAINER_C,
        "oldTargetId": CONTAINER_A,
        "newTargetId": CONTAINER_B,
        "oldStorageBindingSha256": SHA_A,
        "newStorageBindingSha256": SHA_B,
        "expectedSelector": "ABSENT",
        "candidateSelectorSha256": SHA_B,
        "implementationImageBindingSha256": SHA_A,
        "mutationBitmap": {
            "admin": "CLOSED",
            "cleanup": "CLOSED",
            "editor": "CLOSED",
            "request": "CLOSED",
            "scheduler": "CLOSED",
            "upload": "CLOSED",
        },
    }


class SelectorContractTests(unittest.TestCase):
    def test_selector_is_canonical_and_round_trips(self) -> None:
        data = selector.render_selector("rehearsal:" + "3" * 32, "old", SHA_A)
        parsed = selector.parse_selector(data)
        self.assertEqual(parsed["scope"], "rehearsal:" + "3" * 32)
        self.assertEqual(parsed["role"], "old")
        self.assertEqual(parsed["alias"], "r7c-old-app")
        self.assertEqual(parsed["mediaRoot"], "/srv/media-old")
        self.assertEqual(parsed["staticRoot"], "/srv/source-old/modules/pages/static")
        self.assertEqual(selector.render_selector(**selector.selector_render_args(parsed)), data)

    def test_selector_rejects_wrong_scope_role_generation_and_extra_bytes(self) -> None:
        for args in (
            ("foreign", "old", SHA_A),
            ("local", "owner", SHA_A),
            ("local", "new", "A" * 64),
        ):
            with self.subTest(args=args), self.assertRaises(RuntimeError):
                selector.render_selector(*args)
        valid = selector.render_selector("local", "new", SHA_B)
        with self.assertRaises(RuntimeError):
            selector.parse_selector(valid + b"# extra\n")

    def test_closed_journal_transitions_and_unknown(self) -> None:
        payload = selector.validate_journal(journal_payload())
        payload = selector.transition_journal(payload, "INGRESS_STOPPED")
        payload = selector.transition_journal(payload, "SELECTOR_COMMITTED")
        self.assertEqual(payload["phase"], "SELECTOR_COMMITTED")
        with self.assertRaises(RuntimeError):
            selector.transition_journal(payload, "CONFIRMED")
        self.assertEqual(selector.transition_journal(payload, "UNKNOWN")["phase"], "UNKNOWN")

    def test_storage_binding_is_closed_and_binds_media_authority(self) -> None:
        capture = {
            "schema": "estakada.r7-binding-capture-v1",
            "sourceSha256": SHA_A,
            "releaseSha256": SHA_B,
            "schemaFingerprintSha256": SHA_A,
            "appliedMigrationsSha256": SHA_B,
            "tableCountsSha256": SHA_A,
            "tableContentSha256": SHA_B,
            "mediaInventorySha256": SHA_A,
            "mediaFiles": 2,
            "mediaBytes": 7,
        }
        media = {
            "schema": "estakada.r7-media-check-v1",
            "verifierContainerId": CONTAINER_A,
            "verifierImageId": "sha256:" + SHA_B,
            "mediaMountToken": SHA_A,
            "authorityFileSha256": SHA_B,
            "authorityCanonicalSha256": SHA_A,
            "inventorySha256": SHA_A,
            "files": 2,
            "bytes": 7,
            "result": "PASS",
        }
        result = selector.storage_binding({"capture": capture, "mediaCheck": media})
        self.assertEqual(result["schema"], "estakada.r7-storage-binding-v1")
        self.assertRegex(result["storageBindingSha256"], r"^[0-9a-f]{64}$")
        broken = json.loads(json.dumps({"capture": capture, "mediaCheck": media}))
        broken["mediaCheck"]["bytes"] = 8
        with self.assertRaises(RuntimeError):
            selector.storage_binding(broken)
        repeated = json.loads(json.dumps({"capture": capture, "mediaCheck": media}))
        repeated["mediaCheck"]["verifierContainerId"] = CONTAINER_B
        self.assertEqual(
            selector.storage_binding(repeated)["storageBindingSha256"],
            result["storageBindingSha256"],
        )
        remounted = json.loads(json.dumps({"capture": capture, "mediaCheck": media}))
        remounted["mediaCheck"]["mediaMountToken"] = SHA_B
        self.assertNotEqual(
            selector.storage_binding(remounted)["storageBindingSha256"],
            result["storageBindingSha256"],
        )
        for section, key in (
            ("capture", "sourceSha256"),
            ("capture", "releaseSha256"),
            ("capture", "schemaFingerprintSha256"),
            ("capture", "appliedMigrationsSha256"),
            ("capture", "tableCountsSha256"),
            ("capture", "tableContentSha256"),
            ("mediaCheck", "verifierImageId"),
            ("mediaCheck", "authorityFileSha256"),
            ("mediaCheck", "authorityCanonicalSha256"),
        ):
            changed = json.loads(json.dumps({"capture": capture, "mediaCheck": media}))
            changed[section][key] = "sha256:" + SHA_A if key == "verifierImageId" else SHA_C
            with self.subTest(section=section, key=key):
                self.assertNotEqual(
                    selector.storage_binding(changed)["storageBindingSha256"],
                    result["storageBindingSha256"],
                )
        changed_inventory = json.loads(json.dumps({"capture": capture, "mediaCheck": media}))
        changed_inventory["capture"]["mediaInventorySha256"] = SHA_C
        changed_inventory["mediaCheck"]["inventorySha256"] = SHA_C
        self.assertNotEqual(selector.storage_binding(changed_inventory)["storageBindingSha256"], result["storageBindingSha256"])
        for key in ("files", "bytes"):
            changed_count = json.loads(json.dumps({"capture": capture, "mediaCheck": media}))
            capture_key = "mediaFiles" if key == "files" else "mediaBytes"
            changed_count["capture"][capture_key] += 1
            changed_count["mediaCheck"][key] += 1
            self.assertNotEqual(selector.storage_binding(changed_count)["storageBindingSha256"], result["storageBindingSha256"])


class SelectorFilesystemTests(unittest.TestCase):
    def test_absent_to_old_and_stale_cas_mutates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_id = "4" * 32
            candidate = selector.render_candidate(root, run_id, "rehearsal:" + "3" * 32, "old", SHA_A)
            first = selector.selector_cas(root, "ABSENT", candidate)
            self.assertEqual(first["state"], "PRESENT")
            before = (root / "selectors" / "active.conf").read_bytes()
            with self.assertRaises(RuntimeError):
                selector.selector_cas(root, SHA_B, candidate)
            self.assertEqual((root / "selectors" / "active.conf").read_bytes(), before)
            self.assertEqual(selector.selector_unlink(root, first["selector"]["sha256"])["state"], "ABSENT")

    def test_symlink_active_is_unknown_and_not_replaced(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlink unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "selectors").mkdir()
            target = root / "target"
            target.write_text("foreign", encoding="utf-8")
            try:
                (root / "selectors" / "active.conf").symlink_to(target)
            except OSError:
                self.skipTest("symlink privilege unavailable")
            self.assertEqual(selector.inspect_selector(root)["state"], "UNKNOWN")

    def test_hardlink_wrong_mode_and_cap_are_rejected(self) -> None:
        if selector.fcntl is None:
            self.skipTest("Linux filesystem contract unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = selector.render_candidate(
                root, "4" * 32, "local", "old", SHA_A
            )
            selected = selector.selector_cas(root, "ABSENT", candidate)
            active = root / "selectors" / "active.conf"
            linked = root / "active-link"
            os.link(active, linked)
            self.assertEqual(selector.inspect_selector(root)["state"], "UNKNOWN")
            linked.unlink()
            active.chmod(0o666)
            self.assertEqual(selector.inspect_selector(root)["state"], "UNKNOWN")
            active.chmod(0o644)
            self.assertEqual(
                selector.inspect_selector(root)["selector"]["sha256"],
                selected["selector"]["sha256"],
            )
        with self.assertRaises(RuntimeError):
            selector.parse_selector(b"x" * 4097)

    def test_concurrent_absent_cas_has_exactly_one_winner(self) -> None:
        if selector.fcntl is None:
            self.skipTest("Linux flock unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = selector.render_candidate(
                root, "4" * 32, "rehearsal:" + "3" * 32, "old", SHA_A
            )
            second = selector.render_candidate(
                root, "5" * 32, "rehearsal:" + "3" * 32, "new", SHA_B
            )

            def attempt(candidate: Path) -> bool:
                try:
                    selector.selector_cas(root, "ABSENT", candidate)
                except RuntimeError:
                    return False
                return True

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(attempt, (first, second)))
            self.assertEqual(outcomes.count(True), 1)
            self.assertEqual(outcomes.count(False), 1)

    def test_journal_compare_and_swap_requires_exact_previous_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            created = selector.create_journal(root, journal_payload())
            transitioned = selector.update_journal(root, created["sha256"], "INGRESS_STOPPED")
            self.assertEqual(transitioned["phase"], "INGRESS_STOPPED")
            with self.assertRaises(RuntimeError):
                selector.update_journal(root, created["sha256"], "SELECTOR_COMMITTED")

    def test_fault_marker_is_rejected_without_exact_testing_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            os.environ,
            {"ESTAKADA_R7C_TEST_FAULT": "before-replace"},
            clear=False,
        ):
            with self.assertRaises(RuntimeError):
                selector.render_candidate(
                    Path(temporary), "4" * 32, "local", "old", SHA_A
                )

    def test_each_atomic_write_fault_stage_fails_closed(self) -> None:
        if selector.fcntl is None:
            self.skipTest("Linux filesystem contract unavailable")
        for stage in ("after-file-fsync", "before-replace", "after-replace", "after-parent-fsync"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
                os.environ,
                {"ESTAKADA_R7C_TESTING": "1", "ESTAKADA_R7C_TEST_FAULT": stage},
                clear=False,
            ):
                with self.assertRaisesRegex(RuntimeError, "R7C_INJECTED_FAULT"):
                    selector.render_candidate(
                        Path(temporary), "4" * 32, "local", "old", SHA_A
                    )

    def test_receipt_requires_terminal_journal_selector_and_role_storage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_id = "4" * 32
            candidate = selector.render_candidate(
                root, run_id, "rehearsal:" + "3" * 32, "old", SHA_A
            )
            selected = selector.selector_cas(root, "ABSENT", candidate)
            payload = journal_payload()
            payload["candidateSelectorSha256"] = selected["selector"]["sha256"]
            journal = selector.create_journal(root, payload)
            for phase in (
                "INGRESS_STOPPED",
                "SELECTOR_COMMITTED",
                "INGRESS_STARTED",
                "OBSERVED_OLD",
                "CONFIRMED",
            ):
                journal = selector.update_journal(root, journal["sha256"], phase)
            receipt = {
                "schema": "estakada.r7c-receipt-v1",
                "scope": payload["scope"],
                "runId": run_id,
                "result": "CONFIRMED",
                "journalSha256": journal["sha256"],
                "selectorSha256": selected["selector"]["sha256"],
                "implementationImageBindingSha256": SHA_A,
                "ingressId": CONTAINER_C,
                "oldTargetId": CONTAINER_A,
                "newTargetId": CONTAINER_B,
                "expectedSelector": "ABSENT",
                "observedRole": "old",
                "observedGenerationSha256": SHA_A,
                "storageBindingSha256": SHA_A,
                "mutationBitmap": payload["mutationBitmap"],
                "cleanup": "EXACT",
            }
            broken = dict(receipt, storageBindingSha256=SHA_B)
            with self.assertRaises(RuntimeError):
                selector.finalize_receipt(root, broken)
            finalized = selector.finalize_receipt(root, receipt)
            self.assertRegex(finalized["sha256"], r"^[0-9a-f]{64}$")
            closed = selector.close_operation(
                root, finalized["sha256"], journal["sha256"], finalized
            )
            self.assertEqual(closed["state"], "ABSENT")
            self.assertIsNone(selector.inspect_state(root)["journal"])
            self.assertIsNone(selector.inspect_state(root)["receipt"])


class CutoverSourceOracleTests(unittest.TestCase):
    def test_nginx_and_compose_are_closed_to_local_read_only_cutover(self) -> None:
        project = Path(__file__).resolve().parents[1]
        http = (project / "environment/rebuild7-cutover/http.conf").read_text(
            encoding="utf-8"
        )
        compose = (project / "environment/rebuild7-cutover/compose.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("limit_except GET HEAD { deny all; }", http)
        self.assertIn("location = /request/submit/ { return 404; }", http)
        self.assertNotIn("ESTAKADA_RESTORE_VERIFY_WRITE", compose)
        self.assertIn("127.0.0.1:${R7C_LOOPBACK_PORT:?required}:8080", compose)
        self.assertNotIn("/var/run/docker.sock", compose)
        self.assertNotRegex(compose, r"(?i)https?://(?!localhost)")

    def test_implementation_inventory_covers_every_cutover_runtime_source(self) -> None:
        project = Path(__file__).resolve().parents[1]
        inventory = selector.implementation_inventory(project)
        names = {row["path"] for row in inventory["files"]}
        required = {
            "environment/rebuild7-cutover/compose.yaml",
            "environment/rebuild7-cutover/http.conf",
            "environment/rebuild7-cutover/nginx.conf",
            "environment/rebuild7-cutover/nginx-validate.conf",
            "scripts/rebuild7-selector.ps1",
            "scripts/test-rebuild7-selector.ps1",
            "tools/rebuild7_selector.py",
            "tools/rebuild7_selector_probe.py",
        }
        self.assertTrue(required <= names)

    def test_recover_preserves_inspected_journal_digest_for_cas(self) -> None:
        project = Path(__file__).resolve().parents[1]
        coordinator = (project / "scripts/rebuild7-selector.ps1").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            coordinator,
            r"(?s)\$journal = \$state\.journal\.value\s+"
            r"Assert-Hex \(\[string\]\$state\.journal\.sha256\) 64 "
            r"'R7C_RECOVERY_JOURNAL_INVALID'\s+"
            r"\$journal \| Add-Member -MemberType NoteProperty -Name sha256 "
            r"-Value \(\[string\]\$state\.journal\.sha256\)",
        )


if __name__ == "__main__":
    unittest.main()
