import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await use(app); } finally { await app.close(); }
} });
const id = value => { expect(typeof value === 'string' && value.trim().length > 0).toBe(true); return value; };
const integer = value => { expect(Number.isSafeInteger(value) && value >= 0).toBe(true); return value; };
const hash = value => { expect(value).toMatch(/^[a-f0-9]{64}$/); return value; };
const time = value => { id(value); const parsed = Date.parse(value); expect(Number.isFinite(parsed)).toBe(true); return parsed; };

async function setup(app, profile = 'backup-seven-verified-two-local') {
  const admission = await app.inspectInfrastructureAdmission();
  expect(admission.arc10Verified).toBe(true); expect(admission.isolatedInfrastructure).toBe(true);
  id(admission.reviewedEvidenceId); expect(admission.capabilities).toContain('backup-control-v1');
  await app.reset(profile);
}
async function control(app, action, args = {}) {
  const result = await app.control(action, args); expect(result.outcome).toBe('accepted'); return result;
}
function point(value) {
  for (const key of ['id', 'epochId', 'applicationDigest', 'schemaVersion']) id(value[key]);
  time(value.cutoffAt); integer(value.bytes); expect(value.bytes).toBeGreaterThan(0);
  hash(value.manifestSha256); hash(value.archiveSha256);
  expect(typeof value.verified).toBe('boolean');
  for (const where of ['local', 'external']) expect(typeof value.locations?.[where]).toBe('boolean');
  if (value.verified) time(value.verifiedAt);
  return value;
}
async function catalog(app) {
  const value = await app.observe('backup-catalog');
  expect(Array.isArray(value.points)).toBe(true); expect(value.points.length).toBeGreaterThan(0);
  value.points.forEach(point); expect(new Set(value.points.map(item => item.id)).size).toBe(value.points.length);
  expect(value.authoritativeSource).toBe('independent-signed-catalog');
  return value;
}
const verified = (value, where) => value.points.filter(item => item.verified && item.locations[where]);
function ids(points) { return points.map(item => item.id).sort(); }
function fingerprints(points) { return points.map(item => ({ id: item.id, epochId: item.epochId,
  manifestSha256: item.manifestSha256, archiveSha256: item.archiveSha256 })).sort((a, b) => a.id.localeCompare(b.id)); }
