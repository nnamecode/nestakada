"""Real closed TLS/SQL boundary, persistent API deliberately write-disabled.

Runs only inside the approved TRUST API container. Never prints payload/tokens,
uses no website endpoint, and never claims the absent HTML gate was exercised.
"""
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import ssl
import urllib.error
import urllib.request
import uuid
import psycopg

ORIGIN = 'https://trust-ingress:8443'
assert os.environ['TRUST_DB_HOST'] == 'trust-db'
assert os.environ['TRUST_DB_NAME'] == 'estakada_trust'
assert os.environ['TRUST_DB_USER'] == 'trust_runtime'
assert os.environ['TRUST_WRITE_PROFILE'] == 'disabled'
config = json.loads(Path('/run/secrets/credentials.json').read_text())
keys = {item['role']: item for item in config['credentials']}
ca = '/run/secrets/ingress-ca'
context = ssl.create_default_context(cafile=ca)
groups = []


def ensure(condition, code):
    if not condition:
        raise RuntimeError(code)


def request(target, role=None, body=None, extra=None):
    ensure(target in ['/v1/head', '/v1/prepare', '/v1/snapshot'], 'CLOSED_TARGET')
    headers = {'Content-Type': 'application/json'}
    if role:
        key = keys[role]
        headers['Authorization'] = 'Bearer ' + key['id'] + ':' + key['secret']
    if extra:
        headers.update(extra)
    data = json.dumps(body).encode() if body is not None else None
    try:
        result = urllib.request.urlopen(urllib.request.Request(ORIGIN + target, data=data,
            headers=headers), context=context, timeout=6)
    except urllib.error.HTTPError as error:
        result = error
    with result:
        raw = result.read(1048577)
        ensure(len(raw) <= 1048576, 'RESPONSE_BOUND')
        return result.status, dict(result.headers), json.loads(raw)


