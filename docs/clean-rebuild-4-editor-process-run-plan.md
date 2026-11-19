# RB4 process editor focused PostgreSQL gate

Дата: 2026-11-19. ID: `RB4-EDITOR-PROCESS-PG-001`. Статус: **completed by D-1594; run1 exact51/51 independently ACCEPTED P1/P2/P3=0/0/0, product0, no-bloat PASS**.

## Purpose and exact suite

This is the first runtime gate for independently approved `RB4-EDITOR-001B-S1-PROCESS`. It proves server/template/wire/PageCAS behavior only. Browser behavior remains a later, separately planned and authorized `process-editor-native` exact8 gate.

One disposable PostgreSQL run executes exactly:

- `modules.accounts.tests.test_http_auth` —16 methods;
- `modules.pages.tests.test_http_list` —9 methods;
- `modules.pages.tests.test_http_editor` —26 methods.

Preflight discovery must equal exact51 before Django creates a test database. Expected result: all migrations, system check0, `Ran 51 tests`, failures0/errors0/skips0 and exit0. The standard runner creates/destroys only `estakada_editor_process_test`. It executes real PageCAS, current/previous, media-usage preservation and audit rollback paths. Chromium/JS behavior is not claimed.

Current-source preflight uses only a workspace-derived, exact-parent-checked readonly `src:/review/src` bind; no backslash-escaped literal workspace path. It verifies the same ten literal regular non-symlink origins accepted by the price gate: accounts `api.py`, `middleware.py`, `web.py`; pages `content.py`, `commands.py`, `editor.py`, `web.py`; config `urls.py`, `settings/base.py`; pages `templates/pages/page_editor.html`. It emits only `RB4_PROCESS_ORIGINS_OK=10`. Process/rich/price JS is not executed by this server gate and remains browser evidence.

## Reused disposable boundary

Reuse the accepted D-1580 corrected lifecycle with only process names/counts:

- existing exact local app/PG images, `--pull=never`, build/install0;
- fresh run UUID and exact absent names `rb4-process-pg`, `rb4-process-tests`, `rb4-process-net`, label `nestakada.run=rb4-editor-process-pg-001-<uuid>`;
- one internal bridge, published ports0, other network0;
- PostgreSQL parent/socket/tmp tmpfs3, bind/volume mounts0, fixed caps/resources and internal TCP readiness≤30s;
- synthetic base `estakada_editor_process_base`, standard test DB `estakada_editor_process_test`, real/imported data0;
- app UID10001, readonly source, tmpfs, caps/resources; docs, media bytes, host secrets, Docker socket and named volumes0;
- bounded evidence only: exact ID/name/run-label/state/mount/port projections, origins/count output and bounded logs; full Env/inspect forbidden.

Network endpoints must be parsed with `ConvertFrom-Json -AsHashtable` and require an actual hashtable with `Count == 0`. Label identity uses the already accepted complete JSON label dictionaries, never nested Docker-template quoting. No persistent launcher, Compose file or new infrastructure is added.

## Cleanup and stop rules

Record nullable network/PG/app IDs immediately after each create. One `finally` rechecks exact ID+name+run-label, stops only a running recorded container, proves stopped, removes app by ID and PG by exact ID with `docker container rm -v`, proves any exact unexpected volume recorded from the PG projection absent, and removes the recorded network ID only after endpoints0. Final IDs/names must be absent. No prune, name fallback, broad enumeration deletion, retry or time inference.

Run plus recorded-ID cleanup require one explicit owner authorization after plan approval. Any first failure stops for diagnosis and independent triage; no automatic equivalent retry or fallback. Independent result review closes the server gate. Browser execution, S2/S3/S4, media/B002, real data, Nginx, live/deploy and push remain closed.

## No-bloat boundary

No source/code/test change, model/migration/dependency/image/volume/runner/serializer mirror or persistent test launcher. Exact51 reuses the accepted disposable pattern and does not rerun already closed price/rich Chromium suites.

## Run1 result

The one owner-authorized run proved PG pre-start tmpfs3/mounts0, TCP readiness on attempt4, current-source origins10, exact discovery51, all migrations and system check0. Accounts16+list9+editor26 passed exact51/51 in9.821s with failures/errors/skips0 and `OK`; the standard test database was destroyed. App state was exited/runningfalse/OOMfalse/deadfalse/exit0/error-empty, sourceRO1 and published ports0. Recorded app/PG/network cleanup returned OK and coordinator exit0. Independent result review is required before server-gate closure; browser exact8 remains unexecuted.
