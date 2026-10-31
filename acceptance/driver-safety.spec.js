import path from 'node:path';
import fs from 'node:fs';
import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { test, expect } from '@playwright/test';
import { localTarget } from './test-support.js';
import { actorBrowserOptions, responseReportBody, validateFoundationProcessRequest, foundationProcessData, pick, materialize, targetPath, validateBindings, validateStorage, validateRestoreProbeSession, fixtureExchange, guardUiPreparation, validateControlAdmission, validateControlReply, controlCapability } from './driver-safety.js';
import { driverKind, loadBindings } from './isolated-application-driver.js';
import { filePayload, multipartPayload, transportFileLimit } from './upload-support.js';
import { sensitiveValueCheck, htmlSensitiveCheck } from './response-safety.js';
import { inspectBrowserPersistence } from './browser-memory.js';
import { authSourceOrigin, authCsrfPreparation } from './driver-safety.js';

const directory = fileURLToPath(new URL('.', import.meta.url));

test('DRIVER-SAFE-036 | real auth source proxies and fresh CSRF preparation stay in the reviewed fixture scope', () => {
  const profile='auth-login-isolated-sources';
  expect(authSourceOrigin(profile,'LOGIN-A','http://host.docker.internal:8768').port).toBe('8768');
  expect(authSourceOrigin(profile,'LOGIN-A2','http://host.docker.internal:8768').port).toBe('8768');
  expect(authSourceOrigin(profile,'LOGIN-B','http://host.docker.internal:8769').port).toBe('8769');
  for(const args of [[profile,'OWNER','http://host.docker.internal:8768'],['other','LOGIN-A','http://host.docker.internal:8768'],
    [profile,'LOGIN-A','http://host.docker.internal:8769'],[profile,'LOGIN-B','http://example.com:8769'],
    [profile,'LOGIN-A','http://host.docker.internal:8768/arbitrary']]) expect(()=>authSourceOrigin(...args)).toThrow('AUTH_SOURCE_SCOPE');
  const definition={kind:'http',method:'POST',encoding:'form',path:'/manage/login/',freshCsrfPath:'/manage/login/'};
  expect(authCsrfPreparation(profile,definition)).toBe('/manage/login/');
  for(const altered of [{...definition,method:'GET'},{...definition,path:'/arbitrary/'},{...definition,freshCsrfPath:'http://example.com/'},
    {...definition,encoding:'json'}])expect(()=>authCsrfPreparation(profile,altered)).toThrow('AUTH_CSRF_SCOPE');
  expect(()=>authCsrfPreparation('other',definition)).toThrow('AUTH_CSRF_SCOPE');
});

test('DRIVER-SAFE-034 | fixed foundation process reads cannot become arbitrary commands, paths or business observations', () => {
  const view = 'foundation-settings', profile = 'local-foundation-isolated';
  expect(() => validateFoundationProcessRequest(view, { profile: 'local-http' }, profile)).not.toThrow();
  for (const args of [{ command: 'anything' }, { path: '/outside' }, { profile: 'production' }, { profile: 'local-http', expected: true }])
    expect(() => validateFoundationProcessRequest(view, args, profile)).toThrow('SCOPE_REQUIRED');
  expect(() => validateFoundationProcessRequest('page', {}, profile)).toThrow('SCOPE_REQUIRED');
  expect(() => validateFoundationProcessRequest(view, {}, 'other-profile')).toThrow('SCOPE_REQUIRED');
  for (const [name, declaration] of [[view, { kind: 'fixture-read' }], ['page', { kind: 'process-read' }],
    [view, { kind: 'process-read', command: 'anything' }]]) {
    const value = bindings(); value.observations[name] = declaration;
    expect(() => validateBindings(value, base.href)).toThrow('PROCESS_DECLARATION_INVALID');
  }
});

test('DRIVER-SAFE-035 | process provenance is honest and limited to the current local fixture run', () => {
  const context = { view: 'foundation-settings', args: {}, profileName: 'local-foundation-isolated', runId: 'synthetic-run' };
  const reply = () => ({ source: 'actual-process', runId: context.runId,
    evidence: { fixtureProfile: context.profileName }, data: { safeSetting: false } });
  expect(foundationProcessData(reply(), context)).toEqual({ safeSetting: false });
  for (const alter of [r => { r.source = 'actual-http'; }, r => { r.runId = 'old-run'; },
    r => { r.evidence.fixtureProfile = 'other'; }, r => { r.data = null; }]) {
    const value = reply(); alter(value); expect(() => foundationProcessData(value, context)).toThrow('PROVENANCE_REQUIRED');
  }
});

