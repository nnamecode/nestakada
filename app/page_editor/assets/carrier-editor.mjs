// D-330 pinned packages only. This adapter is not server admission or a sanitizer.
import { Editor, Node, Mark, Extension } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { Plugin } from '@tiptap/pm/state';

const FONTS = Object.freeze({inter:'Inter,Arial,sans-serif',oswald:'Oswald,Arial,sans-serif',arial:'Arial,sans-serif',georgia:'Georgia,serif','times-new-roman':'"Times New Roman",serif','courier-new':'"Courier New",monospace'});
const FORMAT = ['font','size','fg','bg'];
const BLOCK = ['align','mt','mr','mb','ml','anchor'];
const ATTR = {font:'data-es-font',size:'data-es-size',fg:'data-es-fg',bg:'data-es-bg',align:'data-es-align',mt:'data-es-mt',mr:'data-es-mr',mb:'data-es-mb',ml:'data-es-ml',anchor:'data-es-anchor'};
const TAG_MARK = {strong:'bold',em:'italic',u:'underline',s:'strike',sub:'subscript',sup:'superscript'};
const MARK_TAG = Object.fromEntries(Object.entries(TAG_MARK).map(([tag,name])=>[name,tag]));
const INLINE_TAGS = new Set(['br','strong','em','u','s','sub','sup','span','a']);
const BLOCK_TAGS = new Set(['p','h1','h2','h3','blockquote','ul','ol','li','table']);
const escapeText = value => String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const escapeAttr = value => escapeText(value).replaceAll('"','&quot;').replaceAll("'",'&#x27;');
const failure = code => { const error = new Error(code); error.code=code; throw error; };
const VISUAL_UNSUPPORTED = new Set(['EDITOR_PROTECTED_OR_UNSUPPORTED','EDITOR_EMPTY_ANCHOR_UNSUPPORTED','EDITOR_NESTED_ANCHOR_UNSUPPORTED','EDITOR_LIST_UNSUPPORTED','EDITOR_EMPTY_LIST_UNSUPPORTED','EDITOR_BLOCK_UNSUPPORTED','EDITOR_INLINE_UNSUPPORTED']);
const blank = names => Object.fromEntries(names.map(name=>[name,null]));
function uuid(){const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;const hex=[...bytes].map(value=>value.toString(16).padStart(2,'0')).join('');return hex.slice(0,8)+'-'+hex.slice(8,12)+'-'+hex.slice(12,16)+'-'+hex.slice(16,20)+'-'+hex.slice(20);}

