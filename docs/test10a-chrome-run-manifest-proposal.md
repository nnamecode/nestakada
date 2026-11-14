# TEST-10A — exact current-Chrome run manifest proposal

Статус D-1068 amendment, 2026-11-14. Три canonical registry ранее прошли independent review: `APPROVED`, P1=0, P2=0, P3=0. Exact action arrays сохраняются без нового продуктового поведения. Документ не является run manifest, не создаёт fixture/stand/evidence и не разрешает Docker, Foundation, browser execution, direct HTTP или acceptance promotion. D-1055–1059 partial writer retired по no-bloat D-1068; approved D-1054 policy сохранена. Все 40 bindings и 6 observers пока `unbound`, `registryReady=false`; `TEST10-Q003` закрыт до отдельного simplified evidence protocol review и фактических bindings/observers, затем отдельного owner gate.

## D-1069 read-only route-binding audit

Фактический `app/estakada/urls.py` включает editor под `/manage/pages/<uuid>/edit/`, versions под `/manage/pages/<uuid>/versions/`, accounts под `/manage/` и public catch-all. Fixture `app/page_editor/test10_fixture.py` создаёт published primary route `/test10/assigned/` и нужные owner/edit/other sessions/history.

Из40 binding rows ровно26 механически имеют существующую route+method пару без добавления endpoint:

- public GET3: assigned page, `/header/`, `/footer/`;
- accounts7: login3, employee password2, grants2;
- editor GET6: active/expired/other/revoked access and unsaved-tab entry;
- editor `save/` POST5;
- versions history GET5.

Остальные14 пока conceptual и не исполняются честно в записанном виде:

- seven UI rows задают `POST /manage/pages/{page}/edit/`, но editor root допускает GET; нормализация/валидация/сохранение используют existing `check/` или `save/`, а сохранение ввода вкладки является browser observation;
- seven rows задают generic `/manage/pages/{page}/versions/{version}/`; GET там только read, POST route отсутствует. Сравнение использует `compare/`, восстановление — reviewed sequence через `restore/prepare/` и `restore/apply/` (historical `restore/stage/` не подменяется догадкой), cancel не создаёт отдельный HTTP mutation.

Это mechanical audit, не readiness и не amendment: existing JSON/hashes/status не меняются. Independent review D-1070 установил, что registry write нельзя ограничить14 rows.

### D-1070 semantic corrections

До любого registry amendment нужна exact all40 table. Для каждого ID она фиксирует existing endpoint/UI-only step, method, content type, exact allowed fields/body, dynamic receipt/CSRF/session prerequisites, pre-state, post-state, oracle и scenario-isolation transition.

Три открытых класса:

1. Twelve nominal route candidates имеют несовместимый request contract: account payloads используют registry references/extra fields, которые strict form parser не принимает как literal endpoint body; five editor-save rows объявлены form-urlencoded, хотя editor POST admission и save contract JSON. Registry reference material нельзя отправлять буквально.
2. One-Prepare order отзывает единственный S-EDIT grant в AC-015 до history/restore scenarios. Regrant/reset отсутствует и generation изменён. До reviewed isolation transition поздние employee rows остаются unreachable/BLOCKED; второй Prepare/run не разрешён.
3. D-1071 снял AC-022 product/acceptance mismatch явным owner decision: current oracle — compare read-only → explicit confirmation → one atomic direct restore/new current revision. Отдельные editor stage и second save исключены; `restore/stage/` не возвращается. Oracle `OBS-022-PROTECTED-UNCHANGED` должен быть role-aware: common unchanged URL/tree position/publication/grants/Stable/shared; employee-only unchanged owner-protected H1/SEO/block layout/media; owner branch проверяет их восстановление из compatible snapshot по D-261. Registry rows всё ещё не меняются до all40 semantic table и independent review.

All40 bindings и six observers остаются `unbound`, `registryReady=false`. Следующий документарный этап после repeat review — all40 semantic table proposal; product code и JSON registry пока не меняются.

## Closed identity

Будущий write-once JSON имеет schema `test10a-chrome-run-v1` и создаётся только после всех preflight checks. Обязательные поля:

- `runId`: ровно 32 lowercase hex; совпадает с exact fixture receipt и evidence root `work/test10/runs/<runId>`;
- `createdAt`: UTC ISO-8601; `os`: exact Windows build;
- `sourceSha256`, `appImage`, `fixtureHash`: exact independently reviewed frozen source/image/fixture receipt;
- `browser`: только `family=chrome`, exact canonical binary path, file SHA-256 и фактический `major.fullVersion`; inventory/ярлык/registry сами по себе не являются identity;
- `acceptanceCaseIds`: ровно `AC-013`, `AC-014`, `AC-015`, `AC-021`, `AC-022`, `AC-023`, `AC-DTL-004`, `AC-DTL-006`, `AC-DTL-018` в этом утверждённом fixture-порядке;
- `runScenarioIds`: ровно соответствующие `T10C-AC013`, `T10C-AC014`, `T10C-AC015`, `T10C-AC021`, `T10C-AC022`, `T10C-AC023`, `T10C-DTL004`, `T10C-DTL006`, `T10C-DTL018`; это отдельные 1:1 execution labels, не замена AC IDs;
- `bindingsSha256`, `payloadRegistrySha256`, `observerRegistrySha256`, `evidencePolicySha256`, `cleanupReceipt`: только exact independently reviewed значения;
- `previous1` и `previous2`: `not_run`; Edge и остальные браузеры отсутствуют, а не наследуют результат.

