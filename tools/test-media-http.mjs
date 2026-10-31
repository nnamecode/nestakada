// Host-only coordinator. Docker control never enters the browser container.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import readline from 'node:readline';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const root=path.join(repo,'work/foundation/test');
const origin='http://host.docker.internal:8767';
const image='mcr.microsoft.com/playwright@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea';
const inputs=path.join(repo,'work/dev06-http-20261031/inputs');
const modules=path.join(repo,'work/acceptance-container/acceptance/node_modules');
const fixtureFile=path.join(repo,'tools/media_http_fixture.py');
const runnerFile=path.join(repo,'tools/media_http_probe.mjs');
const coordinatorFile=fileURLToPath(import.meta.url);
const wrapperFile=path.join(repo,'scripts/test-media.ps1');
const collector=path.join(repo,'tools/collect-foundation-evidence.mjs');
const runId=crypto.randomUUID();
const runnerName='nestakada-media-http-'+runId;
const results=path.join(root,'media-http',runId);
const fail=code=>{throw new Error(code);};
function regular(p,dir=false){
  const stat=fs.lstatSync(p);
  if(stat.isSymbolicLink()||(dir?!stat.isDirectory():!stat.isFile()))fail('UNSAFE_INPUT_PATH');
  return p;
}
function checkedQAPath(p){
  const relative=path.relative(repo,path.resolve(p));
  if(relative.startsWith('..')||path.isAbsolute(relative))fail('QA_INPUT_BOUNDARY');
  let current=repo;
  if(fs.lstatSync(current).isSymbolicLink())fail('QA_INPUT_LINK');
  for(const part of relative.split(path.sep)){
    current=path.join(current,part);
    if(fs.lstatSync(current).isSymbolicLink())fail('QA_INPUT_LINK');
  }
  return regular(p);
}
const qaHash=p=>crypto.createHash('sha256').update(fs.readFileSync(checkedQAPath(p))).digest('hex');
const qaRow=p=>({path:path.relative(repo,p).split(path.sep).join('/'),sha256:qaHash(p)});
let qaBefore,qaAfter,qaFiles,qaUnchanged=false;
function captureQAInputs(){
  const manifestPath=path.join(inputs,'inputs.json');
  const declared=JSON.parse(fs.readFileSync(checkedQAPath(manifestPath),'utf8'));
  const names=Object.keys(declared).sort();
  const expected=['valid.png','valid.jpg','valid.webp','boundary.png','over.png','truncated.png','active.svg','active.html','pixel-over.png'].sort();
  if(JSON.stringify(names)!==JSON.stringify(expected))fail('SYNTHETIC_INPUT_SET_CHANGED');
  for(const name of names){
    if(!/^[a-z][a-z0-9-]*\.(?:png|jpg|webp|svg|html)$/u.test(name)||path.basename(name)!==name||declared[name]?.name!==name)fail('SYNTHETIC_INPUT_BASENAME');
    const file=path.join(inputs,name),stat=fs.statSync(checkedQAPath(file));
    if(stat.size!==declared[name].bytes||qaHash(file)!==declared[name].sha256)fail('SYNTHETIC_INPUT_DECLARATION');
  }
  qaFiles=[fixtureFile,runnerFile,coordinatorFile,wrapperFile,manifestPath,...names.map(name=>path.join(inputs,name))];
  qaBefore=qaFiles.map(qaRow);
}
function bounded(command,args,{input,timeout=60_000}={}){
  const result=spawnSync(command,args,{input,encoding:'utf8',timeout,maxBuffer:16*1024*1024,windowsHide:true});
  if(result.error||result.status!==0)fail('BOUNDED_LOCAL_COMMAND_FAILED');
  return result.stdout;
}
function observer(kind,seed,knownFiles=[]){
  const request=kind==='seed'?{kind,runId}:{kind,runId,userIds:seed.userIds,pageIds:seed.pageIds,...(kind==='observe'?{knownFiles}:{})};
  // Program text is nonsecret. Credentials and fixture operation JSON enter only stdin.
  const program=fs.readFileSync(checkedQAPath(fixtureFile));
  const expected=qaBefore?.find(row=>row.path==='tools/media_http_fixture.py')?.sha256;
  if(!expected||crypto.createHash('sha256').update(program).digest('hex')!==expected)fail('FIXTURE_SOURCE_CHANGED');
  const value=bounded('docker.exe',['exec','-i','nestakada-foundation-test-app','python','-c',program.toString('utf8')],{input:JSON.stringify(request)});
  return JSON.parse(value);
}
let seed,guardSha,result,failure,cleanupFailure,expectedRunnerImage,runnerTimer,runnerLaunched=false;
const known=new Map();
try{
  if(process.argv.length!==2)fail('NO_ARGUMENTS_ALLOWED');
  regular(root,true);
  const manifest=JSON.parse(fs.readFileSync(regular(path.join(root,'manifest.json')),'utf8'));
  if(!manifest.active||manifest.environment!=='test'||manifest.composeProject!=='nestakada-foundation-test'||manifest.containers?.app!=='nestakada-foundation-test-app')fail('ACTIVE_EXCLUSIVE_TEST_MANIFEST_REQUIRED');
  for(const p of [fixtureFile,runnerFile,collector,path.join(inputs,'inputs.json'),path.join(modules,'playwright/index.mjs'),path.join(modules,'@playwright/test/package.json')])regular(p);
  for(const p of [inputs,modules])regular(p,true);
  captureQAInputs();
  if(JSON.parse(fs.readFileSync(path.join(modules,'@playwright/test/package.json'),'utf8')).version!=='1.64.1')fail('APPROVED_PLAYWRIGHT_PACKAGE_REQUIRED');
  expectedRunnerImage=JSON.parse(bounded('docker.exe',['image','inspect',image]))[0].Id;
  if(!/^sha256:[a-f0-9]{64}$/u.test(expectedRunnerImage??''))fail('RUNNER_IMAGE_ID_REQUIRED');
  if(bounded('docker.exe',['ps','-aq','--filter','name=^/'+runnerName+'$']).trim())fail('OWN_RUNNER_NAME_ALREADY_EXISTS');
  // Same immutable source/images/worker/container evidence guard as foundation tests.
  bounded(process.execPath,[collector],{timeout:120_000});
  guardSha=crypto.createHash('sha256').update(fs.readFileSync(regular(path.join(root,'evidence/guard.json')))).digest('hex');
  bounded(process.execPath,[collector,'--verify',guardSha],{timeout:120_000});
  seed=observer('seed');
  if(seed.runId!==runId||seed.pageIds?.length!==3||seed.userIds?.length!==2||!seed.accounts?.owner?.password||!seed.accounts?.employee?.password)fail('SEED_CONTRACT');
  fs.mkdirSync(results,{recursive:true});
  const args=['run','--rm','-i','--init','--pull=never','--name',runnerName,'--label','nestakada.scope=media-http-test','--label','nestakada.run='+runId,'--user','1000:1000',
    '--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true','--memory=2g','--cpus=2','--pids-limit=256','--shm-size=512m',
    '--network','bridge','--add-host','host.docker.internal:host-gateway',
    '--tmpfs','/tmp:rw,nosuid,nodev,size=256m,uid=1000,gid=1000,mode=1777',
    '--env','HOME=/tmp','--env','CI=1','--env','XDG_CACHE_HOME=/tmp/cache',
    '--mount','type=bind,source='+modules+',target=/tests/node_modules,readonly',
    '--mount','type=bind,source='+runnerFile+',target=/runner/probe.mjs,readonly',
    '--mount','type=bind,source='+inputs+',target=/inputs,readonly',
    '--mount','type=bind,source='+results+',target=/results',
    '--workdir','/tmp',image,'node','/runner/probe.mjs'];
  runnerLaunched=true;
  const child=spawn('docker.exe',args,{stdio:['pipe','pipe','pipe'],windowsHide:true});
  const stdout=readline.createInterface({input:child.stdout,terminal:false});
  let lastId=0,invalid=false,stderrBytes=0;
  child.stderr.on('data',chunk=>{stderrBytes+=chunk.length;});
  child.stdin.on('error',()=>{invalid=true;});
  runnerTimer=setTimeout(()=>{invalid=true;child.kill();},300_000);
  stdout.on('line',line=>{
    try{
      if(line.length>128*1024)fail('RUNNER_LINE_LIMIT');
      const msg=JSON.parse(line);
      if(msg.kind==='observe'){
        if(Object.keys(msg).sort().join(',')!=='id,kind'||!Number.isInteger(msg.id)||msg.id!==lastId+1||msg.id>120)fail('RUNNER_CONTROL_REJECTED');
        lastId=msg.id;
        const state=observer('observe',seed,[...known.values()]);
        for(const asset of state.assets)for(const file of asset.files)known.set(file.key,{assetId:asset.id,key:file.key});
        child.stdin.write(JSON.stringify({kind:'observation',id:msg.id,value:state})+'\n');
      }else if(msg.kind==='result'){
        if(result)fail('MULTIPLE_RUNNER_RESULTS');
        result=msg;
      }else fail('RUNNER_PROTOCOL');
    }catch{
      invalid=true;
      child.stdin.write(JSON.stringify({kind:'observation',id:lastId,error:true})+'\n');
      child.kill();
    }
  });
  child.stdin.write(JSON.stringify({kind:'seed',origin,fixture:seed})+'\n');
  const code=await new Promise((resolve,reject)=>{child.on('error',()=>reject(new Error('RUNNER_LAUNCH_FAILED')));child.on('close',resolve);});
  clearTimeout(runnerTimer);stdout.close();
  bounded(process.execPath,[collector,'--verify',guardSha],{timeout:120_000});
  if(invalid||code!==0||result?.status!=='PASS')fail('MEDIA_HTTP_SUITE_FAILED');
  // Report only reviewed fields. No raw stderr/options/cookies/credentials are emitted.
  if(stderrBytes>256*1024)fail('RUNNER_DIAGNOSTIC_LIMIT');
}catch(error){
  failure=/^[A-Z0-9_-]{1,100}$/u.test(error.message??'')?error.message:'MEDIA_HTTP_COORDINATOR_ERROR';
}finally{
  clearTimeout(runnerTimer);
  // Killing the Docker CLI is not proof that its container stopped. Stop only this labelled, pinned runner.
  if(runnerLaunched){
    try{
      const found=bounded('docker.exe',['ps','-aq','--filter','name=^/'+runnerName+'$']).trim();
      if(found){
        if(!/^[a-f0-9]{12,64}$/u.test(found))fail('OWN_RUNNER_LOOKUP');
        const actual=JSON.parse(bounded('docker.exe',['inspect',runnerName]))[0];
        if(actual.Name!=='/'+runnerName||actual.Image!==expectedRunnerImage||actual.Config?.Image!==image||
           actual.Config?.Labels?.['nestakada.scope']!=='media-http-test'||actual.Config?.Labels?.['nestakada.run']!==runId)fail('OWN_RUNNER_IDENTITY_MISMATCH');
        if(actual.State.Running)bounded('docker.exe',['stop','--time','3',runnerName],{timeout:15_000});
      }
    }catch{cleanupFailure='OWN_BROWSER_CONTAINER_STOP_NOT_CONFIRMED';}
  }
  if(seed&&!cleanupFailure){
    try{
      const closed=observer('close',seed);
      if(!closed.closed||closed.remainingUsers!==0||closed.remainingAssets!==0)fail('CLOSE_CONTRACT');
    }catch{cleanupFailure='OWNED_FIXTURE_CLEANUP_INCOMPLETE-preserved-for-investigation';}
  }
  if(guardSha){
    try{bounded(process.execPath,[collector,'--verify',guardSha],{timeout:120_000});}
    catch{failure??='FOUNDATION_GUARD_FAILED';}
  }
  if(qaBefore){
    try{
      qaAfter=qaFiles.map(qaRow);
      qaUnchanged=JSON.stringify(qaBefore)===JSON.stringify(qaAfter);
      if(!qaUnchanged)failure??='QA_SCRIPTS_OR_INPUTS_DRIFT';
    }catch{failure??='QA_SCRIPTS_OR_INPUTS_DRIFT';}
  }
}
const report={runId,origin,status:failure||cleanupFailure?'FAIL':'PASS',checks:result?.passed??[],
  qaProvenance:{before:qaBefore??[],after:qaAfter??[],unchanged:qaUnchanged},
  ...(result?.failedAt?{failedAt:result.failedAt,code:result.code}:{}),
  notChecked:result?.notChecked??[],fixtureClosed:Boolean(seed&&!cleanupFailure),...(failure?{failure}:{}),...(cleanupFailure?{cleanupFailure}:{})};
if(fs.existsSync(results))fs.writeFileSync(path.join(results,'report.json'),JSON.stringify(report,null,2)+'\n','utf8');
console.log(JSON.stringify(report));
if(report.status!=='PASS')process.exitCode=1;
