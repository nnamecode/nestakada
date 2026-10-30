import { createHash } from 'node:crypto';
import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver(); try { await use(app); } finally { await app.close(); }
} });
test.beforeEach(async ({ context }) => {
  await context.route('**/*', route => route.abort());
  await context.routeWebSocket('**/*', socket => socket.close());
});
const required = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
const ids = value => { expect(Array.isArray(value)).toBe(true); value.forEach(required); expect(new Set(value).size).toBe(value.length); return [...value].sort(); };
const expectedRoutes = ['/', '/acceptance/night/service/', '/acceptance/night/second/'].sort();
const routeCanaries = { '/': ['NIGHT-PUBLISHED-CANARY'], '/acceptance/night/service/': ['NIGHT-OLD-TEXT', 'NIGHT-NEW-TEXT'],
  '/acceptance/night/second/': ['NIGHT-SECOND-PUBLISHED-CANARY'] };
async function setup(app, profile = 'html-two-good-sets-published-source') {
  const admission = await app.inspectInfrastructureAdmission();
  expect(admission.arc10Verified).toBe(true); expect(admission.isolatedInfrastructure).toBe(true);
  required(admission.reviewedEvidenceId); expect(admission.capabilities).toContain('html-build-control-v1');
  await app.reset(profile);
}
async function control(app, action, args = {}) {
  const result = await app.control(action, args); expect(result.outcome).toBe('accepted'); return result;
}
async function inventory(app) {
  const result = await app.observe('html-set-inventory');
  required(result.activeSetId); required(result.previousSetId); expect(result.previousSetId).not.toBe(result.activeSetId);
  const good = ids(result.usableSetIds); expect(good).toHaveLength(2);
  expect(good).toContain(result.activeSetId); expect(good).toContain(result.previousSetId);
  expect(result.activeVerified).toBe(true); expect(result.previousVerified).toBe(true);
  return result;
}
async function build(app) { const result = await control(app, 'run-isolated-html-build', { trigger: 'scheduled-night-slot' }); required(result.jobId); return result.jobId; }
async function finish(app, jobId) {
  await expect.poll(async () => (await app.observe('html-build-run', { jobId })).state, { timeout: 10_000 }).toMatch(/^(READY|FAILED)$/);
  const result = await app.observe('html-build-run', { jobId }); expect(result.jobId).toBe(jobId); return result;
}
async function setBytes(app, setId) {
  const result = await app.observe('html-set-byte-inventory', { setId });
  expect(result.setId).toBe(setId); expect(result.source).toBe('actual-storage-bytes');
  expect(Array.isArray(result.files)).toBe(true); expect(result.files.length).toBeGreaterThan(0);
  for (const file of result.files) {
    required(file.relativePath); required(file.bytesBase64); expect(Number.isSafeInteger(file.size) && file.size > 0).toBe(true);
    expect(file.sha256).toMatch(/^[a-f0-9]{64}$/);
    const bytes = Buffer.from(file.bytesBase64, 'base64'); expect(bytes.length).toBe(file.size);
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(file.sha256);
  }
  ids(result.files.map(file => file.relativePath));
  const htmlFiles = result.files.filter(file => typeof file.route === 'string');
  expect(ids(htmlFiles.map(file => file.route))).toEqual(expectedRoutes);
  const manifest = await app.observe('html-set-manifest', { setId }); expect(manifest.setId).toBe(setId);
  expect(ids(manifest.publicRoutes)).toEqual(expectedRoutes);
  for (const route of expectedRoutes) {
    const matches = htmlFiles.filter(file => file.route === route); expect(matches).toHaveLength(1);
    const body = Buffer.from(matches[0].bytesBase64, 'base64').toString('utf8');
    expect(routeCanaries[route].some(canary => body.includes(canary))).toBe(true);
  }
  return { setId: result.setId, source: result.source, files: result.files.map(file => ({ relativePath: file.relativePath,
    route: file.route ?? null, size: file.size, sha256: file.sha256, bytesBase64: file.bytesBase64 })).sort((a, b) => a.relativePath.localeCompare(b.relativePath)) };
}
function unchangedGood(after, before) {
  expect(after.activeSetId).toBe(before.activeSetId); expect(after.previousSetId).toBe(before.previousSetId);
  expect(ids(after.usableSetIds)).toEqual(ids(before.usableSetIds));
}
async function mediaBeforeActivation(app, jobId, setId) {
  const ledger = await app.observe('html-build-activation-ledger', { jobId });
  expect(ledger.jobId).toBe(jobId); expect(Array.isArray(ledger.events)).toBe(true); expect(ledger.events.length).toBeGreaterThan(0);
  const held = ledger.events.filter(event => event.kind === 'media-retention-committed' && event.setId === setId);
  const activated = ledger.events.filter(event => event.kind === 'active-pointer-committed' && event.setId === setId);
  expect(held).toHaveLength(1); expect(activated).toHaveLength(1);
  for (const event of [held[0], activated[0]]) expect(Number.isSafeInteger(event.sequence) && event.sequence >= 0).toBe(true);
  expect(held[0].sequence).toBeLessThan(activated[0].sequence);
}

