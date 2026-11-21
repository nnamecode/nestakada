# RB4 Page create PostgreSQL gate

Дата: 2026-11-20. ID: `RB4-PAGE-CREATE-PG-001`. Статус: **D-1819 COMPLETE — final exact184 at coordinator SHA `AEBF128C111853DB6BDBB6C991ED1C66FD80302E9DDA9996A0EE98D7F76EDE73` returned `PASS184`, clean app exit, cleanup0 and post-audit containers0/networks0; independent terminal review `ACCEPTED_PASS`, P0/P1/P2=0/0/0, product findings0**.

D-1816 original-cause run proved every error was PageCommandError/INITIAL_PAYLOAD and uniquely identified truthy empty media-slot mapping. D-1817 changed only the zero-reference guard to `any(media.values())`. The first confirmation improved failures3/errors9 to failures1/errors0, only CRT-C01; D-1818 triage found product0 and corrected its false `{}` expectation without weakening validation. D-1819 final confirmation passed exact184 with clean app exit, cleanup0 and post-audit0; independent terminal review accepted the result and closed Page Create source + PostgreSQL runtime.

D-1814 cause run produced safe failure phases but all nine errors remained OTHER/OTHER because unittest had formatted err tuples. D-1815 replaces formatted parsing with reviewed original err/tb hooks and pre-Docker SHA pins for all frame line authorities. Raw values/messages/paths remain closed. No original-cause run has occurred.

D-1812 evidence run reproduced3/9 and proved exact172 clean; all outcomes are exact12 CRT codes. D-1813 adds only validated anchored exception-class and structural frame/assertion phase aggregates with exact per-code/global sums; raw traceback/messages/paths remain closed. No cause-evidence rerun has occurred.

Full D-1810 reached suite184 and returned failures3/errors9 with coarse `MULTIPLE`, cleanup/post-audit0. Triage classified accepted fail0/1/0: product gate FAIL, cause undetermined. D-1811 replaces MULTIPLE with validated sorted per-safe-code failure/error summaries and exact sum oracles; raw test data remains closed. No evidence rerun has occurred.

Post-fix diagnostic D-1809 completed exit0 with `PG_READY=4`, `PG_DIAGNOSTIC=READY`, cleanup0 and exact post-audit containers0/networks0. This proves wrapper/cert/mode/entrypoint/readiness only. App/test DB/discovery/tests were intentionally skipped, so exact184 remains UNDETERMINED. Coordinator bytes are unchanged; any full run requires fresh permission.

Diagnostic D-1807 returned `PG_WRAPPER_START` with cleanup/post-audit0. Triage uniquely proved invalid first builtin `set -ceu`; D-1808 changes only it to `set -eu`, retaining correct outer `/bin/sh -ceu`. A same-code repeat requires anti-loop owner-pause. Full exact184 remains unauthorized.

Run2 (D-1805) proved all corrected PG boundary checks and invoked start, then stopped at coarse `PG_READINESS`; cleanup/post-audit0, app/test DB/tests0. Triage classified `ACCEPTED_FAIL / POSTGRESQL START-READINESS EVIDENCE GAP`, P0/P1/P2=0/1/0, product0. D-1806 adds reviewed `-PgReadinessDiagnosticOnly`: cause-safe fixed wrapper/state/local-log classes, no raw output, success stop immediately after readiness and before app. Full exact184 rerun is not authorized.

Run1 (D-1803) passed origins9/static8+4/images2/names3/TLS/CA/network, then stopped before PostgreSQL start at coarse `PG_BOUNDARY`; cleanup errors0 and exact post-audit containers0/networks0. Triage classified `ACCEPTED_FAIL / COORDINATOR PG BOUNDARY EVIDENCE GAP`, P0/P1/P2=0/1/0, product0, runtime UNDETERMINED. D-1804 removes the coarse/order-sensitive oracle: each PG/app scalar has a fixed private-safe failure code, and mounts are an order-independent exact destination set. No Run2 has occurred.

## Purpose and exact suite

Один disposable PostgreSQL run выполняет независимо принятый Page Rename exact172 regression и два новых literal Page Create modules exact12, всего exact184. Page Move modules намеренно исключены: их runtime branch D-1793/D-1794 owner-paused, и этот run не является обходом паузы или evidence для Move.

Полный closed list из19 labels:

