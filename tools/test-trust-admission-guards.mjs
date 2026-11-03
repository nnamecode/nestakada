// Finite AD15 host guard checks. Fake Docker only: no process launch/DB/private IO.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
import path from 'node:path';import crypto from 'node:crypto';import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const source=fs.readFileSync(path.join(root,'tools/admit-trust-runtime.mjs'),'utf8');
const sourceSha256=crypto.createHash('sha256').update(source).digest('hex');
const project='nestakada-trust-test',full='a'.repeat(64),foreign='b'.repeat(64);
function line(prefix){const rows=source.split('\n').filter(x=>x.startsWith(prefix));assert.equal(rows.length,1,'unique actual function');return rows[0];}
const snippets=['function fullIds(','const projectIds=','const namedIds=','function dbOwned(',
 'function preToolGuard(','function runTool(','function archiveProof(',
 'function closeChangedArchives(','function finishArchiveChecks('].map(line).join('\n');
assert.ok(line('function runToolOnce(').includes('{preToolGuard();'),'real runner invokes guard before create');
assert.ok(source.includes('if(archive)catalogMayHaveChanged=true;helperSendSerial++;'),'real pre-send accounting exists');
assert.ok(source.includes('finishArchiveChecks();try{stopDatabase();'),'actual finally dispatches guarded preservation');
assert.ok(source.includes('enforceFinalStatus();const b=Buffer.from(stable(report)'),'actual final report enforces diagnostic failure');
function database(){return {Id:full,Name:'/'+project+'-db',Image:'fixed-db-image',
 Config:{Labels:{'nestakada.scope':'trust-test','com.docker.compose.project':project,'com.docker.compose.service':'db'}},
 HostConfig:{Memory:536870912,MemorySwap:536870912,NanoCpus:500000000,PidsLimit:128,ReadonlyRootfs:true},
 Mounts:[{Type:'volume',Name:project+'-dbdata',Destination:'/var/lib/postgresql',RW:true},
  {Type:'bind',Destination:'/run/secrets/database-ca',RW:false}],
 NetworkSettings:{Networks:{[project+'-db']:{}},Ports:{}},State:{Running:true}};}
function fixture(){const calls={docker:[],inspect:[],mutations:[],proof:[],close:0};const state={
 project,dbId:full,toolSafe:true,helperSendSerial:0,preSendGuardFailed:false,
 archiveProofFailed:false,catalogMayHaveChanged:false,m:{images:{postgres:'fixed-db-image'}},
 report:{status:'PASS',archivesPreserved:false,cleanupErrors:[]},chain:{report:{}},root:'/fixture',archives:'fake-code',
 ids:full+'\n',db:database(),mode:'pass',calls,Buffer,
 ensure:(v,c)=>{if(!v)throw Error(c);},stable:JSON.stringify,sha:()=> 'digest',
 read:()=>Buffer.from('fake-public-dependency'),path:{join:(...parts)=>parts.join('/')},
 docker:args=>{assert.equal(args[0],'ps','no mutating Docker commands in VM');assert.ok(args.includes('--no-trunc'));calls.docker.push([...args]);return {stdout:state.ids};},
 inspect:id=>{calls.inspect.push(id);return state.db;},
 runToolOnce:(code,arg,label)=>{calls.proof.push(label);vm.runInContext('preToolGuard()',context,{timeout:1000});
  calls.mutations.push('fake-compose-create');state.helperSendSerial++;state.catalogMayHaveChanged=true;
  if(state.mode==='sent-fail')throw Error('FAKE_POST_SEND_FAILURE');return {archivesClosed:true};},
 closeKnownArchives:()=>{calls.close++;if(state.mode==='close-fail')throw Error('FAKE_CLOSE_FAILURE');
  state.catalogMayHaveChanged=false;return {status:'CLOSED_NOT_ROW_VERIFIED',fullRowsVerified:false};}};
 const context=vm.createContext(state);vm.runInContext(snippets,context,{timeout:1000});
 return {state,calls,run:code=>vm.runInContext(code,context,{timeout:1000})};}
