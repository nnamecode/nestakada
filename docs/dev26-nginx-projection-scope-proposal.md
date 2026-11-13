# DEV-26/27: generated Nginx projection + controlled reload

Статус: **remediation третьего architecture-specific review завершена; final repeat review требуется**. Дата: 2026-11-12. Основание: D-592, D-899–D-906, `DEV26-Q002=A` и owner `DEV26-Q003=1`. Reviews: P1=2/P2=2, затем P1=3, затем P1=1 `R26A-S001-DURABLE`; все findings отражены без permanent service/scope bloat. Product code/config/image не менялись.

Этот документ заменяет njs runtime-кандидат из общего scope, но сохраняет R26-S001–008 и DEV26-AT-001–014. Реализация, image build, compose/config mutation и persistent apply пока не разрешены.

## 1. Выбранная граница

DEV-26 использует vanilla закреплённый Nginx без njs и без нового постоянного service. После успешной owner-сборки DEV-25 доверенный локальный оператор явно запускает host-side `Activate`:

1. Одноразовый offline projector на уже закреплённом app image, с `network_mode: none`, читает DEV-25 reserve volume только RO через отдельный read-only verifier protocol и удерживаемый shared source lock.
2. Projector повторно проверяет active pointer, current manifest и каждый response/resource byte, затем копирует их в новый immutable release отдельного `html-reserve-delivery` volume и генерирует только bounded data maps для versioned fixed Nginx template.
3. Host wrapper проверяет release manifest/digests и выполняет candidate `nginx -t` на том же закреплённом ingress image, без сети и без изменения active selector.
4. Только после PASS host создаёт fsynced activation journal, вызывает отдельный one-shot selector-writer для атомарной замены малого `active.conf`, посылает ingress master один `HUP` через Docker CLI и проверяет exact loopback-only generation canary.
5. Если canary не подтверждает candidate, wrapper восстанавливает предыдущий canonical selector state `ABSENT` либо `PRESENT(exact bytes,digest)`, посылает один rollback `HUP` и проверяет previous empty/candidate canary. Автоматического третьего reload/retry нет.
6. При успешной активации normal upstream по-прежнему имеет приоритет; reserve используется per-request только для public GET/HEAD при transport error/502/503/504. Возврат к Django автоматический на следующем нормальном запросе.

Owner POST `/manage/html-reserve/` **не** вызывает Docker, projector или reload. App не получает Docker socket, PID namespace, signal capability, host path, delivery mount или write access к ingress config. Django UI показывает только DEV-25 source fact `reserve built` и постоянную подсказку, что фактическая delivery activation проверяется локальной host-командой `Status`; UUID/state delivery в Django не отображаются. Authoritative delivery state существует только в host delivery volume/receipt/canary. Автоматической ложной активации и status bridge нет.

## 2. Почему delivery package отделён от DEV-25 reserve

Нельзя заставлять loaded Nginx config ссылаться прямо на `generations/<uuid>` DEV-25: две следующие owner-сборки могут легально удалить старое поколение до host activation. Поэтому projector создаёт самодостаточный immutable delivery release:

```text
html-reserve-delivery/
  control.lock
  activation.json
  selectors/
    active.conf
  releases/
    <delivery-uuid>/
      release.json
      maps.conf
      responses/<sha256>.html
      resources/<sha256>.<allowlisted-suffix>
```

