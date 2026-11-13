# DEV-26/27 branch A: минимальный implementation plan

Статус: **исходный plan APPROVED; amendment `DEV26A-PLAN-009` runtime-rejected D-922**. Дата: 2026-11-13. Основание: D-592, D-895, D-904, final scope approval D-907 и closed findings R26A-PLAN-001–008. Scope authority: `docs/dev26-nginx-projection-scope-proposal.md`. IMP-001/002 PASS; IMP-003 и PLAN-009 остановлены exact semantic failure. Branch A/IMP-004+ blocked; failed code rolled back to D-919 baseline.

## 0. Amendment DEV26A-PLAN-009 — internal URI static handoff (REJECTED D-922)

D-920 доказал: optional selector/map parsing и zero/active `nginx -t` работают, но цепочка `error_page → named location → variable-root try_files` возвращает generated503 вместо stored file. Третий template workaround в рамках исходного плана запрещён.

Предлагается сохранить branch A/no-new-process и заменить только file handoff внутри IMP-003:

1. Closed map по exact `$request_uri` остаётся единственным selector-driven data input; generated release содержит только map-entry fragments, zero selector сохраняет fixed503.
2. Dispatch выбирает один из literal internal codes для stored `200|301|302|404`. Каждый код использует documented `error_page CODE =STATUS /__html_reserve/<release>/<subdir>/<leaf>?` с переменными и очищенными args, а не named static location.
3. Только две fixed regex locations принимают internal redirect: response `UUID/responses/<64hex>.html` и resource `UUID/resources/<64hex>.(css|js|webp|jpg|png)`. Обе имеют `internal;` и полный `alias /delivery/releases/<named captures>`; внешний запрос на namespace обязан дать404 и reads0.
4. Status override, exact nullable Location, content type, HEAD/Content-Length и closed security/cache headers формируются только fixed template. Upstream hostile headers не наследуются. Missing/nonregular file обязан перейти в exact neutral503, не 404/HTML500.
5. Map record остаётся bounded/closed; capture names уникальны, positional captures запрещены. `$request_uri` остаётся исходным exact raw target, internal `$uri` не используется для повторного route decision.

Основание feasibility: официальная документация Nginx core говорит, что `error_page` URI может содержать variables, `=response` меняет status и выполняет internal redirect; `internal` закрывает location от внешнего вызова; regex `alias` поддерживает captures и задаёт полный file path. Named captures используются вместо нестабильных positional captures.

Amended IMP-003 обязан был сначала в synthetic harness доказать: exact raw query; GET/HEAD; POST/private reads0; live priority; 502/503/504; literal200/301/302/404; Location/Content-Length/content types; external internal-namespace404; missing/symlink/nonregular/traversal/injection fail closed; zero/one/multiple/temp selector; cap2MiB; resource envelope. D-922: owner continuation принято как code gate, zero/active `nginx -t` PASS, но первый active stored response снова вернул HTML503. Stop-gate сработал; PLAN-009 и branch A rejected, IMP-004 запрещён.

## 1. Жёсткая граница

План не добавляет package dependency, image, model, migration, database table, API, background worker, daemon, scheduler, request-time verifier, native/Nginx module, Docker socket/PID namespace в app, production/VPS config или live apply.

Используются только:

- existing pinned app image для stopped-by-default one-shot Python tools;
- existing pinned vanilla ingress image;
- два dedicated named volumes: source `html-reserve` и delivery `html-reserve-delivery`;
- один новый host operator wrapper `scripts/html-reserve-delivery.ps1`;
- три distinct stopped compose tools services одного и того же app image только для enforcement разных mounts: `reserve-projector` sourceRO+deliveryRW, `reserve-control` deliveryRW, `reserve-verify` deliveryRO;
- existing `scripts/local-foundation.ps1`, `scripts/test-editor.ps1`, base Nginx config и DEV-25 package.

