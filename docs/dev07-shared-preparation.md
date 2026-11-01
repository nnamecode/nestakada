# DEV07-SH — подготовка общих блоков и измеряемой квоты

2026-11-01. DEV-07 около95%, этап8 около20%. Техническое предложение для независимого ревью до кода; это не сообщение о готовности Header/Footer. Возобновление документальной работы — DEV07-SH-RESUME-001 по work/dev07-combined-20261101/shared-resume-plan.md. Старый сайт/VPS, зависимости, ресурсы и конфигурация не меняются.

**Актуальный метод ограниченного probe:** [dev07-shared-probe-amendment.md](dev07-shared-probe-amendment.md), предварительное независимое ревью метода завершено без блокеров. Первый TEMP прогон завершился отказом TEMP privilege на первом CREATE (1test/error,0PASS); неизменный повтор не выполнялся. Ниже TEMP-разделы сохраняют первоначальный проект, а не описание текущего исполняемого метода. Тест адаптирован к фиксированным собственным `app.es_shared_probe_*` отношениям внутри обязательного outer rollback; перед запуском нужен независимый разбор точного diff/hash. Новых прав/GRANT, настроек, product моделей или API нет.

## Основания и границы

Принятые основания: D-066, D-111, D-261, D-294, аналитика D-301; analytics-content-detail.md §7; dev07-editor-contract.md §6–7; acceptance-shared-blocks.md, acceptance-shared-component-restore.md, acceptance-version-storage.md. Постоянные связи: REQ-013/017/018/022/028/029/050, AC-013/017/022/028/029/050, AC-DTL-017, AT-117/405. Номера ниже уточняют технические проверки, не заменяют эти требования.

Нельзя наследовать для общих блоков Page10/новые Stable-команды или приписывать блоку фиктивную Page. История двух блоков независима, общий ресурсный бюджет —256МиБ=268435456B и10000 immutable снимков; один действующий черновик на каждый блок. Предупреждение при измеренной byte-занятости не менее75% не запрещает запись, если резерв достаточен. Исчерпание бюджета не разрешает автоматическую очистку.

Схема ниже выводится из принятого макета docs/design/public-light-v4-template.html: header строки33–49 и footer182–192, с историей правок docs/public-light-v4.md (D-129–132). Тексты/контакты — содержимое, а не новая проверка их актуальности перед выпуском. Демо HTML редактора из admin-design-options.md не считается готовой серверной политикой.

## SH07-SCHEMA-001 — закрытая структура первого компонента

Предлагаемые идентификаторы схемы: header-v1 и footer-v1; версия профиля нормализации хранится отдельно. Это доверенные литералы, не имена импортируемого модуля или шаблона. Форма снимка: schema_version, component_kind, canonical_html и извлечённые сервером Asset bindings. Не принимать произвольный клиентский список файлов, renderer name, Django/Python/JS, CSS-файлы или набор разрешённых классов.

Разрешённая структурная палитра ограничивается фактическим макетом:

| Блок/элемент | Тег и точный структурный класс | Содержимое |
|---|---|---|
| Header root | header.es-header | Один brand, доверенная область меню и один contacts |
| Логотип | a.es-brand → img | Буквальная безопасная ссылка, выбранный READY Asset и alt |
| Контакты | div.es-header-contacts | Socials, address, phone в порядке макета |
| Социальные ссылки | div.es-header-socials → a → img | Буквальные HTTPS-ссылки/подписи, READY Assets; исходный порядок Telegram/MAX/Instagram |
| Адрес | a.es-header-address → b, span | Буквальная ссылка на карту, город/адрес |
| Телефон/расписание | a.es-header-phone → strong, span | Буквальный tel: и видимый телефон/расписание |
| Footer root | footer.es-footer | Один left и один legal |
| Левая часть Footer | div.es-footer-left | Brand как выше и p с буквальным копирайтом |
| Юридическая часть | div.es-footer-legal | Две span с буквальными подписями и credit |
| Подпись автора | span.es-footer-credit → b | Буквальный текст |

