"""FR07 framework/PG/real-process checks; not Nginx transport evidence."""
import gc
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from unittest.mock import patch
from uuid import UUID

from django.test import TransactionTestCase, override_settings

from editor_runtime import processing
from editor_runtime.child_bootstrap import ADDRESS_BYTES, CPU_SECONDS
from editor_runtime.guards import EditorSlot
from page_editor import test_check_http as H
from page_editor.checks import verify_check_receipt


# Fixed trusted test programs only; neither code nor arguments come from a DTO.
# Write only our PID before configure_limits sets RLIMIT_FSIZE=0.
PRELUDE = """
import os,sys,time
from pathlib import Path
sys.path.insert(0, '/app')
Path(sys.argv[1]).write_text(str(os.getpid()), encoding='ascii')
from editor_runtime.child_bootstrap import configure_limits,read_frame
configure_limits()
"""
FAULTS = {
    'timeout': PRELUDE + "time.sleep(60)\n",
    'crash': PRELUDE + """
read_frame(sys.stdin.buffer)
sys.stdout.write('{"protocol":"editor-worker-v1","ok":true,"result":{}}')
sys.stdout.flush()
raise SystemExit(7)
""",
    'stderr': PRELUDE + """
sys.stderr.write('FR07_SYNTHETIC_DIAGNOSTIC_' * 2000)
sys.stderr.flush()
time.sleep(60)
""",
}


def cgroup_facts():
    root = Path('/sys/fs/cgroup')
    facts = {}
    for name in ('memory.current', 'memory.peak', 'memory.max', 'cpu.max', 'pids.max'):
        facts[name] = (root / name).read_text(encoding='ascii').strip()
    facts['memory.events'] = {key: int(value) for key, value in
        (line.split() for line in (root / 'memory.events').read_text(encoding='ascii').splitlines())}
    return facts


