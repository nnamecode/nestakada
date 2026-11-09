"""Owner-only read HTTP evidence, not public rendering or native RAM proof.

Snapshots/current pointers are explicit test setup, never accepted product Apply.
Reuse fixture methods by binding; do not inherit/collect the 17 write/check tests.
"""
import hashlib
from uuid import uuid4

import html5lib
from django.db import connection, transaction
from django.test import TransactionTestCase, override_settings

from shared_content import test_shared_http as Q
from shared_content.models import SharedBlock, SharedRevision


@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SharedReadHttpTests(TransactionTestCase):
    setUp = Q.SharedHttpTests.setUp
    login = Q.SharedHttpTests.login
    raw = Q.SharedHttpTests.raw
    fixture = Q.SharedHttpTests.fixture
    state = Q.SharedHttpTests.state
    path = Q.SharedHttpTests.path
    assert_private = Q.SharedHttpTests.assert_private

    def parsed(self, response):
        self.assertEqual(response.status_code, 200, 'OWNER_SHARED_READ_REFUSED')
        self.assert_private(response)
        # Framework profile reports CSP; enforced ingress CSP is a separate
        # real-Nginx check, not evidence supplied by Django Client.
        self.assertIn("default-src 'self'", response.get('Content-Security-Policy-Report-Only', ''))
        return html5lib.parse(response.content.decode('utf-8'), treebuilder='etree',
                              namespaceHTMLElements=False)

    def marked_text(self, tree, marker):
        nodes = [node for node in tree.iter() if marker in node.attrib]
        self.assertEqual(len(nodes), 1, 'SHARED_READ_SLOT_COUNT')
        return ''.join(nodes[0].itertext())

    def history_fixture(self, kind):
        block = SharedBlock.objects.get(kind=kind)
        old_html = self.fixture(kind, 'OLD-PRIVATE-' + kind)
        old = SharedRevision.objects.create(block=block, sequence=1,
            schema_version=kind + '-v1', html=old_html,
            payload_hash=hashlib.sha256(old_html.encode()).hexdigest(), author_id=self.owner.pk)
        current_html = self.fixture(kind, 'CURRENT-PRIVATE-' + kind).replace(
            '+70000000001', '+70000000002')
        current = SharedRevision.objects.create(block=block, sequence=2,
            schema_version=kind + '-v1', html=current_html,
            payload_hash=hashlib.sha256(current_html.encode()).hexdigest(), author_id=self.owner.pk)
        # Explicit fixture pointer installation, not a service/Apply acceptance.
        with transaction.atomic(), connection.cursor() as cursor:
            from content.models import lock_content
            lock_content('default')
            cursor.execute('UPDATE ' + connection.ops.quote_name(SharedBlock._meta.db_table) +
                ' SET current_revision_id=%s,generation=2 WHERE id=%s', [current.pk, block.pk])
        return old, current

    def test_owner_empty_editor_and_history_are_private_read_only(self):
        before = self.state()
        for kind in ('header', 'footer'):
            with self.subTest(kind=kind):
                tree = self.parsed(self.owner_client.get(self.path(kind)))
                inputs = [node for node in tree.iter('textarea') if node.attrib.get('id') == 'shared-html']
                self.assertEqual(len(inputs), 1)
                self.assertEqual(''.join(inputs[0].itertext()), '')
                text = ''.join(tree.itertext())
                self.assertIn('Проверить Сохранить черновик Применить к сайту', text)
                self.assertNotIn('Применение и сохранение пока недоступны', text)
                self.assertIn('Меню строится по текущей структуре сайта', text)
                history = self.parsed(self.owner_client.get(self.path(kind, 'history')))
                self.assertIn('История пуста.', ''.join(history.itertext()))
                self.assertEqual(self.state(), before)

    def test_owner_history_version_and_compare_preserve_old_literal_and_current(self):
        for kind in ('header', 'footer'):
            old, current = self.history_fixture(kind)
            before = self.state()
            listing = self.parsed(self.owner_client.get(self.path(kind, 'history')))
            ids = [node.attrib['data-shared-version'] for node in listing.iter()
                   if 'data-shared-version' in node.attrib]
            self.assertEqual(ids, [str(current.pk), str(old.pk)])
            version = self.parsed(self.owner_client.get(self.path(kind, 'versions/' + str(old.pk))))
            self.assertEqual(self.marked_text(version, 'data-saved-html'), old.html)
            comparison = self.parsed(self.owner_client.get(
                self.path(kind, 'compare') + '?versionId=' + str(old.pk)))
            self.assertEqual(self.marked_text(comparison, 'data-saved-html'), old.html)
            self.assertEqual(self.marked_text(comparison, 'data-current-html'), current.html)
            if kind == 'header':
                self.assertIn('+70000000001', self.marked_text(comparison, 'data-saved-html'))
                self.assertIn('+70000000002', self.marked_text(comparison, 'data-current-html'))
                self.assertNotIn('+70000000002', self.marked_text(comparison, 'data-saved-html'))
            editor = self.parsed(self.owner_client.get(self.path(kind)))
            inputs = [node for node in editor.iter('textarea') if node.attrib.get('id') == 'shared-html']
            self.assertEqual(len(inputs), 1)
            self.assertEqual(''.join(inputs[0].itertext()), current.html)
            self.assertEqual(self.state(), before, 'OWNER_READ_CHANGED_HISTORY_OR_CURRENT')

    def test_unknown_schema_is_escaped_readable_data_and_not_an_executed_component(self):
        block = SharedBlock.objects.get(kind='header')
        source = '<script data-unsafe-history="yes">HISTORY-UNSAFE-CANARY</script>'
        source += '<img src="https://example.invalid/history" onerror="HISTORY-UNSAFE-CANARY">'
        row = SharedRevision.objects.create(block=block, sequence=1,
            schema_version='unknown-test-v99', html=source,
            payload_hash=hashlib.sha256(source.encode()).hexdigest(), author_id=self.owner.pk)
        before = self.state()
        for url in (self.path('header', 'versions/' + str(row.pk)),
                    self.path('header', 'compare') + '?versionId=' + str(row.pk)):
            tree = self.parsed(self.owner_client.get(url))
            self.assertEqual(self.marked_text(tree, 'data-saved-html'), source)
            self.assertFalse(any('data-unsafe-history' in node.attrib for node in tree.iter()),
                             'HISTORICAL_SCRIPT_BECAME_LIVE_DOM')
            self.assertFalse(any(node.attrib.get('src') == 'https://example.invalid/history'
                                 for node in tree.iter()), 'HISTORICAL_IMAGE_BECAME_LIVE_DOM')
            if '/versions/' in url:
                self.assertIn('Версия несовместима', ''.join(tree.itertext()))
            self.assertEqual(self.state(), before)
        # Parser/response evidence only: no browser, network or runtime trace claim.

    def test_crossblock_and_missing_version_reads_do_not_disclose_or_mutate(self):
        old, _ = self.history_fixture('footer')
        before = self.state()
        urls = (self.path('header', 'versions/' + str(old.pk)),
                self.path('header', 'compare') + '?versionId=' + str(old.pk),
                self.path('header', 'versions/' + str(uuid4())),
                self.path('header', 'compare') + '?versionId=' + str(uuid4()))
        for url in urls:
            response = self.owner_client.get(url)
            self.assertEqual(response.status_code, 404)
            self.assert_private(response)
            self.assertNotIn(b'OLD-PRIVATE-footer', response.content)
            self.assertEqual(self.state(), before)
