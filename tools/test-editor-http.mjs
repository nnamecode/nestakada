// Host coordinator only. Browser has no Docker socket or database credentials.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import readline from 'node:readline';
import net from 'node:net';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const root=path.join(repo,'work/dev07-ui-20261031');
const attempt=process.argv[2]??'first';
if(!['first','second','third','fourth','fifth','sixth','seventh'].includes(attempt))throw new Error('CLOSED_ATTEMPT_LABEL');
const results=path.join(root,'browser-'+attempt);
const privateFile=path.join(repo,'work/foundation/test/private/editor-seed.json');
const fixtureFile=path.join(repo,'tools/editor_http_fixture.py');
const probeFile=path.join(repo,'tools/editor_http_probe.mjs');
const image='mcr.microsoft.com/playwright@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea';
const appImage='sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986';
const runId=crypto.randomUUID(),runnerName='nestakada-editor-browser-'+runId;
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
if(fixtureHash!=='7e9dcaf8e19f12a64d479cfbd873f47f5ef61ee86acb0c8d6a4618bdd72f4ff3'
  ||probeHash!=='e32a7fd6973c79956e3288d82f69121c0507a6a6632e096d86ef3bd5f39551ad')fail('QA_FREEZE_MISMATCH');
const manifest=JSON.parse(fs.readFileSync(path.join(repo,'work/foundation/test/manifest.json'),'utf8'));
if(!manifest.active||manifest.environment!=='test'||manifest.composeProject!=='nestakada-foundation-test')fail('ACTIVE_LOCAL_TEST_REQUIRED');
for(const row of JSON.parse(fs.readFileSync(regular(manifest.sourceManifest),'utf8'))){
  const file=path.resolve(manifest.sourceDirectory,row.path),relative=path.relative(manifest.sourceDirectory,file);
  if(relative.startsWith('..')||path.isAbsolute(relative)||sha(fs.readFileSync(regular(file)))!==row.sha256)fail('SOURCE_DRIFT');
}
const app=JSON.parse(docker(['inspect','nestakada-foundation-test-app']))[0];
if(app.Image!==appImage||app.Config.Labels['nestakada.scope']!=='foundation-test'
  ||!app.Config.Env.includes('DJANGO_SETTINGS_MODULE=probe_settings'))fail('EDITOR_PROBE_APP_REQUIRED');
if(fs.existsSync(privateFile)||!fs.statSync(results).isDirectory())fail('FRESH_PRIVATE_SEED_AND_OUTPUT_REQUIRED');
const expectedRunnerImage=JSON.parse(docker(['image','inspect',image]))[0].Id;
let seed,report,cleanup,runner,runnerStopped=true,seedAttempted=false,ownershipConflict=false;
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
  const request=kind==='seed'?{kind,runId}:{kind,runId,userIds:seed.userIds,pageIds:seed.pageIds,routeIds:seed.routeIds,systemRouteIds:seed.systemRouteIds};
  return JSON.parse(docker(['exec','-i','--env','DJANGO_SETTINGS_MODULE=estakada.settings.local_http',
    'nestakada-foundation-test-app','python','-c',fixtureSource],JSON.stringify(request)));
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
  fs.writeFileSync(path.join(results,'socket-report.json'),JSON.stringify({early,over,framing,scope:'anonymous-header-only'}));
  seedAttempted=true;seed=helper('seed');
  if(seed.runId!==runId||seed.pageIds.length!==2||seed.userIds.length!==3)fail('FIXTURE_SEED_CONTRACT');
  fs.writeFileSync(privateFile,JSON.stringify(seed));
  const args=['run','--rm','-i','--init','--pull=never','--name',runnerName,'--label','nestakada.scope=editor-http-test','--label','nestakada.run='+runId,
    '--user','1000:1000','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
    '--memory','1g','--memory-swap','1g','--cpus','2','--pids-limit','256','--shm-size','256m',
    '--tmpfs','/tmp:rw,nosuid,nodev,size=256m,uid=1000,gid=1000,mode=1777',
    '--network','bridge','--add-host','host.docker.internal:host-gateway','--env','HOME=/tmp','--env','CI=1',
    '--mount',`type=bind,source=${privateFile},target=/private/editor-seed.json,readonly`,
    '--mount',`type=bind,source=${probeFile},target=/qa/editor_http_probe.mjs,readonly`,
    '--mount',`type=bind,source=${path.join(repo,'work/acceptance-container/acceptance/node_modules')},target=/tests/node_modules,readonly`,
    '--mount',`type=bind,source=${results},target=/output`,image,'node','/qa/editor_http_probe.mjs'];
  runner=spawn('docker.exe',args,{stdio:['pipe','pipe','pipe'],windowsHide:true});runnerStopped=false;
  let stderrBytes=0;
  runner.stderr.on('data',bytes=>{stderrBytes+=bytes.length;if(stderrBytes>65536)runner.kill();});
  let queue=Promise.resolve();
  const lines=readline.createInterface({input:runner.stdout});
  lines.on('line',line=>{queue=queue.then(()=>{
    if(line.length>65536)fail('PROBE_OUTPUT_BOUND');const value=JSON.parse(line);
    if(value.kind==='observe'&&Number.isSafeInteger(value.id)&&value.id>0&&value.id<1000){
      runner.stdin.write(JSON.stringify({kind:'observation',id:value.id,value:helper('observe')})+'\n');
    }else if(value.kind==='result'){report=value;}else fail('CLOSED_PROBE_PROTOCOL');
  }).catch(()=>{runner.kill();});});
  const timer=setTimeout(()=>{try{runnerStopped=stopOwnedRunner();}catch{ownershipConflict=true;}runner.kill();},600000);
  const code=await new Promise((resolve,reject)=>{runner.on('error',reject);runner.on('exit',resolve);});
  clearTimeout(timer);await queue;runnerStopped=true;
  if(code!==0||report?.status!=='PASS')fail('EDITOR_BROWSER_PROBE_FAILED');
  if(sha(fs.readFileSync(probeFile))!==probeHash)fail('PROBE_SOURCE_DRIFT');
}catch(error){
  report={...(report??{}),kind:'result',status:'FAIL',code:/^[A-Z_]+$/.test(error.message)?error.message:'EDITOR_COORDINATOR_FAILED'};
}finally{
  try{
    runnerStopped=!ownershipConflict&&stopOwnedRunner();
  }catch{runnerStopped=false;ownershipConflict=true;}
  if(seed&&runnerStopped){try{cleanup=helper('close');}catch{cleanup={closed:false};}}
  if(cleanup?.closed!==true&&seedAttempted)report={...(report??{}),status:'FAIL',cleanupRequired:true};
  fs.writeFileSync(path.join(results,'host-report.json'),JSON.stringify({runId,report,cleanup,fixtureHash,probeHash}));
  console.log(JSON.stringify({status:report?.status??'FAIL',groups:report?.groups?.length??0,cleanupClosed:cleanup?.closed??!seedAttempted,results}));
  if(report?.status!=='PASS')process.exitCode=1;
}
