from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from rebuild3_importer.content import validate_https, validate_payload
from rebuild3_importer.errors import ManifestError


SHA256 = re.compile(r"^[0-9a-f]{64}$")
SECTIONS = {
    "routes": frozenset({"id", "page_id", "target", "mode", "outcome"}),
    "pages": frozenset({"id", "name", "kind", "parent_id", "position", "is_published", "content_generation", "current", "previous"}),
    "assets": frozenset({"id", "purpose", "source_sha256", "state"}),
    "files": frozenset({"id", "asset_id", "kind", "source_path", "sha256", "byte_size", "mime_type", "width", "height"}),
    "usages": frozenset({"id", "asset_id", "scope", "target_uuid", "slot", "position"}),
    "gallery_albums": frozenset({"id", "page_id", "generation", "position"}),
    "gallery_photos": frozenset({"id", "album_id", "asset_id", "position", "alt"}),
}
SETTINGS = frozenset({
    "id", "structure_generation", "settings_generation", "organization_name", "legal_name",
    "phone_display", "phone_e164", "address", "opening_hours", "contact_email", "map_url",
    "max_url", "telegram_url", "logo_asset_id",
})
VERSION = frozenset({"payload", "sha256", "created_at"})
UTC_TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$")
EXTENSIONS = {
    "image/jpeg": frozenset({"jpg", "jpeg"}), "image/png": frozenset({"png"}),
    "image/webp": frozenset({"webp"}), "image/svg+xml": frozenset({"svg"}),
}
PAGE_KINDS = frozenset({
    "home", "services_master_catalog", "service_catalog", "service_section_overview",
    "service_detail", "articles_catalog", "article", "contacts", "reviews", "actions",
    "gallery_catalog", "gallery_album", "legacy_partner_links", "legacy_director_message",
    "legacy_news_article", "legacy_empty_main", "legacy_news_catalog",
    "legacy_under_construction", "legacy_camera_schedule_text",
})
ROUTE_MODES = frozenset({"PRIMARY", "ALIAS", "REDIRECT"})
SLOT_CAPS = {
    "home": {"hero": 1, "service_cards": 12, "process": 12, "works": 32, "brand_logos": 20},
    "service_catalog": {"hero": 1},
    "service_section_overview": {"hero": 1, "works": 32},
    "service_detail": {"hero": 1, "body": 32, "works": 32},
    "article": {"hero": 1, "body": 32, "works": 32},
    "contacts": {"gallery": 5}, "reviews": {"thumbnail": 32}, "actions": {"banner": 32},
    "legacy_director_message": {"hero": 1}, "legacy_news_article": {"hero": 1},
    "legacy_under_construction": {"hero": 1},
}


@dataclass(frozen=True, slots=True)
class ManifestLimits:
    routes: int
    pages: int
    assets: int
    files: int
    usages: int
    gallery_albums: int
    gallery_photos: int
    canonical_bytes: int
    total_file_bytes: int
    gallery_file_bytes: int
    trusted_svg_sha256: frozenset[str]


@dataclass(frozen=True, slots=True)
class PublicManifest:
    snapshot_id: str
    digest: str
    site_settings: dict[str, Any]
    sections: dict[str, tuple[dict[str, Any], ...]]


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError("duplicate-key")
        result[key] = value
    return result


