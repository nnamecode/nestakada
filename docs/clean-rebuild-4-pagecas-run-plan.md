# RB4 PAGECAS focused PostgreSQL run plan

Дата: 2026-11-18. ID: `RB4-PAGECAS-PG-001`. Статус: **completed by D-1521; run2 PASS13/13 and independent result ACCEPTED 0/0/0; repeat unnecessary**.

## Purpose and exact suite

One disposable PostgreSQL run verifies only D-1513 Save/Undo domain code. The exact test label is `modules.pages.tests.test_commands`; pre-run discovery must equal exactly 13 tests. The suite covers retained replay, operation conflict, stale CAS, auth-before-basis, employee text isolation, forbidden groups/Undo, exact provenance swap, current/previous media usages, missing/STAGED/wrong-purpose asset rejection, audit rollback and two-connection PostgreSQL winner/stale concurrency.

The Django test runner creates and destroys only `estakada_pagecas_test`. All clean-rebuild migrations and Django system checks must succeed before the 13 tests can be accepted. Success requires exact13 run, failures0, errors0, skips0, exit0 and independent result review.

## Disposable boundary

- existing local images only, each preflighted with `docker image inspect` and every create uses `--pull=never`; pull/build/install0: `nestakada-local/postgres:18.6-security-20261030` and `nestakada-local/app-editor:candidate-d330`;
- immediately before creation, exact names `rb4-pagecas-pg`, `rb4-pagecas-tests` and network `rb4-pagecas-net` must all be absent; any existing object refuses the run;
- one fresh UUID is generated in the bounded orchestrator and used only as exact label `nestakada.run=rb4-pagecas-pg-001-<uuid>` on both containers and the network. Three initially null in-memory slots record each successfully returned network, PG and app ID immediately after its create call; recorded IDs become the sole cleanup authority and names alone never authorize deletion;
- one new Docker `--internal` bridge, no published ports and no attachment to foundation/source/live networks;
- PostgreSQL exact tmpfs mounts: `/var/lib/postgresql/data:rw,nosuid,nodev,noexec,size=512m,uid=999,gid=999,mode=0700`, `/var/run/postgresql:rw,nosuid,nodev,noexec,size=16m,uid=999,gid=999,mode=3775`, `/tmp:rw,nosuid,nodev,noexec,size=32m,mode=1777`; no volume or host database/media mount;
- PostgreSQL root filesystem read-only, cap-drop ALL plus only the already foundation-approved entrypoint capabilities `CHOWN,DAC_OVERRIDE,FOWNER,SETGID,SETUID`, no-new-privileges, memory1GiB/CPU1/pids128;
- app root filesystem and host `src` mount read-only, UID/GID10001, cap-drop ALL, no-new-privileges, memory768MiB/CPU1/pids128; only `/tmp:rw,nosuid,nodev,noexec,size=128m,uid=10001,gid=10001,mode=1777` is writable;
- test source is mounted `T:\nestakada\src → /review/src:ro`; project docs/app/media/private data are not mounted;
- fixed synthetic DB password is test-only and passed only to the two disposable containers. It is not a user/project secret and must not be printed. Real credentials/data0.

## Test settings and command

PostgreSQL exact environment is `POSTGRES_DB=estakada_pagecas_base`, `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=<fixed synthetic value>`, `PGDATA=/var/lib/postgresql/data/pgdata`. D-1518 proved the bare hardened image intentionally keeps closed/default `listen_addresses`, so the exact disposable command is the argument array `postgres -c listen_addresses=* -c max_connections=30 -c log_statement=none -c log_min_error_statement=panic`; it listens only on container port5432 inside the internal network and no port is published. Readiness is at most30 attempts with one-second intervals using TCP explicitly: `pg_isready -h 127.0.0.1 -p 5432 -U postgres -d estakada_pagecas_base` through the retained PG container ID. This proves a TCP listener exists; the app connection separately proves the exact bridge DNS path `rb4-pagecas-pg:5432`. Timeout stops the run before app creation.

