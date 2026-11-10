// DEV-09A host-only, read-only integrity gate. Never imports application data.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const mapRelative = 'docs/analytics-route-map.csv';
const evidenceRelative = 'docs/analytics-route-evidence.csv';
const crawlRelative = 'work/site-audit/crawl';
const READY = 'design_basis_present_verify_migration_before_launch';
const BLOCKER_COUNTS = new Map([
  ['READY-06_missing_catalog_design', 1],
  ['READY-06_missing_legacy_design', 10],
  ['READY-06_missing_standalone_album_design', 17],
  ['content_difference_price_not_in_v3_requires_resolution', 3],
  ['review_alias_template_and_canonical', 1],
  ['review_legacy_page2_subset', 1],
  ['verify_initial_redirect_chain', 1],
]);
const MAP_HEADER = [
  'map_id', 'requested_path', 'observed_effective_path',
  'observed_final_status', 'content_key', 'proposed_type', 'import_rule',
  'basis', 'review_state', 'source_snapshot', 'source_sha256',
  'source_main_locator', 'source_h1', 'source_main_facts', 'target_template',
  'template_artifact', 'template_basis', 'static_v3_entry',
  'static_v3_state', 'evidence_id', 'target_media_bindings',
];
const EVIDENCE_HEADER = [
  'evidence_id', 'map_id', 'requested_path', 'source_requested_path',
  'source_snapshot', 'source_sha256', 'source_main_line', 'source_h1',
  'source_main_facts', 'source_main_text_excerpt', 'target_template',
  'template_artifact', 'template_basis', 'template_review_state',
  'static_v3_entry', 'static_v3_state', 'notes', 'target_media_bindings',
];

function fail(code) {
  const error = new Error(code);
  error.code = code;
  throw error;
}

function parseCsv(bytes, expectedHeader) {
  let text;
  try { text = new TextDecoder('utf-8', { fatal: true }).decode(bytes); }
  catch { fail('CSV_UTF8'); }
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  const rows = [];
  let row = [], field = '', quoted = false, afterQuote = false;
  const finishField = () => { row.push(field); field = ''; afterQuote = false; };
  const finishRow = () => { finishField(); rows.push(row); row = []; };
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"') {
        if (text[index + 1] === '"') { field += '"'; index += 1; }
        else { quoted = false; afterQuote = true; }
      } else field += char;
      continue;
    }
    if (afterQuote && char !== ',' && char !== '\r' && char !== '\n')
      fail('CSV_FORMAT');
    if (char === '"') {
      if (field !== '' || afterQuote) fail('CSV_FORMAT');
      quoted = true;
    } else if (char === ',') finishField();
    else if (char === '\n') finishRow();
    else if (char === '\r') {
      if (text[index + 1] !== '\n') fail('CSV_FORMAT');
    } else field += char;
  }
  if (quoted) fail('CSV_FORMAT');
  if (row.length || field !== '' || afterQuote) finishRow();
  if (!rows.length) fail('CSV_EMPTY');
  const header = rows.shift();
  if (header.length !== expectedHeader.length ||
      header.some((value, index) => value !== expectedHeader[index]))
    fail('CSV_HEADER');
  return rows.map(values => {
    if (values.length !== expectedHeader.length) fail('CSV_COLUMNS');
    return Object.fromEntries(expectedHeader.map((name, index) => [name, values[index]]));
  });
}

function requireUnique(rows, field, code) {
  const seen = new Set();
  for (const row of rows) {
    if (!row[field] || seen.has(row[field])) fail(code);
    seen.add(row[field]);
  }
}

function requirePublicPath(value) {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') ||
      value.includes('\\') || value.includes('#') || /[\u0000-\u001f\u007f]/u.test(value) ||
      /^[a-z][a-z0-9+.-]*:/iu.test(value)) fail('PUBLIC_PATH');
  if (value.includes('?') && value !== '/gallery-of-works/?page=1' &&
      value !== '/gallery-of-works/?page=2') fail('PUBLIC_QUERY');
}

function within(candidate, parent) {
  const relative = path.relative(parent, candidate);
  return relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative));
}

