// DEV-09E host-only bounded validator/generator. No filesystem writes or network.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MAP_PATH = 'docs/analytics-route-map.csv';
const RTE_PATH = 'docs/analytics-route-evidence.csv';
const SOURCE_PATH = 'work/site-audit/crawl/0184ec81ddcc19cff2bd.html';
const PACKAGE_PATH = 'app/content/dev09e_services_catalog.json';
const MAP_SHA = 'c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8';
const RTE_SHA = 'c3a8a395fb4ed55fef6027a58014ce5decaadda7c559870bf06247c2fbeb79bc';
const SOURCE_SHA = 'e61fbaffbfea280abf1c9d3c1017174b8c22323bcc149c88e8bb013cbf9e1da7';
const PACKAGE_SHA = 'beffdfdbacc6a24a71c68ee692f03be262f67745b8425e1ce9b204b8d15ca9e9';
const CAPS = new Map([[MAP_PATH, 256 * 1024], [RTE_PATH, 512 * 1024],
  [SOURCE_PATH, 256 * 1024], [PACKAGE_PATH, 20 * 1024]]);
const ALLOWED = new Set(CAPS.keys());
const H1 = 'Услуги и цены автосервиса "Эстакада"';
const GROUP_COUNTS = [12, 10, 18, 11, 7];
const PAGE = Object.freeze({
  page_id: 'f39af842-05a7-4101-af9a-2fc320d457d0', map_id: 'MAP-002',
  url: '/services/', kind: 'services_master_catalog',
  parent_id: 'e80c3de1-feea-4847-b550-325a825ffc0e', position: 1,
  name: 'Услуги и цены', h1: H1, title: 'Услуги | Автосервис «Эстакада»',
  description: '', is_published: false,
});
const MAP_HEADER = [
  'map_id', 'requested_path', 'observed_effective_path', 'observed_final_status',
  'content_key', 'proposed_type', 'import_rule', 'basis', 'review_state',
  'source_snapshot', 'source_sha256', 'source_main_locator', 'source_h1',
  'source_main_facts', 'target_template', 'template_artifact', 'template_basis',
  'static_v3_entry', 'static_v3_state', 'evidence_id', 'target_media_bindings',
];
const RTE_HEADER = [
  'evidence_id', 'map_id', 'requested_path', 'source_requested_path',
  'source_snapshot', 'source_sha256', 'source_main_line', 'source_h1',
  'source_main_facts', 'source_main_text_excerpt', 'target_template',
  'template_artifact', 'template_basis', 'template_review_state',
  'static_v3_entry', 'static_v3_state', 'notes', 'target_media_bindings',
];

function fail(code) {
  const error = new Error(code); error.code = code; throw error;
}

function within(candidate, parent) {
  const relative = path.relative(parent, candidate);
  return relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative));
}

function samePath(left, right) {
  const a = path.normalize(left), b = path.normalize(right);
  return process.platform === 'win32' ? a.toLowerCase() === b.toLowerCase() : a === b;
}

function requireFile(relative, root = repo, io = fs, allowed = ALLOWED) {
  if (!allowed.has(relative) || !/^[a-z0-9_./-]+$/u.test(relative) ||
      relative.includes('..') || relative.includes('//')) fail('FILE_PATH');
  const absolute = path.resolve(root, ...relative.split('/'));
  if (!within(absolute, root)) fail('FILE_PATH');
  let metadata, real;
  try { metadata = io.lstatSync(absolute); real = io.realpathSync(absolute); }
  catch { fail('FILE_ACCESS'); }
  if (metadata.isSymbolicLink() || !metadata.isFile() || !within(real, root) ||
      !samePath(real, absolute)) fail('FILE_BOUNDARY');
  return { absolute, size: metadata.size };
}

function readBounded(relative, io = fs) {
  const file = requireFile(relative, repo, io);
  const cap = CAPS.get(relative);
  if (!Number.isSafeInteger(file.size) || file.size < 1 || file.size > cap)
    fail('FILE_SIZE');
  let bytes;
  try { bytes = io.readFileSync(file.absolute); } catch { fail('FILE_ACCESS'); }
  if (!Buffer.isBuffer(bytes) || bytes.length !== file.size || bytes.length > cap)
    fail('FILE_SIZE');
  return bytes;
}

