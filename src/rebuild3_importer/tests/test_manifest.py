import copy
import hashlib
import json
import unittest

from rebuild3_importer.manifest import ManifestError, ManifestLimits, parse_public_manifest


IDS = {
    "home": "00000000-0000-4000-8000-000000000001",
    "gallery_page": "00000000-0000-4000-8000-000000000002",
    "route_home": "00000000-0000-4000-8000-000000000003",
    "route_gallery": "00000000-0000-4000-8000-000000000004",
    "content": "00000000-0000-4000-8000-000000000005",
    "logo": "00000000-0000-4000-8000-000000000006",
    "gallery": "00000000-0000-4000-8000-000000000007",
    "file_content": "00000000-0000-4000-8000-000000000008",
    "file_logo": "00000000-0000-4000-8000-000000000009",
    "file_gallery": "00000000-0000-4000-8000-00000000000a",
    "usage_content": "00000000-0000-4000-8000-00000000000b",
    "usage_logo": "00000000-0000-4000-8000-00000000000c",
    "album": "00000000-0000-4000-8000-00000000000d",
    "photo": "00000000-0000-4000-8000-00000000000e",
    "settings": "00000000-0000-4000-8000-00000000000f",
}
def _page(page_id, kind, position):
    common = {"seo": {"title": kind, "description": "", "allow_index": True},
              "heading": {"h1": kind}}
    if kind == "home":
        fields = {**common, "lead": "<p>Lead</p>", "service_refs": [], "process_steps": [],
                  "about": "<p>About</p>", "brand_refs": [], "review_refs": [],
                  "contact_text": "<p>Contacts</p>", "media": {
                      "hero": IDS["content"], "service_cards": [], "process": [],
                      "works": [], "brand_logos": []}}
    else:
        fields = {**common, "intro": "<p>Gallery</p>"}
    payload = {"schema": "estakada.page-content", "schema_version": 1, "kind": kind, "fields": fields}
    payload_hash = hashlib.sha256(encoded(payload)).hexdigest()
    return {"id": page_id, "name": kind, "kind": kind, "parent_id": None, "position": position,
            "is_published": True, "content_generation": 1,
            "current": {"payload": payload, "sha256": payload_hash,
            "created_at": "2026-11-17T00:00:00.000000Z"}, "previous": None}


def document():
    sections = {
        "routes": [
            {"id": IDS["route_home"], "page_id": IDS["home"], "target": "/", "mode": "PRIMARY", "outcome": "home"},
            {"id": IDS["route_gallery"], "page_id": IDS["gallery_page"], "target": "/gallery/", "mode": "PRIMARY", "outcome": "gallery_album"},
        ],
        "pages": [_page(IDS["home"], "home", 0), _page(IDS["gallery_page"], "gallery_album", 1)],
        "assets": [
            {"id": IDS["content"], "purpose": "CONTENT", "source_sha256": "1" * 64, "state": "READY"},
            {"id": IDS["logo"], "purpose": "SITE_ASSET", "source_sha256": "2" * 64, "state": "READY"},
            {"id": IDS["gallery"], "purpose": "GALLERY_ORIGINAL", "source_sha256": "3" * 64, "state": "READY"},
        ],
        "files": [
            {"id": IDS["file_content"], "asset_id": IDS["content"], "kind": "MAIN", "source_path": "content.png", "sha256": "4" * 64, "byte_size": 10, "mime_type": "image/png", "width": 10, "height": 10},
            {"id": IDS["file_logo"], "asset_id": IDS["logo"], "kind": "MAIN", "source_path": "logo.png", "sha256": "5" * 64, "byte_size": 20, "mime_type": "image/png", "width": 20, "height": 20},
            {"id": IDS["file_gallery"], "asset_id": IDS["gallery"], "kind": "LEGACY_PUBLIC", "source_path": "gallery.png", "sha256": "6" * 64, "byte_size": 30, "mime_type": "image/png", "width": 30, "height": 30},
        ],
        "usages": [
            {"id": IDS["usage_content"], "asset_id": IDS["content"], "scope": "PAGE_CURRENT", "target_uuid": IDS["home"], "slot": "hero", "position": 0},
            {"id": IDS["usage_logo"], "asset_id": IDS["logo"], "scope": "SITE_SETTINGS", "target_uuid": IDS["settings"], "slot": "logo", "position": 0},
        ],
        "gallery_albums": [{"id": IDS["album"], "page_id": IDS["gallery_page"], "generation": 1, "position": 0}],
        "gallery_photos": [{"id": IDS["photo"], "album_id": IDS["album"], "asset_id": IDS["gallery"], "position": 0, "alt": "Работа"}],
    }
    settings = {"id": IDS["settings"], "structure_generation": 1, "settings_generation": 1,
        "organization_name": "Эстакада", "legal_name": None, "phone_display": "+7 499 110-25-52",
        "phone_e164": "+74991102552", "address": "Москва", "opening_hours": "09:00–21:00",
        "contact_email": "owner@example.test", "map_url": "https://example.test/map",
        "max_url": None, "telegram_url": None, "logo_asset_id": IDS["logo"]}
    unsigned = {"version": 1, "snapshot_id": "snapshot-1", "site_settings": settings, "sections": sections}
    digest = hashlib.sha256(json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**unsigned, "digest": digest}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def reseal(value):
    unsigned = {key: value[key] for key in ("version", "snapshot_id", "site_settings", "sections")}
    value["digest"] = hashlib.sha256(encoded(unsigned)).hexdigest()
    return value


