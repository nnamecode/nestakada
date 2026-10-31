import { createHash } from 'node:crypto';
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
const normalize = value => value.replace(/\s+/gu, ' ').trim();
function money(value) {
  const text = normalize(value), from = /^от\s*/iu.test(text);
  const match = text.replace(/^от\s*/iu, '').replace(/\s/gu, '').match(/^(\d+)(?:[,.](\d{1,2}))?(?:₽|руб\.?|р\.?)?$/iu);
  return match ? { kopecks: BigInt(match[1]) * 100n + BigInt((match[2] || '').padEnd(2, '0')), from } : null;
}
function decimal(value) {
  const match = required(value).match(/^(\d+)(?:\.(\d{1,2}))?$/u);
  expect(Boolean(match)).toBe(true);
  return BigInt(match[1]) * 100n + BigInt((match[2] || '').padEnd(2, '0'));
}
async function setup(app, options = {}) {
  await app.reset('price-editor-isolated-table', options);
  const fixture = await app.observe('price-editor-fixture');
  for (const key of ['pageId', 'rowId', 'cellId', 'cellSelector', 'labelSelector', 'tableSelector', 'rowSelector', 'allCellsSelector']) required(fixture[key]);
  return fixture;
}
async function state(app, page = 'P-PRICE') {
  const value = await app.observe('price-editor-state', { page });
  required(value.revision); required(value.row.id); required(value.cell.id);
  expect(Array.isArray(value.history)).toBe(true);
  for (const key of ['url', 'h1', 'title', 'description', 'publicText', 'draftText', 'grants', 'assetIds']) expect(value.protectedFields).toHaveProperty(key);
  return value;
}
async function rendered(app, page, fixture, material = 'P-PRICE') {
  const response = await app.observe('price-editor-public-response', { page: material });
  expect(response.status).toBe(200); required(response.body);
  return page.evaluate(({ body, selectors }) => {
    const doc = new DOMParser().parseFromString(body, 'text/html'), clean = value => value.replace(/\s+/gu, ' ').trim();
    const table = doc.querySelector(selectors.tableSelector);
    if (!table) throw new Error('PRICE_TABLE_NOT_OBSERVED');
    return { cell: clean(doc.querySelector(selectors.cellSelector)?.textContent || ''),
      label: clean(doc.querySelector(selectors.labelSelector)?.textContent || ''),
      hasCell: doc.querySelectorAll(selectors.cellSelector).length === 1,
      hasLabel: doc.querySelectorAll(selectors.labelSelector).length === 1,
      rows: table.querySelectorAll(selectors.rowSelector).length,
      cells: table.querySelectorAll(selectors.allCellsSelector).length };
  }, { body: response.body, selectors: fixture });
}
async function update(app, actor, fixture, before, cell, material = 'P-PRICE') {
  return app.act(actor, 'price-editor-update-cell', { page: material, rowId: fixture.rowId, cellId: fixture.cellId, base: before.revision, cell });
}
async function storedAndPublic(app, page, fixture, before, cell, material = 'P-PRICE') {
  const after = await state(app, material), actual = await rendered(app, page, fixture, material);
  expect(actual.hasCell).toBe(true); expect(actual.hasLabel).toBe(true);
  expect(after.row.id).toBe(fixture.rowId); expect(after.cell.id).toBe(fixture.cellId);
  expect(after.revision).not.toBe(before.revision); expect(after.protectedFields).toEqual(before.protectedFields);
  expect(after.cell.kind).toBe(cell.kind);
  if (cell.kind === 'money') {
    expect(decimal(after.cell.amount)).toBe(decimal(cell.amount)); expect(after.cell.from).toBe(cell.from);
    const displayed = money(actual.cell); expect(displayed).not.toBeNull();
    expect(displayed.kopecks).toBe(decimal(cell.amount)); expect(displayed.from).toBe(cell.from);
  } else if (cell.kind === 'text') {
    expect(after.cell.text).toBe(cell.text); expect(actual.cell).toBe(normalize(cell.text));
  } else {
    expect(after.cell.amount ?? null).toBeNull(); expect(money(actual.cell)).toBeNull();
    // This fixture's empty value has no numeric note: a prefixed/suffixed zero must not evade the anchored parser.
    expect(actual.cell).not.toMatch(/\p{N}/u);
  }
  return after;
}
const validCells = [
  ['empty', { kind: 'empty' }],
  ['text', { kind: 'text', text: 'После осмотра; код 15' }],
  ['zero', { kind: 'money', amount: '0.00', from: false }],
  ['from', { kind: 'money', amount: '1234.56', from: true }],
  ['kopeck', { kind: 'money', amount: '0.01', from: false }],
  ['maximum', { kind: 'money', amount: '999999999.99', from: false }],
];
for (const [name, cell] of validCells) {
  test(`PRICE-EDITOR-cell-${name} | AT-105 AC-DTL-005 | typed value persists and appears in the real public price cell`, async ({ app, page }) => {
    const fixture = await setup(app), before = await state(app);
    expect(before.row.id).toBe(fixture.rowId); expect(before.cell.id).toBe(fixture.cellId);
    expect((await update(app, 'OWNER', fixture, before, cell)).outcome).toBe('accepted');
    await storedAndPublic(app, page, fixture, before, cell);
  });
}

for (const value of ['-0.01', 'Infinity', '-Infinity', 'NaN', '1000000000.00']) {
  test(`PRICE-EDITOR-reject-${value} | AT-105 AC-DTL-005 | invalid numeric value is refused whole without altering valid published prices`, async ({ app, page }) => {
    const fixture = await setup(app), before = await state(app), publicBefore = await rendered(app, page, fixture);
    expect((await update(app, 'OWNER', fixture, before, { kind: 'money', amount: value, from: false })).outcome).toBe('denied');
    expect(await state(app)).toEqual(before); expect(await rendered(app, page, fixture)).toEqual(publicBefore);
    const positive = { kind: 'money', amount: '0.01', from: false };
    expect((await update(app, 'OWNER', fixture, before, positive)).outcome).toBe('accepted');
    await storedAndPublic(app, page, fixture, before, positive);
  });
}

