from __future__ import annotations

import copy
import uuid
from typing import Any

from rebuild3_importer.errors import ManifestError


_NAMESPACE = uuid.UUID("08782b79-2219-5f2b-94cf-dd245b324ae6")
INFOGRAPHIC_ASSET_ID = "6fa5cdd8-dabd-52ab-b994-4e10ef2cb2c8"
MAP019_PAGE_ID = "080d64ee-4ce1-5399-b672-83dc22f9f8bf"
_EXPECTED_MAP_IDS = frozenset({
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
})

_ROWS = (
    ("MAP-010", "206083cd-b864-57b2-ad24-f3835e07ffd6", "media/design-concepts/services-v4/body-repair.webp", 137872, "783e8200f1ffdb3beaa6ff883ecfea682dbe7263baa11d252d436e7198fa933d", "Кузовной ремонт"),
    ("MAP-015", "773eedaa-da12-5231-b384-b34669b44170", "media/design-concepts/services-v4/tire-service-v1.webp", 211750, "6f6bfe02dfb78c320ecccce26a4c1948ca7e876212f1bd3d1d67ce96c6ed677f", "Шиномонтаж"),
    ("MAP-016", "944cabaf-4a36-560c-8ec6-c3a35b79b8ee", "media/design-concepts/services-v4/wheel-alignment-alt-v1.webp", 198370, "2ab7c5bcd81bab3f9b9859df4809c6f15fc8795cf06b2bdb8a7cf5f526651bda", "Сход-развал"),
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
    ("MAP-069", "328329a3-79d5-55e0-9560-02f113542e41", "media/design-concepts/services-v4/wheel-alignment-v1.webp", 173550, "10d6c62d2ccb0f2f69f323df3a55dfbc22665300dfdaa2ff54f5482da783af1b", "Сход-развал"),
    ("MAP-073", "3d20cd31-a956-5993-b2f9-82d8851ecc75", "media/design-concepts/services-v4/climate-system-diagnostics-v1.webp", 202332, "3c1256c7f87ba38d66eb68a2e66290a5833a7da80e75ee745061e26b92e59e8a", "Диагностика кондиционера и печки"),
    ("MAP-083", "82946366-0148-5158-afb8-2c80fa3564f4", "media/design-concepts/services-v4/headlight-adjustment-v1.webp", 161086, "e1ca9371c7eee4aacd82f24fad94d4e2094d1e1b24cc6950db3ac79ef94794cf", "Регулировка фар"),
    ("MAP-089", "c4884f81-dbc7-5b75-9f13-181d04539f5c", "media/design-concepts/services-v4/engine-overhaul-v1.webp", 199450, "1aa8183729c583fe1959f5213ecced803a61f3fc1d3f0211a75119be7a3e1d8c", "Ремонт двигателя"),
    ("MAP-011", "4359fedb-0703-41a0-b76c-faaa165073ca", "media/design-concepts/services-v4/scheduled-maintenance-detail-v1.webp", 196596, "bb8f858b48c7f777b6776afb5e7ebd84b937e0c354120c33552761f772880d81", "Плановое ТО"),
    ("MAP-013", "2171f684-ccda-4402-b2be-f498b665f5b5", "media/design-concepts/services-v4/computer-diagnostics-v1.webp", 175228, "e9fda136b8113ee615ad5ea7dd9e9a266e050fd1094d9cabeae79a0cdb976a6e", "Компьютерная диагностика автомобиля"),
    ("MAP-030", "49e44e5d-9bde-46e9-ac59-76118db6299d", "media/design-concepts/services-v4/technical-maintenance-detail-v1.webp", 160946, "f394f73f5d06bf0d1d374a866998de0175d19ad74cc5aad1171bc0ad9632c33f", "Техническое Обслуживание (ТО)"),
    ("MAP-034", "0a9ed67e-67ae-4854-a139-a7ede3972bde", "media/design-concepts/services-v4/pre-purchase-car-inspection-v1.webp", 183448, "97efcd91d193a2e969c32d69db085c2b88112405b841f925dd35e2ceb1351a4a", "Диагностирование авто перед приобретением"),
    ("MAP-035", "567db00e-f835-408f-9b39-f79e379b7cc3", "media/design-concepts/services-v4/engine-oil-change-detail-v1.webp", 174688, "675ed7ab6c03e6ed6b2a80f4ac650d904353397fe43085accf193c972e5171a7", "Замена масла в двигателе"),
    ("MAP-040", "2b083fea-a676-46a8-8f0e-cff48d6b88de", "media/design-concepts/services-v4/brake-system-diagnostics-v1.webp", 147070, "bc29e13a7e48c34ef3e244225d3eb73f9d4219995aaca12b5fffd3fd6738de26", "Диагностика тормозной системы"),
    ("MAP-042", "c176ea0e-e37c-4f7b-9e7c-3f4ca73608cb", "media/design-concepts/services-v4/brake-system-repair-v1.webp", 151186, "d4776bc84d705440733dfb10616446f47bad798fdd280b0e7cb34b7259adbf7d", "Ремонт тормозной системы"),
    ("MAP-046", "66cbd76e-e2e8-46a0-a4e2-18b1533ee63f", "media/design-concepts/services-v4/cabin-filter-replacement-detail-v1.webp", 135852, "5401aa7c5ac44cf7a17e953e363eec0f69734c6a8a72fd218d0a848e17cd5d6c", "Замена салонного фильтра"),
    ("MAP-047", "cd7ece74-a74b-427c-ba26-0ff70fe80635", "media/design-concepts/services-v4/vehicle-recovery-flatbed-v1.webp", 263978, "a053fb88bfe06a3f7ce3498419491929b00306ddadec107f7e9f66fd628730c0", "Эвакуация автомобиля"),
    ("MAP-050", "cda9b4b6-002b-4526-89aa-9b0e79eeb368", "media/design-concepts/services-v4/rocker-panel-antigravel-v1.webp", 181954, "03b71c8c46dc34575bafdbd34307c4b69692516a56dcfda5a10ee91931de5aa0", "Обработка порогов"),
    ("MAP-051", "39b0875f-2b79-46b5-8728-bd40a41184a1", "media/design-concepts/services-v4/brake-pad-replacement-detail-v1.webp", 145488, "88a91c694a572e8ae5567e00fadcfb07e09235a5629136b89a7e29c68578aabc", "Замена тормозных колодок"),
    ("MAP-052", "38a4be87-aae5-4776-a32d-10407f70eac9", "media/design-concepts/services-v4/suspension-repair-v1.webp", 159682, "8e86b4f835c64d91dc3e89f14166f631690a926a6bd493240b7919e27ad6ca66", "Ремонт подвески"),
    ("MAP-054", "c8d6af90-725e-458e-a88b-0ef188a922ae", "media/design-concepts/services-v4/brake-disc-replacement-detail-v1.webp", 155158, "1e453f50fad735d077c93c0c3611002893e6c44bb52ef2d41ce432ff74d42e44", "Замена тормозных дисков"),
    ("MAP-055", "1078747a-4264-4ba6-9980-b981b4e52e8c", "media/design-concepts/services-v4/running-gear-repair-v1.webp", 203142, "267d89ed84167da0ea810f1f8b20e65bb271babe379767a09e48d631d11b78d7", "Ремонт ходовой части"),
    ("MAP-059", "42d0463d-e852-4679-86a5-b6302336d505", "media/design-concepts/services-v4/suspension-diagnostics-v1.webp", 163484, "0cdb31076c2ae1c833b30a95f24f502d8bc8859ca2c88b3f200fa0fce489f30f", "Диагностика подвески"),
    ("MAP-060", "fdf7901d-6699-4fc1-90a3-7e7bb37d5c04", "media/design-concepts/services-v4/technical-fluids-replacement-detail-v1.webp", 176578, "53a6273e912f87b6472110c72b3a101e152ad7073272630b033b937bbf20407c", "Замена техниченских жидкостей"),
    ("MAP-062", "b97f4f53-a14c-467f-a807-5026b0f6f1ad", "media/design-concepts/services-v4/running-gear-diagnostics-v1.webp", 204970, "db2bf62273ac10ef05176ba487005bedc653e7b1fb03dd29edfe5d8dd1862483", "Диагностика ходовой части"),
    ("MAP-063", "95de515f-cfda-432f-8e6b-bce0b9808e75", "media/design-concepts/services-v4/spark-plug-replacement-detail-v1.webp", 180914, "4c61d8de891a81e36a3e3decd77ca4b7277e0f45a23711f11987537958493749", "Замена свечей зажигания"),
    ("MAP-064", "92858ae1-d4ba-4e48-9370-642bce5f1999", "media/design-concepts/services-v4/auto-electrical-repair-v1.webp", 156788, "66cdefb0783091ec1ed5e51ae212c88a4a46e27518355cfcfdc89ecc13c948f6", "Ремонт электрооборудования"),
    ("MAP-066", "58507a9f-89ac-4546-bad9-957dd818f246", "media/design-concepts/services-v4/electrical-system-diagnostics-v1.webp", 154092, "87210b952d91e26cf72cc3045c282feedb41ba8019891ca7f5033fee44927bda", "Диагностика электрооборудования"),
    ("MAP-067", "9f940baf-a1bf-4d0b-ad24-feb6d2c0a070", "media/design-concepts/services-v4/timing-belt-replacement-v1.webp", 201224, "cfee70eace9d4d1b837b7c745219947ab2d2cea8c35aa0af76f85f3496336f9e", "Замена ремня ГРМ"),
    ("MAP-074", "f0a24fb2-6924-4b7f-af7a-2ea227196563", "media/design-concepts/services-v4/wiper-blade-replacement-detail-v1.webp", 176258, "b4941ff8cc2aed54e28efd29a312e807294652a4b9761b540a00c217d88c93a4", "Замена щёток стеклоочистетелей"),
    ("MAP-075", "de93552c-7bba-4385-b1ec-870435157579", "media/design-concepts/services-v4/cooling-system-repair-v1.webp", 174914, "5babf24b298ef6335d945b16b423d6490a0e947570068629c1d541c33f85f924", "Ремонт системы охлаждения"),
    ("MAP-079", "b03e4d41-246f-493d-af9c-89d39ae8bb6b", "media/design-concepts/services-v4/cooling-system-diagnostics-v1.webp", 199470, "75864393dfb6e14962d658bcebd67023235878613ef953e7ab85da35db9f21c5", "Диагностика системы охлаждения"),
    ("MAP-080", "29eb36ce-e161-4ac2-bc3a-e7510d018e90", "media/design-concepts/services-v4/gearbox-overhaul-v1.webp", 223824, "3ccf1d76ad84cfcc83d07f0d697835a66463779002eceb201b492e201d6cdf0d", "Капитальный ремонт АКПП/МКПП/РКПП/Вариатора"),
    ("MAP-084", "e7d5b8ed-824c-49db-8fef-b78210d869e3", "media/design-concepts/services-v4/gearbox-diagnostics-v1.webp", 169588, "de27fe96df0cf398f25a53307bae4f982e4052b61be720cf7b30f7d3bf5a90b6", "Диагностика АКПП/МКПП/РКПП/Вариатора"),
    ("MAP-085", "9178b8f5-9461-41c4-a753-afd923f8c592", "media/design-concepts/services-v4/drivetrain-repair-v1.webp", 206584, "d3aa17edb7620876f070427e882306e80319f804ae2a793f3e50c5ef4a4d064f", "Ремонт трансмиссии"),
    ("MAP-091", "2bd689c2-5fba-48b8-9532-58dc1fbe281e", "media/design-concepts/services-v4/drivetrain-diagnostics-v1.webp", 211118, "307e9be0fe2f2ea27ab06c0abd5108077c1ee74eff9cfa73bb31c966673c66d9", "Диагностика трансмиссии"),
    ("MAP-094", "82292f8e-d5e7-47e4-b5d5-0fc8a4242e34", "media/design-concepts/services-v4/engine-diagnostics-v1.webp", 194082, "2d9cb0f265c516b0bc108ef6c9724b5a8909012c9cb30b9a515d4da0368fca70", "Диагностика двигателя"),
    ("MAP-095", "c46751ca-6822-4bdb-b5f2-7c5d14f9132f", "media/design-concepts/services-v4/alternator-repair-v1.webp", 209004, "f622651525d4be20f07874b2e4c66437a55f3913e8c62ff00bec3adac0bca089", "Ремонт генератора"),
    ("MAP-098", "5ce13aec-a88f-4881-a920-dd4118a384bf", "media/design-concepts/services-v4/starter-repair-v1.webp", 202078, "f759e4cad7b3c53337d153518bb3922783a22b058e78a34b7093f4f77bbbbfd9", "Ремонт стартера"),
    ("MAP-101", "36e686ee-21e5-4712-bc2f-9de9600ffa3e", "media/design-concepts/services-v4/exhaust-system-repair-v1.webp", 166950, "edf4702e5d359a3ba915152a30ac011d57fd08edf285324ac5db43d7c249048d", "Ремонт выхлопной системы"),
    ("MAP-104", "d602432b-7326-4718-b243-0d35012e4f3a", "media/design-concepts/services-v4/ignition-system-diagnostics-v1.webp", 177394, "55b2d5f36ee3f6c1c5c4ce1dd0151223fbcea4658aa5ad1fb418828815044205", "Ремонт системы зажигания"),
    ("MAP-107", "d6509b60-e4be-4466-9f4f-f5a37710a170", "media/design-concepts/services-v4/commercial-oversized-vehicle-repair-v1.webp", 185948, "b0ca1633e1a82cb45a7ffbfb1aa98b07ad316a9999426786fea38b7743911670", "Ремонт коммерческого (негабаритного, любой длины и высоты) транспорта до 10 тонн"),
    ("MAP-115", "07c018a9-1431-5a7e-8c84-b28aa5361d25", "media/design-concepts/services-v4/car-wash.webp", 277134, "efef7ac707f9fad0c9330814640d47b58cfb8f45ae5dc44e0bccce2af1c307af", "Автомойка"),
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
    } for map_id, page_id, source_path, byte_size, digest, alt in sorted(_ROWS))
    if (
        len(rows) != 58
        or {row["map_id"] for row in rows} != _EXPECTED_MAP_IDS
        or len({row["page_id"] for row in rows}) != 58
        or len({row["source_path"] for row in rows}) != 58
        or len({row["asset_id"] for row in rows}) != 58
        or len({row["file_id"] for row in rows}) != 58
        or sum(row["byte_size"] for row in rows) != 10_531_478
        or any(
            not row["source_path"].startswith("media/design-concepts/services-v4/")
            or not row["source_path"].endswith(".webp")
            or len(row["sha256"]) != 64
            or any(character not in "0123456789abcdef" for character in row["sha256"])
            or not row["alt"]
            for row in rows
        )
    ):
        raise ManifestError("service-media-authority")
    try:
        if any(str(uuid.UUID(row["page_id"])) != row["page_id"] for row in rows):
            raise ManifestError("service-media-authority")
    except (ValueError, AttributeError):
        raise ManifestError("service-media-authority") from None
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
        if (
            previous_hero is not None
            and previous_hero != INFOGRAPHIC_ASSET_ID
        ) or body != []:
            raise ManifestError("service-media-payload")
        if previous_hero == INFOGRAPHIC_ASSET_ID:
            media["body"] = [INFOGRAPHIC_ASSET_ID]
    elif previous_hero is not None:
        raise ManifestError("service-media-payload")
    media["hero"] = row["asset_id"]
    return result
