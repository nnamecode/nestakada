import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';
import { sensitiveValueCheck } from './response-safety.js';

// Acceptance assertions only. No application, inspector endpoint or framework mock is implemented here.
const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await app.reset('local-foundation-isolated'); await use(app); } finally { await app.close(); }
} });
test.describe.configure({ timeout: 60_000 }); // Test-process budget, not a site/owner response deadline.
const selected = { python: '3.14.10', django: '5.2.18', psycopg: '3.3.6', 'psycopg-c': '3.3.6', 'django-csp': '4.0' };
const required = value => { expect(typeof value === 'string' && value.length > 0).toBe(true); return value; };
const processView = (app, view, profile = 'local-http') => app.observe(view, { profile });
async function settings(app, profile = 'local-http') {
  const value = await processView(app, 'foundation-settings', profile);
  expect(value.profile).toBe(profile); return value;
}
function middleware(value) {
  expect(Array.isArray(value.middleware)).toBe(true);
  for (const name of ['django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware', 'csp.middleware.CSPMiddleware'])
    expect(value.middleware).toContain(name);
  expect(value.middleware.indexOf('django.contrib.sessions.middleware.SessionMiddleware')).toBeLessThan(
    value.middleware.indexOf('django.contrib.auth.middleware.AuthenticationMiddleware'));
}
function cookiePolicy(value, secure) {
  expect(value.sessionCookieSecure).toBe(secure); expect(value.csrfCookieSecure).toBe(secure);
  expect(value.sessionCookieHttpOnly).toBe(true); expect(value.sessionCookieSameSite).toBe('Lax');
  expect(value.csrfCookieSameSite).toBe('Lax');
  expect(value.sessionCookieDomain).toBeNull(); expect(value.csrfCookieDomain).toBeNull();
  required(value.sessionCookieName); required(value.csrfCookieName);
}
function policy(text) {
  const result = new Map();
  for (const fragment of required(text).split(';')) {
    const [name, ...values] = fragment.trim().split(/\s+/u); if (!name) continue;
    expect(result.has(name)).toBe(false); result.set(name, values);
  }
  return result;
}
async function http(app, challenge) {
  const value = await app.observe('foundation-http-response', { challenge });
  expect(value.challenge).toBe(challenge); expect(value.method).toBe('GET'); expect(value.requestTarget).toBe('/');
  expect(typeof value.body).toBe('string'); expect(value.headers !== null && typeof value.headers === 'object').toBe(true);
  return value;
}
const packages = rows => rows.map(row => ({ name: required(row.name).toLowerCase().replace(/[-_.]+/gu, '-'), version: required(row.version) }))
  .sort((a, b) => a.name.localeCompare(b.name));

test('FOUNDATION-001-versions | AT-053 AT-055 AC-053 AC-055 | actual isolated runtimes match the proposed exact versions', async ({ app }) => {
  const actual = await processView(app, 'foundation-runtime-versions');
  expect(actual.python).toBe(selected.python); expect(actual.implementation).toBe('CPython');
  for (const name of ['django', 'psycopg', 'psycopg-c', 'django-csp']) expect(actual.packages[name]).toBe(selected[name]);
  expect(actual.packages['psycopg-binary']).toBeUndefined(); expect(actual.psycopgImplementation).toBe('c');
  expect(actual.libpqVersionNum).toBe(170011); expect(actual.systemOpenSSLPackage).toBe('3.5.7-1~deb13u3');
  expect(actual.postgresqlServerVersionNum).toBe(180006); expect(actual.postgresqlEngine).toBe('PostgreSQL');
  expect(actual.postgresqlXmlProbeSqlstate).toBe('0A000');
  expect(actual.nginxVersion).toBe('1.30.6'); // D-313: separate local ingress, not a Python dependency.
});

