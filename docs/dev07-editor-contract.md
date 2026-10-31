# DEV-07 — технический контракт редактора и Header/Footer

2026-10-31. **Предложение к техническому ревью, не код и не изменение настроек.** D-329 разрешает DEV-07, D-330 — подготовку и проверку точного пакета. По D-331 владелец принял ограниченный транспорт/child profile [dev07-transport-amendment.md](dev07-transport-amendment.md):64/5/4MiB,1slot,body120,childAS384/CPU10/wall20. Фактические handlers и их испытания остаются pending. CSP не ослабляется. Приоритет D-301/TECH-01, PR-02/08, D-258/294 и UI-S003–013/принятых состояний редактора сохраняется.

## 1. Область и точки HTTP

Предлагаемые закрытые маршруты, все только same-origin/private,no-store; write только CSRF-protected POST. UUID пути — серверная Page, не её опубликованный URL. Ни один маршрут не принимает произвольный Snapshot, template name, filename, renderer type или команду.

| Endpoint | Метод/назначение | Права/тело |
|---|---|---|
| `/manage/pages/<uuid>/edit/` | GET редактора/current и доступных полей | Owner либо назначенный employee; owner draft не включается в employee DTO |
| `/manage/pages/<uuid>/edit/check/` | POST безопасной нормализации/проверки | JSON закрытого PageInput ниже; без публикации/версии/сохранённого draft |
| `/manage/pages/<uuid>/edit/save/` | POST явного применения | PageInput + operationId/checkReceipt; создаёт одну automatic через DEV05 |
| `/manage/pages/<uuid>/edit/draft/` | POST отдельного owner draft | Owner; PageInput + operationId/checkReceipt + draft basis |

**Ровно три JSON POST выше — точный предложенный allowlist большого тела в принятом D-331 профиле**. Не префикс `/manage`, не весь `/edit`, не regex произвольного хвоста. Согласование профиля не заменяет техническое ревью wiring и фактическое доказательство раннего auth/CSRF/framing/ресурсных границ. До подключения проверенного handler прежние настройки сохраняются. Shared block≤1MiB snapshot использует собственные bounded DTO/формы и не получает64MiB автоматически. Существующие media/login/versions формы не меняют своих лимитов.

Предлагаемые дополнительные малые закрытые действия: GET `/manage/pages/<uuid>/edit/result/<operationUuid>/` для выяснения исхода без повторного commit; GET `/manage/pages/<uuid>/edit/stage/<stageUuid>/` для разрешённой подстановки; POST `/manage/pages/<uuid>/edit/draft/cancel/` для явной отмены конкретного owner draft. Их DTO только ID/generation/basis, без большого HTML; большой allowlist к ним не применяется. Перед кодом URL wiring сверяется root, системные public маршруты не меняются.

## 2. Закрытые DTO и идентичность

JSON парсится с запретом duplicate keys/неожиданных полей, NaN/Infinity и неверных типов. Корень каждого запроса имеет ровно перечисленные поля; `null` разрешён только явно. Непереиспользуемые UUID — canonical lowercase strings. Значения boolean не принимаются как integer.

`PageInput` для check:

```text
{
  protocol: "page-editor-v1",
  generation: positive integer,
  baseRevisionId: UUID,
  editingFrom: "current" | "owner-draft" | "restore-stage",
  draftBasis: null | { id: UUID, revision: positive integer },
  stageId: null | UUID,
  changes: {только явно разрешённые поля текущего пользователя}
}
```

Поля changes: intro_text/main_text — исходные HTML strings; price — typed PriceV1/null; h1/title/description — plain text; indexing_allowed boolean; main_image/preview_image — два ImageRef/null. **Клиентские embedded_images/layout исключены**: producer выводит их из checked canonical richHTML + актуального server context, сохраняя image/node IDs и защищённые зависимости. Полная metadata встроенного изображения (UUID/alt/dimensions/alignment/parent/slot) находится в closed markup и входит в исходный1MiB budget его text field; отдельного unlimited image array поверх этого budget нет. Сотрудник передаёт только непустой поднабор текущих allowed_fields intro/main/price; owner-only ключ даже с прежним/пустым значением отклоняется. Владелец тоже не передаёт Page.kind/name/URL/parent/position/publication/права/Stable/Header/Footer/автора. Верхнеуровневый snapshot(schema_version/page_kind) собирает сервер.

