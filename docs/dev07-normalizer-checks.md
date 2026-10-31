# DEV-07 — независимые сценарии pure HTML/CSS normalizer

2026-10-31, D-329–331. Основные V07-сценарии записаны до реализации. Дополнительная независимая детализация N07 ниже записана **до test_policy.py и тела html_policy**, при уже параллельно начатых types/constants/scaffold; более широкая хронология не заявляется. Источники: TECH01 §5/AC-DTL-004/006/017, V07-001–005/010/014–016, FMT001–009, dev07-format-carrier.md и dev07-editor-contract.md. Runtime guards20PASS — отдельное свидетельство, не прохождение этих сценариев. Пока фактических normalizer-результатов нет.

## Граница тестирования

Здесь проверяется чистая функция: строка и закрытый доверенный контекст → canonical carrier либо полный безопасный отказ. Ни БД/сессий/версий/HTTP, ни browser UI/CSP computed style/публикации тест не имитирует. Текущие grants, READY Asset/FS, component state, receipts и повторная проверка перед commit принадлежат следующей интеграции; синтетический ProtectedContext не объявляется реальной проверкой этих прав.

Все позитивы вызывают тот же normalizer, что отклоняет опасные строки. Ожидаемые текст/значения/структура задаются независимо, не копируются из result. Не использовать nh3-strip как успех whole rejection. Таблица/protected node с ещё не реализованной интеграцией даёт отдельный ControlledUnsupported, не молчаливое удаление/частичный canonical HTML и не заявление готовности функции.

## Независимые ожидания

