"""TP2 actual producer/selected-source/protected-media tests; not native commands."""
from copy import deepcopy
from urllib.parse import urlencode
from uuid import uuid4

from django.conf import settings
from django.test import TransactionTestCase, override_settings
from accounts.services import set_grant
from page_versions import services as V, schema as S
from page_versions.models import PageRevision, PageContentState, OwnerDraft, RestoreStage
from media_library.models import AssetUsage
from media_library.storage import MediaStorage
from . import test_check_http as H, test_draft_restore_http as D
from . import test_media_http as M, test_embedded_http as E

TEST_TEMPLATES = deepcopy(settings.TEMPLATES)
TEST_TEMPLATES[0]['DIRS'] = [*TEST_TEMPLATES[0].get('DIRS', []), str(settings.BASE_DIR/'page_editor'/'templates')]


def simple(padding='4', marker='TABLE-UNICODE-é-😀'):
    return ('<table data-es-cellpad="'+padding+'"><thead><tr><th scope="col">H1</th><th scope="col">H2</th></tr></thead>'
        '<tbody><tr><td>'+marker+'</td><td><strong>Bold</strong></td></tr><tr><td>R3</td><td>R3C2</td></tr></tbody></table>')


@override_settings(ROOT_URLCONF='page_editor.test_check_http', MIDDLEWARE=H.TEST_MIDDLEWARE,
    TEMPLATES=TEST_TEMPLATES, AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TableGuiHttpTests(TransactionTestCase):
    setUp = H.EditorCheckHttpTests.setUp
    login = H.EditorCheckHttpTests.login
    raw = H.EditorCheckHttpTests.raw
    post = H.EditorCheckHttpTests.post
    payload = H.EditorCheckHttpTests.payload
    state = H.EditorCheckHttpTests.state

    def current(self):
        return PageRevision.objects.get(pk=PageContentState.objects.get(page=self.page).current_revision_id)

    def commit_html(self, html):
        payload=deepcopy(self.current().payload);payload['main_text']=html
        result=V.commit_owner(actor=self.owner,page_id=self.page.pk,base_revision=self.current().pk,
            snapshot=S.Snapshot.trusted(payload,self.page.kind),expected_generation=1,operation_id=uuid4())
        return PageRevision.objects.get(pk=result['result_id'])

    def checked_save(self, html, client=None):
        value=self.payload({'main_text':html},baseRevisionId=str(self.current().pk))
        checked=self.post(client or self.owner_client,value)
        self.assertEqual(checked.status_code,200)
        result=checked.json()
        value.update(changes=result['normalisedChanges'],operationId=str(uuid4()),checkReceipt=result['checkReceipt'])
        original=self.url
        try:
            self.url=original.replace('/check/','/save/')
            saved=self.post(client or self.owner_client,value)
        finally:self.url=original
        self.assertEqual(saved.status_code,200)
        return result

    def editor(self, selector=None, client=None):
        target='/manage/pages/%s/edit/'%self.page.pk
        if selector:target+='?'+urlencode(selector)
        return (client or self.owner_client).get(target)

    def test_tp2_001_002_employee_real_table_save_padding_scope_and_protected_payload(self):
        before=deepcopy(self.current().payload)
        for padding in ('4','0','32'):
            result=self.checked_save(simple(padding),self.employee_client)
            stored=self.current().payload
            self.assertEqual(stored['main_text'],result['normalisedChanges']['main_text'])
            self.assertIn('data-es-cellpad="'+padding+'"',stored['main_text'])
            self.assertIn('<thead><tr><th scope="col">',stored['main_text'])
            self.assertIn('<tbody><tr><td>TABLE-UNICODE-é-😀</td>',stored['main_text'])
            self.assertNotIn('data-editor-',stored['main_text']);self.assertNotIn('<colgroup',stored['main_text'])
            self.assertEqual({key:value for key,value in stored.items() if key!='main_text'},
                             {key:value for key,value in before.items() if key!='main_text'})

    def test_tp2_007_current_draft_stage_and_rights_use_real_selected_html(self):
        old=self.commit_html(simple('0','OLD-CURRENT'))
        draft=OwnerDraft.objects.get(page=self.page)
        payload=deepcopy(draft.payload);payload['main_text']=simple('4','OWNER-DRAFT')
        V.save_owner_draft(actor=self.owner,page_id=self.page.pk,base_revision=draft.base_revision_id,
            draft_id=draft.pk,draft_revision=draft.revision,snapshot=S.Snapshot.trusted(payload,self.page.kind),
            expected_generation=1,operation_id=uuid4())
        draft.refresh_from_db();self.commit_html(simple('32','NEW-CURRENT'))
        preparation=V.prepare_restore(actor=self.owner,page_id=self.page.pk,version_id=old.pk,expected_generation=1)
        result=V.stage_restore(actor=self.owner,page_id=self.page.pk,preparation=preparation['preparation'],
            confirm_input_replacement=True,expected_generation=1,operation_id=uuid4())
        stage=RestoreStage.objects.get(pk=result['result_id']);before=self.state()
        selector={'source':'owner-draft','draftId':str(draft.pk),'draftRevision':draft.revision}
        self.assertIn('NEW-CURRENT',self.editor().context['initial_state']['values']['main_text'])
        self.assertIn('OWNER-DRAFT',self.editor(selector).context['initial_state']['values']['main_text'])
        self.assertIn('OLD-CURRENT',self.editor({'source':'restore-stage','stageId':str(stage.pk)}).context['initial_state']['values']['main_text'])
        self.assertEqual(self.editor(selector,self.employee_client).status_code,403)
        self.assertEqual(self.state(),before)
        set_grant(actor=self.owner,employee=self.employee,page=self.page,intro_text=True,main_text=False)
        before=self.state()
        denied=self.post(self.employee_client,self.payload({'main_text':simple()},baseRevisionId=str(self.current().pk)))
        self.assertEqual(denied.status_code,403);self.assertEqual(self.state(),before)

    def test_tp2_002_invalid_padding_refuses_whole_input_without_revision_or_receipt(self):
        for padding in ('-1','33','NaN','0.5',''):
            before=self.state();source=simple(padding)
            checked=self.post(self.owner_client,self.payload({'main_text':source},baseRevisionId=str(self.current().pk)))
            self.assertEqual(checked.status_code,400)
            self.assertNotIn('checkReceipt',checked.json());self.assertEqual(self.state(),before)

    def test_tp2_006_giant_nested_and_complex_are_actual_approved_source_not_dense_html(self):
        sources=[
            '<table><tbody><tr><td colspan="1000000000">GIANT-EXACT</td></tr></tbody></table>',
            '<table><tbody><tr><td><table><tbody><tr><td>NESTED</td></tr></tbody></table></td></tr></tbody></table>',
            '<table data-es-cellpad="4"><caption>CAPTION</caption><thead><tr><th scope="col" colspan="2">H</th></tr></thead><tbody><tr><th scope="row">R</th><td>VALUE</td></tr></tbody></table>',
            '<table><tbody>'+('<tr>'+'<td>x</td>'*140+'</tr>')*100+'</tbody></table>',
            '<ul>'+'<li>x</li>'*15000+'</ul>',
        ]
        for source in sources:
            result=self.checked_save(source)
            canonical=result['normalisedChanges']['main_text']
            self.assertEqual(self.current().payload['main_text'],canonical)
            self.assertEqual(self.editor().context['initial_state']['values']['main_text'],canonical)
            if 'GIANT-EXACT' in source:self.assertEqual(canonical,source)


@override_settings(ROOT_URLCONF='page_editor.test_check_http', MIDDLEWARE=H.TEST_MIDDLEWARE,
    TEMPLATES=TEST_TEMPLATES, AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TableProtectedHttpTests(TransactionTestCase):
    setUp=M.EditorMediaHttpTests.setUp
    login=H.EditorCheckHttpTests.login
    raw=H.EditorCheckHttpTests.raw
    post=H.EditorCheckHttpTests.post
    payload=H.EditorCheckHttpTests.payload
    upload=M.EditorMediaHttpTests.upload
    ref=M.EditorMediaHttpTests.ref
    current=D.DraftRestoreEditorHttpTests.current
    draft=D.DraftRestoreEditorHttpTests.draft
    state=D.DraftRestoreEditorHttpTests.state
    selector=D.DraftRestoreEditorHttpTests.selector
    path=D.DraftRestoreEditorHttpTests.path
    send=D.DraftRestoreEditorHttpTests.send
    checked=D.DraftRestoreEditorHttpTests.checked
    issue=E.EmbeddedEditorHttpTests.issue
    minted=E.EmbeddedEditorHttpTests.minted
    marker=E.EmbeddedEditorHttpTests.marker
    block=E.EmbeddedEditorHttpTests.block
    publish=E.EmbeddedEditorHttpTests.publish
    payload_now=E.EmbeddedEditorHttpTests.payload_now

    def test_tp2_007_real_ready_photo_ordinal_guard_prefix_refused_suffix_table_saved(self):
        self.publish()
        original=deepcopy(self.payload_now())
        physical={str(file.pk):MediaStorage().manifest(file.key) for file in self.a.files.all()}
        state=self.state()
        refusal=self.send('check',self.payload({'main_text':simple()+original['main_text']},
            baseRevisionId=str(self.current())),client=self.employee_client)
        self.assertEqual(refusal.status_code,409)
        self.assertEqual(refusal.json()['code'],'EDITOR_CAPABILITY_UNAVAILABLE')
        self.assertNotIn('checkReceipt',refusal.json())
        self.assertEqual(self.state(),state)
        self.assertEqual({str(file.pk):MediaStorage().manifest(file.key) for file in self.a.files.all()},physical)
        active_refs=list(AssetUsage.objects.filter(kind='current_page').order_by('consumer_id','slot')
                         .values('kind','consumer_id','slot','asset_id'))
        self.publish(html=original['main_text']+simple(),client=self.employee_client)
        after=self.payload_now()
        self.assertEqual(after['embedded_images'],original['embedded_images'])
        self.assertEqual(after['layout'],original['layout'])
        self.assertEqual(list(AssetUsage.objects.filter(kind='current_page').order_by('consumer_id','slot')
                             .values('kind','consumer_id','slot','asset_id')),active_refs)
        self.assertEqual({str(file.pk):MediaStorage().manifest(file.key) for file in self.a.files.all()},physical)
