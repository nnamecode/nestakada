import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver(); try { await use(app); } finally { await app.close(); }
} });
test.describe.configure({ timeout: 120_000 }); // Test budget, not a cleanup/recovery SLA.
const RECEIPT_BYTES = 16 * 1024 * 1024, RECEIPT_COUNT = 20_000;
const required = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
const integer = value => { expect(Number.isSafeInteger(value) && value >= 0).toBe(true); return value; };
const hash = value => { expect(value).toMatch(/^[a-f0-9]{64}$/); return value; };
const payload = () => ({ name: 'Синтетический посетитель', phone: '+70000000000', car: '', comment: 'SERVICE-QUOTA-OWN-INPUT', consent: true });
async function control(app, action, args = {}) { const result = await app.control(action, args); expect(result.outcome).toBe('accepted'); return result; }
async function occupancy(app, resource) {
  const value = await app.observe('service-quota-state', { resource }); expect(value.resource).toBe(resource);
  required(value.configEvidenceId);
  for (const field of ['capacityBytes', 'usedBytes', 'reservedBytes', 'overheadBytes', 'activeEntries', 'maxEntries', 'nextWriteReservationBytes']) integer(value[field]);
  expect(value.capacityBytes).toBeGreaterThan(0); expect(value.overheadBytes).toBeLessThanOrEqual(value.usedBytes);
  expect(value.usedBytes + value.reservedBytes).toBeLessThanOrEqual(value.capacityBytes);
  if (value.maxEntries) expect(value.activeEntries).toBeLessThanOrEqual(value.maxEntries);
  return value;
}
async function retained(app) {
  const value = await app.observe('service-retained-state');
  for (const field of ['requestsDigest', 'consentsDigest', 'usedMediaDigest', 'retainedSetManifestDigest', 'validReceiptDigest']) hash(value[field]);
  expect(value.goodSetIds).toHaveLength(1); required(value.goodSetIds[0]); expect(value.activeSetId).toBe(value.goodSetIds[0]);
  return value;
}
async function counts(app) {
  const value = await app.observe('form-counters');
  for (const field of ['requests', 'consents', 'acceptedGoals', 'telegramMessages']) integer(value[field]);
  return value;
}
async function receiptManifest(app, validAfter) {
  const value = await app.observe('service-receipt-manifest', { validAfter });
  integer(value.count); hash(value.digest); expect(value.count).toBeGreaterThan(0);
  return value;
}
async function pressure(app, resource) {
  const value = await app.observe('service-pressure-diagnostic', { resource }); integer(value.occurrences);
  if (value.occurrences) expect(value.code).toBe('RESOURCE_PRESSURE'); return value;
}
async function setup(app, resource) {
  const admission = await app.inspectInfrastructureAdmission();
  expect(admission.arc10Verified).toBe(true); expect(admission.isolatedInfrastructure).toBe(true); required(admission.reviewedEvidenceId);
  expect(admission.capabilities).toContain('service-quota-control-v1');
  if (resource === 'temporary-bytes') expect(admission.capabilities).toContain('html-build-control-v1');
  await app.reset('isolated-service-quota-full', { resource });
  const fixture = await app.observe('service-quota-fixture'); expect(fixture.resource).toBe(resource);
  required(fixture.oldContext); required(fixture.oldRequestId); required(fixture.oldReceiptExpiresAt);
  integer(fixture.cleanupAdvanceSeconds); expect(fixture.cleanupAdvanceSeconds).toBeGreaterThan(0);
  const state = await occupancy(app, resource);
  if (resource.startsWith('receipt-')) {
    expect(state.capacityBytes).toBe(RECEIPT_BYTES); expect(state.maxEntries).toBe(RECEIPT_COUNT);
    expect(fixture.oldSource).toBe('home');
    if (resource === 'receipt-count') expect(state.activeEntries).toBe(RECEIPT_COUNT);
    else {
      expect(state.activeEntries).toBeLessThan(RECEIPT_COUNT);
      expect(state.usedBytes + state.reservedBytes + state.nextWriteReservationBytes).toBeGreaterThan(RECEIPT_BYTES);
    }
  } else if (resource === 'throttle-keys') {
    expect(state.maxEntries).toBeGreaterThan(0); expect(state.activeEntries).toBe(state.maxEntries); required(fixture.newThrottleKeyRef);
  } else expect(state.usedBytes + state.reservedBytes + state.nextWriteReservationBytes).toBeGreaterThan(state.capacityBytes);
  // Do not replay before the test has captured the complete live cohort oracle.
  const link = await app.observe('form-intent-records', { source: 'home', context: fixture.oldContext });
  expect(link.requestIds).toEqual([fixture.oldRequestId]); expect(link.receiptCommitted).toBe(true);
  return { fixture, state };
}
async function cleanup(app, resource, fixture, expectedCutoff) {
  const beforeClock = await app.observe('service-test-clock');
  const expectedNow = Date.parse(beforeClock.now) + fixture.cleanupAdvanceSeconds * 1000;
  expect(Number.isFinite(expectedNow)).toBe(true);
  if (expectedCutoff) expect(expectedNow).toBe(Date.parse(expectedCutoff));
  await control(app, 'advance-service-test-time', { seconds: fixture.cleanupAdvanceSeconds });
  const clock = await app.observe('service-test-clock');
  expect(Number.isFinite(Date.parse(clock.now))).toBe(true);
  expect(Date.parse(clock.now)).toBe(expectedNow);
  expect(Date.parse(clock.now)).toBeLessThan(Date.parse(fixture.oldReceiptExpiresAt));
  const invoked = await control(app, 'run-isolated-service-cleanup', { resource }); required(invoked.jobId);
  await expect.poll(async () => (await app.observe('service-cleanup-job', { jobId: invoked.jobId })).state, { timeout: 20_000 }).toMatch(/^(completed|failed)$/);
  const job = await app.observe('service-cleanup-job', { jobId: invoked.jobId }); expect(job.state).toBe('completed');
  expect(job.jobId).toBe(invoked.jobId); expect(job.resource).toBe(resource);
  if (resource === 'temporary-bytes') expect(integer(job.deletedExpiredTemporaryBytes)).toBeGreaterThan(0);
  else expect(integer(job.deletedExpiredEntries)).toBeGreaterThan(0);
  await control(app, 'drain-isolated-service-workers', { jobId: invoked.jobId });
  return occupancy(app, resource);
}
async function oldReceipt(app, fixture) {
  const before = await counts(app);
  expect((await app.act('VISITOR', 'submit-form-direct', { source: 'home', context: fixture.oldContext, payload: payload() })).outcome).toBe('accepted');
  expect(await counts(app)).toEqual(before);
  expect((await app.observe('form-intent-records', { source: 'home', context: fixture.oldContext })).requestIds).toEqual([fixture.oldRequestId]);
}

