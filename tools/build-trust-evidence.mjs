// D-387/D-388, EV15: immutable evidence assembly only; no runtime/DB/tool launch.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

const self=fileURLToPath(import.meta.url),root=path.resolve(path.dirname(self),'..');
const work='work/dev15-evidence-20261102',runtime='work/dev15-20261102/runtime';
const packageDirectory=work+'/package',privateDirectory='work/dev15-20261102/private';
const SOURCE='014efc288de0d32772fca15d63afbb0a4c23a9009ee6ef8bdc877cb1aa41c672';
const OLD='5fbcb9d9ea04ee58853b9b8d9fe2131fc6b0d1122f087239f3c66bfded768986';
const SCHEMA='4fb7464026b738b4bc9cfd1dd23657d5e0425c7b3f859e1d9a9ddb97495d4de7';
const SNAPSHOT='5933ad132f7586c38996084248dd7cd90b7bd2fd8b3c5b0ef80ed51ff4625315';
const CAPS={logicalBytes:67108864,completionBytes:16777216,maxOperations:1000,
 maxHistoricalReferences:4096,maxTombstones:1024,maxRecoveryActions:4,maxCredentials:20,
 maxPolicyRows:16,maxPolicyRowBytes:32768,maxMessageBytes:1048576,maxTargets:256,maxTargetBytes:2048};
const PINNED={
 'work/dev15-corpus-20261102/candidate-test-report.json':'2df7b5435840cd87dd0c2714bc909b56a516bf3f212d3a5cd605bf29bfe63c3e',
 'work/dev15-corpus-20261102/candidate-integration.json':'ee7c28d133aff9b9341341840e77d5c4aac2cf60534e614ef21ae2403a8551ec',
 'work/dev15-capacity-20261102/phase-a-report.json':'589236084c89fce92c934dad0e3fc351bb1141605605d13aaafedc2c072f9a80',
 'work/dev15-capacity-20261102/phase-b-report.json':'ac1ebd2f855a5a1d06f19946fdbff379a2654ca948fd6ac7000d553bbc95d978',
 'work/dev15-wb005-20261102/worker-tls-report.json':'4c78d149065a124450292ba77bf69530693eb50172ca0145cfd80478adc799d7',
 'work/dev15-resource-20261102/resource-report.json':'30f0510f5ea898c94d39cdb76730dcba6a5ff584206e12b7cf2477177e0f29d1',
 'work/dev15-legacy-inclusion-20261102/legacy-capacity-assessment.json':'7e540df522a9d7fe999f066b00aa15fc93e44fc7822115ac93850280a3dac9b6',
 'work/dev15-legacy-inclusion-20261102/legacy-capacity-report.json':'961a38fe4ebe03d46c846696b8974df09cbb63810a0dd847fa86f42b1446b3ae',
 'work/dev15-legacy-inclusion-20261102/wrapper-smoke-report.json':'21dc96cc39cfd7b3dc5a7479773d79b02341807d1ff1ef7c86cc1a8fac426da1',
 'docs/dev15-runtime-implementation-review.md':'8afb7688710358f5a4672d558ad7113fcbc980ee33514231fbf7880888451e8a',
 'docs/dev15-candidate-regression-review.md':'55eb19f4d34184dd2a44aaced0907c6138fdbf46a9468928836c0074cfdd8d0f',
 'docs/dev15-capacity-review.md':'0884eb616ac88142c22ea0b0841fa012f47d6ab08c2d79a44bd807c58a083f4c',
 'docs/dev15-worker-tls-review.md':'4deb2b25bca462cf52a2ac17d1ab822fa260e760a531cb9ce36e0adf19626cfb',
 'docs/dev15-resource-review.md':'30a17afb5eb53983728fe87fc424dadcd3285de63d6158dcb43556ab2ffd75bd',
 'docs/dev15-legacy-quota-review.md':'f571c9e64de28dfaa57c08ab86f469ab3a1e2e7715dfe65fc3ea9fc69aef1f07'
};
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const stable=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)
 ?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a<b?-1:a>b?1:0)):x);
const raw=v=>Buffer.from(stable(v)+'\n');
const ensure=(v,c)=>{if(!v)throw Error(c);};
const closed=(v,keys)=>ensure(v&&typeof v==='object'&&!Array.isArray(v)
 &&stable(Object.keys(v).sort())===stable([...keys].sort()),'EV_CLOSED_SHAPE');
function inside(file){const p=path.resolve(root,file);ensure(p.startsWith(root+path.sep),'EV_PATH');
 for(let q=p;q!==root;q=path.dirname(q))if(fs.existsSync(q))ensure(!fs.lstatSync(q).isSymbolicLink(),'EV_REPARSE');
 return p;}
function read(file){const p=inside(file),s=fs.lstatSync(p);ensure(s.isFile()&&s.size<=4194304,'EV_INPUT_FILE');return fs.readFileSync(p);}
const json=file=>JSON.parse(read(file));
const relative=file=>path.relative(root,inside(file)).replaceAll('\\','/');
function write(file,value){const b=raw(value);ensure(b.length<=1048576,'EV_OUTPUT_SIZE');fs.writeFileSync(inside(file),b,{flag:'wx',mode:0o600});return sha(b);}
function mac(value){const cfg=json(privateDirectory+'/credentials.json');const keys=cfg.credentials.filter(x=>x.role==='recovery');
 ensure(keys.length===1&&/^[a-f0-9]{64}$/.test(keys[0].secret),'EV_SIGNING_CONFIGURATION');
 return crypto.createHmac('sha256',Buffer.from(keys[0].secret,'hex')).update(stable(value)).digest('hex');}
