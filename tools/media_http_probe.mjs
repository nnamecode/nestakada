// Fixed-origin real HTTP/browser checks. Fixture observations arrive over stdin, never an HTTP control API.
import fs from 'node:fs';
import crypto from 'node:crypto';
import readline from 'node:readline';
import { chromium } from '/tests/node_modules/playwright/index.mjs';

const origin='http://host.docker.internal:8767';
const lines=readline.createInterface({input:process.stdin,terminal:false});
const pending=new Map();
let startResolve; const start=new Promise(resolve=>{startResolve=resolve;});
lines.on('line',line=>{
  try{
    const item=JSON.parse(line);
    if(item.kind==='seed')startResolve(item);
    else if(item.kind==='observation'&&pending.has(item.id)){
      const wait=pending.get(item.id);pending.delete(item.id);
      item.error?wait.reject(new Error('HOST_OBSERVATION_FAILED')):wait.resolve(item.value);
    }
  }catch{process.exitCode=1;}
});
const write=value=>process.stdout.write(JSON.stringify(value)+'\n');
let seq=0;
function observe(){
  const id=++seq;return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{pending.delete(id);reject(new Error('OBSERVER_TIMEOUT'));},30_000);
    pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value);},reject:error=>{clearTimeout(timer);reject(error);}});
    write({kind:'observe',id});
  });
}
let current='START', browser, contexts=[];
const passed=[];
const requireCheck=(condition,code)=>{if(!condition)throw new Error(code);};
async function check(id,run){current=id;const details=await run();passed.push({id,status:'PASS',...details});}
const safePath=p=>{if(typeof p!=='string'||!p.startsWith('/')||new URL(p,origin).origin!==origin)throw new Error('FIXED_ORIGIN_REQUIRED');return new URL(p,origin).href;};
async function privateHeader(response){
  const h=response.headers();requireCheck((h['cache-control']??'').includes('private')&&(h['cache-control']??'').includes('no-store'),'PRIVATE_HEADERS');
}
async function authContext(account){
  const context=await browser.newContext({viewport:{width:1280,height:900}});
  contexts.push(context);
  await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  const page=await context.newPage();
  await page.goto(safePath('/manage/login/'));
  await page.locator('input[name=username]').fill(account.username);
  await page.locator('input[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(safePath('/manage/')),page.locator('form[action="/manage/login/"] button').click()]);
  // Credentials never appear in a screenshot, trace, or printed result.
  requireCheck(await page.locator('input[type=password]').count()===0,'LOGIN_NOT_COMPLETE');
  return {context,page,api:context.request};
}
async function formInfo(actor,path,action){
  const response=await actor.page.goto(safePath(path));requireCheck(response?.status()===200,'FORM_GET_STATUS');
  const form=actor.page.locator('form[action="'+action+'"]');
  requireCheck(await form.count()===1,'FORM_NOT_UNIQUE');
  return {csrf:await form.locator('input[name=csrfmiddlewaretoken]').inputValue(),generation:await form.locator('input[name=generation]').inputValue(),form};
}
function multipart(fields,files){
  const boundary='media-http-'+crypto.randomBytes(12).toString('hex'),parts=[];
  for(const [name,value]of Object.entries(fields))parts.push(Buffer.from('--'+boundary+'\r\nContent-Disposition: form-data; name="'+name+'"\r\n\r\n'+value+'\r\n'));
  for(const file of files){
    parts.push(Buffer.from('--'+boundary+'\r\nContent-Disposition: form-data; name="image"; filename="'+file.name+'"\r\nContent-Type: '+file.mime+'\r\n\r\n'),file.buffer,Buffer.from('\r\n'));
  }
  parts.push(Buffer.from('--'+boundary+'--\r\n'));
  return {data:Buffer.concat(parts),headers:{'Content-Type':'multipart/form-data; boundary='+boundary,Referer:origin+'/manage/media/'}};
}
async function postImages(api,path,info,files,csrf=info.csrf){
  return api.post(safePath(path),{...multipart({generation:info.generation,...(csrf===null?{}:{csrfmiddlewaretoken:csrf})},files),maxRedirects:0,timeout:30_000});
}
try{
  const input=await start, fixture=input.fixture;
  requireCheck(input.origin===origin&&Array.isArray(fixture.pageIds)&&fixture.pageIds.length===3&&fixture.folders?.length===3,'FIXED_FIXTURE_REQUIRED');
  const inputs=JSON.parse(fs.readFileSync('/inputs/inputs.json','utf8'));
  function file(name,overrides={}){
    const meta=inputs[name];requireCheck(meta&&meta.name===name,'UNKNOWN_SYNTHETIC_INPUT');
    const buffer=fs.readFileSync('/inputs/'+name);
    requireCheck(buffer.length===meta.bytes&&crypto.createHash('sha256').update(buffer).digest('hex')===meta.sha256,'INPUT_INTEGRITY');
    return {name,mime:meta.mime,buffer,...overrides};
  }
  const pageId=fixture.pageIds[0], upload='/manage/media/pages/'+pageId+'/upload/',catalog='/manage/media/?page='+pageId;
  browser=await chromium.launch({headless:true});
  const owner=await authContext(fixture.accounts.owner);
  const employee=await authContext(fixture.accounts.employee);
  const visitorContext=await browser.newContext();contexts.push(visitorContext);
  await visitorContext.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  const visitorPage=await visitorContext.newPage();await visitorPage.goto(safePath('/manage/login/'));
  const visitorCsrf=await visitorPage.locator('input[name=csrfmiddlewaretoken]').inputValue();
  let info=await formInfo(owner,catalog,upload);
  let uploaded=[];
  await check('MH-002',async()=>{
    const before=await observe();
    const deniedVisitor=await postImages(visitorContext.request,upload,{...info,csrf:visitorCsrf},[file('valid.png')]);
    requireCheck(deniedVisitor.status()===401,'VISITOR_UPLOAD_NOT_401');
    await employee.page.goto(safePath('/manage/'));
    const employeeCsrf=await employee.page.locator('form[action="/manage/logout/"] input[name=csrfmiddlewaretoken]').inputValue();
    const deniedEmployee=await postImages(employee.api,upload,{...info,csrf:employeeCsrf},[file('valid.png')]);
    requireCheck(deniedEmployee.status()===403,'EMPLOYEE_UPLOAD_NOT_403');
    for(const path of [catalog,'/manage/media/cleanup/']){
      requireCheck((await visitorContext.request.get(safePath(path),{maxRedirects:0})).status()===401,'VISITOR_MEDIA_UI_NOT_401');
      requireCheck((await employee.api.get(safePath(path),{maxRedirects:0})).status()===403,'EMPLOYEE_MEDIA_UI_NOT_403');
    }
    const after=await observe();requireCheck(JSON.stringify(after.assets)===JSON.stringify(before.assets),'DENIED_UPLOAD_CHANGED_ASSETS');
    return {visitorStatus:401,employeeStatus:403};
  });
  await check('MH-003-upload',async()=>{
    const before=await observe();
    for(const csrf of [null,'invalid-csrf']){
      const response=await postImages(owner.api,upload,info,[file('valid.png')],csrf);
      requireCheck(response.status()===403,'CSRF_UPLOAD_NOT_403');
    }
    const after=await observe();requireCheck(JSON.stringify(after.assets)===JSON.stringify(before.assets),'CSRF_UPLOAD_CHANGED_ASSETS');
    return {missingAndForgedCsrfDenied:true};
  });
  await check('MH-001',async()=>{
    for(const [index,name]of ['valid.jpg','valid.png','valid.webp'].entries()){
      const specificUpload='/manage/media/pages/'+fixture.pageIds[index]+'/upload/';
      info=await formInfo(owner,'/manage/media/?page='+fixture.pageIds[index],specificUpload);
      await info.form.locator('input[name=image]').setInputFiles('/inputs/'+name);
      await Promise.all([owner.page.waitForURL(url=>url.pathname==='/manage/media/'&&url.searchParams.has('asset')),info.form.locator('button[type=submit],button:not([type])').click()]);
      const id=new URL(owner.page.url()).searchParams.get('asset');
      requireCheck(/^[a-f0-9-]{36}$/u.test(id??''),'UPLOAD_ID');
      requireCheck(await owner.page.locator('[data-uploaded-asset-id="'+id+'"]').count()===1,'UPLOAD_SUCCESS_MARKER');
      const state=await observe(),asset=state.assets.find(a=>a.id===id);
      requireCheck(asset?.status==='ready'&&asset.files.length===3,'UPLOAD_NOT_PHYSICALLY_READY');
      const source=asset.files.find(f=>f.kind==='private-source');
      requireCheck(source?.physical?.sha256===inputs[name].sha256&&source.physical.byte_size===inputs[name].bytes,'SOURCE_BYTES_CHANGED');
      for(const kind of ['main','preview']){
        const part=asset.files.find(f=>f.kind===kind);requireCheck(part?.physical?.byte_size>0,'DERIVATIVE_MISSING');
      }
      uploaded.push({id,name,pageId:fixture.pageIds[index],files:asset.files});
    }
    return {formats:['JPEG','PNG','WEBP'],assetIds:uploaded.map(a=>a.id)};
  });
  await check('MH-004',async()=>{
    info=await formInfo(owner,catalog,upload);
    const boundary=await postImages(owner.api,upload,info,[file('boundary.png')]);
    requireCheck(boundary.status()===303,'EXACT_1MB_REJECTED');
    const location=boundary.headers().location;requireCheck(location&&new URL(location,origin).origin===origin,'BOUNDARY_LOCATION');
    const boundaryId=new URL(location,origin).searchParams.get('asset'),state=await observe();
    const boundaryAsset=state.assets.find(a=>a.id===boundaryId);
    requireCheck(boundaryAsset?.status==='ready'&&boundaryAsset.files.find(f=>f.kind==='private-source')?.physical?.byte_size===1_000_000,'BOUNDARY_NOT_READY');
    uploaded.push({id:boundaryId,name:'boundary.png',files:boundaryAsset.files});
    const rejected=[];
    for(const [id,files]of [
      ['over',[file('over.png')]],['two-files',[file('valid.png'),file('valid.jpg')]],
      ['svg',[file('active.svg')]],['html',[file('active.html')]],
      ['mime-mismatch',[file('valid.png',{mime:'image/jpeg'})]],
      ['extension-mismatch',[file('valid.png',{name:'wrong.jpg'})]],
      ['truncated',[file('truncated.png')]],['pixel-over',[file('pixel-over.png')]]
    ]){
      info=await formInfo(owner,catalog,upload);const before=await observe();
      const response=await postImages(owner.api,upload,info,files);
      requireCheck([400,413].includes(response.status()),'INVALID_UPLOAD_STATUS_'+id);
      const after=await observe();
      requireCheck(after.assets.filter(a=>a.status==='ready').length===before.assets.filter(a=>a.status==='ready').length,'INVALID_UPLOAD_READY_'+id);
      rejected.push({id,status:response.status()});
    }
    return {boundaryBytes:1_000_000,rejected};
  });
  await check('MH-005',async()=>{
    const asset=uploaded[0];
    for(const part of asset.files){
      const uri='/manage/media/files/'+part.id+'/';
      const response=await owner.api.get(safePath(uri),{maxRedirects:0});
      if(part.kind==='private-source')requireCheck(response.status()===404,'OWNER_SOURCE_EXPOSED');
      else{
        requireCheck(response.status()===200,'OWNER_DERIVATIVE_UNAVAILABLE');await privateHeader(response);
        const h=response.headers();requireCheck(h['content-type']?.split(';')[0]==='image/webp'&&h['x-content-type-options']==='nosniff','DERIVATIVE_HEADERS');
        const body=await response.body();requireCheck(body.toString('ascii',0,4)==='RIFF'&&body.toString('ascii',8,12)==='WEBP','NOT_WEBP_BYTES');
        requireCheck(body.length===part.physical.byte_size&&crypto.createHash('sha256').update(body).digest('hex')===part.physical.sha256,'DERIVATIVE_HTTP_FS_MISMATCH');
      }
      for(const api of [employee.api,visitorContext.request]){
        const denied=await api.get(safePath(uri),{maxRedirects:0});requireCheck([401,403,404].includes(denied.status()),'PRIVATE_FILE_EXPOSED');
      }
      for(const uriGuess of ['/'+part.key,'/img/'+part.key,'/media/'+part.key]){
        const denied=await visitorContext.request.get(safePath(uriGuess),{maxRedirects:0});requireCheck([401,403,404].includes(denied.status()),'STORAGE_KEY_PUBLIC');
      }
    }
    for(const uri of ['/img/','/media/','/manage/media/files/']){
      const denied=await visitorContext.request.get(safePath(uri),{maxRedirects:0});requireCheck([401,403,404].includes(denied.status()),'DIRECTORY_LISTING');
    }
    await owner.page.goto(safePath(catalog));
    const images=owner.page.locator('[data-media-asset-id="'+asset.id+'"] img');
    requireCheck(await images.count()>0,'BROWSER_PREVIEW_ABSENT');
    requireCheck(await images.evaluateAll(imgs=>imgs.every(img=>img.complete&&img.naturalWidth===100&&img.naturalHeight===50)),'BROWSER_PREVIEW_DECODE');
    return {sourceNeverServed:true,derivativesOwnerOnly:true,browserImageDecoded:true};
  });
  await check('MH-006-paths',async()=>{
    for(const folder of ['../','..\\','%2e%2e%2f','/etc','private/sources']){
      const response=await owner.api.get(safePath(catalog+'&folder='+encodeURIComponent(folder)),{maxRedirects:0});
      requireCheck([400,404].includes(response.status()),'UNSAFE_FOLDER_ACCEPTED');
    }
    const folder=fixture.folders[0].path;
    const search=catalog+'&folder='+encodeURIComponent(folder)+'&q='+encodeURIComponent('fixture-'+fixture.runId);
    const searchResponse=await owner.page.goto(safePath(search));requireCheck(searchResponse.status()===200,'SEARCH_STATUS');
    for(const [index,expected]of [[0,1],[1,1],[2,0]])
      requireCheck(await owner.page.locator('[data-media-asset-id="'+uploaded[index].id+'"]').count()===expected,'FOLDER_SEGMENT_SEARCH');
    const exact=await owner.page.goto(safePath(catalog+'&folder='+encodeURIComponent(folder)));
    requireCheck(exact.status()===200,'FOLDER_EXACT_STATUS');
    requireCheck(await owner.page.locator('[data-media-asset-id="'+uploaded[1].id+'"]').count()===0,'FOLDER_EXACT_RECURSED');
    return {pathRejection:true,descendantIncluded:true,similarPrefixExcluded:true,withoutQueryDirectOnly:true};
  });
  await check('MH-010',async()=>{
    await owner.page.goto(safePath(catalog));
    for(const [name,width]of [['desktop',1280],['mobile',390]]){
      await owner.page.setViewportSize({width,height:900});
      requireCheck(await owner.page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'MEDIA_HORIZONTAL_OVERFLOW');
      requireCheck(await owner.page.locator('input[type=password]').count()===0,'PASSWORD_SCREENSHOT_PROHIBITED');
      await owner.page.screenshot({path:'/results/'+name+'.png',fullPage:true});
    }
    return {widths:[1280,390],screenshots:['desktop.png','mobile.png']};
  });
  await check('MH-007',async()=>{
    const cleanup='/manage/media/cleanup/',prepare='/manage/media/cleanup/prepare/',confirm='/manage/media/cleanup/confirm/';
    const response=await owner.page.goto(safePath(cleanup));requireCheck(response.status()===200,'CLEANUP_PAGE');
    const form=owner.page.locator('form[action="'+prepare+'"]');
    const target=uploaded[0], keys=target.files.map(f=>f.key);
    await form.locator('input[name=asset_ids][value="'+target.id+'"]').check();
    await Promise.all([owner.page.waitForURL(safePath(prepare)),form.locator('button[type=submit],button:not([type])').click()]);
    const confirmation=owner.page.locator('form[data-media-confirmation]');
    requireCheck(await confirmation.count()===1,'CONFIRMATION_MISSING');
    const beforeCancel=await observe();
    await Promise.all([owner.page.waitForURL(safePath(cleanup)),confirmation.getByRole('link',{name:'Отмена',exact:true}).click()]);
    const afterCancel=await observe();
    requireCheck(JSON.stringify(beforeCancel.assets)===JSON.stringify(afterCancel.assets),'CANCEL_CHANGED_MEDIA');
    await form.locator('input[name=asset_ids][value="'+target.id+'"]').check();
    await Promise.all([owner.page.waitForURL(safePath(prepare)),form.locator('button[type=submit],button:not([type])').click()]);
    requireCheck(await confirmation.count()===1,'CONFIRMATION_AFTER_CANCEL');
    const token=await confirmation.locator('input[name=confirmation]').inputValue();
    const generation=await confirmation.locator('input[name=generation]').inputValue();
    const csrf=await confirmation.locator('input[name=csrfmiddlewaretoken]').inputValue();
    const total=target.files.reduce((n,f)=>n+f.physical.byte_size,0);
    requireCheck(await owner.page.locator('[data-media-total-bytes]').getAttribute('data-media-total-bytes')===String(total),'CLEANUP_TOTAL_BYTES');
    for(const [label,api,fields]of [
      ['owner-no-csrf',owner.api,{confirmation:token,generation}],
      ['owner-tamper',owner.api,{confirmation:token+'tampered',generation,csrfmiddlewaretoken:csrf}],
      ['employee',employee.api,{confirmation:token,generation,csrfmiddlewaretoken:await employee.page.locator('form[action="/manage/logout/"] input[name=csrfmiddlewaretoken]').inputValue()}],
      ['visitor',visitorContext.request,{confirmation:token,generation,csrfmiddlewaretoken:visitorCsrf}]
    ]){
      const denied=await api.post(safePath(confirm),{form:fields,maxRedirects:0,headers:{Referer:origin+cleanup}});
      requireCheck([400,401,403].includes(denied.status()),'CLEANUP_UNSAFE_'+label);
      requireCheck((await observe(keys)).assets.some(a=>a.id===target.id),'DENIED_CLEANUP_REMOVED_ASSET');
    }
    await Promise.all([owner.page.waitForURL(safePath(confirm)),confirmation.locator('button[type=submit],button:not([type])').click()]);
    const result=owner.page.locator('[data-media-cleanup-result][data-state=deleted]');
    requireCheck(await result.count()===1,'CLEANUP_NOT_DELETED');
    requireCheck(await result.getAttribute('data-released-bytes')===String(total),'RELEASED_BYTES');
    requireCheck(await result.getAttribute('data-pending-files')==='0','CLEANUP_PENDING');
    const after=await observe(keys);
    requireCheck(!after.assets.some(a=>a.id===target.id),'CLEANUP_DB_REMAINED');
    const physical=after.physicalFiles?.filter(f=>f.assetId===target.id);
    requireCheck(Array.isArray(physical)&&physical.length===keys.length&&physical.every(f=>keys.includes(f.key)&&f.physical===null),'CLEANUP_PHYSICAL_NOT_PROVEN');
    return {assetId:target.id,releasedBytes:total,physicalFilesAbsent:keys.length,cancelPreservedMedia:true};
  });
  write({kind:'result',status:'PASS',passed,notChecked:['MH-008 physical-failure HTTP branch (separate PostgreSQL/FS tests)','MH-009 worker-down/unknown-receipt (root controlled fault)','Full MEDIA-001..029; Stable/HTML/current references;214-original import']});
}catch(error){
  write({kind:'result',status:'FAIL',failedAt:current,code:/^[A-Z0-9_-]{1,100}$/u.test(error.message??'')?error.message:'BROWSER_OR_PROTOCOL_ERROR',passed});
  process.exitCode=1;
}finally{
  for(const context of contexts)await context.close().catch(()=>{});
  await browser?.close().catch(()=>{});
  lines.close();process.stdin.destroy();
}
