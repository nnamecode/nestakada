from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from django.db import connections

from .models import Asset, AssetFile, AssetPurpose, AssetState, AssetUsage, FileKind, UsageScope


class MediaUsageError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class SiteLogoOption:
    asset_id: uuid.UUID
    mime_type: str
    width: int | None
    height: int | None


def _site_logo_usage(*, settings_id: uuid.UUID, current_logo_id: uuid.UUID, lock: bool) -> None:
    query = AssetUsage.objects.filter(
        scope=UsageScope.SITE_SETTINGS,
        target_uuid=settings_id,
    ).order_by("id")
    if lock:
        query = query.select_for_update()
    rows = list(query.values_list("slot", "position", "asset_id"))
    if rows != [("logo", 0, current_logo_id)]:
        raise MediaUsageError("MEDIA_USAGE_MISMATCH")


def project_site_logo_options(
    *,
    settings_id: uuid.UUID,
    current_logo_id: uuid.UUID,
    include_options: bool,
) -> tuple[SiteLogoOption, ...]:
    """Return a bounded public-metadata-only logo projection."""

    if (
        type(settings_id) is not uuid.UUID
        or type(current_logo_id) is not uuid.UUID
        or type(include_options) is not bool
    ):
        raise MediaUsageError("SITE_LOGO_UNAVAILABLE")
    try:
        _site_logo_usage(
            settings_id=settings_id,
            current_logo_id=current_logo_id,
            lock=False,
        )
        assets_query = Asset.objects.filter(
            purpose=AssetPurpose.SITE_ASSET,
            state=AssetState.READY,
        ).order_by("id")
        if include_options:
            asset_ids = list(assets_query.values_list("id", flat=True)[:65])
            if not 1 <= len(asset_ids) <= 64 or current_logo_id not in asset_ids:
                raise MediaUsageError("SITE_LOGO_UNAVAILABLE")
        else:
            if not assets_query.filter(pk=current_logo_id).exists():
                raise MediaUsageError("SITE_LOGO_UNAVAILABLE")
            asset_ids = [current_logo_id]
        files = list(
            AssetFile.objects.filter(asset_id__in=asset_ids, kind=FileKind.MAIN)
            .order_by("asset_id")
            .values_list("asset_id", "mime_type", "width", "height")
        )
        if len(files) != len(asset_ids) or {row[0] for row in files} != set(asset_ids):
            raise MediaUsageError("SITE_LOGO_UNAVAILABLE")
        return tuple(SiteLogoOption(*row) for row in files)
    except MediaUsageError as exc:
        if exc.code == "SITE_LOGO_UNAVAILABLE":
            raise
        raise MediaUsageError("SITE_LOGO_UNAVAILABLE") from exc


def lock_site_logo_usage(
    *,
    settings_id: uuid.UUID,
    current_asset_id: uuid.UUID,
    new_asset_id: uuid.UUID,
) -> None:
    """Lock and validate all scalar site-logo participants without mutation."""

    if not connections["default"].in_atomic_block:
        raise RuntimeError("Site logo usage must be replaced inside an atomic transaction.")
    if any(type(value) is not uuid.UUID for value in (settings_id, current_asset_id, new_asset_id)):
        raise MediaUsageError("MEDIA_NOT_READY")
    asset_ids = sorted({current_asset_id, new_asset_id}, key=str)
    assets = list(
        Asset.objects.select_for_update().filter(pk__in=asset_ids).order_by("id")
    )
    if (
        len(assets) != len(asset_ids)
        or any(
            asset.state != AssetState.READY or asset.purpose != AssetPurpose.SITE_ASSET
            for asset in assets
        )
    ):
        raise MediaUsageError("MEDIA_NOT_READY")
    _site_logo_usage(
        settings_id=settings_id,
        current_logo_id=current_asset_id,
        lock=True,
    )


def replace_site_logo_usage(
    *,
    settings_id: uuid.UUID,
    current_asset_id: uuid.UUID,
    new_asset_id: uuid.UUID,
) -> None:
    """Replace the validated scalar site-logo projection inside the owner transaction."""

    lock_site_logo_usage(
        settings_id=settings_id,
        current_asset_id=current_asset_id,
        new_asset_id=new_asset_id,
    )
    if new_asset_id == current_asset_id:
        return
    AssetUsage.objects.filter(
        scope=UsageScope.SITE_SETTINGS,
        target_uuid=settings_id,
    ).delete()
    usage = AssetUsage(
        asset_id=new_asset_id,
        scope=UsageScope.SITE_SETTINGS,
        target_uuid=settings_id,
        slot="logo",
        position=0,
    )
    usage.full_clean()
    usage.save(force_insert=True)


