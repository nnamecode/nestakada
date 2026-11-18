import hashlib
import json
import uuid
from unittest import TestCase

from rebuild3_importer.content import validate_payload
from rebuild3_importer.freeze import (
    EXACT_GALLERY_ALBUMS,
    EXACT_GALLERY_PHOTOS,
    EXACT_PACKAGE_MEDIA,
    EXACT_SOURCE_MEDIA,
    EXACT_TARGET_MEDIA,
    _canonical,
    _project_public_rows,
    _validate_media_projection,
    freeze_package_digest,
)
from rebuild3_importer.freeze_authority import (
    FreezeCapture,
    _literal_page_route_inputs,
    _thaw_value,
)
from rebuild3_importer.media_authority import (
    LOGO_EVIDENCE_ID,
    _literal_media_descriptors,
    _media_evidence,
    compose_freeze_package,
    compose_run_authority,
)


def _digest(value):
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _capture():
    page_inputs, route_inputs = _literal_page_route_inputs()
    pages = []
    for row in page_inputs:
        current = row["source_current_payload"]
        previous = row["source_previous_payload"]
        pages.append((
            row["id"], row["name"], row["kind"], row["parent_id"],
            row["position"], True, row["generation"], row["generation"],
            current["schema_version"], current, _digest(current),
            "2026-11-18T00:00:00.000000Z", False, previous,
            None if previous is None else _digest(previous),
            None if previous is None else "2026-11-17T00:00:00.000000Z",
            None if previous is None else previous["schema_version"],
        ))
    routes = tuple((
        str(uuid.uuid4()), row["page_id"], row["target"],
        row["source_kind"], row["source_is_legacy"],
    ) for row in route_inputs)
    shared = (
        (str(uuid.uuid4()), "header", 1, str(uuid.uuid4()), 1,
         "header-v1", "inline", "", "0" * 64, None, "", ""),
        (str(uuid.uuid4()), "footer", 1, str(uuid.uuid4()), 1,
         "footer-v1", "inline", "", "0" * 64, None, "", ""),
    )

    descriptors = _literal_media_descriptors()
    evidence = _media_evidence()
    logo = next(row for row in evidence if row["evidence_id"] == LOGO_EVIDENCE_ID)
    logo_asset_id, logo_file_id = str(uuid.uuid4()), str(uuid.uuid4())
    media = []
    for row in descriptors:
        kind = {"MAIN": "main", "LEGACY_PUBLIC": "legacy-public"}[row["kind"]]
        media.extend((
            ("asset", row["asset_id"],
             [None, "ready", "migration", False, "", row["sha256"]]),
            ("file", row["file_id"],
             [row["asset_id"], kind, "old/key", row["sha256"], row["byte_size"]]),
        ))
    media.extend((
        ("asset", logo_asset_id,
         [None, "ready", "migration", False, "", logo["sha256"]]),
        ("file", logo_file_id,
         [logo_asset_id, "main", "old/logo.png", logo["sha256"], logo["byte_size"]]),
    ))

    usage_index = 0

    def usage(asset_id, kind, slot, classification, scope, target):
        nonlocal usage_index
        usage_index += 1
        media.append((
            "usage", str(uuid.UUID(int=100_000 + usage_index)),
            [asset_id, kind, str(uuid.uuid4()), slot, classification, scope, target],
        ))

    page_refs = []
    for row in page_inputs:
        for scope, payload in (
            ("PAGE_CURRENT", row["current_payload"]),
            ("PAGE_PREVIOUS", row["previous_payload"]),
        ):
            if payload is None:
                continue
            for slot, asset_ids in validate_payload(payload, payload["kind"]).items():
                for asset_id in asset_ids:
                    page_refs.append((asset_id, scope, row["id"], slot))
                    usage(asset_id, "current_page", "embedded:current", "eligible", scope, row["id"])
                    usage(asset_id, "ordinary_version", "embedded:revision", "eligible", scope, row["id"])
                    usage(asset_id, "draft", slot, "excluded", None, None)

    from content.dev10_gallery_apply import _read_package as _read_gallery_package

    gallery = _read_gallery_package()
    for album in gallery["albums"]:
        for photo in album["photos"]:
            usage(photo["asset_id"], "current_page", "embedded:current",
                  "eligible", "PAGE_CURRENT", album["page_id"])
            usage(photo["asset_id"], "ordinary_version", "embedded:revision",
                  "eligible", "PAGE_CURRENT", album["page_id"])
            usage(photo["asset_id"], "draft", "embedded:draft",
                  "excluded", None, None)
    for index in range(7):
        usage(logo_asset_id, "shared_block", f"embedded:logo-{index}",
              "eligible", None, None)
    if usage_index != 736 or len(page_refs) != 29:
        raise AssertionError((usage_index, len(page_refs)))
    return FreezeCapture(tuple(pages), routes, shared, tuple(media))


