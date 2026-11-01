// Native owner flow; observer is a closed host protocol, never a product endpoint.
import fs from 'node:fs';
import readline from 'node:readline';
import {chromium} from '/tests/node_modules/playwright/index.mjs';
const seed=JSON.parse(fs.readFileSync('/private/shared-seed.json','utf8'));
const origin='http://host.docker.internal:8767',groups=[],contexts=[],waiters=new Map();
const tokens=new Set([seed.password]),urls=[];
const ensure=(value,code)=>{if(!value)throw new Error(code);};
const output=value=>process.stdout.write(JSON.stringify(value)+'\n');
let browser,serial=0,current='START',pageErrors=0;
const channel=readline.createInterface({input:process.stdin,terminal:false});
channel.on('line',line=>{try{const value=JSON.parse(line),pending=waiters.get(value.id);
  if(value.kind!=='observation'||!pending)throw new Error();waiters.delete(value.id);clearTimeout(pending.timer);pending.resolve(value.value);
}catch{process.exitCode=1;}});
function observe(){return new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{
  waiters.delete(id);reject(new Error('CLEANUP_OBSERVER_TIMEOUT'));},30000);waiters.set(id,{resolve,reject,timer});
  output({kind:'observe',id,caseId:current,operation:'observe'});});}
function watch(page){
  page.on('pageerror',()=>{pageErrors++;});
  page.on('dialog',dialog=>dialog.type()==='beforeunload'?dialog.dismiss():dialog.accept());
  page.on('request',request=>{urls.push(request.url());try{const value=JSON.parse(request.postData()||'null');
    if(typeof value?.checkReceipt==='string')tokens.add(value.checkReceipt);}catch{}});
  return page;
}
async function open(){
  const context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});contexts.push(context);
  await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  const page=watch(await context.newPage());await page.goto(origin+'/manage/login/');
  await page.locator('[name=username]').fill(seed.username);await page.locator('[name=password]').fill(seed.password);
  await Promise.all([page.waitForURL(origin+'/manage/'),page.locator('form button').click()]);
  await page.goto(origin+'/manage/shared/header/edit/');await page.locator('#shared-html').waitFor();return page;
}
const markup=canary=>seed.markup.header.replace('RSV-UI-SEED',canary);
async function publish(page,canary){await page.locator('#shared-html').fill(markup(canary));
  await page.locator('[data-action=check]').click();await page.locator('[data-editor-status]').filter({hasText:'Проверка пройдена'}).waitFor();
  await page.locator('[data-action=apply]').click();await page.locator('[data-editor-status]').filter({hasText:'Изменения сохранены'}).waitFor();return observe();}
async function tab(page,url){const next=watch(await page.context().newPage());await next.goto(origin+url);return next;}
const previewUrl=id=>'/manage/shared/header/cleanup/'+id+'/';
function domain(state){return JSON.stringify({blocks:state.blocks,receipts:state.receiptCount,
  journal:state.journalCount,jobs:state.cleanupJobs,assets:state.assetManifests});}
async function rememberFormTokens(page){for(const value of await page.locator('[name=confirmation], [name=csrfmiddlewaretoken]').evaluateAll(
  elements=>elements.map(element=>element.value).filter(value=>typeof value==='string'&&value.length>0)))tokens.add(value);}
async function fillConfirmation(page){const form=page.locator('form[data-cleanup-form]');await form.waitFor();await rememberFormTokens(page);
  const operationId=await form.locator('[name=operationId]').inputValue();
  await form.locator('[name=password]').fill(seed.password);await form.locator('[name=confirmed]').check();return {form,operationId};}
function oneDeletion(before,after,target,operationId){
  ensure(after.blocks.header.current===before.blocks.header.current&&after.blocks.footer.current===before.blocks.footer.current,'CLEANUP_CHANGED_CURRENT');
  ensure(after.blocks.header.count===before.blocks.header.count-1,'CLEANUP_NOT_ONE_VERSION');
  ensure(after.receiptCount===before.receiptCount,'CLEANUP_REMOVED_SAVE_RECEIPT');
  ensure(after.cleanupJobs.length===before.cleanupJobs.length+1,'CLEANUP_NOT_ONE_JOB');
  const job=after.cleanupJobs.find(value=>value.id===operationId);
  ensure(job&&job.target===target&&job.phase==='complete'&&!job.filePresent&&!job.targetExists&&job.targetUsageCount===0,'CLEANUP_ACTUAL_JOB_NOT_COMPLETE');
  ensure(JSON.stringify(after.assetManifests)===JSON.stringify(before.assetManifests),'CLEANUP_CHANGED_ASSET_BYTES');
  ensure(after.budget.usedBytes<=after.budget.limitBytes,'CLEANUP_EXCEEDED_CAP');
}
async function privacy(page){const forbidden=[...tokens,'LC-UNSAVED-TEXT'];
  const clean=await page.evaluate(forbidden=>{const stored=[...Object.entries(localStorage),...Object.entries(sessionStorage)].flat().join('|');
    return forbidden.every(value=>!stored.includes(value)&&!decodeURIComponent(location.href).includes(value));},forbidden);
  ensure(clean&&urls.every(url=>forbidden.every(value=>!decodeURIComponent(url).includes(value))),'CLEANUP_PRIVATE_STORAGE_OR_URL_LEAK');}
