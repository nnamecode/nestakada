from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from modules.media.api import MediaUsageError, project_public_site_logo

from .models import PageKind, SiteSettings
from .public import (
    PublicBlank,
    PublicEmptyDocument,
    PublicHomeDocument,
    PublicHomeLegacyDocument,
    PublicLegacyTextDocument,
    PublicPage,
    PublicPartnerLinksDocument,
    PublicReadError,
    PublicRedirect,
    project_home,
    project_legacy_plain,
    project_public_navigation,
    resolve_public_target,
)


_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_SUPPORTED = {
    PageKind.HOME,
    PageKind.LEGACY_PARTNER_LINKS,
    PageKind.LEGACY_EMPTY_MAIN,
    PageKind.LEGACY_UNDER_CONSTRUCTION,
    PageKind.LEGACY_CAMERA_SCHEDULE_TEXT,
}
_NAVIGATION_IDENTITIES = (
    ("Акции", "/actions"),
    ("Галерея работ", "/gallery-of-works/"),
    ("Отзывы", "/reviews"),
    ("Статьи", "/articles/"),
    ("Контакты", "/contacts"),
)
_HEADER_MENU = (
    ("Услуги и цены", "/#es-services"),
    ("Акции", "/actions"),
    ("Наши работы", "/gallery-of-works/"),
    ("Отзывы", "/reviews"),
    ("Статьи", "/articles/"),
    ("Контакты", "/contacts"),
)


class PublicHttpError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _SiteSnapshot:
    settings_id: uuid.UUID
    settings_generation: int
    structure_generation: int
    organization_name: str
    phone_display: str
    phone_e164: str
    address: str
    opening_hours: str
    map_url: str
    logo_asset_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PublicMenuItem:
    label: str
    target: str


@dataclass(frozen=True, slots=True)
class PublicSiteShell:
    organization_name: str
    phone_display: str
    phone_e164: str
    address: str
    opening_hours: str
    map_url: str
    logo_url: str
    logo_mime_type: str
    logo_width: int | None
    logo_height: int | None
    menu: tuple[PublicMenuItem, ...]


def _constant(body: str, status: int) -> HttpResponse:
    response = HttpResponse(body, status=status, content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "no-store"
    return response


def _blank() -> HttpResponse:
    response = HttpResponse(b"", status=200)
    response["Cache-Control"] = "no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _trusted_target(request: HttpRequest) -> str:
    target = request.META.get("HTTP_X_ESTAKADA_REQUEST_TARGET")
    if not isinstance(target, str) or not 1 <= len(target) <= 2048:
        raise PublicHttpError
    try:
        target.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        raise PublicHttpError from None
    if _PERCENT.search(target):
        raise PublicHttpError
    try:
        parsed = urlsplit(target)
        decoded_path = unquote(parsed.path, errors="strict")
    except (UnicodeDecodeError, ValueError):
        raise PublicHttpError from None
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or not parsed.path.startswith("/")
        or "\\" in target
        or any(ord(char) < 32 or ord(char) == 127 or char.isspace() for char in target)
        or decoded_path != request.path_info
    ):
        raise PublicHttpError
    return target


def _capture_site_snapshot() -> _SiteSnapshot:
    try:
        rows = list(
            SiteSettings.objects.filter(singleton_key=True)
            .values(
                "id",
                "settings_generation",
                "structure_generation",
                "organization_name",
                "phone_display",
                "phone_e164",
                "address",
                "opening_hours",
                "map_url",
                "logo_asset_id",
            )[:2]
        )
        if len(rows) != 1:
            raise PublicHttpError
        row = rows[0]
        if (
            type(row["id"]) is not uuid.UUID
            or type(row["logo_asset_id"]) is not uuid.UUID
            or type(row["settings_generation"]) is not int
            or row["settings_generation"] < 1
            or type(row["structure_generation"]) is not int
            or row["structure_generation"] < 1
            or any(
                type(row[name]) is not str or not row[name]
                for name in (
                    "organization_name",
                    "phone_display",
                    "phone_e164",
                    "address",
                    "opening_hours",
                    "map_url",
                )
            )
        ):
            raise PublicHttpError
        return _SiteSnapshot(
            settings_id=row["id"],
            settings_generation=row["settings_generation"],
            structure_generation=row["structure_generation"],
            organization_name=row["organization_name"],
            phone_display=row["phone_display"],
            phone_e164=row["phone_e164"],
            address=row["address"],
            opening_hours=row["opening_hours"],
            map_url=row["map_url"],
            logo_asset_id=row["logo_asset_id"],
        )
    except PublicHttpError:
        raise
    except (DatabaseError, KeyError, TypeError, ValueError):
        raise PublicHttpError from None


