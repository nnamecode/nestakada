import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver(); try { await use(app); } finally { await app.close(); }
} });
test.describe.configure({ timeout: 90_000 }); // Multiple actual test fault phases, not a production SLA.
const paths = { a: '/acceptance/url-transition/a/', b: '/acceptance/url-transition/b/', c: '/acceptance/url-transition/c/' };
const origin = 'https://acceptance.invalid'; // Logical origin, never fetched.
const phases = ['before-deny-write', 'after-deny-before-db', 'after-db-before-finalize', 'incoming-redirect-finalize', 'before-admission'];
const required = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
async function control(app, action, args) {
  const result = await app.control(action, args); expect(result.outcome).toBe('accepted'); return result;
}
async function gate(app, path, method = 'GET') {
  const value = await app.observe('url-transition-reserve-response', { path, method });
  expect(value.requestTarget).toBe(path); expect(value.method).toBe(method);
  expect(typeof value.body).toBe('string'); expect(value.headers !== null && typeof value.headers === 'object').toBe(true);
  if (method === 'HEAD') expect(value.body).toBe('');
  return value;
}
function redirect(value, path) {
  expect(value.status).toBe(301); expect(new URL(required(value.headers.location), origin).href).toBe(new URL(path, origin).href);
}
async function db(app) {
  const value = await app.observe('url-transition-db-state');
  required(value.page.id); required(value.page.url); required(value.page.revision);
  for (const field of ['history', 'redirects', 'receipts', 'protectedBusiness']) expect(Array.isArray(value[field])).toBe(true);
  return value;
}
function ownRows(state, operationId) {
  return { history: state.history.filter(row => row.operationId === operationId), receipts: state.receipts.filter(row => row.operationId === operationId) };
}
function redirectRows(state, fixture) {
  return state.redirects.filter(row => row.targetPageId === fixture.pageId || Object.values(paths).includes(row.path))
    .map(row => ({ path: row.path, targetPageId: row.targetPageId, targetPath: row.targetPath }))
    .sort((a, b) => a.path.localeCompare(b.path));
}
async function operation(app, operationId) {
  const value = await app.observe('url-transition-operation', { operationId });
  expect(value.operationId).toBe(operationId);
  expect(['pending', 'complete', 'rejected', 'rolled-back']).toContain(value.state);
  expect(['not-started', 'rolled-back', 'committed', 'unknown']).toContain(value.commitState);
  return value;
}
async function prepare(app) {
  const before = await db(app);
  const result = await app.act('OWNER', 'prepare-page-url-change', { page: 'P-URL-TRANSITION', base: before.page.revision, requestedPath: paths.c });
  expect(result.outcome).toBe('accepted'); required(result.operationId);
  expect(result.confirmation.oldPath).toBe(paths.b); expect(result.confirmation.newPath).toBe(paths.c);
  return { operationId: result.operationId, page: 'P-URL-TRANSITION', base: before.page.revision, requestedPath: paths.c, confirmation: result.confirmation };
}
async function confirm(app, request) { return app.act('OWNER', 'confirm-page-url-change', request); }
async function setup(app) {
  const admission = await app.inspectInfrastructureAdmission();
  expect(admission.arc10Verified).toBe(true); expect(admission.isolatedInfrastructure).toBe(true); required(admission.reviewedEvidenceId);
  for (const capability of ['fallback-control-v1', 'url-transition-control-v1']) expect(admission.capabilities).toContain(capability);
  await app.reset('url-transition-existing-redirect-night');
  const fixture = await app.observe('url-transition-fixture');
  expect(fixture.nightPath).toBe(paths.a); expect(fixture.currentPath).toBe(paths.b);
  required(fixture.pageId); required(fixture.setId); required(fixture.oldBodyCanary); required(fixture.mainCanary);
  expect(fixture.actualBuildReady).toBe(true); expect(fixture.firstMoveCommitted).toBe(true);
  expect(fixture.trustedPublicOrigin).toBe(origin);
  const before = await db(app); expect(before.page.id).toBe(fixture.pageId); expect(before.page.url).toBe(paths.b);
  expect(before.redirects.filter(row => row.targetPageId === fixture.pageId).map(row => ({ path: row.path, targetPath: row.targetPath }))).toEqual([{ path: paths.a, targetPath: paths.b }]);
  redirect(await gate(app, paths.a), paths.b); expect((await gate(app, paths.b)).status).toBe(503);
  const oldFile = await app.observe('url-transition-night-file');
  expect(oldFile.setId).toBe(fixture.setId); expect(oldFile.pageId).toBe(fixture.pageId); expect(oldFile.path).toBe(paths.a);
  expect(oldFile.body).toContain(fixture.oldBodyCanary); expect(oldFile.sha256).toMatch(/^[a-f0-9]{64}$/);
  return fixture;
}
async function safePending(app, fixture, method) {
  for (const path of Object.values(paths)) {
    const actual = await gate(app, path, method); expect(actual.status).toBe(503);
    expect(actual.headers.location).toBeUndefined(); expect(actual.body).not.toContain(fixture.oldBodyCanary);
    expect(required(actual.headers['cache-control']).toLowerCase().split(',').map(value => value.trim())).toContain('no-store');
  }
  const main = await gate(app, '/'); expect(main.status).toBe(200); expect(main.body).toContain(fixture.mainCanary);
}
async function settledRoutes(app, fixture, state, method) {
  if (state.commitState === 'unknown' || state.state === 'pending') { await safePending(app, fixture, method); return; }
  const current = await db(app), committed = state.commitState === 'committed';
  expect(current.page.id).toBe(fixture.pageId);
  expect(current.page.url).toBe(committed ? paths.c : paths.b);
  if (committed) {
    expect(redirectRows(current, fixture)).toEqual([
      { path: paths.a, targetPageId: fixture.pageId, targetPath: paths.c },
      { path: paths.b, targetPageId: fixture.pageId, targetPath: paths.c },
    ]);
    expect(ownRows(current, state.operationId).history).toHaveLength(1);
    expect(ownRows(current, state.operationId).receipts).toHaveLength(1);
    redirect(await gate(app, paths.a, method), paths.c); redirect(await gate(app, paths.b, method), paths.c);
    expect((await gate(app, paths.c, method)).status).toBe(503);
  } else {
    expect(['not-started', 'rolled-back']).toContain(state.commitState);
    expect(state.rollbackVerified).toBe(true); // Actual DB/transaction evidence, never inferred from fault label or elapsed time.
    expect(redirectRows(current, fixture)).toEqual([{ path: paths.a, targetPageId: fixture.pageId, targetPath: paths.b }]);
    expect(ownRows(current, state.operationId).history).toHaveLength(0);
    redirect(await gate(app, paths.a, method), paths.b); expect((await gate(app, paths.b, method)).status).toBe(503);
    expect((await gate(app, paths.c, method)).status).toBe(404);
  }
}