def _closed(value: Any, fields: frozenset[str], code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or frozenset(value) != fields:
        raise ManifestError(code)
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _uuid(value: Any, code: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ManifestError(code) from exc
    if not isinstance(value, str) or str(parsed) != value:
        raise ManifestError(code)
    return value


def _sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ManifestError(code)
    return value


def _uint(value: Any, code: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < int(positive):
        raise ManifestError(code)
    return value


def _text(value: Any, code: str, cap: int, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if (not isinstance(value, str) or not value or len(value) > cap
            or unicodedata.normalize("NFC", value) != value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ManifestError(code)
    return value


def _source_path(value: Any) -> str:
    value = _text(value, "source-path", 1024)
    assert isinstance(value, str)
    parts = value.split("/")
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10))}
    if (PurePosixPath(value).is_absolute() or "\\" in value or ":" in value or "%" in value
            or any(part in {"", ".", ".."} or part.endswith((".", " "))
                   or any(char.isspace() for char in part)
                   or part.split(".", 1)[0].casefold() in reserved for part in parts)):
        raise ManifestError("source-path")
    if "." not in parts[-1] or parts[-1].startswith("."):
        raise ManifestError("source-extension")
    return value


def target_storage_key(row: dict[str, Any]) -> str:
    asset_id = _uuid(row.get("asset_id"), "file-asset")
    extension = _source_path(row.get("source_path")).rsplit(".", 1)[-1].lower()
    if extension not in EXTENSIONS.get(row.get("mime_type"), frozenset()):
        raise ManifestError("file-extension")
    kind = row.get("kind")
    if kind == "PRIVATE_SOURCE":
        return f"private/sources/{asset_id}/source.{extension}"
    segment = {"MAIN": "main", "PREVIEW": "preview", "LEGACY_PUBLIC": "legacy-public"}.get(kind)
    if segment is None:
        raise ManifestError("file-kind")
    return f"img/{asset_id}/{segment}.{extension}"


def _version(value: Any, *, nullable: bool, expected_kind: str) -> dict[str, list[str]]:
    if value is None and nullable:
        return {}
    row = _closed(value, VERSION, "page-version")
    if not isinstance(row["payload"], dict):
        raise ManifestError("page-payload")
    digest = _sha(row["sha256"], "page-hash")
    if hashlib.sha256(_canonical(row["payload"])).hexdigest() != digest:
        raise ManifestError("page-hash-drift")
    timestamp = _text(row["created_at"], "page-created", 27)
    if UTC_TIMESTAMP.fullmatch(timestamp) is None:
        raise ManifestError("page-created")
    try:
        parsed = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise ManifestError("page-created") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != timestamp:
        raise ManifestError("page-created")
    return validate_payload(row["payload"], expected_kind)


def _https(value: Any, code: str, *, nullable: bool = False) -> None:
    validate_https(value, code, nullable=nullable)


def _route_target(value: Any) -> None:
    value = _text(value, "route-target", 2048)
    assert isinstance(value, str)
    try:
        parsed = urlsplit(value)
        decoded = unquote(parsed.path, errors="strict")
        decoded_query = unquote(parsed.query, errors="strict")
    except (UnicodeDecodeError, ValueError) as exc:
        raise ManifestError("route-target") from exc
    if (re.search(r"%(?![0-9A-Fa-f]{2})", value) or not value.startswith("/")
            or value.startswith("//") or parsed.scheme or parsed.netloc
            or parsed.fragment or parsed.query not in {"", "page=1", "page=2"}
            or "\\" in value or "\\" in decoded
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in decoded + decoded_query)
            or any(part in {".", ".."} for part in decoded.split("/"))):
        raise ManifestError("route-target")


def _settings(row: dict[str, Any]) -> None:
    _uuid(row["id"], "settings-id"); _uuid(row["logo_asset_id"], "settings-logo")
    for field in ("structure_generation", "settings_generation"):
        _uint(row[field], field, positive=True)
    for field, cap in (("organization_name", 120), ("phone_display", 64), ("address", 255),
                       ("opening_hours", 128), ("contact_email", 254)):
        _text(row[field], f"settings-{field}", cap)
    _text(row["legal_name"], "settings-legal", 160, nullable=True)
    phone = _text(row["phone_e164"], "settings-phone", 16)
    if re.fullmatch(r"\+[1-9][0-9]{7,14}", str(phone)) is None:
        raise ManifestError("settings-phone")
    email = row["contact_email"]
    try:
        validate_email(email)
    except ValidationError as exc:
        raise ManifestError("settings-email") from exc
    if not email.isascii() or email.strip() != email:
        raise ManifestError("settings-email")
    _https(row["map_url"], "settings-map")
    _https(row["max_url"], "settings-max", nullable=True)
    _https(row["telegram_url"], "settings-telegram", nullable=True)


def _validate(sections: dict[str, tuple[dict[str, Any], ...]], settings: dict[str, Any], limits: ManifestLimits) -> None:
    ids: dict[str, set[str]] = {}
    for name, fields in SECTIONS.items():
        rows = sections[name]
        if len(rows) != getattr(limits, name):
            raise ManifestError(f"count-{name}")
        ids[name] = set()
        for row in rows:
            _closed(row, fields, f"shape-{name}")
            row_id = _uuid(row["id"], f"id-{name}")
            if row_id in ids[name]:
                raise ManifestError(f"duplicate-{name}")
            ids[name].add(row_id)
    page_ids, asset_ids = ids["pages"], ids["assets"]
    assets = {row["id"]: row for row in sections["assets"]}
    for row in sections["assets"]:
        if row["purpose"] not in {"CONTENT", "SITE_ASSET", "GALLERY_ORIGINAL"} or row["state"] != "READY":
            raise ManifestError("asset-shape")
        _sha(row["source_sha256"], "asset-sha")
    keys: set[str] = set()
    source_casefold: dict[str, str] = {}
    source_descriptors: dict[str, tuple[Any, ...]] = {}
    asset_kinds: set[tuple[str, str]] = set()
    total = gallery = 0
    for row in sections["files"]:
        asset_id = _uuid(row["asset_id"], "file-asset")
        if asset_id not in asset_ids:
            raise ManifestError("file-asset")
        _sha(row["sha256"], "file-sha")
        size = _uint(row["byte_size"], "file-size", positive=True)
        if row["mime_type"] == "image/svg+xml":
            if (row["kind"] == "PRIVATE_SOURCE" or row["width"] is not None or row["height"] is not None
                    or row["sha256"] not in limits.trusted_svg_sha256):
                raise ManifestError("file-svg")
        elif row["mime_type"] in EXTENSIONS:
            dimensions = (row["width"], row["height"])
            if dimensions != (None, None) and not all(
                isinstance(value, int)
                and not isinstance(value, bool)
                and 1 <= value <= 10_000
                for value in dimensions
            ):
                raise ManifestError("file-dimensions")
        else:
            raise ManifestError("file-mime")
        source = _source_path(row["source_path"])
        folded = source.casefold()
        if folded in source_casefold and source_casefold[folded] != source:
            raise ManifestError("source-casefold-collision")
        source_casefold[folded] = source
        descriptor = (
            assets[asset_id]["source_sha256"], row["sha256"], size,
            row["mime_type"], row["width"], row["height"],
        )
        if source in source_descriptors and source_descriptors[source] != descriptor:
            raise ManifestError("source-descriptor-drift")
        source_descriptors[source] = descriptor
        key = target_storage_key(row)
        asset_kind = (asset_id, row["kind"])
        if assets[asset_id]["purpose"] == "GALLERY_ORIGINAL" and row["kind"] != "LEGACY_PUBLIC":
            raise ManifestError("gallery-file-kind")
        if key in keys or asset_kind in asset_kinds:
            raise ManifestError("duplicate-target-key")
        keys.add(key)
        asset_kinds.add(asset_kind)
        total += size
        if assets[asset_id]["purpose"] == "GALLERY_ORIGINAL":
            gallery += size
    if (total, gallery) != (limits.total_file_bytes, limits.gallery_file_bytes):
        raise ManifestError("file-byte-total")
    settings_id = settings["id"]
    pages = {row["id"]: row for row in sections["pages"]}
    expected_usages: set[tuple[str, str, str, int, str]] = {
        ("SITE_SETTINGS", settings_id, "logo", 0, settings["logo_asset_id"])
    }
    for page in sections["pages"]:
        for scope, version, nullable in (
            ("PAGE_CURRENT", page["current"], False),
            ("PAGE_PREVIOUS", page["previous"], True),
        ):
            refs = _version(version, nullable=nullable, expected_kind=page["kind"])
            for slot, asset_list in refs.items():
                expected_usages.update(
                    (scope, page["id"], slot, position, asset_id)
                    for position, asset_id in enumerate(asset_list)
                )
    usage_positions: set[tuple[Any, ...]] = set()
    usage_assets: set[tuple[Any, ...]] = set()
    actual_usages: set[tuple[str, str, str, int, str]] = set()
    for row in sections["usages"]:
        asset_id, target = _uuid(row["asset_id"], "usage-asset"), _uuid(row["target_uuid"], "usage-target")
        position, slot = _uint(row["position"], "usage-position"), _text(row["slot"], "usage-slot", 100)
        scope = row["scope"]
        if asset_id not in asset_ids or scope not in {"PAGE_CURRENT", "PAGE_PREVIOUS", "SITE_SETTINGS"}:
            raise ManifestError("usage-reference")
        if scope != "SITE_SETTINGS" and assets[asset_id]["purpose"] != "CONTENT":
            raise ManifestError("usage-purpose")
        if scope == "SITE_SETTINGS" and (target != settings_id or slot != "logo" or position != 0):
            raise ManifestError("usage-settings")
        if scope != "SITE_SETTINGS" and target not in page_ids:
            raise ManifestError("usage-page")
        if scope == "PAGE_PREVIOUS" and pages[target]["previous"] is None:
            raise ManifestError("usage-previous-missing")
        a, b = (scope, target, slot, position), (scope, target, slot, asset_id)
        if a in usage_positions or b in usage_assets:
            raise ManifestError("duplicate-usage")
        usage_positions.add(a); usage_assets.add(b)
        actual_usages.add((scope, target, str(slot), position, asset_id))
    if actual_usages != expected_usages: raise ManifestError("usage-payload-drift")
    if assets.get(settings["logo_asset_id"], {}).get("purpose") != "SITE_ASSET":
        raise ManifestError("settings-logo-purpose")
    slot_positions: dict[tuple[str, str, str], list[int]] = {}
    for row in sections["usages"]:
        if row["scope"] == "SITE_SETTINGS":
            continue
        page_kind = pages[row["target_uuid"]]["kind"]
        cap = SLOT_CAPS.get(page_kind, {}).get(row["slot"])
        if cap is None:
            raise ManifestError("usage-slot-registry")
        key = (row["scope"], row["target_uuid"], row["slot"])
        slot_positions.setdefault(key, []).append(row["position"])
        if len(slot_positions[key]) > cap:
            raise ManifestError("usage-slot-cap")
    for positions in slot_positions.values():
        if sorted(positions) != list(range(len(positions))):
            raise ManifestError("usage-position-gap")
    sibling_positions: set[tuple[str | None, int]] = set()
    for row in sections["pages"]:
        if row["parent_id"] is not None and _uuid(row["parent_id"], "page-parent") not in page_ids:
            raise ManifestError("page-parent")
        if row["parent_id"] == row["id"] or row["kind"] not in PAGE_KINDS:
            raise ManifestError("page-shape")
        _text(row["name"], "page-name", 500); _uint(row["position"], "page-position")
        _uint(row["content_generation"], "content-generation", positive=True)
        sibling = (row["parent_id"], row["position"])
        if sibling in sibling_positions: raise ManifestError("page-sibling-position")
        sibling_positions.add(sibling)
        if not isinstance(row["is_published"], bool): raise ManifestError("page-published")
    for page_id in page_ids:
        seen: set[str] = set()
        cursor: str | None = page_id
        while cursor is not None:
            if cursor in seen: raise ManifestError("page-cycle")
            seen.add(cursor)
            cursor = pages[cursor]["parent_id"]
    route_targets: set[str] = set()
    primary_pages: set[str] = set()
    for row in sections["routes"]:
        if _uuid(row["page_id"], "route-page") not in page_ids: raise ManifestError("route-page")
        _uuid(row["id"], "route-id"); _route_target(row["target"])
        if row["mode"] not in ROUTE_MODES: raise ManifestError("route-mode")
        page_kind = pages[row["page_id"]]["kind"]
        if row["outcome"] == "service_wash_legacy_alias":
            if row["mode"] != "ALIAS" or page_kind != "service_detail": raise ManifestError("route-outcome")
        elif row["outcome"] != page_kind:
            raise ManifestError("route-outcome")
        if row["target"] in route_targets: raise ManifestError("route-target-duplicate")
        route_targets.add(row["target"])
        if row["mode"] == "PRIMARY":
            if row["page_id"] in primary_pages: raise ManifestError("route-primary-duplicate")
            primary_pages.add(row["page_id"])
    if primary_pages != page_ids: raise ManifestError("route-primary-missing")
    album_positions: set[int] = set(); album_pages: set[str] = set()
    for row in sections["gallery_albums"]:
        if _uuid(row["page_id"], "album-page") not in page_ids: raise ManifestError("album-page")
        if pages[row["page_id"]]["kind"] != "gallery_album": raise ManifestError("album-page-kind")
        _uint(row["generation"], "album-generation", positive=True); _uint(row["position"], "album-position")
        if row["position"] in album_positions or row["page_id"] in album_pages: raise ManifestError("album-unique")
        album_positions.add(row["position"]); album_pages.add(row["page_id"])
    if sorted(album_positions) != list(range(len(album_positions))): raise ManifestError("album-position-gap")
    photo_positions: set[tuple[str, int]] = set()
    positions_by_album: dict[str, list[int]] = {album_id: [] for album_id in ids["gallery_albums"]}
    for row in sections["gallery_photos"]:
        if _uuid(row["album_id"], "photo-album") not in ids["gallery_albums"] or _uuid(row["asset_id"], "photo-asset") not in asset_ids:
            raise ManifestError("photo-reference")
        _uint(row["position"], "photo-position"); _text(row["alt"], "photo-alt", 1000)
        key = (row["album_id"], row["position"])
        if (key in photo_positions
                or assets[row["asset_id"]]["purpose"] != "GALLERY_ORIGINAL"):
            raise ManifestError("photo-shape")
        photo_positions.add(key)
        positions_by_album[row["album_id"]].append(row["position"])
    for positions in positions_by_album.values():
        if sorted(positions) != list(range(len(positions))): raise ManifestError("photo-position-gap")


def parse_public_manifest(raw: bytes, limits: ManifestLimits) -> PublicManifest:
    if not isinstance(raw, bytes) or len(raw) > limits.canonical_bytes: raise ManifestError("manifest-bytes")
    try:
        root = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ManifestError("number")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError("manifest-json") from exc
    root = _closed(root, frozenset({"version", "snapshot_id", "site_settings", "sections", "digest"}), "manifest-shape")
    if type(root["version"]) is not int or root["version"] != 1: raise ManifestError("manifest-version")
    snapshot_id = _text(root["snapshot_id"], "snapshot-id", 200); digest = _sha(root["digest"], "manifest-digest")
    settings = _closed(root["site_settings"], SETTINGS, "settings-shape")
    _settings(settings)
    sections_raw = _closed(root["sections"], frozenset(SECTIONS), "sections-shape")
    sections = {name: tuple(rows) if isinstance(rows, list) else () for name, rows in sections_raw.items()}
    if any(not isinstance(sections_raw[name], list) for name in SECTIONS): raise ManifestError("section-type")
    unsigned = {key: root[key] for key in ("version", "snapshot_id", "site_settings", "sections")}
    canonical = _canonical(unsigned)
    if len(canonical) > limits.canonical_bytes or hashlib.sha256(canonical).hexdigest() != digest: raise ManifestError("manifest-digest")
    if raw != _canonical(root):
        raise ManifestError("manifest-noncanonical")
    _validate(sections, settings, limits)
    return PublicManifest(str(snapshot_id), digest, settings, sections)
