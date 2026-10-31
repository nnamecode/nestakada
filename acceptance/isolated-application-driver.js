import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { chromium } from '@playwright/test';
import { filePayload, multipartPayload } from './upload-support.js';
import { checkedCanaries, sensitiveValueCheck, htmlSensitiveCheck } from './response-safety.js';
import { inspectBrowserPersistence } from './browser-memory.js';
import { authSourceOrigin, authCsrfPreparation } from './driver-safety.js';
import { actorBrowserOptions, responseReportBody, validateFoundationProcessRequest, foundationProcessData, materialize, pick, targetPath, validateBindings, validateStorage, validateRestoreProbeSession, fixtureExchange, guardUiPreparation, infrastructureControlActions, controlCapability, validateControlAdmission, validateControlReply } from './driver-safety.js';

export const driverKind = 'real-isolated-application-v1';
const directory = fileURLToPath(new URL('.', import.meta.url));
const fixtureEntry = path.join(directory, 'local-fixture-bridge.mjs');

// Optional filename is used only by the read-only loader selfcheck. createDriver uses the fixed default.
export function loadBindings(filename = path.join(directory, 'local-bindings.json')) {
  if (!fs.existsSync(filename)) throw new Error('DRIVER_BINDINGS_NOT_CONFIGURED');
  if (fs.statSync(filename).size > 128 * 1024) throw new Error('DRIVER_BINDINGS_SIZE_LIMIT');
  try { return JSON.parse(fs.readFileSync(filename, 'utf8')); }
  catch { throw new Error('DRIVER_BINDINGS_INVALID_JSON'); }
}
const atPath = (data, reference) => pick({ response: data }, `response.${reference}`);