- release UUID генерируется операторским процессом и не берётся из request;
- `release.json` — canonical bounded manifest с DEV-25 generation UUID+manifest SHA, projection schema/template version, file names, sizes и SHA-256;
- projector создаёт staging directory, пишет regular files с private modes, полностью переоткрывает и сверяет release, затем публикует каждый durable object единым protocol `write temp → fsync(temp fd) → renameat/replace → fsync(parent directory fd)`; fsync только до rename недостаточен;
- `active.conf` содержит только fixed schema/template ID и exact immutable delivery UUID; arbitrary Nginx directives из DB/content/manifest туда не попадают;
- first Start не создаёт selector/release: fixed base config использует closed optional selector glob `/delivery/selectors/*.conf`; zero matches означает canonical empty delivery и fixed fallback503. После первой activation inventory допускает ровно `selectors/active.conf`; temp leaf не имеет `.conf` suffix. Unknown/multiple selector закрывает Verify/Start;
- ingress монтирует delivery volume RO; app service не монтирует его вообще;
- projector получает delivery RW только в одноразовом tools profile и не имеет сети/DB secrets;
- один control-writer получает delivery RW только в отдельном one-shot tools profile, не монтирует source reserve и не имеет сети/DB secrets. Его closed modes: `journal-transition`, `selector-replace`, `recover-transition`; projector selector/journal не меняет. Host передаёт bounded canonical input и expected old/new digests, но сам в Docker volume не пишет;
- тот же pinned tools image имеет strictly read-only mode `verify-active`: delivery RO, network none, no source/DB/secrets/write paths. Он разрешён только Foundation Start, explicit Verify и pre-Activate под общим host lock и удаляется после вызова;
- ingress не монтирует DEV-25 reserve/state/media/request-ledger.

Hard caps не шире DEV-25: один source file ≤8MiB, source total ≤256MiB, resources ≤1024, all files ≤4096, source manifest ≤2MiB. Projection добавляет отдельные caps до allocation: config/maps total ≤2MiB, delivery releases ≤4, staging ≤2, root entries closed. Точные более узкие measured caps фиксируются implementation plan до кода.

## 3. Fixed template и generated data

Base Nginx config остаётся code-owned. Projector не генерирует свободный Nginx-программный текст; он использует один versioned emitter с closed grammar:

- keys — exact canonical `$request_uri` DEV-25 target/resource URL;
- values — только digest-derived leaf name, один из fixed response classes `200/301/302/404`, allowlisted content-type/policy IDs, exact validated internal Location и optional fixed robots value;
- CR/LF/NUL/control, ambiguous escaping, duplicate keys, external/userinfo Location, unknown status/type/policy и value over cap закрываются до emission;
- user-controlled value никогда не становится filesystem directory или directive name;
- file path строится только из validated delivery UUID + digest leaf;
- generated include ограничен `map` data; location/proxy/error/header/static-serving logic находится только в reviewed base template;
- `nginx -t` — обязательный второй parser gate, но не заменяет emitter validation.

Fixed template сначала сохраняет existing private/specialized locations и limits. Оставшийся public namespace разделяется до proxying: только GET/HEAD идут в intercepting public proxy; прочие methods идут в non-intercept proxy. При 502/503/504 internal fallback dispatch использует exact generated maps. Unknown/ambiguous target даёт fixed contact503/no-store; nearest match отсутствует.

Для manifest status 200/301/302/404 fixed internal locations используют `error_page =<literal-status>` и static file из immutable release, чтобы вернуть сохранённые bytes вместе с literal status. Redirect `Location` берётся только из validated map. Resource classes используют fixed content type/cache policy. `HEAD` проходит тот же selection/file metadata path, Nginx подавляет body. Hostile upstream headers скрываются до internal fallback; closed headers остаются из DEV26-AT-014.

До code gate config-only spike обязан доказать на точной Nginx1.30.6 semantics:

- `$request_uri` exact raw-query matching и rejection duplicate/noncanonical query;
- method/URI/query preservation на named/error_page dispatch;
- literal status + exact stored body для 200/301/302/404;
- exact nullable Location, Content-Length/HEAD и no inherited hostile headers;
- variable/static path не допускает traversal или external URI;
- private/method/normal-upstream paths имеют reserve reads0;
- bounded generated map size помещается в ingress128MiB/0.25CPU/8 connections.

