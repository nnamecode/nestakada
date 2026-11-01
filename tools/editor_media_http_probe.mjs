// E2 bounded real browser/HTTP proof. Synthetic inputs only, no control HTTP API.
import fs from 'node:fs';
import crypto from 'node:crypto';
import readline from 'node:readline';
import {chromium} from '/tests/node_modules/playwright/index.mjs';
const origin='http://host.docker.internal:8767',groups=[],contexts=[],pending=new Map();
const output=value=>process.stdout.write(JSON.stringify(value)+'\n');
const ensure=(value,code)=>{if(!value)throw new Error(code);};
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const safe=value=>{ensure(typeof value==='string'&&value.startsWith('/')&&new URL(value,origin).origin===origin,'FIXED_ORIGIN');return new URL(value,origin).href;};
const fixed=value=>typeof value==='string'&&/^[A-Z0-9_]{1,120}$/u.test(value)?value:'MEDIA_BROWSER_PROBE_FAILED';
let current='START',serial=0,browser,diagnosticPage;
const lastResponses=[],pageErrorCodes=[];
const channel=readline.createInterface({input:process.stdin,terminal:false});
channel.on('line',line=>{try{const value=JSON.parse(line),waiter=pending.get(value.id);if(value.kind==='observation'&&waiter){pending.delete(value.id);value.error?waiter.reject(new Error('HOST_OBSERVER_FAILED')):waiter.resolve(value.value);}}catch{process.exitCode=1;}});
function observe(){return new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{pending.delete(id);reject(new Error('OBSERVER_TIMEOUT'));},30000);pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value);},reject:error=>{clearTimeout(timer);reject(error);}});output({kind:'observe',id,caseId:current});});}
const row=(state,id)=>{const result=state.pages.find(value=>value.id===id);ensure(result,'PAGE_OBSERVER_MISSING');return result;};
const asset=(state,id)=>{const result=state.assets.find(value=>value.id===id);ensure(result,'ASSET_OBSERVER_MISSING');return result;};
const part=(state,id,kind)=>{const result=asset(state,id).files.find(value=>value.kind===kind);ensure(result,'FILE_OBSERVER_MISSING');return result;};
const media=(page,field)=>page.locator('[data-editor-media="'+field+'"]');
const action=(page,name)=>page.locator('.es-page-actions [data-editor-action="'+name+'"]');
async function context(){const value=await browser.newContext({viewport:{width:1280,height:900},timezoneId:'UTC'});contexts.push(value);await value.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  value.on('response',async response=>{try{const url=new URL(response.url());if(url.origin!==origin||!/^\/manage\/pages\/[0-9a-f-]{36}\/edit\/(?:check|save|draft)\/$/u.test(url.pathname))return;
    const summary={operation:url.pathname.split('/').filter(Boolean).at(-1),status:response.status()};
    try{const body=await response.json();if(typeof body.code==='string'&&/^[A-Z0-9_]{1,120}$/u.test(body.code))summary.code=body.code;}catch{}
    lastResponses.push(summary);if(lastResponses.length>12)lastResponses.shift();}catch{}});
  value.on('page',page=>page.on('pageerror',error=>{pageErrorCodes.push(fixed(error.message));if(pageErrorCodes.length>8)pageErrorCodes.shift();}));
  await value.addInitScript(()=>{globalThis.__mediaCsp=[];document.addEventListener('securitypolicyviolation',event=>globalThis.__mediaCsp.push(event.effectiveDirective));});return value;}
