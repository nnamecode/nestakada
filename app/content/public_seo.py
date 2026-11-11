"""Closed, side-effect-free SEO projection for the public renderer."""
from dataclasses import dataclass
import hashlib
import ipaddress
import json
import math
import re
from urllib.parse import urlencode, urlsplit
from uuid import UUID
from xml.etree import ElementTree

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models.expressions import RawSQL

from page_versions import schema
from page_versions.models import PageContentState, PageRevision

from .models import Page, Route
from .public_gallery import (ROOT_TARGET as GALLERY_ROOT,
                             PAGE2_TARGET as GALLERY_PAGE2,
                             page1_redirect_target, parse_gallery_target)
from .public_read import PublicNotFound
from .validators import exact_target


ROBOTS_PROFILES = frozenset(('deny-all', 'production'))
MAX_SITEMAP_PAGES = 50_000
MAX_SITEMAP_PRIMARY_ROUTES = 50_000
MAX_SITEMAP_ALIASES = 2
MAX_SITEMAP_STATES = 50_000
MAX_SITEMAP_REVISIONS = 50_000
MAX_SITEMAP_BYTES = 50 * 1024 * 1024
WASH_OLD_TARGET = '/services/drugie-uslugi/avtomojka'
WASH_NEW_TARGET = '/services/avtomojka'
_HOST_LABEL = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z')


class SeoUnavailable(Exception):
    pass


@dataclass(frozen=True)
class SeoConfiguration:
    origin: str
    robots_profile: str


@dataclass(frozen=True)
class SeoPage:
    request_target: str
    route_kind: str
    page_kind: str
    name: str
    title: str
    description: str
    indexing_allowed: bool
    wash_peer_eligible: bool = False


@dataclass(frozen=True)
class SeoProjection:
    title: str
    description: str | None
    canonical: str | None
    robots: str | None
    og_title: str
    og_description: str | None
    og_url: str | None
    image: 'SeoImage | None'


@dataclass(frozen=True)
class SeoImage:
    url: str
    alt: str


@dataclass(frozen=True)
class SitemapSnapshot:
    stamp: str
    locations: tuple[str, ...]


@dataclass(frozen=True)
class AutoRepairProfile:
    name: str
    address: str
    telephone: str
    opening_hours: tuple[str, ...] = ()
    latitude: float | None = None
    longitude: float | None = None
    same_as: tuple[str, ...] = ()
    logo: str | None = None
    image: str | None = None


@dataclass(frozen=True)
class VisibleBusinessFacts:
    name: str
    address: str
    telephone: str


@dataclass(frozen=True)
class AutoRepairPage:
    page_kind: str
    published: bool
    indexing_allowed: bool


@dataclass(frozen=True)
class AutoRepairNode:
    profile: AutoRepairProfile
    origin: str


def _host_is_valid(host):
    if type(host) is not str or not host or host != host.lower():
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    return (host == 'localhost'
            or all(_HOST_LABEL.fullmatch(label) for label in host.split('.')))


def _configuration(origin, profile):
    if type(origin) is not str or type(profile) is not str:
        raise SeoUnavailable()
    if profile not in ROBOTS_PROFILES:
        raise SeoUnavailable()
    try:
        origin.encode('ascii')
        parts = urlsplit(origin)
        port = parts.port
    except (UnicodeError, ValueError, TypeError):
        raise SeoUnavailable() from None
    if (not origin or any(ord(char) < 33 or ord(char) == 127 for char in origin)
            or parts.scheme not in ('http', 'https')
            or parts.username is not None or parts.password is not None
            or parts.path or parts.query or parts.fragment
            or not _host_is_valid(parts.hostname)
            or port is not None and not 1 <= port <= 65535):
        raise SeoUnavailable()
    host = parts.hostname
    if ':' in host:
        host = '[' + host + ']'
    normalized = parts.scheme + '://' + host
    if port is not None:
        normalized += ':' + str(port)
    if origin != normalized:
        raise SeoUnavailable()
    if profile == 'production' and parts.scheme != 'https':
        raise SeoUnavailable()
    if (parts.scheme == 'http' and profile == 'deny-all'
            and parts.hostname not in ('localhost', '127.0.0.1', '::1',
                                       'host.docker.internal')):
        raise SeoUnavailable()
    return SeoConfiguration(origin=origin, robots_profile=profile)


def load_configuration():
    return _configuration(
        getattr(settings, 'PUBLIC_ORIGIN', None),
        getattr(settings, 'SEO_ROBOTS_PROFILE', None))


