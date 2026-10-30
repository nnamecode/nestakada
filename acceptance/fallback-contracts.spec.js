import { createHash } from 'node:crypto';
import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({
  app: async ({}, use) => {
    const app = await openApplicationDriver();
    try { await use(app); } finally { await app.close(); }
  },
});

async function setup(app, profile = 'fallback-healthy-validated-baseline') {
  // Read independently reviewed infrastructure admission before any fault/reset control.
  if (typeof app.inspectInfrastructureAdmission !== 'function')
    throw new Error('INFRASTRUCTURE_NOT_ADMITTED: independent pre-fixture admission reader is required');
  const admission = await app.inspectInfrastructureAdmission();
  if (admission?.arc10Verified !== true || admission?.isolatedInfrastructure !== true ||
      typeof admission?.reviewedEvidenceId !== 'string' || !admission.reviewedEvidenceId.trim() ||
      !Array.isArray(admission?.capabilities) || !admission.capabilities.includes('fallback-control-v1')) {
    throw new Error('INFRASTRUCTURE_NOT_ADMITTED: real isolated fault adapter and ARC-10 evidence are required; no skip or model fallback');
  }
  await app.reset(profile);
}

async function control(app, action, args = {}) {
  if (typeof app.control !== 'function')
    throw new Error('LOCAL_CONTROL_NOT_CONFIGURED: isolated controlOrigin/session is required');
  const result = await app.control(action, args);
  expect(result.outcome, `actual isolated control action: ${action}`).toBe('accepted');
  return result;
}

function record(value, label) {
  expect(value !== null && typeof value === 'object' && !Array.isArray(value), `${label}: object required`).toBe(true);
  return value;
}
function nonEmptyId(value, label) {
  expect(typeof value, `${label}: string required`).toBe('string');
  expect(value.trim().length, `${label}: nonempty ID required`).toBeGreaterThan(0);
  return value;
}
function counter(value, label) {
  expect(Number.isSafeInteger(value) && value >= 0, `${label}: nonnegative safe integer required`).toBe(true);
  return value;
}
function generation(value, label) {
  const valid = (Number.isSafeInteger(value) && value >= 0) || (typeof value === 'string' && value.trim().length > 0);
  expect(valid, `${label}: explicit integer or nonempty opaque generation required`).toBe(true);
  return value;
}
async function state(app) {
  const actual = record(await app.observe('fallback-control-state'), 'fallback-control-state');
  expect(actual).toHaveProperty('confirmedMode');
  expect(actual.confirmedMode === null || (typeof actual.confirmedMode === 'string' && actual.confirmedMode.trim().length > 0),
    'confirmedMode must be explicit, including null for an unconfirmed mode').toBe(true);
  for (const source of ['local', 'external']) {
    const stream = record(actual[source], `${source} state`);
    for (const field of ['completedChecks', 'failedStreak', 'healthyStreak']) counter(stream[field], `${source}.${field}`);
    expect(stream).toHaveProperty('lastCheckId');
    if (stream.completedChecks > 0) nonEmptyId(stream.lastCheckId, `${source}.lastCheckId`);
    else expect(stream.lastCheckId === null || (typeof stream.lastCheckId === 'string' && stream.lastCheckId.trim().length > 0),
      `${source}.lastCheckId must be explicit before first check`).toBe(true);
  }
  return actual;
}
async function readinessCounters(app) {
  const actual = record(await app.observe('readiness-counters'), 'readiness-counters');
  for (const field of ['localHttp', 'externalHttp', 'readinessSelects']) counter(actual[field], field);
  record(actual.lastSequences, 'lastSequences');
  for (const source of ['local', 'external']) counter(actual.lastSequences[source], `lastSequences.${source}`);
  return actual;
}
async function telegramEvents(app) {
  const events = await app.observe('telegram-sink-events');
  expect(Array.isArray(events), 'telegram-sink-events: array required').toBe(true);
  for (const event of events) {
    record(event, 'telegram event');
    nonEmptyId(event.source, 'telegram source');
    nonEmptyId(event.kind, 'telegram kind');
  }
  return events;
}
async function modeMessages(app, kind) {
  return (await telegramEvents(app)).filter(event => event.source === 'local-controller' && event.kind === kind);
}
async function tick(app) {
  const before = await state(app);
  await control(app, 'advance-infrastructure-time', { seconds: 300 });
  await expect.poll(async () => {
    const current = await state(app);
    return [current.local.completedChecks, current.external.completedChecks];
  }, { timeout: 10_000 }).toEqual([before.local.completedChecks + 1, before.external.completedChecks + 1]);
}
async function expectReserve(app) {
  await expect.poll(async () => (await state(app)).confirmedMode, { timeout: 10_000 }).toBe('reserve');
  const response = await app.observe('reserve-public-response', { route: 'P-LIVE' });
  expect(response.status).toBe(200);
  expect(response.body).toContain('NIGHT-PUBLIC-CANARY');
}
async function enterReserve(app, component = 'application') {
  await control(app, 'stop-isolated-component', { component });
  await tick(app);
  await tick(app);
  await expectReserve(app);
}