- `modules.accounts.tests.test_http_auth` —16;
- `modules.pages.tests.test_http_list` —9;
- `modules.pages.tests.test_http_editor` —34;
- `modules.pages.tests.test_commands` —13;
- `modules.pages.tests.test_grants` —10;
- `modules.pages.tests.test_http_grants` —8;
- `modules.pages.tests.test_staff_lifecycle` —13;
- `modules.pages.tests.test_http_staff` —8;
- `modules.pages.tests.test_publication` —8;
- `modules.pages.tests.test_http_publication` —7;
- `modules.pages.tests.test_public_read` —10;
- `modules.pages.tests.test_legacy_plain_projection` —10;
- `modules.pages.tests.test_site_settings` —4;
- `modules.pages.tests.test_site_settings_commands` —7;
- `modules.pages.tests.test_http_site_settings` —5;
- `modules.pages.tests.test_rename` —6;
- `modules.pages.tests.test_http_rename` —4;
- `modules.pages.tests.test_create` —8;
- `modules.pages.tests.test_http_create` —4.

Guarded ordinary Django5.2 runner обязан получить discovery exact184 before test DB creation. Success requires migrations applied, system check0, exact suite counts184/failures0/errors0/skips0/expected-failures0/unexpected-successes0, one CR-tolerant timing-shaped `Ran 184 tests in <decimal>s`, standalone CR-tolerant `OK`, exact configured and destroyed `estakada_page_create_test`, app exit0/OOM0/dead0/empty State.Error and bounded marker `PASS184`.

Create exact12 prove `RB4-CRT-001..012`: exact19 valid aggregates, name/path/decoded private namespace, root/parent/gapped positions, lost-response replay and incompatible/partial/corrupt aggregate refusal, graph cycle/cap512/513/overflow, rollback, preservation/unpublished visibility, create-vs-create and create-vs-rename global CAS, coherent GET-vs-rename locks, fixed private HTTP/CSRF/body cap/405/status/no-reflection. Browser is unnecessary for the fixed no-JavaScript form.

## Reused disposable boundary

Only independently accepted Page Rename Run10 conditions are reused, not its deleted coordinator, old permissions, names or certificate files:

- installed pinned PostgreSQL image `sha256:de3d5ee43e308309e10730caead7dd880539d53f0275d977cd2f8c3f62b6eef7` and app/test image `sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986`; before any create, exact `docker image inspect` ID equality is required; pull/build/install0;
- fresh exact names `rb4-page-create-pg`, `rb4-page-create-tests`, `rb4-page-create-net`, label `nestakada.run=rb4-page-create-pg-001-<uuid>`;
- internal bridge, ports0, named volumes0, Docker socket0; PostgreSQL parent `/var/lib/postgresql`, socket/tmp and app tmp use tmpfs; removal includes anonymous volumes and exact absence proof;
- synthetic base `estakada_page_create_base`, sole test DB `estakada_page_create_test`, real/imported/user data0;
- PostgreSQL/app readonly roots, cap-drop ALL, no-new-privileges, bounded CPU/memory/PID; app UID10001 and exact current `src` read-only; `PYTHONPATH=/app`;
- literal labels only; wildcard discovery/source copy/filter/reorder/keepdb/retry/fallback0.

Current-slice preflight before first Docker object verifies exact9 literal regular non-reparse origins:

1. `src/config/urls.py`;
2. `src/modules/accounts/middleware.py`;
3. `src/modules/pages/commands.py`;
4. `src/modules/pages/web.py`;
5. `src/modules/pages/templates/pages/page_list.html`;
6. `src/modules/pages/templates/pages/page_create.html`;
7. `src/modules/pages/templates/pages/page_create_conflict.html`;
8. `src/modules/pages/tests/test_create.py`;
9. `src/modules/pages/tests/test_http_create.py`.

Marker is only `RB4_PAGE_CREATE_ORIGINS_OK=9`. Static parser additionally proves literal8+4 test methods; guarded Django discovery remains authoritative exact184.

## Materially different no-task-directory TLS boundary

Page Move runtime remains anti-loop paused after two corrected probes repeated `TASK_CREATE` while attempting to create a child task directory. This Page Create run must not call `New-Item` for a directory, must not create any task directory and must not run the old probe/coordinator.

The new temporary coordinator itself is prepared through the normal reviewed workspace edit. At execution it uses the already existing exact `work` directory only after proving it is a real non-reparse directory under repository root. A fresh canonical run UUID derives a closed set of exactly four absent leaf paths directly under `work`:

1. `rb4-page-create-<uuid>-ca.pem`;
2. `rb4-page-create-<uuid>-server.pem`;
3. `rb4-page-create-<uuid>-server-key.pem`;
4. `rb4-page-create-<uuid>-runner.py`.

No glob, subdirectory, alternate root or fallback path is permitted. Coordinator records canonical repo and `work` identities before any write. Immediately before **each** leaf CreateNew it re-resolves every repo→work component, proves unchanged exact canonical identity, directory type, non-reparse state and direct-parent containment. Each leaf is opened with exact .NET `FileMode.CreateNew`; the same open `FileStream` remains held through bounded write, `Flush(true)`, seek/readback and exact byte/hash equality, then closes. After close, exact leaf is lstat-checked regular/non-reparse/direct-parent with the recorded length/hash. Parent or leaf drift gives fixed `LEAF_GUARD` and no alternate write. TLS remains fresh RSA2048 with exact PostgreSQL container SAN, accepted provider-capability PKCS#8 export, bounded PEM bytes and CA validation. App runner is bounded UTF-8 no-BOM. Private key is never printed or added to Git.

