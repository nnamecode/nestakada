"""Isolated base-MVP export for the owner-only local visual preview."""
import base64
import hashlib
import json
import os
from pathlib import Path
import stat

from django.test import TransactionTestCase

from content.public_views import PUBLIC_CSP
from html_reserve import build as reserve_build
from html_reserve.projection import emit_maps
from html_reserve.storage import ReserveStore

from .test_test08_fixture import _counts, build_test08_fixture


MAX_INDEX_BYTES = 2 * 1024 * 1024


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_new(path, body):
    if not isinstance(body, bytes) or not 0 < len(body) <= MAX_INDEX_BYTES:
        raise AssertionError("LOCAL_PREVIEW_INDEX_SIZE_INVALID")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(body)
        while view:
            written = os.write(descriptor, view)
            if written < 1:
                raise OSError("short write")
            view = view[written:]
        os.fsync(descriptor)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            raise AssertionError("LOCAL_PREVIEW_INDEX_FILE_INVALID")
    finally:
        os.close(descriptor)


class LocalPreviewExportTests(TransactionTestCase):
    reset_sequences = True
    result = None
    media_root = None

    def test_lprev_001_export_one_verified_generation(self):
        run_id = os.environ.get("ESTAKADA_LOCAL_PREVIEW_RUN_ID", "")
        export_root = Path(os.environ.get("ESTAKADA_LOCAL_PREVIEW_ROOT", ""))
        self.assertRegex(
            run_id,
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        )
        self.assertTrue(export_root.is_absolute())
        self.assertEqual(export_root, Path("/local-preview-export"))
        self.assertTrue(export_root.is_dir())
        self.assertEqual(list(export_root.iterdir()), [])

        before = _counts()
        self.assertTrue(all(value == 0 for value in before.values()), before)
        with build_test08_fixture(self) as fixture:
            type(self).media_root = fixture["mediaRoot"]
            reserve_root = export_root / "reserve"
            reserve_build.run(root=reserve_root)
            with ReserveStore(reserve_root).locked() as store:
                pointer = store.read_pointer()
                generation = pointer["current"]
                manifest_sha = pointer["current_manifest_sha256"]
                self.assertIsNotNone(generation)
                self.assertIsNone(pointer["previous"])
                manifest = store.generation_manifest(generation, manifest_sha)

            # Reuse the reviewed pure projection validator without retaining DEV-26 output.
            self.assertGreater(len(emit_maps(manifest, generation)), 0)
            responses = manifest["responses"]
            resources = manifest["resources"]
            self.assertEqual(len(responses), 139)
            self.assertEqual(len({row["target"] for row in responses}), 139)
            self.assertEqual(sum(row["status"] == 200 for row in responses), 138)
            self.assertEqual(sum(row["status"] == 302 for row in responses), 1)
            self.assertLessEqual(manifest["totals"]["files"], 4096)
            self.assertLessEqual(manifest["totals"]["bytes"], 256 * 1024 * 1024)

            generation_root = reserve_root / "generations" / generation
            manifest_path = generation_root / "manifest.json"
            self.assertEqual(_sha(manifest_path), manifest_sha)
            response_index = []
            for row in responses:
                relative = f"reserve/generations/{generation}/responses/{row['name']}"
                path = export_root / relative
                self.assertEqual(path.stat().st_size, row["byte_size"])
                self.assertEqual(_sha(path), row["sha256"])
                if row["status"] == 200:
                    body = path.read_bytes().lower()
                    self.assertNotIn(b"csrfmiddlewaretoken", body)
                    self.assertNotIn(b"<form", body)
                response_index.append({
                    "target": row["target"], "path": relative,
                    "status": row["status"], "location": row["location"],
                    "contentType": row["content_type"],
                    "xRobotsTag": row["x_robots_tag"],
                    "securityPolicyId": row["security_policy_id"],
                    "cachePolicyId": row["cache_policy_id"],
                    "bytes": row["byte_size"], "sha256": row["sha256"],
                })
            resource_index = []
            for row in resources:
                relative = f"reserve/generations/{generation}/resources/{row['name']}"
                path = export_root / relative
                self.assertEqual(path.stat().st_size, row["byte_size"])
                self.assertEqual(_sha(path), row["sha256"])
                resource_index.append({
                    "url": row["url"], "path": relative,
                    "contentType": row["content_type"],
                    "bytes": row["byte_size"], "sha256": row["sha256"],
                })

            index = {
                "schema": "local-preview-index-v1",
                "runId": run_id,
                "generation": generation,
                "reserveManifest": {
                    "path": f"reserve/generations/{generation}/manifest.json",
                    "sha256": manifest_sha,
                },
                "headerPolicy": {
                    "contentSecurityPolicy": PUBLIC_CSP,
                    "securityPolicies": {
                        "public-v1": {"xContentTypeOptions": "nosniff"}
                    },
                    "cachePolicies": {"reserve-v1": "no-cache"},
                },
                "responses": response_index,
                "resources": resource_index,
                "totals": manifest["totals"],
            }
            index_body = _canonical(index)
            _write_new(export_root / "preview-index-v1.json", index_body)
            index_sha = hashlib.sha256(index_body).hexdigest()
            type(self).result = {
                "schema": "local-preview-export-result-v1",
                "runId": run_id,
                "fixtureBefore": before,
                "fixtureAssembled": fixture["assembled"],
                "fixtureAfter": None,
                "generation": generation,
                "reserveManifestSha256": manifest_sha,
                "indexSha256": index_sha,
                "responses": len(responses),
                "resources": len(resources),
                "totals": manifest["totals"],
                "externalDelivery": 0,
            }

        self.assertFalse(Path(type(self).media_root).exists())

    def test_lprev_002_verify_teardown_and_emit(self):
        self.assertIsNotNone(type(self).result)
        after = _counts()
        self.assertTrue(all(value == 0 for value in after.values()), after)
        self.assertFalse(Path(type(self).media_root).exists())
        result = dict(type(self).result)
        result["fixtureAfter"] = after
        encoded = base64.urlsafe_b64encode(_canonical(result)).decode().rstrip("=")
        self.assertLessEqual(len(encoded), 32768)
        print("LOCAL_PREVIEW_EXPORT_RESULT=" + encoded, flush=True)
