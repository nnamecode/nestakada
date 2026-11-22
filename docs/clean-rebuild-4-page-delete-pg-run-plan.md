# REBUILD-4 — Page Delete PostgreSQL exact208 run plan

Дата: 2026-11-21. ID: `RB4-PAGE-DELETE-PG-001`. Статус: **plan independently APPROVED D-1839. Run1/Run2/Run3 and the sole readiness-only diagnostic all stopped pre-app/pre-tests with cleanup0/post-audit0 and product `UNDETERMINED`; all executed SHAs/actions are superseded/no-repeat. Diagnostic SHA `C5731DB99C70280375D3CB48681322345A2D30DBCC8261B27143C11DE8DBB6C5` proved PG EXITED post-start/pre-readiness with OOM0/dead0/error-empty but not entrypoint/initdb cause. Branch owner-paused D-1844. Next only by owner decision: documentation/static materially different PG-entrypoint-exit classifier plan; runtime closed**.

## 1. Purpose and anti-loop boundary

Один будущий disposable PostgreSQL run должен проверить approved Page Delete source и регрессию без live/deploy/persistent apply. Арифметика закрыта: accepted base exact172 + Page Create12 + Page Reorder12 + Page Delete12 = **exact208** across literal23 test modules: base17 + Create2 + Reorder2 + Delete2. Page Move modules, browser/Playwright, public network, B002, fixture import, live data and broad discovery excluded.

D-1833 owner-paused host `.NET RandomNumberGenerator.Fill` TLS branch не повторяется и не дробится. Этот план запрещает host TLS/certificate/PEM leaves, CAPI2, TCP, Docker network и published ports. Materially different transport — PostgreSQL Unix-domain socket in one fresh ephemeral Docker named volume shared only by the recorded PostgreSQL and app containers. PostgreSQL authenticates the app with SCRAM password through exact `pg_hba.conf` local rule; `trust`, peer-only bypass and password output are forbidden.

No coordinator is prepared by this document. After plan approval a future apply_patch-only coordinator receives its own parser/diff/exact-SHA review. Execution then requires fresh explicit owner permission for exactly one run.

## 2. Exact disposable topology

Future coordinator uses the already pinned installed PostgreSQL/app image IDs from accepted Page Create/Reorder authority and verifies exact `docker image inspect .Id` equality before create. Fresh unpredictable bounded names identify exactly:

- one PostgreSQL container, exact UID/GID `999:999`, `--network none`, read-only rootfs, cap-drop ALL, no-new-privileges, memory/swap768MiB, CPU0.5, pids128 and ports0;
- one app test container, exact UID/GID `10001:10001`, `--network none`, read-only rootfs/source, cap-drop ALL, no-new-privileges, memory/swap768MiB, CPU1, pids128 and ports0;
- one named volume mounted at the official image path `/var/run/postgresql` in PostgreSQL and at `/run/estakada-pg` in app, nowhere else.

PGDATA stays in exact bounded tmpfs `/var/lib/postgresql:rw,nosuid,nodev,noexec,size=512m,uid=999,gid=999,mode=0700`; PostgreSQL also has exact `/tmp`32MiB tmpfs. Socket volume carries only socket/lock bytes, never PGDATA. It is a local-driver tmpfs volume with exact Options `type=tmpfs`, `device=tmpfs`, `o=uid=999,gid=999,mode=0777,size=16m`, so non-root UID999 can create the socket without entrypoint root/chown/helper. Server starts directly as999 with `listen_addresses=''`, socket directory `/var/run/postgresql`, `unix_socket_permissions=0777`, `password_encryption=scram-sha-256` and literal supported `POSTGRES_INITDB_ARGS=--auth-local=scram-sha-256 --auth-host=reject`. All active `pg_hba_file_rules` local rows must have no error and auth_method SCRAM before app start; any trust/peer local row stops. Synthetic DB/user/password are fresh and exist honestly in recorded container `Config.Env` until cleanup, not memory-only; coordinator never prints or inspects Env values and deletion of both containers is required.

App exact settings are `ESTAKADA_DB_HOST=/run/estakada-pg`, `ESTAKADA_TEST_DB_HOST=/run/estakada-pg`, `ESTAKADA_DB_PORT=5432`, and required but socket-ignored `ESTAKADA_DB_SSLROOTCERT=/dev/null`; existing `sslmode=verify-full` remains code-unchanged. Before migrations, app proves `/run/estakada-pg/.s.PGSQL.5432` is a socket, connection succeeds, `inet_server_addr() IS NULL`, server port5432 and `current_setting('listen_addresses')=''`. TLS/certificate/CA generation and network remain0.

