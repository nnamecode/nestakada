// D-327/328. Real closed-history UI/HTTP, never a fake editor or publication writer.
import crypto from 'node:crypto';
import readline from 'node:readline';
import {chromium} from '/tests/node_modules/playwright/index.mjs';
const origin='http://host.docker.internal:8767';
const input=readline.createInterface({input:process.stdin,terminal:false});
const waiting=new Map();let startResolve,serial=0;
const start=new Promise(resolve=>{startResolve=resolve;});
const output=data=>process.stdout.write(JSON.stringify(data)+'\n');
input.on('line',line=>{
  try{
    const value=JSON.parse(line);
    if(value.kind==='seed')startResolve(value);
    else if(value.kind==='observation'&&waiting.has(value.id)){
      const waiter=waiting.get(value.id);waiting.delete(value.id);
      value.error?waiter.reject(new Error('HOST_OBSERVER_FAILED')):waiter.resolve(value.value);
    }
  }catch{process.exitCode=1;}
});
function observe(){
  const id=++serial;
  return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{waiting.delete(id);reject(new Error('OBSERVER_TIMEOUT'));},30_000);
    waiting.set(id,{resolve:v=>{clearTimeout(timer);resolve(v);},reject:e=>{clearTimeout(timer);reject(e);}});
    output({kind:'observe',id});
  });
}
const requireCheck=(condition,code)=>{if(!condition)throw new Error(code);};
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const safe=p=>{const url=new URL(p,origin);requireCheck(typeof p==='string'&&p.startsWith('/')&&url.origin===origin,'FIXED_ORIGIN');return url.href;};
const passed=[];let current='START',browser;const contexts=[];
async function check(id,body){current=id;const facts=await body();passed.push({id,status:'PASS',...facts});}
async function newContext(){
  const context=await browser.newContext({viewport:{width:1280,height:900},timezoneId:'UTC'});
  contexts.push(context);
  await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  return context;
}
async function actor(account){
  const context=await newContext(),page=await context.newPage();
  await page.goto(safe('/manage/login/'));
  await page.locator('input[name=username]').fill(account.username);
  await page.locator('input[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(safe('/manage/')),page.locator('form[action="/manage/login/"] button').click()]);
  requireCheck(await page.locator('input[type=password]').count()===0,'LOGIN_NOT_COMPLETE');
  return {context,page,api:context.request};
}
async function csrf(who){
  if(who.visitor)return who.loginCsrf;
  const page=who.page;
  return page.locator('form[action="/manage/logout/"] input[name=csrfmiddlewaretoken]').inputValue();
}
async function formFields(locator){
  return locator.evaluate(form=>Object.fromEntries(new FormData(form)));
}
async function post(who,path,fields){
  return who.api.post(safe(path),{form:fields,maxRedirects:0,headers:{Referer:origin+'/manage/'},timeout:30_000});
}
async function get(who,path){return who.api.get(safe(path),{maxRedirects:0,timeout:30_000});}
async function privateHeaders(response){
  const h=response.headers();
  requireCheck((h['cache-control']??'').includes('private')&&(h['cache-control']??'').includes('no-store')&&(h.vary??'').toLowerCase().split(/,\s*/u).includes('cookie'),'PRIVATE_CACHE_HEADERS');
}
async function clickSubmit(who,locator){
  const [response]=await Promise.all([who.page.waitForNavigation({waitUntil:'domcontentloaded'}),locator.locator('button').click()]);
  requireCheck(response?.status()===200,'UI_MUTATION_STATUS');
  return response;
}
async function result(who){
  const node=who.page.locator('[data-version-result]');
  requireCheck(await node.count()===1,'RESULT_MARKER');
  return {id:await node.getAttribute('data-version-result'),operationId:await node.getAttribute('data-operation-id'),
    code:await node.getAttribute('data-result-code'),replay:await node.getAttribute('data-replay'),gone:await node.getAttribute('data-gone')};
}
const pageState=(state,id)=>{const page=state.pages.find(p=>p.id===id);requireCheck(page,'OBSERVED_PAGE_MISSING');return page;};
const revision=(state,page,id)=>{const row=pageState(state,page).versions.find(r=>r.id===id);requireCheck(row,'OBSERVED_REVISION_MISSING');return row;};
function currentDomain(state){
  return {pages:state.pages.map(page=>({id:page.id,name:page.name,parentId:page.parentId,position:page.position,
    kind:page.kind,isPublished:page.isPublished,routes:page.routes,currentId:page.currentId,
    currentPayloadHash:page.versions.find(row=>row.id===page.currentId)?.payloadHash})),drafts:state.drafts};
}
function fileDomain(state){
  return state.assets.map(asset=>({id:asset.id,status:asset.status,files:asset.files})).sort((a,b)=>a.id.localeCompare(b.id));
}
function assertCurrent(before,after){requireCheck(equal(currentDomain(before),currentDomain(after)),'CURRENT_DRAFT_PAGE_CHANGED');}
function assertPhysical(before,after){requireCheck(equal(fileDomain(before),fileDomain(after)),'VERSION_MUTATION_CHANGED_MEDIA_BYTES');}
function assertManualPrune(before,after,pageId,newId){
  const a=pageState(before,pageId),b=pageState(after,pageId);
  const ordinary=a.versions.filter(row=>!row.stable);
  const held=new Set(before.pins.map(pin=>pin.revisionId));
  for(const draft of before.drafts)held.add(draft.baseId);
  const eligible=ordinary.filter(row=>row.id!==a.currentId&&!held.has(row.id)).sort((x,y)=>Date.parse(x.createdAt)-Date.parse(y.createdAt)||x.sequence-y.sequence||x.id.localeCompare(y.id));
  const count=Math.max(0,ordinary.length+1-10);
  const removed=new Set(eligible.slice(0,count).map(row=>row.id));
  const expected=[...a.versions.map(row=>row.id).filter(id=>!removed.has(id)),newId].sort();
  requireCheck(equal(b.versions.map(row=>row.id).sort(),expected),'MANUAL_PRUNE_WRONG_IDS');
  requireCheck(b.versions.filter(row=>!row.stable).length<=10,'ORDINARY_OVER_LIMIT');
  requireCheck(a.versions.filter(row=>row.stable).every(row=>b.versions.some(now=>now.id===row.id&&now.stable)),'STABLE_PRUNED');
}
try{
  const boot=await start,seed=boot.fixture;
  requireCheck(boot.origin===origin&&seed.pageIds?.length===2&&seed.userIds?.length===3&&seed.assetIds?.length===3,'FIXTURE_CONTRACT');
  const pageId=seed.pageIds[0],base='/manage/pages/'+pageId+'/versions/';
  const versionPath=(id,suffix='')=>base+id+'/'+suffix;
  browser=await chromium.launch({headless:true});
  const owner=await actor(seed.accounts.owner),employee=await actor(seed.accounts.employee),other=await actor(seed.accounts.other);
  const visitorContext=await newContext(),visitorPage=await visitorContext.newPage();
  await visitorPage.goto(safe('/manage/login/'));
  const visitor={context:visitorContext,page:visitorPage,api:visitorContext.request,visitor:true,
    loginCsrf:await visitorPage.locator('input[name=csrfmiddlewaretoken]').inputValue()};
  const initial=await observe();
  let manualId,manualCreateFields,manualCreationState,nextManualId;
  async function read(who,id){
    const response=await who.page.goto(safe(versionPath(id)));requireCheck(response?.status()===200,'VERSION_READ_STATUS');
    return who.page.locator('[data-version-read="'+id+'"]');
  }
  async function manual(who,name,date){
    const response=await who.page.goto(safe(base+'manual/prepare/'));requireCheck(response?.status()===200,'MANUAL_PREPARE_STATUS');
    const form=who.page.locator('form[data-manual-create]');
    requireCheck(await who.page.locator('[data-manual-source]').getAttribute('data-manual-source')===pageState(await observe(),pageId).currentId,'MANUAL_SOURCE_NOT_CURRENT');
    await form.locator('[name=name]').fill(name);await form.locator('[name=comment]').fill('Synthetic checkpoint');
    await form.locator('[name=manual_date]').fill(date);
    const fields=await formFields(form);await clickSubmit(who,form);
    return {value:await result(who),fields};
  }
  async function metadata(who,id,{name,comment,manualDate}){
    const response=await who.page.goto(safe(versionPath(id,'metadata/')));requireCheck(response?.status()===200,'METADATA_GET_STATUS');
    const form=who.page.locator('form[data-manual-metadata]');
    await form.locator('[name=name]').fill(name);await form.locator('[name=comment]').fill(comment);await form.locator('[name=manual_date]').fill(manualDate);
    const fields=await formFields(form);await clickSubmit(who,form);return {value:await result(who),fields};
  }
  await check('VH-001',async()=>{
    const page=pageState(initial,pageId);
    requireCheck(page.versions.length===12&&page.versions.filter(row=>!row.stable).length===10&&page.versions.filter(row=>row.stable).length===2,'INITIAL_10_PLUS_2');
    for(const who of [owner,employee]){
      const response=await who.page.goto(safe(base));requireCheck(response?.status()===200,'HISTORY_STATUS');
      await privateHeaders(response);
      requireCheck(await who.page.locator('[data-ordinary-count]').getAttribute('data-ordinary-count')==='10','HISTORY_ORDINARY_COUNT');
      requireCheck(await who.page.locator('[data-stable-count]').getAttribute('data-stable-count')==='2','HISTORY_STABLE_COUNT');
      const ids=await who.page.locator('[data-version-id]').evaluateAll(nodes=>nodes.map(node=>node.dataset.versionId).sort());
      requireCheck(equal(ids,page.versions.map(row=>row.id).sort()),'HISTORY_IDS');
    }
    for(const path of [base,versionPath(seed.stableIds[0]),versionPath(seed.stableIds[0],'compare/')]){
      requireCheck((await get(visitor,path)).status()===401,'VISITOR_HISTORY_NOT_DENIED');
      requireCheck((await get(other,path)).status()===403,'OTHER_HISTORY_NOT_DENIED');
    }
    return {ordinary:10,stable:2,assignedEmployeeAllIds:true};
  });
  await check('VH-002',async()=>{
    const before=await observe();
    for(const who of [owner,employee]){
      await read(who,seed.stableIds[0]);
      requireCheck((await who.page.locator('[data-version-payload]').textContent()).includes(seed.textCanary),'ESCAPED_PAYLOAD_TEXT_MISSING');
      requireCheck(await who.page.locator('[data-version-payload] script').count()===0,'SCRIPT_NODE_IN_HISTORY');
      requireCheck(await who.page.evaluate(()=>globalThis.__version_probe_executed===undefined),'SCRIPT_EXECUTED');
      await who.page.goto(safe(versionPath(seed.stableIds[0],'compare/')));
      requireCheck(!(await who.page.content()).includes(seed.draftCanary),'DRAFT_CANARY_IN_COMPARE');
    }
    requireCheck((await get(employee,base+'draft/')).status()===403,'EMPLOYEE_DRAFT_EXPOSED');
    await owner.page.goto(safe(base+'draft/'));
    requireCheck((await owner.page.locator('[data-owner-draft]').textContent()).includes(seed.draftCanary),'OWNER_DRAFT_CONTROL');
    const after=await observe();assertCurrent(before,after);
    requireCheck(equal(before.pins,after.pins)&&before.receipts.length===after.receipts.length,'READ_CREATED_PINS_OR_RECEIPTS');
    return {escapedRead:true,noScript:true,draftOwnerOnly:true};
  });
  await check('VH-003',async()=>{
    const before=await observe(),created=await manual(owner,'HTTP checkpoint 1960','1960-01-01T00:00:00+00:00');
    manualId=created.value.id;manualCreateFields=created.fields;
    manualCreationState=await observe();
    const row=revision(manualCreationState,pageId,manualId);
    requireCheck(row.kind==='manual'&&!row.stable&&row.sourceRevisionId===pageState(before,pageId).currentId,'MANUAL_TYPE_SOURCE');
    requireCheck(row.payloadHash===revision(before,pageId,pageState(before,pageId).currentId).payloadHash,'MANUAL_COPIED_WRONG_PAYLOAD');
    requireCheck(row.authorId===seed.userIds[0]&&new Date(row.metadata.manualDate).getUTCFullYear()===1960,'MANUAL_METADATA_AUTHOR');
    requireCheck(new Date(row.createdAt).getUTCFullYear()!==1960,'MANUAL_DATE_REPLACED_CREATED');
    assertCurrent(before,manualCreationState);assertPhysical(before,manualCreationState);
    assertManualPrune(before,manualCreationState,pageId,manualId);
    return {versionId:manualId,manualYear:1960,ordinaryLimit:true,currentUnchanged:true};
  });
  await check('VH-004',async()=>{
    const before=await observe();
    const replay=await post(owner,base+'manual/create/',manualCreateFields);
    requireCheck(replay.status()===200,'MANUAL_REPLAY_STATUS');
    const body=await replay.text();
    requireCheck(body.includes('data-version-result="'+manualId+'"')&&body.includes('data-replay="true"'),'MANUAL_REPLAY_RESULT');
    const mismatch=await post(owner,base+'manual/create/',{...manualCreateFields,name:'Changed same operation'});
    requireCheck(mismatch.status()===409,'MANUAL_REPLAY_MISMATCH');
    const denied=await post(employee,base+'manual/create/',{...manualCreateFields,csrfmiddlewaretoken:await csrf(employee)});
    requireCheck(denied.status()===403,'EMPLOYEE_MANUAL_REPLAY');
    const after=await observe();requireCheck(equal(before.pages,after.pages)&&before.receipts.length===after.receipts.length&&before.versionAuditCount===after.versionAuditCount,'MANUAL_REPLAY_MUTATED');
    return {sameResult:true,mismatchDenied:true,noDuplicateReceiptAudit:true};
  });
  await check('VH-005',async()=>{
    const before=await observe(),original=revision(before,pageId,manualId);
    await owner.page.goto(safe(versionPath(manualId,'metadata/')));
    const fields=await formFields(owner.page.locator('form[data-manual-metadata]'));
    for(const patch of [{name:'N'.repeat(201)},{comment:'C'.repeat(1001)},{manual_date:'2099-01-01T00:00:00'}]){
      const denied=await post(owner,versionPath(manualId,'metadata/'),{...fields,...patch,operation_id:crypto.randomUUID()});
      requireCheck(denied.status()===409,'METADATA_BOUNDARY_NOT_REJECTED');
    }
    requireCheck((await post(employee,versionPath(manualId,'metadata/'),{...fields,csrfmiddlewaretoken:await csrf(employee)})).status()===403,'EMPLOYEE_METADATA_EDIT');
    await metadata(owner,manualId,{name:'N'.repeat(200),comment:'C'.repeat(1000),manualDate:'2099-01-01T00:00:00+00:00'});
    const after=await observe(),changed=revision(after,pageId,manualId);
    for(const key of ['payloadHash','createdAt','authorId','sequence','sourceRevisionId'])requireCheck(changed[key]===original[key],'METADATA_CHANGED_IMMUTABLE');
    requireCheck(changed.metadata.name.length===200&&changed.metadata.comment.length===1000&&new Date(changed.metadata.manualDate).getUTCFullYear()===2099,'METADATA_VALID_BOUNDARIES');
    assertCurrent(before,after);
    return {manualYear:2099,name200:true,comment1000:true,immutablePreserved:true};
  });
  await check('VH-006',async()=>{
    await read(owner,manualId);
    const form=owner.page.locator('form[data-stable-set]'),fields=await formFields(form),path=versionPath(manualId,'stable/');
    const before=await observe();
    for(const who of [employee,other,visitor]){
      const denied=await post(who,path,{...fields,csrfmiddlewaretoken:await csrf(who)});
      requireCheck(denied.status()===(who.visitor?401:403),'STABLE_ROLE_NOT_DENIED');
    }
    const missing={...fields};delete missing.csrfmiddlewaretoken;
    requireCheck((await post(owner,path,missing)).status()===403,'STABLE_CSRF');
    requireCheck((await get(owner,path)).status()===405,'STABLE_GET_MUTATED');
    requireCheck((await post(owner,path,{...fields,view_receipt:'tampered'})).status()===409,'STABLE_VIEW_TAMPER');
    await clickSubmit(owner,form);
    const promoted=await observe();requireCheck(revision(promoted,pageId,manualId).stable,'STABLE_NOT_MARKED');
    assertCurrent(before,promoted);assertPhysical(before,promoted);
    const created=await manual(owner,'HTTP ordinary after Stable','1960-02-01T00:00:00+00:00');nextManualId=created.value.id;
    const after=await observe();requireCheck(!revision(after,pageId,nextManualId).stable,'STABLE_INHERITED');
    return {versionId:manualId,newOrdinaryId:nextManualId,stableNotPublication:true,noInheritance:true};
  });
  await check('VH-007',async()=>{
    const before=await observe(),original=revision(before,pageId,manualId);
    await owner.page.goto(safe(versionPath(manualId,'demote/prepare/')));
    let form=owner.page.locator('form[data-stable-demote]'),fields=await formFields(form);
    requireCheck((await post(owner,versionPath(manualId,'demote/'),{...fields,password:'wrong-current-password'})).status()===403,'DEMOTE_WRONG_PASSWORD');
    await metadata(owner,manualId,{name:'Stable metadata changed',comment:'Allowed metadata change',manualDate:'2099-01-01T00:00:00+00:00'});
    requireCheck((await post(owner,versionPath(manualId,'demote/'),{...fields,password:seed.accounts.owner.password})).status()===409,'STALE_DEMOTE_ACCEPTED');
    requireCheck(revision(await observe(),pageId,manualId).stable,'FAILED_DEMOTE_REMOVED_PROTECTION');
    await owner.page.goto(safe(versionPath(manualId,'demote/prepare/')));form=owner.page.locator('form[data-stable-demote]');
    await form.locator('[name=password]').fill(seed.accounts.owner.password);
    await clickSubmit(owner,form);
    const after=await observe(),row=revision(after,pageId,manualId);
    requireCheck(!row.stable&&row.createdAt===original.createdAt&&row.payloadHash===original.payloadHash,'DEMOTE_CHANGED_SNAPSHOT');
    requireCheck(pageState(after,pageId).versions.filter(v=>!v.stable).length===10,'DEMOTE_LIMIT');
    const held=new Set([...before.pins.map(pin=>pin.revisionId),...before.drafts.map(draft=>draft.baseId)]);
    const candidates=pageState(before,pageId).versions.filter(v=>(!v.stable||v.id===manualId)&&v.id!==pageState(before,pageId).currentId&&!held.has(v.id))
      .sort((a,b)=>Date.parse(a.createdAt)-Date.parse(b.createdAt)||a.sequence-b.sequence||a.id.localeCompare(b.id));
    requireCheck(candidates.length>0&&equal(pageState(after,pageId).versions.map(v=>v.id).sort(),pageState(before,pageId).versions.filter(v=>v.id!==candidates[0].id).map(v=>v.id).sort()),'DEMOTE_PRUNED_WRONG_SERVER_OLDEST');
    requireCheck(seed.stableIds.every(id=>revision(after,pageId,id).stable),'ORIGINAL_STABLE_LOST');
    assertCurrent(before,after);assertPhysical(before,after);
    return {wrongPasswordDenied:true,staleCompositionDenied:true,currentPasswordAccepted:true,ordinary:10};
  });
  let deleteFields;
  await check('VH-008',async()=>{
    for(const id of [seed.currentId,seed.stableIds[0],seed.pinnedBaseId])
      requireCheck((await get(owner,versionPath(id,'delete/prepare/'))).status()===409,'PROTECTED_DELETE_PREPARED');
    const before=await observe();
    await owner.page.goto(safe(versionPath(nextManualId,'delete/prepare/')));
    let form=owner.page.locator('form[data-version-delete]');
    await Promise.all([owner.page.waitForURL(safe(versionPath(nextManualId))),form.getByRole('link',{name:'Отмена',exact:true}).click()]);
    requireCheck(equal(before.pages,(await observe()).pages),'DELETE_CANCEL_CHANGED_HISTORY');
    await owner.page.goto(safe(versionPath(nextManualId,'delete/prepare/')));form=owner.page.locator('form[data-version-delete]');
    const stale=await formFields(form);
    await metadata(owner,nextManualId,{name:'Changed before delete',comment:'New metadata',manualDate:'1960-02-01T00:00:00+00:00'});
    requireCheck((await post(owner,versionPath(nextManualId,'delete/'),stale)).status()===409,'STALE_DELETE_ACCEPTED');
    await owner.page.goto(safe(versionPath(nextManualId,'delete/prepare/')));form=owner.page.locator('form[data-version-delete]');deleteFields=await formFields(form);
    for(const who of [employee,visitor]){
      const denied=await post(who,versionPath(nextManualId,'delete/'),{...deleteFields,csrfmiddlewaretoken:await csrf(who)});
      requireCheck(denied.status()===(who.visitor?401:403),'DELETE_ROLE_DENIAL');
    }
    const noCsrf={...deleteFields};delete noCsrf.csrfmiddlewaretoken;
    requireCheck((await post(owner,versionPath(nextManualId,'delete/'),noCsrf)).status()===403,'DELETE_CSRF');
    requireCheck((await post(owner,versionPath(nextManualId,'delete/'),{...deleteFields,confirmation:'forged'})).status()===409,'DELETE_TICKET');
    const exactBefore=await observe();await clickSubmit(owner,form);
    const after=await observe();
    requireCheck(!pageState(after,pageId).versions.some(v=>v.id===nextManualId),'DELETED_VERSION_REMAINED');
    requireCheck(equal(pageState(after,pageId).versions.map(v=>v.id).sort(),pageState(exactBefore,pageId).versions.filter(v=>v.id!==nextManualId).map(v=>v.id).sort()),'DELETE_WRONG_SET');
    assertCurrent(before,after);assertPhysical(before,after);
    return {deletedId:nextManualId,protectedCurrentStableBase:true,cancelUnchanged:true,physicalUnlinkAbsent:true};
  });
  await check('VH-009',async()=>{
    const before=await observe(),replay=await post(owner,versionPath(nextManualId,'delete/'),deleteFields);
    requireCheck(replay.status()===200,'DELETE_REPLAY_STATUS');
    const body=await replay.text();
    requireCheck(body.includes('data-replay="true"')&&body.includes('data-gone="true"')&&body.includes('data-version-result="'+nextManualId+'"'),'DELETE_REPLAY_GONE');
    const after=await observe();requireCheck(equal(before.pages,after.pages)&&before.receipts.length===after.receipts.length&&before.versionAuditCount===after.versionAuditCount,'DELETE_REPLAY_MUTATED');
    return {consumedGone:true,noSecondDeletion:true};
  });
  await check('VH-010-011',async()=>{
    const summary=[];
    for(const who of [owner,employee]){
      const before=await observe();await read(who,seed.stableIds[0]);
      await clickSubmit(who,who.page.locator('form[data-restore-prepare]'));
      const fields=await who.page.locator('[data-restore-field]').evaluateAll(nodes=>nodes.map(node=>node.dataset.restoreField).sort());
      const expected=who===owner?['description','embedded_images','h1','indexing_allowed','intro_text','layout','main_image','main_text','preview_image','price','title']:['intro_text','main_text'];
      requireCheck(equal(fields,expected),'RESTORE_FIELDS');
      const prepared=await observe();assertCurrent(before,prepared);
      requireCheck(equal(before.pins,prepared.pins)&&before.stages.length===prepared.stages.length,'PREPARE_CREATED_HOLD');
      const form=who.page.locator('form[data-restore-stage]');
      await form.locator('[name=confirm_input_replacement]').check();
      const replayFields=await formFields(form);
      await clickSubmit(who,form);
      const stageId=await who.page.locator('[data-restore-staged]').getAttribute('data-restore-staged');
      const held=await observe();assertCurrent(before,held);
      requireCheck(held.stages.find(s=>s.id===stageId)?.status==='held','STAGE_NOT_HELD');
      requireCheck(held.pins.filter(p=>p.holderId===stageId).length===2,'STAGE_PINS');
      const cancelForm=who.page.locator('form[data-stage-cancel]'),cancelFields=await formFields(cancelForm);
      const wrongActor=who===owner?employee:owner;
      const deniedCancel=await post(wrongActor,base+'stages/'+stageId+'/cancel/',{generation:cancelFields.generation,operation_id:crypto.randomUUID(),csrfmiddlewaretoken:await csrf(wrongActor)});
      requireCheck(deniedCancel.status()===403,'FOREIGN_STAGE_CANCEL_ALLOWED');
      requireCheck((await observe()).stages.find(s=>s.id===stageId)?.status==='held','FOREIGN_STAGE_CANCEL_CHANGED_HOLD');
      await clickSubmit(who,cancelForm);
      const released=await observe();assertCurrent(before,released);
      requireCheck(released.stages.find(s=>s.id===stageId)?.status==='released'&&!released.pins.some(p=>p.holderId===stageId),'STAGE_CANCEL_HOLDS');
      requireCheck(equal(before.pins,released.pins),'CANCEL_REMOVED_FOREIGN_HOLD');
      const replay=await post(who,versionPath(seed.stableIds[0],'restore/stage/'),replayFields);
      requireCheck(replay.status()===200,'STAGE_TERMINAL_REPLAY_STATUS');
      const terminal=await replay.text();
      requireCheck(terminal.includes('data-stage-status="released"')&&!terminal.includes('data-stage-field=')&&!terminal.includes('data-restore-staged='),'STAGE_TERMINAL_REEXPOSED_CANDIDATE');
      const cancelReplay=await post(who,base+'stages/'+stageId+'/cancel/',cancelFields);
      requireCheck(cancelReplay.status()===200,'CANCEL_REPLAY_STATUS');
      summary.push({actor:who===owner?'owner':'assigned',stageId,fields,cancelled:true,terminalReplayWithoutCandidate:true});
    }
    return {stages:summary,noPublish:true};
  });
  await check('VH-012',async()=>{
    const state=await observe(),asset=state.assets.find(a=>a.id===seed.assetIds[0]),draftAsset=state.assets.find(a=>a.id===seed.assetIds[1]),unreferenced=state.assets.find(a=>a.id===seed.assetIds[2]);
    for(const file of asset.files){
      const path=versionPath(seed.stableIds[0],'files/'+file.id+'/');
      for(const who of [owner,employee]){
        const response=await get(who,path);
        if(file.kind==='private-source'){requireCheck(response.status()===404,'CONTEXT_PRIVATE_SOURCE');continue;}
        requireCheck(response.status()===200,'CONTEXT_DERIVATIVE_STATUS');await privateHeaders(response);
        requireCheck(response.headers()['content-type']?.split(';')[0]==='image/webp'&&response.headers()['x-content-type-options']==='nosniff','CONTEXT_HEADERS');
        const bytes=await response.body();requireCheck(bytes.length===file.physical.byte_size&&crypto.createHash('sha256').update(bytes).digest('hex')===file.physical.sha256,'CONTEXT_HTTP_FS_MISMATCH');
      }
      requireCheck((await get(other,path)).status()===403&&(await get(visitor,path)).status()===401,'CONTEXT_OTHER_VISITOR');
    }
    for(const asset of [draftAsset,unreferenced]){
      const file=asset.files.find(f=>f.kind==='preview');
      requireCheck((await get(employee,versionPath(seed.stableIds[0],'files/'+file.id+'/'))).status()===404,'UNREFERENCED_CONTEXT_FILE_EXPOSED');
    }
    const preview=asset.files.find(f=>f.kind==='preview');
    requireCheck((await get(employee,'/manage/media/files/'+preview.id+'/')).status()===403,'MEDIA_OWNER_GATE_WEAKENED');
    await read(employee,seed.stableIds[0]);
    const image=employee.page.locator('[data-version-file-id="'+preview.id+'"] img');
    await image.scrollIntoViewIfNeeded();
    await image.evaluate(img=>img.decode());
    requireCheck(await image.evaluate(img=>img.naturalWidth===100&&img.naturalHeight===50),'HISTORY_IMAGE_BROWSER_DECODE');
    return {memberBytesMatchFs:true,assignedEmployeeAllowed:true,draftUnreferencedSourceDenied:true,mediaOwnerGatePreserved:true};
  });
  await check('VH-013',async()=>{
    const state=await observe();assertPhysical(initial,state);
    requireCheck(state.assets.find(a=>a.id===seed.assetIds[0]).usageCount>0&&state.assets.find(a=>a.id===seed.assetIds[1]).usageCount>0&&state.assets.find(a=>a.id===seed.assetIds[2]).usageCount===0,'REAL_MEDIA_REFERENCE_COUNTS');
    requireCheck(state.secretHashesAndSessionIdsAbsent===true,'LEDGER_SECRET_CHECK');
    return {physicalBytesUnchanged:true,currentHistoryStableDraftReferences:true,unreferencedControl:true};
  });
  await check('VH-014',async()=>{
    await owner.page.goto(safe(base+'manual/prepare/'));const fields=await formFields(owner.page.locator('form[data-manual-create]'));
    const before=await observe();
    requireCheck((await get(owner,base+'manual/create/')).status()===405,'MANUAL_CREATE_GET');
    requireCheck((await post(owner,base+'manual/create/',{...fields,payload:'arbitrary writer attempt'})).status()===400,'GENERIC_PAYLOAD_ACCEPTED');
    const forged={...fields,csrfmiddlewaretoken:'forged'};
    requireCheck((await post(owner,base+'manual/create/',forged)).status()===403,'FORGED_CSRF_ACCEPTED');
    const after=await observe();requireCheck(equal(before.pages,after.pages)&&before.receipts.length===after.receipts.length,'INVALID_FIELDS_MUTATED');
    assertCurrent(before,after);return {noGenericWriter:true,getAndCsrfDenied:true};
  });
  await check('VH-015',async()=>{
    for(const [label,width]of [['desktop',1280],['mobile',390]]){
      await owner.page.setViewportSize({width,height:900});await owner.page.goto(safe(base));
      requireCheck(await owner.page.locator('input[type=password]').count()===0,'PASSWORD_SCREENSHOT_PROHIBITED');
      requireCheck(await owner.page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'HISTORY_HORIZONTAL_OVERFLOW');
      await owner.page.screenshot({path:'/results/'+label+'.png',fullPage:true});
    }
    return {widths:[1280,390],screenshots:['desktop.png','mobile.png']};
  });
  await check('VH-016',async()=>{
    const state=await observe();await owner.page.goto(safe(base));
    for(const row of pageState(state,pageId).versions){
      const time=owner.page.locator('[data-version-id="'+row.id+'"] [data-version-saved-at]');
      requireCheck(Date.parse(await time.getAttribute('data-version-saved-at'))===Date.parse(row.createdAt),'SAVED_INSTANT');
      const parts=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Moscow',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(row.createdAt)).filter(p=>p.type!=='literal').map(p=>[p.type,p.value]));
      const text=(await time.textContent()).trim();
      requireCheck(text.includes(parts.day+'.'+parts.month+'.'+parts.year+' '+parts.hour+':'+parts.minute+':'+parts.second)&&text.includes('Europe/Moscow'),'VISIBLE_MOSCOW_TIME');
    }
    const final=revision(state,pageId,manualId),original=revision(manualCreationState,pageId,manualId);
    requireCheck(final.createdAt===original.createdAt&&final.authorId===original.authorId&&new Date(final.metadata.manualDate).getUTCFullYear()===2099,'MANUAL_ACTUAL_TIME_INDEPENDENCE');
    return {actualUtcAndMoscowDisplay:true,manual1960Then2099Separate:true};
  });
  output({kind:'result',status:'PASS',passed,notChecked:['Engine commit/rollback/concurrency tested separately with PostgreSQL; seed is not browser save',
    'Full DEV07 rich editor/unsaved input, DEV08 public rendering, DEV29 publication/URL and HeaderFooter',
    'Audit export/midnight-clock profile, unknown historical schema Stable/restore and lifecycle beyond this bounded HTTP corpus']});
}catch(error){
  output({kind:'result',status:'FAIL',failedAt:current,code:/^[A-Z0-9_-]{1,100}$/u.test(error.message??'')?error.message:'BROWSER_OR_PROTOCOL_ERROR',passed});
  process.exitCode=1;
}finally{
  for(const context of contexts)await context.close().catch(()=>{});
  await browser?.close().catch(()=>{});input.close();process.stdin.destroy();
}
