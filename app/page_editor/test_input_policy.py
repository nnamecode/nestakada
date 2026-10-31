"""Closed DTO/actual static child checks; not HTTP or authorization evidence."""
import copy
import json
import unittest
from editor_runtime.processing import normalize_input, ProcessingRejected, ProcessingUnavailable
from . import policy_constants

PAGE = '00000000-0000-0000-0000-000000000001'
BASE = '00000000-0000-0000-0000-000000000002'


class InputPolicyTests(unittest.TestCase):
    def context(self):
        return {'protocol': 'page-editor-context-v1', 'owner': True,
                'fields': ['intro_text', 'main_text', 'price', 'h1', 'title', 'description', 'indexing_allowed'],
                'generation': 1, 'page_id': PAGE, 'base_revision_id': BASE,
                'page_path': '/services/example/', 'origin': 'https://example.com',
                'protected_fields': [], 'policy_version': policy_constants.POLICY_VERSION}

    def payload(self, changes=None):
        return {'protocol': 'page-editor-v1', 'generation': 1, 'baseRevisionId': BASE,
                'editingFrom': 'current', 'draftBasis': None, 'stageId': None,
                'changes': {'main_text': '<p>SAFE</p>'} if changes is None else changes}

    def run_input(self, value, context=None):
        raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
        return normalize_input(raw, self.context() if context is None else context)

    def test_actual_child_plain_normalization_is_explicit_and_nonmutating(self):
        value = self.payload({'h1': '  Заголовок  ', 'title': '\u00a0e\u0301\u00a0',
                              'description': '  line1\r\nline2  ', 'indexing_allowed': False})
        original = copy.deepcopy(value)
        result = self.run_input(value)
        self.assertTrue(result['accepted'])
        self.assertEqual(result['changes'], {'h1': 'Заголовок', 'title': 'é',
                         'description': '  line1\nline2  ', 'indexing_allowed': False})
        self.assertTrue(result['changed'])
        self.assertEqual({item['field'] for item in result['warnings']}, {'h1', 'title', 'description'})
        self.assertEqual(value, original)

    def test_actual_child_text_url_context_and_price(self):
        result = self.run_input(self.payload({'main_text': '<p><a href="../price/">Цены</a></p>',
                                             'price': None}))
        self.assertTrue(result['accepted'])
        self.assertIn('href="../price/"', result['changes']['main_text'])
        self.assertIsNone(result['changes']['price'])
        self.assertEqual(result['policy_version'], policy_constants.POLICY_VERSION)

    def test_closed_root_and_duplicate_keys_rejected(self):
        value = self.payload()
        value['snapshot'] = {}
        with self.assertRaises(ProcessingRejected):
            self.run_input(value)
        raw = json.dumps(self.payload()).encode()
        raw = b'{"generation":1,' + raw[1:]
        with self.assertRaises(ProcessingRejected):
            normalize_input(raw, self.context())

    def test_scalar_exact_types_controls_and_limit_after_normalization(self):
        for changes in ({'indexing_allowed': 1}, {'h1': True}, {'title': 'bad\nline'},
                        {'description': 'bad\x00'}, {'h1': '🚀' * 256}):
            with self.subTest(field=next(iter(changes))), self.assertRaises(ProcessingRejected):
                self.run_input(self.payload(changes))
        accepted = self.run_input(self.payload({'h1': '  ' + '🚀' * 255 + '  '}))
        self.assertEqual(accepted['changes']['h1'], '🚀' * 255)

    def test_generation_and_base_have_distinct_fixed_conflicts(self):
        value = self.payload()
        value['generation'] = 2
        self.assertEqual(self.run_input(value), {'accepted': False, 'code': 'EDITOR_IDENTITY_CHANGED'})
        value['generation'] = 1
        value['baseRevisionId'] = PAGE
        self.assertEqual(self.run_input(value), {'accepted': False, 'code': 'EDITOR_BASE_CONFLICT'})

    def test_employee_keys_cannot_promote_owner_fields(self):
        context = self.context()
        context.update(owner=False, fields=['main_text'])
        result = self.run_input(self.payload({'h1': 'injected'}), context)
        self.assertEqual(result, {'accepted': False, 'code': 'EDITOR_FIELDS_FORBIDDEN'})

    def test_inconsistent_and_unsupported_editing_modes(self):
        value = self.payload()
        value['stageId'] = PAGE
        with self.assertRaises(ProcessingRejected):
            self.run_input(value)
        value['editingFrom'] = 'restore-stage'
        self.assertEqual(self.run_input(value), {'accepted': False, 'code': 'EDITOR_CAPABILITY_UNAVAILABLE'})

    def test_trusted_context_and_semantic_policy_must_match(self):
        context = self.context()
        context['policy_version'] = 'old-semantic-policy'
        with self.assertRaises(ProcessingUnavailable):
            self.run_input(self.payload(), context)
        context = self.context()
        context['owner'] = 'true'
        with self.assertRaises(ProcessingUnavailable):
            self.run_input(self.payload(), context)


if __name__ == '__main__':
    unittest.main()
