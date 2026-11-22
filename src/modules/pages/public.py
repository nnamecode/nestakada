from __future__ import annotations

import copy
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ValidationError
from django.db import DatabaseError, models
from django.db.models import Count, Subquery

from modules.media.api import MediaUsageError, PublicPageMediaFile, project_public_page_media

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


@dataclass(frozen=True, slots=True)
class PublicImage:
    url: str
    mime_type: str
    width: int | None
    height: int | None
    alt: str


@dataclass(frozen=True, slots=True)
class PublicHomeComparison:
    heading: str
    bullets: tuple[str, ...]
    result_mark: str
    result_text: str


@dataclass(frozen=True, slots=True)
class PublicHomeStep:
    title: str
    body: str
    image: PublicImage


@dataclass(frozen=True, slots=True)
class PublicHomeService:
    label: str
    caption: str
    target: str
    image: PublicImage


@dataclass(frozen=True, slots=True)
class PublicHomePriceRow:
    label: str
    target: str
    price_text: str


@dataclass(frozen=True, slots=True)
class PublicHomePriceGroup:
    key: str
    label: str
    target: str
    rows: tuple[PublicHomePriceRow, ...]


@dataclass(frozen=True, slots=True)
class PublicHomeWork:
    label: str
    photo_count_text: str
    target: str
    image: PublicImage


@dataclass(frozen=True, slots=True)
class PublicHomeDocument:
    page_id: uuid.UUID
    primary_target: str
    h1: str
    seo: PublicSeo
    lead: str
    about: str
    hero: PublicImage
    advantages: tuple[str, ...]
    comparisons: tuple[PublicHomeComparison, ...]
    steps: tuple[PublicHomeStep, ...]
    services: tuple[PublicHomeService, ...]
    prices: tuple[PublicHomePriceGroup, ...]
    photo_strip: PublicImage
    works: tuple[PublicHomeWork, ...]
    reviews_heading: str
    reviews_target: str
    reviews_label: str


@dataclass(frozen=True, slots=True)
class PublicHomeLegacyDocument:
    page_id: uuid.UUID
    primary_target: str
    h1: str
    seo: PublicSeo
    lead: str
    about: str


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


@dataclass(frozen=True, slots=True)
class _HomePriceFact:
    row_id: str
    amount: str | None
    from_amount: bool | None


@dataclass(frozen=True, slots=True)
class _HomeSourceFact:
    page_id: str
    present: bool
    visible: bool
    generation: int | None
    payload_hash: str | None
    primary_target: str | None
    prices: tuple[_HomePriceFact, ...]


def _home_bindings(profile: dict) -> dict[str, set[str]]:
    bindings: dict[str, set[str]] = {}

    def add(page_id, row_id=None) -> None:
        if page_id is None:
            return
        rows = bindings.setdefault(page_id, set())
        if row_id is not None:
            rows.add(row_id)

    for item in profile["services"]:
        add(item["source_page_id"])
    for group in profile["prices"]:
        add(group["source_page_id"])
        for row in group["rows"]:
            add(row["source_page_id"], row["source_row_id"])
    for item in profile["works"]:
        add(item["source_page_id"])
    if len(bindings) > 64:
        raise PublicReadError("UNAVAILABLE")
    return bindings


