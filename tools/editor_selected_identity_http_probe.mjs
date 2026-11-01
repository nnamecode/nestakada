// SID001–004: actual selected sources and browser-session identity changes.
// Credentials, CSRF, proof and private input remain in this process RAM only.
import fs from 'node:fs';
import readline from 'node:readline';
import {chromium} from '/tests/node_modules/playwright/index.mjs';
const origin='http://host.docker.internal:8767',groups=[],contexts=[],pending=new Map(),pageErrors=[],unexpected=[];
const ensure=(value,code)=>{if(!value)throw new Error(code);};
const emit=value=>process.stdout.write(JSON.stringify(value)+'\n');
const fixed=value=>typeof value==='string'&&/^[A-Z0-9_]{1,100}$/.test(value)?value:'SID_BROWSER_FAILED';
const safe=value=>{ensure(typeof value==='string'&&value.startsWith('/')&&new URL(value,origin).origin===origin,'SID_FIXED_ORIGIN');return origin+value;};
let serial=0,current='START',browser,seed;
const channel=readline.createInterface({input:process.stdin,terminal:false});
channel.on('line',line=>{try{const value=JSON.parse(line),resolve=pending.get(value.id);ensure(value.kind==='observation'&&resolve,'SID_OBSERVER_PROTOCOL');pending.delete(value.id);resolve(value.value);}catch{process.exitCode=1;}});
function observe(){return new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{pending.delete(id);reject(new Error('SID_OBSERVER_TIMEOUT'));},30000);
  pending.set(id,value=>{clearTimeout(timer);resolve(value);});emit({kind:'observe',id,caseId:current,operation:'observe'});});}
const pageRow=state=>{const value=state.pages.find(row=>row.id===seed.pageIds[0]);ensure(value,'SID_OWN_PAGE_MISSING');return value;};
const draftRow=state=>{const value=state.drafts.find(row=>row.pageId===seed.pageIds[0]);ensure(value,'SID_OWN_DRAFT_MISSING');return value;};
const prefix=()=>'/manage/pages/'+seed.pageIds[0]+'/edit/';
const action=(page,name)=>page.locator('.es-page-actions [data-editor-action="'+name+'"]');
const field=page=>page.locator('[data-editor-field=main_text]');
const draftPath=row=>prefix()+'?'+new URLSearchParams({source:'owner-draft',draftId:row.id,draftRevision:String(row.revision)});
async function context(){const ctx=await browser.newContext({viewport:{width:1280,height:900}});contexts.push(ctx);
  await ctx.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():(unexpected.push('EXTERNAL_REQUEST'),route.abort()));
  await ctx.addInitScript(()=>{globalThis.__sidCsp=[];document.addEventListener('securitypolicyviolation',event=>{if(globalThis.__sidCsp.length<8)globalThis.__sidCsp.push(/^[a-z-]{1,40}$/.test(event.effectiveDirective)?event.effectiveDirective:'unknown');});});
  ctx.on('page',page=>page.on('pageerror',()=>pageErrors.push('PAGE_ERROR')));return ctx;}
