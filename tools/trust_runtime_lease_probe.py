"""RL15 private API-side observations/closed transport; never issues a lease."""
import hashlib
import http.client
import json
import os
import re
import signal
import ssl
import time
import uuid
from pathlib import Path


class ProbeFailure(Exception):
    pass


def ensure(value, code):
    if not value:
        raise ProbeFailure(code)


def main():
    tick = time.monotonic()
    out = {'status': 'FAIL', 'scope': 'RL15-private-probe-not-lease-issuer', 'rowMutationByProbe': False}
    def expire(*_):
        raise ProbeFailure('LEASE_PROBE_DEADLINE')
    signal.signal(signal.SIGALRM, expire); signal.alarm(30)
    try:
        import django
        django.setup()
        from django.conf import settings
        from django.db import connection, transaction
        from journal import auth, bounded as B, profile as P, services as S, state_v2 as V
        from journal.models import Head, Credential, AdmissionPolicy, Operation
        from journal.protocol import Fault, canonical, closed, digest, uid, validate
        arg = globals().get('ARG')
        closed(arg, {'action', 'expected', 'request', 'admission'})
        ensure(arg['action'] in ('snapshot', 'admission', 'request'), 'LEASE_PROBE_ACTION')
        ex = arg['expected']
        closed(ex, {'database', 'oid', 'incarnation', 'sourceFingerprint', 'schemaFingerprint',
            'policyId', 'policyDigest', 'runtimeId'})
        uid(ex['runtimeId']); uid(ex['policyId']); uid(ex['incarnation'])
        ensure(ex['database'] == 'estakada_trust' and type(ex['oid']) is int
            and ex['oid'] > 0 and ex['oid'] not in (16387, 32563, 52766), 'LEASE_PROBE_DB_SCOPE')
        ensure(connection.settings_dict['NAME'] == ex['database']
            and connection.settings_dict['HOST'] == 'trust-db'
            and connection.settings_dict['USER'] == 'trust_runtime'
            and settings.TRUST_RUNTIME_ID == ex['runtimeId']
            and settings.TRUST_WRITE_PROFILE in ('disabled', 'local-bounded-writer')
            and os.environ.get('TRUST_TEST_EXECUTION') != '1' and not B._unit_authority.get(), 'LEASE_PROBE_METADATA')
        ensure(P.source_fingerprint() == ex['sourceFingerprint'] and len(P.source_files()) == 30
            and auth.identity() == ex['incarnation'], 'LEASE_PROBE_SOURCE')
        resources = P.runtime_resource_facts()
        with connection.cursor() as cursor:
            cursor.execute('''SELECT current_database(),current_user,session_user,d.oid
                FROM pg_database d WHERE d.datname=current_database()''')
            ensure(cursor.fetchone() == (ex['database'], 'trust_runtime', 'trust_runtime', ex['oid']),
                'LEASE_PROBE_ACTUAL_DB')
            cursor.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')
            ensure(cursor.fetchone() == (True,), 'LEASE_PROBE_DB_TLS')
            cursor.execute("SET statement_timeout='5s'")
            cursor.execute("SET lock_timeout='1s'")
        permit_path = Path(settings.TRUST_WRITE_PERMIT_FILE)
        file_info = permit_path.stat()
        permit_raw = permit_path.read_bytes()
        ensure(len(permit_raw) <= 65536, 'LEASE_PROBE_PERMIT_SIZE')
        out['permitFile'] = {'dev': str(file_info.st_dev), 'ino': str(file_info.st_ino),
            'bytes': len(permit_raw), 'sha256': hashlib.sha256(permit_raw).hexdigest()}
        out['runtime'] = {'runtimeId': settings.TRUST_RUNTIME_ID, 'writeProfile': settings.TRUST_WRITE_PROFILE,
            'resources': resources}

        def snapshot():
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                ensure(P.schema_fingerprint() == ex['schemaFingerprint'], 'LEASE_PROBE_SCHEMA')
                head = Head.objects.get(pk=1)
                ensure(str(head.incarnation) == ex['incarnation'] and Operation.objects.count() <= 16,
                    'LEASE_PROBE_SMALL_MAIN_SCOPE')
                full = hashlib.sha256(V.DOMAIN)
                V._frame(full, {'stateDigestVersion': 2, 'head': V.persistent_values(head)})
                counts = {}; rows = {}; bindings = []; policy = None; accounting = {}
                for model, limit in V.TABLES:
                    name = model.__name__; rows[name] = {}; count = 0
                    V._frame(full, {'table': model._meta.db_table,
                        'fields': [field.attname for field in model._meta.concrete_fields]})
                    for row in model.objects.order_by(model._meta.pk.attname).iterator(chunk_size=1):
                        count += 1; ensure(count <= limit, 'LEASE_PROBE_ROW_BOUND')
                        value = V.persistent_values(row); V._frame(full, value)
                        rows[name][str(row.pk)] = digest(value)
                        if model is Operation:
                            accounting[str(row.pk)] = {key: value[key] for key in ('logical_bytes', 'reserve_bytes')}
                        if model is Credential:
                            bindings.append({key: value[key] for key in ('id', 'role', 'active', 'writer_epoch')})
                        if model is AdmissionPolicy:
                            ensure(count == 1 and str(row.pk) == ex['policyId']
                                and row.policy_digest == ex['policyDigest'] and row.epoch == 1,
                                'LEASE_PROBE_POLICY')
                            policy = {'policyId': str(row.pk), 'policyDigest': row.policy_digest,
                                'epoch': row.epoch, 'policy': row.policy}
                    V._frame(full, {'count': count}); counts[name] = count
                ensure(policy is not None, 'LEASE_PROBE_POLICY_MISSING')
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COALESCE(sum(jsonb_array_length(payload->'policies')),0) FROM journal_operation")
                    references = int(cursor.fetchone()[0])
                return {'database': ex['database'], 'oid': ex['oid'], 'sourceFingerprint': ex['sourceFingerprint'],
                    'schemaFingerprint': ex['schemaFingerprint'], 'head': V.persistent_values(head),
                    'stateDigestVersion': 2, 'stateDigest': full.hexdigest(), 'counts': counts,
                    'rows': rows, 'credentialBindings': bindings, 'policy': policy,
                    'operationAccounting': accounting,
                    'historicalReferences': references}

        if arg['action'] == 'snapshot':
            ensure(arg['request'] is None and arg['admission'] is None, 'LEASE_PROBE_SNAPSHOT_ARGUMENT')
            out['snapshot'] = snapshot()
        elif arg['action'] == 'admission':
            ensure(arg['request'] is None and arg['admission'] in ('valid', 'invalid'), 'LEASE_PROBE_ADMISSION_ARGUMENT')
            baseline = snapshot(); cfg = auth.configuration(); writers = []
            for item in cfg.values():
                if item['role'] != 'writer':
                    continue
                actor = auth.authenticate('Bearer ' + item['id'] + ':' + item['secret'], 'writer')
                if Credential.objects.filter(pk=actor['id'], active=True, principal=actor['principal'],
                        role='writer', verifier=actor['verifier'], writer_epoch=baseline['head']['writer_epoch']).exists():
                    writers.append(actor)
            ensure(writers, 'LEASE_PROBE_ACTIVE_WRITER')
            actor = sorted(writers, key=lambda item: item['id'])[0]
            object_id = str(uuid.uuid5(uuid.UUID(ex['runtimeId']), 'lock-only-admission'))
            body = {'operationId': object_id, 'incarnation': ex['incarnation'],
                'expectedGeneration': str(baseline['head']['generation']),
                'writerEpoch': str(baseline['head']['writer_epoch']), 'kind': 'route_restriction',
                'objectId': object_id, 'basis': digest({'scope': 'LOCK_ONLY_NO_OPERATION'}),
                'policies': [{'target': '/lease-validation-only/' + object_id, 'objectId': object_id,
                    'policy': 'HIDDEN', 'redirectTarget': None}], 'requestIds': []}
            validate(body, 'prepare'); fingerprint = S.semantic(body, actor)
            if arg['admission'] == 'invalid':
                try:
                    B.check(actor, body, 'prepare', fingerprint)
                except Fault as fault:
                    ensure(fault.status == 503 and fault.code in ('WRITE_PROFILE_DISABLED', 'BOUNDED_ADMISSION_REJECTED'),
                        'LEASE_PROBE_WRONG_CLOSED_ERROR')
                    out['admission'] = {'accepted': False, 'faultStatus': fault.status, 'faultCode': fault.code,
                        'httpRequestPerformed': False, 'rowWrites': False}
                else:
                    raise ProbeFailure('LEASE_PROBE_UNEXPECTED_ADMISSION')
            else:
                permit = B.check(actor, body, 'prepare', fingerprint)
                with transaction.atomic():
                    head = S.locked(actor, ex['incarnation'], body['writerEpoch'])
                    B.check_locked(permit, actor, body, 'prepare', fingerprint, head)
                    transaction.set_rollback(True)
                ensure(permit['payload']['policy']['policyId'] == ex['policyId']
                    and permit['payload']['lease']['runtimeId'] == ex['runtimeId'], 'LEASE_PROBE_VALID_BINDING')
                out['admission'] = {'accepted': True, 'httpRequestPerformed': False,
                    'lockOnlyRolledBack': True, 'rowWrites': False}
            ensure(snapshot() == baseline, 'LEASE_PROBE_ADMISSION_CHANGED_STATE')
            out['snapshot'] = baseline
        else:
            ensure(arg['admission'] is None, 'LEASE_PROBE_REQUEST_ARGUMENT')
            req = arg['request']; closed(req, {'path', 'body', 'credentialId'})
            is_read = req['path'] == '/v1/head' or bool(re.fullmatch('/v1/operations/[0-9a-f-]{36}', req['path']))
            is_write = req['path'] in ('/v1/prepare', '/v1/report-result')
            ensure(is_read or is_write, 'LEASE_PROBE_REQUEST_PATH')
            if req['path'].startswith('/v1/operations/'):
                uid(req['path'].rsplit('/', 1)[1])
            ensure((req['body'] is None) if is_read else type(req['body']) is dict, 'LEASE_PROBE_REQUEST_BODY')
            item = auth.configuration().get(req['credentialId'])
            ensure(item is not None and item['role'] == ('reader' if is_read else 'writer'), 'LEASE_PROBE_REQUEST_ROLE')
            payload = None if is_read else canonical(req['body'])
            ensure(payload is None or len(payload) <= 1048576, 'LEASE_PROBE_HTTP_BODY_BOUND')
            context = ssl.create_default_context(cafile='/run/secrets/ingress-ca')
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            conn = http.client.HTTPSConnection('trust-ingress', 8443, timeout=6, context=context)
            response = None
            signal.alarm(6)
            try:
                headers = {'Authorization': 'Bearer ' + item['id'] + ':' + item['secret'], 'Connection': 'close'}
                if payload is not None:
                    headers['Content-Type'] = 'application/json'
                conn.request('GET' if is_read else 'POST', req['path'], body=payload, headers=headers)
                response = conn.getresponse(); data = response.read(65537)
                ensure(len(data) <= 65536, 'LEASE_PROBE_HTTP_RESPONSE_BOUND')
                cache = response.getheader('Cache-Control', '')
                cookie = response.getheader('Set-Cookie') is not None
                cache_tokens = [value.strip().lower() for value in cache.split(',')]
                ensure(cache_tokens and all(value == 'no-store' for value in cache_tokens)
                    and not cookie, 'LEASE_PROBE_HTTP_PRIVACY')
                value = json.loads(data)
                ensure(type(value) is dict, 'LEASE_PROBE_HTTP_JSON')
                out['request'] = {'statusCode': response.status, 'body': value,
                    'phaseReceipt': value.get('phaseReceipt'), 'headers': {'cacheControl': cache,
                        'setCookiePresent': cookie}, 'responseClosed': True, 'requestDeadlineSeconds': 6}
            finally:
                if response is not None:
                    response.close()
                conn.close()
                signal.alarm(max(1, int(30 - (time.monotonic() - tick))))
            out['rowMutationByProbe'] = 'HTTP_REQUEST_BODY_EXPLICITLY_OPERATOR_SUPPLIED' if is_write else False
        out['status'] = 'PASS'; out['action'] = arg['action']
        connection.close()
    except Exception as exc:
        code = str(exc) if isinstance(exc, ProbeFailure) else getattr(exc, 'code', 'LEASE_PROBE_FAILED')
        out.update({'errorClass': type(exc).__name__,
            'errorCode': code if re.fullmatch('[A-Z0-9_]{1,80}', str(code)) else 'LEASE_PROBE_FAILED'})
    finally:
        signal.alarm(0); out['elapsedSeconds'] = round(time.monotonic() - tick, 6)
    print(json.dumps(out, sort_keys=True, separators=(',', ':'), ensure_ascii=False))
    return 0 if out['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
