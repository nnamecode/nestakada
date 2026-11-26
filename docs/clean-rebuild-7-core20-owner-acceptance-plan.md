# CORE-20 / RB7-OWNER-ACCEPTANCE-001 — финальная локальная приёмка владельцем

Дата: 2026-11-25. Статус: plan и coordinator source review `APPROVED P0=0/P1=0/P2=0` после remediation `0/3/4 → 0/2/3 → 0/0/0`. Runtime/media-read требует отдельного решения владельца.

Source coordinator: `scripts/prepare-core20-owner-acceptance.ps1` плюс bounded native-process helper `tools/core20_bounded_process.js`. Remediation вводит pinned Node/Docker/Playwright paths, SHA и exact202 dependency-tree digest без install/network fallback; каждый Docker/Playwright native call получает PID/deadline/output cap и exact process-tree termination. Evidence commit выполняется только после stop, zero clients, post projection, exact bitmap/resource audits и staging cleanup; failure удаляет uncommitted evidence и сохраняет lock marker для owner disposition. PNG имеют exact signature/dimensions, receipt — closed `bytes=<decimal>` grammar.

Second remediation reconciles daemon-owned state after a timed-out Docker client: exact preview IDs are stopped from observed state, exact owned pre/post capture names are identity-checked and removed, then resources are re-audited. Playwright records and validates the exact persistent session Node PID, audits the named session after close and may kill only that validated process tree before re-audit. Readiness/browser/client deadlines use monotonic Stopwatch ticks. The complete Playwright tree rejects file or directory reparse points, pinned absolute `taskkill.exe` replaces PATH lookup, and native output uses one combined cap.

Final repeat source/security/data/destructive review: `APPROVED 0/0/0`; runtime0.

First owner-authorized runtime stopped before boundary admission, source projection, preview start, browser or media read. Exact source PostgreSQL container was already `stopped`, so the initial generic result was `CORE20_OWNER_ACCEPTANCE_UNAVAILABLE cleanup=clients,clients-post,bitmap`. Read-only post-audit proved DB/app/ingress all stopped, CORE20 containers/networks/volumes/staging/evidence0, Playwright session/error files0 and retained failure lock1. No product/browser execution occurred. Harness-only remediation now emits exact `CORE20_SOURCE_DB_NOT_RUNNING` and gates active-runtime cleanup behind `boundaryAdmitted`; independent review `APPROVED 0/0/0`. Fresh runtime requires a new owner decision covering exact DB start, validated failure-lock disposition and a new bounded capture.

Reviewed recovery path `-RecoverStoppedSource` keeps the retained lock exclusively held, validates its exact known bytes, writes a durable non-overwriting archive `failures/<old-run>.lock`, then rewrites/fsyncs the active lock for the new run without an unlocked gap. Invalid lock/archive failures leave original bytes untouched; rewrite failure restores the captured original and the durable archive remains. Only exact stopped DB/app/ingress IDs are admitted; exact DB start and `pg_isready` are bounded, then the ordinary reviewed capture runs. Recovery/source review after one P1 remediation: `APPROVED 0/0/0`. Runtime remains owner-gated.

Second owner-authorized recovery successfully archived the first lock, started the exact source DB and passed bounded PostgreSQL readiness. Pre-capture container then ran for 13 seconds and exited1 before preview app/ingress/browser start; host wrapper collapsed its safe generation code to generic `CORE20_OWNER_ACCEPTANCE_UNAVAILABLE`. Cleanup/post-audit: DB running; app/ingress stopped; CORE20 containers/networks/volumes/staging/evidence/Playwright sessions0; current failure lock1 and first archive1. Product/browser execution0.

Diagnostic remediation extracts only the last token matching `(CORE20|R7)_[A-Z0-9_]+` from failed bounded Docker output and maps `R7_*` to `CORE20_CAPTURE_R7_*`; raw stdout/stderr remain hidden. The recovery gate accepts exactly the immediate second known lock only when its canonical parent archive matches byte-for-byte ASCII/LF under a read handle denying write/delete; it archives the second lock with CreateNew and requires DB already running plus app/ingress stopped. A third chained retry is rejected. Independent review after one P2 remediation: `APPROVED 0/0/0`. Any diagnostic confirmation requires a fresh owner decision.

