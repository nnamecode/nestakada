// D-400 / RF15-001-008. Exact UNIT recovery only; MAIN remains readonly.
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';import {fileURLToPath} from 'node:url';
const self=fileURLToPath(import.meta.url),root=path.resolve(path.dirname(self),'..'),project='nestakada-trust-test';
const work=path.join(root,'work/dev15-recovery-20261103'),runtime=path.join(root,'work/dev15-20261102/runtime'),priv=path.join(root,'work/dev15-20261102/private');
const env=path.join(runtime,'compose.env'),base=path.join(root,'environment/trust/compose.yaml'),metadata=path.join(root,'environment/trust/archive-tool.compose.yaml');
const pkg=path.join(root,'work/dev15-evidence-20261102/package'),validationFile=path.join(root,'work/dev15-evidence-20261102/validation-result.json');
const SOURCE='014efc288de0d32772fca15d63afbb0a4c23a9009ee6ef8bdc877cb1aa41c672',OLD='5fbcb9d9ea04ee58853b9b8d9fe2131fc6b0d1122f087239f3c66bfded768986';
const SCHEMA='4fb7464026b738b4bc9cfd1dd23657d5e0425c7b3f859e1d9a9ddb97495d4de7';
const RECEIPT='666ba3175edede3db99dcc1688829b68edf78081f2e11cbb22c35e0a0ec23f51',VALIDATOR='cbdb645bb6078b66ce3c858b7182046e8b19ba5ea990f89ddf6556d007908bb2';
const phase='Recovery',runId=crypto.randomUUID(),MAX=262144,sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const reportFile=path.join(work,String(phase).toLowerCase()+'-'+runId+'-report.json');
const ensure=(v,c)=>{if(!v)throw Error(c);},stable=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a<b?-1:a>b?1:0)):x);
const closed=(v,keys)=>ensure(v&&typeof v==='object'&&!Array.isArray(v)&&stable(Object.keys(v).sort())===stable([...keys].sort()),'ADMIT_CLOSED_SHAPE');
function inside(f){const p=path.resolve(root,f);ensure(p.startsWith(root+path.sep),'ADMIT_PATH');for(let q=p;q!==root;q=path.dirname(q))if(fs.existsSync(q))ensure(!fs.lstatSync(q).isSymbolicLink(),'ADMIT_REPARSE');return p;}
function read(f){const p=inside(f),s=fs.lstatSync(p);ensure(s.isFile()&&s.size<=4194304,'ADMIT_INPUT_SIZE');return fs.readFileSync(p);}
const json=f=>JSON.parse(read(f));
function bytes(f,b){ensure(Buffer.byteLength(b)<=MAX,'ADMIT_OUTPUT_SIZE');fs.writeFileSync(inside(f),b,{flag:'wx',mode:0o600});}
const save=(f,v)=>bytes(f,Buffer.from(stable(v)+'\n'));
function mac(v){const keys=json(path.join(priv,'credentials.json')).credentials.filter(x=>x.role==='recovery');ensure(keys.length===1&&/^[a-f0-9]{64}$/.test(keys[0].secret),'ADMIT_OPERATOR_KEY');return crypto.createHmac('sha256',Buffer.from(keys[0].secret,'hex')).update(stable(v)).digest('hex');}
function signed(f,scope){const e=json(f);closed(e,['payload','signature']);ensure(e.payload.scope===scope&&e.signature===mac(e.payload),'ADMIT_SIGNATURE');return e.payload;}
const execution=r=>({status:r.status,errorCode:r.error?.code||null,signal:r.signal||null,elapsedMilliseconds:r.elapsedMilliseconds,stdoutBytes:Buffer.byteLength(r.stdout||''),stderrBytes:Buffer.byteLength(r.stderr||'')});
function call(program,args,{input,timeout=90000,optional=false}={}){const start=performance.now(),r=spawnSync(program,args,{input,encoding:'utf8',timeout,maxBuffer:MAX,windowsHide:true});r.elapsedMilliseconds=performance.now()-start;if((r.error||r.status!==0)&&!optional){const id=crypto.randomUUID();save(path.join(priv,'admit-command-'+id+'.json'),execution(r));bytes(path.join(priv,'admit-command-'+id+'.stderr'),r.stderr||'');throw Error('ADMIT_COMMAND_FAILED');}return r;}
const docker=(args,options)=>call('docker.exe',['--context','desktop-linux',...args],options);
function compose(envFile,args,options){return docker(['compose','--env-file',envFile,'--project-name',project,'--file',base,'--file',metadata,...args],options);}
const inspect=id=>JSON.parse(docker(['inspect',id]).stdout)[0];
function fullIds(stdout){const ids=String(stdout).trim().split(/\r?\n/).filter(Boolean);ensure(ids.every(id=>/^[a-f0-9]{64}$/.test(id))&&new Set(ids).size===ids.length,'ADMIT_CONTAINER_ID_FORMAT');return ids;}
const projectIds=()=>fullIds(docker(['ps','-aq','--no-trunc','--filter','label=com.docker.compose.project='+project]).stdout);
const namedIds=name=>fullIds(docker(['ps','-aq','--no-trunc','--filter','name=^/'+name+'$']).stdout);
function sourceRows(rows,dir,expected){ensure(Array.isArray(rows)&&rows.length===30,'ADMIT_SOURCE_COUNT');const found=[];
 function walk(d,prefix=''){for(const e of fs.readdirSync(inside(d),{withFileTypes:true})){ensure(!e.isSymbolicLink(),'ADMIT_SOURCE_LINK');const n=prefix+e.name;if(e.isDirectory())walk(path.join(d,e.name),n+'/');else if(e.isFile()&&n.endsWith('.py'))found.push(n);}}
 walk(dir);ensure(stable(found.sort())===stable(rows.map(x=>x.path))&&sha(Buffer.from(stable(rows)))===expected,'ADMIT_SOURCE_MANIFEST');
 for(const row of rows){closed(row,['path','sha256']);ensure(/^[A-Za-z0-9_./-]+\.py$/.test(row.path)&&!row.path.split('/').includes('..')&&sha(read(path.join(dir,row.path)))===row.sha256,'ADMIT_SOURCE_DRIFT');}}
