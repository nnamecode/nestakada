// WB15-004 / D-380: retain both exact corpora before any destructive UNIT tests.
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';
import {spawn,spawnSync} from 'node:child_process';import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),project='nestakada-trust-test';
const runtime=path.join(root,'work/dev15-20261102/runtime'),priv=path.join(root,'work/dev15-20261102/private'),rootOut=path.join(root,'work/dev15-corpus-20261102');
const resumePreflight=process.argv.length===3&&process.argv[2]==='ResumePreflight',out=resumePreflight?path.join(rootOut,'resume-001'):rootOut;
const env=path.join(runtime,'compose.env'),base=path.join(root,'environment/trust/compose.yaml'),metadataOverride=path.join(root,'environment/trust/archive-tool.compose.yaml');
const unit='test_estakada_trust',archive='test_estakada_trust_cap_32563',appName='dev15_capacity_archive_guard';
const stable=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a<b?-1:a>b?1:0)):x);
const sha=b=>crypto.createHash('sha256').update(b).digest('hex'),ensure=(v,c)=>{if(!v)throw Error(c);};
function read(file){const f=path.resolve(file);ensure(f.startsWith(root+path.sep),'PATH_SCOPE');for(let p=f;p!==root;p=path.dirname(p))ensure(!fs.lstatSync(p).isSymbolicLink(),'LINK_REJECTED');return fs.readFileSync(f);}
const json=f=>JSON.parse(read(f));
function save(file,v){ensure(path.resolve(file).startsWith(root+path.sep),'OUTPUT_SCOPE');fs.writeFileSync(file,JSON.stringify(v,null,2)+'\n',{flag:'wx',mode:0o600});}
function call(program,args,{input,timeout=90000,optional=false}={}){const r=spawnSync(program,args,{input,encoding:'utf8',timeout,maxBuffer:4194304,windowsHide:true});if((r.error||r.status!==0)&&!optional){save(path.join(priv,'capacity-archive-command-'+crypto.randomUUID()+'.json'),{status:r.status,errorCode:r.error?.code||null,stdout:r.stdout||'',stderr:r.stderr||''});throw Error('COMMAND_FAILED');}return r;}
const docker=(args,o)=>call('docker.exe',args,o),local=(a,o)=>call(process.execPath,[path.join(root,'tools/local_trust.mjs'),a],o);
const compose=(args,o,metadata=false)=>docker(['compose','--env-file',env,'--project-name',project,'--file',base,...(metadata?['--file',metadataOverride]:[]),...args],o);
function mac(v){const keys=json(path.join(priv,'credentials.json')).credentials.filter(x=>x.role==='recovery');ensure(keys.length===1,'OPERATOR_KEY');return crypto.createHmac('sha256',Buffer.from(keys[0].secret,'hex')).update(stable(v)).digest('hex');}
function verifyEnvelope(file){const v=json(file);ensure(v.signature===mac(v.payload),'SIGNATURE_INVALID');return v;}
function verifySources(m){for(const f of m.sourceFiles)for(const dir of [path.join(root,'trust'),m.sourceDirectory])ensure(sha(read(path.join(dir,f.path)))===f.sha256,'SOURCE_DRIFT');for(const [f,h]of Object.entries(m.configHashes))ensure(sha(read(path.join(root,f)))===h,'CONFIG_DRIFT');}
function inspectDb(m){const v=JSON.parse(docker(['inspect',project+'-db']).stdout)[0],h=v.HostConfig;ensure(v.State.Running&&v.Image===m.images.postgres&&v.Config.Labels?.['nestakada.scope']==='trust-test'&&v.Config.Labels?.['com.docker.compose.project']===project&&h.ReadonlyRootfs&&h.Memory===536870912&&h.MemorySwap===536870912&&h.NanoCpus===500000000&&h.PidsLimit===128&&!Object.values(v.NetworkSettings.Ports||{}).some(x=>x?.length),'DB_SCOPE');return v.Id;}
function query(sql){const r=docker(['exec','--user','999:999','--env','PGCONNECT_TIMEOUT=3','--env','PGOPTIONS=-c statement_timeout=5000',project+'-db','psql','-X','-w','-U','postgres','-q','-A','-t','-v','ON_ERROR_STOP=1','-d','estakada_trust','-c',sql]);return JSON.parse(r.stdout.trim());}
function catalog(){return query(`SELECT json_build_object('unit',(SELECT json_build_object('oid',oid,'allow',datallowconn) FROM pg_database WHERE datname='${unit}'),'archive',(SELECT json_build_object('oid',oid,'allow',datallowconn) FROM pg_database WHERE datname='${archive}'))`);}
function holders(){return query(`SELECT coalesce(json_agg(pid),'[]'::json) FROM pg_stat_activity WHERE application_name='${appName}' AND datname='${unit}' AND usename='postgres' AND backend_type='client backend' AND query='SELECT pg_sleep(40)'`);}
function cancel(pid){ensure(Number.isSafeInteger(pid)&&pid>0,'HOLDER_PID');return query(`SELECT coalesce(json_agg(pg_cancel_backend(pid)),'[]'::json) FROM pg_stat_activity WHERE pid=${pid} AND application_name='${appName}' AND datname='${unit}' AND usename='postgres' AND backend_type='client backend' AND query='SELECT pg_sleep(40)'`);}
function probe(action,reference,label){const source=read(path.join(root,'tools/trust_archive_capacity.py')).toString();const launcher="import sys,json\nv=json.loads(sys.stdin.buffer.readline(1048577));ns={'__name__':'__main__','ARG':v['arg']};exec(compile(v['source'],'capacity-archive','exec'),ns)";
 const r=compose(['--profile','tools','run','--rm','--no-deps','-T','init','python','-B','-c',launcher],{optional:true,timeout:150000,input:JSON.stringify({source,arg:{action,reference}})+'\n'},true);
 save(path.join(priv,'capacity-archive-'+(resumePreflight?'resume-001-':'')+label+'.json'),{status:r.status,errorCode:r.error?.code||null,signal:r.signal||null,stdout:r.stdout||'',stderr:r.stderr||''});return r;}
