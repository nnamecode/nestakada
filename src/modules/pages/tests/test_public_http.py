from __future__ import annotations

import inspect
import re
import uuid
from html import escape
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from modules.gallery.models import GalleryAlbum, GalleryPhoto
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

from ..content import canonical_payload_hash
from ..models import Page, PageContent, PageKind, Route, RouteMode, SiteSettings


User = get_user_model()


def _payload(kind: str, *, allow_index: bool = True) -> dict:
    fields: dict[str, object] = {
        "seo": {"title": f"SEO {kind}", "description": "Описание", "allow_index": allow_index},
        "heading": {"h1": f"H1 {kind}"},
    }
    if kind == PageKind.LEGACY_PARTNER_LINKS:
        fields["links"] = [{"label": "Партнёр <1>", "https_url": "https://example.test/path"}]
    elif kind in {PageKind.LEGACY_DIRECTOR_MESSAGE, PageKind.LEGACY_NEWS_ARTICLE}:
        fields.update({
            "intro": "<p>Вступление</p>",
            "body": "<p>Текст <strong>безопасен</strong></p>",
            "media": {"hero": None},
        })
    elif kind == PageKind.LEGACY_NEWS_CATALOG:
        fields["intro"] = "<p>Новости автотехцентра</p>"
    elif kind in {PageKind.LEGACY_UNDER_CONSTRUCTION, PageKind.LEGACY_CAMERA_SCHEDULE_TEXT}:
        fields.update({"intro": "<p>Вступление</p>", "body": "<p>Текст <strong>безопасен</strong></p>"})
    elif kind == PageKind.SERVICES_MASTER_CATALOG:
        fields["intro"] = "<p>Все услуги автотехцентра</p>"
    elif kind == PageKind.SERVICE_CATALOG:
        fields.update({"intro": "<p>Услуги раздела</p>", "media": {"hero": None}})
    elif kind == PageKind.SERVICE_SECTION_OVERVIEW:
        fields.update({
            "intro": "<p>Вступление раздела</p>",
            "body": "<p>Описание раздела</p>",
            "media": {"hero": None, "works": []},
        })
    elif kind == PageKind.SERVICE_DETAIL:
        fields.update({
            "intro": "<p>Вступление услуги</p>",
            "body": "<p>Описание услуги</p>",
            "price_rows": {"columns": [], "rows": []},
            "media": {"hero": None, "body": [], "works": []},
        })
    elif kind == PageKind.ARTICLES_CATALOG:
        fields["intro"] = "<p>Полезные статьи об обслуживании автомобиля</p>"
    elif kind == PageKind.ARTICLE:
        fields.update({
            "intro": "<p>Краткое вступление статьи</p>",
            "body": "<p>Основной текст статьи</p>",
            "media": {"hero": None, "body": [], "works": []},
        })
    elif kind == PageKind.ACTIONS:
        fields.update({
            "intro": "<p>Действующие акции автотехцентра</p>",
            "actions": [],
            "media": {"banner": []},
        })
    elif kind == PageKind.REVIEWS:
        fields.update({
            "intro": "<p>Видео-отзывы клиентов автотехцентра</p>",
            "reviews": [],
            "media": {"thumbnail": []},
        })
    elif kind == PageKind.CONTACTS:
        fields.update({
            "intro": "<p>Свяжитесь с автотехцентром «Эстакада» удобным способом.</p>",
            "body": "<p>Мы находимся рядом с Ленинским проспектом.</p>",
            "media": {"gallery": []},
        })
    elif kind in {PageKind.GALLERY_CATALOG, PageKind.GALLERY_ALBUM}:
        fields["intro"] = "<p>Работы автотехцентра</p>"
    return {"schema": "estakada.page-content", "schema_version": 1, "kind": kind, "fields": fields}


class PublicHttpFixture:
    def make_base(self) -> None:
        self.owner = User.objects.create_superuser(username="nesadmin", password=None)
        self.logo = Asset.objects.create(
            purpose=AssetPurpose.SITE_ASSET,
            state=AssetState.READY,
            source_sha256="a" * 64,
        )
        self.logo_file = AssetFile.objects.create(
            asset=self.logo,
            kind=FileKind.MAIN,
            storage_key=f"img/{self.logo.id}/main.jpeg",
            sha256="b" * 64,
            byte_size=30190,
            mime_type=MediaType.JPEG,
            width=240,
            height=80,
        )
        self.settings = SiteSettings.objects.create(
            organization_name="Эстакада",
            phone_display="+7 (499) 110-25-52",
            phone_e164="+74991102552",
            address="Москва, Проспект 60-летия Октября, 15Б",
            opening_hours="Ежедневно с 9:00 до 21:00",
            contact_email="private@example.test",
            map_url="https://example.test/map",
            logo_asset=self.logo,
        )
        AssetUsage.objects.create(
            asset=self.logo,
            scope=UsageScope.SITE_SETTINGS,
            target_uuid=self.settings.id,
            slot="logo",
            position=0,
        )
        menu = (
            ("Акции", "/actions", PageKind.ACTIONS),
            ("Галерея работ", "/gallery-of-works/", PageKind.GALLERY_CATALOG),
            ("Отзывы", "/reviews", PageKind.REVIEWS),
            ("Статьи", "/articles/", PageKind.ARTICLES_CATALOG),
            ("Контакты", "/contacts", PageKind.CONTACTS),
        )
        for position, (name, target, kind) in enumerate(menu, start=1):
            page = Page.objects.create(name=name, kind=kind, position=position, is_published=True)
            Route.objects.create(page=page, target=target, mode=RouteMode.PRIMARY, outcome=kind)
        self.position = len(menu)

    def make_page(
        self,
        kind: str = PageKind.LEGACY_EMPTY_MAIN,
        *,
        target: str | None = None,
        published: bool = True,
        allow_index: bool = True,
    ) -> Page:
        self.position += 1
        target = target or f"/plain-{self.position}/"
        page = Page.objects.create(
            name=f"Plain {self.position}", kind=kind, position=self.position, is_published=published
        )
        Route.objects.create(page=page, target=target, mode=RouteMode.PRIMARY, outcome=kind)
        payload = _payload(kind, allow_index=allow_index)
        PageContent.objects.create(
            page=page,
            current_payload=payload,
            current_hash=canonical_payload_hash(payload),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )
        return page

    def get(self, target: str, **extra):
        return self.client.get(target, HTTP_X_ESTAKADA_REQUEST_TARGET=target, **extra)


