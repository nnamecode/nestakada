"""F07-008: real handler/PG/child Unicode admission, framework reader seam."""
import hashlib
import unicodedata

from django.test import TransactionTestCase, override_settings

from page_editor import test_check_http as H
from page_editor import test_embedded_http as E
from page_editor.checks import verify_check_receipt


@override_settings(ROOT_URLCONF='page_editor.test_check_http', MIDDLEWARE=H.TEST_MIDDLEWARE,
                   AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UnicodeAdmissionTests(TransactionTestCase):
    setUp = H.EditorCheckHttpTests.setUp
    login = H.EditorCheckHttpTests.login
    raw = H.EditorCheckHttpTests.raw
    payload = H.EditorCheckHttpTests.payload
    post = H.EditorCheckHttpTests.post
    state = H.EditorCheckHttpTests.state
    context = H.EditorCheckHttpTests.context
    assert_error = H.EditorCheckHttpTests.assert_error

    def actors(self):
        return ((self.owner, self.owner_client), (self.employee, self.employee_client))

    def accepted(self, source, canonical):
        before = self.state()
        for actor, client in self.actors():
            with self.subTest(role='owner' if actor == self.owner else 'assigned_employee'):
                payload = self.payload({'main_text': source})
                wire = self.raw(payload)
                response = self.post(client, raw=wire)
                self.assertEqual(response.status_code, 200, 'UNICODE_EXACT_BOUND_REFUSED')
                value = response.json()
                self.assertTrue(value['normalisedChanges'] == {'main_text': canonical},
                                'UNICODE_CANONICAL_CHANGED_OR_TRUNCATED')
                self.assertTrue(value['normalisationChanged'])
                self.assertIn({'field': 'main_text', 'code': 'NORMALIZATION_REVIEW_REQUIRED'},
                              value['fieldWarnings'])
                self.assertTrue(value['inputFingerprint'] == hashlib.sha256(wire).hexdigest())
                proof = verify_check_receipt(value['checkReceipt'], context=self.context(actor),
                                             changes=value['normalisedChanges'])
                self.assertEqual(proof['actorId'], actor.pk)
                self.assertTrue(proof['inputFingerprint'] == hashlib.sha256(wire).hexdigest())
                self.assertEqual(self.state(), before)

    def refused(self, source):
        before = self.state()
        for actor, client in self.actors():
            with self.subTest(role='owner' if actor == self.owner else 'assigned_employee'):
                response = self.post(client, self.payload({'main_text': source}))
                self.assert_error(response, 400, 'EDITOR_INPUT_REJECTED')
                self.assertNotIn(b'checkReceipt', response.content)
                self.assertNotIn(b'result_id', response.content)
                self.assertEqual(self.state(), before)

    def test_nfd_exact_200000_after_nfc_owner_and_assigned_employee(self):
        source = '<p>' + 'e\u0301' * 200000 + '</p>'
        self.assertLessEqual(len(source.encode()), 1048576)
        self.accepted(source, '<p>' + 'é' * 200000 + '</p>')

    def test_nfd_200001_after_nfc_refused_without_proof_or_mutation(self):
        source = '<p>' + 'e\u0301' * 200001 + '</p>'
        self.assertLessEqual(len(source.encode()), 1048576)
        self.refused(source)

    def test_crlf_exact_200000_after_newline_normalization_both_roles(self):
        source = '<p>' + 'x\r\n' * 100000 + '</p>'
        canonical = '<p>' + 'x\n' * 100000 + '</p>'
        self.assertEqual(len('x\n' * 100000), 200000)
        self.accepted(source, canonical)

    def test_raw_source_byte_limit_precedes_hangul_nfc_contraction(self):
        text = '\u1100\u1161' * 180000
        source = '<p>' + text + '</p>'
        normalized = unicodedata.normalize('NFC', text)
        self.assertEqual(len(normalized), 180000)
        self.assertGreater(len(source.encode()), 1048576)
        self.assertLess(len(('<p>' + normalized + '</p>').encode()), 1048576)
        self.refused(source)


@override_settings(ROOT_URLCONF='page_editor.test_check_http', MIDDLEWARE=H.TEST_MIDDLEWARE,
                   AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IssuedUnicodeAdmissionTests(TransactionTestCase):
    login = H.EditorCheckHttpTests.login
    raw = H.EditorCheckHttpTests.raw
    payload = H.EditorCheckHttpTests.payload
    post = H.EditorCheckHttpTests.post
    state = H.EditorCheckHttpTests.state
    context = H.EditorCheckHttpTests.context
    upload = E.EmbeddedEditorHttpTests.upload
    ref = E.EmbeddedEditorHttpTests.ref
    current = E.EmbeddedEditorHttpTests.current
    selector = E.EmbeddedEditorHttpTests.selector
    path = E.EmbeddedEditorHttpTests.path
    issue = E.EmbeddedEditorHttpTests.issue
    minted = E.EmbeddedEditorHttpTests.minted
    marker = E.EmbeddedEditorHttpTests.marker
    block = E.EmbeddedEditorHttpTests.block

    def setUp(self):
        H.EditorCheckHttpTests.setUp(self)
        self.a = self.upload('png', self.page)  # Actual approved WorkerClient/FS.

    def test_pending_permit_does_not_hide_unicode_review_or_invent_token_only_review(self):
        from editor_runtime.processing import normalize_input
        from page_editor import media

        mint = self.minted()
        before = self.state()
        for slot_text, expected_text, changed in (
                ('e\u0301\r\n😀', 'é\n😀', True),
                ('CANONICAL 😀', 'CANONICAL 😀', False)):
            with self.subTest(semantic_normalization=changed):
                source = self.block(mint, before=slot_text, after='TAIL')
                payload = self.payload({'main_text': source})
                wire = self.raw(payload)
                response = self.post(self.owner_client, raw=wire)
                self.assertEqual(response.status_code, 200)
                value = response.json()
                canonical = self.block(mint, before=expected_text, after='TAIL', permit=False)
                self.assertTrue(value['normalisedChanges'] == {'main_text': canonical},
                                'ISSUED_UNICODE_CANONICAL_CHANGED')
                self.assertEqual(value['normalisationChanged'], changed)
                warning = {'field': 'main_text', 'code': 'NORMALIZATION_REVIEW_REQUIRED'}
                self.assertEqual(warning in value['fieldWarnings'], changed)
                self.assertTrue(value['inputFingerprint'] == hashlib.sha256(wire).hexdigest())
                self.assertNotIn('data-es-media-intent', value['normalisedChanges']['main_text'])
                self.assertNotIn(mint['permit'], response.content.decode())
                record = value['embeddedMedia']['main_text'][0]
                self.assertEqual(record['markerId'], mint['ids']['markerId'])
                self.assertEqual(record['imageId'], mint['ids']['imageId'])
                context = self.context()
                # Independently rerun the real child for the typed derived map,
                # then actual physical evidence; no manufactured READY/proof.
                worker = normalize_input(wire, context.child)
                self.assertTrue(worker['changes'] == value['normalisedChanges'])
                evidence = media.prepare(context, value['normalisedChanges'], derived=worker['derived'])
                self.assertIsNotNone(evidence)
                proof = verify_check_receipt(value['checkReceipt'], context=context,
                    changes=value['normalisedChanges'], media_evidence=evidence.proof,
                    derived_map_hash=worker['derived']['mapHash'])
                self.assertEqual(proof['actorId'], self.owner.pk)
                self.assertTrue(proof['inputFingerprint'] == hashlib.sha256(wire).hexdigest())
                self.assertEqual(self.state(), before)
