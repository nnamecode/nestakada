from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from rebuild3_importer.manifest import ManifestLimits, PublicManifest, parse_public_manifest
from rebuild3_importer.source import SNAPSHOT_ID, SourceExecutor, SourceSession, TargetPageRef


MAX_PUBLIC_PAGES = 112
MAX_PUBLIC_ROUTES = 114
MAX_PUBLIC_SHARED = 2
MAX_PUBLIC_MEDIA_FACTS = 2048
EXACT_SOURCE_MEDIA = 238
EXACT_PACKAGE_MEDIA = 65
EXACT_TARGET_MEDIA = 303
EXACT_PAGES = 112
EXACT_ROUTES = 114
EXACT_GALLERY_ALBUMS = 17
EXACT_GALLERY_PHOTOS = 214


PUBLIC_PAGES_SQL = """
WITH guard AS (
  SELECT pg_backend_pid() AS backend_pid, txid_current() AS transaction_id,
         txid_current_snapshot()::text AS snapshot_id
), selected_current AS (
  SELECT s.page_id, s.sequence AS generation, r.id, r.sequence, r.schema_version,
         r.payload, r.payload_hash, r.created_at,
         EXISTS (
           SELECT 1 FROM app.page_versions_pagerevision n
           WHERE n.page_id = s.page_id AND n.sequence > r.sequence
             AND n.kind IN ('initial', 'automatic')
         ) AS newer_exists
  FROM app.page_versions_pagecontentstate s
  JOIN app.page_versions_pagerevision r
    ON r.id = s.current_revision_id AND r.page_id = s.page_id
  WHERE r.kind IN ('initial', 'automatic')
), selected_previous AS (
  SELECT c.page_id, p.id, p.schema_version, p.payload, p.payload_hash, p.created_at
  FROM selected_current c
  LEFT JOIN LATERAL (
    SELECT r.id, r.schema_version, r.payload, r.payload_hash, r.created_at
    FROM app.page_versions_pagerevision r
    WHERE r.page_id = c.page_id AND r.sequence < c.sequence
      AND r.kind IN ('initial', 'automatic')
    ORDER BY r.sequence DESC LIMIT 1
  ) p ON true
)
SELECT 0, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       NULL::uuid, NULL::text, NULL::text, NULL::uuid, NULL::bigint, NULL::boolean,
       NULL::bigint, NULL::bigint, NULL::text, NULL::jsonb, NULL::text,
       NULL::timestamptz, NULL::boolean, NULL::jsonb, NULL::text,
       NULL::timestamptz, NULL::text
FROM guard
UNION ALL
SELECT 1, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       p.id, p.name, p.kind, p.parent_id, p.position, p.is_published,
       c.generation, c.sequence, c.schema_version, c.payload, c.payload_hash,
       c.created_at, c.newer_exists, v.payload, v.payload_hash, v.created_at,
       v.schema_version
FROM guard CROSS JOIN app.content_page p
JOIN selected_current c ON c.page_id = p.id
LEFT JOIN selected_previous v ON v.page_id = p.id
ORDER BY 1, 9, 5 LIMIT 114
""".strip()

PUBLIC_ROUTES_SQL = """
WITH guard AS (
  SELECT pg_backend_pid() AS backend_pid, txid_current() AS transaction_id,
         txid_current_snapshot()::text AS snapshot_id
)
SELECT 0, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       NULL::uuid, NULL::uuid, NULL::text, NULL::text, NULL::boolean
FROM guard
UNION ALL
SELECT 1, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       r.id, r.page_id, r.target, r.kind, r.is_legacy
FROM guard CROSS JOIN app.content_route r
WHERE r.kind <> 'system'
ORDER BY 1, 7, 5 LIMIT 116
""".strip()

PUBLIC_SHARED_SQL = """
WITH guard AS (
  SELECT pg_backend_pid() AS backend_pid, txid_current() AS transaction_id,
         txid_current_snapshot()::text AS snapshot_id
)
SELECT 0, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       NULL::uuid, NULL::text, NULL::bigint, NULL::uuid, NULL::bigint,
       NULL::text, NULL::text, NULL::text, NULL::text, NULL::bigint,
       NULL::text, NULL::text
FROM guard
UNION ALL
SELECT 1, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       b.id, b.kind, b.generation, r.id, r.sequence, r.schema_version,
       r.storage_kind, r.file_key, r.payload_hash, r.byte_size, r.file_sha256, r.html
FROM guard CROSS JOIN app.shared_content_sharedblock b
JOIN app.shared_content_sharedrevision r
  ON r.id = b.current_revision_id AND r.block_id = b.id
ORDER BY 1, 6, 5 LIMIT 4
""".strip()

