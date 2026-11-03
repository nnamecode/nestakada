// D-380: two fixed continuations of the SAME retained UNIT, never a reset/retry.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const project='nestakada-trust-test', helper=project+'-capacity-continuation';
const runtime=path.join(root,'work/dev15-20261102/runtime'),priv=path.join(root,'work/dev15-20261102/private');
const out=path.join(root,'work/dev15-capacity-20261102');
const phase=process.argv[2],tag=phase==='A'?'a':'b';
const env=path.join(runtime,'compose.env'),base=path.join(root,'environment/trust/compose.yaml');
const receiptFile=path.join(runtime,'capacity-phase-'+tag+'.json');
const outputFile=path.join(out,'phase-'+tag+'-report.json');
const runnerFile=path.join(out,'phase-'+tag+'-runner.json');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const stable=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)
  ?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a<b?-1:a>b?1:0)):x);
const ensure=(v,c)=>{if(!v)throw Error(c);};
function read(file){
  const p=path.resolve(file);ensure(p.startsWith(root+path.sep),'PATH_SCOPE');
  for(let x=p;x!==root;x=path.dirname(x))ensure(!fs.lstatSync(x).isSymbolicLink(),'LINK_REJECTED');
  ensure(fs.lstatSync(p).isFile(),'REGULAR_INPUT_REQUIRED');return fs.readFileSync(p);
}
const json=f=>JSON.parse(read(f));
function saveNew(file,v){ensure(path.resolve(file).startsWith(root+path.sep),'OUTPUT_SCOPE');
  fs.writeFileSync(file,JSON.stringify(v,null,2)+'\n',{flag:'wx',mode:0o600});}
function command(program,args,{input,timeout=90000,optional=false}={}){
  const r=spawnSync(program,args,{input,encoding:'utf8',timeout,maxBuffer:4*1024*1024,windowsHide:true});
  if((r.error||r.status!==0)&&!optional){saveNew(path.join(priv,'capacity-cont-command-'+crypto.randomUUID()+'.json'),
    {stdout:r.stdout||'',stderr:r.stderr||''});throw Error('CONTINUATION_COMMAND_FAILED');}return r;
}
const docker=(a,o)=>command('docker.exe',a,o);
const compose=(a,o)=>docker(['compose','--env-file',env,'--project-name',project,'--file',base,...a],o);
const local=(a,o)=>command(process.execPath,[path.join(root,'tools/local_trust.mjs'),a],o);
function inspected(name){const v=JSON.parse(docker(['inspect',name]).stdout)[0];
  ensure(v.Config.Labels?.['nestakada.scope']==='trust-test'&&v.Config.Labels?.['com.docker.compose.project']===project,'OWNERSHIP');return v;}
function mac(payload){const keys=json(path.join(priv,'credentials.json')).credentials.filter(x=>x.role==='recovery');
  ensure(keys.length===1&&/^[0-9a-f]{64}$/.test(keys[0].secret),'OPERATOR_KEY');
  return crypto.createHmac('sha256',Buffer.from(keys[0].secret,'hex')).update(stable(payload)).digest('hex');}
function signed(file,scope){const e=json(file);ensure(e.payload.scope===scope&&e.payload.authority==='D-380'
  &&e.signature===mac(e.payload),'SIGNED_PARENT_INVALID');return e;}
function verifySource(m){for(const [f,h]of Object.entries(m.configHashes))ensure(sha(read(path.join(root,f)))===h,'CONFIG_DRIFT');
  for(const row of m.sourceFiles)for(const dir of [path.join(root,'trust'),m.sourceDirectory])ensure(sha(read(path.join(dir,row.path)))===row.sha256,'SOURCE_DRIFT');}