class MediaAuthorityTests(TestCase):
    def test_exact_literal_evidence_and_package_cohorts(self):
        evidence = _media_evidence()
        descriptors = _literal_media_descriptors()
        self.assertEqual((len(evidence), len(descriptors)), (301, 237))
        self.assertEqual(sum(row["byte_size"] for row in evidence), 56_134_441)
        self.assertEqual(
            len({(row["sha256"], row["byte_size"]) for row in descriptors}), 236,
        )
        self.assertEqual(
            sum(row["purpose"] == "GALLERY_ORIGINAL" for row in descriptors), 214,
        )

    def test_composes_closed_303_media_gallery_settings_and_usage_projection(self):
        package = compose_freeze_package(_capture())
        self.assertEqual(
            (len(package.assets), len(package.files), len(package.gallery_albums),
             len(package.gallery_photos)),
            (EXACT_TARGET_MEDIA, EXACT_TARGET_MEDIA,
             EXACT_GALLERY_ALBUMS, EXACT_GALLERY_PHOTOS),
        )
        self.assertEqual(
            sum(row.origin == "SOURCE_DB" for row in package.media_bindings),
            EXACT_SOURCE_MEDIA,
        )
        self.assertEqual(
            sum(row.origin == "APPROVED_PACKAGE" for row in package.media_bindings),
            EXACT_PACKAGE_MEDIA,
        )
        self.assertEqual(sum(row.resolved_unmatched for row in package.media_bindings), 1)
        self.assertEqual(len(package.usages), 30)
        self.assertEqual(package.site_settings["legal_name"], None)
        self.assertEqual(package.site_settings["max_url"], None)
        self.assertEqual(package.site_settings["telegram_url"], None)
        package_only_ids = {
            str(row.target_asset_id) for row in package.media_bindings
            if row.origin == "APPROVED_PACKAGE"
        }
        self.assertTrue(all(uuid.UUID(value).version == 4 for value in package_only_ids))
        _validate_media_projection(package.source_media, package)

    def test_run_authority_closes_exact_limits_and_package_digest(self):
        capture = _capture()
        package, limits, digest = compose_run_authority(capture)
        self.assertEqual(
            (limits.routes, limits.pages, limits.assets, limits.files,
             limits.usages, limits.gallery_albums, limits.gallery_photos),
            (114, 112, 303, 303, 30, 17, 214),
        )
        self.assertEqual(
            (limits.total_file_bytes, limits.gallery_file_bytes),
            (56_440_807, 41_176_391),
        )
        self.assertEqual(len(limits.trusted_svg_sha256), 3)
        pages, routes, _refs = _project_public_rows(
            tuple(_thaw_value(row) for row in capture.pages),
            tuple(_thaw_value(row) for row in capture.routes),
            package,
        )
        sections = {
            "routes": routes, "pages": pages,
            "assets": list(package.assets), "files": list(package.files),
            "usages": list(package.usages),
            "gallery_albums": list(package.gallery_albums),
            "gallery_photos": list(package.gallery_photos),
        }
        unsigned = {
            "version": 1, "snapshot_id": "1:1:" + "1" * 196,
            "site_settings": package.site_settings, "sections": sections,
        }
        root = {
            **unsigned, "digest": hashlib.sha256(_canonical(unsigned)).hexdigest(),
        }
        self.assertEqual(limits.canonical_bytes, len(_canonical(root)))
        short = {**unsigned, "snapshot_id": "1:2:"}
        short_root = {
            **short, "digest": hashlib.sha256(_canonical(short)).hexdigest(),
        }
        self.assertLessEqual(len(_canonical(short_root)), limits.canonical_bytes)
        self.assertEqual(digest, freeze_package_digest(package))
        self.assertEqual(len(package.files), limits.files)
