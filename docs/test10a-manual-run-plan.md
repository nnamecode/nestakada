# TEST-10 T10-A — bounded manual run plan

Статус D-1039, 2026-11-14. План прошёл повторное independent review: `APPROVED`, P1=0, P2=0, P3=0. Следующий gate `TEST10-Q002=1` может разрешить только fixed fixture design/implementation и offline tests; browser/Foundation execution, acceptance promotion и product changes не разрешены. `TEST10-Q003` закрыт.

## Scope exact9

T10-A содержит только девять AC из approved D-1036 feasibility:

| Package | AC | Цель |
|---|---|---|
| T10-A1 editor safety | `AC-013`, `AC-DTL-004`, `AC-DTL-006` | разрешённое форматирование и ссылки сохраняются; active/template/unsafe URL не исполняются и не публикуются |
| T10-A2 auth/session/tab memory | `AC-014`, `AC-015`, `AC-DTL-018` | reset/session boundaries/re-login/conflict сохраняют server authority и допустимый ввод только в открытой вкладке |
| T10-A3 history/compare/rights | `AC-021`, `AC-022`, `AC-023` | история приватна, compare не мутирует, restore требует explicit save, incompatible/revoked state fail-closed |

T10-B forms, T10-C gallery, T10-D full8×3 matrix и T10-E fallback не входят и не наследуют будущие approvals T10-A.

## Mandatory stop-gates до запуска

`T10A-001`: exact current browser major/date не назначать по inventory. В день будущего run отдельно подтвердить Chrome/Edge binary identity и major; иначе соответствующий browser run `BLOCKED`.

`T10A-002`: один isolated TEST-10 stand с pinned reviewed images, loopback-only ingress, synthetic data и running-containers0 до start. Production/VPS/old site запрещены.

`T10A-003`: retained `estakada_foundation`/unit DB не является manual fixture. До execution нужен independently reviewed fixed one-shot preparation/teardown contract с fresh per-run DB или равноценной доказанной isolation; arbitrary SQL/path/model/callable запрещены.

`T10A-004`: preparation переиспользует канонические synthetic profiles `FX-IDENTITY`, `FX-CONTENT`, `assigned-page-with-owner-draft`, `controlled-session-boundary`, `page-history-restore`; он не кодирует expected result и не создаёт новый product endpoint/model/permission.

`T10A-005`: synthetic secrets генерируются на run, передаются только через private file/context и не попадают в Git, screenshots, HAR, console, report или clipboard notes. Для проверки утечки используется отдельный непечатаемый canary marker: reviewed observer возвращает только booleans presence/absence по разрешённым synthetic audit/log/report sinks, не значение/строку. Нет observer или неполный sink set → affected branch `BLOCKED`. Реальные ПД/контакты запрещены.

`T10A-006`: idle/absolute boundaries используют только controlled server/test time age `1801`/`43201`; Windows clock, Docker Desktop clock и production time не меняются. Если existing product/test boundary не даёт честно управлять временем, affected scenarios `BLOCKED`, новый global clock subsystem не добавляется.

`T10A-007`: fixture implementation требует отдельного owner gate `TEST10-Q002=1` после independent plan review. Сам browser execution затем потребует отдельного manifest/review и `TEST10-Q003=1`.

## Exact run manifest до каждого browser run

`T10A-008`: manifest write-once фиксирует run UUID, reviewed source/code hashes, exact browser family/version/OS, stand identity, fixture profile hash, nine case IDs, order, evidence root и cleanup receipt. CLI не принимает произвольные paths/cases/browser flags.

`T10A-009`: evidence root только ignored `work/test10/runs/<32-lowercase-hex-uuid>`; каждый ancestor ordinary/no-reparse. Screenshots допускаются только без secret/PII; network evidence хранит method/path/status/class и destination origin, но не bodies/cookies/raw headers/tokens. Для cache oracle допускаются только derived booleans `cachePrivate` и `noStore`, вычисленные reviewed observer из фактического ответа; raw header/cookie не сохраняется.

`T10A-010`: Chrome и Edge — два отдельных fresh runs с одинаковым reviewed manifest profile. Результат одного не переносится на другой. Previous-1/2 не устанавливаются и остаются `not_run`.

`T10A-011`: перед первым действием оператор записывает fixture IDs/hashes из закрытого safe summary, подтверждает owner/S-EDIT/S-OTHER/visitor contexts и positive control. Fixture echo/expected flags не считаются результатом.

## T10-A1 — editor safety

`T10A-012`: `AT-013`: через настоящий UI сохранить разрешённые heading/table/link/style, открыть public result и history, затем compare/restore. Отдельно через reviewed direct HTTP binding отправить script/event/template payload; требуется полный отказ без mutation, затем fresh safe positive control. Existing Header/Footer history остаётся component-only: exact guessed/direct public routes для обоих не дают самостоятельную Page/публичное содержимое, при этом реальный общий header/footer продолжает присутствовать в обычной published Page.

