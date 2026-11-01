"""Closed private immutable HTML storage; no public URLs or automatic cleanup."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from uuid import UUID, uuid4

from django.conf import settings
from .faults import SharedFault

MAX_BYTES = 1048576
MAX_ENTRIES = 32768
KEY = re.compile(r'blobs/([0-9a-f]{2})/([0-9a-f]{32})\.html\Z')
JOURNAL = re.compile(r'[0-9a-f]{32}\.json\Z')
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
READ_FLAGS = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC


def checked_key(value):
    match = KEY.fullmatch(value) if type(value) is str else None
    if match is None or match[1] != match[2][:2]:
        raise ValueError('SHARED_BLOB_KEY_INVALID')
    return value


def checked_descriptor(value):
    if (type(value) is not dict or set(value) != {'storage_kind', 'file_key', 'byte_size', 'file_sha256'}
            or value['storage_kind'] != 'file' or type(value['byte_size']) is not int
            or not 0 <= value['byte_size'] <= MAX_BYTES or type(value['file_sha256']) is not str
            or re.fullmatch(r'[0-9a-f]{64}', value['file_sha256']) is None):
        raise ValueError('SHARED_BLOB_DESCRIPTOR_INVALID')
    checked_key(value['file_key'])
    return value


def facts(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
            info.st_size, info.st_blocks, info.st_mtime_ns, info.st_ctime_ns)


class SharedStorage:
    def __init__(self):
        self.media_root = Path(getattr(settings, 'MEDIA_LIBRARY_ROOT', '/var/lib/estakada/media'))
        if not self.media_root.is_absolute() or '..' in self.media_root.parts:
            raise SharedFault('SHARED_CONTENT_UNAVAILABLE', 503)
        self.root = self.media_root / 'private' / 'shared-content'

    @staticmethod
    def _directory(fd):
        info = os.fstat(fd)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError('SHARED_DIRECTORY_INVALID')
        return info

    @staticmethod
    def _regular(fd, limit=MAX_BYTES):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600
                or not 0 <= info.st_size <= limit or info.st_blocks < 0):
            raise ValueError('SHARED_FILE_INVALID')
        return info

    def _directory_at(self, parent, name, create=False):
        try:
            fd = os.open(name, DIR_FLAGS, dir_fd=parent)
        except FileNotFoundError:
            if not create:
                raise
            os.mkdir(name, mode=0o700, dir_fd=parent)
            os.fsync(parent)
            fd = os.open(name, DIR_FLAGS, dir_fd=parent)
        try:
            self._directory(fd)
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _named_directory_identity(self, expected_fd, suffix):
        fd = os.open('/', DIR_FLAGS)
        try:
            for component in self.media_root.parts[1:]:
                nxt = os.open(component, DIR_FLAGS, dir_fd=fd)
                os.close(fd)
                fd = nxt
            for component in suffix:
                nxt = self._directory_at(fd, component)
                os.close(fd)
                fd = nxt
            actual, expected = os.fstat(fd), os.fstat(expected_fd)
            if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                raise ValueError('SHARED_ROOT_NAME_CHANGED')
        finally:
            os.close(fd)

    @staticmethod
    def _assert_absent(parent, name):
        try:
            os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise ValueError('SHARED_ABSENT_ROOT_CHANGED')

    @contextmanager
    def _root(self, *, create=False, absent_ok=False):
        fd = os.open('/', DIR_FLAGS)
        try:
            # Never create anything outside the pre-existing configured media root.
            for component in self.media_root.parts[1:]:
                nxt = os.open(component, DIR_FLAGS, dir_fd=fd)
                os.close(fd)
                fd = nxt
            try:
                nxt = self._directory_at(fd, 'private', create)
            except FileNotFoundError:
                if not absent_ok:
                    raise
                yield None
                self._named_directory_identity(fd, ())
                self._assert_absent(fd, 'private')
                return
            os.close(fd)
            fd = nxt
            try:
                nxt = self._directory_at(fd, 'shared-content', create)
            except FileNotFoundError:
                if not absent_ok:
                    raise
                yield None
                self._named_directory_identity(fd, ('private',))
                self._assert_absent(fd, 'shared-content')
                return
            os.close(fd)
            fd = nxt
            yield fd
            self._named_directory_identity(fd, ('private', 'shared-content'))
        finally:
            os.close(fd)

    def _revalidate_entry(self, root, row):
        """Reopen every component: O_NOFOLLOW on a multi-component path is insufficient."""
        fd = os.dup(root)
        try:
            components = [] if row['key'] == '.' else row['key'].split('/')
            directories = components if row['kind'] == 'directory' else components[:-1]
            for name in directories:
                nxt = self._directory_at(fd, name)
                os.close(fd)
                fd = nxt
            if row['kind'] == 'directory':
                actual = self._directory(fd)
            else:
                leaf = components[-1]
                leaf_fd = os.open(leaf, READ_FLAGS, dir_fd=fd)
                try:
                    actual = self._regular(leaf_fd, 4096 if row['kind'] == 'journal' else MAX_BYTES)
                    named = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
                    if facts(named) != facts(actual):
                        raise ValueError('SHARED_SCAN_NAME_CHANGED')
                finally:
                    os.close(leaf_fd)
            if facts(actual) != row['facts']:
                raise ValueError('SHARED_SCAN_CHANGED')
        finally:
            os.close(fd)

    def _parent_identity(self, root, held_blobs, held_fanout, fanout_name):
        current_blobs = self._directory_at(root, 'blobs')
        try:
            actual, held = self._directory(current_blobs), self._directory(held_blobs)
            if (actual.st_dev, actual.st_ino) != (held.st_dev, held.st_ino):
                raise ValueError('SHARED_BLOBS_PARENT_CHANGED')
            current_fanout = self._directory_at(current_blobs, fanout_name)
            try:
                actual, held = self._directory(current_fanout), self._directory(held_fanout)
                if (actual.st_dev, actual.st_ino) != (held.st_dev, held.st_ino):
                    raise ValueError('SHARED_FANOUT_PARENT_CHANGED')
            finally:
                os.close(current_fanout)
        finally:
            os.close(current_blobs)

    def _journal_identity(self, root, held_journal):
        current = self._directory_at(root, 'journal')
        try:
            actual, held = self._directory(current), self._directory(held_journal)
            if (actual.st_dev, actual.st_ino) != (held.st_dev, held.st_ino):
                raise ValueError('SHARED_JOURNAL_PARENT_CHANGED')
        finally:
            os.close(current)

    @contextmanager
    def _journal_parent(self, operation_id, *, create=False):
        if type(operation_id) is not UUID:
            raise ValueError('SHARED_SERVER_UUID_REQUIRED')
        with self._root(create=create) as root:
            journal = self._directory_at(root, 'journal', create)
            try:
                yield root, journal, operation_id.hex + '.json'
                self._journal_identity(root, journal)
            finally:
                os.close(journal)

    def _sync_journal_chain(self, root, journal):
        """Re-confirm ALL directory entries, including a previous creator's mkdir."""
        media = os.open('/', DIR_FLAGS)
        try:
            for component in self.media_root.parts[1:]:
                nxt = os.open(component, DIR_FLAGS, dir_fd=media)
                os.close(media)
                media = nxt
            private = self._directory_at(media, 'private')
            try:
                current_root = self._directory_at(private, 'shared-content')
                try:
                    actual, expected = self._directory(current_root), self._directory(root)
                    if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                        raise ValueError('SHARED_ROOT_NAME_CHANGED')
                    current_journal = self._directory_at(current_root, 'journal')
                    try:
                        actual, expected = self._directory(current_journal), self._directory(journal)
                        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                            raise ValueError('SHARED_JOURNAL_PARENT_CHANGED')
                        for fd in (current_journal, current_root, private, media):
                            os.fsync(fd)
                        self._named_directory_identity(media, ())
                        self._named_directory_identity(private, ('private',))
                        self._named_directory_identity(root, ('private', 'shared-content'))
                        self._journal_identity(root, journal)
                    finally:
                        os.close(current_journal)
                finally:
                    os.close(current_root)
            finally:
                os.close(private)
        finally:
            os.close(media)

    @contextmanager
    def _parent(self, key, *, create=False):
        checked_key(key)
        with self._root(create=create) as root:
            blobs = self._directory_at(root, 'blobs', create)
            try:
                fanout = self._directory_at(blobs, key.split('/')[1], create)
                try:
                    yield fanout, key.split('/')[2]
                    self._parent_identity(root, blobs, fanout, key.split('/')[1])
                finally:
                    os.close(fanout)
            finally:
                os.close(blobs)

    @staticmethod
    def new_key(blob_id=None):
        identity = uuid4() if blob_id is None else blob_id
        if type(identity) is not UUID:
            raise ValueError('SHARED_SERVER_UUID_REQUIRED')
        return f'blobs/{identity.hex[:2]}/{identity.hex}.html'

    def write_new(self, content, *, blob_id=None):
        try:
            if type(content) is str:
                data = content.encode('utf-8')
            elif type(content) is bytes:
                data = content
            else:
                raise ValueError('SHARED_UTF8_REQUIRED')
            if len(data) > MAX_BYTES:
                raise ValueError('SHARED_BLOB_LIMIT')
            data.decode('utf-8', errors='strict')
            key = self.new_key(blob_id)
            expected_hash = hashlib.sha256(data).hexdigest()
            with self._parent(key, create=True) as (parent, leaf):
                fd = os.open(leaf, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                             0o600, dir_fd=parent)
                try:
                    initial = self._regular(fd)
                    view = memoryview(data)
                    while view:
                        written = os.write(fd, view[:65536])
                        if written <= 0:
                            raise OSError('SHARED_SHORT_WRITE')
                        view = view[written:]
                    os.fsync(fd)
                    os.lseek(fd, 0, os.SEEK_SET)
                    digest, actual_size = hashlib.sha256(), 0
                    while chunk := os.read(fd, 65536):
                        actual_size += len(chunk)
                        if actual_size > MAX_BYTES:
                            raise ValueError('SHARED_BLOB_LIMIT')
                        digest.update(chunk)
                    after = self._regular(fd)
                    named = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                    if (actual_size != len(data) or digest.hexdigest() != expected_hash
                            or after.st_size != actual_size or after.st_ino != initial.st_ino
                            or facts(named) != facts(after)):
                        raise ValueError('SHARED_WRITE_CHANGED')
                    os.fsync(parent)
                finally:
                    # Failed partial files remain accounted orphans; never silently unlink.
                    os.close(fd)
            return {'storage_kind': 'file', 'file_key': key, 'byte_size': len(data), 'file_sha256': expected_hash}
        except (OSError, ValueError, UnicodeError):
            raise SharedFault('SHARED_CONTENT_UNAVAILABLE', 503) from None

    def read(self, descriptor):
        try:
            value = checked_descriptor(descriptor)
            with self._parent(value['file_key']) as (parent, leaf):
                fd = os.open(leaf, READ_FLAGS, dir_fd=parent)
                try:
                    before = self._regular(fd)
                    chunks, size, digest = [], 0, hashlib.sha256()
                    while chunk := os.read(fd, 65536):
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise ValueError('SHARED_BLOB_LIMIT')
                        chunks.append(chunk)
                        digest.update(chunk)
                    after = self._regular(fd)
                    named = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                    if (facts(before) != facts(after) or facts(named) != facts(after)
                            or size != value['byte_size'] or digest.hexdigest() != value['file_sha256']):
                        raise ValueError('SHARED_BLOB_CHANGED')
                finally:
                    os.close(fd)
            return b''.join(chunks).decode('utf-8', errors='strict')
        except (OSError, ValueError, UnicodeError):
            raise SharedFault('SHARED_CONTENT_UNAVAILABLE', 503) from None

    def unlink_verified(self, descriptor, *, allow_missing=False):
        """Caller must hold the shared lease and prove metadata-deleted/no references.

        Missing leaves are accepted only by the explicit durable cleanup phase.
        Parent directories are never removed; the descriptor remains in its job.
        """
        try:
            value = checked_descriptor(descriptor)
            with self._parent(value['file_key']) as (parent, leaf):
                try:
                    fd = os.open(leaf, READ_FLAGS, dir_fd=parent)
                except FileNotFoundError:
                    if not allow_missing:
                        raise
                    os.fsync(parent)
                    return False
                try:
                    before = self._regular(fd)
                    digest, size = hashlib.sha256(), 0
                    while True:
                        part = os.read(fd, 65536)
                        if not part:
                            break
                        size += len(part)
                        if size > MAX_BYTES:
                            raise ValueError('SHARED_BLOB_CHANGED')
                        digest.update(part)
                    after = self._regular(fd)
                    named = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                    if (facts(before) != facts(after) or facts(named) != facts(after)
                            or size != value['byte_size'] or digest.hexdigest() != value['file_sha256']):
                        raise ValueError('SHARED_BLOB_CHANGED')
                    # Re-open the named path before destructive I/O, not merely
                    # on context exit. A renamed held parent is not authority.
                    with self._parent(value['file_key']) as (named_parent, named_leaf):
                        old_parent, current_parent = os.fstat(parent), os.fstat(named_parent)
                        if (old_parent.st_dev, old_parent.st_ino) != (current_parent.st_dev, current_parent.st_ino):
                            raise ValueError('SHARED_BLOB_PARENT_CHANGED')
                        if facts(os.stat(named_leaf, dir_fd=named_parent, follow_symlinks=False)) != facts(after):
                            raise ValueError('SHARED_BLOB_CHANGED')
                        os.unlink(named_leaf, dir_fd=named_parent)
                        os.fsync(named_parent)
                finally:
                    os.close(fd)
            return True
        except (OSError, ValueError, UnicodeError):
            raise SharedFault('SHARED_CLEANUP_FILE_UNAVAILABLE', 503) from None

    def inventory(self, referenced_keys=None):
        try:
            referenced = set() if referenced_keys is None else {checked_key(value) for value in referenced_keys}
            rows, entries = [], 0

            def add(name, info, kind):
                nonlocal entries
                entries += 1
                if entries > MAX_ENTRIES or info.st_blocks < 0:
                    raise ValueError('SHARED_SCAN_BOUND')
                rows.append({'key': name, 'kind': kind, 'facts': facts(info),
                             'allocatedBytes': info.st_blocks * 512, 'logicalBytes': info.st_size})

            def file_at(parent, name, key, journal=False):
                fd = os.open(name, READ_FLAGS, dir_fd=parent)
                try:
                    before = self._regular(fd, 4096 if journal else MAX_BYTES)
                    if journal:
                        data = os.read(fd, 4097)
                        if len(data) != before.st_size:
                            raise ValueError('SHARED_JOURNAL_CHANGED')
                        data.decode('utf-8', errors='strict')
                    after = self._regular(fd, 4096 if journal else MAX_BYTES)
                    named = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    if facts(before) != facts(after) or facts(named) != facts(after):
                        raise ValueError('SHARED_SCAN_CHANGED')
                    add(key, after, 'journal' if journal else 'blob')
                finally:
                    os.close(fd)

            def walk(fd, prefix, level):
                before = self._directory(fd)
                add(prefix or '.', before, 'directory')
                names = sorted(os.listdir(fd))
                if len(names) > MAX_ENTRIES - entries:
                    raise ValueError('SHARED_SCAN_BOUND')
                for name in names:
                    key = prefix + '/' + name if prefix else name
                    if level == 'root':
                        if name not in ('blobs', 'journal'):
                            raise ValueError('SHARED_SCAN_UNKNOWN')
                        child = self._directory_at(fd, name)
                        try: walk(child, key, name)
                        finally: os.close(child)
                    elif level == 'blobs':
                        if re.fullmatch(r'[0-9a-f]{2}', name) is None or len(names) > 256:
                            raise ValueError('SHARED_SCAN_FANOUT')
                        child = self._directory_at(fd, name)
                        try: walk(child, key, 'fanout')
                        finally: os.close(child)
                    elif level == 'fanout':
                        checked_key(key)
                        file_at(fd, name, key)
                    elif level == 'journal':
                        if JOURNAL.fullmatch(name) is None:
                            raise ValueError('SHARED_JOURNAL_NAME')
                        file_at(fd, name, key, journal=True)
                if facts(before) != facts(self._directory(fd)):
                    raise ValueError('SHARED_SCAN_CHANGED')

            with self._root(absent_ok=True) as root:
                if root is not None:
                    walk(root, '', 'root')
                    # A later entry may have been visited after an earlier file grew.
                    # Product writers must cooperate with the content domain; this
                    # detects observed drift, not an adversarial atomic FS snapshot.
                    for row in rows:
                        self._revalidate_entry(root, row)
            rows.sort(key=lambda item: item['key'])
            blobs = [row for row in rows if row['kind'] == 'blob']
            journals = [row for row in rows if row['kind'] == 'journal']
            present = {row['key'] for row in blobs}
            if referenced - present:
                raise ValueError('SHARED_REFERENCED_BLOB_MISSING')
            return {'complete': True, 'actualAllocatedBytes': sum(row['allocatedBytes'] for row in rows),
                'logicalBytes': sum(row['logicalBytes'] for row in rows),
                'blobCount': len(blobs), 'orphanCount': len(present - referenced),
                'journalCount': len(journals), 'journalAllocatedBytes': sum(row['allocatedBytes'] for row in journals),
                'directoryCount': sum(row['kind'] == 'directory' for row in rows), 'files': rows,
                'inventoryStamp': hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
                'fsMetadataReserveAvailable': False, 'reserveBytes': None,
                'reservationReadiness': False, 'profileAvailable': False}
        except (OSError, ValueError, UnicodeError):
            raise SharedFault('SHARED_MEASUREMENT_UNAVAILABLE', 503) from None
