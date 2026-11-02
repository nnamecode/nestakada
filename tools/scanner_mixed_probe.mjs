// SC20-011: one bounded, genuine authenticated read overlapping a local scan.
import fs from 'node:fs';
import readline from 'node:readline';
import {chromium} from '/tests/node_modules/playwright/index.mjs';
const seed=JSON.parse(fs.readFileSync('/private/guard-seed.json','utf8'));
const origin='http://host.docker.internal:8767',pending=new Map();
let serial=0,browser,context;
const emit=value=>process.stdout.write(JSON.stringify(value)+'\n');
const ensure=(value,code)=>{if(!value)throw Error(code);};
const channel=readline.createInterface({input:process.stdin});
channel.on('line',line=>{const value=JSON.parse(line),item=pending.get(value.id);if(item){pending.delete(value.id);clearTimeout(item.timer);value.error?item.reject(Error('CONTROL_REFUSED')):item.resolve(value.value);}});
function control(action){return new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{pending.delete(id);reject(Error('CONTROL_TIMEOUT'));},45000);pending.set(id,{resolve,reject,timer});emit({kind:'control',id,action});});}
async function scan(){const startedAt=Date.now(),deadline=startedAt+8000;let cursor=0,allowed=0,limited=0;await Promise.all(Array.from({length:5},async()=>{for(;;){const n=cursor++;if(n>=90)break;const remaining=deadline-Date.now();ensure(remaining>0,'MIXED_SCAN_DEADLINE');const r=await fetch(origin+'/.env?noise=DEV20-PRIVATE-CANARY-'+n,{redirect:'manual',signal:AbortSignal.timeout(Math.min(3000,remaining))});const body=Buffer.from(await r.arrayBuffer());ensure([404,429].includes(r.status)&&(r.headers.get('cache-control')||'').includes('no-store')&&!r.headers.has('set-cookie')&&!body.includes(Buffer.from('DEV20-PRIVATE-CANARY')),'MIXED_SCAN_RESPONSE');if(r.status===404)allowed++;else limited++;}}));return{startedAt,finishedAt:Date.now(),requests:90,allowed,limited,concurrency:5};}
async function usefulRead(){const startedAt=Date.now(),response=await context.request.get(origin+seed.pages.media.url,{maxRedirects:0,timeout:15000});const body=await response.body();return{startedAt,finishedAt:Date.now(),status:response.status(),editorMarker:body.includes(Buffer.from('id="editor-initial-state"'))};}
try{
 const before=await control('sample');browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});context=await browser.newContext({serviceWorkers:'block'});await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
 const page=await context.newPage();await page.goto(origin+'/manage/login/');await page.locator('[name=username]').fill(seed.accounts.owner.username);await page.locator('[name=password]').fill(seed.accounts.owner.password);await Promise.all([page.waitForURL(origin+'/manage/'),page.locator('form[action="/manage/login/"] button').click()]);await page.close();
 await new Promise(resolve=>setTimeout(resolve,4000));
 const [read,noise]=await Promise.all([usefulRead(),scan()]);
 const overlapMs=Math.min(read.finishedAt,noise.finishedAt)-Math.max(read.startedAt,noise.startedAt);
 ensure(read.status===200&&read.editorMarker&&overlapMs>0,'NO_SUCCESSFUL_OVERLAPPING_ADMIN_READ');ensure(noise.allowed>0&&noise.limited>0,'MIXED_RATE_NOT_OBSERVED');
 await new Promise(resolve=>setTimeout(resolve,4000));const recovery=await usefulRead();ensure(recovery.status===200&&recovery.editorMarker,'MIXED_RECOVERY_FAILED');
 const after=await control('sample');ensure(before.domainHash===after.domainHash,'MIXED_MUTATED_CONTENT');
 emit({kind:'result',status:'PASS',groups:[{id:'SC20-N07',status:'PASS',read,scan:noise,overlapMs,recovery,concurrentRequestsAtMostSix:true,noSave:true}],scope:'one-local-mixed-component-witness-not-full-PERF-SCAN'});
}catch(error){emit({kind:'result',status:'FAIL',phase:'SC20-N07',errorCode:/^[A-Z0-9_]{1,100}$/u.test(error?.message||'')?error.message:'MIXED_UI_OR_TRANSPORT_FAILURE',groups:[]});process.exitCode=1;}
finally{await context?.close().catch(()=>{});await browser?.close().catch(()=>{});channel.close();}
