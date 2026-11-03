"""Two finite continuations of the retained UNIT corpus; no reset or activation.

GLOBAL INPUT is supplied by the guarded host launcher. A and B each run once,
with their own actual operator lease and a complete expected audit checkpoint.
Original FAIL evidence and all database rows remain intact on every outcome.
"""
import copy
import hashlib
import json
import os
import random
import re
import signal
import string
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch

DEADLINE_SECONDS = 600
AUDIT_KEYS = {'status', 'database', 'oid', 'scope', 'head', 'counts', 'historicalReferences',
    'stages', 'stateDigestVersion', 'stateDigest', 'schemaFingerprint', 'policyId',
    'policyDigest', 'policySourceFingerprint', 'actualSourceFingerprint',
    'sourceMatchesPolicy', 'credentialConfigSha256', 'policy', 'dataMutation', 'headLock'}
INFORMATIONAL_AUDIT_KEYS = {'scope', 'dataMutation', 'headLock'}


class ContinuationFailure(Exception):
    pass


def ensure(condition, code):
    if not condition:
        raise ContinuationFailure(code)


def cgroup():
    root = Path('/sys/fs/cgroup')
    def number(name):
        raw = (root / name).read_text(encoding='ascii').strip()
        return int(raw) if raw.isdecimal() else raw
    def pairs(name):
        return {key: int(value) for key, value in
            (line.split() for line in (root / name).read_text(encoding='ascii').splitlines())}
    return {'memoryPeak': number('memory.peak'), 'memoryCurrent': number('memory.current'),
        'memoryMax': number('memory.max'), 'memoryEvents': pairs('memory.events'),
        'pidsCurrent': number('pids.current'), 'pidsMax': number('pids.max'),
        'pidsPeak': number('pids.peak') if (root / 'pids.peak').exists() else 'NOT_MEASURED',
        'cpu': pairs('cpu.stat')}