function parsed(r){ensure(!r.error,'PROBE_TRANSPORT_FAILED');let v;try{v=JSON.parse(r.stdout);}catch{throw Error('PROBE_RESULT_MISSING');}return v;}
function pass(r){const v=parsed(r);ensure(r.status===0&&v.status==='PASS','PROBE_FAILED');return v;}
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let report={status:'FAIL',scope:'WB15-004-capacity-preservation-not-regression-PASS',dropPerformed:false,mainAdmission:false},started=false,reserved=false,holder=null,holderDone=null,holderPid=null;
async function releaseHolder(){if(!holder)return;const ids=holders();ensure(ids.length<=1,'HOLDER_NOT_UNIQUE');if(holderPid===null&&ids.length===1)holderPid=ids[0];if(ids.length){ensure(ids[0]===holderPid,'HOLDER_ID_CHANGED');const result=cancel(holderPid);ensure(result.length===1&&result[0]===true,'HOLDER_CANCEL_FAILED');}await Promise.race([holderDone,new Promise((_,reject)=>setTimeout(()=>reject(Error('HOLDER_REAP_TIMEOUT')),5000))]);report.holderReaped=true;holder=null;}
try{
 ensure(process.argv.length===2||resumePreflight,'ARGUMENTS');for(const name of Object.keys(process.env))ensure(!name.startsWith('TRUST_'),'INHERITED_OVERRIDE');
 const gate=json(path.join(out,'review-gate.json'));ensure(gate.status==='APPROVED'&&gate.authority==='D-380'&&gate.files.length>=4,'REVIEW_REQUIRED');for(const f of gate.files)ensure(sha(read(path.join(root,f.path)))===f.sha256,'REVIEW_DRIFT');
 ensure(!fs.existsSync(path.join(runtime,'archive-capacity.json'))&&!fs.existsSync(path.join(runtime,'capacity-archive-intent.json')),'ALREADY_ATTEMPTED');
 if(resumePreflight){const parentFile=path.join(rootOut,'archive-report.json'),rawFile=path.join(priv,'capacity-archive-inspect-before.json'),parent=json(parentFile),raw=json(rawFile),failure=JSON.parse(raw.stdout);ensure(parent.status==='FAIL'&&parent.errorCode==='PROBE_FAILED'&&parent.finalStatus?.actualRunningContainers===0&&parent.finalStatus.manifestActive===false&&raw.status===1&&failure.status==='FAIL'&&failure.errorClass==='ModuleNotFoundError'&&failure.stage==='REFERENCE_VALIDATION'&&failure.catalogMutationAttempted===false&&failure.journalRowWrites===false,'PREFLIGHT_PARENT_UNSAFE');report.resume={id:'resume-001',parentReportSha256:sha(read(parentFile)),parentRawSha256:sha(read(rawFile)),reason:'readonly-model-source-mount-missing'};}
 const old=json(path.join(runtime,'manifest.json'));ensure(!old.active&&read(path.join(priv,'write-profile.json')).toString().trim()==='{}','CLOSED_REQUIRED');
 for(const f of old.sourceFiles)for(const dir of [path.join(root,'trust'),old.sourceDirectory])ensure(sha(read(path.join(dir,f.path)))===f.sha256,'OLD_SOURCE_DRIFT');
 ensure(old.sourceSha256==='5fbcb9d9ea04ee58853b9b8d9fe2131fc6b0d1122f087239f3c66bfded768986','SOURCE_COHORT');
 const legacy=verifyEnvelope(path.join(runtime,'archive-unit.json'));ensure(legacy.payload.scope==='DEV15-WP-ARCHIVE'&&legacy.payload.report.freshUnitOid===32563,'LEGACY_LINEAGE');
 for(const file of ['capacity-attempt.json','capacity-resume-001.json','capacity-phase-a.json','capacity-phase-a-checkpoint.json','capacity-phase-b.json','capacity-tls-intent.json','capacity-tls-resume-001.json','capacity-tls-resume-002.json','capacity-tls-resume-003.json','capacity-tls-resume-004.json'])verifyEnvelope(path.join(runtime,file));
 fs.closeSync(fs.openSync(path.join(out,'archive-report.json'),'wx',0o600));reserved=true;started=true;
 local('Start',{timeout:180000});const m=json(path.join(runtime,'manifest.json'));verifySources(m);ensure(m.sourceSha256===old.sourceSha256,'SOURCE_CHANGED');compose(['stop','--timeout','3','api','ingress']);report.dbId=inspectDb(m);
 const input={intentId:crypto.randomUUID(),sourceSha256:m.sourceSha256,legacyState:legacy.payload.report.state};
 const inspected=pass(probe('inspect',input,'inspect-before'));report.before=inspected;const reference=inspected.reference;
 ensure(reference.unit.oid===32563&&reference.unit.stateV2Sha256==='116bb54a5d5d8cc5aa2ff6a4b593c51202aece6accff2421c47b525b9cc4c6b7'&&reference.main.stateV2Sha256==='dfdf4021db5dba1b807699b548e4370488fb3582e9c87734206f8f91ee3c6066','INSPECT_COHORT');
 const intent={scope:'DEV15-CAPACITY-ARCHIVE-INTENT',authority:'D-380',incarnation:m.incarnation,reference,sourceSha256:m.sourceSha256,sourceDirectory:m.sourceDirectory,sourceFiles:m.sourceFiles,legacyReceiptSha256:sha(read(path.join(runtime,'archive-unit.json'))),phaseBReceiptSha256:sha(read(path.join(runtime,'capacity-phase-b.json'))),helperSha256:sha(read(path.join(root,'tools/trust_archive_capacity.py'))),controllerSha256:sha(read(fileURLToPath(import.meta.url))),reviewGateSha256:sha(read(path.join(out,'review-gate.json'))),resume:report.resume||null};
 save(path.join(runtime,'capacity-archive-intent.json'),{payload:intent,signature:mac(intent)});
 const beforeCatalog=catalog(),bad=structuredClone(reference);bad.unit.oid=32564;
 const wrong=probe('archive',bad,'wrong-oid'),wrongResult=parsed(wrong);ensure(wrong.status===1&&wrongResult.status==='FAIL'&&wrongResult.errorCode==='CAP_ARCHIVE_EXPECTED_OID','WRONG_OID_NOT_REFUSED');ensure(stable(catalog())===stable(beforeCatalog),'WRONG_OID_MUTATED_CATALOG');report.wrongOidRefused=true;
 ensure(holders().length===0,'HOLDER_ALREADY_EXISTS');let holderOutput='',holderError='';
 holder=spawn('docker.exe',['exec','--user','999:999','--env','PGAPPNAME='+appName,project+'-db','psql','-X','-w','-U','postgres','-d',unit,'-c','SELECT pg_sleep(40)'],{windowsHide:true,stdio:['ignore','pipe','pipe']});
 holderDone=new Promise(resolve=>{holder.once('error',()=>resolve('SPAWN_ERROR'));holder.once('close',code=>resolve(code));});holder.stdout.on('data',b=>{holderOutput+=b.toString();});holder.stderr.on('data',b=>{holderError+=b.toString();});
 for(let n=0;n<30;n++){const ids=holders();ensure(ids.length<=1,'HOLDER_NOT_UNIQUE');if(ids.length===1){holderPid=ids[0];break;}await delay(100);}ensure(holderPid!==null,'HOLDER_NOT_READY');
 const active=probe('archive',reference,'active-session'),activeResult=parsed(active);ensure(active.status===1&&activeResult.status==='FAIL'&&activeResult.errorCode==='CAP_ARCHIVE_ACTIVE_SESSION','ACTIVE_SESSION_NOT_REFUSED');ensure(stable(catalog())===stable(beforeCatalog),'ACTIVE_SESSION_MUTATED_CATALOG');report.activeSessionRefused=true;
 await releaseHolder();save(path.join(priv,'capacity-archive-holder.json'),{stdout:holderOutput,stderr:holderError});
 const afterNegative=pass(probe('inspect',input,'inspect-after-negative'));ensure(stable(afterNegative.reference)===stable(reference),'NEGATIVE_CHANGED_STATE');report.negativeStatePreserved=true;
 const ack=probe('archive',reference,'archive-ack-not-consumed');ensure(!ack.error&&ack.status===0,'ARCHIVE_COMMAND_FAILED');report.archiveAckConsumedBeforeRecovery=false;
 const recovered=pass(probe('recover',reference,'recover'));report.recovered=recovered;ensure(stable(parsed(ack))===stable(recovered),'RECOVER_CHANGED_RESULT');report.archiveAckMatchesRecovery=true;
 ensure(recovered.archiveName===archive&&recovered.unitState.oid===32563&&recovered.freshUnitOid!==32563&&recovered.freshUnitOid!==legacy.payload.report.state.oid&&recovered.archivesClosed===true&&recovered.dropPerformed===false&&recovered.sameRowsDigest===true&&recovered.sameArchiveOid===true,'ARCHIVE_PROOF_INVALID');
 const verified=pass(probe('verify',recovered,'verify-before-init'));ensure(stable(verified)===stable(recovered),'VERIFY_CHANGED_RESULT');
 const payload={scope:'DEV15-CAPACITY-ARCHIVE',authority:'D-380',incarnation:m.incarnation,intentSha256:sha(read(path.join(runtime,'capacity-archive-intent.json'))),legacyReceiptSha256:intent.legacyReceiptSha256,sourceSha256:m.sourceSha256,sourceDirectory:m.sourceDirectory,sourceFiles:m.sourceFiles,report:recovered};
 save(path.join(runtime,'archive-capacity.json'),{payload,signature:mac(payload)});report.signedReceiptSaved=true;
 compose(['--profile','tools','run','--rm','--no-deps','init']);const final=pass(probe('verify',recovered,'verify-after-init'));ensure(stable(final)===stable(recovered),'INIT_CHANGED_ARCHIVES');report.after=final;
 ensure(sha(read(path.join(runtime,'archive-unit.json')))===intent.legacyReceiptSha256,'LEGACY_RECEIPT_CHANGED');verifySources(m);report.sourceDrift=0;report.status='PASS';
}catch(e){report.errorCode=/^[A-Z0-9_]+$/.test(e?.message||'')?e.message:'CAPACITY_ARCHIVE_FAILED';}
finally{
 if(holder){try{await releaseHolder();}catch{report.status='FAIL';report.cleanupError='HOLDER_CLEANUP_FAILED';}}
 if(started){try{local('Stop');report.finalStatus=JSON.parse(local('Status').stdout);ensure(report.finalStatus.actualRunningContainers===0&&!report.finalStatus.manifestActive,'FINAL_NOT_CLOSED');}catch{report.status='FAIL';report.cleanupError='STOP_FAILED';}}
 if(reserved)fs.writeFileSync(path.join(out,'archive-report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:report.status,errorCode:report.errorCode||null}));if(report.status!=='PASS')process.exitCode=1;
}
