"""Fd-relative immutable delivery storage for the HTML reserve."""
import base64
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from uuid import UUID, uuid4

from .contracts import ContractError, active_pointer, canonical_bytes
from .projection import emit_maps


MAX_MAP_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_FILES = 4096
MAX_RESOURCES = 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_RELEASE_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_JOURNAL_BYTES = 64 * 1024
_ROOT_NAMES = frozenset(
    ('control.lock', 'activation.json', 'activation.tmp', 'releases',
     'staging', 'selectors'))
_SHA = re.compile(r'^[0-9a-f]{64}\Z')
_RESPONSE = re.compile(r'^[0-9a-f]{64}\.html\Z')
_RESOURCE = re.compile(r'^[0-9a-f]{64}\.(?:css|js|webp|jpg|png)\Z')
_SELECTOR = re.compile(
    rb'\A# html-reserve-selector-v1 ([0-9a-f]{64})\n'
    rb'include /delivery/releases/'
    rb'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-'
    rb'[0-9a-f]{12})/maps\.conf;\n\Z')
ABSENT = {'kind': 'ABSENT'}
_SOURCE_ROOT_NAMES = frozenset(
    ('active.json', 'build.lock', 'staging', 'generations'))
_JOURNAL_STAGES = frozenset((
    'PREPARED', 'SELECTOR_CANDIDATE', 'HUP_INTENT',
    'CANDIDATE_CONFIRMED', 'ROLLBACK_REQUIRED', 'ROLLBACK_SELECTOR',
    'ROLLBACK_HUP_INTENT', 'ROLLED_BACK', 'SUCCESS_RECEIPT_WARNING',
    'COMPLETE', 'UNKNOWN'))
_JOURNAL_TRANSITIONS = {
    'PREPARED': frozenset(('SELECTOR_CANDIDATE', 'UNKNOWN')),
    'SELECTOR_CANDIDATE': frozenset((
        'HUP_INTENT', 'ROLLBACK_REQUIRED', 'UNKNOWN')),
    'HUP_INTENT': frozenset((
        'CANDIDATE_CONFIRMED', 'ROLLBACK_REQUIRED', 'UNKNOWN')),
    'CANDIDATE_CONFIRMED': frozenset((
        'COMPLETE', 'SUCCESS_RECEIPT_WARNING', 'UNKNOWN')),
    'ROLLBACK_REQUIRED': frozenset(('ROLLBACK_SELECTOR', 'UNKNOWN')),
    'ROLLBACK_SELECTOR': frozenset(('ROLLBACK_HUP_INTENT', 'UNKNOWN')),
    'ROLLBACK_HUP_INTENT': frozenset(('ROLLED_BACK', 'UNKNOWN')),
    'SUCCESS_RECEIPT_WARNING': frozenset(('COMPLETE', 'UNKNOWN')),
}


def _uuid(value, code='HTML_RESERVE_DELIVERY_UUID_INVALID'):
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ContractError(code) from None
    if str(parsed) != value:
        raise ContractError(code)
    return value


def _sha(value, code='HTML_RESERVE_DELIVERY_SHA_INVALID'):
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise ContractError(code)
    return value


def _write_all(fd, body):
    view = memoryview(body)
    while view:
        written = os.write(fd, view)
        if written < 1:
            raise ContractError('HTML_RESERVE_DELIVERY_SHORT_WRITE')
        view = view[written:]


def _write_file(parent_fd, name, body, mode=0o600):
    if type(body) is not bytes:
        raise ContractError('HTML_RESERVE_DELIVERY_BYTES_REQUIRED')
    fd = os.open(
        name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        mode, dir_fd=parent_fd)
    try:
        _write_all(fd, body)
        os.fsync(fd)
    finally:
        os.close(fd)


def _read_file(parent_fd, name, limit, code):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
    except OSError:
        raise ContractError(code) from None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_size > limit):
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
    finally:
        os.close(fd)


def _open_dir(parent_fd, name, code):
    try:
        return os.open(
            name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd)
    except OSError:
        raise ContractError(code) from None


