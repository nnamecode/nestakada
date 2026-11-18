import uuid
from unittest import TestCase

from rebuild3_importer.errors import SourceReadError
from rebuild3_importer.source import (
    PREFLIGHT_SQL,
    PRIVATE_BINDINGS_SQL,
    STAFF_SQL,
    SourceReader,
    SourceSession,
    TargetPageRef,
    VerifiedLedgerEvidence,
)


SNAPSHOT = "10:20:"
PID = 731
TXID = 991
DIGEST = "a" * 64
PAGE = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SOURCE_PAGE = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
PAGE_REF = TargetPageRef(PAGE, "service_detail")
STAFF = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


class FakeExecutor:
    def __init__(self, *, preflight=None, staff=(), bindings=(), private_pid=PID):
        self.staff = staff
        self.bindings = bindings
        grants = sum(row[0] == "grant" for row in bindings)
        current = sum(row[0] == "current" for row in bindings)
        previous = sum(row[0] == "previous" for row in bindings)
        self.preflight = preflight or (
            (PID, TXID, SNAPSHOT) + (0,) * 9 + (len(staff), grants, current, previous)
        )
        self.private_pid = private_pid
        self.calls = []

    def fetch_one(self, sql):
        self.calls.append(sql)
        return self.preflight

    def fetch_all(self, sql):
        self.calls.append(sql)
        rows = self.staff if sql == STAFF_SQL else self.bindings
        width = 5 if sql == STAFF_SQL else 6
        return (
            (0, self.private_pid, TXID, SNAPSHOT) + (None,) * width,
            *((1, self.private_pid, TXID, SNAPSHOT) + tuple(row) for row in rows),
        )


class FakeLedger:
    def __init__(self, evidence=None):
        self.evidence = evidence or VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, 0, SNAPSHOT)
        self.calls = []

    def latest_for(self, snapshot_id):
        self.calls.append(snapshot_id)
        return self.evidence


