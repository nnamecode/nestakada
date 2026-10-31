import {createEditor} from './carrier-editor.mjs';

const LABELS={intro_text:'Вводный текст',main_text:'Основной текст'};
const FONTS=[['inter','Inter'],['oswald','Oswald'],['arial','Arial'],['georgia','Georgia'],['times-new-roman','Times New Roman'],['courier-new','Courier New']];
const STATUS={SESSION_ENDED:'Сессия завершена. Войдите снова, затем проверьте права и введённый текст.',PERMISSION_DENIED:'Действие недоступно. Изменения не отправляются автоматически.',BASE_CHANGED:'Страница уже изменена. Сравните правки с актуальной редакцией.',CHECK_CHANGED:'Ввод изменился после проверки. Проверьте его ещё раз.',UNKNOWN_RESULT:'Результат сохранения пока неизвестен. Не повторяйте отправку с новым намерением.',CSRF_FAILED:'Не удалось проверить защиту запроса. Войдите снова и выполните проверку явно.'};
const STATUS_ALIASES=Object.freeze({EDITOR_SESSION_ENDED:'SESSION_ENDED',EDITOR_FIELDS_FORBIDDEN:'PERMISSION_DENIED',EDITOR_BASE_CONFLICT:'BASE_CHANGED'});
function fail(code){const error=new Error(code);error.code=code;throw error;}
function uuid(){const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;const hex=[...bytes].map(value=>value.toString(16).padStart(2,'0')).join('');return hex.slice(0,8)+'-'+hex.slice(8,12)+'-'+hex.slice(12,16)+'-'+hex.slice(16,20)+'-'+hex.slice(20);}
function button(label,handler){const element=document.createElement('button');element.type='button';element.textContent=label;element.addEventListener('click',handler);return element;}
function select(label,options,handler){const wrapper=document.createElement('label'),element=document.createElement('select');wrapper.append(document.createTextNode(label+' '),element);element.setAttribute('aria-label',label);for(const [value,text] of options){const option=document.createElement('option');option.value=value;option.textContent=text;element.append(option);}element.addEventListener('change',()=>handler(element.value));return wrapper;}

/**
 * Root supplies actual transport/identity callbacks. This module has no routes,
 * credentials, storage, automatic retry, draft policy or own publication engine.
 * initialState: root's versioned state, fields:[{name,rawHtml,approvedHtml|null}],
 * values:all allowed changes. check(changes) returns normalisedChanges,
 * normalisationChanged,fieldWarnings,checkReceipt,baseRevisionId.
 * save/draft({changes,checkReceipt,operationId,context}) return a DEV05 receipt.
 */
