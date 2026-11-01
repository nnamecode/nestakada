// D07 product browser checks. Real fixture/HTTP/PG observer; no reset endpoint.
import fs from 'node:fs';
import readline from 'node:readline';
import {chromium} from '/tests/node_modules/playwright/index.mjs';

const origin='http://host.docker.internal:8767';
const output=value=>process.stdout.write(JSON.stringify(value)+'\n');
const ensure=(value,code)=>{if(!value)throw new Error(code);};
const safe=value=>{const url=new URL(value,origin);ensure(typeof value==='string'&&value.startsWith('/')&&url.origin===origin,'FIXED_ORIGIN');return url.href;};
const fixed=value=>typeof value==='string'&&/^[A-Z0-9_]{1,120}$/.test(value)?value:'DRAFT_BROWSER_PROBE_FAILED';
const channel=readline.createInterface({input:process.stdin,terminal:false}),waiters=new Map(),results=[],contexts=[],releases=[];
let serial=0,current='START',browser,diagnosticPage;
class DiagnosticStop extends Error {}
channel.on('line',line=>{try{const value=JSON.parse(line),waiter=waiters.get(value.id);if(value.kind==='observation'&&waiter){waiters.delete(value.id);value.error?waiter.reject(new Error('HOST_OBSERVER_FAILED')):waiter.resolve(value.value);}}catch{process.exitCode=1;}});
function observe(){return new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{waiters.delete(id);reject(new Error('OBSERVER_TIMEOUT'));},30000);
  waiters.set(id,{resolve:value=>{clearTimeout(timer);resolve(value);},reject:error=>{clearTimeout(timer);reject(error);}});output({kind:'observe',id,caseId:current});});}
const pageRow=(state,id)=>{const row=state.pages.find(row=>row.id===id);ensure(row,'PAGE_OBSERVER_MISSING');return row;};
const draftRow=(state,id)=>state.drafts.find(row=>row.pageId===id);
const action=(page,name)=>page.locator('.es-page-actions [data-editor-action="'+name+'"]');
const field=page=>page.locator('[data-editor-field="main_text"]');
async function ctx(){const value=await browser.newContext({viewport:{width:1280,height:900},timezoneId:'UTC'});contexts.push(value);
  await value.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  await value.addInitScript(()=>{globalThis.__draftCsp=[];document.addEventListener('securitypolicyviolation',event=>globalThis.__draftCsp.push(event.effectiveDirective));});return value;}
