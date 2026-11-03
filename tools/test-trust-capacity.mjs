// D-380: one retained UNIT corpus. No MAIN admission, reset, image pull or ports.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const project='nestakada-trust-test', helper=project+'-capacity';
const task=path.join(root,'work/dev15-20261102');
const runtime=path.join(task,'runtime'), priv=path.join(task,'private');
const out=path.join(root,'work/dev15-capacity-20261102');
const env=path.join(runtime,'compose.env'), base=path.join(root,'environment/trust/compose.yaml');
const resuming=process.argv.length===3&&process.argv[2]==='ResumePreHelper';
const overrideFile=path.join(out,resuming?'resume-runner.compose.json':'runner.compose.json');
const attemptFile=path.join(runtime,'capacity-attempt.json');
const resumeFile=path.join(runtime,'capacity-resume-001.json');
const outputFile=path.join(out,resuming?'capacity-resume-report.json':'capacity-report.json');
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const ensure=(value,code)=>{if(!value)throw Error(code);};
const stable=value=>JSON.stringify(value,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)
  ?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a<b?-1:a>b?1:0)):x);

function read(file){
  const resolved=path.resolve(file);
  ensure(resolved.startsWith(root+path.sep),'PATH_SCOPE');
  for(let p=resolved;p!==root;p=path.dirname(p))ensure(!fs.lstatSync(p).isSymbolicLink(),'LINK_REJECTED');
  ensure(fs.lstatSync(resolved).isFile(),'REGULAR_INPUT_REQUIRED');
  return fs.readFileSync(resolved);
}
function json(file){return JSON.parse(read(file));}
function saveNew(file,value){
  ensure(path.resolve(file).startsWith(root+path.sep),'OUTPUT_SCOPE');
  fs.writeFileSync(file,JSON.stringify(value,null,2)+'\n',{flag:'wx',mode:0o600});
}
function command(program,args,{input,timeout=90000,optional=false}={}){
  const result=spawnSync(program,args,{input,encoding:'utf8',timeout,maxBuffer:4*1024*1024,windowsHide:true});
  if(result.error||result.status!==0){
    if(!optional){
      saveNew(path.join(priv,'capacity-failure-'+crypto.randomUUID()+'.json'),
        {stdout:String(result.stdout||''),stderr:String(result.stderr||'')});
      throw Error('CAPACITY_COMMAND_FAILED');
    }
  }
  return result;
}
const docker=(args,options)=>command('docker.exe',args,options);
const compose=(args,options)=>docker(['compose','--env-file',env,'--project-name',project,'--file',base,...args],options);
const local=(action,options)=>command(process.execPath,[path.join(root,'tools/local_trust.mjs'),action],options);
function inspect(name){
  const item=JSON.parse(docker(['inspect',name]).stdout)[0];
  ensure(item.Config.Labels?.['nestakada.scope']==='trust-test'
    &&item.Config.Labels?.['com.docker.compose.project']===project,'OWNED_CONTAINER_REQUIRED');
  return item;
}
function removeOwnedHelper(identity){
  const present=docker(['ps','-aq','--filter','id='+identity.id]).stdout.trim();
  if(!present)return false;
  let item=inspect(identity.id);
  ensure(item.Id===identity.id&&item.Name==='/'+helper&&item.Image===identity.image
    &&item.Config.Labels?.['com.docker.compose.service']==='migrate'
    &&item.HostConfig.ReadonlyRootfs&&item.Mounts.every(x=>x.Type==='tmpfs'||x.Type==='bind'&&!x.RW),
    'HELPER_CLEANUP_SCOPE');
  if(item.State.Running)docker(['stop','--timeout','5',item.Id]);
  item=inspect(identity.id);ensure(!item.State.Running,'HELPER_CLEANUP_STILL_RUNNING');
  saveNew(path.join(priv,'capacity-helper-final-'+item.Id.slice(0,12)+'.json'),
    {id:item.Id,image:item.Image,running:false,exitCode:item.State.ExitCode,oomKilled:item.State.OOMKilled,
      mountTypes:item.Mounts.map(x=>x.Type),noVolumeRemoval:true});
  docker(['rm',item.Id]);
  return true;
}
function verifySource(m){
  for(const [file,digest]of Object.entries(m.configHashes))ensure(sha(read(path.join(root,file)))===digest,'CONFIG_DRIFT');
  for(const row of m.sourceFiles)for(const directory of [path.join(root,'trust'),m.sourceDirectory])
    ensure(sha(read(path.join(directory,row.path)))===row.sha256,'SOURCE_DRIFT');
}
function mac(payload){
  const keys=json(path.join(priv,'credentials.json')).credentials.filter(x=>x.role==='recovery');
  ensure(keys.length===1&&/^[0-9a-f]{64}$/.test(keys[0].secret),'OPERATOR_KEY_REQUIRED');
  return crypto.createHmac('sha256',Buffer.from(keys[0].secret,'hex')).update(stable(payload)).digest('hex');
}
function verifyArchive(m){
  const old=json(path.join(runtime,'archive-unit.json'));
  ensure(old.signature===mac(old.payload)&&old.payload.incarnation===m.incarnation,'ARCHIVE_SIGNATURE');
  const entry="import json,sys\nv=json.load(sys.stdin);ns={'__name__':'__main__','ACTION':'verify','REFERENCE':v['reference']};exec(compile(v['source'],'archive-unit','exec'),ns)";
  const result=JSON.parse(compose(['--profile','tools','run','--rm','--no-deps','-T','init','python','-B','-c',entry],
    {input:JSON.stringify({source:read(path.join(root,'tools/trust_archive_unit.py')).toString(),reference:old.payload.report})}).stdout);
  ensure(stable(result)===stable(old.payload.report),'OLD_ARCHIVE_CHANGED');
  return result;
}
const mainProbe=`import json,django
django.setup()
from django.db import transaction
from journal.models import Head,Operation,RoutePolicy,RequestTombstone,RecoveryReceipt,AdmissionPolicy
from journal import recovery as R,state_v2 as V
with transaction.atomic():
 h=Head.objects.select_for_update().get(pk=1)
 assert (h.generation,h.writer_epoch,h.mode)==(9,2,'ACTIVE')
 counts=[m.objects.count() for m in (Operation,RoutePolicy,RequestTombstone,RecoveryReceipt,AdmissionPolicy)]
 assert counts==[4,3,1,2,0]
 old=R.state_digest(h)
 assert old=='64dd0a52dc0732cbc004d09b21d87f17a82d08a0cd885fa9d57f0656bf47f2c4'
 full=V.state_digest(h)
 assert full=='dfdf4021db5dba1b807699b548e4370488fb3582e9c87734206f8f91ee3c6066'
print(json.dumps({'status':'PASS','headGeneration':9,'writerEpoch':2,'counts':counts,'stateV1':old,'stateV2':full}))
`;
function mainState(){
  return JSON.parse(compose(['--profile','tools','run','--rm','--no-deps','-T','migrate','python','-B','-'],
    {input:mainProbe}).stdout);
}
function emptyUnit(expectedOid){
  const source=`import json,django
django.setup()
from django.apps import apps
from django.db import connection,transaction
from journal.profile import schema_fingerprint
with transaction.atomic():
 with connection.cursor() as c:
  c.execute('SET TRANSACTION READ ONLY')
  c.execute('SELECT current_database(),current_user,session_user,oid FROM pg_database WHERE datname=current_database()')
  identity=c.fetchone()
  assert identity[:3]==('test_estakada_trust','trust_migrator','trust_migrator')
  c.execute('SELECT app,name FROM django_migrations ORDER BY app,name')
  assert c.fetchall()==[('journal','0001_initial'),('journal','0002_local_test_recovery'),('journal','0003_admission_policy')]
 counts={name:apps.get_model('journal',name).objects.count() for name in ('Head','Credential','Operation','RoutePolicy','RequestTombstone','RecoveryReceipt','AdmissionPolicy')}
 assert all(value==0 for value in counts.values())
 schema=schema_fingerprint()
print(json.dumps({'status':'PASS','database':'test_estakada_trust','oid':identity[3],'counts':counts,'schemaFingerprint':schema}))
`;
  const proof=JSON.parse(compose(['--profile','tools','run','--rm','--no-deps','-T',
    '-e','TRUST_DB_NAME=test_estakada_trust','migrate','python','-B','-'],{input:source}).stdout);
  ensure(proof.status==='PASS'&&proof.oid===expectedOid,'UNIT_EMPTY_IDENTITY_REQUIRED');
  return proof;
}
function treeBytes(directory){
  let bytes=0;
  for(const entry of fs.readdirSync(directory,{withFileTypes:true})){
    const file=path.join(directory,entry.name);ensure(!fs.lstatSync(file).isSymbolicLink(),'LINK_REJECTED');
    bytes+=entry.isDirectory()?treeBytes(file):fs.statSync(file).size;
  }
  return bytes;
}
let report={status:'FAIL',errorCode:null,dataRetained:true,mainAdmission:false,
  tlsFullSnapshot:'NOT_RUN',htmlAdmission:false,workflowComplete:false,productionVerified:false};
