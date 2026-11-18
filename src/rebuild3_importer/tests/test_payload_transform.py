import unittest

from rebuild3_importer.content import validate_payload
from rebuild3_importer.errors import ManifestError
from rebuild3_importer.payload_transform import (
    _media,
    target_page_kind,
    transform_legacy_payload,
)


def legacy(kind):
    return {
        "schema_version": "page-content-v1", "page_kind": kind,
        "intro_text": "<p>Intro</p>", "main_text": "<p>Body</p>",
        "price": None, "h1": "Heading", "title": "Title",
        "description": "", "indexing_allowed": True,
        "main_image": None, "preview_image": None,
        "embedded_images": [], "layout": [],
    }


class PayloadTransformTests(unittest.TestCase):
    def test_simple_kinds_produce_only_target_envelope(self):
        kinds = (
            "services_master_catalog", "service_catalog",
            "service_section_overview", "service_detail", "articles_catalog",
            "article", "contacts", "gallery_catalog", "gallery_album",
            "legacy_director_message", "legacy_news_article",
            "legacy_empty_main", "legacy_news_catalog",
            "legacy_under_construction", "legacy_camera_schedule_text",
            "service_wash_legacy_alias",
        )
        for kind in kinds:
            with self.subTest(kind=kind):
                result = transform_legacy_payload(
                    legacy(kind), source_kind=kind, page_url="/page/",
                )
                target_kind = target_page_kind(kind)
                self.assertEqual(
                    set(result), {"schema", "schema_version", "kind", "fields"},
                )
                self.assertEqual(result["kind"], target_kind)
                validate_payload(result, target_kind)

    def test_empty_legacy_main_uses_only_exact_page_name_for_target_h1(self):
        value = legacy("legacy_empty_main")
        value["h1"] = ""
        result = transform_legacy_payload(
            value,
            source_kind="legacy_empty_main",
            page_url="/empty",
            page_name="Approved page name",
        )
        self.assertEqual(result["fields"]["heading"]["h1"], "Approved page name")
        self.assertEqual(value["h1"], "")

        for page_name in (None, "", " padded ", "x" * 256, 1):
            with self.subTest(page_name=page_name), self.assertRaisesRegex(
                ManifestError, "payload-h1",
            ):
                transform_legacy_payload(
                    value,
                    source_kind="legacy_empty_main",
                    page_url="/empty",
                    page_name=page_name,
                )

        nonempty = legacy("legacy_empty_main")
        preserved = transform_legacy_payload(
            nonempty,
            source_kind="legacy_empty_main",
            page_url="/nonempty",
            page_name="",
        )
        self.assertEqual(preserved["fields"]["heading"]["h1"], "Heading")

    def test_actions_reviews_and_partner_profiles_are_literal(self):
        cases = (
            ("reviews", {"videos": [{
                "title": "Review", "url": "https://example.test/review",
            }]}),
            ("legacy_partner_links", {"items": [{
                "text": "Partner", "url": "http://example.test/path",
                "label": "example.test",
            }]}),
        )
        for kind, profile in cases:
            with self.subTest(kind=kind):
                result = transform_legacy_payload(
                    legacy(kind), source_kind=kind, page_url="/page/",
                    profile=profile,
                )
                validate_payload(result, kind)
        self.assertEqual(
            transform_legacy_payload(
                legacy("legacy_partner_links"),
                source_kind="legacy_partner_links", page_url="/partners",
                profile=cases[-1][1],
            )["fields"]["links"][0]["https_url"],
            "https://example.test/path",
        )

    def test_wrong_source_envelope_and_missing_profile_fail_closed(self):
        value = legacy("actions")
        value["schema_version"] = "wrong"
        with self.assertRaisesRegex(ManifestError, "legacy-payload-envelope"):
            transform_legacy_payload(value, source_kind="actions", page_url="/actions")
        with self.assertRaisesRegex(ManifestError, "legacy-profile-missing"):
            transform_legacy_payload(
                legacy("reviews"), source_kind="reviews", page_url="/reviews",
            )

    def test_previous_home_must_be_semantically_empty(self):
        previous = legacy("home")
        previous["intro_text"] = ""
        previous["main_text"] = ""
        result = transform_legacy_payload(
            previous, source_kind="home", page_url="/",
        )
        self.assertEqual((result["fields"]["lead"], result["fields"]["about"]), ("", ""))
        self.assertTrue(all(
            value is None or value == []
            for value in result["fields"]["media"].values()
        ))
        mutations = {
            "intro_text": "<p>unexpected</p>",
            "main_text": "<p>unexpected</p>",
            "price": {"columns": [], "rows": []},
            "embedded_images": [{
                "id": "00000000-0000-4000-8000-000000000001",
                "asset_id": "00000000-0000-4000-8000-000000000002",
            }],
        }
        for field, unexpected in mutations.items():
            with self.subTest(field=field):
                value = legacy("home")
                value["intro_text"] = ""
                value["main_text"] = ""
                value[field] = unexpected
                with self.assertRaisesRegex(ManifestError, "legacy-home-previous"):
                    transform_legacy_payload(
                        value, source_kind="home", page_url="/",
                    )

    def test_home_media_preserves_photo_strip_first_and_covers_every_asset(self):
        image_ids = {
            name: f"00000000-0000-4000-8000-{index:012d}"
            for index, name in enumerate(
                ("hero", "service", "step", "photo", "work", "extra"), 1,
            )
        }
        asset_ids = {
            name: f"00000000-0000-4000-8001-{index:012d}"
            for index, name in enumerate(image_ids, 1)
        }
        value = legacy("home")
        value["embedded_images"] = [
            {"id": image_ids[name], "asset_id": asset_ids[name]}
            for name in ("hero", "service", "step", "photo", "work")
        ]
        profile = {
            "hero": {"image_id": image_ids["hero"]},
            "services": [{"image_id": image_ids["service"]}],
            "steps": [{"image_id": image_ids["step"]}],
            "photo_strip": {"image_id": image_ids["photo"]},
            "works": [{
                "image_id": image_ids["work"], "asset_id": asset_ids["work"],
            }],
        }
        media = _media(value, "home", profile)
        self.assertEqual(
            media["works"], [asset_ids["photo"], asset_ids["work"]],
        )
        self.assertEqual(
            {
                media["hero"], *media["service_cards"], *media["process"],
                *media["works"],
            },
            {row["asset_id"] for row in value["embedded_images"]},
        )

        missing = {**profile, "photo_strip": {"image_id": image_ids["extra"]}}
        with self.assertRaisesRegex(ManifestError, "legacy-home-media"):
            _media(value, "home", missing)

        wrong = {**profile, "photo_strip": {"image_id": image_ids["hero"]}}
        with self.assertRaisesRegex(ManifestError, "legacy-home-media"):
            _media(value, "home", wrong)

        value["embedded_images"].append({
            "id": image_ids["extra"], "asset_id": asset_ids["extra"],
        })
        with self.assertRaisesRegex(ManifestError, "legacy-home-media"):
            _media(value, "home", profile)

    def test_action_profile_controls_banner_order_and_coverage(self):
        first_image = "00000000-0000-4000-8000-000000000011"
        second_image = "00000000-0000-4000-8000-000000000012"
        first_asset = "00000000-0000-4000-8000-000000000021"
        second_asset = "00000000-0000-4000-8000-000000000022"
        value = legacy("actions")
        value["embedded_images"] = [
            {"id": first_image, "asset_id": first_asset},
            {"id": second_image, "asset_id": second_asset},
        ]
        profile = {"cards": [
            {"heading": "Second", "text": "B", "image_id": second_image},
            {"heading": "First", "text": "A", "image_id": first_image},
        ]}
        result = transform_legacy_payload(
            value, source_kind="actions", page_url="/actions", profile=profile,
        )
        self.assertEqual(
            result["fields"]["media"]["banner"], [second_asset, first_asset],
        )
        profile["cards"][0]["image_id"] = (
            "00000000-0000-4000-8000-000000000099"
        )
        with self.assertRaisesRegex(ManifestError, "legacy-action-media"):
            transform_legacy_payload(
                value, source_kind="actions", page_url="/actions", profile=profile,
            )


if __name__ == "__main__":
    unittest.main()