async function login(context,account){const page=await context.newPage();await page.goto(safe('/manage/login/'));
  await page.locator('[name=username]').fill(account.username);await page.locator('[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(safe('/manage/'),{timeout:15000}),page.locator('form[action="/manage/login/"] button').click()]);return page;}
async function ready(page){diagnosticPage=page;await page.locator('.es-page-actions').waitFor();await field(page).locator('.es-toolbar').waitFor();}
async function source(page,html){await field(page).locator('.es-toolbar').getByRole('button',{name:'HTML',exact:true}).click();await field(page).locator('.es-html-source').fill(html);}
async function idle(page){await page.waitForFunction(()=>!document.querySelector('.es-page-actions [data-editor-action=check]').disabled,{},{timeout:20000});}
async function checked(page){await action(page,'check').click();await idle(page);
  const accept=page.locator('.es-review').getByRole('button',{name:'Принять проверенный вариант',exact:true});if(await accept.isVisible())await accept.click();
  ensure((await page.locator('[data-editor-dirty]').textContent()).includes('Проверено.'),'CHECK_NOT_ACCEPTED');}
async function write(page,name){await action(page,name).click();await page.waitForFunction(name=>document.querySelector('[data-editor-dirty]')?.textContent===(name==='draft'?'Черновик сохранён отдельно от сайта.':'Сохранение подтверждено.'),name,{timeout:20000});}
async function invariant(page){const facts=await page.evaluate(()=>({csp:globalThis.__draftCsp||[],inline:document.querySelectorAll('[data-editor-page] [style],[data-editor-page] style,[data-editor-page] colgroup').length,
  local:localStorage.length,session:sessionStorage.length}));ensure(facts.csp.length===0,'CSP_VIOLATION');ensure(facts.inline===0,'INLINE_STYLE_OR_COLGROUP');ensure(facts.local===0&&facts.session===0,'BROWSER_STORAGE_USED');}
async function check(id,d07,body){current=id;const facts=await body();if(diagnosticPage&&!diagnosticPage.isClosed()&&new URL(diagnosticPage.url()).pathname.includes('/edit/'))await invariant(diagnosticPage);results.push({id,d07,status:'PASS',...facts});
  if(process.env.D07_STOP_AFTER_CASE==='DUI-004'&&id==='DUI-004')throw new DiagnosticStop();}
async function navigate(page,locator){let decision,dialogFailed=false;
  const handler=dialog=>{decision=new Promise(resolve=>{const timer=setTimeout(()=>{dialogFailed=true;resolve();},5000);
    dialog.accept().then(()=>{clearTimeout(timer);resolve();},()=>{clearTimeout(timer);dialogFailed=true;resolve();});});};page.once('dialog',handler);
  try{await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded',timeout:20000}),locator.click()]);}
  finally{page.off('dialog',handler);if(decision)await decision;}
  ensure(!dialogFailed,'SOURCE_NAVIGATION_DIALOG_FAILED');await ready(page);}

try{
  const seed=JSON.parse(fs.readFileSync('/private/editor-seed.json','utf8'));ensure(seed.pageIds?.length===2&&seed.accounts?.owner&&seed.accounts?.employee,'SEED_CONTRACT');
  const pageId=seed.pageIds[0],prefix='/manage/pages/'+pageId+'/edit/',draftPath=prefix+'draft/',savePath=prefix+'save/';
  browser=await chromium.launch({headless:true});const ownerContext=await ctx(),owner=await login(ownerContext,seed.accounts.owner);
  await owner.goto(safe(prefix));await ready(owner);let publishedRequest;

  await check('DUI-001',['D07-001'],async()=>{const before=await observe();await source(owner,'<p><b>DRAFT PRIVATE ONE</b></p>');await checked(owner);await write(owner,'draft');
    const after=await observe(),draft=draftRow(after,pageId);ensure(draft&&draft.revision===1,'NEW_DRAFT_MISSING');
    ensure(draft.payload.main_text==='<p><strong>DRAFT PRIVATE ONE</strong></p>','DRAFT_CANONICAL_PAYLOAD');
    ensure(pageRow(after,pageId).currentId===pageRow(before,pageId).currentId&&pageRow(after,pageId).history.length===pageRow(before,pageId).history.length,'DRAFT_PUBLISHED');
    ensure(after.pins.some(pin=>pin.holderKind==='owner_draft'&&pin.holderId===draft.id&&pin.revisionId===draft.baseRevisionId),'DRAFT_PIN_MISSING');return {draftId:draft.id,noHiddenPublish:true};});

  await check('DUI-002',['D07-002','D07-007'],async()=>{const before=await observe(),old=draftRow(before,pageId);
    await source(owner,'<p>DRAFT UPDATE TWO</p>');await checked(owner);await write(owner,'draft');const updated=await observe();
    ensure(draftRow(updated,pageId).id===old.id&&draftRow(updated,pageId).revision===old.revision+1,'DRAFT_UPDATE_IDENTITY');
    ensure(pageRow(updated,pageId).currentId===pageRow(before,pageId).currentId,'DRAFT_UPDATE_PUBLISHED');
    await source(owner,'<p>EDITED BEFORE APPLY</p>');await checked(owner);
    const listener=request=>{if(new URL(request.url()).pathname===savePath&&request.method()==='POST')publishedRequest={body:request.postData(),url:request.url()};};owner.on('request',listener);
    await write(owner,'save');owner.off('request',listener);const applied=await observe();
    ensure(!draftRow(applied,pageId),'DRAFT_NOT_CONSUMED');ensure(!applied.pins.some(pin=>pin.holderId===old.id),'DRAFT_PIN_RETAINED');
    ensure(pageRow(applied,pageId).payload.main_text==='<p>EDITED BEFORE APPLY</p>','EDITED_DRAFT_NOT_APPLIED');
    ensure(pageRow(applied,pageId).history.length===pageRow(updated,pageId).history.length+1,'DRAFT_APPLY_AUTOMATIC_COUNT');return {editedApply:true};});

  await check('DUI-003',['D07-008'],async()=>{ensure(publishedRequest,'PUBLISH_REQUEST_MISSING');const before=await observe();
    const token=await owner.locator('[data-editor-page] [name=csrfmiddlewaretoken]').inputValue();
    const response=await ownerContext.request.post(publishedRequest.url,{maxRedirects:0,headers:{'Content-Type':'application/json','X-CSRFToken':token},data:publishedRequest.body});
    ensure(response.status()===200,'CONSUMED_DRAFT_REPLAY_STATUS');const result=await response.json();ensure(result.replay===true&&result.result_id===pageRow(before,pageId).currentId,'CONSUMED_DRAFT_REPLAY_RESULT');
    const after=await observe();ensure(after.domainHash===before.domainHash&&after.versionAuditCount===before.versionAuditCount,'CONSUMED_DRAFT_RECOMMITTED');return {metadataReplay:true};});

  await check('DUI-004',['D07-004','D07-006'],async()=>{await owner.goto(safe(prefix));await ready(owner);await source(owner,'<p>REBASE DRAFT TEXT</p>');await checked(owner);await write(owner,'draft');
    const employeeContext=await ctx(),employee=await login(employeeContext,seed.accounts.employee);await employee.goto(safe(prefix));await ready(employee);
    await source(employee,'<p>EMPLOYEE CURRENT TEXT</p>');await checked(employee);await write(employee,'save');await invariant(employee);
    const stale=await observe(),draft=draftRow(stale,pageId);ensure(draft.baseRevisionId!==pageRow(stale,pageId).currentId,'DRAFT_NOT_STALE');
    await owner.reload();await ready(owner);await navigate(owner,owner.locator('[data-editor-rebase-link]'));
    ensure((await owner.locator('pre[data-editor-compare-draft=main_text]').textContent()).includes('REBASE DRAFT TEXT'),'COMPARE_DRAFT_NOT_ACTUAL');
    ensure((await owner.locator('pre[data-editor-compare-current=main_text]').textContent()).includes('EMPLOYEE CURRENT TEXT'),'COMPARE_CURRENT_NOT_ACTUAL');
    let checkPosts=0;const listener=request=>{if(new URL(request.url()).pathname===prefix+'check/'&&request.method()==='POST')checkPosts++;};owner.on('request',listener);
    await action(owner,'check').click();await idle(owner);owner.off('request',listener);ensure(checkPosts===0,'REBASE_WITHOUT_CONFIRM_CHECKED');
    await owner.locator('[data-editor-rebase-confirm]').check();await checked(owner);await write(owner,'draft');const rebased=await observe();
    ensure(draftRow(rebased,pageId).baseRevisionId===pageRow(stale,pageId).currentId,'REBASE_TARGET_WRONG');ensure(draftRow(rebased,pageId).payload.main_text==='<p>REBASE DRAFT TEXT</p>','REBASE_MERGED_TEXT');
    ensure(pageRow(rebased,pageId).currentId===pageRow(stale,pageId).currentId,'REBASE_PUBLISHED');diagnosticPage=owner;return {employeeCurrentPreserved:true,actualCompareExplicitRebase:true};});

  await check('DUI-005',['D07-009','D07-024'],async()=>{const before=await observe();const raw='<p>UNSAVED AFTER REBASE</p>';await source(owner,raw);
    owner.once('dialog',dialog=>dialog.accept());await action(owner,'cancel-draft').click();await idle(owner);
    ensure(!draftRow(await observe(),pageId),'DRAFT_CANCEL_FAILED');ensure(await field(owner).locator('.es-html-source').inputValue()===raw,'CANCEL_LOST_RAM');
    let saves=0;const listener=request=>{if(new URL(request.url()).pathname===savePath&&request.method()==='POST')saves++;};owner.on('request',listener);await action(owner,'save').click();await idle(owner);owner.off('request',listener);
    ensure(saves===0,'CANCELLED_DRAFT_IMPLICIT_SAVE');ensure(pageRow(await observe(),pageId).currentId===pageRow(before,pageId).currentId,'CANCEL_PUBLISHED');return {explicitCancelRamRetained:true};});

  await check('DUI-006',['D07-010','D07-011','D07-014'],async()=>{await owner.goto(safe(prefix));await ready(owner);
    const dirtyBefore=await observe(),dirtyUrl=owner.url(),dirtyCanary='<p>UNSAVED BEFORE HISTORY REPLACEMENT</p>';
    await source(owner,dirtyCanary);let declined=false;
    owner.once('dialog',async dialog=>{declined=true;await dialog.dismiss();});
    await owner.getByRole('link',{name:'История и Stable',exact:true}).click();
    ensure(declined&&owner.url()===dirtyUrl,'DIRTY_HISTORY_NAVIGATION_NOT_DECLINED');
    ensure(await field(owner).locator('.es-html-source').inputValue()===dirtyCanary,'DIRTY_HISTORY_DECLINE_LOST_RAM');
    ensure((await observe()).domainHash===dirtyBefore.domainHash,'DIRTY_HISTORY_DECLINE_MUTATED_DOMAIN');
    let accepted=false;owner.once('dialog',async dialog=>{accepted=true;await dialog.accept();});
    await Promise.all([owner.waitForNavigation(),owner.getByRole('link',{name:'История и Stable',exact:true}).click()]);
    ensure(accepted,'DIRTY_HISTORY_NAVIGATION_NOT_CONFIRMED');
    const row=owner.locator('[data-version-id="'+seed.currentIds[0]+'"]');ensure(await row.count()===1,'HISTORY_SOURCE_NOT_FOUND');
    await Promise.all([owner.waitForNavigation(),row.getByRole('link',{name:'Просмотреть',exact:true}).click()]);const before=await observe();
    await Promise.all([owner.waitForNavigation(),owner.locator('form[data-restore-prepare] button').click()]);
    ensure((await observe()).domainHash===before.domainHash,'PREPARE_MUTATED_DOMAIN');
    const form=owner.locator('form[data-restore-stage]');
    ensure(!await form.locator('[name=confirm_input_replacement]').isChecked(),'REPLACEMENT_PRECONFIRMED');
    const unchecked=await form.evaluate(element=>Object.fromEntries(new FormData(element)));
    ensure(!Object.hasOwn(unchecked,'confirm_input_replacement'),'UNCHECKED_CONFIRMATION_WAS_SERIALIZED');
    const refused=await ownerContext.request.post(safe(await form.getAttribute('action')),{form:unchecked,maxRedirects:0,headers:{Referer:owner.url()}});
    ensure(refused.status()===409,'UNCHECKED_REPLACEMENT_SERVER_NOT_REFUSED');
    ensure((await observe()).domainHash===before.domainHash,'UNCHECKED_REPLACEMENT_CREATED_STAGE_OR_MUTATION');
    await form.locator('[name=confirm_input_replacement]').check();
    await Promise.all([owner.waitForNavigation(),owner.locator('form[data-restore-stage] button').click()]);const staged=await observe();
    const stage=staged.stages.find(stage=>stage.pageId===pageId&&stage.status==='held');ensure(stage,'ACTUAL_STAGE_NOT_CREATED');ensure(pageRow(staged,pageId).currentId===pageRow(before,pageId).currentId,'STAGE_PUBLISHED');
    await Promise.all([owner.waitForNavigation(),owner.locator('a[data-restore-editor]').click()]);await ready(owner);ensure(await action(owner,'draft').count()===0,'STAGE_DRAFT_CALLBACK_PRESENT');
    await source(owner,'<p>EDITED STAGE UI</p>');await checked(owner);ensure(pageRow(await observe(),pageId).currentId===pageRow(before,pageId).currentId,'CHECK_STAGE_PUBLISHED');
    await write(owner,'save');const after=await observe();ensure(pageRow(after,pageId).payload.main_text==='<p>EDITED STAGE UI</p>','EDITED_STAGE_SAVE_WRONG');
    ensure(after.stages.find(value=>value.id===stage.id)?.status==='consumed','STAGE_NOT_CONSUMED');ensure(!after.pins.some(pin=>pin.holderId===stage.id),'STAGE_PIN_RETAINED');
    ensure(pageRow(after,pageId).history.at(-1).sourceId===seed.currentIds[0],'STAGE_SOURCE_PROVENANCE');diagnosticPage=owner;return {dirtyNavigationDeclineRetainedRam:true,uncheckedServerRefusal:true,actualHistoryPrepareStage:true,editedSeparateSave:true};});

  await check('DUI-007',['D07-003','D07-029'],async()=>{await owner.goto(safe(prefix));await ready(owner);await source(owner,'<p>OWNER PRIVATE DRAFT CANARY</p>');await checked(owner);await write(owner,'draft');
    const before=await observe(),draft=draftRow(before,pageId),employeeContext=await ctx(),employee=await login(employeeContext,seed.accounts.employee);
    await employee.goto(safe(prefix));await ready(employee);ensure(await employee.locator('[data-editor-draft-link],[data-editor-rebase-link]').count()===0,'EMPLOYEE_DRAFT_NAV_VISIBLE');
    ensure(!(await employee.content()).includes('OWNER PRIVATE DRAFT CANARY'),'EMPLOYEE_DRAFT_DATA_VISIBLE');
    const selected=prefix+'?'+new URLSearchParams({source:'owner-draft',draftId:draft.id,draftRevision:String(draft.revision)});
    const denied=await employeeContext.request.get(safe(selected),{maxRedirects:0});ensure(denied.status()===403,'EMPLOYEE_DRAFT_SOURCE_ALLOWED');ensure(!(await denied.text()).includes('OWNER PRIVATE DRAFT CANARY'),'EMPLOYEE_DENIAL_LEAKED_DRAFT');
    ensure((await employeeContext.request.get(safe('/manage/pages/'+seed.pageIds[1]+'/edit/'),{maxRedirects:0})).status()===403,'FOREIGN_PAGE_ALLOWED');
    const visitor=await ctx();ensure((await visitor.request.get(safe(selected),{maxRedirects:0})).status()===401,'VISITOR_DRAFT_ALLOWED');
    ensure((await observe()).domainHash===before.domainHash,'PRIVACY_CHECK_MUTATED_DOMAIN');await invariant(employee);diagnosticPage=owner;return {employeeDraftPrivacy:true};});

  await check('DUI-008',['D07-008','D07-021'],async()=>{await source(owner,'<p>LOST DRAFT RESPONSE</p>');await checked(owner);
    let firstBody,firstUrl,requests=0;const match=url=>new URL(url).origin===origin&&new URL(url).pathname===draftPath;
    await owner.route(match,async route=>{requests++;const body=route.request().postData();
      if(!firstBody){firstBody=body;firstUrl=route.request().url();const response=await route.fetch({maxRedirects:0,timeout:30000});ensure(response.status()===200,'LOST_DRAFT_COMMIT_FAILED');await route.abort();}
      else{ensure(body===firstBody&&route.request().url()===firstUrl,'DRAFT_UNKNOWN_RETRY_CHANGED');await route.continue();}});
    await action(owner,'draft').click();await action(owner,'retry-intent').waitFor({state:'visible'});await owner.waitForTimeout(150);ensure(requests===1,'DRAFT_HIDDEN_RETRY');
    const committed=await observe(),draft=draftRow(committed,pageId);ensure(draft.payload.main_text==='<p>LOST DRAFT RESPONSE</p>','LOST_DRAFT_COMMIT_NOT_OBSERVED');
    const other=await ownerContext.newPage();await other.goto(safe(prefix+'?'+new URLSearchParams({source:'owner-draft',draftId:draft.id,draftRevision:String(draft.revision)})));await ready(other);await checked(other);await write(other,'save');await invariant(other);
    const consumed=await observe();ensure(!draftRow(consumed,pageId),'SECOND_TAB_DRAFT_NOT_CONSUMED');
    diagnosticPage=owner;await action(owner,'retry-intent').click();await idle(owner);await action(owner,'retry-intent').waitFor({state:'hidden'});await owner.unroute(match);
    ensure(requests===2,'DRAFT_EXACT_MANUAL_RETRY_COUNT');const replayed=await observe();ensure(replayed.domainHash===consumed.domainHash&&replayed.versionAuditCount===consumed.versionAuditCount,'GONE_DRAFT_REPLAY_MUTATED_DOMAIN');return {lostDraftCommitted:true,consumedResultExactReplay:true};});

  await check('DUI-009',['D07-002','D07-021','D07-024'],async()=>{await owner.goto(safe(prefix));await ready(owner);await source(owner,'<p>COMMITTED WHILE TYPING</p>');await checked(owner);
    let announce,release;const arrived=new Promise(resolve=>{announce=resolve;}),held=new Promise(resolve=>{release=resolve;});releases.push(release);
    const match=url=>new URL(url).origin===origin&&new URL(url).pathname===draftPath;
    await owner.route(match,async route=>{const response=await route.fetch({maxRedirects:0,timeout:30000});ensure(response.status()===200,'DELAYED_DRAFT_COMMIT_FAILED');announce();await held;await route.fulfill({response});},{times:1});
    await action(owner,'draft').click();await Promise.race([arrived,new Promise((_,reject)=>setTimeout(()=>reject(new Error('DELAYED_DRAFT_TIMEOUT')),30000))]);
    await source(owner,'<p>NEWER UNSAVED INPUT</p>');release();await idle(owner);
    ensure(await field(owner).locator('.es-html-source').inputValue()==='<p>NEWER UNSAVED INPUT</p>','DELAYED_RESPONSE_OVERWROTE_RAM');
    const first=await observe();ensure(draftRow(first,pageId).payload.main_text==='<p>COMMITTED WHILE TYPING</p>','DELAYED_RESPONSE_AUTOSAVED_NEW_INPUT');
    await checked(owner);await write(owner,'draft');const after=await observe();ensure(draftRow(after,pageId).revision===draftRow(first,pageId).revision+1,'DELAYED_NEW_INTENT_WRONG_REVISION');
    ensure(draftRow(after,pageId).payload.main_text==='<p>NEWER UNSAVED INPUT</p>','DELAYED_NEW_INPUT_NOT_EXPLICITLY_SAVED');
    await invariant(owner);await owner.screenshot({path:'/output/editor-draft-desktop.png',fullPage:true,caret:'initial'});await invariant(owner);
    await owner.setViewportSize({width:390,height:844});await invariant(owner);await owner.screenshot({path:'/output/editor-draft-mobile.png',fullPage:true,caret:'initial'});await invariant(owner);
    ensure(await owner.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'MOBILE_OVERFLOW');return {inflightRamRetained:true,newExplicitIntent:true,screenshots:true};});

  output({kind:'result',status:'PASS',groups:results});
}catch(error){if(error instanceof DiagnosticStop){output({kind:'result',status:'PASS',scope:'DIAGNOSTIC_ONLY',groups:results});}else{let screenshot=false;
  try{if(diagnosticPage&&!diagnosticPage.isClosed()&&new URL(diagnosticPage.url()).origin===origin&&await diagnosticPage.locator('[data-editor-page]').count()===1&&await diagnosticPage.locator('input[type=password]:visible').count()===0){await diagnosticPage.screenshot({path:'/output/editor-draft-failure.png',fullPage:true,caret:'initial',timeout:5000});screenshot=true;}}catch{}
  output({kind:'result',status:'FAIL',caseId:current,errorCode:fixed(error?.message),errorClass:error?.constructor?.name||'Error',screenshot,groups:results});process.exitCode=1;}
}finally{for(const release of releases)release();for(const value of contexts)await value.close().catch(()=>{});await browser?.close().catch(()=>{});channel.close();}