def _capture_home_sources(profile: dict) -> tuple[_HomeSourceFact, ...]:
    bindings = _home_bindings(profile)
    page_ids = list(bindings)
    pages = list(Page.objects.filter(pk__in=page_ids).order_by("id")[:65])
    if len(pages) > 64:
        raise PublicReadError("UNAVAILABLE")
    page_by_id = {str(page.id): page for page in pages}
    routes = list(
        Route.objects.select_related("page")
        .filter(page_id__in=[page.id for page in pages], mode=RouteMode.PRIMARY)
        .order_by("page_id", "id")[:65]
    )
    route_by_page: dict[str, Route] = {}
    for route in routes:
        key = str(route.page_id)
        if key in route_by_page:
            raise PublicReadError("UNAVAILABLE")
        _validate_route(route)
        route_by_page[key] = route
    contents = list(
        PageContent.objects.filter(page_id__in=[page.id for page in pages])
        .order_by("page_id")[:65]
    )
    content_by_page = {str(content.page_id): content for content in contents}
    if len(content_by_page) != len(contents):
        raise PublicReadError("UNAVAILABLE")

    facts: list[_HomeSourceFact] = []
    for page_id in sorted(bindings):
        page = page_by_id.get(page_id)
        if page is None:
            facts.append(_HomeSourceFact(page_id, False, False, None, None, None, ()))
            continue
        route = route_by_page.get(page_id)
        content = content_by_page.get(page_id)
        if route is None or content is None:
            raise PublicReadError("UNAVAILABLE")
        if canonical_payload_hash(content.current_payload) != content.current_hash:
            raise PublicReadError("UNAVAILABLE")
        validate_payload(content.current_payload, page.kind)
        wanted_rows = bindings[page_id]
        price_facts: list[_HomePriceFact] = []
        if wanted_rows:
            fields = content.current_payload["fields"]
            price_rows = fields.get("price_rows")
            indexed = (
                {row["id"]: row for row in price_rows["rows"]}
                if isinstance(price_rows, dict)
                else {}
            )
            if isinstance(price_rows, dict) and len(indexed) != len(price_rows["rows"]):
                raise PublicReadError("UNAVAILABLE")
            for row_id in sorted(wanted_rows):
                row = indexed.get(row_id)
                amounts = (
                    [cell for cell in row["cells"] if cell["kind"] == "amount"]
                    if row is not None
                    else []
                )
                price_facts.append(
                    _HomePriceFact(
                        row_id,
                        amounts[0]["amount"] if len(amounts) == 1 else None,
                        amounts[0]["from"] if len(amounts) == 1 else None,
                    )
                )
        facts.append(
            _HomeSourceFact(
                page_id=page_id,
                present=True,
                visible=page.is_published,
                generation=content.generation,
                payload_hash=content.current_hash,
                primary_target=route.target,
                prices=tuple(price_facts),
            )
        )
    return tuple(facts)


def _home_visible(item: dict, sources: dict[str, _HomeSourceFact]) -> bool:
    source_id = item["source_page_id"]
    if source_id is None:
        return item["fallback_visible"]
    source = sources[source_id]
    return source.visible if source.present else item["fallback_visible"]


def _format_amount(amount: str, from_amount: bool) -> str:
    try:
        value = Decimal(amount)
    except (InvalidOperation, TypeError, ValueError):
        raise PublicReadError("UNAVAILABLE") from None
    if not value.is_finite() or value < 0 or type(from_amount) is not bool:
        raise PublicReadError("UNAVAILABLE")
    text = format(value.normalize(), "f")
    whole, dot, fraction = text.partition(".")
    chunks = [
        whole[max(0, len(whole) - offset - 3):len(whole) - offset]
        for offset in range(0, len(whole), 3)
    ]
    grouped = " ".join(reversed(chunks))
    return ("от " if from_amount else "") + grouped + (dot + fraction if fraction else "") + " ₽"


def _public_image(file: PublicPageMediaFile, alt: str) -> PublicImage:
    return PublicImage(
        url=f"/media/{file.storage_key}",
        mime_type=file.mime_type,
        width=file.width,
        height=file.height,
        alt=alt,
    )


