from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ValidationError
from django.db import DatabaseError, models
from django.db.models import Count, Subquery

from .content import ContentValidationError, canonical_payload_hash, validate_payload
from .models import Page, PageContent, PageKind, Route, RouteMode, RouteOutcome, SiteSettings


_PAGE_CAP = 512


class PublicReadError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class PublicBlank:
    pass


@dataclass(frozen=True, slots=True)
class PublicPage:
    page_id: uuid.UUID
    kind: str
    requested_target: str
    primary_target: str
    requested_mode: str


@dataclass(frozen=True, slots=True)
class PublicRedirect:
    primary_target: str


@dataclass(frozen=True, slots=True)
class PublicNavigationItem:
    page_id: uuid.UUID
    name: str
    primary_target: str
    children: tuple[PublicNavigationItem, ...]


@dataclass(frozen=True, slots=True)
class PublicSeo:
    title: str
    description: str
    allow_index: bool


@dataclass(frozen=True, slots=True)
class PublicExternalLink:
    label: str
    https_url: str


@dataclass(frozen=True, slots=True)
class PublicPartnerLinksDocument:
    page_id: uuid.UUID
    primary_target: str
    h1: str
    seo: PublicSeo
    links: tuple[PublicExternalLink, ...]


@dataclass(frozen=True, slots=True)
class PublicEmptyDocument:
    page_id: uuid.UUID
    primary_target: str
    h1: str
    seo: PublicSeo


@dataclass(frozen=True, slots=True)
class PublicLegacyTextDocument:
    page_id: uuid.UUID
    primary_target: str
    h1: str
    seo: PublicSeo
    kind: str
    intro: str
    body: str


_LEGACY_PLAIN_KINDS = {
    PageKind.LEGACY_PARTNER_LINKS,
    PageKind.LEGACY_EMPTY_MAIN,
    PageKind.LEGACY_UNDER_CONSTRUCTION,
    PageKind.LEGACY_CAMERA_SCHEDULE_TEXT,
}


def _target_is_valid(target: object) -> bool:
    if not isinstance(target, str) or not 1 <= len(target) <= 2048:
        return False
    if target.startswith("//"):
        return False
    if re.search(r"%(?![0-9A-Fa-f]{2})", target):
        return False
    try:
        parsed = urlsplit(target)
        decoded_path = unquote(parsed.path, errors="strict")
        decoded_query = unquote(parsed.query, errors="strict")
    except (UnicodeDecodeError, ValueError):
        return False
    return not (
        not target.startswith("/")
        or parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or "\\" in target
        or "\\" in decoded_path
        or any(
            ord(char) < 32 or ord(char) == 127 or char.isspace()
            for char in target + decoded_path + decoded_query
        )
        or any(segment in {".", ".."} for segment in decoded_path.split("/"))
    )


def _settings_annotations() -> dict[str, Subquery]:
    grouped = (
        SiteSettings.objects.filter(singleton_key=True)
        .values("singleton_key")
        .annotate(row_count=Count("id"))
    )
    return {
        "public_settings_count": Subquery(
            grouped.values("row_count"),
            output_field=models.IntegerField(),
        ),
        "public_structure_generation": Subquery(
            SiteSettings.objects.filter(singleton_key=True).values(
                "structure_generation"
            ),
            output_field=models.PositiveBigIntegerField(),
        ),
    }


def _exact_generation() -> int:
    values = list(
        SiteSettings.objects.filter(singleton_key=True)
        .values_list("structure_generation", flat=True)[:2]
    )
    if len(values) != 1 or type(values[0]) is not int or values[0] < 1:
        raise PublicReadError("UNAVAILABLE")
    return values[0]


def _validate_route(route: Route) -> None:
    if (
        route.mode not in RouteMode.values
        or route.outcome not in RouteOutcome.values
        or route.page.kind not in PageKind.values
    ):
        raise PublicReadError("UNAVAILABLE")
    try:
        route.clean()
    except ValidationError:
        raise PublicReadError("UNAVAILABLE") from None


