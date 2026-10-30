import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver(); try { await use(app); } finally { await app.close(); }
} });
test.beforeEach(async ({ context }) => {
  await context.route('**/*', route => route.abort());
  await context.routeWebSocket('**/*', socket => socket.close());
});
async function paragraph(page, source, expected) {
  expect(typeof source).toBe('string'); expect(source.length).toBeGreaterThan(0);
  const found = await page.evaluate(({ source, expected }) => {
    const document = new DOMParser().parseFromString(source, 'text/html');
    return [...document.querySelectorAll('p')].some(node => node.textContent.trim() === expected);
  }, { source, expected });
  expect(found).toBe(true);
}
function id(value) { expect(typeof value === 'string' && value.length > 0).toBe(true); }
function block(value, kind) {
  expect(value.kind).toBe(kind);
  for (const name of ['id', 'revision', 'draftRevision', 'currentVersionId']) id(value[name]);
  expect(typeof value.currentHtml).toBe('string'); expect(value.currentHtml.length).toBeGreaterThan(0);
  expect(typeof value.draftHtml).toBe('string'); expect(Array.isArray(value.versions)).toBe(true);
  expect(value.versions.length).toBeGreaterThan(0);
  for (const item of value.versions) { id(item.id); expect(typeof item.html).toBe('string'); }
  expect(value.versions.some(item => item.id === value.currentVersionId)).toBe(true);
  return value;
}
async function current(app, kind) { return block(await app.observe('shared-block', { kind }), kind); }
function same(after, before, fields = ['id', 'revision', 'draftRevision', 'currentVersionId', 'currentHtml', 'draftHtml', 'versions']) {
  for (const field of fields) { expect(after).toHaveProperty(field); expect(before).toHaveProperty(field); expect(after[field]).toEqual(before[field]); }
}
async function publicPage(app, options = {}) {
  const actual = await app.observe('public-with-shared-blocks', { page: 'P-ONE', ...options });
  expect(Number.isInteger(actual.status)).toBe(true); expect(typeof actual.body).toBe('string');
  if (actual.status === 200) for (const field of ['headerHtml', 'footerHtml', 'pageText', 'etag']) id(actual[field]);
  return actual;
}
const html = (kind, value) => `<${kind}><p>${value}</p></${kind}>`;

