import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from content.models import Page
from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder
from media_library.storage import MediaStorage
from page_versions import schema

from . import dev09_migration_apply as migration


PACKAGE = Path(__file__).with_name('dev09n_remaining_content.json')
PACKAGE_SHA256 = '4b679b676b5e1ba1d2a5971799695d8ef944da9015c1f2270aee9d8878f09c30'
PAGE_IDS = [
    'ffdbdc65-39d8-4e22-88e3-7e44e752fbde',
    'b427b1b8-2fb9-44cd-a301-5b14f2f991b2',
    'df6b50bb-d749-4106-b053-2999e0335223',
    '91631e35-5e81-407f-806b-e973223d7340',
    '87cf5862-20fd-4ad3-b90c-bb4d6e888355',
    'e3c55ade-799b-4118-88b8-3fb03deea235',
    '9b5b3c53-d8c7-4395-89e5-6d07645f0d61',
    'da5e675f-fedf-4c4e-a3b4-c82d6a6dafcb',
    '62228d71-44ce-44da-82b5-85ba9c7d93dd',
    'f30b0e81-5ac6-4779-bb0e-65dc3ae5c301',
    '13fe0f8c-001c-446a-8cb7-b588fcdb1916',
    'f1c97615-2220-4732-a9cb-d5979d6500b2',
    '06f43591-ff13-4409-89ef-823534b5b33e',
]
IMAGE_IDS = [
    'edd55fd1-91cf-4e20-8cfc-2f5e9861dcc1',
    '0721a988-5dc4-42a4-b73e-8bb2f27705ca',
    '4f680d0d-66e0-41a4-8361-6a85b84d9bba',
    '94c7fa00-3395-465f-abbe-d991bedbcd0e',
    '5857c071-6e81-460d-9fac-519bae6a0ebc',
    '7efdc034-f931-4397-be93-fe503a19eeca',
    '191e8b95-af10-423e-9507-59a7c62be591',
]
CONTACT_KEYS = (
    'phone_display', 'phone_href', 'address', 'hours', 'email_display',
    'email_href', 'route_href', 'gallery_heading',
)


class Dev09NPackageAndContactsSchemaTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.package_bytes = PACKAGE.read_bytes()
        cls.package = json.loads(cls.package_bytes.decode('utf-8'))
        package_profile = next(
            page['profile'] for page in cls.package['pages']
            if page['map_id'] == 'MAP-007')
        cls.contacts = {
            key: copy.deepcopy(package_profile[key]) for key in CONTACT_KEYS}

    def payload(self, profile=None, *, kind=Page.Kind.CONTACTS):
        value = schema.snapshot_v1(kind, h1='Контакты').data(kind)
        value['contacts_profile'] = copy.deepcopy(profile or self.contacts)
        return value

    def assert_invalid(self, payload):
        with self.assertRaisesMessage(ValidationError, 'VERSIONS_INVALID_SNAPSHOT'):
            schema.Snapshot.trusted(payload, payload['page_kind'])

    def test_dev09n_001_package_is_canonical_bounded_and_exact_identity(self):
        self.assertLessEqual(len(self.package_bytes), 128 * 1024)
        self.assertEqual(hashlib.sha256(self.package_bytes).hexdigest(), PACKAGE_SHA256)
        self.assertEqual(
            self.package_bytes,
            (json.dumps(self.package, ensure_ascii=False, indent=2) + '\n').encode())
        self.assertEqual([page['page_id'] for page in self.package['pages']], PAGE_IDS)
        self.assertEqual([item['image_id'] for item in self.package['media']], IMAGE_IDS)
        self.assertEqual(len({item['asset_id'] for item in self.package['media']}), 7)
        self.assertEqual(len({item['file_id'] for item in self.package['media']}), 7)
        self.assertLessEqual(sum(item['bytes'] for item in self.package['media']), 2 * 1024 * 1024)

    def test_dev09n_002_exact_contacts_profile_is_accepted_and_copied(self):
        payload = self.payload()
        result = schema.Snapshot.trusted(payload, Page.Kind.CONTACTS).data(Page.Kind.CONTACTS)
        self.assertEqual(result['contacts_profile'], self.contacts)
        self.contacts['phone_display'] = 'mutation after validation'
        self.addCleanup(self.contacts.__setitem__, 'phone_display', '+7 (499) 110-25-52')
        self.assertEqual(result['contacts_profile']['phone_display'], '+7 (499) 110-25-52')

    def test_dev09n_003_profile_is_contacts_only_and_closed(self):
        self.assert_invalid(self.payload(kind=Page.Kind.ARTICLE))
        changed = self.payload()
        changed['contacts_profile']['unknown'] = True
        self.assert_invalid(changed)
        changed = self.payload()
        changed['contacts_profile'].pop('gallery_heading')
        self.assert_invalid(changed)

    def test_dev09n_004_contact_literals_and_schemes_fail_closed(self):
        mutations = {
            'phone_display': '8 (903) 772-33-43',
            'phone_href': 'tel:+79037723343',
            'email_display': 'other@example.test',
            'email_href': 'mailto:other@example.test',
            'route_href': 'javascript:alert(1)',
            'address': 'Другой адрес',
            'hours': 'Круглосуточно',
            'gallery_heading': '<script>x</script>',
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                changed = self.payload()
                changed['contacts_profile'][field] = value
                self.assert_invalid(changed)
        for route in ('data:text/html,x', 'https://user@example.test/',
                      'https://example.test/#fragment', 'https://example.test/\n'):
            with self.subTest(route=route):
                changed = self.payload()
                changed['contacts_profile']['route_href'] = route
                self.assert_invalid(changed)

    def test_dev09n_005_profile_caps_reject_before_storage(self):
        for field, value in (
                ('phone_display', 'x' * 65), ('phone_href', 'x' * 65),
                ('address', 'x' * 256), ('hours', 'x' * 129),
                ('email_display', 'x' * 255), ('email_href', 'x' * 262),
                ('route_href', 'x' * 2049), ('gallery_heading', 'x' * 129)):
            with self.subTest(field=field):
                changed = self.payload()
                changed['contacts_profile'][field] = value
                self.assert_invalid(changed)

    def test_dev09n_006_package_contains_no_executable_or_removed_contact(self):
        text = self.package_bytes.decode('utf-8').lower()
        for forbidden in ('8 (903) 772-33-43', '<script', '<iframe', '<form',
                          'javascript:', 'data:', '{%', '{{'):
            self.assertNotIn(forbidden, text)
        self.assertIn('+7 (499) 110-25-52', text)
        self.assertIn('estakada10@yandex.ru', text)


@override_settings(DEV09_MIGRATION_APPLY_ENABLED=True)
class Dev09NRemainingMediaTests(TransactionTestCase):
    reset_sequences = True

    def fixture(self):
        package = copy.deepcopy(json.loads(PACKAGE.read_text(encoding='utf-8')))
        sources = TemporaryDirectory()
        media = TemporaryDirectory()
        self.addCleanup(sources.cleanup)
        self.addCleanup(media.cleanup)
        for index, row in enumerate(package['media']):
            content = f'dev09n-exact-media-{index}'.encode()
            suffix = Path(row['relative_path']).suffix
            row['relative_path'] = f'media/dev09n-test/{index}{suffix}'
            row['bytes'] = len(content)
            row['sha256'] = hashlib.sha256(content).hexdigest()
            source = Path(sources.name, row['relative_path'])
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(content)
        return package, sources.name, media.name

    def test_dev09n_101_exact7_prepare_and_zero_write_replay(self):
        package, sources, media = self.fixture()
        with patch.object(migration, '_read_remaining_content_package',
                          return_value=package), \
                override_settings(MEDIA_LIBRARY_ROOT=media):
            first = migration.import_remaining_media(
                source_root=sources, storage=MediaStorage())
            before = {
                'folders': list(MediaFolder.objects.values()),
                'assets': list(Asset.objects.order_by('pk').values()),
                'files': list(AssetFile.objects.order_by('pk').values()),
            }
            second = migration.import_remaining_media(
                source_root=sources, storage=MediaStorage())
        self.assertEqual(first, {'status': 'pass', 'created': 7,
                                 'recovered': 0, 'replayed': 0})
        self.assertEqual(second, {'status': 'pass', 'created': 0,
                                  'recovered': 0, 'replayed': 7})
        self.assertEqual({
            'folders': list(MediaFolder.objects.values()),
            'assets': list(Asset.objects.order_by('pk').values()),
            'files': list(AssetFile.objects.order_by('pk').values()),
        }, before)
        self.assertEqual(Asset.objects.filter(status=Asset.Status.READY).count(), 7)
        self.assertFalse(Page.objects.exists())
        self.assertFalse(AssetUsage.objects.exists())

    def test_dev09n_102_all_sources_are_verified_before_db_work(self):
        package, sources, media = self.fixture()
        Path(sources, package['media'][-1]['relative_path']).unlink()
        with patch.object(migration, '_read_remaining_content_package',
                          return_value=package), \
                override_settings(MEDIA_LIBRARY_ROOT=media), \
                self.assertRaisesMessage(
                    ValidationError, 'MIGRATION_MEDIA_SOURCE_UNAVAILABLE'):
            migration.import_remaining_media(
                source_root=sources, storage=MediaStorage())
        self.assertFalse(MediaFolder.objects.exists())
        self.assertFalse(Asset.objects.exists())
        self.assertFalse(AssetFile.objects.exists())

    def test_dev09n_103_interrupted_prepare_is_exactly_recoverable(self):
        package, sources, media = self.fixture()
        original = migration.media_services.mark_ready
        calls = 0

        def interrupt_fourth(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise ValidationError('TEST_INTERRUPTION')
            return original(**kwargs)

        with patch.object(migration, '_read_remaining_content_package',
                          return_value=package), \
                override_settings(MEDIA_LIBRARY_ROOT=media), \
                patch.object(migration.media_services, 'mark_ready',
                             side_effect=interrupt_fourth), \
                self.assertRaisesMessage(ValidationError, 'TEST_INTERRUPTION'):
            migration.import_remaining_media(
                source_root=sources, storage=MediaStorage())
        self.assertEqual(Asset.objects.filter(status=Asset.Status.READY).count(), 3)
        self.assertEqual(Asset.objects.filter(status=Asset.Status.STAGED).count(), 1)
        self.assertEqual(AssetFile.objects.count(), 4)
        with patch.object(migration, '_read_remaining_content_package',
                          return_value=package), \
                override_settings(MEDIA_LIBRARY_ROOT=media):
            result = migration.import_remaining_media(
                source_root=sources, storage=MediaStorage())
        self.assertEqual(result, {'status': 'pass', 'created': 3,
                                  'recovered': 1, 'replayed': 3})
        self.assertEqual(Asset.objects.filter(status=Asset.Status.READY).count(), 7)

    def test_dev09n_104_existing_descriptor_or_manifest_conflict_refuses(self):
        package, sources, media = self.fixture()
        row = package['media'][0]
        MediaFolder.objects.create(
            id=package['media_folder']['id'], path='foreign/path')
        with patch.object(migration, '_read_remaining_content_package',
                          return_value=package), \
                override_settings(MEDIA_LIBRARY_ROOT=media), \
                self.assertRaisesMessage(
                    ValidationError, 'MIGRATION_MEDIA_EXISTING_CONFLICT'):
            migration.import_remaining_media(
                source_root=sources, storage=MediaStorage())
        self.assertFalse(Asset.objects.exists())
        self.assertFalse(AssetFile.objects.exists())
        self.assertFalse(Asset.objects.filter(pk=row['asset_id']).exists())

    @override_settings(DEV09_MIGRATION_APPLY_ENABLED=False)
    def test_dev09n_105_disabled_before_package_read(self):
        with patch.object(migration, '_read_remaining_content_package') as reader:
            with self.assertRaisesMessage(ValidationError,
                                          'MIGRATION_APPLY_DISABLED'):
                migration.import_remaining_media(source_root='missing')
        reader.assert_not_called()

