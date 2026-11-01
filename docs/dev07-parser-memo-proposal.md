# DEV07-F — ограниченный request-local memo разбора

2026-10-31. Отдельное техническое предложение до ревью и code gate. Прежнее coalescing предложение: dev07-parser-performance.md. Никаких изменений приложения, лимитов, зависимостей, разрешённых HTML/прав или live/VPS этим документом не выполняется.

## Измеренное основание

work/dev07-f-20261031/entity-optimized-phase-first.txt: optimized parse exact200000 entity text — CPU2.114824s, прежний canonical SHA95097f…; pure H.normalize_html CPU8.015022s, три parse около2.080/2.045/2.074s, scan1.392s, cleans0.135/0.140s. Whole child CPU около8.651s, OOM0, reaped. Это instrumentation pure H, а не успешный actual embedded handler. Actual optimized handler ранее завершился-9; его дополнительный pre-scan/preparse объясняет выход за CPU10s, но новая request-local схема ещё не измерена. Ускорение одного parse не было достаточным допуском.

## Точный минимальный API и lifetime

В app/page_editor/html_parser.py предлагается закрытый stdlib contextmanager `_parse_session()` без аргументов. ContextVar default=None хранит только активный session object; модульного dict/LRU/source/tree вне активного session нет. Session содержит максимум одну пару exact source str + закрытое raw etree дерево. Contextmanager не выдаёт caller cache object и в finally явно удаляет key/tree и reset ContextVar token. Исключение, отказ normalization, issue branch и успешный return очищают scope одинаково. Nested session не создаёт вторую запись: для первого инкремента это фиксированная внутренняя ошибка, а не неограниченный стек caches.

Единственная production точка lifetime — существующая page_editor.normalizer_child.normalize(raw,context): lazy import `_parse_session`, затем `with _parse_session(): return _normalize(raw,context)`. Нынешнее тело normalize переименовывается в private _normalize без перестановки его условий/проверок/фингерпринтов. Обёртка включает embedded-issue и все current/draft/stage branches. child_bootstrap, parent Django/EditorSlot, framing и resource launcher не меняются. Даже если normalize вызывается непосредственно из тестового/другого процесса, finally очищает cache до возврата; долгоживущий Django процесс не сохраняет HTML после вызова.

Прямой parse_fragment(source) вне активной session ничего не memoizes и сохраняет нынешний fresh parse. `_CoalescingParser()` и его .errors также всегда остаются настоящим fresh parser, без memo и caller-configurable cache. Вход, treebuilder, namespace, container/scripting фиксированы, поэтому parse identity не зависит от actor/Page/grants/URL/source mode. Эти контексты продолжают проверяться отдельно на каждом этапе.

## Алгоритм одной записи и границы

1. Lookup только по точному равенству Python str, не по hash/normalized key. Разные Unicode формы, whitespace, entity spelling и case — разные keys, даже если итоговые деревья похожи. До каждого production parse вызова прежний caller выполняет свою полную admission; cache не отменяет scan, raw-byte/type/NFC/role/URL проверки.
2. Entry допускается только для exact source UTF8≤существующего MAX_SOURCE_BYTES1MiB и корректного bounded дерева в пределах существующих node20000/depth32. Проверка пригодности memo не нормализует и не отклоняет контент: при превышении cache-admission или Unicode/parse error источник просто идёт uncached, а прежний caller определяет свой отказ. Это bound внутренней памяти, не новый content limit. Исходник, выросший при canonical serialization, также не получает cache сверх1MiB.
3. Miss сначала освобождает старые key/tree, затем выполняет тот же реальный _CoalescingParser один раз. Исключение не кешируется. Для первого инкремента parser.errors nonempty также не кешируется: повторный вызов проходит тот же parser и error positions. Fresh parser и stock differential oracle сохраняются; helper не синтезирует parser.errors.
4. При допустимом результате приватный raw tree сохраняется до любых caller mutations. Caller получает только copy.deepcopy(raw tree), включая первый miss return. Каждый hit вновь возвращает deepcopy. Element/children/attrib containers не разделяются между returns; sharing неизменяемых str text/tails безопасно. Запрещено возвращать cached tree, его children/attrib либо закрытый cache handle. Deepcopy failure распространяется как прежний resource failure, без возврата shared tree/частичного успеха.
5. На hit сохраняется точное source-specific дерево штатного deterministic parser; не объединяются разные источники. Тот же parse_fragment всё равно вызывается во всех четырёх production местах; заменяется повторное детерминированное построение идентичного дерева, а не последующие проверки. После смены key только одна новая запись; cache не хранит оба rich fields/версии/историю.

