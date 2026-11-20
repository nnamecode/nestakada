# RB4 PageGrant focused PostgreSQL gate

Дата: 2026-11-19. ID: `RB4-PAGEGRANT-PG-001`. Статус: **completed D-1665; run5 exact90/90 and cleanup independently ACCEPTED 0/0/0, product0, no-bloat PASS; server gate closed, repeat0**.

## Purpose and exact suite

This is the first runtime gate for independently approved code candidate `RB4-SLICE-003A-PAGEGRANT`. One disposable PostgreSQL run executes exactly:

- `modules.accounts.tests.test_http_auth` —16 methods;
- `modules.pages.tests.test_http_list` —9 methods;
- `modules.pages.tests.test_http_editor` —34 methods;
- `modules.pages.tests.test_commands` —13 methods;
- `modules.pages.tests.test_grants` —10 methods;
- `modules.pages.tests.test_http_grants` —8 methods.

Preflight discovery must equal exact90 before Django creates a test database. Expected result: all migrations, system check0, `Ran 90 tests`, failures0/errors0/skips0 and exit0. Standard Django runner creates/destroys only `estakada_pagegrant_test`. This proves existing auth/list/editor/PageCAS regressions plus exact hash, set/change/revoke, role/kind/group denial, stale409, no-change, audit rollback, actual User→Page→Grant→audit locks, two grant contenders, both Save↔Revoke outcomes, owner-only HTTP/CSRF/caps/projection and old-session revoke. Browser/JavaScript claims0 because the new flow is server-rendered no-JS.

Current-source preflight uses only a workspace-derived, exact-parent-checked readonly `src:/review/src` bind. It verifies exact15 literal regular non-symlink origins: accounts `api.py`, `middleware.py`, `web.py`; pages `content.py`, `commands.py`, `editor.py`, `grants.py`, `web.py`; config `urls.py`, `settings/base.py`; pages templates `page_editor.html`, `grant_staff_list.html`, `grant_employee.html`, `grant_form.html`, `grant_conflict.html`. It emits only `RB4_GRANT_ORIGINS_OK=15`.

## Reused disposable boundary

Reuse the accepted D-1636 lifecycle with grant-only names/counts:

- exact existing local app/PG images, `--pull=never`, build/install0;
- fresh run UUID and exact absent names `rb4-grant-pg`, `rb4-grant-tests`, `rb4-grant-net`, label `nestakada.run=rb4-pagegrant-pg-001-<uuid>`;
- one internal bridge, published ports0, other network0;
- PostgreSQL parent/socket/tmp tmpfs3 verified before start through exact `HostConfig.Tmpfs`, `Mounts0`, literal case-sensitive sizes `512m/16m/32m`, existing exact flags/uid/gid/modes, fixed caps/resources and internal TCP readiness≤30s;
- synthetic base `estakada_pagegrant_base`, standard test DB `estakada_pagegrant_test`, real/imported data0;
- app UID10001, readonly source, tmpfs, caps/resources; docs, media bytes, host secrets, Docker socket and named volumes0;
- bounded evidence only: exact ID/name/run-label/state/mount/port projections, origins/count output and bounded logs; full Env/inspect forbidden.

Network endpoints use `ConvertFrom-Json -AsHashtable` and require actual hashtable Count0. Label identity uses complete JSON label dictionaries. No persistent launcher/Compose/image/dependency is added.

## Cleanup and stop rules

Record nullable network/PG/app IDs immediately after each create. One `finally` rechecks exact ID+name+run-label, stops only a running recorded container, proves stopped, removes app by ID and PG by exact ID with `docker container rm -v`, proves any exact unexpected volume recorded from PG projection absent, and removes recorded network ID only after endpoints0. Final IDs/names absent. No prune, name fallback, broad deletion, retry or fallback.

Run plus recorded-ID cleanup require one explicit owner authorization after plan approval. Any first failure stops for independent triage; no automatic retry. Independent result review closes the server gate. B002/public composition, staff create/password/deactivate/reactivate, browser, Nginx, live/deploy and push remain closed.

## No-bloat boundary

No source/test change during the run, model/migration/dependency/image/volume/runner/persistent artifact0. Exact90 is the smallest combined suite that covers the touched accounts participant, shared grant policy used by command/editor, new grant domain/HTTP and their concurrency while retaining already accepted auth/list/editor behavior.

## Run1 accepted-fail and changed condition

