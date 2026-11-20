# RB4 partner-links editor focused PostgreSQL gate

Дата: 2026-11-19. ID: `RB4-EDITOR-LINKS-PG-001`. Статус: **completed by D-1615; corrected run2 exact55/55 independently ACCEPTED0/0/0, product0/no-bloat; repeat unnecessary**.

## Purpose and exact suite

This is the first runtime gate for independently approved `RB4-EDITOR-001B-S2A-LINKS`. It proves server/template/wire/PageCAS behavior only. Browser behavior remains a later, separately planned and authorized `links-editor-native` exact8 gate.

One disposable PostgreSQL run executes exactly:

- `modules.accounts.tests.test_http_auth` —16 methods;
- `modules.pages.tests.test_http_list` —9 methods;
- `modules.pages.tests.test_http_editor` —30 methods.

Preflight discovery must equal exact55 before Django creates a test database. Expected result: all migrations, system check0, `Ran 55 tests`, failures0/errors0/skips0 and exit0. The standard runner creates/destroys only `estakada_editor_links_test`. It exercises the real link projection/wire, valid empty/exact64, cap65/invalid HTTPS, replay/PageCAS, current/previous and existing audit rollback paths. Chromium/JS behavior is not claimed.

Current-source preflight uses only a workspace-derived, exact-parent-checked readonly `src:/review/src` bind. It verifies the same ten literal regular non-symlink origins accepted by the prior editor gates: accounts `api.py`, `middleware.py`, `web.py`; pages `content.py`, `commands.py`, `editor.py`, `web.py`; config `urls.py`, `settings/base.py`; pages `templates/pages/page_editor.html`. It emits only `RB4_LINKS_ORIGINS_OK=10`. Partner-links/rich/process/price JS is not executed by this server gate.

## Reused disposable boundary

Reuse the accepted D-1580/D-1592 lifecycle with only links names/counts:

- existing exact local app/PG images, `--pull=never`, build/install0;
- fresh run UUID and exact absent names `rb4-links-pg`, `rb4-links-tests`, `rb4-links-net`, label `nestakada.run=rb4-editor-links-pg-001-<uuid>`;
- one internal bridge, published ports0, other network0;
- PostgreSQL parent/socket/tmp tmpfs3, bind/volume mounts0, fixed caps/resources and internal TCP readiness≤30s;
- synthetic base `estakada_editor_links_base`, standard test DB `estakada_editor_links_test`, real/imported data0;
- app UID10001, readonly source, tmpfs, caps/resources; docs, media bytes, host secrets, Docker socket and named volumes0;
- bounded evidence only: exact ID/name/run-label/state/mount/port projections, origins/count output and bounded logs; full Env/inspect forbidden.

Network endpoints must be parsed with `ConvertFrom-Json -AsHashtable` and require an actual hashtable with `Count == 0`. Label identity uses complete JSON label dictionaries, never nested Docker-template quoting. No persistent launcher, Compose file or new infrastructure is added.

## Cleanup and stop rules

Record nullable network/PG/app IDs immediately after each create. One `finally` rechecks exact ID+name+run-label, stops only a running recorded container, proves stopped, removes app by ID and PG by exact ID with `docker container rm -v`, proves any exact unexpected volume recorded from the PG projection absent, and removes the recorded network ID only after endpoints0. Final IDs/names must be absent. No prune, name fallback, broad enumeration deletion, retry or time inference.

Run plus recorded-ID cleanup require one explicit owner authorization after plan approval. Any first failure stops for diagnosis and independent triage; no automatic equivalent retry or fallback. Independent result review closes the server gate. Browser execution, S2B reviews/media/B002, S3/S4/M, real data, Nginx, live/deploy and push remain closed.

## No-bloat boundary

No source/code/test change, model/migration/dependency/image/volume/runner/serializer mirror or persistent test launcher. Exact55 reuses the accepted disposable pattern and does not rerun already closed price/process/rich Chromium suites.

## Run1 pre-start result and changed condition

The owner-authorized run1 passed exact image/name/source preflight and recorded only its internal network and PG container. It stopped before PG start, app creation, discovery, migrations or tests because the coordinator expected configured tmpfs entries in Docker `.Mounts`. Recorded-ID cleanup removed the PG container with `-v`, removed the endpoints0 network and proved all exact names absent.

This is harness-only/product0. Docker's bounded projections have separate authorities. The run2 candidate parses JSON `.HostConfig.Tmpfs` with `ConvertFrom-Json -AsHashtable`, requires count3 and exact entries `/var/lib/postgresql=rw,nosuid,nodev,noexec,size=536870912,uid=999,gid=999,mode=0700`, `/var/run/postgresql=rw,nosuid,nodev,noexec,size=16777216,uid=999,gid=999,mode=3775`, `/tmp=rw,nosuid,nodev,noexec,size=33554432,mode=1777`. Separately, JSON `.Mounts` must be an array with count0, proving bind/volume0. Images/source/names/exact55/runtime command/identity/recorded-prefix cleanup remain unchanged. Independent repeat review and fresh owner authorization are required; no automatic retry.

## Corrected run2 result

The separately authorized run2 proved exact local images2 and reserved names absent3, PG HostConfig tmpfs3/Mounts0 before start, TCP readiness attempt4, app tmpfs1/readonly source1/published ports0, internal network true, current-source origins10 and discovery55. Django created/destroyed only `estakada_editor_links_test`, applied all migrations with system check0 and passed accounts16+list9+editor30=55/55 in10.544s with failures/errors/skips0 and `OK`. App state was exited/runningfalse/OOMfalse/deadfalse/exit0/error-empty. Recorded app/PG/network cleanup returned OK. Product finding0 observed; independent result review precedes server-gate closure and separate browser exact8.
