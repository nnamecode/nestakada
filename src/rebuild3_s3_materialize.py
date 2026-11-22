"""Narrow operational adapter for the D-1848 zero-ledger S3 authority."""

from __future__ import annotations

import hashlib
import base64
import binascii
import os
import stat
import subprocess
import threading
import uuid
from typing import Protocol
from urllib.parse import urlsplit

import rebuild3_zero_ledger as authority


_RECEIPT_MARKER = b"RB3_ZLG_RECEIPT="
MAX_RUNNER_OUTPUT_BYTES = 8192
_MAX_SECRET_HANDLE_BYTES = 512
__all__ = (
    "AgeSubprocess",
    "MAX_RUNNER_OUTPUT_BYTES",
    "SelectelS3Authority",
    "decode_receipt_marker",
    "encode_receipt_marker",
    "materialize_once",
)


class _ProcessFailed(Exception):
    pass


class _ProcessOversize(Exception):
    pass


class _S3Client(Protocol):
    def get_bucket_versioning(self, **kwargs): ...

    def put_object(self, **kwargs): ...

    def get_object(self, **kwargs): ...


class _AgePort(Protocol):
    def encrypt(self, plaintext: bytes, recipient: str) -> bytes: ...

    def decrypt(self, ciphertext: bytes) -> bytes: ...


def _fail() -> None:
    raise authority.ZeroLedgerError("zero-ledger")


def _bytes(value: object, minimum: int, maximum: int) -> bytes:
    if not isinstance(value, bytes) or not minimum <= len(value) <= maximum:
        _fail()
    return value


def _version(value: object) -> tuple[str, bytes]:
    if not isinstance(value, str):
        _fail()
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        _fail()
    if not 1 <= len(encoded) <= 1024 or b"\x00" in encoded:
        _fail()
    return value, encoded


def _http_status(error: BaseException) -> int | None:
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return None
    metadata = response.get("ResponseMetadata")
    if not isinstance(metadata, dict):
        return None
    status = metadata.get("HTTPStatusCode")
    if isinstance(status, bool) or not isinstance(status, int):
        return None
    return status


def _validate_readonly_handle(fd: object, maximum: int) -> os.stat_result:
    if isinstance(fd, bool) or not isinstance(fd, int) or fd < 0:
        _fail()
    try:
        import fcntl

        state = os.fstat(fd)
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    except BaseException:
        _fail()
    if (
        not stat.S_ISREG(state.st_mode)
        or state.st_uid != os.geteuid()
        or state.st_nlink != 1
        or state.st_mode & 0o077
        or flags & os.O_ACCMODE != os.O_RDONLY
        or not 1 <= state.st_size <= maximum
    ):
        _fail()
    return state


def _read_s3_secret_handle(fd: int) -> tuple[str, str]:
    state = _validate_readonly_handle(fd, _MAX_SECRET_HANDLE_BYTES)
    try:
        payload = os.pread(fd, _MAX_SECRET_HANDLE_BYTES + 1, 0)
    except BaseException:
        _fail()
    if len(payload) != state.st_size or not payload.endswith(b"\n") or b"\r" in payload:
        _fail()
    lines = payload.splitlines()
    if len(lines) != 2:
        _fail()
    prefixes = (b"access_key_id=", b"secret_access_key=")
    values: list[str] = []
    for line, prefix, minimum, maximum in zip(
        lines,
        prefixes,
        (16, 20),
        (128, 256),
        strict=True,
    ):
        if not line.startswith(prefix):
            _fail()
        raw = line[len(prefix) :]
        if not minimum <= len(raw) <= maximum or any(byte < 0x21 or byte > 0x7E for byte in raw):
            _fail()
        values.append(raw.decode("ascii"))
    return values[0], values[1]


def _load_sdk():
    try:
        from boto3.session import Session
        from botocore.config import Config
    except BaseException:
        _fail()
    return Session, Config