function mediaObjects(value) {
  expect(Array.isArray(value)).toBe(true); expect(value.length).toBeGreaterThan(0);
  const actual = value.map(item => ({ objectId: id(item.objectId), sha256: hash(item.sha256), bytes: integer(item.bytes) }));
  for (const item of actual) expect(item.bytes).toBeGreaterThan(0);
  expect(new Set(actual.map(item => item.objectId)).size).toBe(actual.length);
  return actual.sort((a, b) => a.objectId.localeCompare(b.objectId));
}
function pointArtifacts(value, pointId, storage) {
  return value.filter(item => item.pointId === pointId && item.storage === storage)
    .map(item => ({ artifactId: item.artifactId, kind: item.kind, sha256: item.sha256, bytes: item.bytes }))
    .sort((a, b) => a.artifactId.localeCompare(b.artifactId));
}
async function retentionSnapshot(app) {
  const actual = await catalog(app);
  const physical = await app.observe('backup-retained-artifact-inventory', { readMode: 'out-of-band-isolated-volume' });
  expect(physical.source).toBe('actual-storage-bytes-out-of-band');
  expect(Array.isArray(physical.artifacts)).toBe(true); expect(physical.artifacts.length).toBeGreaterThan(0);
  for (const item of physical.artifacts) {
    id(item.pointId); id(item.artifactId); expect(['local', 'external']).toContain(item.storage);
    expect(['manifest', 'ciphertext']).toContain(item.kind); expect(typeof item.exists).toBe('boolean');
    if (item.exists) { hash(item.sha256); integer(item.bytes); expect(item.bytes).toBeGreaterThan(0); }
  }
  expect(new Set(physical.artifacts.map(item => `${item.storage}:${item.pointId}:${item.artifactId}`)).size).toBe(physical.artifacts.length);
  const reconstructions = [];
  for (const storage of ['local', 'external']) for (const entry of verified(actual, storage)) {
    const entries = physical.artifacts.filter(item => item.pointId === entry.id && item.storage === storage);
    for (const kind of ['manifest', 'ciphertext']) expect(entries.some(item => item.kind === kind)).toBe(true);
    for (const item of entries) expect(item.exists).toBe(true);
    const reconstructed = await app.observe('backup-retained-point-reconstruction', {
      pointId: entry.id, storage, readMode: 'out-of-band-isolated-volume',
    });
    expect(reconstructed.pointId).toBe(entry.id); expect(reconstructed.storage).toBe(storage);
    expect(reconstructed.source).toBe('full-reconstruction-from-storage-bytes-out-of-band');
    expect(reconstructed.reconstructionSucceeded).toBe(true); expect(reconstructed.manifestSignatureValid).toBe(true);
    expect(hash(reconstructed.manifestSha256)).toBe(entry.manifestSha256); hash(reconstructed.dumpSha256);
    const manifest = await app.observe('backup-full-manifest', { pointId: entry.id, storage, readMode: 'out-of-band-isolated-volume' });
    expect(manifest.pointId).toBe(entry.id); expect(hash(manifest.dumpSha256)).toBe(reconstructed.dumpSha256);
    const media = mediaObjects(reconstructed.media);
    expect(media).toEqual(mediaObjects(manifest.media));
    reconstructions.push({ pointId: entry.id, storage, manifestSha256: reconstructed.manifestSha256,
      dumpSha256: reconstructed.dumpSha256, media });
  }
  return { ...actual, artifactEvidence: physical.artifacts, reconstructionEvidence: reconstructions };
}
async function run(app, args = {}) {
  const previousIds = (await catalog(app)).points.map(item => item.id);
  const result = await control(app, 'run-isolated-backup-job', args);
  id(result.jobId); id(result.candidatePointId); expect(previousIds).not.toContain(result.candidatePointId); return result;
}
async function finish(app, job, expected) {
  await expect.poll(async () => (await app.observe('backup-job-state', { jobId: job.jobId })).state, { timeout: 10_000 }).toBe(expected);
  const actual = await app.observe('backup-job-state', { jobId: job.jobId });
  expect(actual.jobId).toBe(job.jobId); expect(actual.pointId).toBe(job.candidatePointId);
  expect(actual.state).toBe(expected); time(actual.startedAt); time(actual.finishedAt);
  return actual;
}
async function retained(app, before, job) {
  const after = await retentionSnapshot(app);
  expect(Array.isArray(before.artifactEvidence)).toBe(true); expect(before.artifactEvidence.length).toBeGreaterThan(0);
  expect(Array.isArray(before.reconstructionEvidence)).toBe(true); expect(before.reconstructionEvidence.length).toBeGreaterThan(0);
  for (const [where, capacity] of [['external', 7], ['local', 2]]) {
    const old = verified(before, where), actual = verified(after, where);
    expect(old.length).toBeGreaterThan(0); expect(actual.length).toBeGreaterThanOrEqual(old.length);
    const missing = old.filter(item => !actual.some(next => next.id === item.id));
    const added = actual.filter(item => !old.some(previous => previous.id === item.id));
    for (const item of old.filter(item => !missing.includes(item))) {
      expect(fingerprints([actual.find(next => next.id === item.id)])).toEqual(fingerprints([item]));
      const previousBytes = pointArtifacts(before.artifactEvidence, item.id, where);
      expect(previousBytes.length).toBeGreaterThan(0);
      expect(pointArtifacts(after.artifactEvidence, item.id, where)).toEqual(previousBytes);
      const originalSet = before.reconstructionEvidence.find(entry => entry.pointId === item.id && entry.storage === where);
      expect(originalSet).toBeTruthy();
      expect(after.reconstructionEvidence.find(entry => entry.pointId === item.id && entry.storage === where)).toEqual(originalSet);
    }
    if (!added.length) expect(ids(actual)).toEqual(ids(old));
    if (missing.length) {
      // A globally failed job may have a separately verified local copy; only a genuinely
      // verified replacement at this location can permit normal rotation of its oldest point.
      expect(old.length).toBeGreaterThanOrEqual(capacity); expect(added.length).toBeGreaterThanOrEqual(missing.length);
      expect(ids(missing)).toEqual(ids([...old].sort((a, b) => time(a.cutoffAt) - time(b.cutoffAt)).slice(0, missing.length)));
      const ledger = await app.observe('backup-operation-ledger', { jobId: job.jobId }); expect(Array.isArray(ledger.events)).toBe(true);
      for (const removed of missing) {
        const retire = ledger.events.find(event => event.kind === 'point-retired' && event.pointId === removed.id && event.storage === where);
        expect(retire).toBeTruthy(); integer(retire.sequence);
        expect(ledger.events.some(event => event.kind === 'point-verified' && event.storage === where &&
          added.some(item => item.id === event.pointId) && Number.isSafeInteger(event.sequence) && event.sequence >= 0 && event.sequence < retire.sequence)).toBe(true);
      }
    }
  }
  return after;
}
async function failureEvidence(app, job) {
  const actual = await app.observe('backup-job-state', { jobId: job.jobId });
  id(actual.safeErrorCode); expect(actual.state).toBe('failed');
  const notices = await app.observe('backup-failure-evidence', { jobId: job.jobId });
  expect(notices.jobId).toBe(job.jobId); expect(notices.auditRecorded).toBe(true);
  expect(notices.successReported).toBe(false); expect(notices.notificationCycleOpened).toBe(true);
}

