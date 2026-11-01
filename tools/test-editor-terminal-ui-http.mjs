// Host-only RUI coordinator. Browser receives synthetic credentials, never Docker/PG.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import readline from 'node:readline';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const root=path.join(repo,'work/dev07-terminal-ui-20261101'),attempt=process.argv[2];
const fail=code=>{throw new Error(code);};
if(process.argv.length!==3||!/^first$|^fixed-[a-z0-9-]{1,32}$/.test(attempt||''))fail('CLOSED_ATTEMPT_REQUIRED');
const image='mcr.microsoft.com/playwright@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea';
const appImage='sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986';
const runId=crypto.randomUUID(),runnerName='nestakada-terminal-ui-browser-'+runId;
const fixture=path.join(repo,'tools/editor_restore_terminal_http_fixture.py'),probe=path.join(repo,'tools/editor_terminal_ui_http_probe.mjs');
const output=path.join(root,'native-'+attempt),privateFile=path.join(repo,'work/foundation/test/private/terminal-ui-'+runId+'.json');
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
function regular(file){const value=fs.lstatSync(file);if(value.isSymbolicLink()||!value.isFile())fail('REGULAR_INPUT_REQUIRED');return file;}
const runtimeLock=JSON.parse(fs.readFileSync(regular(path.join(repo,'environment/foundation/runtime-images.lock.json')),'utf8'));
const runtimes=runtimeLock.images.filter(row=>row.component==='python-runtime');
if(runtimeLock.schemaVersion!==1||runtimeLock.status!=='independently-reviewed-local-artifacts'||runtimes.length!==1
    ||!/^sha256:[a-f0-9]{64}$/.test(runtimes[0].reference))fail('APPROVED_NORMAL_RUNTIME_REQUIRED');
const normalAppImage=runtimes[0].reference;
function docker(args,input,timeout=60000){const result=spawnSync('docker.exe',args,{input,encoding:'utf8',timeout,maxBuffer:2*1024*1024,windowsHide:true});
  if(result.error||result.status!==0)fail('SCOPED_DOCKER_COMMAND_FAILED');return result.stdout;}
const frozen=JSON.parse(fs.readFileSync(regular(path.join(root,'http-freeze.json')),'utf8'));
const expectedPaths=['tools/editor_restore_terminal_http_fixture.py','tools/editor_terminal_ui_http_probe.mjs','tools/test-editor-terminal-ui-http.mjs'];
if(frozen.files.length!==3||frozen.files.map(row=>row.path).sort().join()!==expectedPaths.sort().join())fail('CLOSED_QA_FREEZE_REQUIRED');
function verifyQa(){for(const row of frozen.files){const file=path.resolve(repo,row.path);
  if(!file.startsWith(repo+path.sep)||sha(fs.readFileSync(regular(file)))!==row.sha256)fail('RESTORE_TERMINAL_QA_SOURCE_DRIFT');}}
verifyQa();
const manifest=JSON.parse(fs.readFileSync(regular(path.join(repo,'work/foundation/test/manifest.json')),'utf8'));
if(!manifest.active||manifest.environment!=='test'||manifest.composeProject!=='nestakada-foundation-test')fail('ACTIVE_LOCAL_TEST_REQUIRED');
function verifySource(){if(sha(fs.readFileSync(regular(manifest.sourceManifest)))!==manifest.sourceSha256)fail('SOURCE_MANIFEST_DRIFT');
  for(const row of JSON.parse(fs.readFileSync(manifest.sourceManifest,'utf8'))){const file=path.resolve(manifest.sourceDirectory,row.path);
    if(!file.startsWith(path.resolve(manifest.sourceDirectory)+path.sep)||sha(fs.readFileSync(regular(file)))!==row.sha256)fail('FROZEN_APP_DRIFT');}}
function checkServices(probeProfile=false){for(const [kind,caps] of Object.entries({app:[805306368,1000000000,128],db:[1073741824,1000000000,128],ingress:[134217728,250000000,64],'media-worker':[536870912,1000000000,64]})){
  const item=JSON.parse(docker(['inspect','nestakada-foundation-test-'+kind]))[0];
  if(!item.State.Running||item.Config.Labels?.['nestakada.scope']!=='foundation-test'||item.HostConfig.Memory!==caps[0]||item.HostConfig.NanoCpus!==caps[1]||item.HostConfig.PidsLimit!==caps[2])fail('APPROVED_SERVICE_CAPS_REQUIRED');
  const ports=Object.values(item.NetworkSettings.Ports||{}).flatMap(value=>value||[]);
  if(kind==='ingress'){if(ports.length!==1||ports[0].HostIp!=='127.0.0.1'||ports[0].HostPort!=='8767')fail('LOOPBACK_INGRESS_REQUIRED');}
  else if(ports.length)fail('PRIVATE_SERVICE_PUBLISHED');
  if(kind==='app'&&(item.Image!==(probeProfile?appImage:normalAppImage)||!item.Config.Env.includes('DJANGO_SETTINGS_MODULE='+(probeProfile?'probe_settings':'estakada.settings.local_http'))||!item.HostConfig.ReadonlyRootfs||!item.Mounts.some(m=>m.Destination==='/app'&&!m.RW)))fail('EXACT_FROZEN_APP_PROFILE_REQUIRED');}
  const network=JSON.parse(docker(['network','inspect','nestakada-foundation-test-db']))[0];
  if(!network.Internal||network.Labels?.['nestakada.scope']!=='foundation-test')fail('PRIVATE_DB_NETWORK_REQUIRED');}
