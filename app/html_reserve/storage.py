"""Private, no-follow filesystem primitives for HTML reserve generations."""
from contextlib import contextmanager
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from uuid import UUID, uuid4

from .contracts import (
    ContractError, active_pointer, canonical_bytes, response_name,
)


MAX_ROOT_ENTRIES = 32
MAX_GENERATIONS = 8
MAX_STAGING = 4
MAX_POINTER_TEMPS = 2
MAX_RESOURCES = 1024
MAX_FILES = 4096
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
_UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
_RESPONSE = re.compile(r'^[0-9a-f]{64}\.html$')
_RESOURCE = re.compile(r'^[a-z0-9][a-z0-9._-]{0,127}$')
_TEMP = re.compile(r'^active\.([0-9a-f-]{36})\.tmp$')
_HEX = re.compile(r'^[0-9a-f]{64}$')
_ROOT_NAMES = frozenset(('active.json', 'build.lock', 'staging', 'generations'))
_LOCK_MARKER = b'html-reserve-initialized-v1'


def _uuid(value):
    if type(value) is not str or _UUID.fullmatch(value) is None:
        raise ContractError('HTML_RESERVE_STORAGE_UUID_INVALID')
    try:
        if str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ContractError('HTML_RESERVE_STORAGE_UUID_INVALID') from None
    return value


def _regular(info, mode, code):
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != mode:
        raise ContractError(code)


def _directory(info, mode, code):
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != mode:
        raise ContractError(code)


def _read_fd(fd, limit, code):
    info = os.fstat(fd)
    _regular(info, 0o600, code)
    if info.st_size > limit:
        raise ContractError(code)
    chunks, remaining = [], info.st_size
    while remaining:
        chunk = os.read(fd, min(65536, remaining))
        if not chunk:
            raise ContractError(code)
        chunks.append(chunk)
        remaining -= len(chunk)
    if os.read(fd, 1):
        raise ContractError(code)
    return b''.join(chunks)


def _write_file(parent_fd, name, body):
    if type(body) is not bytes or len(body) > MAX_FILE_BYTES:
        raise ContractError('HTML_RESERVE_FILE_SIZE_INVALID')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = os.open(name, flags, 0o600, dir_fd=parent_fd)
    try:
        view = memoryview(body)
        while view:
            written = os.write(fd, view)
            if written < 1:
                raise OSError('short write')
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _decode_canonical(body, code):
    try:
        value = json.loads(body.decode('ascii'))
    except (UnicodeError, json.JSONDecodeError, TypeError):
        raise ContractError(code) from None
    if canonical_bytes(value) != body:
        raise ContractError(code)
    return value


