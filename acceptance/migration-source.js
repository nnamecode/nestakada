import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { expect } from '@playwright/test';
import { readCsv, root } from './test-support.js';

const map = readCsv('docs/analytics-route-map.csv');
const evidence = readCsv('docs/analytics-route-evidence.csv');
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const parserPages = new WeakSet();

export function route(id) {
  const rows = map.filter(row => row.map_id === id); expect(rows).toHaveLength(1);
  const row = rows[0];
  const records = evidence.filter(item => item.evidence_id === row.evidence_id);
  expect(records).toHaveLength(1);
  for (const key of ['map_id', 'requested_path', 'source_snapshot', 'source_sha256']) expect(records[0][key]).toBe(row[key]);
  expect(row.source_snapshot).toMatch(/^work\/site-audit\/crawl\/[a-f0-9]{20}\.html$/);
  expect(row.source_sha256).toMatch(/^[a-f0-9]{64}$/);
  return row;
}
function sourceBytes(row) {
  // Only an exact, hash-pinned public snapshot staged by the runner. No target dump or network oracle.
  const directory = path.join(root, 'acceptance', 'local-migration-source');
  const filename = path.basename(row.source_snapshot);
  const candidate = path.join(directory, filename);
  if (!fs.existsSync(candidate)) throw new Error(`MIGRATION_SOURCE_UNAVAILABLE: ${row.map_id}`);
  const realDirectory = fs.realpathSync(directory), realFile = fs.realpathSync(candidate);
  if (path.dirname(realFile) !== realDirectory || fs.lstatSync(candidate).isSymbolicLink()) throw new Error('MIGRATION_SOURCE_ESCAPE');
  const stat = fs.statSync(realFile);
  if (!stat.isFile() || stat.size <= 0 || stat.size > 256 * 1024) throw new Error('MIGRATION_SOURCE_SIZE');
  const bytes = fs.readFileSync(realFile);
  // Deliberately report only the MAP id on mismatch, never a full old-page body.
  if (digest(bytes) !== row.source_sha256) throw new Error(`MIGRATION_SOURCE_HASH_MISMATCH: ${row.map_id}`);
  return bytes.toString('utf8');
}
export async function parseSource(page, row) {
  const html = sourceBytes(row);
  if (!parserPages.has(page)) {
    await page.route('**/*', request => request.abort());
    await page.routeWebSocket('**/*', socket => socket.close());
    parserPages.add(page);
  }
  const serviceContent = ['MAP-013', 'MAP-015', 'MAP-032', 'MAP-038', 'MAP-073', 'MAP-088'].includes(row.map_id);
  const result = await page.evaluate(({ source, serviceContent }) => {
    const doc = new DOMParser().parseFromString(source, 'text/html');
    const mains = [...doc.querySelectorAll('div.col-lg-9')];
    if (mains.length !== 1) throw new Error('MIGRATION_SOURCE_MAIN_AMBIGUOUS');
    const main = mains[0].cloneNode(true);
    const clean = text => text.replace(/\s+/gu, ' ').trim();
    const headings = [...main.querySelectorAll(':scope > .pagetitle h1')].map(node => clean(node.textContent));
    let body;
    if (serviceContent) {
      // Individually inspected hash-pinned service sources use this own body, before images/menu.
      const roots = main.querySelectorAll(':scope > .c-content');
      if (roots.length !== 1) throw new Error('MIGRATION_SOURCE_CONTENT_AMBIGUOUS');
      body = roots[0].cloneNode(true);
    } else {
      // The ten legacy sources have their own text/list directly in the main column.
      body = main;
      body.querySelectorAll(':scope > .pagetitle').forEach(node => node.remove());
    }
    body.querySelectorAll('script, style').forEach(node => node.remove());
    if (body.querySelector('.services-list, .services-list-extended, .pagetitle')) throw new Error('MIGRATION_SOURCE_NAV_IN_BODY');
    const tables = [...body.querySelectorAll('table')].map(table => [...table.rows].map(tr => [...tr.cells].map(cell => ({
      text: clean(cell.textContent), rowSpan: cell.rowSpan, colSpan: cell.colSpan,
    }))));
    const text = clean(body.textContent);
    body.querySelectorAll('table').forEach(node => node.remove());
    return { headings, text, proseText: clean(body.textContent), tables };
  }, { source: html, serviceContent });
  expect(Array.isArray(result.headings)).toBe(true); expect(Array.isArray(result.tables)).toBe(true);
  return result;
}