def _remove_staging_tree(staging_fd, delivery):
    """Remove only a proven protocol-owned, unpublished staging tree."""
    _uuid(delivery)
    generation_fd = _open_dir(
        staging_fd, delivery, 'HTML_RESERVE_DELIVERY_STAGING_INVALID')
    try:
        names = set(os.listdir(generation_fd))
        if not names.issubset(
                {'release.json', 'maps.conf', 'responses', 'resources'}):
            raise ContractError('HTML_RESERVE_DELIVERY_STAGING_INVALID')
        for name in ('release.json', 'maps.conf'):
            if name not in names:
                continue
            info = os.stat(name, dir_fd=generation_fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ContractError('HTML_RESERVE_DELIVERY_STAGING_INVALID')
            os.unlink(name, dir_fd=generation_fd)
        for directory, pattern in (
                ('responses', _RESPONSE), ('resources', _RESOURCE)):
            if directory not in names:
                continue
            directory_fd = _open_dir(
                generation_fd, directory,
                'HTML_RESERVE_DELIVERY_STAGING_INVALID')
            try:
                for leaf in os.listdir(directory_fd):
                    info = os.stat(
                        leaf, dir_fd=directory_fd, follow_symlinks=False)
                    if (pattern.fullmatch(leaf) is None
                            or not stat.S_ISREG(info.st_mode)
                            or info.st_nlink != 1):
                        raise ContractError(
                            'HTML_RESERVE_DELIVERY_STAGING_INVALID')
                    os.unlink(leaf, dir_fd=directory_fd)
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            os.rmdir(directory, dir_fd=generation_fd)
        os.fsync(generation_fd)
    finally:
        os.close(generation_fd)
    os.rmdir(delivery, dir_fd=staging_fd)
    os.fsync(staging_fd)


def _canonical_json(body, *, max_bytes, code):
    if type(body) is not bytes or len(body) > max_bytes:
        raise ContractError(code)
    duplicate = False

    def pairs(values):
        nonlocal duplicate
        result = {}
        for key, value in values:
            if key in result:
                duplicate = True
            result[key] = value
        return result
    try:
        value = json.loads(body.decode('ascii'), object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError):
        raise ContractError(code) from None
    if duplicate or canonical_bytes(value, max_bytes=max_bytes) != body:
        raise ContractError(code)
    return value


def selector_bytes(delivery, release_sha256):
    delivery, release_sha256 = _uuid(delivery), _sha(release_sha256)
    return (
        f'# html-reserve-selector-v1 {release_sha256}\n'
        f'include /delivery/releases/{delivery}/maps.conf;\n'
    ).encode('ascii')


def present_selector(body):
    if type(body) is not bytes or len(body) > 4096:
        raise ContractError('HTML_RESERVE_SELECTOR_BYTES_INVALID')
    match = _SELECTOR.fullmatch(body)
    if match is None:
        raise ContractError('HTML_RESERVE_SELECTOR_BYTES_INVALID')
    digest = hashlib.sha256(body).hexdigest()
    return {
        'kind': 'PRESENT', 'bytes': body, 'sha256': digest,
        'release_sha256': match.group(1).decode('ascii'),
        'delivery': match.group(2).decode('ascii'),
    }


def _selector_state(value):
    if value == ABSENT:
        return ABSENT
    if type(value) is not dict or value.get('kind') != 'PRESENT':
        raise ContractError('HTML_RESERVE_SELECTOR_STATE_INVALID')
    expected = present_selector(value.get('bytes'))
    if value != expected:
        raise ContractError('HTML_RESERVE_SELECTOR_STATE_INVALID')
    return value


def selector_record(value):
    """Return the canonical JSON-safe form of one typed selector state."""
    value = _selector_state(value)
    if value == ABSENT:
        return {'kind': 'ABSENT'}
    return {
        'kind': 'PRESENT',
        'body_base64': base64.b64encode(value['bytes']).decode('ascii'),
        'sha256': value['sha256'],
        'release_sha256': value['release_sha256'],
        'delivery': value['delivery'],
    }


def selector_from_record(value):
    if value == {'kind': 'ABSENT'}:
        return ABSENT
    if type(value) is not dict or set(value) != {
            'kind', 'body_base64', 'sha256', 'release_sha256', 'delivery'}:
        raise ContractError('HTML_RESERVE_SELECTOR_RECORD_INVALID')
    if (value.get('kind') != 'PRESENT'
            or type(value.get('body_base64')) is not str):
        raise ContractError('HTML_RESERVE_SELECTOR_RECORD_INVALID')
    try:
        body = base64.b64decode(
            value['body_base64'].encode('ascii'), validate=True)
        state = present_selector(body)
    except (UnicodeError, ValueError, ContractError):
        raise ContractError('HTML_RESERVE_SELECTOR_RECORD_INVALID') from None
    if selector_record(state) != value:
        raise ContractError('HTML_RESERVE_SELECTOR_RECORD_INVALID')
    return state


def activation_journal(*, operation, sequence, stage, old_selector,
                       new_selector, previous_sha256):
    """Build the closed durable activation state used by the host wrapper."""
    operation = _uuid(operation, 'HTML_RESERVE_JOURNAL_OPERATION_INVALID')
    if type(sequence) is not int or type(sequence) is bool or sequence < 0:
        raise ContractError('HTML_RESERVE_JOURNAL_SEQUENCE_INVALID')
    if stage not in _JOURNAL_STAGES:
        raise ContractError('HTML_RESERVE_JOURNAL_STAGE_INVALID')
    if previous_sha256 is not None:
        previous_sha256 = _sha(
            previous_sha256, 'HTML_RESERVE_JOURNAL_PREVIOUS_INVALID')
    return {
        'schema': 'html-reserve-activation-v1',
        'operation': operation,
        'sequence': sequence,
        'stage': stage,
        'old_selector': selector_record(old_selector),
        'new_selector': selector_record(new_selector),
        'previous_sha256': previous_sha256,
    }


def _validate_journal(value):
    if type(value) is not dict or set(value) != {
            'schema', 'operation', 'sequence', 'stage', 'old_selector',
            'new_selector', 'previous_sha256'}:
        raise ContractError('HTML_RESERVE_JOURNAL_INVALID')
    if value.get('schema') != 'html-reserve-activation-v1':
        raise ContractError('HTML_RESERVE_JOURNAL_INVALID')
    try:
        expected = activation_journal(
            operation=value.get('operation'), sequence=value.get('sequence'),
            stage=value.get('stage'),
            old_selector=selector_from_record(value.get('old_selector')),
            new_selector=selector_from_record(value.get('new_selector')),
            previous_sha256=value.get('previous_sha256'))
    except ContractError:
        raise ContractError('HTML_RESERVE_JOURNAL_INVALID') from None
    if value != expected:
        raise ContractError('HTML_RESERVE_JOURNAL_INVALID')
    return value


class _LockedDelivery:
    def __init__(self, root_fd):
        self.root_fd = root_fd

    def _directory(self, name):
        return _open_dir(
            self.root_fd, name, 'HTML_RESERVE_DELIVERY_DIRECTORY_INVALID')

    def write_release(self, *, delivery, source_generation,
                      source_manifest_sha256, maps, files, _fault=None):
        delivery = _uuid(delivery)
        source_generation = _uuid(source_generation)
        source_manifest_sha256 = _sha(source_manifest_sha256)
        if type(maps) is not bytes or len(maps) > MAX_MAP_BYTES:
            raise ContractError('HTML_RESERVE_DELIVERY_MAP_LIMIT')
        if type(files) is not dict or len(files) > MAX_FILES:
            raise ContractError('HTML_RESERVE_DELIVERY_FILE_LIMIT')
        descriptors, total, resource_count = [], 0, 0
        for path, body in files.items():
            if type(path) is not str or path.count('/') != 1:
                raise ContractError('HTML_RESERVE_DELIVERY_FILE_NAME_INVALID')
            directory, leaf = path.split('/')
            valid = (directory == 'responses' and _RESPONSE.fullmatch(leaf)
                     or directory == 'resources' and _RESOURCE.fullmatch(leaf))
            if not valid or type(body) is not bytes or len(body) > MAX_FILE_BYTES:
                raise ContractError('HTML_RESERVE_DELIVERY_FILE_NAME_INVALID')
            resource_count += directory == 'resources'
            total += len(body)
            descriptors.append({
                'path': path, 'sha256': hashlib.sha256(body).hexdigest(),
                'byte_size': len(body),
            })
        if resource_count > MAX_RESOURCES or total > MAX_TOTAL_BYTES:
            raise ContractError('HTML_RESERVE_DELIVERY_FILE_LIMIT')
        releases_fd, staging_fd = self._directory('releases'), self._directory('staging')
        try:
            if delivery in os.listdir(releases_fd) or delivery in os.listdir(staging_fd):
                raise ContractError('HTML_RESERVE_DELIVERY_EXISTS')
            os.mkdir(delivery, 0o700, dir_fd=staging_fd)
            generation_fd = _open_dir(
                staging_fd, delivery, 'HTML_RESERVE_DELIVERY_DIRECTORY_INVALID')
            try:
                for name in ('responses', 'resources'):
                    os.mkdir(name, 0o700, dir_fd=generation_fd)
                _write_file(generation_fd, 'maps.conf', maps)
                for path, body in sorted(files.items()):
                    directory, leaf = path.split('/')
                    directory_fd = _open_dir(
                        generation_fd, directory,
                        'HTML_RESERVE_DELIVERY_DIRECTORY_INVALID')
                    try:
                        _write_file(directory_fd, leaf, body)
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                manifest = {
                    'schema': 'html-reserve-delivery-v1',
                    'delivery': delivery,
                    'source_generation': source_generation,
                    'source_manifest_sha256': source_manifest_sha256,
                    'maps': {
                        'sha256': hashlib.sha256(maps).hexdigest(),
                        'byte_size': len(maps),
                    },
                    'files': sorted(descriptors, key=lambda row: row['path']),
                    'totals': {'files': len(files), 'bytes': total},
                }
                manifest_body = canonical_bytes(
                    manifest, max_bytes=MAX_RELEASE_MANIFEST_BYTES)
                _write_file(generation_fd, 'release.json', manifest_body)
                os.fsync(generation_fd)
            finally:
                os.close(generation_fd)
            if _fault is not None:
                _fault('staging-fsynced')
            os.rename(
                delivery, delivery, src_dir_fd=staging_fd, dst_dir_fd=releases_fd)
            if _fault is not None:
                _fault('release-renamed')
            os.fsync(staging_fd)
            os.fsync(releases_fd)
            if _fault is not None:
                _fault('release-parent-fsynced')
            digest = hashlib.sha256(manifest_body).hexdigest()
            self.read_release(delivery, digest)
            return digest
        finally:
            os.close(staging_fd)
            os.close(releases_fd)

    def reconcile_staging(self, delivery):
        """Discard one explicitly selected, unpublished protocol staging tree."""
        delivery = _uuid(delivery)
        releases_fd, staging_fd = self._directory('releases'), self._directory('staging')
        try:
            if delivery in os.listdir(releases_fd):
                if delivery in os.listdir(staging_fd):
                    raise ContractError('HTML_RESERVE_DELIVERY_STAGING_INVALID')
                return 'PUBLISHED'
            if delivery not in os.listdir(staging_fd):
                return 'ABSENT'
            _remove_staging_tree(staging_fd, delivery)
            return 'REMOVED'
        finally:
            os.close(staging_fd)
            os.close(releases_fd)

    def read_release(self, delivery, expected_sha256):
        delivery, expected_sha256 = _uuid(delivery), _sha(expected_sha256)
        releases_fd = self._directory('releases')
        try:
            release_fd = _open_dir(
                releases_fd, delivery, 'HTML_RESERVE_DELIVERY_RELEASE_INVALID')
        finally:
            os.close(releases_fd)
        try:
            if set(os.listdir(release_fd)) != {
                    'release.json', 'maps.conf', 'responses', 'resources'}:
                raise ContractError('HTML_RESERVE_DELIVERY_RELEASE_INVALID')
            body = _read_file(
                release_fd, 'release.json', MAX_RELEASE_MANIFEST_BYTES,
                'HTML_RESERVE_DELIVERY_RELEASE_INVALID')
            if hashlib.sha256(body).hexdigest() != expected_sha256:
                raise ContractError('HTML_RESERVE_DELIVERY_RELEASE_INVALID')
            try:
                manifest = json.loads(body.decode('ascii'))
            except (UnicodeError, json.JSONDecodeError):
                raise ContractError('HTML_RESERVE_DELIVERY_RELEASE_INVALID') from None
            if canonical_bytes(
                    manifest, max_bytes=MAX_RELEASE_MANIFEST_BYTES) != body:
                raise ContractError('HTML_RESERVE_DELIVERY_RELEASE_INVALID')
            keys = {
                'schema', 'delivery', 'source_generation',
                'source_manifest_sha256', 'maps', 'files', 'totals'}
            if (type(manifest) is not dict or set(manifest) != keys
                    or manifest['schema'] != 'html-reserve-delivery-v1'
                    or manifest['delivery'] != delivery):
                raise ContractError('HTML_RESERVE_DELIVERY_RELEASE_INVALID')
            _uuid(manifest['source_generation'])
            _sha(manifest['source_manifest_sha256'])
            maps = _read_file(
                release_fd, 'maps.conf', MAX_MAP_BYTES,
                'HTML_RESERVE_DELIVERY_FILE_MISMATCH')
            if manifest['maps'] != {
                    'sha256': hashlib.sha256(maps).hexdigest(),
                    'byte_size': len(maps)}:
                raise ContractError('HTML_RESERVE_DELIVERY_FILE_MISMATCH')
            expected, total = set(), 0
            if type(manifest['files']) is not list:
                raise ContractError('HTML_RESERVE_DELIVERY_RELEASE_INVALID')
            for row in manifest['files']:
                if (type(row) is not dict
                        or set(row) != {'path', 'sha256', 'byte_size'}
                        or type(row['path']) is not str
                        or row['path'].count('/') != 1):
                    raise ContractError('HTML_RESERVE_DELIVERY_RELEASE_INVALID')
                directory, leaf = row['path'].split('/')
                valid = (
                    directory == 'responses' and _RESPONSE.fullmatch(leaf)
                    or directory == 'resources' and _RESOURCE.fullmatch(leaf))
                if (not valid or row['path'] in expected
                        or type(row['byte_size']) is not int
                        or type(row['byte_size']) is bool
                        or row['byte_size'] < 0):
                    raise ContractError('HTML_RESERVE_DELIVERY_RELEASE_INVALID')
                _sha(row['sha256'], 'HTML_RESERVE_DELIVERY_RELEASE_INVALID')
                directory_fd = _open_dir(
                    release_fd, directory,
                    'HTML_RESERVE_DELIVERY_RELEASE_INVALID')
                try:
                    value = _read_file(
                        directory_fd, leaf, MAX_FILE_BYTES,
                        'HTML_RESERVE_DELIVERY_FILE_MISMATCH')
                finally:
                    os.close(directory_fd)
                if (row['sha256'] != hashlib.sha256(value).hexdigest()
                        or row['byte_size'] != len(value)):
                    raise ContractError('HTML_RESERVE_DELIVERY_FILE_MISMATCH')
                expected.add(row['path'])
                total += len(value)
            actual = set()
            for directory in ('responses', 'resources'):
                directory_fd = _open_dir(
                    release_fd, directory,
                    'HTML_RESERVE_DELIVERY_RELEASE_INVALID')
                try:
                    actual.update(directory + '/' + name for name in os.listdir(directory_fd))
                finally:
                    os.close(directory_fd)
            if expected != actual or manifest['totals'] != {
                    'files': len(expected), 'bytes': total}:
                raise ContractError('HTML_RESERVE_DELIVERY_FILE_MISMATCH')
            return manifest
        finally:
            os.close(release_fd)

    def read_journal(self):
        names = set(os.listdir(self.root_fd))
        if 'activation.tmp' in names:
            raise ContractError('HTML_RESERVE_JOURNAL_TEMP_PRESENT')
        if 'activation.json' not in names:
            return None, None
        body = _read_file(
            self.root_fd, 'activation.json', MAX_JOURNAL_BYTES,
            'HTML_RESERVE_JOURNAL_INVALID')
        value = _validate_journal(_canonical_json(
            body, max_bytes=MAX_JOURNAL_BYTES,
            code='HTML_RESERVE_JOURNAL_INVALID'))
        return value, hashlib.sha256(body).hexdigest()

    def transition_journal(self, *, expected_sha256, new, _fault=None):
        """CAS one durable journal transition and return its exact digest."""
        new = _validate_journal(new)
        current, current_sha256 = self.read_journal()
        if expected_sha256 is not None:
            expected_sha256 = _sha(
                expected_sha256, 'HTML_RESERVE_JOURNAL_PREVIOUS_INVALID')
        if current_sha256 != expected_sha256:
            raise ContractError('HTML_RESERVE_JOURNAL_STATE_MISMATCH')
        if current is None:
            if (new['stage'] != 'PREPARED' or new['sequence'] != 0
                    or new['previous_sha256'] is not None):
                raise ContractError('HTML_RESERVE_JOURNAL_TRANSITION_INVALID')
        else:
            if (new['operation'] != current['operation']
                    or new['old_selector'] != current['old_selector']
                    or new['new_selector'] != current['new_selector']
                    or new['sequence'] != current['sequence'] + 1
                    or new['previous_sha256'] != current_sha256
                    or new['stage'] not in _JOURNAL_TRANSITIONS.get(
                        current['stage'], frozenset())):
                raise ContractError('HTML_RESERVE_JOURNAL_TRANSITION_INVALID')
        body = canonical_bytes(new, max_bytes=MAX_JOURNAL_BYTES)
        _write_file(self.root_fd, 'activation.tmp', body)
        if _fault is not None:
            _fault('journal-temp-fsynced')
        os.replace(
            'activation.tmp', 'activation.json', src_dir_fd=self.root_fd,
            dst_dir_fd=self.root_fd)
        if _fault is not None:
            _fault('journal-renamed')
        os.fsync(self.root_fd)
        if _fault is not None:
            _fault('journal-parent-fsynced')
        reread, digest = self.read_journal()
        if reread != new:
            raise ContractError('HTML_RESERVE_JOURNAL_INVALID')
        return digest

    def reconcile_journal_temp(self):
        """Remove only a canonical temp that did not become authoritative."""
        names = set(os.listdir(self.root_fd))
        if 'activation.tmp' not in names:
            return 'ABSENT'
        body = _read_file(
            self.root_fd, 'activation.tmp', MAX_JOURNAL_BYTES,
            'HTML_RESERVE_JOURNAL_INVALID')
        _validate_journal(_canonical_json(
            body, max_bytes=MAX_JOURNAL_BYTES,
            code='HTML_RESERVE_JOURNAL_INVALID'))
        os.unlink('activation.tmp', dir_fd=self.root_fd)
        os.fsync(self.root_fd)
        return 'REMOVED'

    def read_selector(self):
        selectors_fd = self._directory('selectors')
        try:
            names = os.listdir(selectors_fd)
            if not names:
                return ABSENT
            if names != ['active.conf']:
                raise ContractError('HTML_RESERVE_SELECTOR_INVENTORY_INVALID')
            return present_selector(_read_file(
                selectors_fd, 'active.conf', 4096,
                'HTML_RESERVE_SELECTOR_BYTES_INVALID'))
        finally:
            os.close(selectors_fd)

    def replace_selector(self, *, expected, new):
        expected, new = _selector_state(expected), _selector_state(new)
        current = self.read_selector()
        if current != expected:
            raise ContractError('HTML_RESERVE_SELECTOR_STATE_MISMATCH')
        selectors_fd = self._directory('selectors')
        try:
            if new == ABSENT:
                if current != ABSENT:
                    os.unlink('active.conf', dir_fd=selectors_fd)
                    os.fsync(selectors_fd)
                return
            temp = str(uuid4()) + '.tmp'
            _write_file(selectors_fd, temp, new['bytes'])
            os.replace(
                temp, 'active.conf', src_dir_fd=selectors_fd,
                dst_dir_fd=selectors_fd)
            os.fsync(selectors_fd)
        finally:
            os.close(selectors_fd)


class DeliveryStore:
    def __init__(self, root):
        self.root = Path(root)

    @contextmanager
    def locked(self):
        try:
            root_fd = os.open(
                self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError:
            raise ContractError('HTML_RESERVE_DELIVERY_ROOT_INVALID') from None
        lock_fd = None
        try:
            info = os.fstat(root_fd)
            if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
                raise ContractError('HTML_RESERVE_DELIVERY_ROOT_INVALID')
            for name in os.listdir(root_fd):
                item = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
                if stat.S_ISLNK(item.st_mode):
                    raise ContractError('HTML_RESERVE_DELIVERY_ROOT_LINK')
                if name not in _ROOT_NAMES:
                    raise ContractError('HTML_RESERVE_DELIVERY_ROOT_UNKNOWN')
            for name in ('releases', 'staging', 'selectors'):
                try:
                    os.mkdir(name, 0o700, dir_fd=root_fd)
                except FileExistsError:
                    pass
                item = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
                if not stat.S_ISDIR(item.st_mode):
                    raise ContractError('HTML_RESERVE_DELIVERY_DIRECTORY_INVALID')
            lock_fd = os.open(
                'control.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                0o600, dir_fd=root_fd)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ContractError('HTML_RESERVE_DELIVERY_BUSY') from None
            yield _LockedDelivery(root_fd)
        finally:
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                finally:
                    os.close(lock_fd)
            os.close(root_fd)


def verify_active(delivery_root):
    """Verify the exact active release without writing to the delivery root."""
    try:
        root_fd = os.open(
            Path(delivery_root),
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise ContractError('HTML_RESERVE_DELIVERY_ROOT_INVALID') from None
    try:
        info = os.fstat(root_fd)
        if (not stat.S_ISDIR(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise ContractError('HTML_RESERVE_DELIVERY_ROOT_INVALID')
        names = set(os.listdir(root_fd))
        if not names.issubset(_ROOT_NAMES) or 'activation.tmp' in names:
            raise ContractError('HTML_RESERVE_DELIVERY_ROOT_UNKNOWN')
        for name in names:
            item = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            if stat.S_ISLNK(item.st_mode):
                raise ContractError('HTML_RESERVE_DELIVERY_ROOT_LINK')
            if name in {'releases', 'staging', 'selectors'}:
                if not stat.S_ISDIR(item.st_mode):
                    raise ContractError(
                        'HTML_RESERVE_DELIVERY_DIRECTORY_INVALID')
            elif not stat.S_ISREG(item.st_mode) or item.st_nlink != 1:
                raise ContractError('HTML_RESERVE_DELIVERY_ROOT_INVALID')
        view = _LockedDelivery(root_fd)
        journal = None
        if 'activation.json' in names:
            journal, _journal_sha = view.read_journal()
            if journal['stage'] not in {'COMPLETE', 'ROLLED_BACK'}:
                raise ContractError('HTML_RESERVE_JOURNAL_UNFINISHED')
        staging_names = []
        if 'staging' in names:
            staging_fd = _open_dir(
                root_fd, 'staging',
                'HTML_RESERVE_DELIVERY_DIRECTORY_INVALID')
            try:
                staging_names = os.listdir(staging_fd)
            finally:
                os.close(staging_fd)
        if staging_names:
            raise ContractError('HTML_RESERVE_DELIVERY_STAGING_PRESENT')
        release_names = []
        if 'releases' in names:
            releases_fd = _open_dir(
                root_fd, 'releases',
                'HTML_RESERVE_DELIVERY_DIRECTORY_INVALID')
            try:
                release_names = os.listdir(releases_fd)
                for name in release_names:
                    _uuid(name)
                    item = os.stat(
                        name, dir_fd=releases_fd, follow_symlinks=False)
                    if not stat.S_ISDIR(item.st_mode):
                        raise ContractError(
                            'HTML_RESERVE_DELIVERY_RELEASE_INVALID')
            finally:
                os.close(releases_fd)
        selector = ABSENT
        if 'selectors' in names:
            selector = view.read_selector()
        if selector == ABSENT:
            if release_names or journal is not None:
                raise ContractError('HTML_RESERVE_DELIVERY_EMPTY_INVALID')
            return {'state': 'EMPTY'}
        if selector['delivery'] not in release_names:
            raise ContractError('HTML_RESERVE_DELIVERY_RELEASE_INVALID')
        release = view.read_release(
            selector['delivery'], selector['release_sha256'])
        return {
            'state': 'ACTIVE',
            'delivery': selector['delivery'],
            'release_sha256': selector['release_sha256'],
            'source_generation': release['source_generation'],
            'source_manifest_sha256': release['source_manifest_sha256'],
        }
    finally:
        os.close(root_fd)


def project_current(*, source_root, delivery_root, delivery):
    """Copy one coherently locked DEV-25 current into a delivery release."""
    delivery = _uuid(delivery)
    try:
        root_fd = os.open(
            Path(source_root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise ContractError('HTML_RESERVE_SOURCE_ROOT_INVALID') from None
    lock_fd = None
    try:
        root_info = os.fstat(root_fd)
        if (not stat.S_ISDIR(root_info.st_mode)
                or stat.S_IMODE(root_info.st_mode) != 0o700):
            raise ContractError('HTML_RESERVE_SOURCE_ROOT_INVALID')
        names = set(os.listdir(root_fd))
        if names != _SOURCE_ROOT_NAMES:
            raise ContractError('HTML_RESERVE_SOURCE_ROOT_INVALID')
        for name in names:
            info = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                raise ContractError('HTML_RESERVE_SOURCE_ROOT_INVALID')
        try:
            lock_fd = os.open(
                'build.lock', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_fd)
        except OSError:
            raise ContractError('HTML_RESERVE_SOURCE_LOCK_INVALID') from None
        if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
            raise ContractError('HTML_RESERVE_SOURCE_LOCK_INVALID')
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ContractError('HTML_RESERVE_SOURCE_BUSY') from None
        pointer_body = _read_file(
            root_fd, 'active.json', 4096,
            'HTML_RESERVE_SOURCE_POINTER_INVALID')
        pointer = _canonical_json(
            pointer_body, max_bytes=4096,
            code='HTML_RESERVE_SOURCE_POINTER_INVALID')
        if type(pointer) is not dict:
            raise ContractError('HTML_RESERVE_SOURCE_POINTER_INVALID')
        try:
            expected_pointer = active_pointer(
                pointer.get('current'), pointer.get('previous'),
                pointer.get('current_manifest_sha256'),
                pointer.get('previous_manifest_sha256'))
        except ContractError:
            raise ContractError('HTML_RESERVE_SOURCE_POINTER_INVALID') from None
        if pointer != expected_pointer or pointer['current'] is None:
            raise ContractError('HTML_RESERVE_SOURCE_POINTER_INVALID')
        generations_fd = _open_dir(
            root_fd, 'generations', 'HTML_RESERVE_SOURCE_GENERATION_INVALID')
        try:
            generation_fd = _open_dir(
                generations_fd, pointer['current'],
                'HTML_RESERVE_SOURCE_GENERATION_INVALID')
        finally:
            os.close(generations_fd)
        try:
            if set(os.listdir(generation_fd)) != {
                    'manifest.json', 'responses', 'resources'}:
                raise ContractError('HTML_RESERVE_SOURCE_GENERATION_INVALID')
            manifest_body = _read_file(
                generation_fd, 'manifest.json', MAX_RELEASE_MANIFEST_BYTES,
                'HTML_RESERVE_SOURCE_MANIFEST_INVALID')
            if hashlib.sha256(manifest_body).hexdigest() != pointer[
                    'current_manifest_sha256']:
                raise ContractError('HTML_RESERVE_SOURCE_MANIFEST_INVALID')
            manifest = _canonical_json(
                manifest_body, max_bytes=MAX_RELEASE_MANIFEST_BYTES,
                code='HTML_RESERVE_SOURCE_MANIFEST_INVALID')
            maps = emit_maps(manifest, delivery)
            expected = {}
            for directory, rows in (
                    ('responses', manifest['responses']),
                    ('resources', manifest['resources'])):
                for row in rows:
                    path = directory + '/' + row['name']
                    if path in expected:
                        raise ContractError('HTML_RESERVE_SOURCE_MANIFEST_INVALID')
                    expected[path] = row
            if len(expected) > MAX_FILES:
                raise ContractError('HTML_RESERVE_SOURCE_MANIFEST_INVALID')
            files, total = {}, 0
            for directory in ('responses', 'resources'):
                directory_fd = _open_dir(
                    generation_fd, directory,
                    'HTML_RESERVE_SOURCE_GENERATION_INVALID')
                try:
                    actual_names = set(os.listdir(directory_fd))
                    expected_names = {
                        path.split('/', 1)[1] for path in expected
                        if path.startswith(directory + '/')}
                    if actual_names != expected_names:
                        raise ContractError('HTML_RESERVE_SOURCE_FILE_MISMATCH')
                    for leaf in sorted(actual_names):
                        path = directory + '/' + leaf
                        body = _read_file(
                            directory_fd, leaf, MAX_FILE_BYTES,
                            'HTML_RESERVE_SOURCE_FILE_MISMATCH')
                        row = expected[path]
                        if (row['sha256'] != hashlib.sha256(body).hexdigest()
                                or row['byte_size'] != len(body)):
                            raise ContractError('HTML_RESERVE_SOURCE_FILE_MISMATCH')
                        files[path] = body
                        total += len(body)
                finally:
                    os.close(directory_fd)
            if (total > MAX_TOTAL_BYTES or manifest.get('totals') != {
                    'files': len(files), 'bytes': total}):
                raise ContractError('HTML_RESERVE_SOURCE_FILE_MISMATCH')
            with DeliveryStore(delivery_root).locked() as locked:
                release_sha = locked.write_release(
                    delivery=delivery,
                    source_generation=pointer['current'],
                    source_manifest_sha256=pointer[
                        'current_manifest_sha256'],
                    maps=maps, files=files)
            return {
                'delivery': delivery,
                'release_sha256': release_sha,
                'source_generation': pointer['current'],
                'source_manifest_sha256': pointer[
                    'current_manifest_sha256'],
            }
        finally:
            os.close(generation_fd)
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)
        os.close(root_fd)
