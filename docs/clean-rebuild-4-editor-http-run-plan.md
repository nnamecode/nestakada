# RB4 editor HTTP focused PostgreSQL regression plan

Дата: 2026-11-18. ID: `RB4-EDITOR-PG-001`. Статус: **completed by D-1545; run3 PASS40/40 and independent result ACCEPTED 0/0/0; repeat unnecessary**.

## Exact suite and purpose

One disposable PostgreSQL run verifies the approved `RB4-EDITOR-HTTP-001A` code plus its already closed auth/list HTTP boundary. Exact labels:

- `modules.accounts.tests.test_http_auth` —14;
- `modules.pages.tests.test_http_list` —9;
- `modules.pages.tests.test_http_editor` —17.

Preflight discovery must equal exact40 before test DB creation. The standard Django runner must create/destroy only `estakada_editor_test`, complete migrations and system check0, and finish tests40/failures0/errors0/skips0/exit0. PAGECAS command source was not changed and editor tests call its real Save/Undo paths; rerunning the separate13 command suite is unnecessary here. JS serializer behavior is not claimed by this Django gate and remains a later browser-native gate.

Current-source origin preflight imports and proves eight literal files beneath `/review/src`: accounts middleware/api/web, pages editor/web/commands/content and config URLs. It emits only `RB4_EDITOR_ORIGINS_OK=8`; paths and environment are not printed.

## Disposable boundary

Reuse the corrected D-1532 lifecycle, not the flawed run1 profile:

- existing pull-never PG/app images only; build/pull/install0;
- exact absent names `rb4-editor-pg`, `rb4-editor-tests`, `rb4-editor-net` and fresh run label `nestakada.run=rb4-editor-pg-001-<uuid>`;
- one internal bridge, published ports0, other network0;
- PG read-only/caps/resources plus exact parent tmpfs `/var/lib/postgresql:rw,nosuid,nodev,noexec,size=512m,uid=999,gid=999,mode=0700`, socket and `/tmp` tmpfs, `PGDATA=/var/lib/postgresql/data/pgdata`;
- immediately after PG create and before start, exact recorded ID/name/label and HostConfig tmpfs3 must match while `.Mounts` bind/volume count is0. Any unexpected volume name is recorded from that exact container projection and the container is not started on mismatch;
- exact internal listener/TCP readiness from D-1532; synthetic base `estakada_editor_base`, test DB `estakada_editor_test`, in-memory isolated-network SSL disable only;
- app read-only UID10001/caps/resources/tmpfs and readonly exact `T:\nestakada\src:/review/src`; docs, media bytes, real DB/data/secrets/volumes0.

## Evidence and cleanup

Bounded evidence: pre-start volume0; TCP readiness≤30s; origins8; discovery40; migrations/system check; `Ran 40 tests`; exit/OOM/dead/error; internal/published ports0; app bind source only; PG exact tmpfs and mounts0. App logs tail700; PG tail200 only on failure; Env/full inspect forbidden.

Nullable network/PG/app IDs are recorded immediately after create. One finally rechecks exact ID+name+run-label, stops only running recorded containers, proves stopped, removes app by ID and PG by exact ID with `docker container rm -v`, proves every unexpected volume recorded from its projection absent, then removes recorded network ID only after endpoints0. Final exact names/IDs are absent. No prune, name fallback, time inference, persistent launcher or automatic retry.

Run plus exact recorded-prefix cleanup require explicit owner authorization after plan approval. Independent result review closes the gate. Browser, Nginx, structured/prices/media001B, live/deploy and real data remain separate.

## Run1 result and changed condition

Owner-authorized run1 passed pre-start tmpfs3/volume0, TCP readiness, origins8, discovery40, isolated test DB creation, migrations and system check0. It ran40 in5.900s: 39 passed and one test harness error occurred before its HTTP request because pre-encoded multipart bytes were passed to `Client.post()`, which attempted a second mapping encode and raised `AttributeError`. Product view/command/transaction executed0 for that case; product findings0. App exit1/OOM0/dead0/error-empty, test DB destroyed and recorded cleanup absent.