for (const kind of ['header', 'footer']) {
  test(`BLOCK-owner-only-${kind} | AT-013 AC-013 | valid same-handler block publication is owner-only`, async ({ app, page }) => {
    await app.reset('shared-blocks-independent-history'); const before = await current(app, kind);
    const value = html(kind, `BLOCK-NEW-${kind}`); expect(before.currentHtml).not.toBe(value);
    const args = { kind, base: before.revision, html: value };
    expect((await app.act('S-EDIT', 'publish-shared-block-direct', args)).outcome).toBe('denied');
    same(await current(app, kind), before);
    expect((await app.act('OWNER', 'publish-shared-block-direct', args)).outcome).toBe('accepted');
    const after = await current(app, kind); await paragraph(page, after.currentHtml, `BLOCK-NEW-${kind}`);
    expect(after.currentHtml).not.toBe(before.currentHtml);
    expect(after.revision).not.toBe(before.revision); expect(after.versions).toHaveLength(before.versions.length + 1);
  });

  for (const actor of ['S-EDIT', 'VISITOR']) {
    test(`BLOCK-private-history-${kind}-${actor} | AT-115 AC-DTL-015 | assigned page does not grant block history`, async ({ app }) => {
      await app.reset('shared-blocks-independent-history');
      const allowed = await app.act('OWNER', 'read-shared-block-history-direct', { kind });
      expect(allowed.outcome).toBe('accepted'); expect(allowed.body).toContain(`BLOCK-HISTORY-PRIVATE-${kind}`);
      const denied = await app.act(actor, 'read-shared-block-history-direct', { kind });
      expect(denied.outcome).toBe('denied'); expect(denied.body).not.toContain(`BLOCK-HISTORY-PRIVATE-${kind}`);
    });
  }

  test(`BLOCK-draft-${kind} | AT-116 AC-DTL-016 | saving the separate draft does not publish it on pages`, async ({ app, page }) => {
    await app.reset('shared-blocks-independent-history'); const before = await current(app, kind), publicBefore = await publicPage(app);
    expect(publicBefore.status).toBe(200); const value = html(kind, `BLOCK-DRAFT-ONLY-${kind}`);
    expect(before.draftHtml).not.toBe(value);
    expect((await app.act('OWNER', 'save-shared-block-draft', { kind, base: before.draftRevision, html: value })).outcome).toBe('accepted');
    const after = await current(app, kind); await paragraph(page, after.draftHtml, `BLOCK-DRAFT-ONLY-${kind}`); expect(after.draftRevision).not.toBe(before.draftRevision);
    same(after, before, ['id', 'revision', 'currentVersionId', 'currentHtml', 'versions']);
    const actual = await publicPage(app); expect(actual.status).toBe(200);
    for (const field of ['headerHtml', 'footerHtml', 'pageText']) expect(actual[field]).toBe(publicBefore[field]);
    expect(actual.body).not.toContain(`BLOCK-DRAFT-ONLY-${kind}`);
  });

  test(`BLOCK-apply-${kind} | AT-116 AC-DTL-016 | explicit current publication creates one block version only`, async ({ app, page }) => {
    await app.reset('shared-blocks-independent-history'); const before = await current(app, kind);
    const otherKind = kind === 'header' ? 'footer' : 'header', otherBefore = await current(app, otherKind);
    const pageBefore = await app.observe('page', { page: 'P-ONE' });
    id(pageBefore.revision); expect(Array.isArray(pageBefore.versions)).toBe(true); expect(pageBefore.versions.length).toBeGreaterThan(0);
    const value = html(kind, `BLOCK-APPLIED-${kind}`); expect(before.currentHtml).not.toBe(value);
    expect((await app.act('OWNER', 'publish-shared-block-direct', { kind, base: before.revision, html: value })).outcome).toBe('accepted');
    const after = await current(app, kind); await paragraph(page, after.currentHtml, `BLOCK-APPLIED-${kind}`); expect(after.versions).toHaveLength(before.versions.length + 1);
    expect(after.currentVersionId).not.toBe(before.currentVersionId);
    same(await current(app, otherKind), otherBefore);
    const pageAfter = await app.observe('page', { page: 'P-ONE' });
    expect(pageAfter.revision).toBe(pageBefore.revision); expect(pageAfter.versions).toEqual(pageBefore.versions);
    const rendered = await publicPage(app); expect(rendered.status).toBe(200); await paragraph(page, rendered[`${kind}Html`], `BLOCK-APPLIED-${kind}`);
  });

  test(`BLOCK-concurrent-${kind} | AT-017 AT-116 AC-017 AC-DTL-016 | two owner sessions cannot overwrite the same old block revision`, async ({ app, page }) => {
    await app.reset('shared-blocks-independent-history'); const before = await current(app, kind);
    const values = [html(kind, 'BLOCK-RACE-A'), html(kind, 'BLOCK-RACE-B')];
    for (const value of values) expect(before.currentHtml).not.toBe(value);
    const results = await Promise.all(['OWNER', 'OWNER-SECOND'].map((actor, n) => app.act(actor, 'publish-shared-block-direct', { kind, base: before.revision, html: values[n] })));
    expect(results.map(result => result.outcome).sort()).toEqual(['accepted', 'conflict']);
    const after = await current(app, kind);
    await paragraph(page, after.currentHtml, ['BLOCK-RACE-A', 'BLOCK-RACE-B'][results.findIndex(result => result.outcome === 'accepted')]);
    expect(after.versions).toHaveLength(before.versions.length + 1);
    expect(after.revision).not.toBe(before.revision);
  });

  test(`BLOCK-compare-restore-${kind} | AT-115 AC-DTL-015 | comparison shows historical literal contact before explicit block application`, async ({ app }) => {
    await app.reset('shared-blocks-independent-history'); const before = await current(app, kind);
    const otherKind = kind === 'header' ? 'footer' : 'header', otherBefore = await current(app, otherKind);
    const historical = before.versions.find(item => item.id !== before.currentVersionId && item.html.includes('+70000000001'));
    expect(historical).toBeTruthy(); expect(before.currentHtml).not.toBe(historical.html);
    const compare = await app.act('OWNER', 'compare-shared-block-version', { kind, version: historical.id });
    expect(compare.outcome).toBe('accepted'); expect(compare.comparison.historicalHtml).toBe(historical.html);
    expect(compare.comparison.literalContactValues).toContain('+70000000001');
    same(await current(app, kind), before);
    const prepared = await app.act('OWNER', 'prepare-shared-block-restore', { kind, version: historical.id, base: before.revision });
    expect(prepared.outcome).toBe('accepted'); expect(prepared.confirmation).toBeTruthy();
    same(await current(app, kind), before, ['id', 'revision', 'currentVersionId', 'currentHtml', 'versions']);
    same(await current(app, otherKind), otherBefore);
    expect((await app.act('OWNER', 'apply-shared-block-version', { kind, version: historical.id, base: before.revision, confirmation: prepared.confirmation })).outcome).toBe('accepted');
    const after = await current(app, kind); expect(after.currentHtml).toBe(historical.html);
    expect(after.versions).toHaveLength(before.versions.length + 1); expect(after.currentVersionId).not.toBe(historical.id);
    expect(after.versions.find(item => item.id === historical.id)).toEqual(historical);
    same(await current(app, otherKind), otherBefore);
  });

  test(`BLOCK-validator-${kind} | AT-050 AT-116 AC-050 AC-DTL-016 | old validator cannot return304 for a newly published shared block`, async ({ app, page }) => {
    await app.reset('shared-blocks-independent-history'); const before = await current(app, kind), publicBefore = await publicPage(app);
    expect(publicBefore.status).toBe(200);
    const value = html(kind, `BLOCK-VALIDATOR-NEW-${kind}`); expect(before.currentHtml).not.toBe(value);
    expect((await app.act('OWNER', 'publish-shared-block-direct', { kind, base: before.revision, html: value })).outcome).toBe('accepted');
    const actual = await publicPage(app, { ifNoneMatch: publicBefore.etag });
    expect(actual.status).toBe(200); expect(actual.etag).not.toBe(publicBefore.etag); await paragraph(page, actual[`${kind}Html`], `BLOCK-VALIDATOR-NEW-${kind}`);
  });
}

