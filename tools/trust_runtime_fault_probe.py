"""RP15-013/014/015: finite native transport witnesses; never issue a lease.

Loaded through a closed stdin launcher in the existing isolated API container.
The host must persist the exact synthetic intent before invoking this helper.
No product monkeypatch, UNIT bypass, arbitrary URL or secret output is allowed.
"""
import hashlib
import http.client
import json
import os
import re
import signal
import ssl
import time
import uuid


def ensure(condition, code):
    if not condition:
        raise RuntimeError(code)


def snapshot(identifier):
    from django.db import connection, transaction
    from journal.models import Head, Operation
    from journal.protocol import digest
    from journal.state_v2 import persistent_values
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            cursor.execute('SELECT current_database(),current_user,session_user')
            ensure(cursor.fetchone() == ('estakada_trust', 'trust_runtime', 'trust_runtime'),
                   'NATIVE_SQL_IDENTITY')
        head = Head.objects.get(pk=1)
        row = Operation.objects.filter(pk=identifier).first()
        return {'head': {'generation': str(head.generation), 'digest': head.digest,
                         'writerEpoch': str(head.writer_epoch)},
                'operation': None if row is None else {
                    'id': str(row.pk), 'stage': row.stage,
                    'prepareFingerprint': row.prepare_fingerprint,
                    'terminalFingerprint': row.terminal_fingerprint,
                    'phasesSha256': digest(row.phases),
                    'rowSha256': digest(persistent_values(row))}}


