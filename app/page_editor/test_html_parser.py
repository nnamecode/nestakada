"""Independent stock html5lib oracle. Parser equivalence is not sanitization."""
import unittest
from contextlib import contextmanager
import json
from unittest.mock import patch
from xml.etree import ElementTree as ET
import html5lib

from page_editor.html_parser import _CoalescingParser, _parse_session, parse_fragment, TEXT_BATCH_CHARS


CASES = (
    ('EMPTY', ''),
    ('PLAIN', '<p>ordinary text</p>'),
    ('BATCH_8191', '<p>' + '&amp;' * 8191 + '</p>'),
    ('BATCH_8192', '<p>' + '&amp;' * 8192 + '</p>'),
    ('BATCH_8193', '<p>' + '&amp;' * 8193 + '</p>'),
    ('BATCH_16385', '<p>' + '&amp;' * 16385 + '</p>'),
    ('MIXED_LITERAL_ENTITY', '<p>' + 'A&amp;B &lt;C&gt;' * 32 + '</p>'),
    ('SPACE_CHARACTERS', '<p> \t\n\r\n </p>'),
    ('SPACE_ENTITIES', '<p>&#32;&Tab;&NewLine;&nbsp;</p>'),
    ('CRLF_NFD', '<p>e\u0301\r\nx\ry</p>'),
    ('NUMERIC_ASTRAL_MULTIPOINT', '<p>&#65;&#x41;&#x1f680;&NotEqualTilde;</p>'),
    ('ESCAPED_SCRIPT', '<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>'),
    ('ESCAPED_IMG_EVENT', '<p>&lt;img src=x onerror=&quot;alert(1)&quot;&gt;</p>'),
    ('DOUBLE_ESCAPE', '<p>&amp;lt;script&amp;gt;</p>'),
    ('INVALID_ENTITY', '<p>&unknown; &amp text &#xzz; &#0;</p>'),
    ('NUL_CONTROLS', '<p>A\x00B&#0;&#xD800;\x01C</p>'),
    ('TEXT_CHILD_TAIL', 'BEFORE<p>A<strong>B&amp;C</strong>D<em>E</em>F</p>AFTER'),
    ('ADOPTION_AGENCY', '<p><b><i>A&amp;B</b>C</i>D'),
    ('DUPLICATE_ATTR', '<p title="A&amp;B" title="C">X</p>'),
    ('MALFORMED_EOF', '<p>A&amp;B<a href="unterminated'),
    ('TABLE_WHITESPACE', '<table> \n<tbody><tr><td>A&amp;B</td></tr></tbody></table>'),
    ('TABLE_FOSTER', 'A<table>B&amp;C<tr><td>D</td></tr>E</table>F'),
    ('TABLE_CAPTION_NESTED', '<table><caption>A&amp;B</caption><thead><tr><th>C</th></tr></thead><tbody><tr><td><table><tr><td>D</td></tr></table></td></tr></tbody></table>'),
    ('FOREIGN_NAMESPACES', '<svg><title>A&amp;B</title><foreignObject><p>C</p></foreignObject></svg><math><mi>x</mi></math>'),
    ('RAWTEXT_BARRIERS', '<script>if(a<b&&c){x="&amp;"}</script><style>a>b{color:red}</style><p>&amp;</p>'),
    ('SELECT_PRE_RCDATA', '<select><option>A&amp;B</option> C</select><pre>\n X&amp;Y</pre><textarea>&lt;x&gt;</textarea><p>&amp;</p>'),
    ('COMMENT_DOCTYPE', '<!DOCTYPE html><!-- A&amp;B --><p>C</p>'),
    ('ATTRIBUTE_ENTITIES', '<p title="&amp;&quot;&#x1f680;&unknown;" data-x="&amp">A&amp;B</p>'),
    ('ERROR_AFTER_BATCH', '<p>' + '&amp;' * 8192 + '</p></em><p>TAIL'),
    ('ERROR_NUL_BATCH', '<p>' + '&amp;' * 8193 + '\x00</p><a href="x" href="y">Z'),
)


def signature(node):
    # Includes namespace-expanded names, all attrs, text/tails and child order.
    tag = node.tag if isinstance(node.tag, str) else ('COMMENT', node.tag.__name__)
    return (tag, tuple(sorted(node.attrib.items())), node.text, node.tail,
            tuple(signature(child) for child in node))


