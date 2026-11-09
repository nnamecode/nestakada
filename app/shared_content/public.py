"""Optimistic read-only public composition; production host policy stays outside."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from uuid import UUID
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from content.models import lock_content
from media_library.models import Asset, AssetFile, AssetUsage
from media_library.storage import MediaStorage
from page_versions import schema as page_schema
from page_versions.models import PageContentState
from .models import SharedBlock, SharedRevision
from .content import descriptor_for, content_html
from .services import digest
from .faults import SharedFault
from .public_markup import hydrate, parse_component, navigation_html, local_url

RENDERER_POLICY = 'shared-public-v1'
STATIC_TYPES = {'public-shared.css': 'text/css; charset=utf-8',
                'public-shared.js': 'text/javascript; charset=utf-8'}


def _canonical_uuid(value):
    try:
        return type(value) is str and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


@dataclass(frozen=True)
class NavItem:
    label: str
    url: str
    current: bool = False


@dataclass(frozen=True)
class HostMediaFile:
    id: str
    asset_id: str
    kind: str
    key: str
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class HostContext:
    stamp: str
    navigation: tuple[NavItem, ...]
    media: tuple[HostMediaFile, ...] = ()


@dataclass(frozen=True)
class RenderedShared:
    header_html: str
    footer_html: str
    etag: str
    fingerprint: str


def _read_boundary(phase):
    """Fixed local test seam, never selected by HTTP or editor content."""


def unavailable():
    return SharedFault('SHARED_PUBLIC_UNAVAILABLE', 503)


def static_descriptor(name):
    if name not in STATIC_TYPES:
        raise ValueError('SHARED_PUBLIC_STATIC_UNKNOWN')
    if connection.in_atomic_block:
        raise unavailable()
    body = (Path(__file__).parent / 'assets' / name).read_bytes()
    return {'name': name, 'digest': hashlib.sha256(body).hexdigest(),
            'content_type': STATIC_TYPES[name], 'body': body}


def _file(row):
    return {'id': str(row.pk), 'assetId': str(row.asset_id), 'kind': row.kind,
            'key': row.key, 'sha256': row.sha256, 'byte_size': row.byte_size}


def _component(row, block):
    if row is None or row.schema_version != block.kind + '-v1':
        raise unavailable()
    usages = list(AssetUsage.objects.filter(kind='shared_block', consumer_id=row.pk)
                  .select_related('asset').order_by('slot', 'asset_id')[:6])
    if len(usages) != (4 if block.kind == 'header' else 1):
        raise unavailable()
    assets = []
    for usage in usages:
        if usage.asset.status != Asset.Status.READY:
            raise unavailable()
        files = list(AssetFile.objects.filter(asset_id=usage.asset_id,
                     kind__in=[AssetFile.Kind.MAIN, AssetFile.Kind.LEGACY_PUBLIC]).order_by('id')[:2])
        if len(files) != 1:
            raise unavailable()
        assets.append({'slot': usage.slot, 'assetId': str(usage.asset_id), 'file': _file(files[0])})
    return {'id': str(row.pk), 'blockId': str(block.pk), 'kind': block.kind,
            'generation': block.generation, 'schema': row.schema_version,
            'descriptor': descriptor_for(row), 'payloadHash': row.payload_hash, 'assets': assets}


def _capture(capture_host):
    if not connection.in_atomic_block:
        raise unavailable()
    lock_content('default')
    host = capture_host()
    if (type(host) is not HostContext or type(host.stamp) is not str
            or re.fullmatch('[0-9a-f]{64}', host.stamp) is None or type(host.navigation) is not tuple
            or any(type(item) is not NavItem or type(item.label) is not str or type(item.url) is not str
                   or type(item.current) is not bool
                   for item in host.navigation)
            or type(host.media) is not tuple
            or any(type(item) is not HostMediaFile
                   or not _canonical_uuid(item.id)
                   or not _canonical_uuid(item.asset_id)
                   or item.kind not in (AssetFile.Kind.MAIN, AssetFile.Kind.LEGACY_PUBLIC)
                   or type(item.key) is not str
                   or re.fullmatch('[0-9a-f]{64}', item.sha256) is None
                   or type(item.byte_size) is not int or item.byte_size < 0
                   for item in host.media)
            or len({item.id for item in host.media}) != len(host.media)):
        raise unavailable()
    blocks = list(SharedBlock.objects.select_related('current_revision').order_by('kind'))
    if [block.kind for block in blocks] != ['footer', 'header']:
        raise unavailable()
    pair = [_component(block.current_revision, block) for block in blocks]
    projection = {'host': {'stamp': host.stamp,
                  'navigation': [[item.label, item.url, item.current] for item in host.navigation],
                  'media': [[item.id, item.asset_id, item.kind, item.key,
                             item.sha256, item.byte_size] for item in host.media]},
                  'pair': pair}
    return projection, host, digest(projection)


def _open_media(file):
    if connection.in_atomic_block:
        raise unavailable()
    source = MediaStorage().open_verified(file['key'], {'sha256': file['sha256'], 'byte_size': file['byte_size']})
    try:
        prefix = source.read(12); source.seek(0)
        if file['kind'] == AssetFile.Kind.MAIN:
            mime = ('image/webp' if prefix[:4] == b'RIFF'
                    and prefix[8:12] == b'WEBP' else None)
        elif file['kind'] == AssetFile.Kind.LEGACY_PUBLIC:
            mime = ('image/jpeg' if prefix.startswith(b'\xff\xd8\xff')
                    else 'image/png' if prefix.startswith(b'\x89PNG\r\n\x1a\n')
                    else None)
        else:
            mime = None
        if mime is None:
            raise unavailable()
        return source, mime
    except BaseException:
        source.close()
        raise


def render_shared(*, capture_host, media_url, static_url):
    """Callbacks are trusted configured host code, never names from a request.

    The host owns correspondence of stamp and its body, and must not fetch a
    different mutable body after this function's final coherent capture.
    """
    if connection.in_atomic_block:
        raise unavailable()
    try:
        for attempt in range(2):
            statics = [static_descriptor(name) for name in STATIC_TYPES]
            with transaction.atomic():
                snapshot, host, stamp = _capture(capture_host)
            _read_boundary('captured')
            error, output, urls = None, {}, {}
            try:
                navigation_html(host.navigation)
                for item in host.media:
                    stream, _ = _open_media({
                        'id': item.id, 'assetId': item.asset_id,
                        'kind': item.kind, 'key': item.key,
                        'sha256': item.sha256, 'byte_size': item.byte_size})
                    stream.close()
                for component in snapshot['pair']:
                    source = content_html(component['descriptor'])
                    _, checked = parse_component(source, component['kind'])
                    actual = sorted((binding['slot'], binding['assetId']) for binding in checked['bindings'])
                    expected = sorted((item['slot'], item['assetId']) for item in component['assets'])
                    if actual != expected or checked['payloadHash'] != component['payloadHash']:
                        raise unavailable()
                    media_urls = {}
                    for item in component['assets']:
                        file = item['file']
                        stream, _ = _open_media(file)
                        stream.close()
                        url = local_url(media_url(UUID(file['id'])))
                        media_urls[item['assetId']] = url
                        urls[file['id']] = url
                    output[component['kind']] = hydrate(source, component['kind'], host.navigation, media_urls)
                static_urls = {item['name']: local_url(static_url(item['name'], item['digest'])) for item in statics}
                _read_boundary('files_read')
            except Exception as exc:
                error = exc
            _read_boundary('before_recheck')
            current_statics = [static_descriptor(name) for name in STATIC_TYPES]
            with transaction.atomic():
                _, _, current_stamp = _capture(capture_host)
            changed = current_stamp != stamp or [(x['name'], x['digest']) for x in current_statics] != [(x['name'], x['digest']) for x in statics]
            _read_boundary('rechecked')
            if changed:
                if attempt == 0:
                    continue
                raise unavailable()
            if error is not None:
                raise unavailable() from None
            fingerprint = digest({'snapshot': snapshot, 'policy': RENDERER_POLICY,
                'emittedHeader': output['header'], 'emittedFooter': output['footer'],
                'mediaUrls': urls, 'staticUrls': static_urls,
                'static': [[item['name'], item['digest']] for item in statics]})
            return RenderedShared(output['header'], output['footer'], '"' + fingerprint + '"', fingerprint)
    except Exception:
        raise unavailable() from None
    raise unavailable()


def _page_media_consumer(file, page_id, slot):
    state = (PageContentState.objects.select_related('page', 'current_revision')
             .filter(page_id=page_id, page__is_published=True).first())
    if (state is None or state.current_revision.page_id != state.page_id
            or not slot.startswith('embedded:')):
        return None
    revision = state.current_revision
    try:
        payload = page_schema.validate(revision.payload, state.page.kind)
    except (ValidationError, TypeError, ValueError, AttributeError):
        return None
    if (revision.schema_version != page_schema.SCHEMA
            or page_schema.digest(payload) != revision.payload_hash):
        return None
    image_id = slot[len('embedded:'):]
    images = [item for item in payload['embedded_images'] if item['id'] == image_id]
    if len(images) != 1 or images[0]['asset_id'] != str(file.asset_id):
        return None
    if not any(node['kind'] == 'image' and node['image_id'] == image_id
               for node in payload['layout']):
        return None
    if not AssetUsage.objects.filter(
            kind=AssetUsage.Kind.CURRENT_PAGE, consumer_id=state.page_id,
            slot=slot, asset_id=file.asset_id).exists():
        return None
    return {'pageId': str(state.page_id), 'revisionId': str(revision.pk),
            'payloadHash': revision.payload_hash, 'slot': slot,
            'assetId': str(file.asset_id)}


def _capture_media(file_id, page_id=None, slot=None):
    if not connection.in_atomic_block:
        raise unavailable()
    lock_content('default')
    file = AssetFile.objects.select_related('asset').filter(pk=file_id,
        kind__in=[AssetFile.Kind.MAIN, AssetFile.Kind.LEGACY_PUBLIC], asset__status=Asset.Status.READY).first()
    if file is None:
        return None
    variants = list(AssetFile.objects.filter(asset_id=file.asset_id,
        kind__in=[AssetFile.Kind.MAIN, AssetFile.Kind.LEGACY_PUBLIC]).values_list('id', flat=True)[:2])
    if variants != [file.pk]:
        return None
    if ((file.asset.is_legacy and file.kind != AssetFile.Kind.LEGACY_PUBLIC)
            or (not file.asset.is_legacy and file.kind != AssetFile.Kind.MAIN)):
        return None
    if (page_id is None) != (slot is None):
        return None
    if page_id is not None:
        consumer = _page_media_consumer(file, page_id, slot)
        return None if consumer is None else {'file': _file(file), 'page': consumer}
    consumers = []
    for block in SharedBlock.objects.select_related('current_revision').order_by('kind'):
        row = block.current_revision
        if row is None or row.schema_version != block.kind + '-v1':
            continue
        slots = list(AssetUsage.objects.filter(kind='shared_block', consumer_id=row.pk,
                     asset_id=file.asset_id).order_by('slot').values_list('slot', flat=True)[:5])
        if slots:
            consumers.append({'id': str(row.pk), 'blockId': str(block.pk), 'kind': block.kind,
                'descriptor': descriptor_for(row), 'slots': slots})
    if not consumers:
        return None
    return {'file': _file(file), 'consumers': consumers}


def _verify_media_consumers(snapshot):
    if 'page' in snapshot:
        return True
    asset_id = snapshot['file']['assetId']
    for consumer in snapshot['consumers']:
        source = content_html(consumer['descriptor'])
        _, checked = parse_component(source, consumer['kind'])
        if any(binding['assetId'] == asset_id and binding['slot'] in consumer['slots'] for binding in checked['bindings']):
            return True
    return False
