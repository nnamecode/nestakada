import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { localTarget, routeUrl } from './test-support.js';

const forbidden = new Set(['__proto__', 'constructor', 'prototype']);
export function authSourceOrigin(profile, actor, declaredOrigin) {
  const expected = actor === 'LOGIN-B' ? 'http://host.docker.internal:8769' :
    ['LOGIN-A','LOGIN-A2'].includes(actor) ? 'http://host.docker.internal:8768' : undefined;
  if (profile !== 'auth-login-isolated-sources' || !expected || declaredOrigin !== expected)
    throw new Error('DRIVER_AUTH_SOURCE_SCOPE_REQUIRED');
  return new URL(expected);
}
export function authCsrfPreparation(profile, definition) {
  const expected = definition.path === '/manage/login/' ? '/manage/login/' :
    definition.path === '/manage/logout/' ? '/manage/' : undefined;
  if (profile !== 'auth-login-isolated-sources' || definition.kind !== 'http' || definition.method !== 'POST' ||
      definition.encoding !== 'form' || !expected || definition.freshCsrfPath !== expected)
    throw new Error('DRIVER_AUTH_CSRF_SCOPE_REQUIRED');
  return expected;
}
export const foundationProcessViews = new Set(['foundation-runtime-versions', 'foundation-settings',
  'foundation-isolation', 'foundation-dependency-evidence', 'foundation-deploy-check', 'foundation-audit-redaction']);
export function validateFoundationProcessRequest(view, args, profileName) {
  if (profileName !== 'local-foundation-isolated' || !foundationProcessViews.has(view) ||
    !args || typeof args !== 'object' || Array.isArray(args) || Object.keys(args).some(key => key !== 'profile') ||
    (Object.hasOwn(args, 'profile') && !['local-http', 'deployment-audit'].includes(args.profile)))
    throw new Error('DRIVER_FOUNDATION_PROCESS_SCOPE_REQUIRED');
}
export function foundationProcessData(reply, { view, args, profileName, runId }) {
  validateFoundationProcessRequest(view, args, profileName);
  if (reply?.source !== 'actual-process' || reply.runId !== runId || reply.evidence?.fixtureProfile !== profileName ||
    !reply.data || typeof reply.data !== 'object' || Array.isArray(reply.data))
    throw new Error('DRIVER_FOUNDATION_PROCESS_PROVENANCE_REQUIRED');
  return structuredClone(reply.data);
}
// Applied to the actual visitor context, independently of the inert response parser.
export function actorBrowserOptions(storageState, javaScriptEnabled = true) {
  if (typeof javaScriptEnabled !== 'boolean') throw new Error('DRIVER_JAVASCRIPT_POLICY_INVALID');
  return { storageState, javaScriptEnabled, serviceWorkers: 'block', acceptDownloads: false };
}
export function responseReportBody(status, raw, parsed) {
  if (status === 304) {
    if (raw.length) throw new Error('DRIVER_NOT_MODIFIED_BODY_NOT_EMPTY');
    return '';
  }
  return parsed || raw;
}
const backupActions = new Set(['run-isolated-backup-job', 'fail-isolated-backup-stage', 'block-isolated-backup-storage',
  'corrupt-isolated-backup-object', 'remove-isolated-backup-manifest-object', 'release-isolated-backup-barrier']);
const htmlBuildActions = new Set(['run-isolated-html-build', 'set-html-build-fault', 'clear-html-build-fault',
  'hold-html-build-phase', 'release-html-build-phase', 'drain-isolated-html-jobs']);
const logMaintenanceActions = new Set(['run-isolated-log-maintenance', 'hold-log-maintenance-phase',
  'release-log-maintenance-phase', 'set-log-storage-fault', 'clear-log-storage-fault', 'advance-log-test-time']);
const backgroundActions = new Set(['start-isolated-job-invocation', 'hold-isolated-job-phase',
  'release-isolated-job-barrier', 'fail-isolated-job-phase', 'clear-isolated-job-fault', 'advance-background-test-time']);
