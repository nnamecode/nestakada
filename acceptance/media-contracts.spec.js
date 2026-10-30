import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';
import { readCsv } from './test-support.js';

const test = base.extend({
  app: async ({}, use) => {
    const app = await openApplicationDriver();
    try { await use(app); } finally { await app.close(); }
  },
});

function nonempty(value) {
  expect(typeof value).toBe('string');
  expect(value.trim().length).toBeGreaterThan(0);
}
function checksum(value) { expect(value).toMatch(/^[a-f0-9]{64}$/); }
function asset(value) {
  nonempty(value.id); expect(value.exists).toBe(true); nonempty(value.path);
  expect(Number.isSafeInteger(value.bytes)).toBe(true); expect(value.bytes).toBeGreaterThan(0);
  checksum(value.sha256); expect(Array.isArray(value.references)).toBe(true);
  for (const reference of value.references) { nonempty(reference.kind); nonempty(reference.objectId); }
  return value;
}
function pageMedia(value) {
  nonempty(value.pageId); nonempty(value.revision); nonempty(value.folder);
  expect(Array.isArray(value.placements)).toBe(true); expect(value.placements.length).toBeGreaterThan(0);
  for (const item of value.placements) {
    for (const key of ['placementId', 'assetId', 'src', 'alignment']) nonempty(item[key]);
    expect(typeof item.alt).toBe('string');
  }
  return value;
}
function picker(value) {
  nonempty(value.currentFolder); nonempty(value.rootFolder);
  expect(value.rootFolder).toBe('/img/');
  expect(value.currentFolder.startsWith('/img/')).toBe(true);
  expect(Array.isArray(value.entries)).toBe(true);
  for (const item of value.entries) { nonempty(item.path); expect(item.path.startsWith('/img/')).toBe(true); }
  return value;
}
async function preparedCleanup(app) {
  const prepared = await app.act('OWNER', 'prepare-media-cleanup');
  expect(prepared.outcome).toBe('accepted');
  expect(prepared.confirmation).toBeTruthy();
  expect(Array.isArray(prepared.candidates)).toBe(true);
  expect(prepared.candidates.length).toBeGreaterThan(0);
  for (const candidate of prepared.candidates) {
    nonempty(candidate.assetId); nonempty(candidate.path);
    expect(Number.isSafeInteger(candidate.bytes)).toBe(true); expect(candidate.bytes).toBeGreaterThan(0);
  }
  expect(prepared.totalBytes).toBe(prepared.candidates.reduce((total, item) => total + item.bytes, 0));
  return prepared;
}

test('MEDIA-025-hashes | AT-025 AC-025 | imported originals match all 214 independent manifest hashes', async ({ app }) => {
  const expected = readCsv('docs/analytics-media-evidence.csv').filter(row => row.role === 'gallery-original');
  expect(expected).toHaveLength(214);
  expect(new Set(expected.map(row => row.source_url)).size).toBe(214);
  for (const row of expected) { nonempty(row.source_url); checksum(row.sha256); expect(Number(row.bytes)).toBeGreaterThan(0); }
  await app.reset('gallery-imported-originals-from-local-archive');
  const actual = await app.observe('gallery-original-hash-inventory');
  expect(Array.isArray(actual)).toBe(true); expect(actual).toHaveLength(214);
  expect(new Set(actual.map(item => item.sourceUrl)).size).toBe(214);
  for (const item of actual) {
    nonempty(item.sourceUrl); checksum(item.sha256);
    expect(Number.isSafeInteger(item.bytes)).toBe(true); expect(item.bytes).toBeGreaterThan(0);
    expect(item.hashFrom).toBe('storage-file-bytes');
    const source = expected.find(row => row.source_url === item.sourceUrl);
    expect(source, 'each actual original must have an independent manifest record').toBeTruthy();
    expect(item.bytes).toBe(Number(source.bytes)); expect(item.sha256).toBe(source.sha256);
  }
});

// Positive input formats/output MIME are deferred until an independent owner-approved upload policy exists.
// Synthetic PNG/JPEG/WebP candidates do not themselves establish an accepted format allowlist.

for (const fileRef of ['svg', 'html', 'svg-disguised-as-png', 'jpeg-mime-png-bytes', 'png-extension-jpeg-bytes', 'truncated-png']) {
  test(`MEDIA-026-reject-${fileRef} | AT-026 AC-026 | invalid upload leaves no usable Asset or changed page`, async ({ app }) => {
    await app.reset('synthetic-media-upload-files');
    const before = pageMedia(await app.observe('page-media', { page: 'P-A' }));
    const inventory = await app.observe('media-inventory-state');
    expect(Array.isArray(inventory.assetIds)).toBe(true); expect(inventory.assetIds.length).toBeGreaterThan(0);
    const result = await app.act('OWNER', 'upload-media-direct', { page: 'P-A', fileRef });
    expect(result.outcome).toBe('denied');
    expect((await app.observe('media-inventory-state')).assetIds).toEqual(inventory.assetIds);
    expect(pageMedia(await app.observe('page-media', { page: 'P-A' }))).toEqual(before);
    const rejected = await app.observe('last-upload-state');
    expect(rejected.usableAssetCreated).toBe(false); expect(rejected.activeContentExecuted).toBe(false);
  });
}

