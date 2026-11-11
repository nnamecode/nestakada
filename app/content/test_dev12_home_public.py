from html import escape
from unittest.mock import patch
from uuid import UUID

from django.db import models, transaction
from django.test import TestCase, override_settings

from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder
from page_versions import schema
from page_versions.models import PageContentState, PageRevision
from shared_content.public import RenderedShared

from . import dev12_home_apply as home_apply
from .models import Page, Route


def raw(model):
    return models.QuerySet(model=model, using='default')


def fake_shared(*, capture_host, media_url, static_url):
    with transaction.atomic():
        host = capture_host()
    static_url('public-shared.css', 'a' * 64)
    static_url('public-shared.js', 'b' * 64)
    links = ''.join('<a href="%s">%s</a>' % (
        escape(item.url, quote=True), escape(item.label))
        for item in host.navigation)
    return RenderedShared('<header>' + links + '</header>',
                          '<footer>Footer</footer>', '"home"', 'home')


@override_settings(PUBLIC_ORIGIN='http://localhost:8767',
                   SEO_ROBOTS_PROFILE='deny-all')
class Dev12HomePublicTests(TestCase):
    def setUp(self):
        renderer = patch('content.public_views.render_shared',
                         side_effect=fake_shared)
        renderer.start(); self.addCleanup(renderer.stop)

    def create_home(self, *, profile=True):
        package = home_apply._read_package()
        payload = (home_apply._target_payload(package) if profile else
                   schema.snapshot_v1(
                       Page.Kind.HOME, h1='Legacy home',
                       main_text='<p>Legacy body</p>', layout=[{
                           'id': '71de8370-3105-5209-a189-82bb243b0052',
                           'kind': 'text', 'field': 'main_text',
                           'protected_nodes': [],
                       }]).data(Page.Kind.HOME))
        page = Page.objects.create(
            id=UUID(home_apply.HOME_ID), name='Главная', kind=Page.Kind.HOME,
            is_published=True)
        route = Route.objects.create(
            page=page, target='/', kind=Route.Kind.PRIMARY)
        revision = PageRevision.objects.create(
            page=page, sequence=1, schema_version=schema.SCHEMA,
            payload=payload, payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(
            page=page, current_revision=revision, sequence=1)
        if profile:
            self.seed_media(page, package, payload)
        return page, route, revision, package

    def seed_media(self, page, package, payload):
        descriptors = home_apply._media_descriptors(package)
        design = MediaFolder.objects.create(
            id=home_apply.MEDIA_FOLDER_ID, path=home_apply.MEDIA_FOLDER_PATH)
        legacy = MediaFolder.objects.create(path='legacy/public-home-test')
        assets, files = [], []
        for row in descriptors:
            assets.append(Asset(
                id=UUID(row['asset_id']),
                folder=legacy if row['legacy'] else design,
                status=Asset.Status.READY,
                provenance='fixture' if row['legacy'] else home_apply.PROVENANCE,
                is_legacy=row['legacy'], source_url=row['source_url'],
                source_sha256=row['source_sha256']))
            files.append(AssetFile(
                id=UUID(row['file_id']), asset_id=row['asset_id'],
                kind=row['kind'], key=row['key'], sha256=row['sha256'],
                byte_size=row['byte_size']))
        raw(Asset).bulk_create(assets); raw(AssetFile).bulk_create(files)
        for slot, asset_id in schema.asset_slots(payload).items():
            AssetUsage.objects.create(
                asset_id=asset_id, kind=AssetUsage.Kind.CURRENT_PAGE,
                consumer_id=page.pk, slot=slot)

    def test_profile_home_renders_fixed_safe_sections_and_local_assets(self):
        _page, route, _revision, package = self.create_home()
        response = self.client.get(route.target)
        self.assertEqual(response.status_code, 200)
        source = response.content.decode()
        self.assertEqual(source.count('class="public-home"'), 1)
        self.assertEqual(source.count('class="public-home-services"'), 1)
        self.assertEqual(source.count('data-home-price-panel'), 6)
        self.assertEqual(source.count('href="#home-price-panel-'), 6)
        self.assertNotIn('role="tab"', source)
        self.assertNotIn('role="tabpanel"', source)
        self.assertNotIn('aria-selected=', source)
        self.assertNotRegex(
            source,
            r'<section[^>]*(?:hidden[^>]*data-home-price-panel|'
            r'data-home-price-panel[^>]*hidden)')
        self.assertEqual(source.count('class="public-home-works"'), 1)
        self.assertEqual(source.count('/public-media/'), 21)
        self.assertIn('<script defer src="/static/public-home.js"></script>', source)
        self.assertIn('href="/reviews"', source)
        self.assertIn(package['profile']['reviews']['label'], source)
        for forbidden in ('<form', '<iframe', 'youtube', 'yandex',
                          'maps.', 'http://example', 'https://example'):
            self.assertNotIn(forbidden, source.lower())
        self.assertEqual(response['Cache-Control'], 'no-cache')
        self.assertIn("script-src 'self'", response['Content-Security-Policy'])

    def test_legacy_home_keeps_generic_body_without_profile_script(self):
        _page, route, _revision, _package = self.create_home(profile=False)
        response = self.client.get(route.target)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Legacy body', response.content)
        self.assertNotIn(b'class="public-home"', response.content)
        self.assertNotIn(b'/static/public-home.js', response.content)

    def test_missing_current_home_usage_fails_closed_without_partial_body(self):
        page, route, _revision, package = self.create_home()
        asset_id = package['media'][0]['asset_id']
        raw(AssetUsage).filter(
            kind=AssetUsage.Kind.CURRENT_PAGE, consumer_id=page.pk,
            asset_id=asset_id).delete()
        response = self.client.get(route.target)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertNotIn(b'public-home', response.content)
        self.assertNotIn(package['profile']['hero']['lead'].encode(),
                         response.content)

    def test_home_script_is_fixed_local_nosniff_and_get_head_only(self):
        response = self.client.get('/static/public-home.js')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'],
                         'text/javascript; charset=utf-8')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        source = response.content.decode()
        for forbidden in ('fetch(', 'XMLHttpRequest', 'WebSocket',
                          'localStorage', 'sessionStorage', 'document.cookie',
                          'innerHTML', 'eval(', 'new Function', 'import('):
            self.assertNotIn(forbidden, source)
        self.assertIn("['ArrowLeft', 'ArrowRight', 'Home', 'End']", source)
        self.assertIn("setAttribute('role', 'tablist')", source)
        self.assertIn("setAttribute('role', 'tabpanel')", source)
        stylesheet = self.client.get('/static/public.css')
        self.assertEqual(stylesheet.status_code, 200)
        css = stylesheet.content.decode()
        for contract in ('.public-home-services a:focus-visible',
                         '.public-home [hidden]{display:none}',
                         '@media(max-width:960px)',
                         '@media(max-width:620px)'):
            self.assertIn(contract, css)
        self.assertEqual(self.client.head('/static/public-home.js').content, b'')
        post = self.client.post('/static/public-home.js')
        self.assertEqual(post.status_code, 405)
        self.assertEqual(post['Allow'], 'GET, HEAD')
