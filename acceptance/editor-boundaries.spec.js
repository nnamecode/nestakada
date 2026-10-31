import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({
  app: async ({}, use) => {
    const app = await openApplicationDriver();
    try { await use(app); } finally { await app.close(); }
  },
});
const unchangedFields = ['id', 'url', 'parentId', 'published', 'h1', 'title', 'description',
  'assetId', 'price', 'publicText', 'draftText', 'revision', 'versions', 'currentVersionId'];
function unchanged(after, before, fields = unchangedFields) {
  for (const field of fields) {
    expect(before).toHaveProperty(field); expect(after).toHaveProperty(field);
    expect(after[field], field).toEqual(before[field]);
  }
}

for (const [field, limit] of [['h1', 255], ['title', 255], ['description', 1000]]) {
  for (const size of [limit - 1, limit, limit + 1]) {
    test(`EDIT-103-${field}-${size} | AT-103 AC-DTL-003 | direct owner input is stored whole or refused whole`, async ({ app }) => {
      await app.reset('assigned-page-with-owner-draft');
      const before = await app.observe('page', { page: 'P-ASSIGNED' });
      const value = 'Я'.repeat(size);
      const payload = { page: 'P-ASSIGNED', base: before.revision, text: before.publicText, extra: { [field]: value } };
      const result = await app.act('OWNER', 'submit-page-direct', payload);
      if (size > limit) {
        expect(result.outcome).toBe('denied'); expect(result.fieldErrors).toContain(field);
        unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before);
        // A valid boundary value on the same operation proves this is not just an unavailable handler.
        payload.extra[field] = 'Я'.repeat(limit);
        expect((await app.act('OWNER', 'submit-page-direct', payload)).outcome).toBe('accepted');
        expect((await app.observe('page', { page: 'P-ASSIGNED' }))[field]).toBe(payload.extra[field]);
      } else {
        expect(result.outcome).toBe('accepted');
        const after = await app.observe('page', { page: 'P-ASSIGNED' });
        expect(after[field]).toBe(value);
        unchanged(after, before, ['id', 'url', 'parentId', 'published', 'assetId', 'price']);
      }
    });
  }
}

test('EDIT-103-empty-description | AT-103 AC-DTL-003 | empty description is saved without generated replacement', async ({ app }) => {
  await app.reset('assigned-page-with-owner-draft');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  expect(typeof before.description).toBe('string'); expect(before.description.length).toBeGreaterThan(0);
  expect((await app.act('OWNER', 'submit-page-direct', {
    page: 'P-ASSIGNED', base: before.revision, text: before.publicText, extra: { description: '' },
  })).outcome).toBe('accepted');
  expect((await app.observe('page', { page: 'P-ASSIGNED' })).description).toBe('');
});

for (const actor of ['OWNER', 'S-EDIT']) {
  test(`EDIT-103-body-${actor} | AT-103 AC-DTL-003 | text edit preserves independently saved SEO`, async ({ app }) => {
    await app.reset('assigned-page-with-owner-draft');
    const before = await app.observe('page', { page: 'P-ASSIGNED' });
    const text = `Отдельная правка текста ${actor}`;
    expect((await app.act(actor, 'save-text', { page: 'P-ASSIGNED', base: before.revision, text })).outcome).toBe('accepted');
    const after = await app.observe('page', { page: 'P-ASSIGNED' });
    expect(after.publicText).toBe(text);
    unchanged(after, before, ['h1', 'title', 'description', 'url']);
  });
}

for (const reason of ['stale-revision', 'revoked-price-grant']) {
  test(`EDIT-101-${reason} | AT-101 AC-DTL-001 | an initially valid price operation is refused after intervening change`, async ({ app }) => {
    await app.reset('assigned-page-with-owner-draft');
    expect((await app.act('OWNER', 'grant-price', { employee: 'S-EDIT', page: 'P-ASSIGNED' })).outcome).toBe('accepted');
    let current = await app.observe('page', { page: 'P-ASSIGNED' });
    // Positive control before revocation/change: this employee and operation can actually update the price.
    expect((await app.act('S-EDIT', 'edit-price', { page: 'P-ASSIGNED', base: current.revision, value: '1500' })).outcome).toBe('accepted');
    current = await app.observe('page', { page: 'P-ASSIGNED' }); expect(current.price).toBe('1500');
    const oldBase = current.revision;
    if (reason === 'stale-revision') {
      expect((await app.act('OWNER', 'save-text', { page: 'P-ASSIGNED', base: oldBase, text: 'Новая редакция владельца' })).outcome).toBe('accepted');
    } else {
      expect((await app.act('OWNER', 'revoke-price', { employee: 'S-EDIT', page: 'P-ASSIGNED' })).outcome).toBe('accepted');
    }
    const before = await app.observe('page', { page: 'P-ASSIGNED' });
    const result = await app.act('S-EDIT', 'edit-price', { page: 'P-ASSIGNED', base: oldBase, value: '1600' });
    expect(result.outcome).toBe(reason === 'stale-revision' ? 'conflict' : 'denied');
    unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before);
    // Owner uses a fresh base on the very same edit operation; the submitted value is valid.
    expect((await app.act('OWNER', 'edit-price', { page: 'P-ASSIGNED', base: before.revision, value: '1600' })).outcome).toBe('accepted');
    expect((await app.observe('page', { page: 'P-ASSIGNED' })).price).toBe('1600');
  });
}
