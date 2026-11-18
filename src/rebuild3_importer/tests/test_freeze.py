import hashlib
import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from unittest import TestCase

from rebuild3_importer.freeze import (
    PUBLIC_MEDIA_SQL,
    PUBLIC_PAGES_SQL,
    PUBLIC_ROUTES_SQL,
    PUBLIC_SHARED_SQL,
    MAX_PUBLIC_MEDIA_FACTS,
    MAX_PUBLIC_PAGES,
    MAX_PUBLIC_ROUTES,
    MAX_PUBLIC_SHARED,
    EXACT_PAGES,
    EXACT_ROUTES,
    EXACT_GALLERY_PHOTOS,
    EXACT_PACKAGE_MEDIA,
    EXACT_SOURCE_MEDIA,
    EXACT_TARGET_MEDIA,
    ApprovedPage,
    ApprovedRoute,
    FreezeError,
    FreezePackage,
    MediaBinding,
    UsageBinding,
    _validate_media_projection,
    _validate_shared,
    build_public_manifest,
    freeze_package_digest,
)
from rebuild3_importer.manifest import ManifestLimits
from rebuild3_importer.source import SourceSession


PAGE = uuid.UUID("00000000-0000-4000-8000-000000000001")
ROUTE = uuid.UUID("00000000-0000-4000-8000-000000000002")
CONTENT = uuid.UUID("00000000-0000-4000-8000-000000000003")
LOGO = uuid.UUID("00000000-0000-4000-8000-000000000004")
CONTENT_FILE = uuid.UUID("00000000-0000-4000-8000-000000000005")
LOGO_FILE = uuid.UUID("00000000-0000-4000-8000-000000000006")
CONTENT_USAGE = uuid.UUID("00000000-0000-4000-8000-000000000007")
LOGO_USAGE = uuid.UUID("00000000-0000-4000-8000-000000000008")
SETTINGS = uuid.UUID("00000000-0000-4000-8000-000000000009")
SESSION = SourceSession(731, 991, "10:20:")
STAMP = datetime(2026, 11, 17, 3, 0, tzinfo=timezone.utc)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


PAYLOAD = {
    "schema": "estakada.page-content",
    "schema_version": 1,
    "kind": "home",
    "fields": {
        "seo": {"title": "Home", "description": "", "allow_index": True},
        "heading": {"h1": "Home"},
        "lead": "<p>Lead</p>",
        "service_refs": [],
        "process_steps": [],
        "about": "<p>About</p>",
        "brand_refs": [],
        "review_refs": [],
        "contact_text": "<p>Contacts</p>",
        "media": {
            "hero": str(CONTENT),
            "service_cards": [],
            "process": [],
            "works": [],
            "brand_logos": [],
        },
    },
}
PAYLOAD_HASH = hashlib.sha256(canonical(PAYLOAD)).hexdigest()


class Executor:
    def __init__(self):
        guard = (0, SESSION.backend_pid, SESSION.transaction_id, SESSION.snapshot_id)
        self.rows = {
            PUBLIC_PAGES_SQL: (
                guard + (None,) * 17,
                (1, *guard[1:], PAGE, "Home", "home", None, 0, True, 1, 1,
                 "estakada.page-content@1", PAYLOAD, PAYLOAD_HASH, STAMP, False,
                 None, None, None, None),
            ),
            PUBLIC_ROUTES_SQL: (
                guard + (None,) * 5,
                (1, *guard[1:], ROUTE, PAGE, "/", "primary", False),
            ),
            PUBLIC_SHARED_SQL: (guard + (None,) * 12,),
            PUBLIC_MEDIA_SQL: (guard + (None,) * 3,),
        }

    def fetch_one(self, _sql):
        raise AssertionError("builder uses only guarded row sets")

    def fetch_all(self, sql):
        return self.rows[sql]