async function login(ctx,account){const page=await ctx.newPage();await page.goto(safe('/manage/login/'));await page.locator('[name=username]').fill(account.username);await page.locator('[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(safe('/manage/'),{timeout:15000}),page.locator('form[action="/manage/login/"] button').click()]);return page;}
async function logout(ctx,page){const token=await page.locator('form[action="/manage/logout/"] [name=csrfmiddlewaretoken]').inputValue();
  ensure((await ctx.request.post(safe('/manage/logout/'),{maxRedirects:0,form:{csrfmiddlewaretoken:token}})).status()===303,'SID_LOGOUT_FAILED');}
async function switchActor(ctx,page,account){await logout(ctx,page);const next=await login(ctx,account);await next.close();}
async function ready(page,path){await page.goto(safe(path));await page.locator('.es-page-actions').waitFor();await field(page).locator('.es-toolbar').waitFor();}
async function rawInput(page,html){const source=field(page).locator('.es-html-source');if(!await source.isVisible())await field(page).locator('.es-toolbar').getByRole('button',{name:'HTML',exact:true}).click();await source.fill(html);}
async function checked(page){const response=page.waitForResponse(value=>new URL(value.url()).pathname===prefix()+'check/',{timeout:30000});await action(page,'check').click();const actual=await response;ensure(actual.status()===200,'SID_CHECK_REFUSED');
  await page.waitForFunction(()=>!document.querySelector('.es-page-actions [data-editor-action=check]').disabled,null,{timeout:30000});const accept=page.locator('.es-review').getByRole('button',{name:'Принять проверенный вариант',exact:true});if(await accept.isVisible())await accept.click();
  ensure((await page.locator('[data-editor-dirty]').textContent()).includes('Проверено.'),'SID_CHECK_NOT_ACCEPTED');return actual.json();}
async function write(page,name){const response=page.waitForResponse(value=>new URL(value.url()).pathname===prefix()+name+'/',{timeout:30000});await action(page,name).click();const actual=await response;ensure(actual.status()===200,'SID_EXPLICIT_WRITE_REFUSED');
  const text=name==='draft'?'Черновик сохранён отдельно от сайта.':'Сохранение подтверждено.';await page.waitForFunction(value=>document.querySelector('[data-editor-dirty]')?.textContent===value,text,{timeout:30000});return actual.json();}
async function invariant(page){ensure(pageErrors.length===0&&unexpected.length===0,'SID_PAGE_OR_EXTERNAL_ERROR');const facts=await page.evaluate(()=>({csp:globalThis.__sidCsp?.length||0,storage:localStorage.length+sessionStorage.length,inline:document.querySelectorAll('[data-editor-page] [style],[data-editor-page] style,[data-editor-page] colgroup').length}));
  ensure(facts.csp===0&&facts.storage===0&&facts.inline===0,'SID_CSP_STORAGE_INLINE');}
function traffic(page){const posts=[];const listener=request=>{if(request.method()==='POST'&&new URL(request.url()).pathname.startsWith(prefix()))posts.push(request);};page.on('request',listener);return {posts,close:()=>page.off('request',listener)};}
async function retainedHandles(page){const handles=await page.locator('[data-editor-page] textarea,[data-editor-page] pre,#editor-initial-state').elementHandles();
  ensure(handles.length>=2,'SID_RETAINED_HANDLES_MISSING');ensure(await page.locator('#editor-initial-state').count()===1,'SID_INITIAL_SCRIPT_MISSING');return handles;}
async function terminal(page,handles,canary){await page.waitForFunction(()=>document.querySelector('[data-editor-status]')?.textContent.includes('Пользователь изменился.'),null,{timeout:30000});
  const facts=await page.evaluate(marker=>({live:document.querySelectorAll('[data-editor-page] .es-editor-surface').length,enabled:document.querySelectorAll('[data-editor-page] button:not(:disabled),[data-editor-page] input:not(:disabled),[data-editor-page] textarea:not(:disabled),[data-editor-page] select:not(:disabled)').length,
    input:[...document.querySelectorAll('[data-editor-page] textarea,[data-editor-page] input')].some(node=>node.value.includes(marker)),script:document.querySelector('#editor-initial-state')?.textContent||'',canary:document.documentElement.textContent.includes(marker)}),canary);
  ensure(facts.live===0&&facts.enabled===0&&!facts.input&&!facts.canary&&facts.script==='','SID_IDENTITY_NOT_TERMINAL');
  ensure(!await action(page,'retry-intent').isVisible(),'SID_RETRY_RETAINED');
  for(const handle of handles){ensure(await handle.evaluate(node=>('value' in node?node.value:node.textContent)===''),'SID_ADDRESSABLE_HANDLE_RETAINED');await handle.dispose();}
  await invariant(page);}
function unchanged(before,after){ensure(after.domainHash===before.domainHash&&after.versionAuditCount===before.versionAuditCount,'SID_DOMAIN_MUTATED');}
async function createStage(page){await page.goto(safe('/manage/pages/'+seed.pageIds[0]+'/versions/'));const source=page.locator('[data-version-id="'+seed.currentIds[0]+'"]');ensure(await source.count()===1,'SID_SOURCE_MISSING');
  await Promise.all([page.waitForNavigation(),source.getByRole('link',{name:'Просмотреть',exact:true}).click()]);await Promise.all([page.waitForNavigation(),page.locator('form[data-restore-prepare] button').click()]);const form=page.locator('form[data-restore-stage]');
  ensure(!await form.locator('[name=confirm_input_replacement]').isChecked(),'SID_PRECONFIRMED_STAGE');await form.locator('[name=confirm_input_replacement]').check();await Promise.all([page.waitForNavigation(),form.locator('button').click()]);
  const stageId=await page.locator('[data-restore-staged]').getAttribute('data-restore-staged');ensure(/^[a-f0-9-]{36}$/.test(stageId||''),'SID_STAGE_ID');return {stageId,path:prefix()+'?'+new URLSearchParams({source:'restore-stage',stageId})};}
async function group(id,fn){current=id;const result=await fn();groups.push({id,requirements:['D07-022','D07-023','D07-024'],status:'PASS',...result});}

try{
  seed=JSON.parse(fs.readFileSync('/private/selected-identity-seed.json','utf8'));browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
  await group('SID-001',async()=>{const ctx=await context(),page=await login(ctx,seed.accounts.owner);await ready(page,prefix());
    await rawInput(page,'<p>SID SAVED PRIVATE DRAFT</p>');await checked(page);await write(page,'draft');const draft=draftRow(await observe());await ready(page,draftPath(draft));
    const canary='SID OWNER CHECK PRIVATE';await rawInput(page,'<p>'+canary+'</p>');await checked(page);const handles=await retainedHandles(page),before=await observe(),watch=traffic(page);
    await switchActor(ctx,page,seed.accounts.employee);await action(page,'check').click();await terminal(page,handles,canary);ensure(watch.posts.length===0,'SID_SWITCH_CHECK_POSTED');unchanged(before,await observe());watch.close();
    await page.screenshot({path:'/evidence/identity-1280.png',fullPage:true,caret:'initial'});await invariant(page);await page.setViewportSize({width:390,height:844});await page.screenshot({path:'/evidence/identity-390.png',fullPage:true,caret:'initial'});await invariant(page);
    return {selectedDraftCheckSwitch:true,retainedHandlesCleared:true,noEditorPost:true,receiptInclusiveNoMutation:true};});
  await group('SID-002',async()=>{const ctx=await context(),page=await login(ctx,seed.accounts.employee),stage=await createStage(page);await ready(page,stage.path);
    const canary='SID EMPLOYEE STAGE PRIVATE';await rawInput(page,'<p>'+canary+'</p>');await checked(page);const handles=await retainedHandles(page),before=await observe(),watch=traffic(page);
    ensure(before.stages.find(row=>row.id===stage.stageId)?.status==='held','SID_STAGE_NOT_HELD');await switchActor(ctx,page,seed.accounts.owner);await action(page,'save').click();await terminal(page,handles,canary);
    ensure(watch.posts.length===0,'SID_SWITCH_STAGE_POSTED');unchanged(before,await observe());watch.close();return {selectedStageSaveSwitch:true,ownerDoesNotBypassActor:true,heldStagePinsPreserved:true,retainedHandlesCleared:true};});
  await group('SID-003',async()=>{const ctx=await context(),page=await login(ctx,seed.accounts.owner);await ready(page,draftPath(draftRow(await observe())));
    const canary='SID UNKNOWN DRAFT PRIVATE';await rawInput(page,'<p>'+canary+'</p>');await checked(page);const handles=await retainedHandles(page),before=await observe(),oldDraft=draftRow(before);let requests=0,result;
    const target=safe(prefix()+'draft/')+'*';await page.route(target,async route=>{requests++;ensure(requests===1,'SID_UNKNOWN_UNEXPECTED_REPLAY');const response=await route.fetch({maxRedirects:0,timeout:30000});ensure(response.status()===200,'SID_UNKNOWN_COMMIT_REFUSED');result=await response.json();await route.abort();});
    await action(page,'draft').click();await action(page,'retry-intent').waitFor({state:'visible'});const committed=await observe(),updated=draftRow(committed);
    ensure(requests===1&&result?.result_id===oldDraft.id&&updated.id===oldDraft.id&&updated.revision===oldDraft.revision+1&&updated.payload.main_text==='<p>'+canary+'</p>','SID_UNKNOWN_DRAFT_NOT_COMMITTED');
    ensure(JSON.stringify(pageRow(committed))===JSON.stringify(pageRow(before)),'SID_UNKNOWN_DRAFT_PUBLISHED');const fresh=committed.receipts.filter(row=>!before.receipts.some(old=>old.id===row.id));
    ensure(fresh.length===1&&fresh[0].actorId===seed.userIds[0]&&fresh[0].action==='save_draft'&&fresh[0].resultId===oldDraft.id,'SID_UNKNOWN_DURABLE_RECEIPT');
    const watch=traffic(page);await switchActor(ctx,page,seed.accounts.employee);await action(page,'retry-intent').click();await terminal(page,handles,canary);ensure(watch.posts.length===0&&requests===1,'SID_UNKNOWN_SWITCH_REPLAY_POSTED');unchanged(committed,await observe());watch.close();await page.unroute(target);
    return {selectedDraftRealCommitLostResponse:true,currentUnchanged:true,oneDraftUpdateAndReceipt:true,differentActorRetryNoPost:true,unknownIntentCleared:true};});
  await group('SID-004',async()=>{const ctx=await context(),page=await login(ctx,seed.accounts.owner),beforeOpen=await observe(),draft=draftRow(beforeOpen);await ready(page,draftPath(draft));
    const canary='SID SAME OWNER RETAINED RAM';await rawInput(page,'<p>'+canary+'</p>');await checked(page);const initial=JSON.parse(await page.locator('#editor-initial-state').textContent()),originalUrl=page.url();
    const state=await ctx.request.get(safe(prefix()+'state/'),{maxRedirects:0});ensure(state.status()===200,'SID_INITIAL_STATE_REFUSED');const oldState=await state.json(),oldCookies=await ctx.cookies(origin),watch=traffic(page),before=await observe();
    await logout(ctx,page);ensure((await ctx.request.get(safe('/manage/session/'),{maxRedirects:0})).status()===401,'SID_LOGOUT_NOT_ENDED');ensure(await field(page).locator('.es-html-source').inputValue()==='<p>'+canary+'</p>','SID_LOGOUT_LOST_RAM');
    const logged=await login(ctx,seed.accounts.owner);await logged.close();const session=await ctx.request.get(safe('/manage/session/'),{maxRedirects:0});ensure(session.status()===200&&(await session.json()).userId===seed.userIds[0],'SID_SAME_ACTOR_NOT_AUTHENTICATED');
    const response=await ctx.request.get(safe(prefix()+'state/'),{maxRedirects:0});ensure(response.status()===200,'SID_FRESH_STATE_REFUSED');const fresh=await response.json(),freshCookies=await ctx.cookies(origin);ensure(fresh.generation===oldState.generation&&fresh.generation===initial.generation&&fresh.csrfToken!==oldState.csrfToken,'SID_FRESH_SESSION_OR_GENERATION');
    const oldSession=oldCookies.find(cookie=>cookie.name==='estakada_test_session'),freshSession=freshCookies.find(cookie=>cookie.name==='estakada_test_session');
    ensure(oldSession?.value&&freshSession?.value&&oldSession.value!==freshSession.value,'SID_SESSION_COOKIE_NOT_RENEWED');
    ensure(watch.posts.length===0,'SID_LOGIN_AUTOSENT');await page.getByRole('button',{name:'Войти снова',exact:true}).click();await page.waitForFunction(()=>document.querySelector('[data-editor-status]')?.textContent.includes('Вход выполнен.'),null,{timeout:30000});
    ensure(watch.posts.length===0&&page.url()===originalUrl&&await field(page).locator('.es-html-source').inputValue()==='<p>'+canary+'</p>','SID_REAUTH_CHANGED_INPUT_OR_SENT');unchanged(before,await observe());
    // get_token masks independently on each GET; compare with the bridge's
    // actual current-state response for this operation, never a separate GET.
    const checkStatePromise=page.waitForResponse(value=>{const url=new URL(value.url());return url.pathname===prefix()+'state/'&&url.search==='';},{timeout:30000});
    const newCheck=await checked(page),checkState=await (await checkStatePromise).json();ensure(watch.posts.length===1,'SID_EXPLICIT_CHECK_COUNT');const checkRequest=watch.posts[0],checkUrl=new URL(checkRequest.url()),checkBody=checkRequest.postDataJSON();
    ensure(checkUrl.searchParams.get('source')==='owner-draft'&&checkUrl.searchParams.get('draftId')===draft.id&&checkUrl.searchParams.get('draftRevision')===String(draft.revision)&&checkBody.draftBasis.id===draft.id&&checkBody.draftBasis.revision===draft.revision,'SID_REAUTH_SELECTED_BASIS_CHANGED');
    ensure(checkState.generation===initial.generation&&checkRequest.headers()['x-csrftoken']===checkState.csrfToken&&newCheck.checkReceipt,'SID_FRESH_CHECK_CSRF');
    const saveStatePromise=page.waitForResponse(value=>{const url=new URL(value.url());return url.pathname===prefix()+'state/'&&url.search==='';},{timeout:30000});
    const result=await write(page,'save'),saveState=await (await saveStatePromise).json();ensure(watch.posts.length===2,'SID_EXPLICIT_SAVE_COUNT');const saveRequest=watch.posts[1],body=saveRequest.postDataJSON();
    ensure(new URL(saveRequest.url()).pathname===prefix()+'save/'&&saveState.generation===initial.generation&&saveRequest.headers()['x-csrftoken']===saveState.csrfToken&&body.checkReceipt===newCheck.checkReceipt&&body.draftBasis.id===draft.id,'SID_FRESH_SAVE_BINDING');
    const after=await observe(),added=after.receipts.filter(row=>!before.receipts.some(old=>old.id===row.id));ensure(pageRow(after).currentId===result.result_id&&pageRow(after).payload.main_text==='<p>'+canary+'</p>'&&added.length===1&&added[0].actorId===seed.userIds[0]&&added[0].action==='commit_owner','SID_REAUTH_EXPLICIT_COMMIT');
    ensure(pageRow(after).history.length===pageRow(before).history.length+1,'SID_REAUTH_EXTRA_VERSION');watch.close();await invariant(page);
    return {sameOwnerSameGeneration:true,freshCsrf:true,selectedBasisAndRamRetained:true,noLoginOrReauthAutosend:true,explicitFreshCheckSave:true,oneActualCommit:true};});
  emit({kind:'result',status:'PASS',scope:'SID-four-selected-source-browser-identity-groups-not-heap-zeroization-or-new-generation-matrix',groups});
}catch(error){emit({kind:'result',status:'FAIL',caseId:current,errorCode:fixed(error?.message),errorClass:error?.constructor?.name||'Error',groups,diagnostics:{pageErrorCount:pageErrors.length,unexpectedRequestCount:unexpected.length}});process.exitCode=1;}
finally{for(const ctx of contexts)await ctx.close().catch(()=>{});await browser?.close().catch(()=>{});channel.close();}
