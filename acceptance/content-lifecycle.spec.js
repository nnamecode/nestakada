import { randomUUID } from 'node:crypto';
import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({
  app: async ({}, use) => {
    const app = await openApplicationDriver();
    try { await use(app); } finally { await app.close(); }
  },
});

const protectedPage = ['url', 'parentId', 'position', 'published', 'h1', 'title', 'description', 'assetId', 'grants', 'stableIds', 'headerRevision', 'footerRevision'];
function unchanged(after, before, fields) {
  for (const field of fields) {
    expect(before, `fixture must expose ${field}`).toHaveProperty(field);
    expect(after).toHaveProperty(field);
    expect(after[field], field).toEqual(before[field]);
  }
}

test('LIFE-003 | AT-003 AC-003 | hiding parent preserves published child and regrouping on return', async ({ app }) => {
  await app.reset('tree-parent-published-child');
  const parent = await app.observe('page', { page: 'P-PARENT' });
  const child = await app.observe('page', { page: 'P-CHILD' });
  expect(parent.published).toBe(true);
  expect(child.published).toBe(true);
  expect((await app.act('OWNER', 'set-page-publication', { page: 'P-PARENT', base: parent.revision, published: false })).outcome).toBe('accepted');
  const hidden = await app.observe('public-page-response', { page: 'P-PARENT' });
  expect(hidden.status).toBe(200);
  expect(hidden.body.trim()).toBe('');
  const publicChild = await app.observe('public-page-response', { page: 'P-CHILD' });
  expect(publicChild.status).toBe(200);
  expect(publicChild.body).toContain('CHILD-PUBLIC-CANARY');
  unchanged(await app.observe('page', { page: 'P-CHILD' }), child, ['url', 'parentId', 'published', 'revision']);
  const currentParent = await app.observe('page', { page: 'P-PARENT' });
  expect((await app.act('OWNER', 'set-page-publication', { page: 'P-PARENT', base: currentParent.revision, published: true })).outcome).toBe('accepted');
  const nav = await app.observe('public-navigation');
  expect(nav.groups.find(group => group.pageId === parent.id).childIds).toContain(child.id);
});

test('LIFE-004-append | AT-004 AC-004 | newly published sibling appends instead of alphabetic reorder', async ({ app }) => {
  await app.reset('tree-two-published-siblings');
  const before = await app.observe('public-navigation');
  const created = await app.act('OWNER', 'create-page', { parent: 'P-PARENT', name: 'А новая тестовая', requestedPath: '/acceptance/new-a/' });
  expect(created.outcome).toBe('accepted');
  expect(created.pageId).toBeTruthy();
  expect((await app.act('OWNER', 'publish-created-page', { pageId: created.pageId })).outcome).toBe('accepted');
  const after = await app.observe('public-navigation');
  const oldIds = before.groups.find(group => group.alias === 'P-PARENT').childIds;
  expect(after.groups.find(group => group.alias === 'P-PARENT').childIds).toEqual([...oldIds, created.pageId]);
});

test('LIFE-004-rename-order | AT-004 AC-004 | rename keeps public order; explicit reorder changes it', async ({ app }) => {
  await app.reset('tree-two-published-siblings');
  const before = await app.observe('public-navigation');
  const sibling = await app.observe('page', { page: 'P-CHILD' });
  expect((await app.act('OWNER', 'rename-page', { page: 'P-CHILD', base: sibling.revision, name: 'Я переименованная тестовая' })).outcome).toBe('accepted');
  expect((await app.observe('public-navigation')).groups.map(group => group.childIds)).toEqual(before.groups.map(group => group.childIds));
  const ids = before.groups.find(group => group.alias === 'P-PARENT').childIds;
  expect(ids).toHaveLength(2);
  expect((await app.act('OWNER', 'reorder-page-siblings', { parent: 'P-PARENT', pageIds: [...ids].reverse() })).outcome).toBe('accepted');
  expect((await app.observe('public-navigation')).groups.find(group => group.alias === 'P-PARENT').childIds).toEqual([...ids].reverse());
});

