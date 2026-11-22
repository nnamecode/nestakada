from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
import json
import os
import re
import stat
import uuid
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from rebuild3_importer.source import SNAPSHOT_ID, VerifiedLedgerEvidence


SCHEMA = "estakada.zero-request-ledger-genesis"
FILENAME = "zero-ledger-genesis-v1.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IDENTITY_BYTES = re.compile(
    rb'^\{"schema":"estakada\.zero-request-ledger-genesis","version":1,'
    rb'"identity":"([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})",'
    rb'"generation":1,"row_count":0\}\n$'
)


class ZeroLedgerError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True, repr=False)
class ZeroLedgerReceipt:
    identity: uuid.UUID
    generation: int
    digest: str
    row_count: int


@dataclass(frozen=True, slots=True)
class _RootIdentity:
    dev: int
    ino: int
    mode: int
    uid: int


@dataclass(frozen=True, slots=True)
class _FileIdentity:
    dev: int
    ino: int
    mode: int
    uid: int
    nlink: int
    size: int
    mtime_ns: int
    ctime_ns: int


def _canonical(identity: uuid.UUID) -> bytes:
    return (
        f'{{"schema":"{SCHEMA}","version":1,"identity":"{identity}",'
        '"generation":1,"row_count":0}\n'
    ).encode("ascii")


MAX_BYTES = len(_canonical(uuid.UUID("ffffffff-ffff-4fff-bfff-ffffffffffff")))


def _fail() -> None:
    raise ZeroLedgerError("zero-ledger")


def _root_identity(fd: int) -> _RootIdentity:
    value = os.fstat(fd)
    identity = _RootIdentity(
        value.st_dev,
        value.st_ino,
        stat.S_IMODE(value.st_mode),
        value.st_uid,
    )
    if (
        not stat.S_ISDIR(value.st_mode)
        or identity.uid != os.geteuid()
        or identity.mode != 0o700
    ):
        _fail()
    return identity


def _assert_root(fd: int, expected: _RootIdentity) -> None:
    if _root_identity(fd) != expected:
        _fail()


def _roots_independent(left: _RootIdentity, right: _RootIdentity) -> bool:
    return left.dev != right.dev


def _duplicate_roots(primary_root_fd: int, independent_root_fd: int) -> tuple[int, int]:
    if (
        isinstance(primary_root_fd, bool)
        or not isinstance(primary_root_fd, int)
        or primary_root_fd < 0
        or isinstance(independent_root_fd, bool)
        or not isinstance(independent_root_fd, int)
        or independent_root_fd < 0
    ):
        _fail()
    primary = os.dup(primary_root_fd)
    try:
        independent = os.dup(independent_root_fd)
    except Exception:
        os.close(primary)
        raise
    return primary, independent


def _close_pair(primary_fd: int | None, independent_fd: int | None) -> None:
    failed = False
    if independent_fd is not None:
        try:
            os.close(independent_fd)
        except Exception:
            failed = True
    if primary_fd is not None:
        try:
            os.close(primary_fd)
        except Exception:
            failed = True
    if failed:
        raise ZeroLedgerError("zero-ledger") from None


def _root_pair(primary_fd: int, independent_fd: int) -> tuple[_RootIdentity, _RootIdentity]:
    primary = _root_identity(primary_fd)
    independent = _root_identity(independent_fd)
    if not _roots_independent(primary, independent):
        _fail()
    return primary, independent


