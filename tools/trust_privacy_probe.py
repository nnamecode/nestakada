"""PV15: finite transport/privacy controls, no database or real credentials."""
import http.client
import importlib.util
import json
import logging
import socket
import ssl
import sys
import time
from http.server import ThreadingHTTPServer

CANARIES = ('PC15_AUTH_MARKER', 'PC15_URI_MARKER', 'PC15_PAYLOAD_MARKER',
            'PC15_SQL_MARKER', 'PC15_OS_MARKER', 'PC15_EXCEPTION_MARKER',
            'PC15_PROCESS_MARKER', 'PC15_CHILD_MARKER')


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


L = load('pv_load_fixture', '/probe/load.py')
ensure = L.ensure
GET_VIEW = POST_VIEW = None


def prepare():
    L.prepare_view()
    from django.db import DatabaseError
    from journal import views
    from journal.protocol import Fault
    from journal.safe_logging import SafeFormatter
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(SafeFormatter())
    for name in ('trust.endpoint', 'pv.process'):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.ERROR)
    L.COUNTS['requests'] = 0

    def authenticate(header, role):
        with L.LOCK:
            L.COUNTS['auth'] += 1
        if header != 'Bearer synthetic':
            raise Fault('UNAUTHORIZED', 401)
        return {'id': 'synthetic', 'role': role}

    views.auth.authenticate = authenticate

    @views.endpoint('GET', 'reader')
    def get(request, actor, body):
        with L.LOCK:
            L.COUNTS['service'] += 1
        if request.GET:
            raise Fault('INPUT_REJECTED', 400)
        fault = request.headers.get('X-Test-Fault')
        if fault == 'sql':
            raise DatabaseError(CANARIES[3])
        if fault == 'os':
            raise OSError(CANARIES[4])
        if fault == 'unexpected':
            raise RuntimeError(CANARIES[5])
        if fault == 'process':
            try:
                raise RuntimeError(CANARIES[6])
            except RuntimeError:
                logging.getLogger('pv.process').exception(CANARIES[6])
        return {'ok': True, 'fixture': 'PV15'}

    @views.endpoint('POST', 'writer', 'prepare')
    def post(request, actor, body):
        with L.LOCK:
            L.COUNTS['service'] += 1
        return {'ok': True, 'fixture': 'PV15'}

    return get, post


class Handler(L.Handler):
    def handle_view(self, method):
        from django.test import RequestFactory
        with L.LOCK:
            L.COUNTS['requests'] += 1
        headers = {'HTTP_AUTHORIZATION': self.headers.get('Authorization', ''),
                   'HTTP_X_TEST_FAULT': self.headers.get('X-Test-Fault', '')}
        if method == 'POST':
            length = int(self.headers.get('Content-Length', '0'))
            ensure(0 <= length <= 1048576, 'PV_BACKEND_BODY_BOUND')
            raw = self.rfile.read(length)
            ensure(len(raw) == length, 'PV_BACKEND_PARTIAL')
            request = RequestFactory().generic('POST', self.path, raw, content_type='application/json', **headers)
            response = POST_VIEW(request)
        else:
            request = RequestFactory().get(self.path, **headers)
            response = GET_VIEW(request)
        self.respond(response.status_code, response.content, dict(response.items()))

    def do_GET(self):
        if self.path.startswith('/control/'):
            return super().do_GET()
        ensure(self.path.split('?', 1)[0] == '/v1/head', 'PV_TARGET')
        self.handle_view('GET')

    def do_POST(self):
        ensure(self.path == '/v1/prepare', 'PV_TARGET')
        self.handle_view('POST')


def connection():
    return http.client.HTTPSConnection('trust-ingress', 8443, timeout=14,
        context=ssl.create_default_context(cafile='/fixtures/ca.pem'))


