import copy
import hashlib
import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from content.models import Page
from page_versions import schema


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

