import hashlib
import inspect
import os
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import rebuild3_zero_ledger as authority
from rebuild3_importer.runtime_source import ProvidedLedgerVerifier, SourceRuntimeError


IDENTITY = uuid.UUID("7bb42ec1-dd9c-4ec7-a017-13427e446477")
SNAPSHOT = "10:20:"
RECIPIENT = "age1" + ("q" * 58)
CONFIG = authority.S3AuthorityConfig(
    endpoint_origin="https://s3.ru-3.storage.selcloud.ru",
    region_pool="ru-3",
    bucket="estakada-zero-ledger",
    recipient=RECIPIENT,
)
BINDING = authority._s3_binding(CONFIG)
CIPHERTEXT_SHA = "c" * 64
VERSION = b"version-1"
PLAINTEXT = authority._canonical(IDENTITY)


class FakeS3Authority:
    def __init__(self, versioning="Enabled", *, actual_config=None, publish_barrier=None):
        self.versioning = versioning
        self.actual_config = actual_config
        self.publish_barrier = publish_barrier
        self.events = []
        self.payload = None
        self.publish_error = None
        self.publish_proof = None
        self.read_proof = None
        self.keys = set()
        self.lock = threading.Lock()

    def binding(self, supplied):
        if self.actual_config is None:
            return supplied
        return authority._s3_binding(self.actual_config)

    def get_bucket_versioning(self, *, binding):
        self.events.append(("versioning",))
        echoed = self.binding(binding)
        return authority.S3VersioningProof(
            self.versioning,
            echoed.authority_config_sha256,
            echoed.recipient_sha256,
        )

    def publish_and_read_back(self, **kwargs):
        self.events.append(("publish", kwargs))
        if self.publish_error is not None:
            raise self.publish_error
        if self.publish_barrier is not None:
            self.publish_barrier.wait(timeout=5)
        with self.lock:
            if kwargs["object_key"] in self.keys:
                raise authority.ZeroLedgerError("zero-ledger")
            self.keys.add(kwargs["object_key"])
        self.payload = kwargs["plaintext"]
        echoed = self.binding(kwargs["binding"])
        return self.publish_proof or authority.S3PublishProof(
            VERSION,
            200,
            CIPHERTEXT_SHA,
            self.payload,
            echoed.authority_config_sha256,
            echoed.recipient_sha256,
        )

    def read_exact(self, **kwargs):
        self.events.append(("read", kwargs))
        echoed = self.binding(kwargs["binding"])
        return self.read_proof or authority.S3ReadProof(
            200,
            CIPHERTEXT_SHA,
            self.payload,
            echoed.authority_config_sha256,
            echoed.recipient_sha256,
        )