const restoreActions = new Set(['set-isolated-restore-fault', 'clear-isolated-restore-fault',
  'prepare-isolated-external-restore', 'confirm-isolated-external-restore',
  'confirm-isolated-restore-loss', 'complete-isolated-identity-recovery', 'prepare-isolated-restore-write-probe']);
const logDeletionActions = new Set(['set-log-delete-file-fault', 'clear-log-delete-file-fault']);
const urlTransitionActions = new Set(['set-url-transition-fault', 'clear-url-transition-fault',
  'hold-url-transition-reconciliation', 'release-url-transition-reconciliation',
  'hold-url-route-worker', 'release-url-route-worker']);
const serviceQuotaActions = new Set(['run-isolated-service-cleanup', 'advance-service-test-time', 'drain-isolated-service-workers']);
const contentStorageActions = new Set(['set-content-storage-fault', 'clear-content-storage-fault']);
export const infrastructureControlActions = new Set([
  'advance-infrastructure-time', 'stop-isolated-component', 'start-isolated-component',
  'block-readiness-channel', 'unblock-readiness-channel', 'replay-captured-readiness-result',
  'block-independent-head', 'restart-gate-with-closed-start-barrier',
  'rollback-isolated-app-edge-to-valid-old-snapshot', 'hold-front-switch-confirmation',
  'release-front-switch-confirmation', 'block-telegram-transport', 'fail-front-switch-application',
  'hold-response-after-gate-admission', 'release-admitted-response', 'stop-isolated-host-zone',
  ...backupActions, ...htmlBuildActions, ...logMaintenanceActions, ...backgroundActions, ...restoreActions, ...logDeletionActions, ...urlTransitionActions, ...serviceQuotaActions, ...contentStorageActions,
]);
export function controlCapability(action) {
  if (backupActions.has(action)) return 'backup-control-v1';
  if (htmlBuildActions.has(action)) return 'html-build-control-v1';
  if (logMaintenanceActions.has(action)) return 'log-maintenance-control-v1';
  if (backgroundActions.has(action)) return 'background-job-control-v1';
  if (restoreActions.has(action)) return 'restore-control-v1';
  if (logDeletionActions.has(action)) return 'log-deletion-control-v1';
  if (urlTransitionActions.has(action)) return 'url-transition-control-v1';
  if (serviceQuotaActions.has(action)) return 'service-quota-control-v1';
  if (contentStorageActions.has(action)) return 'content-storage-control-v1';
  if (infrastructureControlActions.has(action)) return 'fallback-control-v1';
  throw new Error('DRIVER_CONTROL_ACTION_NOT_ALLOWED');
}
export function pick(value, reference) {
  if (typeof reference !== 'string' || !reference || reference.length > 300)
    throw new Error('DRIVER_INVALID_REFERENCE');
  let current = value;
  for (const key of reference.split('.')) {
    if (forbidden.has(key) || current === null || typeof current !== 'object' || !Object.hasOwn(current, key))
      throw new Error('DRIVER_REFERENCE_NOT_AVAILABLE');
    current = current[key];
  }
  return structuredClone(current);
}

export function materialize(template, scope) {
  if (Array.isArray(template)) return template.map(item => materialize(item, scope));
  if (template && typeof template === 'object') {
    if (Object.keys(template).length === 1 && Object.hasOwn(template, '$ref')) return pick(scope, template.$ref);
    if (Object.hasOwn(template, '$lookup')) {
      if (Object.keys(template).some(key => !['$lookup', 'key', 'field'].includes(key))) throw new Error('DRIVER_INVALID_LOOKUP');
      const table = pick(scope, template.$lookup), key = materialize(template.key, scope);
      if (!['string', 'number'].includes(typeof key) || forbidden.has(String(key)) ||
        !table || typeof table !== 'object' || !Object.hasOwn(table, key)) throw new Error('DRIVER_LOOKUP_NOT_AVAILABLE');
      return template.field ? pick(table[key], template.field) : structuredClone(table[key]);
    }
    const result = Object.create(null);
    for (const [key, value] of Object.entries(template)) {
      if (forbidden.has(key)) throw new Error('DRIVER_UNSAFE_KEY');
      result[key] = materialize(value, scope);
    }
    return result;
  }
  return template;
}