test('DRIVER-SAFE-031 | real empty HTTP304 stays empty after HTML parser serialization', async ({ request }) => {
  const server = http.createServer((req, res) => { res.writeHead(304, { ETag: 'W/"transport"' }); res.end(); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const response = await request.get(`http://127.0.0.1:${server.address().port}/`, { headers: { 'if-none-match': 'W/"transport"' }, maxRedirects: 0 });
    expect(response.status()).toBe(304); expect(response.headers().etag).toBe('W/"transport"');
    expect(responseReportBody(response.status(), await response.text(), '<html><head></head><body></body></html>')).toBe('');
    expect(() => responseReportBody(304, 'unexpected bytes', '')).toThrow('DRIVER_NOT_MODIFIED_BODY_NOT_EMPTY');
  } finally { await new Promise(resolve => server.close(resolve)); }
});

test('DRIVER-SAFE-028 | visitor JS policy rejects nonboolean input', () => {
  for (const value of ['false', 0, null, {}]) expect(() => actorBrowserOptions(undefined, value)).toThrow('DRIVER_JAVASCRIPT_POLICY_INVALID');
  expect(actorBrowserOptions(undefined, false)).toMatchObject({ javaScriptEnabled: false, serviceWorkers: 'block', acceptDownloads: false });
  expect(actorBrowserOptions(undefined).javaScriptEnabled).toBe(true);
});

test('DRIVER-SAFE-029 | actor context options disable actual inline JS while native form POST works on synthetic harness', async ({ browser }) => {
  const context = await browser.newContext(actorBrowserOptions(undefined, false));
  try {
    const posted = [];
    await context.route('**/*', async route => {
      posted.push({ method: route.request().method(), body: route.request().postData() });
      await route.fulfill({ status: 200, contentType: 'text/html', body: '<p>transport received</p>' });
    });
    const page = await context.newPage();
    await page.setContent('<script>document.documentElement.dataset.ran="yes"</script><form method="post" action="http://127.0.0.1:8000/synthetic-transport"><input name="probe" value="own"><button>Transport submit</button></form>');
    expect(await page.locator('html').getAttribute('data-ran')).toBeNull();
    await Promise.all([page.waitForURL('http://127.0.0.1:8000/synthetic-transport'), page.getByRole('button', { name: 'Transport submit' }).click()]);
    expect(posted).toEqual([{ method: 'POST', body: 'probe=own' }]);
  } finally { await context.close(); }
});

test('DRIVER-SAFE-030 | 304 transport outcome is restricted to explicit conditional GET, never business acceptance', () => {
  const operation = () => ({ kind: 'http', method: 'GET', headers: { 'if-none-match': { $ref: 'args.etag' } },
    result: { format: 'html', outcomes: [{ outcome: 'not-modified', statuses: [304] }] } });
  const bind = op => ({ ...bindings(), operations: { revalidate: op } });
  expect(() => validateBindings(bind(operation()), base.href)).not.toThrow();
  for (const alter of [op => { op.method = 'POST'; }, op => { op.headers = {}; },
    op => { op.followRedirectGet = true; }, op => { op.result.outcomes[0].statuses = [200, 304]; },
    op => { op.result.outcomes[0].outcome = 'accepted'; }]) {
    const op = operation(); alter(op); expect(() => validateBindings(bind(op), base.href)).toThrow();
  }
});
const base = localTarget('http://127.0.0.1:8000');
const bindings = () => ({ schema: 'isolated-ui-http-v1', targetOrigin: base.origin,
  profiles: ['synthetic-profile'], observations: {}, operations: {
    example: { kind: 'http', method: 'POST', result: { format: 'html', outcomes: [
      { outcome: 'accepted', statuses: [200], marker: { selector: '[data-synthetic-result]' } },
      { outcome: 'denied', statuses: [403] },
    ] } },
  } });

test('DRIVER-SAFE-001 | importing adapter does not create a fake application', () => {
  expect(driverKind).toBe('real-isolated-application-v1');
  expect(validateBindings(bindings(), base.href).base.origin).toBe(base.origin);
});

test('DRIVER-MEMORY-001 | only fixed actor-browser inspection can be declared, never a fixture echo', async () => {
  const value = bindings(); value.observations['editor-memory-state'] = { kind: 'ui-memory' };
  expect(() => validateBindings(value, base.href)).not.toThrow();
  value.observations['editor-memory-state'].script = 'untrusted';
  expect(() => validateBindings(value, base.href)).toThrow('MEMORY_OBSERVATION_INVALID');
  value.observations['editor-memory-state'] = { kind: 'fixture-read' };
  expect(() => validateBindings(value, base.href)).toThrow('MEMORY_OBSERVATION_INVALID');
  delete value.observations['editor-memory-state']; value.observations.other = { kind: 'ui-memory' };
  expect(() => validateBindings(value, base.href)).toThrow('MEMORY_OBSERVATION_INVALID');
  await expect(inspectBrowserPersistence({ url: () => base.href }, base.origin, '')).rejects.toThrow('CANARY_INVALID');
  await expect(inspectBrowserPersistence({ url: () => 'about:blank' }, base.origin, 'synthetic-canary')).rejects.toThrow('ORIGIN_MISMATCH');
});

test('DRIVER-MEMORY-002 | real browser storage and encoded URL are inspected without returning their contents', async ({ page }) => {
  const server = http.createServer((request, response) => {
    response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    response.end('<!doctype html><title>Synthetic memory-tool selfcheck</title><textarea aria-label="Synthetic input"></textarea>');
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const origin = `http://127.0.0.1:${server.address().port}`;
  const canary = 'SYNTHETIC-MEMORY-CANARY';
  try {
    await page.goto(origin + '/memory-tool');
    await page.getByLabel('Synthetic input').fill(canary);
    const clean = { source: 'actual-actor-browser', urlContainsCanary: false,
      localStorageContainsCanary: false, sessionStorageContainsCanary: false };
    expect(await inspectBrowserPersistence(page, origin, canary)).toEqual(clean);
    await page.evaluate(canary => {
      const encoded = [...canary].map(ch => '%' + ch.charCodeAt(0).toString(16)).join('');
      localStorage.setItem('synthetic', encodeURIComponent(encoded));
      sessionStorage.setItem(canary, 'synthetic value');
      history.replaceState(null, '', '/memory-tool?draft=' + encoded);
    }, canary);
    const leaked = await inspectBrowserPersistence(page, origin, canary);
    expect(leaked).toEqual({ source: 'actual-actor-browser', urlContainsCanary: true,
      localStorageContainsCanary: true, sessionStorageContainsCanary: true });
    expect(JSON.stringify(leaked)).not.toContain(canary);
    await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); history.replaceState(null, '', '/memory-tool'); });
    expect(await inspectBrowserPersistence(page, origin, canary)).toEqual(clean);
    expect(await page.getByLabel('Synthetic input').inputValue()).toBe(canary);
  } finally { await new Promise(resolve => server.close(resolve)); }
});

