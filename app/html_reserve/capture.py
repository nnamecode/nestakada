"""Internal reserve rendering and read-only resource capture."""
from html.parser import HTMLParser
import hashlib
import re
from urllib.parse import urlsplit

from django.http import HttpRequest, QueryDict

from content import public_views
from content.public_seo import load_configuration
from content.validators import exact_target
from django.core.exceptions import ValidationError
from shared_content import public as shared_public

from .contracts import ContractError, parse_resource_url


MAX_HTML_BYTES = 4 * 1024 * 1024
_CSS_NETWORK = re.compile(rb'(?:url\s*\(|@import\b)', re.IGNORECASE)
_JS_NETWORK = re.compile(
    rb'(?:\bfetch\s*\(|\bXMLHttpRequest\b|\bWebSocket\b|'
    rb'\bEventSource\b|\bsendBeacon\b|\bimport\s*\()', re.IGNORECASE)


def internal_request(target):
    try:
        exact_target(target)
        configuration = load_configuration()
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise ContractError('HTML_RESERVE_INTERNAL_TARGET_INVALID') from None
    parts = urlsplit(target)
    origin = urlsplit(configuration.origin)
    request = HttpRequest()
    request.method = 'GET'
    request.path = parts.path
    request.path_info = parts.path
    request.content_type = None
    request.GET = QueryDict(parts.query, mutable=False)
    request.COOKIES = {}
    request.META = {
        'REQUEST_METHOD': 'GET',
        'PATH_INFO': parts.path,
        'QUERY_STRING': parts.query,
        'SERVER_NAME': origin.hostname,
        'SERVER_PORT': str(origin.port or (443 if origin.scheme == 'https' else 80)),
        'wsgi.url_scheme': origin.scheme,
    }
    return request


def render_target(target):
    return public_views.render_reserve(internal_request(target))


def resource_policy(snapshot):
    descriptor = snapshot.descriptor
    files_by_asset = {}
    for row in descriptor.get('files', []):
        if type(row) is not list or len(row) not in (6, 7):
            raise ContractError('HTML_RESERVE_SOURCE_FILE_INVALID')
        files_by_asset.setdefault(row[1], []).append(row[0])
    bare, contextual = set(), set()
    for row in descriptor.get('usages', []):
        if type(row) is not list or len(row) not in (5, 6):
            raise ContractError('HTML_RESERVE_SOURCE_USAGE_INVALID')
        _usage_id, kind, consumer_id, slot, asset_id = row[:5]
        file_ids = files_by_asset.get(asset_id, ())
        if kind in ('current_page', 'shared_block'):
            bare.update(file_ids)
        if kind == 'current_page':
            contextual.update(
                (file_id, consumer_id, slot) for file_id in file_ids)
    return frozenset(bare), frozenset(contextual)


def _resource_url(value, origin):
    if type(value) is not str:
        raise ContractError('HTML_RESERVE_RESOURCE_URL_INVALID')
    if value.startswith(origin + '/'):
        return value[len(origin):]
    return value


_FETCH_TAGS = frozenset(('iframe', 'object', 'embed', 'video', 'audio', 'track', 'base'))
_FETCH_ATTRS = frozenset((
    'srcset', 'imagesrcset', 'poster', 'data', 'background', 'manifest',
    'ping', 'xlink:href',
))
_TEL = re.compile(r'^tel:\+[0-9]{7,15}$')


class _Resources(HTMLParser):
    def __init__(self, origin, bare_file_ids, contextual, local_targets):
        super().__init__(convert_charrefs=True)
        self.origin = origin
        self.bare_file_ids = bare_file_ids
        self.contextual = contextual
        self.local_targets = frozenset(local_targets)
        self.items = set()
        self.in_json_ld = False
        self.in_style = False

    def _add(self, value):
        self.items.add(parse_resource_url(
            _resource_url(value, self.origin),
            bare_file_ids=self.bare_file_ids,
            contextual=self.contextual))

    def _navigation(self, value):
        if type(value) is not str or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ContractError('HTML_RESERVE_NAVIGATION_URL_INVALID')
        if value.startswith('#') and len(value) > 1:
            return
        if value.startswith('/') and not value.startswith('//'):
            if value not in self.local_targets:
                raise ContractError('HTML_RESERVE_NAVIGATION_TARGET_UNKNOWN')
            return
        if _TEL.fullmatch(value) is not None:
            return
        parts = urlsplit(value)
        if (parts.scheme not in ('http', 'https') or not parts.netloc
                or parts.username is not None or parts.password is not None):
            raise ContractError('HTML_RESERVE_NAVIGATION_URL_INVALID')
        configured = urlsplit(self.origin)
        if (parts.scheme, parts.netloc) == (configured.scheme, configured.netloc):
            target = parts.path + (('?' + parts.query) if parts.query else '')
            if parts.fragment or target not in self.local_targets:
                raise ContractError('HTML_RESERVE_NAVIGATION_TARGET_UNKNOWN')

    def handle_starttag(self, tag, attrs):
        names = [name for name, _value in attrs]
        if len(names) != len(set(names)):
            raise ContractError('HTML_RESERVE_HTML_DUPLICATE_ATTRIBUTE')
        values = dict(attrs)
        if tag in _FETCH_TAGS or _FETCH_ATTRS.intersection(values):
            raise ContractError('HTML_RESERVE_FETCHABLE_HTML_FORBIDDEN')
        if tag == 'form':
            raise ContractError('HTML_RESERVE_WORKING_FORM_FORBIDDEN')
        if (tag == 'meta'
                and str(values.get('http-equiv', '')).lower() == 'refresh'):
            raise ContractError('HTML_RESERVE_FETCHABLE_HTML_FORBIDDEN')
        if tag == 'style':
            self.in_style = True
        if tag == 'link':
            if values.get('rel') == 'stylesheet' and values.get('href') is not None:
                self._add(values['href'])
            elif values.get('rel') == 'canonical' and values.get('href') is not None:
                self._navigation(values['href'])
            elif values.get('href') is not None:
                raise ContractError('HTML_RESERVE_LINK_REL_FORBIDDEN')
        elif tag == 'script':
            if values.get('src') is not None:
                self._add(values['src'])
            elif values.get('type') == 'application/ld+json':
                self.in_json_ld = True
            else:
                raise ContractError('HTML_RESERVE_INLINE_SCRIPT_FORBIDDEN')
        elif tag in ('img', 'source') and values.get('src') is not None:
            self._add(values['src'])
        elif (tag == 'meta' and values.get('property') == 'og:image'
              and values.get('content') is not None):
            self._add(values['content'])
        elif tag == 'meta' and values.get('property') == 'og:url':
            self._navigation(values.get('content'))
        if tag == 'a' and values.get('href') is not None:
            self._navigation(values['href'])
        if 'href' in values and tag not in ('a', 'link'):
            raise ContractError('HTML_RESERVE_FETCHABLE_HTML_FORBIDDEN')
        if 'src' in values and tag not in ('script', 'img', 'source'):
            raise ContractError('HTML_RESERVE_FETCHABLE_HTML_FORBIDDEN')
        if 'style' in values and _CSS_NETWORK.search(values['style'].encode('utf-8')):
            raise ContractError('HTML_RESERVE_INLINE_STYLE_RESOURCE_FORBIDDEN')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_json_ld = False
        if tag == 'style':
            self.in_style = False

    def handle_data(self, data):
        if self.in_style and _CSS_NETWORK.search(data.encode('utf-8')):
            raise ContractError('HTML_RESERVE_INLINE_STYLE_RESOURCE_FORBIDDEN')


