import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { root, readCsv, localTarget, routeUrl, getLocal } from './test-support.js';

test('HARNESS-001 | CSV, constant IDs and complete 140-AC/63-REQ document coverage', () => {
  const trace = readCsv('docs/implementation-traceability.csv');
  const cases = readCsv('docs/acceptance-cases.csv');
  const docs = [...new Set(trace.map(row => row.source_document))];
  const sourceIds = docs.flatMap(doc => [...fs.readFileSync(path.join(root, 'docs', doc), 'utf8')
    .matchAll(/^\| (AC-(?:[A-Z]+-)?\d{3}) \|/gm)].map(match => match[1]));
  expect(sourceIds).toHaveLength(140);
  expect(new Set(sourceIds).size).toBe(140);
  expect(trace.map(row => row.ac_id).sort()).toEqual([...sourceIds].sort());
  expect(cases).toHaveLength(140);
  expect(new Set(cases.map(row => row.case_id)).size).toBe(cases.length);
  expect(cases.flatMap(row => row.ac_ids.split(';')).sort()).toEqual([...sourceIds].sort());
  expect(new Set(cases.flatMap(row => row.req_ids.split(';'))).size).toBe(63);
  const byAc = new Map(trace.map(row => [row.ac_id, row]));
  for (const row of cases) {
    expect(row.case_id).toMatch(/^AT-\d{3}$/);
    const contract = byAc.get(row.ac_ids);
    expect(contract, `${row.case_id}: one AC per composite case`).toBeTruthy();
    expect(row.req_ids.split(';').sort()).toEqual(contract.requirement_ids.split(';').sort());
    expect(row.design_task).toBe(contract.test_design_task);
    for (const column of ['preconditions', 'actions', 'expected', 'method', 'evidence', 'readiness'])
      expect(row[column]?.trim(), `${row.case_id}:${column}`).toBeTruthy();
  }
});

test('HARNESS-002 | all 115 migration paths and MAP/RTE IDs are unique and local', () => {
  const maps = readCsv('docs/analytics-route-map.csv');
  const evidence = readCsv('docs/analytics-route-evidence.csv');
  expect(maps).toHaveLength(115);
  expect(new Set(maps.map(row => row.map_id)).size).toBe(115);
  expect(new Set(maps.map(row => row.requested_path)).size).toBe(115);
  expect(evidence).toHaveLength(115);
  const base = localTarget('http://127.0.0.1:8000');
  for (const row of maps) expect(routeUrl(base, row.requested_path).origin).toBe(base.origin);
  expect(maps.filter(row => row.proposed_type === 'gallery_album')).toHaveLength(17);
  expect(maps.find(row => row.map_id === 'MAP-115').requested_path).toBe('/services/avtomojka');
});

test('HARNESS-003 | live targets, credentials and origin escapes are rejected', () => {
  for (const value of [undefined, 'https://estakada-service.ru', 'http://estakada-service.ru:8000',
    'http://127.0.0.1', 'http://user:secret@127.0.0.1:8000', 'http://127.0.0.1:8000/path',
    'file:///tmp/site', 'http://127.0.0.1.evil.test:8000'])
    expect(() => localTarget(value)).toThrow();
  const base = localTarget('http://127.0.0.1:8000');
  for (const value of ['//estakada-service.ru/', '/\\evil.test/', 'https://example.org/'])
    expect(() => routeUrl(base, value)).toThrow();
});

test('HARNESS-004 | external redirects are rejected before a second request', async () => {
  let calls = 0;
  const fakeRequest = { get: async () => {
    calls++;
    return { status: () => 302, headers: () => ({ location: 'https://estakada-service.ru/' }) };
  } };
  await expect(getLocal(fakeRequest, localTarget('http://127.0.0.1:8000'), '/', true)).rejects.toThrow('External redirect');
  expect(calls).toBe(1);
});
