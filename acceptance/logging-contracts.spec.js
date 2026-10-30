import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await use(app); } finally { await app.close(); }
} });
const categories = ['access', 'security', 'user_actions', 'site_errors', 'pages_links',
  'updates_environment', 'backup_maintenance', 'performance_external', 'other_service'];
const identifier = value => expect(typeof value === 'string' && value.length > 0).toBe(true);
function integer(value) { expect(Number.isSafeInteger(value) && value >= 0).toBe(true); return value; }
function ids(value) {
  expect(Array.isArray(value)).toBe(true); value.forEach(identifier);
  expect(new Set(value).size).toBe(value.length); return [...value].sort();
}
function logState(value) {
  identifier(value.category); identifier(value.readBoundary); identifier(value.notificationCycleId);
  ids(value.visibleEventIds); ids(value.fileEventIds); ids(value.activeCriticalIds);
  integer(value.unreadCount); integer(value.physicalBytes);
  expect(typeof value.notificationCycleOpen).toBe('boolean');
  return value;
}
async function categoryState(app, category = 'user_actions') {
  const actual = logState(await app.observe('log-category-state', { category }));
  expect(actual.category).toBe(category);
  if (category === 'site_errors') {
    const fixture = await app.observe('log-delete-fixture-identifiers');
    const protectedIds = ids(fixture.protectedOtherCategoryEventIds);
    expect(protectedIds.length).toBeGreaterThan(0);
    for (const id of protectedIds) { expect(actual.visibleEventIds).toContain(id); expect(actual.fileEventIds).toContain(id); }
  }
  return actual;
}
async function prepareDelete(app, category = 'user_actions') {
  const result = await app.act('OWNER', 'prepare-category-log-delete', { category });
  expect(result.outcome).toBe('accepted');
  expect(result.confirmation).toBeTruthy(); identifier(result.operationId);
  const displayed = result.displayed;
  expect(displayed.category).toBe(category); identifier(displayed.boundary); integer(displayed.eventCount); integer(displayed.fileBytes);
  const manifest = await app.observe('prepared-log-deletion-set', { operationId: result.operationId });
  expect(manifest.operationId).toBe(result.operationId); expect(manifest.category).toBe(category);
  expect(manifest.boundary).toBe(displayed.boundary); ids(manifest.eventIds);
  expect(manifest.eventIds.length).toBeGreaterThan(0); expect(displayed.eventCount).toBe(manifest.eventIds.length);
  result.confirmedEventIds = manifest.eventIds;
  const current = await categoryState(app, category);
  for (const id of manifest.eventIds) { expect(current.visibleEventIds).toContain(id); expect(current.fileEventIds).toContain(id); }
  expect(displayed.requiresOwnerPassword).toBe(true);
  return result;
}
async function deleteCategory(app, prepared, extra = {}, actor = 'OWNER') {
  return app.act(actor, 'confirm-category-log-delete-direct', { confirmation: prepared.confirmation,
    operationId: prepared.operationId, passwordRef: 'OWNER-CURRENT-SECRET', ...extra });
}
async function savePage(app, text) {
  const before = await app.observe('page', { page: 'P-LOG-PROBE' });
  identifier(before.revision); expect(typeof before.publicText).toBe('string');
  expect(before.publicText).not.toBe(text);
  const result = await app.act('OWNER', 'submit-page-direct', { page: 'P-LOG-PROBE', base: before.revision, fields: { text } });
  expect(result.outcome).toBe('accepted');
  expect((await app.observe('page', { page: 'P-LOG-PROBE' })).publicText).toBe(text);
  return result;
}

for (const category of categories) {
  test(`LOG-category-${category} | AT-038 AT-307 AC-038 AC-OPS-007 | one category and no raw sensitive corpus in visible/stored outputs`, async ({ app }) => {
    await app.reset('nine-category-source-events');
    const view = await app.act('OWNER', 'view-log-category-direct', { category });
    expect(view.outcome).toBe('accepted');
    const actual = await app.observe('processed-category-evidence', { category });
    expect(actual.category).toBe(category); identifier(actual.sourceEventId);
    expect(actual.primaryCategoryCount).toBe(1);
    for (const key of ['databaseText', 'fileText', 'diagnosticText']) expect(typeof actual[key]).toBe('string');
    for (const value of [view.body, actual.databaseText, actual.fileText]) expect(value).toContain(`SAFE-LOG-${category}`);
    expect(Array.isArray(actual.telegramBodies)).toBe(true); actual.telegramBodies.forEach(body => expect(typeof body).toBe('string'));
    const corpus = await app.observe('synthetic-sensitive-canaries');
    expect(Array.isArray(corpus.values)).toBe(true); expect(corpus.values.length).toBeGreaterThan(0); corpus.values.forEach(identifier);
    expect(view.sensitiveCanaryCheck?.checkedCount).toBe(corpus.values.length);
    expect(view.sensitiveCanaryCheck?.detected).toBe(false);
    const surfaces = [view.body, actual.databaseText, actual.fileText, actual.diagnosticText, ...actual.telegramBodies];
    for (const value of surfaces) { expect(typeof value).toBe('string'); for (const canary of corpus.values) expect(value).not.toContain(canary); }
    expect(actual.sourceAcceptedByRealEventPipeline).toBe(true);
    expect(actual.dbEventIds.filter(id => id === actual.sourceEventId)).toHaveLength(1);
  });
}

