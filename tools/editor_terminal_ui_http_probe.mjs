// RUI actual private stage-read messages, using the immutable RST fixture.
import fs from 'node:fs';
import readline from 'node:readline';
import {chromium} from '/tests/node_modules/playwright/index.mjs';
const origin='http://host.docker.internal:8767',groups=[],contexts=[],pending=new Map(),pageErrors=[],unexpected=[];
const ensure=(value,code)=>{if(!value)throw new Error(code);};
const emit=value=>process.stdout.write(JSON.stringify(value)+'\n');
const fixed=value=>typeof value==='string'&&/^[A-Z0-9_]{1,100}$/.test(value)?value:'RUI_BROWSER_FAILED';
const safe=value=>{ensure(typeof value==='string'&&value.startsWith('/')&&new URL(value,origin).origin===origin,'FIXED_ORIGIN');return origin+value;};
let serial=0,current='START',browser,seed,owner,ownerContext;
const channel=readline.createInterface({input:process.stdin,terminal:false});
channel.on('line',line=>{try{const value=JSON.parse(line),resolve=pending.get(value.id);ensure(value.kind==='observation'&&resolve,'CLOSED_OBSERVER_PROTOCOL');pending.delete(value.id);resolve(value.value);}catch{process.exitCode=1;}});
function observe(){return new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{pending.delete(id);reject(new Error('OBSERVER_TIMEOUT'));},30000);
  pending.set(id,value=>{clearTimeout(timer);resolve(value);});emit({kind:'observe',id,caseId:current,operation:'observe'});});}
const pageRow=(state,id)=>{const found=state.pages.find(row=>row.id===id);ensure(found,'OWN_PAGE_MISSING');return found;};
const prefix=id=>'/manage/pages/'+id+'/edit/';
const action=(page,name)=>page.locator('.es-page-actions [data-editor-action="'+name+'"]');
const field=page=>page.locator('[data-editor-field=main_text]');
const canary='RST HISTORICAL SOURCE CANARY';
async function context(){const value=await browser.newContext({viewport:{width:1280,height:900}});contexts.push(value);
  await value.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():(unexpected.push('EXTERNAL_REQUEST'),route.abort()));
  await value.addInitScript(()=>{globalThis.__ruiCsp=[];document.addEventListener('securitypolicyviolation',event=>{if(globalThis.__ruiCsp.length<8)globalThis.__ruiCsp.push(/^[a-z-]{1,40}$/.test(event.effectiveDirective)?event.effectiveDirective:'unknown');});});
  value.on('page',page=>page.on('pageerror',()=>pageErrors.push('PAGE_ERROR')));return value;}
