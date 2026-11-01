// Actual Chromium/HTTP only. No Docker socket, DB credentials or control URL.
import fs from 'node:fs';
import crypto from 'node:crypto';
import readline from 'node:readline';
import {chromium} from '/tests/node_modules/playwright/index.mjs';
const seed=JSON.parse(fs.readFileSync('/private/shared-seed.json','utf8'));
const origin='http://host.docker.internal:8767',groups=[],contexts=[],waiters=new Map();
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
const ensure=(condition,code)=>{if(!condition)throw new Error(code);};
const output=value=>process.stdout.write(JSON.stringify(value)+'\n');
let serial=0,current='START',browser,pageErrors=0,externalDenied=0;
const privateTokens=new Set([seed.password]),visitedUrls=[];
const channel=readline.createInterface({input:process.stdin,terminal:false});
channel.on('line',line=>{
  try{const value=JSON.parse(line),pending=waiters.get(value.id);if(value.kind!=='observation'||!pending)throw new Error();
    waiters.delete(value.id);clearTimeout(pending.timer);value.error?pending.reject(new Error('HOST_OBSERVER_FAILED')):pending.resolve(value.value);
  }catch{process.exitCode=1;}
});
function observe(kind='observe'){
  return new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{waiters.delete(id);reject(new Error('HOST_OBSERVER_TIMEOUT'));},30000);
    waiters.set(id,{resolve,reject,timer});output({kind:'observe',id,caseId:current,operation:kind});});
}
const markup=(kind,canary)=>seed.markup[kind].replace('RSV-UI-SEED',canary);
const status=page=>page.locator('[data-editor-status]');
const input=page=>page.locator('#shared-html');
async function waitStatus(page,text){await status(page).filter({hasText:text}).waitFor({timeout:30000});}
async function open(kind){
  const context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});contexts.push(context);
  await context.route('**/*',route=>{if(new URL(route.request().url()).origin===origin)return route.continue();externalDenied++;return route.abort();});
  const page=await context.newPage();page.on('pageerror',()=>{pageErrors++;});
  page.on('request',request=>{
    visitedUrls.push(request.url());
    try{const body=JSON.parse(request.postData()||'null');if(typeof body?.checkReceipt==='string')privateTokens.add(body.checkReceipt);}catch{}
  });
  page.on('dialog',dialog=>dialog.type()==='beforeunload'?dialog.dismiss():dialog.accept());
  await page.goto(origin+'/manage/login/');await page.locator('[name=username]').fill(seed.username);await page.locator('[name=password]').fill(seed.password);
  await Promise.all([page.waitForURL(origin+'/manage/'),page.locator('form button').click()]);
  await page.goto(origin+'/manage/shared/'+kind+'/edit/');await input(page).waitFor();return page;
}
async function check(page){await page.locator('[data-action=check]').click();await waitStatus(page,'Проверка пройдена');}
async function save(page,action='apply'){
  await page.locator('[data-action='+action+']').click();
  await waitStatus(page,action==='draft'?'Черновик сохранён отдельно':'Изменения сохранены');
}
function oneMutation(before,after,kind,html){
  ensure(after.blocks[kind].count===before.blocks[kind].count+1,'ONE_ACTUAL_VERSION_REQUIRED');
  ensure(after.blocks[kind].sha256===hash(html),'ACTUAL_FILE_CONTENT_MISMATCH');
  const other=kind==='header'?'footer':'header';ensure(after.blocks[other].current===before.blocks[other].current,'OTHER_BLOCK_CHANGED');
  ensure(after.journalCount===0,'UNRELEASED_BOOK_AFTER_SUCCESS');
  ensure(after.budget.usedBytes<=after.budget.limitBytes,'ACTUAL_BUDGET_EXCEEDED');
}
async function noStorageLeak(page,canary){
  const tokens=[canary,...privateTokens];
  const safe=await page.evaluate(({tokens})=>{
    const entries=[...Object.entries(localStorage),...Object.entries(sessionStorage)].flat().join('|');
    const secrets=[...tokens,document.querySelector('[name=csrfmiddlewaretoken]')?.value].filter(Boolean);
    return secrets.every(token=>!decodeURIComponent(location.href).includes(token)&&!entries.includes(token));
  },{tokens});ensure(safe&&visitedUrls.every(url=>tokens.every(token=>!decodeURIComponent(url).includes(token))),'URL_OR_WEB_STORAGE_LEAK');
}
async function dirtyNavigation(page,expected){
  let noticed=false;const listener=dialog=>{if(dialog.type()==='beforeunload')noticed=true;};page.on('dialog',listener);
  await page.reload({timeout:5000}).catch(()=>{});page.off('dialog',listener);
  ensure(noticed&&await input(page).inputValue()===expected,'NATIVE_DIRTY_GUARD_LOST_INPUT');
}
async function lostResponse(page){
  let capture;
  const path=origin+'/manage/shared/header/apply/';
  await page.route(path+'**',async route=>{
    capture={hash:hash(route.request().postData()||''),operationId:JSON.parse(route.request().postData()).operationId};
    const response=await route.fetch();ensure(response.ok(),'REAL_APPLY_FAILED_BEFORE_ABORT');await response.body();
    await route.abort('failed');
  },{times:1});
  await page.locator('[data-action=apply]').click();await page.locator('[data-retry-intent]').waitFor({state:'visible'});
  ensure(capture,'LOST_RESPONSE_NOT_REACHED');return capture;
}
async function retry(page,captured){
  let repeated;
  const listener=request=>{if(new URL(request.url()).pathname==='/manage/shared/header/apply/')repeated={hash:hash(request.postData()||''),operationId:JSON.parse(request.postData()).operationId};};
  page.on('request',listener);await page.locator('[data-retry-intent]').click();
  await page.locator('[data-retry-intent]').waitFor({state:'hidden'});page.off('request',listener);
  ensure(repeated&&repeated.hash===captured.hash&&repeated.operationId===captured.operationId,'MANUAL_RETRY_CHANGED_INTENT');
}
try{
  browser=await chromium.launch({headless:true});
  current='RSV-UI-001';
  {
    const page=await open('header'),a=markup('header','RSV-PENDING-A'),b=markup('header','RSV-PENDING-B');
    await input(page).fill(a);await check(page);const before=await observe();
    let reached,release;const ready=new Promise(resolve=>{reached=resolve;}),held=new Promise(resolve=>{release=resolve;});
    await page.route(origin+'/manage/shared/header/apply/**',async route=>{const response=await route.fetch();ensure(response.ok(),'PENDING_SERVER_FAILED');reached();await held;await route.fulfill({response});},{times:1});
    let readyTimer;
    try{await page.locator('[data-action=apply]').click();await Promise.race([ready,new Promise((_,reject)=>{readyTimer=setTimeout(()=>reject(new Error('PENDING_RESPONSE_TIMEOUT')),30000);})]);
      await input(page).fill(b);
    }finally{clearTimeout(readyTimer);release();}
    await waitStatus(page,'Новые изменения остаются');const after=await observe();oneMutation(before,after,'header',a);
    ensure(await input(page).inputValue()===b,'PENDING_ACK_REPLACED_NEW_TEXT');await dirtyNavigation(page,b);
    await check(page);await save(page);oneMutation(after,await observe(),'header',b);await noStorageLeak(page,'RSV-PENDING-B');
    groups.push({id:current,pass:true,pendingEdit:true,nativeDirtyGuard:true,freshSecondSave:true});
  }
  current='RSV-UI-002';
  {
    const page=await open('header'),html=markup('header','RSV-UNKNOWN-A');await input(page).fill(html);await check(page);const before=await observe();
    const captured=await lostResponse(page),committed=await observe();oneMutation(before,committed,'header',html);
    await retry(page,captured);await waitStatus(page,'Изменения сохранены');const replayed=await observe();
    ensure(replayed.blocks.header.current===committed.blocks.header.current&&replayed.receiptCount===committed.receiptCount,'RETRY_DUPLICATED_COMMIT');
    groups.push({id:current,pass:true,transportAbortedAfterServerResponse:true,exactManualRetry:true});
  }
  current='RSV-UI-003';
  {
    const page=await open('header'),a=markup('header','RSV-RETRY-A'),b=markup('header','RSV-RETRY-B');
    await input(page).fill(a);await check(page);const captured=await lostResponse(page),committed=await observe();
    await input(page).fill(b);await page.locator('[data-action=check]').click();await waitStatus(page,'Результат прежней отправки');
    await retry(page,captured);await waitStatus(page,'Новые изменения остаются');
    ensure(await input(page).inputValue()===b,'RETRY_ACK_REPLACED_NEW_TEXT');
    const replayed=await observe();ensure(replayed.blocks.header.current===committed.blocks.header.current,'RETRY_CREATED_VERSION');
    await dirtyNavigation(page,b);await check(page);await save(page);oneMutation(replayed,await observe(),'header',b);
    groups.push({id:current,pass:true,changedTextRetained:true,oldIntentOnly:true});
  }
  current='RSV-UI-004';
  {
    const page=await open('footer'),html=markup('footer','RSV-FOOTER-DRAFT');await input(page).fill(html);await check(page);
    const before=await observe();await save(page,'draft');const draft=await observe();
    ensure(draft.blocks.footer.current===before.blocks.footer.current&&draft.blocks.footer.draftRevision===1&&draft.blocks.footer.draftSha256===hash(html),'DRAFT_PUBLISHED_OR_ACK_WRONG');
    await check(page);await save(page);const applied=await observe();oneMutation(before,applied,'footer',html);ensure(applied.blocks.footer.draftId===null,'DRAFT_NOT_CONSUMED');
    await noStorageLeak(page,'RSV-FOOTER-DRAFT');groups.push({id:current,pass:true,realFooterDraftAndApply:true,noStorageLeak:true});
  }
  current='RSV-UI-005';
  {
    const page=await open('header'),html=markup('header','RSV-AUTH-REVOKED');await input(page).fill(html);await check(page);const before=await observe();
    const revoked=await observe('reset');ensure(revoked.generation>before.generation,'AUTH_RESET_NOT_REACHED');
    await page.locator('[data-action=apply]').click();await waitStatus(page,'Сессия завершена');
    const after=await observe();ensure(after.blocks.header.current===before.blocks.header.current&&after.receiptCount===before.receiptCount,'REVOKED_SESSION_MUTATED_CONTENT');
    ensure(await input(page).inputValue()===html,'AUTH_ERROR_LOST_INPUT');await noStorageLeak(page,'RSV-AUTH-REVOKED');
    groups.push({id:current,pass:true,actualAuthGenerationRevoked:true,inputRetained:true});
  }
  ensure(pageErrors===0,'BROWSER_PAGE_ERROR');output({kind:'result',pass:true,groups,pageErrors,externalDenied});
}catch(error){
  const code=typeof error?.message==='string'&&/^[A-Z0-9_]{1,120}$/.test(error.message)?error.message:'SHARED_BROWSER_PROBE_FAILED';
  output({kind:'result',pass:false,groups,failedCase:current,code,pageErrors});process.exitCode=1;
}finally{
  for(const context of contexts)await context.close().catch(()=>{});
  if(browser)await browser.close().catch(()=>{});channel.close();for(const pending of waiters.values())clearTimeout(pending.timer);
}
