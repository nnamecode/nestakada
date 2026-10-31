"""Independent bounded dense oracle versus sparse table capability proof."""
import random
import unittest

import html5lib

from page_editor.html_policy import normalize_html
from page_editor.tables import inspect_tables
from page_editor.types import PolicyError, ProtectedContext, URLContext

SCOPE = "abcdefab-1234-4abc-8abc-abcdefabcdef"


def fragment(value):
    return html5lib.parseFragment(value, treebuilder="etree", namespaceHTMLElements=True)


def table_html(groups):
    output = ["<table>"]
    for section, rows in groups:
        output.append("<" + section + ">")
        for row in rows:
            output.append("<tr>")
            for rowspan, colspan in row:
                output.append('<td rowspan="%s" colspan="%s">X</td>' % (rowspan, colspan))
            output.append("</tr>")
        output.append("</" + section + ">")
    output.append("</table>")
    return "".join(output)


def dense_oracle(groups):
    """Small test-only coordinates; no product helpers or giant dimensions."""
    width = 0
    total_rows = 0
    cell_count = 0
    for _section, rows in groups:
        occupied = set()
        if len(rows) > 8:
            raise AssertionError("oracle fixture too large")
        for row_index, row in enumerate(rows):
            cursor = 0
            for rowspan, colspan in row:
                if not 1 <= rowspan <= 8 or not 1 <= colspan <= 8:
                    raise AssertionError("oracle fixture too large")
                if row_index + rowspan > len(rows):
                    raise ValueError("cross group")
                while (row_index, cursor) in occupied:
                    cursor += 1
                cells = {(r, c) for r in range(row_index, row_index + rowspan)
                         for c in range(cursor, cursor + colspan)}
                if cells & occupied:
                    raise ValueError("overlap")
                occupied.update(cells)
                cursor += colspan
                width = max(width, cursor)
                cell_count += 1
        total_rows += len(rows)
    return total_rows, cell_count, width * total_rows


