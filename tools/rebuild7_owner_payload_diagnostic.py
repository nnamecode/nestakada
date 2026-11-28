from __future__ import annotations

import json
import os
import sys
from typing import Any


SCHEMA = "estakada.r7-owner-payload-diagnostic-v1"
CATEGORIES = frozenset(
    {
        "PAYLOAD_SHAPE",
        "HERO_TARGET",
        "HERO_OTHER",
        "MAP019_HERO_NULL",
        "MAP019_HERO_TARGET",
        "MAP019_HERO_OTHER",
        "MAP019_BODY_NONEMPTY",
    }
)
MAP_IDS = frozenset(
    {
        "MAP-010", "MAP-011", "MAP-013", "MAP-015", "MAP-016", "MAP-019",
        "MAP-020", "MAP-021", "MAP-022", "MAP-023", "MAP-024", "MAP-025",
        "MAP-026", "MAP-027", "MAP-028", "MAP-029", "MAP-030", "MAP-032",
        "MAP-034", "MAP-035", "MAP-038", "MAP-040", "MAP-041", "MAP-042",
        "MAP-046", "MAP-047", "MAP-050", "MAP-051", "MAP-052", "MAP-054",
        "MAP-055", "MAP-058", "MAP-059", "MAP-060", "MAP-062", "MAP-063",
        "MAP-064", "MAP-066", "MAP-067", "MAP-068", "MAP-069", "MAP-073",
        "MAP-074", "MAP-075", "MAP-079", "MAP-080", "MAP-083", "MAP-084",
        "MAP-085", "MAP-089", "MAP-091", "MAP-094", "MAP-095", "MAP-098",
        "MAP-101", "MAP-104", "MAP-107", "MAP-115",
    }
)


def fail() -> None:
    raise RuntimeError("R7_OWNER_PAYLOAD_DIAGNOSTIC_UNAVAILABLE")


def classify_payload(
    row: dict[str, Any], payload: object, infographic_asset_id: str, map019_page_id: str
) -> str | None:
    try:
        if type(payload) is not dict:
            return "PAYLOAD_SHAPE"
        fields = payload["fields"]
        if type(fields) is not dict:
            return "PAYLOAD_SHAPE"
        media = fields["media"]
        if type(media) is not dict or "hero" not in media:
            return "PAYLOAD_SHAPE"
        hero = media["hero"]
    except (KeyError, TypeError):
        return "PAYLOAD_SHAPE"

    if str(row["page_id"]) == map019_page_id:
        if hero is None:
            return "MAP019_HERO_NULL"
        if hero == str(row["asset_id"]):
            return "MAP019_HERO_TARGET"
        if hero != infographic_asset_id:
            return "MAP019_HERO_OTHER"
        if media.get("body") != []:
            return "MAP019_BODY_NONEMPTY"
        return None

    if hero is None:
        return None
    if hero == str(row["asset_id"]):
        return "HERO_TARGET"
    return "HERO_OTHER"


def build_result(
    rows: tuple[dict[str, Any], ...], payloads: dict[str, object], infographic_asset_id: str, map019_page_id: str
) -> dict[str, object]:
    if (
        len(rows) != 58
        or len(payloads) != 58
        or set(payloads) != {str(row["page_id"]) for row in rows}
        or {str(row["map_id"]) for row in rows} != MAP_IDS
    ):
        fail()
    mismatches = []
    for row in sorted(rows, key=lambda item: str(item["map_id"])):
        map_id = str(row["map_id"])
        if map_id not in MAP_IDS:
            fail()
        category = classify_payload(
            row, payloads[str(row["page_id"])], infographic_asset_id, map019_page_id
        )
        if category is not None:
            if category not in CATEGORIES:
                fail()
            mismatches.append({"map": map_id, "category": category})
    if not mismatches:
        fail()
    return {"schema": SCHEMA, "mismatches": mismatches}


def run() -> None:
    if len(sys.argv) != 1:
        fail()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local_restore")
    import django

    django.setup()
    from django.db import connection, transaction

    from modules.pages.models import PageContent
    from rebuild3_importer.service_media import (
        INFOGRAPHIC_ASSET_ID,
        MAP019_PAGE_ID,
        service_media_rows,
    )

    rows = service_media_rows()
    page_ids = [row["page_id"] for row in rows]
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE, READ ONLY, DEFERRABLE"
            )
        payloads = {
            str(page_id): payload
            for page_id, payload in PageContent.objects.filter(page_id__in=page_ids)
            .order_by("page_id")
            .values_list("page_id", "current_payload")
        }
    result = build_result(rows, payloads, INFOGRAPHIC_ASSET_ID, MAP019_PAGE_ID)
    print(
        "R7_OWNER_PAYLOAD_DIAGNOSTIC_OK "
        + json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    )


if __name__ == "__main__":
    try:
        run()
    except BaseException:
        raise RuntimeError("R7_OWNER_PAYLOAD_DIAGNOSTIC_UNAVAILABLE") from None