| ID | Вход / положительный контроль | Oracle и граница |
|---|---|---|
| N07-001 | p/br/h2/h3/blockquote/списки/strong/em/u/s/sub/sup, кириллица/emoji/кавычки | Смысловые узлы и текст сохранены; canonical без style/runtimeclass/script; повторный normalize canonical идемпотентен |
| N07-002 | Owner body h1 и employee тот же h1; обычный h2 у employee | Owner content-h1 допустим, employee не обходит protected heading; h2 положительный. Это не запись Page.h1/проверка grants |
| N07-003 | benign b/i и безопасные style aliases | Явная normalization b→strong/i→em; normal/400/bold700, italic, underline/line-through/sub/super дают правильные semantic tags, changed/warnings показаны; не случайный порядок source attrs |
| N07-004 | Разрешённые font names,8/12.50/72px,HEX3/6/uppercase,bg transparent | Carrier имеет закрытые font enum/size12.5/lowercase6HEX/bg; foreground transparent,7.99/72.01/NaN/Infinity/экспонентный carrier/чужойfont отклонены без округления |
| N07-005 | align left/center/right/justify, margins0/64, cellpad0/32 в соответствующем допустимом carrier | Точные0 и nullable отсутствие различаются; +1/отрицательные/%/calc/чужое размещение attrs отвергнуты. Cellpad/table capability отдельно pending, если schema ещё не реализована |
| N07-006 | Вложенные spans с непересекающимися и переопределяемыми допустимыми свойствами | Итоговый inherited map каждого текстового run сохранён; минимизация span не теряет отдельные marks/текст; canonical reparse/clean не меняет смысл |
| N07-007 | Безопасный style + противоречащий data-es carrier; duplicates CSS/unknown attrs | Конфликт/неизвестный input вызывает whole PolicyError, не «последний победил»/silent drop. Согласованный безопасный вариант того же свойства проходит |
| N07-008 | script/event/iframe/SVG/MathML/object/embed/base/meta/custom tags/foreign namespace и malformed варианты | Весь исходник отклонён до restricted nh3; нет result.html/пригодного partial output, диагностическое сообщение не повторяет payload |
| N07-009 | Точные upstream PoC RUSTSEC-2021-0157/0158/2026-0373 из локальных первичных JSON | Все три получают product PolicyError до nh3. Отдельный restricted helper сохраняет HARMLESS/DATA/#safe без style/SVG/URL; helper не получает filter_style_properties |
| N07-010 | CSS escaped url/expression/property, position/z-index/line-height/import/font-face/var/functions/unknown declarations | tinycss2 decoding не прячет опасное; whole refusal. Safe font/color control принимается той же функцией; не browser computed-style fallback |
| N07-011 | Django {{expression}}/{%tag%}/{#comment#} в HTML, исполняемые/неописанные комментарии | Отказ, никаких Template/eval/исполняемых callbacks. Benign Word-traces допускаются только по явно согласованному конечному перечню и с normalization warning; новых исключений QA не придумывает |
| N07-012 | Local root/relative/http/https и _blank; Unicode host/обычный текст ссылки | Проверенный URL и подпись сохраняются; noopener для _blank, не навязанный nofollow/noreferrer. Source/result fingerprint и changed точно соответствуют реальным байтам |
| N07-013 | javascript/data/file/vbscript/blob, mixed-case/entity/control/backslash/protocol-relative/userinfo | Whole refusal после однозначного разбора/декодирования. Не превращать percent-encoded безопасный literal path/query в опасную scheme или запрещать любой encoded текст произвольно |
| N07-014 | Текст/URLs с внешними адресами и ссылка /manage/ в обычном контенте | Никаких fetch/DNS/socket/FS загрузок при normalize. Закрытые ссылки определяются утверждённым URL-context; function не проверяет существование внешнего сайта запросом |
| N07-015 | same-field/cross-field anchors, NFC labels, unknown target, cross-page literal URL | Exact data-es-target-field/anchor binding сохраняется; неизвестная метка даёт warning, не выдуманный запрет. Cross-page path#fragment остаётся literal без автоматического resolver |
| N07-016 | Дубликаты NFC labels в одном field, неполная/противоречивая binding-пара, чужой field/id/class | Неоднозначность/инъекция отвергнуты; intro/main scopes и system DOM не смешиваются. Runtime DOM id/CSSOM/browser navigation проверяются позже |
| N07-017 | Исходный UTF8 ровно1MiB/+1 без превышения text/node/depth | Byte-limit применяется независимо до дорогого parse. Позитив можно построить одним разрешённым anchor label в source budget, а не запрещённым comment padding; большой label не получает выдуманный отдельный cap |
| N07-018 |200000/200001 astral codepoints при <1MiB UTF8; короткий combining/NFC corpus | Нет UTF16 truncation/бесшумной усечки; codepoints и UTF8 bytes считаются отдельно. Правило NFC отражается явно, не меняет смысл/старые материалы молча |
| N07-019 |20k nodes/depth32 и +1 при остальных допустимых размерах | Полные допустимые позитивы и точные отказы. Перед тестовым кодом зафиксировать определение node/depth: fragment/text/comments входят или нет; не вычислять expected из ответа normalizer |
| N07-020 | caption Unicode/marks,thead/tbody/scope,rowspan/colspan, nested/oversized virtual table | При реализованном table policy всё содержимое сохраняется; неверная sparse grid/пересечение групп отвергнуты. Пока интеграции нет — явный ControlledUnsupported, не fake table PASS |
| N07-021 | Обычная table с >32колонок или >20000virtualSlots при допустимых source/DOM | Price32/10000 не назначается обычной таблице; widget cap не вводит content/save запрет. Полный canonical source сохраняется для opaque HTML-mode; GUI/TableMap здесь не имитируется |
| N07-022 | Protected marker со всем carrier/parent/slot и trusted frozen context; altered metadata/position | При описанной capability — сохранность карты и разрешённый текст вокруг; неизвестная/неполная integration — ControlledUnsupported. Raw src/путь/чужой marker не получает полномочий из одного UUID; real Asset/FS/права отдельно |
| N07-023 | Restricted nh3 вызывается только после полной проверки и с точными closed kwargs | No style/SVG/animation/filter_style_properties/wildcard data-attrs; разрешённые carrier/tags не теряются. Неожиданная потеря безопасного текста/anchor/carrier у helper вызывает PolicyError |
| N07-024 | Повторная сериализация, перестановка input attrs, quotes/entities/Unicode и новые/пустые форматирующие spans | Детерминированный canonical attribute order/escaping, стабильные source/result SHA, семантическая идемпотентность; source не сравнивается побайтно с нормализованным HTML как универсальное правило |
| N07-025 | Неверный value type/profile/field/scope/context; oversized/bad syntax | Закрытый API не принимает caller-defined cleaner options/renderer/file/команду. Только PolicyError(code)/ControlledUnsupported(code), без raw diagnostics/доступного частичного результата |
| N07-026 | Pure вызов/повтор/отказ при неизменяемом доверенном context | Нет мутации исходного context/его protected map; никакой записи временного input на диск/в журнал или сетевых операций. Process CPU/RAM/reap остаются отдельными runtime guards, а не доказательством одного unit-теста |

N07-008–011 обязаны проверять ранний отказ до nh3 через spy реального call boundary; позитивы одновременно доказывают, что та же политика/handler вообще доступны. Инъекция потери утверждённого текста/attrs после restricted helper — fault-injection тест, а не модель работающего normalizer.

## Закрытый API для независимых тестов

Root подтвердил проектную форму:

`normalize_html(value: str, *, owner: bool, field: str, scope_id: str, protected_context: ProtectedContext) -> NormalizationResult`

Fields — только intro_text/main_text; scope_id — canonical UUID из доверенного server context. Result: policy_version/html/changed/warnings(tuple кодов)/source_sha256/normalized_sha256, metrics(source_bytes,text_codepoints,node_count,max_depth), anchors/anchor_links/pending_assets. Отказ: PolicyError(code) или ControlledUnsupported(code), никаких raw diagnostics.

Исполнитель подтвердил import из page_editor.html_policy и frozen shapes из page_editor.types. ProtectedContext(nodes=()) — пустой trusted context. PolicyWarning(code,field), Metrics(source_bytes,text_codepoints,node_count,max_depth), Anchor(label,field), AnchorLink(field,anchor,href), PendingAsset(image_id,asset_id), NormalizationResult — замороженные dataclasses; policy_version=es-format-v1. Metrics относятся к source tree после CRLF→LF/NFC/entity decode и до generated wrappers: element nodes без fragment/text, direct child depth1, text/tails включая whitespace; source_bytes — исходные UTF8 bytes. Canonical tree budgets проверяются дополнительно. Restricted boundary — page_editor.clean.nh3.clean; spy оборачивает настоящий cleaner. Table/protected integrations до реализации остаются ControlledUnsupported после полного unsafe-input validation, не fake positives.

Проверка не должна получать arbitrary allowlists/cleaner kwargs из аргументов. Нет live Page/DB/FS lookup внутри pure API; actual grants/READY/owner/media proof потребитель перепроверяет отдельно. Tests используют стандартный unittest и фактические согласованные библиотеки, не собственный normalizer/expected JSON renderer.

## DEV07-B — независимая детализация до тестового кода

Root разрешил pure table/actual URL-context cohort; прежние unsupported expectations изменяются только после подтверждения фактической capability. HTTP-тесты этим разрешением не вводятся.

| ID | Ожидание и независимый oracle |
|---|---|
| B07-001 | Прямоугольная таблица, допустимые colspan/rowspan, expiry предыдущих rowspan и поиск первого свободного места: факты сравниваются с небольшим независимым dense-grid oracle на ограниченных deterministic fixtures. Oracle не импортирует AVL/placement helpers продукта |
| B07-002 | Детерминированно сгенерированные малые сетки сравниваются с oracle: overlapping/cross-row-group spans отклоняются. Ragged rows/дырки сами по себе не являются новым запретом и не исправляются молча. Политика placement сверяется с утверждённой геометрией, не угадывается по браузерному fixTables |
| B07-003 | Billion colspan и длинная десятичная запись сохраняют смысл или дают честный controlled resource/capability outcome согласно фактическому контракту; не создаются dense virtual arrays/поразрядные gigantic loops. Таблица не получает новый content cap из UI budget. Изолированный resource/time proof запускает root отдельно |
| B07-004 | Budget ровно20000 virtual slots даёт rich capability; +1/остаток после предыдущей таблицы даёт opaque fallback с полным approved HTML. Две таблицы по15000 не получают обе rich admission; перенос оставшегося editor budget между полями проверяется явно |
| B07-005 | Nested таблица остаётся approved canonical HTML и opaque capability без stock rich map. Caption с Unicode/marks, head/body/scope/cellpad/rowspan/colspan сохраняются после clean/serialization/reparse; unsafe source whole rejected до nh3 |
| B07-006 | Geometry proof выполняется на bounded real nodes без аллокации по virtual extent. Отдельные патологические/expiry workloads предназначены для resource guard, unit elapsed time сам по себе не объявляется production bound |
| B07-007 | Actual URLContext Page path/origin позволяет safe relative/parent links внутри public root; href остаётся literal по контракту. Same-origin absolute private paths, encoded dot/private paths и выход за root запрещены; внешний безопасный URL не переписывается в локальный |
| B07-008 | Без URLContext относительная ссылка остаётся явно unsupported; недоверенные/неправильные context и budget не получают расширенных прав. Protected nodes/reset-normal остаются pending; тест таблицы не снимает этот отказ |

## Статус

Подготовлен первый независимый исполняемый набор `app/page_editor/test_policy.py` на стандартном unittest после подтверждения фактических types/API и freeze core. В нём реальные безопасные positives, canonical/SHA/source metrics, целый отказ до nh3, три точных upstream PoC, границы source bytes/codepoints/nodes/depth, отсутствие сетевых вызовов, конфигурация настоящего cleaner и отказ при его неожиданной потере текста. Отдельные регрессии: атрибуты в закрывающем теге (PRODUCER-REV001), неверный тип field и inherited style resets.

Первый pure cohort оставлял safe table/protected integrations и относительный URL-context неподдержанными. DEV07-B меняет только подтвердившуюся table/URL capability: новый `test_tables.py` сравнивает геометрию с независимым малым dense oracle на160 детерминированных примерах, проверяет expiry/first-free/overlap/group boundaries, сохранность caption/scope/carriers/nested approved HTML, aggregate20000/carry между полями, billion и5001-digit colspan, actual URLContext. Прежний table unsupported assertion заменён настоящим положительным контролем, а relative без контекста, protected integrations и semantic resets normal/400/none/baseline остаются явными unsupported; unsafe source всё равно отклоняется целиком.

Новая table capability — server facts/approved canonical HTML, не доказательство полноценного widget, CSSOM, TableMap, browser commands или публичного renderer. Ресурсная пригодность AVL/giant spans требует отдельного isolated измерения; наличие unit testcase без dense allocation не считается memory proof. Тесты не подтверждают права, READY/media membership, transport или сохранение страницы и не закрывают весь N07/V07/DEV-07.

Docker/network/install/runtime QA этим агентом не выполнялись; результат набора пока НЕ ПРОВЕРЕН. Root запускает первый approved isolated runtime после freeze и независимого ревью. app/editor_runtime и price tests не менялись. Приёмка pure helper не закрывает V07/AC/публичный renderer/полный DEV-07.