Если любой из этих пунктов не подтверждается официальной документацией плюс разрешённым config-only smoke, branch A возвращается к architecture review; product implementation поверх недоказанной semantics запрещён.

## 4. Controlled activation protocol

Host wrapper — новый проектный операторский инструмент, не сторонняя зависимость. Перед его будущим добавлением владельцу отдельно объясняются действия и изменения на компьютере. Scope действий:

1. Проверить exact repo/foundation locks, approved image IDs, environment/run manifest, `Active=True`, один expected ingress container и отсутствие чужих containers/resources.
2. Взять один environment-scoped exclusive host lock, общий с Foundation Start/Stop/UnitTests и другим reserve Activate; lock удерживается до финального receipt.
3. Запустить ровно один projector tools container с existing app image: source reserve RO, delivery RW, source code RO, network none, UID10001, read-only rootfs/tmpfs/caps. Projector открывает существующий `build.lock` fd-relative с `O_RDONLY|O_NOFOLLOW`, проверяет regular file/owner/mode/inode и берёт `LOCK_SH|LOCK_NB`, совместимый с DEV-25 `LOCK_EX`; lock удерживается от первого pointer read до полного copy, reopen и release verification. Projector ничего не создаёт/удаляет/reconcile в source. Если exact Linux/filesystem shared-lock semantics не проходят отдельный low-level oracle, projection блокируется до нового review.
4. Получить immutable candidate release и canonical candidate receipt; projector не меняет `active.conf`.
5. Запустить disposable exact ingress image `nginx -t` с base config, candidate selector/release RO и без app/network. Любой warning/error/nonzero отклоняет candidate без HUP.
6. До selector mutation вызвать one-shot control-writer mode `journal-transition` с canonical input: unique operation UUID, exact old/new selector states (`ABSENT` или `PRESENT` with bytes+digest), delivery UUIDs, environment/run/container/image identity, expected no-active-operation и stage `PREPARED`. Writer проверяет closed schema/current journal state, публикует journal через `temp → fsync(temp) → renameat → fsync(parent)` и возвращает digest, который host сверяет. Затем existing mode `selector-replace` проверяет exact old state и публикует new `PRESENT` selector тем же post-rename parent-fsync protocol. Прямой доступ PowerShell к Docker-managed host path и `docker cp` запрещены. Все последующие stages, включая `SELECTOR_CANDIDATE`, `HUP_INTENT` и HUP outcome, также проходят только `journal-transition`; host напрямую journal/selector не пишет.
7. Poll bounded loopback-only internal canary с Host allowlist; PASS только если loaded delivery UUID+selector digest exact candidate. Canary не раскрывает source UUID/path/digest, закрыт от public fallback, POST и non-loopback.
8. При candidate failure control-writer durable transition сначала фиксирует `ROLLBACK_REQUIRED`; mode `selector-replace` восстанавливает recorded previous state только при exact candidate digest. Для old=`ABSENT` он fd-relative проверяет exact selector leaf, выполняет `unlinkat`, затем обязательный fsync selectors parent; для old=`PRESENT` атомарно восстанавливает exact bytes. Затем journal transitions `ROLLBACK_SELECTOR`/`ROLLBACK_HUP_INTENT`, повторная container identity check, один rollback HUP и previous empty/candidate canary. Это компенсирующее действие, не новый mode и не повтор candidate. Если rollback не подтверждён, durable `UNKNOWN`, дальнейшие Activate/Start/Stop запрещены до owner diagnosis; третьего HUP нет.
9. После confirmed candidate durable stage `CANDIDATE_CONFIRMED` является authoritative success. Записать bounded no-secret host receipt: action/result, environment/run ID, old/new delivery UUID, selector/release digests, exact container/image ID, `nginx -t`, HUP/canary/rollback result, timestamps. Request URI/content/paths/PII/secrets не пишутся. Receipt write failure после confirmed canary не откатывает activation: stage становится recoverable `SUCCESS_RECEIPT_WARNING`, а следующий Recovery дописывает receipt без HUP.

