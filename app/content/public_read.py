"""Small read-only resolver for the public site.

It returns validated data, never a Django template name or executable source.
"""
from dataclasses import dataclass
from types import MappingProxyType

from django.core.exceptions import ValidationError
from django.db import transaction

from page_versions import schema
from page_versions.models import PageContentState
from page_editor.clean import restricted_clean

from .models import Page, Route
from .validators import exact_target


PUBLIC_HERO_PAGE_KINDS = frozenset((
    Page.Kind.SERVICE,
    Page.Kind.SERVICE_SECTION,
))


class PublicNotFound(Exception):
    pass


class PublicUnavailable(Exception):
    pass


@dataclass(frozen=True)
class PublicPage:
    route_id: str
    page_id: str
    revision_id: str
    target: str
    route_kind: str
    page_kind: str
    name: str
    payload_hash: str
    payload: MappingProxyType


@dataclass(frozen=True)
class PublicRedirect:
    location: str


@dataclass(frozen=True)
class PublicBlank:
    route_id: str
    page_id: str
    target: str
    route_kind: str


@dataclass(frozen=True)
class PublicNavigationItem:
    page_id: str
    parent_id: str | None
    name: str
    target: str


def _target(value):
    try:
        exact_target(value)
    except ValidationError:
        raise PublicNotFound() from None
    return value


def _stored_target(value):
    try:
        exact_target(value)
    except ValidationError:
        raise PublicUnavailable() from None
    return value


def _safe_public_html(payload):
    for field in ('intro_text', 'main_text'):
        value = payload[field]
        try:
            cleaned = restricted_clean(value)
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise PublicUnavailable() from None
        if cleaned != value:
            raise PublicUnavailable()


def public_navigation():
    """Return accessible pages in stable pre-order without projecting hidden subtrees."""
    try:
        with transaction.atomic():
            pages = list(Page.objects.all().only(
                'id', 'parent_id', 'position', 'name', 'is_published'))
            primary = {}
            for route in Route.objects.filter(kind=Route.Kind.PRIMARY).only(
                    'page_id', 'target'):
                if route.page_id in primary:
                    raise PublicUnavailable()
                primary[route.page_id] = route.target
            children = {}
            for page in pages:
                children.setdefault(page.parent_id, []).append(page)
            stack = [(page, None) for page in reversed(children.get(None, []))]
            items, seen = [], set()
            while stack:
                page, visible_parent_id = stack.pop()
                if page.pk in seen:
                    raise PublicUnavailable()
                seen.add(page.pk)
                next_parent_id = visible_parent_id
                if page.is_published:
                    if (type(page.name) is not str or not page.name.strip()
                            or any(ord(char) < 32 or ord(char) == 127
                                   for char in page.name)):
                        raise PublicUnavailable()
                    target = primary.get(page.pk)
                    if target is None:
                        raise PublicUnavailable()
                    items.append(PublicNavigationItem(
                        page_id=str(page.pk),
                        parent_id=visible_parent_id,
                        name=page.name, target=_stored_target(target)))
                    next_parent_id = str(page.pk)
                stack.extend((child, next_parent_id)
                             for child in reversed(children.get(page.pk, [])))
            if len(seen) != len(pages):
                raise PublicUnavailable()
            return tuple(items)
    except PublicUnavailable:
        raise
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise PublicUnavailable() from None


def resolve_target(target):
    """Resolve one exact stored target without writing or creating a session."""
    target = _target(target)
    try:
        with transaction.atomic():
            route = (Route.objects.select_related('page')
                     .filter(target=target).first())
            if (route is None or route.kind == Route.Kind.SYSTEM
                    or route.page_id is None):
                raise PublicNotFound()
            if route.kind == Route.Kind.REDIRECT:
                primary = Route.objects.filter(
                    page_id=route.page_id, kind=Route.Kind.PRIMARY).only('target').first()
                if primary is None or primary.target == route.target:
                    raise PublicUnavailable()
                return PublicRedirect(location=_stored_target(primary.target))
            if route.kind not in (Route.Kind.PRIMARY, Route.Kind.ALIAS):
                raise PublicNotFound()
            if not route.page.is_published:
                return PublicBlank(
                    route_id=str(route.pk), page_id=str(route.page_id),
                    target=route.target, route_kind=route.kind)
            state = (PageContentState.objects.select_related('current_revision')
                     .filter(page_id=route.page_id).first())
            if state is None or state.current_revision.page_id != route.page_id:
                raise PublicUnavailable()
            revision = state.current_revision
            payload = schema.validate(revision.payload, route.page.kind)
            if (revision.schema_version != schema.SCHEMA
                    or schema.digest(payload) != revision.payload_hash):
                raise PublicUnavailable()
            _safe_public_html(payload)
            return PublicPage(
                route_id=str(route.pk), page_id=str(route.page_id),
                revision_id=str(revision.pk), target=route.target,
                route_kind=route.kind, page_kind=route.page.kind,
                name=route.page.name, payload_hash=revision.payload_hash,
                payload=MappingProxyType(payload))
    except (PublicNotFound, PublicUnavailable):
        raise
    except (ValidationError, TypeError, ValueError, AttributeError):
        raise PublicUnavailable() from None
