import { randomUUID } from 'node:crypto';
import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await use(app); } finally { await app.close(); }
} });
test.setTimeout(240_000); // Test-tool budget, not an operational completion SLA.
const CAP = 1_073_741_824;
const id = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
const integer = value => { expect(Number.isSafeInteger(value) && value >= 0).toBe(true); return value; };
const hash = value => { expect(value).toMatch(/^[a-f0-9]{64}$/); return value; };
const kinds = ['active', 'closed', 'compressed', 'manifest', 'temporary'];
function occupancyBand(bytes, percent) {
  const measuredPercent = integer(bytes) / CAP * 100;
  expect(measuredPercent).toBeGreaterThanOrEqual(percent - 0.25);
  expect(measuredPercent).toBeLessThanOrEqual(percent + 0.25);
}

async function setup(app, profile, options = {}) {
  const admission = await app.inspectInfrastructureAdmission();
  expect(admission.arc10Verified).toBe(true); expect(admission.isolatedInfrastructure).toBe(true);
  id(admission.reviewedEvidenceId); expect(admission.capabilities).toContain('log-maintenance-control-v1');
  await app.reset(profile, options);
}
async function control(app, action, args = {}) {
  const result = await app.control(action, args); expect(result.outcome).toBe('accepted'); return result;
}
async function run(app, task, args = {}) {
  const result = await control(app, 'run-isolated-log-maintenance', { task, operationId: randomUUID(), ...args });
  id(result.jobId);
  await expect.poll(async () => (await app.observe('log-maintenance-job', { jobId: result.jobId })).state,
    { timeout: 60_000 }).toMatch(/^(completed|failed)$/);
  const job = await app.observe('log-maintenance-job', { jobId: result.jobId });
  expect(job.jobId).toBe(result.jobId); return job;
}
function files(entries) {
  expect(Array.isArray(entries)).toBe(true); expect(entries.length).toBeGreaterThan(0);
  expect(new Set(entries.map(entry => entry.objectId)).size).toBe(entries.length);
  for (const entry of entries) {
    id(entry.objectId); expect(kinds).toContain(entry.kind); integer(entry.bytes); hash(entry.sha256);
    expect(entry.relativePath).toMatch(/^[a-zA-Z0-9_./-]+$/); expect(entry.relativePath.split('/')).not.toContain('..');
    expect(entry.relativePath.startsWith('/')).toBe(false);
  }
  return entries.reduce((total, entry) => total + entry.bytes, 0);
}
function finalCheckpoint(evidence) {
  const closing = evidence.checkpoints.filter(point => point.phase === 'causal-quiescence-end');
  expect(closing).toHaveLength(1);
  expect(closing[0].sequence).toBe(evidence.captureEndSequence);
  return closing[0];
}
async function physical(app, jobId) {
  const args = { jobId, captureThrough: 'causal-quiescence' };
  await expect.poll(async () => {
    const value = await app.observe('log-volume-physical-evidence', args);
    return [value.captureClosed, value.terminalObserved, value.pendingDescendantWork];
  }, { timeout: 30_000 }).toEqual([true, true, 0]);
  const value = await app.observe('log-volume-physical-evidence', args);
  expect(value.source).toBe('actual-isolated-volume-io-trace'); expect(value.jobId).toBe(jobId);
  id(value.measurementId); hash(value.traceSha256); expect(value.capBytes).toBe(CAP);
  expect(value.captureScope).toBe('all-writers-and-temporary-files');
  expect(value.coverage).toBe('before-dispatch-through-causal-quiescence');
  expect(value.captureClosed).toBe(true); expect(value.terminalObserved).toBe(true); expect(integer(value.pendingDescendantWork)).toBe(0);
  id(value.captureId); integer(value.captureStartSequence); integer(value.terminalSequence); integer(value.captureEndSequence);
  expect(value.terminalSequence).toBeGreaterThan(value.captureStartSequence); expect(value.captureEndSequence).toBeGreaterThanOrEqual(value.terminalSequence);
  expect(Array.isArray(value.allocationEvents)).toBe(true); expect(value.allocationEvents.length).toBeGreaterThan(0);
  let previous = -1;
  for (const event of value.allocationEvents) {
    expect(integer(event.sequence)).toBeGreaterThan(previous); previous = event.sequence;
    expect(event.sequence).toBeGreaterThanOrEqual(value.captureStartSequence); expect(event.sequence).toBeLessThanOrEqual(value.captureEndSequence);
    expect(integer(event.totalFileBytes)).toBeLessThanOrEqual(CAP);
  }
  expect(value.highWaterBytes).toBe(Math.max(...value.allocationEvents.map(event => event.totalFileBytes)));
  expect(integer(value.highWaterBytes)).toBeLessThanOrEqual(CAP);
  expect(Array.isArray(value.checkpoints)).toBe(true); expect(value.checkpoints.length).toBeGreaterThan(0);
  for (const point of value.checkpoints) {
    id(point.phase); integer(point.sequence);
    const total = files(point.files); expect(point.totalFileBytes).toBe(total); expect(total).toBeLessThanOrEqual(value.highWaterBytes);
    expect(value.allocationEvents.some(event => event.sequence === point.sequence && event.totalFileBytes === total)).toBe(true);
  }
  const closing = finalCheckpoint(value);
  const finalMeasurement = value.allocationEvents.at(-1);
  expect(finalMeasurement.operation).toBe('final-measurement');
  expect(finalMeasurement.sequence).toBe(value.captureEndSequence);
  expect(finalMeasurement.totalFileBytes).toBe(closing.totalFileBytes);
  return value;
}
function overlappingWriters(evidence, jobId, rotation) {
  expect(Array.isArray(evidence.writerAttempts)).toBe(true);
  const attempts = evidence.writerAttempts;
  expect(attempts.length).toBeGreaterThanOrEqual(2);
  expect(new Set(attempts.map(attempt => attempt.attemptId)).size).toBe(attempts.length);
  for (const attempt of attempts) {
    id(attempt.attemptId); id(attempt.writerId); expect(attempt.originJobId).toBe(jobId);
    expect(integer(attempt.finishedSequence)).toBeGreaterThan(integer(attempt.startedSequence));
    expect(Array.isArray(attempt.writeSequences)).toBe(true); expect(attempt.writeSequences.length).toBeGreaterThan(0);
    for (const sequence of attempt.writeSequences) {
      expect(integer(sequence)).toBeGreaterThan(attempt.startedSequence); expect(sequence).toBeLessThan(attempt.finishedSequence);
      expect(evidence.allocationEvents.some(event => event.sequence === sequence && event.writerId === attempt.writerId &&
        event.originJobId === jobId && event.operation === 'write')).toBe(true);
    }
  }
  const overlapAtTemporaryCheckpoint = rotation.some(point => attempts.some((a, index) => attempts.slice(index + 1).some(b =>
    a.writerId !== b.writerId && Math.max(a.startedSequence, b.startedSequence) <= point.sequence &&
    point.sequence < Math.min(a.finishedSequence, b.finishedSequence))));
  expect(overlapAtTemporaryCheckpoint, 'two actual writer attempts overlap the same real temporary-rotation checkpoint').toBe(true);
}
async function quiescentFailure(app, jobId) {
  await expect.poll(async () => {
    const value = await app.observe('log-rotation-failure-evidence', { jobId });
    return [value.captureClosed, value.pendingPipelineEvents, value.pendingDeliveries, value.pendingDelayedWork];
  }, { timeout: 30_000 }).toEqual([true, 0, 0, 0]);
  const value = await app.observe('log-rotation-failure-evidence', { jobId });
  for (const field of ['pendingPipelineEvents', 'pendingDeliveries', 'pendingDelayedWork']) expect(integer(value[field])).toBe(0);
  expect(value.captureClosed).toBe(true); id(value.captureId); integer(value.captureStartSequence); integer(value.captureEndSequence);
  expect(value.graphCoverage).toBe('before-dispatch-through-causal-quiescence');
  expect(value.graphCaptureComplete).toBe(true);
  return value;
}
async function notifications(app) {
  await expect.poll(async () => (await app.observe('log-quota-notification-sink')).pendingQuotaMessageCount,
    { timeout: 10_000 }).toBe(0);
  const result = await app.observe('log-quota-notification-sink');
  expect(result.source).toBe('actual-local-delivery-sink'); expect(Array.isArray(result.messages)).toBe(true);
  for (const item of result.messages) { id(item.messageId); id(item.cycleId); expect(['warning80', 'critical95', 'recovery75']).toContain(item.kind); }
  return result.messages;
}
async function usefulRead(app) {
  const response = await app.act('VISITOR', 'read-log-quota-public-probe-direct');
  expect(response.outcome).toBe('accepted'); expect(response.status).toBe(200);
  expect(response.body).toContain('LOG-QUOTA-PUBLIC-CANARY');
}

