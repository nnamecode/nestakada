// Host coordinator only. Browser has no Docker socket or database credentials.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import readline from 'node:readline';
import net from 'node:net';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const root=path.join(repo,'work/dev07-network-20261101');
const attempt=process.argv[2];
if(attempt!=='first'||process.argv.length!==3)throw new Error('CLOSED_ATTEMPT_LABEL');
const results=path.join(root,'browser-'+attempt);
const privateFile=path.join(repo,'work/foundation/test/private/editor-network-seed.json');
const fixtureFile=path.join(repo,'tools/editor_embedded_http_fixture.py');
const probeFile=path.join(repo,'tools/editor_network_http_probe.mjs');
const witnessFile=path.join(repo,'tools/editor_network_http_fixture.py');
const selfFile=fileURLToPath(import.meta.url);
const inputsDir=path.join(repo,'work/dev06-http-20261031/inputs');
const image='mcr.microsoft.com/playwright@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea';
const appImage='sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986';
const runId=crypto.randomUUID(),runnerName='nestakada-editor-network-'+runId;
const fail=code=>{throw new Error(code);};
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
function regular(file){if(fs.lstatSync(file).isSymbolicLink()||!fs.lstatSync(file).isFile())fail('REGULAR_INPUT_REQUIRED');return file;}
function docker(args,input,timeout=60000){
  const value=spawnSync('docker.exe',args,{input,encoding:'utf8',timeout,maxBuffer:2*1024*1024,windowsHide:true});
  if(value.error||value.status!==0)fail('OWN_DOCKER_OPERATION_FAILED');
  return value.stdout;
}
const fixtureSource=fs.readFileSync(regular(fixtureFile),'utf8');
const fixtureHash=sha(fixtureSource),probeHash=sha(fs.readFileSync(regular(probeFile)));
if(probeHash!=='79777019e2087322817e529fe1041127b96ced53df90a5eccc3d66a34607a193')fail('QA_PROBE_FREEZE_MISMATCH');
if(fixtureHash!=='772b02f4721a8fe65e08ac6e17fecf03e7b98e6b5492ce97b58462675c32abb5')fail('QA_FIXTURE_FREEZE_MISMATCH');
const inputManifest=path.join(inputsDir,'inputs.json');
const inputs=JSON.parse(fs.readFileSync(regular(inputManifest),'utf8'));
if(Object.keys(inputs).length!==9)fail('CLOSED_SYNTHETIC_CORPUS_REQUIRED');
const inputFiles=Object.entries(inputs).map(([name,row])=>{
  if(!/^[a-z0-9][a-z0-9.-]{0,70}$/u.test(name)||row.name!==name||path.basename(name)!==name)fail('CLOSED_INPUT_BASENAME');
  const file=regular(path.join(inputsDir,name)),data=fs.readFileSync(file);
  if(data.length!==row.bytes||sha(data)!==row.sha256)fail('INPUT_MANIFEST_MISMATCH');return file;
});
const witnessSource=fs.readFileSync(regular(witnessFile),'utf8'),witnessHash=sha(witnessSource);
if(witnessHash!=='2d84521906ea413c7cb40f87b9653bc98d363af3a1be10930d1fb03baed6d691')fail('NETWORK_WITNESS_FREEZE_MISMATCH');
const networkPins={
  'network_observer.py':'1ed961fd7ca0d3f49773633907d3def262248d18330ad5e92b484f63ec5efe92',
  'probe_settings.py':'fa4de2627121b7737cd61bc70d25edea77035821e3d5f3f0b56dc89a61ce4301',
  'compose-network-probe.yaml':'603e879e95716a1254c702b042b2830ad3669da46e4f9ab6b920fe42309ab5e1',
  'probe-nginx.conf':'a5a6f737363da62e70566aff38fccc638cb731e5b7f411cf93c94ff5a8c82cf0'};
