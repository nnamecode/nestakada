"""Signed UNIT admission checks; capacity/native/MAIN activation remain separate."""
import copy
import hashlib
import hmac
import uuid
from pathlib import Path
from unittest.mock import patch

from django.db import connection, transaction
from django.test import override_settings

from . import auth, bounded as B, profile as P, recovery as R, services as S, state_v2 as V
from .models import AdmissionPolicy, Credential, Head, Operation, RecoveryReceipt, RoutePolicy
from .protocol import Fault, MAX_BODY, canonical, digest, target, validate
from .tests import JournalFixture


class BoundedFixture(JournalFixture):
    def setUp(self):
        super().setUp()
        token = S._test_mode.set(False)
        self.addCleanup(S._test_mode.reset, token)
        self.runtime = str(uuid.uuid4())
        self.permit = Path(self.tmp.name, 'bounded-permit')
        override = override_settings(TRUST_WRITE_PROFILE='local-bounded-writer',
            TRUST_WRITE_PERMIT_FILE=str(self.permit), TRUST_RUNTIME_ID=self.runtime)
        override.enable(); self.addCleanup(override.disable)
        resource = patch.object(P, 'runtime_resource_facts', return_value=P.DEPLOYMENT['api'])
        resource.start(); self.addCleanup(resource.stop)
        head = Head.objects.get(pk=1)
        head.plan_id = uuid.uuid4(); head.permitted_operations = []; head.permitted_recovery_actions = []
        head.save()
        self.recovery_actor = auth.authenticate('Bearer recovery:' + '3' * 64, 'recovery')

    def sign(self, payload):
        return {'payload': payload, 'signature': hmac.new(bytes.fromhex('3' * 64),
            canonical(payload), hashlib.sha256).hexdigest()}

    def policy(self, epoch=1):
        rows = P.source_files()
        return {'policyId': str(uuid.uuid4()), 'epoch': str(epoch), 'incarnation': self.identity,
            'dbName': connection.settings_dict['NAME'], 'protocolVersion': 1,
            'sourceFiles': rows, 'sourceFingerprint': digest(rows),
            'schemaFingerprint': P.schema_fingerprint(),
            'evidence': {'unit': 'a' * 64, 'calibration': 'b' * 64, 'review': 'c' * 64},
            'caps': copy.deepcopy(B.CAPS)}

    def intent(self, policy=None):
        policy = policy or self.policy()
        with transaction.atomic():
            head = Head.objects.select_for_update().get(pk=1)
            current = B.latest_policy()
            payload = {'schemaVersion': 2, 'scope': B.ACTIVATION_SCOPE,
                'actionId': str(uuid.uuid4()), 'credentialId': 'recovery', 'policy': policy,
                'previousPolicy': {'epoch': str(current.epoch), 'digest': current.policy_digest} if current else None,
                'legacySeal': None if current else B.legacy_seal(head),
                'expected': {'head': V.persistent_values(head), 'stateDigestVersion': 2,
                    'stateDigest': V.state_digest(head)},
                'credentialConfigSha256': B._configuration_sha(),
                'evidence': copy.deepcopy(policy['evidence']), 'configFingerprint': 'd' * 64}
        return self.sign(payload)

    def activate(self, intent=None):
        intent = intent or self.intent()
        # Real guarded UNIT runner uses the existing trust_migrator DB role.
        # Only unfinished final report evidence is substituted by this scope.
        with B.unit_calibration():
            return B.activate(intent, {})

    def lease(self, policy):
        return {'policyDigest': digest(policy), 'runtimeId': self.runtime,
            'credentialConfigSha256': B._configuration_sha(),
            'deployment': {**copy.deepcopy(P.DEPLOYMENT), 'configFingerprint': 'd' * 64, 'evidence': 'e' * 64},
            'exclusion': {'previousRuntimeId': str(uuid.uuid4()), 'previousContainerId': 'a' * 64,
                'newRuntimeId': self.runtime, 'newContainerId': 'b' * 64, 'evidenceSha256': 'c' * 64},
            'recoveryActions': [], 'reconciliation': None}

    def install(self, policy=None, lease=None):
        policy = policy or AdmissionPolicy.objects.latest('epoch').policy
        lease = lease or self.lease(policy)
        envelope = self.sign({'schemaVersion': 2, 'scope': B.SCOPE, 'policy': policy, 'lease': lease})
        self.permit.write_bytes(canonical(envelope))
        return envelope

    def start(self):
        self.activate(); return self.install()


