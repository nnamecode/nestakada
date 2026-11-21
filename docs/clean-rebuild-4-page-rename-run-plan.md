# RB4 Page rename PostgreSQL gate

Дата: 2026-11-20. ID: `RB4-PAGE-RENAME-PG-001`. Статус: **D-1774 terminal `ACCEPTED_PASS / PAGE RENAME EXACT172`, P0/P1/P2=0/0/0, product0; source+PostgreSQL runtime gate complete; temporary coordinator/probe removed**.

## Purpose and exact suite

Один disposable PostgreSQL run выполняет принятый SiteSettings exact162 regression и два новых literal modules Page rename exact10, всего exact172. Полный закрытый список из17 labels:

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
- `modules.pages.tests.test_http_rename` —4.

Guarded ordinary Django5.2 runner обязан получить discovery exact172 до создания test DB. Success требует migrations applied, system check0, одной CR-tolerant timing-shaped строки `Ran 172 tests in <decimal>s`, отдельной standalone CR-tolerant строки `OK`, failures/errors/skips/expected-failures/unexpected-successes0, уничтожение только `estakada_page_rename_test`, app exit0/OOM0/dead0/`State.Error==""` и bounded marker `PASS172`.

Новые exact10 доказывают owner-only name validation/CAS/audit/rollback, command и GET↔rename PostgreSQL lock coherence, fixed private HTTP/CSRF/405/body cap/cache/no-reflection. Browser не нужен для fixed no-JavaScript form; public Route/renderer/navigation/media evidence не заявляется.

## Reused disposable boundary

Переиспользуется только независимо принятая финальная SiteSettings boundary по условиям, но не её удалённый runner и не прежнее разрешение:

- только уже установленные pinned PostgreSQL image `sha256:de3d5ee…b6eef7` и app/test image `sha256:782f53c…e39986`; pull/build/install0;
- fresh exact names `rb4-page-rename-pg`, `rb4-page-rename-tests`, `rb4-page-rename-net`, fresh label `nestakada.run=rb4-page-rename-pg-001-<uuid>`;
- internal bridge, ports0, named volumes0, Docker socket0; PostgreSQL data/socket/tmp и app tmp только tmpfs;
- synthetic TLS certificate только для exact PostgreSQL container name; synthetic base `estakada_page_rename_base`, test DB `estakada_page_rename_test`, real/imported data0;
- PostgreSQL/app readonly roots, cap-drop ALL, no-new-privileges, bounded CPU/memory/PID; app UID10001 и exact current `src` read-only;
- fixed labels only; wildcard discovery/source copy/filter/reorder/keepdb/retry/fallback0; `PYTHONPATH=/app` сохраняется.

Current-slice preflight до первого Docker object проверяет exact9 literal regular non-reparse source origins:

1. `src/config/urls.py`;
2. `src/modules/accounts/middleware.py`;
3. `src/modules/pages/commands.py`;
4. `src/modules/pages/web.py`;
5. `src/modules/pages/templates/pages/page_editor.html`;
6. `src/modules/pages/templates/pages/page_rename.html`;
7. `src/modules/pages/templates/pages/page_rename_conflict.html`;
8. `src/modules/pages/tests/test_rename.py`;
9. `src/modules/pages/tests/test_http_rename.py`.

Marker — только `RB4_PAGE_RENAME_ORIGINS_OK=9`. Coordinator дополнительно проверяет, что новые два literal modules дают ровно6+4 методов статически и guarded discovery остаётся authoritative172.

## Coordinator and evidence contract

Временный host coordinator создаётся только после одобрения этого плана. Он должен быть self-contained PowerShell, exact-SHA reviewed и удалён после independently accepted terminal result. Permanent runner artifact0.

Он переиспользует принятые границы SiteSettings run5:

- для каждого network/PG/app create output coordinator сначала находит единственный 64-hex candidate и немедленно записывает его по ссылке в nullable recorded ID, затем отдельно требует, чтобы весь output был ровно одной64hex строкой; поэтому warning/format rejection не может предшествовать identity-safe recording. Cleanup никогда не использует name fallback;
- PowerShell сохраняет global ErrorActionPreference, только один bounded `docker logs --tail 600 ... 2>&1` выполняет с local Continue, `$LASTEXITCODE` захватывается до finally, preference всегда восстанавливается; null/nonzero log exit fail closed;
- bounded output: origins9, images2, names3, internal network/ports0, PG tmpfs3/raw `Mounts=[]`/readiness≤30, app readonly-source/ports0, discovery172, migrations/check0, exact timing-shaped `Ran 172 tests in <decimal>s`, standalone `OK`, checked app marker `exit0/OOM0/dead0/error-empty` (только boolean empty proof, без raw `State.Error`), `PASS172`, cleanup categories0;
- запрещён вывод raw Env, secrets, certificate private key, passwords, full inspect, Docker IDs, paths, test payloads/names и unbounded logs;
- success parser отвергает skip/expected-failure/unexpected-success summaries и требует CR-tolerant standalone `OK`;
- source/test frozen на время run; model/migration/dependency/image/permanent artifact changes0.

Один `finally` recheck-ит exact recorded ID/name/run-label, останавливает только running recorded containers, удаляет app/PG по recorded IDs, доказывает их отсутствие, удаляет только recorded endpoints0 network, exact certificate leaf и verified task directory под `work`. Cleanup error не маскирует сохранённый primary ErrorRecord; выводятся только fixed cleanup failure categories.

## Stop rule and authorization

Любая первая coordinator/product/test/cleanup ошибка останавливает run для независимого result triage. Automatic retry, partial diagnostic container, alternate suite, fallback и повтор того же действия0. Failed run consumes permission; новый run возможен только после triage, materially changed reviewed condition и fresh explicit owner permission.

Этот документ не разрешает Docker. После independent plan review требуется отдельно подготовить и независимо проверить exact temporary coordinator. Только затем владелец может явно разрешить ровно один full exact172 run. Browser, media bytes/storage, live/deploy/push остаются закрыты.

## Run1 coordinator-preflight result and remediation

Freshly authorized run1 passed origins9, static rename6+4 and pinned images2, then stopped on the first exact-name absence check. `Invoke-Docker` correctly returned no pipeline objects for an empty `docker container ls`; `Assert-ObjectAbsent` assigned the conditional result without outer array materialization, so under `StrictMode Latest` `$lines` became null and `$lines.Count` raised `PropertyNotFoundStrict`. TLS/task directory/network/PG/app/test DB/discovery/tests0; no Docker create was reached. Coordinator reported cleanup errors0; exact post-audit confirmed containers0/networks0/task-directories0.

Independent triage: `ACCEPTED_FAIL / COORDINATOR PREFLIGHT`, P0/P1/P2=`0/1/0`, product findings0, privacy/no-bloat/anti-loop PASS. The sole remediation wraps the conditional empty-list result in `@(...)`. Audit confirmed all other expected-empty Docker list results already use arrays, while other conditional assignments are required scalars. Product/suite/runtime boundary unchanged. New exact coordinator SHA256 is `737E6A270E714F6EFE5EB18725A5CA16919E2B7B29DACB612CF6889654DE38BD`; PowerShell parser errors0 and diff-check PASS. Repeat static review is APPROVED0/0/0 with privacy/cleanup/no-bloat/anti-loop PASS. Run1 permission is consumed; a fresh explicit owner permission is mandatory before run2.

## Run2 PG-boundary result and remediation

Freshly authorized run2 passed origins9, static rename6+4, pinned images2, names3, in-memory TLS1 and internal network1. PostgreSQL creation then stopped at `PG_BOUNDARY_INVALID`: the pinned image declares parent `VOLUME /var/lib/postgresql`, while the coordinator mounted tmpfs only at child `/var/lib/postgresql/data`; Docker therefore attached one anonymous parent volume and `Mounts` was not empty. PG readiness/app/test DB/discovery/tests0. Built-in cleanup falsely reported PG/network cleanup failures because deprecated `docker stop --time 10` produced warning output rejected by the strict wrapper; exact read-only audit found only the recorded PG and network. Identity-safe emergency cleanup removed both plus the one exact observed anonymous volume; final audit containers0/networks0/new-volume0/task-directories0, and unrelated older volumes were untouched.