test('DRIVER-SAFE-013 | absent test input fails closed without changing real private bindings', () => {
  expect(() => loadBindings(path.join(directory, 'driver-safety-never-created-input.json'))).toThrow('DRIVER_BINDINGS_NOT_CONFIGURED');
});

test('DRIVER-SAFE-014 | UI-only result requires actual probes and cannot claim server accepted', () => {
  const value = bindings();
  value.operations = { 'type-unsaved-text': { kind: 'ui', steps: [{ kind: 'fill' }],
    result: { format: 'ui', probes: [{ locator: { label: 'Synthetic input' }, read: 'input', expected: { $ref: 'args.text' } }] } } };
  expect(() => validateBindings(value, base.href)).not.toThrow();
  value.operations['type-unsaved-text'].result.outcomes = [{ outcome: 'accepted', statuses: [200] }];
  expect(() => validateBindings(value, base.href)).toThrow('UI_ONLY_DECLARATION_INVALID');
});

for (const profile of ['page-history-restore', 'controlled-session-boundary']) {
  test(`DRIVER-SAFE-015-${profile} | real open editor preparation is required`, () => {
    const value = bindings(); value.profiles = [profile];
    expect(() => validateBindings(value, base.href)).toThrow('UI_PREPARATION_REQUIRED');
    value.profileSetups = { [profile]: { actors: [{ actor: 'S-EDIT', steps: [{ kind: 'goto' }, { kind: 'fill' }] }], finalizeFixture: true } };
    expect(() => validateBindings(value, base.href)).not.toThrow();
    if (profile === 'controlled-session-boundary') {
      value.profileSetups[profile].finalizeFixture = false;
      expect(() => validateBindings(value, base.href)).toThrow('AFTER_UI_FINALIZATION_REQUIRED');
    }
  });
}
for (const url of ['http://estakada-service.ru:8000', 'https://estakada-service.ru/', 'http://127.0.0.1:8765']) {
  test(`DRIVER-SAFE-origin-${url} | old site and preview not valid adapter targets`, () => {
    expect(() => validateBindings(bindings(), url)).toThrow();
  });
}
test('DRIVER-SAFE-002 | fixture/target origin mismatch rejected', () => {
  const value = bindings(); value.targetOrigin = 'http://127.0.0.1:9000';
  expect(() => validateBindings(value, base.href)).toThrow('MISMATCH');
});

for (const origin of [base.origin, 'http://estakada-service.ru:8000', 'http://127.0.0.1:8765']) {
  test(`DRIVER-SAFE-017-${origin} | control origin must be independently local and never preview`, () => {
    const value = bindings(); value.controlOrigin = origin;
    value.controls = { 'advance-infrastructure-time': value.operations.example };
    expect(() => validateBindings(value, base.href)).toThrow();
  });
}

test('DRIVER-SAFE-018 | control transport cannot execute business actions or GET mutations', () => {
  const value = bindings(); value.controlOrigin = 'http://127.0.0.1:9001';
  value.controls = { 'submit-page-direct': value.operations.example };
  expect(() => validateBindings(value, base.href)).toThrow('CONTROL_ACTION_NOT_ALLOWED');
  value.controls = { 'advance-infrastructure-time': { ...value.operations.example, method: 'GET' } };
  expect(() => validateBindings(value, base.href)).toThrow('CONTROL_ACTION_NOT_ALLOWED');
});

test('DRIVER-SAFE-019 | independent test control binding keeps the application origin unchanged', () => {
  const value = bindings(); value.controlOrigin = 'http://127.0.0.1:9001';
  value.controls = { 'advance-infrastructure-time': value.operations.example };
  const checked = validateBindings(value, base.href);
  expect(checked.base.origin).toBe(base.origin);
  expect(checked.controlBase.origin).toBe(value.controlOrigin);
});

test('DRIVER-SAFE-020 | control admission is bound to current run, instance and generation', () => {
  const controlBase = localTarget('http://127.0.0.1:9001'), runId = 'synthetic-run-0001';
  const admission = { arc10Verified: true, isolatedInfrastructure: true, capabilities: ['fallback-control-v1'],
    reviewedEvidenceId: 'synthetic-evidence', controlOrigin: controlBase.origin, runId,
    controlInstanceId: 'synthetic-instance', admissionGeneration: 'synthetic-generation' };
  const session = { instanceId: admission.controlInstanceId, admissionGeneration: admission.admissionGeneration, runId };
  expect(validateControlAdmission(admission, { controlBase, runId, session }).instanceId).toBe(session.instanceId);
  for (const key of ['runId', 'controlInstanceId', 'admissionGeneration', 'controlOrigin'])
    expect(() => validateControlAdmission({ ...admission, [key]: 'stale' }, { controlBase, runId, session })).toThrow('NOT_ADMITTED');
});