function digest(bytes) {
  return crypto.createHash('sha256').update(bytes).digest('hex');
}

function requireDigest(bytes, expected, code) {
  if (!/^[a-f0-9]{64}$/u.test(expected) || digest(bytes) !== expected) fail(code);
}

function decodeUtf8(bytes, code) {
  try { return new TextDecoder('utf-8', { fatal: true }).decode(bytes); }
  catch { fail(code); }
}

function parseCsv(bytes, expectedHeader) {
  let text = decodeUtf8(bytes, 'CSV_UTF8');
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  const rows = []; let row = [], field = '', quoted = false, afterQuote = false;
  const finishField = () => { row.push(field); field = ''; afterQuote = false; };
  const finishRow = () => { finishField(); rows.push(row); row = []; };
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"') {
        if (text[index + 1] === '"') { field += '"'; index += 1; }
        else { quoted = false; afterQuote = true; }
      } else field += char;
    } else if (afterQuote && ![',', '\r', '\n'].includes(char)) fail('CSV_FORMAT');
    else if (char === '"') {
      if (field !== '' || afterQuote) fail('CSV_FORMAT'); quoted = true;
    } else if (char === ',') finishField();
    else if (char === '\n') finishRow();
    else if (char === '\r') {
      if (text[index + 1] !== '\n') fail('CSV_FORMAT');
    } else field += char;
  }
  if (quoted) fail('CSV_FORMAT');
  if (row.length || field !== '' || afterQuote) finishRow();
  const header = rows.shift();
  if (!header || header.length !== expectedHeader.length ||
      header.some((value, index) => value !== expectedHeader[index])) fail('CSV_HEADER');
  return rows.map(values => {
    if (values.length !== expectedHeader.length) fail('CSV_COLUMNS');
    return Object.fromEntries(expectedHeader.map((name, index) => [name, values[index]]));
  });
}

function one(rows, field, value, code) {
  const found = rows.filter(row => row[field] === value);
  if (found.length !== 1) fail(code);
  return found[0];
}

