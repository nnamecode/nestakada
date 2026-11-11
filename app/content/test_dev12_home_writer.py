from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock, patch
from uuid import UUID

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import close_old_connections, models
from django.test import TransactionTestCase, override_settings

from accounts import services as auth
from accounts.tests import FAST_HASHERS, PASSWORD
from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder
from page_versions import engine, schema
from page_versions.models import OwnerDraft, PageContentState, PageRevision, VersionBasePin

from . import dev12_home_apply as home
from .models import Page, Route


def raw(model):
    return models.QuerySet(model=model, using='default')


@override_settings(
    PASSWORD_HASHERS=FAST_HASHERS, ENVIRONMENT='test',
    DEV12_HOME_APPLY_ENABLED=True,
)
class Dev12HomeWriterTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        self.package = home._read_package()
        self.create_parent()
        self.descriptors = home._media_descriptors(self.package)
        self.seed_assets()

    def create_parent(self):
        data = home.PARENT_DESCRIPTOR
        page = Page.objects.create(
            id=UUID(data['page_id']), name=data['name'], kind=data['kind'],
            parent_id=data['parent_id'], position=data['position'],
            is_published=False)
        Route.objects.create(
            page=page, target=data['url'], kind=Route.Kind.PRIMARY,
            is_legacy=True)
        payload = home._parent_payload()
        revision = engine.new_revision(
            page, None, payload, PageRevision.Kind.INITIAL, self.owner)
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

    def seed_assets(self):
        design = MediaFolder.objects.create(
            id=home.MEDIA_FOLDER_ID, path=home.MEDIA_FOLDER_PATH)
        legacy = MediaFolder.objects.create(path='legacy/gallery-home-fixture')
        assets, files = [], []
        for row in self.descriptors:
            assets.append(Asset(
                id=UUID(row['asset_id']),
                folder=legacy if row['legacy'] else design,
                status=Asset.Status.READY,
                provenance=('DEV10 gallery fixture' if row['legacy']
                            else home.PROVENANCE),
                is_legacy=row['legacy'], source_url=row['source_url'],
                source_sha256=row['source_sha256']))
            files.append(AssetFile(
                id=UUID(row['file_id']), asset_id=row['asset_id'],
                kind=row['kind'], key=row['key'], sha256=row['sha256'],
                byte_size=row['byte_size']))
        raw(Asset).bulk_create(assets); raw(AssetFile).bulk_create(files)

    def storage(self, *, wrong=False):
        expected = {row['key']:{'sha256':row['sha256'],
                                'byte_size':row['byte_size']}
                    for row in self.descriptors}
        storage = Mock()
        storage.manifest.side_effect = (
            (lambda _key: {'sha256':'0' * 64, 'byte_size':1}) if wrong
            else lambda key: expected[key])
        return storage

    def state(self):
        labels = ('content', 'page_versions', 'media_library', 'audit')
        return {model._meta.db_table:list(model.objects.order_by('pk').values())
                for label in labels
                for model in apps.get_app_config(label).get_models()}

    def assert_fault(self, code, action):
        with self.assertRaises(ValidationError) as caught:
            action()
        self.assertIn(code, caught.exception.messages)

    def test_writer_creates_exact_revision_draft_pin_usages_and_replays(self):
        storage = self.storage()
        result = home.apply_home(storage=storage)
        self.assertEqual(result, {
            'status':'pass', 'replayed':False, 'page_id':home.HOME_ID,
            'revision':2, 'assets':21, 'usages':63, 'published':0})
        payload = home._target_payload(self.package)
        self.assertTrue(home._exact_applied(self.owner, payload))
        self.assertEqual(AssetUsage.objects.count(), 63)
        before = self.state()
        replay = home.apply_home(storage=storage)
        self.assertTrue(replay['replayed'])
        self.assertEqual(self.state(), before)
        self.assertEqual(storage.manifest.call_count, 84)

    def test_changed_owner_draft_and_mixed_history_refuse_without_mutation(self):
        draft = OwnerDraft.objects.get(page_id=home.HOME_ID)
        raw(OwnerDraft).filter(pk=draft.pk).update(revision=2)
        before = self.state()
        self.assert_fault('HOME_EXISTING_CONFLICT',
                          lambda: home.apply_home(storage=self.storage()))
        self.assertEqual(self.state(), before)

    def test_late_audit_failure_rolls_back_revision_draft_pin_and_usages(self):
        before = self.state()
        with patch.object(home, 'record_event',
                          side_effect=RuntimeError('synthetic-home-event')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic-home-event'):
                home.apply_home(storage=self.storage())
        self.assertEqual(self.state(), before)

    def test_physical_failure_precedes_identity_and_sql_mutation(self):
        before = self.state()
        with patch.object(home, '_identity') as identity:
            self.assert_fault('HOME_MEDIA_UNAVAILABLE',
                              lambda: home.apply_home(storage=self.storage(wrong=True)))
        identity.assert_not_called()
        self.assertEqual(self.state(), before)

    @override_settings(DEV12_HOME_APPLY_ENABLED=False)
    def test_writer_is_default_off_before_package_read(self):
        with patch.object(home, '_read_package') as package:
            self.assert_fault('HOME_APPLY_DISABLED', lambda: home.apply_home())
        package.assert_not_called()

    def test_concurrent_writers_create_once_then_exact_replay(self):
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return home.apply_home(storage=self.storage())
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(sum(not row['replayed'] for row in results), 1)
        self.assertEqual(sum(row['replayed'] for row in results), 1)
        self.assertEqual(AssetUsage.objects.count(), 63)
