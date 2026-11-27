from __future__ import annotations

import csv
import hashlib
import io
import re
import uuid
from pathlib import Path
from typing import Any

from rebuild3_importer.content import validate_payload
from rebuild3_importer.freeze import (
    EXACT_GALLERY_ALBUMS,
    EXACT_GALLERY_PHOTOS,
    EXACT_PACKAGE_MEDIA,
    EXACT_SOURCE_MEDIA,
    EXACT_TARGET_MEDIA,
    FreezeError,
    FreezePackage,
    MediaBinding,
    UsageBinding,
    _canonical,
    _project_public_rows,
    _validate_media_projection,
    freeze_package_digest,
)
from rebuild3_importer.freeze_authority import (
    FreezeCapture,
    _thaw_value,
    compose_page_route_authority,
)
from rebuild3_importer.manifest import ManifestLimits
from rebuild3_importer.service_media import INFOGRAPHIC_ASSET_ID, service_media_by_pair


EVIDENCE_SHA256 = "52823a26c535f6bcbb45601fccad630278d59d421ab5f87b25bb1390d28867ca"
EVIDENCE_ROLES = frozenset({
    "gallery-original",
    "new_design_asset",
    "trusted_design_svg_not_user_upload",
    "illustration-or-layout",
})
LOGO_EVIDENCE_ID = "MED-0105"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MIME_BY_EXTENSION = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "svg": "image/svg+xml",
}


def _media_evidence() -> tuple[dict[str, Any], ...]:
    """Read only the pinned exact301 CSV authority."""

    path = Path(__file__).parents[2] / "docs" / "analytics-media-evidence.csv"
    try:
        raw = path.read_bytes()
    except OSError:
        raise FreezeError("media-evidence-unavailable") from None
    if hashlib.sha256(raw).hexdigest() != EVIDENCE_SHA256:
        raise FreezeError("media-evidence-digest")
    try:
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8", "strict"))))
    except (UnicodeError, csv.Error):
        raise FreezeError("media-evidence-shape") from None
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    seen_pairs: set[tuple[str, int]] = set()
    for row in rows:
        if (
            row.get("role") not in EVIDENCE_ROLES
            or row.get("local_exists") != "true"
            or row.get("archive_status") == "error_http404"
        ):
            continue
        try:
            size = int(row["bytes"])
        except (KeyError, TypeError, ValueError):
            raise FreezeError("media-evidence-shape") from None
        evidence_id = row.get("media_evidence_id")
        source_path = row.get("media_path")
        digest = row.get("sha256")
        if (
            not isinstance(evidence_id, str)
            or not isinstance(source_path, str)
            or not source_path.startswith("media/")
            or not isinstance(digest, str)
            or SHA256.fullmatch(digest) is None
            or size <= 0
            or evidence_id in seen_ids
            or source_path in seen_paths
            or (digest, size) in seen_pairs
        ):
            raise FreezeError("media-evidence-shape")
        seen_ids.add(evidence_id)
        seen_paths.add(source_path)
        seen_pairs.add((digest, size))
        selected.append({
            "evidence_id": evidence_id,
            "source_path": source_path,
            "role": row["role"],
            "byte_size": size,
            "sha256": digest,
        })
    if (
        len(selected) != 301
        or sum(row["byte_size"] for row in selected) != 56_134_441
        or sum(row["role"] == "gallery-original" for row in selected) != 214
        or sum(row["role"] == "trusted_design_svg_not_user_upload" for row in selected) != 3
        or sum(row["evidence_id"] == LOGO_EVIDENCE_ID for row in selected) != 1
    ):
        raise FreezeError("media-evidence-count")
    return tuple(selected)


