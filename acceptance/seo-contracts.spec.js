import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';
import { localTarget } from './test-support.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await use(app); } finally { await app.close(); }
} });
test.use({ javaScriptEnabled: false, serviceWorkers: 'block' });
const parserPages = new WeakSet();
const paths = {
  live: '/acceptance/seo/published/', second: '/acceptance/seo/second/', hidden: '/acceptance/seo/hidden/',
  noindex: '/acceptance/seo/noindex/', deleted: '/acceptance/seo/deleted/', redirect: '/acceptance/seo/old/',
  private: '/acceptance/seo/private/', alias: '/acceptance/seo/alias/', query: '/acceptance/seo/published/?tracking=one',
  draft: '/acceptance/seo/draft/',
};
const required = value => { expect(typeof value).toBe('string'); expect(value.length).toBeGreaterThan(0); return value; };
const absolute = route => new URL(route, localTarget(process.env.ESTAKADA_TEST_BASE_URL)).href;
const eligible = () => ['/', paths.live, paths.second].map(absolute).sort();
const response = value => {
  expect(Number.isInteger(value.status)).toBe(true); expect(typeof value.body).toBe('string');
  required(value.contentType); return value;
};
async function sitemap(app, page) {
  if (!parserPages.has(page)) {
    await page.route('**/*', route => route.abort());
    await page.routeWebSocket('**/*', socket => socket.close());
    parserPages.add(page);
  }
  const actual = response(await app.observe('seo-sitemap-response'));
  expect(actual.status).toBe(200); expect(actual.contentType).toMatch(/^application\/xml(?:;|$)/i);
  expect(actual.body.length).toBeGreaterThan(0);
  const parsed = await page.evaluate(source => {
    const xml = new DOMParser().parseFromString(source, 'application/xml');
    return { errorCount: xml.querySelectorAll('parsererror').length, root: xml.documentElement.localName,
      namespace: xml.documentElement.namespaceURI, entries: [...xml.getElementsByTagNameNS('http://www.sitemaps.org/schemas/sitemap/0.9', 'url')].map(node => ({
        locs: [...node.getElementsByTagNameNS('http://www.sitemaps.org/schemas/sitemap/0.9', 'loc')].map(item => item.textContent),
        lastmods: [...node.getElementsByTagNameNS('http://www.sitemaps.org/schemas/sitemap/0.9', 'lastmod')].map(item => item.textContent),
      })) };
  }, actual.body);
  expect(parsed.errorCount).toBe(0); expect(parsed.root).toBe('urlset');
  expect(parsed.namespace).toBe('http://www.sitemaps.org/schemas/sitemap/0.9');
  expect(parsed.entries.length).toBeGreaterThan(0);
  const urls = parsed.entries.map(entry => { expect(entry.locs).toHaveLength(1); return required(entry.locs[0]); });
  expect(new Set(urls).size).toBe(urls.length);
  for (const url of urls) expect(new URL(url).origin).toBe(localTarget(process.env.ESTAKADA_TEST_BASE_URL).origin);
  return { ...actual, entries: parsed.entries, urls };
}
async function metadata(app, material) {
  const actual = response(await app.observe('seo-public-response', { material }));
  for (const key of ['canonicalUrls', 'jsonLd', 'descriptionValues']) expect(Array.isArray(actual[key])).toBe(true);
  return actual;
}
async function changeIndexing(app, material, indexable) {
  const current = await app.observe('seo-page-state', { material }); required(current.revision);
  expect((await app.act('OWNER', 'set-page-indexing-direct', { material, base: current.revision, indexable })).outcome).toBe('accepted');
}
function repairNodes(actual) {
  const result = [];
  const visit = (node, context) => {
    if (Array.isArray(node)) { node.forEach(item => visit(item, context)); return; }
    expect(node && typeof node === 'object').toBeTruthy();
    const effectiveContext = node['@context'] ?? context;
    const types = Array.isArray(node['@type']) ? node['@type'] : [node['@type']];
    if (types.includes('AutoRepair')) result.push({ ...node, '@context': effectiveContext });
    if (node['@graph']) visit(node['@graph'], effectiveContext);
  };
  actual.jsonLd.forEach(node => visit(node, undefined)); return result;
}
function robotsProfile(body) {
  const groups = [], sitemaps = [], forbiddenNoindex = [];
  let current = { agents: [], rules: [] };
  for (const raw of body.split(/\r?\n/)) {
    const line = raw.replace(/#.*/, '').trim(); if (!line) continue;
    const at = line.indexOf(':'); if (at < 0) continue;
    const name = line.slice(0, at).trim().toLowerCase(), value = line.slice(at + 1).trim();
    if (name === 'user-agent') {
      if (current.rules.length) { groups.push(current); current = { agents: [], rules: [] }; }
      current.agents.push(value.toLowerCase());
    } else if (name === 'allow' || name === 'disallow') current.rules.push({ name, value });
    else if (name === 'sitemap') sitemaps.push(value);
    else if (name === 'noindex') forbiddenNoindex.push(value);
  }
  groups.push(current);
  return { starRules: groups.filter(group => group.agents.includes('*')).flatMap(group => group.rules),
    hasWildcardGroup: groups.some(group => group.agents.includes('*')), sitemaps, forbiddenNoindex };
}
function effectiveAllow(rules, target) {
  // Deliberately limited to these independent ASCII fixture paths/rules.
  // Fail explicitly rather than guessing UTF-8/percent-normalization behavior.
  if (!target.startsWith('/') || /[^\x21-\x7e]|%|#/.test(target)) throw new Error('SEO_ROBOTS_UNSUPPORTED_FIXTURE_PATH');
  let longest = -1, allow = true;
  for (const rule of rules) {
    if (!rule.value) continue;
    if (!rule.value.startsWith('/') || /[^\x21-\x7e]|%|#/.test(rule.value)) throw new Error('SEO_ROBOTS_UNSUPPORTED_RULE_ENCODING');
    const anchored = rule.value.endsWith('$');
    const normalized = anchored ? rule.value : rule.value.replace(/\*+$/, '');
    const pattern = anchored ? normalized.slice(0, -1) : normalized;
    const escaped = pattern.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*');
    if (!new RegExp('^' + escaped + (anchored ? '$' : '')).test(target)) continue;
    const specificity = normalized.length;
    if (specificity > longest) { longest = specificity; allow = rule.name === 'allow'; }
    else if (specificity === longest && rule.name === 'allow') allow = true;
  }
  return allow;
}

test('SEO-sitemap-exact | AT-061 AT-602 AC-061 AC-SEO-002 | raw XML contains exactly the independent eligible fixture set', async ({ app, page }) => {
  await app.reset('seo-index-state-matrix');
  expect((await sitemap(app, page)).urls.sort()).toEqual(eligible());
});
for (const kind of ['hidden', 'noindex', 'deleted', 'redirect', 'private', 'alias', 'query', 'draft']) {
  test(`SEO-sitemap-excludes-${kind} | AT-061 AT-602 AC-061 AC-SEO-002 | excluded material is absent while real eligible pages remain`, async ({ app, page }) => {
    await app.reset('seo-index-state-matrix');
    const xml = await sitemap(app, page);
    expect(xml.urls).not.toContain(absolute(paths[kind]));
    expect(xml.urls.sort()).toEqual(eligible());
  });
}
test('SEO-sitemap-index-transition | AT-011 AT-602 AC-011 AC-SEO-002 | owner noindex removes the actual page and reallow restores it without touching old SEO', async ({ app, page }) => {
  await app.reset('seo-index-state-matrix');
  const initial = await app.observe('seo-page-state', { material: 'P-LIVE' });
  for (const key of ['title', 'h1', 'description']) required(initial[key]);
  expect((await sitemap(app, page)).urls).toContain(absolute(paths.live));
  await changeIndexing(app, 'P-LIVE', false);
  expect((await sitemap(app, page)).urls.sort()).toEqual(eligible().filter(url => url !== absolute(paths.live)));
  const hiddenFromSearch = await metadata(app, 'P-LIVE');
  expect(hiddenFromSearch.status).toBe(200); expect(hiddenFromSearch.body).toContain('SEO-PUBLISHED-CANARY');
  expect(required(hiddenFromSearch.xRobotsTag)).toMatch(/\bnoindex\b/i);
  await changeIndexing(app, 'P-LIVE', true);
  expect((await sitemap(app, page)).urls.sort()).toEqual(eligible());
  const final = await app.observe('seo-page-state', { material: 'P-LIVE' });
  for (const key of ['title', 'h1', 'description']) expect(final[key]).toBe(initial[key]);
});
test('SEO-sitemap-lastmod | AT-602 AC-SEO-002 | lastmod comes from actual source changes, not request time', async ({ app, page }) => {
  await app.reset('seo-index-state-matrix');
  const first = await sitemap(app, page), second = await sitemap(app, page);
  const entry = first.entries.find(item => item.locs[0] === absolute(paths.live)); expect(entry).toBeTruthy();
  expect(entry.lastmods).toEqual(['2026-10-01T08:30:00Z']);
  expect(second.entries.find(item => item.locs[0] === absolute(paths.live)).lastmods).toEqual(entry.lastmods);
  const unknown = first.entries.find(item => item.locs[0] === absolute(paths.second)); expect(unknown).toBeTruthy();
  expect(unknown.lastmods).toHaveLength(0);
});

test('SEO-robots-production | AT-061 AT-603 AC-061 AC-SEO-003 | actual production-profile robots is text and does not block the entire site', async ({ app }) => {
  await app.reset('seo-index-state-matrix');
  const actual = response(await app.observe('seo-robots-response'));
  expect(actual.status).toBe(200); expect(actual.contentType).toMatch(/^text\/plain(?:;|$)/i);
  const profile = robotsProfile(actual.body); expect(profile.hasWildcardGroup).toBe(true);
  for (const route of ['/', paths.live, paths.second, '/assets/seo-fixture.css', '/assets/seo-fixture.js', '/img/seo-fixture-image.jpg'])
    expect(effectiveAllow(profile.starRules, route), `wildcard policy must allow required fixture path ${route}`).toBe(true);
  expect(profile.forbiddenNoindex).toHaveLength(0);
  expect(profile.sitemaps).toContain(absolute('/sitemap.xml'));
});
for (const number of [1, 2]) {
  test(`SEO-robots-gallery-${number} | AT-603 AC-SEO-003 | exact accepted gallery query exception remains present`, async ({ app }) => {
    await app.reset('seo-index-state-matrix');
    const actual = response(await app.observe('seo-robots-response')); expect(actual.status).toBe(200);
    const rules = robotsProfile(actual.body).starRules;
    expect(rules).toContainEqual({ name: 'allow', value: `/gallery-of-works/?page=${number}$` });
    expect(effectiveAllow(rules, `/gallery-of-works/?page=${number}`)).toBe(true);
    expect(effectiveAllow(rules, `/gallery-of-works/?page=${number}&tracking=one`)).toBe(false);
  });
}
test('SEO-robots-no-secret-list | AT-603 AC-SEO-003 | secret object/cookie paths are not advertised in raw robots', async ({ app }) => {
  await app.reset('seo-index-state-matrix');
  const actual = response(await app.observe('seo-robots-response')); expect(actual.status).toBe(200);
  for (const canary of ['/SEO-SECRET-DOCUMENT-CANARY/', 'SEO-SYNTHETIC-SESSION-CANARY', '/local/private/backup-seo-fixture/']) expect(actual.body).not.toContain(canary);
});

for (const [material, status, canary] of [['P-HIDDEN', 200, 'SEO-HIDDEN-CANARY'], ['P-NOINDEX', 200, 'SEO-NOINDEX-CANARY'], ['P-DELETED', 404, 'SEO-DELETED-CANARY']]) {
  test(`SEO-public-state-${material} | AT-061 AT-603 AC-061 AC-SEO-003 | real response preserves HTTP state instead of indexing metadata`, async ({ app }) => {
    await app.reset('seo-index-state-matrix'); const actual = await metadata(app, material);
    expect(actual.status).toBe(status); expect(actual.canonicalUrls).toHaveLength(0); expect(repairNodes(actual)).toHaveLength(0);
    if (material === 'P-NOINDEX') {
      expect(actual.body).toContain(canary); expect(required(actual.xRobotsTag)).toMatch(/\bnoindex\b/i); expect(actual.xRobotsTag).toMatch(/(?:^|[,\s])follow(?:$|[,\s])/i);
    } else {
      expect(actual.body).not.toContain(canary);
      if (material === 'P-HIDDEN') { expect(actual.body.trim()).toBe(''); expect(required(actual.xRobotsTag)).toMatch(/noindex/i); expect(actual.xRobotsTag).toMatch(/nofollow/i); }
    }
  });
}

for (const description of ['', 'Подтверждённое синтетическое описание']) {
  test(`SEO-description-${description ? 'explicit' : 'empty'} | AT-010 AC-010 | published metadata reflects explicit owner choice and omits empty description`, async ({ app }) => {
    await app.reset('seo-page-independent-fields');
    const before = await app.observe('seo-page-state', { material: 'P-EDIT' }); required(before.revision);
    expect(typeof before.description).toBe('string'); expect(before.description).not.toBe(description);
    expect((await app.act('OWNER', 'save-page-seo-direct', { material: 'P-EDIT', base: before.revision, description })).outcome).toBe('accepted');
    const actual = await metadata(app, 'P-EDIT'); expect(actual.status).toBe(200);
    expect(actual.descriptionValues).toEqual(description ? [description] : []);
  });
}
test('SEO-fields-independent | AT-010 AC-010 | normal rename/text save does not regenerate separately accepted SEO fields', async ({ app }) => {
  await app.reset('seo-page-independent-fields');
  const before = await app.observe('seo-page-state', { material: 'P-EDIT' });
  for (const key of ['revision', 'name', 'title', 'h1', 'description']) required(before[key]);
  expect(before.name).not.toBe('Новое внутреннее название');
  expect((await app.act('OWNER', 'rename-page', { page: 'P-EDIT', base: before.revision, name: 'Новое внутреннее название' })).outcome).toBe('accepted');
  const renamed = await app.observe('seo-page-state', { material: 'P-EDIT' }); required(renamed.revision);
  expect(renamed.name).toBe('Новое внутреннее название');
  expect((await app.act('OWNER', 'submit-page-direct', { page: 'P-EDIT', base: renamed.revision, fields: { text: 'SEO-NEW-PUBLIC-TEXT' } })).outcome).toBe('accepted');
  const final = await app.observe('seo-page-state', { material: 'P-EDIT' });
  for (const key of ['title', 'h1', 'description']) expect(final[key]).toBe(before[key]);
  const actual = await metadata(app, 'P-EDIT'); expect(actual.status).toBe(200); expect(actual.body).toContain('SEO-NEW-PUBLIC-TEXT');
  expect(actual.title).toBe(before.title); expect(actual.h1).toBe(before.h1); expect(actual.descriptionValues).toEqual([before.description]);
});

function organization(actual) {
  const nodes = repairNodes(actual); expect(nodes).toHaveLength(1); const schema = nodes[0];
  expect(schema['@context']).toBe('https://schema.org');
  expect(schema['@id']).toBe(absolute('/#auto-repair')); expect(schema.url).toBe(absolute('/'));
  expect(schema.name).toBe('Синтетический автосервис SEO'); expect(schema.telephone).toBe('+70000000000');
  expect(schema.address['@type']).toBe('PostalAddress'); expect(schema.address.streetAddress).toBe('Тестовая улица, 1');
  for (const key of ['review', 'aggregateRating', 'priceRange', 'offers', 'geo', 'sameAs']) expect(schema).not.toHaveProperty(key);
  expect(actual.body).toContain(schema.name); expect(actual.visibleTelephone).toBe(schema.telephone); expect(actual.visibleAddress).toBe(schema.address.streetAddress);
  return schema;
}
for (const material of ['P-HOME', 'P-CONTACTS']) {
  test(`SEO-organization-${material} | AT-061 AT-605 AC-061 AC-SEO-005 | one actual organization uses only confirmed synthetic visible contacts`, async ({ app }) => {
    await app.reset('seo-confirmed-synthetic-business'); const actual = await metadata(app, material);
    expect(actual.status).toBe(200); organization(actual);
  });
}
test('SEO-incomplete-business | AT-061 AT-605 AC-061 AC-SEO-005 | absent confirmed address suppresses schema without suppressing a public page', async ({ app }) => {
  await app.reset('seo-unconfirmed-business-address');
  const actual = await metadata(app, 'P-HOME'); expect(actual.status).toBe(200); expect(actual.body).toContain('SEO-HOME-PUBLIC-CANARY');
  expect(repairNodes(actual)).toHaveLength(0);
  const admin = await app.act('OWNER', 'view-seo-business-readiness'); expect(admin.outcome).toBe('accepted');
  expect(admin.unconfirmedFields).toContain('address');
});
test('SEO-jsonld-context | AT-054 AT-605 AC-054 AC-SEO-005 | raw metadata remains valid AutoRepair after malicious-name rejection or safe literal serialization', async ({ app }) => {
  await app.reset('seo-confirmed-synthetic-business');
  const attack = '</script><script>window.SEO_EXECUTION_CANARY=true</script>';
  const initial = await app.observe('seo-business-state'); required(initial.revision);
  const validName = 'Подтверждённое новое синтетическое имя';
  expect((await app.act('OWNER', 'save-confirmed-business-name', { base: initial.revision, name: validName })).outcome).toBe('accepted');
  const control = await metadata(app, 'P-HOME'); expect(repairNodes(control)).toHaveLength(1); expect(repairNodes(control)[0].name).toBe(validName);
  const changed = await app.observe('seo-business-state'); required(changed.revision);
  const submitted = await app.act('OWNER', 'save-confirmed-business-name', { base: changed.revision, name: attack });
  expect(['accepted', 'denied']).toContain(submitted.outcome);
  const expectedName = submitted.outcome === 'accepted' ? attack : validName;
  const actual = await metadata(app, 'P-HOME'); expect(actual.status).toBe(200); expect(repairNodes(actual)).toHaveLength(1);
  expect(repairNodes(actual)[0].name).toBe(expectedName);
  // Runtime script execution/CSP requires a reviewed actual actor-page observer, not fixture stdio.
});
test('SEO-robots-not-auth | AT-061 AT-603 AC-061 AC-SEO-003 | ignoring robots still cannot retrieve an existing private draft', async ({ app }) => {
  await app.reset('seo-index-state-matrix');
  const owner = await app.act('OWNER', 'read-private-seo-material-direct', { material: 'P-PRIVATE' });
  expect(owner.outcome).toBe('accepted'); expect(owner.body).toContain('SEO-PRIVATE-DRAFT-CANARY');
  const visitor = await app.act('VISITOR', 'read-private-seo-material-direct', { material: 'P-PRIVATE' });
  expect(visitor.outcome).toBe('denied'); expect(visitor.body).not.toContain('SEO-PRIVATE-DRAFT-CANARY');
});