Mount/transport is closed and asymmetric:

- PostgreSQL has exactly two readonly bind mounts: server certificate leaf → `/run/estakada-input/server.pem` and server key leaf → `/run/estakada-input/server-key.pem`. Its fixed entrypoint copies certificate into `/var/run/postgresql/server.pem` mode0644 and key into `/var/run/postgresql/server-key.pem` mode0600, both owned by postgres, on the already required tmpfs; it then starts PostgreSQL using only the tmpfs copies. Host binds are never configured as live PostgreSQL key paths;
- app has exactly three readonly binds: exact current `src` → `/app`, CA leaf → `/run/estakada-input/ca.pem`, runner leaf → `/run/estakada-input/runner.py`. No server key/certificate mount reaches app;
- inspect oracle requires PG `Mounts` exact2 and app `Mounts` exact3 with exact source/destination/type=bind/RW=false, plus exact HostConfig tmpfs entries. Named and anonymous volumes are exact0 for both containers. The obsolete `PG Mounts=[]` oracle is removed.

One finally block removes only the four exact recorded leaf paths. Immediately before **each** delete it repeats the canonical repo→work component identity/non-reparse/direct-parent proof and verifies exact leaf regular/non-reparse/recorded length+hash; any drift is fixed cleanup failure with deletion0 for that leaf. Missing already-clean leaves are accepted. Recursive deletion, parent deletion and alternate path0. Post-audit repeats component proof and requires all four leaves absent. This is a materially different execution condition, not a claim that Page Move's unresolved host cause is known.

## Coordinator and evidence contract

After plan approval a new temporary self-contained PowerShell coordinator is created, parser/diff checked and independently reviewed at exact SHA. It is removed only after an independently accepted terminal result. Permanent runner0.

Coordinator retains accepted Run10 identity/privacy semantics:

- every network/PG/app create output first records the sole 64-hex ID, then validates exact output; cleanup uses recorded IDs only and never name fallback;
- one bounded `docker logs --tail 800 ... 2>&1` with local Continue, immediate `$LASTEXITCODE` capture and restored global preference; null/nonzero retrieval fails closed;
- bounded markers only: origins9, create8+4, leaf preflight/write/TLS/CA validation, exact full image IDs2, names3, internal network/ports0, PG tmpfs3/exact bind mounts2/readiness≤30, app exact readonly binds3/ports0, volumes0, discovery184, DB setup/migrations/check0, suite numeric counts, Ran184, OK, configured/destroyed DB, app state, PASS184, cleanup categories0;
- suite result parsed before app-exit classification; valid non-clean result emits numeric counts plus fixed `TEST_RESULT`, malformed/missing evidence emits `SUITE_EXECUTION`;
- closed failure identity map uses `CRT-C01..C08`, `CRT-H01..H04` and accepted regression module codes only. Raw test names, tracebacks, assertion values, payloads, paths and submitted Page fields never leave the app container;
- forbidden output includes raw Env, secrets, key/certificate bytes, passwords, Docker IDs, full inspect, filesystem paths, request bodies and unbounded logs;
- source/tests frozen; models/migrations/dependencies/images/permanent artifacts unchanged.

Finally rechecks exact recorded ID/name/run-label, stops only running recorded containers, removes app/PG by recorded IDs with volumes, proves absence, removes only recorded endpoints0 network, then removes only four exact TLS/runner leaves. Cleanup error never masks stored primary ErrorRecord and emits fixed categories only.

## Result classification and stop rule

Terminal success is only `ACCEPTED_PASS / PAGE CREATE EXACT184` after independent result review confirms all suite/state/DB destruction/privacy/cleanup/post-audit oracles. Any first coordinator/product/test/cleanup error stops for bounded independent triage. Automatic retry, partial diagnostic container, alternate suite, fallback and equivalent repeated action0.

A failed run consumes permission. Another run requires cause-bearing triage, a materially changed independently reviewed condition and fresh explicit owner permission. Repeated same error after remediation triggers owner-paused anti-loop; no third equivalent attempt.

The first execution must treat any leaf-create failure as `LEAF_CREATE`, not `TASK_CREATE`; it stops before Docker and cleans already recorded leaves. It must not respond by creating a directory or choosing another path.

## Authorization boundary

This plan does not authorize Docker or leaf generation. After independent plan review, a new exact coordinator must be prepared and independently reviewed. Only then may the owner authorize exactly one Page Create exact184 run. Browser, media bytes/storage, Page Move runtime, live/deploy/push remain closed.