def _literal_media_descriptors() -> tuple[dict[str, Any], ...]:
    """Reuse the four approved package readers; no second package format."""

    from content.dev09_migration_apply import (
        _read_combined_infographic_package,
        _read_remaining_content_package,
    )
    from content.dev10_gallery_apply import _read_package as _read_gallery_package
    from content.dev12_home_apply import _read_package as _read_home_package

    gallery = _read_gallery_package()
    remaining = _read_remaining_content_package()
    infographic = _read_combined_infographic_package()["media"]
    home = _read_home_package()
    result: list[dict[str, Any]] = []
    for album in gallery["albums"]:
        for row in album["photos"]:
            result.append({
                "asset_id": row["asset_id"], "file_id": row["file_id"],
                "source_path": row["local_file"], "sha256": row["sha256"],
                "byte_size": row["bytes"], "kind": "LEGACY_PUBLIC",
                "purpose": "GALLERY_ORIGINAL",
            })
    for row in remaining["media"]:
        result.append({
            "asset_id": row["asset_id"], "file_id": row["file_id"],
            "source_path": row["relative_path"], "sha256": row["sha256"],
            "byte_size": row["bytes"], "kind": "MAIN", "purpose": "CONTENT",
        })
    for row in home["media"]:
        result.append({
            "asset_id": row["asset_id"], "file_id": row["file_id"],
            "source_path": row["local_file"], "sha256": row["sha256"],
            "byte_size": row["bytes"], "kind": "MAIN", "purpose": "CONTENT",
        })
    result.append({
        "asset_id": infographic["asset_id"], "file_id": infographic["file_id"],
        "source_path": infographic["relative_path"], "sha256": infographic["sha256"],
        "byte_size": infographic["bytes"], "kind": "MAIN", "purpose": "CONTENT",
    })
    if (
        len(result) != 237
        or len({row["asset_id"] for row in result}) != 237
        or len({row["file_id"] for row in result}) != 237
        or len({(row["sha256"], row["byte_size"]) for row in result}) != 236
        or sum(row["purpose"] == "GALLERY_ORIGINAL" for row in result) != 214
    ):
        raise FreezeError("media-package-count")
    return tuple(result)


def _mime(source_path: str) -> str:
    extension = source_path.rsplit(".", 1)[-1].lower()
    try:
        return MIME_BY_EXTENSION[extension]
    except KeyError:
        raise FreezeError("media-extension") from None


def _file_row(
    *, file_id: str, asset_id: str, kind: str, source_path: str,
    digest: str, byte_size: int,
) -> dict[str, Any]:
    return {
        "id": file_id, "asset_id": asset_id, "kind": kind,
        "source_path": source_path, "sha256": digest,
        "byte_size": byte_size, "mime_type": _mime(source_path),
        "width": None, "height": None,
    }


def _site_settings(settings_id: uuid.UUID, logo_asset_id: str) -> dict[str, Any]:
    return {
        "id": str(settings_id), "structure_generation": 1,
        "settings_generation": 1,
        "organization_name": "Автосервис «Эстакада»", "legal_name": None,
        "phone_display": "+7 (499) 110-25-52", "phone_e164": "+74991102552",
        "address": "117105, Москва, Проспект 60-летия Октября, 15Б",
        "opening_hours": "Ежедневно с 9:00 до 21:00",
        "contact_email": "estakada10@yandex.ru",
        "map_url": "https://yandex.ru/maps/org/57771430682",
        "max_url": None, "telegram_url": None,
        "logo_asset_id": logo_asset_id,
    }


