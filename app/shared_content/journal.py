"""Immutable unvetted book primitive; no quota admission or DB authority."""
import errno
import fcntl
import hashlib
import json
import os
import re
import stat
from uuid import UUID

from .faults import SharedFault
from .storage import SharedStorage, facts

MAX_BOOK_BYTES = 4096
FIELDS = frozenset(('bookSchema', 'profileId', 'operationId', 'blockId', 'action', 'actorId',
                   'generation', 'inputFingerprint', 'sourceStamp', 'reservedBytes', 'snapshotIncrement'))
ACTIONS = {'draft': 0, 'apply': 1, 'restore_prepare': 0, 'restore_cancel': 0}


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError('JOURNAL_UUID_INVALID')
    return UUID(value)


def _validate(book):
    if type(book) is not dict or set(book) != FIELDS:
        raise ValueError('JOURNAL_FIELDS_INVALID')
    if (book['bookSchema'] != 'shared-held-book-v1'
            or book['profileId'] not in ('shared-unvetted-v1', 'shared-local-v1', 'shared-local-lc-v1')):
        raise ValueError('JOURNAL_PROFILE_INVALID')
    _uuid(book['operationId']); _uuid(book['blockId'])
    if type(book['action']) is not str or book['action'] not in ACTIONS:
        raise ValueError('JOURNAL_ACTION_INVALID')
    for field in ('actorId', 'generation'):
        if type(book[field]) is not int or not 1 <= book[field] <= 9223372036854775807:
            raise ValueError('JOURNAL_INTEGER_INVALID')
    for field in ('inputFingerprint', 'sourceStamp'):
        if type(book[field]) is not str or re.fullmatch(r'[0-9a-f]{64}', book[field]) is None:
            raise ValueError('JOURNAL_DIGEST_INVALID')
    if type(book['reservedBytes']) is not int or not 0 <= book['reservedBytes'] <= 268435456:
        raise ValueError('JOURNAL_RESERVE_INVALID')
    if (type(book['snapshotIncrement']) is not int
            or book['snapshotIncrement'] != ACTIONS[book['action']]):
        raise ValueError('JOURNAL_INCREMENT_INVALID')
    return dict(book)


def _encode(book):
    value = _validate(book)
    wire = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')
    if len(wire) > MAX_BOOK_BYTES:
        raise ValueError('JOURNAL_BYTES_LIMIT')
    return value, wire


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('JOURNAL_DUPLICATE_FIELD')
        value[key] = item
    return value


def _bad_number(value):
    raise ValueError('JOURNAL_NUMBER_INVALID')


class SharedJournal:
    def __init__(self, storage=None):
        self.storage = SharedStorage() if storage is None else storage

    @staticmethod
    def _regular(fd):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600 or info.st_blocks < 0):
            raise SharedFault('SHARED_JOURNAL_UNAVAILABLE', 503)
        if not 0 <= info.st_size <= MAX_BOOK_BYTES:
            raise SharedFault('SHARED_JOURNAL_INVALID', 503)
        return info

    def _read(self, fd, parent, leaf, operation_id):
        before = self._regular(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        chunks, size = [], 0
        while chunk := os.read(fd, MAX_BOOK_BYTES + 1 - size):
            size += len(chunk)
            if size > MAX_BOOK_BYTES:
                raise SharedFault('SHARED_JOURNAL_INVALID', 503)
            chunks.append(chunk)
        after = self._regular(fd)
        named = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
        if facts(before) != facts(after) or facts(named) != facts(after):
            raise SharedFault('SHARED_JOURNAL_UNAVAILABLE', 503)
        wire = b''.join(chunks)
        try:
            value = json.loads(wire.decode('utf-8'), object_pairs_hook=_pairs,
                               parse_float=_bad_number, parse_constant=_bad_number)
            book, canonical = _encode(value)
            if canonical != wire or _uuid(book['operationId']) != operation_id:
                raise ValueError('JOURNAL_CANONICAL_BINDING_INVALID')
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise SharedFault('SHARED_JOURNAL_INVALID', 503) from None
        return book, wire

    def _access(self, operation_id, expected=None):
        fd, locked = None, False
        try:
            # The outer finally is deliberate: the file lock survives BOTH
            # parent/root context exits and their named-anchor validation.
            with self.storage._journal_parent(operation_id, create=expected is not None) as (root, parent, leaf):
                flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
                created = False
                if expected is not None:
                    try:
                        fd = os.open(leaf, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent)
                        created = True
                    except FileExistsError:
                        fd = os.open(leaf, flags, dir_fd=parent)
                else:
                    fd = os.open(leaf, flags, dir_fd=parent)
                self._regular(fd)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                except OSError as exc:
                    if exc.errno in (errno.EACCES, errno.EAGAIN):
                        raise SharedFault('SHARED_JOURNAL_BUSY', 503) from None
                    raise
                if created:
                    view = memoryview(expected)
                    while view:
                        written = os.write(fd, view)
                        if written <= 0:
                            raise OSError('JOURNAL_SHORT_WRITE')
                        view = view[written:]
                    os.fsync(fd)
                book, wire = self._read(fd, parent, leaf, operation_id)
                if expected is not None and wire != expected:
                    raise SharedFault('SHARED_JOURNAL_CONFLICT', 409)
                if not created:
                    # EEXIST proves a name, not the previous creator's fsync.
                    os.fsync(fd)
                self.storage._sync_journal_chain(root, parent)
                final_book, final_wire = self._read(fd, parent, leaf, operation_id)
                if final_wire != wire:
                    raise SharedFault('SHARED_JOURNAL_UNAVAILABLE', 503)
                result = {'book': final_book, 'sha256': hashlib.sha256(final_wire).hexdigest(),
                    'replay': not created, 'durable': True, 'profileAvailable': False, 'heldAuthority': False}
            return result
        except SharedFault:
            raise
        except (OSError, ValueError, UnicodeError):
            raise SharedFault('SHARED_JOURNAL_UNAVAILABLE', 503) from None
        finally:
            if fd is not None:
                cleanup_failed = False
                try:
                    if locked:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    cleanup_failed = True
                finally:
                    try:
                        os.close(fd)
                    except OSError:
                        cleanup_failed = True
                if cleanup_failed:
                    raise SharedFault('SHARED_JOURNAL_UNAVAILABLE', 503) from None

    def create_or_replay(self, book):
        try:
            detached, wire = _encode(book)
            operation_id = _uuid(detached['operationId'])
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise SharedFault('SHARED_JOURNAL_INVALID', 503) from None
        return self._access(operation_id, expected=wire)

    def read(self, operation_id):
        try:
            identity = operation_id if type(operation_id) is UUID else _uuid(operation_id)
        except (ValueError, TypeError, AttributeError):
            raise SharedFault('SHARED_JOURNAL_INVALID', 503) from None
        return self._access(identity)