test('BACKUP-retention-baseline | AT-043 AC-043 | seven verified external and two newest local points are genuinely present', async ({ app }) => {
  await setup(app); const actual = await retentionSnapshot(app);
  const external = verified(actual, 'external'), local = verified(actual, 'local');
  expect(external).toHaveLength(7); expect(local).toHaveLength(2);
  const latest = [...external].sort((a, b) => time(b.cutoffAt) - time(a.cutoffAt)).slice(0, 2);
  expect(ids(local)).toEqual(ids(latest));
  const storage = await app.observe('backup-storage-inventory');
  for (const entry of [...external, ...local]) {
    expect(storage.externalPointIds).toContain(entry.id);
    if (entry.locations.local) expect(storage.localPointIds).toContain(entry.id);
  }
});

test('BACKUP-verified-rotation | AT-043 AC-043 | the oldest point retires only after the new full point has verified', async ({ app }) => {
  await setup(app); const before = await retentionSnapshot(app), old = [...verified(before, 'external')].sort((a, b) => time(a.cutoffAt) - time(b.cutoffAt))[0];
  expect(verified(before, 'external')).toHaveLength(7); expect(verified(before, 'local')).toHaveLength(2);
  const job = await run(app); await finish(app, job, 'succeeded'); const after = await retentionSnapshot(app);
  expect(verified(after, 'external')).toHaveLength(7); expect(verified(after, 'local')).toHaveLength(2);
  const created = verified(after, 'external').find(item => item.id === job.candidatePointId); expect(created).toBeTruthy();
  expect(verified(after, 'local').some(item => item.id === created.id)).toBe(true);
  expect(ids(verified(after, 'external'))).not.toContain(old.id);
  for (const entry of verified(before, 'external').filter(item => item.id !== old.id)) expect(ids(verified(after, 'external'))).toContain(entry.id);
  const ledger = await app.observe('backup-operation-ledger', { jobId: job.jobId });
  expect(Array.isArray(ledger.events)).toBe(true);
  const verify = ledger.events.find(item => item.kind === 'point-verified' && item.pointId === created.id);
  const retire = ledger.events.find(item => item.kind === 'point-retired' && item.pointId === old.id);
  expect(verify).toBeTruthy(); expect(retire).toBeTruthy(); integer(verify.sequence); integer(retire.sequence);
  expect(verify.sequence).toBeLessThan(retire.sequence);
});

test('BACKUP-epoch-manifest | AT-043 AC-043 | each manifest binds full dump/media/application/schema to one independently captured epoch', async ({ app }) => {
  await setup(app); const points = verified(await catalog(app), 'external'); expect(points).toHaveLength(7);
  for (const item of points) {
    const manifest = await app.observe('backup-full-manifest', { pointId: item.id });
    const oracle = await app.observe('backup-epoch-source-inventory', { epochId: item.epochId });
    expect(oracle.source).toBe('captured-source-epoch'); expect(oracle.epochId).toBe(item.epochId);
    for (const key of ['dumpEpochId', 'mediaEpochId']) expect(manifest[key]).toBe(item.epochId);
    expect(manifest.pointId).toBe(item.id); expect(manifest.epochId).toBe(item.epochId);
    expect(manifest.applicationDigest).toBe(item.applicationDigest); expect(manifest.schemaVersion).toBe(item.schemaVersion);
    expect(Array.isArray(oracle.migrations)).toBe(true); expect(oracle.migrations.length).toBeGreaterThan(0); oracle.migrations.forEach(id);
    expect(Array.isArray(manifest.appliedMigrations)).toBe(true); manifest.appliedMigrations.forEach(id);
    expect([...manifest.appliedMigrations].sort()).toEqual([...oracle.migrations].sort());
    hash(manifest.dumpSha256); expect(manifest.dumpSha256).toBe(hash(oracle.dumpSha256));
    expect(Array.isArray(oracle.media)).toBe(true); expect(oracle.media.length).toBeGreaterThan(0);
    for (const entry of oracle.media) { id(entry.objectId); hash(entry.sha256); integer(entry.bytes); expect(entry.bytes).toBeGreaterThan(0); }
    expect(mediaObjects(manifest.media)).toEqual(mediaObjects(oracle.media));
  }
});

