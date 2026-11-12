"""Bounded read-only snapshot of dependencies that affect public reserve bytes."""
from dataclasses import dataclass
import hashlib
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from content.models import Page, Route, lock_content
from content.public_gallery import (
    ALBUM_TARGETS, PAGE2_TARGETS, ROOT_TARGET,
)
from content.public_seo import load_configuration
from content.public_shared import HOST_POLICY
from content import public_views
from media_library.models import Asset, AssetFile, AssetUsage
from page_versions import schema as page_schema
from page_versions.models import PageContentState
from shared_content.content import validate_metadata
from shared_content.models import SharedBlock
from shared_content.public import RENDERER_POLICY

from .contracts import ContractError, TargetSpec, canonical_bytes


DEFAULT_MAX_PAGES = 512
DEFAULT_MAX_ROUTES = 512
DEFAULT_MAX_STATES = 512
DEFAULT_MAX_ASSETS = 1024
DEFAULT_MAX_FILES = 1024
DEFAULT_MAX_USAGES = 4096
DEFAULT_MAX_TARGETS = 512


@dataclass(frozen=True)
class SourceSnapshot:
    stamp: str
    descriptor: dict
    targets: tuple[TargetSpec, ...]


def _limit(name, default):
    value = getattr(settings, name, default)
    if type(value) is not int or value < 1:
        raise ContractError('SOURCE_LIMIT_INVALID')
    return value


def _bounded(queryset, limit, code):
    rows = list(queryset[:limit + 1])
    if len(rows) > limit:
        raise ContractError(code)
    return rows


def _add(specs, item):
    previous = specs.get(item.target)
    if previous is not None and previous != item:
        raise ContractError('SOURCE_TARGET_CONFLICT')
    specs[item.target] = item


def _targets_from_rows(pages, routes):
    page_map = {str(page.pk): page for page in pages}
    primary = {}
    for route in routes:
        if route.kind == Route.Kind.PRIMARY:
            key = str(route.page_id)
            if key in primary:
                raise ContractError('SOURCE_PRIMARY_ROUTE_CONFLICT')
            primary[key] = route.target
    specs = {}
    for route in routes:
        page = page_map.get(str(route.page_id))
        if page is None:
            raise ContractError('SOURCE_ROUTE_PAGE_MISSING')
        if route.kind == Route.Kind.REDIRECT:
            location = primary.get(str(route.page_id))
            if location is None or location == route.target:
                raise ContractError('SOURCE_REDIRECT_PRIMARY_MISSING')
            item = TargetSpec(route.target, 301, location)
        elif route.kind in (Route.Kind.PRIMARY, Route.Kind.ALIAS):
            item = TargetSpec(route.target, 200, None)
        else:
            raise ContractError('SOURCE_ROUTE_KIND_INVALID')
        _add(specs, item)
    gallery_roots = [
        route for route in routes
        if route.target == ROOT_TARGET and route.kind == Route.Kind.PRIMARY]
    if gallery_roots:
        if len(gallery_roots) != 1:
            raise ContractError('SOURCE_GALLERY_ROOT_CONFLICT')
        root = gallery_roots[0]
        root_page = page_map[str(root.page_id)]
        if root_page.kind != Page.Kind.GALLERY:
            raise ContractError('SOURCE_GALLERY_ROOT_KIND_INVALID')
        _add(specs, TargetSpec(ROOT_TARGET + '?page=1', 302, ROOT_TARGET))
        route_by_target = {route.target: route for route in routes}
        for album_target in ALBUM_TARGETS:
            album_route = route_by_target.get(album_target)
            if album_route is None or album_route.kind != Route.Kind.PRIMARY:
                continue
            album = page_map.get(str(album_route.page_id))
            if (album is None or not album.is_published
                    or album.kind != Page.Kind.ALBUM
                    or str(album.parent_id) != str(root.page_id)):
                continue
            slug = album_target.removeprefix(ROOT_TARGET)
            _add(specs, TargetSpec(ROOT_TARGET + '?album=' + slug, 200, None))
            if album_target in PAGE2_TARGETS:
                _add(specs, TargetSpec(
                    ROOT_TARGET + '?page=2&album=' + slug, 200, None))
    target_cap = _limit('HTML_RESERVE_MAX_TARGETS', DEFAULT_MAX_TARGETS)
    if len(specs) > target_cap:
        raise ContractError('SOURCE_TARGET_LIMIT')
    return tuple(sorted(specs.values()))


def _capture_rows():
    pages = _bounded(
        Page.objects.order_by('id'),
        _limit('HTML_RESERVE_MAX_PAGES', DEFAULT_MAX_PAGES),
        'SOURCE_PAGE_LIMIT')
    routes = _bounded(
        Route.objects.exclude(kind=Route.Kind.SYSTEM).order_by('target', 'id'),
        _limit('HTML_RESERVE_MAX_ROUTES', DEFAULT_MAX_ROUTES),
        'SOURCE_ROUTE_LIMIT')
    return pages, routes


def capture_targets():
    pages, routes = _capture_rows()
    return _targets_from_rows(pages, routes)


