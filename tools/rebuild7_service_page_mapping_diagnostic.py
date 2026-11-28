from __future__ import annotations

import json
import uuid
from typing import Any


SCHEMA = "estakada.r7-service-page-mapping-diagnostic-v1"
SERVICE_ROUTES = (
    ("MAP-010", "/services/kuzovnoj-remont/"),
    ("MAP-011", "/services/planovoe-to/"),
    ("MAP-013", "/services/diagnostika/"),
    ("MAP-015", "/services/drugie-uslugi/shinomontazh/"),
    ("MAP-016", "/services/drugie-uslugi/sxod-razval"),
    ("MAP-019", "/services/kuzovnoj-remont/remont-kuzova"),
    ("MAP-020", "/services/kuzovnoj-remont/pokraska-avtomobilya"),
    ("MAP-021", "/services/kuzovnoj-remont/vosstanovlenie-geometrii-kuzova"),
    ("MAP-022", "/services/kuzovnoj-remont/remont-kuzovnyix-detalej-avtomobilya"),
    ("MAP-023", "/services/kuzovnoj-remont/zamena-detalej-kuzova"),
    ("MAP-024", "/services/kuzovnoj-remont/remont-posle-lobovogo-udara"),
    ("MAP-025", "/services/kuzovnoj-remont/stekla-i-faryi"),
    ("MAP-026", "/services/kuzovnoj-remont/polirovka-kuzova"),
    ("MAP-027", "/services/kuzovnoj-remont/zamena-lobovogo-stekla"),
    ("MAP-028", "/services/kuzovnoj-remont/ustranenie-czarapin"),
    ("MAP-029", "/services/kuzovnoj-remont/remont-bamperov"),
    ("MAP-030", "/services/planovoe-to/texnicheskoe-obsluzhivanie-to"),
    ("MAP-032", "/services/drugie-uslugi/zapravka-i-remont-kondiczionera/"),
    ("MAP-034", "/services/diagnostika/diagnostirovanie-avto-pered-priobreteniem"),
    ("MAP-035", "/services/planovoe-to/zamena-masla-v-dvigatele"),
    ("MAP-038", "/services/drugie-uslugi/polirovka-avto/"),
    ("MAP-040", "/services/diagnostika/diagnostika-tormoznoj-sistemyi"),
    ("MAP-041", "/services/planovoe-to/zamena-filtrov"),
    ("MAP-042", "/services/remont/remont-tormoznoj-sistemyi"),
    ("MAP-046", "/services/planovoe-to/zamena-salonnogo-filtra"),
    ("MAP-047", "/services/drugie-uslugi/evakuacziya-avtomobilya"),
    ("MAP-050", "/services/drugie-uslugi/obrabotka-porogov"),
    ("MAP-051", "/services/planovoe-to/zamena-tormoznyix-kolodok"),
    ("MAP-052", "/services/remont/remont-podveski"),
    ("MAP-054", "/services/planovoe-to/zamena-tormoznyix-diskov"),
    ("MAP-055", "/services/remont/remont-xodovoj-chasti"),
    ("MAP-058", "/services/remont/remont-rulevogo-upravleniya"),
    ("MAP-059", "/services/diagnostika/diagnostika-podveski"),
    ("MAP-060", "/services/planovoe-to/zamena-texnichenskix-zhidkostej"),
    ("MAP-062", "/services/diagnostika/diagnostika-xodovoj-chasti"),
    ("MAP-063", "/services/planovoe-to/zamena-svechej-zazhiganiya"),
    ("MAP-064", "/services/remont/remont-elektrooborudovaniya"),
    ("MAP-066", "/services/diagnostika/diagnostika-elektrooborudovaniya"),
    ("MAP-067", "/services/remont/zamena-remnya-grm"),
    ("MAP-068", "/services/remont/kondiczionera-klimatkontrolya-pechki"),
    ("MAP-069", "/services/remont/sxod-razval"),
    ("MAP-073", "/services/diagnostika/diagnostika-kondiczionerapechki"),
    ("MAP-074", "/services/planovoe-to/zamena-shhyotok-stekloochistetelej"),
    ("MAP-075", "/services/remont/remont-sistemyi-oxlazhdeniya"),
    ("MAP-079", "/services/diagnostika/diagnostika-sistemyi-oxlazhdeniya"),
    ("MAP-080", "/services/remont/remont-akppmkpprkppvariatora"),
    ("MAP-083", "/services/drugie-uslugi/regulirovka-far"),
    ("MAP-084", "/services/diagnostika/diagnostika-akppmkpprkppvariatora"),
    ("MAP-085", "/services/remont/remont-transmissii"),
    ("MAP-089", "/services/remont/remont-dvigatelya"),
    ("MAP-091", "/services/diagnostika/diagnostika-transmissii"),
    ("MAP-094", "/services/diagnostika/diagnostika-dvigatelya"),
    ("MAP-095", "/services/remont/remont-generatora"),
    ("MAP-098", "/services/remont/remont-startera"),
    ("MAP-101", "/services/remont/remont-vyixlopnoj-sistemyi"),
    ("MAP-104", "/services/remont/remont-sistemyi-zazhiganiya"),
    ("MAP-107", "/services/remont/remont-kommercheskogo-negabaritnogo"),
    ("MAP-115", "/services/avtomojka"),
)
ALLOWED_KINDS = frozenset({"service_section_overview", "service_detail"})