PriceV1 точно соответствует DEV05: `{columns:[{id:UUID,label:string}],rows:[{id:UUID,label:string,cells:[Cell]}]}`. Cell — ровно `{column_id:UUID,kind:"text",text:string}` либо `{column_id:UUID,kind:"amount",amount:decimalString,from:boolean}`. Пустая семантическая ячейка хранится text="", не нулём; acceptance money/empty — проекция, не третья непроверенная storage-ветка. Stable cell identity=(rowUUID,columnUUID); label changes не перевыпускают UUID. Лимиты500rows/32columns/10000cells/label500/text1000, exact nonnegative decimal≤999999999.99, без float; wire decimal parsing и canonical normalization должны показать допустимые values без выдуманного запрета локализованного/экспонентного исходного ввода. Whole typed matrix не обрезается клиентом/драйвером.

Два внешних ImageRef — ровно `{asset_id:UUID,alt:string,alignment:"left"|"center"|"right",width_px:null|positiveInteger,height_px:null|positiveInteger}`. Внутренний выведенный producer EmbeddedImageRef добавляет `id:UUID`, но не является client array. Ни src/path/MIME/filename, ни injected attributes не принимаются. Alt≤300 plain codepoints. Производный Layout хранит existing DEV05 descriptor IDs и закрытые fields по schema.py; произвольный layout/block type/renderer name не является полем этого API. Точная carrier map — [dev07-format-carrier.md](dev07-format-carrier.md).

Для save/draft к тому же PageInput добавляются `operationId:UUID` и `checkReceipt:string`; для draft также `rebase:boolean` (действительный explicit rebase существующего owner draft), а не молчаливый перенос основы. Создание нового draft имеет draftBasis=null; существующий — точные id/revision. Save из owner-draft передаёт draftBasis существующему commit_owner; editingFrom=restore-stage требует stageId и не принимает draftBasis. Противоречивые сочетания отклоняются. Employee не выбирает owner-draft.

Ответ check: protocol, inputFingerprint, normalisedChanges, normalisationChanged:boolean, fieldWarnings:[{field,code,message}], checkReceipt, baseRevisionId. Никакого current pointer mutation или automatic version. Ответ не содержит скрытых protected fields сверх Page-доступа. Опасный ввод возвращает отказ целиком, не успешный нормализованный DTO.

CheckReceipt — подписанная stateless привязка protocol/policyVersion/actorId/generation/Page/base/permissionHash/editingFrom/draftBasis/stageId и fingerprints исходных и нормализованных changes. Без тела/PW/CSRF/session key. Не автоматическое разрешение сохранить: при write перепроверяются подпись, точное содержание, текущие права/base/политика и зависимости. Нет нового TTL бизнес-подтверждения; актуальность определяется этими состояниями. Ротация ключа может дать безопасный запрос повторной проверки, не silent save.

Принятие normalization: check показывает исходный/нормализованный результат и предупреждение; пользователь явно выбирает продолжение с этим результатом. При save отправляются именно показанные normalizedChanges с receipt, связывающим оба fingerprint. После любой правки содержимого нужен новый check. Опасный ввод не получает receipt. Нормализация не приводит к тому, что сервер автоматически принимает другой смысл без показа.

Ответ успешного save/draft: operationId,action,resultId,resultCode,replay,gone и только актуальный доступный current/draft basis. Receipt означает доказанный commit; HTTP200 само по себе не oracle. Terminal result/pruned result не выдаёт утраченный payload. Result-read проверяет текущую личность/generation/права, не служит lookup по чужому operationId.

## 3. Производитель HTML и единый restricted nh3

Предлагаемая последовательность без DB/domain locks:

1. Header/session/Page-access/CSRF проверены до большого тела; bounded reader/framing только после отдельного допуска transport. UTF8 strict, byte cap до JSON/HTML; ограничения scalar/field/DOM/price — независимые.
2. HTML5lib etree, без XML/lxml/внешних загрузок. Ранний контроль source bytes/работы и затем20k nodes/depth32/200k text codepoints; один post-parse count сам по себе не доказывает CPU/RAM bound. Нужен measured execution guard в существующем runtime, без нового worker по умолчанию. Пока предельные входы не укладываются, producer не подключается.
3. Полная проверка исходного дерева: TECH01 tags/атрибуты/URL, no script/style/SVG/MathML/foreign namespace/custom elements/events/исполняемые инструкции; Django конструкции в HTML отклоняются. Разрешённое Word оформление разбирается tinycss2 как декларации, с конечной allowlist значений и явной normalization; активное/неизвестное опасное свойство — whole refusal. Сотрудник не меняет protected node/media через текст.
4. Нормализованное представление serializes trusted code: только закрытые semantic attributes, разрешённые text/structure и защищённые opaque node IDs. Входные class/id не становятся системными; anchor IDs имеют отдельное content namespace. `style` как исполняемая/универсальная строка не сохраняется.
5. **Одна закрытая функция дополнительного nh3-clean** для уже проверенного HTML; фиксированные tags/attributes/URL schemes, без style/SVG/animation и без `filter_style_properties`. Никаких caller-supplied nh3 kwargs/allowlist/CSS. Три affected RustSec пути не объявляются исправленными; restricted call и upstream PoC — обязательные регрессии. Call не принимает небезопасное дерево с целью «потом очистить».
6. Проверка неожиданной потери структуры/текста/ссылок, повторный HTML5 разбор и idempotence. Если nh3 изменил уже разрешённый смысл сверх ожидаемой канонической сериализации — отказ, не публикация остатков. Отдельный serializer никогда не Template.compile/mark_safe raw input. Публичный вывод разрешает только verified producer representation.