for (const [percent, expectedKind] of [[79, null], [81, 'warning80'], [96, 'critical95']]) {
  test(`LOG-QUOTA-threshold-${percent} | AT-040 AT-308 AC-040 AC-OPS-008 | actual occupancy crosses only the applicable quota threshold`, async ({ app }) => {
    await setup(app, 'log-quota-threshold', { percent });
    const before = await app.observe('log-volume-inventory');
    const initialBytes = files(before.files);
    occupancyBand(initialBytes, percent);
    expect(await notifications(app)).toHaveLength(0);
    const job = await run(app, 'evaluate-quota'); expect(job.state).toBe('completed');
    await physical(app, job.jobId);
    const messages = await notifications(app);
    if (expectedKind === null) expect(messages).toHaveLength(0);
    else {
      expect(messages.filter(item => item.kind === expectedKind)).toHaveLength(1);
      await run(app, 'evaluate-quota');
      expect((await notifications(app)).filter(item => item.kind === expectedKind)).toHaveLength(1);
    }
    if (percent === 96) {
      const suppression = await app.observe('log-noise-suppression-evidence', { jobId: job.jobId });
      expect(suppression.source).toBe('actual-writer-and-file-inspection'); expect(suppression.jobId).toBe(job.jobId);
      expect(integer(suppression.attemptedKnownNoiseCount)).toBeGreaterThan(0);
      expect(suppression.detailBytesAddedWhileAtOrAbove95).toBe(0);
      expect(integer(suppression.aggregateCountAdded)).toBeGreaterThan(0);
      expect(suppression.incompletenessShown).toBe(true);
    }
    await usefulRead(app);
  });
}