def fail() -> None:
    raise RuntimeError("R7_SERVICE_PAGE_MAPPING_DIAGNOSTIC_UNAVAILABLE")


def build_result(rows: list[dict[str, Any]]) -> dict[str, object]:
    authority = dict(SERVICE_ROUTES)
    if (
        len(SERVICE_ROUTES) != 58
        or len(authority) != 58
        or len(set(authority.values())) != 58
        or len(rows) != 58
    ):
        fail()
    by_target: dict[str, dict[str, Any]] = {}
    page_ids: set[str] = set()
    for row in rows:
        if type(row) is not dict or set(row) != {
            "target", "page_id", "page_kind", "mode", "outcome", "is_published"
        }:
            fail()
        target = row["target"]
        page_id = row["page_id"]
        page_kind = row["page_kind"]
        if (
            type(target) is not str
            or target not in authority.values()
            or target in by_target
            or type(page_id) is not str
            or type(page_kind) is not str
            or page_kind not in ALLOWED_KINDS
            or row["mode"] != "PRIMARY"
            or row["outcome"] != page_kind
            or row["is_published"] is not True
        ):
            fail()
        try:
            parsed = uuid.UUID(page_id)
        except (ValueError, AttributeError):
            fail()
        if str(parsed) != page_id or page_id in page_ids:
            fail()
        page_ids.add(page_id)
        by_target[target] = row
    if set(by_target) != set(authority.values()):
        fail()
    return {
        "schema": SCHEMA,
        "mappings": [
            {"map": map_id, "page_id": by_target[target]["page_id"]}
            for map_id, target in SERVICE_ROUTES
        ],
    }


def main() -> None:
    import django

    django.setup()
    from django.db import connection, transaction
    from modules.pages.models import Route, RouteMode

    targets = [target for _map_id, target in SERVICE_ROUTES]
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE, READ ONLY, DEFERRABLE"
            )
        rows = [
            {
                "target": str(row["target"]),
                "page_id": str(row["page_id"]),
                "page_kind": str(row["page__kind"]),
                "mode": str(row["mode"]),
                "outcome": str(row["outcome"]),
                "is_published": bool(row["page__is_published"]),
            }
            for row in Route.objects.filter(
                target__in=targets, mode=RouteMode.PRIMARY
            )
            .values(
                "target", "page_id", "page__kind", "mode", "outcome",
                "page__is_published",
            )
            .order_by("target")
        ]
        result = build_result(rows)
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
