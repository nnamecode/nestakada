# RB4 Staff lifecycle focused PostgreSQL gate

Дата: 2026-11-19. ID: `RB4-STAFF-PG-001`. Статус: **completed D-1678; run2 exact111/111 and cleanup independently ACCEPTED0/0/0, product0/no-bloat PASS, server gate closed, repeat0**.

## Purpose and exact suite

This is the first runtime gate for independently approved code candidate `RB4-SLICE-003B-STAFF`. One disposable PostgreSQL run executes exactly:

- `modules.accounts.tests.test_http_auth` —16 methods;
- `modules.pages.tests.test_http_list` —9 methods;
- `modules.pages.tests.test_http_editor` —34 methods;
- `modules.pages.tests.test_commands` —13 methods;
- `modules.pages.tests.test_grants` —10 methods;
- `modules.pages.tests.test_http_grants` —8 methods;
- `modules.pages.tests.test_staff_lifecycle` —13 methods;
- `modules.pages.tests.test_http_staff` —8 methods.

Preflight discovery must equal exact111 before Django creates a test database. Expected result: migrations, system check0, `Ran 111 tests`, failures0/errors0/skips0 and exit0. Standard Django runner creates/destroys only `estakada_staff_test`. The first exact90 retain accepted auth/list/editor/PageCAS/PageGrant behavior; exact21 proves employee create/password/deactivate/reactivate, digest/audit rollback, session revocation, actual PostgreSQL lock order/concurrency and fixed private HTTP.

## Current-source and disposable boundary

Reuse the independently accepted D-1665 run5 boundary byte-for-condition, changing only exact names/counts/origins/base/test DB:

- existing local PG/app images, pull/build/install0;
- exact fresh names `rb4-staff-pg`, `rb4-staff-tests`, `rb4-staff-net`, fresh label `nestakada.run=rb4-staff-pg-001-<uuid>`;
- internal bridge, ports0, other networks0;
- PostgreSQL parent/socket/tmp tmpfs3 with exact literal sizes/modes, raw `Mounts=[]`, readonly root, accepted caps/resources;
- existing bounded root bootstrap proves parent/data/PGDATA numeric999:999:700, then standard entrypoint/privilege drop;
- bounded canonical-base64 extraction of public synthetic TLS certificate, full-string validation, CreateNew+WriteThrough+re-read, exact leaf+empty-dir cleanup;
- synthetic base `estakada_staff_base`, test DB `estakada_staff_test`, real/imported data0;
- app UID10001, readonly exact current `src`, one tmpfs, caps/resources, ports0; docs/media/private data/Docker socket/named volumes0.

Current-source preflight proves exact23 literal regular non-symlink origins: previous15 (`accounts api/middleware/web`; `pages content/commands/editor/grants/web`; config urls/settings; page editor+four grant templates) plus `accounts/staff.py`, `pages/staff.py` and exact six templates `staff_create.html`, `staff_password.html`, `staff_list.html`, `staff_conflict.html`, `staff_deactivate.html`, `staff_reactivate.html`. It emits only `RB4_STAFF_ORIGINS_OK=23`.

## Evidence and cleanup

Bounded evidence only: images2/names3, PG tmpfs3/raw-Mounts[]/ports0, readiness attempt≤30, certificate marker, app readonly-source/ports0, origins23, discovery111, migrations/check result, `Ran 111 tests`, final state and tail≤600. Full Env/inspect/raw errors/paths/IDs remain forbidden.

Record nullable network/PG/app IDs immediately. One finally rechecks exact ID/name/run-label, stops only running recorded containers, removes app by ID and PG by ID with `rm -v`, proves stopped/absent, removes recorded endpoints0 network by ID, then removes only exact certificate leaf and empty task directory after identity/non-reparse checks. No name fallback, prune, broad delete, retry or fallback.

## No-bloat and stop rule

No source/test change during run; model/migration/dependency/image/volume/runner artifact0. Browser is unnecessary for fixed no-JS forms. B002/media/public/live/deploy/push remain closed. One explicit owner authorization is required after independent plan approval. Any first runtime error stops for result triage; no automatic retry.

## Run1 result and bounded remediation

Run1 passed every boundary through exact23 origins, exact111 discovery, migrations and system check0, then ran all111 tests in46.487s. Result was failures4/errors1 with all evidence confined to test contracts: four otherwise valid staff HTTP posts used Django Client's default multipart instead of the approved exact urlencoded wire, and one Save↔Deactivate fixture supplied the obsolete untyped payload shape. Test DB destruction and exact recorded cleanup passed. No product code, schema, dependency, image or runtime boundary changed during the run.

The remediation candidate is test-only: a local helper sends the existing staff HTTP dictionaries through `urlencode(..., doseq=True)` with exact `application/x-www-form-urlencoded`, and the one concurrency fixture uses the already authoritative Article payload envelope (`schema`, `allow_index`, typed media slots). It adds no product behavior, generic form helper, framework or second runner. Independent result/remediation review and then a fresh explicit owner authorization are required before one run2; no retry is currently authorized.

Independent D-1676 review accepted the negative result and approved this remediation with P1/P2/P3=0/0/0, product findings0 and no-bloat PASS. Intentional CSRF/auth-negative multipart calls remain unchanged, method/module arithmetic remains exact111 and the changed condition is material, so this is not an anti-loop recurrence. One fresh full exact111 run2, not a focused subset, is the next eligible action after explicit owner permission; it remains unauthorized now.

Run2 passed the full boundary: PG readiness4, certificate transport, readonly current source, origins23, discovery111, migrations and system check0, then111/111 OK in66.726s. Django destroyed only the isolated test DB; app state was exit0/OOM0/dead0/error-empty and recorded app/PG/network/certificate/task-directory cleanup passed with exact names absent. A host-side retrieval guard before harness invocation emitted a nonfatal malformed-regex diagnostic; exact stored execution ID and script length were still checked, the approved harness ran exactly once and all of its own evidence passed. Independent result review must classify this disclosed outer diagnostic before server-gate closure; no repeat is proposed.

Independent D-1678 result review ACCEPTED run2 with P1/P2/P3=0/0/0, product findings0, no-bloat PASS and repeat0. The outer malformed-regex diagnostic is classified as one host-wrapper tool error and does not invalidate the harness/runtime evidence. The staff server gate is closed; no additional run is required.
