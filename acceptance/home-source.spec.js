import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver(); try { await use(app); } finally { await app.close(); }
} });
test.use({ javaScriptEnabled: false, serviceWorkers: 'block' });
test.beforeEach(async ({ context }) => {
  await context.route('**/*', route => route.abort());
  await context.routeWebSocket('**/*', socket => socket.close());
});
const required = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
function numericPrice(text) {
  // This fixture uses one numeric amount, not a range/text/from price. Parse DOM text independently of DB.
  const match = required(text).trim().match(/^((?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[,.]\d{1,2})?)\s*(?:₽|руб\.?|р\.?)?$/iu);
  expect(Boolean(match)).toBe(true);
  return Number(match[1].replace(/[ \u00a0\u202f]/gu, '').replace(',', '.'));
}
async function setup(app, reserve = false) {
  if (reserve) {
    const permit = await app.inspectInfrastructureAdmission();
    expect(permit.arc10Verified).toBe(true); expect(permit.isolatedInfrastructure).toBe(true);
    required(permit.reviewedEvidenceId); expect(permit.capabilities).toContain('fallback-control-v1');
  }
  await app.reset(reserve ? 'home-source-night-ready' : 'home-source-single-published');
  const fixture = await app.observe('home-source-fixture');
  for (const field of ['sourcePageId', 'sourceRowId', 'homeItemId', 'assetId', 'sourceUrl', 'mainCanary', 'itemLabel']) required(fixture[field]);
  for (const field of ['main', 'item', 'price', 'priceTab', 'priceBlock', 'technicalTokens']) required(fixture.selectors[field]);
  expect(fixture.itemLabel).toBe('MAIN-SOURCE-SYNTHETIC-LABEL');
  return fixture;
}
async function item(app, fixture) {
  const value = await app.observe('home-source-item', { itemId: fixture.homeItemId });
  for (const key of ['id', 'label', 'href', 'priceText', 'assetId', 'sourcePageId', 'sourceRowId']) required(value[key]);
  expect(value.id).toBe(fixture.homeItemId); expect(value.sourcePageId).toBe(fixture.sourcePageId);
  expect(value.sourceRowId).toBe(fixture.sourceRowId); expect(typeof value.visible).toBe('boolean');
  return value;
}
const presentation = value => Object.fromEntries(['id', 'label', 'href', 'priceText', 'assetId', 'visible'].map(key => [key, value[key]]));
async function render(app, page, fixture, mode = 'normal') {
  const response = await app.observe('home-source-public-response', { mode });
  expect(response.status).toBe(200); required(response.body);
  const actual = await page.evaluate(({ html, selectors }) => {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const main = doc.querySelector(selectors.main); if (!main) throw new Error('HOME_MAIN_NOT_FOUND');
    const clean = value => value.replace(/\s+/gu, ' ').trim();
    const cards = [...main.querySelectorAll(selectors.item)];
    return { text: clean(main.textContent), cards: cards.map(card => ({ text: clean(card.textContent),
      priceText: clean(card.querySelector(selectors.price)?.textContent || ''),
      links: [...card.querySelectorAll('a[href]')].map(node => ({ text: clean(node.textContent), href: node.getAttribute('href') })),
      images: [...card.querySelectorAll('img')].map(node => ({ src: node.getAttribute('src'), alt: node.getAttribute('alt') })) })),
      tabCount: main.querySelectorAll(selectors.priceTab).length, blockCount: main.querySelectorAll(selectors.priceBlock).length,
      technicalTokenCount: doc.querySelectorAll(selectors.technicalTokens).length };
  }, { html: response.body, selectors: fixture.selectors });
  expect(actual.text).toContain(fixture.mainCanary);
  return actual;
}
function visible(actual, fixture) {
  expect(actual.cards).toHaveLength(1); expect(actual.cards[0].text).toContain(fixture.itemLabel);
  expect(actual.cards[0].links.some(link => link.href === fixture.sourceUrl)).toBe(true);
  expect(actual.cards[0].images.length).toBeGreaterThan(0);
  expect(actual.tabCount).toBeGreaterThan(0); expect(actual.blockCount).toBeGreaterThan(0);
}
function hidden(actual) { expect(actual.cards).toHaveLength(0); expect(actual.tabCount).toBe(0); expect(actual.blockCount).toBe(0); }
async function remove(app, fixture) {
  const prepared = await app.act('OWNER', 'prepare-delete-page', { page: 'P-PRICE-SOURCE' });
  expect(prepared.outcome).toBe('accepted'); expect(prepared.confirmation.pageId).toBe(fixture.sourcePageId);
  expect(prepared.confirmation.url).toBe(fixture.sourceUrl);
  expect((await app.act('OWNER', 'confirm-page-delete-direct', { page: 'P-PRICE-SOURCE', confirmation: prepared.confirmation, passwordRef: 'OWNER-CURRENT-SECRET' })).outcome).toBe('accepted');
  expect((await app.observe('home-source-record', { pageId: fixture.sourcePageId })).exists).toBe(false);
  const response = await app.observe('home-source-route-response', { path: fixture.sourceUrl });
  expect(response.status).toBe(404);
}
async function unpublish(app) {
  const source = await app.observe('page', { page: 'P-PRICE-SOURCE' });
  expect((await app.act('OWNER', 'set-page-publication', { page: 'P-PRICE-SOURCE', base: source.revision, published: false })).outcome).toBe('accepted');
  const response = await app.observe('public-page-response', { page: 'P-PRICE-SOURCE' });
  expect(response.status).toBe(200); expect(response.body.trim()).toBe('');
}

