# DEV-09F: выбор следующего ограниченного service-среза

Дата: 2026-11-10. Основание: D-023, D-171, D-200, D-208, D-235, D-759 и read-only inventory D-760/D-761. Статус: рекомендация до product code; требуется явное утверждение владельца.

## Результат инвентаризации

После DEV-09E остаётся 61 route в exact ready-state. Из них 57 относятся к service-страницам и имеют media bindings. Перенос всех 57 одним пакетом нерентабелен: смешиваются hero, текст, цены/таблицы, media, разные page kinds и три ещё не закрытых blocker route.

Наиболее узкий целостный следующий срез:

- MAP-012 `/services/remont/`, `service_catalog`, parent MAP-002, intended sibling position 2;
- MAP-014 `/services/drugie-uslugi/`, `service_catalog`, parent MAP-002, intended sibling position 4.

Обе строки имеют state `design_basis_present_verify_migration_before_launch`, точные source SHA совпадают локальным snapshot, target template `service_catalog_tiles_no_hero`, утверждённые owner artifacts `work/remont.html` и `work/drugie-uslugi.html`, tables=0 и отсутствие отдельного hero binding. Их media bindings состоят только из уже общего Header/Footer/works cohort; в hidden migration slice media не переносится и publication не выполняется.

## Почему не остальные ветки

- MAP-010 «Кузовной ремонт» и MAP-011 «Плановое ТО» — section overview с hero, текстом и navigation; MAP-010 также содержит таблицу.
- MAP-013 «Диагностика» имеет нерешённый blocker `content_difference_price_not_in_v3_requires_resolution` и не может входить в ready-package.
- Детальные service pages требуют hero/content и optional price/media; их нельзя смешивать с простым root-catalog slice.
- Actions/reviews/contacts/gallery требуют соответственно banner media, external video policy, media/form/legal gates и DEV-10/album designs.

## Точный утверждённый контент

MAP-012 использует 17 плиток из `work/remont.html` в утверждённом порядке. URL совпадают с master catalog. Две подписи намеренно отличаются от старого master-source и сохраняются по D-171:

- position 7: `Климат-контроль, Печка`;
- position 10: `АКПП/МКПП/РКПП/Вариатора`.

MAP-014 использует ровно пять плиток из `work/drugie-uslugi.html` в утверждённом порядке. `Автомойка` `/services/drugie-uslugi/avtomojka` намеренно исключена по D-200 и остаётся отдельной корневой страницей `/services/avtomojka` в будущем срезе.

Исходные WhatsApp/устаревшие вводные тексты, искусственный hero и повторный heading не переносятся: это уже утверждено D-171/D-200 и не является новым content rewrite.

## Рекомендуемая граница будущего плана

После явного owner approval подготовить отдельный implementation plan и `MIGF-xxx` до кода:

- один малый closed package с двумя hidden `service_catalog` pages;
- exact parent MAP-002, intended positions 2/4 и exact legacy PRIMARY routes;
- closed tile data only; renderer сам строит безопасные `ul/li/a/strong` из escaped text и exact internal paths, затем требует sanitizer equality;
- narrow reuse существующих UNIT-only DB/role/lock/transaction/replay/rollback/concurrency gates;
- kind-scoped catalog class/CSS с 4/3/1 layout, visible focus и без fixed height/ellipsis;
- production pages остаются hidden; no grants, children, media transfer, publication, persistent apply или live access;
- no model/migration/dependency/universal parser/ETL/API/command/cache/worker/scheduler.

Отдельно доказать standalone exact MAP-002 parent без требования article package/other service roots. Старый article writer и DEV-09E catalog replay остаются обязательной regression.

## Gate

Это выбор среза, не разрешение реализации. Следующий переход: явное утверждение владельцем MAP-012+MAP-014 → minimal implementation plan с acceptance scenarios → independent plan review → отдельное разрешение product code.
