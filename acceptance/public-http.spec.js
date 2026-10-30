import { test, expect } from '@playwright/test';
import { readCsv, localTarget, getLocal } from './test-support.js';

const configured = Boolean(process.env.ESTAKADA_TEST_BASE_URL);

test('ENV-HTTP-001 | isolated origin replies HTML; not application admission', async ({ request }) => {
  const base = localTarget(process.env.ESTAKADA_TEST_BASE_URL);
  const response = await getLocal(request, base, '/');
  expect(response.status(), 'Narrow HTTP smoke only; this does not establish application identity or fixtures').toBe(200);
  expect(response.headers()['content-type']).toMatch(/text\/html/i);
  // Full application identity/data provisioning remains a TEST-03/04 fixture prerequisite.
});

for (const row of readCsv('docs/analytics-route-map.csv')) {
  test(`HTTP-${row.map_id} | AT-001 AT-501 | exact path ${row.requested_path}`, async ({ request }) => {
    test.skip(!configured, 'NOT RUN: isolated target not configured; ENV-HTTP-001 is expected to fail');
    const base = localTarget(process.env.ESTAKADA_TEST_BASE_URL);
    // MAP-017 preserves the observed chain's final path; archived initial code is unknown.
    const response = await getLocal(request, base, row.requested_path, row.map_id === 'MAP-017');
    expect(response.status(), `${row.map_id}: no replacement of the exact old URL with a redirect`).toBe(200);
    expect(response.headers()['content-type']).toMatch(/text\/html/i);
    const final = new URL(response.url());
    if (row.map_id === 'MAP-017') expect(final.pathname + final.search).toBe(row.observed_effective_path);
    else expect(final.pathname + final.search).toBe(row.requested_path);
    const body = await response.text();
    expect(body.trim()).not.toBe('');
    expect(body).not.toMatch(/<meta\b[^>]*http-equiv\s*=\s*["']?refresh\b/i);
    // Status/HTML checks alone do not close content, prices, gallery bytes or full AT-001.
  });
}

test('HTTP-UNKNOWN-001 | AT-002 | unknown path is a real 404', async ({ request }) => {
  test.skip(!configured, 'NOT RUN: no isolated application');
  const response = await getLocal(request, localTarget(process.env.ESTAKADA_TEST_BASE_URL), '/__acceptance_unknown_7edc4403__/');
  expect(response.status()).toBe(404);
});
