import hashlib
import os
import stat
import tempfile
import uuid
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import rebuild3_zero_ledger as authority
from rebuild3_importer.runtime_source import ProvidedLedgerVerifier, SourceRuntimeError


IDENTITY = uuid.UUID("7bb42ec1-dd9c-4ec7-a017-13427e446477")
SNAPSHOT = "10:20:"


class ZeroLedgerAuthorityTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.primary = root / "primary"
        self.independent = root / "independent"
        self.primary.mkdir(mode=0o700)
        self.independent.mkdir(mode=0o700)
        os.chmod(self.primary, 0o700)
        os.chmod(self.independent, 0o700)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        self.primary_fd = os.open(self.primary, flags)
        self.independent_fd = os.open(self.independent, flags)
        self.addCleanup(os.close, self.independent_fd)
        self.addCleanup(os.close, self.primary_fd)

    def create(self):
        with (
            patch.object(authority, "_roots_independent", return_value=True),
            patch.object(authority.uuid, "uuid4", return_value=IDENTITY),
        ):
            return authority.create_zero_genesis(self.primary_fd, self.independent_fd)

    def verify(self, receipt, snapshot=SNAPSHOT):
        with patch.object(authority, "_roots_independent", return_value=True):
            return authority.verify_zero_genesis(
                self.primary_fd,
                self.independent_fd,
                receipt,
                snapshot,
            )

    def artifact(self, root):
        return root / authority.FILENAME

    def assert_safe_failure(self, callback):
        with self.assertRaises(authority.ZeroLedgerError) as caught:
            callback()
        self.assertEqual(str(caught.exception), "zero-ledger")

    def test_create_then_verify_is_exact_zero_row_snapshot_evidence(self):
        receipt = self.create()
        primary = self.artifact(self.primary).read_bytes()
        independent = self.artifact(self.independent).read_bytes()
        self.assertEqual(primary, independent)
        self.assertEqual(len(primary), authority.MAX_BYTES)
        self.assertTrue(primary.endswith(b"\n"))
        self.assertEqual(hashlib.sha256(primary).hexdigest(), receipt.digest)
        self.assertEqual(receipt.identity, IDENTITY)
        self.assertEqual((receipt.generation, receipt.row_count), (1, 0))
        self.assertNotIn(receipt.digest, repr(receipt))
        for path in (self.artifact(self.primary), self.artifact(self.independent)):
            value = path.stat()
            self.assertTrue(stat.S_ISREG(value.st_mode))
            self.assertEqual(stat.S_IMODE(value.st_mode), 0o600)
            self.assertEqual(value.st_nlink, 1)

        evidence = self.verify(receipt)
        self.assertEqual(
            (
                evidence.identity,
                evidence.generation,
                evidence.digest,
                evidence.row_count,
                evidence.snapshot_id,
            ),
            (IDENTITY, 1, receipt.digest, 0, SNAPSHOT),
        )
        verifier = ProvidedLedgerVerifier(evidence)
        self.assertIs(verifier.latest_for(SNAPSHOT), evidence)
        with self.assertRaisesRegex(SourceRuntimeError, "ledger-snapshot"):
            verifier.latest_for(SNAPSHOT)

    def test_same_device_fails_before_file_creation(self):
        self.assertEqual(os.fstat(self.primary_fd).st_dev, os.fstat(self.independent_fd).st_dev)
        self.assert_safe_failure(
            lambda: authority.create_zero_genesis(self.primary_fd, self.independent_fd)
        )
        self.assertFalse(self.artifact(self.primary).exists())
        self.assertFalse(self.artifact(self.independent).exists())

    def test_existing_file_is_never_overwritten(self):
        receipt = self.create()
        before = self.artifact(self.primary).read_bytes()
        self.assert_safe_failure(self.create)
        self.assertEqual(self.artifact(self.primary).read_bytes(), before)
        self.assertEqual(self.verify(receipt).row_count, 0)

    def test_independent_copy_precedes_primary_and_partial_is_not_evidence(self):
        real_write = authority._write_copy
        primary_inode = os.fstat(self.primary_fd).st_ino
        order = []

        def fail_primary(root_fd, root, payload):
            order.append(root.ino)
            if root.ino == primary_inode:
                raise OSError("synthetic")
            return real_write(root_fd, root, payload)

        with (
            patch.object(authority, "_roots_independent", return_value=True),
            patch.object(authority.uuid, "uuid4", return_value=IDENTITY),
            patch.object(authority, "_write_copy", side_effect=fail_primary),
        ):
            self.assert_safe_failure(
                lambda: authority.create_zero_genesis(
                    self.primary_fd,
                    self.independent_fd,
                )
            )
        self.assertEqual(order[-1], primary_inode)
        self.assertTrue(self.artifact(self.independent).exists())
        self.assertFalse(self.artifact(self.primary).exists())

    def test_short_write_is_fail_closed_without_primary(self):
        with (
            patch.object(authority, "_roots_independent", return_value=True),
            patch.object(authority.uuid, "uuid4", return_value=IDENTITY),
            patch.object(authority.os, "write", return_value=0),
        ):
            self.assert_safe_failure(
                lambda: authority.create_zero_genesis(
                    self.primary_fd,
                    self.independent_fd,
                )
            )
        self.assertFalse(self.artifact(self.primary).exists())

    def test_fsync_ambiguity_is_fail_closed_without_primary(self):
        with (
            patch.object(authority, "_roots_independent", return_value=True),
            patch.object(authority.uuid, "uuid4", return_value=IDENTITY),
            patch.object(authority.os, "fsync", side_effect=OSError("synthetic")),
        ):
            self.assert_safe_failure(
                lambda: authority.create_zero_genesis(
                    self.primary_fd,
                    self.independent_fd,
                )
            )
        self.assertFalse(self.artifact(self.primary).exists())

    def test_close_ambiguity_never_retries_same_file_descriptor(self):
        real_close = os.close
        attempts = []
        failed_regular = []

        def ambiguous_close(fd):
            attempts.append(fd)
            is_regular = stat.S_ISREG(os.fstat(fd).st_mode)
            real_close(fd)
            if is_regular and not failed_regular:
                failed_regular.append(fd)
                raise OSError("synthetic")

        with (
            patch.object(authority, "_roots_independent", return_value=True),
            patch.object(authority.uuid, "uuid4", return_value=IDENTITY),
            patch.object(authority.os, "close", side_effect=ambiguous_close),
        ):
            self.assert_safe_failure(
                lambda: authority.create_zero_genesis(
                    self.primary_fd,
                    self.independent_fd,
                )
            )
        self.assertEqual(len(failed_regular), 1)
        self.assertEqual(attempts.count(failed_regular[0]), 1)
        self.assertFalse(self.artifact(self.primary).exists())

    def test_pair_close_attempts_both_once_after_first_error(self):
        attempts = []

        def close(fd):
            attempts.append(fd)
            if fd == 202:
                raise OSError("synthetic")

        with patch.object(authority.os, "close", side_effect=close):
            self.assert_safe_failure(lambda: authority._close_pair(101, 202))
        self.assertEqual(attempts, [202, 101])

    def test_copy_drift_metadata_drift_and_receipt_drift_fail(self):
        receipt = self.create()
        copy_path = self.artifact(self.independent)
        original = copy_path.read_bytes()
        copy_path.write_bytes(original[:-2] + b"1\n")
        os.chmod(copy_path, 0o600)
        self.assert_safe_failure(lambda: self.verify(receipt))
        copy_path.write_bytes(original)
        os.chmod(copy_path, 0o640)
        self.assert_safe_failure(lambda: self.verify(receipt))
        os.chmod(copy_path, 0o600)
        wrong = authority.ZeroLedgerReceipt(
            receipt.identity,
            1,
            "0" * 64,
            0,
        )
        self.assert_safe_failure(lambda: self.verify(wrong))

    def test_root_mode_drift_and_extra_canonical_byte_fail(self):
        receipt = self.create()
        os.chmod(self.primary, 0o750)
        self.assert_safe_failure(lambda: self.verify(receipt))
        os.chmod(self.primary, 0o700)
        path = self.artifact(self.primary)
        path.write_bytes(path.read_bytes() + b"\n")
        os.chmod(path, 0o600)
        self.assert_safe_failure(lambda: self.verify(receipt))

    def test_named_entry_replacement_is_rejected(self):
        receipt = self.create()
        real_assert = authority._assert_named
        replaced = False

        def replace_once(root_fd, root, held):
            nonlocal replaced
            if not replaced and root.ino == os.fstat(self.primary_fd).st_ino:
                replaced = True
                path = self.artifact(self.primary)
                payload = path.read_bytes()
                path.unlink()
                path.write_bytes(payload)
                os.chmod(path, 0o600)
            return real_assert(root_fd, root, held)

        with (
            patch.object(authority, "_roots_independent", return_value=True),
            patch.object(authority, "_assert_named", side_effect=replace_once),
        ):
            self.assert_safe_failure(
                lambda: authority.verify_zero_genesis(
                    self.primary_fd,
                    self.independent_fd,
                    receipt,
                    SNAPSHOT,
                )
            )
        self.assertTrue(replaced)

    def test_nonzero_or_malformed_receipt_and_snapshot_are_rejected(self):
        receipt = self.create()
        bad_receipts = (
            authority.ZeroLedgerReceipt(uuid.UUID(int=0), 1, receipt.digest, 0),
            authority.ZeroLedgerReceipt(receipt.identity, 2, receipt.digest, 0),
            authority.ZeroLedgerReceipt(receipt.identity, 1, receipt.digest.upper(), 0),
            authority.ZeroLedgerReceipt(receipt.identity, 1, receipt.digest, 1),
        )
        for bad in bad_receipts:
            with self.subTest(receipt=repr(bad)):
                self.assert_safe_failure(lambda bad=bad: self.verify(bad))
        for snapshot in ("", "10:20", "snapshot-1", None):
            with self.subTest(snapshot=snapshot):
                self.assert_safe_failure(lambda snapshot=snapshot: self.verify(receipt, snapshot))

    def test_api_has_no_append_or_nonzero_operation(self):
        public = {name for name in dir(authority) if not name.startswith("_")}
        self.assertNotIn("append", public)
        self.assertNotIn("delete", public)
        self.assertNotIn("restore", public)
        self.assertEqual(
            {name for name in public if name.endswith("zero_genesis")},
            {"create_zero_genesis", "verify_zero_genesis"},
        )