Independent triage: `ACCEPTED_FAIL / PG BOUNDARY + CLEANUP`, P0/P1/P2=`0/1/2`, product findings0, privacy/no-bloat/anti-loop PASS. The remediation mounts the accepted parent path `/var/lib/postgresql` as tmpfs while retaining `PGDATA=/var/lib/postgresql/data/pgdata`; uses `docker stop --timeout 10`; removes containers with `--volumes`; records any unexpected anonymous PG volume name before boundary validation and proves its absence after cleanup. Exact coordinator SHA256 is now `BA374FA70D6C6CC446B971EA50818F74BC090694CF018D3052ED2BE744980372`,557 lines; PowerShell parser errors0 and diff-check PASS. Repeat independent static review is APPROVED0/0/0 with privacy/cleanup/no-bloat/anti-loop PASS. Run2 permission is consumed. Docker rerun0; fresh explicit owner permission is mandatory before run3.

## Run3 TLS-preflight result and remediation

Freshly authorized run3 passed origins9, static rename6+4, pinned images2 and names3, then stopped at `TLS_RSA_PROVIDER_UNSUPPORTED`. On PowerShell7.6.9/.NET10, `RSA.Create(2048)` returned valid `System.Security.Cryptography.RSABCrypt`; the coordinator incorrectly required concrete `RSACng`, and its later `.Key.Export` expression was also provider-specific. TLS marker/network/PG/app/test DB/discovery/tests0. Cleanup errors0; exact read-only post-audit containers0/networks0/task-directories0.

Independent triage: `ACCEPTED_FAIL / COORDINATOR TLS PREFLIGHT`, P0/P1/P2=`0/1/0`, product findings0, privacy/no-bloat/anti-loop PASS. The minimal remediation removes the concrete-type gate, retains the previously accepted native RSACng PKCS#8 path, and uses capability-checked `ExportPkcs8PrivateKey()` for providers such as the observed RSABCrypt. RSA2048, certificate algorithm/SAN/lifetime, bounded PEM/base64 transport, Docker boundary and product suite remain unchanged. Exact coordinator SHA256 is `6E12131D55AFF31703B9DDCD2EF5FA73DEAECF760693F97AC989B461533F3314`,559 lines; parser errors0 and diff-check PASS. Independent static review is APPROVED0/0/0. A separately prepared bounded same-host in-memory TLS probe first received review0/1/0 for unsuppressed extension indices, then repeat review APPROVED0/0/0 at exact SHA256 `954EC929401151216FF14B3EE70D84D7C2CB2C06C716E79DDBF81D4EE459C32A`,93 lines/parser0; files/network/Docker/secrets0 and sole fixed PASS marker. Run3 permission is consumed. Separate explicit owner permission is required for exactly one probe; its result review precedes any fresh Run4 owner permission.

The owner authorized exactly one reviewed same-host probe. It returned exit0 with sole fixed marker `RB4_PAGE_RENAME_TLS_PROBE=PASS`; independent result review classified it `ACCEPTED_PASS / TLS REMEDIATION PROVED`, P0/P1/P2=`0/0/0`, product findings0. Files/network/Docker/secrets0 and privacy/no-bloat/anti-loop PASS. The current-provider CA/server certificate, PKCS#8 and bounded PEM condition is materially proved; repeat probe0. A fresh explicit owner permission is mandatory before one full exact172 Run4.

## Run4 post-discovery result and evidence remediation

Freshly authorized Run4 passed origins9, static rename6+4, pinned images2, names3, TLS1, internal network1, PostgreSQL boundary/readiness and app boundary. The app then exited nonzero after emitting a discovery marker. The coordinator exposed only `POST_DISCOVERY`, so DB setup/migrations, checks, suite execution/result and teardown could not be distinguished; bounded logs were correctly retrieved but then removed with the recorded container. Cleanup errors0 and exact post-audit containers0/networks0/task-directories0.

Independent triage: `ACCEPTED_FAIL / POST-DISCOVERY EVIDENCE GAP`, P0/P1/P2=`0/1/0`; product result UNDETERMINED with confirmed product findings0, privacy/cleanup/no-bloat/anti-loop PASS. The remediation adds success-only fixed markers after exact discovery, DB setup/migrations, system checks, bounded numeric suite result and DB teardown. First static review0/1/0 found an exit0 skip/expected-failure evidence gap. The suite marker is now parsed before exit branching: every valid result other than exact172/all-zero emits bounded numeric counts plus fixed `TEST_RESULT`, and missing/malformed suite evidence emits `SUITE_EXECUTION`. Raw logs, tracebacks, test names, payloads, paths and secrets remain suppressed. Existing bounded log retrieval, state/exit coherence and recorded-ID cleanup remain unchanged. Exact coordinator SHA256 is `7532B42AB496ABDD9884A7FF5913ED96DCE091D3FD0899565BD7B0C65FDAE44F`,647 lines; parser errors0 and diff-check PASS. Repeat independent static review is APPROVED0/0/0 with lifecycle/privacy/cleanup/no-bloat/anti-loop PASS. Run4 permission is consumed. Fresh explicit owner permission is mandatory before Run5.

