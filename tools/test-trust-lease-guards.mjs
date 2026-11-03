// D-391: finite VM checks of actual lease functions. No Docker, DB, keys or private IO.
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';
import vm from 'node:vm';import assert from 'node:assert/strict';import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const source=fs.readFileSync(path.join(root,'tools/lease-trust-runtime.mjs'),'utf8');
const sourceSha256=crypto.createHash('sha256').update(source).digest('hex');
function line(prefix){const a=source.split('\n').filter(x=>x.startsWith(prefix));assert.equal(a.length,1,'one actual function');return a[0];}
const project='nestakada-trust-test',apiId='b'.repeat(64),dbId='a'.repeat(64),ingressId='c'.repeat(64),run='00000000-0000-4000-8000-000000000001';
const ensure=(v,c)=>{if(!v)throw Error(c);};
function lifecycle(){const s={runtimeId:run,apiProfile:'disabled',apiId:null,previous:{runtimeId:'old'},permitIdentity:{dev:'1',ino:'2'}};
 const m={images:{postgres:'db-image','python-runtime':'api-image','local-ingress':'ingress-image'},sourceDirectory:'/source'};
 const services={};for(const [service,id,limits,image,nets]of [
  ['db',dbId,[536870912,500000000,128],'db-image',['db']],
  ['api',apiId,[268435456,500000000,64],'api-image',['api','db']],
  ['ingress',ingressId,[134217728,250000000,64],'ingress-image',['api','client']]]){
  services[id]={Id:id,Name:'/'+project+'-'+service,Image:image,
   Config:{Labels:{'nestakada.scope':'trust-test','com.docker.compose.project':project,
    'com.docker.compose.service':service,'nestakada.lease-run':run},Env:service==='api'?[
     'TRUST_RUNTIME_ID='+run,'TRUST_WRITE_PROFILE=disabled','TRUST_DB_NAME=estakada_trust','TRUST_DB_USER=trust_runtime']:[]},
   HostConfig:{ReadonlyRootfs:true,Memory:limits[0],MemorySwap:limits[0],NanoCpus:limits[1],PidsLimit:limits[2],
    LogConfig:{Type:'json-file',Config:{'max-size':'1m','max-file':'2'}}},
   Mounts:service==='db'?[{Type:'volume',Name:project+'-dbdata',Destination:'/var/lib/postgresql',RW:true}]:service==='api'?[
    {Type:'bind',Source:'/source',Destination:'/trust',RW:false},
    {Type:'bind',Source:'/private/write-profile.json',Destination:'/run/secrets/write-profile.json',RW:false}]:[],
   NetworkSettings:{Ports:{},Networks:Object.fromEntries(nets.map(n=>[project+'-'+n,{}]))},State:{Running:true}};
 }
 const calls={inspect:0,mutations:[],revocations:0};const c={project,m,s,permitFile:'/private/write-profile.json',
  ownershipRefused:false,stopRefused:false,cleanupAttempted:false,report:{status:'FAIL',cleanupErrors:[]},
  ensure,stable:JSON.stringify,projectIds:()=>Object.keys(services),
  inspect:id=>{calls.inspect++;const v=services[id]||Object.values(services).find(x=>x.Name==='/'+id);ensure(v,'FAKE_NOT_FOUND');return v;},
  absent:id=>ensure(!services[id],'FAKE_STILL_EXISTS'),
  docker:args=>{const id=args.at(-1);ensure(services[id],'FAKE_NOT_FOUND');calls.mutations.push([...args]);
   if(args[0]==='stop'){services[id].State.Running=false;return {status:0};}
   if(args[0]==='rm'){ensure(!services[id].State.Running,'FAKE_RUNNING');delete services[id];return {status:0};}
   throw Error('UNEXPECTED_FAKE_DOCKER');},
  revokeOnce:()=>{calls.revocations++;return {status:'REVOKED',permitEmpty:true};}};
 const ctx=vm.createContext(c);vm.runInContext(['function mountPath(','function ownedOnce(','function owned(',
  'function allOwnedOnce(','function allOwned(','function stopFrontOnce(','function stopFront(',
  'function removeStoppedFront(','function scopedStop(','function failureCleanup('].map(line).join('\n'),ctx,{timeout:1000});
 return {s,c,calls,services,run:code=>vm.runInContext(code,ctx,{timeout:1000})};}