Third owner-authorized diagnostic confirmation returned exact `CORE20_CAPTURE_R7_LOCAL_GENERATION_UNAVAILABLE`. It stopped in the pre-capture container before preview app/ingress/browser start and before owner evidence. Final read-only post-audit: source DB running; app/ingress stopped; clients0; CORE20 containers/networks/volumes/staging/evidence/Playwright sessions0; current failure lock1 and prior archives2. The reviewed recovery chain is exhausted and intentionally rejects another chained retry. Source-only remediation now classifies the generic generation failure by a closed safe stage vocabulary while preserving existing specific R7 codes; independent source/security/data/release review `APPROVED P0=0/P1=0/P2=0`. Python execution remains unavailable on the host and Docker was not used for this review. No further runtime is authorized by the previous decisions.

Owner-approved source-only disposition adds separate `-RecoverGenerationDiagnostic` for exactly one materially changed confirmation. It pins the actual lineage `c1daa7f3-3183-4148-8ae4-fbdf9ed81a9b → ff2bbccc-5cf8-4240-8f22-f5bbc872893b → 52f82993-3046-4844-a449-92d477d771b0`, requires canonical ASCII/LF bytes for active lock and both archives, distinct GUIDs, exclusive active handle, CreateNew durable archive and rollback on rewrite failure. It requires DB already running and app/ingress stopped and cannot start DB. Any next lock, including a stage-specific failure, is not eligible for this recovery mode. Independent repeat review after remediation of one P1 finding: `APPROVED P0=0/P1=0/P2=0`. Docker/runtime remains separately owner-gated.

The separately owner-authorized materially changed confirmation returned exact `CORE20_CAPTURE_R7_GENERATION_MIGRATION_PARITY_UNAVAILABLE`. It stopped in pre-capture before preview app/ingress/browser and owner evidence. Post-audit: source DB running, app/ingress stopped, source clients0, CORE20 containers/networks/volumes/staging/evidence0, current failure lock1 and archives3. This result is not eligible for another automatic recovery. Source inspection shows the current tree contains the new default-off `service_requests.0001_initial` migration while the reused RB5 preview database predates CORE-18; the exact applied/missing set remains unconfirmed until a separately authorized read-only migration-metadata diagnostic. No source DB mutation, clone, new preview topology or parity exception is approved.

The separately authorized read-only metadata diagnostic confirmed the exact difference: source files contain `service_requests.0001_initial`; the preview DB has applied `accounts.0001_initial`, `audit.0001_initial`, `gallery.0001_initial`, `media.0001_initial`, `pages.0001_initial`, `pages.0002_sitesettings` and `pages.0003_page_primary_url_mutable`, but no `service_requests` migration. No user/request/media rows were read; post-query clients0. The recommended remediation is a reviewed disposable local clone of the RB5 database, apply exactly the missing migration to the clone, and run final preview/capture against that clone while preserving the source DB byte/state authority. Mutating the source DB or weakening generation parity is not recommended. Clone/new preview topology, migration, destructive clone cleanup and runtime remain unapproved until a new owner decision.

## Disposable-clone remediation addendum

Owner approved source-only plan/code/review, not runtime. The coordinator adds a separate `-DisposableCloneRemediation` mode bound to the exact retained failure lock `900b20e3-f443-428e-8c69-073937f26307` and its exact three archived ancestors. No later lock shape is eligible.

Only for this mode, this addendum replaces the section 1/2 requirements that capture and walkthrough use the existing source database and existing preview containers and the prohibition on database clone, one migration and container creation. The exact browser walkthrough, evidence limits, source immutability, loopback boundary, no-external rule and owner-acceptance criteria remain unchanged. The original path remains closed by its retained failure lock and is not silently widened.

Before mutation, a digest-only `estakada.r7-source-guard-v1` snapshot records the source DB raw+semantic schema digests, applied-migration digest, table-count/content digests and READY-media metadata digest. It emits no migration names, table names, row payloads, media bytes, paths or credentials. Source clients must be zero.

The mode creates exactly one database `estakada_core20_<32hex>` inside the already pinned local PostgreSQL container using the zero-client RB5 source as a template. It never migrates the source. One labelled, resource-capped helper is first created, pinned by returned container ID and closed immutable projection, then started with the pinned app image to apply only `service_requests.0001_initial` to the clone; it is removed manually only after the same exact identity is revalidated. Closed validation requires the exact migration row, both exact request tables and row counts `0|0`; ordinary generation-v5 capture on the clone must then pass full migration parity.

