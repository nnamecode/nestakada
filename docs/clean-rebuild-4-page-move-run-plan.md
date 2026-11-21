# RB4 Page move PostgreSQL gate

Дата: 2026-11-20. ID: `RB4-PAGE-MOVE-PG-001`. Статус: **D-1784 plan and exact coordinator independently APPROVED P0/P1/P2=0/0/0; explicit owner permission required for one exact184 run**.

## Purpose and exact suite

Один disposable PostgreSQL run выполняет independently accepted Page Rename exact172 regression и два новых literal Page Move modules exact12, всего exact184. Полный закрытый список из19 labels:

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
- `modules.pages.tests.test_move` —8;
- `modules.pages.tests.test_http_move` —4.

Guarded ordinary Django 5.2 runner обязан получить discovery exact184 до создания test DB. Success требует migrations applied, system check0, одной CR-tolerant timing-shaped строки `Ran 184 tests in <decimal>s`, отдельной standalone CR-tolerant строки `OK`, failures/errors/skips/expected-failures/unexpected-successes0, уничтожение только `estakada_page_move_test`, app exit0/OOM0/dead0/`State.Error==""` и bounded marker `PASS184`.

Новые exact12 доказывают `RB4-MOV-001..012`: owner-only CAS/audit/rollback, discovery→single ordered Page lock→exact revalidation, actual ancestry/cycle/before validation, immediate-unique staging including root/boundaries/headroom, preservation/navigation/URL, unrelated-generation invalidation, coherent GET↔move PostgreSQL locking, fixed private HTTP/CSRF/405/body cap/canonical wire/cap512/corrupt graph/no-reflection. Browser не нужен для fixed no-JavaScript form.

## Reused disposable boundary

Переиспользуются только независимо принятые условия Page Rename Run10, но не удалённый coordinator, старое разрешение или старые object names:

- только уже установленные pinned PostgreSQL image `sha256:de3d5ee…b6eef7` и app/test image `sha256:782f53c…e39986`; pull/build/install0;
- fresh exact names `rb4-page-move-pg`, `rb4-page-move-tests`, `rb4-page-move-net`, fresh label `nestakada.run=rb4-page-move-pg-001-<uuid>`;
- internal bridge, ports0, named volumes0, Docker socket0; PostgreSQL parent data path `/var/lib/postgresql`, socket/tmp и app tmp только tmpfs; container removal includes anonymous-volume cleanup and proof;
- synthetic TLS certificate only for exact PostgreSQL container name; synthetic base `estakada_page_move_base`, sole test DB `estakada_page_move_test`, real/imported data0;
- PostgreSQL/app readonly roots, cap-drop ALL, no-new-privileges, bounded CPU/memory/PID; app UID10001 and exact current `src` read-only;
- fixed labels only; wildcard discovery/source copy/filter/reorder/keepdb/retry/fallback0; `PYTHONPATH=/app` retained.

Current-slice preflight до первого Docker object проверяет exact9 literal regular non-reparse source origins:

1. `src/config/urls.py`;
2. `src/modules/accounts/middleware.py`;
3. `src/modules/pages/commands.py`;
4. `src/modules/pages/web.py`;
5. `src/modules/pages/templates/pages/page_editor.html`;
6. `src/modules/pages/templates/pages/page_move.html`;
7. `src/modules/pages/templates/pages/page_move_conflict.html`;
8. `src/modules/pages/tests/test_move.py`;
9. `src/modules/pages/tests/test_http_move.py`.

Marker — only `RB4_PAGE_MOVE_ORIGINS_OK=9`. Coordinator additionally proves exactly8+4 static test methods in the two literal modules; guarded Django discovery remains authoritative exact184.

## Coordinator and evidence contract

После independent approval плана создаётся новый temporary self-contained PowerShell coordinator. Он получает отдельный exact-SHA review и удаляется только после independently accepted terminal result. Permanent runner artifact0. Старый удалённый Page Rename coordinator не считается существующим артефактом и не восстанавливается через Git.

Coordinator обязан сохранить доказанные Run10 boundaries:

- every network/PG/app create output first yields a sole recorded 64-hex ID before separate exact-output validation; cleanup uses recorded IDs only, never name fallback;
- only one bounded `docker logs --tail 700 ... 2>&1` uses local Continue, captures `$LASTEXITCODE` before `finally` and restores global preference; null/nonzero log retrieval fails closed;
- bounded output: origins9, move methods8+4, images2, names3, TLS1, internal network/ports0, PG tmpfs3/raw `Mounts=[]`/readiness≤30, app readonly-source/ports0, discovery184, DB setup/migrations/check0, exact suite counts, timing-shaped `Ran 184 tests in <decimal>s`, standalone `OK`, exact configured/destructed test DB marker, checked app marker `exit0/OOM0/dead0/error-empty`, `PASS184`, cleanup categories0;
- suite result is parsed before app-exit classification: every valid non-clean result emits only bounded numeric counts and fixed `TEST_RESULT`; missing/malformed evidence is `SUITE_EXECUTION`;
- a closed failure identity map covers new move methods (`MOV-C01..C08`, `MOV-H01..H04`) and accepted regression modules only by fixed base-module codes; raw names, traceback, assertion values, payloads and paths never leave app container;
- forbidden output: raw Env, secrets, private key/password, full inspect, Docker IDs, Page names/placements, request bodies, test payloads and unbounded logs;
- source/test frozen during run; model/migration/dependency/image/permanent artifact changes0.