Formatting хранится в server-owned semantic attrs/закрытых style tokens, не пользовательском CSS/selector. Визуальный editor node view и опубликованный renderer назначают только доверенные классы. Числовые цвета/шрифты/размеры задаются trusted CSSOM rules отдельного same-origin stylesheet либо заранее описанным конечным CSS-набором; вставлять style attribute или ослаблять CSP ради Tiptap нельзя. Точный carrier/roundtrip mapping и CSSOM-поведение должны пройти QA/review до реализации; кандидатные library probes не доказывают исправленный product renderer. Owner image selection берёт real Asset, src/srcset строит сервер.

## 4. UI-ввод, ошибки и повторный вход

Tiptap default paste/drop/HTML handoff не получает сырой HTML в liveDOM. Paste/drop перехватывается до вставки, source остаётся в памяти; check→показ нормализации→явное принятие→только approved representation в editor. HTML mode — textarea, а не исполняемый preview. Text-only безопасная вставка не превращается в произвольный HTML. Разрешённые H1/H2/H3/quote, размеры/таблицы/цвета/индексы и D057 таблицы реализуются в конечном профиле; H1 сотруднику не даёт менять защищённый главный H1.

Unicode lengths — Python codepoints после принятой нормализации; JS использует codepoint count, не UTF16 `.length`/native maxlength как единственную границу. Astral emoji и combining/NFC cases входят в тесты. Текст не усекается. Denied style, неправильная схема и неверное число не «лечатся» произвольным fallback.

| Код ответа | HTTP/смысл | Вкладка/состояние |
|---|---|---|
| INPUT_INVALID / HTML_UNSUPPORTED / URL_UNSUPPORTED | 400, field errors DTL001/007 | Ввод сохранён, current/draft/history неизменны |
| BODY_TOO_LARGE | 413, без полного parse | Нет partial commit/успеха |
| SESSION_ENDED | 401, DTL003 | Текст остаётся в памяти, отдельный повторный вход |
| PERMISSION_DENIED / CSRF_FAILED | 403, DTL004 | Не выдавать новые закрытые данные; note_denial существующим bounded агрегатором для authenticated denial |
| BASE_CHANGED / DRAFT_CHANGED / CHECK_CHANGED | 409, DTL002 | Без merge/нового base автоматически; сравнение после проверки доступа |
| RESTORE_INCOMPATIBLE | 409, DTL005 | Подстановка/commit целиком отклонены |
| RESOURCE_UNAVAILABLE | 503, DTL012 | При доказанном rollback понятный отказ; при потерянном ответе сначала result прежнего UUID |

Пароли/секреты не отражаются и не сохраняются. Validation/refusal не создаёт обычную content version. Отдельный безопасный bounded audit не содержит исходного HTML/имени файла/URL пользователя. Для постоянных машинных errors здесь предложение, не смена принятых русских UI сообщений.

Вкладка хранит собственный ввод только в памяти, без autosave/localStorage/sessionStorage/IndexedDB/URL/логов. Login в том же browser context отдельно, исходная вкладка остаётся. После входа явно проверяются фактический user ID, session generation, fresh CSRF, grants и base; тот же user не вызывает автоматическую отправку. Другой user не получает прежний payload/доступ к закрытой Page. Reload/закрытие может потерять ввод поD258. Перенос в свежую редакцию только явным действием после сравнения.

## 5. Атомарное Save/draft/restore и DEV05