function sourceRows(rows,directory,fingerprint){ensure(Array.isArray(rows)&&rows.length===30,'EV_SOURCE_COUNT');let previous='';
 const discovered=[];function walk(dir,prefix=''){for(const entry of fs.readdirSync(inside(dir),{withFileTypes:true})){
  const file=path.join(dir,entry.name),name=prefix+entry.name;ensure(!entry.isSymbolicLink(),'EV_SOURCE_REPARSE');
  if(entry.isDirectory())walk(file,name+'/');else if(entry.isFile()&&name.endsWith('.py'))discovered.push(name);}}
 walk(directory);ensure(stable(discovered.sort())===stable(rows.map(x=>x.path)),'EV_SOURCE_TREE_SET');
 const actual=rows.map(row=>{closed(row,['path','sha256']);ensure(/^[A-Za-z0-9_./-]+\.py$/.test(row.path)
  &&!row.path.split('/').includes('..')&&row.path>previous&&/^[a-f0-9]{64}$/.test(row.sha256),'EV_SOURCE_PATH');
  previous=row.path;const digest=sha(read(path.join(directory,row.path)));ensure(digest===row.sha256,'EV_SOURCE_DRIFT');return {path:row.path,sha256:digest};});
 ensure(sha(Buffer.from(stable(actual)))===fingerprint,'EV_SOURCE_FINGERPRINT');return actual;}
function manifest(kind){return {kind,status:'PASS',sourceFingerprint:SOURCE,schemaFingerprint:SCHEMA,caps:CAPS,
 checks:kind==='unit'?Array.from({length:7},(_,i)=>'RP15-'+String(i+1).padStart(3,'0')):
 kind==='calibration'?Array.from({length:5},(_,i)=>'RP15-'+String(i+8).padStart(3,'0')):['CODE','QA','CAPACITY']};}
function codeGate(){const file=work+'/builder-code-gate.json',gate=json(file);closed(gate,['status','authority','files']);
 ensure(gate.status==='APPROVED'&&gate.authority==='D-388'&&Array.isArray(gate.files),'EV_CODE_GATE');
 let own=false;const seen=new Set();for(const entry of gate.files){closed(entry,['path','sha256']);const name=relative(entry.path);
  ensure(!seen.has(name)&&sha(read(name))===entry.sha256,'EV_CODE_GATE_DRIFT');seen.add(name);if(name===relative(self))own=true;}
 ensure(own,'EV_CODE_GATE_SELF');return {path:file,sha256:sha(read(file))};}

