import { createHash } from 'node:crypto';
import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver(); try { await use(app); } finally { await app.close(); }
} });
const id = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
async function command(app, action, args) {
  const result = await app.control(action, args); expect(result.outcome).toBe('accepted'); return result;
}
async function setup(app, jobKind) {
  const admission = await app.inspectInfrastructureAdmission();
  expect(admission.arc10Verified).toBe(true); expect(admission.isolatedInfrastructure).toBe(true);
  id(admission.reviewedEvidenceId); expect(admission.capabilities).toContain('background-job-control-v1');
  await app.reset('background-job-own-workers', { jobKind });
  const fixture = await app.observe('background-job-identifiers');
  for (const key of ['logicalTaskId', 'nextLogicalTaskId', 'nextEligibleSlotUtc', 'sourceEpochId']) id(fixture[key]);
  expect(fixture.logicalTaskId).not.toBe(fixture.nextLogicalTaskId);
  return fixture;
}
async function output(app, jobKind) {
  const actual = await app.observe('background-published-output', { jobKind, readMode: 'out-of-band-own-test-volumes' });
  expect(actual.jobKind).toBe(jobKind); expect(actual.source).toBe('actual-head-and-storage-bytes');
  id(actual.headId); id(actual.sourceEpochId); expect(actual.verified).toBe(true);
  expect(Array.isArray(actual.artifacts)).toBe(true); expect(actual.artifacts.length).toBeGreaterThan(0);
  const files = actual.artifacts.map(file => {
    id(file.id); id(file.role); expect(Number.isSafeInteger(file.size) && file.size > 0 && file.size <= 256 * 1024).toBe(true);
    const bytes = Buffer.from(file.bytesBase64, 'base64'); expect(bytes.length).toBe(file.size);
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(file.sha256);
    return { id: file.id, role: file.role, size: file.size, sha256: file.sha256, bytesBase64: file.bytesBase64 };
  }).sort((a, b) => a.id.localeCompare(b.id));
  expect(new Set(files.map(file => file.id)).size).toBe(files.length);
  const manifests = files.filter(file => file.role === 'manifest');
  expect(manifests).toHaveLength(1);
  expect(actual.headManifestSha256).toBe(manifests[0].sha256);
  expect(files.some(file => file.role === (jobKind === 'backup' ? 'ciphertext' : 'html'))).toBe(true);
  return { headId: actual.headId, sourceEpochId: actual.sourceEpochId, headManifestSha256: actual.headManifestSha256, artifacts: files };
}
async function state(app, jobKind, logicalTaskId) {
  const actual = await app.observe('background-logical-task-state', { jobKind, logicalTaskId });
  expect(actual.jobKind).toBe(jobKind); expect(actual.logicalTaskId).toBe(logicalTaskId);
  expect(Array.isArray(actual.invocations)).toBe(true); expect(actual.invocations.length).toBeGreaterThan(0);
  expect(new Set(actual.invocations.map(item => id(item.id))).size).toBe(actual.invocations.length);
  expect(Array.isArray(actual.committedEffects)).toBe(true);
  expect(Number.isSafeInteger(actual.peakConcurrentCommitSections) && actual.peakConcurrentCommitSections >= 0).toBe(true);
  return actual;
}
async function waitPhase(app, invocationId, phase) {
  await expect.poll(async () => (await app.observe('background-worker-phase', { invocationId })).phase, { timeout: 10_000 }).toBe(phase);
  const actual = await app.observe('background-worker-phase', { invocationId });
  expect(actual.invocationId).toBe(invocationId); id(actual.workerInstanceId);
  expect(actual.actualWorkerObserved).toBe(true); return actual;
}
async function successful(app, jobKind, logicalTaskId, fixture, before) {
  await expect.poll(async () => (await state(app, jobKind, logicalTaskId)).committedEffects.length, { timeout: 10_000 }).toBe(1);
  const actual = await state(app, jobKind, logicalTaskId);
  expect(actual.committedEffects).toHaveLength(1); expect(actual.peakConcurrentCommitSections).toBe(1);
  const effect = actual.committedEffects[0]; id(effect.id); expect(effect.sourceEpochId).toBe(fixture.sourceEpochId);
  const published = await output(app, jobKind);
  expect(published.headId).toBe(effect.outputHeadId); expect(published.headId).not.toBe(before.headId);
  expect(published.sourceEpochId).toBe(fixture.sourceEpochId);
  const manifest = await app.observe('background-output-manifest', { jobKind, headId: published.headId });
  expect(manifest.headId).toBe(published.headId); expect(manifest.sourceEpochId).toBe(fixture.sourceEpochId);
  expect(manifest.observedFileSha256).toBe(published.headManifestSha256);
  expect(manifest.artifactHashes).toEqual(published.artifacts.filter(file => file.role !== 'manifest')
    .map(file => ({ id: file.id, sha256: file.sha256 })).sort((a, b) => a.id.localeCompare(b.id)));
}

