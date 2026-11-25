from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Collection, Iterator, Protocol, Sequence


_ZERO_HASH = "0" * 64
_HASH = re.compile(r"\A[0-9a-f]{64}\Z")
_STAMP = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z\Z")
_LEDGER_NAME = "service-request-deletions.jsonl"
_LOCK_NAME = ".service-request-deletions.lock"
_ROW_KEYS = frozenset(
    {"sequence", "request_id", "deleted_at", "reason", "previous_hash", "row_hash"}
)


class LedgerError(RuntimeError):
    pass


class LedgerReason(StrEnum):
    OWNER = "OWNER"
    RETENTION = "RETENTION"


class LedgerState(StrEnum):
    PRIMARY_PENDING = "PRIMARY_PENDING"
    INDEPENDENT_VERIFIED = "INDEPENDENT_VERIFIED"
    PROJECTED = "PROJECTED"


@dataclass(frozen=True, slots=True)
class Tombstone:
    sequence: int
    request_id: uuid.UUID
    deleted_at: datetime
    reason: LedgerReason
    previous_hash: str
    row_hash: str


@dataclass(frozen=True, slots=True)
class LedgerSnapshot:
    generation: int
    digest: str
    records: tuple[Tombstone, ...]
    payload: bytes


@dataclass(frozen=True, slots=True)
class IndependentReceipt:
    generation: int
    digest: str


class IndependentLedger(Protocol):
    def current_receipt(self) -> IndependentReceipt | None: ...

    def publish_and_verify(self, snapshot: LedgerSnapshot) -> IndependentReceipt | None: ...


class SyntheticIndependentLedger:
    def __init__(self) -> None:
        self._payload: bytes | None = None
        self._receipt: IndependentReceipt | None = None

    def current_receipt(self) -> IndependentReceipt | None:
        return self._receipt

    def publish_and_verify(self, snapshot: LedgerSnapshot) -> IndependentReceipt:
        validated = _parse(snapshot.payload)
        if validated != snapshot:
            raise LedgerError("INVALID_PRIMARY_SNAPSHOT")
        candidate = IndependentReceipt(snapshot.generation, snapshot.digest)
        if self._receipt is not None:
            if candidate.generation < self._receipt.generation:
                raise LedgerError("INDEPENDENT_ROLLBACK")
            if candidate.generation == self._receipt.generation:
                if candidate != self._receipt or snapshot.payload != self._payload:
                    raise LedgerError("INDEPENDENT_EQUIVOCATION")
                return self._receipt
            assert self._payload is not None
            if not snapshot.payload.startswith(self._payload):
                raise LedgerError("INDEPENDENT_FORK")
            if _prefix_digest(snapshot, self._receipt.generation) != self._receipt.digest:
                raise LedgerError("INDEPENDENT_FORK")
        self._payload = bytes(snapshot.payload)
        self._receipt = candidate
        if hashlib.sha256(self._payload).hexdigest() != self._receipt.digest:
            raise LedgerError("INDEPENDENT_VERIFY_FAILED")
        return self._receipt


class DisabledIndependentLedger:
    def current_receipt(self) -> None:
        return None

    def publish_and_verify(self, snapshot: LedgerSnapshot) -> None:
        del snapshot
        return None