async function login(ctx,account){const page=await ctx.newPage();await page.goto(safe('/manage/login/'));await page.locator('[name=username]').fill(account.username);await page.locator('[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(safe('/manage/'),{timeout:15000}),page.locator('form[action="/manage/login/"] button').click()]);return page;}
async function ready(page){diagnosticPage=page;await page.locator('.es-page-actions').waitFor();await page.locator('[data-editor-media=main_image]').waitFor();}
async function idle(page){await page.waitForFunction(()=>!document.querySelector('.es-page-actions [data-editor-action=check]').disabled,{},{timeout:25000});}
async function checked(page){await action(page,'check').click();await idle(page);const accept=page.locator('.es-review').getByRole('button',{name:'Принять проверенный вариант',exact:true});if(await accept.isVisible())await accept.click();ensure((await page.locator('[data-editor-dirty]').textContent()).includes('Проверено.'),'CHECK_NOT_ACCEPTED');}
async function write(page,name='save'){await action(page,name).click();await page.waitForFunction(name=>document.querySelector('[data-editor-dirty]')?.textContent===(name==='draft'?'Черновик сохранён отдельно от сайта.':'Сохранение подтверждено.'),name,{timeout:25000});}
async function choose(page,field,id,apply=true){const section=media(page,field);await section.locator('[data-editor-media-action=open]').click();await section.locator('[data-editor-media-asset="'+id+'"]').click();if(apply){const button=section.getByRole('button',{name:/^(Добавить|Заменить) здесь$/u});await button.click();}}
async function text(page,value){const field=page.locator('[data-editor-field=main_text]');await field.locator('.es-toolbar').getByRole('button',{name:'HTML',exact:true}).click();await field.locator('.es-html-source').fill(value);}
async function invariant(page){const facts=await page.evaluate(()=>({csp:globalThis.__mediaCsp||[],inline:document.querySelectorAll('[data-editor-page] [style],[data-editor-page] style,[data-editor-page] colgroup').length,local:localStorage.length,session:sessionStorage.length}));ensure(facts.csp.length===0,'CSP_VIOLATION');ensure(facts.inline===0,'INLINE_STYLE_OR_COLGROUP');ensure(facts.local===0&&facts.session===0,'BROWSER_STORAGE_USED');}
async function check(id,m07,body){current=id;const facts=await body();if(diagnosticPage&&!diagnosticPage.isClosed()&&new URL(diagnosticPage.url()).pathname.includes('/edit/'))await invariant(diagnosticPage);groups.push({id,m07,status:'PASS',...facts});}
async function bytes(api,url,file){const response=await api.get(safe(url),{maxRedirects:0});ensure(response.status()===200,'IMAGE_HTTP_STATUS');const headers=response.headers(),body=await response.body();ensure(headers['content-type']==='image/webp'&&headers['x-content-type-options']==='nosniff'&&(headers['cache-control']||'').includes('no-store'),'IMAGE_PRIVATE_HEADERS');ensure(file.physical&&body.length===file.physical.byte_size&&sha(body)===file.physical.sha256,'IMAGE_ACTUAL_FILESYSTEM_SHA');ensure(body.subarray(0,4).toString()==='RIFF'&&body.subarray(8,12).toString()==='WEBP','IMAGE_WEBP_BYTES');}
async function imageUrl(locator){
  await locator.waitFor();
  try{
    await locator.evaluate(target=>{
      const images=[...document.querySelectorAll('[data-editor-media] img')];
      if(!images.includes(target)||images.length===0)throw new Error('IMAGE_LOAD_FAILED');
      return Promise.all(images.map(image=>new Promise((resolve,reject)=>{
      let timer;
      const finish=ok=>{clearTimeout(timer);observer.disconnect();image.removeEventListener('load',inspect);image.removeEventListener('error',failed);ok?resolve():reject(new Error('IMAGE_LOAD_FAILED'));};
      const failed=()=>finish(false);
      const inspect=()=>{if(!image.isConnected){finish(false);return;}if(image.getAttribute('src')&&image.complete)finish(image.naturalWidth>0&&image.naturalHeight>0);};
      const observer=new MutationObserver(inspect);
      image.addEventListener('load',inspect);image.addEventListener('error',failed);
      observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['src']});
      timer=setTimeout(failed,20000);inspect();
      })));
    });
    ensure(await locator.evaluate(image=>image.isConnected&&image.complete&&image.naturalWidth>0&&image.naturalHeight>0),'IMAGE_NOT_ACTUALLY_DISPLAYED');
  }catch{throw new Error('IMAGE_NOT_ACTUALLY_DISPLAYED');}
  return locator.getAttribute('src');
}
async function navigate(page,locator){let decision,failure=false;const handler=dialog=>{decision=dialog.accept().catch(()=>{failure=true;});};page.once('dialog',handler);try{await Promise.all([page.waitForNavigation({timeout:20000}),locator.click()]);}finally{page.off('dialog',handler);if(decision)await decision;}ensure(!failure,'NAVIGATION_DIALOG_FAILED');}
try{
  const seed=JSON.parse(fs.readFileSync('/private/editor-seed.json','utf8')),inputs=JSON.parse(fs.readFileSync('/inputs/inputs.json','utf8'));ensure(seed.pageIds?.length===2&&seed.accounts?.owner,'SEED_CONTRACT');
  const pageId=seed.pageIds[0],prefix='/manage/pages/'+pageId+'/edit/';
  browser=await chromium.launch({headless:true});const ownerContext=await context(),owner=await login(ownerContext,seed.accounts.owner),ids=[];let firstVersion;
  await check('EMUI-001',['M07-001','M07-002'],async()=>{
    const before=await observe();
    for(const [name,page] of [['valid.png',pageId],['valid.jpg',seed.pageIds[1]],['valid.webp',pageId]]){
      const spec=inputs[name],data=fs.readFileSync('/inputs/'+name);ensure(spec?.name===name&&data.length===spec.bytes&&sha(data)===spec.sha256,'SYNTHETIC_INPUT_SHA');
      await owner.goto(safe('/manage/media/?page='+page));const form=owner.locator('form[data-media-upload]');await form.locator('[name=image]').setInputFiles({name,mimeType:spec.mime,buffer:data});await Promise.all([owner.waitForNavigation({timeout:30000}),form.getByRole('button',{name:'Добавить изображение',exact:true}).click()]);
      const id=await owner.locator('[data-uploaded-asset-id]').getAttribute('data-uploaded-asset-id');ensure(id&&!ids.includes(id),'NATIVE_UPLOAD_READY_MARKER');ids.push(id);
      const state=await observe(),uploaded=asset(state,id);ensure(uploaded.status==='ready'&&uploaded.files.length===3,'REAL_WORKER_READY');const source=part(state,id,'private-source');ensure(source.physical?.sha256===spec.sha256&&source.physical.byte_size===data.length,'ACTUAL_SOURCE_INPUT_SHA');
    }
    const state=await observe();ensure(row(state,pageId).currentId===row(before,pageId).currentId,'UPLOAD_PUBLISHED_PAGE');await owner.goto(safe(prefix));await ready(owner);return {actualNativeUploads:3,formats:['png','jpeg','webp']};
  });
  await check('EMUI-002',['M07-003','M07-004','M07-005','M07-006'],async()=>{
    const before=await observe();await choose(owner,'main_image',ids[0],false);ensure(await media(owner,'main_image').getByRole('button',{name:'Добавить здесь',exact:true}).count()===1,'ADD_HERE_REQUIRED');
    let checks=0;const listener=request=>{if(new URL(request.url()).pathname===prefix+'check/'&&request.method()==='POST')checks++;};owner.on('request',listener);await action(owner,'check').click();await idle(owner);owner.off('request',listener);ensure(checks===0,'PENDING_SELECTION_SENT');ensure((await observe()).domainHash===before.domainHash,'PICKER_CHANGED_DOMAIN');
    await media(owner,'main_image').getByRole('button',{name:'Добавить здесь',exact:true}).click();
    await media(owner,'main_image').locator('[data-editor-media-field=alt]').fill('SYNTHETIC <img onerror=canary> 😀');await media(owner,'main_image').locator('[data-editor-media-field=alignment]').selectOption('left');await media(owner,'main_image').locator('[data-editor-media-field=width_px]').fill('320');await media(owner,'main_image').locator('[data-editor-media-field=height_px]').fill('160');
    await checked(owner);ensure((await observe()).domainHash===before.domainHash,'CHECK_PUBLISHED_IMAGE');await write(owner);const state=await observe(),value=row(state,pageId).payload.main_image;firstVersion=row(state,pageId).currentId;
    ensure(value.asset_id===ids[0]&&value.alt==='SYNTHETIC <img onerror=canary> 😀'&&value.alignment==='left'&&value.width_px===320&&value.height_px===160,'METADATA_NOT_COMMITTED');
    const image=media(owner,'main_image').locator('img').first();await image.waitFor();ensure((await imageUrl(image)).includes(part(state,ids[0],'preview').id),'THUMBNAIL_NOT_PREVIEW');await bytes(ownerContext.request,await imageUrl(image),part(state,ids[0],'preview'));return {ramBeforeCheckAndSave:true,metadataLiteral:true};
  });
  await check('EMUI-003',['M07-003','M07-008','M07-020'],async()=>{
    const before=await observe();await choose(owner,'main_image',ids[1],false);ensure(await media(owner,'main_image').getByRole('button',{name:'Заменить здесь',exact:true}).count()===1,'REPLACE_HERE_REQUIRED');ensure(await media(owner,'main_image').getByRole('heading',{name:'Сейчас в редакторе',exact:true}).count()===1&&await media(owner,'main_image').getByRole('heading',{name:'Новое фото',exact:true}).count()===1,'OLD_NEW_MATERIAL_CONTEXT');ensure((await observe()).domainHash===before.domainHash,'PENDING_REPLACE_MUTATED');await media(owner,'main_image').getByRole('button',{name:'Заменить здесь',exact:true}).click();await choose(owner,'preview_image',ids[0]);await checked(owner);await write(owner);const after=await observe();ensure(row(after,pageId).payload.main_image.asset_id===ids[1]&&row(after,pageId).payload.preview_image.asset_id===ids[0],'CROSS_PAGE_REUSE_NOT_SAVED');ensure(asset(after,ids[0]).usages.some(use=>use.kind==='ordinary_version'&&use.consumerId===firstVersion),'OLD_VERSION_REFERENCE_LOST');for(const id of ids)for(const file of asset(after,id).files)ensure(file.physical?.sha256===file.sha256,'REPLACEMENT_DELETED_FILE');return {crossPageReuse:true,oldHistoryAndFilesRetained:true};
  });
  await check('EMUI-004',['M07-009','M07-010'],async()=>{
    const before=await observe();await choose(owner,'main_image',ids[2]);await checked(owner);await write(owner,'draft');const drafted=await observe(),draft=drafted.drafts.find(value=>value.pageId===pageId);ensure(draft?.payload.main_image.asset_id===ids[2]&&row(drafted,pageId).currentId===row(before,pageId).currentId,'IMAGE_DRAFT_PUBLISHED_OR_MISSING');
    const selectedUrl=new URL(owner.url());ensure(selectedUrl.searchParams.get('source')==='owner-draft'&&selectedUrl.searchParams.get('draftId')===draft.id&&selectedUrl.searchParams.get('draftRevision')===String(draft.revision),'DRAFT_ACK_URL_NOT_SELECTED');
    await owner.reload();await ready(owner);const image=media(owner,'main_image').locator('img').first();await bytes(ownerContext.request,await imageUrl(image),part(drafted,ids[2],'preview'));ensure((await imageUrl(image)).includes('source=owner-draft'),'DRAFT_IMAGE_SELECTOR_MISSING');await text(owner,'<p>IMAGE DRAFT APPLY</p>');await checked(owner);await write(owner);const after=await observe();ensure(!after.drafts.some(value=>value.pageId===pageId)&&row(after,pageId).payload.main_image.asset_id===ids[2],'DRAFT_IMAGE_NOT_APPLIED');return {actualDraftBytes:true,separateApply:true};
  });
  await check('EMUI-005',['M07-011','M07-012'],async()=>{
    await owner.goto(safe(prefix));await ready(owner);await navigate(owner,owner.getByRole('link',{name:'История и Stable',exact:true}));const version=owner.locator('[data-version-id="'+firstVersion+'"]');await navigate(owner,version.getByRole('link',{name:'Просмотреть',exact:true}));await navigate(owner,owner.locator('form[data-restore-prepare] button'));await owner.locator('form[data-restore-stage] [name=confirm_input_replacement]').check();await navigate(owner,owner.locator('form[data-restore-stage] button'));const before=await observe();await navigate(owner,owner.locator('a[data-restore-editor]'));await ready(owner);const image=media(owner,'main_image').locator('img').first();await bytes(ownerContext.request,await imageUrl(image),part(before,ids[0],'preview'));ensure((await imageUrl(image)).includes('source=restore-stage'),'STAGE_IMAGE_SELECTOR_MISSING');await choose(owner,'preview_image',ids[2]);await checked(owner);ensure(row(await observe(),pageId).currentId===row(before,pageId).currentId,'STAGE_CHECK_PUBLISHED');await write(owner);const after=await observe();ensure(row(after,pageId).payload.main_image.asset_id===ids[0]&&row(after,pageId).payload.preview_image.asset_id===ids[2],'STAGE_EFFECTIVE_IMAGES_WRONG');return {actualCandidateBytes:true,editedStageApply:true};
  });
  await check('EMUI-006',['M07-013','M07-014','M07-015'],async()=>{
    const state=await observe(),employeeContext=await context(),employee=await login(employeeContext,seed.accounts.employee);await employee.goto(safe(prefix));await ready(employee);ensure(await employee.locator('[data-editor-media-action=open],[data-editor-media-field]').count()===0,'EMPLOYEE_IMAGE_EDITOR_VISIBLE');ensure((await employeeContext.request.get(safe(prefix+'media/'),{maxRedirects:0})).status()===403,'EMPLOYEE_PICKER_ALLOWED');const thumb=media(employee,'main_image').locator('img').first();await bytes(employeeContext.request,await imageUrl(thumb),part(state,ids[0],'preview'));
    const visitor=await context();for(const route of [prefix+'media/',prefix+'media/files/'+part(state,ids[0],'main').id+'/'])ensure((await visitor.request.get(safe(route),{maxRedirects:0})).status()===401,'VISITOR_PRIVATE_IMAGE_ALLOWED');
    const otherContext=await context();await login(otherContext,seed.accounts.other);ensure((await otherContext.request.get(safe(prefix+'media/files/'+part(state,ids[0],'main').id+'/'),{maxRedirects:0})).status()===403,'FOREIGN_PAGE_IMAGE_ALLOWED');
    for(const id of ids){const source=part(state,id,'private-source');ensure((await ownerContext.request.get(safe(prefix+'media/picker-files/'+source.id+'/'),{maxRedirects:0})).status()===404,'OWNER_ORIGINAL_ALLOWED');for(const file of asset(state,id).files)ensure((await visitor.request.get(safe('/'+file.key),{maxRedirects:0})).status()===404,'PRIVATE_KEY_PUBLICLY_SERVED');}
    await invariant(employee);diagnosticPage=owner;return {employeeReadonlyActualBytes:true,originalAndPublicKeyDenied:true};
  });
  await check('EMUI-007',['M07-006','M07-007','M07-014'],async()=>{
    await owner.goto(safe(prefix));await ready(owner);const section=media(owner,'main_image');await section.locator('[data-editor-media-field=width_px]').fill('0');await section.locator('[data-editor-media-field=alt]').fill('ALT CANNOT CLEAR BAD DIMENSION');const before=await observe();let posts=0;const listener=request=>{if(new URL(request.url()).pathname===prefix+'check/'&&request.method()==='POST')posts++;};owner.on('request',listener);await action(owner,'check').click();await idle(owner);owner.off('request',listener);ensure(posts===0&&(await observe()).domainHash===before.domainHash,'INVALID_DIMENSION_SENT_OR_CHANGED');
    await section.locator('[data-editor-media-field=width_px]').fill('321');
    const oldCheck=owner.waitForResponse(response=>new URL(response.url()).pathname===prefix+'check/'&&response.request().method()==='POST');await checked(owner);const oldProof=(await(await oldCheck).json()).checkReceipt;ensure(typeof oldProof==='string','OLD_CHECK_PROOF_MISSING');
    await section.locator('[data-editor-media-field=alt]').fill('AFTER CHECK CHANGE');
    const sequence=[];let submittedProof;
    const saveListener=request=>{if(request.method()!=='POST')return;const path=new URL(request.url()).pathname;if(path===prefix+'check/')sequence.push('check');else if(path===prefix+'save/'){sequence.push('save');submittedProof=request.postDataJSON().checkReceipt;}};
    const freshCheck=owner.waitForResponse(response=>new URL(response.url()).pathname===prefix+'check/'&&response.request().method()==='POST');owner.on('request',saveListener);
    try{await write(owner);}finally{owner.off('request',saveListener);}
    const freshResponse=await freshCheck,freshProof=(await freshResponse.json()).checkReceipt;
    ensure(freshResponse.status()===200&&typeof freshProof==='string'&&freshProof!==oldProof,'FRESH_IMAGE_PROOF_REQUIRED');
    ensure(JSON.stringify(sequence)===JSON.stringify(['check','save'])&&submittedProof===freshProof&&submittedProof!==oldProof,'SAVE_DID_NOT_USE_FRESH_IMAGE_PROOF');
    const saved=row(await observe(),pageId).payload.main_image;ensure(saved.width_px===321&&saved.alt==='AFTER CHECK CHANGE','CORRECTED_METADATA_NOT_SAVED');return {badDimensionWholeInputBlocked:true,metadataInvalidatesProof:true,freshCheckBeforeSave:true};
  });
  await check('EMUI-008',['M07-022','M07-023'],async()=>{
    await owner.reload();await ready(owner);await invariant(owner);await owner.screenshot({path:'/output/media-desktop.png',fullPage:true,caret:'initial'});await invariant(owner);await owner.setViewportSize({width:390,height:844});await invariant(owner);await owner.screenshot({path:'/output/media-mobile.png',fullPage:true,caret:'initial'});await invariant(owner);return {desktop1280:true,mobile390:true,strictCsp:true};
  });
  output({kind:'result',status:'PASS',scope:'MEDIA_8',groups});
}catch(error){const facts={lastResponses,pageErrorCodes};if(diagnosticPage&&!diagnosticPage.isClosed()&&new URL(diagnosticPage.url()).pathname.includes('/edit/')){try{facts.csp=await diagnosticPage.evaluate(()=>globalThis.__mediaCsp||[]);await diagnosticPage.screenshot({path:'/output/media-failure.png',fullPage:true,caret:'initial'});}catch{facts.diagnosticUnavailable=true;}}output({kind:'result',status:'FAIL',caseId:current,errorClass:error?.constructor?.name||'Error',errorCode:fixed(error?.message),groups,diagnostics:facts});process.exitCode=1;
}finally{for(const ctx of contexts)await ctx.close().catch(()=>{});if(browser)await browser.close().catch(()=>{});channel.close();}