class HtmlParserDifferentialTests(unittest.TestCase):
    def test_thirty_fixed_trees_errors_positions_and_public_helper_against_stock(self):
        self.assertEqual(len(CASES), 30)
        original_class = html5lib.HTMLParser
        for case_id, source in CASES:
            with self.subTest(case=case_id):
                stock = html5lib.HTMLParser(tree=html5lib.getTreeBuilder('etree'), namespaceHTMLElements=True)
                expected = stock.parseFragment(source, container='div', scripting=False)
                candidate = _CoalescingParser()
                actual = candidate.parseFragment(source)
                # No raw source/attrs/error datavars in assertion diagnostics.
                self.assertTrue(signature(actual) == signature(expected), case_id + '_TREE_DIFFERENCE')
                self.assertTrue(candidate.errors == stock.errors, case_id + '_ERROR_POSITION_DIFFERENCE')
                self.assertTrue(signature(parse_fragment(source)) == signature(expected), case_id + '_HELPER_DIFFERENCE')
                self.assertIs(html5lib.HTMLParser, original_class, 'GLOBAL_STOCK_PARSER_PATCHED')

    def test_helper_batch_size_and_closed_configuration(self):
        self.assertEqual(TEXT_BATCH_CHARS, 8192)
        with self.assertRaises(TypeError):
            parse_fragment('<p>X</p>', container='table')


@contextmanager
def real_parse_calls():
    calls = []
    original = _CoalescingParser.parseFragment

    def observe(parser, value):
        calls.append(1)  # Do not retain source or expose a private cache handle.
        return original(parser, value)

    with patch.object(_CoalescingParser, 'parseFragment', new=observe):
        yield calls


def stock_tree(source):
    parser = html5lib.HTMLParser(tree=html5lib.getTreeBuilder('etree'), namespaceHTMLElements=True)
    tree = parser.parseFragment(source, container='div', scripting=False)
    return tree, parser.errors


