// TP2 native controls through existing Nginx. No evaluate/setter product actions.
import fs from 'node:fs';
import readline from 'node:readline';
import {chromium} from '/tests/node_modules/playwright/index.mjs';
const origin='http://host.docker.internal:8767',groups=[],contexts=[],pending=new Map();
const ensure=(yes,code)=>{if(!yes)throw new Error(code);};
const fixed=value=>typeof value==='string'&&/^[A-Z0-9_]{1,100}$/.test(value)?value:'TABLE_BROWSER_FAILED';
const emit=value=>process.stdout.write(JSON.stringify(value)+'\n');
let browser,seed,owner,ownerContext,current='START',serial=0;
const pageErrors=[],responses=[],unexpected=[],invariantFacts=[],paddingDiagnostics=[];
const channel=readline.createInterface({input:process.stdin,terminal:false});
channel.on('line',line=>{try{const value=JSON.parse(line),entry=pending.get(value.id);
  if(value.kind!=='observation'||!entry)throw new Error('CLOSED_OBSERVER_PROTOCOL');pending.delete(value.id);entry(value.value);
}catch{process.exitCode=1;}});
function observe(operation='observe'){return new Promise((resolve,reject)=>{const id=++serial;
  const timer=setTimeout(()=>{pending.delete(id);reject(new Error('OBSERVER_TIMEOUT'));},30000);
  pending.set(id,value=>{clearTimeout(timer);resolve(value);});emit({kind:'observe',id,operation,caseId:current});});}
const pageRow=(state,id)=>{const found=state.pages.find(row=>row.id===id);ensure(found,'OWN_PAGE_OBSERVER_MISSING');return found;};
const prefix=id=>'/manage/pages/'+id+'/edit/';
const url=value=>{ensure(value.startsWith('/')&&new URL(value,origin).origin===origin,'CLOSED_ORIGIN');return origin+value;};
const action=(page,name)=>page.locator('.es-page-actions [data-editor-action="'+name+'"]');
async function context(){const ctx=await browser.newContext({viewport:{width:1280,height:900}});contexts.push(ctx);
  await ctx.route('**/*',route=>{if(new URL(route.request().url()).origin===origin)return route.continue();unexpected.push('EXTERNAL_REQUEST');return route.abort();});
  await ctx.addInitScript(()=>{
    globalThis.__tableCsp=[];globalThis.__tableCspCounts={};globalThis.__tableCspTotal=0;
    document.addEventListener('securitypolicyviolation',event=>{
      let directive=/^[a-z-]{1,40}$/.test(event.effectiveDirective)?event.effectiveDirective:'unknown';
      const counts=globalThis.__tableCspCounts;
      if(!Object.hasOwn(counts,directive)&&Object.keys(counts).length>=8)directive='other';
      counts[directive]=Math.min(10000,(counts[directive]||0)+1);
      globalThis.__tableCspTotal=Math.min(10000,globalThis.__tableCspTotal+1);
      if(globalThis.__tableCsp.length>=4)return;
      let source='unknown';
      try{const candidate=new URL(event.sourceFile).pathname.split('/').at(-1);
        if(/^[A-Za-z0-9._-]{1,60}$/.test(candidate))source=candidate;}catch{}
      globalThis.__tableCsp.push({directive,sourceBasename:source,
        line:Number.isInteger(event.lineNumber)&&event.lineNumber>=0&&event.lineNumber<=10000000?event.lineNumber:null,
        disposition:['enforce','report'].includes(event.disposition)?event.disposition:'unknown'});
    });
  });
  ctx.on('page',page=>page.on('pageerror',()=>pageErrors.push('PAGE_ERROR')));return ctx;}