def _request_origin_guard(endpoint_origin: str, bucket: str):
    def guard(request, **kwargs) -> None:
        del kwargs
        url = getattr(request, "url", None)
        if not isinstance(url, str):
            _fail()
        try:
            parsed = urlsplit(url)
        except ValueError:
            _fail()
        if (
            f"{parsed.scheme}://{parsed.netloc}" != endpoint_origin
            or not (parsed.path == f"/{bucket}" or parsed.path.startswith(f"/{bucket}/"))
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or parsed.fragment
        ):
            _fail()

    return guard


def _build_selectel_client(
    config: authority.S3AuthorityConfig,
    s3_secret_fd: int,
):
    try:
        authority._s3_binding(config)
        access_key_id, secret_access_key = _read_s3_secret_handle(s3_secret_fd)
        session_factory, config_factory = _load_sdk()
        session = session_factory(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=config.region_pool,
        )
        sdk_config = config_factory(
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=10,
            retries={"total_max_attempts": 1, "mode": "standard"},
            s3={"addressing_style": "path"},
            proxies={},
            ignore_configured_endpoint_urls=True,
        )
        client = session.client(
            "s3",
            endpoint_url=config.endpoint_origin,
            region_name=config.region_pool,
            use_ssl=True,
            verify=True,
            config=sdk_config,
        )
        events = getattr(getattr(client, "meta", None), "events", None)
        register = getattr(events, "register_first", None)
        if not callable(register):
            _fail()
        register(
            "before-send.s3",
            _request_origin_guard(config.endpoint_origin, config.bucket),
            unique_id="estakada-zero-ledger-origin-v1",
        )
        return client
    except authority.ZeroLedgerError:
        raise
    except BaseException:
        _fail()


def encode_receipt_marker(receipt: authority.S3ZeroLedgerReceipt) -> bytes:
    payload = authority.encode_s3_receipt(receipt)
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    marker = _RECEIPT_MARKER + encoded + b"\n"
    if len(marker) > MAX_RUNNER_OUTPUT_BYTES:
        _fail()
    return marker


def decode_receipt_marker(marker: bytes) -> authority.S3ZeroLedgerReceipt:
    if (
        not isinstance(marker, bytes)
        or not 1 <= len(marker) <= MAX_RUNNER_OUTPUT_BYTES
        or not marker.startswith(_RECEIPT_MARKER)
        or not marker.endswith(b"\n")
        or marker.count(b"\n") != 1
        or b"\r" in marker
    ):
        _fail()
    encoded = marker[len(_RECEIPT_MARKER) : -1]
    if not encoded or b"=" in encoded:
        _fail()
    try:
        payload = base64.b64decode(
            encoded + (b"=" * (-len(encoded) % 4)),
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError):
        _fail()
    receipt = authority.decode_s3_receipt(payload)
    if encode_receipt_marker(receipt) != marker:
        _fail()
    return receipt


