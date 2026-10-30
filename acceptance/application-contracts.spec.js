import { test as base, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({
  app: async ({}, use) => {
    const app = await openApplicationDriver();
    try { await use(app); } finally { await app.close(); }
  },
});

function unchanged(actual, before, fields) {
  for (const key of fields) {
    expect(before, `fixture must expose ${key}`).toHaveProperty(key);
    expect(actual).toHaveProperty(key);
    expect(actual[key], key).toEqual(before[key]);
  }
}
const protectedPage = ['url', 'parentId', 'published', 'h1', 'title', 'description', 'assetId'];

for (const field of ['title', 'h1', 'description', 'published', 'assetId']) {
  test(`APP-016-${field} | AT-016 AC-016 | employee cannot change protected ${field}`, async ({ app }) => {
    await app.reset('assigned-page-with-owner-draft');
    const before = await app.observe('page', { page: 'P-ASSIGNED' });
    const fixture = await app.observe('fixture-identifiers');
    const value = field === 'published' ? !before.published : field === 'assetId'
      ? fixture.otherAssetId : `Допустимый новый ${field}`;
    if (field === 'assetId') {
      expect(value).toBeTruthy();
      expect(value).not.toBe(before.assetId);
    }
    const payload = { page: 'P-ASSIGNED', base: before.revision, text: 'Разрешённая правка', extra: { [field]: value } };
    const result = await app.act('S-EDIT', 'submit-page-direct', payload);
    expect(result.outcome).toBe('denied');
    unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before,
      [...protectedPage, 'revision', 'publicText', 'draftText', 'versions']);
    // Positive control: exactly this value/payload must be valid for the owner.
    expect((await app.act('OWNER', 'submit-page-direct', payload)).outcome).toBe('accepted');
    expect((await app.observe('page', { page: 'P-ASSIGNED' }))[field]).toBe(value);
  });
}

test('APP-016-main | AT-016 AC-016 | valid main-page text remains owner-only', async ({ app }) => {
  await app.reset('assigned-page-with-owner-draft');
  const before = await app.observe('page', { page: 'P-MAIN' });
  const payload = { page: 'P-MAIN', base: before.revision, text: 'Допустимый текст главной', extra: {} };
  expect((await app.act('S-EDIT', 'submit-page-direct', payload)).outcome).toBe('denied');
  unchanged(await app.observe('page', { page: 'P-MAIN' }), before, [...protectedPage, 'publicText', 'revision', 'versions']);
  expect((await app.act('OWNER', 'submit-page-direct', payload)).outcome).toBe('accepted');
  expect((await app.observe('page', { page: 'P-MAIN' })).publicText).toBe(payload.text);
});

test('APP-016-price | AT-016 AC-016 | price grant off/on is checked at submission', async ({ app }) => {
  await app.reset('assigned-page-with-owner-draft');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  expect((await app.act('S-EDIT', 'edit-price', { page: 'P-ASSIGNED', base: before.revision, value: '1500' })).outcome).toBe('denied');
  unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before, ['price', 'revision', 'versions']);
  await app.act('OWNER', 'grant-price', { employee: 'S-EDIT', page: 'P-ASSIGNED' });
  expect((await app.act('S-EDIT', 'edit-price', { page: 'P-ASSIGNED', base: before.revision, value: '1500' })).outcome).toBe('accepted');
  const after = await app.observe('page', { page: 'P-ASSIGNED' });
  expect(after.price).toBe('1500');
  expect(after.versions).toHaveLength(before.versions.length + 1);
  unchanged(after, before, protectedPage);
});

test('APP-017 | AT-017 AC-017 | stale save conflicts without partial changes', async ({ app }) => {
  await app.reset('assigned-page-with-owner-draft');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  expect((await app.act('S-EDIT', 'save-text', { page: 'P-ASSIGNED', base: before.revision, text: 'Первый текст' })).outcome).toBe('accepted');
  const first = await app.observe('page', { page: 'P-ASSIGNED' });
  const stale = await app.act('OWNER', 'save-text', { page: 'P-ASSIGNED', base: before.revision, text: 'Второй текст' });
  expect(stale.outcome).toBe('conflict');
  expect(stale.retainedInput).toBe('Второй текст');
  expect(stale.comparison.currentText).toBe('Первый текст');
  unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), first, [...protectedPage, 'publicText', 'draftText', 'versions', 'revision']);
});

