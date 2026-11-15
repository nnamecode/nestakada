// DEV-09N host-only, read-only validator. It never imports or publishes data.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PACKAGE = 'app/content/dev09n_remaining_content.json';
const PACKAGE_SHA = '4b679b676b5e1ba1d2a5971799695d8ef944da9015c1f2270aee9d8878f09c30';
const AUTHORITIES = [
  ['docs/analytics-route-map.csv', 128 * 1024,
    'c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8'],
  ['docs/analytics-route-evidence.csv', 256 * 1024,
    'c3a8a395fb4ed55fef6027a58014ce5decaadda7c559870bf06247c2fbeb79bc'],
  ['docs/analytics-media-evidence.csv', 256 * 1024,
    '59fd85967e36d39a9d9f9a4a9ab8eda6b63457e1649107a434d184846e759601'],
];
const ROOT = 'e80c3de1-feea-4847-b550-325a825ffc0e';
const NEWS = 'da5e675f-fedf-4c4e-a3b4-c82d6a6dafcb';
const PAGES = [
  ['MAP-003', 'ffdbdc65-39d8-4e22-88e3-7e44e752fbde', '/partners',
    'legacy_partner_links', ROOT, 3, 'work/site-audit/crawl/47603c27b74b562c849f.html',
    '63afb07928c3074fb795bf46b275f8b5d539db35a7f031f6df99ee19e5a08b71'],
  ['MAP-004', 'b427b1b8-2fb9-44cd-a301-5b14f2f991b2', '/actions',
    'actions', ROOT, 5, 'work/site-audit/crawl/3133b886374780db941f.html',
    '89959fb0ecfb5a83d70d9a22ca38708907fef008fab697968e3f95314e70449d'],
  ['MAP-005', 'df6b50bb-d749-4106-b053-2999e0335223', '/reviews',
    'reviews', ROOT, 6, 'work/site-audit/crawl/eb8219cbca1aa49e96d8.html',
    '322102551a51d472305c22d408396302f1a23106eaf2c2fd90eabd67221d9b64'],
  ['MAP-007', '91631e35-5e81-407f-806b-e973223d7340', '/contacts',
    'contacts', ROOT, 7, 'work/site-audit/crawl/6f2460775068eaa289d1.html',
    'fa3518936b0a2f9fd277378e66ba9fed67641c949422335cb5cc1b2014e47ac0'],
  ['MAP-009', '87cf5862-20fd-4ad3-b90c-bb4d6e888355', '/direct-contact',
    'legacy_director_message', ROOT, 8, 'work/site-audit/crawl/f52091cb91f84127f6fc.html',
    '8c3465e86ecf84dcc629485eb5958df83f861af039c9481d3f19e3fc5af31a2f'],
  ['MAP-044', 'e3c55ade-799b-4118-88b8-3fb03deea235', '/nash-servisnyij-czentr',
    'legacy_empty_main', ROOT, 9, 'work/site-audit/crawl/ca8ca7fba5644aa2c1bd.html',
    'b045ddf3e628459fe0094239eae8841b68ae2251f789422aced4043606573daf'],
  ['MAP-049', '9b5b3c53-d8c7-4395-89e5-6d07645f0d61', '/about',
    'legacy_empty_main', ROOT, 10, 'work/site-audit/crawl/8e314bdb2ebde8cb9356.html',
    '9d37c9663551c31748224e33265f5e181b013671b162c96cb02127af8b3cc1e4'],
  ['MAP-078', NEWS, '/news/', 'legacy_news_catalog', ROOT, 11,
    'work/site-audit/crawl/c73906bf9371c4f9b024.html',
    '7341b2a1cbcbf9dc0655ba45e0def685af3bc1007deafbebce09ad840f0cbc1c'],
  ['MAP-090', '62228d71-44ce-44da-82b5-85ba9c7d93dd', '/garantii',
    'legacy_under_construction', ROOT, 12, 'work/site-audit/crawl/5dad9bce323c991924d7.html',
    '29e5a2aae9ce8c4f30a9078a148afe23840dfcc8a3430f25a79caf146f561ccd'],
  ['MAP-097', 'f30b0e81-5ac6-4779-bb0e-65dc3ae5c301', '/cctv',
    'legacy_camera_schedule_text', ROOT, 13, 'work/site-audit/crawl/5c43976d69bd9ce64ed8.html',
    '89c78095b10cb0888d129da85947ec30cf63e6b5c0f9e0c98520d31d079f7013'],
  ['MAP-045', '13fe0f8c-001c-446a-8cb7-b588fcdb1916',
    '/news/priobretenie-podemnika-do-10-tonn-dlya-remonta-malotonnazhnyix-avtomobilej',
    'legacy_news_article', NEWS, 0, 'work/site-audit/crawl/04614bb6eacfa8f3a4e4.html',
    '61f814922b0bfc17759ece7fb9141c90c49376d2d6633cbf536e8e0788c980ab'],
  ['MAP-039', 'f1c97615-2220-4732-a9cb-d5979d6500b2',
    '/news/atcz-estakada-podklyuchila-mnogokanalnyij-telefon',
    'legacy_news_article', NEWS, 1, 'work/site-audit/crawl/c4e52e3c290d204f9560.html',
    '6fa269bb6569b0a38174beb8e91186a0e8f5fe48865ed1df4193b0548559beb3'],
  ['MAP-033', '06f43591-ff13-4409-89ef-823534b5b33e',
    '/news/okazanie-dopolnitelnyix-uslug', 'legacy_news_article', NEWS, 2,
    'work/site-audit/crawl/d0afd77f4753d8dd50ef.html',
    '2456222b91910ab23d444ea49520232a8b69fb3f580659a765aa6ab37944a3f3'],
];
const MEDIA = [
  ['MED-0001', '89f6efb6-b243-4fc8-80ec-a61dc5393ef8',
    'cdad24a4-91f9-451f-9c59-fa9f305f3a77', 'edd55fd1-91cf-4e20-8cfc-2f5e9861dcc1',
    'media/design-concepts/actions-v4/first-visit-discount-v1.webp', 151726,
    'be710512d347e6b4d529240817edb9050df9d5daf61bd4efcf4c02b5b2c262bc'],
  ['MED-0002', '70dab673-6a5f-4274-947a-7bf8efc5e029',
    '6488fe3d-cef6-484a-aa48-a2fa0291ae0b', '0721a988-5dc4-42a4-b73e-8bb2f27705ca',
    'media/design-concepts/actions-v4/sunday-repair-discount-v1.webp', 222598,
    'df13ba501d57cbade361225c90f34d1276f7fbff5911217624569a2d319cd02a'],
  ['MED-0004', '6bd3397f-d79e-4542-bf2a-168bf8eefd14',
    'efb52c4a-3926-4eee-b7a5-c8d7c3d6d923', '4f680d0d-66e0-41a4-8361-6a85b84d9bba',
    'media/design-concepts/contacts-v4/body-shop-exterior-clean-light-v1.webp', 191734,
    '8fc2142538ad2f7c3a0016df89f3d3f90df2da37d03bd1b39135e95f810c3df5'],
  ['MED-0005', 'cdaba860-0d92-4c28-a340-d392cf5412ab',
    '012aeb12-0028-4da8-a74f-64c2ccc07538', '94c7fa00-3395-465f-abbe-d991bedbcd0e',
    'media/design-concepts/contacts-v4/reception-v1.jpg', 190431,
    '68fb97e86a37c2361686bb057590d602b951fca6eb269725813265915a2472ad'],
  ['MED-0006', 'e1f19d53-5811-4166-858d-35308ae853c1',
    '6e1eeea7-b8ae-4f08-a71f-fbc9d0983dd6', '5857c071-6e81-460d-9fac-519bae6a0ebc',
    'media/design-concepts/contacts-v4/service-reception-v1.jpg', 189101,
    'e7e0b315e4fd6f192713476680f2cee5ba830983def383b0c1f43f72a9cfcec0'],
  ['MED-0007', 'ac6af51d-a08b-47bb-b818-0c84e13e7050',
    '5ef31b85-ec14-49a7-a944-e5c62fcb977e', '7efdc034-f931-4397-be93-fe503a19eeca',
    'media/design-concepts/contacts-v4/waiting-area-v1.jpg', 247402,
    '5f8dd608684af7baf484397c77d9a9cc3805cc7bd9255df1079646f1b79df8e9'],
  ['MED-0008', '27fe380b-0728-489a-b7cf-64a47aea9c14',
    '29f355a7-3a9f-4692-8295-0591afbe4f5c', '191e8b95-af10-423e-9507-59a7c62be591',
    'media/design-concepts/photo-strip-v4/exterior-bays-bright-v1.webp', 201684,
    '640bc75001fede5e3c29c85ca2629af2263770da5014339edc0e5def9d83d43f'],
];
const ARTIFACTS = new Map([
  ['MAP-004', ['work/actions.html', '241e51df9338276f9a2f6ad6e41403bcdb6dedde265eaed427ec569f4b18b0ce']],
  ['MAP-005', ['work/reviews.html', '5c8e8d193106da4cd1ba3ac76be6111acc5a9085d6310df15a9fed41143974f1']],
  ['MAP-007', ['work/contacts.html', '9d0e6f7b3a9c7eb0ff0c3afb8d235c70d13fd6fc23703a5b4e2dbb8ee5fcce6e']],
]);
const ALLOWED = new Set([PACKAGE, ...AUTHORITIES.map(row => row[0]),
  ...PAGES.map(row => row[6]), ...MEDIA.map(row => row[4]),
  ...[...ARTIFACTS.values()].map(row => row[0])]);