test('BACKUP-encryption-key-boundary | AT-043 AC-043 | encrypted artifacts are checked without placing the decryption key in the backup or app DB', async ({ app }) => {
  await setup(app); const job = await run(app); await finish(app, job, 'succeeded');
  const selected = verified(await catalog(app), 'external').find(item => item.id === job.candidatePointId); expect(selected).toBeTruthy();
  const actual = await app.observe('backup-archive-security-inspection', { pointId: selected.id });
  expect(actual.pointId).toBe(selected.id); expect(actual.source).toBe('artifact-crypto-and-decrypted-inventory-inspection');
  expect(hash(actual.archiveSha256)).toBe(selected.archiveSha256);
  expect(actual.cryptoValidationPassed).toBe(true); expect(actual.uploadedEncrypted).toBe(true);
  expect(actual.decryptionCheckPassed).toBe(true); expect(actual.decryptionKeyIncluded).toBe(false);
  expect(actual.keyInAppDb).toBe(false); expect(actual.keyInBackupStorage).toBe(false);
  expect(actual.independentKeyRetrievalPassed).toBe(true);
  expect(Array.isArray(actual.secretCanaryReferencesChecked)).toBe(true); expect(actual.secretCanaryReferencesChecked.length).toBeGreaterThan(0); actual.secretCanaryReferencesChecked.forEach(id);
  expect(actual.forbiddenSecretMatches).toEqual([]); expect(actual.plaintextExternalArtifactCount).toBe(0);
});

test('BACKUP-full-media-reconstruction | AT-043 AC-043 | reconstruction includes unchanged objects absent from the latest transfer', async ({ app }) => {
  await setup(app, 'backup-shared-media-and-incremental-transfer');
  const before = await catalog(app), previous = verified(before, 'external'); expect(previous).toHaveLength(7);
  const job = await run(app); await finish(app, job, 'succeeded');
  const source = await app.observe('backup-epoch-source-inventory', { pointId: job.candidatePointId });
  expect(source.source).toBe('captured-source-epoch'); expect(source.media.length).toBeGreaterThan(1);
  source.media.forEach(entry => { id(entry.objectId); hash(entry.sha256); integer(entry.bytes); });
  const actual = await app.observe('backup-media-reconstruction', { pointId: job.candidatePointId });
  expect(actual.pointId).toBe(job.candidatePointId); expect(actual.source).toBe('reconstructed-storage-bytes');
  expect(mediaObjects(actual.objects)).toEqual(mediaObjects(source.media));
  const fixture = await app.observe('backup-fixture-identifiers'); id(fixture.unchangedSharedObjectId);
  expect(actual.objects.map(item => item.objectId)).toContain(fixture.unchangedSharedObjectId);
  const transfer = await app.observe('backup-transfer-inventory', { jobId: job.jobId });
  expect(Array.isArray(transfer.transferredObjectIds)).toBe(true);
  expect(transfer.transferredObjectIds).not.toContain(fixture.unchangedSharedObjectId);
});

test('BACKUP-retained-object | AT-043 AC-043 | rotation retains a shared object still referenced by another retained point', async ({ app }) => {
  await setup(app, 'backup-shared-media-and-incremental-transfer');
  const fixture = await app.observe('backup-fixture-identifiers'); id(fixture.unchangedSharedObjectId); id(fixture.retainedReferencingPointId);
  const original = await app.observe('backup-object-storage-state', { objectId: fixture.unchangedSharedObjectId });
  expect(original.exists).toBe(true); hash(original.sha256); expect(original.referencedByPointIds).toContain(fixture.retainedReferencingPointId);
  const job = await run(app); await finish(app, job, 'succeeded');
  expect(ids(verified(await catalog(app), 'external'))).toContain(fixture.retainedReferencingPointId);
  const after = await app.observe('backup-object-storage-state', { objectId: fixture.unchangedSharedObjectId });
  expect(after.exists).toBe(true); expect(after.sha256).toBe(original.sha256);
  expect(after.referencedByPointIds).toContain(fixture.retainedReferencingPointId);
});