for (const component of ['application', 'database']) {
  test(`FALLBACK-first-${component} | AT-045 AT-303 AC-045 AC-OPS-003 | one failed local check does not confirm reserve`, async ({ app }) => {
    await setup(app);
    await control(app, 'stop-isolated-component', { component });
    await tick(app);
    const actual = await state(app);
    expect(actual.local.failedStreak).toBe(1);
    expect(actual.confirmedMode).toBe('normal');
    expect(await modeMessages(app, 'mode-entered')).toHaveLength(0);
  });

  test(`FALLBACK-second-${component} | AT-046 AT-305 AC-046 AC-OPS-005 | two failures confirm actual HTML handling`, async ({ app }) => {
    await setup(app);
    await enterReserve(app, component);
    const actual = await state(app);
    expect(actual.local.failedStreak).toBe(2);
    generation(actual.frontConfirmedGeneration, 'frontConfirmedGeneration');
    generation(actual.requestedModeGeneration, 'requestedModeGeneration');
    expect(actual.frontConfirmedGeneration).toBe(actual.requestedModeGeneration);
    await expect.poll(async () => (await modeMessages(app, 'mode-entered')).length).toBe(1);
  });
}

test('FALLBACK-recovery | AT-049 AT-305 AC-049 AC-OPS-005 | first success keeps reserve, second confirms normal handler', async ({ app }) => {
  await setup(app);
  await enterReserve(app);
  await control(app, 'start-isolated-component', { component: 'application' });
  await tick(app);
  expect((await state(app)).local.healthyStreak).toBe(1);
  expect((await state(app)).confirmedMode).toBe('reserve');
  expect(await modeMessages(app, 'mode-left')).toHaveLength(0);
  await tick(app);
  await expect.poll(async () => (await state(app)).confirmedMode).toBe('normal');
  expect((await state(app)).local.healthyStreak).toBe(2);
  const response = await app.observe('normal-public-response', { route: 'P-LIVE' });
  expect(response.status).toBe(200);
  expect(response.body).toContain('CURRENT-APP-PUBLIC-CANARY');
  await expect.poll(async () => (await modeMessages(app, 'mode-left')).length).toBe(1);
});

test('FALLBACK-independent-streams | AT-406 AC-PRO-006 | failures from distinct streams never combine', async ({ app }) => {
  await setup(app);
  await control(app, 'block-readiness-channel', { source: 'local' });
  await tick(app);
  expect((await state(app)).local.failedStreak).toBe(1);
  await control(app, 'unblock-readiness-channel', { source: 'local' });
  await control(app, 'block-readiness-channel', { source: 'external' });
  await tick(app);
  const actual = await state(app);
  expect(actual.local.failedStreak).toBe(0);
  expect(actual.external.failedStreak).toBe(1);
  expect(actual.confirmedMode).toBe('normal');
  expect(await modeMessages(app, 'mode-entered')).toHaveLength(0);
});