for (const field of ['assetId', 'src', 'alt', 'alignment']) {
  test(`MEDIA-107-rights-${field} | AT-107 AC-DTL-007 | valid same-handler media change stays owner-only`, async ({ app }) => {
    await app.reset('shared-media-replacement');
    const before = pageMedia(await app.observe('page-media', { page: 'P-A' }));
    const choices = await app.observe('media-fixture-identifiers');
    for (const key of ['otherAssetId', 'otherAssetPath']) nonempty(choices[key]);
    const current = before.placements[0];
    const value = field === 'assetId' ? choices.otherAssetId : field === 'src' ? choices.otherAssetPath : field === 'alt' ? 'Другая допустимая подпись' : current.alignment === 'left' ? 'right' : 'left';
    expect(value).not.toBe(current[field]);
    const args = { page: 'P-A', placementId: current.placementId, base: before.revision, field, value };
    expect((await app.act('S-EDIT', 'submit-media-markup-direct', args)).outcome).toBe('denied');
    expect(pageMedia(await app.observe('page-media', { page: 'P-A' }))).toEqual(before);
    expect((await app.act('OWNER', 'submit-media-markup-direct', args)).outcome).toBe('accepted');
    const changed = pageMedia(await app.observe('page-media', { page: 'P-A' }));
    expect(changed.placements.find(item => item.placementId === current.placementId)[field]).toBe(value);
  });
}

test('MEDIA-027-open | AT-027 AC-027 | picker opens actual material folder', async ({ app }) => {
  await app.reset('nested-media-catalog');
  const page = pageMedia(await app.observe('page-media', { page: 'P-A' }));
  expect((await app.act('OWNER', 'open-media-picker', { page: 'P-A' })).outcome).toBe('accepted');
  const actual = picker(await app.observe('media-picker-state'));
  expect(actual.currentFolder).toBe(page.folder);
});

test('MEDIA-027-search | AT-027 AC-027 | search includes descendants and remains inside selected folder', async ({ app }) => {
  await app.reset('nested-media-catalog');
  expect((await app.act('OWNER', 'open-media-picker', { page: 'P-A' })).outcome).toBe('accepted');
  const folder = picker(await app.observe('media-picker-state')).currentFolder;
  const subtree = folder.replace(/\/+$/, '') + '/';
  const identifiers = await app.observe('media-fixture-identifiers');
  nonempty(identifiers.searchSiblingFolder);
  const sibling = identifiers.searchSiblingFolder.replace(/\/+$/, '') + '/';
  expect(sibling.startsWith(subtree.slice(0, -1))).toBe(true);
  expect(sibling.startsWith(subtree)).toBe(false);
  // Positive control: a same-query file really exists in a sibling with a shared text prefix.
  expect((await app.act('OWNER', 'browse-media-folder-direct', { folder: sibling })).outcome).toBe('accepted');
  expect((await app.act('OWNER', 'search-media-picker', { query: 'MEDIA-SEARCH-CANARY' })).outcome).toBe('accepted');
  const neighboringResults = picker(await app.observe('media-picker-state'));
  expect(neighboringResults.entries.length).toBeGreaterThan(0);
  for (const item of neighboringResults.entries) expect(item.path.startsWith(sibling)).toBe(true);
  expect((await app.act('OWNER', 'browse-media-folder-direct', { folder })).outcome).toBe('accepted');
  expect((await app.act('OWNER', 'search-media-picker', { query: 'MEDIA-SEARCH-CANARY' })).outcome).toBe('accepted');
  const results = picker(await app.observe('media-picker-state'));
  expect(results.entries.length).toBeGreaterThan(0);
  expect(results.entries.some(item => item.path.includes('/nested/'))).toBe(true);
  for (const item of results.entries) {
    expect(item.path.startsWith(subtree)).toBe(true);
    expect(item.path.startsWith(sibling)).toBe(false);
  }
});