class ZeroLedgerS3AuthorityTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "primary"
        self.root.mkdir(mode=0o700)
        os.chmod(self.root, 0o700)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        self.root_fd = os.open(self.root, flags)
        self.addCleanup(os.close, self.root_fd)

    def artifact(self):
        return self.root / authority.FILENAME

    def assert_safe_failure(self, callback):
        with self.assertRaises(authority.ZeroLedgerError) as caught:
            callback()
        self.assertEqual(str(caught.exception), "zero-ledger")

    def create(self, remote=None, config=CONFIG):
        remote = remote or FakeS3Authority()
        with patch.object(authority.uuid, "uuid4", return_value=IDENTITY):
            receipt = authority.create_s3_zero_genesis(self.root_fd, config, remote)
        return receipt, remote

    def test_s3_001_success_order_receipt_and_snapshot_evidence(self):
        receipt, remote = self.create()
        self.assertEqual([item[0] for item in remote.events], ["versioning", "publish", "read"])
        publish = remote.events[1][1]
        self.assertEqual(publish["if_none_match"], "*")
        self.assertEqual(publish["encryption_profile"], "age-x25519-v1-binary")
        self.assertEqual(publish["object_key"], receipt.object_key)
        self.assertEqual(publish["binding"], BINDING)
        self.assertTrue(receipt.object_key.endswith(f"/{receipt.plaintext_sha256}.age"))
        self.assertEqual(self.artifact().read_bytes(), publish["plaintext"])
        read = remote.events[2][1]
        self.assertEqual(read["object_key"], receipt.object_key)
        self.assertEqual(read["version_id"], VERSION)
        self.assertEqual(read["encryption_profile"], authority.S3_ENCRYPTION_PROFILE)
        self.assertEqual(read["binding"], BINDING)
        encoded = authority.encode_s3_receipt(receipt)
        self.assertEqual(authority.decode_s3_receipt(encoded), receipt)
        self.assertNotIn(CONFIG.bucket.encode(), encoded)
        self.assertNotIn(RECIPIENT.encode(), encoded)

        evidence = authority.verify_s3_zero_genesis(
            self.root_fd,
            CONFIG,
            remote,
            receipt,
            SNAPSHOT,
        )
        self.assertEqual(
            (evidence.identity, evidence.generation, evidence.row_count, evidence.snapshot_id),
            (IDENTITY, 1, 0, SNAPSHOT),
        )
        verifier = ProvidedLedgerVerifier(evidence)
        self.assertIs(verifier.latest_for(SNAPSHOT), evidence)
        with self.assertRaisesRegex(SourceRuntimeError, "ledger-snapshot"):
            verifier.latest_for(SNAPSHOT)

    def test_s3_002_non_enabled_versioning_fails_before_uuid_plaintext_and_publish(self):
        for state in (None, "", "Disabled", "Suspended", "enabled", "UNKNOWN"):
            with self.subTest(state=state):
                remote = FakeS3Authority(state)
                with patch.object(authority.uuid, "uuid4", side_effect=AssertionError("uuid")):
                    self.assert_safe_failure(
                        lambda: authority.create_s3_zero_genesis(
                            self.root_fd,
                            CONFIG,
                            remote,
                        )
                    )
                self.assertEqual(remote.events, [("versioning",)])
                self.assertFalse(self.artifact().exists())
        os.chmod(self.root, 0o750)
        remote = FakeS3Authority()
        with (
            patch.object(authority, "_s3_binding", side_effect=AssertionError("config")),
            patch.object(authority.uuid, "uuid4", side_effect=AssertionError("uuid")),
        ):
            self.assert_safe_failure(
                lambda: authority.create_s3_zero_genesis(
                    self.root_fd,
                    CONFIG,
                    remote,
                )
            )
        self.assertEqual(remote.events, [])
        self.assertFalse(self.artifact().exists())
        os.chmod(self.root, 0o700)

    def test_s3_003_conditional_same_key_has_one_winner_and_no_overwrite(self):
        second_root = Path(self.temp.name) / "second"
        second_root.mkdir(mode=0o700)
        os.chmod(second_root, 0o700)
        second_fd = os.open(second_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.addCleanup(os.close, second_fd)
        remote = FakeS3Authority(publish_barrier=threading.Barrier(2))

        def run(root_fd):
            try:
                return ("ok", authority.create_s3_zero_genesis(root_fd, CONFIG, remote))
            except authority.ZeroLedgerError as exc:
                return ("error", exc)

        with patch.object(authority.uuid, "uuid4", return_value=IDENTITY):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(run, (self.root_fd, second_fd)))
        self.assertEqual([result[0] for result in results].count("ok"), 1)
        self.assertEqual([result[0] for result in results].count("error"), 1)
        winner = next(result[1] for result in results if result[0] == "ok")
        loser = next(result[1] for result in results if result[0] == "error")
        self.assertEqual(str(loser), "zero-ledger")
        publishes = [event for event in remote.events if event[0] == "publish"]
        self.assertEqual(len(publishes), 2)
        self.assertEqual({event[1]["if_none_match"] for event in publishes}, {"*"})
        self.assertEqual({event[1]["object_key"] for event in publishes}, {winner.object_key})
        artifacts = [self.artifact().exists(), (second_root / authority.FILENAME).exists()]
        self.assertEqual(artifacts.count(True), 1)

    def test_s3_004_ambiguous_publish_never_creates_local_or_discovers(self):
        remote = FakeS3Authority()
        remote.publish_error = TimeoutError("PRIVATE")
        with self.assertRaises(authority.S3AmbiguousUpload) as caught:
            self.create(remote)
        self.assertEqual(str(caught.exception), "zero-ledger")
        self.assertEqual(caught.exception.result.state, "UNKNOWN_VERSION")
        self.assertEqual(caught.exception.result.object_key, remote.events[1][1]["object_key"])
        self.assertEqual([event[0] for event in remote.events], ["versioning", "publish"])
        self.assertFalse(self.artifact().exists())

        remote = FakeS3Authority()
        remote.publish_error = TimeoutError("PRIVATE")
        real_close_pair = authority._close_pair

        def close_then_fail(primary_fd, independent_fd):
            real_close_pair(primary_fd, independent_fd)
            raise authority.ZeroLedgerError("zero-ledger")

        with patch.object(authority, "_close_pair", side_effect=close_then_fail):
            with self.assertRaises(authority.S3AmbiguousUpload) as combined:
                self.create(remote)
        self.assertEqual(combined.exception.result.state, "UNKNOWN_VERSION")
        self.assertEqual(combined.exception.result.object_key, remote.events[1][1]["object_key"])

    def test_s3_005_publish_and_readback_proof_boundaries_fail_closed(self):
        for bad_version in (b"", b"bad\x00version", b"\xff"):
            with self.subTest(version=bad_version):
                remote = FakeS3Authority()
                remote.publish_proof = authority.S3PublishProof(
                    bad_version,
                    200,
                    CIPHERTEXT_SHA,
                    PLAINTEXT,
                    BINDING.authority_config_sha256,
                    BINDING.recipient_sha256,
                )
                with self.assertRaises(authority.S3AmbiguousUpload) as caught:
                    self.create(remote)
                self.assertEqual(caught.exception.result.state, "UNKNOWN_VERSION")
                self.assertEqual(
                    caught.exception.result.object_key,
                    remote.events[1][1]["object_key"],
                )
                self.assertFalse(self.artifact().exists())
        bad_proofs = (
            authority.S3PublishProof(
                VERSION, 0, CIPHERTEXT_SHA, b"x" * authority.MAX_BYTES,
                BINDING.authority_config_sha256, BINDING.recipient_sha256,
            ),
            authority.S3PublishProof(
                VERSION,
                authority.S3_MAX_CIPHERTEXT_BYTES + 1,
                CIPHERTEXT_SHA,
                b"x" * authority.MAX_BYTES,
                BINDING.authority_config_sha256,
                BINDING.recipient_sha256,
            ),
            authority.S3PublishProof(
                VERSION, 200, CIPHERTEXT_SHA.upper(), b"x" * authority.MAX_BYTES,
                BINDING.authority_config_sha256, BINDING.recipient_sha256,
            ),
            authority.S3PublishProof(
                VERSION, 200, CIPHERTEXT_SHA, PLAINTEXT,
                "0" * 64, BINDING.recipient_sha256,
            ),
        )
        for proof in bad_proofs:
            with self.subTest(proof=repr(proof)):
                remote = FakeS3Authority()
                remote.publish_proof = proof
                self.assert_safe_failure(lambda: self.create(remote))
                self.assertFalse(self.artifact().exists())

    def test_s3_006_local_failure_after_remote_success_is_not_evidence(self):
        remote = FakeS3Authority()
        with patch.object(authority, "_write_copy", side_effect=OSError("PRIVATE")):
            self.assert_safe_failure(lambda: self.create(remote))
        self.assertEqual([event[0] for event in remote.events], ["versioning", "publish"])
        self.assertEqual(len(remote.keys), 1)
        self.assertFalse(self.artifact().exists())

        remote = FakeS3Authority()
        remote.read_proof = authority.S3ReadProof(
            200,
            "d" * 64,
            b"x" * authority.MAX_BYTES,
            BINDING.authority_config_sha256,
            BINDING.recipient_sha256,
        )
        self.assert_safe_failure(lambda: self.create(remote))
        self.assertEqual([event[0] for event in remote.events], ["versioning", "publish", "read"])
        self.assertTrue(self.artifact().exists())

    def test_s3_007_remote_final_read_and_local_drift_fail_verification(self):
        receipt, remote = self.create()
        remote.read_proof = authority.S3ReadProof(
            200,
            "d" * 64,
            remote.payload,
            BINDING.authority_config_sha256,
            BINDING.recipient_sha256,
        )
        self.assert_safe_failure(
            lambda: authority.verify_s3_zero_genesis(
                self.root_fd, CONFIG, remote, receipt, SNAPSHOT
            )
        )
        remote.read_proof = authority.S3ReadProof(
            200,
            CIPHERTEXT_SHA,
            remote.payload,
            BINDING.authority_config_sha256,
            "0" * 64,
        )
        self.assert_safe_failure(
            lambda: authority.verify_s3_zero_genesis(
                self.root_fd, CONFIG, remote, receipt, SNAPSHOT
            )
        )
        remote.read_proof = None
        os.chmod(self.artifact(), 0o640)
        self.assert_safe_failure(
            lambda: authority.verify_s3_zero_genesis(
                self.root_fd, CONFIG, remote, receipt, SNAPSHOT
            )
        )

    def test_s3_008_config_crypto_receipt_and_snapshot_drift_are_rejected(self):
        receipt, remote = self.create()
        other = replace(CONFIG, bucket="estakada-zero-ledger-alt")
        mismatched = FakeS3Authority(actual_config=other)
        with patch.object(authority.uuid, "uuid4", side_effect=AssertionError("uuid")):
            self.assert_safe_failure(
                lambda: authority.create_s3_zero_genesis(
                    self.root_fd,
                    CONFIG,
                    mismatched,
                )
            )
        self.assertEqual(mismatched.events, [("versioning",)])
        bad_configs = (
            replace(CONFIG, endpoint_origin="http://s3.example.test"),
            replace(CONFIG, endpoint_origin="https://s3.example.test/path"),
            replace(CONFIG, region_pool="RU-3"),
            replace(CONFIG, bucket="192.168.1.1"),
            replace(CONFIG, bucket="bad..bucket"),
            replace(CONFIG, recipient="age1" + ("b" * 58)),
        )
        for config in bad_configs:
            with self.subTest(config=repr(config)):
                self.assert_safe_failure(
                    lambda config=config: authority.verify_s3_zero_genesis(
                        self.root_fd, config, remote, receipt, SNAPSHOT
                    )
                )
        bad_receipts = (
            replace(receipt, encryption_profile="other"),
            replace(receipt, recipient_sha256="0" * 64),
            replace(receipt, authority_config_sha256="0" * 64),
            replace(receipt, object_version_id_b64="="),
            replace(receipt, ciphertext_sha256="0" * 64),
        )
        for bad in bad_receipts:
            with self.subTest(receipt=repr(bad)):
                self.assert_safe_failure(
                    lambda bad=bad: authority.verify_s3_zero_genesis(
                        self.root_fd, CONFIG, remote, bad, SNAPSHOT
                    )
                )
        self.assert_safe_failure(
            lambda: authority.verify_s3_zero_genesis(
                self.root_fd, CONFIG, remote, receipt, "wrong"
            )
        )

    def test_s3_009_receipt_parser_rejects_noncanonical_duplicate_extra_and_caps(self):
        receipt, _ = self.create()
        canonical = authority.encode_s3_receipt(receipt)
        mutations = (
            canonical.replace(b'"version":1,', b'"version":true,'),
            canonical.replace(b'"identity":', b'"extra":0,"identity":'),
            canonical.replace(b'"generation":1,', b'"generation":1,"generation":1,'),
            canonical.replace(b',"generation":1', b'') + b" ",
            canonical + (b"x" * authority.S3_MAX_RECEIPT_BYTES),
        )
        for payload in mutations:
            with self.subTest(size=len(payload)):
                self.assert_safe_failure(lambda payload=payload: authority.decode_s3_receipt(payload))

    def test_s3_010_scope_has_no_client_secret_or_generic_storage_api(self):
        public = {name for name in dir(authority) if not name.startswith("_")}
        self.assertEqual(
            {name for name in public if name.endswith("zero_genesis")},
            {
                "create_zero_genesis",
                "verify_zero_genesis",
                "create_s3_zero_genesis",
                "verify_s3_zero_genesis",
            },
        )
        self.assertEqual(
            set(authority.S3AuthorityConfig.__dataclass_fields__),
            {"endpoint_origin", "region_pool", "bucket", "recipient"},
        )
        source = inspect.getsource(authority)
        for forbidden in ("boto", "requests", "rclone", "access_key", "secret_key"):
            self.assertNotIn(forbidden, source.lower())
        self.assertNotIn("delete", set(authority.S3AuthorityPort.__dict__))
        self.assertNotIn("list", set(authority.S3AuthorityPort.__dict__))
