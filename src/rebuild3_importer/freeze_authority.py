from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from rebuild3_importer.freeze import (
    ApprovedPage,
    ApprovedRoute,
    EXACT_PAGES,
    EXACT_ROUTES,
    EXACT_SOURCE_MEDIA,
    MAX_PUBLIC_MEDIA_FACTS,
    MAX_PUBLIC_PAGES,
    MAX_PUBLIC_ROUTES,
    MAX_PUBLIC_SHARED,
    PUBLIC_MEDIA_SQL,
    PUBLIC_PAGES_SQL,
    PUBLIC_ROUTES_SQL,
    PUBLIC_SHARED_SQL,
    FreezeError,
    _canonical,
    _guarded_rows,
    _source_fact,
    _timestamp,
    _validate_shared,
)
from rebuild3_importer.source import SNAPSHOT_ID, SourceExecutor, SourceSession
from rebuild3_importer.payload_transform import (
    target_page_kind,
    transform_legacy_payload,
)
from rebuild3_importer.service_media import bind_service_media


@dataclass(frozen=True, slots=True, repr=False)
class FreezeCapture:
    """Public-only facts from one bounded RRRO authority capture."""

    pages: tuple[tuple[object, ...], ...]
    routes: tuple[tuple[object, ...], ...]
    shared: tuple[tuple[object, ...], ...]
    media: tuple[tuple[object, ...], ...]


@dataclass(frozen=True, slots=True, repr=False)
class _FrozenMap:
    items: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True, repr=False)
class _FrozenList:
    items: tuple[object, ...]


def _freeze_value(value: object) -> object:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return _timestamp(value)
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise FreezeError("freeze-capture-value")
        return _FrozenMap(tuple(
            (key, _freeze_value(item)) for key, item in sorted(value.items())
        ))
    if isinstance(value, list):
        return _FrozenList(tuple(_freeze_value(item) for item in value))
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    if value is None or type(value) in (str, int, bool):
        return value
    raise FreezeError("freeze-capture-value")


def _capture_value(value: object) -> object:
    if isinstance(value, _FrozenMap):
        return {key: _capture_value(item) for key, item in value.items}
    if isinstance(value, _FrozenList):
        return [_capture_value(item) for item in value.items]
    if isinstance(value, tuple):
        return [_capture_value(item) for item in value]
    return value


def _thaw_value(value: object) -> object:
    if isinstance(value, _FrozenMap):
        return {key: _thaw_value(item) for key, item in value.items}
    if isinstance(value, _FrozenList):
        return [_thaw_value(item) for item in value.items]
    if isinstance(value, tuple):
        return tuple(_thaw_value(item) for item in value)
    return value


def freeze_capture_digest(capture: FreezeCapture) -> str:
    if not isinstance(capture, FreezeCapture):
        raise FreezeError("freeze-capture")
    return hashlib.sha256(
        _canonical({
            "pages": _capture_value(capture.pages),
            "routes": _capture_value(capture.routes),
            "shared": _capture_value(capture.shared),
            "media": _capture_value(capture.media),
        })
    ).hexdigest()