def _validate_menu(navigation) -> tuple[PublicMenuItem, ...]:
    roots = {(item.name, item.primary_target) for item in navigation}
    if len(roots) != len(navigation) or any(identity not in roots for identity in _NAVIGATION_IDENTITIES):
        raise PublicHttpError
    return tuple(PublicMenuItem(*item) for item in _HEADER_MENU)


def _same_capture(first: _SiteSnapshot, final: _SiteSnapshot) -> bool:
    return (
        first.settings_id,
        first.settings_generation,
        first.structure_generation,
        first.logo_asset_id,
    ) == (
        final.settings_id,
        final.settings_generation,
        final.structure_generation,
        final.logo_asset_id,
    )


def public_page_view(request: HttpRequest) -> HttpResponse:
    if request.method not in {"GET", "HEAD"}:
        response = _constant("METHOD_NOT_ALLOWED", 405)
        response["Allow"] = "GET, HEAD"
        return response
    try:
        target = _trusted_target(request)
    except PublicHttpError:
        return _constant("INVALID_REQUEST_TARGET", 400)
    if request.path_info.startswith("/manage/") or request.path_info.startswith("/media/"):
        return _constant("NOT_FOUND", 404)
    try:
        resolved = resolve_public_target(target)
    except PublicReadError as exc:
        return _constant("NOT_FOUND" if exc.code == "NOT_FOUND" else "UNAVAILABLE", 404 if exc.code == "NOT_FOUND" else 503)
    if isinstance(resolved, PublicBlank):
        return _blank()
    if isinstance(resolved, PublicRedirect):
        response = HttpResponse(b"", status=301)
        response["Location"] = resolved.primary_target
        response["Cache-Control"] = "public, max-age=0, must-revalidate"
        return response
    if not isinstance(resolved, PublicPage) or resolved.kind not in _SUPPORTED:
        return _constant("UNAVAILABLE", 503)
    try:
        first = _capture_site_snapshot()
        document = (
            project_home(resolved)
            if resolved.kind == PageKind.HOME
            else project_legacy_plain(resolved)
        )
        if isinstance(document, PublicBlank):
            return _blank()
        if not isinstance(
            document,
            (
                PublicPartnerLinksDocument,
                PublicEmptyDocument,
                PublicLegacyTextDocument,
                PublicHomeDocument,
                PublicHomeLegacyDocument,
            ),
        ):
            raise PublicHttpError
        logo = project_public_site_logo(
            settings_id=first.settings_id,
            logo_asset_id=first.logo_asset_id,
        )
        menu = _validate_menu(project_public_navigation())
        final = _capture_site_snapshot()
        if not _same_capture(first, final):
            raise PublicHttpError
        shell = PublicSiteShell(
            organization_name=first.organization_name,
            phone_display=first.phone_display,
            phone_e164=first.phone_e164,
            address=first.address,
            opening_hours=first.opening_hours,
            map_url=first.map_url,
            logo_url=f"/media/{logo.storage_key}",
            logo_mime_type=logo.mime_type,
            logo_width=logo.width,
            logo_height=logo.height,
            menu=menu,
        )
        is_home = isinstance(document, PublicHomeDocument)
        is_legacy_home = isinstance(document, PublicHomeLegacyDocument)
        context = {
            "shell": shell,
            "document": document,
            "canonical_target": document.primary_target,
            "robots": "index, follow" if document.seo.allow_index else "noindex, nofollow",
            "intro_html": (
                mark_safe(document.intro)
                if isinstance(document, PublicLegacyTextDocument)
                else mark_safe(document.lead)
                if is_legacy_home
                else ""
            ),
            "body_html": (
                mark_safe(document.body)
                if isinstance(document, PublicLegacyTextDocument)
                else mark_safe(document.about)
                if is_legacy_home
                else ""
            ),
            "lead_html": mark_safe(document.lead) if is_home or is_legacy_home else "",
            "about_html": mark_safe(document.about) if is_home or is_legacy_home else "",
        }
        html = render_to_string(
            "pages/public_home.html" if is_home else "pages/public_legacy.html",
            context,
        )
    except (MediaUsageError, PublicHttpError, PublicReadError, DatabaseError):
        return _constant("UNAVAILABLE", 503)
    response = HttpResponse(b"" if request.method == "HEAD" else html, content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "public, max-age=0, must-revalidate"
    response["X-Content-Type-Options"] = "nosniff"
    return response
