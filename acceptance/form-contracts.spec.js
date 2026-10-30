import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({
  app: async ({}, use) => {
    const app = await openApplicationDriver();
    try { await use(app); } finally { await app.close(); }
  },
});
const valid = () => ({ name: 'Тестовый посетитель', phone: '+70000000000', car: '', comment: '', consent: true });
const bounds = [
  ['name-empty', 'name', '', false], ['name-spaces', 'name', '   ', false],
  ['name-one', 'name', '李', true], ['name-99', 'name', 'А'.repeat(99), true],
  ['name-100', 'name', 'А'.repeat(100), true], ['name-101', 'name', 'А'.repeat(101), false],
  ['car-empty', 'car', '', true], ['car-299', 'car', 'А'.repeat(299), true],
  ['car-300', 'car', 'А'.repeat(300), true], ['car-301', 'car', 'А'.repeat(301), false],
  ['comment-empty', 'comment', '', true], ['comment-3999', 'comment', 'А'.repeat(3999), true],
  ['comment-4000', 'comment', 'А'.repeat(4000), true], ['comment-4001', 'comment', 'А'.repeat(4001), false],
  ['consent-missing', 'consent', undefined, false], ['consent-off', 'consent', false, false],
  ['phone-missing', 'phone', undefined, false], ['name-missing', 'name', undefined, false],
  ['name-NUL', 'name', 'Тест\0овый', false], ['comment-NUL', 'comment', 'Тест\0овый', false],
];
const phones = [
  ['plus7', '+70000000000', true], ['eight', '80000000000', true],
  ['ascii-separators', '+7 (000) 000-00-00', true],
  ['nbsp-separators', '+7\u00a0(000)\u202f000\u201000\u201100', true],
  ['en-dash', '8\u202f(000)\u00a0000\u201300\u201300', true],
  ['input-64', '+70000000000' + ' '.repeat(52), true],
  ['input-65', '+70000000000' + ' '.repeat(53), false],
  ['foreign-code', '+10000000000', false], ['extension', '+70000000000 доб.1', false],
  ['letters', '+7abcdefghij', false], ['double-plus', '++70000000000', false],
  ['short', '+7000000000', false], ['long', '+700000000000', false],
  ['unicode-digits', '+7００００００００００', false],
];

async function setup(app, source) {
  await app.reset('isolated-form-with-local-sinks');
  const opened = await app.act('VISITOR', 'open-form', { source });
  expect(opened.outcome).toBe('accepted');
  expect(opened.context).toBeTruthy();
  return opened.context;
}
function counterValues(value) {
  for (const key of ['requests', 'consents', 'acceptedGoals', 'telegramMessages'])
    expect(Number.isSafeInteger(value[key]) && value[key] >= 0, key).toBe(true);
  return value;
}
function intentLink(value) {
  expect(typeof value.intentKey === 'string' && value.intentKey.length > 0).toBe(true);
  expect(Array.isArray(value.requestIds)).toBe(true);
  for (const id of value.requestIds) expect(typeof id === 'string' && id.length > 0).toBe(true);
  expect(new Set(value.requestIds).size).toBe(value.requestIds.length);
  expect(typeof value.receiptCommitted).toBe('boolean');
  return value;
}
async function acceptedLink(app, source, context) {
  const link = intentLink(await app.observe('form-intent-records', { source, context }));
  expect(link.receiptCommitted).toBe(true); expect(link.requestIds).toHaveLength(1);
  return link;
}
async function acceptedRequest(app, source, context) {
  const link = await acceptedLink(app, source, context);
  const record = await app.observe('request-by-id', { id: link.requestIds[0] });
  expect(record.id).toBe(link.requestIds[0]);
  expect(record.original && typeof record.original === 'object').toBeTruthy();
  return record;
}
function oneAccepted(before, after) {
  counterValues(before); counterValues(after);
  expect(after.requests).toBe(before.requests + 1);
  expect(after.consents).toBe(before.consents + 1);
  expect(after.acceptedGoals - before.acceptedGoals).toBeGreaterThanOrEqual(0);
  expect(after.acceptedGoals - before.acceptedGoals).toBeLessThanOrEqual(1);
  expect(after.telegramMessages).toBe(before.telegramMessages);
}
function noAccepted(before, after) {
  counterValues(before); counterValues(after);
  for (const field of ['requests', 'consents', 'acceptedGoals', 'telegramMessages'])
    expect(after[field], field).toBe(before[field]);
}

