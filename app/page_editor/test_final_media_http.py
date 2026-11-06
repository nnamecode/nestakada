"""CF07-005: genuine two-PG Save-wins media cleanup; framework reader seam."""
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event
import time
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection, connections
from django.test import TransactionTestCase, override_settings

from media_library.models import Asset, AssetFile, AssetUsage
from media_library.services import prepare_cleanup, confirm_cleanup
from media_library.storage import MediaStorage
from page_versions import engine as E
from page_versions.models import PageRevision, OperationReceipt
from audit.models import AuditEvent
from . import test_media_http as M
from . import test_draft_restore_http as D
from . import test_check_http as H


@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FinalMediaConcurrencyTests(TransactionTestCase):
    login=H.EditorCheckHttpTests.login
    raw=H.EditorCheckHttpTests.raw
    post=H.EditorCheckHttpTests.post
    payload=H.EditorCheckHttpTests.payload
    current=D.DraftRestoreEditorHttpTests.current
    draft=D.DraftRestoreEditorHttpTests.draft
    state=D.DraftRestoreEditorHttpTests.state
    selector=D.DraftRestoreEditorHttpTests.selector
    path=D.DraftRestoreEditorHttpTests.path
    send=D.DraftRestoreEditorHttpTests.send
    checked=D.DraftRestoreEditorHttpTests.checked
    upload=M.EditorMediaHttpTests.upload
    ref=M.EditorMediaHttpTests.ref
    file=M.EditorMediaHttpTests.file

    def setUp(self):
        self.assertEqual(connection.settings_dict['NAME'],'estakada_foundation_unit')
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_user')
            self.assertEqual(cursor.fetchone(),('app_migrator',))
        M.EditorMediaHttpTests.setUp(self)

    def test_cf07_005_actual_save_commit_blocks_cleanup_then_reference_refuses_unlink(self):
        self.assertEqual(self.a.status,'ready')
        self.assertFalse(AssetUsage.objects.filter(asset=self.a).exists())
        self.assertEqual(AssetFile.objects.filter(asset=self.a).count(),3)
        files={str(file.pk):MediaStorage().manifest(file.key) for file in self.a.files.all()}
        other_files={str(file.pk):MediaStorage().manifest(file.key) for file in self.b.files.all()}
        value,selector,_=self.checked({'main_image':self.ref(self.a)})
        prepared=prepare_cleanup(actor=self.owner,asset_ids=[self.a.pk],expected_generation=1)
        self.assertTrue(prepared['confirmation'])
        before_count=PageRevision.objects.filter(page=self.page).count()
        before_current=self.current()
        before_other=PageRevision.objects.filter(page=self.page_b).values_list('pk','payload_hash').get()
        before_audit=AuditEvent.objects.filter(code__startswith='VERSION_').count()
        reached,release=Event(),Event();save_pid=Queue(maxsize=1);cleanup_pid=Queue(maxsize=1);hits=[]
        actual_event=E.event

        def hold_after_real_event(*args,**kwargs):
            result=actual_event(*args,**kwargs)
            self.assertTrue(connection.in_atomic_block)
            self.assertTrue(AssetUsage.objects.filter(asset=self.a,kind='current_page',consumer_id=self.page.pk).exists())
            self.assertFalse(OperationReceipt.objects.filter(pk=value['operationId']).exists())
            hits.append('real_event_inside_tx')
            save_pid.put(connection.connection.info.backend_pid)
            reached.set()
            if not release.wait(15):
                raise RuntimeError('CF005_RELEASE_DEADLINE')
            return result

        def save_worker():
            try:
                response=self.send('save',value,selector=selector)
                return response.status_code,response.json()
            finally:
                connections.close_all()

        def cleanup_worker():
            try:
                connection.ensure_connection()
                cleanup_pid.put(connection.connection.info.backend_pid)
                try:
                    outcome=confirm_cleanup(actor=self.owner,confirmation=prepared['confirmation'],expected_generation=1)
                    return {'refused':False,'states':[row['state'] for row in outcome]}
                except ValidationError as error:
                    return {'refused':True,'messages':error.messages}
            finally:
                connections.close_all()

        blocked=False
        with patch('page_versions.engine.event',side_effect=hold_after_real_event),ThreadPoolExecutor(max_workers=2) as executor:
            saving=executor.submit(save_worker)
            deleting=None
            try:
                self.assertTrue(reached.wait(15),'CF005_SAVE_DID_NOT_REACH_REAL_FINISH')
                first=save_pid.get(timeout=1)
                deleting=executor.submit(cleanup_worker)
                second=cleanup_pid.get(timeout=5)
                self.assertNotEqual(first,second)
                self.assertNotEqual(second,connection.connection.info.backend_pid)
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_blocking_pids(%s)',[second])
                        blockers=cursor.fetchone()[0]
                    if first in blockers:
                        blocked=True
                        break
                    if deleting.done():
                        break
                    time.sleep(0.02)
                self.assertTrue(blocked,'CF005_NO_ACTUAL_PG_BLOCKING_WITNESS')
            finally:
                release.set()
            status,result=saving.result(timeout=15)
            cleanup=deleting.result(timeout=15)

        self.assertEqual(hits,['real_event_inside_tx'])
        self.assertEqual(status,200)
        self.assertTrue(cleanup['refused'])
        self.assertEqual(cleanup['messages'],['MEDIA_ASSET_RETAINED_OR_NOT_READY'])
        self.assertNotEqual(self.current(),before_current)
        self.assertEqual(str(self.current()),result['result_id'])
        self.assertEqual(PageRevision.objects.filter(page=self.page).count(),before_count+1)
        self.assertEqual(OperationReceipt.objects.filter(pk=value['operationId']).count(),0)
        self.assertEqual(AuditEvent.objects.filter(code__startswith='VERSION_').count(),before_audit+1)
        self.assertEqual(PageRevision.objects.filter(page=self.page_b).values_list('pk','payload_hash').get(),before_other)
        self.assertEqual(Asset.objects.get(pk=self.a.pk).status,'ready')
        self.assertEqual(AssetUsage.objects.filter(asset=self.a).count(),2)
        self.assertTrue(AssetUsage.objects.filter(asset=self.a,kind='current_page',consumer_id=self.page.pk).exists())
        self.assertTrue(AssetUsage.objects.filter(asset=self.a,kind='ordinary_version',consumer_id=result['result_id']).exists())
        self.assertEqual({str(file.pk):MediaStorage().manifest(file.key) for file in self.a.files.all()},files)
        self.assertEqual({str(file.pk):MediaStorage().manifest(file.key) for file in self.b.files.all()},other_files)
        print('{"scope":"CF07-005-framework-real-two-PG","saveWins":true,"actualBlockingPidWitness":true,"cleanupRefused":true,"noLegacyReceipt":true,"threePhysicalFilesIntact":true,"frameworkReaderSeam":true,"twoSocketProof":false}',flush=True)
