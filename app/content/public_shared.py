"""Typed bridge from the public Page reader to the shared renderer."""
from dataclasses import dataclass
from types import MappingProxyType

from media_library.models import Asset, AssetFile, AssetUsage
from shared_content.public import HostContext, HostMediaFile, NavItem
from shared_content.services import digest

from .public_read import (PUBLIC_HERO_PAGE_KINDS, PublicPage,
                          PublicUnavailable, public_navigation, resolve_target)


HOST_POLICY = 'public-page-host-v1'
MAX_STANDALONE_IMAGE_SLOTS = 64
MAX_STANDALONE_MEDIA_FILES = 64


@dataclass(frozen=True)
class PublicBreadcrumbItem:
    name: str
    target: str | None
    current: bool


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

    @staticmethod
    def _standalone_media(page):
        embedded = {item['id']: item for item in page.payload['embedded_images']}
        slots = {}
        main_image = page.payload['main_image']
        if (main_image is not None
                and page.page_kind in PUBLIC_HERO_PAGE_KINDS):
            intro_nodes = [
                node for node in page.payload['layout']
                if node['kind'] == 'text' and node['field'] == 'intro_text']
            if (len(intro_nodes) != 1
                    or intro_nodes[0]['protected_nodes']):
                raise PublicUnavailable()
            slots['main_image'] = main_image['asset_id']
        for node in page.payload['layout']:
            if node['kind'] != 'image':
                continue
            image = embedded.get(node['image_id'])
            if image is None:
                raise PublicUnavailable()
            slots['embedded:' + image['id']] = image['asset_id']
        if len(slots) > MAX_STANDALONE_IMAGE_SLOTS:
            raise PublicUnavailable()
        if not slots:
            return MappingProxyType({}), ()
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
        return MappingProxyType(mapping), tuple(files[key] for key in sorted(files))

    def capture(self):
        page = resolve_target(self.target)
        if not isinstance(page, PublicPage):
            raise PublicUnavailable()
        navigation = public_navigation()
        breadcrumbs = project_breadcrumbs(page, navigation)
        media, media_files = self._standalone_media(page)
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
        }
        self.page = page
        self.navigation = navigation
        self.breadcrumbs = breadcrumbs
        self.media = media
        shared_navigation = tuple(NavItem(
            item.name, item.target, item.page_id == page.page_id)
            for item in navigation)
        return HostContext(digest(projection), shared_navigation, media_files)

    def body(self):
        if not isinstance(self.page, PublicPage):
            raise PublicUnavailable()
        return self.page, self.navigation, self.breadcrumbs, self.media
