# DEV07-TP2 — результаты редактора HTML-таблиц

2026-11-01, D-358/D-359. **Выполнено в ограниченной локальной области:**5модельных групп,5HTTP/PG-тестов,5браузерных групп таблиц и5повторных браузерных групп прайса PASS. Независимое ревью проверенного объёма положительное. Полный DEV-07 остаётся в работе, около98%; этап8 около20%.

Основания: D-051/057/069, REQ-013/016, AC-DTL-004 и [контракт TP2-001–008](dev07-table-gui-checks.md). Браузерные группы не равны числу закрытых AC; частичные сценарии ниже не объявляются полными.

## Что работает

Новые простые таблицы имеют отдельную строку заголовков, две строки данных, две колонки и padding4px. В поддержанном ненестированном unitspan-варианте доступны текст/inline marks, отступ0–32px, добавление/удаление строк данных и колонок, Undo/Redo, Enter как hardBreak и Tab/ShiftTab между ячейками без неявного добавления строки. Header/scope/sections сохраняются, данные чужой строки/колонки не удаляются. Padding действует только на выбранную таблицу; header прозрачный, вторая общая строка затемнена, следующая прозрачна. Private DOM имеет одно tbody со всеми рядами, поэтому доверенный nth-child(even) не сбрасывается между head/body; wire экспортирует настоящие thead/tbody.

Перед stock capability и любым docChanged действуют aggregate geometry/actualPM/protected/canonical guards. Стандартные table plugins/shortcuts/fixTables/TableView/colwidth/colgroup выключены. Manual PM-команды создают один undoable content transaction; metadata-only history barrier без steps/selection не добавляет новую undo-запись или версию. Общий бюджет rich widgets20000virtual slots и существующий40000PM guard не меняют допустимость source HTML.

Сложные/nested/spanned/caption/неподдержанные format варианты сохраняются exactapprovedopaque с HTML-режимом. Если обычный допустимый HTML создаёт чрезмерное число PM-узлов, HTML-only выбирается до Editor/NodeViews. Нет тихой обрезки или ремонта содержимого. Новый контент по-прежнему проходит Check→явное принятие нормализации→Save и прежние права/current/draft/stage/receipt/CSRF проверки.

Выбранная цель padding хранится только в частном bookmark собственных контролов: same view/immutableDoc/table position+node identity/field. Посторонний фокус/выделение, изменение документа/источника, rebuild/destroy/window blur и попытка команды сбрасывают привязку. Общий commandSelection не ослаблен.

## Фактические проверки и snapshots

| Набор | Результат и область |
|---|---|
| Model |5PASS model-first.txt в network:none контейнере с approved PM: exact20000/+1/sum, nonunit/giant отказ без dense slots, отсутствие price caps, actualPM39102 разрешено/42102 отказано. Это geometry/model, не browser и не положительный HTML max |
| Первый framework |5/60.353с FAILED:4PASS/1ожидание400вместо409 в real-photo negative. Исходный протокол сохранён |
| Framework после D-359 |5PASS59.868с, framework-resume001.txt: настоящее сохранение/padding0/4/32/права/current-draft-stage, valid14kcell и15kli source, настоящий READY-файл, exact409/code/no proof при prefix displacement и успешный suffix с прежними refs/bytes |
| Финальные таблицы |5/5PASS native-fixed-history/host-report.json через Chromium/Nginx: insert/header/Unicode/marks/PG/reload; padding0/32/isolation/zebra/GC/invalid refusal; stale target crossfield+rebuild negatives; структурные операции/строгий Undo/Redo до и после typing/Enter/Tab; exactopaque/source fallback/права/identity |
| Регрессия TP1 |5/5PASS price-regression.txt; actual host-report в work/dev07-price-20261101/native-fixed-table-regression/: types/LF/21rows/page20/IDs/null/grants/revoke/lateCheck/newproof/maxamount/identity. Старые frozen price tools не изменялись |

