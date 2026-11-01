// RST native forms and selected-source regression. No new terminal editor UI.
import fs from 'node:fs';
import {randomUUID} from 'node:crypto';
import readline from 'node:readline';
import {chromium} from '/tests/node_modules/playwright/index.mjs';
const origin='http://host.docker.internal:8767',groups=[],contexts=[],pending=new Map(),pageErrors=[],unexpected=[];
const ensure=(value,code)=>{if(!value)throw new Error(code);};
const emit=value=>process.stdout.write(JSON.stringify(value)+'\n');
const fixed=value=>typeof value==='string'&&/^[A-Z0-9_]{1,100}$/.test(value)?value:'RST_BROWSER_FAILED';
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
  await value.addInitScript(()=>{globalThis.__rstCsp=[];document.addEventListener('securitypolicyviolation',event=>{if(globalThis.__rstCsp.length<8)globalThis.__rstCsp.push(/^[a-z-]{1,40}$/.test(event.effectiveDirective)?event.effectiveDirective:'unknown');});});
  value.on('page',page=>page.on('pageerror',()=>pageErrors.push('PAGE_ERROR')));return value;}
async function login(ctx,account){const page=await ctx.newPage();await page.goto(safe('/manage/login/'));await page.locator('[name=username]').fill(account.username);await page.locator('[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(safe('/manage/'),{timeout:15000}),page.locator('form[action="/manage/login/"] button').click()]);return page;}
async function invariant(page){ensure(pageErrors.length===0&&unexpected.length===0,'RST_PAGE_OR_EXTERNAL_ERROR');const facts=await page.evaluate(()=>({csp:globalThis.__rstCsp||[],storage:localStorage.length+sessionStorage.length,
  inline:document.querySelectorAll('[data-editor-page] [style],[data-editor-page] style,[data-editor-page] colgroup').length}));ensure(facts.csp.length===0&&facts.storage===0&&facts.inline===0,'RST_CSP_STORAGE_INLINE');}
async function checked(page){const response=page.waitForResponse(value=>new URL(value.url()).pathname.endsWith('/edit/check/'),{timeout:30000});await action(page,'check').click();const actual=await response;ensure(actual.status()===200,'RST_OWN_CHECK_REFUSED');
  await page.waitForFunction(()=>!document.querySelector('.es-page-actions [data-editor-action=check]').disabled,null,{timeout:30000});const accept=page.locator('.es-review').getByRole('button',{name:'Принять проверенный вариант',exact:true});if(await accept.isVisible())await accept.click();
  ensure((await page.locator('[data-editor-dirty]').textContent()).includes('Проверено.'),'RST_CHECK_NOT_ACCEPTED');return actual.json();}
async function ready(page,target){await page.goto(safe(target));await page.locator('.es-page-actions').waitFor();await field(page).locator('.es-toolbar').waitFor();}
async function createStage(page,ctx,id){
  const before=await observe();await page.goto(safe('/manage/pages/'+id+'/versions/'));
  const source=page.locator('[data-version-id="'+seed.currentIds[0]+'"]');ensure(await source.count()===1,'RST_HISTORICAL_SOURCE_MISSING');
  await Promise.all([page.waitForNavigation(),source.getByRole('link',{name:'Просмотреть',exact:true}).click()]);
  await Promise.all([page.waitForNavigation(),page.locator('form[data-restore-prepare] button').click()]);
  const form=page.locator('form[data-restore-stage]');ensure(!await form.locator('[name=confirm_input_replacement]').isChecked(),'RST_REPLACEMENT_PRECONFIRMED');await form.locator('[name=confirm_input_replacement]').check();
  const body=await form.evaluate(element=>Object.fromEntries(new FormData(element))),path=await form.getAttribute('action');
  await Promise.all([page.waitForNavigation(),form.locator('button').click()]);
  const stageId=await page.locator('[data-restore-staged]').getAttribute('data-restore-staged');ensure(/^[a-f0-9-]{36}$/.test(stageId||''),'RST_STAGE_ID_INVALID');
  const after=await observe();ensure(after.stages.some(stage=>stage.id===stageId&&stage.status==='held'),'RST_OWN_STAGE_NOT_HELD');
  ensure(pageRow(after,id).currentId===pageRow(before,id).currentId,'RST_STAGE_CREATE_PUBLISHED');
  ensure((await page.locator('[data-stage-field=main_text]').textContent()).includes(canary),'RST_OWN_CANDIDATE_MISSING');
  return {id:stageId,pageId:id,ctx,page,body,path,selected:prefix(id)+'?'+new URLSearchParams({source:'restore-stage',stageId}),state:prefix(id)+'state/?'+new URLSearchParams({source:'restore-stage',stageId})};
}
async function terminalReplay(stage,status){const before=await observe();const response=await stage.ctx.request.post(safe(stage.path),{form:stage.body,maxRedirects:0});ensure(response.status()===200,'RST_STAGE_RECEIPT_REPLAY_STATUS');
  const html=await response.text();ensure(html.includes('data-stage-status="'+status+'"')&&html.includes('data-replay="true"'),'RST_TERMINAL_RECEIPT_WRONG');
  ensure(!html.includes('data-stage-field')&&!html.includes('data-restore-editor')&&!html.includes(canary),'RST_TERMINAL_CANDIDATE_LEAK');
  const after=await observe();ensure(after.domainHash===before.domainHash&&after.versionAuditCount===before.versionAuditCount,'RST_TERMINAL_REPLAY_MUTATED');}
async function selectedDenied(stage,ctx=stage.ctx){const before=await observe();for(const path of [stage.selected,stage.state]){const response=await ctx.request.get(safe(path),{maxRedirects:0});ensure(response.status()===409,'RST_SELECTED_TERMINAL_STATUS');const value=await response.json();ensure(value.code==='EDITOR_BASE_UNAVAILABLE'&&!Object.hasOwn(value,'checkReceipt'),'RST_SELECTED_TERMINAL_DTO');ensure(!(await response.text()).includes(canary),'RST_SELECTED_CANARY_LEAK');}
  const after=await observe();ensure(after.domainHash===before.domainHash&&after.versionAuditCount===before.versionAuditCount,'RST_SELECTED_READ_MUTATED');}
async function group(id,requirements,fn){current=id;const facts=await fn();await invariant(owner);groups.push({id,requirements,status:'PASS',...facts});}

try{
  seed=JSON.parse(fs.readFileSync('/private/restore-terminal-seed.json','utf8'));browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});ownerContext=await context();owner=await login(ownerContext,seed.accounts.owner);
  const id=seed.pageIds[0],employeeContext=await context(),employee=await login(employeeContext,seed.accounts.employee);
  await group('RST-UI-001',['RST-001','RST-002'],async()=>{
    const stage=await createStage(owner,ownerContext,id),form=owner.locator('form[data-stage-cancel]');
    const body=await form.evaluate(element=>Object.fromEntries(new FormData(element))),path=await form.getAttribute('action');
    await Promise.all([owner.waitForNavigation(),form.locator('button').click()]);ensure(await owner.locator('[data-result-code=released]').count()===1,'RST_CANCEL_RESULT_MISSING');
    const after=await observe();ensure(after.stages.find(row=>row.id===stage.id)?.status==='released'&&!after.pins.some(pin=>pin.holderId===stage.id),'RST_RELEASED_PINS');
    const repeated=await ownerContext.request.post(safe(path),{form:body,maxRedirects:0});ensure(repeated.status()===200&&(await repeated.text()).includes('data-replay="true"'),'RST_CANCEL_EXACT_REPLAY');
    const replayed=await observe();ensure(replayed.domainHash===after.domainHash&&replayed.versionAuditCount===after.versionAuditCount,'RST_CANCEL_REPLAY_MUTATED');
    await selectedDenied(stage);await terminalReplay(stage,'released');return {nativeExplicitCancel:true,exactCancelReplay:true,separateStageReceiptReleased:true,editorSelected409:true};
  });
  await group('RST-UI-002',['RST-003'],async()=>{
    const stage=await createStage(employee,employeeContext,id);await ready(employee,stage.selected);
    await field(employee).locator('.es-toolbar').getByRole('button',{name:'HTML',exact:true}).click();await field(employee).locator('.es-html-source').fill('<p>RST EDITED THROUGH SELECTED SOURCE</p>');await checked(employee);
    let captured;const listener=request=>{if(request.method()==='POST'&&new URL(request.url()).pathname===prefix(id)+'save/')captured={body:request.postData(),path:new URL(request.url()).pathname+new URL(request.url()).search};};employee.on('request',listener);
    const result=employee.waitForResponse(response=>new URL(response.url()).pathname===prefix(id)+'save/',{timeout:30000});await action(employee,'save').click();ensure((await result).status()===200,'RST_SELECTED_SAVE_STATUS');
    await employee.waitForFunction(()=>document.querySelector('[data-editor-dirty]')?.textContent==='Сохранение подтверждено.',null,{timeout:30000});employee.off('request',listener);ensure(captured,'RST_SAVE_INTENT_NOT_CAPTURED');
    const after=await observe(),row=pageRow(after,id);ensure(row.payload.main_text==='<p>RST EDITED THROUGH SELECTED SOURCE</p>','RST_EDITED_STAGE_WRONG');
    ensure(after.stages.find(value=>value.id===stage.id)?.status==='consumed'&&!after.pins.some(pin=>pin.holderId===stage.id),'RST_CONSUMED_STAGE_PINS');ensure(row.history.at(-1).sourceId===seed.currentIds[0],'RST_SOURCE_PROVENANCE');
    const csrf=await employee.locator('[data-editor-page] [name=csrfmiddlewaretoken]').inputValue();const response=await employeeContext.request.post(safe(captured.path),{headers:{'Content-Type':'application/json','X-CSRFToken':csrf},data:captured.body,maxRedirects:0});
    ensure(response.status()===200&&(await response.json()).replay===true,'RST_CONSUMED_SAVE_EXACT_REPLAY');
    const fresh=JSON.parse(captured.body);fresh.operationId=randomUUID();const denied=await employeeContext.request.post(safe(captured.path),{headers:{'Content-Type':'application/json','X-CSRFToken':csrf},data:fresh,maxRedirects:0});
    ensure(denied.status()===409&&(await denied.json()).code==='EDITOR_BASE_UNAVAILABLE','RST_CONSUMED_FRESH_OPERATION');
    const replayed=await observe();ensure(replayed.domainHash===after.domainHash&&replayed.versionAuditCount===after.versionAuditCount,'RST_CONSUMED_REPLAY_MUTATED');
    await selectedDenied(stage);await terminalReplay(stage,'consumed');await invariant(employee);return {editedNativeStageSave:true,sourceProvenance:true,exactSaveReplay:true,freshOperationRefused:true};
  });
  await group('RST-UI-003',['RST-006'],async()=>{
    const foreign=await createStage(employee,employeeContext,id),otherContext=await context(),other=await login(otherContext,seed.accounts.other);
    for(const [page,ctx] of [[owner,ownerContext],[other,otherContext]]){
      const own=await createStage(page,ctx,id);await ready(page,own.selected);const checkedResult=await checked(page);
      const initial=JSON.parse(await page.locator('#editor-initial-state').textContent()),before=await observe();await selectedDenied(foreign,ctx);
      const query='?'+new URLSearchParams({source:'restore-stage',stageId:foreign.id}),csrf=await page.locator('[data-editor-page] [name=csrfmiddlewaretoken]').inputValue();
      const base={protocol:'page-editor-v1',generation:initial.generation,baseRevisionId:initial.baseRevisionId,editingFrom:'restore-stage',draftBasis:null,stageId:foreign.id,changes:checkedResult.normalisedChanges};
      const headers={'Content-Type':'application/json','X-CSRFToken':csrf};
      const check=await ctx.request.post(safe(prefix(id)+'check/'+query),{headers,data:base,maxRedirects:0});ensure(check.status()===409&&(await check.json()).code==='EDITOR_BASE_UNAVAILABLE','RST_FOREIGN_CHECK_ACTOR_BINDING');
      const save=await ctx.request.post(safe(prefix(id)+'save/'+query),{headers,data:{...base,operationId:randomUUID(),checkReceipt:checkedResult.checkReceipt},maxRedirects:0});ensure(save.status()===409&&(await save.json()).code==='EDITOR_BASE_UNAVAILABLE','RST_FOREIGN_SAVE_ACTOR_BINDING');
      const cancel=await ctx.request.post(safe('/manage/pages/'+id+'/versions/stages/'+foreign.id+'/cancel/'),{form:{generation:String(initial.generation),operation_id:randomUUID(),csrfmiddlewaretoken:csrf},maxRedirects:0});ensure(cancel.status()===403,'RST_FOREIGN_CANCEL_ACTOR_BINDING');
      const after=await observe();ensure(after.domainHash===before.domainHash&&after.versionAuditCount===before.versionAuditCount,'RST_FOREIGN_STAGE_MUTATED');ensure(after.stages.find(row=>row.id===foreign.id)?.status==='held','RST_FOREIGN_STAGE_NOT_HELD');await invariant(page);
    }
    await owner.screenshot({path:'/evidence/restore-1280.png',fullPage:true,caret:'initial'});await owner.setViewportSize({width:390,height:844});await owner.screenshot({path:'/evidence/restore-390.png',fullPage:true,caret:'initial'});
    return {samePageSameGrantsEmployee:true,ownerAlsoDenied:true,bothOwnHeldPositive:true,noCrossActorApplyCancel:true};
  });
  emit({kind:'result',status:'PASS',scope:'RST-three-native-groups-existing-terminal-results-not-new-stage-read-ui',groups});
}catch(error){emit({kind:'result',status:'FAIL',caseId:current,errorCode:fixed(error?.message),errorClass:error?.constructor?.name||'Error',groups,diagnostics:{pageErrorCount:pageErrors.length,unexpectedRequestCount:unexpected.length}});process.exitCode=1;
}finally{for(const ctx of contexts)await ctx.close().catch(()=>{});if(browser)await browser.close().catch(()=>{});channel.close();}