export async function createDriver({ baseURL, javaScriptEnabled = true }) {
  actorBrowserOptions(undefined, javaScriptEnabled);
  const { base, controlBase, bindings } = validateBindings(loadBindings(), baseURL);
  if (!fs.existsSync(fixtureEntry)) throw new Error('FIXTURE_IO_NOT_IMPLEMENTED');
  let browser, browserPromise, parserPromise, parserContext, parser, fixture, runId, closed = false, poisoned = false, resetting = false, active = 0;
  const actors = new Map(), actorInitializations = new Map(), secrets = new Set();
  const authRequestIds = new Map();
  let controlContext, profileName, provisioningRestoreProbe = false;
  const scrub = text => {
    let result = String(text);
    for (const value of secrets) if (value.length >= 4) result = result.replaceAll(value, '[REDACTED]');
    return result;
  };
  const addSecrets = value => {
    if (typeof value === 'string') secrets.add(value);
    else if (Array.isArray(value)) value.forEach(addSecrets);
    else if (value && typeof value === 'object') Object.values(value).forEach(addSecrets);
  };
  function ready() {
    if (closed || poisoned || resetting || !fixture || !runId) throw new Error('DRIVER_FIXTURE_NOT_READY');
  }
  async function exchange(request) {
    try { return await fixtureExchange(fixtureEntry, request, { root: directory }); }
    catch (error) {
      if (error.message === 'DRIVER_FIXTURE_TERMINATION_UNCONFIRMED') poisoned = true;
      throw error;
    }
  }
  async function ensureBrowser() {
    browserPromise ??= chromium.launch({ headless: true });
    browser = await browserPromise;
    parserPromise ??= (async () => {
      parserContext = await browser.newContext({ javaScriptEnabled: false, serviceWorkers: 'block' });
      await parserContext.route('**/*', route => route.abort());
      await parserContext.routeWebSocket('**/*', socket => socket.close());
      return parserContext.newPage();
    })();
    parser = await parserPromise;
  }
  async function actorContext(name, preparing = false) {
    if (name === 'OWNER-RESTORE-PROBE' && provisioningRestoreProbe) throw new Error('DRIVER_RESTORE_PROBE_PROVISIONING');
    if (preparing) {
      if (closed || poisoned || !resetting || !fixture || !runId) throw new Error('DRIVER_FIXTURE_NOT_READY');
    } else ready();
    if (!Object.hasOwn(fixture.actors, name)) throw new Error('DRIVER_ACTOR_NOT_PROVISIONED');
    if (actors.has(name)) return actors.get(name);
    if (!actorInitializations.has(name)) actorInitializations.set(name, (async () => {
      await ensureBrowser();
      const storage = validateStorage(fixture.actors[name].storageState, base);
      const context = await browser.newContext(actorBrowserOptions(storage, javaScriptEnabled));
      await context.route('**/*', route => {
        const url = new URL(route.request().url());
        return url.origin === base.origin ? route.continue() : route.abort();
      });
      await context.routeWebSocket('**/*', socket => socket.close());
      const actor = { context, page: await context.newPage(), name };
      actors.set(name, actor);
      return actor;
    })());
    try { return await actorInitializations.get(name); }
    finally { actorInitializations.delete(name); }
  }
  async function domSnapshot(html, resultDefinition) {
    await ensureBrowser();
    return parser.evaluate(({ source, definition }) => {
      const doc = new DOMParser().parseFromString(source, 'text/html');
      const select = rule => {
        const nodes = [...doc.querySelectorAll(rule.selector)];
        const values = nodes.map(node => rule.attribute ? node.getAttribute(rule.attribute)
          : rule.read === 'value' ? node.value : (node.textContent || '').trim());
        return rule.all ? values : values[0];
      };
      const markers = definition.outcomes.map(rule => !rule.marker ? false :
        [...doc.querySelectorAll(rule.marker.selector)].some(node => rule.marker.text === undefined ||
          (node.textContent || '').trim() === rule.marker.text));
      const fields = {};
      for (const [name, rule] of Object.entries(definition.fields || {})) {
        if (rule.selector) fields[name] = select(rule);
        else if (rule.presentFields) fields[name] = Object.entries(rule.presentFields)
          .filter(([, selector]) => doc.querySelector(selector)).map(([field]) => field);
      }
      // Preserve evidence of disclosure while suppressing ordinary password/token inputs.
      for (const input of doc.querySelectorAll('input[type="password"], input[name*="csrf" i], input[name*="token" i]'))
        input.setAttribute('value', '[REDACTED]');
      return { markers, fields, body: doc.documentElement.outerHTML };
    }, { source: html, definition: resultDefinition });
  }
  async function decode(response, definition) {
    if (!response) throw new Error('DRIVER_RESPONSE_NOT_OBSERVED');
    const status = response.status();
    const raw = await response.body();
    if (raw.length > 2 * 1024 * 1024) throw new Error('DRIVER_RESPONSE_PARSE_LIMIT');
    const text = raw.toString('utf8');
    const canaries = checkedCanaries(fixture?.logSensitiveCanaries || []);
    let snapshot, data;
    if (status === 304 && text.length) throw new Error('DRIVER_NOT_MODIFIED_BODY_NOT_EMPTY');
    if (definition.format === 'json') {
      try { data = JSON.parse(text); } catch { throw new Error('DRIVER_EXPECTED_JSON_RESPONSE'); }
    } else snapshot = await domSnapshot(text, definition);
    let sensitiveCanaryCheck;
    if (definition.format === 'json') sensitiveCanaryCheck = sensitiveValueCheck([text, data], canaries);
    else {
      await ensureBrowser();
      // Parse the original response before returning any scrubbed body/fields.
      sensitiveCanaryCheck = await parser.evaluate(htmlSensitiveCheck, { source: text, canaries });
    }
    const matched = definition.outcomes.filter((rule, index) => {
      if (!rule.statuses?.includes(status)) return false;
      if (rule.jsonEquals) return definition.format === 'json' &&
        JSON.stringify(atPath(data, rule.jsonEquals.path)) === JSON.stringify(rule.jsonEquals.value);
      return rule.marker ? snapshot?.markers[index] === true : true;
    });
    if (matched.length !== 1) throw new Error('DRIVER_RESULT_AMBIGUOUS_OR_UNRECOGNIZED');
    const fields = snapshot?.fields || {};
    if (definition.format === 'json') for (const [name, rule] of Object.entries(definition.fields || {}))
      if (!rule.header) fields[name] = atPath(data, rule.path);
    for (const [name, rule] of Object.entries(definition.fields || {})) if (rule.header) {
      const header = rule.header.toLowerCase();
      if (!['cache-control', 'vary', 'content-type', 'location', 'etag', 'last-modified', 'x-content-type-options', 'content-disposition'].includes(header))
        throw new Error('DRIVER_RESPONSE_HEADER_NOT_ALLOWED');
      fields[name] = response.headers()[header];
    }
    for (const [name, rule] of Object.entries(definition.fields || {})) if (rule.secret) addSecrets(fields[name]);
    return { ...fields, outcome: matched[0].outcome, body: scrub(responseReportBody(status, text, snapshot?.body)), observedStatus: status,
      sensitiveCanaryCheck };
  }
  async function http(actor, definition, scope, transportBase = base, correlation) {
    const url = targetPath(transportBase, definition.path, scope);
    const headers = materialize(definition.headers || {}, scope);
    const allowedHeaders = new Set(['x-csrftoken', 'content-type', 'x-requested-with', 'if-none-match', 'if-modified-since']);
    if (Object.keys(headers).some(key => !allowedHeaders.has(key.toLowerCase()))) throw new Error('DRIVER_HEADER_NOT_ALLOWED');
    if (correlation) {
      headers['x-estakada-test-run'] = correlation.runId;
      headers['x-estakada-test-operation'] = correlation.operationId;
      headers['x-estakada-test-instance'] = correlation.instanceId;
      headers['x-estakada-test-admission'] = correlation.admissionGeneration;
      headers['x-estakada-test-capability'] = correlation.capability;
    }
    const options = { method: definition.method, headers, maxRedirects: 0, timeout: 8000, failOnStatusCode: false };
    if (definition.encoding === 'multipart') {
      if (definition.method !== 'POST' || Object.keys(headers).some(key => key.toLowerCase() === 'content-type'))
        throw new Error('DRIVER_MULTIPART_METHOD_OR_BOUNDARY_INVALID');
      options.multipart = multipartPayload(materialize(definition.body || {}, scope), materialize(definition.files || {}, scope), (reference, remaining) => {
        if (!Object.hasOwn(fixture.uploads || {}, reference)) throw new Error('DRIVER_UPLOAD_REFERENCE_NOT_AVAILABLE');
        return filePayload(directory, runId, fixture.uploads[reference], { maxBytes: remaining });
      });
    }
    if (definition.body !== undefined) {
      if (definition.method === 'GET') throw new Error('DRIVER_GET_BODY_FORBIDDEN');
      const body = materialize(definition.body, scope);
      if (definition.encoding === 'multipart') { /* fields already included with the actual file bytes */ }
      else if (definition.encoding === 'form') options.form = body;
      else if (definition.encoding === 'json') options.data = body;
      else throw new Error('DRIVER_BODY_ENCODING_REQUIRED');
    }
    if (definition.freshCsrfPath !== undefined) {
      const csrfPath = authCsrfPreparation(profileName, definition);
      const preparation = await actor.context.request.get(new URL(csrfPath, transportBase).href, { maxRedirects: 0, timeout: 8000 });
      if (preparation.status() !== 200) throw new Error('DRIVER_AUTH_CSRF_GET_FAILED');
      const html = await preparation.text();
      const token = await parser.evaluate(source => new DOMParser().parseFromString(source,'text/html')
        .querySelector('input[name="csrfmiddlewaretoken"]')?.value, html);
      if (typeof token !== 'string' || !/^[A-Za-z0-9]{64}$/u.test(token)) throw new Error('DRIVER_AUTH_CSRF_TOKEN_REQUIRED');
      addSecrets(token); options.form = { ...(options.form || {}), csrfmiddlewaretoken: token };
    }
    let response = await actor.context.request.fetch(url.href, options);
    if (profileName === 'auth-login-isolated-sources' && definition.path === '/manage/login/' && definition.method === 'POST') {
      const requestId = response.headers()['x-request-id'];
      if (typeof requestId !== 'string' || !/^[a-zA-Z0-9-]{16,128}$/u.test(requestId)) throw new Error('DRIVER_AUTH_RESPONSE_CORRELATION_REQUIRED');
      authRequestIds.set(transportBase.origin, requestId);
    }
    if (correlation) validateControlReply(response.headers(), correlation);
    if ([301, 302, 303, 307, 308].includes(response.status())) {
      const location = response.headers().location;
      if (!location) throw new Error('DRIVER_REDIRECT_WITHOUT_LOCATION');
      const next = new URL(location, url);
      if (next.origin !== transportBase.origin || next.username || next.password) throw new Error('DRIVER_EXTERNAL_REDIRECT');
      if (!definition.followRedirectGet || ![301, 302, 303].includes(response.status()))
        throw new Error('DRIVER_REDIRECT_NOT_CONFIGURED');
      response = await actor.context.request.get(next.href, { maxRedirects: 0, timeout: 8000 });
    }
    return decode(response, definition.result);
  }
  const locate = (page, locator) => {
    if (locator.role) return page.getByRole(locator.role, { name: locator.name, exact: true });
    if (locator.label) return page.getByLabel(locator.label, { exact: true });
    if (locator.testId) return page.getByTestId(locator.testId);
    throw new Error('DRIVER_UI_LOCATOR_REQUIRED');
  };
  async function steps(actor, program, scope, preparing = false) {
    let response;
    for (const step of program || []) {
      if (preparing && !['goto', 'fill', 'check'].includes(step.kind)) throw new Error('DRIVER_PREPARATION_STEP_NOT_ALLOWED');
      if (step.kind === 'goto') response = await actor.page.goto(targetPath(base, step.path, scope).href, { waitUntil: 'domcontentloaded', timeout: 8000 });
      else if (step.kind === 'fill') {
        response = undefined;
        const value = materialize(step.value, scope);
        await locate(actor.page, step.locator).fill(value, { timeout: 5000 });
        if (preparing && await locate(actor.page, step.locator).inputValue() !== value) throw new Error('DRIVER_UI_PREPARATION_INPUT_MISMATCH');
      } else if (step.kind === 'click') {
        if (step.responsePath) {
          const expected = targetPath(base, step.responsePath, scope).href;
          [response] = await Promise.all([actor.page.waitForResponse(r => r.url() === expected && r.request().method() === step.responseMethod, { timeout: 8000 }), locate(actor.page, step.locator).click({ timeout: 5000 })]);
        } else { response = undefined; await locate(actor.page, step.locator).click({ timeout: 5000 }); }
      } else if (step.kind === 'check') {
        response = undefined;
        await locate(actor.page, step.locator).setChecked(Boolean(materialize(step.value, scope)), { timeout: 5000 });
      } else if (step.kind === 'setInputFiles') {
        response = undefined;
        const reference = materialize(step.fileRef, scope);
        if (!Object.hasOwn(fixture.uploads || {}, reference)) throw new Error('DRIVER_UPLOAD_REFERENCE_NOT_AVAILABLE');
        const payload = filePayload(directory, runId, fixture.uploads[reference]);
        const select = () => locate(actor.page, step.locator).setInputFiles(payload, { timeout: 5000 });
        if (step.responsePath) {
          const expected = targetPath(base, step.responsePath, scope).href;
          [response] = await Promise.all([actor.page.waitForResponse(r => r.url() === expected && r.request().method() === step.responseMethod, { timeout: 8000 }), select()]);
        } else await select();
      } else throw new Error('DRIVER_UI_STEP_NOT_SUPPORTED');
    }
    return response;
  }
  async function uiResult(actor, definition, scope) {
    const fields = {};
    for (const probe of definition.probes) {
      const element = locate(actor.page, probe.locator);
      const actual = probe.read === 'input' ? await element.inputValue() : probe.read === 'checked' ? await element.isChecked() : (await element.textContent())?.trim();
      if (!Object.is(actual, materialize(probe.expected, scope))) throw new Error('DRIVER_UI_RESULT_NOT_OBSERVED');
      if (probe.field) fields[probe.field] = actual;
    }
    return { ...fields, outcome: 'ui-observed', observedTransport: 'dom' };
  }
  const driver = {
    async provisionRestoreWriteProbe(operationId) {
      ready();
      const name = 'OWNER-RESTORE-PROBE';
      if (profileName !== 'restore-old-point-new-state' || typeof operationId !== 'string' || !operationId ||
        !Object.hasOwn(fixture.actors, name) || actors.has(name) || actorInitializations.has(name) || provisioningRestoreProbe)
        throw new Error('DRIVER_RESTORE_PROBE_NOT_FRESH');
      provisioningRestoreProbe = true; active++;
      try {
        const issued = await driver.control('prepare-isolated-restore-write-probe', { operationId, actor: name });
        if (issued.outcome !== 'accepted' || typeof issued.probeGrantRef !== 'string' || !issued.probeGrantRef)
          throw new Error('DRIVER_RESTORE_PROBE_GRANT_REQUIRED');
        addSecrets(issued.probeGrantRef);
        const reply = await exchange({ kind: 'observe', view: 'fresh-restore-probe-session',
          args: { operationId, grantRef: issued.probeGrantRef, actor: name }, runId, targetOrigin: base.origin });
        const actorState = validateRestoreProbeSession(reply, {
          runId, operationId, grantRef: issued.probeGrantRef, base, previousCookieValues: secrets,
        });
        fixture.actors[name] = actorState;
        addSecrets(actorState.credentials || {});
        for (const cookie of actorState.storageState.cookies) addSecrets(cookie.value);
        return { outcome: 'fixture-provisioned', actor: name };
      } catch (error) {
        poisoned = true;
        if (/^(DRIVER_|FIXTURE_IO_)[A-Z_]+$/.test(error.message)) throw error;
        throw new Error('DRIVER_RESTORE_PROBE_PROVISIONING_FAILED');
      } finally { active--; provisioningRestoreProbe = false; }
    },
    async inspectInfrastructureAdmission() {
      if (closed || poisoned || resetting || active) throw new Error('DRIVER_FIXTURE_NOT_READY');
      const reply = await exchange({ kind: 'observe', view: 'infrastructure-admission', targetOrigin: base.origin });
      if (reply.source !== 'actual-http') throw new Error('DRIVER_INFRASTRUCTURE_ADMISSION_PROVENANCE_REQUIRED');
      return structuredClone(reply.data);
    },
    async control(action, args = {}) {
      ready();
      if (!controlBase || !Object.hasOwn(bindings.controls || {}, action)) throw new Error('DRIVER_CONTROL_TRANSPORT_NOT_CONFIGURED');
      active++;
      try {
        // Fresh read for this run before every fault command; pre-reset preflight is not a permit.
        const admissionReply = await exchange({ kind: 'observe', view: 'infrastructure-admission', runId, targetOrigin: base.origin });
        if (admissionReply.source !== 'actual-http') throw new Error('DRIVER_INFRASTRUCTURE_ADMISSION_PROVENANCE_REQUIRED');
        const permit = validateControlAdmission(admissionReply.data, { controlBase, runId, session: fixture.controlSession, capability: controlCapability(action) });
        if (!controlContext) {
          await ensureBrowser();
          controlContext = await browser.newContext({ storageState: validateStorage(fixture.controlSession.storageState, controlBase), serviceWorkers: 'block', acceptDownloads: false });
        }
        return await http({ context: controlContext }, bindings.controls[action], { args, fixture }, controlBase,
          { ...permit, operationId: randomUUID() });
      } catch (error) {
        if (/^(DRIVER_|FIXTURE_IO_)[A-Z_]+$/.test(error.message)) throw error;
        throw new Error('DRIVER_CONTROL_TRANSPORT_FAILED');
      } finally { active--; }
    },
    async reset(profile, options = {}) {
      if (closed || poisoned) throw new Error('DRIVER_CLOSED');
      if (active || resetting) throw new Error('DRIVER_OPERATION_IN_PROGRESS');
      if (!bindings.profiles.includes(profile)) throw new Error('DRIVER_PROFILE_NOT_BOUND');
      resetting = true;
      try {
      for (const actor of actors.values()) await actor.context.close();
      if (controlContext) { await controlContext.close(); controlContext = undefined; }
      actors.clear(); authRequestIds.clear(); fixture = undefined; runId = undefined; profileName = undefined; secrets.clear();
      const reply = await exchange({ kind: 'reset', phase: 'before-ui', profile, options, targetOrigin: base.origin });
      if (typeof reply.runId !== 'string' || reply.runId.length < 16 || reply.source !== 'actual-fixture' ||
        !reply.data?.actors || !reply.evidence?.fixtureVersion) throw new Error('DRIVER_FIXTURE_EVIDENCE_REQUIRED');
      // The declaration is checked here; actual bridge/UI/DB provenance still needs independent review.
      fixture = structuredClone(reply.data); runId = reply.runId;
      addSecrets(fixture.secretRefs || {});
      for (const cookie of fixture.controlSession?.storageState?.cookies || []) addSecrets(cookie.value);
      for (const role of Object.values(fixture.actors)) {
        validateStorage(role.storageState, base);
        for (const cookie of role.storageState.cookies) addSecrets(cookie.value);
        addSecrets(role.credentials || {});
      }
      if (profile === 'controlled-session-boundary' && reply.evidence.preparationPhase !== 'fresh-before-ui')
        throw new Error('DRIVER_FRESH_SESSION_PREPARATION_REQUIRED');
      const setup = bindings.profileSetups?.[profile];
      const preparationState = async () => {
        const state = await exchange({ kind: 'observe', view: 'ui-preparation-business-state', runId, targetOrigin: base.origin });
        if (state.source !== 'actual-db' || !Array.isArray(state.data?.pages) || !state.data.pages.length ||
          state.data.pages.some(page => !page.id || page.revision === undefined || typeof page.publicText !== 'string' || !Array.isArray(page.versions) || !page.versions.length))
          throw new Error('DRIVER_UI_PREPARATION_DB_EVIDENCE_REQUIRED');
        return JSON.stringify(state.data);
      };
      if (setup?.actors?.length) {
        const initialActors = [];
        for (const initial of setup.actors) initialActors.push({ initial, actor: await actorContext(initial.actor, true) });
        await guardUiPreparation({
          readState: preparationState,
          subscribe: notify => {
            const listener = request => notify(request.method());
            for (const { actor } of initialActors) actor.context.on('request', listener);
            return () => { for (const { actor } of initialActors) actor.context.off('request', listener); };
          },
          prepare: async () => {
            for (const { initial, actor } of initialActors)
              await steps(actor, initial.steps, { fixture, args: options, actor: fixture.actors[initial.actor] }, true);
          },
        });
      }
      if (setup?.finalizeFixture) {
        const final = await exchange({ kind: 'reset', phase: 'after-ui', profile, options, runId, targetOrigin: base.origin });
        if (final.source !== 'actual-fixture' || final.evidence?.preparationPhase !== 'after-ui-finalized')
          throw new Error('DRIVER_FIXTURE_FINALIZATION_NOT_CONFIRMED');
      }
      profileName = profile;
      } catch (error) {
        // A partially prepared editor/session is never usable by a later assertion.
        poisoned = true; fixture = undefined;
        if (/^(DRIVER_|FIXTURE_IO_)[A-Z_]+$/.test(error.message)) throw error;
        throw new Error('DRIVER_FIXTURE_UI_PREPARATION_FAILED');
      } finally { resetting = false; }
    },
    async act(name, action, args = {}) {
      ready();
      if (name === 'TEST-CONTROL' || infrastructureControlActions.has(action)) throw new Error('DRIVER_USE_INDEPENDENT_CONTROL_TRANSPORT');
      if (!Object.hasOwn(bindings.operations, action)) throw new Error('DRIVER_ACTION_NOT_BOUND');
      const definition = bindings.operations[action];
      const scope = { args, fixture, actor: fixture.actors[name] };
      active++;
      try {
        const actor = await actorContext(name);
        if (definition.kind === 'http') {
          const transport = profileName === 'auth-login-isolated-sources' ? authSourceOrigin(profileName,name,fixture.actors[name].sourceOrigin) : base;
          return await http(actor, definition, scope, transport);
        }
        let mutationSeen = false;
        const listener = request => { if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) mutationSeen = true; };
        const uiOnly = definition.result.format === 'ui';
        if (uiOnly) actor.context.on('request', listener);
        try {
          const response = await steps(actor, definition.steps, scope);
          if (!uiOnly) return await decode(response, definition.result);
          const result = await uiResult(actor, definition.result, scope);
          if (mutationSeen) throw new Error('DRIVER_UI_ONLY_NETWORK_MUTATION');
          return result;
        } finally { if (uiOnly) actor.context.off('request', listener); }
      } catch (error) {
        if (/^(DRIVER_|FIXTURE_IO_)[A-Z_]+$/.test(error.message)) throw error;
        throw new Error('DRIVER_ACTION_TRANSPORT_OR_UI_FAILED');
      } finally { active--; }
    },
    async observe(view, args = {}) {
      ready();
      if (!Object.hasOwn(bindings.observations, view)) throw new Error('DRIVER_OBSERVATION_NOT_BOUND');
      const definition = bindings.observations[view];
      active++;
      try {
      if (definition.kind === 'ui-input') {
        const actor = await actorContext(args.actor);
        return locate(actor.page, definition.locator).inputValue({ timeout: 5000 });
      }
      if (definition.kind === 'ui-memory') {
        const actor = await actorContext(args.actor);
        return inspectBrowserPersistence(actor.page, base.origin, args.canary);
      }
      if (definition.kind === 'process-read') {
        validateFoundationProcessRequest(view, args, profileName);
        const reply = await exchange({ kind: 'observe', view, args, runId, targetOrigin: base.origin });
        return foundationProcessData(reply, { view, args, profileName, runId });
      }
      if (definition.kind !== 'fixture-read') throw new Error('DRIVER_OBSERVATION_KIND_NOT_SUPPORTED');
      const observerArgs = profileName === 'auth-login-isolated-sources' && view === 'auth-source-state' ?
        { ...args, expectedRequestId: authRequestIds.get(authSourceOrigin(profileName,args.actor,fixture.actors[args.actor]?.sourceOrigin).origin) } : args;
      const reply = await exchange({ kind: 'observe', view, args: observerArgs, runId, targetOrigin: base.origin });
      if (reply.source !== 'actual-db' && reply.source !== 'actual-http') throw new Error('DRIVER_OBSERVATION_PROVENANCE_REQUIRED');
      return structuredClone(reply.data);
      } catch (error) {
        if (/^(DRIVER_|FIXTURE_IO_)[A-Z_]+$/.test(error.message)) throw error;
        throw new Error('DRIVER_OBSERVATION_FAILED');
      } finally { active--; }
    },
    async close() {
      if (closed) return;
      closed = true;
      await Promise.allSettled(actorInitializations.values());
      const results = await Promise.allSettled([...actors.values()].map(actor => actor.context.close()));
      actors.clear();
      if (browser) await browser.close();
      controlContext = undefined;
      if (runId && !poisoned) await exchange({ kind: 'close', runId, targetOrigin: base.origin });
      fixture = undefined; runId = undefined; secrets.clear();
      if (results.some(result => result.status === 'rejected')) throw new Error('DRIVER_CLOSE_INCOMPLETE');
    },
  };
  return driver;
}
