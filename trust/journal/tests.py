"""SC15 primitive evidence only. TLS/caps/full gate workflow are separate runs."""
import copy
import hashlib
import json
import io
import logging
import os
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from unittest.mock import patch
from django.db import DatabaseError, connection, transaction
from django.test import TransactionTestCase, override_settings
from . import auth, services as S
from .models import Head, Credential, Operation, RoutePolicy, RequestTombstone
from .protocol import Fault, MAX_INT, canonical, validate
from .safe_logging import SafeFormatter

class JournalFixture(TransactionTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.identity=str(uuid.uuid4())
        (root/'pin').write_text(self.identity,encoding='ascii')
        self.items=[{'id':role,'principal':role+'-machine','role':role,'secret':str(index)*64}
            for index,role in enumerate(('reader','writer','recovery'),1)]
        (root/'keys').write_text(json.dumps({'schemaVersion':1,'credentials':self.items}),encoding='ascii')
        self.settings=override_settings(TRUST_IDENTITY_FILE=str(root/'pin'),TRUST_CREDENTIALS_FILE=str(root/'keys'))
        self.settings.enable(); self.addCleanup(self.settings.disable)
        self.env=patch.dict(os.environ,{'TRUST_TEST_EXECUTION':'1'}); self.env.start(); self.addCleanup(self.env.stop)
        S.bootstrap(self.identity)
        self.writer=auth.authenticate('Bearer writer:'+'2'*64,'writer')
        self.reader=auth.authenticate('Bearer reader:'+'1'*64,'reader')
        self.scope=S.calibration_mode(); self.scope.__enter__(); self.addCleanup(self.scope.__exit__,None,None,None)

    def prepare_body(self,target='/Exact?Key=Y'):
        return {'operationId':str(uuid.uuid4()),'incarnation':self.identity,'expectedGeneration':str(Head.objects.get().generation),
            'writerEpoch':'1','kind':'route_restriction','objectId':str(uuid.uuid4()),'basis':'a'*64,
            'policies':[{'target':target,'objectId':str(uuid.uuid4()),'policy':'DELETED','redirectTarget':None}], 'requestIds':[]}
    def report_body(self,body,outcome='committed'):
        return {'operationId':body['operationId'],'incarnation':self.identity,'expectedGeneration':str(Head.objects.get().generation),
            'writerEpoch':'1','outcome':outcome,'mainIncarnation':str(uuid.uuid4()) if outcome!='unknown' else None,
            'mainReceipt':'b'*64 if outcome!='unknown' else None,'policies':body['policies'] if outcome=='committed' else []}
    def mutate(self,body,phase='prepare'): return S.mutate(self.writer,body,phase)
    def fault(self,code,function):
        with self.assertRaises(Fault) as caught: function()
        self.assertEqual(caught.exception.code,code)

class JournalTests(JournalFixture):
    def test_sc004_replay_before_cas_and_terminal_immutable(self):
        body=self.prepare_body(); first=self.mutate(body)
        unknown=self.report_body(body,'unknown'); self.mutate(unknown,'report')
        final=self.report_body(body); self.mutate(final,'report')
        generation=Head.objects.get().generation
        replay=self.mutate(body)
        self.assertTrue(replay['replay']); self.assertEqual(replay['stage'],'FINAL_RESTRICTION')
        self.assertEqual(replay['phaseReceipt'],first['phaseReceipt'])
        self.assertEqual(self.mutate(unknown,'report')['stage'],'FINAL_RESTRICTION')
        self.assertTrue(self.mutate(final,'report')['replay'])
        self.assertEqual(Head.objects.get().generation,generation)
        changed=copy.deepcopy(final); changed['mainReceipt']='c'*64
        self.fault('PHASE_CONFLICT',lambda:self.mutate(changed,'report'))
        self.assertFalse(first['workflowComplete'])

    def test_sc003_stale_cas_and_pending_overlap(self):
        body=self.prepare_body(); other=self.prepare_body('/other')
        self.mutate(body)
        self.fault('CAS_CONFLICT',lambda:self.mutate(other))
        overlap=self.prepare_body(body['policies'][0]['target'])
        self.fault('POLICY_PENDING',lambda:self.mutate(overlap))
        self.assertEqual(Operation.objects.count(),1)

    def test_sc003_two_real_connections_compete_for_same_generation(self):
        first=self.prepare_body('/concurrent-a'); second=self.prepare_body('/concurrent-b')
        before=Head.objects.get().generation
        barrier=Barrier(2,timeout=3)
        def attempt(body):
            try:
                connection.ensure_connection()
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()')
                    pid=cursor.fetchone()[0]
                with S.calibration_mode():
                    barrier.wait()
                    try:
                        result=S.mutate(self.writer,body,'prepare')
                        return ('committed',pid,result['operationId'])
                    except Fault as fault:
                        return (fault.code,pid,body['operationId'])
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(attempt,body) for body in (first,second)]
            outcomes=[future.result(timeout=7) for future in futures]
        self.assertEqual(len({result[1] for result in outcomes}),2)
        self.assertCountEqual([result[0] for result in outcomes],['committed','CAS_CONFLICT'])
        winner=next(result[2] for result in outcomes if result[0]=='committed')
        loser=next(result[2] for result in outcomes if result[0]=='CAS_CONFLICT')
        self.assertEqual(Head.objects.get().generation,before+1)
        self.assertEqual(list(Operation.objects.values_list('id',flat=True)),[uuid.UUID(winner)])
        self.assertEqual(RoutePolicy.objects.get().operation_id,uuid.UUID(winner))
        self.assertFalse(Operation.objects.filter(pk=loser).exists())
        self.assertEqual(RequestTombstone.objects.count(),0)

    def test_sc009_tombstone_abort_never_reopens_or_reuses(self):
        body=self.prepare_body(); body.update(kind='request_tombstone',policies=[],requestIds=[str(uuid.uuid4())])
        self.mutate(body)
        abort=self.report_body(body,'aborted'); self.mutate(abort,'report')
        self.assertEqual(Operation.objects.get().stage,'RECONCILE_REQUIRED')
        self.assertEqual(RequestTombstone.objects.count(),1)
        another=self.prepare_body(); another.update(kind='request_tombstone',policies=[],requestIds=body['requestIds'])
        self.fault('REQUEST_ID_REUSED',lambda:self.mutate(another))
        self.assertNotIn('phone',canonical(S.snapshot(self.reader)).decode())

    def test_sc003_pending_identity_conflicts_across_distinct_targets(self):
        first=self.prepare_body('/first'); self.mutate(first)
        baseline=S.read_head(self.reader)
        for placement in ('root_root','root_policy','policy_root','policy_policy'):
            candidate=self.prepare_body('/different-'+placement)
            shared=first['objectId'] if placement.startswith('root_') else first['policies'][0]['objectId']
            if placement.endswith('_root'): candidate['objectId']=shared
            else: candidate['policies'][0]['objectId']=shared
            self.fault('OBJECT_PENDING',lambda:self.mutate(candidate))
            self.assertEqual(S.read_head(self.reader),baseline)
        self.assertEqual(Operation.objects.count(),1)
        self.assertEqual(RoutePolicy.objects.count(),1)
        self.assertTrue(self.mutate(first)['replay'])

    def test_sc011_old_actual_secret_with_fresh_epoch_rejected(self):
        body=self.prepare_body()
        Credential.objects.filter(pk='writer').update(active=False)
        Head.objects.filter(pk=1).update(writer_epoch=2)
        # Early file authentication still succeeds; authoritative binding must fail.
        old=auth.authenticate('Bearer writer:'+'2'*64,'writer')
        body['writerEpoch']='2'
        self.fault('CREDENTIAL_REVOKED',lambda:S.mutate(old,body,'prepare'))
        self.assertEqual(Operation.objects.count(),0)

    def test_sc002_auth_bad_shape_and_role_do_no_sql(self):
        with self.assertNumQueries(0), patch.object(connection,'ensure_connection',wraps=connection.ensure_connection) as ensure:
            response=self.client.post('/v1/prepare',data='{}',content_type='application/json',HTTP_AUTHORIZATION='Bearer reader:'+'1'*64)
            self.assertEqual(response.status_code,401)
            response=self.client.post('/v1/prepare',data='{}',content_type='application/json',HTTP_AUTHORIZATION='Bearer writer:'+'2'*64)
            self.assertEqual(response.status_code,400)
            response=self.client.get('/v1/head',HTTP_AUTHORIZATION='Bearer reader:'+'0'*64)
            self.assertEqual(response.status_code,401)
            ensure.assert_not_called()
        self.assertEqual(response['Cache-Control'],'no-store')

    def test_sc002_framework_excess_query_fields_no_connection_or_sql(self):
        executions=[]
        def witness(execute,sql,params,many,context):
            executions.append(True)
            raise AssertionError('unexpected SQL on rejected input')
        query='&'.join('field'+str(index)+'=canary' for index in range(1001))
        with connection.execute_wrapper(witness), patch.object(connection,'ensure_connection',wraps=connection.ensure_connection) as ensure:
            response=self.client.get('/v1/snapshot?'+query,HTTP_AUTHORIZATION='Bearer reader:'+'1'*64)
            self.assertEqual(response.status_code,400)
            self.assertEqual(response.json(),{'ok':False,'code':'INPUT_REJECTED'})
            self.assertEqual(response['Cache-Control'],'no-store')
            ensure.assert_not_called()
        self.assertEqual(executions,[])

    def test_sc005_transaction_failure_rolls_back_whole_prepare(self):
        body=self.prepare_body(); before=S.read_head(self.reader)
        with patch.object(RoutePolicy.objects,'update_or_create',side_effect=DatabaseError('synthetic')):
            with self.assertRaises(DatabaseError): self.mutate(body)
        self.assertEqual(S.read_head(self.reader),before)
        self.assertFalse(Operation.objects.exists()); self.assertFalse(RoutePolicy.objects.exists())

    def test_sc012_snapshot_generation_barrier_and_exact_targets(self):
        body=self.prepare_body('/X?Q=a'); self.mutate(body)
        first=S.snapshot(self.reader)
        self.assertEqual(first['items'][0]['target'],'/X?Q=a')
        self.mutate(self.prepare_body('/x?q=a'))
        self.fault('SNAPSHOT_CHANGED',lambda:S.snapshot(self.reader,first['head']['generation'],100))

    def test_sc012_three_real_pages_complete_digest_and_changed_generation(self):
        body=self.prepare_body()
        body['policies']=[{'target':'/Page-'+str(index)+'?Exact=Y','objectId':str(uuid.uuid4()),
            'policy':'DELETED','redirectTarget':None} for index in range(151)]
        self.mutate(body)
        tombs=self.prepare_body(); request_ids=[str(uuid.uuid4()) for _ in range(101)]
        tombs.update(kind='request_tombstone',policies=[],requestIds=request_ids)
        self.mutate(tombs)
        first=S.snapshot(self.reader)
        second=S.snapshot(self.reader,first['head']['generation'],first['nextCursor'])
        third=S.snapshot(self.reader,first['head']['generation'],second['nextCursor'])
        self.assertEqual([len(page['items']) for page in (first,second,third)],[100,100,52])
        self.assertEqual([first['nextCursor'],second['nextCursor'],third['nextCursor']],[100,200,None])
        rows=[]
        for page in (first,second,third):
            self.assertEqual(page['head'],first['head'])
            raw=json.dumps(page['items'],ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
            self.assertEqual(page['pageDigest'],hashlib.sha256(raw).hexdigest())
            rows.extend(page['items'])
        observed_targets=[row['target'] for row in rows if row['type']=='route']
        observed_requests=[row['request_id'] for row in rows if row['type']=='tombstone']
        self.assertCountEqual(observed_targets,[item['target'] for item in body['policies']])
        self.assertCountEqual(observed_requests,request_ids)
        self.assertEqual(len(set(observed_targets)),151)
        self.assertEqual(len(set(observed_requests)),101)
        self.mutate(self.prepare_body('/after-first-snapshot'))
        self.fault('SNAPSHOT_CHANGED',lambda:S.snapshot(self.reader,first['head']['generation'],100))

    def test_sc016_missing_pin_mismatch_and_no_automatic_bootstrap(self):
        Path(self.tmp.name,'pin').write_text(str(uuid.uuid4()),encoding='ascii')
        self.fault('IDENTITY_MISMATCH',lambda:S.read_head(self.reader))
        self.assertEqual(Head.objects.count(),1)
        Path(self.tmp.name,'pin').unlink()
        self.fault('IDENTITY_UNAVAILABLE',lambda:S.read_head(self.reader))

    def test_sc013_reserve_refusal_preserves_existing_denial(self):
        first=self.prepare_body(); self.mutate(first)
        Head.objects.filter(pk=1).update(reserved_bytes=S.COMPLETION_CAP)
        next_body=self.prepare_body('/next')
        self.fault('BUDGET_EXHAUSTED',lambda:self.mutate(next_body))
        self.assertEqual(RoutePolicy.objects.get().policy,'PENDING_DENY')
        self.assertEqual(Operation.objects.count(),1)

    def test_sc004_bigint_saturation_does_not_wrap(self):
        Head.objects.filter(pk=1).update(generation=MAX_INT)
        body=self.prepare_body()
        self.fault('GENERATION_EXHAUSTED',lambda:self.mutate(body))
        self.assertEqual(S.read_head(self.reader)['generation'],str(MAX_INT))

    def test_db_terminal_and_tombstone_protection(self):
        body=self.prepare_body(); self.mutate(body); self.mutate(self.report_body(body),'report')
        with self.assertRaises(DatabaseError),transaction.atomic():
            Operation.objects.filter(pk=body['operationId']).update(stage='MAIN_RESULT_UNKNOWN',terminal_fingerprint=None)
        with self.assertRaises(DatabaseError),transaction.atomic():
            Head.objects.filter(pk=1).update(generation=0)

    def test_persistent_profile_default_closed_outside_explicit_scope(self):
        token=S._test_mode.set(False)
        try: self.fault('WRITE_PROFILE_DISABLED',lambda:self.mutate(self.prepare_body()))
        finally: S._test_mode.reset(token)

    def test_physical_calibration_is_measured_not_profile_approval(self):
        before=S.physical_facts()
        body=self.prepare_body('/'+'q'*2047)
        self.mutate(body); self.mutate(self.report_body(body),'report')
        after=S.physical_facts()
        self.assertEqual(len(after['relations']),6)
        self.assertGreater(after['relationBytes'],0)
        self.assertGreaterEqual(after['databaseBytes'],after['relationBytes'])
        self.assertFalse(after['profileVerified'])
        self.assertLess(after['databaseBytes'],2*1024**3)
        self.assertGreaterEqual(after['relationBytes'],before['relationBytes'])

    def test_protocol_rejects_full_set_not_truncates(self):
        body=self.prepare_body(); body['policies']*=257
        self.fault('INPUT_REJECTED',lambda:validate(body,'prepare'))
        body=self.prepare_body('/'+'x'*2048)
        self.fault('INPUT_REJECTED',lambda:validate(body,'prepare'))

    def test_sc014_formatter_never_accesses_message_arguments_or_traceback(self):
        class Bomb:
            def __str__(self): raise AssertionError('must not stringify')
        record=logging.LogRecord('canary-url-secret',logging.ERROR,'private-path',1,Bomb(),(Bomb(),),
            (ValueError,ValueError('PRIVATE_CANARY'),None))
        record.getMessage=lambda: (_ for _ in ()).throw(AssertionError('must not getMessage'))
        record.request=Bomb(); record.exc_text='PRIVATE_CANARY'; record.stack_info='PRIVATE_CANARY'
        record.trust_event='TRUST_UNAVAILABLE'
        self.assertEqual(json.loads(SafeFormatter().format(record)),
            {'event':'TRUST_UNAVAILABLE','level':'ERROR','result':'rejected'})
        record.trust_event='PRIVATE_CANARY'
        self.assertNotIn('PRIVATE_CANARY',SafeFormatter().format(record))

    def test_sc014_actual_endpoint_failure_pipeline_is_safe_and_observable(self):
        stream=io.StringIO(); handler=logging.StreamHandler(stream); handler.setFormatter(SafeFormatter())
        logger=logging.getLogger('trust.endpoint')
        old_handlers,old_level,old_propagate=logger.handlers[:],logger.level,logger.propagate
        logger.handlers=[handler]; logger.setLevel(logging.ERROR); logger.propagate=False
        try:
            with patch('journal.services.read_head',side_effect=DatabaseError('PRIVATE_CANARY')):
                reply=self.client.get('/v1/head',HTTP_AUTHORIZATION='Bearer reader:'+'1'*64)
            self.assertEqual(reply.status_code,503)
            events=[json.loads(line) for line in stream.getvalue().splitlines()]
            self.assertEqual(events,[{'event':'TRUST_UNAVAILABLE','level':'ERROR','result':'rejected'}])
            self.assertNotIn('PRIVATE_CANARY',stream.getvalue())
            stream.seek(0); stream.truncate()
            with patch('journal.services.read_head',side_effect=RuntimeError('PRIVATE_CANARY')):
                reply=self.client.get('/v1/head',HTTP_AUTHORIZATION='Bearer reader:'+'1'*64)
            self.assertEqual(reply.status_code,500)
            self.assertEqual(json.loads(stream.getvalue())['event'],'UNEXPECTED_FAILURE')
            self.assertNotIn('PRIVATE_CANARY',reply.content.decode())
        finally:
            logger.handlers=old_handlers; logger.setLevel(old_level); logger.propagate=old_propagate
