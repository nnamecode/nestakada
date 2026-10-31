import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await use(app); } finally { await app.close(); }
} });
const variants = [
  ['same-live-context', null],
  ['new-context', 'contextFingerprint'], ['new-csrf-secret', 'csrfFingerprint'],
  ['new-consent', 'consentVersion'], ['new-protection-interval', 'protectionInterval'],
  ['missing-context-cookie', 'contextCookieState'], ['invalid-context-cookie', 'contextCookieState'],
  ['new-public-data', 'publicDataRevision'], ['new-template', 'templateRevision'],
  ['new-form-policy', 'formPolicyRevision'],
];
const dimensions = ['contextFingerprint', 'csrfFingerprint', 'consentVersion', 'protectionInterval',
  'contextCookieState', 'publicDataRevision', 'templateRevision', 'formPolicyRevision'];
const payload = () => ({ name: 'Синтетический посетитель', phone: '+70000000000', car: '',
  comment: 'FORM-CACHE-OWN-INPUT', consent: true });
function nonempty(value) { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; }
function counts(value) {
  for (const key of ['receiptRows', 'databaseSessionRows'])
    expect(Number.isSafeInteger(value[key]) && value[key] >= 0, key).toBe(true);
  return value;
}
function business(value) {
  for (const key of ['requests', 'consents', 'acceptedGoals', 'telegramMessages'])
    expect(Number.isSafeInteger(value[key]) && value[key] >= 0, key).toBe(true);
  return value;
}
function cacheHeaders(value) {
  nonempty(value.etag); expect(/^W\/"[^"\r\n]+"$/.test(value.etag)).toBe(true);
  const directives = nonempty(value.cacheControl).toLowerCase().split(',').map(item => item.trim());
  expect(directives).toContain('private'); expect(directives).toContain('no-cache');
  expect(directives.some(item => item === 'public' || item.startsWith('s-maxage'))).toBe(false);
  expect(nonempty(value.vary).toLowerCase().split(',').map(item => item.trim())).toContain('cookie');
}
async function setup(app, source, variant, changedDimension) {
  await app.reset('form-preissued-cache-variant', { source, variant });
  const prepared = await app.observe('prepared-form-cache');
  expect(prepared.source).toBe(source); expect(prepared.clockScope).toBe('isolated-test-process');
  expect(prepared.issuedByActualFormGet).toBe(true); expect(prepared.initial.observedStatus).toBe(200);
  nonempty(prepared.initial.context); cacheHeaders(prepared.initial);
  for (const dimension of dimensions) {
    nonempty(prepared.before[dimension]); nonempty(prepared.after[dimension]);
    if (dimension === changedDimension) expect(prepared.after[dimension]).not.toBe(prepared.before[dimension]);
    else expect(prepared.after[dimension]).toBe(prepared.before[dimension]);
  }
  expect(prepared.before.contextCookieState).toBe('valid');
  if (variant === 'missing-context-cookie') expect(prepared.after.contextCookieState).toBe('missing');
  else if (variant === 'invalid-context-cookie') expect(prepared.after.contextCookieState).toBe('invalid');
  else expect(prepared.after.contextCookieState).toBe('valid');
  counts(prepared.storageBeforeInitialGet);
  expect(counts(await app.observe('form-storage-counters'))).toEqual(prepared.storageBeforeInitialGet);
  return prepared;
}
async function submitUsable(app, source, context) {
  const before = business(await app.observe('form-counters'));
  const result = await app.act('VISITOR', 'submit-form-direct', { source, context, payload: payload() });
  expect(result.outcome).toBe('accepted');
  const after = business(await app.observe('form-counters'));
  expect(after.requests).toBe(before.requests + 1); expect(after.consents).toBe(before.consents + 1);
  expect(after.acceptedGoals - before.acceptedGoals).toBeGreaterThanOrEqual(0);
  expect(after.acceptedGoals - before.acceptedGoals).toBeLessThanOrEqual(1);
  expect(after.telegramMessages).toBe(before.telegramMessages);
  const link = await app.observe('form-intent-records', { source, context });
  nonempty(link.intentKey); expect(link.receiptCommitted).toBe(true);
  expect(Array.isArray(link.requestIds)).toBe(true); expect(link.requestIds).toHaveLength(1);
  const record = await app.observe('request-by-id', { id: nonempty(link.requestIds[0]) });
  expect(record.id).toBe(link.requestIds[0]); expect(record.original?.comment).toBe(payload().comment);
}

for (const source of ['home', 'contacts']) {
  for (const [variant, changedDimension] of variants) {
    test(`FORM-CACHE-${source}-${variant} | AT-402 AC-PRO-002 | conditional GET preserves usable CSRF and intent`, async ({ app }) => {
      const prepared = await setup(app, source, variant, changedDimension);
      const before = business(await app.observe('form-counters'));
      const result = await app.act('VISITOR', 'revalidate-form-etag', { source, etag: prepared.initial.etag });
      expect(business(await app.observe('form-counters'))).toEqual(before);
      expect(counts(await app.observe('form-storage-counters'))).toEqual(prepared.storageBeforeInitialGet);
      if (changedDimension) expect(result.observedStatus).toBe(200);
      else expect([200, 304]).toContain(result.observedStatus);
      let context;
      if (result.observedStatus === 304) {
        expect(result.outcome).toBe('not-modified'); expect(result.body).toBe('');
        cacheHeaders(result); expect(result.etag).toBe(prepared.initial.etag);
        context = prepared.initial.context;
      } else {
        expect(result.outcome).toBe('accepted'); cacheHeaders(result); context = nonempty(result.context);
        if (changedDimension && !['missing-context-cookie', 'invalid-context-cookie'].includes(variant))
          expect(result.etag).not.toBe(prepared.initial.etag);
      }
      // Explicit POST uses the selected real representation, never a driver-generated replacement.
      await submitUsable(app, source, context);
    });
  }
  test(`FORM-CACHE-${source}-ims-only | AT-402 AC-PRO-002 | Last-Modified alone cannot validate a protected form`, async ({ app }) => {
    const prepared = await setup(app, source, 'same-live-context', null);
    const before = business(await app.observe('form-counters'));
    // A future date also exercises servers that would otherwise accept any sufficiently recent IMS.
    const result = await app.act('VISITOR', 'revalidate-form-ims', { source, modifiedSince: 'Wed, 31 Dec 2098 23:59:59 GMT' });
    expect(result.observedStatus).toBe(200); expect(result.outcome).toBe('accepted'); cacheHeaders(result);
    expect(business(await app.observe('form-counters'))).toEqual(before);
    expect(counts(await app.observe('form-storage-counters'))).toEqual(prepared.storageBeforeInitialGet);
    await submitUsable(app, source, nonempty(result.context));
  });
}
