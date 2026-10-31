"""Bounded pure rich-text producer; no authentication, DB, IO or publication.

Call in the approved isolated child. Post-parse budgets do not replace its CPU,
wall and address-space limits. Recognised unfinished integrations fail closed.
"""
from decimal import Decimal, InvalidOperation
import hashlib
from html import escape
import re
import unicodedata
from uuid import UUID
from xml.etree import ElementTree as ET
import html5lib
from html5lib._tokenizer import HTMLTokenizer
from html5lib.constants import tokenTypes
import tinycss2
from . import clean
from .policy_constants import (POLICY_VERSION, MAX_SOURCE_BYTES, MAX_TEXT_CODEPOINTS,
    MAX_NODES, MAX_DEPTH, FIELDS, FONTS, FONT_FAMILIES, ALIGNMENTS, TAGS, ALIASES,
    BLOCK_FORMAT_TAGS, MARGIN_TAGS, FORMAT_ATTRS, MARGIN_ATTRS, MAX_UI_TABLE_SLOTS,
    PROTECTED_ATTRS, attributes_for)
from .types import (PolicyError, ControlledUnsupported, ProtectedContext, PolicyWarning,
    NormalizationResult, Metrics, Anchor)
from .urls import anchor_label, normalize_link, validate_context
from .tables import inspect_tables

HTML_NS='http://www.w3.org/1999/xhtml'
INLINE=frozenset({'br','strong','em','u','s','sub','sup','span','a'})
TEMPLATE_MARKERS=('{{','{%','{#')


def _error(code):raise PolicyError(code)


def _uuid(value):
    try:
        if type(value) is not str or str(UUID(value))!=value:_error('IDENTITY_INVALID')
    except (ValueError,AttributeError):_error('IDENTITY_INVALID')


def _string(value, *, multiline=False):
    if type(value) is not str:_error('INPUT_TYPE_INVALID')
    if any((ord(char)<32 and (not multiline or char not in '\n\t')) or ord(char)==127 for char in value):_error('INPUT_CONTROL_INVALID')
    if any(marker in value for marker in TEMPLATE_MARKERS):_error('TEMPLATE_FORBIDDEN')
    return unicodedata.normalize('NFC',value)


def _tag(node):
    if type(node.tag) is not str:_error('COMMENT_FORBIDDEN')
    if node.tag.startswith('{'):
        namespace,tag=node.tag[1:].split('}',1)
        if namespace!=HTML_NS:_error('FOREIGN_NAMESPACE_FORBIDDEN')
        return tag
    return node.tag


def _scan(value, owner):
    """Inspect tokens even if the HTML5 tree builder would discard them."""
    starts=0
    for token in HTMLTokenizer(value):
        kind=token['type']
        if kind==tokenTypes['ParseError']:
            error_code=token.get('data','')
            # Incomplete tokens can disappear entirely from the constructed
            # tree (including an unterminated script or dangerous href). Such
            # lexical EOF errors must not become a successful empty fragment.
            if 'eof' in error_code.lower() or error_code in {'duplicate-attribute','attributes-in-end-tag','invalid-codepoint','invalid-codepoint-in-attribute-name'}:
                _error('HTML_TOKEN_INVALID')
            continue
        if kind in (tokenTypes['Comment'],tokenTypes['Doctype']):_error('COMMENT_FORBIDDEN')
        if kind in (tokenTypes['StartTag'],tokenTypes['EmptyTag'],tokenTypes['EndTag']):
            tag=token['name']
            if tag not in TAGS and tag not in ALIASES:_error('TAG_FORBIDDEN')
            if tag=='h1' and not owner:_error('FIELD_FORBIDDEN')
            if kind==tokenTypes['EndTag'] and token.get('data'):_error('HTML_TOKEN_INVALID')
            if kind!=tokenTypes['EndTag']:
                starts+=1
                if starts>MAX_NODES:_error('NODE_LIMIT')
                for name,content in token.get('data',{}).items():
                    if type(name) is not str or name.startswith('on') or ':' in name:_error('ATTRIBUTE_FORBIDDEN')
                    _string(content,multiline=name=='style')
                    if name!='style' and name not in attributes_for(ALIASES.get(tag,tag)):_error('ATTRIBUTE_FORBIDDEN')


def _number(value, minimum, maximum, *, integer=False, px=False):
    candidate=value.strip()
    if px:
        if candidate.endswith('px'):candidate=candidate[:-2]
        elif candidate!='0':_error('CSS_VALUE_UNSUPPORTED')
    if not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?',candidate):_error('FORMAT_VALUE_INVALID')
    try:number=Decimal(candidate)
    except InvalidOperation:_error('FORMAT_VALUE_INVALID')
    if number<minimum or number>maximum or (integer and number!=number.to_integral_value()):_error('FORMAT_VALUE_INVALID')
    result=format(number,'f')
    if '.' in result:result=result.rstrip('0').rstrip('.')
    return result


