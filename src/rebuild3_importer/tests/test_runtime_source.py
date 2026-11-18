import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from rebuild3_importer import freeze_authority, media_authority
from rebuild3_importer.runtime_source import (
    GRANT_SOURCE_SQL,
    REVOKE_SOURCE_SQL,
    CREATE_SOURCE_ROLE_SQL,
    SOURCE_DATABASE,
    SOURCE_PRIVILEGE_PROOF_SQL,
    SOURCE_ROLE,
    SOURCE_ROLE_IDENTITY_SQL,
    SOURCE_SESSION_SQL,
    SOURCE_TABLES,
    capture_run_authority,
    open_source_bound,
    ProvidedLedgerVerifier,
    PsycopgSourceExecutor,
    SourceEndpoint,
    SourceLifecycle,
    SourceRuntimeError,
)
from rebuild3_importer.source import VerifiedLedgerEvidence


SNAPSHOT = "10:20:"
DIGEST = "a" * 64


class Cursor:
    def __init__(self):
        self.sql = []
        self.rows = [(1,)]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.sql.append((sql, params))

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self):
        self.value = Cursor()

    def cursor(self):
        return self.value


class RuntimeSourceTests(TestCase):
    def test_executor_is_one_literal_connection_adapter(self):
        connection = Connection()
        executor = PsycopgSourceExecutor(connection)
        self.assertEqual(tuple(executor.fetch_one("SELECT one")), (1,))
        self.assertEqual(tuple(executor.fetch_all("SELECT all")), ((1,),))
        self.assertEqual(
            connection.value.sql,
            [("SELECT one", None), ("SELECT all", None)],
        )
        executor.close()

    def test_provided_ledger_is_memory_only_snapshot_bound_and_one_shot(self):
        evidence = VerifiedLedgerEvidence(uuid.uuid4(), 3, DIGEST, 0, SNAPSHOT)
        verifier = ProvidedLedgerVerifier(evidence)
        self.assertIs(verifier.latest_for(SNAPSHOT), evidence)
        with self.assertRaisesRegex(SourceRuntimeError, "ledger-snapshot"):
            verifier.latest_for(SNAPSHOT)
        with self.assertRaisesRegex(SourceRuntimeError, "ledger-snapshot"):
            ProvidedLedgerVerifier(evidence).latest_for("11:20:")

    def test_source_role_and_privileges_are_literal_and_closed(self):
        self.assertEqual(SOURCE_DATABASE, "estakada_foundation")
        self.assertEqual(SOURCE_ROLE, "estakada_rebuild_reader")
        self.assertEqual(len(SOURCE_TABLES), 14)
        grant = "\n".join(GRANT_SOURCE_SQL)
        revoke = "\n".join(REVOKE_SOURCE_SQL)
        for table in SOURCE_TABLES:
            self.assertIn(f"app.{table}", grant)
            self.assertIn(f"app.{table}", revoke)
        self.assertIn("SELECT (id) ON TABLE app.service_requests_servicerequest", grant)
        self.assertNotIn("SELECT ON TABLE app.service_requests_servicerequest", grant)
        self.assertIn("a.attname = 'id'", SOURCE_PRIVILEGE_PROOF_SQL)
        self.assertIn("rolsuper", SOURCE_PRIVILEGE_PROOF_SQL)
        self.assertIn("pg_auth_members", SOURCE_PRIVILEGE_PROOF_SQL)
        self.assertIn("has_sequence_privilege", SOURCE_PRIVILEGE_PROOF_SQL)
        self.assertIn("'TEMP'", SOURCE_PRIVILEGE_PROOF_SQL)
        self.assertIn("'CREATE'", SOURCE_PRIVILEGE_PROOF_SQL)
        self.assertIn("'TRIGGER'", SOURCE_PRIVILEGE_PROOF_SQL)
        self.assertNotIn("NOT IN ('estakada_foundation', 'template0'", SOURCE_PRIVILEGE_PROOF_SQL)

    def endpoint(self, root: Path):
        ca = root / "ca.pem"
        admin = root / "admin.secret"
        ca.write_text("certificate", encoding="utf-8")
        admin.write_text("admin-password", encoding="utf-8")
        os.chmod(admin, 0o600)
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=10)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        return SourceEndpoint(
            "db.example.test", 5432, ca, "foundation_admin", admin,
            root / "reader.secret", expiry,
        )

    def connector(
        self, *, create_lost=False, role_collision=False, oid_drift=False,
        expiry_drift=False, snapshot=SNAPSHOT,
    ):
        class CollisionError(RuntimeError):
            sqlstate = "42710"

        class FakeCursor:
            def __init__(self, connection):
                self.connection = connection
                self.last = None

            def __enter__(self): return self
            def __exit__(self, *_args): return False

            def execute(self, sql, params=None):
                self.last = sql
                self.connection.calls.append((sql, params))
                if sql == CREATE_SOURCE_ROLE_SQL and params is not None:
                    self.connection.expiry = params[1]
                if role_collision and sql == CREATE_SOURCE_ROLE_SQL:
                    raise CollisionError("duplicate role")
                if create_lost and sql == CREATE_SOURCE_ROLE_SQL:
                    raise RuntimeError("lost response")

            def fetchone(self):
                if self.last == SOURCE_PRIVILEGE_PROOF_SQL:
                    return (0,)
                if self.last == SOURCE_SESSION_SQL:
                    return (731, 991, snapshot)
                if self.last == SOURCE_ROLE_IDENTITY_SQL:
                    self.connection.oid_reads += 1
                    return (
                        901,
                        "2000-01-01T00:00:00.000000Z"
                        if expiry_drift else self.connection.expiry,
                    )
                if "SELECT oid FROM pg_roles" in self.last:
                    self.connection.oid_reads += 1
                    if oid_drift and self.connection.oid_reads > 1:
                        return (902,)
                    return (901,)
                if "pg_stat_activity" in self.last:
                    return (0,)
                raise AssertionError(self.last)

        class FakeConnection:
            def __init__(self):
                self.calls = []
                self.oid_reads = 0
                self.expiry = None
                self.closed = False

            def cursor(self): return FakeCursor(self)
            def close(self): self.closed = True

        connections = []

        def connect(**_kwargs):
            value = FakeConnection()
            connections.append(value)
            return value

        return connect, connections

    def test_lifecycle_success_removes_only_its_exact_secret(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, connections = self.connector()
            evidence = VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, 0, SNAPSHOT)
            opened = SourceLifecycle.open(endpoint, evidence, connect=connect)
            self.assertTrue(endpoint.reader_secret_file.exists())
            opened.lifecycle.close()
            self.assertFalse(endpoint.reader_secret_file.exists())
            self.assertTrue(all(value.closed for value in connections))

    def test_snapshot_binder_receives_only_fresh_id_and_returns_one_shot(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, connections = self.connector()
            evidence = VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, 0, SNAPSHOT)
            binder = Mock(return_value=evidence)
            opened = open_source_bound(endpoint, binder, connect=connect)
            binder.assert_called_once_with(SNAPSHOT)
            self.assertIs(opened.ledger.latest_for(SNAPSHOT), evidence)
            with self.assertRaisesRegex(SourceRuntimeError, "ledger-snapshot"):
                opened.ledger.latest_for(SNAPSHOT)
            opened.lifecycle.close()
            self.assertFalse(endpoint.reader_secret_file.exists())
            self.assertTrue(all(connection.closed for connection in connections))

    def test_snapshot_binder_rejects_every_malformed_evidence_with_cleanup(self):
        identity = uuid.uuid4()
        malformed = (
            object(),
            VerifiedLedgerEvidence(uuid.UUID(int=0), 1, DIGEST, 0, SNAPSHOT),
            VerifiedLedgerEvidence(identity, True, DIGEST, 0, SNAPSHOT),
            VerifiedLedgerEvidence(identity, 0, DIGEST, 0, SNAPSHOT),
            VerifiedLedgerEvidence(identity, 1, DIGEST.upper(), 0, SNAPSHOT),
            VerifiedLedgerEvidence(identity, 1, "1" * 63, 0, SNAPSHOT),
            VerifiedLedgerEvidence(identity, 1, DIGEST, True, SNAPSHOT),
            VerifiedLedgerEvidence(identity, 1, DIGEST, 1, SNAPSHOT),
            VerifiedLedgerEvidence(identity, 1, DIGEST, 0, "11:20:"),
        )
        for evidence in malformed:
            with self.subTest(evidence=repr(evidence)), tempfile.TemporaryDirectory() as raw:
                endpoint = self.endpoint(Path(raw))
                connect, connections = self.connector()
                with self.assertRaisesRegex(SourceRuntimeError, "ledger-evidence"):
                    open_source_bound(endpoint, lambda _snapshot: evidence, connect=connect)
                self.assertFalse(endpoint.reader_secret_file.exists())
                self.assertTrue(all(connection.closed for connection in connections))

    def test_snapshot_binder_noncallable_fails_before_connect(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, connections = self.connector()
            with self.assertRaisesRegex(SourceRuntimeError, "ledger-binder"):
                open_source_bound(endpoint, object(), connect=connect)
            self.assertFalse(endpoint.reader_secret_file.exists())
            self.assertEqual(connections, [])

    def test_snapshot_binder_never_receives_malformed_source_snapshot(self):
        for snapshot in (None, "bad"):
            with self.subTest(snapshot=snapshot), tempfile.TemporaryDirectory() as raw:
                endpoint = self.endpoint(Path(raw))
                connect, connections = self.connector(snapshot=snapshot)
                binder = Mock(return_value=object())
                with self.assertRaisesRegex(SourceRuntimeError, "source-session"):
                    open_source_bound(endpoint, binder, connect=connect)
                binder.assert_not_called()
                self.assertFalse(endpoint.reader_secret_file.exists())
                self.assertTrue(all(connection.closed for connection in connections))

    def test_snapshot_binder_base_exception_cleans_and_re_raises(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, connections = self.connector()

            def interrupt(_snapshot):
                raise KeyboardInterrupt()

            with self.assertRaises(KeyboardInterrupt):
                open_source_bound(endpoint, interrupt, connect=connect)
            self.assertFalse(endpoint.reader_secret_file.exists())
            self.assertTrue(all(connection.closed for connection in connections))

    def test_snapshot_binder_cleanup_ambiguity_is_constant(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, connections = self.connector()
            with patch.object(
                SourceLifecycle,
                "_drop",
                side_effect=KeyboardInterrupt(),
            ):
                with self.assertRaisesRegex(
                    SourceRuntimeError,
                    "source-bind-cleanup-ambiguous",
                ):
                    open_source_bound(endpoint, lambda _snapshot: object(), connect=connect)
            self.assertTrue(all(connection.closed for connection in connections))
            self.assertTrue(endpoint.reader_secret_file.exists())

    def test_capture_closes_db_before_compose_and_returns_no_db_object(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, connections = self.connector()
            capture = object()
            package = object()
            limits = object()

            def compose(value):
                self.assertIs(value, capture)
                self.assertFalse(endpoint.reader_secret_file.exists())
                self.assertTrue(all(connection.closed for connection in connections))
                return package, limits, DIGEST

            with (
                patch.object(
                    freeze_authority,
                    "capture_source_authority",
                    return_value=capture,
                ) as capture_call,
                patch.object(
                    media_authority,
                    "compose_run_authority",
                    side_effect=compose,
                ) as compose_call,
            ):
                result = capture_run_authority(endpoint, connect=connect)
            self.assertEqual(result, (package, limits, DIGEST))
            self.assertEqual(capture_call.call_count, 1)
            self.assertEqual(compose_call.call_count, 1)
            executor, session = capture_call.call_args.args
            self.assertIsInstance(executor, PsycopgSourceExecutor)
            self.assertEqual(session.snapshot_id, SNAPSHOT)

    def test_capture_failure_closes_lifecycle_and_never_composes(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, connections = self.connector()
            with (
                patch.object(
                    freeze_authority,
                    "capture_source_authority",
                    side_effect=RuntimeError("synthetic"),
                ),
                patch.object(
                    media_authority,
                    "compose_run_authority",
                ) as compose,
            ):
                with self.assertRaisesRegex(RuntimeError, "synthetic"):
                    capture_run_authority(endpoint, connect=connect)
            compose.assert_not_called()
            self.assertFalse(endpoint.reader_secret_file.exists())
            self.assertTrue(all(connection.closed for connection in connections))

    def test_capture_base_exception_cleans_everything_and_re_raises(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, connections = self.connector()
            with (
                patch.object(
                    freeze_authority,
                    "capture_source_authority",
                    side_effect=KeyboardInterrupt(),
                ),
                patch.object(
                    media_authority,
                    "compose_run_authority",
                ) as compose,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    capture_run_authority(endpoint, connect=connect)
            compose.assert_not_called()
            self.assertFalse(endpoint.reader_secret_file.exists())
            self.assertTrue(all(connection.closed for connection in connections))

    def test_capture_cleanup_base_exception_attempts_remaining_steps(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, connections = self.connector()
            with (
                patch.object(
                    freeze_authority,
                    "capture_source_authority",
                    return_value=object(),
                ),
                patch.object(
                    SourceLifecycle,
                    "_drop",
                    side_effect=KeyboardInterrupt(),
                ),
                patch.object(
                    media_authority,
                    "compose_run_authority",
                ) as compose,
            ):
                with self.assertRaisesRegex(
                    SourceRuntimeError,
                    "capture-close-ambiguous",
                ):
                    capture_run_authority(endpoint, connect=connect)
            compose.assert_not_called()
            self.assertTrue(all(connection.closed for connection in connections))
            self.assertTrue(endpoint.reader_secret_file.exists())

    def test_capture_secret_write_base_exception_cleans_before_connect(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, connections = self.connector()
            with patch.object(os, "fsync", side_effect=KeyboardInterrupt()):
                with self.assertRaises(KeyboardInterrupt):
                    capture_run_authority(endpoint, connect=connect)
            self.assertFalse(endpoint.reader_secret_file.exists())
            self.assertEqual(connections, [])

    def test_capture_close_ambiguity_blocks_composition(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, _connections = self.connector(oid_drift=True)
            with (
                patch.object(
                    freeze_authority,
                    "capture_source_authority",
                    return_value=object(),
                ),
                patch.object(
                    media_authority,
                    "compose_run_authority",
                ) as compose,
            ):
                with self.assertRaisesRegex(
                    SourceRuntimeError,
                    "capture-close-ambiguous",
                ):
                    capture_run_authority(endpoint, connect=connect)
            compose.assert_not_called()
            self.assertTrue(endpoint.reader_secret_file.exists())

    def test_foreign_secret_survives_collision_and_create_lost_response_is_isolated(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            endpoint.reader_secret_file.write_text("foreign", encoding="utf-8")
            connect, _connections = self.connector()
            evidence = VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, 0, SNAPSHOT)
            with self.assertRaisesRegex(SourceRuntimeError, "reader-secret-target"):
                SourceLifecycle.open(endpoint, evidence, connect=connect)
            self.assertEqual(endpoint.reader_secret_file.read_text(encoding="utf-8"), "foreign")

        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, _connections = self.connector(create_lost=True)
            evidence = VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, 0, SNAPSHOT)
            with self.assertRaisesRegex(SourceRuntimeError, "source-role-create-ambiguous"):
                SourceLifecycle.open(endpoint, evidence, connect=connect)
            self.assertTrue(endpoint.reader_secret_file.exists())

        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, _connections = self.connector(role_collision=True)
            evidence = VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, 0, SNAPSHOT)
            with self.assertRaisesRegex(SourceRuntimeError, "source-role-collision"):
                SourceLifecycle.open(endpoint, evidence, connect=connect)
            self.assertFalse(endpoint.reader_secret_file.exists())

    def test_oid_drift_blocks_drop_and_preserves_owned_secret(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, _connections = self.connector(oid_drift=True)
            evidence = VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, 0, SNAPSHOT)
            opened = SourceLifecycle.open(endpoint, evidence, connect=connect)
            with self.assertRaisesRegex(SourceRuntimeError, "source-close-ambiguous"):
                opened.lifecycle.close()
            self.assertTrue(endpoint.reader_secret_file.exists())

    def test_expiry_readback_mismatch_drops_exact_role_and_secret(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, connections = self.connector(expiry_drift=True)
            evidence = VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, 0, SNAPSHOT)
            with self.assertRaisesRegex(SourceRuntimeError, "source-role-expiry"):
                SourceLifecycle.open(endpoint, evidence, connect=connect)
            self.assertFalse(endpoint.reader_secret_file.exists())
            self.assertTrue(all(value.closed for value in connections))

    def test_no_follow_and_untrusted_parent_fail_before_write_or_connect(self):
        with tempfile.TemporaryDirectory() as raw:
            endpoint = self.endpoint(Path(raw))
            connect, connections = self.connector()
            evidence = VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, 0, SNAPSHOT)
            with patch.object(os, "O_NOFOLLOW", 0, create=True):
                with self.assertRaisesRegex(SourceRuntimeError, "source-endpoint"):
                    SourceLifecycle.open(endpoint, evidence, connect=connect)
            self.assertFalse(endpoint.reader_secret_file.exists())
            self.assertEqual(connections, [])

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            endpoint = self.endpoint(root)
            connect, connections = self.connector()
            evidence = VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, 0, SNAPSHOT)
            os.chmod(root, 0o755)
            try:
                with self.assertRaisesRegex(SourceRuntimeError, "source-endpoint"):
                    SourceLifecycle.open(endpoint, evidence, connect=connect)
            finally:
                os.chmod(root, 0o700)
            self.assertFalse(endpoint.reader_secret_file.exists())
            self.assertEqual(connections, [])

    def test_unbounded_expiry_fails_before_secret_or_connection(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            endpoint = self.endpoint(root)
            endpoint = SourceEndpoint(
                endpoint.host, endpoint.port, endpoint.sslrootcert, endpoint.admin_user,
                endpoint.admin_secret_file, endpoint.reader_secret_file,
                (datetime.now(timezone.utc) + timedelta(hours=2)).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                ),
            )
            connect, connections = self.connector()
            evidence = VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, 0, SNAPSHOT)
            with self.assertRaisesRegex(SourceRuntimeError, "source-endpoint"):
                SourceLifecycle.open(endpoint, evidence, connect=connect)
            self.assertFalse(endpoint.reader_secret_file.exists())
            self.assertEqual(connections, [])


if __name__ == "__main__":
    import unittest

    unittest.main()
