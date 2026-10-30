import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await use(app); } finally { await app.close(); }
} });
const valid = () => ({ name: 'Синтетический посетитель', phone: '+70000000000', car: '', comment: 'FORM-WINDOW-OWN-INPUT', consent: true });
const required = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
function counters(value) {
  for (const field of ['requests', 'consents', 'acceptedGoals', 'telegramMessages'])
    expect(Number.isSafeInteger(value[field]) && value[field] >= 0, field).toBe(true);
  return value;
}
async function counts(app) { return counters(await app.observe('form-counters')); }
function unchanged(before, after) {
  counters(before); counters(after);
  for (const field of ['requests', 'consents', 'acceptedGoals', 'telegramMessages']) expect(after[field]).toBe(before[field]);
}
function oneNew(before, after) {
  counters(before); counters(after);
  expect(after.requests).toBe(before.requests + 1); expect(after.consents).toBe(before.consents + 1);
  expect(after.acceptedGoals - before.acceptedGoals).toBeGreaterThanOrEqual(0);
  expect(after.acceptedGoals - before.acceptedGoals).toBeLessThanOrEqual(1);
  expect(after.telegramMessages).toBe(before.telegramMessages);
}
function epoch(value) { required(value); const result = Date.parse(value); expect(Number.isFinite(result)).toBe(true); return result; }
async function setup(app, source, options) {
  await app.reset('form-preissued-controlled-window', { source, ...options });
  const prepared = await app.observe('prepared-form-window');
  expect(prepared.source).toBe(source); expect(prepared.context).toBeTruthy();
  expect(prepared.issuedByActualFormGet).toBe(true); expect(prepared.clockScope).toBe('isolated-test-process');
  epoch(prepared.serverNow); epoch(prepared.issuedAt);
  if (options.tokenAgeSeconds !== undefined) expect(epoch(prepared.serverNow) - epoch(prepared.issuedAt)).toBe(options.tokenAgeSeconds * 1000);
  if (options.receiptAgeSeconds !== undefined) {
    expect(epoch(prepared.serverNow) - epoch(prepared.acceptedAt)).toBe(options.receiptAgeSeconds * 1000);
    // Receipt lifetime starts at acceptance, not issuance; both timestamps come from actual operations.
    expect(epoch(prepared.acceptedAt) - epoch(prepared.issuedAt)).toBe(600 * 1000);
    required(prepared.requestId);
    const record = await app.observe('request-by-id', { id: prepared.requestId });
    expect(record.id).toBe(prepared.requestId); expect(record.original?.comment).toBe(valid().comment);
  }
  return prepared;
}
async function submit(app, source, context) {
  return app.act('VISITOR', 'submit-form-direct', { source, context, payload: valid() });
}
async function privateIntentKey(app, source, context) {
  const link = await app.observe('form-intent-records', { source, context });
  return required(link.intentKey);
}
async function privateRequestId(app, source, context) {
  const link = await app.observe('form-intent-records', { source, context });
  required(link.intentKey); expect(link.receiptCommitted).toBe(true);
  expect(Array.isArray(link.requestIds)).toBe(true);
  expect(link.requestIds).toHaveLength(1); return required(link.requestIds[0]);
}
async function explicitNew(app, source) {
  const result = await app.act('VISITOR', 'explicit-new-form-intent', { source });
  expect(result.outcome).toBe('accepted'); expect(result.context).toBeTruthy(); return result.context;
}
async function consentEvidence(app, source, context) {
  const evidence = await app.observe('form-consent-evidence', { source, context });
  required(evidence.id); required(evidence.requestId); required(evidence.version); epoch(evidence.acceptedAt);
  expect(evidence.requestId).toBe(await privateRequestId(app, source, context));
  return evidence;
}

