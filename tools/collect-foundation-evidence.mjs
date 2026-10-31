// Host-only fixed observer. Never mount the Docker socket in the application/test runner.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const root = path.join(repo, 'work/foundation/test');
const read = p => fs.readFileSync(p);
const json = p => JSON.parse(read(p));
const hash = p => crypto.createHash('sha256').update(read(p)).digest('hex');
const fail = message => { throw new Error(message); };
function requireSameGuard(expected, actual) {
  if (JSON.stringify(expected) !== JSON.stringify(actual)) fail('Foundation evidence drift detected; acceptance result is invalid');
}
function requireGuardAnchor(expectedSha256, bytes) {
  if (!/^[a-f0-9]{64}$/u.test(expectedSha256??'') || crypto.createHash('sha256').update(bytes).digest('hex')!==expectedSha256)
    fail('Foundation guard anchor mismatch; acceptance result is invalid');
}
if (process.argv[2] === '--selfcheck') {
  const fixture={runId:'run-a',manifestSha256:'manifest-a',sourceSha256:'source-a',snapshotSha256:'snapshot-a',nginxSha256:'nginx-a',workerSourceSha256:'worker-source-a',workerReceiptSha256:'worker-receipt-a',containers:{app:{id:'app-a',startedAt:'time-a'},db:{id:'db-a'},ingress:{id:'nginx-a'},'media-worker':{id:'worker-a'}}};
  requireSameGuard(fixture,structuredClone(fixture));
  for (const key of ['runId','manifestSha256','sourceSha256','snapshotSha256','nginxSha256','workerSourceSha256','workerReceiptSha256']) {
    const changed=structuredClone(fixture); changed[key]+='-changed';
    let rejected=false; try {requireSameGuard(fixture,changed);} catch {rejected=true;}
    if(!rejected)fail(`Guard selfcheck missed ${key}`);
  }
  for(const service of ['app','db','ingress','media-worker']) {
    const changed=structuredClone(fixture); changed.containers[service].id+='-changed';
    let rejected=false;try {requireSameGuard(fixture,changed);} catch {rejected=true;}
    if(!rejected)fail(`Guard selfcheck missed ${service}`);
  }
  const originalBytes=Buffer.from(JSON.stringify(fixture));
  const anchor=crypto.createHash('sha256').update(originalBytes).digest('hex');
  requireGuardAnchor(anchor,originalBytes);
  const replaced=structuredClone(fixture);replaced.runId='run-b';replaced.snapshotSha256='snapshot-b';
  const replacementBytes=Buffer.from(JSON.stringify(replaced));
  // A simultaneous guard+snapshot replacement is internally consistent, but cannot replace the wrapper's anchor.
  requireSameGuard(replaced,structuredClone(replaced));
  let swapRejected=false;try{requireGuardAnchor(anchor,replacementBytes);}catch{swapRejected=true;}
  if(!swapRejected)fail('Guard selfcheck missed simultaneous guard/snapshot replacement');
  console.log('Drift guard selfcheck passed: unchanged accepted; run/manifest/source/snapshot/nginx/container substitution rejected');
  process.exit(0);
}
if ((process.argv[2] && process.argv[2]!=='--verify') ||
    (process.argv[2]==='--verify' ? (process.argv.length!==4 || !/^[a-f0-9]{64}$/u.test(process.argv[3])) : process.argv.length!==2))
  fail('Usage: collector [--verify <guard-sha256>]');