@override_settings(ROOT_URLCONF='page_editor.test_check_http', MIDDLEWARE=H.TEST_MIDDLEWARE,
                   AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EditorFailureHttpTests(TransactionTestCase):
    # Reuse fixture methods, not inheritance/import of another collected TestCase.
    setUp = H.EditorCheckHttpTests.setUp
    login = H.EditorCheckHttpTests.login
    raw = H.EditorCheckHttpTests.raw
    payload = H.EditorCheckHttpTests.payload
    post = H.EditorCheckHttpTests.post
    state = H.EditorCheckHttpTests.state
    context = H.EditorCheckHttpTests.context
    assert_error = H.EditorCheckHttpTests.assert_error

    def process_fault(self, kind, code):
        before = self.state()
        pidfile = Path(self.temp.name) / ('fr07-' + kind + '.pid')
        original_popen = subprocess.Popen
        processes = []

        def capture(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            processes.append(process)
            return process

        def actual_fault(raw, context):
            return processing._exchange(
                (sys.executable, '-I', '-B', '-c', FAULTS[kind], str(pidfile)), raw, context)

        started = time.monotonic()
        with patch('page_editor.views.normalize_input', side_effect=actual_fault), \
             patch('editor_runtime.processing.subprocess.Popen', side_effect=capture):
            response = self.post(self.owner_client)
        elapsed = time.monotonic() - started
        self.assert_error(response, 503, code)
        self.assertNotIn(b'FR07_SYNTHETIC_DIAGNOSTIC', response.content)
        self.assertNotIn(b'checkReceipt', response.content)
        self.assertEqual(len(processes), 1)
        process = processes[0]
        self.assertTrue(pidfile.is_file(), 'OWN_CHILD_PID_NOT_RECORDED')
        self.assertEqual(int(pidfile.read_text(encoding='ascii')), process.pid)
        self.assertIsNotNone(process.returncode, 'OWN_CHILD_NOT_WAITED')
        with self.assertRaises(ProcessLookupError):
            os.kill(process.pid, 0)
        with self.assertRaises(ChildProcessError):
            os.waitpid(process.pid, os.WNOHANG)
        self.assertTrue(all(stream.closed for stream in (process.stdin, process.stdout, process.stderr)))
        if kind == 'timeout':
            self.assertGreaterEqual(elapsed, processing.WORK_SECONDS - 0.1)
        if kind == 'crash':
            self.assertEqual(process.returncode, 7)
        self.assertEqual(self.state(), before)
        with EditorSlot():
            pass
        # A separate real healthy manual request, outside both fault patches.
        healthy = self.post(self.owner_client)
        self.assertEqual(healthy.status_code, 200)
        self.assertTrue(bool(healthy.json().get('checkReceipt')))
        self.assertEqual(self.state(), before)
        print(json.dumps({'scope': 'FR07-framework-real-exchange', 'fault': kind,
            'status': 'PASS', 'elapsedSeconds': round(elapsed, 3),
            'exitCode': process.returncode, 'reaped': True, 'slotFree': True,
            'healthyRealCheck': True, 'domainUnchanged': True}), flush=True)

    def test_fr07_001_actual_default_wall_timeout_reap_slot_and_healthy_check(self):
        self.process_fault('timeout', 'EDITOR_PROCESS_TIMEOUT')

    def test_fr07_002_actual_nonzero_exit_valid_prefix_is_not_success(self):
        self.process_fault('crash', 'EDITOR_PROCESS_UNAVAILABLE')

    def test_fr07_003_actual_stderr_cap_no_diagnostic_forwarding_and_recovery(self):
        self.process_fault('stderr', 'EDITOR_PROCESS_RESOURCE_LIMIT')

    def test_fr07_006_full_framework_handler_max_dto_real_child_no_mutation(self):
        before = self.state()
        construction_started = time.monotonic()
        construction_before = cgroup_facts()
        columns = [{'id': str(UUID(int=index + 1)), 'label': '🚀' * 500} for index in range(32)]
        rows = [{'id': str(UUID(int=1000 + index)), 'label': '🚀' * 500,
            'cells': [{'column_id': columns[column]['id'], 'kind': 'text', 'text': '🚀' * 1000}
                      for column in range(20)]} for index in range(500)]
        text = '🚀' * 200000
        prefix, suffix = '<p data-es-anchor="', '">' + text + '</p>'
        html = prefix + 'a' * (1024 * 1024 - len((prefix + suffix).encode())) + suffix
        self.assertEqual(len(html.encode()), 1024 * 1024)
        html_hash = hashlib.sha256(html.encode()).hexdigest()
        price = {'columns': columns, 'rows': rows}
        price_hash = hashlib.sha256(self.raw(price)).hexdigest()
        raw = self.raw(self.payload({'price': price, 'intro_text': html, 'main_text': html}))
        input_hash, input_bytes = hashlib.sha256(raw).hexdigest(), len(raw)
        self.assertLessEqual(input_bytes, 64 * 1024 * 1024)
        del columns, rows, text, prefix, suffix, html, price
        gc.collect()
        construction_seconds = time.monotonic() - construction_started
        handler_before = cgroup_facts()
        self.assertEqual(handler_before['memory.max'], str(768 * 1024 * 1024))
        quota, period = map(int, handler_before['cpu.max'].split())
        self.assertEqual(quota, period)
        self.assertEqual(ADDRESS_BYTES, 384 * 1024 * 1024)
        self.assertEqual(CPU_SECONDS, 10)
        self.assertEqual(processing.WORK_SECONDS, 20.0)
        started = time.monotonic()
        # Framework Client is not the approved streaming WSGI socket. In this
        # MAX-only seam return the identical submitted bytes, without invoking
        # Django's global 11MiB HttpRequest.body cache. Product caps unchanged.
        with patch('page_editor.views.normalize_input', wraps=processing.normalize_input) as real_child:
            response = self.post(self.owner_client, raw=raw, reader=lambda request, profile: raw)
        elapsed = time.monotonic() - started
        handler_after = cgroup_facts()
        # No giant assertion diffs, response/receipt/raw source dumps on failure.
        if response.status_code != 200:
            code = 'NON_JSON'
            try:
                candidate = response.json().get('code')
                if isinstance(candidate, str) and 0 < len(candidate) <= 120 and all(
                        char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for char in candidate):
                    code = candidate
                else:
                    code = 'NO_FIXED_CODE'
            except (ValueError, AttributeError, TypeError):
                pass
            print(json.dumps({'scope': 'FR07-006-full-framework-check', 'status': 'FAIL',
                'httpStatus': response.status_code, 'code': code,
                'realNormalizerCallCount': real_child.call_count,
                'wireBytes': input_bytes, 'wireSha256': input_hash,
                'handlerSeconds': round(elapsed, 3), 'handlerBefore': handler_before,
                'handlerAfter': handler_after, 'frameworkReaderSeam': True}), flush=True)
        self.assertEqual(response.status_code, 200, 'MAX_HANDLER_REFUSED')
        self.assertEqual(real_child.call_count, 1, 'MAX_REAL_NORMALIZER_NOT_ONCE')
        value = response.json()
        self.assertTrue(value.get('inputFingerprint') == input_hash, 'MAX_INPUT_HASH_CHANGED')
        changes = value['normalisedChanges']
        self.assertTrue(set(changes) == {'intro_text', 'main_text', 'price'}, 'MAX_FIELDS_CHANGED')
        self.assertTrue(hashlib.sha256(self.raw(changes['price'])).hexdigest() == price_hash,
                        'MAX_PRICE_TRUNCATED_OR_CHANGED')
        self.assertEqual(len(changes['price']['columns']), 32)
        self.assertEqual(len(changes['price']['rows']), 500)
        self.assertEqual(sum(len(row['cells']) for row in changes['price']['rows']), 10000)
        for field in ('intro_text', 'main_text'):
            self.assertTrue(hashlib.sha256(changes[field].encode()).hexdigest() == html_hash,
                            'MAX_HTML_TRUNCATED_OR_CHANGED')
        proof = verify_check_receipt(value['checkReceipt'], context=self.context(), changes=changes)
        self.assertTrue(proof['inputFingerprint'] == input_hash, 'MAX_PROOF_NOT_BOUND')
        self.assertEqual(self.state(), before)
        for name in ('memory.max', 'cpu.max', 'pids.max'):
            self.assertEqual(handler_before[name], handler_after[name])
        for name in ('oom', 'oom_kill'):
            self.assertEqual(handler_before['memory.events'].get(name, 0),
                             handler_after['memory.events'].get(name, 0))
        self.assertLessEqual(int(handler_after['memory.peak']), 768 * 1024 * 1024)
        print(json.dumps({'scope': 'FR07-006-full-framework-check', 'status': 'PASS',
            'wireBytes': input_bytes, 'wireSha256': input_hash, 'responseBytes': len(response.content),
            'responseSha256': hashlib.sha256(response.content).hexdigest(),
            'constructionSeconds': round(construction_seconds, 3),
            'handlerSeconds': round(elapsed, 3), 'constructionBefore': construction_before,
            'handlerBefore': handler_before, 'handlerAfter': handler_after,
            'parentPeakRssKiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'childPeakRssKiB': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
            'cgroupPeakIsLifetimeIncludingFixture': True, 'rssPeaksNotSummed': True,
            'frameworkReaderSeam': True, 'nginxProof': False, 'domainUnchanged': True,
            'receiptVerified': True}), flush=True)