The stopped legacy preview containers remain untouched. Fresh GUID-owned app and ingress containers use the pinned images, existing internal DB network, read-only roots, dropped capabilities, no-new-privileges, resource caps and exact labels. App has host ports0 and targets only the clone. Ingress alone publishes `127.0.0.1:18085`, mounts READY public media read-only, and uses a fresh config derived from the pinned RB5 config with only its upstream alias replaced. The existing loopback-only exact11 browser walkthrough is unchanged.

In `finally`, browser closes; exact labelled ingress/app/migration helpers and capture helpers are reconciled and removed; clone clients reach zero; a second generation-v5 clone capture must equal the first; the exact GUID clone database is dropped; then a fresh source guard must equal the first. Existing DB/app/ingress identities and stopped bitmap, source clients0, clone databases0, CORE20 containers/networks/volumes0 and staging0 are mandatory. Failure keeps a durable lock and removes uncommitted owner evidence. Success retains only the exact12 owner-evidence files until the later owner decision. Runtime permission must explicitly include local source data copy into the clone, applying one migration to the clone, fresh preview, and destructive cleanup of only the exact clone/GUID resources; it does not authorize source mutation, external copy, VPS, deploy, live or an automatic retry.

Independent architecture/security/data/destructive/release review after remediation `P0=0/P1=3/P2=3 → 0/1/1 → APPROVED P0=0/P1=0/P2=0`. PowerShell 7 parse, Node syntax and `git diff --check` pass; Python execution remains unavailable on the host and Docker/runtime was not used for source review.

The first owner-authorized disposable-clone runtime stopped before migration, preview, browser or media serving with `CORE20_CLONE_DATABASE_IDENTITY_INVALID`. PostgreSQL had successfully created the exact GUID clone, closed its ACL and stored the exact run marker; the harness incorrectly read a shared database comment with `obj_description` instead of `shobj_description`. Cleanup therefore refused destructive drop and reported `clone-nginx-config,clone-database,resources`; the nginx error was also a harness false positive because config creation had not started. Read-only audit proved source DB running with clients0, legacy app/ingress stopped, CORE20 containers/networks/volumes0 and the one clone with exact OID `3753432`, owner, run marker, ACL and clients0. Under the already authorized exact-GUID cleanup scope, the clone identity was revalidated immediately before manual drop; post-audit after five seconds proved clone databases0, CORE20 resources0, source clients0 and original bitmap exact. Source-only remediation uses `shobj_description`, gates nginx cleanup validation on actual config creation and binds a possible confirmation to the exact new failure lock plus all four exact ancestors. Runtime has not been repeated.

Independent repeat security/data/destructive review of that harness-only remediation: `APPROVED P0=0/P1=0/P2=0`. A materially changed confirmation remains owner-gated and has no automatic successor.

The separately authorized materially changed confirmation passed clone creation, exact migration and generation-v5 pre-capture, then stopped before browser at `CORE20_READINESS_FAILED`. Docker event metadata proves migration exit0 and both exact app/ingress containers remained running for the entire 90-second readiness window; they were killed only by reviewed cleanup. Cleanup/post-audit: source DB running with clients0, legacy app/ingress stopped, clone DB0, CORE20 containers/networks/volumes/staging/evidence0, current failure lock1 and archives5. No screenshot or owner evidence was committed. The exhausted mode has no accepted successor. A future proposal should first add separate safe app-direct and ingress-loopback readiness classification without raw logs, then receive new source review and a new owner decision; no further runtime is authorized.

Owner-approved source-only staged-readiness remediation now waits for exact app-direct HTTP 200 from inside the pinned app container before creating ingress. The bounded probe catches its own HTTP/network errors and emits only `CORE20_APP_STATUS_<code>`, where code is closed to `000` or HTTP `100..599`; timeout becomes `CORE20_APP_READINESS_STATUS_<code>`. Only after app PASS is the pinned ingress created. Loopback readiness uses PowerShell 7 `SkipHttpErrorCheck`, retains only the same closed three-digit status and fails as `CORE20_INGRESS_READINESS_STATUS_<code>`. Response bodies, exception text, container logs and DB data are never emitted. The current failure lock is intentionally not accepted by any recovery mode, so this source change cannot authorize or accidentally start another runtime.

