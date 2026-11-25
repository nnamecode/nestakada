from __future__ import annotations

import json
import os
import stat
import tempfile
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from modules.service_requests.ledger import (
    DisabledIndependentLedger,
    LedgerError,
    LedgerReason,
    LedgerState,
    PrimaryLedger,
    IndependentReceipt,
    SyntheticIndependentLedger,
    assess_ledger_state,
)


REQUEST_ID = uuid.UUID("12345678-1234-4abc-8def-1234567890ab")
DELETED_AT = datetime(2026, 11, 25, 8, 30, 0, 123456, tzinfo=UTC)


class PrimaryLedgerTests(SimpleTestCase):
    def test_append_is_canonical_chained_and_durable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = PrimaryLedger(Path(directory))
            sync_modes = []
            real_fsync = os.fsync

            def tracked_fsync(descriptor):
                sync_modes.append(stat.S_IFMT(os.fstat(descriptor).st_mode))
                return real_fsync(descriptor)

            with patch("modules.service_requests.ledger.os.fsync", side_effect=tracked_fsync):
                with ledger.locked() as session:
                    empty = session.snapshot()
                    self.assertEqual((empty.generation, empty.records), (0, ()))
                    first = session.append(((REQUEST_ID, DELETED_AT, LedgerReason.OWNER),))
                    second = session.append(
                        ((uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), DELETED_AT, LedgerReason.RETENTION),)
                    )
            self.assertEqual(
                sync_modes,
                [
                    stat.S_IFREG,
                    stat.S_IFDIR,
                    stat.S_IFREG,
                    stat.S_IFDIR,
                    stat.S_IFREG,
                    stat.S_IFDIR,
                ],
            )
            self.assertEqual(second.generation, 2)
            self.assertEqual(second.records[0].sequence, 1)
            self.assertEqual(second.records[0].previous_hash, "0" * 64)
            self.assertEqual(second.records[1].previous_hash, second.records[0].row_hash)
            raw = (Path(directory) / "service-request-deletions.jsonl").read_bytes()
            self.assertTrue(raw.endswith(b"\n"))
            lines = raw.splitlines()
            self.assertEqual(len(lines), 2)
            parsed = json.loads(lines[0])
            self.assertEqual(
                tuple(parsed),
                ("deleted_at", "previous_hash", "reason", "request_id", "row_hash", "sequence"),
            )
            self.assertEqual(parsed["deleted_at"], "2026-11-25T08:30:00.123456Z")
            with ledger.locked() as session:
                self.assertEqual(session.snapshot(), second)

    def test_corruption_extra_fields_and_noncanonical_rows_fail_closed(self) -> None:
        mutations = (
            lambda row: row.__setitem__("reason", "UNKNOWN"),
            lambda row: row.__setitem__("extra", True),
            lambda row: row.__setitem__("request_id", str(REQUEST_ID).upper()),
            lambda row: row.__setitem__("sequence", 2),
            lambda row: row.__setitem__("row_hash", "f" * 64),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                ledger = PrimaryLedger(Path(directory))
                with ledger.locked() as session:
                    session.append(((REQUEST_ID, DELETED_AT, LedgerReason.OWNER),))
                path = Path(directory) / "service-request-deletions.jsonl"
                row = json.loads(path.read_bytes())
                mutate(row)
                path.write_text(
                    json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
                with ledger.locked() as session, self.assertRaises(LedgerError):
                    session.snapshot()

    def test_duplicate_tombstone_is_rejected_before_write_and_during_parse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = PrimaryLedger(Path(directory))
            with ledger.locked() as session:
                with self.assertRaises(LedgerError):
                    session.append(
                        (
                            (REQUEST_ID, DELETED_AT, LedgerReason.OWNER),
                            (REQUEST_ID, DELETED_AT, LedgerReason.RETENTION),
                        )
                    )
                self.assertEqual(session.snapshot().generation, 0)
                first = session.append(((REQUEST_ID, DELETED_AT, LedgerReason.OWNER),))
                with self.assertRaises(LedgerError):
                    session.append(((REQUEST_ID, DELETED_AT, LedgerReason.OWNER),))
                self.assertEqual(session.snapshot(), first)
            path = Path(directory) / "service-request-deletions.jsonl"
            path.write_bytes(first.payload + first.payload)
            with ledger.locked() as session, self.assertRaises(LedgerError):
                session.snapshot()

    def test_symlink_and_nonexclusive_lock_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.write_bytes(b"")
            (root / "service-request-deletions.jsonl").symlink_to(target)
            with self.assertRaises(LedgerError), PrimaryLedger(root).locked():
                pass

        with tempfile.TemporaryDirectory() as directory:
            ledger = PrimaryLedger(Path(directory))
            entered = threading.Event()
            release = threading.Event()

            def holder() -> None:
                with ledger.locked():
                    entered.set()
                    release.wait(timeout=5)

            thread = threading.Thread(target=holder)
            thread.start()
            self.assertTrue(entered.wait(timeout=2))
            try:
                with self.assertRaises(LedgerError), ledger.locked():
                    pass
            finally:
                release.set()
                thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def test_insecure_modes_and_hardlinks_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            os.chmod(root, 0o755)
            with self.assertRaises(LedgerError), PrimaryLedger(root).locked():
                pass
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = PrimaryLedger(root)
            with ledger.locked():
                pass
            os.chmod(root / "service-request-deletions.jsonl", 0o640)
            with self.assertRaises(LedgerError), ledger.locked():
                pass
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = PrimaryLedger(root)
            with ledger.locked():
                pass
            os.link(
                root / "service-request-deletions.jsonl",
                root / "service-request-deletions-copy",
            )
            with self.assertRaises(LedgerError), ledger.locked():
                pass

    def test_independent_receipt_must_match_exact_generation_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = PrimaryLedger(Path(directory))
            independent = SyntheticIndependentLedger()
            with ledger.locked() as session:
                empty = session.snapshot()
                self.assertEqual(
                    assess_ledger_state(empty, None, (), ()),
                    LedgerState.PRIMARY_PENDING,
                )
                receipt = independent.publish_and_verify(empty)
                self.assertEqual(
                    assess_ledger_state(empty, receipt, (), ()),
                    LedgerState.PROJECTED,
                )
                first = session.append(((REQUEST_ID, DELETED_AT, LedgerReason.OWNER),))
                self.assertEqual(
                    assess_ledger_state(first, receipt, (), (REQUEST_ID,)),
                    LedgerState.PRIMARY_PENDING,
                )
                verified = independent.publish_and_verify(first)
                self.assertEqual(
                    assess_ledger_state(first, verified, (), (REQUEST_ID,)),
                    LedgerState.INDEPENDENT_VERIFIED,
                )
                self.assertEqual(
                    assess_ledger_state(first, verified, ((1, REQUEST_ID),), ()),
                    LedgerState.PROJECTED,
                )
                self.assertEqual(
                    assess_ledger_state(first, verified, ((1, REQUEST_ID),), (REQUEST_ID,)),
                    LedgerState.INDEPENDENT_VERIFIED,
                )
            self.assertIsNone(DisabledIndependentLedger().publish_and_verify(first))

    def test_ambiguous_receipt_projection_matrix_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = PrimaryLedger(Path(directory))
            with ledger.locked() as session:
                empty = session.snapshot()
                first = session.append(((REQUEST_ID, DELETED_AT, LedgerReason.OWNER),))
            empty_receipt = IndependentReceipt(0, empty.digest)
            with self.assertRaises(LedgerError):
                assess_ledger_state(first, None, ((1, REQUEST_ID),), ())
            with self.assertRaises(LedgerError):
                assess_ledger_state(first, empty_receipt, ((1, REQUEST_ID),), ())
            with self.assertRaises(LedgerError):
                assess_ledger_state(first, IndependentReceipt(1, "f" * 64), (), (REQUEST_ID,))
            with self.assertRaises(LedgerError):
                assess_ledger_state(first, IndependentReceipt(2, first.digest), (), (REQUEST_ID,))
            for generation, digest in (
                (True, first.digest),
                ("1", first.digest),
                (-1, first.digest),
                (1, "F" * 64),
                (1, "f" * 65),
            ):
                with self.subTest(generation=generation, digest=digest), self.assertRaises(LedgerError):
                    assess_ledger_state(
                        first,
                        IndependentReceipt(generation, digest),  # type: ignore[arg-type]
                        (),
                        (REQUEST_ID,),
                    )
            for malformed in (object(), {"generation": 1}, (1, first.digest)):
                with self.subTest(malformed=malformed), self.assertRaises(LedgerError):
                    assess_ledger_state(first, malformed, (), (REQUEST_ID,))  # type: ignore[arg-type]
            with self.assertRaises(LedgerError):
                assess_ledger_state(first, None, (), ([REQUEST_ID],))  # type: ignore[list-item]

    def test_older_receipt_requires_fully_projected_live_free_prefix(self) -> None:
        second_id = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        with tempfile.TemporaryDirectory() as directory:
            ledger = PrimaryLedger(Path(directory))
            with ledger.locked() as session:
                first = session.append(((REQUEST_ID, DELETED_AT, LedgerReason.OWNER),))
                second = session.append(((second_id, DELETED_AT, LedgerReason.RETENTION),))
            receipt = IndependentReceipt(first.generation, first.digest)
            self.assertEqual(
                assess_ledger_state(second, receipt, ((1, REQUEST_ID),), (second_id,)),
                LedgerState.PRIMARY_PENDING,
            )
            with self.assertRaises(LedgerError):
                assess_ledger_state(second, receipt, (), (second_id,))
            with self.assertRaises(LedgerError):
                assess_ledger_state(second, receipt, ((1, REQUEST_ID),), (REQUEST_ID, second_id))

    def test_independent_adapter_rejects_rollback_equivocation_and_corrupt_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = PrimaryLedger(Path(directory))
            adapter = SyntheticIndependentLedger()
            with ledger.locked() as session:
                empty = session.snapshot()
                first = session.append(((REQUEST_ID, DELETED_AT, LedgerReason.OWNER),))
            adapter.publish_and_verify(empty)
            receipt = adapter.publish_and_verify(first)
            self.assertEqual(adapter.publish_and_verify(first), receipt)
            with self.assertRaises(LedgerError):
                adapter.publish_and_verify(empty)
            equivocal = type(first)(first.generation, "f" * 64, first.records, first.payload)
            with self.assertRaises(LedgerError):
                adapter.publish_and_verify(equivocal)
            corrupt = type(first)(first.generation, first.digest, first.records, first.payload + b"x")
            with self.assertRaises(LedgerError):
                adapter.publish_and_verify(corrupt)

    def test_truncated_duplicate_json_and_invalid_deleted_at_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = PrimaryLedger(Path(directory))
            with ledger.locked() as session:
                first = session.append(((REQUEST_ID, DELETED_AT, LedgerReason.OWNER),))
            path = Path(directory) / "service-request-deletions.jsonl"
            path.write_bytes(first.payload[:-1])
            with ledger.locked() as session, self.assertRaises(LedgerError):
                session.snapshot()
        with tempfile.TemporaryDirectory() as directory:
            ledger = PrimaryLedger(Path(directory))
            path = Path(directory) / "service-request-deletions.jsonl"
            path.write_bytes(b'{"sequence":1,"sequence":1}\n')
            path.chmod(0o600)
            with ledger.locked() as session, self.assertRaises(LedgerError):
                session.snapshot()
        with tempfile.TemporaryDirectory() as directory:
            ledger = PrimaryLedger(Path(directory))
            with ledger.locked() as session, self.assertRaises(LedgerError):
                session.append(((REQUEST_ID, "not-a-time", LedgerReason.OWNER),))  # type: ignore[arg-type]
            self.assertEqual(
                (Path(directory) / "service-request-deletions.jsonl").read_bytes(),
                b"",
            )

    def test_short_write_and_fsync_failures_never_hide_ambiguity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = PrimaryLedger(Path(directory))
            real_write = os.write
            writes = 0

            def broken_write(descriptor, value):
                nonlocal writes
                writes += 1
                if writes == 1:
                    return real_write(descriptor, bytes(value[:10]))
                raise OSError("synthetic write fault")

            with self.assertRaises(LedgerError):
                with ledger.locked() as session, patch(
                    "modules.service_requests.ledger.os.write",
                    side_effect=broken_write,
                ):
                    session.append(((REQUEST_ID, DELETED_AT, LedgerReason.OWNER),))
            with ledger.locked() as session, self.assertRaises(LedgerError):
                session.snapshot()

        for fail_call in (1, 2):
            with self.subTest(fail_call=fail_call), tempfile.TemporaryDirectory() as directory:
                ledger = PrimaryLedger(Path(directory))
                real_fsync = os.fsync
                calls = 0

                def broken_fsync(descriptor):
                    nonlocal calls
                    calls += 1
                    if calls == fail_call:
                        raise OSError("synthetic fsync fault")
                    return real_fsync(descriptor)

                with self.assertRaises(LedgerError):
                    with ledger.locked() as session, patch(
                        "modules.service_requests.ledger.os.fsync",
                        side_effect=broken_fsync,
                    ):
                        session.append(((REQUEST_ID, DELETED_AT, LedgerReason.OWNER),))
                self.assertEqual(calls, fail_call)
                with self.assertRaises(LedgerError):
                    with ledger.locked() as session, patch(
                        "modules.service_requests.ledger.os.fsync",
                        side_effect=OSError("recovery fsync fault"),
                    ):
                        session.snapshot()
                with ledger.locked() as session:
                    snapshot = session.snapshot()
                self.assertEqual((snapshot.generation, snapshot.records[0].request_id), (1, REQUEST_ID))
