// D-330 candidate artifacts only. No subprocess, package execution or integration.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {gunzipSync,gzipSync} from 'node:zlib';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const recipe=path.join(repo,'environment/editor-package');
const cache=path.join(repo,'work/dev07-package-cache');
const metadata=path.join(repo,'work/dev07-20261031');
const sha=(data,algorithm='sha256')=>createHash(algorithm).update(data).digest('hex');
const fail=message=>{throw new Error(message);};
const inside=(root,value)=>value===root||value.startsWith(root+path.sep);
const pins=JSON.parse(await fs.readFile(path.join(recipe,'direct-pins.json'),'utf8'));
const safeRelative=value=>{
  if(typeof value!=='string'||!value||/[\x00-\x1f\x7f]/.test(value)||value.includes('\\')||value.includes(':')||value.split('/').some(x=>!x||x==='.'||x==='..'))fail('Unsafe artifact path');
  return value;
};
async function checked(target,{missing=false}={}){
  const absolute=path.resolve(target);if(!inside(repo,absolute))fail('Outside repository');
  let current=repo;
  for(const part of path.relative(repo,absolute).split(path.sep).filter(Boolean)){
    current=path.join(current,part);
    try{if((await fs.lstat(current)).isSymbolicLink())fail('Artifact ancestor is a symlink');}
    catch(error){if(error.code==='ENOENT'&&missing)return absolute;throw error;}
  }
  return absolute;
}
async function read(target){await checked(target);const stat=await fs.lstat(target);if(!stat.isFile())fail('Expected regular file');return fs.readFile(target);}
export async function resolveInstalledLink(root,target,operations=fs){
  // Walk relative link segments ourselves: Windows realpath cannot resolve some
  // Linux-created links. Never normalise away a component before examining it.
  if(!inside(root,target))fail('Installed link source escapes node_modules');
  const rootStat=await operations.lstat(root);
  if(rootStat.isSymbolicLink()||!rootStat.isDirectory())fail('Installed node_modules root must be an ordinary directory');
  let pending=path.relative(root,target).split(path.sep).filter(Boolean),resolved=[];const seen=new Set();let hops=0;
  while(pending.length){
    const part=pending.shift();
    if(part==='.')continue;
    if(part==='..'){if(!resolved.length)fail('Installed link escapes node_modules');resolved.pop();continue;}
    if(!part||part.includes('\\')||part.includes(':')||/[\x00-\x1f\x7f]/.test(part))fail('Invalid installed link segment');
    const current=path.join(root,...resolved,part);const stat=await operations.lstat(current);
    if(stat.isSymbolicLink()){
      if(++hops>32||seen.has(current.toLowerCase()))fail('Installed symlink cycle/hop bound');seen.add(current.toLowerCase());
      const value=await operations.readlink(current);
      if(typeof value!=='string'||!value||path.isAbsolute(value)||value.startsWith('/')||value.includes('\\')||value.includes(':')||/[\x00-\x1f\x7f]/.test(value))fail('Installed link must have a portable relative target');
      const segments=value.split('/');if(segments.some(segment=>!segment))fail('Invalid installed link target');
      pending=[...segments,...pending];
    }else{
      if(!stat.isFile()&&!stat.isDirectory())fail('Unknown installed link target type');
      if(pending.length&&!stat.isDirectory())fail('Installed link traverses a non-directory');
      resolved.push(part);
    }
  }
  const result=path.join(root,...resolved);if(!inside(root,result))fail('Installed link resolution escapes node_modules');return result;
}
async function usage(){
  let bytes=0;const seen=new Set();
  async function visit(directory){
    for(const entry of await fs.readdir(directory,{withFileTypes:true})){
      const target=path.join(directory,entry.name);const stat=await fs.lstat(target);
      if(stat.isSymbolicLink()){
        const installedRoot=path.join(cache,'js/project/node_modules');
        if(!inside(installedRoot,target))fail('Cache link outside installed node_modules');
        await resolveInstalledLink(installedRoot,target);
        bytes+=stat.size;continue;
      }
      if(stat.isDirectory())await visit(target);
      else if(stat.isFile()){
        const identity=`${stat.dev}:${stat.ino}`;
        if(!seen.has(identity)){bytes+=stat.size;seen.add(identity);}
      }else fail('Unexpected cache filesystem node');
      if(bytes>pins.cacheBudgetBytes)fail('Cache exceeds the 2 GiB preparation budget');
    }
  }
  await checked(cache);await visit(cache);return bytes;
}
async function reserve(bytes){if(!Number.isSafeInteger(bytes)||bytes<0)fail('Invalid reservation');const current=await usage();if(current+bytes>pins.cacheBudgetBytes)fail('Insufficient measured cache budget');return current;}
async function put(relative,data){
  safeRelative(relative);const target=path.join(cache,...relative.split('/'));
  await checked(target,{missing:true});await fs.mkdir(path.dirname(target),{recursive:true});await checked(path.dirname(target));
  try{const previous=await read(target);if(!previous.equals(data))fail('Existing artifact differs; no automatic overwrite');return;}
  catch(error){if(error.code!=='ENOENT')throw error;}
  await reserve(data.length);const handle=await fs.open(target,'wx',0o600);
  try{await handle.writeFile(data);await handle.sync();}finally{await handle.close();}
}
async function jsonPut(relative,value){await put(relative,Buffer.from(JSON.stringify(value,null,2)+'\n'));}
async function fetchBounded(url,maxBytes,host){
  const parsed=new URL(url);if(parsed.protocol!=='https:'||parsed.hostname!==host||parsed.username||parsed.password||parsed.port||parsed.hash)fail('Unapproved download origin');
  await reserve(maxBytes);
  const response=await fetch(parsed,{redirect:'error',signal:AbortSignal.timeout(30000),headers:{'accept-encoding':'identity'}});
  if(!response.ok)fail(`Download rejected: HTTP ${response.status}`);
  const length=response.headers.get('content-length');
  if(length!==null&&(!/^\d+$/.test(length)||Number(length)>maxBytes))fail('Download Content-Length exceeds bound');
  const chunks=[];let total=0;
  try{for await(const chunk of response.body){total+=chunk.length;if(total>maxBytes)fail('Download exceeds byte bound');chunks.push(chunk);}}
  catch(error){await response.body?.cancel().catch(()=>{});throw error;}
  return Buffer.concat(chunks,total);
}
function integrity(data,sri){
  const match=/^(sha256|sha384|sha512)-([A-Za-z0-9+/]+={0,2})$/.exec(sri||'');
  if(!match||createHash(match[1]).update(data).digest('base64')!==match[2])fail('Artifact integrity mismatch');
}
async function pythonManifest(){
  const output=[];
  for(const [name,version] of Object.entries(pins.python)){
    const bytes=await read(path.join(metadata,`${name}-metadata.json`));const info=JSON.parse(bytes);
    if(info.info.name.toLowerCase()!==name||info.info.version!==version)fail('Python metadata version mismatch');
    const wheels=info.urls.filter(item=>name==='nh3'?item.filename===pins.nh3Filename:/-py(?:2\.py3|3)-none-any\.whl$/.test(item.filename));
    if(wheels.length!==1)fail('Expected one approved wheel');
    const item=wheels[0];safeRelative(item.filename);
    if(!Number.isSafeInteger(item.size)||item.size<=0||item.size>pins.perNpmArchiveLimitBytes||!/^[a-f0-9]{64}$/.test(item.digests.sha256)||item.yanked)fail('Invalid wheel metadata');
    if(name==='nh3'&&item.digests.sha256!==pins.nh3Sha256)fail('Wrong ABI3 wheel hash');
    output.push({name,version,filename:item.filename,size:item.size,sha256:item.digests.sha256,url:item.url,metadataSha256:sha(bytes)});
  }
  return output;
}
async function initialize(){
  const packageData=await read(path.join(recipe,'package.json'));const packageJson=JSON.parse(packageData);
  if(JSON.stringify(packageJson.dependencies)!==JSON.stringify(pins.frontend)||packageJson.scripts||packageJson.packageManager!=='pnpm@11.25.0')fail('Unexpected direct frontend manifest');
  const python=await pythonManifest();
  const requirements=python.map(item=>`${item.name}==${item.version} --hash=sha256:${item.sha256}`).join('\n')+'\n';
  if((await read(path.join(recipe,'requirements.lock'))).toString().replace(/\r/g,'')!==requirements)fail('Wheel requirements do not match official metadata');
  await put('python/requirements.lock',Buffer.from(requirements));
  await put('js/project/package.json',packageData);
  await put('js/project/pnpm-workspace.yaml',await read(path.join(recipe,'pnpm-workspace.yaml')));
  await jsonPut('candidate-manifest.json',{schemaVersion:1,approvedBy:'D-330',status:'preparation-only-not-integrated',basePythonImageId:pins.basePythonImageId,python,frontend:pins.frontend,cacheBudgetBytes:pins.cacheBudgetBytes});
}
async function downloadPython(){
  await initialize();
  for(const item of await pythonManifest()){
    const relative=`python/wheels/${item.filename}`;let data;
    try{data=await read(path.join(cache,...relative.split('/')));}
    catch(error){if(error.code!=='ENOENT')throw error;data=await fetchBounded(item.url,item.size,'files.pythonhosted.org');}
    if(data.length!==item.size||sha(data)!==item.sha256)fail('Wheel bytes/hash mismatch');
    await put(relative,data);
  }
  await jsonPut('python/download-receipt.json',{schemaVersion:1,artifacts:await pythonManifest()});
}
// Restricted reader for package keys + inline integrity emitted by approved pnpm.
// This is not a YAML parser: any unexpected resolution form is a hard failure.
export function extractPackages(source){
  // URI schemes are tokens/values, not suffixes of ordinary YAML keys such as
  // excludeLinksFromLockfile. Quoted and mixed-case URI values remain rejected.
  if(source.includes('\t')||/<<:|[&*][A-Za-z_]|https?:\/\/|(?:^|[^A-Za-z0-9_])(?:file|git|link|workspace):/im.test(source))fail('Unsupported lock syntax/source');
  if(!/^lockfileVersion: '9\.0'\s*$/m.test(source))fail('Unexpected pnpm lock version');
  const section=/^packages:\r?\n([\s\S]*?)(?=^[A-Za-z][A-Za-z0-9]*:|(?![\s\S]))/m.exec(source);
  if(!section)fail('Missing packages section');
  const blocks=section[1].split(/(?=^  \S)/m).filter(x=>x.trim());const output=[];const seen=new Set();
  for(const block of blocks){
    const lines=block.replace(/\r/g,'').split('\n');
    const key=/^  (?:'([^']+)'|([^ '][^:]*)):$/.exec(lines[0]);if(!key)fail('Unexpected package-key shape');
    const identity=key[1]||key[2];const parts=/^(@[a-z0-9._-]+\/[a-z0-9._-]+|[a-z0-9._-]+)@(\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?)$/.exec(identity);
    if(!parts||seen.has(identity))fail('Unsupported or duplicate package identity');seen.add(identity);
    const resolutions=lines.filter(line=>/^    resolution:/.test(line));
    if(resolutions.length!==1)fail('Expected one package resolution');
    const resolved=/^    resolution: \{integrity: (sha(?:256|384|512)-[A-Za-z0-9+/]+={0,2})\}$/.exec(resolutions[0]);
    if(!resolved)fail('Unsupported package resolution');
    output.push({name:parts[1],version:parts[2],integrity:resolved[1],skipped:parts[1].startsWith('@esbuild/')&&parts[1]!=='@esbuild/linux-x64'});
  }
  if(!output.length)fail('Empty lock graph');return output;
}

