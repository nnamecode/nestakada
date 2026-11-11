# DEV-09L: bounded selection оставшегося контента

Дата: 2026-11-10. Основание: D-023, D-024, D-041, D-189, D-208, D-235, AT-508/AC-MIG-008 и завершённый DEV-09K D-801. Статус D-802: read-only selection завершён; product code, foundation и БД не затрагивались. Рекомендация ожидает решения владельца `DEV09L-Q001`.

## Проверенная граница

Сопоставлены только pinned `docs/analytics-route-map.csv`, `docs/analytics-route-evidence.csv` и семь уже принятых canonical packages DEV-09B/E/G/H/I/J/K. После них остаётся 58 MAP-строк:

- 26 `design_basis_present_verify_migration_before_launch`;
- 17 gallery albums без standalone design;
- 10 legacy pages без утверждённого дизайна;
- 2 service details с unresolved source/artifact price difference;
- по одной wash alias, gallery page2 subset и initial gallery redirect-chain строке.

В 26 design-basis строк входят 21 service detail, один тяжёлый service-section parent, actions, contacts, reviews и gallery catalog. Последние четыре относятся к отдельным продуктовым областям и зависят от media/embed/form/legal либо DEV-10, поэтому переносить их как побочный DEV-09 package нельзя.

## Почему следующего дешёвого service cohort нет

Под уже существующими service roots остаётся13 строк. Одиннадцать имеют одну/две исходные таблицы либо unresolved price/alias contract: MAP-015/016/038/058/068/069/073/083/088/089/115. Их нельзя объединить существующим exact text или leading-price contract без новых разновидностей interleaved/multi-table/surcharge/alias rules.

Только MAP-032 и MAP-041 имеют `source tables=0`, но и они не являются простым повтором DEV-09H:

- MAP-032 approved artifact содержит отдельную price table `1900`, `+350`, `+500` и note; existing amount contract не поддерживает signed surcharge и эту структуру;
- MAP-041 approved artifact содержит ordered list с четырьмя вложенными `h3` и paragraphs; existing closed block grammar не поддерживает headings внутри list items.

Кузовная ветвь состоит из тяжёлого MAP-010 parent и11 children. Даже пять безтабличных children нельзя создать раньше exact parent; сам parent содержит source table,17 paragraphs,23 links и media/gallery bindings. Делать новый сложный parent только ради нескольких простых leaves сейчас нерентабельно.

## Оценка вариантов

### Рекомендуется: остановить DEV-09 micro-cohorts

Не создавать восьмой canonical package ради одной-двух страниц и не расширять общий renderer новыми структурами до появления достаточного однородного набора. Перейти к DEV-10, где 17 оставшихся gallery albums, gallery catalog и обязательные по D-024 оригиналы образуют одну крупную целевую область. После DEV-10/media binding вернуться к одному объединённому remaining-content pass: bodywork, complex prices, actions/reviews/contacts и legacy pages уже по утверждённым зависимостям.

Плюсы: прекращается повторение package/writer/test/review overhead; не появляется универсальный HTML importer; media и gallery не моделируются дважды; безопасность sanitizer/closed DTO не ослабляется.

### Не рекомендуется: DEV-09L exact2

MAP-032+MAP-041 потребуют как минимум два новых content grammar contract (surcharge price table и nested heading list), отдельный package/writer/tests/review и затем всё равно оставят56 MAP. Это высокий процессный overhead при минимальном приросте готовности.

### Запрещённое упрощение

Нельзя импортировать artifact/source HTML целиком, разрешить произвольные tags/attributes, выполнять templates/JavaScript либо ослабить sanitizer. Это сократило бы код только ценой безопасности и нарушило бы D-023/D-041.

## Решение владельца

`DEV09L-Q001`: утвердить остановку последовательных DEV-09 micro-packages после D-801 и переход к bounded DEV-10 gallery implementation planning. DEV-09 остаётся частично выполненной областью; оставшиеся exact URL и тексты не отменяются, а группируются в более поздний объединённый pass после готовности gallery/media и связанных продуктовых областей.

После утверждения: сверить существующие DEV-10 требования и acceptance IDs → подготовить минимальный implementation plan без нового gallery runtime → independent plan review → отдельное разрешение product code.
