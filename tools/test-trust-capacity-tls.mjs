// D-380 / RP15-011: temporary read-only UNIT API; one fixed TLS snapshot.
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),project='nestakada-trust-test';
const runtime=path.join(root,'work/dev15-20261102/runtime'),priv=path.join(root,'work/dev15-20261102/private');
const tlsRoot=path.join(root,'work/dev15-tls-20261102'),timingResume=process.argv.length===3&&process.argv[2]==='ResumeTiming';
const readResume=timingResume||(process.argv.length===3&&process.argv[2]==='ResumeReadResult');
const startupResume=readResume||(process.argv.length===3&&process.argv[2]==='ResumeStartup');
const resume=startupResume||(process.argv.length===3&&process.argv[2]==='Resume'),resumeId=timingResume?'resume-004':readResume?'resume-003':startupResume?'resume-002':'resume-001';
const out=resume?path.join(tlsRoot,resumeId):tlsRoot,cap=path.join(root,'work/dev15-capacity-20261102');
const env=path.join(runtime,'compose.env'),base=path.join(root,'environment/trust/compose.yaml'),override=path.join(out,'unit-api.compose.json');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex'),ensure=(v,c)=>{if(!v)throw Error(c);};
const stable=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a<b?-1:a>b?1:0)):x);
function read(file){const p=path.resolve(file);ensure(p.startsWith(root+path.sep),'PATH_SCOPE');for(let x=p;x!==root;x=path.dirname(x))ensure(!fs.lstatSync(x).isSymbolicLink(),'LINK_REJECTED');return fs.readFileSync(p);}
const json=f=>JSON.parse(read(f));
function saveNew(f,v){ensure(path.resolve(f).startsWith(root+path.sep),'OUTPUT_SCOPE');fs.writeFileSync(f,JSON.stringify(v,null,2)+'\n',{flag:'wx',mode:0o600});}
function command(program,args,{input,timeout=90000,optional=false}={}){const r=spawnSync(program,args,{input,encoding:'utf8',timeout,maxBuffer:4*1024*1024,windowsHide:true});
 if((r.error||r.status!==0)&&!optional){saveNew(path.join(priv,'tls-command-'+crypto.randomUUID()+'.json'),{stdout:r.stdout||'',stderr:r.stderr||''});throw Error('TLS_COMMAND_FAILED');}return r;}
const docker=(a,o)=>command('docker.exe',a,o),local=(a,o)=>command(process.execPath,[path.join(root,'tools/local_trust.mjs'),a],o);
const compose=(a,o,unit=false)=>docker(['compose','--env-file',env,'--project-name',project,'--file',base,...(unit?['--file',override]:[]),...a],o);
function inspect(kind){const v=JSON.parse(docker(['inspect',project+'-'+kind]).stdout)[0];ensure(v.Config.Labels?.['nestakada.scope']==='trust-test'&&v.Config.Labels?.['com.docker.compose.project']===project&&v.Config.Labels?.['com.docker.compose.service']===kind,'OWNERSHIP');return v;}
function mac(v){const keys=json(path.join(priv,'credentials.json')).credentials.filter(x=>x.role==='recovery');ensure(keys.length===1,'OPERATOR_KEY');return crypto.createHmac('sha256',Buffer.from(keys[0].secret,'hex')).update(stable(v)).digest('hex');}
function verifySource(m){for(const [f,h]of Object.entries(m.configHashes))ensure(sha(read(path.join(root,f)))===h,'CONFIG_DRIFT');for(const row of m.sourceFiles)for(const d of [path.join(root,'trust'),m.sourceDirectory])ensure(sha(read(path.join(d,row.path)))===row.sha256,'SOURCE_DRIFT');}
function authority(v){return Object.fromEntries(['head','counts','historicalReferences','stages','stateDigestVersion','stateDigest','schemaFingerprint','policyId','policyDigest','actualSourceFingerprint','credentialConfigSha256','policy','oid'].map(k=>[k,v[k]]));}
function unitAudit(){return JSON.parse(compose(['--profile','tools','run','--rm','--no-deps','-T','-e','TRUST_DB_NAME=test_estakada_trust','-e','TRUST_TEST_EXECUTION=1','migrate','python','-B','-'],{input:read(path.join(root,'tools/trust_capacity_audit.py'))}).stdout);}
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
 old=R.state_digest(h);new=V.state_digest(h)
 assert old=='64dd0a52dc0732cbc004d09b21d87f17a82d08a0cd885fa9d57f0656bf47f2c4'
 assert new=='dfdf4021db5dba1b807699b548e4370488fb3582e9c87734206f8f91ee3c6066'
