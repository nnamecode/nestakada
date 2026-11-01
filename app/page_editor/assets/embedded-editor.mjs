// Actor-owned RAM issuance. No raw HTML enters a browser HTML parser here.
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
const IDKEYS=['layoutId','parentId','markerId','imageId','slotBeforeId','slotAfterId'];
const REFKEYS=['asset_id','alt','alignment','width_px','height_px'];
const escape=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#x27;');
const attrs=values=>Object.entries(values).filter(([,value])=>value!==null&&value!==undefined).sort(([a],[b])=>a.localeCompare(b,'en')).map(([key,value])=>' '+key+'="'+escape(value)+'"').join('');
function fail(){throw Object.assign(new Error('EDITOR_EMBEDDED_INVALID'),{code:'EDITOR_EMBEDDED_INVALID'});}
function keys(value,expected){return value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join() === [...expected].sort().join();}
export function imageRef(value){
  if(!keys(value,REFKEYS)||!UUID.test(value.asset_id)||typeof value.alt!=='string'||[...value.alt].length>300||/[\x00-\x1f\x7f]/u.test(value.alt)||!['left','center','right'].includes(value.alignment)
      ||['width_px','height_px'].some(key=>value[key]!==null&&(!Number.isSafeInteger(value[key])||value[key]<=0)))fail();
  return structuredClone(value);
}
export function approvedEmbedded(records,{pageId}={}){
  if(!Array.isArray(records))fail();const result=new Map();
  for(const item of records){
    if(!keys(item,['markerId','imageId','reference','url','thumbnailUrl'])||!UUID.test(item.markerId)||!UUID.test(item.imageId)||result.has(item.markerId))fail();
    const reference=imageRef(item.reference);
    for(const key of ['url','thumbnailUrl'])if(item[key]!==null){
      if(!UUID.test(pageId||'')||typeof item[key]!=='string')fail();
      const prefix=`/manage/pages/${pageId}/edit/media/`,url=new URL(item[key],location.origin);
      if(url.origin!==location.origin||url.hash||!item[key].startsWith(prefix)||!new RegExp('^'+prefix+'(?:files|picker-files)/[0-9a-f-]{36}/$','u').test(url.pathname))fail();
    }
    result.set(item.markerId,{...item,reference});
  }
  return result;
}
export function markerAttributes(value){
  if(!UUID.test(value.markerId)||!UUID.test(value.imageId))fail();const ref=imageRef(value.reference);
  return {'data-es-protected':value.markerId,'data-es-image':value.imageId,'data-es-asset':ref.asset_id,
    'data-es-alt':ref.alt,'data-es-image-align':ref.alignment,'data-es-width':ref.width_px,'data-es-height':ref.height_px};
}
export function markerHtml(value){return '<span'+attrs(markerAttributes(value))+'></span>';}
export function readMarker(element,map){
  const item=map.get(element.getAttribute('data-es-protected'));if(!item)fail();
  const expected=markerAttributes(item),actual=Object.fromEntries([...element.attributes].map(attr=>[attr.name,attr.value]));
  const normalized=Object.fromEntries(Object.entries(expected).filter(([,value])=>value!==null).map(([key,value])=>[key,String(value)]));
  if(JSON.stringify(Object.entries(actual).sort())!==JSON.stringify(Object.entries(normalized).sort())||element.childNodes.length)fail();
  return {markerId:item.markerId,imageId:item.imageId,reference:structuredClone(item.reference)};
}
export function protectedShape(doc){
  const rows=[];
  function walk(node,path,ancestors){
    if(node.type.name==='esProtectedParent'){
      const children=[];node.forEach(child=>children.push(child.type.name==='esProtectedSlot'?{slotId:child.attrs.slotId}:child.type.name==='esProtected'?child.attrs:{invalid:true}));
      rows.push({path,ancestors,attrs:node.attrs,children});return;
    }
    if(node.type.name==='esProtected'||node.type.name==='esProtectedSlot'){rows.push({orphan:true,path,attrs:node.attrs});return;}
    let index=0;node.forEach(child=>walk(child,[...path,index++],[...ancestors,{type:node.type.name,attrs:node.attrs}]));
  }
  walk(doc,[],[]);return JSON.stringify(rows);
}
export function createImageQueue(){
  let tail=Promise.resolve(),destroyed=false;
  const queue=task=>{tail=tail.then(()=>destroyed?undefined:task(),()=>destroyed?undefined:task());return tail;};
  queue.destroy=()=>{destroyed=true;};return queue;
}
const SPAN=/<span\b(?:[^"'<>]|"[^"]*"|'[^']*')*>/giu;
function markerId(tag){const match=/\bdata-es-protected\s*=\s*(?:"([0-9a-f-]{36})"|'([0-9a-f-]{36})'|([0-9a-f-]{36}))/iu.exec(tag);return match?(match[1]||match[2]||match[3]):null;}
export function replaceMarkerInHtml(html,issuance){
  let count=0;const output=html.replace(SPAN,tag=>{if(markerId(tag)!==issuance.ids.markerId)return tag;count++;return markerHtml({markerId:issuance.ids.markerId,imageId:issuance.ids.imageId,reference:issuance.image}).slice(0,-7);});
  if(count!==1)fail();return output;
}
export function insertBlockHtml(issuance){
  return '<p'+attrs({'data-es-parent':issuance.ids.parentId})+'><span'+attrs({'data-es-slot':issuance.ids.slotBeforeId})+'></span>'+markerHtml({markerId:issuance.ids.markerId,imageId:issuance.ids.imageId,reference:issuance.image})+'<span'+attrs({'data-es-slot':issuance.ids.slotAfterId})+'></span></p>';
}
function element(tag,text){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;}
export function mountEmbeddedControls({root,initial,editors,run,canEdit,getEpoch,invalidate,listMedia,issueEmbedded,queueImage}){
  const permits=new Map(),sections=[],records=new Map();let destroyed=false;
  function button(text,fn){const node=element('button',text);node.type='button';node.addEventListener('click',run(fn));return node;}
  function sourceItems(field){return initial.embeddedMedia?.[field]||[];}
  function picture(host,item){
    if(!item?.thumbnailUrl)return;
    const prefix=`/manage/pages/${initial.pageId}/edit/media/`,url=new URL(item.thumbnailUrl,location.origin);
    if(url.origin!==location.origin||url.hash||!item.thumbnailUrl.startsWith(prefix)||!new RegExp('^'+prefix+'(?:files|picker-files)/[0-9a-f-]{36}/$','u').test(url.pathname))fail();
    imageRef(item.reference);
    const img=element('img');img.alt=item.reference.alt;host.append(img);
    queueImage(()=>new Promise(resolve=>{if(destroyed||!img.isConnected){resolve();return;}let timer;
      const done=()=>{clearTimeout(timer);img.onload=null;img.onerror=null;resolve();};img.onload=done;img.onerror=done;timer=setTimeout(done,10000);img.src=item.thumbnailUrl;}));
  }
  function refresh(){
    for(const [field,record] of records){
      const previous=record.target.value;record.target.replaceChildren();const option=element('option','Новое изображение отдельным блоком');option.value='';record.target.append(option);
      const seen=new Set();
      for(const item of [...sourceItems(field),...[...permits.values()].filter(value=>value.field===field).map(value=>({markerId:value.ids.markerId,reference:value.image}))]){
        if(seen.has(item.markerId))continue;seen.add(item.markerId);const choice=element('option','Заменить изображение: '+(item.reference.alt||item.markerId));choice.value=item.markerId;record.target.append(choice);
      }
      if(seen.has(previous))record.target.value=previous;
    }
  }
  for(const [field,editor] of editors){
    if(!initial.owner||typeof listMedia!=='function'||typeof issueEmbedded!=='function')continue;
    const section=element('section');section.className='es-embedded-controls';section.dataset.editorEmbedded=field;
    section.append(element('h3','Изображение внутри '+(field==='intro_text'?'вводного':'основного')+' текста'));
    const target=element('select');target.dataset.editorEmbeddedMarker='';target.setAttribute('aria-label','Место изображения');section.append(target);
    const query=element('input');query.type='search';query.setAttribute('aria-label','Поиск готового изображения внутри текста');
    const list=element('div'),pendingHost=element('div'),notice=element('p');notice.setAttribute('role','status');
    const record={target,list,pendingHost,notice,pending:null,metadata:{},after:null};records.set(field,record);
    const open=button('Выбрать фото для текста',()=>browse(null));open.dataset.editorEmbeddedAction='open';
    const more=button('Следующие готовые фото',()=>browse(record.after));more.hidden=true;
    section.append(query,open,more,list,pendingHost,notice);
    for(const [key,label] of [['alt','Описание фото (alt)'],['alignment','Выравнивание'],['width_px','Ширина, px'],['height_px','Высота, px']]){
      const wrap=element('label',label+' '),input=element(key==='alignment'?'select':'input');input.dataset.editorEmbeddedField=key;input.setAttribute('aria-label','Встроенное фото: '+label);
      if(key==='alignment')for(const value of ['left','center','right']){const option=element('option',value==='left'?'Слева':value==='center'?'По центру':'Справа');option.value=value;input.append(option);}
      else input.type=key==='alt'?'text':'number';if(key==='alignment')input.value='center';record.metadata[key]=input;wrap.append(input);section.append(wrap);
      input.addEventListener('input',invalidate);
    }
    async function browse(after){
      const result=await listMedia({q:query.value,after});if(destroyed)return;
      if(!result||!Array.isArray(result.items)||result.items.length>50||(result.nextAfter!==null&&!UUID.test(result.nextAfter)))fail();
      list.replaceChildren();record.after=result.nextAfter;more.hidden=record.after===null;
      for(const item of result.items){
        if(!UUID.test(item.assetId)||!UUID.test(item.mainFileId)||!UUID.test(item.previewFileId)||typeof item.label!=='string')fail();
        const prefix=`/manage/pages/${initial.pageId}/edit/media/picker-files/`;
        if(item.mainUrl!==prefix+item.mainFileId+'/'||item.previewUrl!==prefix+item.previewFileId+'/')fail();
        const choose=button('Выбрать '+item.label,async()=>{
          if(!canEdit())return;record.pending=item;invalidate();pendingHost.replaceChildren();
          const oldPermit=permits.get(field+':'+target.value),old=oldPermit?{markerId:oldPermit.ids.markerId,imageId:oldPermit.ids.imageId,reference:oldPermit.image,...oldPermit.preview}:sourceItems(field).find(value=>value.markerId===target.value);
          if(old){pendingHost.append(element('h4','Прежнее изображение'));picture(pendingHost,old);for(const [key,input] of Object.entries(record.metadata))input.value=old.reference[key]??'';}
          pendingHost.append(element('h4','Новое изображение'));picture(pendingHost,{reference:{asset_id:item.assetId,alt:'',alignment:'center',width_px:null,height_px:null},url:item.mainUrl,thumbnailUrl:item.previewUrl});
          const action=target.value?'replace':'insert';const confirm=button(action==='replace'?'Заменить здесь':'Вставить здесь отдельным блоком',async()=>{
            if(!canEdit()||!record.pending)return;
            const reference={asset_id:record.pending.assetId};
            for(const [key,input] of Object.entries(record.metadata))reference[key]=key==='alt'||key==='alignment'?input.value:input.value===''?null:Number(input.value);
            const image=imageRef(reference),marker=target.value||null,prior=marker?permits.get(field+':'+marker):null;
            const capturedEpoch=getEpoch();
            const issuance=await issueEmbedded({field,action:marker?'replace':'insert',image,markerId:marker,priorPermit:prior?.permit||null});
            if(destroyed)return;
            if(capturedEpoch!==getEpoch()){if(issuance)issuance.permit='';throw Object.assign(new Error('CHECK_CHANGED'),{code:'CHECK_CHANGED'});}
            if(!keys(issuance,['permit','field','action','ids','image'])||typeof issuance.permit!=='string'||issuance.permit.length>8192||issuance.field!==field||!keys(issuance.ids,IDKEYS)||IDKEYS.some(key=>!UUID.test(issuance.ids[key])))fail();
            imageRef(issuance.image);
            editor.stageEmbedded(issuance);
            permits.set(field+':'+issuance.ids.markerId,{...structuredClone(issuance),preview:{url:record.pending.mainUrl,thumbnailUrl:record.pending.previewUrl}});
            record.pending=null;pendingHost.replaceChildren();list.replaceChildren();invalidate();refresh();notice.textContent='Изображение подготовлено только в памяти. Выполните проверку, затем сохраните страницу явно.';
          });confirm.dataset.editorEmbeddedAction=action;pendingHost.append(confirm,button('Отменить выбор',async()=>{record.pending=null;pendingHost.replaceChildren();invalidate();}));
        });choose.dataset.editorEmbeddedAsset=item.assetId;list.append(choose);
      }
    }
    target.addEventListener('input',()=>{record.pending=null;pendingHost.replaceChildren();invalidate();});root.querySelector(`[data-editor-field="${field}"]`).append(section);sections.push(section);
  }
  refresh();
  return Object.freeze({
    project(changes){const result=structuredClone(changes);for(const field of ['intro_text','main_text'])if(typeof result[field]==='string'&&[...permits.values()].some(value=>value.field===field)){if(new TextEncoder().encode(result[field]).length>1048576)fail();result[field]=result[field].replace(SPAN,tag=>{const value=permits.get(field+':'+markerId(tag));if(!value)return tag;if(/\bdata-es-media-intent\s*=/iu.test(tag))fail();return tag.slice(0,-1)+' data-es-media-intent="'+escape(value.permit)+'">';});}return result;},
    capture(changes){return [...permits].filter(([,value])=>typeof changes[value.field]==='string'&&[...changes[value.field].matchAll(SPAN)].some(match=>markerId(match[0])===value.ids.markerId)).map(([key,value])=>({key,token:value.permit}));},
    acknowledge(snapshot){for(const item of snapshot||[])if(permits.get(item.key)?.permit===item.token)permits.delete(item.key);refresh();},
    refresh,
    valid(){return ![...records.values()].some(record=>record.pending);},
    destroy(){destroyed=true;for(const section of sections){for(const img of section.querySelectorAll('img'))img.removeAttribute('src');for(const input of section.querySelectorAll('input,textarea'))input.value='';section.replaceChildren();section.remove();}for(const value of permits.values()){value.permit='';value.image.alt='';}permits.clear();for(const record of records.values())record.pending=null;records.clear();}
  });
}