def compose_freeze_package(capture: FreezeCapture) -> FreezePackage:
    """Compose the one literal public package from an immutable capture."""

    if not isinstance(capture, FreezeCapture):
        raise FreezeError("freeze-capture")
    pages, routes = compose_page_route_authority(capture)
    shared = tuple(_thaw_value(row) for row in capture.shared)
    media = tuple(_thaw_value(row) for row in capture.media)
    if len(shared) != 2 or {row[1] for row in shared} != {"header", "footer"}:
        raise FreezeError("shared-authority-count")

    facts: dict[tuple[str, str], tuple[Any, ...]] = {}
    for row in media:
        if not isinstance(row, tuple) or len(row) != 3:
            raise FreezeError("media-authority-shape")
        entity, identity, fact = row
        normalized = tuple(fact) if isinstance(fact, (list, tuple)) else ()
        key = (str(entity), str(identity))
        if key in facts or not normalized:
            raise FreezeError("media-authority-shape")
        facts[key] = normalized
    source_assets = {
        identity: fact for (entity, identity), fact in facts.items()
        if entity == "asset"
    }
    source_files = {
        identity: fact for (entity, identity), fact in facts.items()
        if entity == "file"
    }
    source_usages = {
        identity: fact for (entity, identity), fact in facts.items()
        if entity == "usage"
    }
    if (
        len(source_assets) != EXACT_SOURCE_MEDIA
        or len(source_files) != EXACT_SOURCE_MEDIA
        or len(source_usages) != 736
    ):
        raise FreezeError("media-authority-count")
    files_by_asset: dict[str, tuple[str, tuple[Any, ...]]] = {}
    for file_id, fact in source_files.items():
        asset_id = str(fact[0])
        if asset_id in files_by_asset:
            raise FreezeError("media-authority-file")
        files_by_asset[asset_id] = (file_id, fact)
    if set(files_by_asset) != set(source_assets):
        raise FreezeError("media-authority-file")

    evidence = _media_evidence()
    evidence_by_pair = {
        (row["sha256"], row["byte_size"]): row for row in evidence
    }
    evidence_by_id = {row["evidence_id"]: row for row in evidence}
    descriptors = _literal_media_descriptors()
    descriptors_by_asset = {row["asset_id"]: row for row in descriptors}
    used_evidence: set[str] = set()
    used_descriptors: set[str] = set()
    assets: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    media_bindings: list[MediaBinding] = []
    logo_asset_id: str | None = None
    logo_file_id: str | None = None
    unresolved = 0
    kind_map = {"main": "MAIN", "preview": "PREVIEW", "legacy-public": "LEGACY_PUBLIC"}

    for asset_id in sorted(source_assets):
        asset_fact = source_assets[asset_id]
        file_id, file_fact = files_by_asset[asset_id]
        if (
            len(asset_fact) != 6 or len(file_fact) != 5
            or asset_fact[1] != "ready" or str(file_fact[0]) != asset_id
            or kind_map.get(file_fact[1]) is None
            or not isinstance(file_fact[3], str) or SHA256.fullmatch(file_fact[3]) is None
            or type(file_fact[4]) is not int or file_fact[4] <= 0
        ):
            raise FreezeError("media-authority-source")
        pair = (file_fact[3], file_fact[4])
        candidate = evidence_by_pair.get(pair)
        descriptor = descriptors_by_asset.get(asset_id)
        if descriptor is not None:
            if (
                descriptor["file_id"] != file_id
                or descriptor["sha256"] != file_fact[3]
                or descriptor["byte_size"] != file_fact[4]
                or descriptor["kind"] != kind_map[file_fact[1]]
            ):
                raise FreezeError("media-package-source-drift")
            used_descriptors.add(asset_id)
            if candidate is None:
                if asset_id != INFOGRAPHIC_ASSET_ID:
                    raise FreezeError("media-source-unresolved")
                unresolved += 1
                source_path = descriptor["source_path"]
            else:
                source_path = candidate["source_path"]
                used_evidence.add(candidate["evidence_id"])
            purpose = descriptor["purpose"]
        else:
            logo = evidence_by_id[LOGO_EVIDENCE_ID]
            if candidate != logo or logo_asset_id is not None:
                raise FreezeError("media-source-unapproved")
            logo_asset_id, logo_file_id = asset_id, file_id
            source_path = logo["source_path"]
            purpose = "SITE_ASSET"
            used_evidence.add(LOGO_EVIDENCE_ID)
        source_sha = asset_fact[5] or file_fact[3]
        if source_sha != file_fact[3]:
            raise FreezeError("media-source-hash")
        assets.append({
            "id": asset_id, "purpose": purpose,
            "source_sha256": source_sha, "state": "READY",
        })
        files.append(_file_row(
            file_id=file_id, asset_id=asset_id, kind=kind_map[file_fact[1]],
            source_path=source_path, digest=file_fact[3], byte_size=file_fact[4],
        ))
        media_bindings.append(MediaBinding(
            uuid.UUID(asset_id), uuid.UUID(file_id), "SOURCE_DB",
            uuid.UUID(asset_id), uuid.UUID(file_id), candidate is None,
        ))
    if (
        used_descriptors != set(descriptors_by_asset)
        or unresolved != 1
        or logo_asset_id is None or logo_file_id is None
        or len(used_evidence) != 236
    ):
        raise FreezeError("media-source-coverage")

    package_only = [
        row for row in evidence if row["evidence_id"] not in used_evidence
    ]
    if len(package_only) != EXACT_PACKAGE_MEDIA:
        raise FreezeError("media-package-only-count")
    service_media = service_media_by_pair()
    bound_service_media: set[tuple[str, int]] = set()
    for row in package_only:
        pair = (row["sha256"], row["byte_size"])
        service_row = service_media.get(pair)
        if service_row is None:
            asset_id, file_id = uuid.uuid4(), uuid.uuid4()
        else:
            if row["source_path"] != service_row["source_path"]:
                raise FreezeError("service-media-authority")
            asset_id = uuid.UUID(service_row["asset_id"])
            file_id = uuid.UUID(service_row["file_id"])
            bound_service_media.add(pair)
        assets.append({
            "id": str(asset_id), "purpose": "CONTENT",
            "source_sha256": row["sha256"], "state": "READY",
        })
        files.append(_file_row(
            file_id=str(file_id), asset_id=str(asset_id), kind="MAIN",
            source_path=row["source_path"], digest=row["sha256"],
            byte_size=row["byte_size"],
        ))
        media_bindings.append(MediaBinding(
            asset_id, file_id, "APPROVED_PACKAGE", None, None, False,
        ))
    if bound_service_media != set(service_media):
        raise FreezeError("service-media-authority")
    if len(assets) != EXACT_TARGET_MEDIA or len(files) != EXACT_TARGET_MEDIA:
        raise FreezeError("media-target-count")

    settings_id = uuid.uuid4()
    settings = _site_settings(settings_id, logo_asset_id)
    usages: list[dict[str, Any]] = [{
        "id": str(uuid.uuid4()), "asset_id": logo_asset_id,
        "scope": "SITE_SETTINGS", "target_uuid": str(settings_id),
        "slot": "logo", "position": 0,
    }]
    for page in pages:
        for scope, payload in (
            ("PAGE_CURRENT", page.current_payload),
            ("PAGE_PREVIOUS", page.previous_payload),
        ):
            if payload is None:
                continue
            refs = validate_payload(payload, page.kind)
            for slot, asset_ids in refs.items():
                for position, target_asset_id in enumerate(asset_ids):
                    usages.append({
                        "id": str(uuid.uuid4()), "asset_id": target_asset_id,
                        "scope": scope, "target_uuid": str(page.id),
                        "slot": slot, "position": position,
                    })
    target_by_projection: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in usages:
        key = (row["asset_id"], row["scope"], row["target_uuid"])
        target_by_projection.setdefault(key, []).append(row)

    from content.dev10_gallery_apply import _read_package as _read_gallery_package

    gallery_package = _read_gallery_package()
    gallery_albums: list[dict[str, Any]] = []
    gallery_photos: list[dict[str, Any]] = []
    gallery_pairs: set[tuple[str, str]] = set()
    page_by_id = {str(page.id): page for page in pages}
    for position, album in enumerate(gallery_package["albums"]):
        album_id = uuid.UUID(album["page_id"])
        page = page_by_id.get(album["page_id"])
        if page is None:
            raise FreezeError("gallery-page-authority")
        gallery_albums.append({
            "id": str(album_id), "page_id": album["page_id"],
            "generation": page.content_generation, "position": position,
        })
        for photo in album["photos"]:
            gallery_photos.append({
                "id": photo["image_id"], "album_id": str(album_id),
                "asset_id": photo["asset_id"], "position": photo["position"],
                "alt": photo["alt"],
            })
            gallery_pairs.add((photo["asset_id"], album["page_id"]))
    if (
        len(gallery_albums) != EXACT_GALLERY_ALBUMS
        or len(gallery_photos) != EXACT_GALLERY_PHOTOS
        or len(gallery_pairs) != EXACT_GALLERY_PHOTOS
    ):
        raise FreezeError("gallery-authority-count")

    usage_bindings: list[UsageBinding] = []
    targets_with_source: set[str] = set()
    for (entity, source_id), fact in facts.items():
        if entity != "usage" or fact[4] != "eligible":
            continue
        asset_id = str(fact[0])
        projected_target = None if fact[6] is None else str(fact[6])
        if (asset_id, projected_target) in gallery_pairs:
            continue
        if fact[1] == "shared_block":
            if fact[5] is not None or fact[6] is not None or asset_id != logo_asset_id:
                raise FreezeError("shared-usage-authority")
            candidates = target_by_projection.get(
                (logo_asset_id, "SITE_SETTINGS", str(settings_id)), [],
            )
        else:
            valid_projection = (
                (fact[1] == "current_page" and fact[5] == "PAGE_CURRENT")
                or (
                    fact[1] in ("ordinary_version", "stable_version")
                    and fact[5] in ("PAGE_CURRENT", "PAGE_PREVIOUS")
                )
            )
            if not valid_projection or fact[6] is None:
                raise FreezeError("page-usage-authority")
            candidates = target_by_projection.get(
                (asset_id, str(fact[5]), projected_target), [],
            )
        if len(candidates) != 1:
            raise FreezeError("usage-projection-ambiguous")
        target_id = candidates[0]["id"]
        usage_bindings.append(UsageBinding(
            uuid.UUID(target_id), uuid.UUID(source_id),
        ))
        targets_with_source.add(target_id)
    for row in usages:
        if row["id"] not in targets_with_source:
            usage_bindings.append(UsageBinding(uuid.UUID(row["id"]), None))

    package = FreezePackage(
        pages=pages, routes=routes, source_shared=shared, source_media=media,
        site_settings=settings, assets=tuple(assets), files=tuple(files),
        usages=tuple(usages), gallery_albums=tuple(gallery_albums),
        gallery_photos=tuple(gallery_photos),
        media_bindings=tuple(media_bindings),
        usage_bindings=tuple(usage_bindings),
    )
    _validate_media_projection(media, package)
    return package