try{
  browser=await chromium.launch({headless:true});
  current='LC-UI-001';
  const editor=await open();const old=await publish(editor,'LC-OLD-A'),target=old.blocks.header.current;
  const latest=await publish(editor,'LC-CURRENT-B');
  const protectedPage=await tab(editor,previewUrl(latest.blocks.header.current));await protectedPage.locator('[data-cleanup-preview]').waitFor();
  ensure(await protectedPage.locator('form[data-cleanup-form]').count()===0,'CURRENT_CLEANUP_FORM_AVAILABLE');
  const protectedText=await protectedPage.locator('[data-cleanup-preview]').innerText();
  ensure(protectedText.includes('Это текущая версия.')&&!protectedText.includes('CURRENT'),'CURRENT_REASON_NOT_READABLE_RUSSIAN');
  const page=await tab(editor,previewUrl(target));await page.locator('[data-cleanup-preview]').waitFor();
  ensure(await page.locator('form[data-cleanup-form]').count()===1,'OLD_VERSION_PREVIEW_MISSING');
  await rememberFormTokens(page);
  await page.goto(origin+'/manage/shared/header/history/');ensure(domain(await observe())===domain(latest),'PREVIEW_OR_CANCEL_MUTATED_DOMAIN');
  groups.push({id:current,pass:true,currentProtected:true,oldPreviewAndCancelReadOnly:true});

  current='LC-UI-002';
  const unsaved=markup('LC-UNSAVED-TEXT');await editor.locator('#shared-html').fill(unsaved);
  await page.goto(origin+previewUrl(target));const before=await observe(),confirmation=await fillConfirmation(page);
  await confirmation.form.locator('[type=submit]').click();await page.locator('[data-cleanup-status]').waitFor();
  const after=await observe();oneDeletion(before,after,target,confirmation.operationId);
  ensure(await page.locator('[data-cleanup-status]').getAttribute('data-job-id')===confirmation.operationId,'CLEANUP_STATUS_ID_MISMATCH');
  ensure(await editor.locator('#shared-html').inputValue()===unsaved,'CLEANUP_LOST_EDITOR_TEXT');
  await page.reload();ensure(domain(await observe())===domain(after),'STATUS_GET_REPEATED_DELETE');await privacy(page);await privacy(editor);
  groups.push({id:current,pass:true,oneActualVersionAndFile:true,assetsUnchanged:true,editorInputRetained:true});

  current='LC-UI-003';
  const second=await open(),saved=await publish(second,'LC-LOST-RESPONSE-C'),lostTarget=saved.blocks.header.current;
  await publish(second,'LC-CURRENT-D');const cleanup=await tab(second,previewUrl(lostTarget)),lostBefore=await observe();
  const pending=await fillConfirmation(cleanup);let reachedResolve,reached=false;
  const delivered=new Promise(resolve=>{reachedResolve=resolve;});
  await cleanup.route(origin+previewUrl(lostTarget),async route=>{
    if(route.request().method()!=='POST')return route.continue();
    const response=await route.fetch();ensure(response.ok(),'CLEANUP_SERVER_REFUSED_BEFORE_RESPONSE_LOSS');await response.body();
    reached=true;await route.abort('failed');reachedResolve();
  },{times:1});
  let timer;try{const clicked=pending.form.locator('[type=submit]').click().catch(()=>{});
    await Promise.race([delivered,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('CLEANUP_RESPONSE_LOSS_TIMEOUT')),30000);})]);await clicked;
  }finally{clearTimeout(timer);}
  ensure(reached,'CLEANUP_RESPONSE_LOSS_NOT_REACHED');const lostAfter=await observe();oneDeletion(lostBefore,lostAfter,lostTarget,pending.operationId);
  await cleanup.goto(origin+'/manage/shared/header/history/');
  await cleanup.locator('[data-cleanup-job="'+pending.operationId+'"]').click();
  await cleanup.locator('[data-cleanup-status]').waitFor();
  ensure(domain(await observe())===domain(lostAfter),'LOST_RESPONSE_STATUS_DUPLICATED_CLEANUP');await privacy(cleanup);
  groups.push({id:current,pass:true,actualCommitBeforeTransportAbort:true,sameJobAfterManualNavigation:true});

  current='LC-UI-004';
  const known=lostAfter.receiptIds[0];ensure(known,'KNOWN_RECEIPT_REQUIRED');const baseline=await observe();
  const diagnostics=await tab(second,'/manage/shared/header/diagnostics/'+known+'/');
  ensure((await diagnostics.locator('body').innerText()).includes(known),'DIAGNOSTICS_NOT_ACTUAL_OPERATION');
  ensure(domain(await observe())===domain(baseline),'DIAGNOSTICS_GET_MUTATED_DOMAIN');await privacy(diagnostics);
  ensure(pageErrors===0,'CLEANUP_BROWSER_PAGE_ERROR');groups.push({id:current,pass:true,knownOperationReadOnly:true,noPrivateStorageOrUrl:true});
  output({kind:'result',pass:true,groups,pageErrors});
}catch(error){output({kind:'result',pass:false,groups,failedCase:current,
  code:typeof error?.message==='string'&&/^[A-Z0-9_]{1,120}$/.test(error.message)?error.message:'CLEANUP_BROWSER_PROBE_FAILED',pageErrors});process.exitCode=1;
}finally{for(const context of contexts)await context.close().catch(()=>{});if(browser)await browser.close().catch(()=>{});
  channel.close();for(const pending of waiters.values())clearTimeout(pending.timer);}