def hidden_robots():
    return 'noindex, nofollow'


def _absolute(configuration, target):
    try:
        exact_target(target)
    except ValidationError:
        raise SeoUnavailable() from None
    return configuration.origin + target


def _canonical(configuration, page):
    if not page.indexing_allowed:
        return None
    if page.page_kind == 'gallery_catalog':
        try:
            gallery = parse_gallery_target(page.request_target)
        except PublicNotFound:
            raise SeoUnavailable() from None
        if gallery is None:
            raise SeoUnavailable()
        expected_kind = (Route.Kind.ALIAS
                         if gallery.base_target == GALLERY_PAGE2
                         else Route.Kind.PRIMARY)
        if page.route_kind != expected_kind:
            raise SeoUnavailable()
        return _absolute(configuration, GALLERY_ROOT)
    if page.route_kind == Route.Kind.ALIAS:
        if (page.request_target != WASH_OLD_TARGET
                or page.page_kind != 'service_wash_legacy_alias'):
            return None
        return (_absolute(configuration, WASH_NEW_TARGET)
                if page.wash_peer_eligible else None)
    if page.route_kind != Route.Kind.PRIMARY:
        raise SeoUnavailable()
    if page1_redirect_target(page.request_target) is not None:
        raise SeoUnavailable()
    if '?' in page.request_target or '#' in page.request_target:
        raise SeoUnavailable()
    return _absolute(configuration, page.request_target)


def project_seo_image(configuration, *, page_id, file_id, slot, alt):
    if (type(configuration) is not SeoConfiguration
            or slot not in ('preview_image', 'main_image')):
        raise SeoUnavailable()
    try:
        page_id = UUID(str(page_id))
        file_id = UUID(str(file_id))
        schema.text(alt, 500)
    except (ValueError, TypeError, AttributeError, ValidationError):
        raise SeoUnavailable() from None
    query = urlencode((('page', str(page_id)), ('slot', slot)))
    return SeoImage(
        url=(configuration.origin + '/public-media/' + str(file_id)
             + '/?' + query), alt=alt)


def project_page_seo(configuration, page, image=None):
    if type(configuration) is not SeoConfiguration or type(page) is not SeoPage:
        raise SeoUnavailable()
    if image is not None and type(image) is not SeoImage:
        raise SeoUnavailable()
    try:
        schema.text(page.name, 200)
        schema.text(page.title, 255)
        schema.text(page.description, 1000, multiline=True)
    except ValidationError:
        raise SeoUnavailable() from None
    if (not page.name.strip() or type(page.indexing_allowed) is not bool
            or type(page.wash_peer_eligible) is not bool):
        raise SeoUnavailable()
    title = page.title or page.name
    description = page.description or None
    canonical = _canonical(configuration, page)
    robots = None if page.indexing_allowed else 'noindex, follow'
    return SeoProjection(
        title=title, description=description, canonical=canonical,
        robots=robots, og_title=title, og_description=description,
        og_url=canonical, image=image)


def _bounded(queryset, cap):
    rows = list(queryset[:cap + 1])
    if len(rows) > cap:
        raise SeoUnavailable()
    return rows


