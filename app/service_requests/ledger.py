import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from django.conf import settings


SCHEMA = 'service-request-deletion-v1'
ENTRY_MAX_BYTES = 128
ENTRY_MAX_COUNT = 10_000
TOTAL_MAX_BYTES = 1_280_000
BATCH_SIZE = 500
_ENTRY_NAME = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.deleted$')
_LINE = re.compile(
    rb'^service-request-deletion-v1 ([0-9a-f-]{36}) '
    rb'([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z)\n$')


class LedgerError(Exception):
    pass


@dataclass(frozen=True)
class Record:
    request_id: UUID
    deleted_at: datetime


def _flags():
    required = ('O_DIRECTORY', 'O_NOFOLLOW')
    if any(not hasattr(os, name) for name in required):
        raise LedgerError('REQUEST_LEDGER_SAFE_OPEN_UNAVAILABLE')
    return os.O_DIRECTORY | os.O_NOFOLLOW


def _root_fd():
    path = Path(settings.SERVICE_REQUEST_DELETION_LEDGER_ROOT)
    if not path.is_absolute() or path.name in ('', '.', '..'):
        raise LedgerError('REQUEST_LEDGER_ROOT_INVALID')
    parent_fd = None
    try:
        parent_fd = os.open(path.parent, os.O_RDONLY | _flags())
        root_fd = os.open(path.name, os.O_RDONLY | _flags(), dir_fd=parent_fd)
    except OSError:
        raise LedgerError('REQUEST_LEDGER_ROOT_UNAVAILABLE') from None
    finally:
        if parent_fd is not None:
            os.close(parent_fd)
    info = os.fstat(root_fd)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        os.close(root_fd)
        raise LedgerError('REQUEST_LEDGER_ROOT_UNSAFE')
    return root_fd


@contextmanager
def locked():
    """Hold the trusted ledger directory before taking any database row lock."""
    try:
        import fcntl
    except ImportError:
        raise LedgerError('REQUEST_LEDGER_LOCK_UNAVAILABLE') from None
    root_fd = _root_fd()
    try:
        try:
            fcntl.flock(root_fd, fcntl.LOCK_EX)
        except OSError:
            raise LedgerError('REQUEST_LEDGER_LOCK_FAILED') from None
        yield root_fd
    finally:
        try:
            fcntl.flock(root_fd, fcntl.LOCK_UN)
        finally:
            os.close(root_fd)


def _name(request_id):
    value = UUID(str(request_id))
    if str(value) != str(request_id):
        raise LedgerError('REQUEST_LEDGER_ID_INVALID')
    return value, f'{value}.deleted'


def _read(fd, expected_id):
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
            or not 1 <= info.st_size <= ENTRY_MAX_BYTES):
        raise LedgerError('REQUEST_LEDGER_ENTRY_UNSAFE')
    body = os.read(fd, ENTRY_MAX_BYTES + 1)
    match = _LINE.fullmatch(body)
    if match is None:
        raise LedgerError('REQUEST_LEDGER_ENTRY_INVALID')
    try:
        request_id = UUID(match.group(1).decode('ascii'))
        deleted_at = datetime.fromisoformat(
            match.group(2).decode('ascii').removesuffix('Z') + '+00:00')
    except (ValueError, UnicodeError):
        raise LedgerError('REQUEST_LEDGER_ENTRY_INVALID') from None
    if request_id != expected_id or deleted_at.tzinfo is None:
        raise LedgerError('REQUEST_LEDGER_ENTRY_CONFLICT')
    return Record(request_id, deleted_at.astimezone(timezone.utc))


def _existing(root_fd, request_id, name):
    entry_fd = None
    try:
        try:
            entry_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_fd)
        except FileNotFoundError:
            return None
        return _read(entry_fd, request_id)
    except OSError:
        raise LedgerError('REQUEST_LEDGER_READ_FAILED') from None
    finally:
        if entry_fd is not None:
            os.close(entry_fd)


def _scan(root_fd):
    try:
        names = os.listdir(root_fd)
    except OSError:
        raise LedgerError('REQUEST_LEDGER_LIST_FAILED') from None
    if len(names) > ENTRY_MAX_COUNT:
        raise LedgerError('REQUEST_LEDGER_COUNT_LIMIT')
    result, total = [], 0
    for name in sorted(names):
        if _ENTRY_NAME.fullmatch(name) is None:
            raise LedgerError('REQUEST_LEDGER_UNKNOWN_ENTRY')
        request_id = UUID(name[:-len('.deleted')])
        entry_fd = None
        try:
            entry_fd = os.open(
                name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_fd)
            info = os.fstat(entry_fd)
            total += info.st_size
            if total > TOTAL_MAX_BYTES:
                raise LedgerError('REQUEST_LEDGER_TOTAL_LIMIT')
            result.append(_read(entry_fd, request_id))
        except OSError:
            raise LedgerError('REQUEST_LEDGER_ENTRY_READ_FAILED') from None
        finally:
            if entry_fd is not None:
                os.close(entry_fd)
    return tuple(result), total


def record(request_id, deleted_at=None, *, root_fd=None):
    if root_fd is None:
        with locked() as held_fd:
            return record(request_id, deleted_at, root_fd=held_fd)
    request_id, name = _name(request_id)
    deleted_at = (deleted_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    timestamp = deleted_at.isoformat(timespec='microseconds').replace('+00:00', 'Z')
    body = f'{SCHEMA} {request_id} {timestamp}\n'.encode('ascii')
    if len(body) > ENTRY_MAX_BYTES:
        raise LedgerError('REQUEST_LEDGER_ENTRY_LIMIT')
    existing = _existing(root_fd, request_id, name)
    if existing is not None:
        return existing
    records, total = _scan(root_fd)
    if len(records) >= ENTRY_MAX_COUNT:
        raise LedgerError('REQUEST_LEDGER_COUNT_LIMIT')
    if total + len(body) > TOTAL_MAX_BYTES:
        raise LedgerError('REQUEST_LEDGER_TOTAL_LIMIT')
    entry_fd = None
    try:
        try:
            entry_fd = os.open(
                name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600, dir_fd=root_fd)
            written = os.write(entry_fd, body)
            if written != len(body):
                raise LedgerError('REQUEST_LEDGER_WRITE_INCOMPLETE')
            os.fsync(entry_fd)
            os.close(entry_fd)
            entry_fd = None
            os.fsync(root_fd)
        except FileExistsError:
            entry_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_fd)
            return _read(entry_fd, request_id)
        return Record(request_id, deleted_at)
    except OSError:
        raise LedgerError('REQUEST_LEDGER_WRITE_FAILED') from None
    finally:
        if entry_fd is not None:
            os.close(entry_fd)


def get(request_id, *, root_fd=None):
    if root_fd is None:
        with locked() as held_fd:
            return get(request_id, root_fd=held_fd)
    request_id, name = _name(request_id)
    return _existing(root_fd, request_id, name)


def entries(*, root_fd=None):
    if root_fd is None:
        with locked() as held_fd:
            return entries(root_fd=held_fd)
    records, _ = _scan(root_fd)
    return records