for (const source of ['home', 'contacts']) {
  for (const [id, field, value, accepted] of bounds) {
    test(`FORM-${source}-${id} | AT-030 AT-108 AC-030 AC-DTL-008 | direct server validation`, async ({ app }) => {
      const context = await setup(app, source);
      const payload = valid();
      if (value === undefined) delete payload[field]; else payload[field] = value;
      const before = await app.observe('form-counters');
      const result = await app.act('VISITOR', 'submit-form-direct', { source, context, payload });
      const after = await app.observe('form-counters');
      if (accepted) {
        expect(result.outcome).toBe('accepted');
        oneAccepted(before, after);
        expect((await acceptedRequest(app, source, context)).original[field]).toBe(value);
      } else {
        expect(result.outcome).toBe('denied');
        expect(result.fieldErrors).toContain(field);
        noAccepted(before, after);
      }
    });
  }
  for (const [id, phone, accepted] of phones) {
    test(`PHONE-${source}-${id} | AT-031 AT-108 AC-031 AC-DTL-008 | +7/8 normalization and input bound`, async ({ app }) => {
      const context = await setup(app, source);
      const before = await app.observe('form-counters');
      const result = await app.act('VISITOR', 'submit-form-direct', { source, context, payload: { ...valid(), phone } });
      const after = await app.observe('form-counters');
      if (accepted) {
        expect(result.outcome).toBe('accepted');
        oneAccepted(before, after);
        expect((await acceptedRequest(app, source, context)).original.phone).toBe('+70000000000');
      } else {
        expect(result.outcome).toBe('denied');
        expect(result.fieldErrors).toContain('phone');
        noAccepted(before, after);
      }
    });
  }

  test(`FORM-${source}-same-intent-parallel | AT-032 AT-109 AC-032 AC-DTL-009 | two POSTs yield one request`, async ({ app }) => {
    const context = await setup(app, source);
    const before = await app.observe('form-counters');
    const submissions = await Promise.all([0, 1].map(() => app.act('VISITOR', 'submit-form-direct', { source, context, payload: valid() })));
    for (const result of submissions) expect(['accepted', 'pending']).toContain(result.outcome);
    // Pending is a real observed waiting response, never an accepted result inferred from a timeout.
    await expect.poll(async () => {
      const link = intentLink(await app.observe('form-intent-records', { source, context }));
      expect(link.requestIds.length).toBeLessThanOrEqual(1);
      return link.receiptCommitted && link.requestIds.length === 1;
    }, { timeout: 8000 }).toBe(true);
    const link = await acceptedLink(app, source, context);
    const repeated = await app.act('VISITOR', 'submit-form-direct', { source, context, payload: valid() });
    expect(repeated.outcome).toBe('accepted');
    const afterRepeat = await acceptedLink(app, source, context);
    for (const key of ['intentKey', 'requestIds', 'receiptCommitted']) expect(afterRepeat[key]).toEqual(link[key]);
    oneAccepted(before, await app.observe('form-counters'));
  });

  test(`FORM-${source}-same-intent-different-payload | AT-110 AC-DTL-010 | accepted original is never overwritten`, async ({ app }) => {
    const context = await setup(app, source);
    const first = await app.act('VISITOR', 'submit-form-direct', { source, context, payload: valid() });
    expect(first.outcome).toBe('accepted');
    const request = await acceptedRequest(app, source, context);
    const before = await app.observe('form-counters');
    const result = await app.act('VISITOR', 'submit-form-direct', { source, context, payload: { ...valid(), comment: 'Иное содержимое' } });
    expect(result.outcome).toBe('conflict');
    noAccepted(before, await app.observe('form-counters'));
    expect((await acceptedRequest(app, source, context)).original).toEqual(request.original);
  });

  test(`FORM-${source}-new-intent-same-phone | AT-110 AC-DTL-010 | separate explicit request is allowed`, async ({ app }) => {
    const context = await setup(app, source);
    const before = await app.observe('form-counters');
    const first = await app.act('VISITOR', 'submit-form-direct', { source, context, payload: valid() });
    expect(first.outcome).toBe('accepted');
    const firstLink = await acceptedLink(app, source, context);
    const next = await app.act('VISITOR', 'explicit-new-form-intent', { source });
    expect(next.outcome).toBe('accepted');
    expect(next.context).toBeTruthy();
    const second = await app.act('VISITOR', 'submit-form-direct', { source, context: next.context, payload: valid() });
    expect(second.outcome).toBe('accepted');
    const secondLink = await acceptedLink(app, source, next.context);
    expect(secondLink.intentKey).not.toBe(firstLink.intentKey);
    expect(secondLink.requestIds[0]).not.toBe(firstLink.requestIds[0]);
    const after = await app.observe('form-counters');
    counterValues(before); counterValues(after);
    expect(after.requests).toBe(before.requests + 2);
    expect(after.consents).toBe(before.consents + 2);
    expect(after.acceptedGoals - before.acceptedGoals).toBeGreaterThanOrEqual(0);
    expect(after.acceptedGoals - before.acceptedGoals).toBeLessThanOrEqual(2);
    expect(after.telegramMessages).toBe(before.telegramMessages);
  });
}