def project_home(
    page: PublicPage,
) -> PublicBlank | PublicHomeDocument | PublicHomeLegacyDocument:
    if not isinstance(page, PublicPage) or page.kind != PageKind.HOME:
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
            or current.kind != PageKind.HOME
        ):
            raise PublicReadError("UNAVAILABLE")
        if not current.is_published:
            return PublicBlank()
        content = current.content
        if canonical_payload_hash(content.current_payload) != content.current_hash:
            raise PublicReadError("UNAVAILABLE")
        media_values = validate_payload(content.current_payload, PageKind.HOME)
        routes = list(Route.objects.select_related("page").filter(page_id=current.id).order_by("id"))
        primary = _primary_route(routes)
        if primary.target != page.primary_target:
            raise PublicReadError("UNAVAILABLE")
        requested = [
            route for route in routes
            if route.target == page.requested_target and route.mode == page.requested_mode
        ]
        if len(requested) != 1:
            raise PublicReadError("UNAVAILABLE")
        _validate_route(requested[0])

        fields = content.current_payload["fields"]
        seo_fields = fields["seo"]
        common = {
            "page_id": current.id,
            "primary_target": primary.target,
            "h1": fields["heading"]["h1"],
            "seo": PublicSeo(
                title=seo_fields["title"],
                description=seo_fields["description"],
                allow_index=seo_fields["allow_index"],
            ),
        }
        profile = fields.get("home_profile")
        if profile is None:
            if media_values:
                raise PublicReadError("UNAVAILABLE")
            if _exact_generation() != current.public_structure_generation:
                raise PublicReadError("UNAVAILABLE")
            return PublicHomeLegacyDocument(
                **common,
                lead=fields["lead"],
                about=fields["about"],
            )
        if len(fields["process_steps"]) != 5:
            raise PublicReadError("UNAVAILABLE")
        first_sources = _capture_home_sources(profile)
        projected_media = project_public_page_media(
            page_id=current.id,
            expected_media=media_values,
        )
        final_sources = _capture_home_sources(profile)
        if first_sources != final_sources:
            raise PublicReadError("UNAVAILABLE")
        final_page = Page.objects.select_related("content").get(pk=current.id)
        if (
            not final_page.is_published
            or final_page.content.generation != content.generation
            or final_page.content.current_hash != content.current_hash
            or _exact_generation() != current.public_structure_generation
        ):
            raise PublicReadError("UNAVAILABLE")
        sources = {fact.page_id: fact for fact in first_sources}
        files = {
            str(file.asset_id): file
            for values in projected_media.values()
            for file in values
        }
        hero = _public_image(files[profile["hero"]["asset_id"]], profile["hero"]["alt"])
        steps = tuple(
            PublicHomeStep(
                title=copy_row["title"],
                body=copy_row["body"],
                image=_public_image(files[media_row["asset_id"]], media_row["alt"]),
            )
            for copy_row, media_row in zip(fields["process_steps"], profile["steps"], strict=True)
        )
        services = tuple(
            PublicHomeService(
                label=item["label"],
                caption=item["caption"],
                target=item["url"],
                image=_public_image(files[item["asset_id"]], item["alt"]),
            )
            for item in profile["services"]
            if _home_visible(item, sources)
        )
        price_groups: list[PublicHomePriceGroup] = []
        for group in profile["prices"]:
            group_source = sources.get(group["source_page_id"])
            if group_source is not None and group_source.present and not group_source.visible:
                continue
            rows: list[PublicHomePriceRow] = []
            for item in group["rows"]:
                if not _home_visible(item, sources):
                    continue
                price_text = item["price_text"]
                if item["source_page_id"] is not None:
                    source = sources[item["source_page_id"]]
                    if source.present and source.visible:
                        price = next(
                            (value for value in source.prices if value.row_id == item["source_row_id"]),
                            None,
                        )
                        if price is None or price.amount is None or price.from_amount is None:
                            continue
                        price_text = _format_amount(price.amount, price.from_amount)
                rows.append(PublicHomePriceRow(item["label"], item["url"], price_text))
            if rows:
                price_groups.append(
                    PublicHomePriceGroup(group["key"], group["label"], group["url"], tuple(rows))
                )
        works = tuple(
            PublicHomeWork(
                label=item["label"],
                photo_count_text=item["photo_count_text"],
                target=item["url"],
                image=_public_image(files[item["asset_id"]], item["alt"]),
            )
            for item in profile["works"]
            if _home_visible(item, sources)
        )
        return PublicHomeDocument(
            **common,
            lead=fields["lead"],
            about=fields["about"],
            hero=hero,
            advantages=tuple(profile["advantages"]),
            comparisons=tuple(
                PublicHomeComparison(
                    item["heading"], tuple(item["bullets"]), item["result_mark"], item["result_text"]
                )
                for item in profile["comparisons"]
            ),
            steps=steps,
            services=services,
            prices=tuple(price_groups),
            photo_strip=_public_image(
                files[profile["photo_strip"]["asset_id"]], profile["photo_strip"]["alt"]
            ),
            works=works,
            reviews_heading=profile["reviews"]["heading"],
            reviews_target=profile["reviews"]["url"],
            reviews_label=profile["reviews"]["label"],
        )
    except PublicReadError:
        raise
    except (
        ContentValidationError,
        DatabaseError,
        KeyError,
        MediaUsageError,
        Page.DoesNotExist,
        PageContent.DoesNotExist,
        TypeError,
        ValueError,
        ValidationError,
    ):
        raise PublicReadError("UNAVAILABLE") from None


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
