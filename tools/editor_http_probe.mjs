// DEV07-C: actual product UI/HTTP/adapter, fixed local origin, no trace/secrets.
import fs from 'node:fs';
import crypto from 'node:crypto';
import readline from 'node:readline';
import {chromium} from '/tests/node_modules/playwright/index.mjs';

const origin='http://host.docker.internal:8767';
const output=value=>process.stdout.write(JSON.stringify(value)+'\n');
const ensure=(value,code)=>{if(!value)throw new Error(code);};
const safe=path=>{const url=new URL(path,origin);ensure(typeof path==='string'&&path.startsWith('/')&&url.origin===origin,'FIXED_ORIGIN');return url.href;};
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
const pendingObservers=new Map();let observationSerial=0;
const channel=readline.createInterface({input:process.stdin,terminal:false});
channel.on('line',line=>{try{const value=JSON.parse(line);const waiter=pendingObservers.get(value.id);
  if(value.kind==='observation'&&waiter){pendingObservers.delete(value.id);value.error?waiter.reject(new Error('HOST_OBSERVER_FAILED')):waiter.resolve(value.value);}
}catch{process.exitCode=1;}});
function observe(){return new Promise((resolve,reject)=>{const id=++observationSerial;
  const timer=setTimeout(()=>{pendingObservers.delete(id);reject(new Error('OBSERVER_TIMEOUT'));},30000);
  pendingObservers.set(id,{resolve:value=>{clearTimeout(timer);resolve(value);},reject:error=>{clearTimeout(timer);reject(error);}});
  output({kind:'observe',id});});}

const results=[],contexts=[],pageErrors=[],responseReads=new Set(),lastResponses={check:null,save:null};let current='START',browser,diagnosticPage;
const fixedCode=value=>typeof value==='string'&&/^[A-Z0-9_]{1,120}$/.test(value)?value:null;
const editorUrl=value=>{try{const url=new URL(value);return url.origin===origin&&/^\/manage\/pages\/[0-9a-f-]{36}\/edit\/$/.test(url.pathname)&&!url.search&&!url.hash;}catch{return false;}};
function wireDiagnostics(page){
  page.on('framenavigated',frame=>{if(frame===page.mainFrame()&&editorUrl(frame.url()))diagnosticPage=page;});
  page.on('pageerror',error=>{if(pageErrors.length<16)pageErrors.push({code:fixedCode(error?.message)||'UNCLASSIFIED_PAGE_ERROR',
    errorClass:typeof error?.constructor?.name==='string'&&/^[A-Za-z0-9_]{1,80}$/.test(error.constructor.name)?error.constructor.name:'Error'});});
  page.on('response',response=>{let url;try{url=new URL(response.url());}catch{return;}
    if(url.origin!==origin||!/^\/manage\/pages\/[0-9a-f-]{36}\/edit\/(check|save)\/$/.test(url.pathname))return;
    const kind=url.pathname.endsWith('/check/')?'check':'save',fact={status:response.status(),code:'NO_FIXED_CODE'};lastResponses[kind]=fact;
    // Decode only to extract an approved fixed code; no response body/HTML or
    // success payload/proof is retained, emitted or used for failure diagnosis.
    const read=(async()=>{try{const value=await response.json();fact.code=fixedCode(value?.code)||'NO_FIXED_CODE';}catch{fact.code='NON_JSON_RESPONSE';}})();
    responseReads.add(read);read.finally(()=>responseReads.delete(read));
  });
}
async function failureDiagnostics(){
  await Promise.race([Promise.allSettled([...responseReads]),new Promise(resolve=>setTimeout(resolve,2000))]);
  const result={lastResponses,pageErrors,cspEffectiveDirectives:[],status:'UNAVAILABLE',dirty:'UNAVAILABLE',screenshot:false};
  if(!diagnosticPage||diagnosticPage.isClosed()||!editorUrl(diagnosticPage.url()))return result;
  try{
    const observed=await diagnosticPage.evaluate(()=>({status:document.querySelector('[data-editor-status]')?.textContent||'',dirty:document.querySelector('[data-editor-dirty]')?.textContent||'',
      csp:Array.isArray(globalThis.__editorQaViolations)?globalThis.__editorQaViolations:[],ownEditor:document.querySelectorAll('[data-editor-page]').length===1,
      passwordVisible:[...document.querySelectorAll('input[type=password]')].some(element=>element.getClientRects().length)}));
    const statuses=new Set(['Загрузка редактора…','Ввод остаётся в памяти вкладки до явного сохранения.','Проверка пройдена. Ничего не опубликовано.',
      'Проверьте изменения нормализации перед применением.','Проверенный вариант подставлен. Он ещё не сохранён.','Изменения сохранены.',
      'Результат сохранения пока неизвестен. Не повторяйте отправку с новым намерением.','Действие не выполнено. Ввод остаётся в открытой вкладке. Проверьте данные перед повторной попыткой.',
      'Не удалось обновить визуальное оформление. Ввод сохранён в памяти. Нажмите «Проверить» перед сохранением.',
      'Вход выполнен. Проверьте актуальные права и данные, затем сохраните изменения явно.','Пользователь изменился. Откройте доступную страницу заново.',
      'HTML редактируется только в памяти. Для возврата в визуальный режим выполните проверку.','Сначала нажмите «Проверить» и примите подготовленный вариант.',
      'Сессия завершена. Войдите снова, затем проверьте права и введённый текст.','Действие недоступно. Изменения не отправляются автоматически.',
      'Страница уже изменена. Сравните правки с актуальной редакцией.','Ввод изменился после проверки. Проверьте его ещё раз.',
      'Не удалось проверить защиту запроса. Войдите снова и выполните проверку явно.']);
    const dirty=new Set(['Нет несохранённых изменений','Есть несохранённые изменения.','Проверено. Для применения нажмите «Сохранить».','Сохранение подтверждено.','Черновик сохранён отдельно от сайта.']);
    result.status=statuses.has(observed.status)?observed.status:'UNRECOGNIZED_FIXED_STATUS';result.dirty=dirty.has(observed.dirty)?observed.dirty:'UNRECOGNIZED_FIXED_DIRTY';
    result.cspEffectiveDirectives=observed.csp.filter(value=>typeof value==='string'&&/^[a-z-]{1,60}$/.test(value)).slice(0,32);
    if(observed.ownEditor&&!observed.passwordVisible){await diagnosticPage.screenshot({path:'/output/editor-failure.png',fullPage:true,timeout:5000,caret:'initial'});result.screenshot=true;}
  }catch{result.diagnosticCode='EDITOR_DIAGNOSTIC_UNAVAILABLE';}
  return result;
}
async function check(id,body){current=id;results.push({id,status:'PASS',...await body()});}
async function context(){const value=await browser.newContext({viewport:{width:1280,height:900},timezoneId:'UTC'});contexts.push(value);value.on('page',wireDiagnostics);
  await value.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  await value.addInitScript(()=>{globalThis.__editorQaViolations=[];globalThis.__editorQaCanary=0;
    document.addEventListener('securitypolicyviolation',event=>globalThis.__editorQaViolations.push(event.effectiveDirective));});
  return value;}
