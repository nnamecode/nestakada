"""PUB07 independent real HTTP/PG/FS checks; host is explicitly QA-only."""
import hashlib
import base64
from html.parser import HTMLParser
from pathlib import Path
import threading
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections, models, transaction
from django.test import Client, TransactionTestCase, override_settings

from content.models import Page, Route, lock_content
from media_library.models import Asset, AssetFile, AssetUsage
from media_library.storage import MediaStorage
from . import test_shared_reservation as R
from .models import SharedBlock, SharedRevision, SharedDraft, SharedBasePin
from .storage import SharedStorage


class PublicDOM(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.tags, self.text = [], []
        self.feed(source)
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
    def handle_data(self, data):
        self.text.append(data)


@override_settings(ROOT_URLCONF='shared_content.public_test_urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SharedPublicTests(R.ReservationFixture, TransactionTestCase):
    host_url = '/__shared_public__/'

    def setUp(self):
        super().setUp()
        self.anonymous = Client(enforce_csrf_checks=True, HTTP_HOST='localhost')

    def seed_public(self):
        _, header = self.apply_text('header', 'PUBLIC-HEADER-LITERAL')
        _, footer = self.apply_text('footer', 'PUBLIC-FOOTER')
        self.nav = Page.objects.create(kind=Page.Kind.ARTICLE, name='Menu <literal> & safe',
                                      is_published=True, position=10)
        self.route = Route.objects.create(page=self.nav, kind=Route.Kind.PRIMARY,
            target='/Legacy/Exact/?a=1&b=Two', is_legacy=True)
        return header, footer

    def body_bytes(self, response):
        try:
            return b''.join(response.streaming_content) if response.streaming else response.content
        finally:
            if response.streaming: response.close()

    def ready_main(self):
        return self.asset.files.get(kind=AssetFile.Kind.MAIN)

    def media_url(self, file):
        return '/__shared_public__/media/%s/' % file.pk

    def read_state(self):
        from django.contrib.sessions.models import Session
        return self.state(), SharedStorage().inventory(), Session.objects.count()

    def test_pub001_current_literal_contacts_ready_media_and_nonpublic_sources_stay_private(self):
        with self.candidate():
            header, footer = self.seed_public()
            # Accepted writer grammar permits whitespace-only nav content.
            # Exercise real canonical Check/Apply before the public consumer.
            pretty = self.fixture('header', 'PUBLIC-HEADER-LITERAL').replace('</nav>', '\n  </nav>', 1)
            pretty_result = self.applied('header', 'apply', self.intent('header', pretty))
            stored_pretty = SharedRevision.objects.get(pk=pretty_result['resultId'])
            self.assertIn('\n  </nav>', self.body(stored_pretty))
            baseline = self.anonymous.get(self.host_url)
            self.assertEqual(baseline.status_code, 200)
            source = self.body_bytes(baseline).decode()
            dom = PublicDOM(source)
            self.assertEqual(sum(tag == 'header' for tag, attrs in dom.tags), 1)
            self.assertEqual(sum(tag == 'footer' for tag, attrs in dom.tags), 1)
            self.assertIn('PUBLIC-HEADER-LITERAL', ''.join(dom.text))
            self.assertIn('PUBLIC-FOOTER', ''.join(dom.text))
            self.assertIn(('a', {'class': 'es-header-phone', 'href': 'tel:+70000000001'}), dom.tags)
            self.assertTrue(any(tag == 'a' and attrs.get('href') == self.route.target for tag, attrs in dom.tags))
            self.assertNotIn('<literal>', source)
            self.assertEqual([attrs.get('src') for tag, attrs in dom.tags if tag == 'img'],
                             [self.media_url(self.ready_main())] * 5)
            self.assertNotIn('/manage/', source)
            self.assertNotIn('private/', source)
            # These constructs never cross the accepted producer boundary.
            # Public positive fixtures must obey the existing closed policy.
            rejected_state = self.read_state()
            for marker in ('{{7*7}}', '{% include "private" %}', '{# template #}'):
                value = {'protocol': 'shared-editor-v1', 'generation': 1, **self.context('header'),
                         'html': self.fixture('header', marker)}
                self.assertEqual(self.send('header', 'check', value).status_code, 400)
            self.assertEqual(self.read_state(), rejected_state)
            self.applied('header', 'draft', self.intent('header', self.fixture('header', 'DRAFT-NEVER-PUBLIC')))
            before = self.read_state()
            unchanged = self.anonymous.get(self.host_url)
            self.assertEqual(self.body_bytes(unchanged), source.encode())
            self.assertEqual(unchanged['ETag'], baseline['ETag'])
            self.assertEqual(self.read_state(), before)
            self.assertEqual(self.anonymous.cookies.keys(), set())

    def test_pub003_conditional_get_head_weak_list_star_and_no_invented_last_modified(self):
        with self.candidate():
            self.seed_public()
            first = self.anonymous.get(self.host_url)
            self.assertEqual(first.status_code, 200)
            tag = first['ETag']
            before = self.read_state()
            for condition in (tag, 'W/' + tag, '"other", W/' + tag, '*'):
                for method in (self.anonymous.get, self.anonymous.head):
                    with self.subTest(condition=condition, method=method.__name__):
                        result = method(self.host_url, HTTP_IF_NONE_MATCH=condition)
                        self.assertEqual(result.status_code, 304)
                        self.assertEqual(self.body_bytes(result), b'')
                        self.assertEqual(result['ETag'], tag)
                        self.assertEqual(result['Cache-Control'], 'no-cache')
                        self.assertNotIn('Last-Modified', result)
            for condition in ('bad-tag', '"unterminated', '"different"'):
                self.assertEqual(self.anonymous.get(self.host_url, HTTP_IF_NONE_MATCH=condition).status_code, 200)
            head = self.anonymous.head(self.host_url)
            self.assertEqual(head.status_code, 200)
            self.assertEqual(self.body_bytes(head), b'')
            self.assertEqual(head['ETag'], tag)
            self.assertNotIn('Last-Modified', head)
            ims = self.anonymous.get(self.host_url, HTTP_IF_MODIFIED_SINCE='Thu, 31 Dec 2099 23:59:59 GMT')
            self.assertEqual(ims.status_code, 200)
            self.assertEqual(self.read_state(), before)

    def test_pub002_actual_page_primary_nav_publication_name_order_and_visibility_change_etag(self):
        with self.candidate():
            self.seed_public()
            first = self.anonymous.get(self.host_url)
            other = Page.objects.create(kind=Page.Kind.ARTICLE, name='SECOND-NAV', is_published=True, position=20)
            Route.objects.create(page=other, kind=Route.Kind.PRIMARY, target='/qa-second/')
            second = self.anonymous.get(self.host_url, HTTP_IF_NONE_MATCH=first['ETag'])
            self.assertEqual(second.status_code, 200)
            self.assertNotEqual(second['ETag'], first['ETag'])
            untouched = dict(Page.objects.exclude(pk__in=[self.nav.pk, other.pk]).values_list('pk', 'position'))
            with transaction.atomic():
                lock_content('default')
                self.nav = Page.objects.select_for_update().get(pk=self.nav.pk)
                other = Page.objects.select_for_update().get(pk=other.pk)
                other.position, self.nav.position = self.nav.position, other.position
                other.name = 'RENAMED-NAV'
                other.save(); self.nav.save()
            self.assertEqual(dict(Page.objects.exclude(pk__in=[self.nav.pk, other.pk]).values_list('pk', 'position')),
                             untouched)
            third = self.anonymous.get(self.host_url)
            text = self.body_bytes(third).decode()
            self.assertLess(text.index('RENAMED-NAV'), text.index('Menu &lt;literal&gt; &amp; safe'))
            self.assertNotEqual(third['ETag'], second['ETag'])
            other.is_published = False; other.save()
            hidden = self.anonymous.get(self.host_url)
            self.assertNotIn('RENAMED-NAV', self.body_bytes(hidden).decode())
            self.assertNotEqual(hidden['ETag'], third['ETag'])

    def test_pub001_both_exact_mebibyte_components_plus_independent_navigation_budget(self):
        from . import public
        from . import public_test_urls as host
        from .test_shared_calibration import SharedCalibrationTests
        max_html = SharedCalibrationTests.max_html.__get__(self)
        with self.candidate():
            for kind in ('header', 'footer'):
                html = max_html(kind, label='PUB-MAX-' + kind)
                self.assertEqual(len(html.encode()), 1048576)
                self.applied(kind, 'apply', self.intent(kind, html))
            navigation = tuple(public.NavItem('N' * 100 + str(index), '/qa-large-nav/%s/' % index)
                               for index in range(1024))
            rendered = public.render_shared(capture_host=lambda: public.HostContext('a' * 64, navigation),
                media_url=host.media_url, static_url=host.static_url)
            self.assertGreater(len(rendered.header_html.encode()), 1048576)
            self.assertGreater(len(rendered.header_html.encode()) + len(rendered.footer_html.encode()), 2 * 1048576)
            self.assertEqual(sum(tag == 'a' and attrs.get('href', '').startswith('/qa-large-nav/')
                                 for tag, attrs in PublicDOM(rendered.header_html).tags), 1024)
            # PUBREV-001: a legal character-bounded local URL can expand both
            # through UTF-8 and HTML escaping. Preserve the full legal source.
            long_url = '/__shared_public__/' + 'ж' * 1000 + '?' + '&' * 900
            self.assertLessEqual(len(long_url), 2048)
            expanded = public.render_shared(capture_host=lambda: public.HostContext('a' * 64, navigation),
                media_url=lambda file_id: long_url, static_url=host.static_url)
            self.assertEqual([attrs['src'] for tag, attrs in PublicDOM(expanded.header_html).tags if tag == 'img'],
                             [long_url] * 4)
            self.assertEqual([attrs['src'] for tag, attrs in PublicDOM(expanded.footer_html).tags if tag == 'img'],
                             [long_url])
            self.assertGreater(len(expanded.header_html.encode()), len(rendered.header_html.encode()))

    def test_pub009_corrupt_current_inline_payload_old_etag_cannot_hide_failure_or_blind_retry(self):
        from . import public
        with self.candidate():
            self.seed_public()
            first = self.anonymous.get(self.host_url)
            row = SharedRevision.objects.get(pk=SharedBlock.objects.get(kind='footer').current_revision_id)
            self.assertEqual(row.storage_kind, 'inline')
            models.QuerySet(model=SharedRevision).filter(pk=row.pk).update(
                html='PUB-PRIVATE-CORRUPTION-CANARY')
            hits = []
            with patch.object(public, '_read_boundary', side_effect=hits.append):
                failed = self.anonymous.get(self.host_url, HTTP_IF_NONE_MATCH=first['ETag'])
            self.assertEqual(failed.status_code, 503)
            self.assertEqual(failed['Cache-Control'], 'no-store')
            self.assertEqual(hits.count('captured'), 1)
            self.assertEqual(hits.count('before_recheck'), 1)
            body = self.body_bytes(failed)
            self.assertNotIn(b'PUB-PRIVATE-CORRUPTION-CANARY', body)

    def commit_nav_on_other_connection(self, name):
        values, errors = {}, []
        page_id = self.nav.pk
        def writer():
            try:
                with transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()'); values['pid'] = cursor.fetchone()[0]
                    page = Page.objects.get(pk=page_id)
                    page.name = name; page.save()
            except Exception as error:
                errors.append(type(error).__name__)
            finally:
                connections.close_all()
        thread = threading.Thread(target=writer, name='public-host-pg-commit')
        thread.start(); thread.join(timeout=15)
        self.assertFalse(thread.is_alive(), 'PUBLIC_REAL_PG_WRITER_NOT_REAPED')
        self.assertEqual(errors, [])
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_backend_pid()'); self.assertNotEqual(values['pid'], cursor.fetchone()[0])

    def test_pub004_two_real_pg_connections_drift_retries_once_and_twice_drift_refuses(self):
        from . import public
        with self.candidate():
            self.seed_public()
            first = self.anonymous.get(self.host_url)
            hits = []
            def once(phase):
                hits.append(phase)
                if phase == 'before_recheck' and hits.count(phase) == 1:
                    self.assertFalse(connection.in_atomic_block)
                    self.commit_nav_on_other_connection('REAL-PG-NAV-COMMIT')
            with patch.object(public, '_read_boundary', side_effect=once):
                changed = self.anonymous.get(self.host_url, HTTP_IF_NONE_MATCH=first['ETag'])
            self.assertEqual(changed.status_code, 200)
            self.assertIn(b'REAL-PG-NAV-COMMIT', self.body_bytes(changed))
            self.assertEqual(hits.count('captured'), 2)
            hits.clear()
            def twice(phase):
                hits.append(phase)
                if phase == 'before_recheck':
                    self.commit_nav_on_other_connection('UNSTABLE-' + str(hits.count(phase)))
            with patch.object(public, '_read_boundary', side_effect=twice):
                unstable = self.anonymous.get(self.host_url)
            self.assertEqual(unstable.status_code, 503)
            self.assertEqual(hits.count('captured'), 2)
            self.assertEqual(unstable['Cache-Control'], 'no-store')

    def test_pub004_current_advanced_between_capture_and_read_retries_new_confirmed_snapshot(self):
        from . import public
        with self.candidate():
            self.seed_public()
            first = self.anonymous.get(self.host_url)
            hits = []
            def advance(phase):
                hits.append(phase)
                if phase == 'captured' and hits.count(phase) == 1:
                    self.apply_text('header', 'AFTER-CAPTURE-CURRENT-B')
            pins = SharedBasePin.objects.count()
            with patch.object(public, '_read_boundary', side_effect=advance):
                response = self.anonymous.get(self.host_url, HTTP_IF_NONE_MATCH=first['ETag'])
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'AFTER-CAPTURE-CURRENT-B', self.body_bytes(response))
            self.assertNotEqual(response['ETag'], first['ETag'])
            self.assertEqual(hits.count('captured'), 2)
            self.assertEqual(SharedBasePin.objects.count(), pins)

    def test_pub005_media_current_ready_only_revocation_conditional_and_verified_fd(self):
        from . import public
        from media_library.uploads import upload
        from page_editor.test_media_http import PNG
        with self.candidate():
            self.seed_public()
            main = self.ready_main()
            response = self.anonymous.get(self.media_url(main))
            self.assertEqual(response.status_code, 200)
            original = self.body_bytes(response)
            self.assertEqual(hashlib.sha256(original).hexdigest(), main.sha256)
            self.assertEqual(response['Content-Type'], 'image/webp')
            tag = response['ETag']
            for file in self.asset.files.exclude(kind=AssetFile.Kind.MAIN):
                self.assertEqual(self.anonymous.get(self.media_url(file), HTTP_IF_NONE_MATCH='*').status_code, 404)
            self.assertEqual(self.anonymous.get('/__shared_public__/media/%s/' % uuid4()).status_code, 404)
            for method in (self.anonymous.get, self.anonymous.head):
                conditional = method(self.media_url(main), HTTP_IF_NONE_MATCH='"other", W/' + tag)
                self.assertEqual(conditional.status_code, 304)
                self.assertEqual(self.body_bytes(conditional), b'')
                self.assertEqual(conditional['Cache-Control'], 'no-cache')
            second = upload(actor=self.owner, page_id=self.page.pk, expected_generation=1,
                upload=SimpleUploadedFile('pub-second.png', base64.b64decode(PNG), content_type='image/png'))
            other_main = second.files.get(kind=AssetFile.Kind.MAIN)
            second_html = self.fixture('header', 'ONLY-HISTORY-STAGE-DRAFT').replace(str(self.asset.pk), str(second.pk))
            result = self.applied('header', 'apply', self.intent('header', second_html))
            self.apply_text('header', 'CURRENT-FIRST-ASSET')
            self.applied('header', 'draft', self.intent('header', second_html))
            self.assertEqual(self.anonymous.get(self.media_url(other_main), HTTP_IF_NONE_MATCH='*').status_code, 404)
            # Explicit isolated metadata fixture: READY must be checked again.
            models.QuerySet(model=Asset).filter(pk=self.asset.pk).update(status=Asset.Status.STAGED)
            self.assertEqual(self.anonymous.get(self.media_url(main), HTTP_IF_NONE_MATCH=tag).status_code, 404)
            models.QuerySet(model=Asset).filter(pk=self.asset.pk).update(status=Asset.Status.READY)
            path = MediaStorage().root / main.key
            retained = path.with_name(path.name + '.own-retained')
            hits = []
            def substitute_after_verification(phase):
                if phase == 'media_verified' and not hits:
                    hits.append(phase)
                    path.rename(retained)
                    path.write_bytes(b'X' * main.byte_size); path.chmod(0o600)
            try:
                with patch.object(public, '_read_boundary', side_effect=substitute_after_verification):
                    verified = self.anonymous.get(self.media_url(main))
                    self.assertEqual(verified.status_code, 200)
                    self.assertEqual(self.body_bytes(verified), original)
                self.assertEqual(hits, ['media_verified'])
                self.assertEqual(self.anonymous.get(self.media_url(main), HTTP_IF_NONE_MATCH=tag).status_code, 503)
            finally:
                if retained.exists():
                    path.unlink(); retained.rename(path)
            hits.clear()
            def revoke_after_verification(phase):
                if phase == 'media_verified' and not hits:
                    hits.append(phase)
                    for kind in ('header', 'footer'):
                        html = self.fixture(kind, 'CURRENT-SECOND-ASSET').replace(str(self.asset.pk), str(second.pk))
                        self.applied(kind, 'apply', self.intent(kind, html))
            with patch.object(public, '_read_boundary', side_effect=revoke_after_verification):
                denied = self.anonymous.get(self.media_url(main), HTTP_IF_NONE_MATCH=tag)
            self.assertEqual(hits, ['media_verified'])
            self.assertEqual(denied.status_code, 404)
            self.assertEqual(denied['Cache-Control'], 'no-store')

    def test_pub007_trusted_static_exact_bytes_versions_and_actual_fixture_source_change(self):
        from . import public, public_test_urls as host
        with self.candidate():
            self.seed_public()
            first = self.anonymous.get(self.host_url)
            for name in ('public-shared.css', 'public-shared.js'):
                descriptor = public.static_descriptor(name)
                self.assertEqual(hashlib.sha256(descriptor['body']).hexdigest(), descriptor['digest'])
                url = host.static_url(name, descriptor['digest'])
                response = self.anonymous.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.body_bytes(response), descriptor['body'])
                self.assertEqual(response['Content-Type'], descriptor['content_type'])
                self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
                self.assertIn('immutable', response['Cache-Control'])
                self.assertEqual(self.anonymous.get(url, HTTP_IF_NONE_MATCH='W/' + response['ETag']).status_code, 304)
                head = self.anonymous.head(url)
                self.assertEqual(head.status_code, 200)
                self.assertEqual(self.body_bytes(head), b'')
                self.assertEqual(self.anonymous.get(host.static_url(name, '0' * 64)).status_code, 404)
            self.assertEqual(self.anonymous.get(host.static_url('private-source', '0' * 64)).status_code, 404)
            # Approved trusted-source seam: actual own CSS file bytes and SHA,
            # never a content/permission/quota bypass or mutation of frozen /app.
            original = public.static_descriptor
            path = Path(self.temp.name) / 'own-trusted-css-fixture'
            path.write_bytes(original('public-shared.css')['body'] + b'\n/* PUB actual fixture deployment */\n')
            def fixture_source(name):
                descriptor = original(name)
                if name == 'public-shared.css':
                    body = path.read_bytes()
                    descriptor = dict(descriptor, body=body, digest=hashlib.sha256(body).hexdigest())
                return descriptor
            with patch.object(public, 'static_descriptor', side_effect=fixture_source):
                changed = self.anonymous.get(self.host_url, HTTP_IF_NONE_MATCH=first['ETag'])
                self.assertEqual(changed.status_code, 200)
                self.assertNotEqual(changed['ETag'], first['ETag'])
                descriptor = fixture_source('public-shared.css')
                served = self.anonymous.get(host.static_url(descriptor['name'], descriptor['digest']))
                self.assertEqual(served.status_code, 200)
                self.assertEqual(self.body_bytes(served), path.read_bytes())
            with override_settings(ROOT_URLCONF='estakada.urls'):
                self.assertEqual(self.anonymous.get(self.host_url).status_code, 404)

    def test_pub009_actual_restore_old_literal_phone_changes_selected_fragment_only(self):
        with self.candidate():
            original, footer = self.seed_public()
            old = SharedRevision.objects.get(pk=original['resultId'])
            old_hash = old.file_sha256
            html = self.fixture('header', 'NEW-PHONE').replace('+70000000001', '+70000000002')
            self.applied('header', 'apply', self.intent('header', html))
            new = self.anonymous.get(self.host_url)
            self.assertIn(b'tel:+70000000002', self.body_bytes(new))
            context = self.context('header')
            token = self.owner_client.cookies[settings.CSRF_COOKIE_NAME].value
            restored_form = self.owner_client.post(
                f'/manage/shared/header/versions/{old.pk}/restore/',
                data={'expectedCurrentId': context['baseRevisionId'], 'confirmed': 'yes'},
                HTTP_X_CSRFTOKEN=token)
            self.assertEqual(restored_form.status_code, 302)
            restored = self.anonymous.get(self.host_url, HTTP_IF_NONE_MATCH=new['ETag'])
            self.assertEqual(restored.status_code, 200)
            body = self.body_bytes(restored)
            self.assertIn(b'tel:+70000000001', body)
            self.assertNotIn(b'tel:+70000000002', body)
            self.assertEqual(str(SharedBlock.objects.get(kind='footer').current_revision_id), footer['resultId'])
            old.refresh_from_db(); self.assertEqual(old.file_sha256, old_hash)
