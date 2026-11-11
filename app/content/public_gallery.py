"""Bounded read-only gallery projection on the existing public lifecycle."""
from dataclasses import dataclass
import re
from types import MappingProxyType
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.db import connection

from media_library.models import Asset, AssetFile, AssetUsage
from page_editor.clean import restricted_clean
from page_versions import schema
from page_versions.models import PageContentState

from .models import Page, Route
from .public_read import PublicNotFound, PublicPage, PublicUnavailable


ROOT_TARGET = '/gallery-of-works/'
PAGE2_TARGET = '/gallery-of-works/?page=2'
ALBUM_TARGETS = (
    '/gallery-of-works/nissan-murano-kuzovnoj-remont',
    '/gallery-of-works/volkswagen-passat-kuzovnoj-remont',
    '/gallery-of-works/volvo-xc60-kuzovnoj-remont',
    '/gallery-of-works/shumoizolyacziya-salona-audi-a5',
    '/gallery-of-works/kuzovnoj-remont-hyundai-solaris',
    '/gallery-of-works/ssangyong-rexton-kuzovnoj-remont',
    '/gallery-of-works/chrysler-kuzovnoj-remont',
    '/gallery-of-works/mitsubishi-pereborka-dvs',
    '/gallery-of-works/kuzovnyie-rabotyi-scoda-fabia',
    '/gallery-of-works/kuzovnyie-rabotyi-kia',
    '/gallery-of-works/kuzovnyie-rabotyi-scoda-octavia',
    '/gallery-of-works/audi-a8-kuzovnoj-remont',
    '/gallery-of-works/kuzovnoj-remont-bentli',
    '/gallery-of-works/zamena-czepi-toyota-camry',
    '/gallery-of-works/kuzovnyie-rabotyi-hyundai',
    '/gallery-of-works/kuzovnyie-rabotyi-mitsubishi',
    '/gallery-of-works/ford-mondeo',
)
PAGE2_TARGETS = ALBUM_TARGETS[10:]
MAX_ALBUMS = 17
MAX_PHOTOS_PER_ALBUM = 32
MAX_PROJECTED_FILES = 49
_ALBUM_QUERY = re.compile(r'\?album=([a-z0-9-]+)\Z')
_PAGE2_ALBUM_QUERY = re.compile(r'\?page=2&album=([a-z0-9-]+)\Z')


@dataclass(frozen=True)
class GalleryRequest:
    base_target: str
    page: int
    selected_target: str | None


@dataclass(frozen=True)
class GalleryPhoto:
    image_id: str
    asset_id: str
    file_id: str
    src: str
    alt: str
    alignment: str
    width_px: int | None
    height_px: int | None


@dataclass(frozen=True)
class GalleryAlbum:
    page_id: str
    revision_id: str
    name: str
    target: str
    modal_target: str
    position: int
    h1: str
    main_text: str
    photos: tuple[GalleryPhoto, ...]


@dataclass(frozen=True)
class GalleryProjection:
    request: GalleryRequest
    albums: tuple[GalleryAlbum, ...]
    selected: GalleryAlbum | None
    files: MappingProxyType
    stamp_data: tuple


def parse_gallery_target(target):
    if target == ROOT_TARGET:
        return GalleryRequest(ROOT_TARGET, 1, None)
    if target == PAGE2_TARGET:
        return GalleryRequest(PAGE2_TARGET, 2, None)
    if type(target) is not str or not target.startswith(ROOT_TARGET + '?'):
        return None
    suffix = target[len(ROOT_TARGET):]
    match = _ALBUM_QUERY.fullmatch(suffix)
    if match is not None:
        selected = ROOT_TARGET + match.group(1)
        if selected not in ALBUM_TARGETS:
            raise PublicNotFound()
        return GalleryRequest(ROOT_TARGET, 1, selected)
    match = _PAGE2_ALBUM_QUERY.fullmatch(suffix)
    if match is not None:
        selected = ROOT_TARGET + match.group(1)
        if selected not in PAGE2_TARGETS:
            raise PublicNotFound()
        return GalleryRequest(PAGE2_TARGET, 2, selected)
    raise PublicNotFound()


