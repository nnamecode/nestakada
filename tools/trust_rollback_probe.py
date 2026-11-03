"""RB15: late SQL/ENOSPC injection on exact UNIT; all writes rolled back."""
import errno
import hashlib
import json
import os
import re
import signal
import uuid
from unittest.mock import patch

SOURCE = '014efc288de0d32772fca15d63afbb0a4c23a9009ee6ef8bdc877cb1aa41c672'
SCHEMA = '4fb7464026b738b4bc9cfd1dd23657d5e0425c7b3f859e1d9a9ddb97495d4de7'
CHECKPOINT = 'START'


def ensure(value, code):
    if not value:
        raise RuntimeError(code)


def main():
    global CHECKPOINT
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(RuntimeError('RB_DEADLINE')))
    signal.alarm(60)
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection, transaction, DatabaseError
    from journal import profile as P, state_v2 as V
    from journal.models import Head, Operation, RoutePolicy, RequestTombstone
    from journal.test_bounded import BoundedFixture
    from journal.protocol import canonical, closed, validate
    arg = globals().get('ARG')
    closed(arg, {'oid', 'marker', 'runId'})
    ensure(arg['oid'] == 52766 and type(arg['marker']) is str and
           arg['marker'].startswith('ESTAKADA-DEV15-CAPACITY:'), 'RB_EXPECTED_UNIT')
    namespace = uuid.UUID(arg['runId'])
    ensure(settings.TRUST_WRITE_PROFILE == 'disabled' and os.environ.get('TRUST_TEST_EXECUTION') == '1'
           and connection.settings_dict['NAME'] == 'test_estakada_trust'
           and connection.settings_dict['USER'] == 'trust_migrator', 'RB_UNIT_METADATA')
    CHECKPOINT = 'SOURCE_SCHEMA'
    ensure(P.source_fingerprint() == SOURCE and P.schema_fingerprint() == SCHEMA, 'RB_SOURCE_SCHEMA')

    def identity():
        with connection.cursor() as c:
            c.execute("SELECT current_database(),current_user,session_user,d.oid,shobj_description(d.oid,'pg_database') FROM pg_database d WHERE d.datname=current_database()")
            ensure(c.fetchone() == ('test_estakada_trust', 'trust_migrator', 'trust_migrator', 52766, arg['marker']), 'RB_ACTUAL_UNIT')
            c.execute('SELECT count(*) FROM pg_stat_activity WHERE datid=52766 AND pid<>pg_backend_pid()')
            ensure(c.fetchone() == (0,), 'RB_FOREIGN_SESSION')
            c.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')
            ensure(c.fetchone() == (True,), 'RB_TLS')
            c.execute("SET statement_timeout='5s'")
            c.execute("SET lock_timeout='1s'")

    def raw_state():
        models = {m._meta.db_table: m for m in (Head, *(m for m, _ in V.TABLES))}
        h = hashlib.sha256(b'RB15-ALL-ROWS-v1\x00')
        counts = {}
        for table in sorted([*models, 'django_migrations']):
            V._frame(h, {'table': table})
            pk = models[table]._meta.pk.column if table in models else 'id'
            with connection.cursor() as c:
                c.execute('SELECT row_to_json(t) FROM "' + table + '" t ORDER BY "' + pk + '"')
                count = 0
                for (row,) in c:
                    V._frame(h, json.loads(row) if type(row) is str else row)
                    count += 1
            V._frame(h, {'count': count})
            counts[table] = count
        with connection.cursor() as c:
            c.execute('SELECT last_value,is_called FROM trust.django_migrations_id_seq')
            value, called = c.fetchone()
        return {'rowsSha256': h.hexdigest(), 'counts': counts, 'migrationSequence': [value, called]}

    def state():
        head = Head.objects.get(pk=1)
        return {'raw': raw_state(), 'head': V.persistent_values(head), 'stateDigest': V.state_digest(head)}

    CHECKPOINT = 'UNIT_IDENTITY'
    identity()
    before = raw_state()
    ensure(before['counts']['django_migrations'] == 3 and all(n == 0 for table, n in before['counts'].items() if table != 'django_migrations'), 'RB_UNIT_NOT_EMPTY')
    fixture = BoundedFixture(methodName='runTest')
    groups = []
    try:
        with transaction.atomic():
            CHECKPOINT = 'FIXTURE_SETUP'
            fixture.setUp()
            CHECKPOINT = 'FIXTURE_START'
            fixture.start()
            CHECKPOINT = 'FIXTURE_BASELINE'
            baseline = state()
            bases = [('prepare', 'sql', 'RB15-001'), ('prepare', 'disk', 'RB15-002'),
                     ('report', 'sql', 'RB15-003'), ('report', 'disk', 'RB15-004')]
            cases = [(phase, fault, base + '-' + shape, shape)
                     for phase, fault, base in bases for shape in ('ROUTE', 'TOMB')]
            for phase, fault, label, shape in cases:
                with transaction.atomic():
                    CHECKPOINT = label + '_DTO'
                    identifier = str(uuid.uuid5(namespace, label))
                    body = fixture.prepare_body('/rb15/' + label + '/a')
                    body['operationId'] = identifier
                    body['policies'].append({'target': '/rb15/' + label + '/b',
                        'objectId': str(uuid.uuid5(namespace, label + '-object')), 'policy': 'DELETED', 'redirectTarget': None})
                    if shape == 'TOMB':
                        body['kind'] = 'request_tombstone'
                        body['policies'] = []
                        body['requestIds'] = [str(uuid.uuid5(namespace, label + '-request'))]
                    validate(body, 'prepare')
                    if phase == 'report':
                        CHECKPOINT = label + '_PREPARE'
                        fixture.mutate(body)
                        dto = fixture.report_body(body)
                    else:
                        dto = body
                    saved = state()
                    witness = {}

                    def injected_save(head, *args, **kwargs):
                        op = Operation.objects.get(pk=identifier)
                        policies = list(RoutePolicy.objects.filter(operation=op).order_by('key').values_list('policy', flat=True))
                        tombs = RequestTombstone.objects.filter(operation=op).count()
                        expected_phase = 'prepare' if phase == 'prepare' else 'committed'
                        expected_routes, expected_tombs = (2, 0) if shape == 'ROUTE' else (0, 1)
                        ensure(len(policies) == expected_routes and tombs == expected_tombs and expected_phase in op.phases, 'RB_NO_LATE_WRITES')
                        ensure(policies == ([('PENDING_DENY' if phase == 'prepare' else 'DELETED')] * expected_routes), 'RB_LATE_POLICY_STATE')
                        witness.update({'operationExists': True, 'routeRows': len(policies), 'tombRows': tombs,
                            'phaseExists': True, 'stage': op.stage, 'operationReserve': op.reserve_bytes,
                            'uncommittedStateSha256': V.state_digest(Head.objects.get(pk=1))})
                        if fault == 'sql':
                            with connection.cursor() as c:
                                c.execute('SELECT 1/0')
                            raise RuntimeError('RB_SQL_DID_NOT_FAIL')
                        raise OSError(errno.ENOSPC, 'RB15 synthetic disk error')

                    caught = None
                    CHECKPOINT = label + '_INJECTION'
                    try:
                        with patch.object(Head, 'save', injected_save):
                            fixture.mutate(dto, phase)
                    except DatabaseError as error:
                        ensure(fault == 'sql' and getattr(error.__cause__, 'sqlstate', None) == '22012', 'RB_WRONG_SQLSTATE')
                        caught = '22012'
                    except OSError as error:
                        ensure(fault == 'disk' and error.errno == errno.ENOSPC, 'RB_WRONG_ERRNO')
                        caught = 'ENOSPC28_INJECTED'
                    CHECKPOINT = label + '_ROLLBACK_CHECK'
                    rolled_back = state()
                    ensure(caught is not None and witness and rolled_back == saved, 'RB_ROLLBACK_MISMATCH')
                    CHECKPOINT = label + '_RETRY'
                    retried = fixture.mutate(dto, phase)
                    after_retry = state()
                    replay = fixture.mutate(dto, phase)
                    ensure(not retried['replay'] and replay['replay'] and replay['phaseReceipt'] == retried['phaseReceipt']
                           and state() == after_retry, 'RB_EXACT_REPLAY')
                    ensure(after_retry['head']['generation'] == saved['head']['generation'] + 1, 'RB_RETRY_HEAD_ADVANCE')
                    groups.append({'id': label, 'shape': shape, 'phase': phase, 'failure': caught, 'witness': witness,
                        'beforeStateSha256': saved['stateDigest'], 'rollbackStateSha256': rolled_back['stateDigest'],
                        'sameDtoSha256': hashlib.sha256(canonical(dto)).hexdigest(), 'operationId': identifier,
                        'sameUuidRetry': True, 'exactReplay': True, 'retryHeadAdvances': 1,
                        'reserveBefore': saved['head']['reserved_bytes'],
                        'sameReceiptSha256': hashlib.sha256(canonical(replay['phaseReceipt'])).hexdigest()})
                    transaction.set_rollback(True)
                ensure(state() == baseline, 'RB_BRANCH_ROLLBACK')
            transaction.set_rollback(True)
    finally:
        ensure(not connection.in_atomic_block, 'RB_OUTER_ATOMIC_STILL_OPEN')
        ensure(fixture.doCleanups(), 'RB_FIXTURE_CLEANUP_FAILED')
    connection.close()
    identity()
    after = raw_state()
    ensure(after == before and P.source_fingerprint() == SOURCE and P.schema_fingerprint() == SCHEMA, 'RB_FINAL_PRESERVATION')
    signal.alarm(0)
    return {'status': 'PASS', 'scope': 'RP15-015-real-unit-atomic-rollback', 'groups': groups,
            'unitBefore': before, 'unitAfter': after, 'outerRollbackVerified': True,
            'sourceFingerprint': SOURCE, 'schemaFingerprint': SCHEMA,
            'sqlErrorsFromServer': 4, 'diskExceptionsInjected': 4,
            'mainWrites': False, 'physicalDiskFull': False, 'flushPerformed': False}


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True, separators=(',', ':')))
    except Exception as error:
        code = getattr(error, 'code', None)
        if type(code) is not str or re.fullmatch('[A-Z0-9_]{1,80}', code) is None:
            code = str(error) if type(error) is RuntimeError else type(error).__name__
        print(json.dumps({'status': 'FAIL', 'code': code, 'checkpoint': CHECKPOINT}))
        raise SystemExit(1) from None
