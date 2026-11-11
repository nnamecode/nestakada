"""Typed bridge from the public Page reader to the shared renderer."""
from dataclasses import dataclass
from types import MappingProxyType

from django.core.exceptions import ValidationError
from django.db.models.expressions import RawSQL

from media_library.models import Asset, AssetFile, AssetUsage
from page_versions import schema
from page_versions.models import PageContentState, PageRevision
from shared_content.public import HostContext, HostMediaFile, NavItem
from shared_content.services import digest

from .models import Page, Route
from .public_seo import WASH_NEW_TARGET, WASH_OLD_TARGET
from .public_read import (PUBLIC_HERO_PAGE_KINDS, PublicPage,
                          PublicUnavailable, public_navigation, resolve_target)
from .public_gallery import parse_gallery_target, project_gallery
from .home_projection import capture_once as capture_home_sources, project as project_home


HOST_POLICY = 'public-page-host-v1'
MAX_STANDALONE_IMAGE_SLOTS = 64
MAX_STANDALONE_MEDIA_FILES = 64


@dataclass(frozen=True)
class PublicBreadcrumbItem:
    name: str
    target: str | None
    current: bool


@dataclass(frozen=True)
class PublicSeoMedia:
    file_id: str
    slot: str
    alt: str


def project_breadcrumbs(page, navigation):
    """Project one validated visible ancestry chain without another read."""
    by_id = {}
    for item in navigation:
        if item.page_id in by_id:
            raise PublicUnavailable()
        by_id[item.page_id] = item
    item = by_id.get(page.page_id)
    if item is None:
        raise PublicUnavailable()
    reverse_chain, seen = [], set()
    while item is not None:
        if item.page_id in seen:
            raise PublicUnavailable()
        seen.add(item.page_id)
        reverse_chain.append(item)
        if item.parent_id is None:
            break
        item = by_id.get(item.parent_id)
        if item is None:
            raise PublicUnavailable()
    chain = tuple(reversed(reverse_chain))
    return tuple(PublicBreadcrumbItem(
        name=crumb.name,
        target=None if crumb.page_id == page.page_id else crumb.target,
        current=crumb.page_id == page.page_id,
    ) for crumb in chain)