Independent staged-readiness source/security review after redirect/status hardening: `APPROVED P0=0/P1=0/P2=0`. App redirects are not followed; both stages accept only `000` or HTTP `100..599`. Runtime0 after remediation.

Owner-approved source-only disposition binds a possible staged-readiness confirmation to the exact active lock `7b4b9c8f-22ef-4f85-ba31-95089fdb568b`, exact parent `daeb6054-14ed-432b-9399-4245c002d382`, exact `CORE20_READINESS_FAILED cleanup=` bytes and the five exact archived ancestors through `52f82993-3046-4844-a449-92d477d771b0`. It does not accept the prior active-lock forms or any later result. Docker/runtime remains unapproved pending independent review and a separate owner decision.

Independent destructive/release review of the exact six-link disposition: `APPROVED P0=0/P1=0/P2=0`. Runtime0; any staged-readiness confirmation remains a separate owner gate and has no automatic successor.

The separately owner-authorized staged-readiness confirmation proved app-direct HTTP 200 after clone/migration/pre-capture, then returned exact `CORE20_INGRESS_READINESS_STATUS_000` before browser. Cleanup/post-audit: source DB running clients0, legacy preview stopped, clone DB0, CORE20 containers/networks/volumes/staging/evidence0, lock1/archives6. Source review then proved the host PowerShell 7.6.9 `Invoke-WebRequest` has no `-TimeoutSec` parameter: parameter binding failed inside the closed catch and was normalized to `000`, so that result does not prove an ingress transport fault. Host proxy also points to closed loopback port 9, so explicit `-NoProxy` remains required. The mode is exhausted and no further runtime is authorized.

Owner-approved source-only remediation adds PowerShell 7 `-NoProxy` only to the fixed loopback ingress request and replaces unsupported `-TimeoutSec 2` with the verified host parameters `-ConnectionTimeoutSeconds 2 -OperationTimeoutSeconds 2`; host proxy environment is not changed. A possible confirmation is bound to exact active lock `64740252-d287-457d-85e6-0ae3fbd4a364`, exact parent `7b4b9c8f-22ef-4f85-ba31-95089fdb568b`, exact `CORE20_INGRESS_READINESS_STATUS_000 cleanup=` bytes and all six exact ancestors. Any previous or later lock is rejected. Runtime remains unapproved pending independent review and a separate owner gate.

Independent network/destructive/release repeat review after one P1 remediation: `APPROVED P0=0/P1=0/P2=0`. Host PowerShell 7.6.9 command metadata confirms the exact NoProxy parameter set and both timeout parameters; parse and diff-check pass, runtime0.

The owner-authorized host-compatible confirmation again passed clone/migration/pre-capture and app-direct HTTP 200, then returned genuine `CORE20_INGRESS_READINESS_STATUS_000` with supported timeout parameters and `-NoProxy`. Cleanup/post-audit is exact: source clients0, legacy bitmap exact, clone DB0, CORE20 containers/networks/volumes/staging/evidence0, lock1/archives7. Docker Engine is 29.9.2 under Docker Desktop/WSL2; the only runtime network is the pinned `bridge` with `Internal=true`, no explicit gateway-mode options and only the source DB endpoint after cleanup. The same published-port transport must not be repeated. Recommended next design is a fresh GUID-owned ordinary preview bridge used only as ingress's host-publishing/default-route network while app remains only on the existing internal DB network; ingress is dual-homed solely to reach the app alias. This changes network topology and ingress outbound capability, so it requires a new source-only plan/code/security review and later owner runtime gate.

