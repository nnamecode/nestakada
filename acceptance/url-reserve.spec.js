import { createHash } from 'node:crypto';
import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver(); try { await use(app); } finally { await app.close(); }
} });
test.describe.configure({ timeout: 90_000 }); // Tool budget for multiple real fault phases, not a website SLA.
test.use({ javaScriptEnabled: false, serviceWorkers: 'block' });
test.beforeEach(async ({ context }) => {
  await context.route('**/*', route => route.abort());
  await context.routeWebSocket('**/*', socket => socket.close());
});
const paths = { a: '/acceptance/url/a/', b: '/acceptance/url/b/', c: '/acceptance/url/c/' };
const origin = 'https://acceptance.invalid'; // Logical canonical origin only: never a network target.
const required = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
const directives = value => required(value).toLowerCase().split(',').map(item => item.trim());
async function setup(app, options = {}) {
  const admission = await app.inspectInfrastructureAdmission();
  expect(admission.arc10Verified).toBe(true); expect(admission.isolatedInfrastructure).toBe(true);
  required(admission.reviewedEvidenceId); expect(admission.capabilities).toContain('fallback-control-v1');
  await app.reset('url-route-night-ready', options);
  const fixture = await app.observe('url-route-fixture');
  required(fixture.pageId); required(fixture.setId); required(fixture.oldBodyCanary); required(fixture.mainCanary);
  expect(fixture.trustedPublicOrigin).toBe(origin); expect(fixture.nightPath).toBe(paths.a);
  expect(fixture.nightPageId).toBe(fixture.pageId); expect(fixture.createdByActualBuild).toBe(true);
  expect(fixture.validatedState).toBe('READY');
  const original = await response(app, paths.a);
  expect(original.status).toBe(200); expect(original.body).toContain(fixture.oldBodyCanary);
  required(fixture.oldEtag); expect(original.headers.etag).toBe(fixture.oldEtag);
  return fixture;
}
async function response(app, path, method = 'GET', headers = {}) {
  const actual = await app.observe('url-route-response', { path, method, headers });
  expect(Number.isInteger(actual.status)).toBe(true); expect(typeof actual.body).toBe('string');
  expect(actual.headers !== null && typeof actual.headers === 'object').toBe(true);
  expect(actual.requestTarget).toBe(path); expect(actual.method).toBe(method);
  if (headers['if-none-match']) expect(actual.requestHeaders['if-none-match']).toBe(headers['if-none-match']);
  if (method === 'HEAD') expect(actual.body).toBe('');
  return actual;
}
function redirect(actual, target) {
  expect(actual.status).toBe(301); const location = new URL(required(actual.headers.location), origin);
  expect(location.href).toBe(new URL(target, origin).href);
  expect(location.username).toBe(''); expect(location.password).toBe('');
  expect(directives(actual.headers['cache-control'])).toContain('no-cache');
}
async function move(app, fixture, from, to) {
  const before = await app.observe('page', { page: 'P-URL' });
  expect(before.id).toBe(fixture.pageId); expect(before.url).toBe(from);
  const prepared = await app.act('OWNER', 'prepare-page-url-change', { page: 'P-URL', base: before.revision, requestedPath: to });
  expect(prepared.outcome).toBe('accepted');
  expect(prepared.confirmation.oldPath).toBe(from); expect(prepared.confirmation.newPath).toBe(to);
  expect((await app.act('OWNER', 'confirm-page-url-change', { page: 'P-URL', base: before.revision, requestedPath: to, confirmation: prepared.confirmation })).outcome).toBe('accepted');
  const after = await app.observe('page', { page: 'P-URL' });
  expect(after.id).toBe(before.id); expect(after.url).toBe(to); expect(after.revision).not.toBe(before.revision);
  expect((await response(app, to)).status).toBe(200);
}
async function indexing(app, value) {
  const before = await app.observe('seo-page-state', { material: 'P-URL' });
  expect((await app.act('OWNER', 'set-page-indexing-direct', { material: 'P-URL', base: before.revision, indexable: value })).outcome).toBe('accepted');
  expect((await app.observe('seo-page-state', { material: 'P-URL' })).indexable).toBe(value);
}
async function control(app, action, args) { expect((await app.control(action, args)).outcome).toBe('accepted'); }
async function fail(app, component) {
  await control(app, 'stop-isolated-component', { component });
  for (let n = 0; n < 2; n++) {
    const before = await app.observe('fallback-control-state');
    await control(app, 'advance-infrastructure-time', { seconds: 300 });
    await expect.poll(async () => (await app.observe('fallback-control-state')).local.completedChecks, { timeout: 10_000 }).toBe(before.local.completedChecks + 1);
  }
  await expect.poll(async () => (await app.observe('fallback-control-state')).confirmedMode, { timeout: 10_000 }).toBe('reserve');
}
async function main(app, fixture) {
  const actual = await response(app, '/'); expect(actual.status).toBe(200); expect(actual.body).toContain(fixture.mainCanary);
}
async function business(app) {
  const value = await app.observe('url-route-business-state');
  for (const key of ['pages', 'redirects', 'homeItems', 'versions', 'requests', 'consents']) expect(Array.isArray(value[key])).toBe(true);
  expect(value.pages.length).toBeGreaterThan(0); return value;
}
async function unchangedAfterRestart(app, component, before) {
  await control(app, 'start-isolated-component', { component });
  expect(await business(app)).toEqual(before);
}
async function metadata(page, html) {
  return page.evaluate(source => {
    const doc = new DOMParser().parseFromString(source, 'text/html');
    return { canonicals: [...doc.querySelectorAll('link[rel~="canonical"]')].map(node => node.getAttribute('href')),
      robots: [...doc.querySelectorAll('meta[name="robots" i]')].map(node => node.getAttribute('content') || '') };
  }, html);
}