class ParseMemoTests(unittest.TestCase):
    def test_stock_thirty_corpus_inside_session_and_fresh_parser_errors(self):
        for case_id, source in CASES:
            with self.subTest(case=case_id):
                expected, errors = stock_tree(source)
                with _parse_session() as handle:
                    self.assertIsNone(handle)
                    first, second = parse_fragment(source), parse_fragment(source)
                    self.assertTrue(signature(first) == signature(expected), case_id + '_MEMO_FIRST_TREE')
                    self.assertTrue(signature(second) == signature(expected), case_id + '_MEMO_SECOND_TREE')
                    fresh = _CoalescingParser()
                    self.assertTrue(signature(fresh.parseFragment(source)) == signature(expected), case_id + '_FRESH_TREE')
                    self.assertTrue(fresh.errors == errors, case_id + '_FRESH_ERROR_POSITIONS')

    def test_every_return_isolated_from_mutations_including_first_miss(self):
        source = '<p title="A">head<strong>B</strong>tail</p>'
        expected, _ = stock_tree(source)
        with real_parse_calls() as calls, _parse_session():
            first = parse_fragment(source)
            paragraph, strong = first[0], first[0][0]
            paragraph.attrib['title'] = 'MUTATED'
            paragraph.text, strong.text, strong.tail = 'BAD', 'BAD', 'BAD'
            paragraph.remove(strong)
            first.append(ET.Element('extra'))
            second = parse_fragment(source)
            self.assertTrue(signature(second) == signature(expected), 'CACHE_FIRST_RETURN_SHARED')
            first_ids = {id(node) for node in first.iter()} | {id(node.attrib) for node in first.iter()}
            second_ids = {id(node) for node in second.iter()} | {id(node.attrib) for node in second.iter()}
            self.assertTrue(first_ids.isdisjoint(second_ids), 'CACHE_MUTABLE_IDENTITIES_SHARED')
            second[0][0].tail = 'SECOND_MUTATION'
            self.assertTrue(signature(parse_fragment(source)) == signature(expected), 'CACHE_HIT_RETURN_SHARED')
            self.assertEqual(len(calls), 1)

    def test_exact_string_identity_single_entry_eviction_and_unicode_forms(self):
        a, b = '<p>A&amp;B</p>', '<p>A&#38;B</p>'
        self.assertTrue(signature(stock_tree(a)[0]) == signature(stock_tree(b)[0]))
        with real_parse_calls() as calls:
            with _parse_session():
                parse_fragment(a); parse_fragment(a)
                self.assertEqual(len(calls), 1)
                parse_fragment(b); parse_fragment(a)
                self.assertEqual(len(calls), 3, 'CACHE_NOT_EXACT_SINGLE_ENTRY')
                parse_fragment('<p>e\u0301</p>'); parse_fragment('<p>é</p>')
                self.assertEqual(len(calls), 5, 'CACHE_NORMALIZED_SOURCE_KEYS')
            parse_fragment(a)
            self.assertEqual(len(calls), 6, 'CACHE_ESCAPED_SCOPE')

    def test_lifetime_outside_sequential_exception_and_nested_scope(self):
        source = '<p>LIFETIME</p>'
        with real_parse_calls() as calls:
            parse_fragment(source); parse_fragment(source)
            self.assertEqual(len(calls), 2)
            for _ in range(2):
                with _parse_session():
                    parse_fragment(source); parse_fragment(source)
            self.assertEqual(len(calls), 4)
            with self.assertRaises(RuntimeError):
                with _parse_session():
                    parse_fragment(source)
                    raise RuntimeError('SYNTHETIC_SCOPE_FAILURE')
            with _parse_session():
                parse_fragment(source)
                with self.assertRaises(RuntimeError):
                    with _parse_session():
                        pass
                parse_fragment(source)
            self.assertEqual(len(calls), 6, 'NESTED_FAILURE_CORRUPTED_OUTER_SCOPE')
            parse_fragment(source)
            self.assertEqual(len(calls), 7)

    def test_errorful_results_and_parse_exceptions_are_not_cached(self):
        errorful, a, b = '<p title="A" title="B">X</p>', '<p>A</p>', '<p>B</p>'
        self.assertTrue(stock_tree(errorful)[1], 'ERRORFUL_CONTROL_NOT_ERRORFUL')
        original, count, fail_once = _CoalescingParser.parseFragment, [], [True]

        def observe(parser, value):
            count.append(1)
            if value == b and fail_once[0]:
                fail_once[0] = False
                raise RuntimeError('SYNTHETIC_PARSE_FAILURE')
            return original(parser, value)

        with patch.object(_CoalescingParser, 'parseFragment', new=observe), _parse_session():
            parse_fragment(errorful); parse_fragment(errorful)
            self.assertEqual(len(count), 2)
            parse_fragment(a)
            with self.assertRaises(RuntimeError):
                parse_fragment(b)
            parse_fragment(a); parse_fragment(b); parse_fragment(b)
            self.assertEqual(len(count), 6, 'ERROR_OR_OLD_ENTRY_RETAINED_AFTER_MISS')

    def test_memo_byte_node_depth_bounds_are_cache_admission_not_new_parse_refusal(self):
        prefix, suffix = '<p title="', '">x</p>'
        exact_bytes = prefix + 'a' * (1048576 - len(prefix + suffix)) + suffix
        cases = ((exact_bytes, 1), (exact_bytes + ' ', 2),
            ('<p>' + '<span></span>' * 19999 + '</p>', 1),
            ('<p>' + '<span></span>' * 20000 + '</p>', 2),
            ('<div>' * 32 + 'x' + '</div>' * 32, 1),
            ('<div>' * 33 + 'x' + '</div>' * 33, 2))
        for index, (source, expected_calls) in enumerate(cases):
            with self.subTest(boundary=index):
                expected, errors = stock_tree(source)
                self.assertFalse(errors, 'CACHE_BOUNDARY_CONTROL_ERRORFUL')
                with real_parse_calls() as calls, _parse_session():
                    first, second = parse_fragment(source), parse_fragment(source)
                    self.assertTrue(signature(first) == signature(expected), 'CACHE_BOUNDARY_FIRST_TREE')
                    self.assertTrue(signature(second) == signature(expected), 'CACHE_BOUNDARY_SECOND_TREE')
                    self.assertEqual(len(calls), expected_calls)

    def test_actual_normalizer_success_and_partial_field_failure_release_session(self):
        from page_editor.normalizer_child import normalize
        from page_editor.policy_constants import POLICY_VERSION
        context = {'protocol': 'page-editor-context-v1', 'owner': True,
            'fields': ['intro_text', 'main_text'], 'generation': 1,
            'page_id': '00000000-0000-0000-0000-000000000001',
            'base_revision_id': '00000000-0000-0000-0000-000000000002',
            'page_path': '/test/', 'origin': 'http://localhost',
            'protected_fields': [], 'policy_version': POLICY_VERSION}

        def wire(changes):
            return json.dumps({'protocol': 'page-editor-v1', 'generation': 1,
                'baseRevisionId': context['base_revision_id'], 'editingFrom': 'current',
                'draftBasis': None, 'stageId': None, 'changes': changes}).encode()

        with real_parse_calls() as calls:
            for _ in range(2):
                result = normalize(wire({'main_text': '<p>A</p>'}), context)
                self.assertTrue(result['accepted'])
            self.assertEqual(len(calls), 2, 'NORMALIZER_SCOPE_SHARED_OR_ABSENT')
            with self.assertRaises(ValueError):
                normalize(wire({'intro_text': '<p>A</p>', 'main_text': '<script>X</script>'}), context)
            result = normalize(wire({'main_text': '<p>A</p>'}), context)
            self.assertTrue(result['accepted'])
            self.assertEqual(len(calls), 4, 'NORMALIZER_EXCEPTION_RETAINED_SESSION')
