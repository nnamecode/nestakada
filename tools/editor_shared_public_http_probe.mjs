// Actual anonymous browser/HTTP observations against the QA-only host.
import fs from 'node:fs';
import readline from 'node:readline';
import {chromium} from '/tests/node_modules/playwright/index.mjs';
const seed=JSON.parse(fs.readFileSync('/private/shared-seed.json','utf8'));
const origin='http://host.docker.internal:8767',publicUrl=origin+'/__shared_public__/';
const groups=[],contexts=[],waiters=new Map(),privateTokens=new Set([seed.password]),visited=[];
const ensure=(value,code)=>{if(!value)throw new Error(code);};
const output=value=>process.stdout.write(JSON.stringify(value)+'\n');
let browser,serial=0,current='START',pageErrors=0,externalDenied=0;
const channel=readline.createInterface({input:process.stdin,terminal:false});
channel.on('line',line=>{try{const value=JSON.parse(line),pending=waiters.get(value.id);
  if(value.kind!=='observation'||!pending)throw new Error();waiters.delete(value.id);clearTimeout(pending.timer);pending.resolve(value.value);
}catch{process.exitCode=1;}});
function observe(operation='observe'){return new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{
  waiters.delete(id);reject(new Error('PUBLIC_OBSERVER_TIMEOUT'));},30000);waiters.set(id,{resolve,reject,timer});
  output({kind:'observe',id,caseId:current,operation});});}
async function context(options={}){
  const value=await browser.newContext({viewport:{width:1440,height:900},serviceWorkers:'block',...options});contexts.push(value);
  await value.route('**/*',route=>{if(new URL(route.request().url()).origin===origin)return route.continue();externalDenied++;return route.abort();});
  return value;
}
function watch(page){page.on('pageerror',()=>{pageErrors++;});
  page.on('dialog',dialog=>dialog.type()==='beforeunload'?dialog.dismiss():dialog.accept());
  page.on('request',request=>{visited.push(request.url());try{const data=JSON.parse(request.postData()||'null');
    if(typeof data?.checkReceipt==='string')privateTokens.add(data.checkReceipt);}catch{}});return page;}
function readonly(before,after){for(const key of ['blocks','receiptCount','jobCount','pinCount','assetManifests','inventoryStamp','sessionCount','authSessionCount'])
  ensure(JSON.stringify(before[key])===JSON.stringify(after[key]),'ANONYMOUS_SHARED_STATE_MUTATION');}
async function checkImages(page){const images=await page.locator('.es-header img,.es-footer img').evaluateAll(nodes=>nodes.map(node=>({
  loaded:node.complete&&node.naturalWidth>0,path:new URL(node.src).pathname})));
  ensure(images.length===5&&images.every(image=>image.loaded&&image.path==='/__shared_public__/media/'+seed.assetFiles.main+'/'),'PUBLIC_ACTUAL_MEDIA_NOT_LOADED');}
async function privacy(page){const forbidden=[...privateTokens];const result=await page.evaluate(forbidden=>{
  const stored=[...Object.entries(localStorage),...Object.entries(sessionStorage)].flat().join('|');
  return forbidden.every(value=>!stored.includes(value)&&!decodeURIComponent(location.href).includes(value));},forbidden);
  ensure(result&&visited.every(url=>forbidden.every(value=>!decodeURIComponent(url).includes(value))),'PUBLIC_PRIVATE_STORAGE_OR_URL_LEAK');}
async function owner(){const own=await context(),page=watch(await own.newPage());await page.goto(origin+'/manage/login/');
  await page.locator('[name=username]').fill(seed.username);await page.locator('[name=password]').fill(seed.password);
  await Promise.all([page.waitForURL(origin+'/manage/'),page.locator('form button').click()]);
  await page.goto(origin+'/manage/shared/header/edit/');return page;}