The app process runs from workdir `/review` as `python3 -B`, with `PYTHONPATH=/review/src` and `PYTHONDONTWRITEBYTECODE=1`. Exact settings are `DJANGO_SETTINGS_MODULE=config.settings.test`, `ESTAKADA_TEST_RUNTIME=1`, base `ESTAKADA_DB_NAME=estakada_pagecas_base`, test `ESTAKADA_TEST_DB_NAME=estakada_pagecas_test`, DB/test host `rb4-pagecas-pg`, DB/test user `postgres`, port5432, fixed synthetic DB password, bounded synthetic Django secret and allowed host `testserver`. `ESTAKADA_DB_SSLROOTCERT=/tmp/nonexistent-ca` satisfies only the required setting shape. Because this isolated internal network tests row locks/transactions rather than TLS transport, the inline process imports `config.settings.test` and changes only its in-memory `DATABASES["default"]["OPTIONS"]` to `{"sslmode": "disable"}` before `django.setup()`; no source/settings file changes and no broader network are permitted.

Before discovery, the inline process imports the production modules used by the command and verifies their resolved files equal the five literal container paths under `/review/src`: pages commands/content, accounts API, media API and audit API. It emits only `RB4_ORIGINS_OK=5`, never a host/container path; any mismatch fails before test DB creation.

The inline runner loads the exact label once to assert count13, then invokes the standard Django `DiscoverRunner` on the same exact label with keepdb=false and interactive=false. A count mismatch refuses the run before database creation. Django owns test DB creation/migrations/checks/destruction. No persistent launcher or custom test framework is added.

## Evidence and cleanup

Containers are named and not auto-removed until evidence is read. Required evidence:

1. PostgreSQL readiness on the exact retained container ID within30 seconds;
2. app formatted inspect only for `Status,Running,OOMKilled,Dead,ExitCode,Error` plus the exact run-label; `Config.Env` and full inspect are forbidden;
3. bounded app `docker logs --tail 500` containing origin marker5, exact discovered count, migration/check outcome, `Ran 13 tests`, failures/errors/skips and final exit; PostgreSQL logs are read only as bounded tail200 on failure and never include environment/inspect;
4. formatted network/container projections prove internal=true, published ports0, volume mounts0 and exact run-label/retained IDs without printing Env;
5. one `finally` handles the recorded creation prefix in reverse order on success, readiness timeout, create/start failure or test failure. If app ID was recorded, cleanup rechecks its exact name+run-label, stops it only if still running, proves stopped and removes only that ID. If PG ID was recorded, it performs the same checks, stops it only if running with a15-second timeout, proves stopped and removes only that ID. If network ID was recorded, cleanup rechecks its exact name+run-label and endpoints0, then removes only that ID. Null slots are never inspected or removed. Post-check proves every recorded ID and all exact names absent. Any identity/state mismatch refuses that deletion and returns the retained object to the owner; it never falls back from ID to name.

Run and exact cleanup require one explicit owner authorization after plan approval. If the first run fails, no automatic retry. Diagnose retained state/logs, independently review the result, then either make one bounded correction or stop under anti-loop.

## D-1518 run1 result and changed condition

Authorized run1 passed image/name preflight, PostgreSQL Unix-socket readiness, current-source origin5 and exact discovery13, then failed before test DB creation with TCP connection refused. Migrations/checks/tests executed0/0/0; app exit1/OOM0 and product findings0. Cleanup proved app/PG/network absent. Independent triage classified only `RB4-PAGECAS-PG-RESULT-P2-001`: readiness omitted TCP host while the image retained its documented closed bare listen policy. Run2 is permitted only after independent approval of the explicit server command and TCP readiness amendment above, followed by a fresh owner authorization. All other boundaries remain byte-for-byte unchanged; no automatic retry.

## D-1521 run2 result

Owner-authorized run2 used the approved TCP-listener changed condition. TCP readiness passed; current-source origin5 and exact discovery13 passed; Django created the isolated test DB, completed migrations/lifecycle and system check0, then all13 tests passed in0.526s with failures/errors/skips0 and exit0. Test DB was destroyed. App state was exited/runningfalse/OOMfalse/deadfalse/Error-empty. Recorded-ID cleanup proved app, PG and network absent. Independent result review `ACCEPTED`, P1/P2/P3=0/0/0. D-1513 PAGECAS domain code/runtime gate is closed; repeat0. HTTP/Nginx/live/real data remain separate gates.

## No-bloat boundary

No Compose service, launcher file, image, dependency, volume, repository/UoW, receipt/history, HTTP/UI/Nginx, source/media read, B002 workaround, live/deploy or push. If the existing images cannot provide the exact dependency/runtime boundary, stop instead of installing or building.
