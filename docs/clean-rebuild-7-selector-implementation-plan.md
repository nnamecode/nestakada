# R7C-SELECTOR-IMP-PLAN-001 — tests-first selector implementation

Статус: source implementation `R7CSI-IMP-001..006` approved 23 ноября 2026 года. Исходный plan review: `CHANGES_REQUIRED P0=0/P1=4/P2=2`, repeat `APPROVED 0/0/0`. Первое full source review: `CHANGES_REQUIRED P0=1/P1=9/P2=2`; после двух bounded remediation repeat review: `APPROVED P0=0/P1=0/P2=0`. Закрыты accidental actual-authority access, selector UID/mode и concurrent CAS, host lock/env race, target/topology/media authority, recovery/receipt/external evidence, exact quiesce/dispose и source test gaps. Docker/runtime/PostgreSQL/media не запускались; `faults|all` намеренно fail-closed до отдельного IMP-007 fixture setup/runtime gate. Authority: `docs/clean-rebuild-7-selector-design.md`, `docs/clean-rebuild-7-local-cutover-plan.md`, `docs/clean-rebuild-7-local-cutover-inventory.md`.

Этот документ не разрешает code/config/compose edits, Docker/PostgreSQL/media read, topology apply, target bootstrap, migration freeze, transfer, external copy, rehearsal, cutover, rollback, live или destructive cleanup. Каждый следующий gate указан отдельно.

## 1. Жёсткая граница

Реализация добавляет только bounded local selector stack:

- pure Python canonical selector/journal/storage-binding contracts;
- fd-relative one-shot control modes внутри уже pinned app image;
- local-cutover-only Django identity endpoint/settings;
- отдельные Nginx/Compose config для R7 selector scopes;
- один PowerShell coordinator и один exact named test wrapper;
- safe receipts и fault injection.

Foundation compose/config и текущие foundation/RB5 containers не переписываются и не становятся selector authority. New selector stack использует отдельный compose file/project/labels. Никаких новых images/dependencies/models/migrations/product buttons/public APIs/controller daemon/scheduler/retry queue/service discovery/native or njs module.

Синтетические selector tests не считаются `R7C-REHEARSAL-001`, fresh `SEALED` transfer, external restore или Q003 evidence. Real DB/media verification и actual rehearsal выполняются только поздними отдельными runtime packages после соответствующих gates.

## 2. Exact files

### Новые source files

- `tools/rebuild7_selector.py` — canonical schemas, renderer/parser, fd-relative selector/journal/receipt writer/verifier, storage-binding receipt combiner; closed CLI modes only.
- `tools/test_rebuild7_selector.py` — pure/storage/fault unit tests без Django/Docker.
- `tools/rebuild7_selector_probe.py` — bounded internal direct-target identity+readiness probe, stdlib only; through-ingress proof выполняется отдельно с Windows host loopback.
- `src/config/local_cutover_identity.py` — local-only target identity view.
- `src/config/urls_local_cutover.py` — identity URL перед base public catch-all, используется только cutover settings.
- `src/config/settings/local_cutover.py` — import existing `local_restore`, exact role/generation/storage-binding validation, local URLconf, probe host.
- `src/config/tests/__init__.py` и `src/config/tests/test_local_cutover_identity.py` — endpoint/settings isolation tests.
- `environment/rebuild7-cutover/compose.yaml` — separate old/new app, ingress и stopped tools profiles; external DB/media authority only.
- `environment/rebuild7-cutover/nginx.conf`, `nginx-validate.conf`, `http.conf` — separate active/staging selector entry configs plus one shared fixed GET/HEAD public proxy, mutation deny and identity config.
- `scripts/rebuild7-selector.ps1` — exact host coordinator actions `Inspect|Bootstrap|Switch|Recover|Status|QuiesceRehearsal|DisposeRehearsal`; default is read-only `Status`. Quiesce exact receipt IDs только останавливает disposable rehearsal containers; Dispose принимает только уже stopped exact manifest.
- `scripts/test-rebuild7-selector.ps1` — named suites `unit|django|config|synthetic|faults|all`, explicit commands only. Host shell contract — PowerShell 7+; process arguments передаются только через native `ProcessStartInfo.ArgumentList`, hard-crash child использует exact executable текущего PowerShell 7 process.

### Изменяемые existing files

- `tools/rebuild7_generation.py` — только новый read-only `binding-capture` output mode, переиспользующий существующий generation-v5 `build_release`; capture/verify/reconcile behavior не меняется.
- `tools/test_rebuild7_generation_diagnostic.py` — direct tests closed safe binding output и неизменности generation-v5 restore semantics.
- `docs/clean-rebuild-7-selector-design.md`, `docs/clean-rebuild-7-local-cutover-plan.md`, `docs/currentprocent.html` — evidence/status после факта.

`environment/foundation/compose.yaml`, `environment/foundation/local-nginx.conf`, base/public URLconf, models, migrations, dependencies/locks/SBOM и product templates не меняются. Любой иной file требует stop, plan amendment и independent repeat review.

## 3. Closed contracts

### 3.1 `rebuild7_selector.py`

CLI не принимает arbitrary host paths. Fixed container roots: `/selector`, `/authority`, `/capture`; scope/role/run/generation/digests передаются как closed values. Modes:

- `render-candidate` — canonical selector bytes only into exact staging leaf;
- `inspect` — `ABSENT|PRESENT|UNKNOWN`, no writes;
- `selector-cas` — exact expected ABSENT/digest → canonical candidate, same-filesystem replace+file/parent fsync;
- `journal-create` — only `PREPARED`, exact closed payload;
- `journal-transition` — only approved next phase with exact previous journal digest;
- `receipt-finalize` — only terminal known state;
- `operation-close` — exact terminal receipt+journal cleanup только по matching external receipt bytes/digests, active selector не меняет;
- `storage-binding` — validates closed generation-v5 capture/media check receipts and returns one safe SHA-256.

Selector schema is exactly `estakada.r7c-selector-v1`; scope `local|rehearsal:<32hex>`; role/alias/source-static/media roots form one closed old/new tuple; generation exactly 64 lower hex; port fixed `8000`. Selector ≤4 KiB.

