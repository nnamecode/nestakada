from html import escape
import base64
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder
from media_library.storage import MediaStorage
from page_editor.test_media_http import PNG
from page_versions import schema
from page_versions.models import PageContentState, PageRevision

from .models import Page, Route
from .public_gallery import (
    ALBUM_TARGETS, PAGE2_TARGET, ROOT_TARGET, page1_redirect_target,
    parse_gallery_target, project_gallery,
)
from .public_read import PublicNotFound, PublicUnavailable, resolve_target
from .public_shared import PublicSharedHost


def fake_shared(*, capture_host, media_url, static_url):
    from shared_content.public import RenderedShared
    host = capture_host()
    static_url('public-shared.css', 'a' * 64)
    static_url('public-shared.js', 'b' * 64)
    links = ''.join('<a href="%s">%s</a>' % (
        escape(item.url, quote=True), escape(item.label))
        for item in host.navigation)
    return RenderedShared(
        '<header><nav>' + links + '</nav></header>',
        '<footer>Test footer</footer>', '"gallery-test"', 'gallery-test')


def fake_shared_atomic(**kwargs):
    with transaction.atomic():
        return fake_shared(**kwargs)


def raw(model):
    return models.QuerySet(model=model, using='default')


class Dev10GalleryPublicProjectionTests(TestCase):
    def setUp(self):
        shared = patch('content.public_views.render_shared', side_effect=fake_shared)
        shared.start()
        self.addCleanup(shared.stop)
        self.folder = MediaFolder.objects.create(path='gallery/public-test')
        self.root = self.page(
            name='Галерея', target=ROOT_TARGET, kind=Page.Kind.GALLERY,
            position=0, payload=schema.snapshot_v1(
                Page.Kind.GALLERY, h1='Галерея', title='Галерея').data())
        Route.objects.create(
            page=self.root, target=PAGE2_TARGET, kind=Route.Kind.ALIAS,
            is_legacy=True)
        self.albums = []
        for position, target in enumerate(ALBUM_TARGETS):
            image_id = str(uuid4())
            block_id = str(uuid4())
            asset_id = uuid4()
            file_id = uuid4()
            payload = schema.snapshot_v1(
                Page.Kind.ALBUM, h1='Album ' + str(position),
                title='Album ' + str(position), main_text='<p>Описание</p>',
                embedded_images=[{
                    'id': image_id, 'asset_id': str(asset_id),
                    'alt': 'Фото ' + str(position), 'alignment': 'center',
                    'width_px': None, 'height_px': None,
                }], layout=[
                    {'id': str(uuid4()), 'kind': 'text',
                     'field': 'intro_text', 'protected_nodes': []},
                    {'id': str(uuid4()), 'kind': 'text',
                     'field': 'main_text', 'protected_nodes': []},
                    {'id': block_id, 'kind': 'image', 'image_id': image_id},
                ]).data()
            album = self.page(
                name='Album ' + str(position), target=target,
                kind=Page.Kind.ALBUM, position=position,
                parent=self.root, payload=payload)
            raw(Asset).bulk_create([Asset(
                id=asset_id, folder=self.folder, status=Asset.Status.READY,
                provenance='DEV10 public test', is_legacy=True,
                source_url='https://estakada-service.ru/assets/images/resources/'
                           + str(position) + '.jpg',
                source_sha256=('%064x' % (position + 1)))])
            raw(AssetFile).bulk_create([AssetFile(
                id=file_id, asset_id=asset_id,
                kind=AssetFile.Kind.LEGACY_PUBLIC,
                key='img/' + str(asset_id) + '/original.jpg',
                sha256=('%064x' % (position + 1)), byte_size=position + 1)])
            AssetUsage.objects.create(
                asset_id=asset_id, kind=AssetUsage.Kind.CURRENT_PAGE,
                consumer_id=album.pk, slot='embedded:' + image_id)
            self.albums.append(album)

    def page(self, *, name, target, kind, position, payload,
             parent=None, published=True):
        page = Page.objects.create(
            name=name, kind=kind, parent=parent, position=position,
            is_published=published)
        Route.objects.create(
            page=page, target=target, kind=Route.Kind.PRIMARY,
            is_legacy=True)
        revision = PageRevision.objects.create(
            page=page, sequence=1, schema_version=schema.SCHEMA,
            payload=payload, payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(
            page=page, current_revision=revision, sequence=1)
        return page

    def assert_not_found(self, action):
        with self.assertRaises(PublicNotFound):
            action()

    def assert_unavailable(self, action):
        with self.assertRaises(PublicUnavailable):
            action()

    def projection(self, target):
        request = parse_gallery_target(target)
        return project_gallery(resolve_target(request.base_target), request)

    def set_root_preview(self, asset, *, alt='Gallery preview'):
        state = PageContentState.objects.get(page=self.root)
        current = state.current_revision
        payload = dict(current.payload)
        payload['preview_image'] = {
            'asset_id': str(asset.pk), 'alt': alt, 'alignment': 'center',
            'width_px': 1200, 'height_px': 700,
        }
        revision = PageRevision.objects.create(
            page=self.root, sequence=current.sequence + 1,
            schema_version=schema.SCHEMA, payload=payload,
            payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.AUTOMATIC, author_id=1)
        raw(PageContentState).filter(pk=state.pk).update(
            current_revision=revision, sequence=state.sequence + 1)
        AssetUsage.objects.create(
            asset=asset, kind=AssetUsage.Kind.CURRENT_PAGE,
            consumer_id=self.root.pk, slot='preview_image')
        return revision

    def test_g10_public_001_closed_query_parser_and_page1_redirect(self):
        self.assertEqual(page1_redirect_target(ROOT_TARGET + '?page=1'),
                         ROOT_TARGET)
        self.assertIsNone(page1_redirect_target(ROOT_TARGET + '?page=01'))
        self.assertEqual(parse_gallery_target(ROOT_TARGET).page, 1)
        self.assertEqual(parse_gallery_target(PAGE2_TARGET).page, 2)
        selected = ALBUM_TARGETS[0].removeprefix(ROOT_TARGET)
        self.assertEqual(parse_gallery_target(
            ROOT_TARGET + '?album=' + selected).selected_target,
            ALBUM_TARGETS[0])
        selected2 = ALBUM_TARGETS[10].removeprefix(ROOT_TARGET)
        self.assertEqual(parse_gallery_target(
            PAGE2_TARGET + '&album=' + selected2).selected_target,
            ALBUM_TARGETS[10])
        for target in (
                ROOT_TARGET + '?page=01', ROOT_TARGET + '?page=2&x=1',
                ROOT_TARGET + '?album=', ROOT_TARGET + '?album=unknown',
                ROOT_TARGET + '?album=' + selected + '&page=2',
                ROOT_TARGET + '?page=2&album=' + selected):
            with self.subTest(target=target):
                self.assert_not_found(lambda target=target:
                                      parse_gallery_target(target))
        self.assertIsNone(parse_gallery_target('/other/'))

    def test_g10_public_002_root_page2_and_modal_are_exact_bounded(self):
        root = self.projection(ROOT_TARGET)
        self.assertEqual(len(root.albums), 17)
        self.assertEqual(tuple(album.target for album in root.albums),
                         ALBUM_TARGETS)
        self.assertEqual(len(root.files), 17)
        page2 = self.projection(PAGE2_TARGET)
        self.assertEqual(len(page2.albums), 7)
        self.assertEqual(tuple(album.target for album in page2.albums),
                         ALBUM_TARGETS[10:])
        selected = ALBUM_TARGETS[4].removeprefix(ROOT_TARGET)
        modal = self.projection(ROOT_TARGET + '?album=' + selected)
        self.assertEqual(modal.selected.target, ALBUM_TARGETS[4])
        self.assertEqual(len(modal.files), 17)

    def test_g10_public_003_hidden_album_is_omitted_and_not_selectable(self):
        raw(Page).filter(pk=self.albums[0].pk).update(is_published=False)
        projected = self.projection(ROOT_TARGET)
        self.assertEqual(len(projected.albums), 16)
        selected = ALBUM_TARGETS[0].removeprefix(ROOT_TARGET)
        self.assert_not_found(
            lambda: self.projection(ROOT_TARGET + '?album=' + selected))
        response = self.client.get(ROOT_TARGET + '?album=' + selected)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b'Album 0', response.content)

    def test_g10_public_004_extra_child_and_missing_usage_close_unavailable(self):
        Page.objects.create(
            name='Extra', kind=Page.Kind.ALBUM, parent=self.root,
            position=17, is_published=False)
        self.assert_unavailable(lambda: self.projection(ROOT_TARGET))
        failed = self.client.get(ROOT_TARGET)
        self.assertEqual(failed.status_code, 503)
        self.assertNotIn(b'public-gallery-card', failed.content)
        raw(Page).filter(parent=self.root, position=17).delete()
        usage = AssetUsage.objects.filter(
            consumer_id=self.albums[0].pk).first()
        raw(AssetUsage).filter(pk=usage.pk).delete()
        self.assert_unavailable(lambda: self.projection(ROOT_TARGET))
        failed = self.client.get(ROOT_TARGET)
        self.assertEqual(failed.status_code, 503)
        self.assertNotIn(b'public-gallery-card', failed.content)

    def test_g10_public_005_projection_requires_coherent_transaction(self):
        request = parse_gallery_target(ROOT_TARGET)
        root = resolve_target(ROOT_TARGET)
        with self.captureOnCommitCallbacks(execute=True):
            pass
        # TestCase itself owns a transaction; the explicit guard is covered by
        # temporarily exposing the connection state rather than opening a new API.
        from unittest.mock import patch
        with patch('content.public_gallery.connection.in_atomic_block', False):
            self.assert_unavailable(lambda: project_gallery(root, request))

    def test_g10_public_006_shared_host_stamp_carries_bounded_gallery_files(self):
        selected = ALBUM_TARGETS[3].removeprefix(ROOT_TARGET)
        host = PublicSharedHost(ROOT_TARGET + '?album=' + selected)
        context = host.capture()
        self.assertEqual(len(context.media), 17)
        self.assertEqual(host.gallery_body().selected.target, ALBUM_TARGETS[3])
        self.assertEqual(len(host.gallery_body().albums), 17)
        self.assertEqual(len({item.id for item in context.media}), 17)

    @override_settings(MEDIA_LIBRARY_ROOT='/tmp/dev11-gallery-media')
    def test_s11_gallery_preview_is_og_contextual_and_deduplicated(self):
        usage = AssetUsage.objects.get(
            consumer_id=self.albums[0].pk,
            kind=AssetUsage.Kind.CURRENT_PAGE)
        file = AssetFile.objects.get(asset_id=usage.asset_id)
        body = base64.b64decode(PNG, validate=True)
        key = 'img/' + str(usage.asset_id) + '/dev11-preview.jpg'
        manifest = MediaStorage().write_new(key, body)
        raw(AssetFile).filter(pk=file.pk).update(
            key=key, sha256=manifest['sha256'],
            byte_size=manifest['byte_size'])
        self.set_root_preview(usage.asset, alt='<Gallery preview>')
        host = PublicSharedHost(ROOT_TARGET)
        context = host.capture()
        self.assertEqual(len(context.media), 17)
        self.assertEqual(len({item.id for item in context.media}), 17)
        seo_media, wash_peer_eligible = host.seo_body()
        self.assertEqual(seo_media.file_id, str(file.pk))
        self.assertFalse(wash_peer_eligible)

        response = self.client.get(ROOT_TARGET)
        self.assertEqual(response.status_code, 200)
        query = urlencode((('page', str(self.root.pk)),
                           ('slot', 'preview_image')))
        expected = '/public-media/%s/?%s' % (file.pk, query)
        self.assertContains(response, 'property="og:image"')
        self.assertContains(response, expected.replace('&', '&amp;'))

    def test_s11_gallery_preview_and_gallery_share_one_unique_file_cap(self):
        asset_id, file_id = uuid4(), uuid4()
        asset = Asset(
            id=asset_id, folder=self.folder, status=Asset.Status.READY,
            provenance='DEV11 gallery preview cap', is_legacy=True,
            source_url='https://estakada-service.ru/assets/preview.jpg',
            source_sha256='f' * 64)
        raw(Asset).bulk_create([asset])
        raw(AssetFile).bulk_create([AssetFile(
            id=file_id, asset=asset, kind=AssetFile.Kind.LEGACY_PUBLIC,
            key='img/' + str(asset_id) + '/preview.jpg',
            sha256='f' * 64, byte_size=1)])
        self.set_root_preview(asset)
        with patch('content.public_shared.MAX_STANDALONE_MEDIA_FILES', 17):
            self.assert_unavailable(
                lambda: PublicSharedHost(ROOT_TARGET).capture())
            response = self.client.get(ROOT_TARGET)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(str(file_id).encode(), response.content)

    def test_g10_public_007_http_page1_and_invalid_queries_close_exactly(self):
        moved = self.client.get(ROOT_TARGET + '?page=1')
        self.assertEqual(moved.status_code, 302)
        self.assertEqual(moved['Location'], ROOT_TARGET)
        self.assertEqual(moved['Cache-Control'], 'no-cache')
        moved_head = self.client.head(ROOT_TARGET + '?page=1')
        self.assertEqual(moved_head.status_code, 302)
        self.assertEqual(moved_head['Location'], ROOT_TARGET)
        refused = self.client.post(ROOT_TARGET + '?page=1')
        self.assertEqual(refused.status_code, 405)
        self.assertEqual(refused['Allow'], 'GET, HEAD')
        for target in (
                ROOT_TARGET + '?page=01', ROOT_TARGET + '?album=unknown',
                ROOT_TARGET + '?x=1',
                ALBUM_TARGETS[0] + '?album=ford-mondeo'):
            with self.subTest(target=target):
                response = self.client.get(target)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response['Cache-Control'], 'no-store')

    def test_g10_public_008_server_rendered_catalog_page2_modal_and_album(self):
        root = self.client.get(ROOT_TARGET)
        self.assertEqual(root.status_code, 200)
        self.assertEqual(root.content.count(b'class="public-gallery-card"'), 17)
        self.assertEqual(root.content.count(b'src="/static/public-gallery.js"'), 1)
        positions = [root.content.index(target.encode()) for target in ALBUM_TARGETS]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn(b'<script type="application/json"', root.content)
        page2 = self.client.get(PAGE2_TARGET)
        self.assertEqual(page2.status_code, 200)
        self.assertNotIn('Location', page2)
        self.assertEqual(page2.content.count(b'class="public-gallery-card"'), 7)
        self.assertContains(page2, 'Все выполненные работы')
        selected = ALBUM_TARGETS[2].removeprefix(ROOT_TARGET)
        modal = self.client.get(ROOT_TARGET + '?album=' + selected)
        self.assertEqual(modal.status_code, 200)
        self.assertContains(modal, 'data-gallery-dialog')
        self.assertContains(modal, 'aria-labelledby="public-gallery-dialog-title"')
        self.assertEqual(modal.content.count(b'data-gallery-photo'), 1)
        album = self.client.get(ALBUM_TARGETS[2])
        self.assertEqual(album.status_code, 200)
        self.assertNotContains(album, '/static/public-gallery.js')
        self.assertContains(album, 'class="public-gallery-album"')
        self.assertContains(album, 'Все работы')
        self.assertEqual(album.content.count(b'<figure>'), 1)

    def test_g10_public_009_gallery_stamp_changes_with_every_rendered_field(self):
        host = PublicSharedHost(ROOT_TARGET)
        first = host.capture().stamp
        raw(Page).filter(pk=self.albums[0].pk).update(name='Changed album name')
        second = PublicSharedHost(ROOT_TARGET).capture().stamp
        self.assertNotEqual(first, second)
        state = PageContentState.objects.select_related('current_revision').get(
            page=self.albums[0])
        payload = dict(state.current_revision.payload)
        payload['main_text'] = '<p>Changed safe description</p>'
        raw(PageRevision).filter(pk=state.current_revision_id).update(
            payload=payload, payload_hash=schema.digest(payload))
        third = PublicSharedHost(ROOT_TARGET).capture().stamp
        self.assertNotEqual(second, third)

    def test_g10_public_010_gallery_css_is_scoped_responsive_and_unclipped(self):
        from .public_views import STYLESHEET
        css = STYLESHEET.decode('utf-8')
        self.assertIn(
            '.public-gallery-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))',
            css)
        self.assertIn(
            '@media(max-width:1000px){.public-gallery-grid{grid-template-columns:repeat(3,minmax(0,1fr))}',
            css)
        self.assertIn(
            '@media(max-width:700px){.public-gallery-grid{grid-template-columns:repeat(2,minmax(0,1fr))',
            css)
        self.assertIn('.public-gallery-stage>img{width:100%;height:100%;object-fit:contain}', css)
        gallery_css = css[css.index('.public-gallery-grid'):]
        self.assertNotIn('text-overflow:ellipsis', gallery_css)
        self.assertNotIn('white-space:nowrap', gallery_css.split('.public-gallery-dialog', 1)[0])

    def test_g10_public_011_fixed_viewer_asset_get_head_only_and_csp_local(self):
        from .public_views import GALLERY_SCRIPT
        response = self.client.get('/static/public-gallery.js')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, GALLERY_SCRIPT)
        self.assertEqual(response['Content-Type'], 'text/javascript; charset=utf-8')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        head = self.client.head('/static/public-gallery.js')
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b'')
        post = self.client.post('/static/public-gallery.js')
        self.assertEqual(post.status_code, 405)
        self.assertEqual(post['Allow'], 'GET, HEAD')
        root = self.client.get(ROOT_TARGET)
        self.assertIn("script-src 'self'", root['Content-Security-Policy'])
        source = GALLERY_SCRIPT.decode('utf-8')
        for forbidden in ('fetch(', 'XMLHttpRequest', 'localStorage',
                          'sessionStorage', 'eval(', 'innerHTML',
                          'insertAdjacentHTML', 'import('):
            self.assertNotIn(forbidden, source)


