from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
import stat
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings

from accounts import services as auth
from accounts.tests import FAST_HASHERS, PASSWORD
from audit.constants import Category, Level, Result, Source
from audit.models import AuditEvent
from audit.services import record_event
from page_editor.clean import restricted_clean
from page_versions.models import (
    IdentityReservation, OwnerDraft, PageContentState, PageRevision,
    RevisionMetadata, VersionBasePin,
)

from . import dev09_migration_apply as migration
from .models import Page, Route
from .reads import public_tree


@override_settings(
    PASSWORD_HASHERS=FAST_HASHERS, ENVIRONMENT='test',
    DEV09_MIGRATION_APPLY_ENABLED=True,
)
class Dev09MigrationApplyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        self.page_ids = [UUID(row[1]) for row in migration.EXPECTED]

    def state(self):
        labels = ('content', 'page_versions', 'media_library', 'audit')
        return {
            model._meta.db_table: list(model.objects.order_by('pk').values())
            for label in labels
            for model in apps.get_app_config(label).get_models()
        }

    def assert_fault(self, code, action):
        with self.assertRaises(ValidationError) as caught:
            action()
        self.assertIn(code, caught.exception.messages)

    def test_migw_create_exact_hidden_aggregates_and_safe_article(self):
        self.assertEqual(
            (connection.settings_dict['NAME'], connection.settings_dict['USER']),
            ('estakada_foundation_unit', 'app_migrator'))
        result = migration.apply_articles_slice()
        self.assertEqual(result, {
            'status': 'pass', 'replayed': False, 'pages': 20, 'published': 0})
        pages = list(Page.objects.filter(pk__in=self.page_ids).order_by('id'))
        self.assertEqual(len(pages), 20)
        package = migration._read_package()
        for page_data in package['pages']:
            page = Page.objects.get(pk=page_data['page_id'])
            self.assertEqual(
                (page.name, page.kind,
                 str(page.parent_id) if page.parent_id else None,
                 page.position, page.is_published),
                (page_data['name'], page_data['kind'], page_data['parent_id'],
                 page_data['position'], False))
            route = Route.objects.get(page=page)
            self.assertEqual(
                (route.kind, route.target, route.is_legacy),
                (Route.Kind.PRIMARY, page_data['url'], True))
            revision = PageRevision.objects.get(page=page)
            state = PageContentState.objects.get(page=page)
            draft = OwnerDraft.objects.get(page=page)
            metadata = RevisionMetadata.objects.get(revision=revision)
            pin = VersionBasePin.objects.get(revision=revision)
            payload = migration._expected_payload(page_data)
            self.assertEqual(
                (revision.sequence, revision.kind, revision.payload,
                 revision.author_id, state.sequence,
                 state.current_revision_id),
                (1, PageRevision.Kind.INITIAL, payload, self.owner.pk, 1,
                 revision.pk))
            self.assertEqual(
                (draft.base_revision_id, draft.payload, draft.author_id,
                 pin.holder_kind, pin.holder_id),
                (revision.pk, payload, self.owner.pk, 'owner_draft', draft.pk))
            self.assertEqual(
                (metadata.generation, metadata.name, metadata.comment,
                 metadata.manual_date), (1, '', '', None))
            self.assertEqual(
                set(IdentityReservation.objects.filter(
                    pk__in=[revision.pk, draft.pk]).values_list('kind', flat=True)),
                {'pagerevision', 'ownerdraft'})
            event = AuditEvent.objects.get(
                code='MIGRATION_PAGE_IMPORTED',
                object_ref='uuid:' + str(page.pk))
            self.assertEqual(
                (event.category, event.level, event.source, event.result,
                 event.actor_id, event.object_kind, event.request_id,
                 event.ip_address, event.occurrence_count,
                 event.count_is_lower_bound),
                (Category.PAGES_LINKS, Level.INFO, Source.APPLICATION,
                 Result.SUCCESS, self.owner.pk, 'page', None, None, 1, False))
        self.assertEqual(
            PageRevision.objects.get(page_id=self.page_ids[0]).payload['main_text'], '')
        self.assertEqual(
            PageRevision.objects.get(page_id=self.page_ids[1]).payload['main_text'], '')
        article_html = PageRevision.objects.get(
            page_id=self.page_ids[2]).payload['main_text']
        self.assertEqual(article_html,
                         migration._expected_payload(package['pages'][2])['main_text'])
        list_html = PageRevision.objects.get(
            page_id=next(row['page_id'] for row in package['pages']
                         if row['map_id'] == 'MAP-065')).payload['main_text']
        self.assertEqual(list_html.count('<ul>'), 1)
        self.assertEqual(list_html.count('<li>'), 4)
        break_html = PageRevision.objects.get(
            page_id=next(row['page_id'] for row in package['pages']
                         if row['map_id'] == 'MAP-103')).payload['main_text']
        self.assertEqual(break_html.count('<br>'), 3)
        nbsp_html = PageRevision.objects.get(
            page_id=next(row['page_id'] for row in package['pages']
                         if row['map_id'] == 'MAP-108')).payload['main_text']
        self.assertIn('<p>&nbsp;</p>', nbsp_html)
        for html in (article_html, list_html, break_html, nbsp_html):
            self.assertEqual(restricted_clean(html), html)
            self.assertNotIn('<script', html.lower())
        public_ids = {row['id'] for row in public_tree()}
        self.assertTrue(set(self.page_ids).isdisjoint(public_ids))

    def test_migw_exact_replay_has_zero_mutation(self):
        migration.apply_articles_slice()
        before = self.state()
        result = migration.apply_articles_slice()
        self.assertTrue(result['replayed'])
        self.assertEqual(self.state(), before)

    def test_migw_disabled_and_wrong_target_stop_before_package(self):
        with override_settings(DEV09_MIGRATION_APPLY_ENABLED=False), patch(
                'content.dev09_migration_apply._read_package') as package:
            self.assert_fault('MIGRATION_APPLY_DISABLED',
                              migration.apply_articles_slice)
            package.assert_not_called()

    def test_migw_actual_identity_mismatch_precedes_locks_and_mutation(self):
        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, statement):
                self.statement = statement

            def fetchone(self):
                return ('estakada_foundation', 'app_runtime')

        cursor = Cursor()
        before = self.state()
        with patch.object(migration.connection, 'cursor',
                          return_value=cursor), patch(
                'content.dev09_migration_apply.lock_content') as content_lock, patch(
                'content.dev09_migration_apply.lock_auth') as auth_lock:
            self.assert_fault('MIGRATION_APPLY_DISABLED',
                              migration.apply_articles_slice)
            content_lock.assert_not_called()
            auth_lock.assert_not_called()
        self.assertEqual(cursor.statement,
                         'SELECT current_database(), current_user')
        self.assertEqual(self.state(), before)
        with patch.dict(connection.settings_dict,
                        {'NAME': 'estakada_foundation'}, clear=False), patch(
                'content.dev09_migration_apply._read_package') as package:
            self.assert_fault('MIGRATION_APPLY_DISABLED',
                              migration.apply_articles_slice)
            package.assert_not_called()

    def test_migw_package_schema_and_duplicate_keys_fail_closed(self):
        value = migration._read_package()
        changed = deepcopy(value)
        changed['pages'][2]['map_id'] = 'MAP-999'
        self.assert_fault('MIGRATION_PACKAGE_INVALID',
                          lambda: migration._validate_package(changed))
        self.assert_fault('MIGRATION_PACKAGE_INVALID',
                          lambda: migration._pairs([('x', 1), ('x', 2)]))
        changed = deepcopy(value)
        changed['schema'] = 'dev09-articles-slice-v1'
        self.assert_fault('MIGRATION_PACKAGE_INVALID',
                          lambda: migration._validate_package(changed))
        changed = deepcopy(value)
        changed['pages'][2]['blocks'][0]['extra'] = True
        self.assert_fault('MIGRATION_PACKAGE_INVALID',
                          lambda: migration._validate_package(changed))
        changed = deepcopy(value)
        changed['pages'][2]['blocks'][0]['segments'].append('extra')
        self.assert_fault('MIGRATION_PACKAGE_INVALID',
                          lambda: migration._validate_package(changed))

    def test_migw_package_sha_and_realpath_fail_closed(self):
        with patch('content.dev09_migration_apply.hashlib.sha256') as digest:
            digest.return_value.hexdigest.return_value = '0' * 64
            self.assert_fault('MIGRATION_PACKAGE_INVALID',
                              migration._read_package)

    def test_migw_package_fd_type_size_cr_and_utf8_fail_closed(self):
        with patch.object(migration.os, 'O_NOFOLLOW', None):
            self.assert_fault('MIGRATION_PACKAGE_UNSUPPORTED',
                              migration._read_package)
        with patch('content.dev09_migration_apply.os.open',
                   side_effect=OSError('synthetic')):
            self.assert_fault('MIGRATION_PACKAGE_INVALID',
                              migration._read_package)
        for info in (
                SimpleNamespace(st_mode=stat.S_IFDIR, st_size=1),
                SimpleNamespace(st_mode=stat.S_IFREG, st_size=65537)):
            with self.subTest(info=info), patch(
                    'content.dev09_migration_apply.os.open', return_value=99), patch(
                    'content.dev09_migration_apply.os.fstat', return_value=info), patch(
                    'content.dev09_migration_apply.os.close'):
                self.assert_fault('MIGRATION_PACKAGE_INVALID',
                                  migration._read_package)
        for content in (b'\r', b'\xff'):
            info = SimpleNamespace(st_mode=stat.S_IFREG, st_size=len(content))
            with self.subTest(content=content), patch(
                    'content.dev09_migration_apply.os.open', return_value=99), patch(
                    'content.dev09_migration_apply.os.fstat', return_value=info), patch(
                    'content.dev09_migration_apply.os.fdopen',
                    side_effect=lambda *_args, data=content: BytesIO(data)), patch(
                    'content.dev09_migration_apply.hashlib.sha256') as digest:
                digest.return_value.hexdigest.return_value = migration.PACKAGE_SHA256
                self.assert_fault('MIGRATION_PACKAGE_INVALID',
                                  migration._read_package)
        with patch('content.dev09_migration_apply.os.path.realpath',
                   return_value='/outside/package.json'):
            self.assert_fault('MIGRATION_PACKAGE_INVALID',
                              migration._read_package)

    def test_migw_snapshot_escapes_plain_text_without_trusted_html(self):
        page = deepcopy(migration._read_package()['pages'][2])
        page['blocks'] = [
            {'type': 'paragraph', 'segments': [
                '<script>alert(1)</script>', 'A&B', '"quoted"']},
            {'type': 'unordered_list', 'items': [
                '<img src=x onerror=alert(1)>', "O'Reilly"]},
        ]
        main = migration._snapshot(page).data(page['kind'])['main_text']
        self.assertEqual(
            main,
            '<p>&lt;script&gt;alert(1)&lt;/script&gt;<br>A&amp;B<br>'
            '"quoted"</p><ul><li>&lt;img src=x onerror=alert(1)&gt;'
            "</li><li>O'Reilly</li></ul>")
        self.assertEqual(restricted_clean(main), main)

    def test_migw_partial_or_orphan_state_refuses_without_mutation(self):
        Page.objects.create(
            id=self.page_ids[0], name='Главная', kind=Page.Kind.HOME,
            position=0, is_published=False)
        before = self.state()
        self.assert_fault('MIGRATION_EXISTING_CONFLICT',
                          migration.apply_articles_slice)
        self.assertEqual(self.state(), before)

    def test_migw_orphan_audit_refuses_and_audit_failure_rolls_back(self):
        record_event(
            category=Category.PAGES_LINKS,
            event_code='MIGRATION_PAGE_IMPORTED', level=Level.INFO,
            source=Source.APPLICATION, result=Result.SUCCESS,
            actor_id=self.owner.pk, object_kind='page',
            object_ref=self.page_ids[0])
        before = self.state()
        self.assert_fault('MIGRATION_EXISTING_CONFLICT',
                          migration.apply_articles_slice)
        self.assertEqual(self.state(), before)

    def test_migw_route_uuid_and_reservation_collisions_refuse(self):
        unrelated = Page.objects.create(
            name='Unrelated', kind=Page.Kind.ARTICLE, position=7,
            is_published=False)
        Route.objects.create(
            id=self.page_ids[0], page=unrelated, kind=Route.Kind.PRIMARY,
            target='/unrelated/')
        before = self.state()
        self.assert_fault('MIGRATION_EXISTING_CONFLICT',
                          migration.apply_articles_slice)
        self.assertEqual(self.state(), before)

    def test_migw_identity_reservation_collision_refuses(self):
        IdentityReservation.objects.create(
            id=self.page_ids[0], kind='synthetic')
        before = self.state()
        self.assert_fault('MIGRATION_EXISTING_CONFLICT',
                          migration.apply_articles_slice)
        self.assertEqual(self.state(), before)

    def test_migw_extra_migration_event_breaks_exact_replay(self):
        migration.apply_articles_slice()
        record_event(
            category=Category.PAGES_LINKS,
            event_code='MIGRATION_PAGE_IMPORTED', level=Level.INFO,
            source=Source.APPLICATION, result=Result.SUCCESS,
            actor_id=self.owner.pk, object_kind='page',
            object_ref=self.page_ids[0])
        before = self.state()
        self.assert_fault('MIGRATION_EXISTING_CONFLICT',
                          migration.apply_articles_slice)
        self.assertEqual(self.state(), before)

    def test_migw_extra_pin_held_by_imported_draft_breaks_replay(self):
        migration.apply_articles_slice()
        draft = OwnerDraft.objects.get(page_id=self.page_ids[0])
        unrelated_revision = PageRevision.objects.get(page_id=self.page_ids[1])
        VersionBasePin.objects.create(
            revision=unrelated_revision, holder_kind='owner_draft',
            holder_id=draft.pk)
        before = self.state()
        self.assert_fault('MIGRATION_EXISTING_CONFLICT',
                          migration.apply_articles_slice)
        self.assertEqual(self.state(), before)

    def test_migw_late_audit_failure_rolls_back_all_twenty(self):
        real = record_event
        calls = {'count': 0}
        before = self.state()

        def fail_second(**values):
            calls['count'] += 1
            if calls['count'] == len(migration.EXPECTED):
                raise RuntimeError('SYNTHETIC_MIGRATION_AUDIT_FAILURE')
            return real(**values)

        with patch('content.dev09_migration_apply.record_event',
                   side_effect=fail_second):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_MIGRATION_AUDIT_FAILURE'):
                migration.apply_articles_slice()
        self.assertFalse(Page.objects.filter(pk__in=self.page_ids).exists())
        urls = [row['url'] for row in migration._read_package()['pages']]
        self.assertFalse(Route.objects.filter(target__in=urls).exists())
        self.assertFalse(AuditEvent.objects.filter(
            code='MIGRATION_PAGE_IMPORTED').exists())
        self.assertEqual(self.state(), before)

    def test_migw_inactive_owner_refuses_without_pages(self):
        self.owner.is_active = False
        self.owner.save(update_fields=['is_active'])
        with self.assertRaises(PermissionDenied):
            migration.apply_articles_slice()
        self.assertFalse(Page.objects.filter(pk__in=self.page_ids).exists())

    def test_migw_concurrent_calls_create_once_then_replay(self):
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return migration.apply_articles_slice()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(sum(not row['replayed'] for row in results), 1)
        self.assertEqual(sum(row['replayed'] for row in results), 1)
        self.assertEqual(Page.objects.filter(pk__in=self.page_ids).count(), 20)
        self.assertEqual(AuditEvent.objects.filter(
            code='MIGRATION_PAGE_IMPORTED').count(), 20)