Unfinished activation journal является startup barrier. Foundation Start/Stop/UnitTests и следующий Activate до любого container mutation читают и валидируют journal; незавершённая операция не допускает обычное действие. Отдельный `Recover` сначала read-only сопоставляет selector digest, exact loopback loaded-delivery canary и recorded environment/run/container identity. Он либо завершает уже confirmed result/receipt, либо выполняет не более одного заранее записанного rollback на exact recorded container. Selector/canary/container ambiguity, отсутствующий или recreated container дают `UNKNOWN` без blind HUP/retry. Каждая journal/selector transition выполняется только control-writer и обязана завершить `write temp → fsync(temp) → renameat/replace → fsync(parent dir)` до возврата PASS. Abrupt separate-process exit oracles обязательны до temp fsync, после temp fsync, после rename до parent fsync и после parent fsync для release publication, PREPARED, selector replace, candidate HUP stages, candidate canary, rollback selector и rollback HUP.

Signal отправляется только exact running ingress container текущего foundation run; prefix/name-only lookup запрещён. Wrapper не выполняет build/pull/install, не меняет app/db/media-worker и не касается live/VPS.

## 5. Worker drain, retention и cleanup

Reload может оставить old workers обслуживать начатые запросы. Поэтому candidate activation никогда не удаляет release, который использовался каким-либо pre-HUP worker:

- wrapper снимает exact pre-HUP worker inventory через host Docker/process inspection;
- после candidate canary ждёт bounded drain не дольше согласованного timeout и подтверждает исчезновение pre-HUP workers;
- current и previous delivery releases всегда сохраняются; older release удаляется только если не referenced active/previous, его manifest целиком validated и все workers, которые могли его использовать, доказанно завершились;
- при недоказанном drain cleanup пропускается, release остаётся; cap+1 блокирует следующую activation до диагностики, но active serving не повреждается;
- symlink/device/FIFO/socket/hardlink anomaly, unknown root entry или invalid release закрывает cleanup целиком до любых delete;
- удаление выполняется только внутри exact validated delivery volume; DEV-25 reserve и shared files не затрагиваются.

Projector shared-lock блокирует DEV-25 `LOCK_EX` на всё bounded copy+verify окно; он не удерживает до4096 fd одновременно. Pointer/manifest/files открываются fd-relative с no-follow, проверяются и копируются последовательно под lock. Конкурентный owner build получает существующий busy result и не меняет current; после освобождения lock новая сборка — отдельное действие, следующий Activate — отдельная operator action. Обязательны race/lock-busy/fd-cap oracles.

## 6. Failure semantics

| Failure | Результат |
|---|---|
| DEV-25 missing/tampered/unsafe | Projector fail; active delivery untouched |
| Projector crash/staging garbage | Active untouched; bounded later reconcile только proven staging |
| Candidate config invalid/oversize | `nginx -t` fail; no selector/HUP |
| Selector replace fails | No HUP; previous active remains loaded |
| Candidate HUP/config rejection | Old workers/config остаются; restore previous selector + one rollback HUP |
| Candidate canary mismatch/timeout | То же компенсирующее rollback; no third attempt |
| Rollback not confirmed | `unknown`, Activate blocked, owner diagnosis required |
| Wrapper crash at any activation stage | Unfinished fsynced journal blocks normal actions; bounded Recover confirms state or performs at most recorded rollback; ambiguity → `unknown` |
| Delivery file missing after activation | Exact target gives fixed503/no-store; no previous auto-fallback |
| Delivery bytes change after activation | Вне принятой local request-time integrity boundary D-904; следующий Start/Activate/Verify обнаруживает mismatch и блокирует действие как unknown |
| App recovers | Next normal public request returns Django immediately |
| Host wrapper/projector absent | Existing ingress and active delivery continue; owner build alone does not activate new delivery |