for (const folder of ['../', '%2e%2e%2f', 'C:\\Windows\\']) {
  test(`MEDIA-027-traversal-${folder} | AT-027 AC-027 | catalog traversal is rejected by the server`, async ({ app }) => {
    await app.reset('nested-media-catalog');
    expect((await app.act('OWNER', 'open-media-picker', { page: 'P-A' })).outcome).toBe('accepted');
    const before = picker(await app.observe('media-picker-state'));
    expect((await app.act('OWNER', 'browse-media-folder-direct', { folder })).outcome).toBe('denied');
    expect(picker(await app.observe('media-picker-state'))).toEqual(before);
    expect((await app.act('OWNER', 'browse-media-folder-direct', { folder: before.rootFolder })).outcome).toBe('accepted');
    expect(picker(await app.observe('media-picker-state')).currentFolder).toBe(before.rootFolder);
  });
}

test('MEDIA-027-rename | AT-027 AC-027 | renaming title does not move current or historical media', async ({ app }) => {
  await app.reset('nested-media-catalog');
  const before = pageMedia(await app.observe('page-media', { page: 'P-A' }));
  const history = await app.observe('historical-media-bindings', { page: 'P-A' });
  expect(Array.isArray(history)).toBe(true); expect(history.length).toBeGreaterThan(0);
  for (const item of history) { nonempty(item.versionId); nonempty(item.assetId); nonempty(item.path); checksum(item.sha256); }
  expect((await app.act('OWNER', 'rename-page', { page: 'P-A', base: before.revision, name: 'Новое название материала' })).outcome).toBe('accepted');
  const after = pageMedia(await app.observe('page-media', { page: 'P-A' }));
  expect(after.folder).toBe(before.folder); expect(after.placements).toEqual(before.placements);
  expect(await app.observe('historical-media-bindings', { page: 'P-A' })).toEqual(history);
});

test('MEDIA-028-shared | AT-028 AT-107 AC-028 AC-DTL-007 | replacement changes only selected material placement', async ({ app }) => {
  await app.reset('shared-media-replacement');
  const first = pageMedia(await app.observe('page-media', { page: 'P-A' }));
  const other = pageMedia(await app.observe('page-media', { page: 'P-B' }));
  const identifiers = await app.observe('media-fixture-identifiers'); nonempty(identifiers.otherAssetId);
  const original = asset(await app.observe('asset', { assetId: first.placements[0].assetId }));
  expect(other.placements.some(item => item.assetId === original.id)).toBe(true);
  const retained = await app.observe('retained-media-bindings');
  expect(Array.isArray(retained)).toBe(true);
  for (const kind of ['ordinary', 'stable', 'html']) expect(retained.some(item => item.kind === kind && item.assetId === original.id)).toBe(true);
  expect((await app.act('OWNER', 'replace-image-here', { page: 'P-A', placementId: first.placements[0].placementId, base: first.revision, assetId: identifiers.otherAssetId })).outcome).toBe('accepted');
  const changed = pageMedia(await app.observe('page-media', { page: 'P-A' }));
  expect(changed.placements.find(item => item.placementId === first.placements[0].placementId).assetId).toBe(identifiers.otherAssetId);
  expect(pageMedia(await app.observe('page-media', { page: 'P-B' }))).toEqual(other);
  expect(await app.observe('retained-media-bindings')).toEqual(retained);
  const old = asset(await app.observe('asset', { assetId: original.id }));
  expect(old.path).toBe(original.path); expect(old.bytes).toBe(original.bytes); expect(old.sha256).toBe(original.sha256);
});

test('MEDIA-028-placement | AT-028 AC-028 | repeated image in another placement of same page is not replaced', async ({ app }) => {
  await app.reset('shared-media-replacement');
  const before = pageMedia(await app.observe('page-media', { page: 'P-A' }));
  expect(before.placements.length).toBeGreaterThanOrEqual(2);
  const [selected, untouched] = before.placements;
  expect(selected.assetId).toBe(untouched.assetId);
  const identifiers = await app.observe('media-fixture-identifiers'); nonempty(identifiers.otherAssetId);
  expect((await app.act('OWNER', 'replace-image-here', { page: 'P-A', placementId: selected.placementId, base: before.revision, assetId: identifiers.otherAssetId })).outcome).toBe('accepted');
  const after = pageMedia(await app.observe('page-media', { page: 'P-A' }));
  expect(after.placements.find(item => item.placementId === selected.placementId).assetId).toBe(identifiers.otherAssetId);
  expect(after.placements.find(item => item.placementId === untouched.placementId)).toEqual(untouched);
});

for (const consumerKind of ['current-page', 'common-block', 'draft', 'ordinary', 'stable', 'html']) {
  test(`MEDIA-029-protected-${consumerKind} | AT-029 AC-029 | every retained consumer excludes its Asset from cleanup`, async ({ app }) => {
    await app.reset('media-cleanup-protected-consumer', { consumerKind });
    const identifiers = await app.observe('media-fixture-identifiers'); nonempty(identifiers.protectedAssetId);
    const protectedAsset = asset(await app.observe('asset', { assetId: identifiers.protectedAssetId }));
    expect(protectedAsset.references.some(reference => reference.kind === consumerKind)).toBe(true);
    const prepared = await preparedCleanup(app);
    expect(prepared.candidates.map(item => item.assetId)).not.toContain(protectedAsset.id);
    expect(asset(await app.observe('asset', { assetId: protectedAsset.id })).sha256).toBe(protectedAsset.sha256);
  });
}