test('HTML-BUILD-rotation | AT-047 AC-047 | verified new night set replaces oldest only after success', async ({ app }) => {
  await setup(app); const before = await inventory(app), oldActive = await setBytes(app, before.activeSetId);
  const jobId = await build(app), done = await finish(app, jobId); expect(done.state).toBe('READY'); required(done.setId);
  const after = await inventory(app); expect(after.activeSetId).toBe(done.setId); expect(after.activeSetId).not.toBe(before.activeSetId);
  expect(after.previousSetId).toBe(before.activeSetId);
  expect(await setBytes(app, after.previousSetId)).toEqual(oldActive);
  expect((await app.observe('html-build-run', { jobId })).mediaRetentionVerified).toBe(true);
  await mediaBeforeActivation(app, jobId, done.setId);
});

test('HTML-BUILD-published-routes | AT-047 AC-047 | manifest contains exactly the independent published fixture routes', async ({ app }) => {
  await setup(app); const done = await finish(app, await build(app)); expect(done.state).toBe('READY'); required(done.setId);
  const manifest = await app.observe('html-set-manifest', { setId: done.setId }); expect(manifest.setId).toBe(done.setId);
  expect(ids(manifest.publicRoutes)).toEqual(['/', '/acceptance/night/service/', '/acceptance/night/second/'].sort());
  required(manifest.snapshotAt); required(manifest.sourceGeneration);
  expect(Number.isFinite(Date.parse(manifest.snapshotAt))).toBe(true);
});

test('HTML-BUILD-private-exclusion | AT-047 AT-207 AC-047 AC-HTML-007 | actual completed files and manifest exclude existing private source canaries', async ({ app }) => {
  await setup(app);
  const proof = await app.observe('html-private-source-proof');
  expect(ids(proof.kinds)).toEqual(['page-draft', 'page-history', 'request', 'technical-token'].sort());
  expect(proof.existing).toBe(true); expect(Array.isArray(proof.canaries)).toBe(true); expect(proof.canaries).toHaveLength(4); proof.canaries.forEach(required);
  const done = await finish(app, await build(app)); expect(done.state).toBe('READY'); required(done.setId);
  const actual = await setBytes(app, done.setId);
  for (const file of actual.files) {
    const raw = Buffer.from(file.bytesBase64, 'base64').toString('utf8');
    for (const canary of proof.canaries) expect(raw).not.toContain(canary);
  }
  expect(actual.files.some(file => Buffer.from(file.bytesBase64, 'base64').toString('utf8').includes('NIGHT-PUBLISHED-CANARY'))).toBe(true);
});

for (const phase of ['prepare', 'validate', 'retain-media', 'activate', 'cleanup']) {
  test(`HTML-BUILD-fault-${phase} | AT-047 AT-206 AC-047 AC-HTML-006 | bounded job IO failure never replaces good bytes with an incomplete candidate`, async ({ app }) => {
    await setup(app); const before = await inventory(app), active = await setBytes(app, before.activeSetId), previous = await setBytes(app, before.previousSetId);
    await control(app, 'set-html-build-fault', { phase, fault: 'bounded-test-storage-write-failure' });
    const jobId = await build(app), result = await finish(app, jobId);
    const after = await inventory(app);
    // A boundary failure after activation may leave a complete new set selected; job state is not the pointer oracle.
    if (['activate', 'cleanup'].includes(phase) && after.activeSetId !== before.activeSetId) {
      if (phase === 'cleanup') expect(result.cleanupIncomplete).toBe(true);
      required(result.setId); expect(after.activeSetId).toBe(result.setId); expect(after.previousSetId).toBe(before.activeSetId);
      expect(result.mediaRetentionVerified).toBe(true); await setBytes(app, after.activeSetId);
      const manifest = await app.observe('html-set-manifest', { setId: after.activeSetId });
      expect(ids(manifest.publicRoutes)).toEqual(['/', '/acceptance/night/service/', '/acceptance/night/second/'].sort());
      expect(await setBytes(app, before.activeSetId)).toEqual(active);
    } else {
      expect(result.state).toBe('FAILED'); required(result.safeErrorCode);
      unchangedGood(after, before);
      expect(await setBytes(app, before.activeSetId)).toEqual(active); expect(await setBytes(app, before.previousSetId)).toEqual(previous);
    }
    const event = await app.observe('html-build-failure-evidence', { jobId });
    expect(event.jobId).toBe(jobId); expect(event.observedFailure).toBe(true); required(event.incidentId);
  });
}

test('HTML-BUILD-validation-barrier | AT-047 AC-047 | unverified held candidate does not move either good-set pointer', async ({ app }) => {
  await setup(app); const before = await inventory(app);
  await control(app, 'hold-html-build-phase', { phase: 'before-validation' }); const jobId = await build(app);
  await expect.poll(async () => (await app.observe('html-build-run', { jobId })).phase).toBe('HELD_BEFORE_VALIDATION');
  unchangedGood(await inventory(app), before);
  await control(app, 'release-html-build-phase', { jobId });
  expect((await finish(app, jobId)).state).toBe('READY');
});

