/** External ImageRef controls only. No HTML, storage keys or embedded nodes. */
const FIELDS={main_image:'Главное фото страницы',preview_image:'Превью страницы'};
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
const KEYS=['asset_id','alt','alignment','width_px','height_px'];
function ref(value){
  if(value===null)return null;
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).sort().join()!==[...KEYS].sort().join()
    ||!UUID.test(value.asset_id)||typeof value.alt!=='string'||[...value.alt].length>300
    ||!['left','center','right'].includes(value.alignment)
    ||['width_px','height_px'].some(key=>value[key]!==null&&(!Number.isSafeInteger(value[key])||value[key]<=0)))throw new Error('EDITOR_MEDIA_INVALID');
  return structuredClone(value);
}
function element(tag,text){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;}

export function mountMediaControls({root,before,initial,run,listMedia,sourceUrl,invalidate,canEdit,queueImage}){
  const sections=[],records=new Map(),urls=new Map();let destroyed=false,chain=Promise.resolve();
  const prefix=`/manage/pages/${encodeURIComponent(initial.pageId)}/edit/media/`;
  function safeUrl(value){
    if(typeof value!=='string'||!value.startsWith(prefix))return null;
    const url=new URL(value,location.origin),suffix=url.pathname.slice(prefix.length);
    if(url.origin!==location.origin||url.hash||!(/^(?:files|picker-files)\/[0-9a-f-]{36}\/$/u.test(suffix)))return null;
    if(!UUID.test(suffix.split('/')[1]))return null;
    return url.pathname+url.search;
  }
  function remember(assetId,mainUrl,previewUrl){
    if(!UUID.test(assetId))throw new Error('EDITOR_MEDIA_INVALID');
    const old=urls.get(assetId)||{};
    urls.set(assetId,{mainUrl:safeUrl(mainUrl)||old.mainUrl||null,previewUrl:safeUrl(previewUrl)||old.previewUrl||null});
  }
  function picture(host,value){
    const image=element('img');image.alt=value.alt;image.loading='eager';image.decoding='async';
    const state=urls.get(value.asset_id),url=state?.previewUrl||state?.mainUrl;
    if(!url){host.append(element('p','Предпросмотр недоступен. Проверьте файл перед сохранением.'));return;}
    host.append(image);
    // One image request at a time: the server hashes each file under EditorSlot.
    const task=()=>new Promise(resolve=>{
      if(destroyed||!image.isConnected){resolve();return;}
      let timer;
      const finish=failed=>{
        clearTimeout(timer);image.onload=null;image.onerror=null;
        if(failed&&image.isConnected){image.removeAttribute('src');image.replaceWith(element('p','Не удалось загрузить предпросмотр. Откройте выбор фото заново для повторной проверки.'));}
        resolve();
      };
      image.onload=()=>finish(false);image.onerror=()=>finish(true);
      let actualUrl;
      try{actualUrl=url.startsWith(prefix+'files/')&&typeof sourceUrl==='function'?safeUrl(sourceUrl(url)):url;}
      catch{finish(true);return;}
      if(!actualUrl){finish(true);return;}
      timer=setTimeout(()=>finish(true),10000);image.src=actualUrl;
    });
    if(typeof queueImage==='function')queueImage(task);else chain=chain.then(task);
  }
  function button(label,callback){const node=element('button',label);node.type='button';node.addEventListener('click',run(callback));return node;}
  function current(field){return ref(initial.owner?initial.values[field]:initial.media?.[field]?.reference??null);}
  function render(record){
    const {field,display,metadata,notice,pendingHost}=record;
    for(const img of display.querySelectorAll('img'))img.removeAttribute('src');
    display.replaceChildren();
    let value;
    try{value=current(field);record.invalid=false;}catch{record.invalid=true;notice.textContent='Это изображение пока нельзя безопасно открыть в редакторе.';return;}
    display.append(element('h4','Сейчас в редакторе'));
    if(value)picture(display,value);else display.append(element('p','Фото не выбрано.'));
    for(const [key,input] of Object.entries(metadata)){input.value=value?.[key]??'';input.disabled=!value;}
    pendingHost.replaceChildren();
    if(record.pending){
      pendingHost.append(element('h4','Новое фото'));picture(pendingHost,record.pending);
      pendingHost.append(button(value?'Заменить здесь':'Добавить здесь',async()=>{
        if(!canEdit())return;
        initial.values[field]=ref(record.pending);record.pending=null;record.list.replaceChildren();
        invalidate();notice.textContent='Выбор изменён только в этой вкладке. Проверьте и сохраните страницу.';render(record);
      }),button('Отменить выбор',async()=>{record.pending=null;invalidate();render(record);}));
    }
  }
  for(const [field,label] of Object.entries(FIELDS)){
    if(!initial.media||!Object.hasOwn(initial.media,field))continue;
    const source=initial.media[field];
    if(source?.reference){remember(source.reference.asset_id,field==='main_image'?source.url:null,source.thumbnailUrl||source.url);}
    const section=element('section');section.dataset.editorMedia=field;section.className='es-media';
    section.append(element('h3',label));root.insertBefore(section,before);sections.push(section);
    const display=element('div'),notice=element('p'),pendingHost=element('div');notice.setAttribute('role','status');
    const record={field,display,notice,pendingHost,metadata:{},pending:null,invalid:false,list:element('div')};records.set(field,record);
    section.append(display,notice);
    if(initial.owner&&typeof listMedia==='function'){
      const controls=element('div');controls.className='es-media-controls';
      const folder=element('input');folder.type='text';folder.setAttribute('aria-label',label+': папка');
      const query=element('input');query.type='search';query.setAttribute('aria-label',label+': поиск');
      const folderLabel=element('label','Папка '),queryLabel=element('label','Поиск фото ');
      folderLabel.append(folder);queryLabel.append(query);
      let after=null;
      async function browse(cursor=null){
        const result=await listMedia({folder:folder.value,q:query.value,after:cursor});
        if(destroyed)return;
        if(!result||!Array.isArray(result.items)||result.items.length>50||(result.nextAfter!==null&&!UUID.test(result.nextAfter)))throw new Error('EDITOR_MEDIA_INVALID');
        record.list.replaceChildren();after=result.nextAfter;
        for(const item of result.items){
          if(!item||!UUID.test(item.assetId)||!UUID.test(item.mainFileId)||!UUID.test(item.previewFileId)
            ||typeof item.label!=='string'||typeof item.folder!=='string'
            ||item.mainUrl!==prefix+'picker-files/'+item.mainFileId+'/'||item.previewUrl!==prefix+'picker-files/'+item.previewFileId+'/')throw new Error('EDITOR_MEDIA_INVALID');
          remember(item.assetId,item.mainUrl,item.previewUrl);
          const choose=button('Выбрать '+item.label,async()=>{
            if(!canEdit())return;
            if(record.invalid){notice.textContent='Сначала исправьте описание и размеры выбранного фото.';return;}
            const previous=current(field);
            record.pending={...(previous||{alt:'',alignment:'center',width_px:null,height_px:null}),asset_id:item.assetId};
            invalidate();notice.textContent='Сравните прежнее и новое фото, затем подтвердите замену здесь.';render(record);
          });choose.dataset.editorMediaAsset=item.assetId;record.list.append(choose);
        }
        if(!result.items.length)record.list.append(element('p','Подходящих готовых фото нет.'));
        more.hidden=after===null;notice.textContent='Выбор из медиатеки не изменяет страницу до подтверждения и сохранения.';
      }
      const more=button('Следующие фото',()=>browse(after));more.hidden=true;
      const open=button('Выбрать фото',()=>browse());open.dataset.editorMediaAction='open';
      controls.append(folderLabel,queryLabel,open,more,button('Убрать со страницы',async()=>{
        if(!canEdit())return;initial.values[field]=null;record.pending=null;record.list.replaceChildren();invalidate();render(record);
        notice.textContent='Ссылка убрана только в редакторе. Сам файл и история сохраняются.';
      }));section.append(controls,record.list,pendingHost);
      for(const [key,text] of [['alt','Описание фото (alt)'],['alignment','Выравнивание'],['width_px','Ширина, px'],['height_px','Высота, px']]){
        const wrapper=element('label',text+' '),input=element(key==='alignment'?'select':'input');
        input.setAttribute('aria-label',label+': '+text);input.dataset.editorMediaField=key;
        if(key==='alignment'){for(const [value,title] of [['left','Слева'],['center','По центру'],['right','Справа']]){const option=element('option',title);option.value=value;input.append(option);}}
        else input.type=key==='alt'?'text':'number';
        input.addEventListener('input',()=>{
          if(!canEdit())return;invalidate();
          try{
            const changed=current(field);if(changed===null)throw new Error('EDITOR_MEDIA_INVALID');
            for(const [name,control] of Object.entries(record.metadata)){
              if(name==='alt'||name==='alignment')changed[name]=control.value;
              else{
                if(control.validity.badInput||(control.value!==''&&!/^[1-9][0-9]*$/u.test(control.value)))throw new Error('EDITOR_MEDIA_INVALID');
                changed[name]=control.value===''?null:Number(control.value);
              }
            }
            initial.values[field]=ref(changed);record.invalid=false;notice.textContent='Описание изменено в памяти. Проверьте и сохраните страницу.';
          }catch{record.invalid=true;notice.textContent='Проверьте описание и размеры фото. Страница с этим вводом не будет отправлена.';}
        });record.metadata[key]=input;wrapper.append(input);section.append(wrapper);
      }
    }
    render(record);
  }
  return Object.freeze({
    valid(){return ![...records.values()].some(record=>record.invalid||record.pending);},
    refresh(){for(const record of records.values())render(record);},
    destroy(){destroyed=true;for(const section of sections){for(const img of section.querySelectorAll('img'))img.removeAttribute('src');section.replaceChildren();section.remove();}for(const record of records.values()){record.pending=null;}records.clear();urls.clear();}
  });
}
