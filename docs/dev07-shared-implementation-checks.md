# DEV07-SH1 — контракт первого локального инкремента общих блоков

2026-11-01. DEV-07 около95%, этап8 около20%. Предварительный технический контракт/сценарии до product кода; задача поручена владельцем, конкретный diff проходит независимое ревью. Основания: D-066/D-111/D-261/D-294/D-301, dev07-editor-contract.md §6–7, dev07-shared-preparation.md, dev07-shared-probe-amendment.md; REQ-013/017/018/022/028/029/050, AC-013/017/022/028/029/050, AC-DTL-017, AT-117/405. Product код этим документом не объявляется готовым.

## Исполняемый результат и честная граница квоты

Первый инкремент: отдельный shared_content со storage invariants, owner-only read/check/history/compare и atomic draft/apply/restore command pipelines. Header/Footer не являются Page и не получают Page10, новые Stable-команды, публичный URL/SEO/публикационный флаг. Только явное Apply меняет выбранный current; draft/restore prepare не публикуют. Все endpoints private/no-store. Публичная композиция/ETag DEV-08 и подключение основного меню DEV-29 остаются отдельными зависимостями.

**Вычисленный безопасный резерв пока не утверждён.** Три экспериментальных PG измерения не доказывают универсальный multiplier по UTF8. Product quota admission должен fail closed при неизвестном/unvetted reservation profile или measurement inventory. Нельзя включить profile только потому, что конечный тест прошёл. Поэтому первый срез может честно предоставить работающие read/check и доказанный безопасный отказ записи; accepted draft/apply/restore production behaviour не считается принятым до отдельного проверенного reservation profile. Тестовый bypass/искусственный profile не выдаётся за product PASS. Если владелец ожидает уже принимающий записи редактор, этот оставшийся gate явно указывается в результате, а не скрывается за отметкой «готово».

## SHI07-DATA — отдельные модели и доменная граница

Имена — технический проект по принятому §6, не новая архитектура сервера:

| Модель | Инвариант |
|---|---|
| SharedBlock | UUID, unique kind=header/footer, current_revision nullable до первоначального наполнения, monotonic generation; никаких Page/tree/URL/SEO полей |
| SharedRevision | UUID, block, unique positive sequence per block, component_schema_version, canonical HTML/payload hash, server author/time, source_revision_id nullable; immutable |
| SharedDraft | UUID, unique block, own monotonic revision, current base FK, canonical HTML/hash, author/time; одно действующее состояние на блок |
| SharedRestoreStage | UUID, block, actor/generation, source/base identities, policy/schema stamps, state held/consumed/released/invalidated и terminal provenance |
| SharedBasePin | revision FK, holder kind/UUID unique; current/draft/held stage bases не исчезают под операцией |
| SharedReceipt | operation UUID, action, actor/generation, block/source/base/result IDs, canonical request fingerprint, resultCode; immutable, без текста/секретов |
| SharedIdentityReservation | permanent UUID/kind reservation, не удаляется с временным draft/stage; все IDs назначаются сервером |
| SharedBudget | singleton cached count/bytes/accounting version; только cache, не замена actual rows/relations |

Модели защищают обычные update/delete/bulk_update/bulk_create так же, как существующий page_versions service boundary; internal validated commands используют явно отделённый raw queryset внутри короткой transaction. Нельзя импортировать PageRevision как базовый SharedRevision или сохранять фиктивную Page ради reuse.

Порядок mutations: content.models.lock_content → accounts.services.lock_auth → fresh active owner profile/generation → row locks выбранного block/баз → operation replay check → fresh compatibility/Asset states → budget admission → writes/refs/receipt/audit → post-write measured quota assertion → commit. Тяжёлое body/HTML чтение и child-нормализация до этой transaction; свежесть повторно проверяется после неё. Invalid/unknown result не создаёт успешной квитанции. Exact replay возвращает тот же result, другой fingerprint под тем же operation UUID даёт409. Существующая успешная квитанция проверяется до нового quota reservation, но после свежей авторизации.

Identity создаётся под content domain; SharedDraft consumer kind=draft не должен присвоить identity существующего Page draft. Перед выдачей нового consumer UUID проверить существующие shared/Page identity reservations и AssetUsage, не полагаться на клиентский UUID или только на низкую вероятность случайной коллизии. Server-only UUID не означает разрешение переиспользовать исторический ID.

## SHI07-HTML — закрытая схема и Asset-маркер

Структурная палитра/позиции — таблица SH07-SCHEMA-001 в dev07-shared-preparation.md, источник docs/design/public-light-v4-template.html. `header-v1` и `footer-v1` — закрытые literal schema IDs. Sanitizer не принимает имя renderer/module/template из DTO. Raw UTF8≤1МиБ,20k nodes/depth32; один выбранный блок на операцию. Нет arbitrary style/class/id/data/event attributes, script/iframe/raw SVG, CSS URL, шаблонных конструкций или серверной загрузки external links.