const networkFiles=Object.entries(networkPins).map(([name,digest])=>{const file=regular(path.join(root,name));if(sha(fs.readFileSync(file))!==digest)fail('NETWORK_CONFIG_FREEZE_MISMATCH');return file;});
const qaFiles=[fixtureFile,probeFile,selfFile,witnessFile,...networkFiles,
  path.join(repo,'work/dev07-f-20261031/probe-config/probe_settings.py'),
  path.join(repo,'work/dev07-f-20261031/probe-config/probe_urls.py'),inputManifest,...inputFiles];
regular(path.join(repo,'work/acceptance-container/acceptance/node_modules/playwright/index.mjs'));
const playwrightPackage=JSON.parse(fs.readFileSync(regular(path.join(repo,'work/acceptance-container/acceptance/node_modules/playwright/package.json')),'utf8'));
if(playwrightPackage.version!=='1.64.1')fail('APPROVED_PLAYWRIGHT_REQUIRED');
const qaBefore=qaFiles.map(file=>({path:path.relative(repo,file).replaceAll('\\','/'),sha256:sha(fs.readFileSync(regular(file)))}));
const manifest=JSON.parse(fs.readFileSync(path.join(repo,'work/foundation/test/manifest.json'),'utf8'));
if(!manifest.active||manifest.environment!=='test'||manifest.composeProject!=='nestakada-foundation-test')fail('ACTIVE_LOCAL_TEST_REQUIRED');
if(sha(fs.readFileSync(regular(manifest.sourceManifest)))!==manifest.sourceSha256)fail('SOURCE_MANIFEST_DRIFT');
for(const row of JSON.parse(fs.readFileSync(regular(manifest.sourceManifest),'utf8'))){
  const file=path.resolve(manifest.sourceDirectory,row.path),relative=path.relative(manifest.sourceDirectory,file);
  if(relative.startsWith('..')||path.isAbsolute(relative)||sha(fs.readFileSync(regular(file)))!==row.sha256)fail('SOURCE_DRIFT');
}
const app=JSON.parse(docker(['inspect','nestakada-foundation-test-app']))[0];
if(app.Image!==appImage||app.Config.Labels['nestakada.scope']!=='foundation-test'
  ||!app.Config.Env.includes('DJANGO_SETTINGS_MODULE=probe_settings'))fail('EDITOR_PROBE_APP_REQUIRED');
