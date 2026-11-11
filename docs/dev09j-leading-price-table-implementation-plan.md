# DEV-09J: минимальный план переноса пяти страниц с начальным прайсом

Дата: 2026-11-10. Основание: D-023, D-172–D-174, D-180, D-184, D-208, D-235, D-781/D-782, selection `docs/dev09j-leading-price-table-selection.md` и owner approval D-784. Статус D-787: repeat independent plan review `APPROVED`, P1/P2/P3=0; product code не начат, требуется отдельное owner approval реализации.

## Утверждённая граница exact5

Все страницы — hidden `service_detail` под уже существующим exact MAP-012 `/services/remont/`:

| MAP | UUID | Position | Name | Price rows |
|---|---|---:|---|---:|
| MAP-042 | `c176ea0e-e37c-4f7b-9e7c-3f4ca73608cb` | 0 | Ремонт тормозной системы | 11 |
| MAP-052 | `38a4be87-aae5-4776-a32d-10407f70eac9` | 1 | Ремонт подвески | 8 |
| MAP-055 | `1078747a-4264-4ba6-9980-b981b4e52e8c` | 2 | Ремонт ходовой части | 21 |
| MAP-075 | `de93552c-7bba-4385-b1ec-870435157579` | 8 | Ремонт системы охлаждения | 5 |
| MAP-095 | `c46751ca-6822-4bdb-b5f2-7c5d14f9132f` | 12 | Ремонт генератора | 1 |

Authority разделена явно: exact URL и route identity даёт pinned MAP/RTE; exact parent/name/position binding даёт MAP-012 в pinned `app/content/dev09g_service_roots.json`; source supplies exact H1/title/empty description; approved artifact supplies one intro paragraph, one leading table and ordered main body. Total exact price rows: 46.

Media, hero files, works gallery, publication, grants, other pages and other table formats не входят. Persistent/local/production apply не выполняется.

## Минимальная архитектурная граница

Новая модель, таблица, migration, dependency, runtime registry/loader, API, management command, cache, worker, scheduler или frontend component не создаются.

- `tools/dev09-service-details.mjs` получает только третий literal cohort и fixed actions `--emit-leading-prices`, `--selfcheck-leading-prices`, `--check-leading-prices`. Existing DEV-09H/I actions and results remain unchanged.
- Canonical package: `app/content/dev09j_leading_price_details.json`, schema `dev09-leading-price-details-v1`, cap 64 KiB.
- `app/content/dev09_migration_apply.py` получает один exact reader/validator и `apply_leading_price_details()` рядом с существующими fixed entrypoints.
- Existing `_validate_service_text()` and safe text renderer are reused. A narrow price builder converts closed package rows into the existing page-version `price` matrix; no generic importer/dispatch/plugin interface is introduced.
- Existing `initial_snapshot()` block IDs are reused, but layout order is exactly `intro_text → price → main_text` instead of the default `intro_text → main_text → price` so the public order matches the approved artifact.
- Price column/row UUIDs are deterministic standard UUIDv5 values derived from the fixed page UUID and literal `price-column:0` / `price-row:<zero-based index>`. They are code-owned presentation identities, not a new stored registry or authority.

## Pinned authority и input boundary

Global inputs:

- `docs/analytics-route-map.csv`: 121,766 bytes, SHA-256 `c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8`;
- `docs/analytics-route-evidence.csv`: 203,030 bytes, SHA-256 `c3a8a395fb4ed55fef6027a58014ce5decaadda7c559870bf06247c2fbeb79bc`;
- `app/content/dev09g_service_roots.json`: 5,147 bytes, SHA-256 `956c35fb5697acb23b039a980d1915228bd1100f1884ebece3fcd909ace365db`.

Exact selected inputs:

| MAP | Source path | Source bytes / SHA-256 | Artifact path | Artifact bytes / SHA-256 |
|---|---|---|---|---|
| MAP-042 | `work/site-audit/crawl/92c944163a138dab06b6.html` | 36,877 / `52832b5b069df61c60ba8800fda548851b2c8f3f0b1189bacab895ae28187c5e` | `work/remont-tormoznoj-sistemyi.html` | 20,339 / `45544cb2edf59be05f5bb051b3806d4593ed348f27618e4a067d7a58de549e05` |
| MAP-052 | `work/site-audit/crawl/5e61de142f74adfee68e.html` | 35,745 / `625d9a7ba7b25d6c286a1e4d7dc8896a273b152b46e1a7c40d0bb67f7e262012` | `work/remont-podveski.html` | 19,552 / `2ad8187a24dd059562d9c8ea509610a0ed4ab6bd46c986754b44605f09e57efa` |
| MAP-055 | `work/site-audit/crawl/3a8a0966147a34590630.html` | 37,209 / `a59f3b27eff7f07add2d1b0c3664d2b8d6d5a30d1dd2af164a54ffc7c9195ce2` | `work/remont-xodovoj-chasti.html` | 19,358 / `cfd3f7fe6015e3fd8f994359bc90b66510550befbc10fa997774f062e7d9ff55` |
| MAP-075 | `work/site-audit/crawl/8f1ee434464d2ed3a662.html` | 36,144 / `31c727a1ed5e942b4c3e7ab59f03e5a71e89efbaa125becd50fa6f31d2610b2d` | `work/remont-sistemyi-oxlazhdeniya.html` | 19,782 / `23e9d3cb12ec65aa10aafd469badd4a6f10151bfbbd1c9b6fe345a78d455a4d3` |
| MAP-095 | `work/site-audit/crawl/829754837596fdefbacc.html` | 32,655 / `aa64afc0e98f75923b9ede4ac0e4f8cf339a32d8ec4c57b76bc56508b00528d0` | `work/remont-generatora.html` | 17,331 / `204343a186d0f224c034156f8ccc703906fac1ec97276e148da7f6cb0a8d3c6b` |

Measured maxima are 37,209 source bytes and 20,339 artifact bytes. Fixed caps: MAP 256 KiB, RTE 512 KiB, existing DEV-09G parent package 16 KiB, each source/artifact 64 KiB, output package 64 KiB. The accepted 16 KiB parent boundary is preserved exactly in host and Python reader, including exact-cap success and cap+1 pre-read refusal. Every path must pass the existing literal allowlist, lexical and resolved containment, regular-file/no-link-or-reparse, realpath equality, pre-read size cap, strict UTF-8 and pinned SHA checks. Host tool performs no filesystem write, network or child process; emit writes stdout only.

## Closed artifact and price contract

Every artifact must have exactly one `.article`, exactly one `.article-hero-copy > p`, then one leading `<table class="price-table">`, followed by the frozen body. Table headers are exactly `Услуга` / `Цена, руб.`; every data row has exactly two plain-text cells with no nested tags.

Raw signatures use `T`=table, `P`=plain paragraph, `H`=h2, `U`=ul and `C`=`div.closing > p`:

| MAP | Raw ordered signature | Normalized main signature | price-note positions | closing positions |
|---|---|---|---|---|
| MAP-042 | `T,P,P,P,P,P,H,P,U,C` | `P,P,P,P,P,H,P,U,P` | `[1]` | `[9]` |
| MAP-052 | `T,P,P,P,H,U,C` | `P,P,P,H,U,P` | `[]` | `[6]` |
| MAP-055 | `T,P,C` | `P,P` | `[1]` | `[2]` |
| MAP-075 | `T,P,P,P,U,P,H,U,P,P,C` | `P,P,P,U,P,H,U,P,P,P` | `[1]` | `[10]` |
| MAP-095 | `T,P,U,C` | `P,U,P` | `[]` | `[3]` |

`p.price-note` normalizes to an ordinary paragraph and `div.closing > p` to the final ordinary paragraph; exact wrapper/class positions are checked before normalization. Missing, extra, reordered or differently classed elements fail before package comparison. Imported regions reject `a/form/script/style/h3/ol`, attributes outside the exact table/price-note/closing facts, HTML in cells, ampersand/entity variants and control/unpaired-surrogate data.

Package price rows are closed data with exact service label and one cell:

- exact `от N` → `{kind:"amount", amount:"N", from:true}`;
- exact `N` → `{kind:"amount", amount:"N", from:false}`;
- only MAP-055 row index 12 (`Замена задних рычагов`) is exact text `от 3500 за 1 шт.`;
- only MAP-055 row index 15 (`Запрессовка сайлентблоков в рычаги и тяги`) is exact text `1500 за 1 шт.`;
- every other syntax fails; suffixes are never guessed or discarded.

The public snapshot uses the existing one-column price matrix with column label `Цена, руб.`. The existing template supplies the left header `Услуга`; the existing public projector formats amount cells with `от`, narrow grouping, decimal comma and `₽`, while exact text cells remain escaped text. No new renderer or CSS is planned.

## Package and writer contract

Each package page contains exact fixed identity, source/artifact facts, `intro`, normalized `blocks` and exact `price_rows`. Canonical JSON is UTF-8/LF/no CR, duplicate-key rejecting and pins full package SHA plus ordered pages SHA after reviewed generation.

`apply_leading_price_details()` remains default-off and accepts only database `estakada_foundation_unit`, user `app_migrator` and one active owner `nesadmin`. Actual database identity is the first SQL inside one transaction; content→auth lock order remains unchanged.

