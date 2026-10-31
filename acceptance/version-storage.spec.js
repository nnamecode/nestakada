import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver(); try { await use(app); } finally { await app.close(); }
} });
test.describe.configure({ timeout: 120_000 }); // Test-fixture resource budget, not a website SLA.
const CAP = 268_435_456, COUNT = 10_000;
const required = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
const integer = value => { expect(Number.isSafeInteger(value) && value >= 0).toBe(true); return value; };
async function admission(app) {
  const permit = await app.inspectInfrastructureAdmission();
  expect(permit.arc10Verified).toBe(true); expect(permit.isolatedInfrastructure).toBe(true);
  required(permit.reviewedEvidenceId); expect(permit.capabilities).toContain('content-storage-control-v1');
}
async function state(app) {
  const value = await app.observe('version-storage-business-state');
  for (const field of ['pages', 'blocks', 'versions', 'assetReferences', 'assetFiles', 'protectedSnapshots']) expect(Array.isArray(value[field])).toBe(true);
  expect(value.pages.length).toBeGreaterThan(0); expect(value.blocks).toHaveLength(2);
  expect(value.versions.length).toBeGreaterThan(0); expect(value.assetFiles.length).toBeGreaterThan(0);
  return value;
}
async function publicState(app) {
  const value = await app.observe('version-storage-public-response');
  expect(value.status).toBe(200);
  for (const field of ['pageText', 'headerHtml', 'footerHtml', 'etag']) required(value[field]);
  return value;
}
async function quota(app) {
  const value = await app.observe('shared-history-resource-usage');
  expect(value.limitBytes).toBe(CAP); expect(value.limitSnapshots).toBe(COUNT);
  integer(value.usedBytes); integer(value.snapshotCount); integer(value.nextReservationBytes);
  expect(value.nextReservationBytes).toBeGreaterThan(0);
  expect(value.usedBytes).toBeLessThanOrEqual(CAP); expect(value.snapshotCount).toBeLessThanOrEqual(COUNT);
  for (const field of ['snapshotDataBytes', 'indexBytes', 'metadataBytes', 'temporaryBytes']) integer(value[field]);
  expect(value.usedBytes).toBe(value.snapshotDataBytes + value.indexBytes + value.metadataBytes + value.temporaryBytes);
  expect(value.mediaBytesExcluded).toBe(true); expect(value.source).toBe('actual-storage-measurement');
  return value;
}
async function block(app, kind) {
  const value = await app.observe('shared-block', { kind });
  expect(value.kind).toBe(kind); required(value.id); required(value.revision); required(value.currentVersionId);
  expect(Array.isArray(value.versions)).toBe(true); expect(value.versions.length).toBeGreaterThan(0);
  return value;
}
async function retainedBlock(app, kind, text) {
  expect(await app.observe(`open-${kind}-input`, { actor: 'OWNER' })).toBe(text);
  expect(await app.observe('editor-memory-state', { actor: 'OWNER', canary: text })).toEqual({
    source: 'actual-actor-browser', urlContainsCanary: false, localStorageContainsCanary: false, sessionStorageContainsCanary: false,
  });
}
async function setupBlock(app, kind, resource, operation) {
  await admission(app);
  await app.reset('shared-history-resource-boundary', { kind, resource, operation });
  const fixture = await app.observe('version-storage-fixture');
  expect(fixture.kind).toBe(kind); required(fixture.input); required(fixture.restoreVersionId);
  expect(fixture.inputPreparedByActualUi).toBe(true);
  const current = await block(app, kind); expect(current.currentVersionId).not.toBe(fixture.restoreVersionId);
  expect(current.versions.some(version => version.id === fixture.restoreVersionId)).toBe(true);
  await retainedBlock(app, kind, fixture.input);
  const drafts = await app.observe('shared-block-draft-counts');
  expect(drafts).toEqual({ header: 1, footer: 1 });
  return { fixture, current };
}