Journal schema records scope/run, exact ingress+old/new target IDs, old/new storage-binding SHA, expected/candidate selector SHA, exact implementation/image inventory SHA and mutation bitmap. Closed transitions: `PREPARED→INGRESS_STOPPED→SELECTOR_COMMITTED→INGRESS_STARTED→OBSERVED_OLD|OBSERVED_NEW→CONFIRMED|ROLLED_BACK`; any ambiguity writes `UNKNOWN` only from an exact known previous digest. Journal/receipt ≤16 KiB each.

`implementation-inventory` mode имеет встроенный closed list runtime-authority files: selector tool/probe, generation/media tools, coordinator, cutover settings/view/URLconf, cutover compose/Nginx and exact requirements/image lock files. Он читает их только из fixed `/project`, отвергает symlink/nonregular/missing/extra declared entry и возвращает per-file SHA плюс canonical aggregate. Wrapper добавляет immutable app/ingress/PostgreSQL image IDs и получает `implementationImageBindingSha256`. Этот digest входит в PREPARED journal и final receipt и fresh сверяется непосредственно pre-CAS, post-start и перед final receipt. Drift до CAS даёт mutation0; drift после CAS идёт в exact rollback/UNKNOWN matrix.

All roots and leaves are fd-relative, `O_NOFOLLOW`, regular, link count1, expected owner/mode, no unknown entries. Temp leaves never match `*.conf`. Pre/post-rename fault hooks exist only under exact test marker and cannot be enabled in normal mode. Stdout contains only fixed codes/counts/digests.

### 3.2 Actual storage binding

`binding-capture` runs against the target's actual source and DB connection with `default_transaction_read_only=on`; it emits only closed generation-v5 release/facts/media-inventory digests/counts. Existing capture/verify paths remain byte/behavior compatible.

Separately, existing `rebuild7_media.py check` reads the actual media root read-only against exact authority `media-inventory.json`. Coordinator accepts storage binding only if:

- target app inspect matches exact DB network/credential mount token and media mount ID/token;
- binding capture matches the readiness authority for release/schema/migrations/table counts/content/media DB inventory;
- actual media byte check passes exact count/bytes/SHA;
- canonical hash of those safe results equals expected old or fresh `SEALED` `storageBindingSha256`.

Неизменяемый `rebuild7_media.py check` остаётся stdout verifier. Coordinator создаёт closed safe media-check receipt только после exact exit0 и exact fixed output line, связывая verifier container/image ID, media mount token, authority-file SHA-256 до/после, canonical inventory SHA/count/bytes из authority и result `PASS`. Receipt пишется temp+file fsync+replace+parent fsync; selector `storage-binding` mode проверяет closed shape/digests и объединяет его с DB capture. Любое несовпадение/лишняя строка/authority drift отказывает. Сам media tool и его совместимость не меняются.

No DB rows, media paths/bytes, credentials or absolute host paths reach stdout/receipt. A past receipt is never substituted for fresh pre-CAS or post-start binding.

Safe external operation receipt хранится append-only как `results/<runId>-<receiptSha256>.json`. Перед новой операцией coordinator обязан доказать exact terminal journal/receipt, найти ровно одну matching external receipt по journal digest и только затем вызвать `operation-close`. Это позволяет последовательность bootstrap old → switch new → switch old в одном scope без перезаписи evidence; incomplete/ambiguous state остаётся blocked.

### 3.3 Local target identity

До импорта existing `local_restore` файл `local_cutover.py` fail-closed запрещает **само наличие** `ESTAKADA_RESTORE_VERIFY_WRITE`; после импорта повторно требует `default_transaction_read_only=on`. Compose closed environment inventory также запрещает эту variable. Затем settings требуют exact:

- `ESTAKADA_R7C_ROLE=old|new`;
- `ESTAKADA_R7C_GENERATION_SHA256=<64hex>`;
- `ESTAKADA_R7C_STORAGE_BINDING_SHA256=<64hex>`.

`urls_local_cutover.py` adds only `/__r7c_target_identity__`; base `config.urls` stays unchanged. View accepts `GET|HEAD` and exact host `r7c-probe.invalid`, returns `204`, three fixed identity headers, `Cache-Control: no-store`, no body/cookie/DB/media read. Wrong host/method/config fails closed with constant response and no reflected values. Tests explicitly inject `ESTAKADA_RESTORE_VERIFY_WRITE=0|1|empty` and require settings import failure in every case.

### 3.4 Separate scope topology

Compose project must be exactly `nestakada-r7c-rehearsal-<32hex>` or `nestakada-r7c-local`. Every resource has matching `estakada.r7c.scope` label.

- Rehearsal: disposable selector volume+ingress, loopback `127.0.0.1:18086`, no current/live route.
- Durable local: fixed selector volume+ingress, loopback `127.0.0.1:18087`; creation/bootstrap is a later separate topology gate and not Q003.
- Old/new app each join only their own internal web+DB networks. Ingress joins two web networks, never DB. DB has no host binding.
- App and ingress mount exact role media root read-only. Ingress selector volume read-only.
- Control writer mounts only its scope selector volume RW, `network_mode:none`, no source/DB/media/secrets.
- Storage verifier mounts exact role source/media/authority RO plus exact DB credential/CA RO and joins only that role DB network.
- Direct probe has only exact role web network, no mounts/secrets/external route. Through-ingress proof is a separate coordinator-owned Windows `.NET HttpClient` request to exact `http://127.0.0.1:18086|18087`, with proxy disabled, bounded timeout, exact `Host: r7c-probe.invalid`, identity headers and public canary. It proves the actual loopback listener; an internal request to ingress cannot substitute for it.
- All container tools are `run --rm --no-deps`, read-only rootfs, cap-drop ALL, no restart.

`docker compose up` is forbidden for tools profiles. Rehearsal and local project/resource IDs cannot be mixed. Fixed ports are revalidated as loopback-only and unused before create; conflict fails before topology mutation. Host probe additionally rejects redirects, proxy use, wrong peer/port, missing/duplicate identity headers, cookies/body on marker and any response not bound to the exact running ingress ID/config.

## 4. Tests-first implementation slices

### `R7CSI-IMP-001` — pure selector schemas

Сначала failing unit cases: canonical round-trip; closed keys/types/caps; role/alias/scope/generation mismatch; extra bytes/directives; ABSENT/PRESENT/UNKNOWN; receipt redaction. Затем minimal pure renderer/parser/hash implementation.