async function login(ctx,account){const page=await ctx.newPage();await page.goto(url('/manage/login/'));
  await page.locator('[name=username]').fill(account.username);await page.locator('[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(url('/manage/'),{timeout:15000}),page.locator('form[action="/manage/login/"] button').click()]);return page;}
async function ready(page,id){await page.goto(url(prefix(id)));await page.locator('.es-page-actions').waitFor();}
async function checked(page,expected=200){const awaited=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/edit/check/'),{timeout:30000});
  await action(page,'check').click();const response=await awaited;responses.push({operation:'check',status:response.status()});
  ensure(response.status()===expected,'TABLE_CHECK_STATUS');
  await page.waitForFunction(()=>{const button=document.querySelector('.es-page-actions [data-editor-action=check]');return button&&!button.disabled;},null,{timeout:30000});
  if(expected!==200)return;
  const accept=page.locator('.es-review').getByRole('button',{name:'Принять проверенный вариант',exact:true});
  if(await accept.isVisible())await accept.click();
  await page.waitForFunction(()=>document.querySelector('[data-editor-dirty]')?.textContent.includes('Проверено.'),null,{timeout:30000});}
async function saved(page){const awaited=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/edit/save/'),{timeout:30000});
  await action(page,'save').click();const response=await awaited;responses.push({operation:'save',status:response.status()});
  ensure(response.status()===200,'TABLE_SAVE_STATUS');
  await page.waitForFunction(()=>document.querySelector('[data-editor-dirty]')?.textContent==='Сохранение подтверждено.',null,{timeout:30000});}
async function captureInvariant(page,checkpoint){
  const facts=await page.evaluate(()=>{
    const nodes=[...document.querySelectorAll('[data-editor-field] [style],[data-editor-field] script')];
    const safe=value=>/^[a-z0-9:-]{1,32}$/.test(value)?value:'unknown';
    return {csp:globalThis.__tableCsp||[],cspDirectiveCounts:globalThis.__tableCspCounts||{},cspTotal:globalThis.__tableCspTotal||0,
      storage:localStorage.length+sessionStorage.length,storageCounts:{local:localStorage.length,session:sessionStorage.length},
      inline:nodes.length,inlineNodes:nodes.slice(0,4).map(node=>({tag:safe(node.tagName.toLowerCase()),
        attributeNames:node.getAttributeNames().slice(0,4).map(safe)}))};
  });
  invariantFacts.push({caseId:current,checkpoint,...facts});if(invariantFacts.length>6)invariantFacts.shift();return facts;
}
async function invariant(page){const facts=await captureInvariant(page,'invariant');
  ensure(pageErrors.length===0,'PAGE_ERROR');ensure(unexpected.length===0,'EXTERNAL_REQUEST');
  ensure(facts.csp.length===0&&facts.storage===0&&facts.inline===0,'TABLE_CSP_STORAGE_INLINE');}
async function group(id,fn){current=id;const facts=await fn();await invariant(owner);groups.push({id,status:'PASS',...facts});}
const protectedPayload=payload=>JSON.stringify(Object.fromEntries(Object.entries(payload).filter(([key])=>key!=='main_text')));

const field=page=>page.locator('[data-editor-field=main_text]');
const surface=page=>field(page).locator('.es-editor-surface');
const tables=page=>surface(page).locator('[data-editor-table] > table');
const tableTool=(page,name)=>field(page).locator('[data-editor-table-action="'+name+'"]');
const cellAt=(page,table,row,column)=>tables(page).nth(table).locator(':scope > tbody > tr').nth(row).locator(':scope > td,:scope > th').nth(column);
async function insert(page){await surface(page).locator('p').filter({hasText:'TABLE START A'}).first().click();await page.keyboard.press('End');await tableTool(page,'insert').click();}
async function paddingDiagnostic(page){return field(page).evaluate(root=>{
  const surface=root.querySelector('.es-editor-surface'),tables=[...surface.querySelectorAll('[data-editor-table] > table')];
  const anchor=window.getSelection()?.anchorNode,element=anchor?.nodeType===1?anchor:anchor?.parentElement;
  const cell=element?.closest('td,th'),selected=cell?.closest('table');
  const pixels=value=>/^(?:[0-9]|[12][0-9]|3[0-2])px$/.test(value)?Number(value.slice(0,-2)):null;
  const rows=table=>[...table.querySelectorAll(':scope > tbody > tr')];
  const selection=selected&&surface.contains(selected)?{table:tables.indexOf(selected),row:rows(selected).indexOf(cell.parentElement),column:[...cell.parentElement.children].indexOf(cell)}:null;
  const rules=[...document.querySelector('[data-editor-stylesheet]').sheet.cssRules]
    .filter(rule=>rule.style?.getPropertyValue('padding')&&/tbody.*td.*th/.test(rule.selectorText||''));
  const status=root.closest('[data-editor-page]')?.querySelector('[data-editor-status]')?.textContent||'';
  return {selection,tableCount:tables.length,tables:tables.slice(0,4).map(table=>({rowCount:rows(table).length,
    rows:rows(table).slice(0,8).map(row=>({section:['head','body'].includes(row.dataset.editorTableSection)?row.dataset.editorTableSection:'unknown',
      cellCount:row.children.length,paddingPixels:[...row.children].slice(0,8).map(cell=>pixels(getComputedStyle(cell).paddingTop))}))})),
    cssPaddingRuleCount:rules.length,cssPaddingRules:rules.slice(0,6).map(rule=>({
      classes:(rule.selectorText.match(/\.esf-[a-f0-9]+-n[0-9]+/g)||[]).slice(0,2),paddingPixels:pixels(rule.style.getPropertyValue('padding'))})),
    statusCategory:/не выполнено|Не удалось|неподдерж/.test(status)?'refusal':/Загрузка/.test(status)?'loading':/Провер/.test(status)?'check':'other'};
});}
async function padding(page,table,value){const record={caseId:current,targetTable:table,
  requestedPadding:/^(?:[0-9]|[12][0-9]|3[0-2])$/.test(value)?Number(value):null};
  paddingDiagnostics.push(record);if(paddingDiagnostics.length>4)paddingDiagnostics.shift();
  await cellAt(page,table,1,0).click();record.afterSelectedCell=await paddingDiagnostic(page);
  await field(page).locator('[data-editor-table-padding]').fill(value);record.afterFill=await paddingDiagnostic(page);
  await tableTool(page,'padding').click();record.afterCommand=await paddingDiagnostic(page);}
async function tableFacts(page){return tables(page).evaluateAll(nodes=>nodes.map(table=>({rows:[...table.querySelectorAll(':scope > tbody > tr')].map(row=>({section:row.dataset.editorTableSection,cells:[...row.children].map(cell=>({tag:cell.tagName,text:cell.textContent,padding:getComputedStyle(cell).paddingTop,background:getComputedStyle(cell).backgroundColor}))}))})));}
async function selectedCell(page){return surface(page).evaluate(root=>{const node=window.getSelection()?.anchorNode,element=node?.nodeType===1?node:node?.parentElement,cell=element?.closest('td,th'),table=cell?.closest('table');if(!cell||!table||!root.contains(table))return null;const row=cell.parentElement;return {row:[...table.querySelectorAll(':scope > tbody > tr')].indexOf(row),column:[...row.children].indexOf(cell)};});}
async function ruleCount(page){return page.evaluate(()=>[...document.querySelector('[data-editor-stylesheet]').sheet.cssRules].filter(rule=>rule.style?.getPropertyValue('padding')&&/tbody.*td.*th/.test(rule.selectorText||'')).length);}
function browserMemory(){const result={};for(const name of ['current','peak','max']){const fd=fs.openSync('/sys/fs/cgroup/memory.'+name,'r');try{const buffer=Buffer.alloc(65),length=fs.readSync(fd,buffer,0,65,0),value=buffer.subarray(0,length).toString().trim();result[name+'Bytes']=/^\d{1,20}$/.test(value)?Number(value):null;}finally{fs.closeSync(fd);}}return result;}
async function deniedMain(page,ctx,id,html){const response=await ctx.request.get(url(prefix(id)+'state/'));ensure(response.status()===200,'TABLE_STATE_HTTP');const state=await response.json(),csrf=await page.locator('[data-editor-page] [name=csrfmiddlewaretoken]').inputValue();const denied=await ctx.request.post(url(prefix(id)+'check/'),{headers:{'Content-Type':'application/json','X-CSRFToken':csrf},data:{protocol:'page-editor-v1',generation:state.generation,baseRevisionId:state.baseRevisionId,editingFrom:'current',draftBasis:null,stageId:null,changes:{main_text:html}}});ensure(denied.status()===403,'TABLE_PERMISSION_DENIAL');}

try{
  seed=JSON.parse(fs.readFileSync('/private/table-seed.json','utf8'));
  browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});ownerContext=await context();owner=await login(ownerContext,seed.accounts.owner);
  const [a,b]=seed.pageIds;
  await group('TP2-UI-001',async()=>{
    const before=pageRow(await observe(),a);await ready(owner,a);await surface(owner).waitFor();await insert(owner);
    ensure(await tables(owner).count()===1,'TABLE_INSERT_NOT_RICH');
    const initial=await tableFacts(owner);ensure(initial[0].rows.length===3&&initial[0].rows.every(row=>row.cells.length===2),'TABLE_INITIAL_GEOMETRY');
    ensure(initial[0].rows[0].cells.every(cell=>cell.tag==='TH'),'TABLE_NO_HEADER');ensure(initial[0].rows.every(row=>row.cells.every(cell=>cell.padding==='4px')),'TABLE_DEFAULT_PADDING');
    await cellAt(owner,0,0,0).click();await owner.keyboard.insertText('Header 😀');
    await cellAt(owner,0,1,0).click();await owner.keyboard.insertText('Body é');
    await cellAt(owner,0,1,1).click();await field(owner).locator('.es-toolbar').getByRole('button',{name:'Ж',exact:true}).click();await owner.keyboard.insertText('Bold α');await field(owner).locator('.es-toolbar').getByRole('button',{name:'Ж',exact:true}).click();
    ensure(pageRow(await observe(),a).currentId===before.currentId,'TABLE_RAM_PUBLISHED');
    await checked(owner);await saved(owner);const after=pageRow(await observe(),a);
    ensure(after.payload.main_text.includes('<thead>')&&after.payload.main_text.includes('<tbody>')&&after.payload.main_text.includes('scope="col"'),'TABLE_CANONICAL_SECTIONS');
    ensure(after.payload.main_text.includes('<strong>Bold α</strong>')&&after.payload.main_text.includes('Header 😀'),'TABLE_MARKS_UNICODE');
    ensure(!/data-editor-|colgroup|style=|es-rich-table/.test(after.payload.main_text),'TABLE_PRIVATE_WIRE');
    ensure(!/<(?:td|th)[^>]*><p/.test(after.payload.main_text),'TABLE_SYNTHETIC_PARAGRAPH_WIRE');
    ensure(protectedPayload(after.payload)===protectedPayload(before.payload),'TABLE_PROTECTED_PRICE_CHANGED');
    await ready(owner,a);ensure(await tables(owner).count()===1,'TABLE_RELOAD_NOT_RICH');
    return {actualInsert:true,headerPlusTwoBody:true,unicodeMarks:true,actualPg:true,pricePreserved:true};
  });
  await group('TP2-UI-002',async()=>{
    await insert(owner);ensure(await tables(owner).count()===2,'TABLE_NEIGHBOUR_FIXTURE');
    await padding(owner,0,'0');await padding(owner,1,'32');
    const facts=await tableFacts(owner);
    ensure(facts[0].rows.every(row=>row.cells.every(cell=>cell.padding==='0px')),'TABLE_SELECTED_ZERO');
    ensure(facts[1].rows.every(row=>row.cells.every(cell=>cell.padding==='32px')),'TABLE_NEIGHBOUR_32');
    for(const table of facts){ensure(table.rows[0].cells[0].background===table.rows[2].cells[0].background,'TABLE_ZEBRA_RESETS');ensure(table.rows[0].cells[0].background!==table.rows[1].cells[0].background,'TABLE_ZEBRA_SECOND_ROW');}
    // Only the selected view's own input/button may retain this capability.
    // Real focus in another editor must consume the old pending target.
    await cellAt(owner,0,1,0).click();await field(owner).locator('[data-editor-table-padding]').fill('4');
    await owner.locator('[data-editor-field=intro_text] .es-editor-surface').click();
    await tableTool(owner,'padding').click();
    ensure(JSON.stringify(await tableFacts(owner))===JSON.stringify(facts),'TABLE_PADDING_BOOKMARK_CROSSED_FIELD');
    // A genuine Check replaces the approved view. Its old target cannot be
    // replayed through the unchanged toolbar after that rebuild.
    await cellAt(owner,0,1,0).click();await field(owner).locator('[data-editor-table-padding]').fill('4');
    await checked(owner);await tableTool(owner,'padding').click();
    ensure(JSON.stringify(await tableFacts(owner))===JSON.stringify(facts),'TABLE_PADDING_BOOKMARK_SURVIVED_REBUILD');
    await padding(owner,0,'4');const fresh=await tableFacts(owner);
    ensure(fresh[0].rows.every(row=>row.cells.every(cell=>cell.padding==='4px'))&&fresh[1].rows.every(row=>row.cells.every(cell=>cell.padding==='32px')),'TABLE_PADDING_FRESH_TARGET_FAILED');
    await padding(owner,0,'0');
    const unchanged=JSON.stringify(facts),before=pageRow(await observe(),a);
    for(const value of ['-1','33','NaN','0.5','']){await padding(owner,0,value);ensure(JSON.stringify(await tableFacts(owner))===unchanged,'TABLE_INVALID_PADDING_CHANGED');}
    ensure(pageRow(await observe(),a).currentId===before.currentId,'TABLE_INVALID_PADDING_PUBLISHED');
    const baselineRules=await ruleCount(owner);
    for(let index=0;index<4;index++){await padding(owner,0,'4');await padding(owner,0,'0');ensure(await ruleCount(owner)<=baselineRules,'TABLE_PADDING_RULE_LEAK');}
    await checked(owner);await saved(owner);await ready(owner,a);
    const restored=await tableFacts(owner);ensure(restored[0].rows[1].cells[0].padding==='0px'&&restored[1].rows[1].cells[0].padding==='32px','TABLE_PADDING_RELOAD');
    await captureInvariant(owner,'before-screenshot-1280');await owner.screenshot({path:'/evidence/table-1280.png',fullPage:true,caret:'initial'});await captureInvariant(owner,'after-screenshot-1280');
    await owner.setViewportSize({width:390,height:844});await captureInvariant(owner,'before-screenshot-390');await owner.screenshot({path:'/evidence/table-390.png',fullPage:true,caret:'initial'});await captureInvariant(owner,'after-screenshot-390');await owner.setViewportSize({width:1280,height:900});
    return {selectedOnly:true,padding0And32:true,zebraAcrossHeader:true,invalidNoMutation:true,cssomBounded:true};
  });
  await group('TP2-UI-003',async()=>{
    await cellAt(owner,0,1,0).click();await owner.keyboard.press('End');await owner.keyboard.insertText('Keyboard before');await owner.keyboard.press('Enter');await owner.keyboard.insertText('Keyboard after');
    await owner.keyboard.press('Tab');ensure(JSON.stringify(await selectedCell(owner))===JSON.stringify({row:1,column:1}),'TABLE_NATIVE_TAB_NEXT');
    await owner.keyboard.press('Shift+Tab');ensure(JSON.stringify(await selectedCell(owner))===JSON.stringify({row:1,column:0}),'TABLE_NATIVE_SHIFT_TAB_PREVIOUS');
    await cellAt(owner,0,2,1).click();const lastBoundary=JSON.stringify(await tableFacts(owner));await owner.keyboard.press('Tab');ensure(JSON.stringify(await tableFacts(owner))===lastBoundary,'TABLE_LAST_TAB_AUTOAPPENDED');
    ensure(JSON.stringify(await selectedCell(owner))===JSON.stringify({row:2,column:1}),'TABLE_LAST_TAB_MOVED_OUTSIDE');
    await cellAt(owner,0,1,0).click();const original=await tableFacts(owner),rows=original[0].rows.length;
    await tableTool(owner,'add-row').click();ensure((await tableFacts(owner))[0].rows.length===rows+1,'TABLE_ADD_ROW');
    const withAddedRow=await tableFacts(owner);
    await cellAt(owner,0,2,0).click();await owner.keyboard.insertText('AFTER-ROW');
    await owner.keyboard.press('Control+z');
    ensure((await tableFacts(owner))[0].rows.length===rows+1,'TABLE_TYPING_UNDO_REMOVED_ROW');
    ensure(JSON.stringify(await tableFacts(owner))===JSON.stringify(withAddedRow),'TABLE_TYPING_UNDO_CHANGED_STRUCTURE');
    await cellAt(owner,0,1,0).click();await owner.keyboard.press('Control+z');ensure((await tableFacts(owner))[0].rows.length===rows,'TABLE_UNDO_ONE_ROW_TRANSACTION');
    ensure(JSON.stringify(await tableFacts(owner))===JSON.stringify(original),'TABLE_UNDO_CHANGED_EXISTING_DATA');
    await owner.keyboard.press('Control+Shift+z');ensure((await tableFacts(owner))[0].rows.length===rows+1,'TABLE_REDO_ROW');
    await cellAt(owner,0,2,0).click();await tableTool(owner,'delete-row').click();ensure((await tableFacts(owner))[0].rows.length===rows,'TABLE_DELETE_EMPTY_ROW');
    await cellAt(owner,0,1,0).click();await tableTool(owner,'add-column').click();ensure((await tableFacts(owner))[0].rows.every(row=>row.cells.length===3),'TABLE_ADD_COLUMN');
    await cellAt(owner,0,1,1).click();await tableTool(owner,'delete-column').click();ensure((await tableFacts(owner))[0].rows.every(row=>row.cells.length===2),'TABLE_DELETE_EMPTY_COLUMN');
    await cellAt(owner,0,0,0).click();const before=JSON.stringify(await tableFacts(owner));await tableTool(owner,'delete-row').click();ensure(JSON.stringify(await tableFacts(owner))===before,'TABLE_HEADER_DELETED');
    await checked(owner);await saved(owner);const state=pageRow(await observe(),a);
    ensure((state.payload.main_text.match(/<table/g)||[]).length===2,'TABLE_STRUCTURAL_NEIGHBOUR_LOST');
    ensure(state.payload.main_text.includes('Keyboard before<br>Keyboard after'),'TABLE_ENTER_NOT_CANONICAL_BREAK');
    return {addDeleteRowsColumns:true,undoRedoNative:true,headerBoundaryRefused:true,enterHardBreak:true,nativeTabShiftTab:true,lastCellNoAutoAppend:true};
  });
  await group('TP2-UI-006',async()=>{
    const before=pageRow(await observe(),b),started=Date.now();await ready(owner,b);await surface(owner).waitFor();
    const opaque=surface(owner).locator('.es-opaque-table');ensure(await opaque.count()===3,'TABLE_LARGE_NOT_OPAQUE');
    ensure(await tables(owner).count()===0,'TABLE_DENSE_VIEW_ALLOCATED');
    const live=await surface(owner).locator('*').count();ensure(live<300,'TABLE_OPAQUE_LIVE_DOM_UNBOUNDED');
    await field(owner).locator('.es-toolbar').getByRole('button',{name:'HTML',exact:true}).click();
    ensure(await field(owner).locator('.es-html-source').inputValue()===before.payload.main_text,'TABLE_OPAQUE_SOURCE_CHANGED');
    await checked(owner);await saved(owner);const after=pageRow(await observe(),b);
    ensure(after.payload.main_text===before.payload.main_text,'TABLE_OPAQUE_PG_CHANGED');
    ensure(protectedPayload(after.payload)===protectedPayload(before.payload),'TABLE_OPAQUE_PROTECTED_CHANGED');
    ensure((await observe('select-ordinary')).selected,'TABLE_ORDINARY_SOURCE_ACK');
    const ordinary=pageRow(await observe(),b);ensure((ordinary.payload.main_text.match(/<li>/g)||[]).length===15000,'TABLE_ORDINARY_APPROVED_FIXTURE');
    await ready(owner,b);const htmlOnly=field(owner).locator('.es-html-source');await htmlOnly.waitFor();
    ensure(await htmlOnly.inputValue()===ordinary.payload.main_text,'TABLE_ORDINARY_HTML_ONLY_LOSS');
    const ordinaryLive=await field(owner).locator('*').count();ensure(ordinaryLive<300,'TABLE_ORDINARY_HUGE_LIVE_DOM');
    await checked(owner);await saved(owner);ensure(pageRow(await observe(),b).payload.main_text===ordinary.payload.main_text,'TABLE_ORDINARY_CHECK_SAVE_CHANGED');
    const memory=browserMemory();ensure(memory.maxBytes===1073741824&&memory.peakBytes<=memory.maxBytes,'TABLE_BROWSER_MEMORY_CAP');
    const app=(await observe()).appMemory;ensure(app.maxBytes===805306368&&app.peakBytes<=app.maxBytes,'TABLE_APP_MEMORY_CAP');
    return {giantSpanAndNestedAnd14000TextCellsOpaque:true,ordinary15000ListItemsHtmlOnly:true,exactSource:true,liveNodes:live,ordinaryLiveNodes:ordinaryLive,elapsedMs:Date.now()-started,browserMemory:memory,appMemory:app,peakScope:'whole-cohort-not-per-case'};
  });
  await group('TP2-UI-007',async()=>{
    const before=pageRow(await observe(),a),onContext=await context(),on=await login(onContext,seed.accounts.employee);await ready(on,a);await surface(on).waitFor();
    await cellAt(on,0,1,0).click();await on.keyboard.press('End');await on.keyboard.insertText(' EMPLOYEE');await checked(on);await saved(on);
    const after=pageRow(await observe(),a);ensure(after.payload.main_text.includes('EMPLOYEE'),'TABLE_EMPLOYEE_SAVE');ensure(protectedPayload(after.payload)===protectedPayload(before.payload),'TABLE_EMPLOYEE_PRICE_PROTECTED_CHANGED');
    const offContext=await context(),off=await login(offContext,seed.accounts.other);await ready(off,a);ensure(await field(off).count()===0,'TABLE_OTHER_FIELD_EXPOSED');await deniedMain(off,offContext,a,after.payload.main_text);
    ensure((await observe('revoke-main')).revoked,'TABLE_GRANT_REVOKE_ACK');await ready(on,a);ensure(await field(on).count()===0,'TABLE_LATE_GRANT_UI');await deniedMain(on,onContext,a,after.payload.main_text);await invariant(on);await invariant(off);
    await ready(owner,a);ensure(await ruleCount(owner)>0,'TABLE_DESTROY_FIXTURE_HAS_NO_RULES');
    const switcher=await login(ownerContext,seed.accounts.other);await switcher.close();await action(owner,'check').click();await owner.waitForFunction(()=>document.querySelectorAll('[data-editor-table]').length===0,null,{timeout:30000});ensure(await ruleCount(owner)===0,'TABLE_DESTROY_RULES_REMAINED');
    return {employeeActualSave:true,otherDenied:true,lateGrant:true,identityDestroyGc:true,protectedPhotoNative:'not-covered-framework-real-ready-photo-only'};
  });
  emit({kind:'result',status:'PASS',scope:'TP2-native-five-groups-not-full-FMT004',groups,diagnostics:{invariantFacts,paddingDiagnostics},browserMemory:browserMemory()});
}catch(error){if(owner&&!owner.isClosed()){try{await captureInvariant(owner,'failure');}catch{invariantFacts.push({caseId:current,checkpoint:'failure',factsUnavailable:true});}}
  emit({kind:'result',status:'FAIL',caseId:current,errorCode:fixed(error?.message),errorClass:error?.constructor?.name||'Error',groups,diagnostics:{pageErrors,responses:responses.slice(-20),unexpectedCount:unexpected.length,invariantFacts,paddingDiagnostics}});process.exitCode=1;
}finally{for(const ctx of contexts)await ctx.close().catch(()=>{});if(browser)await browser.close().catch(()=>{});channel.close();}