test('HTML-BUILD-page-coherence | AT-205 AC-HTML-005 | one atomic page publication cannot produce old text with new H1', async ({ app, page }) => {
  await setup(app); const before = await inventory(app);
  const initial = await app.observe('page', { page: 'P-NIGHT' }); required(initial.revision);
  expect(initial.publicText).toBe('NIGHT-OLD-TEXT'); expect(initial.h1).toBe('NIGHT-OLD-H1');
  await control(app, 'hold-html-build-phase', { phase: 'after-first-source-read' }); const jobId = await build(app);
  await expect.poll(async () => (await app.observe('html-build-run', { jobId })).phase).toBe('HELD_AFTER_FIRST_SOURCE_READ');
  expect((await app.act('OWNER', 'submit-page-direct', { page: 'P-NIGHT', base: initial.revision, fields: { text: 'NIGHT-NEW-TEXT', h1: 'NIGHT-NEW-H1' } })).outcome).toBe('accepted');
  const changed = await app.observe('page', { page: 'P-NIGHT' }); expect(changed.publicText).toBe('NIGHT-NEW-TEXT'); expect(changed.h1).toBe('NIGHT-NEW-H1');
  await control(app, 'release-html-build-phase', { jobId }); const result = await finish(app, jobId);
  if (result.state === 'FAILED') { required(result.safeErrorCode); unchangedGood(await inventory(app), before); return; }
  required(result.setId); const bytes = await setBytes(app, result.setId);
  const file = bytes.files.find(file => file.route === '/acceptance/night/service/'); expect(file).toBeTruthy();
  const facts = await page.evaluate(source => {
    const document = new DOMParser().parseFromString(source, 'text/html');
    return { h1: document.querySelector('h1')?.textContent.trim(), body: document.body.textContent };
  }, Buffer.from(file.bytesBase64, 'base64').toString('utf8'));
  const oldText = facts.body.includes('NIGHT-OLD-TEXT'), newText = facts.body.includes('NIGHT-NEW-TEXT');
  expect(Number(oldText) + Number(newText)).toBe(1); expect(facts.h1).toBe(oldText ? 'NIGHT-OLD-H1' : 'NIGHT-NEW-H1');
});

test('HTML-BUILD-day-edit | AT-047 AT-210 AC-047 AC-HTML-010 | daytime page save does not execute a reserve build or rewrite snapshot time', async ({ app }) => {
  await setup(app, 'html-two-good-sets-frozen-daytime'); const before = await inventory(app);
  const ledger = await app.observe('html-build-ledger'); expect(Number.isSafeInteger(ledger.jobCount) && ledger.jobCount >= 0).toBe(true);
  const snapshot = await app.observe('html-set-manifest', { setId: before.activeSetId }); required(snapshot.snapshotAt);
  const initial = await app.observe('page', { page: 'P-NIGHT' }); required(initial.revision); expect(initial.publicText).not.toBe('NIGHT-DAYTIME-EDIT');
  expect((await app.act('OWNER', 'submit-page-direct', { page: 'P-NIGHT', base: initial.revision, fields: { text: 'NIGHT-DAYTIME-EDIT' } })).outcome).toBe('accepted');
  expect((await app.observe('page', { page: 'P-NIGHT' })).publicText).toBe('NIGHT-DAYTIME-EDIT');
  await control(app, 'drain-isolated-html-jobs', { scope: 'currently-due-only' });
  expect((await app.observe('html-build-ledger')).jobCount).toBe(ledger.jobCount); unchangedGood(await inventory(app), before);
  expect((await app.observe('html-set-manifest', { setId: before.activeSetId })).snapshotAt).toBe(snapshot.snapshotAt);
});

test('HTML-BUILD-media-barrier | AT-047 AT-206 AC-047 AC-HTML-006 | candidate cannot become active before all referenced media are retained', async ({ app }) => {
  await setup(app); const before = await inventory(app);
  await control(app, 'hold-html-build-phase', { phase: 'before-media-retention' }); const jobId = await build(app);
  await expect.poll(async () => (await app.observe('html-build-run', { jobId })).phase).toBe('HELD_BEFORE_MEDIA_RETENTION');
  unchangedGood(await inventory(app), before);
  await control(app, 'release-html-build-phase', { jobId }); const done = await finish(app, jobId); expect(done.state).toBe('READY'); required(done.setId);
  const manifest = await app.observe('html-set-media-retention', { setId: done.setId }); expect(manifest.setId).toBe(done.setId);
  const requiredIds = ids(manifest.requiredAssetIds); expect(requiredIds.length).toBeGreaterThan(0);
  for (const assetId of requiredIds) { expect(ids(manifest.retainedAssetIds)).toContain(assetId); expect(ids(manifest.existingAssetIds)).toContain(assetId); }
  expect((await inventory(app)).activeSetId).toBe(done.setId);
  await mediaBeforeActivation(app, jobId, done.setId);
});
