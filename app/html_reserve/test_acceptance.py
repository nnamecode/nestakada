import hashlib
import os
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.http import HttpResponse, HttpResponsePermanentRedirect
from django.test import TransactionTestCase, override_settings

from content import public_views
from content.public_gallery import ALBUM_TARGETS, ROOT_TARGET
from content.public_views import PUBLIC_CSP
from media_library import services
from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder
from media_library.storage import MediaStorage
from shared_content import public as shared_public

from .build import run
from .contracts import ContractError, TargetSpec
from .source import SourceSnapshot
from .storage import ReserveStore


@override_settings(PUBLIC_ORIGIN='http://localhost:8767',
                   SEO_ROBOTS_PROFILE='deny-all')
class HtmlReserveCombinedAcceptanceTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.media_temp = TemporaryDirectory()
        self.reserve_temp = TemporaryDirectory()
        self.addCleanup(self.media_temp.cleanup)
        self.addCleanup(self.reserve_temp.cleanup)
        self.media_override = override_settings(
            MEDIA_LIBRARY_ROOT=self.media_temp.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.root = Path(self.reserve_temp.name) / 'reserve'
        folder = MediaFolder.objects.create(path='html-reserve/acceptance')
        asset = Asset.objects.create(
            folder=folder, provenance='DEV25 synthetic acceptance')
        self.file = services.write_file(
            asset_id=asset.pk, kind=AssetFile.Kind.MAIN,
            key='img/%s/main.webp' % asset.pk,
            chunks=b'RIFFxxxxWEBPdev25-acceptance', storage=MediaStorage())
        self.asset = services.mark_ready(
            asset_id=asset.pk, storage=MediaStorage())
        self.page_id = uuid4()
        self.usage = services.attach(
            asset_id=asset.pk, kind=AssetUsage.Kind.CURRENT_PAGE,
            consumer_id=self.page_id, slot='main_image')
        slug = ALBUM_TARGETS[0].removeprefix(ROOT_TARGET)
        self.targets = (
            TargetSpec('/', 200),
            TargetSpec('/hidden/', 200),
            TargetSpec('/old/', 301, '/'),
            TargetSpec(ROOT_TARGET + '?album=' + slug, 200),
            TargetSpec(ROOT_TARGET + '?page=2&album=' + slug, 200),
        )
        descriptor = {
            'seo': ['http://localhost:8767', 'deny-all'],
            'files': [[
                str(self.file.pk), str(self.asset.pk), self.file.kind,
                self.file.key, self.file.sha256, self.file.byte_size]],
            'usages': [[
                str(self.usage.pk), self.usage.kind, str(self.page_id),
                self.usage.slot, str(self.asset.pk)]],
            'statics': [[
                name, hashlib.sha256(body).hexdigest(), len(body)]
                for name, body in sorted({
                    'public.css': public_views.STYLESHEET,
                    'public-gallery.js': public_views.GALLERY_SCRIPT,
                    'public-home.js': public_views.HOME_SCRIPT,
                    'public-shared.css': shared_public.static_descriptor(
                        'public-shared.css')['body'],
                    'public-shared.js': shared_public.static_descriptor(
                        'public-shared.js')['body'],
                }.items())],
        }
        self.source = SourceSnapshot(
            hashlib.sha256(b'DEV25 synthetic source').hexdigest(),
            descriptor, self.targets)

    def page_response(self, *, robots=None):
        shared_css = shared_public.static_descriptor('public-shared.css')
        shared_js = shared_public.static_descriptor('public-shared.js')
        bare = '/public-media/%s/' % self.file.pk
        contextual = bare + '?page=%s&slot=main_image' % self.page_id
        body = (
            '<!doctype html><link rel="stylesheet" href="/static/public.css">'
            '<link rel="stylesheet" href="/static/shared/%s/public-shared.css">'
            '<script src="/static/public-home.js"></script>'
            '<script src="/static/shared/%s/public-shared.js"></script>'
            '<img src="%s"><meta property="og:image" content="%s">'
            '<a href="https://navigation.example/safe">external navigation</a>'
            '<p>DEV25-PUBLISHED-CANARY</p>'
            % (shared_css['digest'], shared_js['digest'], bare, contextual)
        ).encode()
        response = HttpResponse(body, content_type='text/html; charset=utf-8')
        response['Cache-Control'] = 'no-cache'
        response['Content-Security-Policy'] = PUBLIC_CSP
        response['X-Content-Type-Options'] = 'nosniff'
        response['ETag'] = '"' + hashlib.sha256(body).hexdigest() + '"'
        if robots is not None:
            response['X-Robots-Tag'] = robots
        return response

    def responses(self):
        hidden = HttpResponse(b'', content_type='text/html; charset=utf-8')
        hidden['Cache-Control'] = 'no-cache'
        hidden['Content-Security-Policy'] = PUBLIC_CSP
        hidden['X-Content-Type-Options'] = 'nosniff'
        hidden['X-Robots-Tag'] = 'noindex, nofollow'
        redirect = HttpResponsePermanentRedirect('/')
        redirect['Cache-Control'] = 'no-cache'
        return {
            '/': self.page_response(),
            '/hidden/': hidden,
            '/old/': redirect,
            self.targets[3].target: self.page_response(robots='noindex, follow'),
            self.targets[4].target: self.page_response(robots='noindex, follow'),
        }

    def test_exact_self_contained_set_and_fail_closed_integrity(self):
        responses = self.responses()
        result = run(
            root=self.root, capture_source=lambda: self.source,
            render=lambda target: responses[target],
            recapture=lambda: self.source,
            now=lambda: datetime(2026, 11, 12,
                                 tzinfo=datetime_timezone.utc))
        self.assertEqual(result.status, 'activated')
        with ReserveStore(self.root).locked() as locked:
            pointer = locked.read_pointer()
            manifest = locked.generation_manifest(
                pointer['current'], pointer['current_manifest_sha256'])
        self.assertEqual(
            {row['target'] for row in manifest['responses']},
            {spec.target for spec in self.targets})
        metadata = {row['target']: row for row in manifest['responses']}
        self.assertEqual(metadata['/old/']['location'], '/')
        self.assertIsNone(metadata['/']['x_robots_tag'])
        self.assertEqual(
            metadata['/hidden/']['x_robots_tag'], 'noindex, nofollow')
        resource_urls = {row['url'] for row in manifest['resources']}
        self.assertIn('/public-media/%s/' % self.file.pk, resource_urls)
        self.assertIn(
            '/public-media/%s/?page=%s&slot=main_image'
            % (self.file.pk, self.page_id), resource_urls)
        self.assertFalse(any(url.startswith('http') for url in resource_urls))

        generation = self.root / 'generations' / pointer['current']
        html = b''.join(
            (generation / 'responses' / row['name']).read_bytes()
            for row in manifest['responses'])
        self.assertIn(b'https://navigation.example/safe', html)
        self.assertIn(b'DEV25-PUBLISHED-CANARY', html)
        for forbidden in (
                b'<form', b'csrfmiddlewaretoken', b'/manage/', b'/history/',
                b'/preview/', b'PRIVATE-PII-CANARY', b'TECHNICAL-TOKEN-CANARY',
                b'OWNER-COOKIE-CANARY'):
            self.assertNotIn(forbidden, html)

        before = (self.root / 'active.json').read_bytes()
        private = self.responses()
        private['/'].set_cookie('private', 'OWNER-COOKIE-CANARY')
        with self.assertRaisesRegex(
                ContractError, 'HTML_RESERVE_RESPONSE_PRIVATE_STATE'):
            run(root=self.root, capture_source=lambda: self.source,
                render=lambda target: private[target],
                recapture=lambda: self.source)
        self.assertEqual((self.root / 'active.json').read_bytes(), before)

        resource = manifest['resources'][0]
        resource_path = generation / 'resources' / resource['name']
        os.chmod(resource_path, 0o600)
        resource_path.write_bytes(b'tampered')
        with ReserveStore(self.root).locked() as locked:
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_MANIFEST_FILE_MISMATCH'):
                locked.read_pointer()