def capture_sitemap(configuration):
    if type(configuration) is not SeoConfiguration or not connection.in_atomic_block:
        raise SeoUnavailable()
    pages = _bounded(
        Page.objects.annotate(row_version=RawSQL('xmin::text', []))
        .only('id', 'kind', 'is_published').order_by('id'),
        MAX_SITEMAP_PAGES)
    primary = _bounded(
        Route.objects.annotate(row_version=RawSQL('xmin::text', []))
        .filter(kind=Route.Kind.PRIMARY)
        .only('id', 'page_id', 'target', 'kind').order_by('target', 'id'),
        MAX_SITEMAP_PRIMARY_ROUTES)
    aliases = _bounded(
        Route.objects.annotate(row_version=RawSQL('xmin::text', []))
        .filter(kind=Route.Kind.ALIAS)
        .only('id', 'page_id', 'target', 'kind').order_by('target', 'id'),
        MAX_SITEMAP_ALIASES)
    states = _bounded(
        PageContentState.objects.annotate(row_version=RawSQL('xmin::text', []))
        .only('id', 'page_id', 'current_revision_id').order_by('page_id'),
        MAX_SITEMAP_STATES)
    current_ids = [row.current_revision_id for row in states]
    revisions = _bounded(
        PageRevision.objects.annotate(row_version=RawSQL('xmin::text', []))
        .filter(pk__in=current_ids)
        .only('id', 'page_id', 'schema_version', 'payload_hash', 'payload')
        .order_by('id'), MAX_SITEMAP_REVISIONS)

    page_by_id = {row.pk: row for row in pages}
    primary_by_page = {}
    for row in primary:
        if row.page_id in primary_by_page or row.page_id not in page_by_id:
            raise SeoUnavailable()
        try:
            exact_target(row.target)
        except ValidationError:
            raise SeoUnavailable() from None
        primary_by_page[row.page_id] = row
    state_by_page = {row.page_id: row for row in states}
    revision_by_id = {row.pk: row for row in revisions}
    if (len(page_by_id) != len(pages)
            or len(state_by_page) != len(states)
            or len(revision_by_id) != len(revisions)
            or set(page_by_id) != set(primary_by_page)
            or set(page_by_id) != set(state_by_page)
            or set(current_ids) != set(revision_by_id)):
        raise SeoUnavailable()

    aliases_by_target = {row.target: row for row in aliases}
    if (len(aliases_by_target) != len(aliases)
            or set(aliases_by_target) != {GALLERY_PAGE2, WASH_OLD_TARGET}):
        raise SeoUnavailable()
    gallery_alias = aliases_by_target[GALLERY_PAGE2]
    wash_alias = aliases_by_target[WASH_OLD_TARGET]
    if (page_by_id.get(gallery_alias.page_id) is None
            or page_by_id[gallery_alias.page_id].kind != Page.Kind.GALLERY
            or primary_by_page[gallery_alias.page_id].target != GALLERY_ROOT
            or page_by_id.get(wash_alias.page_id) is None
            or page_by_id[wash_alias.page_id].kind != Page.Kind.WASH):
        raise SeoUnavailable()

    evidence, locations = [], []
    eligible = {}
    for page in pages:
        route = primary_by_page[page.pk]
        state = state_by_page[page.pk]
        revision = revision_by_id.get(state.current_revision_id)
        if revision is None or revision.page_id != page.pk:
            raise SeoUnavailable()
        try:
            payload = schema.validate(revision.payload, page.kind)
        except (ValidationError, TypeError, ValueError, AttributeError):
            raise SeoUnavailable() from None
        if (revision.schema_version != schema.SCHEMA
                or schema.digest(payload) != revision.payload_hash):
            raise SeoUnavailable()
        is_eligible = page.is_published and payload['indexing_allowed'] is True
        eligible[page.pk] = is_eligible
        if is_eligible and ('?' in route.target or '#' in route.target):
            raise SeoUnavailable()
        if is_eligible and page.kind != Page.Kind.WASH:
            locations.append(_absolute(configuration, route.target))
        evidence.append({
            'page': [str(page.pk), page.kind, page.is_published,
                     page.row_version],
            'primary': [str(route.pk), route.target, route.row_version],
            'state': [str(state.pk), str(state.current_revision_id),
                      state.row_version],
            'revision': [str(revision.pk), revision.schema_version,
                         revision.payload_hash, revision.row_version],
            'indexing': payload['indexing_allowed'],
        })
    wash_new = next(
        (row for row in primary if row.target == WASH_NEW_TARGET), None)
    if wash_new is None or not eligible.get(wash_new.page_id, False):
        raise SeoUnavailable()
    locations = tuple(sorted(locations))
    if len(locations) > MAX_SITEMAP_PAGES or len(set(locations)) != len(locations):
        raise SeoUnavailable()
    aliases_evidence = [[str(row.pk), str(row.page_id), row.target,
                         row.row_version] for row in aliases]
    encoded = json.dumps(
        {'pages': evidence, 'aliases': aliases_evidence,
         'locations': locations},
        ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return SitemapSnapshot(
        stamp=hashlib.sha256(encoded.encode('utf-8')).hexdigest(),
        locations=locations)


def sitemap_xml(snapshot):
    if type(snapshot) is not SitemapSnapshot:
        raise SeoUnavailable()
    root = ElementTree.Element(
        'urlset', {'xmlns': 'http://www.sitemaps.org/schemas/sitemap/0.9'})
    for location in snapshot.locations:
        url = ElementTree.SubElement(root, 'url')
        ElementTree.SubElement(url, 'loc').text = location
    body = ElementTree.tostring(
        root, encoding='utf-8', xml_declaration=True, short_empty_elements=True)
    if len(body) > MAX_SITEMAP_BYTES:
        raise SeoUnavailable()
    return body


def robots_text(configuration):
    if type(configuration) is not SeoConfiguration:
        raise SeoUnavailable()
    if configuration.robots_profile == 'deny-all':
        return b'User-agent: *\nDisallow: /\n'
    if configuration.robots_profile != 'production':
        raise SeoUnavailable()
    return (
        'User-agent: *\n'
        'Disallow: /manage/\n'
        'Disallow: /cgi-bin\n'
        'Disallow: /manager/\n'
        'Disallow: /assets/components/\n'
        'Disallow: /core/\n'
        'Disallow: /connectors/\n'
        'Disallow: /index.php\n'
        'Disallow: /*?\n'
        'Allow: /gallery-of-works/?page=1$\n'
        'Allow: /gallery-of-works/?page=2$\n'
        'Sitemap: ' + configuration.origin + '/sitemap.xml\n'
    ).encode('utf-8')


def _public_https_url(value):
    if type(value) is not str or not value or any(
            ord(char) < 32 or ord(char) == 127 for char in value):
        raise SeoUnavailable()
    try:
        parts = urlsplit(value)
        port = parts.port
    except (ValueError, TypeError, AttributeError):
        raise SeoUnavailable() from None
    if (parts.scheme != 'https' or not _host_is_valid(parts.hostname)
            or parts.username is not None or parts.password is not None
            or parts.fragment or port is not None and not 1 <= port <= 65535):
        raise SeoUnavailable()
    return value


def build_auto_repair(profile, visible_facts, page, configuration):
    if profile is None or visible_facts is None:
        return None
    if (type(profile) is not AutoRepairProfile
            or type(visible_facts) is not VisibleBusinessFacts
            or type(page) is not AutoRepairPage
            or type(configuration) is not SeoConfiguration):
        raise SeoUnavailable()
    if (page.page_kind not in (Page.Kind.HOME, Page.Kind.CONTACTS)
            or page.published is not True or page.indexing_allowed is not True):
        return None
    mandatory = (
        (profile.name, visible_facts.name, 200),
        (profile.address, visible_facts.address, 500),
        (profile.telephone, visible_facts.telephone, 100),
    )
    try:
        for expected, visible, cap in mandatory:
            schema.text(expected, cap, multiline=True)
            schema.text(visible, cap, multiline=True)
            if not expected.strip() or expected != visible:
                return None
        if (type(profile.opening_hours) is not tuple
                or len(profile.opening_hours) > 14
                or type(profile.same_as) is not tuple
                or len(profile.same_as) > 20):
            raise SeoUnavailable()
        for value in profile.opening_hours:
            schema.text(value, 200)
            if not value.strip():
                raise SeoUnavailable()
    except ValidationError:
        raise SeoUnavailable() from None
    coordinates = (profile.latitude, profile.longitude)
    if (coordinates[0] is None) != (coordinates[1] is None):
        raise SeoUnavailable()
    if coordinates[0] is not None:
        if (type(coordinates[0]) not in (int, float)
                or type(coordinates[1]) not in (int, float)
                or not math.isfinite(coordinates[0])
                or not math.isfinite(coordinates[1])
                or not -90 <= coordinates[0] <= 90
                or not -180 <= coordinates[1] <= 180):
            raise SeoUnavailable()
    for value in profile.same_as:
        _public_https_url(value)
    for value in (profile.logo, profile.image):
        if value is not None:
            _public_https_url(value)
    return AutoRepairNode(profile=profile, origin=configuration.origin)


def serialize_auto_repair(node):
    if type(node) is not AutoRepairNode:
        raise SeoUnavailable()
    profile = node.profile
    data = {
        '@context': 'https://schema.org',
        '@id': node.origin + '/#auto-repair',
        '@type': 'AutoRepair',
        'address': profile.address,
        'name': profile.name,
        'telephone': profile.telephone,
        'url': node.origin + '/',
    }
    if profile.opening_hours:
        data['openingHours'] = list(profile.opening_hours)
    if profile.latitude is not None:
        data['geo'] = {
            '@type': 'GeoCoordinates',
            'latitude': profile.latitude,
            'longitude': profile.longitude,
        }
    if profile.same_as:
        data['sameAs'] = list(profile.same_as)
    if profile.logo is not None:
        data['logo'] = profile.logo
    if profile.image is not None:
        data['image'] = profile.image
    encoded = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
        allow_nan=False)
    return (encoded.replace('&', '\\u0026').replace('<', '\\u003c')
            .replace('>', '\\u003e').replace('\u2028', '\\u2028')
            .replace('\u2029', '\\u2029'))