Это первоначальная закрытая схема по существующему компоненту, а не универсальный конструктор. Перечень не разрешает произвольное размещение этих классов на любом теге/вложенности, дублирование обязательных областей или классы других секций главной. Неподдерживаемое изменение структуры отклоняется целиком с сохранением ввода. Расширение палитры требует отдельного технического контракта и проверки; существующий исторический снимок не переписывается ради новой схемы.

Атрибуты первого профиля: структурный class только из таблицы в указанной позиции; a[href] с разобранным безопасным URL и текстовой aria-label при наличии в макете; img с серверно назначенным src из READY Asset, alt и проверенными числовыми размерами. На доверенной области меню — фиксированные id/aria-controls/aria-expanded/type, которые не поступают как произвольные редакторские атрибуты. Нельзя on*, style/произвольный CSS, srcset, iframe, svg, script, template, data-* от клиента или arbitrary id. Точный формат внутреннего Asset-маркера должен быть определён до sanitizer-кода, согласован с media_library и проверен на подмену идентичности. SVG-иконка макета не означает разрешения вставлять сырой SVG: выбор доверенного Asset проходит отдельную проверку поддерживаемого файла.

Базовый профиль не добавляет редактируемых юридических ссылок там, где принят макет с неактивными span. LEGAL-01/согласование юридических материалов остаются отдельными. Значения нынешних телефона/адреса не фиксируются как неизменяемое бизнес-правило: владелец редактирует буквальное содержимое, а историческое восстановление возвращает прежнее буквальное значение после сравнения.

## SH07-SCHEMA-002 — доверенное меню и снимок

В макете есть button.es-menu-button с тремя span и b, aria-controls=es-nav, а nav#es-nav содержит ссылки. Интерактивное поведение и управление aria принадлежат доверенному renderer; редактор не получает обработчики событий/JavaScript и не сохраняет состояние открытого меню.

Предлагаемый способ интеграции: сервер распознаёт единственную фиксированную область навигации в schema header-v1 и выдаёт её доверенным кодом; содержимое текущей навигации берётся из действующего DEV-29/DEV-08 механизма согласно D-032. Новый язык плейсхолдеров в HTML не вводится. Конкретная форма внутреннего маркера/нормализации этой области остаётся техническим воротом до реализации Header apply: нужно проверить, что фактическая автонавигация не превращается в новый несогласованный реестр ручных меню. Сам принятый статический макет не доказывает реализацию этого механизма.

Исторический просмотр обязан отдельно обозначать живую доверенную навигацию; нельзя выдать её за побайтный старый экран. Буквальные контакты и ссылки вне этой области входят в snapshot и возвращаются буквально. Снимок не содержит всю навигационную БД, права или секреты. До выбора конкретного marker/resolver нет заявления о готовности публичной композиции.

## SH07-DATA-001 — отдельная история и действия

Конкретный следующий проект использует предложенные в dev07-editor-contract.md §6 SharedBlock/SharedRevision/SharedDraft/SharedRestoreStage/SharedBasePin/SharedReceipt/SharedBudget. Перед миграциями требуется зафиксировать типы, ограничения FK/unique, identity reservations и все затраты отношений; сейчас модели не созданы.

- Два фиксированных kind header/footer, без Page URL/SEO/публикационного флага. Только текущая owner-сессия/generation; назначение сотруднику Page не даёт доступа к любому shared endpoint.
- Check не публикует. Draft сохраняет только отдельный черновик. Apply после Check и повторной проверки текущих прав/base создаёт новый immutable снимок и меняет только выбранный блок. Второй блок и Page не меняются.
- История/сравнение owner-only, постраничные metadata без загрузки10000 HTML. Unknown schema доступна как экранированные данные; whole restore неподдерживаемой схемы отклоняется.
- Restore prepare после подтверждения замены ввода создаёт основание редактора, но не меняет current; отдельный Apply создаёт новую текущую версию, исходный snapshot остаётся неизменным. Старый буквальный телефон показывается до применения.
- Операции имеют отдельный shared operation UUID/receipt, bound actor/generation/block/source/base/action/fingerprint. Exact replay не создаёт вторую версию; другой ввод под тем же ID — конфликт. Page receipts не используются как фиктивные shared receipts.
- SharedRevision UUID — consumer_id kind=shared_block; SharedDraft UUID — kind=draft. Existing media_library.models.AssetUsage и media_library.services.attach/detach позволяют удерживать ссылки без копирования файлов. Полная идентичность consumer/slot не смешивается с Page. Физическая очистка Asset отдельно перепроверяет все виды ссылок.
- Content lock из content.models.lock_content берётся до auth/row locks по существующему порядку; тяжёлое чтение/нормализация не удерживают SQL-транзакцию. Конкретный shared сервис не вызывается до проверки этого порядка независимым ревью.

