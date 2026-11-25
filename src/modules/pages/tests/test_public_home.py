from __future__ import annotations

import copy
import uuid
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import NoReverseMatch, resolve, reverse
from django.utils import timezone

from modules.audit.models import AuditEvent
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
from modules.service_requests.models import ServiceRequest

from ..content import canonical_payload_hash
from ..models import Page, PageContent, PageKind, Route, RouteMode
from .test_public_http import PublicHttpFixture


def _id() -> str:
    return str(uuid.uuid4())


class PublicHomeTests(PublicHttpFixture, TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.make_base()
        self.page, self.payload = self._make_home()

    def _asset(self, *, gallery: bool = False) -> Asset:
        asset = Asset.objects.create(
            purpose=AssetPurpose.GALLERY_ORIGINAL if gallery else AssetPurpose.CONTENT,
            state=AssetState.READY,
            source_sha256="c" * 64,
        )
        kind = FileKind.LEGACY_PUBLIC if gallery else FileKind.MAIN
        segment = "legacy-public" if gallery else "main"
        AssetFile.objects.create(
            asset=asset,
            kind=kind,
            storage_key=f"img/{asset.id}/{segment}.webp",
            sha256="d" * 64,
            byte_size=1024,
            mime_type=MediaType.WEBP,
            width=800,
            height=600,
        )
        return asset

    def _make_home(self) -> tuple[Page, dict]:
        hero = self._asset()
        service_assets = [self._asset() for _ in range(8)]
        step_assets = [self._asset() for _ in range(5)]
        photo_strip = self._asset()
        work_assets = [self._asset(gallery=True) for _ in range(6)]
        media = {
            "hero": str(hero.id),
            "service_cards": [str(asset.id) for asset in service_assets],
            "process": [str(asset.id) for asset in step_assets],
            "works": [str(photo_strip.id), *[str(asset.id) for asset in work_assets]],
            "brand_logos": [],
        }
        profile = {
            "schema": "estakada.home-profile",
            "schema_version": 1,
            "hero": {"alt": "Главный экран", "asset_id": str(hero.id)},
            "advantages": [f"Преимущество {index}" for index in range(1, 9)],
            "comparisons": [
                {
                    "heading": f"Сравнение {index}",
                    "bullets": [f"Пункт {index}.{bullet}" for bullet in range(1, 5)],
                    "result_mark": "✓",
                    "result_text": f"Результат {index}",
                }
                for index in range(1, 4)
            ],
            "steps": [
                {"alt": f"Шаг {index}", "asset_id": str(asset.id)}
                for index, asset in enumerate(step_assets, 1)
            ],
            "services": [
                {
                    "id": _id(),
                    "label": f"Услуга {index}",
                    "caption": f"Описание {index}",
                    "url": f"/services/service-{index}/",
                    "alt": f"Иллюстрация услуги {index}",
                    "fallback_visible": True,
                    "source_page_id": None,
                    "asset_id": str(asset.id),
                }
                for index, asset in enumerate(service_assets, 1)
            ],
            "prices": [
                {
                    "id": _id(),
                    "key": f"group-{index}",
                    "url": f"/services/group-{index}/",
                    "label": f"Группа {index}",
                    "source_page_id": None,
                    "rows": [
                        {
                            "id": _id(),
                            "url": f"/services/group-{index}/work/",
                            "label": f"Работа {index}",
                            "price_text": f"от {index} 000 ₽",
                            "fallback_visible": True,
                            "source_page_id": None,
                            "source_row_id": None,
                        }
                    ],
                }
                for index in range(1, 7)
            ],
            "photo_strip": {"alt": "Автотехцентр", "asset_id": str(photo_strip.id)},
            "works": [
                {
                    "id": _id(),
                    "source_page_id": None,
                    "url": f"/gallery-of-works/work-{index}",
                    "label": f"Работа {index}",
                    "photo_count_text": f"{index + 1} фото",
                    "asset_id": str(asset.id),
                    "alt": f"Выполненная работа {index}",
                    "fallback_visible": True,
                }
                for index, asset in enumerate(work_assets, 1)
            ],
            "reviews": {
                "heading": "ОТЗЫВЫ",
                "url": "/reviews",
                "label": "ОТКРЫТЬ ВСЕ ВИДЕО-ОТЗЫВЫ",
            },
        }
        fields = {
            "seo": {"title": "Главная", "description": "Описание главной", "allow_index": True},
            "heading": {"h1": "АВТОТЕХЦЕНТР ЭСТАКАДА"},
            "lead": "<p>Ремонт и обслуживание автомобилей.</p>",
            "service_refs": [],
            "process_steps": [
                {"title": f"Этап {index}", "body": f"Описание этапа {index}"}
                for index in range(1, 6)
            ],
            "about": "",
            "brand_refs": [],
            "review_refs": [],
            "contact_text": "",
            "media": media,
            "home_profile": profile,
        }
        payload = {
            "schema": "estakada.page-content",
            "schema_version": 1,
            "kind": PageKind.HOME,
            "fields": fields,
        }
        self.position += 1
        page = Page.objects.create(
            name="Главная",
            kind=PageKind.HOME,
            position=self.position,
            is_published=True,
        )
        Route.objects.create(page=page, target="/", mode=RouteMode.PRIMARY, outcome=PageKind.HOME)
        PageContent.objects.create(
            page=page,
            current_payload=payload,
            current_hash=canonical_payload_hash(payload),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )
        for slot, values in media.items():
            asset_ids = [values] if isinstance(values, str) else values
            for position, asset_id in enumerate(asset_ids):
                AssetUsage.objects.create(
                    asset_id=asset_id,
                    scope=UsageScope.PAGE_CURRENT,
                    target_uuid=page.id,
                    slot=slot,
                    position=position,
                )
        return page, payload

    def _save_payload(self, payload: dict) -> None:
        content = PageContent.objects.get(page=self.page)
        content.current_payload = payload
        content.current_hash = canonical_payload_hash(payload)
        content.generation += 1
        content.save(update_fields=("current_payload", "current_hash", "generation"))

    def test_get_and_head_render_exact_local_v4_core(self) -> None:
        response = self.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for marker in (
            "АВТОТЕХЦЕНТР",
            "ЭСТАКАДА",
            "КАК МЫ <mark>РАБОТАЕМ</mark>",
            'id="es-services"',
            "РЕШАЕМ ЗАДАЧИ",
            "ЛЮБОЙ СЛОЖНОСТИ",
            "УСЛУГИ И <mark>ЦЕНЫ</mark>",
            "НАШИ <mark>РАБОТЫ</mark>",
            "ОТЗЫВЫ",
            "public_home.css",
        ):
            self.assertIn(marker, html)
        self.assertEqual(html.count("/legacy-public.webp"), 6)
        self.assertEqual(html.count("/main.webp"), 15)
        for forbidden in (
            "<form",
            "<input",
            "<textarea",
            "data-service-request-form",
            "request/submit",
            "<iframe",
            'src="http://',
            'src="https://',
            "fetch(",
        ):
            self.assertNotIn(forbidden, html.lower())
        head = self.client.head("/", HTTP_X_ESTAKADA_REQUEST_TARGET="/")
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b"")
        self.assertEqual(head["Cache-Control"], response["Cache-Control"])

    def test_default_off_post_has_no_endpoint_side_effect_or_network(self) -> None:
        with self.assertRaises(NoReverseMatch):
            reverse("service-request-submit")
        self.assertEqual(resolve("/request/submit/").url_name, "public-page")
        request_count = ServiceRequest.objects.count()
        audit_count = AuditEvent.objects.count()
        with patch("urllib.request.urlopen") as urlopen:
            response = self.client.post(
                "/request/submit/",
                {"name": "Иван", "phone": "+79991234567"},
                HTTP_X_ESTAKADA_REQUEST_TARGET="/request/submit/",
            )
        self.assertEqual((response.status_code, response.content), (404, b"NOT_FOUND"))
        self.assertEqual(ServiceRequest.objects.count(), request_count)
        self.assertEqual(AuditEvent.objects.count(), audit_count)
        urlopen.assert_not_called()

    def test_bound_price_is_dynamic_and_hidden_source_disappears(self) -> None:
        source_row = _id()
        self.position += 1
        source = Page.objects.create(
            name="Источник цены",
            kind=PageKind.SERVICE_DETAIL,
            position=self.position,
            is_published=True,
        )
        Route.objects.create(
            page=source,
            target="/services/source/",
            mode=RouteMode.PRIMARY,
            outcome=PageKind.SERVICE_DETAIL,
        )
        column = _id()
        source_payload = {
            "schema": "estakada.page-content",
            "schema_version": 1,
            "kind": PageKind.SERVICE_DETAIL,
            "fields": {
                "seo": {"title": "Источник", "description": "", "allow_index": True},
                "heading": {"h1": "Источник"},
                "intro": "",
                "body": "",
                "price_rows": {
                    "columns": [{"id": column, "label": "Цена"}],
                    "rows": [{
                        "id": source_row,
                        "label": "Связанная работа",
                        "cells": [{"column_id": column, "kind": "amount", "amount": "12345.50", "from": True}],
                    }],
                },
                "media": {"hero": None, "body": [], "works": []},
            },
        }
        PageContent.objects.create(
            page=source,
            current_payload=source_payload,
            current_hash=canonical_payload_hash(source_payload),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )
        payload = copy.deepcopy(self.payload)
        row = payload["fields"]["home_profile"]["prices"][0]["rows"][0]
        row["source_page_id"] = str(source.id)
        row["source_row_id"] = source_row
        row["price_text"] = "fallback"
        self._save_payload(payload)
        html = self.get("/").content.decode()
        self.assertIn("от 12 345.5 ₽", html)
        self.assertNotIn("fallback", html)
        source.is_published = False
        source.save(update_fields=("is_published",))
        html = self.get("/").content.decode()
        self.assertNotIn("/services/group-1/work/", html)
        self.assertNotIn("<summary>Группа 1</summary>", html)

    def test_media_usage_or_profile_drift_is_fail_closed(self) -> None:
        usage = AssetUsage.objects.filter(
            target_uuid=self.page.id,
            scope=UsageScope.PAGE_CURRENT,
        ).first()
        assert usage is not None
        usage_values = (usage.asset_id, usage.slot, usage.position)
        usage.delete()
        response = self.get("/")
        self.assertEqual((response.status_code, response.content), (503, b"UNAVAILABLE"))
        AssetUsage.objects.create(
            asset_id=usage_values[0],
            scope=UsageScope.PAGE_CURRENT,
            target_uuid=self.page.id,
            slot=usage_values[1],
            position=usage_values[2],
        )

        payload = copy.deepcopy(self.payload)
        payload["fields"]["home_profile"]["hero"]["asset_id"] = _id()
        self._save_payload(payload)
        response = self.get("/")
        self.assertEqual((response.status_code, response.content), (503, b"UNAVAILABLE"))
