# DEV-09K: выбор ветви «Диагностика»

Дата: 2026-11-10. Основание: D-023, D-189, D-208, D-235, AT-508/AC-MIG-008 и завершённый DEV-09J D-792. Статус: bounded read-only selection завершён; exact10 и точное размещение исходного прайса предложены владельцу, но не утверждены. Product code не начат.

## Остаток после DEV-09J

Шесть canonical migration packages описывают 48 уникальных MAP-страниц. В ready-множестве остаётся35 строк:

- 30 `service_detail`;
- 1 `service_section_overview`;
- по одной actions, contacts, gallery-catalog и reviews странице.

Под существующими MAP-012/MAP-014 остались неоднородные multi-table/interleaved/paragraph-price страницы; MAP-010 требует сложного parent с многоколоночным прайсом и даёт лишь несколько простых детей. Actions/reviews/contacts/gallery зависят от media/embed/form/legal. Продолжать по одной сложной странице нерентабельно.

## Почему MAP-013 теперь можно разблокировать без новой схемы

MAP-013 `/services/diagnostika/` имеет точный source `work/site-audit/crawl/f06dce9c7fc86e83ee4f.html`, SHA256 `a93aad4d34a86e7a0032efe58a311f85276b5dab97807eed201933e69503b3fa`, и approved artifact `work/diagnostika.html`. Его `review_state=content_difference_price_not_in_v3_requires_resolution` возник не из-за неизвестного содержания: approved artifact сохранил текст, hero и десять tiles, но пропустил исходную таблицу перед текстом.

Source lines257–287 содержат ровно одну таблицу в начале `.c-content`:

- headers `Класс авто, наименование работ` / `Цена, руб.`;
- category row `ВАЗ`, затем `Диагностика ЭСУД и удаление ошибок` / `от 1500`;
- category row `Иномарки среднего класса`, затем та же услуга / `от 1500`;
- category row `Внедорожники`, затем та же услуга / `от 1500`.

Existing `main_text` и editor/public sanitizer уже поддерживают `table/thead/tbody/tr/th/td/strong`, `scope` и `colspan`; public CSS уже даёт bounded horizontal overflow. Поэтому cheapest lossless representation — не расширять typed `price` DTO, а code-owned renderer-ом поместить точную безопасную таблицу первой в `main_text`, непосредственно после hero/`intro_text` и перед approved artifact body. Так сохраняются исходный порядок, headers, все шесть body rows, `colspan=2`, категории, услуга и три literal `от 1500`. Никакой произвольный source HTML не исполняется и не становится template.

## Рекомендуемый exact10 cohort

Один hidden atomic package: MAP-013 parent плюс девять простых children из exact DEV-09E group3. Position5 намеренно отсутствует.

| MAP | URL | Position | Contract |
|---|---|---:|---|
| MAP-013 | `/services/diagnostika/` | group3 | exact source table + approved safe text |
| MAP-034 | `/services/diagnostika/diagnostirovanie-avto-pered-priobreteniem` | 0 | closed text |
| MAP-040 | `/services/diagnostika/diagnostika-tormoznoj-sistemyi` | 1 | closed text |
| MAP-059 | `/services/diagnostika/diagnostika-podveski` | 2 | closed text |
| MAP-062 | `/services/diagnostika/diagnostika-xodovoj-chasti` | 3 | closed text |
| MAP-066 | `/services/diagnostika/diagnostika-elektrooborudovaniya` | 4 | closed text |
| MAP-079 | `/services/diagnostika/diagnostika-sistemyi-oxlazhdeniya` | 6 | closed text |
| MAP-084 | `/services/diagnostika/diagnostika-akppmkpprkppvariatora` | 7 | closed text |
| MAP-091 | `/services/diagnostika/diagnostika-transmissii` | 8 | closed text |
| MAP-094 | `/services/diagnostika/diagnostika-dvigatelya` | 9 | closed text |

All nine child artifacts have zero tables, links and price expressions in the transferable article body. Their exact body tags are limited to the already supported `h2/p/ul/li/strong` plus approved closing paragraph. Media remains deferred.

MAP-073 `/services/diagnostika/diagnostika-kondiczionerapechki` at position5 stays excluded: its own source prices `1900` and `от 3000` are absent from the artifact and require a separate placement decision. The parent and all pages remain hidden, so its absent direct URL stays unknown404 and there is no partial public launch.

## Proposed implementation boundary after approval

- extend existing `tools/dev09-service-details.mjs`; no new importer/registry;
- one canonical exact10 package with pinned MAP/RTE/catalog/source/artifact facts;
- source-authoritative MAP-013 table and approved artifact-authoritative intro/body;
- existing safe text renderer plus one fixed closed table renderer; no arbitrary HTML/template execution;
- exact DEV-09E MAP-002/group3 authority, parent-first transaction, all10 absent create or all10 exact zero-write replay;
- mixed/collisions/late failure/concurrency fail with full rollback;
- pages hidden; media, publication, grants, MAP-073, persistent/production apply excluded;
- no model, migration, dependency, API, cache, worker, scheduler or new runtime layer.

## Gate

`DEV09K-Q001`: утвердить exact10 выше и точное placement rule для MAP-013: исходная таблица первой в `main_text`, после hero/intro и перед approved body, с literal headers/rows/`colspan`/`от 1500`. После ответа: minimal implementation plan with acceptance scenarios → independent plan review → separate owner approval product code.
