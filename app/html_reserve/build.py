"""One synchronous manual HTML-reserve build; no scheduler or background worker."""
import hashlib
import re
from urllib.parse import urlencode
from uuid import uuid4

from django.utils import timezone

from content.public_views import PUBLIC_CSP
from media_library.services import reconcile_retained_html

from .activation import activate_prebuilt
from .capture import (
    extract_resources, render_target, resource_bytes, resource_policy,
)
from .contracts import ContractError, response_name
from .source import capture
from .storage import ReserveStore


_ETAG = re.compile(r'^"[0-9a-f]{64}"$')
_PAGE_HEADERS = frozenset((
    'Content-Type', 'Content-Length', 'Cache-Control', 'ETag',
    'X-Content-Type-Options', 'Content-Security-Policy', 'X-Robots-Tag',
))
_REDIRECT_HEADERS = frozenset(('Content-Type', 'Location', 'Cache-Control'))
MAX_RESOURCES = 1024


def _resource_url(reference):
    if reference.kind == 'static-public':
        return '/static/' + reference.name
    if reference.kind == 'static-shared':
        return '/static/shared/%s/%s' % (reference.digest, reference.name)
    base = '/public-media/%s/' % reference.file_id
    if reference.kind == 'media-bare':
        return base
    if reference.kind == 'media-contextual':
        return base + '?' + urlencode((('page', reference.page_id),
                                        ('slot', reference.slot)))
    raise ContractError('HTML_RESERVE_RESOURCE_KIND_INVALID')


def _resource_name(url, content_type):
    suffixes = {
        'text/css; charset=utf-8': '.css',
        'text/javascript; charset=utf-8': '.js',
        'image/webp': '.webp', 'image/jpeg': '.jpg', 'image/png': '.png',
    }
    try:
        suffix = suffixes[content_type]
    except KeyError:
        raise ContractError('HTML_RESERVE_RESOURCE_CONTENT_TYPE_INVALID') from None
    return hashlib.sha256(url.encode('utf-8')).hexdigest() + suffix


def _response_row(spec, response, body):
    if response.status_code != spec.status:
        raise ContractError('HTML_RESERVE_RESPONSE_STATUS_MISMATCH')
    location = response.get('Location')
    if location != spec.location:
        raise ContractError('HTML_RESERVE_RESPONSE_LOCATION_MISMATCH')
    if response.cookies or response.get('Vary'):
        raise ContractError('HTML_RESERVE_RESPONSE_PRIVATE_STATE')
    cache = response.get('Cache-Control', '').lower()
    if 'private' in cache or 'no-store' in cache:
        raise ContractError('HTML_RESERVE_RESPONSE_PRIVATE_CACHE')
    allowed = _PAGE_HEADERS if spec.status == 200 else _REDIRECT_HEADERS
    if not set(response.headers).issubset(allowed):
        raise ContractError('HTML_RESERVE_RESPONSE_HEADERS_INVALID')
    if response.get('Cache-Control') != 'no-cache':
        raise ContractError('HTML_RESERVE_RESPONSE_CACHE_INVALID')
    robots = response.get('X-Robots-Tag')
    if robots not in (None, 'noindex, follow', 'noindex, nofollow'):
        raise ContractError('HTML_RESERVE_RESPONSE_SECURITY_INVALID')
    if spec.status == 200:
        content_length = response.get('Content-Length')
        etag = response.get('ETag')
        if (response.get('Content-Security-Policy') != PUBLIC_CSP
                or response.get('X-Content-Type-Options') != 'nosniff'
                or (content_length is not None and content_length != str(len(body)))
                or (etag is not None and _ETAG.fullmatch(etag) is None)):
            raise ContractError('HTML_RESERVE_RESPONSE_SECURITY_INVALID')
    elif robots is not None:
        raise ContractError('HTML_RESERVE_RESPONSE_SECURITY_INVALID')
    content_type = response.get('Content-Type', '').split(';')[0].strip()
    if content_type != 'text/html':
        raise ContractError('HTML_RESERVE_RESPONSE_CONTENT_TYPE_INVALID')
    name = response_name(spec.target)
    return {
        'name': name, 'target': spec.target, 'status': spec.status,
        'location': spec.location, 'content_type': 'text/html; charset=utf-8',
        'x_robots_tag': robots,
        'security_policy_id': 'public-v1', 'cache_policy_id': 'reserve-v1',
        'sha256': hashlib.sha256(body).hexdigest(), 'byte_size': len(body),
    }


def run(*, root, capture_source=capture, render=render_target,
        recapture=capture, now=timezone.now):
    with ReserveStore(root).locked() as locked:
        locked.bootstrap()
        locked.reconcile_orphans()
        pointer = locked.read_pointer()
        reconcile_retained_html(active_generation_ids=[
            generation for generation in (
                pointer['current'], pointer['previous'])
            if generation is not None
        ])
        source_a = capture_source()
        bare, contextual = resource_policy(source_a)
        origin = source_a.descriptor['seo'][0]
        local_targets = frozenset(spec.target for spec in source_a.targets)
        generation = str(uuid4())
        files, responses, references = {}, [], set()
        for spec in source_a.targets:
            response = render(spec.target)
            body = bytes(response.content)
            row = _response_row(spec, response, body)
            responses.append(row)
            files['responses/' + row['name']] = body
            if spec.status == 200:
                references.update(extract_resources(
                    body, origin=origin, bare_file_ids=bare,
                    contextual=contextual, local_targets=local_targets))
                if len(references) > MAX_RESOURCES:
                    raise ContractError('HTML_RESERVE_RESOURCE_LIMIT')
        resources = []
        for reference in sorted(references, key=repr):
            body, content_type = resource_bytes(reference, source_a)
            url = _resource_url(reference)
            name = _resource_name(url, content_type)
            files['resources/' + name] = body
            resources.append({
                'name': name, 'url': url, 'content_type': content_type,
                'sha256': hashlib.sha256(body).hexdigest(),
                'byte_size': len(body),
            })
        file_to_asset = {row[0]: row[1]
                         for row in source_a.descriptor.get('files', [])}
        retained = sorted({file_to_asset[reference.file_id]
                           for reference in references
                           if reference.kind in ('media-bare', 'media-contextual')})
        manifest = {
            'schema': 'html-reserve-manifest-v1', 'generation': generation,
            'built_at': now().isoformat().replace('+00:00', 'Z'),
            'source_stamp': source_a.stamp,
            'responses': sorted(responses, key=lambda row: row['target']),
            'resources': sorted(resources, key=lambda row: row['url']),
            'retained_asset_ids': retained,
            'totals': {'files': len(files),
                       'bytes': sum(len(body) for body in files.values())},
        }
        digest = locked.write_generation(generation, manifest, files)
        return activate_prebuilt(
            store=locked, generation_id=generation,
            manifest_sha256=digest, source_snapshot=source_a,
            recapture=recapture)