class TablePolicyTests(unittest.TestCase):
    def normalize(self, value, **kwargs):
        return normalize_html(value, owner=True, field="main_text", scope_id=SCOPE,
                              protected_context=ProtectedContext(), **kwargs)

    def assert_geometry(self, groups):
        value = table_html(groups)
        try:
            expected = dense_oracle(groups)
        except ValueError:
            with self.assertRaises(PolicyError):
                inspect_tables(fragment(value))
            return False
        facts = inspect_tables(fragment(value))
        self.assertEqual(len(facts), 1)
        fact = facts[0]
        self.assertEqual((fact.row_count, fact.cell_count, fact.virtual_slots), expected)
        self.assertTrue(fact.rich_widget)
        self.assertEqual(fact.reason, "rich")
        return True

    def test_handwritten_expiry_first_gap_and_group_width(self):
        fixtures = [
            [("tbody", [[(2, 1), (1, 1)], [(1, 1)], [(1, 2)]])],
            [("tbody", [[(3, 1), (1, 1), (2, 1)], [(1, 1)], [(1, 1)]])],
            [("thead", [[(1, 3)]]), ("tbody", [[(1, 1)], [(1, 2)]])],
            [("tbody", [[(1, 1), (1, 1)], [(1, 1)]])],
            # The second row starts free at0 but its colspan hits occupied1.
            [("tbody", [[(1, 1), (2, 1)], [(1, 2)]])],
        ]
        outcomes = [self.assert_geometry(groups) for groups in fixtures]
        self.assertEqual(outcomes, [True, True, True, True, False])

    def test_seeded_small_dense_oracle(self):
        rng = random.Random(7082026)
        accepted = rejected = 0
        for index in range(160):
            row_count = rng.randint(1, 5)
            rows = [[(rng.randint(1, row_count - r), rng.randint(1, 3))
                     for _ in range(rng.randint(1, 4))] for r in range(row_count)]
            with self.subTest(index=index):
                if self.assert_geometry([("tbody", rows)]):
                    accepted += 1
                else:
                    rejected += 1
        self.assertGreater(accepted, 0)
        self.assertGreater(rejected, 0)

    def test_rowspan_cross_group_and_zero_rejected(self):
        values = [table_html([("thead", [[(2, 1)]]), ("tbody", [[(1, 1)]])]),
                  '<table><tbody><tr><td rowspan="0">X</td></tr></tbody></table>',
                  '<table><tbody><tr><td colspan="0">X</td></tr></tbody></table>']
        for value in values:
            with self.subTest(value=value), self.assertRaises(PolicyError):
                self.normalize(value)

    def test_caption_scope_sections_and_carriers_survive_native_clean(self):
        value = '<table data-es-cellpad="4" data-es-mt="8"><caption>Цена <strong>😀</strong></caption><thead><tr><th scope="col" colspan="2">H</th></tr></thead><tbody><tr><th scope="row">R</th><td data-es-align="right">10</td></tr></tbody></table>'
        result = self.normalize(value)
        self.assertIn('<caption>Цена <strong>😀</strong></caption>', result.html)
        for attribute in ('scope="col"', 'scope="row"', 'colspan="2"',
                          'data-es-cellpad="4"', 'data-es-mt="8"', 'data-es-align="right"'):
            self.assertIn(attribute, result.html)
        self.assertEqual(result.table_capabilities[0].virtual_slots, 4)
        self.assertEqual(result.ui_table_slots_used, 4)
        self.assertEqual(self.normalize(result.html).html, result.html)

    def test_nested_tables_are_preorder_opaque_with_exact_content(self):
        value = '<table><tbody><tr><td>Outer<table><tbody><tr><td>INNER_CANARY</td></tr></tbody></table>Tail</td></tr></tbody></table>'
        result = self.normalize(value)
        self.assertEqual(result.html, value)
        self.assertEqual([f.table_index for f in result.table_capabilities], [0, 1])
        for fact in result.table_capabilities:
            self.assertTrue(fact.nested)
            self.assertFalse(fact.rich_widget)
            self.assertEqual(fact.reason, "nested")
            self.assertEqual((fact.row_count, fact.cell_count, fact.virtual_slots), (1, 1, 1))
        self.assertEqual(result.ui_table_slots_used, 0)

    def test_exact_aggregate_boundary_and_cross_field_carry(self):
        def single(width):
            return '<table><tbody><tr><td colspan="%s">X</td></tr></tbody></table>' % width
        exact = self.normalize(single(20000))
        self.assertTrue(exact.table_capabilities[0].rich_widget)
        self.assertEqual(exact.ui_table_slots_used, 20000)
        over = self.normalize(single(20001))
        self.assertFalse(over.table_capabilities[0].rich_widget)
        self.assertIsNone(over.table_capabilities[0].virtual_slots)
        self.assertEqual(over.html, single(20001))
        two = self.normalize(single(15000) + single(15000))
        self.assertEqual([f.rich_widget for f in two.table_capabilities], [True, False])
        self.assertEqual(two.table_capabilities[1].reason, "aggregate-budget")
        self.assertEqual(two.table_capabilities[1].virtual_slots, 15000)
        self.assertEqual(two.ui_table_slots_used, 15000)
        second_field = self.normalize(single(15000), table_budget_remaining=20000 - two.ui_table_slots_used)
        self.assertFalse(second_field.table_capabilities[0].rich_widget)
        self.assertEqual(second_field.ui_table_slots_used, 0)
        self.assertEqual(second_field.html, single(15000))

    def test_billion_colspan_and_long_decimal_no_dense_or_integer_limit(self):
        # 5001digits exceeds CPython's default whole-int conversion limit.
        for width in ("1000000000", "1" + "0" * 5000):
            with self.subTest(decimal_digits=len(width)):
                value = '<table><tbody><tr><td colspan="' + width + '">KEEP</td></tr></tbody></table>'
                result = self.normalize(value)
                fact = result.table_capabilities[0]
                self.assertFalse(fact.rich_widget)
                self.assertEqual(fact.reason, "oversized")
                self.assertIsNone(fact.virtual_slots)
                self.assertEqual(result.ui_table_slots_used, 0)
                self.assertEqual(result.html, value)

    def test_many_rowspan_expiry_events_small_dense_reference(self):
        groups = [("tbody", [[(2, 1), (1, 1), (3, 1), (1, 1)],
                              [(1, 1), (1, 1)], [(1, 1)],
                              [(2, 1), (1, 1)], [(1, 1)], [(1, 4)]])]
        self.assertTrue(self.assert_geometry(groups))

    def test_bad_remaining_budget_not_accepted_as_permission(self):
        value = '<table><tbody><tr><td>X</td></tr></tbody></table>'
        for budget in (-1, 20001, True, None, 1.5, "20000"):
            with self.subTest(budget=budget), self.assertRaises(PolicyError):
                self.normalize(value, table_budget_remaining=budget)

    def test_actual_context_relative_and_external_links(self):
        context = URLContext(page_path="/services/repair/", origin="https://example.invalid")
        for href in ("next/", "../other/", "./?q=x", "https://outside.invalid/manage/"):
            with self.subTest(href=href):
                result = self.normalize('<a href="' + href + '">LINK</a>', url_context=context)
                tree = html5lib.parseFragment(result.html, treebuilder="etree", namespaceHTMLElements=False)
                self.assertEqual(tree.find("a").attrib["href"], href)

    def test_context_private_and_outside_root_links_rejected(self):
        context = URLContext(page_path="/services/repair/", origin="https://example.invalid")
        for href in ("../../../x", "../../manage/", "https://example.invalid/manage/",
                     "https://example.invalid/%6danage/", "../../%6danage/",
                     "https://example.invalid/services/../../manage/"):
            with self.subTest(href=href), self.assertRaises(PolicyError):
                self.normalize('<a href="' + href + '">LINK</a>', url_context=context)

    def test_custom_private_root_context_and_safe_same_origin(self):
        context = URLContext(page_path="/public/", origin="https://example.invalid",
                             private_roots=("/manage/", "/private/"))
        with self.assertRaises(PolicyError):
            self.normalize('<a href="../private/x">X</a>', url_context=context)
        value = '<a href="https://example.invalid/service/">X</a>'
        self.assertEqual(self.normalize(value, url_context=context).html, value)


if __name__ == "__main__":
    unittest.main()
