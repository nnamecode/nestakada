"""E2 main/preview: real uploads/worker/PG/FS, framework HTTP reader seam."""
import base64
import copy
import hashlib
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.test import TransactionTestCase, override_settings

from accounts.models import AuthSession
from accounts.services import set_grant
from audit.models import AuditEvent
from content.models import Page, Route
from media_library.models import AssetFile, AssetUsage
from media_library.storage import MediaStorage
from media_library.uploads import upload
from media_library.services import prepare_cleanup
from page_versions import services as V, schema as S, engine as E
from page_versions.models import PageRevision, RestoreStage
from page_editor import test_check_http as H
from page_editor import test_draft_restore_http as D

# Exact previously approved synthetic corpus, not personal/gallery photographs.
PNG='iVBORw0KGgoAAAANSUhEUgAAAGQAAAAyCAYAAACqNX6+AAAAlUlEQVR4nO3RQRHAIADAsDFJaEIIKtC79xTQR6Kgdx1znf2Q8d4O4M+QGENiDIkxJMaQGENiDIkxJMaQGENiDIkxJMaQGENiDIkxJMaQGENiDIkxJMaQGENiDIkxJMaQGENiDIkxJMaQGENiDIkxJMaQGENiDIkxJMaQGENiDIkxJMaQGENiDIkxJMaQGENiDIkxJOYDj0ACEAwqRxgAAAAASUVORK5CYII='
JPEG='/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAyAGQDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDmqKKK908UKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooA/9k='
CORPUS={'png':(PNG,'image/png','06908e28b4c42eaab6b67833f32c178d0223c07fd5837ad155394777d98fb12c'),
        'jpg':(JPEG,'image/jpeg','4603ec2c4256971c8c8d9686709f276357966183f859023e32a3a329418bc806')}
TEST_TEMPLATES=copy.deepcopy(settings.TEMPLATES)
TEST_TEMPLATES[0]['DIRS']=[*TEST_TEMPLATES[0].get('DIRS',[]),str(settings.BASE_DIR/'page_editor'/'templates')]


