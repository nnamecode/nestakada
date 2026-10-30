import { test, expect } from '@playwright/test';
import { readCsv, localTarget, getLocal } from './test-support.js';
import { parseMetadata } from './html-metadata.js';

// This suite requires the normal, isolated, imported published/indexable fixture.
// It does not prove application identity, publication rights, migration content or a full AC.
test.skip(!process.env.ESTAKADA_TEST_BASE_URL, 'NOT RUN: isolated application/fixture not configured');
test.use({ javaScriptEnabled: false, serviceWorkers: 'block' });

const routes = readCsv('docs/analytics-route-map.csv');
const albums = routes.filter(row => row.proposed_type === 'gallery_album');
const canonicalCases = [
  { id: 'WASH-OLD', path: '/services/drugie-uslugi/avtomojka', canonical: '/services/avtomojka', at: 'AT-601', ac: 'AC-SEO-001' },
  { id: 'WASH-NEW', path: '/services/avtomojka', canonical: '/services/avtomojka', at: 'AT-601', ac: 'AC-SEO-001' },
  { id: 'GALLERY-ROOT', path: '/gallery-of-works/', canonical: '/gallery-of-works/', at: 'AT-604', ac: 'AC-SEO-004' },
  { id: 'GALLERY-PAGE2', path: '/gallery-of-works/?page=2', canonical: '/gallery-of-works/', at: 'AT-604', ac: 'AC-SEO-004' },
  { id: 'GALLERY-PAGE1', path: '/gallery-of-works/?page=1', canonical: '/gallery-of-works/', follow: true, at: 'AT-604', ac: 'AC-SEO-004' },
  ...albums.map(row => ({ id: row.map_id, path: row.requested_path, canonical: row.requested_path, at: 'AT-604', ac: 'AC-SEO-004' })),
];

for (const item of canonicalCases) {
  test(`PUB-CANONICAL-${item.id} | ${item.at} ${item.ac} | ${item.path}`, async ({ request, page }) => {
    const base = localTarget(process.env.ESTAKADA_TEST_BASE_URL);
    const response = await getLocal(request, base, item.path, Boolean(item.follow));
    expect(response.status(), 'The exact published path must not become a redirect or unavailable page').toBe(200);
    expect(response.headers()['content-type']).toMatch(/text\/html/i);
    if (item.follow) {
      const final = new URL(response.url());
      expect(final.pathname + final.search).toBe('/gallery-of-works/');
      // The source archive did not establish page=1 initial/intermediate status codes.
    }
    const metadata = await parseMetadata(page, await response.text());
    expect(metadata.canonical).toHaveLength(1);
    expect(metadata.canonical[0].inHead).toBe(true);
    const expected = new URL(item.canonical, base).href;
    // The isolated fixture must use its explicit trusted origin, not the production origin.
    expect(metadata.canonical[0].href).toBe(expected);
    const httpLink = response.headers().link || '';
    for (const value of httpLink.split(/,(?=\s*<)/).filter(Boolean)) {
      const link = value.match(/^\s*<([^>]+)>([\s\S]*)$/);
      if (!link) continue;
      const relation = link[2].match(/(?:^|;)\s*rel\s*=\s*(?:"([^"]*)"|'([^']*)'|([^;\s,]+))/i);
      const tokens = (relation?.[1] ?? relation?.[2] ?? relation?.[3] ?? '').toLowerCase().split(/\s+/);
      if (tokens.includes('canonical'))
        expect(new URL(link[1], base).href, 'HTTP Link must not contradict the HTML canonical').toBe(expected);
    }
  });
}

for (const row of routes) {
  test(`PUB-METADATA-${row.map_id} | AT-605 AC-SEO-005 | viewport and no refresh`, async ({ request, page }) => {
    const base = localTarget(process.env.ESTAKADA_TEST_BASE_URL);
    const response = await getLocal(request, base, row.requested_path, row.map_id === 'MAP-017');
    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toMatch(/text\/html/i);
    const metadata = await parseMetadata(page, await response.text());
    expect(metadata.refreshCount, 'No client-side redirect replacing the required material').toBe(0);
    expect(metadata.viewport).toHaveLength(1);
    expect(metadata.viewport[0].inHead).toBe(true);
    const parts = (metadata.viewport[0].content || '').split(',').map(part => part.trim().split('=').map(value => value.trim().toLowerCase()));
    const width = parts.filter(([key]) => key === 'width');
    const scale = parts.filter(([key]) => key === 'initial-scale');
    expect(width).toEqual([['width', 'device-width']]);
    expect(scale).toHaveLength(1);
    expect(scale[0]).toHaveLength(2);
    expect(Number(scale[0][1])).toBe(1);
    expect(parts.filter(([key]) => key === 'maximum-scale'), 'Do not restrict user zoom').toHaveLength(0);
    expect(parts.some(([key, value]) => key === 'user-scalable' && ['no', '0'].includes(value))).toBe(false);
    // AutoRepair/alt/permissions and real mobile layout require their separate fixture/actions.
  });

  test(`PUB-CACHE-${row.map_id} | AT-050 AC-050 | normal HTML revalidation directive`, async ({ request }) => {
    const response = await getLocal(request, localTarget(process.env.ESTAKADA_TEST_BASE_URL), row.requested_path, row.map_id === 'MAP-017');
    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toMatch(/text\/html/i);
    const directives = (response.headers()['cache-control'] || '').split(',').map(value => value.trim().split('=')[0].toLowerCase());
    expect(directives, 'REQ-050 explicitly requires no-cache for normal public HTML').toContain('no-cache');
    // This is not proof of correct validators, no shared server cache, private/no-store or fallback behavior.
  });
}
