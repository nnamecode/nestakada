// Host-only coordinator. Only the browser receives synthetic login credentials.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import readline from 'node:readline';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const root=path.join(repo,'work/dev07-reservation-20261101'),attempt=process.argv[2];
if(!/^first$|^fixed-[a-z0-9-]{1,32}$/.test(attempt||'')||process.argv.length!==3)throw new Error('CLOSED_ATTEMPT_REQUIRED');
const image='mcr.microsoft.com/playwright@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea';
const appImage='sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986';
const runId=crypto.randomUUID(),runnerName='nestakada-shared-browser-'+runId;
const fixture=path.join(repo,'tools/editor_shared_http_fixture.py'),probe=path.join(repo,'tools/editor_shared_http_probe.mjs');
const outputDir=path.join(root,'native-'+attempt),privateFile=path.join(repo,'work/foundation/test/private/shared-'+runId+'.json');
const sha=value=>crypto.createHash('sha256').update(value).digest('hex');
const fail=code=>{throw new Error(code);};
function regular(file){const stat=fs.lstatSync(file);if(!stat.isFile()||stat.isSymbolicLink())fail('REGULAR_FILE_REQUIRED');return file;}
function docker(args,input,timeout=60000){
  const result=spawnSync('docker.exe',args,{input,encoding:'utf8',timeout,windowsHide:true,maxBuffer:2*1024*1024});
  if(result.error||result.status!==0)fail('SCOPED_DOCKER_COMMAND_FAILED');return result.stdout;
}
const frozen=JSON.parse(fs.readFileSync(regular(path.join(root,'http-freeze.json')),'utf8'));
for(const row of frozen.files){const file=path.resolve(repo,row.path);if(!file.startsWith(repo+path.sep)||sha(fs.readFileSync(regular(file)))!==row.sha256)fail('HTTP_QA_SOURCE_DRIFT');}
if(frozen.files.length!==3||frozen.files.map(row=>row.path).sort().join()!==['tools/editor_shared_http_fixture.py','tools/editor_shared_http_probe.mjs','tools/test-editor-shared-http.mjs'].sort().join())fail('CLOSED_HTTP_QA_FREEZE_REQUIRED');
const manifest=JSON.parse(fs.readFileSync(regular(path.join(repo,'work/foundation/test/manifest.json')),'utf8'));
if(!manifest.active||manifest.environment!=='test'||manifest.composeProject!=='nestakada-foundation-test')fail('ACTIVE_TEST_FOUNDATION_REQUIRED');
function verifySource(){
  if(sha(fs.readFileSync(regular(manifest.sourceManifest)))!==manifest.sourceSha256)fail('APP_SOURCE_MANIFEST_DRIFT');
  for(const row of JSON.parse(fs.readFileSync(manifest.sourceManifest,'utf8'))){const file=path.resolve(manifest.sourceDirectory,row.path);
    if(!file.startsWith(path.resolve(manifest.sourceDirectory)+path.sep)||sha(fs.readFileSync(regular(file)))!==row.sha256)fail('FROZEN_APP_DRIFT');}
}
verifySource();
const pwRoot=path.join(repo,'work/acceptance-container/acceptance/node_modules');
if(JSON.parse(fs.readFileSync(regular(path.join(pwRoot,'playwright/package.json')),'utf8')).version!=='1.64.1')fail('APPROVED_PLAYWRIGHT_REQUIRED');
docker(['image','inspect',image]);docker(['image','inspect',appImage]);
const beforeApp=JSON.parse(docker(['inspect','nestakada-foundation-test-app']))[0];
function checkServices(){
  for(const [kind,caps] of Object.entries({app:[805306368,1000000000,128],db:[1073741824,1000000000,128],ingress:[134217728,250000000,64],'media-worker':[536870912,1000000000,64]})){
    const item=JSON.parse(docker(['inspect','nestakada-foundation-test-'+kind]))[0];
    if(!item.State.Running||item.Config.Labels?.['nestakada.scope']!=='foundation-test'||item.HostConfig.Memory!==caps[0]||item.HostConfig.NanoCpus!==caps[1]||item.HostConfig.PidsLimit!==caps[2])fail('APPROVED_LOCAL_SERVICE_CAPS_REQUIRED');
    const ports=Object.values(item.NetworkSettings.Ports||{}).flatMap(value=>value||[]);
    if(kind==='ingress'){if(ports.length!==1||ports[0].HostIp!=='127.0.0.1'||ports[0].HostPort!=='8767')fail('LOOPBACK_INGRESS_REQUIRED');}
    else if(ports.length)fail('PRIVATE_SERVICE_PUBLISHED');
    if(kind==='app'&&(!item.HostConfig.ReadonlyRootfs||!item.Mounts.some(m=>m.Destination==='/app'&&!m.RW)))fail('FROZEN_APP_MOUNT_REQUIRED');
  }
  const network=JSON.parse(docker(['network','inspect','nestakada-foundation-test-db']))[0];
  if(!network.Internal||network.Labels?.['nestakada.scope']!=='foundation-test')fail('PRIVATE_DATABASE_REQUIRED');
}
checkServices();
function verifyRuntimeSource(){
  const code="import hashlib,json,pathlib; root=pathlib.Path('/app'); suffix={'.py','.lock','.html','.css','.js','.mjs','.svg'}; files=sorted(p for p in root.rglob('*') if p.is_file() and p.suffix in suffix); print(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}))";
  const actual=JSON.parse(docker(['exec','--user','10001:10001','nestakada-foundation-test-app','python','-B','-c',code]));
  const expected=JSON.parse(fs.readFileSync(manifest.sourceManifest,'utf8'));
  if(Object.keys(actual).length!==expected.length||expected.some(row=>actual[row.path.replaceAll('\\','/')]!==row.sha256))fail('ACTUAL_CONTAINER_SOURCE_DRIFT');
}
if(fs.existsSync(outputDir)||fs.existsSync(privateFile))fail('FRESH_HTTP_OUTPUT_REQUIRED');
fs.mkdirSync(outputDir);const config=path.join(outputDir,'probe-config');fs.mkdirSync(config);
fs.writeFileSync(path.join(config,'probe_settings.py'),"from estakada.settings.local_http import *\nMEDIA_LIBRARY_ROOT = '/var/lib/estakada/rc-http351/"+runId+"/media'\n");
const overlay=path.join(outputDir,'compose-http.yaml');
fs.writeFileSync(overlay,'services:\n  app:\n    image: '+appImage+'\n    environment:\n      DJANGO_SETTINGS_MODULE: probe_settings\n      PYTHONPATH: /reservation-probe:/app\n    volumes:\n      - {type: bind, source: '+JSON.stringify(config.replaceAll('\\','/'))+', target: /reservation-probe, read_only: true}\n');
const compose=['compose','--env-file',path.join(repo,'work/foundation/test/compose.env'),'--project-name','nestakada-foundation-test','--file',path.join(repo,'environment/foundation/compose.yaml')];
let seed,runner,report,cleanup,failed=null,overlayStarted=false,stderrBytes=0;
const fixtureSource=fs.readFileSync(fixture,'utf8');
function helper(kind){
  const request={kind,runId,...(kind==='seed'?{}:{state:seed})};
  const result=spawnSync('docker.exe',['exec','-i','--user','10001:10001','nestakada-foundation-test-app','python','-B','-c',fixtureSource],
    {input:JSON.stringify(request),encoding:'utf8',timeout:60000,maxBuffer:512*1024,windowsHide:true});
  if(result.error||result.status!==0)fail('OWNED_HTTP_FIXTURE_'+kind.toUpperCase()+'_FAILED');return JSON.parse(result.stdout);
}
async function ready(){
  // Bounded startup observation, not a repeated test execution.
  for(let i=0;i<30;i++){
    try{const response=await fetch('http://127.0.0.1:8767/manage/login/',{signal:AbortSignal.timeout(1000)});await response.arrayBuffer();if(response.status===200)return;}catch{}
    await new Promise(resolve=>setTimeout(resolve,500));
  }
  fail('TEST_APP_STARTUP_TIMEOUT');
}
try{
  docker([...compose,'--file',overlay,'up','-d','--no-deps','app'],undefined,60000);overlayStarted=true;await ready();checkServices();verifySource();
  const app=JSON.parse(docker(['inspect','nestakada-foundation-test-app']))[0];if(app.Image!==appImage||!app.Config.Env.includes('DJANGO_SETTINGS_MODULE=probe_settings'))fail('CANDIDATE_HTTP_APP_REQUIRED');
  verifyRuntimeSource();
  seed=helper('seed');if(seed.runId!==runId)fail('OWNED_SEED_REQUIRED');
  fs.writeFileSync(privateFile,JSON.stringify(seed),{flag:'wx',mode:0o600});
  const args=['run','--rm','-i','--init','--pull=never','--name',runnerName,'--label','nestakada.scope=editor-http-test','--label','nestakada.run='+runId,
    '--user','1000:1000','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
    '--memory','1g','--memory-swap','1g','--cpus','2','--pids-limit','256','--shm-size','256m',
    '--tmpfs','/tmp:rw,nosuid,nodev,size=256m,uid=1000,gid=1000,mode=1777',
    '--network','bridge','--add-host','host.docker.internal:host-gateway','--env','HOME=/tmp','--env','CI=1',
    '--mount','type=bind,source='+privateFile+',target=/private/shared-seed.json,readonly',
    '--mount','type=bind,source='+probe+',target=/qa/editor_shared_http_probe.mjs,readonly',
    '--mount','type=bind,source='+pwRoot+',target=/tests/node_modules,readonly',image,'node','/qa/editor_shared_http_probe.mjs'];
  runner=spawn('docker.exe',args,{stdio:['pipe','pipe','pipe'],windowsHide:true});
  runner.stderr.on('data',chunk=>{stderrBytes+=chunk.length;});
  let queue=Promise.resolve();
  const lines=readline.createInterface({input:runner.stdout});
  lines.on('line',line=>{queue=queue.then(()=>{
    if(line.length>16384)fail('BOUNDED_BROWSER_PROTOCOL_REQUIRED');const value=JSON.parse(line);
    if(value.kind==='observe'&&Number.isSafeInteger(value.id)&&value.id>0&&value.id<100&&/^RSV-UI-00[1-5]$/.test(value.caseId)&&['observe','reset'].includes(value.operation)){
      if(value.operation==='reset'&&value.caseId!=='RSV-UI-005')fail('CLOSED_AUTH_RESET_CASE');
      runner.stdin.write(JSON.stringify({kind:'observation',id:value.id,value:helper(value.operation)})+'\n');
    }else if(value.kind==='result'&&!report)report=value;else fail('CLOSED_BROWSER_PROTOCOL_REQUIRED');
  }).catch(()=>{failed='BROWSER_OBSERVER_FAILED';runner.stdin.end();});});
  const exit=await new Promise(resolve=>{runner.once('error',()=>resolve(-1));runner.once('exit',resolve);});await queue;lines.close();
  if(exit!==0||!report?.pass||report.groups.length!==5||stderrBytes!==0||failed)fail('NATIVE_SHARED_CHECKS_FAILED');
  verifySource();for(const row of frozen.files)if(sha(fs.readFileSync(regular(path.resolve(repo,row.path))))!==row.sha256)fail('HTTP_QA_SOURCE_DRIFT');
}catch(error){failed=typeof error?.message==='string'&&/^[A-Z0-9_]{1,120}$/.test(error.message)?error.message:'SHARED_NATIVE_COORDINATOR_FAILED';}
finally{
  const ownIds=docker(['ps','-aq','--filter','name=^/'+runnerName+'$']).trim().split(/\s+/).filter(Boolean);
  for(const id of ownIds){const own=JSON.parse(docker(['inspect',id]))[0];if(own.Config.Labels?.['nestakada.run']!==runId)fail('FOREIGN_BROWSER_CONTAINER');if(own.State.Running)docker(['stop','--time','2',id]);}
  if(seed){try{cleanup=helper('close');}catch{failed=failed||'OWNED_HTTP_CLEANUP_FAILED';}}
  if(fs.existsSync(privateFile)&&!fs.lstatSync(privateFile).isSymbolicLink())fs.unlinkSync(privateFile);
  // Preserve a failed probe configuration for diagnosis; only restore after clean teardown.
  if(overlayStarted&&cleanup?.closed){try{docker([...compose,'up','-d','--no-deps','app'],undefined,60000);}catch{failed=failed||'BASE_APP_RESTORE_FAILED';}}
  const result={runId,sourceRunId:manifest.runId,sourceSha256:manifest.sourceSha256,report,cleanup,failed,
    appImage,originalAppImage:beforeApp.Image,playwrightImage:image,stderrBytes,overlaySha256:sha(fs.readFileSync(overlay)),qaFreeze:frozen};
  fs.writeFileSync(path.join(outputDir,'host-report.json'),JSON.stringify(result,null,2));
  process.stdout.write(JSON.stringify({pass:!failed,groups:report?.groups||[],cleanup:cleanup?.closed===true,failed})+'\n');
  if(failed)process.exitCode=1;
}
