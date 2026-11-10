// DEV-09B host-only, read-only validator. It never imports or publishes data.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MAP_PATH = 'docs/analytics-route-map.csv';
const RTE_PATH = 'docs/analytics-route-evidence.csv';
const PACKAGE_PATH = 'app/content/dev09b_articles_slice.json';
const MAP_SHA = 'c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8';
const RTE_SHA = 'c3a8a395fb4ed55fef6027a58014ce5decaadda7c559870bf06247c2fbeb79bc';
const READY = 'design_basis_present_verify_migration_before_launch';
const EXPECTED = [
  ['MAP-001', 'e80c3de1-feea-4847-b550-325a825ffc0e', '/', 'home', null, 0,
    'Главная', 'deferred', 'work/site-audit/crawl/59657143c68dec7e2e68.html',
    'b4999dfa62959ae390eb45162dcf62257dc228e52cd2bfe1e9702f49fc1c0b97', []],
  ['MAP-006', '5e6ab812-950c-46f6-875e-6205a9446cc8', '/articles/',
    'articles_catalog', 'e80c3de1-feea-4847-b550-325a825ffc0e', 4, 'Статьи',
    'deferred', 'work/site-audit/crawl/7d77056de27a9d3d4178.html',
    '364555e482c73244c9c8e887a7b4e9eabcda1f63627c3ef1736eade75bc455ed', []],
  ['MAP-031', '2d53411f-cc5e-4fd7-9cc7-8ebee6bbd435',
    '/articles/zamena-masla-v-dvigatele', 'article',
    '5e6ab812-950c-46f6-875e-6205a9446cc8', 0, 'Замена масла в двигателе',
    'source_text_complete_media_deferred',
    'work/site-audit/crawl/14576e552fecad65ae73.html',
    '34e865f3d936e29d84a69c2a97002d532ee2ac359de5a4a439214b9b34b0a6bc',
    ['p1', 'p1', 'p1']],
  ['MAP-037', 'f22de959-c6c6-4ff8-8008-a9bf835145fe',
    '/articles/zamena-texnicheskix-zhidkostej', 'article',
    '5e6ab812-950c-46f6-875e-6205a9446cc8', 1, 'Замена технических жидкостей',
    'source_text_complete_media_deferred',
    'work/site-audit/crawl/f6c171267a4a1a59417d.html',
    'f79707f5875c6d64ffd14f4cde85bd12b7e8747bceac2180ebafdc5da90e3927',
    ['p1', 'p1', 'p1', 'p1', 'p1']],
  ['MAP-043', '7054b068-2221-41df-a292-bc30aeb9b119',
    '/articles/zamena-filtrov-avtomobilya', 'article',
    '5e6ab812-950c-46f6-875e-6205a9446cc8', 2, 'Замена фильтров автомобиля',
    'source_text_complete_media_deferred',
    'work/site-audit/crawl/78c4fe8f69621612ab29.html',
    '8ea9baadcce5f7e43c69557543eb5c00d56632a28ca358b3b4da2c857a0de693',
    ['p1', 'p1', 'p1', 'p1']],
  ['MAP-048', '5120fe58-109c-48fa-aa11-b34580449aaf',
    '/articles/kompyuternaya-diagnostika-avtomobilya', 'article',
    '5e6ab812-950c-46f6-875e-6205a9446cc8', 3,
    'Компьютерная диагностика автомобиля', 'source_text_complete_media_deferred',
    'work/site-audit/crawl/340a8c32c65d034518b9.html',
    'a7e11f47d0c44b93810d8a4132315e31c8d7c8078b763b71648bdea20082e09d',
    ['p1', 'p1', 'p1', 'p1']],
  ['MAP-053', 'bf7482e2-016b-481d-b319-a0df7a47d177', '/articles/remen-grm',
    'article', '5e6ab812-950c-46f6-875e-6205a9446cc8', 4, 'Ремень ГРМ',
    'source_text_complete_media_deferred',
    'work/site-audit/crawl/5e25c0d654f83ac6d720.html',
    '148bbf09861f9c2035e9a26c93f0a0e28ca8830a4fb72e860c6dee246710c147',
    ['p1', 'p1', 'p1']],
  ['MAP-057', '010c6bdd-a610-45f1-af6b-52f55a569ddf', '/articles/remont-akpp',
    'article', '5e6ab812-950c-46f6-875e-6205a9446cc8', 5, 'Ремонт АКПП',
    'source_text_complete_media_deferred',
    'work/site-audit/crawl/66ec46d6386f2fd85a68.html',
    '498a942964d1270b5ab7fe3b69d20bc652588f05014ca96aa29ed192cc02b5e0',
    ['p1', 'p1', 'p1', 'p1', 'p1', 'p1', 'p1', 'p1', 'p1']],
  ['MAP-065', '5929545c-b932-4dbc-8ec6-9806f5a9007a',
    '/articles/remont-dvigatelya-avtomobilya', 'article',
    '5e6ab812-950c-46f6-875e-6205a9446cc8', 6, 'Ремонт двигателя автомобиля',
    'source_text_complete_media_deferred',
    'work/site-audit/crawl/aff237c9c93859f8aecb.html',
    '69eb70cf2fb43fb3442cac2197e8f03dfea93ef84651e17cf51ec1d0a659f7a6',
    ['p1', 'p1', 'p1', 'u4', 'p1']],
  ['MAP-071', 'd9e46de1-297b-4c43-969b-6ba579ffe07b',
    '/articles/remont-i-diagnostika-avtoelektriki', 'article',
    '5e6ab812-950c-46f6-875e-6205a9446cc8', 7,
    'Ремонт и диагностика автоэлектрики', 'source_text_complete_media_deferred',
    'work/site-audit/crawl/87b016281c0189929789.html',
    '3ca05a66dcd63647322e3171e2384eb124e593acf21801f377233a05891cbc5f',
    ['p1', 'p1', 'u6', 'p1']],
  ['MAP-072', '83763734-e473-41e4-a878-bc06ff6bbd99', '/articles/remont-mkpp',
    'article', '5e6ab812-950c-46f6-875e-6205a9446cc8', 8, 'Ремонт МКПП',
    'source_text_complete_media_deferred',
    'work/site-audit/crawl/ae236ec43daccf2bdb79.html',
    '6b2918d65a3268fb16eae730783634f47d116ebd25880eeef0a47e66639ba9e5',
    ['p1', 'p1', 'p1', 'p1', 'p1', 'p1', 'p1']],
  ['MAP-077', '23e720a7-dbad-482a-b9c8-6a2912ae0b48', '/articles/polirovka-far',
    'article', '5e6ab812-950c-46f6-875e-6205a9446cc8', 9, 'Полировка фар',
    'source_text_complete_media_deferred',
    'work/site-audit/crawl/9d71d73299ccfa8e7bee.html',
    'b2e37576a02003f499a76450c0ea692f766f36f2a74daf7cb6ea08b8f5c8d9d0',
    ['p1', 'p1', 'p1', 'p1']],
  ['MAP-082', '4dbe3ebe-24ea-4b40-90c7-8354dc33b2fc',
    '/articles/regulirovka-razval-sxozhdeniya-koles', 'article',
    '5e6ab812-950c-46f6-875e-6205a9446cc8', 10,
    'Регулировка развал-схождения колес', 'source_text_complete_media_deferred',
    'work/site-audit/crawl/e6d28289278e8f481833.html',
    'd84833d87c80b709c52a549a07767a071ff65e30f6d6d4dd259e4c6779ed728c',
    ['p1', 'p1', 'p1']],
  ['MAP-087', 'd8d10b26-f3f5-46ba-9d32-0984b2d40a9f',
    '/articles/kachestvennyie-uslugi-shinomontazha', 'article',
    '5e6ab812-950c-46f6-875e-6205a9446cc8', 11,
    'Качественные услуги шиномонтажа', 'source_text_complete_media_deferred',
    'work/site-audit/crawl/00600f366618519d6337.html',
    'f5f8a38fbde524b484b79b74a057b9a6a68f27434e4612741df36f52a96edcab',
    ['p1', 'p1', 'p1', 'p1', 'p1', 'p1', 'p1', 'p1']],
  ['MAP-093', 'd4a63713-7f22-41f3-8769-edaa91b8e457',
    '/articles/sistema-oxlazhdeniya-dvigatelya', 'article',
    '5e6ab812-950c-46f6-875e-6205a9446cc8', 12, 'Система охлаждения двигателя',
    'source_text_complete_media_deferred',
    'work/site-audit/crawl/5b2446a839b3c70d5dcf.html',
    'bcab530a05f47d5be59195bbd7599b802afda04d6c6f607dcf83df5ccf45ed2b',
    ['p1', 'p1', 'p1', 'u6']],
  ['MAP-100', 'f07e4a08-9746-4b1e-81c8-74a325b4230c',
    '/articles/ochistka-kondiczionera', 'article',
    '5e6ab812-950c-46f6-875e-6205a9446cc8', 13, 'Очистка кондиционера',
    'source_text_complete_media_deferred',
    'work/site-audit/crawl/3e5b979e2112059af1d1.html',
    '22ff446ce6287b6e3d234d4750fd1f3aca0ade3d841f0a841cf7d3dd04abd992',
    ['p1', 'p1', 'p1']],
  ['MAP-103', '545aa532-47e0-4fbb-864a-96e5db71482d',
    '/articles/kuzovnoj-remont-avtomobilya', 'article',
    '5e6ab812-950c-46f6-875e-6205a9446cc8', 14, 'Кузовной ремонт автомобиля',
    'source_text_complete_media_deferred',
    'work/site-audit/crawl/3b78a41b670c3f1fb7d2.html',
    'b1d9ff6c721f19441041bb05c3cee6bc49ade12cafced2eb0658cad544f9f631', ['p4']],
  ['MAP-105', '1b9bc2ee-ad4a-4e05-9b45-53c7e738755d',
    '/articles/povrezhdenie-lakokrasochnogo-pokryitiya', 'article',
    '5e6ab812-950c-46f6-875e-6205a9446cc8', 15,
    'Повреждение лакокрасочного покрытия', 'source_text_complete_media_deferred',
    'work/site-audit/crawl/f478027d9d05996d409e.html',
    'b8d8161a6c3b2d0bdfa4aacd704967e9e40b6e968671bdef05e7bd7d4a2fd672',
    ['p1', 'p1', 'p1', 'p1']],
  ['MAP-108', '1023fe6c-6843-4032-9481-a7106cbbdf71',
    '/articles/pokraska-bampera', 'article', '5e6ab812-950c-46f6-875e-6205a9446cc8',
    16, 'Покраска бампера', 'source_text_complete_media_deferred',
    'work/site-audit/crawl/7e52c2b8f35f4aa7ce91.html',
    'abeff8d042e17dbf6234be5cc2492672f6e571608b4af95a5005956896efa7cc',
    ['p1', 'p1', 'p1']],
  ['MAP-110', '9de01837-f7b1-42f2-bcb1-a2832730e6fc',
    '/articles/kompleksnaya-shumoizolyacziya', 'article',
    '5e6ab812-950c-46f6-875e-6205a9446cc8', 17, 'Комплексная шумоизоляция',
    'source_text_complete_media_deferred',
    'work/site-audit/crawl/a1934f18d933a8e5a5e1.html',
    '4a8628d4833152fbe8dcc6f0e944ae0512dd8ed7b161a42e140409f1f2fec3ab',
    ['p1', 'p1']],
];
const IDS = EXPECTED.map(row => row[0]);
const SOURCES = EXPECTED.map(row => row[8]);
const ALLOWED = new Set([MAP_PATH, RTE_PATH, PACKAGE_PATH, ...SOURCES]);
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
const PAGE_KEYS = ['page_id', 'map_id', 'url', 'kind', 'parent_id', 'position',
  'name', 'h1', 'title', 'description', 'is_published', 'content_state',
  'source', 'blocks'];