@override_settings(ROOT_URLCONF='page_editor.test_check_http',MIDDLEWARE=H.TEST_MIDDLEWARE,
                   TEMPLATES=TEST_TEMPLATES,AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EditorMediaHttpTests(TransactionTestCase):
    login=H.EditorCheckHttpTests.login
    payload=H.EditorCheckHttpTests.payload
    raw=H.EditorCheckHttpTests.raw
    post=H.EditorCheckHttpTests.post
    current=D.DraftRestoreEditorHttpTests.current
    draft=D.DraftRestoreEditorHttpTests.draft
    state=D.DraftRestoreEditorHttpTests.state
    selector=D.DraftRestoreEditorHttpTests.selector
    path=D.DraftRestoreEditorHttpTests.path
    send=D.DraftRestoreEditorHttpTests.send
    checked=D.DraftRestoreEditorHttpTests.checked

    def setUp(self):
        H.EditorCheckHttpTests.setUp(self)
        self.page_b=Page.objects.create(kind=Page.Kind.ARTICLE,name='Media foreign Page')
        Route.objects.create(page=self.page_b,kind=Route.Kind.PRIMARY,target='/media-foreign/')
        self.a=self.upload('png',self.page)
        self.b=self.upload('jpg',self.page_b)
        V.initialize(actor=self.owner,page_id=self.page_b.pk,
            snapshot=S.snapshot_v1(self.page_b.kind,main_text='<p>OTHER</p>',main_image=self.ref(self.b)),
            expected_generation=1,operation_id=uuid4())

    def upload(self,kind,page):
        encoded,mime,expected=CORPUS[kind];data=base64.b64decode(encoded,validate=True)
        self.assertEqual(hashlib.sha256(data).hexdigest(),expected)
        asset=upload(actor=self.owner,page_id=page.pk,
            upload=SimpleUploadedFile('synthetic.'+kind,data,content_type=mime),expected_generation=1)
        self.assertEqual(asset.status,'ready')
        self.assertEqual(asset.files.count(),3)
        source=asset.files.get(kind='private-source')
        self.assertEqual(MediaStorage().manifest(source.key),{'sha256':expected,'byte_size':len(data)})
        return asset

    def ref(self,asset,**kwargs):
        value={'asset_id':str(asset.pk),'alt':'Synthetic 😀','alignment':'center','width_px':None,'height_px':None}
        value.update(kwargs)
        return value

    def media_url(self,file,selector=None,picker=False,page=None):
        path='/manage/pages/%s/edit/media/%s/%s/' % ((page or self.page).pk,'picker-files' if picker else 'files',file.pk)
        return path+('?' + urlencode(selector) if selector else '')

    def file(self,asset,kind='main'):
        return asset.files.get(kind=kind)

    def assert_image(self,response,file):
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'].split(';')[0],'image/webp')
        self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.assertIn('no-store',response['Cache-Control'])
        body=b''.join(response.streaming_content)
        response.close()
        actual=MediaStorage().manifest(file.key)
        self.assertEqual(len(body),actual['byte_size'])
        self.assertEqual(hashlib.sha256(body).hexdigest(),actual['sha256'])
        self.assertEqual(body[:4],b'RIFF');self.assertEqual(body[8:12],b'WEBP')

    def commit(self,changes,*,client=None,draft=None,stage=None):
        value,selector,_=self.checked(changes,client=client,draft=draft,stage=stage)
        response=self.send('save',value,selector=selector,client=client)
        self.assertEqual(response.status_code,200)
        return value,selector,response.json()

    def physical(self,file):
        root=Path(settings.MEDIA_LIBRARY_ROOT).resolve()
        path=(root/file.key).resolve()
        self.assertTrue(path.is_relative_to(root))
        return path

    def stage(self,actor,source):
        prepared=V.prepare_restore(actor=actor,page_id=self.page.pk,version_id=source,expected_generation=1)
        result=V.stage_restore(actor=actor,page_id=self.page.pk,preparation=prepared['preparation'],
            confirm_input_replacement=True,expected_generation=1,operation_id=uuid4())
        return RestoreStage.objects.get(pk=result['result_id'])

    def test_picker_owner_actual_ready_files_and_cross_page_reuse(self):
        response=self.owner_client.get(self.path('media'))
        self.assertEqual(response.status_code,200)
        value=response.json();self.assertEqual(set(value),{'items','nextAfter'})
        self.assertEqual({row['assetId'] for row in value['items']},{str(self.a.pk),str(self.b.pk)})
        for row in value['items']:
            self.assertEqual(set(row),{'assetId','label','folder','mainFileId','previewFileId','mainUrl','previewUrl'})
            for key in ('mainUrl','previewUrl'):
                self.assertIn('/edit/media/picker-files/',row[key])
        self.commit({'main_image':self.ref(self.b)})
        self.assertEqual(PageRevision.objects.get(pk=self.current()).payload['main_image']['asset_id'],str(self.b.pk))

    def test_picker_main_preview_bytes_are_real_distinct_worker_outputs(self):
        self.assertNotEqual(MediaStorage().manifest(self.file(self.a).key)['sha256'],MediaStorage().manifest(self.file(self.b).key)['sha256'])
        for asset in (self.a,self.b):
            for kind in ('main','preview'):
                file=self.file(asset,kind)
                self.assert_image(self.owner_client.get(self.media_url(file,picker=True)),file)

    def test_picker_employee_visitor_and_private_source_closed(self):
        for client,status in ((self.employee_client,403),(self.other_client,403),(self.visitor,401)):
            self.assertEqual(client.get(self.path('media')).status_code,status)
            self.assertEqual(client.get(self.media_url(self.file(self.a),picker=True)).status_code,status)
        source=self.file(self.a,'private-source')
        self.assertEqual(self.owner_client.get(self.media_url(source,picker=True)).status_code,404)

    def test_picker_closed_query_and_boundary(self):
        for query in ('unknown=1','q=a&q=b','after=INVALID','folder=../../outside','q='+'x'*16385):
            with self.subTest(kind=query.split('=')[0]):
                self.assertEqual(self.owner_client.get(self.path('media')+'?'+query).status_code,400)

    def test_picker_pagination_51_actual_worker_uploads(self):
        for _ in range(49):self.upload('png',self.page)
        first=self.owner_client.get(self.path('media')).json()
        self.assertEqual(len(first['items']),50)
        self.assertTrue(first['nextAfter'])
        second=self.owner_client.get(self.path('media')+'?'+urlencode({'after':first['nextAfter']})).json()
        ids=[item['assetId'] for item in first['items']+second['items']]
        self.assertEqual(len(ids),51);self.assertEqual(len(set(ids)),51)

    def test_owner_main_preview_metadata_save_and_usage_slots(self):
        a=self.ref(self.a,alt='Alt 😀 & "quote"',alignment='left',width_px=120,height_px=80)
        b=self.ref(self.b,alignment='right')
        _,_,result=self.commit({'main_image':a,'preview_image':b})
        row=PageRevision.objects.get(pk=result['result_id'])
        self.assertEqual(row.payload['main_image'],a);self.assertEqual(row.payload['preview_image'],b)
        for slot,asset in (('main_image',self.a),('preview_image',self.b)):
            self.assertTrue(AssetUsage.objects.filter(kind='current_page',consumer_id=self.page.pk,slot=slot,asset=asset).exists())
            self.assertTrue(AssetUsage.objects.filter(kind='ordinary_version',consumer_id=row.pk,slot=slot,asset=asset).exists())

    def test_employee_media_keys_denied_even_unchanged_or_null(self):
        self.commit({'main_image':self.ref(self.a)})
        before=self.state()
        for changes in ({'main_image':self.ref(self.a)},{'preview_image':None}):
            response=self.send('check',self.payload(changes,baseRevisionId=str(self.current())),client=self.employee_client)
            self.assertEqual(response.status_code,403)
        self.assertEqual(self.state(),before)

    def test_current_context_membership_and_private_source(self):
        self.commit({'main_image':self.ref(self.a),'preview_image':self.ref(self.b)})
        for client in (self.owner_client,self.employee_client):
            for asset in (self.a,self.b):self.assert_image(client.get(self.media_url(self.file(asset))),self.file(asset))
        self.assertEqual(self.visitor.get(self.media_url(self.file(self.a))).status_code,401)
        self.assertEqual(self.other_client.get(self.media_url(self.file(self.a))).status_code,403)
        self.assertEqual(self.employee_client.get(self.media_url(self.file(self.b),page=self.page_b)).status_code,403)
        self.assertEqual(self.owner_client.get(self.media_url(self.file(self.a,'private-source'))).status_code,404)

    def test_initial_media_has_context_urls_without_employee_write_keys(self):
        self.commit({'main_image':self.ref(self.a),'preview_image':self.ref(self.b)})
        for client,owner in ((self.owner_client,True),(self.employee_client,False)):
            response=client.get(self.path(''))
            self.assertEqual(response.status_code,200)
            initial=response.context['initial_state']
            for field,asset in (('main_image',self.a),('preview_image',self.b)):
                self.assertEqual(initial['media'][field]['reference'],self.ref(asset))
                self.assertIn('/edit/media/files/',initial['media'][field]['url'])
                self.assertIn(str(self.file(asset,'preview').pk),initial['media'][field]['thumbnailUrl'])
                self.assertEqual(field in initial['values'],owner)

    def test_referenced_asset_cleanup_refuses_without_unlink(self):
        self.commit({'main_image':self.ref(self.a)})
        before=[MediaStorage().manifest(file.key) for file in self.a.files.order_by('key')]
        with self.assertRaisesMessage(ValidationError,'MEDIA_ASSET_RETAINED_OR_NOT_READY'):
            prepare_cleanup(actor=self.owner,asset_ids=[self.a.pk],expected_generation=1)
        self.assertEqual([MediaStorage().manifest(file.key) for file in self.a.files.order_by('key')],before)

    def test_unattached_picker_asset_does_not_grant_context_membership(self):
        self.assert_image(self.owner_client.get(self.media_url(self.file(self.a),picker=True)),self.file(self.a))
        self.assertEqual(self.owner_client.get(self.media_url(self.file(self.a))).status_code,404)
        self.assertEqual(self.employee_client.get(self.media_url(self.file(self.a))).status_code,404)

    def test_stable_old_asset_bytes_survive_owner_replace_and_null(self):
        _,_,first=self.commit({'main_image':self.ref(self.a),'preview_image':self.ref(self.a)})
        viewed=V.view_version(actor=self.owner,page_id=self.page.pk,version_id=first['result_id'],expected_generation=1)
        V.set_stable(actor=self.owner,page_id=self.page.pk,version_id=first['result_id'],view_receipt=viewed['view_receipt'],expected_generation=1,operation_id=uuid4())
        physical=[MediaStorage().manifest(file.key) for file in self.a.files.order_by('key')]
        self.commit({'main_image':self.ref(self.b),'preview_image':None})
        self.assertEqual([MediaStorage().manifest(file.key) for file in self.a.files.order_by('key')],physical)
        self.assertTrue(AssetUsage.objects.filter(kind='stable_version',consumer_id=first['result_id'],asset=self.a).exists())
        self.assertFalse(AssetUsage.objects.filter(kind='current_page',consumer_id=self.page.pk,asset=self.a).exists())

    def test_draft_context_uses_actual_private_reference(self):
        self.commit({'main_image':self.ref(self.a)})
        draft=self.draft();value,selector,_=self.checked({'main_image':self.ref(self.b)},draft=draft)
        current=self.current();response=self.send('draft',{**value,'rebase':False},selector=selector)
        self.assertEqual(response.status_code,200)
        selected=self.selector(draft=self.draft())
        self.assert_image(self.owner_client.get(self.media_url(self.file(self.b),selected)),self.file(self.b))
        self.assertEqual(self.employee_client.get(self.media_url(self.file(self.b),selected)).status_code,403)
        self.assertEqual(self.current(),current)

    def test_stage_owner_candidate_a_employee_candidate_b(self):
        _,_,historical=self.commit({'main_image':self.ref(self.a)})
        self.commit({'main_image':self.ref(self.b)})
        owner_stage=self.stage(self.owner,historical['result_id']);employee_stage=self.stage(self.employee,historical['result_id'])
        self.assert_image(self.owner_client.get(self.media_url(self.file(self.a),self.selector(stage=owner_stage))),self.file(self.a))
        self.assert_image(self.employee_client.get(self.media_url(self.file(self.b),self.selector(stage=employee_stage))),self.file(self.b))
        self.assertEqual(self.employee_client.get(self.media_url(self.file(self.a),self.selector(stage=employee_stage))).status_code,404)

    def test_check_typed_metadata_invalid_and_alt_boundary(self):
        valid=self.ref(self.a,alt='😀'*300,width_px=1,height_px=None)
        self.checked({'main_image':valid})
        before=self.state()
        for value in (self.ref(self.a,alt='😀'*301),self.ref(self.a,width_px=True),self.ref(self.a,width_px=0),
                      self.ref(self.a,height_px=-1),{**valid,'src':'https://outside.invalid/x'}):
            response=self.send('check',self.payload({'main_image':value},baseRevisionId=str(self.current())))
            self.assertEqual(response.status_code,400)
        self.assertEqual(self.state(),before)

    def test_media_changes_cannot_reuse_check_proof(self):
        value,selector,_=self.checked({'main_image':self.ref(self.a)})
        value['changes']['main_image']=self.ref(self.b)
        before=self.state();response=self.send('save',value,selector=selector)
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.state(),before)

    def test_exact_permanent_replay_precedes_new_file_availability(self):
        value,selector,result=self.commit({'main_image':self.ref(self.a)})
        path=self.physical(self.file(self.a));data=path.read_bytes();path.unlink()
        try:
            before=self.state();audit=AuditEvent.objects.count();response=self.send('save',value,selector=selector)
            self.assertEqual(response.status_code,200);self.assertTrue(response.json()['replay'])
            self.assertEqual(response.json()['result_id'],result['result_id'])
            self.assertEqual(self.state(),before);self.assertEqual(AuditEvent.objects.count(),audit)
        finally:path.write_bytes(data)

    def test_missing_retained_image_text_only_check_has_no_proof(self):
        self.commit({'main_image':self.ref(self.a)})
        path=self.physical(self.file(self.a));data=path.read_bytes();path.unlink()
        try:
            before=self.state();response=self.send('check',self.payload({'main_text':'<p>TEXT ONLY</p>'},baseRevisionId=str(self.current())))
            self.assertEqual(response.status_code,409);self.assertEqual(response.json()['code'],'EDITOR_MEDIA_UNAVAILABLE');self.assertNotIn('checkReceipt',response.json());self.assertEqual(self.state(),before)
        finally:path.write_bytes(data)

    def test_corrupt_retained_preview_refuses_verified_context_bytes(self):
        self.commit({'preview_image':self.ref(self.a)})
        file=self.file(self.a,'preview');path=self.physical(file);data=path.read_bytes();path.write_bytes(data[:-1]+bytes([data[-1]^255]))
        try:
            response=self.owner_client.get(self.media_url(file))
            self.assertEqual(response.status_code,404)
        finally:path.write_bytes(data)

    def test_late_context_grant_revoke_closes_verified_file(self):
        self.commit({'main_image':self.ref(self.a)})
        actual=MediaStorage.open_verified;opened=[]
        def revoke(storage,*args,**kwargs):
            file=actual(storage,*args,**kwargs);opened.append(file)
            set_grant(actor=self.owner,employee=self.employee,page=self.page,revoke=True)
            return file
        with patch('media_library.storage.MediaStorage.open_verified',new=revoke):
            response=self.employee_client.get(self.media_url(self.file(self.a)))
        self.assertEqual(response.status_code,403);self.assertTrue(opened);self.assertTrue(all(file.closed for file in opened))

    def test_late_picker_session_revoke_closes_verified_file(self):
        actual=MediaStorage.open_verified;opened=[];key=self.owner_client.session.session_key
        def revoke(storage,*args,**kwargs):
            file=actual(storage,*args,**kwargs);opened.append(file);AuthSession.objects.filter(pk=key).delete();return file
        with patch('media_library.storage.MediaStorage.open_verified',new=revoke):
            response=self.owner_client.get(self.media_url(self.file(self.a),picker=True))
        self.assertEqual(response.status_code,401);self.assertTrue(opened);self.assertTrue(all(file.closed for file in opened))

    def test_actual_media_commit_post_ledger_fault_rolls_back_refs_and_bytes(self):
        value,selector,_=self.checked({'main_image':self.ref(self.a),'preview_image':self.ref(self.b)})
        before=self.state();audit=AuditEvent.objects.count();actual=E.finish
        manifests=[MediaStorage().manifest(file.key) for file in AssetFile.objects.order_by('id')]
        def fault(*args,**kwargs):
            actual(*args,**kwargs);raise DatabaseError('synthetic media post-ledger fault')
        with patch('page_versions.engine.finish',side_effect=fault):response=self.send('save',value,selector=selector)
        self.assertEqual(response.status_code,503);self.assertEqual(self.state(),before);self.assertEqual(AuditEvent.objects.count(),audit)
        self.assertEqual([MediaStorage().manifest(file.key) for file in AssetFile.objects.order_by('id')],manifests)