The socket volume is created after exact pre-audit proves no same-name resource. Docker volumes have no container-like immutable ID, so coordinator records the closed tuple `(Name, Driver=local, Scope=local, exact sole run label, exact tmpfs Options above, canonical nonempty Mountpoint)` and revalidates equality before use/removal. Container mount projections use exact volume tuples `(Type=volume, Name=recorded, Destination, RW=true, Driver=local)`, not bind Source semantics. PG has exactly one mount plus two tmpfs; app has exactly three mounts (readonly source, readonly runner, socket volume) plus exact `/tmp:rw,nosuid,nodev,noexec,size=128m,uid=10001,gid=10001,mode=0700`. Each container has exactly the sole built-in `none` network attachment; user-defined networks0 and published port bindings0. Image-declared exposed-port metadata with a null binding is not a published port and is accepted only when exact `HostConfig.PortBindings` is null/empty and every `NetworkSettings.Ports` value is null; any non-null binding stops. Any unexpected mount/tmpfs/network/published-port/anonymous volume stops before migrations/tests. App starts only after bounded `pg_isready -h /var/run/postgresql -p 5432` in PG and the exact socket/HBA/settings proofs above.

## 3. Source and suite authority

Before Docker, coordinator resolves workspace/source without wildcard and requires the complete literal origin set. It extends the accepted Reorder12 origins with Page Delete-owned media API, two delete templates and two delete tests; all changed shared sources are exact SHA-pinned. Required origins are:

1. `src/config/urls.py`
2. `src/modules/accounts/middleware.py`
3. `src/modules/audit/models.py`
4. `src/modules/media/api.py`
5. `src/modules/pages/commands.py`
6. `src/modules/pages/public.py`
7. `src/modules/pages/web.py`
8. `src/modules/pages/templates/pages/page_list.html`
9. `src/modules/pages/templates/pages/page_editor.html`
10. `src/modules/pages/templates/pages/page_reorder.html`
11. `src/modules/pages/templates/pages/page_reorder_conflict.html`
12. `src/modules/pages/templates/pages/page_delete.html`
13. `src/modules/pages/templates/pages/page_delete_conflict.html`
14. `src/modules/pages/tests/test_reorder.py`
15. `src/modules/pages/tests/test_http_reorder.py`
16. `src/modules/pages/tests/test_delete.py`
17. `src/modules/pages/tests/test_http_delete.py`

Count is exact17 origins/hashes, mismatch or missing/unexpected path stops pre-Docker. Static inspection requires Delete8+4, Reorder8+4 and no Page Move label. Literal suite labels are base17 + Create2 + Reorder2 + Delete2 = **23 modules**; exact208 is method count. Coordinator must encode **23 literal modules / exact208 methods** and mechanically prove discovery208 before DB creation.

Delete identities are a closed map `DEL-C01..DEL-C08` and `DEL-H01..DEL-H04` matching the twelve literal method IDs. Existing Reorder/Create identities remain `ROR-*`/`CRT-*`; accepted base prefixes remain `BASE-M01..M17`. Any discovered ID outside exactly those groups is `UNKNOWN` and makes the run fail. Failure output is only validated per-code failure/error counts and global sums; raw test name, assertion, traceback, exception, SQL, UUID, URL, password, payload/hash and submitted confirmation values are never emitted.

## 4. Execution sequence and success

Future single run performs, in order:

1. workspace/origin/hash/static-count/image/name/tmpfs-volume-option/pre-audit checks;
2. create and record exact socket volume identity tuple;
3. create/start recorded PG container network-none, socket-only; readiness/settings/HBA proof;
4. create recorded app container network-none with readonly exact source and socket volume;
5. Django creates only fresh `estakada_page_delete_test`, applies migrations, `check` reports0;
6. exact23 labels discover and run exactly208, including PostgreSQL-gated Delete↔Rename and late-child/FK oracles;
7. require `Ran 208`, failures0/errors0/skips0, `OK`, test DB destroyed, app exit0/OOMKilled=false/dead=false/error-empty;
8. emit terminal `PASS208` only after all checks.

No rerun occurs automatically. A failure yields one closed stage and safe code summary; product result is `UNDETERMINED` unless exact test evidence identifies it. Same-stage repeat without new evidence triggers owner pause.

### 4.1 D-1843 readiness-only diagnostic boundary after Run3

Run3 on superseded SHA `3C72A3A377FB437FBD1DD3BB415EBC42ACC5B70C1F624ABA7DF7923E6C607ABC` passed all source/static/image/volume/PG container boundary, mount, tmpfs, network and published-binding checks, and `docker start` returned success, then exhausted the fixed readiness loop at coarse `PG_READINESS`. Cleanup/post-audit were clean; app/test DB/migrations/tests0 and product remains `UNDETERMINED`. This SHA must not repeat and the 30-attempt bound must not be guessed larger.

One future diagnostic-only mode may recreate the same reviewed PG half only and must never create the app container, test DB or run migrations/tests. It preserves the fixed 30-attempt loop and suppresses every raw command output. Every in-container probe uses a fixed `/bin/sh` wrapper which suppresses child stdout/stderr and translates only the child's result into a reserved sentinel exit namespace: `pg_isready` 0/1/2/3→40/41/42/43, socket yes/no→50/51, and PGDATA complete/incomplete→60/61. Only these exact host-observed sentinel codes count as probe evidence; every other `docker exec` code is transport/exec failure or unavailable. On readiness failure it emits exactly these fixed non-secret classifications, each once:

- container state: `RUNNING|EXITED`, plus separate `OOM=0|1`, `DEAD=0|1`, `ERROR=EMPTY|NONEMPTY`; the actual State.Error, exit text and logs are never read or emitted;
- last `pg_isready` outcome: `ACCEPTING|REJECTING|NO_RESPONSE|INVALID_PARAMETERS|EXEC_FAILURE`, mapping only sentinel codes40/41/42/43 and every other host code to `EXEC_FAILURE`;
- literal socket `/var/run/postgresql/.s.PGSQL.5432`: `YES|NO|UNAVAILABLE`, mapping only sentinel50/51 and every other host code to `UNAVAILABLE`;
- bounded PGDATA initialization: `COMPLETE|INCOMPLETE|UNAVAILABLE`, where sentinel60 means both literal `PG_VERSION` and `postgresql.conf` are regular files under the already fixed PGDATA, sentinel61 means the bounded condition is false, and every other host code means `UNAVAILABLE`; no content or path discovered from runtime is emitted.

If readiness succeeds, diagnostic-only mode emits only `READY` and stops before HBA/app/tests. If readiness fails, exact targeted state inspect must first succeed; inspect failure emits one fixed `DIAG_INSPECT_FAILURE` and does not fabricate state/probe facts. Otherwise it emits the four fixed classifications and terminal `NOT_READY`, then the unchanged recorded-ID/volume-tuple/runner cleanup and inventory audit run once. No logs, inspect JSON/raw value, env, password, SQL, file content, timestamps, process list, retry extension, TCP/network/TLS path or product change is permitted. The diagnostic coordinator requires parser/static/exact-SHA independent review, and its one execution requires fresh explicit owner permission. Any repeat of the same classified result without a new condition owner-pauses this diagnostic branch.

## 5. Cleanup and post-audit

Finally cleanup targets recorded container IDs, then the socket volume's literal recorded Name. It never enumerates a broad target for deletion and never removes by computed prefix. Container identity and the volume closed tuple are re-inspected immediately before removal; mismatch records cleanup failure and refuses guessed cleanup. Post-audit proves exact names/IDs/volume Name absent, no runner/TLS/certificate/task-directory leaves and no new networks. Pre-existing containers/networks/volumes are inventory-only exact identity sets before/after; unrelated resources are untouched.

On abnormal exit, cleanup still runs once. Volume removal failure is reported without retry or destructive fallback. No secret, DB dump, log tail, socket bytes or original media enters repository/output.

## 6. Acceptance

| ID | Required proof |
|---|---|
| `RB4-DEL-PG-001` | exact17 source origins/hashes and Delete8+4 static count before Docker |
| `RB4-DEL-PG-002` | literal23 labels, mechanical discovery208, Move0, closed identity/sum map |
| `RB4-DEL-PG-003` | pinned images; exact UIDs/read-only/cap-drop/no-new-privileges/resource caps; sole built-in none network, user-defined0, published port bindings0 (null exposed metadata accepted) |
| `RB4-DEL-PG-004` | exact-option tuple-identified tmpfs socket volume; PGDATA512MiB+PG tmp32MiB/app tmp128MiB; mount/tmpfs counts exact, no host leaves |
| `RB4-DEL-PG-005` | socket leaf + `inet_server_addr() IS NULL`, network/ports0, all effective local HBA SCRAM; credential lifetime limited to recorded Config.Env and never emitted |
| `RB4-DEL-PG-006` | fresh test DB only, migrations/check0, exact208 all pass including real concurrency/FK |
| `RB4-DEL-PG-007` | bounded private failure markers, no traceback/test values, no retry |
| `RB4-DEL-PG-008` | recorded container-ID + volume-tuple cleanup and before/after resource identity; socket volume removed |
| `RB4-DEL-PG-009` | model/migration/dependency/product change during run0; browser/live/deploy/push0 |
| `RB4-DEL-PG-010` | anti-loop: host TLS/RNG/CAPI2/cert path0; repeated same socket stage owner-pauses |

## 7. Stop line and gates

Stop before coordinator if Docker local-driver tmpfs volume options cannot be statically expressed/reviewed exactly, if images do not already support socket-only PostgreSQL/SCRAM with existing binaries, if shared socket requires privileged helper/root/chmod, if `/dev/null` plus existing verify-full does not remain socket-only, if source discovery is not exact208, or if cleanup cannot revalidate the sole volume tuple. Do not install a tool, enable Docker network/TCP, reuse the paused TLS path, weaken auth, add schema/product code or broaden tests to work around the stop.

Plan review gate is complete. Next requires separate owner agreement for an apply_patch-only coordinator and exact-SHA review. Even an approved coordinator does not authorize Docker execution.