for (const phase of phases) for (const method of ['GET', 'HEAD']) {
  test(`URL-TRANSITION-${phase}-${method} | AT-204 AT-212 AC-HTML-004 AC-HTML-012 | interrupted URL change remains fenced and receipt replay does not duplicate mutations`, async ({ app }) => {
    const fixture = await setup(app), request = await prepare(app), before = await db(app);
    const held = await control(app, 'hold-url-transition-reconciliation', { operationId: request.operationId }); required(held.barrierId);
    const fault = await control(app, 'set-url-transition-fault', { operationId: request.operationId, phase, fault: 'persistent-test-dependency-error' }); required(fault.faultId);
    const result = await confirm(app, request); expect(result.operationId).toBe(request.operationId);
    expect(result.outcome).toBe(phase === 'before-deny-write' ? 'denied' : 'pending');
    const hit = await app.observe('url-transition-fault-evidence', { operationId: request.operationId, faultId: fault.faultId });
    expect(hit.phase).toBe(phase); expect(hit.hitCount).toBeGreaterThanOrEqual(1); expect(hit.handlerSettled).toBe(true);
    let state = await operation(app, request.operationId), actual = await db(app);
    expect(actual.protectedBusiness).toEqual(before.protectedBusiness);
    if (phase === 'before-deny-write') {
      expect(actual).toEqual(before); expect(hit.durableDenyConfirmed).toBe(false);
      redirect(await gate(app, paths.a, method), paths.b); expect((await gate(app, paths.b, method)).status).toBe(503);
      expect((await gate(app, paths.c, method)).status).toBe(404);
    } else {
      expect(hit.durableDenyConfirmed).toBe(true); expect(state.state).toBe('pending');
      await safePending(app, fixture, method);
      // The known injection boundary is proved by independent DB reads, not a receipt's claim.
      if (phase === 'after-deny-before-db') {
        expect(actual.page).toEqual(before.page); expect(actual.redirects).toEqual(before.redirects);
        expect(ownRows(actual, request.operationId).history).toHaveLength(0);
      } else {
        expect(actual.page.url).toBe(paths.c); expect(actual.page.revision).not.toBe(before.page.revision);
        expect(ownRows(actual, request.operationId).history).toHaveLength(1);
        expect(ownRows(actual, request.operationId).receipts).toHaveLength(1);
        expect(redirectRows(actual, fixture)).toEqual([
          { path: paths.a, targetPageId: fixture.pageId, targetPath: paths.c },
          { path: paths.b, targetPageId: fixture.pageId, targetPath: paths.c },
        ]);
      }
      // Repeating exactly this operation is a lookup/resume, never a new independent URL change.
      const snapshot = await db(app), repeated = await confirm(app, request);
      expect(repeated.operationId).toBe(request.operationId); expect(repeated.outcome).toBe('pending');
      expect(await db(app)).toEqual(snapshot);
      await control(app, 'advance-infrastructure-time', { seconds: 1800 });
      expect((await operation(app, request.operationId)).state).toBe('pending');
      await safePending(app, fixture, method); expect(await db(app)).toEqual(snapshot);
    }
    await control(app, 'clear-url-transition-fault', { operationId: request.operationId, faultId: fault.faultId });
    await control(app, 'release-url-transition-reconciliation', { operationId: request.operationId, barrierId: held.barrierId });
    const checked = await app.act('OWNER', 'recheck-page-url-change', { operationId: request.operationId });
    expect(checked.operationId).toBe(request.operationId); expect(['accepted', 'denied', 'pending']).toContain(checked.outcome);
    state = await operation(app, request.operationId); await settledRoutes(app, fixture, state, method);
    actual = await db(app); const rows = ownRows(actual, request.operationId);
    expect(rows.history.length).toBeLessThanOrEqual(1); expect(rows.receipts.length).toBeLessThanOrEqual(1);
    expect(actual.protectedBusiness).toEqual(before.protectedBusiness);
  });
}

