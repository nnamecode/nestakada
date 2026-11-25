import hashlib
import os
import stat
import sys
import tempfile
import types
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from rebuild3_importer.coordinator import (
    RESULT_SCHEMA,
    RESULT_VERSION,
    ProjectionCounts,
    ReadbackProof,
    SafeResult,
    target_names,
)
from rebuild3_importer.manifest import PublicManifest
from rebuild3_importer.runtime_target import (
    ALLOWED_ERROR_CODES,
    EMPTY_PUBLIC_SQL,
    PRIVATE_REQUEST_TABLES,
    TARGET_COUNT_SQL,
    TARGET_COLLISION_SQL,
    TARGET_GLOBAL_PROOF_SQL,
    TARGET_IDENTITY_SQL,
    TARGET_INVARIANT_SQL,
    TARGET_READBACK_QUERIES,
    TARGET_PRIVILEGE_PROOF_SQL,
    TARGET_ROLE_IDENTITY_SQL,
    TARGET_RUNTIME_SETTINGS_SQL,
    TARGET_SESSION_COUNT_SQL,
    TARGET_SETTINGS_PROOF_SQL,
    INSERT_PAGE_SQL,
    INSERT_GRANT_SQL,
    INSERT_STAFF_SQL,
    CommittedReadback,
    ConcreteRunOps,
    MediaTransfer,
    ProjectionWriter,
    ResultAuthority,
    TargetDatabaseLifecycle,
    TargetEndpoint,
    TargetRuntimeError,
    _close_descriptors,
    _open_child_directory,
    _open_root,
    run_target_migrations,
    _canonical_result,
)
from rebuild3_importer.source import (
    PrivateSourceRows,
    SourcePreflight,
    TargetGrant,
    TargetProvenance,
    TargetStaff,
    VerifiedLedgerEvidence,
)


RUN_ID = uuid.UUID("12345678-1234-4234-8234-123456789abc")
LEDGER_ID = uuid.UUID("87654321-4321-4321-8321-cba987654321")
DIGEST = "a" * 64
MEDIA_DIGEST = "b" * 64
COUNTS = ProjectionCounts(1, 112, 115, 112, 100, 2, 3, 303, 303, 304, 17, 214)


def result(phase, *, error_code=None):
    names = target_names(RUN_ID)
    sealed = phase == "SEALED"
    return SafeResult(
        RESULT_SCHEMA, RESULT_VERSION, phase, RUN_ID, names.database, names.media_key,
        DIGEST, LEDGER_ID, 1, DIGEST, COUNTS,
        DIGEST if sealed else None, MEDIA_DIGEST,
        MEDIA_DIGEST if sealed else None, error_code,
    )


