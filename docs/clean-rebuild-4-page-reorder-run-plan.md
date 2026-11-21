# RB4 Page reorder PostgreSQL gate

Дата: 2026-11-21. ID: `RB4-PAGE-REORDER-PG-001`. Статус: **D-1828 apply_patch-only coordinator prepared and exact-SHA independently APPROVED P0/P1/P2=0/0/0; SHA `1CCB9D07BDDF287E2FB9B97A47CB622EBCE9FC24F67752733D347B7AA2F52282`, 989/923; fresh owner permission required for one exact196 run; Docker/runtime0**.

## Purpose and exact suite

Один disposable PostgreSQL run расширяет independently accepted Page Create exact184 двумя новыми literal Reorder modules exact12, всего exact196. Page Move modules намеренно исключены: их runtime branch остаётся owner-paused, и этот run не является обходом паузы или evidence для Move.

Полный closed list из21 labels:

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
- `modules.pages.tests.test_http_create` —4;
- `modules.pages.tests.test_reorder` —8;
- `modules.pages.tests.test_http_reorder` —4.

Guarded ordinary Django5.2 runner обязан получить discovery exact196 before test DB creation. Success requires migrations applied, system check0, suite196/failures0/errors0/skips0/expected-failures0/unexpected-successes0, one CR-tolerant timing-shaped `Ran 196 tests in <decimal>s`, standalone CR-tolerant `OK`, exact configured and destroyed `estakada_page_reorder_test`, app exit0/OOM0/dead0/empty State.Error and bounded `PASS196`.

Reorder exact12 prove `RB4-ROR-001..012`: access/session/CSRF and employee DOM isolation; root/non-root exact-set order; no-op/gap normalization; parent/set/cap/discovery-lock drift; preservation of URL/content/current+previous/grants/usages/gallery/SiteSettings values; promoted navigation order; literal position max with N1/N512 root/non-root; rollback and reorder-vs-rename CAS; deterministic audit-target branches; fixed no-JS wire/body-cap/405/status/no-reflection/private-cache matrix. Browser is unnecessary for this fixed ordinary HTML form.

## Reused disposable boundary

Only the independently accepted D-1819 Page Create terminal boundary is reused, not its permission or names. Images remain exact installed IDs, pull/build/install0:

- PostgreSQL `sha256:de3d5ee43e308309e10730caead7dd880539d53f0275d977cd2f8c3f62b6eef7`;
- app/test `sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986`.

Fresh exact names are `rb4-page-reorder-pg`, `rb4-page-reorder-tests`, `rb4-page-reorder-net`; label prefix `nestakada.run=rb4-page-reorder-pg-001-<uuid>`; synthetic base `estakada_page_reorder_base`; sole test DB `estakada_page_reorder_test`. Internal bridge/ports0, Docker socket0, named/anonymous volumes0, real/imported/user data0. PostgreSQL/app readonly roots, cap-drop ALL, no-new-privileges, bounded CPU/RAM/PIDs, exact tmpfs and app UID10001 remain unchanged. Literal labels only; wildcard discovery/filter/reorder/keepdb/retry/fallback0.

Before first Docker object the coordinator verifies exact12 literal regular non-reparse origins:

1. `src/config/urls.py`;
2. `src/modules/accounts/middleware.py`;
3. `src/modules/audit/models.py`;
4. `src/modules/pages/commands.py`;
5. `src/modules/pages/public.py`;
6. `src/modules/pages/web.py`;
7. `src/modules/pages/templates/pages/page_list.html`;
8. `src/modules/pages/templates/pages/page_editor.html`;
9. `src/modules/pages/templates/pages/page_reorder.html`;
10. `src/modules/pages/templates/pages/page_reorder_conflict.html`;
11. `src/modules/pages/tests/test_reorder.py`;
12. `src/modules/pages/tests/test_http_reorder.py`.

Marker is `RB4_PAGE_REORDER_ORIGINS_OK=12`; static parser requires literal8+4 Reorder methods. Exact SHA pins cover all12 origins before Docker so reviewed bytes, traceback identities and runner input cannot drift.