test('DRIVER-SAFE-021 | control reply cannot reuse an old run, operation, instance, admission or capability', () => {
  const correlation = { runId: 'r', operationId: 'o', instanceId: 'i', admissionGeneration: 'g', capability: 'fallback-control-v1' };
  const headers = { 'x-estakada-test-run': 'r', 'x-estakada-test-operation': 'o', 'x-estakada-test-instance': 'i', 'x-estakada-test-admission': 'g', 'x-estakada-test-capability': 'fallback-control-v1' };
  expect(() => validateControlReply(headers, correlation)).not.toThrow();
  for (const key of Object.keys(headers))
    expect(() => validateControlReply({ ...headers, [key]: 'stale' }, correlation)).toThrow('CORRELATION_NOT_CONFIRMED');
});

test('DRIVER-SAFE-022 | pending needs explicit observed evidence and cannot be inferred from HTTP 200/202', () => {
  const value = bindings();
  value.operations.example.result.outcomes = [{ outcome: 'pending', statuses: [202] }];
  expect(() => validateBindings(value, base.href)).toThrow('ACTUAL_RESULT_MARKER_REQUIRED');
  value.operations.example.result.outcomes[0].marker = { selector: '[data-synthetic-waiting]' };
  expect(() => validateBindings(value, base.href)).not.toThrow();
  value.operations.example.result.outcomes[0].statuses = [200];
  delete value.operations.example.result.outcomes[0].marker;
  expect(() => validateBindings(value, base.href)).toThrow('ACTUAL_RESULT_MARKER_REQUIRED');
});

test('DRIVER-SAFE-023 | job domains require their own capability, unknown business commands remain forbidden', () => {
  expect(controlCapability('run-isolated-backup-job')).toBe('backup-control-v1');
  expect(controlCapability('run-isolated-html-build')).toBe('html-build-control-v1');
  expect(controlCapability('stop-isolated-component')).toBe('fallback-control-v1');
  for (const action of ['run-isolated-log-maintenance', 'hold-log-maintenance-phase', 'release-log-maintenance-phase',
    'set-log-storage-fault', 'clear-log-storage-fault', 'advance-log-test-time'])
    expect(controlCapability(action)).toBe('log-maintenance-control-v1');
  for (const action of ['start-isolated-job-invocation', 'hold-isolated-job-phase', 'release-isolated-job-barrier',
    'fail-isolated-job-phase', 'clear-isolated-job-fault', 'advance-background-test-time'])
    expect(controlCapability(action)).toBe('background-job-control-v1');
  for (const action of ['set-isolated-restore-fault', 'clear-isolated-restore-fault', 'prepare-isolated-external-restore',
    'confirm-isolated-external-restore', 'confirm-isolated-restore-loss', 'complete-isolated-identity-recovery', 'prepare-isolated-restore-write-probe'])
    expect(controlCapability(action)).toBe('restore-control-v1');
  for (const action of ['set-log-delete-file-fault', 'clear-log-delete-file-fault'])
    expect(controlCapability(action)).toBe('log-deletion-control-v1');
  expect(() => controlCapability('publish-page')).toThrow('CONTROL_ACTION_NOT_ALLOWED');
});
for (const capability of ['backup-control-v1', 'html-build-control-v1', 'log-maintenance-control-v1', 'background-job-control-v1', 'restore-control-v1', 'log-deletion-control-v1', 'url-transition-control-v1', 'service-quota-control-v1', 'content-storage-control-v1']) {
  test(`DRIVER-SAFE-024-${capability} | fallback-only admission cannot authorize another job domain`, () => {
    const controlBase = localTarget('http://127.0.0.1:9001'), runId = 'synthetic-run-0001';
    const session = { instanceId: 'i', runId, admissionGeneration: 'g' };
    const admission = { arc10Verified: true, isolatedInfrastructure: true, capabilities: ['fallback-control-v1'],
      reviewedEvidenceId: 'e', controlOrigin: controlBase.origin, runId, controlInstanceId: 'i', admissionGeneration: 'g' };
    expect(() => validateControlAdmission(admission, { controlBase, runId, session, capability })).toThrow('NOT_ADMITTED');
    admission.capabilities.push(capability);
    expect(validateControlAdmission(admission, { controlBase, runId, session, capability }).capability).toBe(capability);
  });
}

test('DRIVER-SAFE-032 | URL fault permits are isolated from every other domain and never authorize business URL changes', () => {
  for (const action of ['set-url-transition-fault', 'clear-url-transition-fault',
    'hold-url-transition-reconciliation', 'release-url-transition-reconciliation', 'hold-url-route-worker', 'release-url-route-worker'])
    expect(controlCapability(action)).toBe('url-transition-control-v1');
  for (const action of ['confirm-page-url-change', 'reconcile-page-url-change', 'complete-url-transition', 'update-route-db'])
    expect(() => controlCapability(action)).toThrow('CONTROL_ACTION_NOT_ALLOWED');
  const controlBase = localTarget('http://127.0.0.1:9001'), runId = 'synthetic-run-0001';
  const session = { instanceId: 'i', runId, admissionGeneration: 'g' };
  for (const granted of ['fallback-control-v1', 'backup-control-v1', 'html-build-control-v1', 'log-maintenance-control-v1',
    'background-job-control-v1', 'restore-control-v1', 'log-deletion-control-v1']) {
    const admission = { arc10Verified: true, isolatedInfrastructure: true, capabilities: [granted],
      reviewedEvidenceId: 'e', controlOrigin: controlBase.origin, runId, controlInstanceId: 'i', admissionGeneration: 'g' };
    expect(() => validateControlAdmission(admission, { controlBase, runId, session, capability: 'url-transition-control-v1' })).toThrow('NOT_ADMITTED');
    admission.capabilities = ['url-transition-control-v1'];
    expect(() => validateControlAdmission(admission, { controlBase, runId, session, capability: granted })).toThrow('NOT_ADMITTED');
  }
});

