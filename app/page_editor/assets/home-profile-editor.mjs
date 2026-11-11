const exact=(value,keys)=>value&&typeof value==='object'&&!Array.isArray(value)&&JSON.stringify(Object.keys(value).sort())===JSON.stringify([...keys].sort());

export function validateHomeProfileShape(value){
  if(!exact(value,['schema','hero','advantages','comparisons','steps','services','prices','photo_strip','works','reviews'])||value.schema!=='home-profile-v1')throw new Error('HOME_PROFILE_UI_INVALID');
  if(!Array.isArray(value.advantages)||value.advantages.length!==8||!Array.isArray(value.comparisons)||value.comparisons.length!==3||!Array.isArray(value.steps)||value.steps.length!==5||!Array.isArray(value.services)||value.services.length!==8||!Array.isArray(value.prices)||value.prices.length!==6||!Array.isArray(value.works)||value.works.length!==6)throw new Error('HOME_PROFILE_UI_INVALID');
  for(const group of value.prices)if(!Array.isArray(group.rows)||group.rows.length<1||group.rows.length>8)throw new Error('HOME_PROFILE_UI_INVALID');
  return value;
}

const node=(name,text)=>{const value=document.createElement(name);if(text!==undefined)value.textContent=text;return value;};

export function mountHomeProfileEditor({root,initial,searchSources,invalidate}={}){
  if(!(root instanceof HTMLElement)||!initial?.owner||typeof searchSources!=='function'||typeof invalidate!=='function')throw new Error('HOME_PROFILE_UI_MOUNT_INVALID');
  validateHomeProfileShape(initial.values.home_profile);
  const host=node('section');host.className='es-home-profile-editor';host.dataset.homeProfileEditor='';
  host.append(node('h2','Содержимое главной страницы'),node('p','Поля и порядок секций фиксированы. Произвольные шаблоны, HTML, CSS и JavaScript здесь не принимаются.'));
  const profile=()=>validateHomeProfileShape(initial.values.home_profile);
  const get=path=>path.reduce((value,key)=>value[key],profile());
  const controls=[];
  const same=(left,right)=>left.length===right.length&&left.every((value,index)=>value===right[index]);
  const put=(path,value)=>{const key=path.at(-1),parent=path.slice(0,-1).reduce((row,item)=>row[item],profile());parent[key]=value;for(const item of controls)if(same(item.path,path)){if(item.kind==='check')item.control.checked=value;else item.control.value=value??'';}invalidate();};
  function field(parent,label,path,{area=false,readonly=false,nullable=false}={}){
    const wrap=node('label'),control=node(area?'textarea':'input');wrap.append(document.createTextNode(label+' '),control);
    control.value=get(path)??'';control.readOnly=readonly;if(!readonly)control.addEventListener('input',()=>put(path,nullable&&!control.value?null:control.value));controls.push({path,control,kind:'value'});parent.append(wrap);return control;
  }
  function check(parent,label,path){const wrap=node('label'),control=node('input');control.type='checkbox';control.checked=get(path);control.addEventListener('change',()=>put(path,control.checked));controls.push({path,control,kind:'check'});wrap.append(control,document.createTextNode(' '+label));parent.append(wrap);}
  function fixed(parent,label,path){field(parent,label,path,{readonly:true});}
  function card(parent,title){const value=node('fieldset');value.append(node('legend',title));parent.append(value);return value;}
  function binding(parent,path,{rowPath=null}={}){
    const box=node('div');box.className='es-source-picker';
    const current=node('p'),query=node('input'),results=node('div'),status=node('p');query.type='search';query.maxLength=100;query.placeholder='Название или внутренний адрес';
    const paint=()=>{current.textContent='Источник: '+(get(path)??'не выбран');};paint();
    const clear=node('button','Снять привязку');clear.type='button';clear.addEventListener('click',()=>{put(path,null);if(rowPath)put(rowPath,null);results.replaceChildren();paint();});
    const find=node('button','Найти источник');find.type='button';find.addEventListener('click',async()=>{
      results.replaceChildren();const q=query.value;if(!q||q!==q.trim()){status.textContent='Введите запрос без пробелов по краям.';return;}
      find.disabled=true;try{
        const value=await searchSources(q);if(!exact(value,['protocol','results','hasNext'])||value.protocol!=='home-source-candidates-v1'||!Array.isArray(value.results)||value.results.length>20||typeof value.hasNext!=='boolean')throw new Error('HOME_SOURCE_RESPONSE_INVALID');
        for(const item of value.results){if(!exact(item,['pageId','path','name','kind','published','currentRevisionId']))throw new Error('HOME_SOURCE_RESPONSE_INVALID');const choose=node('button',item.path+' — '+item.name);choose.type='button';choose.addEventListener('click',()=>{if(get(path)!==item.pageId&&rowPath)put(rowPath,null);put(path,item.pageId);paint();results.replaceChildren();status.textContent='Источник выбран. Сохранение ещё не выполнено.';});results.append(choose);}
        status.textContent=value.results.length?(value.hasNext?'Показаны первые 20 совпадений. Уточните запрос при необходимости.':'Выберите один источник.'):'Совпадений нет.';
      }catch{status.textContent='Поиск источников недоступен. Ничего не изменено.';}finally{find.disabled=false;}
    });
    box.append(current,query,find,clear,results,status);parent.append(box);
  }

  let section=card(host,'Главный экран');field(section,'Краткое описание',['hero','lead'],{area:true});field(section,'Описание изображения',['hero','alt']);fixed(section,'ID изображения',['hero','image_id']);
  section=card(host,'Преимущества');for(let i=0;i<8;i++)field(section,'Преимущество '+(i+1),['advantages',i]);
  section=card(host,'Сравнение');for(let i=0;i<3;i++){const item=card(section,'Карточка '+(i+1));field(item,'Заголовок',['comparisons',i,'heading'],{area:true});for(let j=0;j<get(['comparisons',i,'bullets']).length;j++)field(item,'Пункт '+(j+1),['comparisons',i,'bullets',j]);field(item,'Знак',['comparisons',i,'result_mark']);field(item,'Итог',['comparisons',i,'result_text'],{area:true});}
  section=card(host,'Этапы работы');for(let i=0;i<5;i++){const item=card(section,'Этап '+(i+1));field(item,'Заголовок',['steps',i,'heading']);field(item,'Текст',['steps',i,'text'],{area:true});field(item,'Описание изображения',['steps',i,'alt']);fixed(item,'ID изображения',['steps',i,'image_id']);}
  section=card(host,'Услуги');for(let i=0;i<8;i++){const item=card(section,'Услуга '+(i+1));fixed(item,'ID карточки',['services',i,'id']);field(item,'Название',['services',i,'label']);field(item,'Подпись',['services',i,'caption']);field(item,'Внутренний адрес',['services',i,'url']);field(item,'Описание изображения',['services',i,'alt']);fixed(item,'ID изображения',['services',i,'image_id']);check(item,'Показывать сохранённый вариант без источника',['services',i,'fallback_visible']);binding(item,['services',i,'source_page_id']);}
  section=card(host,'Цены');for(let i=0;i<6;i++){const group=card(section,'Группа '+(i+1));fixed(group,'ID группы',['prices',i,'id']);fixed(group,'Ключ группы',['prices',i,'key']);field(group,'Название',['prices',i,'label']);field(group,'Внутренний адрес',['prices',i,'url']);binding(group,['prices',i,'source_page_id']);for(let j=0;j<get(['prices',i,'rows']).length;j++){const row=card(group,'Строка '+(j+1));fixed(row,'ID строки',['prices',i,'rows',j,'id']);field(row,'Название',['prices',i,'rows',j,'label']);field(row,'Внутренний адрес',['prices',i,'rows',j,'url']);field(row,'Сохранённая цена',['prices',i,'rows',j,'price_text']);check(row,'Показывать сохранённый вариант без источника',['prices',i,'rows',j,'fallback_visible']);field(row,'ID строки цены в источнике',['prices',i,'rows',j,'source_row_id'],{nullable:true});binding(row,['prices',i,'rows',j,'source_page_id'],{rowPath:['prices',i,'rows',j,'source_row_id']});}}
  section=card(host,'Полоса фотографий');field(section,'Описание изображения',['photo_strip','alt']);fixed(section,'ID изображения',['photo_strip','image_id']);
  section=card(host,'Работы');for(let i=0;i<6;i++){const item=card(section,'Работа '+(i+1));fixed(item,'ID карточки',['works',i,'id']);field(item,'Название',['works',i,'label'],{area:true});field(item,'Подпись количества фото',['works',i,'photo_count_text']);field(item,'Внутренний адрес',['works',i,'url']);field(item,'Описание изображения',['works',i,'alt']);fixed(item,'ID изображения',['works',i,'image_id']);fixed(item,'ID медиафайла',['works',i,'asset_id']);check(item,'Показывать сохранённый вариант без источника',['works',i,'fallback_visible']);binding(item,['works',i,'source_page_id']);}
  section=card(host,'Отзывы');fixed(section,'Заголовок',['reviews','heading']);fixed(section,'Внутренний адрес',['reviews','url']);fixed(section,'Подпись ссылки',['reviews','label']);
  root.append(host);return Object.freeze({host});
}
