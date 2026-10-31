import { createHash } from 'node:crypto';
import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver(); try { await use(app); } finally { await app.close(); }
} });
test.setTimeout(180_000); // Own isolated test budget, never an owner response deadline.
const id = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
const integer = value => { expect(Number.isSafeInteger(value) && value >= 0).toBe(true); return value; };
const ordered = rows => [...rows].sort((a, b) => a.id.localeCompare(b.id));
function mediaProjection(files) {
  expect(Array.isArray(files)).toBe(true); expect(files.length).toBeGreaterThan(0);
  expect(new Set(files.map(file => id(file.id))).size).toBe(files.length);
  return ordered(files.map(file => {
    expect(Number.isSafeInteger(file.size) && file.size > 0 && file.size <= 256 * 1024).toBe(true);
    const bytes = Buffer.from(file.bytesBase64, 'base64'); expect(bytes.length).toBe(file.size);
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(file.sha256);
    return { id: file.id, size: file.size, sha256: file.sha256 };
  }));
}
async function liveOracle(app) {
  const businessState = await app.observe('restore-live-read-only-state');
  for (const key of ['pages', 'versions', 'requests', 'consents', 'users', 'rights']) {
    expect(Array.isArray(businessState[key])).toBe(true); expect(businessState[key].length).toBeGreaterThan(0);
  }
  const media = await app.observe('restore-current-media-inspection');
  expect(media.source).toBe('actual-working-media-bytes');
  const mediaFiles = mediaProjection(media.files);
  expect(await app.observe('restore-live-read-only-state')).toEqual(businessState);
  return { businessState, mediaFiles };
}
async function safetyMatches(app, operationId, target, before) {
  expect(before).toBeTruthy();
  const safety = await app.observe('restore-safety-inspection', { operationId });
  expect(safety.source).toBe('independent-safety-reconstruction-and-export');
  expect(safety.operationId).toBe(operationId); id(safety.pointId); expect(safety.pointId).not.toBe(target.pointId);
  expect(safety.businessState).toEqual(before.businessState);
  expect(mediaProjection(safety.mediaFiles)).toEqual(before.mediaFiles);
  expect(Number.isFinite(Date.parse(target.cutoffAt))).toBe(true);
  const requests = before.businessState.requests.filter(row => {
    expect(Number.isFinite(Date.parse(row.createdAt))).toBe(true);
    return Date.parse(row.createdAt) > Date.parse(target.cutoffAt);
  });
  const requestIds = new Set(requests.map(row => row.id));
  expect(requests.length).toBeGreaterThan(0);
  expect(ordered(safety.exportRequests)).toEqual(ordered(requests));
  expect(ordered(safety.exportConsents)).toEqual(ordered(before.businessState.consents.filter(row => requestIds.has(row.requestId))));
  expect(safety.exportConsents.length).toBeGreaterThan(0);
  expect(safety.encrypted).toBe(true); expect(safety.verified).toBe(true);
}
async function command(app, action, args) {
  const result = await app.control(action, args); expect(result.outcome).toBe('accepted'); return result;
}
async function setup(app, options = {}) {
  const admission = await app.inspectInfrastructureAdmission();
  expect(admission.arc10Verified).toBe(true); expect(admission.isolatedInfrastructure).toBe(true);
  id(admission.reviewedEvidenceId); expect(admission.capabilities).toContain('restore-control-v1');
  await app.reset('restore-old-point-new-state', options);
  const f = await app.observe('restore-fixture-identifiers');
  for (const key of ['pointId', 'ownerId', 'employeeId', 'removedRequestId', 'keptRequestId', 'afterCutoffRequestId', 'externalDeletionGeneration']) id(f[key]);
  expect(new Set([f.removedRequestId, f.keptRequestId, f.afterCutoffRequestId]).size).toBe(3);
  const target = await app.observe('restore-target-inspection', { pointId: f.pointId });
  expect(target.pointId).toBe(f.pointId); expect(target.source).toBe('independent-reconstruction-of-target-bytes');
  expect(target.verified).toBe(true); expect(target.dumpSha256).toMatch(/^[a-f0-9]{64}$/);
  for (const collection of ['pages', 'versions', 'requests', 'media']) {
    expect(Array.isArray(target[collection])).toBe(true); expect(target[collection].length).toBeGreaterThan(0);
  }
  expect(target.requests.some(row => row.id === f.removedRequestId)).toBe(true);
  expect(target.requests.some(row => row.id === f.keptRequestId)).toBe(true);
  expect(target.requests.some(row => row.id === f.afterCutoffRequestId)).toBe(false);
  const tombstones = await app.observe('restore-external-deletions');
  expect(tombstones.generation).toBe(f.externalDeletionGeneration);
  expect(tombstones.requestIds).toContain(f.removedRequestId);
  expect(tombstones.requestIds).not.toContain(f.keptRequestId);
  return { f, target };
}
async function prepare(app, pointId) {
  const result = await app.act('OWNER', 'prepare-backup-restore', { pointId });
  expect(result.outcome).toBe('accepted'); expect(result.confirmation).toBeTruthy();
  expect(result.displayed.pointId).toBe(pointId); expect(result.displayed.requiresOwnerPassword).toBe(true);
  return result;
}
async function start(app, prepared, pointId, actor = 'OWNER', passwordRef = 'OWNER-CURRENT-SECRET') {
  return app.act(actor, 'confirm-backup-restore', { pointId, confirmation: prepared.confirmation, passwordRef });
}
async function operation(app, operationId) {
  const value = await app.observe('restore-external-operation', { operationId });
  expect(value.operationId).toBe(operationId); expect(value.source).toBe('actual-status-outside-replaced-db');
  return value;
}
async function settle(app, operationId) {
  await expect.poll(async () => (await operation(app, operationId)).phase,
    { timeout: 60_000 }).toMatch(/^(identity-recovery-required|completed|blocked|failed)$/);
  let value = await operation(app, operationId);
  if (value.phase === 'identity-recovery-required') {
    await command(app, 'complete-isolated-identity-recovery', { operationId, operatorRef: 'OWNER-LOCAL-OPERATOR' });
    await expect.poll(async () => (await operation(app, operationId)).phase,
      { timeout: 60_000 }).toMatch(/^(completed|blocked|failed)$/);
    value = await operation(app, operationId);
  }
  return value;
}
function event(ledger, kind) {
  const matches = ledger.events.filter(item => item.kind === kind); expect(matches).toHaveLength(1);
  integer(matches[0].sequence); return matches[0];
}
async function completed(app, f, target, operationId, { readable = true, cause = 'non-security', before } = {}) {
  const result = await settle(app, operationId);
  expect(result.phase).toBe('completed'); expect(result.reportedComplete).toBe(true);
  expect(result.pointId).toBe(f.pointId); expect(result.confirmedByOwnerId).toBe(f.ownerId);
  expect(Number.isFinite(result.elapsedMonotonicMs) && result.elapsedMonotonicMs >= 0).toBe(true);
  const ledger = await app.observe('restore-execution-ledger', { operationId });
  expect(ledger.operationId).toBe(operationId); expect(Array.isArray(ledger.events)).toBe(true);
  const normalOpen = event(ledger, 'normal-access-open').sequence;
  const adminOpen = event(ledger, 'admin-access-open').sequence;
  const replace = event(ledger, 'target-db-applied').sequence;
  const mediaReplace = event(ledger, 'target-media-applied').sequence;
  for (const kind of ['write-fence-closed', 'point-verified', 'compatibility-verified']) {
    expect(event(ledger, kind).sequence).toBeLessThan(replace);
    expect(event(ledger, kind).sequence).toBeLessThan(mediaReplace);
  }
  for (const kind of ['point-verified', 'compatibility-verified', 'target-db-applied', 'target-media-applied',
    'external-deletions-applied', 'old-sessions-invalidated', 'employees-disabled', 'smoke-passed']) {
    expect(event(ledger, kind).sequence).toBeLessThan(normalOpen);
    expect(event(ledger, kind).sequence).toBeLessThan(adminOpen);
  }
  if (readable) {
    for (const kind of ['safety-verified', 'post-cutoff-export-verified']) {
      expect(event(ledger, kind).sequence).toBeLessThan(replace);
      expect(event(ledger, kind).sequence).toBeLessThan(mediaReplace);
    }
    await safetyMatches(app, operationId, target, before);
  } else {
    expect(event(ledger, 'enhanced-loss-confirmed').sequence).toBeLessThan(replace);
    expect(event(ledger, 'enhanced-loss-confirmed').sequence).toBeLessThan(mediaReplace);
  }
  const actual = await app.observe('restored-working-state');
  expect(actual.source).toBe('actual-restored-sql-and-media-bytes');
  expect(actual.pages).toEqual(target.pages); expect(actual.versions).toEqual(target.versions);
  expect(actual.requests).toEqual(target.requests.filter(row => row.id !== f.removedRequestId));
  expect(actual.requests.some(row => row.id === f.afterCutoffRequestId)).toBe(false);
  expect(actual.appliedExternalDeletionGeneration).toBe(f.externalDeletionGeneration);
  expect(actual.media.length).toBe(target.media.length);
  for (const expected of target.media) {
    const files = actual.media.filter(file => file.id === expected.id); expect(files).toHaveLength(1);
    const file = files[0]; expect(Number.isSafeInteger(file.size) && file.size > 0 && file.size <= 256 * 1024).toBe(true);
    const bytes = Buffer.from(file.bytesBase64, 'base64'); expect(bytes.length).toBe(file.size);
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(expected.sha256);
    expect(file.sha256).toBe(expected.sha256); expect(file.size).toBe(expected.size);
  }
  expect(actual.employees.some(user => user.id === f.employeeId)).toBe(true);
  for (const employee of actual.employees) expect(employee.active).toBe(false);
  id(result.effectiveOwnerId);
  expect(actual.owner).toMatchObject({ id: result.effectiveOwnerId, login: 'nesadmin', active: true, isOwner: true });
  for (const actor of ['OWNER-CURRENT-SESSION', 'OWNER-BACKUP-SESSION', 'EMPLOYEE-CURRENT-SESSION', 'EMPLOYEE-BACKUP-SESSION']) {
    const denied = await app.act(actor, 'read-restore-private-direct'); expect(denied.outcome).toBe('denied');
    expect(denied.body).not.toContain('RESTORE-PRIVATE-CANARY');
  }
  expect(['current-owner-preserved', 'break-glass-reset']).toContain(result.ownerRecoveryMethod);
  if (result.ownerRecoveryMethod === 'current-owner-preserved') expect(result.effectiveOwnerId).toBe(f.ownerId);
  if (cause !== 'non-security' || !readable) {
    expect(result.ownerRecoveryMethod).toBe('break-glass-reset');
    expect(event(ledger, 'external-secrets-rotated').sequence).toBeLessThan(event(ledger, 'admin-access-open').sequence);
  }
  if (result.ownerRecoveryMethod === 'break-glass-reset')
    expect(event(ledger, 'interactive-owner-reset-completed').sequence).toBeLessThan(event(ledger, 'admin-access-open').sequence);
  const login = await app.act('OWNER-NEW-LOGIN', 'login-after-restore', {
    passwordRef: result.ownerRecoveryMethod === 'current-owner-preserved' ? 'OWNER-CURRENT-SECRET' : 'RECOVERED-OWNER-SECRET',
  });
  expect(login.outcome).toBe('accepted');
  const identity = await app.act('OWNER-NEW-LOGIN', 'read-restore-private-direct');
  expect(identity.outcome).toBe('accepted'); expect(identity.userId).toBe(result.effectiveOwnerId);
  expect(identity.body).toContain('RESTORE-PRIVATE-CANARY');
  const stalePassword = await app.act('OWNER-STALE-LOGIN', 'login-after-restore', { passwordRef: 'BACKUP-OWNER-SECRET' });
  expect(stalePassword.outcome).toBe('denied');
  const smoke = await app.act('VISITOR', 'read-restored-public-direct');
  expect(smoke.outcome).toBe('accepted'); expect(smoke.status).toBe(200); expect(smoke.body).toContain('RESTORED-TARGET-PUBLIC-CANARY');
}

