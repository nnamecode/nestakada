// E3 bounded real browser/HTTP proof. Synthetic inputs only, no control HTTP API.
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
const lastResponses=[],pageErrorCodes=[],slotGeometry=[],toolbarFocus=[],cspPhases=[],boundarySelections=[],nativeKeyFacts=[];
const diagnosticScope=process.env.E3_DIAGNOSTIC_SCOPE;
class DiagnosticStop extends Error {}
const channel=readline.createInterface({input:process.stdin,terminal:false});
channel.on('line',line=>{try{const value=JSON.parse(line),waiter=pending.get(value.id);if(value.kind==='observation'&&waiter){pending.delete(value.id);value.error?waiter.reject(new Error('HOST_OBSERVER_FAILED')):waiter.resolve(value.value);}}catch{process.exitCode=1;}});
function observe(){return new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{pending.delete(id);reject(new Error('OBSERVER_TIMEOUT'));},30000);pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value);},reject:error=>{clearTimeout(timer);reject(error);}});output({kind:'observe',id,caseId:current});});}
const row=(state,id)=>{const result=state.pages.find(value=>value.id===id);ensure(result,'PAGE_OBSERVER_MISSING');return result;};
const asset=(state,id)=>{const result=state.assets.find(value=>value.id===id);ensure(result,'ASSET_OBSERVER_MISSING');return result;};
const part=(state,id,kind)=>{const result=asset(state,id).files.find(value=>value.kind===kind);ensure(result,'FILE_OBSERVER_MISSING');return result;};
const media=(page,field)=>page.locator('[data-editor-media="'+field+'"]');
const action=(page,name)=>page.locator('.es-page-actions [data-editor-action="'+name+'"]');
async function context(){const value=await browser.newContext({viewport:{width:1280,height:900},timezoneId:'UTC'});contexts.push(value);await value.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  value.on('response',async response=>{try{const url=new URL(response.url());if(url.origin!==origin||!/^\/manage\/pages\/[0-9a-f-]{36}\/edit\/(?:check|save|draft|embedded\/issue)\/$/u.test(url.pathname))return;
    const summary={operation:url.pathname.split('/').filter(Boolean).at(-1),status:response.status()};
    try{const body=await response.json();if(typeof body.code==='string'&&/^[A-Z0-9_]{1,120}$/u.test(body.code))summary.code=body.code;}catch{}
    lastResponses.push(summary);if(lastResponses.length>12)lastResponses.shift();}catch{}});
  value.on('page',page=>page.on('pageerror',error=>{pageErrorCodes.push(fixed(error.message));if(pageErrorCodes.length>8)pageErrorCodes.shift();}));
  await value.addInitScript(()=>{
    globalThis.__mediaCsp=[];globalThis.__cspDetails=[];globalThis.__styleMutations=[];globalThis.__cspPhase='BOOT';
    document.addEventListener('securitypolicyviolation',event=>{
      globalThis.__mediaCsp.push(event.effectiveDirective);
      let sourceFile=null,blocked='other';
      try{const url=new URL(event.sourceFile);const name=url.pathname.split('/').at(-1);if(url.origin===location.origin&&/^[A-Za-z0-9._-]{1,100}$/u.test(name))sourceFile=name;}catch{}
      if(!event.blockedURI)blocked='empty';else if(['inline','eval','wasm-eval'].includes(event.blockedURI))blocked=event.blockedURI;
      else if(event.blockedURI.startsWith('data:'))blocked='data';else try{blocked=new URL(event.blockedURI).origin===location.origin?'same-origin':'external';}catch{}
      const integer=value=>Number.isSafeInteger(value)&&value>=0&&value<=10000000?value:null;
      globalThis.__cspDetails.push({effectiveDirective:/^[a-z-]{1,80}$/u.test(event.effectiveDirective)?event.effectiveDirective:'unknown',sourceFile,
        line:integer(event.lineNumber),column:integer(event.columnNumber),blocked,phase:globalThis.__cspPhase});
      if(globalThis.__cspDetails.length>40)globalThis.__cspDetails.shift();
    });
    const classes=['es-editor-surface','es-protected-slot','es-protected-parent','es-embedded-atom','ProseMirror','ProseMirror-trailingBreak','ProseMirror-selectednode'];
    new MutationObserver(records=>{for(const record of records){const node=record.target;
      globalThis.__styleMutations.push({phase:globalThis.__cspPhase,tag:/^[A-Z0-9-]{1,40}$/u.test(node.tagName)?node.tagName:'other',
        localClass:classes.find(name=>node.classList?.contains(name))||'other',attributeCount:node.attributes.length,stylePresent:node.hasAttribute('style')});
      if(globalThis.__styleMutations.length>60)globalThis.__styleMutations.shift();
    }}).observe(document,{subtree:true,attributes:true,attributeFilter:['style']});
  });return value;}
