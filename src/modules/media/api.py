from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

from django.db import connections

from .models import Asset, AssetPurpose, AssetState, AssetUsage, UsageScope


class MediaUsageError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


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
