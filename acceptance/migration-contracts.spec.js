import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';
import { route, parseSource } from './migration-source.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await use(app); } finally { await app.close(); }
} });
test.use({ javaScriptEnabled: false, serviceWorkers: 'block' });
const nonempty = value => { expect(typeof value).toBe('string'); expect(value.trim().length).toBeGreaterThan(0); return value; };
const same = (actual, expected, label) => expect(JSON.stringify(actual) === JSON.stringify(expected), label).toBe(true);
async function material(app, row) {
  const actual = await app.observe('migration-imported-material', { mapId: row.map_id, requestedPath: row.requested_path });
  expect(actual.mapId).toBe(row.map_id); expect(actual.requestedPath).toBe(row.requested_path);
  expect(actual.sourceSnapshotSha256).toBe(row.source_sha256);
  nonempty(actual.materialId); nonempty(actual.revision);
  expect(actual.publicationState).toBe('published');
  expect(Array.isArray(actual.headings)).toBe(true); expect(typeof actual.bodyText).toBe('string');
  return actual;
}
async function publicRead(app, row) {
  const actual = await app.act('VISITOR', 'read-migration-route-direct', { requestedPath: row.requested_path });
  expect(actual.outcome).toBe('accepted'); expect(actual.status).toBe(200);
  expect(actual.location ?? '').toBe(''); expect(actual.requestedPath).toBe(row.requested_path);
  expect(actual.finalPath).toBe(row.requested_path);
  expect(actual.contentType).toMatch(/^text\/html(?:;|$)/i);
  return actual;
}

const legacyIds = ['MAP-003', 'MAP-009', 'MAP-033', 'MAP-039', 'MAP-044', 'MAP-045', 'MAP-049', 'MAP-078', 'MAP-090', 'MAP-097'];
for (const id of legacyIds) {
  test(`MIG-legacy-${id} | AT-504 AT-507 AC-MIG-004 AC-MIG-007 | historical material keeps its own source words and exact public path`, async ({ app, page }) => {
    const row = route(id); expect(row.proposed_type.startsWith('legacy_')).toBe(true);
    const source = await parseSource(page, row);
    await app.reset('migration-imported-local-source-bundle');
    const actual = await material(app, row);
    // Compare semantic stored text, not template markup; H1 is a separate field.
    same(actual.headings, source.headings, `${id}: stored headings`);
    same(actual.bodyText.replace(/\s+/gu, ' ').trim(), source.text, `${id}: stored words`);
    const response = await publicRead(app, row);
    const visible = await app.observe('migration-public-material-text', { requestedPath: row.requested_path });
    expect(visible.status).toBe(response.status); expect(visible.materialId).toBe(actual.materialId);
    same(visible.headings, source.headings, `${id}: public headings`);
    expect(typeof visible.bodyText).toBe('string');
    same(visible.bodyText.replace(/\s+/gu, ' ').trim(), source.text, `${id}: public words`);
    if (row.proposed_type === 'legacy_empty_main') {
      expect(source.headings).toEqual([]); expect(source.text).toBe('');
      // A historical empty main is still a published material, not an unpublished empty page.
      expect(actual.publicationState).toBe('published');
    } else expect(source.text.length).toBeGreaterThan(0);
  });
}

for (const id of ['MAP-013', 'MAP-038', 'MAP-073']) {
  test(`MIG-price-${id} | AT-508 AC-MIG-008 | every original price row and qualifier survives the local import`, async ({ app, page }) => {
    const row = route(id); const source = await parseSource(page, row);
    expect(source.tables.length).toBeGreaterThan(0);
    expect(source.tables.flat(2).some(cell => /\d/u.test(cell.text))).toBe(true);
    await app.reset('migration-imported-local-source-bundle');
    const actual = await material(app, row);
    const prices = await app.observe('migration-imported-price-grids', { materialId: actual.materialId });
    expect(prices.materialId).toBe(actual.materialId);
    // Logical row/cell grids, including merged axes: not a demand for identical HTML tags/CSS.
    same(prices.tables, source.tables, `${id}: stored price grids`);
    await publicRead(app, row);
    const rendered = await app.observe('migration-public-price-grids', { requestedPath: row.requested_path });
    expect(rendered.status).toBe(200); expect(rendered.materialId).toBe(actual.materialId);
    same(rendered.tables, source.tables, `${id}: public price grids`);
  });
}

test('MIG-wash-shared | AT-502 AC-MIG-002 | both exact wash routes expose one actual imported material and price source', async ({ app, page }) => {
  const oldRoute = route('MAP-088'), newRoute = route('MAP-115');
  expect(oldRoute.content_key).toBe('CONTENT-WASH'); expect(newRoute.content_key).toBe(oldRoute.content_key);
  expect(newRoute.source_sha256).toBe(oldRoute.source_sha256);
  const source = await parseSource(page, oldRoute); expect(source.text.length).toBeGreaterThan(0);
  await app.reset('migration-imported-local-source-bundle');
  const oldMaterial = await material(app, oldRoute), newMaterial = await material(app, newRoute);
  expect(oldMaterial.materialId).toBe(newMaterial.materialId);
  expect(oldMaterial.revision).toBe(newMaterial.revision);
  same(oldMaterial.headings, source.headings, 'MAP-088: stored heading'); same(newMaterial.headings, source.headings, 'MAP-115: stored heading');
  expect(typeof oldMaterial.proseText).toBe('string'); expect(typeof newMaterial.proseText).toBe('string');
  same(oldMaterial.proseText.replace(/\s+/gu, ' ').trim(), source.proseText, 'MAP-088: stored prose');
  same(newMaterial.proseText, oldMaterial.proseText, 'MAP-115: common prose');
  const oldPrices = await app.observe('migration-imported-price-grids', { materialId: oldMaterial.materialId });
  expect(oldPrices.materialId).toBe(oldMaterial.materialId);
  expect(Array.isArray(oldPrices.tables)).toBe(true); expect(oldPrices.tables.length).toBeGreaterThan(0);
  for (const cell of oldPrices.tables.flat(2)) expect(typeof cell.text).toBe('string');
  expect(oldPrices.tables.flat(2).some(cell => /\d/u.test(cell.text))).toBe(true);
  for (const row of [oldRoute, newRoute]) {
    await publicRead(app, row);
    const visible = await app.observe('migration-public-material-text', { requestedPath: row.requested_path });
    expect(visible.status).toBe(200); expect(visible.materialId).toBe(oldMaterial.materialId);
    same(visible.headings, source.headings, `${row.map_id}: public heading`); expect(typeof visible.proseText).toBe('string');
    same(visible.proseText.replace(/\s+/gu, ' ').trim(), source.proseText, `${row.map_id}: public prose`);
    const prices = await app.observe('migration-public-price-grids', { requestedPath: row.requested_path });
    expect(prices.status).toBe(200); expect(prices.materialId).toBe(oldMaterial.materialId);
    same(prices.tables, oldPrices.tables, `${row.map_id}: public common price grids`);
  }
  // Common actual price source is checked; original wash price/class mapping is a separate deferred comparison.
  // Canonical and advertising completeness are separate accepted profiles/readiness gates.
});
