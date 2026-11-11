from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock, patch
from uuid import UUID

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import close_old_connections, models, transaction
from django.test import TransactionTestCase, override_settings

from accounts import services as auth
from accounts.tests import FAST_HASHERS, PASSWORD
from audit.constants import Category, Level, Result, Source
from audit.models import AuditEvent
from audit.services import record_event
from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder
from page_versions import engine, schema
from page_versions.creation import initial_snapshot
from page_versions.models import (
    IdentityReservation, OwnerDraft, PageContentState, PageRevision,
    RevisionMetadata, VersionBasePin,
)

from . import dev10_gallery_apply as gallery
from .models import Page, Route


def raw(model):
    return models.QuerySet(model=model, using='default')


@override_settings(
    PASSWORD_HASHERS=FAST_HASHERS, ENVIRONMENT='test',
    DEV10_GALLERY_APPLY_ENABLED=True,
)
class Dev10GalleryWriterTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        self.package = gallery._read_package()
        self.create_exact_parent()

    def assert_fault(self, code, action):
        with self.assertRaises(ValidationError) as caught:
            action()
        self.assertIn(code, caught.exception.messages)

    def create_exact_parent(self):
        page = Page.objects.create(
            id=UUID(gallery.HOME_ID), name='Главная', kind=Page.Kind.HOME,
            position=0, is_published=False)
        Route.objects.create(
            page=page, target='/', kind=Route.Kind.PRIMARY, is_legacy=True)
        payload = initial_snapshot(
            Page.Kind.HOME, h1='АВТОТЕХЦЕНТР ЭСТАКАДА',
            title='Главная | Автосервис «Эстакада»').data(Page.Kind.HOME)
        revision = engine.new_revision(page, None, payload, 'initial', self.owner)
        PageContentState.objects.create(
            page=page, current_revision=revision, sequence=1)
        instant = engine.now()
        draft = OwnerDraft.objects.create(
            page=page, revision=1, base_revision=revision, payload=payload,
            payload_hash=schema.digest(payload), author_id=self.owner.pk,
            created_at=instant, updated_at=instant)
        VersionBasePin.objects.create(
            revision=revision, holder_kind='owner_draft', holder_id=draft.pk)
        record_event(
            category=Category.PAGES_LINKS,
            event_code='MIGRATION_PAGE_IMPORTED', level=Level.INFO,
            source=Source.APPLICATION, result=Result.SUCCESS,
            actor_id=self.owner.pk, object_kind='page', object_ref=page.pk)

    def seed_assets(self, *, wrong_first=False):
        folder = MediaFolder.objects.create(path='legacy/gallery')
        photos = gallery._photo_rows(self.package)
        assets = []
        files = []
        for index, photo in enumerate(photos):
            assets.append(Asset(
                id=UUID(photo['asset_id']), folder=folder,
                status=Asset.Status.READY, provenance='DEV10 test fixture',
                is_legacy=True, source_url=photo['source_url'],
                source_sha256=('0' * 64 if wrong_first and index == 0
                               else photo['sha256'])))
            files.append(AssetFile(
                id=UUID(photo['file_id']), asset_id=photo['asset_id'],
                kind=AssetFile.Kind.LEGACY_PUBLIC, key=photo['storage_key'],
                sha256=photo['sha256'], byte_size=photo['bytes']))
        raw(Asset).bulk_create(assets)
        raw(AssetFile).bulk_create(files)

    def storage(self, *, fail_first=False):
        expected = {photo['storage_key']: {
            'sha256': photo['sha256'], 'byte_size': photo['bytes']}
            for photo in gallery._photo_rows(self.package)}
        storage = Mock()
        if fail_first:
            storage.manifest.return_value = {'sha256': '0' * 64, 'byte_size': 1}
        else:
            storage.manifest.side_effect = lambda key: expected[key]
        return storage

    def state(self):
        labels = ('content', 'page_versions', 'media_library', 'audit')
        return {
            model._meta.db_table: list(model.objects.order_by('pk').values())
            for label in labels
            for model in apps.get_app_config(label).get_models()
        }

    def test_g10_writer_001_physical_failure_precedes_sql(self):
        with patch('content.dev10_gallery_apply._identity') as identity:
            self.assert_fault(
                'GALLERY_MEDIA_UNAVAILABLE',
                lambda: gallery.apply_gallery(storage=self.storage(fail_first=True)))
        identity.assert_not_called()

    def test_g10_writer_002_create_exact_aggregate_and_zero_write_replay(self):
        self.seed_assets()
        storage = self.storage()
        result = gallery.apply_gallery(storage=storage)
        self.assertEqual(result, {
            'status': 'pass', 'replayed': False, 'pages': 18, 'routes': 19,
            'photos': 214, 'usages': 642, 'published': 0})
        self.assertEqual(Page.objects.filter(
            pk__in=[page['page_id'] for page in [
                self.package['root'], *self.package['albums']]]).count(), 18)
        gallery_ids = [page['page_id'] for page in [
            self.package['root'], *self.package['albums']]]
        revisions = PageRevision.objects.filter(page_id__in=gallery_ids)
        drafts = OwnerDraft.objects.filter(page_id__in=gallery_ids)
        self.assertEqual(Route.objects.filter(page_id__in=gallery_ids).count(), 19)
        self.assertEqual(revisions.count(), 18)
        self.assertEqual(PageContentState.objects.filter(
            page_id__in=gallery_ids).count(), 18)
        self.assertEqual(drafts.count(), 18)
        self.assertEqual(RevisionMetadata.objects.filter(
            revision__page_id__in=gallery_ids).count(), 18)
        self.assertEqual(VersionBasePin.objects.filter(
            revision__page_id__in=gallery_ids).count(), 18)
        self.assertEqual(IdentityReservation.objects.filter(
            pk__in=[*revisions.values_list('pk', flat=True),
                    *drafts.values_list('pk', flat=True)]).count(), 36)
        self.assertEqual(AuditEvent.objects.filter(
            code='MIGRATION_PAGE_IMPORTED',
            object_ref__in=['uuid:' + value for value in gallery_ids]).count(), 18)
        self.assertEqual(AssetUsage.objects.count(), 642)
        self.assertEqual(storage.manifest.call_count, 214)
        before = self.state()
        replay = gallery.apply_gallery(storage=storage)
        self.assertTrue(replay['replayed'])
        self.assertEqual(storage.manifest.call_count, 428)
        self.assertEqual(self.state(), before)

    def test_g10_writer_003_descriptor_drift_rolls_back_content(self):
        self.seed_assets(wrong_first=True)
        before = self.state()
        self.assert_fault(
            'GALLERY_MEDIA_UNAVAILABLE',
            lambda: gallery.apply_gallery(storage=self.storage()))
        self.assertEqual(self.state(), before)

    def test_g10_writer_004_mixed_state_is_not_completed(self):
        self.seed_assets()
        root = self.package['root']
        with transaction.atomic():
            gallery._create_aggregate(
                root, self.owner, gallery._payload(root),
                alias=root['page2_alias'])
        before = self.state()
        self.assert_fault(
            'GALLERY_EXISTING_CONFLICT',
            lambda: gallery.apply_gallery(storage=self.storage()))
        self.assertEqual(self.state(), before)

    def test_g10_writer_005_identity_is_first_sql_before_locks(self):
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
        with patch.object(gallery.connection, 'cursor', return_value=cursor), \
                patch('content.dev10_gallery_apply.lock_content') as content_lock, \
                patch('content.dev10_gallery_apply.lock_auth') as auth_lock:
            self.assert_fault(
                'GALLERY_APPLY_DISABLED',
                lambda: gallery.apply_gallery(storage=self.storage()))
        self.assertEqual(cursor.statement,
                         'SELECT current_database(), current_user')
        content_lock.assert_not_called()
        auth_lock.assert_not_called()
        self.assertEqual(self.state(), before)

    def test_g10_writer_006_late_failure_rolls_back_every_gallery_row(self):
        self.seed_assets()
        before = self.state()
        original = gallery.record_event
        calls = 0

        def fail_last(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 18:
                raise RuntimeError('SYNTHETIC_GALLERY_LAST_EVENT_FAILURE')
            return original(**kwargs)

        with patch('content.dev10_gallery_apply.record_event',
                   side_effect=fail_last):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_GALLERY_LAST_EVENT_FAILURE'):
                gallery.apply_gallery(storage=self.storage())
        self.assertEqual(self.state(), before)

    def test_g10_writer_007_extra_child_refuses_replay_without_mutation(self):
        self.seed_assets()
        gallery.apply_gallery(storage=self.storage())
        Page.objects.create(
            name='Unexpected gallery child', kind=Page.Kind.ALBUM,
            parent_id=gallery.ROOT_ID, position=17, is_published=False)
        before = self.state()
        self.assert_fault(
            'GALLERY_EXISTING_CONFLICT',
            lambda: gallery.apply_gallery(storage=self.storage()))
        self.assertEqual(self.state(), before)

    def test_g10_writer_008_concurrent_calls_create_once_then_replay(self):
        self.seed_assets()
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return gallery.apply_gallery(storage=self.storage())
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(sum(not row['replayed'] for row in results), 1)
        self.assertEqual(sum(row['replayed'] for row in results), 1)
        self.assertEqual(AssetUsage.objects.count(), 642)
