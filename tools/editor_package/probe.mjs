// QA-only artifact/browser probe. Not a product renderer, HTML policy or site handler.
import fs from 'node:fs';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const outputDirectory='/output';
const artifact=outputDirectory+'/tiptap-candidate.js';
const syntheticOrigin='http://editor-candidate.invalid';
const policy="default-src 'none'; script-src 'self'; style-src 'self'; img-src 'none'; font-src 'self'; connect-src 'none'; base-uri 'none'; form-action 'none'";
const require=createRequire('/deps/package.json');
const pins=['@tiptap/core','@tiptap/pm','@tiptap/starter-kit','@tiptap/extension-table','@tiptap/extension-text-style','@tiptap/extension-text-align','@tiptap/extension-subscript','@tiptap/extension-superscript'];
const facts=[],network=[];
let current='preflight',browser,context,page;
const ensure=(value,code)=>{if(!value)throw new Error(code);};
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
async function check(id,body){current=id;facts.push({id,status:'PASS',...await body()});}
const entry="import {Editor,mergeAttributes} from '@tiptap/core';\nimport StarterKit from '@tiptap/starter-kit';\nimport * as TableExports from '@tiptap/extension-table';\nimport * as StyleExports from '@tiptap/extension-text-style';\nimport {TextAlign} from '@tiptap/extension-text-align';\nimport {Subscript} from '@tiptap/extension-subscript';\nimport {Superscript} from '@tiptap/extension-superscript';\nif(!TableExports.TableKit || !StyleExports.TextStyleKit)throw new Error('CANDIDATE_KIT_EXPORT_MISSING');\nconst editor=new Editor({\n  element:document.querySelector('#candidate-editor'),injectCSS:false,\n  extensions:[\n    StarterKit.configure({code:false,codeBlock:false,horizontalRule:false,\n      link:{openOnClick:false,autolink:false,linkOnPaste:false,HTMLAttributes:{rel:'noopener',target:'_blank'}}}),\n    TableExports.TableKit.configure({table:{resizable:false}}),\n    StyleExports.TextStyleKit.configure({lineHeight:false}),\n    TextAlign.configure({types:['heading','paragraph']}),Subscript,Superscript],\n  content:'<p>Candidate initial positive</p>'\n});\nconst reset=value=>editor.commands.setContent(value);\nglobalThis.candidate={\n  editor,\n  prototypeRegression:()=>{\n    const keysBefore=Reflect.ownKeys(Object.prototype).map(String).sort();\n    const prototypeBefore=Object.getPrototypeOf(Object.prototype);\n    const input=JSON.parse('{\"__proto__\":{\"dev07PrototypeCanary\":\"PROTOTYPE-CANARY\"},\"data-approved\":\"kept\",\"class\":\"positive\"}');\n    const result=mergeAttributes({title:'ordinary-title',class:'base'},input,{'data-final':'ok'});\n    const descriptor=Object.getOwnPropertyDescriptor(result,'__proto__');\n    return {\n      functionSource:String(mergeAttributes),\n      inputReallyOwnsProto:Object.prototype.hasOwnProperty.call(input,'__proto__'),\n      resultPlainPrototype:Object.getPrototypeOf(result)===Object.prototype,\n      safeOwnDataDescriptor:!!descriptor&&Object.prototype.hasOwnProperty.call(descriptor,'value')&&!Object.prototype.hasOwnProperty.call(descriptor,'get')&&!Object.prototype.hasOwnProperty.call(descriptor,'set')&&descriptor.value?.dev07PrototypeCanary==='PROTOTYPE-CANARY',\n      canaryNotInherited:result.dev07PrototypeCanary===undefined,\n      globalPrototypeUnchanged:({}).dev07PrototypeCanary===undefined&&Object.getPrototypeOf(Object.prototype)===prototypeBefore&&JSON.stringify(Reflect.ownKeys(Object.prototype).map(String).sort())===JSON.stringify(keysBefore),\n      ordinaryAttributesPreserved:result.title==='ordinary-title'&&result['data-approved']==='kept'&&result['data-final']==='ok'&&result.class.split(/\\s+/).includes('base')&&result.class.split(/\\s+/).includes('positive')\n    };\n  },\n  extensionNames:editor.extensionManager.extensions.map(extension=>extension.name),\n  html:()=>editor.getHTML(),json:()=>editor.getJSON(),\n  marks:()=>{reset('<p>FORMAT-CANARY</p>');return editor.chain().focus().selectAll().toggleBold().toggleItalic().toggleUnderline().toggleStrike().run();},\n  heading:()=>{reset('<p>HEADING-CANARY</p>');return editor.chain().focus().selectAll().setHeading({level:2}).run();},\n  quote:()=>{reset('<p>QUOTE-CANARY</p>');return editor.chain().focus().selectAll().setBlockquote().run();},\n  bullet:()=>{reset('<p>ITEM-A</p><p>ITEM-B</p>');return editor.chain().focus().selectAll().toggleBulletList().run();},\n  ordered:()=>{reset('<p>ORDER-A</p><p>ORDER-B</p>');return editor.chain().focus().selectAll().toggleOrderedList().run();},\n  subscript:()=>{reset('<p>SUB-CANARY</p>');return editor.chain().focus().selectAll().toggleSubscript().run();},\n  superscript:()=>{reset('<p>SUP-CANARY</p>');return editor.chain().focus().selectAll().toggleSuperscript().run();},\n  link:()=>{reset('<p>LINK-CANARY</p>');return editor.chain().focus().selectAll().setLink({href:'/approved-reference/',target:'_blank'}).run();},\n  table:()=>{reset('<p></p>');return editor.chain().focus().insertTable({rows:2,cols:2,withHeaderRow:true}).run();},\n  style:()=>{reset('<p>STYLE-CANARY</p>');return editor.chain().focus().selectAll().setFontFamily('Arial').setFontSize('24px').setColor('#123456').setBackgroundColor('#ddeeff').setTextAlign('center').run();},\n  cssom:()=>{\n    const sheet=Array.from(document.styleSheets).find(value=>value.href===location.origin+'/candidate.css');\n    if(!sheet)throw new Error('SAME_ORIGIN_STYLESHEET_MISSING');\n    sheet.insertRule('.candidate-cssom-positive{font-family:Arial;font-size:26px;color:#224466;background-color:#ddeeff;text-align:center}',sheet.cssRules.length);\n    const node=document.createElement('p');node.className='candidate-cssom-positive';node.id='candidate-cssom-positive';node.textContent='CSSOM-APPROVED';\n    document.querySelector('#cssom-control').append(node);return true;\n  },\n  roundtrip:()=>{const before=editor.getJSON(),html=editor.getHTML();reset(html);return {before,after:editor.getJSON(),html:editor.getHTML()};}\n};\nglobalThis.CANDIDATE_JS_ENABLED=(globalThis.CANDIDATE_JS_ENABLED||0)+1;\ndocument.querySelector('#candidate-status').textContent='Candidate-only editor loaded';";
const stylesheet='body{font:16px Arial,sans-serif;margin:16px}#candidate-editor{max-width:900px;border:1px solid #777;padding:12px;overflow-wrap:anywhere}#candidate-editor table{border-collapse:collapse;width:100%}#candidate-editor td,#candidate-editor th{border:1px solid #555;min-width:40px;padding:4px}p{margin:8px 0}';
const html='<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tiptap candidate-only probe</title><link rel="stylesheet" href="/candidate.css"></head><body><h1>Проверка кандидата Tiptap</h1><p id="candidate-status">Loading candidate only</p><div id="candidate-editor"></div><div id="cssom-control"></div><script src="/candidate.js"></script></body></html>';
try{
  ensure(fs.lstatSync(outputDirectory).isDirectory()&&!fs.lstatSync(outputDirectory).isSymbolicLink(),'ROOT_OUTPUT_DIRECTORY_REQUIRED');
  for(const name of ['tiptap-candidate.js','tiptap-candidate.html','candidate.css','tiptap-candidate.metafile.json','js-report.json','candidate-desktop.png','candidate-mobile.png']){
    const path=outputDirectory+'/'+name;
    if(fs.existsSync(path))ensure(fs.lstatSync(path).isFile()&&!fs.lstatSync(path).isSymbolicLink(),'UNSAFE_OUTPUT_ARTIFACT');
  }
  const installed={};
  for(const name of pins){
    const metadata=JSON.parse(fs.readFileSync('/deps/node_modules/'+name+'/package.json','utf8'));
    ensure(metadata.name===name&&metadata.version==='3.32.2','TIPTAP_INSTALLED_PIN_MISMATCH');installed[name]=metadata.version;
  }
  const esbuild=require('esbuild');
  ensure(esbuild.version==='0.28.2','ESBUILD_VERSION_MISMATCH');
  const native=JSON.parse(fs.readFileSync('/deps/node_modules/@esbuild/linux-x64/package.json','utf8'));
  ensure(native.version==='0.28.2','ESBUILD_PLATFORM_VERSION_MISMATCH');
  let artifactBytes;
  await check('PKG-JS-001',async()=>{
    const build=await esbuild.build({stdin:{contents:entry,resolveDir:'/deps',sourcefile:'qa-candidate-entry.js'},bundle:true,write:true,outfile:artifact,
      format:'iife',platform:'browser',target:'es2020',metafile:true,legalComments:'none',logLevel:'silent'});
    const inputs=Object.keys(build.metafile.inputs);
    ensure(!inputs.some(name=>/(?:^|\/)(?:react|react-dom|vue)(?:\/|$)/u.test(name)),'UNAPPROVED_REACT_VUE_BUNDLE');
    ensure(Object.values(build.metafile.outputs).every(value=>value.imports.length===0),'EXTERNAL_BUNDLE_IMPORTS');
    artifactBytes=fs.readFileSync(artifact);ensure(artifactBytes.length>1000,'EMPTY_BUNDLE');
    fs.writeFileSync(outputDirectory+'/tiptap-candidate.html',html,'utf8');
    fs.writeFileSync(outputDirectory+'/candidate.css',stylesheet,'utf8');
    fs.writeFileSync(outputDirectory+'/tiptap-candidate.metafile.json',JSON.stringify(build.metafile,null,2)+'\n','utf8');
    return {esbuild:esbuild.version,packages:installed,bundleBytes:artifactBytes.length,bundleSha256:hash(artifactBytes),actualBuildInputs:inputs.length,noReactVue:true};
  });
  const {chromium}=await import('/tests/node_modules/playwright/index.mjs');
  browser=await chromium.launch({headless:true});
  context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block',javaScriptEnabled:true});
  await context.addInitScript(()=>{
    globalThis.CANDIDATE_CSP_VIOLATIONS=[];
    document.addEventListener('securitypolicyviolation',event=>{
      globalThis.CANDIDATE_CSP_VIOLATIONS.push({directive:event.effectiveDirective,blockedUri:event.blockedURI,disposition:event.disposition});
    });
  });
  await context.route('**/*',async route=>{
    const url=new URL(route.request().url());
    if(url.origin!==syntheticOrigin){network.push({external:true,method:route.request().method()});await route.abort();return;}
    if(url.pathname==='/')await route.fulfill({status:200,contentType:'text/html; charset=utf-8',headers:{'Content-Security-Policy':policy},body:fs.readFileSync(outputDirectory+'/tiptap-candidate.html')});
    else if(url.pathname==='/candidate.js')await route.fulfill({status:200,contentType:'application/javascript',body:fs.readFileSync(artifact)});
    else if(url.pathname==='/candidate.css')await route.fulfill({status:200,contentType:'text/css',body:fs.readFileSync(outputDirectory+'/candidate.css')});
    else await route.fulfill({status:404,contentType:'text/plain',body:'QA synthetic origin only'});
  });
  page=await context.newPage();
  const pageErrors=[];page.on('pageerror',error=>pageErrors.push(error.name));
  await check('PKG-JS-002',async()=>{
    const response=await page.goto(syntheticOrigin+'/');
    ensure(response?.status()===200&&response.headers()['content-security-policy']===policy,'SYNTHETIC_HARNESS_POLICY_LOAD');
    await page.waitForFunction(()=>globalThis.candidate&&globalThis.CANDIDATE_JS_ENABLED===1);
    const names=await page.evaluate(()=>candidate.extensionNames);
    for(const name of ['bold','italic','underline','strike','paragraph','heading','table','textStyle','textAlign','subscript','superscript'])ensure(names.includes(name),'APPROVED_EXTENSION_MISSING_'+name);
    for(const name of ['code','codeBlock','horizontalRule','image'])ensure(!names.includes(name),'DISABLED_EXTENSION_ACTIVE_'+name);
    ensure(await page.locator('#candidate-editor [contenteditable=true]').count()===1,'EDITOR_DOM_NOT_REAL');
    return {realEditorCreated:true,jsEnabled:true,extensionNames:names};
  });
  await check('PKG-JS-009',async()=>{
    ensure(await page.evaluate(()=>candidate.cssom()),'SAME_ORIGIN_CSSOM_FAILED');
    const actual=await page.locator('#candidate-cssom-positive').evaluate(node=>{
      const style=getComputedStyle(node);return {fontSize:style.fontSize,color:style.color,fontFamily:style.fontFamily,background:style.backgroundColor,textAlign:style.textAlign};
    });
    ensure(actual.fontSize==='26px'&&actual.color==='rgb(34, 68, 102)'&&actual.fontFamily.includes('Arial')&&actual.background==='rgb(221, 238, 255)'&&actual.textAlign==='center','SAME_ORIGIN_CSSOM_COMPUTED_STYLE');
    const violations=await page.evaluate(()=>globalThis.CANDIDATE_CSP_VIOLATIONS);
    return {enforcedPolicy:policy,cssomClassComputedStyle:actual,observedViolations:violations,inlineStylesNotDeclaredProductSafe:true,productPolicyChanged:false};
  });
  await check('PKG-JS-010',async()=>{
    const regression=await page.evaluate(()=>candidate.prototypeRegression());
    ensure(regression.inputReallyOwnsProto,'PROTO_VECTOR_NOT_OWN_JSON_KEY');
    ensure(regression.resultPlainPrototype&&regression.safeOwnDataDescriptor&&regression.canaryNotInherited&&regression.globalPrototypeUnchanged,'MERGE_ATTRIBUTES_PROTOTYPE_REGRESSION');
    ensure(regression.ordinaryAttributesPreserved,'MERGE_ATTRIBUTES_POSITIVE_ATTRIBUTES_LOST');
    return {coreVersion:'3.32.2',advisory:'GHSA-cp6q-959q-f8rh',mergeAttributesFunctionSha256:hash(Buffer.from(regression.functionSource)),
      safeOwnDataProperty:true,prototypeUnchanged:true,noInheritedCanary:true,globalPrototypeUnchanged:true,ordinaryAttributesPreserved:true,markdownPackageAdded:false};
  });
  await check('PKG-JS-003',async()=>{
    ensure(await page.evaluate(()=>candidate.marks()),'MARK_COMMAND_FALSE');
    for(const tag of ['strong','em','u','s'])ensure(await page.locator('#candidate-editor '+tag).textContent()==='FORMAT-CANARY','MARK_DOM_'+tag);
    ensure(await page.evaluate(()=>candidate.heading()),'HEADING_COMMAND_FALSE');
    ensure(await page.locator('#candidate-editor h2').textContent()==='HEADING-CANARY','HEADING_DOM');
    ensure(await page.evaluate(()=>candidate.quote()),'QUOTE_COMMAND_FALSE');
    ensure(await page.locator('#candidate-editor blockquote').textContent()==='QUOTE-CANARY','QUOTE_DOM');
    ensure(await page.evaluate(()=>candidate.bullet()),'BULLET_COMMAND_FALSE');ensure(await page.locator('#candidate-editor ul li').count()===2,'BULLET_DOM');
    ensure(await page.evaluate(()=>candidate.ordered()),'ORDERED_COMMAND_FALSE');ensure(await page.locator('#candidate-editor ol li').count()===2,'ORDERED_DOM');
    ensure(await page.evaluate(()=>candidate.subscript()),'SUB_COMMAND_FALSE');ensure(await page.locator('#candidate-editor sub').textContent()==='SUB-CANARY','SUB_DOM');
    ensure(await page.evaluate(()=>candidate.superscript()),'SUP_COMMAND_FALSE');ensure(await page.locator('#candidate-editor sup').textContent()==='SUP-CANARY','SUP_DOM');
    ensure(await page.evaluate(()=>candidate.link()),'LINK_COMMAND_FALSE');
    const link=page.locator('#candidate-editor a');
    ensure(await link.getAttribute('href')==='/approved-reference/'&&await link.getAttribute('target')==='_blank'&&(await link.getAttribute('rel')).split(/\s/u).includes('noopener'),'LINK_DOM');
    return {marks:true,headings:true,lists:true,quote:true,subSup:true,safeLink:true};
  });
  await check('PKG-JS-004',async()=>{
    ensure(await page.evaluate(()=>candidate.table()),'TABLE_INSERT_FALSE');
    const shape=()=>page.locator('#candidate-editor tr').evaluateAll(rows=>rows.map(row=>row.querySelectorAll('th,td').length));
    ensure(JSON.stringify(await shape())==='[2,2]'&&await page.locator('#candidate-editor th').count()===2,'TABLE_INITIAL_SHAPE');
    await page.locator('#candidate-editor th').first().click();await page.keyboard.type('TABLE-CELL-CANARY');
    ensure((await page.locator('#candidate-editor table').textContent()).includes('TABLE-CELL-CANARY'),'CELL_EDIT_DOM');
    ensure(await page.evaluate(()=>candidate.editor.chain().focus().addRowAfter().run()),'TABLE_ADD_ROW');ensure(JSON.stringify(await shape())==='[2,2,2]','TABLE_ADD_ROW_SHAPE');
    ensure(await page.evaluate(()=>candidate.editor.chain().focus().addColumnAfter().run()),'TABLE_ADD_COLUMN');ensure(JSON.stringify(await shape())==='[3,3,3]','TABLE_ADD_COLUMN_SHAPE');
    ensure(await page.evaluate(()=>candidate.editor.chain().focus().deleteRow().run()),'TABLE_DELETE_ROW');ensure(JSON.stringify(await shape())==='[3,3]','TABLE_DELETE_ROW_SHAPE');
    ensure(await page.evaluate(()=>candidate.editor.chain().focus().deleteColumn().run()),'TABLE_DELETE_COLUMN');ensure(JSON.stringify(await shape())==='[2,2]','TABLE_DELETE_COLUMN_SHAPE');
    const roundtrip=await page.evaluate(()=>candidate.roundtrip());
    ensure(JSON.stringify(roundtrip.before)===JSON.stringify(roundtrip.after),'TABLE_ROUNDTRIP');
    return {inserted2x2Header:true,realKeyboardCellEdit:true,rowColumnCommands:true,documentRoundtrip:true};
  });
  await check('PKG-JS-005',async()=>{
    ensure(await page.evaluate(()=>candidate.style()),'STYLE_COMMAND_FALSE');
    const actual=await page.locator('#candidate-editor span').first().evaluate(node=>{
      const style=getComputedStyle(node),paragraph=getComputedStyle(node.closest('p'));
      return {family:style.fontFamily,size:style.fontSize,color:style.color,background:style.backgroundColor,align:paragraph.textAlign};
    });
    ensure(actual.family.includes('Arial')&&actual.size==='24px'&&actual.color==='rgb(18, 52, 86)'&&actual.background==='rgb(221, 238, 255)'&&actual.align==='center','STYLE_COMPUTED_BASELINE');
    return {computedStyle:actual,notProductLimitsOrCspFix:true};
  });
  await check('PKG-JS-006',async()=>{
    const roundtrip=await page.evaluate(()=>candidate.roundtrip());
    ensure(JSON.stringify(roundtrip.before)===JSON.stringify(roundtrip.after),'SAFE_STYLE_ROUNDTRIP');
    ensure(await page.locator('#candidate-editor').textContent()==='STYLE-CANARY','ROUNDTRIP_TEXT');
    return {approvedPositiveRoundtrip:true,noDangerousInputPassedToEditor:true};
  });
  await check('PKG-JS-007',async()=>{
    ensure(network.length===0,'EXTERNAL_CANDIDATE_REQUEST');ensure(pageErrors.length===0,'BROWSER_PAGE_ERROR');
    ensure(hash(fs.readFileSync(artifact))===hash(artifactBytes),'BUILT_ARTIFACT_DRIFT');
    return {externalRequests:0,artifactSha256:hash(artifactBytes),productSiteContacted:false};
  });
  await check('PKG-JS-008',async()=>{
    for(const [name,width]of [['desktop',1280],['mobile',390]]){
      await page.setViewportSize({width,height:900});ensure(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'QA_HARNESS_HORIZONTAL_OVERFLOW');
      await page.screenshot({path:outputDirectory+'/candidate-'+name+'.png',fullPage:true});
    }
    return {widths:[1280,390],syntheticHarnessOnly:true};
  });
  const report={scope:'candidate-packages-only',status:'PASS',checks:facts,observedCspViolations:await page.evaluate(()=>globalThis.CANDIDATE_CSP_VIOLATIONS??[]),productSanitizerOrAuthorizationTested:false,productRendererTested:false};
  fs.writeFileSync(outputDirectory+'/js-report.json',JSON.stringify(report,null,2)+'\n','utf8');console.log(JSON.stringify(report));
}catch(error){
  let violations=[];try{violations=await page?.evaluate(()=>globalThis.CANDIDATE_CSP_VIOLATIONS??[])??[];}catch{}
  const report={scope:'candidate-packages-only',status:'FAIL',failedAt:current,errorClass:error.name,message:String(error.message??'').replace(/\s+/gu,' ').slice(0,240),
    observedCspViolations:violations,checks:facts,productSanitizerOrAuthorizationTested:false,productRendererTested:false};
  if(fs.existsSync(outputDirectory)&&fs.lstatSync(outputDirectory).isDirectory()&&!fs.lstatSync(outputDirectory).isSymbolicLink()){
    const reportPath=outputDirectory+'/js-report.json';
    if(!fs.existsSync(reportPath)||fs.lstatSync(reportPath).isFile()&&!fs.lstatSync(reportPath).isSymbolicLink())fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n','utf8');
  }
  console.log(JSON.stringify(report));process.exitCode=1;
}finally{
  await context?.close().catch(()=>{});await browser?.close().catch(()=>{});
}