def read(conn):
    response = conn.getresponse()
    headers = response.getheaders()
    header_bytes = '\n'.join(k + ':' + v for k, v in headers).encode('utf-8')
    ensure(len(headers) <= 32 and len(header_bytes) <= 16384, 'PV_RESPONSE_HEADER_BOUND')
    raw = response.read(2049)
    ensure(len(raw) <= 2048, 'PV_RESPONSE_BOUND')
    ensure(not any(c.encode() in raw or c.encode() in header_bytes for c in CANARIES), 'PV_RESPONSE_CANARY_LEAK')
    return {'status': response.status, 'body': raw.decode('utf-8', errors='replace'),
            'responseHeaderCanaryAbsent': True, 'responseHeaderCount': len(headers),
            'cache': response.getheader('Cache-Control', ''),
            'cookie': response.getheader('Set-Cookie')}


def request(method='GET', target='/v1/head', body=None, extra=None):
    conn = connection()
    headers = {'Authorization': 'Bearer synthetic', 'Content-Type': 'application/json', 'Connection': 'close'}
    if extra:
        headers.update(extra)
    try:
        conn.request(method, target, body=body, headers=headers)
        return read(conn)
    finally:
        conn.close()


def private_response(r, status):
    ensure(r['status'] == status and 'no-store' in r['cache'] and r['cookie'] is None, 'PV_STATUS_CACHE_COOKIE')


def delayed_close(kind):
    before = L.control('stats')
    context = ssl.create_default_context(cafile='/fixtures/ca.pem')
    with socket.create_connection(('trust-ingress', 8443), timeout=14) as raw:
        with context.wrap_socket(raw, server_hostname='trust-ingress') as tls:
            if kind == 'header':
                prefix = b'GET /v1/head HTTP/1.1\r\nHost: trust-ingress\r\nX-Partial: '
            else:
                prefix = (b'POST /v1/prepare HTTP/1.1\r\nHost: trust-ingress\r\nAuthorization: Bearer synthetic\r\n'
                          b'Content-Type: application/json\r\nContent-Length: 1000\r\nConnection: close\r\n\r\n{partial')
            started = time.monotonic()
            tls.sendall(prefix)
            response = http.client.HTTPResponse(tls)
            try:
                response.begin()
                status = response.status
                ensure(status == 408, 'PV_UNEXPECTED_TIMEOUT_RESPONSE')
                response.read(2049)
                outcome = 'SERVER_408'
            except http.client.RemoteDisconnected:
                status, outcome = None, 'SERVER_EOF'
            finally:
                response.close()
            elapsed = time.monotonic() - started
    minimum, maximum = (4, 8) if kind == 'header' else (9, 13)
    ensure(minimum <= elapsed <= maximum, 'PV_SERVER_TIMEOUT_WINDOW')
    after = L.control('stats')
    ensure(before == after, 'PV_PARTIAL_REACHED_BACKEND')
    return {'kind': kind, 'outcome': outcome, 'status': status, 'elapsedSeconds': elapsed,
            'bytesSent': len(prefix), 'declaredBodyBytes': 1000 if kind == 'body' else None,
            'before': before, 'after': after}


def boundaries():
    L.control('arm')
    before = L.control('stats')
    conn = connection()
    try:
        conn.putrequest('POST', '/v1/prepare')
        conn.putheader('Content-Length', '1048577')
        conn.putheader('Connection', 'close')
        conn.endheaders()
        too_big = read(conn)
    finally:
        conn.close()
    private_response(too_big, 413)
    ensure(before == L.control('stats'), 'PV_OVERSIZE_REACHED_BACKEND')
    suffix = b'"}'
    prefix = b'{"probe":"' + CANARIES[2].encode()
    exact = prefix + b'x' * (1048576 - len(prefix) - len(suffix)) + suffix
    allowed = request('POST', '/v1/prepare', exact)
    private_response(allowed, 400)
    ensure(json.loads(allowed['body'])['code'] == 'INPUT_REJECTED', 'PV_EXACT_BODY_REASON')
    after_exact = L.control('stats')
    ensure(after_exact['requests'] == after_exact['auth'] == 1 and after_exact['service'] == after_exact['cursor'] == 0, 'PV_EXACT_BODY_BOUNDARY')
    header = request(extra={'X-Large': 'x' * 9000})
    ensure(header['status'] in (400, 431), 'PV_HEADER_LIMIT')
    private_response(header, header['status'])
    ensure(after_exact == L.control('stats'), 'PV_HEADER_REACHED_BACKEND')
    private_response(request(), 200)
    slow_header = delayed_close('header')
    partial_body = delayed_close('body')
    control = request()
    private_response(control, 200)
    return {'id': 'PV15-001-004', 'oversizeStatus': too_big['status'], 'oversizeBackendUnchanged': True,
            'exactBodyBytes': len(exact), 'exactStatus': allowed['status'], 'exactCounters': after_exact,
            'largeHeaderBytes': 9000, 'largeHeaderStatus': header['status'], 'headerRecoveryStatus': 200,
            'slowHeader': slow_header, 'partialBody': partial_body, 'recoveryStatus': 200}