async function loginPage(ctx,account){const page=await ctx.newPage();await page.goto(safe('/manage/login/'));
  await page.locator('[name=username]').fill(account.username);await page.locator('[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(safe('/manage/'),{timeout:15000}),page.locator('form[action="/manage/login/"] button').click()]);return page;}
const field=page=>page.locator('[data-editor-field="main_text"]');
const action=(page,name)=>page.locator('.es-page-actions [data-editor-action="'+name+'"]');
async function ready(page){await page.locator('.es-page-actions').waitFor();await field(page).locator('.es-editor-surface').waitFor();}
async function rawInput(page,html){await field(page).locator('.es-toolbar').getByRole('button',{name:'HTML',exact:true}).click();
  await field(page).locator('.es-html-source').fill(html);}
async function checked(page){await action(page,'check').click();
  await page.waitForFunction(()=>{const root=document.querySelector('[data-editor-page]');return root&&(
    root.querySelector('.es-review:not([hidden])')||root.querySelector('[data-editor-dirty]')?.textContent.includes('Проверено.'));},{},{timeout:15000});
  const accept=page.locator('.es-review').getByRole('button',{name:'Принять проверенный вариант',exact:true});
  if(await accept.isVisible())await accept.click();}
async function saved(page){await action(page,'save').click();await page.waitForFunction(()=>document.querySelector('[data-editor-dirty]')?.textContent==='Сохранение подтверждено.',{},{timeout:20000});}
async function csrf(page){return page.locator('[data-editor-page] input[name=csrfmiddlewaretoken]').inputValue();}
async function apiCheck(who,pageId,base,changes){const response=await who.context.request.post(safe('/manage/pages/'+pageId+'/edit/check/'),{
  maxRedirects:0,timeout:30000,headers:{'Content-Type':'application/json','X-CSRFToken':await csrf(who.page)},
  data:JSON.stringify({protocol:'page-editor-v1',generation:1,baseRevisionId:base,editingFrom:'current',draftBasis:null,stageId:null,changes})});
  ensure(response.status()===200,'API_CHECK_FAILED');return response.json();}
const pageState=(state,id)=>{const value=state.pages.find(page=>page.id===id);ensure(value,'PAGE_OBSERVER_MISSING');return value;};
async function invariants(page){const facts=await page.evaluate(()=>({violations:globalThis.__editorQaViolations,
  canary:globalThis.__editorQaCanary,inline:document.querySelectorAll('[data-editor-page] [style], [data-editor-page] style, [data-editor-page] colgroup').length,
  local:localStorage.length,session:sessionStorage.length}));
  ensure(facts.violations.length===0,'CSP_VIOLATION');ensure(facts.canary===0,'INPUT_EXECUTED');ensure(facts.inline===0,'INLINE_STYLE_OR_COLGROUP');
  ensure(facts.local===0&&facts.session===0,'BROWSER_STORAGE_USED');return {cspViolations:0,inlineStyles:0};}

try{
  const seed=JSON.parse(fs.readFileSync('/private/editor-seed.json','utf8'));
  ensure(Array.isArray(seed.pageIds)&&seed.pageIds.length===2&&seed.accounts?.owner&&seed.accounts?.employee,'SEED_CONTRACT');
  const pageId=seed.pageIds[0],editPath='/manage/pages/'+pageId+'/edit/',saveUrl=safe(editPath+'save/');
  browser=await chromium.launch({headless:true});
  const ownerContext=await context(),ownerPage=await loginPage(ownerContext,seed.accounts.owner);
  const owner={context:ownerContext,page:ownerPage};
  await ownerPage.goto(safe(editPath));await ready(ownerPage);
  await check('EH001',async()=>{const before=await observe();await rawInput(ownerPage,'<p><b>UI 😀</b></p>');await checked(ownerPage);
    const afterCheck=await observe();ensure(afterCheck.domainHash===before.domainHash,'CHECK_MUTATED_DOMAIN');
    await saved(ownerPage);const after=await observe(),page=pageState(after,pageId);
    ensure(page.payload.main_text==='<p><strong>UI 😀</strong></p>','UI_SAVE_PAYLOAD');ensure(page.history.length===pageState(before,pageId).history.length+1,'ONE_AUTOMATIC');
    await ownerPage.reload();await ready(ownerPage);ensure((await field(ownerPage).locator('.es-editor-surface').innerText()).includes('UI 😀'),'RELOAD_LOST_SAVE');
    return {actualUiSave:true,resultId:page.currentId,...await invariants(ownerPage)};});

  await check('EH002',async()=>{const before=await observe(),base=pageState(before,pageId).currentId;
    const source='<p data-es-align="center" data-es-mt="8"><span data-es-font="arial" data-es-size="12.5" data-es-fg="#112233" data-es-bg="transparent">FORMAT <strong>😀</strong></span></p><table data-es-cellpad="4"><caption>CAPTION</caption><tbody><tr><th scope="row">H</th><td>DATA</td></tr></tbody></table>';
    const approved=await apiCheck(owner,pageId,base,{main_text:source});
    const facts=await ownerPage.evaluate(async html=>{const {createEditor}=await import('/manage/editor-assets/editor.bundle.js');
      const host=document.createElement('section');host.dataset.editorQaAdapter='';document.querySelector('[data-editor-page]').append(host);
      globalThis.__editorQaAdapterDirty=0;
      const editor=createEditor(host,{approvedHtml:html,owner:true,field:'main_text',styleSheet:document.querySelector('[data-editor-stylesheet]').sheet,onDirty:()=>globalThis.__editorQaAdapterDirty++});
      const canonical=editor.getCanonicalHtml(),span=host.querySelector('.es-editor-surface span'),p=host.querySelector('.es-editor-surface p');
      const walker=document.createTreeWalker(host.querySelector('.es-editor-surface'),NodeFilter.SHOW_TEXT);let emoji;
      while(walker.nextNode()){if(walker.currentNode.data.includes('😀')){emoji=walker.currentNode;break;}}
      const emojiParent=emoji?.parentElement;
      const result={canonical,size:getComputedStyle(span).fontSize,color:getComputedStyle(span).color,align:getComputedStyle(p).textAlign,
        opaque:host.querySelectorAll('.es-opaque-table').length,liveTable:host.querySelectorAll('table').length,
        nestedSize:emojiParent?getComputedStyle(emojiParent).fontSize:null,nestedColor:emojiParent?getComputedStyle(emojiParent).color:null,strongText:emoji?.data,nestedStrong:!!emojiParent?.closest('strong')};
      globalThis.__editorQaAdapter={editor,host};return result;},approved.normalisedChanges.main_text);
    ensure(facts.size==='12.5px'&&facts.color==='rgb(17, 34, 51)'&&facts.align==='center','FORMAT_COMPUTED_STYLE');
    ensure(facts.opaque===1&&facts.liveTable===0,'TABLE_NOT_APPROVED_OPAQUE');
    ensure(facts.nestedSize==='12.5px'&&facts.nestedColor==='rgb(17, 34, 51)'&&facts.strongText==='😀'&&facts.nestedStrong,'NESTED_MARK_FORMAT_LOST');
    const rechecked=await apiCheck(owner,pageId,base,{main_text:facts.canonical});
    if(rechecked.normalisedChanges.main_text!==approved.normalisedChanges.main_text){
      // EH002 uses the fixed synthetic source above, never editor/user input.
      // Write only the four HTML representations; no request/proof/credentials.
      fs.writeFileSync('/output/adapter-roundtrip.json',JSON.stringify({source,approved:approved.normalisedChanges.main_text,
        adapter:facts.canonical,rechecked:rechecked.normalisedChanges.main_text},null,2)+'\n',{mode:0o600});
    }
    ensure(rechecked.normalisedChanges.main_text===approved.normalisedChanges.main_text,'ADAPTER_SERVER_ROUNDTRIP');
    try{
      const surface=ownerPage.locator('[data-editor-qa-adapter] .es-editor-surface');
      await surface.focus();await ownerPage.keyboard.press('Control+Home');
      const focus=await surface.evaluate(element=>({active:document.activeElement===element,editable:element.contentEditable==='true',
        anchorInside:!!getSelection()?.anchorNode&&element.contains(getSelection().anchorNode),dirty:globalThis.__editorQaAdapterDirty}));
      ensure(focus.active&&focus.editable&&focus.anchorInside,'ADAPTER_EDIT_TARGET_NOT_FOCUSED');
      await ownerPage.keyboard.type('EDITED ');
      const transaction=await ownerPage.evaluate(()=>({canonical:globalThis.__editorQaAdapter.editor.getCanonicalHtml(),dirty:globalThis.__editorQaAdapterDirty,
        domChanged:globalThis.__editorQaAdapter.host.querySelector('.es-editor-surface').textContent.includes('EDITED ')}));
      ensure(transaction.dirty>focus.dirty&&transaction.domChanged,'ADAPTER_REAL_TRANSACTION_MISSING');
      const edited=transaction.canonical;
      ensure(edited!==approved.normalisedChanges.main_text&&edited.includes('EDITED '),'ADAPTER_CACHE_MASKED_REAL_EDIT');
      const editedStrong=await ownerPage.evaluate(html=>[...new DOMParser().parseFromString(html,'text/html').body.querySelectorAll('strong')].some(node=>node.textContent==='😀'),edited);
      ensure(editedStrong&&edited.includes('<table data-es-cellpad="4"><caption>CAPTION</caption><tbody><tr><th scope="row">H</th><td>DATA</td></tr></tbody></table>'),'EDIT_LOST_MARK_OR_OPAQUE_SOURCE');
      const editedChecked=await apiCheck(owner,pageId,base,{main_text:edited});
      ensure(editedChecked.normalisedChanges.main_text===edited,'EDIT_EXPORT_NOT_SERVER_STABLE');
      const undone=await ownerPage.evaluate(()=>{const {editor}=globalThis.__editorQaAdapter;editor.command('undo');return editor.getCanonicalHtml();});
      ensure(undone===approved.normalisedChanges.main_text,'UNDO_DID_NOT_RESTORE_EXACT_APPROVED');
      const loaded=await ownerPage.evaluate(html=>{const {editor,host}=globalThis.__editorQaAdapter;editor.setApprovedHtml(html);
        const walker=document.createTreeWalker(host.querySelector('.es-editor-surface'),NodeFilter.SHOW_TEXT);let emoji;
        while(walker.nextNode()){if(walker.currentNode.data.includes('😀')){emoji=walker.currentNode;break;}}
        const parent=emoji?.parentElement;return {canonical:editor.getCanonicalHtml(),size:parent?getComputedStyle(parent).fontSize:null,
          color:parent?getComputedStyle(parent).color:null,strongText:emoji?.data,strong:!!parent?.closest('strong'),opaque:host.querySelectorAll('.es-opaque-table').length};},editedChecked.normalisedChanges.main_text);
      ensure(loaded.canonical===edited&&loaded.size==='12.5px'&&loaded.color==='rgb(17, 34, 51)'&&loaded.strongText==='😀'&&loaded.strong&&loaded.opaque===1,'EDIT_RELOAD_FORMAT_OR_SOURCE_LOST');
    }finally{await ownerPage.evaluate(()=>{const value=globalThis.__editorQaAdapter;value?.editor.destroy();value?.host.remove();delete globalThis.__editorQaAdapter;delete globalThis.__editorQaAdapterDirty;});}
    ensure((await observe()).domainHash===before.domainHash,'ADAPTER_CHECK_MUTATED_DOMAIN');
    return {realAdapter:true,opaqueTables:1,actualEditExport:true,undoExactApproved:true,nestedMarkComputedStyle:true,canonicalSha256:hash(facts.canonical),...await invariants(ownerPage)};});

  await check('EH002-paste-drop',async()=>{const canary='EDITOR_UNTRUSTED_PASTE_CANARY',requests=[];
    const listener=request=>{if(request.url().includes(canary))requests.push(true);};ownerPage.on('request',listener);
    await ownerPage.evaluate(value=>{const descriptor=Object.getOwnPropertyDescriptor(Element.prototype,'innerHTML'),parse=DOMParser.prototype.parseFromString;
      globalThis.__editorRawParserCalls=0;globalThis.__editorRestoreParsers=()=>{Object.defineProperty(Element.prototype,'innerHTML',descriptor);DOMParser.prototype.parseFromString=parse;};
      Object.defineProperty(Element.prototype,'innerHTML',{...descriptor,set(input){if(String(input).includes(value))globalThis.__editorRawParserCalls++;return descriptor.set.call(this,input);}});
      DOMParser.prototype.parseFromString=function(input,...args){if(String(input).includes(value))globalThis.__editorRawParserCalls++;return parse.call(this,input,...args);};
    },canary);
    try{
      for(const kind of ['paste','drop']){
        await field(ownerPage).locator('.es-editor-surface').evaluate((element,{kind,canary})=>{const transfer=new DataTransfer();
          transfer.setData('text/html','<img src="https://outside.invalid/'+canary+'" onerror="globalThis.__editorQaCanary++"><style>'+canary+'{color:red}</style>');
          transfer.setData('text/plain',canary);const event=kind==='paste'?new ClipboardEvent('paste',{clipboardData:transfer,bubbles:true,cancelable:true}):new DragEvent('drop',{dataTransfer:transfer,bubbles:true,cancelable:true});element.dispatchEvent(event);
        },{kind,canary});
        await ownerPage.locator('.es-review textarea').waitFor();
        ensure((await ownerPage.locator('.es-review textarea').inputValue()).includes(canary),'RAW_NOT_RAM_STAGED');
        ensure(!await field(ownerPage).locator('.es-editor-surface').innerHTML().then(value=>value.includes(canary)),'RAW_INSERTED_LIVE');
        await ownerPage.locator('.es-review').getByRole('button',{name:'Отмена',exact:true}).click();
      }
      await field(ownerPage).locator('.es-editor-surface').evaluate(element=>{element.focus();const transfer=new DataTransfer();transfer.setData('text/plain','SAFE TEXT PASTE');element.dispatchEvent(new ClipboardEvent('paste',{clipboardData:transfer,bubbles:true,cancelable:true}));});
      ensure((await field(ownerPage).locator('.es-editor-surface').innerText()).includes('SAFE TEXT PASTE'),'PLAIN_TEXT_PASTE_POSITIVE');
      ensure(await ownerPage.evaluate(()=>globalThis.__editorRawParserCalls===0),'RAW_PARSED_BEFORE_SERVER');
      ensure(requests.length===0,'RAW_NETWORK_REQUEST');return {rawPasteDropPrevented:true,plainTextPositive:true,...await invariants(ownerPage)};
    }finally{await ownerPage.evaluate(()=>globalThis.__editorRestoreParsers());ownerPage.off('request',listener);}
  });

  await check('EH003',async()=>{await rawInput(ownerPage,'<p>KNOWN REFUSAL</p>');await checked(ownerPage);let firstOperation;
    await ownerPage.route(saveUrl,async route=>{firstOperation=JSON.parse(route.request().postData()).operationId;
      await route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({ok:false,code:'EDITOR_BASE_CONFLICT'})});},{times:1});
    const before=await observe();await action(ownerPage,'save').click();await action(ownerPage,'retry-intent').waitFor({state:'hidden'});
    await ownerPage.waitForFunction(()=>!document.querySelector('.es-page-actions [data-editor-action=save]').disabled);
    ensure((await observe()).domainHash===before.domainHash,'KNOWN_REFUSAL_CHANGED_DOMAIN');
    await rawInput(ownerPage,'<p>NEW INTENT</p>');await checked(ownerPage);let nextOperation;
    await ownerPage.route(saveUrl,async route=>{nextOperation=JSON.parse(route.request().postData()).operationId;await route.continue();},{times:1});
    await saved(ownerPage);ensure(firstOperation&&nextOperation&&firstOperation!==nextOperation,'KNOWN_REFUSAL_STUCK_PENDING');
    return {knownRefusalCleared:true};});

  for(const [suffix,mutate] of [['missing',value=>{delete value.result_id;}],['null',value=>{value.result_id=null;}],
                               ['action',value=>{value.action='other';}],['uuid',value=>{value.result_id='not-a-uuid';}]]){
    await check('EH004-'+suffix,async()=>{await rawInput(ownerPage,'<p>MALFORMED '+suffix+'</p>');await checked(ownerPage);
      let originalBody,requests=0;const before=await observe();
      await ownerPage.route(saveUrl,async route=>{requests++;const body=route.request().postData();
        if(!originalBody){originalBody=body;const value={operation_id:JSON.parse(body).operationId,action:'commit_owner',result_id:crypto.randomUUID(),result_code:'applied',gone:false,replay:false};mutate(value);
          await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(value)});
        }else{ensure(body===originalBody,'UNKNOWN_RETRY_BODY_CHANGED');await route.continue();}});
      await action(ownerPage,'save').click();await action(ownerPage,'retry-intent').waitFor({state:'visible'});
      await ownerPage.waitForTimeout(150);ensure(requests===1,'HIDDEN_AUTO_RETRY');ensure((await observe()).domainHash===before.domainHash,'FAULT_RESPONSE_COMMITTED');
      await action(ownerPage,'retry-intent').click();await ownerPage.waitForFunction(()=>document.querySelector('[data-editor-dirty]')?.textContent==='Сохранение подтверждено.',{},{timeout:20000});
      await ownerPage.unroute(saveUrl);ensure(requests===2,'MANUAL_RETRY_COUNT');return {unknownRetained:true,exactManualRetry:true};});
  }

  await check('EH005',async()=>{await rawInput(ownerPage,'<p>LOST RESPONSE SAME USER</p>');await checked(ownerPage);
    let originalBody,requests=0,committedResult;
    await ownerPage.route(saveUrl,async route=>{requests++;const body=route.request().postData();
      if(!originalBody){originalBody=body;const response=await route.fetch({maxRedirects:0,timeout:30000});ensure(response.status()===200,'LOST_RESPONSE_COMMIT_FAILED');committedResult=(await response.json()).result_id;await route.abort();}
      else{ensure(body===originalBody,'REAUTH_RETRY_BODY_CHANGED');await route.continue();}});
    await action(ownerPage,'save').click();await action(ownerPage,'retry-intent').waitFor({state:'visible'});
    const committed=await observe();ensure(pageState(committed,pageId).currentId===committedResult,'COMMIT_NOT_OBSERVED');
    const logoutToken=await ownerPage.locator('form[action="/manage/logout/"] [name=csrfmiddlewaretoken]').inputValue();
    ensure((await ownerContext.request.post(safe('/manage/logout/'),{maxRedirects:0,form:{csrfmiddlewaretoken:logoutToken}})).status()===303,'LOGOUT_FAILED');
    await action(ownerPage,'retry-intent').click();await ownerPage.waitForFunction(()=>!document.querySelector('.es-page-actions [data-editor-action=retry-intent]').disabled);
    ensure(requests===1,'STATE_401_SENT_SAVE');ensure(await action(ownerPage,'retry-intent').isVisible(),'STATE_401_CLEARED_UNKNOWN');
    const login=await loginPage(ownerContext,seed.accounts.owner);await login.close();
    await ownerPage.getByRole('button',{name:'Войти снова',exact:true}).click();
    await ownerPage.waitForFunction(()=>document.querySelector('[data-editor-status]')?.textContent.includes('Вход выполнен.'));
    await action(ownerPage,'retry-intent').click();await ownerPage.waitForFunction(()=>document.querySelector('[data-editor-dirty]')?.textContent==='Сохранение подтверждено.',{},{timeout:20000});
    await ownerPage.unroute(saveUrl);ensure(requests===2,'REAUTH_MANUAL_RETRY_COUNT');ensure((await observe()).domainHash===committed.domainHash,'REPLAY_CREATED_SECOND_REVISION');
    return {lostResponseCommitted:true,sameUserReauthExactReplay:true,resultId:committedResult};});

  await check('EH006',async()=>{const ctx=await context(),page=await loginPage(ctx,seed.accounts.employee);await page.goto(safe(editPath));await ready(page);
    await rawInput(page,'<p>EMPLOYEE UI</p>');await checked(page);await saved(page);const observed=await observe(),savedPage=pageState(observed,pageId);
    ensure(savedPage.payload.main_text==='<p>EMPLOYEE UI</p>','EMPLOYEE_UI_SAVE');
    ensure(savedPage.history.at(-1).authorId===seed.userIds[1],'EMPLOYEE_AUTHOR');
    ensure((await ctx.request.get(safe('/manage/pages/'+seed.pageIds[1]+'/edit/'),{maxRedirects:0})).status()===403,'FOREIGN_PAGE_VISIBLE');
    return {employeeActualUiSave:true,...await invariants(page)};});
  await check('EH007',async()=>{const visitor=await context();ensure((await visitor.request.get(safe(editPath),{maxRedirects:0})).status()===401,'VISITOR_EDITOR_VISIBLE');
    await ownerPage.reload();await ready(ownerPage);await invariants(ownerPage);await ownerPage.screenshot({path:'/output/editor-desktop.png',fullPage:true,caret:'initial'});
    await invariants(ownerPage);await ownerPage.setViewportSize({width:390,height:844});await invariants(ownerPage);await ownerPage.screenshot({path:'/output/editor-mobile.png',fullPage:true,caret:'initial'});
    ensure(await ownerPage.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'MOBILE_OVERFLOW');return {...await invariants(ownerPage),screenshots:true};});
  await check('EH008',async()=>{await ownerPage.reload();await ready(ownerPage);
    await rawInput(ownerPage,'<p>POST CHECK OLD</p>');await checked(ownerPage);
    const editable=field(ownerPage).locator('.es-editor-surface');await editable.click();await editable.press('ControlOrMeta+A');await editable.pressSequentially('TRANSACTION NEW');
    await ownerPage.waitForFunction(()=>document.querySelector('[data-editor-dirty]')?.textContent.includes('Есть несохранённые'));
    await checked(ownerPage);let submitted;
    await ownerPage.route(saveUrl,async route=>{submitted=JSON.parse(route.request().postData());await route.continue();},{times:1});
    await saved(ownerPage);ensure(submitted?.changes.main_text.includes('TRANSACTION NEW')&&!submitted.changes.main_text.includes('POST CHECK OLD'),'STALE_CHECK_TRANSACTION_SAVED');
    await checked(ownerPage);await editable.click();await editable.press('ControlOrMeta+A');
    await ownerPage.evaluate(()=>{const actual=CSSStyleSheet.prototype.insertRule;globalThis.__editorRestoreInsertRule=()=>{CSSStyleSheet.prototype.insertRule=actual;};
      CSSStyleSheet.prototype.insertRule=function(rule,...args){if(String(rule).includes('.esf-'))throw new Error('QA_CSSOM_FAILURE');return actual.call(this,rule,...args);};});
    try{await field(ownerPage).getByLabel('Размер текста, px',{exact:true}).fill('18');await field(ownerPage).getByLabel('Размер текста, px',{exact:true}).press('Tab');
      await ownerPage.waitForFunction(()=>document.querySelector('[data-editor-status]')?.textContent.includes('Не удалось'));
    }finally{await ownerPage.evaluate(()=>globalThis.__editorRestoreInsertRule());}
    let saves=0;const listener=request=>{if(request.url()===saveUrl&&request.method()==='POST')saves++;};ownerPage.on('request',listener);
    await action(ownerPage,'save').click();await ownerPage.waitForTimeout(150);ensure(saves===0,'CSS_FAILURE_REUSED_PROOF');ownerPage.off('request',listener);
    await checked(ownerPage);await saved(ownerPage);const observed=await observe();ensure(pageState(observed,pageId).payload.main_text.includes('data-es-size="18"'),'CSS_FAILURE_LOST_MODEL');
    return {postCheckTransaction:true,cssFaultBlocksOldProof:true,recoveryExplicitCheck:true};});

  await check('EH009',async()=>{const source='<p><span data-es-anchor="empty"></span>EMPTY ANCHOR TEXT</p>';
    await rawInput(ownerPage,source);await checked(ownerPage);
    ensure(await field(ownerPage).locator('.es-html-source').isVisible(),'EMPTY_ANCHOR_NOT_HTML_ONLY');
    ensure(await field(ownerPage).locator('.es-html-source').inputValue()===source,'EMPTY_ANCHOR_SOURCE_CHANGED');
    await saved(ownerPage);ensure(pageState(await observe(),pageId).payload.main_text===source,'EMPTY_ANCHOR_SAVE_LOST_DATA');
    return {serverCheckedHtmlOnlySaved:true};});

  await check('EH010',async()=>{await rawInput(ownerPage,'<p>OWNER_UNSAVED_PRIVATE_CANARY</p>');await checked(ownerPage);
    const before=await observe();let posts=0;const listener=request=>{if(request.url()===saveUrl&&request.method()==='POST')posts++;};ownerPage.on('request',listener);
    const token=await ownerPage.locator('form[action="/manage/logout/"] [name=csrfmiddlewaretoken]').inputValue();
    ensure((await ownerContext.request.post(safe('/manage/logout/'),{maxRedirects:0,form:{csrfmiddlewaretoken:token}})).status()===303,'SWITCH_LOGOUT_FAILED');
    const login=await loginPage(ownerContext,seed.accounts.employee);await login.close();
    await ownerPage.getByRole('button',{name:'Войти снова',exact:true}).click();
    await ownerPage.waitForFunction(()=>document.querySelector('[data-editor-status]')?.textContent.includes('Пользователь изменился.'));
    ensure(await ownerPage.locator('[data-editor-page] .es-editor-surface').count()===0,'OLD_EDITOR_DOM_RETAINED');
    const state=await ownerPage.evaluate(()=>({enabled:document.querySelectorAll('[data-editor-page] button:not(:disabled),[data-editor-page] input:not(:disabled),[data-editor-page] textarea:not(:disabled),[data-editor-page] select:not(:disabled)').length,
      oldInput:[...document.querySelectorAll('[data-editor-page] textarea')].some(element=>element.value.includes('OWNER_UNSAVED_PRIVATE_CANARY')),
      initialScript:document.querySelector('#editor-initial-state')?.textContent||'',
      ownerCanaryRetained:document.documentElement.textContent.includes('OWNER_UNSAVED_PRIVATE_CANARY')||document.documentElement.textContent.includes('Protected fixture title')}));
    ensure(state.enabled===0&&!state.oldInput&&state.initialScript===''&&!state.ownerCanaryRetained,'OLD_IDENTITY_INPUT_RETAINED');await ownerPage.waitForTimeout(150);ensure(posts===0,'SWITCH_POSTED_OWNER_INPUT');
    ensure((await observe()).domainHash===before.domainHash,'SWITCH_CHANGED_CONTENT');ownerPage.off('request',listener);
    return {actualDifferentUserReauth:true,oldEditableDomCleared:true,controlsLocked:true,noOldPayloadPost:true};});

  await check('EH011',async()=>{const employeeContext=await context(),page=await loginPage(employeeContext,seed.accounts.employee);
    await page.goto(safe(editPath));await page.locator('.es-page-actions').waitFor();
    const retained='<p>SAME ACTOR NEW GENERATION RAM</p>';await rawInput(page,retained);
    const adminContext=await context(),admin=await loginPage(adminContext,seed.accounts.owner);
    const token=await admin.locator('form[action="/manage/logout/"] [name=csrfmiddlewaretoken]').inputValue();
    const reset=await adminContext.request.post(safe('/manage/employees/'+seed.userIds[1]+'/password/'),{
      maxRedirects:0,form:{password:seed.accounts.employee.password,csrfmiddlewaretoken:token}});
    ensure(reset.status()===303,'GENERATION_PASSWORD_RESET_FAILED');
    const login=await loginPage(employeeContext,seed.accounts.employee);await login.close();
    const stateResponse=await employeeContext.request.get(safe(editPath+'state/'),{maxRedirects:0});
    ensure(stateResponse.status()===200&&(await stateResponse.json()).generation===2,'GENERATION_NOT_ADVANCED');
    let checkPosts=0;const listener=request=>{if(request.url()===safe(editPath+'check/')&&request.method()==='POST')checkPosts++;};page.on('request',listener);
    await action(page,'check').click();await page.waitForFunction(()=>!document.querySelector('.es-page-actions [data-editor-action=check]').disabled);
    ensure(checkPosts===0,'STALE_GENERATION_POSTED_CHECK');
    ensure(await field(page).locator('.es-html-source').inputValue()===retained,'GENERATION_CHANGE_WIPED_RAM');
    ensure(await page.getByRole('button',{name:'Войти снова',exact:true}).isEnabled(),'GENERATION_TERMINALLY_LOCKED');
    await page.getByRole('button',{name:'Войти снова',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('[data-editor-status]')?.textContent.includes('Вход выполнен.'));
    await checked(page);await saved(page);page.off('request',listener);
    ensure(checkPosts===1,'GENERATION_RECHECK_NOT_EXPLICIT');
    ensure(pageState(await observe(),pageId).payload.main_text===retained,'GENERATION_RECOVERY_SAVE_LOST_RAM');
    return {sameActorGeneration2:true,ramRetained:true,explicitReauthCheckSave:true};});

  await check('EH012',async()=>{const ctx=await context(),page=await loginPage(ctx,seed.accounts.owner);
    await page.goto(safe(editPath));await page.locator('.es-page-actions').waitFor();
    await rawInput(page,'<p>OWNER_DIRECT_SAVE_PRIVATE_CANARY</p>');await checked(page);
    const before=await observe();let savePosts=0;const listener=request=>{if(request.url()===saveUrl&&request.method()==='POST')savePosts++;};page.on('request',listener);
    const token=await page.locator('form[action="/manage/logout/"] [name=csrfmiddlewaretoken]').inputValue();
    ensure((await ctx.request.post(safe('/manage/logout/'),{maxRedirects:0,form:{csrfmiddlewaretoken:token}})).status()===303,'DIRECT_SAVE_SWITCH_LOGOUT_FAILED');
    const login=await loginPage(ctx,seed.accounts.employee);await login.close();
    await action(page,'save').click();
    await page.waitForFunction(()=>document.querySelector('[data-editor-status]')?.textContent.includes('Пользователь изменился.'));
    const terminal=await page.evaluate(()=>({liveEditors:document.querySelectorAll('[data-editor-page] .es-editor-surface').length,
      enabled:document.querySelectorAll('[data-editor-page] button:not(:disabled),[data-editor-page] input:not(:disabled),[data-editor-page] textarea:not(:disabled),[data-editor-page] select:not(:disabled)').length,
      sourceRetained:[...document.querySelectorAll('[data-editor-page] textarea')].some(element=>element.value.includes('OWNER_DIRECT_SAVE_PRIVATE_CANARY')),
      script:document.querySelector('#editor-initial-state')?.textContent||'',
      canary:document.documentElement.textContent.includes('OWNER_DIRECT_SAVE_PRIVATE_CANARY')||document.documentElement.textContent.includes('Protected fixture title')}));
    ensure(terminal.liveEditors===0&&terminal.enabled===0&&!terminal.sourceRetained&&terminal.script===''&&!terminal.canary,'DIRECT_SAVE_IDENTITY_NOT_TERMINAL');
    ensure(!await action(page,'retry-intent').isVisible(),'DIRECT_SAVE_IDENTITY_BECAME_UNKNOWN');
    ensure(savePosts===0,'DIRECT_SAVE_POSTED_PREVIOUS_ACTOR');ensure((await observe()).domainHash===before.domainHash,'DIRECT_SAVE_SWITCH_MUTATED_DOMAIN');
    page.off('request',listener);return {differentUserDirectSaveTerminal:true,noOldPayloadPost:true};});

  output({kind:'result',status:'PASS',groups:results});
}catch(error){output({kind:'result',status:'FAIL',caseId:current,errorClass:error?.constructor?.name||'Error',errorCode:typeof error?.message==='string'&&/^[A-Z0-9_]{1,120}$/.test(error.message)?error.message:'EDITOR_BROWSER_PROBE_FAILED',diagnostics:await failureDiagnostics(),groups:results});process.exitCode=1;}
finally{for(const ctx of contexts)await ctx.close().catch(()=>{});await browser?.close().catch(()=>{});channel.close();}
