"""Read-only, closed network witnesses; original run fixture is separate."""
import fcntl
import json
import os
import re
import stat
import sys

SAFE = 2**53 - 1
OPS = {'network_observer_read', 'network_slot_try', 'network_pg_try'}


def uint(value):
    return type(value) is int and 0 <= value <= SAFE


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('DUPLICATE_JSON_KEY')
        value[key] = item
    return value


def owned(info):
    return (stat.S_ISREG(info.st_mode) and info.st_uid == 10001 and
            info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600)


def snapshot(run):
    path = '/tmp/estakada-network-observer.json'
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if not owned(info) or not 0 < info.st_size <= 65536:
            raise ValueError('OBSERVER_FILE_BOUNDARY')
        data = b''
        while len(data) <= 65536:
            part = os.read(fd, min(8192, 65537 - len(data)))
            if not part:
                break
            data += part
        if len(data) > 65536:
            raise ValueError('OBSERVER_FILE_BOUNDARY')
        # An atomic replacement is legitimate; the opened inode is immutable.
        after = os.fstat(fd)
        if (after.st_dev, after.st_ino, after.st_size) != (info.st_dev, info.st_ino, info.st_size):
            raise ValueError('OBSERVER_OPENED_FILE_CHANGED')
    finally:
        os.close(fd)
    value = json.loads(data.decode('utf-8'), object_pairs_hook=unique)
    keys = {'version', 'run', 'ready', 'fault', 'sequence', 'updatedMs', 'installCount', 'requests'}
    if (type(value) is not dict or set(value) != keys or type(value['version']) is not int or value['version'] != 1
            or value['run'] != run or type(value['ready']) is not bool or type(value['fault']) is not bool
            or not uint(value['sequence']) or not uint(value['updatedMs'])
            or type(value['installCount']) is not int or value['installCount'] != 1
            or type(value['requests']) is not list or len(value['requests']) > 32):
        raise ValueError('OBSERVER_SCHEMA')
    prior = 0
    for row in value['requests']:
        expected = {'id', 'events', 'timesMs', 'status', 'outcome', 'timerAlive',
                    'duplicateClosed', 'expired', 'slotFdClosed'}
        if (type(row) is not dict or set(row) != expected or type(row['id']) is not int
                or not prior < row['id'] <= 32 or type(row['events']) is not list or len(row['events']) != 10
                or not all(uint(item) for item in row['events'])
                or type(row['timesMs']) is not list or len(row['timesMs']) != 10
                or not all(item is None or uint(item) for item in row['timesMs'])
                or not (row['status'] is None or type(row['status']) is int and 100 <= row['status'] <= 599)
                or type(row['outcome']) is not int or not 0 <= row['outcome'] <= 7
                or any(row[name] is not None and type(row[name]) is not bool for name in
                       ('timerAlive', 'duplicateClosed', 'expired', 'slotFdClosed'))):
            raise ValueError('OBSERVER_RECORD_SCHEMA')
        prior = row['id']
    return value


def slot():
    path = '/tmp/estakada-editor.slot'
    try:
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return {'exists': False, 'busy': False, 'device': None, 'inode': None}
    acquired = False
    try:
        info = os.fstat(fd)
        if not owned(info):
            raise ValueError('SLOT_FILE_BOUNDARY')
        current = os.stat(path, follow_symlinks=False)
        if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError('SLOT_IDENTITY_CHANGED')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired, busy = True, False
        except BlockingIOError:
            busy = True
        return {'exists': True, 'busy': busy, 'device': str(info.st_dev), 'inode': str(info.st_ino)}
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def execute(request):
    if (type(request) is not dict or set(request) != {'operation', 'run'} or request['operation'] not in OPS
            or type(request['run']) is not str or re.fullmatch('[0-9a-f]{32}', request['run']) is None
            or request['run'] != os.environ.get('ESTAKADA_NETWORK_PROBE_RUN')
            or os.environ.get('ESTAKADA_LOCAL_ENV') != 'test' or os.geteuid() != 10001):
        raise ValueError('NETWORK_WITNESS_BOUNDARY')
    if request['operation'] == 'network_observer_read':
        return snapshot(request['run'])
    if request['operation'] == 'network_slot_try':
        return slot()
    if os.environ.get('DJANGO_SETTINGS_MODULE') != 'estakada.settings.local_http':
        raise ValueError('NETWORK_DATABASE_PROFILE')
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection, transaction
    if settings.DATABASES['default']['NAME'] != 'estakada_foundation':
        raise ValueError('NETWORK_DATABASE_PROFILE')
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_try_advisory_xact_lock(%s)', [7342810401])
                content = cursor.fetchone()[0]
                auth = False
                if content:
                    cursor.execute('SELECT pg_try_advisory_xact_lock(%s)', [7342810301])
                    auth = cursor.fetchone()[0]
            transaction.set_rollback(True)
        return {'content': content is True, 'auth': auth is True}
    finally:
        connection.close()


if __name__ == '__main__':
    try:
        wire = sys.stdin.buffer.read(2049)
        if len(wire) > 2048:
            raise ValueError('NETWORK_REQUEST_BOUND')
        print(json.dumps(execute(json.loads(wire.decode('utf-8'), object_pairs_hook=unique)),
                         separators=(',', ':'), allow_nan=False))
    except Exception as error:
        print(json.dumps({'errorClass': type(error).__name__, 'code': 'NETWORK_WITNESS_FAILED'}), file=sys.stderr)
        raise SystemExit(1)