Checks: AST/import compile where available, `tools/test_rebuild7_selector.py` named schema group, PowerShell parse, `git diff --check`. Docker/config/product source unchanged.

### `R7CSI-IMP-002` — durable writer and journal

Сначала filesystem/fault cases on Linux semantics: symlink/nonregular/hardlink/foreign owner/mode/unknown leaf; stale expected digest mutation0; temp/full-write/reopen/hash; crash before/after file fsync/rename/parent fsync; exact journal transitions; missing/incomplete/mismatched journal blocks recovery; cap+1; concurrent stale CAS one winner.

Implement fd-relative closed modes. Windows-host source tests alone do not close durability; Linux pinned-container execution is a later runtime gate.

### `R7CSI-IMP-003` — local Django marker

Сначала tests prove base URLconf marker absent; local URLconf exact path only; required env closed; any presence of `ESTAKADA_RESTORE_VERIFY_WRITE` rejected before import; GET/HEAD204 exact headers/no body/no cookie/no DB query; wrong host, POST/other methods and reflected headers denied; request/service intake remains off; DB option exactly read-only after import.

Then minimal settings/view/URLconf. No model/migration/product public route.

### `R7CSI-IMP-004` — generation-v5 storage binding

Сначала direct tests prove safe closed binding output changes on source/schema/migration/table-content/media inventory changes, excludes raw values/paths, and does not alter capture/verify/reconcile projections. Then add only `binding-capture` mode and selector-side closed combiner.

Existing 12 generation-v5 diagnostic cases remain mandatory. Media byte truth continues to come from unmodified `rebuild7_media.py check`.

### `R7CSI-IMP-005` — fixed Nginx and Compose source

Add configs only after static negative oracles exist:

- selector include only at fixed `/selector/selectors/active.conf` in `http` context;
- no selector/unknown/multiple `.conf` fails `nginx -t`;
- only closed upstream name can result from renderer;
- identity headers are never synthesized/overwritten by Nginx;
- public GET/HEAD proxy; admin/editor/upload/request POST and all other mutating methods terminate before upstream;
- loopback-only ports; no production/live host/domain/TLS;
- exact scope labels, networks, RO/RW mounts, tool profiles and no Docker socket;
- compose interpolation cannot supply arbitrary command/path/capability or `ESTAKADA_RESTORE_VERIFY_WRITE`;
- cutover implementation inventory is closed and every runtime file/mounted config/image is represented in its canonical digest.

Static source review occurs here. `nginx -t` and `docker compose config` wait for separate runtime permission.

### `R7CSI-IMP-006` — thin coordinator and safe status

Implement `Status` first: read-only exact inventory, selector/journal state and safe bitmap. Mutating actions remain gated by explicit switch parameter and closed readiness authority.

Then implement Bootstrap/Switch/Recover phases exactly from design:

1. acquire existing R7 coordinator lock family and reject foreign/temp resources;
2. capture exact implementation/image inventory; prepare candidate/config/storage/direct probes;
3. create+fsync `PREPARED` journal;
4. exact ingress identity stop and `INGRESS_STOPPED`;
5. fresh implementation/image plus target/network/alias/storage/direct-marker revalidation;
6. one selector CAS and journal `SELECTOR_COMMITTED`;
7. exact ingress start, fresh implementation/image/target identities/storage, then separate Windows host-loopback marker+canary;
8. terminal journal+safe receipt after final implementation/image revalidation;
9. `finally` preserves active/data/evidence, removes only exact staging after known state, proves bitmap/tool containers/lock.

Every Docker action uses exact ID reinspection immediately before mutation. No `docker compose down`, wildcard name filter mutation, retry loop, HUP or implicit recreate. Missing/mismatched journal allows only matching ingress stop and owner inspection.

Coordinator has a separate exact `DisposeRehearsal` phase/action, never implicit generic teardown. It is allowed only after terminal receipt, stopped exact disposable ingress/apps, fresh proof durable local selector/current ingress digest+IDs unchanged, and preserved external safe receipt. It then:

1. checks exact rehearsal project/scope labels and closed resource manifest;
2. removes only listed disposable containers by exact ID;
3. verifies zero links/members, then removes only listed rehearsal networks by exact ID/name+labels;
4. verifies selector volume closed inventory, copies/verifies safe receipt outside the volume, proves mount links0 and removes only the exact rehearsal selector volume by name+labels;
5. proves rehearsal containers/networks/volumes0 and durable local/old/new DB/media/evidence unchanged.

Durable local volume/ingress, DB/media volumes, old/new authorities and external receipts are structurally excluded from removal manifest. Any identity/link/local-digest mismatch stops teardown and retains remaining resources for owner inspection. Failure is cleanup-not-confirmed; no broad `down`, prune or second equivalent removal attempt.

### `R7CSI-IMP-007` — synthetic runtime/config/fault confirmation

Runtime attempt 23 ноября 2026 года через approved PowerShell 7 contract: selector unit `14/14 PASS`, generation diagnostics `13/13 PASS`, Django identity/settings `6/6 PASS`, system check0; затем synthetic Setup завершился общим `R7C_SYNTHETIC_DOCKER_FAILED_1`. Cleanup самого wrapper: `R7C_SYNTHETIC_CLEANUP_PASS scope=rehearsal:3fc6691a7050497cbe87ea27cd955f78 containers=0 networks=0 volumes=0`; отдельный post-audit: testRoot0, labeled synthetic containers0/networks0/volumes0, fixture root empty. Повтор не выполнялся. Independent runtime evidence review: `CHANGES_REQUIRED P0=0/P1=1/P2=0`: state был записан после image inspect, но примерно двадцать Docker calls setup используют один error token и теряют stdout/stderr, поэтому exact failed stage и факт достижения migrate/seed не доказуемы. Следующий owner-gated source-only шаг — closed stage token плюс bounded safe diagnostic для каждого mutating setup call, independent review; новый runtime требует отдельного решения и не считается автоматически разрешённой confirmation.

