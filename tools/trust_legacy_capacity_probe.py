"""LG15: real legacy rows, fixed admission caps, three isolated rollback branches.

The private ARG/export is never included in the public report. The 995-operation
fill is explicitly a bulk fixture, not 995 successful service/API transitions.
No bootstrap, flush, DELETE, test runner or MAIN connection is used here.
"""
import copy
import hashlib
import hmac
import json
import os
import re
import signal
import tempfile
import time
import uuid
from pathlib import Path

SOURCE = '014efc288de0d32772fca15d63afbb0a4c23a9009ee6ef8bdc877cb1aa41c672'
SCHEMA = '4fb7464026b738b4bc9cfd1dd23657d5e0425c7b3f859e1d9a9ddb97495d4de7'
MAIN_V2 = 'dfdf4021db5dba1b807699b548e4370488fb3582e9c87734206f8f91ee3c6066'


class ProbeFailure(Exception):
    pass


def ensure(value, code):
    if not value:
        raise ProbeFailure(code)


def resources():
    root = Path('/sys/fs/cgroup')
    def number(name):
        value = (root / name).read_text(encoding='ascii').strip()
        return int(value) if value.isdecimal() else value
    def pairs(name):
        return {key: int(value) for key, value in
            (line.split() for line in (root / name).read_text(encoding='ascii').splitlines())}
    return {'memoryPeak': number('memory.peak'), 'memoryCurrent': number('memory.current'),
        'memoryMax': number('memory.max'), 'memoryEvents': pairs('memory.events'),
        'cpuMax': (root / 'cpu.max').read_text(encoding='ascii').strip(),
        'cpuStat': pairs('cpu.stat'), 'pidsMax': number('pids.max'),
        'pidsCurrent': number('pids.current'),
        'pidsPeak': number('pids.peak') if (root / 'pids.peak').exists() else 'NOT_MEASURED'}


