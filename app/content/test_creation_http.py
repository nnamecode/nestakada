"""CP29: actual forms/CSRF, real editor child and commit/confirmation boundary."""
import json
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit, parse_qs
from uuid import uuid4
from django.db import connection, DatabaseError
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from accounts import services as auth
from accounts.tests import PASSWORD, FAST_HASHERS, client, login
from page_versions import engine
from page_versions.models import (PageRevision, PageContentState, OwnerDraft,
                                 OperationReceipt, IdentityReservation)
from audit.models import AuditEvent
from . import creation, simple_creation
from .models import Page


@override_settings(PASSWORD_HASHERS=FAST_HASHERS, AUTH_TRUSTED_PROXY_HOST=None,
                   DEV29_LOCAL_CREATE_ENABLED=True, ENVIRONMENT='test')
class CreationHttpTests(TransactionTestCase):
    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        self.employee = auth.create_employee(actor=self.owner, username='auth-employee', password=PASSWORD)
        self.browser = client(csrf=True)
        self.browser.get('/manage/login/')
        self.assertEqual(login(self.browser, 'nesadmin', HTTP_X_CSRFTOKEN=self.browser.cookies['estakada_test_csrf'].value).status_code, 303)
        self.url = reverse('accounts:page-create')
        self.temp = TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        media = override_settings(MEDIA_LIBRARY_ROOT=self.temp.name);media.enable();self.addCleanup(media.disable)

    def post(self, values, browser=None, csrf=True):
        browser = browser or self.browser
        headers = {'HTTP_X_CSRFTOKEN': browser.cookies['estakada_test_csrf'].value} if csrf else {}
        return browser.post(self.url, data=urlencode(values), content_type='application/x-www-form-urlencoded', **headers)

    def proof(self, kind='article'):
        response = self.browser.get(self.url, {'kind': kind})
        self.assertEqual(response.status_code, 200)
        return {key:response.context['values'][key] for key in ('token','operation_id','page_id','parent_id','kind')}

    def values(self, proof, **extra):
        return {**proof, 'parent_id':proof['parent_id'] or '', 'name':'Новая страница', 'url':'/new-page/',
                'h1':'Заголовок', 'title':'Название', 'step':'save', **extra}

    def test_preview_is_readonly_and_preserves_explicit_empty_metadata(self):
        proof=self.proof();before=(Page.objects.count(),PageRevision.objects.count(),OperationReceipt.objects.count())
        first=self.post({**proof,'parent_id':'','name':'Ремонт ёмкости','url':'','step':'preview'})
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.context['values']['url'],'/remont-yomkosti/')
        self.assertEqual(first.context['values']['h1'],'Ремонт ёмкости')
        values=first.context['values'];values.update(h1='',title='',url='/manual/',step='preview')
        again=self.post(values)
        self.assertEqual(again.status_code,200)
        self.assertEqual(again.context['values']['h1'],'')
        self.assertEqual(again.context['values']['title'],'')
        self.assertEqual(again.context['values']['url'],'/manual/')
        self.assertEqual(before,(Page.objects.count(),PageRevision.objects.count(),OperationReceipt.objects.count()))

    def test_real_forms_create_replay_and_stale_keep_original_input(self):
        proof=self.proof();stale=self.proof()
        values=self.values(proof)
        created=self.post(values);self.assertEqual(created.status_code,303)
        self.assertEqual(created['X-Tree-Result'],'applied')
        self.assertEqual(urlsplit(created['Location']).path,reverse('page_editor:editor',kwargs={'page_id':proof['page_id']}))
        self.assertEqual(parse_qs(urlsplit(created['Location']).query)['source'],['owner-draft'])
        self.assertEqual(self.post(values)['X-Tree-Result'],'replay')
        conflict=self.post(self.values(stale,name='НЕСОХРАНЁННЫЙ ВВОД',url='/other/'))
        self.assertEqual(conflict.status_code,409)
        self.assertEqual(conflict.context['values']['token'],stale['token'])
        self.assertEqual(conflict.context['values']['operation_id'],stale['operation_id'])
        self.assertContains(conflict,'НЕСОХРАНЁННЫЙ ВВОД',status_code=409)
        self.assertEqual(conflict['Cache-Control'],'private, no-store')
        self.assertIn('Cookie',conflict['Vary'])

    def test_disabled_and_employee_csrf_and_bad_fields_do_not_create(self):
        proof=self.proof();values=self.values(proof)
        self.assertEqual(self.post(values,csrf=False).status_code,403)
        self.assertEqual(self.post({**values,'is_published':'1'}).status_code,400)
        self.assertEqual(self.post({**values,'kind':'home'}).status_code,400)
        other=client();self.assertEqual(login(other,'auth-employee').status_code,303)
        self.assertEqual(other.get(self.url).status_code,403)
        self.assertEqual(self.post(values,browser=other).status_code,403)
        with override_settings(DEV29_LOCAL_CREATE_ENABLED=False):
            self.assertEqual(self.browser.get(self.url).status_code,503)
            self.assertEqual(self.post(values).status_code,503)
        self.assertEqual(Page.objects.count(),0)
        self.assertEqual(OperationReceipt.objects.filter(action='tree_create').count(),0)

    def test_combined_unicode_metadata_transport_and_scalar_multiplicity(self):
        proof=self.proof();values=self.values(proof,name='😀'*200,h1='😀'*255,title='😀'*255,
            url='/'+('/'.join(['a']*1023))+'/')
        self.assertLessEqual(len(urlencode(values).encode()),16384)
        self.assertEqual(self.post(values).status_code,303)
        self.assertEqual(Page.objects.get(pk=proof['page_id']).name,'😀'*200)
        duplicate=urlencode(self.values(self.proof(),url='/duplicate/'))+'&name=other'
        response=self.browser.post(self.url,data=duplicate,content_type='application/x-www-form-urlencoded',
            HTTP_X_CSRFTOKEN=self.browser.cookies['estakada_test_csrf'].value)
        self.assertEqual(response.status_code,400)
        self.assertEqual(Page.objects.count(),1)

    def test_uncertain_confirmation_after_independently_observed_commit_exact_retry(self):
        proof=self.proof();values=self.values(proof);original=simple_creation.apply
        def lost(**kwargs):
            original(**kwargs)
            self.assertFalse(connection.in_atomic_block)
            import psycopg
            options=connection.get_connection_params()
            options.pop('cursor_factory',None);options.pop('context',None);options.pop('prepare_threshold',None)
            with psycopg.connect(**options) as observer:
                self.assertEqual(observer.execute('SELECT count(*) FROM app.content_page WHERE id=%s',
                    [proof['page_id']]).fetchone()[0],1)
                self.assertEqual(observer.execute('SELECT count(*) FROM app.page_versions_operationreceipt WHERE id=%s',
                    [proof['operation_id']]).fetchone()[0],0)
            raise DatabaseError('synthetic confirmation loss')
        with patch('content.creation_views.simple.apply',side_effect=lost):
            response=self.post(values)
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.context['values']['token'],proof['token'])
        self.assertEqual(self.post(values)['X-Tree-Result'],'replay')
        self.assertEqual(Page.objects.count(),1)
        self.assertEqual(PageRevision.objects.count(),1)
        self.assertEqual(OwnerDraft.objects.count(),1)

    def test_all_types_open_existing_editor_and_save_text_while_hidden(self):
        for index,kind in enumerate(creation.KINDS):
            with self.subTest(kind=kind):
                proof=self.proof(kind);response=self.post(self.values(proof,url=f'/created-{index}/'))
                self.assertEqual(response.status_code,303)
                page=Page.objects.get(pk=proof['page_id'])
                opened=self.browser.get(response['Location']);self.assertEqual(opened.status_code,200)
                state=PageContentState.objects.get(page=page)
                draft=OwnerDraft.objects.get(page=page)
                selector=urlencode({'source':'owner-draft','draftId':str(draft.pk),'draftRevision':draft.revision})
                payload={'protocol':'page-editor-v1','generation':1,'baseRevisionId':str(draft.base_revision_id),
                    'editingFrom':'owner-draft','draftBasis':{'id':str(draft.pk),'revision':draft.revision},
                    'stageId':None,'changes':{'main_text':'<p>Новый текст</p>'}}
                headers={'HTTP_X_CSRFTOKEN':self.browser.cookies['estakada_test_csrf'].value}
                def selected_request(action,body):
                    with patch('page_editor.views.read_json_bytes',side_effect=lambda req,profile:req.body):
                        return self.browser.post(reverse('page_editor:'+action,kwargs={'page_id':page.pk})+'?'+selector,
                            data=json.dumps(body,ensure_ascii=False).encode(),content_type='application/json',**headers)
                checked=selected_request('check',payload);self.assertEqual(checked.status_code,200)
                saved=selected_request('draft',{**payload,'rebase':False,'changes':checked.json()['normalisedChanges'],
                    'checkReceipt':checked.json()['checkReceipt'],'operationId':str(uuid4())})
                self.assertEqual(saved.status_code,200,saved.content.decode())
                draft.refresh_from_db();self.assertEqual(draft.payload['main_text'],'<p>Новый текст</p>')
                self.assertEqual(PageContentState.objects.get(page=page).current_revision_id,state.current_revision_id)
                replay=self.post(self.values(proof,url=f'/created-{index}/'))
                self.assertEqual(replay['X-Tree-Result'],'replay')
                self.assertEqual(parse_qs(urlsplit(replay['Location']).query)['draftRevision'],[str(draft.revision)])
                selector=urlencode({'source':'owner-draft','draftId':str(draft.pk),'draftRevision':draft.revision})
                payload['draftBasis']['revision']=draft.revision
                checked=selected_request('check',payload);self.assertEqual(checked.status_code,200)
                saved=selected_request('save',{**payload,'changes':checked.json()['normalisedChanges'],
                    'checkReceipt':checked.json()['checkReceipt'],'operationId':str(uuid4())})
                self.assertEqual(saved.status_code,200,saved.content.decode())
                page.refresh_from_db();self.assertFalse(page.is_published)
                self.assertEqual(PageContentState.objects.get(page=page).current_revision.payload['main_text'],'<p>Новый текст</p>')

    def test_reauthentication_same_owner_can_recognise_completed_operation(self):
        proof=self.proof();values=self.values(proof)
        self.assertEqual(self.post(values).status_code,303)
        again=client();self.assertEqual(login(again,'nesadmin').status_code,303)
        self.assertEqual(self.post(values,browser=again)['X-Tree-Result'],'replay')

    def test_cp012_physical_relation_cost_of_one_synthetic_creation(self):
        tables=['content_page','content_route','page_versions_pagerevision','page_versions_revisionmetadata',
                'page_versions_pagecontentstate','page_versions_ownerdraft','page_versions_versionbasepin',
                'page_versions_operationreceipt','page_versions_identityreservation','audit_auditevent']
        def sizes():
            with connection.cursor() as cursor:
                result={}
                for name in tables:
                    cursor.execute('SELECT pg_total_relation_size(%s)', ['app.'+name])
                    result[name]=cursor.fetchone()[0]
                return result
        before=sizes();self.assertEqual(self.post(self.values(self.proof())).status_code,303);after=sizes()
        self.assertTrue(all(after[key]>=before[key] for key in tables))
        print('CP29_STORAGE='+json.dumps({'before':before,'after':after,'delta':{k:after[k]-before[k] for k in tables},
            'scope':'one synthetic UNIT creation; includes indexes/TOAST, not a constant per-page tariff'},sort_keys=True))