class ReserveStore:
    def __init__(self, root, *, fault=None):
        self.root = Path(root)
        if not self.root.is_absolute():
            raise ContractError('HTML_RESERVE_ROOT_ABSOLUTE_REQUIRED')
        if fault is not None and not callable(fault):
            raise ContractError('HTML_RESERVE_FAULT_SEAM_INVALID')
        self.fault = fault

    def _prepare(self):
        if not self.root.exists():
            self.root.mkdir(mode=0o700)
        root_info = os.lstat(self.root)
        _directory(root_info, 0o700, 'HTML_RESERVE_ROOT_UNSAFE')
        entries = list(os.scandir(self.root))
        if len(entries) > MAX_ROOT_ENTRIES:
            raise ContractError('HTML_RESERVE_ROOT_ENTRY_LIMIT')
        for entry in entries:
            if entry.name not in _ROOT_NAMES:
                match = _TEMP.fullmatch(entry.name)
                if match is None:
                    raise ContractError('HTML_RESERVE_ROOT_UNKNOWN_ENTRY')
                _uuid(match.group(1))
            if entry.is_symlink():
                raise ContractError('HTML_RESERVE_ROOT_LINK_FORBIDDEN')
        root_fd = os.open(
            self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            for name in ('staging', 'generations'):
                try:
                    os.mkdir(name, 0o700, dir_fd=root_fd)
                except FileExistsError:
                    pass
                info = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
                _directory(info, 0o700, 'HTML_RESERVE_DIRECTORY_UNSAFE')
            return root_fd
        except BaseException:
            os.close(root_fd)
            raise

    @contextmanager
    def locked(self):
        root_fd = self._prepare()
        lock_fd = None
        try:
            lock_fd = os.open(
                'build.lock', os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600, dir_fd=root_fd)
            _regular(os.fstat(lock_fd), 0o600, 'HTML_RESERVE_LOCK_UNSAFE')
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ContractError('HTML_RESERVE_BUILD_BUSY') from None
            locked = _LockedStore(root_fd, lock_fd, self.fault)
            locked.validate_inventory()
            yield locked
        finally:
            if lock_fd is not None:
                os.close(lock_fd)
            os.close(root_fd)


class _LockedStore:
    def __init__(self, root_fd, lock_fd, fault):
        self.root_fd = root_fd
        self.lock_fd = lock_fd
        self.fault = fault

    def _fault(self, event):
        if self.fault is not None:
            self.fault(event)

    def _open_dir(self, name):
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                     dir_fd=self.root_fd)
        _directory(os.fstat(fd), 0o700, 'HTML_RESERVE_DIRECTORY_UNSAFE')
        return fd

    def validate_inventory(self):
        for name in ('staging', 'generations'):
            fd = self._open_dir(name)
            try:
                entries = os.listdir(fd)
                limit = MAX_STAGING if name == 'staging' else MAX_GENERATIONS
                if len(entries) > limit:
                    raise ContractError('HTML_RESERVE_GENERATION_ENTRY_LIMIT')
                for entry in entries:
                    _uuid(entry)
                    info = os.stat(entry, dir_fd=fd, follow_symlinks=False)
                    _directory(info, 0o700, 'HTML_RESERVE_GENERATION_UNSAFE')
            finally:
                os.close(fd)

    def _pointer_contract(self, body):
        value = _decode_canonical(body, 'HTML_RESERVE_POINTER_INVALID')
        if type(value) is not dict or set(value) != {
                'schema', 'current', 'previous', 'current_manifest_sha256',
                'previous_manifest_sha256'}:
            raise ContractError('HTML_RESERVE_POINTER_INVALID')
        expected = active_pointer(
            value['current'], value['previous'], value['current_manifest_sha256'],
            value['previous_manifest_sha256'])
        if value != expected:
            raise ContractError('HTML_RESERVE_POINTER_INVALID')
        return value

    def _reconcile_pointer_temps(self):
        names = []
        for name in os.listdir(self.root_fd):
            match = _TEMP.fullmatch(name)
            if match is not None:
                _uuid(match.group(1))
                names.append(name)
        if len(names) > MAX_POINTER_TEMPS:
            raise ContractError('HTML_RESERVE_POINTER_TEMP_LIMIT')
        for name in sorted(names):
            body = self._read_named(
                self.root_fd, name, 4096, 'HTML_RESERVE_POINTER_TEMP_INVALID')
            try:
                self._pointer_contract(body)
            except ContractError:
                raise ContractError('HTML_RESERVE_POINTER_TEMP_INVALID') from None
        for name in sorted(names):
            os.unlink(name, dir_fd=self.root_fd)
        if names:
            os.fsync(self.root_fd)

    def _read_named(self, parent_fd, name, limit, code):
        try:
            fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                         dir_fd=parent_fd)
        except (FileNotFoundError, OSError):
            raise ContractError(code) from None
        try:
            return _read_fd(fd, limit, code)
        finally:
            os.close(fd)

    def _generation_manifest(self, generation, expected_sha):
        generations_fd = self._open_dir('generations')
        generation_fd = None
        try:
            generation_fd = os.open(
                generation, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=generations_fd)
            _directory(os.fstat(generation_fd), 0o700, 'HTML_RESERVE_GENERATION_UNSAFE')
            body = self._read_named(
                generation_fd, 'manifest.json', 2 * 1024 * 1024,
                'HTML_RESERVE_MANIFEST_UNAVAILABLE')
            if hashlib.sha256(body).hexdigest() != expected_sha:
                raise ContractError('HTML_RESERVE_MANIFEST_DIGEST_MISMATCH')
            manifest = _decode_canonical(body, 'HTML_RESERVE_MANIFEST_INVALID')
            if manifest.get('generation') != generation:
                raise ContractError('HTML_RESERVE_MANIFEST_GENERATION_MISMATCH')
            files = self._read_generation_files(generation_fd)
            self._validate_manifest(generation, manifest, files)
        except (FileNotFoundError, OSError):
            raise ContractError('HTML_RESERVE_GENERATION_UNAVAILABLE') from None
        finally:
            if generation_fd is not None:
                os.close(generation_fd)
            os.close(generations_fd)
        return manifest

    def generation_manifest(self, generation, expected_sha):
        generation = _uuid(generation)
        if type(expected_sha) is not str or _HEX.fullmatch(expected_sha) is None:
            raise ContractError('HTML_RESERVE_MANIFEST_DIGEST_INVALID')
        return self._generation_manifest(generation, expected_sha)

    def _read_generation_files(self, generation_fd):
        if set(os.listdir(generation_fd)) != {'manifest.json', 'responses', 'resources'}:
            raise ContractError('HTML_RESERVE_GENERATION_TREE_INVALID')
        files = {}
        for directory, pattern in (('responses', _RESPONSE), ('resources', _RESOURCE)):
            try:
                directory_fd = os.open(
                    directory,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=generation_fd)
            except OSError:
                raise ContractError('HTML_RESERVE_GENERATION_TREE_INVALID') from None
            try:
                _directory(
                    os.fstat(directory_fd), 0o700,
                    'HTML_RESERVE_GENERATION_TREE_INVALID')
                names = os.listdir(directory_fd)
                limit = MAX_RESOURCES if directory == 'resources' else MAX_FILES
                if len(names) > limit:
                    raise ContractError('HTML_RESERVE_GENERATION_LIMIT')
                for name in names:
                    if pattern.fullmatch(name) is None:
                        raise ContractError('HTML_RESERVE_FILE_NAME_INVALID')
                    files[directory + '/' + name] = self._read_named(
                        directory_fd, name, MAX_FILE_BYTES,
                        'HTML_RESERVE_GENERATION_FILE_INVALID')
            finally:
                os.close(directory_fd)
        return files

    def _delete_uuid_tree(self, parent_fd, generation, *, require_complete,
                          delete=True):
        generation = _uuid(generation)
        try:
            generation_fd = os.open(
                generation,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent_fd)
        except OSError:
            raise ContractError('HTML_RESERVE_ORPHAN_UNSAFE') from None
        opened = {}
        try:
            _directory(os.fstat(generation_fd), 0o700, 'HTML_RESERVE_ORPHAN_UNSAFE')
            top = set(os.listdir(generation_fd))
            allowed = {'manifest.json', 'responses', 'resources'}
            if not top.issubset(allowed):
                raise ContractError('HTML_RESERVE_ORPHAN_UNSAFE')
            if require_complete and top != allowed:
                raise ContractError('HTML_RESERVE_ORPHAN_INCOMPLETE')
            for directory, pattern in (('responses', _RESPONSE), ('resources', _RESOURCE)):
                if directory not in top:
                    continue
                try:
                    fd = os.open(
                        directory,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                        dir_fd=generation_fd)
                except OSError:
                    raise ContractError('HTML_RESERVE_ORPHAN_UNSAFE') from None
                opened[directory] = fd
                _directory(os.fstat(fd), 0o700, 'HTML_RESERVE_ORPHAN_UNSAFE')
                names = os.listdir(fd)
                limit = MAX_RESOURCES if directory == 'resources' else MAX_FILES
                if len(names) > limit:
                    raise ContractError('HTML_RESERVE_GENERATION_LIMIT')
                for name in names:
                    if pattern.fullmatch(name) is None:
                        raise ContractError('HTML_RESERVE_ORPHAN_UNSAFE')
                    _regular(
                        os.stat(name, dir_fd=fd, follow_symlinks=False), 0o600,
                        'HTML_RESERVE_ORPHAN_UNSAFE')
            if 'manifest.json' in top:
                _regular(
                    os.stat('manifest.json', dir_fd=generation_fd, follow_symlinks=False),
                    0o600, 'HTML_RESERVE_ORPHAN_UNSAFE')
                if require_complete:
                    body = self._read_named(
                        generation_fd, 'manifest.json', 2 * 1024 * 1024,
                        'HTML_RESERVE_MANIFEST_UNAVAILABLE')
                    manifest = _decode_canonical(body, 'HTML_RESERVE_MANIFEST_INVALID')
                    files = self._read_generation_files(generation_fd)
                    self._validate_manifest(generation, manifest, files)
            if not delete:
                return
            for directory, fd in opened.items():
                for name in os.listdir(fd):
                    os.unlink(name, dir_fd=fd)
                os.fsync(fd)
            for fd in opened.values():
                os.close(fd)
            opened.clear()
            for directory in ('responses', 'resources'):
                if directory in top:
                    os.rmdir(directory, dir_fd=generation_fd)
            if 'manifest.json' in top:
                os.unlink('manifest.json', dir_fd=generation_fd)
            os.fsync(generation_fd)
        finally:
            for fd in opened.values():
                os.close(fd)
            os.close(generation_fd)
        os.rmdir(generation, dir_fd=parent_fd)
        os.fsync(parent_fd)

    def reconcile_orphans(self):
        pointer = self.read_pointer()
        active = {value for value in (pointer['current'], pointer['previous'])
                  if value is not None}
        removed = set()
        opened = []
        candidates = []
        try:
            for parent_name, require_complete in (('staging', False), ('generations', True)):
                parent_fd = self._open_dir(parent_name)
                opened.append(parent_fd)
                names = os.listdir(parent_fd)
                limit = MAX_STAGING if parent_name == 'staging' else MAX_GENERATIONS
                if len(names) > limit:
                    raise ContractError('HTML_RESERVE_GENERATION_ENTRY_LIMIT')
                for generation in sorted(names):
                    _uuid(generation)
                    if parent_name == 'generations' and generation in active:
                        continue
                    self._delete_uuid_tree(
                        parent_fd, generation, require_complete=require_complete,
                        delete=False)
                    candidates.append((parent_fd, generation, require_complete))
            for parent_fd, generation, require_complete in candidates:
                self._delete_uuid_tree(
                    parent_fd, generation, require_complete=require_complete)
                removed.add(generation)
        finally:
            for parent_fd in opened:
                os.close(parent_fd)
        return tuple(sorted(removed))

    def read_pointer(self):
        body = self._read_named(
            self.root_fd, 'active.json', 4096, 'HTML_RESERVE_POINTER_UNAVAILABLE')
        value = self._pointer_contract(body)
        if value['current'] is not None:
            self._generation_manifest(value['current'], value['current_manifest_sha256'])
        if value['previous'] is not None:
            self._generation_manifest(value['previous'], value['previous_manifest_sha256'])
        return value

    def bootstrap(self):
        self._reconcile_pointer_temps()
        try:
            return self.read_pointer()
        except ContractError as error:
            if str(error) != 'HTML_RESERVE_POINTER_UNAVAILABLE':
                raise
        marker = os.pread(self.lock_fd, len(_LOCK_MARKER) + 1, 0)
        if marker == _LOCK_MARKER:
            raise ContractError('HTML_RESERVE_POINTER_MISSING_AFTER_BOOTSTRAP')
        if marker:
            raise ContractError('HTML_RESERVE_LOCK_MARKER_INVALID')
        for directory in ('staging', 'generations'):
            fd = self._open_dir(directory)
            try:
                if os.listdir(fd):
                    raise ContractError('HTML_RESERVE_BOOTSTRAP_NOT_EMPTY')
            finally:
                os.close(fd)
        pointer = active_pointer(None, None, None, None)
        self._replace_pointer(pointer, str(uuid4()))
        os.pwrite(self.lock_fd, _LOCK_MARKER, 0)
        os.ftruncate(self.lock_fd, len(_LOCK_MARKER))
        os.fsync(self.lock_fd)
        return pointer

    def _replace_pointer(self, pointer, temp_uuid):
        temp_uuid = _uuid(temp_uuid)
        name = 'active.%s.tmp' % temp_uuid
        body = canonical_bytes(pointer, max_bytes=4096)
        _write_file(self.root_fd, name, body)
        os.fsync(self.root_fd)
        self._fault('before_pointer_replace')
        os.replace(name, 'active.json', src_dir_fd=self.root_fd, dst_dir_fd=self.root_fd)
        self._fault('after_pointer_replace')
        os.fsync(self.root_fd)
        self._fault('after_pointer_fsync')

    def write_pointer(self, pointer, temp_uuid):
        expected = active_pointer(
            pointer.get('current'), pointer.get('previous'),
            pointer.get('current_manifest_sha256'),
            pointer.get('previous_manifest_sha256'))
        if pointer != expected:
            raise ContractError('HTML_RESERVE_POINTER_INVALID')
        if pointer['current'] is not None:
            self._generation_manifest(pointer['current'], pointer['current_manifest_sha256'])
        if pointer['previous'] is not None:
            self._generation_manifest(pointer['previous'], pointer['previous_manifest_sha256'])
        self._replace_pointer(pointer, temp_uuid)

    def _validate_manifest(self, generation, manifest, files):
        keys = {'schema', 'generation', 'built_at', 'source_stamp', 'responses',
                'resources', 'retained_asset_ids', 'totals'}
        if type(manifest) is not dict or set(manifest) != keys:
            raise ContractError('HTML_RESERVE_MANIFEST_INVALID')
        if (manifest['schema'] != 'html-reserve-manifest-v1'
                or manifest['generation'] != generation
                or type(manifest['built_at']) is not str
                or _HEX.fullmatch(manifest['source_stamp']) is None
                or type(manifest['responses']) is not list
                or type(manifest['resources']) is not list
                or type(manifest['retained_asset_ids']) is not list):
            raise ContractError('HTML_RESERVE_MANIFEST_INVALID')
        expected = {}
        response_keys = {'name', 'target', 'status', 'location', 'content_type',
                         'x_robots_tag', 'security_policy_id', 'cache_policy_id',
                         'sha256', 'byte_size'}
        resource_keys = {'name', 'url', 'content_type', 'sha256', 'byte_size'}
        for row in manifest['responses']:
            if type(row) is not dict or set(row) != response_keys:
                raise ContractError('HTML_RESERVE_RESPONSE_METADATA_INVALID')
            if (type(row['target']) is not str or response_name(row['target']) != row['name']
                    or row['status'] not in (200, 301, 302, 404)
                    or (row['status'] in (301, 302)) != (type(row['location']) is str)
                    or row['content_type'] != 'text/html; charset=utf-8'
                    or row['x_robots_tag'] not in (None, 'noindex, follow', 'noindex, nofollow')
                    or row['security_policy_id'] != 'public-v1'
                    or row['cache_policy_id'] != 'reserve-v1'):
                raise ContractError('HTML_RESERVE_RESPONSE_METADATA_INVALID')
            expected['responses/' + row['name']] = row
        for row in manifest['resources']:
            if (type(row) is not dict or set(row) != resource_keys
                    or _RESOURCE.fullmatch(row['name']) is None
                    or type(row['url']) is not str or len(row['url']) > 2048
                    or not row['url'].startswith('/') or row['url'].startswith('//')
                    or any(ord(char) < 33 or ord(char) == 127 for char in row['url'])):
                raise ContractError('HTML_RESERVE_RESOURCE_METADATA_INVALID')
            expected['resources/' + row['name']] = row
        if len(manifest['resources']) > MAX_RESOURCES:
            raise ContractError('HTML_RESERVE_RESOURCE_LIMIT')
        if set(expected) != set(files) or len(expected) != len(manifest['responses']) + len(manifest['resources']):
            raise ContractError('HTML_RESERVE_MANIFEST_FILE_SET_MISMATCH')
        total = 0
        for name, body in files.items():
            row = expected[name]
            if (type(body) is not bytes or _HEX.fullmatch(row['sha256']) is None
                    or row['sha256'] != hashlib.sha256(body).hexdigest()
                    or row['byte_size'] != len(body)):
                raise ContractError('HTML_RESERVE_MANIFEST_FILE_MISMATCH')
            total += len(body)
        if len(files) > MAX_FILES or total > MAX_TOTAL_BYTES:
            raise ContractError('HTML_RESERVE_GENERATION_LIMIT')
        if manifest['totals'] != {'files': len(files), 'bytes': total}:
            raise ContractError('HTML_RESERVE_TOTALS_MISMATCH')
        retained = manifest['retained_asset_ids']
        if len(retained) != len(set(retained)):
            raise ContractError('HTML_RESERVE_RETAINED_INVALID')
        for value in retained:
            _uuid(value)
        canonical_bytes(manifest)

    def write_generation(self, generation, manifest, files):
        generation = _uuid(generation)
        if type(files) is not dict:
            raise ContractError('HTML_RESERVE_FILES_INVALID')
        for name in files:
            if type(name) is not str or '/' not in name:
                raise ContractError('HTML_RESERVE_FILE_NAME_INVALID')
            directory, leaf = name.split('/', 1)
            if (directory == 'responses' and _RESPONSE.fullmatch(leaf) is not None):
                continue
            if directory == 'resources' and _RESOURCE.fullmatch(leaf) is not None:
                continue
            raise ContractError('HTML_RESERVE_FILE_NAME_INVALID')
        self._validate_manifest(generation, manifest, files)
        manifest_body = canonical_bytes(manifest)
        staging_fd, generations_fd = self._open_dir('staging'), self._open_dir('generations')
        generation_fd = None
        try:
            if len(os.listdir(staging_fd)) >= MAX_STAGING:
                raise ContractError('HTML_RESERVE_STAGING_LIMIT')
            if len(os.listdir(generations_fd)) >= MAX_GENERATIONS:
                raise ContractError('HTML_RESERVE_GENERATION_ENTRY_LIMIT')
            try:
                os.stat(generation, dir_fd=generations_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ContractError('HTML_RESERVE_GENERATION_EXISTS')
            try:
                os.mkdir(generation, 0o700, dir_fd=staging_fd)
            except FileExistsError:
                raise ContractError('HTML_RESERVE_GENERATION_EXISTS') from None
            generation_fd = os.open(
                generation, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=staging_fd)
            for directory in ('responses', 'resources'):
                os.mkdir(directory, 0o700, dir_fd=generation_fd)
            opened = {}
            try:
                for directory in ('responses', 'resources'):
                    opened[directory] = os.open(
                        directory, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                        dir_fd=generation_fd)
                for name in sorted(files):
                    directory, leaf = name.split('/', 1)
                    _write_file(opened[directory], leaf, files[name])
                for fd in opened.values():
                    os.fsync(fd)
                _write_file(generation_fd, 'manifest.json', manifest_body)
                os.fsync(generation_fd)
            finally:
                for fd in opened.values():
                    os.close(fd)
            self._fault('before_generation_rename')
            os.rename(generation, generation, src_dir_fd=staging_fd, dst_dir_fd=generations_fd)
            self._fault('after_generation_rename')
            os.fsync(staging_fd)
            os.fsync(generations_fd)
        except OSError as error:
            if error.errno in (errno.EEXIST, errno.ENOTEMPTY):
                raise ContractError('HTML_RESERVE_GENERATION_EXISTS') from None
            raise
        finally:
            if generation_fd is not None:
                os.close(generation_fd)
            os.close(staging_fd)
            os.close(generations_fd)
        return hashlib.sha256(manifest_body).hexdigest()