test('FALLBACK-duplicate-result | AT-303 AT-406 AC-OPS-003 AC-PRO-006 | replayed result ID is not another check', async ({ app }) => {
  await setup(app);
  await control(app, 'block-readiness-channel', { source: 'local' });
  await tick(app);
  const before = await state(app);
  nonEmptyId(before.local.lastCheckId, 'captured local lastCheckId');
  const counters = await readinessCounters(app);
  await control(app, 'replay-captured-readiness-result', { source: 'local', checkId: before.local.lastCheckId });
  const after = await state(app);
  expect(after.local.failedStreak).toBe(1);
  expect(after.local.lastCheckId).toBe(before.local.lastCheckId);
  expect(after.confirmedMode).toBe('normal');
  const afterCounters = await readinessCounters(app);
  for (const key of ['localHttp', 'externalHttp', 'readinessSelects', 'lastSequences'])
    expect(afterCounters[key], key).toEqual(counters[key]);
  expect(after.local.completedChecks).toBe(before.local.completedChecks);
});

test('FALLBACK-failure-chain-reset | AT-303 AC-OPS-003 | intervening success resets failure streak', async ({ app }) => {
  await setup(app);
  await control(app, 'block-readiness-channel', { source: 'local' });
  await tick(app);
  await control(app, 'unblock-readiness-channel', { source: 'local' });
  await tick(app);
  expect((await state(app)).local.failedStreak).toBe(0);
  await control(app, 'block-readiness-channel', { source: 'local' });
  await tick(app);
  expect((await state(app)).local.failedStreak).toBe(1);
  expect((await state(app)).confirmedMode).toBe('normal');
});

test('FALLBACK-recovery-chain-reset | AT-049 AT-305 AC-049 AC-OPS-005 | failure resets partial recovery without second incident', async ({ app }) => {
  await setup(app);
  await enterReserve(app);
  await control(app, 'start-isolated-component', { component: 'application' });
  await tick(app);
  expect((await state(app)).local.healthyStreak).toBe(1);
  const incident = nonEmptyId((await state(app)).local.incidentId, 'open local incidentId');
  await control(app, 'stop-isolated-component', { component: 'application' });
  await tick(app);
  expect((await state(app)).local.healthyStreak).toBe(0);
  expect(nonEmptyId((await state(app)).local.incidentId, 'continuing local incidentId')).toBe(incident);
  expect((await state(app)).confirmedMode).toBe('reserve');
  expect(await modeMessages(app, 'mode-left')).toHaveLength(0);
});

test('FALLBACK-five-minute-budget | AT-407 AC-PRO-007 | stable day has 288 real checks per stream and 576 readiness SELECTs', async ({ app }) => {
  test.setTimeout(120_000);
  await setup(app);
  const before = await readinessCounters(app);
  await control(app, 'advance-infrastructure-time', { seconds: 86400 });
  await expect.poll(async () => {
    const counts = await readinessCounters(app);
    return [counts.localHttp - before.localHttp, counts.externalHttp - before.externalHttp, counts.readinessSelects - before.readinessSelects];
  }, { timeout: 90_000 }).toEqual([288, 288, 576]);
  const after = await readinessCounters(app);
  expect(after.externalHttp - before.externalHttp).toBe(288);
  expect(after.readinessSelects - before.readinessSelects).toBe(576);
  const ledger = await app.observe('readiness-check-ledger');
  expect(Array.isArray(ledger), 'readiness-check-ledger: array required').toBe(true);
  for (const entry of ledger) {
    record(entry, 'readiness ledger entry');
    expect(['local', 'external']).toContain(entry.source);
    nonEmptyId(entry.checkId, 'readiness ledger checkId');
    counter(entry.sequence, 'readiness ledger sequence');
    expect(Number.isFinite(entry.scheduledMonotonicSeconds) && entry.scheduledMonotonicSeconds >= 0,
      'readiness ledger scheduledMonotonicSeconds: finite nonnegative number required').toBe(true);
  }
  for (const source of ['local', 'external']) {
    const checks = ledger.filter(check => check.source === source && check.sequence > before.lastSequences[source]);
    expect(checks).toHaveLength(288);
    expect(new Set(checks.map(check => check.checkId)).size).toBe(288);
    for (let i = 1; i < checks.length; i++) {
      expect(checks[i].sequence).toBeGreaterThan(checks[i - 1].sequence);
      expect(checks[i].scheduledMonotonicSeconds - checks[i - 1].scheduledMonotonicSeconds).toBe(300);
    }
  }
});

