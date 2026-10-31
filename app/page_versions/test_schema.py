"""Closed DTO/field boundary tests; no sanitizer/editor acceptance claim."""
import copy
from uuid import uuid4
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from content.models import Page
from . import schema


class SnapshotSchemaTests(SimpleTestCase):
    def test_manual_metadata_controls_before_strip_and_normalized_lengths(self):
        from .engine import metadata_values
        for name in ['Name\n','\nName','Name\t','\tName','Name\r','Name\0']:
            with self.subTest(name=name),self.assertRaises(ValidationError):metadata_values(name=name)
        self.assertEqual(metadata_values(name='  '+'Я'*200+'  ')['name'],'Я'*200)
        self.assertEqual(metadata_values(name='e\u0301'*200)['name'],'é'*200)
        with self.assertRaises(ValidationError):metadata_values(name=' '+'Я'*201+' ')
        comment='first\r\nsecond\rthird\nlast\t'
        self.assertEqual(metadata_values(comment=comment)['comment'],'first\nsecond\nthird\nlast\t')
        self.assertEqual(metadata_values(comment='x\r\n'*500)['comment'],'x\n'*500)
        with self.assertRaises(ValidationError):metadata_values(comment='a\x01')
        with self.assertRaises(ValidationError):metadata_values(comment='x\r\n'*501)

    def test_optional_lists_accept_only_none_or_actual_lists(self):
        for key in ['embedded_images','layout']:
            for value in [None,[]]:
                with self.subTest(key=key,value=value):
                    self.assertEqual(schema.snapshot_v1(Page.Kind.ARTICLE,**{key:value}).data()[key],[])
            for value in [{},'',0,False]:
                with self.subTest(key=key,value=value),self.assertRaises(ValidationError):
                    schema.snapshot_v1(Page.Kind.ARTICLE,**{key:value})

    def test_exact_snapshot_keys_and_duplicate_json_denied(self):
        original=schema.snapshot_v1(Page.Kind.ARTICLE,main_text='<p>trusted normalized text</p>').data()
        for key in ['url','is_published','owner_draft','stable','template_code']:
            value=copy.deepcopy(original);value[key]='forbidden'
            with self.subTest(key=key),self.assertRaises(ValidationError):schema.Snapshot.trusted(value)
        duplicated=schema.canonical(original)[:-1]+',"h1":"duplicate"}'
        with self.assertRaises(ValidationError):schema.Snapshot(duplicated).data()

    def test_h1_title_description_exact_boundaries_and_empty(self):
        for key,limit in [('h1',255),('title',255),('description',1000)]:
            for count in [0,limit]:
                self.assertEqual(schema.snapshot_v1(Page.Kind.ARTICLE,**{key:'Я'*count}).data()[key],'Я'*count)
            with self.assertRaises(ValidationError):schema.snapshot_v1(Page.Kind.ARTICLE,**{key:'Я'*(limit+1)})

    def test_price_typed_amounts_do_not_coerce_text_to_zero_or_float(self):
        column=str(uuid4());row=str(uuid4())
        price={'columns':[{'id':column,'label':'Цена'}],'rows':[{'id':row,'label':'Проверка','cells':[{'column_id':column,'kind':'text','text':'по запросу'}]}]}
        result=schema.snapshot_v1(Page.Kind.ARTICLE,price=price).data()['price']
        self.assertEqual(result,price)
        for value in [0.1,-1,'NaN','1000000000.00','1.001']:
            changed=copy.deepcopy(price);changed['rows'][0]['cells']=[{'column_id':column,'kind':'amount','amount':value,'from':False}]
            with self.subTest(value=value),self.assertRaises(ValidationError):schema.snapshot_v1(Page.Kind.ARTICLE,price=changed)
        price['rows'][0]['cells']=[{'column_id':column,'kind':'amount','amount':'999999999.99','from':True}]
        self.assertEqual(schema.snapshot_v1(Page.Kind.ARTICLE,price=price).data()['price'],price)