function verifyRuntime(){const code="import hashlib,json,pathlib; root=pathlib.Path('/app'); suffix={'.py','.lock','.html','.css','.js','.mjs','.svg'}; print(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and p.suffix in suffix}))";
  const actual=JSON.parse(docker(['exec','--user','10001:10001','nestakada-foundation-test-app','python','-B','-c',code]));
  const expected=JSON.parse(fs.readFileSync(manifest.sourceManifest,'utf8'));
  if(Object.keys(actual).length!==expected.length||expected.some(row=>actual[row.path.replaceAll('\\','/')]!==row.sha256))fail('ACTUAL_RUNTIME_SOURCE_DRIFT');}
verifySource();checkServices();verifyRuntime();
const modules=path.join(repo,'work/acceptance-container/acceptance/node_modules');
if(JSON.parse(fs.readFileSync(regular(path.join(modules,'playwright/package.json')),'utf8')).version!=='1.64.1')fail('PINNED_PLAYWRIGHT_REQUIRED');
const browserImageId=JSON.parse(docker(['image','inspect',image]))[0].Id;
if(fs.existsSync(output)||fs.existsSync(privateFile))fail('FRESH_OWN_OUTPUT_REQUIRED');
fs.mkdirSync(output);const screenshots=path.join(output,'screenshots');fs.mkdirSync(screenshots);
const config=path.join(output,'probe-config');fs.mkdirSync(config);
fs.writeFileSync(path.join(config,'probe_settings.py'),"from estakada.settings.local_http import *\nfrom copy import deepcopy\nROOT_URLCONF = 'page_editor.price_test_urls'\nTEMPLATES = deepcopy(TEMPLATES)\nTEMPLATES[0]['DIRS'] = [*TEMPLATES[0].get('DIRS', []), '/app/page_editor/templates']\nMIDDLEWARE = list(MIDDLEWARE)\nif 'page_editor.middleware.EditorAdmissionMiddleware' not in MIDDLEWARE:\n    MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.csrf.CsrfViewMiddleware'), 'page_editor.middleware.EditorAdmissionMiddleware')\n");
const overlay=path.join(output,'compose-http.yaml');
fs.writeFileSync(overlay,'services:\n  app:\n    image: '+appImage+'\n    environment:\n      DJANGO_SETTINGS_MODULE: probe_settings\n      PYTHONPATH: /reservation-probe:/app\n    volumes:\n      - {type: bind, source: '+JSON.stringify(config.replaceAll('\\','/'))+', target: /reservation-probe, read_only: true}\n');
const compose=['compose','--env-file',path.join(repo,'work/foundation/test/compose.env'),'--project-name','nestakada-foundation-test','--file',path.join(repo,'environment/foundation/compose.yaml')];
const fixtureSource=fs.readFileSync(fixture,'utf8');
let seed,runner,report,cleanup,failed=null,stderrBytes=0,overlayStarted=false;
function helper(kind){verifyQa();const request=kind==='seed'?{kind,runId}:{kind,runId,
  userIds:seed.userIds,pageIds:seed.pageIds,routeIds:seed.routeIds,systemRouteIds:seed.systemRouteIds};
  return JSON.parse(docker(['exec','-i','--user','10001:10001','nestakada-foundation-test-app','python','-B','-c',fixtureSource],JSON.stringify(request)));}
function stopOwned(){for(const id of docker(['ps','-aq','--filter','name=^/'+runnerName+'$']).trim().split(/\s+/).filter(Boolean)){
  const item=JSON.parse(docker(['inspect',id]))[0];
  if(item.Image!==browserImageId||item.Name!=='/'+runnerName||item.Config.Labels?.['nestakada.run']!==runId||item.Config.Labels?.['nestakada.scope']!=='editor-http-test')fail('BROWSER_OWNERSHIP_CONFLICT');
  if(item.State.Running)docker(['stop','--time','2',id]);}}
async function ready(){for(let index=0;index<30;index++){
  try{const response=await fetch('http://127.0.0.1:8767/manage/login/',{signal:AbortSignal.timeout(1000)});await response.arrayBuffer();if(response.status===200)return;}catch{}
  await new Promise(resolve=>setTimeout(resolve,500));}fail('TEST_APP_STARTUP_TIMEOUT');}
