import io
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import time
import unittest

from .guards import (BodyDeadline, BodyMalformed, BodyTooLarge, BodyTypeUnsupported,
                     EditorBusy, EditorForbidden, EditorSlot, InputProfile, LengthRequired,
                     TransportUnavailable, input_profile, read_json_bytes)


class Request:
    method = 'POST'
    content_type = 'application/json'
    content_params = {}

    def __init__(self, stream, length):
        self.META = {'wsgi.input': stream, 'CONTENT_LENGTH': str(length)}
        self.remaining = length
        self.stream = stream
        self.reads = 0

    def read(self, size):
        self.reads += 1
        value = self.stream.read(min(size, self.remaining))
        self.remaining -= len(value)
        return value


class GuardTests(unittest.TestCase):
    def sockets(self):
        writer, reader = socket.socketpair()
        stream = reader.makefile('rb')
        self.addCleanup(writer.close)
        self.addCleanup(reader.close)
        self.addCleanup(stream.close)
        return writer, stream

    def test_profiles_are_derived_from_server_permission_flags(self):
        self.assertEqual(input_profile(owner=True).byte_budget, 64 * 1024 * 1024)
        self.assertEqual(input_profile(owner=False, can_price=True).byte_budget, 64 * 1024 * 1024)
        self.assertEqual(input_profile(owner=False).byte_budget, 5 * 1024 * 1024)
        self.assertEqual(input_profile(owner=True, shared=True).byte_budget, 4 * 1024 * 1024)
        with self.assertRaises(EditorForbidden):
            input_profile(owner=False, shared=True)
        for value in (1, None, 'owner'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                input_profile(owner=value)

    def test_real_socket_exact_boundary_and_zero_length(self):
        writer, stream = self.sockets()
        writer.sendall(b'abc')
        self.assertEqual(read_json_bytes(Request(stream, 3), InputProfile(3)), b'abc')
        self.assertEqual(read_json_bytes(Request(io.BytesIO(), 0), InputProfile(3)), b'')

    def test_pinned_django_runserver_limited_stream_keeps_socket_deadline(self):
        from django.core.handlers.wsgi import LimitedStream
        writer, stream = self.sockets()
        writer.sendall(b'abcEXTRA')
        wrapped = LimitedStream(LimitedStream(stream, 3), 3)
        self.assertEqual(read_json_bytes(Request(wrapped, 3), InputProfile(3)), b'abc')

    def test_pinned_django_wrapper_blocking_read_is_interrupted(self):
        from django.core.handlers.wsgi import LimitedStream
        writer, stream = self.sockets()
        writer.sendall(b'a')
        started = time.monotonic()
        with self.assertRaises(BodyDeadline):
            read_json_bytes(Request(LimitedStream(stream, 3), 3), InputProfile(3), seconds=0.05)
        self.assertLess(time.monotonic() - started, 1)

    def test_rejected_headers_do_not_read_any_body(self):
        variants = [({}, '4', BodyTooLarge), ({}, '', LengthRequired),
                    ({}, None, LengthRequired), ({}, '-1', BodyMalformed),
                    ({}, '1,1', BodyMalformed), ({}, 'NaN', BodyMalformed),
                    ({}, 2, BodyMalformed), ({'HTTP_TRANSFER_ENCODING': 'chunked'}, '2', BodyMalformed),
                    ({'HTTP_CONTENT_ENCODING': 'gzip'}, '2', BodyMalformed)]
        for headers, length, expected in variants:
            request = Request(io.BytesIO(b'abc'), 3)
            request.META.update(headers, CONTENT_LENGTH=length)
            with self.subTest(headers=headers, length=length), self.assertRaises(expected):
                read_json_bytes(request, InputProfile(3))
            self.assertEqual(request.reads, 0)
        request = Request(io.BytesIO(b'abc'), 3)
        request.content_type = 'application/x-www-form-urlencoded'
        with self.assertRaises(BodyTypeUnsupported):
            read_json_bytes(request, InputProfile(3))
        self.assertEqual(request.reads, 0)

    def test_truncated_stream_is_not_partial_success(self):
        writer, stream = self.sockets()
        writer.sendall(b'a')
        writer.shutdown(socket.SHUT_WR)
        with self.assertRaises(BodyMalformed):
            read_json_bytes(Request(stream, 3), InputProfile(3))

    def test_deadline_really_interrupts_a_blocking_socket_read(self):
        writer, stream = self.sockets()
        writer.sendall(b'a')
        started = time.monotonic()
        with self.assertRaises(BodyDeadline):
            read_json_bytes(Request(stream, 3), InputProfile(3), seconds=0.1)
        self.assertLess(time.monotonic() - started, 2)

    def test_success_cancels_timer_before_a_later_read_on_same_socket(self):
        writer, stream = self.sockets()
        writer.sendall(b'ab')
        self.assertEqual(read_json_bytes(Request(stream, 2), InputProfile(2), seconds=0.05), b'ab')

        def later_body():
            threading.Event().wait(0.1)
            writer.sendall(b'cd')
        sender = threading.Thread(target=later_body)
        sender.start()
        try:
            self.assertEqual(read_json_bytes(Request(stream, 2), InputProfile(2), seconds=1), b'cd')
        finally:
            sender.join(timeout=2)
        self.assertFalse(sender.is_alive())

    def test_unknown_non_socket_transport_is_not_claimed_bounded(self):
        request = Request(io.BytesIO(b'ab'), 2)
        with self.assertRaises(TransportUnavailable):
            read_json_bytes(request, InputProfile(2))
        self.assertEqual(request.reads, 0)

    def test_slot_is_nonblocking_cross_process_and_released_after_error(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'slot'
            child = '''
import sys
from editor_runtime.guards import EditorSlot,EditorBusy
try:
    with EditorSlot(sys.argv[1]):
        sys.exit(2 if sys.argv[2]=='busy' else 0)
except EditorBusy:
    sys.exit(0 if sys.argv[2]=='busy' else 2)
'''
            with EditorSlot(path):
                with self.assertRaises(EditorBusy):
                    with EditorSlot(path):
                        self.fail('Second descriptor acquired the same slot')
                result = subprocess.run([sys.executable, '-B', '-c', child, str(path), 'busy'], timeout=3)
                self.assertEqual(result.returncode, 0)
            self.assertTrue(path.exists())
            self.assertEqual(path.read_bytes(), b'')
            result = subprocess.run([sys.executable, '-B', '-c', child, str(path), 'free'], timeout=3)
            self.assertEqual(result.returncode, 0)
            with self.assertRaises(RuntimeError):
                with EditorSlot(path):
                    raise RuntimeError('Synthetic failure')
            with EditorSlot(path):
                pass

    def test_slot_rejects_links_and_insecure_existing_mode(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / 'original'
            target.write_bytes(b'')
            target.chmod(0o600)
            linked = Path(directory) / 'linked'
            linked.symlink_to(target)
            with self.assertRaises(TransportUnavailable):
                with EditorSlot(linked):
                    pass
            hard = Path(directory) / 'hard'
            os.link(target, hard)
            with self.assertRaises(TransportUnavailable):
                with EditorSlot(target):
                    pass
            hard.unlink()
            target.chmod(0o666)
            with self.assertRaises(TransportUnavailable):
                with EditorSlot(target):
                    pass