test('LIFE-005-hidden-child | AT-005 AC-005 | hidden child still blocks parent deletion preparation', async ({ app }) => {
  await app.reset('tree-parent-hidden-child-and-empty-parent');
  const before = await app.observe('tree');
  const allowed = await app.act('OWNER', 'prepare-delete-page', { page: 'P-EMPTY' });
  expect(allowed.outcome).toBe('accepted');
  expect(allowed.confirmation.pageId).toBeTruthy();
  expect((await app.act('OWNER', 'prepare-delete-page', { page: 'P-PARENT' })).outcome).toBe('denied');
  expect(await app.observe('tree')).toEqual(before);
});

test('LIFE-005-new-child | AT-005 AC-005 | concurrent child invalidates prepared deletion before mutation', async ({ app }) => {
  await app.reset('empty-page-delete-confirmation');
  const prepared = await app.act('OWNER', 'prepare-delete-page', { page: 'P-EMPTY' });
  expect(prepared.outcome).toBe('accepted');
  expect((await app.act('OWNER', 'create-page', { parent: 'P-EMPTY', name: 'Новый ребёнок', requestedPath: '/acceptance/late-child/' })).outcome).toBe('accepted');
  const before = await app.observe('tree');
  const attempt = await app.act('OWNER', 'submit-stale-page-delete', { page: 'P-EMPTY', confirmation: prepared.confirmation, passwordRef: 'OWNER-CURRENT-SECRET' });
  expect(attempt.outcome).toBe('conflict');
  expect(await app.observe('tree')).toEqual(before);
});

for (const occupiedBy of ['page', 'redirect']) {
  test(`LIFE-006-collision-${occupiedBy} | AT-006 AC-006 | occupied URL fails visibly without silent suffix`, async ({ app }) => {
    await app.reset('page-url-collision', { occupiedBy });
    const fixture = await app.observe('fixture-identifiers');
    const before = await app.observe('tree');
    const rejected = await app.act('OWNER', 'create-page', { parent: 'P-PARENT', name: 'Допустимое имя', requestedPath: fixture.occupiedPath });
    expect(rejected.outcome).toBe('denied');
    expect(rejected.fieldErrors).toContain('url');
    expect(await app.observe('tree')).toEqual(before);
    const allowed = await app.act('OWNER', 'create-page', { parent: 'P-PARENT', name: 'Допустимое имя', requestedPath: '/acceptance/free-path/' });
    expect(allowed.outcome).toBe('accepted');
    expect((await app.observe('page-by-id', { id: allowed.pageId })).url).toBe('/acceptance/free-path/');
  });
}

test('LIFE-006-rename-move | AT-006 AC-006 | saved URL survives rename and parent move', async ({ app }) => {
  await app.reset('tree-parent-published-child');
  const before = await app.observe('page', { page: 'P-CHILD' });
  expect((await app.act('OWNER', 'rename-page', { page: 'P-CHILD', base: before.revision, name: 'Новое имя' })).outcome).toBe('accepted');
  const renamed = await app.observe('page', { page: 'P-CHILD' });
  expect(renamed.url).toBe(before.url);
  expect((await app.act('OWNER', 'move-page', { page: 'P-CHILD', base: renamed.revision, parent: 'P-OTHER-PARENT' })).outcome).toBe('accepted');
  expect((await app.observe('page', { page: 'P-CHILD' })).url).toBe(before.url);
});

