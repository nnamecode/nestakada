from copy import deepcopy
import json
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import SimpleTestCase, override_settings

from . import dev10_gallery_apply as gallery


@override_settings(ENVIRONMENT='test', DEV10_GALLERY_APPLY_ENABLED=True)
class Dev10GalleryLoaderTests(SimpleTestCase):
    def assert_fault(self, code, action):
        with self.assertRaises(ValidationError) as caught:
            action()
        self.assertIn(code, caught.exception.messages)

    def package(self):
        return gallery._read_package()

    def encoded(self, value):
        return gallery._canonical(value)

    def test_g10_loader_001_exact_package_summary(self):
        value = self.package()
        photos = [photo for album in value['albums'] for photo in album['photos']]
        self.assertEqual((len(value['albums']), len(photos),
                          sum(photo['bytes'] for photo in photos)),
                         (17, 214, 41176391))
        self.assertEqual(tuple(album['map_id'] for album in value['albums']),
                         gallery.MAP_ORDER)
        self.assertEqual(value['page2_map_ids'], list(gallery.PAGE2_MAP_IDS))

    def test_g10_loader_002_default_off_before_package_read(self):
        with override_settings(DEV10_GALLERY_APPLY_ENABLED=False), patch(
                'content.dev10_gallery_apply._read_package') as read:
            self.assert_fault('GALLERY_APPLY_DISABLED', gallery.load_for_apply)
        read.assert_not_called()

    def test_g10_loader_003_wrong_environment_database_or_user_closed(self):
        cases = [
            ({'ENVIRONMENT': 'production'}, {}),
            ({}, {'ENGINE': 'django.db.backends.sqlite3'}),
            ({}, {'NAME': 'wrong'}),
            ({}, {'USER': 'wrong'}),
        ]
        for settings_change, database_change in cases:
            configured = dict(connection.settings_dict)
            configured.update(database_change)
            with self.subTest(settings=settings_change, database=database_change), \
                    override_settings(**settings_change), patch.object(
                        connection, 'settings_dict', configured), patch(
                        'content.dev10_gallery_apply._read_package') as read:
                self.assert_fault('GALLERY_APPLY_DISABLED', gallery.load_for_apply)
                read.assert_not_called()

    def test_g10_loader_004_duplicate_noncanonical_and_oversize_closed(self):
        self.assert_fault(
            'GALLERY_PACKAGE_INVALID',
            lambda: gallery._decode_package(b'{"schema":"x","schema":"y"}\n'))
        value = self.package()
        compact = json.dumps(value, ensure_ascii=False).encode() + b'\n'
        self.assert_fault('GALLERY_PACKAGE_INVALID',
                          lambda: gallery._decode_package(compact))
        self.assert_fault(
            'GALLERY_PACKAGE_INVALID',
            lambda: gallery._decode_package(b' ' * (gallery.PACKAGE_MAX_BYTES + 1)))

    def test_g10_loader_005_closed_nested_schema_and_identity(self):
        value = self.package()
        mutations = []
        extra = deepcopy(value);extra['unknown'] = True;mutations.append(extra)
        wrong_order = deepcopy(value);wrong_order['albums'].reverse();mutations.append(wrong_order)
        duplicate = deepcopy(value);duplicate['albums'][1]['photos'][0]['asset_id'] = duplicate['albums'][0]['photos'][0]['asset_id'];mutations.append(duplicate)
        traversal = deepcopy(value);traversal['albums'][0]['photos'][0]['local_file'] = '../outside.jpg';mutations.append(traversal)
        overflow = deepcopy(value);overflow['albums'][0]['photos'][0]['bytes'] = 1024 * 1024 + 1;mutations.append(overflow)
        for mutation in mutations:
            with self.subTest(keys=mutation.keys()):
                self.assert_fault(
                    'GALLERY_PACKAGE_INVALID',
                    lambda mutation=mutation: gallery._decode_package(
                        self.encoded(mutation)))

    def test_g10_loader_006_payload_is_closed_safe_and_exact(self):
        value = self.package()
        root = gallery._payload(value['root'])
        self.assertEqual(root['page_kind'], 'gallery_catalog')
        self.assertEqual(root['embedded_images'], [])
        self.assertEqual(gallery.schema.asset_slots(root), {})
        slots = 0
        for album in value['albums']:
            payload = gallery._payload(album)
            slots += len(gallery.schema.asset_slots(payload))
            self.assertEqual(len(payload['embedded_images']), len(album['photos']))
            self.assertEqual(
                [node['image_id'] for node in payload['layout'][2:]],
                [photo['image_id'] for photo in album['photos']])
            self.assertEqual(gallery.restricted_clean(payload['main_text']),
                             payload['main_text'])
            self.assertNotIn('<script', payload['main_text'].lower())
        self.assertEqual(slots, 214)
