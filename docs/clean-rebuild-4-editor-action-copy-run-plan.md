# RB4 action-copy editor focused PostgreSQL gate

Дата: 2026-11-19. ID: `RB4-EDITOR-ACTION-PG-001`. Статус: **completed by D-1636; run4 exact59/59 independently ACCEPTED0/0/0, product0/no-bloat; repeat0**.

## Purpose and exact suite

This is the first runtime gate for independently approved `RB4-EDITOR-001B-S3A-ACTION-COPY`. It proves only server/template/wire/PageCAS behavior. Browser behavior remains a later separately reviewed and authorized `action-editor-native` exact8 gate.

One disposable PostgreSQL run executes exactly:

- `modules.accounts.tests.test_http_auth` —16 methods;
- `modules.pages.tests.test_http_list` —9 methods;
- `modules.pages.tests.test_http_editor` —34 methods.

Preflight discovery must equal exact59 before Django creates a test database. Expected result: all migrations, system check0, `Ran 59 tests`, failures0/errors0/skips0 and exit0. The standard runner creates/destroys only `estakada_editor_action_test`. It exercises owner/actions projection, employee disclosure0, count0/exact32/cap33/context drift, exact closed multipart wire, title/body-only candidate preservation, current/previous banner usages, replay/PageCAS/audit and the already covered error/rollback paths. Chromium/JS behavior is not claimed.

Current-source preflight uses only a workspace-derived, exact-parent-checked readonly `src:/review/src` bind. It verifies the same ten literal regular non-symlink origins accepted by prior editor gates: accounts `api.py`, `middleware.py`, `web.py`; pages `content.py`, `commands.py`, `editor.py`, `web.py`; config `urls.py`, `settings/base.py`; pages `templates/pages/page_editor.html`. It emits only `RB4_ACTION_ORIGINS_OK=10`. JavaScript is not executed by this server gate.

## Reused disposable boundary

Reuse the accepted D-1615 lifecycle with action-only names/counts:

- existing exact local app/PG images, `--pull=never`, build/install0;
- fresh run UUID and exact absent names `rb4-action-pg`, `rb4-action-tests`, `rb4-action-net`, label `nestakada.run=rb4-editor-action-pg-001-<uuid>`;
- one internal bridge, published ports0, other network0;
- PostgreSQL parent/socket/tmp tmpfs3 verified through exact `HostConfig.Tmpfs`, separate bind/volume `Mounts0`, fixed caps/resources and internal TCP readiness≤30s;
- synthetic base `estakada_editor_action_base`, standard test DB `estakada_editor_action_test`, real/imported data0;
- app UID10001, readonly source, tmpfs, caps/resources; docs, media bytes, host secrets, Docker socket and named volumes0;
- bounded evidence only: exact ID/name/run-label/state/mount/port projections, origins/count output and bounded logs; full Env/inspect forbidden.

Network endpoints must be parsed with `ConvertFrom-Json -AsHashtable` and require an actual hashtable with `Count == 0`. Label identity uses complete JSON label dictionaries. No persistent launcher, Compose file or new infrastructure is added.

## Cleanup and stop rules

Record nullable network/PG/app IDs immediately after each create. One `finally` rechecks exact ID+name+run-label, stops only a running recorded container, proves stopped, removes app by ID and PG by exact ID with `docker container rm -v`, proves any exact unexpected volume recorded from the PG projection absent, and removes the recorded network ID only after endpoints0. Final IDs/names must be absent. No prune, name fallback, broad enumeration deletion, retry or time inference.

Run plus recorded-ID cleanup require one explicit owner authorization after plan approval. Any first failure stops for diagnosis and independent triage; no automatic equivalent retry or fallback. Independent result review closes the server gate. Browser execution, S3B structure, media/B002, S4/M, real data, Nginx, live/deploy and push remain closed.

## No-bloat boundary

No source/code/test change, model/migration/dependency/image/volume/runner/serializer mirror or persistent test launcher. Exact59 reuses the accepted disposable pattern and does not rerun already closed rich/price/process/links browser suites.

## Run1 pre-start result and changed condition

