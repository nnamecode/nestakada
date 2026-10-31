"""MH02..09 HTTP/PG/FS checks. Real positive decoder+HTTP tests are separate QA e2e.

Ledger fixtures are internal bytes, not evidence of JPEG/PNG/WebP acceptance.
Dummy transport/result objects below exercise only negative failure/revocation paths.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
from tempfile import TemporaryDirectory
from threading import Thread
from types import SimpleNamespace
from urllib.parse import urlencode
from unittest.mock import patch, Mock
from uuid import uuid4
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, TransactionTestCase, SimpleTestCase, override_settings
from django.urls import reverse
from accounts.models import UserProfile
from accounts.services import bootstrap_owner, create_employee
from audit.models import AuditEvent
from content.models import Page
from .models import Asset, AssetFile, AssetUsage, MediaFolder, PageMediaHome
from . import services, uploads
from .worker_client import WorkerClient, UploadPending, WorkerUnavailable, UploadRejected, webp_dimensions

PASSWORD='Media-Unit-Owner-2026-Aa!7'
EMPLOYEE_PASSWORD='Media-Unit-Employee-2026-Aa!7'


@override_settings(AUTH_TRUSTED_PROXY_HOST=None)
class MediaHttpTests(TransactionTestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.storage=Path(self.temp.name,'media');self.storage.mkdir()
        self.exchange=Path(self.temp.name,'exchange');self.exchange.mkdir()
        self.override=override_settings(MEDIA_LIBRARY_ROOT=str(self.storage),MEDIA_EXCHANGE_ROOT=str(self.exchange))
        self.override.enable();self.addCleanup(self.override.disable)
        self.owner=bootstrap_owner(PASSWORD)
        self.employee=create_employee(actor=self.owner,username='media-http-employee',password=EMPLOYEE_PASSWORD)
        self.page=Page.objects.create(kind=Page.Kind.ARTICLE,name='needle parent')
        self.folder=MediaFolder.objects.create(path='fixture/foo')
        PageMediaHome.objects.create(page=self.page,folder=self.folder)
        self.owner_client=self.login('nesadmin',PASSWORD)
        self.employee_client=self.login('media-http-employee',EMPLOYEE_PASSWORD)
        self.visitor=Client(enforce_csrf_checks=True,HTTP_HOST='localhost')

    def csrf(self,client):
        return client.cookies[settings.CSRF_COOKIE_NAME].value

    def form(self,client,url,data,csrf=True):
        values={**data}
        if csrf:values['csrfmiddlewaretoken']=self.csrf(client)
        return client.post(url,urlencode(values,doseq=True),content_type='application/x-www-form-urlencoded')

    def login(self,username,password):
        client=Client(enforce_csrf_checks=True,HTTP_HOST='localhost')
        self.assertEqual(client.get('/manage/login/').status_code,200)
        response=self.form(client,'/manage/login/',{'username':username,'password':password})
        self.assertEqual(response.status_code,303)
        return client

    def file_asset(self,folder=None):
        asset=Asset.objects.create(folder=folder or self.folder,provenance='internal ledger fixture, not an image decoder')
        for kind,key,data in [('private-source',f'private/sources/{asset.pk}/original.bin',b'PRIVATE-ORIGINAL-CANARY'),
                              ('main',f'img/fixture/{asset.pk}/main.data',b'internal-main-bytes')]:
            services.write_file(asset_id=asset.pk,kind=kind,key=key,chunks=data)
        return services.mark_ready(asset_id=asset.pk)

    def post_image(self,client,data=b'not valid PNG',name='synthetic.png',mime='image/png',csrf=True):
        values={'generation':'1'}
        if csrf:values['csrfmiddlewaretoken']=self.csrf(client)
        values['image']=SimpleUploadedFile(name,data,content_type=mime)
        return client.post(reverse('media_library:upload',args=[self.page.pk]),values)

    def assert_private(self,response):
        self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertIn('Cookie',response.get('Vary',''))

    def test_mh02_closed_routes_enforce_actor_and_csrf(self):
        for url in [reverse('media_library:catalog'),reverse('media_library:cleanup')]:
            for client,status in [(self.owner_client,200),(self.employee_client,403),(self.visitor,401)]:
                with self.subTest(url=url,status=status):
                    response=client.get(url);self.assertEqual(response.status_code,status);self.assert_private(response)
        response=self.post_image(self.owner_client,csrf=False)
        self.assertEqual(response.status_code,403);self.assert_private(response)
        response=self.post_image(self.employee_client)
        self.assertEqual(response.status_code,403);self.assert_private(response)
        response=self.post_image(self.visitor,csrf=False)
        self.assertEqual(response.status_code,401)
        self.assertFalse(Asset.objects.exists())

    def test_mh03_file_bytes_formats_and_count_reject_before_decoder(self):
        with patch('media_library.uploads.WorkerClient.process') as decoder:
            self.assertEqual(self.post_image(self.owner_client,data=b'x'*1_000_001).status_code,413)
            self.assertEqual(self.post_image(self.owner_client,name='picture.svg',mime='image/svg+xml').status_code,400)
            self.assertEqual(self.post_image(self.owner_client,name='picture.png',mime='text/html').status_code,400)
            self.assertEqual(self.post_image(self.owner_client,data=b'').status_code,400)
            response=self.owner_client.post(reverse('media_library:upload',args=[self.page.pk]),
                {'generation':'1','csrfmiddlewaretoken':self.csrf(self.owner_client),'image':[SimpleUploadedFile('one.png',b'one',content_type='image/png'),SimpleUploadedFile('two.png',b'two',content_type='image/png')]})
            self.assertEqual(response.status_code,400)
            decoder.assert_not_called()
        self.assertFalse(Asset.objects.exists())

    def test_mh03_exact_decimal_megabyte_is_not_truncated_before_decoder_rejection(self):
        # Deliberately invalid image: this tests only the HTTP byte boundary, not codec acceptance.
        data=b'x'*1_000_000
        with patch('media_library.uploads.WorkerClient.process',side_effect=UploadRejected('negative codec fixture')) as decoder:
            response=self.post_image(self.owner_client,data=data)
        self.assertEqual(response.status_code,400)
        self.assertEqual(decoder.call_args.args[0],data)
        self.assertFalse(Asset.objects.exists())

    def test_mh03_body_guard_precedes_csrf_and_multipart_parse(self):
        response=self.owner_client.post(reverse('media_library:upload',args=[self.page.pk]),b'',
            content_type='multipart/form-data; boundary=unused',CONTENT_LENGTH=str(11*1024*1024+1))
        self.assertEqual(response.status_code,413);self.assert_private(response)
        self.assertFalse(Asset.objects.exists())

    def test_mh04_revocation_after_terminal_worker_reply_prevents_registration(self):
        cleanup=Mock();quarantine=Mock()
        def revoked(*args,**kwargs):
            self.assertFalse(connection.in_atomic_block)
            UserProfile.objects.filter(user=self.owner).update(generation=2)
            # Negative authorization boundary only. These bytes must never reach a stored Asset.
            return SimpleNamespace(outputs={'main':b'unreachable','preview':b'unreachable'},cleanup=cleanup,quarantine=quarantine)
        with patch('media_library.uploads.WorkerClient.process',side_effect=revoked):
            response=self.post_image(self.owner_client)
        self.assertEqual(response.status_code,403)
        cleanup.assert_called_once();self.assertFalse(Asset.objects.exists())
        self.assertFalse(any(self.storage.rglob('*.webp')))

    def test_mh05_original_has_no_preview_and_private_routes_do_not_leak_it(self):
        asset=self.file_asset();original=asset.files.get(kind='private-source')
        url=reverse('media_library:preview',args=[original.pk])
        for client,status in [(self.owner_client,404),(self.employee_client,403),(self.visitor,401)]:
            response=client.get(url);self.assertEqual(response.status_code,status);self.assert_private(response)
            self.assertNotIn(b'PRIVATE-ORIGINAL-CANARY',response.content)
        response=self.visitor.get('/'+original.key)
        self.assertEqual(response.status_code,404)
        self.assertNotIn(b'PRIVATE-ORIGINAL-CANARY',response.content)

    def test_mh06_logical_recursive_search_does_not_include_prefix_neighbor(self):
        first=self.file_asset()
        child=MediaFolder.objects.create(path='fixture/foo/child');neighbor=MediaFolder.objects.create(path='fixture/foobar')
        for folder in [child,neighbor]:
            page=Page.objects.create(kind=Page.Kind.ARTICLE,name='needle '+folder.path)
            PageMediaHome.objects.create(page=page,folder=folder)
        nested=self.file_asset(child);outside=self.file_asset(neighbor)
        response=self.owner_client.get(reverse('media_library:catalog'),{'folder':'fixture/foo','q':'needle'})
        self.assertContains(response,f'data-media-asset-id="{first.pk}"')
        self.assertContains(response,f'data-media-asset-id="{nested.pk}"')
        self.assertNotContains(response,f'data-media-asset-id="{outside.pk}"')
        for folder in ['../','/etc','fixture/foo/../foobar','fixture/foo%2f..']:
            self.assertEqual(self.owner_client.get(reverse('media_library:catalog'),{'folder':folder}).status_code,404)
        self.page.name='renamed page';self.page.save()
        self.assertEqual(PageMediaHome.objects.get(page=self.page).folder_id,self.folder.pk)

    def prepare(self,asset):
        response=self.form(self.owner_client,reverse('media_library:cleanup_prepare'),{'generation':'1','asset_ids':[str(asset.pk)]})
        self.assertEqual(response.status_code,200)
        match=re.search(r'name="confirmation" value="([^"]+)"',response.content.decode())
        self.assertIsNotNone(match)
        return match.group(1)

    def test_mh07_cleanup_confirmation_late_reference_blocks_and_cancel_is_read_only(self):
        asset=self.file_asset();keys=list(asset.files.values_list('key',flat=True));before={key:(self.storage/key).read_bytes() for key in keys}
        ticket=self.prepare(asset)
        response=self.owner_client.get(reverse('media_library:cleanup'))
        self.assertContains(response,'Проверенные кандидаты: 1')
        self.assertTrue(Asset.objects.filter(pk=asset.pk).exists())
        self.assertEqual(before,{key:(self.storage/key).read_bytes() for key in keys})
        services.attach(asset_id=asset.pk,kind='retained_html',consumer_id=uuid4(),slot='internal-ledger-fixture')
        response=self.form(self.owner_client,reverse('media_library:cleanup_confirm'),{'generation':'1','confirmation':ticket})
        self.assertEqual(response.status_code,400)
        self.assertEqual(before,{key:(self.storage/key).read_bytes() for key in keys})

    def test_mh07_cleanup_actual_bytes_failure_and_retry_http(self):
        asset=self.file_asset();files=list(asset.files.order_by('key'));ticket=self.prepare(asset)
        protected=(self.storage/files[-1].key).parent;protected.chmod(0o500)
        try:response=self.form(self.owner_client,reverse('media_library:cleanup_confirm'),{'generation':'1','confirmation':ticket})
        finally:protected.chmod(0o700)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'data-state="delete_failed"');self.assertContains(response,'data-pending-files="1"')
        self.assertTrue(Asset.objects.filter(pk=asset.pk).exists())
        response=self.form(self.owner_client,reverse('media_library:cleanup_retry',args=[asset.pk]),{'generation':'1'})
        self.assertEqual(response.status_code,200);self.assertContains(response,'data-state="deleted"')
        self.assertFalse(Asset.objects.filter(pk=asset.pk).exists())
        for file in files:self.assertFalse((self.storage/file.key).exists())

    def test_mh08_worker_pending_never_creates_ready_or_retries(self):
        with patch('media_library.uploads.WorkerClient.process',side_effect=UploadPending('synthetic negative fault')) as decoder:
            response=self.post_image(self.owner_client)
        self.assertEqual(response.status_code,503);self.assertContains(response,'Загрузка не завершена',status_code=503)
        decoder.assert_called_once();self.assertFalse(Asset.objects.exists())

    def test_mh09_rejected_filename_never_enters_audit_fields(self):
        canary='RAW-FILENAME-PRIVATE-CANARY'
        response=self.post_image(self.owner_client,name=canary+'.svg',mime='image/svg+xml')
        self.assertEqual(response.status_code,400)
        fields=list(AuditEvent.objects.filter(code__startswith='MEDIA_').values())
        self.assertTrue(fields)
        self.assertNotIn(canary,str(fields));self.assertNotIn('not valid PNG',str(fields))
        self.assertTrue(all(row['object_ref'] in ('',None) or str(row['object_ref']).startswith('uuid:') for row in fields))

    def test_mh09_upload_accepted_and_cleanup_emit_actual_typed_uuid_audit_rows(self):
        # Writer integration only: this ledger fixture does not claim decoder/upload acceptance.
        asset=self.file_asset()
        uploads.media_event('MEDIA_UPLOAD_ACCEPTED',self.owner,asset.pk)
        uploads.media_event('MEDIA_CLEANUP_PREPARED',self.owner,str(asset.pk))
        events=list(AuditEvent.objects.filter(code__in=['MEDIA_UPLOAD_ACCEPTED','MEDIA_CLEANUP_PREPARED']).order_by('code'))
        self.assertEqual(len(events),2)
        for event in events:
            self.assertEqual(event.object_ref,'uuid:'+str(asset.pk))
            self.assertEqual(event.object_kind,'media_asset')
            self.assertEqual(event.actor_id,self.owner.pk)
            self.assertEqual(event.result,'SUCCESS')


class WorkerClientNegativeTests(SimpleTestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.override=override_settings(MEDIA_EXCHANGE_ROOT=str(self.root))
        self.override.enable();self.addCleanup(self.override.disable)

    def test_missing_worker_discards_only_unsent_job(self):
        with self.assertRaises(WorkerUnavailable):WorkerClient().process(b'input','.png','image/png')
        self.assertEqual(list((self.root/'jobs').iterdir()),[])

    def test_bad_terminal_json_keeps_quarantine_and_input(self):
        ready=[]
        server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);server.bind(str(self.root/'media-worker.sock'));server.listen(1)
        def reply():
            with server:
                connection,_=server.accept()
                with connection:
                    raw=b''
                    while not raw.endswith(b'\n'):raw+=connection.recv(4096)
                    ready.append(json.loads(raw));connection.sendall(b'{"status":"ok","arbitrary":true}\n')
        server.settimeout(3)
        thread=Thread(target=reply,daemon=True);thread.start()
        try:
            with self.assertRaises(UploadPending):WorkerClient().process(b'input','.png','image/png')
        finally:
            thread.join(timeout=2);server.close()
        self.assertFalse(thread.is_alive())
        job=self.root/'jobs'/ready[0]['job_id']
        self.assertEqual((job/'input.bin').read_bytes(),b'input');self.assertTrue((job/'pending.json').exists())
        self.assertEqual(len(WorkerClient().pending()),1)

    def test_symlink_job_is_not_followed_and_pending_does_not_read_it(self):
        (self.root/'jobs').mkdir();job_id=str(uuid4())
        with TemporaryDirectory() as outside:
            (self.root/'jobs'/job_id).symlink_to(outside,target_is_directory=True)
            with self.assertRaises(OSError):WorkerClient()._job(job_id)
            self.assertEqual(WorkerClient().pending(),[])

    def test_pending_directory_remains_visible_without_allocatable_marker(self):
        (self.root/'jobs').mkdir();job_id=str(uuid4());(self.root/'jobs'/job_id).mkdir()
        self.assertEqual(WorkerClient().pending(),[{'job_id':job_id,'asset_id':None}])

    def test_malformed_webp_headers_and_metadata_are_rejected(self):
        for data in [b'',b'RIFFxxxxWEBP',b'<svg/>',b'RIFF\x10\0\0\0WEBPVP8X\xff\xff\xff\xff']:
            with self.assertRaises(ValueError):webp_dimensions(data)