print(json.dumps({'status':'PASS','counts':counts,'v1':old,'v2':new}))`;
function mainState(){return JSON.parse(compose(['--profile','tools','run','--rm','--no-deps','-T','migrate','python','-B','-'],{input:mainProbe}).stdout);}
function archive(m){const e=json(path.join(runtime,'archive-unit.json'));ensure(e.signature===mac(e.payload)&&e.payload.incarnation===m.incarnation,'ARCHIVE_SIGNATURE');
 const launcher="import json,sys\nv=json.loads(sys.stdin.buffer.readline(1048577));ns={'__name__':'__main__','ACTION':'verify','REFERENCE':v['reference']};exec(compile(v['source'],'archive-unit','exec'),ns)";
 const v=JSON.parse(compose(['--profile','tools','run','--rm','--no-deps','-T','init','python','-B','-c',launcher],{input:JSON.stringify({source:read(path.join(root,'tools/trust_archive_unit.py')).toString(),reference:e.payload.report})+'\n'}).stdout);ensure(stable(v)===stable(e.payload.report),'ARCHIVE_CHANGED');return v;}
function access(action,reference){const source=read(path.join(root,'tools/trust_capacity_read_access.py')).toString();
 const launcher="import json,sys\nv=json.loads(sys.stdin.buffer.readline(1048577));ns={'__name__':'__main__','ARG':v['arg']};exec(compile(v['source'],'unit-read-access','exec'),ns)";
 const r=compose(['--profile','tools','run','--rm','--no-deps','-T','init','python','-B','-c',launcher],{optional:true,input:JSON.stringify({source,arg:{action,reference}})+'\n',timeout:90000});
 saveNew(path.join(priv,'tls-access-'+action+'-'+crypto.randomUUID()+'.json'),{stdout:r.stdout||'',stderr:r.stderr||''});
 const v=JSON.parse(r.stdout);ensure(!r.error&&r.status===0&&v.status==='PASS','UNIT_ACCESS_'+action.toUpperCase()+'_FAILED');return v;}
function caps(m,dbName){for(const [kind,limits]of Object.entries({api:[268435456,500000000,64],db:[536870912,500000000,128],ingress:[134217728,250000000,64]})){
 const v=inspect(kind),h=v.HostConfig;ensure(v.State.Running&&h.ReadonlyRootfs&&h.Memory===limits[0]&&h.MemorySwap===limits[0]&&h.NanoCpus===limits[1]&&h.PidsLimit===limits[2]&&!Object.values(v.NetworkSettings.Ports||{}).some(x=>x?.length)&&v.Mounts.every(x=>x.Type!=='bind'||!x.RW),'ACTIVE_CAPS');
 ensure(v.Image===m.images[{api:'python-runtime',db:'postgres',ingress:'local-ingress'}[kind]],'IMAGE_DRIFT');}
 const api=inspect('api');ensure(api.Config.Env.includes('TRUST_DB_NAME='+dbName)&&api.Config.Env.includes('TRUST_WRITE_PROFILE=disabled')&&api.Config.Env.includes('TRUST_DB_USER=trust_runtime'),'API_PROFILE');
 for(const suffix of ['client','api','db'])ensure(JSON.parse(docker(['network','inspect',project+'-'+suffix]).stdout)[0].Internal,'EXTERNAL_NETWORK');}
function ready(label){const code="import socket,ssl;socket.create_connection(('127.0.0.1',8000),1).close();c=ssl.create_default_context(cafile='/run/secrets/ingress-ca');s=c.wrap_socket(socket.create_connection(('trust-ingress',8443),1),server_hostname='trust-ingress');s.close()",observations=[];
 for(let i=0;i<20;i++){const r=docker(['exec',project+'-api','python','-B','-c',code],{optional:true,timeout:4000});observations.push({status:r.status,errorCode:r.error?.code||null,signal:r.signal||null,stdout:r.stdout||'',stderr:r.stderr||''});if(!r.error&&r.status===0){saveNew(path.join(out,'readiness-'+label+'.json'),{status:'PASS',observations});return;}Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,200);}
 saveNew(path.join(out,'readiness-'+label+'.json'),{status:'FAIL',observations});report.failureResources=memory();report.failureServiceStates={};for(const kind of ['api','db','ingress']){const v=inspect(kind);report.failureServiceStates[kind]={id:v.Id,state:v.State};const r=docker(['logs','--tail','100',v.Id],{optional:true,timeout:5000});saveNew(path.join(priv,'tls-'+resumeId+'-'+label+'-'+kind+'-failure.json'),{status:r.status,errorCode:r.error?.code||null,stdout:r.stdout||'',stderr:r.stderr||''});}throw Error('TLS_SOCKET_NOT_READY');}
function memory(){const result={};for(const kind of ['api','db','ingress']){try{const owned=inspect(kind),r=docker(['exec',owned.Id,'cat','/sys/fs/cgroup/memory.peak','/sys/fs/cgroup/memory.max','/sys/fs/cgroup/memory.events'],{optional:true,timeout:5000});const v=(r.stdout||'').trim().split('\n');result[kind]={containerId:owned.Id,running:owned.State.Running,oomKilled:owned.State.OOMKilled,status:r.status,errorCode:r.error?.code||null,signal:r.signal||null,peak:Number(v[0]),max:Number(v[1]),events:Object.fromEntries(v.slice(2).filter(Boolean).map(x=>x.split(/\s+/)).map(([k,n])=>[k,Number(n)]))};}catch{result[kind]={observation:'FAILED'};}}return result;}
function counters(){const result={};for(const kind of ['api','db','ingress']){try{const owned=inspect(kind),sampleStartedMs=Date.now(),r=docker(['exec',owned.Id,'cat','/sys/fs/cgroup/cpu.stat','/sys/fs/cgroup/memory.events'],{optional:true,timeout:5000});const values=Object.fromEntries((r.stdout||'').trim().split('\n').filter(Boolean).map(x=>x.trim().split(/\s+/)).map(([k,n])=>[k,Number(n)]));result[kind]={containerId:owned.Id,sampleStartedMs,elapsedMs:Date.now()-sampleStartedMs,status:r.status,errorCode:r.error?.code||null,signal:r.signal||null,values,valid:!r.error&&r.status===0&&['usage_usec','nr_periods','nr_throttled','throttled_usec','oom','oom_kill'].every(k=>Number.isSafeInteger(values[k])&&values[k]>=0)};}catch{result[kind]={valid:false,errorCode:'COUNTER_OBSERVATION_FAILED'};}}return result;}
function collectProbeFiles(id,tag,stdoutPath,stderrPath){ensure(/^[a-f0-9]{64}$/.test(id),'PROBE_CONTAINER_ID');const result={};
 const reader="import os,stat,sys\nf=os.open(sys.argv[1],os.O_RDONLY|os.O_NOFOLLOW);s=os.fstat(f)\nassert stat.S_ISREG(s.st_mode) and s.st_size<=1048576\nwith os.fdopen(f,'rb') as stream:data=stream.read(1048577)\nassert len(data)<=1048576\nsys.stdout.buffer.write(data)";
 for(const [kind,source]of [['stdout',stdoutPath],['stderr',stderrPath]]){const destination=path.join(priv,tag+'.'+kind);try{ensure(inspect('api').Id===id,'PROBE_CONTAINER_CHANGED');const r=docker(['exec','--user','10001:10001',id,'python','-I','-B','-c',reader,source],{optional:true,timeout:15000});saveNew(path.join(priv,tag+'-'+kind+'-capture.json'),{status:r.status,errorCode:r.error?.code||null,signal:r.signal||null,stdout:r.stdout||'',stderr:r.stderr||''});fs.writeFileSync(destination,r.stdout||'',{flag:'wx',mode:0o600});const info=fs.lstatSync(destination);result[kind]={method:'bounded-exec-read-tmpfs',status:r.status,errorCode:r.error?.code||null,signal:r.signal||null,file:destination,bytes:info.size,valid:!r.error&&r.status===0&&info.isFile()&&!info.isSymbolicLink()&&info.size<=1048576};}catch{result[kind]={valid:false,errorCode:'PROBE_FILE_CAPTURE_FAILED',file:destination};}}return result;}
let report={status:'FAIL',mainAdmission:false,dataRetained:true,htmlAdmission:false,workflowComplete:false,production:false};
let started=false,reserved=false,grantStarted=false,accessReference=null,unitApiId=null;
try{
 ensure(process.argv.length===2||resume,'ARGUMENTS_REJECTED');for(const k of Object.keys(process.env))ensure(!k.startsWith('TRUST_'),'INHERITED_OVERRIDE');
 let parentReportSha256=null,parentIntentSha256=null;
 if(resume){const parentFile=path.join(timingResume?path.join(tlsRoot,'resume-003'):readResume?path.join(tlsRoot,'resume-002'):startupResume?path.join(tlsRoot,'resume-001'):tlsRoot,'tls-report.json'),intentFile=path.join(runtime,timingResume?'capacity-tls-resume-003.json':readResume?'capacity-tls-resume-002.json':startupResume?'capacity-tls-resume-001.json':'capacity-tls-intent.json'),parent=json(parentFile),original=json(intentFile);
  ensure(parent.status==='FAIL'&&parent.errorCode===(timingResume?'TLS_PROBE_FAILED':readResume?'TLS_PROBE_FILE_CAPTURE_FAILED':startupResume?'TLS_SOCKET_NOT_READY':'TLS_HOST_FAILED')&&parent.restoredAccess?.status==='PASS'&&parent.restoredAccess.restored===true&&parent.restoredAccess.effectiveBaselineEqual===true,'RESUME_PARENT_NOT_SAFE');
  if(timingResume)ensure(parent.probe?.status==='FAIL'&&parent.probe.errorCode==='SNAPSHOT_DEADLINE'&&parent.probeFiles?.stdout.valid&&parent.probeFiles.stderr.valid&&parent.probeExecution?.status===1,'RESUME_DEADLINE_EVIDENCE_REQUIRED');
  if(readResume)ensure(parent.startupMigrationDenied42501===true&&parent.probeExecution?.status===(timingResume?1:0)&&!parent.probeExecution.errorCode&&Object.values(parent.unitApiCgroup||{}).length===3&&Object.values(parent.unitApiCgroup).every(v=>v.status===0&&!v.oomKilled&&v.events.oom===0&&v.events.oom_kill===0),'RESUME_PARENT_EXECUTION_REQUIRED');
  ensure(parent.finalStatus?.actualRunningContainers===0&&parent.finalStatus.manifestActive===false&&parent.finalStatus.state==='stopped'&&parent.finalStatus.writeProfile==='disabled','RESUME_PARENT_NOT_STOPPED');
  ensure(original.signature===mac(original.payload)&&original.payload.scope===(startupResume?'DEV15_UNIT_READONLY_TLS_RESUME':'DEV15_UNIT_READONLY_TLS')&&original.payload.authority==='D-380'&&original.payload.sourceSha256===parent.sourceSha256,'RESUME_PARENT_INTENT');
  ensure(original.payload.checkpointSha256===sha(Buffer.from(stable(authority(parent.unitBefore))))&&original.payload.baselineAccessSha256===sha(Buffer.from(stable(parent.baselineAccess.reference))),'RESUME_PARENT_BINDING');
  ensure(!fs.existsSync(path.join(runtime,'capacity-tls-'+resumeId+'.json')),'RESUME_ALREADY_ATTEMPTED');
  parentReportSha256=sha(read(parentFile));parentIntentSha256=sha(read(intentFile));report.resume={id:resumeId,parentReportSha256,parentIntentSha256,parentErrorCode:parent.errorCode};}
 const gate=json(path.join(out,'review-gate.json'));ensure(gate.status==='APPROVED'&&gate.authority==='D-380'&&gate.files.length>=5,'REVIEW_REQUIRED');for(const f of gate.files)ensure(sha(read(path.join(root,f.path)))===f.sha256,'REVIEW_DRIFT');
 const b=json(path.join(cap,'phase-b-report.json'));ensure(b.status==='PASS'&&b.helper?.status==='PASS','CAPACITY_B_REQUIRED');
 const receipt=json(path.join(runtime,'capacity-phase-b.json'));ensure(receipt.signature===mac(receipt.payload)&&receipt.payload.phase==='B','CAPACITY_RECEIPT');
 ensure(!json(path.join(runtime,'manifest.json')).active&&read(path.join(priv,'write-profile.json')).toString().trim()==='{}','STOPPED_CLOSED_REQUIRED');
 fs.closeSync(fs.openSync(path.join(out,'tls-report.json'),'wx',0o600));reserved=true;started=true;local('Start',{timeout:180000});const m=json(path.join(runtime,'manifest.json'));
 report.sourceSha256=m.sourceSha256;ensure(m.sourceSha256===b.sourceSha256,'SOURCE_CHANGED');if(resume)ensure(m.sourceSha256===json(path.join(runtime,'capacity-tls-intent.json')).payload.sourceSha256,'RESUME_SOURCE_CHANGED');verifySource(m);compose(['stop','--timeout','3','api','ingress']);
 report.mainBefore=mainState();report.archiveBefore=archive(m);report.unitBefore=unitAudit();ensure(stable(authority(report.unitBefore))===stable(authority(b.helper.finalAudit)),'UNIT_CHECKPOINT_DRIFT');
 report.baselineAccess=access('verify',null);accessReference=report.baselineAccess.reference;
 const intent={scope:'DEV15_UNIT_READONLY_TLS',authority:'D-380',sourceSha256:m.sourceSha256,checkpointSha256:sha(Buffer.from(stable(authority(report.unitBefore)))),baselineAccessSha256:sha(Buffer.from(stable(accessReference)))};
 if(resume){const payload={...intent,scope:'DEV15_UNIT_READONLY_TLS_RESUME',resumeId,parentReportSha256,parentIntentSha256,unitStartupMigrationCheckSeparated:startupResume,hostSha256:sha(read(fileURLToPath(import.meta.url))),reviewGateSha256:sha(read(path.join(out,'review-gate.json')))};saveNew(path.join(runtime,'capacity-tls-'+resumeId+'.json'),{payload,signature:mac(payload)});}
 else saveNew(path.join(runtime,'capacity-tls-intent.json'),{payload:intent,signature:mac(intent)});
 grantStarted=true;report.grantedAccess=access('grant',accessReference);accessReference=report.grantedAccess.reference;
 saveNew(path.join(out,'access-grant.json'),report.grantedAccess);
 const apiOverride={environment:{TRUST_DB_NAME:'test_estakada_trust',TRUST_WRITE_PROFILE:'disabled',TRUST_RUNTIME_ID:crypto.randomUUID()}};
 if(startupResume){const startCode=`import json,django