class Dev11GalleryMediaIntegrationTests(TransactionTestCase):
    def setUp(self):
        shared = patch(
            'content.public_views.render_shared', side_effect=fake_shared_atomic)
        shared.start()
        self.addCleanup(shared.stop)
        self.folder = MediaFolder.objects.create(path='gallery/dev11-media-test')
        self.root = self.page(
            name='Галерея', target=ROOT_TARGET, kind=Page.Kind.GALLERY,
            position=0, payload=schema.snapshot_v1(
                Page.Kind.GALLERY, h1='Галерея', title='Галерея').data())
        Route.objects.create(
            page=self.root, target=PAGE2_TARGET, kind=Route.Kind.ALIAS,
            is_legacy=True)
        self.albums = []
        for position, target in enumerate(ALBUM_TARGETS):
            image_id = str(uuid4())
            asset_id, file_id = uuid4(), uuid4()
            payload = schema.snapshot_v1(
                Page.Kind.ALBUM, h1='Album ' + str(position),
                title='Album ' + str(position),
                embedded_images=[{
                    'id': image_id, 'asset_id': str(asset_id),
                    'alt': 'Фото ' + str(position), 'alignment': 'center',
                    'width_px': None, 'height_px': None,
                }], layout=[
                    {'id': str(uuid4()), 'kind': 'text',
                     'field': 'intro_text', 'protected_nodes': []},
                    {'id': str(uuid4()), 'kind': 'text',
                     'field': 'main_text', 'protected_nodes': []},
                    {'id': str(uuid4()), 'kind': 'image',
                     'image_id': image_id},
                ]).data()
            album = self.page(
                name='Album ' + str(position), target=target,
                kind=Page.Kind.ALBUM, position=position,
                parent=self.root, payload=payload)
            raw(Asset).bulk_create([Asset(
                id=asset_id, folder=self.folder, status=Asset.Status.READY,
                provenance='DEV11 media integration', is_legacy=True,
                source_url='https://estakada-service.ru/assets/'
                           + str(position) + '.png',
                source_sha256=('%064x' % (position + 1)))])
            raw(AssetFile).bulk_create([AssetFile(
                id=file_id, asset_id=asset_id,
                kind=AssetFile.Kind.LEGACY_PUBLIC,
                key='img/' + str(asset_id) + '/original.png',
                sha256=('%064x' % (position + 1)), byte_size=position + 1)])
            AssetUsage.objects.create(
                asset_id=asset_id, kind=AssetUsage.Kind.CURRENT_PAGE,
                consumer_id=album.pk, slot='embedded:' + image_id)
            self.albums.append(album)

    def page(self, *, name, target, kind, position, payload,
             parent=None):
        page = Page.objects.create(
            name=name, kind=kind, parent=parent, position=position,
            is_published=True)
        Route.objects.create(
            page=page, target=target, kind=Route.Kind.PRIMARY,
            is_legacy=True)
        revision = PageRevision.objects.create(
            page=page, sequence=1, schema_version=schema.SCHEMA,
            payload=payload, payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(
            page=page, current_revision=revision, sequence=1)
        return page

    def set_root_preview(self, asset):
        state = PageContentState.objects.get(page=self.root)
        payload = dict(state.current_revision.payload)
        payload['preview_image'] = {
            'asset_id': str(asset.pk), 'alt': 'Gallery preview',
            'alignment': 'center', 'width_px': 1200, 'height_px': 700,
        }
        revision = PageRevision.objects.create(
            page=self.root, sequence=2, schema_version=schema.SCHEMA,
            payload=payload, payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.AUTOMATIC, author_id=1)
        raw(PageContentState).filter(pk=state.pk).update(
            current_revision=revision, sequence=2)
        AssetUsage.objects.create(
            asset=asset, kind=AssetUsage.Kind.CURRENT_PAGE,
            consumer_id=self.root.pk, slot='preview_image')

    @override_settings(MEDIA_LIBRARY_ROOT='/tmp/dev11-gallery-media-http')
    def test_s11_gallery_preview_contextual_media_is_public(self):
        usage = AssetUsage.objects.get(
            consumer_id=self.albums[0].pk,
            kind=AssetUsage.Kind.CURRENT_PAGE)
        file = AssetFile.objects.get(asset_id=usage.asset_id)
        body = base64.b64decode(PNG, validate=True)
        key = 'img/' + str(usage.asset_id) + '/dev11-preview.png'
        manifest = MediaStorage().write_new(key, body)
        raw(AssetFile).filter(pk=file.pk).update(
            key=key, sha256=manifest['sha256'],
            byte_size=manifest['byte_size'])
        self.set_root_preview(usage.asset)

        page_response = self.client.get(ROOT_TARGET)
        self.assertEqual(page_response.status_code, 200)
        query = urlencode((('page', str(self.root.pk)),
                           ('slot', 'preview_image')))
        expected = '/public-media/%s/?%s' % (file.pk, query)
        media_response = self.client.get(expected)
        self.assertEqual(media_response.status_code, 200)
        self.assertEqual(media_response['Content-Type'], 'image/png')
        media_response.close()