test('FALLBACK-readiness-bypass | AT-301 AT-406 AC-OPS-001 AC-PRO-006 | successful night page never masks failed real SQL readiness', async ({ app }) => {
  await setup(app);
  await enterReserve(app, 'database');
  const response = await app.observe('external-readiness-http');
  expect(response.status).toBe(503);
  expect(response.cacheControl).toContain('no-store');
  expect(response.body).not.toContain('NIGHT-PUBLIC-CANARY');
  expect(response.usedReserve).toBe(false);
});

for (const [route, status] of [['P-DELETED', 404], ['P-HIDDEN', 200], ['P-NEW-NO-SET', 503], ['P-UNKNOWN', 404], ['P-OLD-REDIRECT', 301]]) {
  test(`FALLBACK-route-${route} | AT-002 AT-207 AT-211 AC-002 AC-HTML-007 AC-HTML-011 | current route policy precedes night files`, async ({ app }) => {
    await setup(app, 'fallback-current-policy-versus-old-files');
    const fixture = await app.observe('fallback-fixture-identifiers');
    record(fixture, 'fallback fixture identifiers');
    record(fixture.paths, 'fallback fixture paths');
    nonEmptyId(fixture.paths[route], `path ${route}`);
    const response = await app.observe('reserve-public-response', { route, followRedirects: false });
    expect(response.status).toBe(status);
    expect(response.body).not.toContain('REVOKED-OLD-BODY-CANARY');
    expect(nonEmptyId(response.requestedPath, 'actual requestedPath')).toBe(fixture.paths[route]);
    if (route === 'P-HIDDEN') {
      expect(response.body.trim()).toBe('');
      expect(response.robotsDirectives).toContain('noindex');
    }
    if ([404, 503].includes(status)) expect(response.cacheControl).toContain('no-store');
    if (route === 'P-OLD-REDIRECT') {
      nonEmptyId(fixture.currentRedirectTarget, 'currentRedirectTarget');
      nonEmptyId(fixture.intermediateRedirectTarget, 'intermediateRedirectTarget');
      expect(nonEmptyId(response.location, 'actual Location')).toBe(fixture.currentRedirectTarget);
      expect(response.location).not.toBe(fixture.intermediateRedirectTarget);
    } else expect(response.location).toBeNull();
  });
}

test('FALLBACK-night-home | AT-201 AT-048 AC-HTML-001 AC-048 | admitted night home is unchanged and has no failure banner', async ({ app }) => {
  await setup(app, 'fallback-home-deleted-link-current-denial');
  const file = await app.observe('admitted-night-file', { route: 'P-HOME' });
  expect(file.sha256, 'night file SHA-256').toMatch(/^[a-f0-9]{64}$/i);
  const response = await app.observe('reserve-public-response', { route: 'P-HOME' });
  expect(response.status).toBe(200);
  expect(createHash('sha256').update(response.bodyBytesBase64, 'base64').digest('hex')).toBe(file.sha256);
  expect(response.body).toContain('OLD-PUBLIC-LINK-CANARY');
  expect((await app.observe('reserve-visible-state', { route: 'P-HOME' })).technicalFailureBannerVisible).toBe(false);
  expect((await app.observe('reserve-public-response', { route: 'P-DELETED' })).status).toBe(404);
});