Конкретный internal Asset-маркер: только `img[data-es-shared-asset="<canonical-lowercase-UUID>"]` плюс plain alt и проверенные width/height. Клиент не передаёт src/srcset/original path/вариант/consumer ID. Child проверяет syntax и закрытую структуру; родитель после child проверяет настоящий READY Asset и доступные public WebP variants/файлы, заново выводит bindings; финальная transaction повторяет READY/usage/identity проверки. Хранимый canonical HTML содержит этот маркер, публичный доверенный renderer выдаёт src только из server-selected variant. В history/compare данные экранируются; имитация raw img как готового публичного preview запрещена.

Маркер — точное исключение из общего запрета произвольных data-атрибутов, не открытие всей data-* палитры. img Asset markers могут стоять только в brand/social image positions принятой схемы. Сырой SVG макета не принимается как пользовательский SVG; если trusted social-icon asset ещё не соответствует принятой media модели, нельзя молча преобразовать это в разрешение загрузки SVG. Реальная интеграция таких icon assets остаётся отдельным явно отмеченным gate; текстовые owner проверки можно исполнять без ложного заявления о полной иконографии.

Буквальные tel/адрес/время/social HTTPS ссылки входят в snapshot. URL разбирается после entity decoding/Unicode policy; отклоняются script/data/file/protocol-relative/пробельные обходы. Внешняя ссылка не вызывает серверный fetch. Restore старого телефона возвращает старое буквальное значение после сравнения; отдельный реестр контактов не создаётся.

Shared нормализация идёт в существующем короткоживущем Python child со статическим закрытым dispatcher action, без новой dependency/процесса-сервиса/порта. Нельзя передать в dispatcher arbitrary import/function/command. Прежние CPU10s/wall20s/AS384MiB и app768MiB/1CPU сохраняются. Owner admission/CSRF/metadata до большого body; Shared reader≤4МиБ, прежний11МиБ Nginx;64МиБ Page special locations сюда не добавляются. Один heavy slot и bounded body120s используются существующим механизмом. Конкретный child dispatcher diff проходит ревью вместе с проверкой Page regression.

## SHI07-NAV — конкретная доверенная область

В `header-v1` единственный доверенный nav marker: `<nav id="es-nav" aria-label="Основное меню"></nav>`; его дочерние editor links/JS отсутствуют. Это literal закрытая node shape, не язык шаблонов. Доверенный menu button сохраняется как фиксированная структура принятого template с type/aria-controls/начальным aria-expanded, не редактируемое поведение. Renderer распознаёт схему и точный node, получает current navigation через типизированный server argument; никакого eval/template rendering сохранённого HTML.

Нельзя автоматически превратить static template links в новый реестр ручных меню. Current navigation source обязан быть действующим DEV-29/DEV-08 resolver по D-032; пока он не подключён, shared runtime не изображает готовую публичную навигацию и не подставляет выдуманные страницы. History показывает marker как данные и подпись «Меню строится по текущей структуре сайта», не выдаёт current menu за исторический snapshot. Первые private read/check могут работать до публичного resolver.

## SHI07-QUOTA — actual relation inventory и admission

Общий cap268435456B/10000 immutable revisions, warning actualBytes≥201326592B. Bytes включают все shared root tables+their indexes/TOAST/forks через pg_total_relation_size каждого root ровно один раз. Доверенный inventory связан с установленной migration/schema/model table list, проверяет owner/namespace/OID/relkind; недостающая/заменённая/неподдерживаемая relation — отказ измерения. Receipt/identity/draft/pin/budget не выпадают из inventory. Attributable AssetUsage metadata и temporary growth должны иметь отдельно проверенный reservation accounting; их нельзя объявить бесплатными потому, что media_library таблица общая. WAL/whole PostgreSQL disk имеют отдельную эксплуатационную границу и не называются охваченными этим cap.

Count читается настоящим COUNT обеих SharedRevision, а не ожидаемым cached budget. Admission принимает только серверное измерение и trusted reservation profile version, не bytes/count из JSON. Unknown profile, отрицательные/нецелые/устаревшие параметры, отсутствие lock scope/inventory → SHARED_BUDGET_PROFILE_UNAVAILABLE/MEASUREMENT_UNAVAILABLE503 без mutation. Count10000 с increment1 → SHARED_HISTORY_COUNT_FULL409; measured bytes + отдельно учитываемые bytes + reservation > cap → SHARED_HISTORY_BYTES_FULL409. Warning при достаточном остатке не является отказом. Диагностическое чтение при full count остаётся доступно владельцу.