test('DRIVER-SAFE-033 | service cleanup and content fault capabilities are distinct and cannot mutate business records', () => {
  for (const action of ['run-isolated-service-cleanup', 'advance-service-test-time', 'drain-isolated-service-workers'])
    expect(controlCapability(action)).toBe('service-quota-control-v1');
  for (const action of ['set-content-storage-fault', 'clear-content-storage-fault'])
    expect(controlCapability(action)).toBe('content-storage-control-v1');
  for (const action of ['save-open-editor', 'apply-shared-block-version', 'delete-request', 'delete-used-media', 'increase-production-quota'])
    expect(() => controlCapability(action)).toThrow('CONTROL_ACTION_NOT_ALLOWED');
  const controlBase = localTarget('http://127.0.0.1:9001'), runId = 'synthetic-run-0001';
  const session = { instanceId: 'i', runId, admissionGeneration: 'g' };
  const all = ['fallback-control-v1', 'backup-control-v1', 'html-build-control-v1', 'log-maintenance-control-v1',
    'background-job-control-v1', 'restore-control-v1', 'log-deletion-control-v1', 'url-transition-control-v1',
    'service-quota-control-v1', 'content-storage-control-v1'];
  for (const requested of ['service-quota-control-v1', 'content-storage-control-v1']) for (const granted of all) {
    if (requested === granted) continue;
    const admission = { arc10Verified: true, isolatedInfrastructure: true, capabilities: [granted],
      reviewedEvidenceId: 'e', controlOrigin: controlBase.origin, runId, controlInstanceId: 'i', admissionGeneration: 'g' };
    expect(() => validateControlAdmission(admission, { controlBase, runId, session, capability: requested })).toThrow('NOT_ADMITTED');
    admission.capabilities = [requested];
    expect(() => validateControlAdmission(admission, { controlBase, runId, session, capability: granted })).toThrow('NOT_ADMITTED');
  }
});

for (const [granted, requested] of [['backup-control-v1', 'restore-control-v1'], ['restore-control-v1', 'backup-control-v1'],
  ['log-maintenance-control-v1', 'log-deletion-control-v1'], ['log-deletion-control-v1', 'log-maintenance-control-v1']]) {
  test(`DRIVER-SAFE-026-${requested} | destructive restore and manual log faults require a distinct permit`, () => {
    const controlBase = localTarget('http://127.0.0.1:9001'), runId = 'synthetic-run-0001';
    const session = { instanceId: 'i', runId, admissionGeneration: 'g' };
    const admission = { arc10Verified: true, isolatedInfrastructure: true, capabilities: [granted],
      reviewedEvidenceId: 'e', controlOrigin: controlBase.origin, runId, controlInstanceId: 'i', admissionGeneration: 'g' };
    expect(() => validateControlAdmission(admission, { controlBase, runId, session, capability: requested })).toThrow('NOT_ADMITTED');
  });
}

for (const [granted, requested] of [['log-maintenance-control-v1', 'background-job-control-v1'],
  ['background-job-control-v1', 'log-maintenance-control-v1']]) {
  test(`DRIVER-SAFE-025-${requested} | log and worker fault permits are not interchangeable`, () => {
    const controlBase = localTarget('http://127.0.0.1:9001'), runId = 'synthetic-run-0001';
    const session = { instanceId: 'i', runId, admissionGeneration: 'g' };
    const admission = { arc10Verified: true, isolatedInfrastructure: true, capabilities: [granted],
      reviewedEvidenceId: 'e', controlOrigin: controlBase.origin, runId, controlInstanceId: 'i', admissionGeneration: 'g' };
    expect(() => validateControlAdmission(admission, { controlBase, runId, session, capability: requested })).toThrow('NOT_ADMITTED');
  });
}
test('DRIVER-SAFE-003 | 200 alone cannot prove accepted business operation', () => {
  const value = bindings(); delete value.operations.example.result.outcomes[0].marker;
  expect(() => validateBindings(value, base.href)).toThrow('ACTUAL_RESULT_MARKER_REQUIRED');
});