Observability remediation завершена source-only: `Invoke-Docker` принимает только closed `ValidateSet` stage, все setup/cleanup calls размечены; failure token содержит только fixed stage, exit, canonical args SHA-256 и byte-count/SHA-256 stdout/stderr, без raw args, SQL, paths, output или secrets. Allow-failure и exact cleanup semantics сохранены. Repeat independent review: `APPROVED P0=0/P1=0/P2=0`; parser трёх scripts и `git diff --check` PASS. Docker после исправления не запускался; новый bounded run требует отдельного owner gate.

Owner-approved run после observability remediation снова подтвердил unit `14/14`, generation `13/13`, Django `6/6`, затем остановился точно на `stage=DB_SCHEMA exit=2`, до migrate/seed. Cleanup scope `rehearsal:f2e984b83e82461cb0fa60ec89eb44cd` и отдельный post-audit: testRoot0, containers0, networks0, volumes0, fixture root empty. Source assessment выявил official-entrypoint race: прежний socket-only `pg_isready` мог принять временный init server до final TCP restart. Bounded fix: DB_READY проверяет exact container TCP `127.0.0.1:5432` в прежнем 45×1s loop; DB_SCHEMA остаётся socket psql без password exposure. Repeat source review: `APPROVED P0=0/P1=0/P2=0`; parser/diff-check PASS. Runtime confirmation после fix не выполнялась.

Owner-approved confirmation после TCP fix прошёл DB_SCHEMA и DB_MIGRATE, затем остановился на `stage=DB_SEED exit=1`; cleanup scope `rehearsal:7d86e858f2524fc3b006fd819ee6c565` и post-audit testRoot/containers/networks/volumes0. Source cause deterministic: fixture передавал `create_superuser(username="synthetic-owner")`, но StaffUserManager и DB invariant разрешают OWNER только `nesadmin`; atomic seed откатился до остальных rows. Harness-only fix использует exact `username="nesadmin"`; repeat current-file review `APPROVED P0=0/P1=0/P2=0`, diff-check PASS. Новый runtime требует отдельного owner gate, поскольку migrations уже исполнялись в disposable synthetic DB.

Следующий owner-approved run повторил exact `DB_SEED exit=1` с теми же stderr bytes1974/SHA `001ffe0f8bb0a6e6e0990b3fda71ee36ac1ca2dc6060cb74c8bb680655bfab`; cleanup scope `rehearsal:ec4b67600b4444a8b43e05d46248a632` и post-audit exact0. Anti-loop остановлен. Повтор доказал, что username-гипотеза не была исполняемой причиной: absolute `/project/tools/rebuild7_selector_fixture.py` получает `sys.path[0]=/project/tools`, а environment не содержал `PYTHONPATH`, поэтому `django.setup()` не мог импортировать `/app/config` и падал до owner line. Исправление добавляет exact `PYTHONPATH=/app` в общий migrate/seed/readonly environment, совпадая с canonical cutover compose. Current-file repeat review: `APPROVED P0=0/P1=0/P2=0`; parser/diff-check PASS. Runtime после fix не выполнялся.

Следующий owner-approved run подтвердил полный synthetic setup: seal old/new и `R7C_SYNTHETIC_SETUP_PASS`, затем первый Bootstrap остановился `R7C_APP_ALIAS_MISMATCH`; cleanup scope `rehearsal:50e48186b19a45048a4d4d7937c639a3` и post-audit exact0. Source cause: stopped containers после `compose create` имеют declared endpoint alias, но `network inspect .Containers` может ещё не содержать active endpoint; pre-start `Get-App(...,$false)` ошибочно требовал active owner до start. Fix сохраняет pre-start identity/env/mount/network/declared-alias checks, а alias owner count/exact ID проверяет только при `RequireRunning=true`; final Get-App после exact-ID start обязателен, duplicate-alias fault semantics сохранены. Repeat review: `APPROVED P0=0/P1=0/P2=0`; parser/diff-check PASS. Runtime после fix не выполнялся.

Следующий owner-approved run снова прошёл fresh gates и `R7C_SYNTHETIC_SETUP_PASS`; alias phase больше не падала, Bootstrap продолжился и остановился позже общим `R7C_DOCKER_COMMAND_FAILED`. Cleanup scope `rehearsal:63386b6ae4994e9196e845214f9f49e6` и post-audit exact0. Coordinator observability remediation ввела обязательный closed stage для всех Docker paths и safe failure token: stage/exit, args SHA, stdin presence/bytes/SHA, stdout/stderr bytes/SHA без raw content. Tool stages различают implementation/binding/authority/media/probe/selector phases; app/ingress/durable/dispose calls размечены. Repeat review: `APPROVED P0=0/P1=0/P2=0`; parser/diff-check PASS. Runtime после fix не выполнялся.

Source fixture/harness подготовлены 23 ноября 2026 года. После первого review `CHANGES_REQUIRED P0=0/P1=7/P2=3` исправлены runtime-role isolation, real seeded canary, source/storage binding, exact cleanup, replacement/recovery и safe host test paths; финальный repeat source-only review: `APPROVED P0=0/P1=0/P2=0`. PowerShell parse трёх скриптов и `git diff --check` PASS. Владелец разрешил один bounded Docker package. Initial run остановился до Docker/fixture на допустимом Windows ACL owner representation корня repo: `R7C_TEST_DIRECTORY_INVALID`; post-audit synthetic containers/networks/volumes0, testRoot0. Малое harness-only исправление сохранило non-reparse repo boundary и current-owner для writable `work/testRoot/secrets`, repeat review `APPROVED 0/0/0`. Единственная materially changed confirmation также остановилась до Docker: Windows PowerShell `5.1.19041.6456` не имеет `ProcessStartInfo.ArgumentList`; это затрагивает четыре process-wrapper call site в трёх R7C scripts. Финальный post-audit: synthetic containers0/networks0/volumes0, testRoot0. После нового owner approval начата PS5-compatible source remediation через exact Windows command-line encoder; PS5 parser исправлен удалением literal UTF-8, но Docker-free native argv probe дважды дал одинаковый `R7C_TEST_COMMAND_FAILED_91`. Владелец затем отдельно утвердил fail-closed запрет неиспользуемого empty argv; empty literals в process call arrays не найдены, но non-empty space/quote/backslash/Unicode probe снова получил тот же `exit91`. Это опровергло empty-argument гипотезу. Разрешённый sanitized diagnostic также дважды не дал closed schema: сначала guard ошибочно зависел от JSON property order, после исправления stdout разобрался в объект без `schema`; payload не раскрывался. Diagnostic anti-loop остановлен, testRoot0, synthetic containers/networks/volumes0, parse/diff-check PASS. PS5 remediation не прошла review и не считается завершённой. Рекомендованный выход — удалить неподтверждённый PS5 encoder/probe, зафиксировать уже установленный PowerShell 7 как минимальный shell contract и использовать нативный `ArgumentList`.

