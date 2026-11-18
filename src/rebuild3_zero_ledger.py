from __future__ import annotations

import hashlib
import os
import re
import stat
import uuid
from dataclasses import dataclass

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