The owner-authorized run1 passed exact images2/names3 and created only its recorded internal network and PG container. It stopped before PG start/readiness/app/discovery/migrations/test DB/tests because the pre-start harness compared each `HostConfig.Tmpfs` option value as one order-sensitive raw string and returned `PG_TMPFS_VALUE`. Identity-checked finally removed only the recorded PG/network IDs, returned cleanup OK and proved all exact names absent. Product finding0; runtime tests0; retry0.

The changed condition keeps exact tmpfs keys3 and separate `Mounts0`, but treats comma order as non-authoritative. Each value is split on comma and must have no empty or duplicate token. A closed parser requires exact flag set `rw,nosuid,nodev,noexec`, exact one `size`, and only the applicable exact `uid`, `gid`, `mode`; unknown/missing/multiple key-value options reject. `size` must match strict decimal bytes and equal536870912 for `/var/lib/postgresql`,16777216 for `/var/run/postgresql`,33554432 for `/tmp`; uid/gid remain999, modes remain exact0700/3775/1777. No unit aliases or alternative options are admitted. Images, source, names, exact59, runtime command, identity and cleanup are unchanged. Repeat review and fresh explicit owner permission are required before one run2.

## Run2 anti-loop result and owner choice

The separately authorized run2 repeated the same bounded prefix and reached the changed parser, but stopped at its strict decimal `size` regex because the current Docker HostConfig retains a non-decimal size representation. PG start/readiness/app/discovery/migrations/test DB/tests remained0; product finding0; recorded PG/network cleanup again returned OK and exact names are absent. This is the second equivalent pre-start tmpfs-oracle failure, so anti-loop forbids run3 and pauses the task to the owner.

The recommended light option is to keep the duplicate-free closed token-set parser but require only the exact case-sensitive size literals already used by create: parent `512m`, socket `16m`, `/tmp` `32m`; no aliases or general unit parser. Alternative: change only create inputs to exact decimal byte literals and retain decimal checks. A post-start effective-mount oracle would add process/mount semantics and weaken the pre-start boundary, so it is a bloat-prone non-recommended option. Any selected condition requires independent review and a fresh explicit run permission.

Owner choice D-1629 selects the light option. The next candidate requires the exact literal token `size=512m` for `/var/lib/postgresql`, `size=16m` for `/var/run/postgresql` and `size=32m` for `/tmp`; comparisons are case-sensitive. All other closed tokens remain exact, and unknown/missing/duplicate/alternative size forms reject. No size conversion or post-start mount check is added. Run3 stays closed until independent review and fresh permission.

## Run3 test result and fixture-only remediation

The separately authorized run3 passed the full disposable boundary, origins10, discovery59, migrations and system check0, then completed57 tests with one failure and one error in11.163s. The isolated test DB was destroyed, app exited1 and recorded cleanup returned OK. Independent triage found product0 and two fixture-only P2: the count0/exact32 test called a helper twice with the same root sibling position4, and the projection fixture supplied a query outside the existing internal-URL allowlist.

D-1632 changes only test data: the helper accepts explicit position and the second same-test page uses5; the projection fixture and assertion use canonical `/actions/?page=1`. The production DB constraint and URL validator remain unchanged. Independent code review and fresh owner permission are required before one full exact59 rerun.

First repeat review found that the same second fixture would next collide on unique Route.target. D-1633 therefore gives the helper an explicit target default and uses canonical `/actions-exact32/` only for the second page. The production Route constraint and runtime code remain unchanged; another independent static review is required.

## Run4 accepted result

The separately authorized run4 passed exact images2/names3, exact-literal tmpfs3/Mounts0, PG readiness4, app tmpfs1/readonly source1/ports0, origins10 and discovery59. Django created and destroyed only `estakada_editor_action_test`, completed migrations with system check0 and passed accounts16+list9+editor34=59/59 in10.948s with failures/errors/skips0 and `OK`. App exited0 and recorded app/PG/network cleanup returned OK. Independent result review accepted0/0/0/product0/no-bloat; the server gate is closed and repeat0. Browser exact8 remains separate.
