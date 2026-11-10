# DEV-09I: выбор ветви «Плановое ТО»

Дата: 2026-11-10. Основание: D-023, D-176/D-177, D-181/D-182, D-185–D-188, D-203/D-204, D-208, D-235 и завершённый DEV-09H D-773. Статус: read-only выбор завершён; exact9 предложен владельцу, но не утверждён. Product code не начат.

## Актуальный остаток

Preflight по-прежнему содержит 81 ready и 34 blocked строки. Четыре canonical package описывают 33 уникальные страницы, но MAP-002 исходно относится к blocker `READY-06_missing_catalog_design`; поэтому из ready-множества фактически закрыты 32 строки, а остаток равен 49:

- 43 `service_detail`;
- 2 `service_section_overview`;
- по одной actions, contacts, gallery-catalog и reviews странице.

Следующий пакет не должен смешивать прайсы, таблицы, формы, media transfer и разные runtime-контракты только ради большого числа страниц.

## Рекомендуемый bounded cohort exact9

Один атомарный hidden-пакет: новый section parent MAP-011 и восемь его простых дочерних страниц. Parent соответствует exact group position 1 в уже проверенном `app/content/dev09e_services_catalog.json`; дочерние name/URL/position также берутся только из этого существующего каталога.

| MAP | URL | Exact parent | Position |
|---|---|---|---:|
| MAP-011 | `/services/planovoe-to/` | MAP-002 | 1 |
| MAP-030 | `/services/planovoe-to/texnicheskoe-obsluzhivanie-to` | MAP-011 | 0 |
| MAP-035 | `/services/planovoe-to/zamena-masla-v-dvigatele` | MAP-011 | 1 |
| MAP-046 | `/services/planovoe-to/zamena-salonnogo-filtra` | MAP-011 | 3 |
| MAP-051 | `/services/planovoe-to/zamena-tormoznyix-kolodok` | MAP-011 | 4 |
| MAP-054 | `/services/planovoe-to/zamena-tormoznyix-diskov` | MAP-011 | 5 |
| MAP-060 | `/services/planovoe-to/zamena-texnichenskix-zhidkostej` | MAP-011 | 6 |
| MAP-063 | `/services/planovoe-to/zamena-svechej-zazhiganiya` | MAP-011 | 7 |
| MAP-074 | `/services/planovoe-to/zamena-shhyotok-stekloochistetelej` | MAP-011 | 8 |

Все девять строк имеют approved artifact, pinned source SHA, `tables=0` и один approved hero paragraph. В переносимых article-регионах точная проверка показала ноль `a/table/form/script/style/h3`, ноль числовых выражений с ₽/рублями и только code-owned hero image, который сейчас не переносится. Основной материал укладывается в уже существующую закрытую грамматику `h2/p/ul/li/strong`; presentation-only classes `body-types`, `note` и `closing` не становятся данными.

## Почему MAP-041 не входит

MAP-041 `/services/planovoe-to/zamena-filtrov` находится на sibling position 2, но его approved body использует вложенную структуру `ol > li > h3 + несколько p`. Для неё пришлось бы расширить package schema и renderer вложенными block-list items либо потерять семантику при уплощении. Обе цены несоразмерны одной странице, поэтому position 2 намеренно остаётся незаполненной до отдельного рентабельного cohort. Existing master catalog уже содержит ссылку на этот URL, но пока Route/Page отсутствуют direct URL закономерно даёт unknown404, а не hidden blank200. Публикация каталога/ветви до готовности связанных страниц остаётся отдельным будущим launch gate; текущий slice целиком hidden.

## Почему не выбран более крупный пакет

- MAP-032 содержит утверждённые цены в абзацах и требует отдельного price contract.
- Большинство оставшихся дочерних страниц MAP-012/MAP-014 содержит HTML-таблицы или цены; это отдельная price/table ветвь.
- Вторая section overview MAP-010 имеет body-table и не совпадает с no-price text contract.
- MAP-013 и зависимые страницы остаются blocked из-за нерешённого price mismatch.
- actions/reviews/contacts/gallery требуют media, embed, form/legal либо DEV-10 gates.

Exact9 даёт девять страниц за один package/review/guard цикл и переиспользует существующие writer, transaction, replay, rollback, concurrency, sanitizer и public-hidden границы. Универсальный importer, новая модель, миграция, dependency, API, command, cache, worker, scheduler или автоматический apply не нужны.

## Предлагаемая будущая граница

После явного owner approval подготовить minimal implementation plan и acceptance scenarios до кода:

- один bounded package exact9 с pinned MAP/RTE/source/artifact SHA;
- existing DEV-09E catalog — единственная authority для parent group и всех child tiles, включая намеренный sparse position 2;
- source-authoritative URL/title/H1/empty description и artifact-authoritative intro/body;
- existing closed safe text renderer без новой HTML-грамматики;
- одна UNIT-only transaction: all9 absent либо all9 exact replay; mixed/partial/collision отказываются без mutation;
- MAP-002 доказывается exact и не переписывается; MAP-011 создаётся вместе с восемью детьми;
- страницы hidden; prices, media, grants, publication, MAP-041 и persistent/production apply исключены.

## Gate

`DEV09I-Q001`: утвердить exact9 выше как следующий cohort. После ответа: minimal implementation plan → independent plan review → отдельное разрешение product code.