test('DRIVER-SAFE-027 | restore probe handoff is run-bound, new after invalidation and cannot seed persistent editor data', () => {
  const reply = { source: 'actual-fixture', runId: 'run-1', evidence: {
    preparationPhase: 'fresh-framework-session-after-restore-invalidation', rightsChanged: false, businessDataChanged: false,
    invalidationSequence: 10, sessionCreatedSequence: 11, frameworkEvidenceId: 'synthetic-evidence',
  }, data: { operationId: 'operation-1', grantRef: 'grant-1', actor: 'OWNER-RESTORE-PROBE', sessionCookieName: 'synthetic_session',
    actorState: { storageState: { cookies: [{ name: 'synthetic_session', value: 'new-synthetic-session', domain: '127.0.0.1', path: '/' }], origins: [] } } } };
  const scope = { runId: 'run-1', operationId: 'operation-1', grantRef: 'grant-1', base, previousCookieValues: new Set(['old-synthetic-session']) };
  expect(validateRestoreProbeSession(reply, scope)).toEqual(reply.data.actorState);
  for (const mutate of [
    r => { r.runId = 'old-run'; }, r => { r.data.operationId = 'old-operation'; }, r => { r.data.grantRef = 'old-grant'; },
    r => { r.data.actor = 'OWNER-CURRENT-SESSION'; }, r => { r.evidence.sessionCreatedSequence = 10; },
    r => { r.evidence.rightsChanged = true; }, r => { r.evidence.businessDataChanged = true; },
    r => { r.data.actorState.storageState.cookies[0].value = 'old-synthetic-session'; },
    r => { r.data.actorState.storageState.cookies[0].domain = 'elsewhere.invalid'; },
    r => { r.data.actorState.storageState.origins = [{ origin: base.origin, localStorage: [{ name: 'editor', value: 'synthetic' }] }]; },
  ]) {
    const bad = structuredClone(reply); mutate(bad);
    expect(() => validateRestoreProbeSession(bad, scope)).toThrow();
  }
});
test('DRIVER-SAFE-004 | missing profile list and result statuses rejected', () => {
  const value = bindings(); value.profiles = [];
  expect(() => validateBindings(value, base.href)).toThrow('INCOMPLETE');
  const other = bindings(); delete other.operations.example.result.outcomes[0].statuses;
  expect(() => validateBindings(other, base.href)).toThrow('STATUSES_REQUIRED');
});
for (const reference of ['constructor.name', '__proto__.secret', 'object.prototype.value', 'absent.field']) {
  test(`DRIVER-SAFE-ref-${reference} | no prototype traversal or missing-value defaults`, () => {
    expect(() => pick({ object: {} }, reference)).toThrow();
  });
}
test('DRIVER-SAFE-005 | payload/Unicode preserved, not normalized by adapter', () => {
  const payload = { name: '  李  ', comment: 'Строка\r\nЕщё\0', extra: false };
  expect(materialize({ $ref: 'args.payload' }, { args: { payload } })).toEqual(payload);
  const clone = materialize({ $ref: 'args.payload' }, { args: { payload } }); clone.name = 'other';
  expect(payload.name).toBe('  李  ');
});
test('DRIVER-SAFE-006 | fixture route lookup is constrained to local origin', () => {
  const scope = { args: { page: 'P-ONE' }, fixture: { routes: { 'P-ONE': { edit: '/local/page?id=one' } } } };
  expect(targetPath(base, { $lookup: 'fixture.routes', key: { $ref: 'args.page' }, field: 'edit' }, scope).href)
    .toBe(base.origin + '/local/page?id=one');
  scope.fixture.routes['P-ONE'].edit = '//estakada-service.ru/';
  expect(() => targetPath(base, { $lookup: 'fixture.routes', key: { $ref: 'args.page' }, field: 'edit' }, scope)).toThrow();
});
test('DRIVER-SAFE-007 | interpolated path values cannot become an external URL', () => {
  const url = targetPath(base, '/items/{args.id}', { args: { id: '//elsewhere.invalid/a?x=1' } });
  expect(url.origin).toBe(base.origin);
  expect(url.pathname).toContain('%2F%2Felsewhere.invalid');
});
for (const storage of [
  { cookies: [{ domain: 'estakada-service.ru', value: 'synthetic' }], origins: [] },
  { cookies: [], origins: [{ origin: 'https://elsewhere.invalid', localStorage: [] }] },
  { cookies: [], origins: [{ origin: base.origin, localStorage: [{ name: 'input', value: 'do-not-persist' }] }] },
]) {
  test(`DRIVER-SAFE-storage-${JSON.stringify(storage)} | reject foreign credentials or persistent fixture input`, () => {
    expect(() => validateStorage(storage, base)).toThrow();
  });
}
test('DRIVER-SAFE-008 | fixture bridge is not an application-mutation API', async () => {
  await expect(fixtureExchange(path.join(directory, 'fixture-transport-selfcheck.mjs'),
    { kind: 'act', targetOrigin: base.origin }, { root: directory })).rejects.toThrow('BUSINESS_MUTATION_FORBIDDEN');
});
test('DRIVER-SAFE-009 | cannot execute observer outside acceptance directory', async () => {
  await expect(fixtureExchange(path.join(directory, '..', 'docs', 'analytics-spec.md'),
    { kind: 'observe', targetOrigin: base.origin }, { root: directory })).rejects.toThrow('OUTSIDE_ACCEPTANCE');
});
const exchange = (transportMode, value, options) => fixtureExchange(path.join(directory, 'fixture-transport-selfcheck.mjs'),
  { kind: 'observe', targetOrigin: base.origin, runId: 'synthetic-run-0001', args: { transportMode, value } },
  { root: directory, ...options });