function matrix(rows, columns) {
  return Array.from({ length: rows }, (_, row) => Array.from({ length: columns }, (_, col) => col === 0
    ? { kind: 'text', text: `PRICE-EDITOR-LABEL-${row}` }
    : { kind: 'money', amount: '0.01', from: false }));
}
const shapes = [
  ['rows-at', 500, 1, true], ['rows-over', 501, 1, false],
  ['columns-at', 1, 32, true], ['columns-over', 1, 33, false],
  ['cells-at', 500, 20, true], ['cells-over', 435, 23, false],
];
for (const [name, rows, columns, allowed] of shapes) {
  test(`PRICE-EDITOR-table-${name} | AT-105 AC-DTL-005 | table bounds are checked without trimming rows columns or cells`, async ({ app, page }) => {
    const fixture = await setup(app), before = await state(app), publicBefore = await rendered(app, page, fixture);
    const cells = matrix(rows, columns);
    const result = await app.act('OWNER', 'price-editor-replace-table', { page: 'P-PRICE', base: before.revision, cells });
    if (!allowed) {
      expect(result.outcome).toBe('denied'); expect(await state(app)).toEqual(before);
      expect(await rendered(app, page, fixture)).toEqual(publicBefore);
      expect((await app.act('OWNER', 'price-editor-replace-table', { page: 'P-PRICE', base: before.revision, cells: matrix(2, 2) })).outcome).toBe('accepted');
    } else expect(result.outcome).toBe('accepted');
    const expected = allowed ? cells : matrix(2, 2), shape = await app.observe('price-editor-table-shape', { page: 'P-PRICE' });
    expect(shape.rows).toBe(expected.length); expect(shape.columns).toBe(expected[0].length);
    expect(shape.cells).toBe(expected.length * expected[0].length);
    expect(shape.cellsDigest).toBe(createHash('sha256').update(JSON.stringify(expected), 'utf8').digest('hex'));
    const actual = await rendered(app, page, fixture);
    expect(actual.rows).toBe(shape.rows); expect(actual.cells).toBe(shape.cells);
  });
}

for (const [field, limit] of [['label', 500], ['text', 1000]]) for (const size of [limit, limit + 1]) {
  test(`PRICE-EDITOR-length-${field}-${size} | AT-105 AC-DTL-005 | label and text boundaries preserve the complete value or reject the whole edit`, async ({ app, page }) => {
    const fixture = await setup(app), before = await state(app), publicBefore = await rendered(app, page, fixture), value = 'Я'.repeat(size);
    const act = text => field === 'label'
      ? app.act('OWNER', 'price-editor-update-label', { page: 'P-PRICE', rowId: fixture.rowId, base: before.revision, label: text })
      : update(app, 'OWNER', fixture, before, { kind: 'text', text });
    const result = await act(value);
    if (size > limit) {
      expect(result.outcome).toBe('denied'); expect(await state(app)).toEqual(before);
      expect(await rendered(app, page, fixture)).toEqual(publicBefore);
      expect((await act('Я'.repeat(limit))).outcome).toBe('accepted');
    } else expect(result.outcome).toBe('accepted');
    const after = await state(app), actual = await rendered(app, page, fixture), expected = 'Я'.repeat(limit);
    expect(after.protectedFields).toEqual(before.protectedFields); expect(after.row.id).toBe(fixture.rowId);
    if (field === 'label') { expect(actual.hasLabel).toBe(true); expect(after.row.label).toBe(expected); expect(actual.label).toBe(expected); }
    else { expect(actual.hasCell).toBe(true); expect(after.cell.text).toBe(expected); expect(actual.cell).toBe(expected); }
  });
}

for (const role of ['owner', 'employee-default-off', 'employee-assigned-on', 'employee-other-page']) {
  test(`PRICE-EDITOR-right-${role} | AT-105 AT-016 AC-DTL-005 AC-016 | price permission is bound to the submitted page`, async ({ app, page }) => {
    const fixture = await setup(app, { role }), material = role === 'employee-other-page' ? 'P-PRICE-OTHER' : 'P-PRICE';
    const rights = await app.observe('price-editor-permissions');
    expect(rights.assignedPageIds).toContain(fixture.assignedPageId);
    expect(rights.priceGrantedPageIds.includes(fixture.assignedPageId)).toBe(role === 'employee-assigned-on' || role === 'employee-other-page');
    if (role === 'employee-other-page') { expect(rights.assignedPageIds).not.toContain(fixture.pageId); expect(rights.priceGrantedPageIds).not.toContain(fixture.pageId); }
    const before = await state(app, material), publicBefore = await rendered(app, page, fixture, material), cell = { kind: 'money', amount: '1234.56', from: false };
    const actor = role === 'owner' ? 'OWNER' : 'S-EDIT', allowed = role === 'owner' || role === 'employee-assigned-on';
    const result = await update(app, actor, fixture, before, cell, material);
    if (allowed) expect(result.outcome).toBe('accepted');
    else {
      expect(result.outcome).toBe('denied'); expect(await state(app, material)).toEqual(before);
      expect(await rendered(app, page, fixture, material)).toEqual(publicBefore);
      expect((await update(app, 'OWNER', fixture, before, cell, material)).outcome).toBe('accepted');
    }
    await storedAndPublic(app, page, fixture, before, cell, material);
  });
}