django.setup()
from django.conf import settings
from django.db import connection,DatabaseError
from django.core.management.commands.runserver import Command
from journal import profile as P
assert settings.TRUST_WRITE_PROFILE=='disabled' and connection.settings_dict['NAME']=='test_estakada_trust' and connection.settings_dict['USER']=='trust_runtime'
with connection.cursor() as c:
 c.execute('SELECT current_database(),current_user,session_user,oid FROM pg_database WHERE datname=current_database()')
 assert c.fetchone()==('test_estakada_trust','trust_runtime','trust_runtime',32563)
assert P.source_fingerprint()==${JSON.stringify(m.sourceSha256)}
try:
 Command().check_migrations()
except DatabaseError as e:
 assert getattr(e.__cause__,'sqlstate',None)=='42501' and 'django_migrations' in str(e.__cause__)
 print('UNIT_READONLY_MIGRATION_DENIED_42501',flush=True)
else:raise RuntimeError('UNIT_MIGRATION_DENIAL_CONTROL_FAILED')
connection.close()
class UnitCommand(Command):
 def check_migrations(self):pass
UnitCommand().run_from_argv(['manage.py','runserver','0.0.0.0:8000','--noreload'])`;
  apiOverride.command=['python','-u','-B','-c',startCode];}
 saveNew(override,{services:{api:apiOverride}});
 compose(['up','-d','--no-build','--pull','never','--force-recreate','api','ingress'],{},true);caps(m,'test_estakada_trust');ready('unit');unitApiId=inspect('api').Id;
 if(startupResume){const r=docker(['logs','--tail','100',unitApiId],{optional:true,timeout:5000});saveNew(path.join(priv,'tls-'+resumeId+'-startup.json'),{status:r.status,errorCode:r.error?.code||null,stdout:r.stdout||'',stderr:r.stderr||''});ensure(!r.error&&r.status===0&&(r.stdout||'').includes('UNIT_READONLY_MIGRATION_DENIED_42501'),'UNIT_STARTUP_CONTROL_FAILED');report.startupMigrationDenied42501=true;}
 const tag=resume?'capacity-tls-'+resumeId+'-probe':'capacity-tls-initial-probe',stdoutPath='/tmp/'+tag+'.stdout',stderrPath='/tmp/'+tag+'.stderr';
 const launcher="import json,sys,os,resource\nflags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW\na=os.open("+JSON.stringify(stdoutPath)+",flags,0o600);b=os.open("+JSON.stringify(stderrPath)+",flags,0o600)\nos.dup2(a,1);os.dup2(b,2);os.close(a);os.close(b)\nresource.setrlimit(resource.RLIMIT_FSIZE,(1048576,1048576))\nv=json.loads(sys.stdin.buffer.readline(1048577));ns={'__name__':'__main__','ARG':v['arg']};exec(compile(v['source'],'capacity-tls-probe','exec'),ns)";
 if(timingResume){report.countersBefore=counters();saveNew(path.join(out,'counters-before.json'),report.countersBefore);}
 const execStarted=Date.now(),r=docker(['exec','-i','--user','10001:10001',unitApiId,'python','-u','-B','-c',launcher],{optional:true,timeout:45000,input:JSON.stringify({source:read(path.join(root,'tools/trust_capacity_tls_probe.py')).toString(),arg:{expectedAudit:b.helper.finalAudit,expectedSnapshotDigest:b.helper.snapshot.manifest.snapshotDigest}})+'\n'});
 report.probeExecution={status:r.status,errorCode:r.error?.code||null,signal:r.signal||null,elapsedMs:Date.now()-execStarted,transportStdoutBytes:Buffer.byteLength(r.stdout||''),transportStderrBytes:Buffer.byteLength(r.stderr||'')};
 if(timingResume){report.countersAfter=counters();saveNew(path.join(out,'counters-after.json'),report.countersAfter);report.cpuCountersValid=Object.entries(report.countersAfter).every(([k,v])=>{const before=report.countersBefore[k];return v.valid&&before.valid&&v.containerId===before.containerId&&v.sampleStartedMs>before.sampleStartedMs&&['usage_usec','nr_periods','nr_throttled','throttled_usec','oom','oom_kill'].every(key=>v.values[key]>=before.values[key]);});}
 report.unitApiCgroup=memory();report.probeFiles=collectProbeFiles(unitApiId,tag,stdoutPath,stderrPath);
 saveNew(path.join(priv,tag+'-transport.json'),{...report.probeExecution,stdout:r.stdout||'',stderr:r.stderr||''});saveNew(path.join(out,'probe-execution.json'),{execution:report.probeExecution,memory:report.unitApiCgroup,files:report.probeFiles,countersBefore:report.countersBefore||null,countersAfter:report.countersAfter||null});
 ensure(report.probeFiles.stdout.valid&&report.probeFiles.stderr.valid,'TLS_PROBE_FILE_CAPTURE_FAILED');const probeText=read(report.probeFiles.stdout.file).toString();ensure(probeText.trim().length>0,'TLS_PROBE_OUTPUT_EMPTY');
 try{report.probe=JSON.parse(probeText);}catch{throw Error('TLS_PROBE_OUTPUT_INVALID_JSON');}ensure(!r.error&&r.status===0&&report.probe.status==='PASS','TLS_PROBE_FAILED');
 if(timingResume)ensure(report.cpuCountersValid,'CPU_COUNTERS_INVALID');
 for(const kind of ['api','db','ingress']){const value=report.unitApiCgroup[kind];ensure(value.status===0&&Number.isFinite(value.peak)&&Number.isFinite(value.max)&&value.peak<=value.max,'TLS_MEMORY_OBSERVATION_FAILED');ensure(value.oomKilled!==true&&!value.events.oom&&!value.events.oom_kill,'OOM');}
 compose(['stop','--timeout','3','api','ingress']);
 report.restoredAccess=access('restore',accessReference);grantStarted=false;
 report.unitAfter=unitAudit();report.mainAfter=mainState();report.archiveAfter=archive(m);
 ensure(stable(authority(report.unitBefore))===stable(authority(report.unitAfter))&&stable(report.mainBefore)===stable(report.mainAfter)&&stable(report.archiveBefore)===stable(report.archiveAfter),'DATA_PRESERVATION_FAILED');
 compose(['up','-d','--no-build','--pull','never','--force-recreate','api','ingress']);caps(m,'estakada_trust');ready('main');ensure(inspect('api').Id!==unitApiId,'API_NOT_RECREATED');
 const check="import django;django.setup();from django.db import connection;from django.conf import settings;from journal import auth,services;assert connection.settings_dict['NAME']=='estakada_trust' and settings.TRUST_WRITE_PROFILE=='disabled';c=connection.cursor();c.execute('SELECT current_database(),current_user');assert c.fetchone()==('estakada_trust','trust_runtime');c.close();k=next(x for x in auth.configuration().values() if x['role']=='reader');a=auth.authenticate('Bearer '+k['id']+':'+k['secret'],'reader');h=services.read_head(a);assert h['generation']=='9' and h['writerEpoch']=='2';print('MAIN_API_IDENTITY_DISABLED_PASS')";
 ensure(docker(['exec',project+'-api','python','-B','-c',check]).stdout.trim()==='MAIN_API_IDENTITY_DISABLED_PASS','MAIN_API_IDENTITY');
 verifySource(m);report.mainApiRecreated=true;report.status='PASS';
}catch(error){report.errorCode=/^[A-Z][A-Z0-9_]{1,90}$/.test(error?.message||'')?error.message:'TLS_HOST_FAILED';}
finally{
 if(started){try{compose(['stop','--timeout','3','api','ingress']);}catch{report.status='FAIL';report.errorCode='FRONT_STOP_FAILED';}}
 if(grantStarted&&accessReference){try{report.restoredAccess=access('restore',accessReference);grantStarted=false;}catch{report.status='FAIL';report.errorCode='ACCESS_RESTORE_FAILED';}}
 if(timingResume&&started&&!grantStarted&&report.unitBefore&&!report.unitAfter){try{report.unitAfter=unitAudit();report.mainAfter=mainState();report.archiveAfter=archive(json(path.join(runtime,'manifest.json')));ensure(stable(authority(report.unitBefore))===stable(authority(report.unitAfter))&&stable(report.mainBefore)===stable(report.mainAfter)&&stable(report.archiveBefore)===stable(report.archiveAfter),'DATA_PRESERVATION_FAILED');verifySource(json(path.join(runtime,'manifest.json')));report.preservationAfterFailure=true;}catch{report.initialErrorCode=report.errorCode||null;report.status='FAIL';report.errorCode='FAILURE_PRESERVATION_CHECK_FAILED';}}
 if(started){try{local('Stop');report.finalStatus=JSON.parse(local('Status').stdout);ensure(report.finalStatus.actualRunningContainers===0&&!report.finalStatus.manifestActive,'FINAL_NOT_STOPPED');}catch{report.status='FAIL';report.errorCode='FINAL_STOP_FAILED';}}
 if(reserved)fs.writeFileSync(path.join(out,'tls-report.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({status:report.status,errorCode:report.errorCode||null,dataRetained:true}));if(report.status!=='PASS')process.exitCode=1;
}