let m,chain,provenance,originalPrivateHashes,originalEnvSha,dbId=null,dbStarted=false,toolSafe=true,activationSent=false;
let helperSendSerial=0,preSendGuardFailed=false,archiveProofFailed=false,catalogMayHaveChanged=false;
const live=new Map(),evidence={unit:'/evidence/unit.json',calibration:'/evidence/calibration.json',review:'/evidence/review.json'};
const stateFile=path.join(work,'prepared-state.json'),intentFile=path.join(priv,'admission-activation-intent.json'),beforeFile=path.join(priv,'admission-before-state.json');
// Failure restoration only: no journal reads, full-proof retry or session termination.
const closeArchives=String.raw`import json,signal,hashlib
signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('ADMIT_CLOSE_DEADLINE')));signal.alarm(60)
dep={'__name__':'admission_archive_close_dependency'}
assert hashlib.sha256(ARG['source'].encode()).hexdigest()==ARG['sourceSha256'],'ADMIT_CLOSE_DEPENDENCY'
exec(compile(ARG['source'],'accepted-archive-dependency','exec'),dep)
ref=ARG['reference'];dep['report_reference'](ref)
control=dep['connect'](dep['MAIN']);targets=[];errors=[]
try:
 assert dep['identity'](control,dep['MAIN'])==ref['mainState']['oid'],'ADMIT_CLOSE_CONTROL'
 targets=[(dep['LEGACY'],16387),(dep['ARCHIVE'],32563)]
finally:
 for name,oid in targets:
  try:
   row=dep['catalog'](control,name)
   assert row and row[0]==oid,'ADMIT_CLOSE_OID'
   if row[1]:control.execute(dep['sql'].SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(dep['sql'].Identifier(name)))
   dep['no_connect'](control,name);dep['readonly_default'](control,oid)
   assert not dep['catalog'](control,name)[1],'ADMIT_CLOSE_STILL_OPEN'
   assert dep['sessions'](control,oid)==0,'ADMIT_CLOSE_FOREIGN_SESSION'
  except Exception as e:errors.append(type(e).__name__)
 control.close()
assert len(targets)==2 and not errors,'ADMIT_CLOSE_RESTORATION_NOT_PROVEN'
signal.alarm(0)
print(json.dumps({'status':'PASS','scope':'AD15-close-known-archives-only-not-row-proof','archivesClosed':True,'fullRowsVerified':False,'rowWrites':False,'foreignSessionsTerminated':False,'cleanupErrors':errors},sort_keys=True,separators=(',',':')))
`;
const report={status:'FAIL',scope:'RF15-unit-recovery-no-main-writes',phase,runId,lease:'NOT_IMPLEMENTED',native:'NOT_RUN',production:false,activationOutcome:'NOT_SENT',archivesPreserved:false,cleanupErrors:[],helperEvidence:{},privateAclResult:'OWNER_RESULT_REVIEW_REQUIRED'};
function gate(){const g=json(path.join(work,'review-gate.json'));closed(g,['status','authority','files']);ensure(g.status==='APPROVED'&&g.authority==='D-400'&&Array.isArray(g.files),'ADMIT_CODE_GATE');const required=new Set(['tools/test-trust-recovery.mjs','tools/trust_recovery_probe.py','work/dev15-recovery-20261103/unit-audit.py','docs/dev15-recovery-plan.md','work/dev15-recovery-20261103/private-acl.ps1','tools/trust_runtime_admission.py','tools/trust_archive_capacity.py','environment/trust/compose.yaml','environment/trust/archive-tool.compose.yaml','work/dev15-evidence-20261102/package/receipt.json','work/dev15-evidence-20261102/validation-result.json']);const seen=new Set();for(const row of g.files){closed(row,['path','sha256']);ensure(!seen.has(row.path)&&sha(read(row.path))===row.sha256,'ADMIT_GATE_DRIFT');seen.add(row.path);required.delete(row.path);}ensure(!required.size,'ADMIT_GATE_INCOMPLETE');}
function verifyInputs(){ensure(sha(read(path.join(pkg,'receipt.json')))===RECEIPT&&sha(read(validationFile))===VALIDATOR,'ADMIT_EVIDENCE_RECEIPT');const receipt=signed(path.join(pkg,'receipt.json'),'DEV15-EVIDENCE-FINALIZED');ensure(receipt.status==='PASS'&&receipt.sourceFingerprint===SOURCE&&receipt.schemaFingerprint===SCHEMA,'ADMIT_EVIDENCE_SCOPE');for(const[name,h]of Object.entries(receipt.files))ensure(/^[a-z-]+\.json$/.test(name)&&sha(read(path.join(pkg,name)))===h,'ADMIT_PACKAGE_DRIFT');const validation=json(validationFile);ensure(validation.status==='PASS'&&validation.result.status==='PASS'&&validation.result.unitBypass===false&&validation.result.connectionOpened===false,'ADMIT_VALIDATOR_RESULT');provenance=json(path.join(pkg,'provenance.json'));ensure(provenance.inputs.length===63&&provenance.sourceFingerprint===SOURCE&&provenance.schemaFingerprint===SCHEMA,'ADMIT_PROVENANCE_SCOPE');for(const row of provenance.inputs){ensure(sha(read(row.path))===row.sha256,'ADMIT_UPSTREAM63_DRIFT');if(row.authentication==='HMAC_VERIFIED'){const e=json(row.path);ensure(e.signature===mac(e.payload),'ADMIT_UPSTREAM_HMAC');}}
 m=json(path.join(runtime,'manifest.json'));ensure(!m.active&&m.writeMode==='disabled'&&m.sourceSha256===SOURCE,'ADMIT_MANIFEST_STATE');sourceRows(m.sourceFiles,m.sourceDirectory,SOURCE);sourceRows(m.sourceFiles,path.join(root,'trust'),SOURCE);for(const[f,h]of Object.entries(m.configHashes))ensure(sha(read(f))===h,'ADMIT_CONFIG_DRIFT');ensure(read(path.join(priv,'write-profile.json')).toString().trim()==='{}','ADMIT_PERMIT_OPEN');
 const capFile=path.join(runtime,'archive-capacity.json'),archiveIntentFile=path.join(runtime,'capacity-archive-intent.json'),legacyFile=path.join(runtime,'archive-unit.json');chain=signed(capFile,'DEV15-CAPACITY-ARCHIVE');const ai=signed(archiveIntentFile,'DEV15-CAPACITY-ARCHIVE-INTENT'),old=signed(legacyFile,'DEV15-WP-ARCHIVE');ensure(chain.sourceSha256===OLD&&chain.intentSha256===sha(read(archiveIntentFile))&&chain.legacyReceiptSha256===sha(read(legacyFile))&&stable(chain.report.unitState)===stable(ai.reference.unit)&&stable(chain.report.legacyState)===stable(old.report.state)&&sha(read(path.join(root,'tools/trust_archive_capacity.py')))===ai.helperSha256,'ADMIT_ARCHIVE_LINEAGE');sourceRows(chain.sourceFiles,chain.sourceDirectory,OLD);ensure(chain.report.mainState.head.generation==='9'&&chain.report.mainState.head.writerEpoch==='2'&&chain.report.mainState.oid>0&&![16387,32563,52766].includes(chain.report.mainState.oid),'ADMIT_MAIN_REFERENCE');
 if(originalEnvSha)ensure(sha(read(env))===originalEnvSha,'ADMIT_ENV_DRIFT');if(originalPrivateHashes)for(const[f,h]of Object.entries(originalPrivateHashes))ensure(sha(read(path.join(priv,f)))===h,'ADMIT_PRIVATE_CONFIG_DRIFT');return receipt;}