test('MEDIA-029-late-reference | AT-029 AC-029 | current reference added after candidate list prevents physical deletion', async ({ app }) => {
  await app.reset('media-cleanup-orphan-candidate');
  const identifiers = await app.observe('media-fixture-identifiers'); nonempty(identifiers.orphanAssetId);
  const orphan = asset(await app.observe('asset', { assetId: identifiers.orphanAssetId })); expect(orphan.references).toHaveLength(0);
  const prepared = await preparedCleanup(app);
  expect(prepared.candidates.map(item => item.assetId)).toContain(orphan.id);
  const before = pageMedia(await app.observe('page-media', { page: 'P-A' }));
  expect((await app.act('OWNER', 'replace-image-here', { page: 'P-A', placementId: before.placements[0].placementId, base: before.revision, assetId: orphan.id })).outcome).toBe('accepted');
  const attached = asset(await app.observe('asset', { assetId: orphan.id }));
  expect(attached.references.some(reference => reference.kind === 'current-page' && reference.objectId === before.pageId)).toBe(true);
  const result = await app.act('OWNER', 'confirm-media-cleanup-direct', { confirmation: prepared.confirmation });
  expect(['accepted', 'denied', 'conflict']).toContain(result.outcome);
  const retained = asset(await app.observe('asset', { assetId: orphan.id }));
  expect(retained.sha256).toBe(orphan.sha256); expect(retained.bytes).toBe(orphan.bytes);
});

test('MEDIA-029-no-confirmation | AT-029 AC-029 | direct cleanup without current owner confirmation cannot delete', async ({ app }) => {
  await app.reset('media-cleanup-orphan-candidate');
  const identifiers = await app.observe('media-fixture-identifiers'); nonempty(identifiers.orphanAssetId);
  const before = asset(await app.observe('asset', { assetId: identifiers.orphanAssetId }));
  expect((await app.act('OWNER', 'confirm-media-cleanup-direct', {})).outcome).toBe('denied');
  expect(asset(await app.observe('asset', { assetId: before.id }))).toEqual(before);
});

test('MEDIA-029-employee | AT-029 AC-029 | same valid cleanup confirmation remains owner-only', async ({ app }) => {
  await app.reset('media-cleanup-orphan-candidate');
  const identifiers = await app.observe('media-fixture-identifiers'); nonempty(identifiers.orphanAssetId);
  const before = asset(await app.observe('asset', { assetId: identifiers.orphanAssetId }));
  const prepared = await preparedCleanup(app);
  expect(prepared.candidates.map(item => item.assetId)).toContain(before.id);
  expect((await app.act('S-EDIT', 'confirm-media-cleanup-direct', { confirmation: prepared.confirmation })).outcome).toBe('denied');
  expect(asset(await app.observe('asset', { assetId: before.id }))).toEqual(before);
  expect((await app.act('OWNER', 'confirm-media-cleanup-direct', { confirmation: prepared.confirmation })).outcome).toBe('accepted');
  expect((await app.observe('asset', { assetId: before.id })).exists).toBe(false);
});

test('MEDIA-029-positive | AT-029 AC-029 | only confirmed unreferenced working Asset is deleted', async ({ app }) => {
  await app.reset('media-cleanup-orphan-candidate');
  const identifiers = await app.observe('media-fixture-identifiers');
  nonempty(identifiers.orphanAssetId); nonempty(identifiers.protectedAssetId);
  const protectedAsset = asset(await app.observe('asset', { assetId: identifiers.protectedAssetId }));
  const outside = await app.observe('archive-and-backup-media-integrity');
  checksum(outside.archiveDigest); checksum(outside.backupDigest);
  const prepared = await preparedCleanup(app);
  expect(prepared.candidates.map(item => item.assetId)).toContain(identifiers.orphanAssetId);
  expect(prepared.candidates.map(item => item.assetId)).not.toContain(protectedAsset.id);
  expect((await app.act('OWNER', 'confirm-media-cleanup-direct', { confirmation: prepared.confirmation })).outcome).toBe('accepted');
  expect((await app.observe('asset', { assetId: identifiers.orphanAssetId })).exists).toBe(false);
  expect(asset(await app.observe('asset', { assetId: protectedAsset.id }))).toEqual(protectedAsset);
  expect(await app.observe('archive-and-backup-media-integrity')).toEqual(outside);
});