export function targetPath(base, template, scope) {
  if (template && typeof template === 'object') return routeUrl(base, materialize(template, scope));
  if (typeof template !== 'string') throw new Error('DRIVER_INVALID_PATH_TEMPLATE');
  const resolved = template.replace(/\{([a-zA-Z0-9_.-]+)\}/g, (_, reference) => {
    const value = pick(scope, reference);
    if (!['string', 'number'].includes(typeof value)) throw new Error('DRIVER_INVALID_PATH_VALUE');
    return encodeURIComponent(String(value));
  });
  if (/[{}]/.test(resolved)) throw new Error('DRIVER_INVALID_PATH_TEMPLATE');
  return routeUrl(base, resolved);
}

export function validateBindings(value, baseURL) {
  const base = localTarget(baseURL);
  if (base.port === '8765') throw new Error('DRIVER_PREVIEW_TARGET_FORBIDDEN');
  if (value?.schema !== 'isolated-ui-http-v1' || value.targetOrigin !== base.origin)
    throw new Error('DRIVER_BINDINGS_ORIGIN_OR_SCHEMA_MISMATCH');
  if (!Array.isArray(value.profiles) || !value.profiles.length || !value.operations || !value.observations)
    throw new Error('DRIVER_BINDINGS_INCOMPLETE');
  if (!value.profiles.every(name => typeof name === 'string' && /^[a-zA-Z0-9_-]+$/.test(name)))
    throw new Error('DRIVER_INVALID_PROFILE');
  for (const [name, observation] of Object.entries(value.observations)) {
    if ((foundationProcessViews.has(name) || observation.kind === 'process-read') &&
      (!foundationProcessViews.has(name) || observation.kind !== 'process-read' || Object.keys(observation).some(key => key !== 'kind')))
      throw new Error('DRIVER_FOUNDATION_PROCESS_DECLARATION_INVALID');
    if ((name === 'editor-memory-state' || observation.kind === 'ui-memory') &&
      (name !== 'editor-memory-state' || observation.kind !== 'ui-memory' || Object.keys(observation).some(key => key !== 'kind')))
      throw new Error('DRIVER_MEMORY_OBSERVATION_INVALID');
  }
  for (const profile of ['page-history-restore', 'controlled-session-boundary']) {
    if (!value.profiles.includes(profile)) continue;
    const setup = value.profileSetups?.[profile];
    if (!setup?.actors?.some(actor => actor.actor === 'S-EDIT' && actor.steps?.some(step => step.kind === 'goto') && actor.steps?.some(step => step.kind === 'fill')))
      throw new Error('DRIVER_REVIEWED_UI_PREPARATION_REQUIRED');
    if (profile === 'controlled-session-boundary' && setup.finalizeFixture !== true)
      throw new Error('DRIVER_SESSION_AFTER_UI_FINALIZATION_REQUIRED');
  }
  for (const [name, operation] of Object.entries(value.operations)) {
    if (forbidden.has(name) || !['http', 'ui'].includes(operation.kind)) throw new Error('DRIVER_INVALID_OPERATION');
    if (operation.result?.format === 'ui') {
      if (operation.kind !== 'ui' || !['type-unsaved-text', 'stage-page-version-restore'].includes(name) ||
        !operation.result.probes?.length || operation.result.outcomes)
        throw new Error('DRIVER_UI_ONLY_DECLARATION_INVALID');
      for (const probe of operation.result.probes) if (!probe.locator || !['input', 'text', 'checked'].includes(probe.read) || !Object.hasOwn(probe, 'expected'))
        throw new Error('DRIVER_ACTUAL_UI_PROBE_REQUIRED');
    } else {
    if (!operation.result || !Array.isArray(operation.result.outcomes) || !operation.result.outcomes.length)
      throw new Error('DRIVER_RESULT_RULES_REQUIRED');
    if (!['html', 'json'].includes(operation.result.format)) throw new Error('DRIVER_RESULT_FORMAT_REQUIRED');
    for (const rule of operation.result.outcomes) {
      if (!['accepted', 'denied', 'conflict', 'pending', 'not-modified'].includes(rule.outcome)) throw new Error('DRIVER_INVALID_OUTCOME');
      if (!Array.isArray(rule.statuses) || !rule.statuses.length || rule.statuses.some(status => !Number.isInteger(status) || status < 100 || status > 599))
        throw new Error('DRIVER_RESULT_STATUSES_REQUIRED');
      // 2xx/login/static HTML is not enough to claim a successful business operation.
      if (rule.outcome === 'not-modified') {
        if (operation.kind !== 'http' || operation.method !== 'GET' || operation.followRedirectGet || operation.result.format !== 'html' ||
          !Object.keys(operation.headers || {}).some(key => key.toLowerCase() === 'if-none-match') ||
          rule.statuses.length !== 1 || rule.statuses[0] !== 304 || rule.marker || rule.jsonEquals)
          throw new Error('DRIVER_CONDITIONAL_GET_REQUIRED');
      } else if (!rule.marker && !rule.jsonEquals) {
        if (['accepted', 'pending'].includes(rule.outcome) || !Array.isArray(rule.statuses) || !rule.statuses.length ||
          rule.statuses.some(status => ![400, 401, 403, 404, 409, 422, 429].includes(status)))
          throw new Error('DRIVER_ACTUAL_RESULT_MARKER_REQUIRED');
      }
    }
    }
    if (operation.kind === 'http' && !['GET', 'POST'].includes(operation.method))
      throw new Error('DRIVER_HTTP_METHOD_NOT_CONFIGURED');
    if (operation.kind === 'ui') {
      if (!Array.isArray(operation.steps) || !operation.steps.length) throw new Error('DRIVER_UI_STEPS_REQUIRED');
      for (const step of operation.steps) if (['click', 'setInputFiles'].includes(step.kind) && step.responsePath && !['GET', 'POST'].includes(step.responseMethod))
        throw new Error('DRIVER_UI_RESPONSE_METHOD_REQUIRED');
    }
  }
  let controlBase;
  if (value.controls) {
    controlBase = localTarget(value.controlOrigin);
    if (controlBase.origin === base.origin || controlBase.port === '8765') throw new Error('DRIVER_INDEPENDENT_CONTROL_ORIGIN_REQUIRED');
    for (const [action, operation] of Object.entries(value.controls)) {
      if (!infrastructureControlActions.has(action) || operation.kind !== 'http' || operation.method !== 'POST' || operation.followRedirectGet)
        throw new Error('DRIVER_CONTROL_ACTION_NOT_ALLOWED');
    }
    validateBindings({ schema: value.schema, targetOrigin: controlBase.origin, profiles: ['test-control'],
      operations: value.controls, observations: {} }, controlBase.href);
  }
  return { base, controlBase, bindings: value };
}

