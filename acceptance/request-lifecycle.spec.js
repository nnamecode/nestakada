import { randomUUID } from 'node:crypto';
import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await use(app); } finally { await app.close(); }
} });
function id(value) { expect(typeof value === 'string' && value.length > 0).toBe(true); }
function request(value) {
  for (const key of ['id', 'revision', 'createdAt', 'assignee']) id(value[key]);
  expect(['new', 'in_progress', 'done', 'cancelled']).toContain(value.status);
  expect(value.original && typeof value.original === 'object').toBeTruthy();
  expect(Object.keys(value.original).length).toBeGreaterThan(0);
  expect(Array.isArray(value.notes)).toBe(true); expect(Array.isArray(value.history)).toBe(true);
  return value;
}
async function current(app) { return request(await app.observe('request', { request: 'R-ONE' })); }
function unchanged(after, before, fields = ['id', 'createdAt', 'original', 'status', 'assignee', 'revision', 'notes', 'history']) {
  for (const key of fields) { expect(before).toHaveProperty(key); expect(after).toHaveProperty(key); expect(after[key]).toEqual(before[key]); }
}
async function reopenPreparation(app, actor, before) {
  const result = await app.act(actor, 'prepare-request-reopen', { request: 'R-ONE', base: before.revision });
  expect(result.outcome).toBe('accepted'); expect(result.confirmation).toBeTruthy();
  expect(result.displayed.requestId).toBe(before.id); expect(result.displayed.fromStatus).toBe(before.status);
  return result.confirmation;
}
async function deletionSetup(app) {
  const admission = await app.inspectInfrastructureAdmission();
  expect(admission.arc10Verified).toBe(true); expect(admission.isolatedInfrastructure).toBe(true);
  id(admission.reviewedEvidenceId); expect(admission.capabilities).toContain('request-deletion-v1');
  await app.reset('request-delete-with-live-receipt');
  const existing = await current(app);
  expect(JSON.stringify(existing.original)).toContain('REQUEST-PRIVATE-CANARY');
  expect(existing.notes.length).toBeGreaterThan(0);
  expect(JSON.stringify(existing.notes)).toContain('NOTE-PRIVATE-CANARY');
  const ownerRead = await app.act('OWNER', 'view-request-direct', { request: 'R-ONE' });
  expect(ownerRead.outcome).toBe('accepted'); expect(ownerRead.body).toContain('REQUEST-PRIVATE-CANARY');
  const ownerNotes = await app.act('OWNER', 'view-request-notes-direct', { request: 'R-ONE' });
  expect(ownerNotes.outcome).toBe('accepted'); expect(ownerNotes.body).toContain('NOTE-PRIVATE-CANARY');
}
async function deletionPreparation(app, before) {
  const result = await app.act('OWNER', 'prepare-request-delete', { request: 'R-ONE', base: before.revision });
  expect(result.outcome).toBe('accepted'); expect(result.confirmation).toBeTruthy(); id(result.operationId);
  expect(result.displayed.requestId).toBe(before.id); expect(result.displayed.createdAt).toBe(before.createdAt);
  expect(result.displayed.requiresOwnerPassword).toBe(true);
  return { confirmation: result.confirmation, operationId: result.operationId, passwordRef: 'OWNER-CURRENT-SECRET' };
}
async function deletionEvidence(app, before, operationId) {
  const state = await app.observe('deleted-request-evidence', { requestId: before.id, operationId });
  expect(state.requestId).toBe(before.id); expect(state.operationId).toBe(operationId);
  expect(state.requestExists).toBe(false); expect(state.notesExist).toBe(false);
  expect(state.independentTombstoneCommitted).toBe(true); id(state.tombstoneId);
  expect(state.containsOriginalBody).toBe(false);
}