def _literal_page_route_inputs() -> tuple[
    tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]
]:
    """Read the closed package set; do not introduce a second package format."""

    from content.dev09_migration_apply import (
        _combined_payload,
        _diagnostics_payload,
        _expected_payload,
        _leading_price_payload,
        _parent_payload,
        _read_combined_infographic_package,
        _read_combined_services_package,
        _read_diagnostics_package,
        _read_leading_price_package,
        _read_package,
        _read_planned_maintenance_package,
        _read_remaining_content_package,
        _read_service_details_package,
        _read_service_roots_package,
        _read_services_package,
        _remaining_payload,
        _service_detail_payload,
        _service_root_payload,
        _services_payload,
    )
    from content.dev10_gallery_apply import (
        _payload as _gallery_payload,
        _read_package as _read_gallery_package,
    )
    from content.dev12_home_apply import (
        _read_package as _read_home_package,
        _target_payload,
    )

    articles = _read_package()
    services = _read_services_package()
    roots = _read_service_roots_package()
    details = _read_service_details_package(roots)
    planned = _read_planned_maintenance_package(services)
    leading = _read_leading_price_package(roots)
    diagnostics = _read_diagnostics_package(services)
    combined = _read_combined_services_package()
    infographic = _read_combined_infographic_package()
    remaining = _read_remaining_content_package()
    gallery = _read_gallery_package()
    home = _read_home_package()

    rendered: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]] = []
    rendered.extend((page, _expected_payload(page), None) for page in articles["pages"])
    rendered.append((services["page"], _services_payload(services["page"]), None))
    rendered.extend((page, _service_root_payload(page), None) for page in roots["pages"])
    rendered.extend((page, _service_detail_payload(page), None) for page in details["pages"])
    rendered.extend((page, _service_detail_payload(page), None) for page in planned["pages"])
    rendered.extend((page, _leading_price_payload(page), None) for page in leading["pages"])
    rendered.extend((page, _diagnostics_payload(page), None) for page in diagnostics["pages"])
    rendered.extend(
        (page, _combined_payload(page, infographic), None)
        for page in combined["pages"]
    )
    rendered.extend(
        (page, _remaining_payload(page, remaining), page["profile"])
        for page in remaining["pages"]
    )
    rendered.append((gallery["root"], _gallery_payload(gallery["root"]), None))
    rendered.extend(
        (page, _gallery_payload(page), None) for page in gallery["albums"]
    )

    pages: list[dict[str, Any]] = []
    home_id = home["home"]["page_id"]
    for descriptor, initial_payload, profile in rendered:
        is_home = descriptor["page_id"] == home_id
        source_current = _target_payload(home) if is_home else initial_payload
        source_previous = _parent_payload() if is_home else None
        target_current = transform_legacy_payload(
            source_current,
            source_kind=descriptor["kind"],
            page_url=descriptor["url"],
            profile=home["profile"] if is_home else profile,
            page_name=descriptor["name"],
        )
        target_current = bind_service_media(target_current, descriptor["page_id"])
        target_previous = (
            transform_legacy_payload(
                source_previous,
                source_kind=descriptor["kind"],
                page_url=descriptor["url"],
            )
            if source_previous is not None else None
        )
        pages.append({
            "id": descriptor["page_id"],
            "name": descriptor["name"],
            "kind": descriptor["kind"],
            "parent_id": descriptor["parent_id"],
            "position": descriptor["position"],
            "generation": 2 if is_home else 1,
            "source_current_payload": source_current,
            "source_previous_payload": source_previous,
            "current_payload": target_current,
            "previous_payload": target_previous,
            "target": descriptor["url"],
        })

    routes = [{
        "page_id": page["id"],
        "target": page["target"],
        "source_kind": "primary",
        "source_is_legacy": True,
        "mode": "PRIMARY",
        "outcome": target_page_kind(page["kind"]),
    } for page in pages]
    for row in combined["routes"]:
        if row["kind"] == "alias":
            routes.append({
                "page_id": row["page_id"],
                "target": row["target"],
                "source_kind": "alias",
                "source_is_legacy": row["is_legacy"],
                "mode": "ALIAS",
                "outcome": "service_wash_legacy_alias",
            })
    routes.append({
        "page_id": gallery["root"]["page_id"],
        "target": gallery["root"]["page2_alias"],
        "source_kind": "alias",
        "source_is_legacy": True,
        "mode": "ALIAS",
        "outcome": gallery["root"]["kind"],
    })
    return tuple(pages), tuple(routes)


def _payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def compose_page_route_authority(
    capture: FreezeCapture,
) -> tuple[tuple[ApprovedPage, ...], tuple[ApprovedRoute, ...]]:
    """Bind literal Page/Route packages to captured runtime identities."""

    if not isinstance(capture, FreezeCapture):
        raise FreezeError("freeze-capture")
    page_inputs, route_inputs = _literal_page_route_inputs()
    expected_pages = {row["id"]: row for row in page_inputs}
    expected_routes = {row["target"]: row for row in route_inputs}
    if (
        len(page_inputs) != EXACT_PAGES
        or len(expected_pages) != EXACT_PAGES
        or len(route_inputs) != EXACT_ROUTES
        or len(expected_routes) != EXACT_ROUTES
        or "/gallery-of-works/?page=1" in expected_routes
    ):
        raise FreezeError("authority-literal-count")

    approved_pages: list[ApprovedPage] = []
    seen_pages: set[str] = set()
    for frozen_row in capture.pages:
        row = _thaw_value(frozen_row)
        if not isinstance(row, tuple) or len(row) != 17:
            raise FreezeError("authority-page-shape")
        (
            page_id, name, source_kind, parent_id, position, is_published,
            generation, current_sequence, current_schema, source_current_payload,
            source_current_hash, _current_created_at, newer_exists,
            source_previous_payload, source_previous_hash, _previous_created_at,
            previous_schema,
        ) = row
        page_key = str(page_id)
        expected = expected_pages.get(page_key)
        if expected is None or page_key in seen_pages:
            raise FreezeError("authority-page-unapproved")
        source_current = expected["source_current_payload"]
        source_previous = expected["source_previous_payload"]
        current_payload = expected["current_payload"]
        previous_payload = expected["previous_payload"]
        current_hash = _payload_hash(source_current)
        previous_hash = (
            None if source_previous is None else _payload_hash(source_previous)
        )
        expected_previous_schema = (
            None if source_previous is None else source_previous["schema_version"]
        )
        if (
            name != expected["name"]
            or source_kind != expected["kind"]
            or (None if parent_id is None else str(parent_id)) != expected["parent_id"]
            or position != expected["position"]
            or is_published is not True
            or generation != expected["generation"]
            or current_sequence != expected["generation"]
            or current_schema != source_current["schema_version"]
            or source_current_payload != source_current
            or source_current_hash != current_hash
            or newer_exists is not False
            or source_previous_payload != source_previous
            or source_previous_hash != previous_hash
            or previous_schema != expected_previous_schema
        ):
            raise FreezeError("authority-page-drift")
        seen_pages.add(page_key)
        approved_pages.append(ApprovedPage(
            id=uuid.UUID(page_key),
            name=expected["name"],
            source_kind=expected["kind"],
            kind=target_page_kind(expected["kind"]),
            parent_id=(
                None if expected["parent_id"] is None
                else uuid.UUID(expected["parent_id"])
            ),
            position=expected["position"],
            is_published=True,
            content_generation=expected["generation"],
            source_current_schema=source_current["schema_version"],
            source_current_hash=current_hash,
            source_current_created_at=_timestamp(_current_created_at),
            current_payload=current_payload,
            source_previous_schema=expected_previous_schema,
            source_previous_hash=previous_hash,
            source_previous_created_at=(
                None if _previous_created_at is None
                else _timestamp(_previous_created_at)
            ),
            previous_payload=previous_payload,
        ))
    if seen_pages != set(expected_pages):
        raise FreezeError("authority-page-count")

    approved_routes: list[ApprovedRoute] = []
    seen_routes: set[str] = set()
    for frozen_row in capture.routes:
        row = _thaw_value(frozen_row)
        if not isinstance(row, tuple) or len(row) != 5:
            raise FreezeError("authority-route-shape")
        route_id, page_id, target, source_kind, source_is_legacy = row
        expected = expected_routes.get(target)
        if expected is None or target in seen_routes:
            raise FreezeError("authority-route-unapproved")
        if (
            str(page_id) != expected["page_id"]
            or source_kind != expected["source_kind"]
            or source_is_legacy is not expected["source_is_legacy"]
        ):
            raise FreezeError("authority-route-drift")
        seen_routes.add(target)
        approved_routes.append(ApprovedRoute(
            id=uuid.UUID(str(route_id)),
            page_id=uuid.UUID(expected["page_id"]),
            target=target,
            source_kind=source_kind,
            source_is_legacy=source_is_legacy,
            mode=expected["mode"],
            outcome=expected["outcome"],
        ))
    if seen_routes != set(expected_routes):
        raise FreezeError("authority-route-count")
    return tuple(approved_pages), tuple(approved_routes)


