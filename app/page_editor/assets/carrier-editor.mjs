// D-330 pinned packages only. This adapter is not server admission or a sanitizer.
import { Editor, Node, Mark, Extension } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { Plugin, TextSelection } from '@tiptap/pm/state';
import { canSplit, canJoin } from '@tiptap/pm/transform';
import {approvedEmbedded,readMarker,markerHtml,protectedShape,insertBlockHtml,replaceMarkerInHtml} from './embedded-editor.mjs';

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
      for(const [attrs,names] of [[node.attrs,BLOCK],...(node.type.name==='esProtectedSlot'?[[node.attrs,FORMAT]]:[]),...node.marks.filter(mark=>mark.type.name==='esFormat').map(mark=>[mark.attrs,FORMAT])]){
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

function protectedDeleteBoundary(view,event){
  if(event.key!=='Backspace'&&event.key!=='Delete')return false;
  const direction=event.key==='Backspace'?-1:1,selection=view.dom.ownerDocument.getSelection();
  if(!selection?.rangeCount||!selection.anchorNode||!selection.focusNode
      ||!view.dom.contains(selection.anchorNode)||!view.dom.contains(selection.focusNode))return false;
  const closest=(node,selector)=>(node.nodeType===1?node:node.parentElement)?.closest(selector);
  const isProtected=node=>node&&['esProtectedParent','esProtectedSlot','esProtected'].includes(node.type.name);
  const containsProtected=node=>{if(!node)return false;if(isProtected(node))return true;let found=false;node.descendants(child=>{if(isProtected(child)){found=true;return false;}return !found;});return found;};
  const slotAt=position=>{const resolved=view.state.doc.resolve(position);for(let depth=resolved.depth;depth>0;depth--){const node=resolved.node(depth);if(node.type.name==='esProtectedSlot')return {node,start:resolved.start(depth),end:resolved.end(depth),offset:position-resolved.start(depth)};}return null;};
  try{
    const anchor=view.posAtDOM(selection.anchorNode,selection.anchorOffset,-1);
    const focus=view.posAtDOM(selection.focusNode,selection.focusOffset,direction);
    const anchorSlot=slotAt(anchor),focusSlot=slotAt(focus);
    if(!selection.isCollapsed){
      if(anchorSlot&&focusSlot&&anchorSlot.start===focusSlot.start){
        const a=closest(selection.anchorNode,'[data-editor-protected-slot]'),f=closest(selection.focusNode,'[data-editor-protected-slot]');
        return !a||!f||a.dataset.editorProtectedSlot!==anchorSlot.node.attrs.slotId||f.dataset.editorProtectedSlot!==focusSlot.node.attrs.slotId;
      }
      let hazard=false;view.state.doc.nodesBetween(Math.min(anchor,focus),Math.max(anchor,focus),node=>{if(isProtected(node)){hazard=true;return false;}return !hazard;});
      return hazard||!!closest(selection.anchorNode,'[data-editor-protected-parent]')||!!closest(selection.focusNode,'[data-editor-protected-parent]');
    }
    if(focusSlot){
      const domSlot=closest(selection.focusNode,'[data-editor-protected-slot]');
      if(domSlot&&domSlot.dataset.editorProtectedSlot!==focusSlot.node.attrs.slotId)return true;
      if(!domSlot&&closest(selection.focusNode,'[data-editor-protected-parent]'))return true;
      const boundary=direction<0?focusSlot.offset===0:focusSlot.offset===focusSlot.node.content.size;
      if(boundary)return true;
      const domAnchorSlot=closest(selection.anchorNode,'[data-editor-protected-slot]');
      if(anchor===focus&&anchorSlot?.start===focusSlot.start
          &&domSlot?.dataset.editorProtectedSlot===focusSlot.node.attrs.slotId
          &&domAnchorSlot?.dataset.editorProtectedSlot===focusSlot.node.attrs.slotId
          &&(view.state.selection.anchor!==anchor||view.state.selection.head!==focus)){
        // Native cursor movement may precede ProseMirror's selectionchange update.
        // Synchronize only the validated interior caret; native deletion stays native.
        view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc,anchor,focus)));
      }
      return false;
    }
    const resolved=view.state.doc.resolve(focus);
    if(closest(selection.focusNode,'[data-editor-protected-parent]'))return true;
    for(let depth=resolved.depth;depth>0;depth--)if(isProtected(resolved.node(depth)))return true;
    if(!resolved.parent.inlineContent)return containsProtected(resolved.nodeBefore)||containsProtected(resolved.nodeAfter);
    if(direction<0?resolved.parentOffset!==0:resolved.parentOffset!==resolved.parent.content.size)return false;
    // Ordinary text at a boundary may merge with a protected adjacent block.
    // Walk outward only while no intervening sibling exists.
    for(let depth=resolved.depth;depth>0;depth--){
      const edge=view.state.doc.resolve(direction<0?resolved.before(depth):resolved.after(depth));
      const neighbor=direction<0?edge.nodeBefore:edge.nodeAfter;
      if(neighbor)return containsProtected(neighbor);
    }
    return false;
  }catch{
    // A stale DOM point in a protected region must not start native merging.
    return !!closest(selection.focusNode,'[data-editor-protected-parent]')||!!closest(selection.anchorNode,'[data-editor-protected-parent]');
  }
}

