"""SC20-001–007: real middleware, SQL/connect fences, bounded privacy state."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import csv
import gc
import hashlib
import io
import logging
import os
from pathlib import Path
import select
import signal
import tracemalloc
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connections
from django.http import HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase

from .counters import MAX_COUNT, NoiseCounters
from .middleware import ScannerMiddleware
from .noise import ExpectedScanner404Filter
from .paths import SIGNATURES, classify_path, classify_target

SCANS = ('/.env', '/.git/config', '/wp-login.php', '/phpmyadmin/index.php',
         '/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php', '/WP-ADMIN/',
         '//wp-admin/', '/%2eenv', '/%252eenv', '/a/../x', '/a%5c..%5c.env',
         '/backup.sql', '/cgi-bin/test', '/file.PHP8/more', '/secret.tar.gz')


class PathTests(SimpleTestCase):
    def test_sc20_002_encoded_signatures_and_transport_errors(self):
        for path in SCANS:
            with self.subTest(path=path):
                self.assertIn(classify_path(path), SIGNATURES[:8])
        for path in ('/%ZZ', '/%FF', '/a\x00b', '/' + chr(0xD800)):
            self.assertEqual(classify_path(path), 'malformed')
        self.assertEqual(classify_path('/' + 'x' * 8192), 'oversize')
        self.assertIsNone(classify_path('/' + 'x' * 8191))

    def test_sc20_003_allowed_paths_and_query_are_not_rewritten(self):
        for target in ('/', '/services/', '/gallery-of-works/?page=2',
                       '/services/?q=wp-login.php', '/services/wp-admin/',
                       '/.well-known/acme-challenge/AbC_123', '/.well-known/security.txt',
                       '/manage/editor-assets/editor.bundle.js', '/manage/assets/manage.css'):
            self.assertIsNone(classify_target(target), target)
        self.assertEqual(classify_path('/.well-known/.env'), 'dotfile')

    def test_sc20_003_actual_legacy_registry_with_frozen_inputs(self):
        counts = []
        targets = []
        for name, variable in (('routes', 'DEV20_ROUTES_SHA256'), ('media', 'DEV20_MEDIA_SHA256')):
            raw = Path('/legacy-docs/' + name + '.csv').read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), os.environ[variable])
            rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
            counts.append(len(rows))
            if name == 'routes':
                targets.extend(row[field] for row in rows for field in ('requested_path', 'observed_effective_path')
                               if row[field].startswith('/'))
            else:
                targets.extend(row['media_path'] if row['media_path'].startswith('/') else '/' + row['media_path']
                               for row in rows if row['media_path'])
        self.assertEqual(counts, [115, 316])
        self.assertEqual(len(targets), 543)
        for target in targets:
            self.assertIsNone(classify_target(target), target)

    def test_sc20_003_future_creation_and_legacy_conflict_refuse_without_rewrite(self):
        from content.models import Route
        from content.validators import new_target
        for path in ('/wp-admin/', '/wp-content/', '/cgi-bin/'):
            with self.assertRaisesMessage(ValidationError, 'ROUTE_RESERVED_SCAN_TARGET'):
                new_target(path)
        new_target('/services/wp-admin/')
        legacy = Route(target='/wp-login.php', kind=Route.Kind.PRIMARY, is_legacy=True)
        with self.assertRaisesMessage(ValidationError, 'ROUTE_RESERVED_SCAN_TARGET'):
            legacy.clean()
        self.assertEqual(legacy.target, '/wp-login.php')


class MiddlewareTests(SimpleTestCase):
    def test_sc20_001_minimal_request_never_inspects_body_or_session(self):
        class Minimal:
            path_info = '/.env'
            method = 'POST'

            def __getattr__(self, name):
                raise AssertionError('UNEXPECTED_REQUEST_ACCESS_' + name)

        response = ScannerMiddleware(lambda request: self.fail('DOWNSTREAM_CALLED'))(Minimal())
        self.assertEqual(response.status_code, 404)
        self.assertLess(len(response.content), 256)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertFalse(response.cookies)

    def test_sc20_001_real_client_zero_connections_sql_and_no_session(self):
        client = Client(enforce_csrf_checks=True)
        client.cookies['sessionid'] = 'PRIVATE-CANARY-NOT-A-SESSION'
        spies = []
        with ExitStack() as stack:
            for alias in connections:
                connection = connections[alias]
                spies.append(stack.enter_context(patch.object(connection, 'ensure_connection',
                    side_effect=AssertionError('SCANNER_CONNECT_ATTEMPT'))))
                stack.enter_context(connection.execute_wrapper(lambda *args: self.fail('SCANNER_SQL')))
            for path in SCANS[:6] + SCANS[7:9]:
                for method in ('get', 'head', 'post'):
                    with self.subTest(path=path, method=method):
                        response = getattr(client, method)(path + '?canary=PRIVATE-CANARY',
                            HTTP_USER_AGENT='PRIVATE-UA-CANARY')
                        self.assertEqual(response.status_code, 404)
                        self.assertIn('no-store', response['Cache-Control'])
                        self.assertFalse(response.cookies)
                        self.assertNotIn(b'PRIVATE', response.content)
                        if method == 'head':
                            self.assertEqual(response.content, b'')
            self.assertTrue(all(spy.call_count == 0 for spy in spies))

    def test_sc20_003_passthrough_preserves_original_request_and_response(self):
        request = RequestFactory().get('/Services/?q=wp-login.php')
        expected = HttpResponse('LEGITIMATE-PASSTHROUGH', status=200)
        seen = []
        response = ScannerMiddleware(lambda value: seen.append(value) or expected)(request)
        self.assertIs(response, expected)
        self.assertEqual(seen, [request])
        self.assertEqual(request.path_info, '/Services/')
        self.assertEqual(request.META['QUERY_STRING'], 'q=wp-login.php')

    def test_sc20_002_transport_refusals_are_separate_from_known_404(self):
        middleware = ScannerMiddleware(lambda request: self.fail('DOWNSTREAM'))
        for path, status in (('/%FF', 400), ('/' + 'x' * 8192, 414)):
            # Explicit PATH_INFO: RequestFactory may decode raw %FF first.
            request = RequestFactory().get('/')
            request.path_info = path
            response = middleware(request)
            self.assertEqual(response.status_code, status)
            self.assertEqual(response['Cache-Control'], 'no-store')

    def test_sc20_005_noise_failure_keeps_refusal_and_marks_incomplete(self):
        counter = NoiseCounters()
        with patch('request_guard.middleware.COUNTERS', counter), patch.object(NoiseCounters, 'note', side_effect=OSError):
            response = ScannerMiddleware(lambda request: self.fail('DOWNSTREAM'))(RequestFactory().get('/.env'))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(counter.snapshot()['countIsLowerBound'])


class CounterTests(SimpleTestCase):
    def test_sc20_004_arbitrary_path_and_ip_do_not_become_keys_or_state(self):
        counter = NoiseCounters()
        gc.collect()
        tracemalloc.start()
        for index in range(10_000):
            counter.note(classify_path('/' + str(index) + '.php'))
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        state = counter.snapshot()
        self.assertLess(current, 65536)
        self.assertLess(peak, 65536)
        self.assertEqual(set(state['counts']), set(SIGNATURES))
        self.assertEqual(state['counts']['executable']['total'], 10_000)
        self.assertEqual(state['configuredKeyLimit'], 10)
        self.assertEqual(state['scope'], 'process')
        self.assertTrue(state['historyIncomplete'])

    def test_sc20_005_window_rollover_and_clock_failure(self):
        now = [0.0]
        counter = NoiseCounters(clock=lambda: now[0])
        counter.note('wordpress')
        now[0] = 60
        state = counter.snapshot()['counts']['wordpress']
        self.assertEqual(state, {'total': 1, 'current': 0, 'previous': 1})
        now[0] = 180
        self.assertEqual(counter.snapshot()['counts']['wordpress'], {'total': 1, 'current': 0, 'previous': 0})
        now[0] = float('nan')
        self.assertFalse(counter.note('wordpress'))
        self.assertFalse(counter.snapshot()['available'])
        now[0] = 240
        self.assertTrue(counter.snapshot()['countIsLowerBound'])

    def test_sc20_005_busy_and_saturation_never_fabricate_exact_counts(self):
        counter = NoiseCounters()
        counter._lock.acquire()
        try:
            self.assertFalse(counter.note('dotfile'))
            self.assertFalse(counter.snapshot()['available'])
        finally:
            counter._lock.release()
        counter._total[1] = MAX_COUNT
        counter._current[1] = MAX_COUNT
        counter.note('dotfile')
        state = counter.snapshot()
        self.assertEqual(state['counts']['dotfile']['total'], MAX_COUNT)
        self.assertTrue(state['countIsLowerBound'])

    def test_sc20_005_concurrent_updates_are_exact_or_explicit_lower_bound(self):
        counter = NoiseCounters()
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: counter.note('dotfile'), range(1000)))
        state = counter.snapshot()
        count = state['counts']['dotfile']['total']
        self.assertGreater(count, 0)
        self.assertLessEqual(count, 1000)
        if not state['countIsLowerBound']:
            self.assertEqual(count, 1000)

    def test_sc20_005_unregistered_pid_change_is_explicitly_unavailable(self):
        counter = NoiseCounters()
        counter.note('dotfile')
        with patch('request_guard.counters.os.getpid', return_value=counter._pid + 1):
            self.assertFalse(counter.note('wordpress'))
            self.assertFalse(counter.snapshot()['available'])

    def test_sc20_005_actual_fork_resets_before_threads_and_preserves_parent(self):
        from .counters import COUNTERS
        import json
        parent_token = COUNTERS.snapshot()['processToken']
        read_fd, write_fd = os.pipe()
        child = None
        COUNTERS._lock.acquire()
        try:
            child = os.fork()
            if child == 0:
                os.close(read_fd)
                try:
                    COUNTERS.note('wordpress')
                    state = COUNTERS.snapshot()
                    facts = {'freshToken': state['processToken'] != parent_token,
                             'total': state['counts']['wordpress']['total'],
                             'other': sum(row['total'] for key, row in state['counts'].items() if key != 'wordpress')}
                    os.write(write_fd, json.dumps(facts).encode())
                    os._exit(0)
                except BaseException:
                    os._exit(1)
            os.close(write_fd)
            self.assertTrue(select.select([read_fd], [], [], 5)[0], 'child did not finish within bound')
            facts = json.loads(os.read(read_fd, 2048))
            self.assertEqual(facts, {'freshToken': True, 'total': 1, 'other': 0})
        finally:
            if child:
                done, status = os.waitpid(child, os.WNOHANG)
                if done == 0:
                    os.kill(child, signal.SIGKILL)
                    os.waitpid(child, 0)
            os.close(read_fd)
            COUNTERS._lock.release()
        self.assertEqual(COUNTERS.snapshot()['processToken'], parent_token)


class LoggingTests(SimpleTestCase):
    def record(self, name, status=404, target='/.env?secret=PRIVATE-CANARY'):
        record = logging.LogRecord(name, logging.WARNING, '', 0, '"%s" %s %s',
                                   ('GET ' + target + ' HTTP/1.1', str(status), '11'), None)
        record.status_code = status
        return record

    def test_sc20_006_actual_server_shape_and_safe_formatter_pipeline(self):
        from audit.formatters import SafeJsonFormatter
        filt = ExpectedScanner404Filter()
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(SafeJsonFormatter())
        handler.addFilter(filt)
        handler.handle(self.record('django.server'))
        self.assertEqual(stream.getvalue(), '')
        for status in (200, 400, 403, 500):
            self.assertTrue(filt.filter(self.record('django.server', status)))
        handler.handle(self.record('django.server', 500))
        self.assertNotIn('PRIVATE', stream.getvalue())
        self.assertIn('PROCESS_MESSAGE', stream.getvalue())
        self.assertTrue(filt.filter(self.record('django.server', target='/important-missing/')))

    def test_sc20_006_request_marker_only_suppresses_expected_404(self):
        request = RequestFactory().get('/.env')
        ScannerMiddleware(lambda request: self.fail('DOWNSTREAM'))(request)
        record = self.record('django.request')
        record.request = request
        self.assertFalse(ExpectedScanner404Filter().filter(record))
        record.status_code = 500
        self.assertTrue(ExpectedScanner404Filter().filter(record))
        record.status_code = 404
        record.name = 'audit'
        self.assertTrue(ExpectedScanner404Filter().filter(record))

    def test_sc20_006_long_query_cannot_restore_per_scanner_process_logs(self):
        filt = ExpectedScanner404Filter()
        for length in (9000, 100_000):
            record = self.record('django.server', target='/.env?secret=' + 'x' * length)
            self.assertFalse(filt.filter(record))
            record.status_code = 500
            self.assertTrue(filt.filter(record))
        record = self.record('django.server', target='/important-missing/?secret=' + 'x' * 9000)
        self.assertTrue(filt.filter(record))

    def test_sc20_006_non_browser_methods_keep_query_agnostic_noise_policy(self):
        for method in ('PROPFIND', 'TRACE', 'X-CUSTOM'):
            record = self.record('django.server')
            record.args = (method + ' /.env?ignored=1 HTTP/1.1', '404', '11')
            self.assertFalse(ExpectedScanner404Filter().filter(record))

    def test_sc20_006_unproven_shapes_and_objects_are_not_rendered_or_suppressed(self):
        class Dangerous:
            def __str__(self):
                raise AssertionError('UNSAFE_STRING')
            def __eq__(self, other):
                raise AssertionError('UNSAFE_EQUALITY')
        filt = ExpectedScanner404Filter()
        record = self.record('django.server')
        record.msg = Dangerous()
        self.assertTrue(filt.filter(record))
        record.msg = '"%s" %s %s'
        for args in (('GET /.env HTTP/1.1', '404', Dangerous()),
                     ('GET /.env HTTP/1.1', '500', '11'),
                     ('GET /.env HTTP/1.1 extra', '404', '11')):
            record.args = args
            self.assertTrue(filt.filter(record))
