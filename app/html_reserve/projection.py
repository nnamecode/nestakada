"""Pure, bounded data-map projection for the vanilla Nginx reserve."""
import hashlib
import re
from uuid import UUID

from django.core.exceptions import ValidationError

from content.validators import exact_target

from .contracts import ContractError, response_name


SCHEMA = 'html-reserve-projection-v1'
MAX_MAP_BYTES = 2 * 1024 * 1024
MAX_FILES = 4096
MAX_RESOURCES = 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
_HEX = re.compile(r'^[0-9a-f]{64}\Z')
_RESOURCE_TYPES = {
    'text/css; charset=utf-8': '.css',
    'text/javascript; charset=utf-8': '.js',
    'image/webp': '.webp',
    'image/jpeg': '.jpg',
    'image/png': '.png',
}
_MANIFEST_KEYS = {
    'schema', 'generation', 'built_at', 'source_stamp', 'responses',
    'resources', 'retained_asset_ids', 'totals',
}
_RESPONSE_KEYS = {
    'name', 'target', 'status', 'location', 'content_type',
    'x_robots_tag', 'security_policy_id', 'cache_policy_id', 'sha256',
    'byte_size',
}
_RESOURCE_KEYS = {'name', 'url', 'content_type', 'sha256', 'byte_size'}


def _uuid(value):
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ContractError('HTML_RESERVE_PROJECTION_UUID_INVALID') from None
    if str(parsed) != value:
        raise ContractError('HTML_RESERVE_PROJECTION_UUID_INVALID')
    return value


def _sha(value):
    return type(value) is str and _HEX.fullmatch(value) is not None


def _size(value):
    return type(value) is int and 0 <= value <= MAX_FILE_BYTES


def _target(value, code='HTML_RESERVE_PROJECTION_TARGET_INVALID'):
    try:
        exact_target(value)
    except ValidationError:
        raise ContractError(code) from None
    return value


def _quote(value):
    if type(value) is not str or any(
            ord(char) < 32 or ord(char) == 127 for char in value):
        raise ContractError('HTML_RESERVE_PROJECTION_VALUE_INVALID')
    return '"' + value.replace('\\', '\\\\').replace(
        '"', '\\"').replace('$', '\\$') + '"'


def _response(row):
    if type(row) is not dict or set(row) != _RESPONSE_KEYS:
        raise ContractError('HTML_RESERVE_PROJECTION_METADATA_INVALID')
    try:
        target = _target(row['target'])
        expected_name = response_name(target)
    except ContractError:
        raise ContractError('HTML_RESERVE_PROJECTION_TARGET_INVALID') from None
    status, location = row['status'], row['location']
    if status in (301, 302):
        if type(location) is not str:
            raise ContractError('HTML_RESERVE_PROJECTION_METADATA_INVALID')
        try:
            _target(location, 'HTML_RESERVE_PROJECTION_METADATA_INVALID')
        except ContractError:
            raise ContractError('HTML_RESERVE_PROJECTION_METADATA_INVALID') from None
    elif location is not None:
        raise ContractError('HTML_RESERVE_PROJECTION_METADATA_INVALID')
    if (row['name'] != expected_name
            or status not in (200, 301, 302, 404)
            or row['content_type'] != 'text/html; charset=utf-8'
            or row['x_robots_tag'] not in (
                None, 'noindex, follow', 'noindex, nofollow')
            or row['security_policy_id'] != 'public-v1'
            or row['cache_policy_id'] != 'reserve-v1'
            or not _sha(row['sha256']) or not _size(row['byte_size'])):
        raise ContractError('HTML_RESERVE_PROJECTION_METADATA_INVALID')
    return {
        'uri': target, 'kind': 'response', 'leaf': row['name'],
        'status': str(status), 'location': location or '',
        'content_type': row['content_type'],
        'robots': row['x_robots_tag'] or '', 'sha256': row['sha256'],
        'cache_class': 'response',
    }


def _resource(row):
    if type(row) is not dict or set(row) != _RESOURCE_KEYS:
        raise ContractError('HTML_RESERVE_PROJECTION_METADATA_INVALID')
    try:
        url = _target(row['url'], 'HTML_RESERVE_PROJECTION_METADATA_INVALID')
    except ContractError:
        raise ContractError('HTML_RESERVE_PROJECTION_METADATA_INVALID') from None
    suffix = _RESOURCE_TYPES.get(row['content_type'])
    expected_name = (hashlib.sha256(url.encode('utf-8')).hexdigest() + suffix
                     if suffix is not None else None)
    if (row['name'] != expected_name or not _sha(row['sha256'])
            or not _size(row['byte_size'])):
        raise ContractError('HTML_RESERVE_PROJECTION_METADATA_INVALID')
    cache_class = ('immutable' if url.startswith('/static/shared/')
                   else 'resource-no-cache')
    return {
        'uri': url, 'kind': 'resource', 'leaf': row['name'], 'status': '200',
        'location': '', 'content_type': row['content_type'], 'robots': '',
        'sha256': row['sha256'], 'cache_class': cache_class,
    }


def _map(variable, values, field):
    lines = [f'map $request_uri ${variable} {{', '    default "";']
    for row in values:
        lines.append(f'    {_quote(row["uri"])} {_quote(row[field])};')
    lines.append('}')
    return '\n'.join(lines)


def emit_maps(manifest, delivery_uuid, *, max_bytes=MAX_MAP_BYTES):
    """Return deterministic map-only Nginx data for one verified generation."""
    if type(max_bytes) is not int or max_bytes < 1 or max_bytes > MAX_MAP_BYTES:
        raise ContractError('HTML_RESERVE_PROJECTION_LIMIT_INVALID')
    delivery_uuid = _uuid(delivery_uuid)
    if (type(manifest) is not dict or set(manifest) != _MANIFEST_KEYS
            or manifest.get('schema') != 'html-reserve-manifest-v1'
            or type(manifest.get('responses')) is not list
            or type(manifest.get('resources')) is not list):
        raise ContractError('HTML_RESERVE_PROJECTION_MANIFEST_INVALID')
    _uuid(manifest.get('generation'))
    if (len(manifest['resources']) > MAX_RESOURCES
            or len(manifest['responses']) + len(manifest['resources']) > MAX_FILES):
        raise ContractError('HTML_RESERVE_PROJECTION_MANIFEST_INVALID')
    rows = [_response(row) for row in manifest['responses']]
    rows.extend(_resource(row) for row in manifest['resources'])
    rows.sort(key=lambda row: row['uri'])
    uris = [row['uri'] for row in rows]
    if len(uris) != len(set(uris)):
        raise ContractError('HTML_RESERVE_PROJECTION_URI_DUPLICATE')
    for row in rows:
        row['release'] = delivery_uuid
    fields = (
        ('reserve_kind', 'kind'), ('reserve_release', 'release'),
        ('reserve_leaf', 'leaf'), ('reserve_status', 'status'),
        ('reserve_location', 'location'),
        ('reserve_content_type', 'content_type'),
        ('reserve_robots', 'robots'), ('reserve_sha256', 'sha256'),
        ('reserve_cache_class', 'cache_class'),
    )
    chunks = [f'# {SCHEMA} {delivery_uuid}']
    chunks.extend(_map(variable, rows, field) for variable, field in fields)
    body = ('\n\n'.join(chunks) + '\n').encode('utf-8')
    if len(body) > max_bytes:
        raise ContractError('HTML_RESERVE_PROJECTION_MAP_LIMIT')
    return body