Owner web UI остаётся только Build/Status DEV-25 и показывает source build facts плюс fixed note «delivery activation проверяется host Status»; actual delivery UUID/state туда не передаётся. Project/Activate/Verify/Recover/Status — локальные host actions; новых публичных/admin product buttons и status bridge нет. Explicit `Verify` не является periodic job.

## 2. Exact files

Новые:

- `app/html_reserve/projection.py` — closed projection contracts, source shared-lock verifier/copy, fixed map emitter;
- `app/html_reserve/delivery.py` — fd-relative delivery store, canonical release/journal/selector contracts, durability/recovery primitives;
- `app/html_reserve/delivery_tool.py` — closed CLI modes `project`, `verify-active`, `journal-transition`, `selector-replace`, `recover-transition`;
- `app/html_reserve/test_projection.py`, `app/html_reserve/test_delivery.py` — pure/storage/fault tests;
- `scripts/html-reserve-delivery.ps1` — exact host orchestration `Status|Project|Activate|Verify|Recover`, no automatic retry;
- `scripts/test-dev26-nginx.ps1` — exact pinned-image config/HTTP smoke harness, вызывается только named suite `dev26-config` из `scripts/test-editor.ps1`; no wildcard/Playwright.

Изменяемые:

- `app/estakada/settings/local_http.py` — exact local-only `HTML_RESERVE_ROOT` из fixed container path, без generic env configuration;
- `environment/foundation/compose.yaml` — two volumes, ingress RO mount, app source-reserve RW mount, stopped tools profiles/init; no new network/service daemon;
- `environment/foundation/local-nginx.conf` — reviewed fixed fallback template, generated-map include и loopback-only canary;
- `scripts/local-foundation.ps1` — volume inventory, common lock/barrier, Start verify-active/bootstrap, Stop/UnitTests exclusion; normal actions unchanged outside exact new gates;
- `scripts/test-editor.ps1` — only named suites `dev26-projection`, `dev26-config`, `dev26-activation`, `dev26`, exact modules/commands without wildcard/Playwright;
- `app/html_reserve/views.py`, `app/accounts/templates/accounts/html_reserve.html`, `app/html_reserve/test_http.py` — только source-build wording и fixed host-Status note; delivery state lookup/mount отсутствует;
- `README.md`, `docs/decisions.md`, `docs/tasks.md`, `docs/pipeline.md`, `docs/currentprocent.html`, `docs/dev26-nginx-projection-scope-proposal.md`, этот plan — status/evidence updates.

Fixture directory не создаётся: config harness генерирует bounded synthetic config/content только в test work directory и удаляет их. Image locks/SBOM/receipts не меняются, потому что images/dependencies не меняются. Любой иной production/test/docs/lock/receipt файл требует plan-amend stop и нового review до изменения.

Если fixed-template proof requires a different file, implementation stops for plan amendment; не добавлять ad-hoc scripts/services.

## 3. Bounded slices

### DEV26A-IMP-001 — pure projection/emitter contracts

Tests first for canonical release/selector/journal schemas, caps, exact target/resource classification, closed content/status/header policies and Nginx string escaping. Implement pure emitter that accepts only validated DEV-25 manifest rows and emits bounded map data; no filesystem/Docker/Nginx changes.

Evidence: named `dev26-projection`; Django check/no migrations/diff-check. Failure baseline is expected only before module exists and is not repeated unchanged.

### DEV26A-IMP-002 — safe source copy and delivery storage

Implement fd-relative source RO open, existing `build.lock` `O_RDONLY|O_NOFOLLOW` + shared nonblocking flock, sequential bounded copy, staging/reopen/SHA, release publication `temp/fsync/rename/parent-fsync`, closed inventory/caps. Implement selector/journal primitives and CLI modes with exact mount-role assertions.

Tests use real child processes for shared-vs-exclusive lock, pre/post-rename crash boundaries, symlink/nonregular/hardlink/unknown entries, cap+1, source change attempts and source writes0. No Docker yet.