function decodeText(value) {
  const entities = new Map([['&amp;', '&'], ['&quot;', '"'], ['&nbsp;', '\u00a0'],
    ['&laquo;', '«'], ['&raquo;', '»'], ['&ndash;', '–'], ['&mdash;', '—']]);
  const withoutEntities = value.replace(
    /&(?:[A-Za-z][A-Za-z0-9]+|#[0-9]+|#x[0-9A-Fa-f]+);/gu, entity => {
      if (!entities.has(entity)) fail('SOURCE_ENTITY');
      return '';
    });
  if (withoutEntities.includes('&')) fail('SOURCE_ENTITY');
  const result = value.replace(
    /&(?:[A-Za-z][A-Za-z0-9]+|#[0-9]+|#x[0-9A-Fa-f]+);/gu,
    entity => entities.get(entity));
  if (result.includes('<') || result.includes('>') ||
      /[\u0000-\u001f\u007f]/u.test(result)) fail('SOURCE_TEXT');
  return result;
}

function internalPath(value) {
  if (!/^services\/[a-z0-9/-]+$/u.test(value) || value.includes('//') ||
      value.includes('..') || /[?#\\]/u.test(value)) fail('SOURCE_PATH');
  return `/${value}`;
}

function sourceCatalog(bytes, counts = GROUP_COUNTS, expectedH1 = H1) {
  const text = decodeUtf8(bytes, 'SOURCE_UTF8').replace(/\r\n?/gu, '\n');
  const marker = '<div class="services-list-extended">';
  if (text.split(marker).length !== 2) fail('SOURCE_LOCATOR');
  const h1s = [...text.matchAll(/<h1>([^<>]+)<\/h1>/gu)];
  if (h1s.length !== 1 || decodeText(h1s[0][1]) !== expectedH1) fail('SOURCE_H1');
  const matches = [...text.matchAll(
    /<a class="item-link" href="([^"]+)">\s*<h([23])>([^<>]+)<\/h\2>\s*<\/a>/gu)];
  const groups = [];
  for (const match of matches) {
    const item = { name: decodeText(match[3].trim()), href: internalPath(match[1]) };
    if (match[2] === '2') groups.push({ ...item, items: [] });
    else {
      if (!groups.length) fail('SOURCE_GROUPS');
      groups.at(-1).items.push(item);
    }
  }
  if (groups.length !== counts.length || groups.reduce(
    (total, group) => total + group.items.length + 1, 0) !==
      counts.reduce((total, count) => total + count, 0) ||
      groups.some((group, index) => group.items.length + 1 !== counts[index]))
    fail('SOURCE_COUNTS');
  return groups;
}

function exactKeys(value, expected, code = 'PACKAGE_SCHEMA') {
  if (value === null || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).length !== expected.length ||
      Object.keys(value).some((key, index) => key !== expected[index])) fail(code);
}

function packageValue(groups) {
  return {
    schema: 'dev09-services-catalog-v1',
    policy: 'validated_package_not_import_authority',
    inputs: { map_sha256: MAP_SHA, evidence_sha256: RTE_SHA, source_sha256: SOURCE_SHA },
    page: { ...PAGE, source: { relative_path: SOURCE_PATH, sha256: SOURCE_SHA }, groups },
  };
}

function canonical(value) { return `${JSON.stringify(value, null, 2)}\n`; }

function parsePackage(bytes) {
  const text = decodeUtf8(bytes, 'PACKAGE_UTF8');
  if (text.includes('\r')) fail('PACKAGE_CANONICAL');
  let value;
  try { value = JSON.parse(text); } catch { fail('PACKAGE_JSON'); }
  if (canonical(value) !== text) fail('PACKAGE_CANONICAL');
  return value;
}

function requireLink(value) {
  exactKeys(value, ['name', 'href']);
  if (typeof value.name !== 'string' || value.name.length < 1 || value.name.length > 200 ||
      typeof value.href !== 'string' || !/^\/services\/[a-z0-9/-]+$/u.test(value.href) ||
      value.href.includes('//') || value.href.includes('..') || /[?#\\]/u.test(value.href) ||
      /[<>\u0000-\u001f\u007f]/u.test(value.name)) fail('PACKAGE_LINK');
}

function requireCatalogContent(actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) fail('PACKAGE_CONTENT');
}

function validatePackage(value, sourceGroups, mapRows, rteRows) {
  exactKeys(value, ['schema', 'policy', 'inputs', 'page']);
  if (value.schema !== 'dev09-services-catalog-v1' ||
      value.policy !== 'validated_package_not_import_authority') fail('PACKAGE_POLICY');
  exactKeys(value.inputs, ['map_sha256', 'evidence_sha256', 'source_sha256']);
  if (value.inputs.map_sha256 !== MAP_SHA || value.inputs.evidence_sha256 !== RTE_SHA ||
      value.inputs.source_sha256 !== SOURCE_SHA) fail('PACKAGE_INPUTS');
  exactKeys(value.page, ['page_id', 'map_id', 'url', 'kind', 'parent_id', 'position',
    'name', 'h1', 'title', 'description', 'is_published', 'source', 'groups']);
  exactKeys(value.page.source, ['relative_path', 'sha256']);
  for (const [key, expected] of Object.entries(PAGE)) {
    if (value.page[key] !== expected) fail('PAGE_EXACT');
  }
  if (value.page.source.relative_path !== SOURCE_PATH || value.page.source.sha256 !== SOURCE_SHA ||
      !Array.isArray(value.page.groups) || value.page.groups.length !== 5) fail('PAGE_EXACT');
  value.page.groups.forEach((group, index) => {
    exactKeys(group, ['name', 'href', 'items']);
    requireLink({ name: group.name, href: group.href });
    if (!Array.isArray(group.items) || group.items.length + 1 !== GROUP_COUNTS[index])
      fail('PACKAGE_GROUPS');
    group.items.forEach(requireLink);
  });
  requireCatalogContent(value.page.groups, sourceGroups);
  const map = one(mapRows, 'map_id', 'MAP-002', 'MAP_EXACT');
  const rte = one(rteRows, 'map_id', 'MAP-002', 'RTE_EXACT');
  if (mapRows.length !== 115 || rteRows.length !== 115 || map.requested_path !== PAGE.url ||
      map.proposed_type !== PAGE.kind || map.source_snapshot !== SOURCE_PATH ||
      map.source_sha256 !== SOURCE_SHA || map.source_h1 !== H1 ||
      map.source_main_locator !== '//div[contains(@class,"col-lg-9")]:248' ||
      map.source_main_facts !== 'h1=True;main_chars=1387;paragraphs=0;tables=0;services_lists=1;links=58;images=0;iframes=0' ||
      rte.evidence_id !== 'RTE-002' || rte.map_id !== map.map_id ||
      rte.requested_path !== map.requested_path || rte.source_snapshot !== map.source_snapshot ||
      rte.source_sha256 !== map.source_sha256 || rte.source_h1 !== map.source_h1 ||
      rte.source_main_facts !== map.source_main_facts) fail('MAP_RTE_EXACT');
  return value;
}

function expectFailure(label, code, action) {
  try { action(); } catch (error) {
    if (error.code === code) return;
    fail(`SELFCHECK_ERROR_${label}`);
  }
  fail(`SELFCHECK_MISSED_${label}`);
}

function selfcheck() {
  const base = '<h1>Каталог</h1><div class="services-list-extended">' +
    '<a class="item-link" href="services/a/"><h2>Группа А</h2></a>' +
    '<a class="item-link" href="services/a/one"><h3>Один &amp; два</h3></a>' +
    '<a class="item-link" href="services/b/"><h2>Группа Б</h2></a>' +
    '<a class="item-link" href="services/b/one"><h3>Три</h3></a></div>';
  const parse = value => sourceCatalog(Buffer.from(value), [2, 2], 'Каталог');
  const groups = parse(base);
  if (groups.length !== 2 || groups[0].items[0].name !== 'Один & два')
    fail('SELFCHECK_SOURCE');
  expectFailure('MISSING_LINK', 'SOURCE_COUNTS', () => parse(base.replace(
    '<a class="item-link" href="services/b/one"><h3>Три</h3></a>', '')));
  expectFailure('EXTRA_LINK', 'SOURCE_COUNTS', () => parse(base.replace('</div>',
    '<a class="item-link" href="services/b/two"><h3>Четыре</h3></a></div>')));
  expectFailure('GROUP_SHIFT', 'SOURCE_GROUPS', () => parse(base.replace(
    '<a class="item-link" href="services/a/"><h2>Группа А</h2></a>', '')));
  expectFailure('NAME_ENTITY', 'SOURCE_ENTITY', () => parse(base.replace('Три', '&copy;')));
  expectFailure('PATH_QUERY', 'SOURCE_PATH', () => parse(base.replace(
    'services/b/one', 'services/b/one?x=1')));
  const reordered = structuredClone(groups);
  [reordered[0], reordered[1]] = [reordered[1], reordered[0]];
  expectFailure('REORDERED_PACKAGE', 'PACKAGE_CONTENT',
    () => requireCatalogContent(reordered, groups));
  const renamed = structuredClone(groups);
  renamed[0].items[0].name = 'Другое корректное имя';
  expectFailure('CHANGED_PACKAGE_NAME', 'PACKAGE_CONTENT',
    () => requireCatalogContent(renamed, groups));
  const repathed = structuredClone(groups);
  repathed[0].items[0].href = '/services/a/two';
  expectFailure('CHANGED_PACKAGE_HREF', 'PACKAGE_CONTENT',
    () => requireCatalogContent(repathed, groups));
  expectFailure('EXTRA_PACKAGE_KEY', 'PACKAGE_SCHEMA', () => exactKeys(
    { name: 'x', href: '/services/x', extra: true }, ['name', 'href']));
  expectFailure('DUPLICATE_PACKAGE_KEY', 'PACKAGE_CANONICAL', () => parsePackage(
    Buffer.from('{"schema":"x","schema":"y"}\n')));
  expectFailure('PACKAGE_CR', 'PACKAGE_CANONICAL', () => parsePackage(
    Buffer.from('{\r\n}\r\n')));
  expectFailure('PACKAGE_UTF8', 'PACKAGE_UTF8', () => parsePackage(Buffer.from([0xff])));
  const allowed = new Set(['safe/file']);
  const fake = { lstatSync: () => ({ size: 1, isSymbolicLink: () => false,
    isFile: () => true }), realpathSync: value => value };
  requireFile('safe/file', repo, fake, allowed);
  expectFailure('PATH_ESCAPE', 'FILE_PATH', () => requireFile('../safe/file', repo, fake, allowed));
  expectFailure('SYMLINK', 'FILE_BOUNDARY', () => requireFile('safe/file', repo, {
    ...fake, lstatSync: () => ({ size: 1, isSymbolicLink: () => true, isFile: () => true }),
  }, allowed));
  expectFailure('NONREGULAR', 'FILE_BOUNDARY', () => requireFile('safe/file', repo, {
    ...fake, lstatSync: () => ({ size: 1, isSymbolicLink: () => false, isFile: () => false }),
  }, allowed));
  expectFailure('OVERSIZE', 'FILE_SIZE', () => readBounded(PACKAGE_PATH, {
    lstatSync: () => ({ size: CAPS.get(PACKAGE_PATH) + 1,
      isSymbolicLink: () => false, isFile: () => true }),
    realpathSync: value => value,
    readFileSync: () => { fail('SELFCHECK_OVERSIZE_READ'); },
  }));
  process.stdout.write('{"schema":"dev09-services-catalog-selfcheck-v1","status":"pass"}\n');
}

function inputs() {
  const mapBytes = readBounded(MAP_PATH), rteBytes = readBounded(RTE_PATH);
  const sourceBytes = readBounded(SOURCE_PATH);
  requireDigest(mapBytes, MAP_SHA, 'MAP_SHA256');
  requireDigest(rteBytes, RTE_SHA, 'RTE_SHA256');
  requireDigest(sourceBytes, SOURCE_SHA, 'SOURCE_SHA256');
  return { mapBytes, rteBytes, sourceBytes, groups: sourceCatalog(sourceBytes) };
}

function emit() {
  const value = inputs();
  const result = packageValue(value.groups);
  validatePackage(result, value.groups, parseCsv(value.mapBytes, MAP_HEADER),
    parseCsv(value.rteBytes, RTE_HEADER));
  process.stdout.write(canonical(result));
}

function check() {
  const value = inputs();
  const packageBytes = readBounded(PACKAGE_PATH);
  requireDigest(packageBytes, PACKAGE_SHA, 'PACKAGE_SHA256');
  const result = validatePackage(parsePackage(packageBytes), value.groups,
    parseCsv(value.mapBytes, MAP_HEADER), parseCsv(value.rteBytes, RTE_HEADER));
  process.stdout.write(`${JSON.stringify({ schema: 'dev09-services-catalog-check-v1',
    status: 'pass', mapId: result.page.map_id, groups: 5, links: 58,
    bytes: packageBytes.length,
    groupsSha256: digest(Buffer.from(JSON.stringify(result.page.groups))),
    writes: 0, published: 0 })}\n`);
}

try {
  const mode = process.argv[2];
  if (process.argv.length !== 3 || !['--emit', '--check', '--selfcheck'].includes(mode))
    fail('USAGE');
  if (mode === '--emit') emit(); else if (mode === '--check') check(); else selfcheck();
} catch (error) {
  const code = /^[A-Z0-9_]+$/u.test(error?.code ?? '') ? error.code : 'INTERNAL';
  process.stderr.write(`DEV09_SERVICES_CATALOG_ERROR ${code}\n`);
  process.exitCode = 1;
}