for (const component of ['application', 'database']) {
  test(`URL-RESERVE-single-${component} | AT-007 AT-211 AT-606 AC-007 AC-HTML-011 AC-SEO-006 | current redirect wins over old night body and uncopied destination503`, async ({ app }) => {
    const fixture = await setup(app); await move(app, fixture, paths.a, paths.b); await indexing(app, false);
    const before = await business(app); await fail(app, component);
    for (const method of ['GET', 'HEAD']) {
      redirect(await response(app, paths.a, method, { 'if-none-match': fixture.oldEtag }), paths.b);
      const target = await response(app, paths.b, method); expect(target.status).toBe(503);
      expect(target.headers.location).toBeUndefined(); expect(directives(target.headers['cache-control'])).toContain('no-store');
      expect(target.body).not.toContain(fixture.oldBodyCanary);
    }
    await main(app, fixture); await unchangedAfterRestart(app, component, before);
  });
  for (const state of ['live', 'hidden', 'deleted']) {
    test(`URL-RESERVE-chain-${component}-${state} | AT-007 AT-211 AC-007 AC-HTML-011 | both previous paths target final object state without redirect chains`, async ({ app }) => {
      const fixture = await setup(app); await move(app, fixture, paths.a, paths.b); await move(app, fixture, paths.b, paths.c);
      // Positive normal-path assertions prevent a static error responder from satisfying failure checks.
      for (const path of [paths.a, paths.b]) redirect(await response(app, path), paths.c);
      if (state === 'hidden') {
        const source = await app.observe('page', { page: 'P-URL' });
        expect((await app.act('OWNER', 'set-page-publication', { page: 'P-URL', base: source.revision, published: false })).outcome).toBe('accepted');
      } else if (state === 'deleted') {
        const prepared = await app.act('OWNER', 'prepare-delete-page', { page: 'P-URL' });
        expect(prepared.outcome).toBe('accepted');
        expect(prepared.confirmation.pageId).toBe(fixture.pageId); expect(prepared.confirmation.url).toBe(paths.c);
        expect([...prepared.confirmation.redirectPaths].sort()).toEqual([paths.a, paths.b]);
        expect((await app.act('OWNER', 'confirm-page-delete-direct', { page: 'P-URL', confirmation: prepared.confirmation, passwordRef: 'OWNER-CURRENT-SECRET' })).outcome).toBe('accepted');
      }
      const before = await business(app); await fail(app, component);
      for (const method of ['GET', 'HEAD']) {
        for (const path of [paths.a, paths.b]) {
          const actual = await response(app, path, method, { 'if-none-match': fixture.oldEtag });
          if (state === 'deleted') { expect(actual.status).toBe(404); expect(actual.headers.location).toBeUndefined(); }
          else redirect(actual, paths.c);
          expect(actual.body).not.toContain(fixture.oldBodyCanary);
        }
        const target = await response(app, paths.c, method);
        expect(target.status).toBe(state === 'deleted' ? 404 : state === 'hidden' ? 200 : 503);
        expect(target.headers.location).toBeUndefined(); expect(target.body).not.toContain(fixture.oldBodyCanary);
        if (state === 'hidden') expect(target.body.trim()).toBe('');
      }
      await main(app, fixture); await unchangedAfterRestart(app, component, before);
    });
  }
  for (const nightNoindex of [false, true]) {
    test(`URL-RESERVE-index-${component}-${nightNoindex ? 'relax' : 'tighten'} | AT-606 AC-SEO-006 | current noindex can strengthen night HTML but HTTP cannot erase old meta noindex`, async ({ app, page }) => {
      const fixture = await setup(app, { indexable: !nightNoindex });
      const original = await response(app, paths.a), oldMeta = await metadata(page, original.body);
      expect(oldMeta.canonicals).toEqual([new URL(paths.a, origin).href]);
      expect(oldMeta.robots.some(value => /(?:^|[,\s])noindex(?:$|[,\s])/iu.test(value))).toBe(nightNoindex);
      await indexing(app, nightNoindex); const before = await business(app); await fail(app, component);
      const actual = await response(app, paths.a); expect(actual.status).toBe(200); expect(actual.body).toContain(fixture.oldBodyCanary);
      const meta = await metadata(page, actual.body); expect(meta.canonicals).toEqual(oldMeta.canonicals);
      expect(meta.robots).toEqual(oldMeta.robots);
      if (!nightNoindex) expect(required(actual.headers['x-robots-tag'])).toMatch(/(?:^|[,\s])noindex(?:$|[,\s])/iu);
      // An equivalent HTTP canonical is allowed; a conflicting target is not.
      const httpLinks = [...(actual.headers.link || '').matchAll(/<([^>]+)>\s*([^<>]*)/gu)];
      for (const [, target, parameters] of httpLinks) {
        const relation = parameters.match(/\brel\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s;,]+))/iu);
        if ((relation?.[1] || relation?.[2] || relation?.[3] || '').toLowerCase().split(/\s/u).includes('canonical'))
          expect(new URL(target, origin).href).toBe(oldMeta.canonicals[0]);
      }
      const xml = await response(app, '/sitemap.xml'); expect([200, 503]).toContain(xml.status);
      if (xml.status === 503) {
        expect(directives(xml.headers['cache-control'])).toContain('no-store');
        expect(xml.body).not.toMatch(/<(?:urlset|sitemapindex)\b/iu);
      } else {
        // A separately proven current XML is allowed; the two-page fixture makes stale XML observable.
        const parsed = await page.evaluate(source => {
          const doc = new DOMParser().parseFromString(source, 'application/xml');
          return { errors: doc.querySelectorAll('parsererror').length, root: doc.documentElement.localName,
            namespace: doc.documentElement.namespaceURI,
            urls: [...doc.getElementsByTagNameNS('http://www.sitemaps.org/schemas/sitemap/0.9', 'url')].map(node =>
              [...node.getElementsByTagNameNS('http://www.sitemaps.org/schemas/sitemap/0.9', 'loc')].map(loc => loc.textContent)) };
        }, xml.body);
        expect(parsed.errors).toBe(0); expect(parsed.root).toBe('urlset');
        expect(parsed.namespace).toBe('http://www.sitemaps.org/schemas/sitemap/0.9');
        for (const urls of parsed.urls) expect(urls).toHaveLength(1);
        const urls = parsed.urls.flat().sort();
        expect(urls).toEqual([new URL('/', origin).href, ...(nightNoindex ? [new URL(paths.a, origin).href] : [])].sort());
        const proof = await app.observe('url-route-sitemap-proof');
        expect(proof.currentIndexGeneration).toBe(proof.confirmedXmlGeneration);
        required(proof.currentIndexGeneration); expect(proof.actualXmlSha256).toMatch(/^[a-f0-9]{64}$/);
        expect(proof.actualXmlSha256).toBe(createHash('sha256').update(xml.body, 'utf8').digest('hex'));
        expect(proof.confirmed).toBe(true);
      }
      await main(app, fixture); await unchangedAfterRestart(app, component, before);
    });
  }
}