Owner-approved source-only dual-network remediation creates exactly one ordinary bridge `nestakada-core20-preview-<32hex>` after app-direct 200 and before ingress creation. The network is labelled with exact scope/run/role, pinned by returned 64-hex ID and a closed static projection, has Docker scope `local`, is not config-only and has no config source, is non-internal/non-attachable/non-ingress and IPv4-only, and forces default host binding to `127.0.0.1`. It initially has members0. App remains exclusively on the existing internal DB network. Ingress is created with the preview bridge as primary/publishing network, then connected to the internal DB network only to resolve the exact app alias; boundary requires exact two networks for ingress, exact one preview member equal to the pinned ingress ID, and no DB/app membership on preview. The closed Nginx config has only the fixed app upstream and static/media locations, so its new default route cannot be selected by request input. Cleanup removes exact ingress ID first, requires preview members0 and unchanged network projection, removes exact network ID, then completes the existing app/clone/source guards and stable-zero audit. If a bounded Docker create call times out after daemon-side creation but before returning an ID, cleanup reconciles only the exact GUID name, closed immutable container/network projection and exact labels, captures the resulting 64-hex ID, and still removes by that pinned ID; any mismatch remains fail-closed.

A possible confirmation is bound to exact active lock `d40d43cd-cd66-4b70-bc62-ba4812731443`, parent `64740252-d287-457d-85e6-0ae3fbd4a364`, exact ingress-000 failure bytes and all seven exact archives through the initial lock. Any next result is ineligible. Docker/runtime remains unapproved pending independent network/security/destructive review and a separate owner gate.

Independent network/security/destructive repeat review after timeout-reconciliation, exact-ID mutation and closed network-authority remediation: `APPROVED P0=0/P1=0/P2=0`. PowerShell 7 parse and `git diff --check` pass; Docker/runtime/media/browser remain 0. Any dual-network confirmation is still a separate owner gate and has no automatic successor.

The owner-authorized dual-network confirmation passed disposable clone creation, the exact migration, pre-capture, app-direct HTTP 200 and loopback ingress HTTP 200, then stopped on the closed generic `CORE20_BROWSER_FAILED` before owner evidence could be accepted. Cleanup/post-state is exact: failure reports `cleanup=`; staging and owner evidence are empty; the new lock is `32aefdbf-50db-45fe-8086-75d588b99496`, recovered from the archived host-transport lock, and all eight ancestors remain. No automatic runtime successor is authorized.

Source-only browser diagnostic remediation maps only bounded Playwright command failures to a closed safe stage vocabulary: `OPEN`, `POLICY`, `PID`, `RESIZE`, `NAVIGATION`, `SCREENSHOT` or `EXTERNAL`. Raw stdout/stderr, URLs, page content and exception text remain hidden. A possible future confirmation is bound byte-for-byte to the exact browser-failure lock, exact parent and all eight exact archives; any later lock is ineligible. Runtime remains separately owner-gated pending independent browser/security/destructive review.

Independent browser/security/destructive repeat review after one P1 wrapper-normalization remediation: `APPROVED P0=0/P1=0/P2=0`. PowerShell parse and `git diff --check` pass; Docker/runtime/media/browser0 after remediation. Any confirmation remains a separate owner gate and has no automatic successor.

The separately authorized diagnostic confirmation again passed clone/migration/pre-capture/app-direct and ingress HTTP 200, then returned exact `CORE20_BROWSER_POLICY_FAILED` before navigation or owner evidence. Cleanup/post-state is exact with `cleanup=`, staging0 and evidence0. The active lock is `8a775d4f-693a-41cf-9627-763e36f52261`, recovered from the archived generic browser failure; nine ancestors remain. No repeat is authorized.

Pinned local Playwright CLI documentation and implementation prove `run-code` requires one function expression `async page => { ... }`, while the harness passed bare statements; they also prove the isolated context does not expose `process`, while the policy attempted `process.pid`. Source-only remediation wraps policy, navigation and external-audit snippets as function expressions, removes the invalid process access, and captures the session PID only from the CLI's exact documented/open implementation line before validating the pinned Node process. A possible confirmation is bound to the exact policy-failure lock and all nine archives. Runtime remains separately owner-gated pending independent browser/security/destructive review.

Independent browser/security/destructive review of function-expression/PID remediation and exact ten-link disposition: `APPROVED P0=0/P1=0/P2=0`. Local exact open-line regex validation, PowerShell parse and `git diff --check` pass; Docker/runtime/media/browser0 after remediation. Any confirmation remains a separate owner gate and has no automatic successor.

The owner-authorized confirmation stopped at recovery preflight with exact `CORE20_RECOVERY_BITMAP_INVALID` before DB start, clone, browser or media. Closed read-only post-audit proved exact DB/app/ingress IDs with bitmap `db=stopped/app=stopped/ingress=stopped`, CORE20 containers/networks/volumes0, and active lock `3edf38fc-bd3c-4619-9b10-c59f46cd06c9` recovered from the archived policy failure. The local DB stop is consistent with a Docker Desktop/host interruption; external internet is not required by this loopback-only package. No repeat is authorized.

