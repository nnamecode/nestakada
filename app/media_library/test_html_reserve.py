from tempfile import TemporaryDirectory
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase, override_settings

from . import services
from .models import Asset, AssetFile, AssetUsage, MediaFolder
from .storage import MediaStorage


class RetainedHtmlTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.temp = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_LIBRARY_ROOT=self.temp.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.temp.cleanup)
        self.folder = MediaFolder.objects.create(path='html-reserve')
        self.storage = MediaStorage()

    def asset(self, *, ready=True):
        asset = Asset.objects.create(
            folder=self.folder, provenance='DEV25 retained test')
        services.write_file(
            asset_id=asset.pk, kind=AssetFile.Kind.MAIN,
            key='img/%s/main.webp' % asset.pk,
            chunks=b'RIFFxxxxWEBPfixture', storage=self.storage)
        return (services.mark_ready(asset_id=asset.pk, storage=self.storage)
                if ready else asset)

    def test_exact_ready_set_and_replay(self):
        generation = str(uuid4())
        assets = [self.asset(), self.asset()]
        ids = [str(asset.pk) for asset in reversed(assets)]
        result = services.set_retained_html(
            generation_id=generation, asset_ids=ids)
        self.assertEqual(result['created'], 2)
        self.assertFalse(result['replay'])
        rows = list(AssetUsage.objects.filter(
            kind=AssetUsage.Kind.RETAINED_HTML,
            consumer_id=generation).order_by('asset_id'))
        self.assertEqual([(str(row.asset_id), row.slot) for row in rows],
                         [(value, value) for value in sorted(ids)])
        replay = services.set_retained_html(
            generation_id=generation, asset_ids=ids)
        self.assertEqual(replay['created'], 0)
        self.assertTrue(replay['replay'])
        self.assertEqual(AssetUsage.objects.filter(
            kind=AssetUsage.Kind.RETAINED_HTML,
            consumer_id=generation).count(), 2)

    def test_not_ready_and_conflicting_generation_roll_back(self):
        generation = str(uuid4())
        ready, staged = self.asset(), self.asset(ready=False)
        with self.assertRaisesRegex(ValidationError, 'MEDIA_RETAINED_REQUIRES_READY'):
            services.set_retained_html(
                generation_id=generation,
                asset_ids=[str(ready.pk), str(staged.pk)])
        self.assertFalse(AssetUsage.objects.filter(
            kind=AssetUsage.Kind.RETAINED_HTML,
            consumer_id=generation).exists())
        services.set_retained_html(
            generation_id=generation, asset_ids=[str(ready.pk)])
        with self.assertRaisesRegex(
                ValidationError, 'MEDIA_RETAINED_GENERATION_CONFLICT'):
            services.set_retained_html(
                generation_id=generation,
                asset_ids=[str(ready.pk), str(self.asset().pk)])
        self.assertEqual(AssetUsage.objects.filter(
            kind=AssetUsage.Kind.RETAINED_HTML,
            consumer_id=generation).count(), 1)

    def test_release_and_reconcile_keep_only_active_generations(self):
        asset = self.asset()
        current, previous, stale = (str(uuid4()) for _ in range(3))
        for generation in (current, previous, stale):
            services.set_retained_html(
                generation_id=generation, asset_ids=[str(asset.pk)])
        self.assertEqual(services.reconcile_retained_html(
            active_generation_ids=[current, previous]), 1)
        self.assertEqual(set(str(value) for value in AssetUsage.objects.filter(
            kind=AssetUsage.Kind.RETAINED_HTML).values_list(
                'consumer_id', flat=True)), {current, previous})
        self.assertEqual(services.release_retained_html(
            generation_id=previous), 1)
        self.assertEqual(services.release_retained_html(
            generation_id=previous), 0)