for (const resource of ['receipt-count', 'receipt-bytes']) {
  test(`SERVICE-QUOTA-${resource} | AT-310 AC-OPS-010 | existing receipt survives full pool while new request is refused and expired-only cleanup restores capacity`, async ({ app }) => {
    const { fixture, state } = await setup(app, resource), protectedBefore = await retained(app), before = await counts(app), diagnostic = await pressure(app, resource);
    const clock = await app.observe('service-test-clock'); expect(Number.isFinite(Date.parse(clock.now))).toBe(true);
    const liveBefore = await receiptManifest(app, clock.now);
    expect(liveBefore.count).toBe(state.activeEntries);
    const opened = await app.act('VISITOR-NEW', 'open-form', { source: 'home' }); expect(opened.outcome).toBe('accepted'); required(opened.context);
    const result = await app.act('VISITOR-NEW', 'submit-form-direct', { source: 'home', context: opened.context, payload: payload() });
    expect(result.outcome).toBe('denied'); expect(await counts(app)).toEqual(before);
    const refused = await app.observe('form-intent-records', { source: 'home', context: opened.context });
    expect(refused.requestIds).toEqual([]); expect(refused.receiptCommitted).toBe(false);
    expect((await pressure(app, resource)).occurrences).toBeGreaterThan(diagnostic.occurrences);
    expect(await retained(app)).toEqual(protectedBefore); await oldReceipt(app, fixture);
    expect((await occupancy(app, resource)).activeEntries).toBe(state.activeEntries);
    expect(await receiptManifest(app, clock.now)).toEqual(liveBefore);
    const cutoff = new Date(Date.parse(clock.now) + fixture.cleanupAdvanceSeconds * 1000).toISOString();
    const survivors = await receiptManifest(app, cutoff);
    const recovered = await cleanup(app, resource, fixture, cutoff);
    expect(recovered.capacityBytes).toBe(state.capacityBytes); expect(recovered.maxEntries).toBe(state.maxEntries);
    expect(await retained(app)).toEqual(protectedBefore); await oldReceipt(app, fixture);
    expect(await receiptManifest(app, cutoff)).toEqual(survivors);
    // Explicit fresh GET after clock advance; no silent renewal/resubmission of the refused token.
    const fresh = await app.act('VISITOR-NEW', 'open-form', { source: 'home' }); expect(fresh.outcome).toBe('accepted'); required(fresh.context);
    const previous = await counts(app);
    expect((await app.act('VISITOR-NEW', 'submit-form-direct', { source: 'home', context: fresh.context, payload: payload() })).outcome).toBe('accepted');
    const after = await counts(app); expect(after.requests).toBe(previous.requests + 1); expect(after.consents).toBe(previous.consents + 1);
    expect(after.acceptedGoals - previous.acceptedGoals).toBeGreaterThanOrEqual(0); expect(after.acceptedGoals - previous.acceptedGoals).toBeLessThanOrEqual(1);
    expect(after.telegramMessages).toBe(previous.telegramMessages);
    const created = await app.observe('form-intent-records', { source: 'home', context: fresh.context });
    expect(created.receiptCommitted).toBe(true); expect(created.requestIds).toHaveLength(1); expect(created.requestIds[0]).not.toBe(fixture.oldRequestId);
    await occupancy(app, resource);
  });
}

