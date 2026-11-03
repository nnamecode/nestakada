"""One retained, bounded UNIT corpus; never flush/reset or activate MAIN.

The host saves a signed attempted receipt before starting this helper. A second
run refuses its nonempty database. Reports expose digests, counts and measurements
only; complete accepted synthetic payloads/phases remain in the retained DB.
"""
import copy
import hashlib
import hmac
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
MODELS = ('Head', 'Credential', 'Operation', 'RoutePolicy', 'RequestTombstone',
          'RecoveryReceipt', 'AdmissionPolicy')


class ProbeFailure(Exception):
    pass


def ensure(condition, code):
    if not condition:
        raise ProbeFailure(code)


def cgroup():
    root = Path('/sys/fs/cgroup')
    def number(name):
        value = (root / name).read_text(encoding='ascii').strip()
        return int(value) if value.isdecimal() else value
    def pairs(name):
        return dict((key, int(value)) for key, value in
            (line.split() for line in (root / name).read_text(encoding='ascii').splitlines()))
    return {'memoryPeak': number('memory.peak'), 'memoryCurrent': number('memory.current'),
        'memoryMax': number('memory.max'), 'memoryEvents': pairs('memory.events'),
        'pidsCurrent': number('pids.current'), 'pidsMax': number('pids.max'),
        'pidsPeak': number('pids.peak') if (root / 'pids.peak').exists() else 'NOT_MEASURED',
        'cpu': pairs('cpu.stat')}


