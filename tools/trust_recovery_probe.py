"""RF15: bounded-v2 recovery on exact UNIT; all writes rolled back."""
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
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(RuntimeError('RF_DEADLINE')))
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
           arg['marker'].startswith('ESTAKADA-DEV15-CAPACITY:'), 'RF_EXPECTED_UNIT')
    namespace = uuid.UUID(arg['runId'])
    ensure(settings.TRUST_WRITE_PROFILE == 'disabled' and os.environ.get('TRUST_TEST_EXECUTION') == '1'
           and connection.settings_dict['NAME'] == 'test_estakada_trust'
           and connection.settings_dict['USER'] == 'trust_migrator', 'RF_UNIT_METADATA')
    CHECKPOINT = 'SOURCE_SCHEMA'
    ensure(P.source_fingerprint() == SOURCE and P.schema_fingerprint() == SCHEMA, 'RF_SOURCE_SCHEMA')

    def identity():
        with connection.cursor() as c:
            c.execute("SELECT current_database(),current_user,session_user,d.oid,shobj_description(d.oid,'pg_database') FROM pg_database d WHERE d.datname=current_database()")
            ensure(c.fetchone() == ('test_estakada_trust', 'trust_migrator', 'trust_migrator', 52766, arg['marker']), 'RF_ACTUAL_UNIT')
            c.execute('SELECT count(*) FROM pg_stat_activity WHERE datid=52766 AND pid<>pg_backend_pid()')
            ensure(c.fetchone() == (0,), 'RF_FOREIGN_SESSION')
            c.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')
            ensure(c.fetchone() == (True,), 'RF_TLS')
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
    ensure(before['counts']['django_migrations'] == 3 and all(n == 0 for table, n in before['counts'].items() if table != 'django_migrations'), 'RF_UNIT_NOT_EMPTY')
    import copy
    from pathlib import Path
    from django.test import override_settings
    from journal import auth, bounded as B, recovery as R, services as S
    from journal.models import Credential, RecoveryReceipt
    from journal.protocol import Fault, digest
    fixture = BoundedFixture(methodName='runTest')
    groups = []
    seed_ids = []

    def identifier(label):
        return str(uuid.uuid5(namespace, 'RF15:' + label))

    def seed_state():
        rows = {}
        for model, filters in [(Operation, {'pk__in': seed_ids}),
                               (RoutePolicy, {'operation_id__in': seed_ids}),
                               (RequestTombstone, {'operation_id__in': seed_ids})]:
            rows[model._meta.db_table] = [V.persistent_values(row) for row in
                model.objects.filter(**filters).order_by(model._meta.pk.attname)]
        return {'rowsSha256': digest(rows), 'operations': len(rows['journal_operation']),
                'routes': len(rows['journal_routepolicy']), 'tombs': len(rows['journal_requesttombstone']),
                'operationReserves': [r['reserve_bytes'] for r in rows['journal_operation']]}

    def fail_unchanged(code, fn):
        saved = state()
        try:
            fn()
        except Fault as error:
            ensure(error.code == code, 'RF_WRONG_FAULT_' + error.code)
        else:
            raise RuntimeError('RF_EXPECTED_FAILURE')
        ensure(state() == saved, 'RF_FAILURE_CHANGED_STATE')
        return {'code': code, 'beforeStateSha256': saved['stateDigest'], 'afterStateSha256': state()['stateDigest']}

    def action(phase, previous, new=None, fence_id=None, proof_digest=None, label='action'):
        head = Head.objects.get(pk=1)
        value = {'actionId': identifier(label), 'incarnation': fixture.identity,
            'expectedGeneration': str(head.generation), 'writerEpoch': str(head.writer_epoch),
            'scope': B.SCOPE, 'previousCredentialId': previous, 'newCredentialId': new,
            'fenceActionId': fence_id, 'reconciliationDigest': proof_digest}
        R.validate(value, phase)
        return value

    def descriptor(body, phase):
        return {'id': body['actionId'], 'credentialId': 'recovery', 'writerEpoch': body['writerEpoch'],
                'phase': phase, 'fingerprint': S.semantic(body, fixture.recovery_actor)}

    def install(body, phase, lease=None):
        lease = copy.deepcopy(lease) if lease is not None else fixture.lease(policy)
        lease['recoveryActions'] = [descriptor(body, phase)]
        fixture.install(policy, lease)
        return lease

    def rotate(name, secret):
        fixture.runtime = identifier(name + '-runtime')
        fixture.items.append({'id': name, 'principal': name + '-machine', 'role': 'writer', 'secret': secret})
        Path(fixture.tmp.name, 'keys').write_bytes(canonical({'schemaVersion': 1, 'credentials': fixture.items}))
        scope = override_settings(TRUST_RUNTIME_ID=fixture.runtime)
        scope.enable()
        fixture.addCleanup(scope.disable)

    def activation(fence_body, fenced, previous_runtime, new_name, label):
        head = Head.objects.select_for_update().get(pk=1)
        full = V.state_digest(head)
        lease = fixture.lease(policy)
        lease['exclusion']['previousRuntimeId'] = previous_runtime
        lease['reconciliation'] = {'fenceActionId': fence_body['actionId'],
            'fenceReceiptDigest': digest(fenced['recoveryReceipt']), 'head': S.head_dict(head),
            'stateDigestVersion': 2, 'stateDigest': full, 'runtimeId': fixture.runtime,
            'credentialConfigSha256': B._configuration_sha(), 'exclusion': copy.deepcopy(lease['exclusion'])}
        body = action('activate', fence_body['previousCredentialId'], new_name,
                      fence_body['actionId'], full, label)
        return body, install(body, 'activate', lease)

    def exact_replay(body, phase, first):
        saved = state()
        replay = R.mutate(fixture.recovery_actor, body, phase)
        ensure(replay['replay'] and replay['recoveryReceipt'] == first['recoveryReceipt']
               and state() == saved, 'RF_EXACT_REPLAY')
        return digest(replay['recoveryReceipt'])

    def writer_prepare(name, secret, label):
        writer = auth.authenticate('Bearer ' + name + ':' + secret, 'writer')
        body = fixture.prepare_body('/rf15/' + label)
        body['operationId'] = identifier(label)
        body['writerEpoch'] = str(Head.objects.get(pk=1).writer_epoch)
        validate(body, 'prepare')
        value = S.mutate(writer, body, 'prepare')
        ensure(not value['replay'], 'RF_NEW_WRITER_NOT_NEW')
        return {'operationId': body['operationId'], 'writerEpoch': body['writerEpoch'], 'status': 'ACCEPTED'}

    try:
        with transaction.atomic():
            CHECKPOINT = 'RF_FIXTURE_SETUP'
            fixture.setUp()
            envelope = fixture.start()
            policy = copy.deepcopy(envelope['payload']['policy'])
            route = fixture.prepare_body('/rf15/pending-a')
            route['operationId'] = identifier('seed-route')
            route['policies'].append({'target': '/rf15/pending-b', 'objectId': identifier('seed-object'),
                                      'policy': 'DELETED', 'redirectTarget': None})
            validate(route, 'prepare'); fixture.mutate(route)
            unknown = fixture.report_body(route, 'unknown'); validate(unknown, 'report')
            fixture.mutate(unknown, 'report')
            tomb = fixture.prepare_body()
            tomb.update({'operationId': identifier('seed-tomb'), 'kind': 'request_tombstone',
                         'policies': [], 'requestIds': [identifier('seed-request')]})
            validate(tomb, 'prepare'); fixture.mutate(tomb)
            seed_ids = [route['operationId'], tomb['operationId']]
            protected = seed_state()
            ensure(protected['operations'] == 2 and protected['routes'] == 2 and protected['tombs'] == 1
                   and all(n > 0 for n in protected['operationReserves']), 'RF_SEED_SHAPE')
            ensure(Operation.objects.get(pk=route['operationId']).stage == 'MAIN_RESULT_UNKNOWN', 'RF_SEED_UNKNOWN')
            fence = action('fence', 'writer', label='fence-1')
            CHECKPOINT = 'RF15_001_NO_DESCRIPTOR'
            missing = fail_unchanged('WRITE_PERMIT_SCOPE_REJECTED', lambda: R.mutate(fixture.recovery_actor, fence, 'fence'))
            groups.append({'id': 'RF15-001', 'protectedSeed': protected, 'missingDescriptor': missing})

            CHECKPOINT = 'RF15_002_FENCE_FAILURE'
            install(fence, 'fence')
            saved = state(); witness = {}
            def fail_fence(head, *args, **kwargs):
                ensure(RecoveryReceipt.objects.filter(pk=fence['actionId']).exists()
                       and not Credential.objects.filter(role='writer', active=True).exists(), 'RF_NO_FENCE_LATE_WRITES')
                witness.update({'receiptInserted': True, 'writersRevokedInsideTransaction': True,
                                'uncommittedStateSha256': state()['stateDigest']})
                raise OSError(errno.ENOSPC, 'RF15 synthetic disk error')
            try:
                with patch.object(Head, 'save', fail_fence):
                    R.mutate(fixture.recovery_actor, fence, 'fence')
            except OSError as error:
                ensure(error.errno == errno.ENOSPC, 'RF_FENCE_ERRNO')
            else:
                raise RuntimeError('RF_FENCE_DID_NOT_FAIL')
            ensure(state() == saved and witness and seed_state() == protected, 'RF_FENCE_ROLLBACK')
            fenced = R.mutate(fixture.recovery_actor, fence, 'fence')
            fence_receipt = exact_replay(fence, 'fence', fenced)
            ensure(Head.objects.get(pk=1).mode == 'FROZEN' and RecoveryReceipt.objects.count() == 1, 'RF_NOT_FROZEN')
            groups.append({'id': 'RF15-002', 'injectedError': 'ENOSPC28', 'witness': witness,
                           'rollbackEqual': True, 'sameActionRetry': True, 'exactReceiptSha256': fence_receipt})

            CHECKPOINT = 'RF15_003_BINDING'
            old = fixture.prepare_body('/rf15/old-frozen'); old['writerEpoch'] = '2'
            old_key = fail_unchanged('CREDENTIAL_REVOKED', lambda: fixture.mutate(old))
            old_runtime = fixture.runtime
            rotate('writer2', '4' * 64)
            sql_calls = []
            def observe(execute, sql, params, many, context):
                sql_calls.append(1)
                return execute(sql, params, many, context)
            try:
                with connection.execute_wrapper(observe):
                    B.read_envelope()
            except Fault as error:
                ensure(error.code == 'BOUNDED_ADMISSION_REJECTED', 'RF_STALE_BINDING_CODE')
            else:
                raise RuntimeError('RF_STALE_BINDING_ACCEPTED')
            ensure(not sql_calls and seed_state() == protected, 'RF_STALE_BINDING_SQL')
            activate, lease = activation(fence, fenced, old_runtime, 'writer2', 'activate-1')
            groups.append({'id': 'RF15-003', 'oldKeyFreshEpoch': old_key, 'staleBindingSqlCalls': 0,
                           'stillFrozen': Head.objects.get(pk=1).mode == 'FROZEN'})

            CHECKPOINT = 'RF15_004_BAD_PROOFS'
            bad_results = []
            for kind in ('digest', 'previous-runtime'):
                bad = copy.deepcopy(lease)
                if kind == 'digest':
                    bad['reconciliation']['stateDigest'] = 'f' * 64
                else:
                    bad['exclusion']['previousRuntimeId'] = identifier('wrong-previous-runtime')
                    bad['reconciliation']['exclusion'] = copy.deepcopy(bad['exclusion'])
                install(activate, 'activate', bad)
                bad_results.append({'kind': kind, **fail_unchanged('RECOVERY_PRECONDITION_FAILED',
                    lambda: R.mutate(fixture.recovery_actor, activate, 'activate'))})
            lease = install(activate, 'activate', lease)
            groups.append({'id': 'RF15-004', 'negativeProofs': bad_results, 'protectedSeedUnchanged': seed_state() == protected})

            CHECKPOINT = 'RF15_005_ACTIVATE_FAILURE'
            saved = state(); witness = {}
            def fail_activate(head, *args, **kwargs):
                ensure(Credential.objects.filter(pk='writer2', active=True).exists()
                       and RecoveryReceipt.objects.filter(pk=activate['actionId']).exists(), 'RF_NO_ACTIVATE_LATE_WRITES')
                ensure(Head.objects.get(pk=1).mode == 'FROZEN', 'RF_HEAD_SAVED_BEFORE_INJECTION')
                witness.update({'newCredentialInserted': True, 'activateReceiptInserted': True,
                                'uncommittedStateSha256': state()['stateDigest']})
                with connection.cursor() as cursor:
                    cursor.execute('SELECT 1/0')
                raise RuntimeError('RF_SQL_DID_NOT_FAIL')
            try:
                with patch.object(Head, 'save', fail_activate):
                    R.mutate(fixture.recovery_actor, activate, 'activate')
            except DatabaseError as error:
                ensure(getattr(error.__cause__, 'sqlstate', None) == '22012', 'RF_SQLSTATE')
            else:
                raise RuntimeError('RF_ACTIVATE_DID_NOT_FAIL')
            ensure(state() == saved and witness and not Credential.objects.filter(pk='writer2').exists()
                   and RecoveryReceipt.objects.count() == 1 and seed_state() == protected, 'RF_ACTIVATE_ROLLBACK')
            activated = R.mutate(fixture.recovery_actor, activate, 'activate')
            activation_receipt = exact_replay(activate, 'activate', activated)
            ensure(Head.objects.get(pk=1).mode == 'ACTIVE' and RecoveryReceipt.objects.count() == 2, 'RF_ACTIVATE_RESULT')
            groups.append({'id': 'RF15-005', 'serverSqlState': '22012', 'witness': witness,
                           'frozenRollbackEqual': True, 'sameActionRetry': True, 'exactReceiptSha256': activation_receipt})

            CHECKPOINT = 'RF15_006_WRITER_CONTROL'
            old = fixture.prepare_body('/rf15/old-active'); old['writerEpoch'] = '2'
            old_key = fail_unchanged('CREDENTIAL_REVOKED', lambda: fixture.mutate(old))
            new_write = writer_prepare('writer2', '4' * 64, 'writer2-control')
            ensure(seed_state() == protected, 'RF_SEED_CHANGED_AFTER_RECOVERY')
            groups.append({'id': 'RF15-006', 'oldKeyFreshEpoch': old_key, 'newWriterPrepare': new_write,
                           'protectedSeedUnchanged': True})

            CHECKPOINT = 'RF15_007_RECEIPT_LIMIT'
            fence2 = action('fence', 'writer2', label='fence-2')
            install(fence2, 'fence')
            fenced2 = R.mutate(fixture.recovery_actor, fence2, 'fence')
            exact_replay(fence2, 'fence', fenced2)
            runtime2 = fixture.runtime
            rotate('writer3', '5' * 64)
            activate2, lease2 = activation(fence2, fenced2, runtime2, 'writer3', 'activate-2')
            activated2 = R.mutate(fixture.recovery_actor, activate2, 'activate')
            ensure(RecoveryReceipt.objects.count() == 4, 'RF_RECEIPTS_NOT_FOUR')
            next_fence = action('fence', 'writer3', label='fence-3-over-cap')
            lease2['recoveryActions'] = [descriptor(activate2, 'activate'), descriptor(next_fence, 'fence')]
            fixture.install(policy, lease2)
            cap = fail_unchanged('RECOVERY_COUNT_CAP', lambda: R.mutate(fixture.recovery_actor, next_fence, 'fence'))
            cap_replay = exact_replay(activate2, 'activate', activated2)
            after_cap_write = writer_prepare('writer3', '5' * 64, 'writer3-after-cap')
            ensure(RecoveryReceipt.objects.count() == 4 and seed_state() == protected
                   and Credential.objects.count() == 5, 'RF_CAP_CHANGED_HISTORY')
            groups.append({'id': 'RF15-007', 'actualReceiptCount': 4, 'credentialCount': 5,
                           'nextFence': cap, 'exactReplayAtCapSha256': cap_replay,
                           'writerPrepareAtCap': after_cap_write, 'protectedSeedUnchanged': True,
                           'policyRows': B.AdmissionPolicy.objects.count()})
            transaction.set_rollback(True)
    finally:
        ensure(not connection.in_atomic_block, 'RF_OUTER_ATOMIC_STILL_OPEN')
        ensure(fixture.doCleanups(), 'RF_FIXTURE_CLEANUP_FAILED')
    connection.close()
    identity()
    after = raw_state()
    ensure(after == before and P.source_fingerprint() == SOURCE and P.schema_fingerprint() == SCHEMA, 'RF_FINAL_PRESERVATION')
    groups.append({'id': 'RF15-008', 'outerRollbackVerified': True, 'rawBeforeAfterEqual': True,
                   'unitOid': 52766, 'freshMainSql': 'PARENT_READONLY_WITNESS'})
    signal.alarm(0)
    return {'status': 'PASS', 'scope': 'RP15-007-019-real-unit-recovery', 'groups': groups,
            'unitBefore': before, 'unitAfter': after, 'outerRollbackVerified': True,
            'sourceFingerprint': SOURCE, 'schemaFingerprint': SCHEMA,
            'recoveryReceiptsCreatedInTransaction': 4, 'serverSqlErrors': 1,
            'injectedEnospcErrors': 1, 'protectedSeedPreserved': True,
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