try{
  docker([...compose,'--file',overlay,'up','-d','--no-deps','app'],undefined,60000);overlayStarted=true;
  await ready();checkServices(true);verifySource();verifyRuntime();
  seed=helper('seed');if(seed.runId!==runId||seed.userIds.length!==3||seed.pageIds.length!==2)fail('OWNED_SEED_REQUIRED');
  fs.writeFileSync(privateFile,JSON.stringify(seed),{flag:'wx',mode:0o600});
  const args=['run','--rm','-i','--init','--pull=never','--name',runnerName,'--label','nestakada.scope=editor-http-test','--label','nestakada.run='+runId,
    '--user','1000:1000','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
    '--memory','1g','--memory-swap','1g','--cpus','2','--pids-limit','256','--shm-size','256m',
    '--tmpfs','/tmp:rw,nosuid,nodev,size=256m,uid=1000,gid=1000,mode=1777','--network','bridge','--add-host','host.docker.internal:host-gateway',
    '--env','HOME=/tmp','--env','CI=1','--mount','type=bind,source='+privateFile+',target=/private/terminal-ui-seed.json,readonly',
    '--mount','type=bind,source='+probe+',target=/qa/editor_terminal_ui_http_probe.mjs,readonly',
    '--mount','type=bind,source='+modules+',target=/tests/node_modules,readonly',
    '--mount','type=bind,source='+screenshots+',target=/evidence',image,'node','/qa/editor_terminal_ui_http_probe.mjs'];
  runner=spawn('docker.exe',args,{stdio:['pipe','pipe','pipe'],windowsHide:true});
  runner.stderr.on('data',bytes=>{stderrBytes+=bytes.length;});let queue=Promise.resolve();
  const lines=readline.createInterface({input:runner.stdout});
  lines.on('line',line=>{queue=queue.then(()=>{if(line.length>16384)fail('BOUNDED_BROWSER_PROTOCOL');const value=JSON.parse(line);
    if(value.kind==='observe'&&Number.isSafeInteger(value.id)&&value.id>0&&value.id<100&&/^RUI-00[123]$/.test(value.caseId)&&value.operation==='observe'){
      runner.stdin.write(JSON.stringify({kind:'observation',id:value.id,value:helper(value.operation)})+'\n');
    }else if(value.kind==='result'&&!report)report=value;else fail('CLOSED_BROWSER_PROTOCOL');
  }).catch(()=>{failed='BROWSER_OBSERVER_FAILED';runner.stdin.end();});});
  const timeout=setTimeout(()=>{failed='BROWSER_DEADLINE';try{stopOwned();}catch{failed='BROWSER_OWNERSHIP_CONFLICT';}},600000);
  const exit=await new Promise(resolve=>{runner.once('error',()=>resolve(-1));runner.once('exit',resolve);});
  clearTimeout(timeout);await queue;lines.close();
  if(exit!==0||report?.status!=='PASS'||report.groups.length!==3||stderrBytes!==0||failed)fail('RESTORE_TERMINAL_NATIVE_FAILED');
  const names=fs.readdirSync(screenshots).sort();if(names.join()!==['terminal-1280.png','terminal-390.png'].sort().join())fail('CLOSED_SCREENSHOTS_REQUIRED');
  for(const name of names){const data=fs.readFileSync(regular(path.join(screenshots,name)));if(data.length>4*1024*1024||data.subarray(0,8).toString('hex')!=='89504e470d0a1a0a')fail('BOUNDED_PNG_REQUIRED');}
  verifyQa();verifySource();verifyRuntime();checkServices(true);
}catch(error){failed=typeof error?.message==='string'&&/^[A-Z0-9_]{1,120}$/.test(error.message)?error.message:'RESTORE_TERMINAL_COORDINATOR_FAILED';}
finally{
  try{stopOwned();}catch{failed=failed||'BROWSER_OWNERSHIP_CONFLICT';}
  if(seed){try{cleanup=helper('close');}catch{failed=failed||'OWNED_FIXTURE_CLEANUP_FAILED';}}
  if(fs.existsSync(privateFile)&&!fs.lstatSync(privateFile).isSymbolicLink())fs.unlinkSync(privateFile);
  if(overlayStarted&&cleanup?.closed){try{docker([...compose,'up','-d','--no-deps','app'],undefined,60000);await ready();checkServices();}catch{failed=failed||'BASE_APP_RESTORE_FAILED';}}
  fs.writeFileSync(path.join(output,'host-report.json'),JSON.stringify({runId,sourceRunId:manifest.runId,
    sourceSha256:manifest.sourceSha256,report,cleanup,failed,stderrBytes,appImage,normalAppImage,playwrightImage:image,qaFreeze:frozen,overlaySha256:sha(fs.readFileSync(overlay))},null,2));
  process.stdout.write(JSON.stringify({pass:!failed,groups:report?.groups||[],cleanup:cleanup?.closed===true,failed})+'\n');
  if(failed)process.exitCode=1;
}






