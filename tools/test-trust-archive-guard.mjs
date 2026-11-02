// WP15-001 negative only. Review this source before invoking it explicitly.
// Never seeds, renames, drops or resets a database; retains the existing corpus.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const task=path.join(repo,'work/dev15-20261102');
const privateDir=path.join(task,'private');
const manifestFile=path.join(task,'runtime/manifest.json');
const envFile=path.join(task,'runtime/compose.env');
const composeFile=path.join(repo,'environment/trust/compose.yaml');
const helperFile=path.join(repo,'tools/trust_archive_unit.py');
const output=path.join(repo,'work/dev15-write-20261102/archive-guard-report.json');
const project='nestakada-trust-test',db=project+'-db';
const unit='test_estakada_trust',archive='test_estakada_trust_cal_7e145c49';
const appName='dev15_archive_guard';
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const fail=code=>{throw Error(code);};
const ensure=(condition,code)=>{if(!condition)fail(code);};
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function checked(file){
 const full=path.resolve(file);ensure(full.startsWith(repo+path.sep),'PATH_SCOPE');
 for(let current=full;current!==repo;current=path.dirname(current)){
  if(fs.existsSync(current))ensure(!fs.lstatSync(current).isSymbolicLink(),'LINK_REJECTED');
 }
 return full;
}
function read(file){checked(file);ensure(fs.lstatSync(file).isFile(),'REGULAR_FILE_REQUIRED');return fs.readFileSync(file);}
function privateEvidence(label,result){
 checked(privateDir);ensure(fs.lstatSync(privateDir).isDirectory(),'PRIVATE_DIRECTORY_REQUIRED');
 fs.writeFileSync(path.join(privateDir,'archive-guard-'+label+'-'+crypto.randomUUID()+'.txt'),
  String(result.stdout||'')+'\n'+String(result.stderr||''),{flag:'wx',mode:0o600});
}
function docker(args,{input,timeout=20000,allowFailure=false}={}){
 const result=spawnSync('docker.exe',args,{input,encoding:'utf8',timeout,maxBuffer:1024*1024,windowsHide:true});
 if(result.error||result.status!==0){privateEvidence('command',result);if(!allowFailure)fail('OWNED_DOCKER_COMMAND_FAILED');}
 return result;
}
const compose=(args,options)=>docker(['compose','--env-file',envFile,'--project-name',project,'--file',composeFile,...args],options);
function owned({dbOnly=true}={}){
 const ids=docker(['ps','-aq','--filter','label=com.docker.compose.project='+project]).stdout.trim().split(/\r?\n/).filter(Boolean);
 for(const id of ids){
  const item=JSON.parse(docker(['inspect',id]).stdout)[0];
  ensure(item.Config.Labels?.['nestakada.scope']==='trust-test'&&item.Config.Labels?.['com.docker.compose.project']===project,'CONTAINER_OWNERSHIP');
  if(dbOnly)ensure(item.Config.Labels?.['com.docker.compose.service']==='db','ONLY_DB_MAY_EXIST');
 }
 for(const [kind,names] of [['network',['client','api','db']],['volume',['dbdata']]]){
  const existing=docker([kind,'ls','--format','{{.Name}}']).stdout.trim().split(/\r?\n/);
  for(const suffix of names){
   const name=project+'-'+suffix;
   if(existing.includes(name))ensure(JSON.parse(docker([kind,'inspect',name]).stdout)[0].Labels?.['nestakada.scope']==='trust-test','RESOURCE_OWNERSHIP');
  }
 }
 return ids;
}
function inspectDb(expectedImage){
 const ids=owned();ensure(ids.length===1,'ONE_OWNED_DB_REQUIRED');
 const item=JSON.parse(docker(['inspect',db]).stdout)[0];
 ensure(item.State.Running&&item.Image===expectedImage,'DB_IMAGE_OR_STATE');
 const limits=item.HostConfig;
 ensure(limits.Memory===536870912&&limits.MemorySwap===536870912&&limits.NanoCpus===500000000&&limits.PidsLimit===128,'DB_RESOURCE_CAPS');
 ensure(limits.ReadonlyRootfs&&!Object.keys(item.NetworkSettings.Ports||{}).some(key=>item.NetworkSettings.Ports[key]),'DB_NO_HOST_PORTS');
 return item.Id;
}
function query(database,sql){
 ensure(database==='estakada_trust'||database===unit,'QUERY_DATABASE_SCOPE');
 const raw=docker(['exec','--user','999',db,'psql','-X','-w','-U','postgres','-q','-A','-t','-v','ON_ERROR_STOP=1','-d',database,'-c',sql]).stdout.trim();
 return JSON.parse(raw);
}
function catalog(){return query('estakada_trust',`SELECT json_build_object(
 'unit',(SELECT json_build_object('oid',oid,'name',datname,'allowConnections',datallowconn) FROM pg_database WHERE datname='${unit}'),
 'archiveExists',EXISTS(SELECT 1 FROM pg_database WHERE datname='${archive}'))`);}
