import hashlib
import inspect
import os
import subprocess
import tempfile
import unittest
import uuid
from dataclasses import replace
from unittest.mock import patch

import rebuild3_s3_materialize as materialize
import rebuild3_zero_ledger as authority


CONFIG = authority.S3AuthorityConfig(
    endpoint_origin="https://s3.ru-3.storage.selcloud.ru",
    region_pool="ru-3",
    bucket="estakada-zero-ledger",
    recipient="age1" + ("q" * 58),
)
BINDING = authority._s3_binding(CONFIG)
KEY_IDENTITY = uuid.UUID("12345678-1234-4abc-8def-1234567890ab")
PLAINTEXT = authority._canonical(KEY_IDENTITY)
CIPHERTEXT = b"age-encrypted\x00payload"
VERSION = "3/L4kqtJlcpXroDTDmJ+rmSpXd3dIbrHY+MTRCxf3vjVBk"
OBJECT_KEY = (
    f"{authority.S3_PREFIX}{KEY_IDENTITY}/"
    f"{hashlib.sha256(PLAINTEXT).hexdigest()}.age"
)


class FakeBody:
    def __init__(self, payload, *, close_error=False):
        self.payload = payload
        self.close_error = close_error
        self.read_sizes = []
        self.closed = False

    def read(self, size):
        self.read_sizes.append(size)
        return self.payload[:size]

    def close(self):
        self.closed = True
        if self.close_error:
            raise OSError("PRIVATE")


class ClientError(Exception):
    def __init__(self, status):
        super().__init__("PRIVATE")
        self.response = {"ResponseMetadata": {"HTTPStatusCode": status}}


class FakeClient:
    def __init__(self, trace=None):
        self.events = []
        self.trace = trace
        self.versioning = {"Status": "Enabled"}
        self.put_response = {"VersionId": VERSION}
        self.put_error = None
        self.get_error = None
        self.get_payload = CIPHERTEXT
        self.get_version = VERSION
        self.close_error = False
        self.last_body = None

    def get_bucket_versioning(self, **kwargs):
        self.events.append(("versioning", kwargs))
        if self.trace is not None:
            self.trace.append("versioning")
        return self.versioning

    def put_object(self, **kwargs):
        self.events.append(("put", kwargs))
        if self.trace is not None:
            self.trace.append("put")
        if self.put_error is not None:
            raise self.put_error
        return self.put_response

    def get_object(self, **kwargs):
        self.events.append(("get", kwargs))
        if self.trace is not None:
            self.trace.append("get")
        if self.get_error is not None:
            raise self.get_error
        self.last_body = FakeBody(self.get_payload, close_error=self.close_error)
        return {
            "VersionId": self.get_version,
            "ContentLength": len(self.get_payload),
            "Body": self.last_body,
        }


class FakeAge:
    def __init__(self, trace=None):
        self.events = []
        self.trace = trace
        self.encrypt_result = CIPHERTEXT
        self.decrypt_result = PLAINTEXT
        self.encrypt_error = None
        self.decrypt_error = None

    def encrypt(self, plaintext, recipient):
        self.events.append(("encrypt", plaintext, recipient))
        if self.trace is not None:
            self.trace.append("encrypt")
        if self.encrypt_error is not None:
            raise self.encrypt_error
        return self.encrypt_result

    def decrypt(self, ciphertext):
        self.events.append(("decrypt", ciphertext))
        if self.trace is not None:
            self.trace.append("decrypt")
        if self.decrypt_error is not None:
            raise self.decrypt_error
        return self.decrypt_result


