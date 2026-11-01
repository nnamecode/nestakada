"""Read-only response functions. Registered by test hosts, not product URLConf."""
import re
from uuid import UUID
from django.db import connection, transaction
from django.http import HttpResponse, FileResponse
from . import public as P

_TAG = re.compile(r'(?:W/)?"[\x21\x23-\x7e\x80-\xff]*"')


def conditional_matches(value, etag):
    if type(value) is not str or type(etag) is not str:
        return False
    text = value.strip(' \t')
    if text == '*':
        return True
    position, tags = 0, []
    while position < len(text):
        match = _TAG.match(text, position)
        if match is None:
            return False
        tag = match.group()
        tags.append(tag[2:] if tag.startswith('W/') else tag)
        position = match.end()
        while position < len(text) and text[position] in ' \t': position += 1
        if position == len(text): break
        if text[position] != ',': return False
        position += 1
        while position < len(text) and text[position] in ' \t': position += 1
        if position == len(text): return False
    return bool(tags) and etag in tags


def _closed(status):
    response = HttpResponse('Ресурс недоступен.', status=status, content_type='text/plain; charset=utf-8')
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def unavailable_response():
    return _closed(503)


def _method(request):
    if request.method in ('GET', 'HEAD'):
        return None
    response = _closed(405)
    response['Allow'] = 'GET, HEAD'
    return response


def _headers(response, etag, *, immutable=False):
    response['Cache-Control'] = 'public, max-age=31536000, immutable' if immutable else 'no-cache'
    response['ETag'] = etag
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def html_response(request, rendered, html_bytes):
    """Trusted host owns stamp/body correspondence; no mutable body re-fetch.

    Readiness has already been proved by render_shared. No generic Page renderer
    or arbitrary user-supplied template/body execution is provided here.
    """
    denied = _method(request)
    if denied is not None: return denied
    if type(rendered) is not P.RenderedShared or type(html_bytes) is not bytes:
        return unavailable_response()
    if conditional_matches(request.headers.get('If-None-Match'), rendered.etag):
        return _headers(HttpResponse(status=304), rendered.etag)
    response = HttpResponse(b'' if request.method == 'HEAD' else html_bytes, content_type='text/html; charset=utf-8')
    response['Content-Length'] = str(len(html_bytes))
    return _headers(response, rendered.etag)


def static_response(request, name, digest):
    denied = _method(request)
    if denied is not None: return denied
    try:
        descriptor = P.static_descriptor(name)
    except (OSError, ValueError, TypeError):
        return _closed(404)
    if descriptor['digest'] != digest:
        return _closed(404)
    etag = '"' + descriptor['digest'] + '"'
    if conditional_matches(request.headers.get('If-None-Match'), etag):
        return _headers(HttpResponse(status=304), etag, immutable=True)
    response = HttpResponse(b'' if request.method == 'HEAD' else descriptor['body'], content_type=descriptor['content_type'])
    response['Content-Length'] = str(len(descriptor['body']))
    return _headers(response, etag, immutable=True)


def media_response(request, file_id):
    denied = _method(request)
    if denied is not None: return denied
    if connection.in_atomic_block:
        return unavailable_response()
    stream = None
    try:
        file_id = UUID(str(file_id))
        for attempt in range(2):
            with transaction.atomic():
                snapshot = P._capture_media(file_id)
            if snapshot is None:
                return _closed(404)
            stamp = P.digest(snapshot)
            P._read_boundary('media_captured')
            error = None
            try:
                if not P._verify_media_consumers(snapshot):
                    raise P.unavailable()
                stream, mime = P._open_media(snapshot['file'])
                P._read_boundary('media_verified')
            except Exception as exc:
                error = exc
            P._read_boundary('media_before_recheck')
            with transaction.atomic():
                current = P._capture_media(file_id)
            if current is None:
                if stream is not None: stream.close(); stream = None
                return _closed(404)
            if P.digest(current) != stamp:
                if stream is not None: stream.close(); stream = None
                if attempt == 0:
                    continue
                return unavailable_response()
            if error is not None:
                return unavailable_response()
            etag = '"' + snapshot['file']['sha256'] + '"'
            if conditional_matches(request.headers.get('If-None-Match'), etag):
                stream.close(); stream = None
                return _headers(HttpResponse(status=304), etag)
            if request.method == 'HEAD':
                stream.close(); stream = None
                response = HttpResponse(b'', content_type=mime)
                response['Content-Length'] = str(snapshot['file']['byte_size'])
            else:
                response = FileResponse(stream, content_type=mime)
                stream = None  # Ownership transfers to FileResponse; never reopen.
                response['Content-Disposition'] = 'inline'
            return _headers(response, etag)
    except Exception:
        return unavailable_response()
    finally:
        if stream is not None:
            stream.close()
    return unavailable_response()