Owner-authorized run1 passed images2/names3, exact PG tmpfs3/Mounts0/ports0 and readiness in4 checks. It then stopped at `CERT_COPY` before app create, origins/discovery, migrations, test DB or tests. The harness suppressed `docker cp` stderr and combined nonzero Docker exit with missing host leaf, so the exact transport cause was not retained. Product finding0. Recorded PG/network cleanup returned OK and exact app/PG/network names are absent; retry0.

`RB4-PAGEGRANT-RUN1-P2-001` changes only certificate transport/observability for a future separately authorized run2:

- create and resolve one isolated exact temp directory, prove its exact task-derived leaf name and expected `server.crt` absent;
- copy `container:/tmp/server.crt` to that directory, not to a nonexistent leaf path;
- distinguish constant `CERT_COPY_DOCKER` for nonzero Docker exit from `CERT_COPY_OUTPUT` for an invalid result, without printing raw stderr, host path or container ID;
- accept only exact `server.crt` that is a regular non-reparse leaf with size1..16,384 bytes;
- remove only that exact public synthetic certificate and then its empty exact directory in the existing finally.

PG/app/test boundaries, exact90/origins15, source/product/tests/images/names/tmpfs/network/cleanup remain unchanged. Static changed-condition review and fresh owner permission are required before run2; no automatic retry.

## Run2 anti-loop result and owner choice

Separately authorized run2 again passed images2/names3, exact PG tmpfs3/Mounts0/ports0 and readiness4. The approved split oracle then returned exact `CERT_COPY_DOCKER`: `docker cp` itself exited nonzero before host-output validation. App/origins/discovery/migrations/test DB/tests remained0. Recorded PG/network cleanup returned OK and exact names are absent. Product finding0.

This is the second failure on the same certificate-transport mechanism, so anti-loop sets **PAUSED_OWNER** and forbids run3 until a materially different mechanism is selected, documented, independently reviewed and freshly authorized.

`RB4-GRANT-CERT-Q001` owner choice D-1654:

1. **Selected/light:** remove `docker cp`. One fixed `docker exec` against the recorded/identity-checked running PG ID invokes exact `/usr/bin/timeout -s KILL 5 /bin/sh -ceu <literal script>`. The script silently proves `/tmp/server.crt` is a non-symlink regular file, `stat` size1..16384, then `exec openssl base64 -A -in /tmp/server.crt`; success stdout therefore contains only canonical base64. Missing timeout/stat/openssl or any check gives constant `CERT_EXEC` and stops; stderr/raw error/path/ID are captured but never printed.
2. Host requires output type string, ASCII length4..21848 divisible by4 and full-string .NET regex `\A[A-Za-z0-9+/]+={0,2}\z`; padding may occur only at the end. Any whitespace, CR/LF or added character gives `CERT_OUTPUT` before `.NET Convert.FromBase64String`. Decoded bytes must be1..16384, every byte ASCII, begin exact `-----BEGIN CERTIFICATE-----\n`, end exact `-----END CERTIFICATE-----\n`; the exact ASCII PEM is then accepted only by `X509Certificate2.CreateFromPem(...)`, and the object is immediately disposed. Any mismatch gives constant `CERT_OUTPUT`.
3. Before exec, the exact task directory identity is proved and exact `server.crt` must be absent. Host creates only that leaf with `.NET FileStream(FileMode.CreateNew, FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough)`, writes all bytes, `Flush(true)`, closes once, then requires exact regular non-reparse size and byte-for-byte re-read equality. Create/write/close/re-read ambiguity gives constant `CERT_WRITE`; no overwrite/retry.
4. Existing finally deletes only the exact leaf after identity/reparse check and then the exact empty task directory. Shared bind/volume/helper-container transport remains rejected as unnecessary scope and maintenance bloat.

Option1 changes only public synthetic certificate transport. Exact90/origins15/product/source/tests/PG/app/network/cleanup remain unchanged. Selection itself does not authorize runtime.

## Run3 pre-start result

Owner-authorized run3 passed existing local images2 and exact absent names3, then created only its recorded internal network and PostgreSQL container. It stopped before PostgreSQL start/readiness, certificate transport, app creation, origins, discovery, migrations, test DB or tests because the harness parsed the exact JSON empty mount array `[]` through the PowerShell pipeline: the zero-element result became `$null`, while the oracle incorrectly required a non-null value before checking count0. This is a harness projection error; product/source/tests were not executed or changed. The recorded PG ID was removed with `docker container rm -v`, the recorded endpoints0 network ID was removed, and exact names are absent. Automatic retry0; independent result triage and a reviewed materially changed empty-array oracle are required before any fresh owner permission.

