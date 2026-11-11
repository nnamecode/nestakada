# DEV-09K: минимальный план переноса ветви «Диагностика»

Дата: 2026-11-10. Основание: D-023, D-189–D-199, D-208, D-235, AT-508/AC-MIG-008, selection `docs/dev09k-diagnostics-branch-selection.md` и owner approval `DEV09K-Q001` от 2026-11-10. Итог D-801: реализация разрешена D-797, выполнена и принята final independent review `APPROVED`, P1/P2/P3=0; focused5/full403/final checks PASS, foundation stopped. Persistent/production apply и публикация не выполнялись.

## Утверждённая граница exact10

Один hidden atomic cohort: MAP-013 parent под existing exact MAP-002 `/services/` и девять простых children. MAP-073 position 5 отсутствует намеренно.

| MAP | UUID | Parent / position | Name |
|---|---|---|---|
| MAP-013 | `2171f684-ccda-4402-b2be-f498b665f5b5` | MAP-002 / 3 | Диагностика |
| MAP-034 | `0a9ed67e-67ae-4854-a139-a7ede3972bde` | MAP-013 / 0 | Диагностирование авто перед приобретением |
| MAP-040 | `2b083fea-a676-46a8-8f0e-cff48d6b88de` | MAP-013 / 1 | Диагностика тормозной системы |
| MAP-059 | `42d0463d-e852-4679-86a5-b6302336d505` | MAP-013 / 2 | Диагностика подвески |
| MAP-062 | `b97f4f53-a14c-467f-a807-5026b0f6f1ad` | MAP-013 / 3 | Диагностика ходовой части |
| MAP-066 | `58507a9f-89ac-4546-bad9-957dd818f246` | MAP-013 / 4 | Диагностика электрооборудования |
| MAP-079 | `b03e4d41-246f-493d-af9c-89d39ae8bb6b` | MAP-013 / 6 | Диагностика системы охлаждения |
| MAP-084 | `e7d5b8ed-824c-49db-8fef-b78210d869e3` | MAP-013 / 7 | Диагностика АКПП/МКПП/РКПП/Вариатора |
| MAP-091 | `2bd689c2-5fba-48b8-9532-58dc1fbe281e` | MAP-013 / 8 | Диагностика трансмиссии |
| MAP-094 | `82292f8e-d5e7-47e4-b5d5-0fc8a4242e34` | MAP-013 / 9 | Диагностика двигателя |

Authority разделена: exact URL/type/source/artifact даёт pinned MAP/RTE; exact MAP-002 parent и group 3 name/href/items дают pinned `dev09e_services_catalog.json`; source даёт H1/title/empty description и только для MAP-013 exact исходную таблицу; approved artifact даёт intro и ordered body. Media, publication, grants, MAP-073, persistent/local/production apply не входят.

## Минимальная архитектурная граница

Новая модель, migration, dependency, API, management command, registry/loader, cache, worker, scheduler, frontend component или общий table-builder не создаются.

- Existing `tools/dev09-service-details.mjs` получает один literal diagnostics cohort и fixed actions `--emit-diagnostics`, `--selfcheck-diagnostics`, `--check-diagnostics`.
- Canonical package: `app/content/dev09k_diagnostics_branch.json`, schema `dev09-diagnostics-branch-v1`, cap 96 KiB.
- Existing `app/content/dev09_migration_apply.py` получает один exact reader/validator и `apply_diagnostics_branch()` рядом с существующими fixed entrypoints.
- Existing closed artifact parser и `_validate_service_text()` переиспользуются для intro/body всех десяти страниц.
- Только MAP-013 имеет обязательное поле `source_table`; children обязаны не иметь его. Это закрытая структура из двух literal headers и шести ordered rows двух видов (`category` или `service`), а не HTML.
- Один fixed renderer добавляет таблицу первой в `main_text`, затем existing rendered body. Он самостоятельно экранирует каждую строку, выдаёт только `table/thead/tbody/tr/th/td/strong`, `scope="col"` и `colspan="2"`, после чего требует `restricted_clean(output) == output`.
- Source `class/style/border/cellspacing/cellpadding` не копируются: они не несут содержания и расширяли бы разрешённые атрибуты. Никакой source/artifact HTML не хранится и не исполняется.

