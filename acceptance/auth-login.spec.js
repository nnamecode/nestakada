import { isIP } from 'node:net';
import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await use(app); } finally { await app.close(); }
} });
const targets = {
  OWNER: { userKey: 'ownerUserId', secret: 'OWNER-CURRENT-SECRET', canary: 'AUTH-OWNER-PRIVATE-CANARY' },
  'S-EDIT': { userKey: 'employeeUserId', secret: 'EMPLOYEE-CURRENT-SECRET', canary: 'AUTH-EMPLOYEE-PRIVATE-CANARY' },
};
const good = (app, actor, target = 'S-EDIT') => app.act(actor, 'submit-login-direct', { account: target, passwordRef: targets[target].secret });
const bad = (app, actor, target = 'S-EDIT') => app.act(actor, 'submit-login-direct', { account: target, passwordRef: 'WRONG-SYNTHETIC-SECRET' });
async function failed(app, actor, count, target = 'S-EDIT') {
  for (let i = 0; i < count; i++) expect((await bad(app, actor, target)).outcome).toBe('denied');
}
async function identified(app, actor, identifiers, target = 'S-EDIT') {
  const response = await app.act(actor, 'read-authenticated-identity-direct');
  expect(response.outcome).toBe('accepted');
  expect(response.authenticatedUserId).toBe(identifiers[targets[target].userKey]);
  expect(response.body).toContain(targets[target].canary);
}
async function anonymous(app, actor) {
  const response = await app.act(actor, 'read-authenticated-identity-direct');
  expect(response.outcome).toBe('denied');
  for (const { canary } of Object.values(targets)) expect(response.body).not.toContain(canary);
}
async function reset(app, options = {}) {
  await app.reset('auth-login-isolated-sources', options);
  const ids = await app.observe('auth-fixture-identifiers');
  for (const key of ['ownerUserId', 'employeeUserId', 'sourceAIp', 'sourceBIp']) {
    expect(typeof ids[key]).toBe('string'); expect(ids[key].length).toBeGreaterThan(0);
  }
  expect(ids.ownerUserId).not.toBe(ids.employeeUserId);
  expect(isIP(ids.sourceAIp)).toBeGreaterThan(0); expect(isIP(ids.sourceBIp)).toBeGreaterThan(0);
  expect(ids.sourceAIp).not.toBe(ids.sourceBIp);
  return ids;
}
async function source(app, actor, ids) {
  const actual = await app.observe('auth-source-state', { actor });
  const expectedIp = actor === 'LOGIN-B' ? ids.sourceBIp : ids.sourceAIp;
  expect(actual.sourceIp).toBe(expectedIp);
  expect(actual.observedFrom).toBe('actual-ingress-and-limiter');
  expect(typeof actual.lastRequestId).toBe('string'); expect(actual.lastRequestId.length).toBeGreaterThan(0);
  expect(Number.isSafeInteger(actual.failedCount)).toBe(true); expect(actual.failedCount).toBeGreaterThanOrEqual(0);
  expect(Number.isFinite(Date.parse(actual.nowUtc))).toBe(true);
  if (actual.blockedUntilUtc !== null) expect(Number.isFinite(Date.parse(actual.blockedUntilUtc))).toBe(true);
  return actual;
}
function limited(state) {
  expect(state.blockedUntilUtc).not.toBeNull();
  expect(Date.parse(state.blockedUntilUtc)).toBeGreaterThan(Date.parse(state.nowUtc));
}
function notLimited(state) {
  expect(state.blockedUntilUtc === null || Date.parse(state.blockedUntilUtc) <= Date.parse(state.nowUtc)).toBe(true);
}

for (const target of ['OWNER', 'S-EDIT']) {
  test(`AUTH-LOGIN-014-${target} | AT-014 AC-014 | valid password establishes the actual selected identity`, async ({ app }) => {
    const ids = await reset(app);
    await anonymous(app, 'LOGIN-A');
    expect((await good(app, 'LOGIN-A', target)).outcome).toBe('accepted');
    await identified(app, 'LOGIN-A', ids, target);
    notLimited(await source(app, 'LOGIN-A', ids));
  });
}

test('AUTH-LOGIN-014-wrong | AT-014 AC-014 | wrong password gives no private access and the same account can then log in', async ({ app }) => {
  const ids = await reset(app);
  await failed(app, 'LOGIN-A', 1); await anonymous(app, 'LOGIN-A');
  expect((await source(app, 'LOGIN-A', ids)).failedCount).toBe(1);
  expect((await good(app, 'LOGIN-A')).outcome).toBe('accepted'); await identified(app, 'LOGIN-A', ids);
});

test('AUTH-LIMIT-060-four | AT-060 AC-060 | four failures allow a correct password and success clears this source', async ({ app }) => {
  const ids = await reset(app);
  await failed(app, 'LOGIN-A', 4);
  const four = await source(app, 'LOGIN-A', ids); expect(four.failedCount).toBe(4); notLimited(four);
  expect((await good(app, 'LOGIN-A')).outcome).toBe('accepted'); await identified(app, 'LOGIN-A', ids);
  expect((await source(app, 'LOGIN-A', ids)).failedCount).toBe(0);
  expect((await app.act('LOGIN-A', 'logout-auth-session')).outcome).toBe('accepted');
  await anonymous(app, 'LOGIN-A');
  await failed(app, 'LOGIN-A', 4); notLimited(await source(app, 'LOGIN-A', ids));
  expect((await good(app, 'LOGIN-A')).outcome).toBe('accepted'); await identified(app, 'LOGIN-A', ids);
});