class AgeSubprocess:
    """Closed age CLI boundary with bounded binary pipes and no ambient env."""

    def __init__(
        self,
        binary: str,
        identity_fd: int,
        *,
        timeout_seconds: int = 10,
    ) -> None:
        if (
            not isinstance(binary, str)
            or not binary.startswith("/")
            or "\x00" in binary
            or len(binary.encode("utf-8")) > 512
            or isinstance(identity_fd, bool)
            or not isinstance(identity_fd, int)
            or identity_fd < 0
            or isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or not 1 <= timeout_seconds <= 60
        ):
            _fail()
        self._binary = binary
        self._identity_fd = identity_fd
        self._timeout = timeout_seconds
        state = _validate_readonly_handle(identity_fd, 256)
        try:
            identity = os.pread(identity_fd, 257, 0)
        except BaseException:
            _fail()
        prefix = b"AGE-SECRET-KEY-1"
        allowed = b"023456789ACDEFGHJKLMNPQRSTUVWXYZ"
        if (
            len(identity) != state.st_size
            or not identity.endswith(b"\n")
            or not identity.startswith(prefix)
            or len(identity) != len(prefix) + 58 + 1
            or any(byte not in allowed for byte in identity[len(prefix) : -1])
        ):
            _fail()
        self._identity_stat = (
            state.st_dev,
            state.st_ino,
            stat.S_IMODE(state.st_mode),
            state.st_uid,
            state.st_nlink,
            state.st_size,
            state.st_mtime_ns,
            state.st_ctime_ns,
        )
        self._identity_sha256 = hashlib.sha256(identity).digest()

    def _assert_identity(self) -> None:
        state = _validate_readonly_handle(self._identity_fd, 256)
        current_stat = (
            state.st_dev,
            state.st_ino,
            stat.S_IMODE(state.st_mode),
            state.st_uid,
            state.st_nlink,
            state.st_size,
            state.st_mtime_ns,
            state.st_ctime_ns,
        )
        try:
            identity = os.pread(self._identity_fd, 257, 0)
        except BaseException:
            _fail()
        if (
            current_stat != self._identity_stat
            or len(identity) != state.st_size
            or hashlib.sha256(identity).digest() != self._identity_sha256
        ):
            _fail()

    def _execute(
        self,
        arguments: tuple[str, ...],
        payload: bytes,
        output_cap: int,
        *,
        use_identity: bool,
    ) -> bytes:
        process = None
        reader = None
        output: list[bytes] = []
        read_error: list[BaseException] = []
        pass_fds = (self._identity_fd,) if use_identity else ()
        try:
            process = subprocess.Popen(
                (self._binary, *arguments),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                shell=False,
                close_fds=True,
                pass_fds=pass_fds,
                env={"LANG": "C", "LC_ALL": "C"},
            )
            if process.stdin is None or process.stdout is None:
                raise _ProcessFailed()
            try:
                process.stdin.write(payload)
                process.stdin.close()
            except (BrokenPipeError, OSError):
                raise _ProcessFailed() from None

            def read_output() -> None:
                try:
                    output.append(process.stdout.read(output_cap + 1))
                except BaseException as exc:
                    read_error.append(exc)

            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            reader.join(self._timeout)
            if reader.is_alive():
                process.kill()
                process.wait()
                reader.join()
                raise subprocess.TimeoutExpired((self._binary, *arguments), self._timeout)
            if read_error or len(output) != 1 or not isinstance(output[0], bytes):
                raise _ProcessFailed()
            if len(output[0]) > output_cap:
                process.kill()
                process.wait()
                raise _ProcessOversize()
            try:
                return_code = process.wait(timeout=self._timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise
            if return_code != 0:
                raise _ProcessFailed()
            return output[0]
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if process.stdin is not None:
                    process.stdin.close()
                if process.stdout is not None:
                    process.stdout.close()
            if reader is not None and reader.is_alive():
                reader.join()

    def encrypt(self, plaintext: bytes, recipient: str) -> bytes:
        payload = _bytes(plaintext, authority.MAX_BYTES, authority.MAX_BYTES)
        if (
            not isinstance(recipient, str)
            or authority.S3_AGE_RECIPIENT.fullmatch(recipient) is None
        ):
            _fail()
        try:
            ciphertext = self._execute(
                ("--encrypt", "--recipient", recipient),
                payload,
                authority.S3_MAX_CIPHERTEXT_BYTES,
                use_identity=False,
            )
        except BaseException:
            _fail()
        return _bytes(ciphertext, 1, authority.S3_MAX_CIPHERTEXT_BYTES)

    def decrypt(self, ciphertext: bytes) -> bytes:
        payload = _bytes(ciphertext, 1, authority.S3_MAX_CIPHERTEXT_BYTES)
        try:
            self._assert_identity()
            plaintext = self._execute(
                ("--decrypt", "--identity", f"/proc/self/fd/{self._identity_fd}"),
                payload,
                authority.MAX_BYTES,
                use_identity=True,
            )
        except BaseException:
            _fail()
        return _bytes(plaintext, authority.MAX_BYTES, authority.MAX_BYTES)


class SelectelS3Authority:
    """Explicit Selectel implementation of the narrow S3AuthorityPort."""

    def __init__(
        self,
        *,
        config: authority.S3AuthorityConfig,
        client: _S3Client,
        age: _AgePort,
    ) -> None:
        try:
            expected = authority._s3_binding(config)
        except authority.ZeroLedgerError:
            raise
        except BaseException:
            _fail()
        self._config = config
        self._binding = expected
        self._client = client
        self._age = age

    def _check_binding(self, binding: object) -> authority.S3AuthorityBinding:
        if binding != self._binding:
            _fail()
        return self._binding

    def _check_common(
        self,
        object_key: object,
        encryption_profile: object,
        binding: object,
    ) -> tuple[str, authority.S3AuthorityBinding]:
        checked = self._check_binding(binding)
        if not isinstance(object_key, str) or "\x00" in object_key:
            _fail()
        try:
            encoded = object_key.encode("ascii")
        except UnicodeEncodeError:
            _fail()
        if not 1 <= len(encoded) <= 512:
            _fail()
        if not object_key.startswith(authority.S3_PREFIX) or not object_key.endswith(".age"):
            _fail()
        relative = object_key[len(authority.S3_PREFIX) : -4]
        parts = relative.split("/")
        if len(parts) != 2 or authority.SHA256.fullmatch(parts[1]) is None:
            _fail()
        try:
            identity = uuid.UUID(parts[0])
        except (AttributeError, TypeError, ValueError):
            _fail()
        if not authority._valid_uuid4(identity) or str(identity) != parts[0]:
            _fail()
        if encryption_profile != authority.S3_ENCRYPTION_PROFILE:
            _fail()
        return object_key, checked

    def get_bucket_versioning(
        self,
        *,
        binding: authority.S3AuthorityBinding,
    ) -> authority.S3VersioningProof:
        checked = self._check_binding(binding)
        try:
            response = self._client.get_bucket_versioning(
                Bucket=self._config.bucket,
            )
        except BaseException:
            _fail()
        if not isinstance(response, dict):
            _fail()
        state = response.get("Status")
        if state is not None and not isinstance(state, str):
            _fail()
        return authority.S3VersioningProof(
            state=state,
            authority_config_sha256=checked.authority_config_sha256,
            recipient_sha256=checked.recipient_sha256,
        )

    def _read_ciphertext(
        self,
        *,
        object_key: str,
        version: str,
    ) -> bytes:
        body = None
        close_failed = False
        try:
            try:
                response = self._client.get_object(
                    Bucket=self._config.bucket,
                    Key=object_key,
                    VersionId=version,
                )
            except BaseException:
                _fail()
            if not isinstance(response, dict):
                _fail()
            actual_version, _ = _version(response.get("VersionId"))
            if actual_version != version:
                _fail()
            content_length = response.get("ContentLength")
            if (
                isinstance(content_length, bool)
                or not isinstance(content_length, int)
                or not 1 <= content_length <= authority.S3_MAX_CIPHERTEXT_BYTES
            ):
                _fail()
            body = response.get("Body")
            read = getattr(body, "read", None)
            close = getattr(body, "close", None)
            if not callable(read) or not callable(close):
                _fail()
            try:
                ciphertext = read(authority.S3_MAX_CIPHERTEXT_BYTES + 1)
            except BaseException:
                _fail()
            value = _bytes(ciphertext, 1, authority.S3_MAX_CIPHERTEXT_BYTES)
            if len(value) != content_length:
                _fail()
            return value
        finally:
            if body is not None:
                try:
                    body.close()
                except BaseException:
                    close_failed = True
            if close_failed:
                _fail()

    def publish_and_read_back(
        self,
        *,
        object_key: str,
        plaintext: bytes,
        encryption_profile: str,
        if_none_match: str,
        binding: authority.S3AuthorityBinding,
    ) -> authority.S3PublishProof:
        key, checked = self._check_common(
            object_key,
            encryption_profile,
            binding,
        )
        payload = _bytes(plaintext, authority.MAX_BYTES, authority.MAX_BYTES)
        try:
            identity = authority._parse(payload)
        except authority.ZeroLedgerError:
            raise
        except BaseException:
            _fail()
        if key != authority._s3_object_key(identity, hashlib.sha256(payload).hexdigest()):
            _fail()
        if if_none_match != authority.S3_IF_NONE_MATCH:
            _fail()
        try:
            ciphertext = self._age.encrypt(payload, self._config.recipient)
        except authority.ZeroLedgerError:
            raise
        except BaseException:
            _fail()
        encrypted = _bytes(ciphertext, 1, authority.S3_MAX_CIPHERTEXT_BYTES)
        try:
            response = self._client.put_object(
                Bucket=self._config.bucket,
                Key=key,
                Body=encrypted,
                IfNoneMatch=authority.S3_IF_NONE_MATCH,
            )
        except BaseException as exc:
            if _http_status(exc) == 412:
                _fail()
            raise authority.S3AmbiguousUpload(
                authority.S3UnknownVersionResult(key, "UNKNOWN_VERSION")
            ) from None
        if not isinstance(response, dict):
            raise authority.S3AmbiguousUpload(
                authority.S3UnknownVersionResult(key, "UNKNOWN_VERSION")
            )
        try:
            version, version_bytes = _version(response.get("VersionId"))
        except authority.ZeroLedgerError:
            raise authority.S3AmbiguousUpload(
                authority.S3UnknownVersionResult(key, "UNKNOWN_VERSION")
            ) from None
        downloaded = self._read_ciphertext(object_key=key, version=version)
        if downloaded != encrypted:
            _fail()
        try:
            recovered = self._age.decrypt(downloaded)
        except authority.ZeroLedgerError:
            raise
        except BaseException:
            _fail()
        if recovered != payload:
            _fail()
        return authority.S3PublishProof(
            version_id=version_bytes,
            ciphertext_size=len(encrypted),
            ciphertext_sha256=hashlib.sha256(encrypted).hexdigest(),
            plaintext=recovered,
            authority_config_sha256=checked.authority_config_sha256,
            recipient_sha256=checked.recipient_sha256,
        )

    def read_exact(
        self,
        *,
        object_key: str,
        version_id: bytes,
        encryption_profile: str,
        binding: authority.S3AuthorityBinding,
    ) -> authority.S3ReadProof:
        key, checked = self._check_common(
            object_key,
            encryption_profile,
            binding,
        )
        raw = _bytes(version_id, 1, 1024)
        if b"\x00" in raw:
            _fail()
        try:
            version = raw.decode("utf-8")
        except UnicodeDecodeError:
            _fail()
        ciphertext = self._read_ciphertext(object_key=key, version=version)
        try:
            plaintext = self._age.decrypt(ciphertext)
        except authority.ZeroLedgerError:
            raise
        except BaseException:
            _fail()
        recovered = _bytes(plaintext, authority.MAX_BYTES, authority.MAX_BYTES)
        return authority.S3ReadProof(
            ciphertext_size=len(ciphertext),
            ciphertext_sha256=hashlib.sha256(ciphertext).hexdigest(),
            plaintext=recovered,
            authority_config_sha256=checked.authority_config_sha256,
            recipient_sha256=checked.recipient_sha256,
        )


def _preflight_primary(primary_root_fd: int):
    try:
        root = authority._root_identity(primary_root_fd)
        entries = os.listdir(primary_root_fd)
    except authority.ZeroLedgerError:
        raise
    except BaseException:
        _fail()
    if entries:
        _fail()
    return root


def materialize_once(
    primary_root_fd: int,
    config: authority.S3AuthorityConfig,
    s3_secret_fd: int,
    age_identity_fd: int,
    age_binary: str,
) -> bytes:
    root = _preflight_primary(primary_root_fd)
    client = _build_selectel_client(config, s3_secret_fd)
    age = AgeSubprocess(age_binary, age_identity_fd)
    authority._assert_root(primary_root_fd, root)
    try:
        if os.listdir(primary_root_fd):
            _fail()
    except authority.ZeroLedgerError:
        raise
    except BaseException:
        _fail()
    remote = SelectelS3Authority(config=config, client=client, age=age)
    receipt = authority.create_s3_zero_genesis(primary_root_fd, config, remote)
    return encode_receipt_marker(receipt)