function fileFixture({fdMismatch=false,pathMismatch=false}={}){let content=Buffer.from('{}\n');
 const calls={open:0,write:0,truncate:0,close:0};const identity={dev:'1',ino:'2'};
 const stat=ino=>({dev:1n,ino:BigInt(ino),isFile:()=>true,isSymbolicLink:()=>false});
 const c={Buffer,permitFile:'/private/write-profile.json',permitIdentityRefused:false,permitMayBeValid:false,
  revocationAttempted:false,revocationResult:null,report:{cleanupErrors:[]},identity,value:Buffer.from('{"new":true}\n'),
  ensure,stable:JSON.stringify,inside:x=>x,read:()=>Buffer.from(content),mac:()=> 'unused-no-keys',
  s:{runtimeId:run,previous:{runtimeId:'old'},permitIdentity:identity},fs:{
   lstatSync:()=>stat(pathMismatch?9:2),openSync:(p,flags)=>{assert.equal(flags,'r+');calls.open++;return 42;},
   fstatSync:()=>stat(fdMismatch?9:2),
   writeSync:(fd,b,offset,length,position)=>{calls.write++;const n=Buffer.alloc(Math.max(content.length,position+length));content.copy(n);b.copy(n,position,offset,offset+length);content=n;return length;},
   ftruncateSync:(fd,n)=>{calls.truncate++;content=content.subarray(0,n);},fsyncSync:()=>{},closeSync:()=>{calls.close++;}}};
 const ctx=vm.createContext(c);vm.runInContext(['function fileIdentity(','function publishOnce(','function publish(',
  'function revokeOnce('].map(line).join('\n'),ctx,{timeout:1000});
 return {c,calls,content:()=>content,run:code=>vm.runInContext(code,ctx,{timeout:1000})};}
function publication({running=false,changed=false}={}){const c={ensure,ownershipRefused:false,permitMayBeValid:false,
 s:{apiId,permitIdentity:{dev:'1',ino:'2'}},value:Buffer.from('{}\n'),writes:0,inspections:0,
 inspect:()=>{c.inspections++;return {Id:changed&&c.inspections>1?'d'.repeat(64):apiId,State:{Running:running}};},
 owned:()=>{},publish:()=>{c.writes++;}};
 const ctx=vm.createContext(c);vm.runInContext([line('function finalApi('),line('function publishValid(')].join('\n'),ctx,{timeout:1000});
 return {c,run:code=>vm.runInContext(code,ctx,{timeout:1000})};}
function negativeFixture(code,disabled=false){const state={head:{generation:10,writer_epoch:2},credentialBindings:[{id:'active',role:'writer',active:true,writer_epoch:2}]};
 const c={ensure,s:{runtimeId:run},disabled,m:{incarnation:run},crypto:{randomUUID:()=>run},
 sha:()=> 'digest',Buffer,stable:JSON.stringify,negativePostSent:false,invariant:()=>{},snapshot:()=>state,
 probe:(s,action)=>action==='admission'?{admission:{faultCode:disabled?'WRITE_PROFILE_DISABLED':'BOUNDED_ADMISSION_REJECTED'}}:
  {request:{statusCode:503,body:{ok:false,code}},permitFile:{}}};
 const ctx=vm.createContext(c);vm.runInContext(line('function negative('),ctx,{timeout:1000});
 return {c,run:()=>vm.runInContext('negative(s,disabled)',ctx,{timeout:1000})};}