let started=false,outputReserved=false,helperIdentity=null;
try{
  ensure(process.argv.length===2||resuming,'CLOSED_ARGUMENTS');
  for(const key of Object.keys(process.env))ensure(!key.startsWith('TRUST_'),'INHERITED_OVERRIDE');
  const gate=json(path.join(out,resuming?'resume-review-gate.json':'review-gate.json'));
  ensure(gate.status==='APPROVED'&&gate.authority==='D-380'&&gate.files.length>=4,'REVIEW_REQUIRED');
  for(const file of gate.files)ensure(sha(read(path.join(root,file.path)))===file.sha256,'REVIEW_DRIFT');
  let parent=null,failed=null;
  if(resuming){
    ensure(!fs.existsSync(resumeFile),'CAPACITY_RESUME_ALREADY_PRESERVED');
    parent=json(attemptFile);failed=json(path.join(out,'capacity-report.json'));
    ensure(parent.signature===mac(parent.payload)&&parent.payload.scope==='DEV15_CAPACITY_ATTEMPT'
      &&parent.payload.authority==='D-380'&&parent.payload.probeSha256===sha(read(path.join(root,'tools/trust_capacity_probe.py'))),'RESUME_PARENT_INVALID');
    ensure(failed.status==='FAIL'&&failed.errorCode==='CAPACITY_HOST_FAILED'&&!Object.hasOwn(failed,'helper')
      &&failed.corpusGuard==='PASS'&&failed.finalStatus?.actualRunningContainers===0
      &&failed.finalStatus?.state==='stopped'&&failed.sourceSha256===parent.payload.sourceSha256,'RESUME_NOT_PREHELPER_FAILURE');
  }else ensure(!fs.existsSync(attemptFile),'CAPACITY_ATTEMPT_ALREADY_PRESERVED');
  const old=json(path.join(runtime,'manifest.json'));
  ensure(!old.active&&old.writeMode==='disabled'&&old.unitArchive,'STOPPED_PRESERVED_STATE_REQUIRED');
  const unitName=resuming?parent.payload.unitEvidenceFile:'unit-result-'+old.runId+'.json';
  ensure(/^unit-result-[0-9a-f-]{36}\.json$/.test(unitName),'UNIT_EVIDENCE_SCOPE');
  const unit=json(path.join(runtime,unitName));
  ensure(unit.status==='PASS'&&unit.tests===131&&unit.sourceSha256===old.sourceSha256,'UNIT_131_REQUIRED');
  if(resuming)ensure(sha(read(path.join(runtime,unitName)))===parent.payload.unitSha256,'PARENT_UNIT_DRIFT');
  ensure(read(path.join(priv,'write-profile.json')).toString().trim()==='{}','ACTIVE_MAIN_PERMIT');
  const fd=fs.openSync(outputFile,'wx',0o600);fs.closeSync(fd);outputReserved=true;
  started=true;local('Start',{timeout:180000});
  const m=json(path.join(runtime,'manifest.json'));report.sourceSha256=m.sourceSha256;
  ensure(m.sourceSha256===unit.sourceSha256,'PRODUCT_SOURCE_CHANGED');verifySource(m);
  const previousApi=inspect(project+'-api');
  compose(['stop','--timeout','3','api','ingress']);
  const previousIngress=inspect(project+'-ingress');
  ensure(!inspect(project+'-api').State.Running&&!previousIngress.State.Running,'FRONT_STILL_RUNNING');
  ensure(previousIngress.Image===m.images['local-ingress']&&previousIngress.HostConfig.Memory===134217728
    &&previousIngress.HostConfig.MemorySwap===134217728&&previousIngress.HostConfig.NanoCpus===250000000
    &&previousIngress.HostConfig.PidsLimit===64&&previousIngress.HostConfig.ReadonlyRootfs,'INGRESS_CAPS');
  report.mainBefore=mainState();report.archiveBefore=verifyArchive(m);
  if(resuming)ensure(stable(report.mainBefore)===stable(failed.mainBefore)
    &&stable(report.archiveBefore)===stable(failed.archiveBefore),'RESUME_PRESERVATION_DRIFT');
  report.emptyUnitBefore=emptyUnit(report.archiveBefore.freshUnitOid);
  const newRuntime=crypto.randomUUID();
  // A created container keeps stdin open: one bounded line never waits for EOF.
  const launcher="import json,sys\nline=sys.stdin.buffer.readline(1048577)\nif not line.endswith(b'\\n') or len(line)>1048576: raise SystemExit('CAPACITY_FRAME_REJECTED')\nv=json.loads(line);ns={'__name__':'__main__','OPERATOR':v['operator']};exec(compile(v['source'],'trust-capacity-probe','exec'),ns)";
  saveNew(overrideFile,{services:{migrate:{container_name:helper,stdin_open:true,tty:false,
    command:['python','-B','-c',launcher],environment:{TRUST_DB_NAME:'test_estakada_trust',
      TRUST_TEST_EXECUTION:'1',TRUST_RUNTIME_ID:newRuntime}}}});
  docker(['compose','--env-file',env,'--project-name',project,'--file',base,'--file',overrideFile,
    '--profile','tools','create','--no-build','--pull','never','migrate']);
  const tool=inspect(helper),hc=tool.HostConfig;
  helperIdentity={id:tool.Id,image:m.images['python-runtime']};
  ensure(tool.Config.Labels?.['com.docker.compose.service']==='migrate'&&!tool.State.Running
    &&tool.Image===m.images['python-runtime']&&hc.ReadonlyRootfs&&hc.Memory===268435456
    &&hc.MemorySwap===268435456&&hc.NanoCpus===500000000&&hc.PidsLimit===64,'HELPER_CAPS');
  ensure(!Object.values(tool.NetworkSettings.Ports||{}).some(x=>x?.length)
    &&Object.keys(tool.NetworkSettings.Networks).length===1
    &&tool.NetworkSettings.Networks[project+'-db']
    &&tool.Mounts.every(x=>x.Type!=='bind'||!x.RW),'HELPER_BOUNDARY');
  const db=inspect(project+'-db');
  ensure(db.State.Running&&db.Image===m.images.postgres&&db.HostConfig.Memory===536870912
    &&db.HostConfig.MemorySwap===536870912&&db.HostConfig.ReadonlyRootfs
    &&db.HostConfig.NanoCpus===500000000&&db.HostConfig.PidsLimit===128
    &&!Object.values(db.NetworkSettings.Ports||{}).some(x=>x?.length),'DB_CAPS');
  for(const suffix of ['client','api','db'])
    ensure(JSON.parse(docker(['network','inspect',project+'-'+suffix]).stdout)[0].Internal,'EXTERNAL_NETWORK');
  const facts={previousApiId:previousApi.Id,previousApiStopped:true,newToolId:tool.Id,
    previousIngressId:previousIngress.Id,previousIngressStopped:true,
    newRuntimeId:newRuntime,helper:{memoryBytes:hc.Memory,nanoCpus:hc.NanoCpus,pids:hc.PidsLimit},
    database:{memoryBytes:db.HostConfig.Memory,nanoCpus:db.HostConfig.NanoCpus,pids:db.HostConfig.PidsLimit},
    ingress:{memoryBytes:previousIngress.HostConfig.Memory,nanoCpus:previousIngress.HostConfig.NanoCpus,pids:previousIngress.HostConfig.PidsLimit},
    readonlyBinds:true,internalDatabaseNetworkOnly:true};
  const factsSha=sha(Buffer.from(stable(facts)));
  const operator={runtimeId:newRuntime,configFingerprint:sha(Buffer.from(stable({config:m.configHashes,
    runner:sha(read(overrideFile))}))),deploymentEvidenceSha256:factsSha,
    exclusion:{previousRuntimeId:m.runtimeId,previousContainerId:previousApi.Id,
      newRuntimeId:newRuntime,newContainerId:tool.Id,evidenceSha256:factsSha}};
  saveNew(path.join(priv,'capacity-operator-'+newRuntime+'.json'),{facts,operator});
  const attempt={schemaVersion:1,scope:'DEV15_CAPACITY_ATTEMPT',authority:'D-380',
    runtimeId:newRuntime,containerId:tool.Id,sourceSha256:m.sourceSha256,
    unitEvidenceFile:unitName,
    unitSha256:sha(read(path.join(runtime,unitName))),
    probeSha256:sha(read(path.join(root,'tools/trust_capacity_probe.py'))),operatorSha256:sha(Buffer.from(stable(operator)))};
  if(resuming){
    const linked={...attempt,scope:'DEV15_CAPACITY_PREHELPER_RESUME',
      parentAttemptSha256:sha(read(attemptFile)),priorFailureReportSha256:sha(read(path.join(out,'capacity-report.json'))),
      emptyUnitProofSha256:sha(Buffer.from(stable(report.emptyUnitBefore)))};
    saveNew(resumeFile,{payload:linked,signature:mac(linked)});
    report.parentAttemptSha256=linked.parentAttemptSha256;
  }else saveNew(attemptFile,{payload:attempt,signature:mac(attempt)});
  // Test the actual destructive-test guard after the permanent receipt exists.
  const blocked=local('Tests',{optional:true});
  ensure(blocked.status!==0&&String(blocked.stderr).trim()==='TRUST_CAPACITY_CORPUS_PRESERVED','CORPUS_GUARD_FAILED');
  report.corpusGuard='PASS';
  const execution=docker(['start','--attach','--interactive',tool.Id],{optional:true,timeout:620000,
    input:JSON.stringify({source:read(path.join(root,'tools/trust_capacity_probe.py')).toString(),operator})+'\n'});
  saveNew(path.join(priv,'capacity-process-'+newRuntime+'.json'),{stdout:String(execution.stdout||''),stderr:String(execution.stderr||'')});
  const exited=inspect(helper);ensure(!exited.State.Running,'HELPER_DID_NOT_EXIT');
  ensure(!exited.State.OOMKilled,'HELPER_OOM');
  report.helper=JSON.parse(String(execution.stdout));
  ensure(!execution.error&&exited.State.ExitCode===0&&report.helper.status==='PASS','CAPACITY_PROBE_FAILED');
  report.mainAfter=mainState();report.archiveAfter=verifyArchive(m);
  ensure(stable(report.mainBefore)===stable(report.mainAfter)
    &&stable(report.archiveBefore)===stable(report.archiveAfter),'PRESERVATION_FAILED');
  verifySource(m);
  const dbFacts=docker(['exec','--user','999:999',project+'-db','cat',
    '/sys/fs/cgroup/memory.peak','/sys/fs/cgroup/memory.max','/sys/fs/cgroup/memory.events',
    '/sys/fs/cgroup/cpu.stat','/sys/fs/cgroup/pids.current','/sys/fs/cgroup/pids.max']).stdout.trim().split('\n');
  report.databaseCgroup={peak:Number(dbFacts[0]),max:Number(dbFacts[1]),
    pidsCurrent:Number(dbFacts.at(-2)),pidsMax:Number(dbFacts.at(-1)),
    stats:Object.fromEntries(dbFacts.slice(2,-2).map(row=>row.trim().split(/\s+/)).map(([key,value])=>[key,Number(value)])),
    peakPeriod:'one-db-container-lifetime',pidPeak:'NOT_MEASURED'};
  ensure(report.databaseCgroup.peak<=report.databaseCgroup.max
    &&!report.databaseCgroup.stats.oom&&!report.databaseCgroup.stats.oom_kill,'DB_OOM');
  const data=Number(docker(['exec','--user','999:999',project+'-db','du','-sk','/var/lib/postgresql']).stdout.trim().split(/\s+/)[0])*1024;
  let hostBytes=0;for(const e of fs.readdirSync(path.join(root,'work'),{withFileTypes:true}))
    if(e.isDirectory()&&e.name.startsWith('dev15'))hostBytes+=treeBytes(path.join(root,'work',e.name));
  report.observedBudget={databaseBytes:data,dev15HostBytes:hostBytes,logReservationBytes:8388608,
    observedBytes:data+hostBytes+8388608,limitBytes:2147483648,hardQuota:false};
  ensure(report.observedBudget.observedBytes<2147483648,'OBSERVED_BUDGET_EXCEEDED');
  report.status='PASS';
}catch(error){report.errorCode=/^[A-Z][A-Z0-9_]{1,90}$/.test(error?.message||'')?error.message:'CAPACITY_HOST_FAILED';}
finally{
  if(started){try{local('Stop');}catch{report.status='FAIL';report.errorCode='FINAL_STOP_FAILED';}}
  if(helperIdentity){try{report.helperContainerRemoved=removeOwnedHelper(helperIdentity);}
    catch{report.status='FAIL';report.errorCode='HELPER_CLEANUP_FAILED';}}
  if(started){try{
    report.finalStatus=JSON.parse(local('Status').stdout);
    ensure(report.finalStatus.actualRunningContainers===0&&!report.finalStatus.manifestActive
      &&read(path.join(priv,'write-profile.json')).toString().trim()==='{}','FINAL_NOT_CLOSED');
  }catch{report.status='FAIL';report.errorCode='FINAL_STATUS_FAILED';}}
  if(outputReserved)fs.writeFileSync(outputFile,JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({status:report.status,errorCode:report.errorCode,dataRetained:true,tlsFullSnapshot:'NOT_RUN'}));
  if(report.status!=='PASS')process.exitCode=1;
}
