import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await use(app); } finally { await app.close(); }
} });
const oldPhone = '+70000000001', newPhone = '+70000000002';
const required = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
function same(after, before) {
  for (const field of ['id', 'revision', 'draftRevision', 'currentVersionId', 'currentHtml', 'draftHtml', 'versions']) {
    expect(before).toHaveProperty(field); expect(after).toHaveProperty(field); expect(after[field]).toEqual(before[field]);
  }
}
async function current(app, kind) {
  const value = await app.observe('shared-block', { kind });
  expect(value.kind).toBe(kind);
  for (const field of ['id', 'revision', 'draftRevision', 'currentVersionId']) required(value[field]);
  expect(Array.isArray(value.versions) && value.versions.length > 0).toBe(true);
  return value;
}
async function snapshot(app, kind, version) {
  const value = await app.observe('shared-component-snapshot', { kind, version });
  expect(value.versionId).toBe(version); required(value.componentId); required(value.schemaVersion);
  expect(value.payload !== null && typeof value.payload === 'object').toBe(true);
  expect(Array.isArray(value.assets)).toBe(true);
  for (const asset of value.assets) { required(asset.id); expect(asset.sha256).toMatch(/^[a-f0-9]{64}$/); }
  return value;
}
async function runtime(app, componentId) {
  const value = await app.observe('shared-component-runtime', { componentId });
  expect(value.componentId).toBe(componentId);
  expect(Array.isArray(value.supportedSchemas) && value.supportedSchemas.length > 0).toBe(true);
  expect(Array.isArray(value.invocations)).toBe(true);
  const ids = new Set();
  for (const event of value.invocations) {
    required(event.invocationId); required(event.schemaVersion); required(event.phase);
    expect(event.componentId).toBe(componentId); expect(ids.has(event.invocationId)).toBe(false); ids.add(event.invocationId);
  }
  return value;
}
async function publicBlock(app, kind) {
  const value = await app.observe('public-with-shared-blocks', { page: 'P-ONE' });
  expect(value.status).toBe(200); required(value[`${kind}Html`]); return value;
}
async function componentState(app, kind) {
  const value = await app.observe('shared-component-block-state', { kind });
  for (const field of ['currentPayload', 'draftPayload', 'currentSchemaVersion', 'draftSchemaVersion', 'currentAssets', 'draftAssets'])
    expect(value).toHaveProperty(field);
  return value;
}
async function setup(app, kind) {
  await app.reset('shared-block-component-history', { kind });
  const evidence = await app.observe('shared-component-history-evidence', { kind });
  expect(evidence.oldPhone).toBe(oldPhone); expect(evidence.newPhone).toBe(newPhone);
  required(evidence.compatibleVersionId); required(evidence.incompatibleVersionId);
  expect(evidence.compatibleVersionId).not.toBe(evidence.incompatibleVersionId);
  const before = await current(app, kind), otherKind = kind === 'header' ? 'footer' : 'header';
  expect(before.currentVersionId).not.toBe(evidence.compatibleVersionId);
  expect(before.currentVersionId).not.toBe(evidence.incompatibleVersionId);
  const compatible = await snapshot(app, kind, evidence.compatibleVersionId);
  const incompatible = await snapshot(app, kind, evidence.incompatibleVersionId);
  expect(compatible.componentId).toBe(incompatible.componentId);
  const actualRuntime = await runtime(app, compatible.componentId);
  expect(actualRuntime.supportedSchemas).toContain(compatible.schemaVersion);
  expect(actualRuntime.supportedSchemas).not.toContain(incompatible.schemaVersion);
  return { before, otherKind, otherBefore: await current(app, otherKind), compatible, incompatible };
}