def extract_resources(html, *, origin, bare_file_ids, contextual,
                      local_targets=()):
    if type(html) is not bytes or len(html) > MAX_HTML_BYTES:
        raise ContractError('HTML_RESERVE_HTML_SIZE_LIMIT')
    try:
        text = html.decode('utf-8')
    except UnicodeError:
        raise ContractError('HTML_RESERVE_HTML_UTF8_REQUIRED') from None
    parser = _Resources(origin, bare_file_ids, contextual, local_targets)
    try:
        parser.feed(text)
        parser.close()
    except ContractError:
        raise
    except (ValueError, TypeError, UnicodeError):
        raise ContractError('HTML_RESERVE_HTML_INVALID') from None
    return tuple(sorted(parser.items, key=lambda item: (
        item.kind, item.file_id or '', item.page_id or '', item.slot or '',
        item.name or '', item.digest or '')))


def safe_css(body):
    if type(body) is not bytes or _CSS_NETWORK.search(body):
        raise ContractError('HTML_RESERVE_CSS_RESOURCE_FORBIDDEN')
    return body


def safe_javascript(body):
    if type(body) is not bytes or _JS_NETWORK.search(body):
        raise ContractError('HTML_RESERVE_JAVASCRIPT_NETWORK_FORBIDDEN')
    return body


def resource_bytes(reference, snapshot):
    if reference.kind == 'static-public':
        rows = {
            'public.css': (public_views.STYLESHEET, 'text/css; charset=utf-8'),
            'public-gallery.js': (
                public_views.GALLERY_SCRIPT, 'text/javascript; charset=utf-8'),
            'public-home.js': (
                public_views.HOME_SCRIPT, 'text/javascript; charset=utf-8'),
        }
        try:
            body, content_type = rows[reference.name]
        except KeyError:
            raise ContractError('HTML_RESERVE_STATIC_UNKNOWN') from None
    elif reference.kind == 'static-shared':
        try:
            row = shared_public.static_descriptor(reference.name)
        except (OSError, ValueError, TypeError):
            raise ContractError('HTML_RESERVE_SHARED_STATIC_UNAVAILABLE') from None
        if row['digest'] != reference.digest:
            raise ContractError('HTML_RESERVE_SHARED_STATIC_DIGEST_MISMATCH')
        body, content_type = row['body'], row['content_type']
    elif reference.kind in ('media-bare', 'media-contextual'):
        rows = [row for row in snapshot.descriptor.get('files', [])
                if row[0] == reference.file_id]
        if len(rows) != 1:
            raise ContractError('HTML_RESERVE_MEDIA_DESCRIPTOR_MISSING')
        row = rows[0]
        descriptor = {
            'id': row[0], 'asset_id': row[1], 'kind': row[2], 'key': row[3],
            'sha256': row[4], 'byte_size': row[5],
        }
        try:
            stream, content_type = shared_public._open_media(descriptor)
            with stream:
                body = stream.read(row[5] + 1)
        except Exception:
            raise ContractError('HTML_RESERVE_MEDIA_UNAVAILABLE') from None
        if len(body) != row[5]:
            raise ContractError('HTML_RESERVE_MEDIA_SIZE_MISMATCH')
    else:
        raise ContractError('HTML_RESERVE_RESOURCE_KIND_INVALID')
    static_names = {row[0]: row[1:] for row in snapshot.descriptor.get('statics', [])
                    if type(row) is list and len(row) == 3}
    if reference.kind in ('static-public', 'static-shared'):
        expected = static_names.get(reference.name)
        if (expected is None or expected != [hashlib.sha256(body).hexdigest(), len(body)]):
            raise ContractError('HTML_RESERVE_STATIC_SOURCE_CHANGED')
    if reference.name is not None and reference.name.endswith('.css'):
        safe_css(body)
    if reference.name is not None and reference.name.endswith('.js'):
        safe_javascript(body)
    return body, content_type