test('BACKUP-no-volatile-artifacts | AT-043 AC-043 | complete inspected bundle excludes fixture cache/temp and unprotected secrets', async ({ app }) => {
  await setup(app); const job = await run(app); await finish(app, job, 'succeeded');
  const selected = verified(await catalog(app), 'external').find(item => item.id === job.candidatePointId); expect(selected).toBeTruthy();
  const actual = await app.observe('backup-decrypted-bundle-inventory', { pointId: selected.id });
  expect(actual.pointId).toBe(selected.id); expect(actual.source).toBe('decrypted-artifact-bytes');
  expect(hash(actual.archiveSha256)).toBe(selected.archiveSha256);
  expect(actual.dumpPresent).toBe(true); expect(actual.fullMediaManifestPresent).toBe(true);
  expect(actual.applicationSchemaMetadataPresent).toBe(true);
  expect(Array.isArray(actual.checkedCanaryReferences)).toBe(true); expect(actual.checkedCanaryReferences.length).toBeGreaterThan(0);
  expect(actual.excludedCacheCanaryFound).toBe(false); expect(actual.excludedTemporaryCanaryFound).toBe(false);
  expect(actual.rawEncryptionKeyFound).toBe(false); expect(actual.rawStorageTokenFound).toBe(false);
});

for (const stage of ['dump', 'encrypt', 'upload', 'verify', 'manifest']) {
  test(`BACKUP-stage-failed-${stage} | AT-043 AC-043 | failure of the new point does not evict verified points`, async ({ app }) => {
    await setup(app); const before = await retentionSnapshot(app); expect(verified(before, 'external')).toHaveLength(7); expect(verified(before, 'local')).toHaveLength(2);
    await control(app, 'fail-isolated-backup-stage', { stage }); const job = await run(app);
    const result = await finish(app, job, 'failed'); expect(result.failedStage).toBe(stage);
    await retained(app, before, job); await failureEvidence(app, job);
  });
}

for (const storage of ['local', 'external']) {
  test(`BACKUP-storage-unavailable-${storage} | AT-043 AC-043 | inaccessible storage cannot be reported as a verified new point`, async ({ app }) => {
    await setup(app); const before = await retentionSnapshot(app); expect(verified(before, 'external')).toHaveLength(7);
    await control(app, 'block-isolated-backup-storage', { storage }); const job = await run(app); await finish(app, job, 'failed');
    const after = await retained(app, before, job);
    expect(verified(after, storage).some(item => item.id === job.candidatePointId)).toBe(false);
    await failureEvidence(app, job);
  });
}

test('BACKUP-last-good | AT-043 AC-043 | one surviving verified point is retained when its replacement fails', async ({ app }) => {
  await setup(app, 'backup-only-one-verified-point'); const before = await retentionSnapshot(app);
  expect(verified(before, 'external')).toHaveLength(1); expect(verified(before, 'local')).toHaveLength(1);
  await control(app, 'fail-isolated-backup-stage', { stage: 'verify' }); const job = await run(app); await finish(app, job, 'failed');
  await retained(app, before, job); await failureEvidence(app, job);
});

for (const mutation of ['corrupt', 'remove']) {
  test(`BACKUP-invalid-candidate-${mutation} | AT-043 AC-043 | corrupt or missing candidate media cannot pass full verification`, async ({ app }) => {
    await setup(app, 'backup-shared-media-and-incremental-transfer'); const before = await retentionSnapshot(app);
    const job = await run(app, { holdAt: 'before-verify' });
    await expect.poll(async () => (await app.observe('backup-job-state', { jobId: job.jobId })).state).toBe('held-before-verify');
    const candidate = await app.observe('backup-candidate-object', { pointId: job.candidatePointId }); id(candidate.objectId);
    expect(candidate.pointId).toBe(job.candidatePointId); expect(candidate.referencedByPointIds).toEqual([job.candidatePointId]);
    expect(candidate.exists).toBe(true); expect(candidate.exclusiveToCandidate).toBe(true); hash(candidate.sha256);
    await control(app, mutation === 'corrupt' ? 'corrupt-isolated-backup-object' : 'remove-isolated-backup-manifest-object', { pointId: job.candidatePointId, objectId: candidate.objectId });
    const mutated = await app.observe('backup-object-storage-state', { objectId: candidate.objectId });
    if (mutation === 'remove') expect(mutated.exists).toBe(false);
    else { expect(mutated.exists).toBe(true); hash(mutated.sha256); expect(mutated.sha256).not.toBe(candidate.sha256); }
    await control(app, 'release-isolated-backup-barrier', { jobId: job.jobId });
    expect((await finish(app, job, 'failed')).failedStage).toBe('verify');
    await retained(app, before, job); await failureEvidence(app, job);
  });
}