class TargetResultTests(TestCase):
    def trusted_root(self, raw):
        root = Path(raw)
        os.chmod(root, 0o700)
        return root

    def test_created_and_sealed_are_exact_write_once(self):
        with tempfile.TemporaryDirectory() as raw:
            authority = ResultAuthority(self.trusted_root(raw), target_names(RUN_ID))
            authority.record_created(result("CREATED"))
            with self.assertRaisesRegex(TargetRuntimeError, "result-run-root"):
                authority.record_created(result("CREATED"))
            authority.record_terminal(result("SEALED"))
            self.assertEqual(authority.seal_status(result("SEALED")), "EXACT")
            with self.assertRaises(TargetRuntimeError):
                authority.record_terminal(result("FAILED", error_code="file-copy-failed"))

    def test_absent_unknown_and_conflicting_terminal_are_not_exact(self):
        with tempfile.TemporaryDirectory() as raw:
            authority = ResultAuthority(self.trusted_root(raw), target_names(RUN_ID))
            authority.record_created(result("CREATED"))
            self.assertEqual(authority.seal_status(result("SEALED")), "ABSENT")
            (authority.run_root / "unknown").write_text("x", encoding="utf-8")
            self.assertEqual(authority.seal_status(result("SEALED")), "AMBIGUOUS")

        with tempfile.TemporaryDirectory() as raw:
            authority = ResultAuthority(self.trusted_root(raw), target_names(RUN_ID))
            authority.record_created(result("CREATED"))
            authority.record_terminal(result("FAILED", error_code="file-copy-failed"))
            self.assertEqual(authority.seal_status(result("SEALED")), "AMBIGUOUS")

    def test_unknown_entry_blocks_both_terminal_phases(self):
        for terminal in (
            result("SEALED"), result("FAILED", error_code="file-copy-failed"),
        ):
            with self.subTest(phase=terminal.phase), tempfile.TemporaryDirectory() as raw:
                authority = ResultAuthority(self.trusted_root(raw), target_names(RUN_ID))
                authority.record_created(result("CREATED"))
                (authority.run_root / "partial.tmp").write_text("x", encoding="utf-8")
                with self.assertRaisesRegex(TargetRuntimeError, "result-terminal-ambiguous"):
                    authority.record_terminal(terminal)
                self.assertFalse((authority.run_root / f"{terminal.phase}.json").exists())

    def test_failed_error_codes_are_closed_and_safe(self):
        for code in ALLOWED_ERROR_CODES:
            with self.subTest(code=code):
                _canonical_result(result("FAILED", error_code=code))
        with self.assertRaisesRegex(TargetRuntimeError, "result-phase"):
            _canonical_result(result("FAILED", error_code="secret-owner-example"))

    def test_invalid_created_is_rejected_before_run_directory_creation(self):
        with tempfile.TemporaryDirectory() as raw:
            authority = ResultAuthority(self.trusted_root(raw), target_names(RUN_ID))
            value = result("CREATED")
            invalid = SafeResult(
                value.schema, value.version, value.phase, value.run_id, value.database,
                value.media_key, "wrong", value.ledger_identity, value.ledger_generation,
                value.ledger_digest, value.counts, value.database_digest,
                value.source_media_digest, value.target_media_digest, value.error_code,
            )
            with self.assertRaisesRegex(TargetRuntimeError, "result-shape"):
                authority.record_created(invalid)
            self.assertFalse(authority.run_root.exists())

    def test_parent_flush_failure_is_explicitly_ambiguous(self):
        with tempfile.TemporaryDirectory() as raw:
            authority = ResultAuthority(self.trusted_root(raw), target_names(RUN_ID))
            with patch("rebuild3_importer.runtime_target._directory_fsync", side_effect=OSError):
                with self.assertRaisesRegex(TargetRuntimeError, "result-run-root-ambiguous"):
                    authority.record_created(result("CREATED"))
            self.assertTrue(authority.run_root.exists())

    def test_result_authority_rejects_untrusted_root_and_no_follow_absence(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            os.chmod(root, 0o755)
            with self.assertRaisesRegex(TargetRuntimeError, "result-root"):
                ResultAuthority(root, target_names(RUN_ID))

        with tempfile.TemporaryDirectory() as raw:
            authority = ResultAuthority(self.trusted_root(raw), target_names(RUN_ID))
            with patch.object(os, "O_NOFOLLOW", 0, create=True):
                with self.assertRaisesRegex(TargetRuntimeError, "result-no-follow"):
                    authority.record_created(result("CREATED"))

    def test_safe_result_cannot_switch_generated_names_or_phase_fields(self):
        with tempfile.TemporaryDirectory() as raw:
            authority = ResultAuthority(self.trusted_root(raw), target_names(RUN_ID))
            value = result("CREATED")
            foreign = SafeResult(
                value.schema, value.version, value.phase, value.run_id, "foreign",
                value.media_key, value.manifest_digest, value.ledger_identity,
                value.ledger_generation, value.ledger_digest, value.counts,
                value.database_digest, value.source_media_digest,
                value.target_media_digest, value.error_code,
            )
            with self.assertRaisesRegex(TargetRuntimeError, "result-shape"):
                authority.record_created(foreign)


class TargetDatabaseLifecycleTests(TestCase):
    def endpoint(self, root):
        root = Path(root)
        os.chmod(root, 0o700)
        ca = root / "ca.pem"
        admin = root / "admin.secret"
        ca.write_text("certificate", encoding="utf-8")
        admin.write_text("admin-password", encoding="utf-8")
        os.chmod(admin, 0o600)
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=10)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        return TargetEndpoint(
            "db.example.test", 5432, ca, "foundation_admin", admin, root, expiry,
        )

    def connector(
        self, endpoint, *, collision=False, create_lost=False,
        privilege_count=0, global_count=0, settings_count=0,
        importer_connect_lost=False, importer_settings_drift=False,
        existing="none",
    ):
        names = target_names(RUN_ID)
        state = {
            names.owner_role: {"oid": 601, "login": False},
            names.importer_role: {"oid": 701, "login": False},
        }
        dropped = set()
        events = []

        class Cursor:
            def __init__(self, connection):
                self.connection = connection
                self.last = None
                self.params = None

            def __enter__(self): return self
            def __exit__(self, *_args): return False

            def execute(self, sql, params=None):
                self.last = sql
                self.params = params
                self.connection.calls.append((sql, params))
                events.append((self.connection.user, sql, params))
                if create_lost and sql.startswith("CREATE ROLE"):
                    raise RuntimeError("lost response")
                for role in state:
                    if sql.startswith(f"ALTER ROLE {role} LOGIN"):
                        state[role]["login"] = True
                    elif sql == f"ALTER ROLE {role} NOLOGIN":
                        state[role]["login"] = False
                    elif sql == f"DROP ROLE {role}":
                        dropped.add(role)

            def fetchone(self):
                if self.last == TARGET_COLLISION_SQL:
                    if existing == "full":
                        return (501, 601, 701)
                    if existing == "partial":
                        return (501, 601, None)
                    return (501, None, None) if collision else (None, None, None)
                if self.last == TARGET_IDENTITY_SQL:
                    return (501, 601, 601, 701)
                if self.last == EMPTY_PUBLIC_SQL:
                    return (0,)
                if self.last == TARGET_ROLE_IDENTITY_SQL:
                    role = self.params[0]
                    oid = state[role]["oid"]
                    return (
                        oid, False, False, False, False, False, False,
                        state[role]["login"], 1, 0,
                    )
                if "rolvaliduntil" in self.last:
                    role = self.params[0]
                    return (state[role]["oid"], True, endpoint.valid_until_utc)
                if self.last == TARGET_SESSION_COUNT_SQL:
                    return (0,)
                if self.last == TARGET_PRIVILEGE_PROOF_SQL:
                    return (privilege_count,)
                if self.last == TARGET_GLOBAL_PROOF_SQL:
                    return (global_count,)
                if self.last == TARGET_SETTINGS_PROOF_SQL:
                    return (settings_count,)
                if self.last == TARGET_RUNTIME_SETTINGS_SQL:
                    timeout = "15min" if self.connection.user == names.importer_role else "5min"
                    if importer_settings_drift and self.connection.user == names.importer_role:
                        timeout = "unbounded"
                    return (
                        self.connection.user, names.database, "app, pg_catalog",
                        timeout, "5s", "1min",
                    )
                if self.last == "SELECT oid FROM pg_roles WHERE rolname = %s":
                    return None if self.params[0] in dropped else (state[self.params[0]]["oid"],)
                raise AssertionError(self.last)

        class Connection:
            def __init__(self, kwargs):
                self.user = kwargs["user"]
                self.dbname = kwargs["dbname"]
                self.calls = []
                self.closed = False
                self.rollbacks = 0
                self.events = events

            def cursor(self): return Cursor(self)
            def close(self): self.closed = True
            def rollback(self): self.rollbacks += 1

        connections = []

        def connect(**kwargs):
            if importer_connect_lost and kwargs["user"] == names.importer_role:
                raise RuntimeError("lost response")
            value = Connection(kwargs)
            connections.append(value)
            return value

        return connect, connections, state

    def test_generated_lifecycle_migrates_proves_privileges_and_closes_secrets(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(raw)
            connect, connections, state = self.connector(endpoint)
            names = target_names(RUN_ID)
            lifecycle = TargetDatabaseLifecycle.create(endpoint, names, connect=connect)
            migrated = []
            importer = lifecycle.prepare(
                lambda actual_endpoint, actual_names, secret_path: migrated.append(
                    (actual_endpoint, actual_names, secret_path)
                )
            )
            self.assertEqual(
                migrated,
                [(endpoint, names, Path(raw) / f"{RUN_ID}.owner.secret")],
            )
            self.assertEqual(importer.user, names.importer_role)
            self.assertEqual(importer.rollbacks, 1)
            self.assertFalse((Path(raw) / f"{RUN_ID}.owner.secret").exists())
            self.assertTrue((Path(raw) / f"{RUN_ID}.importer.secret").exists())
            lifecycle.close_identities()
            self.assertFalse((Path(raw) / f"{RUN_ID}.importer.secret").exists())
            self.assertFalse(state[names.owner_role]["login"])
            self.assertFalse(state[names.importer_role]["login"])
            self.assertTrue(all(connection.closed for connection in connections))

    def test_collision_and_lost_create_response_are_distinct_and_do_not_retry(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(raw)
            connect, connections, _state = self.connector(endpoint, collision=True)
            with self.assertRaisesRegex(TargetRuntimeError, "target-collision"):
                TargetDatabaseLifecycle.create(endpoint, target_names(RUN_ID), connect=connect)
            self.assertEqual(len(connections), 1)
            self.assertTrue(connections[0].closed)

        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(raw)
            connect, connections, _state = self.connector(endpoint, create_lost=True)
            with self.assertRaisesRegex(TargetRuntimeError, "target-create-ambiguous"):
                TargetDatabaseLifecycle.create(endpoint, target_names(RUN_ID), connect=connect)
            self.assertEqual(len(connections), 1)
            self.assertTrue(connections[0].closed)

    def test_post_create_probe_returns_owned_token_only_for_exact_full_identity(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(raw)
            connect, connections, _state = self.connector(endpoint, existing="none")
            status, lifecycle = TargetDatabaseLifecycle.recover_after_create(
                endpoint, target_names(RUN_ID), connect=connect,
            )
            self.assertEqual((status, lifecycle), ("ABSENT", None))
            self.assertTrue(all(connection.closed for connection in connections))

        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(raw)
            connect, connections, _state = self.connector(endpoint, existing="partial")
            status, lifecycle = TargetDatabaseLifecycle.recover_after_create(
                endpoint, target_names(RUN_ID), connect=connect,
            )
            self.assertEqual((status, lifecycle), ("AMBIGUOUS", None))
            self.assertTrue(all(connection.closed for connection in connections))

        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(raw)
            connect, _connections, _state = self.connector(endpoint, existing="full")
            status, lifecycle = TargetDatabaseLifecycle.recover_after_create(
                endpoint, target_names(RUN_ID), connect=connect,
            )
            self.assertEqual(status, "ACQUIRED")
            self.assertIsInstance(lifecycle, TargetDatabaseLifecycle)
            lifecycle.close_identities()

    def test_privilege_failure_happens_before_importer_secret_or_login(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(raw)
            connect, _connections, state = self.connector(endpoint, privilege_count=1)
            names = target_names(RUN_ID)
            lifecycle = TargetDatabaseLifecycle.create(endpoint, names, connect=connect)
            with self.assertRaisesRegex(TargetRuntimeError, "target-privileges"):
                lifecycle.prepare(lambda *_args: None)
            self.assertFalse((Path(raw) / f"{RUN_ID}.importer.secret").exists())
            self.assertFalse(state[names.importer_role]["login"])
            lifecycle.close_identities()
            self.assertFalse(state[names.owner_role]["login"])
            self.assertFalse(state[names.importer_role]["login"])

    def test_each_prelogin_matrix_failure_blocks_both_login_roles(self):
        for field in ("global_count", "settings_count", "privilege_count"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as raw:
                endpoint = self.endpoint(raw)
                options = {field: 1}
                connect, _connections, state = self.connector(endpoint, **options)
                names = target_names(RUN_ID)
                lifecycle = TargetDatabaseLifecycle.create(endpoint, names, connect=connect)
                with self.assertRaises(TargetRuntimeError):
                    lifecycle.prepare(lambda *_args: None)
                self.assertFalse(state[names.owner_role]["login"])
                self.assertFalse(state[names.importer_role]["login"])
                self.assertFalse((Path(raw) / f"{RUN_ID}.importer.secret").exists())
                lifecycle.close_identities()

    def test_extra_database_setting_is_rejected_before_owner_login(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(raw)
            connect, connections, state = self.connector(endpoint, settings_count=1)
            names = target_names(RUN_ID)
            lifecycle = TargetDatabaseLifecycle.create(endpoint, names, connect=connect)
            with self.assertRaisesRegex(TargetRuntimeError, "target-role-settings"):
                lifecycle.prepare(lambda *_args: None)
            self.assertFalse(state[names.owner_role]["login"])
            self.assertFalse(any(
                event[1].startswith(f"ALTER ROLE {names.owner_role} LOGIN")
                for event in connections[0].events
            ))
            lifecycle.close_identities()

    def test_global_default_acl_violation_blocks_before_importer_secret(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(raw)
            connect, _connections, state = self.connector(endpoint, privilege_count=1)
            names = target_names(RUN_ID)
            lifecycle = TargetDatabaseLifecycle.create(endpoint, names, connect=connect)
            with self.assertRaisesRegex(TargetRuntimeError, "target-privileges"):
                lifecycle.prepare(lambda *_args: None)
            self.assertFalse((Path(raw) / f"{RUN_ID}.importer.secret").exists())
            self.assertFalse(state[names.importer_role]["login"])
            lifecycle.close_identities()

    def test_role_oid_drift_blocks_close_and_preserves_owned_secret(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(raw)
            connect, _connections, _state = self.connector(endpoint)
            names = target_names(RUN_ID)
            lifecycle = TargetDatabaseLifecycle.create(endpoint, names, connect=connect)
            lifecycle.prepare(lambda *_args: None)
            lifecycle._owner_oid += 1
            with self.assertRaisesRegex(TargetRuntimeError, "target-close-ambiguous"):
                lifecycle.close_identities()
            self.assertTrue((Path(raw) / f"{RUN_ID}.importer.secret").exists())

    def test_privilege_proof_is_literal_and_denies_broad_capabilities(self):
        self.assertIn("has_any_column_privilege", TARGET_PRIVILEGE_PROOF_SQL)
        self.assertIn("'UPDATE,REFERENCES'", TARGET_PRIVILEGE_PROOF_SQL)
        self.assertIn("unexpected-importer-table", TARGET_PRIVILEGE_PROOF_SQL)
        self.assertEqual(
            PRIVATE_REQUEST_TABLES,
            (
                "service_requests_servicerequest",
                "service_requests_servicerequestdeletionprojection",
            ),
        )
        self.assertIn("private-request-table", TARGET_PRIVILEGE_PROOF_SQL)
        self.assertIn("%(private_request_tables)s", TARGET_PRIVILEGE_PROOF_SQL)
        self.assertIn("DELETE,TRUNCATE,REFERENCES,TRIGGER", TARGET_PRIVILEGE_PROOF_SQL)
        self.assertIn("schema-owner", TARGET_PRIVILEGE_PROOF_SQL)
        self.assertIn("public-function", TARGET_PRIVILEGE_PROOF_SQL)
        self.assertIn("public-type", TARGET_PRIVILEGE_PROOF_SQL)
        self.assertIn("has_any_column_privilege", TARGET_PRIVILEGE_PROOF_SQL)
        self.assertIn("has_sequence_privilege", TARGET_PRIVILEGE_PROOF_SQL)
        self.assertIn("pg_default_acl", TARGET_PRIVILEGE_PROOF_SQL)
        self.assertIn('END)::"char"', TARGET_PRIVILEGE_PROOF_SQL)
        self.assertNotIn("a.defaclnamespace =", TARGET_PRIVILEGE_PROOF_SQL)
        self.assertIn("other-database", TARGET_GLOBAL_PROOF_SQL)
        self.assertIn("rolbypassrls", TARGET_GLOBAL_PROOF_SQL)
        self.assertIn("pg_db_role_setting", TARGET_SETTINGS_PROOF_SQL)
        self.assertIn("extra-database-setting", TARGET_SETTINGS_PROOF_SQL)
        self.assertIn("s.setdatabase <>", TARGET_SETTINGS_PROOF_SQL)
        self.assertIn("rolconfig", TARGET_SETTINGS_PROOF_SQL)

    def test_owner_global_proof_precedes_login_and_importer_proof_precedes_secret(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(raw)
            connect, connections, _state = self.connector(endpoint)
            names = target_names(RUN_ID)
            lifecycle = TargetDatabaseLifecycle.create(endpoint, names, connect=connect)
            lifecycle.prepare(lambda *_args: None)
            owner_global = next(
                index for index, event in enumerate(connections[0].events)
                if event[1] == TARGET_GLOBAL_PROOF_SQL and event[2][0] == names.owner_role
            )
            owner_login = next(
                index for index, event in enumerate(connections[0].events)
                if event[1].startswith(f"ALTER ROLE {names.owner_role} LOGIN")
            )
            self.assertLess(owner_global, owner_login)
            privilege = next(
                i for i, event in enumerate(connections[0].events)
                if event[1] == TARGET_PRIVILEGE_PROOF_SQL
            )
            importer_login = next(
                i for i, event in enumerate(connections[0].events)
                if event[1].startswith(f"ALTER ROLE {names.importer_role} LOGIN")
            )
            self.assertLess(privilege, importer_login)
            lifecycle.close_identities()

    def test_prepare_is_one_shot_after_failure_between_credentials(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(raw)
            connect, _connections, _state = self.connector(endpoint)
            lifecycle = TargetDatabaseLifecycle.create(
                endpoint, target_names(RUN_ID), connect=connect,
            )
            original = __import__(
                "rebuild3_importer.runtime_target", fromlist=["_write_secret"]
            )._write_secret
            calls = 0

            def fail_second(path, value):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise TargetRuntimeError("reader-secret-write")
                return original(path, value)

            with patch("rebuild3_importer.runtime_target._write_secret", side_effect=fail_second):
                with self.assertRaises(TargetRuntimeError):
                    lifecycle.prepare(lambda *_args: None)
            with self.assertRaisesRegex(TargetRuntimeError, "target-prepare-state"):
                lifecycle.prepare(lambda *_args: None)
            lifecycle.close_identities()

    def test_failure_boundaries_remove_exact_importer_role_without_retry(self):
        cases = ("migration", "connect", "settings")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as raw:
                endpoint = self.endpoint(raw)
                connect, connections, state = self.connector(
                    endpoint,
                    importer_connect_lost=case == "connect",
                    importer_settings_drift=case == "settings",
                )
                names = target_names(RUN_ID)
                lifecycle = TargetDatabaseLifecycle.create(endpoint, names, connect=connect)

                def migrate(*_args):
                    if case == "migration":
                        raise RuntimeError("migration failed")

                with self.assertRaises(TargetRuntimeError):
                    lifecycle.prepare(migrate)
                self.assertFalse(state[names.owner_role]["login"])
                self.assertFalse(state[names.importer_role]["login"])
                lifecycle.close_identities()
                self.assertFalse((Path(raw) / f"{RUN_ID}.owner.secret").exists())
                self.assertFalse((Path(raw) / f"{RUN_ID}.importer.secret").exists())
                target_calls = connections[1].calls
                self.assertTrue(any(call[0] == f"DROP ROLE {names.importer_role}" for call in target_calls))


class TargetProjectionTests(TestCase):
    PAGE_ID = "00000000-0000-4000-8000-000000000101"
    ROUTE_ID = "00000000-0000-4000-8000-000000000102"
    ASSET_ID = "00000000-0000-4000-8000-000000000103"
    FILE_ID = "00000000-0000-4000-8000-000000000104"
    USAGE_ID = "00000000-0000-4000-8000-000000000105"
    SETTINGS_ID = "00000000-0000-4000-8000-000000000106"

    class Cursor:
        def __init__(self, connection):
            self.connection = connection
            self.result = None

        def __enter__(self): return self
        def __exit__(self, *_args): return False

        def execute(self, sql, params=None):
            if sql == "BEGIN ISOLATION LEVEL SERIALIZABLE":
                if self.connection.in_transaction:
                    raise RuntimeError("transaction already open")
                self.connection.in_transaction = True
                self.connection.begin_count += 1
            self.connection.events.append((sql, params))
            if sql == TARGET_INVARIANT_SQL:
                self.result = (self.connection.invariant_count,)
            elif sql == TARGET_COUNT_SQL:
                self.result = self.connection.counts
            else:
                self.result = None

        def fetchone(self):
            return self.result

    class Connection:
        def __init__(self, counts, invariant_count=0):
            self.counts = counts
            self.invariant_count = invariant_count
            self.events = []
            self.commits = 0
            self.rollbacks = 0
            self.begin_count = 0
            self.in_transaction = False

        def cursor(self): return TargetProjectionTests.Cursor(self)
        def commit(self):
            self.commits += 1
            self.in_transaction = False

        def rollback(self):
            self.rollbacks += 1
            self.in_transaction = False

    def manifest(self):
        payload = {"schema": "estakada.page-content", "schema_version": 1}
        page = {
            "id": self.PAGE_ID, "name": "Главная", "kind": "home",
            "parent_id": None, "position": 0, "is_published": True,
            "content_generation": 1,
            "current": {
                "payload": payload, "sha256": DIGEST,
                "created_at": "2026-11-17T00:00:00.000000Z",
            },
            "previous": None,
        }
        return PublicManifest(
            "snapshot-1", DIGEST,
            {
                "id": self.SETTINGS_ID, "structure_generation": 1,
                "settings_generation": 1, "organization_name": "Эстакада",
                "legal_name": None, "phone_display": "+7 499 110-25-52",
                "phone_e164": "+74991102552", "address": "Москва",
                "opening_hours": "09:00–21:00",
                "contact_email": "owner@example.test",
                "map_url": "https://example.test/map", "max_url": None,
                "telegram_url": None, "logo_asset_id": self.ASSET_ID,
            },
            {
                "routes": ({
                    "id": self.ROUTE_ID, "page_id": self.PAGE_ID,
                    "target": "/", "mode": "PRIMARY", "outcome": "home",
                },),
                "pages": (page,),
                "assets": ({
                    "id": self.ASSET_ID, "purpose": "SITE_ASSET",
                    "source_sha256": DIGEST, "state": "READY",
                },),
                "files": ({
                    "id": self.FILE_ID, "asset_id": self.ASSET_ID,
                    "kind": "MAIN", "source_path": "logo.png",
                    "sha256": DIGEST, "byte_size": 1,
                    "mime_type": "image/png", "width": 1, "height": 1,
                },),
                "usages": ({
                    "id": self.USAGE_ID, "asset_id": self.ASSET_ID,
                    "scope": "SITE_SETTINGS", "target_uuid": self.SETTINGS_ID,
                    "slot": "logo", "position": 0,
                },),
                "gallery_albums": (), "gallery_photos": (),
            },
        )

    def private_rows(self):
        owner = TargetStaff(
            uuid.UUID("00000000-0000-4000-8000-000000000107"),
            "nesadmin", True, "OWNER", 1,
        )
        return PrivateSourceRows(
            (owner,), (),
            (TargetProvenance(uuid.UUID(self.PAGE_ID), "CURRENT", owner.id),),
        )

    def test_literal_projection_verifies_before_single_commit(self):
        expected = ProjectionCounts(1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 0, 0)
        connection = self.Connection(tuple(expected.__dict__.values()) if hasattr(expected, "__dict__") else (
            expected.site_settings, expected.pages, expected.routes, expected.current,
            expected.previous, expected.staff, expected.grants, expected.assets,
            expected.files, expected.usages, expected.albums, expected.photos,
        ))
        writer = ProjectionWriter(connection)
        writer.begin()
        with self.assertRaisesRegex(TargetRuntimeError, "target-import-state"):
            writer.commit()
        writer.import_public(self.manifest())
        writer.import_private(self.private_rows())
        writer.apply_zero_ledger(VerifiedLedgerEvidence(
            LEDGER_ID, 1, DIGEST, 0, "snapshot-1",
        ))
        self.assertEqual(writer.verify_counts(), expected)
        writer.commit()
        self.assertEqual((connection.commits, connection.rollbacks), (1, 0))
        self.assertEqual(connection.begin_count, 1)
        sql = [event[0] for event in connection.events]
        self.assertLess(sql.index(INSERT_STAFF_SQL), sql.index(TARGET_INVARIANT_SQL))
        self.assertIn("primary_url_mutable", INSERT_PAGE_SQL)
        self.assertIn("FALSE", INSERT_PAGE_SQL)
        self.assertIn("p.primary_url_mutable IS DISTINCT FROM FALSE", TARGET_INVARIANT_SQL)
        page_insert = next(event for event in connection.events if event[0] == INSERT_PAGE_SQL)
        self.assertEqual(len(page_insert[1]), 6)
        self.assertNotIn("owner-password", repr(connection.events))

    def test_page_cycle_and_invariant_failure_block_commit(self):
        manifest = self.manifest()
        manifest.sections["pages"][0]["parent_id"] = self.PAGE_ID
        connection = self.Connection((1,) * 12)
        writer = ProjectionWriter(connection)
        writer.begin()
        with self.assertRaisesRegex(TargetRuntimeError, "target-page-cycle"):
            writer.import_public(manifest)
        writer.rollback()
        self.assertEqual(connection.rollbacks, 1)

        expected = (1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 0, 0)
        connection = self.Connection(expected, invariant_count=1)
        writer = ProjectionWriter(connection)
        writer.begin()
        writer.import_public(self.manifest())
        writer.import_private(self.private_rows())
        writer.apply_zero_ledger(VerifiedLedgerEvidence(
            LEDGER_ID, 1, DIGEST, 0, "snapshot-1",
        ))
        with self.assertRaisesRegex(TargetRuntimeError, "target-invariants"):
            writer.verify_counts()
        with self.assertRaisesRegex(TargetRuntimeError, "target-import-state"):
            writer.commit()
        writer.rollback()

    def test_private_projection_rejects_owner_or_grant_drift(self):
        owner = TargetStaff(uuid.uuid4(), "other", True, "OWNER", 1)
        rows = PrivateSourceRows(
            (owner,), (),
            (TargetProvenance(uuid.UUID(self.PAGE_ID), "CURRENT", owner.id),),
        )
        writer = ProjectionWriter(self.Connection((0,) * 12))
        writer.begin()
        writer.import_public(self.manifest())
        with self.assertRaisesRegex(TargetRuntimeError, "target-staff"):
            writer.import_private(rows)

        valid_owner = TargetStaff(uuid.uuid4(), "nesadmin", True, "OWNER", 1)
        employee = TargetStaff(uuid.uuid4(), "worker", True, "EMPLOYEE", 1)
        rows = PrivateSourceRows(
            (valid_owner, employee),
            (TargetGrant(employee.id, uuid.UUID(self.PAGE_ID), ("prices", "text")),),
            (TargetProvenance(
                uuid.UUID(self.PAGE_ID), "CURRENT", valid_owner.id,
            ),),
        )
        writer = ProjectionWriter(self.Connection((0,) * 12))
        writer.begin()
        writer.import_public(self.manifest())
        with self.assertRaisesRegex(TargetRuntimeError, "target-grant"):
            writer.import_private(rows)


class TargetCommittedReadbackTests(TestCase):
    class Cursor:
        def __init__(self, connection):
            self.connection = connection
            self.sql = None

        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, sql, params=None):
            if sql == self.connection.fail_sql:
                raise RuntimeError("query failed")
            self.sql = sql
            self.connection.events.append((sql, params))
        def fetchone(self):
            if self.sql == TARGET_INVARIANT_SQL:
                return (self.connection.invariant_count,)
            if self.sql == TARGET_COUNT_SQL:
                return self.connection.counts
            raise AssertionError(self.sql)
        def fetchmany(self, size):
            self.connection.table_reads += 1
            return self.connection.rows[self.sql][:size]

    class Connection:
        def __init__(self, rows, counts, invariant_count=0, fail_sql=None):
            self.rows = rows
            self.counts = counts
            self.invariant_count = invariant_count
            self.fail_sql = fail_sql
            self.events = []
            self.table_reads = 0
        def cursor(self): return TargetCommittedReadbackTests.Cursor(self)

    def fixtures(self):
        fixture = TargetProjectionTests()
        manifest = fixture.manifest()
        private = fixture.private_rows()
        page = manifest.sections["pages"][0]
        settings = manifest.site_settings
        owner = private.staff[0]
        values = {
            "assets": ((fixture.ASSET_ID, "SITE_ASSET", DIGEST, "READY", True),),
            "files": ((
                fixture.FILE_ID, fixture.ASSET_ID, "MAIN",
                f"img/{fixture.ASSET_ID}/main.png", DIGEST, 1,
                "image/png", 1, 1,
            ),),
            "pages": ((fixture.PAGE_ID, "Главная", "home", None, 0, True, False),),
            "routes": ((fixture.ROUTE_ID, fixture.PAGE_ID, "/", "PRIMARY", "home"),),
            "settings": ((
                settings["id"], 1, 1, "Эстакада", None, "+7 499 110-25-52",
                "+74991102552", "Москва", "09:00–21:00", "owner@example.test",
                "https://example.test/map", None, None, fixture.ASSET_ID,
            ),),
            "usages": ((
                fixture.USAGE_ID, fixture.ASSET_ID, "SITE_SETTINGS",
                fixture.SETTINGS_ID, "logo", 0,
            ),),
            "albums": (), "photos": (),
            "staff": ((
                str(owner.id), "nesadmin", True, "OWNER", 1, True, True, "!",
                None, "", "", "", True,
            ),),
            "content": ((
                fixture.PAGE_ID, 1, page["current"]["payload"], DIGEST,
                str(owner.id), "2026-11-17T00:00:00.000000Z",
                None, None, None, None,
                None, None, None, None,
            ),),
            "grants": (),
        }
        rows = {TARGET_READBACK_QUERIES[name]: value for name, value in values.items()}
        counts = (1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 0, 0)
        ledger = VerifiedLedgerEvidence(LEDGER_ID, 1, DIGEST, 0, "snapshot-1")
        return manifest, private, ledger, rows, counts

    def test_exact_committed_projection_returns_closed_proof_once(self):
        manifest, private, ledger, rows, counts = self.fixtures()
        connection = self.Connection(rows, counts)
        reader = CommittedReadback(connection)
        proof = reader.read(manifest, private, ledger, MEDIA_DIGEST, MEDIA_DIGEST)
        self.assertEqual(proof.database_digest, manifest.digest)
        self.assertEqual(proof.counts, ProjectionCounts(*counts))
        self.assertEqual(connection.events[0][0], "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        with self.assertRaisesRegex(TargetRuntimeError, "target-readback-state"):
            reader.read(manifest, private, ledger, MEDIA_DIGEST, MEDIA_DIGEST)

    def test_any_row_or_count_drift_fails_closed(self):
        manifest, private, ledger, rows, counts = self.fixtures()
        route_sql = TARGET_READBACK_QUERIES["routes"]
        rows[route_sql] = ((
            TargetProjectionTests.ROUTE_ID, TargetProjectionTests.PAGE_ID,
            "/drift/", "PRIMARY", "home",
        ),)
        with self.assertRaisesRegex(TargetRuntimeError, "target-readback-drift"):
            CommittedReadback(self.Connection(rows, counts)).read(
                manifest, private, ledger, MEDIA_DIGEST, MEDIA_DIGEST,
            )
        manifest, private, ledger, rows, counts = self.fixtures()
        bad_counts = tuple(counts[:1]) + (2,) + tuple(counts[2:])
        with self.assertRaisesRegex(TargetRuntimeError, "target-readback-counts"):
            connection = self.Connection(rows, bad_counts)
            CommittedReadback(connection).read(
                manifest, private, ledger, MEDIA_DIGEST, MEDIA_DIGEST,
            )
        self.assertEqual(connection.table_reads, 0)
        manifest, private, ledger, rows, counts = self.fixtures()
        pages_sql = TARGET_READBACK_QUERIES["pages"]
        rows[pages_sql] = (rows[pages_sql][0][:-1] + (True,),)
        with self.assertRaisesRegex(TargetRuntimeError, "target-readback-drift"):
            CommittedReadback(self.Connection(rows, counts)).read(
                manifest, private, ledger, MEDIA_DIGEST, MEDIA_DIGEST,
            )

    def test_fixed_row_bounds_types_and_normalization_contracts(self):
        mutations = (
            ("staff-fixed", lambda rows, counts: rows.__setitem__(
                TARGET_READBACK_QUERIES["staff"],
                (rows[TARGET_READBACK_QUERIES["staff"]][0][:-5]
                 + ("unexpected-login", "", "", "", True),),
            )),
            ("content-fixed", lambda rows, counts: rows.__setitem__(
                TARGET_READBACK_QUERIES["content"],
                (rows[TARGET_READBACK_QUERIES["content"]][0][:-4]
                 + (uuid.uuid4(), None, None, None),),
            )),
            ("missing", lambda rows, counts: rows.__setitem__(
                TARGET_READBACK_QUERIES["routes"], (),
            )),
            ("extra", lambda rows, counts: rows.__setitem__(
                TARGET_READBACK_QUERIES["routes"],
                rows[TARGET_READBACK_QUERIES["routes"]]
                + ((uuid.uuid4(), TargetProjectionTests.PAGE_ID,
                    "/extra/", "ALIAS", "home"),),
            )),
            ("bool-count", lambda rows, counts: counts.__setitem__(0, True)),
        )
        for name, mutate in mutations:
            with self.subTest(name=name):
                manifest, private, ledger, rows, raw_counts = self.fixtures()
                counts = list(raw_counts)
                mutate(rows, counts)
                with self.assertRaises(TargetRuntimeError):
                    CommittedReadback(self.Connection(rows, tuple(counts))).read(
                        manifest, private, ledger, MEDIA_DIGEST, MEDIA_DIGEST,
                    )

        manifest, private, ledger, rows, counts = self.fixtures()
        content_sql = TARGET_READBACK_QUERIES["content"]
        content = list(rows[content_sql][0])
        content[0] = uuid.UUID(content[0])
        content[2] = dict(content[2])
        content[4] = uuid.UUID(content[4])
        content[5] = datetime(2026, 11, 17, tzinfo=timezone.utc)
        rows[content_sql] = (tuple(content),)
        proof = CommittedReadback(self.Connection(rows, counts)).read(
            manifest, private, ledger, MEDIA_DIGEST, MEDIA_DIGEST,
        )
        self.assertEqual(proof.database_digest, manifest.digest)

    def test_query_exception_is_constant_and_one_shot(self):
        manifest, private, ledger, rows, counts = self.fixtures()
        reader = CommittedReadback(self.Connection(
            rows, counts, fail_sql=TARGET_READBACK_QUERIES["routes"],
        ))
        with self.assertRaisesRegex(TargetRuntimeError, "target-readback-ambiguous"):
            reader.read(manifest, private, ledger, MEDIA_DIGEST, MEDIA_DIGEST)
        with self.assertRaisesRegex(TargetRuntimeError, "target-readback-state"):
            reader.read(manifest, private, ledger, MEDIA_DIGEST, MEDIA_DIGEST)

        manifest, private, ledger, rows, counts = self.fixtures()
        connection = self.Connection(rows, counts, invariant_count=1)
        with self.assertRaisesRegex(TargetRuntimeError, "target-readback-invariants"):
            CommittedReadback(connection).read(
                manifest, private, ledger, MEDIA_DIGEST, MEDIA_DIGEST,
            )
        self.assertEqual(connection.table_reads, 0)


class ConcreteRunOpsTests(TestCase):
    def test_one_composition_delegates_exact_sequence_and_cleanup_stays_closed(self):
        fixture = TargetProjectionTests()
        manifest = fixture.manifest()
        private = fixture.private_rows()
        ledger = VerifiedLedgerEvidence(LEDGER_ID, 1, DIGEST, 0, "snapshot-1")
        source = SourcePreflight(ledger, 1, 0, 1, 0)
        calls = []

        class SourceLifecycle:
            def close(self): calls.append("source-close")
        class Media:
            def preflight(self, value): calls.append("media-preflight"); return MEDIA_DIGEST
            def copy_and_verify(self, value, names): calls.append("media-copy"); return MEDIA_DIGEST
            def readback(self, value, names): calls.append("media-readback"); return MEDIA_DIGEST
        class Target:
            def prepare(self, migrate): calls.append(("prepare", migrate)); return object()
            def close_identities(self): calls.append("target-close")
        class Writer:
            def begin(self): calls.append("begin")
            def import_public(self, value): calls.append("public")
            def import_private(self, value): calls.append("private")
            def apply_zero_ledger(self, value): calls.append("ledger")
            def verify_counts(self): calls.append("verify"); return ProjectionCounts(1,1,1,1,0,1,0,1,1,1,0,0)
            def commit(self): calls.append("commit")
            def rollback(self): calls.append("rollback")
            def clear_private(self): calls.append("clear-private")
        class Authority:
            def record_created(self, value): calls.append("created")
            def record_terminal(self, value): calls.append(value.phase.lower())
            def seal_status(self, value): return "EXACT"
        proof = ReadbackProof(
            RESULT_SCHEMA, RESULT_VERSION,
            ProjectionCounts(1,1,1,1,0,1,0,1,1,1,0,0),
            DIGEST, DIGEST, MEDIA_DIGEST, MEDIA_DIGEST,
            LEDGER_ID, 1, DIGEST, True, True, True,
        )
        reader = types.SimpleNamespace(read=lambda *_args: proof)
        target = Target()
        endpoint = object()
        names = target_names(RUN_ID)
        with (
            patch("rebuild3_importer.runtime_target._target_endpoint", return_value=endpoint),
            patch.object(TargetDatabaseLifecycle, "create", return_value=target),
            patch("rebuild3_importer.runtime_target.ProjectionWriter", return_value=Writer()),
            patch("rebuild3_importer.runtime_target.ResultAuthority", return_value=Authority()),
            patch("rebuild3_importer.runtime_target.CommittedReadback", return_value=reader),
        ):
            ops = ConcreteRunOps(endpoint, SourceLifecycle(), Media(), Path("/results"))
            pretarget = ops.validate_pre_target(manifest, source)
            self.assertEqual(pretarget.source_media_digest, MEDIA_DIGEST)
            ops.create_empty_target(names)
            ops.record_created(result("CREATED"))
            ops.prepare_target(names)
            ops.begin_import(names)
            ops.import_public(manifest)
            ops.import_private(private)
            ops.apply_zero_request_ledger(ledger)
            ops.copy_and_verify_files(manifest, names)
            ops.verify_before_commit(manifest, private)
            ops.commit()
            self.assertEqual(ops.readback(manifest, names), proof)
            self.assertIsNone(ops._private)
            self.assertIn("clear-private", calls)
            with self.assertRaises(TargetRuntimeError):
                ops.commit()
            with self.assertRaises(TargetRuntimeError):
                ops.readback(manifest, names)
            ops.close_source_identity()
            ops.close_identities(names)
            ops.record_sealed(result("SEALED"))
            self.assertEqual(ops.seal_status(result("SEALED")), "EXACT")
            cleanup = ops.cleanup_proof(names)
            self.assertFalse(cleanup.allows_cleanup())
            self.assertFalse(cleanup.pointers_absent)
            with self.assertRaisesRegex(
                TargetRuntimeError, "cleanup-pointer-authority-absent",
            ):
                ops.cleanup_exact_pair(names)
        self.assertIn(("prepare", run_target_migrations), calls)
        self.assertEqual(calls.count("media-copy"), 1)
        self.assertEqual(calls.count("media-readback"), 1)

    def test_recovery_is_one_shot_for_exact_absent_and_ambiguous(self):
        endpoint = object()
        names = target_names(RUN_ID)
        exact = object()
        fixture = TargetProjectionTests()
        manifest = fixture.manifest()
        ledger = VerifiedLedgerEvidence(LEDGER_ID, 1, DIGEST, 0, "snapshot-1")
        source = SourcePreflight(ledger, 1, 0, 1, 0)
        media = types.SimpleNamespace(preflight=lambda value: MEDIA_DIGEST)
        for status, lifecycle in (("ACQUIRED", exact), ("ABSENT", None), ("AMBIGUOUS", None)):
            with self.subTest(status=status):
                with (
                    patch("rebuild3_importer.runtime_target._target_endpoint", return_value=endpoint),
                    patch.object(TargetDatabaseLifecycle, "create", side_effect=RuntimeError),
                    patch.object(
                        TargetDatabaseLifecycle, "recover_after_create",
                        return_value=(status, lifecycle),
                    ),
                ):
                    ops = ConcreteRunOps(endpoint, object(), media, Path("/results"))
                    ops.validate_pre_target(manifest, source)
                    with self.assertRaises(RuntimeError):
                        ops.create_empty_target(names)
                    self.assertEqual(ops.target_acquisition_status(names), status)
                    self.assertIs(ops._target, lifecycle)
                    with self.assertRaisesRegex(TargetRuntimeError, "runops-acquisition-state"):
                        ops.target_acquisition_status(names)

    def test_off_order_calls_fail_before_side_effects(self):
        fixture = TargetProjectionTests()
        manifest = fixture.manifest()
        ledger = VerifiedLedgerEvidence(LEDGER_ID, 1, DIGEST, 0, "snapshot-1")
        source = SourcePreflight(ledger, 1, 0, 1, 0)
        calls = []
        media = types.SimpleNamespace(
            preflight=lambda value: MEDIA_DIGEST,
            copy_and_verify=lambda *args: calls.append("copy"),
        )
        endpoint = object()
        names = target_names(RUN_ID)
        with patch("rebuild3_importer.runtime_target._target_endpoint", return_value=endpoint):
            ops = ConcreteRunOps(endpoint, object(), media, Path("/results"))
            ops.validate_pre_target(manifest, source)
            for method, args in (
                (ops.copy_and_verify_files, (manifest, names)),
                (ops.commit, ()),
                (ops.readback, (manifest, names)),
                (ops.import_private, (fixture.private_rows(),)),
            ):
                with self.subTest(method=method.__name__), self.assertRaises(TargetRuntimeError):
                    method(*args)
            self.assertEqual(calls, [])

    def test_commit_lost_response_prepared_rollback_and_close_ambiguity(self):
        endpoint = object()
        with patch("rebuild3_importer.runtime_target._target_endpoint", return_value=endpoint):
            ops = ConcreteRunOps(endpoint, object(), object(), Path("/results"))

        class LostCommitWriter:
            def __init__(self): self.rollback_calls = 0; self.cleared = 0
            def commit(self): raise RuntimeError("lost response")
            def rollback(self): self.rollback_calls += 1
            def clear_private(self): self.cleared += 1
        writer = LostCommitWriter()
        ops._writer = writer
        ops._phase = "VERIFIED"
        with self.assertRaises(RuntimeError):
            ops.commit()
        self.assertEqual(ops._phase, "COMMIT_PENDING")
        with self.assertRaisesRegex(TargetRuntimeError, "runops-rollback-ambiguous"):
            ops.rollback()
        self.assertEqual(writer.rollback_calls, 0)

        connection = types.SimpleNamespace(rollbacks=0)
        def rollback(): connection.rollbacks += 1
        connection.rollback = rollback
        ops._connection = connection
        ops._phase = "PREPARED"
        ops.rollback()
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(writer.cleared, 1)
        with self.assertRaises(TargetRuntimeError):
            ops.rollback()

        class FailingSource:
            def close(self): raise RuntimeError("close ambiguous")
        ops._source_lifecycle = FailingSource()
        with self.assertRaises(RuntimeError):
            ops.close_source_identity()
        self.assertTrue(ops._source_close_attempted)
        self.assertFalse(ops._source_closed)
        self.assertEqual(writer.cleared, 2)
        with self.assertRaisesRegex(TargetRuntimeError, "runops-failed-state"):
            ops.record_failed(result("FAILED", error_code="database-import-failed"))
        with self.assertRaisesRegex(TargetRuntimeError, "runops-seal-state"):
            ops.record_sealed(result("SEALED"))
        with self.assertRaisesRegex(TargetRuntimeError, "runops-source-close-state"):
            ops.close_source_identity()

        class FailingTarget:
            def close_identities(self): raise RuntimeError("close ambiguous")
        names = target_names(RUN_ID)
        ops._names = names
        ops._target = FailingTarget()
        with self.assertRaises(RuntimeError):
            ops.close_identities(names)
        self.assertTrue(ops._target_close_attempted)
        self.assertFalse(ops._target_closed)
        with self.assertRaisesRegex(TargetRuntimeError, "runops-target-close-state"):
            ops.close_identities(names)


class TargetMigrationRunnerTests(TestCase):
    EXPECTED_LEAVES = frozenset({
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("sessions", "0001_initial"),
        ("audit", "0001_initial"),
        ("accounts", "0001_initial"),
        ("media", "0001_initial"),
        ("pages", "0003_page_primary_url_mutable"),
        ("gallery", "0001_initial"),
        ("service_requests", "0001_initial"),
    })

    def run_case(
        self, root, *, leaves=None, applied=None, collision=False,
        fail_close=False, fail_delete=False, fail_pop=False,
    ):
        root = Path(root)
        os.chmod(root, 0o700)
        ca = root / "ca.pem"
        admin = root / "admin.secret"
        owner = root / f"{RUN_ID}.owner.secret"
        ca.write_text("certificate", encoding="utf-8")
        admin.write_text("admin-password", encoding="utf-8")
        owner.write_text("owner-password", encoding="utf-8")
        os.chmod(admin, 0o600)
        os.chmod(owner, 0o600)
        endpoint = TargetEndpoint(
            "db.example.test", 5432, ca, "foundation_admin", admin, root,
            (datetime.now(timezone.utc) + timedelta(minutes=10)).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
        )
        actual_leaves = self.EXPECTED_LEAVES if leaves is None else frozenset(leaves)
        actual_applied = self.EXPECTED_LEAVES if applied is None else frozenset(applied)
        alias = f"rb3_{RUN_ID.hex}"
        test_case = self

        class Databases(dict):
            def pop(self, key, default=None):
                if fail_pop and key == alias:
                    raise RuntimeError("pop failed")
                return super().pop(key, default)

        class Connection:
            def __init__(self, settings_dict):
                self.settings_dict = settings_dict
                self.closed = False

            def close(self):
                if fail_close:
                    raise RuntimeError("close failed")
                self.closed = True

        class Connections:
            def __init__(self):
                self.databases = Databases()
                self._connections = types.SimpleNamespace()

            def __getitem__(self, key):
                try:
                    return getattr(self._connections, key)
                except AttributeError:
                    value = Connection(self.databases[key])
                    test_case.last_connection = value
                    setattr(self._connections, key, value)
                    return value

            def __delitem__(self, key):
                if fail_delete:
                    raise RuntimeError("delete failed")
                delattr(self._connections, key)

        connections = Connections()
        self.last_connections = connections
        self.last_connection = None
        if collision:
            connections.databases[alias] = {"PASSWORD": "foreign"}
        migrated = []

        class Graph:
            def leaf_nodes(self): return tuple(actual_leaves)

        class Executor:
            def __init__(self, _connection):
                self.loader = types.SimpleNamespace(graph=Graph())

            def migrate(self, targets): migrated.append(tuple(targets))

        class Recorder:
            def __init__(self, _connection): pass
            def applied_migrations(self): return set(actual_applied)

        django_db = types.ModuleType("django.db")
        django_db.connections = connections
        executor_module = types.ModuleType("django.db.migrations.executor")
        executor_module.MigrationExecutor = Executor
        recorder_module = types.ModuleType("django.db.migrations.recorder")
        recorder_module.MigrationRecorder = Recorder
        modules = {
            "django.db": django_db,
            "django.db.migrations.executor": executor_module,
            "django.db.migrations.recorder": recorder_module,
        }
        with patch.dict(sys.modules, modules):
            run_target_migrations(endpoint, target_names(RUN_ID), owner)
        return connections, migrated

    def test_exact_leaves_generated_alias_and_cleanup(self):
        with tempfile.TemporaryDirectory() as raw:
            connections, migrated = self.run_case(raw)
        alias = f"rb3_{RUN_ID.hex}"
        self.assertNotIn(alias, connections.databases)
        self.assertFalse(hasattr(connections._connections, alias))
        self.assertEqual(migrated, [tuple(sorted(self.EXPECTED_LEAVES))])

    def test_leaf_apply_and_collision_fail_closed(self):
        cases = (
            ({*self.EXPECTED_LEAVES, ("pages", "9999_extra")}, None,
             "target-migration-leaves"),
            (self.EXPECTED_LEAVES - {("gallery", "0001_initial")}, None,
             "target-migration-leaves"),
            (self.EXPECTED_LEAVES,
             self.EXPECTED_LEAVES - {("gallery", "0001_initial")},
             "target-migration-apply"),
        )
        for leaves, applied, code in cases:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as raw:
                with self.assertRaisesRegex(TargetRuntimeError, code):
                    self.run_case(raw, leaves=leaves, applied=applied)
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaisesRegex(TargetRuntimeError, "target-migration-alias"):
                self.run_case(raw, collision=True)
            alias = f"rb3_{RUN_ID.hex}"
            self.assertEqual(
                self.last_connections.databases[alias]["PASSWORD"], "foreign",
            )

    def test_each_alias_cleanup_failure_is_ambiguous_and_password_is_scrubbed(self):
        for option in ("fail_close", "fail_delete", "fail_pop"):
            with self.subTest(option=option), tempfile.TemporaryDirectory() as raw:
                with self.assertRaisesRegex(
                    TargetRuntimeError, "target-migration-cleanup-ambiguous",
                ):
                    self.run_case(raw, **{option: True})
                self.assertIsNotNone(self.last_connection)
                self.assertEqual(self.last_connection.settings_dict["PASSWORD"], "")


class TargetMediaTransferTests(TestCase):
    PNG = b"\x89PNG\r\n\x1a\nfixed-test-payload"
    ASSET_ID = "00000000-0000-4000-8000-000000000201"
    FILE_ID = "00000000-0000-4000-8000-000000000202"

    def roots(self, raw):
        root = Path(raw)
        source = root / "source"
        target = root / "target"
        source.mkdir(mode=0o700)
        target.mkdir(mode=0o700)
        os.chmod(source, 0o700)
        os.chmod(target, 0o700)
        return source, target

    def manifest(
        self, *, source_path="logo.png", payload=None,
        mime_type="image/png", asset_id=None, file_id=None,
    ):
        payload = self.PNG if payload is None else payload
        digest = hashlib.sha256(payload).hexdigest()
        asset_id = self.ASSET_ID if asset_id is None else asset_id
        file_id = self.FILE_ID if file_id is None else file_id
        return PublicManifest(
            "snapshot-1", DIGEST, {},
            {"files": ({
                "id": file_id, "asset_id": asset_id,
                "kind": "MAIN", "source_path": source_path,
                "sha256": digest, "byte_size": len(payload),
                "mime_type": mime_type,
                "width": None if mime_type == "image/svg+xml" else 1,
                "height": None if mime_type == "image/svg+xml" else 1,
            },)},
        )

    @unittest.skipUnless(
        bool(getattr(os, "O_NOFOLLOW", 0) and getattr(os, "O_DIRECTORY", 0)),
        "secure dirfd primitives are required",
    )
    def test_same_open_source_copy_and_postcopy_readback_match(self):
        with tempfile.TemporaryDirectory() as raw:
            source, target = self.roots(raw)
            (source / "logo.png").write_bytes(self.PNG)
            manifest = self.manifest()
            transfer = MediaTransfer(source, target, frozenset())
            source_digest = transfer.preflight(manifest)
            names = target_names(RUN_ID)
            self.assertEqual(
                transfer.copy_and_verify(manifest, names), source_digest,
            )
            copied = target / str(RUN_ID) / "media" / "img" / self.ASSET_ID / "main.png"
            self.assertEqual(copied.read_bytes(), self.PNG)
            self.assertEqual(transfer.readback(manifest, names), source_digest)

    @unittest.skipUnless(
        bool(getattr(os, "O_NOFOLLOW", 0) and getattr(os, "O_DIRECTORY", 0)),
        "secure dirfd primitives are required",
    )
    def test_magic_drift_blocks_before_target_creation(self):
        with tempfile.TemporaryDirectory() as raw:
            source, target = self.roots(raw)
            payload = b"not-a-png"
            (source / "logo.png").write_bytes(payload)
            transfer = MediaTransfer(source, target, frozenset())
            with self.assertRaisesRegex(TargetRuntimeError, "media-source-drift"):
                transfer.preflight(self.manifest(payload=payload))
            self.assertEqual(tuple(target.iterdir()), ())

    @unittest.skipUnless(
        bool(getattr(os, "O_NOFOLLOW", 0) and getattr(os, "O_DIRECTORY", 0)),
        "secure dirfd primitives are required",
    )
    def test_size_cap_and_trusted_svg_boundary_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            source, target = self.roots(raw)
            (source / "logo.png").write_bytes(self.PNG + b"x")
            transfer = MediaTransfer(source, target, frozenset())
            with self.assertRaisesRegex(TargetRuntimeError, "media-size"):
                transfer.preflight(self.manifest())

        safe = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>'
        unsafe = b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>'
        for payload, trusted, accepted in (
            (safe, False, False), (safe, True, True), (unsafe, True, False),
        ):
            with self.subTest(trusted=trusted, accepted=accepted), tempfile.TemporaryDirectory() as raw:
                source, target = self.roots(raw)
                (source / "logo.svg").write_bytes(payload)
                digest = hashlib.sha256(payload).hexdigest()
                transfer = MediaTransfer(
                    source, target, frozenset({digest}) if trusted else frozenset(),
                )
                manifest = self.manifest(
                    source_path="logo.svg", payload=payload,
                    mime_type="image/svg+xml",
                )
                if accepted:
                    transfer.preflight(manifest)
                    transfer.close()
                else:
                    with self.assertRaisesRegex(TargetRuntimeError, "media-source-drift"):
                        transfer.preflight(manifest)

    @unittest.skipUnless(
        bool(getattr(os, "O_NOFOLLOW", 0) and getattr(os, "O_DIRECTORY", 0)),
        "secure dirfd primitives are required",
    )
    def test_duplicate_source_creates_two_keys_and_target_collision_refuses(self):
        second_asset = "00000000-0000-4000-8000-000000000203"
        second_file = "00000000-0000-4000-8000-000000000204"
        with tempfile.TemporaryDirectory() as raw:
            source, target = self.roots(raw)
            (source / "logo.png").write_bytes(self.PNG)
            first = self.manifest()
            second = self.manifest(asset_id=second_asset, file_id=second_file)
            manifest = PublicManifest(
                "snapshot-1", DIGEST, {},
                {"files": first.sections["files"] + second.sections["files"]},
            )
            transfer = MediaTransfer(source, target, frozenset())
            transfer.preflight(manifest)
            names = target_names(RUN_ID)
            transfer.copy_and_verify(manifest, names)
            media = target / str(RUN_ID) / "media" / "img"
            self.assertEqual((media / self.ASSET_ID / "main.png").read_bytes(), self.PNG)
            self.assertEqual((media / second_asset / "main.png").read_bytes(), self.PNG)

        with tempfile.TemporaryDirectory() as raw:
            source, target = self.roots(raw)
            (source / "logo.png").write_bytes(self.PNG)
            manifest = self.manifest()
            transfer = MediaTransfer(source, target, frozenset())
            transfer.preflight(manifest)
            (target / str(RUN_ID)).mkdir()
            with self.assertRaisesRegex(TargetRuntimeError, "media-copy-ambiguous"):
                transfer.copy_and_verify(manifest, target_names(RUN_ID))

    def test_descriptor_cleanup_attempts_all_after_first_failure(self):
        calls = []

        def close(descriptor):
            calls.append(descriptor)
            if descriptor == 10:
                raise OSError("close failed")

        with patch("rebuild3_importer.runtime_target.os.close", side_effect=close):
            self.assertTrue(_close_descriptors(10, 11, 12))
        self.assertEqual(calls, [10, 11, 12])

    def test_child_directory_reparse_and_cleanup_failure_are_closed(self):
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        info = types.SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o700, st_file_attributes=reparse,
        )
        with (
            patch("rebuild3_importer.runtime_target.os.open", return_value=20),
            patch("rebuild3_importer.runtime_target.os.fstat", return_value=info),
            patch("rebuild3_importer.runtime_target.os.close") as close,
        ):
            with self.assertRaisesRegex(TargetRuntimeError, "media-target-path"):
                _open_child_directory(10, "media", "media-target-path")
            close.assert_called_once_with(20)

        with (
            patch("rebuild3_importer.runtime_target.os.open", return_value=20),
            patch("rebuild3_importer.runtime_target.os.fstat", side_effect=OSError),
            patch("rebuild3_importer.runtime_target.os.close", side_effect=OSError),
        ):
            with self.assertRaisesRegex(
                TargetRuntimeError, "media-descriptor-cleanup-ambiguous",
            ):
                _open_child_directory(10, "media", "media-target-path")

    def test_root_and_init_cleanup_failures_are_constant_and_attempt_all(self):
        info = types.SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o700, st_dev=1, st_ino=1,
            st_file_attributes=0,
        )
        listed = types.SimpleNamespace(st_dev=1, st_ino=2)
        path = Path("/approved-root")
        with (
            patch("rebuild3_importer.runtime_target._trusted_directory", return_value=True),
            patch("rebuild3_importer.runtime_target.os.open", return_value=20),
            patch("rebuild3_importer.runtime_target.os.fstat", return_value=info),
            patch.object(Path, "lstat", return_value=listed),
            patch("rebuild3_importer.runtime_target.os.close", side_effect=OSError),
        ):
            with self.assertRaisesRegex(
                TargetRuntimeError, "media-descriptor-cleanup-ambiguous",
            ):
                _open_root(path, "media-source-root")

        calls = []
        def close(descriptor):
            calls.append(descriptor)
            if descriptor == 20:
                raise OSError("target close failed")
        with (
            patch("rebuild3_importer.runtime_target._open_root", side_effect=(10, 20)),
            patch("rebuild3_importer.runtime_target.os.close", side_effect=close),
        ):
            with self.assertRaisesRegex(
                TargetRuntimeError, "media-descriptor-cleanup-ambiguous",
            ):
                MediaTransfer(Path("/source"), Path("/target"), frozenset())
        self.assertEqual(calls, [20, 10])

    @unittest.skipUnless(
        bool(getattr(os, "O_NOFOLLOW", 0) and getattr(os, "O_DIRECTORY", 0)),
        "secure dirfd primitives are required",
    )
    def test_symlink_source_and_extra_target_inventory_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            source, target = self.roots(raw)
            outside = Path(raw) / "outside.png"
            outside.write_bytes(self.PNG)
            try:
                (source / "logo.png").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            transfer = MediaTransfer(source, target, frozenset())
            with self.assertRaises(TargetRuntimeError):
                transfer.preflight(self.manifest())

        with tempfile.TemporaryDirectory() as raw:
            source, target = self.roots(raw)
            (source / "logo.png").write_bytes(self.PNG)
            manifest = self.manifest()
            transfer = MediaTransfer(source, target, frozenset())
            transfer.preflight(manifest)
            names = target_names(RUN_ID)
            transfer.copy_and_verify(manifest, names)
            extra = target / str(RUN_ID) / "media" / "extra"
            extra.write_bytes(b"x")
            with self.assertRaisesRegex(TargetRuntimeError, "media-target-inventory"):
                transfer.readback(manifest, names)


if __name__ == "__main__":
    import unittest

    unittest.main()