test('URL-TRANSITION-late-worker | AT-212 AC-HTML-012 | worker held before admission cannot emit old routing after confirmed change', async ({ app }) => {
  const fixture = await setup(app), request = await prepare(app);
  const held = await control(app, 'hold-url-route-worker', { operationId: request.operationId, path: paths.a, phase: 'before-current-generation-admission' }); required(held.workerId);
  const late = app.observe('url-transition-worker-response', { workerId: held.workerId, path: paths.a, method: 'GET' })
    .then(response => ({ response }), error => ({ error })); // Observe early timeout immediately; propagate it after releasing the barrier.
  // A genuinely concurrent HTTP read is parked before admission, not an already-admitted response.
  await expect.poll(async () => (await app.observe('url-transition-worker-state', { workerId: held.workerId })).phase).toBe('held-before-admission');
  expect((await confirm(app, request)).outcome).toBe('accepted');
  const state = await operation(app, request.operationId); expect(state.state).toBe('complete'); expect(state.commitState).toBe('committed');
  expect(Number.isSafeInteger(state.confirmedAdmissionSequence) && state.confirmedAdmissionSequence > 0).toBe(true);
  await control(app, 'release-url-route-worker', { operationId: request.operationId, workerId: held.workerId });
  const finished = await late; if (finished.error) throw finished.error;
  const actual = finished.response; expect([301, 503]).toContain(actual.status); expect(actual.body).not.toContain(fixture.oldBodyCanary);
  if (actual.status === 301) redirect(actual, paths.c); else expect(actual.headers.location).toBeUndefined();
  const trace = await app.observe('url-transition-worker-state', { workerId: held.workerId });
  expect(trace.admittedBeforeConfirmation).toBe(false); expect(trace.completed).toBe(true);
  if (trace.admitted === true) expect(trace.admissionSequence).toBeGreaterThan(state.confirmedAdmissionSequence);
  else expect(trace.fenced).toBe(true);
  redirect(await gate(app, paths.a), paths.c); redirect(await gate(app, paths.b), paths.c);
  expect((await gate(app, '/')).body).toContain(fixture.mainCanary);
});