export function mountEditorPage({root,initialState,styleSheet,check,save,draft,reauth}={}){
  if(!(root instanceof HTMLElement)||!initialState||typeof initialState.owner!=='boolean'||!Array.isArray(initialState.fields)||!initialState.values||typeof check!=='function')fail('EDITOR_MOUNT_INVALID');
  const editors=new Map(),owned=[],viewErrors=new Set();let epoch=0,busy=false,pending=null,accepted=null,applying=false,destroyed=false,uncertain=null,identityChanged=false;
  const status=root.querySelector('[data-editor-status]')||document.createElement('p');if(!status.parentNode){status.dataset.editorStatus='';root.append(status);owned.push(status);}status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const dirty=root.querySelector('[data-editor-dirty]')||document.createElement('p');if(!dirty.parentNode){dirty.dataset.editorDirty='';root.append(dirty);owned.push(dirty);}
  const actions=document.createElement('div');actions.className='es-page-actions';root.append(actions);owned.push(actions);
  const review=document.createElement('section');review.className='es-review';review.hidden=true;root.append(review);owned.push(review);
  const show=text=>{status.textContent=text;};
  const error=exception=>{const code=typeof exception?.code==='string'?exception.code:'';const key=Object.hasOwn(STATUS_ALIASES,code)?STATUS_ALIASES[code]:code;show((Object.hasOwn(STATUS,key)?STATUS[key]:null)||(viewErrors.size?'Не удалось обновить визуальное оформление. Ввод сохранён в памяти. Нажмите «Проверить» перед сохранением.':'Действие не выполнено. Ввод остаётся в открытой вкладке. Проверьте данные перед повторной попыткой.'));};
  function inputs(){return Object.fromEntries([...editors].map(([field,editor])=>[field,editor.getInput()]));}
  function changes(){return {...initialState.values,...Object.fromEntries(Object.entries(inputs()).map(([field,input])=>[field,input.html]))};}
  const retryButton=button('Повторить проверку результата прежней отправки',()=>{});retryButton.hidden=true;retryButton.dataset.editorAction='retry-intent';actions.append(retryButton);
  function invalidate(){if(applying)return;epoch++;accepted=null;pending=null;review.hidden=true;dirty.textContent='Есть несохранённые изменения.';}
  function adapterFailure(field,exception){
    // This must invalidate even during a failed checked-response application.
    epoch++;accepted=null;pending=null;review.hidden=true;dirty.textContent='Изменения не сохранены. Для продолжения выполните проверку.';
    if(exception.viewBlocked)viewErrors.add(field);error(exception);
  }
  function guarded(fn){return async()=>{if(destroyed||busy||identityChanged)return;busy=true;for(const node of actions.querySelectorAll('button'))node.disabled=true;
    try{await fn();}catch(exception){if(exception?.code==='EDITOR_IDENTITY_CHANGED')changedIdentity();else error(exception);}finally{busy=false;if(!identityChanged)for(const node of actions.querySelectorAll('button'))node.disabled=false;}};}
  function acceptChecked(result,capturedEpoch){
    if(epoch!==capturedEpoch)fail('CHECK_CHANGED');
    if(!result||!result.normalisedChanges||typeof result.checkReceipt!=='string')fail('EDITOR_CHECK_RESPONSE_INVALID');
    for(const [field,editor] of editors){if(typeof result.normalisedChanges[field]!=='string')fail('EDITOR_CHECK_RESPONSE_INVALID');editor.validateApprovedHtml(result.normalisedChanges[field]);}
    // Prepare every response before replacing anything. A failed field never
    // triggers publication; root can retain/restore its own versioned state.
    const previous=inputs();applying=true;
    try{for(const [field,editor] of editors)editor.setApprovedHtml(result.normalisedChanges[field],{emitDirty:false});}
    catch(exception){for(const [field,editor] of editors)editor.setRawHtml(previous[field].html);throw exception;}
    finally{applying=false;}
    viewErrors.clear();
    Object.assign(initialState.values,structuredClone(result.normalisedChanges));
    accepted={result,epoch};pending=null;review.hidden=true;dirty.textContent='Проверено. Для применения нажмите «Сохранить».';
  }
  function showReview(result,capturedEpoch){
    pending={result,epoch:capturedEpoch};review.replaceChildren();review.hidden=false;
    const heading=document.createElement('h2');heading.textContent='Проверьте подготовленное содержимое';review.append(heading);
    const note=document.createElement('p');note.textContent='Ничего не опубликовано. Примите проверенный вариант, затем сохраните его отдельным действием.';review.append(note);
    for(const field of editors.keys()){
      const html=result.normalisedChanges?.[field];
      const title=document.createElement('h3'),pre=document.createElement('pre');title.textContent=LABELS[field]||'Содержимое';pre.textContent=html;review.append(title,pre);
    }
    const otherFields=Object.entries(result.normalisedChanges||{}).filter(([field])=>!editors.has(field));
    if(otherFields.length){const details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent='Остальные проверенные поля';pre.textContent=JSON.stringify(Object.fromEntries(otherFields),null,2);details.append(summary,pre);review.append(details);}
    review.append(button('Принять проверенный вариант',()=>{try{if(!pending)fail('CHECK_CHANGED');acceptChecked(pending.result,pending.epoch);show('Проверенный вариант подставлен. Он ещё не сохранён.');}catch(exception){error(exception);}}),button('Отмена',()=>{pending=null;review.hidden=true;show('Проверка не применена. Ваш ввод сохранён в памяти вкладки.');}));
  }
  function stageUntrusted({field,html,text,intent}){
    const editor=editors.get(field);if(!editor)return;
    review.replaceChildren();review.hidden=false;pending=null;
    const title=document.createElement('h2');title.textContent=intent==='link'?'Проверка новой ссылки':'Вставка в HTML-режиме';
    const note=document.createElement('p');note.textContent=intent==='link'?'Новая ссылка ещё не вставлена в визуальный редактор. Сначала проверьте её на сервере.':'Форматированный HTML не вставлен в визуальный редактор. В подготовленном тексте он добавлен в конец текущего поля; проверьте расположение вручную.';
    const area=document.createElement('textarea');area.className='es-html-source';area.setAttribute('aria-label','Подготовленный HTML для проверки');area.value=intent==='link'?html:editor.getInput().html+(html||text.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'));
    review.append(title,note,area,button('Перенести в HTML-режим',()=>{editor.setRawHtml(area.value);review.hidden=true;show('HTML находится только в памяти. Нажмите «Проверить», чтобы подготовить визуальный вариант.');}),button('Отмена',()=>{review.hidden=true;show('Вставка отменена. Исходный ввод не заменён.');}));
  }
  function controls(host,editor,field){
    const toolbar=document.createElement('div');toolbar.className='es-toolbar';toolbar.setAttribute('role','toolbar');toolbar.setAttribute('aria-label','Форматирование: '+LABELS[field]);host.prepend(toolbar);owned.push(toolbar);
    const command=(name,value)=>{try{editor.command(name,value);}catch(exception){error(exception);}};
    toolbar.append(select('Стиль',[['p','Обычный текст'],...(initialState.owner?[['h1','H1']]:[]),['h2','H2'],['h3','H3'],['quote','Цитата']],value=>value==='p'?command('paragraph'):value==='quote'?command('blockquote'):command('heading',Number(value[1]))));
    for(const [label,name] of [['Ж','bold'],['К','italic'],['Подчеркнуть','underline'],['Зачеркнуть','strike'],['Нижний индекс','subscript'],['Верхний индекс','superscript'],['Список','bulletList'],['Нумерация','orderedList'],['Убрать оформление','clearFormatting'],['Отменить','undo'],['Повторить','redo']])toolbar.append(button(label,()=>command(name)));
    toolbar.append(select('Шрифт',FONTS,value=>command('font',value)));
    const size=document.createElement('input');size.type='number';size.min='8';size.max='72';size.step='any';size.setAttribute('aria-label','Размер текста, px');size.addEventListener('change',()=>command('size',size.value));toolbar.append(size);
    for(const [label,name] of [['Цвет текста','fg'],['Цвет подложки','bg']]){const input=document.createElement('input');input.type='color';input.setAttribute('aria-label',label);input.addEventListener('change',()=>command(name,input.value));toolbar.append(input);}
    toolbar.append(button('Прозрачная подложка',()=>command('bg','transparent')),select('Выравнивание',[['left','Слева'],['center','По центру'],['right','Справа'],['justify','По ширине']],value=>command('align',value)));
    for(const [name,label] of [['mt','Отступ сверху'],['mr','Отступ справа'],['mb','Отступ снизу'],['ml','Отступ слева']]){const input=document.createElement('input');input.type='number';input.min='0';input.max='64';input.step='1';input.setAttribute('aria-label',label+', px');input.addEventListener('change',()=>command(name,input.value));toolbar.append(input);}
    const link=document.createElement('input');link.type='text';link.setAttribute('aria-label','Адрес ссылки');toolbar.append(link,button('Добавить ссылку',()=>command('link',{href:link.value,target:'_self'})),button('Убрать ссылку',()=>command('removeLink')));
    toolbar.append(button('HTML',()=>{try{editor.setMode('html');show('HTML редактируется только в памяти. Для возврата в визуальный режим выполните проверку.');}catch(exception){error(exception);}}),button('Визуальный режим',()=>{try{editor.setMode('visual');}catch{show('Сначала нажмите «Проверить» и примите подготовленный вариант.');}}));
  }
  for(const state of initialState.fields){
    const field=state?.name;
    if(!Object.hasOwn(LABELS,field)||editors.has(field)||!state||typeof state.rawHtml!=='string'||state.approvedHtml!==null&&typeof state.approvedHtml!=='string')fail('EDITOR_MOUNT_INVALID');
    const host=root.querySelector('[data-editor-field="'+field+'"]');if(!host)fail('EDITOR_FIELD_MISSING');
    let mount=host.querySelector('[data-editor-mount]');if(!mount){mount=document.createElement('div');mount.dataset.editorMount='';host.append(mount);owned.push(mount);}
    const editor=createEditor(mount,{approvedHtml:state.approvedHtml??'',owner:initialState.owner,field,styleSheet,onDirty:invalidate,onError:exception=>adapterFailure(field,exception),onUntrustedInput:stageUntrusted});editors.set(field,editor);controls(host,editor,field);
    if(state.approvedHtml===null){applying=true;try{editor.setRawHtml(state.rawHtml);}finally{applying=false;}}
  }
  if(!editors.size)fail('EDITOR_FIELDS_REQUIRED');
  async function prepare(intent){
    const capturedEpoch=epoch,data=changes();let result;
    try{result=await check(data);}catch(exception){if(exception?.code==='EDITOR_IDENTITY_CHANGED')scrub(data);throw exception;}
    if(capturedEpoch!==epoch)fail('CHECK_CHANGED');
    if(!result||!result.normalisedChanges)fail('EDITOR_CHECK_RESPONSE_INVALID');
    const changed=[...editors.keys()].some(field=>result.normalisedChanges[field]!==data[field]);
    if(result.normalisationChanged||changed){showReview(result,capturedEpoch);show('Проверьте изменения нормализации перед применением.');return null;}
    acceptChecked(result,capturedEpoch);return result;
  }
  const checkButton=button('Проверить',guarded(async()=>{await prepare('check');if(accepted)show('Проверка пройдена. Ничего не опубликовано.');}));checkButton.dataset.editorAction='check';actions.append(checkButton);
  async function submitIntent(intent){
    const response=await intent.callback(structuredClone(intent.body));
    const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
    if(!response||response.operation_id!==intent.body.operationId||!uuid.test(response.result_id||'')||typeof response.result_code!=='string'||!response.result_code||typeof response.replay!=='boolean'||typeof response.gone!=='boolean')fail('UNKNOWN_RESULT');
    uncertain=null;retryButton.hidden=true;
    if(intent.epoch!==epoch){show('Прежняя операция подтверждена. Новые изменения остаются в открытой вкладке и ещё не сохранены.');return;}
    accepted=null;pending=null;dirty.textContent=intent.name==='draft'?'Черновик сохранён отдельно от сайта.':'Сохранение подтверждено.';
    show(response.gone?'Операция обработана. Снимок больше не хранится.':intent.name==='draft'?'Черновик сохранён. Публичная версия не изменена.':'Изменения сохранены.');
  }
  async function transmitIntent(intent){
    try{await submitIntent(intent);}catch(exception){
      if(exception?.code==='EDITOR_IDENTITY_CHANGED'){scrub(intent.body);throw exception;}
      if(exception?.outcomeKnown===true&&[400,401,403,404,408,409,411,413,415].includes(exception.status)){
        uncertain=null;retryButton.hidden=true;invalidate();throw exception;
      }
      uncertain=intent;retryButton.hidden=false;throw Object.assign(new Error('UNKNOWN_RESULT'),{code:'UNKNOWN_RESULT'});
    }
  }
  retryButton.addEventListener('click',guarded(async()=>{if(!uncertain)return;await transmitIntent(uncertain);}));
  for(const [label,name,callback] of [['Сохранить','save',save],['Сохранить черновик','draft',draft]]){
    if(typeof callback!=='function')continue;
    const action=button(label,guarded(async()=>{
      if(uncertain){show(STATUS.UNKNOWN_RESULT);return;}
      if(viewErrors.size){show('Не удалось обновить визуальное оформление. Ввод сохранён в памяти. Нажмите «Проверить» перед сохранением.');return;}
      const result=accepted?.epoch===epoch?accepted.result:await prepare(name);if(!result)return;
      const context=Object.fromEntries(['pageId','generation','baseRevisionId','editingFrom','draftBasis','stageId'].map(key=>[key,initialState[key]??null]));
      const intent={name,callback,epoch,body:structuredClone({changes:result.normalisedChanges,checkReceipt:result.checkReceipt,operationId:uuid(),context})};
      await transmitIntent(intent);
    }));action.dataset.editorAction=name;actions.append(action);
  }
  if(initialState.owner&&typeof draft!=='function'){const note=document.createElement('p');note.textContent='Сохранение черновика на этом экране пока недоступно.';actions.append(note);}
  if(typeof save!=='function')show('Визуальная правка доступна. Сохранение пока не подключено.');else show('Ввод остаётся в памяти вкладки до явного сохранения.');
  function scrub(value,seen=new Set()){
    if(!value||typeof value!=='object'||seen.has(value))return;seen.add(value);
    for(const key of Object.keys(value)){scrub(value[key],seen);delete value[key];}
    if(Array.isArray(value))value.length=0;
  }
  function clearOwnedCopies(){
    scrub(uncertain?.body);scrub(accepted?.result);scrub(pending?.result);
    scrub(initialState.values);initialState.values={};scrub(initialState.fields);initialState.fields=[];
    for(const name of ['pageId','generation','baseRevisionId','editingFrom','draftBasis','stageId','checkReceipt']){scrub(initialState[name]);initialState[name]=null;}
    for(const node of root.querySelectorAll('textarea,input,pre')){if('value' in node)node.value='';else node.textContent='';}
  }
  function changedIdentity(){
    identityChanged=true;clearOwnedCopies();uncertain=null;accepted=null;pending=null;retryButton.hidden=true;review.replaceChildren();review.hidden=true;
    for(const editor of editors.values())editor.destroy();editors.clear();
    for(const control of root.querySelectorAll('button,input,select,textarea'))control.disabled=true;
    show('Пользователь изменился. Откройте доступную страницу заново.');
  }
  if(typeof reauth==='function')actions.append(button('Войти снова',guarded(async()=>{
    let response;
    try{response=await reauth();}catch(exception){if(exception?.code==='EDITOR_IDENTITY_CHANGED'){changedIdentity();return;}throw exception;}
    if(!response||typeof response!=='object'||typeof response.sameUser!=='boolean')fail('EDITOR_REAUTH_INCOMPLETE');
    if(response.sameUser===false){changedIdentity();return;}
    accepted=null;pending=null;review.hidden=true;
    show('Вход выполнен. Проверьте актуальные права и данные, затем сохраните изменения явно.');
  })));
  const externalInput=event=>{if(!event.target.closest?.('[data-editor-field]')&&!review.contains(event.target))invalidate();};
  root.addEventListener('input',externalInput);
  return Object.freeze({editors,getInputs:inputs,getChanges:changes,invalidate,
    destroy(){if(destroyed)return;destroyed=true;clearOwnedCopies();uncertain=null;accepted=null;pending=null;root.removeEventListener('input',externalInput);for(const editor of editors.values())editor.destroy();editors.clear();review.replaceChildren();for(const node of owned)node.remove();}});
}
