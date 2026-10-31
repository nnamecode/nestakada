// Host-only fixture coordinator. Fixed test helpers; no arbitrary command/path API.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const root=path.join(repo,'work/foundation/test');
const fixtureRoot=path.join(root,'auth');
const origin='http://host.docker.internal:8767';
const credential=JSON.parse(fs.readFileSync(path.join(fixtureRoot,'runner/control.json'),'utf8'));
if(credential.origin!=='http://host.docker.internal:8770'||!/^[a-f0-9]{96}$/u.test(credential.token??''))throw new Error('AUTH_CONTROLLER_CREDENTIAL_INVALID');
const manifestBytes=fs.readFileSync(path.join(root,'manifest.json'));
const manifest=JSON.parse(manifestBytes), source=fs.readFileSync(path.join(repo,'tools/auth_fixture.py'),'utf8');
if(!manifest.active||manifest.environment!=='test'||manifest.composeProject!=='nestakada-foundation-test')throw new Error('AUTH_CONTROLLER_SCOPE_INVALID');
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const manifestHash=crypto.createHash('sha256').update(manifestBytes).digest('hex');
function checkSource() {
  if(sha(manifest.sourceManifest)!==manifest.sourceSha256)throw new Error('AUTH_SOURCE_MANIFEST_CHANGED');
  for(const row of JSON.parse(fs.readFileSync(manifest.sourceManifest,'utf8'))) {
    const p=path.resolve(manifest.sourceDirectory,row.path),rel=path.relative(manifest.sourceDirectory,p);
    if(rel.startsWith('..')||path.isAbsolute(rel)||fs.lstatSync(p).isSymbolicLink()||sha(p)!==row.sha256)throw new Error('AUTH_SOURCE_CHANGED');
  }
}
function docker(args,input) {
  const p=spawnSync('docker',args,{input,encoding:'utf8',timeout:20_000,maxBuffer:256*1024,windowsHide:true});
  if(p.error||p.status!==0)throw new Error('AUTH_FIXED_DOCKER_OPERATION_FAILED');
  return JSON.parse(p.stdout);
}
let activeRun, activeControllerContainers, ownedUserIds=[];
function saveState() {
  fs.writeFileSync(path.join(fixtureRoot,'controller-state.json'),JSON.stringify({controllerPid:process.pid,runId:activeRun??null,ownedUserIds}),'utf8');
}
function actualSources() {
  if(sha(path.join(root,'manifest.json'))!==manifestHash)throw new Error('AUTH_MANIFEST_CHANGED');
  checkSource();
  const rows=docker(['inspect','nestakada-auth-source-a','nestakada-auth-source-b','nestakada-foundation-test-app']);
  for(const [i,c]of rows.entries())if(!c.State.Running||c.Config.Labels['nestakada.scope']!==(i===2?'foundation-test':'auth-fixture-test'))throw new Error('AUTH_CONTAINER_SCOPE_INVALID');
  for(const c of rows.slice(0,2))if(c.Image!=='sha256:a3b293bbab17bfd78d82d2392240d3d351501fba538ab82de1595b1d28d0d646'||
    Object.keys(c.NetworkSettings.Networks).join()!=='nestakada-foundation-test-ingress')throw new Error('AUTH_SOURCE_PROXY_IMAGE_OR_NETWORK_CHANGED');
  const app=rows[2];
  if(!app.Config.Env.includes('DJANGO_SETTINGS_MODULE=estakada.settings.auth_isolated')||
      !app.Mounts.some(m=>m.Destination==='/run/auth-fixture'&&!m.RW))throw new Error('AUTH_CLOCK_MOUNT_REQUIRED');
  const ids=rows.map(c=>`${c.Id}:${c.State.StartedAt}`);
  if(activeControllerContainers && JSON.stringify(ids)!==JSON.stringify(activeControllerContainers))throw new Error('AUTH_CONTAINERS_CHANGED');
  activeControllerContainers=ids;
  const sourceAIp=rows[0].NetworkSettings.Networks['nestakada-foundation-test-ingress']?.IPAddress;
  const sourceBIp=rows[1].NetworkSettings.Networks['nestakada-foundation-test-ingress']?.IPAddress;
  if(!sourceAIp||!sourceBIp||sourceAIp===sourceBIp)throw new Error('AUTH_DISTINCT_REAL_SOURCES_REQUIRED');
  return {sourceAIp,sourceBIp};
}
function helper(request) {
  const payload={...request,...actualSources(),previousIds:ownedUserIds};
  // Script is fixed repository code, credentials travel only via stdin/stdout, not argv/env.
  return docker(['exec','-i',manifest.containers.app,'python','-c',source],JSON.stringify(payload));
}
function validate(request) {
  if(request.protocol!=='estakada-fixture-v1'||request.targetOrigin!==origin||!/^[a-f0-9]{48}$/u.test(request.nonce??''))throw new Error('AUTH_REQUEST_SCOPE_INVALID');
  if(request.kind==='reset') {
    if(activeRun||request.profile!=='auth-login-isolated-sources'||request.phase!=='before-ui'||request.runId)throw new Error('AUTH_RESET_SCOPE_INVALID');
  }else if(!activeRun||request.runId!==activeRun||!['observe','close'].includes(request.kind))throw new Error('AUTH_RUN_MISMATCH');
  if(request.kind==='observe'&&!['auth-fixture-identifiers','auth-source-state'].includes(request.view))throw new Error('AUTH_OBSERVER_NOT_ALLOWED');
}
const server=http.createServer(async(req,res)=>{
  try {
    if(req.method!=='POST'||req.url!=='/control'||req.headers.authorization!==`Bearer ${credential.token}`)throw new Error('AUTH_CONTROL_DENIED');
    let body='';for await(const chunk of req){body+=chunk;if(body.length>32768)throw new Error('AUTH_INPUT_LIMIT');}
    const request=JSON.parse(body);validate(request);
    let data,sourceKind;
    if(request.kind==='reset') {
      actualSources();
      fs.writeFileSync(path.join(fixtureRoot,'clock/clock.json'),JSON.stringify({now:new Date().toISOString()}),'utf8');
      data=helper(request);ownedUserIds=data.ownedUserIds;delete data.ownedUserIds;
      activeRun=crypto.randomUUID();saveState();sourceKind='actual-fixture';
    } else if(request.kind==='observe') {data=helper(request);sourceKind='actual-db';}
    else {data=helper(request);ownedUserIds=[];sourceKind='actual-fixture';}
    res.writeHead(200,{'content-type':'application/json','cache-control':'no-store'});
    res.end(JSON.stringify({protocol:request.protocol,nonce:request.nonce,ok:true,targetOrigin:origin,runId:activeRun,source:sourceKind,data,
      evidence:{fixtureVersion:'auth-real-db-v1',fixtureProfile:'auth-login-isolated-sources'}}));
    if(request.kind==='close'){activeRun=undefined;saveState();}
  } catch {res.writeHead(400,{'content-type':'application/json'});res.end('{"ok":false,"error":"AUTH_FIXED_FIXTURE_FAILED"}');}
});
server.listen(8770,'127.0.0.1',()=>{saveState();fs.writeFileSync(path.join(fixtureRoot,'controller-ready.json'),JSON.stringify({pid:process.pid,manifestHash}),'utf8');});