def package():
    return FreezePackage(
        pages=(ApprovedPage(
            PAGE, "Home", "home", "home", None, 0, True, 1,
            "estakada.page-content@1", PAYLOAD_HASH,
            "2026-11-17T03:00:00.000000Z", PAYLOAD,
            None, None, None, None,
        ),),
        routes=(ApprovedRoute(ROUTE, PAGE, "/", "primary", False, "PRIMARY", "home"),),
        source_shared=(),
        source_media=(),
        site_settings={
            "id": str(SETTINGS), "structure_generation": 1, "settings_generation": 1,
            "organization_name": "Эстакада", "legal_name": None,
            "phone_display": "+7 499 110-25-52", "phone_e164": "+74991102552",
            "address": "Москва", "opening_hours": "09:00–21:00",
            "contact_email": "owner@example.test", "map_url": "https://example.test/map",
            "max_url": None, "telegram_url": None, "logo_asset_id": str(LOGO),
        },
        assets=(
            {"id": str(CONTENT), "purpose": "CONTENT", "source_sha256": "1" * 64, "state": "READY"},
            {"id": str(LOGO), "purpose": "SITE_ASSET", "source_sha256": "2" * 64, "state": "READY"},
        ),
        files=(
            {"id": str(CONTENT_FILE), "asset_id": str(CONTENT), "kind": "MAIN",
             "source_path": "content.png", "sha256": "3" * 64, "byte_size": 10,
             "mime_type": "image/png", "width": 10, "height": 10},
            {"id": str(LOGO_FILE), "asset_id": str(LOGO), "kind": "MAIN",
             "source_path": "logo.png", "sha256": "4" * 64, "byte_size": 20,
             "mime_type": "image/png", "width": 20, "height": 20},
        ),
        usages=(
            {"id": str(CONTENT_USAGE), "asset_id": str(CONTENT), "scope": "PAGE_CURRENT",
             "target_uuid": str(PAGE), "slot": "hero", "position": 0},
            {"id": str(LOGO_USAGE), "asset_id": str(LOGO), "scope": "SITE_SETTINGS",
             "target_uuid": str(SETTINGS), "slot": "logo", "position": 0},
        ),
        gallery_albums=(),
        gallery_photos=(),
        media_bindings=(
            MediaBinding(CONTENT, CONTENT_FILE, "APPROVED_PACKAGE", None, None, False),
            MediaBinding(LOGO, LOGO_FILE, "APPROVED_PACKAGE", None, None, False),
        ),
        usage_bindings=(
            UsageBinding(CONTENT_USAGE, None),
            UsageBinding(LOGO_USAGE, None),
        ),
    )


LIMITS = ManifestLimits(1, 1, 2, 2, 2, 0, 0, 100_000, 30, 0, frozenset())


def build(executor, value=None):
    value = package() if value is None else value
    return build_public_manifest(
        executor, SESSION, value, LIMITS, freeze_package_digest(value)
    )


