"""WP unit/real PostgreSQL evidence. Runtime TLS/crash/exclusion is external."""
import copy
import hashlib
import hmac
import json
import uuid
from pathlib import Path
from unittest.mock import patch
from django.db import connection, transaction, DatabaseError
from django.test import override_settings
from . import auth, profile as P, recovery as R, services as S
from .models import Head, Credential, Operation, RoutePolicy, RequestTombstone, RecoveryReceipt
from .protocol import canonical, digest, Fault
from .tests import JournalFixture

class WriteProfileTests(JournalFixture):
    def setUp(self):
        super().setUp()
        token=S._test_mode.set(False); self.addCleanup(S._test_mode.reset,token)
        self.runtime=str(uuid.uuid4()); self.plan=str(uuid.uuid4())
        self.permit_path=Path(self.tmp.name,'permit')
        self.profile_settings=override_settings(TRUST_WRITE_PROFILE='local-test-permit',
            TRUST_WRITE_PERMIT_FILE=str(self.permit_path),TRUST_RUNTIME_ID=self.runtime)
        self.profile_settings.enable(); self.addCleanup(lambda:self.profile_settings.disable())
        self.operation_ids=[str(uuid.uuid4()) for _ in range(16)]
        self.action_ids=[str(uuid.uuid4()) for _ in range(4)]
        self.body=self.prepare_body(); self.body['operationId']=self.operation_ids[0]
        self.committed=self.report_body(self.body); self.committed['expectedGeneration']='1'
        self.unknown=self.report_body(self.body,'unknown'); self.unknown['expectedGeneration']='1'
        self.aborted=self.report_body(self.body,'aborted'); self.aborted['expectedGeneration']='1'
        self.recovery_actor=auth.authenticate('Bearer recovery:'+'3'*64,'recovery')
        self.requests=[self.request(self.body,'prepare'),self.request(self.committed,'committed'),
            self.request(self.unknown,'unknown'),self.request(self.aborted,'aborted')]
        self.install()

    def request(self,body,phase,actor=None):
        actor=actor or self.writer
        return {'id':body.get('operationId',body.get('actionId')),'credentialId':actor['id'],
            'writerEpoch':body['writerEpoch'],'phase':phase,'fingerprint':S.semantic(body,actor)}
    def payload(self,reconciliation=None):
        rows=P.source_files()
        return {'schemaVersion':1,'scope':'LOCAL_TRUST_TEST_ONLY','planId':self.plan,
            'dbName':connection.settings_dict['NAME'],'incarnation':self.identity,'protocolVersion':1,
            'sourceFiles':rows,'sourceFingerprint':digest(rows),'schemaFingerprint':P.schema_fingerprint(),
            'evidence':{'unit':'a'*64,'calibration':'b'*64,'review':'c'*64},'caps':copy.deepcopy(P.CAPS),
            'deployment':{**copy.deepcopy(P.DEPLOYMENT),'configFingerprint':'a'*64,'evidence':'b'*64},
            'operationIds':self.operation_ids[:],'recoveryActionIds':self.action_ids[:],
            'requests':copy.deepcopy(self.requests),'runtimeId':self.runtime,
            'credentialConfigSha256':hashlib.sha256(Path(self.tmp.name,'keys').read_bytes()).hexdigest(),
            'reconciliation':reconciliation}
    def sign(self,payload):
        envelope={'payload':payload,'signature':hmac.new(bytes.fromhex('3'*64),canonical(payload),hashlib.sha256).hexdigest()}
        self.permit_path.write_bytes(canonical(envelope))
        return envelope
    def install(self,reconciliation=None): return self.sign(self.payload(reconciliation))
    def post(self,path,body,role='writer',secret='2'):
        return self.client.post(path,data=canonical(body),content_type='application/json',HTTP_AUTHORIZATION='Bearer '+role+':'+secret*64)
    def fence_body(self):
        return {'actionId':self.action_ids[0],'incarnation':self.identity,'expectedGeneration':str(Head.objects.get().generation),
            'writerEpoch':'1','scope':'LOCAL_TRUST_TEST_ONLY','previousCredentialId':'writer',
            'newCredentialId':None,'fenceActionId':None,'reconciliationDigest':None}
    def fence(self):
        body=self.fence_body(); self.requests.append(self.request(body,'fence',self.recovery_actor)); self.install()
        result=R.mutate(self.recovery_actor,body,'fence')
        return body,result
    def activation(self):
        fence_body,result=self.fence()
        self.items.append({'id':'writer2','principal':'new-machine','role':'writer','secret':'4'*64})
        Path(self.tmp.name,'keys').write_bytes(canonical({'schemaVersion':1,'credentials':self.items}))
        previous_runtime=self.runtime
        self.runtime=str(uuid.uuid4()); self.profile_settings.disable()
        self.profile_settings=override_settings(TRUST_WRITE_PROFILE='local-test-permit',TRUST_WRITE_PERMIT_FILE=str(self.permit_path),TRUST_RUNTIME_ID=self.runtime)
        self.profile_settings.enable()
        head=Head.objects.get(); state=R.state_digest(head)
        proof={'fenceActionId':fence_body['actionId'],'fenceReceiptDigest':R.receipt_digest(result['recoveryReceipt']),
            'head':S.head_dict(head),'stateDigest':state,'runtimeId':self.runtime,
            'credentialConfigSha256':hashlib.sha256(Path(self.tmp.name,'keys').read_bytes()).hexdigest(),
            'exclusion':{'previousRuntimeId':previous_runtime,'previousContainerId':'a'*64,
                'newRuntimeId':self.runtime,'newContainerId':'b'*64,'evidenceSha256':'c'*64}}
        body={'actionId':self.action_ids[1],'incarnation':self.identity,'expectedGeneration':str(head.generation),
            'writerEpoch':str(head.writer_epoch),'scope':'LOCAL_TRUST_TEST_ONLY','previousCredentialId':'writer',
            'newCredentialId':'writer2','fenceActionId':fence_body['actionId'],'reconciliationDigest':state}
        self.requests.append(self.request(body,'activate',self.recovery_actor)); self.install(proof)
        return body,proof

    def test_wp002_disabled_env_cannot_enable(self):
        with override_settings(TRUST_WRITE_PROFILE='disabled'):
            with self.assertNumQueries(0),patch.object(connection,'ensure_connection',wraps=connection.ensure_connection) as spy:
                self.fault('WRITE_PROFILE_DISABLED',lambda:self.mutate(self.body)); spy.assert_not_called()

    def test_wp002_absent_permit_no_sql_or_connect(self):
        self.permit_path.unlink()
        with self.assertNumQueries(0),patch.object(connection,'ensure_connection',wraps=connection.ensure_connection) as spy:
            self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body)); spy.assert_not_called()

    def test_wp002_signature_failure_no_sql_or_connect(self):
        envelope=self.install(); envelope['signature']='d'*64; self.permit_path.write_bytes(canonical(envelope))
        with self.assertNumQueries(0),patch.object(connection,'ensure_connection',wraps=connection.ensure_connection) as spy:
            self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body)); spy.assert_not_called()

    def test_wp002_source_manifest_drift_with_valid_signature(self):
        payload=self.payload(); payload['sourceFiles'][0]['sha256']='e'*64; payload['sourceFingerprint']=digest(payload['sourceFiles']); self.sign(payload)
        with self.assertNumQueries(0): self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body))

    def test_wp002_wrong_database_with_valid_signature(self):
        payload=self.payload(); payload['dbName']='foreign'; self.sign(payload)
        with self.assertNumQueries(0): self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body))

    def test_wp002_wrong_identity_with_valid_signature(self):
        payload=self.payload(); payload['incarnation']=str(uuid.uuid4()); self.sign(payload)
        with self.assertNumQueries(0): self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body))

    def test_wp002_caps_cannot_be_enlarged(self):
        payload=self.payload(); payload['caps']['maxOperations']=17; self.sign(payload)
        with self.assertNumQueries(0): self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body))

    def test_wp002_evidence_missing_refuses(self):
        payload=self.payload(); del payload['evidence']['review']; self.sign(payload)
        with self.assertNumQueries(0): self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body))

    def test_wp002_schema_mismatch_rolls_back_first_plan(self):
        payload=self.payload(); payload['schemaFingerprint']='d'*64; self.sign(payload)
        self.fault('PERMIT_SCHEMA_MISMATCH',lambda:self.mutate(self.body))
        self.assertIsNone(Head.objects.get().plan_id); self.assertFalse(Operation.objects.exists())

    def test_wp003_real_http_write_and_exact_stale_cas_replay(self):
        first=self.post('/v1/prepare',self.body); self.assertEqual(first.status_code,200)
        repeat=self.post('/v1/prepare',self.body); self.assertEqual(repeat.status_code,200)
        self.assertTrue(repeat.json()['replay']); self.assertEqual(Head.objects.get().generation,1)
        self.assertEqual(Operation.objects.count(),1); self.assertFalse(first.json()['workflowComplete'])

    def test_wp003_unknown_id_refuses_before_sql(self):
        body=copy.deepcopy(self.body); body['operationId']=str(uuid.uuid4())
        with self.assertNumQueries(0): self.fault('WRITE_PERMIT_SCOPE_REJECTED',lambda:self.mutate(body))

    def test_wp003_body_change_refuses_before_sql(self):
        body=copy.deepcopy(self.body); body['policies'][0]['target']='/changed'
        with self.assertNumQueries(0): self.fault('WRITE_PERMIT_SCOPE_REJECTED',lambda:self.mutate(body))

    def test_wp003_unknown_and_terminal_keep_reserve_receipts(self):
        self.mutate(self.body); self.mutate(self.unknown,'report')
        final=copy.deepcopy(self.committed); final['expectedGeneration']='2'
        result=self.mutate(final,'report')
        self.assertEqual(result['stage'],'FINAL_RESTRICTION'); self.assertEqual(Head.objects.get().reserved_bytes,0)
        self.assertEqual(self.mutate(self.unknown,'report')['stage'],'FINAL_RESTRICTION')

    def test_wp007_fence_replay_uses_saved_receipt_before_old_epoch_cas(self):
        body,result=self.fence(); self.assertEqual(Head.objects.get().writer_epoch,2)
        replay=R.mutate(self.recovery_actor,body,'fence')
        self.assertTrue(replay['replay']); self.assertEqual(result['recoveryReceipt'],replay['recoveryReceipt'])
        self.assertEqual(RecoveryReceipt.objects.count(),1); self.assertEqual(Head.objects.get().generation,1)

    def test_wp007_old_key_fresh_epoch_reaches_authoritative_revocation(self):
        self.fence(); candidate=copy.deepcopy(self.body); candidate['writerEpoch']='2'
        self.requests.append(self.request(candidate,'prepare')); self.install()
        self.fault('CREDENTIAL_REVOKED',lambda:self.mutate(candidate))
        self.assertEqual(Head.objects.get().generation,1); self.assertEqual(Operation.objects.count(),0)

    def test_wp008_missing_proof_passes_permit_but_stays_frozen(self):
        body,proof=self.activation(); self.install(None)
        self.fault('RECOVERY_PRECONDITION_FAILED',lambda:R.mutate(self.recovery_actor,body,'activate'))
        self.assertEqual(Head.objects.get().mode,'FROZEN'); self.assertFalse(Credential.objects.filter(pk='writer2').exists())

    def test_wp008_bad_actual_proof_passes_whitelist_and_stays_frozen(self):
        body,proof=self.activation(); proof['stateDigest']='e'*64; self.install(proof)
        self.fault('RECOVERY_PRECONDITION_FAILED',lambda:R.mutate(self.recovery_actor,body,'activate'))
        self.assertEqual(Head.objects.get().mode,'FROZEN'); self.assertEqual(RecoveryReceipt.objects.count(),1)

    def test_wp009_new_key_activates_and_old_key_remains_revoked(self):
        body,proof=self.activation(); result=R.mutate(self.recovery_actor,body,'activate')
        self.assertEqual(result['head']['mode'],'ACTIVE'); self.assertEqual(result['head']['writerEpoch'],'2')
        writer2=auth.authenticate('Bearer writer2:'+'4'*64,'writer')
        candidate=copy.deepcopy(self.body); candidate.update(writerEpoch='2',expectedGeneration='2')
        self.requests.append(self.request(candidate,'prepare',writer2)); self.install(proof)
        saved=S.mutate(writer2,candidate,'prepare'); self.assertEqual(saved['head']['generation'],'3')
        self.assertFalse(Credential.objects.get(pk='writer').active)
        self.assertFalse(result['workflowComplete'])

    def test_wp009_activation_replay_no_second_credential_or_generation(self):
        body,proof=self.activation(); first=R.mutate(self.recovery_actor,body,'activate')
        replay=R.mutate(self.recovery_actor,body,'activate')
        self.assertTrue(replay['replay']); self.assertEqual(first['recoveryReceipt'],replay['recoveryReceipt'])
        self.assertEqual(Credential.objects.filter(pk='writer2').count(),1)
        self.assertEqual(Head.objects.get().generation,2)

    def test_wp010_recovery_does_not_remove_pending_or_tombstone(self):
        self.mutate(self.body)
        tomb=self.prepare_body(); tomb.update(operationId=self.operation_ids[1],kind='request_tombstone',policies=[],requestIds=[str(uuid.uuid4())])
        self.requests.append(self.request(tomb,'prepare')); self.install(); self.mutate(tomb)
        before=list(Operation.objects.order_by('id').values())
        routes=list(RoutePolicy.objects.values()); tombs=list(RequestTombstone.objects.values())
        body,proof=self.activation(); R.mutate(self.recovery_actor,body,'activate')
        self.assertEqual(list(Operation.objects.order_by('id').values()),before)
        self.assertEqual(list(RoutePolicy.objects.values()),routes); self.assertEqual(list(RequestTombstone.objects.values()),tombs)

    def test_wp011_receipt_is_physically_accounted_and_db_immutable(self):
        self.fence(); receipt=RecoveryReceipt.objects.get()
        self.assertLessEqual(receipt.logical_bytes,16384); self.assertEqual(Head.objects.get().logical_bytes,receipt.logical_bytes)
        self.assertIn('journal_recoveryreceipt',S.physical_facts()['relations'])
        with self.assertRaises(DatabaseError),transaction.atomic(): RecoveryReceipt.objects.filter(pk=receipt.pk).update(action='activate')

    def test_wp012_runtime_id_drift_closes_before_sql(self):
        with override_settings(TRUST_RUNTIME_ID=str(uuid.uuid4())),self.assertNumQueries(0):
            self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body))

    def test_wp012_credential_configuration_drift_closes_before_sql(self):
        self.items.append({'id':'other','principal':'other','role':'reader','secret':'5'*64})
        Path(self.tmp.name,'keys').write_bytes(canonical({'schemaVersion':1,'credentials':self.items}))
        with self.assertNumQueries(0): self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body))

    def test_wp012_rotation_cannot_expand_fixed_plan(self):
        self.mutate(self.body); self.operation_ids[15]=str(uuid.uuid4()); self.install()
        self.fault('PERMIT_PLAN_MISMATCH',lambda:self.mutate(self.body))
        self.assertEqual(Operation.objects.count(),1)

    def test_wp002_oversized_operation_plan_cannot_be_signed_into_scope(self):
        self.operation_ids.append(str(uuid.uuid4())); self.install()
        with self.assertNumQueries(0): self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body))

    def test_wp002_oversized_recovery_plan_cannot_be_signed_into_scope(self):
        self.action_ids.append(str(uuid.uuid4())); self.install()
        with self.assertNumQueries(0): self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body))

    def test_wp007_writer_cannot_use_recovery_endpoint(self):
        body=self.fence_body(); self.requests.append(self.request(body,'fence',self.recovery_actor)); self.install()
        with self.assertNumQueries(0):
            response=self.post('/v1/recovery/fence',body)
            self.assertEqual(response.status_code,401)
        self.assertEqual(Head.objects.get().writer_epoch,1)

    def test_wp007_altered_allowed_recovery_fingerprint_cannot_rewrite_receipt(self):
        body,result=self.fence(); changed=copy.deepcopy(body); changed['previousCredentialId']='another-writer'
        self.requests.append(self.request(changed,'fence',self.recovery_actor)); self.install()
        self.fault('RECOVERY_REPLAY_CONFLICT',lambda:R.mutate(self.recovery_actor,changed,'fence'))
        self.assertEqual(RecoveryReceipt.objects.count(),1); self.assertEqual(Head.objects.get().writer_epoch,2)

    def test_wp008_activation_without_new_runtime_reaches_precondition(self):
        body,proof=self.activation()
        fence=RecoveryReceipt.objects.get(action='fence')
        self.runtime=fence.receipt['runtimeId']
        with override_settings(TRUST_RUNTIME_ID=self.runtime):
            proof['runtimeId']=self.runtime
            proof['exclusion']['newRuntimeId']=self.runtime
            proof['exclusion']['previousRuntimeId']=str(uuid.uuid4())
            self.install(proof)
            self.fault('RECOVERY_PRECONDITION_FAILED',lambda:R.mutate(self.recovery_actor,body,'activate'))
        self.assertEqual(Head.objects.get().mode,'FROZEN')

    def test_wp008_new_credential_cannot_reuse_old_secret(self):
        body,proof=self.activation()
        self.items[-1]['secret']='2'*64
        Path(self.tmp.name,'keys').write_bytes(canonical({'schemaVersion':1,'credentials':self.items}))
        proof['credentialConfigSha256']=hashlib.sha256(Path(self.tmp.name,'keys').read_bytes()).hexdigest()
        self.install(proof)
        self.fault('RECOVERY_PRECONDITION_FAILED',lambda:R.mutate(self.recovery_actor,body,'activate'))
        self.assertEqual(Head.objects.get().mode,'FROZEN')

    def test_wp008_budget_corruption_changes_full_digest_and_rejects_old_proof(self):
        body,proof=self.activation(); before=R.state_digest(Head.objects.get())
        Head.objects.filter(pk=1).update(logical_bytes=Head.objects.get().logical_bytes+1,reserved_bytes=1)
        self.assertNotEqual(R.state_digest(Head.objects.get()),before)
        self.fault('RECOVERY_PRECONDITION_FAILED',lambda:R.mutate(self.recovery_actor,body,'activate'))
        self.assertEqual(Head.objects.get().mode,'FROZEN')

    def test_wp008_inactive_credential_mutation_changes_full_digest_and_rejects_proof(self):
        body,proof=self.activation(); before=R.state_digest(Head.objects.get())
        Credential.objects.filter(pk='writer').update(principal='changed-old-principal',verifier='f'*64)
        self.assertNotEqual(R.state_digest(Head.objects.get()),before)
        self.fault('RECOVERY_PRECONDITION_FAILED',lambda:R.mutate(self.recovery_actor,body,'activate'))
        self.assertEqual(Head.objects.get().mode,'FROZEN')

    def test_wp008_foreign_active_writer_refused_even_with_current_signed_proof(self):
        body,proof=self.activation()
        Credential.objects.create(id='foreign-writer',principal='foreign',role='writer',verifier='f'*64,writer_epoch=2,active=True)
        state=R.state_digest(Head.objects.get()); body['reconciliationDigest']=state; proof['stateDigest']=state
        self.requests.append(self.request(body,'activate',self.recovery_actor)); self.install(proof)
        self.fault('RECOVERY_PRECONDITION_FAILED',lambda:R.mutate(self.recovery_actor,body,'activate'))
        self.assertEqual(Head.objects.get().mode,'FROZEN'); self.assertFalse(Credential.objects.filter(pk='writer2').exists())

    def cgroup_fixture(self,memory='268435456',cpu='50000 100000',pids='64'):
        root=Path(self.tmp.name,'cgroup'); root.mkdir(exist_ok=True)
        for name,value in (('memory.max',memory),('cpu.max',cpu),('pids.max',pids)):
            (root/name).write_text(value,encoding='ascii')
        return root

    def test_wp002_cgroup_reader_exact_integer_ratio(self):
        root=self.cgroup_fixture(cpu='100000 200000')
        with patch.object(P,'CGROUP_ROOT',root):
            self.assertEqual(P.runtime_resource_facts(),{'memoryBytes':268435456,'nanoCpus':500000000,'pids':64})

    def test_wp002_actual_cgroup_memory_mismatch_prevents_sql(self):
        root=self.cgroup_fixture(memory='536870912')
        with patch.object(P,'CGROUP_ROOT',root),self.assertNumQueries(0):
            self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body))

    def test_wp002_actual_cgroup_unlimited_cpu_refused(self):
        root=self.cgroup_fixture(cpu='max 100000')
        with patch.object(P,'CGROUP_ROOT',root):
            self.fault('WRITE_PROFILE_RESOURCE_MISMATCH',P.runtime_resource_facts)

    def test_wp002_actual_cgroup_wrong_cpu_ratio_refused(self):
        root=self.cgroup_fixture(cpu='25000 100000')
        with patch.object(P,'CGROUP_ROOT',root):
            self.fault('WRITE_PROFILE_RESOURCE_MISMATCH',P.runtime_resource_facts)

    def test_wp002_actual_cgroup_wrong_pids_refused(self):
        root=self.cgroup_fixture(pids='128')
        with patch.object(P,'CGROUP_ROOT',root):
            self.fault('WRITE_PROFILE_RESOURCE_MISMATCH',P.runtime_resource_facts)

    def test_wp002_signed_db_deployment_caps_drift_refused(self):
        payload=self.payload(); payload['deployment']['db']['pids']=129; self.sign(payload)
        with self.assertNumQueries(0): self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body))

    def test_wp002_signed_deployment_missing_config_evidence_refused(self):
        payload=self.payload(); del payload['deployment']['configFingerprint']; self.sign(payload)
        with self.assertNumQueries(0): self.fault('WRITE_PERMIT_REJECTED',lambda:self.mutate(self.body))

    def test_wp008_exclusion_same_container_refused_before_sql(self):
        body,proof=self.activation()
        proof['exclusion']['newContainerId']=proof['exclusion']['previousContainerId']; self.install(proof)
        with self.assertNumQueries(0):
            self.fault('WRITE_PERMIT_REJECTED',lambda:R.mutate(self.recovery_actor,body,'activate'))

    def test_wp008_exclusion_previous_runtime_must_match_actual_fence(self):
        body,proof=self.activation(); proof['exclusion']['previousRuntimeId']=str(uuid.uuid4()); self.install(proof)
        self.fault('RECOVERY_PRECONDITION_FAILED',lambda:R.mutate(self.recovery_actor,body,'activate'))
        self.assertEqual(Head.objects.get().mode,'FROZEN')