async function login(ctx,account){const page=await ctx.newPage();await page.goto(safe('/manage/login/'));await page.locator('[name=username]').fill(account.username);await page.locator('[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(safe('/manage/'),{timeout:15000}),page.locator('form[action="/manage/login/"] button').click()]);return page;}
async function invariant(page){ensure(pageErrors.length===0&&unexpected.length===0,'RUI_PAGE_OR_EXTERNAL_ERROR');const facts=await page.evaluate(()=>({csp:globalThis.__ruiCsp||[],storage:localStorage.length+sessionStorage.length,
  inline:document.querySelectorAll('[data-editor-page] [style],[data-editor-page] style,[data-editor-page] colgroup').length}));ensure(facts.csp.length===0&&facts.storage===0&&facts.inline===0,'RUI_CSP_STORAGE_INLINE');}
async function checked(page){const response=page.waitForResponse(value=>new URL(value.url()).pathname.endsWith('/edit/check/'),{timeout:30000});await action(page,'check').click();const actual=await response;ensure(actual.status()===200,'RUI_OWN_CHECK_REFUSED');
  await page.waitForFunction(()=>!document.querySelector('.es-page-actions [data-editor-action=check]').disabled,null,{timeout:30000});const accept=page.locator('.es-review').getByRole('button',{name:'Принять проверенный вариант',exact:true});if(await accept.isVisible())await accept.click();
  ensure((await page.locator('[data-editor-dirty]').textContent()).includes('Проверено.'),'RUI_CHECK_NOT_ACCEPTED');return actual.json();}
async function ready(page,target){await page.goto(safe(target));await page.locator('.es-page-actions').waitFor();await field(page).locator('.es-toolbar').waitFor();}
async function createStage(page,ctx,id){
  const before=await observe();await page.goto(safe('/manage/pages/'+id+'/versions/'));
  const source=page.locator('[data-version-id="'+seed.currentIds[0]+'"]');ensure(await source.count()===1,'RUI_HISTORICAL_SOURCE_MISSING');
  await Promise.all([page.waitForNavigation(),source.getByRole('link',{name:'Просмотреть',exact:true}).click()]);
  await Promise.all([page.waitForNavigation(),page.locator('form[data-restore-prepare] button').click()]);
  const form=page.locator('form[data-restore-stage]');ensure(!await form.locator('[name=confirm_input_replacement]').isChecked(),'RUI_REPLACEMENT_PRECONFIRMED');await form.locator('[name=confirm_input_replacement]').check();
  const body=await form.evaluate(element=>Object.fromEntries(new FormData(element))),path=await form.getAttribute('action');
  await Promise.all([page.waitForNavigation(),form.locator('button').click()]);
  const stageId=await page.locator('[data-restore-staged]').getAttribute('data-restore-staged');ensure(/^[a-f0-9-]{36}$/.test(stageId||''),'RUI_STAGE_ID_INVALID');
  const after=await observe();ensure(after.stages.some(stage=>stage.id===stageId&&stage.status==='held'),'RUI_OWN_STAGE_NOT_HELD');
  ensure(pageRow(after,id).currentId===pageRow(before,id).currentId,'RUI_STAGE_CREATE_PUBLISHED');
  ensure((await page.locator('[data-stage-field=main_text]').textContent()).includes(canary),'RUI_OWN_CANDIDATE_MISSING');
  return {id:stageId,pageId:id,ctx,page,body,path,selected:prefix(id)+'?'+new URLSearchParams({source:'restore-stage',stageId}),state:prefix(id)+'state/?'+new URLSearchParams({source:'restore-stage',stageId})};
}

const messages={
  released:'Подготовка восстановления отменена. Данные для подстановки не выдаются. Текущая версия страницы не изменена этим просмотром.',
  consumed:'Подготовка восстановления уже применена. Повторная подстановка недоступна. Текущая версия страницы не изменена этим просмотром.',
  invalidated:'Подготовка восстановления утратила актуальность. Подготовьте восстановление заново из истории. Текущая версия страницы не изменена этим просмотром.'
};
const stagePath=stage=>'/manage/pages/'+stage.pageId+'/versions/stages/'+stage.id+'/';
async function noCandidate(page){ensure(await page.locator('[data-stage-field],[data-restore-staged],[data-restore-editor],[data-version-result],#editor-initial-state').count()===0,'RUI_CANDIDATE_OR_RECEIPT_PRESENT');ensure(!(await page.content()).includes(canary),'RUI_SOURCE_CANARY_LEAK');}
async function visibleTerminal(stage,status){const before=await observe();
  for(let index=0;index<2;index++){
    const response=await stage.page.goto(safe(stagePath(stage)));ensure(response.status()===409,'RUI_TERMINAL_STATUS');
    ensure((response.headers()['cache-control']||'').includes('no-store'),'RUI_TERMINAL_CACHE');
    ensure(await stage.page.getByText(messages[status],{exact:true}).isVisible(),'RUI_TERMINAL_MESSAGE');await noCandidate(stage.page);await invariant(stage.page);
  }
  const after=await observe();ensure(after.domainHash===before.domainHash&&after.versionAuditCount===before.versionAuditCount,'RUI_REPEATED_GET_MUTATED');
}
async function foreignNegative(stage,page,ctx){const permitted=await ctx.request.get(safe(prefix(stage.pageId)+'state/'),{maxRedirects:0});ensure(permitted.status()===200,'RUI_FOREIGN_ACTOR_HAS_NO_PAGE_RIGHTS');
  const before=await observe(),response=await page.goto(safe(stagePath(stage)));ensure(response.status()===409,'RUI_FOREIGN_STAGE_STATUS');await noCandidate(page);
  const content=await page.content();for(const message of Object.values(messages))ensure(!content.includes(message),'RUI_FOREIGN_TERMINAL_STATUS_LEAK');
  const after=await observe();ensure(after.domainHash===before.domainHash&&after.versionAuditCount===before.versionAuditCount,'RUI_FOREIGN_READ_MUTATED');await invariant(page);
}
async function source(page,html){await field(page).locator('.es-toolbar').getByRole('button',{name:'HTML',exact:true}).click();await field(page).locator('.es-html-source').fill(html);}
async function save(page){const pending=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/edit/save/'),{timeout:30000});await action(page,'save').click();ensure((await pending).status()===200,'RUI_SAVE_SETUP_REFUSED');
  await page.waitForFunction(()=>document.querySelector('[data-editor-dirty]')?.textContent==='Сохранение подтверждено.',null,{timeout:30000});}
async function group(id,fn){current=id;const facts=await fn();groups.push({id,status:'PASS',...facts});}

try{
  seed=JSON.parse(fs.readFileSync('/private/terminal-ui-seed.json','utf8'));browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
  ownerContext=await context();owner=await login(ownerContext,seed.accounts.owner);
  const id=seed.pageIds[0],employeeContext=await context(),employee=await login(employeeContext,seed.accounts.employee),otherContext=await context(),other=await login(otherContext,seed.accounts.other);
  await group('RUI-001',async()=>{
    const stage=await createStage(owner,ownerContext,id),form=owner.locator('form[data-stage-cancel]');
    await Promise.all([owner.waitForNavigation(),form.locator('button').click()]);
    const after=await observe();ensure(after.stages.find(row=>row.id===stage.id)?.status==='released'&&!after.pins.some(pin=>pin.holderId===stage.id),'RUI_CANCEL_SETUP_NOT_RELEASED');
    await visibleTerminal(stage,'released');await foreignNegative(stage,other,otherContext);
    return {nativeCancel:true,visibleReleased:true,repeatedGetReadOnly:true,samePageForeignGeneric:true};
  });
  await group('RUI-002',async()=>{
    const stage=await createStage(employee,employeeContext,id);await ready(employee,stage.selected);
    await source(employee,'<p>RUI ACTUAL SELECTED SAVE</p>');await checked(employee);await save(employee);
    const after=await observe();ensure(after.stages.find(row=>row.id===stage.id)?.status==='consumed'&&pageRow(after,id).payload.main_text==='<p>RUI ACTUAL SELECTED SAVE</p>','RUI_CONSUME_SETUP_NOT_REAL');
    await visibleTerminal(stage,'consumed');await foreignNegative(stage,owner,ownerContext);
    return {nativeEditedSave:true,visibleConsumed:true,noRepeatApplication:true,ownerForeignGeneric:true};
  });
  await group('RUI-003',async()=>{
    const stage=await createStage(owner,ownerContext,id);await ready(employee,prefix(id));
    await source(employee,'<p>RUI ACTUAL CURRENT COMPETITOR</p>');await checked(employee);await save(employee);
    const after=await observe();ensure(after.stages.find(row=>row.id===stage.id)?.status==='invalidated'&&!after.pins.some(pin=>pin.holderId===stage.id),'RUI_INVALIDATION_SETUP_NOT_REAL');
    await visibleTerminal(stage,'invalidated');
    await owner.screenshot({path:'/evidence/terminal-1280.png',fullPage:true,caret:'initial'});await owner.setViewportSize({width:390,height:844});await owner.screenshot({path:'/evidence/terminal-390.png',fullPage:true,caret:'initial'});await invariant(owner);
    return {actualCompetitorCommit:true,visibleStaleMessage:true,repeatedGetReadOnly:true,noNewStageOrRedirect:true};
  });
  emit({kind:'result',status:'PASS',scope:'RUI-three-native-stage-read-messages-not-full-terminal-matrix',groups});
}catch(error){emit({kind:'result',status:'FAIL',caseId:current,errorCode:fixed(error?.message),errorClass:error?.constructor?.name||'Error',groups,diagnostics:{pageErrorCount:pageErrors.length,unexpectedRequestCount:unexpected.length}});process.exitCode=1;
}finally{for(const ctx of contexts)await ctx.close().catch(()=>{});if(browser)await browser.close().catch(()=>{});channel.close();}