test('FOUNDATION-002-local-config | AT-053 AT-055 AC-053 AC-055 | local profile keeps safeguards and fails closed without required secrets', async ({ app }) => {
  const actual = await settings(app);
  expect(actual.debug).toBe(false); middleware(actual); cookiePolicy(actual, false);
  expect(actual.sslRedirect).toBe(false); expect(actual.hstsSeconds).toBe(0);
  expect(actual.secureProxySslHeader).toBeNull(); expect(actual.useXForwardedHost).toBe(false);
  expect(Array.isArray(actual.allowedHosts) && actual.allowedHosts.length > 0).toBe(true);
  for (const host of actual.allowedHosts) expect(['localhost', '127.0.0.1', 'host.docker.internal', '[::1]']).toContain(host);
  expect(actual.csrfExemptApplicationRoutes).toEqual([]);
  expect(actual.templateAutoescape).toBe(true);
  expect(actual.missingConfigurationProbes.map(item => item.missing).sort()).toEqual(['database-password', 'django-secret-key']);
  for (const probe of actual.missingConfigurationProbes) {
    expect(Number.isInteger(probe.exitCode) && probe.exitCode !== 0).toBe(true);
    expect(probe.usedFallback).toBe(false); expect(probe.canaryLeakCount).toBe(0);
  }
});

test('FOUNDATION-003-deployment-config | AT-053 AT-312 AC-053 AC-OPS-012 | separate deployment-audit settings are secure without claiming live TLS', async ({ app }) => {
  const local = await settings(app), actual = await settings(app, 'deployment-audit');
  expect(actual.debug).toBe(false); middleware(actual); cookiePolicy(actual, true);
  expect(actual.sslRedirect).toBe(true); expect(actual.secureProxySslHeader).toBeNull(); expect(actual.useXForwardedHost).toBe(false);
  expect(actual.allowedHosts.length).toBeGreaterThan(0); expect(actual.allowedHosts).not.toContain('*');
  expect(actual.sessionCookieName).not.toBe(local.sessionCookieName); expect(actual.csrfCookieName).not.toBe(local.csrfCookieName);
  expect(actual.secretReferenceId).not.toBe(local.secretReferenceId); required(actual.secretReferenceId); required(local.secretReferenceId);
  expect(actual.csrfExemptApplicationRoutes).toEqual([]); expect(actual.templateAutoescape).toBe(true);
});

test('FOUNDATION-004-host | AT-053 AC-053 | actual HTTP rejects an untrusted Host while forwarded input cannot change the local redirect policy', async ({ app }) => {
  const baseline = await http(app, 'baseline'); expect([200, 404]).toContain(baseline.status);
  const invalid = await http(app, 'unknown-host'); expect(invalid.requestHeaders.host).toBe('untrusted.invalid'); expect(invalid.status).toBe(400);
  const spoofed = await http(app, 'spoofed-forwarded');
  expect(spoofed.requestHeaders['x-forwarded-host']).toBe('untrusted.invalid');
  expect(spoofed.requestHeaders['x-forwarded-proto']).toBe('https');
  expect(spoofed.status).toBe(baseline.status); expect(spoofed.headers.location).toBeUndefined();
  // Runtime trust is also checked in the settings case; response equality alone is not proof of is_secure().
});

test('FOUNDATION-005-headers | AT-053 AT-312 AC-053 AC-OPS-012 | actual local response carries headers and initial CSP report-only policy', async ({ app }) => {
  const actual = await http(app, 'baseline'); expect([200, 404]).toContain(actual.status);
  expect(actual.headers['x-content-type-options']).toBe('nosniff'); expect(actual.headers['x-frame-options']).toBe('DENY');
  expect(actual.headers['referrer-policy']).toBe('same-origin'); expect(actual.headers['cross-origin-opener-policy']).toBe('same-origin');
  const csp = policy(actual.headers['content-security-policy-report-only']);
  expect(csp.get('default-src')).toEqual(["'self'"]); expect(csp.get('object-src')).toEqual(["'none'"]);
  expect(csp.get('base-uri')).toEqual(["'self'"]); expect(csp.get('frame-ancestors')).toEqual(["'none'"]);
  expect(csp.get('form-action')).toEqual(["'self'"]); expect(csp.get('script-src')).toEqual(["'self'"]);
  expect(actual.headers['content-security-policy']).toBeUndefined();
});