class SourceReaderTests(TestCase):
    def reader(self, executor, ledger=None, uuid_factory=lambda: STAFF, page=lambda key: PAGE_REF):
        return SourceReader(
            executor,
            SourceSession(PID, TXID, SNAPSHOT),
            ledger or FakeLedger(),
            page,
            uuid_factory=uuid_factory,
        )

    def test_queries_are_literal_and_exclude_credentials(self):
        combined = "\n".join((PREFLIGHT_SQL, STAFF_SQL, PRIVATE_BINDINGS_SQL)).lower()
        for forbidden in ("password", "email", "session", "token", "{", "%s"):
            self.assertNotIn(forbidden, combined)
        self.assertIn("repeatable", SourceReader.__doc__.lower())
        self.assertIn("current_user = 'estakada_rebuild_reader'", PREFLIGHT_SQL)
        self.assertIn("current_database() = 'estakada_foundation'", PREFLIGHT_SQL)
        self.assertIn("pg_stat_ssl", PREFLIGHT_SQL)

    def test_every_nonzero_aggregate_blocks_before_private_read(self):
        for position in range(3, 12):
            facts = [PID, TXID, SNAPSHOT] + [0] * 9 + [0] * 4
            facts[position] = 1
            executor = FakeExecutor(preflight=tuple(facts))
            reader = self.reader(executor)
            with self.assertRaisesRegex(SourceReadError, "pretarget-gate"):
                reader.preflight(SNAPSHOT)
            self.assertEqual(executor.calls, [PREFLIGHT_SQL])

    def test_private_read_requires_preflight_and_valid_zero_row_ledger(self):
        executor = FakeExecutor()
        reader = self.reader(executor)
        with self.assertRaisesRegex(SourceReadError, "source-state"):
            reader.read_private()
        self.assertEqual(executor.calls, [])
        bad = FakeLedger(VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, 1, SNAPSHOT))
        reader = self.reader(executor, bad)
        with self.assertRaisesRegex(SourceReadError, "ledger-evidence"):
            reader.preflight(SNAPSHOT)
        self.assertEqual(executor.calls, [PREFLIGHT_SQL])

    def test_malformed_ledger_evidence_fails_closed(self):
        cases = (
            VerifiedLedgerEvidence(uuid.UUID(int=0), 1, DIGEST, 0, SNAPSHOT),
            VerifiedLedgerEvidence(uuid.uuid4(), True, DIGEST, 0, SNAPSHOT),
            VerifiedLedgerEvidence(uuid.uuid4(), 1, "A" * 64, 0, SNAPSHOT),
            VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, False, SNAPSHOT),
            VerifiedLedgerEvidence(uuid.uuid4(), 1, DIGEST, 0, "11:20:"),
        )
        for evidence in cases:
            reader = self.reader(FakeExecutor(), FakeLedger(evidence))
            with self.assertRaisesRegex(SourceReadError, "ledger-evidence"):
                reader.preflight(SNAPSHOT)

    def test_session_drift_and_raw_exceptions_fail_closed(self):
        preflight_drift = self.reader(
            FakeExecutor(preflight=(PID + 1, TXID, SNAPSHOT) + (0,) * 9 + (0,) * 4)
        )
        with self.assertRaisesRegex(SourceReadError, "source-session-drift"):
            preflight_drift.preflight(SNAPSHOT)
        private_drift = self.reader(FakeExecutor(private_pid=PID + 1))
        private_drift.preflight(SNAPSHOT)
        with self.assertRaisesRegex(SourceReadError, "source-session-drift"):
            private_drift.read_private()

        class LeakingExecutor(FakeExecutor):
            def fetch_one(self, sql):
                raise RuntimeError("private-user-77")

        leaking = self.reader(LeakingExecutor())
        with self.assertRaisesRegex(SourceReadError, "source-preflight") as caught:
            leaking.preflight(SNAPSHOT)
        self.assertNotIn("private-user", str(caught.exception))

    def test_staff_grant_and_provenance_use_same_private_map(self):
        executor = FakeExecutor(
            staff=((7, "employee", True, "employee", 3),),
            bindings=(
                ("grant", SOURCE_PAGE, 7, True, False, True),
                ("current", SOURCE_PAGE, 7, False, False, False),
                ("previous", SOURCE_PAGE, 7, False, False, False),
            ),
        )
        reader = self.reader(executor)
        preflight = reader.preflight(SNAPSHOT)
        rows = reader.read_private()
        self.assertEqual(preflight.ledger.row_count, 0)
        self.assertEqual(
            (
                preflight.staff_count,
                preflight.grant_count,
                preflight.current_count,
                preflight.previous_count,
            ),
            (1, 1, 1, 1),
        )
        self.assertEqual(rows.staff[0].id, STAFF)
        self.assertEqual(rows.staff[0].role, "EMPLOYEE")
        self.assertEqual(rows.grants[0].groups, ("text", "prices"))
        self.assertEqual(rows.grants[0].staff_id, STAFF)
        self.assertEqual({row.staff_id for row in rows.provenance}, {STAFF})
        self.assertEqual(executor.calls, [PREFLIGHT_SQL, STAFF_SQL, PRIVATE_BINDINGS_SQL])
        with self.assertRaisesRegex(SourceReadError, "source-state"):
            reader.read_private()
        for value in (rows.staff[0], rows.grants[0], rows.provenance[0], rows):
            self.assertNotIn("employee", repr(value))
            self.assertNotIn("source_key", repr(value))

    def test_unmapped_duplicate_and_non_v4_staff_fail_closed(self):
        cases = (
            (FakeExecutor(staff=((7, "a", True, "employee", 1),), bindings=(("current", SOURCE_PAGE, 8, False, False, False),)), lambda: STAFF, "staff-unmapped"),
            (FakeExecutor(staff=((7, "a", True, "employee", 1), (7, "b", True, "employee", 1))), uuid.uuid4, "staff-map-duplicate"),
            (FakeExecutor(staff=((7, "a", True, "employee", 1),)), lambda: uuid.UUID(int=0), "staff-uuid"),
        )
        for executor, factory, code in cases:
            reader = self.reader(executor, uuid_factory=factory)
            reader.preflight(SNAPSHOT)
            with self.assertRaisesRegex(SourceReadError, code):
                reader.read_private()
            with self.assertRaisesRegex(SourceReadError, "source-state"):
                reader.read_private()

    def test_unmapped_page_and_duplicate_binding_fail_closed(self):
        base = ((7, "a", True, "employee", 1),)
        cases = (
            (FakeExecutor(staff=base, bindings=(("current", SOURCE_PAGE, 7, False, False, False),)), lambda key: (_ for _ in ()).throw(KeyError(key))),
            (FakeExecutor(staff=base, bindings=(("current", SOURCE_PAGE, 7, False, False, False), ("current", SOURCE_PAGE, 7, False, False, False))), lambda key: PAGE_REF),
        )
        for executor, resolver in cases:
            reader = self.reader(executor, page=resolver)
            reader.preflight(SNAPSHOT)
            with self.assertRaises(SourceReadError):
                reader.read_private()

    def test_grant_groups_must_match_target_page_kind(self):
        cases = (
            ("article", (False, False, True)),
            ("home", (True, False, False)),
            ("service_section_overview", (False, False, True)),
        )
        for page_kind, flags in cases:
            executor = FakeExecutor(
                staff=((7, "a", True, "employee", 1),),
                bindings=(("grant", SOURCE_PAGE, 7, *flags),),
            )
            reader = self.reader(executor, page=lambda key, kind=page_kind: TargetPageRef(PAGE, kind))
            reader.preflight(SNAPSHOT)
            with self.assertRaisesRegex(SourceReadError, "grant-groups"):
                reader.read_private()

        owner = FakeExecutor(
            staff=((7, "nesadmin", True, "owner", 1),),
            bindings=(("grant", SOURCE_PAGE, 7, True, False, False),),
        )
        reader = self.reader(owner)
        reader.preflight(SNAPSHOT)
        with self.assertRaisesRegex(SourceReadError, "grant-row"):
            reader.read_private()

    def test_preflight_sql_checks_closed_source_grant_matrix(self):
        self.assertIn("service_wash_legacy_alias", PREFLIGHT_SQL)
        self.assertIn("legacy_news_article", PREFLIGHT_SQL)
        self.assertIn("g.price AND p.kind NOT IN", PREFLIGHT_SQL)
        self.assertIn("NULL::uuid, NULL::bigint", PRIVATE_BINDINGS_SQL)
        self.assertIn("p.role <> 'employee' OR NOT u.is_active", PREFLIGHT_SQL)
        self.assertIn(
            "SELECT count(id) AS value FROM app.service_requests_servicerequest",
            PREFLIGHT_SQL,
        )
        self.assertEqual(PREFLIGHT_SQL.count("app.service_requests_servicerequest"), 1)

    def test_private_rows_are_preflight_bounded_and_exact_counted(self):
        over_cap = (PID, TXID, SNAPSHOT) + (0,) * 9 + (65, 0, 0, 0)
        reader = self.reader(FakeExecutor(preflight=over_cap))
        with self.assertRaisesRegex(SourceReadError, "private-cap"):
            reader.preflight(SNAPSHOT)

        mismatch = FakeExecutor(
            preflight=(PID, TXID, SNAPSHOT) + (0,) * 9 + (1, 0, 0, 0),
            staff=(),
        )
        reader = self.reader(mismatch)
        reader.preflight(SNAPSHOT)
        with self.assertRaisesRegex(SourceReadError, "staff-count"):
            reader.read_private()

    def test_close_erases_map_and_blocks_reuse(self):
        executor = FakeExecutor(staff=((7, "a", True, "employee", 1),))
        reader = self.reader(executor)
        reader.preflight(SNAPSHOT)
        reader.read_private()
        reader.close()
        self.assertEqual(repr(reader), "<SourceReader state=closed>")
        with self.assertRaisesRegex(SourceReadError, "source-state"):
            reader.preflight(SNAPSHOT)