test('APP-018 | AT-018 AC-018 | employee save creates one revision and keeps owner draft private', async ({ app }) => {
  await app.reset('assigned-page-with-owner-draft');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  const result = await app.act('S-EDIT', 'save-text', { page: 'P-ASSIGNED', base: before.revision, text: 'Новый открытый текст' });
  expect(result.outcome).toBe('accepted');
  const after = await app.observe('page', { page: 'P-ASSIGNED' });
  expect(after.publicText).toBe('Новый открытый текст');
  expect(after.versions).toHaveLength(before.versions.length + 1);
  unchanged(after, before, [...protectedPage, 'draftText']);
  const html = await app.observe('public-page-body', { page: 'P-ASSIGNED' });
  expect(html).toContain('Новый открытый текст');
  expect(html).not.toContain(before.draftText);
});

test('APP-019 | AT-019 AC-019 | ten ordinary plus all Stable after sequential saves', async ({ app }) => {
  await app.reset('two-stable-and-ten-ordinary');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  const stableIds = before.versions.filter(v => v.isStable).map(v => v.id).sort();
  expect(stableIds).toHaveLength(2);
  for (let i = 0; i < 3; i++) {
    const current = await app.observe('page', { page: 'P-ASSIGNED' });
    expect((await app.act('S-EDIT', 'save-text', { page: 'P-ASSIGNED', base: current.revision, text: `Обычная правка ${i}` })).outcome).toBe('accepted');
  }
  const after = await app.observe('page', { page: 'P-ASSIGNED' });
  expect(after.versions.filter(v => !v.isStable)).toHaveLength(10);
  expect(after.versions.filter(v => v.isStable).map(v => v.id).sort()).toEqual(stableIds);
  expect(after.versions.some(v => v.id === after.currentVersionId)).toBe(true);
});

for (const action of ['assign-stable', 'remove-stable']) {
  test(`APP-020-${action} | AT-020 AC-020 | employee cannot change Stable`, async ({ app }) => {
    await app.reset('two-stable-and-ten-ordinary');
    const before = await app.observe('page', { page: 'P-ASSIGNED' });
    const version = before.versions.find(v => v.isStable === (action === 'remove-stable'));
    expect(version).toBeTruthy();
    expect((await app.act('S-EDIT', action, { page: 'P-ASSIGNED', version: version.id })).outcome).toBe('denied');
    unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before, ['versions', 'revision', 'publicText']);
  });
}

for (const actor of ['VISITOR', 'S-OTHER']) {
  test(`APP-021-${actor} | AT-021 AC-021 | guessed history does not disclose version text`, async ({ app }) => {
    await app.reset('assigned-page-with-owner-draft');
    const allowed = await app.act('OWNER', 'read-history-direct', { page: 'P-ASSIGNED' });
    expect(allowed.outcome).toBe('accepted');
    expect(allowed.body).toContain('HISTORY-ONLY-CANARY');
    const response = await app.act(actor, 'read-history-direct', { page: 'P-ASSIGNED' });
    expect(response.outcome).toBe('denied');
    expect(response.body).not.toContain('OWNER-DRAFT-CANARY');
    expect(response.body).not.toContain('HISTORY-ONLY-CANARY');
  });
}

test('APP-MAN-001 | AT-701 AC-MAN-001 | named version copies saved current, not draft or unsaved input', async ({ app }) => {
  await app.reset('assigned-page-with-owner-draft');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  await app.act('OWNER', 'type-unsaved-text', { page: 'P-ASSIGNED', text: 'Несохранённый ввод' });
  const result = await app.act('OWNER', 'create-named-version', { page: 'P-ASSIGNED', name: 'Контрольная', comment: 'Тестовая точка' });
  expect(result.outcome).toBe('accepted');
  const after = await app.observe('page', { page: 'P-ASSIGNED' });
  const created = after.versions.find(v => v.id === result.versionId);
  expect(created).toMatchObject({ text: before.publicText, isStable: false, kind: 'manual' });
  expect(after.versions).toHaveLength(before.versions.length + 1);
  unchanged(after, before, [...protectedPage, 'publicText', 'draftText', 'revision', 'currentVersionId']);
  expect(await app.observe('open-editor-input', { actor: 'OWNER', page: 'P-ASSIGNED' })).toBe('Несохранённый ввод');
});