for (const kind of ['header', 'footer']) {
  for (const resource of ['count-full', 'bytes-insufficient']) for (const operation of ['publish', 'restore']) {
    test(`VERSION-STORAGE-budget-${kind}-${resource}-${operation} | AT-117 AC-DTL-017 | shared budget refuses a whole new snapshot without pruning history or losing input`, async ({ app }) => {
      const { fixture, current } = await setupBlock(app, kind, resource, operation), usage = await quota(app);
      if (resource === 'count-full') expect(usage.snapshotCount).toBe(COUNT);
      else {
        expect(usage.snapshotCount).toBeLessThan(COUNT);
        expect(usage.usedBytes + usage.nextReservationBytes).toBeGreaterThan(CAP);
      }
      const before = await state(app), rendered = await publicState(app);
      let result;
      if (operation === 'publish') result = await app.act('OWNER', 'save-open-shared-block', { kind, base: current.revision });
      else {
        const prepared = await app.act('OWNER', 'prepare-shared-block-restore', { kind, version: fixture.restoreVersionId, base: current.revision });
        expect(['accepted', 'denied']).toContain(prepared.outcome);
        if (prepared.outcome === 'denied') result = prepared; // Early resource refusal is valid too.
        else {
          expect(prepared.confirmation).toBeTruthy();
          result = await app.act('OWNER', 'apply-shared-block-version', { kind, version: fixture.restoreVersionId, base: current.revision, confirmation: prepared.confirmation });
        }
      }
      expect(result.outcome).toBe('denied'); expect(result.body).toContain('Недостаточно места для новой версии общего блока');
      expect(await state(app)).toEqual(before); expect(await publicState(app)).toEqual(rendered);
      const after = await quota(app); expect(after.snapshotCount).toBe(usage.snapshotCount);
      expect(await app.observe('shared-block-draft-counts')).toEqual({ header: 1, footer: 1 });
      await retainedBlock(app, kind, fixture.input);
    });
  }
  test(`VERSION-STORAGE-warning-${kind} | AT-117 AC-DTL-017 | warning at75percent leaves space for a real valid publication`, async ({ app }) => {
    const { fixture, current } = await setupBlock(app, kind, 'warning-band', 'publish'), usage = await quota(app);
    expect(usage.usedBytes).toBeGreaterThanOrEqual(CAP * 0.75); expect(usage.usedBytes).toBeLessThan(CAP * 0.9);
    expect(usage.usedBytes + usage.nextReservationBytes).toBeLessThanOrEqual(CAP); expect(usage.snapshotCount).toBeLessThan(COUNT);
    const status = await app.act('OWNER', 'read-shared-history-budget', { kind });
    expect(status.outcome).toBe('accepted'); required(status.warningText);
    const before = await state(app);
    expect((await app.act('OWNER', 'save-open-shared-block', { kind, base: current.revision })).outcome).toBe('accepted');
    const after = await block(app, kind); expect(after.revision).not.toBe(current.revision);
    expect(after.currentHtml).toBe(fixture.input); expect(after.versions).toHaveLength(current.versions.length + 1);
    const measured = await quota(app); expect(measured.snapshotCount).toBe(usage.snapshotCount + 1);
    expect((await publicState(app))[`${kind}Html`]).toBe(after.currentHtml);
    const next = await state(app); expect(next.protectedSnapshots).toEqual(before.protectedSnapshots);
  });
}