def main():
    started = time.monotonic()
    report = {'status': 'FAIL', 'scope': 'RP15-008-legacy-inclusion-rollback-only',
        'sourceFingerprint': SOURCE, 'deadlineSeconds': 120, 'groups': [],
        'bulkFixtureIsServicePass': False, 'mainWrites': False, 'archiveWrites': False,
        'mainActivation': False, 'htmlAdmission': False, 'workflowComplete': False,
        'outerRollbackVerified': False, 'cleanupErrors': [], 'resources': {}}
    before_raw = None
    raw_state = None
    connection = None
    def expire(*_):
        raise ProbeFailure('LG_PROBE_DEADLINE')
    signal.signal(signal.SIGALRM, expire); signal.alarm(120)
    try:
        import django
        django.setup()
        from django.conf import settings
        from django.db import connection, transaction
        from django.test import override_settings
        from journal import auth, bounded as B, profile as P, services as S, state_v2 as V
        from journal.models import (AdmissionPolicy, Credential, Head, Operation,
            RecoveryReceipt, RequestTombstone, RoutePolicy)
        from journal.protocol import Fault, MAX_BODY, canonical, closed, digest, uid, validate
        arg = globals().get('ARG')
        closed(arg, {'export', 'exportSha256', 'unit', 'operator', 'credentialConfigSha256'})
        closed(arg['unit'], {'oid', 'marker'})
        ensure(type(arg['unit']['oid']) is int and arg['unit']['oid'] == 52766,
            'LG_UNIT_EXPECTED_OID')
        marker = arg['unit']['marker']
        ensure(type(marker) is str and marker.startswith('ESTAKADA-DEV15-CAPACITY:'), 'LG_UNIT_MARKER')
        uid(marker[len('ESTAKADA-DEV15-CAPACITY:'):])
        exported = arg['export']
        closed(exported, {'status', 'scope', 'snapshot', 'snapshotSha256'})
        ensure(len(canonical(exported)) <= 65536 and digest(exported) == arg['exportSha256']
            and exported['status'] == 'PASS' and exported['scope'] == 'LG15-private-main-fixture',
            'LG_EXPORT_LINK')
        snapshot = exported['snapshot']
        closed(snapshot, {'database', 'oid', 'sourceFingerprint', 'schemaFingerprint',
            'stateDigestVersion', 'stateDigest', 'tables', 'counts', 'historicalReferences'})
        ensure(snapshot['database'] == 'estakada_trust' and type(snapshot['oid']) is int
            and snapshot['oid'] == 16384 and snapshot['sourceFingerprint'] == SOURCE
            and snapshot['schemaFingerprint'] == SCHEMA and snapshot['stateDigestVersion'] == 2
            and snapshot['stateDigest'] == MAIN_V2 and digest(snapshot) == exported['snapshotSha256'],
            'LG_EXPORT_EXPECTED_STATE')
        models = (Head, Credential, Operation, RoutePolicy, RequestTombstone, RecoveryReceipt, AdmissionPolicy)
        by_table = {model._meta.db_table: model for model in models}
        closed(snapshot['tables'], by_table)
        expected_counts = {'journal_head': 1, 'journal_credential': 4, 'journal_operation': 4,
            'journal_routepolicy': 3, 'journal_requesttombstone': 1,
            'journal_recoveryreceipt': 2, 'journal_admissionpolicy': 0}
        ensure(snapshot['counts'] == expected_counts, 'LG_EXPORT_COUNTS')
        for table, model in by_table.items():
            rows = snapshot['tables'][table]
            ensure(type(rows) is list and len(rows) == expected_counts[table], 'LG_EXPORT_TABLE_COUNT')
            for row in rows:
                closed(row, {field.attname for field in model._meta.concrete_fields})
        legacy_head = snapshot['tables']['journal_head'][0]
        ensure(legacy_head['generation'] == 9 and legacy_head['writer_epoch'] == 2
            and legacy_head['mode'] == 'ACTIVE' and legacy_head['plan_id'] is not None,
            'LG_EXPORT_HEAD')
        legacy_refs = sum(len(row['payload']['policies']) for row in snapshot['tables']['journal_operation'])
        ensure(type(snapshot['historicalReferences']) is int and legacy_refs == snapshot['historicalReferences']
            and 0 <= legacy_refs < 4095, 'LG_EXPORT_HISTORICAL_REFERENCES')
        operator = arg['operator']
        closed(operator, {'runtimeId', 'exclusion', 'configFingerprint', 'deploymentEvidenceSha256'})
        uid(operator['runtimeId']); B._hex(operator['configFingerprint']); B._hex(operator['deploymentEvidenceSha256'])
        B._exclusion(operator['exclusion'], operator['runtimeId'])
        ensure(settings.TRUST_RUNTIME_ID == operator['runtimeId'] and settings.TRUST_WRITE_PROFILE == 'disabled'
            and connection.vendor == 'postgresql' and connection.settings_dict['NAME'] == 'test_estakada_trust'
            and connection.settings_dict['USER'] == 'trust_migrator'
            and os.environ.get('TRUST_TEST_EXECUTION') == '1', 'LG_UNIT_SCOPE_METADATA')
        ensure(P.source_fingerprint() == SOURCE and len(P.source_files()) == 30, 'LG_SOURCE')
        B._hex(arg['credentialConfigSha256'])
        ensure(B._configuration_sha() == arg['credentialConfigSha256'], 'LG_CONFIG')
        ensure(auth.identity() == legacy_head['incarnation'], 'LG_IDENTITY_CONFIG')
        P.runtime_resource_facts()
        report['resources']['before'] = resources()
        report.update({'exportSha256': arg['exportSha256'], 'snapshotSha256': exported['snapshotSha256'],
            'legacyHistoricalReferences': legacy_refs, 'legacyCurrentRoutes': 3})
        with connection.cursor() as cursor:
            cursor.execute('''SELECT current_database(),current_user,session_user,d.oid,
                pg_get_userbyid(d.datdba),shobj_description(d.oid,'pg_database')
                FROM pg_database d WHERE d.datname=current_database()''')
            ensure(cursor.fetchone() == ('test_estakada_trust', 'trust_migrator', 'trust_migrator',
                52766, 'postgres', marker), 'LG_UNIT_ACTUAL_IDENTITY')
            cursor.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')
            ensure(cursor.fetchone() == (True,), 'LG_UNIT_TLS')
            cursor.execute('SELECT count(*) FROM pg_stat_activity WHERE datid=52766 AND pid<>pg_backend_pid()')
            ensure(cursor.fetchone() == (0,), 'LG_UNIT_OTHER_SESSIONS')
            cursor.execute("SET statement_timeout='5s'")
            cursor.execute("SET lock_timeout='1s'")
        ensure(P.schema_fingerprint() == SCHEMA, 'LG_SCHEMA')

        def raw_state():
            hasher = hashlib.sha256(b'LG15-ALL-ROWS-v1\x00')
            result_counts = {}
            for table in sorted([*by_table, 'django_migrations']):
                V._frame(hasher, {'table': table})
                pk = by_table[table]._meta.pk.column if table in by_table else 'id'
                # Both identifiers come exclusively from the closed model registry.
                with connection.cursor() as cursor:
                    cursor.execute('SELECT row_to_json(t) FROM "' + table + '" t ORDER BY "' + pk + '"')
                    count = 0
                    for (row,) in cursor:
                        # Django raw cursors may leave json text undecoded.
                        if type(row) is str:
                            row = json.loads(row)
                        V._frame(hasher, row); count += 1
                V._frame(hasher, {'count': count}); result_counts[table] = count
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_get_serial_sequence('django_migrations','id')")
                ensure(cursor.fetchone() == ('trust.django_migrations_id_seq',), 'LG_MIGRATIONS_SEQUENCE_NAME')
                cursor.execute('SELECT last_value,is_called FROM trust.django_migrations_id_seq')
                sequence = cursor.fetchone()
            return {'rowsSha256': hasher.hexdigest(), 'counts': result_counts,
                'migrationSequence': {'lastValue': sequence[0], 'isCalled': sequence[1]}}

        def reconnect_unit():
            connection.close(); connection.ensure_connection()
            with connection.cursor() as cursor:
                cursor.execute('''SELECT current_database(),current_user,session_user,d.oid,
                    shobj_description(d.oid,'pg_database') FROM pg_database d
                    WHERE d.datname=current_database()''')
                ensure(cursor.fetchone() == ('test_estakada_trust','trust_migrator','trust_migrator',
                    52766,marker), 'LG_FINAL_ACTUAL_IDENTITY')
                cursor.execute("SET statement_timeout='5s'")
                cursor.execute("SET lock_timeout='1s'")

        before_raw = raw_state()
        report['unitBefore'] = before_raw
        ensure(all(before_raw['counts'][table] == 0 for table in by_table)
            and before_raw['counts']['django_migrations'] == 3, 'LG_UNIT_NOT_EMPTY')
        config = auth.configuration()
        recovery = [item for item in config.values() if item['role'] == 'recovery']
        ensure(len(recovery) == 1, 'LG_RECOVERY_CONFIGURATION')
        recovery = recovery[0]
        namespace = uuid.UUID(operator['runtimeId'])
        def synthetic(label):
            return str(uuid.uuid5(namespace, 'LG15:' + label))
        def sign(payload):
            return {'payload': payload, 'signature': hmac.new(bytes.fromhex(recovery['secret']),
                canonical(payload), hashlib.sha256).hexdigest()}
        def counts():
            with connection.cursor() as cursor:
                cursor.execute("SELECT COALESCE(sum(jsonb_array_length(payload->'policies')),0) FROM journal_operation")
                refs = int(cursor.fetchone()[0])
            return {'operations': Operation.objects.count(), 'historicalReferences': refs,
                'routes': RoutePolicy.objects.count(), 'tombstones': RequestTombstone.objects.count(),
                'recoveryReceipts': RecoveryReceipt.objects.count(), 'policies': AdmissionPolicy.objects.count()}
        def state():
            head = Head.objects.select_for_update().get(pk=1)
            return {'head': V.persistent_values(head), 'stateDigestVersion': 2,
                'stateDigest': V.state_digest(head), 'counts': counts()}
        protected_head = ('id', 'incarnation', 'plan_id', 'permitted_operations', 'permitted_recovery_actions')
        def legacy_values():
            values = {}
            for model in models:
                table = model._meta.db_table
                ids = [row[model._meta.pk.attname] for row in snapshot['tables'][table]]
                values[table] = [V.persistent_values(row) for row in
                    model.objects.filter(pk__in=ids).order_by(model._meta.pk.attname)]
            values['journal_head'] = [{key: values['journal_head'][0][key] for key in protected_head}]
            return values
        def immutable(expected):
            ensure(legacy_values() == expected, 'LG_LEGACY_CHANGED')

        with tempfile.TemporaryDirectory(prefix='trust-lg15-') as temporary:
            permit = Path(temporary, 'permit.json')
            # No real permit/config file is edited. All database changes are nested here.
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_advisory_xact_lock(374001)')
                ensure(raw_state() == before_raw, 'LG_UNIT_CHANGED_BEFORE_IMPORT')
                for model in models:
                    model.objects.bulk_create([model(**row) for row in snapshot['tables'][model._meta.db_table]])
                with connection.cursor() as cursor:
                    cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                imported = state()
                ensure(imported['stateDigest'] == MAIN_V2 and imported['head'] == legacy_head,
                    'LG_IMPORTED_STATE_MISMATCH')
                for model in models:
                    actual = [V.persistent_values(row) for row in model.objects.order_by(model._meta.pk.attname)]
                    ensure(actual == snapshot['tables'][model._meta.db_table], 'LG_IMPORTED_ROW_MISMATCH')
                original = legacy_values()
                report['legacyImmutableSha256'] = digest(original)
                active_writers = []
                for item in config.values():
                    if item['role'] != 'writer':
                        continue
                    actor = auth.authenticate('Bearer ' + item['id'] + ':' + item['secret'], 'writer')
                    credential = Credential.objects.filter(pk=actor['id'], active=True,
                        writer_epoch=legacy_head['writer_epoch'], principal=actor['principal'],
                        role='writer', verifier=actor['verifier']).first()
                    if credential:
                        active_writers.append(actor)
                ensure(len(active_writers) == 1, 'LG_CURRENT_WRITER_BINDING')
                writer = active_writers[0]
                source_rows = P.source_files()
                policy = {'policyId': synthetic('policy'), 'epoch': '1', 'incarnation': auth.identity(),
                    'dbName': 'test_estakada_trust', 'protocolVersion': 1, 'sourceFiles': source_rows,
                    'sourceFingerprint': SOURCE, 'schemaFingerprint': SCHEMA,
                    'evidence': {kind: digest({'scope': 'UNFINISHED_UNIT_EVIDENCE_ONLY', 'kind': kind})
                        for kind in ('unit', 'calibration', 'review')}, 'caps': copy.deepcopy(B.CAPS)}
                intent = sign({'schemaVersion': 2, 'scope': B.ACTIVATION_SCOPE,
                    'actionId': synthetic('admit'), 'credentialId': recovery['id'], 'policy': policy,
                    'previousPolicy': None, 'legacySeal': B.legacy_seal(Head.objects.get(pk=1)),
                    'expected': {key: imported[key] for key in ('head', 'stateDigestVersion', 'stateDigest')},
                    'credentialConfigSha256': arg['credentialConfigSha256'], 'evidence': policy['evidence'],
                    'configFingerprint': operator['configFingerprint']})
                with B.unit_calibration():
                    admitted = B.activate(intent, {})
                immutable(original)
                lease = {'policyDigest': digest(policy), 'runtimeId': operator['runtimeId'],
                    'credentialConfigSha256': arg['credentialConfigSha256'],
                    'deployment': {**copy.deepcopy(P.DEPLOYMENT), 'configFingerprint': operator['configFingerprint'],
                        'evidence': operator['deploymentEvidenceSha256']}, 'exclusion': operator['exclusion'],
                    'recoveryActions': [], 'reconciliation': None}
                envelope = sign({'schemaVersion': 2, 'scope': B.SCOPE, 'policy': policy, 'lease': lease})
                permit.write_bytes(canonical(envelope)); os.chmod(permit, 0o600)
                report['admission'] = {'intentSha256': digest(intent), 'envelopeSha256': digest(envelope),
                    'policyDigest': digest(policy), 'receiptSha256': digest(admitted),
                    'legacySeal': B.legacy_seal(Head.objects.get(pk=1))}

                def body(label, *, request_count=0, route_count=0, head=None):
                    head = head or Head.objects.get(pk=1)
                    op = synthetic(label)
                    return {'operationId': op, 'incarnation': auth.identity(),
                        'expectedGeneration': str(head.generation), 'writerEpoch': str(head.writer_epoch),
                        'kind': 'request_tombstone' if request_count else 'route_restriction',
                        'objectId': synthetic(label + ':object'), 'basis': digest({'op': op}),
                        'requestIds': [synthetic(label + ':request:' + str(index)) for index in range(request_count)],
                        'policies': [{'target': '/LG15/Ремонт/' + op + '/' + str(index) + '?Case=X',
                            'objectId': synthetic(label + ':route:' + str(index)), 'policy': 'DELETED',
                            'redirectTarget': None} for index in range(route_count)]}
                def mutate(value, phase='prepare'):
                    result = S.mutate(writer, value, phase)
                    ensure(result['ok'] is True and result['workflowComplete'] is False, 'LG_BAD_RECEIPT')
                    return result
                def refusal(value):
                    before = state(); raw = raw_state()
                    try:
                        mutate(value)
                    except Fault as exc:
                        ensure(exc.code == 'COUNT_CAP_REACHED', 'LG_WRONG_REFUSAL')
                    else:
                        raise ProbeFailure('LG_EXPECTED_REFUSAL_MISSING')
                    ensure(state() == before and raw_state() == raw, 'LG_REFUSAL_NOT_ATOMIC')
                    return before
                def replay_finish(prepared, accepted):
                    before = state()
                    prepared_op = Operation.objects.get(pk=prepared['operationId'])
                    completion_charge = prepared_op.reserve_bytes
                    replay = mutate(prepared)
                    ensure(replay['replay'] is True and replay['phaseReceipt'] == accepted['phaseReceipt']
                        and state() == before, 'LG_PREPARE_REPLAY')
                    head = Head.objects.get(pk=1)
                    unknown = {'operationId': prepared['operationId'], 'incarnation': auth.identity(),
                        'expectedGeneration': str(head.generation), 'writerEpoch': str(head.writer_epoch),
                        'outcome': 'unknown', 'mainIncarnation': None, 'mainReceipt': None, 'policies': []}
                    first = mutate(unknown, 'report'); unchanged = state()
                    ensure(first['stage'] == 'MAIN_RESULT_UNKNOWN'
                        and unchanged['head']['generation'] == before['head']['generation'] + 1
                        and unchanged['head']['logical_bytes'] == before['head']['logical_bytes']
                        and unchanged['head']['reserved_bytes'] == before['head']['reserved_bytes']
                        and unchanged['counts'] == before['counts'], 'LG_UNKNOWN_STAGE')
                    replay = mutate(unknown, 'report')
                    ensure(replay['replay'] is True and replay['phaseReceipt'] == first['phaseReceipt']
                        and state() == unchanged, 'LG_UNKNOWN_REPLAY')
                    head = Head.objects.get(pk=1)
                    terminal = {**unknown, 'expectedGeneration': str(head.generation), 'outcome': 'committed',
                        'mainIncarnation': synthetic(prepared['operationId'] + ':main'),
                        'mainReceipt': digest({'unitFixtureOperation': prepared['operationId']}),
                        'policies': prepared['policies']}
                    finished = mutate(terminal, 'report'); final = state()
                    ensure(finished['stage'] == 'FINAL_RESTRICTION'
                        and final['head']['reserved_bytes'] == before['head']['reserved_bytes']
                            - completion_charge
                        and final['head']['logical_bytes'] == before['head']['logical_bytes'] + completion_charge
                        and final['head']['generation'] == unchanged['head']['generation'] + 1
                        and final['counts'] == before['counts']
                        and Operation.objects.get(pk=prepared['operationId']).reserve_bytes == 0,
                        'LG_FINISH_RESERVE')
                    replay = mutate(terminal, 'report')
                    ensure(replay['replay'] is True and replay['phaseReceipt'] == finished['phaseReceipt']
                        and state() == final, 'LG_TERMINAL_REPLAY')
                    immutable(original)
                    return final
                def bulk_operations():
                    head = Head.objects.select_for_update().get(pk=1)
                    operations = []; tombs = []
                    for index in range(995):
                        value = body('bulk-operation:' + str(index), request_count=1, head=head)
                        validate(value, 'prepare')
                        ensure(len(canonical(value)) <= MAX_BODY, 'LG_BULK_DTO_SIZE')
                        fingerprint = S.semantic(value, writer)
                        size = len(canonical(value)) + 4096
                        reserve = len(canonical(value['policies'])) + 8192
                        S.advance(head, value, fingerprint)
                        operations.append(Operation(id=value['operationId'], credential_id=writer['id'],
                            principal=writer['principal'], writer_epoch=head.writer_epoch,
                            kind=value['kind'], object_id=value['objectId'], prepare_fingerprint=fingerprint,
                            payload=value, stage='PENDING_DENY', terminal_fingerprint=None,
                            phases={'prepare': {'fingerprint': fingerprint, 'receipt': {
                                'generation': str(head.generation), 'fingerprint': fingerprint, 'stage': 'PENDING_DENY'}}},
                            logical_bytes=size, reserve_bytes=reserve))
                        tombs.append(RequestTombstone(request_id=value['requestIds'][0],
                            tombstone_id=synthetic('bulk-tomb:' + str(index)),
                            operation_id=value['operationId'], generation=head.generation))
                        head.logical_bytes += size; head.reserved_bytes += reserve
                    Operation.objects.bulk_create(operations, batch_size=64)
                    RequestTombstone.objects.bulk_create(tombs, batch_size=64)
                    head.save()
                    with connection.cursor() as cursor:
                        cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                    B._counts(head)
                    return {'kind': '995-bulk-valid-pending-fixtures-not-service-transitions',
                        'operations': len(operations), 'tombstones': len(tombs),
                        'logicalCharge': sum(row.logical_bytes for row in operations),
                        'reservedCharge': sum(row.reserve_bytes for row in operations)}

                with override_settings(TRUST_WRITE_PROFILE='local-bounded-writer',
                        TRUST_WRITE_PERMIT_FILE=str(permit)):
                    baseline = state(); baseline_raw = raw_state()
                    for branch in ('operations', 'historicalReferences', 'tombstones'):
                        group = {'id': 'LG15-' + branch, 'status': 'FAIL', 'fixedCaps': copy.deepcopy(B.CAPS)}
                        report['groups'].append(group)
                        with transaction.atomic():
                            if branch == 'operations':
                                group['fill'] = bulk_operations()
                                ensure(counts()['operations'] == 999, 'LG_OPERATION_FIXTURE_COUNT')
                                last = body('operations:last', request_count=1)
                                following = body('operations:refused', request_count=1)
                            elif branch == 'historicalReferences':
                                remaining = 4095 - legacy_refs; fill_count = 0
                                while remaining:
                                    amount = min(256, remaining)
                                    mutate(body('references:fill:' + str(fill_count), route_count=amount))
                                    remaining -= amount; fill_count += 1
                                group['fill'] = {'kind': 'real-service-prepares', 'operations': fill_count}
                                ensure(counts()['historicalReferences'] == 4095, 'LG_REFERENCE_FIXTURE_COUNT')
                                last = body('references:last', route_count=1)
                                following = body('references:refused', route_count=1)
                            else:
                                remaining = 1023 - 1; fill_count = 0
                                while remaining:
                                    amount = min(256, remaining)
                                    mutate(body('tombs:fill:' + str(fill_count), request_count=amount))
                                    remaining -= amount; fill_count += 1
                                group['fill'] = {'kind': 'real-service-prepares', 'operations': fill_count}
                                ensure(counts()['tombstones'] == 1023, 'LG_TOMB_FIXTURE_COUNT')
                                last = body('tombs:last', request_count=1)
                                following = body('tombs:refused', request_count=1)
                            group['beforeLast'] = counts()
                            accepted = mutate(last)
                            at_limit = counts()
                            ensure(at_limit[branch] == B.CAPS[{'operations': 'maxOperations',
                                'historicalReferences': 'maxHistoricalReferences', 'tombstones': 'maxTombstones'}[branch]],
                                'LG_LAST_NOT_AT_LIMIT')
                            # Refresh CAS; the expected refusal must be the real count ceiling.
                            following['expectedGeneration'] = str(Head.objects.get(pk=1).generation)
                            refusal_state = refusal(following)
                            final = replay_finish(last, accepted)
                            immutable(original)
                            group.update({'status': 'PASS', 'atLimit': at_limit,
                                'refusal': 'COUNT_CAP_REACHED', 'refusalAtomicStateDigest': refusal_state['stateDigest'],
                                'completionStateDigest': final['stateDigest'], 'legacyUnchanged': True,
                                'prepareUnknownTerminalReplay': True})
                            transaction.set_rollback(True)
                        ensure(state() == baseline and raw_state() == baseline_raw, 'LG_BRANCH_ROLLBACK_FAILED')
                        group['branchRollbackVerified'] = True
                    immutable(original)
                transaction.set_rollback(True)
            reconnect_unit()
            after_raw = raw_state()
            report['unitAfter'] = after_raw
            ensure(after_raw == before_raw, 'LG_OUTER_ROLLBACK_FAILED')
            report['outerRollbackVerified'] = True
        ensure(P.source_fingerprint() == SOURCE and B._configuration_sha() == arg['credentialConfigSha256'],
            'LG_POST_SOURCE_OR_CONFIG_DRIFT')
        report['status'] = 'PASS'
    except Exception as exc:
        code = str(exc) if isinstance(exc, ProbeFailure) else getattr(exc, 'code', 'LG_PROBE_FAILED')
        report.update({'errorClass': type(exc).__name__,
            'errorCode': code if re.fullmatch('[A-Z0-9_]{1,80}', str(code)) else 'LG_PROBE_FAILED'})
    finally:
        signal.alarm(0)
        if before_raw is not None and raw_state is not None:
            try:
                reconnect_unit()
                after_raw = raw_state()
                report['unitAfter'] = after_raw
                report['outerRollbackVerified'] = after_raw == before_raw
                if not report['outerRollbackVerified']:
                    report['status'] = 'FAIL'; report['cleanupErrors'].append('LG_FINAL_RAW_MISMATCH')
            except Exception as exc:
                report['status'] = 'FAIL'; report['cleanupErrors'].append(type(exc).__name__)
        try:
            report['resources']['after'] = resources()
        except Exception as exc:
            report['status'] = 'FAIL'; report['cleanupErrors'].append(type(exc).__name__)
        if connection is not None:
            connection.close()
        report['elapsedSeconds'] = round(time.monotonic() - started, 6)
    print(json.dumps(report, sort_keys=True, separators=(',', ':'), ensure_ascii=False))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