Пути — уже предложенные /manage/shared/<header|footer>/edit/, check/draft/apply, history/versions/compare, restore prepare/stage/cancel/result из dev07-editor-contract.md; пути не подключены. DTO shared-editor-v1 не принимает поля Page/URL/Stable/права/автора, использует явные sourceMode/generation/base/draftBasis/stage. Shared reader до4МиБ, прежний внешний11МиБ, один heavy slot и прежний child/cgroup профиль. Shared не получает64МиБ Page transport.

## SH07-QUOTA-001 — что нужно измерять

Count — фактическое число SharedRevision обоих блоков, включая current; draft не притворяется immutable снимком, но занимает byte-budget. Byte-accounting включает все собственные shared heap/index/TOAST/freespace/visibility map footprints, receipts, identity/pins/drafts/budget metadata и резерв временного роста. Файлы Asset считаются в своём медиа-бюджете, но attributable AssetUsage metadata нельзя спрятать: будущая формула должна явно назначить им измеренный верхний резерв/долю общего отношения. Нельзя суммировать pg_total_relation_size таблицы и её индексов/TOAST второй раз.

Предлагаемый measured footprint: pg_total_relation_size каждого корневого shared table OID плюс отдельно перечисленные не входящие в эту сумму attributable отношения/резервы. Корневые OID устанавливаются доверенным migration inventory, не строкой HTTP или широким запросом ко всей БД. Никакой pg_total_relation_size по пользовательскому имени. Конкретное покрытие forks проверяется в экспериментах, а не предполагается по названию функции. Общее место PostgreSQL/WAL/backup и общие таблицы аудита имеют отдельную эксплуатационную границу;256МиБ не называется ограничением всего диска VPS.

Admission под content domain: fresh actual count/bytes → conservative transient reservation → проверка остатка → атомарные snapshot/draft/refs/receipt/audit → actual post-write measurement до commit. Счётчик — проверяемый cache, actual rows/relations являются независимым oracle. После rollback physical heap growth не вычитается как якобы освобождённый. Post-write превышение требует rollback и диагностируемого отказа, но само по себе не доказывает hard physical cap: до допуска надо показать, что предварительный резерв покрывает рост и отказы.

Произвольный коэффициент ×2/×4 по UTF8 не утверждается. Экспериментальная верхняя оценка на конечном corpus не является математической гарантией для всех payload/версий PG. Если достаточный резерв не обоснован — отказ и открытые ворота формулы, без автоматического повышения лимита или усечения допустимого ввода. Обновление PG/schema/indexes требует перепроверки коэффициентов/минимального резерва.

## SH07-QEXP — сценарии до реализации

Первый допустимый инкремент — изолированный измерительный probe с собственными TEMP relations в unit DB текущего локального стенда, без product endpoints/публикации/миграций приложения. Все новые SQL-идентификаторы фиксированы программой; разрешена адресация только собственных OID текущего pg_temp namespace. Для двухсоединительной проверки lock/reservation нужны отдельно проверенные собственные постоянные тестовые отношения: TEMP одного соединения не объявляется видимой другому таблицей. Только синтетические данные; сериализованные payload не выводятся в логи. Ресурсы/версии не повышаются. Перед запуском — независимое ревью probe/DDL/cleanup и точного списка отношений. Очистка адресована только собственным созданным объектам; ошибка оставляет диагностируемый остаток вместо broad DROP.

