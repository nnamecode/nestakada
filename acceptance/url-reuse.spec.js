import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver(); try { await use(app); } finally { await app.close(); }
} });
test.describe.configure({ timeout: 90_000 }); // Test transport budget, not a production deadline.
const path = '/acceptance/reuse-route/';
const oldText = 'URL-REUSE-OLD-P-NIGHT-CANARY', newText = 'URL-REUSE-NEW-Q-CANARY';
const required = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
async function control(app, action, args) { expect((await app.control(action, args)).outcome).toBe('accepted'); }
async function response(app, target, method = 'GET', headers = {}) {
  const value = await app.observe('url-reuse-route-response', { path: target, method, headers });
  expect(Number.isInteger(value.status)).toBe(true); expect(value.headers !== null && typeof value.headers === 'object').toBe(true);
  expect(typeof value.body).toBe('string'); expect(value.requestTarget).toBe(target); expect(value.method).toBe(method);
  if (headers['if-none-match']) expect(value.requestHeaders['if-none-match']).toBe(headers['if-none-match']);
  if (method === 'HEAD') expect(value.body).toBe('');
  return value;
}
function noLocation(value) { expect(value.headers.location ?? null).toBeNull(); }
async function setup(app) {
  const admission = await app.inspectInfrastructureAdmission();
  expect(admission.arc10Verified).toBe(true); expect(admission.isolatedInfrastructure).toBe(true);
  required(admission.reviewedEvidenceId); expect(admission.capabilities).toContain('fallback-control-v1');
  await app.reset('url-reuse-existing-night');
  const fixture = await app.observe('url-reuse-fixture');
  expect(fixture.path).toBe(path); required(fixture.oldPageId);
  const publicOrigin = new URL(required(fixture.trustedPublicOrigin));
  expect(publicOrigin.protocol).toBe('https:'); expect(publicOrigin.pathname).toBe('/');
  expect(publicOrigin.search).toBe(''); expect(publicOrigin.hash).toBe('');
  expect(publicOrigin.username).toBe(''); expect(publicOrigin.password).toBe('');
  const proof = await app.observe('url-reuse-night-proof');
  expect(proof.createdByActualBuild).toBe(true); expect(proof.validationState).toBe('READY');
  expect(proof.path).toBe(path); expect(proof.objectId).toBe(fixture.oldPageId);
  required(proof.setId); expect(proof.fileSha256).toMatch(/^[a-f0-9]{64}$/);
  const oldPage = await response(app, path); expect(oldPage.status).toBe(200);
  expect(oldPage.body).toContain(oldText); expect(oldPage.body).not.toContain(newText); noLocation(oldPage);
  // Capture a validator of the actual old reserve body, not the separate Django namespace.
  await reserve(app, 'application');
  const oldReserve = await response(app, path); expect(oldReserve.status).toBe(200);
  expect(oldReserve.body).toContain(oldText); expect(oldReserve.body).not.toContain(newText);
  const oldEtag = required(oldReserve.headers.etag);
  await control(app, 'start-isolated-component', { component: 'application' });
  await checks(app, 'normal');
  const prepared = await app.act('OWNER', 'prepare-delete-page', { page: 'P-URL-REUSE' });
  expect(prepared.outcome).toBe('accepted'); expect(prepared.confirmation.pageId).toBe(fixture.oldPageId);
  expect(prepared.confirmation.url).toBe(path);
  expect((await app.act('OWNER', 'confirm-page-delete-direct', { page: 'P-URL-REUSE', confirmation: prepared.confirmation, passwordRef: 'OWNER-CURRENT-SECRET' })).outcome).toBe('accepted');
  expect((await app.observe('url-reuse-record', { pageId: fixture.oldPageId })).exists).toBe(false);
  const removed = await response(app, path); expect(removed.status).toBe(404); noLocation(removed); expect(removed.body).not.toContain(oldText);
  const created = await app.act('OWNER', 'create-page', { parent: 'P-URL-PARENT', name: 'Новая синтетическая Q', requestedPath: path });
  expect(created.outcome).toBe('accepted'); required(created.pageId); expect(created.pageId).not.toBe(fixture.oldPageId);
  const draft = await app.observe('url-reuse-record', { pageId: created.pageId });
  expect(draft.exists).toBe(true); expect(draft.path).toBe(path); required(draft.revision);
  expect((await app.act('OWNER', 'save-created-page-text-direct', { pageId: created.pageId, base: draft.revision, text: newText })).outcome).toBe('accepted');
  expect((await app.act('OWNER', 'publish-created-page', { pageId: created.pageId })).outcome).toBe('accepted');
  const current = await response(app, path); expect(current.status).toBe(200); noLocation(current);
  expect(current.body).toContain(newText); expect(current.body).not.toContain(oldText);
  expect(await app.observe('url-reuse-night-proof')).toEqual(proof);
  const route = await app.observe('url-reuse-routing-state', { path });
  expect(route.objectId).toBe(created.pageId); expect(route.routeKind).toBe('LIVE_NO_SET');
  expect(route.nightObjectId).toBe(fixture.oldPageId); expect(route.nightSetId).toBe(proof.setId);
  return { oldEtag, proof, trustedPublicOrigin: publicOrigin.origin };
}
async function checks(app, mode) {
  for (let n = 0; n < 2; n++) {
    const before = await app.observe('fallback-control-state');
    await control(app, 'advance-infrastructure-time', { seconds: 300 });
    await expect.poll(async () => (await app.observe('fallback-control-state')).local.completedChecks, { timeout: 10_000 }).toBe(before.local.completedChecks + 1);
  }
  await expect.poll(async () => (await app.observe('fallback-control-state')).confirmedMode, { timeout: 10_000 }).toBe(mode);
}
async function reserve(app, component) {
  await control(app, 'stop-isolated-component', { component });
  await checks(app, 'reserve');
}

for (const component of ['application', 'database']) for (const method of ['GET', 'HEAD']) {
  for (const variant of ['direct', 'encoded-unreserved', 'query', 'old-etag']) {
    test(`URL-REUSE-${component}-${method}-${variant} | AT-202 AC-HTML-002 | new object cannot inherit old path HTML or validator`, async ({ app }) => {
      const prepared = await setup(app); await reserve(app, component);
      const target = variant === 'encoded-unreserved' ? '/acceptance/%72euse-route/' : variant === 'query' ? `${path}?acceptance_probe=1` : path;
      const headers = variant === 'old-etag' ? { 'if-none-match': prepared.oldEtag } : {};
      const actual = await response(app, target, method, headers);
      expect(actual.status).not.toBe(200); expect(actual.status).not.toBe(304);
      expect(actual.body).not.toContain(oldText); expect(actual.body).not.toContain(newText);
      if (variant === 'direct' || variant === 'old-etag') {
        expect(actual.status).toBe(503); noLocation(actual);
      } else if (actual.status === 301) {
        // Exact normalization of encoded/unknown-query input is not a newly imposed route rule.
        // If canonicalized, it must only lead to this same Q route and its actual 503.
        const location = new URL(required(actual.headers.location), prepared.trustedPublicOrigin);
        expect(location.origin).toBe(prepared.trustedPublicOrigin); expect(location.pathname).toBe(path);
        expect(location.search).toBe(''); expect(location.hash).toBe('');
        expect(location.username).toBe(''); expect(location.password).toBe('');
        const canonical = await response(app, path, method, headers); expect(canonical.status).toBe(503); noLocation(canonical);
      } else {
        expect([404, 503]).toContain(actual.status); noLocation(actual);
      }
      expect(await app.observe('url-reuse-night-proof')).toEqual(prepared.proof);
    });
  }
}