test('AUTH-LIMIT-060-five | AT-060 AC-060 | fifth failure limits the source for fifteen minutes, not the account on another source', async ({ app }) => {
  const ids = await reset(app);
  await failed(app, 'LOGIN-A', 5);
  const blocked = await source(app, 'LOGIN-A', ids); limited(blocked);
  expect(Date.parse(blocked.blockedUntilUtc) - Date.parse(blocked.nowUtc)).toBe(900_000);
  expect((await good(app, 'LOGIN-A')).outcome).toBe('denied'); await anonymous(app, 'LOGIN-A');
  expect((await good(app, 'LOGIN-B')).outcome).toBe('accepted'); await identified(app, 'LOGIN-B', ids);
  const other = await source(app, 'LOGIN-B', ids); notLimited(other);
  limited(await source(app, 'LOGIN-A', ids));
});

for (const [ageSeconds, permitted] of [[899, false], [901, true]]) {
  test(`AUTH-LIMIT-060-expiry-${ageSeconds} | AT-060 AC-060 | limit expiry is checked on both sides of fifteen minutes`, async ({ app }) => {
    const ids = await reset(app, { seed: 'five-failures-blocked', ageSeconds });
    await anonymous(app, 'LOGIN-A');
    const attempt = await good(app, 'LOGIN-A');
    expect(attempt.outcome).toBe(permitted ? 'accepted' : 'denied');
    if (permitted) await identified(app, 'LOGIN-A', ids);
    else {
      await anonymous(app, 'LOGIN-A'); limited(await source(app, 'LOGIN-A', ids));
      expect((await good(app, 'LOGIN-B')).outcome).toBe('accepted'); await identified(app, 'LOGIN-B', ids);
    }
  });
}

for (const [ageSeconds, shouldLimit] of [[599, true], [601, false]]) {
  test(`AUTH-LIMIT-060-window-${ageSeconds} | AT-060 AC-060 | old failures count only inside the ten-minute window`, async ({ app }) => {
    const ids = await reset(app, { seed: 'four-failures-aged', ageSeconds });
    await failed(app, 'LOGIN-A', 1);
    const state = await source(app, 'LOGIN-A', ids);
    if (shouldLimit) limited(state); else notLimited(state);
    expect((await good(app, 'LOGIN-A')).outcome).toBe(shouldLimit ? 'denied' : 'accepted');
    if (shouldLimit) {
      await anonymous(app, 'LOGIN-A');
      expect((await good(app, 'LOGIN-B')).outcome).toBe('accepted'); await identified(app, 'LOGIN-B', ids);
    } else await identified(app, 'LOGIN-A', ids);
  });
}

test('AUTH-LIMIT-060-shared-source | AT-060 AC-060 | separate browser contexts on one actual IP share its limit', async ({ app }) => {
  const ids = await reset(app);
  await failed(app, 'LOGIN-A', 3); await failed(app, 'LOGIN-A2', 2);
  const first = await source(app, 'LOGIN-A', ids), second = await source(app, 'LOGIN-A2', ids);
  expect(first.sourceIp).toBe(second.sourceIp); limited(first); limited(second);
  expect((await good(app, 'LOGIN-A2')).outcome).toBe('denied'); await anonymous(app, 'LOGIN-A2');
  expect((await good(app, 'LOGIN-B')).outcome).toBe('accepted'); await identified(app, 'LOGIN-B', ids);
});

test('AUTH-LIMIT-060-mixed-accounts | AT-060 AC-060 | failures for different accounts share the same actual source limit', async ({ app }) => {
  const ids = await reset(app);
  await failed(app, 'LOGIN-A', 3, 'S-EDIT');
  await failed(app, 'LOGIN-A', 2, 'OWNER');
  limited(await source(app, 'LOGIN-A', ids));
  expect((await good(app, 'LOGIN-A', 'OWNER')).outcome).toBe('denied');
  await anonymous(app, 'LOGIN-A');
  expect((await good(app, 'LOGIN-B', 'OWNER')).outcome).toBe('accepted');
  await identified(app, 'LOGIN-B', ids, 'OWNER');
  notLimited(await source(app, 'LOGIN-B', ids));
  limited(await source(app, 'LOGIN-A', ids));
});

test('AUTH-LIMIT-060-success-source-only | AT-060 AC-060 | successful login resets only its own source, not another source counter', async ({ app }) => {
  const ids = await reset(app);
  await failed(app, 'LOGIN-A', 4); await failed(app, 'LOGIN-B', 4);
  expect((await good(app, 'LOGIN-A')).outcome).toBe('accepted'); await identified(app, 'LOGIN-A', ids);
  expect((await source(app, 'LOGIN-A', ids)).failedCount).toBe(0);
  expect((await source(app, 'LOGIN-B', ids)).failedCount).toBe(4);
  await failed(app, 'LOGIN-B', 1); limited(await source(app, 'LOGIN-B', ids));
  expect((await good(app, 'LOGIN-B')).outcome).toBe('denied'); await anonymous(app, 'LOGIN-B');
  await identified(app, 'LOGIN-A', ids);
});