if(JSON.stringify(app.Config.Cmd)!==JSON.stringify(['python','manage.py','runserver','0.0.0.0:8000','--noreload']))fail('THREADED_APPROVED_SERVER_REQUIRED');
const nonces=app.Config.Env.filter(value=>value.startsWith('ESTAKADA_NETWORK_PROBE_RUN='));
if(nonces.length!==1||!/^ESTAKADA_NETWORK_PROBE_RUN=[a-f0-9]{32}$/u.test(nonces[0]))fail('OBSERVER_NONCE_REQUIRED');
const networkRun=nonces[0].slice(nonces[0].indexOf('=')+1);
const mountSource=value=>value.replaceAll('\\','/').replace(/^\/run\/desktop\/mnt\/host\/t\//u,'T:/').toLowerCase();
for(const [destination,source] of [['/network-probe/network_observer.py',path.join(root,'network_observer.py')],
  ['/network-probe/probe_settings.py',path.join(root,'probe_settings.py')],
  ['/network-probe/base_probe_settings.py',path.join(repo,'work/dev07-f-20261031/probe-config/probe_settings.py')]]){
  const mounts=app.Mounts.filter(m=>m.Destination===destination);
  if(mounts.length!==1||mounts[0].RW||mountSource(mounts[0].Source)!==mountSource(source))fail('NETWORK_OBSERVER_MOUNT_REQUIRED');
}
const ingress=JSON.parse(docker(['inspect',manifest.containers.ingress]))[0];
const nginxMount=ingress.Mounts.filter(m=>m.Destination==='/preflight/nginx.conf');
if(nginxMount.length!==1||nginxMount[0].RW||mountSource(nginxMount[0].Source)!==mountSource(path.join(root,'probe-nginx.conf')))fail('NETWORK_NGINX_MOUNT_REQUIRED');
if(fs.existsSync(privateFile)||!fs.statSync(results).isDirectory())fail('FRESH_PRIVATE_SEED_AND_OUTPUT_REQUIRED');
const expectedRunnerImage=JSON.parse(docker(['image','inspect',image]))[0].Id;
function foundationState(){
  const manifests=[['app',manifest.sourceManifest,manifest.sourceDirectory,manifest.sourceSha256],
    ['worker',manifest.workerSourceManifest,manifest.workerSourceDirectory,manifest.workerSourceSha256]];
  const sources=manifests.map(([kind,file,base,expected])=>{
    if(sha(fs.readFileSync(regular(file)))!==expected)fail('FOUNDATION_SOURCE_MANIFEST_DRIFT');
    const rows=JSON.parse(fs.readFileSync(file,'utf8'));
    if(!Array.isArray(rows)||rows.length===0)fail('FOUNDATION_SOURCE_MANIFEST_SHAPE');
    const key=kind==='worker'?'name':'path';
    for(const row of rows){
      if(!row||typeof row!=='object'||Array.isArray(row)||Object.keys(row).sort().join()!==[key,'sha256'].sort().join()
          ||typeof row[key]!=='string'||row[key].length===0||path.isAbsolute(row[key])
          ||typeof row.sha256!=='string'||!/^[a-f0-9]{64}$/u.test(row.sha256))fail('FOUNDATION_SOURCE_MANIFEST_SHAPE');
      const target=path.resolve(base,row[key]),relative=path.relative(base,target);
      if(relative.startsWith('..')||path.isAbsolute(relative)||sha(fs.readFileSync(regular(target)))!==row.sha256)fail('FOUNDATION_SOURCE_DRIFT');}
    return {kind,sha256:expected};
  });
  const containers={};
  for(const kind of ['app','db','ingress','media-worker']){
    const item=JSON.parse(docker(['inspect',manifest.containers[kind]]))[0];
    if(!item.State.Running||item.Config.Labels?.['nestakada.scope']!=='foundation-test')fail('FOUNDATION_CONTAINER_SCOPE');
    const caps={app:[805306368,1000000000,128],db:[1073741824,1000000000,128],ingress:[134217728,250000000,64],'media-worker':[536870912,1000000000,64]}[kind];
    if(item.HostConfig.Memory!==caps[0]||item.HostConfig.NanoCpus!==caps[1]||item.HostConfig.PidsLimit!==caps[2])fail('APPROVED_RESOURCE_CAPS_REQUIRED');
    const ports=Object.entries(item.NetworkSettings.Ports||{}).flatMap(([port,bindings])=>(bindings||[]).map(binding=>({port,...binding})));
    if(kind==='ingress'){
      if(ports.length!==1||ports[0].port!=='8080/tcp'||ports[0].HostIp!=='127.0.0.1'||ports[0].HostPort!=='8767')fail('FIXED_LOOPBACK_INGRESS_REQUIRED');
    }else if(ports.length)fail('PRIVATE_SERVICE_PUBLISHED');
    const nets=Object.keys(item.NetworkSettings.Networks||{});
    if(kind==='db'&&(nets.length!==1||nets[0]!=='nestakada-foundation-test-db'))fail('PRIVATE_DATABASE_NETWORK_REQUIRED');
    if(kind==='ingress'&&nets.includes('nestakada-foundation-test-db'))fail('INGRESS_DATABASE_NETWORK_FORBIDDEN');
    containers[kind]={id:item.Id,image:item.Image,startedAt:item.State.StartedAt,command:item.Config.Cmd,
      mounts:item.Mounts.map(m=>({source:m.Source,destination:m.Destination,rw:m.RW})),readOnly:item.HostConfig.ReadonlyRootfs};
  }
  const dbNetwork=JSON.parse(docker(['network','inspect','nestakada-foundation-test-db']))[0];
  if(!dbNetwork.Internal)fail('INTERNAL_DATABASE_NETWORK_REQUIRED');
  return {manifestSha256:sha(fs.readFileSync(regular(path.join(repo,'work/foundation/test/manifest.json')))),sources,containers};
}
const foundationBefore=foundationState();
let seed,report,cleanup,runner,runnerStopped=true,seedAttempted=false,ownershipConflict=false,observerFinal;
let queueFailure=null,fixtureFailure=null,childExit=null,currentCase=null,stderrBytes=0,qaAfter,foundationAfter;
const knownFiles=new Map(),assetIds=new Set(),folderIds=new Set();
let runnerAudited=false;
function auditRunner(){
  if(runnerAudited)return;
  const item=JSON.parse(docker(['inspect',runnerName]))[0];
  if(item.Image!==expectedRunnerImage||item.Config.Labels?.['nestakada.run']!==runId||item.HostConfig.Privileged)fail('RUNNER_SCOPE_REQUIRED');
  const allowed=new Set(['/private/editor-seed.json','/qa/editor_http_probe.mjs','/inputs','/tests/node_modules','/output']);
  for(const mount of item.Mounts){if(!allowed.has(mount.Destination)||((mount.Destination!=='/output')&&mount.RW)||/docker\.sock|docker_engine|containerd\.sock/iu.test(mount.Source))fail('RUNNER_MOUNT_BOUNDARY');}
  if(item.Config.Env.some(value=>/^(?:ESTAKADA_DB|DATABASE_|PGPASSWORD|DJANGO_SECRET)/u.test(value)))fail('RUNNER_DATABASE_SECRET_FORBIDDEN');
  runnerAudited=true;
}
const stderrClasses=new Set();
function stopOwnedRunner(){
  const ids=docker(['ps','-aq','--filter','name=^/'+runnerName+'$']).trim().split(/\s+/u).filter(Boolean);
  if(!ids.length)return true;
  if(ids.length!==1)fail('RUNNER_OWNERSHIP_CONFLICT');
  const container=JSON.parse(docker(['inspect',ids[0]]))[0];
  if(container.Image!==expectedRunnerImage||container.Name!=='/'+runnerName
      ||container.Config.Labels?.['nestakada.scope']!=='editor-http-test'
      ||container.Config.Labels?.['nestakada.run']!==runId)fail('RUNNER_OWNERSHIP_CONFLICT');
  if(container.State.Running)docker(['stop','--time','2',container.Id]);
  return !docker(['ps','-q','--filter','id='+container.Id]).trim();
}
function helper(kind){
  if(sha(fs.readFileSync(regular(fixtureFile)))!==fixtureHash)fail('FIXTURE_SOURCE_DRIFT');
  const request=kind==='seed'?{kind,runId}:{kind,runId,userIds:seed.userIds,pageIds:seed.pageIds,routeIds:seed.routeIds,systemRouteIds:seed.systemRouteIds,
    knownFiles:[...knownFiles.values()],assetIds:[...assetIds],folderIds:[...folderIds]};
  const result=spawnSync('docker.exe',['exec','-i','--env','DJANGO_SETTINGS_MODULE=estakada.settings.local_http',
    'nestakada-foundation-test-app','python','-c',fixtureSource],{input:JSON.stringify(request),encoding:'utf8',
    timeout:60000,maxBuffer:2*1024*1024,windowsHide:true});
  if(result.error||result.status!==0){
    fixtureFailure={kind,exitCode:Number.isInteger(result.status)?result.status:null,errorClass:'UNCLASSIFIED',code:'FIXTURE_OPERATION_FAILED'};
    for(const line of (result.stderr||'').split(/\r?\n/u)){try{const value=JSON.parse(line);
      if(JSON.stringify(Object.keys(value).sort())===JSON.stringify(['code','errorClass'])
          &&/^[A-Za-z0-9_]{1,80}$/u.test(value.errorClass)&&/^FIXTURE_[A-Z_]{1,80}$/u.test(value.code)){
        fixtureFailure.errorClass=value.errorClass;fixtureFailure.code=value.code;
      }}catch{}}
    fail('FIXTURE_HELPER_FAILED');
  }
  if(Buffer.byteLength(result.stdout)>65536)fail('FIXTURE_OUTPUT_BOUND');
  const value=JSON.parse(result.stdout);
  if(kind==='observe'){
    if(!Array.isArray(value.assets)||!Array.isArray(value.folderIds))fail('MEDIA_OBSERVER_PROTOCOL');
    for(const id of value.folderIds)folderIds.add(id);
    for(const asset of value.assets){assetIds.add(asset.id);for(const file of asset.files)knownFiles.set(asset.id+'|'+file.key,{assetId:asset.id,key:file.key});}
  }
  return value;
}
function witness(operation){
  if(!['network_observer_read','network_slot_try','network_pg_try'].includes(operation)
      ||sha(fs.readFileSync(regular(witnessFile)))!==witnessHash)fail('NETWORK_WITNESS_BOUNDARY');
  const result=spawnSync('docker.exe',['exec','-i','--env','DJANGO_SETTINGS_MODULE=estakada.settings.local_http',
    'nestakada-foundation-test-app','python','-c',witnessSource],{input:JSON.stringify({operation,run:networkRun}),
    encoding:'utf8',timeout:15000,maxBuffer:131072,windowsHide:true});
  if(result.error||result.status!==0||Buffer.byteLength(result.stdout)>65536)fail('NETWORK_WITNESS_FAILED');
  return JSON.parse(result.stdout);
}
function rawStatus(request){
  return new Promise((resolve,reject)=>{
    const socket=net.createConnection({host:'127.0.0.1',port:8767});let received='';
    const done=(error,value)=>{socket.destroy();error?reject(error):resolve(value);};
    socket.setTimeout(7000,()=>done(new Error('RAW_SOCKET_DEADLINE')));
    socket.on('connect',()=>socket.write(request));
    socket.on('data',bytes=>{received+=bytes.toString('latin1');if(received.length>65536)return done(new Error('HEADER_BOUND'));
      const match=/^HTTP\/1\.[01] ([0-9]{3}) /u.exec(received);if(match&&received.includes('\r\n\r\n'))done(null,Number(match[1]));});
    socket.on('error',()=>done(new Error('RAW_SOCKET_ERROR')));
    socket.on('end',()=>{if(!received.includes('\r\n\r\n'))done(new Error('RAW_SOCKET_TRUNCATED'));});
  });
}
try{
  const endpoint='/manage/pages/00000000-0000-0000-0000-000000000001/edit/check/';
  const prefix='POST '+endpoint+' HTTP/1.1\r\nHost: localhost:8767\r\nContent-Type: application/json\r\nConnection: close\r\n';
  const early=await rawStatus(prefix+'Content-Length: 67108864\r\n\r\n');
  if(early!==401)fail('ANONYMOUS_EARLY_DENIAL');
  const over=await rawStatus(prefix+'Content-Length: 67108865\r\n\r\n');
  if(over!==413)fail('NGINX_EXACT_BODY_CAP');
  const framing=await rawStatus(prefix+'Content-Length: 5\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n');
  if(framing!==400)fail('AMBIGUOUS_FRAMING');
  const cancelPrefix=prefix.replace('/edit/check/','/edit/draft/cancel/');
  const cancelOver=await rawStatus(cancelPrefix+'Content-Length: 16385\r\n\r\n');
  if(cancelOver!==413)fail('CANCEL_EXACT_BODY_CAP');
  const cancelFraming=await rawStatus(cancelPrefix+'Content-Length: 5\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n');
  if(cancelFraming!==400)fail('CANCEL_AMBIGUOUS_FRAMING');
  const issuePrefix=prefix.replace('/edit/check/','/edit/embedded/issue/');
  const issueOver=await rawStatus(issuePrefix+'Content-Length: 16385\r\n\r\n');
  if(issueOver!==413)fail('ISSUE_EXACT_BODY_CAP');
  const issueFraming=await rawStatus(issuePrefix+'Content-Length: 5\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n');
  if(issueFraming!==400)fail('ISSUE_AMBIGUOUS_FRAMING');
  fs.writeFileSync(path.join(results,'socket-report.json'),JSON.stringify({early,over,framing,cancelOver,cancelFraming,issueOver,issueFraming,scope:'anonymous-header-only'}));
  seedAttempted=true;seed=helper('seed');
  if(seed.runId!==runId||seed.pageIds.length!==2||seed.userIds.length!==3)fail('FIXTURE_SEED_CONTRACT');
  const initialObserver=witness('network_observer_read');
  if(!initialObserver.ready||initialObserver.fault||initialObserver.requests.length!==0)fail('FRESH_OBSERVER_REQUIRED');
  fs.writeFileSync(privateFile,JSON.stringify({...seed,networkRun}));
  const args=['run','--rm','-i','--init','--pull=never','--name',runnerName,'--label','nestakada.scope=editor-http-test','--label','nestakada.run='+runId,
    '--user','1000:1000','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
    '--memory','1g','--memory-swap','1g','--cpus','2','--pids-limit','256','--shm-size','256m',
    '--tmpfs','/tmp:rw,nosuid,nodev,size=256m,uid=1000,gid=1000,mode=1777',
    '--network','bridge','--add-host','host.docker.internal:host-gateway','--env','HOME=/tmp','--env','CI=1',
    '--mount',`type=bind,source=${privateFile},target=/private/editor-seed.json,readonly`,
    '--mount',`type=bind,source=${probeFile},target=/qa/editor_http_probe.mjs,readonly`,
    '--mount',`type=bind,source=${inputsDir},target=/inputs,readonly`,
    '--mount',`type=bind,source=${path.join(repo,'work/acceptance-container/acceptance/node_modules')},target=/tests/node_modules,readonly`,
    '--mount',`type=bind,source=${results},target=/output`,image,'node','/qa/editor_http_probe.mjs'];
  runner=spawn('docker.exe',args,{stdio:['pipe','pipe','pipe'],windowsHide:true});runnerStopped=false;
  runner.stderr.on('data',bytes=>{stderrBytes+=bytes.length;
    for(const name of ['SyntaxError','ReferenceError','TypeError','RangeError','ERR_MODULE_NOT_FOUND'])
      if(bytes.toString('utf8').includes(name))stderrClasses.add(name);
    if(stderrBytes>65536)runner.kill();});
  let queue=Promise.resolve();
  const lines=readline.createInterface({input:runner.stdout});
  lines.on('line',line=>{queue=queue.then(()=>{
    if(line.length>65536)fail('PROBE_OUTPUT_BOUND');const value=JSON.parse(line);
    if(value.kind==='rpc'&&Number.isSafeInteger(value.id)&&value.id>0&&value.id<2000
        &&/^NET07-00[1-6]$/u.test(value.caseId)&&Object.keys(value).sort().join()===['kind','id','caseId','operation'].sort().join()){
      auditRunner();
      currentCase=value.caseId;
      if(!['observe','network_observer_read','network_slot_try','network_pg_try'].includes(value.operation))fail('CLOSED_NETWORK_RPC');
      runner.stdin.write(JSON.stringify({kind:'rpc-result',id:value.id,value:value.operation==='observe'?helper('observe'):witness(value.operation)})+'\n');
    }else if(value.kind==='progress'&&value.caseId==='NET07-004'&&Number.isSafeInteger(value.elapsedSeconds)&&value.elapsedSeconds>=0&&value.elapsedSeconds<=180&&Object.keys(value).sort().join()==='caseId,elapsedSeconds,kind'){
      console.log(JSON.stringify({scope:'NETWORK_PROGRESS',caseId:value.caseId,elapsedSeconds:value.elapsedSeconds}));
    }else if(value.kind==='result'){report=value;}else fail('CLOSED_PROBE_PROTOCOL');
  }).catch(error=>{if(!queueFailure)queueFailure={caseId:currentCase,
    code:typeof error?.message==='string'&&/^[A-Z_]{1,120}$/u.test(error.message)?error.message:'PROBE_PROTOCOL_FAILED'};
    runner.kill();});});
  const timer=setTimeout(()=>{try{runnerStopped=stopOwnedRunner();}catch{ownershipConflict=true;}runner.kill();},600000);
  const code=await new Promise((resolve,reject)=>{runner.on('error',reject);runner.on('exit',(value,signal)=>{childExit={code:value,signal};resolve(value);});});
  clearTimeout(timer);await queue;runnerStopped=true;
  if(code!==0||report?.status!=='PASS')fail('EDITOR_BROWSER_PROBE_FAILED');
  if(report.groups?.length!==6||report.scope!=='NETWORK_6')fail('PROBE_GROUP_SCOPE_MISMATCH');
  if(sha(fs.readFileSync(probeFile))!==probeHash)fail('PROBE_SOURCE_DRIFT');
}catch(error){
  report={...(report??{}),kind:'result',status:'FAIL',code:/^[A-Z_]+$/.test(error.message)?error.message:'EDITOR_COORDINATOR_FAILED'};
}finally{
  try{
    runnerStopped=!ownershipConflict&&stopOwnedRunner();
  }catch{runnerStopped=false;ownershipConflict=true;}
  if(seed&&runnerStopped){try{observerFinal=witness('network_observer_read');
    if(!observerFinal.ready||observerFinal.fault||observerFinal.requests.some(row=>row.events[9]!==1))fail('NETWORK_REQUESTS_NOT_SETTLED');
    helper('observe');cleanup=helper('close');}catch{cleanup={closed:false};}}
  if(cleanup?.closed!==true&&seedAttempted)report={...(report??{}),status:'FAIL',cleanupRequired:true};
  try{qaAfter=qaFiles.map(file=>({path:path.relative(repo,file).replaceAll('\\','/'),sha256:sha(fs.readFileSync(regular(file)))}));
    if(JSON.stringify(qaAfter)!==JSON.stringify(qaBefore))fail('QA_SOURCE_INPUT_DRIFT');
  }catch{report={...(report??{}),status:'FAIL',code:'QA_SOURCE_INPUT_DRIFT'};}
  try{foundationAfter=foundationState();if(JSON.stringify(foundationAfter)!==JSON.stringify(foundationBefore))fail('FOUNDATION_DRIFT');}
  catch{report={...(report??{}),status:'FAIL',code:'FOUNDATION_DRIFT'};}
  fs.writeFileSync(path.join(results,'host-report.json'),JSON.stringify({runId,report,cleanup,fixtureHash,probeHash,
    qaBefore,qaAfter,foundationBefore,foundationAfter,observerFinal,
    diagnostics:{queueFailure,fixtureFailure,childExit,stderrBytes,stderrClasses:[...stderrClasses]}}));
  console.log(JSON.stringify({status:report?.status??'FAIL',scope:report?.scope??'NETWORK_6',groups:report?.groups?.length??0,cleanupClosed:cleanup?.closed??!seedAttempted,results}));
  if(report?.status!=='PASS')process.exitCode=1;
}
