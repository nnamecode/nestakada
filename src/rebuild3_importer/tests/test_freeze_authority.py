import hashlib
import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

from rebuild3_importer.freeze import (
    EXACT_PAGES,
    EXACT_ROUTES,
    EXACT_SOURCE_MEDIA,
    PUBLIC_MEDIA_SQL,
    PUBLIC_PAGES_SQL,
    PUBLIC_ROUTES_SQL,
    PUBLIC_SHARED_SQL,
    FreezeError,
)
from rebuild3_importer.freeze_authority import (
    FreezeCapture,
    _literal_page_route_inputs,
    capture_source_authority,
    compose_page_route_authority,
    freeze_capture_digest,
)
from rebuild3_importer.service_media import service_media_rows
from rebuild3_importer.content import validate_payload
from rebuild3_importer.errors import ManifestError
from rebuild3_importer.source import SourceSession


SESSION = SourceSession(731, 991, "10:20:")


def guarded(width, rows):
    return (
        (0, SESSION.backend_pid, SESSION.transaction_id, SESSION.snapshot_id)
        + (None,) * (width - 4),
        *(
            (1, SESSION.backend_pid, SESSION.transaction_id, SESSION.snapshot_id)
            + tuple(row)
            for row in rows
        ),
    )


def page(index):
    value = uuid.UUID(int=index + 1)
    return (
        value, f"Page {index}", "article", None, index, False,
        1, 1, "page-content-v1", {}, "1" * 64,
        datetime(2026, 11, 18, tzinfo=timezone.utc), False,
        None, None, None, None,
    )


def route(index):
    return (
        uuid.UUID(int=10_000 + index), uuid.UUID(int=index + 1),
        f"/page-{index}", "primary", True,
    )


def media_rows():
    rows = []
    for index in range(EXACT_SOURCE_MEDIA):
        asset = str(uuid.UUID(int=20_000 + index))
        file = str(uuid.UUID(int=30_000 + index))
        rows.append(("asset", asset, [None, "ready", "source", False, "", "1" * 64]))
        rows.append(("file", file, [asset, "main", f"media/{index}.png", "1" * 64, 1]))
    return tuple(rows)


def authority_inputs():
    pages = []
    for index in range(EXACT_PAGES):
        page_id = str(uuid.UUID(int=index + 1))
        kind = (
            "home" if index == 0 else
            "service_detail" if index == 1 else
            "gallery_catalog" if index == 2 else
            "article"
        )
        current = {
            "schema_version": "page-content-v1",
            "page_kind": kind,
            "value": index,
        }
        previous = (
            {"schema_version": "page-content-v1", "page_kind": kind, "value": -1}
            if index == 0 else None
        )
        target = {
            "schema": "estakada.page-content", "schema_version": 1,
            "kind": kind, "fields": {"value": index},
        }
        target_previous = (
            {**target, "fields": {"value": -1}} if previous is not None else None
        )
        pages.append({
            "id": page_id,
            "name": f"Page {index}",
            "kind": kind,
            "parent_id": None,
            "position": index,
            "generation": 2 if index == 0 else 1,
            "source_current_payload": current,
            "source_previous_payload": previous,
            "current_payload": target,
            "previous_payload": target_previous,
            "target": "/" if index == 0 else f"/page-{index}",
        })
    routes = [{
        "page_id": row["id"],
        "target": row["target"],
        "source_kind": "primary",
        "source_is_legacy": True,
        "mode": "PRIMARY",
        "outcome": row["kind"],
    } for row in pages]
    routes.extend((
        {
            "page_id": pages[1]["id"],
            "target": "/services/drugie-uslugi/avtomojka",
            "source_kind": "alias",
            "source_is_legacy": True,
            "mode": "ALIAS",
            "outcome": "service_wash_legacy_alias",
        },
        {
            "page_id": pages[2]["id"],
            "target": "/gallery-of-works/?page=2",
            "source_kind": "alias",
            "source_is_legacy": True,
            "mode": "ALIAS",
            "outcome": "gallery_catalog",
        },
    ))
    return tuple(pages), tuple(routes)


