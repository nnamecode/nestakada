# RB4 Publication focused PostgreSQL gate

Дата: 2026-11-19. ID: `RB4-PUBLICATION-PG-001`. Статус: **completed D-1687; run2 exact126/126 and cleanup independently ACCEPTED0/0/0, product0/no-bloat PASS, server gate closed, repeat0**.

## Purpose and exact suite

This is the first runtime gate for independently approved `RB4-SLICE-004A-PUBLICATION`. One disposable PostgreSQL run executes the already accepted staff regression exact111 plus the publication exact15:

- `modules.accounts.tests.test_http_auth` —16;
- `modules.pages.tests.test_http_list` —9;
- `modules.pages.tests.test_http_editor` —34;
- `modules.pages.tests.test_commands` —13;
- `modules.pages.tests.test_grants` —10;
- `modules.pages.tests.test_http_grants` —8;
- `modules.pages.tests.test_staff_lifecycle` —13;
- `modules.pages.tests.test_http_staff` —8;
- `modules.pages.tests.test_publication` —8;
- `modules.pages.tests.test_http_publication` —7.

Preflight discovery must equal exact126 before Django creates a test database. Expected result: migrations, system check0, `Ran 126 tests`, failures0/errors0/skips0 and exit0. Django creates/destroys only `estakada_publication_test`. The new exact15 prove publish/hide integrity, rollback, PostgreSQL locking/concurrency and fixed owner-only HTTP; a browser run is not claimed or needed for the fixed no-JavaScript form.

## Reused disposable boundary

Reuse the independently accepted `RB4-STAFF-PG-001` run2 boundary byte-for-condition, changing only exact names, label, base/test database, source-origin marker and suite/count:

- existing local PG/app images, pull/build/install0;
- fresh exact names `rb4-publication-pg`, `rb4-publication-tests`, `rb4-publication-net`, label `nestakada.run=rb4-publication-pg-001-<uuid>`;
- internal bridge, ports0, other networks0, Docker socket/named volumes0;
- PostgreSQL parent/socket/tmp tmpfs3 with the accepted exact sizes/modes, raw `Mounts=[]`, readonly root, bounded ownership bootstrap, standard entrypoint/privilege drop, fixed caps/resources and readiness≤30;
- bounded canonical-base64 extraction of the public synthetic TLS certificate with exact CreateNew/re-read/cleanup;
- synthetic base `estakada_publication_base`, test DB `estakada_publication_test`, real/imported data0;
- app UID10001, readonly exact current `src`, one tmpfs, caps/resources, ports0; docs/media/private data0.

Current-source preflight proves exact26 literal regular non-symlink product origins: the accepted staff exact23 plus `modules/media/api.py`, `modules/pages/templates/pages/page_publication.html` and `modules/pages/templates/pages/page_publication_conflict.html`. Publication tests are separately fixed by literal module names and exact discovery8+7; wildcard discovery and source-copy0. Marker is only `RB4_PUBLICATION_ORIGINS_OK=26`.

## Evidence, cleanup and stop rule

Bounded evidence only: images2/names3, PG tmpfs3/raw-Mounts[]/ports0, readiness≤30, certificate marker, app readonly-source/ports0, origins26, discovery126, migrations/check result, `Ran 126 tests`, final app state and tail≤600. Full Env/inspect/raw errors/paths/IDs remain forbidden.

Record nullable network/PG/app IDs immediately. One `finally` rechecks exact ID/name/run-label; stops only a running recorded container; removes app and PG only by recorded ID with `rm -v`; proves exact stopped/absent state; removes only the recorded endpoints0 network by ID; and removes only the identity-checked certificate leaf and empty exact task directory. No name fallback, prune, broad delete, retry or fallback.

No source/test change during the run; model/migration/dependency/image/volume/runner artifact0. B002, public renderer/navigation, media materialization, browser, live/deploy and push remain closed. Any first runtime error stops for independent result triage. One explicit owner authorization is required after independent plan approval.

## Run1 result and test-only candidate

Owner-authorized run1 passed images2/names3, PG tmpfs3/raw-Mounts[]/ports0, readiness4, bounded certificate transport, readonly current source, origins26, discovery126, migrations and system check0. It executed all126 tests in68.620s: regression111 and fourteen publication tests passed; one publication test failed because it asserted that the media participant was outside a transaction while its class inherits Django `TestCase`, which supplies an outer transaction. The participant correctly observed that transaction and therefore did not raise. Product finding0 observed; app exit1/OOM0/dead0/error-empty, isolated test DB destroyed, recorded app/PG/network/certificate/task-directory cleanup PASS and exact names absent. Retry0.

The minimal test-only candidate removes that assertion from the `TestCase` method and places it before the fixture/command work in the existing PostgreSQL `TransactionTestCase` method, where no implicit outer transaction exists. Exact methods/modules/discovery remain8+7=15 and suite126; product source, command behavior, schema, dependency, runner and runtime boundary changes0. Independent result/remediation review and a new explicit owner permission are required before any fresh run2.

Independent D-1685 result/remediation review returned `ACCEPTED_FAIL / REMEDIATION APPROVED`, P1/P2/P3=0/0/0, product findings0, no-bloat and cleanup PASS. The failure is solely an invalid test environment assertion; the moved assertion now exercises the real no-outer-transaction boundary without adding a class, method, helper or framework. This is a materially changed condition, not an anti-loop repeat. One fresh full exact126 run2 may be proposed only after new explicit owner permission; no focused subset or automatic retry.

Run2 passed the complete accepted boundary: images2/names3, tmpfs3/raw-Mounts[]/ports0, PostgreSQL readiness3, certificate transport, readonly current source, origins26, discovery126, migrations and system check0. All126 tests passed in65.948s with failures/errors/skips0 and `OK`; Django destroyed only `estakada_publication_test`. App exit0/OOM0/dead0/error-empty, and exact recorded app/PG/network/certificate/task-directory cleanup passed with names absent. Product/source changes during run0, retry0. Independent result review must accept the evidence before server-gate closure and WBS credit.

Independent D-1687 result review ACCEPTED run2 with P1/P2/P3=0/0/0, product findings0, no-bloat and cleanup PASS, repeat0. Regression111 and publication15 are closed together; no browser confirmation is required for the fixed no-JavaScript form. The publication mutation server gate is closed. B002, public renderer/navigation, media materialization, live/deploy and push remain separately closed.