// Read both live endpoints once. Commands use this exact range, never a later
// stale PM selection. This maps approved editor DOM, not untrusted HTML input.
function commandSelection(view){
  const dom=view.dom.ownerDocument.getSelection();
  if(!dom?.rangeCount||!dom.anchorNode||!dom.focusNode
      ||!view.dom.contains(dom.anchorNode)||!view.dom.contains(dom.focusNode))failure('EDITOR_SELECTION_UNSUPPORTED');
  const closest=(node,selector)=>(node.nodeType===1?node:node.parentElement)?.closest(selector);
  if(closest(dom.anchorNode,'[data-editor-embedded-marker],.es-opaque-table')||closest(dom.focusNode,'[data-editor-embedded-marker],.es-opaque-table'))failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
  const anchor=view.posAtDOM(dom.anchorNode,dom.anchorOffset,1);
  const head=dom.isCollapsed?anchor:view.posAtDOM(dom.focusNode,dom.focusOffset,1);
  const selection=TextSelection.create(view.state.doc,anchor,head);
  if(!selection.$anchor.parent.inlineContent||!selection.$head.parent.inlineContent)failure('EDITOR_SELECTION_UNSUPPORTED');
  for(const [point,node] of [[selection.$anchor,dom.anchorNode],[selection.$head,dom.focusNode]]){
    const slot=closest(node,'[data-editor-protected-slot]');
    if(point.parent.type.name==='esProtectedSlot'){
      if(!slot||slot.dataset.editorProtectedSlot!==point.parent.attrs.slotId)failure('EDITOR_SELECTION_UNSUPPORTED');
      const parent=closest(node,'[data-editor-protected-parent]');
      if(!parent||point.depth<2||parent.dataset.editorProtectedParent!==point.node(point.depth-1).attrs.parentId)failure('EDITOR_SELECTION_UNSUPPORTED');
    }else if(slot||closest(node,'[data-editor-protected-parent]'))failure('EDITOR_SELECTION_UNSUPPORTED');
  }
  return selection;
}