// Orchestration only: readState must read the actual application DB, never expected data.
export async function guardUiPreparation({ readState, prepare, subscribe }) {
  const before = await readState();
  let mutationSeen = false;
  const unsubscribe = subscribe(method => { if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) mutationSeen = true; });
  try {
    await prepare();
    const after = await readState();
    if (mutationSeen) throw new Error('DRIVER_UI_PREPARATION_NETWORK_MUTATION');
    if (after !== before) throw new Error('DRIVER_UI_PREPARATION_BUSINESS_MUTATION');
  } finally { unsubscribe(); }
}

export function validateControlAdmission(admission, { controlBase, runId, session, capability = 'fallback-control-v1' }) {
  if (!['fallback-control-v1', 'backup-control-v1', 'html-build-control-v1', 'log-maintenance-control-v1', 'background-job-control-v1', 'restore-control-v1', 'log-deletion-control-v1', 'url-transition-control-v1', 'service-quota-control-v1', 'content-storage-control-v1'].includes(capability)) throw new Error('DRIVER_CONTROL_CAPABILITY_NOT_SUPPORTED');
  if (admission?.arc10Verified !== true || admission.isolatedInfrastructure !== true ||
    !Array.isArray(admission.capabilities) || !admission.capabilities.includes(capability) ||
    !admission.reviewedEvidenceId || admission.controlOrigin !== controlBase.origin || admission.runId !== runId ||
    typeof admission.controlInstanceId !== 'string' || !admission.controlInstanceId ||
    typeof admission.admissionGeneration !== 'string' || !admission.admissionGeneration ||
    session?.instanceId !== admission.controlInstanceId || session.runId !== runId ||
    session.admissionGeneration !== admission.admissionGeneration) throw new Error('DRIVER_CONTROL_NOT_ADMITTED');
  return { runId, instanceId: admission.controlInstanceId, admissionGeneration: admission.admissionGeneration, capability };
}

