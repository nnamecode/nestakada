// D-391 / RL15-006..010. Finite synthetic native checks; never issue a lease.
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const out=path.join(root,'work/dev15-lease-20261102'),priv=path.join(root,'work/dev15-20261102/private');
const project='nestakada-trust-test',runId=process.argv[2],sourceFile=fileURLToPath(import.meta.url),eventId=crypto.randomUUID();
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const stable=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a<b?-1:a>b?1:0)):x);
const ensure=(ok,code)=>{if(!ok)throw Error(code);};
function inside(p){const full=path.resolve(p);ensure(full.startsWith(root+path.sep),'FAULT_PATH_SCOPE');for(let x=full;x!==root;x=path.dirname(x))if(fs.existsSync(x))ensure(!fs.lstatSync(x).isSymbolicLink(),'FAULT_LINK');return full;}
function read(p){inside(p);ensure(fs.lstatSync(p).isFile()&&fs.statSync(p).size<=4194304,'FAULT_INPUT_BOUND');return fs.readFileSync(p);}
const json=p=>JSON.parse(read(p));
function save(p,value){const bytes=Buffer.from(stable(value)+'\n');ensure(bytes.length<=524288,'FAULT_OUTPUT_BOUND');fs.writeFileSync(inside(p),bytes,{flag:'wx',mode:0o600});}
function command(program,args,{input,timeout=35000}={}){return spawnSync(program,args,{input,encoding:'utf8',windowsHide:true,timeout,maxBuffer:524288});}
const localDocker=(args,options)=>command('docker.exe',['--context','desktop-linux',...args],options);
function docker(args,options){const r=localDocker(args,options);ensure(!r.error&&r.status===0,'FAULT_DOCKER_FAILED');return r.stdout;}
const launcher="import json,sys\nv=json.load(sys.stdin);ns={'__name__':'__main__','ARG':v['arg']};exec(compile(v['source'],'native-fault-check','exec'),ns)";
let policy,lease,expected,apiId,verifiedOwner=false,cleanupTrusted=false,validRunId=false,mutatingMayHaveBeenSent=false,currentStep='initial',reportPath,planPath;
const report={status:'FAIL',scope:'one-synthetic-operation-native-lost-body-and-partial-checks',runId,checks:[],cleanupErrors:[],fullRP15Coverage:false};
function signed(p){const e=json(p),key=json(path.join(priv,'credentials.json')).credentials.filter(x=>x.role==='recovery');ensure(key.length===1&&e.signature===crypto.createHmac('sha256',Buffer.from(key[0].secret,'hex')).update(stable(e.payload)).digest('hex'),'FAULT_SIGNATURE');return e.payload;}
function currentApi(){const v=JSON.parse(docker(['inspect',project+'-api']))[0],h=v.HostConfig,env=Object.fromEntries(v.Config.Env.map(x=>{const n=x.indexOf('=');return[x.slice(0,n),x.slice(n+1)];}));
 ensure(/^[a-f0-9]{64}$/.test(v.Id)&&v.Id===apiId&&v.State.Running&&v.Name==='/'+project+'-api'&&v.Config.Labels?.['nestakada.scope']==='trust-test'&&v.Config.Labels?.['com.docker.compose.project']===project&&v.Config.Labels?.['com.docker.compose.service']==='api','FAULT_API_IDENTITY');
 ensure(h.Memory===268435456&&h.MemorySwap===268435456&&h.NanoCpus===500000000&&h.PidsLimit===64&&h.ReadonlyRootfs&&!Object.values(v.NetworkSettings.Ports||{}).some(x=>x?.length)&&env.TRUST_RUNTIME_ID===runId&&env.TRUST_WRITE_PROFILE==='local-bounded-writer'&&env.TRUST_DB_NAME==='estakada_trust','FAULT_API_CONTEXT');
 ensure(v.Image===json(path.join(root,'work/dev15-20261102/runtime/manifest.json')).images['python-runtime']&&v.Config.User==='10001:10001'&&!h.Privileged&&h.CapDrop?.includes('ALL')&&h.SecurityOpt?.some(x=>x.startsWith('no-new-privileges'))&&stable(Object.keys(v.NetworkSettings.Networks).sort())===stable([project+'-api',project+'-db'])&&v.Mounts.every(x=>x.Type==='tmpfs'||x.Type==='bind'&&!x.RW),'FAULT_API_BOUNDARY');
 const payload=signed(path.join(priv,'write-profile.json'));ensure(payload.lease.runtimeId===runId&&payload.lease.exclusion.newContainerId===apiId&&stable(payload.policy)===stable(policy),'FAULT_LEASE_CHANGED');return v;
}
function probe(file,arg,label){currentApi();const r=localDocker(['exec','-i','--user','10001:10001',apiId,'python','-B','-c',launcher],{input:JSON.stringify({source:read(path.join(root,file)).toString(),arg})});
 save(path.join(priv,'native-'+runId+'-'+label+'-transport.json'),{exitCode:r.status,error:r.error?.code||null,stdout:r.stdout||'',stderr:r.stderr||''});
 ensure(!r.error&&r.status===0,'FAULT_PROBE_FAILED');const value=JSON.parse(r.stdout);ensure(value.status==='PASS','FAULT_PROBE_REJECTED');return value;
}
const leaseProbe=(action,request=null,admission=null,label)=>probe('tools/trust_runtime_lease_probe.py',{action,expected,request,admission},label);
const snapshot=label=>leaseProbe('snapshot',null,null,label).snapshot;
function request(pathValue,body,credentialId,label){const value=leaseProbe('request',{path:pathValue,body,credentialId},null,label).request;ensure(value&&value.statusCode===200&&String(value.headers.cacheControl).includes('no-store')&&value.headers.setCookiePresent===false,'FAULT_HTTP_RESPONSE');return value.body;}
function check(id,ok){ensure(ok,'FAULT_'+id.toUpperCase().replaceAll('-','_'));report.checks.push({id,status:'PASS'});}
function sameState(a,b){return a.stateDigest===b.stateDigest&&stable(a.head)===stable(b.head)&&stable(a.rows)===stable(b.rows)&&stable(a.counts)===stable(b.counts);}
try{
 ensure(process.argv.length===3&&/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(runId),'FAULT_RUN_UUID');validRunId=true;reportPath=path.join(out,'fault-'+runId+'-'+eventId+'-report.json');for(const k of Object.keys(process.env))ensure(!k.startsWith('TRUST_'),'FAULT_INHERITED_ENV');
 const gate=json(path.join(out,'fault-review-gate.json'));ensure(gate.status==='APPROVED'&&gate.authority==='D-391'&&Array.isArray(gate.files),'FAULT_CODE_GATE');
 const cleanupRow=gate.files.filter(x=>x.path==='tools/lease-trust-runtime.mjs');ensure(cleanupRow.length===1&&sha(read(path.join(root,cleanupRow[0].path)))===cleanupRow[0].sha256,'FAULT_CLEANUP_CONTROLLER_UNVERIFIED');cleanupTrusted=true;
 const required=new Set(['tools/test-trust-runtime-faults.mjs','tools/lease-trust-runtime.mjs','tools/trust_runtime_lease_probe.py','tools/trust_runtime_fault_probe.py']);
 for(const row of gate.files){ensure(sha(read(path.join(root,row.path)))===row.sha256,'FAULT_GATE_DRIFT');required.delete(row.path);}ensure(!required.size,'FAULT_GATE_INCOMPLETE');
 const context=JSON.parse(docker(['context','inspect','desktop-linux']));ensure(context.length===1&&context[0].Name==='desktop-linux'&&context[0].Endpoints.docker.Host==='npipe:////./pipe/dockerDesktopLinuxEngine','FAULT_LOCAL_DOCKER_CONTEXT');
 const payload=signed(path.join(priv,'write-profile.json'));policy=payload.policy;lease=payload.lease;ensure(payload.schemaVersion===2&&payload.scope==='LOCAL_TRUST_BOUNDED_WRITER'&&lease.runtimeId===runId&&lease.policyDigest===sha(stable(policy))&&lease.recoveryActions.length===0&&lease.reconciliation===null,'FAULT_LEASE_SCOPE');
 const adoptedFile=path.join(root,'work/dev15-admission-20261102/final-result.json');ensure(sha(read(adoptedFile))==='e102802ba61030558670a30deb109909b80193e6e9eda212343387a9619d026c','FAULT_ADOPTED_BASELINE_SHA');const adopted=json(adoptedFile);const prepared=signed(path.join(root,'work/dev15-admission-20261102/prepared-state.json'));
 ensure(policy.policyId===prepared.policyId&&lease.policyDigest===prepared.policyDigest&&policy.dbName==='estakada_trust'&&policy.epoch==='1','FAULT_POLICY_SCOPE');
 apiId=lease.exclusion.newContainerId;currentApi();verifiedOwner=true;
 expected={database:'estakada_trust',oid:16384,incarnation:policy.incarnation,sourceFingerprint:policy.sourceFingerprint,schemaFingerprint:policy.schemaFingerprint,policyId:policy.policyId,policyDigest:lease.policyDigest,runtimeId:runId};
 planPath=path.join(priv,'native-'+runId+'-plan.json');ensure(!fs.existsSync(planPath),'FAULT_PLAN_EXISTS_RECONCILE_REQUIRED');
 currentStep='baseline';const before=snapshot('baseline');ensure(before.stateDigest===adopted.afterStateDigest&&before.head.generation===10&&before.head.writer_epoch===2&&before.counts.AdmissionPolicy===1,'FAULT_INITIAL_STATE_CHANGED');
 const bindings=before.credentialBindings,keys=json(path.join(priv,'credentials.json')).credentials;
 const writer=bindings.filter(x=>x.role==='writer'&&x.active&&x.writer_epoch===before.head.writer_epoch),reader=bindings.filter(x=>x.role==='reader'&&x.active);
 ensure(writer.length===1&&reader.length===1&&keys.some(x=>x.id===writer[0].id&&x.role==='writer')&&keys.some(x=>x.id===reader[0].id&&x.role==='reader'),'FAULT_ACTIVE_BINDINGS');
 const nonce=crypto.randomUUID(),operationId=crypto.randomUUID(),objectId=crypto.randomUUID(),partialId=crypto.randomUUID(),partialObjectId=crypto.randomUUID(),target='/dev15-runtime/'+nonce+'/restriction/';
 ensure(!Object.hasOwn(before.rows.Operation,operationId)&&!Object.hasOwn(before.rows.Operation,partialId)&&!Object.hasOwn(before.rows.RoutePolicy,sha(target))&&!(before.head.permitted_operations||[]).includes(operationId),'FAULT_SYNTHETIC_ID_NOT_FRESH_OR_TRIAL_MEMBER');
 const common={incarnation:policy.incarnation,writerEpoch:String(before.head.writer_epoch)};
 const prepare={...common,operationId,expectedGeneration:'10',kind:'route_restriction',objectId,basis:sha('synthetic-'+nonce),policies:[{target,objectId,policy:'DELETED',redirectTarget:null}],requestIds:[]};
 const unknown={...common,operationId,expectedGeneration:'11',outcome:'unknown',mainIncarnation:null,mainReceipt:null,policies:[]};
 const terminal={...common,operationId,expectedGeneration:'12',outcome:'committed',mainIncarnation:policy.incarnation,mainReceipt:sha('synthetic-main-'+operationId),policies:prepare.policies};
 const partial={...prepare,operationId:partialId,objectId:partialObjectId,expectedGeneration:'13',policies:[{target:'/dev15-runtime/'+nonce+'/partial/',objectId:partialObjectId,policy:'DELETED',redirectTarget:null}]};
 const plan={scope:'LOCAL_TRUST_SYNTHETIC_NATIVE_FAULTS',authority:'D-391',runId,apiId,sourceSha256:sha(read(sourceFile)),writerId:writer[0].id,readerId:reader[0].id,before,bodies:{prepare,unknown,terminal,partial},syntheticMainReceipt:true};
 save(planPath,plan);report.planSha256=sha(read(planPath));report.baselineStateDigest=before.stateDigest;
 const size=Buffer.byteLength(stable(prepare))+4096,reserve=Buffer.byteLength(stable(prepare.policies))+8192;
 currentStep='prepare';mutatingMayHaveBeenSent=true;const first=request('/v1/prepare',prepare,writer[0].id,'prepare');
 check('RL15-006-prepare-new-uuid',first.ok===true&&first.replay===false&&first.head.generation==='11'&&first.stage==='PENDING_DENY');
 const afterPrepare=snapshot('after-prepare');check('RL15-009-prepare-accounting',afterPrepare.head.logical_bytes===before.head.logical_bytes+size&&afterPrepare.head.reserved_bytes===before.head.reserved_bytes+reserve);
 for(const [body,which,generation]of [[unknown,'unknown-lost-body',12],[terminal,'terminal-lost-body',13]]){
  currentStep=which;const witness=probe('tools/trust_runtime_fault_probe.py',{case:which,credentialId:writer[0].id,body,intentSha256:sha(stable(body))},which);
  check(which==='unknown-lost-body'?'RL15-006-unknown-lost-body':'RL15-007-terminal-lost-body',witness.fullRequestSent===true&&witness.lostResponseBodyWitness===true&&witness.responseBodyConsumed===false&&witness.after.head.generation===String(generation));
  const status=request('/v1/operations/'+operationId,null,reader[0].id,which+'-status');ensure(status.operation?.operationId===operationId&&status.operation.phases[body.outcome],'FAULT_PHASE_STATUS');
  const beforeReplay=snapshot(which+'-before-replay');const replay=request('/v1/report-result',body,writer[0].id,which+'-replay');const afterReplay=snapshot(which+'-after-replay');
  check(which==='unknown-lost-body'?'RL15-006-unknown-exact-replay':'RL15-007-terminal-exact-replay',replay.replay===true&&stable(replay.phaseReceipt)===stable(status.operation.phases[body.outcome].receipt)&&sameState(beforeReplay,afterReplay));
 }
 currentStep='partial-prepare';const beforePartial=snapshot('before-partial');const partialWitness=probe('tools/trust_runtime_fault_probe.py',{case:'partial-prepare',credentialId:writer[0].id,body:partial,intentSha256:sha(stable(partial))},'partial-prepare');
 const after=snapshot('after-partial');check('RL15-008-client-partial-no-mutation',partialWitness.partialRequestSent===true&&partialWitness.fullRequestSent===false&&sameState(beforePartial,after));
 const allowed={Operation:new Set([operationId]),RoutePolicy:new Set([sha(target)])};
 for(const [model,rows]of Object.entries(before.rows)){
  ensure(after.rows[model]&&Object.entries(rows).every(([pk,h])=>after.rows[model][pk]===h),'FAULT_LEGACY_ROW_CHANGED');
  const extras=Object.keys(after.rows[model]).filter(pk=>!Object.hasOwn(rows,pk));ensure(extras.every(pk=>allowed[model]?.has(pk)),'FAULT_UNEXPECTED_NEW_ROW');
 }
 for(const [key,value]of Object.entries(before.head))if(!['generation','digest','logical_bytes','reserved_bytes'].includes(key))ensure(stable(after.head[key])===stable(value),'FAULT_PROTECTED_HEAD_CHANGED');
 check('RL15-009-legacy-and-policy-preserved',stable(after.policy)===stable(before.policy)&&after.counts.Operation===before.counts.Operation+1&&after.counts.RoutePolicy===before.counts.RoutePolicy+1&&after.head.generation===13);
 check('RL15-009-completion-accounting',after.head.logical_bytes===before.head.logical_bytes+size+reserve&&after.head.reserved_bytes===before.head.reserved_bytes&&after.operationAccounting[operationId].logical_bytes===size+reserve&&after.operationAccounting[operationId].reserve_bytes===0);
 report.status='PASS';report.afterStateDigest=after.stateDigest;report.headGeneration=after.head.generation;report.policyRows=after.counts.AdmissionPolicy;report.legacyReserveBytes=after.head.reserved_bytes;report.newOperationId=operationId;report.newRouteKey=sha(target);report.fullRP15Coverage=false;
}catch(error){report.errorCode=/^[A-Z0-9_]{1,100}$/.test(error?.message||'')?error.message:'FAULT_CONTROLLER_FAILED';report.failedStep=currentStep;report.outcome=mutatingMayHaveBeenSent?'RECONCILE_SAVED_PLAN_AND_STATUS_BEFORE_ANY_RETRY':'NOT_SENT';}
finally{
 if(validRunId&&cleanupTrusted){const stop=command(process.execPath,[path.join(root,'tools/lease-trust-runtime.mjs'),'Stop',runId],{timeout:90000});
  try{save(path.join(priv,'native-'+runId+'-stop-result.json'),{status:stop.status,error:stop.error?.code||null,stdout:stop.stdout||'',stderr:stop.stderr||''});}catch{report.status='FAIL';report.cleanupErrors.push('STOP_EVIDENCE_INCOMPLETE');}
  try{ensure(!stop.error&&stop.status===0&&JSON.parse(stop.stdout).status==='PASS','FAULT_STOP_RESULT');const ps=localDocker(['ps','-aq','--no-trunc','--filter','label=com.docker.compose.project='+project],{timeout:15000});ensure(!ps.error&&ps.status===0&&!ps.stdout.trim()&&read(path.join(priv,'write-profile.json')).toString().trim()==='{}','FAULT_STOP_NOT_CLOSED');report.ownedContainersIncludingStopped=0;report.permitEmpty=true;}catch{report.status='FAIL';report.cleanupErrors.push('LEASE_STOP_NOT_PROVEN_NO_AUTOMATIC_RETRY');}
 }else if(validRunId){report.status='FAIL';report.cleanupErrors.push('LEASE_STOP_NOT_PROVEN_TRUSTED_CONTROLLER_UNVERIFIED');}
 if(reportPath){save(reportPath,report);}
 console.log(JSON.stringify({status:report.status,runId,reportPath:reportPath?path.relative(root,reportPath).replaceAll('\\','/'):null,errorCode:report.errorCode||null,checks:report.checks.length,cleanupErrors:report.cleanupErrors,fullRP15Coverage:false}));if(report.status!=='PASS')process.exitCode=1;
}
