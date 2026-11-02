// D-376 / WP15-003..013. Closed, one-shot local synthetic experiment.
// No public target, image pull, database reset or arbitrary command input.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const task=path.join(repo,'work/dev15-20261102'),runtime=path.join(task,'runtime'),privateDir=path.join(task,'private');
const out=path.join(repo,'work/dev15-write-20261102'),project='nestakada-trust-test';
const envFile=path.join(runtime,'compose.env'),manifestFile=path.join(runtime,'manifest.json');
const composeFile=path.join(repo,'environment/trust/compose.yaml');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const stable=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a<b?-1:a>b?1:0)):x);
const hash=v=>sha(stable(v)),ensure=(ok,code)=>{if(!ok)throw Error(code);};
function checked(file){const full=path.resolve(file);ensure(full.startsWith(repo+path.sep),'PATH_SCOPE');for(let p=full;p!==repo;p=path.dirname(p))if(fs.existsSync(p))ensure(!fs.lstatSync(p).isSymbolicLink(),'LINK_REJECTED');return full;}
function read(file){checked(file);ensure(fs.lstatSync(file).isFile(),'REGULAR_FILE_REQUIRED');return fs.readFileSync(file);}
const json=file=>JSON.parse(read(file));
function write(file,data,exclusive=false){fs.writeFileSync(checked(file),typeof data==='string'?data:JSON.stringify(data,null,2)+'\n',{flag:exclusive?'wx':'w',mode:0o600});}
function docker(args,{input,timeout=30000,optional=false}={}){
 const r=spawnSync('docker.exe',args,{input,encoding:'utf8',timeout,maxBuffer:4*1024*1024,windowsHide:true});
 if(r.error||r.status!==0){write(path.join(privateDir,'write-failure-'+crypto.randomUUID()+'.txt'),String(r.stdout||'')+'\n'+String(r.stderr||''),true);if(!optional)throw Error('OWNED_DOCKER_COMMAND_FAILED');}
 return r;
}
const compose=(args,options)=>docker(['compose','--env-file',envFile,'--project-name',project,'--file',composeFile,...args],options);
function local(action){const r=spawnSync('node.exe',[path.join(repo,'tools/local_trust.mjs'),action],{encoding:'utf8',timeout:180000,maxBuffer:1048576,windowsHide:true});if(r.error||r.status!==0){write(path.join(privateDir,'write-local-'+crypto.randomUUID()+'.txt'),String(r.stdout||'')+'\n'+String(r.stderr||''),true);throw Error('LOCAL_ACTION_FAILED');}return r.stdout;}
function inspect(kind){const v=JSON.parse(docker(['inspect',project+'-'+kind]).stdout)[0];ensure(v.Config.Labels?.['nestakada.scope']==='trust-test'&&v.Config.Labels?.['com.docker.compose.project']===project&&v.Config.Labels?.['com.docker.compose.service']===kind,'OWNERSHIP');return v;}
function caps(){const result={};for(const [kind,limits]of Object.entries({api:[268435456,500000000,64],db:[536870912,500000000,128],ingress:[134217728,250000000,64]})){const v=inspect(kind),c=v.HostConfig;ensure(v.State.Running&&c.ReadonlyRootfs&&c.Memory===limits[0]&&c.MemorySwap===limits[0]&&c.NanoCpus===limits[1]&&c.PidsLimit===limits[2]&&!Object.values(v.NetworkSettings.Ports||{}).some(x=>x?.length),'RESOURCE_CAPS');ensure(v.Image===m.images[{api:'python-runtime',db:'postgres',ingress:'local-ingress'}[kind]],'PINNED_IMAGE');for(const mount of v.Mounts)if(mount.Type==='bind')ensure(mount.RW===false,'READONLY_BINDS');result[kind]={id:v.Id,image:v.Image,memoryBytes:c.Memory,nanoCpus:c.NanoCpus,pids:c.PidsLimit};}
 for(const name of ['client','api','db'])ensure(JSON.parse(docker(['network','inspect',project+'-'+name]).stdout)[0].Internal,'INTERNAL_NETWORK');return result;}