CLI не принимает произвольные paths, browser flags, URLs, payloads, cases, observers или output roots. Missing/changed field до первого действия означает `BLOCKED/no run`.

## Exact case order

| Order | Case ID | Acceptance | Fixed actions |
|---:|---|---|---|
| 1 | `T10C-AC013` | `AC-013` | `UI-013-SAFE`, `HTTP-013-ACTIVE`, `HTTP-013-HEADER`, `HTTP-013-FOOTER`, `UI-013-POSITIVE` |
| 2 | `T10C-AC014` | `AC-014` | `UI-014-OWNER-RESET`, `HTTP-014-OLD-SESSIONS`, `HTTP-014-SELF-CHANGE`, `HTTP-014-SELF-RECOVERY`, `UI-014-NEW-LOGIN`, `OBS-014-SECRET-SINKS` |
| 3 | `T10C-AC015` | `AC-015` | `UI-015-UNSAVED`, `HTTP-015-IDLE1801`, `HTTP-015-ABS43201`, `UI-015-RELOGIN`, `HTTP-015-OTHER-DENY`, `UI-015-EXPLICIT-SAVE`, `UI-015-OWNER-REVOKE`, `HTTP-015-REVOKED-DENY` |
| 4 | `T10C-AC021` | `AC-021` | `UI-021-HISTORY`, `UI-021-OWNER-CONTROL`, `HTTP-021-VISITOR`, `HTTP-021-S-OTHER`, `OBS-021-CACHE` |
| 5 | `T10C-AC022` | `AC-022` | `UI-022-COMPARE`, `UI-022-CANCEL`, `UI-022-STAGE`, `UI-022-SAVE`, `UI-022-OWNER-CONTROL`, `OBS-022-PROTECTED-UNCHANGED` |
| 6 | `T10C-AC023` | `AC-023` | `UI-023-INCOMPATIBLE`, `UI-023-COMPARE-BEFORE-REVOKE`, `UI-023-OWNER-REVOKE`, `UI-023-REVOKED`, `UI-023-COMPATIBLE-CONTROL` |
| 7 | `T10C-DTL004` | `AC-DTL-004` | `UI-104-NORMALISE`, fixed payloads `P104-1M`, `P104-TEXT200K`, `P104-NODES20K`, `P104-DEPTH32`, `P104-ACTIVE-SET`, `UI-104-POSITIVE` |
| 8 | `T10C-DTL006` | `AC-DTL-006` | `UI-106-SAFE-LINKS`, fixed payload set `P106-UNSAFE-SET`, `HTTP-106-PROTECTED-SET`, `OBS-106-CLIENT-NETWORK`, `OBS-106-SERVER-EGRESS`, `UI-106-POSITIVE` |
| 9 | `T10C-DTL018` | `AC-DTL-018` | fresh branches `UI-118-VALIDATION`, `UI-118-EXPIRY`, `UI-118-CONFLICT`, `OBS-118-BROWSER-STORAGE` |

## Mandatory closed binding registries before Q003

Текущие IDs — scope labels, не готовые bindings. До предложения Q003 обязательны три отдельные tracked canonical JSON registry и independent review с P1/P2/P3=0:

1. `bindings`: для каждого action фиксирует `kind=ui|http`, actor/context, literal route template, HTTP method, payload ID или UI steps, expected status/class, exact mutation/non-mutation fields и positive control. Допустимые route templates только `/manage/pages/{page}/edit/`, `/manage/pages/{page}/edit/check/`, `/manage/pages/{page}/edit/save/`, `/manage/pages/{page}/versions/…`, `/manage/employees/{employee}/password/`, `/manage/employees/{employee}/grants/`, `/manage/login/`, `/manage/shared/{header|footer}/…`, fixture public route `/test10/assigned/` и exact guessed Header/Footer public paths из registry. UUID/int placeholders разрешаются только из fixture `identifiers`, не из CLI. В AC-015 same-user positive explicit save выполняется до owner revoke; revoked denial — следующая отдельная negative branch. Для AC-023 revoke выполняется после отдельного successful compare и до rejected restore; compatible control начинается на fresh branch, а не после revoke.
2. `payloadRegistry`: canonical UTF-8 JSON/body bytes и SHA-256 для каждого `P104-*`, `P106-*` и direct-request body. Свободный HTML/URL/body запрещён.
3. `observerRegistry`: source file/function identity, input binding, exact sink set/origin set и output schema для каждого `OBS-*`.

