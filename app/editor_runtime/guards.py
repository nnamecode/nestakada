"""One editor work slot and bounded, interruptible WSGI body reads (D-331)."""
from dataclasses import dataclass
import fcntl
import math
import os
from pathlib import Path
import re
import socket
import stat
import threading
import time

MIB = 1024 * 1024
MAX_BODY_BYTES = 64 * MIB
TEXT_BODY_BYTES = 5 * MIB
SHARED_BODY_BYTES = 4 * MIB
BODY_SECONDS = 120.0
SLOT_PATH = Path('/tmp/estakada-editor.slot')


class EditorFault(Exception):
    code = 'EDITOR_UNAVAILABLE'
    status = 503

    def __init__(self):
        super().__init__(self.code)


class EditorBusy(EditorFault):
    code = 'EDITOR_BUSY'


class EditorForbidden(EditorFault):
    code = 'EDITOR_FORBIDDEN'
    status = 403


class BodyTooLarge(EditorFault):
    code = 'EDITOR_BODY_TOO_LARGE'
    status = 413


class BodyMalformed(EditorFault):
    code = 'EDITOR_BODY_INVALID'
    status = 400


class LengthRequired(EditorFault):
    code = 'EDITOR_LENGTH_REQUIRED'
    status = 411


class BodyTypeUnsupported(EditorFault):
    code = 'EDITOR_JSON_REQUIRED'
    status = 415


class BodyDeadline(EditorFault):
    code = 'EDITOR_BODY_TIMEOUT'
    status = 408


class TransportUnavailable(EditorFault):
    code = 'EDITOR_TRANSPORT_UNAVAILABLE'


@dataclass(frozen=True)
class InputProfile:
    byte_budget: int


def input_profile(*, owner, can_price=False, shared=False):
    if any(type(value) is not bool for value in (owner, can_price, shared)):
        raise ValueError('Server-owned boolean permission flags required')
    if shared:
        if not owner:
            raise EditorForbidden()
        return InputProfile(SHARED_BODY_BYTES)
    return InputProfile(MAX_BODY_BYTES if owner or can_price else TEXT_BODY_BYTES)


class EditorSlot:
    """Acquire before body reading. Keep the inode for future requests, not unlink."""

    def __init__(self, path=SLOT_PATH):
        self.path = Path(path)
        self.fd = None

    def __enter__(self):
        if not self.path.is_absolute():
            raise TransportUnavailable()
        try:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        except OSError:
            raise TransportUnavailable() from None
        try:
            opened = os.fstat(fd)
            if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                    or opened.st_uid != os.geteuid() or opened.st_mode & 0o077):
                raise TransportUnavailable()
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise EditorBusy() from None
            current = os.stat(self.path, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                raise TransportUnavailable()
            self.fd = fd
            return self
        except BaseException as error:
            os.close(fd)
            if isinstance(error, OSError):
                raise TransportUnavailable() from None
            raise

    def __exit__(self, *exc):
        if self.fd is not None:
            fd, self.fd = self.fd, None
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)


class _ReadDeadline:
    """Own a duplicated socket; shutdown interrupts a genuinely blocking read.

    Cancellation joins the timer before returning. The duplicate keeps the same
    kernel socket alive, so a reused integer fd cannot target a later request.
    This is not a generic promise for arbitrary WSGI input implementations.
    """

    def __init__(self, request, seconds):
        self.expired = threading.Event()
        self._mutex = threading.Lock()
        self._closed = False
        self._socket = None
        duplicate = None
        try:
            raw = request.META['wsgi.input']
            # Django's pinned runserver wraps the actual socket file in its
            # LimitedStream, whose IOBase.fileno is deliberately unsupported.
            # Unwrap only that exact trusted class through matching bound reads;
            # request.read still enforces both LimitedStream byte boundaries.
            from django.core.handlers.wsgi import LimitedStream
            for _ in range(3):
                if type(raw) is not LimitedStream:
                    break
                underlying = getattr(raw._read, '__self__', None)
                if underlying is None or getattr(raw._readline, '__self__', None) is not underlying:
                    raise ValueError()
                raw = underlying
            descriptor = raw.fileno()
            if type(descriptor) is not int or descriptor < 0:
                raise ValueError()
            duplicate = os.dup(descriptor)
            self._socket = socket.socket(fileno=duplicate)
            duplicate = None
            if self._socket.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_STREAM:
                raise ValueError()
        except (AttributeError, KeyError, OSError, TypeError, ValueError):
            if self._socket is not None:
                self._socket.close()
            if duplicate is not None:
                os.close(duplicate)
            raise TransportUnavailable() from None
        self._timer = threading.Timer(seconds, self._interrupt)
        self._timer.daemon = True

    def _interrupt(self):
        with self._mutex:
            if self._closed:
                return
            self.expired.set()
            try:
                self._socket.shutdown(socket.SHUT_RD)
            except OSError:
                pass

    def __enter__(self):
        try:
            self._timer.start()
        except RuntimeError:
            self._socket.close()
            raise TransportUnavailable() from None
        return self

    def __exit__(self, *exc):
        with self._mutex:
            self._closed = True
            self._timer.cancel()
        self._timer.join()
        self._socket.close()


def read_json_bytes(request, profile, *, seconds=BODY_SECONDS):
    """Call only after current identity/Page/CSRF checks AND taking EditorSlot.

    JSON is not decoded here. Framing is also enforced by the real ingress;
    reading beyond Content-Length on a keep-alive WSGI socket would block and is
    deliberately not used as a supposed request-smuggling detector.
    """
    if (not isinstance(profile, InputProfile) or type(profile.byte_budget) is not int
            or not 0 < profile.byte_budget <= MAX_BODY_BYTES):
        raise ValueError('Invalid server-owned body profile')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= BODY_SECONDS:
        raise ValueError('Invalid server-owned body deadline')
    if request.method != 'POST' or request.content_type != 'application/json':
        raise BodyTypeUnsupported()
    params = request.content_params or {}
    if any(name != 'charset' for name in params) or str(params.get('charset', 'utf-8')).lower() not in ('utf-8', 'utf8'):
        raise BodyTypeUnsupported()
    if request.META.get('HTTP_TRANSFER_ENCODING'):
        raise BodyMalformed()
    encoding = request.META.get('HTTP_CONTENT_ENCODING', '')
    if type(encoding) is not str or encoding.lower() not in ('', 'identity'):
        raise BodyMalformed()
    raw_length = request.META.get('CONTENT_LENGTH', '')
    if raw_length == '' or raw_length is None:
        raise LengthRequired()
    if type(raw_length) is not str or re.fullmatch(r'[0-9]{1,20}', raw_length) is None:
        raise BodyMalformed()
    expected = int(raw_length)
    if expected > profile.byte_budget:
        raise BodyTooLarge()
    if expected == 0:
        return b''
    started = time.monotonic()
    chunks = []
    remaining = expected
    guard = _ReadDeadline(request, seconds)
    with guard:
        try:
            while remaining:
                if guard.expired.is_set() or time.monotonic() - started >= seconds:
                    raise BodyDeadline()
                chunk = request.read(min(65536, remaining))
                if guard.expired.is_set():
                    raise BodyDeadline()
                if type(chunk) is not bytes or not chunk or len(chunk) > remaining:
                    raise BodyMalformed()
                chunks.append(chunk)
                remaining -= len(chunk)
        except (OSError, ValueError):
            if guard.expired.is_set():
                raise BodyDeadline() from None
            raise BodyMalformed() from None
    if guard.expired.is_set() or time.monotonic() - started >= seconds:
        raise BodyDeadline()
    return b''.join(chunks)