for (const actor of ['OWNER', 'S-EDIT']) for (const status of ['done', 'cancelled']) {
  test(`REQUEST-reopen-${actor}-${status} | AT-034 AT-113 AC-034 AC-DTL-013 | explicit confirmation reopens the same request`, async ({ app }) => {
    await app.reset('request-status-matrix', { status }); const before = await current(app);
    expect(before.status).toBe(status);
    const confirmation = await reopenPreparation(app, actor, before);
    unchanged(await current(app), before);
    expect((await app.act(actor, 'reopen-request-direct', { request: 'R-ONE', base: before.revision, confirmation })).outcome).toBe('accepted');
    const after = await current(app); expect(after.status).toBe('in_progress'); expect(after.revision).not.toBe(before.revision);
    unchanged(after, before, ['id', 'createdAt', 'original', 'notes', 'assignee']);
    expect(after.history).toHaveLength(before.history.length + 1);
    expect(after.history.at(-1)).toMatchObject({ actor, from: status, to: 'in_progress' });
    expect((await app.observe('request-record-count', { requestId: before.id })).count).toBe(1);
  });
  test(`REQUEST-unconfirmed-${actor}-${status} | AT-034 AT-113 AC-034 AC-DTL-013 | reopening cannot use an omitted confirmation`, async ({ app }) => {
    await app.reset('request-status-matrix', { status }); const before = await current(app);
    const confirmation = await reopenPreparation(app, actor, before);
    const args = { request: 'R-ONE', base: before.revision };
    expect((await app.act(actor, 'reopen-request-direct', args)).outcome).toBe('denied');
    unchanged(await current(app), before);
    expect((await app.act(actor, 'reopen-request-direct', { ...args, confirmation })).outcome).toBe('accepted');
    expect((await current(app)).status).toBe('in_progress');
  });
}

test('REQUEST-reopen-other-role | AT-033 AT-034 AC-033 AC-034 | valid owner confirmation cannot grant another employee access', async ({ app }) => {
  await app.reset('request-status-matrix', { status: 'done' }); const before = await current(app);
  const confirmation = await reopenPreparation(app, 'OWNER', before);
  const args = { request: 'R-ONE', base: before.revision, confirmation };
  expect((await app.act('S-OTHER', 'reopen-request-direct', args)).outcome).toBe('denied');
  unchanged(await current(app), before);
  expect((await app.act('OWNER', 'reopen-request-direct', args)).outcome).toBe('accepted');
  expect((await current(app)).status).toBe('in_progress');
});

test('REQUEST-status-race | AT-113 AC-DTL-013 | two transitions from one revision create one history transition', async ({ app }) => {
  await app.reset('new-request-assigned-to-S-EDIT'); const before = await current(app);
  expect(before.status).toBe('new'); const targets = ['done', 'cancelled'];
  const results = await Promise.all(targets.map(target => app.act('OWNER', 'change-request-status', {
    request: 'R-ONE', base: before.revision, target, operationId: randomUUID(),
  })));
  expect(results.map(result => result.outcome).sort()).toEqual(['accepted', 'conflict']);
  const target = targets[results.findIndex(result => result.outcome === 'accepted')], after = await current(app);
  expect(after.status).toBe(target); expect(after.history).toHaveLength(before.history.length + 1);
  expect(after.history.at(-1)).toMatchObject({ actor: 'OWNER', from: 'new', to: target });
  unchanged(after, before, ['id', 'createdAt', 'original', 'notes', 'assignee']);
});

test('REQUEST-identical-command | AT-113 AC-DTL-013 | repeat of an accepted command does not append another transition', async ({ app }) => {
  await app.reset('new-request-assigned-to-S-EDIT'); const before = await current(app);
  const args = { request: 'R-ONE', base: before.revision, target: 'done', operationId: randomUUID() };
  expect((await app.act('OWNER', 'change-request-status', args)).outcome).toBe('accepted');
  const first = await current(app); expect(first.status).toBe('done'); expect(first.history).toHaveLength(before.history.length + 1);
  expect((await app.act('OWNER', 'change-request-status', args)).outcome).toBe('accepted');
  unchanged(await current(app), first);
});

