from __future__ import annotations

import copy
import uuid
from typing import Any

from rebuild3_importer.errors import ManifestError


_NAMESPACE = uuid.UUID("08782b79-2219-5f2b-94cf-dd245b324ae6")
INFOGRAPHIC_ASSET_ID = "6fa5cdd8-dabd-52ab-b994-4e10ef2cb2c8"
MAP019_PAGE_ID = "080d64ee-4ce1-5399-b672-83dc22f9f8bf"

_ROWS = (
    ("MAP-010", "206083cd-b864-57b2-ad24-f3835e07ffd6", "media/design-concepts/services-v4/body-repair.webp", 137872, "783e8200f1ffdb3beaa6ff883ecfea682dbe7263baa11d252d436e7198fa933d", "Кузовной ремонт"),
    ("MAP-015", "773eedaa-da12-5231-b384-b34669b44170", "media/design-concepts/services-v4/tire-service-v1.webp", 211750, "6f6bfe02dfb78c320ecccce26a4c1948ca7e876212f1bd3d1d67ce96c6ed677f", "Шиномонтаж"),
    ("MAP-016", "944cabaf-4a36-560c-8ec6-c3a35b79b8ee", "media/design-concepts/services-v4/wheel-alignment-v1.webp", 173550, "10d6c62d2ccb0f2f69f323df3a55dfbc22665300dfdaa2ff54f5482da783af1b", "Сход-развал"),
    ("MAP-019", "080d64ee-4ce1-5399-b672-83dc22f9f8bf", "media/design-concepts/services-v4/body-repair-detail-v1.webp", 167142, "fe7fa0fce9a5768c3d08e66a50d4bf115d3d3026745042adb5b1ec6ba1906705", "Ремонт кузова"),
    ("MAP-020", "0d7b65ca-637b-5aac-a5a5-4ac27f0699c3", "media/design-concepts/services-v4/car-painting-detail-v1.webp", 171006, "188e2e17ab50a64fd4f1c8f9b62ed64a328ed4000d05d0da8e0b723c4aba94ee", "Покраска автомобиля"),
    ("MAP-021", "28c7638c-e5c5-5a46-9189-11d1c085b240", "media/design-concepts/services-v4/body-geometry-detail-v1.webp", 192280, "07bfb481457e4f2ab9de944333f3026c262bfaeef482ce5d3e07d252877d3b26", "Восстановление геометрии кузова"),
    ("MAP-022", "bc0edca3-d9d9-5161-9a50-5e48467bdb3e", "media/design-concepts/services-v4/body-panel-repair-detail-v1.webp", 178628, "f754d0dd5c0efc85f4c25bd89cd705496337871cdc169d5468fc6b5d77225c54", "Ремонт кузовных деталей автомобиля"),
    ("MAP-023", "381ee934-7a7a-5ebf-a279-296d8939304f", "media/design-concepts/services-v4/body-parts-replacement-detail-v1.webp", 196912, "4d39a756b900c342bde04d976b32067c4ae863233a5665ba51d15fe122313de2", "Замена деталей кузова"),
    ("MAP-024", "fa2aeda9-f2eb-5c12-b445-c966c5f9996b", "media/design-concepts/services-v4/frontal-impact-repair-detail-v1.webp", 238992, "a7e3b5e838a2e65befe30cd6ef7257ba7823900f9959eb258d7534371a508325", "Ремонт после лобового удара"),
    ("MAP-025", "382f06ac-d3f2-5d5a-854c-f884314c2e73", "media/design-concepts/services-v4/glass-headlights-detail-v1.webp", 160750, "5d6dd84f1798bec0a7d395ab75d2c4c9dd7087aaafa19506b36d272efda67ef9", "Стекла и фары"),
    ("MAP-026", "ff9a1582-bdd9-541d-9502-55a8c6ef19b6", "media/design-concepts/services-v4/body-polishing-detail-v1.webp", 192324, "9b57ce677d9bd477e4477cfd8c5f5185b8a58164093da9451d3815d8287adc14", "Полировка кузова"),
    ("MAP-027", "2b97b0b1-a270-5d21-9639-fcbd82126be5", "media/design-concepts/services-v4/windshield-replacement-detail-v1.webp", 161312, "99909d37dbbac1fd4acc1d7ddc85274b7ec425f5a893ff1f966ee253e4b01be6", "Замена лобового стекла"),
    ("MAP-028", "86038bbe-4866-5cb4-b664-f928c8fd926c", "media/design-concepts/services-v4/scratch-removal-detail-v1.webp", 144968, "95e7aa7c00e5e6ddb1f71f7082d92d58acad617babdca0d10528343c8d4aa127", "Устранение царапин"),
    ("MAP-029", "d602d9e7-a0b2-50f1-b83a-faef478e7f68", "media/design-concepts/services-v4/bumper-repair-detail-v1.webp", 189536, "0d6683b19e20bb680d80fb389bd26bf48be32254fbe272a8bc7c55deac2f6cdb", "Ремонт бамперов"),
    ("MAP-032", "19f32118-3108-58c5-9e2f-a15cfe2a9f49", "media/design-concepts/services-v4/ac-recharge-service-v1.webp", 209074, "12b4c56c53187d9389840fd988860eee109ceeac335e8da33bb554fdbe1d71bc", "Заправка и ремонт кондиционера"),
    ("MAP-038", "a3345a17-0853-5b7b-9574-9c6628e74a60", "media/design-concepts/services-v4/auto-polishing-studio-v1.webp", 112498, "c045e82ce2aa8b3a56e27080773cb0e42d2f6a6a95ab6e8c308253c297b9e4f2", "Полировка авто"),
    ("MAP-041", "56528881-b8b3-58df-b795-0cfee0bd736d", "media/design-concepts/services-v4/filter-replacement-detail-v1.webp", 172112, "bb29eefdfa31d7b4ccca7da3cf0b5d1dfb2be52e77db5485811f07da54891537", "Замена фильтров"),
    ("MAP-058", "e71a298b-763b-5ef1-be49-8cb8a37753d8", "media/design-concepts/services-v4/steering-system-repair-v1.webp", 141538, "dc01fe54b6698a2facffa95248d8ae5cd8d00738cfac4e90290ac97c50fd84a4", "Ремонт рулевого управления"),
    ("MAP-068", "dc50dcf3-53a5-5066-a706-58cdb5966ddd", "media/design-concepts/services-v4/climate-control-service-v1.webp", 171184, "3ec1f09b3b937d134092da1229adc1d7963bf3e698f4962a1ea39be59942fd92", "Климат-контроль, печка"),
    ("MAP-069", "328329a3-79d5-55e0-9560-02f113542e41", "media/design-concepts/services-v4/wheel-alignment-alt-v1.webp", 198370, "2ab7c5bcd81bab3f9b9859df4809c6f15fc8795cf06b2bdb8a7cf5f526651bda", "Сход-развал"),
    ("MAP-073", "3d20cd31-a956-5993-b2f9-82d8851ecc75", "media/design-concepts/services-v4/climate-system-diagnostics-v1.webp", 202332, "3c1256c7f87ba38d66eb68a2e66290a5833a7da80e75ee745061e26b92e59e8a", "Диагностика кондиционера и печки"),
    ("MAP-083", "82946366-0148-5158-afb8-2c80fa3564f4", "media/design-concepts/services-v4/headlight-adjustment-v1.webp", 161086, "e1ca9371c7eee4aacd82f24fad94d4e2094d1e1b24cc6950db3ac79ef94794cf", "Регулировка фар"),
    ("MAP-089", "c4884f81-dbc7-5b75-9f13-181d04539f5c", "media/design-concepts/services-v4/engine-overhaul-v1.webp", 199450, "1aa8183729c583fe1959f5213ecced803a61f3fc1d3f0211a75119be7a3e1d8c", "Ремонт двигателя"),
)