export function validateControlReply(headers, correlation) {
  for (const [header, key] of [['x-estakada-test-run', 'runId'], ['x-estakada-test-operation', 'operationId'],
    ['x-estakada-test-instance', 'instanceId'], ['x-estakada-test-admission', 'admissionGeneration'], ['x-estakada-test-capability', 'capability']]) {
    if (!correlation[key] || headers[header] !== correlation[key]) throw new Error('DRIVER_CONTROL_CORRELATION_NOT_CONFIRMED');
  }
}

export function validateStorage(storage, base) {
  if (!storage || !Array.isArray(storage.cookies) || !Array.isArray(storage.origins))
    throw new Error('DRIVER_ACTOR_STORAGE_REQUIRED');
  const hostname = base.hostname.replace(/^\[|\]$/g, '');
  for (const cookie of storage.cookies) {
    if (String(cookie.domain).replace(/^\./, '') !== hostname) throw new Error('DRIVER_FOREIGN_COOKIE');
  }
  for (const origin of storage.origins) {
    if (origin.origin !== base.origin) throw new Error('DRIVER_FOREIGN_STORAGE');
    if (origin.localStorage?.length) throw new Error('DRIVER_PERSISTENT_FIXTURE_STORAGE_FORBIDDEN');
  }
  return storage;
}

// A fixture credential handoff, not a way to create users/rights or simulate a restore result.
export function validateRestoreProbeSession(reply, { runId, operationId, grantRef, base, previousCookieValues }) {
  const e = reply?.evidence, d = reply?.data;
  if (reply?.source !== 'actual-fixture' || reply.runId !== runId || d?.operationId !== operationId ||
    d?.grantRef !== grantRef || d?.actor !== 'OWNER-RESTORE-PROBE' ||
    e?.preparationPhase !== 'fresh-framework-session-after-restore-invalidation' ||
    e?.rightsChanged !== false || e?.businessDataChanged !== false ||
    !Number.isSafeInteger(e?.invalidationSequence) || e.invalidationSequence < 0 || !Number.isSafeInteger(e?.sessionCreatedSequence) ||
    e.sessionCreatedSequence <= e.invalidationSequence || typeof e?.frameworkEvidenceId !== 'string' || !e.frameworkEvidenceId)
    throw new Error('DRIVER_RESTORE_PROBE_EVIDENCE_REQUIRED');
  validateStorage(d.actorState?.storageState, base);
  if (d.actorState.storageState.origins.length) throw new Error('DRIVER_RESTORE_PROBE_PERSISTENT_STORAGE_FORBIDDEN');
  const sessionCookies = d.actorState.storageState.cookies.filter(cookie => cookie.name === d.sessionCookieName);
  if (typeof d.sessionCookieName !== 'string' || !d.sessionCookieName || sessionCookies.length !== 1 ||
    typeof sessionCookies[0].value !== 'string' || sessionCookies[0].value.length < 8 ||
    previousCookieValues.has(sessionCookies[0].value)) throw new Error('DRIVER_RESTORE_PROBE_FRESH_COOKIE_REQUIRED');
  return structuredClone(d.actorState);
}

