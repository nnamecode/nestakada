from __future__ import annotations

import io
import os
import unittest
from pathlib import Path

import rebuild7_owner_payload_diagnostic as diagnostic
from rebuild3_importer.service_media import (
    INFOGRAPHIC_ASSET_ID,
    MAP019_PAGE_ID,
    service_media_rows,
)


def payload(hero=None, body=None) -> dict[str, object]:
    return {"fields": {"media": {"hero": hero, "body": [] if body is None else body}}}


class OwnerPayloadDiagnosticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = service_media_rows()
        self.by_page = {str(row["page_id"]): row for row in self.rows}

    def clean_payloads(self) -> dict[str, object]:
        return {
            page_id: payload(
                INFOGRAPHIC_ASSET_ID if page_id == MAP019_PAGE_ID else None
            )
            for page_id in self.by_page
        }

    def test_clean_authority_has_no_classification(self) -> None:
        values = self.clean_payloads()
        for page_id, row in self.by_page.items():
            with self.subTest(map=row["map_id"]):
                self.assertIsNone(
                    diagnostic.classify_payload(
                        row, values[page_id], INFOGRAPHIC_ASSET_ID, MAP019_PAGE_ID
                    )
                )

    def test_closed_ordinary_hero_categories(self) -> None:
        row = next(row for row in self.rows if str(row["page_id"]) != MAP019_PAGE_ID)
        self.assertEqual(
            diagnostic.classify_payload(
                row, payload(str(row["asset_id"])), INFOGRAPHIC_ASSET_ID, MAP019_PAGE_ID
            ),
            "HERO_TARGET",
        )
        self.assertEqual(
            diagnostic.classify_payload(
                row, payload("00000000-0000-4000-8000-000000000001"), INFOGRAPHIC_ASSET_ID, MAP019_PAGE_ID
            ),
            "HERO_OTHER",
        )

    def test_closed_map019_categories(self) -> None:
        row = self.by_page[MAP019_PAGE_ID]
        cases = (
            (payload(None), "MAP019_HERO_NULL"),
            (payload(str(row["asset_id"])), "MAP019_HERO_TARGET"),
            (payload("00000000-0000-4000-8000-000000000001"), "MAP019_HERO_OTHER"),
            (payload(INFOGRAPHIC_ASSET_ID, [INFOGRAPHIC_ASSET_ID]), "MAP019_BODY_NONEMPTY"),
        )
        for value, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    diagnostic.classify_payload(
                        row, value, INFOGRAPHIC_ASSET_ID, MAP019_PAGE_ID
                    ),
                    expected,
                )

    def test_payload_shape_is_closed(self) -> None:
        row = self.rows[0]
        for value in (None, {}, {"fields": None}, {"fields": {"media": {}}}):
            with self.subTest(value=value):
                self.assertEqual(
                    diagnostic.classify_payload(
                        row, value, INFOGRAPHIC_ASSET_ID, MAP019_PAGE_ID
                    ),
                    "PAYLOAD_SHAPE",
                )

    def test_result_contains_only_map_and_category(self) -> None:
        values = self.clean_payloads()
        row = next(row for row in self.rows if str(row["page_id"]) != MAP019_PAGE_ID)
        values[str(row["page_id"])] = payload("00000000-0000-4000-8000-000000000001")
        result = diagnostic.build_result(
            self.rows, values, INFOGRAPHIC_ASSET_ID, MAP019_PAGE_ID
        )
        self.assertEqual(set(result), {"schema", "mismatches"})
        self.assertEqual(
            result["mismatches"],
            [{"map": row["map_id"], "category": "HERO_OTHER"}],
        )

    def test_harness_retains_read_only_boundary(self) -> None:
        source = Path(diagnostic.__file__).read_text(encoding="utf-8")
        harness = Path(os.environ["R7_OWNER_PAYLOAD_DIAGNOSTIC_HARNESS"]).read_text(
            encoding="utf-8"
        )
        for token in (
            "$dbNetwork",
            "'none'",
            "--read-only",
            "--cap-drop', 'ALL'",
            "no-new-privileges:true",
            "Assert-SourceClientsZero",
            "Assert-OwnedDiagnosticContainer",
            "$allowedCodes",
            "Normalize-DiagnosticCode",
            "ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password",
            "$actualNetworks",
            "$expectedNetworkName = if ($Role -ceq 'tests') { 'none' } else { $dbNetwork }",
            "$actualNetworks.Count -ne 1",
            "$item.HostConfig.Tmpfs",
            "$item.HostConfig.AutoRemove",
            "$baseExpectedLabels",
            "$desktopExpectedLabels",
            "foreach ($candidate in @($baseExpectedLabels, $desktopExpectedLabels))",
            "desktop.docker.io/mounts/",
            "desktop.docker.io/ports.scheme",
            "$dbStartMayHaveOccurred",
            "Wait-DatabaseReady",
            "Assert-OriginalBitmap",
            "coordinator.lock",
            "[IO.FileShare]::None",
            "$coordinatorLockOwned",
            "Invoke-DockerBounded",
            "Invoke-RetainedRecovery",
            "RecoverContainerId",
            "RecoverDbId",
            "RecoverAppId",
            "RecoverIngressId",
            "foreach ($path in @($repo, $workParent, $workRoot)) { Assert-Directory $path }",
            "R7_OWNER_PAYLOAD_DIAGNOSTIC_RECOVERY_PASS container=0 lock=0 bitmap=exact query=0",
            "R7_OWNER_PAYLOAD_DIAGNOSTIC_CLEANUP_PASS",
        ):
            self.assertIn(token, harness)
        for banned in ("createdb", "dropdb", "migrate", "mediaSource", "18085"):
            self.assertNotIn(banned, harness)
        for token in (
            "SERIALIZABLE, READ ONLY, DEFERRABLE",
            'values_list("page_id", "current_payload")',
            "MAP_IDS",
            "CATEGORIES",
        ):
            self.assertIn(token, source)
        for banned in (".save(", ".update(", ".delete(", "select_for_update"):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OwnerPayloadDiagnosticTests)
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    if not result.wasSuccessful() or result.testsRun != 6:
        raise RuntimeError("R7_OWNER_PAYLOAD_DIAGNOSTIC_TESTS_UNAVAILABLE")
    print("R7_OWNER_PAYLOAD_DIAGNOSTIC_TESTS_OK cases=6")