test('LIFE-014-reset | AT-014 AC-014 | owner password reset invalidates old employee session', async ({ app }) => {
  await app.reset('employee-active-old-session');
  expect((await app.act('S-EDIT', 'read-assigned-page-direct', { page: 'P-ASSIGNED', session: 'OLD' })).outcome).toBe('accepted');
  expect((await app.act('OWNER', 'reset-employee-password', { employee: 'S-EDIT', newPasswordRef: 'NEW-SYNTHETIC-SECRET' })).outcome).toBe('accepted');
  const after = await app.act('S-EDIT', 'read-assigned-page-direct', { page: 'P-ASSIGNED', session: 'OLD' });
  expect(after.outcome).toBe('denied');
  expect(after.body).not.toContain('ASSIGNED-PRIVATE-CANARY');
  expect((await app.act('S-EDIT', 'login-with-password-ref', { passwordRef: 'NEW-SYNTHETIC-SECRET' })).outcome).toBe('accepted');
});

for (const action of ['change-own-password-direct', 'recover-own-password-direct']) {
  test(`LIFE-014-${action} | AT-014 AC-014 | employee has no self-service password mutation`, async ({ app }) => {
    await app.reset('employee-active-old-session');
    const before = await app.observe('employee-auth-state', { employee: 'S-EDIT' });
    expect((await app.act('S-EDIT', action, { passwordRef: 'NEW-SYNTHETIC-SECRET' })).outcome).toBe('denied');
    unchanged(await app.observe('employee-auth-state', { employee: 'S-EDIT' }), before, ['credentialRevision', 'sessionGeneration']);
    expect((await app.act('OWNER', 'reset-employee-password', { employee: 'S-EDIT', newPasswordRef: 'NEW-SYNTHETIC-SECRET' })).outcome).toBe('accepted');
    expect((await app.observe('employee-auth-state', { employee: 'S-EDIT' })).credentialRevision).not.toBe(before.credentialRevision);
  });
}

for (const [kind, ageSeconds, accepted] of [['idle', 1799, true], ['idle', 1801, false], ['absolute', 43199, true], ['absolute', 43201, false]]) {
  test(`LIFE-015-${kind}-${ageSeconds} | AT-015 AC-015 | controlled session boundary`, async ({ app }) => {
    await app.reset('controlled-session-boundary', { kind, ageSeconds });
    const input = 'Несохранённый допустимый ввод';
    expect(await app.observe('open-editor-input', { actor: 'S-EDIT', page: 'P-ASSIGNED' })).toBe(input);
    const before = await app.observe('page', { page: 'P-ASSIGNED' });
    const result = await app.act('S-EDIT', 'read-assigned-page-direct', { page: 'P-ASSIGNED' });
    expect(result.outcome).toBe(accepted ? 'accepted' : 'denied');
    if (accepted) expect(result.body).toContain('ASSIGNED-PRIVATE-CANARY');
    else expect(result.body).not.toContain('ASSIGNED-PRIVATE-CANARY');
    expect(await app.observe('open-editor-input', { actor: 'S-EDIT', page: 'P-ASSIGNED' })).toBe(input);
    unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before, ['publicText', 'revision', 'versions']);
  });
}

test('LIFE-022-preview | AT-022 AC-022 | preview and comparison do not mutate page or editor', async ({ app }) => {
  await app.reset('page-history-restore');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  const input = await app.observe('open-editor-input', { actor: 'S-EDIT', page: 'P-ASSIGNED' });
  const result = await app.act('S-EDIT', 'compare-page-version', { page: 'P-ASSIGNED', version: 'V-OLD' });
  expect(result.outcome).toBe('accepted');
  expect(result.comparison.proposedText).toBe('HISTORICAL-ALLOWED-TEXT');
  unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before, [...protectedPage, 'revision', 'publicText', 'versions']);
  expect(await app.observe('open-editor-input', { actor: 'S-EDIT', page: 'P-ASSIGNED' })).toBe(input);
});