| ID | Предусловие и действие | Проверяемый результат |
|---|---|---|
| SH07-QEXP-001 | Создать будущие shape-compatible TEMP таблицы revision/draft/pin/receipt/identity/budget и реальные индексы; пустое состояние | OID manifest, PG version/block_size, heap/index/TOAST/forks sizes и контроль отсутствия double count. Это калибровка схемы probe, не готовая product миграция |
| SH07-QEXP-002 | Реальные10000 immutable строк двух kind с непрерывной независимой историей; отдельные current/drafts/pins | COUNT=10000; admission10001 отклонён до записи; полного manifest/hash/count до/после без изменений. Нельзя заменить10000 строк одним fake counter |
| SH07-QEXP-003 | Последовательно добавить воспроизводимые плохо сжимаемые payload до byte occupancy75–90%, count<10000; измерять каждую порцию | >=201326592B предупреждение при достаточном резерве; одна допустимая новая запись проходит. Эта probe-проверка не считается UI/Apply прохождением acceptance/version-storage |
| SH07-QEXP-004 | Меньше10000 строк, measured остаток меньше prospective reservation; отдельно exact numeric boundaries | Отказ без snapshot/draft/receipt mutation и без вытеснения истории. Не требуется добиться ровно256МиБ на ФС; exact inequalities проверяются отдельно от actual relation experiments |
| SH07-QEXP-005 | Малый/средний/1МиБ UTF8, сжимаемый и плохо сжимаемый payload, индексы; расходы receipt/pins/refs; повторные обновления draft | Измерены actual pre/post/transient footprint и maximum observed growth по каждому shape. Нет обещания универсального коэффициента до анализа результатов |
| SH07-QEXP-006 | Вставка после savepoint с принудительным rollback; повторное admission и удаление допустимого historical cohort | Logical manifest возвращается, physical bloat измеряется и учитывается дальше; DELETE не выдаётся за возврат тех же физических байтов; current/draft/pinned/protected snapshots не входят в cleanup |
| SH07-QEXP-007 | Два независимых соединения пытаются забрать последний резерв под одним content domain | Один использует резерв, второй получает свежий actual state и отказ/конфликт; нет двойного расходования, частичной истории или потери первой записи |

Крупное наполнение делает только собственный probe, с проверкой доступного локального места и заранее ограниченным объёмом. Проверка75% требует настоящих relation bytes, не10000 копий одной хорошо сжимаемой строки. Payload генерируется порциями, не держится весь corpus в памяти. Освобождение probe-объектов после чтения результата не подменяет будущую ручную очистку истории продукта. Новых численных throttle/temp/бюджетов VPS этот документ не устанавливает.

Следующий небольшой реализуемый результат после ревью: pure quota-admission primitive с неизменяемыми входами actualSnapshotCount, actualRelationBytes, separatelyChargedBytes, reservationBytes и trusted reservationProfileVersion. При неизвестном/непроверенном профиле reservation — отказ. Раздельные результаты: допустимо, допустимо с75% предупреждением, count-full, byte-insufficient, measurement-invalid. Count10000 запрещает только положительное увеличение snapshotCount, а не само диагностическое чтение. Все целые неотрицательны, byte-суммы считаются точно; метод не делает DB-запись/очистку и не считает подписанный клиентом DTO измерением. Unit boundaries9999→10000/10000→10001,201326591→201326592,exact remaining/+1 и invalid/stale measurement проверяют арифметику. Реальная свежесть/lock scope, full snapshot/draft/receipt mutation и physical reservation проверяются отдельно integration/probe, прежде чем primitive сможет разрешать product Apply.

## SH07-AC — проверки после будущей реализации

SH07-AC-001 owner/employee/anonymous direct HTTP positive/negative; SH07-AC-002 HTML/URL/Asset/structural bypass и literalcontact roundtrip; SH07-AC-003 draft/prepare не публикуют и явный Apply меняет один блок; SH07-AC-004 independent history/new immutable ID/exact replay/conflicts; SH07-AC-005 old compatible/incompatible schema и истинный renderer trace; SH07-AC-006 budget count/bytes/warning/rollback через реальные handlers с RAM input; SH07-AC-007 refs/cleanup races и protected bases; SH07-AC-008 актуальные Header/Footer в публичном ETag и page restore не меняет их. Сопоставление — существующие shared-block-contracts/shared-component-restore/version-storage сценарии; они пока не исполнялись против product shared реализации.

