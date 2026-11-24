from __future__ import annotations

import argparse
import json
import os
import re
import uuid


ASSET_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
FILE_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
SETTINGS_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
PAGE_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
ROUTE_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")


def fail(code: str = "R7C_SYNTHETIC_FIXTURE_UNAVAILABLE") -> None:
    raise RuntimeError(code)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("seed", "verify-readonly"))
    parser.add_argument("--media-sha256")
    parser.add_argument("--media-bytes", type=int)
    parser.add_argument("--expected-user")
    args = parser.parse_args()
    if (
        os.environ.get("ESTAKADA_R7C_SYNTHETIC_FIXTURE") != "1"
    ):
        fail()

    import django

    django.setup()

    from django.contrib.auth import get_user_model
    from django.db import connection, transaction
    from django.utils import timezone
    from modules.media.models import (
        Asset,
        AssetFile,
        AssetPurpose,
        AssetState,
        AssetUsage,
        FileKind,
        MediaType,
        UsageScope,
    )
    from modules.pages.content import canonical_payload_hash
    from modules.pages.models import (
        Page,
        PageContent,
        PageKind,
        Route,
        RouteMode,
        SiteSettings,
    )

    navigation_fixtures = (
        (uuid.UUID("60000000-0000-4000-8000-000000000001"), uuid.UUID("70000000-0000-4000-8000-000000000001"), "Акции", PageKind.ACTIONS, "/actions"),
        (uuid.UUID("60000000-0000-4000-8000-000000000002"), uuid.UUID("70000000-0000-4000-8000-000000000002"), "Галерея работ", PageKind.GALLERY_CATALOG, "/gallery-of-works/"),
        (uuid.UUID("60000000-0000-4000-8000-000000000003"), uuid.UUID("70000000-0000-4000-8000-000000000003"), "Отзывы", PageKind.REVIEWS, "/reviews"),
        (uuid.UUID("60000000-0000-4000-8000-000000000004"), uuid.UUID("70000000-0000-4000-8000-000000000004"), "Статьи", PageKind.ARTICLES_CATALOG, "/articles/"),
        (uuid.UUID("60000000-0000-4000-8000-000000000005"), uuid.UUID("70000000-0000-4000-8000-000000000005"), "Контакты", PageKind.CONTACTS, "/contacts"),
    )

    if args.mode == "verify-readonly":
        if type(args.expected_user) is not str or re.fullmatch(r"r7c_(old|new)_runtime", args.expected_user) is None:
            fail()
        with connection.cursor() as cursor:
            cursor.execute("SHOW transaction_read_only")
            read_only = cursor.fetchone()[0]
            cursor.execute("SELECT current_user")
            current_user = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM django_migrations")
            migrations = int(cursor.fetchone()[0])
        if read_only != "on" or current_user != args.expected_user or migrations < 1:
            fail("R7C_SYNTHETIC_READONLY_UNPROVEN")
        print(json.dumps({"schema": "estakada.r7c-synthetic-readonly-v1", "result": "PASS", "user": current_user}, sort_keys=True, separators=(",", ":")))
        return

    if re.fullmatch(r"[0-9a-f]{64}", args.media_sha256 or "") is None or args.media_bytes is None or args.media_bytes < 1:
        fail()

    storage_key = f"img/{ASSET_ID}/main.svg"
    with transaction.atomic():
        if Asset.objects.exists() or AssetFile.objects.exists() or SiteSettings.objects.exists() or Page.objects.exists():
            fail("R7C_SYNTHETIC_FIXTURE_NOT_EMPTY")
        owner = get_user_model().objects.create_superuser(username="nesadmin", password=None)
        asset = Asset.objects.create(
            id=ASSET_ID,
            purpose=AssetPurpose.SITE_ASSET,
            state=AssetState.READY,
            source_sha256=args.media_sha256,
        )
        AssetFile.objects.create(
            id=FILE_ID,
            asset=asset,
            kind=FileKind.MAIN,
            storage_key=storage_key,
            sha256=args.media_sha256,
            byte_size=args.media_bytes,
            mime_type=MediaType.SVG,
        )
        settings = SiteSettings.objects.create(
            id=SETTINGS_ID,
            organization_name="Synthetic Estakada",
            phone_display="+7 000 000-00-00",
            phone_e164="+70000000000",
            address="Synthetic fixture",
            opening_hours="Always closed",
            contact_email="synthetic@example.test",
            map_url="https://example.test/synthetic",
            logo_asset=asset,
        )
        AssetUsage.objects.create(
            asset=asset,
            scope=UsageScope.SITE_SETTINGS,
            target_uuid=settings.id,
            slot="logo",
            position=0,
        )
        payload = {
            "schema": "estakada.page-content",
            "schema_version": 1,
            "kind": PageKind.LEGACY_EMPTY_MAIN,
            "fields": {
                "seo": {"title": "Synthetic canary", "description": "Synthetic", "allow_index": False},
                "heading": {"h1": "Synthetic canary"},
            },
        }
        page = Page.objects.create(id=PAGE_ID, name="Synthetic canary", kind=PageKind.LEGACY_EMPTY_MAIN, position=1, is_published=True)
        Route.objects.create(id=ROUTE_ID, page=page, target="/synthetic-canary/", mode=RouteMode.PRIMARY, outcome=PageKind.LEGACY_EMPTY_MAIN)
        PageContent.objects.create(page=page, current_payload=payload, current_hash=canonical_payload_hash(payload), current_author=owner, current_created_at=timezone.now())
        for position, (page_id, route_id, name, kind, target) in enumerate(navigation_fixtures, start=2):
            navigation_page = Page.objects.create(id=page_id, name=name, kind=kind, position=position, is_published=True)
            Route.objects.create(id=route_id, page=navigation_page, target=target, mode=RouteMode.PRIMARY, outcome=kind)
    result = {
        "schema": "estakada.r7c-synthetic-seed-v1",
        "assetId": str(ASSET_ID),
        "storageKey": storage_key,
        "sha256": args.media_sha256,
        "bytes": args.media_bytes,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