function state(){return query(unit,`SELECT json_build_object(
 'incarnation',incarnation::text,'generation',generation::text,'epoch',writer_epoch::text,
 'digest',digest,'logicalBytes',logical_bytes,'reservedBytes',reserved_bytes,
 'operations',(SELECT count(*) FROM trust.journal_operation),
 'policies',(SELECT count(*) FROM trust.journal_routepolicy),
 'tombstones',(SELECT count(*) FROM trust.journal_requesttombstone)) FROM trust.journal_head WHERE id=1`);}
function holderPids(){return query('estakada_trust',`SELECT coalesce(json_agg(pid),'[]'::json) FROM pg_stat_activity
 WHERE application_name='${appName}' AND datname='${unit}' AND usename='postgres'
 AND backend_type='client backend' AND query='SELECT pg_sleep(40)'`);}
function cancelHolder(pid){
 ensure(Number.isSafeInteger(pid)&&pid>0,'OWNED_PID_REQUIRED');
 return query('estakada_trust',`SELECT coalesce(json_agg(pg_cancel_backend(pid)),'[]'::json) FROM pg_stat_activity
 WHERE pid=${pid} AND application_name='${appName}' AND datname='${unit}' AND usename='postgres'
 AND backend_type='client backend' AND query='SELECT pg_sleep(40)'`);
}
let started=false,holder=null,holderDone=null,holderPid=null,holderOutput='',holderError='',holderCode=null;
let reportFd=null,holderCancellationConfirmed=false,stopConfirmed=false;
let status='FAIL',errorCode='ARCHIVE_GUARD_FAILED',beforeCatalog,beforeState,afterCatalog,afterState,dbId;
try{
 ensure(process.argv.length===2,'NO_ARGUMENTS_ALLOWED');
 for(const name of Object.keys(process.env))ensure(!name.startsWith('TRUST_'),'INHERITED_TRUST_OVERRIDE');
 checked(output);ensure(!fs.existsSync(output),'REPORT_ALREADY_EXISTS');
 reportFd=fs.openSync(output,'wx',0o600);
 const m=JSON.parse(read(manifestFile));
 ensure(m.project===project&&m.authorizedBy==='D-374'&&m.active===false&&m.initialized===true&&m.calibrationAttempted===true,'LEGACY_MANIFEST_SCOPE');
 ensure(path.resolve(m.privateDirectory)===privateDir&&m.sourceFiles.length===17,'LEGACY_SOURCE_SCOPE');
 ensure(/^[0-9a-f-]{36}$/.test(m.runId)&&path.resolve(m.sourceDirectory)===path.join(task,'runtime/sources',m.runId)
  &&m.sourceSha256==='4c7b0ad9601308725e2f756c53fa6c456634bbfc66edecd95bec005f05bb52d9','LEGACY_FROZEN_SOURCE_SCOPE');
 ensure(m.images.postgres==='sha256:de3d5ee43e308309e10730caead7dd880539d53f0275d977cd2f8c3f62b6eef7'
  &&m.images['python-runtime']==='sha256:09433387bce7dd726eb2f76918287c04c1fbd340eed1db2aaa3397fbd0474951'
  &&m.images['local-ingress']==='sha256:a3b293bbab17bfd78d82d2392240d3d351501fba538ab82de1595b1d28d0d646','PINNED_IMAGES_REQUIRED');
 for(const row of m.sourceFiles)ensure(sha(read(path.join(m.sourceDirectory,row.path)))===row.sha256,'LEGACY_SOURCE_DRIFT');
 let env=read(envFile).toString('utf8');const values={};
 for(const line of env.split(/\r?\n/).filter(Boolean)){
  const match=/^([A-Z_]+)='([^'\r\n]*)'$/.exec(line);ensure(match&&!Object.hasOwn(values,match[1]),'ENV_CLOSED_FORMAT');values[match[1]]=match[2];
 }
 const expected={TRUST_SOURCE:m.sourceDirectory,TRUST_PRIVATE:privateDir,TRUST_PYTHON_IMAGE:m.images['python-runtime'],TRUST_POSTGRES_IMAGE:m.images.postgres,
  TRUST_NGINX_IMAGE:m.images['local-ingress'],TRUST_DB_START:path.join(repo,'environment/foundation/db-start.sh'),TRUST_DB_INIT:path.join(repo,'tools/trust_db_init.py'),
  TRUST_NGINX_CONFIG:path.join(repo,'environment/trust/nginx.conf'),TRUST_HBA_CONFIG:path.join(repo,'environment/trust/pg_hba.conf')};
 ensure(Object.keys(values).every(key=>Object.hasOwn(expected,key)||['TRUST_RUNTIME_ID','TRUST_WRITE_MODE'].includes(key)),'ENV_KEYS_CLOSED');
 for(const [key,value] of Object.entries(expected))ensure(values[key]?.replaceAll('\\','/')===value.replaceAll('\\','/'),'ENV_PATH_OR_IMAGE_MISMATCH');
 ensure(owned().length===0,'STOPPED_PROJECT_REQUIRED');
 if(!Object.hasOwn(values,'TRUST_RUNTIME_ID'))env+="\nTRUST_RUNTIME_ID='"+m.runId+"'\n";
 else ensure(values.TRUST_RUNTIME_ID===(m.runtimeId||m.runId),'ENV_RUNTIME_SCOPE');
 if(!Object.hasOwn(values,'TRUST_WRITE_MODE'))env+="TRUST_WRITE_MODE='disabled'\n";
 else ensure(values.TRUST_WRITE_MODE==='disabled','WRITE_MODE_MUST_BE_DISABLED');
 if(env!==read(envFile).toString('utf8'))fs.appendFileSync(checked(envFile),env.slice(read(envFile).length));
 compose(['config','--quiet']);
 started=true;compose(['up','-d','--no-build','--pull','never','db']);dbId=inspectDb(m.images.postgres);
 let ready=false;
 for(let attempt=0;attempt<40;attempt++){
  const check=docker(['exec',db,'pg_isready','-h','127.0.0.1','-d','estakada_trust'],{timeout:3000,allowFailure:true});
  if(check.status===0&&!check.error){ready=true;break;}await sleep(250);
 }
 ensure(ready,'DB_NOT_READY');
 beforeCatalog=catalog();beforeState=state();
 ensure(beforeCatalog.unit?.allowConnections===true&&beforeCatalog.archiveExists===false,'ORIGINAL_DATABASE_GUARD');
 ensure(beforeState.incarnation===m.incarnation&&beforeState.generation==='121'&&beforeState.epoch==='1'&&beforeState.logicalBytes===66897420&&beforeState.reservedBytes===0
  &&beforeState.operations===60&&beforeState.policies===15360&&beforeState.tombstones===0,'ORIGINAL_CORPUS_GUARD');
 ensure(holderPids().length===0,'HOLDER_NAME_ALREADY_USED');
 holder=spawn('docker.exe',['exec','--user','999','--env','PGAPPNAME='+appName,db,'psql','-X','-w','-U','postgres','-d',unit,'-c','SELECT pg_sleep(40)'],{windowsHide:true,stdio:['ignore','pipe','pipe']});
 holderDone=new Promise(resolve=>{
  holder.once('error',()=>{holderCode='SPAWN_ERROR';resolve();});
  holder.once('close',code=>{holderCode=code;resolve();});
 });
 holder.stdout.on('data',bytes=>{holderOutput+=bytes.toString();});holder.stderr.on('data',bytes=>{holderError+=bytes.toString();});
 for(let attempt=0;attempt<30;attempt++){
  const pids=holderPids();ensure(pids.length<=1,'HOLDER_PID_NOT_UNIQUE');
  if(pids.length===1){holderPid=pids[0];break;}await sleep(100);
 }
 ensure(holderPid!==null&&holderCode===null,'HOLDER_NOT_ACTIVE');
 const launcher="import json,sys\nv=json.load(sys.stdin);ns={'__name__':'__main__','ACTION':v['action'],'REFERENCE':v['reference']};exec(compile(v['source'],'archive-unit','exec'),ns)";
 const result=compose(['--profile','tools','run','--rm','--no-deps','-T','init','python','-B','-c',launcher],{
  input:JSON.stringify({source:read(helperFile).toString('utf8'),action:'archive',reference:{incarnation:m.incarnation,calibrationStatus:'PASS',generation:'121'}}),timeout:30000,allowFailure:true});
 privateEvidence('expected-refusal',result);
 ensure(!result.error&&result.status===1,'EXPECTED_EXIT_ONE');
 let refusal;try{refusal=JSON.parse(result.stdout.trim());}catch{fail('EXPECTED_CLOSED_JSON_REFUSAL');}
 ensure(refusal.status==='FAIL'&&refusal.errorCode==='ARCHIVE_HAS_ACTIVE_SESSION'&&refusal.dataPreserved===true,'EXPECTED_ACTIVE_SESSION_REFUSAL');
 ensure(holderPids().length===1,'HOLDER_EXPIRED_BEFORE_WITNESS');
 afterCatalog=catalog();afterState=state();
 ensure(JSON.stringify(beforeCatalog)===JSON.stringify(afterCatalog)&&JSON.stringify(beforeState)===JSON.stringify(afterState),'CORPUS_CHANGED');
 status='PASS';errorCode='ARCHIVE_HAS_ACTIVE_SESSION';
}catch(error){
 const code=error?.message;errorCode=typeof code==='string'&&/^[A-Z][A-Z0-9_]{1,79}$/.test(code)?code:'ARCHIVE_GUARD_FAILED';
}finally{
 try{
  if(holder){
   if(holderPid===null){const pids=holderPids();if(pids.length===1)holderPid=pids[0];}
   if(holderPid!==null){const cancelled=cancelHolder(holderPid);holderCancellationConfirmed=cancelled.length===1&&cancelled[0]===true;}
   await Promise.race([holderDone,sleep(5000).then(()=>fail('HOLDER_REAP_TIMEOUT'))]);
   privateEvidence('holder',{stdout:holderOutput,stderr:holderError});
   ensure(holderCancellationConfirmed,'HOLDER_CANCELLATION_NOT_CONFIRMED');
  }
 }catch{status='FAIL';errorCode='OWNED_HOLDER_CLEANUP_FAILED';}
 try{if(started){owned({dbOnly:false});compose(['down','--timeout','5']);ensure(owned({dbOnly:false}).length===0,'DB_STOP_NOT_CONFIRMED');stopConfirmed=true;}}
 catch{status='FAIL';errorCode='OWNED_DB_STOP_FAILED';}
 const report={scope:'DEV15-WP001-NEGATIVE',status,errorCode,expectedRefusal:status==='PASS',
  originalDatabaseRetained:status==='PASS',archiveCreated:afterCatalog?.archiveExists??null,
  sameDatabaseOid:beforeCatalog&&afterCatalog?beforeCatalog.unit.oid===afterCatalog.unit.oid:null,
  allowConnections:afterCatalog?.unit?.allowConnections??null,generation:afterState?.generation??null,
  operations:afterState?.operations??null,policies:afterState?.policies??null,tombstones:afterState?.tombstones??null,
  sourceSha256:sha(read(fileURLToPath(import.meta.url))),helperSha256:sha(read(helperFile)),
  holderCancelledOnlyByScopedPid:holderCancellationConfirmed,dbOnly:true,stopRetained:stopConfirmed,
  dropPerformed:false,renamePerformed:status==='PASS'?false:null};
 if(reportFd!==null){fs.writeSync(reportFd,JSON.stringify(report,null,2)+'\n');fs.fsyncSync(reportFd);fs.closeSync(reportFd);}
 process.stdout.write(JSON.stringify({status,errorCode,report:reportFd!==null?'work/dev15-write-20261102/archive-guard-report.json':null})+'\n');
 if(status!=='PASS')process.exitCode=1;
}
