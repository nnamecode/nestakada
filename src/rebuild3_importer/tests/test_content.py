import copy
import unittest

from rebuild3_importer.content import FIELD_SETS, MEDIA_SLOTS, RICH_BY_KIND, validate_payload
from rebuild3_importer.errors import ManifestError


KINDS = {
    "home", "services_master_catalog", "service_catalog", "service_section_overview",
    "service_detail", "articles_catalog", "article", "contacts", "reviews", "actions",
    "gallery_catalog", "gallery_album", "legacy_partner_links", "legacy_director_message",
    "legacy_news_article", "legacy_empty_main", "legacy_news_catalog",
    "legacy_under_construction", "legacy_camera_schedule_text",
}


def payload(kind):
    fields = {"seo": {"title": "Title", "description": "", "allow_index": True},
              "heading": {"h1": "Heading"}}
    for name in RICH_BY_KIND.get(kind, set()): fields[name] = "<p>Text<br></p>"
    for name in ("service_refs", "brand_refs", "review_refs", "process_steps", "actions", "reviews", "links"):
        if name in FIELD_SETS[kind]: fields[name] = []
    if "price_rows" in FIELD_SETS[kind]: fields["price_rows"] = {"columns": [], "rows": []}
    if "media" in FIELD_SETS[kind]:
        fields["media"] = {slot: (None if slot == "hero" else []) for slot in MEDIA_SLOTS[kind]}
    return {"schema": "estakada.page-content", "schema_version": 1, "kind": kind, "fields": fields}


class ContentContractTests(unittest.TestCase):
    def test_exact_nineteen_kinds_accept_minimal_canonical_payload(self):
        self.assertEqual(set(FIELD_SETS), KINDS)
        for kind in sorted(KINDS):
            with self.subTest(kind=kind): self.assertIsInstance(validate_payload(payload(kind), kind), dict)

    def test_unknown_field_kind_and_noncanonical_rich_are_rejected(self):
        cases = []
        value = payload("home"); value["fields"]["unknown"] = True; cases.append(value)
        value = payload("home"); value["schema"] = "wrong"; cases.append(value)
        value = payload("home"); value["schema_version"] = True; cases.append(value)
        value = payload("home"); value["schema_version"] = 1.0; cases.append(value)
        value = payload("home"); value["kind"] = "article"; cases.append(value)
        value = payload("home"); value["fields"]["lead"] = "<script>x</script>"; cases.append(value)
        value = payload("home"); value["fields"]["lead"] = "<b>x</b>"; cases.append(value)
        for value in cases:
            with self.assertRaises(ManifestError): validate_payload(value, "home")

    def test_price_v1_rejects_float_unknown_column_and_duplicate_ids(self):
        base = payload("service_detail")
        column = "00000000-0000-4000-8000-000000000001"
        row = "00000000-0000-4000-8000-000000000002"
        valid = {"columns": [{"id": column, "label": "Price"}], "rows": [
            {"id": row, "label": "Work", "cells": [
                {"column_id": column, "kind": "amount", "amount": "10.50", "from": False}
            ]}
        ]}
        base["fields"]["price_rows"] = valid
        validate_payload(base, "service_detail")
        for mutate in (
            lambda value: value["rows"][0]["cells"][0].__setitem__("amount", 10.5),
            lambda value: value["rows"][0]["cells"][0].__setitem__("column_id", row),
            lambda value: value["columns"].append(copy.deepcopy(value["columns"][0])),
        ):
            candidate = copy.deepcopy(valid); mutate(candidate)
            invalid = payload("service_detail"); invalid["fields"]["price_rows"] = candidate
            with self.assertRaises(ManifestError): validate_payload(invalid, "service_detail")

    def test_media_refs_are_unique_bounded_and_returned_by_slot(self):
        value = payload("home")
        asset = "00000000-0000-4000-8000-000000000003"
        value["fields"]["media"]["hero"] = asset
        self.assertEqual(validate_payload(value, "home")["hero"], [asset])
        value["fields"]["media"]["works"] = [asset, asset]
        with self.assertRaises(ManifestError): validate_payload(value, "home")

    def test_typed_array_caps_are_closed(self):
        cases = (
            ("home", "process_steps", {"title": "T", "body": "B"}, 13),
            ("actions", "actions", {"title": "T", "body": "<p>B</p>", "internal_url": "/x/"}, 33),
            ("reviews", "reviews", {"title": "T", "https_url": "https://example.test/x", "caption": "C"}, 33),
            ("legacy_partner_links", "links", {"label": "L", "https_url": "https://example.test/x"}, 65),
        )
        for kind, field, item, count in cases:
            value = payload(kind); value["fields"][field] = [copy.deepcopy(item) for _ in range(count)]
            with self.subTest(kind=kind), self.assertRaises(ManifestError): validate_payload(value, kind)

    def test_visible_text_and_dom_nodes_are_payload_aggregate_caps(self):
        value = payload("home"); value["fields"]["lead"] = "<p>" + ("x" * 200_001) + "</p>"
        with self.assertRaises(ManifestError): validate_payload(value, "home")
        value = payload("home"); fragment = "<p>x</p>" * 3_500
        for field in ("lead", "about", "contact_text"): value["fields"][field] = fragment
        with self.assertRaises(ManifestError): validate_payload(value, "home")
        value = payload("home"); value["fields"]["lead"] = "<p>x</p>" * 10_001
        with self.assertRaises(ManifestError): validate_payload(value, "home")

    def test_rich_attributes_and_https_boundary_are_closed(self):
        for rich in (
            '<p class="x">x</p>',
            '<p><a href="https://example.test:99999/x">x</a></p>',
            '<p><a href="https://example.test/%0Ax">x</a></p>',
            '<table><tr><td rowspan="101">x</td></tr></table>',
        ):
            value = payload("home"); value["fields"]["lead"] = rich
            with self.subTest(rich=rich), self.assertRaises(ManifestError): validate_payload(value, "home")