Следующий owner-approved run прошёл fresh gates и полный synthetic setup, затем остановился точно на `SELECTOR_JOURNAL_CREATE exit=1`: stdin был ровно один newline (`bytes=1`, SHA-256 `01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`), cleanup scope `rehearsal:08b6e37126e8429ba2b30b6705189531` и отдельный post-audit exact0. Независимый PowerShell 7 micro-proof подтвердил deterministic collision параметра `$Input` с automatic `$input`: payload превращался в пустой enumerator, JSON исчезал, оставался добавленный newline. Bounded source fix переименовал только параметр и две body-ссылки `Invoke-SelectorTool` в `$Payload`; positional call sites и нижележащий `$InputText` не изменены. Repeat review: `APPROVED P0=0/P1=0/P2=0`; parser трёх scripts и `git diff --check` PASS. Runtime после fix не выполнялся и требует отдельного owner gate.

Owner-approved confirmation после `$Payload` fix прошёл fresh gates `14/14`, `13/13`, Django `6/6`, system check0, полный setup/seal и прежнюю journal-create границу, затем остановился новым `R7C_PUBLIC_CANARY_FAILED`. Wrapper cleanup scope `rehearsal:d04cc4f5565f4f49aef04bd046020f87` PASS; отдельный post-audit: testRoot0, fixtureItems0, state0, authority0, synthetic containers0/networks0/volumes0. Direct source evidence доказал deterministic cause: fixture создавал только Synthetic canary, тогда как product public shell `_validate_menu` требует exact пять navigation identities и fail-closed возвращает 503 при их отсутствии. Fixture-only fix добавил пять deterministic published root Page + PRIMARY Route с exact names/targets и matching kinds/outcomes, без PageContent; canary остаётся отдельной реально rendered DB page. Independent repeat review: `APPROVED P0=0/P1=0/P2=0`; parser трёх scripts и `git diff --check` PASS. Runtime после fix не выполнялся и требует отдельного owner gate.

Следующий owner-approved confirmation прошёл fresh gates, setup/seal, journal, public canary и основной selector (`R7C_SELECTOR_PASS`, role old), затем fault suite остановился PowerShell error `A hash table can only be added to another hash table`. Wrapper cleanup scope `rehearsal:04abda36e55d4f92a38257c38dc52a52` PASS; отдельный post-audit: testRoot0, fixtureItems0, state0, authority0, synthetic containers0/networks0/volumes0. Direct source evidence доказал вторую case-insensitive automatic-variable collision: локальный accumulator `$matches` в `Read-ExternalReceipt` перезаписывался automatic `$Matches` после `-cnotmatch`, затем `+= [pscustomobject]` пытался сложить hashtable и object. Bounded rename только accumulator и четырёх use sites в `$candidates` сохранил regex и exact-one receipt selection/validation. Independent repeat review: `APPROVED P0=0/P1=0/P2=0`; parser трёх scripts, absence `$matches` и `git diff --check` PASS. Runtime после fix не выполнялся и требует отдельного owner gate.

Следующий owner-approved confirmation прошёл fresh gates, setup/seal и полный synthetic Bootstrap/Switch new/Switch old с тремя `R7C_SELECTOR_PASS`, затем до fault suite остановился в Quiesce manifest path общим `R7C_HEX_INVALID`. Wrapper cleanup scope `rehearsal:498d63f60d9a4165bddf6e1f4f2ed65c` PASS; отдельный post-audit: testRoot0, fixtureItems0, state0, authority0, synthetic containers0/networks0/volumes0. Retained evidence не позволяет безопасно различить receipt argument и stored digest; journal argument там explicit null. Bounded source-only observability сохранила exact regex/null/length/selection semantics и добавила только fixed no-value tokens `R7C_EXTERNAL_RECEIPT_ARGUMENT_INVALID`, `R7C_EXTERNAL_JOURNAL_ARGUMENT_INVALID`, `R7C_EXTERNAL_RECEIPT_DIGEST_INVALID` через optional code с прежним default. Independent repeat review: `APPROVED P0=0/P1=0/P2=0`; parser трёх scripts и `git diff --check` PASS. Runtime после remediation не выполнялся и требует отдельного owner gate.

Owner-approved diagnostic confirmation снова прошёл fresh gates, setup/seal и Bootstrap old/Switch new/Switch old, затем Quiesce дал exact `R7C_EXTERNAL_JOURNAL_ARGUMENT_INVALID`. Cleanup scope `rehearsal:e1ab23ff8d0e40a0a2a192a0187a414f` и отдельный post-audit exact0. Cause deterministic: два null-intent call site передавали explicit positional `$null` в optional typed `[string]$JournalSha256`, PowerShell bind превращал его в empty string, поэтому null guard считал journal filter присутствующим. Bounded fix удалил только третий аргумент в Quiesce manifest и Dispose post-audit; default остаётся actual null. Два call site с реальными journal SHA не изменены; exact receipt digest selection, Python verifier, scope/digest checks сохранены. Independent review: `APPROVED P0=0/P1=0/P2=0`; parser трёх scripts, call inventory и `git diff --check` PASS. Runtime после fix не выполнялся и требует отдельного owner gate.

Owner-approved confirmation после удаления explicit `$null` снова прошёл fresh gates, setup/seal и Bootstrap old/Switch new/Switch old, затем повторил тот же exact `R7C_EXTERNAL_JOURNAL_ARGUMENT_INVALID`. Cleanup scope `rehearsal:383a3810a08f4a1bb324855a96dc03c9` и отдельный post-audit exact0. Anti-loop остановлен на второй эквивалентной попытке; третьего runtime нет. Новое evidence доказывает, что typed `[AllowNull()][string]$JournalSha256 = $null` материализует empty string даже при использовании default, поэтому прежний call-site-only fix недостаточен. Пакет приостановлен владельцу до решения на source-only parameter-contract remediation и нового independent review. Project DB/media/READY-media, actual storage, real rehearsal, durable local, Q003, external copy, cutover/live не затрагивались.