try:
    status, headers, baseline = request('/v1/head', 'reader')
    ensure(status == 200 and baseline['head']['incarnation'] ==
           Path('/run/secrets/identity-pin').read_text().strip(), 'LIVE_HEAD_IDENTITY')
    ensure('no-store' in headers.get('Cache-Control', '') and 'Set-Cookie' not in headers,
           'PRIVATE_RESPONSE_HEADERS')
    ensure(request('/v1/head')[0] == 401, 'ANONYMOUS_NOT_DENIED')
    ensure(request('/v1/head', 'writer')[0] == 401, 'ROLE_BOUNDARY')
    groups.append({'id': 'SC15-H01', 'status': 'PASS', 'verifiedTlsReader200': True,
                   'anonymous401': True, 'writerReader401': True, 'noCookie': True})

    bad_ca_failed = False
    try:
        wrong = ssl.create_default_context(cafile='/run/secrets/database-ca')
        urllib.request.urlopen(ORIGIN + '/v1/head', context=wrong, timeout=3)
    except urllib.error.URLError as error:
        bad_ca_failed = isinstance(error.reason, ssl.SSLCertVerificationError)
    ensure(bad_ca_failed, 'UNTRUSTED_CA_ACCEPTED')
    wrong_name_failed = False
    try:
        with socket.create_connection(('trust-ingress', 8443), timeout=3) as raw:
            with context.wrap_socket(raw, server_hostname='wrong.invalid'):
                pass
    except ssl.SSLCertVerificationError:
        wrong_name_failed = True
    ensure(wrong_name_failed, 'WRONG_TLS_NAME_ACCEPTED')
    groups.append({'id': 'SC15-H02', 'status': 'PASS', 'wrongCaRejected': True,
                   'wrongServerNameRejected': True})

    password = Path('/run/secrets/database-password').read_text().strip()
    params = dict(host='trust-db', dbname='estakada_trust', user='trust_runtime',
                  password=password, connect_timeout=2, sslmode='verify-full',
                  sslrootcert='/run/secrets/database-ca')
    with psycopg.connect(**params) as conn:
        ensure(conn.execute('SELECT current_user').fetchone()[0] == 'trust_runtime', 'DB_ROLE')
        ensure(conn.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone()[0], 'DB_TLS')
        ensure(conn.execute("SELECT current_setting('fsync'),current_setting('synchronous_commit'),"
                            "current_setting('full_page_writes')").fetchone() == ('on', 'on', 'on'),
               'DB_DURABILITY_SETTINGS')
        ensure(conn.execute("SELECT has_schema_privilege(current_user,'trust','CREATE'),"
                            "has_schema_privilege(current_user,'public','CREATE')").fetchone() == (False, False),
               'RUNTIME_DDL_PRIVILEGE')
        counts_before = conn.execute('SELECT (SELECT count(*) FROM journal_operation),'
                                    '(SELECT count(*) FROM journal_routepolicy),'
                                    '(SELECT count(*) FROM journal_requesttombstone)').fetchone()
    plain_failed = False
    try:
        with psycopg.connect(**{**params, 'sslmode': 'disable'}):
            pass
    except psycopg.OperationalError:
        plain_failed = True
    ensure(plain_failed, 'SERVER_ACCEPTED_PLAINTEXT_DB')
    groups.append({'id': 'SC15-H03', 'status': 'PASS', 'databaseVerifyFull': True,
                   'serverRejectsPlaintext': True, 'runtimeNoSchemaCreate': True,
                   'durableCommitSettings': True})

    body = {'operationId': str(uuid.uuid4()), 'incarnation': baseline['head']['incarnation'],
            'expectedGeneration': baseline['head']['generation'],
            'writerEpoch': baseline['head']['writerEpoch'], 'kind': 'route_restriction',
            'objectId': str(uuid.uuid4()), 'basis': 'a' * 64,
            'policies': [{'target': '/dev15-synthetic-only/', 'objectId': str(uuid.uuid4()),
                          'policy': 'DELETED', 'redirectTarget': None}], 'requestIds': []}
    code, _, value = request('/v1/prepare', 'writer', body)
    ensure(code == 503 and value['code'] == 'WRITE_PROFILE_DISABLED', 'WRITE_GATE_NOT_CLOSED')
    code, _, value = request('/v1/prepare', body={'noise': 'DEV15-PRIVATE-CANARY'},
                            extra={'Authorization': 'Bearer invalid:DEV15-PRIVATE-CANARY'})
    ensure(code == 401, 'MALFORMED_AUTH_NOT_REFUSED')
    client = http.client.HTTPSConnection('trust-ingress', 8443, context=context, timeout=3)
    try:
        client.request('POST', '/v1/prepare', body=b'', headers={'Content-Length': '1048577'})
        response = client.getresponse()
        ensure(response.status == 413 and 'no-store' in response.getheader('Cache-Control', ''),
               'INGRESS_BODY_BOUND_OR_CACHE')
        response.read(4096)
    finally:
        client.close()
    after = request('/v1/head', 'reader')[2]
    ensure(after['head'] == baseline['head'], 'READONLY_HEAD_CHANGED')
    with psycopg.connect(**params) as conn:
        counts_after = conn.execute('SELECT (SELECT count(*) FROM journal_operation),'
                                   '(SELECT count(*) FROM journal_routepolicy),'
                                   '(SELECT count(*) FROM journal_requesttombstone)').fetchone()
    ensure(counts_before == counts_after == (0, 0, 0), 'READONLY_API_MUTATED')
    groups.append({'id': 'SC15-H04', 'status': 'PASS', 'persistentWrite503': True,
                   'authCanaryRejected': True, 'bodyOverLimit413NoStore': True,
                   'operationPolicyTombstoneRows': 0, 'headUnchanged': True})
    print(json.dumps({'status': 'PASS', 'groups': groups, 'scope': 'real-TLS-disabled-profile-only'}))
except Exception as error:
    code = str(error) if isinstance(error, RuntimeError) else type(error).__name__
    if not code.replace('_', '').isalnum() or len(code) > 100:
        code = 'TRANSPORT_PROBE_FAILED'
    print(json.dumps({'status': 'FAIL', 'errorCode': code, 'groups': groups}))
    raise SystemExit(1) from None
