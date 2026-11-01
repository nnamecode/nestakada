"""E1 pure placement checks. UUID references are NOT READY/rights/HTTP proof."""
import copy
from dataclasses import FrozenInstanceError, replace
import hashlib
from html import escape
import json
import unittest
from unittest.mock import patch
from uuid import UUID

import nh3

from page_editor.html_policy import normalize_html
from page_editor.protected_policy import build_protected_context
from page_editor.types import (ControlledUnsupported, PolicyError, ProtectedAncestor,
    ProtectedBinding, ProtectedContext, ProtectedParent)

SCOPE=str(UUID(int=1))
uid=lambda number:str(UUID(int=number))


def attrs(values):
    return ''.join(' '+key+'="'+escape(value,quote=True)+'"' for key,value in sorted(values.items()))


def fingerprint(value):
    # Independent contract oracle: no production fingerprint/builder helper.
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',', ':'),allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def fixture(*,field='main_text',parents=1,markers=1,shared_asset=False):
    layout=[];images=[];expected_nodes=[];expected_parents=[];parent_html=[];marker_html=[];slot_html=[]
    for index in range(parents):
        offset=index*100;parent_id=uid(100+offset);layout_id=uid(101+offset)
        slots=[uid(110+offset+j) for j in range(markers+1)]
        marker_ids=[uid(130+offset+j) for j in range(markers)]
        parent_attrs={'data-es-parent':parent_id,'data-es-align':'left'}
        ancestors=[{'tag':'p','attributes':[[key,value] for key,value in sorted(parent_attrs.items())]}]
        sequence=[]
        for j,slot in enumerate(slots):
            sequence.append(['slot',slot])
            if j<markers:sequence.append(['marker',marker_ids[j]])
        protected=[];children=[]
        for j,slot in enumerate(slots):
            html='<span data-es-slot="'+slot+'">TEXT '+str(index)+':'+str(j)+' 😀</span>'
            children.append(html);slot_html.append(html)
            if j==markers:continue
            image={'id':uid(150+offset+j),'asset_id':uid(9000 if shared_asset else 170+offset+j),
                   'alt':'Image 😀 '+str(index)+':'+str(j),'alignment':'center','width_px':120,'height_px':80}
            images.append(image)
            descriptor={'marker_id':marker_ids[j],'image_id':image['id'],'asset_id':image['asset_id'],
                        'alt':image['alt'],'alignment':image['alignment'],'width_px':120,'height_px':80}
            canonical={'protocol':'es-protected-placement-v1','scope_id':SCOPE,'field':field,
                'layout_id':layout_id,'parent_id':parent_id,'parent_path':[index],
                'ancestors':ancestors,'sequence':sequence,'marker':descriptor,
                'before_slot_id':slots[j],'after_slot_id':slots[j+1]}
            digest=fingerprint(canonical)
            protected.append({'id':marker_ids[j],'reference_id':image['id'],'fingerprint':digest})
            expected_nodes.append(ProtectedBinding(marker_id=marker_ids[j],parent_id=parent_id,
                slot_before_id=slots[j],slot_after_id=slots[j+1],image_id=image['id'],asset_id=image['asset_id'],
                alt=image['alt'],alignment='center',width_px=120,height_px=80,fingerprint=digest))
            marker='<span'+attrs({'data-es-protected':marker_ids[j],'data-es-image':image['id'],
                'data-es-asset':image['asset_id'],'data-es-alt':image['alt'],'data-es-image-align':'center',
                'data-es-width':'120','data-es-height':'80'})+'></span>'
            children.append(marker);marker_html.append(marker)
        layout.append({'id':layout_id,'kind':'text','field':field,'protected_nodes':protected})
        expected_parents.append(ProtectedParent(parent_id=parent_id,layout_id=layout_id,path=(index,),
            ancestors=tuple(ProtectedAncestor(value['tag'],tuple(tuple(pair) for pair in value['attributes'])) for value in ancestors),
            sequence=tuple(tuple(pair) for pair in sequence)))
        parent_html.append('<p'+attrs(parent_attrs)+'>'+''.join(children)+'</p>')
    source=''.join(parent_html)
    return {'source':source,'layout':layout,'images':images,'nodes':tuple(expected_nodes),'parents':tuple(expected_parents),
            'parent_html':parent_html,'marker_html':marker_html,'slot_html':slot_html,'field':field}


