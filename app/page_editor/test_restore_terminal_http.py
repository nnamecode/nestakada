"""RST-001..006 real PG/child/forms; existing selected-source errors, no new DTO."""
from copy import deepcopy
from urllib.parse import urlencode
from uuid import uuid4

from django.conf import settings
from django.test import TransactionTestCase, override_settings
from accounts.services import set_grant
from audit.models import AuditEvent
from page_versions import services as V, schema as S
from page_versions.models import PageRevision, PageContentState, OwnerDraft, RestoreStage, VersionBasePin
from . import test_check_http as H, test_draft_restore_http as D, test_media_http as M


@override_settings(ROOT_URLCONF='page_editor.test_check_http', MIDDLEWARE=H.TEST_MIDDLEWARE,
    TEMPLATES=M.TEST_TEMPLATES, AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RestoreTerminalHttpTests(TransactionTestCase):
    setUp=H.EditorCheckHttpTests.setUp
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

    canary='RST-SOURCE-CANDIDATE-é-PRIVATE'

    def commit(self, marker):
        current=PageRevision.objects.get(pk=self.current())
        payload=deepcopy(current.payload);payload['main_text']='<p>'+marker+'</p>'
        return V.commit_owner(actor=self.owner,page_id=self.page.pk,base_revision=current.pk,
            snapshot=S.Snapshot.trusted(payload,self.page.kind),expected_generation=1,operation_id=uuid4())

    def form_post(self, client, path, body):
        return client.post(path,data=urlencode(body),content_type='application/x-www-form-urlencoded')

    def make_stage(self, actor=None, client=None, source=None):
        actor,client=actor or self.employee,client or self.employee_client
        if source is None:
            source=self.commit(self.canary)['result_id']
            self.commit('RST-CURRENT-PUBLISHED')
        prepared=V.prepare_restore(actor=actor,page_id=self.page.pk,version_id=source,expected_generation=1)
        path='/manage/pages/%s/versions/%s/restore/stage/'%(self.page.pk,source)
        body={'generation':'1','operation_id':str(uuid4()),'preparation':prepared['preparation'],
              'confirm_input_replacement':'yes',
              'csrfmiddlewaretoken':client.cookies[settings.CSRF_COOKIE_NAME].value}
        result=V.stage_restore(
            actor=actor,page_id=self.page.pk,
            preparation=prepared['preparation'],confirm_input_replacement=True,
            expected_generation=1,operation_id=body['operation_id'])
        stage=RestoreStage.objects.get(pk=result['result_id'])
        return {'stage':stage,'path':path,'body':body,'source':source,'client':client}

    def domain(self):
        return self.state(),AuditEvent.objects.filter(code__startswith='VERSION_').count()

    def selected_denied(self, item, checked_value, *, client=None,
                        save_status=409, save_code='EDITOR_BASE_UNAVAILABLE'):
        client=client or item['client'];stage=item['stage'];selector=self.selector(stage=stage)
        before=self.domain()
        for action in ('','state'):
            response=client.get(self.path(action,selector))
            self.assertEqual(response.status_code,409)
            self.assertEqual(response.json()['code'],'EDITOR_BASE_UNAVAILABLE')
            self.assertNotIn(self.canary.encode(),response.content)
            self.assertNotIn('checkReceipt',response.json())
        checked=self.send('check',checked_value,selector=selector,client=client)
        self.assertEqual(checked.status_code,409)
        self.assertEqual(checked.json()['code'],'EDITOR_BASE_UNAVAILABLE')
        self.assertNotIn('checkReceipt',checked.json())
        fresh={**checked_value,'operationId':str(uuid4())}
        refused=self.send('save',fresh,selector=selector,client=client)
        self.assertEqual(refused.status_code,save_status)
        self.assertEqual(refused.json()['code'],save_code)
        self.assertNotIn('result_id',refused.json());self.assertNotIn('checkReceipt',refused.json())
        self.assertNotIn(self.canary.encode(),refused.content)
        self.assertEqual(self.domain(),before)

    def stage_replay(self, item, status):
        before=self.domain()
        replay=self.form_post(item['client'],item['path'],item['body'])
        self.assertEqual(replay.status_code,200)
        self.assertEqual(replay.context['terminal_status'],status)
        self.assertTrue(replay.context['result']['replay'])
        self.assertEqual(replay.context['result']['result_id'],str(item['stage'].pk))
        with self.assertRaises(KeyError):replay.context['prepared']
        with self.assertRaises(KeyError):replay.context['fields']
        self.assertNotContains(replay,'data-restore-editor')
        self.assertNotContains(replay,'data-stage-field')
        self.assertNotContains(replay,self.canary)
        self.assertIn('no-store',replay['Cache-Control'])
        self.assertEqual(self.domain(),before)

    def test_rst001_held_positive_reads_check_preserve_current_and_source_base_pins(self):
        item=self.make_stage();stage=item['stage'];before=self.domain()
        response=self.employee_client.get(self.path('',self.selector(stage=stage)))
        self.assertEqual(response.status_code,200)
        self.assertIn(self.canary,response.context['initial_state']['values']['main_text'])
        self.checked({'intro_text':'','main_text':'<p>RST-HELD-RAM</p>'},stage=stage,client=self.employee_client)
        pins=set(VersionBasePin.objects.filter(holder_kind='restore_stage',holder_id=stage.pk).values_list('revision_id',flat=True))
        self.assertEqual(pins,{stage.source_revision_id,stage.base_revision_id})
        self.assertEqual(self.domain(),before)

    def test_rst002_release_cancel_exact_replay_and_original_stage_receipt_are_distinct(self):
        item=self.make_stage();stage=item['stage']
        value,selector,_=self.checked({'intro_text':'','main_text':'<p>RST-CANCELLED-RAM</p>'},stage=stage,client=self.employee_client)
        body={'generation':'1','operation_id':str(uuid4()),
              'csrfmiddlewaretoken':self.employee_client.cookies[settings.CSRF_COOKIE_NAME].value}
        path='/manage/pages/%s/versions/stages/%s/cancel/'%(self.page.pk,stage.pk)
        cancelled=self.form_post(self.employee_client,path,body)
        self.assertEqual(cancelled.status_code,200)
        stage.refresh_from_db();self.assertEqual(stage.status,'released')
        self.assertFalse(VersionBasePin.objects.filter(holder_kind='restore_stage',holder_id=stage.pk).exists())
        before=self.domain()
        repeated=self.form_post(self.employee_client,path,body)
        self.assertEqual(repeated.status_code,200)
        self.assertEqual(repeated.context['result']['action'],'cancel_stage')
        self.assertTrue(repeated.context['result']['replay'])
        self.assertEqual(self.domain(),before)
        self.selected_denied(item,value)
        self.stage_replay(item,'released')

    def test_rst003_consumed_stage_selected_denial_exact_save_replay_no_new_operation(self):
        item=self.make_stage();stage=item['stage']
        value,selector,_=self.checked({'intro_text':'','main_text':'<p>RST-EDITED-APPLY</p>'},stage=stage,client=self.employee_client)
        saved=self.send('save',value,selector=selector,client=self.employee_client)
        self.assertEqual(saved.status_code,200)
        result=saved.json();row=PageRevision.objects.get(pk=result['result_id'])
        self.assertEqual(row.source_revision_id,stage.source_revision_id)
        self.assertEqual(row.payload['main_text'],'<p>RST-EDITED-APPLY</p>')
        stage.refresh_from_db();self.assertEqual(stage.status,'consumed')
        self.assertFalse(VersionBasePin.objects.filter(holder_id=stage.pk).exists())
        before=self.domain()
        replay=self.send('save',value,selector=selector,client=self.employee_client)
        self.assertEqual(replay.status_code,200);self.assertTrue(replay.json()['replay'])
        self.assertEqual(replay.json()['result_id'],result['result_id']);self.assertEqual(self.domain(),before)
        self.selected_denied(item,value)
        self.stage_replay(item,'consumed')

    def test_rst004_actual_current_commit_invalidates_stage_without_dropping_owner_draft_pin(self):
        item=self.make_stage();stage=item['stage'];draft=self.draft()
        draft_before=list(OwnerDraft.objects.filter(pk=draft.pk).values())
        pins_before=list(VersionBasePin.objects.filter(holder_kind='owner_draft',holder_id=draft.pk).values())
        value,_,_=self.checked({'intro_text':'','main_text':'<p>RST-STALE</p>'},stage=stage,client=self.employee_client)
        self.commit('RST-REAL-CURRENT-COMPETITOR')
        stage.refresh_from_db();self.assertEqual(stage.status,'invalidated')
        self.assertEqual(stage.terminal_reason,'CURRENT_CHANGED')
        self.assertFalse(VersionBasePin.objects.filter(holder_kind='restore_stage',holder_id=stage.pk).exists())
        self.assertEqual(list(OwnerDraft.objects.filter(pk=draft.pk).values()),draft_before)
        self.assertEqual(list(VersionBasePin.objects.filter(holder_kind='owner_draft',holder_id=draft.pk).values()),pins_before)
        self.selected_denied(item,value);self.stage_replay(item,'invalidated')

    def test_rst005_grant_stale_read_is_not_cleanup_exact_restore_preserves_same_basis(self):
        item=self.make_stage();stage=item['stage']
        value,_,_=self.checked({'intro_text':'','main_text':'<p>RST-GRANT-RAM</p>'},stage=stage,client=self.employee_client)
        before_pins=list(VersionBasePin.objects.filter(holder_id=stage.pk).order_by('id').values())
        before_basis=(stage.source_revision_id,stage.base_revision_id)
        set_grant(actor=self.owner,employee=self.employee,page=self.page,intro_text=True,main_text=False)
        self.employee_client=self.login(self.employee.username,H.EMPLOYEE_PASSWORD)
        item['client']=self.employee_client
        self.selected_denied(item,value,save_status=403,save_code='EDITOR_FIELDS_FORBIDDEN')
        stage.refresh_from_db();self.assertEqual(stage.status,'held')
        self.assertEqual(list(VersionBasePin.objects.filter(holder_id=stage.pk).order_by('id').values()),before_pins)
        set_grant(actor=self.owner,employee=self.employee,page=self.page,intro_text=True,main_text=True)
        self.employee_client=self.login(self.employee.username,H.EMPLOYEE_PASSWORD)
        item['client']=self.employee_client
        self.stage_replay(item,'stale')
        before=self.domain()
        restored=self.employee_client.get(self.path('state',self.selector(stage=stage)))
        self.assertEqual(restored.status_code,200)
        stage.refresh_from_db();self.assertEqual((stage.source_revision_id,stage.base_revision_id),before_basis)
        self.assertEqual(stage.status,'held');self.assertEqual(self.domain(),before)
        self.commit('RST-AFTER-GRANT-RESTORE-CURRENT')
        stage.refresh_from_db();self.assertEqual(stage.status,'invalidated')
        self.assertFalse(VersionBasePin.objects.filter(holder_id=stage.pk).exists())

    def test_rst006_same_page_same_grants_and_owner_cannot_read_apply_cancel_foreign_stage(self):
        set_grant(actor=self.owner,employee=self.other,page=self.page,intro_text=True,main_text=True)
        item=self.make_stage();stage=item['stage']
        value,_,_=self.checked({'intro_text':'','main_text':'<p>RST-ACTOR-RAM</p>'},stage=stage,client=self.employee_client)
        own=self.make_stage(actor=self.owner,client=self.owner_client,source=item['source'])
        self.assertEqual(self.owner_client.get(self.path('state',self.selector(stage=own['stage']))).status_code,200)
        own_other=self.make_stage(actor=self.other,client=self.other_client,source=item['source'])
        self.assertEqual(self.other_client.get(self.path('state',self.selector(stage=own_other['stage']))).status_code,200)
        for client in (self.other_client,self.owner_client):
            before=self.domain()
            self.assertEqual(client.get(self.path('state')).status_code,200)
            self.selected_denied(item,value,client=client)
            cancelled=self.form_post(client,'/manage/pages/%s/versions/stages/%s/cancel/'%(self.page.pk,stage.pk),
                {'generation':'1','operation_id':str(uuid4()),'csrfmiddlewaretoken':client.cookies[settings.CSRF_COOKIE_NAME].value})
            self.assertEqual(cancelled.status_code,403)
            self.assertEqual(self.domain(),before)
        stage.refresh_from_db();self.assertEqual(stage.status,'held')
