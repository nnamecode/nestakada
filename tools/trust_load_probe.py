"""RP15-016 test-only HTTP fixture using the unmodified endpoint decorator."""
import concurrent.futures
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import socket
import ssl
import sys
import threading
import time

LOCK = threading.Lock()
RELEASE = threading.Event()
COUNTS = dict(auth=0, service=0, held=0, holdTimeout=0, cursor=0, peak=0, active=0)
VIEW = None


def ensure(value, code):
    if not value:
        raise RuntimeError(code)


def stats():
    with LOCK:
        return dict(COUNTS)


def prepare_view():
    sys.path.insert(0, '/trust')
    from django.conf import settings
    settings.configure(SECRET_KEY='synthetic-load-fixture', INSTALLED_APPS=['journal'],
                       DATABASES={'default': {'ENGINE': 'django.db.backends.dummy'}},
                       DEFAULT_CHARSET='utf-8', USE_TZ=True)
    import django
    django.setup()
    from django.db.backends.base.base import BaseDatabaseWrapper
    from journal import views

    def no_cursor(*args, **kwargs):
        with LOCK:
            COUNTS['cursor'] += 1
        raise RuntimeError('LD_UNEXPECTED_DATABASE_CURSOR')

    BaseDatabaseWrapper.cursor = no_cursor

    def authenticate(header, role):
        with LOCK:
            COUNTS['auth'] += 1
        ensure(header == 'Bearer synthetic' and role == 'reader', 'LD_FIXTURE_AUTH')
        return {'id': 'synthetic', 'role': 'reader'}

    views.auth.authenticate = authenticate

    @views.endpoint('GET', 'reader')
    def held_view(request, actor, body):
        holding = request.headers.get('X-Test-Hold') == '1'
        with LOCK:
            COUNTS['service'] += 1
            COUNTS['active'] += 1
            COUNTS['peak'] = max(COUNTS['peak'], COUNTS['active'])
            if holding:
                COUNTS['held'] += 1
        try:
            if holding and not RELEASE.wait(4):
                with LOCK:
                    COUNTS['holdTimeout'] += 1
                raise RuntimeError('LD_HOLD_TIMEOUT')
            return {'ok': True, 'fixture': 'LD15'}
        finally:
            with LOCK:
                COUNTS['active'] -= 1
                if holding:
                    COUNTS['held'] -= 1

    return held_view


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(7)

    def respond(self, status, raw, headers):
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith('/control/'):
            ensure(self.client_address[0] == '127.0.0.1', 'LD_CONTROL_LOOPBACK_ONLY')
            if self.path == '/control/arm':
                with LOCK:
                    ensure(COUNTS['active'] == COUNTS['held'] == 0, 'LD_ARM_WHILE_ACTIVE')
                    for key in COUNTS:
                        COUNTS[key] = 0
                    RELEASE.clear()
            elif self.path == '/control/release':
                RELEASE.set()
            else:
                ensure(self.path == '/control/stats', 'LD_UNKNOWN_CONTROL')
            self.respond(200, json.dumps(stats()).encode(), {'Content-Type': 'application/json'})
            return
        ensure(self.path == '/v1/head', 'LD_UNKNOWN_TARGET')
        from django.test import RequestFactory
        request = RequestFactory().get('/v1/head', HTTP_AUTHORIZATION=self.headers.get('Authorization', ''),
                                       HTTP_X_TEST_HOLD=self.headers.get('X-Test-Hold', ''))
        response = VIEW(request)
        self.respond(response.status_code, response.content, dict(response.items()))

    def log_message(self, *args):
        pass


def request(tls=False, hold=False, target='/v1/head'):
    conn = http.client.HTTPSConnection('trust-ingress', 8443, timeout=6,
        context=ssl.create_default_context(cafile='/fixtures/ca.pem')) if tls else http.client.HTTPConnection('127.0.0.1', 8000, timeout=6)
    try:
        started = time.monotonic()
        conn.request('GET', target, headers={'Authorization': 'Bearer synthetic',
                     'X-Test-Hold': '1' if hold else '0', 'Connection': 'close'})
        response = conn.getresponse()
        raw = response.read(2049)
        ensure(len(raw) <= 2048, 'LD_RESPONSE_BOUND')
        return {'status': response.status, 'body': raw.decode(),
                'cache': response.getheader('Cache-Control', ''), 'elapsed': time.monotonic() - started}
    finally:
        conn.close()


def control(action):
    r = request(target='/control/' + action)
    ensure(r['status'] == 200, 'LD_CONTROL_FAILED')
    return json.loads(r['body'])


