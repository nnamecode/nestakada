from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase, override_settings

from media_library.models import Asset, AssetFile
from media_library.storage import MediaStorage

from . import dev12_home_apply as home


@override_settings(ENVIRONMENT='test', DEV12_HOME_APPLY_ENABLED=True)
class Dev12HomeMediaImportTests(TransactionTestCase):
    reset_sequences = True

    def package(self, data=b'approved-home-image'):
        digest = __import__('hashlib').sha256(data).hexdigest()
        asset_id, file_id, image_id = str(uuid4()), str(uuid4()), str(uuid4())
        row = {'role':'hero', 'image_id':image_id, 'asset_id':asset_id,
               'file_id':file_id, 'local_file':'media/design-concepts/test.webp',
               'storage_key':f'img/{asset_id}/main.webp', 'kind':'main',
               'mime':'image/webp', 'bytes':len(data), 'sha256':digest,
               'alt':'Тестовое изображение'}
        return {'media':[row]}, row, data

    def roots(self, row, data):
        sources = TemporaryDirectory(); media = TemporaryDirectory()
        path = Path(sources.name, row['local_file'])
        path.parent.mkdir(parents=True); path.write_bytes(data)
        return sources, media

    def run_import(self, package, sources, media):
        with patch.object(home, '_read_package', return_value=package), \
                override_settings(MEDIA_LIBRARY_ROOT=media.name):
            return home.import_home_media(
                source_root=sources.name, storage=MediaStorage())

    def test_exact_reviewed_package_is_read_and_validated(self):
        package = home._read_package()
        self.assertEqual(package['schema'], 'dev12-home-package-v1')
        self.assertEqual(len(package['media']), 15)
        self.assertEqual(len(package['profile']['works']), 6)

    def test_import_creates_ready_exact_asset_and_replays_without_writes(self):
        package, row, data = self.package(); sources, media = self.roots(row, data)
        self.addCleanup(sources.cleanup); self.addCleanup(media.cleanup)
        first = self.run_import(package, sources, media)
        self.assertEqual(first, {'status':'pass', 'assets':1, 'created':1,
                                 'recovered':0, 'replayed':0})
        asset = Asset.objects.get(pk=row['asset_id'])
        file = AssetFile.objects.get(asset=asset)
        self.assertEqual(asset.status, Asset.Status.READY)
        self.assertEqual(str(file.pk), row['file_id'])
        second = self.run_import(package, sources, media)
        self.assertEqual(second, {'status':'pass', 'assets':1, 'created':0,
                                  'recovered':0, 'replayed':1})

    def test_failure_after_physical_write_leaves_recoverable_staged_asset(self):
        package, row, data = self.package(); sources, media = self.roots(row, data)
        self.addCleanup(sources.cleanup); self.addCleanup(media.cleanup)
        with patch.object(home, '_read_package', return_value=package), \
                patch.object(home.media_services, 'mark_ready',
                             side_effect=RuntimeError('synthetic-after-write')), \
                override_settings(MEDIA_LIBRARY_ROOT=media.name):
            with self.assertRaisesRegex(RuntimeError, 'synthetic-after-write'):
                home.import_home_media(
                    source_root=sources.name, storage=MediaStorage())
        self.assertEqual(Asset.objects.get(pk=row['asset_id']).status,
                         Asset.Status.STAGED)
        self.assertEqual(AssetFile.objects.filter(asset_id=row['asset_id']).count(), 1)
        recovered = self.run_import(package, sources, media)
        self.assertEqual(recovered['recovered'], 1)
        self.assertEqual(Asset.objects.get(pk=row['asset_id']).status,
                         Asset.Status.READY)

    def test_changed_source_or_registered_physical_file_fails_closed(self):
        package, row, data = self.package(); sources, media = self.roots(row, data)
        self.addCleanup(sources.cleanup); self.addCleanup(media.cleanup)
        Path(sources.name, row['local_file']).write_bytes(b'changed')
        with self.assertRaisesMessage(ValidationError,
                                      'HOME_MEDIA_SOURCE_UNAVAILABLE'):
            self.run_import(package, sources, media)
        Path(sources.name, row['local_file']).write_bytes(data)
        self.run_import(package, sources, media)
        Path(media.name, row['storage_key']).write_bytes(b'changed')
        with self.assertRaisesMessage(ValidationError,
                                      'HOME_MEDIA_PHYSICAL_MISMATCH'):
            self.run_import(package, sources, media)

    @override_settings(DEV12_HOME_APPLY_ENABLED=False)
    def test_default_off_precedes_package_and_filesystem_reads(self):
        with patch.object(home, '_read_package') as package:
            with self.assertRaisesMessage(ValidationError, 'HOME_APPLY_DISABLED'):
                home.import_home_media(source_root='missing')
        package.assert_not_called()