function archive(m){const e=json(path.join(runtime,'archive-unit.json'));ensure(e.signature===mac(e.payload)
  &&e.payload.incarnation===m.incarnation,'ARCHIVE_SIGNATURE');
  const entry="import json,sys\nv=json.load(sys.stdin);ns={'__name__':'__main__','ACTION':'verify','REFERENCE':v['reference']};exec(compile(v['source'],'archive-unit','exec'),ns)";
  const v=JSON.parse(compose(['--profile','tools','run','--rm','--no-deps','-T','init','python','-B','-c',entry],
    {input:JSON.stringify({source:read(path.join(root,'tools/trust_archive_unit.py')).toString(),reference:e.payload.report})}).stdout);
  ensure(stable(v)===stable(e.payload.report),'ARCHIVE_CHANGED');return v;
}
function mainState(){const source=`import json,django
django.setup()
from django.db import transaction
from journal.models import Head,Operation,RoutePolicy,RequestTombstone,RecoveryReceipt,AdmissionPolicy
from journal import recovery as R,state_v2 as V
with transaction.atomic():
 h=Head.objects.select_for_update().get(pk=1)
 assert (h.generation,h.writer_epoch,h.mode)==(9,2,'ACTIVE')
 counts=[m.objects.count() for m in (Operation,RoutePolicy,RequestTombstone,RecoveryReceipt,AdmissionPolicy)]
 assert counts==[4,3,1,2,0]
 old=R.state_digest(h);new=V.state_digest(h)
 assert old=='64dd0a52dc0732cbc004d09b21d87f17a82d08a0cd885fa9d57f0656bf47f2c4'
 assert new=='dfdf4021db5dba1b807699b548e4370488fb3582e9c87734206f8f91ee3c6066'
print(json.dumps({'status':'PASS','headGeneration':9,'writerEpoch':2,'counts':counts,'stateV1':old,'stateV2':new}))
`;
  return JSON.parse(compose(['--profile','tools','run','--rm','--no-deps','-T','migrate','python','-B','-'],{input:source}).stdout);
}
function unitAudit(){return JSON.parse(compose(['--profile','tools','run','--rm','--no-deps','-T',
  '-e','TRUST_DB_NAME=test_estakada_trust','-e','TRUST_TEST_EXECUTION=1','migrate','python','-B','-'],
  {input:read(path.join(root,'tools/trust_capacity_audit.py'))}).stdout);}
function authority(v){const keys=['head','counts','historicalReferences','stages','stateDigestVersion','stateDigest',
  'schemaFingerprint','policyId','policyDigest','policySourceFingerprint','actualSourceFingerprint',
  'sourceMatchesPolicy','credentialConfigSha256','policy','oid','database'];
  return Object.fromEntries(keys.map(k=>[k,v[k]]));}
function collectLogs(id){const r=docker(['logs',id],{optional:true});
  saveNew(path.join(priv,'capacity-phase-'+tag+'-container-logs.json'),{stdout:r.stdout||'',stderr:r.stderr||''});return r;}
function removeHelper(id,image){const list=docker(['ps','-aq','--filter','id='+id]).stdout.trim();if(!list)return;
  let v=inspected(id);ensure(v.Id===id&&v.Name==='/'+helper&&v.Image===image
    &&v.Config.Labels?.['com.docker.compose.service']==='migrate'&&v.HostConfig.ReadonlyRootfs
    &&v.Mounts.every(x=>x.Type==='tmpfs'||x.Type==='bind'&&!x.RW),'CLEANUP_SCOPE');
  if(v.State.Running)docker(['stop','--timeout','5',id]);v=inspected(id);ensure(!v.State.Running,'HELPER_STILL_RUNNING');
  // Preserve Docker logs even if timeout/transport fails before normal parsing.
  const r=docker(['logs',id],{optional:true});
  saveNew(path.join(priv,'capacity-phase-'+tag+'-final-state.json'),{id,state:v.State,stdout:r.stdout||'',stderr:r.stderr||''});
  docker(['rm',id]);
}
function treeBytes(dir){let total=0;for(const e of fs.readdirSync(dir,{withFileTypes:true})){
  const f=path.join(dir,e.name);ensure(!fs.lstatSync(f).isSymbolicLink(),'LINK_REJECTED');total+=e.isDirectory()?treeBytes(f):fs.statSync(f).size;}return total;}
let report={status:'FAIL',phase,dataRetained:true,mainAdmission:false,tlsFullSnapshot:'NOT_RUN',htmlAdmission:false,
  workflowComplete:false,productionVerified:false},started=false,outputReserved=false,toolId=null,toolImage=null;
