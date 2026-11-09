from unittest.mock import patch
from html import escape

from django.contrib.sessions.models import Session
from django.conf import settings
from django.db import DatabaseError, models
from django.test import TestCase

from audit.models import AuditEvent
from page_versions import schema
from page_versions.models import PageContentState, PageRevision

from .models import Page, Route


def fake_shared(*, capture_host, media_url, static_url):
    from shared_content.public import RenderedShared
    host = capture_host()
    static_url('public-shared.css', 'a' * 64)
    static_url('public-shared.js', 'b' * 64)
    links = ''.join(
        '<a href="%s"%s>%s</a>' % (
            escape(item.url, quote=True),
            ' aria-current="page"' if item.current else '',
            escape(item.label))
        for item in host.navigation)
    return RenderedShared(
        '<header><nav>' + links + '</nav></header>',
        '<footer>Test footer</footer>', '"test-shared"', 'test-shared')


def raw(model):
    return models.QuerySet(model=model, using='default')


class PublicHttpTests(TestCase):
    def setUp(self):
        super().setUp()
        shared = patch('content.public_views.render_shared', side_effect=fake_shared)
        shared.start()
        self.addCleanup(shared.stop)

    def page(self, name, target, *, published=True, route_kind=Route.Kind.PRIMARY,
             intro='<p>Intro</p>', main='<p>Main <strong>text</strong></p>',
             layout=None, price=None, embedded_images=None, position=0):
        page = Page.objects.create(
            name=name, kind=Page.Kind.ARTICLE, position=position,
            is_published=published)
        route = Route.objects.create(
            page=page, kind=route_kind, target=target,
            is_legacy='?' in target)
        payload = schema.snapshot_v1(
            page.kind, h1='H1 <safe>', title='Title <safe>',
            intro_text=intro, main_text=main, price=price,
            embedded_images=embedded_images,
            layout=layout if layout is not None else [
                {'id': '71de8370-3105-5209-a189-82bb243b0051', 'kind': 'text',
                 'field': 'intro_text', 'protected_nodes': []},
                {'id': '71de8370-3105-5209-a189-82bb243b0052', 'kind': 'text',
                 'field': 'main_text', 'protected_nodes': []}]).data()
        revision = PageRevision.objects.create(
            page=page, sequence=1, schema_version=schema.SCHEMA,
            payload=payload, payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(
            page=page, current_revision=revision, sequence=1)
        return page, route, revision

    def counts(self):
        return tuple(model.objects.count() for model in (
            Page, Route, PageRevision, PageContentState, AuditEvent, Session))

    def test_primary_exact_query_renders_safe_data_without_template_execution(self):
        marker = '<p>{{ 7|add:7 }}</p>'
        self.page('Name <safe>', '/exact/?q=1', main=marker)
        response = self.client.get('/exact/?q=1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Name &lt;safe&gt;', html=False)
        self.assertContains(response, 'H1 &lt;safe&gt;', html=False)
        self.assertContains(response, '<p>Intro</p>', html=True)
        self.assertIn(b'{{ 7|add:7 }}', response.content)
        self.assertNotIn(b'<p>14</p>', response.content)
        self.assertEqual(response['Cache-Control'], 'no-cache')
        self.assertFalse(response.cookies)

    def test_alias_renders_current_page_without_changing_url(self):
        page, _primary, revision = self.page('Alias', '/primary/')
        Route.objects.create(
            page=page, kind=Route.Kind.ALIAS, target='/alias/',
            is_legacy=False)
        response = self.client.get('/alias/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(revision.payload['main_text'].encode(), response.content)
        self.assertNotIn(b'/primary/', response.get('Location', '').encode())

    def test_redirect_is_permanent_and_exactly_internal_primary(self):
        page, primary, _revision = self.page('Redirect', '/current/')
        Route.objects.create(
            page=page, kind=Route.Kind.REDIRECT, target='/old/')
        response = self.client.get('/old/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], primary.target)
        self.assertEqual(response['Cache-Control'], 'no-cache')

    def test_unknown_and_system_are_closed_404_while_hidden_is_blank_200(self):
        _page, hidden, _revision = self.page(
            'Hidden', '/hidden/', published=False)
        system = Route.objects.create(
            page=None, kind=Route.Kind.SYSTEM, target='/system-public/')
        for target in ('/missing/', system.target):
            with self.subTest(target=target):
                response = self.client.get(target)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.content, 'Страница не найдена.'.encode())
                self.assertEqual(response['Cache-Control'], 'no-store')
        with patch('content.public_views.render_shared') as renderer:
            blank = self.client.get(hidden.target)
        self.assertEqual(blank.status_code, 200)
        self.assertEqual(blank.content, b'')
        self.assertEqual(blank['Cache-Control'], 'no-cache')
        self.assertEqual(blank['Content-Type'], 'text/html; charset=utf-8')
        self.assertIn("default-src 'none'", blank['Content-Security-Policy'])
        renderer.assert_not_called()

    def test_hidden_alias_and_redirect_are_blank_without_current_or_shared(self):
        page, primary, revision = self.page(
            'Hidden routes', '/hidden-routes/', published=False)
        alias = Route.objects.create(
            page=page, kind=Route.Kind.ALIAS, target='/hidden-alias/')
        redirect = Route.objects.create(
            page=page, kind=Route.Kind.REDIRECT, target='/hidden-old/')
        raw(PageRevision).filter(pk=revision.pk).update(
            payload={'private': 'MUST-NOT-LEAK'}, payload_hash='0' * 64)
        before = self.counts()
        with patch('content.public_views.render_shared') as renderer:
            for target in (primary.target, alias.target):
                response = self.client.get(target)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, b'')
            moved = self.client.get(redirect.target)
        self.assertEqual(moved.status_code, 301)
        self.assertEqual(moved['Location'], primary.target)
        renderer.assert_not_called()
        self.assertEqual(self.counts(), before)

    def test_damaged_or_unsafe_stored_content_and_database_failure_are_503(self):
        _page, route, revision = self.page('Damaged', '/damaged/')
        payload = dict(revision.payload)
        payload['main_text'] = '<script>alert(1)</script><p>Visible</p>'
        raw(PageRevision).filter(pk=revision.pk).update(
            payload=payload, payload_hash=schema.digest(payload))
        response = self.client.get(route.target)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'alert', response.content)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.client.cookies[settings.SESSION_COOKIE_NAME] = 'public-cookie-must-not-load'
        with patch('django.contrib.sessions.backends.db.SessionStore.load',
                   side_effect=DatabaseError()) as session_load, patch(
                       'content.public_views.resolve_target', side_effect=DatabaseError()):
            unavailable = self.client.get('/database-failure/')
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.content, 'Страница временно недоступна.'.encode())
        self.assertFalse(unavailable.cookies)
        session_load.assert_not_called()

    def test_head_and_disallowed_methods_have_no_body_cookie_or_writes(self):
        _page, route, _revision = self.page('Methods', '/methods/')
        before = self.counts()
        head = self.client.head(route.target)
        post = self.client.post(route.target, data={'ignored': 'value'})
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b'')
        self.assertEqual(post.status_code, 405)
        self.assertEqual(post['Allow'], 'GET, HEAD')
        self.assertEqual(post['Cache-Control'], 'no-store')
        self.assertFalse(head.cookies)
        self.assertFalse(post.cookies)
        self.assertEqual(self.counts(), before)

    def test_stylesheet_is_fixed_nosniff_get_head_only(self):
        self.client.cookies[settings.SESSION_COOKIE_NAME] = 'public-cookie-must-not-load'
        with patch('django.contrib.sessions.backends.db.SessionStore.load',
                   side_effect=DatabaseError()) as session_load:
            response = self.client.get('/static/public.css')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b':root'))
        self.assertEqual(response['Content-Type'], 'text/css; charset=utf-8')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertFalse(response.cookies)
        session_load.assert_not_called()
        self.assertEqual(self.client.head('/static/public.css').content, b'')
        self.assertEqual(self.client.post('/static/public.css').status_code, 405)

    def test_manage_routes_keep_priority_over_public_catch_all(self):
        response = self.client.get('/manage/login/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'\x00', response.content)
        self.assertEqual(
            self.client.post('/manage/password/', data={'password': 'ignored'}).status_code,
            401)

    def test_unsupported_layout_kinds_are_closed_without_partial_body_or_uuid(self):
        image_id = '71de8370-3105-5209-a189-82bb243b0091'
        asset_id = '71de8370-3105-5209-a189-82bb243b0092'
        reference_id = '71de8370-3105-5209-a189-82bb243b0093'
        canary = '<p>LAYOUT-CANARY-MUST-NOT-LEAK</p>'
        fingerprint = 'c' * 64
        text = lambda identifier, protected_nodes=None: {
            'id': identifier, 'kind': 'text', 'field': 'intro_text',
            'protected_nodes': protected_nodes or []}
        protected = {
            'id': '71de8370-3105-5209-a189-82bb243b0094',
            'kind': 'protected_ref', 'reference_id': reference_id,
            'fingerprint': fingerprint}
        cases = (
            ('image', '/unsupported-image/', [
                text('71de8370-3105-5209-a189-82bb243b0095'),
                {'id': '71de8370-3105-5209-a189-82bb243b0096',
                 'kind': 'image', 'image_id': image_id}],
             [{'id': image_id, 'asset_id': asset_id, 'alt': 'private',
               'alignment': 'center', 'width_px': None, 'height_px': None}],
             asset_id, False),
            ('protected_ref', '/unsupported-protected-ref/', [
                text('71de8370-3105-5209-a189-82bb243b0097'), protected],
             None, reference_id, False),
            ('protected_text', '/unsupported-protected-text/', [
                text('71de8370-3105-5209-a189-82bb243b0098', [{
                    'id': '71de8370-3105-5209-a189-82bb243b0099',
                    'reference_id': reference_id, 'fingerprint': fingerprint}]),
                protected], None, reference_id, False),
            ('unknown', '/unsupported-unknown/', [
                text('71de8370-3105-5209-a189-82bb243b0100'),
                {'id': '71de8370-3105-5209-a189-82bb243b0101',
                 'kind': 'future_kind', 'reference_id': reference_id}],
             None, reference_id, True))

        for position, (name, target, layout, images, private_id,
                       corrupt_after_create) in enumerate(cases):
            with self.subTest(kind=name):
                initial_layout = layout if not corrupt_after_create else layout[:1]
                _page, route, revision = self.page(
                    name, target, intro=canary, layout=initial_layout,
                    embedded_images=images, position=position)
                if corrupt_after_create:
                    payload = dict(revision.payload)
                    payload['layout'] = layout
                    raw(PageRevision).filter(pk=revision.pk).update(
                        payload=payload, payload_hash=schema.digest(payload))
                response = self.client.get(route.target)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response['Cache-Control'], 'no-store')
                self.assertNotIn(canary.encode(), response.content)
                self.assertNotIn(private_id.encode(), response.content)

    def test_layout_price_actual_html_order_escaping_and_exact_amount(self):
        column = '71de8370-3105-5209-a189-82bb243b0081'
        price = {'columns': [{'id': column, 'label': 'Цена <легковая>'}],
                 'rows': [
                     {'id': '71de8370-3105-5209-a189-82bb243b0082',
                      'label': 'Диагностика <ЭСУД>', 'cells': [
                          {'column_id': column, 'kind': 'amount',
                           'amount': '1234567.01', 'from': True}]},
                     {'id': '71de8370-3105-5209-a189-82bb243b0083',
                      'label': 'После осмотра', 'cells': [
                          {'column_id': column, 'kind': 'text',
                           'text': '<уточняйте>'}]}]}
        _page, route, _revision = self.page(
            'Price', '/price-layout/', price=price,
            layout=[
                {'id': '71de8370-3105-5209-a189-82bb243b0084', 'kind': 'text',
                 'field': 'main_text', 'protected_nodes': []},
                {'id': '71de8370-3105-5209-a189-82bb243b0085', 'kind': 'price'},
                {'id': '71de8370-3105-5209-a189-82bb243b0086', 'kind': 'text',
                 'field': 'intro_text', 'protected_nodes': []}])
        response = self.client.get(route.target)
        source = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertLess(source.index('Main <strong>text</strong>'),
                        source.index('Диагностика &lt;ЭСУД&gt;'))
        self.assertLess(source.index('Диагностика &lt;ЭСУД&gt;'),
                        source.index('<p>Intro</p>'))
        self.assertIn('Цена &lt;легковая&gt;', source)
        self.assertIn('&lt;уточняйте&gt;', source)
        self.assertNotIn('<уточняйте>', source)
        self.assertIn('от 1\u202f234\u202f567,01\u00a0₽', source)