One `finally` rechecks exact recorded ID/name/run-label, stops only running recorded containers, removes app/PG by recorded IDs with volumes, proves their absence, removes only recorded network endpoints0/network, exact certificate leaf and verified task directory under `work`. Cleanup error never masks stored primary ErrorRecord; output uses fixed cleanup categories only.

## Result classification and stop rule

Terminal success is only `ACCEPTED_PASS / PAGE MOVE EXACT184` after independent result review confirms all success, state, DB-destruction, privacy, cleanup and post-audit oracles. Any first coordinator/product/test/cleanup error stops the run for bounded independent triage. Automatic retry, partial diagnostic container, alternate suite, fallback and repeated equivalent action0.

A failed run consumes permission. Another run requires triage, materially changed independently reviewed condition and fresh explicit owner permission. If the same error repeats after equivalent remediation without new evidence, anti-loop sets the task to owner-paused and no third attempt is made.

## Authorization boundary

Этот документ не разрешает Docker. После independent plan review требуется отдельно создать и independently review exact temporary coordinator. Только затем владелец может explicitly authorize exactly one full exact184 run. Browser, media bytes/storage, live/deploy/push remain closed.

## Run1 pre-TLS result and evidence remediation

Owner-authorized Run1 at approved SHA `927A5012…1BBB5A` passed origins9, static move8+4, pinned images2 and names3, then stopped with closed `COORDINATOR_FAILURE` before `TLS_OK`; network/PG/app/discovery/tests0. Cleanup errors0 and exact post-audit containers0/networks0/taskdirs0. Independent triage: `ACCEPTED_FAIL / PRE-TLS COORDINATOR EVIDENCE GAP`, P0/P1/P2=0/1/0, product findings0/result UNDETERMINED. Existing evidence cannot distinguish task creation/guard, TLS generation/provider, CA write/flush or CA validation, so no technical fix or full rerun is justified. Run1 permission is consumed; anti-loop has not triggered, but an equivalent rerun is forbidden.

Evidence-only remediation emits fixed success markers and maps every pre-TLS boundary to one safe category: `TASK_CREATE`, `TASK_GUARD`, `TLS_GENERATION`, `CA_WRITE`, `CA_VALIDATION`; raw exception/path/key/certificate data0. New coordinator SHA256 is `D06DBC1F7D9E8A52B0B72E7CF3F38175695BE4D04E47A5EEED69D096C4733F9C`,570 lines/parser0/diff-check PASS, Docker rerun0. It requires independent exact-SHA review. After approval, a separate reviewed bounded same-host pre-TLS probe and fresh owner permission must prove the changed evidence condition before any full Run2 gate.

The separately approved/authorized probe stopped at exact `TASK_CREATE`, cleanup0/post-audit taskdirs0. Independent triage: `ACCEPTED_FAIL / TEST HARNESS TASK_CREATE PARAMETER DEFECT`, P0/P1/P2=0/1/0, product0/UNDETERMINED. Static cause is exact: PowerShell `New-Item` has `-Path`, not `-LiteralPath`; the same statement explains full Run1. Minimal remediation changes that one parameter in both artifacts while retaining containment, nonexistence and component non-reparse guards. New probe SHA256 `8212C7DB53AD6721F0743F2503AA0E32F2A6DABEF613C80828CAA18531231064`; new coordinator SHA256 `539CAEC4BB449C6974A2ACEE1EEC35430FF83D01FA5E7C6E761A8D109360D4CD`; both parsers and diff-check PASS, execution0. Both require independent diff/exact-SHA review; probe permission is consumed and full Run2 remains closed.

The corrected probe was independently approved and separately authorized once. It again returned exact `TASK_CREATE`, cleanup0, with no `TASK_CREATED`/TLS/CA markers; post-audit taskdirs0. Independent triage: `ACCEPTED_FAIL / REPEATED TASK_CREATE — ANTI-LOOP OWNER-PAUSED`, P0/P1/P2=0/1/0, product0 and product/TLS/PostgreSQL/tests UNDETERMINED. Two authorized probe attempts produced the same localized error around a reviewed remediation. Per AGENTS.md the runtime branch is owner-paused: third probe, full coordinator rerun or guessed fix is forbidden. Eligible owner choices are keep paused, authorize read-only/static investigation of existing host/PowerShell evidence, or later approve a materially different diagnostic package with its own evidence/review/permission.