def active(tls):
    control('arm')
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    jobs = []
    try:
        for _ in range(4):
            jobs.append(pool.submit(request, tls, True))
            if tls:
                time.sleep(.12)
        deadline = time.monotonic() + 2
        while True:
            before = control('stats')
            if before['held'] == 4:
                break
            ensure(time.monotonic() < deadline, 'LD_FOUR_HOLDS_NOT_OBSERVED')
            time.sleep(.02)
        fifth = request(tls)
        after = control('stats')
        ensure(fifth['status'] == 429 and fifth['elapsed'] < 2 and 'no-store' in fifth['cache'], 'LD_FAST_BUSY')
        ensure(before == after and after['auth'] == after['service'] == after['held'] == 4
               and after['cursor'] == after['holdTimeout'] == 0, 'LD_EARLY_REJECTION_BOUNDARY')
        ensure(fifth['body'] == 'Busy.\n' if tls else json.loads(fifth['body']) == {'ok': False, 'code': 'BUSY'}, 'LD_BUSY_BODY')
    finally:
        control('release')
        pool.shutdown(wait=True, cancel_futures=True)
    originals = [j.result() for j in jobs]
    ensure(len(originals) == 4 and all(r['status'] == 200 for r in originals), 'LD_HELD_RESULTS')
    recovered = request(tls)
    final = control('stats')
    ensure(recovered['status'] == 200 and final['held'] == final['active'] == final['holdTimeout'] == final['cursor'] == 0, 'LD_RECOVERY')
    return {'id': 'LD15-002' if tls else 'LD15-001', 'heldObserved': 4, 'rejectedStatus': 429,
            'rejectElapsedSeconds': fifth['elapsed'], 'before': before, 'afterReject': after,
            'releasedStatuses': [r['status'] for r in originals], 'controlStatus': 200, 'final': final}


def read_response(stream):
    line = stream.readline(8193)
    ensure(len(line) < 8193 and line.startswith(b'HTTP/1.1 '), 'LD_PIPELINE_STATUS')
    status = int(line.split()[1])
    headers = {}
    for _ in range(32):
        line = stream.readline(8193)
        ensure(0 < len(line) < 8193, 'LD_PIPELINE_HEADERS')
        if line == b'\r\n':
            break
        key, value = line.decode('ascii').split(':', 1)
        headers[key.lower()] = value.strip()
    else:
        raise RuntimeError('LD_PIPELINE_HEADER_COUNT')
    ensure('transfer-encoding' not in headers, 'LD_PIPELINE_UNEXPECTED_CHUNKING')
    length = int(headers['content-length'])
    ensure(0 <= length <= 2048, 'LD_PIPELINE_BODY_BOUND')
    body = stream.read(length)
    ensure(len(body) == length and 'no-store' in headers.get('cache-control', ''), 'LD_PIPELINE_BODY_CACHE')
    ensure(body == b'Busy.\n' if status == 429 else json.loads(body) == {'ok': True, 'fixture': 'LD15'}, 'LD_PIPELINE_BODY')
    return status


def burst():
    control('arm')
    context = ssl.create_default_context(cafile='/fixtures/ca.pem')
    statuses, offsets = [], []
    with socket.create_connection(('trust-ingress', 8443), timeout=6) as raw:
        with context.wrap_socket(raw, server_hostname='trust-ingress') as tls:
            request_bytes = b'GET /v1/head HTTP/1.1\r\nHost: trust-ingress\r\nAuthorization: Bearer synthetic\r\nConnection: keep-alive\r\n\r\n'
            start = time.monotonic()
            tls.sendall(request_bytes * 48)
            with tls.makefile('rb') as stream:
                for _ in range(48):
                    statuses.append(read_response(stream))
                    offsets.append(time.monotonic() - start)
    elapsed = offsets[-1]
    accepted, rejected = statuses.count(200), statuses.count(429)
    ensure(accepted + rejected == 48 and rejected > 0 and elapsed <= 5, 'LD_PIPELINE_RESULTS')
    first_reject = offsets[statuses.index(429)]
    ensure(first_reject < 2 and accepted <= 11 + math.ceil(10 * elapsed), 'LD_RATE_OR_QUEUE_BOUND')
    counts = control('stats')
    ensure(counts['auth'] == counts['service'] == accepted and counts['peak'] == 1
           and counts['cursor'] == counts['held'] == counts['active'] == counts['holdTimeout'] == 0, 'LD_RATE_BACKEND_COUNTS')
    time.sleep(1.2)
    recovered = request(True)
    ensure(recovered['status'] == 200, 'LD_RATE_RECOVERY')
    return {'id': 'LD15-003-004', 'requests': 48, 'connections': 1, 'responses': statuses,
            'responseOffsetsSeconds': offsets, 'accepted': accepted, 'rejected': rejected,
            'elapsedSeconds': elapsed, 'first429Seconds': first_reject, 'counts': counts,
            'recoveryWaitSeconds': 1.2, 'recoveryStatus': 200}


if __name__ == '__main__':
    try:
        ensure(len(sys.argv) == 2, 'LD_ARGUMENTS')
        kind = sys.argv[1]
        if kind == 'serve':
            VIEW = prepare_view()
            ThreadingHTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
        else:
            ensure(kind in ('api-active', 'ingress-active', 'burst'), 'LD_CASE')
            result = burst() if kind == 'burst' else active(kind == 'ingress-active')
            print(json.dumps({'status': 'PASS', **result}, sort_keys=True))
    except Exception as error:
        code = str(error) if type(error) is RuntimeError else type(error).__name__
        print(json.dumps({'status': 'FAIL', 'code': code if code.replace('_', '').isalnum() else 'LD_FAILED'}))
        raise SystemExit(1) from None
