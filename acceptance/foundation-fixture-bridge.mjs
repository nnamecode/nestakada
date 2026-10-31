// Read-only FOUNDATION adapter. No business fixtures, product endpoints or engine access.
import fs from 'node:fs';
import http from 'node:http';
const origin = 'http://host.docker.internal:8767';
const profile = 'local-foundation-isolated';
const processViews = new Set(['foundation-runtime-versions', 'foundation-settings', 'foundation-isolation',
  'foundation-dependency-evidence', 'foundation-deploy-check', 'foundation-audit-redaction']);
function reject() { throw new Error('FOUNDATION_FIXED_SCOPE_REJECTED'); }
async function getResponse(challenge) {
  if (!['baseline', 'unknown-host', 'spoofed-forwarded'].includes(challenge)) reject();
  const requestHeaders = { host: challenge === 'unknown-host' ? 'untrusted.invalid' : 'host.docker.internal:8767' };
  if (challenge === 'spoofed-forwarded') Object.assign(requestHeaders,
    { 'x-forwarded-host': 'untrusted.invalid', 'x-forwarded-proto': 'https' });
  return new Promise((resolve, rejectPromise) => {
    const req = http.get(`${origin}/`, { headers: requestHeaders, agent: false }, response => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', chunk => { body += chunk; if (body.length > 128 * 1024) response.destroy(new Error('size')); });
      response.on('error', rejectPromise);
      response.on('end', () => {
        const headers = {};
        for (const name of ['x-content-type-options', 'x-frame-options', 'referrer-policy',
          'cross-origin-opener-policy', 'content-security-policy-report-only', 'content-security-policy', 'location'])
          if (response.headers[name] !== undefined) headers[name] = response.headers[name];
        resolve({ challenge, method: 'GET', requestTarget: '/', requestHeaders, status: response.statusCode, headers, body });
      });
    });
    req.setTimeout(4000, () => req.destroy(new Error('timeout')));
    req.on('error', rejectPromise);
  });
}
try {
  let input = '';
  for await (const chunk of process.stdin) { input += chunk; if (input.length > 32768) reject(); }
  const request = JSON.parse(input);
  if (request.protocol !== 'estakada-fixture-v1' || request.targetOrigin !== origin ||
    typeof request.nonce !== 'string' || !/^[a-f0-9]{48}$/u.test(request.nonce)) reject();
  const file = '/foundation-evidence/current.json';
  if (fs.lstatSync(file).isSymbolicLink() || fs.statSync(file).size > 4 * 1024 * 1024) reject();
  const snapshot = JSON.parse(fs.readFileSync(file, 'utf8'));
  const age = Date.now() - Date.parse(snapshot.observedAt);
  if (!Number.isFinite(age) || age < -5000 || age > 15 * 60 * 1000 ||
    snapshot.targetOrigin !== origin || snapshot.fixtureProfile !== profile ||
    !/^[a-f0-9-]{36}$/u.test(snapshot.runId) || !/^[a-f0-9]{64}$/u.test(snapshot.sourceSha256) ||
    snapshot.provenance?.collector !== 'host-docker-exec-inspect' ||
    snapshot.provenance?.sourceVerifiedBeforeAndAfter !== true) reject();
  if (request.runId !== undefined && request.runId !== snapshot.runId) reject();
  let source, data;
  if (request.kind === 'reset') {
    if (request.profile !== profile || request.phase !== 'before-ui' || Object.keys(request.options || {}).length) reject();
    source = 'actual-fixture'; data = { actors: {} };
  } else if (request.kind === 'close') {
    source = 'actual-fixture'; data = { closed: true };
  } else if (request.kind === 'observe' && request.runId === snapshot.runId) {
    const args = request.args || {};
    if (request.view === 'foundation-http-response') {
      if (Object.keys(args).some(key => key !== 'challenge')) reject();
      source = 'actual-http'; data = await getResponse(args.challenge);
    } else if (request.view === 'foundation-db-roles' || processViews.has(request.view)) {
      if (Object.keys(args).some(key => key !== 'profile') ||
        !['local-http', 'deployment-audit'].includes(args.profile || 'local-http')) reject();
      data = snapshot.observations[request.view]?.[args.profile || 'local-http'];
      if (!data || typeof data !== 'object') reject();
      source = request.view === 'foundation-db-roles' ? 'actual-db' : 'actual-process';
    } else reject();
  } else reject();
  process.stdout.write(JSON.stringify({ protocol: request.protocol, nonce: request.nonce, ok: true,
    targetOrigin: origin, runId: snapshot.runId, source, data,
    evidence: { fixtureVersion: 'foundation-readonly-v1', fixtureProfile: profile,
      observationMode: 'host-collected-readonly-snapshot-plus-live-http', observedAt: snapshot.observedAt,
      sourceSha256: snapshot.sourceSha256 } }));
} catch {
  process.stderr.write('FOUNDATION_ADAPTER_FAILED'); process.exitCode = 1;
}