Evidence: `dev26-projection`; affected DEV-25 named suite; no migrations/diff-check.

### DEV26A-IMP-003 — vanilla Nginx config-only proof

Before compose integration, add fixed template and synthetic generated maps. Through `scripts/test-editor.ps1 -Suite dev26-config` only, run pinned ingress image `nginx -t` and isolated HTTP/config smoke proving:

- exact `$request_uri` including raw query and unknown/duplicate rejection;
- GET/HEAD-only intercept; POST/private/normal upstream reserve reads0;
- transport/502/503/504 fallback and immediate live return;
- stored body with literal 200/301/302/404, exact nullable Location, HEAD/Content-Length;
- hostile upstream headers removed and DEV26-AT-014 closed headers;
- traversal/escape/control/generated-map injection rejected;
- optional selector include: zero matches PASS with fixed503, exactly one `selectors/active.conf` PASS, multiple/unknown `.conf` rejection, and temp leaves proven outside `*.conf`;
- 2MiB config cap and measured ingress memory under 128MiB/0.25CPU/8 connections.

If any exact Nginx1.30.6 semantic fails, stop branch A for architecture review; do not compensate with njs/helper/module.

### DEV26A-IMP-004 — local volumes and stopped tools wiring

Add `html-reserve` and `html-reserve-delivery` inventory/labels, app RW source mount, ingress RO delivery mount and three distinct profiled service definitions enforcing sourceRO/deliveryRW, deliveryRW, deliveryRO. App local setting points only at source volume.

Reuse the existing root `state-init` one-shot; do not add an init/bootstrap service or CLI mode. Extend only its exact mounts and fixed chown command to these three targets, in order: `/var/lib/estakada`, `/var/lib/estakada-html-reserve`, `/var/lib/estakada-html-reserve-delivery`, owner `10001:10001`. It runs via existing `compose --profile tools run --rm --no-deps state-init` before app/ingress/tools and is removed. Partial run is idempotently rechecked/repeated only on the next explicit Foundation Start, not inside a retry loop. After it returns, wrapper inspects exact volume labels/driver and a one-shot RO ownership probe; foreign owner/mode/link blocks Start.

Each tools service has a fixed command (`project`, closed `control`, `verify-active`), `profiles: [tools]`, `restart: "no"`, `network_mode: none`, read-only rootfs, UID10001, caps dropped and no DB/private/media mounts. Wrapper may invoke them only as `docker compose ... run --rm --no-deps <exact-service>`; they are forbidden in every `compose up` argument. Containers0 after every success/failure is mandatory. This slice wires services/volumes/state-init ownership and compose-config/mount guards only; it does **not** change Foundation Start/Stop/barrier behavior. Oracles cover fresh roots, foreign owner, one-of-three partial chown, wrong label/driver, state-init failure and container cleanup.

Evidence: `dev26-config`, `dev26-projection`, foundation Status; Stop at slice end.

### DEV26A-IMP-005 — host Project/Activate/Verify/Recover

Implement one wrapper with exact actions and no retry loop. It reuses the foundation exclusive lock and exact manifest/container/image checks. Integrate Foundation First Start canonical empty state, subsequent Start `verify-active`, unfinished-journal barrier, Stop/UnitTests exclusion and failed Start/Verify single journal→UNKNOWN in this slice, not IMP-004.

Canonical empty state is no-write: base Nginx config contains fixed empty maps/fallback503 and a closed optional include `/delivery/selectors/*.conf`; a fresh empty delivery volume has zero matches and needs no selector/release/journal. First activation records old canonical selector state `ABSENT` and creates exact `selectors/active.conf` through existing selector-replace mode. Journal selector states are only `ABSENT` or `PRESENT(exact bytes,digest)`. Verify permits EMPTY only when closed root inventory contains no release/journal/selector; partial/multiple/unknown selector state is UNKNOWN. Temp names never end in `.conf`. No bootstrap writer mode is added.