function fail(code) { const error = new Error(code); error.code = code; throw error; }
function digest(bytes) { return crypto.createHash('sha256').update(bytes).digest('hex'); }
function exactKeys(value, keys, code = 'PACKAGE_SCHEMA') {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).length !== keys.length ||
      Object.keys(value).some((key, index) => key !== keys[index])) fail(code);
}
function maxBytes(bytes, cap, code) { if (bytes.length > cap) fail(code); }
function maxCount(values, cap, code) { if (values.length > cap) fail(code); }
function decode(bytes, code) {
  try { return new TextDecoder('utf-8', { fatal: true }).decode(bytes); }
  catch { fail(code); }
}
function read(relative, cap, io = fs) {
  if (!ALLOWED.has(relative) || relative.includes('..') || path.isAbsolute(relative))
    fail('FILE_PATH');
  const absolute = path.resolve(repo, ...relative.split('/'));
  const rel = path.relative(repo, absolute);
  if (!rel || rel.startsWith('..') || path.isAbsolute(rel)) fail('FILE_PATH');
  let stat; let real;
  try { stat = io.lstatSync(absolute); real = io.realpathSync(absolute); }
  catch { fail('FILE_ACCESS'); }
  if (!stat.isFile() || stat.isSymbolicLink() ||
      path.normalize(real).toLowerCase() !== path.normalize(absolute).toLowerCase())
    fail('FILE_BOUNDARY');
  if (stat.size > cap) fail('FILE_CAP');
  let bytes;
  try { bytes = io.readFileSync(absolute); } catch { fail('FILE_ACCESS'); }
  maxBytes(bytes, cap, 'FILE_CAP');
  return bytes;
}
function pinned(relative, cap, sha, io = fs) {
  const bytes = read(relative, cap, io);
  if (digest(bytes) !== sha) fail('FILE_SHA256');
  return bytes;
}
function parsePackage(bytes) {
  const text = decode(bytes, 'PACKAGE_UTF8');
  if (text.includes('\r')) fail('PACKAGE_CR');
  let value;
  try { value = JSON.parse(text); } catch { fail('PACKAGE_JSON'); }
  if (`${JSON.stringify(value, null, 2)}\n` !== text) fail('PACKAGE_CANONICAL');
  return value;
}
function same(actual, expected, code = 'PACKAGE_IDENTITY') {
  if (actual !== expected) fail(code);
}
function unique(values, code) { if (new Set(values).size !== values.length) fail(code); }
function visitStrings(value, callback) {
  if (typeof value === 'string') callback(value);
  else if (Array.isArray(value)) value.forEach(item => visitStrings(item, callback));
  else if (value && typeof value === 'object') Object.values(value)
    .forEach(item => visitStrings(item, callback));
}
function pageBlockCount(profile) {
  if (profile.type === 'paragraphs') return profile.paragraphs.length;
  if (profile.type === 'actions') return profile.cards.length;
  if (profile.type === 'reviews') return profile.videos.length + 1;
  if (profile.type === 'contacts') return profile.image_ids.length;
  if (profile.type === 'partners' || profile.type === 'links') return profile.items.length;
  if (profile.type === 'news_catalog')
    return profile.items.length + profile.items.reduce((total, item) => total + item.blocks.length, 0);
  return 0;
}
function pageLinkCount(profile) {
  let count = 0;
  const walk = value => {
    if (Array.isArray(value)) value.forEach(walk);
    else if (value && typeof value === 'object') {
      for (const [key, child] of Object.entries(value)) {
        if (key === 'url' || key.endsWith('_href')) count += 1;
        walk(child);
      }
    }
  };
  walk(profile); return count;
}
function validateProfiles(pages, media) {
  const byMap = new Map(pages.map(page => [page.map_id, page]));
  const partner = byMap.get('MAP-003').profile;
  exactKeys(partner, ['type', 'items']); same(partner.type, 'partners'); same(partner.items.length, 6);
  for (const item of partner.items) {
    exactKeys(item, ['text', 'url', 'label']);
    if (!item.url.startsWith('http://') || !item.label.startsWith('www.')) fail('PARTNER_LINK');
  }
  const actions = byMap.get('MAP-004').profile;
  exactKeys(actions, ['type', 'cards']); same(actions.type, 'actions'); same(actions.cards.length, 2);
  for (const card of actions.cards) exactKeys(card, ['heading', 'text', 'image_id']);
  const reviews = byMap.get('MAP-005').profile;
  exactKeys(reviews, ['type', 'intro', 'videos']); same(reviews.type, 'reviews'); same(reviews.videos.length, 10);
  reviews.videos.forEach((video, index) => {
    exactKeys(video, ['title', 'url']);
    same(video.title, `ВИДЕО-ОТЗЫВ ${String(index + 1).padStart(2, '0')}`);
    if (!video.url.startsWith('https://www.youtube.com/watch?v=')) fail('REVIEW_LINK');
  });
  const contacts = byMap.get('MAP-007').profile;
  exactKeys(contacts, ['type', 'phone_display', 'phone_href', 'address', 'hours',
    'email_display', 'email_href', 'route_href', 'gallery_heading', 'image_ids']);
  same(contacts.type, 'contacts'); same(contacts.phone_display, '+7 (499) 110-25-52');
  same(contacts.phone_href, 'tel:+74991102552');
  same(contacts.email_display, 'estakada10@yandex.ru');
  same(contacts.email_href, 'mailto:estakada10@yandex.ru');
  same(contacts.route_href, 'https://yandex.ru/maps/org/57771430682');
  same(contacts.image_ids.length, 5);
  const contactOrder = [
    '191e8b95-af10-423e-9507-59a7c62be591',
    '4f680d0d-66e0-41a4-8361-6a85b84d9bba',
    '94c7fa00-3395-465f-abbe-d991bedbcd0e',
    '7efdc034-f931-4397-be93-fe503a19eeca',
    '5857c071-6e81-460d-9fac-519bae6a0ebc',
  ];
  contacts.image_ids.forEach((id, index) => same(id, contactOrder[index]));
  const imageIds = new Set(media.map(item => item.image_id));
  [...actions.cards.map(card => card.image_id), ...contacts.image_ids]
    .forEach(id => { if (!imageIds.has(id)) fail('MEDIA_REFERENCE'); });
  const shapes = new Map([
    ['MAP-009', ['type', 'paragraphs']], ['MAP-044', ['type']],
    ['MAP-049', ['type']], ['MAP-078', ['type', 'items']],
    ['MAP-090', ['type', 'paragraphs']], ['MAP-097', ['type', 'paragraphs']],
    ['MAP-045', ['type', 'paragraphs']], ['MAP-039', ['type', 'paragraphs']],
    ['MAP-033', ['type', 'items']],
  ]);
  for (const [mapId, keys] of shapes) exactKeys(byMap.get(mapId).profile, keys);
  same(byMap.get('MAP-044').profile.type, 'empty');
  same(byMap.get('MAP-049').profile.type, 'empty');
  same(byMap.get('MAP-078').profile.type, 'news_catalog');
  const newsItems = byMap.get('MAP-078').profile.items;
  same(newsItems.length, 3);
  newsItems.forEach(item => exactKeys(item, ['title', 'date', 'url', 'blocks']));
  newsItems.slice(0, 2).forEach(item => {
    same(item.blocks.length, 1); exactKeys(item.blocks[0], ['type', 'text']);
    same(item.blocks[0].type, 'paragraph');
  });
  same(newsItems[2].blocks.length, 1);
  exactKeys(newsItems[2].blocks[0], ['type', 'items']);
  same(newsItems[2].blocks[0].type, 'links'); same(newsItems[2].blocks[0].items.length, 4);
  newsItems[2].blocks[0].items.forEach(item => exactKeys(item, ['text', 'url']));
  same(byMap.get('MAP-033').profile.type, 'links');
  for (const mapId of ['MAP-009', 'MAP-090', 'MAP-097', 'MAP-045', 'MAP-039'])
    same(byMap.get(mapId).profile.type, 'paragraphs');
  const serialized = JSON.stringify(pages);
  if (/8\s*\(903\)\s*772-33-43/u.test(serialized) ||
      /<(?:iframe|script|form)\b|javascript:|data:/iu.test(serialized)) fail('FORBIDDEN_CONTENT');
  let renderedTotal = 0;
  for (const page of pages) {
    maxCount(new Array(pageBlockCount(page.profile)), 64, 'BLOCK_CAP');
    maxCount(new Array(pageLinkCount(page.profile)), 16, 'LINK_CAP');
    visitStrings(page, value => maxBytes(Buffer.from(value), 8 * 1024, 'TEXT_CAP'));
    const rendered = Buffer.from(JSON.stringify({ name: page.name, h1: page.h1,
      title: page.title, description: page.description, profile: page.profile }));
    maxBytes(rendered, 64 * 1024, 'RENDERED_PAGE_CAP'); renderedTotal += rendered.length;
  }
  maxBytes(Buffer.alloc(renderedTotal), 512 * 1024, 'RENDERED_TOTAL_CAP');
}
function validatePackage(value, io = fs) {
  exactKeys(value, ['schema', 'policy', 'inputs', 'media_folder', 'media', 'pages']);
  same(value.schema, 'dev09n-remaining-content-v1');
  same(value.policy, 'owner-approved-exact13-no-external-embeds');
  exactKeys(value.inputs, ['map_sha256', 'route_evidence_sha256',
    'media_evidence_sha256', 'identity_manifest']);
  AUTHORITIES.forEach((row, index) => same(Object.values(value.inputs)[index], row[2]));
  same(value.inputs.identity_manifest, 'docs/dev09n-remaining-exact13-manifest.md');
  exactKeys(value.media_folder, ['id', 'path', 'provenance']);
  same(value.media_folder.id, '53e5e79f-3aca-40c7-a130-c025bdde8a8b');
  same(value.media_folder.path, 'dev09n/remaining-content');
  same(value.media_folder.provenance, 'DEV09N owner-approved remaining content');
  if (!Array.isArray(value.pages) || value.pages.length !== 13 ||
      !Array.isArray(value.media) || value.media.length !== 7) fail('PACKAGE_COUNT');
  value.pages.forEach((page, index) => {
    const expected = PAGES[index]; const artifact = ARTIFACTS.get(expected[0]);
    exactKeys(page, artifact ? ['page_id', 'map_id', 'url', 'kind', 'parent_id',
      'position', 'name', 'h1', 'title', 'description', 'is_published', 'source',
      'artifact', 'profile'] : ['page_id', 'map_id', 'url', 'kind', 'parent_id',
      'position', 'name', 'h1', 'title', 'description', 'is_published', 'source', 'profile']);
    [page.map_id, page.page_id, page.url, page.kind, page.parent_id, page.position]
      .forEach((field, fieldIndex) => same(field, expected[fieldIndex]));
    same(page.is_published, false); exactKeys(page.source, ['relative_path', 'sha256']);
    same(page.source.relative_path, expected[6]); same(page.source.sha256, expected[7]);
    pinned(expected[6], 128 * 1024, expected[7], io);
    if (artifact) {
      exactKeys(page.artifact, ['relative_path', 'sha256']);
      same(page.artifact.relative_path, artifact[0]); same(page.artifact.sha256, artifact[1]);
      pinned(artifact[0], 128 * 1024, artifact[1], io);
    }
  });
  let mediaTotal = 0;
  value.media.forEach((item, index) => {
    const expected = MEDIA[index];
    exactKeys(item, ['evidence_id', 'asset_id', 'file_id', 'image_id', 'relative_path',
      'storage_key', 'bytes', 'sha256', 'alt']);
    [item.evidence_id, item.asset_id, item.file_id, item.image_id, item.relative_path,
      item.bytes, item.sha256].forEach((field, fieldIndex) => same(field, expected[fieldIndex]));
    const extension = path.extname(item.relative_path);
    same(item.storage_key, `img/${item.asset_id}/original${extension}`);
    pinned(item.relative_path, 256 * 1024, item.sha256, io);
    mediaTotal += item.bytes;
  });
  if (mediaTotal > 2 * 1024 * 1024) fail('MEDIA_TOTAL_CAP');
  unique(value.pages.map(page => page.page_id), 'PAGE_ID_DUPLICATE');
  unique(value.pages.map(page => page.url), 'PAGE_URL_DUPLICATE');
  unique(value.media.flatMap(item => [item.asset_id, item.file_id, item.image_id]), 'MEDIA_ID_DUPLICATE');
  unique(value.pages.filter(page => page.parent_id === ROOT).map(page => page.position), 'ROOT_POSITION_DUPLICATE');
  unique(value.pages.filter(page => page.parent_id === NEWS).map(page => page.position), 'NEWS_POSITION_DUPLICATE');
  validateProfiles(value.pages, value.media);
}
function check() {
  const packageBytes = pinned(PACKAGE, 128 * 1024, PACKAGE_SHA);
  AUTHORITIES.forEach(row => pinned(...row));
  const value = parsePackage(packageBytes);
  validatePackage(value);
  process.stdout.write(JSON.stringify({ schema: value.schema, status: 'pass', pages: 13,
    media: 7, writes: 0, network: 0, child_processes: 0 }) + '\n');
}
function selfcheck() {
  const bytes = read(PACKAGE, 128 * 1024); const value = parsePackage(bytes);
  const expect = (code, mutate) => {
    const candidate = structuredClone(value); mutate(candidate);
    try { validatePackage(candidate); fail('SELFCHECK_MISSED'); }
    catch (error) { if (error.code !== code) throw error; }
  };
  const byteBoundary = (code, cap) => {
    maxBytes(Buffer.alloc(cap), cap, code);
    try { maxBytes(Buffer.alloc(cap + 1), cap, code); fail('SELFCHECK_MISSED'); }
    catch (error) { if (error.code !== code) throw error; }
  };
  const countBoundary = (code, cap) => {
    maxCount(new Array(cap), cap, code);
    try { maxCount(new Array(cap + 1), cap, code); fail('SELFCHECK_MISSED'); }
    catch (error) { if (error.code !== code) throw error; }
  };
  byteBoundary('PACKAGE_CAP', 128 * 1024);
  byteBoundary('ROUTE_MAP_CAP', 128 * 1024);
  byteBoundary('ROUTE_EVIDENCE_CAP', 256 * 1024);
  byteBoundary('MEDIA_EVIDENCE_CAP', 256 * 1024);
  byteBoundary('SOURCE_CAP', 128 * 1024);
  byteBoundary('ARTIFACT_CAP', 128 * 1024);
  byteBoundary('MEDIA_FILE_CAP', 256 * 1024);
  byteBoundary('MEDIA_TOTAL_CAP', 2 * 1024 * 1024);
  countBoundary('BLOCK_CAP', 64); countBoundary('LINK_CAP', 16);
  byteBoundary('TEXT_CAP', 8 * 1024);
  byteBoundary('RENDERED_PAGE_CAP', 64 * 1024);
  byteBoundary('RENDERED_TOTAL_CAP', 512 * 1024);
  let preReadCalled = false;
  const oversizedIo = {
    lstatSync: () => ({ isFile: () => true, isSymbolicLink: () => false, size: 2 }),
    realpathSync: absolute => absolute,
    readFileSync: () => { preReadCalled = true; return Buffer.alloc(2); },
  };
  try { read(PACKAGE, 1, oversizedIo); fail('SELFCHECK_MISSED'); }
  catch (error) { if (error.code !== 'FILE_CAP' || preReadCalled) throw error; }
  expect('PACKAGE_IDENTITY', candidate => { candidate.pages[0].url = '/changed'; });
  expect('FORBIDDEN_CONTENT', candidate => { candidate.pages[4].profile.paragraphs.push('<script>'); });
  expect('PACKAGE_IDENTITY', candidate => { candidate.media[0].bytes += 1; });
  process.stdout.write('{"schema":"dev09n-slice-selfcheck-v1","status":"pass"}\n');
}

try {
  if (process.argv.length !== 3 || !['--check', '--selfcheck'].includes(process.argv[2])) fail('USAGE');
  if (process.argv[2] === '--selfcheck') selfcheck(); else check();
} catch (error) {
  process.stderr.write(`${error.code || 'INTERNAL'}\n`);
  process.exitCode = 1;
}