test('HOME-SOURCE-price-update | AT-012 AC-012 | active source updates the same linked price', async ({ app, page }) => {
  const fixture = await setup(app), before = await item(app, fixture), original = await render(app, page, fixture);
  visible(original, fixture); expect(numericPrice(original.cards[0].priceText)).toBe(1000);
  const row = await app.observe('home-source-price-row', { rowId: fixture.sourceRowId });
  expect(Number(row.amount)).toBe(1000);
  expect((await app.act('OWNER', 'update-home-source-price-direct', { rowId: fixture.sourceRowId, base: row.revision, amount: '1300' })).outcome).toBe('accepted');
  expect(Number((await app.observe('home-source-price-row', { rowId: fixture.sourceRowId })).amount)).toBe(1300);
  const after = await item(app, fixture), actual = await render(app, page, fixture); visible(actual, fixture);
  expect(after.id).toBe(before.id); expect(after.href).toBe(before.href); expect(after.assetId).toBe(before.assetId);
  expect(actual.cards[0].priceText).not.toBe(original.cards[0].priceText);
  expect(numericPrice(actual.cards[0].priceText)).toBe(1300);
});

for (const wasHidden of [false, true]) {
  test(`HOME-SOURCE-delete-${wasHidden ? 'hidden' : 'visible'} | AT-012 AT-411 AC-012 AC-PRO-011 | deletion preserves actual main state and URL reuse never rebinds it`, async ({ app, page }) => {
    const fixture = await setup(app); visible(await render(app, page, fixture), fixture);
    if (wasHidden) { await unpublish(app); hidden(await render(app, page, fixture)); }
    const before = await item(app, fixture), rendered = await render(app, page, fixture);
    expect(before.visible).toBe(!wasHidden);
    await remove(app, fixture);
    expect(presentation(await item(app, fixture))).toEqual(presentation(before));
    expect(await render(app, page, fixture)).toEqual(rendered);
    const created = await app.act('OWNER', 'create-page', { parent: 'P-PRICE-PARENT', name: fixture.itemLabel, requestedPath: fixture.sourceUrl });
    expect(created.outcome).toBe('accepted'); required(created.pageId); expect(created.pageId).not.toBe(fixture.sourcePageId);
    expect((await app.act('OWNER', 'publish-created-page', { pageId: created.pageId })).outcome).toBe('accepted');
    const replacement = await app.observe('home-source-replacement', { pageId: created.pageId });
    expect(replacement.id).toBe(created.pageId); expect(replacement.url).toBe(fixture.sourceUrl); expect(replacement.published).toBe(true);
    // A real new price differs, so accidental rebinding is observable beyond a URL/name match.
    expect((await app.act('OWNER', 'create-replacement-price-direct', { pageId: created.pageId, amount: '9900' })).outcome).toBe('accepted');
    expect(Number((await app.observe('home-source-replacement', { pageId: created.pageId })).amount)).toBe(9900);
    expect(presentation(await item(app, fixture))).toEqual(presentation(before));
    expect(await render(app, page, fixture)).toEqual(rendered);
  });
}

test('HOME-SOURCE-hide-return | AT-012 AC-012 | unpublishing hides the last price but republishing the same source restores the link', async ({ app, page }) => {
  const fixture = await setup(app), original = await render(app, page, fixture); visible(original, fixture);
  await unpublish(app); hidden(await render(app, page, fixture)); expect((await item(app, fixture)).visible).toBe(false);
  const current = await app.observe('page', { page: 'P-PRICE-SOURCE' });
  expect((await app.act('OWNER', 'set-page-publication', { page: 'P-PRICE-SOURCE', base: current.revision, published: true })).outcome).toBe('accepted');
  expect((await item(app, fixture)).visible).toBe(true);
  expect(await render(app, page, fixture)).toEqual(original);
});

