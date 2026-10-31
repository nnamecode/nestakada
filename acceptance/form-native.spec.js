import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

// This switch configures the real actor browser, not only an inert HTML parser.
const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver({ javaScriptEnabled: false });
  try { await use(app); } finally { await app.close(); }
} });
const payload = () => ({ name: 'Синтетический посетитель', phone: '+70000000000', car: '', comment: 'NATIVE-FORM-OWN-INPUT', consent: true });
const required = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
async function counts(app) {
  const value = await app.observe('form-counters');
  for (const field of ['requests', 'consents', 'acceptedGoals', 'telegramMessages'])
    expect(Number.isSafeInteger(value[field]) && value[field] >= 0).toBe(true);
  return value;
}
async function allocation(app) {
  const value = await app.observe('form-allocation-counters');
  for (const field of ['receipts', 'visitorDbSessions']) expect(Number.isSafeInteger(value[field]) && value[field] >= 0).toBe(true);
  return value;
}
function noStore(result) {
  const directives = required(result.cacheControl).toLowerCase().split(',').map(value => value.trim());
  expect(directives).toContain('private'); expect(directives).toContain('no-store');
}
async function open(app, source) {
  await app.reset('isolated-form-with-local-sinks');
  const before = await counts(app), allocated = await allocation(app);
  // Bound only to UI goto; returned token fields are extracted from actual GET HTML.
  const opened = await app.act('VISITOR', 'open-native-form', { source });
  expect(opened.outcome).toBe('accepted'); expect(opened.observedStatus).toBe(200);
  expect(required(opened.formMethod).toLowerCase()).toBe('post');
  for (const field of ['csrfToken', 'signedIntent']) required(opened[field]);
  required(opened.context);
  expect(await counts(app)).toEqual(before); expect(await allocation(app)).toEqual(allocated);
  return opened;
}
async function oneRequest(app, source, context, before) {
  const after = await counts(app);
  expect(after.requests).toBe(before.requests + 1); expect(after.consents).toBe(before.consents + 1);
  expect(after.acceptedGoals - before.acceptedGoals).toBeGreaterThanOrEqual(0);
  expect(after.acceptedGoals - before.acceptedGoals).toBeLessThanOrEqual(1);
  expect(after.telegramMessages).toBe(before.telegramMessages);
  const link = await app.observe('form-intent-records', { source, context });
  expect(link.receiptCommitted).toBe(true); expect(link.requestIds).toHaveLength(1);
  const record = await app.observe('request-by-id', { id: required(link.requestIds[0]) });
  expect(record.original.name).toBe(payload().name); expect(record.original.comment).toBe(payload().comment);
  const consent = await app.observe('form-consent-evidence', { source, context });
  required(consent.version); expect(consent.requestId).toBe(link.requestIds[0]);
  return after;
}

for (const source of ['home', 'contacts']) {
  test(`FORM-NATIVE-${source}-submit | AT-401 AC-PRO-001 | actual JS-disabled browser submits native HTML form`, async ({ app }) => {
    const opened = await open(app, source), before = await counts(app);
    // UI fill/check/click of native submit. No fetch(), request.post(), injected script or hidden-token replacement.
    const result = await app.act('VISITOR', 'submit-native-form', { source, payload: payload() });
    expect(result.outcome).toBe('accepted');
    await oneRequest(app, source, opened.context, before);
  });
  for (const mode of ['without', 'corrupt']) {
    test(`FORM-NATIVE-${source}-csrf-${mode} | AT-401 AT-404 AC-PRO-001 AC-PRO-004 | real POST rejects missing or corrupt CSRF before insertion`, async ({ app }) => {
      const opened = await open(app, source), before = await counts(app), allocated = await allocation(app);
      const result = await app.act('VISITOR', `submit-form-${mode}-csrf`, { source, context: opened.context, payload: payload() });
      expect(result.outcome).toBe('denied'); noStore(result);
      expect(await counts(app)).toEqual(before); expect(await allocation(app)).toEqual(allocated);
      // The untouched real browser form remains usable after a forged direct POST.
      expect((await app.act('VISITOR', 'submit-native-form', { source, payload: payload() })).outcome).toBe('accepted');
      await oneRequest(app, source, opened.context, before);
    });
  }
  test(`FORM-NATIVE-${source}-csrf-before-receipt | AT-404 AC-PRO-004 | accepted intent does not bypass CSRF authentication`, async ({ app }) => {
    const opened = await open(app, source), before = await counts(app);
    expect((await app.act('VISITOR', 'submit-native-form', { source, payload: payload() })).outcome).toBe('accepted');
    const accepted = await oneRequest(app, source, opened.context, before), allocated = await allocation(app);
    const record = await app.observe('form-intent-records', { source, context: opened.context });
    const result = await app.act('VISITOR', 'submit-form-corrupt-csrf', { source, context: opened.context, payload: payload() });
    expect(result.outcome).toBe('denied'); noStore(result);
    expect(await counts(app)).toEqual(accepted); expect(await allocation(app)).toEqual(allocated);
    expect(await app.observe('form-intent-records', { source, context: opened.context })).toEqual(record);
  });
}