function requireSource(relative, root, crawlRoot, io = fs) {
  if (!/^work\/site-audit\/crawl\/[a-f0-9]{20}\.html$/u.test(relative))
    fail('SOURCE_PATH');
  const absolute = path.resolve(root, ...relative.split('/'));
  if (!within(absolute, crawlRoot)) fail('SOURCE_PATH');
  let metadata, real;
  try {
    metadata = io.lstatSync(absolute);
    real = io.realpathSync(absolute);
  } catch { fail('SOURCE_FILE'); }
  if (metadata.isSymbolicLink() || !metadata.isFile() || !within(real, crawlRoot))
    fail('SOURCE_FILE');
  return absolute;
}

function digest(bytes) {
  return crypto.createHash('sha256').update(bytes).digest('hex');
}

function requireDigest(bytes, expected) {
  if (!/^[a-f0-9]{64}$/u.test(expected) || digest(bytes) !== expected)
    fail('SOURCE_SHA256');
}

function requireEqual(left, right, code) {
  if (left !== right) fail(code);
}

function classify(rows) {
  const ready = [], blockers = new Map([...BLOCKER_COUNTS.keys()].map(key => [key, []]));
  for (const row of rows) {
    if (row.review_state === READY) ready.push(row.map_id);
    else if (blockers.has(row.review_state)) blockers.get(row.review_state).push(row.map_id);
    else fail('REVIEW_STATE');
  }
  if (ready.length !== 81) fail('READY_COUNT');
  for (const [state, expected] of BLOCKER_COUNTS) {
    if (blockers.get(state).length !== expected) fail('BLOCKER_COUNT');
  }
  return { ready: ready.sort(), blockers };
}

function validate(mapRows, evidenceRows, root = repo, io = fs) {
  if (mapRows.length !== 115 || evidenceRows.length !== 115) fail('ROW_COUNT');
  for (const [rows, field, code] of [
    [mapRows, 'map_id', 'MAP_ID_DUPLICATE'],
    [mapRows, 'requested_path', 'REQUESTED_PATH_DUPLICATE'],
    [mapRows, 'evidence_id', 'EVIDENCE_ID_DUPLICATE'],
    [evidenceRows, 'evidence_id', 'RTE_ID_DUPLICATE'],
    [evidenceRows, 'map_id', 'RTE_MAP_DUPLICATE'],
  ]) requireUnique(rows, field, code);
  const evidenceById = new Map(evidenceRows.map(row => [row.evidence_id, row]));
  const crawlRoot = path.resolve(root, ...crawlRelative.split('/'));
  const sourceCache = new Map();
  for (let index = 0; index < 115; index += 1) {
    const map = mapRows[index];
    const expectedMap = `MAP-${String(index + 1).padStart(3, '0')}`;
    const expectedRte = `RTE-${String(index + 1).padStart(3, '0')}`;
    requireEqual(map.map_id, expectedMap, 'MAP_SEQUENCE');
    requireEqual(map.evidence_id, expectedRte, 'RTE_SEQUENCE');
    requirePublicPath(map.requested_path);
    if (map.map_id === 'MAP-115') {
      if (map.requested_path !== '/services/avtomojka' || map.observed_effective_path !== '' ||
          map.observed_final_status !== '') fail('MAP115_OBSERVED');
    } else {
      requirePublicPath(map.observed_effective_path);
      if (map.observed_final_status !== '200') fail('OBSERVED_STATUS');
    }
    const evidence = evidenceById.get(expectedRte);
    if (!evidence) fail('RTE_MISSING');
    for (const field of ['map_id', 'requested_path', 'source_snapshot', 'source_sha256',
      'source_h1', 'source_main_facts', 'target_template', 'template_artifact',
      'template_basis', 'static_v3_entry', 'static_v3_state', 'target_media_bindings'])
      requireEqual(map[field], evidence[field], 'MAP_RTE_MISMATCH');
    requireEqual(map.review_state, evidence.template_review_state, 'MAP_RTE_MISMATCH');
    const absolute = requireSource(map.source_snapshot, root, crawlRoot, io);
    const cached = sourceCache.get(absolute);
    if (cached && cached !== map.source_sha256) fail('SOURCE_SHA_CONFLICT');
    if (!cached) {
      let bytes;
      try { bytes = io.readFileSync(absolute); } catch { fail('SOURCE_FILE'); }
      requireDigest(bytes, map.source_sha256);
      sourceCache.set(absolute, map.source_sha256);
    }
  }
  if (sourceCache.size !== 114) fail('SOURCE_COUNT');
  const classes = classify(mapRows);
  return { ...classes, sourceCount: sourceCache.size };
}