## Run5 product-failure result and identity remediation

Freshly authorized Run5 passed all infrastructure boundaries and completed exact172. The bounded result was tests172/failures1/errors0/skips0/expected0/unexpected0 with fixed `TEST_RESULT`; PASS172 was absent. Cleanup errors0 and exact post-audit containers0/networks0/task-directories0. Independent triage classified `ACCEPTED_FAIL / PRODUCT TEST FAILURE IDENTITY GAP`, P0/P1/P2=`0/1/0`: one product-test failure is confirmed, but its identity is undetermined and static guessing is prohibited.

The evidence remediation uses a closed in-run mapping: exact rename tests map to opaque `REN-C01..C06` and `REN-H01..H04`; accepted regression tests reveal only one of 15 fixed module codes `BASE-M01..M15`; unknown or nonunique identities map to `UNKNOWN`. Only when the strict suite counts are failures1/errors0 may the host emit the single allowlisted code. Raw test identity, traceback, assertion values, payloads, paths and secrets remain suppressed. Exact coordinator SHA256 is `BC524C9D8554DD140BCD3E0BE364F8B2FACCD0E16E48701BC3553873D690B2D7`,713 lines; parser errors0, exact code literals10+15 and diff-check PASS. Independent privacy/no-bloat review is APPROVED0/0/0 and confirms all mappings, closed enum, `_SubTest`, state and cleanup. Run5 permission is consumed. Fresh explicit owner permission is mandatory before Run6; product source/tests remain unchanged until identity is proved.

## Run6 H01 result and assertion-site remediation

Freshly authorized Run6 reproduced exact172/failures1/errors0/all other negative categories0 and emitted the closed base code `REN-H01`; infrastructure boundaries, cleanup0 and post-audit0 remained clean. Independent triage classified `ACCEPTED_FAIL / REN-H01 ASSERTION-SITE GAP`, P0/P1/P2=`0/1/0`: the failure is confined to the first HTTP acceptance test, but all 14 assertion sites remain statically plausible and product changes would be guessing.

The remediation examines the already stored formatted failure only inside the app process. It requires the fixed H01 function and test-module path suffix, then maps the allowlisted assertion lines 46,47,51,52,53,60,61,62,64,67,68,69,70,71 to opaque `REN-H01-A01..A14`; missing, nonunique or unlisted evidence becomes `REN-H01-UNKNOWN`. Host output accepts a single closed site code only when base code is H01 and strict counts are failures1/errors0. Filename, line number, traceback, assertion/response values, payloads, paths and secrets never leave the container. Exact coordinator SHA256 is `C16C5884B90A27D929CCEC4088A15901D8EA0F7A0157AEE6CB828ED467C95C8F`,765 lines; parser errors0, site literals14 and diff-check PASS. Independent privacy/mapping review is APPROVED0/0/0 and confirms the Django failure-string parsing, all mappings, closed enum, host gate and cleanup. Run6 permission is consumed. Fresh explicit owner permission is mandatory before Run7; product source/tests remain unchanged.

## Run7 A01 result and test-only remediation

Freshly authorized Run7 reproduced exact172/failures1/errors0/all other negatives0 and emitted `REN-H01-A01`; infrastructure, cleanup0 and post-audit0 remained clean. Independent product triage classified `ACCEPTED_FAIL / TEST EXPECTATION DEFECT`, P0/P1/P2=`0/1/0`, product findings0. The established common staff-session redirect, accepted regressions, SiteSettings contract and the same rename test's stale-session branch use exact `/manage/login/`; only the new anonymous assertion expected an unapproved `?next=` variant.