def service_media_rows() -> tuple[dict[str, Any], ...]:
    rows = tuple({
        "map_id": map_id,
        "page_id": page_id,
        "source_path": source_path,
        "byte_size": byte_size,
        "sha256": digest,
        "alt": alt,
        "asset_id": str(uuid.uuid5(_NAMESPACE, "asset:" + source_path)),
        "file_id": str(uuid.uuid5(_NAMESPACE, "file:" + source_path)),
    } for map_id, page_id, source_path, byte_size, digest, alt in _ROWS)
    if (
        len(rows) != 23
        or len({row["map_id"] for row in rows}) != 23
        or len({row["page_id"] for row in rows}) != 23
        or len({row["source_path"] for row in rows}) != 23
        or len({row["asset_id"] for row in rows}) != 23
        or len({row["file_id"] for row in rows}) != 23
        or any(row["map_id"] == "MAP-115" for row in rows)
    ):
        raise ManifestError("service-media-authority")
    return rows


def service_media_by_page() -> dict[str, dict[str, Any]]:
    return {row["page_id"]: row for row in service_media_rows()}


def service_media_by_pair() -> dict[tuple[str, int], dict[str, Any]]:
    return {(row["sha256"], row["byte_size"]): row for row in service_media_rows()}


def bind_service_media(payload: dict[str, Any], page_id: str) -> dict[str, Any]:
    row = service_media_by_page().get(page_id)
    if row is None:
        return payload
    result = copy.deepcopy(payload)
    try:
        media = result["fields"]["media"]
        previous_hero = media["hero"]
    except (KeyError, TypeError):
        raise ManifestError("service-media-payload") from None
    if page_id == MAP019_PAGE_ID:
        body = media.get("body")
        if previous_hero != INFOGRAPHIC_ASSET_ID or body != []:
            raise ManifestError("service-media-payload")
        media["body"] = [INFOGRAPHIC_ASSET_ID]
    elif previous_hero is not None:
        raise ManifestError("service-media-payload")
    media["hero"] = row["asset_id"]
    return result