def main():
    started = time.monotonic()
    report = {'status': 'FAIL', 'scope': 'retained-unit-continuation-not-main-activation',
        'deadlineSeconds': DEADLINE_SECONDS, 'retained': True, 'cleanupPerformed': False,
        'htmlAdmission': False, 'workflowComplete': False, 'production': False,
        'groups': [], 'tlsSnapshot': 'NOT_RUN', 'mainNativePreSendEvidence': 'NOT_RUN'}
    scope_checked = False
    latencies = []
    def expire(*_):
        raise ContinuationFailure('CAPACITY_CONTINUATION_DEADLINE')
    signal.signal(signal.SIGALRM, expire)
    signal.alarm(DEADLINE_SECONDS)
    try:
        import django
        django.setup()
        from django.conf import settings
        from django.db import connection, transaction
        from django.db.models import Count
        from django.test import override_settings
        from journal import auth, bounded as B, profile as P, services as S, state_v2 as V
        from journal.models import AdmissionPolicy, Credential, Head, Operation, RecoveryReceipt, RequestTombstone, RoutePolicy
        from journal.protocol import Fault, MAX_BODY, canonical, closed, digest, uid, validate

        inputs = globals().get('INPUT')
        closed(inputs, {'phase', 'corpusRuntimeId', 'operator', 'envelope', 'expected'})
        phase = inputs['phase']; ensure(phase in ('A', 'B'), 'CAPACITY_CONTINUATION_PHASE')
        report['phase'] = phase
        uid(inputs['corpusRuntimeId']); namespace = uuid.UUID(inputs['corpusRuntimeId'])
        expected = inputs['expected']; closed(expected, AUDIT_KEYS)
        ensure(expected['status'] == 'PASS' and expected['dataMutation'] is False
            and ((expected['scope'] == 'repeatable-read-readonly-state-v2-formula-not-head-lock-proof'
                    and expected['headLock'] is False)
                or (expected['scope'] == 'head-locked-state-v2-checkpoint' and expected['headLock'] is True)),
            'CAPACITY_EXPECTED_AUDIT_SHAPE')
        ensure(connection.vendor == 'postgresql'
            and connection.settings_dict['NAME'] == 'test_estakada_trust'
            and os.environ.get('TRUST_TEST_EXECUTION') == '1', 'CAPACITY_CONTINUATION_SCOPE')
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(),current_user,session_user,oid FROM pg_database WHERE datname=current_database()')
            ensure(cursor.fetchone() == ('test_estakada_trust', 'trust_migrator', 'trust_migrator', 32563),
                'CAPACITY_CONTINUATION_ACTUAL_IDENTITY')
        scope_checked = True
        operator = inputs['operator']; envelope = inputs['envelope']
        closed(operator, {'runtimeId', 'exclusion', 'configFingerprint', 'deploymentEvidenceSha256'})
        uid(operator['runtimeId']); B._hex(operator['configFingerprint']); B._hex(operator['deploymentEvidenceSha256'])
        ensure(settings.TRUST_RUNTIME_ID == operator['runtimeId']
            and operator['runtimeId'] != inputs['corpusRuntimeId'], 'CAPACITY_CONTINUATION_RUNTIME')
        B._exclusion(operator['exclusion'], operator['runtimeId']); P.runtime_resource_facts()
        expected_lease = {'policyDigest': expected['policyDigest'], 'runtimeId': operator['runtimeId'],
            'credentialConfigSha256': expected['credentialConfigSha256'],
            'deployment': {**copy.deepcopy(P.DEPLOYMENT), 'configFingerprint': operator['configFingerprint'],
                'evidence': operator['deploymentEvidenceSha256']},
            'exclusion': operator['exclusion'], 'recoveryActions': [], 'reconciliation': None}
        closed(envelope, {'payload', 'signature'})
        ensure(envelope['payload'] == {'schemaVersion': 2, 'scope': B.SCOPE,
            'policy': expected['policy'], 'lease': expected_lease}, 'CAPACITY_CONTINUATION_ENVELOPE_BINDING')
        ensure(len(canonical(envelope)) <= B.MAX_ENVELOPE, 'CAPACITY_CONTINUATION_ENVELOPE_SIZE')
        configuration = auth.configuration()
        writers = sorted((item for item in configuration.values() if item['role'] == 'writer'), key=lambda item: item['id'])
        readers = [item for item in configuration.values() if item['role'] == 'reader']
        ensure(writers and readers, 'CAPACITY_CONTINUATION_CREDENTIAL_CONFIGURATION')
        writer = auth.authenticate('Bearer ' + writers[-1]['id'] + ':' + writers[-1]['secret'], 'writer')
        reader = auth.authenticate('Bearer ' + readers[0]['id'] + ':' + readers[0]['secret'], 'reader')
        identity = auth.identity()
        report.update(corpusRuntimeId=inputs['corpusRuntimeId'],
            operatorCanonicalSha256=digest(operator), envelopeSha256=digest(envelope),
            expectedCheckpointSha256=digest(expected), sourceFingerprint=P.source_fingerprint())
        def sid(label):
            return str(uuid.uuid5(namespace, label))
        def elapsed_check():
            ensure(time.monotonic() - started < DEADLINE_SECONDS, 'CAPACITY_CONTINUATION_DEADLINE')
        def audit():
            elapsed_check()
            with transaction.atomic():
                head = Head.objects.select_for_update().get(pk=1)
                current = B.latest_policy()
                ensure(current is not None and current.epoch == 1
                    and AdmissionPolicy.objects.count() == 1, 'CAPACITY_CONTINUATION_POLICY_COUNT')
                with connection.cursor() as cursor:
                    cursor.execute('SELECT current_database(),oid FROM pg_database WHERE datname=current_database()')
                    database = cursor.fetchone()
                    ensure(database == ('test_estakada_trust', 32563), 'CAPACITY_CONTINUATION_DATABASE_CHANGED')
                    cursor.execute("SELECT COALESCE(sum(jsonb_array_length(payload->'policies')),0) FROM journal_operation")
                    references = int(cursor.fetchone()[0])
                stages = {row['stage']: row['count'] for row in
                    Operation.objects.values('stage').annotate(count=Count('id'))}
                actual_source = P.source_fingerprint()
                return {'status': 'PASS', 'database': database[0], 'oid': database[1],
                    'scope': 'head-locked-state-v2-checkpoint', 'head': V.persistent_values(head),
                    'counts': {model.__name__: model.objects.count() for model, _ in V.TABLES},
                    'historicalReferences': references, 'stages': stages,
                    'stateDigestVersion': V.VERSION, 'stateDigest': V.state_digest(head),
                    'schemaFingerprint': P.schema_fingerprint(), 'policyId': str(current.pk),
                    'policyDigest': current.policy_digest,
                    'policySourceFingerprint': current.policy['sourceFingerprint'],
                    'actualSourceFingerprint': actual_source,
                    'sourceMatchesPolicy': actual_source == current.policy['sourceFingerprint'],
                    'credentialConfigSha256': B._configuration_sha(), 'policy': current.policy,
                    'dataMutation': False, 'headLock': True}
        def authority(value):
            return {key: item for key, item in value.items() if key not in INFORMATIONAL_AUDIT_KEYS}
        def physical():
            result = S.physical_facts()
            tables = list(P.TABLES)
            with connection.cursor() as cursor:
                cursor.execute('''SELECT c.relname,pg_relation_size(c.oid),pg_indexes_size(c.oid),
                    CASE WHEN c.reltoastrelid=0 THEN 0 ELSE pg_total_relation_size(c.reltoastrelid) END
                    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='trust' AND c.relname=ANY(%s) ORDER BY c.relname''', [tables])
                rows = cursor.fetchall()
                ensure(len(rows) == 7 and {row[0] for row in rows} == set(tables)
                    and all(type(value) is int and value >= 0 for row in rows for value in row[1:]),
                    'CAPACITY_CONTINUATION_PHYSICAL_TABLES')
                result['relationParts'] = [{'table': row[0], 'heapBytes': row[1],
                    'indexBytes': row[2], 'toastBytes': row[3]} for row in rows]
                cursor.execute('SELECT temp_files,temp_bytes FROM pg_stat_database WHERE datname=current_database()')
                temp = cursor.fetchone(); result['tempFiles'] = int(temp[0]); result['tempBytes'] = int(temp[1])
                cursor.execute('SELECT wal_records,wal_fpi,wal_bytes FROM pg_stat_wal')
                wal = cursor.fetchone(); result['clusterWalCounters'] = {'records': int(wal[0]),
                    'fullPageImages': int(wal[1]), 'bytes': int(wal[2])}
            return result

        # The original corpus is reconstructed, never regenerated in the DB.
        generator = random.Random(38020261102)
        alphabet = string.ascii_letters + string.digits + '-_'
        plan = {}; route_ids = []; tomb_ids = []
        def planned(kind, index, policies, request_ids):
            op_id = sid('capacity-operation:' + str(index) + ':' + kind)
            return op_id, {'operationId': op_id, 'incarnation': identity, 'writerEpoch': '1',
                'kind': kind, 'objectId': str(uuid.uuid5(uuid.UUID(op_id), 'object')),
                'basis': hashlib.sha256((op_id + ':basis').encode('ascii')).hexdigest(),
                'policies': policies, 'requestIds': request_ids}
        for index in range(16):
            policies = []
            for key in range(256):
                prefix = '/Capacity/Ремонт/' + str(index) + '/' + str(key) + '?Case=Y&Ref='
                exact = prefix + ''.join(generator.choices(alphabet, k=2048-len(prefix.encode('utf-8'))))
                restriction = ('HIDDEN', 'DELETED', 'REDIRECT')[key % 3]
                policies.append({'target': exact, 'objectId': sid('capacity-route:' + str(index) + ':' + str(key)),
                    'policy': restriction, 'redirectTarget': '/destination/Ремонт?Case=X&i=' + str(index) + '&k=' + str(key)
                        if restriction == 'REDIRECT' else None})
            op_id, body = planned('route_restriction', index, policies, [])
            plan[op_id] = body; route_ids.append(op_id)
        for index in range(984):
            request_ids = [sid('capacity-request:' + str(index) + ':' + str(item))
                for item in range(41 if index == 983 else 1)]
            op_id, body = planned('request_tombstone', 17+index, [], request_ids)
            plan[op_id] = body; tomb_ids.append(op_id)
        phase_data = {}
        def report_body(op_id, outcome, generation):
            return {'operationId': op_id, 'incarnation': identity, 'expectedGeneration': str(generation),
                'writerEpoch': '1', 'outcome': outcome,
                'mainIncarnation': str(uuid.uuid5(uuid.UUID(op_id), 'main-incarnation')) if outcome == 'committed' else None,
                'mainReceipt': hashlib.sha256(op_id.encode('ascii')).hexdigest() if outcome == 'committed' else None,
                'policies': plan[op_id]['policies'] if outcome == 'committed' else []}
        def validate_plan():
            elapsed_check()
            phase_data.clear(); ledger = []; logical = 0; reserved = 0; present = set(); finals = set()
            with transaction.atomic():
                head = Head.objects.select_for_update().get(pk=1)
                ensure(str(head.incarnation) == identity and head.writer_epoch == 1 and head.mode == 'ACTIVE'
                    and str(head.plan_id) == sid('capacity-legacy-plan')
                    and head.permitted_operations == [] and head.permitted_recovery_actions == [],
                    'CAPACITY_CONTINUATION_HEAD_PLAN')
                ensure(RecoveryReceipt.objects.count() == 0, 'CAPACITY_CONTINUATION_RECOVERY_ROWS')
                credentials = {row.pk: row for row in Credential.objects.all()}
                ensure(set(credentials) == set(configuration), 'CAPACITY_CONTINUATION_CREDENTIAL_IDS')
                for ident, item in configuration.items():
                    row = credentials[ident]
                    ensure(row.principal == item['principal'] and row.role == item['role']
                        and row.verifier == hashlib.sha256(item['secret'].encode('ascii')).hexdigest()
                        and row.writer_epoch == 1 and row.active is True, 'CAPACITY_CONTINUATION_CREDENTIAL_BINDING')
                policy = B.latest_policy()
                ensure(policy is not None and str(policy.pk) == sid('capacity-policy')
                    and str(policy.action_id) == sid('capacity-admission-action')
                    and policy.epoch == 1 and policy.policy == expected['policy'],
                    'CAPACITY_CONTINUATION_POLICY_IDENTITY')
                ensure(policy.receipt['head']['generation'] == '1'
                    and policy.receipt['head']['writerEpoch'] == '1', 'CAPACITY_CONTINUATION_POLICY_RECEIPT')
                ledger.append((1, policy.intent_digest)); logical += policy.logical_bytes
                for row in Operation.objects.order_by('id').iterator(chunk_size=1):
                    elapsed_check()
                    op_id = str(row.pk); ensure(op_id in plan and op_id not in present, 'CAPACITY_CONTINUATION_FOREIGN_OPERATION')
                    present.add(op_id); body = row.payload; validate(body, 'prepare')
                    ensure({key: value for key, value in body.items() if key != 'expectedGeneration'} == plan[op_id]
                        and row.credential_id == writer['id'] and row.principal == writer['principal']
                        and row.writer_epoch == 1 and row.kind == body['kind'] and str(row.object_id) == body['objectId'],
                        'CAPACITY_CONTINUATION_OPERATION_PAYLOAD')
                    ensure(type(row.phases) is dict and 'prepare' in row.phases
                        and set(row.phases) <= {'prepare', 'unknown', 'committed'}, 'CAPACITY_CONTINUATION_PHASE_SET')
                    prepared = row.phases['prepare']; prepare_gen = int(prepared['receipt']['generation'])
                    fingerprint = S.semantic(body, writer)
                    ensure(body['expectedGeneration'] == str(prepare_gen-1)
                        and row.prepare_fingerprint == fingerprint and prepared == {'fingerprint': fingerprint,
                            'receipt': {'generation': str(prepare_gen), 'fingerprint': fingerprint, 'stage': 'PENDING_DENY'}},
                        'CAPACITY_CONTINUATION_PREPARE_RECEIPT')
                    ledger.append((prepare_gen, fingerprint))
                    if 'unknown' in row.phases:
                        ensure(op_id == route_ids[0], 'CAPACITY_CONTINUATION_UNKNOWN_OPERATION')
                        saved = row.phases['unknown']; generation = int(saved['receipt']['generation'])
                        fp = S.semantic(report_body(op_id, 'unknown', generation-1), writer)
                        ensure(saved == {'fingerprint': fp, 'receipt': {'generation': str(generation),
                            'fingerprint': fp, 'stage': 'MAIN_RESULT_UNKNOWN'}} and generation > prepare_gen,
                            'CAPACITY_CONTINUATION_UNKNOWN_RECEIPT')
                        ledger.append((generation, fp))
                    terminal = 'committed' in row.phases
                    if terminal:
                        saved = row.phases['committed']; generation = int(saved['receipt']['generation'])
                        fp = S.semantic(report_body(op_id, 'committed', generation-1), writer)
                        ensure(saved == {'fingerprint': fp, 'receipt': {'generation': str(generation),
                            'fingerprint': fp, 'stage': 'FINAL_RESTRICTION'}}
                            and generation > prepare_gen and (not 'unknown' in row.phases
                                or generation > int(row.phases['unknown']['receipt']['generation']))
                            and row.terminal_fingerprint == fp and row.stage == 'FINAL_RESTRICTION',
                            'CAPACITY_CONTINUATION_TERMINAL_RECEIPT')
                        ledger.append((generation, fp)); finals.add(op_id)
                    else:
                        ensure(row.terminal_fingerprint is None and row.stage == (
                            'MAIN_RESULT_UNKNOWN' if 'unknown' in row.phases else 'PENDING_DENY'),
                            'CAPACITY_CONTINUATION_UNFINISHED_STAGE')
                    original_reserve = len(canonical(body['policies'])) + 8192
                    ensure(row.logical_bytes == len(canonical(body))+4096+(original_reserve if terminal else 0)
                        and row.reserve_bytes == (0 if terminal else original_reserve),
                        'CAPACITY_CONTINUATION_OPERATION_ACCOUNTING')
                    logical += row.logical_bytes; reserved += row.reserve_bytes
                    phase_data[op_id] = {'prepareGeneration': prepare_gen, 'stage': row.stage,
                        'terminalGeneration': int(row.phases['committed']['receipt']['generation']) if terminal else None,
                        'phases': copy.deepcopy(row.phases), 'payload': body if op_id in route_ids else None}
                ensure(set(route_ids) <= present, 'CAPACITY_CONTINUATION_MISSING_ROUTE_OPERATION')
                tomb_count = len(present - set(route_ids))
                ensure(present - set(route_ids) == set(tomb_ids[:tomb_count]), 'CAPACITY_CONTINUATION_TOMBSTONE_PREFIX')
                ensure(logical == head.logical_bytes and reserved == head.reserved_bytes
                    and logical+reserved <= B.CAPS['logicalBytes'] and reserved <= B.CAPS['completionBytes'],
                    'CAPACITY_CONTINUATION_TOTAL_ACCOUNTING')
                rolling = digest({'incarnation': identity, 'generation': '0'})
                for number, (generation, fp) in enumerate(sorted(ledger), 1):
                    ensure(generation == number, 'CAPACITY_CONTINUATION_GENERATION_CHAIN')
                    rolling = digest({'previous': rolling, 'generation': str(generation), 'phase': fp})
                ensure(len(ledger) == head.generation and rolling == head.digest, 'CAPACITY_CONTINUATION_HEAD_CHAIN')
                expected_routes = {}
                for op_id in route_ids:
                    metadata = phase_data[op_id]
                    for item in plan[op_id]['policies']:
                        key = hashlib.sha256(item['target'].encode('utf-8')).hexdigest()
                        expected_routes[key] = (op_id, item, metadata)
                seen = 0
                for row in RoutePolicy.objects.order_by('key').iterator(chunk_size=32):
                    ensure(row.pk in expected_routes, 'CAPACITY_CONTINUATION_FOREIGN_ROUTE')
                    op_id, item, metadata = expected_routes[row.pk]
                    final = metadata['stage'] == 'FINAL_RESTRICTION'
                    ensure(row.operation_id == uuid.UUID(op_id) and row.target == item['target']
                        and str(row.object_id) == item['objectId']
                        and row.generation == (metadata['terminalGeneration'] if final else metadata['prepareGeneration'])
                        and row.policy == (item['policy'] if final else 'PENDING_DENY')
                        and row.redirect_target == (item['redirectTarget'] if final else None),
                        'CAPACITY_CONTINUATION_ROUTE_BINDING')
                    seen += 1
                ensure(seen == 4096, 'CAPACITY_CONTINUATION_ROUTE_COUNT')
                expected_requests = {request: op_id for op_id in tomb_ids[:tomb_count]
                    for request in plan[op_id]['requestIds']}
                seen = 0; tombstone_ids = set()
                for row in RequestTombstone.objects.order_by('request_id').iterator(chunk_size=32):
                    request = str(row.pk)
                    ensure(request in expected_requests and str(row.operation_id) == expected_requests[request]
                        and row.generation == phase_data[expected_requests[request]]['prepareGeneration']
                        and row.tombstone_id not in tombstone_ids, 'CAPACITY_CONTINUATION_TOMBSTONE_BINDING')
                    tombstone_ids.add(row.tombstone_id); seen += 1
                ensure(seen == len(expected_requests), 'CAPACITY_CONTINUATION_TOMBSTONE_COUNT')
                return {'present': present, 'finals': finals, 'tombOperations': tomb_count,
                    'ledgerDigest': digest(sorted(ledger))}

        def mutate(body, request_phase='prepare'):
            elapsed_check(); tick = time.monotonic()
            try:
                result = S.mutate(writer, body, request_phase)
            finally:
                latencies.append(round((time.monotonic()-tick)*1000, 3))
            ensure(result['workflowComplete'] is False, 'CAPACITY_CONTINUATION_FALSE_WORKFLOW')
            return result
        def make_prepare(op_id):
            head = Head.objects.get(pk=1)
            return {**plan[op_id], 'expectedGeneration': str(head.generation)}
        def finish(op_id):
            head = Head.objects.get(pk=1)
            result = mutate(report_body(op_id, 'committed', head.generation), 'report')
            ensure(result['stage'] == 'FINAL_RESTRICTION' and result['replay'] is False,
                'CAPACITY_CONTINUATION_FINISH_RESULT')
        def refusal(body, code):
            before = audit()
            try:
                mutate(body)
            except Fault as fault:
                ensure(fault.code == code, 'CAPACITY_CONTINUATION_WRONG_REFUSAL')
            else:
                raise ContinuationFailure('CAPACITY_CONTINUATION_EXPECTED_REFUSAL_MISSING')
            after = audit(); ensure(after == before, 'CAPACITY_CONTINUATION_REFUSAL_MUTATED')
            return before
        def negative(body, code):
            queries = []
            def observe(execute, sql, params, many, context):
                queries.append(1); return execute(sql, params, many, context)
            with connection.execute_wrapper(observe), patch.object(connection, 'ensure_connection', wraps=connection.ensure_connection) as connect:
                try:
                    S.mutate(writer, body, 'prepare')
                except Fault as fault:
                    ensure(fault.code == code, 'CAPACITY_CONTINUATION_DTO_ERROR')
                else:
                    raise ContinuationFailure('CAPACITY_CONTINUATION_DTO_ACCEPTED')
                ensure(not queries and connect.call_count == 0, 'CAPACITY_CONTINUATION_DTO_SQL')

        with tempfile.TemporaryDirectory(prefix='trust-capacity-continuation-') as temporary:
            permit = Path(temporary, 'write-profile.json'); permit.write_bytes(canonical(envelope)); os.chmod(permit, 0o600)
            with override_settings(TRUST_WRITE_PROFILE='local-bounded-writer', TRUST_WRITE_PERMIT_FILE=str(permit),
                    TRUST_RUNTIME_ID=operator['runtimeId']):
                # This validates the actual HMAC/source/runtime/config/resources before SQL.
                B.read_envelope()
                before = audit()
                ensure(canonical(authority(before)) == canonical(authority(expected)),
                    'CAPACITY_CONTINUATION_CHECKPOINT_MISMATCH')
                ensure(before['sourceMatchesPolicy'] is True and before['policyId'] == sid('capacity-policy')
                    and before['head']['writer_epoch'] == 1, 'CAPACITY_CONTINUATION_CHECKPOINT_POLICY')
                plan_state = validate_plan()
                with transaction.atomic():
                    head = S.locked(writer, identity, '1')
                    probe = Operation.objects.get(pk=route_ids[0]).payload
                    checked = B.check(writer, probe, 'prepare', S.semantic(probe, writer))
                    B.check_locked(checked, writer, probe, 'prepare', S.semantic(probe, writer), head)
                ensure(audit() == before, 'CAPACITY_CONTINUATION_CHANGED_DURING_VALIDATION')
                report['beforeAudit'] = before; report['beforePhysical'] = physical()
                report['initialLedgerDigest'] = plan_state['ledgerDigest']
                if phase == 'A':
                    ensure(before['counts']['Operation'] == 964 and before['counts']['RoutePolicy'] == 4096
                        and before['counts']['RequestTombstone'] == 948
                        and before['stages'] == {'PENDING_DENY': 964}
                        and plan_state['tombOperations'] == 948 and not plan_state['finals'],
                        'CAPACITY_PHASE_A_INITIAL_STATE')
                    first = copy.deepcopy(phase_data[route_ids[0]]['payload'])
                    bad = copy.deepcopy(first); bad['policies'].append({'target': '/257th',
                        'objectId': sid('capacity-257th-object'), 'policy': 'DELETED', 'redirectTarget': None})
                    negative(bad, 'INPUT_REJECTED')
                    bad = copy.deepcopy(first); bad['policies'][0]['target'] = '/'+'x'*2048
                    negative(bad, 'INPUT_REJECTED')
                    bad = copy.deepcopy(first); bad['unknownField'] = True; negative(bad, 'INPUT_REJECTED')
                    bad = copy.deepcopy(first)
                    for index, item in enumerate(bad['policies']):
                        prefix = '/quoted/'+str(index)+'/'
                        item.update(target=prefix+'"'*(2048-len(prefix)), policy='REDIRECT',
                            redirectTarget='/redirect/'+'"'*(2048-len('/redirect/')))
                    validate(bad, 'prepare'); ensure(len(canonical(bad)) > MAX_BODY, 'CAPACITY_PHASE_A_DTO_SIZE')
                    negative(bad, 'BODY_TOO_LARGE')
                    report['groups'].append({'id': 'RP15-009', 'status': 'PASS', 'negativeSqlConnect': 0,
                        'positiveKeys': 256, 'positiveTargetUtf8Bytes': 2048, 'retainedPositivePayloadVerified': True})
                    rejected_id, rejected_body = planned('route_restriction', 16,
                        [{'target': '/4097th-reference', 'objectId': sid('capacity-4097th-object'),
                            'policy': 'DELETED', 'redirectTarget': None}], [])
                    ensure(rejected_id not in plan_state['present'], 'CAPACITY_PHASE_A_REFUSAL_ID_EXISTS')
                    refusal({**rejected_body, 'expectedGeneration': str(Head.objects.get().generation)}, 'COUNT_CAP_REACHED')
                    next_id = tomb_ids[948]; next_body = make_prepare(next_id); head = Head.objects.get()
                    next_reserve = len(canonical(next_body['policies']))+8192
                    ensure(head.reserved_bytes+next_reserve > B.CAPS['completionBytes']
                        and head.logical_bytes+head.reserved_bytes+len(canonical(next_body))+4096+next_reserve
                            <= B.CAPS['logicalBytes'], 'CAPACITY_PHASE_A_RESERVE_NOT_ISOLATED')
                    reserve_audit = refusal(next_body, 'BUDGET_EXHAUSTED')
                    report['reserveRefusal'] = {'stateDigest': reserve_audit['stateDigest'],
                        'head': reserve_audit['head'], 'nextReserveBytes': next_reserve,
                        'stateUnchanged': True}
                    mutate(report_body(route_ids[0], 'unknown', Head.objects.get().generation), 'report')
                    finals = set()
                    for op_id in route_ids:
                        finish(op_id); finals.add(op_id)
                    for index in range(948, 984):
                        op_id = tomb_ids[index]; body = make_prepare(op_id)
                        if index == 983:
                            over = copy.deepcopy(body); over['operationId'] = sid('capacity-over-limit-tombstone-operation')
                            over['requestIds'].append(sid('capacity-1025th-request'))
                            boundary = refusal(over, 'COUNT_CAP_REACHED')
                            ensure(boundary['counts']['Operation'] == 999
                                and boundary['counts']['RequestTombstone'] == 983,
                                'CAPACITY_PHASE_A_INDEPENDENT_TOMBSTONE_BOUNDARY')
                        mutate(body)
                    for op_id in tomb_ids:
                        if len(finals) == 500: break
                        finish(op_id); finals.add(op_id)
                    ensure(len(finals) == 500, 'CAPACITY_PHASE_A_FINAL_LIMIT')
                    final_audit = audit()
                    ensure(final_audit['counts']['Operation'] == 1000
                        and final_audit['counts']['RoutePolicy'] == 4096
                        and final_audit['counts']['RequestTombstone'] == 1024
                        and final_audit['historicalReferences'] == 4096
                        and final_audit['stages'] == {'FINAL_RESTRICTION': 500, 'PENDING_DENY': 500},
                        'CAPACITY_PHASE_A_CHECKPOINT_COUNTS')
                    report['groups'].extend([
                        {'id': 'RP15-008', 'status': 'PASS', 'scope': '1000-4096-1024-with-independent-ref-and-tombstone-refusals'},
                        {'id': 'RP15-010', 'status': 'PARTIAL', 'actualReserve16MiBRefusal': 'PASS',
                            'unknownAnd500Completions': 'PASS', 'logical64MiBBoundary': 'NOT_RUN'}])
                else:
                    ensure(before['scope'] == 'head-locked-state-v2-checkpoint'
                        and expected['scope'] == 'head-locked-state-v2-checkpoint'
                        and before['counts']['Operation'] == 1000
                        and before['counts']['RoutePolicy'] == 4096
                        and before['counts']['RequestTombstone'] == 1024
                        and before['stages'] == {'FINAL_RESTRICTION': 500, 'PENDING_DENY': 500}
                        and plan_state['finals'] == set(route_ids+tomb_ids[:484]),
                        'CAPACITY_PHASE_B_INITIAL_CHECKPOINT')
                    for op_id in tomb_ids[484:]:
                        finish(op_id)
                    head = Head.objects.get()
                    op_id, over = planned('request_tombstone', 1001, [], [sid('capacity-final-over-limit-request')])
                    ensure(op_id not in plan_state['present'], 'CAPACITY_PHASE_B_REFUSAL_ID_EXISTS')
                    refusal({**over, 'expectedGeneration': str(head.generation)}, 'COUNT_CAP_REACHED')
                    replay_id = route_ids[0]; stored = Operation.objects.get(pk=replay_id)
                    before_replay = audit()
                    ensure(mutate(stored.payload)['replay'] is True, 'CAPACITY_PHASE_B_PREPARE_REPLAY')
                    for outcome in ('unknown', 'committed'):
                        ensure(outcome in stored.phases, 'CAPACITY_PHASE_B_REPLAY_PHASE_MISSING')
                        generation = int(stored.phases[outcome]['receipt']['generation'])
                        ensure(mutate(report_body(replay_id, outcome, generation-1), 'report')['replay'] is True,
                            'CAPACITY_PHASE_B_PHASE_REPLAY')
                    ensure(audit() == before_replay, 'CAPACITY_PHASE_B_REPLAY_MUTATED')
                    manifest = S.snapshot_manifest(reader); hasher = hashlib.sha256(b'[')
                    total = 0; pages = 0; cursor = 0; tick = time.monotonic()
                    while True:
                        elapsed_check()
                        page = S.snapshot(reader, manifest['head']['generation'], cursor)
                        ensure(page['head'] == manifest['head'] and page['pageDigest'] == digest(page['items']),
                            'CAPACITY_PHASE_B_SQL_PAGE')
                        for item in page['items']:
                            if total: hasher.update(b',')
                            hasher.update(canonical(item)); total += 1
                        pages += 1
                        if page['nextCursor'] is None: break
                        cursor = page['nextCursor']
                    hasher.update(b']')
                    ensure(total == 5120 and pages == 52 and hasher.hexdigest() == manifest['snapshotDigest'],
                        'CAPACITY_PHASE_B_SQL_SNAPSHOT')
                    report['snapshot'] = {'manifest': manifest, 'sqlPages': pages, 'sqlItems': total,
                        'sqlReadSeconds': round(time.monotonic()-tick, 3), 'fixedTlsWorker': 'NOT_RUN'}
                    final_audit = audit()
                    ensure(final_audit['counts']['Operation'] == 1000
                        and final_audit['counts']['RoutePolicy'] == 4096
                        and final_audit['counts']['RequestTombstone'] == 1024
                        and final_audit['historicalReferences'] == 4096
                        and final_audit['stages'] == {'FINAL_RESTRICTION': 1000}
                        and final_audit['head']['reserved_bytes'] == 0, 'CAPACITY_PHASE_B_FINAL_COUNTS')
                    report['groups'].extend([
                        {'id': 'RP15-008', 'status': 'PASS', 'fullCountsAfterFinishAndReplay': True},
                        {'id': 'RP15-010', 'status': 'PARTIAL', 'remaining500CompletionsAndReplays': 'PASS',
                            'logical64MiBBoundary': 'NOT_RUN'},
                        {'id': 'RP15-011', 'status': 'PARTIAL', 'stateV2AndSql52Pages': 'PASS', 'fixedTlsWorker': 'NOT_RUN'}])
                # Final independent traversal of every binding/phase/accounting.
                final_plan = validate_plan()
                ensure(len(final_plan['finals']) == (500 if phase == 'A' else 1000),
                    'CAPACITY_CONTINUATION_FINAL_PLAN')
                ensure(audit() == final_audit, 'CAPACITY_CONTINUATION_FINAL_AUDIT_CHANGED')
                report['finalAudit'] = final_audit
                report['finalCheckpointSha256'] = digest(final_audit)
                report['finalLedgerDigest'] = final_plan['ledgerDigest']
        report['afterPhysical'] = physical(); usage = cgroup()
        ensure(usage['memoryMax'] == 268435456 and usage['memoryPeak'] <= usage['memoryMax']
            and usage['memoryEvents'].get('oom', 0) == 0
            and usage['memoryEvents'].get('oom_kill', 0) == 0, 'CAPACITY_CONTINUATION_PROCESS_RESOURCE')
        ensure(report['afterPhysical']['databaseBytes'] < 2*1024**3, 'CAPACITY_CONTINUATION_DATABASE_BUDGET')
        report.update(status='PASS', helperCgroup=usage, latency={'mutationCalls': len(latencies),
            'maxMutationMs': max(latencies) if latencies else 0}, newPolicyRows=0,
            changedWriterEpoch=False, hostWholeBudgetAndDbPeak='NOT_RUN')
    except BaseException as error:
        code = error.args[0] if isinstance(error, ContinuationFailure) and error.args else getattr(error, 'code', 'CAPACITY_CONTINUATION_EXCEPTION')
        report.update(status='FAIL', errorCode=code if type(code) is str and re.fullmatch('[A-Z0-9_]{1,80}', code)
            else 'CAPACITY_CONTINUATION_EXCEPTION', errorClass=type(error).__name__, scopeValidated=scope_checked)
        try:
            report['helperCgroup'] = cgroup()
        except Exception:
            report['helperCgroupObservation'] = 'UNAVAILABLE'
    finally:
        signal.alarm(0)
    report['elapsedSeconds'] = round(time.monotonic()-started, 3)
    print(json.dumps(report, sort_keys=True, separators=(',', ':')))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
