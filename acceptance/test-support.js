import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const root = fileURLToPath(new URL('../', import.meta.url));

// Read RFC-style CSV without a second dependency; reject truncated/ambiguous records.
export function readCsv(relativePath) {
  const text = fs.readFileSync(path.join(root, relativePath), 'utf8').replace(/^\uFEFF/, '');
  const records = []; let row = [], field = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      if (quoted && text[i + 1] === '"') { field += '"'; i++; }
      else quoted = !quoted;
    } else if (ch === ',' && !quoted) { row.push(field); field = ''; }
    else if ((ch === '\n' || ch === '\r') && !quoted) {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      row.push(field); if (row.some(Boolean)) records.push(row);
      row = []; field = '';
    } else field += ch;
  }
  if (quoted) throw new Error(`Unclosed CSV quote: ${relativePath}`);
  if (field || row.length) { row.push(field); records.push(row); }
  const headers = records.shift();
  if (!headers || new Set(headers).size !== headers.length) throw new Error('Invalid CSV header');
  return records.map((values, i) => {
    if (values.length !== headers.length) throw new Error(`CSV width: ${relativePath}:${i + 2}`);
    return Object.fromEntries(headers.map((name, n) => [name, values[n]]));
  });
}

export function localTarget(value) {
  if (!value) throw new Error('TEST_TARGET_UNCONFIGURED: set ESTAKADA_TEST_BASE_URL only for an isolated test site');
  const url = new URL(value);
  if (url.protocol !== 'http:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash)
    throw new Error('Only an explicit local HTTP origin without credentials/path is allowed');
  if (!['127.0.0.1', 'localhost', '[::1]', 'host.docker.internal'].includes(url.hostname))
    throw new Error('External/live targets are forbidden in this acceptance suite');
  if (!url.port) throw new Error('An explicit isolated test port is required');
  return url;
}

export function routeUrl(base, requestedPath) {
  if (!requestedPath.startsWith('/') || requestedPath.startsWith('//') || requestedPath.includes('\\'))
    throw new Error('Invalid route path');
  const url = new URL(requestedPath, base);
  if (url.origin !== base.origin) throw new Error('Route escaped the isolated test origin');
  return url;
}

// Follow only local redirects; never allow the HTTP client to follow an external Location.
export async function getLocal(request, base, requestedPath, follow = false) {
  let url = routeUrl(base, requestedPath);
  for (let hop = 0; hop <= 5; hop++) {
    const response = await request.get(url.href, { maxRedirects: 0, timeout: 10_000 });
    if (!follow || ![301, 302, 303, 307, 308].includes(response.status())) return response;
    const location = response.headers().location;
    if (!location) throw new Error('Redirect without Location');
    const next = new URL(location, url);
    if (next.origin !== base.origin) throw new Error('External redirect forbidden');
    url = routeUrl(base, next.pathname + next.search);
  }
  throw new Error('Redirect cycle or too many hops');
}