## Pinned authority и input boundary

Global inputs:

- `docs/analytics-route-map.csv`: 121,766 bytes, SHA-256 `c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8`;
- `docs/analytics-route-evidence.csv`: 203,030 bytes, SHA-256 `c3a8a395fb4ed55fef6027a58014ce5decaadda7c559870bf06247c2fbeb79bc`;
- `app/content/dev09e_services_catalog.json`: pinned existing package SHA-256 `beffdfdbacc6a24a71c68ee692f03be262f67745b8425e1ce9b204b8d15ca9e9`.

Selected inputs:

| MAP | Source bytes / SHA-256 | Artifact bytes / SHA-256 |
|---|---|---|
| MAP-013 | 34,426 / `a93aad4d34a86e7a0032efe58a311f85276b5dab97807eed201933e69503b3fa` | 21,024 / `88406065febf061a104918632d42932d1a8888b715f4789826610db252b6881c` |
| MAP-034 | 27,992 / `bd09fdd7368384a7bb621c696791bb703da597d09776ef66efacc7a2173a2a5b` | 15,991 / `9ec3b71afa1a0c72efa0fcff32d27680a235bff644a1c4f4c4d33c6a9120cbc2` |
| MAP-040 | 29,413 / `27fcb1ec73dc7fa79f14ae397a67b482445c98eb754448799485adc7ebd464dd` | 17,170 / `69fa573a8e3427449fd16e0dba3dbd8d43f340f2c92ecd0642e2d886f2cb2bce` |
| MAP-059 | 29,296 / `5bbcc3a6546df9f3c3e5bc52d5c2f1800a8fff43491b4083398141fcc4709810` | 16,567 / `9fef398f70695564dcd6a02b85acdb487c76b0badbf25385b1b70483951ed665` |
| MAP-062 | 28,682 / `564bb0892ef70a3a187229519461de45e84b30a3ac98697b46363655554c2b17` | 16,506 / `16c81199b19f9d2ce596418e8a47c7b6a402931e3ef44bc72db1fffdd10bf89d` |
| MAP-066 | 28,975 / `584f8b8ffc37a76019a85f87cdc4b84727835bc592eeb1703b84f3fe898ef8ce` | 16,573 / `63537bc6bf9e8a44f20208568d954cef3a80861e46b9569bb9b13be45e9b114b` |
| MAP-079 | 31,771 / `d2ffb1bad6bfefe6fbbca0712a7e41af1c55395e9422656239d2dbb1233efaa9` | 17,775 / `383656ce6a75d2db22b78296a7e2b709e4c1ef87c40d1e5f7d9bc755491818e9` |
| MAP-084 | 29,391 / `d0ad10cfdeb48effd164315761aeb5a8b9d6313ea9731593c9403517a33b0e7a` | 16,793 / `4ca495d14edafc8393efe03a466a916d8c6b8fc8f52dda979a6f1d949f0a17be` |
| MAP-091 | 28,766 / `8632de38c748a0daf10572ccd44c844930fa75f7592d6d6159ebe33ce5e32055` | 16,343 / `5f6326306877bccac977c7e7eeeccecedb25e1b3ad4db5b50eb7e035bc2e1f11` |
| MAP-094 | 30,257 / `aea3351d9d714312d457be6974ba3ee1cbfe144e4bc5b6e117d84c6beeecd3c1` | 17,746 / `1c6ed82f75fbb13b76150350a5b367ef82dec905953fb5db51c048e5e47afe55` |

Exact paths remain those in the selected MAP rows and `docs/dev09k-diagnostics-branch-selection.md`. Fixed caps: MAP 256 KiB, RTE 512 KiB, catalog package existing 20 KiB, each source/artifact 64 KiB, output package 96 KiB. Every path uses the existing literal allowlist, containment, regular-file/no-link-or-reparse, realpath equality, pre-read size, strict UTF-8 and pinned bytes/SHA checks. Host performs no filesystem write, network or child process; emit writes stdout only.

## Закрытый table и artifact contract

MAP-013 source must contain exactly one first table in `.c-content` before its first paragraph. Accepted semantic table is exactly:

- headers `Класс авто, наименование работ` / `Цена, руб.` with `scope="col"`;
- category `ВАЗ`, then service `Диагностика ЭСУД и удаление ошибок` / `от 1500`;
- category `Иномарки среднего класса`, then the same service / `от 1500`;
- category `Внедорожники`, then the same service / `от 1500`;
- category cells span exactly two columns and retain `strong` semantics.

Missing, extra, reordered or altered header/row/category/service/price/colspan/table position fails. Nested links/forms/scripts/styles/images, entities used to disguise content, controls and unpaired surrogates fail. The parser does not accept arbitrary tables or numeric variants and does not infer prices.

Each approved artifact must contain exactly one `.article`, one `.article-hero-copy > p` and the frozen closed body. `H/P/U` mean `h2`/normalized paragraph/`ul`; `div.closing > p` normalizes to `P` only after its exact position is proved:

| MAP | Normalized ordered signature | `div.closing` positions |
|---|---|---|
| MAP-013 | `P,P,H,P,P,H,P,P` | `[7]` |
| MAP-034 | `H,P,P` | `[2]` |
| MAP-040 | `P,H,U,P,P` | `[4]` |
| MAP-059 | `H,P,P,P,P` | `[4]` |
| MAP-062 | `H,U,P,P` | `[3]` |
| MAP-066 | `H,P,P,P` | `[3]` |
| MAP-079 | `P,H,P,P,P,P,P` | `[6]` |
| MAP-084 | `P,H,U,P` | `[3]` |
| MAP-091 | `H,P,P,P` | `[3]` |
| MAP-094 | `H,U,P,U,P,H,U,P,P` | `[8]` |

MAP-013 body boundary is exact: the eight blocks above end with `div.closing`, immediately followed by exactly one `<nav class="service-grid" aria-label="Услуги раздела Диагностика">`; the nav and everything after it are proof-only and never become `main_text`. The nav contains exactly ten ordered tiles numbered `01`–`10`. Each artifact `href` must equal literal origin `https://estakada-service.ru` plus the corresponding exact catalog group3 href. Catalog remains the sole authority for package page names. Artifact labels are proved separately:

| Position | Canonical catalog/page name | Exact artifact tile label |
|---:|---|---|
| 0 | Диагностирование авто перед приобретением | Диагностика перед приобретением |
| 1 | Диагностика тормозной системы | Диагностика тормозной системы |
| 2 | Диагностика подвески | Диагностика подвески |
| 3 | Диагностика ходовой части | Диагностика ходовой части |
| 4 | Диагностика электрооборудования | Диагностика электрооборудования |
| 5 | Диагностика кондиционера\|Печки | Диагностика кондиционера и печки |
| 6 | Диагностика системы охлаждения | Диагностика системы охлаждения |
| 7 | Диагностика АКПП/МКПП/РКПП/Вариатора | Диагностика коробки передач |
| 8 | Диагностика трансмиссии | Диагностика трансмиссии |
| 9 | Диагностика двигателя | Диагностика двигателя |

Only the three literal label deltas at positions 0/5/7 are accepted; they do not rename pages and are not imported. All nine child bodies have no table/link/price expression. Artifact body remains limited to the existing closed `h2/p/ul/li/strong/div.closing` grammar. Package comparison freezes normalized ordered blocks, exact list items, wrappers/classes and exact text.

## Package and writer contract

Package is canonical UTF-8/LF/no CR, duplicate-key rejecting, exact10, fixed UUID/URL/parent/position/name/H1/title/empty description/hidden/source/artifact/intro/blocks. MAP-013 alone also contains exact `source_table`. Full package SHA and ordered pages SHA are pinned after reviewed generation.

`apply_diagnostics_branch()` stays default-off and accepts only database `estakada_foundation_unit`, user `app_migrator` and one active owner `nesadmin`. Actual database identity is the first SQL inside one transaction; content→auth lock order is unchanged.

Under locks it reads the same validated catalog package, proves exact hidden MAP-002 aggregate and exact group 3. MAP-002 is never rewritten. Parent is created before children inside the same transaction. Only two cohort states are valid:

- all ten absent → exhaustive UUID/route/sibling-position/reservation/audit collision preflight, then atomic create of MAP-013 and all nine children;
- all ten complete and exact → zero-write replay.

Any mixed/partial state, collision, catalog/group/table/text/layout/audit/reservation drift, late synthetic failure or unexpected related row fails with full state unchanged. Two concurrent calls yield one create and one exact replay. All pages remain hidden.