function collect(){
 const inputs=new Map();
 function record(file,authentication='RAW_SHA_VERIFIED'){const name=relative(file),b=read(name),digest=sha(b),old=inputs.get(name);
  ensure(!old||old.sha256===digest,'EV_INPUT_CHANGED');inputs.set(name,{path:name,sha256:digest,
   authentication:old?.authentication==='HMAC_VERIFIED'||old?.authentication==='PINNED_RAW_SHA'&&authentication==='RAW_SHA_VERIFIED'
    ?old.authentication:authentication});return b;}
 const get=file=>JSON.parse(record(file));
 function signed(file,scope){const e=get(file);closed(e,['payload','signature']);ensure(e.payload?.scope===scope
  &&typeof e.signature==='string'&&/^[a-f0-9]{64}$/.test(e.signature)&&e.signature===mac(e.payload),'EV_HMAC');
  record(file,'HMAC_VERIFIED');return e.payload;}
 function linked(file,expected){ensure(sha(record(file))===expected,'EV_LINK_SHA');return get(file);}
 for(const [file,digest]of Object.entries(PINNED))ensure(sha(record(file,'PINNED_RAW_SHA'))===digest,'EV_PINNED_INPUT');
 const unit=get('work/dev15-corpus-20261102/candidate-test-report.json');
 const integration=get('work/dev15-corpus-20261102/candidate-integration.json');
 const a=get('work/dev15-capacity-20261102/phase-a-report.json'),b=get('work/dev15-capacity-20261102/phase-b-report.json');
 const tls=get('work/dev15-wb005-20261102/worker-tls-report.json'),ra=get('work/dev15-resource-20261102/resource-report.json');
 const assessment=get('work/dev15-legacy-inclusion-20261102/legacy-capacity-assessment.json');
 const lg=get('work/dev15-legacy-inclusion-20261102/legacy-capacity-report.json'),smoke=get('work/dev15-legacy-inclusion-20261102/wrapper-smoke-report.json');
 const capFile=runtime+'/archive-capacity.json',archiveIntentFile=runtime+'/capacity-archive-intent.json',legacyFile=runtime+'/archive-unit.json';
 const cap=signed(capFile,'DEV15-CAPACITY-ARCHIVE'),archiveIntent=signed(archiveIntentFile,'DEV15-CAPACITY-ARCHIVE-INTENT'),legacy=signed(legacyFile,'DEV15-WP-ARCHIVE');
 ensure(cap.authority==='D-380'&&archiveIntent.authority==='D-380'&&cap.sourceSha256===OLD
  &&cap.intentSha256===sha(record(archiveIntentFile))&&cap.legacyReceiptSha256===sha(record(legacyFile))
  &&archiveIntent.legacyReceiptSha256===sha(record(legacyFile))&&stable(cap.report.unitState)===stable(archiveIntent.reference.unit)
  &&stable(cap.report.mainState)===stable(archiveIntent.reference.main)&&stable(cap.report.legacyState)===stable(legacy.report.state)
  &&legacy.report.freshUnitOid===32563&&legacy.report.state.oid===16387&&cap.report.unitState.oid===32563
  &&cap.report.freshUnitOid===52766&&cap.report.archivesClosed===true&&cap.report.dropPerformed===false
  &&cap.report.sameRowsDigest===true&&cap.report.sameArchiveOid===true,'EV_ARCHIVE_LINEAGE');
 ensure(cap.report.freshUnitMarker==='ESTAKADA-DEV15-CAPACITY:'+archiveIntent.reference.intentId
  &&cap.report.unitState.schemaFingerprint===SCHEMA&&cap.report.mainState.schemaFingerprint===SCHEMA,'EV_ARCHIVE_MARKER_SCHEMA');
 const oldRows=sourceRows(cap.sourceFiles,cap.sourceDirectory,OLD);
 const candidateFile='work/dev15-corpus-20261102/candidate-test-attempt.json';
 const candidate=signed(candidateFile,'DEV15-CANDIDATE-REGRESSIONS');
 ensure(candidate.authority==='D-383'&&candidate.oldSourceSha256===OLD&&candidate.previewSourceSha256===SOURCE
  &&candidate.freshUnitOid===52766&&candidate.freshUnitMarker===cap.report.freshUnitMarker
  &&candidate.sourceDirectory===cap.sourceDirectory&&stable(candidate.sourceFiles)===stable(cap.sourceFiles),'EV_CANDIDATE_LINEAGE');
 closed(candidate.receiptHashes,['intent','receipt','legacy']);
 for(const [key,file]of Object.entries({intent:archiveIntentFile,receipt:capFile,legacy:legacyFile}))
  ensure(sha(record(file))===candidate.receiptHashes[key],'EV_CANDIDATE_RECEIPT_LINK');
 const newRows=sourceRows(candidate.previewFiles,candidate.previewDirectory,SOURCE);
 sourceRows(candidate.previewFiles,'trust',SOURCE);
 ensure(stable(oldRows.map(x=>x.path))===stable(newRows.map(x=>x.path)),'EV_SOURCE_PATH_SET');
 const differences=newRows.filter((row,i)=>row.sha256!==oldRows[i].sha256).map(x=>x.path);
 ensure(stable(differences)===stable(['journal/consumer.py'])&&newRows.find(x=>x.path==='journal/consumer.py').sha256
  ==='15e6c9b25764eab698dac4e52f8cca804f4c339a271d83db521bdf0e8ee98d21','EV_29_UNCHANGED');
 closed(unit.finalOwnedTestContainers,['exactName','runLabel']);
 ensure(unit.status==='PASS'&&unit.tests.status==='PASS'&&unit.tests.count===131&&unit.tests.skipped===0
  &&unit.tests.sourceSha256===SOURCE&&unit.tests.runtimeId===candidate.runId&&unit.tests.freshUnitOid===52766
  &&unit.sourceDrift===0&&unit.finalOwnedTestContainers.exactName===0&&unit.finalOwnedTestContainers.runLabel===0
  &&unit.finalStatus.actualRunningContainers===0,'EV_UNIT_RESULT');
 ensure(integration.status==='PASS'&&integration.sourceSha256===SOURCE&&integration.previewReportSha256===PINNED['work/dev15-corpus-20261102/candidate-test-report.json']
  &&stable(integration.changedFiles)===stable(['trust/journal/consumer.py'])&&integration.additionalRuntimeRun===false,'EV_INTEGRATION_RESULT');
 const phaseAFile=runtime+'/capacity-phase-a.json',phaseBFile=runtime+'/capacity-phase-b.json';
 const phaseA=signed(phaseAFile,'DEV15_CAPACITY_CONTINUATION'),phaseB=signed(phaseBFile,'DEV15_CAPACITY_CONTINUATION');
 const checkpoint=signed(runtime+'/capacity-phase-a-checkpoint.json','DEV15_CAPACITY_CHECKPOINT');
 ensure(phaseA.phase==='A'&&phaseB.phase==='B'&&phaseA.sourceSha256===OLD&&phaseB.sourceSha256===OLD
  &&archiveIntent.phaseBReceiptSha256===sha(record(phaseBFile)),'EV_CAPACITY_RECEIPTS');
 ensure(a.status==='PASS'&&b.status==='PASS'&&a.sourceSha256===OLD&&b.sourceSha256===OLD
  &&a.helper.status==='PASS'&&b.helper.status==='PASS'&&a.dataRetained===true&&b.dataRetained===true
  &&a.helper.sourceFingerprint===OLD&&b.helper.sourceFingerprint===OLD
  &&b.helper.finalAudit.schemaFingerprint===SCHEMA&&b.helper.finalAudit.stateDigest===cap.report.unitState.stateV2Sha256
  &&b.helper.finalAudit.counts.Operation===1000&&b.helper.finalAudit.counts.RoutePolicy===4096
  &&b.helper.finalAudit.counts.RequestTombstone===1024&&b.helper.finalAudit.head.reserved_bytes===0,'EV_CAPACITY_RESULT');
 // Join the authenticated A checkpoint to both accepted executions, not just its shape.
 ensure(checkpoint.reportSha256===PINNED['work/dev15-capacity-20261102/phase-a-report.json']
  &&checkpoint.receiptSha256===sha(record(phaseAFile))&&stable(checkpoint.finalAudit)===stable(a.helper.finalAudit)
  &&checkpoint.finalAudit.stateDigest===b.beforeAudit.stateDigest
  &&stable(checkpoint.finalAudit.head)===stable(b.beforeAudit.head)
  &&stable(checkpoint.finalAudit.counts)===stable(b.beforeAudit.counts),'EV_CAPACITY_CHECKPOINT');
 ensure(a.helper.reserveRefusal.stateUnchanged===true&&a.helper.reserveRefusal.head.reserved_bytes===16772006
  &&a.helper.reserveRefusal.nextReserveBytes===8194&&16772006+8194>CAPS.completionBytes,'EV_RESERVE_RESULT');
 const dto=a.helper.groups.find(x=>x.id==='RP15-009');
 ensure(dto?.status==='PASS'&&dto.positiveKeys===256&&dto.positiveTargetUtf8Bytes===2048&&dto.negativeSqlConnect===0,'EV_DTO_RESULT');
 const tlsIntentFile=runtime+'/worker-tls-read-intent.json',tlsIntent=signed(tlsIntentFile,'DEV15-WORKER-TLS-READ-INTENT');
 closed(tlsIntent.readBinding,['payload','signature']);ensure(tlsIntent.readBinding.signature===mac(tlsIntent.readBinding.payload),'EV_READ_BINDING_HMAC');
 ensure(tlsIntent.sourceSha256===SOURCE&&tlsIntent.readBinding.payload.archiveReceiptSha256===sha(record(capFile))
  &&tlsIntent.readBinding.payload.candidateAttemptSha256===sha(record(candidateFile))
  &&tlsIntent.readBinding.payload.actualSourceSha256===SOURCE&&tlsIntent.readBinding.payload.historicalSourceSha256===OLD
  &&tlsIntent.readBinding.payload.archiveDatabase==='test_estakada_trust_cap_32563'
  &&tlsIntent.readBinding.payload.archiveOid===32563
  &&tlsIntent.readBinding.payload.candidateReportSha256===PINNED['work/dev15-corpus-20261102/candidate-test-report.json']
  &&tlsIntent.readBinding.payload.integrationSha256===PINNED['work/dev15-corpus-20261102/candidate-integration.json'],'EV_TLS_LINEAGE');
 ensure(tls.status==='PASS'&&tls.dataRetained===true&&tls.actualSourceSha256===SOURCE&&tls.historicalPolicySourceSha256===OLD
  &&tls.probe.status==='PASS'&&tls.probe.requests===54&&tls.probe.successfulRequests===54&&tls.probe.pageResponses===52
  &&tls.probe.items===5120&&tls.probe.routes===4096&&tls.probe.tombstones===1024&&tls.probe.retries===0
  &&tls.probe.wholeDeadlineSeconds===30&&tls.probe.requestDeadlineSeconds===6&&tls.probe.readSnapshotCalls===1
  &&tls.probe.snapshotDigest===SNAPSHOT&&tls.probe.readSnapshotElapsedSeconds<=30
  &&tls.probe.sourceMatchesHistoricalWritePolicy===false,'EV_TLS_RESULT');
 ensure(b.helper.snapshot.manifest.snapshotDigest===SNAPSHOT&&b.helper.snapshot.sqlPages===52,'EV_SNAPSHOT_JOIN');
 const raAttempt=signed('work/dev15-resource-20261102/resource-attempt.json','DEV15-RESOURCE-ATTEMPT');
 ensure(raAttempt.sourceSha256===SOURCE&&raAttempt.authority==='D-385','EV_RESOURCE_ATTEMPT');
 for(const [file,digest]of Object.entries(raAttempt.inputHashes))ensure(sha(record(file))===digest,'EV_RA_INPUT_LINK');
 ensure(ra.status==='PASS'&&ra.dataRetained===true&&ra.sourceDrift===0&&ra.ownedContainersIncludingStopped===0
  &&ra.budget.observedPlusReservationBytes===317325492&&ra.budget.observedPlusReservationBytes<=2147483648
  &&ra.hardDiskQuota===false&&ra.budget.hardQuota===false,'EV_RESOURCE_RESULT');
 const lgAttemptFile='work/dev15-legacy-inclusion-20261102/legacy-capacity-attempt.json';
 const lgAttempt=signed(lgAttemptFile,'DEV15-LEGACY-CAPACITY-ATTEMPT');
 ensure(lgAttempt.sourceSha256===SOURCE&&lgAttempt.runId===lg.runId&&lgAttempt.authority==='D-386','EV_LG_ATTEMPT');
 ensure(sha(record('work/dev15-legacy-inclusion-20261102/controller-before-compose-escape.mjs'))===lgAttempt.controllerSha256
  &&lgAttempt.controllerSha256===assessment.originalControllerBackupSha256
  &&assessment.originalControllerBackupSha256==='e6211911d00ea2fa7892b5888cf1392139a4c863887cb88184108568bc2656de'
  &&sha(record('tools/test-trust-legacy-capacity.mjs'))===assessment.correctedControllerSha256
  &&assessment.correctedControllerSha256===smoke.controllerSha256
  &&smoke.controllerSha256==='9030bcd847c15c71416ca88fbb6cb1627a5ca9ca293562799ef2cdabb5413f60','EV_LG_CONTROLLER_LEAVES');
 for(const [file,digest]of Object.entries(lgAttempt.inputHashes))ensure(sha(record(file))===digest,'EV_LG_INPUT_LINK');
 const fixtureFile=privateDirectory+'/legacy-capacity-fixture-intent-'+lg.runId+'.json';
 const fixture=signed(fixtureFile,'DEV15-LEGACY-FIXTURE-INTENT');
 ensure(lg.fixtureIntentSha256===sha(record(fixtureFile))&&fixture.sourceSha256===SOURCE&&fixture.runId===lg.runId
  &&fixture.attemptSha256===sha(record(lgAttemptFile))&&fixture.exportSha256===lg.export.reportSha256
  &&fixture.unitBaselineSha256===sha(Buffer.from(stable(lg.unitBaseline)))
  &&fixture.credentialConfigSha256===sha(read(privateDirectory+'/credentials.json')),'EV_LG_FIXTURE_LINK');
 ensure(lg.status==='FAIL'&&lg.probeExecution.state.exitCode===2&&lg.probe.status==='PASS'
  &&lg.probe.groups.length===3&&lg.probe.groups.every(g=>g.status==='PASS'&&g.legacyUnchanged===true
   &&g.branchRollbackVerified===true&&g.prepareUnknownTerminalReplay===true)
  &&lg.mainArchivesRetained===true&&lg.unitPreserved===true&&stable(lg.unitBaseline)===stable(lg.unitAfter)
  &&lg.probe.outerRollbackVerified===true&&lg.probe.legacyHistoricalReferences===3,'EV_LG_SEMANTIC_RESULT');
 ensure(assessment.status==='ACCEPTED_SELECTED_EVIDENCE'&&assessment.sourceSha256===SOURCE
  &&assessment.semantic==='PASS'&&assessment.preservation==='PASS'&&assessment.wrapperSmoke==='PASS'
  &&assessment.originalController==='FAIL'&&assessment.controllerAfterFix==='NOT_RUN'
  &&assessment.originalFailureSha256===PINNED['work/dev15-legacy-inclusion-20261102/legacy-capacity-report.json']
  &&assessment.originalAttemptSha256===sha(record(lgAttemptFile))
  &&assessment.wrapperSmokeSha256===PINNED['work/dev15-legacy-inclusion-20261102/wrapper-smoke-report.json']
  &&assessment.independentReviewArtifactSha256===PINNED['docs/dev15-legacy-quota-review.md'],'EV_LG_ASSESSMENT');
 linked('work/dev15-legacy-inclusion-20261102/final-preservation.json',assessment.finalPreservationSha256);
 ensure(smoke.status==='PASS'&&smoke.parentFailureSha256===assessment.originalFailureSha256
  &&smoke.controllerSha256===assessment.correctedControllerSha256&&smoke.cases.length===2
  &&stable(smoke.cases.map(x=>x.expectedExit))===stable([0,7])&&smoke.cases.every(x=>x.status==='PASS'
   &&x.actualExit===x.expectedExit&&x.actualCommandMatches===true&&x.postFrameCaptured===true
   &&x.cgroup.memoryEvents.oom===0&&x.cgroup.memoryEvents.oom_kill===0)
  &&smoke.ownedContainersIncludingStopped===0,'EV_WRAPPER_SMOKE');
 const m=get(runtime+'/manifest.json');ensure(m.active===false&&m.writeMode==='disabled'&&m.sourceSha256===SOURCE,'EV_WRITER_NOT_DISABLED');
 sourceRows(m.sourceFiles,m.sourceDirectory,SOURCE);
 for(const [file,digest]of Object.entries(m.configHashes))ensure(sha(record(file))===digest,'EV_CONFIGURATION_DRIFT');
 ensure(read(privateDirectory+'/write-profile.json').toString().trim()==='{}','EV_PERMIT_OPEN');
 const bounded=record('trust/journal/bounded.py').toString(),literal=bounded.match(/^CAPS = (\{[\s\S]*?\})/m);
 ensure(literal&&stable(JSON.parse(literal[1].replaceAll("'",'"')))===stable(CAPS),'EV_CAPS_DRIFT');
 const tests=read('trust/journal/test_bounded.py').toString();
 for(const name of ['test_rp010_combined_budget_preserves_existing_completion_and_replays',
  'test_rp010_policy_charge_cannot_consume_reserved_completion_budget','test_rp010_fence_cannot_consume_full_combined_completion_budget'])
  ensure(tests.includes('def '+name+'('),'EV_INJECTION_TEST_PROVENANCE');
 for(const file of ['docs/dev15-runtime-verification-plan.md','docs/dev15-capacity-gates.md',
  'docs/dev15-runtime-implementation-results.md','docs/dev15-candidate-regression-results.md',
  'docs/dev15-worker-tls-results.md','docs/dev15-resource-results.md','docs/dev15-legacy-quota-results.md'])record(file);
 return {inputs:[...inputs.values()].sort((a,b)=>a.path<b.path?-1:a.path>b.path?1:0),
  sourceProof:{oldFingerprint:OLD,currentFingerprint:SOURCE,oldSourceDirectory:relative(cap.sourceDirectory),
   newPreviewDirectory:relative(candidate.previewDirectory),currentFrozenDirectory:relative(m.sourceDirectory),
   oldFiles:oldRows,newFiles:newRows,changedFiles:differences,unchangedFiles:29},
  facts:{unitCount:131,unitSeconds:unit.tests.seconds,legacyHistoricalReferences:3,
   tlsSeconds:tls.probe.readSnapshotElapsedSeconds,tlsRequests:54,tlsPages:52,snapshotDigest:SNAPSHOT,
   observedBudgetBytes:ra.budget.observedPlusReservationBytes,lgOriginalHostStatus:'FAIL',lgWrapperExit:2}};
}