for (const mode of ['unchanged', 'post', 'state-change', 'ui-error']) {
  test(`DRIVER-SAFE-016-${mode} | preparation guard orchestration uses actual reads and always removes listener`, async () => {
    // Transport callbacks only: no application model or business result is simulated.
    const calls = []; let notify, reads = 0;
    const operation = guardUiPreparation({
      readState: async () => { calls.push('read'); return mode === 'state-change' && reads++ ? 'changed-observation' : 'initial-observation'; },
      subscribe: callback => { notify = callback; calls.push('subscribe'); return () => calls.push('unsubscribe'); },
      prepare: async () => { calls.push('prepare'); notify(mode === 'post' ? 'POST' : 'GET'); if (mode === 'ui-error') throw new Error('UI_FAILURE'); },
    });
    if (mode === 'unchanged') await operation;
    else await expect(operation).rejects.toThrow(mode === 'post' ? 'NETWORK_MUTATION' : mode === 'state-change' ? 'BUSINESS_MUTATION' : 'UI_FAILURE');
    expect(calls).toEqual(mode === 'ui-error' ? ['read', 'subscribe', 'prepare', 'unsubscribe'] : ['read', 'subscribe', 'prepare', 'read', 'unsubscribe']);
  });
}
test('DRIVER-SAFE-010 | framed Unicode survives chunk boundaries', async () => {
  const value = 'Привет🙂'.repeat(12000);
  const reply = await exchange('echo', value);
  expect(reply.source).toBe('transport-selfcheck');
  expect(reply.data).toBe(value);
});
for (const [mode, error] of [
  ['wrong-nonce', 'REPLY_MISMATCH'], ['wrong-run', 'REPLY_MISMATCH'], ['bad-json', 'INVALID_JSON'],
  ['stdout-flood', 'OUTPUT_LIMIT'], ['stderr-flood', 'STDERR_LIMIT'],
]) {
  test(`DRIVER-SAFE-${mode} | reject transport failure with no model fallback`, async () => {
    await expect(exchange(mode)).rejects.toThrow(error);
  });
}
test('DRIVER-SAFE-011 | stderr secret is not copied to reported error', async () => {
  try { await exchange('process-error'); throw new Error('Expected process failure'); }
  catch (error) {
    expect(error.message).toBe('DRIVER_FIXTURE_PROCESS_FAILED');
    expect(error.message).not.toContain('SYNTHETIC-SECRET');
  }
});
for (const mode of ['slow', 'ignore-term']) {
  test(`DRIVER-SAFE-012-${mode} | timeout waits for exit and own process group termination`, async () => {
    try { await exchange(mode, undefined, { timeout: 250 }); throw new Error('Expected timeout'); }
    catch (error) {
      expect(error.message).toBe('DRIVER_FIXTURE_TIMEOUT');
      expect(error.processClosed).toBe(true);
      expect(error.groupTerminated).toBe(true);
      expect(error.childPid).toBeGreaterThan(0);
      expect(() => process.kill(error.childPid, 0)).toThrow();
      if (mode === 'ignore-term') expect(error.forcedTermination).toBe(true);
    }
  });
}

