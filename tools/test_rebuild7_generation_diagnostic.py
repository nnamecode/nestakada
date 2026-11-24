from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import unittest
from pathlib import Path


SOURCE = Path(__file__).with_name("rebuild7_generation.py")
NAMES = {
    "fail",
    "canonical",
    "digest_bytes",
    "safe_table_token",
    "first_mapping_difference",
    "valid_sha256",
    "verify_schema_fingerprint",
    "verify_raw_snapshot",
    "restore_release_sha256",
    "restore_semantic_constraint",
    "binding_capture_value",
}


def load_diagnostic_namespace() -> dict[str, object]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    nodes = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(
                isinstance(target, ast.Name)
                and target.id
                in {
                    "COLUMN_FIELD_NAMES",
                    "CONSTRAINT_FIELD_NAMES",
                    "RELEASE_KEYS",
                    "RESTORE_CONSTRAINT_DEFINITION_SENTINEL",
                    "RESTORE_SOURCE_CAPTURE_SENTINEL",
                }
                for target in targets
            ):
                nodes.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in NAMES:
            nodes.append(node)
    namespace: dict[str, object] = {"hashlib": hashlib, "json": json, "re": re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    if NAMES - set(namespace) or not {
        "COLUMN_FIELD_NAMES",
        "CONSTRAINT_FIELD_NAMES",
        "RELEASE_KEYS",
        "RESTORE_CONSTRAINT_DEFINITION_SENTINEL",
        "RESTORE_SOURCE_CAPTURE_SENTINEL",
    }.issubset(namespace):
        raise AssertionError("diagnostic source extraction incomplete")
    return namespace


def fingerprint() -> dict[str, object]:
    sha = "1" * 64
    fields = {
        name: sha
        for name in (
            "ordinal",
            "type",
            "typmod",
            "notnull",
            "identity",
            "generated",
            "storage",
            "compression",
            "collation",
            "default",
        )
    }
    return {
        "postgres": "17.7",
        "sourceCaptureSha256": sha,
        "sha256": sha,
        "tables": 1,
        "components": {"columns": sha, "constraints": sha, "indexes": sha},
        "tableComponents": {
            "django_content_type": {
                "columns": sha,
                "constraints": sha,
                "indexes": sha,
            }
        },
        "objectComponents": {
            "django_content_type": {
                "columns": {"app_label": sha},
                "constraints": {"content_type_model_closed": sha},
                "indexes": {},
            }
        },
        "columnFieldComponents": {
            "django_content_type": {"app_label": fields}
        },
        "constraintFieldComponents": {
            "django_content_type": {
                "content_type_model_closed": {
                    name: sha
                    for name in (
                        "type",
                        "definition",
                        "deferrable",
                        "deferred",
                        "validated",
                        "noinherit",
                        "key_columns",
                    )
                }
            }
        },
    }


def release_for_snapshot(schema: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "estakada.r7-local-generation-v5",
        "releaseId": "src-test",
        "source": {},
        "dependencies": {},
        "runtime": {},
        "migrationFiles": [],
        "appliedMigrations": [],
        "schemaFingerprint": schema,
        "contracts": {},
        "configuration": {},
    }


class SchemaDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        namespace = load_diagnostic_namespace()
        cls.verify = staticmethod(namespace["verify_schema_fingerprint"])
        cls.verify_snapshot = staticmethod(namespace["verify_raw_snapshot"])
        cls.release_hash = staticmethod(namespace["restore_release_sha256"])
        cls.semantic_constraint = staticmethod(namespace["restore_semantic_constraint"])
        cls.constraint_sentinel = namespace[
            "RESTORE_CONSTRAINT_DEFINITION_SENTINEL"
        ]
        cls.field_names = namespace["COLUMN_FIELD_NAMES"]
        cls.constraint_field_names = namespace["CONSTRAINT_FIELD_NAMES"]
        cls.binding_capture = staticmethod(namespace["binding_capture_value"])

    def test_live_ordinal_contract_excludes_physical_attnum(self) -> None:
        self.assertEqual(self.field_names[0], "ordinal")
        self.assertNotIn("attnum", self.field_names)
        source = SOURCE.read_text(encoding="utf-8")
        self.assertRegex(
            source,
            r"row_number\(\) OVER \(PARTITION BY r\.oid ORDER BY a\.attnum\) AS live_ordinal",
        )
        self.assertIn('"ordinal": row[2]', source)

    def test_identical_fingerprint_passes(self) -> None:
        expected = fingerprint()
        self.verify(expected, copy.deepcopy(expected))

    def test_constraint_field_contract_is_closed(self) -> None:
        self.assertEqual(
            self.constraint_field_names,
            (
                "type",
                "definition",
                "deferrable",
                "deferred",
                "validated",
                "noinherit",
                "key_columns",
            ),
        )

    def test_only_check_definition_is_redacted_from_restore_semantics(self) -> None:
        check = ["table", "check_name", "c", "CHECK raw", False, False, True, False, []]
        foreign_key = [
            "table",
            "fk_name",
            "f",
            "FOREIGN KEY raw",
            False,
            False,
            True,
            False,
            ["column"],
        ]
        semantic_check = self.semantic_constraint(check)
        self.assertEqual(semantic_check[3], self.constraint_sentinel)
        self.assertEqual(semantic_check[:3] + semantic_check[4:], check[:3] + check[4:])
        self.assertEqual(self.semantic_constraint(foreign_key), foreign_key)

    def test_source_capture_definition_hash_is_not_restore_equality(self) -> None:
        expected = fingerprint()
        actual = copy.deepcopy(expected)
        actual["sourceCaptureSha256"] = "2" * 64
        self.verify(expected, actual)

    def test_raw_snapshot_accepts_only_source_capture_hash_difference(self) -> None:
        expected_schema = fingerprint()
        actual_schema = copy.deepcopy(expected_schema)
        actual_schema["sourceCaptureSha256"] = "2" * 64
        release = release_for_snapshot(expected_schema)
        restored_release = copy.deepcopy(release)
        restored_release["schemaFingerprint"] = actual_schema
        facts = {
            "schema": "estakada.r7-local-generation-v5",
            "releaseSha256": "3" * 64,
            "tableCounts": {},
            "tableContentSha256": {},
            "media": {},
        }
        self.verify_snapshot(
            release,
            facts,
            [],
            restored_release,
            copy.deepcopy(facts),
            [],
        )

    def test_release_hash_normalizes_only_source_capture_hash(self) -> None:
        first = release_for_snapshot(fingerprint())
        second = copy.deepcopy(first)
        second["schemaFingerprint"]["sourceCaptureSha256"] = "2" * 64
        self.assertEqual(self.release_hash(first), self.release_hash(second))

        stable_schema_change = copy.deepcopy(second)
        stable_schema_change["schemaFingerprint"]["sha256"] = "3" * 64
        self.assertNotEqual(
            self.release_hash(first), self.release_hash(stable_schema_change)
        )

        stable_release_change = copy.deepcopy(second)
        stable_release_change["runtime"] = {"python": "changed"}
        self.assertNotEqual(
            self.release_hash(first), self.release_hash(stable_release_change)
        )

    def test_field_mismatch_names_exact_safe_attribute(self) -> None:
        expected = fingerprint()
        actual = copy.deepcopy(expected)
        actual["sha256"] = "2" * 64
        actual["components"]["columns"] = "2" * 64
        actual["tableComponents"]["django_content_type"]["columns"] = "2" * 64
        actual["objectComponents"]["django_content_type"]["columns"]["app_label"] = "2" * 64
        actual["columnFieldComponents"]["django_content_type"]["app_label"]["default"] = "2" * 64
        with self.assertRaisesRegex(
            RuntimeError,
            r"^R7_RESTORE_SCHEMA_COLUMNS_DJANGO_CONTENT_TYPE_APP_LABEL_DEFAULT_MISMATCH$",
        ):
            self.verify(expected, actual)

    def test_live_ordinal_mismatch_names_exact_safe_attribute(self) -> None:
        expected = fingerprint()
        actual = copy.deepcopy(expected)
        actual["sha256"] = "2" * 64
        actual["components"]["columns"] = "2" * 64
        actual["tableComponents"]["django_content_type"]["columns"] = "2" * 64
        actual["objectComponents"]["django_content_type"]["columns"]["app_label"] = "2" * 64
        actual["columnFieldComponents"]["django_content_type"]["app_label"]["ordinal"] = "2" * 64
        with self.assertRaisesRegex(
            RuntimeError,
            r"^R7_RESTORE_SCHEMA_COLUMNS_DJANGO_CONTENT_TYPE_APP_LABEL_ORDINAL_MISMATCH$",
        ):
            self.verify(expected, actual)

    def test_constraint_mismatch_names_exact_safe_attribute(self) -> None:
        expected = fingerprint()
        actual = copy.deepcopy(expected)
        actual["sha256"] = "2" * 64
        actual["components"]["constraints"] = "2" * 64
        actual["tableComponents"]["django_content_type"]["constraints"] = "2" * 64
        actual["objectComponents"]["django_content_type"]["constraints"][
            "content_type_model_closed"
        ] = "2" * 64
        actual["constraintFieldComponents"]["django_content_type"][
            "content_type_model_closed"
        ]["definition"] = "2" * 64
        with self.assertRaisesRegex(
            RuntimeError,
            r"^R7_RESTORE_SCHEMA_CONSTRAINTS_DJANGO_CONTENT_TYPE_"
            r"CONTENT_TYPE_MODEL_CLOSED_DEFINITION_MISMATCH$",
        ):
            self.verify(expected, actual)

    def test_incomplete_field_shape_fails_closed(self) -> None:
        expected = fingerprint()
        actual = copy.deepcopy(expected)
        del actual["columnFieldComponents"]["django_content_type"]["app_label"]["default"]
        with self.assertRaisesRegex(
            RuntimeError, r"^R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE$"
        ):
            self.verify(expected, actual)

    def test_incomplete_constraint_field_shape_fails_closed(self) -> None:
        expected = fingerprint()
        actual = copy.deepcopy(expected)
        del actual["constraintFieldComponents"]["django_content_type"][
            "content_type_model_closed"
        ]["definition"]
        with self.assertRaisesRegex(
            RuntimeError, r"^R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE$"
        ):
            self.verify(expected, actual)

    def test_binding_capture_is_closed_safe_and_sensitive(self) -> None:
        release = release_for_snapshot(fingerprint())
        release["source"] = {"files": 1, "sha256": "4" * 64}
        release["appliedMigrations"] = ["pages.0001_initial"]
        facts = {
            "releaseSha256": "5" * 64,
            "tableCounts": {"safe-token": 1},
            "tableContentSha256": {"safe-token": "6" * 64},
            "media": {
                "files": 2,
                "bytes": 7,
                "inventorySha256": "7" * 64,
            },
        }
        first = self.binding_capture(release, facts)
        self.assertEqual(
            set(first),
            {
                "schema",
                "sourceSha256",
                "releaseSha256",
                "schemaFingerprintSha256",
                "appliedMigrationsSha256",
                "tableCountsSha256",
                "tableContentSha256",
                "mediaInventorySha256",
                "mediaFiles",
                "mediaBytes",
            },
        )
        changed = copy.deepcopy(facts)
        changed["tableCounts"]["safe-token"] = 2
        second = self.binding_capture(release, changed)
        self.assertNotEqual(first["tableCountsSha256"], second["tableCountsSha256"])
        self.assertNotIn("safe-token", json.dumps(first))


if __name__ == "__main__":
    unittest.main()