for (const actor of ['S-EDIT', 'VISITOR']) {
  test(`BACKUP-list-owner-only-${actor} | AT-043 AT-044 AC-043 AC-044 | actual backup list is owner-only`, async ({ app }) => {
    await setup(app); const selected = verified(await catalog(app), 'external')[0];
    const allowed = await app.act('OWNER', 'view-backup-points-direct'); expect(allowed.outcome).toBe('accepted');
    expect(allowed.body).toContain(selected.archiveSha256);
    const denied = await app.act(actor, 'view-backup-points-direct'); expect(denied.outcome).toBe('denied');
    expect(denied.body).not.toContain(selected.archiveSha256);
  });
}

test('BACKUP-restore-preparation | AT-044 AC-044 | preparing a verified target shows cutoff and loss classes without starting restore', async ({ app }) => {
  await setup(app); const selected = verified(await catalog(app), 'external')[0];
  const before = await app.observe('backup-restore-execution-state'); integer(before.startedJobs); id(before.databaseGeneration); id(before.mediaGeneration);
  const result = await app.act('OWNER', 'prepare-backup-restore', { pointId: selected.id });
  expect(result.outcome).toBe('accepted'); expect(result.confirmation).toBeTruthy();
  expect(result.displayed.pointId).toBe(selected.id); expect(result.displayed.cutoffAt).toBe(selected.cutoffAt);
  expect(result.displayed.requiresOwnerPassword).toBe(true);
  for (const kind of ['requests_consents', 'users_rights', 'versions', 'logs', 'read_cursors', 'throttle']) expect(result.displayed.lossClasses).toContain(kind);
  expect(await app.observe('backup-restore-execution-state')).toEqual(before);
});

for (const incompatibility of ['application', 'schema']) {
  test(`BACKUP-incompatible-${incompatibility} | AT-044 AC-044 | incompatible target is refused by the same working preflight`, async ({ app }) => {
    await setup(app, 'backup-restore-preflight-matrix');
    const fixture = await app.observe('backup-fixture-identifiers'); id(fixture.compatiblePointId); id(fixture[`${incompatibility}IncompatiblePointId`]);
    expect(fixture[`${incompatibility}IncompatiblePointId`]).not.toBe(fixture.compatiblePointId);
    const before = await app.observe('backup-restore-execution-state'); integer(before.startedJobs); id(before.databaseGeneration); id(before.mediaGeneration);
    expect((await app.act('OWNER', 'prepare-backup-restore', { pointId: fixture.compatiblePointId })).outcome).toBe('accepted');
    const result = await app.act('OWNER', 'prepare-backup-restore', { pointId: fixture[`${incompatibility}IncompatiblePointId`] });
    expect(result.outcome).toBe('denied'); expect(result.safeReasons).toContain(`${incompatibility}-incompatible`);
    expect(await app.observe('backup-restore-execution-state')).toEqual(before);
  });
}

test('BACKUP-unverified-restore-target | AT-044 AC-044 | an unverified candidate cannot become a restore target', async ({ app }) => {
  await setup(app, 'backup-restore-preflight-matrix'); const fixture = await app.observe('backup-fixture-identifiers');
  id(fixture.compatiblePointId); id(fixture.unverifiedPointId); expect(fixture.unverifiedPointId).not.toBe(fixture.compatiblePointId);
  const candidate = (await catalog(app)).points.find(item => item.id === fixture.unverifiedPointId); expect(candidate).toBeTruthy(); expect(candidate.verified).toBe(false);
  const before = await app.observe('backup-restore-execution-state'); integer(before.startedJobs); id(before.databaseGeneration); id(before.mediaGeneration);
  expect((await app.act('OWNER', 'prepare-backup-restore', { pointId: fixture.compatiblePointId })).outcome).toBe('accepted');
  expect((await app.act('OWNER', 'prepare-backup-restore', { pointId: fixture.unverifiedPointId })).outcome).toBe('denied');
  expect(await app.observe('backup-restore-execution-state')).toEqual(before);
});
