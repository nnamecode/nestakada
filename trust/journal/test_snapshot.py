"""SS15 actual PG/endpoint and hostile transport tests, not an HTML gate."""
import copy
import hashlib
import json
import subprocess
import sys
import time
import uuid
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from django.db import connection
from django.test import SimpleTestCase
from . import consumer as C,services as S
from .models import Head,RoutePolicy,RequestTombstone
from .tests import JournalFixture

class SnapshotTests(JournalFixture):
    def setUp(self):
        super().setUp()
        body=self.prepare_body()
        body['policies']=[{'target':'/Путь/Ё-'+str(index)+'?Case=Ю','objectId':str(uuid.uuid4()),
            'policy':('HIDDEN','DELETED','REDIRECT')[index%3],
            'redirectTarget':'/Новый?Case=X' if index%3==2 else None} for index in range(150)]
        self.mutate(body);self.mutate(self.report_body(body),'report')
        self.mutate(self.prepare_body('/Pending?Exact=Y'))
        tomb=self.prepare_body();tomb.update(kind='request_tombstone',policies=[],requestIds=[str(uuid.uuid4()) for _ in range(101)])
        self.mutate(tomb)
        self.expected=S.read_head(self.reader);self.calls=[]

    def transport(self,target,timeout):
        self.assertGreater(timeout,0);self.assertLessEqual(timeout,6)
        self.calls.append(target)
        response=self.client.get(target,HTTP_AUTHORIZATION='Bearer reader:'+'1'*64)
        if response.status_code!=200: raise C.SnapshotRejected('SNAPSHOT_TRANSPORT_REJECTED')
        self.assertEqual(response['Cache-Control'],'no-store')
        return response.json()

    def refused(self,transport=None):
        with self.assertRaises(C.SnapshotRejected): C.read_snapshot(transport or self.transport,self.identity)

    def tamper(self,transform):
        def transport(target,timeout):
            value=self.transport(target,timeout)
            return transform(target,value)
        return transport

    def page_tamper(self,change,recalculate=True):
        def alter(target,value):
            if target.startswith('/v1/snapshot?'):
                change(value)
                if recalculate:value['pageDigest']=hashlib.sha256(C.canonical(value['items'])).hexdigest()
            return value
        return self.tamper(alter)

    def test_ss001_stream_manifest_matches_independent_all_pg_rows(self):
        manifest=self.transport('/v1/snapshot-manifest',6)
        rows=[]
        for row in RoutePolicy.objects.order_by('key').values('key','target','object_id','generation','policy','redirect_target'):
            rows.append({'type':'route',**row,'object_id':str(row['object_id']),'generation':str(row['generation'])})
        for row in RequestTombstone.objects.order_by('request_id').values('request_id','tombstone_id','generation'):
            rows.append({'type':'tombstone',**{key:str(value) for key,value in row.items()}})
        raw=json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
        self.assertEqual(manifest['snapshotDigest'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(manifest['counts'],{'routes':151,'tombstones':101,'items':252})
        verified=C.read_snapshot(self.transport,self.identity)
        self.assertEqual(verified.items_bytes,raw)
        self.assertEqual({row.get('policy') for row in rows if row['type']=='route'}, {'HIDDEN','DELETED','REDIRECT','PENDING_DENY'})

    def test_ss001_three_pages_complete_immutable_result(self):
        value=C.read_snapshot(self.transport,self.identity)
        self.assertEqual((value.total_routes,value.total_tombstones),(151,101))
        self.assertEqual(len(self.calls),5)
        self.assertIn('cursor=0',self.calls[1]);self.assertIn('cursor=100',self.calls[2]);self.assertIn('cursor=200',self.calls[3])
        self.assertEqual(value.digest,hashlib.sha256(value.items_bytes).hexdigest())
        with self.assertRaises(TypeError): value.head['generation']='999'
        with self.assertRaises(FrozenInstanceError): value.digest='x'
        self.assertIsInstance(value.items_bytes,bytes)

    def test_ss005_startup_current_cohort_only_snapshot_ready(self):
        result=C.startup_check(self.transport,self.identity,self.expected)
        self.assertTrue(result.snapshot_ready);self.assertFalse(result.html_admission);self.assertFalse(result.workflow_complete)

    def test_ss004_old_valid_restored_cohort_stays_closed(self):
        old=dict(self.expected);old['generation']=str(int(old['generation'])-1)
        result=C.startup_check(self.transport,self.identity,old)
        self.assertFalse(result.snapshot_ready);self.assertFalse(result.html_admission)

    def test_ss004_foreign_incarnation_stays_closed(self):
        self.assertFalse(C.startup_check(self.transport,str(uuid.uuid4()),self.expected).snapshot_ready)

    def test_ss004_actual_frozen_database_head_stays_closed(self):
        Head.objects.filter(pk=1).update(mode='FROZEN')
        self.assertFalse(C.startup_check(self.transport,self.identity,self.expected).snapshot_ready)

    def test_ss004_invalid_pin_is_closed_without_network(self):
        self.assertFalse(C.startup_check(lambda *_:self.fail('must not fetch'),'',self.expected).snapshot_ready)

    def test_ss002_truncated_page_rejects_even_with_new_page_digest(self):
        self.refused(self.page_tamper(lambda page:page['items'].pop()))

    def test_ss002_early_null_next_cursor_rejects(self):
        self.refused(self.page_tamper(lambda page:page.update(nextCursor=None)))

    def test_ss002_empty_middle_rejects(self):
        def alter(target,value):
            if target.endswith('cursor=100'):value['items']=[];value['pageDigest']=hashlib.sha256(b'[]').hexdigest()
            return value
        self.refused(self.tamper(alter))

    def test_ss002_duplicate_row_rejects_rehashed_page(self):
        def alter(page):page['items'][1]=copy.deepcopy(page['items'][0])
        self.refused(self.page_tamper(alter))

    def test_ss002_out_of_order_rejects_rehashed_page(self):
        def alter(page):page['items'][0],page['items'][1]=page['items'][1],page['items'][0]
        self.refused(self.page_tamper(alter))

    def test_ss002_wrong_full_digest_rejects_all_other_valid_pages(self):
        def alter(target,value):
            if target=='/v1/snapshot-manifest':value['snapshotDigest']='f'*64
            return value
        self.refused(self.tamper(alter))

    def test_ss002_wrong_page_digest_rejects(self):
        self.refused(self.page_tamper(lambda page:page.update(pageDigest='f'*64),False))

    def test_ss002_rehashed_semantic_change_cannot_hide_full_digest(self):
        def alter(page):page['items'][0]['object_id']=str(uuid.uuid4())
        self.refused(self.page_tamper(alter))

    def test_ss002_extra_row_field_rejects(self):
        def alter(page):page['items'][0]['unexpected']=True
        self.refused(self.page_tamper(alter))

    def test_ss002_wrong_types_reject_bool_cursor(self):
        self.refused(self.page_tamper(lambda page:page.update(cursor=False)))

    def test_ss002_wrong_target_hash_rejects(self):
        def alter(page):page['items'][0]['target']='/Different?Exact=Y'
        self.refused(self.page_tamper(alter))

    def test_ss003_real_generation_change_between_pages(self):
        def alter(target,value):
            if target.endswith('cursor=0'):self.mutate(self.prepare_body('/Concurrent'))
            return value
        self.refused(self.tamper(alter))
        self.assertEqual(len(self.calls),3)

    def test_ss003_real_generation_change_before_final_head(self):
        def alter(target,value):
            if target.endswith('cursor=200'):self.mutate(self.prepare_body('/Concurrent-last'))
            return value
        self.refused(self.tamper(alter))

    def test_ss003_same_generation_different_head_digest_rejects(self):
        def alter(target,value):
            if target=='/v1/head':value['head']['digest']='f'*64
            return value
        self.refused(self.tamper(alter))

    def test_ss006_manifest_method_role_and_query_early_reject_no_sql(self):
        with self.assertNumQueries(0),patch.object(connection,'ensure_connection',wraps=connection.ensure_connection) as spy:
            for method,path,token,status in [('post','/v1/snapshot-manifest','reader:'+'1'*64,405),
                ('get','/v1/snapshot-manifest','writer:'+'2'*64,401),
                ('get','/v1/snapshot-manifest?unknown=1','reader:'+'1'*64,400)]:
                response=getattr(self.client,method)(path,HTTP_AUTHORIZATION='Bearer '+token)
                self.assertEqual(response.status_code,status);self.assertEqual(response['Cache-Control'],'no-store')
            spy.assert_not_called()

    def test_ss006_transport_failure_no_retries_and_no_cached_ready(self):
        first=C.startup_check(self.transport,self.identity,self.expected);self.assertTrue(first.snapshot_ready)
        calls=[]
        def unavailable(*args):calls.append(args);raise C.SnapshotRejected('SNAPSHOT_TRANSPORT_REJECTED')
        second=C.startup_check(unavailable,self.identity,self.expected)
        self.assertFalse(second.snapshot_ready);self.assertEqual(len(calls),1)

    def test_ss007_whole_deadline_checked_after_http_and_iterations(self):
        clock=[100.0]
        def fetch(target,timeout):
            result=self.transport(target,timeout);clock[0]+=31;return result
        with patch.object(C.time,'monotonic',side_effect=lambda:clock[0]):self.refused(fetch)
        self.assertEqual(len(self.calls),1)

    def test_ss007_count_bound_rejects_without_fetching_pages(self):
        def alter(target,value):
            if target=='/v1/snapshot-manifest':value['counts']={'routes':50001,'tombstones':0,'items':50001}
            return value
        self.refused(self.tamper(alter));self.assertEqual(len(self.calls),1)

    def test_ss007_actual_worker_slow_output_is_killed_and_reaped(self):
        original=subprocess.Popen;children=[]
        def spawn(*args,**kwargs):
            child=original(*args,**kwargs);children.append(child);return child
        command=[sys.executable,'-I','-c',"import sys,time\nsys.stdin.buffer.read()\nfor _ in range(200):\n sys.stdout.write('x');sys.stdout.flush();time.sleep(0.05)\n"]
        started=time.monotonic()
        with patch.object(C,'_worker_command',return_value=command),patch.object(C.subprocess,'Popen',side_effect=spawn):
            with self.assertRaises(C.SnapshotRejected) as error:C.HTTPSReader('/unused','reader','1'*64)('/v1/head',0.3)
        self.assertEqual(error.exception.code,'SNAPSHOT_DEADLINE')
        self.assertLess(time.monotonic()-started,2)
        self.assertEqual(len(children),1);self.assertIsNotNone(children[0].returncode)

    def test_ss007_snapshot_bytes_bound_rejects_before_return(self):
        with patch.object(C,'MAX_SNAPSHOT',128):self.refused()

class EmptySnapshotTests(JournalFixture):
    def test_ss007_empty_snapshot_has_zero_pages_and_two_reads(self):
        calls=[]
        def transport(target,timeout):
            calls.append(target)
            if target=='/v1/head':return {'ok':True,'head':S.read_head(self.reader)}
            return {'ok':True,**S.snapshot_manifest(self.reader)}
        value=C.read_snapshot(transport,self.identity)
        self.assertEqual(value.items_bytes,b'[]');self.assertEqual(value.total_routes,0)
        self.assertEqual(calls,['/v1/snapshot-manifest','/v1/head'])

class HTTPSWorkerTests(SimpleTestCase):
    def run_worker(self,*,status=200,headers=None,raw=b'{"ok":true}'):
        if headers is None:headers={'Cache-Control':'no-store','Content-Type':'application/json'}
        response=SimpleNamespace(status=status,getheader=lambda name,default=None:headers.get(name,default),read=lambda bound:raw[:bound])
        connection=SimpleNamespace(request=lambda *a,**k:None,getresponse=lambda:response,close=lambda:None)
        with (patch.object(C.ssl,'create_default_context',return_value=object()) as context,
              patch.object(C.http.client,'HTTPSConnection',return_value=connection) as factory):
            result=C._http_worker({'ca':'/run/secrets/ingress-ca','credential':'reader','secret':'1'*64,'target':'/v1/head'})
        self.assertEqual(factory.call_args.args,('trust-ingress',8443))
        context.assert_called_once_with(cafile='/run/secrets/ingress-ca')
        return result

    def test_ss006_worker_fixed_origin_and_verified_ca_path(self):
        self.assertEqual(self.run_worker(),{'ok':True})

    def test_ss006_worker_refuses_redirect_without_following(self):
        with self.assertRaises(C.SnapshotRejected):self.run_worker(status=302,headers={'Location':'https://foreign.invalid'})

    def test_ss006_worker_refuses_cookie(self):
        with self.assertRaises(C.SnapshotRejected):self.run_worker(headers={'Cache-Control':'no-store','Content-Type':'application/json','Set-Cookie':'private-canary'})

    def test_ss006_worker_refuses_cacheable_response(self):
        with self.assertRaises(C.SnapshotRejected):self.run_worker(headers={'Cache-Control':'public','Content-Type':'application/json'})

    def test_ss007_worker_refuses_oversized_body(self):
        with self.assertRaises(C.SnapshotRejected):self.run_worker(raw=b' '*1048577)

    def test_ss006_worker_refuses_duplicate_json_members(self):
        with self.assertRaises(C.SnapshotRejected):self.run_worker(raw=b'{"ok":true,"ok":false}')

    def test_ss006_transport_rejects_arbitrary_origin_and_path(self):
        reader=C.HTTPSReader('/run/secrets/ingress-ca','reader','1'*64)
        with patch.object(C.subprocess,'Popen') as child:
            for target in ('https://foreign.invalid/v1/head','/v1/prepare','/v1/head?secret=x','/v1/snapshot?cursor=0'):
                with self.assertRaises(C.SnapshotRejected):reader(target,1)
            child.assert_not_called()