function resourcesOwned(){const volume=JSON.parse(docker(['volume','inspect',project+'-dbdata']).stdout);ensure(volume.length===1&&volume[0].Name===project+'-dbdata'&&volume[0].Labels?.['nestakada.scope']==='trust-test','ADMIT_DATABASE_VOLUME_OWNERSHIP');const names=docker(['network','ls','--format','{{.Name}}']).stdout.trim().split(/\r?\n/);for(const suffix of ['client','api','db'])if(names.includes(project+'-'+suffix)){const n=JSON.parse(docker(['network','inspect',project+'-'+suffix]).stdout)[0];ensure(n.Name===project+'-'+suffix&&n.Internal===true&&n.Labels?.['nestakada.scope']==='trust-test','ADMIT_NETWORK_OWNERSHIP');}const resolved=JSON.parse(compose(env,['--profile','tools','config','--format','json']).stdout);ensure(resolved.services?.db&&resolved.services?.migrate,'ADMIT_RESOLVED_SERVICES');ensure(resolved.services.db.image===m.images.postgres&&resolved.services.migrate.image===m.images['python-runtime']&&resolved.volumes.dbdata.name===project+'-dbdata'&&resolved.networks.db.name===project+'-db'&&resolved.networks.db.internal===true,'ADMIT_RESOLVED_CONFIGURATION');}
function dbOwned(v){const h=v.HostConfig,l=v.Config.Labels||{},data=v.Mounts.filter(x=>x.Destination==='/var/lib/postgresql');ensure(/^[a-f0-9]{64}$/.test(v.Id)&&v.Name==='/'+project+'-db'&&l['nestakada.scope']==='trust-test'&&l['com.docker.compose.project']===project&&l['com.docker.compose.service']==='db'&&v.Image===m.images.postgres&&h.Memory===536870912&&h.MemorySwap===536870912&&h.NanoCpus===500000000&&h.PidsLimit===128&&h.ReadonlyRootfs&&data.length===1&&data[0].Type==='volume'&&data[0].Name===project+'-dbdata'&&v.Mounts.filter(x=>x.Type==='volume').length===1&&v.Mounts.every(x=>x.Type!=='bind'||!x.RW)&&Object.keys(v.NetworkSettings.Networks).length===1&&v.NetworkSettings.Networks[project+'-db']&&!Object.values(v.NetworkSettings.Ports||{}).some(x=>x?.length),'ADMIT_DATABASE_OWNERSHIP');}
function mountPath(p){return String(p).replaceAll('\\','/').toLowerCase().replace(/^\/run\/desktop\/mnt\/host\/([a-z])\//,(_,d)=>d+':/').replace(/^\/host_mnt\/([a-z])\//,(_,d)=>d+':/').replace(/\/$/,'');}
function toolOwned(v,spec){if(spec.unit)ensure(v.Config.Env.includes('TRUST_DB_NAME=test_estakada_trust')&&v.Config.Env.includes('TRUST_TEST_EXECUTION=1'),'RF_ACTUAL_UNIT_ENV');const h=v.HostConfig,l=v.Config.Labels||{},source=v.Mounts.filter(x=>x.Destination==='/trust'),packageMount=v.Mounts.filter(x=>x.Destination==='/evidence');ensure(/^[a-f0-9]{64}$/.test(v.Id)&&v.Name==='/'+spec.name&&l['nestakada.scope']==='trust-test'&&l['com.docker.compose.project']===project&&l['com.docker.compose.service']===spec.service&&l['nestakada.admission-run']===runId&&v.Image===m.images['python-runtime']&&h.Memory===268435456&&h.MemorySwap===268435456&&h.NanoCpus===500000000&&h.PidsLimit===64&&h.ReadonlyRootfs&&source.length===1&&!source[0].RW&&mountPath(source[0].Source)===mountPath(spec.source)&&v.Mounts.every(x=>x.Type==='tmpfs'||x.Type==='bind'&&!x.RW)&&Object.keys(v.NetworkSettings.Networks).length===1&&v.NetworkSettings.Networks[project+'-db']&&!Object.values(v.NetworkSettings.Ports||{}).some(x=>x?.length),'ADMIT_TOOL_OWNERSHIP');if(spec.service==='migrate')ensure(packageMount.length===1&&!packageMount[0].RW&&mountPath(packageMount[0].Source)===mountPath(pkg),'ADMIT_PACKAGE_MOUNT');ensure(h.LogConfig.Type==='json-file'&&h.LogConfig.Config['max-size']==='1m'&&h.LogConfig.Config['max-file']==='2','ADMIT_TOOL_LOG_CAP');}
function reap(spec){if(spec.reapRefused)return false;try{const ids=namedIds(spec.name);ensure(ids.length<=1,'ADMIT_TOOL_AMBIGUOUS');if(ids.length){let v=inspect(ids[0]);toolOwned(v,spec);ensure(v.Id===ids[0]&&(!spec.id||v.Id===spec.id),'ADMIT_TOOL_ID_CHANGED');const ownedId=v.Id,suffix=crypto.randomUUID(),capture=fn=>{try{fn();}catch{report.status='FAIL';report.evidenceIncomplete=true;report.cleanupErrors.push('REAP_LOGGING_INCOMPLETE');}};capture(()=>save(path.join(priv,'admit-final-inspect-'+suffix+'.json'),v));if(v.State.Running){docker(['stop','--time','3',ownedId]);v=inspect(ownedId);toolOwned(v,spec);ensure(v.Id===ownedId,'ADMIT_TOOL_ID_CHANGED');}ensure(!v.State.Running,'ADMIT_TOOL_RUNNING');capture(()=>{const logs=docker(['logs',ownedId],{optional:true,timeout:5000});ensure(!logs.error&&logs.status===0,'ADMIT_REAP_LOGS_UNAVAILABLE');bytes(path.join(priv,'admit-final-'+suffix+'.stdout'),logs.stdout||'');bytes(path.join(priv,'admit-final-'+suffix+'.stderr'),logs.stderr||'');});docker(['rm',ownedId]);}ensure(!namedIds(spec.name).length,'ADMIT_TOOL_REMAINS');live.delete(spec.name);toolSafe=live.size===0;return true;}catch(error){spec.reapRefused=true;toolSafe=false;report.status='FAIL';throw error;}}
const child="import json,sys\nv=json.loads(sys.stdin.buffer.readline(1048577));ns={'__name__':'__main__','ARG':v['arg']};exec(compile(v['source'],'admission-helper','exec'),ns)";
const supervisor=String.raw`import sys,json,subprocess,pathlib
line=sys.stdin.buffer.readline(1048577)
if not line.endswith(b'\n') or len(line)>1048576:raise SystemExit('ADMIT_INPUT_BOUND')
v=json.loads(line);status=1
try:
 r=subprocess.run([sys.executable,'-u','-B','-c',v['child']],input=line,timeout=v['deadline']);status=r.returncode
finally:
 p=pathlib.Path('/sys/fs/cgroup')
 def n(k):return int((p/k).read_text().strip())
 def pairs(k):return {a:int(b) for a,b in (x.split() for x in (p/k).read_text().splitlines())}
 print(json.dumps({'scope':'AD15-completed-helper-cgroup','memoryPeak':n('memory.peak'),'memoryMax':n('memory.max'),'memoryEvents':pairs('memory.events'),'cpuStat':pairs('cpu.stat'),'pidsMax':n('pids.max'),'pidsPeak':n('pids.peak') if (p/'pids.peak').exists() else 'NOT_MEASURED'}),flush=True)
raise SystemExit(status)
`;
// Uses only exact-hash historical dependency functions; does NOT call its main/execute.
// Row reads are readonly; temporary archive ALLOW_CONNECTIONS catalog toggles are explicit.
const archives=String.raw`import json,signal,time,hashlib
signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('ADMIT_ARCHIVE_DEADLINE')));signal.alarm(120)
dep={'__name__':'admission_archive_dependency'}
assert hashlib.sha256(ARG['source'].encode()).hexdigest()==ARG['sourceSha256'],'ADMIT_ARCHIVE_DEPENDENCY'
exec(compile(ARG['source'],'accepted-archive-dependency','exec'),dep)
P,V=dep['metadata']();ref=ARG['reference'];dep['report_reference'](ref)
control=dep['connect'](dep['MAIN']);cleanupTargets=[];result={};cleanup=[]
try:
 assert dep['identity'](control,dep['MAIN'])==ref['mainState']['oid'],'ADMIT_ARCHIVE_CONTROL'
 cleanupTargets=[(dep['LEGACY'],16387),(dep['ARCHIVE'],32563)]
 for name,oid,legacy,key in [(dep['LEGACY'],16387,True,'legacyState'),(dep['ARCHIVE'],32563,False,'unitState')]:
  row=dep['catalog'](control,name)
  assert row and row[0]==oid and not row[1],'ADMIT_ARCHIVE_BASELINE'
  dep['no_connect'](control,name);dep['readonly_default'](control,oid)
  assert dep['sessions'](control,oid)==0,'ADMIT_ARCHIVE_ACTIVE_SESSION'
  control.execute(dep['sql'].SQL('ALTER DATABASE {} ALLOW_CONNECTIONS true').format(dep['sql'].Identifier(name)))
  try:
   value=dep['read_state'](name,P,V,legacy=legacy)
   assert value==ref[key],'ADMIT_ARCHIVE_ROWS_CHANGED'
   result[key]=value
  finally:
   row=dep['catalog'](control,name)
   if row and row[0]==oid:control.execute(dep['sql'].SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(dep['sql'].Identifier(name)))
  for _ in range(20):
   if dep['sessions'](control,oid)==0:break
   time.sleep(.05)
  assert dep['sessions'](control,oid)==0,'ADMIT_ARCHIVE_REMAINING_SESSION'
  dep['no_connect'](control,name);dep['readonly_default'](control,oid)
 fresh=dep['catalog'](control,dep['UNIT'])
 assert fresh and fresh[0]==ref['freshUnitOid'] and fresh[1] and fresh[2]==ref['freshUnitMarker'],'ADMIT_UNIT_MARKER'
finally:
 for name,oid in cleanupTargets:
  try:
   row=dep['catalog'](control,name)
   assert row and row[0]==oid,'ADMIT_ARCHIVE_CLEANUP_OID'
   if row[1]:control.execute(dep['sql'].SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(dep['sql'].Identifier(name)))
   dep['no_connect'](control,name);dep['readonly_default'](control,oid)
   assert not dep['catalog'](control,name)[1] and dep['sessions'](control,oid)==0,'ADMIT_ARCHIVE_CLEANUP'
  except Exception as e:cleanup.append(type(e).__name__)
 control.close()
assert not cleanup,'ADMIT_ARCHIVE_CLEANUP_FAILED'
signal.alarm(0)
print(json.dumps({'status':'PASS','scope':'AD15-archive-only-catalog-toggle-row-readonly','states':result,'freshUnitOid':fresh[0],'freshUnitMarker':fresh[2],'archivesClosed':True,'mainRowsRead':False,'rowWrites':False,'catalogToggles':True,'cleanupErrors':cleanup},sort_keys=True,separators=(',',':')))
`;
function runToolOnce(source,arg,label,{archive=false,activate=false,closeOnly=false,unit=false}={}){preToolGuard();const spec={name:project+'-admit-'+label+'-'+runId,service:archive?'init':'migrate',source:archive?chain.sourceDirectory:m.sourceDirectory,unit};ensure(!namedIds(spec.name).length,'ADMIT_TOOL_EXISTS');const envFile=archive?path.join(work,'archive-env-'+runId+'.env'):env;
 if(archive&&!fs.existsSync(envFile)){const original=read(env).toString();ensure((original.match(/^TRUST_SOURCE=/gm)||[]).length===1&&/^TRUST_SOURCE='[^'\r\n]*'$/m.test(original),'ADMIT_ENV_FORMAT');bytes(envFile,original.replace(/^TRUST_SOURCE='[^'\r\n]*'$/m,"TRUST_SOURCE='"+inside(chain.sourceDirectory).replaceAll('\\','/')+"'"));}
 const command=['python','-u','-B','-c',supervisor],definition={container_name:spec.name,stdin_open:true,tty:false,labels:{'nestakada.admission-run':runId},command:command.map(x=>x.replaceAll('$',()=> '$$'))};if(unit)definition.environment={TRUST_DB_NAME:'test_estakada_trust',TRUST_TEST_EXECUTION:'1'};if(!archive)definition.volumes=[{type:'bind',source:pkg,target:'/evidence',read_only:true}];const runner=path.join(priv,'admit-runner-'+label+'-'+runId+'.json');save(runner,{services:{[spec.service]:definition}});live.set(spec.name,spec);toolSafe=false;let logs,state,transport;
 try{docker(['compose','--env-file',envFile,'--project-name',project,'--file',base,'--file',metadata,'--file',runner,'--profile','tools','create','--no-build','--pull','never',spec.service]);const v=inspect(spec.name);toolOwned(v,spec);ensure(!v.State.Running&&stable(v.Config.Cmd)===stable(command),'ADMIT_ACTUAL_COMMAND');spec.id=v.Id;const input={source,arg,child,deadline:archive?130:70},inputFile=path.join(priv,'admit-input-'+label+'-'+runId+'.json');bytes(inputFile,Buffer.from(JSON.stringify(input)+'\n'));const pre={scope:'DEV15-ADMISSION-PRE-SEND',authority:'D-400',phase,label,runId,containerId:v.Id,sourceSha256:SOURCE,helperSourceSha256:sha(Buffer.from(source)),argumentSha256:sha(Buffer.from(stable(arg))),privateInputSha256:sha(read(inputFile)),runnerSha256:sha(read(runner)),dbId};save(path.join(priv,'admit-send-'+label+'-'+runId+'.json'),{payload:pre,signature:mac(pre)});if(archive)catalogMayHaveChanged=true;helperSendSerial++;if(activate){activationSent=true;report.activationOutcome='UNKNOWN';}
 transport=docker(['start','--attach','--interactive',v.Id],{optional:true,timeout:archive?150000:90000,input:read(inputFile)});save(path.join(priv,'admit-transport-'+label+'-'+runId+'.json'),execution(transport));bytes(path.join(priv,'admit-transport-'+label+'-'+runId+'.stdout'),transport.stdout||'');bytes(path.join(priv,'admit-transport-'+label+'-'+runId+'.stderr'),transport.stderr||'');state=inspect(v.Id).State;logs=docker(['logs',v.Id],{optional:true,timeout:5000});bytes(path.join(priv,'admit-logs-'+label+'-'+runId+'.stdout'),logs.stdout||'');bytes(path.join(priv,'admit-logs-'+label+'-'+runId+'.stderr'),logs.stderr||'');save(path.join(priv,'admit-execution-'+label+'-'+runId+'.json'),{transport:execution(transport),logs:execution(logs),state});report.helperEvidence[label]={containerId:v.Id,sourceSha256:sha(Buffer.from(source)),privateOutputSha256:sha(Buffer.from(logs.stdout||'')),exitCode:state.ExitCode,oomKilled:state.OOMKilled};
 }finally{reap(spec);}
 ensure(transport&&!transport.error&&state&&!state.Running&&!state.OOMKilled&&logs&&!logs.error&&logs.status===0,'ADMIT_HELPER_TRANSPORT');const lines=String(logs.stdout||'').trim().split('\n');ensure(lines.length===2,'ADMIT_HELPER_FRAMES');const value=JSON.parse(lines[0]),cg=JSON.parse(lines[1]);report.helperEvidence[label].resources=cg;ensure(cg.scope==='AD15-completed-helper-cgroup'&&Number.isSafeInteger(cg.memoryPeak)&&cg.memoryPeak>0&&cg.memoryMax===268435456&&cg.memoryPeak<=cg.memoryMax&&cg.memoryEvents.oom===0&&cg.memoryEvents.oom_kill===0&&cg.pidsMax===64&&(cg.pidsPeak==='NOT_MEASURED'||cg.pidsPeak<=64),'ADMIT_HELPER_RESOURCES');ensure(state.ExitCode===0&&value.status==='PASS','ADMIT_HELPER_REJECTED');return value;}
function preToolGuard(){ensure(toolSafe&&/^[a-f0-9]{64}$/.test(dbId),'ADMIT_HELPER_OVERLAP');const ids=projectIds();for(const id of ids){const v=inspect(id);ensure(v.Id===id,'ADMIT_INSPECT_ID_MISMATCH');dbOwned(v);ensure(v.State.Running,'ADMIT_DATABASE_NOT_RUNNING');}ensure(ids.length===1&&ids[0]===dbId,'ADMIT_UNEXPECTED_SERVICE');}
function runTool(source,arg,label,options={}){const serial=helperSendSerial;try{return runToolOnce(source,arg,label,options);}catch(error){if(helperSendSerial===serial)preSendGuardFailed=true;throw error;}}
function archiveProof(label){try{const dependency=read(path.join(root,'tools/trust_archive_capacity.py'));const value=runTool(archives,{source:dependency.toString(),sourceSha256:sha(dependency),reference:chain.report},'archives-'+label,{archive:true});ensure(value.archivesClosed===true,'ADMIT_ARCHIVE_NOT_CLOSED');catalogMayHaveChanged=false;return {status:'PASS',reportSha256:sha(Buffer.from(stable(value))),archivesClosed:true,catalogToggles:true,rowReadsReadonly:true};}catch(error){archiveProofFailed=true;throw error;}}
function closeKnownArchives(){const dependency=read(path.join(root,'tools/trust_archive_capacity.py'));const value=runTool(closeArchives,{source:dependency.toString(),sourceSha256:sha(dependency),reference:chain.report},'archives-close-only',{archive:true,closeOnly:true});ensure(value.archivesClosed===true&&value.fullRowsVerified===false,'ADMIT_CLOSE_RESTORATION_NOT_PROVEN');catalogMayHaveChanged=false;return {status:'CLOSED_NOT_ROW_VERIFIED',fullRowsVerified:false,reportSha256:sha(Buffer.from(stable(value)))};}
function closeChangedArchives(){if(!catalogMayHaveChanged)return;if(!toolSafe||preSendGuardFailed){report.archiveRestoration={status:'RESTORATION_NOT_PROVEN',reason:'LIVE_HELPER_OR_PRIOR_GUARD_REFUSAL'};report.cleanupErrors.push('ARCHIVE_RESTORATION_BLOCKED');return;}try{report.archiveRestoration=closeKnownArchives();}catch{report.archiveRestoration={status:'RESTORATION_NOT_PROVEN'};report.cleanupErrors.push('ARCHIVE_CLOSE_FAILED_NO_RETRY');}}
function finishArchiveChecks(){report.archivesPreserved=false;if(preSendGuardFailed||archiveProofFailed||!report.archivesBefore){report.status='FAIL';report.archivesAfter={status:'NOT_RUN',reason:'PRIOR_FAILURE_OR_NO_SUCCESSFUL_BASELINE'};closeChangedArchives();return;}if(!toolSafe){report.status='FAIL';report.archivesAfter={status:'NOT_RUN',reason:'LIVE_HELPER'};report.cleanupErrors.push('ARCHIVE_PROOF_BLOCKED_BY_LIVE_HELPER');closeChangedArchives();return;}try{report.archivesAfter=archiveProof('after');ensure(report.archivesBefore.reportSha256===report.archivesAfter.reportSha256,'ADMIT_ARCHIVE_CHANGE');report.archivesPreserved=true;}catch{report.status='FAIL';report.cleanupErrors.push('ARCHIVE_PRESERVATION_NOT_PROVEN');closeChangedArchives();}}
function enforceFinalStatus(){if(report.cleanupErrors.length||report.evidenceIncomplete)report.status='FAIL';}
function privateAcl(){const childEnv={...process.env};delete childEnv.PSModulePath;const r=spawnSync('C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe',['-NoProfile','-ExecutionPolicy','Bypass','-File',path.join(work,'private-acl.ps1')],{env:childEnv,encoding:'utf8',windowsHide:true,timeout:30000,maxBuffer:MAX});ensure(!r.error&&r.status===0,'RF_PRIVATE_ACL');const value=JSON.parse(r.stdout);ensure(value.status==='PASS','RF_PRIVATE_ACL_STATUS');return value;}
function expected(){return {database:'estakada_trust',oid:chain.report.mainState.oid,incarnation:chain.incarnation,sourceFingerprint:SOURCE,schemaFingerprint:SCHEMA,credentialConfigSha256:sha(read(path.join(priv,'credentials.json')))};}
function readMain(label){return runTool(read(path.join(root,'tools/trust_runtime_admission.py')).toString(),{action:'inspect',intent:null,baseline:null,evidence,expected:expected()},label).state;}
function startDatabase(){ensure(projectIds().length===0,'ADMIT_STOP_BEFORE_ACTION');resourcesOwned();dbStarted=true;compose(env,['up','-d','--no-build','--pull','never','db']);const v=inspect(project+'-db');dbOwned(v);dbId=v.Id;ensure(JSON.parse(docker(['network','inspect',project+'-db']).stdout)[0].Internal,'ADMIT_NETWORK');let ready=false;for(let i=0;i<20;i++){const r=docker(['exec',dbId,'pg_isready','-h','127.0.0.1','-d','estakada_trust'],{optional:true,timeout:3000});if(r.status===0&&!r.error){ready=true;break;}Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,250);}ensure(ready,'ADMIT_DB_NOT_READY');}
function stopDatabase(){ensure(![...live.values()].some(spec=>spec.reapRefused),'ADMIT_PRIOR_REAP_REFUSAL_OWNER_REQUIRED');resourcesOwned();for(const spec of [...live.values()])reap(spec);ensure(toolSafe,'ADMIT_UNREAPED_HELPER');for(const id of projectIds()){const v=inspect(id);ensure(v.Id===id,'ADMIT_INSPECT_ID_MISMATCH');dbOwned(v);if(dbId)ensure(v.Id===dbId,'ADMIT_DIFFERENT_DATABASE_CONTAINER');}compose(env,['down','--timeout','5']);ensure(projectIds().length===0,'ADMIT_OWNED_REMAINS');dbId=null;dbStarted=false;}
function baselineMatches(s){ensure(s.database==='estakada_trust'&&s.oid===chain.report.mainState.oid&&s.head.generation===9&&s.head.writer_epoch===2&&s.head.mode==='ACTIVE'&&s.admission===null&&s.stateDigest===chain.report.mainState.stateV2Sha256&&s.schemaFingerprint===SCHEMA&&s.sourceFingerprint===SOURCE&&stable(s.counts)===stable({AdmissionPolicy:0,Credential:4,Operation:4,RecoveryReceipt:2,RequestTombstone:1,RoutePolicy:3}),'ADMIT_BASELINE_CHANGED');}
let reserved=false;
try{
 ensure(process.argv.length===2,'RF_CLOSED_COMMAND');for(const key of Object.keys(process.env))ensure(!key.startsWith('TRUST_'),'ADMIT_ENV_OVERRIDE');const ctx=JSON.parse(docker(['context','inspect','desktop-linux']).stdout);ensure(ctx.length===1&&ctx[0].Endpoints?.docker?.Host==='npipe:////./pipe/dockerDesktopLinuxEngine','RF_LOCAL_CONTEXT');gate();report.privateAclBefore=privateAcl();verifyInputs();originalEnvSha=sha(read(env));originalPrivateHashes=Object.fromEntries(['credentials.json','identity-pin','django-secret','bootstrap-password','migrator-password','runtime-password'].map(f=>[f,sha(read(path.join(priv,f)))]));
 const previous=path.join(root,'work/dev15-lease-20261102/final-result.json');ensure(sha(read(previous))==='48621879539e8b52b049b8577bd45936794c07a3891cd7be4369a8ba233b1136','RF_PREVIOUS_MAIN_RESULT');const attempt={scope:'RF15-ACTION-ATTEMPT',authority:'D-400',phase,runId,sourceSha256:SOURCE,controllerSha256:sha(read(self)),helperSha256:sha(read(path.join(root,'tools/trust_recovery_probe.py'))),previousMainResultSha256:sha(read(previous)),mainWrites:false};save(path.join(work,'recovery-'+runId+'-attempt.json'),{payload:attempt,signature:mac(attempt)});fs.closeSync(fs.openSync(inside(reportFile),'wx',0o600));reserved=true;
 startDatabase();report.archivesBefore=archiveProof('before');report.mainBefore=readMain('main-before');ensure(report.mainBefore.head.generation===13&&report.mainBefore.head.writer_epoch===2&&report.mainBefore.counts.AdmissionPolicy===1&&report.mainBefore.stateDigest==='b42ec332cfcd39f3952210eedbfc9722b0302dd9e94fa76b3b3f03aa6f13599a','RF_MAIN_BASELINE');
 const ref={oid:chain.report.freshUnitOid,marker:chain.report.freshUnitMarker};ensure(ref.oid===52766,'RF_UNIT_OID');const witness=read(path.join(work,'unit-audit.py')).toString();report.unitBefore=runTool(witness,ref,'unit-before',{unit:true});ensure(Object.entries(report.unitBefore.counts).every(([k,v])=>v===(k==='django_migrations'?3:0)),'RF_UNIT_NOT_EMPTY');
 const arg={...ref,runId},intent={scope:'RF15-UNIT-ROLLBACK-INTENT',authority:'D-400',runId,unit:ref,unitBeforeSha256:sha(Buffer.from(stable(report.unitBefore))),mainBeforeSha256:sha(Buffer.from(stable(report.mainBefore))),helperSha256:sha(read(path.join(root,'tools/trust_recovery_probe.py'))),mainWrites:false};save(path.join(priv,'recovery-intent-'+runId+'.json'),{payload:intent,signature:mac(intent)});
 try{report.recovery=runTool(read(path.join(root,'tools/trust_recovery_probe.py')).toString(),arg,'recovery',{unit:true});}
 finally{if(toolSafe&&!preSendGuardFailed){report.unitAfter=runTool(witness,ref,'unit-after',{unit:true});report.unitPreserved=stable(report.unitBefore)===stable(report.unitAfter);report.mainAfter=readMain('main-after');report.mainPreserved=stable(report.mainBefore)===stable(report.mainAfter);}else{report.unitAfter={status:'NOT_RUN',reason:'UNSAFE_OR_PRIOR_GUARD_REFUSAL'};report.mainPreserved=false;}}
 ensure(report.recovery?.status==='PASS'&&report.unitPreserved&&report.mainPreserved,'RF_PRESERVATION');report.mainWrites=false;report.unitOnly=true;report.status='PASS';

}catch(error){report.errorCode=/^[A-Z0-9_]{1,90}$/.test(error?.message||'')?error.message:'ADMIT_HOST_FAILED';if(activationSent&&report.activationOutcome!=='COMMITTED_VALIDATED')report.activationOutcome='UNKNOWN_INSPECT_OR_EXACT_RETRY_REQUIRED';}
finally{
 if(dbStarted){for(const spec of [...live.values()])if(!spec.reapRefused)try{reap(spec);}catch{report.status='FAIL';report.cleanupErrors.push('HELPER_REAP_FAILED');}finishArchiveChecks();try{stopDatabase();report.ownedContainersIncludingStopped=0;}catch{report.status='FAIL';report.cleanupErrors.push('STOP_FAILED');}}
 if(reserved){try{verifyInputs();report.upstream63Drift=0;report.configDrift=0;report.permitEmpty=true;report.manifestUnchanged=true;}catch{report.status='FAIL';report.cleanupErrors.push('INPUT_PRESERVATION_FAILED');}if(phase!=='Stop'&&!report.archivesPreserved)report.status='FAIL';try{report.privateAclAfter=privateAcl();}catch{report.status='FAIL';report.cleanupErrors.push('RF_FINAL_ACL_NOT_PROVEN');}enforceFinalStatus();const b=Buffer.from(stable(report)+'\n');ensure(b.length<=MAX,'ADMIT_REPORT_SIZE');fs.writeFileSync(inside(reportFile),b);}
 console.log(JSON.stringify({status:report.status,phase:phase||null,reportPath:reserved?path.relative(root,reportFile).replaceAll('\\','/'):null,errorCode:report.errorCode||null,activationOutcome:report.activationOutcome,lease:report.lease,native:report.native}));if(report.status!=='PASS')process.exitCode=1;
}