## No-task-directory TLS and transport

Page Move's repeated `TASK_CREATE` condition remains isolated. This run creates no task directory and uses the existing verified non-reparse `work` directory only. A fresh UUID derives exactly four absent direct leaves:

1. `rb4-page-reorder-<uuid>-ca.pem`;
2. `rb4-page-reorder-<uuid>-server.pem`;
3. `rb4-page-reorder-<uuid>-server-key.pem`;
4. `rb4-page-reorder-<uuid>-runner.py`.

The accepted D-1819 stable component identity, same-handle `CreateNew`/Flush/readback/hash, direct-parent containment, no-follow regular-file proof and exact identity delete are reused unchanged. No glob/subdirectory/fallback/alternate root. TLS is fresh RSA2048 with exact PostgreSQL SAN. Key bytes are never printed or committed.

PostgreSQL receives exact two readonly host binds (server cert/key) copied into postgres-owned tmpfs as0644/0600 before start. App receives exact three readonly binds (`src`→`/app`, CA, runner), no key/cert, plus bounded tmpfs. Inspect requires exact mounts/type/RW/source/destination, tmpfs, readonly root, ports0 and volumes0. PG wrapper uses accepted inner `set -eu` and outer `/bin/sh -ceu`; readiness≤30.

Finally removes only recorded app/PG IDs with volumes, exact network ID and the four exact verified leaves. Cleanup never uses name fallback, recursive delete or alternate path. Separate post-audit requires exact containers0/networks0 and all four leaves absent.

## Coordinator and evidence contract

After plan approval a new ignored temporary self-contained PowerShell coordinator is prepared, parser/diff checked and independently reviewed at exact SHA. It is not derived at runtime and is removed only after a separately authorized/accepted cleanup decision; permanent runner0.

Coordinator emits bounded markers only: origins12, source hashes12, static8+4, images2, names3, TLS/leaves/CA, internal network/ports0, PG exact mounts2/tmpfs/readiness, app mounts3/tmpfs, volumes0, discovery196, DB setup/migrations/check0, suite numeric counts, Ran196, OK, configured/destroyed DB, app state, PASS196 and cleanup categories0.

Failure identity is closed to `ROR-C01..C08`, `ROR-H01..H04`, accepted `CRT-C01..C08`/`CRT-H01..H04`, accepted regression `BASE-M01..M17`, and `UNKNOWN`. Each literal test ID maps to exactly one safe code. Non-clean suite emits only validated per-code failure/error counts whose global sums equal suite counts; raw names, traceback, exception/assertion values, request values, UUID lists, Page names, paths and payloads never leave the app container. This initial run does not add speculative traceback phase mapping. Malformed/missing evidence fails `SUITE_EXECUTION`; a clean suite may emit no failure summaries.

Forbidden output includes secrets, passwords, Env, Docker IDs, full inspect, TLS/key bytes, host paths, request bodies and unbounded logs. Log retrieval remains one bounded `docker logs --tail 800` with locally restored PowerShell preference. Source/test files are readonly; models/migrations/dependencies/images/permanent artifacts unchanged.

## Result and stop rules

Terminal success is only `ACCEPTED_PASS / PAGE REORDER EXACT196` after independent review confirms every suite/state/DB-destruction/privacy/cleanup/post-audit oracle. Any first coordinator/product/test/cleanup error stops; automatic retry, partial fallback, alternate suite and equivalent repeated action0.

A failed run consumes permission. Another run requires cause-bearing triage, a materially changed independently reviewed condition and fresh permission. Same failure after remediation triggers owner-paused anti-loop; no third equivalent attempt.

## Authorization boundary

This plan authorizes no Docker, TLS leaf creation or runtime. After independent plan approval a new exact coordinator must be prepared and independently reviewed. Only then may the owner authorize one Page Reorder exact196 run. Browser/media storage/Page Move/live/deploy/push remain closed.
