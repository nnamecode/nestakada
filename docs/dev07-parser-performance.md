# DEV07-F — предложение локальной оптимизации HTML-разбора

2026-10-31. Только техническое предложение до кода и независимого ревью. Повод: FUI ENTITY_EXACT, `<p>` + `&amp;` ×200000 + `</p>`, исходные1000007 UTF8 bytes, декодированные200000 codepoints, получил503 EDITOR_PROCESS_UNAVAILABLE. Причина завершения child и фазовые времена ещё проверяются root; лимиты/положительный oracle не меняются. Никаких зависимостей, vendor patch, сети, увеличения CPU/AS/wall или подключения live/VPS.

## 1. Фактически прочитанный путь

Установленный html5lib1.1 найден через rg inventory: `work/dev07-package-cache/python/site-packages/html5lib/`. `_tokenizer.py` в consumeEntity выдаёт отдельный Characters либо SpaceCharacters token для каждой entity вне attributes. `treebuilders/etree.py:110–130` добавляет его через `_element.text += data` либо last-child.tail += data. Накопление большого immutable text небольшими кусками — конкретный кандидат квадратичного копирования; само наличие этого кода ещё не доказывает CPU kill в данном HTTP-прогоне. Attributes имеют отдельное накопление в tokenizer и этим предложением не оптимизируются.

Результат rg по app/page_editor: ровно четыре production callsite parseFragment, не обязательно четыре исполнения на весь запрос:

| Место | Роль |
|---|---|
| embedded_policy.py:113 | Предварительное дерево candidate для извлечения transient permits и derived map |
| html_policy.py:267 | Первичный нормализованный rich source |
| html_policy.py:328 | Повторный разбор результата единственного закрытого nh3 call |
| html_policy.py:334 | Повторный разбор после второго clean для idempotence/signature |

На один изменённый embedded field эти четыре стадии могут выполниться последовательно. Protected source_maps вызывает build_protected_context → html_policy._admit_protected_source → _normalize_html(source_facts=...), поэтому добавляет те же три callsite на соответствующее сохранённое поле. Два field/source могут увеличить число исполнений; не обещать постоянные4 parse на request. protected_policy.py собственного parseFragment не содержит. normalizer_child делегирует этим функциям, включая action embedded-issue/source_bindings. Parent получает source metadata под прежними правами/EditorSlot; отдельный новый parent parse не предлагается. Независимые test_policy.py/test_tables.py оставляют stock html5lib как oracle.

## 2. Предпочтительный консервативный вариант

Один новый закрытый helper parse_fragment(text) создаёт собственный подкласс html5lib.HTMLParser с прежним etree treebuilder и namespaceHTMLElements=True. Никаких caller kwargs, иной container/scripting либо разрешения менять tokenizer/treebuilder. Собственный mainLoop устанавливает временный tokenizer proxy только у этого parser instance и восстанавливает original в finally; super.mainLoop, штатные phases, namespaces, insertion modes, parsing/reprocessing и EOF остаются html5lib1.1. Глобального monkeypatch и изменения установленной библиотеки нет. Все четыре production callsite вызывают один helper, raw producer _scan продолжает использовать исходный HTMLTokenizer без группировки и без ослабления проверок.

Предлагается сначала группировать только безопасный ограниченный путь: parser.phase is parser.phases['inBody'], текущий узел и предки HTML namespace, вне table-family/foreign/rawtext/select/pre contexts. Для всех остальных состояний iterator выдаёт оригинальные tokens без объединения. Тем самым оптимизация ENTITY_EXACT в обычном p не требует доказывать изменение table insertion modes. Список исключённых состояний/узлов закрытый и фиксируется в реализации до тестов; неизвестный phase/context всегда stock, не guessed safe. Это техническое ограничение оптимизации, не запрет принимать прежний HTML.

Группируются только подряд идущие tokens одного точного типа: Characters отдельно от SpaceCharacters. Нельзя сливать whitespace token в Characters, изменять data, отбрасывать пустые/error tokens, декодировать raw source самостоятельно либо повторно токенизировать декодированные `<`, `&`, quotes. Накопление — list of chunks + join; batch threshold8192 decoded codepoints — технический размер порции, не отказ/новая бизнес-квота. Большой одиночный token не обрезается; остаток проходит следующими порциями либо stock token без изменения данных. На порции/конце обязательно flush, все байты/символы сохраняются.

StartTag/EndTag/EmptyTag, ParseError, Comment, Doctype, standalone NUL либо data с NUL и EOF — barriers: сначала выдать text batch, затем оригинальный barrier в исходном порядке. Нельзя читать следующий token ПОСЛЕ barrier до того, как parser получит и обработает сам barrier: иначе parser может не успеть переключить tokenizer state для rawtext/rcdata. Чтение одного barrier как lookahead допустимо лишь с удержанием его неизменённым и паузой после выдачи; никакого prefetch за tag/error. Stream/state методы и записи tokenizer.state/currentToken/etc делегируются исходному tokenizer, а не создают теневые поля proxy. Reparse/encoding paths должны сохранять прежнее поведение; вход helper — уже decoded Python str, не новая byte-encoding политика.