def _colour(value, background=False):
    value=value.strip().lower()
    if background and value=='transparent':return value
    if re.fullmatch(r'#[0-9a-f]{3}',value):return '#'+''.join(char*2 for char in value[1:])
    if not re.fullmatch(r'#[0-9a-f]{6}',value):_error('FORMAT_VALUE_INVALID')
    return value


def _font(tokens):
    families=[];current=[]
    for token in tokens:
        if token.type=='literal' and token.value==',':
            if not current:_error('CSS_VALUE_UNSUPPORTED')
            families.append(' '.join(current).lower());current=[]
        elif token.type in ('ident','string'):current.append(token.value)
        elif token.type!='whitespace':_error('CSS_VALUE_UNSUPPORTED')
    if not current:_error('CSS_VALUE_UNSUPPORTED')
    families.append(' '.join(current).lower())
    for name,sequence in FONT_FAMILIES.items():
        if tuple(families)==sequence or families==[sequence[0]]:return name
    _error('FONT_UNSUPPORTED')


def _style(value, tag):
    """Return validated carrier attributes and semantic mark wrappers."""
    attributes={};marks=[];seen=set();unsupported=False
    for declaration in tinycss2.parse_declaration_list(value,skip_comments=True,skip_whitespace=True):
        if declaration.type!='declaration' or declaration.important:_error('CSS_UNSUPPORTED')
        name=declaration.lower_name
        if name in seen:_error('CSS_DUPLICATE_PROPERTY')
        seen.add(name)
        tokens=[token for token in declaration.value if token.type!='whitespace']
        if not tokens or any(token.type in ('error','url','function','at-keyword') for token in tokens):_error('CSS_UNSUPPORTED')
        raw=tinycss2.serialize(declaration.value).strip()
        if name=='font-family':attributes['data-es-font']=_font(declaration.value)
        elif name=='font-size':attributes['data-es-size']=_number(raw,8,72,px=True)
        elif name=='color':attributes['data-es-fg']=_colour(raw)
        elif name=='background-color':attributes['data-es-bg']=_colour(raw,True)
        elif name=='text-align':
            if tag not in BLOCK_FORMAT_TAGS|{'th','td'} or raw not in ALIGNMENTS:_error('CSS_VALUE_UNSUPPORTED')
            attributes['data-es-align']=raw
        elif name in {'margin-top','margin-right','margin-bottom','margin-left'}:
            if tag not in MARGIN_TAGS:_error('CSS_CONTEXT_UNSUPPORTED')
            attributes['data-es-m'+name[7]]=_number(raw,0,64,integer=True,px=True)
        elif name=='margin':
            if tag not in MARGIN_TAGS or not 1<=len(tokens)<=4:_error('CSS_CONTEXT_UNSUPPORTED')
            values=[_number(tinycss2.serialize([token]),0,64,integer=True,px=True) for token in tokens]
            top=values[0];right=values[1] if len(values)>1 else top
            bottom=values[2] if len(values)>2 else top;left=values[3] if len(values)>3 else right
            attributes.update(dict(zip(('data-es-mt','data-es-mr','data-es-mb','data-es-ml'),(top,right,bottom,left))))
        elif name=='font-weight':
            if raw in ('bold','700'):marks.append('strong')
            elif raw not in ('normal','400'):_error('CSS_VALUE_UNSUPPORTED')
            else:unsupported=True
        elif name=='font-style':
            if raw=='italic':marks.append('em')
            elif raw!='normal':_error('CSS_VALUE_UNSUPPORTED')
            else:unsupported=True
        elif name in ('text-decoration','text-decoration-line'):
            values=raw.split()
            if values==['none']:
                unsupported=True
            elif len(values)!=len(set(values)) or not set(values)<= {'underline','line-through'}:_error('CSS_VALUE_UNSUPPORTED')
            else:
                if 'underline' in values:marks.append('u')
                if 'line-through' in values:marks.append('s')
        elif name=='vertical-align':
            if raw in ('sub','super'):marks.append('sub' if raw=='sub' else 'sup')
            elif raw!='baseline':_error('CSS_VALUE_UNSUPPORTED')
            else:unsupported=True
        else:_error('CSS_PROPERTY_UNSUPPORTED')
    if unsupported:raise ControlledUnsupported('STYLE_CONTEXT_UNSUPPORTED')
    return attributes,marks