Счётчики сверяются до mutation и после actual write внутри той же transaction, общий content lock сериализует резерв. Post-write overflow откатывает logical writes, но физический рост после rollback остаётся в следующем actual measurement. Один post-check не гарантирует hard physical cap: профиль нельзя включить без обоснованного pre-reservation. Пока такого профиля нет, failure-closed default не снимается через env флаг/debug/test query.

## SHI07-HTTP и история

Owner-only GET edit/history/versions/<uuid>/compare/result; POST check/draft/apply/restore prepare/cancel. Kind только header/footer; unknown path404. Первое представление использует экранированный textarea HTML и обычные кнопки Check/«Сохранить черновик»/«Применить к сайту». Unsaved source остаётся только в RAM открытой вкладки; local/session storage/IndexedDB/URL/request logs не получают payload. При503 input не очищается, автоповтора нет. Нельзя описать заблокированный quota default как успешное применение.

Proof namespace shared-editor-check-v1, binding actor/generation/block UUID/kind/base/draftBasis/stageId/schema/policy/canonical input hash/Asset stamp; не совместим с Page checkReceipt. Check proof только после successful child и fresh context. Draft/Apply повторяют fresh session/owner/generation/base, проверку proof и canonical payload/refs; client sourceMode current|owner-draft|restore-stage закрыт enum. Restore prepare создаёт отдельное held основание после явного подтверждения замены ввода; original revision/current/other block не меняются. Apply stage требует отдельного explicit Apply, создаёт новый snapshot и terminal consume; stale current конфликтует без merge.

## Сценарии до кода

| ID | Реальное действие и обязательный oracle |
|---|---|
| SHI07-001 | Модельные DB constraints: только два kind, crossblock current/base запрещены, unique block sequence/draft, direct immutable update/delete rejected; UUID nonreuse после terminal |
| SHI07-002 | Owner real login/read/check positive; employee с назначенной Page/anonymous direct endpoints denied до body/HTML; fresh grant не открывает shared |
| SHI07-003 | Принятая структура обоих блоков с независимыми text canaries проходит actual child, output proof/input hash; text/field/node/depth/raw byte limits; JS/Django/attr/class/structure/URL bypass rejected |
| SHI07-004 | Asset marker validsyntax+реальныйREADYpublicvariant positive; foreign/path/src/rawSVG/unready/missingbytes/substitutedID negative; content не меняется при refused input |
| SHI07-005 | Unknown/unvetted quota profile: реальный draft/apply/restore pipeline503 без current/draft/history/refs/receipt success mutation; ownerread/check продолжают работать |
| SHI07-006 | Actual shared relation inventory metadata/forks/COUNT; alltables accounted once; missing/foreign relation denies; warning/count/byte arithmetic отдельно от product mutation PASS |
| SHI07-007 | После будущего vetted profile: actual ownerdraft только private; apply одна новаяrevision выбранного блока; exactreplay тотжеresult, modifiedop/base409; postwritefault rollback/no partialrefs; не объявлять executed сейчас |
| SHI07-008 | Старый compatible snapshot compare с буквальнымoldphone; prepare безpublish; после vetted profile отдельныйApply; unknownschema safeescapeddata/whole restore refusal; Page restore не меняетshared |
| SHI07-009 | Header navmarker фиксирован и непустыеeditorchildren rejected; no JS/templateeval; currentnav typedresolver толькопослеDEV29/08. Privatehistory honestcurrentmenulabel |
| SHI07-010 | HTTPCSRF/no-store/earlyauth, childreap/slotrecovery/retainedinput503; Page tests regression при sharedchilddispatcher |

SH-REV-001 закрывается **на уровне контракта binding**, не молчаливой очисткой: прежний synthetic `<header><p>CANARY</p></header>` заменяется целым schema-valid header; независимый CANARY помещается в видимый текст `a.es-header-address > span` или `a.es-header-phone > span`. Binding обязуется прочитать настоящий resulting canonical DOM/public HTTP и проверить canary там, а не взять expected из POST. Footer CANARY — в `div.es-footer-left > p`. Сам семантический oracle сохранён, general header<p> по-прежнему rejected; executed e2e закрытие только после подключения реальной публичной композиции.

## Условия завершения ограниченного среза

Результат отчёта разделяет: модель/normalizer/read-check работающие пути; безопасно отклоняемые mutations без vetted profile; ещё не принятые Apply/publiccomposition/иконография/полная quota corpus. Независимый рецензент проверяет конкретный код другого исполнителя, hashes/tests/неизменность прежних caps. Не закрывать полный DEV-07 по одному этому инкременту. До кода — независимое техническое ревью настоящего документа; затем ограниченный список файлов задаёт координатор.