The sole remediation changes that test expectation to exact `/manage/login/`. Production code, middleware, template, route and privacy behavior remain unchanged; exact10 remains6+4. HTTP rename test SHA256 is `0A68560969426B541C17FB558BB3BDDF319832C53F099D73361F81824AE2B03D`; runner remains SHA256 `C16C5884B90A27D929CCEC4088A15901D8EA0F7A0157AEE6CB828ED467C95C8F`; diff-check PASS. Independent source/privacy/no-bloat review is APPROVED0/0/0 and confirms the sole test diff plus unchanged production/runtime boundary. Run7 permission is consumed. Fresh explicit owner permission is mandatory before Run8.

## Run8 clean-suite result and success-oracle remediation

Freshly authorized Run8 passed infrastructure and app exit0. Before the host failure, strict markers proved discovery172, DB setup/migrations, checks, suite tests172 with failures/errors/skips/expected/unexpected0, no failure code/site and DB teardown. The first final log oracle then raised `PropertyNotFoundStrict`: its single timing-shaped `Ran 172...` match was a scalar without `.Count`. Cleanup errors0 and exact post-audit containers0/networks0/task-directories0.

Independent triage classified `ACCEPTED_FAIL / SUCCESS-ORACLE SCALARIZATION`, P0/P1/P2=`0/1/0`, product findings0. The clean suite is positive evidence, but terminal PASS172 is not claimed because the Ran/OK/PASS, negative/system-check/destruction and final app-state oracles did not all complete. The complete remediation array-materializes all three analogous Ran/OK/PASS filtered results; no other `).Count` sites remain. Exact coordinator SHA256 is `8D857F50321DEA9F954E63DA9F8476D0462C22F5EDC4C7C15B6E69338F6D595D`,765 lines; parser errors0 and diff-check PASS. Independent privacy/cleanup/no-bloat review is APPROVED0/0/0 and confirms strict terminal-oracle semantics plus unchanged cleanup. Run8 permission is consumed. Fresh explicit owner permission is mandatory before Run9.

## Run9 destruction-line result and remediation

Freshly authorized Run9 passed infrastructure, app exit0, discovery172, DB setup/checks, suite172/all-zero, failure-marker absence, custom teardown, Ran172, OK, internal PASS172, negative and system-check oracles. It stopped only at the textual destruction oracle: Django verbosity1 prints the fixed alias line without the test database name. Cleanup errors0 and post-audit0.

Independent triage classified `ACCEPTED_FAIL / DJANGO VERBOSITY-1 DESTRUCTION ORACLE`, P0/P1/P2=`0/1/0`, product findings0. Raising verbosity would enlarge bounded logs and is rejected. The generated runner now requires exactly alias `default` and exact configured TEST.NAME `estakada_page_rename_test` before teardown, calls the ordinary teardown, and emits the exact DB marker only after success. Host parsing separately requires that unique marker and one CR-tolerant standard verbosity1 `Destroying test database for alias 'default'...` line. Exact coordinator SHA256 is `B13582D4B5B94179E1166F874ADEE896FEA66FCC8764C3B9FCD9BE694DE220BF`,775 lines; parser errors0 and diff-check PASS. Independent privacy/cleanup/no-bloat review is APPROVED0/0/0 and confirms exact DB proof, ordinary teardown ordering and unchanged runtime boundary. Run9 permission is consumed.

## Run10 terminal result

Freshly authorized Run10 completed exit0 and emitted `RB4_PAGE_RENAME_APP_STATE=exit0/OOM0/dead0/error-empty`, `RB4_PAGE_RENAME_RESULT=PASS172` and cleanup errors0. The strict contract therefore proved origins9, static rename6+4, pinned images2, names3, TLS1, internal network, PostgreSQL/app boundaries, readiness, discovery172, DB setup/migrations, system checks, suite172 with failures/errors/skips/expected/unexpected0, Ran172, standalone OK, internal PASS172, exact test DB configuration and successful destruction, plus clean app state. Exact post-audit containers0/networks0/task-directories0.

Independent terminal review classified `ACCEPTED_PASS / PAGE RENAME EXACT172`, P0/P1/P2=`0/0/0`, product findings0; privacy/cleanup/no-bloat/anti-loop PASS. Temporary ignored coordinator and TLS probe were deleted and final absence proved. Page Rename source+PostgreSQL runtime gate is complete. The next bounded stage is Page Move requirements/acceptance/architecture planning and independent review; code, Docker, browser, live/deploy and push remain outside this result.