for (const actor of ['S-EDIT', 'S-OTHER']) {
  test(`REQUEST-assignment-role-${actor} | AT-033 AC-033 | same valid assignment remains owner-only`, async ({ app }) => {
    await app.reset('request-with-two-active-assignees'); const before = await current(app);
    expect(before.assignee).toBe('S-EDIT');
    const args = { request: 'R-ONE', base: before.revision, assignee: 'S-OTHER' };
    expect((await app.act(actor, 'assign-request-direct', args)).outcome).toBe('denied');
    unchanged(await current(app), before);
    expect((await app.act('OWNER', 'assign-request-direct', args)).outcome).toBe('accepted');
    const after = await current(app); expect(after.assignee).toBe('S-OTHER');
    unchanged(after, before, ['id', 'createdAt', 'original', 'notes', 'status']);
    expect(after.history).toHaveLength(before.history.length + 1);
  });
}

test('REQUEST-reassignment-access | AT-033 AT-113 AC-033 AC-DTL-013 | reassignment immediately changes direct read/note privileges', async ({ app }) => {
  await app.reset('request-with-two-active-assignees'); const before = await current(app);
  const oldRead = await app.act('S-EDIT', 'view-request-direct', { request: 'R-ONE' });
  expect(oldRead.outcome).toBe('accepted'); expect(oldRead.body).toContain('REQUEST-PRIVATE-CANARY');
  expect((await app.act('OWNER', 'assign-request-direct', { request: 'R-ONE', base: before.revision, assignee: 'S-OTHER' })).outcome).toBe('accepted');
  const assigned = await current(app); expect(assigned.assignee).toBe('S-OTHER');
  const denied = await app.act('S-EDIT', 'view-request-direct', { request: 'R-ONE' });
  expect(denied.outcome).toBe('denied'); expect(denied.body).not.toContain('REQUEST-PRIVATE-CANARY');
  const args = { request: 'R-ONE', base: assigned.revision, text: 'Новое тестовое уточнение' };
  expect((await app.act('S-EDIT', 'add-request-note', args)).outcome).toBe('denied'); unchanged(await current(app), assigned);
  const newRead = await app.act('S-OTHER', 'view-request-direct', { request: 'R-ONE' });
  expect(newRead.outcome).toBe('accepted'); expect(newRead.body).toContain('REQUEST-PRIVATE-CANARY');
  expect((await app.act('S-OTHER', 'add-request-note', args)).outcome).toBe('accepted');
  const after = await current(app); expect(after.notes).toHaveLength(assigned.notes.length + 1);
  expect(after.notes.at(-1)).toMatchObject({ actor: 'S-OTHER', text: args.text }); unchanged(after, before, ['id', 'createdAt', 'original', 'status']);
});

test('REQUEST-inactive-assignee | AT-033 AC-033 | inactive target does not receive a request or its contents', async ({ app }) => {
  await app.reset('request-with-two-active-assignees'); const before = await current(app);
  const identity = await app.observe('employee', { employee: 'S-OFF' }); expect(identity.active).toBe(false);
  expect((await app.act('OWNER', 'assign-request-direct', { request: 'R-ONE', base: before.revision, assignee: 'S-OFF' })).outcome).toBe('denied');
  unchanged(await current(app), before);
  expect((await app.act('OWNER', 'assign-request-direct', { request: 'R-ONE', base: before.revision, assignee: 'S-OTHER' })).outcome).toBe('accepted');
  expect((await current(app)).assignee).toBe('S-OTHER');
});

test('REQUEST-stale-note | AT-035 AT-113 AC-035 AC-DTL-013 | old revision cannot overwrite a new note', async ({ app }) => {
  await app.reset('new-request-assigned-to-S-EDIT'); const before = await current(app);
  const firstText = 'Первое независимое уточнение';
  expect((await app.act('OWNER', 'add-request-note', { request: 'R-ONE', base: before.revision, text: firstText })).outcome).toBe('accepted');
  const first = await current(app); expect(first.notes).toHaveLength(before.notes.length + 1);
  expect(first.notes.at(-1).text).toBe(firstText); expect(first.revision).not.toBe(before.revision);
  expect((await app.act('S-EDIT', 'add-request-note', { request: 'R-ONE', base: before.revision, text: 'Устаревшее уточнение' })).outcome).toBe('conflict');
  unchanged(await current(app), first);
});

