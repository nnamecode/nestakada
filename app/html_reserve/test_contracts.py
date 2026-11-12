from uuid import UUID, uuid4

from django.test import SimpleTestCase

from .contracts import (
    ContractError, ResourceRef, active_pointer, canonical_bytes,
    parse_resource_url, response_name,
)


class HtmlReserveContractTests(SimpleTestCase):
    def test_canonical_json_and_response_name_are_exact_and_bounded(self):
        left = canonical_bytes({'b': [2, 1], 'a': 'текст'}, max_bytes=100)
        right = canonical_bytes({'a': 'текст', 'b': [2, 1]}, max_bytes=100)
        self.assertEqual(left, right)
        self.assertEqual(left, b'{"a":"\\u0442\\u0435\\u043a\\u0441\\u0442","b":[2,1]}')
        self.assertNotEqual(response_name('/same/?x=1'), response_name('/same/?x=2'))
        self.assertRegex(response_name('/same/?x=1'), r'^[0-9a-f]{64}\.html$')
        with self.assertRaises(ContractError):
            canonical_bytes({'too': 'large'}, max_bytes=3)
        with self.assertRaises(ContractError):
            canonical_bytes({'float': 1.5}, max_bytes=100)

    def test_active_pointer_accepts_only_coherent_empty_or_uuid_pairs(self):
        empty = active_pointer(None, None, None, None)
        self.assertEqual(empty['current'], None)
        current, previous = uuid4(), uuid4()
        full = active_pointer(current, previous, 'a' * 64, 'b' * 64)
        self.assertEqual(UUID(full['current']), current)
        self.assertEqual(UUID(full['previous']), previous)
        with self.assertRaises(ContractError):
            active_pointer(current, None, None, None)
        with self.assertRaises(ContractError):
            active_pointer(None, previous, None, 'b' * 64)
        with self.assertRaises(ContractError):
            active_pointer(current, current, 'a' * 64, 'a' * 64)

    def test_resource_policy_distinguishes_static_bare_and_contextual_media(self):
        file_id, page_id = uuid4(), uuid4()
        bare = '/public-media/%s/' % file_id
        contextual = bare + '?page=%s&slot=main_image' % page_id
        allowed = {(str(file_id), str(page_id), 'main_image')}
        self.assertEqual(
            parse_resource_url(bare, bare_file_ids={str(file_id)},
                               contextual=allowed),
            ResourceRef('media-bare', str(file_id), None, None, None, None))
        self.assertEqual(
            parse_resource_url(contextual, bare_file_ids=set(),
                               contextual=allowed),
            ResourceRef('media-contextual', str(file_id), str(page_id),
                        'main_image', None, None))
        shared = parse_resource_url(
            '/static/shared/' + 'c' * 64 + '/public-shared.css',
            bare_file_ids=set(), contextual=set())
        self.assertEqual(shared.kind, 'static-shared')
        self.assertEqual(shared.digest, 'c' * 64)
        self.assertEqual(shared.name, 'public-shared.css')
        for rejected in (
                'https://example.test/x.js', '//example.test/x.js',
                bare + '?x=1',
                bare + '?slot=main_image&page=' + str(page_id),
                bare.replace(str(file_id), str(uuid4())),
                '/static/unknown.js'):
            with self.subTest(rejected=rejected), self.assertRaises(ContractError):
                parse_resource_url(rejected, bare_file_ids={str(file_id)},
                                   contextual=allowed)
