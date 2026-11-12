"""One synchronous manual HTML-reserve build; no scheduler or background worker."""
import hashlib
from urllib.parse import urlencode
from uuid import uuid4

from django.utils import timezone

from .activation import activate_prebuilt
from .capture import (
    extract_resources, render_target, resource_bytes, resource_policy,
)
from .contracts import ContractError, response_name
from .source import capture
from .storage import ReserveStore


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
    content_type = response.get('Content-Type', '').split(';')[0].strip()
    if content_type != 'text/html':
        raise ContractError('HTML_RESERVE_RESPONSE_CONTENT_TYPE_INVALID')
    name = response_name(spec.target)
    return {
        'name': name, 'target': spec.target, 'status': spec.status,
        'location': spec.location, 'content_type': 'text/html; charset=utf-8',
        'x_robots_tag': response.get('X-Robots-Tag'),
        'security_policy_id': 'public-v1', 'cache_policy_id': 'reserve-v1',
        'sha256': hashlib.sha256(body).hexdigest(), 'byte_size': len(body),
    }


def run(*, root, capture_source=capture, render=render_target,
        recapture=capture, now=timezone.now):
    source_a = capture_source()
    bare, contextual = resource_policy(source_a)
    origin = source_a.descriptor['seo'][0]
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
                contextual=contextual))
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
    retained = sorted({row[4] for row in source_a.descriptor['usages']})
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
    with ReserveStore(root).locked() as locked:
        locked.bootstrap()
        locked.reconcile_orphans()
        digest = locked.write_generation(generation, manifest, files)
        return activate_prebuilt(
            store=locked, generation_id=generation,
            manifest_sha256=digest, source_snapshot=source_a,
            recapture=recapture)