Under locks it reads the same validated DEV-09G package, proves exact hidden MAP-012 aggregate using `_service_root_payload()`, and rechecks its exact tiles at positions 0/1/2/8/12. MAP-012 is never rewritten.

Only two cohort states are valid:

- all five absent → exhaustive UUID/route/sibling-position/reservation/audit collision preflight, then atomic create of all five;
- all five complete and exact → zero-write replay.

Any mixed/partial state, collision, parent/tile/payload/price/layout/audit/reservation drift, late synthetic failure or unexpected related row fails with full state unchanged. Two concurrent calls produce one create and one exact replay.

## Приёмочные сценарии до кода

- `MIGJ-001`: host pins the exact ordered global/source/artifact path+bytes+SHA tables above and exact MAP/RTE rows; source yields exact H1/title/empty description, DEV-09G yields exact MAP-012 parent/tile identity.
- `MIGJ-002`: each artifact proves exactly one intro, one leading two-column table, exact headers, row counts 11/8/21/5/1 and total 46, then the literal raw/normalized signatures and price-note/closing positions above. Missing/extra/reordered table/body/wrapper/class/cell fails with labelled error.
- `MIGJ-003`: exact row labels/order/value strings are frozen. Only `от N`, `N` and the two explicitly named compound MAP-055 text values are accepted; negative/decimal/signed/whitespace/suffix/currency/overflow variants are rejected rather than coerced.
- `MIGJ-004`: all input paths are exact contained regular non-links with the fixed pre-read caps, strict UTF-8 and pinned SHA. Escape/link/reparse/nonregular/oversize/short-read/CR/duplicate-key/invalid UTF-8 and exact-cap boundary cases are exercised; host writes/network/child-process count is zero.
- `MIGJ-005`: canonical package is exact5 with fixed UUID/URL/parent/position/name/H1/title/description/hidden, exact intro/body/price rows and no media/HTML/publication. Unknown keys/types/counts, identity/route/position duplicates and package/pages drift fail closed.
- `MIGJ-006`: shared text rendering still emits only escaped `p/h2/ul/li/strong` and requires sanitizer equality. Price construction emits only the existing schema matrix with deterministic UUIDv5 identities; script/style/link/template/control/surrogate mutations cannot reach stored/public output.
- `MIGJ-007`: production writer creates only hidden pages; each exact URL remains blank public 200 and exposes no intro, prices or main text. Separately, an isolated test-only fixture with the same validated snapshots and an explicitly published ancestor chain proves through public HTTP all five layouts intro→price→main, exact 46 rows, both MAP-055 text cells and existing amount formatting/escaping. The fixture does not call the migration writer, mutate a persistent database or authorize publication; production/persistent apply and publication remain zero. Existing DEV-08 price, visibility and DEV-09H/I text regressions stay green.
- `MIGJ-008`: disabled flag, non-test environment, wrong configured DB/user, wrong actual SQL identity and missing/inactive/non-unique `nesadmin` fail before package/locks/mutation.
- `MIGJ-009`: exact hidden MAP-012 and exact tiles at 0/1/2/8/12 permit create and are never rewritten. Parent aggregate or package/tile name/path/order drift refuses with full state unchanged.
- `MIGJ-010`: all-absent creates exactly five complete hidden aggregates and exact PRIMARY routes/revision/state/draft/pin/metadata/reservations/audit. No media, grants, Stable/manual revisions, publication or unrelated rows appear.
- `MIGJ-011`: exact replay performs zero writes and returns replayed=true. Mixed cohort, UUID/route/position collision, altered price/layout/text or synthetic fifth-create failure rolls back and preserves a full before/after state snapshot. Two real concurrent calls yield one create plus one replay.
- `MIGJ-012`: foundation copy/manifest adds only exact `content/dev09j_leading_price_details.json`; static oracle requires exactly six explicit migration package names with no wildcard. Focused host/Python/public tests, full guard, Django check, no migration drift, manifest and diff checks pass; foundation stops. Persistent/production apply remains zero.

## Явно исключено

Multi-table MAP-015/089, interleaved MAP-068/069/083, unauthorised duplicate MAP-016, paragraph-price MAP-032, missing/blocked parents, MAP-041, media, publication, grants, redirects, SEO expansion and all other remaining pages. Их нельзя «заодно» добавить в этот cohort.

## Порядок реализации после отдельного разрешения

1. Extend existing host validator with one literal exact5 cohort; generate and review one canonical package.
2. Add failing focused tests for exact package/price/layout/parent/create/replay/rollback/concurrency/public order and security negatives.
3. Add the minimal reader, price builder and fixed atomic entrypoint; extend the exact-six foundation allowlist.
4. Run focused tests, full guard and final checks; then independent code review before marking DEV-09J complete.