const within = (p, base) => { const rel = path.relative(base,p); return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel)); };
function canonical(p) {
  let value = p.replaceAll('\\','/').replace(/^\/run\/desktop\/mnt\/host\/([a-z])\//i, '$1:/');
  value = value.replace(/^\/host_mnt\/([a-z])\//i, '$1:/');
  return value.replace(/\/+$/u,'').toLowerCase();
}
function docker(args, input) {
  const p = spawnSync('docker',args,{input,encoding:'utf8',timeout:30_000,maxBuffer:8*1024*1024,windowsHide:true});
  if (p.error || p.status !== 0) fail(`Fixed Docker observation failed: ${args[0]} (output withheld)`);
  return {stdout:p.stdout,stderr:p.stderr};
}
function noLink(p) { if (fs.lstatSync(p).isSymbolicLink()) fail('Symlink in evidence source'); }
const manifestPath = path.join(root,'manifest.json');
const initialManifestSha256 = hash(manifestPath);
const manifest = json(manifestPath);
const services=['app','db','ingress','media-worker'];
if (!manifest.active || manifest.environment !== 'test' || manifest.composeProject !== 'nestakada-foundation-test') fail('Active test scope required');
if (!within(manifest.sourceDirectory,path.join(root,'sources')) || !within(manifest.sourceManifest,root) || canonical(manifest.privateDirectory)!==canonical(path.join(root,'private'))) fail('Manifest boundaries rejected');
function checkSource() {
  noLink(manifest.sourceDirectory); noLink(manifest.sourceManifest);
  if (hash(manifest.sourceManifest)!==manifest.sourceSha256) fail('Source manifest changed');
  const rows=json(manifest.sourceManifest), expected=new Set();
  for (const row of rows) {
    const p=path.resolve(manifest.sourceDirectory,row.path);
    if (!within(p,manifest.sourceDirectory)) fail('Source file escaped snapshot');
    noLink(p); if (hash(p)!==row.sha256) fail('Source file changed'); expected.add(canonical(p));
  }
  function walk(dir) { for(const d of fs.readdirSync(dir,{withFileTypes:true})) {
    const p=path.join(dir,d.name); noLink(p);
    if(d.isDirectory())walk(p); else if(!expected.has(canonical(p)))fail('Untracked file in immutable snapshot');
  }}
  walk(manifest.sourceDirectory);
  if (!within(manifest.workerSourceDirectory,path.join(root,'worker-sources')) || !within(manifest.workerSourceManifest,root)) fail('Worker snapshot boundary rejected');
  noLink(manifest.workerSourceDirectory); noLink(manifest.workerSourceManifest);
  if(hash(manifest.workerSourceManifest)!==manifest.workerSourceSha256)fail('Worker manifest changed');
  const workerReceiptPath=path.join(repo,'environment/media-worker/candidate-receipt.json');
  if(hash(workerReceiptPath)!==manifest.workerReceiptSha256)fail('Worker receipt changed');
  const receipt=json(workerReceiptPath), rowsWorker=json(manifest.workerSourceManifest);
  if(receipt.status!=='independently-reviewed-for-local-integration'||JSON.stringify(rowsWorker)!==JSON.stringify(receipt.workerSource))fail('Worker source is not admitted');
  if(rowsWorker.map(r=>r.name).sort().join(',')!=='probe.py,test_worker.py,worker.py')fail('Worker source set changed');
  for(const row of rowsWorker) {
    const p=path.join(manifest.workerSourceDirectory,row.name);noLink(p);
    if(hash(p)!==row.sha256)fail('Worker snapshot changed');
  }
  if(fs.readdirSync(manifest.workerSourceDirectory).length!==rowsWorker.length)fail('Extra worker snapshot files');
}
function inspect() {
  return Object.fromEntries(services.map(service=>{
    const name=`nestakada-foundation-test-${service}`;
    if(manifest.containers[service]!==name)fail('Container name mismatch');
    const item=JSON.parse(docker(['inspect',name]).stdout)[0];
    if(!item.State.Running || item.Config.Labels['nestakada.scope']!=='foundation-test' || item.Config.Labels['com.docker.compose.project']!==manifest.composeProject)fail('Container scope/state mismatch');
    return [service,item];
  }));
}
const output=path.join(root,'evidence/current.json');
const guardPath=path.join(root,'evidence/guard.json');
const nginxConfigPath=path.join(repo,'environment/foundation/local-nginx.conf');
function guardState(containers, snapshotSha256=hash(output)) {
  return {runId:manifest.runId,manifestSha256:hash(manifestPath),sourceSha256:manifest.sourceSha256,
    snapshotSha256,nginxSha256:hash(nginxConfigPath),workerSourceSha256:manifest.workerSourceSha256,workerReceiptSha256:manifest.workerReceiptSha256,containers:Object.fromEntries(services.map(service=>{
      const c=containers[service];
      const metadata={image:c.Image,hostConfig:c.HostConfig,mounts:c.Mounts,networks:c.NetworkSettings.Networks,ports:c.NetworkSettings.Ports};
      return [service,{id:c.Id,startedAt:c.State.StartedAt,restartCount:c.RestartCount,
        metadataSha256:crypto.createHash('sha256').update(JSON.stringify(metadata)).digest('hex')}];
    }))};
}
if(process.argv[2]==='--verify') {
  const guardBytes=read(guardPath);
  requireGuardAnchor(process.argv[3],guardBytes);
  checkSource();
  requireSameGuard(JSON.parse(guardBytes),guardState(inspect()));
  requireGuardAnchor(process.argv[3],read(guardPath));
  console.log(`Foundation evidence guard verified for ${manifest.runId}`);
  process.exit(0);
}
checkSource();
const containers=inspect(), observations={};
const initialGuardState=guardState(containers,'');
const initialNginxSha256=hash(nginxConfigPath);
const probe=read(path.join(repo,'tools/foundation_probe.py'));
function observe(view,profile='local-http') {
  const value=JSON.parse(docker(['exec','-i',manifest.containers.app,'python','-',view,profile],probe).stdout);
  (observations[view]??={})[profile]=value; return value;
}
for(const view of ['foundation-runtime-versions','foundation-settings','foundation-db-roles','foundation-dependencies','foundation-audit-redaction'])observe(view);
observe('foundation-settings','deployment-audit'); observe('foundation-deploy-check','deployment-audit');
const nginx=docker(['exec',manifest.containers.ingress,'nginx','-v']);
const nginxMatch=(nginx.stdout+nginx.stderr).match(/nginx\/(\d+\.\d+\.\d+)/u);
if(!nginxMatch)fail('Nginx version unavailable');
observations['foundation-runtime-versions']['local-http'].nginxVersion=nginxMatch[1];
const ports=c=>Object.values(c.NetworkSettings.Ports??{}).flatMap(v=>(v??[]).map(b=>({hostIp:b.HostIp,hostPort:b.HostPort})));
const network=c=>Object.keys(c.NetworkSettings.Networks??{});
const app=containers.app, db=containers.db, ingress=containers.ingress;
const approvedSecrets=new Set(['database-password','django-secret','deployment-django-secret','database-ca']);
const mounts=(app.Mounts??[]).map(m=>{
  const source=canonical(m.Source??''), target=m.Destination;
  let purpose='unapproved', approved=false;
  if(target==='/app' && m.Type==='bind') {purpose='source';approved=source===canonical(manifest.sourceDirectory);}
  else if(target.startsWith('/run/secrets/') && m.Type==='bind') {
    purpose='secret'; const name=target.slice('/run/secrets/'.length), file=name==='database-password'?'runtime-password':name;
    approved=approvedSecrets.has(name)&&source===canonical(path.join(manifest.privateDirectory,file));
  } else if(target==='/var/lib/estakada'&&m.Type==='volume') {purpose='runtime-data';approved=m.Name==='nestakada-foundation-test-state';}
  else if(target==='/exchange'&&m.Type==='volume') {purpose='media-exchange';approved=m.Name==='nestakada-foundation-test-media-exchange';}
  else if(target==='/tmp'&&m.Type==='tmpfs') {purpose='runtime-temp';approved=true;}
  return {type:m.Type,target,purpose,readOnly:!m.RW,sourceWithinApprovedBoundary:approved,currentFixtureOnly:approved};
});
const actualImage=JSON.parse(docker(['image','inspect',app.Image]).stdout)[0];
const isolation={platform:`${actualImage.Os}/${actualImage.Architecture}`,appUid:Number(docker(['exec',manifest.containers.app,'id','-u']).stdout.trim()),
  privileged:app.HostConfig.Privileged,noNewPrivileges:(app.HostConfig.SecurityOpt??[]).some(x=>x==='no-new-privileges:true'||x==='no-new-privileges'),capDrop:app.HostConfig.CapDrop??[],capAdd:app.HostConfig.CapAdd??[],
  mountAuditSource:'host-docker-inspect-and-canonical-sources',appMounts:mounts,
  hostRootSourceMounted:(app.Mounts??[]).some(m=>/^(?:[a-z]:|\/)\/?$/iu.test(canonical(m.Source??''))),
  hostProfileSourceMounted:(app.Mounts??[]).some(m=>/^[a-z]:\/users(?:\/|$)/iu.test(canonical(m.Source??''))),
  engineSocketSourceMounted:(app.Mounts??[]).some(m=>/(?:docker|containerd)\.sock|docker_engine/iu.test(`${m.Source} ${m.Destination}`)),outsideApprovedSourcesMounted:mounts.some(m=>!m.sourceWithinApprovedBoundary),
  databasePublishedPorts:ports(db),appPublishedPorts:ports(app),ingressPublishedPorts:ports(ingress),
  ingressHasDatabaseNetwork:network(ingress).includes('nestakada-foundation-test-db'),appHasIngressNetwork:network(app).includes('nestakada-foundation-test-ingress'),databaseHasWebNetwork:network(db).includes('nestakada-foundation-test-web'),
  hostNetwork:app.HostConfig.NetworkMode==='host',hostPidNamespace:app.HostConfig.PidMode==='host',databaseDataMountTarget:(db.Mounts??[]).find(m=>m.Name==='nestakada-foundation-test-dbdata')?.Destination};
observations['foundation-isolation']={'local-http':isolation};
const worker=containers['media-worker'];
const workerReceipt=json(path.join(repo,'environment/media-worker/candidate-receipt.json'));
const exchangeVolume=JSON.parse(docker(['volume','inspect','nestakada-foundation-test-media-exchange']).stdout)[0];
isolation.mediaWorker={image:worker.Image,lockedImage:workerReceipt.dockerReportedImageId,uid:worker.Config.User,
  networkMode:worker.HostConfig.NetworkMode,ports:ports(worker),privileged:worker.HostConfig.Privileged,
  readonly:worker.HostConfig.ReadonlyRootfs,capDrop:worker.HostConfig.CapDrop??[],capAdd:worker.HostConfig.CapAdd??[],
  securityOpt:worker.HostConfig.SecurityOpt??[],memory:worker.HostConfig.Memory,memorySwap:worker.HostConfig.MemorySwap,
  nanoCpus:worker.HostConfig.NanoCpus,pids:worker.HostConfig.PidsLimit,
  mounts:worker.Mounts.map(m=>({target:m.Destination,readOnly:!m.RW,type:m.Type,
    approved:m.Destination==='/worker'&&m.Type==='bind'&&!m.RW&&canonical(m.Source)===canonical(manifest.workerSourceDirectory)||
      m.Destination==='/exchange'&&m.Type==='volume'&&m.RW&&m.Name==='nestakada-foundation-test-media-exchange'||
      m.Destination==='/tmp'&&m.Type==='tmpfs'})),
  exchange:{driver:exchangeVolume.Driver,options:exchangeVolume.Options,label:exchangeVolume.Labels['nestakada.scope']}};
const basePath=path.join(repo,'environment/foundation');
const runtime=json(path.join(basePath,'runtime-images.lock.json'));
const materialLock=json(path.join(basePath,'images.lock.json'));
const archiveLock=json(path.join(basePath,'source-archives.lock.json'));
const builds=[],materials=[];
for(const row of runtime.images) {
  const build={component:row.component,lockedDockerImageId:row.reference,materialComponents:row.materialComponents};
  for(const field of ['recipe','inputs','receipt']) {
    const p=path.resolve(repo,row[field].path); if(!within(p,repo))fail('Build evidence escaped repository');
    build[`${field}LockedSha256`]=row[field].sha256; build[`${field}ObservedSha256`]=hash(p);
    if(hash(p)!==row[field].sha256)fail('Build evidence hash mismatch');
  }
  const receipt=json(path.join(repo,row.receipt.path));
  build.builtDockerImageId=receipt['containerimage.digest'];
  const service={'python-runtime':'app',postgres:'db','local-ingress':'ingress'}[row.component];
  build.runningDockerImageId=containers[service].Image;
  const runningImage=JSON.parse(docker(['image','inspect',containers[service].Image]).stdout)[0];
  build.platform=`${runningImage.Os}/${runningImage.Architecture}`;
  const receiptMaterials=receipt['buildx.build.provenance'].materials;
  for(const component of row.materialComponents) {
    const locked=materialLock.images.find(m=>m.component===component);
    const repository=locked.reference.split('@')[0];
    const observed=receiptMaterials.find(m=>m.uri.startsWith(`pkg:docker/${repository}?`));
    if(!observed)fail('Build material not present in actual receipt');
    materials.push({component,platform:receipt['buildx.build.provenance'].invocation.environment.platform,
      lockedManifestDigest:locked.manifestDigest,observedBuildMaterialDigest:`sha256:${observed.digest.sha256}`});
  }
  builds.push(build);
}
const archives=archiveLock.archives.map(a=>({component:a.component,lockedSha256:a.sha256,observedSha256:hash(path.join(repo,'work/foundation-security-20261030',a.component==='postgres-source'?'pg-context':'python-context',a.filename))}));
const dep=observations['foundation-dependencies']['local-http'];
const lockPath=path.join(basePath,'requirements.lock'), lockFileSha256=hash(lockPath);
const normalized=s=>s.toLowerCase().replace(/[-_.]+/gu,'-');
const lockedRuntimePackages=read(lockPath).toString('utf8').trim().split(/\r?\n/u).map(line=>{
  const m=line.match(/^([\w.-]+)==([^ ]+) --hash=sha256:([a-f0-9]{64})$/u);if(!m)fail('Unsupported runtime requirement declaration');
  const artifact=dep.artifacts.find(a=>normalized(a.name)===normalized(m[1])&&a.version===m[2]);if(!artifact)fail('Runtime wheel absent');
  return {name:normalized(m[1]),version:m[2],declaredHashSha256:m[3],artifactSha256:artifact.artifactSha256};
});
observations['foundation-dependency-evidence']={'local-http':{lockedRuntimePackages,installedRuntimePackages:dep.installed.filter(p=>p.name!=='pip'),bootstrapPackages:dep.installed.filter(p=>p.name==='pip'),sourceMaterials:materials,sourceArchives:archives,runtimeBuilds:builds,lockFileSha256,
  applicationImage:{mode:'runtime-image-with-readonly-source',runningDockerImageId:app.Image,builtDockerImageId:builds.find(b=>b.component==='python-runtime').builtDockerImageId,buildBaseDockerImageId:builds.find(b=>b.component==='python-runtime').lockedDockerImageId,dependencyLockSha256:dep.appDependencyLockSha256,sourceSha256:manifest.sourceSha256}}};
delete observations['foundation-dependencies'];
checkSource(); const after=inspect();
requireSameGuard(initialGuardState,guardState(after,''));
if(hash(manifestPath)!==initialManifestSha256 || hash(nginxConfigPath)!==initialNginxSha256)fail('Manifest or ingress configuration changed during observation');
const snapshot={runId:manifest.runId,fixtureProfile:'local-foundation-isolated',targetOrigin:'http://host.docker.internal:8767',observedAt:new Date().toISOString(),sourceSha256:manifest.sourceSha256,applicationMode:'runtime-image-with-readonly-source',provenance:{collector:'host-docker-exec-inspect',probeSha256:crypto.createHash('sha256').update(probe).digest('hex'),sourceVerifiedBeforeAndAfter:true},observations};
fs.mkdirSync(path.dirname(output),{recursive:true}); fs.writeFileSync(output,JSON.stringify(snapshot,null,2),'utf8');
fs.writeFileSync(guardPath,JSON.stringify(guardState(after),null,2),'utf8');
console.log(`Foundation evidence collected for ${manifest.runId}`);