## Приёмочные сценарии до кода

- `MIGK-001`: host pins exact ordered global/source/artifact paths, bytes and SHA above plus exact MAP/RTE rows; catalog supplies exact MAP-002/group3 binding; source supplies only exact H1/title/empty description and MAP-013 table.
- `MIGK-002`: exact10 identities, hierarchy and positions are frozen; position5/MAP-073 and every other page are absent. Duplicate UUID/URL/position, wrong parent/type/name/href/order fail closed.
- `MIGK-003`: MAP-013 source proves exactly one leading table before first content paragraph, exact two headers and exact six ordered rows with three category `colspan=2`/strong cells and three literal `от 1500` service rows. Missing/extra/reordered/changed structure or values fail.
- `MIGK-004`: all ten artifacts prove exact one intro, the per-MAP signatures/closing positions above, exact list items and frozen text. MAP-013 proves the body-before-nav boundary and exact ten ordered tile numbers/absolute hrefs/labels, while catalog alone supplies page names; only literal label deltas at positions0/5/7 are accepted. Children prove no table/link/price expression. Missing/extra/reordered block/item/wrapper/class/body/nav/tile, changed href/label/number and forbidden tags/attributes/entities/controls fail with labelled errors.
- `MIGK-005`: paths are exact contained regular non-links with fixed pre-read caps, strict UTF-8 and pinned SHA. Escape/link/reparse/nonregular/oversize/short-read/invalid UTF-8 and exact-cap boundaries are exercised; host writes/network/child-process count is zero.
- `MIGK-006`: canonical package is exact10 and only MAP-013 has the closed `source_table`; unknown keys/types/counts, HTML strings, package/pages drift and duplicate JSON keys fail.
- `MIGK-007`: renderer emits escaped intro/body and for MAP-013 exactly one safe table before approved body. Sanitizer equality is mandatory; table text containing markup/entity/control cannot reach stored or public output. No arbitrary Django template, Python or JavaScript execution is possible.
- `MIGK-008`: disabled flag, non-test environment, wrong configured DB/user, wrong actual SQL identity and missing/inactive/non-unique `nesadmin` fail before package locks/mutation.
- `MIGK-009`: exact hidden MAP-002 and exact catalog group3 permit create and are never rewritten. Parent/group/name/href/order drift refuses with full state unchanged.
- `MIGK-010`: all-absent creates exactly ten complete hidden aggregates and exact PRIMARY routes/revision/state/draft/pin/metadata/reservations/audit. No media, grants, Stable/manual revisions, publication or unrelated rows appear.
- `MIGK-011`: exact replay writes zero rows. Mixed cohort, UUID/route/position collision, altered table/text/layout or synthetic tenth-create failure rolls back an exhaustive before/after snapshot. Two real concurrent calls yield one create plus one replay.
- `MIGK-012`: writer pages remain hidden and exact URLs expose no imported text publicly. A separate isolated test-only published ancestor fixture proves MAP-013 HTTP order `intro → main_text(table first, then body)`, exact safe table semantics/escaping, and representative child body; it does not call writer or authorize publication. Existing DEV-09H/I/J public regressions stay green.
- `MIGK-013`: foundation copy/manifest adds only exact `content/dev09k_diagnostics_branch.json`; static oracle requires exactly seven explicit migration package names, no wildcard. Focused host/Python/public tests, full guard, Django check, no migration drift, manifest SHA and diff checks pass; foundation stops. Persistent/production apply remains zero.

## Явно исключено

MAP-073 and its prices, all other remaining pages, media/hero files/gallery, publication, grants, redirects, new SEO copy, editing UI, generic table import/rendering and any live/persistent apply. Их нельзя добавлять «заодно».

## Порядок реализации после отдельного разрешения

1. Extend existing host with one literal exact10 oracle; generate and review one canonical package.
2. Add failing focused tests for exact inputs/package/table/renderer/hierarchy/create/replay/rollback/concurrency/public boundary and security negatives.
3. Add minimal reader, closed table renderer and one fixed atomic entrypoint; extend exact-seven foundation allowlist.
4. Run focused tests, full guard and final checks; then independent code review before marking DEV-09K complete.