Owner-approved source-only parameter-contract remediation завершена: optional `ReceiptSha256`/`JournalSha256` в `Read-ExternalReceipt` теперь `[AllowNull()][object] = $null`; любое non-null значение обязано иметь exact runtime type `[string]` и пройти прежнюю 64-char lowercase hex validation до path/filter logic. Empty и non-string fail-closed fixed field token; omitted/explicit-null сохраняют отсутствие фильтра. Actual-function AST microtest current file: omitted/null проходят argument guards, empty/non-string отклоняются, valid digest проходит; файловых мутаций и Docker не было. Four-call inventory подтверждает два real journal digest и два omitted journal call site; exact filename selection, supplied journal equality, exact-one candidate, stored identity/digest, Python external verifier и scope checks сохранены. Independent repeat review: `APPROVED P0=0/P1=0/P2=0`; parser трёх scripts и `git diff --check` PASS. Новый runtime — только отдельное решение владельца после anti-loop remediation.

Owner-approved confirmation после optional-object remediation прошёл fresh gates, setup/seal, Bootstrap old/Switch new/Switch old и впервые `R7C_QUIESCE_PASS`; Dispose затем остановился StrictMode property error на global mount scan: bind/tmpfs mount rows законно не имеют `Name`. Cleanup scope `rehearsal:f73a6f9ef453467da3d147642110470b` и отдельный post-audit exact0. Bounded helper `Assert-NoSelectorVolumeMount` безопасно требует nonempty string `Type`, пропускает non-volume без чтения `Name`, для volume требует nonempty string `Name` и запрещает exact selector volume. Global unfiltered container scan, identity и post-audit сохранены. Actual-function AST microtest: bind/tmpfs PASS, missing Type invalid, volume missing/empty Name invalid, other volume PASS, selector volume linked. Independent repeat review: `APPROVED P0=0/P1=0/P2=0`; parser трёх scripts и `git diff --check` PASS. Runtime после fix не выполнялся и требует отдельного owner gate.

Owner-approved confirmation после mount-shape fix прошёл fresh gates, setup/seal, три selector transitions и Quiesce; Dispose прошёл global mount scan, затем остановился exact `STORAGE_BINDING exit=1`. Cleanup scope `rehearsal:3679696c50b74a4d8b944ffe456b16e5` и отдельный post-audit exact0. Deterministic source cause: old/new binding equality выполнялась после удаления selector volume, но финальный `storage-binding` step использует `selector-verify`, которому эта volume нужна. Bounded reorder сохранил expression и exact semantics: app/ingress+web networks remove → old/new binding equality при существующей selector volume → последний global link scan → identity/remove selector volume → absence/durable/external-evidence post-audits. Independent repeat review: `APPROVED P0=0/P1=0/P2=0`; parser трёх scripts, exact-order source check и `git diff --check` PASS. Runtime после reorder не выполнялся и требует отдельного owner gate.

Owner-approved confirmation после Dispose reorder прошёл fresh gates, setup/seal, три selector transitions, Quiesce и `R7C_DISPOSE_PASS`; базовый synthetic lifecycle впервые полностью PASS. Fault filesystem subset `8/8 PASS`, первый fault fixture setup/Bootstrap PASS, затем harness остановился до injection: array splatting `@Arguments` передал literal `-AuthoritySet` позиционно как Action. Cleanup scope `rehearsal:7d80be8fff924f59ba450c2472b93297` и отдельный post-audit exact0. Bounded harness fix заменил dynamic argument array на closed typed helper: Bootstrap|Switch, old|new, seven catchable stages+none без crash, nonempty Pattern; coordinator вызывается literal named parameters с fixed synthetic authority. Пять call site обновлены, crash stages остаются exact child-exit helper. No-Docker binding proof дошёл до `R7C_AUTHORITY_MISSING`, legacy `@Arguments` absent. Independent repeat review: `APPROVED P0=0/P1=0/P2=0`; parser и `git diff --check` PASS. Runtime после fix не выполнялся и требует отдельного owner gate.

Owner-approved fault confirmation после typed-helper fix прошёл fault filesystem subset `8/8` и все семь catchable boundary: precommit cases сохранили old selector либо ожидаемое ambiguous post-start состояние, terminal rollback cases вернули old selector; во всех случаях mutation bitmap `CLOSED`, каждый disposable scope очищен exact0. Первый crash case подтвердил exact child exit86 после ingress stop, затем Recover остановился StrictMode error: inspect возвращает journal envelope с digest в `.sha256` и payload в `.value`, а coordinator сохранял только `.value`, поэтому первый recovery transition не имел CAS digest. Wrapper cleanup scope `rehearsal:b9bf9f308f5d49e19ebd9d7576058d34` и независимый post-audit testRoot/fixture/state/authority/containers/networks/volumes exact0. Bounded product coordinator fix валидирует envelope digest fixed token `R7C_RECOVERY_JOURNAL_INVALID` и добавляет его только как coordinator-side `sha256` metadata к рабочему journal; Python transition по-прежнему сравнивает `--expected` с текущим stored digest. Добавлен exact source regression oracle; PowerShell parse, actual envelope-transfer proof и `git diff --check` PASS, host Python остаётся Windows Store stub. Independent review: `APPROVED P0=0/P1=0/P2=0`. Новый runtime после product fix требует отдельного owner gate; project DB/media/READY-media, actual storage, real rehearsal, durable local, Q003, external copy, promotion, cutover/live не затрагивались.