class BoundedAdmissionTests(BoundedFixture):
    def test_rp003_real_operator_role_is_migrator(self):
        B._operator_role()

    def test_rp002_signed_hmac_source_caps_config_runtime_and_closed_fail_before_sql(self):
        policy = self.policy(); original = self.sign({'schemaVersion': 2, 'scope': B.SCOPE,
            'policy': policy, 'lease': self.lease(policy)})
        cases = ('hmac', 'source', 'caps', 'config', 'runtime', 'unknown', 'oversized')
        for case in cases:
            with self.subTest(case=case):
                envelope = copy.deepcopy(original); payload = envelope['payload']
                if case == 'source': payload['policy']['sourceFingerprint'] = 'f' * 64
                if case == 'caps': payload['policy']['caps']['maxOperations'] = 1001
                if case == 'config': payload['lease']['credentialConfigSha256'] = 'f' * 64
                if case == 'runtime': payload['lease']['runtimeId'] = str(uuid.uuid4())
                if case == 'unknown': payload['lease']['extra'] = True
                if case == 'oversized': payload['padding'] = 'z' * 65536
                envelope = self.sign(payload)
                if case == 'hmac': envelope['signature'] = 'f' * 64
                self.permit.write_bytes(canonical(envelope))
                with self.assertNumQueries(0), patch.object(connection, 'ensure_connection', wraps=connection.ensure_connection) as connect:
                    self.fault('BOUNDED_ADMISSION_REJECTED', lambda: self.mutate(self.prepare_body_no_query()))
                    connect.assert_not_called()

    def prepare_body_no_query(self):
        return {'operationId': str(uuid.uuid4()), 'incarnation': self.identity, 'expectedGeneration': '0',
            'writerEpoch': '1', 'kind': 'route_restriction', 'objectId': str(uuid.uuid4()), 'basis': 'a' * 64,
            'policies': [{'target': '/no-sql', 'objectId': str(uuid.uuid4()), 'policy': 'DELETED', 'redirectTarget': None}],
            'requestIds': []}

    def test_rp002_env_alone_and_wrong_cgroup_do_not_authorize(self):
        with self.assertNumQueries(0):
            self.fault('BOUNDED_ADMISSION_REJECTED', lambda: self.mutate(self.prepare_body_no_query()))
        policy = self.policy(); self.install(policy)
        with override_settings(TRUST_WRITE_PROFILE='disabled'), self.assertNumQueries(0):
            self.fault('WRITE_PROFILE_DISABLED', lambda: self.mutate(self.prepare_body_no_query()))
        with patch.object(P, 'runtime_resource_facts', side_effect=Fault('TEST_RESOURCE_FAILURE', 503)), self.assertNumQueries(0):
            self.fault('BOUNDED_ADMISSION_REJECTED', lambda: self.mutate(self.prepare_body_no_query()))

    def test_rp003_activation_is_atomic_preserves_pin_and_exact_retry(self):
        before = V.persistent_values(Head.objects.get(pk=1))
        bindings = list(Credential.objects.order_by('id').values())
        intent = self.intent(); first = self.activate(intent)
        self.assertFalse(first['replay'])
        self.assertFalse(first['workflowComplete'])
        head = Head.objects.get(pk=1); row = AdmissionPolicy.objects.get()
        self.assertEqual(head.generation, before['generation'] + 1)
        self.assertEqual(head.writer_epoch, before['writer_epoch'])
        self.assertEqual(str(head.plan_id), before['plan_id'])
        self.assertEqual(head.permitted_operations, before['permitted_operations'])
        self.assertEqual(head.permitted_recovery_actions, before['permitted_recovery_actions'])
        self.assertEqual(list(Credential.objects.order_by('id').values()), bindings)
        self.assertEqual(head.logical_bytes, before['logical_bytes'] + row.logical_bytes)
        self.assertLessEqual(row.logical_bytes, 32768)
        replay = self.activate(intent)
        self.assertTrue(replay['replay']); self.assertEqual(replay['receipt'], first['receipt'])
        self.assertEqual(Head.objects.get().generation, head.generation)
        self.assertEqual(AdmissionPolicy.objects.count(), 1)

    def test_rp003_changed_intent_and_stale_state_roll_back(self):
        intent = self.intent(); self.activate(intent)
        changed = copy.deepcopy(intent['payload']); changed['configFingerprint'] = 'e' * 64
        self.fault('ADMISSION_REPLAY_CONFLICT', lambda: self.activate(self.sign(changed)))
        revision = self.intent(self.policy(2)); revision['payload']['expected']['head']['generation'] += 1
        revision = self.sign(revision['payload'])
        before = V.persistent_values(Head.objects.get())
        self.fault('ADMISSION_STATE_CONFLICT', lambda: self.activate(revision))
        self.assertEqual(V.persistent_values(Head.objects.get()), before)
        self.assertEqual(AdmissionPolicy.objects.count(), 1)

    def test_rp003_wrong_predecessor_and_oversize_charge_roll_back(self):
        intent = self.intent(); intent['payload']['legacySeal'] = 'f' * 64
        self.fault('ADMISSION_PREDECESSOR_CONFLICT', lambda: self.activate(self.sign(intent['payload'])))
        intent = self.intent()
        with patch.object(B, 'canonical', wraps=canonical) as encode:
            original = canonical
            def inflate(value):
                if type(value) is dict and 'logical_bytes' in value and 'prior_state' in value:
                    return b'x' * 32769
                return original(value)
            encode.side_effect = inflate
            self.fault('ADMISSION_BUDGET_EXHAUSTED', lambda: self.activate(intent))
        self.assertEqual(AdmissionPolicy.objects.count(), 0)
        self.assertEqual(Head.objects.get().generation, 0)

    def test_rp003_operator_and_completed_main_evidence_gates(self):
        intent = self.intent()
        # No code-owned UNIT context: dummy hashes do not replace real reports.
        self.fault('ADMISSION_EVIDENCE_REJECTED', lambda: B.activate(intent, {}))
        with patch.object(connection, 'cursor') as cursor:
            cursor.return_value.__enter__.return_value.fetchone.return_value = ('trust_runtime', 'trust_runtime')
            self.fault('ADMISSION_OPERATOR_REQUIRED', B._operator_role)
        with override_settings(TRUST_WRITE_PROFILE='local-bounded-writer'):
            with patch.dict(connection.settings_dict, {'NAME': 'estakada_trust'}):
                self.fault('TEST_SCOPE_REJECTED', lambda: B.unit_calibration().__enter__())
        self.assertEqual(AdmissionPolicy.objects.count(), 0)

    def test_rp003_completed_evidence_reads_actual_hashes_and_closed_manifests(self):
        # Synthetic validator fixtures only: these are not completed capacity
        # evidence and are never used to activate MAIN or issue a working lease.
        policy = self.policy()
        checklists = {'unit': ['RP15-%03d' % n for n in range(1, 8)],
            'calibration': ['RP15-%03d' % n for n in range(8, 13)],
            'review': ['CODE', 'QA', 'CAPACITY']}
        reports = {kind: {'kind': kind, 'status': 'PASS',
            'sourceFingerprint': policy['sourceFingerprint'],
            'schemaFingerprint': policy['schemaFingerprint'], 'caps': copy.deepcopy(B.CAPS),
            'checks': checks} for kind, checks in checklists.items()}
        paths = {kind: Path(self.tmp.name, 'synthetic-evidence-' + kind + '.json') for kind in reports}
        for kind, path in paths.items():
            raw = canonical(reports[kind]); path.write_bytes(raw)
            policy['evidence'][kind] = hashlib.sha256(raw).hexdigest()
        self.assertFalse(B._unit_authority.get())
        with self.assertNumQueries(0):
            self.assertIsNone(B._completed_evidence(policy, paths))
        for case in ('changed-raw', 'in-progress', 'caps', 'source'):
            with self.subTest(case=case):
                candidate = copy.deepcopy(policy)
                report = copy.deepcopy(reports['unit'])
                if case == 'in-progress': report['status'] = 'IN_PROGRESS'
                if case == 'caps': report['caps']['maxOperations'] = 1001
                if case == 'source': report['sourceFingerprint'] = 'f' * 64
                raw = canonical(report)
                if case == 'changed-raw':
                    raw += b' '
                else:
                    # A signed/claimed hash matching bad content is insufficient.
                    candidate['evidence']['unit'] = hashlib.sha256(raw).hexdigest()
                paths['unit'].write_bytes(raw)
                with self.assertNumQueries(0):
                    self.fault('ADMISSION_EVIDENCE_REJECTED',
                        lambda: B._completed_evidence(candidate, paths))
        self.assertEqual(AdmissionPolicy.objects.count(), 0)

    def test_rp004_old_trial_mode_is_retired_under_head_lock(self):
        self.start()
        head = Head.objects.get()
        with override_settings(TRUST_WRITE_PROFILE='local-test-permit'), transaction.atomic():
            head = Head.objects.select_for_update().get(pk=1)
            self.fault('WRITE_TRIAL_RETIRED', lambda: P.check_locked({}, self.writer,
                self.prepare_body_no_query(), 'prepare', 'a' * 64, head))
        self.assertEqual(Head.objects.get().generation, head.generation)

    def test_rp005_new_uuid_without_trial_whitelist_and_exact_replay(self):
        self.start(); body = self.prepare_body('/new-general-id')
        self.assertNotIn(body['operationId'], Head.objects.get().permitted_operations)
        first = self.mutate(body)
        final = self.report_body(body); self.mutate(final, 'report')
        generation = Head.objects.get().generation
        replay = self.mutate(body)
        self.assertTrue(replay['replay']); self.assertEqual(replay['phaseReceipt'], first['phaseReceipt'])
        self.assertEqual(Head.objects.get().generation, generation)
        self.assertEqual(Operation.objects.count(), 1)
        self.assertEqual(Head.objects.get().permitted_operations, [])

    def test_rp005_active_binding_wrong_epoch_and_reader_role_cannot_write(self):
        self.start(); body = self.prepare_body('/roles')
        wrong = copy.deepcopy(body); wrong['writerEpoch'] = '2'
        self.fault('WRITER_FENCED', lambda: self.mutate(wrong))
        self.fault('WRITE_PERMIT_SCOPE_REJECTED', lambda: S.mutate(self.reader, body, 'prepare'))
        Credential.objects.filter(pk='writer').update(active=False)
        self.fault('CREDENTIAL_REVOKED', lambda: self.mutate(body))
        self.assertEqual(Operation.objects.count(), 0)

    def test_rp005_full_count_allows_existing_replay_and_completion_but_no_prepare(self):
        self.start(); body = self.prepare_body('/count-boundary')
        first = self.mutate(body)
        # Isolated count injection, not a capacity corpus PASS.
        with patch.object(Operation.objects, 'count', return_value=1000):
            self.assertTrue(self.mutate(body)['replay'])
            final = self.report_body(body); self.mutate(final, 'report')
            self.assertEqual(self.mutate(body)['phaseReceipt'], first['phaseReceipt'])
            self.fault('COUNT_CAP_REACHED', lambda: self.mutate(self.prepare_body('/one-too-many')))
        self.assertEqual(Operation.objects.count(), 1)

    def test_rp010_combined_budget_preserves_existing_completion_and_replays(self):
        self.start(); body = self.prepare_body('/reserved-completion')
        first = self.mutate(body)
        head = Head.objects.get()
        # Controlled accounting injection, not a full capacity/physical PASS.
        # Keep combined usage valid and leave only 512 unreserved bytes.
        injected_logical = B.CAPS['logicalBytes'] - head.reserved_bytes - 512
        Head.objects.filter(pk=1).update(logical_bytes=injected_logical)
        head = Head.objects.get(); combined = head.logical_bytes + head.reserved_bytes
        self.assertEqual(combined, B.CAPS['logicalBytes'] - 512)
        other = self.prepare_body('/cannot-spend-completion-reserve')
        size = len(canonical(other)) + 4096
        reserve = len(canonical(other['policies'])) + 8192
        self.assertLessEqual(head.logical_bytes + size, B.CAPS['logicalBytes'])
        self.assertGreater(combined + size + reserve, B.CAPS['logicalBytes'])
        before = V.persistent_values(head)
        self.fault('BUDGET_EXHAUSTED', lambda: self.mutate(other))
        self.assertEqual(V.persistent_values(Head.objects.get()), before)
        self.assertTrue(self.mutate(body)['replay'])
        unknown = self.report_body(body, 'unknown'); self.mutate(unknown, 'report')
        final = self.report_body(body); self.mutate(final, 'report')
        self.assertTrue(self.mutate(final, 'report')['replay'])
        self.assertTrue(self.mutate(unknown, 'report')['replay'])
        self.assertEqual(self.mutate(body)['phaseReceipt'], first['phaseReceipt'])
        head = Head.objects.get()
        self.assertEqual(head.reserved_bytes, 0)
        self.assertEqual(head.logical_bytes + head.reserved_bytes, combined)
        self.assertEqual(Operation.objects.count(), 1)

    def test_rp010_policy_charge_cannot_consume_reserved_completion_budget(self):
        self.start(); body = self.prepare_body('/reserved-policy-charge')
        body['policies'] = [{'target': '/reserved-policy/' + str(index) + '/' + 'x' * 1900,
            'objectId': str(uuid.uuid4()), 'policy': 'DELETED', 'redirectTarget': None}
            for index in range(16)]
        self.mutate(body)
        head = Head.objects.get()
        Head.objects.filter(pk=1).update(
            logical_bytes=B.CAPS['logicalBytes'] - head.reserved_bytes - 512)
        before = V.persistent_values(Head.objects.get())
        self.assertLessEqual(before['logical_bytes'] + B.CAPS['maxPolicyRowBytes'],
            B.CAPS['logicalBytes'])
        revision = self.intent(self.policy(2))
        self.fault('ADMISSION_BUDGET_EXHAUSTED', lambda: self.activate(revision))
        self.assertEqual(V.persistent_values(Head.objects.get()), before)
        self.assertEqual(AdmissionPolicy.objects.count(), 1)
        self.assertTrue(self.mutate(body)['replay'])
        self.mutate(self.report_body(body), 'report')
        head = Head.objects.get()
        self.assertEqual(head.logical_bytes, B.CAPS['logicalBytes'] - 512)
        self.assertEqual(head.reserved_bytes, 0)

    def test_rp010_fence_cannot_consume_full_combined_completion_budget(self):
        envelope = self.start(); body = self.prepare_body('/deny-survives-fence-budget-refusal')
        self.mutate(body)
        head = Head.objects.get()
        # Isolated accounting boundary, not a full capacity corpus PASS.
        Head.objects.filter(pk=1).update(
            logical_bytes=B.CAPS['logicalBytes'] - head.reserved_bytes)
        head = Head.objects.get()
        self.assertEqual(head.logical_bytes + head.reserved_bytes, B.CAPS['logicalBytes'])
        fence = {'actionId': str(uuid.uuid4()), 'incarnation': self.identity,
            'expectedGeneration': str(head.generation), 'writerEpoch': str(head.writer_epoch),
            'scope': B.SCOPE, 'previousCredentialId': 'writer', 'newCredentialId': None,
            'fenceActionId': None, 'reconciliationDigest': None}
        lease = envelope['payload']['lease']
        lease['recoveryActions'] = [{'id': fence['actionId'], 'credentialId': 'recovery',
            'writerEpoch': fence['writerEpoch'], 'phase': 'fence',
            'fingerprint': S.semantic(fence, self.recovery_actor)}]
        self.install(lease=lease)
        before_head = V.persistent_values(head)
        before_credentials = list(Credential.objects.order_by('id').values())
        before_deny = list(RoutePolicy.objects.order_by('key').values())
        before_operation = Operation.objects.values().get(pk=body['operationId'])
        self.fault('BUDGET_EXHAUSTED', lambda: R.mutate(self.recovery_actor, fence, 'fence'))
        self.assertEqual(V.persistent_values(Head.objects.get()), before_head)
        self.assertEqual(list(Credential.objects.order_by('id').values()), before_credentials)
        self.assertEqual(list(RoutePolicy.objects.order_by('key').values()), before_deny)
        self.assertEqual(Operation.objects.values().get(pk=body['operationId']), before_operation)
        self.assertEqual(RecoveryReceipt.objects.count(), 0)
        self.assertTrue(self.mutate(body)['replay'])
        final = self.report_body(body); self.mutate(final, 'report')
        self.assertTrue(self.mutate(final, 'report')['replay'])
        head = Head.objects.get()
        self.assertEqual(head.mode, 'ACTIVE')
        self.assertEqual(head.reserved_bytes, 0)
        self.assertEqual(head.logical_bytes, B.CAPS['logicalBytes'])
        self.assertEqual(RecoveryReceipt.objects.count(), 0)

    def test_rp009_quoted_256_redirects_over_wire_limit_reject_before_sql(self):
        self.start()
        body = self.prepare_body_no_query()
        policies = []
        for index in range(256):
            prefix = '/quoted-target/' + str(index) + '/'
            redirect_prefix = '/quoted-redirect/' + str(index) + '/'
            exact = prefix + '"' * (2048 - len(prefix.encode('utf-8')))
            redirect = redirect_prefix + '"' * (2048 - len(redirect_prefix.encode('utf-8')))
            self.assertEqual(len(exact.encode('utf-8')), 2048)
            self.assertEqual(len(redirect.encode('utf-8')), 2048)
            self.assertEqual(target(exact), exact)
            self.assertEqual(target(redirect), redirect)
            policies.append({'target': exact, 'objectId': str(uuid.uuid4()),
                'policy': 'REDIRECT', 'redirectTarget': redirect})
        body['policies'] = policies
        validate(body, 'prepare')
        self.assertGreater(len(canonical(body)), MAX_BODY)
        with self.assertNumQueries(0), patch.object(connection, 'ensure_connection', wraps=connection.ensure_connection) as connect:
            self.fault('BODY_TOO_LARGE', lambda: self.mutate(body))
            connect.assert_not_called()

    def test_rp002_unit_context_checks_actual_database_on_enter_and_evidence_bypass(self):
        with patch.dict('os.environ', {'TRUST_TEST_EXECUTION': '0'}), self.assertNumQueries(0):
            self.fault('TEST_SCOPE_REJECTED', lambda: B.unit_calibration().__enter__())
        with patch.dict(connection.settings_dict, {'NAME': 'estakada_trust'}), self.assertNumQueries(0):
            self.fault('TEST_SCOPE_REJECTED', lambda: B.unit_calibration().__enter__())
        with patch.object(connection, 'cursor') as cursor:
            sql = cursor.return_value.__enter__.return_value
            sql.fetchone.return_value = ('estakada_trust',)
            self.fault('TEST_SCOPE_REJECTED', lambda: B.unit_calibration().__enter__())
            sql.execute.assert_called_once_with('SELECT current_database()')
        with B.unit_calibration():
            # A connection change after entering must be rejected again.
            with patch.object(connection, 'cursor') as cursor:
                sql = cursor.return_value.__enter__.return_value
                sql.fetchone.return_value = ('estakada_trust',)
                self.fault('TEST_SCOPE_REJECTED', lambda: B._completed_evidence({}, {}))
                sql.execute.assert_called_once_with('SELECT current_database()')

    def test_rp002_under_lock_reread_and_schema_change_close(self):
        envelope = self.start(); body = self.prepare_body('/changed-file'); fp = S.semantic(body, self.writer)
        checked = B.check(self.writer, body, 'prepare', fp)
        envelope['payload']['lease']['deployment']['evidence'] = 'f' * 64
        self.permit.write_bytes(canonical(self.sign(envelope['payload'])))
        with transaction.atomic():
            head = S.locked(self.writer, self.identity, '1')
            self.fault('WRITE_PERMIT_CHANGED', lambda: B.check_locked(checked, self.writer, body, 'prepare', fp, head))
        self.install()
        with patch.object(P, 'schema_fingerprint', return_value='f' * 64):
            self.fault('ADMISSION_POLICY_MISMATCH', lambda: self.mutate(body))
        self.assertEqual(Operation.objects.count(), 0)

    def test_rp006_lease_restart_no_new_policy_and_latest_revision_authoritative(self):
        old = self.start(); first_head = Head.objects.get().generation
        self.runtime = str(uuid.uuid4())
        with override_settings(TRUST_RUNTIME_ID=self.runtime):
            self.install()
            body = self.prepare_body('/restart'); self.mutate(body)
        self.assertEqual(AdmissionPolicy.objects.count(), 1)
        self.assertEqual(Head.objects.get().generation, first_head + 1)
        self.activate(self.intent(self.policy(2)))
        self.permit.write_bytes(canonical(old))
        # Restore old runtime to give the stale lease its best chance.
        with override_settings(TRUST_RUNTIME_ID=old['payload']['lease']['runtimeId']):
            self.fault('ADMISSION_POLICY_MISMATCH', lambda: self.mutate(self.prepare_body('/stale-policy')))
        self.assertEqual(AdmissionPolicy.objects.count(), 2)

    def test_rp006_sixteen_revisions_keep_history_and_refuse_seventeenth(self):
        for epoch in range(1, 17):
            self.activate(self.intent(self.policy(epoch)))
        before = V.persistent_values(Head.objects.get())
        self.fault('ADMISSION_INTENT_REJECTED', lambda: self.activate(self.intent(self.policy(17))))
        self.assertEqual(AdmissionPolicy.objects.count(), 16)
        self.assertEqual(V.persistent_values(Head.objects.get()), before)

    def test_rp007_recovery_requires_exact_descriptor_and_v2_proof(self):
        envelope = self.start()
        body = {'actionId': str(uuid.uuid4()), 'incarnation': self.identity,
            'expectedGeneration': str(Head.objects.get().generation), 'writerEpoch': '1',
            'scope': B.SCOPE, 'previousCredentialId': 'writer', 'newCredentialId': None,
            'fenceActionId': None, 'reconciliationDigest': None}
        self.fault('WRITE_PERMIT_SCOPE_REJECTED', lambda: R.mutate(self.recovery_actor, body, 'fence'))
        lease = envelope['payload']['lease']
        lease['recoveryActions'] = [{'id': body['actionId'], 'credentialId': 'recovery',
            'writerEpoch': '1', 'phase': 'fence', 'fingerprint': S.semantic(body, self.recovery_actor)}]
        self.install(lease=lease)
        result = R.mutate(self.recovery_actor, body, 'fence')
        self.assertEqual(Head.objects.get().mode, 'FROZEN')
        self.assertEqual(result['recoveryReceipt']['scope'], B.SCOPE)
        self.assertEqual(RecoveryReceipt.objects.count(), 1)
        generation = Head.objects.get().generation
        self.assertTrue(R.mutate(self.recovery_actor, body, 'fence')['replay'])
        self.assertEqual(Head.objects.get().generation, generation)
        self.fault('CREDENTIAL_REVOKED', lambda: self.mutate(self.prepare_body('/revoked')))
        proof = {'fenceActionId': body['actionId'], 'fenceReceiptDigest': digest(result['recoveryReceipt']),
            'head': S.head_dict(Head.objects.get()), 'stateDigestVersion': 1,
            'stateDigest': 'a' * 64, 'runtimeId': self.runtime,
            'credentialConfigSha256': B._configuration_sha(), 'exclusion': lease['exclusion']}
        lease['reconciliation'] = proof; self.install(lease=lease)
        with self.assertNumQueries(0):
            self.fault('BOUNDED_ADMISSION_REJECTED', B.read_envelope)

    def test_rp007_real_v2_recovery_activation_and_old_secret_with_new_epoch(self):
        envelope = self.start()
        fence = {'actionId': str(uuid.uuid4()), 'incarnation': self.identity,
            'expectedGeneration': str(Head.objects.get().generation), 'writerEpoch': '1',
            'scope': B.SCOPE, 'previousCredentialId': 'writer', 'newCredentialId': None,
            'fenceActionId': None, 'reconciliationDigest': None}
        lease = envelope['payload']['lease']
        lease['recoveryActions'] = [{'id': fence['actionId'], 'credentialId': 'recovery',
            'writerEpoch': '1', 'phase': 'fence', 'fingerprint': S.semantic(fence, self.recovery_actor)}]
        self.install(lease=lease)
        fenced = R.mutate(self.recovery_actor, fence, 'fence')
        previous_runtime = self.runtime
        self.runtime = str(uuid.uuid4())
        self.items.append({'id': 'writer2', 'principal': 'new-machine', 'role': 'writer', 'secret': '4' * 64})
        Path(self.tmp.name, 'keys').write_bytes(canonical({'schemaVersion': 1, 'credentials': self.items}))
        with override_settings(TRUST_RUNTIME_ID=self.runtime):
            with transaction.atomic():
                head = Head.objects.select_for_update().get(pk=1)
                state = V.state_digest(head)
            lease = self.lease(envelope['payload']['policy'])
            lease['exclusion']['previousRuntimeId'] = previous_runtime
            proof = {'fenceActionId': fence['actionId'], 'fenceReceiptDigest': digest(fenced['recoveryReceipt']),
                'head': S.head_dict(head), 'stateDigestVersion': 2, 'stateDigest': state,
                'runtimeId': self.runtime, 'credentialConfigSha256': B._configuration_sha(),
                'exclusion': lease['exclusion']}
            activate = {'actionId': str(uuid.uuid4()), 'incarnation': self.identity,
                'expectedGeneration': str(head.generation), 'writerEpoch': str(head.writer_epoch),
                'scope': B.SCOPE, 'previousCredentialId': 'writer', 'newCredentialId': 'writer2',
                'fenceActionId': fence['actionId'], 'reconciliationDigest': state}
            lease['reconciliation'] = proof
            lease['recoveryActions'] = [{'id': activate['actionId'], 'credentialId': 'recovery',
                'writerEpoch': activate['writerEpoch'], 'phase': 'activate',
                'fingerprint': S.semantic(activate, self.recovery_actor)}]
            self.install(lease=lease)
            result = R.mutate(self.recovery_actor, activate, 'activate')
            self.assertEqual(Head.objects.get().mode, 'ACTIVE')
            self.assertFalse(result['replay'])
            generation = Head.objects.get().generation
            self.assertTrue(R.mutate(self.recovery_actor, activate, 'activate')['replay'])
            self.assertEqual(Head.objects.get().generation, generation)
            old_body = self.prepare_body('/old-secret-fresh-epoch'); old_body['writerEpoch'] = '2'
            self.fault('CREDENTIAL_REVOKED', lambda: self.mutate(old_body))
            fresh = auth.authenticate('Bearer writer2:' + '4' * 64, 'writer')
            new_body = self.prepare_body('/new-secret'); new_body['writerEpoch'] = '2'
            S.mutate(fresh, new_body, 'prepare')
            self.assertEqual(Operation.objects.count(), 1)
            self.assertEqual(RecoveryReceipt.objects.count(), 2)
            self.assertEqual(AdmissionPolicy.objects.count(), 1)