Source-only recovery remediation binds a possible confirmation to the exact stopped-DB lock and all ten archives, requires the exact pinned DB stopped with exact app/ingress stopped, starts only the pinned DB ID, waits for bounded `pg_isready`, and then enters the unchanged disposable-clone flow. Any other bitmap or lock remains fail-closed. DB start and runtime require a separate owner gate pending independent data/destructive review.

Independent data/destructive review of exact DB-start recovery and eleven-link disposition: `APPROVED P0=0/P1=0/P2=0`. PowerShell parse and `git diff --check` pass; Docker/runtime/media/browser0 after remediation. DB start plus any confirmation remain a separate owner gate and have no automatic successor.

## 1. Цель и границы

Закрыть последний core-результат локальной демонстрацией уже реализованного сайта из `src/` и явным решением владельца. Техническое основание не прогоняется повторно: CORE-01…CORE-19 уже закрыты, включая exact115/public browser evidence, R7-LOCAL-001 restore proof, CORE-18 exact148 и CORE-19 PostgreSQL exact250.

Демонстрация использует только существующий RB5 preview:

- source database `estakada_rb5_home_preview`, которая до начала обязана быть running;
- exact existing containers `nestakada-rb5-home-app` и `nestakada-rb5-home-ingress` с неизменными identities/images/configuration;
- loopback-only ingress `127.0.0.1:18085`;
- существующие read-only source/media mounts.

Старый foundation/local-admin demo из `app/`, новый импорт, fixture load, migration, DB/media mutation, container recreation, image build/pull, external network, VPS, deploy, cutover и live запрещены.

## 2. Preflight, immutable projection и восстановление состояния

Один project-owned coordinator удерживает exclusive host lock от preflight до завершения `finally`. Перед start он обязан fail-closed проверить:

1. exact container IDs/images/configured loopback binding соответствуют сохранённому RB5 preview inventory;
2. app и ingress остановлены, source PostgreSQL запущен;
3. closed PostgreSQL client inventory source database равен zero и неизвестных ресурсов с CORE-20 prefix нет;
4. mounts остаются read-only там, где это утверждено preview contract;
5. host port `127.0.0.1:18085` свободен;
6. исходный bitmap записан как `db=running/app=stopped/ingress=stopped`.

До start disposable capture helper переиспользует reviewed `estakada.r7-local-generation-v5` и строит canonical source DB table-count/content digests плюс READY-media inventory. После browser capture, остановки ingress/app и возвращения client inventory к zero второй fresh helper обязан получить те же release/capture/media digests. Любой drift закрывает run как failure и не допускает owner acceptance.

Coordinator запускает exact app, затем exact ingress, ждёт максимум 90 секунд и требует `GET / = 200` через loopback. Browser capture имеет общий timeout 10 минут; timeout/abort всегда переходит в cleanup. В `finally` coordinator закрывает browser session, останавливает ingress, затем app, ждёт zero source DB clients и проверяет:

- exact исходный bitmap;
- те же container IDs/images/config/network membership/loopback binding/mount read-only flags;
- отсутствие созданных CORE-20 containers/networks/volumes/staging и снятие lock только после всех проверок;
- повторный canonical DB/media capture без drift.

Source PostgreSQL остаётся running. Запись в source DB не предполагается и доказывается равенством двух semantic projections, а не одним process bitmap.

## 3. Owner walkthrough

Coordinator создаёт fresh isolated Playwright session сначала на `about:blank`, до первой навигации ставит fail-closed request route и разрешает только scheme/authority `http://127.0.0.1:18085`. Любой non-loopback request abort-ится и делает capture failure. Storage state/cookies не загружаются, внешние partner links не нажимаются, после каждой навигации проверяются status200, console errors0, broken images0 и horizontal overflow0.

Фиксированный walkthrough использует только exact115 authority:

| MAP | URL | Семейство |
|---|---|---|
| MAP-001 | `/` | HOME |
| MAP-002 | `/services/` | каталог услуг |
| MAP-015 | `/services/drugie-uslugi/shinomontazh/` | детальная услуга |
| MAP-008 | `/gallery-of-works/` | каталог галереи |
| MAP-036 | `/gallery-of-works/ford-mondeo` | альбом |
| MAP-007 | `/contacts` | контакты |
| MAP-003 | `/partners` | legacy/public family |

Для всех семи MAP сохраняется desktop screenshot 1440×900. Mobile screenshot 390×844 сохраняется ровно для `MAP-001`, `MAP-002`, `MAP-008`, `MAP-007`: итого exact11 PNG.

Owner evidence создаётся только в новом отсутствующем каталоге `%TEMP%\estakada-core20-owner-acceptance\<runId>`, где `<runId>` — canonical lowercase GUID. Coordinator до создания проверяет resolved ancestry внутри exact parent, отсутствие reparse/symlink на parent/run path и owner текущего Windows account; существующий run directory означает fail-closed без перезаписи. Fixed filenames:

- `MAP-001-desktop.png`, `MAP-002-desktop.png`, `MAP-015-desktop.png`, `MAP-008-desktop.png`, `MAP-036-desktop.png`, `MAP-007-desktop.png`, `MAP-003-desktop.png`;
- `MAP-001-mobile.png`, `MAP-002-mobile.png`, `MAP-008-mobile.png`, `MAP-007-mobile.png`;
- `manifest.json`.

Каждый PNG обязан быть non-empty и не более 20 MiB; exact12 files вместе не более 128 MiB; extra files/directories/reparse points запрещены. Safe manifest содержит только run ID, MAP/path, viewport, filename, byte length, SHA-256, HTTP/console/image/overflow/network results и pre/post safe digests. Credentials, browser storage, DB payloads и отдельно скопированные media originals отсутствуют.

Receipt учитывает `owner_evidence=screenshots11 manifest1` отдельно от runtime `staging=0`. Evidence directory сохраняется до owner decision и final evidence review, не попадает в Git и не удаляется автоматически: его последующее exact удаление является отдельным destructive gate. Preview и browser уже остановлены до передачи изображений владельцу.

Владелец получает сохранённый локальный walkthrough и проверяет без служебных идентификаторов:

1. главную страницу в desktop и mobile;
2. каталог услуг и детальную услугу;
3. каталог галереи и альбом;
4. контакты и legacy/public family page;
5. отсутствие горизонтального переполнения, поломанных изображений и неожиданных внешних виджетов;
6. что общий вид, навигация, тексты и доступные локальные данные достаточны для завершения разработки сайта.

Технические exact115, permissions, admin command semantics, concurrency, restore и default-off intake не перекликиваются вручную: их принятые evidence сохраняются. Intake не включается. Админские credentials не показываются и не передаются; VPS/production не являются частью walkthrough.

## 4. Решение и критерий закрытия

После walkthrough владелец отвечает обычным языком:

- `принимаю` — фиксируется owner acceptance; либо
- перечисляет конкретные замечания — CORE-20 остаётся OPEN, каждое замечание классифицируется как defect или новый scope до исправления.

CORE-20 закрывается только по AND-условию: technical capture PASS + успешный `finally` + exact post-bitmap/projection + явная owner acceptance + independent final evidence review `APPROVED 0/0/0`. Ошибка cleanup, projection drift или замечание финального review оставляет CORE-20 OPEN даже после слова `принимаю`.

Технический PASS без явной owner acceptance не закрывает CORE-20. Owner acceptance не разрешает создание/настройку VPS, production data read/copy, deploy, cutover, live, LEGAL-01 activation, destructive cleanup, commit или push.

## 5. Evidence

Закрывающий evidence содержит только:

- exact pre/post bitmap, DB-client inventory и safe container/image/config/network/mount identities;
- readiness/loopback HTTP status, canonical DB/media projection equality и browser non-loopback requests0 без row payloads, secrets или media bytes;
- exact seven route labels и `owner_evidence=screenshots11 manifest1 files12 bytes<=128MiB`;
- cleanup `containers=0 networks=0 volumes=0 staging=0 lock=0 bitmap=exact`, owner evidence учтён отдельно;
- дословное решение владельца `accepted` либо безопасный список замечаний;
- independent final evidence review.

Новые screenshots, media originals, дампы, credentials и private/browser storage в Git не добавляются.
