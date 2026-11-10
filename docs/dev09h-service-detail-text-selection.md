# DEV-09H: выбор текстового среза внутренних услуг

Дата: 2026-11-10. Основание: D-023, D-176/D-177, D-181/D-182, D-185–D-188, D-203/D-204, D-208, D-235 и завершённый DEV-09G D-766. Статус: exact10 утверждён владельцем D-768; implementation plan записан, product code не начат.

## Актуальный остаток

Прямой пересчёт `docs/analytics-route-map.csv` против трёх canonical packages DEV-09B/09E/09G даёт 23 уже описанные package-страницы и 59 оставшихся строк в состоянии `design_basis_present_verify_migration_before_launch`. Среди остатка:

- 53 `service_detail` с общим target template, но разными текстами, прайсами и media bindings;
- 2 `service_section_overview`;
- по одной actions, reviews, contacts и gallery-catalog странице.

Перенос всех 53 service-detail одним пакетом отклонён: он смешал бы no-price тексты, HTML-таблицы, цены в абзацах, ещё не созданных родителей и отдельные media/content contracts.

## Рекомендуемый bounded cohort

Один пакет из 10 hidden `service_detail` страниц без прайса и без media transfer:

| MAP | URL | Exact parent | Position |
|---|---|---|---:|
| MAP-064 | `/services/remont/remont-elektrooborudovaniya` | MAP-012 | 4 |
| MAP-067 | `/services/remont/zamena-remnya-grm` | MAP-012 | 5 |
| MAP-080 | `/services/remont/remont-akppmkpprkppvariatora` | MAP-012 | 9 |
| MAP-085 | `/services/remont/remont-transmissii` | MAP-012 | 10 |
| MAP-098 | `/services/remont/remont-startera` | MAP-012 | 13 |
| MAP-101 | `/services/remont/remont-vyixlopnoj-sistemyi` | MAP-012 | 14 |
| MAP-104 | `/services/remont/remont-sistemyi-zazhiganiya` | MAP-012 | 15 |
| MAP-107 | `/services/remont/remont-kommercheskogo-negabaritnogo` | MAP-012 | 16 |
| MAP-047 | `/services/drugie-uslugi/evakuacziya-avtomobilya` | MAP-014 | 2 |
| MAP-050 | `/services/drugie-uslugi/obrabotka-porogov` | MAP-014 | 3 |

Positions — нулевые sibling positions из уже проверенного DEV-09G catalog order. Оба parent aggregate уже имеют exact closed package и writer proof.

Все 10 строк имеют approved artifacts, source SHA, `tables=0`, один approved hero paragraph и основной материал без ссылок, изображений, таблиц, script/style. После исключения code-owned hero/media и presentation-only `.closing` wrappers содержимое использует только `h2`, `p`, `ul`, `ol`, `li`, `strong`. Это один конечный contract, а не универсальный HTML importer.

## Почему не включены соседние страницы

- MAP-032 содержит утверждённые цены 1 900/350/500 ₽ в абзацах и требует отдельного price contract, несмотря на `tables=0`.
- MAP-015/016/083/115 и многие repair pages содержат таблицы; их нельзя притворно считать plain text.
- MAP-010/011 — section overview с отдельным hero/navigation contract; MAP-013 остаётся blocker из-за несовпадения price.
- Дочерние страницы MAP-010/011/013 не должны создаваться до exact parent proof.
- actions/reviews/contacts/gallery требуют banner/video/form/legal/gallery-media gates.

## Рекомендуемая будущая реализация

После явного owner approval подготовить отдельный minimal implementation plan и acceptance scenarios до кода:

- один bounded canonical package exact10 с pinned MAP/RTE/source/artifact SHA;
- approved hero paragraph преобразуется code-owned renderer в безопасный `intro_text`; main blocks — в `main_text`;
- closed structured blocks допускают только heading, paragraph, unordered/ordered list и явно ограниченный strong segment; renderer сам экранирует текст и требует sanitizer equality;
- artifact HTML не копируется и не исполняется, class/style/attributes/script/template/Python/JavaScript в package не хранятся;
- existing default-off UNIT-only identity, content→auth locks, exact two-parent proof, one transaction, all-absent/all-exact replay, rollback and concurrency переиспользуются без registry/generic importer;
- pages остаются hidden; hero images, shared works, media usages, prices, children, grants и publication не создаются;
- no model/migration/dependency/API/management command/cache/worker/scheduler/persistent apply/live access.

Это уменьшает количество повторных plan/review/guard циклов по сравнению с переносом одной страницы, но сохраняет однородную и проверяемую границу.

## Gate

Требуется явное утверждение владельцем cohort exact10. Затем: minimal implementation plan → independent plan review → отдельное разрешение product code.