class FreezeTests(TestCase):
    def test_public_cardinality_is_exact_112_pages_and_114_stored_routes(self):
        self.assertEqual((EXACT_PAGES, EXACT_ROUTES), (112, 114))
        self.assertEqual((MAX_PUBLIC_PAGES, MAX_PUBLIC_ROUTES), (112, 114))
        self.assertIn("LIMIT 114", PUBLIC_PAGES_SQL)
        self.assertIn("LIMIT 116", PUBLIC_ROUTES_SQL)

    def test_shared_file_key_and_inclusive_size_bounds_are_exact(self):
        digest = "a" * 64
        valid_key = "blobs/aa/" + "aa" + "0" * 30 + ".html"

        def row(file_key=valid_key, byte_size=0):
            return (
                uuid.uuid4(), "header", 1, uuid.uuid4(), 1, "shared@1",
                "file", file_key, digest, byte_size, digest, "",
            )

        _validate_shared((row(byte_size=0), row(byte_size=1_048_576),))
        for file_key, byte_size in (
            (valid_key, 1_048_577),
            ("blobs/aa/bb" + "0" * 30 + ".html", 1),
            (valid_key.replace("/", "\\"), 1),
        ):
            with self.subTest(file_key=file_key, byte_size=byte_size):
                with self.assertRaisesRegex(FreezeError, "shared-file-drift"):
                    _validate_shared((row(file_key=file_key, byte_size=byte_size),))

    def test_synthetic_cardinality_cannot_bypass_production_arithmetic(self):
        with self.assertRaisesRegex(FreezeError, "media-binding-arithmetic"):
            build(Executor())

    def test_package_authority_digest_is_external_and_shared_inline_hash_is_checked(self):
        with self.assertRaisesRegex(FreezeError, "freeze-package-digest"):
            build_public_manifest(Executor(), SESSION, package(), LIMITS, "0" * 64)

        executor = Executor()
        guard = executor.rows[PUBLIC_SHARED_SQL][0]
        shared = (
            uuid.UUID("00000000-0000-4000-8000-000000000020"), "header", 1,
            uuid.UUID("00000000-0000-4000-8000-000000000021"), 1, "shared@1",
            "inline", "", "0" * 64, None, "", "<p>Header</p>",
        )
        executor.rows[PUBLIC_SHARED_SQL] = (guard, (1, *guard[1:4], *shared))
        value = replace(package(), source_shared=(shared,))
        with self.assertRaisesRegex(FreezeError, "shared-inline-drift"):
            build(executor, value)

    def production_media(self):
        assets = []
        files = []
        facts = []
        bindings = []
        for index in range(EXACT_TARGET_MEDIA):
            asset_id = uuid.UUID(int=1000 + index)
            file_id = uuid.UUID(int=2000 + index)
            digest = f"{index + 1:064x}"
            source_path = f"cohort/file-{index}.png"
            assets.append({
                "id": str(asset_id), "purpose": "CONTENT",
                "source_sha256": digest, "state": "READY",
            })
            files.append({
                "id": str(file_id), "asset_id": str(asset_id), "kind": "MAIN",
                "source_path": source_path, "sha256": digest, "byte_size": index + 1,
                "mime_type": "image/png", "width": 1, "height": 1,
            })
            if index < EXACT_SOURCE_MEDIA:
                facts.extend((
                    ("asset", str(asset_id), ("folder", "ready", "migration", False, "", digest)),
                    ("file", str(file_id), (str(asset_id), "main", source_path, digest, index + 1)),
                ))
                bindings.append(MediaBinding(
                    asset_id, file_id, "SOURCE_DB", asset_id, file_id, index == 0,
                ))
            else:
                bindings.append(MediaBinding(
                    asset_id, file_id, "APPROVED_PACKAGE", None, None, False,
                ))
        usage_id = uuid.UUID(int=4000)
        source_usage_id = uuid.UUID(int=4001)
        usages = ({
            "id": str(usage_id), "asset_id": assets[0]["id"],
            "scope": "PAGE_CURRENT", "target_uuid": str(PAGE),
            "slot": "hero", "position": 0,
        },)
        facts.append((
            "usage", str(source_usage_id),
            (assets[0]["id"], "current_page", str(PAGE), "hero",
             "eligible", "PAGE_CURRENT", str(PAGE)),
        ))
        package_value = FreezePackage(
            (), (), (), tuple(facts), {}, tuple(assets), tuple(files), usages, (), (),
            tuple(bindings), (UsageBinding(usage_id, source_usage_id),),
        )
        return tuple(facts), package_value

    def test_exact_production_media_and_derived_usage_classification(self):
        facts, package_value = self.production_media()
        self.assertEqual(EXACT_SOURCE_MEDIA + EXACT_PACKAGE_MEDIA, EXACT_TARGET_MEDIA)
        _validate_media_projection(facts, package_value)
        changed = list(facts)
        usage = list(changed[-1][2])
        usage[4] = "excluded"
        changed[-1] = (changed[-1][0], changed[-1][1], tuple(usage))
        with self.assertRaises(FreezeError):
            _validate_media_projection(tuple(changed), package_value)

    def test_selected_revision_usage_mapping_uses_target_projection_not_legacy_slot(self):
        facts, package_value = self.production_media()
        source_usage_id = facts[-1][1]
        target_usage_id = package_value.usages[0]["id"]
        for kind, scope, target in (
            ("ordinary_version", "PAGE_CURRENT", str(PAGE)),
            ("stable_version", "PAGE_PREVIOUS", str(PAGE)),
        ):
            changed = list(facts)
            changed[-1] = (
                "usage", source_usage_id,
                (package_value.assets[0]["id"], kind, str(uuid.uuid4()), "embedded:legacy",
                 "eligible", scope, target),
            )
            _validate_media_projection(
                tuple(changed),
                replace(
                    package_value,
                    usages=({
                        **package_value.usages[0], "scope": scope,
                        "target_uuid": target,
                    },),
                    usage_bindings=(UsageBinding(uuid.UUID(target_usage_id), uuid.UUID(source_usage_id)),),
                ),
            )

        changed = list(facts)
        changed[-1] = (
            "usage", source_usage_id,
            (package_value.assets[0]["id"], "current_page", str(PAGE),
             "embedded:legacy", "eligible", "PAGE_PREVIOUS", str(PAGE)),
        )
        with self.assertRaisesRegex(FreezeError, "usage-binding-source"):
            _validate_media_projection(
                tuple(changed),
                replace(
                    package_value,
                    usages=({**package_value.usages[0], "scope": "PAGE_PREVIOUS"},),
                    usage_bindings=(UsageBinding(
                        uuid.UUID(target_usage_id), uuid.UUID(source_usage_id),
                    ),),
                ),
            )

    def test_many_source_ledgers_project_to_one_target_usage_and_shared_only_to_logo(self):
        facts, package_value = self.production_media()
        target_usage_id = uuid.UUID(package_value.usages[0]["id"])
        first_source_id = uuid.UUID(facts[-1][1])
        second_source_id = uuid.UUID(int=4010)
        second = (
            "usage", str(second_source_id),
            (package_value.assets[0]["id"], "ordinary_version", str(uuid.uuid4()),
             "embedded:old", "eligible", "PAGE_CURRENT", str(PAGE)),
        )
        _validate_media_projection(
            (*facts, second),
            replace(package_value, usage_bindings=(
                UsageBinding(target_usage_id, first_source_id),
                UsageBinding(target_usage_id, second_source_id),
            )),
        )

        logo_usage = {
            "id": str(uuid.UUID(int=4020)),
            "asset_id": package_value.assets[0]["id"],
            "scope": "SITE_SETTINGS", "target_uuid": str(SETTINGS),
            "slot": "logo", "position": 0,
        }
        shared = list(facts)
        shared[-1] = (
            "usage", facts[-1][1],
            (package_value.assets[0]["id"], "shared_block", str(uuid.uuid4()),
             "embedded:logo", "eligible", None, None),
        )
        _validate_media_projection(
            tuple(shared),
            replace(
                package_value,
                usages=(logo_usage,),
                usage_bindings=(UsageBinding(
                    uuid.UUID(logo_usage["id"]), first_source_id,
                ),),
            ),
        )

        wrong = {**logo_usage, "scope": "PAGE_CURRENT", "target_uuid": str(PAGE)}
        with self.assertRaisesRegex(FreezeError, "usage-binding-source"):
            _validate_media_projection(
                tuple(shared),
                replace(
                    package_value,
                    usages=(wrong,),
                    usage_bindings=(UsageBinding(
                        uuid.UUID(wrong["id"]), first_source_id,
                    ),),
                ),
            )

    def test_eligible_source_usage_cannot_be_omitted_from_bindings(self):
        facts, package_value = self.production_media()
        with self.assertRaisesRegex(FreezeError, "usage-binding-coverage"):
            _validate_media_projection(
                facts, replace(package_value, usages=(), usage_bindings=())
            )

    def test_gallery_photo_owns_exact_current_and_revision_pair_without_target_usage(self):
        facts, package_value = self.production_media()
        album_id = str(uuid.UUID(int=6000))
        gallery_facts = list(facts[:-1])
        for index in range(EXACT_GALLERY_PHOTOS):
            gallery_facts.extend((
                (
                "usage", str(uuid.UUID(int=7000 + index * 2)),
                (package_value.assets[index]["id"], "current_page", str(PAGE),
                 f"embedded:{index}", "eligible", "PAGE_CURRENT", str(PAGE)),
                ),
                (
                "usage", str(uuid.UUID(int=7001 + index * 2)),
                (package_value.assets[index]["id"], "ordinary_version", str(uuid.uuid4()),
                 f"embedded:{index}", "eligible", "PAGE_CURRENT", str(PAGE)),
                ),
            ))
        photos = tuple({
            "id": str(uuid.UUID(int=8000 + index)), "album_id": album_id,
            "asset_id": package_value.assets[index]["id"],
            "position": index, "alt": f"Работа {index}",
        } for index in range(EXACT_GALLERY_PHOTOS))
        gallery = replace(
            package_value,
            usages=(),
            usage_bindings=(),
            gallery_albums=({
                "id": album_id, "page_id": str(PAGE),
                "generation": 1, "position": 0,
            },),
            gallery_photos=photos,
        )
        _validate_media_projection(tuple(gallery_facts), gallery)
        with self.assertRaisesRegex(FreezeError, "usage-binding-coverage"):
            _validate_media_projection(
                tuple(gallery_facts),
                replace(gallery, gallery_albums=(), gallery_photos=()),
            )
        broken = list(gallery_facts)
        usage = list(broken[-1][2])
        usage[1] = "stable_version"
        broken[-1] = (broken[-1][0], broken[-1][1], tuple(usage))
        with self.assertRaisesRegex(FreezeError, "usage-gallery-coverage"):
            _validate_media_projection(tuple(broken), gallery)

        with self.assertRaisesRegex(FreezeError, "usage-gallery-coverage"):
            _validate_media_projection(tuple(gallery_facts[:-1]), gallery)

        duplicate_photos = list(photos)
        duplicate_photos[-1] = {
            **duplicate_photos[-1], "asset_id": duplicate_photos[0]["asset_id"],
        }
        with self.assertRaisesRegex(FreezeError, "usage-gallery-coverage"):
            _validate_media_projection(
                tuple(gallery_facts),
                replace(gallery, gallery_photos=tuple(duplicate_photos)),
            )

        duplicate_usage = {
            "id": str(uuid.UUID(int=9999)),
            "asset_id": package_value.assets[0]["id"],
            "scope": "PAGE_CURRENT", "target_uuid": str(PAGE),
            "slot": "hero", "position": 0,
        }
        with self.assertRaisesRegex(FreezeError, "usage-gallery-coverage"):
            _validate_media_projection(
                tuple(gallery_facts),
                replace(
                    gallery,
                    usages=(duplicate_usage,),
                    usage_bindings=(UsageBinding(uuid.UUID(duplicate_usage["id"]), None),),
                ),
            )

    def test_session_page_timestamp_and_media_drift_fail_closed(self):
        executor = Executor()
        rows = list(executor.rows[PUBLIC_ROUTES_SQL])
        rows[1] = (1, 999, *rows[1][2:])
        executor.rows[PUBLIC_ROUTES_SQL] = tuple(rows)
        with self.assertRaisesRegex(FreezeError, "source-public-session-drift"):
            build(executor)

        executor = Executor()
        rows = list(executor.rows[PUBLIC_PAGES_SQL])
        rows[1] = (*rows[1][:8], 1, *rows[1][9:])
        executor.rows[PUBLIC_PAGES_SQL] = tuple(rows)
        with self.assertRaises(FreezeError):
            build(executor)

        executor = Executor()
        rows = list(executor.rows[PUBLIC_PAGES_SQL])
        rows[1] = (*rows[1][:15], datetime(2026, 11, 17), *rows[1][16:])
        executor.rows[PUBLIC_PAGES_SQL] = tuple(rows)
        with self.assertRaisesRegex(FreezeError, "source-timestamp"):
            build(executor)

        executor = Executor()
        rows = list(executor.rows[PUBLIC_PAGES_SQL])
        rows[1] = (
            *rows[1][:15], datetime(2026, 11, 18, 3, 0, tzinfo=timezone.utc),
            *rows[1][16:],
        )
        executor.rows[PUBLIC_PAGES_SQL] = tuple(rows)
        with self.assertRaisesRegex(FreezeError, "page-source-drift"):
            build(executor)

        drift = package()
        drift = FreezePackage(
            drift.pages, drift.routes, drift.source_shared,
            (("asset", "foreign", ("ready", 1)),),
            drift.site_settings, drift.assets, drift.files, drift.usages,
            drift.gallery_albums, drift.gallery_photos, drift.media_bindings,
            drift.usage_bindings,
        )
        with self.assertRaisesRegex(FreezeError, "media-source-drift"):
            build(Executor(), drift)

    def test_revision_sequence_schema_and_newer_conflicts_fail_closed(self):
        for index, value in (
            (11, 2),
            (12, "wrong-schema"),
            (16, True),
        ):
            executor = Executor()
            rows = list(executor.rows[PUBLIC_PAGES_SQL])
            changed = list(rows[1])
            changed[index] = value
            rows[1] = tuple(changed)
            executor.rows[PUBLIC_PAGES_SQL] = tuple(rows)
            with self.subTest(index=index), self.assertRaisesRegex(FreezeError, "page-source-drift"):
                build(executor)

    def test_every_public_query_rejects_cap_plus_one(self):
        cases = (
            (PUBLIC_PAGES_SQL, MAX_PUBLIC_PAGES),
            (PUBLIC_ROUTES_SQL, MAX_PUBLIC_ROUTES),
            (PUBLIC_SHARED_SQL, MAX_PUBLIC_SHARED),
            (PUBLIC_MEDIA_SQL, MAX_PUBLIC_MEDIA_FACTS),
        )
        for sql, cap in cases:
            executor = Executor()
            sample = executor.rows[sql][-1]
            executor.rows[sql] = (executor.rows[sql][0],) + (sample,) * (cap + 1)
            with self.subTest(sql=sql), self.assertRaisesRegex(FreezeError, "source-public-guard"):
                build(executor)

    def test_media_binding_cannot_detach_target_from_source(self):
        executor = Executor()
        source_asset = uuid.UUID("00000000-0000-4000-8000-000000000010")
        source_file = uuid.UUID("00000000-0000-4000-8000-000000000011")
        guard = executor.rows[PUBLIC_MEDIA_SQL][0]
        executor.rows[PUBLIC_MEDIA_SQL] = (
            guard,
            (1, *guard[1:4], "asset", str(source_asset),
             ["folder", "ready", "migration", False, "", "3" * 64]),
            (1, *guard[1:4], "file", str(source_file),
             [str(source_asset), "main", "content.png", "3" * 64, 10]),
        )
        base = package()
        detached = FreezePackage(
            base.pages, base.routes, base.source_shared,
            tuple(row[4:] for row in executor.rows[PUBLIC_MEDIA_SQL][1:]),
            base.site_settings, base.assets, base.files, base.usages,
            base.gallery_albums, base.gallery_photos,
            (MediaBinding(CONTENT, CONTENT_FILE, "SOURCE_DB", source_asset, source_file, False),
             base.media_bindings[1]),
            base.usage_bindings,
        )
        with self.assertRaises(FreezeError):
            build(executor, detached)


if __name__ == "__main__":
    import unittest

    unittest.main()
