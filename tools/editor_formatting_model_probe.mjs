// Synthetic MODEL regression of the actual product adapter. PM transactions
// and DOM selection setters below are deliberate test setup, NOT GUI proof.
import fs from 'node:fs';
import crypto from 'node:crypto';
import {chromium} from '/tests/node_modules/playwright/index.mjs';

const origin='http://formatting-model.invalid';
const bundle=fs.readFileSync('/bundle/editor.bundle.js');
const css=fs.readFileSync('/source/editor.css');
const csp="default-src 'none';script-src 'self';style-src 'self';connect-src 'none';img-src 'none';font-src 'none';base-uri 'none'";
const html='<!doctype html><html><head><link rel="stylesheet" href="/editor.css"></head><body><div id="editor"></div><script type="module" src="/harness.js"></script></body></html>';
const harness="import {createEditor} from '/editor.js';globalThis.makeEditor=createEditor;globalThis.violations=[];document.addEventListener('securitypolicyviolation',event=>violations.push(event.violatedDirective));globalThis.ready=true;";
const report={scope:'synthetic-product-adapter-model-only',notEvidenceFor:['native-user-input','HTTP-auth-CSRF','server-normalization','RSS-maximum'],bundleSha256:crypto.createHash('sha256').update(bundle).digest('hex'),cases:[]};
let browser;
try{
  browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
  const page=await browser.newPage();const pageErrors=[],unexpectedRequests=[];
  page.on('pageerror',()=>pageErrors.push('PAGE_ERROR'));
  await page.route('**/*',route=>{
    const url=new URL(route.request().url());
    const value=url.origin!==origin?null:url.pathname==='/'?['text/html',html]:url.pathname==='/editor.js'?['text/javascript',bundle]:url.pathname==='/editor.css'?['text/css',css]:url.pathname==='/harness.js'?['text/javascript',harness]:null;
    if(!value){unexpectedRequests.push('UNAPPROVED_REQUEST');return route.abort();}
    return route.fulfill({status:200,contentType:value[0],body:value[1],headers:{'Content-Security-Policy':csp}});
  });
  await page.goto(origin);await page.waitForFunction(()=>globalThis.ready===true,null,{timeout:15000});
  Object.assign(report,await page.evaluate(()=>{
    const cases=[];let api=null,view=null;
    const ensure=(condition,code)=>{if(!condition)throw new Error(code);};
    const sheet=document.querySelector('link').sheet,baseRules=sheet.cssRules.length;
    const host=document.querySelector('#editor');
    function mount(source='<p>AB</p>',options={}){
      if(api)api.destroy();
      api=makeEditor(host,{approvedHtml:source,owner:true,field:'main_text',styleSheet:sheet,...options});
      view=host.querySelector('.es-editor-surface').editor.view;
    }
    function select(anchor,head=anchor,target=view){
      const selection=target.state.selection.constructor.create(target.state.doc,anchor,head);
      target.dispatch(target.state.tr.setSelection(selection));target.focus();
    }
    function pendingModel(node){
      view.dispatch(view.state.tr.replaceWith(0,view.state.doc.content.size,node));
      select(1,view.state.doc.content.size-1);
    }
    function pendingText(text){
      mount();pendingModel(view.state.schema.nodes.paragraph.create(null,view.state.schema.text(text,[view.state.schema.marks.bold.create()])));
    }
    function rejectedReset(code){
      const before=view.state.doc;let actual=null;
      try{api.command('clearFormatting');}catch(error){actual=error.code;}
      ensure(actual===code,'WRONG_CONTROLLED_REFUSAL');ensure(view.state.doc.eq(before),'REFUSAL_CHANGED_MODEL');
    }
    function acceptedText(expected){
      api.command('clearFormatting');ensure(view.state.doc.textContent===expected,'ACCEPTED_TEXT_CHANGED');
      let bold=false;view.state.doc.descendants(node=>{if(node.marks.some(mark=>mark.type.name==='bold'))bold=true;});ensure(!bold,'RESET_FORMAT_REMAINED');
    }
    // Deliberate MODEL setup: DOM selection moves in this same task while PM
    // remains stale. This is not native keyboard/HTTP/READY media evidence.
    function domRange(anchor,anchorOffset,focus=anchor,focusOffset=anchorOffset){
      document.getSelection().setBaseAndExtent(anchor,anchorOffset,focus,focusOffset);
    }
    const formats=[['font','georgia'],['size','18'],['fg','#778899'],['bg','#aabbcc']];
    const markAttrs=node=>node?.marks.find(mark=>mark.type.name==='esFormat')?.attrs||{};
    try{
      mount();select(2);
      const schema=view.state.schema;
      const link=schema.marks.esLink.create({href:'/safe/',title:null,target:null,rel:null,'data-es-target-field':null,'data-es-target-anchor':null});
      const anchor=schema.marks.esAnchor.create({label:'target'});
      view.dispatch(view.state.tr.setStoredMarks([link,anchor,schema.marks.bold.create(),schema.marks.esFormat.create({fg:'#123456'})]));
      api.command('clearFormatting');
      const remaining=(view.state.storedMarks||[]).map(mark=>mark.type.name).sort();
      ensure(JSON.stringify(remaining)===JSON.stringify(['esAnchor','esLink']),'SAME_CARET_LOST_LINK_ANCHOR');
      view.dispatch(view.state.tr.insertText('x'));
      const inserted=view.state.doc.nodeAt(2);
      ensure(inserted?.marks.some(mark=>mark.type.name==='esLink')&&inserted.marks.some(mark=>mark.type.name==='esAnchor'),'TYPED_TEXT_LOST_RETAINED_MARKS');
      ensure(!inserted.marks.some(mark=>['bold','esFormat'].includes(mark.type.name)),'TYPED_TEXT_RETAINED_FORMAT');
      cases.push({id:'MODEL-FREV004-SAME',status:'PASS'});

      mount();select(2);
      view.dispatch(view.state.tr.setStoredMarks([view.state.schema.marks.esLink.create({href:'/old/'}),view.state.schema.marks.esAnchor.create({label:'old'}),view.state.schema.marks.bold.create()]));
      const textNode=host.querySelector('.es-editor-surface p').firstChild;
      const range=document.createRange();range.setStart(textNode,0);range.collapse(true);
      const domSelection=document.getSelection();domSelection.removeAllRanges();domSelection.addRange(range);
      api.command('clearFormatting');
      ensure(view.state.selection.anchor===1,'MOVED_CARET_NOT_USED');
      ensure(!(view.state.storedMarks||[]).some(mark=>['esLink','esAnchor','bold'].includes(mark.type.name)),'MOVED_CARET_INHERITED_OLD_MARKS');
      cases.push({id:'MODEL-FREV004-MOVED',status:'PASS'});

      for(const [name,value] of formats){
        mount('<p>ABCD</p>');view.focus();
        const text=host.querySelector('.es-editor-surface p').firstChild;
        domRange(text,1,text,3);
        ensure(view.state.selection.empty&&view.state.selection.anchor===1,'FORMAT_STALE_PM_CONTROL');
        ensure(document.getSelection().toString()==='BC','FORMAT_DOM_RANGE_CONTROL');
        api.command(name,value);
        ensure(!view.state.selection.empty&&view.state.selection.from===2&&view.state.selection.to===4,'FORMAT_USED_OLD_PM_RANGE');
        ensure(view.state.doc.textContent==='ABCD','FORMAT_CHANGED_UNICODE_TEXT');
        ensure(markAttrs(view.state.doc.nodeAt(2))[name]===value,'FORMAT_NOT_APPLIED_TO_SELECTED_TEXT');
        ensure(!markAttrs(view.state.doc.nodeAt(1))[name]&&!markAttrs(view.state.doc.nodeAt(4))[name],'FORMAT_CHANGED_ADJACENT_TEXT');
        ensure(sheet.cssRules.length===baseRules+1,'FORMAT_SELECTED_RULE_MISSING');
        cases.push({id:'MODEL-FSEL-RANGE-'+name,status:'PASS',stalePmCaret:true,domSelectedCodepoints:2});
      }

      for(const [name,value] of formats){
        mount();select(2);
        const schema=view.state.schema,initial={font:'arial',size:'12',fg:'#112233',bg:'#445566'};
        view.dispatch(view.state.tr.setStoredMarks([schema.marks.esLink.create({href:'/same/'}),
          schema.marks.esAnchor.create({label:'same'}),schema.marks.bold.create(),schema.marks.esFormat.create(initial)]));
        api.command(name,value);
        const stored=view.state.storedMarks||[],format=stored.find(mark=>mark.type.name==='esFormat');
        ensure(stored.some(mark=>mark.type.name==='esLink')&&stored.some(mark=>mark.type.name==='esAnchor')&&stored.some(mark=>mark.type.name==='bold'),'FORMAT_SAME_CARET_LOST_UNRELATED_MARKS');
        for(const key of ['font','size','fg','bg'])ensure(format?.attrs[key]===(key===name?value:initial[key]),'FORMAT_SAME_CARET_LOST_OTHER_ATTRS');
        view.dispatch(view.state.tr.insertText('x'));
        const inserted=view.state.doc.nodeAt(2);
        ensure(markAttrs(inserted)[name]===value&&inserted.marks.some(mark=>mark.type.name==='esLink')&&inserted.marks.some(mark=>mark.type.name==='esAnchor'),'FORMAT_FUTURE_TEXT_LOST_MARKS');
      }
      cases.push({id:'MODEL-FSEL-SAME-CARET',status:'PASS',commands:4,storedLinkAnchorAndOtherAttrsPreserved:true});

      mount('<p>AB</p><p><span data-es-size="12">CD</span></p>');select(2);
      view.dispatch(view.state.tr.setStoredMarks([view.state.schema.marks.esLink.create({href:'/old/'}),
        view.state.schema.marks.esAnchor.create({label:'old'}),view.state.schema.marks.bold.create(),view.state.schema.marks.esFormat.create({fg:'#ff0000'})]));
      const destination=host.querySelectorAll('.es-editor-surface p')[1].querySelector('span').firstChild;
      domRange(destination,1);api.command('font','georgia');
      ensure(view.state.selection.empty&&view.state.selection.anchor===6,'FORMAT_MOVED_CARET_NOT_USED');
      const moved=view.state.storedMarks||[],movedFormat=moved.find(mark=>mark.type.name==='esFormat');
      ensure(!moved.some(mark=>['esLink','esAnchor','bold'].includes(mark.type.name)),'FORMAT_MOVED_CARET_IMPORTED_OLD_MARKS');
      ensure(movedFormat?.attrs.font==='georgia'&&movedFormat.attrs.size==='12'&&!movedFormat.attrs.fg,'FORMAT_MOVED_CARET_WRONG_DESTINATION_MERGE');
      view.dispatch(view.state.tr.insertText('x'));ensure(markAttrs(view.state.doc.nodeAt(6)).size==='12','FORMAT_MOVED_TYPED_TEXT_LOST_DESTINATION');
      cases.push({id:'MODEL-FSEL-MOVED-CARET',status:'PASS',destinationFormatPreserved:true,oldStoredMarksDiscarded:true});

      mount('<p>AB</p><p>CD</p>');view.focus();
      const blocks=host.querySelectorAll('.es-editor-surface p');domRange(blocks[1].firstChild,2,blocks[0].firstChild,0);
      api.command('fg','#778899');ensure(view.state.selection.anchor>view.state.selection.head,'FORMAT_REVERSE_DIRECTION_LOST');
      let marked=0;view.state.doc.descendants(node=>{if(node.isText){ensure(markAttrs(node).fg==='#778899','FORMAT_MULTIBLOCK_TEXT_UNMARKED');marked+=node.text.length;}});
      ensure(marked===4&&view.state.doc.textContent==='ABCD','FORMAT_MULTIBLOCK_CHANGED_TEXT');
      cases.push({id:'MODEL-FSEL-REVERSE-MULTIBLOCK',status:'PASS'});

      const id=number=>'00000000-0000-0000-0000-'+String(number).padStart(12,'0');
      const reference={asset_id:id(4),alt:'',alignment:'center',width_px:null,height_px:null};
      const protectedHtml='<p data-es-parent="'+id(1)+'"><span data-es-slot="'+id(2)+'">LEFT</span><span data-es-alt="" data-es-asset="'+id(4)+'" data-es-image="'+id(5)+'" data-es-image-align="center" data-es-protected="'+id(6)+'"></span><span data-es-slot="'+id(3)+'">RIGHT</span></p>';
      mount(protectedHtml,{approvedEmbedded:[{markerId:id(6),imageId:id(5),reference,url:null,thumbnailUrl:null}]});view.focus();
      const slots=host.querySelectorAll('[data-editor-protected-slot]'),beforeParent=JSON.stringify(view.state.doc.firstChild.attrs),beforeAtom=JSON.stringify(view.state.doc.firstChild.child(1).attrs);
      domRange(slots[0].firstChild,0,slots[0].firstChild,4);api.command('bg','#aabbcc');
      ensure(view.state.doc.firstChild.firstChild.textContent==='LEFT'&&markAttrs(view.state.doc.firstChild.firstChild.firstChild).bg==='#aabbcc','FORMAT_SINGLE_SLOT_POSITIVE_FAILED');
      const currentSlots=host.querySelectorAll('[data-editor-protected-slot]');domRange(currentSlots[1].firstChild,1);api.command('size','18');
      ensure(view.state.selection.empty&&view.state.storedMarks?.some(mark=>mark.type.name==='esFormat'&&mark.attrs.size==='18'),'FORMAT_SLOT_CARET_STORED_POSITIVE_FAILED');
      ensure(JSON.stringify(view.state.doc.firstChild.attrs)===beforeParent&&JSON.stringify(view.state.doc.firstChild.child(1).attrs)===beforeAtom,'FORMAT_CHANGED_PROTECTED_METADATA');
      function refusedFormat(code){const before=view.state.doc;let actual=null;try{api.command('fg','#123456');}catch(error){actual=error.code;}ensure(actual===code,'FORMAT_WRONG_REFUSAL');ensure(view.state.doc.eq(before),'FORMAT_REFUSAL_CHANGED_MODEL');}
      const freshSlots=host.querySelectorAll('[data-editor-protected-slot]');domRange(freshSlots[0].firstChild,0,freshSlots[1].firstChild,5);refusedFormat('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
      const atom=host.querySelector('[data-editor-embedded-marker]');domRange(atom,0);refusedFormat('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
      domRange(document.body,0,freshSlots[0].firstChild,0);refusedFormat('EDITOR_SELECTION_UNSUPPORTED');
      cases.push({id:'MODEL-FSEL-PROTECTED',status:'PASS',syntheticMappingOnly:true,notReadyMediaEvidence:true,singleSlotAndCaretPositive:true,crossSlotAtomForeignRefused:true});

      mount('<p>AB</p><table><tbody><tr><td>X</td></tr></tbody></table><p>CD</p>');view.focus();
      const paragraphs=host.querySelectorAll('.es-editor-surface > p');domRange(paragraphs[0].firstChild,0,paragraphs[1].firstChild,2);refusedFormat('EDITOR_PROTECTED_COMMAND_UNSUPPORTED');
      cases.push({id:'MODEL-FSEL-OPAQUE-REFUSAL',status:'PASS'});

      const limitPrefix='<p data-es-anchor="',limitSuffix='">BOUND</p>';
      const exactSource=limitPrefix+'a'.repeat(1048576-limitPrefix.length-limitSuffix.length)+limitSuffix;
      ensure(new TextEncoder().encode(exactSource).length===1048576,'FORMAT_SOURCE_BOUNDARY_CONTROL');
      mount(exactSource);view.focus();
      const limitText=host.querySelector('.es-editor-surface p').firstChild;
      domRange(limitText,0,limitText,5);
      const beforeLimitDoc=view.state.doc,beforeLimitSelection=view.state.selection,beforeLimitStored=view.state.storedMarks,beforeLimitRules=sheet.cssRules.length;
      let limitCode=null;try{api.command('fg','#123456');}catch(error){limitCode=error.code;}
      ensure(limitCode==='EDITOR_CANDIDATE_LIMIT','FORMAT_BYTE_BOUNDARY_WRONG_REFUSAL');
      ensure(view.state.doc===beforeLimitDoc&&view.state.selection.eq(beforeLimitSelection)&&view.state.storedMarks===beforeLimitStored,'FORMAT_BYTE_LIMIT_DISPATCHED_PARTIAL_TRANSACTION');
      ensure(sheet.cssRules.length===beforeLimitRules&&api.getCanonicalHtml()===exactSource,'FORMAT_BYTE_LIMIT_CHANGED_RULES_OR_SOURCE');
      cases.push({id:'MODEL-FSEL-BYTE-LIMIT',status:'PASS',validApprovedSourceBytes:1048576,noPartialDispatch:true});

      let value='e\u0301'.repeat(200000);pendingText(value);acceptedText(value);
      cases.push({id:'MODEL-NFC-200000',status:'PASS',normalisedCodepoints:200000});
      value='e\u0301'.repeat(200001);pendingText(value);rejectedReset('EDITOR_CANDIDATE_LIMIT');
      cases.push({id:'MODEL-NFC-200001',status:'PASS'});
      value='\u1100\u1161\u11a8'.repeat(120000);
      ensure(new TextEncoder().encode(value).length>1048576&&Array.from(value.normalize('NFC')).length===120000,'PRE_NFC_BYTES_ORACLE');
      pendingText(value);rejectedReset('EDITOR_CANDIDATE_LIMIT');
      cases.push({id:'MODEL-PRE-NFC-BYTES',status:'PASS'});
      value='&'.repeat(200000);pendingText(value);acceptedText(value);
      ensure(api.getCanonicalHtml()==='<p>'+'&amp;'.repeat(200000)+'</p>','AMP_EXACT_CANONICAL');
      cases.push({id:'MODEL-AMP-200000',status:'PASS'});
      value='\r\n'.repeat(200000);pendingText(value);acceptedText(value);
      cases.push({id:'MODEL-CRLF-200000',status:'PASS',normalisedCodepoints:200000});

      for(const depth of [32,33]){
        mount();let node=view.state.schema.nodes.paragraph.create(null,view.state.schema.text('D',[view.state.schema.marks.bold.create()]));
        for(let level=1;level<depth;level++)node=view.state.schema.nodes.blockquote.create(null,node);
        view.dispatch(view.state.tr.replaceWith(0,view.state.doc.content.size,node));select(depth,depth+1);
        if(depth===32)acceptedText('D');else rejectedReset('EDITOR_CANDIDATE_LIMIT');
        cases.push({id:'MODEL-DEPTH-'+depth,status:'PASS'});
      }
      for(const count of [20000,20001]){
        mount();const children=Array.from({length:count-1},()=>view.state.schema.nodes.hardBreak.create());
        children.push(view.state.schema.text('N',[view.state.schema.marks.bold.create()]));
        pendingModel(view.state.schema.nodes.paragraph.create(null,children));
        if(count===20000){api.command('clearFormatting');ensure(view.state.doc.textContent==='N','NODE_LIMIT_TEXT_CHANGED');}
        else rejectedReset('EDITOR_CANDIDATE_LIMIT');
        cases.push({id:'MODEL-NODES-'+count,status:'PASS'});
      }

      mount('<p><span data-es-font="arial" data-es-fg="#123456">STYLE</span></p>');select(1,6);
      let peak=sheet.cssRules.length;
      for(let index=0;index<50;index++){
        const color='#'+(0x100000+index).toString(16);
        api.command('fg',color);peak=Math.max(peak,sheet.cssRules.length);
        ensure(sheet.cssRules.length<=baseRules+1,'CSSOM_RULE_ACCUMULATION');
        if(index===49)ensure(getComputedStyle(host.querySelector('.es-editor-surface span')).color==='rgb(16, 0, 49)','CSSOM_FINAL_COMPUTED_COLOR');
        api.command('clearFormatting');
        ensure(view.state.doc.textContent==='STYLE'&&api.getCanonicalHtml()==='<p>STYLE</p>','CSSOM_RESET_SOURCE_CHANGED');
        ensure(sheet.cssRules.length===baseRules,'CSSOM_RESET_RULES_REMAIN');
        const ownCanonical=api.getCanonicalHtml();api.setApprovedHtml(ownCanonical);
        view=host.querySelector('.es-editor-surface').editor.view;select(1,6);
        ensure(api.getCanonicalHtml()===ownCanonical&&view.state.doc.textContent==='STYLE','CSSOM_SOURCE_REFRESH_CHANGED');
        ensure(sheet.cssRules.length===baseRules,'CSSOM_REFRESH_RULES_REMAIN');
      }
      ensure(host.querySelectorAll('[style],style,colgroup').length===0,'INLINE_STYLE_OR_COLGROUP');
      api.destroy();api=null;ensure(sheet.cssRules.length===baseRules,'DESTROY_RULES_REMAIN');
      ensure(!host.textContent,'DESTROY_CONTENT_REMAIN');
      mount('<p><span data-es-fg="#112233">FIRST</span></p>');
      const hostB=document.createElement('div');document.body.append(hostB);
      const apiB=makeEditor(hostB,{approvedHtml:'<p><span data-es-fg="#445566">SECOND</span></p>',owner:true,field:'intro_text',styleSheet:sheet});
      try{
        const viewB=hostB.querySelector('.es-editor-surface').editor.view;
        const selectors=element=>Array.from(element.querySelectorAll('[class]')).flatMap(node=>Array.from(node.classList)).filter(value=>value.startsWith('esf-')).map(value=>'.'+value);
        const aSelectors=selectors(host),bSelectors=selectors(hostB);
        ensure(aSelectors.length>0&&bSelectors.length>0,'INDEPENDENT_VIEW_RULE_IDENTITIES');
        ensure(sheet.cssRules.length===baseRules+2,'SIMULTANEOUS_VIEW_RULES');
        ensure(getComputedStyle(host.querySelector('.es-editor-surface span')).color==='rgb(17, 34, 51)','FIRST_VIEW_COMPUTED');
        ensure(getComputedStyle(hostB.querySelector('.es-editor-surface span')).color==='rgb(68, 85, 102)','SECOND_VIEW_COMPUTED');
        api.destroy();api=null;
        const remaining=Array.from(sheet.cssRules).map(rule=>rule.selectorText);
        ensure(aSelectors.every(selector=>!remaining.includes(selector))&&bSelectors.every(selector=>remaining.includes(selector)),'DESTROY_WRONG_VIEW_RULES');
        ensure(sheet.cssRules.length===baseRules+1&&viewB.state.doc.textContent==='SECOND','OTHER_VIEW_DESTROY_AFFECTED_B');
        ensure(getComputedStyle(hostB.querySelector('.es-editor-surface span')).color==='rgb(68, 85, 102)','SECOND_VIEW_COLOR_AFTER_A_DESTROY');
        select(1,7,viewB);apiB.command('fg','#778899');
        ensure(getComputedStyle(hostB.querySelector('.es-editor-surface span')).color==='rgb(119, 136, 153)','SECOND_VIEW_COMMAND_AFTER_A_DESTROY');
        ensure(viewB.state.doc.textContent==='SECOND'&&sheet.cssRules.length===baseRules+1,'SECOND_VIEW_RULE_BUDGET_AFTER_CHANGE');
      }finally{apiB.destroy();hostB.remove();}
      ensure(sheet.cssRules.length===baseRules,'BOTH_VIEWS_DESTROY_RULES_REMAIN');
      cases.push({id:'MODEL-CSSOM-50-DESTROY',status:'PASS',cycles:50,cycleActions:['format','clear','canonical-refresh'],baseRules,peakRules:peak,perViewRuleCap:1,simultaneousViews:2,simultaneousRuleCap:2,finalRules:sheet.cssRules.length,resourceClaim:'rule-lifetime-pattern-only-not-RSS'});
      ensure(violations.length===0,'STRICT_CSP_VIOLATION');
      return {status:'PASS',cases,cspViolations:violations.length};
    }catch(error){return {status:'FAIL',cases,code:/^[A-Z0-9_-]+$/.test(error.message)?error.message:'MODEL_PROBE_FAILED',cspViolations:violations.length};}
    finally{if(api)api.destroy();}
  }));
  const settledViolations=await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(violations.length)))));
  report.cspViolations=settledViolations;
  if(settledViolations){report.status='FAIL';report.code='STRICT_CSP_VIOLATION';}
  if(pageErrors.length||unexpectedRequests.length){report.status='FAIL';report.code='BROWSER_BOUNDARY_FAILED';}
  report.pageErrorCount=pageErrors.length;report.unexpectedRequestCount=unexpectedRequests.length;
}catch(error){report.status='FAIL';report.code=/^[A-Z0-9_-]+$/.test(error.message)?error.message:'MODEL_PROBE_RUNTIME_FAILED';}
finally{if(browser)await browser.close();}
fs.writeFileSync('/output/formatting-model-report.json',JSON.stringify(report,null,2));
console.log(JSON.stringify(report));if(report.status!=='PASS')process.exitCode=1;