def _file_identity(value: os.stat_result, root: _RootIdentity, size: int) -> _FileIdentity:
    identity = _FileIdentity(
        value.st_dev,
        value.st_ino,
        stat.S_IMODE(value.st_mode),
        value.st_uid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
    if (
        not stat.S_ISREG(value.st_mode)
        or identity.dev != root.dev
        or identity.uid != os.geteuid()
        or identity.mode != 0o600
        or identity.nlink != 1
        or identity.size != size
    ):
        _fail()
    return identity


def _held_file(fd: int, root: _RootIdentity, size: int) -> _FileIdentity:
    return _file_identity(os.fstat(fd), root, size)


def _assert_named(root_fd: int, root: _RootIdentity, held: _FileIdentity) -> None:
    _assert_root(root_fd, root)
    named = _file_identity(
        os.stat(FILENAME, dir_fd=root_fd, follow_symlinks=False),
        root,
        held.size,
    )
    if named != held:
        _fail()


def _open_flags(base: int) -> int:
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    if not isinstance(no_follow, int) or no_follow == 0:
        _fail()
    return base | no_follow | getattr(os, "O_CLOEXEC", 0)


def _write_all(fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if isinstance(written, bool) or not isinstance(written, int) or written <= 0:
            _fail()
        offset += written


def _write_copy(root_fd: int, root: _RootIdentity, payload: bytes) -> None:
    file_fd: int | None = None
    try:
        file_fd = os.open(
            FILENAME,
            _open_flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL),
            0o600,
            dir_fd=root_fd,
        )
        created = _held_file(file_fd, root, 0)
        _assert_named(root_fd, root, created)
        _write_all(file_fd, payload)
        os.fsync(file_fd)
        held = _held_file(file_fd, root, len(payload))
        if (
            held.dev,
            held.ino,
            held.mode,
            held.uid,
            held.nlink,
        ) != (
            created.dev,
            created.ino,
            created.mode,
            created.uid,
            created.nlink,
        ):
            _fail()
        _assert_named(root_fd, root, held)
        _assert_named(root_fd, root, held)
        os.fsync(root_fd)
        held = _held_file(file_fd, root, len(payload))
        _assert_named(root_fd, root, held)
        closing = file_fd
        file_fd = None
        os.close(closing)
    finally:
        if file_fd is not None:
            os.close(file_fd)


def _open_copy(root_fd: int, root: _RootIdentity) -> tuple[int, bytes, _FileIdentity]:
    file_fd = os.open(FILENAME, _open_flags(os.O_RDONLY), dir_fd=root_fd)
    try:
        before = _held_file(file_fd, root, MAX_BYTES)
        payload = os.read(file_fd, MAX_BYTES + 1)
        if len(payload) != MAX_BYTES or os.read(file_fd, 1) != b"":
            _fail()
        after = _held_file(file_fd, root, MAX_BYTES)
        if after != before:
            _fail()
        _assert_named(root_fd, root, after)
        return file_fd, payload, after
    except Exception:
        os.close(file_fd)
        raise


def _valid_uuid4(value: object) -> bool:
    return (
        isinstance(value, uuid.UUID)
        and value.int != 0
        and value.version == 4
        and value.variant == uuid.RFC_4122
        and str(value) == str(value).lower()
    )


def _validate_receipt(receipt: object) -> ZeroLedgerReceipt:
    if (
        not isinstance(receipt, ZeroLedgerReceipt)
        or not _valid_uuid4(receipt.identity)
        or isinstance(receipt.generation, bool)
        or receipt.generation != 1
        or not isinstance(receipt.digest, str)
        or SHA256.fullmatch(receipt.digest) is None
        or isinstance(receipt.row_count, bool)
        or receipt.row_count != 0
    ):
        _fail()
    return receipt


def _parse(payload: bytes) -> uuid.UUID:
    match = IDENTITY_BYTES.fullmatch(payload)
    if match is None:
        _fail()
    identity = uuid.UUID(match.group(1).decode("ascii"))
    if not _valid_uuid4(identity) or _canonical(identity) != payload:
        _fail()
    return identity


def _read_pair(
    primary_fd: int,
    independent_fd: int,
    primary_root: _RootIdentity,
    independent_root: _RootIdentity,
    receipt: ZeroLedgerReceipt,
) -> None:
    primary_file: int | None = None
    independent_file: int | None = None
    try:
        primary_file, primary_payload, primary_state = _open_copy(primary_fd, primary_root)
        independent_file, independent_payload, independent_state = _open_copy(
            independent_fd,
            independent_root,
        )
        if primary_payload != independent_payload:
            _fail()
        identity = _parse(primary_payload)
        digest = hashlib.sha256(primary_payload).hexdigest()
        if identity != receipt.identity or digest != receipt.digest:
            _fail()
        primary_final = _held_file(primary_file, primary_root, MAX_BYTES)
        independent_final = _held_file(independent_file, independent_root, MAX_BYTES)
        if primary_final != primary_state or independent_final != independent_state:
            _fail()
        _assert_named(primary_fd, primary_root, primary_final)
        _assert_named(independent_fd, independent_root, independent_final)
    finally:
        closing_independent = independent_file
        closing_primary = primary_file
        independent_file = None
        primary_file = None
        _close_pair(closing_primary, closing_independent)


def create_zero_genesis(primary_root_fd: int, independent_root_fd: int) -> ZeroLedgerReceipt:
    primary_fd: int | None = None
    independent_fd: int | None = None
    try:
        primary_fd, independent_fd = _duplicate_roots(primary_root_fd, independent_root_fd)
        primary_root, independent_root = _root_pair(primary_fd, independent_fd)
        identity = uuid.uuid4()
        if not _valid_uuid4(identity):
            _fail()
        payload = _canonical(identity)
        receipt = ZeroLedgerReceipt(identity, 1, hashlib.sha256(payload).hexdigest(), 0)
        _write_copy(independent_fd, independent_root, payload)
        _write_copy(primary_fd, primary_root, payload)
        _read_pair(primary_fd, independent_fd, primary_root, independent_root, receipt)
        return receipt
    except ZeroLedgerError:
        raise
    except Exception:
        raise ZeroLedgerError("zero-ledger") from None
    finally:
        closing_independent = independent_fd
        closing_primary = primary_fd
        independent_fd = None
        primary_fd = None
        _close_pair(closing_primary, closing_independent)


def verify_zero_genesis(
    primary_root_fd: int,
    independent_root_fd: int,
    expected_receipt: ZeroLedgerReceipt,
    snapshot_id: str,
) -> VerifiedLedgerEvidence:
    primary_fd: int | None = None
    independent_fd: int | None = None
    try:
        receipt = _validate_receipt(expected_receipt)
        if not isinstance(snapshot_id, str) or SNAPSHOT_ID.fullmatch(snapshot_id) is None:
            _fail()
        primary_fd, independent_fd = _duplicate_roots(primary_root_fd, independent_root_fd)
        primary_root, independent_root = _root_pair(primary_fd, independent_fd)
        _read_pair(primary_fd, independent_fd, primary_root, independent_root, receipt)
        return VerifiedLedgerEvidence(receipt.identity, 1, receipt.digest, 0, snapshot_id)
    except ZeroLedgerError:
        raise
    except Exception:
        raise ZeroLedgerError("zero-ledger") from None
    finally:
        closing_independent = independent_fd
        closing_primary = primary_fd
        independent_fd = None
        primary_fd = None
        _close_pair(closing_primary, closing_independent)


# D-1848 S3 authority amendment. The original two-POSIX API above remains
# historical evidence and is not used by this explicit S3 topology.
S3_RECEIPT_SCHEMA = "estakada.zero-request-ledger-s3-receipt"
S3_CONFIG_SCHEMA = "estakada.zero-request-ledger-s3-config"
S3_PREFIX = "estakada/zero-ledger/v1/"
S3_ENCRYPTION_PROFILE = "age-x25519-v1-binary"
S3_PROVIDER = "selectel"
S3_VERSIONING_ENABLED = "Enabled"
S3_IF_NONE_MATCH = "*"
S3_MAX_CIPHERTEXT_BYTES = 4096
S3_MAX_RECEIPT_BYTES = 4096
S3_REGION_POOL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$")
S3_BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
S3_VERSION_B64 = re.compile(r"^[A-Za-z0-9_-]{2,1366}$")
S3_AGE_RECIPIENT = re.compile(r"^age1[023456789acdefghjklmnpqrstuvwxyz]{58}$")


@dataclass(frozen=True, slots=True, repr=False)
class S3AuthorityConfig:
    endpoint_origin: str
    region_pool: str
    bucket: str
    recipient: str


@dataclass(frozen=True, slots=True, repr=False)
class S3AuthorityBinding:
    config: S3AuthorityConfig
    authority_config_sha256: str
    recipient_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class S3VersioningProof:
    state: str
    authority_config_sha256: str
    recipient_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class S3PublishProof:
    version_id: bytes
    ciphertext_size: int
    ciphertext_sha256: str
    plaintext: bytes
    authority_config_sha256: str
    recipient_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class S3ReadProof:
    ciphertext_size: int
    ciphertext_sha256: str
    plaintext: bytes
    authority_config_sha256: str
    recipient_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class S3UnknownVersionResult:
    object_key: str
    state: str


class S3AmbiguousUpload(ZeroLedgerError):
    def __init__(self, result: S3UnknownVersionResult):
        super().__init__("zero-ledger")
        self.result = result


@dataclass(frozen=True, slots=True, repr=False)
class S3ZeroLedgerReceipt:
    identity: uuid.UUID
    generation: int
    row_count: int
    plaintext_sha256: str
    encryption_profile: str
    recipient_sha256: str
    authority_config_sha256: str
    object_key: str
    object_version_id_b64: str
    ciphertext_size: int
    ciphertext_sha256: str


class S3AuthorityPort(Protocol):
    def get_bucket_versioning(
        self,
        *,
        binding: S3AuthorityBinding,
    ) -> S3VersioningProof: ...

    def publish_and_read_back(
        self,
        *,
        object_key: str,
        plaintext: bytes,
        encryption_profile: str,
        if_none_match: str,
        binding: S3AuthorityBinding,
    ) -> S3PublishProof: ...

    def read_exact(
        self,
        *,
        object_key: str,
        version_id: bytes,
        encryption_profile: str,
        binding: S3AuthorityBinding,
    ) -> S3ReadProof: ...


def _s3_valid_sha(value: object) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _s3_ascii(value: object, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        _fail()
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError:
        _fail()
    if not minimum <= len(encoded) <= maximum:
        _fail()
    return value


def _s3_canonical_json(pairs: tuple[tuple[str, object], ...]) -> bytes:
    return (
        json.dumps(
            {key: value for key, value in pairs},
            ensure_ascii=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def _s3_dns_host(value: str) -> bool:
    if len(value) > 253 or value.endswith("."):
        return False
    labels = value.split(".")
    return len(labels) >= 2 and all(
        1 <= len(label) <= 63
        and label[0].isalnum()
        and label[-1].isalnum()
        and all(
            character.islower() or character.isdigit() or character == "-"
            for character in label
        )
        for label in labels
    )


def _s3_endpoint(value: object) -> str:
    endpoint = _s3_ascii(value, 1, 256)
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError:
        _fail()
    if (
        endpoint != endpoint.lower()
        or parsed.scheme != "https"
        or not parsed.hostname
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.netloc != parsed.hostname
        or not _s3_dns_host(parsed.hostname)
    ):
        _fail()
    return endpoint


def _s3_bucket(value: object) -> str:
    bucket = _s3_ascii(value, 3, 63)
    if (
        S3_BUCKET.fullmatch(bucket) is None
        or ".." in bucket
        or ".-" in bucket
        or "-." in bucket
    ):
        _fail()
    try:
        ipaddress.ip_address(bucket)
    except ValueError:
        return bucket
    _fail()


def _s3_config(config: object) -> tuple[str, bytes]:
    if not isinstance(config, S3AuthorityConfig):
        _fail()
    endpoint = _s3_endpoint(config.endpoint_origin)
    region = _s3_ascii(config.region_pool, 1, 32)
    if S3_REGION_POOL.fullmatch(region) is None:
        _fail()
    bucket = _s3_bucket(config.bucket)
    recipient = _s3_ascii(config.recipient, 62, 62)
    if S3_AGE_RECIPIENT.fullmatch(recipient) is None:
        _fail()
    recipient_sha = hashlib.sha256(recipient.encode("ascii")).hexdigest()
    payload = _s3_canonical_json(
        (
            ("schema", S3_CONFIG_SCHEMA),
            ("version", 1),
            ("provider", S3_PROVIDER),
            ("endpoint_origin", endpoint),
            ("region_pool", region),
            ("bucket", bucket),
            ("bucket_versioning", S3_VERSIONING_ENABLED),
            ("prefix", S3_PREFIX),
            ("encryption_profile", S3_ENCRYPTION_PROFILE),
            ("recipient_sha256", recipient_sha),
        )
    )
    return recipient_sha, payload


def _s3_binding(config: object) -> S3AuthorityBinding:
    if not isinstance(config, S3AuthorityConfig):
        _fail()
    recipient_sha, payload = _s3_config(config)
    return S3AuthorityBinding(
        config=config,
        authority_config_sha256=hashlib.sha256(payload).hexdigest(),
        recipient_sha256=recipient_sha,
    )


def _s3_echo(
    authority_config_sha256: object,
    recipient_sha256: object,
    binding: S3AuthorityBinding,
) -> None:
    if (
        authority_config_sha256 != binding.authority_config_sha256
        or recipient_sha256 != binding.recipient_sha256
    ):
        _fail()


def _s3_versioning(proof: object, binding: S3AuthorityBinding) -> None:
    if not isinstance(proof, S3VersioningProof):
        _fail()
    _s3_echo(proof.authority_config_sha256, proof.recipient_sha256, binding)
    if proof.state != S3_VERSIONING_ENABLED:
        _fail()


def _s3_object_key(identity: uuid.UUID, plaintext_sha256: str) -> str:
    return f"{S3_PREFIX}{identity}/{plaintext_sha256}.age"


def _s3_unknown(object_key: str) -> S3UnknownVersionResult:
    return S3UnknownVersionResult(object_key=object_key, state="UNKNOWN_VERSION")


def _s3_validate_unknown(result: object, expected_key: str) -> S3UnknownVersionResult:
    if (
        not isinstance(result, S3UnknownVersionResult)
        or result.state != "UNKNOWN_VERSION"
        or _s3_ascii(result.object_key, 1, 512) != expected_key
    ):
        _fail()
    return result


def _s3_version_to_b64(value: object) -> tuple[bytes, str]:
    if not isinstance(value, bytes) or not 1 <= len(value) <= 1024 or b"\x00" in value:
        _fail()
    try:
        value.decode("utf-8")
    except UnicodeDecodeError:
        _fail()
    encoded = base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
    if S3_VERSION_B64.fullmatch(encoded) is None:
        _fail()
    return value, encoded


def _s3_version_from_b64(value: object) -> bytes:
    version = _s3_ascii(value, 2, 1366)
    if S3_VERSION_B64.fullmatch(version) is None:
        _fail()
    try:
        raw = base64.b64decode(
            version + ("=" * (-len(version) % 4)),
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, TypeError, ValueError):
        _fail()
    canonical_raw, canonical = _s3_version_to_b64(raw)
    if canonical != version:
        _fail()
    return canonical_raw


def _s3_proof_fields(
    size: object,
    digest: object,
    plaintext: object,
) -> tuple[int, str, bytes]:
    if (
        isinstance(size, bool)
        or not isinstance(size, int)
        or not 1 <= size <= S3_MAX_CIPHERTEXT_BYTES
        or not _s3_valid_sha(digest)
        or not isinstance(plaintext, bytes)
        or len(plaintext) != MAX_BYTES
    ):
        _fail()
    return size, digest, plaintext


def _s3_publish_proof(
    proof: object,
    payload: bytes,
    binding: S3AuthorityBinding,
) -> tuple[bytes, str, int, str]:
    if not isinstance(proof, S3PublishProof):
        _fail()
    _s3_echo(proof.authority_config_sha256, proof.recipient_sha256, binding)
    version_id, version_b64 = _s3_version_to_b64(proof.version_id)
    size, digest, plaintext = _s3_proof_fields(
        proof.ciphertext_size,
        proof.ciphertext_sha256,
        proof.plaintext,
    )
    if plaintext != payload:
        _fail()
    return version_id, version_b64, size, digest


def _s3_validate_receipt(receipt: object) -> S3ZeroLedgerReceipt:
    if not isinstance(receipt, S3ZeroLedgerReceipt):
        _fail()
    expected_key = _s3_object_key(receipt.identity, receipt.plaintext_sha256)
    object_key = _s3_ascii(receipt.object_key, 1, 512)
    if (
        not _valid_uuid4(receipt.identity)
        or isinstance(receipt.generation, bool)
        or receipt.generation != 1
        or isinstance(receipt.row_count, bool)
        or receipt.row_count != 0
        or not _s3_valid_sha(receipt.plaintext_sha256)
        or receipt.encryption_profile != S3_ENCRYPTION_PROFILE
        or not _s3_valid_sha(receipt.recipient_sha256)
        or not _s3_valid_sha(receipt.authority_config_sha256)
        or object_key != expected_key
        or isinstance(receipt.ciphertext_size, bool)
        or not isinstance(receipt.ciphertext_size, int)
        or not 1 <= receipt.ciphertext_size <= S3_MAX_CIPHERTEXT_BYTES
        or not _s3_valid_sha(receipt.ciphertext_sha256)
    ):
        _fail()
    _s3_version_from_b64(receipt.object_version_id_b64)
    return receipt


def encode_s3_receipt(receipt: S3ZeroLedgerReceipt) -> bytes:
    value = _s3_validate_receipt(receipt)
    payload = _s3_canonical_json(
        (
            ("schema", S3_RECEIPT_SCHEMA),
            ("version", 1),
            ("identity", str(value.identity)),
            ("generation", value.generation),
            ("row_count", value.row_count),
            ("plaintext_sha256", value.plaintext_sha256),
            ("encryption_profile", value.encryption_profile),
            ("recipient_sha256", value.recipient_sha256),
            ("authority_config_sha256", value.authority_config_sha256),
            ("object_key", value.object_key),
            ("object_version_id_b64", value.object_version_id_b64),
            ("ciphertext_size", value.ciphertext_size),
            ("ciphertext_sha256", value.ciphertext_sha256),
        )
    )
    if len(payload) > S3_MAX_RECEIPT_BYTES:
        _fail()
    return payload


def decode_s3_receipt(payload: bytes) -> S3ZeroLedgerReceipt:
    if (
        not isinstance(payload, bytes)
        or not 1 <= len(payload) <= S3_MAX_RECEIPT_BYTES
        or not payload.endswith(b"\n")
        or b"\r" in payload
    ):
        _fail()
    try:
        pairs = json.loads(payload.decode("ascii"), object_pairs_hook=lambda value: value)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail()
    expected = (
        "schema",
        "version",
        "identity",
        "generation",
        "row_count",
        "plaintext_sha256",
        "encryption_profile",
        "recipient_sha256",
        "authority_config_sha256",
        "object_key",
        "object_version_id_b64",
        "ciphertext_size",
        "ciphertext_sha256",
    )
    if (
        not isinstance(pairs, list)
        or len(pairs) != len(expected)
        or any(not isinstance(pair, tuple) or len(pair) != 2 for pair in pairs)
        or tuple(pair[0] for pair in pairs) != expected
    ):
        _fail()
    values = {key: value for key, value in pairs}
    if (
        values["schema"] != S3_RECEIPT_SCHEMA
        or isinstance(values["version"], bool)
        or values["version"] != 1
    ):
        _fail()
    try:
        identity = uuid.UUID(values["identity"])
    except (AttributeError, TypeError, ValueError):
        _fail()
    receipt = S3ZeroLedgerReceipt(
        identity=identity,
        generation=values["generation"],
        row_count=values["row_count"],
        plaintext_sha256=values["plaintext_sha256"],
        encryption_profile=values["encryption_profile"],
        recipient_sha256=values["recipient_sha256"],
        authority_config_sha256=values["authority_config_sha256"],
        object_key=values["object_key"],
        object_version_id_b64=values["object_version_id_b64"],
        ciphertext_size=values["ciphertext_size"],
        ciphertext_sha256=values["ciphertext_sha256"],
    )
    if encode_s3_receipt(receipt) != payload:
        _fail()
    return receipt


def _s3_read_primary(root_fd: int, root: _RootIdentity) -> bytes:
    file_fd: int | None = None
    try:
        file_fd, payload, state = _open_copy(root_fd, root)
        final = _held_file(file_fd, root, MAX_BYTES)
        if final != state:
            _fail()
        _assert_named(root_fd, root, final)
        return payload
    finally:
        closing = file_fd
        file_fd = None
        _close_pair(closing, None)


def _s3_validate_read(
    proof: object,
    receipt: S3ZeroLedgerReceipt,
    payload: bytes,
    binding: S3AuthorityBinding,
) -> None:
    if not isinstance(proof, S3ReadProof):
        _fail()
    _s3_echo(proof.authority_config_sha256, proof.recipient_sha256, binding)
    size, digest, plaintext = _s3_proof_fields(
        proof.ciphertext_size,
        proof.ciphertext_sha256,
        proof.plaintext,
    )
    if (
        size != receipt.ciphertext_size
        or digest != receipt.ciphertext_sha256
        or plaintext != payload
    ):
        _fail()


def _s3_read_authority(
    authority: S3AuthorityPort,
    receipt: S3ZeroLedgerReceipt,
    version_id: bytes,
    payload: bytes,
    binding: S3AuthorityBinding,
) -> None:
    proof = authority.read_exact(
        object_key=receipt.object_key,
        version_id=version_id,
        encryption_profile=S3_ENCRYPTION_PROFILE,
        binding=binding,
    )
    _s3_validate_read(proof, receipt, payload, binding)


def create_s3_zero_genesis(
    primary_root_fd: int,
    config: S3AuthorityConfig,
    authority: S3AuthorityPort,
) -> S3ZeroLedgerReceipt:
    root_fd: int | None = None
    ambiguous: S3AmbiguousUpload | None = None
    try:
        root_fd = os.dup(primary_root_fd)
        root = _root_identity(root_fd)
        binding = _s3_binding(config)
        _s3_versioning(
            authority.get_bucket_versioning(binding=binding),
            binding,
        )
        identity = uuid.uuid4()
        if not _valid_uuid4(identity):
            _fail()
        payload = _canonical(identity)
        plaintext_sha = hashlib.sha256(payload).hexdigest()
        object_key = _s3_object_key(identity, plaintext_sha)
        try:
            proof = authority.publish_and_read_back(
                object_key=object_key,
                plaintext=payload,
                encryption_profile=S3_ENCRYPTION_PROFILE,
                if_none_match=S3_IF_NONE_MATCH,
                binding=binding,
            )
        except S3AmbiguousUpload as exc:
            _s3_validate_unknown(exc.result, object_key)
            raise
        except ZeroLedgerError:
            raise
        except Exception:
            raise S3AmbiguousUpload(_s3_unknown(object_key)) from None
        if not isinstance(proof, S3PublishProof):
            raise S3AmbiguousUpload(_s3_unknown(object_key)) from None
        try:
            _s3_version_to_b64(proof.version_id)
        except ZeroLedgerError:
            raise S3AmbiguousUpload(_s3_unknown(object_key)) from None
        version_id, version_b64, ciphertext_size, ciphertext_sha = _s3_publish_proof(
            proof,
            payload,
            binding,
        )
        receipt = S3ZeroLedgerReceipt(
            identity=identity,
            generation=1,
            row_count=0,
            plaintext_sha256=plaintext_sha,
            encryption_profile=S3_ENCRYPTION_PROFILE,
            recipient_sha256=binding.recipient_sha256,
            authority_config_sha256=binding.authority_config_sha256,
            object_key=object_key,
            object_version_id_b64=version_b64,
            ciphertext_size=ciphertext_size,
            ciphertext_sha256=ciphertext_sha,
        )
        encode_s3_receipt(receipt)
        _write_copy(root_fd, root, payload)
        local = _s3_read_primary(root_fd, root)
        if local != payload or _parse(local) != identity:
            _fail()
        _s3_read_authority(authority, receipt, version_id, payload, binding)
        _assert_root(root_fd, root)
        return receipt
    except S3AmbiguousUpload as exc:
        ambiguous = exc
        raise
    except ZeroLedgerError:
        raise
    except Exception:
        raise ZeroLedgerError("zero-ledger") from None
    finally:
        closing = root_fd
        root_fd = None
        try:
            _close_pair(closing, None)
        except ZeroLedgerError:
            if ambiguous is not None:
                raise ambiguous
            raise


def verify_s3_zero_genesis(
    primary_root_fd: int,
    config: S3AuthorityConfig,
    authority: S3AuthorityPort,
    expected_receipt: S3ZeroLedgerReceipt,
    snapshot_id: str,
) -> VerifiedLedgerEvidence:
    root_fd: int | None = None
    try:
        receipt = _s3_validate_receipt(expected_receipt)
        binding = _s3_binding(config)
        if (
            receipt.recipient_sha256 != binding.recipient_sha256
            or receipt.authority_config_sha256
            != binding.authority_config_sha256
            or not isinstance(snapshot_id, str)
            or SNAPSHOT_ID.fullmatch(snapshot_id) is None
        ):
            _fail()
        root_fd = os.dup(primary_root_fd)
        root = _root_identity(root_fd)
        _s3_versioning(
            authority.get_bucket_versioning(binding=binding),
            binding,
        )
        local = _s3_read_primary(root_fd, root)
        identity = _parse(local)
        if (
            identity != receipt.identity
            or hashlib.sha256(local).hexdigest() != receipt.plaintext_sha256
        ):
            _fail()
        version_id = _s3_version_from_b64(receipt.object_version_id_b64)
        _s3_read_authority(authority, receipt, version_id, local, binding)
        final_local = _s3_read_primary(root_fd, root)
        if final_local != local:
            _fail()
        _s3_read_authority(authority, receipt, version_id, final_local, binding)
        _assert_root(root_fd, root)
        return VerifiedLedgerEvidence(
            receipt.identity,
            receipt.generation,
            receipt.plaintext_sha256,
            receipt.row_count,
            snapshot_id,
        )
    except ZeroLedgerError:
        raise
    except Exception:
        raise ZeroLedgerError("zero-ledger") from None
    finally:
        closing = root_fd
        root_fd = None
        _close_pair(closing, None)