function reapFixture(){const id='c'.repeat(64),runId='fixture-run',spec={name:project+'-admit-fixture',service:'migrate',source:'/source',id};
 const calls={docker:[],ownershipInspects:0,resourceChecks:0},v={Id:id,Name:'/'+spec.name,Image:'fixed-python-image',
  Config:{Labels:{'nestakada.scope':'trust-test','com.docker.compose.project':project,
   'com.docker.compose.service':'migrate','nestakada.admission-run':runId}},
  HostConfig:{Memory:268435456,MemorySwap:268435456,NanoCpus:500000000,PidsLimit:64,ReadonlyRootfs:true,
   LogConfig:{Type:'json-file',Config:{'max-size':'1m','max-file':'2'}}},
  Mounts:[{Type:'bind',Destination:'/trust',Source:'/source',RW:false},
   {Type:'bind',Destination:'/evidence',Source:'/package',RW:false}],
  NetworkSettings:{Networks:{[project+'-db']:{}},Ports:{}},State:{Running:true}};
 let alive=true;const state={project,runId,pkg:'/package',priv:'/private',spec,
  m:{images:{'python-runtime':'fixed-python-image'}},live:new Map([[spec.name,spec]]),toolSafe:false,
  report:{status:'PASS',cleanupErrors:[]},ensure:(ok,code)=>{if(!ok)throw Error(code);},
  path:{join:(...x)=>x.join('/')},crypto:{randomUUID:()=> 'fixture'},
  save:()=>{throw Error('FAKE_PRIVATE_WRITE_FAILURE');},bytes:()=>{throw Error('FAKE_PRIVATE_WRITE_FAILURE');},
  inspect:()=>{calls.ownershipInspects++;return v;},resourcesOwned:()=>{calls.resourceChecks++;throw Error('UNEXPECTED_RESOURCE_CHECK');},
  docker:args=>{calls.docker.push([...args]);if(args[0]==='ps'){assert.ok(args.includes('--no-trunc'));return {stdout:alive?id+'\n':''};}
   if(args[0]==='stop'){assert.equal(args.at(-1),id);v.State.Running=false;return {status:0,stdout:''};}
   if(args[0]==='logs')return {status:0,stdout:'fake-safe-log',stderr:''};
   if(args[0]==='rm'){assert.equal(args[1],id);alive=false;return {status:0,stdout:''};}
   throw Error('UNEXPECTED_FAKE_DOCKER_COMMAND');}};
 const context=vm.createContext(state);vm.runInContext(['function fullIds(','const namedIds=',
  'function mountPath(','function toolOwned(','function reap(','function stopDatabase(',
  'function enforceFinalStatus('].map(line).join('\n'),context,{timeout:1000});
 const finalLine=line(' if(dbStarted){'),start=finalLine.indexOf('for(const spec'),end=finalLine.indexOf('finishArchiveChecks();');
 assert.ok(start>0&&end>start,'actual outer cleanup loop exists');
 return {state,calls,spec,v,outer:finalLine.slice(start,end),run:code=>vm.runInContext(code,context,{timeout:1000})};}
