from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass
from urllib.parse import urlsplit
from xml.etree import ElementTree

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.models.expressions import RawSQL
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .content import ContentValidationError, canonical_payload_hash, validate_payload
from .models import Page, PageContent, Route, RouteMode, SiteSettings


_CAP = 50_000
_MAX_XML_BYTES = 50 * 1024 * 1024
_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_BAD_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")


class PublicSeoError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _Configuration:
    origin: str
    robots_profile: str


@dataclass(frozen=True, slots=True)
class _SitemapSnapshot:
    stamp: str
    locations: tuple[str, ...]


def _host_is_valid(host: str | None) -> bool:
    if not host or host != host.lower():
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return host == "localhost" or all(_HOST_LABEL.fullmatch(label) for label in host.split("."))


def _configuration() -> _Configuration:
    origin = getattr(settings, "PUBLIC_ORIGIN", None)
    profile = getattr(settings, "SEO_ROBOTS_PROFILE", None)
    if type(origin) is not str or profile not in {"deny-all", "production"}:
        raise PublicSeoError
    try:
        origin.encode("ascii", errors="strict")
        parsed = urlsplit(origin)
        port = parsed.port
    except (UnicodeError, ValueError, TypeError):
        raise PublicSeoError from None
    if (
        not origin
        or any(ord(char) < 33 or ord(char) == 127 for char in origin)
        or parsed.scheme not in {"http", "https"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or not _host_is_valid(parsed.hostname)
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise PublicSeoError
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    normalized = f"{parsed.scheme}://{host}" + (f":{port}" if port is not None else "")
    if origin != normalized or (profile == "production" and parsed.scheme != "https"):
        raise PublicSeoError
    if profile == "deny-all" and parsed.scheme == "http" and parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
        "host.docker.internal",
    }:
        raise PublicSeoError
    return _Configuration(origin=origin, robots_profile=profile)


def _bounded(queryset):
    rows = list(queryset[: _CAP + 1])
    if len(rows) > _CAP:
        raise PublicSeoError
    return rows


def _primary_target_is_valid(target: object) -> bool:
    if type(target) is not str or not target.startswith("/") or target.startswith("//"):
        return False
    try:
        target.encode("ascii", errors="strict")
        parsed = urlsplit(target)
    except (UnicodeError, ValueError, TypeError):
        return False
    return not (
        _BAD_PERCENT.search(target)
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or "\\" in target
        or any(ord(char) < 32 or ord(char) == 127 or char.isspace() for char in target)
        or any(segment in {".", ".."} for segment in parsed.path.split("/"))
    )


def _capture_sitemap(configuration: _Configuration) -> _SitemapSnapshot:
    with transaction.atomic():
        settings_rows = _bounded(
            SiteSettings.objects.annotate(row_version=RawSQL("xmin::text", []))
            .filter(singleton_key=True)
            .values("id", "structure_generation", "row_version")
            .order_by("id")
        )
        pages = _bounded(
            Page.objects.annotate(row_version=RawSQL("xmin::text", []))
            .values("id", "kind", "is_published", "row_version")
            .order_by("id")
        )
        routes = _bounded(
            Route.objects.annotate(row_version=RawSQL("xmin::text", []))
            .filter(mode=RouteMode.PRIMARY)
            .values("id", "page_id", "target", "mode", "outcome", "row_version")
            .order_by("page_id", "id")
        )
        contents = _bounded(
            PageContent.objects.annotate(row_version=RawSQL("xmin::text", []))
            .values(
                "page_id",
                "generation",
                "current_payload",
                "current_hash",
                "row_version",
            )
            .order_by("page_id")
        )
    if (
        len(settings_rows) != 1
        or type(settings_rows[0]["structure_generation"]) is not int
        or settings_rows[0]["structure_generation"] < 1
        or len(pages) != len(routes)
        or len(pages) != len(contents)
    ):
        raise PublicSeoError
    routes_by_page = {row["page_id"]: row for row in routes}
    contents_by_page = {row["page_id"]: row for row in contents}
    if len(routes_by_page) != len(routes) or len(contents_by_page) != len(contents):
        raise PublicSeoError

    evidence: list[dict[str, object]] = []
    locations: list[str] = []
    for page in pages:
        route = routes_by_page.get(page["id"])
        content = contents_by_page.get(page["id"])
        if route is None or content is None or route["mode"] != RouteMode.PRIMARY:
            raise PublicSeoError
        target = route["target"]
        if (
            not _primary_target_is_valid(target)
            or route["outcome"] != page["kind"]
            or canonical_payload_hash(content["current_payload"]) != content["current_hash"]
        ):
            raise PublicSeoError
        validate_payload(content["current_payload"], page["kind"])
        allow_index = content["current_payload"]["fields"]["seo"]["allow_index"]
        if page["is_published"] and allow_index:
            locations.append(configuration.origin + target)
        evidence.append(
            {
                "page": [str(page["id"]), page["kind"], page["is_published"], page["row_version"]],
                "route": [str(route["id"]), target, route["outcome"], route["row_version"]],
                "content": [
                    content["generation"],
                    content["current_hash"],
                    content["row_version"],
                    allow_index,
                ],
            }
        )
    ordered = tuple(sorted(locations))
    if len(ordered) != len(set(ordered)):
        raise PublicSeoError
    encoded = json.dumps(
        {
            "settings": settings_rows,
            "pages": evidence,
            "locations": ordered,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return _SitemapSnapshot(hashlib.sha256(encoded).hexdigest(), ordered)


def _sitemap_xml(snapshot: _SitemapSnapshot) -> bytes:
    root = ElementTree.Element("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})
    for location in snapshot.locations:
        url = ElementTree.SubElement(root, "url")
        ElementTree.SubElement(url, "loc").text = location
    body = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
    if len(body) > _MAX_XML_BYTES:
        raise PublicSeoError
    return body


def _robots_text(configuration: _Configuration) -> bytes:
    if configuration.robots_profile == "deny-all":
        return b"User-agent: *\nDisallow: /\n"
    return (
        "User-agent: *\n"
        "Disallow: /manage/\n"
        "Disallow: /cgi-bin\n"
        "Disallow: /manager/\n"
        "Disallow: /assets/components/\n"
        "Disallow: /core/\n"
        "Disallow: /connectors/\n"
        "Disallow: /index.php\n"
        "Disallow: /*?\n"
        "Allow: /gallery-of-works/?page=1$\n"
        "Allow: /gallery-of-works/?page=2$\n"
        f"Sitemap: {configuration.origin}/sitemap.xml\n"
    ).encode("utf-8")


def _closed(status: int, body: str = "") -> HttpResponse:
    response = HttpResponse(body, status=status, content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _response(request: HttpRequest, body: bytes, content_type: str) -> HttpResponse:
    response = HttpResponse(b"" if request.method == "HEAD" else body, content_type=content_type)
    response["Content-Length"] = str(len(body))
    response["Cache-Control"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@csrf_exempt
def sitemap_view(request: HttpRequest) -> HttpResponse:
    if request.method not in {"GET", "HEAD"}:
        response = _closed(405)
        response["Allow"] = "GET, HEAD"
        return response
    try:
        configuration = _configuration()
        first = _capture_sitemap(configuration)
        body = _sitemap_xml(first)
        second = _capture_sitemap(configuration)
        if first.stamp != second.stamp:
            raise PublicSeoError
        return _response(request, body, "application/xml; charset=utf-8")
    except (
        ContentValidationError,
        DatabaseError,
        KeyError,
        PublicSeoError,
        TypeError,
        ValidationError,
        ValueError,
    ):
        return _closed(503, "SITEMAP_UNAVAILABLE")


@csrf_exempt
def robots_view(request: HttpRequest) -> HttpResponse:
    if request.method not in {"GET", "HEAD"}:
        response = _closed(405)
        response["Allow"] = "GET, HEAD"
        return response
    try:
        body = _robots_text(_configuration())
        return _response(request, body, "text/plain; charset=utf-8")
    except (PublicSeoError, TypeError, ValueError):
        return _closed(503, "ROBOTS_UNAVAILABLE")