for (const cause of ['non-security', 'security-suspected', 'unknown']) {
  test(`RESTORE-044-admin-${cause} | AT-044 AT-037 AC-044 AC-037 | explicit full restore reconciles data, deletion bans and identity before opening access`, async ({ app }) => {
    const { f, target } = await setup(app, { cause });
    const before = await liveOracle(app);
    expect(before.businessState.requests.some(row => row.id === f.afterCutoffRequestId)).toBe(true);
    expect(before.businessState.requests.some(row => row.id === f.removedRequestId)).toBe(false);
    expect(before.businessState.pages).not.toEqual(target.pages);
    const prepared = await prepare(app, f.pointId);
    expect(await app.observe('restore-live-read-only-state')).toEqual(before.businessState);
    const requested = await start(app, prepared, f.pointId); expect(requested.outcome).toBe('accepted'); id(requested.operationId);
    await completed(app, f, target, requested.operationId, { cause, before });
  });
}

test('RESTORE-044-external-loss | AT-044 AC-044 | unavailable current storage needs a separate enhanced owner decision in the external procedure', async ({ app }) => {
  const { f, target } = await setup(app, { cause: 'disk-loss', currentReadable: false });
  const prepared = await command(app, 'prepare-isolated-external-restore', { pointId: f.pointId, operatorRef: 'OWNER-LOCAL-OPERATOR' });
  expect(prepared.confirmationRef).toBeTruthy();
  const initial = await command(app, 'confirm-isolated-external-restore', { confirmationRef: prepared.confirmationRef, operatorRef: 'OWNER-LOCAL-OPERATOR' });
  id(initial.operationId);
  await expect.poll(async () => (await operation(app, initial.operationId)).phase, { timeout: 60_000 }).toBe('enhanced-loss-confirmation-required');
  const waiting = await operation(app, initial.operationId);
  expect(waiting.targetReplacementStarted).toBe(false); expect(waiting.reportedComplete).toBe(false);
  expect(waiting.lossExplanationShown).toBe(true); expect(waiting.safetyImpossibleReason).toBeTruthy();
  await command(app, 'confirm-isolated-restore-loss', { operationId: initial.operationId, operatorRef: 'OWNER-LOCAL-OPERATOR' });
  await completed(app, f, target, initial.operationId, { readable: false, cause: 'disk-loss' });
});