## Граница текущего результата

Подготовлен контракт и ограниченный экспериментальный тест, описанный ниже. Нет shared моделей, миграций, API, sanitizer/renderer или product quota kernel. До полноценного shared кода остаются точный Asset-маркер/меню resolver и проверяемый DDL/accounting inventory; для полного допуска — реальные измерения и HTTP/UI/публичная композиция. Не заявлять готовность по факту создания документа.

## Ограниченный эксперимент после предварительного ревью

Независимое предварительное ревью разрешает только bounded TEMP PG experiment; не полный shared продукт. `app/page_editor/test_shared_quota_probe.py` содержит три ещё **не запущенных** теста:

- QEXP001 — шесть экспериментальных TEMP-отношений revision/draft/pin/receipt/identity/budget, их реальные primary/unique indexes и TOAST; pg_my_temp_schema/relpersistence/OID проверяются до измерения. Измерение каждого root включает table+indexes, forks и уже включённый TOAST показываются отдельно, без повторного сложения.
- QEXP002-count-only —10000 настоящих строк двух kind по5000 с последовательностями1–5000 и повторным независимым SHA256 length-framed manifest из actual rows. Это count/capacityshape evidence; нет имитации отказа10001 и нет заявления о продуктовой immutable защите или full QEXP002.
- QEXP006-insert-rollback-only — одна воспроизводимая плохо сжимаемая1МиБ ASCII-строка (base64 фиксированного PRNG corpus) вставляется после savepoint. До/во время/после измеряются actual PG bytes; rollback должен восстановить logical manifest и оставить наблюдаемый physical growth. Это не испытание ручной очистки/DELETE/общего storage admission.

Guard до DDL: ENV=test, settings=local_http, PostgreSQL, actual DB=estakada_foundation_unit, actual role=app_migrator. TEMP tables живут только внутри outer transaction с ON COMMIT DROP; после каждой группы проверяется исчезновение именно собственных OID. Измерительный предел — менее32МиБ **собственных TEMP relations**, а не новая квота продукта. Перед фиксированной записью требуется минимум16МиБ запаса к этому пределу, после — независимое actual измерение; одна вставка ограничена1МиБ, count corpus —10000 коротких строк. Это предохранитель конкретного конечного эксперимента, не доказанная универсальная reservation formula. Statement timeout30s/lock timeout5s задаются SET LOCAL только на соединении probe. Ресурсы контейнеров/серверные настройки не меняются.

SQL самого probe обращается только к собственным TEMP-отношениям и системным каталогам/измерителям. Это не обещание сохранить произвольные данные unit DB: стандартный lifecycle Django TransactionTestCase сбрасывает данные выделенной estakada_foundation_unit при teardown. Рабочая foundation DB не является базой этого прогона.

QEXP003 real75% fill, QEXP004 product byte refusal, QEXP005 полный overhead corpus и QEXP007 конкуренция **не выполняются** в этом инкременте; для наполнения до256МиБ нужен отдельный подробный локальный ресурсный план. Arithmetic/fake-admission primitive не добавлен: повторить константы в тесте и назвать это проверкой product отказа было бы ложным свидетельством. Файл теста передаётся на независимое ревью до запуска.

### SH-REV-001 — открыто до sanitizer/binding

Принятый положительный shared acceptance-ввод использует `<header><p>CANARY</p></header>`, а закрытая schema выше по точному макету не содержит свободного p внутри header. Перед sanitizer и подключением acceptance binding нужно явно адаптировать синтетический ввод к допустимому текстовому slot принятой структуры, сохранив независимый semantic canary oracle и проверку его actual public появления. Нельзя молча удалить p/canary, ослабить schema или объявить прежний сценарий пройденным. Это замечание P2 к будущей интеграции, не блокер трёх ограниченных TEMP-экспериментов.