test('FALLBACK-head-unavailable | AT-209 AT-409 AC-HTML-009 AC-PRO-009 | restart cannot trust its old valid local permit', async ({ app }) => {
  await setup(app, 'fallback-valid-old-local-new-external-denial');
  await control(app, 'block-independent-head');
  await control(app, 'restart-gate-with-closed-start-barrier');
  const response = await app.observe('reserve-public-response', { route: 'P-REVOKED' });
  expect(response.status).toBe(503);
  expect(response.body).not.toContain('REVOKED-OLD-BODY-CANARY');
  expect((await state(app)).admissionOpen).toBe(false);
});

for (const headAvailable of [true, false]) {
  test(`FALLBACK-signed-rollback-${headAvailable} | AT-209 AT-409 AC-HTML-009 AC-PRO-009 | valid old APP/EDGE state does not roll back TRUST`, async ({ app }) => {
    await setup(app, 'fallback-valid-old-local-new-external-denial');
    const trusted = await app.observe('independent-head-state');
    generation(trusted.generation, 'trusted head generation');
    await control(app, 'rollback-isolated-app-edge-to-valid-old-snapshot');
    expect((await app.observe('restored-local-integrity')).signaturesValid).toBe(true);
    const afterHead = await app.observe('independent-head-state');
    generation(afterHead.generation, 'head generation after local rollback');
    expect(afterHead.generation).toBe(trusted.generation);
    if (!headAvailable) await control(app, 'block-independent-head');
    await control(app, 'restart-gate-with-closed-start-barrier');
    const response = await app.observe('reserve-public-response', { route: 'P-REVOKED' });
    expect(headAvailable ? [404, 503] : [503]).toContain(response.status);
    expect(response.body).not.toContain('REVOKED-OLD-BODY-CANARY');
  });
}

test('FALLBACK-ack-before-message | AT-042 AT-305 AT-306 AC-042 AC-OPS-005 AC-OPS-006 | request to switch is not proof of a loaded handler', async ({ app }) => {
  await setup(app);
  await control(app, 'hold-front-switch-confirmation');
  await control(app, 'stop-isolated-component', { component: 'application' });
  await tick(app);
  await tick(app);
  await expect.poll(async () => (await state(app)).switchPending).toBe(true);
  expect(await modeMessages(app, 'mode-entered')).toHaveLength(0);
  await control(app, 'release-front-switch-confirmation');
  await expectReserve(app);
  await expect.poll(async () => (await modeMessages(app, 'mode-entered')).length).toBe(1);
  const events = await app.observe('local-controller-event-ledger');
  expect(Array.isArray(events), 'local-controller-event-ledger: array required').toBe(true);
  for (const event of events) {
    record(event, 'controller ledger event');
    nonEmptyId(event.kind, 'controller ledger kind');
    counter(event.sequence, 'controller ledger sequence');
    if (event.kind === 'telegram-delivered') nonEmptyId(event.messageKind, 'controller delivered messageKind');
  }
  const confirmed = events.find(event => event.kind === 'front-switch-confirmed');
  const delivered = events.find(event => event.kind === 'telegram-delivered' && event.messageKind === 'mode-entered');
  expect(confirmed).toBeTruthy();
  expect(delivered).toBeTruthy();
  expect(delivered.sequence).toBeGreaterThan(confirmed.sequence);
});

test('FALLBACK-telegram-down | AT-042 AT-306 AC-042 AC-OPS-006 | undelivered Telegram does not prevent or prove the actual switch', async ({ app }) => {
  await setup(app);
  await control(app, 'block-telegram-transport');
  await enterReserve(app);
  expect(await modeMessages(app, 'mode-entered')).toHaveLength(0);
  await expect.poll(async () => counter((await app.observe('controller-outbox-state')).pendingModeMessages,
    'outbox pendingModeMessages')).toBeGreaterThanOrEqual(1);
  expect((await state(app)).confirmedMode).toBe('reserve');
  expect((await app.observe('reserve-public-response', { route: 'P-LIVE' })).status).toBe(200);
});

