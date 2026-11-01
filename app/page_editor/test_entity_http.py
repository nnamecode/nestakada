"""FR07-008 real handler/PG/child entities; not socket/Nginx evidence."""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import time
from unittest.mock import patch

from django.test import TransactionTestCase, override_settings

from page_editor import test_check_http as H
from page_editor.checks import verify_check_receipt


def memory_facts():
    root = Path('/sys/fs/cgroup')
    return {'peakBytes': int((root / 'memory.peak').read_text()),
        'maxBytes': (root / 'memory.max').read_text().strip(),
        'events': {key: int(value) for key, value in
            (line.split() for line in (root / 'memory.events').read_text().splitlines())}}


@override_settings(ROOT_URLCONF='page_editor.test_check_http', MIDDLEWARE=H.TEST_MIDDLEWARE,
                   AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EntityAdmissionHttpTests(TransactionTestCase):
    setUp = H.EditorCheckHttpTests.setUp
    login = H.EditorCheckHttpTests.login
    raw = H.EditorCheckHttpTests.raw
    payload = H.EditorCheckHttpTests.payload
    post = H.EditorCheckHttpTests.post
    state = H.EditorCheckHttpTests.state
    context = H.EditorCheckHttpTests.context
    assert_error = H.EditorCheckHttpTests.assert_error

    def entity_case(self, source, *, accepted=True, large=False):
        before = self.state()
        self.assertLessEqual(len(source.encode()), 1048576)
        for actor, client in ((self.owner, self.owner_client), (self.employee, self.employee_client)):
            with self.subTest(role='owner' if actor == self.owner else 'assigned_employee'):
                wire = self.raw(self.payload({'main_text': source}))
                original, children = subprocess.Popen, []

                def capture(*args, **kwargs):
                    process = original(*args, **kwargs)
                    children.append(process)
                    return process

                prior_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
                memory_before = memory_facts()
                started = time.monotonic()
                with patch('editor_runtime.processing.subprocess.Popen', side_effect=capture):
                    response = self.post(client, raw=wire)
                elapsed = time.monotonic() - started
                after_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
                memory_after = memory_facts()
                self.assertEqual(memory_before['maxBytes'], str(768 * 1024 * 1024))
                self.assertEqual(memory_after['maxBytes'], memory_before['maxBytes'])
                self.assertLessEqual(memory_after['peakBytes'], 768 * 1024 * 1024)
                for name in ('oom', 'oom_kill'):
                    self.assertEqual(memory_before['events'].get(name, 0), memory_after['events'].get(name, 0))
                self.assertEqual(len(children), 1, 'ENTITY_REAL_CHILD_COUNT')
                self.assertEqual(children[0].returncode, 0, 'ENTITY_REAL_CHILD_NONZERO')
                with self.assertRaises(ChildProcessError):
                    os.waitpid(children[0].pid, os.WNOHANG)
                if accepted:
                    self.assertEqual(response.status_code, 200, 'VALID_ENTITY_SOURCE_REFUSED')
                    value = response.json()
                    self.assertTrue(value['normalisedChanges'] == {'main_text': source},
                                    'ENTITY_TREE_OR_TEXT_CHANGED')
                    self.assertFalse(value['normalisationChanged'])
                    self.assertTrue(value['inputFingerprint'] == hashlib.sha256(wire).hexdigest())
                    proof = verify_check_receipt(value['checkReceipt'], context=self.context(actor),
                                                 changes=value['normalisedChanges'])
                    self.assertEqual(proof['actorId'], actor.pk)
                    self.assertTrue(proof['inputFingerprint'] == hashlib.sha256(wire).hexdigest())
                else:
                    self.assert_error(response, 400, 'EDITOR_INPUT_REJECTED')
                    self.assertNotIn(b'checkReceipt', response.content)
                self.assertEqual(self.state(), before)
                if large:
                    print(json.dumps({'scope': 'FR07-008-handler-entity',
                        'role': 'owner' if actor == self.owner else 'assigned_employee',
                        'expectedAcceptance': accepted, 'httpStatus': response.status_code,
                        'sourceBytes': len(source.encode()), 'sourceSha256': hashlib.sha256(source.encode()).hexdigest(),
                        'wallSeconds': round(elapsed, 3), 'childReturnCode': children[0].returncode,
                        'childUserSeconds': round(after_cpu.ru_utime - prior_cpu.ru_utime, 3),
                        'childSysSeconds': round(after_cpu.ru_stime - prior_cpu.ru_stime, 3),
                        'childLifetimePeakRssKiB': after_cpu.ru_maxrss,
                        'cgroupBefore': memory_before, 'cgroupAfter': memory_after,
                        'peakIncludesFixtureAndPriorTests': True,
                        'childReaped': True, 'domainUnchanged': True, 'frameworkReaderSeam': True}), flush=True)

    def test_entity_200000_actual_handler_verified_proof_both_roles(self):
        self.entity_case('<p>' + '&amp;' * 200000 + '</p>', large=True)

    def test_entity_200001_decoded_limit_no_proof_and_no_mutation(self):
        self.entity_case('<p>' + '&amp;' * 200001 + '</p>', accepted=False, large=True)

    def test_escaped_script_remains_exact_safe_text_not_real_markup(self):
        self.entity_case('<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>')

    def test_table_whitespace_and_entity_content_are_preserved(self):
        self.entity_case('<table> \n<tbody><tr><td>A&amp;B</td></tr></tbody></table>')

    def test_exact_20000_nodes_actual_handler_child_scope_proof_and_no_mutation(self):
        source = '<p>' + '<span></span>' * 19999 + '</p>'
        self.assertEqual(source.count('<span>') + 1, 20000)
        self.entity_case(source, large=True)
