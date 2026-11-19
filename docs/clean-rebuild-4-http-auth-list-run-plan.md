# RB4 HTTP auth/list focused PostgreSQL run plan

Дата: 2026-11-18. ID: `RB4-HTTPA-PG-001`. Статус: **completed by D-1532; corrected run2 PASS23/23 and independent result ACCEPTED 0/0/0; repeat unnecessary**.

## Exact purpose and suite

One disposable PostgreSQL run verifies only the D-1525 HTTP auth/session/page-list increment. Exact labels are `modules.accounts.tests.test_http_auth` and `modules.pages.tests.test_http_list`; discovery must equal exactly23 before test DB creation. The standard Django runner must create/destroy only `estakada_httpa_test`, complete migrations and system checks, and finish with tests23, failures0, errors0, skips0 and exit0. PAGECAS tests, Nginx, browser, media reads, typed editor and public/live behavior are outside this run.

Before discovery the app imports and verifies exact current-source origins for five production files under `/review/src`: `modules/accounts/middleware.py`, `modules/accounts/api.py`, `modules/accounts/web.py`, `modules/pages/web.py` and `config/urls.py`. It emits only `RB4_HTTPA_ORIGINS_OK=5`; path or environment output is forbidden.

## Reused disposable boundary

The run reuses the already reviewed and successful D-1517/D-1520/D-1521 boundary without a launcher or source change:

- existing `nestakada-local/postgres:18.6-security-20261030` and `nestakada-local/app-editor:candidate-d330` only, inspected first and created with `--pull=never`; build/pull/install0;
- exact fresh names `rb4-httpa-pg`, `rb4-httpa-tests`, `rb4-httpa-net`, all required absent before creation, plus one fresh exact run label `nestakada.run=rb4-httpa-pg-001-<uuid>`;
- one internal bridge with published ports0 and no other network attachment; PG/app caps, users, read-only roots, resource limits and TCP listener/readiness retain the proven D-1520 values;
- run2 replaces the unsafe child DB tmpfs with exact parent tmpfs `/var/lib/postgresql:rw,nosuid,nodev,noexec,size=512m,uid=999,gid=999,mode=0700`, while retaining `PGDATA=/var/lib/postgresql/data/pgdata`, `/var/run/postgresql` and `/tmp` tmpfs. Mounting the image-declared parent path suppresses Docker's anonymous `VOLUME`; database bytes remain tmpfs-only;
- readonly `T:\nestakada\src:/review/src`, no docs, real database, media, private data, volume or credentials mount; fixed synthetic DB password and Django secret only and neither printed;
- PG base name changes only to `estakada_httpa_base`; test settings use exact `estakada_httpa_test`, bridge host `rb4-httpa-pg`, runtime marker1 and in-memory isolated-network `sslmode=disable` exactly as D-1521;
- app workdir `/review`, `python3 -B`, current source on `PYTHONPATH`, bytecode0. No persistent helper/script is added.

## Evidence and cleanup

Evidence is the same bounded projection as D-1521: TCP readiness within30 seconds; app inspect limited to status/running/OOM/dead/exit/error and exact label; app log tail500 with origin5, discovery23, migration/check result, `Ran 23 tests` and final outcome; PG tail200 only on failure; internal network/published-port0/volume0 projections without Env.

Three initially null in-memory slots record the returned network, PG and app IDs immediately after each successful create. Immediately after PG `docker create` and before start, the exact recorded ID/name/label must project only three tmpfs mounts at `/var/lib/postgresql`, `/var/run/postgresql` and `/tmp`, with bind/volume mounts0. Any volume mount names from that exact PG projection are recorded in a separate initially empty list and the container is not started on mismatch.

One `finally` rechecks each non-null container ID's exact name+label, stops only a running recorded container and proves it stopped. App removal uses its exact ID. PG removal uses exact recorded ID with `docker container rm -v`; before removal every unexpected anonymous volume name is retained from the exact container projection, and after removal each must be absent. Named/unrelated volumes are never inferred or pruned. The recorded network is removed only by ID after exact name+label and endpoints0. Final checks prove every recorded ID, any recorded unexpected volume ID/name and all three exact object names absent. Identity/state mismatch refuses deletion and reports the retained object. No automatic retry follows a failure.

The run plus exact recorded-prefix cleanup requires one explicit owner authorization after independent plan approval. A result review is required before the runtime gate can close.

## Run1 result and reviewed changed condition

Owner-authorized run1 reached TCP readiness, origins5, exact discovery23, successful test DB creation/migrations and system check0. It ran all23 tests in4.945s: 18 passed and five test assertions failed; app exit1 with OOM/dead/error0. Four failures used Django `assertNotContains` without overriding its default expected status200 on intentional302/503 responses. The fifth expected view-level405 from a POST without a CSRF token, while authoritative CSRF middleware correctly returned403 before the view. Test DB destruction completed and recorded app/PG/network IDs and names became absent.

Independent triage classified product findings0 and exactly two test-only P2s. The reviewed minimal test changed condition passes literal302/503 to the four negative-content assertions and obtains a real CSRF token before the POST-only/405 assertion.

A later evidence audit found that run1 PG also had a daemon-created anonymous parent volume despite the child DB tmpfs. Read-only inventory identified exact dangling volume `06c71eacd17aa0c65ab5eaa9411d366f57100ec0e0f8c8892720ab57d1442ee1`, created at the run1 PG creation time, while two older anonymous volumes remain out of scope. It is not covered by the old three-ID cleanup claim and has not been deleted. Independent triage returned one runtime P1 and one cleanup P2; the parent-tmpfs/pre-start-mount/rm-v lifecycle above is the candidate remediation. Run1 is not accepted. Orphan deletion and fresh run2 require new explicit authorization after repeat plan review; no automatic retry is permitted.

The existing run1 orphan has a separate exact cleanup procedure. Immediately before any deletion, inspect only exact volume name `06c71eacd17aa0c65ab5eaa9411d366f57100ec0e0f8c8892720ab57d1442ee1` and require exact same name, local driver, `com.docker.volume.anonymous` marker and attached containers0. Any mismatch or attachment refuses deletion. Only non-force `docker volume rm 06c71eacd17aa0c65ab5eaa9411d366f57100ec0e0f8c8892720ab57d1442ee1` is allowed, followed by exact-ID absence proof. No other volume is listed for deletion or touched. The new combined owner permission must literally name this exact orphan cleanup separately from run2's newly recorded-prefix cleanup.

## Corrected run2 result

The separately authorized exact run1 orphan cleanup passed identity/anonymous/local-driver/attachments0 checks, removed only that volume non-force and proved it absent. Corrected run2 then proved exact parent/socket/tmp tmpfs3 and bind/volume mounts0 before PG start, TCP readiness, current-source origins5 and discovery23. Django created the isolated test DB, completed all migrations with system check0, ran23 tests in4.859s with failures/errors/skips0 and `OK`, destroyed the test DB, and exited0 with OOM/dead/error0. Internal network true and published ports0 were preserved. Recorded app/PG/network cleanup proved absent; final anonymous-volume inventory contained only the two older out-of-scope volumes and no run1/run2 residue. Independent result review `ACCEPTED`, P1/P2/P3=0/0/0, no-bloat PASS. `RB4-HTTP-AUTH-LIST-001` code/runtime gate is closed and repeat0.

## No-bloat boundary

Compose/launcher/dependency/image/model/migration/source change, volume, repository/UoW, throttle store, Nginx/browser/editor/public/live/deploy/push and real data0. If the existing images or exact23 suite cannot satisfy this boundary, stop and report instead of installing or expanding scope.
