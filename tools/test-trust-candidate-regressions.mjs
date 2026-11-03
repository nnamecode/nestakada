// D-380/D-383, WB15-004: receipt-guarded regressions of a separate preview.
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';import {fileURLToPath} from 'node:url';
const root=path.resolve('T:/nestakada'),project='nestakada-trust-test',out=path.join(root,'work/dev15-corpus-20261102');
const runtime=path.join(root,'work/dev15-20261102/runtime'),priv=path.join(root,'work/dev15-20261102/private');
const manifestFile=path.join(runtime,'manifest.json'),envFile=path.join(runtime,'compose.env');
const base=path.join(root,'environment/trust/compose.yaml'),metadataCompose=path.join(root,'environment/trust/archive-tool.compose.yaml');
const candidateFile=path.join(root,'work/dev15-timing-20261102/candidate-consumer.py'),self=fileURLToPath(import.meta.url);
const OLD='5fbcb9d9ea04ee58853b9b8d9fe2131fc6b0d1122f087239f3c66bfded768986',OLD_CONSUMER='5e89ca8ad69fcdea3923f3af7f5dd973f75e0891066c562169321da72b6141b3';
const NEW_CONSUMER='15e6c9b25764eab698dac4e52f8cca804f4c339a271d83db521bdf0e8ee98d21';
const ensure=(v,c)=>{if(!v)throw Error(c);},sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const stable=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a<b?-1:a>b?1:0)):x);
function closed(v,keys){ensure(v&&typeof v==='object'&&!Array.isArray(v)&&stable(Object.keys(v).sort())===stable([...keys].sort()),'CANDIDATE_CLOSED_INPUT');}
function inside(f){const value=path.resolve(f);ensure(value.startsWith(root+path.sep),'CANDIDATE_PATH_SCOPE');for(let p=value;p!==root;p=path.dirname(p))if(fs.existsSync(p))ensure(!fs.lstatSync(p).isSymbolicLink(),'CANDIDATE_LINK');return value;}
function read(f){const v=inside(f);ensure(fs.lstatSync(v).isFile(),'CANDIDATE_REGULAR_FILE');return fs.readFileSync(v);}
const json=f=>JSON.parse(read(f));
function save(f,v){fs.writeFileSync(inside(f),JSON.stringify(v,null,2)+'\n',{flag:'wx',mode:0o600});}
function text(f,v){fs.writeFileSync(inside(f),v,{flag:'wx',mode:0o600});}
function mac(payload){const keys=json(path.join(priv,'credentials.json')).credentials.filter(x=>x.role==='recovery');ensure(keys.length===1&&/^[a-f0-9]{64}$/.test(keys[0].secret),'CANDIDATE_OPERATOR_KEY');return crypto.createHmac('sha256',Buffer.from(keys[0].secret,'hex')).update(stable(payload)).digest('hex');}
function signed(file){const v=json(file);closed(v,['payload','signature']);ensure(v.signature===mac(v.payload),'CANDIDATE_SIGNATURE');return v;}
function call(program,args,{input,timeout=90000,optional=false}={}){const r=spawnSync(program,args,{input,encoding:'utf8',timeout,maxBuffer:4194304,windowsHide:true});if((r.error||r.status!==0)&&!optional){save(path.join(priv,'candidate-command-'+crypto.randomUUID()+'.json'),{status:r.status,errorCode:r.error?.code||null,signal:r.signal||null,stdout:r.stdout||'',stderr:r.stderr||''});throw Error('CANDIDATE_COMMAND_FAILED');}return r;}
const docker=(a,o)=>call('docker.exe',a,o),local=(a,o)=>call(process.execPath,[path.join(root,'tools/local_trust.mjs'),a],o);
function compose(file,args,options,metadata=false){return docker(['compose','--env-file',file,'--project-name',project,'--file',base,...(metadata?['--file',metadataCompose]:[]),...args],options);}
function rowsValid(rows){ensure(Array.isArray(rows)&&rows.length===30,'CANDIDATE_SOURCE_COUNT');const seen=new Set();for(const row of rows){closed(row,['path','sha256']);ensure(typeof row.path==='string'&&/^[A-Za-z0-9_./-]+\.py$/.test(row.path)&&!row.path.startsWith('/')&&!row.path.split('/').some(x=>!x||x==='.'||x==='..')&&!seen.has(row.path)&&/^[a-f0-9]{64}$/.test(row.sha256),'CANDIDATE_SOURCE_ROW');seen.add(row.path);}ensure(stable(rows.map(x=>x.path))===stable(rows.map(x=>x.path).sort()),'CANDIDATE_SOURCE_ORDER');}
function verifySources(m){rowsValid(m.sourceFiles);ensure(m.sourceSha256===OLD&&sha(JSON.stringify(m.sourceFiles))===OLD,'CANDIDATE_OLD_SOURCE');for(const row of m.sourceFiles)for(const dir of [path.join(root,'trust'),m.sourceDirectory])ensure(sha(read(path.join(dir,row.path)))===row.sha256,'CANDIDATE_SOURCE_DRIFT');for(const [file,value]of Object.entries(m.configHashes))ensure(sha(read(path.join(root,file)))===value,'CANDIDATE_CONFIG_DRIFT');ensure(read(path.join(priv,'write-profile.json')).toString().trim()==='{}','CANDIDATE_PERMIT_NOT_DISABLED');}
function envCopy(destination,source,newRuntime=null){const original=read(envFile).toString();ensure((original.match(/^TRUST_SOURCE=/gm)||[]).length===1&&(original.match(/^TRUST_RUNTIME_ID=/gm)||[]).length===1&&/^TRUST_SOURCE='[^'\r\n]*'$/m.test(original)&&/^TRUST_RUNTIME_ID='[^'\r\n]*'$/m.test(original)&&/^TRUST_WRITE_MODE='disabled'$/m.test(original),'CANDIDATE_ENV_PROFILE');const sourcePath=inside(source).replaceAll('\\','/');ensure(!sourcePath.includes("'"),'CANDIDATE_ENV_SOURCE');let result=original.replace(/^TRUST_SOURCE='[^'\r\n]*'$/m,"TRUST_SOURCE='"+sourcePath+"'");if(newRuntime!==null)result=result.replace(/^TRUST_RUNTIME_ID='[^'\r\n]*'$/m,"TRUST_RUNTIME_ID='"+newRuntime+"'");text(destination,result);return sha(Buffer.from(result));}
function lineage(m){const intentFile=path.join(runtime,'capacity-archive-intent.json'),receiptFile=path.join(runtime,'archive-capacity.json'),legacyFile=path.join(runtime,'archive-unit.json');const intent=signed(intentFile).payload,p=signed(receiptFile).payload,legacy=signed(legacyFile).payload,r=p.report;
 ensure(intent.scope==='DEV15-CAPACITY-ARCHIVE-INTENT'&&intent.authority==='D-380'&&p.scope==='DEV15-CAPACITY-ARCHIVE'&&p.authority==='D-380'&&legacy.scope==='DEV15-WP-ARCHIVE','CANDIDATE_RECEIPT_SCOPE');
 ensure(p.intentSha256===sha(read(intentFile))&&p.legacyReceiptSha256===sha(read(legacyFile))&&intent.legacyReceiptSha256===p.legacyReceiptSha256&&p.incarnation===m.incarnation&&intent.incarnation===m.incarnation&&legacy.incarnation===m.incarnation,'CANDIDATE_RECEIPT_LINKS');
 ensure(legacy.report.freshUnitOid===32563&&legacy.report.state.oid===16387&&r.status==='PASS'&&r.scope==='DEV15-CAPACITY-ARCHIVE'&&r.archiveName==='test_estakada_trust_cap_32563'&&r.originalName==='test_estakada_trust'&&r.legacyName==='test_estakada_trust_cal_7e145c49'&&r.unitState.oid===32563&&r.archivesClosed===true&&r.dropPerformed===false&&r.sameRowsDigest===true&&r.sameArchiveOid===true,'CANDIDATE_ARCHIVE_CHAIN');
 const nonce=intent.reference.intentId;ensure(/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(nonce)&&Number.isSafeInteger(r.freshUnitOid)&&r.freshUnitOid>0&&![32563,16387,r.mainState.oid].includes(r.freshUnitOid)&&r.freshUnitMarker==='ESTAKADA-DEV15-CAPACITY:'+nonce,'CANDIDATE_FRESH_REFERENCE');
 ensure(stable(r.unitState)===stable(intent.reference.unit)&&stable(r.mainState)===stable(intent.reference.main)&&stable(r.legacyState)===stable(intent.reference.legacyState)&&stable(r.legacyState)===stable(legacy.report.state),'CANDIDATE_STATE_LINKS');
 ensure(p.sourceSha256===OLD&&intent.sourceSha256===OLD&&p.sourceDirectory===intent.sourceDirectory&&stable(p.sourceFiles)===stable(intent.sourceFiles),'CANDIDATE_ARCHIVE_SOURCE');rowsValid(p.sourceFiles);ensure(sha(JSON.stringify(p.sourceFiles))===OLD,'CANDIDATE_ARCHIVE_MANIFEST');for(const row of p.sourceFiles)ensure(sha(read(path.join(p.sourceDirectory,row.path)))===row.sha256,'CANDIDATE_ARCHIVE_FROZEN_DRIFT');
 ensure(sha(read(path.join(root,'tools/trust_archive_capacity.py')))===intent.helperSha256,'CANDIDATE_ARCHIVE_HELPER_DRIFT');return {intent,p,report:r,hashes:{intent:sha(read(intentFile)),receipt:sha(read(receiptFile)),legacy:sha(read(legacyFile))}};}
