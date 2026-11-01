"""CM07 combined maxima: real framework/PG/child, not Nginx evidence."""
import gc
import hashlib
import json
import os
import resource
import subprocess
import time
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import UUID, uuid4

import html5lib
from django.core.serializers.json import DjangoJSONEncoder
from django.test import TransactionTestCase, override_settings

from accounts.services import set_grant
from editor_runtime import processing
from editor_runtime.child_bootstrap import ADDRESS_BYTES, CPU_SECONDS
from editor_runtime.guards import EditorSlot
from media_library.models import AssetUsage
from page_editor import test_check_http as H
from page_editor.checks import inspect_context, verify_check_receipt
from page_editor.test_failure_http import cgroup_facts
from page_versions import schema as S, services as V
from page_versions.models import (PageContentState, PageRevision, OwnerDraft,
    RestoreStage, VersionBasePin, OperationReceipt, RevisionMetadata,
    RevisionProtection, IdentityReservation)


def sha(value):
    return hashlib.sha256(value.encode('utf-8') if isinstance(value, str) else value).hexdigest()


@override_settings(ROOT_URLCONF='page_editor.test_check_http', MIDDLEWARE=H.TEST_MIDDLEWARE,
    AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CombinedMaximumHttpTests(TransactionTestCase):
    setUp = H.EditorCheckHttpTests.setUp
    login = H.EditorCheckHttpTests.login
    raw = H.EditorCheckHttpTests.raw
    payload = H.EditorCheckHttpTests.payload
    post = H.EditorCheckHttpTests.post

    def domain(self):
        """Hash all selected rows/columns; never materialise/print all payloads."""
        result = {}
        encoder = DjangoJSONEncoder(sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        for model in (PageContentState, PageRevision, OwnerDraft, RestoreStage,
                      VersionBasePin, AssetUsage, OperationReceipt, RevisionMetadata,
                      RevisionProtection, IdentityReservation):
            digest, count = hashlib.sha256(), 0
            for row in model.objects.order_by('pk').values().iterator(chunk_size=1):
                digest.update(b'\x1e')
                for fragment in encoder.iterencode(row):
                    digest.update(fragment.encode('utf-8'))
                digest.update(b'\n')
                count += 1
            result[model._meta.label] = {'rows': count, 'sha256': digest.hexdigest()}
        return result

    def rich(self, label):
        # All limits simultaneously; source/candidate labels and text differ.
        text = '🚀' * 150000 + label * 50000
        tail = '"><span>' + '<span>' * 30 + text + '</span>' * 31
        tail += '<span></span>' * 19968 + '</p>'
        prefix = '<p data-es-anchor="'
        padding = 1048576 - len((prefix + tail).encode('utf-8'))
        source = prefix + label * padding + tail
        self.assertEqual(len(source.encode('utf-8')), 1048576, 'CM_RAW_BYTES')
        # Stock parser is independent of the optimized product helper/memo.
        parser = html5lib.HTMLParser(tree=html5lib.getTreeBuilder('etree'),
                                    namespaceHTMLElements=True)
        tree = parser.parseFragment(source)
        self.assertFalse(bool(parser.errors), 'CM_FIXTURE_PARSE_ERRORS')
        count, deepest, codepoints = 0, 0, len(tree.text or '')
        stack = [(node, 1) for node in tree]
        while stack:
            node, depth = stack.pop()
            count += 1
            deepest = max(deepest, depth)
            codepoints += len(node.text or '') + len(node.tail or '')
            stack.extend((child, depth + 1) for child in node)
        self.assertEqual((count, deepest, codepoints), (20000, 32, 200000),
                         'CM_INDEPENDENT_TREE_LIMITS')
        self.assertTrue(tree[0].attrib == {'data-es-anchor': label * padding},
                        'CM_STOCK_ANCHOR_CHANGED')
        del tree, parser, stack, text, tail
        return source

    def price(self):
        columns = [{'id': str(UUID(int=i + 1)), 'label': '🚀' * 500} for i in range(32)]
        return {'columns': columns, 'rows': [
            {'id': str(UUID(int=1000 + i)), 'label': '🚀' * 500,
             'cells': [{'column_id': columns[j]['id'], 'kind': 'text', 'text': '🚀' * 1000}
                       for j in range(20)]} for i in range(500)]}

    def seed(self, *, draft=False):
        sources = {'intro_text': self.rich('A'), 'main_text': self.rich('B')}
        snapshot = S.snapshot_v1(self.page.kind, **sources)
        selector = {}
        if draft:
            old = OwnerDraft.objects.get(page=self.page)
            V.cancel_owner_draft(actor=self.owner, page_id=self.page.pk, draft_id=old.pk,
                draft_revision=old.revision, expected_generation=1, operation_id=uuid4())
            V.save_owner_draft(actor=self.owner, page_id=self.page.pk,
                base_revision=self.initial, snapshot=snapshot,
                expected_generation=1, operation_id=uuid4())
            selected = OwnerDraft.objects.get(page=self.page)
            selector = {'source': 'owner-draft', 'draftId': str(selected.pk),
                        'draftRevision': selected.revision}
        else:
            self.initial = V.commit_owner(actor=self.owner, page_id=self.page.pk,
                base_revision=self.initial, snapshot=snapshot,
                expected_generation=1, operation_id=uuid4())['result_id']
        return sources, selector

    def request_case(self, case, actor, client, sources, changes, selector):
        source_hashes = {field: sha(value) for field, value in sources.items()}
        expected_hashes = {field: sha(value) for field, value in changes.items()
                           if field in ('intro_text', 'main_text')}
        self.assertEqual(len(set([*source_hashes.values(), *expected_hashes.values()])), 4,
                         'CM_SOURCES_NOT_DISTINCT')
        price_hash = sha(self.raw(changes['price'])) if 'price' in changes else None
        payload = self.payload(changes)
        selected_context = None
        if selector:
            payload.update(editingFrom='owner-draft', draftBasis={
                'id': selector['draftId'], 'revision': selector['draftRevision']})
            from page_editor.source_context import current_selector
            selected_context = {**current_selector(), 'editingFrom': 'owner-draft',
                                'draftBasis': payload['draftBasis']}
        raw = self.raw(payload)
        input_hash = sha(raw)
        self.assertLessEqual(len(raw), (64 if 'price' in changes else 5) * 1024 * 1024,
                             'CM_WIRE_BUDGET')
        original_url = self.url
        if selector:
            self.url += '?' + urlencode(selector)
        before = self.domain()
        gc.collect()
        memory_before = cgroup_facts()
        self.assertEqual(memory_before['memory.max'], str(768 * 1024 * 1024))
        self.assertEqual(memory_before['pids.max'], '128')
        quota, period = map(int, memory_before['cpu.max'].split())
        self.assertEqual(quota, period)
        self.assertEqual((ADDRESS_BYTES, CPU_SECONDS, processing.WORK_SECONDS),
                         (384 * 1024 * 1024, 10, 20.0))
        processes, observed = [], []
        original_popen = subprocess.Popen

        def capture(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            processes.append(process)
            return process

        def actual_normalize(wire, context):
            observed.append({'source': context['source'],
                'base': context['base_revision_id'],
                'hashes': {field: sha(context['embedded_source'][field])
                           for field in ('intro_text', 'main_text')}})
            return processing.normalize_input(wire, context)

        cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.monotonic()
        completed, response = False, None
        try:
            with patch('page_editor.views.normalize_input', side_effect=actual_normalize), \
                 patch('editor_runtime.processing.subprocess.Popen', side_effect=capture):
                response = self.post(client, raw=raw, reader=lambda request, profile: raw)
            elapsed = time.monotonic() - started
            cpu_after = resource.getrusage(resource.RUSAGE_CHILDREN)
            memory_after = cgroup_facts()
            code = 'NO_FIXED_CODE'
            if response.status_code != 200:
                try:
                    candidate = response.json().get('code')
                    if isinstance(candidate, str) and 0 < len(candidate) <= 120 and all(
                        char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for char in candidate):
                        code = candidate
                except (ValueError, AttributeError, TypeError):
                    pass
            evidence = {'scope': 'CM07-framework-real-child', 'case': case,
                'role': 'owner' if actor == self.owner else 'assigned_employee',
                'status': 'OBSERVATION', 'httpStatus': response.status_code, 'code': code,
                'wireBytes': len(raw), 'wireSha256': input_hash,
                'responseBytes': len(response.content), 'responseSha256': sha(response.content),
                'sourceHashes': source_hashes, 'candidateHashes': expected_hashes,
                'handlerSeconds': round(elapsed, 3),
                'childUserSeconds': round(cpu_after.ru_utime - cpu_before.ru_utime, 3),
                'childSysSeconds': round(cpu_after.ru_stime - cpu_before.ru_stime, 3),
                'childExitCodes': [process.returncode for process in processes],
                'handlerBefore': memory_before, 'handlerAfter': memory_after,
                'cgroupPeakIncludesFixtureAndEarlierCases': True,
                'frameworkReaderSeam': True, 'nginxProof': False,
                'retainedSourceProtectedParseProof': False}
            print(json.dumps(evidence), flush=True)
            self.assertEqual(len(processes), 1, 'CM_REAL_CHILD_COUNT')
            process = processes[0]
            self.assertIsNotNone(process.returncode, 'CM_CHILD_NOT_WAITED')
            with self.assertRaises(ProcessLookupError):
                os.kill(process.pid, 0)
            with self.assertRaises(ChildProcessError):
                os.waitpid(process.pid, os.WNOHANG)
            self.assertTrue(all(stream.closed for stream in
                (process.stdin, process.stdout, process.stderr)), 'CM_STREAMS_NOT_CLOSED')
            self.assertEqual(self.domain(), before, 'CM_DOMAIN_CHANGED')
            self.assertEqual(len(observed), 1, 'CM_NORMALIZER_NOT_ONCE')
            self.assertEqual(observed[0]['hashes'], source_hashes, 'CM_SELECTED_SOURCE_HASH')
            self.assertEqual(observed[0]['base'], str(self.initial), 'CM_SELECTED_BASE')
            self.assertEqual(observed[0]['source']['editingFrom'],
                             'owner-draft' if selector else 'current', 'CM_SOURCE_MODE')
            if selector:
                self.assertEqual(observed[0]['source']['draftBasis'], payload['draftBasis'])
            for name in ('memory.max', 'cpu.max', 'pids.max'):
                self.assertEqual(memory_before[name], memory_after[name], 'CM_CAP_CHANGED')
            for name in ('oom', 'oom_kill'):
                self.assertEqual(memory_before['memory.events'].get(name, 0),
                                 memory_after['memory.events'].get(name, 0), 'CM_OOM')
            self.assertLessEqual(int(memory_after['memory.peak']), 768 * 1024 * 1024)
            if response.status_code != 200:
                self.assertNotIn(b'checkReceipt', response.content, 'CM_FAILURE_PROOF')
            self.assertEqual(response.status_code, 200, 'CM_VALID_MAX_REFUSED')
            self.assertEqual(process.returncode, 0, 'CM_CHILD_NONZERO')
            value = response.json()
            self.assertEqual(value['inputFingerprint'], input_hash, 'CM_INPUT_HASH')
            normalized = value['normalisedChanges']
            self.assertEqual(set(normalized), set(changes), 'CM_FIELDS_CHANGED')
            for field, expected in expected_hashes.items():
                self.assertTrue(sha(normalized[field]) == expected, 'CM_RICH_CHANGED_OR_TRUNCATED')
            self.assertFalse(value['normalisationChanged'], 'CM_NORMALIZATION_UNEXPECTED')
            if price_hash is not None:
                price = normalized['price']
                self.assertTrue(sha(self.raw(price)) == price_hash, 'CM_PRICE_CHANGED_OR_TRUNCATED')
                self.assertEqual((len(price['columns']), len(price['rows']),
                    sum(len(row['cells']) for row in price['rows'])), (32, 500, 10000))
            context = inspect_context(actor=actor, page_id=self.page.pk, generation=1,
                                      origin='http://localhost', selector=selected_context)
            proof = verify_check_receipt(value['checkReceipt'], context=context, changes=normalized)
            self.assertEqual(proof['actorId'], actor.pk, 'CM_PROOF_ACTOR')
            self.assertEqual(proof['inputFingerprint'], input_hash, 'CM_PROOF_INPUT')
            with EditorSlot():
                pass
            completed = True
            print(json.dumps({'scope': 'CM07-framework-real-child', 'case': case,
                'role': evidence['role'], 'status': 'PASS', 'receiptVerified': True,
                'domainUnchanged': True, 'childReaped': True, 'streamsClosed': True,
                'slotFree': True}), flush=True)
        finally:
            self.url = original_url
            if not completed:
                # Preserve the MAX failure; recovery never substitutes a PASS.
                with EditorSlot():
                    pass
                healthy = self.post(self.owner_client, self.payload({'main_text': '<p>HEALTHY</p>'}))
                healthy_ok = healthy.status_code == 200 and bool(healthy.json().get('checkReceipt'))
                print(json.dumps({'scope': 'CM07-failure-recovery', 'case': case,
                    'healthyCheck': healthy_ok, 'domainUnchanged': self.domain() == before,
                    'slotFree': True}), flush=True)
                self.assertTrue(healthy_ok, 'CM_HEALTHY_RECOVERY_FAILED')
                self.assertEqual(self.domain(), before, 'CM_RECOVERY_DOMAIN_CHANGED')

    def run_case(self, case, *, price=False, draft=False):
        construction_started = time.monotonic()
        construction_before = cgroup_facts()
        sources, selector = self.seed(draft=draft)
        changes = {'intro_text': self.rich('C'), 'main_text': self.rich('D')}
        if price:
            changes['price'] = self.price()
        actors = [(self.owner, self.owner_client)]
        if not draft:
            if price:
                set_grant(actor=self.owner, employee=self.price_employee, page=self.page,
                          intro_text=True, main_text=True, price=True)
                actors.append((self.price_employee, self.price_client))
            else:
                actors.append((self.employee, self.employee_client))
        gc.collect()
        print(json.dumps({'scope': 'CM07-fixture-construction', 'case': case,
            'constructionSeconds': round(time.monotonic() - construction_started, 3),
            'constructionBefore': construction_before, 'constructionAfter': cgroup_facts(),
            'includesStockParserAndSeed': True, 'richBytesEach': 1048576,
            'richNodesEach': 20000, 'richDepthEach': 32, 'richCodepointsEach': 200000}), flush=True)
        for actor, client in actors:
            self.request_case(case, actor, client, sources, changes, selector)

    def test_cm07_001_current_two_rich_all_limits_retained_sources_both_roles(self):
        self.run_case('CM07-001')

    def test_cm07_002_current_two_rich_all_limits_and_max_price_both_roles(self):
        self.run_case('CM07-002', price=True)

    def test_cm07_003_owner_draft_two_rich_all_limits_retained_selected_source(self):
        self.run_case('CM07-003', draft=True)