test('FALLBACK-switch-failed | AT-042 AT-305 AT-306 AC-042 AC-OPS-005 AC-OPS-006 | unconfirmed reload cannot claim HTML mode', async ({ app }) => {
  await setup(app);
  await control(app, 'fail-front-switch-application');
  await control(app, 'stop-isolated-component', { component: 'application' });
  await tick(app);
  await tick(app);
  await expect.poll(async () => (await state(app)).controlStatus).toBe('SWITCH_FAILED');
  expect((await state(app)).confirmedMode).not.toBe('reserve');
  expect(await modeMessages(app, 'mode-entered')).toHaveLength(0);
  await expect.poll(async () => (await modeMessages(app, 'switch-failed')).length).toBeGreaterThanOrEqual(1);
});

test('FALLBACK-admission-before-revoke | AT-203 AT-410 AC-HTML-003 AC-PRO-010 | previously admitted slow body may finish, new admission is closed', async ({ app }) => {
  await setup(app, 'fallback-owner-revocation-with-slow-client');
  const slow = await control(app, 'hold-response-after-gate-admission', { route: 'P-REVOKED' });
  nonEmptyId(slow.responseId, 'admitted responseId');
  const prepared = await app.act('OWNER', 'prepare-delete-page', { page: 'P-REVOKED' });
  expect(prepared.outcome).toBe('accepted');
  expect((await app.act('OWNER', 'confirm-delete-page', { page: 'P-REVOKED', confirmation: prepared.confirmation, passwordRef: 'OWNER-CURRENT-SECRET' })).outcome).toBe('accepted');
  expect((await app.observe('reserve-public-response', { route: 'P-REVOKED' })).status).toBe(404);
  expect((await app.observe('retained-inflight-set', { responseId: slow.responseId })).retained).toBe(true);
  await control(app, 'release-admitted-response', { responseId: slow.responseId });
  const finished = await app.observe('finished-admitted-response', { responseId: slow.responseId });
  expect(finished.body).toContain('ADMITTED-BEFORE-REVOKE-CANARY');
  counter(finished.admittedSequence, 'finished admittedSequence');
  counter(finished.confirmedRevokeSequence, 'finished confirmedRevokeSequence');
  expect(finished.admittedSequence).toBeLessThan(finished.confirmedRevokeSequence);
});

test('FALLBACK-local-admission-no-cloud-per-request | AT-207 AT-409 AC-HTML-007 AC-PRO-009 | steady valid admission does not query main SQL or cloud on every visit', async ({ app }) => {
  await setup(app, 'fallback-current-policy-versus-old-files');
  const before = await app.observe('fallback-io-counters');
  record(before, 'fallback I/O counters before');
  for (const key of ['publicRequestSql', 'independentHeadHttp', 'policyRegistryWrites']) counter(before[key], `before.${key}`);
  for (let i = 0; i < 10; i++) expect((await app.observe('reserve-public-response', { route: 'P-LIVE' })).status).toBe(200);
  const after = await app.observe('fallback-io-counters');
  record(after, 'fallback I/O counters after');
  for (const key of ['publicRequestSql', 'independentHeadHttp', 'policyRegistryWrites']) counter(after[key], `after.${key}`);
  expect(after.publicRequestSql - before.publicRequestSql).toBe(0);
  expect(after.independentHeadHttp - before.independentHeadHttp).toBe(0);
  expect(after.policyRegistryWrites - before.policyRegistryWrites).toBe(0);
});

test('FALLBACK-full-host-unavailable | AT-304 AT-408 AC-OPS-004 AC-PRO-008 | external alarm cannot claim same-host HTML is working', async ({ app }) => {
  await setup(app);
  await control(app, 'stop-isolated-host-zone', { zone: 'APP-EDGE' });
  await control(app, 'advance-infrastructure-time', { seconds: 600 });
  await expect.poll(async () => counter((await app.observe('external-observer-state')).failedStreak,
    'external failedStreak'), { timeout: 10_000 }).toBe(2);
  expect((await app.observe('external-public-transport')).transportFailed).toBe(true);
  expect(await modeMessages(app, 'mode-entered')).toHaveLength(0);
  const external = (await telegramEvents(app)).filter(event => event.source === 'external-observer' && event.kind === 'readiness-unavailable');
  expect(external).toHaveLength(1);
});
