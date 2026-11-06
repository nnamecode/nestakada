"""E3: real worker/files/PG/child. Framework body seam, not socket evidence."""
import copy
from html import escape
import hashlib
import json
import re
from unittest.mock import patch
from uuid import UUID, uuid4

from django.conf import settings
from django.db import DatabaseError
from django.test import TransactionTestCase, override_settings

from audit.models import AuditEvent
from media_library.models import AssetUsage
from media_library.storage import MediaStorage
from page_versions import engine as E, services as V, schema as S
from page_versions.models import PageRevision
from page_editor import test_check_http as H
from page_editor import test_draft_restore_http as D
from page_editor import test_media_http as M


def attributes(values):
    return ''.join(' '+key+'="'+escape(str(value),quote=True)+'"' for key,value in sorted(values.items()))


@override_settings(ROOT_URLCONF='page_editor.test_check_http',MIDDLEWARE=H.TEST_MIDDLEWARE,
                   TEMPLATES=M.TEST_TEMPLATES,AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EmbeddedEditorHttpTests(TransactionTestCase):
    # Reuse exact approved synthetic corpus and actual WorkerClient fixture, not
    # test-class inheritance (which would silently rerun unrelated methods).
    setUp=M.EditorMediaHttpTests.setUp
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
    remove_initial_draft=D.DraftRestoreEditorHttpTests.remove_initial_draft
    upload=M.EditorMediaHttpTests.upload
    ref=M.EditorMediaHttpTests.ref
    file=M.EditorMediaHttpTests.file
    assert_image=M.EditorMediaHttpTests.assert_image
    stage=M.EditorMediaHttpTests.stage
    physical=M.EditorMediaHttpTests.physical
    version_form=M.EditorMediaHttpTests.version_form

    def issue(self,*,field='main_text',image=None,action='insert',marker=None,prior=None,
              client=None,draft=None,stage=None,changes=None,csrf=True):
        actor=client or self.owner_client
        base=draft.base_revision_id if draft else stage.base_revision_id if stage else self.current()
        body={'generation':1,'baseRevisionId':str(base),'field':field,'action':action,
              'image':self.ref(self.a) if image is None else image,'markerId':marker,'priorPermit':prior}
        if changes:body.update(changes)
        headers={}
        if csrf and settings.CSRF_COOKIE_NAME in actor.cookies:
            headers['HTTP_X_CSRFTOKEN']=actor.cookies[settings.CSRF_COOKIE_NAME].value
        return actor.post(self.path('embedded/issue',self.selector(draft=draft,stage=stage)),
                          data=self.raw(body),content_type='application/json',**headers)

    def minted(self,**kwargs):
        response=self.issue(**kwargs)
        self.assertEqual(response.status_code,200)
        value=response.json()
        self.assertEqual(set(value),{'permit','field','action','ids','image'})
        self.assertIsInstance(value['permit'],str);self.assertTrue(value['permit'])
        self.assertEqual(set(value['ids']),{'layoutId','parentId','markerId','imageId','slotBeforeId','slotAfterId'})
        for identity in value['ids'].values():self.assertEqual(str(UUID(identity)),identity)
        self.assertEqual(len(set(value['ids'].values())),6)
        return value

    def marker(self,mint,*,permit=True):
        ids,image=mint['ids'],mint['image']
        attrs={'data-es-protected':ids['markerId'],'data-es-image':ids['imageId'],
               'data-es-asset':image['asset_id'],'data-es-alt':image['alt'],
               'data-es-image-align':image['alignment']}
        for key,attr in (('width_px','data-es-width'),('height_px','data-es-height')):
            if image[key] is not None:attrs[attr]=str(image[key])
        if permit:attrs['data-es-media-intent']=mint['permit']
        return '<span'+attributes(attrs)+'></span>'

    def block(self,mint,*,before='BEFORE 😀',after='AFTER 😀',permit=True):
        ids=mint['ids']
        return '<p'+attributes({'data-es-parent':ids['parentId']})+'><span'+attributes({'data-es-slot':ids['slotBeforeId']})+'>'+before+'</span>'+self.marker(mint,permit=permit)+'<span'+attributes({'data-es-slot':ids['slotAfterId']})+'>'+after+'</span></p>'

    def publish(self,mint=None,*,html=None,field='main_text',client=None,draft=None,stage=None):
        mint=self.minted(field=field,draft=draft,stage=stage) if mint is None and html is None else mint
        value,selector,checked=self.checked({field:self.block(mint) if html is None else html},
                                          client=client,draft=draft,stage=stage)
        response=self.send('save',value,selector=selector,client=client)
        self.assertEqual(response.status_code,200)
        return mint,value,selector,checked,response.json()

    def payload_now(self):
        return PageRevision.objects.get(pk=self.current()).payload

    def refusal(self,response,status):
        self.assertEqual(response.status_code,status)
        if response.headers.get('Content-Type','').startswith('application/json'):
            value=response.json();self.assertEqual(set(value),{'ok','code'});self.assertFalse(value['ok'])
            self.assertRegex(value['code'],r'^[A-Z0-9_]{1,120}$')
        self.assertIn('no-store',response['Cache-Control'])

    def test_issue_mints_server_ids_without_domain_mutation(self):
        before=self.state();mint=self.minted()
        self.assertEqual(mint['field'],'main_text');self.assertEqual(mint['action'],'insert')
        self.assertEqual(mint['image'],self.ref(self.a));self.assertEqual(self.state(),before)
        second=self.minted();self.assertNotEqual(second['ids'],mint['ids'])

    def test_issue_roles_and_csrf_are_real_early_denials(self):
        before=self.state()
        for client,status in ((self.employee_client,403),(self.other_client,403),(self.visitor,401)):
            self.refusal(self.issue(client=client),status)
        self.refusal(self.issue(csrf=False),403);self.assertEqual(self.state(),before)

    def test_issue_closed_types_source_and_unavailable_asset(self):
        before=self.state()
        for changes in ({'field':'price'},{'generation':True},{'extra':1},{'markerId':str(uuid4())}):
            self.refusal(self.issue(changes=changes),400)
        self.refusal(self.issue(changes={'baseRevisionId':str(uuid4())}),400)
        self.refusal(self.issue(image={**self.ref(self.a),'asset_id':str(uuid4())}),409)
        self.assertEqual(self.state(),before)

    def test_issue_small_json_framing_refuses_before_body_read(self):
        before=self.state();url=self.path('embedded/issue')
        token=self.owner_client.cookies[settings.CSRF_COOKIE_NAME].value
        for content_type,headers,status in (
            ('multipart/form-data; boundary=synthetic',{},415),
            ('application/json',{'CONTENT_LENGTH':'16385'},413),
            ('application/json',{'CONTENT_LENGTH':''},411),
            ('application/json',{'HTTP_TRANSFER_ENCODING':'chunked'},400)):
            with patch('django.http.request.HttpRequest.read',side_effect=AssertionError('body reached')):
                response=self.owner_client.post(url,data=b'{}',content_type=content_type,
                    HTTP_X_CSRFTOKEN=token,**headers)
            self.refusal(response,status)
        self.assertEqual(self.state(),before)

    def test_insert_real_child_derives_closed_refs_layout_and_save_has_no_ticket(self):
        mint=self.minted();before=self.state();value,selector,checked=self.checked({'main_text':'<p>TOP</p>'+self.block(mint)+'<p>END</p>'})
        self.assertEqual(self.state(),before);canonical=checked['normalisedChanges']['main_text']
        self.assertNotIn('data-es-media-intent',canonical);self.assertNotIn(mint['permit'],json.dumps(checked))
        self.assertEqual(checked['embeddedMedia']['main_text'][0]['markerId'],mint['ids']['markerId'])
        count=PageRevision.objects.count();response=self.send('save',value,selector=selector);self.assertEqual(response.status_code,200)
        self.assertEqual(PageRevision.objects.count(),count+1);payload=self.payload_now()
        self.assertEqual(payload['main_text'],canonical)
        image=next(item for item in payload['embedded_images'] if item['id']==mint['ids']['imageId'])
        self.assertEqual(image,{'id':mint['ids']['imageId'],**mint['image']})
        descriptors=[node for item in payload['layout'] if item['kind']=='text' for node in item['protected_nodes']]
        self.assertEqual([node['id'] for node in descriptors],[mint['ids']['markerId']])
        self.assertEqual(descriptors[0]['reference_id'],mint['ids']['imageId']);self.assertRegex(descriptors[0]['fingerprint'],r'^[a-f0-9]{64}$')
        self.assertTrue(AssetUsage.objects.filter(kind='current_page',consumer_id=self.page.pk,
                        slot='embedded:'+mint['ids']['imageId'],asset=self.a).exists())
        self.assertNotIn(mint['permit'],json.dumps(payload));self.assertNotIn('data-es-media-intent',json.dumps(payload))

    def test_repeat_check_after_accept_and_text_edit_reuses_same_issued_ids(self):
        mint=self.minted();first,selector,checked=self.checked({'main_text':self.block(mint)})
        canonical=checked['normalisedChanges']['main_text']
        self.assertIn(mint['ids']['markerId'],canonical)
        edited=self.block(mint,before='<strong>EDITED é 😀</strong>')
        second,_,review=self.checked({'main_text':edited})
        self.assertEqual(review['embeddedMedia']['main_text'][0]['imageId'],mint['ids']['imageId'])
        self.assertIn(mint['ids']['parentId'],second['changes']['main_text'])
        self.assertEqual(self.send('save',second,selector=selector).status_code,200)
        self.assertIn('<strong>EDITED é 😀</strong>',self.payload_now()['main_text'])

    def test_fake_wrong_field_and_changed_image_permits_refuse_whole(self):
        mint=self.minted();before=self.state()
        variants=[('main_text',self.block({**mint,'permit':mint['permit']+'X'}),400,'EDITOR_EMBEDDED_INVALID'),
                  ('intro_text',self.block(mint),403,'EDITOR_EMBEDDED_FORBIDDEN'),
                  ('main_text',self.block({**mint,'image':self.ref(self.b)}),403,'EDITOR_EMBEDDED_FORBIDDEN'),
                  ('main_text',self.block({**mint,'ids':{**mint['ids'],'imageId':str(uuid4())}}),403,'EDITOR_EMBEDDED_FORBIDDEN')]
        for field,html,status,code in variants:
            response=self.send('check',self.payload({field:html},baseRevisionId=str(self.current())))
            self.refusal(response,status);self.assertEqual(response.json()['code'],code);self.assertNotIn('checkReceipt',response.json())
            self.assertEqual(self.state(),before)

    def test_issue_permission_not_transferable_to_employee(self):
        mint=self.minted();before=self.state()
        response=self.send('check',self.payload({'main_text':self.block(mint)},baseRevisionId=str(self.current())),client=self.employee_client)
        self.refusal(response,400);self.assertEqual(response.json()['code'],'EDITOR_INPUT_REJECTED');self.assertNotIn('checkReceipt',response.json());self.assertEqual(self.state(),before)

    def test_employee_unicode_and_inline_slot_positive_preserves_map_and_files(self):
        mint,*_=self.publish();before=self.payload_now();physical=[MediaStorage().manifest(file.key) for file in self.a.files.order_by('key')]
        html=before['main_text'].replace('BEFORE 😀','GROWN é 😀 <strong>MARK</strong>').replace('AFTER 😀','AFTER '+('😀'*20))
        self.publish(html=html,client=self.employee_client)
        after=self.payload_now();self.assertEqual(after['embedded_images'],before['embedded_images']);self.assertEqual(after['layout'],before['layout'])
        self.assertIn('<strong>MARK</strong>',after['main_text']);self.assertEqual(PageRevision.objects.get(pk=self.current()).author_id,self.employee.pk)
        self.assertEqual([MediaStorage().manifest(file.key) for file in self.a.files.order_by('key')],physical)

    def test_employee_marker_parent_slot_asset_and_ancestor_mutations_refuse(self):
        mint,*_=self.publish();source=self.payload_now()['main_text'];before=self.state()
        mutations=[source.replace(mint['ids'][key],str(uuid4())) for key in ('markerId','imageId','parentId','slotBeforeId','slotAfterId')]
        mutations.extend([source.replace(str(self.a.pk),str(self.b.pk)),source.replace('data-es-alt="Synthetic 😀"','data-es-alt="CHANGED"'),
                          source.replace('<p data-es-parent=','<p data-es-align="right" data-es-parent=')])
        for html in mutations:
            self.assertNotEqual(html,source)
            response=self.send('check',self.payload({'main_text':html},baseRevisionId=str(self.current())),client=self.employee_client)
            self.refusal(response,400);self.assertEqual(response.json()['code'],'EDITOR_INPUT_REJECTED');self.assertNotIn('checkReceipt',response.json());self.assertEqual(self.state(),before)

    def test_replace_issues_new_reference_and_retains_stable_old_bytes(self):
        mint,_,_,_,saved=self.publish();old=self.payload_now();view=V.view_version(actor=self.owner,page_id=self.page.pk,version_id=saved['result_id'],expected_generation=1)
        V.set_stable(actor=self.owner,page_id=self.page.pk,version_id=saved['result_id'],view_receipt=view['view_receipt'],expected_generation=1,operation_id=uuid4())
        physical=[MediaStorage().manifest(file.key) for file in self.a.files.order_by('key')]
        replaced=self.minted(action='replace',marker=mint['ids']['markerId'],image=self.ref(self.b))
        self.assertNotEqual(replaced['ids']['imageId'],mint['ids']['imageId'])
        for key in ('layoutId','parentId','markerId','slotBeforeId','slotAfterId'):self.assertEqual(replaced['ids'][key],mint['ids'][key])
        self.publish(replaced)
        self.assertEqual(PageRevision.objects.get(pk=saved['result_id']).payload,old)
        self.assertEqual(self.payload_now()['embedded_images'],[{'id':replaced['ids']['imageId'],**self.ref(self.b)}])
        self.assertEqual([MediaStorage().manifest(file.key) for file in self.a.files.order_by('key')],physical)
        self.assertTrue(AssetUsage.objects.filter(kind='stable_version',consumer_id=saved['result_id'],asset=self.a).exists())

    def test_pending_replace_is_standalone_not_nested_prior_permit(self):
        mint=self.minted();replacement=self.minted(action='replace',marker=mint['ids']['markerId'],prior=mint['permit'],image=self.ref(self.b))
        self.assertNotEqual(replacement['ids']['imageId'],mint['ids']['imageId'])
        _,_,_,checked,_=self.publish(replacement)
        self.assertNotIn(mint['permit'],json.dumps(checked));self.assertNotIn(replacement['permit'],json.dumps(self.payload_now()))

    def test_replace_one_marker_preserves_shared_reference_in_other_field(self):
        # Trusted initial snapshot only: independent canonical fingerprint oracle,
        # actual engine+worker files. The tested replacement itself is HTTP.
        image_id=str(uuid4());image={'id':image_id,**self.ref(self.a)};layout=[];sources={};mints={}
        for field in ('intro_text','main_text'):
            ids={name:str(uuid4()) for name in ('layoutId','parentId','markerId','slotBeforeId','slotAfterId')}
            ids['imageId']=image_id;mint={'ids':ids,'image':self.ref(self.a)};mints[field]=mint
            sources[field]=self.block(mint,permit=False)
            canonical={'protocol':'es-protected-placement-v1','scope_id':str(self.page.pk),'field':field,
                'layout_id':ids['layoutId'],'parent_id':ids['parentId'],'parent_path':[0],
                'ancestors':[{'tag':'p','attributes':[['data-es-parent',ids['parentId']]]}],
                'sequence':[['slot',ids['slotBeforeId']],['marker',ids['markerId']],['slot',ids['slotAfterId']]],
                'marker':{'marker_id':ids['markerId'],'image_id':image_id,'asset_id':str(self.a.pk),
                          'alt':image['alt'],'alignment':image['alignment'],'width_px':None,'height_px':None},
                'before_slot_id':ids['slotBeforeId'],'after_slot_id':ids['slotAfterId']}
            fingerprint=hashlib.sha256(json.dumps(canonical,ensure_ascii=False,sort_keys=True,
                separators=(',',':'),allow_nan=False).encode()).hexdigest()
            layout.append({'id':ids['layoutId'],'kind':'text','field':field,'protected_nodes':[
                {'id':ids['markerId'],'reference_id':image_id,'fingerprint':fingerprint}]})
        payload={**self.payload_now(),**sources,'embedded_images':[image],'layout':layout}
        V.commit_owner(actor=self.owner,page_id=self.page.pk,base_revision=self.current(),
                       snapshot=S.Snapshot.trusted(payload,self.page.kind),expected_generation=1,operation_id=uuid4())
        before=self.payload_now();replacement=self.minted(action='replace',marker=mints['main_text']['ids']['markerId'],image=self.ref(self.b))
        self.publish(replacement);after=self.payload_now()
        self.assertEqual(after['intro_text'],before['intro_text'])
        self.assertEqual(next(node for node in after['layout'] if node['field']=='intro_text'),layout[0])
        self.assertEqual({entry['id']:entry['asset_id'] for entry in after['embedded_images']},
                         {image_id:str(self.a.pk),replacement['ids']['imageId']:str(self.b.pk)})
        for reference,asset in ((image_id,self.a),(replacement['ids']['imageId'],self.b)):
            self.assertTrue(AssetUsage.objects.filter(kind='current_page',consumer_id=self.page.pk,
                slot='embedded:'+reference,asset=asset).exists())

    def test_draft_insert_keeps_current_then_apply_uses_private_selected_map(self):
        draft=self.draft();mint=self.minted(draft=draft,image=self.ref(self.b));current=self.current()
        value,selector,_=self.checked({'main_text':self.block(mint)},draft=draft)
        response=self.send('draft',{**value,'rebase':False},selector=selector);self.assertEqual(response.status_code,200)
        changed=self.draft();self.assertEqual(self.current(),current);self.assertEqual(changed.payload['embedded_images'][0]['asset_id'],str(self.b.pk))
        self.publish(html=changed.payload['main_text'],draft=changed)
        self.assertEqual(self.payload_now()['embedded_images'][0]['id'],mint['ids']['imageId'])

    def test_stage_candidate_contextual_bytes_and_edited_apply(self):
        mint,_,_,_,saved=self.publish()
        replacement=self.minted(action='replace',marker=mint['ids']['markerId'],image=self.ref(self.b))
        self.publish(replacement)
        stage=self.stage(self.owner,saved['result_id']);selected=self.selector(stage=stage)
        response=self.owner_client.get(self.path('',selected));self.assertEqual(response.status_code,200)
        item=response.context['initial_state']['embeddedMedia']['main_text'][0]
        self.assertEqual(item['imageId'],mint['ids']['imageId'])
        self.assert_image(self.owner_client.get(item['thumbnailUrl']),self.file(self.a,'preview'))
        current=self.current();value,selector,_=self.checked({'main_text':self.block(mint,permit=False,before='STAGED EDIT')},stage=stage)
        self.assertEqual(self.current(),current);self.assertEqual(self.send('save',value,selector=selector).status_code,200)
        self.assertEqual(self.payload_now()['embedded_images'][0]['id'],mint['ids']['imageId'])

    def test_direct_employee_restore_preserves_protected_embedded_layout(self):
        mint,_,_,_,saved=self.publish()
        source=PageRevision.objects.get(pk=saved['result_id'])
        source_payload=copy.deepcopy(source.payload)
        current_html=self.block(
            mint,permit=False,before='EMPLOYEE CURRENT BEFORE',
            after='EMPLOYEE CURRENT AFTER')
        value,selector,_=self.checked(
            {'main_text':current_html},client=self.employee_client)
        changed=self.send('save',value,selector=selector,client=self.employee_client)
        self.assertEqual(changed.status_code,200)
        current_payload=copy.deepcopy(self.payload_now())
        self.assertNotEqual(current_payload['main_text'],source_payload['main_text'])
        self.assertEqual(current_payload['layout'],source_payload['layout'])
        self.assertEqual(current_payload['embedded_images'],source_payload['embedded_images'])

        prepared=self.version_form(
            self.employee_client,source.pk,'prepare',{'generation':1})
        self.assertEqual(prepared.status_code,200)
        before=self.state();audit=list(AuditEvent.objects.order_by('id').values())
        response=self.version_form(self.employee_client,source.pk,'apply',{
            'generation':1,'operation_id':str(uuid4()),
            'preparation':prepared.context['prepared']['preparation'],
            'confirm_input_replacement':'yes'})
        self.assertEqual(response.status_code,200)
        restored=self.payload_now()
        self.assertEqual(restored['main_text'],source_payload['main_text'])
        self.assertEqual(restored['layout'],current_payload['layout'])
        self.assertEqual(restored['embedded_images'],current_payload['embedded_images'])
        self.assertEqual(restored['h1'],current_payload['h1'])
        self.assertTrue(AssetUsage.objects.filter(
            kind='current_page',consumer_id=self.page.pk,
            slot='embedded:'+mint['ids']['imageId'],asset=self.a).exists())
        self.assertEqual(len(self.state()['stages']),len(before['stages']))
        self.assertEqual(len(self.state()['operations']),len(before['operations']))
        self.assertEqual(len(self.state()['pins']),len(before['pins']))
        self.assertEqual(len(AuditEvent.objects.order_by('id')),len(audit)+1)

    def test_current_embedded_bytes_membership_employee_and_original_privacy(self):
        mint,*_=self.publish();response=self.employee_client.get(self.path(''));self.assertEqual(response.status_code,200)
        item=response.context['initial_state']['embeddedMedia']['main_text'][0]
        self.assertEqual(item['markerId'],mint['ids']['markerId']);self.assert_image(self.employee_client.get(item['thumbnailUrl']),self.file(self.a,'preview'))
        self.assertEqual(self.other_client.get(item['thumbnailUrl']).status_code,403);self.assertEqual(self.visitor.get(item['thumbnailUrl']).status_code,401)
        self.assertEqual(self.owner_client.get(self.path('media/files/'+str(self.file(self.a,'private-source').pk))).status_code,404)

    def test_repeated_simple_save_conflicts_before_missing_embedded_file(self):
        _,value,selector,_,saved=self.publish();file=self.file(self.a);path=self.physical(file);data=path.read_bytes();path.unlink()
        try:
            before=self.state();audit=AuditEvent.objects.count();response=self.send('save',value,selector=selector)
            self.assertEqual(response.status_code,409);self.assertEqual(response.json()['code'],'EDITOR_BASE_CONFLICT')
            self.assertNotIn('result_id',response.json())
            self.assertEqual(self.state(),before);self.assertEqual(AuditEvent.objects.count(),audit)
        finally:path.write_bytes(data)

    def test_post_real_sql_fault_rolls_back_embedded_layout_refs_and_receipt(self):
        mint=self.minted();value,selector,_=self.checked({'main_text':self.block(mint)});before=self.state();audit=AuditEvent.objects.count();actual=E.event
        physical=[MediaStorage().manifest(file.key) for file in self.a.files.order_by('key')]
        def fault(*args,**kwargs):actual(*args,**kwargs);raise DatabaseError('synthetic embedded post-audit fault')
        with patch('page_versions.engine.event',side_effect=fault):response=self.send('save',value,selector=selector)
        self.assertEqual(response.status_code,503);self.assertEqual(self.state(),before);self.assertEqual(AuditEvent.objects.count(),audit)
        self.assertEqual([MediaStorage().manifest(file.key) for file in self.a.files.order_by('key')],physical)

    def crafted_worker_refusal(self,changes,alter):
        # This is a compromised-worker boundary test, not a claimed HTTP exploit
        # of the actual child. Every fixture/control still runs the genuine child.
        from editor_runtime.processing import normalize_input as actual_child
        value=self.payload(changes,baseRevisionId=str(self.current()))
        self.assertEqual(self.send('check',value).status_code,200)
        before=self.state();audit=AuditEvent.objects.count();calls=[]
        def crafted(raw,context):
            genuine=actual_child(raw,context)
            self.assertTrue(genuine['accepted']);self.assertIn('derived',genuine)
            changed=copy.deepcopy(genuine);alter(changed)
            derived=changed['derived']
            map_value={key:derived[key] for key in ('embedded_images','layout')}
            derived['mapHash']=hashlib.sha256(json.dumps(map_value,ensure_ascii=False,sort_keys=True,
                separators=(',',':'),allow_nan=False).encode()).hexdigest()
            # Keep all accepted changes, source/policy/raw/normalised hashes and
            # warnings genuine; only closed derived metadata is adversarial.
            self.assertEqual({key:item for key,item in genuine.items() if key not in ('derived','intentBindings')},
                             {key:item for key,item in changed.items() if key not in ('derived','intentBindings')})
            calls.append(True);return changed
        with patch('page_editor.views.normalize_input',side_effect=crafted):
            response=self.send('check',value)
        self.assertEqual(calls,[True]);self.refusal(response,400)
        self.assertEqual(response.json()['code'],'EDITOR_EMBEDDED_INVALID')
        self.assertNotIn('checkReceipt',response.json());self.assertEqual(self.state(),before)
        self.assertEqual(AuditEvent.objects.count(),audit)

    def test_parent_rejects_unused_new_worker_image_reference_without_authority(self):
        def alter(result):
            result['derived']['embedded_images'].append({'id':str(uuid4()),**self.ref(self.a)})
            self.assertEqual(result['intentBindings'],[])
        self.crafted_worker_refusal({'main_text':'<p>PLAIN VALID CONTROL 😀</p>'},alter)

    def test_parent_rejects_worker_erasing_source_markers_while_retaining_layout_rows(self):
        self.publish();source=self.payload_now()['main_text']
        def alter(result):
            self.assertTrue(result['intentBindings'])
            for node in result['derived']['layout']:
                if node['kind']=='text':node['protected_nodes']=[]
            result['intentBindings']=[]
        self.crafted_worker_refusal({'main_text':source.replace('BEFORE 😀','PERMITTED TEXT EDIT 😀')},alter)

    def test_parent_rejects_empty_new_worker_layout_without_issued_marker(self):
        def alter(result):
            result['derived']['layout'].append({'id':str(uuid4()),'kind':'text','field':'main_text','protected_nodes':[]})
            self.assertEqual(result['intentBindings'],[])
        self.crafted_worker_refusal({'main_text':'<p>PLAIN VALID CONTROL TWO</p>'},alter)