export function unpackFootprint(archive){
  // Bound decompression before any package manager is allowed to extract it.
  const bytes=gunzipSync(archive,{maxOutputLength:128*1024*1024});
  let offset=0,unpackedBytes=0,files=0;const paths=new Set();let ended=false;
  const string=(buffer)=>buffer.toString('utf8').replace(/\0.*$/s,'');
  while(offset+512<=bytes.length){
    const header=bytes.subarray(offset,offset+512);offset+=512;
    if(header.every(value=>value===0)){
      if(offset+512>bytes.length||bytes.subarray(offset).some(value=>value!==0))fail('Invalid archive end marker/trailing entries');
      ended=true;break;
    }
    const name=string(header.subarray(0,100)),prefix=string(header.subarray(345,500));
    const full=(prefix?prefix+'/':'')+name;const normalized=full.replace(/\/$/,'');
    safeRelative(normalized);if(!normalized.startsWith('package/')&&normalized!=='package')fail('Archive entry outside package namespace');
    if(paths.has(normalized))fail('Duplicate archive entry');paths.add(normalized);
    const type=String.fromCharCode(header[156]||48);
    if(!['0','5'].includes(type))fail('Unsupported archive entry type; no links/devices/PAX execution paths');
    const sizeField=string(header.subarray(124,136)).trim();
    if(!/^[0-7]+$/.test(sizeField))fail('Unsupported tar size');const size=parseInt(sizeField,8);
    if(!Number.isSafeInteger(size)||size<0||offset+size>bytes.length||(type==='5'&&size!==0))fail('Invalid archive size');
    const checksumField=string(header.subarray(148,156)).trim();
    if(!/^[0-7]+$/.test(checksumField))fail('Invalid tar checksum field');
    const checksum=header.reduce((sum,value,index)=>sum+(index>=148&&index<156?32:value),0);
    if(checksum!==parseInt(checksumField,8))fail('Tar checksum mismatch');
    if(type==='0'){files++;unpackedBytes+=size;}
    if(files>10000)fail('Archive file count exceeds preparation bound');
    offset+=Math.ceil(size/512)*512;
  }
  if(!ended||!files)fail('Incomplete or empty package archive');
  return {unpackedBytes,files,decompressedTarBytes:bytes.length};
}
export function deriveOfflineLock(source,artifacts){
  const graph=extractPackages(source);const byIdentity=new Map();
  for(const artifact of artifacts){const key=`${artifact.name}@${artifact.version}`;if(byIdentity.has(key))fail('Duplicate offline artifact');byIdentity.set(key,artifact);}
  if(byIdentity.size!==graph.length)fail('Offline artifact graph is incomplete');
  let output=source;const changes=[];
  for(const item of graph){
    const identity=`${item.name}@${item.version}`,artifact=byIdentity.get(identity);
    if(!artifact||artifact.integrity!==item.integrity||artifact.skipped!==item.skipped)fail('Offline artifact binding mismatch');
    if(item.skipped)continue;
    if(!/^npm-tarballs\/[a-f0-9]{64}\.tgz$/.test(artifact.path))fail('Unsafe offline tarball path');
    const target=`file:../../${artifact.path}`;
    const lines=output.split('\n');let inPackages=false,selected=false,changed=0;
    for(let index=0;index<lines.length;index++){
      const line=lines[index].replace(/\r$/,'');
      if(line==='packages:'){inPackages=true;continue;}
      if(inPackages&&/^[A-Za-z]/.test(line)){inPackages=false;selected=false;}
      if(inPackages&&/^  \S/.test(line))selected=line===`  '${identity}':`||line===`  ${identity}:`;
      if(selected&&line===`    resolution: {integrity: ${item.integrity}}`){
        const next=`    resolution: {integrity: ${item.integrity}, tarball: ${target}}`;
        changes.push({identity,line:index+1,before:line,after:next});lines[index]=next+(lines[index].endsWith('\r')?'\r':'');changed++;
      }
    }
    if(changed!==1)fail('Offline resolution change is not unique');output=lines.join('\n');
  }
  // Reversing precisely the recorded lines must reproduce the complete source.
  const reversed=output.split('\n');for(const change of changes){
    const value=reversed[change.line-1];if(value.replace(/\r$/,'')!==change.after)fail('Offline diff mismatch');
    reversed[change.line-1]=change.before+(value.endsWith('\r')?'\r':'');
  }
  if(reversed.join('\n')!==source)fail('Offline lock changed more than allowed resolutions');
  return {text:output,changes};
}
async function offlineLock(){
  const source=await read(path.join(cache,'js/project/pnpm-lock.yaml'));
  const record=JSON.parse(await read(path.join(cache,'npm-artifacts.json')));
  if(record.lockSha256!==sha(source))fail('Source lock changed before offline derivation');
  for(const item of record.artifacts){if(item.skipped)continue;safeRelative(item.path);const bytes=await read(path.join(cache,...item.path.split('/')));if(sha(bytes)!==item.sha256||bytes.length!==item.byteSize)fail('Offline artifact drift');integrity(bytes,item.integrity);}
  const result=deriveOfflineLock(source.toString(),record.artifacts);const derived=Buffer.from(result.text);
  await put('js/original-pnpm-lock.yaml',source);await put('js/offline-pnpm-lock.yaml',derived);
  await jsonPut('offline-lock-receipt.json',{schemaVersion:1,originalSha256:sha(source),derivedSha256:sha(derived),changes:result.changes,scope:'resolution.tarball-only',dependencyGraphChanged:false});
}
async function downloadNpm(){
  await initialize();const lock=await read(path.join(cache,'js/project/pnpm-lock.yaml'));const entries=extractPackages(lock.toString());
  for(const [name,version] of Object.entries(pins.frontend))if(!entries.some(item=>item.name===name&&item.version===version&&!item.skipped))fail('Direct pin missing from lock');
  const artifacts=[];
  for(const item of entries){
    if(item.skipped){artifacts.push({...item,reason:'unapproved optional esbuild platform; not downloaded'});continue;}
    if(item.name==='@esbuild/linux-x64'&&(item.version!=='0.28.2'||item.integrity!==pins.esbuildPlatformIntegrity))fail('Unapproved esbuild binary');
    const key=sha(Buffer.from(`${item.name}@${item.version}`));let metaBytes;
    const metaRelative=`npm-metadata/${key}.json`;
    try{metaBytes=await read(path.join(cache,'npm-metadata',`${key}.json`));}
    catch(error){if(error.code!=='ENOENT')throw error;metaBytes=await fetchBounded(`https://registry.npmjs.org/${encodeURIComponent(item.name)}/${item.version}`,pins.perMetadataLimitBytes,'registry.npmjs.org');await put(metaRelative,metaBytes);}
    const info=JSON.parse(metaBytes);if(info.name!==item.name||info.version!==item.version||info.dist?.integrity!==item.integrity)fail('Registry metadata differs from lock');
    const relative=`npm-tarballs/${key}.tgz`;let archive;
    try{archive=await read(path.join(cache,'npm-tarballs',`${key}.tgz`));}
    catch(error){if(error.code!=='ENOENT')throw error;archive=await fetchBounded(info.dist.tarball,pins.perNpmArchiveLimitBytes,'registry.npmjs.org');}
    integrity(archive,item.integrity);const footprint=unpackFootprint(archive);await put(relative,archive);
    artifacts.push({...item,path:relative,byteSize:archive.length,sha256:sha(archive),metadataSha256:sha(metaBytes),declaredLifecycleScripts:info.scripts||{},url:info.dist.tarball,...footprint});
  }
  // Reserve enough for independent pnpm store + project copies before extraction.
  const installationReserveBytes=artifacts.filter(item=>!item.skipped).reduce((sum,item)=>sum+2*(item.unpackedBytes+4096*item.files),0);
  await reserve(installationReserveBytes);
  await jsonPut('npm-artifacts.json',{schemaVersion:1,lockSha256:sha(lock),platform:'linux/x64/glibc',lifecycleScriptsExecuted:false,installationReserveBytes,artifacts});
}
async function verify(){
  const manifest=JSON.parse(await read(path.join(cache,'candidate-manifest.json')));
  if(manifest.basePythonImageId!==pins.basePythonImageId||JSON.stringify(manifest.python)!==JSON.stringify(await pythonManifest()))fail('Candidate manifest drift');
  for(const item of manifest.python){const bytes=await read(path.join(cache,'python/wheels',item.filename));if(bytes.length!==item.size||sha(bytes)!==item.sha256)fail('Wheel drift');}
  const npmPath=path.join(cache,'npm-artifacts.json');
  try{
    const record=JSON.parse(await read(npmPath));const workingLock=await read(path.join(cache,'js/project/pnpm-lock.yaml'));
    let lock=workingLock;
    let receipt;
    try{receipt=JSON.parse(await read(path.join(cache,'offline-lock-receipt.json')));}
    catch(error){if(error.code!=='ENOENT')throw error;}
    if(receipt){
      lock=await read(path.join(cache,'js/original-pnpm-lock.yaml'));const derived=await read(path.join(cache,'js/offline-pnpm-lock.yaml'));
      const regenerated=deriveOfflineLock(lock.toString(),record.artifacts);
      if(receipt.originalSha256!==sha(lock)||receipt.derivedSha256!==sha(derived)||derived.toString()!==regenerated.text||JSON.stringify(receipt.changes)!==JSON.stringify(regenerated.changes)||![sha(lock),sha(derived)].includes(sha(workingLock)))fail('Offline derived lock drift');
    }
    if(record.lockSha256!==sha(lock)||JSON.stringify(record.artifacts.map(({name,version,integrity,skipped})=>({name,version,integrity,skipped})))!==JSON.stringify(extractPackages(lock.toString())))fail('Npm graph drift');
    for(const item of record.artifacts){if(item.skipped)continue;safeRelative(item.path);const bytes=await read(path.join(cache,...item.path.split('/')));if(bytes.length!==item.byteSize||sha(bytes)!==item.sha256)fail('Npm bytes drift');integrity(bytes,item.integrity);}
  }catch(error){if(error.code==='ENOENT')fail('Complete npm lock/artifact evidence is missing');throw error;}
  return {schemaVersion:1,status:'verified-artifact-bytes-only-not-security-approval',cacheBytes:await usage()};
}
async function installedManifest(){
  const baseline=JSON.parse(await read(path.join(cache,'python/base-site-packages.json')));
  if(baseline.schemaVersion!==1||baseline.imageId!==pins.basePythonImageId||baseline.sitePackagesPath!=='/usr/local/lib/python3.14/site-packages'||!Array.isArray(baseline.topLevelEntries)||baseline.topLevelEntries.some(item=>typeof item!=='string'||!item||item.includes('/')||item.includes('\\')))fail('Invalid actual base inventory contract');
  const root=path.join(cache,'python/site-packages');await checked(root);
  const allowed=new Set(['html5lib','tinycss2','nh3','six.py','webencodings',...Object.entries(pins.python).map(([name,version])=>`${name}-${version}.dist-info`)]);
  const top=await fs.readdir(root);if(top.some(name=>!allowed.has(name)||baseline.topLevelEntries.includes(name))||top.length!==allowed.size)fail('Installed tree has unknown, missing or colliding top-level entries');
  const files=[];
  async function walk(directory){
    for(const name of (await fs.readdir(directory)).sort()){
      const absolute=path.join(directory,name);await checked(absolute);const stat=await fs.lstat(absolute);
      const relative=path.relative(root,absolute).split(path.sep).join('/');safeRelative(relative);
      if(stat.isSymbolicLink()||(!stat.isDirectory()&&!stat.isFile()))fail('Installed tree must contain only ordinary files/directories');
      if(stat.isDirectory())await walk(absolute);
      else{if(stat.nlink!==1)fail('Installed output hardlink rejected');const bytes=await read(absolute);files.push({path:relative,byteSize:bytes.length,sha256:sha(bytes)});}
    }
  }
  await walk(root);
  for(const [name,version] of Object.entries(pins.python)){
    const directory=`${name}-${version}.dist-info`;const contents=(await read(path.join(root,directory,'METADATA'))).toString();
    if(!new RegExp(`^Name: ${name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}\\r?$`,'mi').test(contents)||!contents.split(/\r?\n/).includes('Version: '+version))fail('Installed distribution version mismatch');
  }
  await jsonPut('python/installed-tree.json',{schemaVersion:1,status:'candidate-output-only-not-integrated',baseImageId:pins.basePythonImageId,baselineSha256:sha(await read(path.join(cache,'python/base-site-packages.json'))),packageVersions:pins.python,files,treeSha256:sha(Buffer.from(JSON.stringify(files))),byteSize:files.reduce((sum,item)=>sum+item.byteSize,0)});
}
async function selfcheck(){
  const valid="lockfileVersion: '9.0'\n\nsettings:\n  autoInstallPeers: true\n  excludeLinksFromLockfile: false\n\nimporters:\n  .: {}\npackages:\n\n  '@tiptap/core@3.32.2':\n    resolution: {integrity: sha512-YWJj}\n\n  '@esbuild/win32-x64@0.28.2':\n    resolution: {integrity: sha512-YWJj}\n\nsnapshots:\n  '@tiptap/core@3.32.2': {}\n";
  const graph=extractPackages(valid);if(graph.length!==2||graph[0].name!=='@tiptap/core'||!graph[1].skipped)fail('Selfcheck: lock completeness/platform skip');
  let negative=0;
  const badSources=['file:../outside','git:repository',"'link:../outside'",'workspace:*','"FiLe:../outside"'];
  for(const input of [valid.replace('integrity: sha512-YWJj','tarball: https://example.invalid/x'),valid.replace("'@tiptap/core@3.32.2'","'@tiptap/core@latest'"),valid.replace('snapshots:','  anchor: &unsafe x\nsnapshots:'),...badSources.map(value=>valid.replace('  .: {}',`  .:\n    specifier: ${value}`))]){
    try{extractPackages(input);}catch{negative++;}
  }
  if(negative!==8)fail('Selfcheck: lock rejection');
  const tar=(name,type='0')=>{
    const header=Buffer.alloc(512);header.write(name);header.write('0000644\0',100);header.write('0000000\0',108);header.write('0000000\0',116);header.write('00000000003\0',124);header.write('00000000000\0',136);header.fill(32,148,156);header.write(type,156);header.write('ustar\0',257);
    const sum=header.reduce((a,b)=>a+b,0).toString(8).padStart(6,'0');header.write(sum+'\0 ',148);
    const payload=Buffer.alloc(512);payload.write('abc');return gzipSync(Buffer.concat([header,payload,Buffer.alloc(1024)]));
  };
  const actual=unpackFootprint(tar('package/file.js'));if(actual.files!==1||actual.unpackedBytes!==3)fail('Selfcheck: archive measurement');
  negative=0;for(const [name,type] of [['package/../escape','0'],['package/link','2'],['/absolute','0']]){try{unpackFootprint(tar(name,type));}catch{negative++;}}
  if(negative!==3)fail('Selfcheck: archive rejection');
  const artifacts=graph.map(item=>({...item,...(!item.skipped?{path:'npm-tarballs/'+'a'.repeat(64)+'.tgz'}:{})}));
  const derived=deriveOfflineLock(valid,artifacts);
  if(derived.changes.length!==1||!derived.text.includes('tarball: file:../../npm-tarballs/')||!derived.text.endsWith("snapshots:\n  '@tiptap/core@3.32.2': {}\n"))fail('Selfcheck: offline change scope');
  negative=0;for(const list of [artifacts.slice(1),artifacts.map(item=>({...item,integrity:'sha512-bad'})),artifacts.map(item=>({...item,path:'npm-tarballs/../escape.tgz'}))]){try{deriveOfflineLock(valid,list);}catch{negative++;}}
  if(negative!==3)fail('Selfcheck: offline graph/path rejection');
  const root=path.join(repo,'synthetic-node-modules');
  const directory={isSymbolicLink:()=>false,isDirectory:()=>true,isFile:()=>false};
  const regular={isSymbolicLink:()=>false,isDirectory:()=>false,isFile:()=>true};
  const link={isSymbolicLink:()=>true,isDirectory:()=>false,isFile:()=>false};
  async function resolveMap(entries,target){
    const nodes=new Map([[root,{stat:directory}],...Object.entries(entries).map(([key,value])=>[path.join(root,...key.split('/')),value])]);
    const operations={lstat:async name=>{if(!nodes.has(name))fail('Missing synthetic link target');return nodes.get(name).stat;},readlink:async name=>nodes.get(name).link};
    return resolveInstalledLink(root,path.join(root,...target.split('/')),operations);
  }
  const entries={'.bin':{stat:directory},'.bin/esbuild':{stat:link,link:'../esbuild/bin/esbuild'},esbuild:{stat:directory},'esbuild/bin':{stat:directory},'esbuild/bin/esbuild':{stat:link,link:'../../actual'},actual:{stat:regular}};
  if(await resolveMap(entries,'.bin/esbuild')!==path.join(root,'actual'))fail('Selfcheck: portable internal link chain');
  negative=0;
  for(const [value,reason] of [['../../../outside','escapes node_modules'],['/absolute','portable relative target'],['../../.bin/esbuild','cycle/hop bound']]){
    try{await resolveMap({...entries,'esbuild/bin/esbuild':{stat:link,link:value}},'.bin/esbuild');}catch(error){if(error.message.includes(reason))negative++;else throw error;}
  }
  // An external intermediate cannot be hidden by a later /.. segment.
  try{await resolveMap({...entries,'esbuild/bin/esbuild':{stat:link,link:'../../external/../actual'},external:{stat:link,link:'../outside'}},'.bin/esbuild');}catch{negative++;}
  if(negative!==4)fail('Selfcheck: portable external/absolute/cycle rejection');
  const longChain={actual:{stat:regular}};for(let index=0;index<34;index++)longChain['link'+index]={stat:link,link:index===33?'actual':'link'+(index+1)};
  let bounded=false;try{await resolveMap(longChain,'link0');}catch(error){bounded=error.message.includes('cycle/hop bound');}
  if(!bounded)fail('Selfcheck: portable link hop limit');
  let missing=false;try{await resolveMap({bad:{stat:link,link:'missing'}},'bad');}catch(error){missing=error.message.includes('Missing synthetic link target');}
  if(!missing)fail('Selfcheck: unknown link target rejection');
  return {status:'pure-selfcheck-pass',cases:24,network:false,filesystemWrites:false};
}
async function main(){
  const action=process.argv[2];if(process.argv.length!==3||!['init','python-download','npm-download','offline-lock','installed-manifest','verify','budget','selfcheck'].includes(action))fail('Usage: prepare.mjs init|python-download|npm-download|offline-lock|installed-manifest|verify|budget|selfcheck');
  if(action==='selfcheck'){process.stdout.write(JSON.stringify(await selfcheck())+'\n');return;}
  await checked(cache,{missing:true});await fs.mkdir(cache,{recursive:true});await checked(cache);
  const lockPath=path.join(cache,'.prepare.lock');const handle=await fs.open(lockPath,'wx',0o600);
  try{
    if(action==='init')await initialize();
    if(action==='python-download')await downloadPython();
    if(action==='npm-download')await downloadNpm();
    if(action==='offline-lock')await offlineLock();
    if(action==='installed-manifest')await installedManifest();
    const result=action==='verify'?await verify():{action,cacheBytes:await usage(),cacheBudgetBytes:pins.cacheBudgetBytes};
    process.stdout.write(JSON.stringify(result)+'\n');
  }finally{await handle.close();await fs.unlink(lockPath);}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))main().catch(error=>{process.stderr.write(`Editor preparation stopped: ${error.message}\n`);process.exitCode=1;});