def payload_hash(value):
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def authority_capture(inputs):
    pages, routes = inputs
    page_rows = []
    for row in pages:
        current = row["source_current_payload"]
        previous = row["source_previous_payload"]
        page_rows.append((
            row["id"], row["name"], row["kind"], row["parent_id"],
            row["position"], True, row["generation"], row["generation"],
            current["schema_version"], current, payload_hash(current),
            "2026-11-18T00:00:00.000000Z", False, previous,
            None if previous is None else payload_hash(previous),
            None if previous is None else "2026-11-17T00:00:00.000000Z",
            None if previous is None else previous["schema_version"],
        ))
    route_rows = [(
        str(uuid.UUID(int=20_000 + index)), row["page_id"], row["target"],
        row["source_kind"], row["source_is_legacy"],
    ) for index, row in enumerate(routes)]
    return FreezeCapture(tuple(page_rows), tuple(route_rows), (), ())


class Executor:
    def __init__(self):
        self.rows = {
            PUBLIC_PAGES_SQL: guarded(21, (page(index) for index in range(EXACT_PAGES))),
            PUBLIC_ROUTES_SQL: guarded(9, (route(index) for index in range(EXACT_ROUTES))),
            PUBLIC_SHARED_SQL: guarded(16, ()),
            PUBLIC_MEDIA_SQL: guarded(7, media_rows()),
        }
        self.calls = []

    def fetch_all(self, sql):
        self.calls.append(sql)
        return self.rows[sql]