Backend5PASS выполнялись на228files/run1398c86e-82ce-46fc-9a50-11cd1eaa2c6b, manifestfe4f26873adf250810dd6ea14699791533274040779fad1d46806e69d54d5184. Финальные оба browser набора —228files/run3c263320-b60d-433a-81d7-b1d3aafbab46, manifest5935165328a768bea77637910e193f78945032af52b6b9783f9710c63b669ad2. Независимая сверка доказала ровно3изменённых пути между ними: carrier-editor.mjs/editor.mjs/производный bundle; весь Python/QA42114b29…/helper8f4ce0ab… и runtime schema/profile прежние. Backend/model PASS не выдаются за повтор на финальном snapshot.

Финальный carrier eb088441ba817f121096cb9f066942b886b6b166f7b8808b96ab818b696b6f59; editor7304623db255ec16649f09233c33a182b3f1798a970d027dd126658a381ec622. Bundle1112419B/SHA8f99a52d3b140ff9dfd58a326540962cf3a4940a2fbedb8c5a3222936089bdd0/56inputs; прежние approved esbuild0.28.2/Tiptap3.32.2, builder1ГиБ/2CPU/network:none, external imports0.

## Ресурсные наблюдения

UI006 реально проверил giant/nested/14000textcell opaque и15000li HTML-only с настоящим Check/Save: liveNodes19 и79 соответственно, exact source сохранён. Whole group занял42.223с, включая несколько загрузок и запросов; это не длительность одного запроса и не универсальная SLA.

В table browser cohort наблюдались peak763699200B (~728.3МиБ) при cap1073741824B и app peak144924672B (~138.2МиБ) при cap805306368B. Это whole-cohort peaks, не отдельный worst case и не обещание для любого максимума. Лимиты и компоненты не повышались. CSP/storage/inline/pageErrors/external requests/stderr0. Два синтетических PNG1280/390 визуально просмотрены.

## Исправления и независимое ревью

TP2-REV001: final PM40000 guard после downgrade таблиц добавлен до Editor; native15kli подтвердил exact HTML-only без тяжёлого live DOM. TP2-REV002: потеря DOM selection при вводе padding доказана readonly diagnostic, bounded bookmark и оба stale-target negatives прошли. TP2-REV003: табличная команда объединялась с предыдущим вводом в history; fences и strictwholefacts before/aftertyping Undo/Redo прошли без sleep/ослабления oracle.

QA исправления не меняли продуктовые правила: prefix-photo negative теперь exact409/EDITOR_CAPABILITY_UNAVAILABLE/no proof вместо400; native marks используют существующую кнопку «Ж» вместо неподтверждённого Ctrl+B. Initial failed framework/native и diagnostic-only запуски сохранены и не названы PASS. Временная пауза после повторного guessed-path QA снята владельцем D-359 по DEV07-TP2-RESUME-001;228SHA до возобновления совпали. [Запись ревью](dev07-review.md).

## Границы и продолжение

Native размещение таблицы рядом с настоящим фото остаётся непокрытым: здесь есть real-photo framework/FS proof, не browser proof. Полная rich-widget MAX/resource матрица, complex/legacy/merge/split, все selected-source/terminal-stage варианты, полный version/public renderer и другие браузеры отдельно. Source max/node budget не подменяется virtual-slot числом;5groups не закрывают весь FMT004/DEV-07/140AC.

Общая responsive-проверка админки также не закрыта: full-page PNG при viewport390 имеет ширину406, как и до TP2 в TP1 screenshot. Это наблюдение прежнего общего layout требует отдельной диагностики; screenshot не объявляется доказательством отсутствия overflow всей страницы.

Следующий шаг этапа8 — оставшиеся сценарии подготовленного восстановления/terminal states, legacy/media/browser/resource матрицы. Этап9 не начинается. Старый сайт/VPS/production не затронуты, push не выполнялся.

Локальные свидетельства в ignored work/dev07-table-20261101/: before/pause manifests, model-first.txt, cohort-resume001.json/framework-resume001.txt, native-first/fixed-toolbar/fixed-padding-diagnostic/fixed-padding/fixed-history reports, source-delta-history.json, build-history-fix.txt, price-regression.txt. Окончательная сверка final-checks.json: active=false, работающих foundation/browser контейнеров нет, 228 host/frozen SHA без расхождений; миграции и профиль записи неизменны. Тома и постоянные ledgers сохранены.