class ProtectedPolicyTests(unittest.TestCase):
    def build(self,value):
        return build_protected_context(value['source'],field=value['field'],scope_id=SCOPE,
                                       layout=value['layout'],embedded_images=value['images'])

    def normalize(self,html,context,**kwargs):
        values={'owner':False,'field':'main_text','scope_id':SCOPE,'protected_context':context}
        values.update(kwargs)
        return normalize_html(html,**values)

    def reject(self,html,context,code=None,**kwargs):
        with patch('page_editor.clean.nh3.clean',wraps=nh3.clean) as cleaner:
            with self.assertRaises(PolicyError) as caught:
                self.normalize(html,context,**kwargs)
            self.assertNotIsInstance(caught.exception,ControlledUnsupported)
            if code:self.assertEqual(caught.exception.code,code)
            self.assertEqual(str(caught.exception),caught.exception.code)
            cleaner.assert_not_called()

    def test_independent_fingerprint_full_map_and_source_hash(self):
        value=fixture(parents=2,markers=2,shared_asset=True)
        before=copy.deepcopy(value)
        context=self.build(value)
        self.assertEqual(context.nodes,value['nodes'])
        self.assertEqual(context.parents,value['parents'])
        self.assertEqual(context.scope_id,SCOPE)
        self.assertEqual(context.field,'main_text')
        self.assertEqual(context.source_sha256,hashlib.sha256(value['source'].encode('utf-8')).hexdigest())
        self.assertEqual(value,before)
        result=self.normalize(value['source'],context)
        self.assertEqual(result.html,value['source'])
        self.assertEqual([(ref.image_id,ref.asset_id) for ref in result.pending_assets],
                         [(node.image_id,node.asset_id) for node in value['nodes']])
        self.assertEqual(len({ref.asset_id for ref in result.pending_assets}),1)

    def test_text_growth_before_after_and_slot_format_are_real_positives(self):
        value=fixture(markers=2);context=self.build(value)
        candidate=value['source'].replace('TEXT 0:0 😀','GROWN BEFORE 😀 é'*8).replace('TEXT 0:2 😀','AFTER 😀'*5)
        candidate=candidate.replace('TEXT 0:1 😀','<strong>MARK 😀</strong><span data-es-font="arial" data-es-size="12.5">MIDDLE</span>')
        result=self.normalize(candidate,context)
        self.assertIn('GROWN BEFORE 😀 é',result.html)
        self.assertIn('<strong>MARK 😀</strong>',result.html)
        self.assertEqual(context.nodes,value['nodes'])
        self.assertEqual(context.parents,value['parents'])
        self.assertEqual(self.normalize(result.html,context).html,result.html)

    def test_nested_parent_positive_uses_independent_ancestor_path_fingerprint(self):
        value=fixture()
        original=value['parents'][0]
        ancestor=ProtectedAncestor('blockquote',(('data-es-ml','8'),))
        parent=replace(original,path=(0,0),ancestors=(ancestor,)+original.ancestors)
        nodes=[]
        for node in value['nodes']:
            canonical={'protocol':'es-protected-placement-v1','scope_id':SCOPE,'field':'main_text',
                'layout_id':parent.layout_id,'parent_id':parent.parent_id,'parent_path':[0,0],
                'ancestors':[{'tag':item.tag,'attributes':[list(pair) for pair in item.attributes]} for item in parent.ancestors],
                'sequence':[list(pair) for pair in parent.sequence],
                'marker':{name:getattr(node,name) for name in ('marker_id','image_id','asset_id','alt','alignment','width_px','height_px')},
                'before_slot_id':node.slot_before_id,'after_slot_id':node.slot_after_id}
            changed=replace(node,fingerprint=fingerprint(canonical));nodes.append(changed)
            value['layout'][0]['protected_nodes'][0]['fingerprint']=changed.fingerprint
        value['source']='<blockquote data-es-ml="8">'+value['source']+'</blockquote>'
        context=self.build(value)
        self.assertEqual(context.parents,(parent,))
        self.assertEqual(context.nodes,tuple(nodes))
        candidate=value['source'].replace('TEXT 0:0 😀','<strong>NESTED GROWN 😀</strong>')
        result=self.normalize(candidate,context)
        self.assertIn('<strong>NESTED GROWN 😀</strong>',result.html)
        self.assertEqual(self.normalize(result.html,context).html,result.html)

    def test_shared_middle_slot_boundaries_and_multiple_layout_descriptors(self):
        value=fixture(parents=2,markers=2);context=self.build(value)
        self.assertEqual(context.nodes[0].slot_after_id,context.nodes[1].slot_before_id)
        self.assertNotEqual(context.parents[0].layout_id,context.parents[1].layout_id)
        self.assertEqual(self.normalize(value['source'],context).html,value['source'])
        for field in ('intro_text','main_text'):
            other=fixture(field=field)
            self.assertEqual(self.normalize(other['source'],self.build(other),field=field).html,other['source'])

    def test_immutable_frozen_context_values(self):
        context=self.build(fixture())
        for value,field,changed in ((context,'field','intro_text'),(context.nodes[0],'alt','changed'),
                                    (context.parents[0],'path',(1,)),(context.parents[0].ancestors[0],'tag','h2')):
            with self.assertRaises(FrozenInstanceError):setattr(value,field,changed)

    def test_empty_trusted_context_keeps_default_unsupported(self):
        value=fixture()
        with patch('page_editor.clean.nh3.clean',wraps=nh3.clean) as cleaner:
            with self.assertRaises(ControlledUnsupported) as caught:
                self.normalize(value['source'],ProtectedContext())
            self.assertEqual(caught.exception.code,'PROTECTED_INTEGRATION_UNSUPPORTED')
            cleaner.assert_not_called()

    def test_scope_and_field_mismatch_are_closed(self):
        value=fixture();context=self.build(value)
        self.reject(value['source'],context,'PROTECTED_SCOPE_MISMATCH',scope_id=uid(2))
        self.reject(value['source'],context,'PROTECTED_SCOPE_MISMATCH',field='intro_text')

    def test_incomplete_or_wrong_top_level_context_is_invalid(self):
        value=fixture();context=self.build(value)
        for changed in (None,{},ProtectedContext(nodes=context.nodes),replace(context,nodes=list(context.nodes))):
            with self.subTest(kind=type(changed).__name__):
                self.reject(value['source'],changed,'POLICY_CONTEXT_INVALID')

    def test_nested_context_types_and_scalar_values_are_invalid(self):
        value=fixture();context=self.build(value);parent=context.parents[0];node=context.nodes[0]
        variants=[replace(context,source_sha256='not-a-hash'),replace(context,parents=(replace(parent,path=(True,)),)),
            replace(context,parents=(replace(parent,path=(-1,)),)),replace(context,nodes=(replace(node,width_px=True),)),
            replace(context,nodes=(replace(node,marker_id='INVALID'),)),replace(context,nodes=({},)),
            replace(context,parents=(replace(parent,ancestors=(('p',()),)),)),
            replace(context,parents=(replace(parent,sequence=(('slot',True),)),)),replace(context,nodes=context.nodes+context.nodes)]
        for index,changed in enumerate(variants):
            with self.subTest(index=index):self.reject(value['source'],changed)

    def test_source_hash_is_provenance_not_a_cryptographic_permission(self):
        value=fixture();context=self.build(value)
        # A different well-formed trusted provenance hash cannot be authenticated
        # from edited candidate HTML; the API has no original-source bytes/secret.
        alternate=replace(context,source_sha256='0'*64)
        self.assertEqual(self.normalize(value['source'],alternate).html,value['source'])

    def test_remove_duplicate_or_reorder_marker_is_whole_refusal(self):
        value=fixture(markers=2);context=self.build(value);first,second=value['marker_html']
        candidates=[value['source'].replace(first,''),value['source'].replace(first,first+first),
            value['source'].replace(first,'TEMP_MARKER').replace(second,first).replace('TEMP_MARKER',second)]
        for index,candidate in enumerate(candidates):
            with self.subTest(index=index):self.reject(candidate,context)

    def test_parent_slot_identity_order_boundaries_are_protected(self):
        value=fixture();context=self.build(value)
        candidates=[value['source'].replace(context.parents[0].parent_id,uid(999)),
            value['source'].replace(context.nodes[0].slot_before_id,uid(998)),
            value['source'].replace(value['slot_html'][0],''),
            value['source'].replace(value['slot_html'][0],value['slot_html'][0]+value['slot_html'][0]),
            value['source'].replace(value['slot_html'][0],'TEMP_SLOT').replace(value['slot_html'][1],value['slot_html'][0]).replace('TEMP_SLOT',value['slot_html'][1]),
            value['source'].replace(value['marker_html'][0],'<a href="/safe/">'+value['marker_html'][0]+'</a>')]
        for index,candidate in enumerate(candidates):
            with self.subTest(index=index):self.reject(candidate,context)

    def test_ancestor_format_parent_relocation_and_swap_are_protected(self):
        value=fixture(parents=2);context=self.build(value)
        for candidate in (value['source'].replace('data-es-align="left"','data-es-align="right"',1),
                          '<blockquote>'+value['source']+'</blockquote>',
                          ''.join(reversed(value['parent_html']))):
            self.reject(candidate,context)

    def test_path_only_structure_change_is_explicitly_unsupported(self):
        value=fixture();context=self.build(value)
        with patch('page_editor.clean.nh3.clean',wraps=nh3.clean) as cleaner:
            with self.assertRaises(ControlledUnsupported) as caught:
                self.normalize('<p>NEW STRUCTURE</p>'+value['source'],context)
            self.assertEqual(caught.exception.code,'PROTECTED_STRUCTURE_EDIT_UNSUPPORTED')
            cleaner.assert_not_called()
        self.reject('<p>NEW STRUCTURE</p>'+value['source']+'<script>bad()</script>',context)

    def test_employee_reference_and_image_metadata_tamper_denied(self):
        value=fixture();context=self.build(value);node=context.nodes[0]
        for old,new in ((node.asset_id,uid(997)),(node.image_id,uid(996)),('Image 😀 0:0','Altered alt'),
                        ('data-es-image-align="center"','data-es-image-align="left"'),
                        ('data-es-width="120"','data-es-width="121"'),('data-es-height="80"','data-es-height="81"')):
            with self.subTest(changed=new):self.reject(value['source'].replace(old,new),context)

    def test_owner_replacement_is_not_implemented_as_pure_permission(self):
        value=fixture();context=self.build(value)
        with self.assertRaises(ControlledUnsupported) as caught:
            self.normalize(value['source'].replace(context.nodes[0].asset_id,uid(995)),context,owner=True)
        self.assertEqual(caught.exception.code,'PROTECTED_INTEGRATION_UNSUPPORTED')

    def test_active_unknown_and_malformed_marker_source_before_native_clean(self):
        value=fixture();context=self.build(value);marker=value['marker_html'][0]
        for extra in (' onclick="bad()"',' src="https://example.invalid/x"',' style="position:fixed"',
                      ' data-es-unknown="1"',' data-es-slot="'+uid(994)+'"'):
            self.reject(value['source'].replace(marker,marker.replace('></span>',extra+'></span>')),context)
        self.reject(value['source'].replace(marker,marker.replace('></span>','>TEXT</span>')),context)
        self.reject(value['source'].replace('TEXT 0:0 😀','<script>bad()</script>'),context)
        self.reject(value['source'].replace('TEXT 0:0 😀','{{ request.user }}'),context)

    def test_native_cleaner_carrier_loss_never_succeeds(self):
        value=fixture();context=self.build(value);actual=nh3.clean
        def lossy(*args,**kwargs):
            return actual(*args,**kwargs).replace('data-es-asset="'+context.nodes[0].asset_id+'"','data-es-asset="'+uid(993)+'"')
        with patch('page_editor.clean.nh3.clean',side_effect=lossy):
            with self.assertRaises(PolicyError):self.normalize(value['source'],context)

    def test_builder_source_descriptor_hash_mismatch_and_noncanonical_are_not_repaired(self):
        value=fixture();bad=copy.deepcopy(value);bad['layout'][0]['protected_nodes'][0]['fingerprint']='0'*64
        with self.assertRaises(ControlledUnsupported) as caught:self.build(bad)
        self.assertEqual(caught.exception.code,'PROTECTED_SOURCE_AMBIGUOUS')
        bad=copy.deepcopy(value)
        # Noncanonical attribute spacing is semantically safe but the builder
        # must not silently rewrite the persisted source before hashing it.
        bad['source']=value['source'].replace('<p ','<p  ',1)
        with self.assertRaises(ControlledUnsupported) as caught:self.build(bad)
        self.assertEqual(caught.exception.code,'PROTECTED_SOURCE_AMBIGUOUS')

    def test_extreme_dimension_digits_fail_closed_before_native_clean(self):
        value=fixture();context=self.build(value)
        for attribute,old in (('width','120'),('height','80')):
            candidate=value['source'].replace('data-es-'+attribute+'="'+old+'"','data-es-'+attribute+'="'+'1'*5000+'"')
            with self.subTest(attribute=attribute):
                with patch('page_editor.clean.nh3.clean',wraps=nh3.clean) as cleaner:
                    with self.assertRaises(PolicyError):self.normalize(candidate,context)
                    cleaner.assert_not_called()

    def test_source_schema_bijection_and_reference_metadata_cannot_be_guessed(self):
        value=fixture()
        variants=[]
        wrong=copy.deepcopy(value);wrong['layout'][0]['field']='intro_text';variants.append(wrong)
        wrong=copy.deepcopy(value);wrong['layout'][0]['protected_nodes'][0]['reference_id']=uid(992);variants.append(wrong)
        wrong=copy.deepcopy(value);wrong['images'][0]['alt']='OTHER';variants.append(wrong)
        wrong=copy.deepcopy(value);wrong['layout'][0]['protected_nodes'].append(copy.deepcopy(wrong['layout'][0]['protected_nodes'][0]));variants.append(wrong)
        for index,wrong in enumerate(variants):
            with self.subTest(index=index),self.assertRaises(PolicyError):self.build(wrong)

    def test_builder_unhashable_trusted_descriptor_fields_fail_closed_before_clean(self):
        baseline=fixture()
        for kind in ('text-field','image-reference'):
            for invalid in ([],{}):
                value=copy.deepcopy(baseline)
                if kind=='text-field':
                    value['layout'][0]['field']=invalid
                else:
                    value['layout'].append({'id':uid(991),'kind':'image','image_id':invalid})
                with self.subTest(kind=kind,invalid_type=type(invalid).__name__):
                    with patch('page_editor.clean.nh3.clean',wraps=nh3.clean) as cleaner:
                        with self.assertRaises(PolicyError):self.build(value)
                        cleaner.assert_not_called()

    def test_builder_unsafe_source_never_reaches_native_clean(self):
        value=fixture();value['source']+='<script>BUILDER_UNSAFE_CANARY</script>'
        with patch('page_editor.clean.nh3.clean',wraps=nh3.clean) as cleaner:
            with self.assertRaises(PolicyError) as caught:self.build(value)
            self.assertNotIsInstance(caught.exception,ControlledUnsupported)
            cleaner.assert_not_called()


if __name__=='__main__':unittest.main()