const cases=[];function check(id,fn){fn();cases.push({id,status:'PASS'});}
let status='FAIL',errorCode=null;
try{
 assert.equal(process.argv.length,2,'closed CLI');
 assert.ok(source.includes("command('docker.exe',['--context','desktop-linux',...a],o)"),'explicit local Docker context');
 assert.ok(source.includes('publishValid(current,raw);startSame(current)'),'real Enable checks post-publication CID before start');
 assert.ok(line('}catch(error){').includes("report.status='FAIL'"),'real catch cannot preserve stale PASS');
 check('RLG15-001-partial-disabled-cleanup',()=>{const t=lifecycle();const value=t.run('failureCleanup(s)');assert.equal(value.status,'CLOSED_FAILED_PHASE');assert.equal(Object.keys(t.services).length,0);assert.equal(t.calls.revocations,1);assert.equal(t.calls.mutations.filter(x=>x[0]==='stop').length,3);});
 check('RLG15-002-foreign-ownership-no-second-guard',()=>{const t=lifecycle();t.services[apiId].Config.Labels['nestakada.lease-run']='foreign';assert.throws(()=>t.run('allOwned(s)'),/LEASE_RUN_OWNERSHIP/);const n=t.calls.inspect;assert.equal(t.run('failureCleanup(s)').status,'RESTORATION_NOT_PROVEN');assert.equal(t.calls.inspect,n);assert.equal(t.calls.revocations,1);assert.equal(t.calls.mutations.length,0);t.run('failureCleanup(s)');assert.equal(t.calls.revocations,1);});
 check('RLG15-003-stop-refusal-no-repeated-stop',()=>{const t=lifecycle();const original=t.c.docker;t.c.docker=args=>{if(args[0]==='stop'){t.calls.mutations.push([...args]);throw Error('FAKE_STOP_FAILED');}return original(args);};assert.throws(()=>t.run('stopFront(s)'),/FAKE_STOP_FAILED/);const n=t.calls.inspect;t.run('failureCleanup(s)');assert.equal(t.calls.inspect,n);assert.equal(t.calls.mutations.length,1);assert.equal(t.calls.revocations,1);});
 check('RLG15-004-fd-mismatch-before-write-truncate',()=>{const t=fileFixture({fdMismatch:true});assert.throws(()=>t.run('publish(value,identity)'),/LEASE_PERMIT_FD_IDENTITY/);assert.equal(t.calls.open,1);assert.equal(t.calls.close,1);assert.equal(t.calls.write,0);assert.equal(t.calls.truncate,0);assert.equal(t.c.permitIdentityRefused,true);assert.equal(t.run('revokeOnce(s)').status,'REVOCATION_NOT_PROVEN');assert.equal(t.calls.open,1);});
 check('RLG15-005-path-mismatch-before-open',()=>{const t=fileFixture({pathMismatch:true});assert.throws(()=>t.run('publish(value,identity)'),/LEASE_PERMIT_PATH_IDENTITY/);assert.equal(t.calls.open,0);assert.equal(t.calls.write,0);});
 check('RLG15-006-same-inode-publish-readback',()=>{const t=fileFixture();t.run('publish(value,identity)');assert.equal(t.content().toString(),t.c.value.toString());assert.equal(t.calls.open,1);assert.equal(t.calls.truncate,1);assert.equal(t.calls.close,1);});
 check('RLG15-007-running-api-no-publication',()=>{const t=publication({running:true});assert.throws(()=>t.run('publishValid(s,value)'),/LEASE_FINAL_CID_OR_STATE_CHANGED/);assert.equal(t.c.writes,0);assert.equal(t.c.ownershipRefused,true);});
 check('RLG15-008-final-cid-changed-after-publication',()=>{const t=publication({changed:true});assert.throws(()=>t.run('publishValid(s,value)'),/LEASE_FINAL_CID_OR_STATE_CHANGED/);assert.equal(t.c.writes,1);assert.equal(t.c.ownershipRefused,true);assert.equal(t.c.permitMayBeValid,true);});
 check('RLG15-009-stopped-same-final-cid',()=>{const t=publication();t.run('publishValid(s,value)');assert.equal(t.c.inspections,2);assert.equal(t.c.writes,1);});
 check('RLG15-010-negative-rejects-unrelated-503',()=>{assert.throws(()=>negativeFixture('TRUST_UNAVAILABLE').run(),/LEASE_EXPECTED_503/);});
 check('RLG15-011-disabled-exact-503',()=>{assert.equal(negativeFixture('WRITE_PROFILE_DISABLED',true).run().statusCode,503);});
 check('RLG15-012-bounded-exact-503',()=>{assert.equal(negativeFixture('BOUNDED_ADMISSION_REJECTED').run().statusCode,503);});
 check('RLG15-013-report-write-failure-revokes-once',()=>{const c={report:{status:'PASS',cleanupErrors:[]},evidenceIncomplete:false,
  sessionTouched:true,current:{runtimeId:run},cleanupAttempted:false,count:0,save:()=>{throw Error('FAKE_DIAG_WRITE');},
  failureCleanup:()=>{c.count++;c.cleanupAttempted=true;return {status:'CLOSED_FAILED_PHASE'};},
  reportFile:'/work/report.json',phase:'Enable',root:'/work',path:{relative:()=> 'report.json'},console:{log:()=>{}},process:{}};
  const ctx=vm.createContext(c);vm.runInContext('try{}'+line('finally{'),ctx,{timeout:1000});assert.equal(c.report.status,'FAIL');assert.equal(c.count,1);assert.equal(c.process.exitCode,1);});
 check('RLG15-014-only-stop-loads-authenticated-partial',()=>{const draft={runtimeId:run,sourceFingerprint:'source',schemaFingerprint:'schema',apiProfile:'local-bounded-writer'},calls=[];
  const c={run,SOURCE:'source',SCHEMA:'schema',ensure,work:'/work',uuid:x=>x,statePath:()=>'/work/prepared.json',
   path:{join:(...x)=>x.join('/')},fs:{existsSync:p=>p.includes('final-creation-')},
   signed:(p,scope)=>{calls.push({p,scope});assert.equal(scope,'RL15-FINAL-CREATION-INTENT');return draft;}};
  const ctx=vm.createContext(c);vm.runInContext(line('function load('),ctx,{timeout:1000});
  assert.throws(()=>vm.runInContext('load(run)',ctx,{timeout:1000}),/LEASE_RUN_STATE/);
  assert.equal(vm.runInContext('load(run,{allowPartial:true})',ctx,{timeout:1000}),draft);assert.equal(calls.length,1);});
 check('RLG15-015-remote-context-refused',()=>{const calls=[],c={ensure,docker:a=>{calls.push(a);return {stdout:JSON.stringify([{Name:'desktop-linux',Endpoints:{docker:{Host:'ssh://remote'}}}])};}};
  const ctx=vm.createContext(c);vm.runInContext(line('function verifyDockerContext('),ctx,{timeout:1000});
  assert.throws(()=>vm.runInContext('verifyDockerContext()',ctx,{timeout:1000}),/LEASE_LOCAL_DESKTOP_CONTEXT/);assert.equal(calls.length,1);});
 check('RLG15-016-other-local-pipe-refused',()=>{const calls=[],c={ensure,docker:a=>{calls.push(a);return {stdout:JSON.stringify([{Name:'desktop-linux',Endpoints:{docker:{Host:'npipe:////./pipe/otherLocalEngine'}}}])};}};
  const ctx=vm.createContext(c);vm.runInContext(line('function verifyDockerContext('),ctx,{timeout:1000});
  assert.throws(()=>vm.runInContext('verifyDockerContext()',ctx,{timeout:1000}),/LEASE_LOCAL_DESKTOP_CONTEXT/);assert.equal(calls.length,1);});
 status='PASS';
}catch(error){errorCode=/^LEASE_[A-Z0-9_]+$/.test(error?.message||'')?error.message:'LEASE_GUARD_ASSERTION_FAILED';}
console.log(JSON.stringify({status,scope:'actual-lease-functions-VM-fakeFS-fakeDocker-not-runtime',sourceSha256,cases,count:cases.length,
 errorCode,dockerInvoked:false,databaseConnected:false,privateFilesRead:false,filesWritten:false}));
if(status!=='PASS')process.exitCode=1;