Sequence: Project → candidate receipt → nginx-t → PREPARED journal with old/new typed selector states → selector replace → HUP intent/exact signal → canary → confirmed receipt, or one recorded rollback. Every journal/selector transition goes through control container and returns an exact digest. First-activation rollback from candidate PRESENT to old ABSENT uses the same selector-replace operation: exact candidate digest check, fd-relative unlink, parent-fsync, empty canary. Failed Start/Verify permits only journal→UNKNOWN. Recover follows durable stage and never blind-retries candidate. Receipt failure after confirmed canary is success-with-warning.

Fault tests inject abrupt process exit at every approved boundary, empty first Start/no-write fixed503, empty restart, partial bootstrap/root ownership, first selector creation, first-activation HUP reject/canary mismatch/crash with PRESENT→ABSENT unlink+parent-fsync recovery, second Start verified-active, active mismatch→single durable UNKNOWN, Start/Stop/Activate exclusion, tools containers0, container replacement/duplicate/foreign identity, rollback failure and receipt failure. Third HUP/retry forbidden.

Worker drain uses exact pre-HUP inventory. Cleanup only after proven drain; otherwise retain and cap-block. Current+previous always retained.

Evidence: named `dev26-activation` is mandatory for the complete Start/bootstrap/barrier/activation lifecycle; `dev26-config` and foundation Status supplement it. Foundation stopped after each destructive fault group.

### DEV26A-IMP-006 — real DEV-25 → delivery → Nginx acceptance

One combined fixture performs real owner login/CSRF POST `/manage/html-reserve/` with unpatched `build_run`, verifies audit/status, runs host Project+Activate, then tests DEV26-AT-001–014 with D-904 delta and DEV26A-AT-001–022 on the same generated bytes/volumes. No hand-seeded manifest may count as combined evidence. On those same first owner-built delivery bytes, injected first-activation HUP rejection/canary mismatch or crash must exercise conditional PRESENT→ABSENT unlink+parent-fsync, empty canary, restart with zero selector/fixed503 and prove no candidate retry.

Include anonymous/employee negative owner-build tests and concurrent owner-build/project lock behavior. Verify G1 stays served while DEV-25 builds G2/G3 without Activate; after Activate G3 is served; app recovery is immediate/nonsticky.

Evidence: named `dev26`; exact HTTP/status/header/body/digest/trace assertions; no real PII/network/live/VPS.

### DEV26A-IMP-007 — calibrated regression and final checks

Only through `scripts/test-editor.ps1`, no wildcard/Playwright:

1. `dev25`;
2. `dev25-affected`;
3. `dev26-projection`;
4. `dev26-config`;
5. `dev26-activation`;
6. `dev26`;
7. `guard`;
8. `check` and `migrations`.

Then PowerShell parser, compose config, exact lock/receipt/SBOM consistency if changed, `git diff --check`, tools containers0, foundation Stop/Status `Active=False`. Прямой широкий Django run не выполняется и не интерпретируется как product evidence.

### DEV26A-IMP-008 — independent code review

Independent reviewer checks full DEV-26 diff and R26A findings, exact test evidence, no scope bloat, no live/persistent apply. Findings receive stable IDs and bounded remediation; final completion only after repeat `APPROVED`, P1/P2/P3=0.

## 4. Ordering and stop rules

- Each slice begins with its named failing oracle and ends with fresh named PASS evidence before the next slice.
- No implementation beyond the current slice after a P1/P2 failure.
- Same error twice under equivalent action stops without third attempt and records task as owner-paused.
- Config semantic failure in IMP-003 returns to architecture review, not a new runtime.
- New dependency/image/service/model/migration/button/periodic task requires plan amendment and new owner approval.
- No commit/push/deploy/live/VPS/persistent apply is included.

## 5. Gate

1. Independent review of this plan.
2. Remediation/repeat review until `APPROVED`, P1/P2/P3=0.
3. Separate explicit owner approval `DEV26A-IMP-001–008`.
4. Only then begin IMP-001 tests first.