class FreezeAuthorityCaptureTests(TestCase):
    def test_exact_four_guarded_public_queries_and_digest(self):
        executor = Executor()
        capture = capture_source_authority(executor, SESSION)
        self.assertEqual(
            executor.calls,
            [PUBLIC_PAGES_SQL, PUBLIC_ROUTES_SQL, PUBLIC_SHARED_SQL, PUBLIC_MEDIA_SQL],
        )
        self.assertEqual(
            (len(capture.pages), len(capture.routes)),
            (EXACT_PAGES, EXACT_ROUTES),
        )
        self.assertEqual(len(capture.media), EXACT_SOURCE_MEDIA * 2)
        self.assertEqual((EXACT_PAGES, EXACT_ROUTES, EXACT_ROUTES + 1), (112, 114, 115))
        digest = freeze_capture_digest(capture)
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual(digest, freeze_capture_digest(capture))

    def test_wrong_public_count_and_session_drift_fail_closed(self):
        executor = Executor()
        executor.rows[PUBLIC_PAGES_SQL] = guarded(
            21, (page(index) for index in range(EXACT_PAGES - 1)),
        )
        with self.assertRaisesRegex(FreezeError, "capture-public-count"):
            capture_source_authority(executor, SESSION)

        executor = Executor()
        rows = list(executor.rows[PUBLIC_ROUTES_SQL])
        rows[1] = (rows[1][0], rows[1][1], rows[1][2], "11:20:", *rows[1][4:])
        executor.rows[PUBLIC_ROUTES_SQL] = tuple(rows)
        with self.assertRaisesRegex(FreezeError, "source-public-session-drift"):
            capture_source_authority(executor, SESSION)

    def test_duplicate_and_missing_media_facts_fail_closed(self):
        executor = Executor()
        rows = list(executor.rows[PUBLIC_MEDIA_SQL])
        rows.append(rows[1])
        executor.rows[PUBLIC_MEDIA_SQL] = tuple(rows)
        with self.assertRaisesRegex(FreezeError, "capture-media-shape"):
            capture_source_authority(executor, SESSION)

        executor = Executor()
        executor.rows[PUBLIC_MEDIA_SQL] = executor.rows[PUBLIC_MEDIA_SQL][:-1]
        with self.assertRaisesRegex(FreezeError, "capture-media-count"):
            capture_source_authority(executor, SESSION)

    def test_duplicate_page_route_and_target_identities_fail_closed(self):
        for sql in (PUBLIC_PAGES_SQL, PUBLIC_ROUTES_SQL):
            with self.subTest(sql=sql):
                executor = Executor()
                rows = list(executor.rows[sql])
                rows[-1] = rows[1]
                executor.rows[sql] = tuple(rows)
                with self.assertRaisesRegex(FreezeError, "capture-public-identity"):
                    capture_source_authority(executor, SESSION)

        executor = Executor()
        rows = list(executor.rows[PUBLIC_ROUTES_SQL])
        rows[-1] = (*rows[-1][:6], rows[1][6], *rows[-1][7:])
        executor.rows[PUBLIC_ROUTES_SQL] = tuple(rows)
        with self.assertRaisesRegex(FreezeError, "capture-public-identity"):
            capture_source_authority(executor, SESSION)

    def test_malformed_media_fact_and_usage_classification_fail_closed(self):
        executor = Executor()
        rows = list(executor.rows[PUBLIC_MEDIA_SQL])
        rows[1] = (*rows[1][:-1], [])
        executor.rows[PUBLIC_MEDIA_SQL] = tuple(rows)
        with self.assertRaisesRegex(FreezeError, "capture-media-shape"):
            capture_source_authority(executor, SESSION)

        executor = Executor()
        rows = list(executor.rows[PUBLIC_MEDIA_SQL])
        usage = (
            1, SESSION.backend_pid, SESSION.transaction_id, SESSION.snapshot_id,
            "usage", str(uuid.UUID(int=40_000)),
            [str(uuid.UUID(int=20_000)), "current_page", str(uuid.UUID(int=1)),
             "hero", "unclassified", "PAGE_CURRENT", str(uuid.UUID(int=1))],
        )
        rows.append(usage)
        executor.rows[PUBLIC_MEDIA_SQL] = tuple(rows)
        with self.assertRaisesRegex(FreezeError, "capture-media-shape"):
            capture_source_authority(executor, SESSION)

    def test_invalid_input_and_non_capture_digest_are_rejected(self):
        with self.assertRaisesRegex(FreezeError, "freeze-capture-input"):
            capture_source_authority(Executor(), replace(SESSION, snapshot_id="bad"))
        with self.assertRaisesRegex(FreezeError, "freeze-capture"):
            freeze_capture_digest(object())

    def test_capture_repr_does_not_expose_rows(self):
        value = repr(FreezeCapture((), (), (), ()))
        self.assertNotIn("pages=", value)
        self.assertNotIn("routes=", value)

    def test_capture_deep_freezes_source_json_before_digest(self):
        executor = Executor()
        payload = executor.rows[PUBLIC_PAGES_SQL][1][13]
        payload["nested"] = {"values": [1, 2]}
        capture = capture_source_authority(executor, SESSION)
        before = freeze_capture_digest(capture)
        payload["nested"]["values"].append(3)
        self.assertEqual(freeze_capture_digest(capture), before)
        frozen_payload = capture.pages[0][9]
        with self.assertRaises((AttributeError, TypeError)):
            frozen_payload["nested"] = "changed"


