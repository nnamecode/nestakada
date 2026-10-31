import { randomUUID } from 'node:crypto';
import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await use(app); } finally { await app.close(); }
} });
function instant(value) {
  expect(typeof value).toBe('string');
  expect(value).toMatch(/(?:Z|[+-]\d{2}:\d{2})$/);
  const parsed = Date.parse(value); expect(Number.isFinite(parsed)).toBe(true); return parsed;
}
function moscowParts(value) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/Moscow', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(value));
  return Object.fromEntries(parts.filter(p => p.type !== 'literal').map(p => [p.type, Number(p.value)]));
}

for (const nowUtc of ['2026-10-30T20:59:30Z', '2026-10-30T21:00:30Z']) {
  for (const manualDate of ['1960-01-01T00:00:00+03:00', '2099-12-31T23:59:00+03:00']) {
    test(`TIME-059-${nowUtc}-${manualDate.slice(0, 4)} | AT-059 AT-703 AC-059 AC-MAN-003 | manual date cannot replace real authorship, clock or retention order`, async ({ app }) => {
      await app.reset('manual-version-clock-boundary', { nowUtc });
      const before = await app.observe('page', { page: 'P-ASSIGNED' });
      const identity = await app.observe('fixture-identifiers');
      expect(typeof identity.ownerUserId).toBe('string'); expect(identity.ownerUserId.length).toBeGreaterThan(0);
      const ordinary = before.versions.filter(v => !v.isStable);
      const stable = before.versions.filter(v => v.isStable);
      expect(ordinary).toHaveLength(10); expect(stable).toHaveLength(2);
      expect(new Set(ordinary.map(v => instant(v.savedAt))).size).toBe(10);
      for (const version of ordinary) expect(instant(version.savedAt)).toBeLessThan(instant(nowUtc));
      const eligible = ordinary.filter(v => v.id !== before.currentVersionId).sort((a, b) => instant(a.savedAt) - instant(b.savedAt));
      expect(eligible.length).toBeGreaterThan(0);
      const oldest = eligible[0];
      const result = await app.act('OWNER', 'create-named-version', {
        page: 'P-ASSIGNED', currentRevision: before.revision, name: 'Проверка даты',
        comment: 'Синтетическая дата отдельно от времени сохранения', manualDate, operationId: randomUUID(),
      });
      expect(result.outcome).toBe('accepted'); expect(result.versionId).toBeTruthy();
      const after = await app.observe('page', { page: 'P-ASSIGNED' });
      const created = after.versions.find(v => v.id === result.versionId);
      expect(created).toBeTruthy();
      expect(created).toMatchObject({ kind: 'manual', isStable: false, authorId: identity.ownerUserId, text: before.publicText });
      expect(instant(created.savedAt)).toBe(instant(nowUtc));
      expect(instant(created.manualDate)).toBe(instant(manualDate));
      expect(instant(created.manualDate)).not.toBe(instant(created.savedAt));
      for (const key of ['revision', 'currentVersionId', 'publicText', 'draftText', 'url', 'h1', 'title', 'description']) {
        expect(before).toHaveProperty(key); expect(after).toHaveProperty(key); expect(after[key], key).toEqual(before[key]);
      }
      expect(after.versions.filter(v => v.isStable)).toEqual(stable);
      const expectedIds = ordinary.filter(v => v.id !== oldest.id).map(v => v.id).concat(created.id).sort();
      expect(after.versions.filter(v => !v.isStable).map(v => v.id).sort()).toEqual(expectedIds);
      expect(after.versions.some(v => v.id === before.currentVersionId)).toBe(true);
      const audit = await app.observe('manual-version-creation-audit', { versionId: created.id });
      expect(typeof audit.eventId).toBe('string'); expect(audit.eventId.length).toBeGreaterThan(0);
      expect(audit.versionId).toBe(created.id); expect(audit.authorId).toBe(identity.ownerUserId);
      expect(instant(audit.occurredAt)).toBe(instant(nowUtc));
      const presentation = await app.observe('audit-time-presentation', { actor: 'OWNER', eventId: audit.eventId });
      expect(presentation.eventId).toBe(audit.eventId); expect(presentation.authorId).toBe(identity.ownerUserId);
      expect(presentation.zoneLabel).toBe('Europe/Moscow');
      const { second, ...minuteParts } = moscowParts(nowUtc);
      expect(presentation.wallTime).toMatchObject(minuteParts);
      if (Object.hasOwn(presentation.wallTime, 'second')) expect(presentation.wallTime.second).toBe(second);
      expect(presentation.exportOccurredAtUtc).toMatch(/(?:Z|\+00:00)$/);
      expect(instant(presentation.exportOccurredAtUtc)).toBe(instant(nowUtc));
    });
  }
}