def main():
    started = time.monotonic()
    report = {'status': 'FAIL', 'scope': 'retained-isolated-unit-capacity-not-main-admission',
        'deadlineSeconds': DEADLINE_SECONDS, 'groups': [], 'retained': True,
        'cleanupPerformed': False, 'htmlAdmission': False, 'workflowComplete': False,
        'tlsSnapshot': 'NOT_RUN', 'production': False}
    scope_checked = False
    transcript = hashlib.sha256(b'ESTAKADA-TRUST-UNIT-CAPACITY-INPUTS\x00v1\x00')
    transcript_entries = 0
    def deadline(*_):
        raise ProbeFailure('CAPACITY_DEADLINE')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(DEADLINE_SECONDS)
    try:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trust_service.settings')
        import django
        django.setup()
        from django.apps import apps
        from django.conf import settings
        from django.db import connection, transaction
        from django.test import override_settings
        from journal import auth, bounded as B, profile as P, services as S, state_v2 as V
        from journal.models import AdmissionPolicy, Credential, Head, Operation, RecoveryReceipt, RequestTombstone, RoutePolicy
        from journal.protocol import Fault, MAX_BODY, canonical, digest, parse, target, uid, validate

        ensure(connection.vendor == 'postgresql'
            and connection.settings_dict['NAME'] == 'test_estakada_trust'
            and os.environ.get('TRUST_TEST_EXECUTION') == '1', 'CAPACITY_SCOPE_METADATA')
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(), current_user, session_user')
            ensure(cursor.fetchone() == ('test_estakada_trust', 'trust_migrator', 'trust_migrator'),
                'CAPACITY_SCOPE_ACTUAL')
        scope_checked = True
        models = [apps.get_model('journal', name) for name in MODELS]
        ensure(not any(model.objects.exists() for model in models), 'CAPACITY_DATABASE_NOT_EMPTY')
        operator = globals().get('OPERATOR')
        from journal.protocol import closed
        closed(operator, {'runtimeId', 'exclusion', 'configFingerprint', 'deploymentEvidenceSha256'})
        uid(operator['runtimeId']); B._hex(operator['configFingerprint']); B._hex(operator['deploymentEvidenceSha256'])
        ensure(settings.TRUST_RUNTIME_ID == operator['runtimeId'], 'CAPACITY_RUNTIME_BINDING')
        B._exclusion(operator['exclusion'], operator['runtimeId'])
        ensure(operator['exclusion']['newContainerId'] != operator['exclusion']['previousContainerId'],
            'CAPACITY_OPERATOR_EXCLUSION')
        P.runtime_resource_facts()
        namespace = uuid.UUID(operator['runtimeId'])
        def synthetic_id(label):
            return str(uuid.uuid5(namespace, label))
        def preserve(name, value):
            # UNIT fixtures are reconstructed from retained policy/prior_state
            # and complete accepted operation rows, not issued as MAIN permits.
            raw = canonical(value)
            report.setdefault('unitFixtureDigests', {})[name] = hashlib.sha256(raw).hexdigest()
            return hashlib.sha256(raw).hexdigest()
        def log_intent(phase, body):
            nonlocal transcript_entries
            raw = canonical({'phase': phase, 'body': body})
            transcript.update(len(raw).to_bytes(8, 'big')); transcript.update(raw)
            transcript_entries += 1
        def elapsed_check():
            ensure(time.monotonic() - started < DEADLINE_SECONDS, 'CAPACITY_DEADLINE')
        def counts():
            with connection.cursor() as cursor:
                cursor.execute("SELECT COALESCE(sum(jsonb_array_length(payload->'policies')),0) FROM journal_operation")
                references = int(cursor.fetchone()[0])
            return {'operations': Operation.objects.count(), 'routes': RoutePolicy.objects.count(),
                'historicalReferences': references, 'tombstones': RequestTombstone.objects.count(),
                'recoveryReceipts': RecoveryReceipt.objects.count(), 'credentials': Credential.objects.count(),
                'policies': AdmissionPolicy.objects.count()}
        def state():
            with transaction.atomic():
                head = Head.objects.select_for_update().get(pk=1)
                return {'head': V.persistent_values(head), 'stateDigestVersion': V.VERSION,
                    'stateDigest': V.state_digest(head), 'counts': counts()}
        def physical():
            result = S.physical_facts()
            with connection.cursor() as cursor:
                cursor.execute('''SELECT c.relname,pg_relation_size(c.oid),pg_indexes_size(c.oid),
                    CASE WHEN c.reltoastrelid=0 THEN 0 ELSE pg_total_relation_size(c.reltoastrelid) END
                    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='trust' AND c.relname=ANY(%s) ORDER BY c.relname''',
                    [[model._meta.db_table for model in models]])
                result['relationParts'] = [{'table': row[0], 'heapBytes': int(row[1]),
                    'indexBytes': int(row[2]), 'toastBytes': int(row[3])} for row in cursor.fetchall()]
                ensure({row['table'] for row in result['relationParts']}
                    == {model._meta.db_table for model in models}
                    and len(result['relationParts']) == len(models), 'CAPACITY_PHYSICAL_TABLE_SET')
                ensure(all(type(row[field]) is int and row[field] >= 0
                    for row in result['relationParts']
                    for field in ('heapBytes', 'indexBytes', 'toastBytes')),
                    'CAPACITY_PHYSICAL_RELATION_BYTES')
                cursor.execute('SELECT temp_files,temp_bytes FROM pg_stat_database WHERE datname=current_database()')
                temp = cursor.fetchone(); result['tempFiles'] = int(temp[0]); result['tempBytes'] = int(temp[1])
                cursor.execute('SELECT wal_records,wal_fpi,wal_bytes FROM pg_stat_wal')
                wal = cursor.fetchone(); result['clusterWalCounters'] = {
                    'records': int(wal[0]), 'fullPageImages': int(wal[1]), 'bytes': int(wal[2])}
            return result
        initial_physical = physical()
        identity = auth.identity()
        config = auth.configuration()
        recovery = [item for item in config.values() if item['role'] == 'recovery']
        writers = sorted((item for item in config.values() if item['role'] == 'writer'), key=lambda item: item['id'])
        readers = [item for item in config.values() if item['role'] == 'reader']
        ensure(len(recovery) == 1 and writers and readers, 'CAPACITY_CREDENTIAL_CONFIGURATION')
        recovery = recovery[0]
        writer = auth.authenticate('Bearer ' + writers[-1]['id'] + ':' + writers[-1]['secret'], 'writer')
        reader = auth.authenticate('Bearer ' + readers[0]['id'] + ':' + readers[0]['secret'], 'reader')
        def sign(payload):
            return {'payload': payload, 'signature': hmac.new(bytes.fromhex(recovery['secret']),
                canonical(payload), hashlib.sha256).hexdigest()}
        S.bootstrap(identity)
        with transaction.atomic():
            head = Head.objects.select_for_update().get(pk=1)
            head.plan_id = synthetic_id('capacity-legacy-plan')
            head.permitted_operations = []; head.permitted_recovery_actions = []
            head.save()
        source = P.source_files()
        policy = {'policyId': synthetic_id('capacity-policy'), 'epoch': '1', 'incarnation': identity,
            'dbName': 'test_estakada_trust', 'protocolVersion': 1, 'sourceFiles': source,
            'sourceFingerprint': digest(source), 'schemaFingerprint': P.schema_fingerprint(),
            'evidence': {kind: hashlib.sha256(('UNIT_CALIBRATION_FIXTURE_NOT_COMPLETED_REPORT:' + kind).encode('ascii')).hexdigest()
                for kind in ('unit', 'calibration', 'review')}, 'caps': B.CAPS.copy()}
        before = state()
        intent = sign({'schemaVersion': 2, 'scope': B.ACTIVATION_SCOPE, 'actionId': synthetic_id('capacity-admission-action'),
            'credentialId': recovery['id'], 'policy': policy, 'previousPolicy': None,
            'legacySeal': B.legacy_seal(Head.objects.get(pk=1)),
            'expected': {key: before[key] for key in ('head', 'stateDigestVersion', 'stateDigest')},
            'credentialConfigSha256': B._configuration_sha(), 'evidence': policy['evidence'],
            'configFingerprint': operator['configFingerprint']})
        preserve('unit-activation-intent.json', intent)
        with B.unit_calibration():
            activated = B.activate(intent, {})
        preserve('unit-activation-receipt.json', activated)
        lease = {'policyDigest': digest(policy), 'runtimeId': operator['runtimeId'],
            'credentialConfigSha256': B._configuration_sha(),
            'deployment': {**copy.deepcopy(P.DEPLOYMENT), 'configFingerprint': operator['configFingerprint'],
                'evidence': operator['deploymentEvidenceSha256']},
            'exclusion': operator['exclusion'], 'recoveryActions': [], 'reconciliation': None}
        envelope = sign({'schemaVersion': 2, 'scope': B.SCOPE, 'policy': policy, 'lease': lease})
        preserve('unit-write-envelope.json', envelope)
        latencies = []; finish_latencies = []; pending = []; completed = []; maximum_reserved = 0
        reserve_refusal = None
        generator = random.Random(38020261102)
        alphabet = string.ascii_letters + string.digits + '-_'
        prepare_index = 0
        def prepare(kind, policies=None, request_ids=None):
            nonlocal prepare_index
            head = Head.objects.get(pk=1)
            operation_id = synthetic_id('capacity-operation:' + str(prepare_index) + ':' + kind)
            prepare_index += 1
            return {'operationId': operation_id, 'incarnation': identity,
                'expectedGeneration': str(head.generation), 'writerEpoch': str(head.writer_epoch),
                'kind': kind, 'objectId': str(uuid.uuid5(uuid.UUID(operation_id), 'object')),
                'basis': hashlib.sha256((operation_id + ':basis').encode('ascii')).hexdigest(),
                'policies': policies or [], 'requestIds': request_ids or []}
        def mutate(body, phase='prepare'):
            elapsed_check(); log_intent(phase, body)
            tick = time.monotonic(); result = S.mutate(writer, body, phase)
            ensure(not result['workflowComplete'], 'CAPACITY_FALSE_WORKFLOW')
            elapsed = round((time.monotonic() - tick) * 1000, 3)
            (latencies if phase == 'prepare' else finish_latencies).append(elapsed)
            return result
        def finish(body):
            head = Head.objects.get(pk=1)
            result = mutate({'operationId': body['operationId'], 'incarnation': identity,
                'expectedGeneration': str(head.generation), 'writerEpoch': str(head.writer_epoch),
                'outcome': 'committed', 'mainIncarnation': str(uuid.uuid5(uuid.UUID(body['operationId']), 'main-incarnation')),
                'mainReceipt': hashlib.sha256(body['operationId'].encode('ascii')).hexdigest(),
                'policies': body['policies']}, 'report')
            ensure(result['stage'] == 'FINAL_RESTRICTION', 'CAPACITY_FINAL_STAGE')
            completed.append(body)
        def refused(body, code):
            before_refusal = state(); log_intent('expected-refusal', body)
            try:
                S.mutate(writer, body, 'prepare')
            except Fault as fault:
                ensure(fault.code == code, 'CAPACITY_WRONG_REFUSAL')
            else:
                raise ProbeFailure('CAPACITY_EXPECTED_REFUSAL_MISSING')
            ensure(state() == before_refusal, 'CAPACITY_REFUSAL_MUTATED_STATE')
            return before_refusal
        def negative_early(body, code):
            seen = []
            def observe(execute, sql, params, many, context):
                seen.append(1); return execute(sql, params, many, context)
            with connection.execute_wrapper(observe), patch.object(connection, 'ensure_connection', wraps=connection.ensure_connection) as connect:
                try:
                    S.mutate(writer, body, 'prepare')
                except Fault as fault:
                    ensure(fault.code == code, 'CAPACITY_BAD_DTO_ERROR')
                else:
                    raise ProbeFailure('CAPACITY_BAD_DTO_ACCEPTED')
                ensure(not seen and connect.call_count == 0, 'CAPACITY_BAD_DTO_SQL')
        def policies(index):
            result = []
            for key in range(256):
                prefix = '/Capacity/Ремонт/' + str(index) + '/' + str(key) + '?Case=Y&Ref='
                exact = prefix + ''.join(generator.choices(alphabet, k=2048-len(prefix.encode('utf-8'))))
                target(exact); ensure(len(exact.encode('utf-8')) == 2048, 'CAPACITY_TARGET_BYTES')
                restriction = ('HIDDEN', 'DELETED', 'REDIRECT')[key % 3]
                result.append({'target': exact, 'objectId': synthetic_id('capacity-route:' + str(index) + ':' + str(key)), 'policy': restriction,
                    'redirectTarget': '/destination/Ремонт?Case=X&i=' + str(index) + '&k=' + str(key)
                        if restriction == 'REDIRECT' else None})
            return result
        with tempfile.TemporaryDirectory(prefix='trust-capacity-') as temporary:
            permit = Path(temporary, 'write-profile.json'); permit.write_bytes(canonical(envelope)); os.chmod(permit, 0o600)
            with override_settings(TRUST_WRITE_PROFILE='local-bounded-writer', TRUST_WRITE_PERMIT_FILE=str(permit),
                    TRUST_RUNTIME_ID=operator['runtimeId']):
                first = prepare('route_restriction', policies(0)); validate(first, 'prepare')
                ensure(len(canonical(first)) <= MAX_BODY, 'CAPACITY_LEGAL_DTO_TOO_LARGE')
                bad = copy.deepcopy(first); bad['policies'].append({'target': '/257th', 'objectId': synthetic_id('capacity-257th-object'),
                    'policy': 'DELETED', 'redirectTarget': None}); negative_early(bad, 'INPUT_REJECTED')
                bad = copy.deepcopy(first); bad['policies'][0]['target'] = '/' + 'x' * 2048
                negative_early(bad, 'INPUT_REJECTED')
                bad = copy.deepcopy(first); bad['unknownField'] = True; negative_early(bad, 'INPUT_REJECTED')
                bad = copy.deepcopy(first)
                for index, item in enumerate(bad['policies']):
                    prefix = '/quoted/' + str(index) + '/'
                    item.update(target=prefix + '"' * (2048 - len(prefix)), policy='REDIRECT',
                        redirectTarget='/redirect/' + '"' * (2048 - len('/redirect/')))
                validate(bad, 'prepare'); ensure(len(canonical(bad)) > MAX_BODY, 'CAPACITY_OVERSIZE_DTO_NOT_OVERSIZE')
                negative_early(bad, 'BODY_TOO_LARGE')
                report['groups'].append({'id': 'RP15-009', 'status': 'PASS', 'negativeSqlConnect': 0,
                    'positiveKeys': 256, 'positiveTargetUtf8Bytes': 2048, 'positiveBodyBytes': len(canonical(first))})
                for index in range(16):
                    body = first if index == 0 else prepare('route_restriction', policies(index))
                    mutate(body); pending.append(body)
                    maximum_reserved = max(maximum_reserved, Head.objects.get().reserved_bytes)
                ref_state = refused(prepare('route_restriction', [{'target': '/4097th-reference',
                    'objectId': synthetic_id('capacity-4097th-object'), 'policy': 'DELETED', 'redirectTarget': None}]), 'COUNT_CAP_REACHED')
                ensure(ref_state['counts']['operations'] == 16 and ref_state['counts']['historicalReferences'] == 4096,
                    'CAPACITY_REFERENCE_BOUNDARY')
                for index in range(984):
                    request_ids = [synthetic_id('capacity-request:' + str(index) + ':' + str(item))
                        for item in range(41 if index == 983 else 1)]
                    body = prepare('request_tombstone', request_ids=request_ids)
                    if index == 983:
                        over = copy.deepcopy(body); over['operationId'] = synthetic_id('capacity-over-limit-tombstone-operation')
                        over['requestIds'].append(synthetic_id('capacity-1025th-request'))
                        boundary = refused(over, 'COUNT_CAP_REACHED')
                        ensure(boundary['counts']['operations'] == 999 and boundary['counts']['tombstones'] == 983,
                            'CAPACITY_INDEPENDENT_TOMBSTONE_BOUNDARY')
                    head = Head.objects.get()
                    expected_reserve = len(canonical(body['policies'])) + 8192
                    before_prepare = state() if reserve_refusal is None and (
                        head.reserved_bytes + expected_reserve > B.CAPS['completionBytes']) else None
                    try:
                        mutate(body)
                    except Fault as fault:
                        ensure(fault.code == 'BUDGET_EXHAUSTED' and reserve_refusal is None,
                            'CAPACITY_UNEXPECTED_PREPARE_REFUSAL')
                        ensure(before_prepare is not None and state() == before_prepare,
                            'CAPACITY_RESERVE_REFUSAL_MUTATED')
                        head = Head.objects.get()
                        reserve = len(canonical(body['policies'])) + 8192
                        ensure(head.reserved_bytes + reserve > B.CAPS['completionBytes']
                            and head.logical_bytes + head.reserved_bytes + len(canonical(body)) + 4096 + reserve <= B.CAPS['logicalBytes'],
                            'CAPACITY_REFUSAL_NOT_RESERVE')
                        reserve_refusal = {'head': S.head_dict(head), 'reservedBytes': head.reserved_bytes,
                            'nextReserveBytes': reserve, 'operations': Operation.objects.count()}
                        first_pending = pending[0]
                        mutate({'operationId': first_pending['operationId'], 'incarnation': identity,
                            'expectedGeneration': str(head.generation), 'writerEpoch': str(head.writer_epoch),
                            'outcome': 'unknown', 'mainIncarnation': None, 'mainReceipt': None, 'policies': []}, 'report')
                        for route in pending[:16]:
                            finish(route)
                        pending = pending[16:]
                        body['expectedGeneration'] = str(Head.objects.get().generation)
                        mutate(body)
                    pending.append(body)
                    maximum_reserved = max(maximum_reserved, Head.objects.get().reserved_bytes)
                ensure(reserve_refusal is not None, 'CAPACITY_RESERVE_BOUNDARY_NOT_REACHED')
                for body in pending:
                    finish(body)
                pending.clear()
                final_counts = counts()
                ensure(final_counts['operations'] == 1000 and final_counts['routes'] == 4096
                    and final_counts['historicalReferences'] == 4096 and final_counts['tombstones'] == 1024,
                    'CAPACITY_FINAL_COUNTS')
                refused(prepare('request_tombstone', request_ids=[synthetic_id('capacity-final-over-limit-request')]), 'COUNT_CAP_REACHED')
                replay_body = completed[0]
                before_replay = state(); replay = mutate(replay_body)
                ensure(replay['replay'] and state() == before_replay, 'CAPACITY_FULL_COUNT_REPLAY')
                saved = Operation.objects.get(pk=replay_body['operationId'])
                for outcome in ('unknown', 'committed'):
                    ensure(outcome in saved.phases, 'CAPACITY_SAVED_PHASE_MISSING')
                    phase_body = {'operationId': replay_body['operationId'], 'incarnation': identity,
                        'expectedGeneration': str(int(saved.phases[outcome]['receipt']['generation']) - 1),
                        'writerEpoch': str(saved.writer_epoch), 'outcome': outcome,
                        'mainIncarnation': str(uuid.uuid5(uuid.UUID(replay_body['operationId']), 'main-incarnation'))
                            if outcome == 'committed' else None,
                        'mainReceipt': hashlib.sha256(replay_body['operationId'].encode('ascii')).hexdigest()
                            if outcome == 'committed' else None,
                        'policies': replay_body['policies'] if outcome == 'committed' else []}
                    ensure(mutate(phase_body, 'report')['replay'] and state() == before_replay,
                        'CAPACITY_FULL_COUNT_PHASE_REPLAY')
                manifest = S.snapshot_manifest(reader)
                hasher = hashlib.sha256(b'['); cursor = 0; total = 0; pages = 0
                snapshot_started = time.monotonic()
                while True:
                    elapsed_check()
                    page = S.snapshot(reader, manifest['head']['generation'], cursor)
                    ensure(page['head'] == manifest['head'] and page['pageDigest'] == digest(page['items']),
                        'CAPACITY_SQL_SNAPSHOT_PAGE')
                    for item in page['items']:
                        if total: hasher.update(b',')
                        hasher.update(canonical(item)); total += 1
                    pages += 1
                    if page['nextCursor'] is None: break
                    cursor = page['nextCursor']
                hasher.update(b']')
                ensure(total == 5120 and pages == 52 and hasher.hexdigest() == manifest['snapshotDigest'],
                    'CAPACITY_SQL_SNAPSHOT_DIGEST')
                report.update(sourceFingerprint=policy['sourceFingerprint'], schemaFingerprint=policy['schemaFingerprint'],
                    operatorCanonicalSha256=digest(operator), before=before, final=state(),
                    snapshot={'manifest': manifest, 'sqlPages': pages, 'sqlItems': total,
                        'sqlReadSeconds': round(time.monotonic()-snapshot_started, 3),
                        'scope': 'direct-service-reads-not-TLS-worker'}, maximumReservedBytes=maximum_reserved,
                    reserveRefusal=reserve_refusal)
        final_head = Head.objects.get()
        ensure(final_head.reserved_bytes == 0 and final_head.logical_bytes <= B.CAPS['logicalBytes'],
            'CAPACITY_FINAL_BUDGET')
        after = physical(); usage = cgroup()
        ensure(usage['memoryMax'] == 268435456 and usage['memoryPeak'] <= usage['memoryMax']
            and usage['memoryEvents'].get('oom', 0) == 0 and usage['memoryEvents'].get('oom_kill', 0) == 0,
            'CAPACITY_PROCESS_RESOURCE')
        ensure(after['databaseBytes'] < 2*1024**3, 'CAPACITY_DATABASE_OBSERVED_BUDGET')
        report['groups'].extend([
            {'id': 'RP15-008', 'status': 'PASS', 'scope': 'retained-corpus-exact-1000-4096-1024-and-atomic-refusals'},
            {'id': 'RP15-010', 'status': 'PARTIAL', 'reserve16MiB': 'PASS',
                'unknownCompletionReplay': 'PASS', 'logical64MiBBoundary': 'NOT_RUN',
                'reason': 'retained-corpus-does-not-saturate-logical64MiB; reviewed-UNIT-injection-separate'},
            {'id': 'RP15-011', 'status': 'PARTIAL', 'fullStateV2AndSql52Pages': 'PASS', 'fixedTlsWorker': 'NOT_RUN'},
            {'id': 'RP15-012', 'status': 'PARTIAL', 'helperPhysicalAndCgroup': 'PASS',
                'hostWholeBudgetArchiveDbPeakAndLogs': 'NOT_RUN'}])
        report.update(status='PASS', scope='retained-unit-count-reserve-dto-fullstate-sql-snapshot-subset-only',
            beforePhysical=initial_physical, afterPhysical=after, helperCgroup=usage,
            latency={'prepareCalls': len(latencies), 'prepareMaxMs': max(latencies),
                'phaseCalls': len(finish_latencies), 'phaseMaxMs': max(finish_latencies)})
        report['reconstruction'] = {'ids': 'UUID5(operator.runtimeId,code-owned-label)',
            'mainIncarnation': 'UUID5(operationId,main-incarnation)',
            'mainReceipt': 'SHA256(operationId-ascii)', 'expectedPhaseGeneration': 'stored-phase-receipt-generation-minus-one',
            'preparedBodies': 'retained-Operation.payload', 'mainNativePreSendEvidence': 'NOT_RUN'}
    except BaseException as error:
        # Never emit exception text, SQL, credentials, URLs or operation bodies.
        code = error.args[0] if isinstance(error, ProbeFailure) and error.args else getattr(error, 'code', 'CAPACITY_EXCEPTION')
        report.update(status='FAIL', errorCode=code if type(code) is str and re.fullmatch('[A-Z0-9_]{1,80}', code) else 'CAPACITY_EXCEPTION',
            errorClass=type(error).__name__, scopeValidated=scope_checked)
        if scope_checked:
            try:
                report['failureCounts'] = counts()
                report['helperCgroup'] = cgroup()
            except Exception:
                report['failureObservation'] = 'UNAVAILABLE'
    finally:
        signal.alarm(0)
    report['elapsedSeconds'] = round(time.monotonic()-started, 3)
    report['inputTranscriptSha256'] = transcript.hexdigest()
    report['inputTranscriptEntries'] = transcript_entries
    print(json.dumps(report, separators=(',', ':')))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