// Only a reviewed test fixture/observer entrypoint under the acceptance directory.
// This bridge prepares fixtures or reads actual state; it must not implement act/business rules.
export async function fixtureExchange(entrypoint, request, { root, timeout = 8000 } = {}) {
  if (process.platform !== 'linux') throw new Error('DRIVER_FIXTURE_REQUIRES_LINUX_CONTAINER');
  const realRoot = fs.realpathSync(root);
  let realEntry;
  try { realEntry = fs.realpathSync(entrypoint); } catch { throw new Error('FIXTURE_IO_NOT_IMPLEMENTED'); }
  if (!realEntry.startsWith(realRoot + path.sep) || path.extname(realEntry) !== '.mjs')
    throw new Error('DRIVER_FIXTURE_ENTRY_OUTSIDE_ACCEPTANCE');
  if (!['reset', 'observe', 'close'].includes(request.kind)) throw new Error('DRIVER_FIXTURE_BUSINESS_MUTATION_FORBIDDEN');
  const nonce = randomBytes(24).toString('hex');
  const envelope = { ...request, protocol: 'estakada-fixture-v1', nonce };
  const input = JSON.stringify(envelope);
  if (Buffer.byteLength(input) > 256 * 1024) throw new Error('DRIVER_FIXTURE_INPUT_LIMIT');
  return new Promise((resolve, reject) => {
    let settled = false, closed = false, stopping, forced = false, size = 0, stderrSize = 0, output = '';
    let forceTimer, stopTimer, pollTimer;
    // Own process group; bridge must not detach grandchildren into other groups.
    const child = spawn(process.execPath, [realEntry], { shell: false, windowsHide: true, detached: true,
      stdio: ['pipe', 'pipe', 'pipe'], env: { LANG: 'C.UTF-8' } });
    const groupExists = () => {
      if (!child.pid) return false;
      try { process.kill(-child.pid, 0); return true; } catch (error) { return error.code !== 'ESRCH'; }
    };
    const signal = name => { if (child.pid) { try { process.kill(-child.pid, name); } catch {} } };
    const finish = (error, result) => {
      if (settled) return;
      settled = true;
      for (const id of [timer, forceTimer, stopTimer, pollTimer]) clearTimeout(id);
      if (error) {
        const failure = new Error(error);
        failure.childPid = child.pid; failure.processClosed = closed;
        failure.groupTerminated = !groupExists(); failure.forcedTermination = forced;
        reject(failure);
      } else resolve(result);
    };
    const pollStop = () => {
      if (settled) return;
      if (closed && !groupExists()) return finish(stopping);
      pollTimer = setTimeout(pollStop, 20);
    };
    const stop = reason => {
      if (settled || stopping) return;
      stopping = reason; clearTimeout(timer); signal('SIGTERM');
      forceTimer = setTimeout(() => { forced = true; signal('SIGKILL'); }, 100);
      stopTimer = setTimeout(() => finish('DRIVER_FIXTURE_TERMINATION_UNCONFIRMED'), 1500);
      pollStop();
    };
    const timer = setTimeout(() => stop('DRIVER_FIXTURE_TIMEOUT'), timeout);
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', chunk => {
      size += Buffer.byteLength(chunk);
      if (size > 1024 * 1024) return stop('DRIVER_FIXTURE_OUTPUT_LIMIT');
      output += chunk;
    });
    // Never include arbitrary stderr/DSN/token/HTML in a Playwright error or report.
    child.stderr.on('data', chunk => {
      stderrSize += chunk.length;
      if (stderrSize > 1024 * 1024) stop('DRIVER_FIXTURE_STDERR_LIMIT');
    });
    child.stdin.on('error', () => stop('DRIVER_FIXTURE_STDIN_FAILED'));
    child.on('error', () => stop('DRIVER_FIXTURE_START_FAILED'));
    child.on('close', code => {
      closed = true;
      if (settled) return;
      if (stopping) return;
      if (code !== 0) return stop('DRIVER_FIXTURE_PROCESS_FAILED');
      if (groupExists()) return stop('DRIVER_FIXTURE_DESCENDANTS_REMAIN');
      let reply;
      try { reply = JSON.parse(output); } catch { return stop('DRIVER_FIXTURE_INVALID_JSON'); }
      if (reply.protocol !== envelope.protocol || reply.nonce !== nonce || reply.ok !== true ||
        reply.targetOrigin !== request.targetOrigin ||
        (request.runId && reply.runId !== request.runId)) return stop('DRIVER_FIXTURE_REPLY_MISMATCH');
      finish(null, reply);
    });
    child.stdin.end(input);
  });
}
