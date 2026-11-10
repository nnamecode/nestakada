from unittest.mock import patch
import base64
import hashlib
from types import SimpleNamespace
from urllib.parse import urlencode
from uuid import uuid4

from django.contrib.sessions.models import Session
from django.db import DatabaseError, models
from django.test import Client, TransactionTestCase, override_settings

from audit.models import AuditEvent
from media_library import services as media_services
from media_library.models import Asset, AssetFile
from media_library.storage import MediaStorage
from page_versions import schema
from page_versions.models import PageContentState, PageRevision
from page_editor.test_media_http import PNG
from shared_content import public as shared_public
from shared_content import test_shared_reservation as reservation
from shared_content.models import SharedBlock, SharedRevision
from shared_content.storage import SharedStorage

from .models import Page, Route
from .public_read import PublicUnavailable
from .public_shared import PublicSharedHost


@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PublicSharedPageTests(reservation.ReservationFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.anonymous = Client(enforce_csrf_checks=True, HTTP_HOST='localhost')

    def create_public_page(self, name='PUBLIC-PAGE', target='/public-page/', *,
                           position=10, published=True, image_asset=None,
                           image_mode='standalone',
                           page_kind=Page.Kind.ARTICLE,
                           intro_text='<p>PUBLIC-INTRO</p>'):
        page = Page.objects.create(
            name=name, kind=page_kind, position=position,
            is_published=published)
        route = Route.objects.create(
            page=page, kind=Route.Kind.PRIMARY, target=target)
        image_id = '71de8370-3105-5209-a189-82bb243b0191'
        embedded, main_image, preview, protected = [], None, None, []
        layout = [
            {'id': '71de8370-3105-5209-a189-82bb243b0051', 'kind': 'text',
             'field': 'intro_text', 'protected_nodes': []}]
        if image_asset is not None:
            reference = {'asset_id': str(image_asset.pk), 'alt': '<PUBLIC-ALT>',
                         'alignment': 'right', 'width_px': 640, 'height_px': None}
            if image_mode == 'main':
                main_image = reference
            elif image_mode == 'preview':
                preview = reference
            else:
                embedded = [{'id': image_id, **reference}]
                if image_mode == 'standalone':
                    layout.append({
                        'id': '71de8370-3105-5209-a189-82bb243b0192',
                        'kind': 'image', 'image_id': image_id})
                elif image_mode == 'protected':
                    protected = [{
                        'id': '71de8370-3105-5209-a189-82bb243b0193',
                        'reference_id': image_id, 'fingerprint': 'd' * 64}]
        layout.append({
            'id': '71de8370-3105-5209-a189-82bb243b0052', 'kind': 'text',
            'field': 'main_text', 'protected_nodes': protected})
        payload = schema.snapshot_v1(
            page.kind, h1='PUBLIC-H1', title='PUBLIC-TITLE',
            intro_text=intro_text,
            main_text='<p>PUBLIC-MAIN</p>', main_image=main_image,
            preview_image=preview,
            embedded_images=embedded, layout=layout).data()
        revision = PageRevision.objects.create(
            page=page, sequence=1, schema_version=schema.SCHEMA,
            payload=payload, payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(
            page=page, current_revision=revision, sequence=1)
        if image_asset is not None:
            slot = ('main_image' if image_mode == 'main'
                    else 'preview_image' if image_mode == 'preview'
                    else 'embedded:' + image_id)
            media_services.attach(
                asset_id=image_asset.pk, kind='current_page',
                consumer_id=page.pk, slot=slot)
        return page, route, revision

    def create_many_image_page(self, assets, *, name, target, position,
                               main_asset=None,
                               page_kind=Page.Kind.ARTICLE):
        page = Page.objects.create(
            name=name, kind=page_kind, position=position,
            is_published=True)
        route = Route.objects.create(
            page=page, kind=Route.Kind.PRIMARY, target=target)
        image_ids = [str(uuid4()) for _asset in assets]
        embedded = [
            {'id': image_id, 'asset_id': str(asset.pk),
             'alt': 'BOUNDARY-' + str(index), 'alignment': 'center',
             'width_px': 640, 'height_px': None}
            for index, (image_id, asset) in enumerate(
                zip(image_ids, assets), start=1)
        ]
        layout = [
            {'id': str(uuid4()), 'kind': 'text', 'field': 'intro_text',
             'protected_nodes': []},
            *[{'id': str(uuid4()), 'kind': 'image', 'image_id': image_id}
              for image_id in image_ids],
            {'id': str(uuid4()), 'kind': 'text', 'field': 'main_text',
             'protected_nodes': []},
        ]
        payload = schema.snapshot_v1(
            page.kind, h1=name, title=name,
            intro_text='<p>BOUNDARY-INTRO</p>',
            main_text='<p>BOUNDARY-MAIN</p>',
            main_image=(None if main_asset is None else {
                'asset_id': str(main_asset.pk), 'alt': 'BOUNDARY-MAIN-ALT',
                'alignment': 'center', 'width_px': 1200,
                'height_px': 700}),
            embedded_images=embedded,
            layout=layout).data()
        revision = PageRevision.objects.create(
            page=page, sequence=1, schema_version=schema.SCHEMA,
            payload=payload, payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(
            page=page, current_revision=revision, sequence=1)
        for image_id, asset in zip(image_ids, assets):
            media_services.attach(
                asset_id=asset.pk, kind='current_page', consumer_id=page.pk,
                slot='embedded:' + image_id)
        if main_asset is not None:
            media_services.attach(
                asset_id=main_asset.pk, kind='current_page',
                consumer_id=page.pk, slot='main_image')
        return page, route, revision

    def clone_public_asset(self):
        source_file = self.asset.files.get(kind=AssetFile.Kind.MAIN)
        with MediaStorage().open_verified(
                source_file.key, {'sha256': source_file.sha256,
                                  'byte_size': source_file.byte_size}) as source:
            body = source.read()
        asset = Asset.objects.create(
            folder=self.asset.folder, provenance='public-page-media-test')
        media_services.write_file(
            asset_id=asset.pk, kind=AssetFile.Kind.MAIN,
            key='img/' + str(asset.pk) + '/main.webp', chunks=body)
        return media_services.mark_ready(asset_id=asset.pk)

    def create_legacy_public_asset(self, body, suffix='png'):
        sha256 = hashlib.sha256(body).hexdigest()
        asset = Asset.objects.create(
            folder=self.asset.folder, provenance='public-page-legacy-test',
            is_legacy=True, source_url='https://legacy.invalid/image.' + suffix,
            source_sha256=sha256)
        media_services.write_file(
            asset_id=asset.pk, kind=AssetFile.Kind.LEGACY_PUBLIC,
            key='img/%s/legacy.%s' % (asset.pk, suffix), chunks=body)
        return media_services.mark_ready(asset_id=asset.pk)

    def read_state(self):
        return self.state(), SharedStorage().inventory(), Session.objects.count(), AuditEvent.objects.count()

    def body(self, response):
        try:
            return b''.join(response.streaming_content) if response.streaming else response.content
        finally:
            if response.streaming:
                response.close()

    def seed(self):
        self.apply_text('header', 'PRODUCTION-HEADER')
        self.apply_text('footer', 'PRODUCTION-FOOTER')
        return self.create_public_page()

    def test_psh001_005_006_current_composition_resources_etag_and_no_writes(self):
        with self.candidate():
            page, route, _revision = self.seed()
            before = self.read_state()
            response = self.anonymous.get(route.target)
            source = response.content.decode()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(source.count('<header'), 1)
            self.assertEqual(source.count('<footer'), 1)
            self.assertIn('PRODUCTION-HEADER', source)
            self.assertIn('PRODUCTION-FOOTER', source)
            self.assertIn('PUBLIC-MAIN', source)
            self.assertRegex(
                source,
                r'<a(?=[^>]*aria-current="page")(?=[^>]*href="/public-page/")[^>]*>PUBLIC-PAGE</a>')
            self.assertIn("default-src 'none'", response['Content-Security-Policy'])
            self.assertEqual(response['Cache-Control'], 'no-cache')
            self.assertRegex(response['ETag'], r'^"[0-9a-f]{64}"$')
            self.assertFalse(response.cookies)

            unchanged = self.anonymous.get(route.target, HTTP_IF_NONE_MATCH=response['ETag'])
            self.assertEqual(unchanged.status_code, 304)
            self.assertEqual(unchanged.content, b'')
            head = self.anonymous.head(route.target)
            self.assertEqual(head.status_code, 200)
            self.assertEqual(head.content, b'')

            css = shared_public.static_descriptor('public-shared.css')
            css_response = self.anonymous.get(
                '/static/shared/%s/public-shared.css' % css['digest'])
            self.assertEqual(css_response.status_code, 200)
            self.assertEqual(css_response.content, css['body'])
            media = self.asset.files.get(kind=AssetFile.Kind.MAIN)
            media_response = self.anonymous.get('/public-media/%s/' % media.pk)
            self.assertEqual(media_response.status_code, 200)
            self.assertTrue(self.body(media_response))
            self.assertEqual(
                self.anonymous.get('/static/shared/%s/unknown.js' % ('0' * 64)).status_code,
                404)
            self.assertEqual(self.read_state(), before)
            self.assertEqual(str(page.pk), str(Page.objects.get(pk=page.pk).pk))

    def test_psh002_page_change_revalidates_body_and_composite_etag(self):
        with self.candidate():
            page, route, revision = self.seed()
            first = self.anonymous.get(route.target)
            payload = dict(revision.payload)
            payload['main_text'] = '<p>PUBLIC-MAIN-SECOND</p>'
            second_revision = PageRevision.objects.create(
                page=page, sequence=2, schema_version=schema.SCHEMA,
                payload=payload, payload_hash=schema.digest(payload),
                kind=PageRevision.Kind.AUTOMATIC, author_id=1)
            models.QuerySet(model=PageContentState).filter(page=page).update(
                current_revision=second_revision, sequence=2)
            second = self.anonymous.get(route.target, HTTP_IF_NONE_MATCH=first['ETag'])
            self.assertEqual(second.status_code, 200)
            self.assertIn(b'PUBLIC-MAIN-SECOND', second.content)
            self.assertNotEqual(second['ETag'], first['ETag'])

    def test_psh003_007_corruption_is_closed_and_404_redirect_skip_shared(self):
        with self.candidate():
            page, route, _revision = self.seed()
            old = Route.objects.create(
                page=page, kind=Route.Kind.REDIRECT, target='/old-public-page/')
            with patch('content.public_views.render_shared') as renderer:
                self.assertEqual(self.anonymous.get('/missing-public-page/').status_code, 404)
                redirected = self.anonymous.get(old.target)
                self.assertEqual(redirected.status_code, 301)
                self.assertEqual(redirected['Location'], route.target)
                renderer.assert_not_called()

            current = SharedBlock.objects.get(kind='footer').current_revision_id
            models.QuerySet(model=SharedRevision).filter(pk=current).update(
                html='PRIVATE-CORRUPTION-CANARY')
            failed = self.anonymous.get(route.target)
            self.assertEqual(failed.status_code, 503)
            self.assertEqual(failed['Cache-Control'], 'no-store')
            self.assertNotIn(b'PRIVATE-CORRUPTION-CANARY', failed.content)
            self.assertIn("default-src 'none'", failed['Content-Security-Policy'])

    def test_pimg_standalone_html_and_contextual_bytes(self):
        with self.candidate():
            self.apply_text('header', 'PRODUCTION-HEADER')
            self.apply_text('footer', 'PRODUCTION-FOOTER')
            asset = self.clone_public_asset()
            page, route, _revision = self.create_public_page(
                image_asset=asset)
            file = asset.files.get(kind=AssetFile.Kind.MAIN)
            slot = 'embedded:71de8370-3105-5209-a189-82bb243b0191'
            query = urlencode((('page', str(page.pk)), ('slot', slot)))
            url = '/public-media/%s/?%s' % (file.pk, query)

            response = self.anonymous.get(route.target)
            source = response.content.decode()
            self.assertEqual(response.status_code, 200)
            self.assertLess(source.index('PUBLIC-INTRO'), source.index('<figure'))
            self.assertLess(source.index('<figure'), source.index('PUBLIC-MAIN'))
            self.assertIn(url.replace('&', '&amp;'), source)
            self.assertIn('alt="&lt;PUBLIC-ALT&gt;"', source)
            self.assertNotIn(str(asset.pk), source)
            self.assertNotIn(file.key, source)

            media = self.anonymous.get(url)
            body = self.body(media)
            self.assertEqual(media.status_code, 200)
            self.assertEqual(hashlib.sha256(body).hexdigest(), file.sha256)
            self.assertEqual(media['Content-Type'], 'image/webp')
            self.assertEqual(media['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(media['Cache-Control'], 'no-cache')
            head = self.anonymous.head(url)
            self.assertEqual(head.status_code, 200)
            self.assertEqual(head.content, b'')
            self.assertEqual(head['Content-Length'], str(file.byte_size))
            unchanged = self.anonymous.get(url, HTTP_IF_NONE_MATCH=media['ETag'])
            self.assertEqual(unchanged.status_code, 304)
            self.assertEqual(unchanged.content, b'')
            with patch('shared_content.public._open_media') as media_open:
                denied = self.anonymous.post(url)
            self.assertIn(denied.status_code, (403, 405))
            media_open.assert_not_called()
            self.assertEqual(self.anonymous.get('/public-media/%s/' % file.pk).status_code, 404)

    def test_pimg_010_standalone_media_ceiling_and_batched_capture(self):
        count = 64
        image_ids = [str(uuid4()) for _index in range(count)]
        asset_ids = [uuid4() for _index in range(count)]
        file_ids = [uuid4() for _index in range(count)]
        page = SimpleNamespace(
            page_id=str(uuid4()),
            payload={
                'main_image': None,
                'embedded_images': [
                    {'id': image_id, 'asset_id': str(asset_id)}
                    for image_id, asset_id in zip(image_ids, asset_ids)
                ],
                'layout': [
                    {'kind': 'image', 'image_id': image_id}
                    for image_id in image_ids
                ],
            })
        usage_rows = [SimpleNamespace(
            slot='embedded:' + image_id, asset_id=asset_id,
            asset=SimpleNamespace(
                status=Asset.Status.READY, is_legacy=False))
            for image_id, asset_id in zip(image_ids, asset_ids)]
        file_rows = [SimpleNamespace(
            pk=file_id, asset_id=asset_id, kind=AssetFile.Kind.MAIN,
            key='img/%s/main.webp' % asset_id, sha256='a' * 64,
            byte_size=1)
            for file_id, asset_id in zip(file_ids, asset_ids)]

        with patch(
                'content.public_shared.AssetUsage.objects.select_related') as usage_query, patch(
                'content.public_shared.AssetFile.objects.filter') as file_query:
            usage_query.return_value.filter.return_value.order_by.return_value = usage_rows
            file_query.return_value.order_by.return_value = file_rows
            mapping, files = PublicSharedHost._standalone_media(page)
        self.assertEqual(len(mapping), count)
        self.assertEqual(len(files), count)
        self.assertEqual(usage_query.call_count, 1)
        self.assertEqual(file_query.call_count, 1)

        over_limit_id = str(uuid4())
        page.payload['embedded_images'].append(
            {'id': over_limit_id, 'asset_id': str(uuid4())})
        page.payload['layout'].append(
            {'kind': 'image', 'image_id': over_limit_id})
        with patch(
                'content.public_shared.AssetUsage.objects.select_related') as usage_query, patch(
                'content.public_shared.AssetFile.objects.filter') as file_query:
            with self.assertRaises(PublicUnavailable):
                PublicSharedHost._standalone_media(page)
        usage_query.assert_not_called()
        file_query.assert_not_called()

        page.payload['embedded_images'].pop()
        page.payload['layout'].pop()
        with patch(
                'content.public_shared.MAX_STANDALONE_MEDIA_FILES', count - 1), patch(
                'content.public_shared.AssetUsage.objects.select_related') as usage_query, patch(
                'content.public_shared.AssetFile.objects.filter') as file_query:
            usage_query.return_value.filter.return_value.order_by.return_value = usage_rows
            file_query.return_value.order_by.return_value = file_rows
            with self.assertRaises(PublicUnavailable):
                PublicSharedHost._standalone_media(page)

    def test_pimg_010_http_boundary_64_files_and_65_closed_before_open(self):
        with self.candidate():
            self.apply_text('header', 'PRODUCTION-HEADER')
            self.apply_text('footer', 'PRODUCTION-FOOTER')
            assets = [self.clone_public_asset() for _index in range(65)]
            _page, route, _revision = self.create_many_image_page(
                assets[:64], name='boundary-64', target='/boundary-64/',
                position=60)
            accepted = self.anonymous.get(route.target)
            source = accepted.content.decode()
            self.assertEqual(accepted.status_code, 200)
            self.assertEqual(source.count('<figure'), 64)
            self.assertEqual(source.count('?page='), 64)
            for asset in assets[:64]:
                file = asset.files.get(kind=AssetFile.Kind.MAIN)
                self.assertIn('/public-media/%s/' % file.pk, source)

            _over_page, over_route, _revision = self.create_many_image_page(
                assets, name='boundary-65', target='/boundary-65/',
                position=61)
            with patch('shared_content.public._open_media') as media_open:
                denied = self.anonymous.get(over_route.target)
            self.assertEqual(denied.status_code, 503)
            self.assertEqual(denied['Cache-Control'], 'no-store')
            self.assertNotIn(b'BOUNDARY-INTRO', denied.content)
            self.assertNotIn(b'BOUNDARY-MAIN', denied.content)
            for asset in assets:
                file = asset.files.get(kind=AssetFile.Kind.MAIN)
                self.assertNotIn(str(file.pk).encode(), denied.content)
            media_open.assert_not_called()

            _hero_page, hero_route, _revision = self.create_many_image_page(
                assets[:63], main_asset=assets[63],
                page_kind=Page.Kind.SERVICE, name='hero-boundary-64',
                target='/hero-boundary-64/', position=62)
            hero_accepted = self.anonymous.get(hero_route.target)
            hero_source = hero_accepted.content.decode()
            self.assertEqual(hero_accepted.status_code, 200)
            self.assertEqual(hero_source.count('class="public-hero '), 1)
            self.assertEqual(hero_source.count('<figure'), 63)
            self.assertEqual(hero_source.count('?page='), 64)

            _hero_over_page, hero_over_route, _revision = self.create_many_image_page(
                assets[:64], main_asset=assets[64],
                page_kind=Page.Kind.SERVICE, name='hero-boundary-65',
                target='/hero-boundary-65/', position=63)
            with patch('shared_content.public._open_media') as media_open:
                hero_denied = self.anonymous.get(hero_over_route.target)
            self.assertEqual(hero_denied.status_code, 503)
            self.assertEqual(hero_denied['Cache-Control'], 'no-store')
            self.assertNotIn(b'BOUNDARY-INTRO', hero_denied.content)
            self.assertNotIn(b'BOUNDARY-MAIN', hero_denied.content)
            media_open.assert_not_called()

    def test_hero_main_image_context_kind_and_intro_structure(self):
        with self.candidate():
            self.apply_text('header', 'PRODUCTION-HEADER')
            self.apply_text('footer', 'PRODUCTION-FOOTER')
            asset = self.clone_public_asset()
            file = asset.files.get(kind=AssetFile.Kind.MAIN)
            long_intro = (
                '<p>HERO-FIRST</p>'
                + ''.join('<p>Длинный разрешённый абзац %s.</p>' % index
                          for index in range(24))
                + '<ul><li>Первый пункт</li><li>HERO-LAST</li></ul>')
            page, route, _revision = self.create_public_page(
                name='service-hero', target='/service-hero/', position=64,
                image_asset=asset, image_mode='main',
                page_kind=Page.Kind.SERVICE, intro_text=long_intro)
            url = '/public-media/%s/?%s' % (
                file.pk, urlencode((('page', str(page.pk)),
                                     ('slot', 'main_image'))))
            response = self.anonymous.get(route.target)
            source = response.content.decode()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(source.count('class="public-hero '), 1)
            self.assertIn(url.replace('&', '&amp;'), source)
            self.assertIn('alt="&lt;PUBLIC-ALT&gt;"', source)
            self.assertEqual(source.count('HERO-FIRST'), 1)
            self.assertEqual(source.count('HERO-LAST'), 1)
            self.assertIn('<ul><li>Первый пункт</li><li>HERO-LAST</li></ul>',
                          source)
            self.assertLess(source.index('HERO-FIRST'),
                            source.index('PUBLIC-MAIN'))
            media = self.anonymous.get(url)
            self.assertEqual(media.status_code, 200)
            self.body(media)

            for index, page_kind in enumerate(
                    (Page.Kind.ARTICLE, Page.Kind.WASH), start=65):
                denied_page, denied_route, _revision = self.create_public_page(
                    name='non-hero-' + page_kind,
                    target='/non-hero-%s/' % index, position=index,
                    image_asset=asset, image_mode='main',
                    page_kind=page_kind)
                denied_url = '/public-media/%s/?%s' % (
                    file.pk, urlencode((('page', str(denied_page.pk)),
                                         ('slot', 'main_image'))))
                denied_page_response = self.anonymous.get(denied_route.target)
                self.assertEqual(denied_page_response.status_code, 200)
                self.assertNotIn(b'public-hero', denied_page_response.content)
                self.assertNotIn(str(file.pk).encode(),
                                 denied_page_response.content)
                self.assertEqual(
                    self.anonymous.get(denied_url).status_code, 404)

            for index, mode in enumerate(('duplicate', 'protected'), start=67):
                bad_page, bad_route, revision = self.create_public_page(
                    name='bad-hero-' + mode,
                    target='/bad-hero-%s/' % mode, position=index,
                    image_asset=asset, image_mode='main',
                    page_kind=Page.Kind.SERVICE_SECTION)
                payload = dict(revision.payload)
                layout = [dict(node) for node in payload['layout']]
                if mode == 'duplicate':
                    layout.append({
                        'id': str(uuid4()), 'kind': 'text',
                        'field': 'intro_text', 'protected_nodes': []})
                else:
                    reference_id = str(uuid4())
                    fingerprint = 'e' * 64
                    layout[0] = {
                        **layout[0],
                        'protected_nodes': [{
                            'id': str(uuid4()),
                            'reference_id': reference_id,
                            'fingerprint': fingerprint}]}
                    layout.append({
                        'id': str(uuid4()), 'kind': 'protected_ref',
                        'reference_id': reference_id,
                        'fingerprint': fingerprint})
                payload['layout'] = layout
                raw = models.QuerySet(model=PageRevision)
                raw.filter(pk=revision.pk).update(
                    payload=payload, payload_hash=schema.digest(payload))
                bad_url = '/public-media/%s/?%s' % (
                    file.pk, urlencode((('page', str(bad_page.pk)),
                                         ('slot', 'main_image'))))
                failed = self.anonymous.get(bad_route.target)
                self.assertEqual(failed.status_code, 503)
                self.assertNotIn(b'PUBLIC-INTRO', failed.content)
                self.assertNotIn(str(file.pk).encode(), failed.content)
                self.assertEqual(self.anonymous.get(bad_url).status_code, 404)

    def test_pimg_exact_kind_binding_and_legacy_mime(self):
        with self.candidate():
            self.apply_text('header', 'PRODUCTION-HEADER')
            self.apply_text('footer', 'PRODUCTION-FOOTER')
            png = base64.b64decode(PNG, validate=True)
            legacy = self.create_legacy_public_asset(png)
            page, route, _revision = self.create_public_page(
                name='legacy-png', target='/legacy-png/', position=35,
                image_asset=legacy)
            file = legacy.files.get(kind=AssetFile.Kind.LEGACY_PUBLIC)
            slot = 'embedded:71de8370-3105-5209-a189-82bb243b0191'
            url = '/public-media/%s/?%s' % (
                file.pk, urlencode((('page', str(page.pk)), ('slot', slot))))
            rendered = self.anonymous.get(route.target)
            media = self.anonymous.get(url)
            self.assertEqual(rendered.status_code, 200)
            self.assertEqual(media.status_code, 200)
            self.assertEqual(media['Content-Type'], 'image/png')
            self.body(media)

            webp_source = self.asset.files.get(kind=AssetFile.Kind.MAIN)
            with MediaStorage().open_verified(
                    webp_source.key,
                    {'sha256': webp_source.sha256,
                     'byte_size': webp_source.byte_size}) as source:
                webp = source.read()
            legacy_webp = self.create_legacy_public_asset(webp, suffix='webp')
            webp_page, webp_route, _revision = self.create_public_page(
                name='legacy-webp', target='/legacy-webp/', position=36,
                image_asset=legacy_webp)
            webp_file = legacy_webp.files.get(
                kind=AssetFile.Kind.LEGACY_PUBLIC)
            webp_url = '/public-media/%s/?%s' % (
                webp_file.pk, urlencode((('page', str(webp_page.pk)),
                                         ('slot', slot))))
            self.assertEqual(
                self.anonymous.get(webp_route.target).status_code, 503)
            self.assertEqual(self.anonymous.get(webp_url).status_code, 503)

            swapped = self.clone_public_asset()
            swapped_page, swapped_route, _revision = self.create_public_page(
                name='swapped-kind', target='/swapped-kind/', position=37,
                image_asset=swapped)
            swapped_file = swapped.files.get(kind=AssetFile.Kind.MAIN)
            models.QuerySet(model=Asset).filter(pk=swapped.pk).update(
                is_legacy=True)
            swapped_url = '/public-media/%s/?%s' % (
                swapped_file.pk, urlencode((('page', str(swapped_page.pk)),
                                             ('slot', slot))))
            self.assertEqual(
                self.anonymous.get(swapped_route.target).status_code, 503)
            self.assertEqual(self.anonymous.get(swapped_url).status_code, 404)

    def test_pimg_context_uuid_errors_and_database_failure_stay_distinct(self):
        with self.candidate():
            self.apply_text('header', 'PRODUCTION-HEADER')
            self.apply_text('footer', 'PRODUCTION-FOOTER')
            asset = self.clone_public_asset()
            page, _route, _revision = self.create_public_page(
                name='uuid-errors', target='/uuid-errors/', position=38,
                image_asset=asset)
            file = asset.files.get(kind=AssetFile.Kind.MAIN)
            slot = 'embedded:71de8370-3105-5209-a189-82bb243b0191'
            malformed = '/public-media/%s/?%s' % (
                file.pk, urlencode((('page', 'not-a-uuid'), ('slot', slot))))
            with patch('shared_content.public._capture_media') as capture:
                response = self.anonymous.get(malformed)
            self.assertEqual(response.status_code, 404)
            capture.assert_not_called()

            valid = '/public-media/%s/?%s' % (
                file.pk, urlencode((('page', str(page.pk)), ('slot', slot))))
            with patch('shared_content.public._capture_media',
                       side_effect=DatabaseError('synthetic database failure')):
                response = self.anonymous.get(valid)
            self.assertEqual(response.status_code, 503)

    def test_pimg_media_recapture_disappearance_and_drift_close_503(self):
        with self.candidate():
            self.apply_text('header', 'PRODUCTION-HEADER')
            self.apply_text('footer', 'PRODUCTION-FOOTER')
            slot = 'embedded:71de8370-3105-5209-a189-82bb243b0191'
            cases = []
            for index, name in enumerate(('unpublish', 'detach', 'descriptor')):
                asset = self.clone_public_asset()
                page, _route, _revision = self.create_public_page(
                    name='media-' + name, target='/media-' + name + '/',
                    position=50 + index, image_asset=asset)
                file = asset.files.get(kind=AssetFile.Kind.MAIN)
                url = '/public-media/%s/?%s' % (
                    file.pk, urlencode((('page', str(page.pk)), ('slot', slot))))
                if name == 'unpublish':
                    mutation = lambda page_id=page.pk: models.QuerySet(
                        model=Page).filter(pk=page_id).update(is_published=False)
                elif name == 'detach':
                    mutation = lambda page_id=page.pk: media_services.detach(
                        kind='current_page', consumer_id=page_id, slot=slot)
                else:
                    mutation = lambda file_id=file.pk: models.QuerySet(
                        model=AssetFile).filter(pk=file_id).update(
                            sha256='0' * 64)
                cases.append((name, url, mutation))

            for name, url, mutation in cases:
                fired = [False]

                def mutate_once(phase):
                    if phase == 'media_before_recheck' and not fired[0]:
                        fired[0] = True
                        mutation()

                with self.subTest(race=name), patch(
                        'shared_content.public._read_boundary',
                        side_effect=mutate_once):
                    response = self.anonymous.get(url)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response['Cache-Control'], 'no-store')

    def test_pimg_context_rejects_wrong_hidden_preview_protected_and_orphan(self):
        with self.candidate():
            self.apply_text('header', 'PRODUCTION-HEADER')
            self.apply_text('footer', 'PRODUCTION-FOOTER')
            asset = self.clone_public_asset()
            file = asset.files.get(kind=AssetFile.Kind.MAIN)
            image_id = '71de8370-3105-5209-a189-82bb243b0191'
            slot = 'embedded:' + image_id
            pages = {}
            for index, mode in enumerate(('standalone', 'standalone-second', 'orphan',
                                          'protected', 'preview')):
                actual_mode = 'standalone' if mode == 'standalone-second' else mode
                pages[mode] = self.create_public_page(
                    name=mode, target='/' + mode + '/', position=20 + index,
                    image_asset=asset, image_mode=actual_mode)
            hidden = self.create_public_page(
                name='hidden-image', target='/hidden-image/', position=30,
                published=False, image_asset=asset)
            wrong = self.create_public_page(
                name='wrong-page', target='/wrong-page/', position=31)
            old = self.create_public_page(
                name='old-image', target='/old-image/', position=32,
                image_asset=asset)
            replacement_payload = schema.snapshot_v1(
                old[0].kind, h1='PUBLIC-H1', title='PUBLIC-TITLE',
                intro_text='<p>PUBLIC-INTRO</p>', main_text='<p>PUBLIC-MAIN-NEW</p>',
                layout=[
                    {'id': '71de8370-3105-5209-a189-82bb243b0201', 'kind': 'text',
                     'field': 'intro_text', 'protected_nodes': []},
                    {'id': '71de8370-3105-5209-a189-82bb243b0202', 'kind': 'text',
                     'field': 'main_text', 'protected_nodes': []}]).data()
            replacement = PageRevision.objects.create(
                page=old[0], sequence=2, schema_version=schema.SCHEMA,
                payload=replacement_payload, payload_hash=schema.digest(replacement_payload),
                kind=PageRevision.Kind.AUTOMATIC, author_id=1)
            models.QuerySet(model=PageContentState).filter(page=old[0]).update(
                current_revision=replacement, sequence=2)
            media_services.detach(
                kind='current_page', consumer_id=old[0].pk, slot=slot)

            def page_url(page, selected_slot=slot):
                query = urlencode((('page', str(page.pk)), ('slot', selected_slot)))
                return '/public-media/%s/?%s' % (file.pk, query)

            self.assertEqual(self.anonymous.get(page_url(pages['standalone'][0])).status_code, 200)
            self.assertEqual(self.anonymous.get(page_url(pages['standalone-second'][0])).status_code, 200)
            self.assertEqual(self.anonymous.get(page_url(pages['orphan'][0])).status_code, 404)
            self.assertEqual(self.anonymous.get(page_url(pages['protected'][0])).status_code, 404)
            self.assertEqual(self.anonymous.get(
                page_url(pages['preview'][0], 'preview_image')).status_code, 404)
            self.assertEqual(self.anonymous.get(page_url(hidden[0])).status_code, 404)
            self.assertEqual(self.anonymous.get(page_url(wrong[0])).status_code, 404)
            self.assertEqual(self.anonymous.get(page_url(old[0])).status_code, 404)
            self.assertEqual(self.anonymous.get(
                page_url(pages['orphan'][0]) + '&extra=1').status_code, 404)
            protected_page = self.anonymous.get(pages['protected'][1].target)
            self.assertEqual(protected_page.status_code, 503)
            self.assertNotIn(str(file.pk).encode(), protected_page.content)

    def test_pimg_corrupt_physical_file_closes_page_before_partial_html(self):
        with self.candidate():
            self.apply_text('header', 'PRODUCTION-HEADER')
            self.apply_text('footer', 'PRODUCTION-FOOTER')
            asset = self.clone_public_asset()
            page, route, _revision = self.create_public_page(
                image_asset=asset)
            file = asset.files.get(kind=AssetFile.Kind.MAIN)
            slot = 'embedded:71de8370-3105-5209-a189-82bb243b0191'
            url = '/public-media/%s/?%s' % (
                file.pk, urlencode((('page', str(page.pk)), ('slot', slot))))
            actual = shared_public._open_media

            def fail_page_file(descriptor):
                if descriptor['assetId'] == str(asset.pk):
                    raise OSError('synthetic page file failure')
                return actual(descriptor)

            with patch('shared_content.public._open_media', side_effect=fail_page_file):
                response = self.anonymous.get(route.target)
                media = self.anonymous.get(url)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response['Cache-Control'], 'no-store')
            self.assertNotIn(b'PUBLIC-INTRO', response.content)
            self.assertNotIn(str(file.pk).encode(), response.content)
            self.assertEqual(media.status_code, 503)
            self.assertEqual(media['Cache-Control'], 'no-store')

    def test_pimg_revision_publication_usage_and_descriptor_drift_close(self):
        with self.candidate():
            self.apply_text('header', 'PRODUCTION-HEADER')
            self.apply_text('footer', 'PRODUCTION-FOOTER')

            asset = self.clone_public_asset()
            page, route, revision = self.create_public_page(
                name='revision-race', target='/revision-race/', position=40,
                image_asset=asset)
            changed_payload = dict(revision.payload)
            changed_payload['main_text'] = '<p>RACE-SECOND-CANARY</p>'
            changed = PageRevision.objects.create(
                page=page, sequence=2, schema_version=schema.SCHEMA,
                payload=changed_payload, payload_hash=schema.digest(changed_payload),
                kind=PageRevision.Kind.AUTOMATIC, author_id=1)
            turns = iter((changed, revision))

            def toggle_revision(phase):
                if phase == 'files_read':
                    selected = next(turns)
                    models.QuerySet(model=PageContentState).filter(page=page).update(
                        current_revision=selected,
                        sequence=2 if selected.pk == changed.pk else 1)

            with patch('shared_content.public._read_boundary', side_effect=toggle_revision):
                response = self.anonymous.get(route.target)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn(b'PUBLIC-INTRO', response.content)
            self.assertNotIn(b'RACE-SECOND-CANARY', response.content)

            cases = []
            for index, name in enumerate(('publication', 'usage', 'descriptor')):
                race_asset = self.clone_public_asset()
                race_page, race_route, _race_revision = self.create_public_page(
                    name=name + '-race', target='/' + name + '-race/',
                    position=41 + index, image_asset=race_asset)
                race_file = race_asset.files.get(kind=AssetFile.Kind.MAIN)
                if name == 'publication':
                    mutation = lambda page_id=race_page.pk: models.QuerySet(
                        model=Page).filter(pk=page_id).update(is_published=False)
                elif name == 'usage':
                    mutation = lambda page_id=race_page.pk: media_services.detach(
                        kind='current_page', consumer_id=page_id,
                        slot='embedded:71de8370-3105-5209-a189-82bb243b0191')
                else:
                    mutation = lambda file_id=race_file.pk: models.QuerySet(
                        model=AssetFile).filter(pk=file_id).update(sha256='0' * 64)
                cases.append((name, race_route, race_file, mutation))

            for name, race_route, race_file, mutation in cases:
                fired = [False]

                def change_once(phase):
                    if phase == 'files_read' and not fired[0]:
                        fired[0] = True
                        mutation()

                with self.subTest(race=name), patch(
                        'shared_content.public._read_boundary', side_effect=change_once):
                    response = self.anonymous.get(race_route.target)
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response['Cache-Control'], 'no-store')
                    self.assertNotIn(b'PUBLIC-INTRO', response.content)
                    self.assertNotIn(str(race_file.pk).encode(), response.content)