LIMITS = ManifestLimits(2, 2, 3, 3, 2, 1, 1, 100_000, 60, 30, frozenset())


class ManifestContractTests(unittest.TestCase):
    def test_accepts_one_closed_coherent_projection(self):
        result = parse_public_manifest(encoded(document()), LIMITS)
        self.assertEqual(result.snapshot_id, "snapshot-1")

    def test_preserves_two_identities_for_one_exact_source_path(self):
        value = document(); first = value["sections"]["files"][0]; second = value["sections"]["files"][1]
        second.update({key: first[key] for key in ("source_path", "sha256", "byte_size", "mime_type", "width", "height")})
        value["sections"]["assets"][1]["source_sha256"] = value["sections"]["assets"][0]["source_sha256"]
        limits = ManifestLimits(2, 2, 3, 3, 2, 1, 1, 100_000, 50, 30, frozenset())
        result = parse_public_manifest(encoded(reseal(value)), limits)
        self.assertEqual(len(result.sections["files"]), 3)

    def test_rejects_same_source_path_with_conflicting_descriptor(self):
        value = document(); value["sections"]["files"][1]["source_path"] = "content.png"
        with self.assertRaisesRegex(ManifestError, "source-descriptor-drift"):
            parse_public_manifest(encoded(reseal(value)), LIMITS)
        value = document(); first = value["sections"]["files"][0]; second = value["sections"]["files"][1]
        second.update({key: first[key] for key in ("source_path", "sha256", "byte_size", "mime_type", "width", "height")})
        limits = ManifestLimits(2, 2, 3, 3, 2, 1, 1, 100_000, 50, 30, frozenset())
        with self.assertRaisesRegex(ManifestError, "source-descriptor-drift"):
            parse_public_manifest(encoded(reseal(value)), limits)

    def test_rejects_unknown_noncanonical_and_duplicate_json(self):
        unknown = document(); unknown["extra"] = True
        with self.assertRaises(ManifestError): parse_public_manifest(encoded(unknown), LIMITS)
        with self.assertRaisesRegex(ManifestError, "manifest-noncanonical"):
            parse_public_manifest(json.dumps(document(), ensure_ascii=False).encode(), LIMITS)
        with self.assertRaisesRegex(ManifestError, "duplicate-key"):
            parse_public_manifest(b'{"version":1,"version":1}', LIMITS)
        for version in (True, 1.0):
            value = document(); value["version"] = version; reseal(value)
            with self.subTest(version=version), self.assertRaisesRegex(ManifestError, "manifest-version"):
                parse_public_manifest(encoded(value), LIMITS)
    def test_rejects_digest_path_payload_and_usage_drift(self):
        cases = []
        bad = document(); bad["sections"]["files"][0]["source_path"] = "../content.png"; cases.append(bad)
        bad = document(); bad["sections"]["pages"][0]["current"]["payload"] = {"changed": True}; cases.append(bad)
        bad = document(); bad["sections"]["usages"][0]["position"] = 1; cases.append(bad)
        for value in cases:
            reseal(value)
            with self.subTest(value=value), self.assertRaises(ManifestError):
                parse_public_manifest(encoded(value), LIMITS)

    def test_requires_positive_generation_and_canonical_utc_timestamps(self):
        for generation in (0, True, 1.0):
            value = document(); value["sections"]["pages"][0]["content_generation"] = generation
            with self.subTest(generation=generation), self.assertRaisesRegex(ManifestError, "content-generation"):
                parse_public_manifest(encoded(reseal(value)), LIMITS)
        for timestamp in (
            "2026-11-17T00:00:00Z",
            "2026-11-17T00:00:00.000000 ",
            "2026-11-17T00:00:00.000000z",
            "2026-11-17T00:00:00.000000+00:00",
            "2026-11-17T03:00:00.000000+03:00",
            "2026-02-30T00:00:00.000000Z",
        ):
            value = document(); value["sections"]["pages"][0]["current"]["created_at"] = timestamp
            with self.subTest(timestamp=timestamp), self.assertRaisesRegex(ManifestError, "page-created"):
                parse_public_manifest(encoded(reseal(value)), LIMITS)
        value = document()
        value["sections"]["pages"][1]["previous"] = copy.deepcopy(
            value["sections"]["pages"][1]["current"]
        )
        value["sections"]["pages"][1]["previous"]["created_at"] = "2026-11-17T00:00:00.000000z"
        with self.assertRaisesRegex(ManifestError, "page-created"):
            parse_public_manifest(encoded(reseal(value)), LIMITS)

    def test_rejects_private_or_absolute_values_and_wrong_projection(self):
        for mutate in (
            lambda d: d["site_settings"].__setitem__("map_url", "https://user@example.test/map"),
            lambda d: d["site_settings"].__setitem__("map_url", "https://exa mple.test/map"),
            lambda d: d["site_settings"].__setitem__("map_url", "https://example.test:99999/map"),
            lambda d: d["site_settings"].__setitem__("map_url", "https://example.test/%0Amap"),
            lambda d: d["site_settings"].__setitem__("contact_email", "owner@invalid"),
            lambda d: d["sections"]["files"][0].__setitem__("source_path", "C:/secret.png"),
            lambda d: d["sections"]["files"][0].__setitem__("source_path", "CON.png"),
            lambda d: d["sections"]["files"][0].__setitem__("source_path", "no_extension"),
            lambda d: d["sections"]["routes"][0].__setitem__("target", "https://example.test/"),
            lambda d: d["sections"]["routes"][0].__setitem__("target", "/%2e%2e/private"),
            lambda d: d["sections"]["gallery_albums"][0].__setitem__("page_id", IDS["home"]),
            lambda d: d["sections"]["gallery_photos"][0].__setitem__("position", 1),
        ):
            value = document(); mutate(value)
            reseal(value)
            with self.assertRaises(ManifestError): parse_public_manifest(encoded(value), LIMITS)

    def test_rejects_casefold_collision_but_allows_repeated_gallery_asset(self):
        value = document(); value["sections"]["files"][0]["source_path"] = "Same.png"; value["sections"]["files"][1]["source_path"] = "same.png"
        with self.assertRaises(ManifestError): parse_public_manifest(encoded(reseal(value)), LIMITS)
        value = document(); duplicate = copy.deepcopy(value["sections"]["gallery_photos"][0]); duplicate["id"] = "00000000-0000-4000-8000-000000000010"; duplicate["position"] = 1
        value["sections"]["gallery_photos"].append(duplicate)
        limits = ManifestLimits(2, 2, 3, 3, 2, 1, 2, 100_000, 60, 30, frozenset())
        result = parse_public_manifest(encoded(reseal(value)), limits)
        self.assertEqual(len(result.sections["gallery_photos"]), 2)

    def test_rejects_utf8_caps_totals_svg_and_previous_usage_drift(self):
        with self.assertRaisesRegex(ManifestError, "manifest-json"):
            parse_public_manifest(b"\xff", LIMITS)
        tiny = ManifestLimits(2, 2, 3, 3, 2, 1, 1, 10, 60, 30, frozenset())
        with self.assertRaisesRegex(ManifestError, "manifest-bytes"):
            parse_public_manifest(encoded(document()), tiny)
        mutations = []
        value = document(); value["sections"]["routes"].pop(); mutations.append((value, LIMITS))
        value = document(); value["sections"]["files"][0]["byte_size"] = 11; mutations.append((value, LIMITS))
        value = document(); file = value["sections"]["files"][0]; file.update(
            {"source_path": "content.svg", "mime_type": "image/svg+xml", "width": None, "height": None}
        ); mutations.append((value, LIMITS))
        value = document(); usage = copy.deepcopy(value["sections"]["usages"][0]); usage.update(
            {"id": "00000000-0000-4000-8000-000000000011", "scope": "PAGE_PREVIOUS"}
        ); value["sections"]["usages"].append(usage)
        mutations.append((value, ManifestLimits(2, 2, 3, 3, 3, 1, 1, 100_000, 60, 30, frozenset())))
        for value, limits in mutations:
            with self.subTest(value=value), self.assertRaises(ManifestError):
                parse_public_manifest(encoded(reseal(value)), limits)

    def test_imported_raster_dimensions_are_optional_but_never_partial_or_invalid(self):
        value = document()
        value["sections"]["files"][0].update({"width": None, "height": None})
        parsed = parse_public_manifest(encoded(reseal(value)), LIMITS)
        self.assertIsNone(parsed.sections["files"][0]["width"])
        self.assertIsNone(parsed.sections["files"][0]["height"])

        for width, height in ((None, 1), (1, None), (0, 1), (1, 10_001), (True, 1)):
            with self.subTest(width=width, height=height):
                value = document()
                value["sections"]["files"][0].update(
                    {"width": width, "height": height},
                )
                with self.assertRaisesRegex(ManifestError, "file-dimensions"):
                    parse_public_manifest(encoded(reseal(value)), LIMITS)


if __name__ == "__main__":
    unittest.main()