def compose_run_authority(
    capture: FreezeCapture,
) -> tuple[FreezePackage, ManifestLimits, str]:
    """Close one in-memory package, its exact caps and external digest."""

    package = compose_freeze_package(capture)
    source_pages = tuple(_thaw_value(row) for row in capture.pages)
    source_routes = tuple(_thaw_value(row) for row in capture.routes)
    pages, routes, _page_refs = _project_public_rows(
        source_pages, source_routes, package,
    )
    sections = {
        "routes": routes, "pages": pages,
        "assets": list(package.assets), "files": list(package.files),
        "usages": list(package.usages),
        "gallery_albums": list(package.gallery_albums),
        "gallery_photos": list(package.gallery_photos),
    }
    maximum_snapshot_id = "1:1:" + "1" * 196
    unsigned = {
        "version": 1, "snapshot_id": maximum_snapshot_id,
        "site_settings": package.site_settings, "sections": sections,
    }
    root = {**unsigned, "digest": hashlib.sha256(_canonical(unsigned)).hexdigest()}
    total_bytes = sum(row["byte_size"] for row in package.files)
    gallery_assets = {row["asset_id"] for row in package.gallery_photos}
    gallery_bytes = sum(
        row["byte_size"] for row in package.files
        if row["asset_id"] in gallery_assets
    )
    trusted_svg = frozenset(
        row["sha256"] for row in package.files
        if row["mime_type"] == "image/svg+xml"
    )
    if (
        len(maximum_snapshot_id) != 200
        or len(package.usages) != 53
        or total_bytes != 56_440_807
        or gallery_bytes != 41_176_391
        or len(trusted_svg) != 3
    ):
        raise FreezeError("manifest-limit-authority")
    limits = ManifestLimits(
        routes=len(package.routes), pages=len(package.pages),
        assets=len(package.assets), files=len(package.files),
        usages=len(package.usages), gallery_albums=len(package.gallery_albums),
        gallery_photos=len(package.gallery_photos),
        canonical_bytes=len(_canonical(root)), total_file_bytes=total_bytes,
        gallery_file_bytes=gallery_bytes, trusted_svg_sha256=trusted_svg,
    )
    return package, limits, freeze_package_digest(package)