Owner-approved confirmation после Recover digest fix повторно прошёл fault filesystem `8/8`, все семь catchable boundary и впервые обе hard-crash границы: exact child exit86 после ingress stop и после selector commit, затем `R7C_RECOVERY_PASS phase=ROLLED_BACK role=old`; Quiesce/Dispose и cleanup каждого crash scope exact0. Следующий negative port-blocker case остановил harness: Docker Desktop publish `127.0.0.1:18086` не появился в Windows `IPGlobalProperties` active-listener inventory, поэтому coordinator законно не выдал ожидаемый `R7C_LOOPBACK_PORT_IN_USE`, Bootstrap завершился и wrapper сообщил `R7C_EXPECTED_FAILURE_MISSING_R7C_LOOPBACK_PORT_IN_USE`. Wrapper cleanup scope `rehearsal:1eb5d96634f541c48da0fa8bfa8d2d1a` и независимый post-audit testRoot/fixture/state/authority/containers/networks/volumes exact0. Harness-only fix заменил Docker port proxy на host-native `TcpListener` exact `127.0.0.1:18086`, synchronous Start до child и Stop в finally; no-Docker cross-process proof увидел exact listener count1/address/port. Product coordinator, topology и data paths не изменены. Independent review: `APPROVED P0=0/P1=0/P2=0`; parser и `git diff --check` PASS. Runtime после harness fix требует нового owner gate, поскольку предыдущий run уже исполнил product paths.

Следующий owner-approved confirmation повторно прошёл filesystem `8/8`, catchable7, обе hard-crash Recover границы, исправленный host-native port-blocker и storage-binding mismatch; каждый завершённый scope имел exact cleanup. По явному запросу владельца run остановлен во время baseline Bootstrap target-replacement case, до duplicate-alias и общего suite PASS. Ctrl+C не вывел wrapper cleanup, поэтому отдельно выполнен штатный synthetic Cleanup scope `rehearsal:5d53055382ca4665b71b1596c63524df` с containers/networks/volumes0. Первый post-audit нашёл только один interrupted test root; после exact path/root/name/non-reparse проверки удалён только `work/r7c-selector-test-0ee762b0fc9848bbb4d029fd6811454e`. Финальный post-audit: testRoot/fixture/state/authority/containers/networks/volumes exact0. Partial run не считается полным faults PASS; работа приостановлена владельцем до возобновления, затем suite запускается fresh.

После возобновления владельцем fresh faults run остановился до product execution на `coordinator.lock already exists`. Wrapper cleanup нового scope `rehearsal:7386d3cd2eeb42019c98686a4387ab81` дал containers/networks/volumes0. Расширенный post-audit доказал единственный остаток вчерашнего Ctrl+C: canonical lock schema с PID57044/startTicks, тогда как testRoot/fixture/state/authority/containers/networks/volumes были0; прежний аудит lock не считал. PID отсутствовал, поэтому после exact path/root/name/schema/property/type/non-reparse/size/live-owner проверки удалён только stale `work/r7c-selector-synthetic/coordinator.lock`. Финальный расширенный post-audit: testRoot/fixture/state/authority/lock/containers/networks/volumes exact0. Source/product/topology не менялись; новый fresh runtime требует отдельного решения владельца как повтор той же стадии.

Owner-approved fresh confirmation 24 ноября 2026 года завершила `faults` suite с exit0 и `R7C_TEST_SUITE_PASS suite=faults`: filesystem subset `8/8`, семь catchable boundaries, обе hard-crash Recover boundaries, host-native port-blocker, storage-binding mismatch, target replacement и duplicate alias PASS. Каждый disposable scope завершён exact cleanup; отдельный финальный расширенный post-audit: testRoot/fixture/state/authority/lock/containers/networks/volumes exact0. Docker warning о deprecated `--time` не изменил command exit или semantics. Independent runtime evidence review fault mechanics: `APPROVED P0=0/P1=0/P2=0`. Final IMP-009 review затем выявил `P1`: direct `faults|synthetic` wrapper paths обходили обязательные fresh unit/generation/Django/config prerequisites, поэтому faults mechanics доказаны, но AC-014 и closure ещё нет.

AC-014 source remediation объединила `all|synthetic|faults` в одну runtime branch с обязательным exact порядком unit→generation→Django→config до Setup и closed subsequent dispatch; regression oracle фиксирует общую ветку, порядок и оба dispatch condition. PowerShell parse, отдельный source oracle и `git diff --check` PASS; independent repeat source review `APPROVED P0=0/P1=0/P2=0`, bypass/cleanup regression0. Owner-approved materially changed `faults` confirmation прошла exit0: до Setup fresh selector unit `16/16`, generation diagnostics `13/13`, Django `6/6` + system check0 и compose config PASS; затем filesystem8/8, catchable7, hard-crash Recover2 и все четыре negative cases завершились общим `R7C_TEST_SUITE_PASS suite=faults`. Каждый scope очищен exact0; отдельный expanded post-audit testRoot/fixture/state/authority/lock/containers/networks/volumes exact0. Final IMP-009 review `APPROVED P0=0/P1=0/P2=0`; `R7CSI-IMP-007` CLOSED, повторный faults runtime не нужен. Project DB/media/READY-media, actual storage, real rehearsal, durable local, Q003, external copy, promotion, cutover и live не затрагивались и не разрешены.

Requires separate bounded Docker permission. Runtime wrapper first executes fresh named suites in exact order: `unit`, generation-v5 diagnostics (existing 12 plus binding cases), `django`, `config`; only after all PASS may it run `synthetic`, then `faults`. Thus Windows Store Python absence cannot leave prepared tests unexecuted.

Synthetic old/new targets are the real project Django app under `config.settings.local_cutover`, not a mimicking HTTP server. Each uses an isolated disposable PostgreSQL database and synthetic empty/bounded media authority created inside the test project; no project DB/media/READY-media read. Both expose the real identity view and a deterministic real public canary from an explicitly seeded synthetic page. Tests prove `ESTAKADA_RESTORE_VERIFY_WRITE` rejection and exact read-only connections before selector work.

Synthetic execution uses only the closed `AuthoritySet=synthetic` work root and requires every DB/network/source/media/secrets/authority/selector/sentinel resource name to carry the exact disposable rehearsal project prefix. Missing fixture authority fails before Docker; actual authority cannot be substituted. The durable-local unchanged oracle is also a disposable prefixed sentinel in this suite, so IMP-007 does not inspect or mount actual local selector/ingress.

До реализации IMP-007 fixture setup named `faults|all` обязаны завершаться fail-closed `R7C_COORDINATOR_FAULT_FIXTURE_REQUIRED`, а не печатать ложный PASS. Runtime slice должен заменить этот prerequisite реальным fresh orchestration всех synthetic-only coordinator boundary hooks, recovery и cleanup; source package IMP-001..006 не объявляет эти suites пройденными.