def page1_redirect_target(target):
    return ROOT_TARGET if target == ROOT_TARGET + '?page=1' else None


def _validated_payload(state, page):
    if state is None or state.current_revision.page_id != page.pk:
        raise PublicUnavailable()
    revision = state.current_revision
    try:
        payload = schema.validate(revision.payload, page.kind)
        if (revision.schema_version != schema.SCHEMA
                or schema.digest(payload) != revision.payload_hash
                or restricted_clean(payload['intro_text']) != payload['intro_text']
                or restricted_clean(payload['main_text']) != payload['main_text']):
            raise PublicUnavailable()
    except PublicUnavailable:
        raise
    except (ValidationError, TypeError, ValueError, UnicodeError,
            RecursionError, AttributeError):
        raise PublicUnavailable() from None
    return revision, payload


def _album_rows(root_id):
    children = list(Page.objects.filter(parent_id=root_id).order_by(
        'position', 'id')[:MAX_ALBUMS + 1])
    if (len(children) != MAX_ALBUMS
            or [page.position for page in children] != list(range(MAX_ALBUMS))
            or any(page.kind != Page.Kind.ALBUM for page in children)):
        raise PublicUnavailable()
    routes = list(Route.objects.filter(
        page_id__in=[page.pk for page in children], kind=Route.Kind.PRIMARY
    ).order_by('page_id', 'id')[:MAX_ALBUMS + 1])
    by_page = {}
    for route in routes:
        if route.page_id in by_page:
            raise PublicUnavailable()
        by_page[route.page_id] = route
    for page, target in zip(children, ALBUM_TARGETS, strict=True):
        route = by_page.get(page.pk)
        if route is None or route.target != target:
            raise PublicUnavailable()
    return children, by_page


def _photo_specs(payload):
    images = {item['id']: item for item in payload['embedded_images']}
    layout = payload['layout']
    nodes = layout[2:]
    if (len(layout) != len(images) + 2
            or [node.get('kind') for node in layout[:2]] != ['text', 'text']
            or [node.get('field') for node in layout[:2]]
            != ['intro_text', 'main_text']
            or any(node.get('protected_nodes') != [] for node in layout[:2])
            or any(node.get('kind') != 'image' for node in nodes)
            or not 1 <= len(nodes) <= MAX_PHOTOS_PER_ALBUM
            or len(images) != len(nodes)
            or payload['main_image'] is not None
            or payload['preview_image'] is not None):
        raise PublicUnavailable()
    specs = []
    for node in nodes:
        image = images.get(node['image_id'])
        if image is None:
            raise PublicUnavailable()
        specs.append(image)
    if len({item['id'] for item in specs}) != len(specs):
        raise PublicUnavailable()
    return specs


