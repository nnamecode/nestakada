"""Fixed child command and bounded duplex pipe exchange; no preexec_fn."""
from collections import deque
import json
import math
import os
from pathlib import Path
import selectors
import signal
import struct
import subprocess
import sys
import time

from .guards import EditorFault, MAX_BODY_BYTES

MAGIC = b'ES-EDITOR-1\n'
PROTOCOL = 'editor-worker-v1'
CONTEXT_BYTES = MAX_BODY_BYTES
OUTPUT_BYTES = MAX_BODY_BYTES
STDERR_BYTES = 16384
WORK_SECONDS = 20.0
BOOTSTRAP = Path(__file__).with_name('child_bootstrap.py')


class ProcessingUnavailable(EditorFault):
    code = 'EDITOR_PROCESS_UNAVAILABLE'


class ProcessingDeadline(EditorFault):
    code = 'EDITOR_PROCESS_TIMEOUT'


class ProcessingResourceLimit(EditorFault):
    code = 'EDITOR_PROCESS_RESOURCE_LIMIT'


class ProcessingRejected(EditorFault):
    code = 'EDITOR_INPUT_REJECTED'
    status = 400


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate key')
        result[key] = value
    return result


def _no_constant(value):
    raise ValueError('Non-finite number')


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('Non-finite number')
    return number


def strict_json(value):
    return json.loads(value, object_pairs_hook=_unique, parse_constant=_no_constant,
                      parse_float=_finite_float)


def _decode_result(data):
    try:
        value = strict_json(data.decode('utf-8'))
        if type(value) is not dict or value.get('protocol') != PROTOCOL or type(value.get('ok')) is not bool:
            raise ValueError()
        if value['ok']:
            if set(value) != {'protocol', 'ok', 'result'} or type(value['result']) is not dict:
                raise ValueError()
            return value['result']
        if set(value) != {'protocol', 'ok', 'code'}:
            raise ValueError()
        if value['code'] == 'INVALID_INPUT':
            raise ProcessingRejected()
        if value['code'] == 'RESOURCE_LIMIT':
            raise ProcessingResourceLimit()
        if value['code'] == 'UNAVAILABLE':
            raise ProcessingUnavailable()
        raise ValueError()
    except (ValueError, UnicodeError, RecursionError, TypeError):
        raise ProcessingUnavailable() from None


def _exchange(command, raw, context, *, seconds=WORK_SECONDS,
              output_budget=OUTPUT_BYTES, stderr_budget=STDERR_BYTES):
    """Internal primitive. Only normalize_input selects the production command.

    Tests use fixed trusted child programs. No HTTP DTO controls command, path,
    environment, deadlines or budgets. stderr is counted and discarded.
    """
    if type(raw) is not bytes or len(raw) > MAX_BODY_BYTES or type(context) is not dict:
        raise ProcessingResourceLimit()
    if (type(seconds) not in (int, float) or not math.isfinite(seconds)
            or not 0 < seconds <= WORK_SECONDS):
        raise ValueError('Invalid process deadline')
    if (type(output_budget) is not int or not 0 < output_budget <= OUTPUT_BYTES
            or type(stderr_budget) is not int or not 0 <= stderr_budget <= STDERR_BYTES):
        raise ValueError('Invalid pipe budget')
    try:
        encoded = json.dumps(context, ensure_ascii=False, allow_nan=False,
                             separators=(',', ':')).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ProcessingUnavailable() from None
    if len(encoded) > CONTEXT_BYTES:
        raise ProcessingResourceLimit()
    if (type(command) is not tuple or not command
            or any(type(part) is not str or not part for part in command)):
        raise ValueError('Trusted command tuple required')
    segments = deque(memoryview(part) for part in (
        MAGIC + struct.pack('!QQ', len(encoded), len(raw)), encoded, raw))
    started = time.monotonic()
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True, start_new_session=True,
            env={'PATH': os.defpath, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'})
    except (OSError, ValueError):
        raise ProcessingUnavailable() from None
    output = []
    output_size = 0
    stderr_size = 0
    input_complete = False
    selector = selectors.DefaultSelector()
    try:
        for stream, mode, kind in ((process.stdin, selectors.EVENT_WRITE, 'input'),
                                  (process.stdout, selectors.EVENT_READ, 'output'),
                                  (process.stderr, selectors.EVENT_READ, 'error')):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, mode, kind)
        while selector.get_map():
            remaining = seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise ProcessingDeadline()
            for key, events in selector.select(min(remaining, 0.25)):
                stream = key.fileobj
                if key.data == 'input':
                    while segments and not len(segments[0]):
                        segments.popleft()
                    if not segments:
                        selector.unregister(stream)
                        stream.close()
                        input_complete = True
                        continue
                    try:
                        written = os.write(stream.fileno(), segments[0][:65536])
                    except BlockingIOError:
                        continue
                    except BrokenPipeError:
                        selector.unregister(stream)
                        stream.close()
                        segments.clear()
                        continue
                    if written <= 0:
                        raise ProcessingUnavailable()
                    segments[0] = segments[0][written:]
                else:
                    try:
                        data = os.read(stream.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not data:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    if key.data == 'error':
                        stderr_size += len(data)
                        if stderr_size > stderr_budget:
                            raise ProcessingResourceLimit()
                    else:
                        output_size += len(data)
                        if output_size > output_budget:
                            raise ProcessingResourceLimit()
                        output.append(data)
        remaining = seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise ProcessingDeadline()
        try:
            code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise ProcessingDeadline() from None
        if code != 0 or not input_complete:
            raise ProcessingUnavailable()
        return _decode_result(b''.join(output))
    except OSError:
        raise ProcessingUnavailable() from None
    finally:
        selector.close()
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()


def normalize_input(raw, context):
    """The only production command selector. Caller owns authorization and slot."""
    return _exchange((sys.executable, '-I', '-B', str(BOOTSTRAP)), raw, context)