function probe(action,arg={}){const launcher="import json,sys\nv=json.load(sys.stdin);ns={'__name__':'__main__','ACTION':v['action'],'ARG':v['arg']};exec(compile(v['source'],'write-probe','exec'),ns)";const r=docker(['exec','-i','--user','10001:10001',project+'-api','python','-B','-c',launcher],{input:JSON.stringify({source:read(path.join(repo,'tools/trust_write_probe.py')).toString('utf8'),action,arg}),timeout:15000});const v=JSON.parse(r.stdout);ensure(v.status==='PASS','PROBE_FAILED');return v;}
function waitReady(){for(let i=0;i<30;i++){const r=docker(['exec',project+'-api','python','-B','-c',"import socket;s=socket.create_connection(('127.0.0.1',8000),1);s.close()"],{optional:true,timeout:3000});if(r.status===0)return;Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,200);}throw Error('API_NOT_READY');}
function waitIngress(){for(let i=0;i<20;i++){const r=docker(['exec',project+'-api','python','-B','-c',"import socket,ssl;c=ssl.create_default_context(cafile='/run/secrets/ingress-ca');s=c.wrap_socket(socket.create_connection(('trust-ingress',8443),1),server_hostname='trust-ingress');s.close()"],{optional:true,timeout:3000});if(r.status===0)return;Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,200);}throw Error('INGRESS_NOT_READY');}
function request(credentialId,url,body=null,{code=200,error=null,dropBody=false}={}){write(path.join(privateDir,'write-intent-'+crypto.randomUUID()+'.json'),{credentialId,path:url,body,dropBody,expectedStatus:code,expectedCode:error},true);const r=probe('request',{credentialId,path:url,body,dropBody});ensure(r.httpStatus===code,'HTTP_STATUS_MISMATCH');if(error)ensure(r.response?.code===error,'HTTP_ERROR_MISMATCH');if(!error&&!dropBody)ensure(r.response?.workflowComplete!==true,'FALSE_WORKFLOW_COMPLETE');return r;}
function facts(){return probe('facts');}
function mode(value,runtimeId){let env=read(envFile).toString();ensure(/^TRUST_WRITE_MODE='[^']*'$/m.test(env)&&/^TRUST_RUNTIME_ID='[^']*'$/m.test(env),'ENV_SCOPE');env=env.replace(/^TRUST_WRITE_MODE='[^']*'$/m,"TRUST_WRITE_MODE='"+value+"'").replace(/^TRUST_RUNTIME_ID='[^']*'$/m,"TRUST_RUNTIME_ID='"+runtimeId+"'");write(envFile,env);const current=json(manifestFile);current.runtimeId=runtimeId;current.writeMode=value;write(manifestFile,current);}
function semantic(body,credential){return hash({principal:credential.principal,credential:credential.id,...Object.fromEntries(Object.entries(body).filter(([k])=>k!=='expectedGeneration'))});}
function descriptor(body,credential,phase){return{id:body.operationId||body.actionId,credentialId:credential.id,writerEpoch:body.writerEpoch,phase,fingerprint:semantic(body,credential)};}
function publish(payload,label){const recovery=keys.credentials.filter(x=>x.role==='recovery');ensure(recovery.length===1,'RECOVERY_KEY');const signature=crypto.createHmac('sha256',Buffer.from(recovery[0].secret,'hex')).update(stable(payload)).digest('hex');const envelope={payload,signature},raw=JSON.stringify(envelope,null,2)+'\n';ensure(Buffer.byteLength(raw)<=65536,'PERMIT_SIZE');write(path.join(privateDir,'write-envelope-'+payload.planId+'-'+label+'.json'),raw,true);write(path.join(privateDir,'write-profile.json'),raw);write(path.join(out,'permit-'+label+'-receipt.json'),{scope:'LOCAL_TRUST_TEST_ONLY',sha256:sha(raw),semanticSha256:hash(envelope),sourceFingerprint:payload.sourceFingerprint,schemaFingerprint:payload.schemaFingerprint,evidence:payload.evidence,planId:payload.planId,operations:payload.operationIds.length,recoveryActions:payload.recoveryActionIds.length},true);}
function recreate(runtimeId){mode('local-test-permit',runtimeId);compose(['up','-d','--no-build','--pull','never','--force-recreate','api']);waitReady();compose(['up','-d','--no-build','--pull','never','--force-recreate','ingress']);waitIngress();caps();}
function stopFront(){compose(['stop','--timeout','3','api','ingress']);ensure(!inspect('api').State.Running&&!inspect('ingress').State.Running,'OLD_API_NOT_EXCLUDED');}
function archiveEvidence(){const v=json(path.join(runtime,'archive-unit.json'));ensure(v.payload.scope==='DEV15-WP-ARCHIVE'&&v.payload.report.sameRowsDigest&&v.payload.report.sameArchiveOid,'ARCHIVE_EVIDENCE');return sha(read(path.join(runtime,'archive-unit.json')));}
function drift(){for(const [file,digest]of Object.entries(m.configHashes))ensure(sha(read(path.join(repo,file)))===digest,'CONFIG_DRIFT');for(const row of m.sourceFiles)ensure(sha(read(path.join(repo,'trust',row.path)))===row.sha256&&sha(read(path.join(m.sourceDirectory,row.path)))===row.sha256,'SOURCE_DRIFT');}
function bytes(root){let n=0;for(const e of fs.readdirSync(root,{withFileTypes:true})){const p=checked(path.join(root,e.name));ensure(!fs.lstatSync(p).isSymbolicLink(),'LINK_REJECTED');n+=e.isDirectory()?bytes(p):fs.statSync(p).size;}return n;}
let m,keys,reportFd=null,started=false,status='FAIL',errorCode=null,groups=[],firstFacts,finalFacts,resources,exclusionEvidence;
const check=(name,ok)=>{ensure(ok,'ASSERT_'+name);groups.push(name);};
try{
 ensure(process.argv.length===2,'NO_ARGUMENTS');for(const name of Object.keys(process.env))ensure(!name.startsWith('TRUST_'),'INHERITED_OVERRIDE');
 reportFd=fs.openSync(checked(path.join(out,'native-write-report.json')),'wx',0o600);
 const review=json(path.join(out,'native-review-gate.json'));ensure(review.status==='APPROVED'&&review.authority==='D-376','NATIVE_REVIEW_REQUIRED');
 for(const row of review.files)ensure(sha(read(path.join(repo,row.path)))===row.sha256,'REVIEW_SOURCE_DRIFT');
 const old=json(manifestFile);ensure(old.active===false&&old.initialized&&old.unitArchive,'PRESERVED_INITIAL_STATE');
 const unit=json(path.join(runtime,'unit-result-'+old.runId+'.json'));ensure(unit.status==='PASS'&&unit.tests===62&&unit.sourceSha256===old.sourceSha256,'CURRENT_62_UNIT_REQUIRED');
 const calibrationFile=path.join(runtime,'calibration-7e145c49-be90-478e-88fe-0aef34f0f3ab.json');ensure(json(calibrationFile).status==='PASS','CALIBRATION_REQUIRED');archiveEvidence();
 started=true;local('Start');m=json(manifestFile);ensure(m.sourceSha256===unit.sourceSha256,'UNIT_SOURCE_MISMATCH');resources=caps();
 keys=json(path.join(privateDir,'credentials.json'));const writer=keys.credentials.find(x=>x.id==='writer-1'&&x.role==='writer'),recovery=keys.credentials.find(x=>x.role==='recovery');ensure(writer&&recovery&&keys.credentials.length===3,'INITIAL_KEYS_REQUIRED');
 firstFacts=facts();drift();ensure(firstFacts.head.mode==='ACTIVE'&&firstFacts.head.writerEpoch==='1'&&firstFacts.counts.operations===0&&firstFacts.counts.recovery===0&&firstFacts.counts.routes===0&&firstFacts.counts.tombstones===0,'EMPTY_MAIN_REQUIRED');
 const planId=crypto.randomUUID(),opIds=Array.from({length:6},()=>crypto.randomUUID()),actionIds=Array.from({length:3},()=>crypto.randomUUID()),inc=m.incarnation;
 const newWriter={id:'writer-2',principal:'writer-local',role:'writer',secret:crypto.randomBytes(32).toString('hex')};
 const gen=()=>facts().head.generation;
 function prepare(index,epoch='1',kind='route_restriction'){const objectId=crypto.randomUUID();return{operationId:opIds[index],incarnation:inc,expectedGeneration:'0',writerEpoch:epoch,kind,objectId,basis:sha('synthetic-'+planId),policies:kind==='route_restriction'?[{target:'/dev15-synthetic/'+planId+'/'+index+'/',objectId,policy:'DELETED',redirectTarget:null}]:[],requestIds:kind==='request_tombstone'?[crypto.randomUUID()]:[]};}
 const a=prepare(0),b=prepare(1),c=prepare(2,'1','request_tombstone'),d=prepare(3,'2'),oldNegative=prepare(4,'2');
 function outcome(p,value){return{operationId:p.operationId,incarnation:inc,expectedGeneration:'0',writerEpoch:p.writerEpoch,outcome:value,mainIncarnation:value==='unknown'?null:inc,mainReceipt:value==='unknown'?null:sha('synthetic-main-'+p.operationId),policies:value==='committed'?p.policies:[]};}
 const unknown=outcome(a,'unknown'),terminal=outcome(a,'committed'),tombTerminal=outcome(c,'committed');
 const fence={actionId:actionIds[0],incarnation:inc,expectedGeneration:'0',writerEpoch:'1',scope:'LOCAL_TRUST_TEST_ONLY',previousCredentialId:writer.id,newCredentialId:null,fenceActionId:null,reconciliationDigest:null};
 const badActivate={actionId:actionIds[1],incarnation:inc,expectedGeneration:'0',writerEpoch:'2',scope:'LOCAL_TRUST_TEST_ONLY',previousCredentialId:writer.id,newCredentialId:newWriter.id,fenceActionId:fence.actionId,reconciliationDigest:sha('deliberately-unreconciled')};
 let requests=[...[a,b,c].map(x=>descriptor(x,writer,'prepare')),descriptor(unknown,writer,'unknown'),descriptor(terminal,writer,'committed'),descriptor(tombTerminal,writer,'committed'),descriptor(oldNegative,writer,'prepare'),descriptor(fence,recovery,'fence'),descriptor(badActivate,recovery,'activate')];
 let permit={schemaVersion:1,scope:'LOCAL_TRUST_TEST_ONLY',planId,dbName:'estakada_trust',incarnation:inc,protocolVersion:1,sourceFiles:firstFacts.sourceFiles,sourceFingerprint:firstFacts.sourceFingerprint,schemaFingerprint:firstFacts.schemaFingerprint,evidence:{unit:sha(read(path.join(runtime,'unit-result-'+old.runId+'.json'))),calibration:sha(read(calibrationFile)),review:sha(read(path.join(out,'native-review-gate.json')))},caps:{logicalBytes:67108864,completionBytes:16777216,maxOperations:16,maxRecoveryActions:4,maxMessageBytes:1048576,maxTargets:256},deployment:{api:{memoryBytes:268435456,nanoCpus:500000000,pids:64},db:{memoryBytes:536870912,nanoCpus:500000000,pids:128},ingress:{memoryBytes:134217728,nanoCpus:250000000,pids:64},configFingerprint:hash(m.configHashes),evidence:hash(resources)},operationIds:opIds,recoveryActionIds:actionIds,requests,runtimeId:m.runtimeId,credentialConfigSha256:sha(read(path.join(privateDir,'credentials.json'))),reconciliation:null};
 write(path.join(privateDir,'write-plan-'+planId+'.json'),{authority:'D-376',planId,opIds,actionIds,newWriter,initialCredentialConfig:keys,bodies:{a,b,c,d,oldNegative,unknown,terminal,tombTerminal,fence,badActivate},initialPermit:permit},true);
 request(writer.id,'/v1/prepare',a,{code:503,error:'WRITE_PROFILE_DISABLED'});check('WP002_DISABLED',facts().head.generation===firstFacts.head.generation);
 stopFront();recreate(m.runtimeId);resources=caps();write(path.join(out,'native-deployment-initial.json'),resources,true);permit.deployment.evidence=sha(read(path.join(out,'native-deployment-initial.json')));
 stopFront();publish(permit,'initial');compose(['up','-d','--no-build','--pull','never','api']);waitReady();compose(['up','-d','--no-build','--pull','never','ingress']);waitIngress();
 const changed={...a,basis:sha('outside-permit')};request(writer.id,'/v1/prepare',changed,{code:403,error:'WRITE_PERMIT_SCOPE_REJECTED'});check('WP003_SCOPE',gen()===firstFacts.head.generation);
 a.expectedGeneration=gen();const lost=request(writer.id,'/v1/prepare',a,{dropBody:true});ensure(lost.bodyConsumed===false&&lost.fullRequestSent&&lost.lostResponseBodyWitness,'BODY_LOSS_WITNESS_MISSING');
 const afterLost=facts();check('WP004_COMMIT_ORACLE',afterLost.counts.operations===1&&afterLost.head.generation===(BigInt(a.expectedGeneration)+1n).toString());
 const replay=request(writer.id,'/v1/prepare',a).response;check('WP004_REPLAY',replay.replay===true&&replay.head.generation===afterLost.head.generation);
 unknown.expectedGeneration=gen();request(writer.id,'/v1/report-result',unknown);terminal.expectedGeneration=gen();const aTerminal=request(writer.id,'/v1/report-result',terminal).response;
 b.expectedGeneration=gen();request(writer.id,'/v1/prepare',b);c.expectedGeneration=gen();request(writer.id,'/v1/prepare',c);tombTerminal.expectedGeneration=gen();request(writer.id,'/v1/report-result',tombTerminal);
 const beforeRestart=facts(),beforePid=inspect('api').State.Pid;compose(['restart','--timeout','3','api']);waitReady();const afterRestart=facts();check('WP005_API_RESTART',inspect('api').State.Pid!==beforePid&&afterRestart.stateDigest===beforeRestart.stateDigest);check('WP005_RECEIPT',stable(request(writer.id,'/v1/report-result',terminal).response.phaseReceipt)===stable(aTerminal.phaseReceipt));
 const dbBefore=inspect('db');docker(['kill','--signal','KILL',dbBefore.Id]);ensure(inspect('db').State.Running===false,'DB_KILL_NOT_OBSERVED');
 request(writer.id,'/v1/prepare',oldNegative,{code:503,error:'TRUST_UNAVAILABLE'});
 docker(['start',dbBefore.Id]);let dbReady=false;for(let i=0;i<40;i++){const r=docker(['exec',dbBefore.Id,'pg_isready','-h','127.0.0.1','-d','estakada_trust'],{optional:true,timeout:3000});if(r.status===0){dbReady=true;break;}Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,250);}ensure(dbReady,'DB_RECOVERY_TIMEOUT');
 check('WP006_DB_RESTART',inspect('db').Id===dbBefore.Id&&facts().stateDigest===beforeRestart.stateDigest);
 fence.expectedGeneration=gen();const fenced=request(recovery.id,'/v1/recovery/fence',fence).response;const frozen=facts();ensure(frozen.head.mode==='FROZEN'&&frozen.head.writerEpoch==='2','FENCE_NOT_FROZEN');
 check('WP007_FENCE_REPLAY',request(recovery.id,'/v1/recovery/fence',fence).response.replay===true&&facts().stateDigest===frozen.stateDigest);
 request(writer.id,'/v1/prepare',oldNegative,{code:403,error:'CREDENTIAL_REVOKED'});check('WP007_OLD_KEY_FENCED',facts().stateDigest===frozen.stateDigest);
 badActivate.expectedGeneration=frozen.head.generation;request(recovery.id,'/v1/recovery/activate',badActivate,{code:409,error:'RECOVERY_PRECONDITION_FAILED'});check('WP008_UNRECONCILED',facts().stateDigest===frozen.stateDigest);
 const oldApi=inspect('api'),newRuntime=crypto.randomUUID();stopFront();ensure(!inspect('api').State.Running&&inspect('api').Id===oldApi.Id,'EXCLUSION_NOT_CONFIRMED');
 write(path.join(privateDir,'credentials-before-rotation-'+planId+'.json'),read(path.join(privateDir,'credentials.json')).toString('utf8'),true);keys.credentials.push(newWriter);write(path.join(privateDir,'credentials.json'),keys);
 // Create the replacement with the new runtime/config but a rejected old permit.
 // No permitted write is possible until the bound proof is issued below.
 mode('local-test-permit',newRuntime);compose(['up','-d','--no-build','--pull','never','--force-recreate','api']);waitReady();const newApi=inspect('api');ensure(newApi.Id!==oldApi.Id,'NEW_CONTAINER_REQUIRED');
 const oldLookup=docker(['inspect',oldApi.Id],{optional:true});ensure(oldLookup.status!==0,'OLD_CONTAINER_STILL_PRESENT');
 compose(['up','-d','--no-build','--pull','never','--force-recreate','ingress']);waitIngress();
 const newFacts=facts();ensure(newFacts.stateDigest===frozen.stateDigest,'ROTATION_CHANGED_DATA');
 exclusionEvidence={previousRuntimeId:m.runtimeId,previousContainerId:oldApi.Id,newRuntimeId:newRuntime,newContainerId:newApi.Id,oldStoppedBeforeRecreate:true,oldRemoved:true,newConfigSha256:sha(read(path.join(privateDir,'credentials.json')))};
 write(path.join(out,'exclusion-evidence.json'),exclusionEvidence,true);
 const proof={fenceActionId:fence.actionId,fenceReceiptDigest:hash(fenced.recoveryReceipt),head:newFacts.head,stateDigest:newFacts.stateDigest,runtimeId:newRuntime,credentialConfigSha256:sha(read(path.join(privateDir,'credentials.json'))),exclusion:{previousRuntimeId:m.runtimeId,previousContainerId:oldApi.Id,newRuntimeId:newRuntime,newContainerId:newApi.Id,evidenceSha256:sha(read(path.join(out,'exclusion-evidence.json')))}};
 const activate={...badActivate,actionId:actionIds[2],reconciliationDigest:newFacts.stateDigest};requests=[...requests,descriptor(activate,recovery,'activate'),descriptor(d,newWriter,'prepare')];
 permit={...permit,requests,runtimeId:newRuntime,credentialConfigSha256:proof.credentialConfigSha256,reconciliation:proof,deployment:{...permit.deployment,evidence:hash(caps())}};
 // Stop/restart the same replacement container to retain the attested ID; direct
 // file truncation preserves bind inode. No atomic rename is used here.
 stopFront();publish(permit,'rotation');mode('local-test-permit',newRuntime);
 compose(['up','-d','--no-build','--pull','never','api']);waitReady();ensure(inspect('api').Id===newApi.Id,'EXCLUSION_ID_DRIFT');compose(['up','-d','--no-build','--pull','never','ingress']);waitIngress();
 activate.expectedGeneration=gen();const active=request(recovery.id,'/v1/recovery/activate',activate).response;ensure(active.head.mode==='ACTIVE','ACTIVATE_FAILED');
 check('WP009_ACTIVATE_REPLAY',request(recovery.id,'/v1/recovery/activate',activate).response.replay===true);
 d.expectedGeneration=gen();request(newWriter.id,'/v1/prepare',d);request(writer.id,'/v1/prepare',oldNegative,{code:403,error:'CREDENTIAL_REVOKED'});finalFacts=facts();
 check('WP009_NEW_WRITER',finalFacts.counts.operations===4&&finalFacts.head.writerEpoch==='2');
 check('WP010_DENIALS_RETAINED',finalFacts.counts.tombstones===1&&finalFacts.counts.routes===3&&finalFacts.counts.recovery===2&&finalFacts.operations.find(x=>x.operationId===a.operationId)?.stage==='FINAL_RESTRICTION'&&finalFacts.operations.find(x=>x.operationId===b.operationId)?.stage==='PENDING_DENY');
 resources=caps();const memory={};for(const kind of ['api','db','ingress']){const rows=docker(['exec',project+'-'+kind,'cat','/sys/fs/cgroup/memory.peak','/sys/fs/cgroup/memory.events']).stdout.trim().split('\n');memory[kind]={peak:Number(rows[0]),events:Object.fromEntries(rows.slice(1).map(x=>x.split(/\s+/)))};ensure(!Number(memory[kind].events.oom)&&!Number(memory[kind].events.oom_kill),'OOM_EVENT');}write(path.join(out,'native-resource-evidence.json'),{resources,memory,logicalBytes:finalFacts.logicalBytes,reservedBytes:finalFacts.reservedBytes},true);check('WP011_CAPS',finalFacts.logicalBytes<67108864&&finalFacts.reservedBytes<16777216);
 const disk=Number(docker(['exec','--user','999:999',project+'-db','du','-sk','/var/lib/postgresql']).stdout.trim().split(/\s+/)[0])*1024;const total=disk+bytes(task)+bytes(out)+8*1024**2;ensure(Number.isSafeInteger(total)&&total<2*1024**3,'DISK_BUDGET');write(path.join(out,'native-budget.json'),{dataBytes:disk,observedTotalBytes:total,budgetBytes:2*1024**3,hardFilesystemQuota:false},true);
 const forbidden=[...keys.credentials.map(x=>x.secret),...keys.credentials.map(x=>x.id+':'+x.secret),planId,...opIds];for(const kind of ['api','db','ingress']){const r=docker(['logs',project+'-'+kind]);const content=r.stdout+'\n'+r.stderr;ensure(!forbidden.some(x=>content.includes(x)),'LOG_PRIVACY_LEAK');}drift();check('WP012_DRIFT_PRIVACY',true);
 stopFront();mode('disabled',newRuntime);write(path.join(privateDir,'write-profile.json'),'{}\n');status='PASS';
}catch(error){errorCode=/^[A-Z][A-Z0-9_]{1,79}$/.test(error?.message||'')?error.message:'NATIVE_EXPERIMENT_FAILED';}
finally{
 try{if(started){const current=json(manifestFile);mode('disabled',current.runtimeId);local('Stop');}}catch{status='FAIL';errorCode='FINAL_STOP_FAILED';}
 const report={scope:'DEV15-LOCAL-SYNTHETIC-NATIVE',status,errorCode,groups,sourceSha256:m?.sourceSha256||null,initialHead:firstFacts?.head||null,finalHead:finalFacts?.head||null,finalCounts:finalFacts?.counts||null,defaultWriteProfile:'disabled',workflowComplete:false,appReconciliationVerified:false,productionVerified:false,dataRetained:true};
 if(reportFd!==null){fs.writeSync(reportFd,JSON.stringify(report,null,2)+'\n');fs.fsyncSync(reportFd);fs.closeSync(reportFd);}process.stdout.write(JSON.stringify({status,errorCode,groups:groups.length,report:'work/dev15-write-20261102/native-write-report.json'})+'\n');if(status!=='PASS')process.exitCode=1;
}