try{
  ensure(process.argv.length===3&&['A','B'].includes(phase),'CLOSED_PHASE');
  for(const key of Object.keys(process.env))ensure(!key.startsWith('TRUST_'),'INHERITED_OVERRIDE');
  ensure(!fs.existsSync(receiptFile),'PHASE_ALREADY_PRESERVED');
  const gate=json(path.join(out,'continuation-review-gate.json'));ensure(gate.status==='APPROVED'
    &&gate.authority==='D-380'&&gate.files.length>=6,'REVIEW_REQUIRED');
  for(const f of gate.files)ensure(sha(read(path.join(root,f.path)))===f.sha256,'REVIEW_DRIFT');
  const original=signed(path.join(runtime,'capacity-attempt.json'),'DEV15_CAPACITY_ATTEMPT');
  const resume=signed(path.join(runtime,'capacity-resume-001.json'),'DEV15_CAPACITY_PREHELPER_RESUME');
  ensure(resume.payload.parentAttemptSha256===sha(read(path.join(runtime,'capacity-attempt.json'))),'PARENT_DRIFT');
  let expected;
  if(phase==='A'){
    ensure(!fs.existsSync(path.join(runtime,'capacity-phase-b.json')),'PHASE_ORDER');
    const failed=json(path.join(out,'capacity-resume-report.json'));
    ensure(failed.status==='FAIL'&&failed.finalStatus?.actualRunningContainers===0,'FAILED_CORPUS_REQUIRED');
    expected=json(path.join(out,'post-failure-unit-audit.json'));
  }else{
    const a=signed(path.join(runtime,'capacity-phase-a.json'),'DEV15_CAPACITY_CONTINUATION');
    const checkpoint=signed(path.join(runtime,'capacity-phase-a-checkpoint.json'),'DEV15_CAPACITY_CHECKPOINT');
    const prior=json(path.join(out,'phase-a-report.json'));
    ensure(a.payload.phase==='A'&&prior.status==='PASS'&&prior.helper?.status==='PASS'
      &&checkpoint.payload.phase==='A'&&checkpoint.payload.receiptSha256===sha(read(path.join(runtime,'capacity-phase-a.json')))
      &&checkpoint.payload.reportSha256===sha(read(path.join(out,'phase-a-report.json')))
      &&stable(checkpoint.payload.finalAudit)===stable(prior.helper.finalAudit),'PHASE_A_REQUIRED');
    expected=checkpoint.payload.finalAudit;
  }
  ensure(expected.status==='PASS'&&expected.sourceMatchesPolicy&&expected.oid===32563,'CHECKPOINT_REQUIRED');
  const old=json(path.join(runtime,'manifest.json'));ensure(!old.active&&old.writeMode==='disabled','STOPPED_REQUIRED');
  ensure(/^unit-result-[0-9a-f-]{36}\.json$/.test(original.payload.unitEvidenceFile),'UNIT_FILE_SCOPE');
  const unitFile=path.join(runtime,original.payload.unitEvidenceFile),unit=json(unitFile);
  ensure(unit.status==='PASS'&&unit.tests===131&&sha(read(unitFile))===original.payload.unitSha256
    &&unit.sourceSha256===expected.actualSourceFingerprint,'UNIT_GATE_DRIFT');
  ensure(read(path.join(priv,'write-profile.json')).toString().trim()==='{}','MAIN_PERMIT_NOT_EMPTY');
  fs.closeSync(fs.openSync(outputFile,'wx',0o600));outputReserved=true;
  started=true;local('Start',{timeout:180000});const m=json(path.join(runtime,'manifest.json'));
  report.sourceSha256=m.sourceSha256;ensure(m.sourceSha256===unit.sourceSha256,'PRODUCT_SOURCE_DRIFT');verifySource(m);
  const previousApi=inspected(project+'-api');compose(['stop','--timeout','3','api','ingress']);
  const ingress=inspected(project+'-ingress'),db=inspected(project+'-db');
  ensure(!inspected(project+'-api').State.Running&&!ingress.State.Running,'FRONT_STILL_RUNNING');
  report.mainBefore=mainState();report.archiveBefore=archive(m);report.beforeAudit=unitAudit();
  ensure(stable(authority(report.beforeAudit))===stable(authority(expected)),'CHECKPOINT_DRIFT');
  saveNew(path.join(out,'phase-'+tag+'-before-audit.json'),report.beforeAudit);
  const freshRuntime=crypto.randomUUID();
  const launcher="import json,sys\nline=sys.stdin.buffer.readline(1048577)\nif not line.endswith(b'\\n') or len(line)>1048576: raise SystemExit('CAPACITY_FRAME_REJECTED')\nv=json.loads(line);ns={'__name__':'__main__','INPUT':v['input']};exec(compile(v['source'],'trust-capacity-continue','exec'),ns)";
  saveNew(runnerFile,{services:{migrate:{container_name:helper,stdin_open:true,tty:false,
    command:['python','-B','-c',launcher],environment:{TRUST_DB_NAME:'test_estakada_trust',TRUST_TEST_EXECUTION:'1',TRUST_RUNTIME_ID:freshRuntime}}}});
  docker(['compose','--env-file',env,'--project-name',project,'--file',base,'--file',runnerFile,'--profile','tools','create','--no-build','--pull','never','migrate']);
  const tool=inspected(helper);toolId=tool.Id;toolImage=m.images['python-runtime'];const hc=tool.HostConfig;
  ensure(!tool.State.Running&&tool.Image===toolImage&&hc.ReadonlyRootfs&&hc.Memory===268435456
    &&hc.MemorySwap===268435456&&hc.NanoCpus===500000000&&hc.PidsLimit===64
    &&tool.Config.Labels?.['com.docker.compose.service']==='migrate'
    &&tool.Mounts.every(x=>x.Type!=='bind'||!x.RW)&&!Object.values(tool.NetworkSettings.Ports||{}).some(x=>x?.length)
    &&Object.keys(tool.NetworkSettings.Networks).length===1&&tool.NetworkSettings.Networks[project+'-db'],'HELPER_CAPS');
  for(const [v,image,limits]of [[db,m.images.postgres,[536870912,500000000,128]],[ingress,m.images['local-ingress'],[134217728,250000000,64]]])
    ensure(v.Image===image&&v.HostConfig.Memory===limits[0]&&v.HostConfig.MemorySwap===limits[0]
      &&v.HostConfig.NanoCpus===limits[1]&&v.HostConfig.PidsLimit===limits[2]&&v.HostConfig.ReadonlyRootfs,'SERVICE_CAPS');
  ensure(db.State.Running,'DB_NOT_RUNNING');
  for(const suffix of ['client','api','db'])ensure(JSON.parse(docker(['network','inspect',project+'-'+suffix]).stdout)[0].Internal,'EXTERNAL_NETWORK');
  const facts={previousApiId:previousApi.Id,previousApiStopped:true,previousIngressId:ingress.Id,previousIngressStopped:true,
    newToolId:toolId,newRuntimeId:freshRuntime,helper:{memoryBytes:hc.Memory,nanoCpus:hc.NanoCpus,pids:hc.PidsLimit},
    dbId:db.Id,readonlyBinds:true,internalDatabaseNetworkOnly:true};
  const factsSha=sha(Buffer.from(stable(facts)));
  const operator={runtimeId:freshRuntime,configFingerprint:sha(Buffer.from(stable({config:m.configHashes,runner:sha(read(runnerFile))}))),
    deploymentEvidenceSha256:factsSha,exclusion:{previousRuntimeId:m.runtimeId,previousContainerId:previousApi.Id,
      newRuntimeId:freshRuntime,newContainerId:toolId,evidenceSha256:factsSha}};
  const payload={schemaVersion:2,scope:'LOCAL_TRUST_BOUNDED_WRITER',policy:expected.policy,
    lease:{policyDigest:expected.policyDigest,runtimeId:freshRuntime,credentialConfigSha256:expected.credentialConfigSha256,
      deployment:{api:{memoryBytes:268435456,nanoCpus:500000000,pids:64},db:{memoryBytes:536870912,nanoCpus:500000000,pids:128},
        ingress:{memoryBytes:134217728,nanoCpus:250000000,pids:64},configFingerprint:operator.configFingerprint,evidence:factsSha},
      exclusion:operator.exclusion,recoveryActions:[],reconciliation:null}};
  const envelope={payload,signature:mac(payload)};
  const input={phase,corpusRuntimeId:resume.payload.runtimeId,operator,envelope,expected};
  saveNew(path.join(priv,'capacity-phase-'+tag+'-pre-send.json'),{input,facts});
  const receipt={schemaVersion:1,scope:'DEV15_CAPACITY_CONTINUATION',authority:'D-380',phase,sourceSha256:m.sourceSha256,
    parentAttemptSha256:sha(read(path.join(runtime,'capacity-attempt.json'))),parentResumeSha256:sha(read(path.join(runtime,'capacity-resume-001.json'))),
    checkpointSha256:sha(Buffer.from(stable(authority(expected)))),inputSha256:sha(Buffer.from(stable(input))),
    actualContainerId:toolId,runtimeId:freshRuntime,probeSha256:sha(read(path.join(root,'tools/trust_capacity_continue.py')))};
  saveNew(receiptFile,{payload:receipt,signature:mac(receipt)});
  const blocked=local('Tests',{optional:true});ensure(blocked.status!==0
    &&String(blocked.stderr).trim()==='TRUST_CAPACITY_CORPUS_PRESERVED','CORPUS_GUARD_FAILED');report.corpusGuard='PASS';
  const transport=docker(['start','--attach','--interactive',toolId],{optional:true,timeout:620000,
    input:JSON.stringify({source:read(path.join(root,'tools/trust_capacity_continue.py')).toString(),input})+'\n'});
  const logs=collectLogs(toolId); // compose-created containers may not stream via start -a.
  saveNew(path.join(priv,'capacity-phase-'+tag+'-transport.json'),{stdout:transport.stdout||'',stderr:transport.stderr||''});
  const state=inspected(toolId).State;ensure(!state.Running&&!state.OOMKilled,'HELPER_RUNNING_OR_OOM');
  ensure(!transport.error,'HELPER_TRANSPORT_TIMEOUT');
  report.helper=JSON.parse(logs.stdout);ensure(state.ExitCode===0&&report.helper.status==='PASS','CONTINUATION_PROBE_FAILED');
  report.afterAudit=unitAudit();ensure(stable(authority(report.afterAudit))===stable(authority(report.helper.finalAudit)),'FINAL_CHECKPOINT_DRIFT');
  report.mainAfter=mainState();report.archiveAfter=archive(m);
  ensure(stable(report.mainAfter)===stable(report.mainBefore)&&stable(report.archiveAfter)===stable(report.archiveBefore),'PRESERVATION_FAILED');
  verifySource(m);
  const cg=docker(['exec','--user','999:999',project+'-db','cat','/sys/fs/cgroup/memory.peak','/sys/fs/cgroup/memory.max',
    '/sys/fs/cgroup/memory.events','/sys/fs/cgroup/cpu.stat','/sys/fs/cgroup/pids.current','/sys/fs/cgroup/pids.max']).stdout.trim().split('\n');
  report.databaseCgroup={peak:Number(cg[0]),max:Number(cg[1]),pidsCurrent:Number(cg.at(-2)),pidsMax:Number(cg.at(-1)),
    stats:Object.fromEntries(cg.slice(2,-2).map(x=>x.split(/\s+/)).map(([k,v])=>[k,Number(v)])),period:'one-db-container-lifetime'};
  ensure(!report.databaseCgroup.stats.oom&&!report.databaseCgroup.stats.oom_kill,'DB_OOM');
  const data=Number(docker(['exec','--user','999:999',project+'-db','du','-sk','/var/lib/postgresql']).stdout.trim().split(/\s+/)[0])*1024;
  let host=0;for(const e of fs.readdirSync(path.join(root,'work'),{withFileTypes:true}))if(e.isDirectory()&&e.name.startsWith('dev15'))host+=treeBytes(path.join(root,'work',e.name));
  report.observedBudget={databaseBytes:data,hostBytes:host,logReservationBytes:8388608,observedBytes:data+host+8388608,limitBytes:2147483648,hardQuota:false};
  ensure(report.observedBudget.observedBytes<2147483648,'OBSERVED_BUDGET_EXCEEDED');report.status='PASS';
}catch(error){report.errorCode=/^[A-Z][A-Z0-9_]{1,90}$/.test(error?.message||'')?error.message:'CONTINUATION_HOST_FAILED';}
finally{
  if(started){try{local('Stop');}catch{report.status='FAIL';report.errorCode='FINAL_STOP_FAILED';}}
  if(toolId){try{removeHelper(toolId,toolImage);report.helperRemoved=true;}catch{report.status='FAIL';report.errorCode='HELPER_CLEANUP_FAILED';}}
  if(started){try{report.finalStatus=JSON.parse(local('Status').stdout);ensure(report.finalStatus.actualRunningContainers===0
    &&!report.finalStatus.manifestActive&&read(path.join(priv,'write-profile.json')).toString().trim()==='{}','FINAL_NOT_CLOSED');}
    catch{report.status='FAIL';report.errorCode='FINAL_STATUS_FAILED';}}
  if(outputReserved){
    fs.writeFileSync(outputFile,JSON.stringify(report,null,2)+'\n');
    if(report.status==='PASS'&&phase==='A'){
      try{const checkpoint={schemaVersion:1,scope:'DEV15_CAPACITY_CHECKPOINT',authority:'D-380',phase:'A',
        receiptSha256:sha(read(receiptFile)),reportSha256:sha(read(outputFile)),finalAudit:report.helper.finalAudit};
        saveNew(path.join(runtime,'capacity-phase-a-checkpoint.json'),{payload:checkpoint,signature:mac(checkpoint)});
      }catch{report.status='FAIL';report.errorCode='CHECKPOINT_SAVE_FAILED';fs.writeFileSync(outputFile,JSON.stringify(report,null,2)+'\n');}
    }
  }
  console.log(JSON.stringify({status:report.status,phase,errorCode:report.errorCode||null,dataRetained:true}));
  if(report.status!=='PASS')process.exitCode=1;
}