def _canonical(value: dict[str, object]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _timestamp(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise LedgerError("INVALID_DELETED_AT")
    result = value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if _STAMP.fullmatch(result) is None:
        raise LedgerError("INVALID_DELETED_AT")
    return result


def _record_bytes(
    sequence: int,
    request_id: uuid.UUID,
    deleted_at: datetime,
    reason: LedgerReason,
    previous_hash: str,
) -> tuple[bytes, Tombstone]:
    base: dict[str, object] = {
        "deleted_at": _timestamp(deleted_at),
        "previous_hash": previous_hash,
        "reason": reason.value,
        "request_id": str(request_id),
        "sequence": sequence,
    }
    row_hash = hashlib.sha256(_canonical(base)).hexdigest()
    stored = dict(base)
    stored["row_hash"] = row_hash
    return _canonical(stored) + b"\n", Tombstone(
        sequence=sequence,
        request_id=request_id,
        deleted_at=deleted_at.astimezone(UTC),
        reason=reason,
        previous_hash=previous_hash,
        row_hash=row_hash,
    )


def _load_object(line: bytes) -> dict[str, object]:
    def closed(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise LedgerError("INVALID_LEDGER_ROW")
            result[key] = value
        return result

    try:
        value = json.loads(line.decode("utf-8"), object_pairs_hook=closed)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise LedgerError("INVALID_LEDGER_ROW") from exc
    if type(value) is not dict or frozenset(value) != _ROW_KEYS:
        raise LedgerError("INVALID_LEDGER_ROW")
    return value


def _parse(payload: bytes) -> LedgerSnapshot:
    if payload and not payload.endswith(b"\n"):
        raise LedgerError("TRUNCATED_LEDGER")
    records: list[Tombstone] = []
    seen: set[uuid.UUID] = set()
    previous_hash = _ZERO_HASH
    for expected_sequence, line in enumerate(payload.splitlines(), 1):
        if not line or len(line) > 1024:
            raise LedgerError("INVALID_LEDGER_ROW")
        value = _load_object(line)
        if _canonical(value) != line:
            raise LedgerError("NONCANONICAL_LEDGER_ROW")
        sequence = value["sequence"]
        request_text = value["request_id"]
        deleted_text = value["deleted_at"]
        reason_text = value["reason"]
        stored_previous = value["previous_hash"]
        stored_hash = value["row_hash"]
        if (
            type(sequence) is not int
            or sequence != expected_sequence
            or type(request_text) is not str
            or type(deleted_text) is not str
            or type(reason_text) is not str
            or type(stored_previous) is not str
            or type(stored_hash) is not str
            or stored_previous != previous_hash
            or _HASH.fullmatch(stored_hash) is None
            or _STAMP.fullmatch(deleted_text) is None
        ):
            raise LedgerError("INVALID_LEDGER_ROW")
        try:
            request_id = uuid.UUID(request_text)
            deleted_at = datetime.strptime(deleted_text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
            reason = LedgerReason(reason_text)
        except (ValueError, TypeError) as exc:
            raise LedgerError("INVALID_LEDGER_ROW") from exc
        if str(request_id) != request_text:
            raise LedgerError("INVALID_LEDGER_ROW")
        if request_id in seen:
            raise LedgerError("DUPLICATE_TOMBSTONE")
        seen.add(request_id)
        expected_line, record = _record_bytes(
            sequence,
            request_id,
            deleted_at,
            reason,
            previous_hash,
        )
        if expected_line[:-1] != line or record.row_hash != stored_hash:
            raise LedgerError("INVALID_LEDGER_HASH")
        records.append(record)
        previous_hash = record.row_hash
    return LedgerSnapshot(
        generation=len(records),
        digest=hashlib.sha256(payload).hexdigest(),
        records=tuple(records),
        payload=payload,
    )


def _prefix_digest(snapshot: LedgerSnapshot, generation: int) -> str:
    if not 0 <= generation <= snapshot.generation:
        raise LedgerError("AMBIGUOUS_GENERATION")
    if generation == snapshot.generation:
        return snapshot.digest
    lines = snapshot.payload.splitlines(keepends=True)
    return hashlib.sha256(b"".join(lines[:generation])).hexdigest()


def assess_ledger_state(
    snapshot: LedgerSnapshot,
    receipt: IndependentReceipt | None,
    projection: Sequence[tuple[int, uuid.UUID]],
    live_tombstoned_ids: Collection[uuid.UUID],
) -> LedgerState:
    expected = tuple((record.sequence, record.request_id) for record in snapshot.records)
    actual = tuple(projection)
    try:
        live_ids = frozenset(live_tombstoned_ids)
    except TypeError:
        raise LedgerError("AMBIGUOUS_PROJECTION") from None
    expected_ids = frozenset(record.request_id for record in snapshot.records)
    if (
        any(type(request_id) is not uuid.UUID for request_id in live_ids)
        or not live_ids.issubset(expected_ids)
        or len(actual) > len(expected)
        or actual != expected[: len(actual)]
    ):
        raise LedgerError("AMBIGUOUS_PROJECTION")
    if receipt is None:
        if actual:
            raise LedgerError("PROJECTION_WITHOUT_RECEIPT")
        return LedgerState.PRIMARY_PENDING
    if type(receipt) is not IndependentReceipt:
        raise LedgerError("AMBIGUOUS_RECEIPT")
    if (
        type(receipt.generation) is not int
        or not 0 <= receipt.generation <= snapshot.generation
        or type(receipt.digest) is not str
        or _HASH.fullmatch(receipt.digest) is None
    ):
        raise LedgerError("AMBIGUOUS_RECEIPT")
    if receipt.digest != _prefix_digest(snapshot, receipt.generation):
        raise LedgerError("AMBIGUOUS_RECEIPT")
    if len(actual) > receipt.generation:
        raise LedgerError("PROJECTION_AHEAD_OF_RECEIPT")
    if receipt.generation != snapshot.generation:
        verified_projection = expected[: receipt.generation]
        verified_ids = frozenset(request_id for _sequence, request_id in verified_projection)
        if actual != verified_projection or live_ids.intersection(verified_ids):
            raise LedgerError("AMBIGUOUS_VERIFIED_PREFIX")
        return LedgerState.PRIMARY_PENDING
    return (
        LedgerState.PROJECTED
        if actual == expected and not live_ids
        else LedgerState.INDEPENDENT_VERIFIED
    )


class LedgerSession:
    def __init__(self, directory_fd: int, ledger_fd: int):
        self._directory_fd = directory_fd
        self._ledger_fd = ledger_fd

    def _read_snapshot(self) -> LedgerSnapshot:
        os.lseek(self._ledger_fd, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(self._ledger_fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        return _parse(b"".join(chunks))

    def snapshot(self) -> LedgerSnapshot:
        snapshot = self._read_snapshot()
        os.fsync(self._ledger_fd)
        os.fsync(self._directory_fd)
        return snapshot

    def append(
        self,
        values: Sequence[tuple[uuid.UUID, datetime, LedgerReason]],
    ) -> LedgerSnapshot:
        if not values:
            raise LedgerError("EMPTY_APPEND")
        current = self._read_snapshot()
        seen = {record.request_id for record in current.records}
        if any(request_id in seen for request_id, _deleted_at, _reason in values):
            raise LedgerError("DUPLICATE_TOMBSTONE")
        incoming = [request_id for request_id, _deleted_at, _reason in values]
        if len(set(incoming)) != len(incoming):
            raise LedgerError("DUPLICATE_TOMBSTONE")
        previous_hash = current.records[-1].row_hash if current.records else _ZERO_HASH
        output = bytearray()
        for offset, (request_id, deleted_at, reason) in enumerate(values, 1):
            if type(request_id) is not uuid.UUID or type(reason) is not LedgerReason:
                raise LedgerError("INVALID_TOMBSTONE")
            encoded, record = _record_bytes(
                current.generation + offset,
                request_id,
                deleted_at,
                reason,
                previous_hash,
            )
            output.extend(encoded)
            previous_hash = record.row_hash
        view = memoryview(output)
        while view:
            written = os.write(self._ledger_fd, view)
            if written <= 0:
                raise LedgerError("LEDGER_WRITE_FAILED")
            view = view[written:]
        os.fsync(self._ledger_fd)
        os.fsync(self._directory_fd)
        return self._read_snapshot()


class PrimaryLedger:
    def __init__(self, root: Path):
        self.root = root

    @contextlib.contextmanager
    def locked(self) -> Iterator[LedgerSession]:
        required = ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
        if any(not hasattr(os, name) for name in required):
            raise LedgerError("UNSUPPORTED_LEDGER_FILESYSTEM")
        directory_fd = lock_fd = ledger_fd = None
        try:
            directory_fd = os.open(
                self.root,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            )
            directory_stat = os.fstat(directory_fd)
            if (
                directory_stat.st_uid != os.geteuid()
                or stat.S_IMODE(directory_stat.st_mode) & 0o077
            ):
                raise LedgerError("INSECURE_LEDGER_ROOT")
            lock_fd = os.open(
                _LOCK_NAME,
                os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                0o600,
                dir_fd=directory_fd,
            )
            lock_stat = os.fstat(lock_fd)
            if (
                not stat.S_ISREG(lock_stat.st_mode)
                or lock_stat.st_uid != os.geteuid()
                or stat.S_IMODE(lock_stat.st_mode) != 0o600
                or lock_stat.st_nlink != 1
            ):
                raise LedgerError("INVALID_LEDGER_LOCK")
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise LedgerError("LEDGER_LOCKED") from exc
            ledger_fd = os.open(
                _LEDGER_NAME,
                os.O_RDWR
                | os.O_CREAT
                | os.O_APPEND
                | os.O_NOFOLLOW
                | os.O_CLOEXEC
                | os.O_NONBLOCK,
                0o600,
                dir_fd=directory_fd,
            )
            ledger_stat = os.fstat(ledger_fd)
            if (
                not stat.S_ISREG(ledger_stat.st_mode)
                or ledger_stat.st_uid != os.geteuid()
                or stat.S_IMODE(ledger_stat.st_mode) != 0o600
                or ledger_stat.st_nlink != 1
            ):
                raise LedgerError("INVALID_LEDGER_FILE")
            yield LedgerSession(directory_fd, ledger_fd)
        except LedgerError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise LedgerError("LEDGER_UNAVAILABLE") from exc
        finally:
            if ledger_fd is not None:
                os.close(ledger_fd)
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                finally:
                    os.close(lock_fd)
            if directory_fd is not None:
                os.close(directory_fd)