Independent triage accepted the failed run P1/P2/P3=0/1/0, product findings0, cleanup PASS and no-bloat PASS. `RB4-PAGEGRANT-RUN3-P2-001` replaces only the defective parsed-array condition: after the already bounded successful Docker capture, require the raw output to be exact case-sensitive `[]`; `null`, `{}`, whitespace, added characters or any mount element reject as `PG_MOUNTS`. No ConvertFrom-Json/NoEnumerate helper or general parser is added. All images/names/tmpfs/ports/start/readiness/base64 certificate/app/source/exact90/evidence/cleanup conditions remain unchanged. This is the first occurrence of this new oracle defect; repeat static review and fresh explicit owner permission are required before one run4, and any equivalent repeat must stop under anti-loop.

## Run4 readiness result

Owner-authorized corrected run4 passed images2/names3 and exact PostgreSQL HostConfig tmpfs3, raw `Mounts=[]` and published ports0. PostgreSQL then failed before readiness: the retained bounded log contained only `mkdir: cannot create directory '/var/lib/postgresql/data': Permission denied`. Certificate extraction, app creation, origins, discovery, migrations, test DB and tests all remained0. Recorded PG and endpoints0 network IDs were removed and exact names are absent. Product/source/tests were unchanged. Automatic retry0; independent result triage must determine whether this is the first distinct runtime condition or an anti-loop recurrence and must review any proposed bounded remediation before fresh owner authority.

Independent triage accepted the failed run P1/P2/P3=0/1/0, product findings0, cleanup PASS and no-bloat PASS. Requested HostConfig uid/gid/mode does not prove effective ownership, so the evidence cannot distinguish ignored tmpfs ownership options from wrapper UID/write-traverse mismatch. Broad mode changes are rejected: 0750 adds no group write, 0770 depends on an unproved group, and 1777 weakens the parent unnecessarily. Owner choice `RB4-PAGEGRANT-PGOWNER-Q001`: option1/recommended is a bounded root pre-entrypoint wrapper that exact-chowns/chmods only `/var/lib/postgresql` and exact `PGDATA` to postgres:postgres/0700, proves numeric ownership/mode with constant safe failure, then execs the standard entrypoint which performs the normal privilege drop; existing readonly root, tmpfs, capabilities, exact90 and cleanup remain. Option2 runs one diagnostic-only bounded id/stat probe and no tests. Either choice requires static review and a fresh explicit runtime permission; no run is authorized now.

Owner choice D-1662 selects option1. `RB4-PAGEGRANT-RUN4-P2-001` changes only the existing in-container root pre-entrypoint script. Before certificate creation it requires `/var/lib/postgresql` to be an actual non-symlink directory and exact `/var/lib/postgresql/data` to be absent; it exact-chowns/chmods the parent to numeric999:999/mode0700, creates only `data` and exact `PGDATA=/var/lib/postgresql/data/pgdata`, and exact-chowns/chmods each to999:999/0700. It then requires all three paths to be non-symlink directories and each `stat -c '%u:%g:%a'` to equal exact `999:999:700`; any command/check failure becomes constant host result `PG_BOOTSTRAP`, with no raw error/path/ID printed. Only after this proof does the unchanged wrapper generate the synthetic TLS key/cert and `exec docker-entrypoint.sh postgres ...`; the standard entrypoint retains its normal privilege drop and database initialization. Rootfs readonly, tmpfs keys/options, caps, network, images, certificate transport, app, exact90, evidence and cleanup are unchanged. A helper/file/general ownership layer, chmod1777, new capability and diagnostic run are absent. Independent static review and fresh owner authorization are required before one run5; runtime remains unauthorized.

## Run5 pass result

Owner-authorized corrected run5 passed images2/names3, exact tmpfs3/raw-Mounts[]/ports0, bounded ownership bootstrap, PostgreSQL TCP readiness on attempt4, bounded-base64 certificate validation/write/re-read and app readonly-source/no-port boundary. Current source proved exact origins15 and discovery90. Django created and destroyed only `estakada_pagegrant_test`, applied all migrations, reported system check0 and passed accounts16+list9+editor34+commands13+grants10+grantHTTP8 = exact90/90 in13.796s with failures/errors/skips0 and `OK`. App state was exited/runningfalse/OOMfalse/deadfalse/exit0/error-empty. Recorded app, PG and endpoints0 network IDs plus exact public certificate leaf and empty task directory were removed; exact names are absent. Product/source/tests were unchanged during execution. Independent result review is required before server-gate closure; browser, B002/media, live/deploy and push remain outside this gate.