// Only a serialization of our typed PM model reaches this finite scanner.
// No raw HTML DOM parse or browser repair is part of candidate admission.
function candidateBudget(html){
  if(new TextEncoder().encode(html).length>1048576)failure('EDITOR_CANDIDATE_LIMIT');
  let nodes=0,depth=0,text=0,last=0;const tags=/<\/?[a-z][^>]*>/gu;
  const count=value=>{const decoded=value.replace(/&(amp|lt|gt|quot|apos|#x27);/gu,entity=>({'&amp;':'&','&lt;':'<','&gt;':'>','&quot;':'"','&apos;':"'",'&#x27;':"'"})[entity]);for(const unused of decoded.replace(/\r\n?/gu,'\n').normalize('NFC')){if(++text>200000)failure('EDITOR_CANDIDATE_LIMIT');}};
  for(const match of html.matchAll(tags)){
    count(html.slice(last,match.index));last=match.index+match[0].length;
    if(match[0][1]==='/'){depth--;continue;}
    if(++nodes>20000||depth+1>32)failure('EDITOR_CANDIDATE_LIMIT');
    if(match[0]!=='<br>')depth++;
  }
  count(html.slice(last));if(depth!==0)failure('EDITOR_CANDIDATE_INVALID');
}

function extensionsFor({owner,pageId,rules,approvedTables,requestHtml,embeddedMap,queueImage,embeddedSourceUrl,onBlocked}) {
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
  const protectedParent=Node.create({name:'esProtectedParent',group:'block',content:'esProtectedSlot (esProtected esProtectedSlot)+',defining:true,isolating:true,
    addAttributes:()=>({...attrsDefinition(BLOCK),parentId:{default:null},tag:{default:'p'}}),parseHTML:()=>[],renderHTML:()=>['div',{},0],
    addNodeView:()=>({node})=>{const dom=document.createElement(node.attrs.tag);dom.dataset.editorProtectedParent=node.attrs.parentId;setNodeDom(dom,node,rules);dom.classList.add('es-protected-parent');return {dom,contentDOM:dom};}});
  const protectedSlot=Node.create({name:'esProtectedSlot',group:'block',content:'inline*',defining:true,isolating:true,
    addAttributes:()=>({...attrsDefinition(FORMAT),anchor:{default:null},slotId:{default:null}}),parseHTML:()=>[],renderHTML:()=>['span',{},0],
    addNodeView:()=>({node})=>{let current=node;const dom=document.createElement('span');dom.dataset.editorProtectedSlot=node.attrs.slotId;
      const update=value=>{dom.className=rules.ensure(styleFacts(value.attrs,FORMAT));dom.classList.add('es-protected-slot');};update(node);
      return {dom,contentDOM:dom,update(next){if(next.type!==current.type||next.attrs.slotId!==current.attrs.slotId)return false;current=next;update(next);return true;}};}});
  const protectedImage=Node.create({name:'esProtected',group:'block',atom:true,selectable:true,draggable:false,
    addAttributes:()=>({markerId:{default:null},imageId:{default:null},reference:{default:null}}),parseHTML:()=>[],renderHTML:()=>['span',{}],
    addNodeView:()=>({node})=>{
      const item=embeddedMap.get(node.attrs.markerId);
      if(!item||item.imageId!==node.attrs.imageId||JSON.stringify(item.reference)!==JSON.stringify(node.attrs.reference))failure('EDITOR_EMBEDDED_MAPPING_INVALID');
      const dom=document.createElement('span');dom.contentEditable='false';dom.className='es-embedded-atom es-embedded-align-'+item.reference.alignment;
      dom.dataset.editorEmbeddedMarker=item.markerId;dom.dataset.editorEmbeddedImageId=item.imageId;
      const image=document.createElement('img');image.alt=item.reference.alt;image.decoding='async';dom.append(image);
      for(const [key,attribute] of [['width_px','width'],['height_px','height']])if(item.reference[key]!==null)image.setAttribute(attribute,String(item.reference[key]));
      let destroyed=false,finish=()=>{};
      if(item.thumbnailUrl)queueImage(()=>new Promise(resolve=>{if(destroyed){resolve();return;}let timer;
        finish=failed=>{clearTimeout(timer);image.onload=null;image.onerror=null;if(failed&&!destroyed){image.removeAttribute('src');dom.append(document.createTextNode(' Предпросмотр недоступен.'))};resolve();};image.onload=()=>finish(false);image.onerror=()=>finish(true);timer=setTimeout(()=>finish(true),10000);
        try{let url=item.thumbnailUrl;
          if(url.includes('/media/files/')&&typeof embeddedSourceUrl==='function')url=embeddedSourceUrl(url);
          const checked=approvedEmbedded([{...item,thumbnailUrl:url}],{pageId});image.src=checked.get(item.markerId).thumbnailUrl;
        }catch{finish(true);}}));
      else dom.append(document.createTextNode(' Предпросмотр недоступен'));
      return {dom,destroy(){destroyed=true;image.removeAttribute('src');finish();}};
    }});
  const safety=Extension.create({name:'esNoDefaultPaste',addProseMirrorPlugins:()=>[new Plugin({
    filterTransaction(transaction,state){if(!transaction.docChanged||protectedShape(transaction.doc)===protectedShape(state.doc))return true;onBlocked();return false;},
    props:{handleDOMEvents:{dragstart:(view,event)=>{event.preventDefault();return true;}}}})]});
  return [StarterKit.configure({paragraph:false,heading:false,blockquote:false,bulletList:false,orderedList:false,listItem:false,bold:false,italic:false,underline:false,strike:false,link:false,code:false,codeBlock:false,horizontalRule:false,dropcursor:false,gapcursor:false,trailingNode:false}),
    blockNode('paragraph','p','inline*'),blockNode('heading','h2','inline*'),blockNode('blockquote','blockquote','block+'),blockNode('bulletList','ul','listItem+'),blockNode('orderedList','ol','listItem+'),
    Node.create({name:'listItem',content:'paragraph block*',defining:true,parseHTML:()=>[{tag:'li'}],renderHTML:()=>['li',{},0]}),...marks,format,anchor,link,opaque,protectedParent,protectedSlot,protectedImage,safety];
}

function approvedTableSlices(html) {
  const slices=[];const stack=[];const pattern=/<\/?table\b[^>]*>/g;let match;
  while((match=pattern.exec(html))){
    if(match[0].startsWith('</')){const item=stack.pop();if(!item)failure('EDITOR_CANONICAL_TABLE_INVALID');slices[item.index]=html.slice(item.start,pattern.lastIndex);}
    else {const item={start:match.index,index:slices.length};slices.push(null);stack.push(item);}
  }
  if(stack.length||slices.some(value=>value===null))failure('EDITOR_CANONICAL_TABLE_INVALID');return slices;
}

function approvedDocument(html,{owner,approvedTables,embeddedMap=new Map()}) {
  if(typeof html!=='string'||new TextEncoder().encode(html).length>1048576)failure('EDITOR_APPROVED_INPUT_REQUIRED');
  // Only server-approved strings reach this inert parser. Raw input has no path
  // to this function. The server policy, not this adapter, performs sanitation.
  if(/<\/?(?:script|style|iframe|object|embed|img|svg|math|form|input|button|textarea|select|link|meta|base)\b/i.test(html))failure('EDITOR_APPROVED_INPUT_REQUIRED');
  const documentValue=new DOMParser().parseFromString(html,'text/html');
  if(documentValue.querySelector('[style],[class],[id]'))failure('EDITOR_APPROVED_INPUT_REQUIRED');
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
      if(node.nodeType===1&&node.hasAttribute('data-es-parent')){
        flush();const tag=node.localName;if(!['p','h1','h2','h3','blockquote'].includes(tag)||tag==='h1'&&!owner)failure('EDITOR_PROTECTED_OR_UNSUPPORTED');
        const blockAttrs=readAttrs(node,BLOCK,['data-es-parent']),parentId=node.getAttribute('data-es-parent');
        if(!/^[0-9a-f-]{36}$/u.test(parentId||'')||node.childNodes.length<3||node.childNodes.length%2!==1)failure('EDITOR_PROTECTED_OR_UNSUPPORTED');
        const children=[];
        [...node.childNodes].forEach((child,index)=>{
          if(child.nodeType!==1||child.localName!=='span')failure('EDITOR_PROTECTED_OR_UNSUPPORTED');
          if(index%2===0){const slotId=child.getAttribute('data-es-slot');if(!/^[0-9a-f-]{36}$/u.test(slotId||''))failure('EDITOR_PROTECTED_OR_UNSUPPORTED');const values=readAttrs(child,FORMAT,['data-es-slot','data-es-anchor']);children.push({type:'esProtectedSlot',attrs:{...values,slotId,anchor:child.getAttribute('data-es-anchor')},content:inline(child.childNodes)});}
          else {if(!embeddedMap.has(child.getAttribute('data-es-protected')))failure('EDITOR_PROTECTED_OR_UNSUPPORTED');children.push({type:'esProtected',attrs:readMarker(child,embeddedMap)});}
        });output.push({type:'esProtectedParent',attrs:{...blockAttrs,parentId,tag},content:children});continue;
      }
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
          if(content[0]?.type==='esProtectedParent')failure('EDITOR_LIST_UNSUPPORTED');
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
    if(name==='esProtected')return markerHtml(node.attrs);
    if(name==='esProtectedSlot')return '<span'+htmlAttrs({'data-es-slot':node.attrs.slotId,...carrierAttrs(node.attrs,FORMAT),...(node.attrs.anchor?{'data-es-anchor':node.attrs.anchor}:{})})+'>'+content(node)+'</span>';
    if(name==='esProtectedParent')return '<'+node.attrs.tag+htmlAttrs({'data-es-parent':node.attrs.parentId,...carrierAttrs(node.attrs,BLOCK)})+'>'+content(node)+'</'+node.attrs.tag+'>';
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

export function createEditor(element,{approvedHtml,owner,field,pageId,approvedEmbedded:initialEmbedded=[],queueImage=task=>task(),embeddedSourceUrl,styleSheet,onDirty=()=>{},onError=()=>{},onUntrustedInput=()=>{}}={}) {
  if(!(element instanceof HTMLElement)||typeof owner!=='boolean'||!['intro_text','main_text'].includes(field))failure('EDITOR_CONTEXT_INVALID');
  let editor=null,rules=null,mode='visual',dirty=false,destroyed=false,viewBlocked=false,approvedBaseDoc=null,approvedCanonical='';let approvedTables=new Set();
  let embeddedMap=approvedEmbedded(initialEmbedded,{pageId});
  const visual=document.createElement('div'),source=document.createElement('textarea');visual.className='es-visual';source.className='es-html-source';source.hidden=true;source.setAttribute('aria-label','HTML содержимого');source.spellcheck=false;element.replaceChildren(visual,source);
  const report=error=>{onError({code:error.code||'EDITOR_OPERATION_FAILED',viewBlocked});};
  const styleFailure=error=>{viewBlocked=true;report(error);};
  const markDirty=()=>{dirty=true;onDirty({field,mode,dirty:true});};
  const guarded=callback=>{try{if(destroyed)failure('EDITOR_DESTROYED');return callback();}catch(error){report(error);throw error;}};
  function refresh(){if(editor&&rules)rules.refresh(editor.state.doc);}
  function dispatchCandidate(transaction){
    if(protectedShape(transaction.doc)!==protectedShape(editor.state.doc))failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
    candidateBudget(canonicalDocument(transaction.doc,{owner,approvedTables}));
    editor.view.dispatch(transaction);return true;
  }
  function clearSelectedFormatting(selection){
    const doc=editor.state.doc;
    let protectedRange=false;
    doc.nodesBetween(selection.from,selection.to,node=>{if(['esProtectedParent','esProtectedSlot','esProtected','esOpaqueTable'].includes(node.type.name))protectedRange=true;});
    const slot=selection.$from.parent;
    if(slot.type.name==='esProtectedSlot'){
      if(selection.empty||!selection.$from.sameParent(selection.$to)||FORMAT.some(name=>slot.attrs[name]!==null&&slot.attrs[name]!==undefined))failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
    }else if(protectedRange)failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
    // A no-op setSelection clears stored marks, including links and anchors.
    // Only a genuinely moved live caret must discard the old location's marks.
    const transaction=editor.state.tr,names=['esFormat',...Object.keys(MARK_TAG)];
    if(!selection.eq(editor.state.selection))transaction.setSelection(selection);
    for(const name of names){const type=editor.schema.marks[name];if(selection.empty)transaction.removeStoredMark(type);else transaction.removeMark(selection.from,selection.to,type);}
    const result=dispatchCandidate(transaction);editor.view.focus();return result;
  }
  function paragraphKey(view,event){
    if(!['Enter','Backspace','Delete'].includes(event.key)||event.shiftKey||event.ctrlKey||event.metaKey||event.altKey||event.isComposing)return false;
    const selection=commandSelection(view),point=selection.$from;
    const structuralHazard=node=>['esProtectedParent','esProtectedSlot','esProtected','esOpaqueTable'].includes(node.type.name)||node.isAtom&&!node.isInline;
    if(event.key==='Enter'&&!selection.empty){
      const withinSlot=point.parent.type.name==='esProtectedSlot'&&point.sameParent(selection.$to);
      let hazard=false;
      view.state.doc.nodesBetween(selection.from,selection.to,node=>{
        if(structuralHazard(node)&&!(withinSlot&&['esProtectedParent','esProtectedSlot'].includes(node.type.name)))hazard=true;
      });
      if(hazard)failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
    }
    // Existing headings/lists and supported non-collapsed ordinary workflows
    // keep their established PM handlers. This cohort adds root paragraphs.
    if(!selection.empty||point.depth!==1||point.parent.type.name!=='paragraph')return false;
    const index=point.index(0),doc=view.state.doc;
    let lastProtected=-1;doc.forEach((node,offset,childIndex)=>{let found=node.type.name==='esProtectedParent';node.descendants(child=>{if(['esProtectedParent','esProtectedSlot','esProtected'].includes(child.type.name))found=true;});if(found)lastProtected=childIndex;});
    if(event.key==='Enter'){
      if(index<=lastProtected)failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
      const before=point.nodeBefore?.marks.find(mark=>mark.type.name==='esAnchor'),after=point.nodeAfter?.marks.find(mark=>mark.type.name==='esAnchor');
      if(before&&after&&before.eq(after))failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
      const attrs={...point.parent.attrs,anchor:null},types=[{type:point.parent.type,attrs}];
      if(!canSplit(doc,point.pos,1,types))failure('EDITOR_SELECTION_UNSUPPORTED');
      event.preventDefault();return dispatchCandidate(view.state.tr.setSelection(selection).split(point.pos,1,types));
    }
    const backward=event.key==='Backspace';
    if(backward?point.parentOffset!==0:point.parentOffset!==point.parent.content.size)return false;
    const leftIndex=backward?index-1:index,rightIndex=leftIndex+1;
    if(leftIndex<0||rightIndex>=doc.childCount)return false;
    const left=doc.child(leftIndex),right=doc.child(rightIndex);
    const neighbor=backward?left:right;
    let hazard=structuralHazard(neighbor);neighbor.descendants(node=>{if(structuralHazard(node))hazard=true;});
    if(hazard)failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
    if(left.type.name!=='paragraph'||right.type.name!=='paragraph')return false;
    if(leftIndex<=lastProtected||JSON.stringify(left.attrs)!==JSON.stringify(right.attrs)||right.attrs.anchor!==null&&right.attrs.anchor!==undefined)failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
    const position=backward?point.before(1):point.after(1);
    if(!canJoin(doc,position))failure('EDITOR_SELECTION_UNSUPPORTED');
    event.preventDefault();return dispatchCandidate(view.state.tr.setSelection(selection).join(position));
  }
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
  function build(html,records=[...embeddedMap.values()]) {
    const nextMap=approvedEmbedded(records,{pageId});
    const nextTables=new Set();const doc=approvedDocument(html,{owner,approvedTables:nextTables,embeddedMap:nextMap});
    approvedBaseDoc=null;approvedCanonical='';
    if(editor)editor.destroy();if(rules)rules.destroy();approvedTables=nextTables;embeddedMap=nextMap;rules=new Rules(styleSheet,styleFailure);
    editor=new Editor({element:visual,injectCSS:false,enableInputRules:false,enablePasteRules:false,content:doc,
      extensions:extensionsFor({owner,pageId,rules,approvedTables,embeddedMap,queueImage,embeddedSourceUrl,requestHtml:()=>api.setMode('html'),onBlocked:()=>report({code:'EDITOR_PROTECTED_COMMAND_UNSUPPORTED'})}),
      editorProps:{attributes:{class:'es-editor-surface',role:'textbox','aria-label':'Текст страницы'},handleDOMEvents:{
        paste(view,event){event.preventDefault();const html=event.clipboardData?.getData('text/html')||'',text=event.clipboardData?.getData('text/plain')||'';
          if(html){onUntrustedInput({field,html,text,intent:'paste'});return true;}
          if(text){try{view.dispatch(view.state.tr.insertText(text));}catch(error){styleFailure(error);}}return true;},
        drop(view,event){event.preventDefault();onUntrustedInput({field,html:event.dataTransfer?.getData('text/html')||'',text:event.dataTransfer?.getData('text/plain')||'',intent:'drop'});return true;},
      },
        handleKeyDown(view,event){
          if(protectedDeleteBoundary(view,event)){event.preventDefault();report({code:'EDITOR_PROTECTED_COMMAND_UNSUPPORTED'});return true;}
          try{if(paragraphKey(view,event))return true;}catch(error){event.preventDefault();report(error);return true;}
          const selection=view.state.selection,slot=selection.$from.parent;
          if(slot.type.name!=='esProtectedSlot')return false;
          if(event.key==='Enter'){
            event.preventDefault();
            if(selection.$to.parent===slot)view.dispatch(view.state.tr.replaceSelectionWith(view.state.schema.nodes.hardBreak.create()));
            else report({code:'EDITOR_PROTECTED_COMMAND_UNSUPPORTED'});return true;
          }
          return false;
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
    validateApprovedHtml:(html,{approvedEmbedded:records=[...embeddedMap.values()]}={})=>guarded(()=>{try{approvedDocument(html,{owner,approvedTables:new Set(),embeddedMap:approvedEmbedded(records,{pageId})});return {visual:true};}catch(error){if(VISUAL_UNSUPPORTED.has(error.code))return {visual:false,code:error.code};throw error;}}),
    getCanonicalHtml:()=>guarded(()=>visualCanonical()),
    getInput:()=>guarded(()=>({mode,html:mode==='html'?source.value:visualCanonical(editor?.state.doc,{forCheck:true})})),
    setApprovedHtml:(html,{emitDirty=false,approvedEmbedded:records=[...embeddedMap.values()]}={})=>guarded(()=>{
      try{build(html,records);mode='visual';source.hidden=true;visual.hidden=false;}
      catch(error){if(!VISUAL_UNSUPPORTED.has(error.code))throw error;htmlOnly(html);}
      dirty=emitDirty;if(emitDirty)markDirty();else onDirty({field,mode,dirty:false});
    }),
    setRawHtml:raw=>guarded(()=>{if(typeof raw!=='string')failure('EDITOR_RAW_TYPE_INVALID');source.value=raw;mode='html';source.hidden=false;visual.hidden=true;markDirty();}),
    stageEmbedded:issuance=>guarded(()=>{
      if(!owner||issuance.field!==field||viewBlocked)failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
      if(mode==='html'){
        api.setRawHtml(issuance.action==='insert'?source.value+insertBlockHtml(issuance):replaceMarkerInHtml(source.value,issuance));return;
      }
      let candidate;
      if(issuance.action==='insert'){
        const json=editor.state.doc.toJSON(),index=editor.state.selection.$from.index(0);
        if(json.content[index]?.type==='esProtectedParent')failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
        json.content.splice(index+1,0,{type:'esProtectedParent',attrs:{parentId:issuance.ids.parentId,tag:'p'},content:[
          {type:'esProtectedSlot',attrs:{slotId:issuance.ids.slotBeforeId}},
          {type:'esProtected',attrs:{markerId:issuance.ids.markerId,imageId:issuance.ids.imageId,reference:issuance.image}},
          {type:'esProtectedSlot',attrs:{slotId:issuance.ids.slotAfterId}}]});candidate=editor.schema.nodeFromJSON(json);
      }else{
        let pos=null;editor.state.doc.descendants((node,index)=>{if(node.type.name==='esProtected'&&node.attrs.markerId===issuance.ids.markerId)pos=index;});
        if(pos===null)failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
        candidate=editor.state.tr.setNodeMarkup(pos,undefined,{markerId:issuance.ids.markerId,imageId:issuance.ids.imageId,reference:issuance.image}).doc;
      }
      api.setRawHtml(canonicalDocument(candidate,{owner,approvedTables}));
    }),
    setMode:next=>guarded(()=>{if(next==='html'){if(mode==='visual')source.value=visualCanonical(editor?.state.doc,{forCheck:true});mode='html';source.hidden=false;visual.hidden=true;return;}
      if(next!=='visual')failure('EDITOR_MODE_INVALID');if(mode==='html')failure('EDITOR_SERVER_CHECK_REQUIRED');}),
    command:(name,value)=>guarded(()=>{
      if(viewBlocked)failure('EDITOR_VIEW_RECHECK_REQUIRED');
      if(mode!=='visual')failure('EDITOR_VISUAL_MODE_REQUIRED');
      if(name==='clearFormatting')return clearSelectedFormatting(commandSelection(editor.view));
      if(FORMAT.includes(name)){
        const attrs=validateAttrs({[name]:value},[name]),selection=commandSelection(editor.view);
        const withinSlot=selection.$from.parent.type.name==='esProtectedSlot'&&selection.$from.sameParent(selection.$to);
        if(!withinSlot){
          let hazard=false;
          editor.state.doc.nodesBetween(selection.from,selection.to,node=>{
            if(['esProtectedParent','esProtectedSlot','esProtected','esOpaqueTable'].includes(node.type.name)||node.isAtom&&!node.isInline)hazard=true;
          });
          if(hazard)failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
        }
        const shape=protectedShape(editor.state.doc);let formatChain=editor.chain();
        if(!selection.eq(editor.state.selection))formatChain=formatChain.command(({tr})=>{tr.setSelection(selection);return true;});
        const result=formatChain.setMark('esFormat',attrs).command(({tr})=>{
          if(protectedShape(tr.doc)!==shape)failure('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
          candidateBudget(canonicalDocument(tr.doc,{owner,approvedTables}));
          return true;
        }).run();
        editor.view.focus();return result;
      }
      editor.view.focus();let chain=editor.chain();
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
      if(['align','mt','mr','mb','ml'].includes(name)){const attrs=validateAttrs({[name]:value},[name]);const selected=editor.state.selection.$from.parent.type.name;if(!['paragraph','heading','blockquote','bulletList','orderedList'].includes(selected))failure('EDITOR_SELECTION_UNSUPPORTED');return chain.updateAttributes(selected,attrs).run();}
      if(name==='undo')return chain.undo().run();if(name==='redo')return chain.redo().run();
      failure('EDITOR_COMMAND_UNSUPPORTED');
    }),
    focus:()=>guarded(()=>mode==='html'?source.focus():editor.view.focus()),
    destroy:()=>{
      if(destroyed)return;destroyed=true;approvedBaseDoc=null;approvedCanonical='';approvedHtml='';
      for(const node of element.querySelectorAll('textarea,input,pre')){if('value' in node)node.value='';else node.textContent='';}
      editor?.destroy();editor=null;rules?.destroy();rules=null;approvedTables.clear();approvedBaseDoc=null;approvedCanonical='';approvedHtml='';source.value='';visual.replaceChildren();element.replaceChildren();
      embeddedMap.clear();initialEmbedded=[];
      onDirty=()=>{};onError=()=>{};onUntrustedInput=()=>{};
    },
  };
  try{build(approvedHtml);}catch(error){
    if(!VISUAL_UNSUPPORTED.has(error.code))throw error;
    htmlOnly(approvedHtml);report(error);
  }
  return Object.freeze(api);
}