def _primary_route(routes: list[Route]) -> Route:
    primary = [route for route in routes if route.mode == RouteMode.PRIMARY]
    if len(primary) != 1:
        raise PublicReadError("UNAVAILABLE")
    _validate_route(primary[0])
    return primary[0]


def project_legacy_plain(
    page: PublicPage,
) -> PublicBlank | PublicPartnerLinksDocument | PublicEmptyDocument | PublicLegacyTextDocument:
    if not isinstance(page, PublicPage) or page.kind not in _LEGACY_PLAIN_KINDS:
        raise PublicReadError("UNAVAILABLE")
    try:
        try:
            current = (
                Page.objects.select_related("content")
                .annotate(**_settings_annotations())
                .get(pk=page.page_id)
            )
        except (Page.DoesNotExist, PageContent.DoesNotExist):
            raise PublicReadError("UNAVAILABLE") from None
        if (
            current.public_settings_count != 1
            or type(current.public_structure_generation) is not int
            or current.public_structure_generation < 1
            or current.kind != page.kind
        ):
            raise PublicReadError("UNAVAILABLE")
        if not current.is_published:
            return PublicBlank()

        content = current.content
        if canonical_payload_hash(content.current_payload) != content.current_hash:
            raise PublicReadError("UNAVAILABLE")
        media = validate_payload(content.current_payload, current.kind)
        if media:
            raise PublicReadError("UNAVAILABLE")

        routes = list(
            Route.objects.select_related("page")
            .filter(page_id=current.id)
            .order_by("id")
        )
        primary = _primary_route(routes)
        if primary.target != page.primary_target:
            raise PublicReadError("UNAVAILABLE")
        requested = [
            route
            for route in routes
            if route.target == page.requested_target and route.mode == page.requested_mode
        ]
        if len(requested) != 1:
            raise PublicReadError("UNAVAILABLE")
        _validate_route(requested[0])
        if _exact_generation() != current.public_structure_generation:
            raise PublicReadError("UNAVAILABLE")

        fields = content.current_payload["fields"]
        seo_fields = fields["seo"]
        seo = PublicSeo(
            title=seo_fields["title"],
            description=seo_fields["description"],
            allow_index=seo_fields["allow_index"],
        )
        common = {
            "page_id": current.id,
            "primary_target": primary.target,
            "h1": fields["heading"]["h1"],
            "seo": seo,
        }
        if current.kind == PageKind.LEGACY_PARTNER_LINKS:
            return PublicPartnerLinksDocument(
                **common,
                links=tuple(
                    PublicExternalLink(link["label"], link["https_url"])
                    for link in fields["links"]
                ),
            )
        if current.kind == PageKind.LEGACY_EMPTY_MAIN:
            return PublicEmptyDocument(**common)
        return PublicLegacyTextDocument(
            **common,
            kind=current.kind,
            intro=fields["intro"],
            body=fields["body"],
        )
    except PublicReadError:
        raise
    except (
        ContentValidationError,
        DatabaseError,
        KeyError,
        PageContent.DoesNotExist,
        TypeError,
        ValueError,
        ValidationError,
    ):
        raise PublicReadError("UNAVAILABLE") from None