try{
  browser=await chromium.launch({headless:true});
  current='PUB-UI-001';
  const anon=await context();await anon.addInitScript(()=>{window.__publicCspViolations=0;
    document.addEventListener('securitypolicyviolation',()=>{window.__publicCspViolations++;});});
  const page=watch(await anon.newPage()),before=await observe();
  const response=await page.goto(publicUrl);ensure(response?.status()===200,'PUBLIC_HOST_NOT_200');
  const headers=response.headers(),etag=headers.etag;ensure(typeof etag==='string'&&headers['cache-control']==='no-cache'&&!headers['set-cookie'],'PUBLIC_VALIDATORS_OR_COOKIE_INVALID');
  await page.locator('.es-header[data-menu-ready="true"]').waitFor();await page.locator('.es-footer').waitFor();
  await checkImages(page);ensure((await page.locator('#es-nav a').evaluateAll(nodes=>nodes.map(node=>node.getAttribute('href')))).join()===seed.navTargets.join(),'PUBLIC_EXACT_NAV_URLS_CHANGED');
  const conditional=await anon.request.get(publicUrl,{headers:{'If-None-Match':etag}});
  ensure(conditional.status()===304&&(await conditional.body()).length===0,'PUBLIC_UNCHANGED_NOT_304');
  readonly(before,await observe());ensure((await anon.cookies()).length===0,'PUBLIC_ANONYMOUS_COOKIE_CREATED');
  groups.push({id:current,pass:true,currentDomAndReadyMedia:true,exactFixtureNav:true,conditional304:true,noAnonymousStateWrites:true});

  current='PUB-UI-002';
  const widths=[];
  for(const width of [320,390,768,1024,1440]){
    await page.setViewportSize({width,height:900});
    const button=page.locator('.es-menu-button'),nav=page.locator('#es-nav');
    if(width<=800){
      await button.click();ensure(await button.getAttribute('aria-expanded')==='true'&&await nav.isVisible(),'MOBILE_MENU_NOT_OPEN');
      await page.keyboard.press('Escape');ensure(await button.getAttribute('aria-expanded')==='false'&&!await nav.isVisible(),'MOBILE_ESCAPE_NOT_CLOSED');
      await button.focus();await button.press('Enter');
      ensure(await page.evaluate(()=>document.activeElement===document.querySelector('#es-nav a')),'KEYBOARD_MENU_FOCUS_NOT_ENTERED');
      await page.keyboard.press('Escape');ensure(await button.evaluate(node=>document.activeElement===node),'MENU_FOCUS_NOT_RESTORED');
    }else ensure(await nav.isVisible(),'DESKTOP_NAV_HIDDEN');
    const docWidth=await page.evaluate(()=>document.documentElement.scrollWidth);
    ensure(docWidth<=width,'PUBLIC_HORIZONTAL_OVERFLOW');widths.push({width,documentWidth:docWidth});await checkImages(page);
    if(width===390||width===1440){ensure(page.url()===publicUrl,'ANONYMOUS_SCREENSHOT_SCOPE');
      await page.screenshot({path:'/evidence/public-'+width+'.png',fullPage:false});}
  }
  const noJs=await context({javaScriptEnabled:false,viewport:{width:390,height:900}}),plain=watch(await noJs.newPage());
  await plain.goto(publicUrl);ensure(await plain.locator('#es-nav').isVisible()&&await plain.locator('#es-nav a').count()===6,'NO_JS_NAV_UNAVAILABLE');
  ensure(!await plain.locator('.es-menu-button').isVisible(),'NO_JS_INERT_MENU_BUTTON');await checkImages(plain);
  ensure(await page.evaluate(()=>window.__publicCspViolations)===0,'PUBLIC_CSP_VIOLATION');
  groups.push({id:current,pass:true,widths,mobileKeyboardAndEscape:true,noJsLinksAvailable:true,cspViolations:0});

  current='PUB-UI-003';
  const editor=await owner(),prior=await observe();
  const changed=seed.markup.header.replaceAll('+70000000001','+70000000002').replace('PUB-UI-SEED','PUB-UI-UPDATED');
  await editor.locator('#shared-html').fill(changed);await editor.locator('[data-action=check]').click();
  await editor.locator('[data-editor-status]').filter({hasText:'Проверка пройдена'}).waitFor();
  await editor.locator('[data-action=apply]').click();await editor.locator('[data-editor-status]').filter({hasText:'Изменения сохранены'}).waitFor();
  const committed=await observe();ensure(committed.blocks.header.count===prior.blocks.header.count+1&&committed.blocks.footer.current===prior.blocks.footer.current,'PUBLIC_OWNER_APPLY_DOMAIN_WRONG');
  const updated=await anon.request.get(publicUrl,{headers:{'If-None-Match':etag}});
  ensure(updated.status()===200&&updated.headers().etag!==etag,'PUBLIC_SHARED_CHANGE_OLD_304');
  await page.goto(publicUrl);ensure(await page.locator('.es-header-phone strong').innerText()==='+70000000002','PUBLIC_LITERAL_PHONE_NOT_UPDATED');
  ensure((await page.locator('.es-header-address span').innerText()).includes('PUB-UI-UPDATED'),'PUBLIC_CANARY_NOT_CURRENT');
  await checkImages(page);await privacy(editor);await privacy(page);
  groups.push({id:current,pass:true,actualOwnerSave:true,newCurrentPhoneInAnonymousDom:true,otherBlockPreserved:true,etagChanged:true});

  current='PUB-UI-004';
  const navBefore=await observe(),oldResponse=await anon.request.get(publicUrl),oldTag=oldResponse.headers().etag;
  await observe('rename');const navChanged=await anon.request.get(publicUrl,{headers:{'If-None-Match':oldTag}});
  ensure(navChanged.status()===200&&navChanged.headers().etag!==oldTag,'PUBLIC_NAV_CHANGE_OLD_304');
  await page.goto(publicUrl);const renamedLink=page.locator('#es-nav a').first(),renamedLabel='Услуги — проверка обновления';
  ensure((await renamedLink.textContent())===renamedLabel,'PUBLIC_FRESH_NAV_LABEL_MISSING');
  ensure((await renamedLink.innerText())===renamedLabel.toLocaleUpperCase('ru-RU'),'PUBLIC_RENDERED_NAV_CASE_WRONG');
  ensure((await page.locator('#es-nav a').first().getAttribute('href'))===seed.navTargets[0],'PUBLIC_NAV_TARGET_REWRITTEN');
  for(const kind of ['private-source','preview']){
    const denied=await anon.request.get(origin+'/__shared_public__/media/'+seed.assetFiles[kind]+'/',{headers:{'If-None-Match':'*'}});
    ensure([403,404].includes(denied.status())&&denied.headers()['cache-control']?.includes('no-store'),'PRIVATE_MEDIA_BECAME_PUBLIC');
  }
  const head=await anon.request.head(publicUrl);ensure(head.status()===200&&(await head.body()).length===0&&head.headers().etag===navChanged.headers().etag,'PUBLIC_HEAD_INVALID');
  readonly(navBefore,await observe());await privacy(page);
  ensure(pageErrors===0&&externalDenied===0,'PUBLIC_BROWSER_OR_EXTERNAL_NETWORK_ERROR');
  ensure(await page.evaluate(()=>window.__publicCspViolations)===0,'PUBLIC_FINAL_CSP_VIOLATION');
  groups.push({id:current,pass:true,realFixtureRenameReflected:true,noPrivateOrPreviewMedia:true,headCorrect:true,noExtraWrites:true});
  output({kind:'result',pass:true,groups,pageErrors,externalDenied});
}catch(error){output({kind:'result',pass:false,groups,failedCase:current,
  code:typeof error?.message==='string'&&/^[A-Z0-9_]{1,120}$/.test(error.message)?error.message:'PUBLIC_BROWSER_PROBE_FAILED',pageErrors,externalDenied});process.exitCode=1;
}finally{for(const value of contexts)await value.close().catch(()=>{});if(browser)await browser.close().catch(()=>{});
  channel.close();for(const pending of waiters.values())clearTimeout(pending.timer);}