class S3MaterializeAdapterTests(unittest.TestCase):
    def adapter(self, client=None, age=None, config=CONFIG):
        return materialize.SelectelS3Authority(
            config=config,
            client=client or FakeClient(),
            age=age or FakeAge(),
        )

    def assert_safe_failure(self, callback, kind=authority.ZeroLedgerError):
        with self.assertRaises(kind) as caught:
            callback()
        self.assertEqual(str(caught.exception), "zero-ledger")
        self.assertNotIn("PRIVATE", repr(caught.exception))
        return caught.exception

    def test_adp_001_versioning_and_client_use_exact_binding_and_secret_handle(self):
        client = FakeClient()
        proof = self.adapter(client=client).get_bucket_versioning(binding=BINDING)
        self.assertEqual(client.events, [("versioning", {"Bucket": CONFIG.bucket})])
        self.assertEqual(proof.state, "Enabled")
        self.assertEqual(proof.authority_config_sha256, BINDING.authority_config_sha256)
        client.versioning = {}
        self.assertIsNone(self.adapter(client=client).get_bucket_versioning(binding=BINDING).state)

        with tempfile.TemporaryDirectory() as directory:
            secret_path = os.path.join(directory, "s3.secret")
            with open(secret_path, "wb") as stream:
                stream.write(
                    b"access_key_id=" + (b"A" * 20) + b"\n"
                    b"secret_access_key=" + (b"s" * 40) + b"\n"
                )
            os.chmod(secret_path, 0o600)
            secret_fd = os.open(secret_path, os.O_RDONLY | os.O_NOFOLLOW)
            self.addCleanup(os.close, secret_fd)
            calls = {}

            class Events:
                def register_first(self, *args, **kwargs):
                    calls["event"] = (args, kwargs)

            class Client:
                class Meta:
                    events = Events()

                meta = Meta()

            class Session:
                def __init__(self, **kwargs):
                    calls["session"] = kwargs

                def client(self, *args, **kwargs):
                    calls["client"] = (args, kwargs)
                    return Client()

            def config_factory(**kwargs):
                calls["config"] = kwargs
                return "CONFIG"

            with patch.object(materialize, "_load_sdk", return_value=(Session, config_factory)):
                built = materialize._build_selectel_client(CONFIG, secret_fd)
            self.assertIsInstance(built, Client)
            self.assertEqual(
                calls["session"],
                {
                    "aws_access_key_id": "A" * 20,
                    "aws_secret_access_key": "s" * 40,
                    "region_name": CONFIG.region_pool,
                },
            )
            self.assertEqual(calls["config"]["retries"], {"total_max_attempts": 1, "mode": "standard"})
            self.assertEqual(calls["config"]["signature_version"], "s3v4")
            self.assertEqual(calls["config"]["connect_timeout"], 5)
            self.assertEqual(calls["config"]["read_timeout"], 10)
            self.assertEqual(calls["config"]["s3"], {"addressing_style": "path"})
            self.assertEqual(calls["config"]["proxies"], {})
            self.assertTrue(calls["config"]["ignore_configured_endpoint_urls"])
            self.assertEqual(calls["client"][0], ("s3",))
            self.assertEqual(calls["client"][1]["endpoint_url"], CONFIG.endpoint_origin)
            self.assertEqual(calls["client"][1]["region_name"], CONFIG.region_pool)
            self.assertTrue(calls["client"][1]["use_ssl"])
            self.assertTrue(calls["client"][1]["verify"])
            self.assertEqual(calls["event"][0][0], "before-send.s3")
            self.assertTrue(callable(calls["event"][0][1]))
            self.assertEqual(
                calls["event"][1],
                {"unique_id": "estakada-zero-ledger-origin-v1"},
            )
            guard = calls["event"][0][1]
            guard(type("Request", (), {"url": f"{CONFIG.endpoint_origin}/{CONFIG.bucket}/key"})())
            self.assert_safe_failure(
                lambda: guard(type("Request", (), {"url": "https://other.example/bucket/key"})())
            )
            read_write_fd = os.open(secret_path, os.O_RDWR | os.O_NOFOLLOW)
            self.addCleanup(os.close, read_write_fd)
            self.assert_safe_failure(
                lambda: materialize._build_selectel_client(CONFIG, read_write_fd)
            )
            os.chmod(secret_path, 0o644)
            self.assert_safe_failure(
                lambda: materialize._build_selectel_client(CONFIG, secret_fd)
            )
            for index, payload in enumerate(
                (
                    b"access_key_id=short\nsecret_access_key=" + (b"s" * 40) + b"\n",
                    b"secret_access_key=" + (b"s" * 40) + b"\naccess_key_id=" + (b"A" * 20) + b"\n",
                    b"access_key_id=" + (b"A" * 20) + b"\nsecret_access_key=" + (b"s" * 20) + b" " + (b"s" * 20) + b"\n",
                    b"x" * (materialize._MAX_SECRET_HANDLE_BYTES + 1),
                )
            ):
                bad_path = os.path.join(directory, f"bad-{index}")
                with open(bad_path, "wb") as stream:
                    stream.write(payload)
                os.chmod(bad_path, 0o600)
                bad_fd = os.open(bad_path, os.O_RDONLY | os.O_NOFOLLOW)
                self.addCleanup(os.close, bad_fd)
                with self.subTest(secret=index):
                    self.assert_safe_failure(
                        lambda bad_fd=bad_fd: materialize._build_selectel_client(
                            CONFIG, bad_fd
                        )
                    )

    def test_adp_002_publish_encrypts_before_exact_conditional_put_and_version_get(self):
        trace = []
        client, age = FakeClient(trace), FakeAge(trace)
        proof = self.adapter(client=client, age=age).publish_and_read_back(
            object_key=OBJECT_KEY,
            plaintext=PLAINTEXT,
            encryption_profile=authority.S3_ENCRYPTION_PROFILE,
            if_none_match="*",
            binding=BINDING,
        )
        self.assertEqual(age.events[0], ("encrypt", PLAINTEXT, CONFIG.recipient))
        self.assertEqual(trace, ["encrypt", "put", "get", "decrypt"])
        self.assertEqual([event[0] for event in client.events], ["put", "get"])
        self.assertEqual(
            client.events[0][1],
            {
                "Bucket": CONFIG.bucket,
                "Key": OBJECT_KEY,
                "Body": CIPHERTEXT,
                "IfNoneMatch": "*",
            },
        )
        self.assertEqual(
            client.events[1][1],
            {
                "Bucket": CONFIG.bucket,
                "Key": OBJECT_KEY,
                "VersionId": VERSION,
            },
        )
        self.assertEqual(proof.version_id, VERSION.encode("utf-8"))
        self.assertEqual(proof.plaintext, PLAINTEXT)
        self.assertEqual(proof.ciphertext_size, len(CIPHERTEXT))
        self.assertEqual(proof.ciphertext_sha256, hashlib.sha256(CIPHERTEXT).hexdigest())

    def test_adp_003_read_exact_is_bounded_closes_body_and_decrypts(self):
        client, age = FakeClient(), FakeAge()
        proof = self.adapter(client=client, age=age).read_exact(
            object_key=OBJECT_KEY,
            version_id=VERSION.encode("utf-8"),
            encryption_profile=authority.S3_ENCRYPTION_PROFILE,
            binding=BINDING,
        )
        self.assertEqual(client.last_body.read_sizes, [authority.S3_MAX_CIPHERTEXT_BYTES + 1])
        self.assertTrue(client.last_body.closed)
        self.assertEqual(age.events, [("decrypt", CIPHERTEXT)])
        self.assertEqual(proof.plaintext, PLAINTEXT)

    def test_adp_004_412_is_closed_collision_without_retry_or_get(self):
        client = FakeClient()
        client.put_error = ClientError(412)
        self.assert_safe_failure(
            lambda: self.adapter(client=client).publish_and_read_back(
                object_key=OBJECT_KEY,
                plaintext=PLAINTEXT,
                encryption_profile=authority.S3_ENCRYPTION_PROFILE,
                if_none_match="*",
                binding=BINDING,
            )
        )
        self.assertEqual([event[0] for event in client.events], ["put"])

    def test_adp_005_409_timeout_and_unknown_put_are_ambiguous_without_discovery(self):
        for error in (ClientError(409), TimeoutError("PRIVATE"), ClientError(500)):
            with self.subTest(error=type(error).__name__):
                client = FakeClient()
                client.put_error = error
                caught = self.assert_safe_failure(
                    lambda: self.adapter(client=client).publish_and_read_back(
                        object_key=OBJECT_KEY,
                        plaintext=PLAINTEXT,
                        encryption_profile=authority.S3_ENCRYPTION_PROFILE,
                        if_none_match="*",
                        binding=BINDING,
                    ),
                    authority.S3AmbiguousUpload,
                )
                self.assertEqual(caught.result.state, "UNKNOWN_VERSION")
                self.assertEqual(caught.result.object_key, OBJECT_KEY)
                self.assertEqual([event[0] for event in client.events], ["put"])

    def test_adp_006_missing_or_invalid_put_version_is_ambiguous(self):
        for response in ({}, {"VersionId": ""}, {"VersionId": "bad\x00version"}, {"VersionId": 7}):
            with self.subTest(response=response):
                client = FakeClient()
                client.put_response = response
                self.assert_safe_failure(
                    lambda: self.adapter(client=client).publish_and_read_back(
                        object_key=OBJECT_KEY,
                        plaintext=PLAINTEXT,
                        encryption_profile=authority.S3_ENCRYPTION_PROFILE,
                        if_none_match="*",
                        binding=BINDING,
                    ),
                    authority.S3AmbiguousUpload,
                )
                self.assertEqual([event[0] for event in client.events], ["put"])

    def test_adp_007_ciphertext_content_length_version_and_close_drift_fail_closed(self):
        cases = (
            (b"x" * (authority.S3_MAX_CIPHERTEXT_BYTES + 1), VERSION, False),
            (CIPHERTEXT, "other", False),
            (CIPHERTEXT, VERSION, True),
        )
        for payload, version, close_error in cases:
            with self.subTest(size=len(payload), version=version, close=close_error):
                client = FakeClient()
                client.get_payload = payload
                client.get_version = version
                client.close_error = close_error
                self.assert_safe_failure(
                    lambda: self.adapter(client=client).read_exact(
                        object_key=OBJECT_KEY,
                        version_id=VERSION.encode("utf-8"),
                        encryption_profile=authority.S3_ENCRYPTION_PROFILE,
                        binding=BINDING,
                    )
                )

    def test_adp_008_age_failure_plaintext_drift_and_ciphertext_cap_fail_closed(self):
        age = FakeAge()
        age.encrypt_error = OSError("PRIVATE")
        self.assert_safe_failure(
            lambda: self.adapter(age=age).publish_and_read_back(
                object_key=OBJECT_KEY,
                plaintext=PLAINTEXT,
                encryption_profile=authority.S3_ENCRYPTION_PROFILE,
                if_none_match="*",
                binding=BINDING,
            )
        )
        age = FakeAge()
        age.encrypt_result = b"x" * (authority.S3_MAX_CIPHERTEXT_BYTES + 1)
        client = FakeClient()
        self.assert_safe_failure(
            lambda: self.adapter(client=client, age=age).publish_and_read_back(
                object_key=OBJECT_KEY,
                plaintext=PLAINTEXT,
                encryption_profile=authority.S3_ENCRYPTION_PROFILE,
                if_none_match="*",
                binding=BINDING,
            )
        )
        self.assertEqual(client.events, [])
        for decrypted in (b"", b"x" * authority.MAX_BYTES):
            with self.subTest(size=len(decrypted)):
                age = FakeAge()
                age.decrypt_result = decrypted
                if len(decrypted) != authority.MAX_BYTES:
                    self.assert_safe_failure(
                        lambda: self.adapter(age=age).read_exact(
                            object_key=OBJECT_KEY,
                            version_id=VERSION.encode("utf-8"),
                            encryption_profile=authority.S3_ENCRYPTION_PROFILE,
                            binding=BINDING,
                        )
                    )
                    continue
                proof = self.adapter(age=age).read_exact(
                    object_key=OBJECT_KEY,
                    version_id=VERSION.encode("utf-8"),
                    encryption_profile=authority.S3_ENCRYPTION_PROFILE,
                    binding=BINDING,
                )
                receipt = authority.S3ZeroLedgerReceipt(
                    identity=KEY_IDENTITY,
                    generation=1,
                    row_count=0,
                    plaintext_sha256=hashlib.sha256(PLAINTEXT).hexdigest(),
                    encryption_profile=authority.S3_ENCRYPTION_PROFILE,
                    recipient_sha256=BINDING.recipient_sha256,
                    authority_config_sha256=BINDING.authority_config_sha256,
                    object_key=OBJECT_KEY,
                    object_version_id_b64="dmVyc2lvbg",
                    ciphertext_size=len(CIPHERTEXT),
                    ciphertext_sha256=hashlib.sha256(CIPHERTEXT).hexdigest(),
                )
                self.assert_safe_failure(
                    lambda: authority._s3_validate_read(
                        proof, receipt, PLAINTEXT, BINDING
                    )
                )

    def test_adp_009_binding_profile_derived_key_and_if_none_match_are_literal(self):
        adapter = self.adapter()
        bad_calls = (
            {"object_key": "other/key", "encryption_profile": authority.S3_ENCRYPTION_PROFILE, "if_none_match": "*", "binding": BINDING},
            {"object_key": OBJECT_KEY, "encryption_profile": "other", "if_none_match": "*", "binding": BINDING},
            {"object_key": OBJECT_KEY, "encryption_profile": authority.S3_ENCRYPTION_PROFILE, "if_none_match": "etag", "binding": BINDING},
            {"object_key": OBJECT_KEY, "encryption_profile": authority.S3_ENCRYPTION_PROFILE, "if_none_match": "*", "binding": replace(BINDING, config=replace(CONFIG, bucket="other-bucket"))},
        )
        for values in bad_calls:
            with self.subTest(values=values):
                self.assert_safe_failure(lambda values=values: adapter.publish_and_read_back(plaintext=PLAINTEXT, **values))
        other_identity = uuid.UUID("87654321-4321-4abc-8def-ba0987654321")
        same_digest_wrong_identity = (
            f"{authority.S3_PREFIX}{other_identity}/"
            f"{hashlib.sha256(PLAINTEXT).hexdigest()}.age"
        )
        self.assert_safe_failure(
            lambda: adapter.publish_and_read_back(
                object_key=same_digest_wrong_identity,
                plaintext=PLAINTEXT,
                encryption_profile=authority.S3_ENCRYPTION_PROFILE,
                if_none_match="*",
                binding=BINDING,
            )
        )

    def test_adp_010_subprocess_age_uses_closed_argv_env_fds_and_no_stderr(self):
        source = inspect.getsource(materialize.AgeSubprocess)
        for required in ("shell=False", "stderr=subprocess.DEVNULL", "close_fds=True", "pass_fds=", '"LANG": "C"', '"LC_ALL": "C"'):
            self.assertIn(required, source)
        for forbidden in ("os.environ", "capture_output", "shell=True", "communicate("):
            self.assertNotIn(forbidden, source)

    def test_adp_011_subprocess_age_timeout_nonzero_and_oversize_are_constant(self):
        with tempfile.TemporaryDirectory() as directory:
            identity_path = os.path.join(directory, "identity")
            with open(identity_path, "wb") as stream:
                stream.write(b"AGE-SECRET-KEY-1" + (b"Q" * 58) + b"\n")
            os.chmod(identity_path, 0o600)
            identity_fd = os.open(identity_path, os.O_RDONLY | os.O_NOFOLLOW)
            self.addCleanup(os.close, identity_fd)
            age = materialize.AgeSubprocess("/opt/age/age", identity_fd, timeout_seconds=1)
            for error in (
                subprocess.TimeoutExpired(["age"], 1),
                materialize._ProcessFailed(),
                materialize._ProcessOversize(),
            ):
                with self.subTest(error=type(error).__name__):
                    with patch.object(age, "_execute", side_effect=error) as execute:
                        self.assert_safe_failure(lambda: age.decrypt(CIPHERTEXT))
                    execute.assert_called_once()
            with open(identity_path, "r+b") as stream:
                stream.seek(len(b"AGE-SECRET-KEY-1"))
                stream.write(b"P")
                stream.flush()
                os.fsync(stream.fileno())
            with patch.object(age, "_execute", return_value=PLAINTEXT) as execute:
                self.assert_safe_failure(lambda: age.decrypt(CIPHERTEXT))
            execute.assert_not_called()

    def test_adp_012_runner_marker_scope_and_no_generic_or_django_api(self):
        source = inspect.getsource(materialize).lower()
        for forbidden in (
            "list_objects",
            "delete_object",
            "head_object",
            "upload_file",
            "download_file",
            "django",
            "os.environ",
            "credential_process",
        ):
            self.assertNotIn(forbidden, source)
        self.assertEqual(
            set(materialize.__all__),
            {
                "AgeSubprocess",
                "MAX_RUNNER_OUTPUT_BYTES",
                "SelectelS3Authority",
                "decode_receipt_marker",
                "encode_receipt_marker",
                "materialize_once",
            },
        )
        identity = uuid.UUID("12345678-1234-4abc-8def-1234567890ab")
        receipt = authority.S3ZeroLedgerReceipt(
            identity=identity,
            generation=1,
            row_count=0,
            plaintext_sha256="a" * 64,
            encryption_profile=authority.S3_ENCRYPTION_PROFILE,
            recipient_sha256=BINDING.recipient_sha256,
            authority_config_sha256=BINDING.authority_config_sha256,
            object_key=f"{authority.S3_PREFIX}{identity}/{'a' * 64}.age",
            object_version_id_b64="dmVyc2lvbg",
            ciphertext_size=len(CIPHERTEXT),
            ciphertext_sha256=hashlib.sha256(CIPHERTEXT).hexdigest(),
        )
        marker = materialize.encode_receipt_marker(receipt)
        self.assertLessEqual(len(marker), materialize.MAX_RUNNER_OUTPUT_BYTES)
        self.assertEqual(materialize.decode_receipt_marker(marker), receipt)
        self.assert_safe_failure(
            lambda: materialize.decode_receipt_marker(marker + b"EXTRA")
        )
        for bad_marker in (
            marker.replace(b"\n", b"\r\n"),
            marker[:-1] + b"=\n",
            marker + b"SECOND\n",
            b"X" * (materialize.MAX_RUNNER_OUTPUT_BYTES + 1),
        ):
            with self.subTest(size=len(bad_marker)):
                self.assert_safe_failure(
                    lambda bad_marker=bad_marker: materialize.decode_receipt_marker(
                        bad_marker
                    )
                )
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o700)
            primary_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            self.addCleanup(os.close, primary_fd)
            with (
                patch.object(materialize, "_build_selectel_client", return_value="CLIENT") as build,
                patch.object(materialize, "AgeSubprocess", return_value="AGE") as age_port,
                patch.object(materialize, "SelectelS3Authority", return_value="REMOTE") as remote,
                patch.object(authority, "create_s3_zero_genesis", return_value=receipt) as create,
            ):
                self.assertEqual(
                    materialize.materialize_once(
                        primary_fd, CONFIG, 12, 13, "/opt/age/age"
                    ),
                    marker,
                )
            build.assert_called_once_with(CONFIG, 12)
            age_port.assert_called_once_with("/opt/age/age", 13)
            remote.assert_called_once_with(config=CONFIG, client="CLIENT", age="AGE")
            create.assert_called_once_with(primary_fd, CONFIG, "REMOTE")
            os.chmod(directory, 0o750)
            with patch.object(materialize, "_build_selectel_client") as build:
                self.assert_safe_failure(
                    lambda: materialize.materialize_once(
                        primary_fd, CONFIG, -1, -1, "/opt/age/age"
                    )
                )
            build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