test('LOG-group-count | AT-039 AC-039 | 1284 events group without counting the group as one', async ({ app }) => {
  await app.reset('grouped-user-events-1284');
  const actual = await app.observe('log-category-display', { category: 'user_actions' });
  expect(actual.groups).toHaveLength(1); integer(actual.groups[0].count);
  expect(actual.groups[0].count).toBe(1284); expect(actual.exactUnreadCount).toBe(1284);
  expect(actual.badgeText).toBe('999+');
});

test('LOG-open-is-not-read | AT-039 AT-706 AC-039 AC-MAN-006 | opening a category leaves cursor and active cycles intact', async ({ app }) => {
  await app.reset('unread-category-with-open-critical');
  const before = await categoryState(app); expect(before.unreadCount).toBeGreaterThan(0);
  expect(before.activeCriticalIds.length).toBeGreaterThan(0); expect(before.notificationCycleOpen).toBe(true);
  expect((await app.act('OWNER', 'view-log-category-direct', { category: 'user_actions' })).outcome).toBe('accepted');
  const after = await categoryState(app);
  for (const key of ['readBoundary', 'unreadCount', 'activeCriticalIds', 'notificationCycleId', 'notificationCycleOpen']) expect(after[key]).toEqual(before[key]);
});

test('LOG-read-boundary | AT-039 AC-039 | explicit mark-read cannot swallow a real save after its displayed boundary', async ({ app }) => {
  await app.reset('unread-category-with-open-critical');
  const before = await categoryState(app);
  const originalUnread = ids((await app.observe('unread-log-event-ids', { category: 'user_actions' })).ids);
  expect(originalUnread.length).toBeGreaterThan(0);
  const prepared = await app.act('OWNER', 'prepare-log-read-boundary', { category: 'user_actions' });
  expect(prepared.outcome).toBe('accepted'); identifier(prepared.boundary);
  expect(prepared.boundary).not.toBe(before.readBoundary);
  await savePage(app, 'LOG-READ-RACE-PUBLIC-TEXT');
  const tail = await app.observe('latest-page-save-log-event', { page: 'P-LOG-PROBE' }); identifier(tail.eventId);
  expect(originalUnread).not.toContain(tail.eventId);
  expect((await app.act('OWNER', 'mark-log-category-read', { category: 'user_actions', boundary: prepared.boundary })).outcome).toBe('accepted');
  const after = await categoryState(app);
  expect(after.readBoundary).toBe(prepared.boundary); expect(after.unreadCount).toBeGreaterThanOrEqual(1);
  const unread = await app.observe('unread-log-event-ids', { category: 'user_actions' });
  expect(ids(unread.ids)).toContain(tail.eventId);
  for (const id of originalUnread) expect(unread.ids).not.toContain(id);
});

test('LOG-delete-boundary | AT-062 AT-704 AC-062 AC-MAN-004 | only displayed IDs are removed and new save/other category/audit survive', async ({ app }) => {
  await app.reset('category-delete-with-shared-segment');
  const prepared = await prepareDelete(app), otherBefore = await categoryState(app, 'site_errors');
  await savePage(app, 'LOG-DELETE-RACE-PUBLIC-TEXT');
  const tail = await app.observe('latest-page-save-log-event', { page: 'P-LOG-PROBE' }); identifier(tail.eventId);
  expect(prepared.confirmedEventIds).not.toContain(tail.eventId);
  const result = await deleteCategory(app, prepared); expect(result.outcome).toBe('accepted');
  const after = await categoryState(app);
  for (const id of prepared.confirmedEventIds) { expect(after.visibleEventIds).not.toContain(id); expect(after.fileEventIds).not.toContain(id); }
  expect(after.visibleEventIds).toContain(tail.eventId); expect(after.fileEventIds).toContain(tail.eventId);
  expect(ids((await categoryState(app, 'site_errors')).visibleEventIds)).toEqual(ids(otherBefore.visibleEventIds));
  const audit = await app.observe('log-delete-operation-evidence', { operationId: prepared.operationId });
  identifier(audit.eventId); expect(audit.operationId).toBe(prepared.operationId); expect(audit.result).toBe('COMPLETED');
  expect(audit.retained).toBe(true); expect(prepared.confirmedEventIds).not.toContain(audit.eventId);
  expect(after.physicalBytes).toBeLessThanOrEqual(1073741824);
});