test('HOME-SOURCE-asset-retention | AT-411 AC-PRO-011 | current main keeps the deleted source image through confirmed cleanup', async ({ app, page }) => {
  const fixture = await setup(app), original = await render(app, page, fixture); visible(original, fixture);
  const asset = await app.observe('asset', { assetId: fixture.assetId }); expect(asset.exists).toBe(true); required(asset.sha256);
  required(fixture.orphanAssetId); expect(fixture.orphanAssetId).not.toBe(fixture.assetId);
  expect((await app.observe('asset', { assetId: fixture.orphanAssetId })).exists).toBe(true);
  const originalImage = await app.observe('home-source-image-response', { assetId: fixture.assetId });
  expect(originalImage.status).toBe(200); expect(originalImage.sha256).toBe(asset.sha256); expect(originalImage.bytes).toBe(asset.bytes);
  await remove(app, fixture);
  const prepared = await app.act('OWNER', 'prepare-media-cleanup');
  expect(prepared.outcome).toBe('accepted'); expect(prepared.candidates.length).toBeGreaterThan(0);
  expect(prepared.candidates.map(candidate => candidate.assetId)).not.toContain(fixture.assetId);
  expect(prepared.candidates.map(candidate => candidate.assetId)).toContain(fixture.orphanAssetId);
  expect((await app.act('OWNER', 'confirm-media-cleanup-direct', { confirmation: prepared.confirmation })).outcome).toBe('accepted');
  expect((await app.observe('asset', { assetId: fixture.orphanAssetId })).exists).toBe(false);
  const after = await app.observe('asset', { assetId: fixture.assetId });
  expect(after.exists).toBe(true); expect(after.sha256).toBe(asset.sha256); expect(after.bytes).toBe(asset.bytes);
  expect(after.references.some(reference => reference.objectId === fixture.homeItemId)).toBe(true);
  const image = await app.observe('home-source-image-response', { assetId: fixture.assetId });
  expect(image.status).toBe(200); expect(image.sha256).toBe(originalImage.sha256); expect(image.bytes).toBe(originalImage.bytes);
  expect(await render(app, page, fixture)).toEqual(original);
});

async function control(app, action, args) { expect((await app.control(action, args)).outcome).toBe('accepted'); }
for (const component of ['application', 'database']) {
  test(`HOME-SOURCE-night-${component} | AT-012 AT-412 AC-012 AC-PRO-012 | night main remains available while deleted own URL stays404 without DB restore`, async ({ app, page }) => {
    const fixture = await setup(app, true), initial = await render(app, page, fixture); visible(initial, fixture);
    const night = await app.observe('home-source-night-proof');
    required(night.setId); expect(night.createdByActualBuild).toBe(true); expect(night.validationState).toBe('READY');
    expect(night.sourcePageId).toBe(fixture.sourcePageId);
    await remove(app, fixture);
    const beforeFailure = await app.observe('home-source-business-state');
    expect(beforeFailure.sourceExists).toBe(false);
    await control(app, 'stop-isolated-component', { component });
    for (let n = 0; n < 2; n++) {
      const before = await app.observe('fallback-control-state');
      await control(app, 'advance-infrastructure-time', { seconds: 300 });
      await expect.poll(async () => (await app.observe('fallback-control-state')).local.completedChecks, { timeout: 10_000 }).toBe(before.local.completedChecks + 1);
    }
    await expect.poll(async () => (await app.observe('fallback-control-state')).confirmedMode, { timeout: 10_000 }).toBe('reserve');
    const actual = await render(app, page, fixture, 'reserve'); visible(actual, fixture);
    expect(actual.cards).toEqual(initial.cards); expect(actual.technicalTokenCount).toBe(0);
    const route = await app.observe('home-source-route-response', { path: fixture.sourceUrl }); expect(route.status).toBe(404);
    const served = await app.observe('home-source-served-set'); expect(served.setId).toBe(night.setId);
    await control(app, 'start-isolated-component', { component });
    expect(await app.observe('home-source-business-state')).toEqual(beforeFailure);
    expect((await app.observe('home-source-record', { pageId: fixture.sourcePageId })).exists).toBe(false);
  });
}
