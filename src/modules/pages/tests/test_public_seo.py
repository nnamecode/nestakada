from __future__ import annotations

from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from ..content import canonical_payload_hash
from ..models import Page, PageContent, PageKind
from .test_public_http import PublicHttpFixture, _payload


class PublicSeoTests(PublicHttpFixture, TestCase):
    def setUp(self) -> None:
        self.client = Client(enforce_csrf_checks=True)
        self.make_base()
        for page in Page.objects.filter(content__isnull=True):
            payload = _payload(page.kind)
            PageContent.objects.create(
                page=page,
                current_payload=payload,
                current_hash=canonical_payload_hash(payload),
                current_author=self.owner,
                current_created_at=timezone.now(),
            )

    @override_settings(
        PUBLIC_ORIGIN="https://estakada-service.ru",
        SEO_ROBOTS_PROFILE="production",
    )
    def test_sitemap_contains_only_published_indexable_primary_routes(self) -> None:
        included = self.make_page(target="/included/")
        self.make_page(target="/hidden/", published=False)
        self.make_page(target="/noindex/", allow_index=False)

        response = self.client.get(
            "/sitemap.xml",
            HTTP_X_FORWARDED_HOST="attacker.example",
            HTTP_REFERER="https://attacker.example/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/xml; charset=utf-8")
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn(b"https://estakada-service.ru/included/", response.content)
        self.assertNotIn(b"/hidden/", response.content)
        self.assertNotIn(b"/noindex/", response.content)
        self.assertNotIn(b"attacker.example", response.content)

        head = self.client.head("/sitemap.xml")
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b"")
        self.assertEqual(head["Content-Length"], str(len(response.content)))
        post = self.client.post("/sitemap.xml")
        self.assertEqual(post.status_code, 405)
        self.assertEqual(post["Allow"], "GET, HEAD")

        included.content.current_hash = "0" * 64
        included.content.save(update_fields=("current_hash",))
        self.assertEqual(self.client.get("/sitemap.xml").status_code, 503)

    @override_settings(PUBLIC_ORIGIN="http://localhost:18085", SEO_ROBOTS_PROFILE="deny-all")
    def test_robots_deny_all_is_exact_and_methods_are_closed(self) -> None:
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"User-agent: *\nDisallow: /\n")
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(self.client.head("/robots.txt")["Content-Length"], str(len(response.content)))
        post = self.client.post("/robots.txt")
        self.assertEqual(post.status_code, 405)
        self.assertEqual(post["Allow"], "GET, HEAD")

    @override_settings(
        PUBLIC_ORIGIN="https://estakada-service.ru",
        SEO_ROBOTS_PROFILE="production",
    )
    def test_robots_production_uses_only_trusted_origin_and_invalid_config_fails_closed(self) -> None:
        response = self.client.get(
            "/robots.txt",
            HTTP_X_FORWARDED_HOST="attacker.example",
            HTTP_REFERER="https://attacker.example/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Disallow: /manage/", response.content)
        self.assertIn(b"Allow: /gallery-of-works/?page=2$", response.content)
        self.assertIn(b"Sitemap: https://estakada-service.ru/sitemap.xml", response.content)
        self.assertNotIn(b"attacker.example", response.content)
        self.assertNotIn(b"Disallow: /static/", response.content)
        self.assertNotIn(b"Disallow: /media/", response.content)

        with override_settings(SEO_ROBOTS_PROFILE="unknown"):
            self.assertEqual(self.client.get("/robots.txt").status_code, 503)

    @override_settings(
        PUBLIC_ORIGIN="https://estakada-service.ru",
        SEO_ROBOTS_PROFILE="production",
    )
    def test_sitemap_race_fails_closed(self) -> None:
        from .. import public_seo

        original = public_seo._capture_sitemap
        calls = 0

        def changed(configuration):
            nonlocal calls
            snapshot = original(configuration)
            calls += 1
            if calls == 2:
                return public_seo._SitemapSnapshot("different", snapshot.locations)
            return snapshot

        with patch.object(public_seo, "_capture_sitemap", side_effect=changed):
            self.assertEqual(self.client.get("/sitemap.xml").status_code, 503)