function fail(code) {
  const error = new Error(code); error.code = code; throw error;
}

function samePath(left, right) {
  const a = path.normalize(left), b = path.normalize(right);
  return process.platform === 'win32' ? a.toLowerCase() === b.toLowerCase() : a === b;
}

function within(candidate, parent) {
  const relative = path.relative(parent, candidate);
  return relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative));
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
  return absolute;
}

function read(relative, io = fs) {
  const absolute = requireFile(relative, repo, io);
  try { return io.readFileSync(absolute); } catch { fail('FILE_ACCESS'); }
}

function digest(bytes) {
  return crypto.createHash('sha256').update(bytes).digest('hex');
}

function requireDigest(bytes, expected, code = 'SHA256') {
  if (!/^[a-f0-9]{64}$/u.test(expected) || digest(bytes) !== expected) fail(code);
}

function decodeUtf8(bytes, code = 'UTF8') {
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

function exactKeys(value, expected, code = 'PACKAGE_SCHEMA') {
  if (value === null || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).length !== expected.length ||
      Object.keys(value).some((key, index) => key !== expected[index])) fail(code);
}

function parsePackage(bytes) {
  const text = decodeUtf8(bytes, 'PACKAGE_UTF8');
  let value;
  try { value = JSON.parse(text); } catch { fail('PACKAGE_JSON'); }
  if (`${JSON.stringify(value, null, 2)}\n` !== text) fail('PACKAGE_CANONICAL');
  return value;
}

