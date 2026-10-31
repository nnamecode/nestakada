import { createHash } from 'node:crypto';
import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver(); try { await use(app); } finally { await app.close(); }
} });
test.setTimeout(180_000); // Tool budget only; no owner reaction or recovery deadline.
const CAP = 1_073_741_824;
const id = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
const integer = value => { expect(Number.isSafeInteger(value) && value >= 0).toBe(true); return value; };
const sorted = values => { expect(Array.isArray(values)).toBe(true); values.forEach(id); expect(new Set(values).size).toBe(values.length); return [...values].sort(); };
async function control(app, action, args) {
  const result = await app.control(action, args); expect(result.outcome).toBe('accepted'); return result;
}
async function category(app, name = 'user_actions') {
  const actual = await app.observe('log-category-state', { category: name });
  expect(actual.category).toBe(name); sorted(actual.visibleEventIds); sorted(actual.fileEventIds);
  id(actual.readBoundary); id(actual.notificationCycleId); sorted(actual.activeCriticalIds);
  integer(actual.unreadCount); integer(actual.physicalBytes);
  return actual;
}
async function saveTail(app, text) {
  const before = await app.observe('page', { page: 'P-LOG-PROBE' }); id(before.revision);
  expect((await app.act('OWNER', 'save-text', {
    page: 'P-LOG-PROBE', base: before.revision, text,
  })).outcome).toBe('accepted');
  expect((await app.observe('page', { page: 'P-LOG-PROBE' })).publicText).toBe(text);
  const actual = await app.observe('latest-page-save-log-event', { page: 'P-LOG-PROBE' }); id(actual.eventId);
  return actual.eventId;
}
async function records(app, operationId) {
  const value = await app.observe('log-delete-physical-records', { operationId, readMode: 'out-of-band-own-test-volume' });
  expect(value.operationId).toBe(operationId); expect(value.source).toBe('actual-complete-decoded-log-file-records');
  expect(value.unmappedRecordRanges).toBe(0); expect(Array.isArray(value.records)).toBe(true);
  expect(value.records.length).toBeGreaterThan(0);
  const result = value.records.map(item => {
    id(item.eventId); id(item.category); id(item.rangeId); integer(item.bytes);
    expect(item.bytes).toBeGreaterThan(0); expect(item.bytes).toBeLessThanOrEqual(64 * 1024);
    const bytes = Buffer.from(item.bytesBase64, 'base64'); expect(bytes.length).toBe(item.bytes);
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(item.sha256);
    return { eventId: item.eventId, category: item.category, rangeId: item.rangeId, bytes: item.bytes, sha256: item.sha256 };
  });
  expect(new Set(result.map(item => item.rangeId)).size).toBe(result.length);
  return result.sort((a, b) => a.rangeId.localeCompare(b.rangeId));
}
function unchangedRecords(after, before, eventIds) {
  const selected = before.filter(item => eventIds.includes(item.eventId));
  for (const eventId of eventIds) expect(selected.some(item => item.eventId === eventId)).toBe(true);
  const comparable = records => records.map(({ eventId, category, bytes, sha256 }) => ({ eventId, category, bytes, sha256 }))
    .sort((a, b) => a.eventId.localeCompare(b.eventId) || a.sha256.localeCompare(b.sha256));
  expect(comparable(after.filter(item => eventIds.includes(item.eventId)))).toEqual(comparable(selected));
}
async function physical(app, operationId, fileAttemptId) {
  const args = { operationId, fileAttemptId, captureThrough: 'causal-quiescence' };
  await expect.poll(async () => {
    const e = await app.observe('log-delete-physical-evidence', args);
    return [e.captureClosed, e.terminalObserved, e.pendingDescendantWork];
  }, { timeout: 30_000 }).toEqual([true, true, 0]);
  const e = await app.observe('log-delete-physical-evidence', args);
  expect(e.operationId).toBe(operationId); expect(e.fileAttemptId).toBe(fileAttemptId);
  expect(e.source).toBe('actual-isolated-volume-io-trace'); id(e.captureId);
  expect(e.coverage).toBe('before-file-attempt-through-causal-quiescence'); expect(e.capBytes).toBe(CAP);
  expect(e.captureClosed).toBe(true); expect(e.terminalObserved).toBe(true); expect(e.pendingDescendantWork).toBe(0);
  integer(e.captureStartSequence); integer(e.captureEndSequence); expect(e.captureEndSequence).toBeGreaterThan(e.captureStartSequence);
  expect(Array.isArray(e.allocationEvents)).toBe(true); expect(e.allocationEvents.length).toBeGreaterThan(0);
  let last = -1;
  for (const event of e.allocationEvents) {
    expect(integer(event.sequence)).toBeGreaterThan(last); last = event.sequence;
    expect(event.sequence).toBeGreaterThanOrEqual(e.captureStartSequence); expect(event.sequence).toBeLessThanOrEqual(e.captureEndSequence);
    expect(integer(event.totalFileBytes)).toBeLessThanOrEqual(CAP);
  }
  expect(e.highWaterBytes).toBe(Math.max(...e.allocationEvents.map(event => event.totalFileBytes)));
  const final = e.checkpoints.filter(point => point.phase === 'causal-quiescence-end'); expect(final).toHaveLength(1);
  expect(final[0].sequence).toBe(e.captureEndSequence); expect(Array.isArray(final[0].files)).toBe(true);
  expect(final[0].files.length).toBeGreaterThan(0);
  expect(new Set(final[0].files.map(file => file.objectId)).size).toBe(final[0].files.length);
  const total = final[0].files.reduce((sum, file) => {
    id(file.objectId); expect(['active', 'closed', 'compressed', 'manifest', 'temporary']).toContain(file.kind);
    return sum + integer(file.bytes);
  }, 0);
  expect(final[0].totalFileBytes).toBe(total); expect(total).toBeLessThanOrEqual(e.highWaterBytes);
  const closing = e.allocationEvents.at(-1);
  expect(closing.operation).toBe('final-measurement'); expect(closing.sequence).toBe(e.captureEndSequence); expect(closing.totalFileBytes).toBe(total);
  return { captureId: e.captureId, totalBytes: total };
}
async function operation(app, operationId, expectedState) {
  await expect.poll(async () => (await app.observe('log-delete-operation-state', { operationId })).state,
    { timeout: 30_000 }).toBe(expectedState);
  const actual = await app.observe('log-delete-operation-state', { operationId });
  expect(actual.operationId).toBe(operationId); expect(actual.state).toBe(expectedState); id(actual.fileAttemptId);
  return actual;
}
async function view(app, operationId, actualState, physical) {
  const displayed = await app.observe('log-delete-progress-view', { operationId });
  expect(displayed.operationId).toBe(operationId); expect(displayed.state).toBe(actualState);
  expect(displayed.physicalCaptureId).toBe(physical.captureId); expect(displayed.reportedPhysicalBytes).toBe(physical.totalBytes);
  expect(displayed.reportedComplete).toBe(actualState === 'COMPLETED');
}
async function audit(app, prepared, expectedState) {
  const actual = await app.observe('log-delete-operation-evidence', { operationId: prepared.operationId });
  expect(actual.operationId).toBe(prepared.operationId); id(actual.eventId);
  expect(actual.retained).toBe(true); expect(actual.result).toBe(expectedState);
  expect(prepared.eventIds).not.toContain(actual.eventId);
  const placement = await app.observe('log-delete-audit-placement', { operationId: prepared.operationId, eventId: actual.eventId });
  expect(placement.operationId).toBe(prepared.operationId); expect(placement.eventId).toBe(actual.eventId);
  expect(placement.source).toBe('actual-audit-record-bytes-and-resolved-storage-placement');
  const record = placement.auditRecord;
  id(record.storeIdentity); id(record.objectIdentity); integer(record.startOffset); integer(record.endOffset);
  expect(record.endOffset).toBeGreaterThan(record.startOffset);
  const bytes = Buffer.from(record.bytesBase64, 'base64');
  expect(bytes.length).toBeGreaterThan(0); expect(bytes.length).toBeLessThanOrEqual(64 * 1024);
  expect(createHash('sha256').update(bytes).digest('hex')).toBe(record.sha256);
  expect(record.decodedEventId).toBe(actual.eventId); expect(record.decodedOperationId).toBe(prepared.operationId);
  expect(Array.isArray(placement.confirmedPhysicalRanges)).toBe(true); expect(placement.confirmedPhysicalRanges.length).toBeGreaterThan(0);
  for (const range of placement.confirmedPhysicalRanges) {
    id(range.storeIdentity); id(range.objectIdentity); integer(range.startOffset); integer(range.endOffset);
    expect(range.endOffset).toBeGreaterThan(range.startOffset);
    const sameObject = range.storeIdentity === record.storeIdentity && range.objectIdentity === record.objectIdentity;
    expect(sameObject && record.startOffset < range.endOffset && range.startOffset < record.endOffset).toBe(false);
  }
  expect(['protected-category', 'external-journal']).toContain(placement.kind);
  if (placement.kind === 'protected-category') {
    expect(actual.category).not.toBe(prepared.category);
    expect(placement.protectedCategory).toBe(actual.category);
  } else {
    id(placement.managedLogRootIdentity); id(placement.externalJournalRootIdentity);
    expect(placement.externalJournalRootIdentity).not.toBe(placement.managedLogRootIdentity);
    expect(sorted(placement.auditObjectAncestorIdentities)).toContain(placement.externalJournalRootIdentity);
    expect(placement.auditObjectAncestorIdentities).not.toContain(placement.managedLogRootIdentity);
    // Same semantic category is allowed in the external journal; physical placement protects this record.
  }
}