const cases=[];
function check(id,body){body();cases.push({id,status:'PASS'});}
let status='FAIL',errorCode=null;
try{
 assert.equal(process.argv.length,2,'no arguments');
 check('ADG15-001-full-id-owned-db',()=>{const t=fixture();t.run('preToolGuard()');assert.deepEqual(t.calls.inspect,[full]);assert.equal(t.calls.mutations.length,0);t.run('namedIds("fixture")');assert.ok(t.calls.docker.every(a=>a.includes('--no-trunc')));});
 check('ADG15-002-short-id-refused-before-inspect',()=>{const t=fixture();t.state.ids=full.slice(0,12)+'\n';assert.throws(()=>t.run('preToolGuard()'),/ADMIT_CONTAINER_ID_FORMAT/);assert.equal(t.calls.inspect.length,0);assert.equal(t.calls.mutations.length,0);});
 check('ADG15-003-duplicate-or-nonhex-id-refused',()=>{for(const ids of [full+'\n'+full+'\n','z'.repeat(64)+'\n']){const t=fixture();t.state.ids=ids;assert.throws(()=>t.run('preToolGuard()'),/ADMIT_CONTAINER_ID_FORMAT/);assert.equal(t.calls.mutations.length,0);}});
 check('ADG15-004-foreign-volume-refused',()=>{const t=fixture();t.state.db.Mounts[0].Name='foreign-data';assert.throws(()=>t.run('preToolGuard()'),/ADMIT_DATABASE_OWNERSHIP/);assert.equal(t.calls.mutations.length,0);});
 check('ADG15-005-inspect-id-mismatch-refused',()=>{const t=fixture();t.state.db.Id=foreign;assert.throws(()=>t.run('preToolGuard()'),/ADMIT_INSPECT_ID_MISMATCH/);assert.equal(t.calls.mutations.length,0);});
 check('ADG15-006-early-refusal-no-after-or-close',()=>{const t=fixture();t.state.ids=full.slice(0,12)+'\n';assert.throws(()=>t.run('archiveProof("before")'),/ADMIT_CONTAINER_ID_FORMAT/);t.run('finishArchiveChecks()');assert.equal(t.calls.proof.length,1);assert.equal(t.calls.close,0);assert.equal(t.calls.mutations.length,0);assert.equal(t.state.report.status,'FAIL');assert.equal(t.state.report.archivesPreserved,false);assert.equal(t.state.report.archivesAfter.status,'NOT_RUN');});
 check('ADG15-007-sent-failure-one-close-no-row-pass',()=>{const t=fixture();t.state.mode='sent-fail';assert.throws(()=>t.run('archiveProof("before")'),/FAKE_POST_SEND_FAILURE/);t.run('finishArchiveChecks()');assert.equal(t.calls.proof.length,1);assert.equal(t.calls.close,1);assert.equal(t.state.report.status,'FAIL');assert.equal(t.state.report.archivesPreserved,false);assert.equal(t.state.report.archiveRestoration.fullRowsVerified,false);});
 check('ADG15-008-after-early-refusal-no-repeat-cleanup',()=>{const t=fixture();t.state.report.archivesBefore=t.run('archiveProof("before")');assert.equal(t.state.catalogMayHaveChanged,false);t.state.ids=full.slice(0,12)+'\n';t.run('finishArchiveChecks()');assert.deepEqual(t.calls.proof,['archives-before','archives-after']);assert.equal(t.calls.close,0);assert.equal(t.state.report.status,'FAIL');assert.equal(t.state.report.archivesPreserved,false);});
 check('ADG15-009-close-failure-not-retried',()=>{const t=fixture();t.state.mode='sent-fail';assert.throws(()=>t.run('archiveProof("before")'),/FAKE_POST_SEND_FAILURE/);t.state.mode='close-fail';t.run('finishArchiveChecks()');assert.equal(t.calls.close,1);assert.equal(t.calls.proof.length,1);assert.equal(t.state.report.archiveRestoration.status,'RESTORATION_NOT_PROVEN');assert.equal(t.state.report.status,'FAIL');});
 check('ADG15-010-successful-before-after',()=>{const t=fixture();t.state.report.archivesBefore=t.run('archiveProof("before")');t.run('finishArchiveChecks()');assert.deepEqual(t.calls.proof,['archives-before','archives-after']);assert.equal(t.calls.close,0);assert.equal(t.state.report.archivesPreserved,true);assert.equal(t.state.catalogMayHaveChanged,false);});
 check('ADG15-011-prior-guard-blocks-close-overlap',()=>{const t=fixture();t.state.catalogMayHaveChanged=true;t.state.preSendGuardFailed=true;t.run('finishArchiveChecks()');assert.equal(t.calls.close,0);assert.equal(t.calls.proof.length,0);assert.equal(t.state.report.archiveRestoration.status,'RESTORATION_NOT_PROVEN');assert.equal(t.state.report.archivesPreserved,false);});
 check('ADG15-012-logging-failure-reaps-owned-and-retains-fail',()=>{const t=reapFixture();assert.equal(t.run('reap(spec)'),true);assert.equal(t.state.live.size,0);assert.equal(t.state.toolSafe,true);assert.equal(t.state.report.status,'FAIL');assert.equal(t.state.report.evidenceIncomplete,true);assert.deepEqual(t.calls.docker.filter(x=>['stop','rm'].includes(x[0])).map(x=>x[0]),['stop','rm']);t.state.report.status='PASS';t.run('enforceFinalStatus()');assert.equal(t.state.report.status,'FAIL');});
 check('ADG15-013-reap-refusal-not-repeated-or-db-stopped',()=>{const t=reapFixture();t.v.Config.Labels['nestakada.scope']='foreign';assert.throws(()=>t.run('reap(spec)'),/ADMIT_TOOL_OWNERSHIP/);assert.equal(t.spec.reapRefused,true);const calls=t.calls.docker.length;t.run(t.outer);assert.throws(()=>t.run('stopDatabase()'),/ADMIT_PRIOR_REAP_REFUSAL_OWNER_REQUIRED/);assert.equal(t.calls.docker.length,calls);assert.equal(t.calls.resourceChecks,0);assert.equal(t.calls.ownershipInspects,1);assert.equal(t.state.live.size,1);assert.equal(t.state.toolSafe,false);assert.equal(t.state.report.status,'FAIL');});
 status='PASS';
}catch(error){errorCode=/^ADMIT_[A-Z0-9_]+$/.test(error?.message||'')?error.message:'ADMISSION_GUARD_ASSERTION_FAILED';}
console.log(JSON.stringify({status,scope:'actual-host-functions-VM-fakeDocker-not-runtime-or-SQL',sourceSha256,
 cases,count:cases.length,errorCode,dockerInvoked:false,databaseConnected:false,privateFilesRead:false,filesWritten:false}));
if(status!=='PASS')process.exitCode=1;