test('LIFE-022-explicit-save | AT-022 AC-022 | staging old allowed text needs explicit save and preserves protected state', async ({ app }) => {
  await app.reset('page-history-restore');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  const prepared = await app.act('S-EDIT', 'prepare-page-version-restore', { page: 'P-ASSIGNED', version: 'V-OLD' });
  expect(prepared.outcome).toBe('accepted');
  expect(prepared.requiresInputReplacementConfirmation).toBe(true);
  expect((await app.act('S-EDIT', 'stage-page-version-restore', { page: 'P-ASSIGNED', preparation: prepared.preparation, confirmInputReplacement: true })).outcome).toBe('ui-observed');
  unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before, [...protectedPage, 'revision', 'publicText', 'versions']);
  expect(await app.observe('open-editor-input', { actor: 'S-EDIT', page: 'P-ASSIGNED' })).toBe('HISTORICAL-ALLOWED-TEXT');
  expect((await app.act('S-EDIT', 'save-open-editor', { page: 'P-ASSIGNED', base: before.revision })).outcome).toBe('accepted');
  const after = await app.observe('page', { page: 'P-ASSIGNED' });
  expect(after.publicText).toBe('HISTORICAL-ALLOWED-TEXT');
  expect(after.versions).toHaveLength(before.versions.length + 1);
  unchanged(after, before, protectedPage);
});

for (const reason of ['incompatible-snapshot', 'revoked-grant']) {
  test(`LIFE-023-${reason} | AT-023 AC-023 | invalid restore is all-or-nothing`, async ({ app }) => {
    await app.reset('page-history-restore');
    expect((await app.act('S-EDIT', 'compare-page-version', { page: 'P-ASSIGNED', version: 'V-OLD' })).outcome).toBe('accepted');
    if (reason === 'revoked-grant') expect((await app.act('OWNER', 'revoke-page-grant', { page: 'P-ASSIGNED', employee: 'S-EDIT' })).outcome).toBe('accepted');
    const before = await app.observe('page', { page: 'P-ASSIGNED' });
    const input = await app.observe('open-editor-input', { actor: 'S-EDIT', page: 'P-ASSIGNED' });
    const result = await app.act('S-EDIT', 'prepare-page-version-restore', { page: 'P-ASSIGNED', version: reason === 'incompatible-snapshot' ? 'V-INCOMPATIBLE' : 'V-OLD' });
    expect(result.outcome).toBe('denied');
    expect(result.safeReasons.length).toBeGreaterThan(0);
    unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before, [...protectedPage, 'revision', 'publicText', 'versions']);
    expect(await app.observe('open-editor-input', { actor: 'S-EDIT', page: 'P-ASSIGNED' })).toBe(input);
  });
}

test('LIFE-024-confirmation | AT-024 AC-024 | owner sees exact page and history composition before deletion', async ({ app }) => {
  await app.reset('empty-page-delete-confirmation');
  const before = await app.observe('page', { page: 'P-EMPTY' });
  const result = await app.act('OWNER', 'prepare-delete-page', { page: 'P-EMPTY' });
  expect(result.outcome).toBe('accepted');
  expect(result.confirmation).toMatchObject({ pageId: before.id, url: before.url, name: before.name, requiresOwnerPassword: true });
  expect([...result.confirmation.versionIds].sort()).toEqual(before.versions.map(version => version.id).sort());
  expect([...result.confirmation.stableIds].sort()).toEqual(before.versions.filter(version => version.isStable).map(version => version.id).sort());
  unchanged(await app.observe('page', { page: 'P-EMPTY' }), before, ['revision', 'versions', 'publicText', 'url']);
});

test('LIFE-024-stale-history | AT-024 AC-024 | additional history requires a fresh deletion confirmation', async ({ app }) => {
  await app.reset('empty-page-delete-confirmation');
  const prepared = await app.act('OWNER', 'prepare-delete-page', { page: 'P-EMPTY' });
  expect(prepared.outcome).toBe('accepted');
  expect((await app.act('OWNER', 'create-named-version', { page: 'P-EMPTY', name: 'Поздняя контрольная' })).outcome).toBe('accepted');
  const before = await app.observe('page', { page: 'P-EMPTY' });
  expect((await app.act('OWNER', 'submit-stale-page-delete', { page: 'P-EMPTY', confirmation: prepared.confirmation, passwordRef: 'OWNER-CURRENT-SECRET' })).outcome).toBe('conflict');
  unchanged(await app.observe('page', { page: 'P-EMPTY' }), before, ['id', 'revision', 'versions', 'publicText', 'url']);
});

