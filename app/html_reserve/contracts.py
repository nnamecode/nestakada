"""Pure, closed contracts for the manual HTML reserve."""
from dataclasses import dataclass
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit
from uuid import UUID

from django.core.exceptions import ValidationError

from content.validators import exact_target


ACTIVE_SCHEMA = 'html-reserve-active-v1'
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
_HEX = re.compile(r'^[0-9a-f]{64}\Z')
_SHARED = re.compile(
    r'^/static/shared/([0-9a-f]{64})/(public-shared\.(?:css|js))\Z')
_MEDIA = re.compile(
    r'^/public-media/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
    r'[0-9a-f]{4}-[0-9a-f]{12})/\Z')
_STATIC = frozenset((
    '/static/public.css',
    '/static/public-gallery.js',
    '/static/public-home.js',
))


class ContractError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class TargetSpec:
    target: str
    status: int
    location: str | None = None


@dataclass(frozen=True)
class ResourceRef:
    kind: str
    file_id: str | None
    page_id: str | None
    slot: str | None
    name: str | None
    digest: str | None


def _json_value(value):
    if value is None or type(value) in (bool, int):
        return
    if type(value) is str:
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ContractError('HTML_RESERVE_JSON_CONTROL_CHARACTER')
        return
    if type(value) is list:
        for item in value:
            _json_value(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ContractError('HTML_RESERVE_JSON_KEY_REQUIRED')
            _json_value(key)
            _json_value(item)
        return
    raise ContractError('HTML_RESERVE_JSON_TYPE_FORBIDDEN')


def canonical_bytes(value, *, max_bytes=MAX_MANIFEST_BYTES):
    if type(max_bytes) is not int or max_bytes < 1:
        raise ContractError('HTML_RESERVE_JSON_LIMIT_INVALID')
    _json_value(value)
    body = json.dumps(
        value, ensure_ascii=True, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('ascii')
    if len(body) > max_bytes:
        raise ContractError('HTML_RESERVE_JSON_SIZE_LIMIT')
    return body


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _uuid(value):
    if value is None:
        return None
    try:
        parsed = UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ContractError('HTML_RESERVE_UUID_INVALID') from None
    if str(parsed) != str(value):
        raise ContractError('HTML_RESERVE_UUID_NONCANONICAL')
    return str(parsed)


def _sha(value):
    if value is None:
        return None
    if type(value) is not str or _HEX.fullmatch(value) is None:
        raise ContractError('HTML_RESERVE_SHA256_INVALID')
    return value


def active_pointer(current, previous, current_manifest_sha256,
                   previous_manifest_sha256):
    current, previous = _uuid(current), _uuid(previous)
    current_sha, previous_sha = (
        _sha(current_manifest_sha256), _sha(previous_manifest_sha256))
    if (current is None) != (current_sha is None):
        raise ContractError('HTML_RESERVE_CURRENT_POINTER_INCOHERENT')
    if previous is not None and current is None:
        raise ContractError('HTML_RESERVE_PREVIOUS_WITHOUT_CURRENT')
    if (previous is None) != (previous_sha is None):
        raise ContractError('HTML_RESERVE_PREVIOUS_POINTER_INCOHERENT')
    if current is not None and current == previous:
        raise ContractError('HTML_RESERVE_POINTER_GENERATIONS_MUST_DIFFER')
    return {
        'schema': ACTIVE_SCHEMA,
        'current': current,
        'previous': previous,
        'current_manifest_sha256': current_sha,
        'previous_manifest_sha256': previous_sha,
    }


def response_name(target):
    try:
        exact_target(target)
    except ValidationError:
        raise ContractError('HTML_RESERVE_TARGET_INVALID') from None
    return hashlib.sha256(target.encode('utf-8')).hexdigest() + '.html'


def _canonical_uuid(value, code):
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ContractError(code) from None
    if str(parsed) != value:
        raise ContractError(code)
    return value


def parse_resource_url(url, *, bare_file_ids, contextual):
    if (type(url) is not str or not url.startswith('/')
            or url.startswith('//') or any(ord(c) < 33 or ord(c) == 127 for c in url)):
        raise ContractError('HTML_RESERVE_RESOURCE_URL_INVALID')
    if url in _STATIC:
        return ResourceRef('static-public', None, None, None,
                           url.removeprefix('/static/'), None)
    match = _SHARED.fullmatch(url)
    if match is not None:
        return ResourceRef(
            'static-shared', None, None, None, match.group(2), match.group(1))
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or parts.fragment:
        raise ContractError('HTML_RESERVE_RESOURCE_URL_INVALID')
    media = _MEDIA.fullmatch(parts.path)
    if media is None:
        raise ContractError('HTML_RESERVE_RESOURCE_NOT_ALLOWED')
    file_id = _canonical_uuid(media.group(1), 'HTML_RESERVE_MEDIA_ID_INVALID')
    if not parts.query:
        if file_id not in set(bare_file_ids):
            raise ContractError('HTML_RESERVE_BARE_MEDIA_NOT_PUBLIC')
        return ResourceRef('media-bare', file_id, None, None, None, None)
    try:
        values = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        raise ContractError('HTML_RESERVE_MEDIA_QUERY_INVALID') from None
    if [key for key, _value in values] != ['page', 'slot']:
        raise ContractError('HTML_RESERVE_MEDIA_QUERY_INVALID')
    if urlencode(values) != parts.query:
        raise ContractError('HTML_RESERVE_MEDIA_QUERY_NONCANONICAL')
    page_id = _canonical_uuid(values[0][1], 'HTML_RESERVE_PAGE_ID_INVALID')
    slot = values[1][1]
    if (file_id, page_id, slot) not in set(contextual):
        raise ContractError('HTML_RESERVE_CONTEXTUAL_MEDIA_NOT_PUBLIC')
    return ResourceRef(
        'media-contextual', file_id, page_id, slot, None, None)