При miss одновременно существуют parser tree, его copy для caller и уже существующие локальные значения caller; при hit — private raw tree и copy. Это реальная дополнительная память, не бесплатный cache. Бюджет учитывает tree containers и canonical/raw strings, а не только1MiB key. Под прежним AS384MiB/CPU10s/wall20s обязательны реальные максимальные замеры; лимиты автоматически не повышаются. Session не служит хранилищем text/PW/CSRF/permit после запроса и не логирует source. Жёстко завершённый отдельный child не оставляет process-local memo в parent.

## Почему проверки не снимаются

Разбор exact str с фиксированным parser profile детерминирован: raw output не зависит от времени/БД/actor. Тем не менее это утверждение требует differential и mutation tests, а не разрешает объявить semantic equivalence по одному SHA. Cached tree — до normalized-tree mutation, protected-map extraction, permit stripping, derived refs и nh3; никто из этих этапов не получает mutable reference к memo.

Все реальные _scan, metrics, source scopes, protected map/parent union, style/URL validation, два restricted nh3 clean, postclean signatures и idempotence остаются на прежних местах и выполняются на независимых копиях. Если clean изменил строку — новый key и настоящий parse, а не ложный hit. Source warnings, meaningful NFC/CRLF comparison, raw request fingerprint/D334 replay и CheckReceipt hashes/crypto не меняются. Нельзя кешировать accepted policy result, capabilities, реальный media evidence/права или worker response.

## Независимые доказательства до допуска

| ID | Oracle |
|---|---|
| MEMO-001 | Stock и fresh coalescing differential corpus прежнего gate остаётся; exact tree/attrs/text/tails/namespaces/errors/canonical на допустимых и adversarial fixtures; raw parser class не memoized |
| MEMO-002 | В session первый parse, изменить returned root/text/tail/attrs/children, повторить exact source: новая copy равна независимому stock, source hash прежний; изменить вторую copy и проверить третью. Сравнить object identity всех mutable containers, не только final string |
| MEMO-003 | A→A даёт один реальный parse; A→B→A даёт три, одинаковое canonical с разными exact str не hit; source/parse errors и exceptions не memoized. Счётчик wraps настоящего parser без подмены результата |
| MEMO-004 | Две последовательные session не делятся tree/key; exception/normalizer отказ/embedded-issue cleanup и direct helper outside session каждый fresh parse. Nested-session controlled internal error не удерживает данные после outer finally |
| MEMO-005 | Cache-admission UTF8/node/depth exact/+1: непригодность memo не меняет сам parse result или caller refusal. Source-only parse вне session не получает новый business limit. Реальные large mixed20knodes/depth32/text200k и два rich fields/retained selected source под AS384, не только tiny p |
| MEMO-006 | Pending permit NFC/repeated Check, employee/current/draft/stage и source maps, canonical mutation between stages, malformed repairs/error locations, nh3/signature/idempotence fault controls: не исчезает ни одна проверка, полный parent proof/binding/old replay прежний |
| MEMO-007 | Тот же actual handler exact entity200k обоих roles и decoded200001/rawsource>1MiB negatives. Новый source/измеренное условие разрешает ровно следующий осмысленный прогон; диагностический pure H успех не заменяет socket/native workflow |

Измерения root: прежний phase harness с явно обозначенным активным _parse_session вокруг full normalization, stock/fresh parse modes без session. Записать реальные parse call count/miss/hit через test-only observing wrappers, closed numeric phase records CPU/wall/RSS/exit/reaped/OOM; не выдавать saved parse executions за пропущенные security checks. Затем non-instrumented actual child/handler, canonical/input/output/source/profile/image hashes, memory peak maximum-case. Stderr без source/URLs/attrs/permit/секретов. Ни повторного full handler на неизменённом source, ни повышения лимитов/снижения fixture/skip oracle.

Предлагаемые будущие app изменения ограничены html_parser.py и обёрткой normalize в normalizer_child.py. Lazy logical position optimization и расширение table/attribute batching сюда не включаются. До независимого ревью этого документа, сценариев QA и отдельного root code gate приложение остаётся frozen.