function coverage(){const refs={unit:['work/dev15-corpus-20261102/candidate-test-report.json',
 'work/dev15-corpus-20261102/candidate-integration.json','docs/dev15-runtime-implementation-review.md','docs/dev15-candidate-regression-review.md'],
 capacity:['work/dev15-capacity-20261102/phase-a-report.json','work/dev15-capacity-20261102/phase-b-report.json','docs/dev15-capacity-review.md'],
 legacy:['work/dev15-legacy-inclusion-20261102/legacy-capacity-assessment.json','work/dev15-legacy-inclusion-20261102/legacy-capacity-report.json',
 'work/dev15-legacy-inclusion-20261102/wrapper-smoke-report.json','docs/dev15-legacy-quota-review.md']};
 const result=Array.from({length:7},(_,i)=>({id:'RP15-'+String(i+1).padStart(3,'0'),status:'PASS',
  scope:'accepted-current-source-131-UNIT-and-integration-provenance-not-native-container-exclusion',evidence:refs.unit}));
 result.push({id:'RP15-008',status:'PASS',scope:'fresh-retained-capacity-plus-real-legacy-inclusion-composite',evidence:[...refs.capacity,...refs.legacy]},
 {id:'RP15-009',status:'PASS',scope:'old-capacity-server-29-files-unchanged-current-131-wire-limit-negative',evidence:[...refs.capacity,...refs.unit]},
 {id:'RP15-010',status:'PASS',scope:'actual-16MiB-reserve-plus-plan-authorized-64MiB-accounting-injection-not-retained-64MiB-corpus',evidence:[...refs.capacity,...refs.unit,'docs/dev15-capacity-gates.md']},
 {id:'RP15-011',status:'PASS',scope:'one-real-54-request-5120-item-fixed-TLS-worker-read-under-30s-not-arbitrary-load-guarantee',
  evidence:['work/dev15-wb005-20261102/worker-tls-report.json','docs/dev15-worker-tls-review.md',...refs.capacity]},
 {id:'RP15-012',status:'PASS',scope:'accepted-observed-resource-budget-beforeStop-with-reservations-distinct-periods-not-hard-quota',
  evidence:['work/dev15-resource-20261102/resource-report.json','docs/dev15-resource-review.md','work/dev15-wb005-20261102/worker-tls-report.json']},
 {id:'CODE',status:'PASS',scope:'historical-independent-code-reviews-for-unchanged-server-and-new-consumer',evidence:refs.unit.slice(2)},
 {id:'QA',status:'PASS',scope:'current-source-131-and-accepted-scoped-result-reviews',evidence:refs.unit},
 {id:'CAPACITY',status:'PASS',scope:'accepted-mixed-source-and-composite-scoped-result-reviews',evidence:[...refs.capacity,...refs.legacy,
  'docs/dev15-worker-tls-review.md','docs/dev15-resource-review.md']});return result;}

