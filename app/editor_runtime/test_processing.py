import io
import json
import os
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from .child_bootstrap import ADDRESS_BYTES, CPU_SECONDS, read_frame
from .processing import (MAGIC, PROTOCOL, ProcessingDeadline, ProcessingRejected,
                         ProcessingResourceLimit, ProcessingUnavailable, _exchange)

PRELUDE = 'import sys,json,os; data=sys.stdin.buffer.read(); '


def command(code, *arguments):
    return (sys.executable, '-I', '-B', '-c', code, *arguments)


def output(result):
    return json.dumps({'protocol': PROTOCOL, 'ok': True, 'result': result})


class ProcessingTests(unittest.TestCase):
    def test_actual_framed_context_and_body(self):
        child = '''
import sys,json,struct
data=sys.stdin.buffer.read()
magic=b'ES-EDITOR-1\\n'
assert data.startswith(magic)
a,b=struct.unpack('!QQ',data[len(magic):len(magic)+16])
start=len(magic)+16
context=json.loads(data[start:start+a].decode())
raw=data[start+a:]
assert len(raw)==b
print(json.dumps({'protocol':'editor-worker-v1','ok':True,'result':{'context':context,'rawMatches':raw==b'{"input":"known"}'}}))
'''
        result = _exchange(command(child), b'{"input":"known"}', {'generation': 3, 'label': 'тест'})
        self.assertEqual(result, {'context': {'generation': 3, 'label': 'тест'}, 'rawMatches': True})

    def test_pipe_output_exact_boundary_and_one_less(self):
        wire = output({'text': 'x' * 100})
        child = PRELUDE + 'sys.stdout.write(' + repr(wire) + ')'
        self.assertEqual(_exchange(command(child), b'{}', {}, output_budget=len(wire))['text'], 'x' * 100)
        with self.assertRaises(ProcessingResourceLimit):
            _exchange(command(child), b'{}', {}, output_budget=len(wire) - 1)

    def test_invalid_protocol_json_duplicate_nonfinite_and_shapes(self):
        invalid = ['not-json', '{"protocol":"wrong","ok":true,"result":{}}',
                   '{"protocol":"editor-worker-v1","ok":true,"ok":true,"result":{}}',
                   '{"protocol":"editor-worker-v1","ok":1,"result":{}}',
                   '{"protocol":"editor-worker-v1","ok":true,"result":[]}',
                   '{"protocol":"editor-worker-v1","ok":true,"result":{"x":NaN}}',
                   '{"protocol":"editor-worker-v1","ok":true,"result":{"x":1e999}}']
        for wire in invalid:
            with self.subTest(wire=wire), self.assertRaises(ProcessingUnavailable):
                _exchange(command(PRELUDE + 'sys.stdout.write(' + repr(wire) + ')'), b'{}', {})

    def test_fixed_error_envelopes_and_nonzero_exit(self):
        for code, error in [('INVALID_INPUT', ProcessingRejected), ('RESOURCE_LIMIT', ProcessingResourceLimit),
                            ('UNAVAILABLE', ProcessingUnavailable), ('arbitrary', ProcessingUnavailable)]:
            wire = json.dumps({'protocol': PROTOCOL, 'ok': False, 'code': code})
            with self.subTest(code=code), self.assertRaises(error):
                _exchange(command(PRELUDE + 'sys.stdout.write(' + repr(wire) + ')'), b'{}', {})
        with self.assertRaises(ProcessingUnavailable):
            _exchange(command(PRELUDE + 'raise SystemExit(7)'), b'{}', {})

    def test_large_duplex_io_does_not_deadlock(self):
        child = 'import sys,json;sys.stdout.write(json.dumps({"protocol":"editor-worker-v1","ok":True,"result":{"text":"a"*200000}}));sys.stdout.flush();sys.stdin.buffer.read()'
        result = _exchange(command(child), b'a' * 200000, {}, seconds=3)
        self.assertEqual(len(result['text']), 200000)

    def test_stderr_flood_is_bounded_and_not_forwarded(self):
        child = 'import sys;sys.stderr.write("PRIVATE_TEST_DIAGNOSTIC"*10000);sys.stderr.flush();sys.stdin.buffer.read()'
        with self.assertRaises(ProcessingResourceLimit) as caught:
            _exchange(command(child), b'a' * 200000, {}, seconds=3, stderr_budget=1024)
        self.assertNotIn('PRIVATE_TEST_DIAGNOSTIC', str(caught.exception))

    def test_blocked_input_deadline_kills_and_reaps_child(self):
        with TemporaryDirectory() as directory:
            pidfile = Path(directory) / 'pid'
            child = 'import os,sys,time;open(sys.argv[1],"w").write(str(os.getpid()));time.sleep(10)'
            started = time.monotonic()
            with self.assertRaises(ProcessingDeadline):
                _exchange(command(child, str(pidfile)), b'a' * 200000, {}, seconds=0.5)
            self.assertLess(time.monotonic() - started, 3)
            self.assertTrue(pidfile.exists())
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pidfile.read_text()), 0)

    def test_early_exit_does_not_acknowledge_an_untransferred_body(self):
        child = 'import sys;sys.stdout.write(' + repr(output({'fake': True})) + ')'
        with self.assertRaises(ProcessingUnavailable):
            _exchange(command(child), b'a' * (1024 * 1024), {})

    def test_environment_and_inheritable_file_descriptor_are_not_forwarded(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'private-canary'
            path.write_bytes(b'SYNTHETIC')
            fd = os.open(path, os.O_RDONLY)
            try:
                os.set_inheritable(fd, True)
                inode = os.fstat(fd).st_ino
                child = '''
import sys,json,os
sys.stdin.buffer.read()
try: inherited=os.fstat(int(sys.argv[1])).st_ino==int(sys.argv[2])
except OSError: inherited=False
print(json.dumps({'protocol':'editor-worker-v1','ok':True,'result':{'inherited':inherited,'envCanary':'EDITOR_TEST_CANARY' in os.environ}}))
'''
                with patch.dict(os.environ, {'EDITOR_TEST_CANARY': 'SYNTHETIC-NOT-FORWARDED'}):
                    result = _exchange(command(child, str(fd), str(inode)), b'{}', {})
                self.assertEqual(result, {'inherited': False, 'envCanary': False})
            finally:
                os.close(fd)

    def test_child_resource_limits_are_real_without_parent_preexec(self):
        project = str(Path(__file__).resolve().parent.parent)
        child = '''
import sys,json,resource
sys.path.insert(0,sys.argv[1])
from editor_runtime.child_bootstrap import configure_limits,ADDRESS_BYTES
configure_limits()
sys.stdin.buffer.read()
try:
    impossible=bytearray(ADDRESS_BYTES*2)
    limited=False
except MemoryError: limited=True
print(json.dumps({'protocol':'editor-worker-v1','ok':True,'result':{'as':resource.getrlimit(resource.RLIMIT_AS)[0],'cpu':resource.getrlimit(resource.RLIMIT_CPU)[0],'core':resource.getrlimit(resource.RLIMIT_CORE)[0],'allocationRefused':limited}}))
'''
        result = _exchange(command(child, project), b'{}', {})
        self.assertEqual(result, {'as': ADDRESS_BYTES, 'cpu': CPU_SECONDS, 'core': 0, 'allocationRefused': True})

    def test_bootstrap_frame_rejects_ambiguity_and_extra_bytes(self):
        context = b'{"generation":1}'
        raw = b'{"value":"known"}'
        frame = MAGIC + struct.pack('!QQ', len(context), len(raw)) + context + raw
        self.assertEqual(read_frame(io.BytesIO(frame)), (raw, {'generation': 1}))
        invalid = [b'bad', frame[:-1], frame + b'x', MAGIC + struct.pack('!QQ', 64 * 1024 * 1024 + 1, 0)]
        for bad in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'[]'):
            invalid.append(MAGIC + struct.pack('!QQ', len(bad), 0) + bad)
        for value in invalid:
            with self.subTest(length=len(value)), self.assertRaises(ValueError):
                read_frame(io.BytesIO(value))