def execute(arg):
    from django.conf import settings
    from journal import auth
    from journal.protocol import canonical, closed, validate
    closed(arg, {'case', 'credentialId', 'body', 'intentSha256'})
    ensure(arg['case'] in ('unknown-lost-body', 'terminal-lost-body', 'partial-prepare'),
           'NATIVE_CASE_REJECTED')
    ensure(settings.TRUST_WRITE_PROFILE == 'local-bounded-writer', 'NATIVE_WRITER_DISABLED')
    ensure(os.environ.get('TRUST_TEST_EXECUTION') is None, 'NATIVE_UNIT_ENV_REJECTED')
    body = arg['body']
    ensure(type(body) is dict, 'NATIVE_BODY_REJECTED')
    phase = 'prepare' if arg['case'] == 'partial-prepare' else 'report'
    validate(body, phase)
    identifier = body['operationId']
    ensure(str(uuid.UUID(identifier)) == identifier, 'NATIVE_UUID_REJECTED')
    if phase == 'report':
        ensure(body['outcome'] == ('unknown' if arg['case'] == 'unknown-lost-body'
                                  else 'committed'), 'NATIVE_OUTCOME_REJECTED')
    raw = canonical(body)
    ensure(re.fullmatch('[0-9a-f]{64}', arg['intentSha256']) is not None
           and hashlib.sha256(raw).hexdigest() == arg['intentSha256'], 'NATIVE_INTENT_CHANGED')
    ensure(len(raw) <= 1048576, 'NATIVE_BODY_BOUND')
    credential = auth.configuration().get(arg['credentialId'])
    ensure(credential is not None and credential['role'] == 'writer', 'NATIVE_WRITER_REQUIRED')
    before = snapshot(identifier)
    ensure(before['head']['generation'] == body['expectedGeneration'], 'NATIVE_INITIAL_CAS')
    if phase == 'prepare':
        ensure(before['operation'] is None, 'NATIVE_PARTIAL_ID_ALREADY_EXISTS')
    else:
        ensure(before['operation'] is not None, 'NATIVE_PREPARE_REQUIRED')
    context = ssl.create_default_context(cafile='/run/secrets/ingress-ca')
    conn = http.client.HTTPSConnection('trust-ingress', 8443, timeout=2, context=context)
    sent = False
    partial_sent = False
    status = None
    headers = None
    response = None
    transport = 'RESPONSE_HEADERS_RECEIVED'
    try:
        conn.connect()
        conn.sock.settimeout(6)
        conn.putrequest('POST', '/v1/prepare' if phase == 'prepare' else '/v1/report-result')
        conn.putheader('Authorization', 'Bearer ' + credential['id'] + ':' + credential['secret'])
        conn.putheader('Content-Type', 'application/json')
        conn.putheader('Content-Length', str(len(raw)))
        conn.putheader('Connection', 'close')
        conn.endheaders()
        if phase == 'prepare':
            conn.send(raw[:-1])
            partial_sent = True
            transport = 'INTENTIONALLY_PARTIAL_BODY_CLOSED'
        else:
            conn.send(raw)
            sent = True
            response = conn.getresponse()
            status = response.status
            headers = {'noStore': 'no-store' in response.getheader('Cache-Control', ''),
                       'cookiePresent': response.getheader('Set-Cookie') is not None}
            # Deliberately do not read response body. This is not packet loss.
    except (OSError, ssl.SSLError, http.client.HTTPException):
        transport = 'TRANSPORT_UNAVAILABLE'
    finally:
        if response is not None:
            response.close()
        conn.close()
    after = snapshot(identifier)
    if phase == 'prepare':
        ensure(partial_sent and transport == 'INTENTIONALLY_PARTIAL_BODY_CLOSED',
               'NATIVE_PARTIAL_WITNESS_MISSING')
        # Finite observation window after closing the incomplete wire request.
        for _ in range(10):
            ensure(after == before, 'NATIVE_PARTIAL_CHANGED_STATE')
            time.sleep(0.1)
            after = snapshot(identifier)
        ensure(after == before, 'NATIVE_PARTIAL_CHANGED_STATE')
    else:
        ensure(sent and status == 200 and headers['noStore'] and not headers['cookiePresent'],
               'NATIVE_LOST_BODY_WITNESS_MISSING')
        ensure(int(after['head']['generation']) == int(before['head']['generation']) + 1,
               'NATIVE_PHASE_ADVANCE_MISMATCH')
        ensure(after['operation'] is not None
               and after['operation']['stage'] == ('MAIN_RESULT_UNKNOWN'
                   if arg['case'] == 'unknown-lost-body' else 'FINAL_RESTRICTION')
               and after['operation']['phasesSha256'] != before['operation']['phasesSha256'],
               'NATIVE_PHASE_NOT_PERSISTED')
    return {'status': 'PASS', 'scope': 'native-transport-witness-not-full-rp15-coverage',
            'case': arg['case'], 'intentSha256': arg['intentSha256'],
            'fullRequestSent': sent, 'httpStatus': status, 'transport': transport,
            'partialRequestSent': partial_sent,
            'responseBodyConsumed': False,
            'lostResponseBodyWitness': bool(sent and status == 200),
            'before': before, 'after': after, 'workflowComplete': False,
            'exactReplay': 'HOST_MUST_VERIFY_SEPARATELY', 'otherRows': 'HOST_MUST_VERIFY_SEPARATELY'}


if __name__ == '__main__':
    try:
        def expire(*_):
            raise RuntimeError('NATIVE_PROBE_DEADLINE')
        signal.signal(signal.SIGALRM, expire)
        signal.alarm(20)
        ensure(os.environ.get('DJANGO_SETTINGS_MODULE') == 'trust_service.settings'
               and os.environ.get('TRUST_DB_HOST') == 'trust-db'
               and os.environ.get('TRUST_DB_NAME') == 'estakada_trust'
               and os.environ.get('TRUST_DB_USER') == 'trust_runtime', 'NATIVE_ENV_SCOPE')
        import django
        django.setup()
        result = execute(ARG)
    except Exception as error:
        code = str(error) if type(error) is RuntimeError else getattr(error, 'code', 'NATIVE_PROBE_FAILED')
        if type(code) is not str or re.fullmatch('[A-Z][A-Z0-9_]{0,99}', code) is None:
            code = 'NATIVE_PROBE_FAILED'
        print(json.dumps({'status': 'FAIL', 'errorCode': code, 'stateNotReset': True}))
        raise SystemExit(1) from None
    print(json.dumps(result, separators=(',', ':')))