class PublicSharedHost:
    """Keep the body data from the renderer's final coherent host capture."""

    def __init__(self, target):
        self.target = target
        self.page = None
        self.navigation = ()
        self.breadcrumbs = ()
        self.media = MappingProxyType({})
        self.gallery = None
        self.seo_media = None
        self.wash_peer = None
        self.home = None

    @staticmethod
    def _standalone_media(page):
        embedded = {item['id']: item for item in page.payload['embedded_images']}
        slots = {}
        main_image = page.payload['main_image']
        preview_image = page.payload['preview_image']
        if (main_image is not None
                and page.page_kind in PUBLIC_HERO_PAGE_KINDS):
            intro_nodes = [
                node for node in page.payload['layout']
                if node['kind'] == 'text' and node['field'] == 'intro_text']
            if (len(intro_nodes) != 1
                    or intro_nodes[0]['protected_nodes']):
                raise PublicUnavailable()
            slots['main_image'] = main_image['asset_id']
        seo_slot = None
        seo_image = preview_image if preview_image is not None else main_image
        if seo_image is not None:
            seo_slot = ('preview_image'
                        if preview_image is not None else 'main_image')
            slots[seo_slot] = seo_image['asset_id']
        for image_id in schema.displayed_embedded_image_ids(page.payload):
            image = embedded.get(image_id)
            if image is None:
                raise PublicUnavailable()
            slots['embedded:' + image['id']] = image['asset_id']
        if len(slots) > MAX_STANDALONE_IMAGE_SLOTS:
            raise PublicUnavailable()
        if not slots:
            return MappingProxyType({}), (), None
        usage_rows = list(AssetUsage.objects.select_related('asset').filter(
            kind=AssetUsage.Kind.CURRENT_PAGE, consumer_id=page.page_id,
            slot__in=slots).order_by('slot'))
        usages = {row.slot: row for row in usage_rows}
        if len(usages) != len(slots):
            raise PublicUnavailable()
        asset_ids = {row.asset_id for row in usage_rows}
        file_rows = list(AssetFile.objects.filter(
            asset_id__in=asset_ids,
            kind__in=[AssetFile.Kind.MAIN, AssetFile.Kind.LEGACY_PUBLIC]
        ).order_by('asset_id', 'id')[:len(asset_ids) + 1])
        variants = {}
        for file in file_rows:
            variants.setdefault(file.asset_id, []).append(file)
        mapping, files = {}, {}
        for slot, asset_id in sorted(slots.items()):
            usage = usages[slot]
            if (str(usage.asset_id) != asset_id
                    or usage.asset.status != Asset.Status.READY):
                raise PublicUnavailable()
            selected = variants.get(usage.asset_id, [])
            if len(selected) != 1:
                raise PublicUnavailable()
            file = selected[0]
            if ((usage.asset.is_legacy
                 and file.kind != AssetFile.Kind.LEGACY_PUBLIC)
                    or (not usage.asset.is_legacy
                        and file.kind != AssetFile.Kind.MAIN)):
                raise PublicUnavailable()
            mapping[slot] = str(file.pk)
            files[str(file.pk)] = HostMediaFile(
                id=str(file.pk), asset_id=str(file.asset_id), kind=file.kind,
                key=file.key, sha256=file.sha256, byte_size=file.byte_size)
        if len(files) > MAX_STANDALONE_MEDIA_FILES:
            raise PublicUnavailable()
        seo_media = (None if seo_slot is None else PublicSeoMedia(
            file_id=mapping[seo_slot], slot=seo_slot, alt=seo_image['alt']))
        return (MappingProxyType(mapping),
                tuple(files[key] for key in sorted(files)), seo_media)

    @staticmethod
    def _merge_media_files(standalone_files, gallery_files):
        merged = {}
        for descriptor in (*standalone_files, *gallery_files):
            previous = merged.get(descriptor.id)
            if previous is not None and previous != descriptor:
                raise PublicUnavailable()
            merged[descriptor.id] = descriptor
        if len(merged) > MAX_STANDALONE_MEDIA_FILES:
            raise PublicUnavailable()
        return tuple(merged[key] for key in sorted(merged))

    @staticmethod
    def _wash_peer_descriptor(page):
        if (page.target != WASH_OLD_TARGET or page.route_kind != Route.Kind.ALIAS
                or page.page_kind != Page.Kind.WASH):
            return None
        route = (Route.objects.annotate(row_version=RawSQL('xmin::text', []))
                 .filter(target=WASH_NEW_TARGET, kind=Route.Kind.PRIMARY)
                 .only('id', 'page_id', 'target').first())
        if route is None:
            return None
        peer = (Page.objects.annotate(row_version=RawSQL('xmin::text', []))
                .filter(pk=route.page_id).only('id', 'is_published', 'kind').first())
        if peer is None or not peer.is_published:
            return None
        state = (PageContentState.objects.annotate(
                    row_version=RawSQL('xmin::text', []))
                 .filter(page_id=peer.pk).only(
                     'id', 'page_id', 'current_revision_id').first())
        if state is None:
            return None
        revision = (PageRevision.objects.annotate(
                        row_version=RawSQL('xmin::text', []))
                    .filter(pk=state.current_revision_id, page_id=peer.pk)
                    .only('id', 'page_id', 'schema_version',
                          'payload_hash', 'payload').first())
        if revision is None:
            return None
        try:
            payload = schema.validate(revision.payload, peer.kind)
        except (ValidationError, TypeError, ValueError, AttributeError):
            return None
        if (revision.schema_version != schema.SCHEMA
                or schema.digest(payload) != revision.payload_hash
                or payload['indexing_allowed'] is not True):
            return None
        return {
            'route': [str(route.pk), str(route.page_id), route.target,
                      route.row_version],
            'page': [str(peer.pk), peer.kind, peer.row_version],
            'state': [str(state.pk), str(state.current_revision_id),
                      state.row_version],
            'revision': [str(revision.pk), revision.schema_version,
                         revision.payload_hash, revision.row_version],
        }

    def capture(self):
        gallery_request = parse_gallery_target(self.target)
        page = resolve_target(
            gallery_request.base_target if gallery_request is not None
            else self.target)
        if not isinstance(page, PublicPage):
            raise PublicUnavailable()
        navigation = public_navigation()
        breadcrumbs = project_breadcrumbs(page, navigation)
        media, media_files, seo_media = self._standalone_media(page)
        wash_peer = self._wash_peer_descriptor(page)
        gallery = None
        home = None
        if gallery_request is not None:
            gallery = project_gallery(page, gallery_request)
            gallery_files = tuple(HostMediaFile(
                id=file_id, asset_id=descriptor[0], kind=descriptor[1],
                key=descriptor[2], sha256=descriptor[3],
                byte_size=descriptor[4])
                for file_id, descriptor in gallery.files.items())
            media_files = self._merge_media_files(media_files, gallery_files)
        profile = page.payload.get('home_profile')
        if profile is not None:
            capture, source_digest = capture_home_sources(profile)
            home = project_home(profile, capture['facts'])
            if home['source_digest'] != schema.digest(capture['facts']):
                raise PublicUnavailable()
        projection = {
            'policy': HOST_POLICY,
            'page': {
                'routeId': page.route_id,
                'pageId': page.page_id,
                'revisionId': page.revision_id,
                'target': page.target,
                'routeKind': page.route_kind,
                'pageKind': page.page_kind,
                'name': page.name,
                'payloadHash': page.payload_hash,
                'payload': dict(page.payload),
            },
            'navigation': [[item.page_id, item.parent_id, item.name, item.target]
                           for item in navigation],
            'media': [[slot, file_id] for slot, file_id in media.items()],
            'seoMedia': (None if seo_media is None else [
                seo_media.file_id, seo_media.slot, seo_media.alt]),
            'washPeer': wash_peer,
            'gallery': None if gallery is None else {
                'request': [gallery.request.base_target, gallery.request.page,
                            gallery.request.selected_target],
                'stamp': gallery.stamp_data,
                'files': [[file_id, *descriptor]
                          for file_id, descriptor in gallery.files.items()],
            },
            'home': None if home is None else {
                'projection': home,
                'sourceCaptureDigest': source_digest,
                'sourceCapture': capture,
            },
        }
        self.page = page
        self.navigation = navigation
        self.breadcrumbs = breadcrumbs
        self.media = media
        self.gallery = gallery
        self.seo_media = seo_media
        self.wash_peer = wash_peer
        self.home = home
        shared_navigation = tuple(NavItem(
            item.name, item.target, item.page_id == page.page_id)
            for item in navigation)
        return HostContext(digest(projection), shared_navigation, media_files)

    def body(self):
        if not isinstance(self.page, PublicPage):
            raise PublicUnavailable()
        return self.page, self.navigation, self.breadcrumbs, self.media

    def gallery_body(self):
        return self.gallery

    def seo_body(self):
        if not isinstance(self.page, PublicPage):
            raise PublicUnavailable()
        return self.seo_media, self.wash_peer is not None

    def home_body(self):
        return self.home
