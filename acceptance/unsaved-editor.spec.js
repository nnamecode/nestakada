import { randomUUID } from 'node:crypto';
import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await use(app); } finally { await app.close(); }
} });
const unchangedFields = ['id', 'url', 'parentId', 'published', 'h1', 'title', 'description',
  'assetId', 'price', 'publicText', 'draftText', 'revision', 'versions', 'currentVersionId', 'grants'];
function unchanged(after, before) {
  for (const key of unchangedFields) {
    expect(before).toHaveProperty(key); expect(after).toHaveProperty(key); expect(after[key], key).toEqual(before[key]);
  }
}
async function retained(app, text, canary = text) {
  expect(await app.observe('open-editor-input', { actor: 'S-EDIT', page: 'P-ASSIGNED' })).toBe(text);
  expect(await app.observe('editor-memory-state', { actor: 'S-EDIT', canary })).toEqual({
    source: 'actual-actor-browser', urlContainsCanary: false,
    localStorageContainsCanary: false, sessionStorageContainsCanary: false,
  });
}
async function type(app, text) {
  expect((await app.act('S-EDIT', 'type-unsaved-text', { page: 'P-ASSIGNED', text })).outcome).toBe('ui-observed');
  await retained(app, text);
}

test('UNSAVED-118-validation | AT-118 AC-DTL-018 | rejected editor input stays in the tab and a corrected explicit save succeeds', async ({ app }) => {
  await app.reset('page-history-restore');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  const canary = `UNSAVED-${randomUUID()}`;
  const invalid = `${canary} {{ request.user }}`;
  await type(app, invalid);
  unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before);
  expect((await app.act('S-EDIT', 'save-open-editor', { page: 'P-ASSIGNED', base: before.revision })).outcome).toBe('denied');
  unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before);
  await retained(app, invalid, canary);
  await type(app, canary);
  expect((await app.act('S-EDIT', 'save-open-editor', { page: 'P-ASSIGNED', base: before.revision })).outcome).toBe('accepted');
  const after = await app.observe('page', { page: 'P-ASSIGNED' });
  expect(after.publicText).toBe(canary); expect(after.versions).toHaveLength(before.versions.length + 1);
});

test('UNSAVED-118-conflict | AT-118 AT-017 AC-DTL-018 AC-017 | stale save retains own input and never merges it into the newer page', async ({ app }) => {
  await app.reset('page-history-restore');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  const text = `UNSAVED-${randomUUID()}`;
  await type(app, text);
  expect((await app.act('OWNER', 'save-text', { page: 'P-ASSIGNED', base: before.revision, text: 'Сохранённая новая редакция владельца' })).outcome).toBe('accepted');
  const current = await app.observe('page', { page: 'P-ASSIGNED' });
  expect((await app.act('S-EDIT', 'save-open-editor', { page: 'P-ASSIGNED', base: before.revision })).outcome).toBe('conflict');
  unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), current);
  await retained(app, text);
});

for (const kind of ['idle', 'absolute']) {
  for (const situation of ['same-user', 'revoked-grant', 'stale-revision', 'other-user']) {
    test(`UNSAVED-015-${kind}-${situation} | AT-015 AT-118 AC-015 AC-DTL-018 | expired access requires login, current permission and explicit save`, async ({ app }) => {
      await app.reset('controlled-session-boundary', { kind, ageSeconds: kind === 'idle' ? 1801 : 43201 });
      const text = 'Несохранённый допустимый ввод';
      await retained(app, text);
      const before = await app.observe('page', { page: 'P-ASSIGNED' });
      const expired = await app.act('S-EDIT', 'read-assigned-page-direct', { page: 'P-ASSIGNED' });
      expect(expired.outcome).toBe('denied'); expect(expired.body).not.toContain('ASSIGNED-PRIVATE-CANARY');
      unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before);
      await retained(app, text);
      if (situation === 'revoked-grant') {
        expect((await app.act('OWNER', 'revoke-page-grant', { page: 'P-ASSIGNED', employee: 'S-EDIT' })).outcome).toBe('accepted');
      } else if (situation === 'stale-revision') {
        expect((await app.act('OWNER', 'save-text', { page: 'P-ASSIGNED', base: before.revision, text: 'Новая редакция до повторного входа' })).outcome).toBe('accepted');
      }
      const current = await app.observe('page', { page: 'P-ASSIGNED' });
      expect((await app.act('S-EDIT', 'reauthenticate-open-editor', {
        credentialActor: situation === 'other-user' ? 'S-OTHER' : 'S-EDIT',
      })).outcome).toBe('accepted');
      const identities = await app.observe('fixture-identifiers');
      const identity = await app.act('S-EDIT', 'read-current-identity-direct');
      expect(identity.outcome).toBe('accepted');
      const expectedUser = situation === 'other-user' ? identities.otherUserId : identities.editUserId;
      expect(typeof expectedUser).toBe('string'); expect(expectedUser.length).toBeGreaterThan(0); expect(identity.userId).toBe(expectedUser);
      unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), current);
      if (situation !== 'other-user') await retained(app, text);
      const deniedAccess = situation === 'other-user' || situation === 'revoked-grant';
      if (deniedAccess) {
        const read = await app.act('S-EDIT', 'read-assigned-page-direct', { page: 'P-ASSIGNED' });
        expect(read.outcome).toBe('denied'); expect(read.body).not.toContain('ASSIGNED-PRIVATE-CANARY');
        const payload = { page: 'P-ASSIGNED', base: before.revision, text };
        expect((await app.act('S-EDIT', 'save-text', payload)).outcome).toBe('denied');
        unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), current);
        // Explicit new owner grant is a positive control, never an automatic consequence of login.
        expect((await app.act('OWNER', 'grant-page-grant', {
          page: 'P-ASSIGNED', employee: situation === 'other-user' ? 'S-OTHER' : 'S-EDIT',
        })).outcome).toBe('accepted');
        expect((await app.act('S-EDIT', 'save-text', payload)).outcome).toBe('accepted');
        expect((await app.observe('page', { page: 'P-ASSIGNED' })).publicText).toBe(text);
      } else {
        const read = await app.act('S-EDIT', 'read-assigned-page-direct', { page: 'P-ASSIGNED' });
        expect(read.outcome).toBe('accepted');
        if (situation === 'same-user') expect(read.body).toContain('ASSIGNED-PRIVATE-CANARY');
        const result = await app.act('S-EDIT', 'save-open-editor', { page: 'P-ASSIGNED', base: before.revision });
        expect(result.outcome).toBe(situation === 'stale-revision' ? 'conflict' : 'accepted');
        const after = await app.observe('page', { page: 'P-ASSIGNED' });
        if (situation === 'stale-revision') { unchanged(after, current); await retained(app, text); }
        else { expect(after.publicText).toBe(text); expect(after.versions).toHaveLength(current.versions.length + 1); }
      }
    });
  }
}