Для `HTTP-013-HEADER`/`FOOTER` registry обязан требовать non-standalone response/no component content, а `UI-013-SAFE` — присутствие реального shared header/footer на обычной published page. Для `HTTP-015-OTHER-DENY`/`REVOKED-DENY` закрытые данные отсутствуют. `OBS-022-PROTECTED-UNCHANGED` имеет role-aware oracle: для обеих ролей до/после неизменны URL, parent, page position, publication, grants, Stable и shared Header/Footer; для employee дополнительно неизменны current owner-only H1/SEO/block layout/protected media, а owner branch доказывает их восстановление из compatible snapshot по D-261. Любой отсутствующий/непроверенный binding/hash не просто блокирует case: Q003 не предлагается вообще.

Direct HTTP не является regression runner: будущий manifest включает только registry actions соответствующего case; произвольные method/path/body запрещены.

## Derived observers and safe evidence

- `OBS-014-SECRET-SINKS` возвращает exact `sinkSetSha256`, complete boolean и per-sink `canaryPresent`; incomplete/mismatched set → `BLOCKED`, любое `true` → `FAIL`, complete+all false → oracle pass. Значение canary не возвращается.
- `OBS-106-SERVER-EGRESS` возвращает actual boolean `serverFetchObserved`: `true→FAIL`, `false→oracle pass`, unavailable/incomplete/source drift → `BLOCKED`.
- `OBS-021-CACHE` возвращает только `status`, `class`, `cachePrivate`, `noStore`: expected denial + both true → oracle pass; unexpected access/false flag → `FAIL`; observer gap → `BLOCKED`. Raw headers/cookies/body запрещены.
- `OBS-106-CLIENT-NETWORK` сохраняет только method, path без query/fragment, status/class и destination origin: любой external request → `FAIL`, complete capture+zero external → oracle pass, incomplete capture → `BLOCKED`. External body, query, fragment, cookies, raw headers и tokens запрещены.
- `OBS-118-BROWSER-STORAGE` допускает только booleans presence по URL/localStorage/sessionStorage: любое presence → `FAIL`, complete all-false → oracle pass, missing scope → `BLOCKED`. IndexedDB/CacheStorage не заявляются без отдельного reviewed observer.

Evidence files содержат только manifest, safe fixture summary, case results `PASS|FAIL|BLOCKED`, перечисленные derived observer outputs, screenshots только уже safe view либо pre-persistence crop/mask и cleanup receipt. Raw screenshot с secret/PII не может быть записан даже временно; post-capture redaction не допускается. HAR, console dump, clipboard notes, secret values, реальные контакты/ПД и response bodies запрещены.

## Write-once and physical durability gate

До Q003 требуется отдельный simplified evidence protocol review. Если он использует реализацию записи, она должна:

1. создаёт manifest через create-new в already verified ordinary/no-reparse evidence root;
2. записывает canonical UTF-8 JSON, выполняет file `Flush(true)` и подтверждает повторным SHA-256 read;
3. не перезаписывает manifest; phase/result files используют новые exact filenames;
4. сохраняет raw safe evidence, manifest и hash summary до independent reconciliation;
5. не удаляет evidence root при fixture teardown.

Отсутствие доказанного `Flush(true)`/readback или stale `.new` означает `BLOCKED`; это не разрешает новый daemon, database, scheduler или logging subsystem.

Cleanup receipt заранее содержит exact stand/container/network/database/private-file identities. Перед каждым delete повторяются identity, containment и full ancestor no-reparse checks. Missing/drift/ambiguity → `BLOCKED/no delete`. Удаляется только ресурс exact run; broad prefix cleanup запрещён. Evidence root исключён из cleanup и не удаляется, пока это единственная safe evidence copy или independent reconciliation не завершена.

## Execution gates and stop rule

До будущего run обязательны: approved simplified evidence protocol, read-only browser binary identity, active isolated foundation identity, fixture Prepare receipt, exact manifest hash и running-foreign-containers0. Любой drift → `BLOCKED/no first action`.

Первая ошибка останавливает current case/package. Повтор возможен только после recorded cause и changed condition. Вторая equivalent error приостанавливает TEST-10A владельцу; третьей попытки нет.

`TEST10-Q003=1` не может быть предложен до approval simplified evidence protocol и binding всех registry rows/observers. Если позже он будет отдельно принят, он разрешит только один exact-run lifecycle: один fixture Prepare, один manifest-bound current-Chrome stand/run и exact Teardown с retained evidence. Он не разрешает второй Prepare/run, Edge, previous versions, другие cases, arbitrary HTTP, Playwright, установку браузеров, live/VPS, acceptance promotion или автоматическую публикацию.