class PublicHttpTests(PublicHttpFixture, TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.make_base()

    def test_transport_envelope_is_400_before_route_authority(self) -> None:
        self.assertEqual(self.client.get("/missing-header/").status_code, 400)
        cases = ("/bad%2/", "/other/", "/" + "x" * 2048)
        for header in cases:
            with self.subTest(header=header):
                response = self.client.get("/plain/", HTTP_X_ESTAKADA_REQUEST_TARGET=header)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response["Cache-Control"], "no-store")
        method = self.client.post("/plain/", HTTP_X_ESTAKADA_REQUEST_TARGET="/plain/")
        self.assertEqual(method.status_code, 405)
        self.assertEqual(method["Allow"], "GET, HEAD")

    def test_actions_render_exact_two_banners_copy_and_fail_closed(self) -> None:
        page = Page.objects.get(kind=PageKind.ACTIONS)
        payload = _payload(PageKind.ACTIONS)
        payload["fields"]["heading"]["h1"] = "Акции"
        payload["fields"]["actions"] = [
            {
                "title": "Скидка 10% за первое посещение!",
                "body": "<p>Качество обслуживания как у официального дилера, но цены значительно ниже!</p>",
                "internal_url": "/actions",
            },
            {
                "title": "Каждое воскресенье скидка на ремонт 7%",
                "body": "<p>Не проспи свою выгоду!</p>",
                "internal_url": "/actions",
            },
        ]
        banners = []
        for position in range(2):
            asset = Asset.objects.create(
                purpose=AssetPurpose.CONTENT,
                state=AssetState.READY,
                source_sha256=f"{position + 101:064x}",
            )
            AssetFile.objects.create(
                asset=asset,
                kind=FileKind.MAIN,
                storage_key=f"img/{asset.id}/main.webp",
                sha256=f"{position + 201:064x}",
                byte_size=4096 + position,
                mime_type=MediaType.WEBP,
                width=1600,
                height=1000,
            )
            AssetUsage.objects.create(
                asset=asset,
                scope=UsageScope.PAGE_CURRENT,
                target_uuid=page.id,
                slot="banner",
                position=position,
            )
            banners.append(asset)
        payload["fields"]["media"]["banner"] = [str(asset.id) for asset in banners]
        PageContent.objects.create(
            page=page,
            current_payload=payload,
            current_hash=canonical_payload_hash(payload),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )

        response = self.get("/actions")
        head = self.client.head("/actions", HTTP_X_ESTAKADA_REQUEST_TARGET="/actions")
        self.assertEqual((response.status_code, head.status_code), (200, 200))
        self.assertEqual(head.content, b"")
        html = response.content.decode("utf-8")
        self.assertIn("public_actions.css", html)
        self.assertIn('class="es-actions-content"', html)
        self.assertNotIn('class="es-actions"', html)
        self.assertEqual(html.count('class="es-promo-card"'), 2)
        self.assertEqual(html.count('class="es-promo-ribbon"'), 2)
        self.assertIn("<mark>Скидка 10%</mark> за первое посещение!", html)
        self.assertIn("Каждое воскресенье <mark>скидка на ремонт 7%</mark>", html)
        self.assertIn("Не проспи свою выгоду!", html)
        for asset in banners:
            self.assertIn(f"/media/img/{asset.id}/main.webp", html)
        self.assertNotIn("sessionid", response.cookies)

        AssetUsage.objects.filter(asset=banners[0], scope=UsageScope.PAGE_CURRENT).delete()
        self.assertEqual(self.get("/actions").status_code, 503)

    def test_reviews_render_exact_ten_local_thumbnails_without_embeds(self) -> None:
        page = Page.objects.get(kind=PageKind.REVIEWS)
        payload = _payload(PageKind.REVIEWS)
        payload["fields"]["heading"]["h1"] = "Отзывы"
        video_ids = (
            "4TrRalaNkT8", "aFwP0Ahry3A", "Yrd3pRcFDwI", "LRaZ46Jilic",
            "jOmJEtGa1Pc", "0QN2bPlOvgU", "pmucl0ww68U", "nAyo9rIIXfA",
            "yrDWcfF5fyY", "jB_lPvIgk2Y",
        )
        thumbnails = []
        reviews = []
        for position, video_id in enumerate(video_ids):
            asset = Asset.objects.create(
                purpose=AssetPurpose.CONTENT,
                state=AssetState.READY,
                source_sha256=f"{position + 301:064x}",
            )
            AssetFile.objects.create(
                asset=asset,
                kind=FileKind.MAIN,
                storage_key=f"img/{asset.id}/main.webp",
                sha256=f"{position + 401:064x}",
                byte_size=4096 + position,
                mime_type=MediaType.WEBP,
                width=1280,
                height=720,
            )
            AssetUsage.objects.create(
                asset=asset,
                scope=UsageScope.PAGE_CURRENT,
                target_uuid=page.id,
                slot="thumbnail",
                position=position,
            )
            title = f"Видео-отзыв {position + 1:02d}"
            reviews.append({
                "title": title,
                "https_url": f"https://www.youtube.com/watch?v={video_id}",
                "caption": "",
            })
            thumbnails.append(asset)
        payload["fields"]["reviews"] = reviews
        payload["fields"]["media"]["thumbnail"] = [str(asset.id) for asset in thumbnails]
        PageContent.objects.create(
            page=page,
            current_payload=payload,
            current_hash=canonical_payload_hash(payload),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )

        response = self.get("/reviews")
        head = self.client.head("/reviews", HTTP_X_ESTAKADA_REQUEST_TARGET="/reviews")
        self.assertEqual((response.status_code, head.status_code), (200, 200))
        self.assertEqual(head.content, b"")
        html = response.content.decode("utf-8")
        self.assertIn("public_reviews.css", html)
        self.assertEqual(html.count('class="es-review-video-card"'), 10)
        self.assertNotIn("<iframe", html)
        self.assertNotIn("youtube-nocookie.com", html)
        self.assertNotIn('src="https://', html)
        self.assertNotIn("i.ytimg.com", html)
        markers = [f"watch?v={video_id}" for video_id in video_ids]
        self.assertTrue(all(marker in html for marker in markers))
        self.assertEqual(
            [html.index(marker) for marker in markers],
            sorted(html.index(marker) for marker in markers),
        )
        for asset in thumbnails:
            self.assertIn(f"/media/img/{asset.id}/main.webp", html)
        self.assertNotIn("sessionid", response.cookies)

        AssetUsage.objects.filter(asset=thumbnails[0], scope=UsageScope.PAGE_CURRENT).delete()
        self.assertEqual(self.get("/reviews").status_code, 503)

    def test_contacts_render_exact_five_local_images_and_confirmed_facts(self) -> None:
        page = Page.objects.get(kind=PageKind.CONTACTS)
        payload = _payload(PageKind.CONTACTS)
        payload["fields"]["heading"]["h1"] = "Контакты"
        gallery = []
        for position in range(5):
            asset = Asset.objects.create(
                purpose=AssetPurpose.CONTENT,
                state=AssetState.READY,
                source_sha256=f"{position + 501:064x}",
            )
            AssetFile.objects.create(
                asset=asset,
                kind=FileKind.MAIN,
                storage_key=f"img/{asset.id}/main.webp",
                sha256=f"{position + 601:064x}",
                byte_size=8192 + position,
                mime_type=MediaType.WEBP,
                width=1600,
                height=1000,
            )
            AssetUsage.objects.create(
                asset=asset,
                scope=UsageScope.PAGE_CURRENT,
                target_uuid=page.id,
                slot="gallery",
                position=position,
            )
            gallery.append(asset)
        payload["fields"]["media"]["gallery"] = [str(asset.id) for asset in gallery]
        PageContent.objects.create(
            page=page,
            current_payload=payload,
            current_hash=canonical_payload_hash(payload),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )

        response = self.get("/contacts")
        head = self.client.head("/contacts", HTTP_X_ESTAKADA_REQUEST_TARGET="/contacts")
        self.assertEqual((response.status_code, head.status_code), (200, 200))
        self.assertEqual(head.content, b"")
        html = response.content.decode("utf-8")
        self.assertIn("public_contacts.css", html)
        self.assertIn('class="es-contacts-content"', html)
        self.assertIn('href="tel:+74991102552"', html)
        self.assertIn('+7 (499) 110-25-52', html)
        self.assertIn('href="mailto:private@example.test"', html)
        self.assertIn('href="https://example.test/map"', html)
        self.assertIn("Москва, Проспект 60-летия Октября, 15Б", html)
        self.assertIn("Ежедневно с 9:00 до 21:00", html)
        self.assertEqual(html.count('class="es-contact-photo"'), 5)
        for asset in gallery:
            self.assertIn(f"/media/img/{asset.id}/main.webp", html)
        self.assertNotIn("<form", html)
        self.assertNotIn("<input", html)
        self.assertNotIn("<textarea", html)
        self.assertNotIn("<iframe", html)
        self.assertNotIn("api-maps.yandex", html)
        self.assertNotIn('src="https://', html)
        self.assertNotIn("sessionid", response.cookies)

        AssetUsage.objects.filter(asset=gallery[0], scope=UsageScope.PAGE_CURRENT).delete()
        self.assertEqual(self.get("/contacts").status_code, 503)

    def test_exact_raw_query_percent_spelling_is_preserved(self) -> None:
        target = "/plain/?x=%2f&b=2"
        self.make_page(target=target)
        response = self.get(target)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<link rel="canonical" href="/plain/?x=%2f&amp;b=2">', html=False)

    def test_four_supported_kinds_get_and_head_render_shell(self) -> None:
        for kind in (
            PageKind.LEGACY_PARTNER_LINKS,
            PageKind.LEGACY_EMPTY_MAIN,
            PageKind.LEGACY_UNDER_CONSTRUCTION,
            PageKind.LEGACY_CAMERA_SCHEDULE_TEXT,
        ):
            with self.subTest(kind=kind):
                page = self.make_page(kind)
                target = Route.objects.get(page=page, mode=RouteMode.PRIMARY).target
                response = self.get(target)
                head = self.client.head(target, HTTP_X_ESTAKADA_REQUEST_TARGET=target)
                self.assertEqual((response.status_code, head.status_code), (200, 200))
                self.assertEqual(head.content, b"")
                self.assertContains(response, "Эстакада")

    def test_remaining_legacy_plain_exact_ten_render_tree_copy_and_links(self) -> None:
        partner = self.make_page(PageKind.LEGACY_PARTNER_LINKS, target="/partners")
        partner.name = "Партнёры"
        partner.save(update_fields=("name",))
        partner_payload = _payload(PageKind.LEGACY_PARTNER_LINKS)
        partner_payload["fields"]["heading"]["h1"] = "Партнёры"
        partner_urls = (
            "http://www.blackstone-russia.ru/",
            "http://automarkirovka.ru/",
            "http://www.argoauto-center.ru/",
            "http://www.ton-service.ru/",
            "http://www.rgs.ru/",
            "http://www.motortehn.ru/",
        )
        partner_payload["fields"]["links"] = [
            {"label": url.removeprefix("http://").rstrip("/"), "https_url": url}
            for url in partner_urls
        ]
        partner_content = PageContent.objects.get(page=partner)
        partner_content.current_payload = partner_payload
        partner_content.current_hash = canonical_payload_hash(partner_payload)
        partner_content.save(update_fields=("current_payload", "current_hash"))

        director = self.make_page(PageKind.LEGACY_DIRECTOR_MESSAGE, target="/direct-contact")
        director.name = "Прямая связь с директором"
        director.save(update_fields=("name",))
        director_content = PageContent.objects.get(page=director)
        director_payload = _payload(PageKind.LEGACY_DIRECTOR_MESSAGE)
        director_payload["fields"]["heading"]["h1"] = "Прямая связь с директором"
        director_payload["fields"]["intro"] = '<p>Уважаемым клиентам АТЦ "ЭСТАКАДА"</p>'
        director_payload["fields"]["body"] = (
            "<p>Мне очень важно знать Ваше мнение.</p>"
            "<p>Мой прямой номер телефона: +7 (499) 110-25-52</p>"
        )
        director_content.current_payload = director_payload
        director_content.current_hash = canonical_payload_hash(director_payload)
        director_content.save(update_fields=("current_payload", "current_hash"))

        empty_targets = ("/nash-servisnyij-czentr", "/about")
        empty_pages = [
            self.make_page(PageKind.LEGACY_EMPTY_MAIN, target=target)
            for target in empty_targets
        ]

        news = self.make_page(PageKind.LEGACY_NEWS_CATALOG, target="/news/")
        news.name = "Новости"
        news.save(update_fields=("name",))
        article_facts = (
            (
                "/news/priobretenie-podemnika-do-10-tonn-dlya-remonta-malotonnazhnyix-avtomobilej",
                "Приобретение подъемника до 10 тонн для ремонта малотоннажных автомобилей",
                "АвтоТехЦентр «Эстакада» приобрел четырехстоечный подъемник грузоподъемностью до 10 тонн.",
            ),
            (
                "/news/atcz-estakada-podklyuchila-mnogokanalnyij-telefon",
                'АТЦ "ЭСТАКАДА" подключила многоканальный телефон',
                "Установка многоканальной телефонного позволяет нам обеспечить качественную связь.",
            ),
            (
                "/news/okazanie-dopolnitelnyix-uslug",
                "Оказание дополнительных услуг",
                (
                    '<ul><li><a href="https://www.estakada-auto.ru/service/ustanovka-avtozvuka">Установка автозвука</a></li>'
                    '<li><a href="https://www.estakada-auto.ru/service/ustanovka-protivougonnyh-sistem">Установка противоугонных систем</a></li>'
                    '<li><a href="https://www.estakada-auto.ru/service/ustanovka-dop-osveshcheniya">Установка доп. освещения</a></li>'
                    '<li><a href="https://www.estakada-auto.ru/service/shumoizolyaciya">Установка доп. шумоизаляции</a></li></ul>'
                ),
            ),
        )
        news_content = PageContent.objects.get(page=news)
        news_payload = _payload(PageKind.LEGACY_NEWS_CATALOG)
        news_payload["fields"]["heading"]["h1"] = "Новости"
        news_payload["fields"]["intro"] = "<ul>" + "".join(
            f'<li><a href="{target}">{title}</a></li>'
            for target, title, _ in article_facts
        ) + "</ul>"
        news_content.current_payload = news_payload
        news_content.current_hash = canonical_payload_hash(news_payload)
        news_content.save(update_fields=("current_payload", "current_hash"))

        articles = []
        for position, (target, title, body) in enumerate(article_facts):
            article = self.make_page(PageKind.LEGACY_NEWS_ARTICLE, target=target)
            article.name = title
            article.parent = news
            article.position = position
            article.save(update_fields=("name", "parent", "position"))
            content = PageContent.objects.get(page=article)
            payload = _payload(PageKind.LEGACY_NEWS_ARTICLE)
            payload["fields"]["heading"]["h1"] = title
            payload["fields"]["intro"] = ""
            payload["fields"]["body"] = body if body.startswith("<") else f"<p>{body}</p>"
            content.current_payload = payload
            content.current_hash = canonical_payload_hash(payload)
            content.save(update_fields=("current_payload", "current_hash"))
            articles.append(article)

        guarantees = self.make_page(PageKind.LEGACY_UNDER_CONSTRUCTION, target="/garantii")
        guarantees.name = "Гарантии"
        guarantees.save(update_fields=("name",))
        guarantees_content = PageContent.objects.get(page=guarantees)
        guarantees_payload = _payload(PageKind.LEGACY_UNDER_CONSTRUCTION)
        guarantees_payload["fields"]["heading"]["h1"] = "Гарантии"
        guarantees_payload["fields"]["intro"] = ""
        guarantees_payload["fields"]["body"] = (
            "<p>Приносим свои извинения, данный раздел сайта находится в разработке!</p>"
        )
        guarantees_content.current_payload = guarantees_payload
        guarantees_content.current_hash = canonical_payload_hash(guarantees_payload)
        guarantees_content.save(update_fields=("current_payload", "current_hash"))

        camera = self.make_page(PageKind.LEGACY_CAMERA_SCHEDULE_TEXT, target="/cctv")
        camera.name = "Web-камеры техцентра"
        camera.save(update_fields=("name",))
        camera_content = PageContent.objects.get(page=camera)
        camera_payload = _payload(PageKind.LEGACY_CAMERA_SCHEDULE_TEXT)
        camera_payload["fields"]["heading"]["h1"] = "Web-камеры техцентра"
        camera_payload["fields"]["intro"] = ""
        camera_payload["fields"]["body"] = (
            "<p>Трансляция ведется в рабочее время с 09-00 до 21-00 мск</p>"
        )
        camera_content.current_payload = camera_payload
        camera_content.current_hash = canonical_payload_hash(camera_payload)
        camera_content.save(update_fields=("current_payload", "current_hash"))

        exact_pages = [partner, director, *empty_pages, news, *articles, guarantees, camera]
        self.assertEqual(len(exact_pages), 10)
        html_by_target = {}
        for page in exact_pages:
            target = Route.objects.get(page=page, mode=RouteMode.PRIMARY).target
            response = self.get(target)
            head = self.client.head(target, HTTP_X_ESTAKADA_REQUEST_TARGET=target)
            self.assertEqual((response.status_code, head.status_code), (200, 200))
            self.assertEqual(head.content, b"")
            html_by_target[target] = response.content.decode("utf-8")
            self.assertIn("public_legacy.css", html_by_target[target])
            self.assertNotIn("<iframe", html_by_target[target])
            self.assertNotIn("<form", html_by_target[target])
            self.assertNotIn('src="http', html_by_target[target])

        partner_html = html_by_target["/partners"]
        self.assertTrue(all(f'href="{url}"' in partner_html for url in partner_urls))
        self.assertIn("Мой прямой номер телефона: +7 (499) 110-25-52", html_by_target["/direct-contact"])
        self.assertNotIn('class="rich-text"', html_by_target["/about"])
        self.assertNotIn("<h1", html_by_target["/about"])
        news_html = html_by_target["/news/"]
        positions = [news_html.index(target) for target, _, _ in article_facts]
        self.assertEqual(positions, sorted(positions))
        for target, title, _ in article_facts:
            self.assertIn("Новости", html_by_target[target])
            self.assertIn(escape(title, quote=True), html_by_target[target])
        self.assertIn("раздел сайта находится в разработке", html_by_target["/garantii"])
        self.assertIn("с 09-00 до 21-00 мск", html_by_target["/cctv"])

        articles[0].parent = None
        articles[0].save(update_fields=("parent",))
        self.assertEqual(self.get(article_facts[0][0]).status_code, 503)

    def test_service_catalogs_render_published_tree_with_exact_links(self) -> None:
        master = self.make_page(
            PageKind.SERVICES_MASTER_CATALOG,
            target="/services/",
        )
        master.name = "Услуги и цены"
        master.save(update_fields=("name",))
        section = self.make_page(
            PageKind.SERVICE_CATALOG,
            target="/services/remont/",
        )
        section.name = "Ремонт"
        section.parent = master
        section.position = 0
        section.save(update_fields=("name", "parent", "position"))
        detail = self.make_page(
            PageKind.SERVICE_DETAIL,
            target="/services/remont/remont-podveski",
        )
        detail.name = "Ремонт подвески"
        detail.parent = section
        detail.position = 0
        detail.save(update_fields=("name", "parent", "position"))
        hidden = self.make_page(
            PageKind.SERVICE_DETAIL,
            target="/services/remont/hidden-service",
            published=False,
        )
        hidden.name = "Скрытая услуга"
        hidden.parent = section
        hidden.position = 1
        hidden.save(update_fields=("name", "parent", "position"))

        master_response = self.get("/services/")
        master_head = self.client.head(
            "/services/",
            HTTP_X_ESTAKADA_REQUEST_TARGET="/services/",
        )
        self.assertEqual((master_response.status_code, master_head.status_code), (200, 200))
        self.assertEqual(master_head.content, b"")
        self.assertRegex(
            master_response.content.decode("utf-8"),
            r'class="[^"]*\bes-service-catalog\b[^"]*"',
        )
        self.assertContains(master_response, 'href="/services/remont/"', html=False)
        self.assertContains(master_response, "Все услуги автотехцентра")
        self.assertContains(
            master_response,
            'href="/services/remont/remont-podveski"',
            html=False,
        )
        self.assertNotContains(master_response, "Скрытая услуга")

        section_response = self.get("/services/remont/")
        self.assertEqual(section_response.status_code, 200)
        self.assertContains(section_response, 'aria-label="Хлебные крошки"', html=False)
        self.assertContains(section_response, "Главная")
        self.assertContains(section_response, "Услуги и цены")
        self.assertContains(section_response, "Ремонт подвески")
        self.assertNotContains(section_response, "Услуги раздела")
        self.assertNotIn("sessionid", section_response.cookies)

    def test_service_overview_and_detail_render_hero_body_price_and_breadcrumbs(self) -> None:
        master = self.make_page(PageKind.SERVICES_MASTER_CATALOG, target="/services/")
        master.name = "Услуги и цены"
        master.save(update_fields=("name",))
        overview = self.make_page(
            PageKind.SERVICE_SECTION_OVERVIEW,
            target="/services/kuzovnoj-remont/",
        )
        overview.name = "Кузовной ремонт"
        overview.parent = master
        overview.position = 0
        overview.save(update_fields=("name", "parent", "position"))
        detail = self.make_page(
            PageKind.SERVICE_DETAIL,
            target="/services/kuzovnoj-remont/remont-kuzova",
        )
        detail.name = "Ремонт кузова"
        detail.parent = overview
        detail.position = 0
        detail.save(update_fields=("name", "parent", "position"))

        hero = Asset.objects.create(
            purpose=AssetPurpose.CONTENT,
            state=AssetState.READY,
            source_sha256="c" * 64,
        )
        AssetFile.objects.create(
            asset=hero,
            kind=FileKind.MAIN,
            storage_key=f"img/{hero.id}/main.jpeg",
            sha256="d" * 64,
            byte_size=2048,
            mime_type=MediaType.JPEG,
            width=1600,
            height=900,
        )
        AssetUsage.objects.create(
            asset=hero,
            scope=UsageScope.PAGE_CURRENT,
            target_uuid=overview.id,
            slot="hero",
            position=0,
        )
        overview_content = PageContent.objects.get(page=overview)
        overview_payload = _payload(PageKind.SERVICE_SECTION_OVERVIEW)
        overview_payload["fields"]["body"] = (
            "<h2>Кузовной ремонт</h2><ul><li>Ремонт кузова</li></ul>"
            "<p>Описание раздела</p>"
        )
        overview_payload["fields"]["media"]["hero"] = str(hero.id)
        overview_content.current_payload = overview_payload
        overview_content.current_hash = canonical_payload_hash(overview_payload)
        overview_content.save(update_fields=("current_payload", "current_hash"))

        column_id = str(uuid.UUID(int=101))
        row_id = str(uuid.UUID(int=102))
        detail_content = PageContent.objects.get(page=detail)
        detail_payload = _payload(PageKind.SERVICE_DETAIL)
        detail_payload["fields"]["price_rows"] = {
            "columns": [{"id": column_id, "label": "Стоимость"}],
            "rows": [{
                "id": row_id,
                "label": "Ремонт элемента",
                "cells": [{
                    "column_id": column_id,
                    "kind": "amount",
                    "amount": "12345.50",
                    "from": True,
                }],
            }],
        }
        detail_content.current_payload = detail_payload
        detail_content.current_hash = canonical_payload_hash(detail_payload)
        detail_content.save(update_fields=("current_payload", "current_hash"))

        overview_response = self.get("/services/kuzovnoj-remont/")
        detail_response = self.get("/services/kuzovnoj-remont/remont-kuzova")
        detail_head = self.client.head(
            "/services/kuzovnoj-remont/remont-kuzova",
            HTTP_X_ESTAKADA_REQUEST_TARGET="/services/kuzovnoj-remont/remont-kuzova",
        )
        self.assertEqual(
            (overview_response.status_code, detail_response.status_code, detail_head.status_code),
            (200, 200, 200),
        )
        self.assertEqual(detail_head.content, b"")
        self.assertRegex(
            overview_response.content.decode("utf-8"),
            r'class="[^"]*\bes-service-content\b[^"]*"',
        )
        self.assertContains(
            overview_response,
            f'src="/media/img/{hero.id}/main.jpeg"',
            html=False,
        )
        self.assertContains(overview_response, "Вступление раздела")
        self.assertContains(
            overview_response,
            'class="es-subservice-card" href="/services/kuzovnoj-remont/remont-kuzova"',
            html=False,
        )
        self.assertContains(overview_response, ">01<", html=False)
        self.assertContains(overview_response, "Описание раздела")
        self.assertContains(overview_response, "Кузовной ремонт</h2>", html=False)
        self.assertContains(overview_response, "<li>Ремонт кузова</li>", html=False)
        self.assertContains(overview_response, 'class="es-content-body"', html=False)
        self.assertContains(overview_response, '/static/pages/public_service_children_v1.css', html=False)
        self.assertContains(
            overview_response,
            '/static/pages/public_service_content_rhythm_v2.css',
            html=False,
        )
        overview_html = overview_response.content.decode("utf-8")
        self.assertLess(
            overview_html.index('class="es-subservice-grid"'),
            overview_html.index('class="es-content-hero"'),
        )
        self.assertContains(detail_response, "Услуги и цены")
        self.assertContains(detail_response, "Кузовной ремонт")
        self.assertContains(detail_response, "Ремонт кузова")
        self.assertContains(detail_response, "Описание услуги")
        self.assertContains(detail_response, "Ремонт элемента")
        self.assertContains(detail_response, "12 345.50 ₽")
        self.assertNotIn("sessionid", detail_response.cookies)

    def test_articles_catalog_and_direct_article_render_exact_tree_and_body(self) -> None:
        catalog = Page.objects.get(kind=PageKind.ARTICLES_CATALOG)
        catalog_payload = _payload(PageKind.ARTICLES_CATALOG)
        PageContent.objects.create(
            page=catalog,
            current_payload=catalog_payload,
            current_hash=canonical_payload_hash(catalog_payload),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )
        targets = (
            "/articles/zamena-masla-v-dvigatele",
            "/articles/zamena-texnicheskix-zhidkostej",
            "/articles/zamena-filtrov-avtomobilya",
            "/articles/kompyuternaya-diagnostika-avtomobilya",
            "/articles/remen-grm",
            "/articles/remont-akpp",
            "/articles/remont-dvigatelya-avtomobilya",
            "/articles/remont-i-diagnostika-avtoelektriki",
            "/articles/remont-mkpp",
            "/articles/polirovka-far",
            "/articles/regulirovka-razval-sxozhdeniya-koles",
            "/articles/kachestvennyie-uslugi-shinomontazha",
            "/articles/sistema-oxlazhdeniya-dvigatelya",
            "/articles/ochistka-kondiczionera",
            "/articles/kuzovnoj-remont-avtomobilya",
            "/articles/povrezhdenie-lakokrasochnogo-pokryitiya",
            "/articles/pokraska-bampera",
            "/articles/kompleksnaya-shumoizolyacziya",
        )
        articles: list[tuple[Page, str, Asset]] = []
        for position, target in enumerate(targets):
            title = f"Статья {position + 1:02d}"
            article = self.make_page(PageKind.ARTICLE, target=target)
            article.name = title
            article.parent = catalog
            article.position = position
            article.save(update_fields=("name", "parent", "position"))
            payload = _payload(PageKind.ARTICLE)
            payload["fields"]["heading"]["h1"] = title
            payload["fields"]["intro"] = f"<p>Вступление {position + 1}</p>"
            payload["fields"]["body"] = f"<p>Текст статьи {position + 1}</p>"
            hero = Asset.objects.create(
                purpose=AssetPurpose.CONTENT,
                state=AssetState.READY,
                source_sha256=f"{position + 1:064x}",
            )
            AssetFile.objects.create(
                asset=hero,
                kind=FileKind.MAIN,
                storage_key=f"img/{hero.id}/main.webp",
                sha256=f"{position + 101:064x}",
                byte_size=2048 + position,
                mime_type=MediaType.WEBP,
                width=1600,
                height=900,
            )
            AssetUsage.objects.create(
                asset=hero,
                scope=UsageScope.PAGE_CURRENT,
                target_uuid=article.id,
                slot="hero",
                position=0,
            )
            payload["fields"]["media"]["hero"] = str(hero.id)
            content = PageContent.objects.get(page=article)
            content.current_payload = payload
            content.current_hash = canonical_payload_hash(payload)
            content.save(update_fields=("current_payload", "current_hash"))
            articles.append((article, target, hero))

        hidden = self.make_page(
            PageKind.ARTICLE,
            target="/articles/hidden-article",
            published=False,
        )
        hidden.name = "Скрытая статья"
        hidden.parent = catalog
        hidden.position = 18
        hidden.save(update_fields=("name", "parent", "position"))

        catalog_response = self.get("/articles/")
        catalog_head = self.client.head(
            "/articles/",
            HTTP_X_ESTAKADA_REQUEST_TARGET="/articles/",
        )
        direct_response = self.get(articles[0][1])
        direct_head = self.client.head(
            articles[0][1],
            HTTP_X_ESTAKADA_REQUEST_TARGET=articles[0][1],
        )

        self.assertEqual(
            (
                catalog_response.status_code,
                catalog_head.status_code,
                direct_response.status_code,
                direct_head.status_code,
            ),
            (200, 200, 200, 200),
        )
        self.assertEqual(catalog_head.content, b"")
        self.assertEqual(direct_head.content, b"")
        catalog_html = catalog_response.content.decode("utf-8")
        markers = [f'href="{target}"' for _article, target, _hero in articles]
        self.assertTrue(all(marker in catalog_html for marker in markers))
        self.assertEqual(
            [catalog_html.index(marker) for marker in markers],
            sorted(catalog_html.index(marker) for marker in markers),
        )
        self.assertNotIn("Скрытая статья", catalog_html)
        self.assertRegex(catalog_html, r'class="[^"]*\bes-articles-catalog\b[^"]*"')
        self.assertIn("public_home.css", catalog_html)
        self.assertIn("public_articles.css", catalog_html)
        self.assertEqual(catalog_html.count('class="es-article-card"'), 18)
        self.assertEqual(catalog_html.count('class="es-article-card-image"'), 18)
        self.assertIn(f'/media/img/{articles[0][2].id}/main.webp', catalog_html)
        self.assertIn("Обслуживание", catalog_html)
        self.assertIn("Комфорт", catalog_html)

        direct_html = direct_response.content.decode("utf-8")
        self.assertRegex(direct_html, r'class="[^"]*\bes-article\b[^"]*"')
        self.assertIn("public_home.css", direct_html)
        self.assertIn("public_articles.css", direct_html)
        self.assertIn("Статьи", direct_html)
        self.assertIn("Статья 01", direct_html)
        self.assertIn("Вступление 1", direct_html)
        self.assertIn("Текст статьи 1", direct_html)
        self.assertIn('class="es-article-hero"', direct_html)
        self.assertIn(f'/media/img/{articles[0][2].id}/main.webp', direct_html)
        self.assertIn('href="/articles/"', direct_html)
        self.assertNotIn("sessionid", direct_response.cookies)

        first_article, first_target, first_hero = articles[0]
        AssetUsage.objects.filter(
            asset=first_hero,
            scope=UsageScope.PAGE_CURRENT,
            target_uuid=first_article.id,
            slot="hero",
        ).delete()
        self.assertEqual(self.get("/articles/").status_code, 503)
        self.assertEqual(self.get(first_target).status_code, 503)
        AssetUsage.objects.create(
            asset=first_hero,
            scope=UsageScope.PAGE_CURRENT,
            target_uuid=first_article.id,
            slot="hero",
            position=0,
        )

        last_article = articles[-1][0]
        Page.objects.filter(pk=last_article.pk).update(is_published=False)
        self.assertEqual(self.get("/articles/").status_code, 503)
        Page.objects.filter(pk=last_article.pk).update(is_published=True)

        from modules.pages import public

        project_media = public.project_public_page_media

        def drift_last_article(*, page_id, expected_media):
            projected = project_media(page_id=page_id, expected_media=expected_media)
            if page_id == first_article.id:
                PageContent.objects.filter(page_id=last_article.id).update(generation=2)
            return projected

        with patch.object(
            public,
            "project_public_page_media",
            side_effect=drift_last_article,
        ):
            self.assertEqual(self.get("/articles/").status_code, 503)

    def test_gallery_catalog_variants_and_direct_album_render_exact_order(self) -> None:
        root = Page.objects.get(kind=PageKind.GALLERY_CATALOG)
        root_payload = _payload(PageKind.GALLERY_CATALOG)
        PageContent.objects.create(
            page=root,
            current_payload=root_payload,
            current_hash=canonical_payload_hash(root_payload),
            current_author=self.owner,
            current_created_at=timezone.now(),
        )
        Route.objects.create(
            page=root,
            target="/gallery-of-works/?page=2",
            mode=RouteMode.ALIAS,
            outcome=PageKind.GALLERY_CATALOG,
        )
        Route.objects.create(
            page=root,
            target="/gallery-of-works/?page=1",
            mode=RouteMode.REDIRECT,
            outcome=PageKind.GALLERY_CATALOG,
        )

        map_ids = (114, 113, 112, 111, 109, 106, 102, 99, 96, 92, 86, 81, 76, 70, 61, 56, 36)
        albums: list[tuple[Page, list[str]]] = []
        for position, map_id in enumerate(map_ids):
            title = f"Работа MAP-{map_id:03d}"
            target = f"/gallery-of-works/work-{position:02d}"
            page = Page.objects.create(
                name=title,
                kind=PageKind.GALLERY_ALBUM,
                parent=root,
                position=position,
                is_published=True,
            )
            Route.objects.create(
                page=page,
                target=target,
                mode=RouteMode.PRIMARY,
                outcome=PageKind.GALLERY_ALBUM,
            )
            payload = _payload(PageKind.GALLERY_ALBUM)
            payload["fields"]["heading"]["h1"] = title
            PageContent.objects.create(
                page=page,
                current_payload=payload,
                current_hash=canonical_payload_hash(payload),
                current_author=self.owner,
                current_created_at=timezone.now(),
            )
            album = GalleryAlbum.objects.create(page=page, position=position)
            photo_urls: list[str] = []
            for photo_position in range(2 if position == 0 else 1):
                identity = position * 10 + photo_position + 1
                asset = Asset.objects.create(
                    purpose=AssetPurpose.GALLERY_ORIGINAL,
                    state=AssetState.READY,
                    source_sha256=f"{identity:064x}",
                )
                file = AssetFile.objects.create(
                    asset=asset,
                    kind=FileKind.LEGACY_PUBLIC,
                    storage_key=f"img/{asset.id}/legacy-public.jpeg",
                    sha256=f"{identity + 1000:064x}",
                    byte_size=2048 + identity,
                    mime_type=MediaType.JPEG,
                    width=1600,
                    height=900,
                )
                GalleryPhoto.objects.create(
                    album=album,
                    asset=asset,
                    position=photo_position,
                    alt=f"{title}, фото {photo_position + 1}",
                )
                photo_urls.append(f"/media/{file.storage_key}")
            albums.append((page, photo_urls))

        root_response = self.get("/gallery-of-works/")
        page2_response = self.get("/gallery-of-works/?page=2")
        page1_response = self.get("/gallery-of-works/?page=1")
        page1_head = self.client.head(
            "/gallery-of-works/",
            HTTP_X_ESTAKADA_REQUEST_TARGET="/gallery-of-works/?page=1",
        )
        direct_target = Route.objects.get(page=albums[0][0], mode=RouteMode.PRIMARY).target
        direct_response = self.get(direct_target)
        direct_head = self.client.head(
            direct_target,
            HTTP_X_ESTAKADA_REQUEST_TARGET=direct_target,
        )

        self.assertEqual(
            (
                root_response.status_code,
                page2_response.status_code,
                page1_response.status_code,
                page1_head.status_code,
                direct_response.status_code,
                direct_head.status_code,
            ),
            (200, 200, 302, 302, 200, 200),
        )
        self.assertNotIn("Location", page2_response)
        self.assertEqual(page1_response["Location"], "/gallery-of-works/")
        self.assertEqual(page1_head["Location"], "/gallery-of-works/")
        self.assertEqual(direct_head.content, b"")

        root_html = root_response.content.decode("utf-8")
        root_markers = [
            f'href="{Route.objects.get(page=page, mode=RouteMode.PRIMARY).target}"'
            for page, _photo_urls in albums
        ]
        self.assertTrue(all(marker in root_html for marker in root_markers))
        self.assertEqual(
            sorted(root_html.index(marker) for marker in root_markers),
            [root_html.index(marker) for marker in root_markers],
        )
        for _page, photo_urls in albums:
            self.assertIn(photo_urls[0], root_html)
        self.assertNotIn(albums[0][1][1], root_html)

        page2_html = page2_response.content.decode("utf-8")
        for marker in root_markers[:10]:
            self.assertNotIn(marker, page2_html)
        for marker in root_markers[10:]:
            self.assertIn(marker, page2_html)
        self.assertIn('href="/gallery-of-works/"', page2_html)

        direct_html = direct_response.content.decode("utf-8")
        self.assertIn("Галерея работ", direct_html)
        self.assertIn(albums[0][0].name, direct_html)
        self.assertLess(
            direct_html.index(albums[0][1][0]),
            direct_html.index(albums[0][1][1]),
        )
        self.assertIn('data-gallery-grid', direct_html)
        self.assertEqual(direct_html.count('data-gallery-open='), 2)
        self.assertEqual(direct_html.count('data-gallery-photo'), 2)
        self.assertEqual(direct_html.count('data-gallery-thumb='), 2)
        self.assertIn('data-gallery-dialog', direct_html)
        self.assertIn('data-gallery-prev', direct_html)
        self.assertIn('data-gallery-next', direct_html)
        self.assertIn('data-gallery-close', direct_html)
        self.assertIn('src="/static/pages/public_gallery.js"', direct_html)
        self.assertNotIn('src="/static/pages/public_gallery.js"', root_html)
        self.assertIn('href="/gallery-of-works/"', direct_html)
        self.assertNotIn("sessionid", direct_response.cookies)

    def test_coherent_unknown_or_domain_invalid_target_is_404(self) -> None:
        for target in ("/unknown/", "/a/../b/"):
            with self.subTest(target=target):
                response = self.get(target)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.content, b"NOT_FOUND")

    def test_hidden_page_is_fieldless_zero_body_without_shell_projection(self) -> None:
        page = self.make_page(published=False)
        target = Route.objects.get(page=page).target
        with patch("modules.pages.public_http._capture_site_snapshot") as capture:
            response = self.get(target)
        capture.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(response["Cache-Control"], "no-store")
        visible = self.make_page()
        visible_target = Route.objects.get(page=visible).target
        from modules.pages import public_http

        with (
            patch.object(public_http, "project_legacy_plain", return_value=public_http.PublicBlank()),
            patch.object(public_http, "project_public_site_logo") as logo,
            patch.object(public_http, "project_public_navigation") as navigation,
            patch.object(public_http, "render_to_string") as render,
        ):
            response = self.get(visible_target)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        logo.assert_not_called()
        navigation.assert_not_called()
        render.assert_not_called()

    def test_redirect_is_direct_301_without_shell_projection(self) -> None:
        page = self.make_page()
        Route.objects.create(page=page, target="/old/", mode=RouteMode.REDIRECT, outcome=page.kind)
        with patch("modules.pages.public_http._capture_site_snapshot") as capture:
            response = self.get("/old/")
        capture.assert_not_called()
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], Route.objects.get(page=page, mode=RouteMode.PRIMARY).target)

    def test_unsupported_kind_and_outer_generation_drift_are_503(self) -> None:
        article = self.make_page(PageKind.ARTICLE)
        target = Route.objects.get(page=article).target
        self.assertEqual(self.get(target).status_code, 503)
        legacy = self.make_page()
        target = Route.objects.get(page=legacy).target
        from modules.pages import public_http

        original_navigation = public_http.project_public_navigation

        def mutate_after_document():
            result = original_navigation()
            SiteSettings.objects.filter(pk=self.settings.pk).update(
                structure_generation=self.settings.structure_generation + 1
            )
            return result

        with patch.object(public_http, "project_public_navigation", side_effect=mutate_after_document):
            response = self.get(target)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"H1", response.content)

    def test_logo_menu_and_settings_context_are_exact_and_private_free(self) -> None:
        page = self.make_page()
        response = self.get(Route.objects.get(page=page).target)
        self.assertContains(response, f'/media/img/{self.logo.id}/main.jpeg')
        for label in ("Услуги и цены", "Акции", "Наши работы", "Отзывы", "Статьи", "Контакты"):
            self.assertContains(response, label)
        self.assertNotContains(response, "private@example.test")
        self.assertNotContains(response, self.logo_file.sha256)
        AssetUsage.objects.filter(scope=UsageScope.SITE_SETTINGS).delete()
        self.assertEqual(self.get(Route.objects.get(page=page).target).status_code, 503)
        AssetUsage.objects.create(
            asset=self.logo, scope=UsageScope.SITE_SETTINGS, target_uuid=self.settings.id,
            slot="logo", position=0,
        )
        Asset.objects.filter(pk=self.logo.pk).update(state=AssetState.STAGED)
        self.assertEqual(self.get(Route.objects.get(page=page).target).status_code, 503)
        Asset.objects.filter(pk=self.logo.pk).update(state=AssetState.READY)
        AssetFile.objects.filter(pk=self.logo_file.pk).delete()
        self.assertEqual(self.get(Route.objects.get(page=page).target).status_code, 503)
        self.logo_file = AssetFile.objects.create(
            asset=self.logo, kind=FileKind.MAIN,
            storage_key=f"img/{self.logo.id}/main.jpeg", sha256="b" * 64,
            byte_size=30190, mime_type=MediaType.JPEG, width=240, height=80,
        )

        actions = Page.objects.get(name="Акции")
        visible_parent = Page.objects.create(
            name="Visible parent", kind=PageKind.ARTICLE, position=99, is_published=True
        )
        Route.objects.create(
            page=visible_parent, target="/visible-parent/", mode=RouteMode.PRIMARY,
            outcome=PageKind.ARTICLE,
        )
        Page.objects.filter(pk=actions.pk).update(parent=visible_parent, position=0)
        self.assertEqual(self.get(Route.objects.get(page=page).target).status_code, 503)
        hidden_parent = Page.objects.create(
            name="Hidden parent", kind=PageKind.ARTICLE, position=100, is_published=False
        )
        Page.objects.filter(pk=actions.pk).update(parent=hidden_parent, position=0)
        self.assertEqual(self.get(Route.objects.get(page=page).target).status_code, 200)

    def test_partner_escaping_and_canonical_rich_text_boundary(self) -> None:
        partner = self.make_page(PageKind.LEGACY_PARTNER_LINKS)
        response = self.get(Route.objects.get(page=partner).target)
        self.assertContains(response, "Партнёр &lt;1&gt;")
        self.assertContains(response, 'rel="noopener noreferrer"')
        text = self.make_page(PageKind.LEGACY_UNDER_CONSTRUCTION)
        response = self.get(Route.objects.get(page=text).target)
        self.assertContains(response, "<p>Текст <strong>безопасен</strong></p>", html=False)

    def test_seo_robots_and_alias_canonical_are_exact(self) -> None:
        page = self.make_page(allow_index=False)
        Route.objects.create(page=page, target="/alias/", mode=RouteMode.ALIAS, outcome=page.kind)
        response = self.get("/alias/")
        primary = Route.objects.get(page=page, mode=RouteMode.PRIMARY).target
        self.assertContains(response, f'<link rel="canonical" href="{primary}">', html=False)
        self.assertContains(response, '<meta name="robots" content="noindex, nofollow">', html=False)

    def test_public_response_has_no_session_cookie_or_private_cache_variation(self) -> None:
        page = self.make_page()
        response = self.get(Route.objects.get(page=page).target)
        self.assertNotIn("sessionid", response.cookies)
        self.assertNotIn("Cookie", response.get("Vary", ""))
        self.assertEqual(response["Cache-Control"], "public, max-age=0, must-revalidate")
        self.assertEqual(self.client.get("/manage/login/").get("Cache-Control"), "private, no-store")

    def test_static_scope_and_nginx_boundaries_remain_narrow(self) -> None:
        from modules.media import api as media_api
        from modules.pages import public_http

        page_source = inspect.getsource(public_http)
        media_source = inspect.getsource(media_api.project_public_site_logo)
        self.assertNotIn("from app", page_source)
        self.assertNotIn("request.user", page_source)
        self.assertNotIn("request.session", page_source)
        self.assertNotIn("open(", media_source)
        root = Path(__file__).resolve().parents[4]
        nginx = (root / "environment" / "rebuild5-preview" / "nginx.conf").read_text(encoding="utf-8")
        self.assertIn("proxy_set_header X-Estakada-Request-Target $request_uri;", nginx)
        self.assertIn("client_body_temp_path /tmp/client_temp;", nginx)
        self.assertIn("proxy_temp_path /tmp/proxy_temp;", nginx)
        self.assertIn("fastcgi_temp_path /tmp/fastcgi_temp;", nginx)
        self.assertIn("uwsgi_temp_path /tmp/uwsgi_temp;", nginx)
        self.assertIn("scgi_temp_path /tmp/scgi_temp;", nginx)
        media_pattern = r"^/media/img/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/(?:main|legacy-public)\.(?:jpg|jpeg|png|webp|svg)$"
        location_pattern = r"^/media/(?<media_key>img/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/(?:main|legacy-public)\.(?:jpg|jpeg|png|webp|svg))$"
        self.assertIn('location ~ "' + location_pattern + '"', nginx)
        self.assertIn('if ($request_uri !~ "' + media_pattern + '") { return 404; }', nginx)
        self.assertIn("location /media/ { return 404; }", nginx)
        media_start = nginx.index('location ~ "' + location_pattern + '"')
        media_end = nginx.index("location /media/ { return 404; }")
        media_block = nginx[media_start:media_end]
        self.assertIn("alias /srv/public-media/$media_key;", media_block)
        self.assertNotIn("$1", media_block)
        self.assertIn("disable_symlinks on;", media_block)
        self.assertIn("add_header X-Content-Type-Options nosniff always;", media_block)
        self.assertNotIn("application/octet-stream", media_block)
        for mime in ("image/jpeg jpg jpeg;", "image/png png;", "image/webp webp;", "image/svg+xml svg;"):
            self.assertIn(mime, media_block)
        accepted = f"/media/img/{uuid.uuid4()}/main.jpeg"
        self.assertIsNotNone(re.fullmatch(media_pattern, accepted))
        self.assertIsNotNone(
            re.fullmatch(media_pattern, accepted.replace("/main.", "/legacy-public."))
        )
        for rejected in (
            accepted.replace("/main.", "/preview."),
            accepted.replace(".jpeg", ".exe"),
            accepted.replace("/main.", "/nested/main."),
            "/media/img/../main.jpeg",
            accepted.replace("/main.", "/%2e%2e/main."),
            accepted.replace("/main.", "/%2Fmain."),
            accepted + "?download=1",
        ):
            self.assertIsNone(re.fullmatch(media_pattern, rejected))
        self.assertNotIn("private", nginx)