test('SERVICE-QUOTA-throttle-keys | AT-310 AC-OPS-010 | new key cannot grow a full throttle map or authorize login, cleanup removes expired keys only', async ({ app }) => {
  const resource = 'throttle-keys', { fixture, state } = await setup(app, resource), protectedBefore = await retained(app), diagnostic = await pressure(app, resource);
  const key = () => app.observe('service-throttle-key', { keyRef: fixture.newThrottleKeyRef });
  expect((await key()).exists).toBe(false);
  expect((await app.act('VISITOR-NEW', 'attempt-new-throttle-key', { keyRef: fixture.newThrottleKeyRef })).outcome).toBe('denied');
  expect((await key()).exists).toBe(false); const full = await occupancy(app, resource); expect(full.activeEntries).toBe(state.maxEntries);
  expect((await pressure(app, resource)).occurrences).toBeGreaterThan(diagnostic.occurrences);
  expect(await retained(app)).toEqual(protectedBefore);
  const recovered = await cleanup(app, resource, fixture);
  expect(recovered.maxEntries).toBe(state.maxEntries); expect(recovered.activeEntries).toBeLessThan(state.maxEntries);
  expect(await retained(app)).toEqual(protectedBefore); await oldReceipt(app, fixture);
  expect((await app.act('VISITOR-NEW', 'attempt-new-throttle-key', { keyRef: fixture.newThrottleKeyRef })).outcome).toBe('denied');
  // Wrong synthetic credentials still deny login, but a real admitted throttle key must now be recorded.
  expect((await key()).exists).toBe(true); await occupancy(app, resource);
});

test('SERVICE-QUOTA-temporary-bytes | AT-310 AC-OPS-010 | failed build and expired-temp cleanup retain sole good set and used media', async ({ app }) => {
  const resource = 'temporary-bytes', { fixture, state } = await setup(app, resource), protectedBefore = await retained(app), diagnostic = await pressure(app, resource);
  const start = await control(app, 'run-isolated-html-build', { trigger: 'scheduled-night-slot' }); required(start.jobId);
  await expect.poll(async () => (await app.observe('html-build-run', { jobId: start.jobId })).state, { timeout: 20_000 }).toMatch(/^(READY|FAILED)$/);
  const failed = await app.observe('html-build-run', { jobId: start.jobId }); expect(failed.state).toBe('FAILED'); expect(failed.failureCode).toBe('RESOURCE_PRESSURE');
  expect((await pressure(app, resource)).occurrences).toBeGreaterThan(diagnostic.occurrences);
  expect(await retained(app)).toEqual(protectedBefore); await occupancy(app, resource);
  const recovered = await cleanup(app, resource, fixture); expect(recovered.capacityBytes).toBe(state.capacityBytes);
  expect(await retained(app)).toEqual(protectedBefore); await oldReceipt(app, fixture);
  const next = await control(app, 'run-isolated-html-build', { trigger: 'scheduled-night-slot' }); required(next.jobId);
  await expect.poll(async () => (await app.observe('html-build-run', { jobId: next.jobId })).state, { timeout: 20_000 }).toMatch(/^(READY|FAILED)$/);
  const built = await app.observe('html-build-run', { jobId: next.jobId }); expect(built.state).toBe('READY'); required(built.setId);
  expect(built.setId).not.toBe(protectedBefore.activeSetId);
  const sets = await app.observe('service-good-set-files'); expect(sets.setIds).toContain(protectedBefore.activeSetId); expect(sets.setIds).toContain(built.setId);
  expect(sets.oldSetBytesDigest).toBe(protectedBefore.retainedSetManifestDigest); await occupancy(app, resource);
});