def _check_attributes(tag, attributes):
    for name,value in list(attributes.items()):
        if name not in attributes_for(tag):_error('ATTRIBUTE_FORBIDDEN')
        value=_string(value)
        if name=='data-es-font' and value not in FONTS:_error('FONT_UNSUPPORTED')
        elif name=='data-es-size':value=_number(value,8,72)
        elif name=='data-es-fg':value=_colour(value)
        elif name=='data-es-bg':value=_colour(value,True)
        elif name=='data-es-align' and value not in ALIGNMENTS:_error('FORMAT_VALUE_INVALID')
        elif name in MARGIN_ATTRS:value=_number(value,0,64,integer=True)
        elif name=='data-es-cellpad':value=_number(value,0,32,integer=True)
        elif name in {'rowspan','colspan'}:
            if not re.fullmatch(r'[1-9][0-9]*',value):_error('TABLE_SPAN_INVALID')
        elif name=='scope' and value not in {'row','col','rowgroup','colgroup'}:_error('TABLE_SCOPE_INVALID')
        elif name in PROTECTED_ATTRS:
            if name=='data-es-alt':
                if len(value)>300:_error('IMAGE_ALT_LIMIT')
            elif name=='data-es-image-align':
                if value not in {'left','center','right'}:_error('FORMAT_VALUE_INVALID')
            elif name in {'data-es-width','data-es-height'}:
                if not re.fullmatch(r'[1-9][0-9]*',value):_error('FORMAT_VALUE_INVALID')
            else:_uuid(value)
        elif name=='data-es-anchor':value=anchor_label(value)
        attributes[name]=value


def _wrap_content(node,tag,attributes=None):
    wrapper=ET.Element('{'+HTML_NS+'}'+tag,attributes or {})
    wrapper.text=node.text;node.text=None
    for child in list(node):node.remove(child);wrapper.append(child)
    node.append(wrapper)


def _metrics(tree,source_bytes):
    count=0;depth_max=0;text_count=len(tree.text or '')
    stack=[(child,1) for child in reversed(list(tree))]
    while stack:
        node,depth=stack.pop();_tag(node);count+=1;depth_max=max(depth_max,depth)
        if count>MAX_NODES:_error('NODE_LIMIT')
        if depth>MAX_DEPTH:_error('DEPTH_LIMIT')
        text_count+=len(node.text or '')+len(node.tail or '')
        if text_count>MAX_TEXT_CODEPOINTS:_error('TEXT_LIMIT')
        stack.extend((child,depth+1) for child in reversed(list(node)))
    if text_count>MAX_TEXT_CODEPOINTS:_error('TEXT_LIMIT')
    return Metrics(source_bytes,text_count,count,depth_max)


def _serialize(tree):
    def node_html(node):
        tag=_tag(node)
        attributes=''.join(' '+name+'="'+escape(value,quote=True)+'"' for name,value in sorted(node.attrib.items()))
        start='<'+tag+attributes+'>'
        if tag=='br':return start
        return start+escape(node.text or '',quote=False)+''.join(node_html(child)+escape(child.tail or '',quote=False) for child in node)+'</'+tag+'>'
    return escape(tree.text or '',quote=False)+''.join(node_html(child)+escape(child.tail or '',quote=False) for child in tree)


def _signature(tree):
    def node_signature(node):
        return (_tag(node),tuple(sorted(node.attrib.items())),node.text or '',tuple((node_signature(child),child.tail or '') for child in node))
    return (tree.text or '',tuple((node_signature(child),child.tail or '') for child in tree))


