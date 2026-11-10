# DEV-09J: выбор первого прайсового cohort

Дата: 2026-11-10. Основание: D-023, D-172–D-174, D-180, D-184, D-208, D-235 и завершённый DEV-09I D-781. Статус: read-only profitability selection завершён; exact5 предложен владельцу, но не утверждён. Product code не начат.

## Актуальный остаток

После canonical packages DEV-09B/E/G/H/I остаётся40 preflight-ready строк:

- 35 `service_detail`;
- 1 `service_section_overview`;
- по одной actions, contacts, gallery-catalog и reviews странице.

Простые no-price страницы диагностики пока зависят от blocked MAP-013; кузовные — от ещё не созданного MAP-010. Под уже существующими MAP-012/MAP-014 остаются страницы с ценами, но они неоднородны по числу таблиц и положению таблицы внутри текста.

## Рекомендуемый bounded cohort exact5

Пять hidden `service_detail` страниц под exact MAP-012 `/services/remont/`:

| MAP | URL | Position | Price rows | Approved decision |
|---|---|---:|---:|---|
| MAP-042 | `/services/remont/remont-tormoznoj-sistemyi` | 0 | 11 | D-172 |
| MAP-052 | `/services/remont/remont-podveski` | 1 | 8 | D-173 |
| MAP-055 | `/services/remont/remont-xodovoj-chasti` | 2 | 21 | D-174 |
| MAP-075 | `/services/remont/remont-sistemyi-oxlazhdeniya` | 8 | 5 | D-180 |
| MAP-095 | `/services/remont/remont-generatora` | 12 | 1 | D-184 |

Positions, names and URLs are exact DEV-09G MAP-012 tile authority. Every page has approved source/artifact and exactly one rectangular two-column table at the start of the material, followed only by the already supported closed text grammar. Direct inspection proves:

- exact headers `Услуга` / `Цена, руб.`;
- exact row counts11/8/21/5/1, total46;
- table cells contain no nested tags;
- article regions contain no links, forms, scripts, styles, h3 or entities;
- media is only existing deferred hero/works material and does not enter this slice.

The existing version schema already has one bounded `price` matrix; public rendering, exact Decimal string validation, escaping and amount formatting are already implemented and tested. No new price model or table renderer is needed. Existing layout is reordered with existing block kinds to `intro_text → price → main_text`, preserving the approved artifact order without splitting `main_text`.

Price cell rule is closed and lossless:

- exact `от N` → existing amount cell `{amount:N, from:true}`;
- exact `N` → amount cell `{amount:N, from:false}`;
- MAP-055 exact compound values `от 3500 за 1 шт.` and `1500 за 1 шт.` remain text cells; suffix semantics are not discarded;
- any other form fails host validation rather than being guessed.

## Почему не включены соседние страницы

- MAP-015 шиномонтаж has three approved tables with 8/9 price columns; current page schema has one price matrix, and merging would invent grouping semantics.
- MAP-089 ремонт двигателя has two separate tables; same problem.
- MAP-068 and MAP-069 place the table between text blocks; one current `main_text` cannot preserve that order without a new content split.
- MAP-083 places the table before a final closing paragraph, also requiring interleaving.
- MAP-016 duplicates сход-развал outside approved MAP-014 tiles and lacks exact DEV-09G child authority.
- MAP-032 has prices embedded in paragraphs and requires a different exact contract.
- MAP-010 and its children depend on an uncreated section parent and mix no-table/table pages.
- MAP-013 diagnostics parent remains blocked by price mismatch; its otherwise simple children cannot be imported first.
- MAP-041 has the separately deferred nested `ol > li > h3 + p` grammar.
- actions/reviews/contacts/gallery remain behind media/embed/form/legal/DEV-10 gates.

## Предлагаемая будущая граница

После explicit owner approval подготовить minimal implementation plan and acceptance scenarios before code:

- extend the existing bounded service-text host validator with one literal exact5 cohort; no duplicate tool or registry;
- one canonical package with pinned MAP/RTE/DEV-09G/source/artifact facts, exact body blocks and exact46-row price matrices;
- reuse the existing closed text renderer and page `price` schema/public projection;
- exact MAP-012 aggregate and tile bindings are immutable prerequisites;
- all5 absent creates atomically, all5 exact replays without writes, mixed/collisions/late failure/concurrency fail safely;
- pages remain hidden; media, publication, grants, other price formats and persistent/production apply are excluded;
- no model/migration/dependency/API/command/cache/worker/scheduler/new runtime layer.

## Gate

`DEV09J-Q001`: утвердить exact5 above as next cohort. Then: minimal implementation plan → independent plan review → separate product-code approval.