for (const jobKind of ['backup', 'html-build']) {
  test(`JOB-060-duplicate-${jobKind} | AT-060 AC-060 | duplicate logical invocation cannot commit twice or overlap its commit section`, async ({ app }) => {
    const fixture = await setup(app, jobKind); const before = await output(app, jobKind);
    await command(app, 'hold-isolated-job-phase', { jobKind, logicalTaskId: fixture.logicalTaskId, phase: 'before-commit' });
    const first = await command(app, 'start-isolated-job-invocation', { jobKind, logicalTaskId: fixture.logicalTaskId });
    id(first.invocationId); await waitPhase(app, first.invocationId, 'before-commit');
    const duplicate = await command(app, 'start-isolated-job-invocation', { jobKind, logicalTaskId: fixture.logicalTaskId });
    id(duplicate.invocationId); expect(duplicate.invocationId).not.toBe(first.invocationId);
    expect(await output(app, jobKind)).toEqual(before);
    await command(app, 'release-isolated-job-barrier', { invocationId: first.invocationId });
    await expect.poll(async () => {
      const actual = await state(app, jobKind, fixture.logicalTaskId);
      const invocations = actual.invocations.filter(item => [first.invocationId, duplicate.invocationId].includes(item.id));
      return invocations.length === 2 && invocations.every(item => item.settled === true);
    }, { timeout: 10_000 }).toBe(true);
    const actual = await state(app, jobKind, fixture.logicalTaskId);
    expect(actual.invocations.map(item => item.id)).toEqual(expect.arrayContaining([first.invocationId, duplicate.invocationId]));
    await successful(app, jobKind, fixture.logicalTaskId, fixture, before);
  });

  for (const fault of ['write-denied', 'terminate-own-worker']) {
    test(`JOB-060-fault-${jobKind}-${fault} | AT-060 AC-060 | a precommit failure preserves actual previous good bytes and never claims success`, async ({ app }) => {
      const fixture = await setup(app, jobKind); const before = await output(app, jobKind);
      const sourceBefore = await app.observe('background-source-state');
      expect(sourceBefore.sourceEpochId).toBe(fixture.sourceEpochId);
      expect(Array.isArray(sourceBefore.pages) && sourceBefore.pages.length > 0).toBe(true);
      expect(sourceBefore.sourceEpochId).not.toBe(before.sourceEpochId);
      await command(app, 'hold-isolated-job-phase', { jobKind, logicalTaskId: fixture.logicalTaskId, phase: 'before-commit' });
      const started = await command(app, 'start-isolated-job-invocation', { jobKind, logicalTaskId: fixture.logicalTaskId });
      id(started.invocationId); await waitPhase(app, started.invocationId, 'before-commit');
      await command(app, 'fail-isolated-job-phase', { invocationId: started.invocationId, phase: 'before-commit', fault });
      await command(app, 'release-isolated-job-barrier', { invocationId: started.invocationId });
      await expect.poll(async () => (await app.observe('background-worker-phase', { invocationId: started.invocationId })).executionStopped, { timeout: 10_000 }).toBe(true);
      const stopped = await app.observe('background-worker-phase', { invocationId: started.invocationId });
      expect(stopped.invocationId).toBe(started.invocationId); expect(stopped.reportedSuccess).toBe(false);
      expect(stopped.failureObserved).toBe(true);
      expect((await state(app, jobKind, fixture.logicalTaskId)).committedEffects).toEqual([]);
      expect(await output(app, jobKind)).toEqual(before);
      expect(await app.observe('background-source-state')).toEqual(sourceBefore);
      const publicRead = await app.act('VISITOR', 'read-job-health-page-direct');
      expect(publicRead.outcome).toBe('accepted'); expect(publicRead.status).toBe(200);
      expect(publicRead.body).toContain('JOB-HEALTH-CANARY');
      // A new eligible slot is explicit test control, not automatic restore/retry of an ambiguous commit.
      await command(app, 'clear-isolated-job-fault', { invocationId: started.invocationId });
      await command(app, 'advance-background-test-time', { toUtc: fixture.nextEligibleSlotUtc });
      const next = await command(app, 'start-isolated-job-invocation', { jobKind, logicalTaskId: fixture.nextLogicalTaskId });
      id(next.invocationId); expect(next.invocationId).not.toBe(started.invocationId);
      await successful(app, jobKind, fixture.nextLogicalTaskId, fixture, before);
    });
  }
}