for (const fault of ['safety-write-failure', 'external-deletions-unavailable', 'smoke-failure']) {
  test(`RESTORE-044-fault-${fault} | AT-044 AC-044 | failed required stage cannot be reported as a completed restoration`, async ({ app }) => {
    const { f, target } = await setup(app, { cause: 'non-security' });
    const probeText = 'RESTORE-PROBE-VALID-TEXT';
    const preProbe = await app.observe('restore-probe-object', { probeRef: 'BEFORE-RESTORE' });
    id(preProbe.revision); expect(preProbe.publicText).not.toBe(probeText);
    const valid = await app.act('OWNER-PRE-RESTORE-PROBE', 'probe-normal-write-during-restore', {
      probeRef: 'BEFORE-RESTORE', base: preProbe.revision, text: probeText,
    });
    expect(valid.outcome).toBe('accepted');
    expect((await app.observe('restore-probe-object', { probeRef: 'BEFORE-RESTORE' })).publicText).toBe(probeText);
    const before = await liveOracle(app);
    const prepared = await prepare(app, f.pointId);
    await command(app, 'set-isolated-restore-fault', { fault });
    try {
      const requested = await start(app, prepared, f.pointId); expect(requested.outcome).toBe('accepted'); id(requested.operationId);
      const result = await settle(app, requested.operationId);
      expect(['blocked', 'failed']).toContain(result.phase); expect(result.reportedComplete).toBe(false);
      const access = await app.observe('restore-access-evidence', { operationId: requested.operationId });
      expect(access.operationId).toBe(requested.operationId);
      if (fault === 'safety-write-failure') {
        expect(result.targetReplacementStarted).toBe(false);
        expect(await app.observe('restore-live-read-only-state')).toEqual(before.businessState);
      }
      if (result.targetReplacementStarted) {
        expect(access.normalApplicationOpen).toBe(false); expect(access.administrativeAccessOpen).toBe(false);
        await safetyMatches(app, requested.operationId, target, before);
        const beforeProvision = await app.observe('restore-live-read-only-state');
        expect((await app.provisionRestoreWriteProbe(requested.operationId)).outcome).toBe('fixture-provisioned');
        expect(await app.observe('restore-live-read-only-state')).toEqual(beforeProvision);
        const eligible = await app.observe('restore-write-probe-eligibility', { operationId: requested.operationId });
        expect(eligible.source).toBe('actual-framework-auth-csrf-and-object');
        expect(eligible.activeOwner).toBe(true); expect(eligible.csrfValid).toBe(true); id(eligible.probeRef);
        const probe = await app.observe('restore-probe-object', { probeRef: eligible.probeRef });
        id(probe.revision); expect(probe.publicText).not.toBe(probeText);
        const beforeProbe = await app.observe('restore-live-read-only-state');
        const accessBeforeProbe = await app.observe('restore-access-evidence', { operationId: requested.operationId });
        expect(integer(accessBeforeProbe.normalWriteCommits)).toBe(0);
        const denied = await app.act('OWNER-RESTORE-PROBE', 'probe-normal-write-during-restore', {
          probeRef: eligible.probeRef, base: probe.revision, text: probeText,
        });
        expect(denied.outcome).toBe('denied');
        expect(await app.observe('restore-live-read-only-state')).toEqual(beforeProbe);
        const accessAfterProbe = await app.observe('restore-access-evidence', { operationId: requested.operationId });
        expect(accessAfterProbe.normalWriteCommits).toBe(accessBeforeProbe.normalWriteCommits);
        expect(accessAfterProbe.normalApplicationOpen).toBe(false); expect(accessAfterProbe.administrativeAccessOpen).toBe(false);
      }
      const ledger = await app.observe('restore-execution-ledger', { operationId: requested.operationId });
      expect(ledger.events.some(item => item.kind === 'normal-access-open')).toBe(false);
      expect(ledger.events.some(item => item.kind === 'admin-access-open')).toBe(false);
    } finally { await command(app, 'clear-isolated-restore-fault', { fault }); }
  });
}