## 7. Acceptance delta к DEV26-AT-001–014

Все DEV26-AT-001–014 из общего scope обязательны. Дополнительно:

- `DEV26A-AT-001`: real owner POST/CSRF/unpatched DEV-25 build создаёт generation; без host Activate loaded delivery/canary не меняется.
- `DEV26A-AT-002`: projector на existing app image/network-none читает exact reserve RO, пишет separate delivery RW, повторно проверяет every byte и не имеет DB/runtime secrets/network.
- `DEV26A-AT-003`: malicious target/Location/content metadata не может добавить directive/map entry/path; duplicate/escape/control/oversize закрывается до `nginx -t`.
- `DEV26A-AT-004`: candidate `nginx -t` failure оставляет selector, loaded workers и HTTP behavior byte-identical.
- `DEV26A-AT-005`: successful atomic selector+HUP подтверждается exact loopback canary; fallback отдаёт candidate, normal upstream остаётся приоритетным.
- `DEV26A-AT-006`: injected HUP rejection/canary mismatch выполняет one rollback и подтверждает previous; третьего HUP/retry нет.
- `DEV26A-AT-007`: injected rollback failure создаёт `unknown`, блокирует следующий Activate и сохраняет evidence без secret/path leakage.
- `DEV26A-AT-008`: G1 loaded, DEV-25 builds G2/G3 без Activate — G1 delivery остаётся целой; source cleanup не влияет на Nginx.
- `DEV26A-AT-009`: concurrent fallback requests во время HUP получают целый old/new verified release либо fixed503, но не mixed bytes/headers.
- `DEV26A-AT-010`: current/previous retention и proven worker drain; no-drain сохраняет release и cap-blocks вместо unsafe cleanup.
- `DEV26A-AT-011`: exact container/image/label/run substitution, duplicate container, stopped/recreated ingress и foreign environment fail before signal.
- `DEV26A-AT-012`: foundation Stop/Start и Activate mutually exclusive; crash освобождает host lock через deterministic finally, active delivery сохраняется.
- `DEV26A-AT-013`: named wrapper suites only through `scripts/test-editor.ps1`, no wildcard/Playwright; existing ingress/request/full guard regression calibrated.
- `DEV26A-AT-014`: after tests foundation stopped, no tools containers/staging/foreign networks; private volumes retained, live/VPS untouched.
- `DEV26A-AT-015`: source reserve RO verifier открывает existing lock `O_RDONLY|O_NOFOLLOW`, удерживает shared flock через full copy/reopen; concurrent DEV-25 build busy, source writes0, bounded fd use.
- `DEV26A-AT-016`: selector меняется только one-shot no-network selector-writer с exact old/new digest, fd-relative no-follow temp/fsync/replace; host path/docker-cp writes отсутствуют.
- `DEV26A-AT-017`: separate-process abrupt exit после каждой journal boundary восстанавливается без blind candidate retry; confirmed canary+receipt failure остаётся success-with-warning; ambiguity блокирует Start/Stop/Activate как unknown.
- `DEV26A-AT-018`: Foundation Start/explicit Verify/pre-Activate запускают только one-shot `verify-active` с delivery RO/network-none/no secrets/writes; mismatch blocks, container removed, no daemon/scheduler.
- `DEV26A-AT-019`: PREPARED и каждая journal transition выполняются только control-writer canonical input; host volume writes0, returned digest exact.
- `DEV26A-AT-020`: release, selector и journal fault injection до/после rename доказывает обязательный post-rename parent-dir fsync и deterministic recovery.

- `DEV26A-AT-021`: failed Start/Verify выполняет ровно один journal-transition to UNKNOWN под тем же lock; selector/release/staging writes0, normal Start/Stop/Activate далее blocked.
- `DEV26A-AT-022`: first activation records old selector ABSENT; HUP reject/canary mismatch/crash after candidate selector restores ABSENT by exact conditional unlink+parent-fsync, then empty canary; no new mode/retry.

