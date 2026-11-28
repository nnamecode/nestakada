from __future__ import annotations

import copy
import io
import os
from pathlib import Path
import unittest
import uuid

import rebuild7_service_page_mapping_diagnostic as diagnostic


class ServicePageMappingDiagnosticTests(unittest.TestCase):
    def rows(self) -> list[dict[str, object]]:
        return [
            {
                "target": target,
                "page_id": str(uuid.uuid5(uuid.NAMESPACE_URL, map_id)),
                "page_kind": (
                    "service_section_overview"
                    if map_id in {"MAP-010", "MAP-011", "MAP-013"}
                    else "service_detail"
                ),
                "mode": "PRIMARY",
                "outcome": (
                    "service_section_overview"
                    if map_id in {"MAP-010", "MAP-011", "MAP-013"}
                    else "service_detail"
                ),
                "is_published": True,
            }
            for map_id, target in diagnostic.SERVICE_ROUTES
        ]

    def test_exact58_result_is_stable_and_closed(self) -> None:
        result = diagnostic.build_result(self.rows())
        self.assertEqual(set(result), {"schema", "mappings"})
        self.assertEqual(result["schema"], diagnostic.SCHEMA)
        self.assertEqual(len(result["mappings"]), 58)
        self.assertEqual(
            [row["map"] for row in result["mappings"]],
            [map_id for map_id, _target in diagnostic.SERVICE_ROUTES],
        )

    def test_missing_duplicate_and_unknown_routes_fail_closed(self) -> None:
        cases = []
        rows = self.rows()
        cases.append(rows[:-1])
        duplicate = copy.deepcopy(rows)
        duplicate[-1]["target"] = duplicate[0]["target"]
        cases.append(duplicate)
        unknown = copy.deepcopy(rows)
        unknown[-1]["target"] = "/services/not-approved"
        cases.append(unknown)
        for value in cases:
            with self.subTest():
                with self.assertRaisesRegex(RuntimeError, "R7_SERVICE_PAGE_MAPPING_DIAGNOSTIC_UNAVAILABLE"):
                    diagnostic.build_result(value)

    def test_identity_kind_mode_publication_and_shape_fail_closed(self) -> None:
        mutations = (
            ("page_id", "NOT-A-UUID"),
            ("page_kind", "article"),
            ("mode", "ALIAS"),
            ("outcome", "article"),
            ("is_published", False),
        )
        for key, value in mutations:
            rows = self.rows()
            rows[0][key] = value
            with self.subTest(key=key):
                with self.assertRaisesRegex(RuntimeError, "R7_SERVICE_PAGE_MAPPING_DIAGNOSTIC_UNAVAILABLE"):
                    diagnostic.build_result(rows)
        rows = self.rows()
        rows[0]["extra"] = "forbidden"
        with self.assertRaisesRegex(RuntimeError, "R7_SERVICE_PAGE_MAPPING_DIAGNOSTIC_UNAVAILABLE"):
            diagnostic.build_result(rows)

    def test_query_boundary_is_serializable_read_only_and_fixed(self) -> None:
        source = open(diagnostic.__file__, encoding="utf-8").read()
        for token in (
            "SERIALIZABLE, READ ONLY, DEFERRABLE",
            '"target", "page_id", "page__kind", "mode", "outcome",',
            '"page__is_published",',
            '.order_by("target")',
            '"map": map_id, "page_id":',
        ):
            self.assertIn(token, source)
        for banned in (
            "select_related", "PageContent", "current_payload", "Asset", "media"
        ):
            self.assertNotIn(banned, source)

    def test_harness_is_bounded_read_only_and_restores_stopped_database(self) -> None:
        harness = Path(os.environ["R7_OWNER_PAYLOAD_DIAGNOSTIC_HARNESS"]).read_text(
            encoding="utf-8"
        )
        for token in (
            "[switch]$ServicePageMapping",
            "Invoke-DockerBounded",
            "Wait-DatabaseReady",
            "Assert-SourceClientsZero",
            "Assert-OriginalBitmap",
            "coordinator.lock",
            "New-DiagnosticContainer 'read'",
            "Assert-OwnedDiagnosticContainer",
            "R7_SERVICE_PAGE_MAPPING_DIAGNOSTIC_OK",
            "R7_SERVICE_PAGE_MAPPING_DIAGNOSTIC_CLEANUP_PASS",
        ):
            self.assertIn(token, harness)
        for banned in ("docker cp", "migrate", "18085", "mediaSource"):
            self.assertNotIn(banned, harness)


if __name__ == "__main__":
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        ServicePageMappingDiagnosticTests
    )
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    if not result.wasSuccessful() or result.testsRun != 5:
        raise RuntimeError("R7_SERVICE_PAGE_MAPPING_DIAGNOSTIC_TESTS_UNAVAILABLE")
    print("R7_SERVICE_PAGE_MAPPING_DIAGNOSTIC_TESTS_OK cases=5")
