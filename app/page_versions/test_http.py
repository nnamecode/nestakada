"""Real sessions/CSRF/PG HTTP checks; codec and browser proof are separate QA."""
from tempfile import TemporaryDirectory
from urllib.parse import urlencode
from uuid import uuid4
from django.conf import settings
from django.test import Client,TransactionTestCase,override_settings
from django.urls import reverse
from accounts.services import bootstrap_owner,create_employee,set_grant
from audit.models import AuditEvent
from content.models import Page,Route
from . import services as V,schema as S
from .models import PageRevision,PageContentState,RestoreStage,OperationReceipt,VersionBasePin

PASSWORD='Versions-http-owner-current-password'
EMPLOYEE_PASSWORD='Versions-http-employee-password'


@override_settings(AUTH_TRUSTED_PROXY_HOST=None,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class VersionHttpTests(TransactionTestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        setting=override_settings(MEDIA_LIBRARY_ROOT=self.temp.name);setting.enable();self.addCleanup(setting.disable)
        self.owner=bootstrap_owner(PASSWORD)
        self.employee=create_employee(actor=self.owner,username='version-http-employee',password=EMPLOYEE_PASSWORD)
        self.other=create_employee(actor=self.owner,username='version-http-other',password=EMPLOYEE_PASSWORD)
        self.page=Page.objects.create(kind=Page.Kind.ARTICLE,name='HTTP history')
        Route.objects.create(page=self.page,kind=Route.Kind.PRIMARY,target='/version-http/')
        set_grant(actor=self.owner,employee=self.employee,page=self.page,main_text=True)
        self.initial=V.initialize(actor=self.owner,page_id=self.page.pk,snapshot=S.snapshot_v1(self.page.kind,main_text='<p>saved</p><script>PRIVATE_SCRIPT_CANARY</script>{{ not_a_template }}',h1='Protected heading'),expected_generation=1,operation_id=uuid4())['result_id']
        self.owner_client=self.login('nesadmin',PASSWORD)
        self.employee_client=self.login(self.employee.username,EMPLOYEE_PASSWORD)
        self.other_client=self.login(self.other.username,EMPLOYEE_PASSWORD)
        self.visitor=Client(enforce_csrf_checks=True,HTTP_HOST='localhost')

    def login(self,username,password):
        client=Client(enforce_csrf_checks=True,HTTP_HOST='localhost');self.assertEqual(client.get('/manage/login/').status_code,200)
        self.assertEqual(self.post(client,'/manage/login/',{'username':username,'password':password}).status_code,303)
        return client

    def post(self,client,url,values,csrf=True):
        data=dict(values)
        if csrf:data['csrfmiddlewaretoken']=client.cookies[settings.CSRF_COOKIE_NAME].value
        return client.post(url,urlencode(data),content_type='application/x-www-form-urlencoded')

    def url(self,name,version=None):
        args=[self.page.pk]
        if version is not None:args.append(version)
        return reverse('page_versions:'+name,args=args)

    def current(self):return PageContentState.objects.get(page=self.page).current_revision_id

    def test_closed_history_roles_draft_privacy_and_escaped_read(self):
        V.save_owner_draft(actor=self.owner,page_id=self.page.pk,base_revision=self.initial,snapshot=S.snapshot_v1(self.page.kind,main_text='OWNER_DRAFT_SECRET_CANARY'),expected_generation=1,operation_id=uuid4())
        count=PageRevision.objects.count()
        for name in ['history','read','compare']:
            url=self.url(name,None if name=='history' else self.initial)
            for client in [self.owner_client,self.employee_client]:
                response=client.get(url);self.assertEqual(response.status_code,200)
                self.assertIn('no-store',response['Cache-Control']);self.assertIn('Cookie',response['Vary'])
                self.assertNotContains(response,'OWNER_DRAFT_SECRET_CANARY');self.assertNotContains(response,'<script>PRIVATE_SCRIPT_CANARY</script>')
            self.assertEqual(self.other_client.get(url).status_code,403);self.assertEqual(self.visitor.get(url).status_code,401)
        read=self.employee_client.get(self.url('read',self.initial))
        self.assertContains(read,'&lt;script&gt;PRIVATE_SCRIPT_CANARY&lt;/script&gt;');self.assertContains(read,'{{ not_a_template }}')
        self.assertEqual(self.employee_client.get(self.url('owner_draft')).status_code,403)
        self.assertEqual(self.owner_client.get(self.url('owner_draft')).status_code,200)
        self.assertEqual(PageRevision.objects.count(),count);self.assertEqual(str(self.current()),self.initial)
        for row in V.history(actor=self.owner,page_id=self.page.pk,expected_generation=1)['rows']:
            self.assertIn('payload',row['revision'].get_deferred_fields())

    def test_manual_csrf_replay_changed_input_and_source_not_draft(self):
        prepared=self.owner_client.get(self.url('manual_prepare'));self.assertEqual(prepared.status_code,200)
        self.assertContains(prepared,f'data-manual-source="{self.initial}"')
        values={'generation':1,'operation_id':uuid4(),'confirmation':prepared.context['prepared']['confirmation'],'name':'HTTP manual','comment':'line1\r\nline2','manual_date':'1960-01-02T03:04:05+03:00'}
        url=self.url('manual_create');before=PageRevision.objects.count()
        self.assertEqual(self.post(self.owner_client,url,values,csrf=False).status_code,403)
        self.assertEqual(self.post(self.employee_client,url,values).status_code,403)
        created=self.post(self.owner_client,url,values);self.assertEqual(created.status_code,200)
        result=created.context['result'];self.assertEqual(PageRevision.objects.count(),before+1)
        copied=PageRevision.objects.get(pk=result['result_id']);self.assertEqual(copied.payload,PageRevision.objects.get(pk=self.initial).payload)
        self.assertEqual(copied.metadata.comment,'line1\nline2');self.assertEqual(copied.metadata.manual_date.year,1960)
        self.assertEqual(str(self.current()),self.initial)
        replay=self.post(self.owner_client,url,values);self.assertEqual(replay.status_code,200);self.assertTrue(replay.context['result']['replay'])
        self.assertEqual(self.post(self.owner_client,url,{**values,'name':'changed'}).status_code,409)
        self.assertEqual(PageRevision.objects.count(),before+1)

    def test_denied_authenticated_requests_aggregate_without_per_request_audit(self):
        before=AuditEvent.objects.filter(code='SEC_PERMISSION_DENIED').count()
        for _ in range(3):self.assertEqual(self.other_client.get(self.url('history')).status_code,403)
        self.assertEqual(AuditEvent.objects.filter(code='SEC_PERMISSION_DENIED').count(),before+1)
        before=AuditEvent.objects.count()
        for _ in range(3):self.assertEqual(self.visitor.get(self.url('history')).status_code,401)
        self.assertEqual(AuditEvent.objects.count(),before)

    def test_manual_metadata_success_message_and_exact_delete_identity_escaped(self):
        prepared=V.prepare_manual(actor=self.owner,page_id=self.page.pk,expected_generation=1)
        result=V.create_manual(actor=self.owner,page_id=self.page.pk,confirmation=prepared['confirmation'],expected_generation=1,operation_id=uuid4(),name='Manual <script>name</script>')
        version=result['result_id'];row=PageRevision.objects.get(pk=version)
        response=self.post(self.owner_client,self.url('metadata_edit',version),{'generation':1,'operation_id':uuid4(),'metadata_generation':row.metadata.generation,'name':'Edited <b>name</b>','comment':'edited','manual_date':'2099-01-02T00:00:00+03:00'})
        self.assertEqual(response.status_code,200);self.assertContains(response,'Сведения о ручной версии сохранены')
        unchanged=PageRevision.objects.get(pk=version);self.assertEqual(unchanged.created_at,row.created_at);self.assertEqual(unchanged.author_id,row.author_id)
        self.page.name='Page <b>name</b>';self.page.save()
        confirmation=self.owner_client.get(self.url('delete_prepare',version));self.assertEqual(confirmation.status_code,200)
        self.assertContains(confirmation,'Page &lt;b&gt;name&lt;/b&gt;');self.assertContains(confirmation,'/version-http/')
        self.assertContains(confirmation,'data-delete-kind');self.assertContains(confirmation,str(version));self.assertContains(confirmation,'Edited &lt;b&gt;name&lt;/b&gt;')
        self.assertNotContains(confirmation,'<b>name</b>')

    def test_stable_requires_exact_view_owner_and_repeated_current_password(self):
        viewed=self.owner_client.get(self.url('read',self.initial));proof=viewed.context['view_receipt']
        values={'generation':1,'operation_id':uuid4(),'view_receipt':proof}
        self.assertEqual(self.post(self.employee_client,self.url('stable_set',self.initial),values).status_code,403)
        self.assertEqual(self.post(self.owner_client,self.url('stable_set',self.initial),values).status_code,200)
        prepared=self.owner_client.get(self.url('demote_prepare',self.initial));self.assertEqual(prepared.status_code,200)
        data={'generation':1,'operation_id':uuid4(),'confirmation':prepared.context['prepared']['confirmation'],'password':'incorrect-private-password'}
        failed=self.post(self.owner_client,self.url('demote',self.initial),data)
        self.assertEqual(failed.status_code,403);self.assertNotContains(failed,data['password'],status_code=403)
        data['password']=PASSWORD;self.assertEqual(self.post(self.owner_client,self.url('demote',self.initial),data).status_code,200)
        self.assertEqual(self.post(self.owner_client,self.url('demote',self.initial),{**data,'password':'wrong-on-replay'}).status_code,403)
        self.assertNotIn(PASSWORD,str(list(OperationReceipt.objects.values())))

    def prepare_stage(self):
        response=self.post(self.employee_client,self.url('restore_prepare',self.initial),{'generation':1})
        self.assertEqual(response.status_code,200)
        data={'generation':1,'operation_id':uuid4(),'preparation':response.context['prepared']['preparation'],'confirm_input_replacement':'yes'}
        staged=self.post(self.employee_client,self.url('restore_stage',self.initial),data);self.assertEqual(staged.status_code,200)
        return data,staged.context['prepared']['stage']

    def test_restore_stage_cancel_then_replay_has_terminal_receipt_without_payload(self):
        before=PageRevision.objects.count();data,stage=self.prepare_stage()
        self.assertEqual(PageRevision.objects.count(),before);self.assertEqual(str(self.current()),self.initial)
        cancel=reverse('page_versions:stage_cancel',args=[self.page.pk,stage.pk])
        self.assertEqual(self.post(self.employee_client,cancel,{'generation':1,'operation_id':uuid4()}).status_code,200)
        replay=self.post(self.employee_client,self.url('restore_stage',self.initial),data)
        self.assertEqual(replay.status_code,200);self.assertContains(replay,'data-stage-status="released"')
        self.assertTrue(replay.context['result']['replay']);self.assertNotContains(replay,'data-stage-field')
        self.assertEqual(RestoreStage.objects.count(),1);self.assertFalse(VersionBasePin.objects.filter(holder_id=stage.pk).exists())

    def test_restore_stage_current_change_then_replay_has_invalidated_receipt(self):
        data,stage=self.prepare_stage()
        V.commit_owner(actor=self.owner,page_id=self.page.pk,base_revision=self.current(),snapshot=S.snapshot_v1(self.page.kind,main_text='new owner current'),expected_generation=1,operation_id=uuid4())
        before=PageRevision.objects.count();replay=self.post(self.employee_client,self.url('restore_stage',self.initial),data)
        self.assertEqual(replay.status_code,200);self.assertContains(replay,'data-stage-status="invalidated"')
        self.assertNotContains(replay,'data-stage-field');self.assertEqual(PageRevision.objects.count(),before);self.assertEqual(RestoreStage.objects.count(),1)

    def test_unexpected_payload_and_missing_explicit_restore_confirmation_are_rejected(self):
        response=self.post(self.employee_client,self.url('restore_prepare',self.initial),{'generation':1,'payload':'arbitrary'})
        self.assertEqual(response.status_code,400)
        prepared=self.post(self.employee_client,self.url('restore_prepare',self.initial),{'generation':1})
        response=self.post(self.employee_client,self.url('restore_stage',self.initial),{'generation':1,'operation_id':uuid4(),'preparation':prepared.context['prepared']['preparation']})
        self.assertEqual(response.status_code,409);self.assertEqual(RestoreStage.objects.count(),0)
        self.assertEqual(self.post(self.owner_client,self.url('read',self.initial),{}).status_code,405)