for (const reenable of [false, true]) {
  test(`LIFE-036-${reenable ? 'reenable' : 'disable'} | AT-036 AC-036 | disable revokes open access and transfers only open requests`, async ({ app }) => {
    await app.reset('employee-assigned-open-and-closed-requests');
    expect((await app.act('S-EDIT', 'view-request-direct', { request: 'R-OPEN' })).outcome).toBe('accepted');
    const beforeOpen = await app.observe('request', { request: 'R-OPEN' });
    const beforeClosed = await app.observe('request', { request: 'R-CLOSED' });
    expect((await app.act('OWNER', 'disable-employee', { employee: 'S-EDIT' })).outcome).toBe('accepted');
    const denied = await app.act('S-EDIT', 'view-request-direct', { request: 'R-OPEN' });
    expect(denied.outcome).toBe('denied');
    expect(denied.body).not.toContain('REQUEST-PRIVATE-CANARY');
    const afterOpen = await app.observe('request', { request: 'R-OPEN' });
    const afterClosed = await app.observe('request', { request: 'R-CLOSED' });
    expect(afterOpen.assignee).toBe('OWNER');
    unchanged(afterOpen, beforeOpen, ['id', 'status', 'createdAt', 'original']);
    expect(afterOpen.history.slice(0, beforeOpen.history.length)).toEqual(beforeOpen.history);
    expect(afterOpen.history.length).toBeGreaterThan(beforeOpen.history.length);
    unchanged(afterClosed, beforeClosed, ['assignee', 'status', 'original', 'history']);
    if (reenable) {
      expect((await app.act('OWNER', 'enable-employee', { employee: 'S-EDIT' })).outcome).toBe('accepted');
      expect((await app.observe('request', { request: 'R-OPEN' })).assignee).toBe('OWNER');
      expect((await app.act('S-EDIT', 'view-request-direct', { request: 'R-OPEN' })).outcome).toBe('denied');
    }
  });
}

for (const version of ['V-CURRENT', 'V-STABLE', 'V-USED-BASE']) {
  test(`LIFE-MAN-002-${version} | AT-063 AT-702 AC-063 AC-MAN-002 | protected version cannot be removed`, async ({ app }) => {
    await app.reset('manual-version-delete-matrix');
    const before = await app.observe('page', { page: 'P-ASSIGNED' });
    const allowed = await app.act('OWNER', 'prepare-delete-version', { page: 'P-ASSIGNED', version: 'V-ELIGIBLE' });
    expect(allowed.outcome).toBe('accepted');
    expect((await app.act('OWNER', 'prepare-delete-version', { page: 'P-ASSIGNED', version })).outcome).toBe('denied');
    unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before, ['versions', 'revision', 'publicText', 'currentVersionId']);
    expect(await app.observe('shared-asset-state')).toMatchObject({ exists: true });
  });
}

test('LIFE-MAN-002-delete-eligible | AT-063 AT-702 AC-063 AC-MAN-002 | only confirmed ordinary version is removed, shared asset kept', async ({ app }) => {
  await app.reset('manual-version-delete-matrix');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  const prepared = await app.act('OWNER', 'prepare-delete-version', { page: 'P-ASSIGNED', version: 'V-ELIGIBLE' });
  expect(prepared.outcome).toBe('accepted');
  const removedId = prepared.confirmation.versionId;
  expect(before.versions.some(version => version.id === removedId)).toBe(true);
  expect((await app.act('OWNER', 'delete-version-direct', { page: 'P-ASSIGNED', version: 'V-ELIGIBLE', confirmation: prepared.confirmation })).outcome).toBe('accepted');
  const after = await app.observe('page', { page: 'P-ASSIGNED' });
  expect(after.versions).toEqual(before.versions.filter(version => version.id !== removedId));
  unchanged(after, before, ['revision', 'publicText', 'currentVersionId']);
  expect(await app.observe('shared-asset-state')).toMatchObject({ exists: true });
});