def _static_descriptor():
    shared_root = Path(__file__).resolve().parents[1] / 'shared_content' / 'assets'
    bodies = {
        'public.css': public_views.STYLESHEET,
        'public-gallery.js': public_views.GALLERY_SCRIPT,
        'public-home.js': public_views.HOME_SCRIPT,
        'public-shared.css': (shared_root / 'public-shared.css').read_bytes(),
        'public-shared.js': (shared_root / 'public-shared.js').read_bytes(),
    }
    return [[name, hashlib.sha256(body).hexdigest(), len(body)]
            for name, body in sorted(bodies.items())]


def capture():
    configuration = load_configuration()
    statics = _static_descriptor()
    with transaction.atomic():
        lock_content('default')
        pages, routes = _capture_rows()
        targets = _targets_from_rows(pages, routes)
        states = _bounded(
            PageContentState.objects.select_related('current_revision').order_by('page_id'),
            _limit('HTML_RESERVE_MAX_PAGE_STATES', DEFAULT_MAX_STATES),
            'SOURCE_PAGE_STATE_LIMIT')
        page_ids = {page.pk for page in pages}
        state_rows = []
        for state in states:
            revision = state.current_revision
            if state.page_id not in page_ids or revision.page_id != state.page_id:
                raise ContractError('SOURCE_PAGE_STATE_INCOHERENT')
            page = next(row for row in pages if row.pk == state.page_id)
            try:
                payload = page_schema.validate(revision.payload, page.kind)
                payload_digest = page_schema.digest(payload)
            except (ValidationError, TypeError, ValueError, AttributeError):
                raise ContractError('SOURCE_PAGE_PAYLOAD_INVALID') from None
            if (revision.schema_version != page_schema.SCHEMA
                    or payload_digest != revision.payload_hash):
                raise ContractError('SOURCE_PAGE_PAYLOAD_INCOHERENT')
            state_rows.append([
                str(state.pk), str(state.page_id), state.sequence,
                str(revision.pk), revision.sequence, revision.schema_version,
                revision.payload_hash, payload_digest,
            ])
        blocks = list(SharedBlock.objects.select_related(
            'current_revision').order_by('kind')[:3])
        if [block.kind for block in blocks] != ['footer', 'header']:
            raise ContractError('SOURCE_SHARED_BLOCKS_INCOHERENT')
        shared_rows = []
        for block in blocks:
            revision = block.current_revision
            if revision is None or revision.block_id != block.pk:
                raise ContractError('SOURCE_SHARED_REVISION_INCOHERENT')
            try:
                validate_metadata(revision)
            except (ValueError, TypeError, AttributeError):
                raise ContractError('SOURCE_SHARED_DESCRIPTOR_INVALID') from None
            shared_rows.append([
                str(block.pk), block.kind, block.generation,
                str(revision.pk), revision.sequence, revision.schema_version,
                revision.storage_kind, revision.file_key, revision.byte_size,
                revision.file_sha256, revision.payload_hash,
            ])
        usage_kinds = (
            AssetUsage.Kind.CURRENT_PAGE, AssetUsage.Kind.SHARED_BLOCK)
        usages = _bounded(
            AssetUsage.objects.filter(kind__in=usage_kinds).order_by(
                'kind', 'consumer_id', 'slot', 'asset_id'),
            _limit('HTML_RESERVE_MAX_PUBLIC_USAGES', DEFAULT_MAX_USAGES),
            'SOURCE_PUBLIC_USAGE_LIMIT')
        usage_rows = [[
            str(row.pk), row.kind, str(row.consumer_id), row.slot,
            str(row.asset_id)] for row in usages]
        asset_ids = {row.asset_id for row in usages}
        assets = _bounded(
            Asset.objects.filter(pk__in=asset_ids).order_by('id'),
            _limit('HTML_RESERVE_MAX_PUBLIC_ASSETS', DEFAULT_MAX_ASSETS),
            'SOURCE_PUBLIC_ASSET_LIMIT')
        if {row.pk for row in assets} != asset_ids or any(
                row.status != Asset.Status.READY for row in assets):
            raise ContractError('SOURCE_PUBLIC_ASSET_INCOHERENT')
        asset_rows = [[str(row.pk), row.status, row.is_legacy]
                      for row in assets]
        files = _bounded(
            AssetFile.objects.filter(
                asset_id__in=asset_ids,
                kind__in=(AssetFile.Kind.MAIN, AssetFile.Kind.LEGACY_PUBLIC)
            ).order_by('asset_id', 'id'),
            _limit('HTML_RESERVE_MAX_PUBLIC_ASSET_FILES', DEFAULT_MAX_FILES),
            'SOURCE_PUBLIC_FILE_LIMIT')
        file_rows = [[
            str(row.pk), str(row.asset_id), row.kind, row.key,
            row.sha256, row.byte_size] for row in files]
        descriptor = {
            'schema': 'html-reserve-source-v1',
            'policies': [HOST_POLICY, RENDERER_POLICY],
            'seo': [configuration.origin, configuration.robots_profile],
            'pages': [[
                str(row.pk), None if row.parent_id is None else str(row.parent_id),
                row.position, row.kind, row.name, row.is_published]
                for row in pages],
            'routes': [[
                str(row.pk), row.target, row.kind, str(row.page_id), row.is_legacy]
                for row in routes],
            'states': state_rows,
            'shared': shared_rows,
            'usages': usage_rows,
            'assets': asset_rows,
            'files': file_rows,
            'statics': statics,
        }
        stamp = hashlib.sha256(canonical_bytes(descriptor)).hexdigest()
        return SourceSnapshot(stamp, descriptor, targets)