def normalize_html(value: str, *, owner: bool, field: str, scope_id: str,
                   protected_context: ProtectedContext, url_context=None,
                   table_budget_remaining=MAX_UI_TABLE_SLOTS) -> NormalizationResult:
    if type(owner) is not bool or type(field) is not str or field not in FIELDS or not isinstance(protected_context,ProtectedContext) or type(protected_context.nodes) is not tuple:_error('POLICY_CONTEXT_INVALID')
    _uuid(scope_id)
    if url_context is not None:validate_context(url_context)
    if type(table_budget_remaining) is not int or not 0<=table_budget_remaining<=MAX_UI_TABLE_SLOTS:_error('TABLE_BUDGET_INVALID')
    if type(value) is not str:_error('INPUT_TYPE_INVALID')
    try:source=value.encode('utf-8')
    except UnicodeError:_error('UTF8_INVALID')
    if len(source)>MAX_SOURCE_BYTES:_error('SOURCE_BYTE_LIMIT')
    candidate=_string(value.replace('\r\n','\n').replace('\r','\n'),multiline=True)
    _scan(candidate,owner)
    tree=html5lib.parseFragment(candidate,treebuilder='etree',namespaceHTMLElements=True)
    source_metrics=_metrics(tree,len(source))
    anchors=[];anchor_links=[];unsupported=set();warnings=set()
    tree.text=_string(tree.text or '',multiline=True)
    # Original nodes are fixed before adding any trusted format wrappers.
    nodes=list(tree.iter())[1:]
    for node in reversed(nodes):
        tag=_tag(node)
        if tag in ALIASES:
            tag=ALIASES[tag];node.tag='{'+HTML_NS+'}'+tag
        if tag not in TAGS:_error('TAG_FORBIDDEN')
        if tag=='h1' and not owner:_error('FIELD_FORBIDDEN')
        node.text=_string(node.text or '',multiline=True);node.tail=_string(node.tail or '',multiline=True)
        attributes=dict(node.attrib);styles=attributes.pop('style',None);marks=[]
        if styles is not None:
            try:converted,marks=_style(styles,tag)
            except ControlledUnsupported as exc:unsupported.add(exc.code);converted={};marks=[]
            for key,item in converted.items():
                if key in attributes and attributes[key]!=item:_error('FORMAT_CONFLICT')
            inline={key:item for key,item in converted.items() if key in FORMAT_ATTRS}
            normal={key:item for key,item in converted.items() if key not in FORMAT_ATTRS}
            attributes.update(normal)
            if inline:
                if tag=='span':attributes.update(inline)
                elif all(_tag(child) in INLINE for child in node):_wrap_content(node,'span',inline)
                else:unsupported.add('STYLE_CONTEXT_UNSUPPORTED')
            if marks:
                if all(_tag(child) in INLINE for child in node):
                    for mark in reversed(marks):_wrap_content(node,mark)
                else:unsupported.add('STYLE_CONTEXT_UNSUPPORTED')
        _check_attributes(tag,attributes)
        if tag=='a':
            try:
                attributes,link=normalize_link(attributes,field=field,context=url_context)
                if link:anchor_links.append(link)
            except ControlledUnsupported as exc:unsupported.add(exc.code)
        if 'data-es-anchor' in attributes:anchors.append(Anchor(attributes['data-es-anchor'],field))
        if any(name in PROTECTED_ATTRS for name in attributes):unsupported.add('PROTECTED_INTEGRATION_UNSUPPORTED')
        node.attrib.clear();node.attrib.update(attributes)
    if len({anchor.label for anchor in anchors})!=len(anchors):_error('ANCHOR_DUPLICATE')
    table_capabilities=inspect_tables(tree,remaining_budget=table_budget_remaining)
    if protected_context.nodes:unsupported.add('PROTECTED_INTEGRATION_UNSUPPORTED')
    if unsupported:raise ControlledUnsupported(sorted(unsupported)[0])
    _metrics(tree,len(source));canonical=_serialize(tree)
    if len(canonical.encode('utf-8'))>MAX_SOURCE_BYTES:_error('NORMALIZED_BYTE_LIMIT')
    # All original source has been validated before the only native clean call.
    cleaned=clean.restricted_clean(canonical)
    checked=html5lib.parseFragment(cleaned,treebuilder='etree',namespaceHTMLElements=True)
    _metrics(checked,len(source))
    if _signature(checked)!=_signature(tree):_error('SANITIZER_DIVERGENCE')
    final=_serialize(checked)
    recleaned=clean.restricted_clean(final)
    reparsed=html5lib.parseFragment(recleaned,treebuilder='etree',namespaceHTMLElements=True)
    _metrics(reparsed,len(source))
    if _signature(reparsed)!=_signature(checked) or _serialize(reparsed)!=final:_error('SERIALIZATION_UNSTABLE')
    if final!=value:warnings.add('NORMALIZATION_REVIEW_REQUIRED')
    known={anchor.label for anchor in anchors}
    if any(link.field==field and link.anchor not in known for link in anchor_links):warnings.add('ANCHOR_TARGET_UNRESOLVED')
    return NormalizationResult(POLICY_VERSION,final,final!=value,
        tuple(PolicyWarning(code,field) for code in sorted(warnings)),hashlib.sha256(source).hexdigest(),
        hashlib.sha256(final.encode('utf-8')).hexdigest(),source_metrics,
        tuple(reversed(anchors)),tuple(reversed(anchor_links)),(),table_capabilities,
        sum(fact.virtual_slots for fact in table_capabilities if fact.rich_widget))