Then suite proves config syntax, scope isolation, ABSENT→old bootstrap, old→new→old, internal direct probe versus separate Windows host-loopback marker/canary, implementation/image drift pre/post CAS, port/listener, all journal/phase crashes, stale CAS, container replacement, alias duplicate, storage-receipt mismatch and exact `DisposeRehearsal` cleanup containers0/volumes0/networks0/bitmap exact with preserved external receipt.

Synthetic storage receipts and disposable DB/media are explicitly test-only and cannot satisfy actual-storage, sealed generation or rehearsal acceptance. Same failure twice stops without third attempt.

### `R7CSI-IMP-008` — actual storage binding confirmation

Requires a new DB/media-read owner gate, one exact old rollback authority and one fresh `SEALED`/B002 readiness authority. Runs generation-v5 capture plus actual media byte check through the proposed verifier, but does not create selector/ingress, bootstrap or switch. Confirms safe output, source post-audit, containers0 and data unchanged.

This slice cannot run while fresh SEALED/B002 authority is absent. It may remain BLOCKED without invalidating source implementation of pure selector mechanics.

#### External dependency for `R7CSI-IMP-008`

Production storage binding, new VPS provisioning/configuration, production B002, domain/TLS, transfer and deploy are not part of this core/local implementation plan and do not count toward its completion percentage. Their approved G01–G14 dependency bridge is retained in `docs/additional-vps-production-plan.md` with a separate progress percentage under D-1857.

`R7CSI-IMP-008` therefore remains an external optional dependency. It may stay BLOCKED without preventing the core/local project from reaching 100% and owner acceptance. No provider, install, network, DB/media-read, external-copy, cutover or live action is authorized here.

### `R7CSI-IMP-009` — independent final code/config review

Independent architecture/data/concurrency/security/destructive/no-bloat review checks full diff, named evidence, exact gates, current foundation unchanged, no secret/path leakage and no live apply. Findings receive bounded remediation and repeat review. Source implementation is not complete before `APPROVED P0/P1/P2=0`.

Actual disposable `R7C-REHEARSAL-001`, durable production bootstrap and Q003 are external VPS/transfer-contour decisions under D-1857; none is required for core/local 100% or implied by IMP-001..009.

## 5. Acceptance matrix

For D-1857 accounting, `R7CSI-AC-001..003` and `R7CSI-AC-011..014` are core source/synthetic acceptance. Actual-authority/runtime criteria `R7CSI-AC-004..010` belong only to the external VPS/transfer contour and are not required for core/local 100% or owner acceptance.

- `R7CSI-AC-001` → `R7CS-AC-001`: closed canonical scope/role/alias/generation selector and caps.
- `R7CSI-AC-002` → `R7CS-AC-002`: same-filesystem exact CAS, stale mutation0, file+parent fsync under fault injection.
- `R7CSI-AC-003` → `R7CS-AC-003`: validation/stop/CAS/start/observation separate; HUP/reload0.
- `R7CSI-AC-004` → `R7CS-AC-004`: actual target marker matches fresh DB/media storage binding through internal direct probe and distinct Windows host-loopback ingress proof. This is external-contour acceptance, not core/local completion.
- `R7CSI-AC-005` → `R7CS-AC-005`: fresh pre-CAS/post-start identity/network/alias/storage plus implementation/config/image inventory checks reject substitution.
- `R7CSI-AC-006` → `R7CS-AC-006`: mutation fence and DB/media fingerprints unchanged; selector opens writes0.
- `R7CSI-AC-007` → `R7CS-AC-007`: mandatory journal/crash boundaries; ambiguous state stopped+closed, no blind retry/third CAS.
- `R7CSI-AC-008` → `R7CS-AC-008`: marker+canary required; mixed/unknown never success.
- `R7CSI-AC-009` → `R7CS-AC-009`: closed safe receipt and exact staging cleanup; active/data/evidence retained.
- `R7CSI-AC-010` → `R7CS-AC-011`: rehearsal/resource separation and distinct ABSENT→old bootstrap. This is external-contour acceptance, not core/local completion.
- `R7CSI-AC-011`: current foundation compose/config/containers and production/live remain unchanged through source/synthetic work.
- `R7CSI-AC-012`: synthetic PASS is not promoted to actual storage/rehearsal/Q003 evidence.
- `R7CSI-AC-013`: exact disposable teardown removes only identity/label/no-link checked rehearsal resources after current-local unchanged; external safe receipt preserved, durable/data/evidence excluded.
- `R7CSI-AC-014`: any `ESTAKADA_RESTORE_VERIFY_WRITE` presence is rejected and runtime executes fresh unit/generation/Django/config suites before synthetic/fault evidence.

## 6. Gates и stop rules

1. Independent review этого source-only plan; remediation/repeat review до `APPROVED P0/P1/P2=0`.
2. Отдельное owner approval на source edits IMP-001..006, tests written before each implementation slice; Docker/media read0.
3. Independent source review before any runtime.
4. Отдельное bounded Docker approval для IMP-007; initial run плюс максимум одна materially changed confirmation по правилу проекта.
5. External VPS/transfer contour only: отдельное DB/media-read approval для IMP-008 только после exact authorities; не требуется для core/local 100%.
6. Final independent review IMP-009.
7. External VPS/transfer contour only: отдельные future gates для real rehearsal, durable production bootstrap и Q003; не требуются для core/local 100%.

Та же ошибка второй раз при эквивалентном действии останавливает пакет без третьей попытки. New dependency/image/service daemon/model/migration/public endpoint/base URL/production config, change foundation compose, generic path/command input, external network или data mutation немедленно требуют plan amendment и нового review.

Текущая точка: `R7CSI-IMP-007` CLOSED после materially changed faults confirmation exit0: mandatory fresh unit16/generation13/Django6+check0/config chain до Setup, полный faults PASS и expanded cleanup/post-audit exact0. Final `R7CSI-IMP-009` review `APPROVED P0=0/P1=0/P2=0`. По D-1857 новая VPS, production B002, actual IMP-008, domain/TLS, перенос, deploy, rehearsal/bootstrap, Q003/cutover и destructive cleanup вынесены в отдельный дополнительный контур `docs/additional-vps-production-plan.md` и не влияют на готовность core/local проекта. Следующий приоритет — локальное завершение и owner acceptance. Все внешние действия по-прежнему не разрешены.