После normalization/FS preflight producer передаёт Snapshot/TextPricePatch в existing services из autocommit; decoding/network/длинный parse не удерживают domain lock. Engine повторно проверяет content→auth→stable UUID row order, grants/generation/current/draft/stage/media READY и фактические evidence. Current+revision+AssetUsage+prune+receipt+audit atomic. Нового idempotence окна/Page quota не вводится; используется permanent DEV05 consumed ledger. Same UUID/other canonical input/action — отказ; replay — существующий ID/gone, без новой версии.

Restore UI получает current service get_stage после явного подтверждения замены несохранённого ввода. Payload stage повторно проходит актуальный producer profile/compatibility; до separate Save ничего не меняется. Employee проекция только разрешённых полей; защищённые URL/tree/publication/HeaderFooter/grants/Stable/owner media не переносятся. Последующая ручная правка stage допустима как обычный editor input; commit(stageId) сохраняет source provenance и перепроверяет whole compatibility. Terminal released/consumed/invalidated/gone/stale показывает честный результат без candidate. OwnerDraft basis сохраняется до explicit save/rebase/cancel независимо от смены current.

Protected media: сервер сверяет current layout/protected node IDs/fingerprints и Asset refs, а не доверяет client `editable=false`. Owner replacement создаёт новую reference, не перезаписывает существующие файлы. Сотрудник может менять текст вокруг сохранённого node, но не его место/структуру/Asset/alt/alignment; если выбранный UI не может обеспечить такой roundtrip без потери прав, scope функции не объявляется готовым. Конкретные разрешённые semantic node schemas/placement должны быть описаны до их code, нельзя трактовать произвольный opaque marker как выполненный component resolver.

## 6. Общие Header/Footer: отдельные модели и API

Предлагаемое приложение shared_content, не наследник Page. Конкретные имена новых модулей/полей — технический проект:

- `SharedBlock(id UUID,kind header|footer unique,current_revision FK,draft FK|null,generation)`: две записи, не public Page; без SEO/parent/url/is_published.
- `SharedRevision(id UUID,block FK,sequence,schema_version,payload,payload_hash,author_id,created_at,source_revision_id|null)`: immutable, actual dates/ID nonreuse; current входит в эту историю. Нет Page10/prune и новых Stable-команд.
- `SharedDraft(id UUID,block unique,revision,base_revision FK,payload/hash,author_id,created_at,updated_at)`: один действующий draft на блок, private owner; optimistic basis.
- `SharedRestoreStage(id UUID,block,actor/generation,source/base revision IDs,schema/policy stamps,status,terminal provenance)` и `SharedBasePin`: explicit cancellation/consume и terminal invalidation, не автоматический возраст; draft base удерживается до явного разрешения.
- `SharedReceipt(operation UUID,action,actor/generation,block/source/target/result IDs,fingerprint,resultCode,createdAt)` и минимальная permanent identity reservation: atomic with mutation, без payload/PW/CSRF/session, nonreuse/replay gone. Профиль следует принятым MAN01/02 принципам, Page receipt таблица не присваивается блоку фиктивной Page.
- `SharedBudget(singleton, snapshotCount, chargedBytes, reservation accounting/version)`: проверяемые cached counters с reconciliation actual rows/relations, не источник выдуманного размера.

Owner-only endpoints: GET `/manage/shared/<kind>/edit/`, POST `/manage/shared/<kind>/{check,draft,apply}/`, GET `/manage/shared/<kind>/history/`, GET `/manage/shared/<kind>/versions/<uuid>/` и `/compare/`, POST `/manage/shared/<kind>/versions/<uuid>/restore/prepare/`, `/restore/stage/`, POST `/manage/shared/<kind>/stages/<uuid>/cancel/`, GET `/manage/shared/<kind>/result/<operationUuid>/`. `kind` только literal header/footer, не произвольный component name. Restore сначала confirmed substitution, потом apply; прямого restore+publish shortcut нет. Поиск/history metadata paginated с deferred payload; все состояния owner-only.

Shared DTO: protocol="shared-editor-v1",generation,baseRevisionId,draftBasis/stageId,explicit sourceMode, componentSchemaVersion и собственный content payload; operations/checkReceipts аналогично Page, но bound block UUID/kind. Payload schema отдельно ограничена HTML≤1MiB/nodes20k/depth32, literal links/contacts, разрешённые Asset refs и только принятой component structure. Current navigation/mobile menu — trusted renderer, не редакторский JS. Список component types/structural classes берётся из принятого макета до кода, не придумывается как general HTML execution.

Asset ledger использует существующие closed kinds: shared_block consumerID=immutable SharedRevisionUUID для истории/current, draft consumerID=SharedDraftUUID; физические байты не копируются. Отдельные UUID непереиспользуемы, full consumer identity не пересекается с Page. Current shared snapshot всегда удержан, draft/restore bases защищены. Shared cleanup snapshot удаляет только свои usages; physical Asset cleanup остаётся отдельной media operation и повторно проверяет все6 kinds.

