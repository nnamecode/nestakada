"""Bounded real PG saturation in the code-owned, separate TRUST test database.

No clearing/reset, no main DB, no profile activation. Test Runner must leave this
database empty; a prior partial calibration is preserved and requires diagnosis.
"""
import hashlib
import json
import os
import random
import signal
import string
import time
import uuid
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trust_service.settings')
import django
django.setup()
from django.db import connection
from journal import auth, services as service
from journal.models import Head, Credential, Operation, RoutePolicy, RequestTombstone
from journal.protocol import Fault


def ensure(condition, code):
    if not condition:
        raise RuntimeError(code)


def cgroup():
    root = Path('/sys/fs/cgroup')
    return {'peak': int((root / 'memory.peak').read_text()),
            'max': int((root / 'memory.max').read_text()),
            'memoryEvents': dict((key, int(value)) for key, value in
                                (line.split() for line in (root / 'memory.events').read_text().splitlines())),
            'cpu': dict((key, int(value)) for key, value in
                        (line.split() for line in (root / 'cpu.stat').read_text().splitlines()))}


groups = []
try:
    ensure(connection.settings_dict['NAME'] == 'test_estakada_trust' and
           os.environ.get('TRUST_TEST_EXECUTION') == '1', 'CALIBRATION_SCOPE')
    signal.alarm(240)
    ensure(not any(model.objects.exists() for model in
                   [Head, Credential, Operation, RoutePolicy, RequestTombstone]), 'CALIBRATION_NOT_EMPTY')
    identity = auth.identity()
    service.bootstrap(identity)
    key = next(item for item in auth.configuration().values() if item['role'] == 'writer')
    actor = auth.authenticate('Bearer ' + key['id'] + ':' + key['secret'], 'writer')
    before = service.physical_facts()
    generator = random.Random(37420261102)
    alphabet = string.ascii_letters + string.digits + '-_'
    started = time.monotonic()
    latencies = []
    maximum_reserved = 0
    refusal = None
    reserve_refusal = False
    pending = []
    finalization_ms = []
    phase = 'reserve'

    def finish(body):
        current = Head.objects.get(pk=1)
        report = {'operationId': body['operationId'], 'incarnation': identity,
                  'expectedGeneration': str(current.generation), 'writerEpoch': str(current.writer_epoch),
                  'outcome': 'committed', 'mainIncarnation': str(uuid.uuid4()),
                  'mainReceipt': hashlib.sha256(body['operationId'].encode()).hexdigest(),
                  'policies': body['policies']}
        started_finish = time.monotonic()
        terminal = service.mutate(actor, report, 'report')
        ensure(terminal['stage'] == 'FINAL_RESTRICTION' and not terminal['workflowComplete'],
               'CALIBRATION_FALSE_WORKFLOW')
        ensure(service.mutate(actor, body, 'prepare')['replay'], 'CALIBRATION_REPLAY')
        finalization_ms.append(round((time.monotonic() - started_finish) * 1000))

    with service.calibration_mode():
        for index in range(160):
            ensure(time.monotonic() - started < 240, 'CALIBRATION_DEADLINE')
            head = Head.objects.get(pk=1)
            policies = []
            for item in range(256):
                # 2048 UTF-8 bytes per target; fixed seed but incompressible text.
                prefix = '/calibration/' + str(index) + '/' + str(item) + '/'
                target = prefix + ''.join(generator.choices(alphabet, k=2048 - len(prefix)))
                policies.append({'target': target, 'objectId': str(uuid.uuid4()),
                                 'policy': 'DELETED', 'redirectTarget': None})
            body = {'operationId': str(uuid.uuid4()), 'incarnation': identity,
                    'expectedGeneration': str(head.generation), 'writerEpoch': str(head.writer_epoch),
                    'kind': 'route_restriction', 'objectId': str(uuid.uuid4()),
                    'basis': hashlib.sha256(str(index).encode()).hexdigest(),
                    'policies': policies, 'requestIds': []}
            start = time.monotonic()
            try:
                prepared = service.mutate(actor, body, 'prepare')
            except Fault as error:
                ensure(error.code == 'BUDGET_EXHAUSTED', 'UNEXPECTED_CALIBRATION_REFUSAL')
                if phase == 'reserve':
                    current = Head.objects.get(pk=1)
                    ensure(current.logical_bytes < service.LOGICAL_CAP - 1048576 and
                           current.reserved_bytes > service.COMPLETION_CAP - 1048576,
                           'RESERVE_NOT_ACTUALLY_SATURATED')
                    reserve_refusal = True
                    # Resolve one UNKNOWN and every terminal while completion
                    # space is reserved; no quota reset or new dataset.
                    first = pending[0]
                    service.mutate(actor, {'operationId': first['operationId'],
                        'incarnation': identity, 'expectedGeneration': str(current.generation),
                        'writerEpoch': str(current.writer_epoch), 'outcome': 'unknown',
                        'mainIncarnation': None, 'mainReceipt': None, 'policies': []}, 'report')
                    for candidate in pending:
                        finish(candidate)
                    pending.clear()
                    phase = 'logical'
                    continue
                refusal = error.code
                break
            current = Head.objects.get(pk=1)
            maximum_reserved = max(maximum_reserved, current.reserved_bytes)
            if phase == 'reserve':
                pending.append(body)
            else:
                finish(body)
            latencies.append(round((time.monotonic() - start) * 1000))
    ensure(reserve_refusal and refusal == 'BUDGET_EXHAUSTED' and len(latencies) > 20,
           'CAP_NOT_REACHED')
    head = Head.objects.get(pk=1)
    counts = {'operations': Operation.objects.count(), 'policies': RoutePolicy.objects.count(),
              'tombstones': RequestTombstone.objects.count()}
    ensure(head.reserved_bytes == 0 and counts['policies'] == 256 * counts['operations'],
           'CALIBRATION_PARTIAL_ROWS')
    ensure(RoutePolicy.objects.exclude(policy='DELETED').count() == 0, 'CALIBRATION_PARTIAL_POLICY')
    after = service.physical_facts()
    usage = cgroup()
    ensure(usage['max'] == 268435456 and usage['peak'] <= usage['max'] and
           usage['memoryEvents'].get('oom', 0) == 0 and usage['memoryEvents'].get('oom_kill', 0) == 0,
           'CALIBRATION_PROCESS_RESOURCE')
    ensure(after['databaseBytes'] < 2 * 1024 ** 3, 'CALIBRATION_DATABASE_BUDGET')
    print(json.dumps({'status': 'PASS', 'scope': 'isolated-test-db-saturation-not-write-profile-approval',
        'before': before, 'after': after, 'counts': counts, 'generation': str(head.generation),
        'logicalBytes': head.logical_bytes, 'reservedBytes': head.reserved_bytes,
        'maximumReservedBytes': maximum_reserved, 'reserveRefusal': reserve_refusal,
        'refusal': refusal, 'elapsedSeconds': round(time.monotonic() - started, 3),
        'maxOperationMs': max(latencies), 'maxFinalizeMs': max(finalization_ms),
        'memoryCpu': usage, 'retained': True, 'cleanupPerformed': False}))
except Exception as error:
    # No body, token, SQL statement or exception message reaches the public report.
    print(json.dumps({'status': 'FAIL', 'errorClass': type(error).__name__, 'retained': True}))
    raise SystemExit(1) from None