async function cspPhase(page,phase){if(current!=='EUI-004')return;const facts=await page.evaluate(value=>{globalThis.__cspPhase=value;return {cspCount:(globalThis.__mediaCsp||[]).length,styleCount:document.querySelectorAll('[data-editor-page] [style]').length,mutationCount:(globalThis.__styleMutations||[]).length};},phase);cspPhases.push({phase,...facts});if(cspPhases.length>80)cspPhases.shift();ensure(facts.cspCount===0,'CSP_VIOLATION');}
async function login(ctx,account,existing=null){const page=existing||await ctx.newPage();await page.goto(safe('/manage/login/'));await cspPhase(page,'LOGIN.FORM.READY');await page.locator('[name=username]').fill(account.username);await page.locator('[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(safe('/manage/'),{timeout:15000}),page.locator('form[action="/manage/login/"] button').click()]);return page;}
async function ready(page){diagnosticPage=page;await page.locator('.es-page-actions').waitFor();await page.locator('[data-editor-media=main_image]').waitFor();}
async function idle(page){await page.waitForFunction(()=>!document.querySelector('.es-page-actions [data-editor-action=check]').disabled,{},{timeout:25000});}
async function checked(page){await action(page,'check').click();await idle(page);const accept=page.locator('.es-review').getByRole('button',{name:'Принять проверенный вариант',exact:true});if(await accept.isVisible())await accept.click();ensure((await page.locator('[data-editor-dirty]').textContent()).includes('Проверено.'),'CHECK_NOT_ACCEPTED');const images=page.locator('[data-editor-page] img');if(await images.count())await imageUrl(images.first());}
async function write(page,name='save'){await action(page,name).click();await page.waitForFunction(name=>document.querySelector('[data-editor-dirty]')?.textContent===(name==='draft'?'Черновик сохранён отдельно от сайта.':'Сохранение подтверждено.'),name,{timeout:25000});}
async function choose(page,field,id,apply=true){const section=media(page,field);await section.locator('[data-editor-media-action=open]').click();await section.locator('[data-editor-media-asset="'+id+'"]').click();if(apply){const button=section.getByRole('button',{name:/^(Добавить|Заменить) здесь$/u});await button.click();}}
async function text(page,value){const field=page.locator('[data-editor-field=main_text]');await field.locator('.es-toolbar').getByRole('button',{name:'HTML',exact:true}).click();await field.locator('.es-html-source').fill(value);}
async function invariant(page){const facts=await page.evaluate(()=>({csp:globalThis.__mediaCsp||[],inline:document.querySelectorAll('[data-editor-page] [style],[data-editor-page] style,[data-editor-page] colgroup').length,local:localStorage.length,session:sessionStorage.length}));ensure(facts.csp.length===0,'CSP_VIOLATION');ensure(facts.inline===0,'INLINE_STYLE_OR_COLGROUP');ensure(facts.local===0&&facts.session===0,'BROWSER_STORAGE_USED');}
async function check(id,i07,body){current=id;const facts=await body();if(diagnosticPage&&!diagnosticPage.isClosed()&&new URL(diagnosticPage.url()).pathname.includes('/edit/'))await invariant(diagnosticPage);groups.push({id,i07,status:'PASS',...facts});if(diagnosticScope==='diagnostic-employee-csp'&&id==='EUI-004')throw new DiagnosticStop();}
async function bytes(api,url,file){const response=await api.get(safe(url),{maxRedirects:0});ensure(response.status()===200,'IMAGE_HTTP_STATUS');const headers=response.headers(),body=await response.body();ensure(headers['content-type']==='image/webp'&&headers['x-content-type-options']==='nosniff'&&(headers['cache-control']||'').includes('no-store'),'IMAGE_PRIVATE_HEADERS');ensure(file.physical&&body.length===file.physical.byte_size&&sha(body)===file.physical.sha256,'IMAGE_ACTUAL_FILESYSTEM_SHA');ensure(body.subarray(0,4).toString()==='RIFF'&&body.subarray(8,12).toString()==='WEBP','IMAGE_WEBP_BYTES');}
async function imageUrl(locator){
  await locator.waitFor();
  try{
    await locator.evaluate(target=>{
      const images=[...document.querySelectorAll('[data-editor-page] img')];
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
const rich=page=>page.locator('[data-editor-field=main_text]');
const embed=page=>page.locator('[data-editor-embedded=main_text]');
const atom=(page,id)=>rich(page).locator('[data-editor-embedded-marker="'+id+'"]');
const slot=(page,id)=>rich(page).locator('[data-editor-protected-slot="'+id+'"]');
async function issued(page,assetId,markerId=null){
  const section=embed(page);await section.locator('select[data-editor-embedded-marker]').selectOption(markerId||'');
  await section.locator('[data-editor-embedded-action=open]').click();await section.locator('[data-editor-embedded-asset="'+assetId+'"]').click();
  await imageUrl(section.locator('img').last());
  await section.locator('[data-editor-embedded-field=alt]').fill('SYNTHETIC EMBED 😀');
  const response=page.waitForResponse(value=>new URL(value.url()).pathname.endsWith('/edit/embedded/issue/')&&value.request().method()==='POST');
  await section.locator('[data-editor-embedded-action="'+(markerId?'replace':'insert')+'"]').click();
  const actual=await response;ensure(actual.status()===200,'ISSUE_HTTP_STATUS');const mint=await actual.json();
  ensure(typeof mint.permit==='string'&&Object.keys(mint.ids||{}).length===6,'ISSUE_RESPONSE_SHAPE');await idle(page);return mint;
}
async function immediateToolbarFocus(target,phase){
  const facts=await target.evaluate(element=>{
    const surface=element.closest('.es-editor-surface'),selection=getSelection();
    const inside=node=>{const parent=node?.nodeType===Node.ELEMENT_NODE?node:node?.parentElement;return parent?.closest('[data-editor-protected-slot]')===element;};
    return {activeOwnSurface:!!surface&&surface.contains(document.activeElement),
      selectionExpectedSlot:!!selection&&inside(selection.anchorNode)&&inside(selection.focusNode),
      anchorOffset:selection?.anchorOffset??null,focusOffset:selection?.focusOffset??null,textLength:element.textContent.length};
  });
  toolbarFocus.push({caseId:current,phase,...facts});if(toolbarFocus.length>12)toolbarFocus.shift();
  ensure(facts.activeOwnSurface,'TOOLBAR_FOCUS_NOT_SYNCHRONOUS');
  ensure(facts.selectionExpectedSlot,'TOOLBAR_SELECTION_LEFT_EXPECTED_SLOT');
}
async function boundarySelection(target,phase){
  const facts=await target.evaluate(element=>{
    const surface=element.closest('.es-editor-surface'),parent=element.closest('[data-editor-protected-parent]'),selection=getSelection();
    const integer=value=>Number.isSafeInteger(value)&&value>=0?value:null;
    const types=['doc','paragraph','heading','blockquote','bulletList','orderedList','listItem','esProtectedParent','esProtectedSlot','esProtected','text','hardBreak'];
    const type=value=>types.includes(value)?value:'other';
    const endpoint=(node,offset)=>{const owner=node?.nodeType===Node.ELEMENT_NODE?node:node?.parentElement;
      return {nodeKind:node?.nodeType===Node.TEXT_NODE?'TEXT':node?.nodeType===Node.ELEMENT_NODE?'ELEMENT':'OTHER',offset:integer(offset),
        expectedSlot:owner?.closest('[data-editor-protected-slot]')===element,anySlot:!!owner?.closest('[data-editor-protected-slot]'),
        expectedParent:!!parent&&owner?.closest('[data-editor-protected-parent]')===parent,anyParent:!!owner?.closest('[data-editor-protected-parent]'),
        insideAtom:!!owner?.closest('[data-editor-embedded-image-id]'),insideProtectedRoot:!!parent&&!!node&&parent.contains(node),insideOwnSurface:!!surface&&!!node&&surface.contains(node)};};
    const result={collapsed:selection?.isCollapsed??null,rangeCount:integer(selection?.rangeCount),activeOwnSurface:!!surface&&surface.contains(document.activeElement),
      anchor:endpoint(selection?.anchorNode,selection?.anchorOffset),focus:endpoint(selection?.focusNode,selection?.focusOffset),pm:{available:false}};
    try{
      const view=surface?.editor?.view;
      if(view&&view.dom===surface){
        const state=view.state,selected=state.selection;
        result.pm={available:true,from:integer(selected.from),to:integer(selected.to),empty:selected.empty,
          parentType:type(selected.$from.parent.type.name),parentOffset:integer(selected.$from.parentOffset),
          toParentType:type(selected.$to.parent.type.name),toParentOffset:integer(selected.$to.parentOffset)};
        const resolve=(node,offset,bias)=>{if(!node)return {available:false};try{const pos=view.posAtDOM(node,offset,bias),at=state.doc.resolve(pos);return {available:true,pos:integer(pos),parentType:type(at.parent.type.name),parentOffset:integer(at.parentOffset)};}catch{return {available:false};}};
        result.anchor.pmMinus=resolve(selection?.anchorNode,selection?.anchorOffset,-1);result.anchor.pmPlus=resolve(selection?.anchorNode,selection?.anchorOffset,1);
        result.focus.pmMinus=resolve(selection?.focusNode,selection?.focusOffset,-1);result.focus.pmPlus=resolve(selection?.focusNode,selection?.focusOffset,1);
      }
    }catch{result.pm={available:false};}
    return result;
  });
  boundarySelections.push({phase,...facts});if(boundarySelections.length>6)boundarySelections.shift();
}
async function typeSlot(page,id,value,{bold=false}={}){
  const phase=bold?'TYPE.BOLD':'TYPE.PLAIN';await cspPhase(page,phase+'.BEFORE');
  const target=slot(page,id),count=await target.count(),facts={caseId:current,count};
  if(count===1)Object.assign(facts,await target.evaluate(element=>{const rect=element.getBoundingClientRect(),style=getComputedStyle(element);return {display:style.display,width:rect.width,height:rect.height};}));
  slotGeometry.push(facts);if(slotGeometry.length>12)slotGeometry.shift();
  ensure(count===1&&Number.isFinite(facts.width)&&Number.isFinite(facts.height)&&facts.width>0&&facts.height>0,'EMPTY_SLOT_NOT_CLICKABLE');
  await target.click();await cspPhase(page,phase+'.CLICK.AFTER');await page.keyboard.press('End');await cspPhase(page,phase+'.END.AFTER');
  if(bold){await cspPhase(page,phase+'.TOGGLE_ON.BEFORE');await rich(page).locator('.es-toolbar').getByRole('button',{name:'Ж',exact:true}).click();await immediateToolbarFocus(target,'bold-on');await cspPhase(page,phase+'.TOGGLE_ON.AFTER');}
  await cspPhase(page,phase+'.KEYBOARD.BEFORE');await page.keyboard.type(value);await cspPhase(page,phase+'.KEYBOARD.AFTER');
  if(bold){await cspPhase(page,phase+'.TOGGLE_OFF.BEFORE');await rich(page).locator('.es-toolbar').getByRole('button',{name:'Ж',exact:true}).click();await immediateToolbarFocus(target,'bold-off');await cspPhase(page,phase+'.TOGGLE_OFF.AFTER');}
  ensure((await target.textContent()).includes(value),'ACTUAL_SLOT_INPUT_DID_NOT_CHANGE');
  await cspPhase(page,phase+'.AFTER');
}
async function collectNativeFacts(page){
  const facts=await page.evaluate(()=>globalThis.__nativeDeleteFacts||[]);if(!facts.length)return;
  const cases=new Set(facts.map(item=>item.caseId));for(let index=nativeKeyFacts.length-1;index>=0;index--)if(cases.has(nativeKeyFacts[index].caseId))nativeKeyFacts.splice(index,1);
  nativeKeyFacts.push(...facts);if(nativeKeyFacts.length>24)nativeKeyFacts.splice(0,nativeKeyFacts.length-24);
}
async function interiorDeletePositive(page,id){
  const target=slot(page,id),before=await target.textContent();
  await target.evaluate((element,{baseline,caseId})=>{
    const surface=element.closest('.es-editor-surface');globalThis.__nativeDeleteFacts=[];
    const number=value=>Number.isSafeInteger(value)&&value>=0?value:null;
    const types=['doc','paragraph','heading','blockquote','listItem','esProtectedParent','esProtectedSlot','esProtected','text','hardBreak'];
    const type=value=>types.includes(value)?value:'other';
    const capture=(event,phase)=>{
      const selected=getSelection(),parent=node=>node?.nodeType===Node.ELEMENT_NODE?node:node?.parentElement;
      const text=element.textContent,suffix=text===baseline+'XYZ'?'XYZ':text===baseline+'XY'?'XY':text===baseline+'X'?'X':text===baseline?'original':'other';
      const facts={caseId,key:event.key,phase,defaultPrevented:event.defaultPrevented,suffix,length:text.length,
        collapsed:selected?.isCollapsed??null,anchorOffset:number(selected?.anchorOffset),focusOffset:number(selected?.focusOffset),
        anchorExpectedSlot:parent(selected?.anchorNode)?.closest('[data-editor-protected-slot]')===element,
        focusExpectedSlot:parent(selected?.focusNode)?.closest('[data-editor-protected-slot]')===element,pm:{available:false}};
      try{const view=surface.editor.view,state=view.state,selection=state.selection;
        facts.pm={available:true,from:number(selection.from),to:number(selection.to),parentType:type(selection.$from.parent.type.name),parentOffset:number(selection.$from.parentOffset)};
        const map=(node,offset,bias)=>{if(!node)return null;try{return number(view.posAtDOM(node,offset,bias));}catch{return null;}};
        facts.anchorMinus=map(selected?.anchorNode,selected?.anchorOffset,-1);facts.anchorPlus=map(selected?.anchorNode,selected?.anchorOffset,1);
        facts.focusMinus=map(selected?.focusNode,selected?.focusOffset,-1);facts.focusPlus=map(selected?.focusNode,selected?.focusOffset,1);
      }catch{}
      globalThis.__nativeDeleteFacts.push(facts);if(globalThis.__nativeDeleteFacts.length>12)globalThis.__nativeDeleteFacts.shift();
    };
    document.addEventListener('keydown',event=>{
      if(!surface.isConnected||!surface.contains(event.target)||!['ArrowLeft','Delete','Backspace'].includes(event.key))return;
      const selected=getSelection(),node=selected?.focusNode,parent=node?.nodeType===Node.ELEMENT_NODE?node:node?.parentElement;
      if(parent?.closest('[data-editor-protected-slot]')!==element)return;
      capture(event,'capture');queueMicrotask(()=>capture(event,'microtask'));
    },true);
  },{baseline:before,caseId:current});
  await target.click();await page.keyboard.press('End');
  ensure(before.length>0,'INTERIOR_DELETE_REQUIRES_TEXT_CONTROL');await page.keyboard.type('XYZ');
  ensure(await target.textContent()===before+'XYZ','INTERIOR_SENTINEL_INPUT_FAILED');
  await page.keyboard.press('Backspace');ensure(await target.textContent()===before+'XY','INTERIOR_BACKSPACE_NOT_APPLIED');
  await page.keyboard.press('ArrowLeft');await page.keyboard.press('Delete');ensure(await target.textContent()===before+'X','INTERIOR_DELETE_NOT_APPLIED');
  await page.keyboard.press('Backspace');ensure(await target.textContent()===before,'INTERIOR_DELETE_DID_NOT_RESTORE_TEXT');
  await collectNativeFacts(page);
}
try{
  ensure(diagnosticScope===undefined||diagnosticScope==='diagnostic-employee-csp','CLOSED_DIAGNOSTIC_SCOPE');
  const seed=JSON.parse(fs.readFileSync('/private/editor-seed.json','utf8')),inputs=JSON.parse(fs.readFileSync('/inputs/inputs.json','utf8'));ensure(seed.pageIds?.length===2&&seed.accounts?.owner&&seed.accounts?.employee,'SEED_CONTRACT');
  const pageId=seed.pageIds[0],prefix='/manage/pages/'+pageId+'/edit/';
  browser=await chromium.launch({headless:true});const ownerContext=await context(),owner=await login(ownerContext,seed.accounts.owner),ids=[];
  let mint,firstVersion,replaceMint;
  await check('EUI-001',['I07-001'],async()=>{
    const before=await observe();
    for(const [name,pageId] of [['valid.png',seed.pageIds[0]],['valid.jpg',seed.pageIds[1]]]){
      const spec=inputs[name],data=fs.readFileSync('/inputs/'+name);ensure(spec?.name===name&&data.length===spec.bytes&&sha(data)===spec.sha256,'SYNTHETIC_INPUT_SHA');
      await owner.goto(safe('/manage/media/?page='+pageId));const form=owner.locator('form[data-media-upload]');await form.locator('[name=image]').setInputFiles({name,mimeType:spec.mime,buffer:data});
      await Promise.all([owner.waitForNavigation({timeout:30000}),form.getByRole('button',{name:'Добавить изображение',exact:true}).click()]);
      const id=await owner.locator('[data-uploaded-asset-id]').getAttribute('data-uploaded-asset-id');ensure(id&&!ids.includes(id),'NATIVE_UPLOAD_MARKER');ids.push(id);
      const state=await observe();ensure(asset(state,id).status==='ready'&&asset(state,id).files.length===3,'ACTUAL_WORKER_READY');ensure(part(state,id,'private-source').physical?.sha256===spec.sha256,'ACTUAL_UPLOAD_SOURCE_SHA');
    }
    const state=await observe();ensure(row(state,pageId).currentId===row(before,pageId).currentId,'UPLOAD_PUBLISHED');ensure(part(state,ids[0],'main').physical.sha256!==part(state,ids[1],'main').physical.sha256,'ASSETS_NOT_DISTINGUISHABLE');
    await owner.goto(safe(prefix));await ready(owner);await text(owner,'<p>TOP BLOCK</p><p>BOTTOM BLOCK</p>');await checked(owner);await write(owner);return {nativePngJpeg:true,realWorkerDistinctBytes:true};
  });
  await check('EUI-002',['I07-002','I07-003','I07-021'],async()=>{
    const before=await observe();await rich(owner).locator('.es-editor-surface').focus();await owner.keyboard.press('Control+Home');mint=await issued(owner,ids[0]);
    const raw=await rich(owner).locator('.es-html-source').inputValue();ensure(raw.indexOf('TOP BLOCK')<raw.indexOf(mint.ids.markerId)&&raw.indexOf(mint.ids.markerId)<raw.indexOf('BOTTOM BLOCK'),'INSERT_NOT_BETWEEN_ORDINARY_BLOCKS');
    ensure(!await atom(owner,mint.ids.markerId).isVisible(),'UNCHECKED_INSERT_RENDERED_LIVE');ensure((await observe()).domainHash===before.domainHash,'ISSUE_OR_RAM_INSERT_PUBLISHED');
    await checked(owner);const image=atom(owner,mint.ids.markerId).locator('img');await bytes(ownerContext.request,await imageUrl(image),part(before,ids[0],'preview'));
    ensure(await atom(owner,mint.ids.markerId).getAttribute('contenteditable')==='false','APPROVED_ATOM_EDITABLE');ensure((await observe()).domainHash===before.domainHash,'CHECK_INSERT_PUBLISHED');return {nativeToolbarIssue:true,stagedRamBeforeCheck:true,parentApprovedLoadedImage:true};
  });
  await check('EUI-003',['I07-005','I07-006','I07-007','I07-015'],async()=>{
    await typeSlot(owner,mint.ids.slotBeforeId,'OWNER SLOT é 😀 ');
    await interiorDeletePositive(owner,mint.ids.slotBeforeId);
    await typeSlot(owner,mint.ids.slotAfterId,'OWNER BOLD',{bold:true});
    const afterSlot=slot(owner,mint.ids.slotAfterId);await afterSlot.click();await owner.keyboard.press('End');await owner.keyboard.press('Enter');await owner.keyboard.type('NATIVE BREAK');
    ensure(await afterSlot.locator('br:not(.ProseMirror-trailingBreak)').count()>0&&(await afterSlot.textContent()).includes('NATIVE BREAK'),'NATIVE_ENTER_DID_NOT_CREATE_SLOT_BREAK');
    const checkResponse=owner.waitForResponse(value=>new URL(value.url()).pathname===prefix+'check/'&&value.request().method()==='POST');await checked(owner);const response=await checkResponse,request=response.request().postDataJSON(),review=await response.json();
    ensure(request.changes.main_text.includes('data-es-media-intent')&&request.changes.main_text.includes(mint.permit),'RAM_PERMIT_NOT_REPROJECTED');
    ensure(review.embeddedMedia.main_text[0].markerId===mint.ids.markerId&&review.embeddedMedia.main_text[0].imageId===mint.ids.imageId,'RECHECK_CHANGED_ISSUED_IDS');
    const saveRequest=owner.waitForRequest(value=>new URL(value.url()).pathname===prefix+'save/'&&value.method()==='POST');await write(owner);const body=(await saveRequest).postData();ensure(!body.includes('data-es-media-intent')&&!body.includes(mint.permit),'PERMIT_LEAKED_TO_CANONICAL_SAVE');
    const state=await observe(),page=row(state,pageId);firstVersion=page.currentId;ensure(page.payload.main_text.includes('OWNER SLOT é 😀')&&page.payload.main_text.includes('<strong>OWNER BOLD</strong>'),'PM_EDIT_OR_FORMAT_NOT_COMMITTED');ensure(/<br\s*\/?>/u.test(page.payload.main_text)&&page.payload.main_text.includes('NATIVE BREAK'),'NATIVE_SLOT_BREAK_NOT_COMMITTED');
    ensure(page.payload.embedded_images.some(image=>image.id===mint.ids.imageId&&image.asset_id===ids[0]),'EMBEDDED_REFERENCE_NOT_DERIVED');ensure(asset(state,ids[0]).usages.some(use=>use.kind==='current_page'&&use.consumerId===pageId&&use.slot==='embedded:'+mint.ids.imageId),'EMBEDDED_CURRENT_LEDGER_MISSING');
    await owner.reload();await ready(owner);await bytes(ownerContext.request,await imageUrl(atom(owner,mint.ids.markerId).locator('img')),part(state,ids[0],'preview'));return {nativeSlotEdits:true,nativeInteriorBackspaceDelete:true,nativeEnterHardBreak:true,nativeBold:true,repeatCheckSameIds:true,canonicalSaveNoPermit:true};
  });
  await check('EUI-004',['I07-005','I07-008','I07-009','I07-022'],async()=>{
    const employeeContext=await context(),employee=await employeeContext.newPage();await cspPhase(employee,'LOGIN.BEFORE');await login(employeeContext,seed.accounts.employee,employee);await cspPhase(employee,'LOGIN.AFTER');await cspPhase(employee,'EDITOR.READY.BEFORE');await employee.goto(safe(prefix));await ready(employee);await cspPhase(employee,'EDITOR.READY.AFTER');ensure(await employee.locator('[data-editor-embedded-action]').count()===0,'EMPLOYEE_OWNER_TOOLBAR_VISIBLE');
    const before=await observe(),map=row(before,pageId).payload.layout;await cspPhase(employee,'BYTES.BEFORE');await bytes(employeeContext.request,await imageUrl(atom(employee,mint.ids.markerId).locator('img')),part(before,ids[0],'preview'));await cspPhase(employee,'BYTES.AFTER');await typeSlot(employee,mint.ids.slotBeforeId,'EMPLOYEE 😀 ');await typeSlot(employee,mint.ids.slotAfterId,' EMPLOYEE MARK',{bold:true});
    await interiorDeletePositive(employee,mint.ids.slotBeforeId);
    const markerBefore=await atom(employee,mint.ids.markerId).getAttribute('data-editor-embedded-image-id'),textBefore=await slot(employee,mint.ids.slotBeforeId).textContent();
    const boundarySlot=slot(employee,mint.ids.slotBeforeId);
    await cspPhase(employee,'BOUNDARY.BEFORE');await boundarySlot.click();await boundarySelection(boundarySlot,'CLICK.AFTER');await cspPhase(employee,'BOUNDARY.CLICK.AFTER');
    if(diagnosticScope==='diagnostic-employee-csp'){
      await employee.keyboard.press('Home');await boundarySelection(boundarySlot,'HOME.AFTER');await cspPhase(employee,'BOUNDARY.HOME.AFTER');
      await boundarySelection(boundarySlot,'BACKSPACE.BEFORE');await employee.keyboard.press('Backspace');
    }else{await employee.keyboard.press('Home');await employee.keyboard.press('Backspace');}
    await boundarySelection(boundarySlot,'BACKSPACE.AFTER');await collectNativeFacts(employee);await cspPhase(employee,'BOUNDARY.BACKSPACE.AFTER');ensure(await atom(employee,mint.ids.markerId).getAttribute('data-editor-embedded-image-id')===markerBefore&&await boundarySlot.textContent()===textBefore,'PROTECTED_BOUNDARY_DELETE_CHANGED_DOC');
    await cspPhase(employee,'CHECK.BEFORE');await checked(employee);await cspPhase(employee,'CHECK.AFTER');await cspPhase(employee,'WRITE.BEFORE');await write(employee);await cspPhase(employee,'WRITE.AFTER');const after=await observe();ensure(JSON.stringify(row(after,pageId).payload.layout)===JSON.stringify(map),'EMPLOYEE_CHANGED_PROTECTED_MAP');ensure(row(after,pageId).payload.main_text.includes('EMPLOYEE 😀'),'EMPLOYEE_TEXT_NOT_SAVED');
    const csrf=await employee.locator('[data-editor-page] [name=csrfmiddlewaretoken]').inputValue();
    for(const [index,changed] of [row(after,pageId).payload.main_text.replace(mint.ids.markerId,crypto.randomUUID()),row(after,pageId).payload.main_text.replace(ids[0],ids[1])].entries()){
      const payload={protocol:'page-editor-v1',generation:1,baseRevisionId:row(after,pageId).currentId,editingFrom:'current',draftBasis:null,stageId:null,changes:{main_text:changed}};
      await cspPhase(employee,'DIRECT_API.'+index+'.BEFORE');const denied=await employeeContext.request.post(safe(prefix+'check/'),{maxRedirects:0,headers:{'Content-Type':'application/json','X-CSRFToken':csrf},data:payload});await cspPhase(employee,'DIRECT_API.'+index+'.AFTER');ensure(denied.status()===400&&(await denied.json()).code==='EDITOR_INPUT_REJECTED','DIRECT_EMPLOYEE_TAMPER_ACCEPTED');
    }
    await cspPhase(employee,'LATE_BYTES.BEFORE');const imagePath=await imageUrl(atom(employee,mint.ids.markerId).locator('img')),visitor=await context(),other=await context();await login(other,seed.accounts.other);
    ensure((await visitor.request.get(safe(imagePath),{maxRedirects:0})).status()===401,'VISITOR_EMBEDDED_BYTES_ALLOWED');ensure((await other.request.get(safe(imagePath),{maxRedirects:0})).status()===403,'FOREIGN_EMBEDDED_BYTES_ALLOWED');
    await cspPhase(employee,'LATE_BYTES.AFTER');
    ensure((await observe()).domainHash===after.domainHash,'DIRECT_TAMPER_MUTATED_STATE');await invariant(employee);diagnosticPage=owner;return {actualEmployeeTextAndFormat:true,nativeInteriorBackspaceDelete:true,rapidHomeBackspaceBoundaryPreserved:true,boundaryDeletePrevented:true,directServerTamperDenied:true,contextualBytesAcl:true};
  });
  await check('EUI-005',['I07-004','I07-014','I07-024'],async()=>{
    await owner.goto(safe(prefix));await ready(owner);await navigate(owner,owner.getByRole('link',{name:'История и Stable',exact:true}));await navigate(owner,owner.locator('[data-version-id="'+firstVersion+'"]').getByRole('link',{name:'Просмотреть',exact:true}));await navigate(owner,owner.locator('form[data-stable-set] button'));
    await owner.goto(safe(prefix));await ready(owner);const before=await observe();replaceMint=await issued(owner,ids[1],mint.ids.markerId);ensure(replaceMint.ids.imageId!==mint.ids.imageId,'REPLACE_REUSED_OLD_REFERENCE');
    for(const key of ['parentId','markerId','slotBeforeId','slotAfterId','layoutId'])ensure(replaceMint.ids[key]===mint.ids[key],'REPLACE_MOVED_PLACEMENT');await checked(owner);await write(owner);const after=await observe();
    ensure(row(after,pageId).payload.embedded_images.some(image=>image.id===replaceMint.ids.imageId&&image.asset_id===ids[1]),'REPLACE_NOT_COMMITTED');ensure(asset(after,ids[0]).usages.some(use=>use.kind==='stable_version'&&use.consumerId===firstVersion),'OLD_STABLE_REFERENCE_LOST');
    ensure(row(after,pageId).history.find(version=>version.id===firstVersion)?.payloadHash===row(before,pageId).history.find(version=>version.id===firstVersion)?.payloadHash,'REPLACE_MUTATED_STABLE_PAYLOAD');
    for(const file of asset(after,ids[0]).files)ensure(file.physical?.sha256===file.sha256,'REPLACE_UNLINKED_OLD_FILE');await owner.reload();await ready(owner);await bytes(ownerContext.request,await imageUrl(atom(owner,mint.ids.markerId).locator('img')),part(after,ids[1],'preview'));return {nativeStable:true,newReferenceSamePlacement:true,oldStableFilesRetained:true};
  });
  await check('EUI-006',['I07-012','I07-014'],async()=>{
    const before=await observe(),draftMint=await issued(owner,ids[0],mint.ids.markerId);await checked(owner);await write(owner,'draft');const drafted=await observe(),draft=drafted.drafts.find(value=>value.pageId===pageId);ensure(draft&&row(drafted,pageId).currentId===row(before,pageId).currentId,'DRAFT_IMAGE_PUBLISHED');
    const url=new URL(owner.url());ensure(url.searchParams.get('source')==='owner-draft'&&url.searchParams.get('draftId')===draft.id&&url.searchParams.get('draftRevision')===String(draft.revision),'DRAFT_ACK_SOURCE_URL');await owner.reload();await ready(owner);
    const image=atom(owner,mint.ids.markerId).locator('img'),src=await imageUrl(image);ensure(src.includes('source=owner-draft'),'DRAFT_IMAGE_NOT_CONTEXTUAL');await bytes(ownerContext.request,src,part(drafted,ids[0],'preview'));await checked(owner);await write(owner);const after=await observe();ensure(!after.drafts.some(value=>value.pageId===pageId)&&row(after,pageId).payload.embedded_images.some(image=>image.id===draftMint.ids.imageId),'DRAFT_APPLY_LOST_IMAGE');return {draftPrivateLoadedBytes:true,separateApply:true};
  });
  await check('EUI-007',['I07-013','I07-014','I07-024'],async()=>{
    await owner.goto(safe(prefix));await ready(owner);await navigate(owner,owner.getByRole('link',{name:'История и Stable',exact:true}));await navigate(owner,owner.locator('[data-version-id="'+firstVersion+'"]').getByRole('link',{name:'Просмотреть',exact:true}));await navigate(owner,owner.locator('form[data-restore-prepare] button'));await owner.locator('form[data-restore-stage] [name=confirm_input_replacement]').check();await navigate(owner,owner.locator('form[data-restore-stage] button'));const before=await observe();await navigate(owner,owner.locator('a[data-restore-editor]'));await ready(owner);
    const source=await imageUrl(atom(owner,mint.ids.markerId).locator('img'));ensure(source.includes('source=restore-stage'),'STAGE_IMAGE_NOT_CONTEXTUAL');await bytes(ownerContext.request,source,part(before,ids[0],'preview'));await typeSlot(owner,mint.ids.slotBeforeId,'STAGED NATIVE EDIT ');await checked(owner);ensure(row(await observe(),pageId).currentId===row(before,pageId).currentId,'STAGE_CHECK_PUBLISHED');await write(owner);const after=await observe();ensure(after.stages.some(stage=>stage.status==='consumed'&&stage.pageId===pageId),'STAGE_NOT_CONSUMED');ensure(row(after,pageId).payload.main_text.includes('STAGED NATIVE EDIT'),'STAGE_NATIVE_EDIT_NOT_SAVED');return {actualHistoryCandidateImage:true,nativeStageEditExplicitSave:true};
  });
  await check('EUI-008',['I07-021','I07-025'],async()=>{
    await owner.goto(safe(prefix));await ready(owner);const canary='EMBEDDED_RAW_CANARY',requests=[];const listener=request=>{if(request.url().includes(canary))requests.push(true);};owner.on('request',listener);
    await owner.evaluate(value=>{const descriptor=Object.getOwnPropertyDescriptor(Element.prototype,'innerHTML'),parse=DOMParser.prototype.parseFromString;globalThis.__rawCalls=0;globalThis.__restoreRaw=()=>{Object.defineProperty(Element.prototype,'innerHTML',descriptor);DOMParser.prototype.parseFromString=parse;};Object.defineProperty(Element.prototype,'innerHTML',{...descriptor,set(input){if(String(input).includes(value))globalThis.__rawCalls++;return descriptor.set.call(this,input);}});DOMParser.prototype.parseFromString=function(input,...args){if(String(input).includes(value))globalThis.__rawCalls++;return parse.call(this,input,...args);};},canary);
    try{for(const kind of ['paste','drop']){await rich(owner).locator('.es-editor-surface').evaluate((surface,{kind,canary})=>{const transfer=new DataTransfer();transfer.setData('text/html','<img src="https://outside.invalid/'+canary+'" onerror="globalThis.__unsafe++"><style>'+canary+'{color:red}</style>');transfer.setData('text/plain',canary);surface.dispatchEvent(kind==='paste'?new ClipboardEvent('paste',{clipboardData:transfer,bubbles:true,cancelable:true}):new DragEvent('drop',{dataTransfer:transfer,bubbles:true,cancelable:true}));},{kind,canary});await owner.locator('.es-review textarea').waitFor();ensure((await owner.locator('.es-review textarea').inputValue()).includes(canary),'RAW_NOT_STAGED_IN_RAM');ensure(!(await rich(owner).locator('.es-editor-surface').innerHTML()).includes(canary),'RAW_ENTERED_LIVE_PM');await owner.locator('.es-review').getByRole('button',{name:'Отмена',exact:true}).click();}
      ensure(await owner.evaluate(()=>globalThis.__rawCalls===0)&&requests.length===0,'RAW_PARSED_OR_FETCHED');
    }finally{await owner.evaluate(()=>globalThis.__restoreRaw());owner.off('request',listener);}
    await imageUrl(atom(owner,mint.ids.markerId).locator('img'));await invariant(owner);await owner.screenshot({path:'/output/embedded-desktop.png',fullPage:true,caret:'initial'});await invariant(owner);await owner.setViewportSize({width:390,height:844});await invariant(owner);await owner.screenshot({path:'/output/embedded-mobile.png',fullPage:true,caret:'initial'});await invariant(owner);return {rawPasteDropInert:true,strictCsp:true,desktop1280:true,mobile390:true};
  });
  output({kind:'result',status:'PASS',scope:'EMBEDDED_8',groups,diagnostics:{toolbarFocus,slotGeometry,cspPhases,boundarySelections,nativeKeyFacts}});
}catch(error){if(error instanceof DiagnosticStop&&diagnosticScope==='diagnostic-employee-csp'){
  output({kind:'result',status:'PASS',scope:'DIAGNOSTIC_ONLY',groups,diagnostics:{toolbarFocus,slotGeometry,cspPhases,boundarySelections,nativeKeyFacts}});
}else{const facts={lastResponses,pageErrorCodes,slotGeometry,toolbarFocus,cspPhases,boundarySelections,nativeKeyFacts};if(diagnosticPage&&!diagnosticPage.isClosed()&&new URL(diagnosticPage.url()).pathname.includes('/edit/')){try{await collectNativeFacts(diagnosticPage);Object.assign(facts,await diagnosticPage.evaluate(()=>({csp:globalThis.__mediaCsp||[],cspDetails:globalThis.__cspDetails||[],styleMutations:globalThis.__styleMutations||[]})));await diagnosticPage.screenshot({path:'/output/embedded-failure.png',fullPage:true,caret:'initial'});}catch{facts.diagnosticUnavailable=true;}}output({kind:'result',status:'FAIL',caseId:current,errorClass:error?.constructor?.name||'Error',errorCode:fixed(error?.message),groups,diagnostics:facts});process.exitCode=1;}
}finally{for(const ctx of contexts)await ctx.close().catch(()=>{});if(browser)await browser.close().catch(()=>{});channel.close();}