PUBLIC_MEDIA_SQL = """
WITH guard AS (
  SELECT pg_backend_pid() AS backend_pid, txid_current() AS transaction_id,
         txid_current_snapshot()::text AS snapshot_id
), selected_current AS (
  SELECT s.page_id, r.id, r.sequence
  FROM app.page_versions_pagecontentstate s
  JOIN app.page_versions_pagerevision r
    ON r.id = s.current_revision_id AND r.page_id = s.page_id
  WHERE r.kind IN ('initial', 'automatic')
), selected_previous AS (
  SELECT c.page_id, p.id
  FROM selected_current c
  LEFT JOIN LATERAL (
    SELECT r.id FROM app.page_versions_pagerevision r
    WHERE r.page_id = c.page_id AND r.sequence < c.sequence
      AND r.kind IN ('initial', 'automatic')
    ORDER BY r.sequence DESC LIMIT 1
  ) p ON true
  WHERE p.id IS NOT NULL
), selected_revision AS (
  SELECT id, page_id, 'PAGE_CURRENT'::text AS scope FROM selected_current
  UNION ALL
  SELECT id, page_id, 'PAGE_PREVIOUS'::text FROM selected_previous
), current_shared AS (
  SELECT r.id
  FROM app.shared_content_sharedblock b
  JOIN app.shared_content_sharedrevision r
    ON r.id = b.current_revision_id AND r.block_id = b.id
), usage_facts AS (
  SELECT u.id, u.asset_id, u.kind, u.consumer_id, u.slot,
    CASE
      WHEN u.kind = 'current_page' AND p.id IS NOT NULL THEN 'eligible'
      WHEN u.kind IN ('ordinary_version','stable_version') AND sr.id IS NOT NULL THEN 'eligible'
      WHEN u.kind = 'shared_block' AND cs.id IS NOT NULL THEN 'eligible'
      WHEN u.kind IN ('ordinary_version','stable_version') AND r.id IS NOT NULL THEN 'excluded'
      WHEN u.kind = 'shared_block' AND sh.id IS NOT NULL THEN 'excluded'
      WHEN u.kind IN ('draft','retained_html') THEN 'excluded'
      ELSE 'unclassified'
    END AS classification,
    CASE WHEN u.kind = 'current_page' AND p.id IS NOT NULL THEN 'PAGE_CURRENT'
         ELSE sr.scope END AS projected_scope,
    CASE WHEN u.kind = 'current_page' AND p.id IS NOT NULL THEN p.id
         ELSE sr.page_id END AS projected_target
  FROM app.media_library_assetusage u
  LEFT JOIN app.content_page p ON u.kind = 'current_page' AND p.id = u.consumer_id
  LEFT JOIN app.page_versions_pagerevision r
    ON u.kind IN ('ordinary_version','stable_version') AND r.id = u.consumer_id
  LEFT JOIN selected_revision sr
    ON u.kind IN ('ordinary_version','stable_version') AND sr.id = u.consumer_id
  LEFT JOIN app.shared_content_sharedrevision sh
    ON u.kind = 'shared_block' AND sh.id = u.consumer_id
  LEFT JOIN current_shared cs ON u.kind = 'shared_block' AND cs.id = u.consumer_id
), facts AS (
  SELECT 'asset'::text AS entity, a.id::text AS identity,
         jsonb_build_array(a.folder_id, a.status, a.provenance, a.is_legacy,
                           a.source_url, a.source_sha256)::jsonb AS fact
  FROM app.media_library_asset a
  UNION ALL
  SELECT 'file', f.id::text,
         jsonb_build_array(f.asset_id, f.kind, f.key, f.sha256, f.byte_size)::jsonb
  FROM app.media_library_assetfile f
  UNION ALL
  SELECT 'usage', u.id::text,
         jsonb_build_array(u.asset_id, u.kind, u.consumer_id, u.slot,
                           u.classification, u.projected_scope, u.projected_target)::jsonb
  FROM usage_facts u
  UNION ALL
  SELECT 'home', h.id::text,
         jsonb_build_array(h.page_id, h.folder_id)::jsonb
  FROM app.media_library_pagemediahome h
)
SELECT 0, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       NULL::text, NULL::text, NULL::jsonb
FROM guard
UNION ALL
SELECT 1, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       f.entity, f.identity, f.fact
FROM guard CROSS JOIN facts f
ORDER BY 1, 5, 6 LIMIT 2050
""".strip()


