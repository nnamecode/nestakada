from unittest.mock import patch
import hashlib
from urllib.parse import urlencode

from django.contrib.sessions.models import Session
from django.db import models
from django.test import Client, TransactionTestCase, override_settings

from audit.models import AuditEvent
from media_library import services as media_services
from media_library.models import Asset, AssetFile
from media_library.storage import MediaStorage
from page_versions import schema
from page_versions.models import PageContentState, PageRevision
from shared_content import public as shared_public
from shared_content import test_shared_reservation as reservation
from shared_content.models import SharedBlock, SharedRevision
from shared_content.storage import SharedStorage

from .models import Page, Route


@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PublicSharedPageTests(reservation.ReservationFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.anonymous = Client(enforce_csrf_checks=True, HTTP_HOST='localhost')

    def create_public_page(self, name='PUBLIC-PAGE', target='/public-page/', *,
                           position=10, published=True, image_asset=None,
                           image_mode='standalone'):
        page = Page.objects.create(
            name=name, kind=Page.Kind.ARTICLE, position=position,
            is_published=published)
        route = Route.objects.create(
            page=page, kind=Route.Kind.PRIMARY, target=target)
        image_id = '71de8370-3105-5209-a189-82bb243b0191'
        embedded, preview, protected = [], None, []
        layout = [
            {'id': '71de8370-3105-5209-a189-82bb243b0051', 'kind': 'text',
             'field': 'intro_text', 'protected_nodes': []}]
        if image_asset is not None:
            reference = {'asset_id': str(image_asset.pk), 'alt': '<PUBLIC-ALT>',
                         'alignment': 'right', 'width_px': 640, 'height_px': None}
            if image_mode == 'preview':
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
            intro_text='<p>PUBLIC-INTRO</p>',
            main_text='<p>PUBLIC-MAIN</p>', preview_image=preview,
            embedded_images=embedded, layout=layout).data()
        revision = PageRevision.objects.create(
            page=page, sequence=1, schema_version=schema.SCHEMA,
            payload=payload, payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(
            page=page, current_revision=revision, sequence=1)
        if image_asset is not None:
            slot = ('preview_image' if image_mode == 'preview'
                    else 'embedded:' + image_id)
            media_services.attach(
                asset_id=image_asset.pk, kind='current_page',
                consumer_id=page.pk, slot=slot)
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