test.describe('upload transport selfchecks, not website AC', () => {
  const runId = 'driver-upload-' + randomUUID(), otherId = 'driver-upload-' + randomUUID();
  const run = path.join(directory, 'generated-fixtures', runId), other = path.join(directory, 'generated-fixtures', otherId);
  const content = Buffer.from([0, 255, 13, 10, 60, 127, 80]);
  const descriptor = { path: path.join(run, 'source.bin'), name: 'probe.bin', mimeType: 'image/jpeg' };
  const created = [];
  test.beforeAll(() => {
    fs.mkdirSync(run, { recursive: true }); fs.mkdirSync(other, { recursive: true });
    for (const name of [descriptor.path, path.join(other, 'other.bin')]) { fs.writeFileSync(name, content); created.push(name); }
  });
  test.afterAll(() => {
    for (const name of created.reverse()) fs.unlinkSync(name);
    fs.rmdirSync(run); fs.rmdirSync(other);
  });
  test('DRIVER-UPLOAD-001 | exact bytes and declared MIME are not sanitized instead of the server', () => {
    const payload = filePayload(directory, runId, descriptor);
    expect(payload.buffer.equals(content)).toBe(true);
    expect(payload.name).toBe(descriptor.name); expect(payload.mimeType).toBe('image/jpeg');
  });
  test('DRIVER-UPLOAD-002 | another run cannot supply a file', () => {
    expect(() => filePayload(directory, runId, { ...descriptor, path: path.join(other, 'other.bin') })).toThrow('OUTSIDE_RUN');
  });
  test('DRIVER-UPLOAD-003 | package/source files cannot be uploaded as fixtures', () => {
    expect(() => filePayload(directory, runId, { ...descriptor, path: path.join(directory, 'package.json') })).toThrow('OUTSIDE_RUN');
  });
  test('DRIVER-UPLOAD-004 | symlink escaping this run is rejected', () => {
    const link = path.join(run, 'escape.bin'); fs.symlinkSync(path.join(other, 'other.bin'), link); created.push(link);
    expect(() => filePayload(directory, runId, { ...descriptor, path: link })).toThrow('OUTSIDE_RUN');
  });
  test('DRIVER-UPLOAD-005 | container resource guard is explicit, not a website rejection', () => {
    const large = path.join(run, 'large.bin'); fs.writeFileSync(large, 'x'); created.push(large); fs.truncateSync(large, transportFileLimit + 1);
    expect(() => filePayload(directory, runId, { ...descriptor, path: large })).toThrow('TRANSPORT_RESOURCE_LIMIT');
  });
  test('DRIVER-UPLOAD-006 | invalid run/descriptor cannot open arbitrary input', () => {
    expect(() => filePayload(directory, '../wrong', descriptor)).toThrow('UPLOAD_RUN_REQUIRED');
    expect(() => filePayload(directory, runId, {})).toThrow('DESCRIPTOR_REQUIRED');
  });
  test('DRIVER-UPLOAD-007 | multipart preserves fields and uses resolved bytes', () => {
    const payload = multipartPayload({ caption: '  Текст\r\n  ', flag: false }, { file: 'F-ONE' }, reference => {
      expect(reference).toBe('F-ONE'); return filePayload(directory, runId, descriptor);
    });
    expect(payload.caption).toBe('  Текст\r\n  '); expect(payload.flag).toBe(false);
    expect(payload.file.buffer.equals(content)).toBe(true);
  });
  test('DRIVER-UPLOAD-008 | no silent collision or JSON object instead of a form field', () => {
    expect(() => multipartPayload({ file: 'shadow' }, { file: 'F' }, () => ({}))).toThrow('FIELD_COLLISION');
    expect(() => multipartPayload({ data: {} }, { file: 'F' }, () => ({}))).toThrow('FIELD_TYPE');
    expect(() => multipartPayload({}, {}, () => ({}))).toThrow('FILES_REQUIRED');
  });
  test('DRIVER-UPLOAD-011 | multipart aggregate guard refuses the next file before reading its bytes', () => {
    const large = path.join(run, 'aggregate.bin'); fs.writeFileSync(large, 'x'); created.push(large); fs.truncateSync(large, 40 * 1024 * 1024);
    const observedBudgets = [];
    expect(() => multipartPayload({}, { first: 'F', second: 'F' }, (reference, remaining) => {
      observedBudgets.push(remaining);
      return filePayload(directory, runId, { ...descriptor, path: large }, { maxBytes: remaining });
    })).toThrow('TRANSPORT_RESOURCE_LIMIT');
    expect(observedBudgets).toEqual([64 * 1024 * 1024, 24 * 1024 * 1024]);
  });
  test('DRIVER-UPLOAD-012 | multipart count/field budget is finite without invoking file resolver', () => {
    const resolve = () => { throw new Error('Resolver must not run'); };
    const tooMany = Object.fromEntries(Array.from({ length: 33 }, (_, n) => [`file${n}`, 'F']));
    expect(() => multipartPayload({}, tooMany, resolve)).toThrow('TRANSPORT_RESOURCE_LIMIT');
    expect(() => multipartPayload({ text: 'x'.repeat(256 * 1024 + 1) }, { file: 'F' }, resolve)).toThrow('TRANSPORT_RESOURCE_LIMIT');
  });
  test('DRIVER-UPLOAD-009 | real Playwright multipart reaches an inert local byte receiver', async ({ request }) => {
    let captured;
    const server = http.createServer((req, res) => {
      const chunks = []; req.on('data', chunk => chunks.push(chunk));
      req.on('end', () => { captured = { contentType: req.headers['content-type'], bytes: Buffer.concat(chunks) }; res.writeHead(204); res.end(); });
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    try {
      const response = await request.post(`http://127.0.0.1:${server.address().port}/transport-only`, { maxRedirects: 0,
        multipart: multipartPayload({ caption: 'raw-value' }, { file: 'F' }, () => filePayload(directory, runId, descriptor)) });
      expect(response.status()).toBe(204);
      expect(captured.contentType).toMatch(/^multipart\/form-data; boundary=/);
      expect(captured.bytes.includes(content)).toBe(true);
      expect(captured.bytes.toString('utf8')).toContain('filename="probe.bin"');
    } finally { await new Promise(resolve => server.close(resolve)); }
  });
  test('DRIVER-UPLOAD-010 | actual browser file input receives original bytes on synthetic harness HTML', async ({ page }) => {
    await page.setContent('<label>Transport file<input type="file"></label>');
    await page.getByLabel('Transport file').setInputFiles(filePayload(directory, runId, descriptor));
    const actual = await page.getByLabel('Transport file').evaluate(async input => ({ name: input.files[0].name,
      type: input.files[0].type, bytes: [...new Uint8Array(await input.files[0].arrayBuffer())] }));
    expect(actual).toEqual({ name: 'probe.bin', type: 'image/jpeg', bytes: [...content] });
  });
});

test('DRIVER-REDACTION-001 | raw JSON detection happens before report masking and returns no secret', () => {
  const secret = 'SYNTHETIC-RAW-SECRET';
  const encoded = '{"logged":"\\u0053YNTHETIC-RAW-SECRET"}';
  const evidence = sensitiveValueCheck([encoded, JSON.parse(encoded)], [secret]);
  expect(evidence).toEqual({ checkedCount: 1, detected: true });
  expect(JSON.stringify(evidence)).not.toContain(secret);
  expect(sensitiveValueCheck('safe payload', [secret]).detected).toBe(false);
});

test('DRIVER-REDACTION-002 | inert parser detects encoded raw HTML/attribute leak without returning it', async ({ page }) => {
  const secret = 'SYNTHETIC-SECRET&RAW';
  const evidence = await page.evaluate(htmlSensitiveCheck, { source: '<input type="password" value="SYNTHETIC-SECRET&amp;RAW">', canaries: [secret] });
  expect(evidence).toEqual({ checkedCount: 1, detected: true });
  expect(JSON.stringify(evidence)).not.toContain(secret);
  expect((await page.evaluate(htmlSensitiveCheck, { source: '<p>safe text</p>', canaries: [secret] })).detected).toBe(false);
});