for (const percent of [76, 74]) {
  test(`LOG-QUOTA-recovery-${percent} | AT-308 AC-OPS-008 | recovery is emitted only below seventy-five percent and once per existing cycle`, async ({ app }) => {
    await setup(app, 'log-quota-existing-cycle', { percent });
    occupancyBand(files((await app.observe('log-volume-inventory')).files), percent);
    const before = await notifications(app); expect(before.some(item => item.kind === 'critical95')).toBe(true);
    expect(before.filter(item => item.kind === 'recovery75')).toHaveLength(0);
    const job = await run(app, 'evaluate-quota'); expect(job.state).toBe('completed'); await physical(app, job.jobId);
    const after = await notifications(app);
    const recovery = after.filter(item => item.kind === 'recovery75');
    expect(recovery).toHaveLength(percent < 75 ? 1 : 0);
    if (recovery.length) expect(before.some(item => item.cycleId === recovery[0].cycleId)).toBe(true);
    await run(app, 'evaluate-quota');
    expect((await notifications(app)).filter(item => item.kind === 'recovery75')).toHaveLength(recovery.length);
  });
}

test('LOG-QUOTA-age-and-noise | AT-040 AC-040 | early low-priority file cleanup never erases younger structured important audit', async ({ app }) => {
  await setup(app, 'log-age-and-pressure');
  const before = await app.observe('log-age-pressure-evidence');
  expect(before.source).toBe('actual-db-and-file-bytes'); id(before.youngImportantEventId); id(before.oldOrdinaryEventId); id(before.oldNoiseObjectId);
  expect(before.importantEventAgeSeconds).toBe(29 * 86400); expect(before.oldOrdinaryEventAgeSeconds).toBe(31 * 86400);
  expect(before.oldNoiseAgeSeconds).toBeLessThan(30 * 86400);
  expect(before.importantEventExists).toBe(true); expect(before.oldOrdinaryEventExists).toBe(true); expect(before.oldNoiseExists).toBe(true);
  hash(before.importantEventDigest);
  const job = await run(app, 'age-and-pressure-cleanup'); expect(job.state).toBe('completed'); await physical(app, job.jobId);
  const after = await app.observe('log-age-pressure-evidence');
  expect(after.youngImportantEventId).toBe(before.youngImportantEventId); expect(after.importantEventExists).toBe(true);
  expect(after.importantEventDigest).toBe(before.importantEventDigest);
  expect(after.oldOrdinaryEventId).toBe(before.oldOrdinaryEventId); expect(after.oldOrdinaryEventExists).toBe(false);
  expect(after.oldNoiseObjectId).toBe(before.oldNoiseObjectId); expect(after.oldNoiseExists).toBe(false);
  await usefulRead(app);
});