function verifyChain(chain,archiveEnv,label){const launcher="import json,sys\nv=json.loads(sys.stdin.buffer.readline(1048577));ns={'__name__':'__main__','ARG':v['arg']};exec(compile(v['source'],'candidate-archive-verifier','exec'),ns)";const r=compose(archiveEnv,['--profile','tools','run','--rm','--no-deps','-T','init','python','-B','-c',launcher],{optional:true,timeout:150000,input:JSON.stringify({source:read(path.join(root,'tools/trust_archive_capacity.py')).toString(),arg:{action:'verify',reference:chain.report}})+'\n'},true);save(path.join(priv,'candidate-chain-'+label+'-'+crypto.randomUUID()+'.json'),{status:r.status,errorCode:r.error?.code||null,signal:r.signal||null,stdout:r.stdout||'',stderr:r.stderr||''});ensure(!r.error&&r.status===0&&r.stdout.trim(),'CANDIDATE_CHAIN_EXECUTION');let v;try{v=JSON.parse(r.stdout);}catch{throw Error('CANDIDATE_CHAIN_JSON');}ensure(stable(v)===stable(chain.report),'CANDIDATE_CHAIN_CHANGED');return {status:'PASS',reportSha256:sha(Buffer.from(stable(v))),freshUnitOid:v.freshUnitOid,freshUnitMarker:v.freshUnitMarker};}
function verifyPreview(directory,rows){for(const row of rows)ensure(sha(read(path.join(directory,row.path)))===row.sha256,'CANDIDATE_PREVIEW_DRIFT');}
function dbCaps(m){const v=JSON.parse(docker(['inspect',project+'-db']).stdout)[0],h=v.HostConfig;ensure(v.Config.Labels?.['nestakada.scope']==='trust-test'&&v.Config.Labels?.['com.docker.compose.project']===project&&v.Config.Labels?.['com.docker.compose.service']==='db'&&v.Image===m.images.postgres&&v.State.Running&&h.Memory===536870912&&h.MemorySwap===536870912&&h.NanoCpus===500000000&&h.PidsLimit===128&&h.ReadonlyRootfs&&!Object.values(v.NetworkSettings.Ports||{}).some(x=>x?.length),'CANDIDATE_DB_CAPS');return v.Id;}
function toolIds(){return docker(['ps','-aq','--filter','name=^/'+toolName+'$']).stdout.trim().split(/\r?\n/).filter(Boolean);}
function runIds(){return docker(['ps','-aq','--filter','label=nestakada.candidate-run-id='+runId]).stdout.trim().split(/\r?\n/).filter(Boolean);}
function mountPath(value){return String(value).replaceAll('\\','/').toLowerCase().replace(/^\/run\/desktop\/mnt\/host\/([a-z])\//,(_,drive)=>drive+':/').replace(/^\/host_mnt\/([a-z])\//,(_,drive)=>drive+':/').replace(/\/$/,'');}
function ownedTool(id){const v=JSON.parse(docker(['inspect',id]).stdout)[0],h=v.HostConfig,l=v.Config.Labels||{},source=v.Mounts.filter(x=>x.Destination==='/trust');ensure(v.Name==='/'+toolName&&l['nestakada.scope']==='trust-test'&&l['com.docker.compose.project']===project&&l['com.docker.compose.service']==='migrate'&&l['nestakada.candidate-run-id']===runId&&v.Image===m.images['python-runtime']&&h.ReadonlyRootfs&&h.Memory===268435456&&h.MemorySwap===268435456&&h.NanoCpus===500000000&&h.PidsLimit===64&&source.length===1&&source[0].Type==='bind'&&!source[0].RW&&mountPath(source[0].Source)===mountPath(preview)&&v.Mounts.every(x=>x.Type==='tmpfs'||x.Type==='bind'&&!x.RW)&&!Object.values(v.NetworkSettings.Ports||{}).some(x=>x?.length)&&v.Config.Env.includes('TRUST_RUNTIME_ID='+runId)&&v.Config.Env.includes('TRUST_WRITE_PROFILE=disabled'),'CANDIDATE_TOOL_OWNERSHIP');return v;}
function reapTool(){const ids=toolIds();ensure(ids.length<=1,'CANDIDATE_TOOL_NOT_UNIQUE');if(!ids.length){ensure(runIds().length===0,'CANDIDATE_RUN_LABEL_REMAINS');return {reaped:true,present:false};}const v=ownedTool(ids[0]),evidence={inspect:v};let evidenceSaved=false;const metadata=r=>({status:r.status,errorCode:r.error?.code||null,signal:r.signal||null,stdout:(r.stdout||'').slice(0,262144),stderr:(r.stderr||'').slice(0,262144)});
 try{evidence.logs=metadata(docker(['logs','--tail','100',v.Id],{optional:true,timeout:5000}));evidence.cgroup=v.State.Running?metadata(docker(['exec',v.Id,'sh','-c','cat /sys/fs/cgroup/memory.peak /sys/fs/cgroup/memory.max /sys/fs/cgroup/memory.events /sys/fs/cgroup/cpu.stat /sys/fs/cgroup/pids.current /sys/fs/cgroup/pids.max'],{optional:true,timeout:5000})):{observation:'NOT_RUNNING'};save(path.join(priv,'candidate-tool-before-reap-'+runId+'.json'),evidence);evidenceSaved=true;}catch{report.status='FAIL';(report.preservationErrors??=[]).push('TOOL_EVIDENCE_FAILED');}
 const stop=v.State.Running?metadata(docker(['stop','--time','3',v.Id],{optional:true,timeout:10000})):null;const after=ownedTool(v.Id);ensure(!after.State.Running,'CANDIDATE_TOOL_STILL_RUNNING');const removal=metadata(docker(['rm',v.Id],{optional:true,timeout:10000}));ensure(toolIds().length===0&&runIds().length===0,'CANDIDATE_TOOL_NOT_REAPED');return {reaped:true,present:true,containerId:v.Id,evidenceSaved,stop:stop&&{status:stop.status,errorCode:stop.errorCode,signal:stop.signal},removal:{status:removal.status,errorCode:removal.errorCode,signal:removal.signal},noVolumeRemoval:true};}

let report={status:'FAIL',scope:'candidate-preview-regressions-not-integration',productIntegrated:false,mainAdmission:false,htmlAdmission:false,workflowComplete:false,production:false};
let started=false,reserved=false,toolAttempted=false,chain=null,chainHashes=null,archiveEnv=null,preview=null,previewRows=null,m=null;
const runId=crypto.randomUUID(),archiveEnvFile=path.join(out,'candidate-archive-env-'+runId+'.env'),previewEnvFile=path.join(out,'candidate-preview-env-'+runId+'.env');
const toolName=project+'-candidate-regressions-'+runId;
try{
 ensure(process.argv.length===2,'CANDIDATE_NO_ARGUMENTS');for(const name of Object.keys(process.env))ensure(!name.startsWith('TRUST_'),'CANDIDATE_INHERITED_OVERRIDE');
 const gateFile=path.join(out,'candidate-review-gate.json'),gate=json(gateFile);closed(gate,['status','authority','files']);ensure(gate.status==='APPROVED'&&gate.authority==='D-383'&&Array.isArray(gate.files),'CANDIDATE_REVIEW_REQUIRED');
 const gated=new Set();for(const row of gate.files){closed(row,['path','sha256']);ensure(!gated.has(row.path)&&sha(read(path.join(root,row.path)))===row.sha256,'CANDIDATE_REVIEW_DRIFT');gated.add(row.path);}
 for(const required of [path.relative(root,self).replaceAll('\\','/'),'tools/trust_archive_capacity.py','tools/local_trust.mjs','environment/trust/compose.yaml','environment/trust/archive-tool.compose.yaml','work/dev15-timing-20261102/candidate-consumer.py'])ensure(gated.has(required),'CANDIDATE_REVIEW_INCOMPLETE');
 const old=json(manifestFile);ensure(old.project===project&&!old.active&&old.initialized&&old.writeMode==='disabled'&&old.privateDirectory===priv,'CANDIDATE_CLOSED_MANIFEST');verifySources(old);chain=lineage(old);chainHashes=chain.hashes;
 ensure(sha(read(candidateFile))===NEW_CONSUMER&&sha(read(path.join(root,'trust/journal/consumer.py')))===OLD_CONSUMER,'CANDIDATE_CONSUMER_PIN');
 previewRows=old.sourceFiles.map(row=>({path:row.path,sha256:row.path==='journal/consumer.py'?NEW_CONSUMER:row.sha256}));const previewSha=sha(JSON.stringify(previewRows));
 ensure(previewSha!==OLD&&previewRows.filter((row,index)=>row.sha256!==old.sourceFiles[index].sha256).length===1,'CANDIDATE_SINGLE_FILE_DIFF');preview=path.join(root,'work/preview',runId);
 ensure(!fs.existsSync(preview)&&!fs.existsSync(path.join(out,'candidate-test-report.json')),'CANDIDATE_ALREADY_ATTEMPTED');
 const payload={scope:'DEV15-CANDIDATE-REGRESSIONS',authority:'D-383',basedOn:'D-380',runId,toolName,runLabel:'nestakada.candidate-run-id='+runId,incarnation:old.incarnation,receiptHashes:chain.hashes,manifestSha256:sha(read(manifestFile)),oldSourceSha256:OLD,sourceFiles:old.sourceFiles,sourceDirectory:old.sourceDirectory,configHashes:old.configHashes,candidateSha256:NEW_CONSUMER,previewDirectory:preview,previewSourceSha256:previewSha,previewFiles:previewRows,controllerSha256:sha(read(self)),reviewGateSha256:sha(read(gateFile)),freshUnitOid:chain.report.freshUnitOid,freshUnitMarker:chain.report.freshUnitMarker};
 save(path.join(out,'candidate-test-attempt.json'),{payload,signature:mac(payload)});
 fs.closeSync(fs.openSync(path.join(out,'candidate-test-report.json'),'wx',0o600));reserved=true;
 started=true;local('Start',{timeout:180000});m=json(manifestFile);verifySources(m);ensure(m.sourceSha256===OLD,'CANDIDATE_START_SOURCE');
 compose(envFile,['stop','--timeout','3','api','ingress']);const actualManifest=json(manifestFile);ensure(stable(actualManifest)===stable(m)&&m.active===true,'CANDIDATE_MANIFEST_CHANGED');m={...m,active:false};fs.writeFileSync(inside(manifestFile),JSON.stringify(m,null,2)+'\n',{mode:0o600});
 report.dbId=dbCaps(m);chain=lineage(m);ensure(stable(chain.hashes)===stable(chainHashes),'CANDIDATE_RECEIPT_CHANGED');report.archiveEnvironmentSha256=envCopy(archiveEnvFile,chain.p.sourceDirectory);archiveEnv=archiveEnvFile;
 report.chainBefore=verifyChain(chain,archiveEnv,'before');
 fs.mkdirSync(inside(path.dirname(preview)),{recursive:true});fs.mkdirSync(inside(preview));
 for(const row of m.sourceFiles){const destination=inside(path.join(preview,row.path));fs.mkdirSync(path.dirname(destination),{recursive:true});const bytes=row.path==='journal/consumer.py'?read(candidateFile):read(path.join(m.sourceDirectory,row.path));ensure(sha(bytes)===previewRows.find(x=>x.path===row.path).sha256,'CANDIDATE_PREVIEW_BUILD');fs.writeFileSync(destination,bytes,{flag:'wx',mode:0o600});}
 verifyPreview(preview,previewRows);save(path.join(out,'candidate-preview-manifest.json'),{runId,sourceSha256:previewSha,sourceFiles:previewRows,changedFiles:['journal/consumer.py'],productIntegrated:false});
 report.previewEnvironmentSha256=envCopy(previewEnvFile,preview,runId);
 // Successor guard is deliberately here; local_trust Tests remains closed.
 ensure(stable(lineage(m).hashes)===stable(chain.hashes),'CANDIDATE_RECEIPT_CHANGED');report.guardImmediatelyBeforeSetup=verifyChain(chain,archiveEnv,'before-setup');
 const expected=JSON.stringify({sourceSha256:previewSha,freshUnitOid:chain.report.freshUnitOid,freshUnitMarker:chain.report.freshUnitMarker});
 const program=`import json,django,signal
signal.alarm(180)
django.setup()
from django.conf import settings
from django.db import connection
from django.test.runner import DiscoverRunner
from journal import profile as P
expected=json.loads(${JSON.stringify(expected)})
assert P.source_fingerprint()==expected['sourceSha256']
assert connection.settings_dict['NAME']=='estakada_trust' and connection.settings_dict['USER']=='trust_migrator'
assert connection.settings_dict['TEST']['NAME']=='test_estakada_trust' and settings.TRUST_WRITE_PROFILE=='disabled'
class GuardedDiscoverRunner(DiscoverRunner):
 def build_suite(self,*args,**kwargs):
  suite=super().build_suite(*args,**kwargs)
  assert suite.countTestCases()==131
  return suite
 def setup_databases(self,**kwargs):
  result=super().setup_databases(**kwargs)
  with connection.cursor() as cursor:
   cursor.execute("SELECT current_database(),current_user,session_user,oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
   assert cursor.fetchone()==('test_estakada_trust','trust_migrator','trust_migrator',expected['freshUnitOid'],expected['freshUnitMarker'])
  return result
 def run_suite(self,suite,**kwargs):
  result=super().run_suite(suite,**kwargs)
  assert result.testsRun==131 and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses
  return result
failures=GuardedDiscoverRunner(keepdb=True,interactive=False,verbosity=1).run_tests(['journal'])
assert failures==0
assert P.source_fingerprint()==expected['sourceSha256']
print('WB15_SHADOW_131_PASS')`;
 ensure(toolIds().length===0&&runIds().length===0,'CANDIDATE_TOOL_ALREADY_EXISTS');toolAttempted=true;
 const tick=Date.now(),r=compose(previewEnvFile,['--profile','tools','run','--no-deps','-T','--name',toolName,'--label','nestakada.candidate-run-id='+runId,'-e','TRUST_TEST_EXECUTION=1','migrate','python','-B','-c',program],{optional:true,timeout:180000});
 const rawFile=path.join(priv,'candidate-regressions-'+runId+'.json');save(rawFile,{status:r.status,errorCode:r.error?.code||null,signal:r.signal||null,elapsedMs:Date.now()-tick,stdout:r.stdout||'',stderr:r.stderr||''});
 report.execution={status:r.status,errorCode:r.error?.code||null,signal:r.signal||null,elapsedMs:Date.now()-tick,rawSha256:sha(read(rawFile))};
 const combined=(r.stdout||'')+'\n'+(r.stderr||''),summary=/Ran ([0-9]+) tests? in ([0-9.]+)s/u.exec(combined);
 ensure(!r.error&&r.status===0&&summary&&Number(summary[1])===131&&/^OK$/mu.test(combined)&&!/^OK \(/mu.test(combined)&&/^WB15_SHADOW_131_PASS$/mu.test(combined),'CANDIDATE_REGRESSIONS_FAILED');
 report.tests={status:'PASS',count:131,seconds:Number(summary[2]),sourceSha256:previewSha,scope:'separate-preview-not-product-integration',freshUnitOid:chain.report.freshUnitOid,runtimeId:runId,skipped:0};
 report.previewSourceSha256=previewSha;report.changedFiles=['journal/consumer.py'];report.status='PASS';
}catch(error){report.errorCode=/^[A-Z0-9_]{1,90}$/.test(error?.message||'')?error.message:'CANDIDATE_CONTROLLER_FAILED';}
finally{
 if(started){try{compose(envFile,['stop','--timeout','3','api','ingress']);}catch{report.status='FAIL';report.preservationErrors=['FRONT_STOP_FAILED'];}
  let toolReaped=false;report.testToolAttempted=toolAttempted;try{report.toolCleanup=reapTool();toolReaped=report.toolCleanup.reaped;}catch{report.status='FAIL';(report.preservationErrors??=[]).push('TOOL_REAP_FAILED');}
  if(toolReaped){try{chain=lineage(json(manifestFile));ensure(stable(chain.hashes)===stable(chainHashes),'CANDIDATE_RECEIPT_CHANGED');if(archiveEnv===null){envCopy(archiveEnvFile,chain.p.sourceDirectory);archiveEnv=archiveEnvFile;}report.chainAfter=verifyChain(chain,archiveEnv,'after');}catch{report.status='FAIL';(report.preservationErrors??=[]).push('CHAIN_VERIFY_FAILED');}}else report.chainAfter={status:'NOT_RUN',reason:'TEST_TOOL_NOT_REAPED'};
  try{verifySources(json(manifestFile));report.sourceDrift=0;}catch{report.status='FAIL';(report.preservationErrors??=[]).push('SOURCE_VERIFY_FAILED');}
  try{if(preview&&fs.existsSync(preview)&&previewRows)verifyPreview(preview,previewRows);}catch{report.status='FAIL';(report.preservationErrors??=[]).push('PREVIEW_VERIFY_FAILED');}
  try{local('Stop');report.finalStatus=JSON.parse(local('Status').stdout);ensure(report.finalStatus.actualRunningContainers===0&&report.finalStatus.manifestActive===false&&report.finalStatus.writeProfile==='disabled','CANDIDATE_FINAL_NOT_CLOSED');}catch{report.status='FAIL';(report.preservationErrors??=[]).push('STOP_FAILED');}
  try{report.finalOwnedTestContainers={exactName:toolIds().length,runLabel:runIds().length};ensure(report.finalOwnedTestContainers.exactName===0&&report.finalOwnedTestContainers.runLabel===0,'CANDIDATE_TOOL_RESIDUAL');}catch{report.status='FAIL';(report.preservationErrors??=[]).push('TOOL_RESIDUAL');}}
 if(reserved)fs.writeFileSync(inside(path.join(out,'candidate-test-report.json')),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({status:report.status,errorCode:report.errorCode||null,previewOnly:true}));if(report.status!=='PASS')process.exitCode=1;
}