class FreezeError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ApprovedPage:
    id: uuid.UUID
    name: str
    source_kind: str
    kind: str
    parent_id: uuid.UUID | None
    position: int
    is_published: bool
    content_generation: int
    source_current_schema: str
    source_current_hash: str
    source_current_created_at: str
    current_payload: dict[str, Any]
    source_previous_schema: str | None
    source_previous_hash: str | None
    source_previous_created_at: str | None
    previous_payload: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class ApprovedRoute:
    id: uuid.UUID
    page_id: uuid.UUID
    target: str
    source_kind: str
    source_is_legacy: bool
    mode: str
    outcome: str


@dataclass(frozen=True, slots=True)
class MediaBinding:
    target_asset_id: uuid.UUID
    target_file_id: uuid.UUID
    origin: str
    source_asset_id: uuid.UUID | None
    source_file_id: uuid.UUID | None
    resolved_unmatched: bool


@dataclass(frozen=True, slots=True)
class UsageBinding:
    target_usage_id: uuid.UUID
    source_usage_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class FreezePackage:
    pages: tuple[ApprovedPage, ...]
    routes: tuple[ApprovedRoute, ...]
    source_shared: tuple[tuple[Any, ...], ...]
    source_media: tuple[tuple[Any, ...], ...]
    site_settings: dict[str, Any]
    assets: tuple[dict[str, Any], ...]
    files: tuple[dict[str, Any], ...]
    usages: tuple[dict[str, Any], ...]
    gallery_albums: tuple[dict[str, Any], ...]
    gallery_photos: tuple[dict[str, Any], ...]
    media_bindings: tuple[MediaBinding, ...]
    usage_bindings: tuple[UsageBinding, ...]


@dataclass(frozen=True, slots=True)
class FrozenPublic:
    manifest: PublicManifest
    page_resolver: Callable[[uuid.UUID], TargetPageRef]


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _authority_value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, tuple):
        return [_authority_value(item) for item in value]
    if isinstance(value, list):
        return [_authority_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _authority_value(item) for key, item in value.items()}
    return value


def freeze_package_digest(package: FreezePackage) -> str:
    if not isinstance(package, FreezePackage):
        raise FreezeError("freeze-package")
    return hashlib.sha256(_canonical(_authority_value(asdict(package)))).hexdigest()


def _timestamp(value: object) -> str:
    if isinstance(value, str):
        if re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z",
            value,
        ) is None:
            raise FreezeError("source-timestamp")
        try:
            parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            raise FreezeError("source-timestamp") from None
        if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != value:
            raise FreezeError("source-timestamp")
        return value
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise FreezeError("source-timestamp")
    normalized = value.astimezone(timezone.utc)
    return normalized.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _guarded_rows(
    executor: SourceExecutor,
    sql: str,
    session: SourceSession,
    width: int,
    cap: int,
) -> tuple[tuple[Any, ...], ...]:
    try:
        rows = tuple(tuple(row) for row in executor.fetch_all(sql))
    except Exception:
        raise FreezeError("source-public-query") from None
    if not rows or len(rows) > cap + 1 or len(rows[0]) != width or rows[0][0] != 0:
        raise FreezeError("source-public-guard")
    result: list[tuple[Any, ...]] = []
    for index, row in enumerate(rows):
        if (
            len(row) != width
            or row[1] != session.backend_pid
            or row[2] != session.transaction_id
            or row[3] != session.snapshot_id
            or (index == 0 and row[0] != 0)
            or (index > 0 and row[0] != 1)
            or (index == 0 and any(value is not None for value in row[4:]))
        ):
            raise FreezeError("source-public-session-drift")
        if index:
            result.append(row[4:])
    return tuple(result)