test('LOG-QUOTA-rotation-peak | AT-040 AT-308 AC-040 AC-OPS-008 | concurrent rotation counts active, compressed, manifest and real temporary bytes within one cap', async ({ app }) => {
  await setup(app, 'log-quota-concurrent-rotation');
  const outside = await app.observe('log-outside-scope-integrity');
  expect(outside.projectionSource).toBe('actual-protected-business-rows-and-outside-file-bytes');
  for (const field of ['protectedBusinessDataDigest', 'mediaDigest', 'backupDigest', 'htmlDigest', 'providerLogDigest']) hash(outside[field]);
  for (const field of ['pageIds', 'requestIds', 'rightsRefs']) {
    expect(Array.isArray(outside.protectedObjectRefs[field])).toBe(true); expect(outside.protectedObjectRefs[field].length).toBeGreaterThan(0);
    outside.protectedObjectRefs[field].forEach(id);
    expect(new Set(outside.protectedObjectRefs[field]).size).toBe(outside.protectedObjectRefs[field].length);
  }
  const job = await run(app, 'rotate-with-concurrent-writers'); expect(job.state).toBe('completed');
  const evidence = await physical(app, job.jobId);
  const rotation = evidence.checkpoints.filter(point => point.phase === 'temporary-rotation'); expect(rotation.length).toBeGreaterThan(0);
  overlappingWriters(evidence, job.jobId, rotation);
  for (const kind of ['active', 'compressed', 'manifest', 'temporary']) expect(rotation.some(point => point.files.some(file => file.kind === kind && file.bytes > 0))).toBe(true);
  expect(evidence.highWaterBytes).toBeGreaterThanOrEqual(Math.floor(CAP * 0.95));
  expect(await app.observe('log-outside-scope-integrity')).toEqual(outside);
  await usefulRead(app);
});

for (const fault of ['no-space', 'rotation-rename-failure']) {
  test(`LOG-QUOTA-fault-${fault} | AT-308 AC-OPS-008 | rotation failure leaves real occupancy and incomplete diagnostics without an error feedback chain`, async ({ app }) => {
    await setup(app, 'log-quota-fault');
    const initial = await app.observe('log-volume-inventory'); expect(files(initial.files)).toBeGreaterThan(0);
    await usefulRead(app);
    try {
      await control(app, 'set-log-storage-fault', { fault });
      const job = await run(app, 'rotate-with-known-noise'); expect(job.state).toBe('failed');
      const diagnostic = await quiescentFailure(app, job.jobId);
      const evidence = await physical(app, job.jobId);
      const final = finalCheckpoint(evidence); expect(final.totalFileBytes).toBeGreaterThan(0);
      for (const key of ['captureId', 'captureStartSequence', 'captureEndSequence']) expect(diagnostic[key]).toBe(evidence[key]);
      expect(diagnostic.jobId).toBe(job.jobId); expect(diagnostic.source).toBe('actual-independent-status-and-sink');
      expect(diagnostic.reportedPhysicalBytes).toBe(final.totalFileBytes);
      expect(diagnostic.incomplete).toBe(true); expect(diagnostic.reportedSuccess).toBe(false);
      expect(Array.isArray(diagnostic.deliveryCauses)).toBe(true);
      expect(diagnostic.deliveryCauses.length).toBeGreaterThan(0);
      for (const cause of diagnostic.deliveryCauses) {
        expect(cause.originJobId).toBe(job.jobId); expect(cause.causedByTransportFailure).toBe(false);
      }
      expect(Array.isArray(diagnostic.pipelineEvents)).toBe(true);
      expect(diagnostic.pipelineEvents.some(event => event.kind === 'rotation-failure')).toBe(true);
      expect(new Set(diagnostic.pipelineEvents.map(event => event.eventId)).size).toBe(diagnostic.pipelineEvents.length);
      for (const event of diagnostic.pipelineEvents) {
        id(event.eventId); expect(['rotation-failure', 'logging-failure', 'transport-failure']).toContain(event.kind);
        expect(integer(event.sequence)).toBeGreaterThanOrEqual(diagnostic.captureStartSequence);
        expect(event.sequence).toBeLessThanOrEqual(diagnostic.captureEndSequence);
        if (event.kind !== 'rotation-failure') expect(diagnostic.pipelineEvents.filter(child => child.parentEventId === event.eventId)).toHaveLength(0);
      }
      await usefulRead(app);
    } finally { await control(app, 'clear-log-storage-fault', { fault }); }
    const retry = await run(app, 'rotate-with-known-noise'); expect(retry.state).toBe('completed'); await physical(app, retry.jobId);
    await usefulRead(app);
  });
}