async function control(app, action, args) { const result = await app.control(action, args); expect(result.outcome).toBe('accepted'); return result; }
async function retainedPage(app, text) {
  expect(await app.observe('open-editor-input', { actor: 'S-EDIT', page: 'P-ASSIGNED' })).toBe(text);
  expect(await app.observe('editor-memory-state', { actor: 'S-EDIT', canary: text })).toEqual({
    source: 'actual-actor-browser', urlContainsCanary: false, localStorageContainsCanary: false, sessionStorageContainsCanary: false,
  });
}
for (const operation of ['save', 'restore']) for (const phase of ['version-persist', 'asset-reference-persist']) {
  test(`VERSION-STORAGE-atomic-${operation}-${phase} | AT-119 AC-DTL-019 | version and Asset reference failure leaves current publication and history unchanged`, async ({ app }) => {
    await admission(app); await app.reset('content-storage-save-restore', { operation });
    const fixture = await app.observe('version-storage-fixture'); required(fixture.input); required(fixture.restoreVersionId);
    const current = await app.observe('page', { page: 'P-ASSIGNED' });
    if (operation === 'restore') {
      const prepared = await app.act('S-EDIT', 'prepare-page-version-restore', { page: 'P-ASSIGNED', version: fixture.restoreVersionId });
      expect(prepared.outcome).toBe('accepted'); expect(prepared.preparation).toBeTruthy();
      expect((await app.act('S-EDIT', 'stage-page-version-restore', { page: 'P-ASSIGNED', preparation: prepared.preparation, confirmInputReplacement: true })).outcome).toBe('ui-observed');
    }
    await retainedPage(app, fixture.input);
    const before = await state(app), publicBefore = await publicState(app);
    const fault = await control(app, 'set-content-storage-fault', { pageId: current.id, phase, fault: 'persistent-test-storage-error' }); required(fault.faultId);
    const result = await app.act('S-EDIT', 'save-open-editor', { page: 'P-ASSIGNED', base: current.revision });
    expect(result.outcome).toBe('denied');
    const evidence = await app.observe('content-storage-fault-evidence', { faultId: fault.faultId });
    expect(evidence.phase).toBe(phase); expect(evidence.hitCount).toBeGreaterThanOrEqual(1); expect(evidence.rollbackConfirmed).toBe(true);
    expect(await state(app)).toEqual(before); expect(await publicState(app)).toEqual(publicBefore);
    await retainedPage(app, fixture.input);
    await control(app, 'clear-content-storage-fault', { pageId: current.id, faultId: fault.faultId });
    expect((await app.act('S-EDIT', 'save-open-editor', { page: 'P-ASSIGNED', base: current.revision })).outcome).toBe('accepted');
    const after = await app.observe('page', { page: 'P-ASSIGNED' });
    expect(after.publicText).toBe(fixture.input); expect(after.revision).not.toBe(current.revision);
    expect(after.versions).toHaveLength(current.versions.length + 1);
    expect((await publicState(app)).pageText).toBe(fixture.input);
    const final = await state(app); expect(final.protectedSnapshots).toEqual(before.protectedSnapshots);
  });
}

test('VERSION-STORAGE-incompatible | AT-119 AC-DTL-019 | incompatible historical snapshot remains intact and cannot be partially applied', async ({ app }) => {
  await admission(app); await app.reset('content-storage-incompatible-history');
  const fixture = await app.observe('version-storage-fixture'); required(fixture.incompatibleVersionId); required(fixture.input);
  await retainedPage(app, fixture.input);
  const before = await state(app), publicBefore = await publicState(app);
  const historical = await app.observe('page-version-payload', { page: 'P-ASSIGNED', version: fixture.incompatibleVersionId });
  expect(historical.versionId).toBe(fixture.incompatibleVersionId); required(historical.schemaVersion);
  expect(historical.compatible).toBe(false);
  const prepared = await app.act('S-EDIT', 'prepare-page-version-restore', { page: 'P-ASSIGNED', version: fixture.incompatibleVersionId });
  expect(prepared.outcome).toBe('denied'); expect(prepared.body).toContain('Версия несовместима');
  expect(await state(app)).toEqual(before); expect(await publicState(app)).toEqual(publicBefore);
  expect(await app.observe('page-version-payload', { page: 'P-ASSIGNED', version: fixture.incompatibleVersionId })).toEqual(historical);
  await retainedPage(app, fixture.input);
});