def privacy():
    L.control('arm')
    cases = []
    inputs = [('auth', 401, {'extra': {'Authorization': 'Bearer ' + CANARIES[0]}}),
              ('uri', 400, {'target': '/v1/head?probe=' + CANARIES[1]}),
              ('payload', 400, {'method': 'POST', 'target': '/v1/prepare', 'body': json.dumps({'probe': CANARIES[2]}).encode()}),
              ('sql', 503, {'extra': {'X-Test-Fault': 'sql'}}),
              ('os', 503, {'extra': {'X-Test-Fault': 'os'}}),
              ('unexpected', 500, {'extra': {'X-Test-Fault': 'unexpected'}}),
              ('process', 200, {'extra': {'X-Test-Fault': 'process'}})]
    for name, status, arguments in inputs:
        r = request(**arguments)
        private_response(r, status)
        cases.append({'case': name, 'status': status, 'noStore': True, 'noCookie': True,
                      'responseCanaryAbsent': True, 'responseHeaderCanaryAbsent': r['responseHeaderCanaryAbsent'],
                      'responseHeaderCount': r['responseHeaderCount']})
    consumer = load('pv_consumer', '/trust/journal/consumer.py')
    child = 'import sys;sys.stderr.write("' + CANARIES[7] + '");sys.stdout.write(\'{"ok":false,"value":null}\')'
    consumer._worker_command = lambda: [sys.executable, '-I', '-c', child]
    try:
        consumer.HTTPSReader('/fixtures/ca.pem', 'synthetic', 'a' * 64)('/v1/head', 6)
    except consumer.SnapshotRejected as error:
        ensure(error.code == 'SNAPSHOT_TRANSPORT_REJECTED', 'PV_CHILD_REJECTION_CODE')
    else:
        raise RuntimeError('PV_CHILD_ACCEPTED')
    counters = L.control('stats')
    ensure(counters['cursor'] == 0, 'PV_UNEXPECTED_CURSOR')
    return {'id': 'PV15-005-006', 'cases': cases, 'childStderrProbe': 'ACTUAL_READER_SYNTHETIC_CHILD',
            'childRejected': True, 'fixtureCursorAttempts': 0, 'counters': counters,
            'logPrivacyRequiresHostCapture': True}


if __name__ == '__main__':
    try:
        ensure(len(sys.argv) == 2, 'PV_ARGUMENTS')
        if sys.argv[1] == 'serve':
            GET_VIEW, POST_VIEW = prepare()
            ThreadingHTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
        else:
            ensure(sys.argv[1] in ('boundaries', 'privacy'), 'PV_CASE')
            result = boundaries() if sys.argv[1] == 'boundaries' else privacy()
            print(json.dumps({'status': 'PASS', **result}, sort_keys=True))
    except Exception as error:
        code = str(error) if type(error) is RuntimeError else type(error).__name__
        print(json.dumps({'status': 'FAIL', 'code': code if code.replace('_', '').isalnum() else 'PV_FAILED'}))
        raise SystemExit(1) from None