function prepare(collected,gate){
 ensure(!fs.existsSync(inside(packageDirectory)),'EV_PACKAGE_ALREADY_EXISTS');
 const attempt={scope:'DEV15-EVIDENCE-PREPARE-ATTEMPT',authority:'D-388',builderSha256:sha(read(self)),
  codeGate:gate,sourceFingerprint:SOURCE,schemaFingerprint:SCHEMA,inputInventorySha256:sha(raw(collected.inputs)),
  credentialConfigSha256:sha(read(privateDirectory+'/credentials.json')),mainActivation:false,native:false};
 write(work+'/prepare-attempt.json',{payload:attempt,signature:mac(attempt)});
 fs.mkdirSync(inside(packageDirectory),{mode:0o700});
 const unit=manifest('unit'),calibration=manifest('calibration'),review=manifest('review');
 const unitSha=write(packageDirectory+'/unit.json',unit),calibrationSha=write(packageDirectory+'/calibration.json',calibration);
 const definition={scope:'DEV15-PROSPECTIVE-REVIEW-DEFINITION',notEvidenceUntilFinalize:true,
  manifest:review,prospectiveReviewSha256:sha(raw(review))};
 const definitionSha=write(packageDirectory+'/review-definition.json',definition);
 const provenance={scope:'DEV15-EVIDENCE-PROVENANCE',authority:'D-388',sourceFingerprint:SOURCE,
  schemaFingerprint:SCHEMA,caps:CAPS,builderSha256:sha(read(self)),prepareAttemptSha256:sha(read(work+'/prepare-attempt.json')),
  codeGate:gate,inputs:collected.inputs,sourceProof:collected.sourceProof,facts:collected.facts,coverage:coverage(),
  manifests:{unitSha256:unitSha,calibrationSha256:calibrationSha,prospectiveReviewSha256:definition.prospectiveReviewSha256,
   reviewDefinitionSha256:definitionSha},limitations:{oldSourceIsNotNewRuntime:true,unchangedServerFiles:29,
   unitMayUseExplicitHostRuntimeFixtures:true,logical64MiB:'plan-authorized-accounting-injection-not-retained-disk-corpus',
   resourcePeriods:'separate-container-windows-beforeStop-and-bounded-artifact-reservations',hardQuota:false,
   lgSemantic:'PASS',lgPreservation:'PASS',lgWrapperSmoke:'PASS',lgOriginalController:'FAIL',
   lgOriginalHostFailureSha256:PINNED['work/dev15-legacy-inclusion-20261102/legacy-capacity-report.json'],
   lgWrapperSmokeSha256:PINNED['work/dev15-legacy-inclusion-20261102/wrapper-smoke-report.json'],lgControllerAfterFix:'NOT_RUN',
   nativeRP15_013_019:'NOT_RUN',mainActivation:false,production:false,externalReady:false},
  packageReview:'NOT_RUN',validatorExecution:'NOT_RUN',privateRawCopied:false,policyOrLeaseIssued:false};
 const provenanceSha=write(packageDirectory+'/provenance.json',provenance);
 return {status:'PREPARED_NOT_FINALIZED',unitSha256:unitSha,calibrationSha256:calibrationSha,
  provenanceSha256:provenanceSha,reviewDefinitionSha256:definitionSha,prospectiveReviewSha256:definition.prospectiveReviewSha256};
}

