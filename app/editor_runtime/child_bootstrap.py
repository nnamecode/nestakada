"""Static D-331 child entry point. Limits are applied here, never preexec_fn."""
import json
import math
from pathlib import Path
import resource
import struct
import sys

ADDRESS_BYTES = 384 * 1024 * 1024
CPU_SECONDS = 10
FRAME_BYTES = 64 * 1024 * 1024
MAGIC = b'ES-EDITOR-1\n'
PROTOCOL = 'editor-worker-v1'


def configure_limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_BYTES, ADDRESS_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    sys.dont_write_bytecode = True


def _read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        value = stream.read(min(65536, remaining))
        if not value:
            raise ValueError('Truncated frame')
        chunks.append(value)
        remaining -= len(value)
    return b''.join(chunks)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate context key')
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError('Invalid context number')


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('Invalid context number')
    return number


def read_frame(stream):
    if _read_exact(stream, len(MAGIC)) != MAGIC:
        raise ValueError('Invalid frame protocol')
    context_size, raw_size = struct.unpack('!QQ', _read_exact(stream, 16))
    if context_size > FRAME_BYTES or raw_size > FRAME_BYTES:
        raise ValueError('Oversize frame')
    context = json.loads(_read_exact(stream, context_size).decode('utf-8'),
                         object_pairs_hook=_unique, parse_constant=_bad_constant,
                         parse_float=_finite_float)
    if type(context) is not dict:
        raise ValueError('Invalid context shape')
    raw = _read_exact(stream, raw_size)
    if stream.read(1):
        raise ValueError('Trailing frame data')
    return raw, context


def main():
    configure_limits()
    try:
        raw, context = read_frame(sys.stdin.buffer)
        # Fixed project path only. It is never supplied by input or environment.
        project = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(project))
        from page_editor.normalizer_child import normalize
        result = normalize(raw, context)
        if type(result) is not dict:
            raise TypeError()
        envelope = {'protocol': PROTOCOL, 'ok': True, 'result': result}
        data = json.dumps(envelope, ensure_ascii=False, allow_nan=False,
                          separators=(',', ':')).encode('utf-8')
        if len(data) > FRAME_BYTES:
            raise MemoryError()
    except (MemoryError, RecursionError):
        data = json.dumps({'protocol': PROTOCOL, 'ok': False, 'code': 'RESOURCE_LIMIT'}).encode()
    except (ValueError, UnicodeError):
        data = json.dumps({'protocol': PROTOCOL, 'ok': False, 'code': 'INVALID_INPUT'}).encode()
    except Exception:
        data = json.dumps({'protocol': PROTOCOL, 'ok': False, 'code': 'UNAVAILABLE'}).encode()
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


if __name__ == '__main__':
    main()