## 8. Утверждённая bounded integrity boundary

Первое review справедливо выявило R26A-S001: обычный Docker named volume с RO ingress защищает от записи самим ingress, но не является cryptographic/request-time integrity primitive. Projector доказывает SHA до activation, однако vanilla static Nginx после HUP не пересчитывает SHA каждого ответа. Поэтому прежнее DEV26-AT-008 «post-activation tamper всегда fixed503» невозможно честно сохранить в branch A без request-time verifier или иной доказанной immutable/verifiable storage technology.

Владелец утвердил `DEV26-Q003=1` решением D-904 с явным требованием не раздувать проект. Для local foundation branch A:

- весь candidate release хешируется при projection и повторном reopen, затем до HUP;
- existing active release полностью хешируется one-shot `verify-active` перед каждым `Activate`, Foundation `Start` и explicit operator `Verify`; mode получает delivery RO, network none, no source/DB/secrets/write path, работает под общим host lock и обязательно удаляется после результата. Mismatch/missing/unknown entry блокирует действие и даёт durable `UNKNOWN` через отдельный control-writer transition, если запись состояния допустима;
- ingress всегда монтирует delivery RO;
- projector/control-writer/verify-active существуют только как stopped-by-default one-shot modes pinned tools image под exclusive host lock и не остаются daemon. Full write modes разрешены только Project/Activate/Recover; read-only verify-active — только Start/Verify/pre-Activate. Единственное write-исключение после failed Start/Verify — один control-writer `journal-transition` exact current operation/state → durable `UNKNOWN` под тем же lock; selector/release/staging writes в этом пути запрещены. Closed fd-relative writer contract запрещает изменение active release bytes и разрешает только явно выбранные staging/new release/journal/selector paths;
- после завершения операции tools containers отсутствуют; active release не имеет штатного writer до следующей заблокированной операции;
- host/Docker-admin mutation и latent disk corruption после confirmed verification находятся вне local request-time guarantee, как corruption самого pinned image/Docker engine; уже начатая static выдача не обещает SHA detection;
- missing/unreadable static file во время запроса по-прежнему закрывается fixed503/no-store;
- production/VPS boundary этим решением не утверждается и требует отдельного launch review.

Эта owner-approved delta явно заменяет только post-activation tamper часть общего `DEV26-AT-008`. Все malformed/symlink/non-regular/tampered-before-activation oracles и остальные DEV26-AT-001–014 сохраняются. Request-time verifier, helper daemon, native module, scheduler и periodic job запрещены как ненужное расширение.

## 9. Primary documentation evidence

Read-only scope опирается на официальные документы, проверенные 2026-11-12:

- Nginx core `error_page`, named/internal locations: https://nginx.org/en/docs/http/ngx_http_core_module.html
- Nginx proxy interception: https://nginx.org/en/docs/http/ngx_http_proxy_module.html
- Nginx rewrite `if`/`return` processing: https://nginx.org/en/docs/http/ngx_http_rewrite_module.html
- Nginx control/reload behavior: https://nginx.org/en/docs/control.html
- njs file API, по которому предыдущий candidate отклонён: https://nginx.org/en/docs/njs/reference.html

Точные Nginx/base image IDs остаются из `environment/foundation/nginx-build-inputs.lock.json`; package/image upgrade этим scope не разрешён.

## 10. Ворота

1. Independent architecture-specific scope review этого документа.
2. Remediation/repeat review до `APPROVED`, если будут findings.
3. Minimal implementation plan с точными files/slices/caps/config-only spike/fault oracles.
4. Independent plan review до `APPROVED`.
5. Отдельное явное owner approval `DEV26A-IMP-001–NNN`.
6. Только затем tests-first code/config/compose/harness changes.

До этих ворот Nginx/config/image/compose/product code не меняются, projector/wrapper/volume не создаются, HUP не отправляется.