for (const fault of ['file-access-denied', 'no-space-for-safe-partial-segment']) {
  test(`LOG-PARTIAL-705-${fault} | AT-062 AT-704 AT-705 AT-706 AC-062 AC-MAN-004 AC-MAN-005 AC-MAN-006 | physical failure preserves boundary and retry resumes only the same deletion`, async ({ app }) => {
    const admission = await app.inspectInfrastructureAdmission();
    expect(admission.arc10Verified).toBe(true); expect(admission.isolatedInfrastructure).toBe(true);
    id(admission.reviewedEvidenceId); expect(admission.capabilities).toContain('log-deletion-control-v1');
    await app.reset('category-delete-shared-range-file-failure');
    const original = await category(app), other = await category(app, 'site_errors');
    expect(original.notificationCycleOpen).toBe(true); expect(original.activeCriticalIds.length).toBeGreaterThan(0);
    expect(other.visibleEventIds.length).toBeGreaterThan(0);
    const result = await app.act('OWNER', 'prepare-category-log-delete', { category: 'user_actions' });
    expect(result.outcome).toBe('accepted'); id(result.operationId); expect(result.confirmation).toBeTruthy();
    const prepared = await app.observe('prepared-log-deletion-set', { operationId: result.operationId });
    expect(prepared.operationId).toBe(result.operationId); expect(prepared.category).toBe('user_actions'); id(prepared.boundary);
    const selected = sorted(prepared.eventIds); expect(selected.length).toBeGreaterThan(0);
    expect(result.displayed.category).toBe(prepared.category); expect(result.displayed.boundary).toBe(prepared.boundary);
    expect(result.displayed.eventCount).toBe(selected.length);
    for (const eventId of selected) { expect(original.visibleEventIds).toContain(eventId); expect(original.fileEventIds).toContain(eventId); }
    const firstTail = await saveTail(app, 'LOG-PARTIAL-TAIL-AFTER-CONFIRMATION'); expect(selected).not.toContain(firstTail);
    const beforeBytes = await records(app, result.operationId);
    const prefixLayout = await app.observe('log-delete-shared-range-layout', { operationId: result.operationId, tailEventId: firstTail });
    expect(prefixLayout.operationId).toBe(result.operationId); expect(prefixLayout.tailEventId).toBe(firstTail);
    id(prefixLayout.segmentId); expect(prefixLayout.confirmedPrefixEventIds.some(eventId => selected.includes(eventId))).toBe(true);
    expect(integer(prefixLayout.confirmedPrefixEndOffset)).toBeGreaterThan(0); integer(prefixLayout.tailStartOffset);
    expect(prefixLayout.confirmedPrefixEndOffset).toBeLessThanOrEqual(prefixLayout.tailStartOffset);
    const payload = { confirmation: result.confirmation, operationId: result.operationId };
    let failedAttempt, secondTail;
    try {
      await control(app, 'set-log-delete-file-fault', { operationId: result.operationId, fault });
      expect(['accepted', 'pending']).toContain((await app.act('OWNER', 'confirm-category-log-delete-direct', payload)).outcome);
      failedAttempt = await operation(app, result.operationId, 'LOGICAL_DONE_FILES_PENDING');
      expect(sorted(failedAttempt.confirmedEventIds)).toEqual(selected); expect(failedAttempt.boundary).toBe(prepared.boundary);
      const partial = await physical(app, result.operationId, failedAttempt.fileAttemptId); expect(partial.totalBytes).toBeGreaterThan(0);
      await view(app, result.operationId, 'LOGICAL_DONE_FILES_PENDING', partial);
      const after = await category(app), partialBytes = await records(app, result.operationId);
      for (const eventId of selected) expect(after.visibleEventIds).not.toContain(eventId);
      expect(after.visibleEventIds).toContain(firstTail); expect(after.fileEventIds).toContain(firstTail);
      unchangedRecords(partialBytes, beforeBytes, [firstTail, ...other.fileEventIds]);
      expect(partialBytes.some(item => selected.includes(item.eventId))).toBe(true);
      for (const key of ['readBoundary', 'notificationCycleId', 'notificationCycleOpen']) expect(after[key]).toEqual(original[key]);
      for (const criticalId of original.activeCriticalIds) expect(after.activeCriticalIds).toContain(criticalId);
      await audit(app, prepared, 'LOGICAL_DONE_FILES_PENDING');
      secondTail = await saveTail(app, 'LOG-PARTIAL-TAIL-WHILE-FILES-PENDING'); expect(selected).not.toContain(secondTail);
      expect(secondTail).not.toBe(firstTail);
    } finally { await control(app, 'clear-log-delete-file-fault', { operationId: result.operationId, fault }); }
    id(secondTail);
    const retryBytes = await records(app, result.operationId);
    expect(['accepted', 'pending']).toContain((await app.act('OWNER', 'confirm-category-log-delete-direct', payload)).outcome);
    const done = await operation(app, result.operationId, 'COMPLETED');
    expect(done.fileAttemptId).not.toBe(failedAttempt.fileAttemptId);
    expect(done.boundary).toBe(prepared.boundary); expect(sorted(done.confirmedEventIds)).toEqual(selected);
    const final = await physical(app, result.operationId, done.fileAttemptId); await view(app, result.operationId, 'COMPLETED', final);
    const after = await category(app), afterBytes = await records(app, result.operationId);
    for (const eventId of selected) { expect(after.visibleEventIds).not.toContain(eventId); expect(after.fileEventIds).not.toContain(eventId); }
    expect(afterBytes.filter(item => selected.includes(item.eventId))).toEqual([]);
    unchangedRecords(afterBytes, retryBytes, [firstTail, secondTail, ...other.fileEventIds]);
    for (const eventId of [firstTail, secondTail]) { expect(after.visibleEventIds).toContain(eventId); expect(after.fileEventIds).toContain(eventId); }
    const otherAfter = await category(app, 'site_errors');
    for (const eventId of other.visibleEventIds) expect(otherAfter.visibleEventIds).toContain(eventId);
    for (const eventId of other.fileEventIds) expect(otherAfter.fileEventIds).toContain(eventId);
    for (const key of ['readBoundary', 'notificationCycleId', 'notificationCycleOpen']) expect(after[key]).toEqual(original[key]);
    for (const criticalId of original.activeCriticalIds) expect(after.activeCriticalIds).toContain(criticalId);
    expect(after.unreadCount).toBeGreaterThanOrEqual(2); await audit(app, prepared, 'COMPLETED');
    expect(['accepted', 'pending']).toContain((await app.act('OWNER', 'confirm-category-log-delete-direct', payload)).outcome);
    const repeated = await operation(app, result.operationId, 'COMPLETED');
    expect(repeated.fileAttemptId).toBe(done.fileAttemptId); expect(sorted(repeated.confirmedEventIds)).toEqual(selected);
    const repeatedBytes = await records(app, result.operationId);
    unchangedRecords(repeatedBytes, afterBytes, [firstTail, secondTail, ...other.fileEventIds]);
    expect(repeatedBytes.filter(item => selected.includes(item.eventId))).toEqual([]);
  });
}