test('LOG-delete-not-recovery | AT-062 AT-706 AC-062 AC-MAN-006 | clearing unread events does not mark viewed or repair a critical incident', async ({ app }) => {
  await app.reset('unread-category-with-open-critical');
  const before = await categoryState(app), prepared = await prepareDelete(app);
  expect(before.activeCriticalIds.length).toBeGreaterThan(0); expect(before.notificationCycleOpen).toBe(true);
  expect((await deleteCategory(app, prepared)).outcome).toBe('accepted');
  const after = await categoryState(app);
  for (const key of ['readBoundary', 'activeCriticalIds', 'notificationCycleId', 'notificationCycleOpen']) expect(after[key]).toEqual(before[key]);
  const notifications = await app.observe('critical-notification-evidence');
  integer(notifications.recoveryMessageCount); expect(notifications.recoveryMessageCount).toBe(0);
});

for (const actor of ['S-EDIT', 'VISITOR']) {
  test(`LOG-delete-role-${actor} | AT-062 AT-704 AC-062 AC-MAN-004 | valid deletion is denied to this actor and succeeds for owner`, async ({ app }) => {
    await app.reset('category-delete-with-shared-segment'); const prepared = await prepareDelete(app);
    const before = await categoryState(app);
    expect((await deleteCategory(app, prepared, {}, actor)).outcome).toBe('denied');
    const after = await categoryState(app);
    expect(ids(after.visibleEventIds)).toEqual(ids(before.visibleEventIds)); expect(ids(after.fileEventIds)).toEqual(ids(before.fileEventIds));
    expect((await deleteCategory(app, prepared)).outcome).toBe('accepted');
    for (const id of prepared.confirmedEventIds) expect((await categoryState(app)).visibleEventIds).not.toContain(id);
  });
}

for (const tamper of ['category', 'boundary', 'password', 'GET']) {
  test(`LOG-delete-tamper-${tamper} | AT-062 AT-704 AC-062 AC-MAN-004 | cannot expand a reviewed deletion or skip password/POST`, async ({ app }) => {
    await app.reset('category-delete-with-shared-segment'); const prepared = await prepareDelete(app);
    const before = await categoryState(app), other = await categoryState(app, 'site_errors');
    const args = { confirmation: prepared.confirmation, operationId: prepared.operationId, passwordRef: 'OWNER-CURRENT-SECRET' };
    if (tamper === 'category') args.category = 'site_errors';
    if (tamper === 'boundary') args.boundary = (await app.observe('log-delete-fixture-identifiers')).validLaterBoundary;
    if (tamper === 'password') args.passwordRef = 'OWNER-WRONG-SYNTHETIC-SECRET';
    if (tamper === 'boundary') identifier(args.boundary);
    const result = await app.act('OWNER', tamper === 'GET' ? 'probe-GET-category-log-delete' : 'confirm-category-log-delete-direct', args);
    expect(['denied', 'conflict']).toContain(result.outcome);
    expect(ids((await categoryState(app)).visibleEventIds)).toEqual(ids(before.visibleEventIds));
    expect(ids((await categoryState(app)).fileEventIds)).toEqual(ids(before.fileEventIds));
    expect(ids((await categoryState(app, 'site_errors')).visibleEventIds)).toEqual(ids(other.visibleEventIds));
  });
}

for (const route of ['/.env', '/.git/config', '/wp-login.php', '/phpmyadmin/index.php', '/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php']) {
  test(`LOG-scanner-${route} | AT-041 AC-041 | known signature is an early real 404 without per-probe application work`, async ({ app }) => {
    const admission = await app.inspectInfrastructureAdmission();
    expect(admission.arc10Verified).toBe(true); expect(admission.isolatedInfrastructure).toBe(true);
    identifier(admission.reviewedEvidenceId); expect(admission.capabilities).toContain('scanner-observe-v1');
    await app.reset('scanner-clean-baseline');
    const positive = await app.observe('scanner-legitimate-public-response');
    expect(positive.status).toBe(200); expect(positive.body).toContain('LEGITIMATE-PUBLIC-CANARY');
    const before = await app.observe('scanner-effects');
    for (let n = 0; n < 8; n++) {
      const response = await app.act('VISITOR', 'probe-known-scanner-path', { path: route, query: `probe=${n}` });
      expect(response.observedStatus).toBe(404); expect(response.cacheControl).toContain('no-store');
      expect(response.body).not.toContain('PRIVATE-SCANNER-CANARY');
    }
    const after = await app.observe('scanner-effects');
    for (const key of ['applicationSql', 'createdSessions', 'auditRows', 'telegramMessages']) {
      integer(before[key]); integer(after[key]); expect(after[key] - before[key]).toBe(0);
    }
    integer(after.aggregateKeys); integer(after.configuredAggregateKeyLimit); expect(after.configuredAggregateKeyLimit).toBeGreaterThan(0);
    expect(after.aggregateKeys).toBeLessThanOrEqual(after.configuredAggregateKeyLimit);
    const final = await app.observe('scanner-legitimate-public-response'); expect(final.status).toBe(200); expect(final.body).toContain('LEGITIMATE-PUBLIC-CANARY');
  });
}