def _rows(
    *,
    page_id: uuid.UUID,
    scope: str,
    media: Mapping[str, Sequence[str]],
) -> list[AssetUsage]:
    rows: list[AssetUsage] = []
    for slot in sorted(media):
        values = media[slot]
        if not isinstance(slot, str) or not isinstance(values, list):
            raise MediaUsageError("MEDIA_SHAPE")
        for position, value in enumerate(values):
            try:
                asset_id = uuid.UUID(value)
            except (ValueError, TypeError, AttributeError):
                raise MediaUsageError("MEDIA_ID") from None
            if str(asset_id) != value:
                raise MediaUsageError("MEDIA_ID")
            rows.append(AssetUsage(
                asset_id=asset_id,
                scope=scope,
                target_uuid=page_id,
                slot=slot,
                position=position,
            ))
    return rows


def replace_page_usages(
    *,
    page_id: uuid.UUID,
    current: Mapping[str, Sequence[str]],
    previous: Mapping[str, Sequence[str]],
) -> None:
    """Replace both page-version usage projections inside a pages-owned transaction."""

    if not connections["default"].in_atomic_block:
        raise RuntimeError("Page usages must be replaced inside an atomic transaction.")
    rows = [
        *_rows(page_id=page_id, scope=UsageScope.PAGE_CURRENT, media=current),
        *_rows(page_id=page_id, scope=UsageScope.PAGE_PREVIOUS, media=previous),
    ]
    asset_ids = sorted({row.asset_id for row in rows}, key=str)
    assets = list(
        Asset.objects
        .select_for_update()
        .filter(pk__in=asset_ids)
        .order_by("id")
    )
    if (
        len(assets) != len(asset_ids)
        or any(
            asset.state != AssetState.READY or asset.purpose != AssetPurpose.CONTENT
            for asset in assets
        )
    ):
        raise MediaUsageError("MEDIA_NOT_READY")

    existing = list(
        AssetUsage.objects
        .select_for_update()
        .filter(
            target_uuid=page_id,
            scope__in=(UsageScope.PAGE_CURRENT, UsageScope.PAGE_PREVIOUS),
        )
        .order_by("id")
        .values_list("id", flat=True)
    )
    if existing:
        AssetUsage.objects.filter(pk__in=existing).delete()
    if rows:
        AssetUsage.objects.bulk_create(rows)


def verify_page_current_usages(
    *,
    page_id: uuid.UUID,
    expected_media: Mapping[str, Sequence[str]],
) -> None:
    """Prove the exact current-page usage projection without mutating it."""

    if not connections["default"].in_atomic_block:
        raise RuntimeError("Page usage verification requires an outer transaction.")
    expected_rows = _rows(
        page_id=page_id,
        scope=UsageScope.PAGE_CURRENT,
        media=expected_media,
    )
    expected = sorted(
        (row.slot, row.position, row.asset_id)
        for row in expected_rows
    )
    actual_asset_ids = list(
        AssetUsage.objects.filter(
            target_uuid=page_id,
            scope=UsageScope.PAGE_CURRENT,
        ).values_list("asset_id", flat=True)
    )
    asset_ids = sorted(
        {*(row.asset_id for row in expected_rows), *actual_asset_ids},
        key=str,
    )
    assets = list(
        Asset.objects.select_for_update().filter(pk__in=asset_ids).order_by("id")
    )
    if (
        len(assets) != len(asset_ids)
        or any(
            asset.state != AssetState.READY or asset.purpose != AssetPurpose.CONTENT
            for asset in assets
        )
    ):
        raise MediaUsageError("MEDIA_NOT_READY")
    actual_rows = list(
        AssetUsage.objects.select_for_update()
        .filter(target_uuid=page_id, scope=UsageScope.PAGE_CURRENT)
        .order_by("slot", "position", "asset_id", "id")
    )
    actual = [(row.slot, row.position, row.asset_id) for row in actual_rows]
    if actual != expected:
        raise MediaUsageError("MEDIA_USAGE_MISMATCH")