function expectFailure(code, action) {
  try { action(); } catch (error) {
    if (error.code === code) return;
    fail('SELFCHECK_WRONG_ERROR');
  }
  fail('SELFCHECK_MISSED_ERROR');
}

function selfcheck() {
  const parsed = parseCsv(Buffer.from('a,b\r\n"x,y","q""z"\r\n'), ['a', 'b']);
  if (parsed.length !== 1 || parsed[0].a !== 'x,y' || parsed[0].b !== 'q"z')
    fail('SELFCHECK_CSV');
  expectFailure('CSV_FORMAT', () => parseCsv(Buffer.from('a,b\n"x,y\n'), ['a', 'b']));
  expectFailure('CSV_HEADER', () => parseCsv(Buffer.from('b,a\n1,2\n'), ['a', 'b']));
  expectFailure('CSV_COLUMNS', () => parseCsv(Buffer.from('a,b\n1,2,3\n'), ['a', 'b']));
  expectFailure('MAP_ID_DUPLICATE', () => requireUnique(
    [{ map_id: 'MAP-001' }, { map_id: 'MAP-001' }], 'map_id', 'MAP_ID_DUPLICATE'));
  expectFailure('REQUESTED_PATH_DUPLICATE', () => requireUnique(
    [{ requested_path: '/' }, { requested_path: '/' }],
    'requested_path', 'REQUESTED_PATH_DUPLICATE'));
  expectFailure('PUBLIC_QUERY', () => requirePublicPath('/page/?x=1'));
  expectFailure('PUBLIC_PATH', () => requirePublicPath('https://example.test/'));
  expectFailure('SOURCE_PATH', () => requireSource('../secret', repo, path.join(repo, crawlRelative)));
  const fakeIo = {
    lstatSync: () => ({ isSymbolicLink: () => true, isFile: () => true }),
    realpathSync: value => value,
  };
  expectFailure('SOURCE_FILE', () => requireSource(
    'work/site-audit/crawl/aaaaaaaaaaaaaaaaaaaa.html', repo,
    path.join(repo, crawlRelative), fakeIo));
  expectFailure('SOURCE_SHA256', () => requireDigest(Buffer.from('safe'), '0'.repeat(64)));
  expectFailure('MAP_RTE_MISMATCH', () => requireEqual('MAP-001', 'MAP-002', 'MAP_RTE_MISMATCH'));
  expectFailure('REVIEW_STATE', () => classify([
    ...Array.from({ length: 81 }, (_, index) => ({ map_id: `M${index}`, review_state: READY })),
    { map_id: 'unknown', review_state: 'unknown' },
  ]));
  process.stdout.write('{"schema":"dev09-preflight-selfcheck-v1","status":"pass"}\n');
}

function inventory() {
  const mapBytes = fs.readFileSync(path.join(repo, ...mapRelative.split('/')));
  const evidenceBytes = fs.readFileSync(path.join(repo, ...evidenceRelative.split('/')));
  const mapRows = parseCsv(mapBytes, MAP_HEADER);
  const evidenceRows = parseCsv(evidenceBytes, EVIDENCE_HEADER);
  const result = validate(mapRows, evidenceRows);
  const blockerGroups = Object.fromEntries([...result.blockers.entries()].map(
    ([state, ids]) => [state, ids.sort()]));
  const report = {
    schema: 'dev09-migration-preflight-v1',
    policy: 'integrity_only_not_import_authority',
    status: 'blocked',
    inputs: {
      map: { relativePath: mapRelative, sha256: digest(mapBytes) },
      evidence: { relativePath: evidenceRelative, sha256: digest(evidenceBytes) },
    },
    counts: { map: mapRows.length, evidence: evidenceRows.length,
      sourceSnapshots: result.sourceCount, ready: result.ready.length,
      blocked: mapRows.length - result.ready.length },
    readyMapIds: result.ready,
    blockers: blockerGroups,
    externalGates: ['READY-04', 'MIG-01', 'ANA-Q041'],
  };
  process.stdout.write(`${JSON.stringify(report)}\n`);
}

try {
  if (process.argv.length !== 3 || !['--inventory', '--selfcheck'].includes(process.argv[2]))
    fail('USAGE');
  if (process.argv[2] === '--selfcheck') selfcheck();
  else inventory();
} catch (error) {
  const code = /^[A-Z0-9_]+$/u.test(error?.code ?? '') ? error.code : 'INTERNAL';
  process.stderr.write(`DEV09_PREFLIGHT_ERROR ${code}\n`);
  process.exitCode = 1;
}