Историческое сравнение показывает исходный payload/schema и literal старый телефон. Unknown schema — безопасные данные, но whole restore refused; compatible rendering не выдаётся за побайтный старый экран. Apply новой версии меняет только выбранный блок; одновременные bases сериализуются PR08. Page restore не меняет SharedBlock. Публичная композиция DEV08 использует actual pair header/footer revisions и соответствующий ETag; draft не меняет валидатор/current. Полный DEV08/12/29 этим не закрывается.

## 7. Реальное учётное пространство и очистка общих блоков

Принятый общий budget256MiB=268435456B/10000снимков, warning75%, не Page10. Счётчик снимков — настоящие immutable revisions двух блоков. Payload, собственные metadata/receipt/pins/drafts, indexes/TOAST и временное пространство нельзя скрыть за одной суммой длины HTML. Новые записи не удаляют историю автоматически.

Предлагаемый измеряемый учёт: выделить собственные отношения shared_content; actual `pg_total_relation_size` всех собственных таблиц/индексов/TOAST (+принятые accounting records) вместе с reserved transient growth сверяется под content domain перед записью. Перед операцией считается upper reservation по реальному canonical UTF8 payload, строкам/индексам/размеру блока PostgreSQL и измеренному worst-case overhead; после записи actual footprint сверяется вновь до commit. Формула/коэффициенты не объявляются готовыми до actual boundary experiments с несжимаемыми payload и индексами. Если фактический безопасный резерв вычислить не удалось — отказ, не optimistic estimate. Physical heap growth после rollback/bloat остаётся фактическим потреблением следующей проверки, не «освобождёнными» байтами из ожидаемого counters.

Count check+byte reservation+revision/draft/refs/receipt/audit фиксируются атомарно; конкурирующая операция не расходует тот же резерв. Ресурсный отказ не меняет current/draft/history, не удаляет valid receipts/pins и сохраняет ввод в памяти. При75% предупреждение не блокирует допустимую запись. Это technical accounting project, не обещание подтверждённой достаточности256MiB и не разрешение менять бюджет.

Ручная snapshot cleanup: owner GET candidates, POST prepare exact IDs→signed confirmation bound owner/generation/block/revision stamps/dependencies+реально ожидаемый объём; POST confirm(operationUUID,confirmation) повторно проверяет current/draft/stage/protection/refs. Никакой age cleanup/foreign implicit cancellation. Текущий/защищённый/held basis не удаляется, operationbase не исчезает под подтверждением. Snapshot metadata removal+ledger detach+receipt atomic, физические Asset не unlink. «Освобождённое дисковое место» не равно сумме payload при PostgreSQL: UI показывает удалённые данные и отдельно actual measurement без false bytes claim. Новый block-Stable API запрещён; существующее protected migrated state при появлении не теряется.

## 8. Проверки до допуска и остающиеся технические ворота

Потребуются actual PG/FS+HTTP+JS-enabled controls: все прямые owner/employee rejectedHTML обходыUI с positive controls; PHP/Python/Django/JS не интерпретируются; Word accepted normalization до save; style semantic roundtrip+CSP безunsafe; codepoint/byte/DOM/price boundaries incl43MB example; true early auth/CSRF доbody/framing/timeout по transport proposal; no plaintext in storage/URL; same/different user reauth и stale grants/base; protected Asset/input injection; restore stage/no publication + explicit save/current source; atomic faults/replays/races; real shared budgets10000/256MiB/75%/transient overhead; incompatible history/actualrenderer trace; literalcontact restore/independent blocks/validator.

Непроверенные условия остаются явными: принятый D331 transport64MiB/streaming/child profile требует фактических испытаний; точная formatting carrier/CSSOM и Tiptap default-style suppression требуют независимого technical review; concrete component schema/structural class palette описывается по принятому дизайну до кода; parser execution/native advisory containment и storage accounting формула требуют испытаний. Новый parser worker/service/библиотека/CSP ослабление/прямая dependency сверх принятого профиля не возникают. Полные публичные шаблоны/главная/миграция/галерея/SEO/production остаются зависимым DEV scope.

Этот исполнитель подготовил только документ. Приложение, схемы/миграции, HTTP/settings/Compose/CSP/body и artifact cache не изменены. Утверждение APIs/DTO/технических формул координатором и независимое ревью обязательны до code cohort.