function decimal(value) {
  if(typeof value!=='string'||! /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(value))failure('EDITOR_FORMAT_INVALID');
  let [whole,fraction='']=value.split('.'); fraction=fraction.replace(/0+$/,'');
  if(whole.length>2||Number(whole)<8||Number(whole)>72||(whole==='72'&&fraction))failure('EDITOR_FORMAT_INVALID');
  return whole+(fraction?'.'+fraction:'');
}
function integer(value,max) {
  const text=String(value);
  if(!/^(?:0|[1-9][0-9]*)$/.test(text)||text.length>2||Number(text)>max)failure('EDITOR_FORMAT_INVALID');
  return text;
}
function color(value,background=false) {
  if(typeof value!=='string')failure('EDITOR_FORMAT_INVALID');
  value=value.toLowerCase();if(background&&value==='transparent')return value;
  if(/^#[0-9a-f]{3}$/.test(value))value='#'+[...value.slice(1)].map(char=>char+char).join('');
  if(!/^#[0-9a-f]{6}$/.test(value))failure('EDITOR_FORMAT_INVALID');return value;
}
function validateAttrs(attrs,names) {
  const result=blank(names);
  for(const name of names) {
    let value=attrs[name];if(value===null||value===undefined)continue;
    if(name==='font'){if(!Object.hasOwn(FONTS,value))failure('EDITOR_FORMAT_INVALID');}
    else if(name==='size')value=decimal(String(value));
    else if(name==='fg'||name==='bg')value=color(value,name==='bg');
    else if(name==='align'){if(!['left','center','right','justify'].includes(value))failure('EDITOR_FORMAT_INVALID');}
    else if(['mt','mr','mb','ml'].includes(name))value=integer(value,64);
    else if(name==='anchor'){if(typeof value!=='string'||!value||/[\x00-\x1f\x7f]/.test(value))failure('EDITOR_ANCHOR_INVALID');}
    result[name]=value;
  }
  return result;
}
function carrierAttrs(attrs,names) {
  const checked=validateAttrs(attrs,names),output={};
  for(const name of names)if(checked[name]!==null)output[ATTR[name]]=checked[name];
  return output;
}
function htmlAttrs(attrs) {
  return Object.entries(attrs).filter(([,value])=>value!==null&&value!==undefined).sort(([a],[b])=>a.localeCompare(b,'en')).map(([name,value])=>' '+name+'="'+escapeAttr(value)+'"').join('');
}
function styleFacts(attrs,names) {
  const checked=validateAttrs(attrs,names),facts={};
  if(checked.font)facts['font-family']=FONTS[checked.font];
  if(checked.size)facts['font-size']=checked.size+'px';
  if(checked.fg)facts.color=checked.fg;
  if(checked.bg)facts['background-color']=checked.bg;
  if(checked.align)facts['text-align']=checked.align;
  for(const [name,property] of [['mt','margin-top'],['mr','margin-right'],['mb','margin-bottom'],['ml','margin-left']])if(checked[name]!==null&&checked[name]!==undefined)facts[property]=checked[name]+'px';
  return facts;
}

class Rules {
  constructor(sheet,onFault) {
    if(!sheet||!sheet.ownerNode||sheet.ownerNode.tagName!=='LINK')failure('EDITOR_STYLESHEET_REQUIRED');
    const url=new URL(sheet.ownerNode.href,location.href);
    if(url.origin!==location.origin)failure('EDITOR_STYLESHEET_REQUIRED');
    try{void sheet.cssRules;}catch{failure('EDITOR_STYLESHEET_REQUIRED');}
    this.sheet=sheet;this.onFault=onFault;this.scope='esf-'+uuid().replaceAll('-','');this.next=0;this.entries=new Map();
  }
  key(facts){return JSON.stringify(Object.entries(facts).sort(([a],[b])=>a.localeCompare(b,'en')));}
  ensure(facts) {
    try{return this.ensureRule(facts);}catch(error){this.onFault?.(error);throw error;}
  }
  ensureRule(facts) {
    if(!Object.keys(facts).length)return '';
    const key=this.key(facts);let entry=this.entries.get(key);
    if(!entry){
      if(!Number.isSafeInteger(this.next)||this.entries.size>=40000)failure('EDITOR_RULE_BUDGET');
      const className=this.scope+'-n'+this.next++;const index=this.sheet.insertRule('.'+className+'{}',this.sheet.cssRules.length);
      const rule=this.sheet.cssRules[index];for(const [name,value] of Object.entries(facts))rule.style.setProperty(name,value);
      entry={className,rule};this.entries.set(key,entry);
    }
    return entry.className;
  }
  refresh(doc) {
    const active=new Set();let nodes=0;
    doc.descendants(node=>{
      if(++nodes>40000)failure('EDITOR_NODE_BUDGET');
      for(const [attrs,names] of [[node.attrs,BLOCK],...node.marks.filter(mark=>mark.type.name==='esFormat').map(mark=>[mark.attrs,FORMAT])]){
        const facts=styleFacts(attrs,names);if(!Object.keys(facts).length)continue;
        const key=this.key(facts);active.add(key);this.ensure(facts);
      }
    });
    for(const [key,entry] of this.entries)if(!active.has(key)){this.remove(entry);this.entries.delete(key);}
  }
  remove(entry){const index=Array.from(this.sheet.cssRules).indexOf(entry.rule);if(index>=0)this.sheet.deleteRule(index);}
  destroy(){for(const entry of this.entries.values())this.remove(entry);this.entries.clear();}
}

function attrsDefinition(names) {
  return Object.fromEntries(names.map(name=>[name,{default:null,parseHTML:element=>element.getAttribute(ATTR[name]),renderHTML:attrs=>carrierAttrs(attrs,[name])}]));
}
function setNodeDom(dom,node,rules) {
  const attrs=carrierAttrs(node.attrs,BLOCK),className=rules.ensure(styleFacts(node.attrs,BLOCK));
  for(const attribute of Array.from(dom.attributes))if(attribute.name.startsWith('data-es-'))dom.removeAttribute(attribute.name);
  for(const [name,value] of Object.entries(attrs))dom.setAttribute(name,value);
  dom.className=className;
}

function extensionsFor({owner,rules,approvedTables,requestHtml}) {
  function blockNode(name,tag,content,extra={}) {
    return Node.create({name,group:'block',content,...extra,
      addAttributes:()=>({...attrsDefinition(BLOCK),...(name==='paragraph'?{esUnwrapped:{default:false,rendered:false}}:{}),...(name==='heading'?{level:{default:2,rendered:false}}:{})}),
      parseHTML:()=>name==='heading'?[1,2,3].filter(level=>owner||level!==1).map(level=>({tag:'h'+level,attrs:{level}})):[{tag}],
      renderHTML:({node})=>[name==='heading'?'h'+node.attrs.level:tag,carrierAttrs(node.attrs,BLOCK),0],
      addNodeView:()=>({node})=>{
        let current=node;const actualTag=name==='heading'?'h'+node.attrs.level:tag;const dom=document.createElement(actualTag);setNodeDom(dom,node,rules);
        return {dom,contentDOM:dom,update(next){if(next.type!==current.type||(name==='heading'&&next.attrs.level!==current.attrs.level))return false;current=next;setNodeDom(dom,next,rules);return true;}};
      },
    });
  }
  const marks=Object.entries(MARK_TAG).map(([name,tag])=>Mark.create({name,parseHTML:()=>[{tag}],renderHTML:()=>[tag,{},0]}));
  const format=Mark.create({name:'esFormat',addAttributes:()=>attrsDefinition(FORMAT),parseHTML:()=>[{tag:'span',getAttrs:element=>FORMAT.some(name=>element.hasAttribute(ATTR[name]))?{}:false}],
    renderHTML:({mark})=>['span',carrierAttrs(mark.attrs,FORMAT),0],
    addMarkView:()=>({mark})=>{const dom=document.createElement('span');dom.className=rules.ensure(styleFacts(mark.attrs,FORMAT));return {dom,contentDOM:dom};},
  });
  const anchor=Mark.create({name:'esAnchor',inclusive:false,addAttributes:()=>({label:{default:null}}),parseHTML:()=>[{tag:'span[data-es-anchor]',getAttrs:element=>({label:element.getAttribute('data-es-anchor')})}],renderHTML:({mark})=>['span',{'data-es-anchor':mark.attrs.label},0]});
  const link=Mark.create({name:'esLink',inclusive:false,addAttributes:()=>Object.fromEntries(['href','title','target','rel','data-es-target-field','data-es-target-anchor'].map(name=>[name,{default:null}])),parseHTML:()=>[{tag:'a'}],
    renderHTML:({mark})=>['a',Object.fromEntries(Object.entries(mark.attrs).filter(([,value])=>value!==null)),0],
  });
  const opaque=Node.create({name:'esOpaqueTable',group:'block',atom:true,selectable:true,
    addAttributes:()=>({approvedHtml:{default:''}}),parseHTML:()=>[],renderHTML:()=>['div',{'data-editor-opaque-table':''}],
    addNodeView:()=>({node})=>{
      if(!approvedTables.has(node.attrs.approvedHtml))failure('EDITOR_APPROVED_TABLE_REQUIRED');
      const dom=document.createElement('div');dom.className='es-opaque-table';dom.contentEditable='false';
      const message=document.createElement('p');message.textContent='Таблица сохранена целиком. Редактирование доступно в HTML-режиме.';
      const button=document.createElement('button');button.type='button';button.textContent='Редактировать HTML';button.addEventListener('click',()=>requestHtml());
      const details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent='Показать HTML таблицы';pre.textContent=node.attrs.approvedHtml;details.append(summary,pre);dom.append(message,button,details);return {dom};
    },
  });
  const safety=Extension.create({name:'esNoDefaultPaste',addProseMirrorPlugins:()=>[new Plugin({props:{handleDOMEvents:{dragstart:(view,event)=>{event.preventDefault();return true;}}}})]});
  return [StarterKit.configure({paragraph:false,heading:false,blockquote:false,bulletList:false,orderedList:false,listItem:false,bold:false,italic:false,underline:false,strike:false,link:false,code:false,codeBlock:false,horizontalRule:false,dropcursor:false,gapcursor:false,trailingNode:false}),
    blockNode('paragraph','p','inline*'),blockNode('heading','h2','inline*'),blockNode('blockquote','blockquote','block+'),blockNode('bulletList','ul','listItem+'),blockNode('orderedList','ol','listItem+'),
    Node.create({name:'listItem',content:'paragraph block*',defining:true,parseHTML:()=>[{tag:'li'}],renderHTML:()=>['li',{},0]}),...marks,format,anchor,link,opaque,safety];
}

function approvedTableSlices(html) {
  const slices=[];const stack=[];const pattern=/<\/?table\b[^>]*>/g;let match;
  while((match=pattern.exec(html))){
    if(match[0].startsWith('</')){const item=stack.pop();if(!item)failure('EDITOR_CANONICAL_TABLE_INVALID');slices[item.index]=html.slice(item.start,pattern.lastIndex);}
    else {const item={start:match.index,index:slices.length};slices.push(null);stack.push(item);}
  }
  if(stack.length||slices.some(value=>value===null))failure('EDITOR_CANONICAL_TABLE_INVALID');return slices;
}

function approvedDocument(html,{owner,approvedTables}) {
  if(typeof html!=='string'||new TextEncoder().encode(html).length>1048576)failure('EDITOR_APPROVED_INPUT_REQUIRED');
  // Only server-approved strings reach this inert parser. Raw input has no path
  // to this function. The server policy, not this adapter, performs sanitation.
  if(/<\/?(?:script|style|iframe|object|embed|img|svg|math|form|input|button|textarea|select|link|meta|base)\b/i.test(html))failure('EDITOR_APPROVED_INPUT_REQUIRED');
  const documentValue=new DOMParser().parseFromString(html,'text/html');
  if(documentValue.querySelector('[style],[class],[id]'))failure('EDITOR_APPROVED_INPUT_REQUIRED');
  if(documentValue.querySelector('[data-es-protected],[data-es-image],[data-es-parent],[data-es-slot]'))failure('EDITOR_PROTECTED_OR_UNSUPPORTED');
  const tables=approvedTableSlices(html);let tableIndex=0;
  if(tables.length!==documentValue.querySelectorAll('table').length)failure('EDITOR_CANONICAL_TABLE_INVALID');
  function readAttrs(element,names,extra=[]) {
    const allowed=new Set([...names.map(name=>ATTR[name]),...extra]);
    for(const attribute of element.attributes)if(!allowed.has(attribute.name))failure('EDITOR_APPROVED_ATTRIBUTE_UNSUPPORTED');
    return validateAttrs(Object.fromEntries(names.map(name=>[name,element.getAttribute(ATTR[name])])),names);
  }
  function inline(nodes,marks=[]) {
    const output=[];
    for(const node of nodes){
      if(node.nodeType===3){if(node.data)output.push({type:'text',text:node.data,marks});continue;}
      if(node.nodeType!==1||!INLINE_TAGS.has(node.localName))failure('EDITOR_INLINE_UNSUPPORTED');
      const tag=node.localName;
      if(tag==='br'){if(node.attributes.length)failure('EDITOR_APPROVED_ATTRIBUTE_UNSUPPORTED');output.push({type:'hardBreak',marks});continue;}
      let next=[...marks];
      if(TAG_MARK[tag]){if(node.attributes.length)failure('EDITOR_APPROVED_ATTRIBUTE_UNSUPPORTED');next.push({type:TAG_MARK[tag]});}
      else if(tag==='span'){
        const attrs=readAttrs(node,FORMAT, ['data-es-anchor']);
        if(Object.values(attrs).some(value=>value!==null)){
          const previous=next.find(mark=>mark.type==='esFormat');const combined={...(previous?.attrs||{}),...Object.fromEntries(Object.entries(attrs).filter(([,value])=>value!==null))};
          next=next.filter(mark=>mark.type!=='esFormat');next.push({type:'esFormat',attrs:combined});
        }
        if(node.hasAttribute('data-es-anchor')){
          if(next.some(mark=>mark.type==='esAnchor'))failure('EDITOR_NESTED_ANCHOR_UNSUPPORTED');
          next.push({type:'esAnchor',attrs:{label:validateAttrs({anchor:node.getAttribute('data-es-anchor')},['anchor']).anchor}});
        }
        if(!node.childNodes.length&&node.hasAttribute('data-es-anchor'))failure('EDITOR_EMPTY_ANCHOR_UNSUPPORTED');
      }else if(tag==='a'){
        const allowed=['href','title','target','rel','data-es-target-field','data-es-target-anchor'];readAttrs(node,[],allowed);
        const attrs=Object.fromEntries(allowed.map(name=>[name,node.getAttribute(name)]));
        if(attrs.target&&!['_self','_blank'].includes(attrs.target))failure('EDITOR_LINK_UNSUPPORTED');
        if(attrs['data-es-target-field']&&!['intro_text','main_text'].includes(attrs['data-es-target-field']))failure('EDITOR_LINK_UNSUPPORTED');
        next.push({type:'esLink',attrs});
      }
      output.push(...inline(node.childNodes,next));
    }
    return output;
  }
  function blocks(nodes,{allowUnwrapped=false}={}) {
    const output=[];let pending=[];
    const flush=()=>{if(pending.length){output.push({type:'paragraph',attrs:{esUnwrapped:allowUnwrapped},content:inline(pending)});pending=[];}};
    for(const node of nodes){
      if(node.nodeType===3||node.nodeType===1&&INLINE_TAGS.has(node.localName)){pending.push(node);continue;}
      flush();if(node.nodeType!==1||!BLOCK_TAGS.has(node.localName))failure('EDITOR_BLOCK_UNSUPPORTED');
      const tag=node.localName;
      if(tag==='table'){
        const source=tables[tableIndex];tableIndex+=1+node.querySelectorAll('table').length;approvedTables.add(source);output.push({type:'esOpaqueTable',attrs:{approvedHtml:source}});continue;
      }
      if(tag==='li')failure('EDITOR_LIST_CONTEXT_INVALID');
      const attrs=readAttrs(node,BLOCK);
      if(tag==='p'||/^h[123]$/.test(tag)){
        if(tag==='h1'&&!owner)failure('EDITOR_OWNER_HEADING_REQUIRED');output.push({type:tag==='p'?'paragraph':'heading',attrs:{...attrs,...(tag!=='p'?{level:Number(tag[1])}:{})},content:inline(node.childNodes)});
      }else if(tag==='blockquote')output.push({type:'blockquote',attrs,content:blocks(node.childNodes)});
      else {
        const items=[];for(const child of node.childNodes){
          if(child.nodeType===3&&!child.data.trim())continue;
          if(child.nodeType!==1||child.localName!=='li'||child.attributes.length)failure('EDITOR_LIST_UNSUPPORTED');
          const content=blocks(child.childNodes,{allowUnwrapped:true});
          if(!content.length||content[0].type!=='paragraph')content.unshift({type:'paragraph',attrs:{esUnwrapped:true},content:[]});
          items.push({type:'listItem',content});
        }
        if(!items.length)failure('EDITOR_EMPTY_LIST_UNSUPPORTED');output.push({type:tag==='ul'?'bulletList':'orderedList',attrs,content:items});
      }
    }
    flush();return output;
  }
  const content=blocks(documentValue.body.childNodes);return {type:'doc',content:content.length?content:[{type:'paragraph'}]};
}

function canonicalDocument(doc,{owner,approvedTables}) {
  function wrapped(text,marks) {
    for(const mark of [...marks].reverse()){
      const name=mark.type.name;
      if(MARK_TAG[name])text='<'+MARK_TAG[name]+'>'+text+'</'+MARK_TAG[name]+'>';
      else if(name==='esFormat')text='<span'+htmlAttrs(carrierAttrs(mark.attrs,FORMAT))+'>'+text+'</span>';
      else if(name==='esAnchor')text='<span'+htmlAttrs({'data-es-anchor':validateAttrs({anchor:mark.attrs.label},['anchor']).anchor})+'>'+text+'</span>';
      else if(name==='esLink')text='<a'+htmlAttrs(mark.attrs)+'>'+text+'</a>';
      else failure('EDITOR_MARK_UNSUPPORTED');
    }
    return text;
  }
  function content(node){let output='';node.forEach(child=>{output+=serialize(child,node.type.name);});return output;}
  function serialize(node,parent='') {
    const name=node.type.name;
    if(name==='text')return wrapped(escapeText(node.text),node.marks);
    if(name==='hardBreak')return wrapped('<br>',node.marks);
    if(name==='esOpaqueTable'){if(!approvedTables.has(node.attrs.approvedHtml))failure('EDITOR_APPROVED_TABLE_REQUIRED');return node.attrs.approvedHtml;}
    if(name==='doc')return content(node);
    if(name==='listItem')return '<li>'+content(node)+'</li>';
    const tag={paragraph:'p',blockquote:'blockquote',bulletList:'ul',orderedList:'ol'}[name]||(name==='heading'?'h'+node.attrs.level:null);
    if(!tag||(name==='heading'&&(![1,2,3].includes(node.attrs.level)||!owner&&node.attrs.level===1)))failure('EDITOR_NODE_UNSUPPORTED');
    const attrs=carrierAttrs(node.attrs,BLOCK),body=content(node);
    if(parent==='listItem'&&name==='paragraph'&&node.attrs.esUnwrapped&&!Object.keys(attrs).length)return body;
    return '<'+tag+htmlAttrs(attrs)+'>'+body+'</'+tag+'>';
  }
  return serialize(doc);
}

export function createEditor(element,{approvedHtml,owner,field,styleSheet,onDirty=()=>{},onError=()=>{},onUntrustedInput=()=>{}}={}) {
  if(!(element instanceof HTMLElement)||typeof owner!=='boolean'||!['intro_text','main_text'].includes(field))failure('EDITOR_CONTEXT_INVALID');
  let editor=null,rules=null,mode='visual',dirty=false,destroyed=false,viewBlocked=false,approvedBaseDoc=null,approvedCanonical='';let approvedTables=new Set();
  const visual=document.createElement('div'),source=document.createElement('textarea');visual.className='es-visual';source.className='es-html-source';source.hidden=true;source.setAttribute('aria-label','HTML содержимого');source.spellcheck=false;element.replaceChildren(visual,source);
  const report=error=>{onError({code:error.code||'EDITOR_OPERATION_FAILED',viewBlocked});};
  const styleFailure=error=>{viewBlocked=true;report(error);};
  const markDirty=()=>{dirty=true;onDirty({field,mode,dirty:true});};
  const guarded=callback=>{try{if(destroyed)failure('EDITOR_DESTROYED');return callback();}catch(error){report(error);throw error;}};
  function refresh(){if(editor&&rules)rules.refresh(editor.state.doc);}
  function visualCanonical(doc=editor?.state.doc,{forCheck=false}={}){
    if(!editor||!doc)failure('EDITOR_VISUAL_UNAVAILABLE');
    if(viewBlocked){
      if(!forCheck)failure('EDITOR_VIEW_RECHECK_REQUIRED');
      // An errored view may expose its actual model only for an explicit check;
      // it must never return the old approved-cache result as current success.
      return canonicalDocument(doc,{owner,approvedTables});
    }
    if(approvedBaseDoc&&doc.eq(approvedBaseDoc))return approvedCanonical;
    return canonicalDocument(doc,{owner,approvedTables});
  }
  function build(html) {
    const nextTables=new Set();const doc=approvedDocument(html,{owner,approvedTables:nextTables});
    approvedBaseDoc=null;approvedCanonical='';
    if(editor)editor.destroy();if(rules)rules.destroy();approvedTables=nextTables;rules=new Rules(styleSheet,styleFailure);
    editor=new Editor({element:visual,injectCSS:false,enableInputRules:false,enablePasteRules:false,content:doc,
      extensions:extensionsFor({owner,rules,approvedTables,requestHtml:()=>api.setMode('html')}),
      editorProps:{attributes:{class:'es-editor-surface',role:'textbox','aria-label':'Текст страницы'},handleDOMEvents:{
        paste(view,event){event.preventDefault();const html=event.clipboardData?.getData('text/html')||'',text=event.clipboardData?.getData('text/plain')||'';
          if(html){onUntrustedInput({field,html,text,intent:'paste'});return true;}
          if(text){try{view.dispatch(view.state.tr.insertText(text));}catch(error){styleFailure(error);}}return true;},
        drop(view,event){event.preventDefault();onUntrustedInput({field,html:event.dataTransfer?.getData('text/html')||'',text:event.dataTransfer?.getData('text/plain')||'',intent:'drop'});return true;},
      },
        handleClick(view,pos,event){if(event.target.closest?.('a')){event.preventDefault();return true;}return false;},
      },onUpdate(){try{markDirty();refresh();}catch(error){styleFailure(error);}},
    });
    // Pinned Tiptap emits this before EditorView.updateState, hence before any
    // node/mark view can fail while rendering the newly applied transaction.
    editor.on('beforeTransaction',({nextState})=>{if(!editor.state.doc.eq(nextState.doc))markDirty();});
    refresh();source.value=html;viewBlocked=false;
    // One actor/view-owned base only, after successful closed import/render.
    // PM nodes are immutable: undo may legitimately return to this exact model.
    approvedBaseDoc=editor.state.doc;approvedCanonical=html;
  }
  function htmlOnly(html){
    approvedBaseDoc=null;approvedCanonical='';
    editor?.destroy();editor=null;rules?.destroy();rules=null;approvedTables.clear();
    source.value=html;mode='html';source.hidden=false;visual.hidden=true;viewBlocked=false;
  }
  source.addEventListener('input',markDirty);
  const stopLink=event=>{if(event.target.closest?.('a'))event.preventDefault();};visual.addEventListener('auxclick',stopLink);
  const api={
    validateApprovedHtml:html=>guarded(()=>{try{approvedDocument(html,{owner,approvedTables:new Set()});return {visual:true};}catch(error){if(VISUAL_UNSUPPORTED.has(error.code))return {visual:false,code:error.code};throw error;}}),
    getCanonicalHtml:()=>guarded(()=>visualCanonical()),
    getInput:()=>guarded(()=>({mode,html:mode==='html'?source.value:visualCanonical(editor?.state.doc,{forCheck:true})})),
    setApprovedHtml:(html,{emitDirty=false}={})=>guarded(()=>{
      try{build(html);mode='visual';source.hidden=true;visual.hidden=false;}
      catch(error){if(!VISUAL_UNSUPPORTED.has(error.code))throw error;htmlOnly(html);}
      dirty=emitDirty;if(emitDirty)markDirty();else onDirty({field,mode,dirty:false});
    }),
    setRawHtml:raw=>guarded(()=>{if(typeof raw!=='string')failure('EDITOR_RAW_TYPE_INVALID');source.value=raw;mode='html';source.hidden=false;visual.hidden=true;markDirty();}),
    setMode:next=>guarded(()=>{if(next==='html'){if(mode==='visual')source.value=visualCanonical(editor?.state.doc,{forCheck:true});mode='html';source.hidden=false;visual.hidden=true;return;}
      if(next!=='visual')failure('EDITOR_MODE_INVALID');if(mode==='html')failure('EDITOR_SERVER_CHECK_REQUIRED');}),
    command:(name,value)=>guarded(()=>{
      if(viewBlocked)failure('EDITOR_VIEW_RECHECK_REQUIRED');
      if(mode!=='visual')failure('EDITOR_VISUAL_MODE_REQUIRED');let chain=editor.chain().focus();
      if(Object.hasOwn(MARK_TAG,name))return chain.toggleMark(name).run();
      if(name==='paragraph')return chain.setNode('paragraph').run();
      if(name==='heading'){if(![1,2,3].includes(value)||!owner&&value===1)failure('EDITOR_OWNER_HEADING_REQUIRED');return chain.setNode('heading',{level:value}).run();}
      if(name==='blockquote')return chain.toggleWrap('blockquote').run();
      if(name==='bulletList'||name==='orderedList')return chain.toggleList(name,'listItem').run();
      if(name==='link'){
        if(!value||typeof value!=='object'||Array.isArray(value))failure('EDITOR_LINK_UNSUPPORTED');
        const allowed=['href','title','target','rel','data-es-target-field','data-es-target-anchor'];
        if(Object.keys(value).some(key=>!allowed.includes(key))||Object.values(value).some(item=>item!==null&&typeof item!=='string'))failure('EDITOR_LINK_UNSUPPORTED');
        if(editor.state.selection.empty)failure('EDITOR_SELECT_LINK_TEXT');
        const attrs=Object.fromEntries(allowed.map(key=>[key,value[key]??null]));
        // A proposed href is serialized into a RAM-only full-field candidate,
        // never dispatched into the live DOM before the server check/accept.
        const transaction=editor.state.tr.addMark(editor.state.selection.from,editor.state.selection.to,editor.schema.marks.esLink.create(attrs));
        onUntrustedInput({field,html:visualCanonical(transaction.doc),text:'',intent:'link'});return true;
      }
      if(name==='removeLink')return chain.unsetMark('esLink').run();
      if(FORMAT.includes(name)){const attrs=validateAttrs({[name]:value},[name]);return chain.setMark('esFormat',attrs).run();}
      if(['align','mt','mr','mb','ml'].includes(name)){const attrs=validateAttrs({[name]:value},[name]);const selected=editor.state.selection.$from.parent.type.name;if(!['paragraph','heading','blockquote','bulletList','orderedList'].includes(selected))failure('EDITOR_SELECTION_UNSUPPORTED');return chain.updateAttributes(selected,attrs).run();}
      if(name==='clearFormatting'){
        chain=chain.unsetMark('esFormat');for(const markName of Object.keys(MARK_TAG))chain=chain.unsetMark(markName);
        return chain.run(); // Anchor identities and explicit link bindings survive.
      }
      if(name==='undo')return chain.undo().run();if(name==='redo')return chain.redo().run();
      failure('EDITOR_COMMAND_UNSUPPORTED');
    }),
    focus:()=>guarded(()=>mode==='html'?source.focus():editor.commands.focus()),
    destroy:()=>{
      if(destroyed)return;destroyed=true;approvedBaseDoc=null;approvedCanonical='';approvedHtml='';
      for(const node of element.querySelectorAll('textarea,input,pre')){if('value' in node)node.value='';else node.textContent='';}
      editor?.destroy();editor=null;rules?.destroy();rules=null;approvedTables.clear();approvedBaseDoc=null;approvedCanonical='';approvedHtml='';source.value='';visual.replaceChildren();element.replaceChildren();
      onDirty=()=>{};onError=()=>{};onUntrustedInput=()=>{};
    },
  };
  try{build(approvedHtml);}catch(error){
    if(!VISUAL_UNSUPPORTED.has(error.code))throw error;
    htmlOnly(approvedHtml);report(error);
  }
  return Object.freeze(api);
}
