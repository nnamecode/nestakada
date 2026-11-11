from unittest.mock import patch

from django.db import models
from django.test import TestCase, override_settings

from page_versions import schema
from page_versions.models import PageContentState, PageRevision

from .models import Page, Route


def raw(model):
    return models.QuerySet(model=model, using='default')


@override_settings(PUBLIC_ORIGIN='http://localhost:8767',
                   SEO_ROBOTS_PROFILE='deny-all')
class Dev11SitemapTests(TestCase):
    def page(self, name, target, *, kind=Page.Kind.ARTICLE, published=True,
             indexing=True, position=None):
        if position is None:
            position = Page.objects.count()
        page = Page.objects.create(
            name=name, kind=kind, position=position,
            is_published=published)
        route = Route.objects.create(
            page=page, kind=Route.Kind.PRIMARY, target=target)
        payload = schema.snapshot_v1(
            kind, h1=name, title=name, description='',
            indexing_allowed=indexing, intro_text='<p>Intro</p>',
            main_text='<p>Main</p>', layout=[
                {'id': '71de8370-3105-5209-a189-82bb243b0051',
                 'kind': 'text', 'field': 'intro_text',
                 'protected_nodes': []},
                {'id': '71de8370-3105-5209-a189-82bb243b0052',
                 'kind': 'text', 'field': 'main_text',
                 'protected_nodes': []},
            ]).data()
        revision = PageRevision.objects.create(
            page=page, sequence=1, schema_version=schema.SCHEMA,
            payload=payload, payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(
            page=page, current_revision=revision, sequence=1)
        return page, route, revision

    def complete_graph(self):
        ordinary = self.page('Обычная', '/ordinary/')[0]
        Route.objects.create(
            page=ordinary, kind=Route.Kind.REDIRECT,
            target='/old-ordinary/')
        Route.objects.create(
            page=None, kind=Route.Kind.SYSTEM,
            target='/system-sitemap-test/')
        gallery = self.page(
            'Галерея', '/gallery-of-works/', kind=Page.Kind.GALLERY)[0]
        Route.objects.create(
            page=gallery, kind=Route.Kind.ALIAS,
            target='/gallery-of-works/?page=2', is_legacy=True)
        album = self.page(
            'Альбом', '/gallery-of-works/album-one',
            kind=Page.Kind.ALBUM)[0]
        wash_old = self.page(
            'Старая автомойка', '/wash-source/', kind=Page.Kind.WASH)[0]
        Route.objects.create(
            page=wash_old, kind=Route.Kind.ALIAS,
            target='/services/drugie-uslugi/avtomojka', is_legacy=True)
        wash_new = self.page(
            'Автомойка', '/services/avtomojka',
            kind=Page.Kind.SERVICE_CATALOG)[0]
        noindex = self.page('Закрытая', '/noindex/', indexing=False)[0]
        hidden = self.page('Скрытая', '/hidden/', published=False)[0]
        return {
            'ordinary': ordinary, 'gallery': gallery, 'album': album,
            'wash_old': wash_old, 'wash_new': wash_new,
            'noindex': noindex, 'hidden': hidden,
        }

    def test_s11_sitemap_001_exact_representatives_order_and_http_methods(self):
        self.complete_graph()
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'], 'application/xml; charset=utf-8')
        self.assertEqual(response['Cache-Control'], 'no-cache')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        body = response.content.decode()
        expected = [
            'http://localhost:8767/gallery-of-works/',
            'http://localhost:8767/gallery-of-works/album-one',
            'http://localhost:8767/ordinary/',
            'http://localhost:8767/services/avtomojka',
        ]
        self.assertEqual(body.count('<url>'), len(expected))
        positions = [body.index('<loc>' + url + '</loc>') for url in expected]
        self.assertEqual(positions, sorted(positions))
        for forbidden in ('?page=2', 'drugie-uslugi', '/wash-source/',
                          '/noindex/', '/hidden/', '/old-ordinary/',
                          '/system-sitemap-test/'):
            self.assertNotIn(forbidden, body)
        head = self.client.head('/sitemap.xml')
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b'')
        self.assertEqual(head['Content-Length'], str(len(response.content)))
        post = self.client.post('/sitemap.xml')
        self.assertEqual(post.status_code, 405)
        self.assertEqual(post['Allow'], 'GET, HEAD')

    def test_s11_sitemap_002_unknown_alias_and_corrupt_revision_fail_closed(self):
        pages = self.complete_graph()
        Route.objects.create(
            page=pages['ordinary'], kind=Route.Kind.ALIAS,
            target='/unexpected-alias/', is_legacy=True)
        refused = self.client.get('/sitemap.xml')
        self.assertEqual(refused.status_code, 503)
        self.assertNotIn(b'<urlset', refused.content)
        raw(Route).filter(target='/unexpected-alias/').delete()
        state = PageContentState.objects.get(page=pages['ordinary'])
        raw(PageRevision).filter(pk=state.current_revision_id).update(
            payload_hash='0' * 64)
        corrupt = self.client.get('/sitemap.xml')
        self.assertEqual(corrupt.status_code, 503)
        self.assertNotIn(b'<urlset', corrupt.content)

    def test_s11_sitemap_003_capture_race_and_caps_have_no_partial_xml(self):
        pages = self.complete_graph()
        fired = [False]

        def mutate_once():
            if not fired[0]:
                fired[0] = True
                raw(Page).filter(pk=pages['ordinary'].pk).update(
                    is_published=False)

        with patch('content.public_views._sitemap_boundary',
                   side_effect=mutate_once):
            raced = self.client.get('/sitemap.xml')
        self.assertEqual(raced.status_code, 503)
        self.assertNotIn(b'<urlset', raced.content)
        raw(Page).filter(pk=pages['ordinary'].pk).update(is_published=True)
        for setting in (
                'MAX_SITEMAP_PAGES', 'MAX_SITEMAP_PRIMARY_ROUTES',
                'MAX_SITEMAP_ALIASES', 'MAX_SITEMAP_STATES',
                'MAX_SITEMAP_REVISIONS'):
            with self.subTest(cap=setting), patch(
                    'content.public_seo.' + setting, 1):
                capped = self.client.get('/sitemap.xml')
            self.assertEqual(capped.status_code, 503)
            self.assertNotIn(b'<urlset', capped.content)
        with patch('content.public_seo.MAX_SITEMAP_BYTES', 64):
            oversized = self.client.get('/sitemap.xml')
        self.assertEqual(oversized.status_code, 503)
        self.assertNotIn(b'<urlset', oversized.content)
