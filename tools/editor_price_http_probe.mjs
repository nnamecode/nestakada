// TP1 native controls through existing Nginx. No evaluate/setter product actions.
import fs from 'node:fs';
import readline from 'node:readline';
import {chromium} from '/tests/node_modules/playwright/index.mjs';
const origin='http://host.docker.internal:8767',groups=[],contexts=[],pending=new Map();
const ensure=(yes,code)=>{if(!yes)throw new Error(code);};
const fixed=value=>typeof value==='string'&&/^[A-Z0-9_]{1,100}$/.test(value)?value:'PRICE_BROWSER_FAILED';
const emit=value=>process.stdout.write(JSON.stringify(value)+'\n');
let browser,seed,owner,ownerContext,current='START',serial=0;
const pageErrors=[],responses=[],unexpected=[],invariantFacts=[];
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
const root=page=>page.locator('[data-price-editor]');
const structural=(page,name)=>root(page).locator('[data-price-action="'+name+'"]');
const cell=(page,row,column)=>root(page).locator('[data-price-cell][data-row-id="'+row+'"][data-column-id="'+column+'"]');
async function context(){const ctx=await browser.newContext({viewport:{width:1280,height:900}});contexts.push(ctx);
  await ctx.route('**/*',route=>{if(new URL(route.request().url()).origin===origin)return route.continue();unexpected.push('EXTERNAL_REQUEST');return route.abort();});
  await ctx.addInitScript(()=>{
    globalThis.__priceCsp=[];globalThis.__priceCspCounts={};globalThis.__priceCspTotal=0;
    document.addEventListener('securitypolicyviolation',event=>{
      let directive=/^[a-z-]{1,40}$/.test(event.effectiveDirective)?event.effectiveDirective:'unknown';
      const counts=globalThis.__priceCspCounts;
      if(!Object.hasOwn(counts,directive)&&Object.keys(counts).length>=8)directive='other';
      counts[directive]=Math.min(10000,(counts[directive]||0)+1);
      globalThis.__priceCspTotal=Math.min(10000,globalThis.__priceCspTotal+1);
      if(globalThis.__priceCsp.length>=4)return;
      let source='unknown';
      try{const candidate=new URL(event.sourceFile).pathname.split('/').at(-1);
        if(/^[A-Za-z0-9._-]{1,60}$/.test(candidate))source=candidate;}catch{}
      globalThis.__priceCsp.push({directive,sourceBasename:source,
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
  ensure(response.status()===expected,'PRICE_CHECK_STATUS');
  await page.waitForFunction(()=>{const button=document.querySelector('.es-page-actions [data-editor-action=check]');return button&&!button.disabled;},null,{timeout:30000});
  if(expected!==200)return;
  const accept=page.locator('.es-review').getByRole('button',{name:'Принять проверенный вариант',exact:true});
  if(await accept.isVisible())await accept.click();
  await page.waitForFunction(()=>document.querySelector('[data-editor-dirty]')?.textContent.includes('Проверено.'),null,{timeout:30000});}
async function saved(page){const awaited=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/edit/save/'),{timeout:30000});
  await action(page,'save').click();const response=await awaited;responses.push({operation:'save',status:response.status()});
  ensure(response.status()===200,'PRICE_SAVE_STATUS');
  await page.waitForFunction(()=>document.querySelector('[data-editor-dirty]')?.textContent==='Сохранение подтверждено.',null,{timeout:30000});}
async function kind(page,row,column,value){await cell(page,row,column).locator('[data-price-kind]').selectOption(value);}
async function captureInvariant(page,checkpoint){
  const facts=await page.evaluate(()=>{
    const nodes=[...document.querySelectorAll('[data-price-editor] [style],[data-price-editor] script')];
    const safe=value=>/^[a-z0-9:-]{1,32}$/.test(value)?value:'unknown';
    return {csp:globalThis.__priceCsp||[],cspDirectiveCounts:globalThis.__priceCspCounts||{},cspTotal:globalThis.__priceCspTotal||0,
      storage:localStorage.length+sessionStorage.length,storageCounts:{local:localStorage.length,session:sessionStorage.length},
      inline:nodes.length,inlineNodes:nodes.slice(0,4).map(node=>({tag:safe(node.tagName.toLowerCase()),
        attributeNames:node.getAttributeNames().slice(0,4).map(safe)}))};
  });
  invariantFacts.push({caseId:current,checkpoint,...facts});if(invariantFacts.length>6)invariantFacts.shift();return facts;
}
async function invariant(page){const facts=await captureInvariant(page,'invariant');
  ensure(pageErrors.length===0,'PAGE_ERROR');ensure(unexpected.length===0,'EXTERNAL_REQUEST');
  ensure(facts.csp.length===0&&facts.storage===0&&facts.inline===0,'PRICE_CSP_STORAGE_INLINE');}
async function group(id,fn){current=id;const facts=await fn();await invariant(owner);groups.push({id,status:'PASS',...facts});}
const protectedPayload=payload=>JSON.stringify(Object.fromEntries(Object.entries(payload).filter(([key])=>key!=='price')));
async function negativeDirectPrice(page,ctx,id,price){const stateResponse=await ctx.request.get(url(prefix(id)+'state/'));ensure(stateResponse.status()===200,'PRICE_STATE_HTTP');
  const state=await stateResponse.json(),csrf=await page.locator('[data-editor-page] [name=csrfmiddlewaretoken]').inputValue();
  const response=await ctx.request.post(url(prefix(id)+'check/'),{headers:{'Content-Type':'application/json','X-CSRFToken':csrf},
    data:{protocol:'page-editor-v1',generation:state.generation,baseRevisionId:state.baseRevisionId,editingFrom:'current',draftBasis:null,stageId:null,changes:{price}}});
  ensure(response.status()===403,'PRICE_DIRECT_DENIAL');}
try{
  seed=JSON.parse(fs.readFileSync('/private/price-seed.json','utf8'));
  browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});ownerContext=await context();owner=await login(ownerContext,seed.accounts.owner);
  const [a,b]=seed.pageIds;
  await group('TP1-UI-001',async()=>{
    const before=pageRow(await observe(),a);await ready(owner,a);await root(owner).waitFor();
    const price=before.payload.price,[r0,r1]=price.rows.map(row=>row.id),[c0,c1]=price.columns.map(column=>column.id);
    await kind(owner,r0,c0,'text');await cell(owner,r0,c0).locator('[data-price-text]').fill('Line one\nLine two <script>literal</script>');
    await kind(owner,r0,c1,'amount');await cell(owner,r0,c1).locator('[data-price-amount]').fill('0');
    await kind(owner,r1,c0,'empty');await kind(owner,r1,c1,'amount');await cell(owner,r1,c1).locator('[data-price-amount]').fill('0.01');
    await cell(owner,r1,c1).locator('[data-price-from]').check();await checked(owner);await saved(owner);
    const after=pageRow(await observe(),a),cells=after.payload.price.rows;
    ensure(cells[0].cells.find(cell=>cell.column_id===c0).text==='Line one\nLine two <script>literal</script>','PRICE_MULTILINE_EXACT');
    ensure(cells[0].cells.find(cell=>cell.column_id===c1).amount==='0','ZERO_BECAME_EMPTY');
    ensure(cells[1].cells.find(cell=>cell.column_id===c0).text==='','EMPTY_BECAME_ZERO');
    ensure(cells[1].cells.find(cell=>cell.column_id===c1).from===true,'PRICE_FROM_FLAG');
    ensure(protectedPayload(after.payload)===protectedPayload(before.payload),'PRICE_PROTECTED_CHANGED');
    ensure(after.history.length===before.history.length+1,'PRICE_NEW_HISTORY');
    await ready(owner,a);ensure(await cell(owner,r0,c0).locator('[data-price-text]').inputValue()==='Line one\nLine two <script>literal</script>','PRICE_RELOAD_MULTILINE');
    await captureInvariant(owner,'before-screenshot-1280');
    await owner.screenshot({path:'/evidence/price-1280.png',fullPage:true,caret:'initial'});
    await captureInvariant(owner,'after-screenshot-1280');return {types:['empty','text','amount-zero','from'],multilineExact:true,actualPg:true};
  });
  await group('TP1-UI-003',async()=>{
    await ready(owner,b);await structural(owner,'create').click();await structural(owner,'add-column').click();await structural(owner,'add-column').click();
    for(let index=0;index<21;index++)await structural(owner,'add-row').click();
    const firstRows=await root(owner).locator('[data-price-row-label]').evaluateAll(nodes=>nodes.map(node=>node.dataset.priceRowLabel));
    const columns=await root(owner).locator('[data-price-column-label]').evaluateAll(nodes=>nodes.map(node=>node.dataset.priceColumnLabel));
    ensure(firstRows.length===20&&columns.length===2,'PRICE_PAGE20');
    await root(owner).locator('[data-price-row-label="'+firstRows[0]+'"]').fill('First row kept');
    await root(owner).locator('[data-price-action=down-row][data-row-id="'+firstRows[0]+'"]').click();
    await root(owner).locator('[data-price-action=right-column][data-column-id="'+columns[0]+'"]').click();
    await structural(owner,'next').click();
    const last=await root(owner).locator('[data-price-row-label]').getAttribute('data-price-row-label');
    await kind(owner,last,columns[0],'text');await cell(owner,last,columns[0]).locator('[data-price-text]').fill('Hidden last\nexact LF');
    await structural(owner,'previous').click();await structural(owner,'next').click();
    ensure(await cell(owner,last,columns[0]).locator('[data-price-text]').inputValue()==='Hidden last\nexact LF','PRICE_PAGINATION_RAM');
    await checked(owner);await saved(owner);const committed=pageRow(await observe(),b);
    ensure(committed.payload.price.rows.length===21,'PRICE_HIDDEN_ROWS_DROPPED');
    ensure(committed.payload.price.rows.at(-1).cells.find(cell=>cell.column_id===columns[0]).text==='Hidden last\nexact LF','PRICE_HIDDEN_ROW_PG');
    ensure(committed.payload.price.rows[1].id===firstRows[0]&&committed.payload.price.columns[1].id===columns[0],'PRICE_REORDER_ID');
    await ready(owner,b);await structural(owner,'next').click();ensure(await cell(owner,last,columns[0]).locator('[data-price-text]').inputValue()==='Hidden last\nexact LF','PRICE_HIDDEN_RELOAD');
    await structural(owner,'previous').click();await root(owner).locator('[data-price-action=remove-row]').first().click();
    await root(owner).locator('[data-price-action=remove-column]').first().click();await checked(owner);await saved(owner);
    const reduced=pageRow(await observe(),b);ensure(reduced.payload.price.rows.length===20&&reduced.payload.price.columns.length===1,'PRICE_REMOVE_STRUCTURE');
    await structural(owner,'remove').click();ensure(pageRow(await observe(),b).payloadHash===reduced.payloadHash,'PRICE_RAM_DELETE_PUBLISHED');
    await checked(owner);await saved(owner);ensure(pageRow(await observe(),b).payload.price===null,'PRICE_NULL_NOT_SAVED');
    return {createNull:true,rows21:true,page20:true,lastRowMultiline:true,idsRetained:true,explicitRemove:true};
  });
  await group('TP1-UI-002',async()=>{
    const offContext=await context(),off=await login(offContext,seed.accounts.other);await ready(off,a);
    ensure(await root(off).count()===0,'PRICE_OFF_GUI_EXPOSED');const before=pageRow(await observe(),a);
    await negativeDirectPrice(off,offContext,a,before.payload.price);
    const onContext=await context(),on=await login(onContext,seed.accounts.employee);await ready(on,a);await root(on).waitFor();
    ensure(await on.locator('[data-editor-field]').count()===0,'PRICE_ONLY_ASSUMED_TEXT_PERMISSION');
    const row=before.payload.price.rows[0].id,column=before.payload.price.columns[1].id;
    await cell(on,row,column).locator('[data-price-amount]').fill('2.5');await checked(on);await saved(on);
    const after=pageRow(await observe(),a);ensure(after.payload.price.rows[0].cells.find(cell=>cell.column_id===column).amount==='2.5','PRICE_ONLY_SAVE');
    ensure(protectedPayload(after.payload)===protectedPayload(before.payload),'PRICE_ONLY_PROTECTED_CHANGED');
    ensure((await observe('revoke-price')).revoked,'PRICE_REVOKE_ACK');await ready(on,a);ensure(await root(on).count()===0,'PRICE_REVOKED_GUI_REMAINED');
    await negativeDirectPrice(on,onContext,a,after.payload.price);await invariant(on);await invariant(off);
    return {priceOnlyEmployee:true,offDenied:true,lateRevoke:true,protectedPreserved:true};
  });
  await group('TP1-UI-004',async()=>{
    await ready(owner,a);const before=pageRow(await observe(),a),row=before.payload.price.rows[0].id,column=before.payload.price.columns[1].id;
    await cell(owner,row,column).locator('[data-price-amount]').fill('0.001');await checked(owner,400);
    ensure(await cell(owner,row,column).locator('[data-price-amount]').inputValue()==='0.001','PRICE_INVALID_TRUNCATED');
    ensure(pageRow(await observe(),a).currentId===before.currentId,'PRICE_INVALID_PUBLISHED');
    await cell(owner,row,column).locator('[data-price-amount]').fill('1e-2');await checked(owner);
    ensure(await cell(owner,row,column).locator('[data-price-amount]').inputValue()==='0.01','PRICE_SERVER_NORMALIZATION_NOT_ACCEPTED');
    await saved(owner);const oversize='🚀'.repeat(501),label=root(owner).locator('[data-price-row-label="'+row+'"]');
    await label.fill(oversize);await checked(owner,400);ensure(await label.inputValue()===oversize,'PRICE_LABEL_SILENT_TRUNCATION');
    await label.fill('Corrected row');await checked(owner);await saved(owner);
    // Hold an ACTUAL completed server Check while a newer native edit occurs.
    // Releasing the old response must neither overwrite RAM nor authorize Save.
    let reachedResolve,releaseResolve;
    const reached=new Promise(resolve=>{reachedResolve=resolve;}),released=new Promise(resolve=>{releaseResolve=resolve;});
    const pattern='**/manage/pages/'+a+'/edit/check/';
    const hold=async route=>{const response=await route.fetch();reachedResolve();await released;await route.fulfill({response});};
    await owner.route(pattern,hold);
    const prior=pageRow(await observe(),a);
    try{
      await cell(owner,row,column).locator('[data-price-amount]').fill('8.88');
      await action(owner,'check').click();
      let timer;await Promise.race([reached,new Promise((resolve,reject)=>{timer=setTimeout(()=>reject(new Error('PRICE_HELD_CHECK_TIMEOUT')),30000);})]).finally(()=>clearTimeout(timer));
      await cell(owner,row,column).locator('[data-price-amount]').fill('9.99');
      const received=owner.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/edit/check/'),{timeout:30000});
      releaseResolve();await received;
      await owner.waitForFunction(()=>!document.querySelector('.es-page-actions [data-editor-action=check]').disabled,null,{timeout:30000});
      ensure(await cell(owner,row,column).locator('[data-price-amount]').inputValue()==='9.99','PRICE_LATE_CHECK_OVERWROTE_INPUT');
      ensure(!(await owner.locator('[data-editor-dirty]').textContent()).includes('Проверено.'),'PRICE_STALE_PROOF_ACCEPTED');
      ensure(pageRow(await observe(),a).currentId===prior.currentId,'PRICE_STALE_PROOF_PUBLISHED');
      // Explicit Save may legitimately perform its own fresh Check. Prove
      // network order and binding to the fresh 9.99 intent, not the old proof.
      const order=[],requests=[];
      const listener=request=>{const path=new URL(request.url()).pathname;
        if(request.method()==='POST'&&(path===prefix(a)+'check/'||path===prefix(a)+'save/')){
          order.push(path.endsWith('/check/')?'check':'save');requests.push(request.postDataJSON());}};
      owner.on('request',listener);
      try{
        const fresh=owner.waitForResponse(response=>new URL(response.url()).pathname===prefix(a)+'check/',{timeout:30000});
        await saved(owner);const freshResponse=await fresh;
        ensure(freshResponse.status()===200,'PRICE_FRESH_SAVE_CHECK_STATUS');
        const freshResult=await freshResponse.json();
        ensure(order.join()===['check','save'].join(),'PRICE_FRESH_CHECK_BEFORE_SAVE');
        ensure(requests[0].changes.price.rows.find(item=>item.id===row).cells.find(item=>item.column_id===column).amount==='9.99','PRICE_FRESH_CHECK_WRONG_INTENT');
        ensure(typeof freshResult.checkReceipt==='string'&&requests[1].checkReceipt===freshResult.checkReceipt,'PRICE_SAVE_WRONG_FRESH_PROOF');
      }finally{owner.off('request',listener);}
    }finally{releaseResolve();await owner.unroute(pattern,hold);}
    ensure(pageRow(await observe(),a).payload.price.rows[0].cells.find(cell=>cell.column_id===column).amount==='9.99','PRICE_FRESH_CHECK_NOT_SAVED');
    await cell(owner,row,column).locator('[data-price-amount]').fill('999999999.99');await checked(owner);await saved(owner);
    ensure(pageRow(await observe(),a).payload.price.rows[0].cells.find(cell=>cell.column_id===column).amount==='999999999.99','PRICE_GUI_MAX_AMOUNT_PG');
    await owner.setViewportSize({width:390,height:844});await captureInvariant(owner,'before-screenshot-390');
    await owner.screenshot({path:'/evidence/price-390.png',fullPage:true,caret:'initial'});await captureInvariant(owner,'after-screenshot-390');
    return {invalidPreserved:true,serverExactDecimal:true,codepoints501ReachServer:true,lateCheckEpoch:true,maxAmountActualPg:true};
  });
  await group('TP1-UI-008',async()=>{
    const before=pageRow(await observe(),a),row=before.payload.price.rows[0].id,column=before.payload.price.columns[1].id;
    await cell(owner,row,column).locator('[data-price-amount]').fill('77.77');
    const switcher=await login(ownerContext,seed.accounts.other);await switcher.close();
    await action(owner,'check').click();await owner.waitForFunction(()=>document.querySelector('[data-price-editor]')===null,null,{timeout:30000});
    ensure(pageRow(await observe(),a).currentId===before.currentId,'PRICE_OLD_IDENTITY_PUBLISHED');
    return {identityDomWiped:true,oldPriceNotSent:true};
  });
  emit({kind:'result',status:'PASS',scope:'TP1-native-five-groups-not-all-price-acceptance',groups,diagnostics:{invariantFacts}});
}catch(error){if(owner&&!owner.isClosed()){try{await captureInvariant(owner,'failure');}catch{invariantFacts.push({caseId:current,checkpoint:'failure',factsUnavailable:true});}}
  emit({kind:'result',status:'FAIL',caseId:current,errorCode:fixed(error?.message),errorClass:error?.constructor?.name||'Error',groups,
  diagnostics:{pageErrors,responses:responses.slice(-20),unexpectedCount:unexpected.length,invariantFacts}});process.exitCode=1;
}finally{for(const ctx of contexts)await ctx.close().catch(()=>{});if(browser)await browser.close().catch(()=>{});channel.close();}