test('BLOCK-page-restore | AT-022 AT-115 AC-022 AC-DTL-015 | restoring page text retains the newer current Header and Footer', async ({ app, page }) => {
  await app.reset('page-history-restore');
  const before = await app.observe('page', { page: 'P-ASSIGNED' }); id(before.revision);
  for (const kind of ['header', 'footer']) {
    const initial = await current(app, kind), value = html(kind, `BLOCK-CURRENT-AFTER-PAGE-VERSION-${kind}`);
    expect(initial.currentHtml).not.toBe(value);
    expect((await app.act('OWNER', 'publish-shared-block-direct', { kind, base: initial.revision, html: value })).outcome).toBe('accepted');
    await paragraph(page, (await current(app, kind)).currentHtml, `BLOCK-CURRENT-AFTER-PAGE-VERSION-${kind}`);
  }
  const header = await current(app, 'header'), footer = await current(app, 'footer');
  const prepared = await app.act('S-EDIT', 'prepare-page-version-restore', { page: 'P-ASSIGNED', version: 'V-OLD' });
  expect(prepared.outcome).toBe('accepted'); expect(prepared.preparation).toBeTruthy();
  expect((await app.act('S-EDIT', 'stage-page-version-restore', { page: 'P-ASSIGNED', preparation: prepared.preparation, confirmInputReplacement: true })).outcome).toBe('ui-observed');
  expect((await app.act('S-EDIT', 'save-open-editor', { page: 'P-ASSIGNED', base: before.revision })).outcome).toBe('accepted');
  expect((await app.observe('page', { page: 'P-ASSIGNED' })).publicText).toBe('HISTORICAL-ALLOWED-TEXT');
  same(await current(app, 'header'), header); same(await current(app, 'footer'), footer);
});

test('BLOCK-not-public-pages | AT-013 AC-013 | shared records have no independent public page or SEO state', async ({ app }) => {
  await app.reset('shared-blocks-independent-history');
  const inventory = await app.observe('shared-block-public-classification');
  expect(inventory.records).toHaveLength(2);
  expect(inventory.records.map(item => item.kind).sort()).toEqual(['footer', 'header']);
  for (const record of inventory.records) {
    id(record.id); expect(record.isPage).toBe(false); expect(record.publicUrl).toBe(null);
    expect(record.hasPageSeo).toBe(false); expect(record.indexedAsPage).toBe(false);
  }
});