for (const kind of ['header', 'footer']) {
  test(`BLOCK-COMPONENT-${kind}-literal-restore | AT-405 AC-PRO-005 | compare exposes old literal contact and explicit compatible restore restores it`, async ({ app }) => {
    const { before, otherKind, otherBefore, compatible } = await setup(app, kind);
    const initial = await publicBlock(app, kind);
    expect(initial[`${kind}Html`]).toContain(newPhone); expect(initial[`${kind}Html`]).not.toContain(oldPhone);
    const compare = await app.act('OWNER', 'compare-shared-block-version', { kind, version: compatible.versionId });
    expect(compare.outcome).toBe('accepted');
    expect(compare.comparison.literalContactValues).toContain(oldPhone);
    expect(compare.comparison.savedPayload).toEqual(compatible.payload);
    expect(compare.comparison.componentSchemaVersion).toBe(compatible.schemaVersion);
    // Viewing a historical contact alone cannot publish it or rewrite the other common block.
    same(await current(app, kind), before); same(await current(app, otherKind), otherBefore);
    const prepared = await app.act('OWNER', 'prepare-shared-block-restore', { kind, version: compatible.versionId, base: before.revision });
    expect(prepared.outcome).toBe('accepted'); expect(prepared.confirmation).toBeTruthy();
    same(await current(app, kind), before);
    const applied = await app.act('OWNER', 'apply-shared-block-version', { kind, version: compatible.versionId,
      base: before.revision, confirmation: prepared.confirmation });
    expect(applied.outcome).toBe('accepted');
    const after = await current(app, kind);
    expect(after.revision).not.toBe(before.revision); expect(after.currentVersionId).not.toBe(compatible.versionId);
    expect(after.versions).toHaveLength(before.versions.length + 1);
    const published = await publicBlock(app, kind);
    expect(published[`${kind}Html`]).toContain(oldPhone); expect(published[`${kind}Html`]).not.toContain(newPhone);
    expect(await snapshot(app, kind, compatible.versionId)).toEqual(compatible);
    same(await current(app, otherKind), otherBefore);
  });

  test(`BLOCK-COMPONENT-${kind}-incompatible | AT-405 AC-PRO-005 | incompatible snapshot is readable as data but never invoked or partially applied`, async ({ app }) => {
    const { before, otherKind, otherBefore, incompatible } = await setup(app, kind);
    const componentBefore = await componentState(app, kind), otherComponentBefore = await componentState(app, otherKind);
    const traceBefore = await runtime(app, incompatible.componentId), initial = await publicBlock(app, kind);
    const compare = await app.act('OWNER', 'compare-shared-block-version', { kind, version: incompatible.versionId });
    expect(compare.outcome).toBe('accepted');
    expect(compare.comparison.savedPayload).toEqual(incompatible.payload);
    expect(compare.comparison.componentSchemaVersion).toBe(incompatible.schemaVersion);
    same(await current(app, kind), before);
    expect(await componentState(app, kind)).toEqual(componentBefore);
    const prepared = await app.act('OWNER', 'prepare-shared-block-restore', { kind, version: incompatible.versionId, base: before.revision });
    expect(prepared.outcome).toBe('denied'); expect(prepared.body).toContain('Версия несовместима');
    same(await current(app, kind), before);
    expect(await componentState(app, kind)).toEqual(componentBefore);
    // A forged direct apply cannot turn a rejected preview into a partial restoration.
    const applied = await app.act('OWNER', 'apply-shared-block-version', { kind, version: incompatible.versionId,
      base: before.revision, confirmation: 'SYNTHETIC-NOT-ISSUED-CONFIRMATION' });
    expect(applied.outcome).toBe('denied');
    same(await current(app, kind), before); same(await current(app, otherKind), otherBefore);
    expect(await componentState(app, kind)).toEqual(componentBefore);
    expect(await componentState(app, otherKind)).toEqual(otherComponentBefore);
    expect(await snapshot(app, kind, incompatible.versionId)).toEqual(incompatible);
    const final = await publicBlock(app, kind);
    for (const field of ['headerHtml', 'footerHtml', 'pageText']) expect(final[field]).toBe(initial[field]);
    const traceAfter = await runtime(app, incompatible.componentId);
    expect(traceAfter.supportedSchemas).toEqual(traceBefore.supportedSchemas);
    const unsupported = trace => trace.invocations.filter(event => event.schemaVersion === incompatible.schemaVersion);
    expect(unsupported(traceAfter)).toEqual(unsupported(traceBefore));
    // At least the real current public render must be visible; an empty/broken trace is not evidence.
    const oldIds = new Set(traceBefore.invocations.map(event => event.invocationId));
    expect(traceAfter.invocations.some(event => !oldIds.has(event.invocationId) && traceAfter.supportedSchemas.includes(event.schemaVersion))).toBe(true);
  });
}