for (const source of ['home', 'contacts']) {
  for (const [age, accepted] of [[1799, true], [1801, false]]) {
    test(`FORM-WINDOW-${source}-issue-${age} | AT-111 AC-DTL-011 | beginning is bounded by actual token issuance age`, async ({ app }) => {
      const prepared = await setup(app, source, { tokenAgeSeconds: age });
      const before = await counts(app), result = await submit(app, source, prepared.context), after = await counts(app);
      if (accepted) {
        expect(result.outcome).toBe('accepted'); oneNew(before, after); await privateRequestId(app, source, prepared.context);
      } else {
        expect(result.outcome).toBe('denied'); unchanged(before, after);
        expect(result.body).toContain('Срок защиты отправки истёк');
      }
    });
  }
  for (const [age, accepted] of [[86399, true], [86401, false]]) {
    test(`FORM-WINDOW-${source}-receipt-${age} | AT-111 AC-DTL-011 | accepted receipt lifetime is measured from commit`, async ({ app }) => {
      const prepared = await setup(app, source, { receiptAgeSeconds: age });
      const before = await counts(app); expect(before.requests).toBeGreaterThan(0); expect(before.consents).toBeGreaterThan(0);
      const original = await app.observe('request-by-id', { id: prepared.requestId });
      const result = await submit(app, source, prepared.context);
      expect(result.outcome).toBe(accepted ? 'accepted' : 'denied'); unchanged(before, await counts(app));
      expect((await app.observe('request-by-id', { id: prepared.requestId })).original).toEqual(original.original);
      if (accepted) expect(await privateRequestId(app, source, prepared.context)).toBe(prepared.requestId);
      else expect(result.body).toContain('Срок защиты отправки истёк');
    });
  }
  test(`FORM-WINDOW-${source}-expired-issue-explicit-new | AT-111 AT-110 AC-DTL-011 AC-DTL-010 | protection refresh does not silently submit expired input`, async ({ app }) => {
    const prepared = await setup(app, source, { tokenAgeSeconds: 1801 }), before = await counts(app);
    const oldIntentKey = await privateIntentKey(app, source, prepared.context);
    expect((await submit(app, source, prepared.context)).outcome).toBe('denied'); unchanged(before, await counts(app));
    const next = await explicitNew(app, source); unchanged(before, await counts(app));
    expect((await submit(app, source, next)).outcome).toBe('accepted'); oneNew(before, await counts(app));
    expect(await privateIntentKey(app, source, next)).not.toBe(oldIntentKey);
    await privateRequestId(app, source, next);
    const afterNew = await counts(app);
    expect((await submit(app, source, prepared.context)).outcome).toBe('denied');
    unchanged(afterNew, await counts(app));
  });
  test(`FORM-WINDOW-${source}-expired-receipt-explicit-new | AT-111 AT-110 AC-DTL-011 AC-DTL-010 | old receipt never becomes a new insertion`, async ({ app }) => {
    const prepared = await setup(app, source, { receiptAgeSeconds: 86401 }), before = await counts(app);
    const oldIntentKey = await privateIntentKey(app, source, prepared.context);
    expect((await submit(app, source, prepared.context)).outcome).toBe('denied'); unchanged(before, await counts(app));
    const next = await explicitNew(app, source); unchanged(before, await counts(app));
    expect((await submit(app, source, next)).outcome).toBe('accepted'); oneNew(before, await counts(app));
    expect(await privateIntentKey(app, source, next)).not.toBe(oldIntentKey);
    expect(await privateRequestId(app, source, next)).not.toBe(prepared.requestId);
    const afterNew = await counts(app);
    expect((await submit(app, source, prepared.context)).outcome).toBe('denied'); unchanged(afterNew, await counts(app));
  });
  test(`FORM-WINDOW-${source}-csrf-receipt | AT-404 AC-PRO-004 | old CSRF cannot bypass checks merely because receipt exists`, async ({ app }) => {
    const prepared = await setup(app, source, { receiptAgeSeconds: 60, rotateCsrfAfterIssue: true });
    const oldIntentKey = await privateIntentKey(app, source, prepared.context);
    expect(prepared.csrfSecretChanged).toBe(true); const before = await counts(app);
    const denied = await submit(app, source, prepared.context); expect(denied.outcome).toBe('denied'); unchanged(before, await counts(app));
    expect(denied.cacheControl).toContain('no-store');
    const refreshed = await app.act('VISITOR', 'refresh-old-intent-csrf', { source, context: prepared.context });
    expect(refreshed.outcome).toBe('accepted'); expect(refreshed.context).toBeTruthy(); unchanged(before, await counts(app));
    expect(await privateIntentKey(app, source, refreshed.context)).toBe(oldIntentKey);
    expect((await submit(app, source, refreshed.context)).outcome).toBe('accepted'); unchanged(before, await counts(app));
    expect(await privateRequestId(app, source, refreshed.context)).toBe(prepared.requestId);
  });
  test(`FORM-WINDOW-${source}-accepted-old-consent | AT-109 AT-403 AC-DTL-009 AC-PRO-003 | policy change does not invalidate a matching accepted original`, async ({ app }) => {
    const prepared = await setup(app, source, { receiptAgeSeconds: 60, changeConsentAfterIssue: true });
    required(prepared.issuedConsentVersion); required(prepared.currentConsentVersion);
    expect(prepared.issuedConsentVersion).not.toBe(prepared.currentConsentVersion);
    const before = await counts(app), original = await app.observe('request-by-id', { id: prepared.requestId });
    const acceptedConsent = await consentEvidence(app, source, prepared.context);
    expect(acceptedConsent.version).toBe(prepared.issuedConsentVersion);
    expect(acceptedConsent.version).not.toBe(prepared.currentConsentVersion);
    expect((await submit(app, source, prepared.context)).outcome).toBe('accepted'); unchanged(before, await counts(app));
    expect(await privateRequestId(app, source, prepared.context)).toBe(prepared.requestId);
    expect((await app.observe('request-by-id', { id: prepared.requestId })).original).toEqual(original.original);
    expect(await consentEvidence(app, source, prepared.context)).toEqual(acceptedConsent);
  });
  test(`FORM-WINDOW-${source}-unaccepted-old-consent | AT-109 AC-DTL-009 | a new insertion still requires the current consent version`, async ({ app }) => {
    const prepared = await setup(app, source, { tokenAgeSeconds: 60, changeConsentAfterIssue: true });
    const oldIntentKey = await privateIntentKey(app, source, prepared.context);
    required(prepared.issuedConsentVersion); required(prepared.currentConsentVersion);
    expect(prepared.issuedConsentVersion).not.toBe(prepared.currentConsentVersion);
    const before = await counts(app);
    expect((await submit(app, source, prepared.context)).outcome).toBe('denied'); unchanged(before, await counts(app));
    const next = await explicitNew(app, source); unchanged(before, await counts(app));
    expect((await submit(app, source, next)).outcome).toBe('accepted'); oneNew(before, await counts(app));
    expect(await privateIntentKey(app, source, next)).not.toBe(oldIntentKey);
    expect((await consentEvidence(app, source, next)).version).toBe(prepared.currentConsentVersion);
  });
  test(`FORM-WINDOW-${source}-get-storage | AT-112 AC-DTL-012 | repeated real form GETs do not allocate receipt or DB sessions`, async ({ app }) => {
    await app.reset('isolated-form-with-local-sinks');
    const before = await app.observe('form-storage-counters');
    for (const key of ['receiptRows', 'databaseSessionRows']) expect(Number.isSafeInteger(before[key]) && before[key] >= 0).toBe(true);
    const businessBefore = await counts(app);
    for (let n = 0; n < 4; n++) {
      const opened = await app.act('VISITOR', 'open-form', { source });
      expect(opened.outcome).toBe('accepted'); expect(opened.context).toBeTruthy();
    }
    const after = await app.observe('form-storage-counters');
    for (const key of ['receiptRows', 'databaseSessionRows']) expect(after[key]).toBe(before[key]);
    unchanged(businessBefore, await counts(app));
  });
}