def _source_fact(value: object) -> object:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, list):
        return tuple(_source_fact(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((key, _source_fact(item)) for key, item in value.items()))
    return value


def _validate_shared(rows: tuple[tuple[Any, ...], ...]) -> None:
    seen: set[object] = set()
    for row in rows:
        if len(row) != 12:
            raise FreezeError("shared-source-shape")
        (
            block_id, kind, generation, revision_id, sequence, schema_version,
            storage_kind, file_key, payload_hash, byte_size, file_sha256, html,
        ) = row
        if (
            block_id in seen
            or kind not in ("header", "footer")
            or type(generation) is not int
            or generation < 1
            or type(sequence) is not int
            or sequence < 1
            or not isinstance(schema_version, str)
            or re.fullmatch(r"[0-9a-f]{64}", str(payload_hash)) is None
        ):
            raise FreezeError("shared-source-shape")
        seen.add(block_id)
        if storage_kind == "inline":
            if (
                not isinstance(html, str)
                or file_key != ""
                or byte_size is not None
                or file_sha256 != ""
                or hashlib.sha256(html.encode("utf-8")).hexdigest() != payload_hash
            ):
                raise FreezeError("shared-inline-drift")
        elif storage_kind == "file":
            if (
                html != ""
                or not isinstance(file_key, str)
                or re.fullmatch(
                    r"blobs/([0-9a-f]{2})/\1[0-9a-f]{30}\.html", file_key
                ) is None
                or type(byte_size) is not int
                or not 0 <= byte_size <= 1_048_576
                or re.fullmatch(r"[0-9a-f]{64}", str(file_sha256)) is None
                or payload_hash != file_sha256
            ):
                raise FreezeError("shared-file-drift")
        else:
            raise FreezeError("shared-storage-kind")


def _validate_media_projection(
    source_media: tuple[tuple[Any, ...], ...],
    package: FreezePackage,
) -> None:
    facts: dict[tuple[str, str], tuple[Any, ...]] = {}
    for entity, identity, fact in source_media:
        key = (entity, identity)
        normalized = _source_fact(fact)
        if (
            not isinstance(entity, str)
            or not isinstance(identity, str)
            or not isinstance(normalized, tuple)
            or key in facts
        ):
            raise FreezeError("media-source-shape")
        facts[key] = normalized
    assets = {row.get("id"): row for row in package.assets}
    files = {row.get("id"): row for row in package.files}
    usages = {row.get("id"): row for row in package.usages}
    if (
        len(assets) != len(package.assets)
        or len(files) != len(package.files)
        or len(usages) != len(package.usages)
        or len(package.media_bindings) != len(files)
    ):
        raise FreezeError("media-projection-count")
    seen_assets: set[str] = set()
    seen_files: set[str] = set()
    bound_source_assets: set[str] = set()
    bound_source_files: set[str] = set()
    db_count = package_count = resolved_count = 0
    kind_map = {
        "main": "MAIN",
        "preview": "PREVIEW",
        "legacy-public": "LEGACY_PUBLIC",
    }
    for binding in package.media_bindings:
        target_asset_id = str(binding.target_asset_id)
        target_file_id = str(binding.target_file_id)
        asset = assets.get(target_asset_id)
        file = files.get(target_file_id)
        if (
            asset is None
            or file is None
            or file.get("asset_id") != target_asset_id
            or target_asset_id in seen_assets
            or target_file_id in seen_files
        ):
            raise FreezeError("media-binding-target")
        seen_assets.add(target_asset_id)
        seen_files.add(target_file_id)
        if binding.origin == "APPROVED_PACKAGE":
            package_count += 1
            if (
                binding.source_asset_id is not None
                or binding.source_file_id is not None
                or binding.resolved_unmatched
            ):
                raise FreezeError("media-binding-package")
            continue
        if binding.origin != "SOURCE_DB":
            raise FreezeError("media-binding-origin")
        db_count += 1
        resolved_count += int(binding.resolved_unmatched)
        source_asset_id = str(binding.source_asset_id)
        source_file_id = str(binding.source_file_id)
        source_asset = facts.get(("asset", source_asset_id))
        source_file = facts.get(("file", source_file_id))
        if (
            binding.source_asset_id is None
            or binding.source_file_id is None
            or target_asset_id != source_asset_id
            or target_file_id != source_file_id
            or source_asset is None
            or len(source_asset) != 6
            or source_asset_id in bound_source_assets
            or source_file is None
            or len(source_file) != 5
            or source_file_id in bound_source_files
            or source_asset[1] != "ready"
            or str(source_file[0]) != source_asset_id
            or kind_map.get(source_file[1]) != file.get("kind")
            or source_file[3] != file.get("sha256")
            or source_file[4] != file.get("byte_size")
            or asset.get("source_sha256") != (source_asset[5] or source_file[3])
            or asset.get("state") != "READY"
        ):
            raise FreezeError("media-binding-source")
        bound_source_assets.add(source_asset_id)
        bound_source_files.add(source_file_id)
    source_asset_ids = {identity for entity, identity in facts if entity == "asset"}
    source_file_ids = {identity for entity, identity in facts if entity == "file"}
    if bound_source_assets != source_asset_ids or bound_source_files != source_file_ids:
        raise FreezeError("media-binding-coverage")
    if (
        len(source_asset_ids) != EXACT_SOURCE_MEDIA
        or len(source_file_ids) != EXACT_SOURCE_MEDIA
        or len(files) != EXACT_TARGET_MEDIA
        or (db_count, package_count, resolved_count)
        != (EXACT_SOURCE_MEDIA, EXACT_PACKAGE_MEDIA, 1)
    ):
        raise FreezeError("media-binding-arithmetic")

    covered_target_usages: set[str] = set()
    null_target_usages: set[str] = set()
    bound_source_usages: set[str] = set()
    for binding in package.usage_bindings:
        target_id = str(binding.target_usage_id)
        target = usages.get(target_id)
        if target is None:
            raise FreezeError("usage-binding-target")
        covered_target_usages.add(target_id)
        if binding.source_usage_id is None:
            if target_id in null_target_usages:
                raise FreezeError("usage-binding-target")
            null_target_usages.add(target_id)
            continue
        source_id = str(binding.source_usage_id)
        source = facts.get(("usage", source_id))
        shared_projection = (
            source is not None
            and len(source) == 7
            and source[1] == "shared_block"
            and source[5] is None
            and source[6] is None
            and target.get("scope") == "SITE_SETTINGS"
            and target.get("slot") == "logo"
            and target.get("position") == 0
        )
        page_projection = (
            source is not None
            and len(source) == 7
            and (
                (source[1] == "current_page" and source[5] == "PAGE_CURRENT")
                or (
                    source[1] in ("ordinary_version", "stable_version")
                    and source[5] in ("PAGE_CURRENT", "PAGE_PREVIOUS")
                )
            )
        )
        if (
            source is None
            or len(source) != 7
            or source_id in bound_source_usages
            or str(source[0]) != target.get("asset_id")
            or source[4] != "eligible"
            or (
                not shared_projection
                and (
                    not page_projection
                    or source[5] != target.get("scope")
                    or str(source[6]) != target.get("target_uuid")
                )
            )
        ):
            raise FreezeError("usage-binding-source")
        bound_source_usages.add(source_id)
    if (
        covered_target_usages != set(usages)
        or null_target_usages & {
            str(binding.target_usage_id)
            for binding in package.usage_bindings
            if binding.source_usage_id is not None
        }
    ):
        raise FreezeError("usage-binding-target")
    source_usages = {
        identity: fact for (entity, identity), fact in facts.items() if entity == "usage"
    }
    if any(
        len(fact) != 7 or fact[4] not in ("eligible", "excluded")
        for fact in source_usages.values()
    ):
        raise FreezeError("usage-classification")
    eligible = {identity for identity, fact in source_usages.items() if fact[4] == "eligible"}
    album_pages = {
        row.get("id"): row.get("page_id") for row in package.gallery_albums
    }
    gallery_pairs = {
        (row.get("asset_id"), album_pages.get(row.get("album_id")))
        for row in package.gallery_photos
    }
    gallery_assets = {row.get("asset_id") for row in package.gallery_photos}
    if package.gallery_photos and (
        len(package.gallery_photos) != EXACT_GALLERY_PHOTOS
        or len(gallery_pairs) != EXACT_GALLERY_PHOTOS
        or len(gallery_assets) != EXACT_GALLERY_PHOTOS
    ):
        raise FreezeError("usage-gallery-coverage")
    if None in {value for pair in gallery_pairs for value in pair}:
        raise FreezeError("usage-gallery-coverage")
    target_page_pairs = {
        (row.get("asset_id"), row.get("target_uuid"))
        for row in package.usages if row.get("scope") == "PAGE_CURRENT"
    }
    if target_page_pairs & gallery_pairs:
        raise FreezeError("usage-gallery-coverage")
    gallery_usage_pairs: dict[
        tuple[object, object], set[tuple[object, object]]
    ] = {}
    gallery_source_usages: set[str] = set()
    for identity in eligible:
        fact = source_usages[identity]
        pair = (str(fact[0]), None if fact[6] is None else str(fact[6]))
        if pair not in gallery_pairs:
            continue
        projection = (fact[1], fact[5])
        if projection not in {
            ("current_page", "PAGE_CURRENT"),
            ("ordinary_version", "PAGE_CURRENT"),
        }:
            raise FreezeError("usage-gallery-coverage")
        cohorts = gallery_usage_pairs.setdefault(pair, set())
        if projection in cohorts:
            raise FreezeError("usage-gallery-coverage")
        cohorts.add(projection)
        gallery_source_usages.add(identity)
    if (
        set(gallery_usage_pairs) != gallery_pairs
        or any(cohorts != {
            ("current_page", "PAGE_CURRENT"),
            ("ordinary_version", "PAGE_CURRENT"),
        } for cohorts in gallery_usage_pairs.values())
    ):
        raise FreezeError("usage-gallery-coverage")
    if bound_source_usages != eligible - gallery_source_usages:
        raise FreezeError("usage-binding-coverage")


def _project_public_rows(
    source_pages: tuple[tuple[Any, ...], ...],
    source_routes: tuple[tuple[Any, ...], ...],
    package: FreezePackage,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[uuid.UUID, TargetPageRef]]:
    """One source-to-manifest projection shared by freeze and limit authority."""

    approved_pages = {str(page.id): page for page in package.pages}
    if len(approved_pages) != len(package.pages) or len(source_pages) != len(package.pages):
        raise FreezeError("page-count")
    pages: list[dict[str, Any]] = []
    page_refs: dict[uuid.UUID, TargetPageRef] = {}
    for row in source_pages:
        (
            page_id, name, source_kind, parent_id, position, is_published, generation,
            current_sequence, current_schema, source_current_payload,
            source_current_hash, current_created_at, newer_exists,
            source_previous_payload, source_previous_hash, previous_created_at,
            previous_schema,
        ) = row
        page_key = str(page_id)
        approved = approved_pages.get(page_key)
        if approved is None:
            raise FreezeError("page-unapproved")
        actual_parent = None if parent_id is None else str(parent_id)
        expected_parent = None if approved.parent_id is None else str(approved.parent_id)
        expected = (
            approved.name, approved.source_kind, expected_parent, approved.position,
            approved.is_published, approved.content_generation,
            approved.content_generation, approved.source_current_schema,
            approved.source_current_hash, approved.source_current_created_at,
            approved.source_previous_schema, approved.source_previous_hash,
            approved.source_previous_created_at,
        )
        actual = (
            name, source_kind, actual_parent, position, is_published, generation,
            current_sequence, current_schema, source_current_hash,
            _timestamp(current_created_at), previous_schema, source_previous_hash,
            None if previous_created_at is None else _timestamp(previous_created_at),
        )
        if actual != expected or newer_exists is not False:
            raise FreezeError("page-source-drift")
        if (
            not isinstance(source_current_payload, dict)
            or hashlib.sha256(_canonical(source_current_payload)).hexdigest()
            != source_current_hash
        ):
            raise FreezeError("page-source-hash")
        if (source_previous_payload is None) != (approved.previous_payload is None):
            raise FreezeError("page-previous-drift")
        if source_previous_payload is not None and (
            not isinstance(source_previous_payload, dict)
            or hashlib.sha256(_canonical(source_previous_payload)).hexdigest()
            != source_previous_hash
        ):
            raise FreezeError("page-source-hash")
        previous = None
        if approved.previous_payload is not None:
            if previous_created_at is None:
                raise FreezeError("page-previous-drift")
            previous = {
                "payload": approved.previous_payload,
                "sha256": hashlib.sha256(
                    _canonical(approved.previous_payload)
                ).hexdigest(),
                "created_at": approved.source_previous_created_at,
            }
        elif previous_created_at is not None:
            raise FreezeError("page-previous-drift")
        pages.append({
            "id": str(approved.id), "name": approved.name, "kind": approved.kind,
            "parent_id": expected_parent, "position": approved.position,
            "is_published": approved.is_published,
            "content_generation": approved.content_generation,
            "current": {
                "payload": approved.current_payload,
                "sha256": hashlib.sha256(
                    _canonical(approved.current_payload)
                ).hexdigest(),
                "created_at": approved.source_current_created_at,
            },
            "previous": previous,
        })
        parsed_page_id = uuid.UUID(page_key)
        page_refs[parsed_page_id] = TargetPageRef(parsed_page_id, approved.kind)

    approved_routes = {str(route.id): route for route in package.routes}
    if len(approved_routes) != len(package.routes) or len(source_routes) != len(package.routes):
        raise FreezeError("route-count")
    routes: list[dict[str, Any]] = []
    for row in source_routes:
        route_id, page_id, target, source_kind, source_is_legacy = row
        approved = approved_routes.get(str(route_id))
        if approved is None or (
            str(page_id), target, source_kind, source_is_legacy
        ) != (
            str(approved.page_id), approved.target, approved.source_kind,
            approved.source_is_legacy,
        ):
            raise FreezeError("route-source-drift")
        routes.append({
            "id": str(approved.id), "page_id": str(approved.page_id),
            "target": approved.target, "mode": approved.mode,
            "outcome": approved.outcome,
        })
    return pages, routes, page_refs


def build_public_manifest(
    executor: SourceExecutor,
    session: SourceSession,
    package: FreezePackage,
    limits: ManifestLimits,
    expected_package_digest: str,
) -> FrozenPublic:
    if (
        not isinstance(session, SourceSession)
        or not isinstance(session.snapshot_id, str)
        or SNAPSHOT_ID.fullmatch(session.snapshot_id) is None
        or not isinstance(package, FreezePackage)
        or not isinstance(limits, ManifestLimits)
    ):
        raise FreezeError("freeze-input")
    if (
        not isinstance(expected_package_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_package_digest) is None
        or freeze_package_digest(package) != expected_package_digest
    ):
        raise FreezeError("freeze-package-digest")

    source_pages = _guarded_rows(
        executor, PUBLIC_PAGES_SQL, session, 21, MAX_PUBLIC_PAGES
    )
    source_routes = _guarded_rows(
        executor, PUBLIC_ROUTES_SQL, session, 9, MAX_PUBLIC_ROUTES
    )
    source_shared = _guarded_rows(
        executor, PUBLIC_SHARED_SQL, session, 16, MAX_PUBLIC_SHARED
    )
    source_media = _guarded_rows(
        executor, PUBLIC_MEDIA_SQL, session, 7, MAX_PUBLIC_MEDIA_FACTS
    )

    pages, routes, page_refs = _project_public_rows(
        source_pages, source_routes, package,
    )

    if tuple(_source_fact(row) for row in source_shared) != tuple(
        _source_fact(row) for row in package.source_shared
    ):
        raise FreezeError("shared-source-drift")
    _validate_shared(source_shared)
    if tuple(_source_fact(row) for row in source_media) != tuple(
        _source_fact(row) for row in package.source_media
    ):
        raise FreezeError("media-source-drift")
    _validate_media_projection(source_media, package)

    if (
        len(pages) != EXACT_PAGES
        or len(routes) != EXACT_ROUTES
        or len(package.assets) != EXACT_TARGET_MEDIA
        or len(package.files) != EXACT_TARGET_MEDIA
        or len(package.gallery_albums) != EXACT_GALLERY_ALBUMS
        or len(package.gallery_photos) != EXACT_GALLERY_PHOTOS
        or (limits.pages, limits.routes, limits.assets, limits.files,
            limits.gallery_albums, limits.gallery_photos)
        != (EXACT_PAGES, EXACT_ROUTES, EXACT_TARGET_MEDIA, EXACT_TARGET_MEDIA,
            EXACT_GALLERY_ALBUMS, EXACT_GALLERY_PHOTOS)
    ):
        raise FreezeError("production-counts")

    sections = {
        "routes": routes,
        "pages": pages,
        "assets": list(package.assets),
        "files": list(package.files),
        "usages": list(package.usages),
        "gallery_albums": list(package.gallery_albums),
        "gallery_photos": list(package.gallery_photos),
    }
    unsigned = {
        "version": 1,
        "snapshot_id": session.snapshot_id,
        "site_settings": package.site_settings,
        "sections": sections,
    }
    root = {**unsigned, "digest": hashlib.sha256(_canonical(unsigned)).hexdigest()}
    manifest = parse_public_manifest(_canonical(root), limits)

    def resolve(source_page_id: uuid.UUID) -> TargetPageRef:
        try:
            return page_refs[source_page_id]
        except (KeyError, TypeError):
            raise FreezeError("page-resolver") from None

    return FrozenPublic(manifest, resolve)