for (const actor of ['S-EDIT', 'VISITOR']) {
  test(`REQUEST-delete-role-${actor} | AT-037 AC-037 | owner-confirmed deletion cannot be executed by another role`, async ({ app }) => {
    await deletionSetup(app); const before = await current(app), args = await deletionPreparation(app, before);
    expect((await app.act(actor, 'confirm-request-delete-direct', { request: 'R-ONE', ...args })).outcome).toBe('denied');
    unchanged(await current(app), before);
    expect((await app.act('OWNER', 'confirm-request-delete-direct', { request: 'R-ONE', ...args })).outcome).toBe('accepted');
    await deletionEvidence(app, before, args.operationId);
  });
}

for (const kind of ['GET', 'wrong-password', 'no-confirmation']) {
  test(`REQUEST-delete-${kind} | AT-037 AC-037 | mutation needs POST, current confirmation and owner password`, async ({ app }) => {
    await deletionSetup(app); const before = await current(app), prepared = await deletionPreparation(app, before);
    const args = { request: 'R-ONE', ...prepared };
    if (kind === 'wrong-password') args.passwordRef = 'OWNER-WRONG-SYNTHETIC-SECRET';
    if (kind === 'no-confirmation') delete args.confirmation;
    const action = kind === 'GET' ? 'probe-GET-request-delete' : 'confirm-request-delete-direct';
    expect((await app.act('OWNER', action, args)).outcome).toBe('denied'); unchanged(await current(app), before);
    const valid = await deletionPreparation(app, before);
    expect((await app.act('OWNER', 'confirm-request-delete-direct', { request: 'R-ONE', ...valid })).outcome).toBe('accepted');
    await deletionEvidence(app, before, valid.operationId);
  });
}

test('REQUEST-receipt-after-delete | AT-037 AT-114 AC-037 AC-DTL-014 | a previously accepted receipt cannot recreate a deleted request', async ({ app }) => {
  await deletionSetup(app); const before = await current(app);
  const receipt = await app.observe('accepted-request-form-context', { requestId: before.id });
  id(receipt.intentRef); expect(receipt.requestId).toBe(before.id);
  const preRepeatCounts = await app.observe('form-counters');
  for (const key of ['requests', 'consents', 'acceptedGoals', 'telegramMessages']) expect(Number.isSafeInteger(preRepeatCounts[key]) && preRepeatCounts[key] >= 0).toBe(true);
  expect(preRepeatCounts.requests).toBeGreaterThan(0); expect(preRepeatCounts.consents).toBeGreaterThan(0);
  const previousRepeat = await app.act('VISITOR', 'repeat-accepted-form-intent', { intentRef: receipt.intentRef });
  expect(previousRepeat.outcome).toBe('accepted');
  const privateLink = await app.observe('accepted-request-form-context', { requestId: before.id });
  expect(privateLink.intentRef).toBe(receipt.intentRef); expect(privateLink.requestId).toBe(before.id);
  expect(await app.observe('form-counters')).toEqual(preRepeatCounts); unchanged(await current(app), before);
  const prepared = await deletionPreparation(app, before);
  expect((await app.act('OWNER', 'confirm-request-delete-direct', { request: 'R-ONE', ...prepared })).outcome).toBe('accepted');
  await deletionEvidence(app, before, prepared.operationId);
  const counts = await app.observe('form-counters');
  for (const key of ['requests', 'consents', 'acceptedGoals', 'telegramMessages']) expect(Number.isSafeInteger(counts[key]) && counts[key] >= 0).toBe(true);
  const repeated = await app.act('VISITOR', 'repeat-accepted-form-intent', { intentRef: receipt.intentRef });
  expect(['accepted', 'denied']).toContain(repeated.outcome);
  expect(repeated.body).toContain('Эта отправка уже обработана. Новая заявка не создана');
  expect(repeated.body).not.toContain('REQUEST-PRIVATE-CANARY'); expect(repeated.body).not.toContain('NOTE-PRIVATE-CANARY');
  expect(await app.observe('form-counters')).toEqual(counts);
  await deletionEvidence(app, before, prepared.operationId);
});