test('FOUNDATION-006-db-roles | AT-055 AC-055 | actual runtime connection has no cluster administration or migration identity', async ({ app }) => {
  const actual = await app.observe('foundation-db-roles');
  required(actual.runtime.name); required(actual.migrator.name); required(actual.bootstrap.name);
  expect(actual.currentUser).toBe(actual.runtime.name); expect(actual.sessionUser).toBe(actual.runtime.name);
  expect(new Set([actual.runtime.name, actual.migrator.name, actual.bootstrap.name]).size).toBe(3);
  for (const field of ['superuser', 'createDb', 'createRole', 'replication', 'bypassRls']) expect(actual.runtime[field]).toBe(false);
  expect(actual.runtime.databaseOwner).toBe(false); expect(actual.runtime.schemaOwner).toBe(false);
});

test('FOUNDATION-007-db-effective | AT-055 AC-055 | role memberships and effective privileges do not restore prohibited powers', async ({ app }) => {
  const actual = await app.observe('foundation-db-roles');
  for (const field of ['databaseCreate', 'schemaCreate', 'memberOfMigrator', 'memberOfBootstrap', 'memberOfPrivilegedRole'])
    expect(actual.effectivePrivileges[field]).toBe(false);
  expect(actual.effectivePrivileges.connect).toBe(true);
  expect(actual.migrator.name).not.toBe(actual.runtime.name);
});

test('FOUNDATION-008-isolation | AT-055 AC-055 | actual container metadata keeps database and privileged host surfaces private', async ({ app }) => {
  const actual = await processView(app, 'foundation-isolation');
  expect(actual.platform).toBe('linux/amd64'); expect(Number.isInteger(actual.appUid) && actual.appUid > 0).toBe(true);
  expect(actual.privileged).toBe(false); expect(actual.noNewPrivileges).toBe(true); expect(actual.capDrop).toContain('ALL');
  expect(actual.capAdd).toEqual([]);
  expect(actual.mountAuditSource).toBe('host-docker-inspect-and-canonical-sources');
  for (const field of ['hostRootSourceMounted', 'hostProfileSourceMounted', 'engineSocketSourceMounted', 'outsideApprovedSourcesMounted'])
    expect(actual[field]).toBe(false);
  expect(actual.databasePublishedPorts).toEqual([]); expect(actual.appPublishedPorts).toEqual([]);
  expect(actual.ingressPublishedPorts.length).toBeGreaterThan(0);
  for (const binding of actual.ingressPublishedPorts) expect(binding.hostIp).toBe('127.0.0.1');
  expect(actual.ingressHasDatabaseNetwork).toBe(false); expect(actual.appHasIngressNetwork).toBe(false);
  expect(actual.databaseHasWebNetwork).toBe(false);
  expect(actual.hostNetwork).toBe(false); expect(actual.hostPidNamespace).toBe(false);
  for (const mount of actual.appMounts) {
    expect(mount.sourceWithinApprovedBoundary).toBe(true);
    expect(['source', 'secret', 'runtime-temp', 'runtime-data', 'media-exchange']).toContain(mount.purpose);
    if (mount.purpose === 'source') { expect(mount.type).toBe('bind'); expect(mount.target).toBe('/app'); }
    if (mount.purpose === 'secret') { expect(mount.type).toBe('bind'); expect(mount.target).toMatch(/^\/run\/secrets\/[a-z0-9-]+$/u); }
    if (mount.purpose === 'runtime-temp') { expect(mount.type).toBe('tmpfs'); expect(mount.target).toBe('/tmp'); }
    if (mount.purpose === 'runtime-data') { expect(mount.type).toBe('volume'); expect(mount.target).toBe('/var/lib/estakada'); }
    if (mount.purpose === 'media-exchange') { expect(mount.type).toBe('volume'); expect(mount.target).toBe('/exchange'); expect(mount.readOnly).toBe(false); }
    if (mount.purpose !== 'source') expect(mount.currentFixtureOnly).toBe(true);
    expect(mount.target).not.toMatch(/(?:docker|containerd)\.sock$/iu);
    expect(mount.target).not.toBe('/');
    if (mount.purpose === 'source' || mount.purpose === 'secret') expect(mount.readOnly).toBe(true);
  }
  expect(actual.appMounts.some(mount => mount.purpose === 'source')).toBe(true);
  expect(actual.databaseDataMountTarget).toBe('/var/lib/postgresql'); // Official PostgreSQL18 image layout.
  const worker=actual.mediaWorker;
  expect(worker.image).toBe('sha256:6105f968d577220973fb9ed8e0caf3ba48a3e028d23d4d324059b4b4b3739f9c');
  expect(worker.lockedImage).toBe(worker.image); expect(worker.uid).toBe('10002:10001');
  expect(worker.networkMode).toBe('none'); expect(worker.ports).toEqual([]); expect(worker.privileged).toBe(false);
  expect(worker.readonly).toBe(true); expect(worker.capDrop).toContain('ALL'); expect(worker.capAdd).toEqual([]);
  expect(worker.securityOpt.some(x=>x==='no-new-privileges'||x==='no-new-privileges:true')).toBe(true);
  expect(worker.memory).toBe(536870912); expect(worker.memorySwap).toBe(536870912);
  expect(worker.nanoCpus).toBe(1000000000); expect(worker.pids).toBe(64);
  for(const mount of worker.mounts)expect(mount.approved).toBe(true);
  expect(worker.mounts.map(m=>m.target).sort()).toEqual(['/exchange','/worker']);
  expect(worker.exchange).toEqual({driver:'local',options:{type:'tmpfs',device:'tmpfs',o:'size=128m,uid=10001,gid=10001,mode=0770'},label:'foundation-test'});
});