def resolve_public_target(target: str) -> PublicBlank | PublicPage | PublicRedirect:
    if not _target_is_valid(target):
        raise PublicReadError("NOT_FOUND")
    try:
        try:
            requested = (
                Route.objects.select_related("page")
                .annotate(**_settings_annotations())
                .get(target=target)
            )
        except Route.DoesNotExist:
            raise PublicReadError("NOT_FOUND") from None
        if (
            requested.public_settings_count != 1
            or type(requested.public_structure_generation) is not int
            or requested.public_structure_generation < 1
        ):
            raise PublicReadError("UNAVAILABLE")
        _validate_route(requested)
        if requested.mode in {RouteMode.PRIMARY, RouteMode.ALIAS} and not requested.page.is_published:
            return PublicBlank()

        routes = list(
            Route.objects.select_related("page")
            .filter(page_id=requested.page_id)
            .order_by("id")
        )
        primary = _primary_route(routes)
        final_generation = _exact_generation()
        if final_generation != requested.public_structure_generation:
            raise PublicReadError("UNAVAILABLE")
        if requested.mode == RouteMode.REDIRECT:
            if primary.target == requested.target:
                raise PublicReadError("UNAVAILABLE")
            return PublicRedirect(primary.target)
        if requested.mode not in {RouteMode.PRIMARY, RouteMode.ALIAS}:
            raise PublicReadError("UNAVAILABLE")
        return PublicPage(
            page_id=requested.page_id,
            kind=requested.page.kind,
            requested_target=requested.target,
            primary_target=primary.target,
            requested_mode=requested.mode,
        )
    except PublicReadError:
        raise
    except (DatabaseError, TypeError, ValueError, ValidationError):
        raise PublicReadError("UNAVAILABLE") from None


def project_public_navigation() -> tuple[PublicNavigationItem, ...]:
    try:
        initial_generation = _exact_generation()
        pages = list(Page.objects.order_by("id")[: _PAGE_CAP + 1])
        if len(pages) > _PAGE_CAP:
            raise PublicReadError("UNAVAILABLE")
        page_by_id = {page.id: page for page in pages}
        if len(page_by_id) != len(pages):
            raise PublicReadError("UNAVAILABLE")
        routes = list(
            Route.objects.select_related("page")
            .filter(page_id__in=page_by_id, mode=RouteMode.PRIMARY)
            .order_by("page_id", "id")
        )
        final_generation = _exact_generation()
        if initial_generation != final_generation:
            raise PublicReadError("UNAVAILABLE")

        primary_by_page: dict[uuid.UUID, Route] = {}
        for route in routes:
            if route.page_id in primary_by_page:
                raise PublicReadError("UNAVAILABLE")
            _validate_route(route)
            primary_by_page[route.page_id] = route
        for page in pages:
            if page.parent_id is not None and page.parent_id not in page_by_id:
                raise PublicReadError("UNAVAILABLE")
            if page.kind not in PageKind.values:
                raise PublicReadError("UNAVAILABLE")
            if page.is_published and page.id not in primary_by_page:
                raise PublicReadError("UNAVAILABLE")

        done: set[uuid.UUID] = set()
        for page in pages:
            if page.id in done:
                continue
            path: list[uuid.UUID] = []
            seen: set[uuid.UUID] = set()
            current: Page | None = page
            while current is not None and current.id not in done:
                if current.id in seen:
                    raise PublicReadError("UNAVAILABLE")
                seen.add(current.id)
                path.append(current.id)
                current = (
                    page_by_id[current.parent_id]
                    if current.parent_id is not None
                    else None
                )
            done.update(path)

        children: dict[uuid.UUID | None, list[Page]] = {}
        for page in pages:
            if not page.is_published:
                continue
            ancestor_id = page.parent_id
            while ancestor_id is not None and not page_by_id[ancestor_id].is_published:
                ancestor_id = page_by_id[ancestor_id].parent_id
            children.setdefault(ancestor_id, []).append(page)
        for siblings in children.values():
            siblings.sort(key=lambda page: (page.position, str(page.id)))

        def materialize(parent_id: uuid.UUID | None) -> tuple[PublicNavigationItem, ...]:
            return tuple(
                PublicNavigationItem(
                    page_id=page.id,
                    name=page.name,
                    primary_target=primary_by_page[page.id].target,
                    children=materialize(page.id),
                )
                for page in children.get(parent_id, ())
            )

        return materialize(None)
    except PublicReadError:
        raise
    except (DatabaseError, KeyError, TypeError, ValueError, ValidationError):
        raise PublicReadError("UNAVAILABLE") from None