test('LIFE-MAN-002-stable-after-prepare | AT-702 AC-MAN-002 | new Stable protection wins over old delete confirmation', async ({ app }) => {
  await app.reset('manual-version-delete-matrix');
  const prepared = await app.act('OWNER', 'prepare-delete-version', { page: 'P-ASSIGNED', version: 'V-ELIGIBLE' });
  expect(prepared.outcome).toBe('accepted');
  expect((await app.act('OWNER', 'assign-stable', { page: 'P-ASSIGNED', version: 'V-ELIGIBLE' })).outcome).toBe('accepted');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  expect((await app.act('OWNER', 'delete-version-direct', { page: 'P-ASSIGNED', version: 'V-ELIGIBLE', confirmation: prepared.confirmation })).outcome).toBe('denied');
  unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before, ['versions', 'revision', 'publicText']);
});

test('LIFE-MAN-003-repeat | AT-703 AC-MAN-003 | repeated named-version operation returns same result', async ({ app }) => {
  await app.reset('assigned-page-with-owner-draft');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  const args = { page: 'P-ASSIGNED', name: 'Контрольная', operationId: randomUUID() };
  const first = await app.act('OWNER', 'create-named-version', args);
  const repeated = await app.act('OWNER', 'create-named-version', args);
  expect(first.outcome).toBe('accepted');
  expect(first.versionId).toBeTruthy();
  expect(repeated.outcome).toBe('accepted');
  expect(repeated.versionId).toBe(first.versionId);
  const after = await app.observe('page', { page: 'P-ASSIGNED' });
  expect(after.versions).toHaveLength(before.versions.length + 1);
  unchanged(after, before, ['publicText', 'revision', 'draftText']);
});

for (const action of ['create-named-version', 'delete-version-direct']) {
  test(`LIFE-MAN-003-employee-${action} | AT-703 AC-MAN-003 | valid operation remains owner-only`, async ({ app }) => {
    await app.reset('manual-version-delete-matrix');
    const args = { page: 'P-ASSIGNED', version: 'V-ELIGIBLE', name: 'Контрольная', operationId: randomUUID() };
    if (action === 'delete-version-direct') {
      const prepared = await app.act('OWNER', 'prepare-delete-version', args);
      expect(prepared.outcome).toBe('accepted');
      args.confirmation = prepared.confirmation;
    }
    const before = await app.observe('page', { page: 'P-ASSIGNED' });
    expect((await app.act('S-EDIT', action, args)).outcome).toBe('denied');
    unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before, ['versions', 'revision', 'publicText']);
    expect((await app.act('OWNER', action, args)).outcome).toBe('accepted');
  });
}

for (const action of ['create-named-version', 'delete-version-direct']) {
  test(`LIFE-MAN-003-GET-${action} | AT-703 AC-MAN-003 | GET cannot mutate named versions`, async ({ app }) => {
    await app.reset('manual-version-delete-matrix');
    const args = { page: 'P-ASSIGNED', version: 'V-ELIGIBLE', name: 'Контрольная', operationId: randomUUID() };
    if (action === 'delete-version-direct') {
      const prepared = await app.act('OWNER', 'prepare-delete-version', args);
      expect(prepared.outcome).toBe('accepted');
      args.confirmation = prepared.confirmation;
    }
    const before = await app.observe('page', { page: 'P-ASSIGNED' });
    expect((await app.act('OWNER', 'probe-GET-version-mutation', { action, arguments: args })).outcome).toBe('denied');
    unchanged(await app.observe('page', { page: 'P-ASSIGNED' }), before, ['versions', 'revision', 'publicText']);
    expect((await app.act('OWNER', action, args)).outcome).toBe('accepted');
  });
}