function one(rows, field, value, code) {
  const found = rows.filter(row => row[field] === value);
  if (found.length !== 1) fail(code);
  return found[0];
}

function titleFromSnapshot(bytes) {
  const lines = decodeUtf8(bytes, 'SOURCE_UTF8').replace(/\r\n?/gu, '\n').split('\n');
  const line = lines[8]?.trim() ?? '';
  const match = /^<title>([^<>]+)<\/title>$/u.exec(line);
  if (!match || match[1].includes('&')) fail('SOURCE_TITLE');
  return match[1];
}

function plain(value) {
  if (value.includes('<') || value.includes('>') || value.includes('\r') ||
      value.includes('\n')) fail('ARTICLE_TEXT');
  const entities = new Map([
    ['&ndash;', '–'], ['&mdash;', '—'], ['&laquo;', '«'], ['&raquo;', '»'],
    ['&nbsp;', '\u00a0'],
  ]);
  const decoded = value.replace(
    /&(?:[A-Za-z][A-Za-z0-9]+|#[0-9]+|#x[0-9A-Fa-f]+);/gu,
    entity => {
      if (!entities.has(entity)) fail('ARTICLE_ENTITY');
      return entities.get(entity);
    });
  if (decoded.includes('&')) fail('ARTICLE_ENTITY');
  return decoded;
}

function articleFragment(bytes, shape) {
  const lines = decodeUtf8(bytes, 'SOURCE_UTF8').replace(/\r\n?/gu, '\n').split('\n');
  const marker = '<div class="col-lg-9 col-md-8">';
  if (lines.filter(line => line.trim() === marker).length !== 1) fail('ARTICLE_LOCATOR');
  const part = lines.map(line => line.trim());
  if (part[247] !== marker || part[248] !== '' ||
      part[249] !== '<div class="pagetitle">' || part[250] !== '<i ></i>' ||
      part[252] !== '</div>') fail('ARTICLE_GRAMMAR');
  const h1 = /^<h1>([^<>]+)<\/h1>$/u.exec(part[251]);
  if (!h1) fail('ARTICLE_GRAMMAR');
  const blocks = [];
  let cursor = 253;
  for (const token of shape) {
    const kind = token[0], count = Number(token.slice(1));
    if (!Number.isInteger(count) || count < 1 || count > 9) fail('ARTICLE_GRAMMAR');
    if (kind === 'p') {
      const paragraph = /^<p>(.*)<\/p>$/u.exec(part[cursor]);
      if (!paragraph) fail('ARTICLE_GRAMMAR');
      const segments = paragraph[1].split('<br />');
      if (segments.length !== count) fail('ARTICLE_GRAMMAR');
      blocks.push({ type: 'paragraph', segments: segments.map(plain) });
      cursor += 1;
    } else if (kind === 'u') {
      if (part[cursor] !== '<ul>') fail('ARTICLE_GRAMMAR');
      const items = [];
      for (let index = 1; index <= count; index += 1) {
        const item = /^<li>([^<>]+)<\/li>$/u.exec(part[cursor + index]);
        if (!item) fail('ARTICLE_GRAMMAR');
        items.push(plain(item[1]));
      }
      if (part[cursor + count + 1] !== '</ul>') fail('ARTICLE_GRAMMAR');
      blocks.push({ type: 'unordered_list', items });
      cursor += count + 2;
    } else fail('ARTICLE_GRAMMAR');
  }
  if (part[cursor] !== '' || part[cursor + 1] !== '' ||
      part[cursor + 2] !== '</div>') fail('ARTICLE_GRAMMAR');
  return { h1: plain(h1[1]), blocks };
}

function requireArticleContent(fragment, page) {
  if (fragment.h1 !== page.h1 || JSON.stringify(fragment.blocks) !==
      JSON.stringify(page.blocks)) fail('ARTICLE_CONTENT');
}

function requireBlocks(blocks, shape) {
  if (!Array.isArray(blocks) || blocks.length !== shape.length) fail('PAGE_BLOCKS');
  blocks.forEach((block, index) => {
    const token = shape[index], count = Number(token.slice(1));
    if (token[0] === 'p') {
      exactKeys(block, ['type', 'segments'], 'PAGE_BLOCKS');
      if (block.type !== 'paragraph' || !Array.isArray(block.segments) ||
          block.segments.length !== count || block.segments.some(
            text => typeof text !== 'string' || text.length === 0)) fail('PAGE_BLOCKS');
    } else if (token[0] === 'u') {
      exactKeys(block, ['type', 'items'], 'PAGE_BLOCKS');
      if (block.type !== 'unordered_list' || !Array.isArray(block.items) ||
          block.items.length !== count || block.items.some(
            text => typeof text !== 'string' || text.length === 0)) fail('PAGE_BLOCKS');
    } else fail('PAGE_BLOCKS');
  });
}

function requireArticleFacts(value, shape) {
  const paragraphs = shape.filter(token => token[0] === 'p').length;
  if (!new RegExp(`^h1=True;main_chars=[0-9]+;paragraphs=${paragraphs};` +
      'tables=0;services_lists=0;links=0;images=0;iframes=0$', 'u').test(value))
    fail('ARTICLE_FACTS');
}

function validatePackage(value, mapRows, rteRows, snapshots) {
  exactKeys(value, ['schema', 'policy', 'inputs', 'pages']);
  if (value.schema !== 'dev09-articles-slice-v2' ||
      value.policy !== 'validated_package_not_import_authority') fail('PACKAGE_POLICY');
  exactKeys(value.inputs, ['map_sha256', 'evidence_sha256']);
  if (value.inputs.map_sha256 !== MAP_SHA || value.inputs.evidence_sha256 !== RTE_SHA ||
      mapRows.length !== 115 || rteRows.length !== 115 ||
      !Array.isArray(value.pages) || value.pages.length !== EXPECTED.length)
    fail('PACKAGE_INPUTS');
  const seenIds = new Set(), seenUrls = new Set(), seenPositions = new Set();
  value.pages.forEach((page, index) => {
    exactKeys(page, PAGE_KEYS);
    exactKeys(page.source, ['relative_path', 'sha256']);
    const [mapId, pageId, url, kind, parentId, position, name, state,
      sourcePath, sourceSha, shape] = EXPECTED[index];
    if (page.map_id !== mapId || page.page_id !== pageId || page.url !== url ||
        page.kind !== kind || page.parent_id !== parentId || page.position !== position ||
        page.name !== name || page.content_state !== state || page.description !== '' ||
        page.is_published !== false || page.source.relative_path !== sourcePath ||
        page.source.sha256 !== sourceSha) fail('PAGE_EXACT');
    requireBlocks(page.blocks, shape);
    const positionKey = `${page.parent_id ?? 'ROOT'}:${page.position}`;
    if (seenIds.has(page.page_id) || seenUrls.has(page.url) || seenPositions.has(positionKey))
      fail('PAGE_UNIQUE');
    seenIds.add(page.page_id); seenUrls.add(page.url); seenPositions.add(positionKey);
    const map = one(mapRows, 'map_id', mapId, 'MAP_EXACT');
    const rte = one(rteRows, 'map_id', mapId, 'RTE_EXACT');
    if (map.review_state !== READY || map.requested_path !== page.url ||
        map.proposed_type !== page.kind || map.source_h1 !== page.h1 ||
        map.source_snapshot !== page.source.relative_path ||
        map.source_sha256 !== page.source.sha256 || rte.evidence_id !== map.evidence_id ||
        rte.requested_path !== map.requested_path || rte.source_snapshot !== map.source_snapshot ||
        rte.source_sha256 !== map.source_sha256 || rte.source_h1 !== map.source_h1 ||
        rte.template_review_state !== map.review_state) fail('MAP_RTE_EXACT');
    const bytes = snapshots.get(page.source.relative_path);
    if (!bytes) fail('SOURCE_EXACT');
    requireDigest(bytes, page.source.sha256, 'SOURCE_SHA256');
    if (page.title !== titleFromSnapshot(bytes)) fail('SOURCE_TITLE');
    if (kind === 'article') {
      if (map.source_main_locator !== '//div[contains(@class,"col-lg-9")]:248')
        fail('ARTICLE_LOCATOR');
      requireArticleFacts(map.source_main_facts, shape);
      requireArticleContent(articleFragment(bytes, shape), page);
    } else if (page.blocks.length !== 0) fail('DEFERRED_CONTENT');
  });
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
  const fragment = [
    '<div class="col-lg-9 col-md-8">', '', '<div class="pagetitle">', '<i ></i>',
    '<h1>Заголовок</h1>', '</div>', '<p>Первый &ndash; абзац.</p>',
    '<ul>', '<li>&laquo;Первый&raquo;</li>', '<li>Второй &mdash; пункт</li>', '</ul>',
    '<p>До&nbsp;переноса<br />После переноса</p>', '', '', '</div>',
  ];
  const wrap = lines => Buffer.from(`${Array(247).fill('').join('\n')}\n${lines.join('\n')}\n`);
  const shape = ['p1', 'u2', 'p2'];
  const parsed = articleFragment(wrap(fragment), shape);
  if (parsed.h1 !== 'Заголовок' || parsed.blocks[0].segments[0] !== 'Первый – абзац.' ||
      parsed.blocks[1].items[0] !== '«Первый»' ||
      parsed.blocks[1].items[1] !== 'Второй — пункт' ||
      parsed.blocks[2].segments[0] !== 'До\u00a0переноса')
    fail('SELFCHECK_FRAGMENT');
  requireArticleContent(parsed, { h1: 'Заголовок', blocks: parsed.blocks });
  expectFailure('CONTENT_MISMATCH', 'ARTICLE_CONTENT', () => requireArticleContent(parsed, {
    h1: 'Заголовок', blocks: [{ type: 'paragraph', segments: ['Изменено'] },
      ...parsed.blocks.slice(1)],
  }));
  for (const [label, code, changed] of [
    ['DUPLICATE_LOCATOR', 'ARTICLE_LOCATOR',
      [...fragment, '<div class="col-lg-9 col-md-8">']],
    ['ATTRIBUTED_ITEM', 'ARTICLE_GRAMMAR', fragment.map(line => line.replace(
      '<li>Второй &mdash; пункт</li>',
      '<li class="x">Второй &mdash; пункт</li>'))],
    ['NESTED_TAG', 'ARTICLE_TEXT',
      fragment.map(line => line.replace('После переноса', '<b>После</b>'))],
    ['UNKNOWN_ENTITY', 'ARTICLE_ENTITY',
      fragment.map(line => line.replace('После переноса', 'После&copy;'))],
    ['NUMERIC_ENTITY', 'ARTICLE_ENTITY',
      fragment.map(line => line.replace('После переноса', 'После&#10;'))],
    ['RAW_AMPERSAND', 'ARTICLE_ENTITY',
      fragment.map(line => line.replace('После переноса', 'После & перенос'))],
    ['EXTRA_BREAK', 'ARTICLE_GRAMMAR', fragment.map(line => line.replace(
      'До&nbsp;переноса<br />После переноса',
      'До&nbsp;переноса<br />Лишний<br />После переноса'))],
    ['MISSING_ITEM', 'ARTICLE_GRAMMAR',
      fragment.filter(line => line !== '<li>&laquo;Первый&raquo;</li>')],
    ['MISSING_PARAGRAPH_BLOCK', 'ARTICLE_GRAMMAR',
      fragment.filter((_line, index) => index !== 6)],
    ['EXTRA_PARAGRAPH_BLOCK', 'ARTICLE_GRAMMAR',
      [...fragment.slice(0, 12), '<p>Лишний.</p>', ...fragment.slice(12)]],
    ['MISSING_LIST_BLOCK', 'ARTICLE_GRAMMAR',
      [...fragment.slice(0, 7), ...fragment.slice(11)]],
    ['EXTRA_LIST_BLOCK', 'ARTICLE_GRAMMAR',
      [...fragment.slice(0, 12), ...fragment.slice(7, 11), ...fragment.slice(12)]],
    ['REORDERED_BLOCKS', 'ARTICLE_GRAMMAR',
      [...fragment.slice(0, 6), ...fragment.slice(7, 11), fragment[6], fragment[11],
        ...fragment.slice(12)]],
    ['MISSING_WRAPPER_CLOSE', 'ARTICLE_GRAMMAR', fragment.slice(0, -1)],
  ]) expectFailure(label, code, () => articleFragment(wrap(changed), shape));
  expectFailure('MULTILINE_TEXT', 'ARTICLE_TEXT', () => plain('bad\ntext'));
  const reordered = [...fragment];
  [reordered[8], reordered[9]] = [reordered[9], reordered[8]];
  expectFailure('REORDERED_ITEM', 'ARTICLE_CONTENT', () => requireArticleContent(
    articleFragment(wrap(reordered), shape), parsed));
  requireBlocks(parsed.blocks, shape);
  expectFailure('EXTRA_BLOCK_KEY', 'PAGE_BLOCKS', () => requireBlocks([
    { type: 'paragraph', segments: ['x'], extra: true }, ...parsed.blocks.slice(1),
  ], shape));
  expectFailure('MISSING_PACKAGE_BLOCK', 'PAGE_BLOCKS',
    () => requireBlocks(parsed.blocks.slice(0, -1), shape));
  expectFailure('EXTRA_PACKAGE_BLOCK', 'PAGE_BLOCKS', () => requireBlocks([
    ...parsed.blocks, { type: 'paragraph', segments: ['extra'] },
  ], shape));
  expectFailure('REORDERED_PACKAGE_BLOCKS', 'PAGE_BLOCKS', () => requireBlocks([
    parsed.blocks[1], parsed.blocks[0], parsed.blocks[2],
  ], shape));
  expectFailure('PACKAGE_V1', 'PACKAGE_POLICY', () => validatePackage({
    schema: 'dev09-articles-slice-v1', policy: 'validated_package_not_import_authority',
    inputs: { map_sha256: MAP_SHA, evidence_sha256: RTE_SHA }, pages: [],
  }, [], [], new Map()));
  requireArticleFacts(
    'h1=True;main_chars=42;paragraphs=2;tables=0;services_lists=0;links=0;images=0;iframes=0',
    shape);
  expectFailure('MALFORMED_FACTS', 'ARTICLE_FACTS', () => requireArticleFacts(
    'h1=True;main_chars=42;paragraphs=3;tables=0;services_lists=0;links=0;images=0;iframes=0',
    shape));
  const allowed = new Set(['safe/file']);
  const fake = {
    lstatSync: () => ({ isSymbolicLink: () => false, isFile: () => true }),
    realpathSync: value => value,
  };
  requireFile('safe/file', repo, fake, allowed);
  expectFailure('PATH_ESCAPE', 'FILE_PATH',
    () => requireFile('../safe/file', repo, fake, allowed));
  expectFailure('SYMLINK', 'FILE_BOUNDARY', () => requireFile('safe/file', repo, {
    ...fake, lstatSync: () => ({ isSymbolicLink: () => true, isFile: () => true }),
  }, allowed));
  expectFailure('REALPATH_DRIFT', 'FILE_BOUNDARY', () => requireFile('safe/file', repo, {
    ...fake, realpathSync: () => path.join(repo, 'other', 'file'),
  }, allowed));
  expectFailure('EXTRA_PACKAGE_KEY', 'PACKAGE_SCHEMA', () => exactKeys(
    { schema: 'x', extra: true }, ['schema']));
  expectFailure('NONCANONICAL_PACKAGE', 'PACKAGE_CANONICAL',
    () => parsePackage(Buffer.from('{"a":1}')));
  expectFailure('DUPLICATE_PACKAGE_KEY', 'PACKAGE_CANONICAL',
    () => parsePackage(Buffer.from('{"a":1,"a":2}\n')));
  process.stdout.write('{"schema":"dev09-articles-slice-selfcheck-v2","status":"pass"}\n');
}

function check() {
  const mapBytes = read(MAP_PATH), rteBytes = read(RTE_PATH), packageBytes = read(PACKAGE_PATH);
  requireDigest(mapBytes, MAP_SHA, 'MAP_SHA256'); requireDigest(rteBytes, RTE_SHA, 'RTE_SHA256');
  const packageValue = parsePackage(packageBytes);
  const snapshots = new Map();
  for (const relative of SOURCES) snapshots.set(relative, read(relative));
  const value = validatePackage(packageValue, parseCsv(mapBytes, MAP_HEADER),
    parseCsv(rteBytes, RTE_HEADER), snapshots);
  process.stdout.write(`${JSON.stringify({ schema: 'dev09-articles-slice-check-v2',
    policy: value.policy, status: 'pass', pages: IDS,
    counts: { pages: 20, deferred: 2, sourceTextCompleteMediaDeferred: 18 },
    writes: 0, published: 0 })}\n`);
}

try {
  if (process.argv.length !== 3 || !['--check', '--selfcheck'].includes(process.argv[2]))
    fail('USAGE');
  if (process.argv[2] === '--selfcheck') selfcheck(); else check();
} catch (error) {
  const code = /^[A-Z0-9_]+$/u.test(error?.code ?? '') ? error.code : 'INTERNAL';
  process.stderr.write(`DEV09_ARTICLES_SLICE_ERROR ${code}\n`);
  process.exitCode = 1;
}
