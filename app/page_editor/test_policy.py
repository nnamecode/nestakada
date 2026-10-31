"""Independent pure-policy expectations; no DB, IO, product renderer or grants."""
import hashlib
import json
import unittest
from html import escape
from unittest.mock import patch

import html5lib
import nh3

from page_editor import clean
from page_editor.html_policy import normalize_html
from page_editor.types import ControlledUnsupported, PolicyError, ProtectedContext

SCOPE = "abcdefab-1234-4abc-8abc-abcdefabcdef"
POCS = json.loads("{\"RUSTSEC-2021-0157\":\"<div style='background:url(\\\"cid:\\\\\\\");EVIL_CSS_HERE;background:url(\\\\\\\"cid:\\\")'>\",\"RUSTSEC-2021-0158\":\"<svg xmlns=\\\"http://www.w3.org/2000/svg\\\">\\n  <a>\\n    <animateMotion attributeName=\\\"href\\\" to=\\\"javascript:alert('SET_XSS')\\\"></animateMotion>\\n    <text y=\\\"30\\\">Click set</text>\\n  </a>\\n</svg>\",\"RUSTSEC-2026-0373\":\"<div style='background:URL(\\\"https://evil.com/ping\\\");'>\"}")


class NormalizerPolicyTests(unittest.TestCase):
    def normalize(self, value, **kwargs):
        context = dict(owner=True, field="main_text", scope_id=SCOPE,
                       protected_context=ProtectedContext())
        context.update(kwargs)
        return normalize_html(value, **context)

    def tree(self, result):
        return html5lib.parseFragment(result.html, treebuilder="etree",
                                      namespaceHTMLElements=False)

    def reject(self, value, **kwargs):
        with patch("page_editor.clean.nh3.clean", wraps=nh3.clean) as cleaner:
            with self.assertRaises(PolicyError) as caught:
                self.normalize(value, **kwargs)
            self.assertNotIsInstance(caught.exception, ControlledUnsupported)
            self.assertTrue(caught.exception.code)
            self.assertEqual(str(caught.exception), caught.exception.code)
            cleaner.assert_not_called()

    def unsupported(self, value, code):
        with patch("page_editor.clean.nh3.clean", wraps=nh3.clean) as cleaner:
            with self.assertRaises(ControlledUnsupported) as caught:
                self.normalize(value)
            self.assertEqual(caught.exception.code, code)
            cleaner.assert_not_called()

    def test_safe_text_metrics_hashes_and_idempotence(self):
        value = "<p>Привет <strong>мир</strong> 😀</p>"
        with patch("page_editor.clean.nh3.clean", wraps=nh3.clean) as cleaner:
            result = self.normalize(value)
            self.assertGreaterEqual(cleaner.call_count, 1)
        self.assertEqual(result.policy_version, "es-format-v1")
        self.assertEqual(result.html, value)
        self.assertFalse(result.changed)
        self.assertEqual(result.source_sha256, hashlib.sha256(value.encode()).hexdigest())
        self.assertEqual(result.normalized_sha256, hashlib.sha256(result.html.encode()).hexdigest())
        self.assertEqual((result.metrics.node_count, result.metrics.max_depth), (2, 2))
        self.assertEqual(result.metrics.text_codepoints, len("Привет мир 😀"))
        self.assertEqual(result.metrics.source_bytes, len(value.encode()))
        self.assertEqual(result.pending_assets, ())
        again = self.normalize(result.html)
        self.assertEqual(again.html, result.html)
        self.assertFalse(again.changed)
        self.assertEqual(again.warnings, ())

    def test_unicode_entities_and_crlf(self):
        value = "<p>e\u0301\r\n&amp;😀</p>"
        result = self.normalize(value)
        self.assertEqual(result.html, "<p>é\n&amp;😀</p>")
        self.assertEqual(result.metrics.text_codepoints, 4)
        self.assertTrue(result.changed)
        self.assertTrue(all(w.field == "main_text" for w in result.warnings))

    def test_owner_h1_employee_h2(self):
        self.assertEqual(self.normalize("<h1>Body</h1>").html, "<h1>Body</h1>")
        self.assertEqual(self.normalize("<h2>Body</h2>", owner=False).html, "<h2>Body</h2>")
        self.reject("<h1>Body</h1>", owner=False)

    def test_semantic_aliases_and_positive_css_marks(self):
        result = self.normalize("<p><b>B</b><i>I</i><u>U</u><s>S</s><sub>L</sub><sup>H</sup></p>")
        self.assertEqual(result.html, "<p><strong>B</strong><em>I</em><u>U</u><s>S</s><sub>L</sub><sup>H</sup></p>")
        for css, mark in [("font-weight:700", "strong"), ("font-style:italic", "em"),
                          ("text-decoration:underline", "u"),
                          ("text-decoration:line-through", "s"),
                          ("vertical-align:sub", "sub"), ("vertical-align:super", "sup")]:
            with self.subTest(css=css):
                result = self.normalize('<p><span style="' + css + '">X</span></p>')
                self.assertEqual(self.tree(result).find(".//" + mark).text, "X")

    def test_css_carriers_preserve_nested_text_and_format(self):
        value = '<p style="text-align:center;margin-left:0px;margin-top:64px"><span style="font-family:Arial;font-size:12.50px;color:#AbC;background-color:transparent">A<strong>B</strong>C</span></p>'
        result = self.normalize(value)
        tree = self.tree(result)
        self.assertEqual(tree.find("p").attrib, {"data-es-align":"center", "data-es-ml":"0", "data-es-mt":"64"})
        span = tree.find(".//span")
        self.assertEqual(span.attrib, {"data-es-font":"arial", "data-es-size":"12.5",
                                      "data-es-fg":"#aabbcc", "data-es-bg":"transparent"})
        self.assertEqual("".join(tree.itertext()), "ABC")
        self.assertEqual(span.find("strong").text, "B")
        self.assertNotIn("style=", result.html)
        self.assertEqual(self.normalize(result.html).html, result.html)

    def test_known_font_and_size_boundaries(self):
        for font in ("inter", "oswald", "arial", "georgia", "times-new-roman", "courier-new"):
            with self.subTest(font=font):
                self.assertIn('data-es-font="' + font + '"',
                              self.normalize('<span data-es-font="' + font + '">X</span>').html)
        for size in ("8", "72"):
            self.assertIn('data-es-size="' + size + '"',
                          self.normalize('<span data-es-size="' + size + '">X</span>').html)
        for size in ("7", "73", "-1", "NaN", "Infinity", "1e1", "+12"):
            with self.subTest(size=size):
                self.reject('<span data-es-size="' + size + '">X</span>')
        for css in ("color:transparent", "margin-left:65px", "margin-left:-1px",
                    "margin-left:10%", "font-family:unknown"):
            with self.subTest(css=css):
                self.reject('<p style="' + css + '">X</p>')

    def test_whole_source_rejection_before_cleaner(self):
        vectors = ["<script>alert(1)</script>", '<p onclick="alert(1)">X</p>',
                   '<p>ok</p onclick="alert(1)">', "<iframe></iframe>", "<svg></svg>",
                   "<math></math>", "<object></object>", "<form></form>", "<base>",
                   "<meta>", "<custom>X</custom>", "<!--unknown-->",
                   '<p class="esf-runtime">X</p>', '<p id="toolbar">X</p>',
                   '<span data-es-unknown="1">X</span>',
                   '<p title="a" title="b">X</p>',
                   '<a href="javascript:alert(1)', '<script']
        for value in vectors:
            with self.subTest(value=value):
                self.reject("<p>SAFE_PREFIX</p>" + value)
        self.assertEqual(self.normalize("<p>SAFE_PREFIX</p>").html, "<p>SAFE_PREFIX</p>")
        self.assertEqual(self.normalize("<p>&lt;script</p>").html, "<p>&lt;script</p>")

    def test_upstream_ammonia_pocs_rejected_before_native_clean(self):
        for advisory, value in POCS.items():
            with self.subTest(advisory=advisory):
                self.reject(value)

    def test_css_token_and_conflict_rejection(self):
        for css in (r"background-image:u\72l(https://example.invalid/x)",
                    r"width:e\78pression(1)", "position:fixed", "z-index:1",
                    "line-height:2", "color:var(--x)", "font-size:calc(12px)",
                    "@import 'https://example.invalid/x'", "color:red",
                    "font-size:12px;font-size:13px"):
            with self.subTest(css=css):
                self.reject('<span style="' + escape(css, quote=True) + '">X</span>')
        self.reject('<span data-es-size="12" style="font-size:13px">X</span>')

    def test_templates_rejected(self):
        for marker in ("{{ request.user }}", "{% include x %}", "{# secret #}"):
            with self.subTest(marker=marker):
                self.reject("<p>" + marker + "</p>")

    def test_links_positive_literals_and_noopener(self):
        for href in ("https://example.invalid/a?q=1", "http://example.invalid/",
                     "/service/", "/search/?q=javascript%3Aword"):
            with self.subTest(href=href):
                result = self.normalize('<a href="' + escape(href, quote=True) + '" target="_blank">X</a>')
                link = self.tree(result).find("a")
                self.assertEqual(link.attrib["href"], href)
                self.assertEqual(set(link.attrib["rel"].split()), {"noopener"})

    def test_unsafe_links_whole_rejection(self):
        for href in ("javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,x",
                     "file:///etc/passwd", "vbscript:1", "blob:https://example.invalid/x",
                     "//example.invalid/x", "https://user:pw@example.invalid/",
                     "/manage/", "/%6danage/", "/../../x", "/a\\b", "java\nscript:1"):
            with self.subTest(href=href):
                self.reject('<a href="' + escape(href, quote=True) + '">X</a>')
        self.reject('<a href="java&#x73;cript:alert(1)">X</a>')

    def test_anchor_facts_nfc_and_explicit_cross_field(self):
        result = self.normalize('<p data-es-anchor="e\u0301">X</p><a href="#%C3%A9">Y</a>')
        self.assertEqual([(a.label, a.field) for a in result.anchors], [("é", "main_text")])
        self.assertEqual([(a.field, a.anchor, a.href) for a in result.anchor_links],
                         [("main_text", "é", "#%C3%A9")])
        cross = self.normalize('<a href="#there" data-es-target-field="intro_text" data-es-target-anchor="there">Y</a>')
        self.assertEqual(cross.anchor_links[0].field, "intro_text")
        unresolved = self.normalize('<a href="#missing">X</a>')
        self.assertIn("ANCHOR_TARGET_UNRESOLVED", [w.code for w in unresolved.warnings])
        external = self.normalize('<a href="/other/#there">X</a>')
        self.assertEqual(external.anchor_links, ())
        self.reject('<p data-es-anchor="é">A</p><p data-es-anchor="e\u0301">B</p>')
        self.reject('<a href="#x" data-es-target-field="main_text">X</a>')

    def test_pending_integrations_fail_closed_not_success(self):
        table = self.normalize("<table><tr><td>X</td></tr></table>")
        self.assertIn("<tbody><tr><td>X</td></tr></tbody>", table.html)
        self.assertEqual(table.ui_table_slots_used, 1)
        self.assertTrue(table.table_capabilities[0].rich_widget)
        self.unsupported('<span data-es-protected="' + SCOPE + '">X</span>',
                         "PROTECTED_INTEGRATION_UNSUPPORTED")
        self.unsupported('<a href="docs/next/">X</a>', "RELATIVE_URL_CONTEXT_REQUIRED")
        self.reject('<table><tr><td onclick="bad()">X</td></tr></table>')
        self.reject('<a href="docs/next/" target="evil">X</a>')

    def test_inherited_style_resets_are_explicitly_pending(self):
        cases = [("strong", "font-weight:normal"), ("strong", "font-weight:400"),
                 ("em", "font-style:normal"), ("u", "text-decoration:none"),
                 ("s", "text-decoration-line:none"), ("sub", "vertical-align:baseline"),
                 ("sup", "vertical-align:baseline")]
        for parent, css in cases:
            with self.subTest(parent=parent, css=css):
                self.unsupported("<" + parent + '><span style="' + css + '">X</span></' + parent + ">",
                                 "STYLE_CONTEXT_UNSUPPORTED")
                self.reject('<p><span style="' + css + ';position:fixed">X</span></p>')
                self.reject('<span style="' + css + '">X</span><script>bad()</script>')

    def test_source_byte_boundary(self):
        prefix, suffix = '<span data-es-anchor="', '"></span>'
        value = prefix + "A" * (1048576 - len(prefix) - len(suffix)) + suffix
        self.assertEqual(len(value.encode()), 1048576)
        self.assertEqual(self.normalize(value).metrics.source_bytes, 1048576)
        self.reject(value.replace('"></span>', 'A"></span>'))

    def test_codepoint_boundary_not_utf16_or_bytes(self):
        result = self.normalize("<p>" + "😀" * 200000 + "</p>")
        self.assertEqual(result.metrics.text_codepoints, 200000)
        self.reject("<p>" + "😀" * 200001 + "</p>")

    def test_source_node_and_depth_boundaries(self):
        value = "<p>" + "<span>x</span>" * 19999 + "</p>"
        result = self.normalize(value)
        self.assertEqual((result.metrics.node_count, result.metrics.max_depth), (20000, 2))
        self.reject("<p>" + "<span>x</span>" * 20000 + "</p>")
        self.assertEqual(self.normalize("<blockquote>" * 32 + "X" + "</blockquote>" * 32).metrics.max_depth, 32)
        self.reject("<blockquote>" * 33 + "X" + "</blockquote>" * 33)

    def test_restricted_cleaner_actual_configuration(self):
        with patch("page_editor.clean.nh3.clean", wraps=nh3.clean) as cleaner:
            result = self.normalize('<span data-es-size="12">SAFE</span>')
        self.assertIn("SAFE", result.html)
        for call in cleaner.call_args_list:
            kwargs = call.kwargs
            self.assertNotIn("style", kwargs["tags"])
            self.assertNotIn("svg", kwargs["tags"])
            self.assertNotIn("filter_style_properties", kwargs)
            self.assertNotIn("*", kwargs["attributes"])
            self.assertTrue(all("style" not in attrs for attrs in kwargs["attributes"].values()))
            self.assertEqual(kwargs["url_schemes"], {"http", "https"})

    def test_cleaner_unexpected_text_loss_rejected(self):
        actual = nh3.clean
        def lossy(*args, **kwargs):
            return actual(*args, **kwargs).replace("INDEPENDENT_SAFE_CANARY", "LOST")
        with patch("page_editor.clean.nh3.clean", side_effect=lossy):
            with self.assertRaises(PolicyError) as caught:
                self.normalize("<p>INDEPENDENT_SAFE_CANARY</p>")
        self.assertNotIsInstance(caught.exception, ControlledUnsupported)
        self.assertEqual(caught.exception.code, "SANITIZER_DIVERGENCE")

    def test_no_network_fetch_for_literal_link(self):
        with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")), \
             patch("socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("fetch forbidden")):
            self.assertIn("example.invalid", self.normalize('<a href="https://example.invalid/x">X</a>').html)

    def test_invalid_context_and_input_types(self):
        for value in (None, b"text", {}, [], 1):
            with self.subTest(value_type=type(value).__name__):
                self.reject(value)
        for kwargs in ({"owner":1}, {"field":[]}, {"field":{}}, {"field":"title"},
                       {"scope_id":"INVALID"}, {"scope_id":SCOPE.upper()},
                       {"protected_context":{}}):
            with self.subTest(kwargs=repr(kwargs)):
                self.reject("<p>X</p>", **kwargs)

    def test_context_unchanged_and_result_frozen(self):
        context = ProtectedContext()
        result = self.normalize("<p>X</p>", protected_context=context)
        self.assertEqual(context.nodes, ())
        with self.assertRaises(AttributeError):
            result.html = "changed"
        self.assertIsInstance(result.warnings, tuple)
        self.assertIsInstance(result.anchors, tuple)


if __name__ == "__main__":
    unittest.main()

