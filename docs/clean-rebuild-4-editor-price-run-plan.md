# RB4 price editor focused PostgreSQL gate

Дата: 2026-11-19. ID: `RB4-EDITOR-PRICE-PG-001`. Статус: **completed by D-1580; run3 exact47/47 independently ACCEPTED P1/P2/P3=0/0/0; repeat unnecessary**.

## Purpose and exact suite

This is the first runtime gate for independently approved `RB4-EDITOR-001B-P`. It proves server/template/settings/middleware behavior only. Browser behavior remains a later, separately authorized `price-editor-native` gate.

One disposable PostgreSQL run executes exactly:

- `modules.accounts.tests.test_http_auth` —16 methods;
- `modules.pages.tests.test_http_list` —9 methods;
- `modules.pages.tests.test_http_editor` —22 methods.

Preflight discovery must equal exact47 before Django creates a test database. Expected result: migrations and system check0, `Ran 47 tests`, failures0/errors0/skips0, exit0. The standard runner creates/destroys only `estakada_editor_price_test`. It executes the real PageCAS, media usages and audit rollback paths. Chromium/JS behavior is not claimed.

Current-source preflight accepts only the existing readonly `T:\nestakada\src:/review/src` bind and verifies ten literal regular, non-symlink origins beneath it: accounts `api.py`, `middleware.py`, `web.py`; pages `content.py`, `commands.py`, `editor.py`, `web.py`; config `urls.py`, `settings/base.py`; pages `templates/pages/page_editor.html`. It emits only `RB4_PRICE_ORIGINS_OK=10`. Price/rich JS source is not executed by this gate and is covered by the later readonly browser mode.

## Reused disposable boundary

Reuse the already accepted D-1545 lifecycle with only new names/counts:

- existing exact local app/PG images, `--pull=never`, build/install0;
- fresh run UUID and exact absent names `rb4-price-pg`, `rb4-price-tests`, `rb4-price-net`, label `nestakada.run=rb4-editor-price-pg-001-<uuid>`;
- one internal bridge, published ports0, other network0;
- PostgreSQL parent/socket/tmp tmpfs3, bind/volume mounts0, fixed caps/resources and internal TCP readiness≤30s;
- synthetic base `estakada_editor_price_base`, standard test DB `estakada_editor_price_test`, real/imported data0;
- app UID10001, readonly source, tmpfs, caps/resources; docs, media bytes, host secrets, Docker socket and named volumes0;
- evidence only from bounded label/name/ID/state/mount/port projections, origin/count output and bounded logs; full Env/inspect forbidden.

The prior empty-endpoints PowerShell defect must not return: network endpoints are converted with `ConvertFrom-Json -AsHashtable` and require an actual hashtable with `Count == 0`. No persistent launcher/Compose/script is added; the one-shot coordinator command is reviewed evidence only.

## Cleanup and stop rules

Record nullable network/PG/app IDs immediately after each create. One `finally` rechecks exact ID+name+run-label, stops only a running recorded container, proves stopped, removes app by ID and PG by exact ID with `docker container rm -v`, proves any exact unexpected volume recorded from the PG projection absent, and removes the recorded network ID only after endpoints0. Final IDs/names are absent. No prune, name fallback, broad enumeration deletion, retry or time inference.

Run plus cleanup require one explicit owner authorization after plan approval. Any first failure stops for diagnosis and independent triage; no automatic equivalent retry. Independent result review closes the gate. Browser execution, `001B-S`, `001B-M`, real data, Nginx, live/deploy and push remain closed.

## No-bloat boundary

No source/code/test change, model/migration/dependency/image/volume/runner/serializer mirror, persistent test launcher or new infrastructure. The exact47 gate reuses the accepted disposable pattern and does not re-run already closed rich exact8.

## Run1 pre-Docker result and changed condition

The owner-authorized run1 stopped in the coordinator before its first Docker call. The outer JavaScript tool wrapper interpreted `\n` in a literal `T:\nestakada\src` PowerShell path as a newline; `Resolve-Path` therefore failed. Container/network/image/PG/app/source/tests0, and a read-only exact-name check proves all three reserved names absent.

No automatic retry is allowed. A run2 candidate changes only source-path construction: `[IO.Path]::GetFullPath((Join-Path (Get-Location).Path 'src'))`, followed by an exact immediate-parent equality check against the fixed current workspace before Docker. It contains no backslash-escaped repo literal. Exact47, images, lifecycle, evidence and cleanup remain unchanged. Independent changed-condition review and fresh owner authorization are required.

## Run2 result and test-only changed condition

Run2 passed PG readiness, origins10, discovery47, migrations and system check0. It ran47 in8.765s:46 passed and one replay assertion expected302 but received400. Cleanup completed for exact recorded app/PG/network IDs.

Independent triage classified product findings0 and P1/P2/P3=0/1/0. The test added valid-looking price records to a copied owner request but retained `price.changed=0`; the approved parser correctly rejects that malformed combination before PageCAS. The only candidate change sets `price.changed=1` in that replay body. The same operation ID can then reach command replay after valid wire/candidate validation; generation, original price/media and audit count remain the oracle. Product code, exact47 and lifecycle are unchanged. Repeat static review and fresh owner permission precede run3.

## Run3 result

Owner-authorized run3 passed PG readiness, origins10 and discovery47, then created only the synthetic test database, applied all migrations and reported system check0. Accounts16+list9+editor22 passed exact47/47 in7.260s with failures/errors/skips0 and OK. App exit0; the exact recorded app/PG/network IDs were removed and cleanup returned OK. Independent result acceptance precedes server-gate closure. Browser exact8 remains separate and unexecuted.
