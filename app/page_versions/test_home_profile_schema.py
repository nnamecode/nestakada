import copy
import json
from pathlib import Path
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from content.models import Page
from . import schema
from page_editor.normalizer_child import normalize


PACKAGE = Path(__file__).resolve().parents[1] / 'content' / 'dev12_home_profile.json'


class HomeProfileSchemaTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.package = json.loads(PACKAGE.read_text(encoding='utf-8'))

    def embedded(self):
        rows = []
        for item in self.package['media']:
            rows.append({'id': item['image_id'], 'asset_id': item['asset_id'], 'alt': item['alt'],
                         'alignment': 'center', 'width_px': None, 'height_px': None})
        for item in self.package['profile']['works']:
            rows.append({'id': item['image_id'], 'asset_id': item['asset_id'], 'alt': item['alt'],
                         'alignment': 'center', 'width_px': None, 'height_px': None})
        return rows

    def snapshot(self, profile=None, *, kind=Page.Kind.HOME):
        return schema.snapshot_v1(kind, h1='Home', embedded_images=self.embedded(),
                                  home_profile=copy.deepcopy(profile or self.package['profile'])).data(kind)

    def test_exact_profile_and_legacy_snapshots_are_compatible(self):
        result = self.snapshot()
        self.assertEqual(result['home_profile']['schema'], 'home-profile-v1')
        legacy = schema.snapshot_v1(Page.Kind.HOME, h1='Legacy').data(Page.Kind.HOME)
        self.assertNotIn('home_profile', legacy)
        article = schema.snapshot_v1(Page.Kind.ARTICLE, h1='Article').data(Page.Kind.ARTICLE)
        self.assertNotIn('home_profile', article)

    def test_profile_is_home_only_and_exact(self):
        with self.assertRaises(ValidationError):
            self.snapshot(kind=Page.Kind.ARTICLE)
        changed = copy.deepcopy(self.package['profile']); changed['unknown'] = True
        with self.assertRaises(ValidationError):
            self.snapshot(changed)
        changed = copy.deepcopy(self.package['profile']); changed['services'].pop()
        with self.assertRaises(ValidationError):
            self.snapshot(changed)

    def test_urls_bindings_ids_and_plain_text_fail_closed(self):
        unbound = copy.deepcopy(self.package['profile'])
        unbound['works'][0]['source_page_id'] = None
        self.assertIsNone(
            self.snapshot(unbound)['home_profile']['works'][0][
                'source_page_id'])
        mutations = []
        changed = copy.deepcopy(self.package['profile']); changed['reviews']['url'] = 'https://example.test/'; mutations.append(changed)
        changed = copy.deepcopy(self.package['profile']); changed['services'][0]['label'] = '<script>x</script>'; mutations.append(changed)
        changed = copy.deepcopy(self.package['profile']); changed['prices'][0]['rows'][0]['source_page_id'] = None; changed['prices'][0]['rows'][0]['source_row_id'] = self.package['profile']['prices'][1]['rows'][0]['id']; mutations.append(changed)
        changed = copy.deepcopy(self.package['profile']); changed['prices'][0]['rows'][1]['id'] = changed['prices'][0]['rows'][0]['id']; mutations.append(changed)
        for profile in mutations:
            with self.subTest(profile=profile), self.assertRaises(ValidationError):
                self.snapshot(profile)

    def test_media_references_and_work_asset_match_are_exact(self):
        changed = copy.deepcopy(self.package['profile']); changed['hero']['image_id'] = changed['works'][0]['image_id']
        # Existing work media is a valid reference, so cross-slot reuse remains structurally valid.
        self.assertEqual(self.snapshot(changed)['home_profile']['hero']['image_id'], changed['works'][0]['image_id'])
        changed = copy.deepcopy(self.package['profile']); changed['hero']['image_id'] = '00000000-0000-4000-8000-000000000000'
        with self.assertRaises(ValidationError):
            self.snapshot(changed)

    def test_owner_edit_preserves_stable_identity_media_and_order(self):
        from .home_profile import validate_edit
        base = copy.deepcopy(self.package['profile'])
        allowed = copy.deepcopy(base)
        allowed['services'][0]['label'] = 'Новое название'
        self.assertEqual(validate_edit(base, allowed, self.embedded()), allowed)
        mutations = []
        changed = copy.deepcopy(base)
        changed['services'][0]['id'] = changed['services'][1]['id']
        mutations.append(changed)
        changed = copy.deepcopy(base)
        changed['prices'][0]['key'] = 'forged-key'
        mutations.append(changed)
        changed = copy.deepcopy(base)
        changed['works'].reverse()
        mutations.append(changed)
        changed = copy.deepcopy(base)
        changed['hero']['image_id'] = changed['works'][0]['image_id']
        mutations.append(changed)
        for profile in mutations:
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                validate_edit(base, profile, self.embedded())

    def test_owner_child_normalizes_profile_and_employee_context_refuses_it(self):
        payload = self.snapshot()
        context = {'protocol': 'page-editor-context-v1', 'owner': True,
                   'fields': ['home_profile'], 'generation': 1,
                   'page_id': 'e80c3de1-feea-4847-b550-325a825ffc0e',
                   'base_revision_id': '00000000-0000-4000-8000-000000000001',
                   'page_path': '/', 'origin': 'https://example.test', 'protected_fields': [],
                   'policy_version': 'es-format-v1',
                   'embedded_source': {'intro_text': '', 'main_text': '', 'layout': [],
                                       'embedded_images': payload['embedded_images']}}
        raw_value = {'protocol': 'page-editor-v1', 'generation': 1,
                     'baseRevisionId': context['base_revision_id'], 'editingFrom': 'current',
                     'draftBasis': None, 'stageId': None,
                     'changes': {'home_profile': payload['home_profile']}}
        raw = json.dumps(raw_value, ensure_ascii=False, separators=(',', ':')).encode()
        result = normalize(raw, context)
        self.assertTrue(result['accepted'])
        self.assertEqual(result['changes']['home_profile'], payload['home_profile'])
        employee = dict(context, owner=False, fields=['main_text'])
        self.assertEqual(normalize(raw, employee), {'accepted': False, 'code': 'EDITOR_FIELDS_FORBIDDEN'})
        changed = copy.deepcopy(self.package['profile']); changed['works'][0]['asset_id'] = changed['works'][1]['asset_id']
        with self.assertRaises(ValidationError):
            self.snapshot(changed)
