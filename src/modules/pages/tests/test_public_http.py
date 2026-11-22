from __future__ import annotations

import inspect
import re
import uuid
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
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
    elif kind in {PageKind.LEGACY_UNDER_CONSTRUCTION, PageKind.LEGACY_CAMERA_SCHEDULE_TEXT}:
        fields.update({"intro": "<p>Вступление</p>", "body": "<p>Текст <strong>безопасен</strong></p>"})
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