test('FOUNDATION-009-pins | AT-055 AC-055 | installed runtime packages and selected images are tied to exact locks and digests', async ({ app }) => {
  const actual = await processView(app, 'foundation-dependency-evidence');
  expect(actual.lockedRuntimePackages.length).toBeGreaterThan(0);
  const locked = packages(actual.lockedRuntimePackages), installed = packages(actual.installedRuntimePackages);
  expect(new Set(locked.map(row => row.name)).size).toBe(locked.length); expect(installed).toEqual(locked);
  for (const row of actual.lockedRuntimePackages) {
    expect(row.artifactSha256).toMatch(/^[a-f0-9]{64}$/u); expect(row.declaredHashSha256).toBe(row.artifactSha256);
  }
  for (const [name, version] of Object.entries(selected).filter(([name]) => name !== 'python'))
    expect(installed.find(row => row.name === name)?.version).toBe(version);
  expect(installed.some(row => row.name === 'psycopg-binary')).toBe(false);
  expect(packages(actual.bootstrapPackages)).toEqual([{ name: 'pip', version: '26.2.2' }]);
  const materials = ['debian-base', 'local-ingress-base', 'postgres-entrypoint-source', 'python-base'];
  expect(actual.sourceMaterials.map(row => row.component).sort()).toEqual(materials);
  for (const row of actual.sourceMaterials) {
    expect(row.platform).toBe('linux/amd64'); expect(row.lockedManifestDigest).toMatch(/^sha256:[a-f0-9]{64}$/u);
    expect(row.observedBuildMaterialDigest).toBe(row.lockedManifestDigest);
  }
  expect(actual.sourceArchives.map(row => row.component).sort()).toEqual(['postgres-source', 'psycopg-c-source']);
  for (const row of actual.sourceArchives) {
    expect(row.lockedSha256).toMatch(/^[a-f0-9]{64}$/u); expect(row.observedSha256).toBe(row.lockedSha256);
  }
  const requiredMaterials = { 'local-ingress': ['local-ingress-base'],
    postgres: ['debian-base', 'postgres-entrypoint-source'], 'python-runtime': ['python-base'] };
  expect(actual.runtimeBuilds.map(row => row.component).sort()).toEqual(Object.keys(requiredMaterials).sort());
  for (const row of actual.runtimeBuilds) {
    expect(row.platform).toBe('linux/amd64'); expect(row.lockedDockerImageId).toMatch(/^sha256:[a-f0-9]{64}$/u);
    expect(row.builtDockerImageId).toBe(row.lockedDockerImageId);
    expect(row.materialComponents.sort()).toEqual(requiredMaterials[row.component]);
    for (const field of ['inputs', 'recipe', 'receipt']) {
      expect(row[`${field}LockedSha256`]).toMatch(/^[a-f0-9]{64}$/u);
      expect(row[`${field}ObservedSha256`]).toBe(row[`${field}LockedSha256`]);
    }
    if (row.component !== 'python-runtime') expect(row.runningDockerImageId).toBe(row.lockedDockerImageId);
  }
  // Engine .Id/.Image are opaque Docker-reported IDs. Do not equate them with OCI config digests.
  const appImage = actual.applicationImage;
  expect(appImage.mode).toBe('runtime-image-with-readonly-source');
  expect(appImage.sourceSha256).toMatch(/^[a-f0-9]{64}$/u);
  expect(appImage.runningDockerImageId).toMatch(/^sha256:[a-f0-9]{64}$/u);
  expect(appImage.runningDockerImageId).toBe(appImage.builtDockerImageId);
  expect(appImage.buildBaseDockerImageId).toBe(actual.runtimeBuilds.find(row => row.component === 'python-runtime').lockedDockerImageId);
  expect(actual.lockFileSha256).toMatch(/^[a-f0-9]{64}$/u);
  expect(appImage.dependencyLockSha256).toBe(actual.lockFileSha256);
});