for (const actor of ['OWNER', 'S-EDIT']) {
  for (const target of ['done', 'cancelled']) {
    test(`APP-034-${actor}-${target} | AT-034 AC-034 | new request can close directly, viewing does not change it`, async ({ app }) => {
      await app.reset('new-request-assigned-to-S-EDIT');
      const before = await app.observe('request', { request: 'R-ONE' });
      expect(before.status).toBe('new');
      expect((await app.act(actor, 'view-request', { request: 'R-ONE' })).outcome).toBe('accepted');
      unchanged(await app.observe('request', { request: 'R-ONE' }), before, ['status', 'createdAt', 'original', 'history']);
      expect((await app.act(actor, 'change-request-status', { request: 'R-ONE', base: before.revision, target, operationId: randomUUID() })).outcome).toBe('accepted');
      const after = await app.observe('request', { request: 'R-ONE' });
      expect(after.status).toBe(target);
      expect(after.history).toHaveLength(before.history.length + 1);
      expect(after.history.at(-1)).toMatchObject({ actor, from: 'new', to: target });
      unchanged(after, before, ['id', 'createdAt', 'original']);
    });
  }
}

for (const [from, target] of [['in_progress', 'new'], ['done', 'new'], ['cancelled', 'new'], ['done', 'cancelled'], ['cancelled', 'done']]) {
  test(`APP-DTL-013-${from}-${target} | AT-113 AC-DTL-013 | forbidden transition does not mutate request`, async ({ app }) => {
    await app.reset('request-status-matrix', { status: from });
    const before = await app.observe('request', { request: 'R-ONE' });
    expect(before.status).toBe(from);
    expect((await app.act('OWNER', 'change-request-status', { request: 'R-ONE', base: before.revision, target, operationId: randomUUID() })).outcome).toBe('denied');
    unchanged(await app.observe('request', { request: 'R-ONE' }), before, ['status', 'revision', 'history', 'original', 'createdAt']);
  });
}

for (const actor of ['VISITOR', 'S-OTHER']) {
  test(`APP-033-${actor} | AT-033 AC-033 | non-assignee cannot read request or notes directly`, async ({ app }) => {
    await app.reset('new-request-assigned-to-S-EDIT');
    for (const action of ['view-request-direct', 'view-request-notes-direct']) {
      const allowed = await app.act('OWNER', action, { request: 'R-ONE' });
      expect(allowed.outcome).toBe('accepted');
      expect(allowed.body).toContain(action === 'view-request-direct' ? 'REQUEST-PRIVATE-CANARY' : 'NOTE-PRIVATE-CANARY');
      const response = await app.act(actor, action, { request: 'R-ONE' });
      expect(response.outcome).toBe('denied');
      expect(response.body).not.toContain('REQUEST-PRIVATE-CANARY');
      expect(response.body).not.toContain('NOTE-PRIVATE-CANARY');
    }
  });
}

test('APP-035 | AT-035 AC-035 | contact correction is append-only note, not original rewrite', async ({ app }) => {
  await app.reset('new-request-assigned-to-S-EDIT');
  const before = await app.observe('request', { request: 'R-ONE' });
  expect((await app.act('S-EDIT', 'add-request-note', { request: 'R-ONE', base: before.revision, text: 'Уточнение контакта: тестовые данные' })).outcome).toBe('accepted');
  const first = await app.observe('request', { request: 'R-ONE' });
  expect(first.notes).toHaveLength(before.notes.length + 1);
  expect(first.notes.at(-1)).toMatchObject({ actor: 'S-EDIT', text: 'Уточнение контакта: тестовые данные' });
  expect(first.notes.at(-1).createdAt).toBeTruthy();
  expect((await app.act('S-EDIT', 'add-request-note', { request: 'R-ONE', base: first.revision, text: 'Исправление предыдущего уточнения' })).outcome).toBe('accepted');
  const second = await app.observe('request', { request: 'R-ONE' });
  expect(second.notes).toHaveLength(first.notes.length + 1);
  expect(second.notes.slice(0, first.notes.length)).toEqual(first.notes);
  unchanged(second, before, ['id', 'createdAt', 'original']);
});