for (const actor of ['S-EDIT', 'VISITOR']) {
  test(`RESTORE-044-actor-${actor} | AT-044 AC-044 | a valid owner confirmation does not grant restoration permission to another actor`, async ({ app }) => {
    const { f, target } = await setup(app); const prepared = await prepare(app, f.pointId);
    const before = await liveOracle(app);
    const executions = await app.observe('backup-restore-execution-state');
    expect((await start(app, prepared, f.pointId, actor)).outcome).toBe('denied');
    expect(await app.observe('restore-live-read-only-state')).toEqual(before.businessState);
    expect(await app.observe('backup-restore-execution-state')).toEqual(executions);
    const fresh = await prepare(app, f.pointId);
    const allowed = await start(app, fresh, f.pointId); expect(allowed.outcome).toBe('accepted'); id(allowed.operationId);
    await completed(app, f, target, allowed.operationId, { before });
  });
}

test('RESTORE-044-password | AT-044 AC-044 | wrong repeated password refuses mutation before a valid owner confirmation', async ({ app }) => {
  const { f, target } = await setup(app); const prepared = await prepare(app, f.pointId);
  const before = await liveOracle(app), executions = await app.observe('backup-restore-execution-state');
  expect((await start(app, prepared, f.pointId, 'OWNER', 'OWNER-WRONG-SYNTHETIC-SECRET')).outcome).toBe('denied');
  expect(await app.observe('restore-live-read-only-state')).toEqual(before.businessState);
  expect(await app.observe('backup-restore-execution-state')).toEqual(executions);
  const fresh = await prepare(app, f.pointId);
  const allowed = await start(app, fresh, f.pointId); expect(allowed.outcome).toBe('accepted'); id(allowed.operationId);
  await completed(app, f, target, allowed.operationId, { before });
});