def project_gallery(root, request):
    """Build one exact root/page2/modal DTO inside shared renderer capture."""
    if (not connection.in_atomic_block or not isinstance(root, PublicPage)
            or not isinstance(request, GalleryRequest)
            or root.page_kind != Page.Kind.GALLERY
            or root.target != request.base_target):
        raise PublicUnavailable()
    children, routes = _album_rows(root.page_id)
    visible = [page for page in children if page.is_published]
    states = list(PageContentState.objects.select_related('current_revision').filter(
        page_id__in=[page.pk for page in visible]).order_by('page_id'))
    states_by_page = {state.page_id: state for state in states}
    if len(states_by_page) != len(visible):
        raise PublicUnavailable()
    provisional = []
    wanted_slots = {}
    for page in visible:
        revision, payload = _validated_payload(states_by_page.get(page.pk), page)
        specs = _photo_specs(payload)
        page_slots = {'embedded:' + item['id']: item['asset_id'] for item in specs}
        wanted_slots[page.pk] = page_slots
        provisional.append((page, routes[page.pk], revision, payload, specs))
    usage_rows = list(AssetUsage.objects.select_related('asset').filter(
        kind=AssetUsage.Kind.CURRENT_PAGE,
        consumer_id__in=[page.pk for page in visible]
    ).order_by('consumer_id', 'slot')[:MAX_ALBUMS * MAX_PHOTOS_PER_ALBUM + 1])
    usages = {}
    for usage in usage_rows:
        key = (usage.consumer_id, usage.slot)
        if key in usages:
            raise PublicUnavailable()
        usages[key] = usage
    wanted_assets = set()
    for page in visible:
        expected = wanted_slots[page.pk]
        actual = {slot: row for (consumer, slot), row in usages.items()
                  if consumer == page.pk}
        if set(actual) != set(expected):
            raise PublicUnavailable()
        for slot, asset_id in expected.items():
            usage = actual[slot]
            if (str(usage.asset_id) != asset_id
                    or usage.asset.status != Asset.Status.READY
                    or usage.asset.is_legacy is not True):
                raise PublicUnavailable()
            wanted_assets.add(usage.asset_id)
    file_rows = list(AssetFile.objects.filter(
        asset_id__in=wanted_assets,
        kind__in=[AssetFile.Kind.MAIN, AssetFile.Kind.LEGACY_PUBLIC]
    ).order_by('asset_id', 'id')[:len(wanted_assets) + 1])
    files_by_asset = {}
    for file in file_rows:
        files_by_asset.setdefault(file.asset_id, []).append(file)
    albums = []
    file_descriptors = {}
    asset_keys = {str(value): value for value in wanted_assets}
    for page, route, revision, payload, specs in provisional:
        photos = []
        for item in specs:
            asset_id = asset_keys.get(item['asset_id'])
            if asset_id is None:
                raise PublicUnavailable()
            candidates = files_by_asset.get(asset_id, [])
            if (len(candidates) != 1
                    or candidates[0].kind != AssetFile.Kind.LEGACY_PUBLIC):
                raise PublicUnavailable()
            file = candidates[0]
            slot = 'embedded:' + item['id']
            query = urlencode((('page', str(page.pk)), ('slot', slot)))
            photos.append(GalleryPhoto(
                image_id=item['id'], asset_id=item['asset_id'],
                file_id=str(file.pk),
                src='/public-media/' + str(file.pk) + '/?' + query,
                alt=item['alt'],
                alignment=item['alignment'], width_px=item['width_px'],
                height_px=item['height_px']))
            file_descriptors[str(file.pk)] = (
                str(file.asset_id), file.kind, file.key,
                file.sha256, file.byte_size)
        albums.append(GalleryAlbum(
            page_id=str(page.pk), revision_id=str(revision.pk),
            name=page.name, target=route.target,
            modal_target=(PAGE2_TARGET + '&album=' if request.page == 2
                          else ROOT_TARGET + '?album=')
                         + route.target.removeprefix(ROOT_TARGET),
            position=page.position,
            h1=payload['h1'], main_text=payload['main_text'],
            photos=tuple(photos)))
    by_target = {album.target: album for album in albums}
    selected = None
    if request.selected_target is not None:
        selected = by_target.get(request.selected_target)
        if selected is None:
            raise PublicNotFound()
    subset = tuple(album for album in albums
                   if album.target in (PAGE2_TARGETS if request.page == 2
                                       else ALBUM_TARGETS))
    projected_file_ids = {album.photos[0].file_id for album in subset}
    if selected is not None:
        projected_file_ids.update(photo.file_id for photo in selected.photos)
    if len(projected_file_ids) > MAX_PROJECTED_FILES:
        raise PublicUnavailable()
    selected_files = MappingProxyType({
        file_id: file_descriptors[file_id] for file_id in sorted(projected_file_ids)})
    stamp_data = tuple((
        album.page_id, album.revision_id, album.name, album.target,
        album.position, album.h1, album.main_text,
        tuple((photo.image_id, photo.asset_id, photo.file_id, photo.src,
               photo.alt, photo.alignment, photo.width_px, photo.height_px)
              for photo in album.photos)) for album in albums)
    return GalleryProjection(
        request=request, albums=subset, selected=selected,
        files=selected_files, stamp_data=stamp_data)
