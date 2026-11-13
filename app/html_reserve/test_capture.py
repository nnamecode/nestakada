import base64
import hashlib
import tempfile
from unittest.mock import patch
from uuid import uuid4

from django.test import TransactionTestCase, override_settings

from content.models import Page
from content import public_views, test_public_http as public_tests
from media_library.storage import MediaStorage
from page_editor.test_media_http import PNG
from shared_content import public as shared_public

from .contracts import ContractError, ResourceRef
from .capture import (
    extract_resources, internal_request, resource_bytes, resource_policy,
    render_target, safe_css, safe_javascript,
)
from .source import SourceSnapshot


class HtmlReserveCaptureTests(TransactionTestCase):
    page = public_tests.PublicHttpTests.page

    def setUp(self):
        super().setUp()
        shared = patch(
            'content.public_views.render_shared',
            side_effect=public_tests.fake_shared)
        shared.start()
        self.addCleanup(shared.stop)

    def statics(self):
        rows = []
        for name, body in (
                ('public.css', public_views.STYLESHEET),
                ('public-gallery.js', public_views.GALLERY_SCRIPT),
                ('public-home.js', public_views.HOME_SCRIPT)):
            rows.append([name, hashlib.sha256(body).hexdigest(), len(body)])
        for name in ('public-shared.css', 'public-shared.js'):
            descriptor = shared_public.static_descriptor(name)
            rows.append([name, descriptor['digest'], len(descriptor['body'])])
        return sorted(rows)

    @override_settings(
        PUBLIC_ORIGIN='http://localhost:8767', SEO_ROBOTS_PROFILE='deny-all',
        SERVICE_REQUEST_INTAKE_ENABLED=True,
        SERVICE_REQUEST_TRANSPORT_PROFILE='synthetic',
        SERVICE_REQUEST_CONSENT_VERSION='synthetic-v1')
    def test_internal_render_is_anonymous_unconditional_and_form_disabled(self):
        self.page('Home', '/', kind=Page.Kind.HOME)
        normal = self.client.get('/')
        self.assertEqual(normal.status_code, 200)
        self.assertIn(b'<form method="post" action="/request/submit/">', normal.content)
        self.assertIn(b'name="intent"', normal.content)

        request = internal_request('/')
        self.assertEqual(request.COOKIES, {})
        self.assertNotIn('HTTP_COOKIE', request.META)
        self.assertNotIn('HTTP_IF_NONE_MATCH', request.META)
        self.assertFalse(hasattr(request, 'session'))
        reserve = render_target('/')
        self.assertEqual(reserve.status_code, 200)
        self.assertNotIn(b'<form', reserve.content)
        self.assertNotIn(b'name="intent"', reserve.content)
        self.assertNotIn(b'csrfmiddlewaretoken', reserve.content)
        self.assertIn('Онлайн-запись пока недоступна'.encode(), reserve.content)
        self.assertFalse(reserve.cookies)
        self.assertNotEqual(reserve.status_code, 304)

    def test_html_extractor_accepts_only_frozen_same_origin_resources(self):
        file_id, page_id = uuid4(), uuid4()
        bare = '/public-media/%s/' % file_id
        contextual = bare + '?page=%s&slot=main_image' % page_id
        html = (
            '<!doctype html><link rel="stylesheet" href="/static/public.css">'
            '<script src="/static/public-home.js"></script>'
            '<img src="%s"><meta property="og:image" '
            'content="http://localhost:8767%s">'
            '<a href="/known/">local navigation</a>'
            '<a href="https://trusted.example/path">external navigation</a>'
            % (bare, contextual)).encode()
        resources = extract_resources(
            html, origin='http://localhost:8767',
            bare_file_ids={str(file_id)},
            contextual={(str(file_id), str(page_id), 'main_image')},
            local_targets={'/known/'})
        self.assertEqual({item.kind for item in resources}, {
            'static-public', 'media-bare', 'media-contextual'})
        for bad in (
                b'<script src="https://evil.test/x.js"></script>',
                b'<img src="//evil.test/x.png">',
                b'<form action="/request/submit/"></form>',
                b'<img src="/public-media/00000000-0000-0000-0000-000000000000/">',
                b'<iframe src="https://evil.test/"></iframe>',
                b'<img srcset="/x.webp 2x">',
                b'<style>.x{background:url(/x.png)}</style>',
                b'<object data="/x"></object>',
                b'<meta http-equiv="refresh" content="0;url=https://evil.test/">',
                b'<svg><image xlink:href="https://evil.test/x.svg"></image></svg>',
                b'<link rel="preload stylesheet" href="/static/public.css">',
                b'<a href="//evil.test/">bad</a>',
                b'<a href="https://user@evil.test/">bad</a>',
                b'<a href="http://localhost:8767/unknown/">bad</a>',
                b'<a href="/unknown/">bad</a>'):
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                extract_resources(
                    bad, origin='http://localhost:8767',
                    bare_file_ids={str(file_id)}, contextual=set())
        self.assertEqual(extract_resources(
            b'<script type="application/ld+json">{"url":"https://safe.example/"}</script>',
            origin='http://localhost:8767', bare_file_ids=set(),
            contextual=set()), ())

    def test_frozen_policy_and_static_bytes_are_closed(self):
        file_id, asset_id, page_id = uuid4(), uuid4(), uuid4()
        snapshot = SourceSnapshot('a' * 64, {
            'files': [[str(file_id), str(asset_id), 'main',
                       'img/a/main.webp', 'b' * 64, 10]],
            'usages': [[str(uuid4()), 'current_page', str(page_id),
                        'main_image', str(asset_id)]],
            'statics': self.statics(),
        }, ())
        bare, contextual = resource_policy(snapshot)
        self.assertEqual(bare, frozenset((str(file_id),)))
        self.assertEqual(
            contextual,
            frozenset(((str(file_id), str(page_id), 'main_image'),)))
        ref = ResourceRef('static-public', None, None, None,
                          'public.css', None)
        body, content_type = resource_bytes(ref, snapshot)
        self.assertTrue(body)
        self.assertEqual(content_type, 'text/css; charset=utf-8')
        safe_css(body)
        for name in ('public-gallery.js', 'public-home.js'):
            body, content_type = resource_bytes(ResourceRef(
                'static-public', None, None, None, name, None), snapshot)
            self.assertTrue(body)
            self.assertEqual(content_type, 'text/javascript; charset=utf-8')
            safe_javascript(body)
        for name in ('public-shared.css', 'public-shared.js'):
            descriptor = shared_public.static_descriptor(name)
            body, _content_type = resource_bytes(ResourceRef(
                'static-shared', None, None, None, name,
                descriptor['digest']), snapshot)
            self.assertEqual(body, descriptor['body'])

        stale = SourceSnapshot('a' * 64, {
            'files': [], 'usages': [], 'statics': self.statics()}, ())
        with patch.object(public_views, 'STYLESHEET', b'changed'):
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_STATIC_SOURCE_CHANGED'):
                resource_bytes(ResourceRef(
                    'static-public', None, None, None, 'public.css', None), stale)

    def test_media_bytes_are_read_once_against_frozen_descriptor(self):
        file_id, asset_id = uuid4(), uuid4()
        key = 'img/%s/original.png' % asset_id
        with tempfile.TemporaryDirectory() as root, self.settings(
                MEDIA_LIBRARY_ROOT=root):
            media_body = base64.b64decode(PNG, validate=True)
            actual = MediaStorage().write_new(key, media_body)
            snapshot = SourceSnapshot('a' * 64, {
                'files': [[str(file_id), str(asset_id), 'legacy-public', key,
                           actual['sha256'], actual['byte_size']]],
                'usages': [],
                'statics': self.statics(),
            }, ())
            body, content_type = resource_bytes(ResourceRef(
                'media-bare', str(file_id), None, None, None, None), snapshot)
        self.assertEqual(body, media_body)
        self.assertEqual(hashlib.sha256(body).hexdigest(), actual['sha256'])
        self.assertEqual(content_type, 'image/png')

    def test_css_and_javascript_network_primitives_fail_closed(self):
        safe_css(b'.a { color: #fff; }')
        safe_javascript(b'document.addEventListener("click", () => {});')
        for body in (b'.a{background:url(/x.png)}', b'@import "/x.css";'):
            with self.subTest(body=body), self.assertRaises(ContractError):
                safe_css(body)
        for body in (b'fetch("/x")', b'new XMLHttpRequest()',
                     b'new WebSocket("wss://x")', b'import("/x.js")'):
            with self.subTest(body=body), self.assertRaises(ContractError):
                safe_javascript(body)