`T10A-013`: `AT-104`: UI показывает нормализацию допустимого content до save; exact profile boundaries 1MiB/200000 text/20000 nodes/depth32 и active HTML/CSS/template variants подаются только reviewed fixed payload IDs, не ручной arbitrary HTML. Unsupported payload/binding → `BLOCKED`, не skip/pass.

`T10A-014`: `AT-106`: local/http/https links проверяются в saved/history/public views; javascript/data/file/entity/mixed-case/control/double-encoding и protected menu/button variants идут через fixed payload IDs. External example literals не открываются; browser network panel должен показать zero client requests к external origins. Отдельный existing reviewed server-egress observer/closed synthetic sink обязан вернуть только `serverFetchObserved=false` для exact canary destination; observer не создаёт endpoint/external service и не возвращает URL/body. Если такого existing binding нет, server-fetch ветвь `BLOCKED` и AC не повышается.

## T10-A2 — auth/session/tab memory

`T10A-015`: `AT-014`: owner штатно создаёт/reset synthetic S-EDIT; две реальные browser contexts теряют старые sessions. Employee self-change/recovery direct requests denied; новый owner-issued secret даёт positive login. Secret value нигде не записывается; bounded observer из T10A-005 должен вернуть canary absent во всех разрешённых synthetic audit/log/report sinks, иначе `FAIL`, а отсутствие полного observer — `BLOCKED`.

`T10A-016`: `AT-015`: в открытой S-EDIT вкладке ввести canary без save, пересечь controlled idle и absolute boundaries раздельными fresh runs; closed reads denied. Same-user re-login не autosave и требует explicit save/current rights/base; other-user/revoked-right paths не получают закрытые данные.

`T10A-017`: `AT-118`: validation error, session expiry и conflict выполняются отдельными fresh scenarios. Допустимый ввод остаётся только в текущем field; manual DevTools inspection подтверждает canary absent в URL/localStorage/sessionStorage. IndexedDB/CacheStorage/network claims без отдельного наблюдения не повышаются автоматически.

## T10-A3 — history/compare/rights

`T10A-018`: `AT-021`: S-EDIT видит ordinary/manual/Stable labels только назначенной page; owner positive control читает exact history/preview canary. Visitor/S-OTHER direct same ID/path denied; reviewed response observer сохраняет только status/class и derived `cachePrivate=true`, `noStore=true`. Отсутствие кнопки не заменяет direct denial.

`T10A-019`: `AT-022`: с unsaved canary выбрать historical version, inspect comparison/substitution warning и cancel — site/history unchanged. Explicit save создаёт новую version, но URL/parent/published/grants/Stable и employee-protected fields unchanged; owner branch проверяется отдельно.

`T10A-020`: `AT-023`: fixed incompatible-schema snapshot и grant revoked after compare дают whole-operation denial with reasons, zero partial mutation и preserved current tab input. Allowed text remains manually readable/copyable within current rights; positive compatible/current-right control обязателен.

## Results, stop and cleanup

`T10A-021`: scenario result только `PASS|FAIL|BLOCKED`; browser crash, missing binding, unknown fixture state, evidence gap или cleanup ambiguity — `BLOCKED`.

`T10A-022`: первая ошибка останавливает current scenario/package и сохраняет safe evidence. Повтор — только после recorded cause и changed condition. Вторая equivalent error ставит T10-A «Приостановлено владельцу»; третьей попытки нет.

`T10A-023`: cleanup выполняется только exact stand/fixture resources из receipt после identity/reparse check. Raw safe evidence, write-once manifest и hash summary сначала fsync сохраняются в ignored evidence root и остаются до independent reconciliation; cleanup receipt явно исключает этот root. Нельзя удалить stand/volume, если внутри него находится единственная evidence copy. Broad delete/prefix cleanup запрещены; ambiguity/drift/missing evidence сохраняет resources и возвращает `BLOCKED/no delete`.

`T10A-024`: manual PASS не повышает AC автоматически и не закрывает full8×3 matrix, production/persistent import, all storage APIs или branches вне exact case. После каждого browser/package нужен independent per-AC reconciliation.

## Порядок продолжения

1. Independent review этого plan; никаких файлов fixture/browser execution до `APPROVED`.
2. После approval отдельный `TEST10-Q002=1` может разрешить только проектирование/реализацию fixed one-shot isolated fixture preparation и offline tests.
3. Fixture code review и read-only feasibility evidence; затем отдельный exact run manifest/review.
4. Только `TEST10-Q003=1` сможет разрешить один exact reviewed manifest: manual current-Chrome UI и только перечисленные в нём fixed direct-HTTP actions/derived observers T10-A. Он не разрешает произвольный HTTP regression/test runner. Edge и любые следующие runs потребуют отдельных явных gates.

