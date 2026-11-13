from copy import deepcopy
import hashlib
from uuid import uuid4

from django.test import SimpleTestCase

from .contracts import ContractError, response_name
from .projection import emit_maps


def _resource_name(url, suffix):
    return hashlib.sha256(url.encode('utf-8')).hexdigest() + suffix


def manifest():
    generation = str(uuid4())
    css_url = '/static/public.css'
    return {
        'schema': 'html-reserve-manifest-v1',
        'generation': generation,
        'built_at': '2026-11-13T00:00:00Z',
        'source_stamp': 'a' * 64,
        'responses': [
            {
                'name': response_name('/'), 'target': '/', 'status': 200,
                'location': None,
                'content_type': 'text/html; charset=utf-8',
                'x_robots_tag': None,
                'security_policy_id': 'public-v1',
                'cache_policy_id': 'reserve-v1',
                'sha256': 'b' * 64, 'byte_size': 12,
            },
            {
                'name': response_name('/old/'), 'target': '/old/',
                'status': 301, 'location': '/new/',
                'content_type': 'text/html; charset=utf-8',
                'x_robots_tag': 'noindex, follow',
                'security_policy_id': 'public-v1',
                'cache_policy_id': 'reserve-v1',
                'sha256': 'c' * 64, 'byte_size': 13,
            },
        ],
        'resources': [{
            'name': _resource_name(css_url, '.css'), 'url': css_url,
            'content_type': 'text/css; charset=utf-8',
            'sha256': 'd' * 64, 'byte_size': 14,
        }],
        'retained_asset_ids': [],
        'totals': {'files': 3, 'bytes': 39},
    }


class ProjectionEmitterTests(SimpleTestCase):
    def test_emits_deterministic_closed_maps(self):
        value = manifest()
        delivery = str(uuid4())
        first = emit_maps(value, delivery)
        value['responses'].reverse()
        second = emit_maps(value, delivery)
        self.assertEqual(first, second)
        self.assertIs(type(first), bytes)
        text = first.decode('ascii')
        self.assertIn('# html-reserve-projection-v1 ' + delivery, text)
        self.assertIn('map $request_uri $reserve_kind {', text)
        self.assertIn('"/" "response";', text)
        self.assertIn('"/static/public.css" "resource";', text)
        self.assertIn('"/old/" "/new/";', text)
        self.assertNotIn(value['built_at'], text)
        self.assertNotIn(value['source_stamp'], text)

    def test_escapes_nginx_variable_syntax_without_directive_injection(self):
        value = manifest()
        target = '/price-$request_uri/'
        row = value['responses'][0]
        row['target'] = target
        row['name'] = response_name(target)
        text = emit_maps(value, str(uuid4())).decode('ascii')
        self.assertIn('"/price-\\$request_uri/"', text)
        self.assertNotIn('"/price-$request_uri/"', text)
        row['target'] = '/bad/\ninclude evil;'
        with self.assertRaisesRegex(
                ContractError, 'HTML_RESERVE_PROJECTION_TARGET_INVALID'):
            emit_maps(value, str(uuid4()))

    def test_rejects_duplicate_or_ambiguous_request_uri(self):
        value = manifest()
        duplicate = deepcopy(value['responses'][0])
        value['responses'].append(duplicate)
        with self.assertRaisesRegex(
                ContractError, 'HTML_RESERVE_PROJECTION_URI_DUPLICATE'):
            emit_maps(value, str(uuid4()))
        value = manifest()
        value['resources'][0]['url'] = '/'
        value['resources'][0]['name'] = _resource_name('/', '.css')
        with self.assertRaisesRegex(
                ContractError, 'HTML_RESERVE_PROJECTION_URI_DUPLICATE'):
            emit_maps(value, str(uuid4()))

    def test_rejects_untrusted_status_location_policy_and_resource_type(self):
        cases = (
            ('responses', 0, 'status', 503),
            ('responses', 1, 'location', 'https://evil.example/'),
            ('responses', 0, 'security_policy_id', 'custom'),
            ('responses', 0, 'cache_policy_id', 'custom'),
            ('responses', 0, 'content_type', 'text/plain'),
            ('responses', 0, 'x_robots_tag', 'index, follow'),
            ('resources', 0, 'content_type', 'application/octet-stream'),
            ('resources', 0, 'name', '../escape.css'),
        )
        for group, index, key, bad in cases:
            with self.subTest(group=group, key=key):
                value = manifest()
                value[group][index][key] = bad
                with self.assertRaisesRegex(
                        ContractError, 'HTML_RESERVE_PROJECTION_METADATA_INVALID'):
                    emit_maps(value, str(uuid4()))

    def test_rejects_schema_uuid_caps_and_map_size(self):
        value = manifest()
        value['unknown'] = True
        with self.assertRaisesRegex(
                ContractError, 'HTML_RESERVE_PROJECTION_MANIFEST_INVALID'):
            emit_maps(value, str(uuid4()))
        with self.assertRaisesRegex(
                ContractError, 'HTML_RESERVE_PROJECTION_UUID_INVALID'):
            emit_maps(manifest(), 'not-a-uuid')
        with self.assertRaisesRegex(
                ContractError, 'HTML_RESERVE_PROJECTION_MAP_LIMIT'):
            emit_maps(manifest(), str(uuid4()), max_bytes=1)
        with self.assertRaisesRegex(
                ContractError, 'HTML_RESERVE_PROJECTION_LIMIT_INVALID'):
            emit_maps(manifest(), str(uuid4()), max_bytes=0)