Independent triage returned P1/P2/P3=0/1/0. The exact test-only changed condition sends the same encoded duplicate-key body through `Client.generic("POST", ...)`; production source and exact40 remain unchanged. Run1 is not accepted. A fresh run2 requires repeat static review and separate owner authorization; no automatic retry.

## Run2 pre-start result and candidate changed condition

Owner-authorized run2 created only its internal network and stopped PostgreSQL container, then stopped before PostgreSQL start, readiness, app creation, discovery or tests. The bounded PowerShell orchestrator passed a backslash-escaped quoted key to Docker's Go template `index`; Docker rejected that label projection with a template parser error. Its `finally` used the same invalid projection and retained the two created objects. A separately authorized cleanup-only action used JSON projections without `index`, proved the exact shared run label, PG state `created/running=false`, mounts0, internal network and endpoints0, then removed only the exact recorded PG and network IDs. Both IDs and all three reserved names are absent; app container, database process, source execution and product findings were0.

The minimal candidate changed condition is orchestrator-only: project the complete labels dictionary with the literal Docker template `{{json .Config.Labels}}` for containers and `{{json .Labels}}` for the network, parse that bounded JSON in PowerShell, and require the exact `nestakada.run` value before start or cleanup. It removes nested template quoting while retaining exact ID/name/run-label authority. Production source, tests, images, exact40, lifecycle and evidence boundaries remain unchanged. Run2 is not accepted; this condition requires independent static review and a separately authorized fresh run3. No automatic retry.

Independent static review returned APPROVED P1/P2/P3=0/0/0 and no-bloat PASS. It confirmed that the JSON dictionaries are parsed locally for an exact `nestakada.run` property, while recorded ID+name+label authority, nullable partial-create cleanup and the prohibition on name fallback/inference/prune remain intact. Edits/runtime0 during review. A fresh run3 still requires separate owner authorization.

## Run3 result

Owner-authorized run3 proved pre-start parent/socket/tmp tmpfs3 and bind/volume mounts0, TCP readiness on attempt4, current-source origins8 and exact discovery40. Django created only `estakada_editor_test`, applied all migrations, reported system check0, ran auth14+list9+editor17 in5.999s with failures/errors/skips0 and `OK`, then destroyed the test database. App state was exited/runningfalse/OOMfalse/deadfalse/exit0/error-empty with matching run label. The network was internal, published ports were0, the app had only the readonly `/review/src` bind and PG mounts were0.

The main cleanup removed the exact recorded app and PG IDs, including PG `rm -v`, but its PowerShell empty-object count check falsely treated the already empty network endpoints JSON `{}` as non-empty and retained only that network. No attachment or resource leak existed. Under the same explicit recorded-prefix cleanup authorization, a bounded projection proved both containers absent and the exact retained network ID/name/run-label/internal=true/endpoints `{}`; only that ID was removed, then its ID/name and both container names were proved absent. Tests were not repeated. Product findings0; one cleanup-oracle finding awaits independent result review. No source/test/image/dependency change was made.

Independent result review ACCEPTED the gate with P1/P2/P3=0/0/0, product findings0 and no-bloat PASS. It classified the empty-object check as a closed cleanup-oracle defect: the failure was safe, exact follow-on cleanup fulfilled the original contract and no test rerun was needed. Future ephemeral PowerShell orchestration should use `ConvertFrom-Json -AsHashtable` plus type/count checks or explicitly materialize `PSObject.Properties` as an array; this does not justify a persistent launcher or framework. Server runtime gate `RB4-EDITOR-PG-001` is closed. Browser-native JS evidence and structured/prices/media001B remain separate later gates.

## No-bloat boundary

No Compose/launcher, image/dependency/model/migration/source change, new runner, jsdom/Node/Python serializer mirror, volume, cache, API framework or browser claim. Failure stops for diagnosis instead of expanding the test environment.
