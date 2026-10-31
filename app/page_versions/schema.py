"""Closed storage DTOs, not a rich-HTML sanitizer or public payload writer."""
import copy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from uuid import UUID
from django.core.exceptions import ValidationError
from content.models import Page

SCHEMA='page-content-v1'
KEYS={'schema_version','page_kind','intro_text','main_text','price','h1','title','description','indexing_allowed',
      'main_image','preview_image','embedded_images','layout'}
OWNER_FIELDS=KEYS-{'schema_version','page_kind'}
EMPLOYEE_FIELDS={'intro_text','main_text','price'}


def invalid():raise ValidationError('VERSIONS_INVALID_SNAPSHOT')


def canonical(value):
    try:return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    except (TypeError,ValueError,UnicodeError):invalid()


def digest(value):
    try:return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()
    except UnicodeError:invalid()


def keys(value,expected):
    if type(value) is not dict or set(value)!=set(expected):invalid()


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:invalid()
        result[key]=value
    return result


def identifier(value):
    try:
        if type(value) is not str or str(UUID(value))!=value:invalid()
    except (ValueError,TypeError,AttributeError):invalid()
    return value


def text(value,limit=None,multiline=False):
    if type(value) is not str or (limit is not None and len(value)>limit):invalid()
    try:value.encode('utf-8')
    except UnicodeError:invalid()
    if any(ord(char)<32 and (not multiline or char not in '\n\t') for char in value):invalid()
    return value


def _image(value,embedded=False):
    expected={'asset_id','alt','alignment','width_px','height_px'}|({'id'} if embedded else set())
    keys(value,expected);identifier(value['asset_id']);text(value['alt'],300)
    if embedded:identifier(value['id'])
    if value['alignment'] not in ('left','center','right'):invalid()
    for name in ['width_px','height_px']:
        if value[name] is not None and (type(value[name]) is not int or value[name]<=0):invalid()


def _price(value):
    if value is None:return
    keys(value,{'columns','rows'})
    if type(value['columns']) is not list or type(value['rows']) is not list or len(value['columns'])>32 or len(value['rows'])>500:invalid()
    columns=set();rows=set();count=0
    for column in value['columns']:
        keys(column,{'id','label'});identifier(column['id']);text(column['label'],500)
        if column['id'] in columns:invalid()
        columns.add(column['id'])
    for row in value['rows']:
        keys(row,{'id','label','cells'});identifier(row['id']);text(row['label'],500)
        if row['id'] in rows or type(row['cells']) is not list:invalid()
        rows.add(row['id']);seen=set()
        for cell in row['cells']:
            if type(cell) is not dict:invalid()
            kind=cell.get('kind')
            if kind=='text':keys(cell,{'column_id','kind','text'});text(cell['text'],1000,multiline=True)
            elif kind=='amount':
                keys(cell,{'column_id','kind','amount','from'})
                if type(cell['from']) is not bool or type(cell['amount']) is not str or not re.fullmatch(r'(0|[1-9][0-9]{0,8})(\.[0-9]{1,2})?',cell['amount']):invalid()
                try:
                    if Decimal(cell['amount'])>Decimal('999999999.99'):invalid()
                except InvalidOperation:invalid()
            else:invalid()
            identifier(cell['column_id'])
            if cell['column_id'] not in columns or cell['column_id'] in seen:invalid()
            seen.add(cell['column_id']);count+=1
    if count>10000:invalid()


def validate(payload,page_kind=None):
    keys(payload,KEYS)
    if payload['schema_version']!=SCHEMA or payload['page_kind'] not in Page.Kind.values or (page_kind is not None and payload['page_kind']!=page_kind):invalid()
    for field in ['intro_text','main_text']:
        text(payload[field],multiline=True)
        if len(payload[field].encode('utf-8'))>1024*1024:invalid()
    text(payload['h1'],255);text(payload['title'],255);text(payload['description'],1000,multiline=True)
    if type(payload['indexing_allowed']) is not bool:invalid()
    _price(payload['price'])
    for field in ['main_image','preview_image']:
        if payload[field] is not None:_image(payload[field])
    if type(payload['embedded_images']) is not list or type(payload['layout']) is not list:invalid()
    images=set()
    for image in payload['embedded_images']:
        _image(image,embedded=True)
        if image['id'] in images:invalid()
        images.add(image['id'])
    blocks=set();protected_references=set()
    for node in payload['layout']:
        if type(node) is not dict:invalid()
        kind=node.get('kind')
        if kind=='text':
            keys(node,{'id','kind','field','protected_nodes'})
            if node['field'] not in ('intro_text','main_text') or type(node['protected_nodes']) is not list:invalid()
            seen=set()
            for protected in node['protected_nodes']:
                keys(protected,{'id','reference_id','fingerprint'});identifier(protected['id']);identifier(protected['reference_id'])
                if protected['id'] in seen or type(protected['fingerprint']) is not str or not re.fullmatch('[a-f0-9]{64}',protected['fingerprint']):invalid()
                seen.add(protected['id'])
        elif kind=='price':keys(node,{'id','kind'})
        elif kind=='image':
            keys(node,{'id','kind','image_id'});identifier(node['image_id'])
            if node['image_id'] not in images:invalid()
        elif kind=='protected_ref':
            keys(node,{'id','kind','reference_id','fingerprint'});identifier(node['reference_id'])
            if type(node['fingerprint']) is not str or not re.fullmatch('[a-f0-9]{64}',node['fingerprint']):invalid()
            protected_references.add(node['reference_id'])
        else:invalid()
        identifier(node['id'])
        if node['id'] in blocks:invalid()
        blocks.add(node['id'])
    for node in payload['layout']:
        if node['kind']=='text' and any(item['reference_id'] not in images|protected_references for item in node['protected_nodes']):invalid()
    return copy.deepcopy(payload)


@dataclass(frozen=True)
class Snapshot:
    """Only a trusted normalized producer constructs this, never an HTTP JSON body."""
    encoded:str
    @classmethod
    def trusted(cls,payload,page_kind=None):return cls(canonical(validate(payload,page_kind)))
    def data(self,page_kind=None):
        try:return validate(json.loads(self.encoded,object_pairs_hook=_pairs),page_kind)
        except (ValueError,TypeError,RecursionError,UnicodeError):invalid()


_MISSING=object()


@dataclass(frozen=True)
class TextPricePatch:
    intro_text:object=_MISSING
    main_text:object=_MISSING
    price:object=_MISSING
    def changes(self):return {key:copy.deepcopy(getattr(self,key)) for key in EMPLOYEE_FIELDS if getattr(self,key) is not _MISSING}


def snapshot_v1(page_kind,*,intro_text='',main_text='',price=None,h1='',title='',description='',indexing_allowed=True,
                main_image=None,preview_image=None,embedded_images=None,layout=None):
    return Snapshot.trusted({'schema_version':SCHEMA,'page_kind':page_kind,'intro_text':intro_text,'main_text':main_text,'price':price,
        'h1':h1,'title':title,'description':description,'indexing_allowed':indexing_allowed,'main_image':main_image,'preview_image':preview_image,
        'embedded_images':[] if embedded_images is None else embedded_images,'layout':[] if layout is None else layout},page_kind)


def asset_slots(payload):
    result={}
    for name in ['main_image','preview_image']:
        if payload[name] is not None:result[name]=payload[name]['asset_id']
    for image in payload['embedded_images']:result['embedded:'+image['id']]=image['asset_id']
    return result