def _validate_media_capture(rows: tuple[tuple[object, ...], ...]) -> None:
    facts: set[tuple[str, str]] = set()
    counts = {"asset": 0, "file": 0}
    widths = {"asset": 6, "file": 5, "usage": 7, "home": 2}
    for row in rows:
        if len(row) != 3:
            raise FreezeError("capture-media-shape")
        entity, identity, fact = row
        key = (entity, identity)
        normalized = _source_fact(fact)
        if (
            entity not in widths
            or not isinstance(identity, str)
            or not identity
            or not isinstance(normalized, tuple)
            or len(normalized) != widths[entity]
            or (entity == "usage" and normalized[4] not in ("eligible", "excluded"))
            or key in facts
        ):
            raise FreezeError("capture-media-shape")
        facts.add(key)
        if entity in counts:
            counts[entity] += 1
    if counts != {"asset": EXACT_SOURCE_MEDIA, "file": EXACT_SOURCE_MEDIA}:
        raise FreezeError("capture-media-count")


def _validate_public_identities(
    pages: tuple[tuple[object, ...], ...],
    routes: tuple[tuple[object, ...], ...],
) -> None:
    page_ids = [row[0] for row in pages]
    route_ids = [row[0] for row in routes]
    route_targets = [row[2] for row in routes]
    if (
        any(not isinstance(value, uuid.UUID) for value in page_ids + route_ids)
        or len(set(page_ids)) != len(page_ids)
        or len(set(route_ids)) != len(route_ids)
        or any(not isinstance(value, str) or not value for value in route_targets)
        or len(set(route_targets)) != len(route_targets)
    ):
        raise FreezeError("capture-public-identity")


def capture_source_authority(
    executor: SourceExecutor,
    session: SourceSession,
) -> FreezeCapture:
    """Capture public facts once; no staff, grants, requests or file bytes."""

    if (
        not isinstance(session, SourceSession)
        or not isinstance(session.snapshot_id, str)
        or SNAPSHOT_ID.fullmatch(session.snapshot_id) is None
    ):
        raise FreezeError("freeze-capture-input")
    pages = _guarded_rows(
        executor, PUBLIC_PAGES_SQL, session, 21, MAX_PUBLIC_PAGES,
    )
    routes = _guarded_rows(
        executor, PUBLIC_ROUTES_SQL, session, 9, MAX_PUBLIC_ROUTES,
    )
    shared = _guarded_rows(
        executor, PUBLIC_SHARED_SQL, session, 16, MAX_PUBLIC_SHARED,
    )
    media = _guarded_rows(
        executor, PUBLIC_MEDIA_SQL, session, 7, MAX_PUBLIC_MEDIA_FACTS,
    )
    if len(pages) != EXACT_PAGES or len(routes) != EXACT_ROUTES:
        raise FreezeError("capture-public-count")
    _validate_public_identities(pages, routes)
    _validate_shared(shared)
    _validate_media_capture(media)
    frozen = _freeze_value((pages, routes, shared, media))
    if not isinstance(frozen, tuple) or len(frozen) != 4:
        raise FreezeError("freeze-capture-value")
    return FreezeCapture(*frozen)
