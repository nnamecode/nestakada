"""FC15: final policy controls on exact UNIT; all writes rolled back."""
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
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(RuntimeError('FC_DEADLINE')))
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
           arg['marker'].startswith('ESTAKADA-DEV15-CAPACITY:'), 'FC_EXPECTED_UNIT')
    namespace = uuid.UUID(arg['runId'])
    ensure(settings.TRUST_WRITE_PROFILE == 'disabled' and os.environ.get('TRUST_TEST_EXECUTION') == '1'
           and connection.settings_dict['NAME'] == 'test_estakada_trust'
           and connection.settings_dict['USER'] == 'trust_migrator', 'FC_UNIT_METADATA')
    CHECKPOINT = 'SOURCE_SCHEMA'
    ensure(P.source_fingerprint() == SOURCE and P.schema_fingerprint() == SCHEMA, 'FC_SOURCE_SCHEMA')

    def identity():
        with connection.cursor() as c:
            c.execute("SELECT current_database(),current_user,session_user,d.oid,shobj_description(d.oid,'pg_database') FROM pg_database d WHERE d.datname=current_database()")
            ensure(c.fetchone() == ('test_estakada_trust', 'trust_migrator', 'trust_migrator', 52766, arg['marker']), 'FC_ACTUAL_UNIT')
            c.execute('SELECT count(*) FROM pg_stat_activity WHERE datid=52766 AND pid<>pg_backend_pid()')
            ensure(c.fetchone() == (0,), 'FC_FOREIGN_SESSION')
            c.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')
            ensure(c.fetchone() == (True,), 'FC_TLS')
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
    ensure(before['counts']['django_migrations'] == 3 and all(n == 0 for table, n in before['counts'].items() if table != 'django_migrations'), 'FC_UNIT_NOT_EMPTY')
    from journal import services as S, state_v2 as V
    from journal.models import AdmissionPolicy
    from journal.protocol import Fault, digest
    fixture = BoundedFixture(methodName='runTest')
    groups = []
    try:
        with transaction.atomic():
            CHECKPOINT = 'FC15_FIXTURE'
            fixture.setUp()
            fixture.start()
            body = fixture.prepare_body('/fc15/pending')
            body['operationId'] = str(uuid.uuid5(namespace, 'FC15:pending'))
            validate(body, 'prepare')
            original = fixture.mutate(body)
            seed = V.persistent_values(Operation.objects.get(pk=body['operationId']))
            CHECKPOINT = 'FC15_POLICY_SIXTEEN'
            for epoch in range(2, 17):
                fixture.activate(fixture.intent(fixture.policy(epoch)))
            fixture.install()
            ensure(AdmissionPolicy.objects.count() == 16, 'FC_POLICY_COUNT')
            history = digest([V.persistent_values(row) for row in AdmissionPolicy.objects.order_by('epoch')])
            saved = state()
            CHECKPOINT = 'FC15_SEVENTEENTH_REFUSED'
            intent17 = fixture.intent(fixture.policy(17))
            try:
                fixture.activate(intent17)
            except Fault as error:
                ensure(error.code == 'ADMISSION_INTENT_REJECTED', 'FC_WRONG_REFUSAL')
            else:
                raise RuntimeError('FC_SEVENTEENTH_ACCEPTED')
            ensure(state() == saved and AdmissionPolicy.objects.count() == 16, 'FC_REFUSAL_CHANGED_STATE')
            groups.append({'id': 'FC15-001', 'policyRows': 16, 'nextPolicyEpoch': 17,
                'refusal': 'ADMISSION_INTENT_REJECTED', 'beforeStateSha256': saved['stateDigest'],
                'afterStateSha256': state()['stateDigest'], 'historySha256': history})

            CHECKPOINT = 'FC15_READS_AFTER_REFUSAL'
            read_head = S.read_head(fixture.reader)
            status = S.operation_status(fixture.reader, body['operationId'])
            manifest = S.snapshot_manifest(fixture.reader)
            page = S.snapshot(fixture.reader, read_head['generation'], 0)
            ensure(status['head'] == read_head == manifest['head'] == page['head'], 'FC_READ_HEADS')
            ensure(status['operation']['stage'] == 'PENDING_DENY' and
                   status['operation']['phases'] == seed['phases'] and
                   manifest['counts'] == {'routes': 1, 'tombstones': 0, 'items': 1} and
                   len(page['items']) == 1 and page['items'][0]['target'] == '/fc15/pending' and
                   page['items'][0]['policy'] == 'PENDING_DENY' and
                   V.persistent_values(Operation.objects.get(pk=body['operationId'])) == seed and
                   state() == saved, 'FC_READ_CHANGED_DENIAL')
            CHECKPOINT = 'FC15_WRITES_AFTER_REFUSAL'
            fresh = fixture.prepare_body('/fc15/new-after-refusal')
            fresh['operationId'] = str(uuid.uuid5(namespace, 'FC15:new'))
            validate(fresh, 'prepare')
            created = fixture.mutate(fresh)
            ensure(not created['replay'] and Operation.objects.count() == 2, 'FC_NEW_PREPARE')
            terminal = fixture.report_body(body)
            validate(terminal, 'report')
            completed = fixture.mutate(terminal, 'report')
            ensure(not completed['replay'] and Operation.objects.get(pk=body['operationId']).stage == 'FINAL_RESTRICTION', 'FC_COMPLETION')
            saved_completed = state()
            replay = fixture.mutate(terminal, 'report')
            prepare_replay = fixture.mutate(body)
            ensure(replay['replay'] and replay['phaseReceipt'] == completed['phaseReceipt'] and
                   prepare_replay['replay'] and prepare_replay['phaseReceipt'] == original['phaseReceipt'] and
                   state() == saved_completed and AdmissionPolicy.objects.count() == 16 and
                   digest([V.persistent_values(row) for row in AdmissionPolicy.objects.order_by('epoch')]) == history,
                   'FC_REPLAY_HISTORY')
            groups.append({'id': 'FC15-002', 'readHead': True, 'operationStatus': True,
                'snapshotManifest': True, 'snapshotPage': True, 'denialAndReservePreservedDuringReads': True,
                'newPrepare': True, 'originalCompletion': True, 'prepareReplayReceiptPreserved': True,
                'terminalReplayReceiptPreserved': True, 'replayStateUnchanged': True,
                'policyRows': 16, 'policyHistoryUnchanged': True, 'historySha256': history})
            transaction.set_rollback(True)
    finally:
        ensure(not connection.in_atomic_block, 'FC_OUTER_ATOMIC_OPEN')
        ensure(fixture.doCleanups(), 'FC_CLEANUP')
    connection.close()
    identity()
    after = raw_state()
    ensure(after == before and P.source_fingerprint() == SOURCE and P.schema_fingerprint() == SCHEMA, 'FC_FINAL_PRESERVATION')
    groups.append({'id': 'FC15-003', 'outerRollbackVerified': True, 'unitBeforeAfterEqual': True})
    signal.alarm(0)
    return {'status': 'PASS', 'scope': 'FC15-final-unit-service-controls', 'groups': groups,
        'unitBefore': before, 'unitAfter': after, 'outerRollbackVerified': True,
        'sourceFingerprint': SOURCE, 'schemaFingerprint': SCHEMA,
        'mainWrites': False, 'mainLeaseIssued': False, 'flushPerformed': False}

if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True, separators=(',', ':')))
    except Exception as error:
        code = getattr(error, 'code', None)
        if type(code) is not str or re.fullmatch('[A-Z0-9_]{1,80}', code) is None:
            code = str(error) if type(error) is RuntimeError else type(error).__name__
        print(json.dumps({'status': 'FAIL', 'code': code, 'checkpoint': CHECKPOINT}))
        raise SystemExit(1) from None