function finalize(collected,gate){
 const provenance=json(packageDirectory+'/provenance.json'),definition=json(packageDirectory+'/review-definition.json');
 ensure(provenance.scope==='DEV15-EVIDENCE-PROVENANCE'&&provenance.authority==='D-388'
  &&provenance.sourceFingerprint===SOURCE&&provenance.schemaFingerprint===SCHEMA&&stable(provenance.caps)===stable(CAPS)
  &&provenance.privateRawCopied===false&&provenance.policyOrLeaseIssued===false
  &&provenance.packageReview==='NOT_RUN'&&provenance.validatorExecution==='NOT_RUN'
  &&stable(provenance.inputs)===stable(collected.inputs)&&stable(provenance.sourceProof)===stable(collected.sourceProof)
  &&stable(provenance.facts)===stable(collected.facts)&&stable(provenance.coverage)===stable(coverage())
  &&provenance.builderSha256===sha(read(self))&&stable(provenance.codeGate)===stable(gate),'EV_PROVENANCE_DRIFT');
 const prepareEnvelope=json(work+'/prepare-attempt.json');closed(prepareEnvelope,['payload','signature']);
 ensure(prepareEnvelope.signature===mac(prepareEnvelope.payload)&&provenance.prepareAttemptSha256===sha(read(work+'/prepare-attempt.json'))
  &&prepareEnvelope.payload.inputInventorySha256===sha(raw(collected.inputs))
  &&prepareEnvelope.payload.credentialConfigSha256===sha(read(privateDirectory+'/credentials.json')),'EV_PREPARE_RECEIPT');
 ensure(stable(json(packageDirectory+'/unit.json'))===stable(manifest('unit'))
  &&stable(json(packageDirectory+'/calibration.json'))===stable(manifest('calibration')),'EV_MANIFEST_DRIFT');
 closed(definition,['scope','notEvidenceUntilFinalize','manifest','prospectiveReviewSha256']);
 ensure(definition.scope==='DEV15-PROSPECTIVE-REVIEW-DEFINITION'&&definition.notEvidenceUntilFinalize===true
  &&stable(definition.manifest)===stable(manifest('review'))&&sha(raw(definition.manifest))===definition.prospectiveReviewSha256,'EV_REVIEW_DEFINITION');
 ensure(provenance.manifests.unitSha256===sha(read(packageDirectory+'/unit.json'))
  &&provenance.manifests.calibrationSha256===sha(read(packageDirectory+'/calibration.json'))
  &&provenance.manifests.reviewDefinitionSha256===sha(read(packageDirectory+'/review-definition.json'))
  &&provenance.manifests.prospectiveReviewSha256===definition.prospectiveReviewSha256,'EV_PROVENANCE_MANIFEST_LINKS');
 const gateFile=work+'/package-review-gate.json',reviewGate=json(gateFile);
 closed(reviewGate,['status','authority','files','prospectiveReviewSha256','coverageReview']);
 ensure(reviewGate.status==='APPROVED'&&reviewGate.authority==='D-388'&&Array.isArray(reviewGate.files)
  &&reviewGate.prospectiveReviewSha256===definition.prospectiveReviewSha256,'EV_PACKAGE_REVIEW_GATE');
 const required=new Set([relative(self),packageDirectory+'/unit.json',packageDirectory+'/calibration.json',
  packageDirectory+'/provenance.json',packageDirectory+'/review-definition.json']),seen=new Set();
 for(const entry of reviewGate.files){closed(entry,['path','sha256']);const name=relative(entry.path);
  ensure(!seen.has(name)&&sha(read(name))===entry.sha256,'EV_PACKAGE_REVIEW_DRIFT');seen.add(name);required.delete(name);}
 ensure(required.size===0,'EV_PACKAGE_REVIEW_INCOMPLETE');
 closed(reviewGate.coverageReview,['path','sha256']);const coveragePath=relative(reviewGate.coverageReview.path);
 ensure(coveragePath.startsWith(work+'/')&&!coveragePath.startsWith(packageDirectory+'/'), 'EV_COVERAGE_REVIEW_PATH');
 const reviewMeta=json(coveragePath);ensure(sha(read(coveragePath))===reviewGate.coverageReview.sha256,'EV_COVERAGE_REVIEW_SHA');
 closed(reviewMeta,['status','scope','authority','sourceFingerprint','schemaFingerprint','checks','unitSha256',
  'calibrationSha256','provenanceSha256','prospectiveReviewSha256','builderSha256','limitationsAccepted']);
 ensure(reviewMeta.status==='APPROVED'&&reviewMeta.scope==='DEV15-EVIDENCE-PACKAGE-REVIEW'&&reviewMeta.authority==='D-388'
  &&reviewMeta.sourceFingerprint===SOURCE&&reviewMeta.schemaFingerprint===SCHEMA&&stable(reviewMeta.checks)===stable(['CODE','QA','CAPACITY'])
  &&reviewMeta.unitSha256===sha(read(packageDirectory+'/unit.json'))&&reviewMeta.calibrationSha256===sha(read(packageDirectory+'/calibration.json'))
  &&reviewMeta.provenanceSha256===sha(read(packageDirectory+'/provenance.json'))&&reviewMeta.prospectiveReviewSha256===definition.prospectiveReviewSha256
  &&reviewMeta.builderSha256===sha(read(self))&&reviewMeta.limitationsAccepted===true,'EV_COVERAGE_REVIEW_REJECTED');
 ensure(!fs.existsSync(inside(packageDirectory+'/review.json'))&&!fs.existsSync(inside(packageDirectory+'/receipt.json')),'EV_ALREADY_FINALIZED');
 const attempt={scope:'DEV15-EVIDENCE-FINALIZE-ATTEMPT',authority:'D-388',sourceFingerprint:SOURCE,
  prepareAttemptSha256:sha(read(work+'/prepare-attempt.json')),builderSha256:sha(read(self)),
  packageReviewGateSha256:sha(read(gateFile)),coverageReview:{path:coveragePath,sha256:sha(read(coveragePath))},
  prospectiveReviewSha256:definition.prospectiveReviewSha256};
 write(work+'/finalize-attempt.json',{payload:attempt,signature:mac(attempt)});
 const reviewSha=write(packageDirectory+'/review.json',definition.manifest);ensure(reviewSha===definition.prospectiveReviewSha256,'EV_REVIEW_OUTPUT_SHA');
 const files=Object.fromEntries(['unit.json','calibration.json','review.json','provenance.json','review-definition.json'].map(name=>[name,sha(read(packageDirectory+'/'+name))]));
 const receipt={scope:'DEV15-EVIDENCE-FINALIZED',authority:'D-388',status:'PASS',sourceFingerprint:SOURCE,
  schemaFingerprint:SCHEMA,caps:CAPS,files,prepareAttemptSha256:sha(read(work+'/prepare-attempt.json')),
  finalizeAttemptSha256:sha(read(work+'/finalize-attempt.json')),builderSha256:sha(read(self)),
  packageReviewGateSha256:sha(read(gateFile)),coverageReviewSha256:sha(read(coveragePath)),
  validatorExecution:'NOT_RUN',mainActivation:false,policyOrLeaseIssued:false,native:false,production:false};
 const receiptSha=write(packageDirectory+'/receipt.json',{payload:receipt,signature:mac(receipt)});
 return {status:'FINALIZED_VALIDATOR_NOT_RUN',receiptSha256:receiptSha,files};
}

try{
 ensure(process.argv.length===3&&['Prepare','Finalize'].includes(process.argv[2]),'EV_CLOSED_PHASE');
 for(const key of Object.keys(process.env))ensure(!key.startsWith('TRUST_'),'EV_ENV_OVERRIDE');
 const gate=codeGate(),collected=collect();
 const result=process.argv[2]==='Prepare'?prepare(collected,gate):finalize(collected,gate);
 console.log(JSON.stringify({phase:process.argv[2],...result}));
}catch(error){console.log(JSON.stringify({status:'FAIL',phase:['Prepare','Finalize'].includes(process.argv[2])?process.argv[2]:null,
 errorCode:/^[A-Z0-9_]{1,80}$/.test(error?.message||'')?error.message:'EV_BUILDER_FAILED',mainActivation:false}));process.exitCode=1;}