class PageRouteAuthorityTests(TestCase):
    def test_literal_reader_composes_exact_closed_package_set(self):
        pages, routes = _literal_page_route_inputs()
        self.assertEqual((len(pages), len(routes)), (112, 114))
        self.assertEqual(len({row["id"] for row in pages}), 112)
        self.assertEqual(len({row["target"] for row in routes}), 114)
        self.assertNotIn(
            "/gallery-of-works/?page=1", {row["target"] for row in routes},
        )
        home = next(row for row in pages if row["target"] == "/")
        self.assertEqual(home["generation"], 2)
        self.assertIsNotNone(home["previous_payload"])
        self.assertTrue(all(
            row["current_payload"]["schema"] == "estakada.page-content"
            and row["current_payload"]["schema_version"] == 1
            for row in pages
        ))
        wash = next(row for row in pages if row["kind"] == "service_wash_legacy_alias")
        self.assertEqual(wash["current_payload"]["kind"], "service_detail")
        self.assertIsNone(wash["current_payload"]["fields"]["media"]["hero"])
        service_rows = {row["page_id"]: row for row in service_media_rows()}
        service_pages = [row for row in pages if row["id"] in service_rows]
        self.assertEqual(len(service_pages), 58)
        for page in service_pages:
            self.assertEqual(
                page["current_payload"]["fields"]["media"]["hero"],
                service_rows[page["id"]]["asset_id"],
            )
            if page["previous_payload"] is not None:
                self.assertNotEqual(
                    page["previous_payload"]["fields"]["media"].get("hero"),
                    service_rows[page["id"]]["asset_id"],
                )
        map019 = next(row for row in service_pages if row["id"] == "080d64ee-4ce1-5399-b672-83dc22f9f8bf")
        self.assertEqual(
            map019["current_payload"]["fields"]["media"]["body"],
            ["6fa5cdd8-dabd-52ab-b994-4e10ef2cb2c8"],
        )

        for target, name in (
            ("/nash-servisnyij-czentr", "Наш сервисный центр"),
            ("/about", "О компании"),
        ):
            with self.subTest(target=target):
                empty = next(row for row in pages if row["target"] == target)
                self.assertEqual(empty["source_current_payload"]["h1"], "")
                self.assertEqual(
                    empty["current_payload"]["fields"]["heading"]["h1"], name,
                )

        home = next(row for row in pages if row["kind"] == "home")
        home_fields = home["current_payload"]["fields"]
        self.assertTrue(home_fields["lead"])
        self.assertEqual(len(home_fields["process_steps"]), 5)
        self.assertEqual(len(home_fields["media"]["service_cards"]), 8)
        self.assertEqual(len(home_fields["media"]["process"]), 5)
        self.assertEqual(len(home_fields["media"]["works"]), 7)
        self.assertEqual(
            home_fields["media"]["works"][0],
            "93518ab5-fc53-50ab-a6b3-302b0813a4ac",
        )
        embedded_assets = {
            row["asset_id"] for row in home["source_current_payload"]["embedded_images"]
        }
        projected_assets = {
            home_fields["media"]["hero"],
            *home_fields["media"]["service_cards"],
            *home_fields["media"]["process"],
            *home_fields["media"]["works"],
        }
        self.assertEqual(projected_assets, embedded_assets)
        profile = home_fields["home_profile"]
        self.assertEqual(
            (
                profile["schema"],
                profile["schema_version"],
                len(profile["advantages"]),
                len(profile["comparisons"]),
                len(profile["steps"]),
                len(profile["services"]),
                len(profile["prices"]),
                len(profile["works"]),
            ),
            ("estakada.home-profile", 1, 8, 3, 5, 8, 6, 6),
        )
        self.assertEqual(
            [row["asset_id"] for row in profile["services"]],
            home_fields["media"]["service_cards"],
        )
        self.assertEqual(
            [row["asset_id"] for row in profile["steps"]],
            home_fields["media"]["process"],
        )
        self.assertEqual(
            [profile["photo_strip"]["asset_id"], *[
                row["asset_id"] for row in profile["works"]
            ]],
            home_fields["media"]["works"],
        )
        for mutate in (
            lambda value: value["services"].pop(),
            lambda value: value["services"][0].__setitem__("url", "https://example.test/"),
            lambda value: value["hero"].__setitem__("asset_id", str(uuid.uuid4())),
            lambda value: value["reviews"].__setitem__("url", "/other"),
        ):
            invalid = json.loads(json.dumps(home["current_payload"]))
            mutate(invalid["fields"]["home_profile"])
            with self.subTest(mutate=mutate), self.assertRaises(ManifestError):
                validate_payload(invalid, "home")
        previous_fields = home["previous_payload"]["fields"]
        self.assertEqual((previous_fields["lead"], previous_fields["about"]), ("", ""))
        self.assertNotIn("home_profile", previous_fields)
        self.assertTrue(all(
            value is None or value == []
            for value in previous_fields["media"].values()
        ))

        actions = next(row for row in pages if row["kind"] == "actions")
        action_fields = actions["current_payload"]["fields"]
        image_assets = {
            row["id"]: row["asset_id"]
            for row in actions["source_current_payload"]["embedded_images"]
        }
        self.assertEqual(len(action_fields["actions"]), 2)
        self.assertEqual(
            action_fields["media"]["banner"], list(image_assets.values()),
        )
        reviews = next(row for row in pages if row["kind"] == "reviews")
        self.assertEqual(len(reviews["current_payload"]["fields"]["reviews"]), 10)

        from content.dev09_migration_apply import _read_remaining_content_package
        remaining = _read_remaining_content_package()
        partner_source = next(
            row["profile"] for row in remaining["pages"]
            if row["kind"] == "legacy_partner_links"
        )
        partners = next(row for row in pages if row["kind"] == "legacy_partner_links")
        partner_target = partners["current_payload"]["fields"]["links"]
        self.assertEqual(len(partner_target), 6)
        self.assertEqual(
            [row["label"] for row in partner_target],
            [row["text"] for row in partner_source["items"]],
        )
        self.assertEqual(
            [row["https_url"] for row in partner_target],
            ["https://" + row["url"][7:] for row in partner_source["items"]],
        )

    def test_composes_captured_ids_and_two_literal_alias_outcomes(self):
        inputs = authority_inputs()
        capture = authority_capture(inputs)
        with patch(
            "rebuild3_importer.freeze_authority._literal_page_route_inputs",
            return_value=inputs,
        ):
            pages, routes = compose_page_route_authority(capture)
        self.assertEqual((len(pages), len(routes)), (112, 114))
        self.assertEqual(pages[0].content_generation, 2)
        self.assertIsNotNone(pages[0].previous_payload)
        self.assertEqual(pages[0].current_payload["schema"], "estakada.page-content")
        aliases = {row.target: row for row in routes if row.mode == "ALIAS"}
        self.assertEqual(
            aliases["/services/drugie-uslugi/avtomojka"].outcome,
            "service_wash_legacy_alias",
        )
        self.assertEqual(
            aliases["/gallery-of-works/?page=2"].outcome,
            "gallery_catalog",
        )

    def test_payload_drift_and_derived_page_one_route_fail_closed(self):
        inputs = authority_inputs()
        capture = authority_capture(inputs)
        rows = list(capture.pages)
        rows[0] = (*rows[0][:9], {**rows[0][9], "value": 99}, *rows[0][10:])
        with patch(
            "rebuild3_importer.freeze_authority._literal_page_route_inputs",
            return_value=inputs,
        ):
            with self.assertRaisesRegex(FreezeError, "authority-page-drift"):
                compose_page_route_authority(replace(capture, pages=tuple(rows)))

        pages, routes = inputs
        changed = list(routes)
        changed[-1] = {
            **changed[-1], "target": "/gallery-of-works/?page=1",
        }
        with patch(
            "rebuild3_importer.freeze_authority._literal_page_route_inputs",
            return_value=(pages, tuple(changed)),
        ):
            with self.assertRaisesRegex(FreezeError, "authority-literal-count"):
                compose_page_route_authority(capture)

    def test_route_identity_or_source_binding_drift_fails_closed(self):
        inputs = authority_inputs()
        capture = authority_capture(inputs)
        rows = list(capture.routes)
        rows[0] = (*rows[0][:1], str(uuid.UUID(int=999_999)), *rows[0][2:])
        with patch(
            "rebuild3_importer.freeze_authority._literal_page_route_inputs",
            return_value=inputs,
        ):
            with self.assertRaisesRegex(FreezeError, "authority-route-drift"):
                compose_page_route_authority(replace(capture, routes=tuple(rows)))
