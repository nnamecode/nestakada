"""Code-owned local candidate. No HTTP/environment flag enables runtime writes."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

from django.conf import settings
from django.db import connection
from .faults import SharedFault
from .storage import SharedStorage


@dataclass(frozen=True)
class Profile:
    identifier: str = 'shared-local-lc-v1'
    reserve_bytes: int = 4194304
    usage_abort_debt_allowance: int = 524288
    fs_metadata_per_object: int = 4096
    usage_growth_allowance: int = 1048576
    core_growth_headroom: int = 2097152
    maintenance_reserve: int = 2097152


CANDIDATE = Profile()
LOCAL_RUNTIME_ENABLED = True
EXPECTED_SCHEMA_SIGNATURE = 'a4190d7eb672ccc7de7453158803d2d826d1c9a9923e3ba802cc2feb7b54cf14'
EXPECTED_FS_ID = 16471834453763965976
ADMITTED_BOOK_RESERVES = {'shared-local-v1': 4194304, 'shared-local-lc-v1': 4194304}
_CALIBRATION = ContextVar('shared_local_calibration', default=None)


def profile():
    if _CALIBRATION.get() is not None:
        from .quota import schema_signature
        if schema_signature() != _CALIBRATION.get()['schemaSignature']:
            raise SharedFault('SHARED_PROFILE_SCHEMA_CHANGED', 503)
        return CANDIDATE
    if LOCAL_RUNTIME_ENABLED and settings.ENVIRONMENT in ('dev', 'test'):
        from .quota import schema_signature
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(),current_user,current_setting('server_version_num'),"
                           "current_setting('block_size')")
            actual = cursor.fetchone()
        fs = os.statvfs(SharedStorage().media_root)
        if (actual == ('estakada_foundation', 'app_runtime', '180006', '8192')
                and fs.f_frsize == 4096 and fs.f_bsize == 4096
                and EXPECTED_FS_ID is not None and getattr(fs, 'f_fsid', None) == EXPECTED_FS_ID
                and len(EXPECTED_SCHEMA_SIGNATURE) == 64 and schema_signature() == EXPECTED_SCHEMA_SIGNATURE):
            return CANDIDATE
    return None


def evidence():
    return _CALIBRATION.get()


def _frozen_source():
    if Path(__file__).resolve().parents[1] != Path('/app'):
        raise SharedFault('SHARED_CALIBRATION_NOT_ISOLATED', 503)
    mount = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()
             if len(line.split()) > 6 and line.split()[4] == '/app']
    if len(mount) != 1 or 'ro' not in mount[0][5].split(','):
        raise SharedFault('SHARED_CALIBRATION_SOURCE_NOT_FROZEN', 503)
    rows = []
    for directory, names, files in os.walk('/app', followlinks=False):
        names[:] = sorted(name for name in names if name != '__pycache__')
        if any((Path(directory) / name).is_symlink() for name in names):
            raise SharedFault('SHARED_CALIBRATION_SOURCE_NOT_FROZEN', 503)
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink():
                raise SharedFault('SHARED_CALIBRATION_SOURCE_NOT_FROZEN', 503)
            rows.append((str(path.relative_to('/app')), hashlib.sha256(path.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest(), len(rows)


@contextmanager
def calibration_scope():
    if (_CALIBRATION.get() is not None or connection.in_atomic_block or not connection.get_autocommit()
            or os.environ.get('ESTAKADA_LOCAL_ENV') != 'test' or settings.ENVIRONMENT != 'test'
            or os.environ.get('DJANGO_SETTINGS_MODULE') != 'estakada.settings.local_http' or settings.DEBUG
            or connection.settings_dict['NAME'] != 'estakada_foundation_unit'):
        raise SharedFault('SHARED_CALIBRATION_NOT_ISOLATED', 503)
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(),current_user,current_setting('server_version_num'),"
                       "current_setting('block_size')")
        database, role, version, block = cursor.fetchone()
    if (database, role) != ('estakada_foundation_unit', 'app_migrator') or version != '180006' or block != '8192':
        raise SharedFault('SHARED_CALIBRATION_NOT_ISOLATED', 503)
    fingerprint, count = _frozen_source()
    fs = os.statvfs(SharedStorage().media_root)
    if fs.f_frsize != 4096 or fs.f_bsize != 4096:
        raise SharedFault('SHARED_CALIBRATION_FILESYSTEM_UNKNOWN', 503)
    from .quota import schema_signature
    record = {'profileId': CANDIDATE.identifier, 'status': 'unvetted', 'sourceFingerprint': fingerprint,
        'sourceFileCount': count, 'schemaSignature': schema_signature(),
        'pgFacts': {'serverVersion': version, 'blockSize': int(block)},
        'fsFacts': {'blockSize': fs.f_bsize, 'fragmentSize': fs.f_frsize, 'fsid': getattr(fs, 'f_fsid', None)},
        'parameters': CANDIDATE.__dict__.copy(), 'events': []}
    token = _CALIBRATION.set(record)
    try:
        yield record
    finally:
        _CALIBRATION.reset(token)