test('FOUNDATION-010-deploy-check | AT-053 AT-055 AC-053 AC-055 | actual deployment audit reports every check and permits only documented HSTS warning', async ({ app }) => {
  const actual = await processView(app, 'foundation-deploy-check', 'deployment-audit');
  expect(actual.commandRef).toBe('DJANGO_CHECK_DEPLOY'); expect(actual.profile).toBe('deployment-audit');
  expect(actual.exitCode).toBe(0); expect(actual.silencedSystemChecks).toEqual([]); expect(actual.errors).toEqual([]);
  expect(Array.isArray(actual.warnings)).toBe(true);
  for (const warning of actual.warnings) {
    expect(warning.id).toBe('security.W004'); expect(warning.reasonRef).toBe('LOCAL-NO-TLS-HSTS');
  }
  expect(actual.secretLeakCount).toBe(0);
});

test('FOUNDATION-011-audit-redaction | AT-055 AC-055 | actual DEV28 formatter retains benign evidence and removes synthetic sensitive inputs', async ({ app }) => {
  const actual = await processView(app, 'foundation-audit-redaction');
  expect(actual.formatterLoadedFromApplication).toBe(true); expect(actual.exercisedFields.sort()).toEqual([
    'authorization', 'cookie', 'password', 'request-comment', 'request-phone', 'secret-key', 'token',
  ]);
  const canaries = ['FOUNDATION-SYNTHETIC-AUTH', 'FOUNDATION-SYNTHETIC-COOKIE', 'FOUNDATION-SYNTHETIC-PASSWORD',
    'FOUNDATION-SYNTHETIC-COMMENT', '+70000000000', 'FOUNDATION-SYNTHETIC-SECRET', 'FOUNDATION-SYNTHETIC-TOKEN'];
  required(actual.formattedText); expect(actual.formattedText).toContain('FOUNDATION-LOG-BENIGN');
  expect(sensitiveValueCheck(actual.formattedText, canaries)).toEqual({ checkedCount: canaries.length, detected: false });
});