Особый риск — stream.position: lookahead мог уже продвинуть stream за buffered text. Нельзя объявлять прежние parser error locations сохранёнными автоматически. Proxy обязан сохранять логическую position каждого отложенного token и отдавать её при обработке barrier; text batch соответствует позиции его последнего исходного token. Непосредственный raw _scan вообще не меняется. Для eligible inBody non-NUL text штатные handlers reconstruct formatting/insertText/framesetOK не создают parseErrors; вне этой доказанной области группировки нет. Exact parser error sequence/positions остаются differential gate: при расхождении конкретный класс выводится из eligible batching либо предложение пересматривается до допуска. Токены/error provenance не выдаются в публичный response/log.

Обобщённая группировка во всех modes сейчас не предлагается: inTableText содержит специальный whitespace/foster-parenting поток, а отдельные handlers трактуют одиночный NUL особо. Сначала нужен завершённый ограниченный алгоритм; не расширять его незаметно ради следующего performance failure.

## 3. Неизменяемые гарантии

До helper остаются raw UTF8 source1MiB, CRLF/CR→LF/NFC и whole _scan; после — прежние metrics, URL/style/role validation, protected source map, derived union, restricted nh3 без style/SVG/filter_style_properties, postclean signatures, idempotence. Source bytes считаются до normalization. ENTITY `<script>` после декодирования остаётся text token, никогда HTML markup. Не убираются повторные clean/parse/signature ради экономии без отдельного доказательства.

CheckReceipt, original input fingerprint/permanent replay, normalization warnings, token stripping comparison, server-issued identities, source scope/generation/session/grants и actual media evidence остаются прежними. Один helper не становится альтернативным способом принять unsafe input или произвольный caller token stream. Old current/draft/stage receipts и exact canonical/protected map hashes должны сохраниться на прежнем corpus.

## 4. Проверки до допуска

Stock HTMLParser1.1 — независимый oracle. Сравнивать структуру namespace/tag/ordered children/attrs/text/tails и stock parser.errors с positions/datavars; canonical serializer output и actual policy results/signatures/maps сравнивать отдельно, не строить expected через optimized helper. Нельзя сравнить только извлечённый plain text.

| ID | Обязательные controls |
|---|---|
| PERF-001 | ENTITY_EXACT200k, plain200k, mixed literal/entity, batch8191/8192/8193 и несколько batches: exact tree/text/tails/canonical; count actual original vs emitted tokens/insertText calls numeric-only |
| PERF-002 | `&lt;script&gt;`, escaped event/img/quotes, `&amp;lt;`, numeric decimal/hex/astral/multi-codepoint named entity, invalid entity/missing semicolon/NUL/replacement/control: тот же refusal либо exact safe text, nh3 не видит запрещённое дерево |
| PERF-003 | Отдельные SpaceCharacters, space entities, CRLF/NFC, Unicode/combining, mixed inline strong/link/anchor, text before/after child и active-format adoption/reconstruction; exact source warning/hash |
| PERF-004 | table whitespace/foster parenting, caption/thead/tbody/cells/nested tables, mixed text around table; foreign namespace/rawtext/select/pre/malformed EOF/attrs/error barriers. Эти contexts идут stock, exact tree/errors/positions обязательны; unsafe product input rejected до clean |
| PERF-005 | Entity-heavy attributes и boundaries перед/после attribute errors: unchanged token/value/error semantics. Это регрессия, не обещание устранённой attribute performance проблемы |
| PERF-006 | Owner/employee existing protected maps и pending permit repeat Check после NFC, current/draft/stage, shared refs, canonical Save без transient token, old permanent replay; independent parent union/proof checks неизменны |
| PERF-007 | Тот же positive exact200k и отрицательные decoded200001/rawUTF8>1MiB/nodes/depth plus1; accepted result без усечения, rejected без БД/current/history/refs/receipt mutation |

## 5. Фазовый benchmark без изменения ресурсов

Root запускает отдельный диагностический harness из сохранённого исходника в прежнем worker profile: AS384MiB, CPU10s, wall20s,1heavy slot; родитель/транспорт/body caps прежние. Не повторять полный HTTP до нового свидетельства/изменённого source. Сначала установить returncode/signal, elapsedCPU/wall и фазу последнего numeric record у failing stock input, затем сравнить optimized variant под теми же caps и exact final output oracle.

Разрешённое временное instrumentation только в test harness: обёртки реальных _scan/parse_fragment/restricted_clean/_metrics/_serialize/whole-normalize, вызывающие настоящую функцию один раз и записывающие CPU user+sys из getrusage и monotonic duration, счётчики вызовов/token/insertText/длин. Не подменять результаты, лимиты, child launcher или время. Stderr — только фиксированные numeric phase IDs/counters/durations/exit code, без HTML/URL/attrs/token/body/секретов; stdout остаётся прежним bounded result protocol. Измерять вложенные inclusive фазы явно, не складывать их как независимый elapsed total. Instrumented и non-instrumented final runs различаются и документируются; диагностический успех не заменяет actual child/HTTP acceptance.

Должны быть actual peak RSS/exit/cgroup evidence там, где применимо, сохранённые input/output hashes фиксированного synthetic corpus и неизменные profile/image/source hashes. Не повышать ограничения после resource failure; если одной coalescing оптимизации недостаточно, фиксировать конкретную новую фазу/причину и готовить отдельный ограниченный план. До ревью документа, отдельных QA scenarios и root code gate приложение не изменяется.
