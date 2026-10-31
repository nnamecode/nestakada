import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';
const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver(); try { await use(app); } finally { await app.close(); }
} });
test.use({ javaScriptEnabled: false, serviceWorkers: 'block' });
test.beforeEach(async ({ context }) => {
  await context.route('**/*', route => route.abort()); await context.routeWebSocket('**/*', socket => socket.close());
});
const required = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
function money(text) {
  const match = required(text).trim().match(/^(от\s+)?((?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[,.]\d{1,2})?)\s*(?:₽|руб\.?|р\.?)?$/iu);
  expect(Boolean(match)).toBe(true);
  const [whole, fraction = ''] = match[2].replace(/[ \u00a0\u202f]/gu, '').replace(',', '.').split('.');
  return { kopecks: BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0')), from: Boolean(match[1]) };
}
async function source(app) {
  const value = await app.observe('price-home-source'); required(value.id); required(value.revision);
  expect(value.published).toBe(true); expect(value.rows.length).toBeGreaterThan(0);
  return value;
}
async function config(app) {
  const value = await app.observe('home-price-configuration'); required(value.revision); expect(value.items.length).toBeGreaterThan(0); return value;
}
async function setup(app, scenario) {
  await app.reset('price-home-linked', { scenario }); const fixture = await app.observe('price-home-fixture');
  expect(fixture.scenario).toBe(scenario); required(fixture.sourcePageId); required(fixture.selectedRowId);
  for (const key of ['row', 'label', 'priceParts']) required(fixture.selectors[key]);
  const actual = await source(app); expect(actual.id).toBe(fixture.sourcePageId);
  expect(actual.rows.some(row => row.id === fixture.selectedRowId)).toBe(true);
  return fixture;
}
async function rendered(app, page, fixture) {
  const response = await app.observe('price-home-http'); expect(response.status).toBe(200); required(response.body);
  return page.evaluate(({ html, selectors }) => {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const clean = value => (value || '').replace(/\s+/gu, ' ').trim();
    return [...doc.querySelectorAll(selectors.row)].map(row => ({ label: clean(row.querySelector(selectors.label)?.textContent),
      prices: [...row.querySelectorAll(selectors.priceParts)].map(node => clean(node.textContent)) }));
  }, { html: response.body, selectors: fixture.selectors });
}
function one(rows) { expect(rows).toHaveLength(1); expect(rows[0].prices).toHaveLength(1); return rows[0].prices[0]; }
async function update(app, fixture, cell) {
  const before = await source(app);
  expect((await app.act('OWNER', 'home-price-update-cell', { page: 'P-HOME-PRICE', rowId: fixture.selectedRowId, base: before.revision, cell })).outcome).toBe('accepted');
  const after = await source(app); expect(after.revision).not.toBe(before.revision);
  expect(after.rows.find(row => row.id === fixture.selectedRowId).cells[0]).toEqual(cell);
}

test('PRICE-HOME-decimal | AT-105 AT-012 AC-DTL-005 AC-012 | linked monetary value keeps an exact kopeck without binary rounding', async ({ app, page }) => {
  const fixture = await setup(app, 'single-number');
  expect(money(one(await rendered(app, page, fixture))).kopecks).toBe(100000n);
  await update(app, fixture, { kind: 'money', amount: '0.01', from: false });
  expect(money(one(await rendered(app, page, fixture)))).toEqual({ kopecks: 1n, from: false });
});
test('PRICE-HOME-zero | AT-105 AC-DTL-005 | an explicit zero remains a monetary value on the main page', async ({ app, page }) => {
  const fixture = await setup(app, 'single-number');
  await update(app, fixture, { kind: 'money', amount: '0', from: false });
  expect(money(one(await rendered(app, page, fixture)))).toEqual({ kopecks: 0n, from: false });
});
for (const kind of ['empty', 'text']) {
  test(`PRICE-HOME-nonnumeric-${kind} | AT-105 AC-DTL-005 | missing monetary value is not zero or a number extracted from descriptive text`, async ({ app, page }) => {
    const fixture = await setup(app, 'single-number');
    const cell = kind === 'empty' ? { kind: 'empty' } : { kind: 'text', text: 'R15, код 24, стоимость после осмотра' };
    await update(app, fixture, cell);
    const text = one(await rendered(app, page, fixture)).toLowerCase();
    expect(['уточняйте', 'после осмотра']).toContain(text);
    expect(text).not.toContain('по прайсу'); expect(text).not.toMatch(/\d/u);
  });
}
test('PRICE-HOME-from | AT-105 AC-DTL-005 | source from marker is retained with the linked amount', async ({ app, page }) => {
  const fixture = await setup(app, 'single-number');
  await update(app, fixture, { kind: 'money', amount: '1750', from: true });
  expect(money(one(await rendered(app, page, fixture)))).toEqual({ kopecks: 175000n, from: true });
});
test('PRICE-HOME-wash-six-classes | AT-105 AC-DTL-005 | first eight matrix rows use the minimum across six actual class cells', async ({ app, page }) => {
  const fixture = await setup(app, 'wash-six-classes'), current = await source(app);
  const minima = [300, 500, 800, 1700, 1600, 2300, 400, 500];
  expect(current.rows).toHaveLength(9);
  for (let i = 0; i < 8; i++) {
    expect(current.rows[i].cells).toHaveLength(6);
    // Synthetic classes intentionally put the minimum outside the first column.
    expect(current.rows[i].cells.map(cell => money(cell.amount).kopecks)).toEqual(
      [minima[i] + 200, minima[i] + 100, minima[i], minima[i] + 300, minima[i] + 400, minima[i] + 500].map(value => BigInt(value) * 100n));
  }
  const actual = await rendered(app, page, fixture); expect(actual).toHaveLength(8);
  for (let i = 0; i < 8; i++) {
    expect(actual[i].label).toBe(current.rows[i].label); expect(actual[i].prices).toHaveLength(1);
    expect(money(actual[i].prices[0])).toEqual({ kopecks: BigInt(minima[i]) * 100n, from: true });
  }
});
test('PRICE-HOME-four-wheel-complex | AT-105 AC-DTL-005 | R15–R22 show the four-wheel complex, not a single operation or invented multiplication', async ({ app, page }) => {
  const fixture = await setup(app, 'tire-complex'), current = await source(app), actual = await rendered(app, page, fixture);
  expect(current.rows).toHaveLength(8); expect(actual).toHaveLength(8);
  for (let i = 0; i < 8; i++) {
    const complex = 2400 + i * 200;
    expect(current.rows[i].label).toBe(`R${15 + i}`);
    expect(current.rows[i].cells.map(cell => money(cell.amount).kopecks)).toEqual([10000n, BigInt(complex) * 100n]);
    expect(actual[i].label).toBe(current.rows[i].label); expect(actual[i].prices).toHaveLength(1);
    expect(money(actual[i].prices[0]).kopecks).toBe(BigInt(complex) * 100n);
  }
});
test('PRICE-HOME-axis-pair | AT-105 AC-DTL-005 | one and two axes retain the source column order', async ({ app, page }) => {
  const fixture = await setup(app, 'axis-pair'), current = await source(app), actual = await rendered(app, page, fixture);
  expect(current.rows[0].cells.map(cell => money(cell.amount).kopecks)).toEqual([170000n, 230000n]);
  expect(actual).toHaveLength(1); expect(actual[0].prices.map(text => money(text).kopecks)).toEqual([170000n, 230000n]);
});
test('PRICE-HOME-stable-row-id | AT-105 AC-DTL-005 | row rename keeps identity while a new row with the old label cannot steal the link', async ({ app, page }) => {
  const fixture = await setup(app, 'single-number'), before = await source(app), configuration = await config(app);
  const oldLabel = before.rows.find(row => row.id === fixture.selectedRowId).label;
  expect((await app.act('OWNER', 'home-price-rename-row', { page: 'P-HOME-PRICE', rowId: fixture.selectedRowId, base: before.revision, label: 'RENAMED-SYNTHETIC-SOURCE' })).outcome).toBe('accepted');
  const renamed = await source(app); expect(renamed.rows.find(row => row.id === fixture.selectedRowId).label).toBe('RENAMED-SYNTHETIC-SOURCE');
  const created = await app.act('OWNER', 'home-price-create-row', { page: 'P-HOME-PRICE', base: renamed.revision, label: oldLabel, cell: { kind: 'money', amount: '1', from: false } });
  expect(created.outcome).toBe('accepted'); required(created.rowId); expect(created.rowId).not.toBe(fixture.selectedRowId);
  const other = (await source(app)).rows.find(row => row.id === created.rowId); expect(other.label).toBe(oldLabel); expect(money(other.cells[0].amount).kopecks).toBe(100n);
  await update(app, fixture, { kind: 'money', amount: '1300', from: false });
  expect(money(one(await rendered(app, page, fixture))).kopecks).toBe(130000n);
  const after = await config(app);
  expect(after.items.map(item => ({ id: item.id, sourcePageId: item.sourcePageId, sourceRowId: item.sourceRowId })))
    .toEqual(configuration.items.map(item => ({ id: item.id, sourcePageId: item.sourcePageId, sourceRowId: item.sourceRowId })));
});
test('PRICE-HOME-owner-draft | AT-105 AT-012 AC-DTL-005 AC-012 | private price draft never becomes the public linked amount', async ({ app, page }) => {
  const fixture = await setup(app, 'single-number'), before = await source(app), publicBefore = await rendered(app, page, fixture);
  expect((await app.act('OWNER', 'home-price-save-draft', { page: 'P-HOME-PRICE', rowId: fixture.selectedRowId, base: before.revision, cell: { kind: 'money', amount: '9999', from: false } })).outcome).toBe('accepted');
  const actual = await source(app); expect(money(actual.draftRows.find(row => row.id === fixture.selectedRowId).cells[0].amount).kopecks).toBe(999900n);
  expect(actual.rows).toEqual(before.rows); expect(await rendered(app, page, fixture)).toEqual(publicBefore);
});
test('PRICE-HOME-settings-owner-only | AT-105 AT-016 AC-DTL-005 AC-016 | employee price grant does not grant main-page source selection', async ({ app, page }) => {
  const fixture = await setup(app, 'owner-selection'), before = await config(app), publicBefore = await rendered(app, page, fixture);
  const current = await source(app), grant = await app.observe('price-home-employee-grant');
  expect(grant.canEditAssignedPrice).toBe(true); required(fixture.otherRowId);
  // Real positive price write proves the employee is not simply blocked everywhere.
  expect((await app.act('S-PRICE', 'home-price-update-cell', { page: 'P-HOME-PRICE', rowId: fixture.otherRowId, base: current.revision, cell: { kind: 'money', amount: '12', from: false } })).outcome).toBe('accepted');
  const currentConfig = await config(app);
  expect(currentConfig.items).toEqual(before.items);
  const args = { itemId: currentConfig.items[0].id, sourceRowId: fixture.otherRowId, base: currentConfig.revision };
  expect((await app.act('S-PRICE', 'home-price-select-source', args)).outcome).toBe('denied');
  expect(await config(app)).toEqual(currentConfig); expect(await rendered(app, page, fixture)).toEqual(publicBefore);
  expect((await app.act('OWNER', 'home-price-select-source', args)).outcome).toBe('accepted');
  expect((await config(app)).items[0].sourceRowId).toBe(fixture.otherRowId);
  expect(money(one(await rendered(app, page, fixture))).kopecks).toBe(1200n);
});
