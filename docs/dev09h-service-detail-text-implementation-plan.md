# DEV-09H: минимальный план текстовых service-detail страниц

Дата: 2026-11-10. Основание: owner approval exact10 после D-767, D-023, D-176/D-177, D-181/D-182, D-185–D-188, D-203/D-204, D-208 и D-235. Статус: independent plan review `APPROVED` D-770, P1/P2/P3=0; product code не начат.

## Цель и граница

Создать одним bounded migration slice десять hidden страниц `service_detail`:

| MAP | UUID | Exact parent | Position | Name |
|---|---|---|---:|---|
| MAP-064 | `92858ae1-d4ba-4e48-9370-642bce5f1999` | MAP-012 | 4 | Ремонт электрооборудования |
| MAP-067 | `9f940baf-a1bf-4d0b-ad24-feb6d2c0a070` | MAP-012 | 5 | Замена ремня ГРМ |
| MAP-080 | `29eb36ce-e161-4ac2-bc3a-e7510d018e90` | MAP-012 | 9 | АКПП/МКПП/РКПП/Вариатора |
| MAP-085 | `9178b8f5-9461-41c4-a753-afd923f8c592` | MAP-012 | 10 | Ремонт трансмиссии |
| MAP-098 | `5ce13aec-a88f-4881-a920-dd4118a384bf` | MAP-012 | 13 | Ремонт стартера |
| MAP-101 | `36e686ee-21e5-4712-bc2f-9de9600ffa3e` | MAP-012 | 14 | Ремонт выхлопной системы |
| MAP-104 | `d602432b-7326-4718-b243-0d35012e4f3a` | MAP-012 | 15 | Ремонт системы зажигания |
| MAP-107 | `d6509b60-e4be-4466-9f4f-f5a37710a170` | MAP-012 | 16 | Ремонт негабаритного транспорта |
| MAP-047 | `cd7ece74-a74b-427c-ba26-0ff70fe80635` | MAP-014 | 2 | Эвакуация автомобиля |
| MAP-050 | `cda9b4b6-002b-4526-89aa-9b0e79eeb368` | MAP-014 | 3 | Обработка порогов |

URL и positions берутся из approved DEV-09G catalog order. H1 и title сохраняются exact по pinned source/решениям; поэтому MAP-080 и MAP-107 могут иметь короткое navigation/admin name и более полный H1. Description остаётся exact empty.

Срез переносит только approved hero paragraph как `intro_text` и approved text body как `main_text`. Hero images, main/embedded/preview media, shared works, price, children, grants, publication и persistent apply не входят. Production, старый сайт и VPS не затрагиваются.

Не создаются model/table/migration, universal HTML parser/ETL, runtime JSON registry/loader, API, management command, dependency, CSS/component layer, cache, worker или schedule. Existing page schema, UNIT-only writer, generic public body and sanitizer policy are reused unchanged.

## Exact inputs и authority

Host-only `tools/dev09-service-details.mjs` читает только exact allowlist:

- pinned `docs/analytics-route-map.csv` и `docs/analytics-route-evidence.csv`;
- pinned existing parent/order authority `app/content/dev09g_service_roots.json` SHA `956c35fb5697acb23b039a980d1915228bd1100f1884ebece3fcd909ace365db`;
- десять exact source snapshots из D-767/MAP rows;
- десять exact approved artifacts: `work/remont-elektrooborudovaniya.html`, `work/zamena-remnya-grm.html`, `work/remont-akppmkpprkppvariatora.html`, `work/remont-transmissii.html`, `work/remont-startera.html`, `work/remont-vyixlopnoj-sistemyi.html`, `work/remont-sistemyi-zazhiganiya.html`, `work/remont-kommercheskogo-negabaritnogo.html`, `work/evakuacziya-avtomobilya.html`, `work/obrabotka-porogov.html`;
- new package `app/content/dev09h_service_details.json`.

Source SHAs already pinned in MAP rows. Approved artifact SHAs in MAP order are:

`4e841a6c20ad0ceb73f8d8395fe580a98abf5b8d0041aad649e1b1bff1e3a221`, `c72d7651cecd4e7a4241625cb8528c0653742e87742e1d33e6a1f7291a0fa8d1`, `6fb77f13b0da1d5ff90484e826846cde6481b878f91dd8a29f3fdc76393581ec`, `6f3fc2bdb22af157f42c7dfddf97f45a5f6161fef3cfdbc8c4ce75978934c6b2`, `31f6eab74dd4e6de9063c4c43ce19ba30cc5a1472bbc4f4e432b21ba2bb41c6e`, `ee07630cf8f2768d18f454efeba1bd5c68192ab2650b96ccbb5b271fffad0335`, `458e3edf61d3f3864eab0edecae3f1ef17ef35a4a5721ff31c2799df84478c93`, `3267e504cecdef7437cf5cf54a60224b6ad33dc255d5520d5c4899249e30195d`, `00de554c41bb0d220927356df32c1cc0dfcfe40dc710b5dd188fe559d6f55bd5`, `84af556ec907457d69f3cf13a0c860556e839857c6dcac440879690c3235ed06`.

Source snapshot is authority for exact URL, source SHA, one title, one H1 and empty description under D-023. Approved artifact plus named D-176/D-177/D-181/D-182/D-185–D-188/D-203/D-204 is authority only for hero paragraph and body block text/order. Header/footer/breadcrumbs/works/scripts/styles/artifact title are not imported. No new DEV-11 SEO decision is made.

Every file path must pass exact allowlist, lexical containment, `lstat` regular/no-link-or-reparse, realpath equality, pre-read cap, strict UTF-8 and pinned SHA. Exact caps: MAP256KiB, RTE512KiB, existing DEV-09G package16KiB, each source64KiB, each artifact64KiB and new package96KiB. Inspected maxima are35,677 source bytes and19,310 artifact bytes. Tool has zero filesystem writes, network or child processes; `--emit` writes stdout only.

The existing DEV-09G package is the sole catalog-order authority for child `(parent_id, position, name, url)`. For every planned page, host validation requires the exact parent page and exact tile at that zero-based position to equal the child name and URL. Missing/reordered/renamed/repathed tile or a new package descriptor that disagrees with the parent package fails; the new package cannot self-authorize its own navigation identity.

## Closed package и renderer

Package schema `dev09-service-details-v1`, LF/no CR, canonical JSON, exact ordered10 pages, cap96KiB. Each page contains fixed identity/source/artifact facts, `intro` plain text and ordered `blocks` only. Allowed block shapes:

- `{type: heading, text}`;
- `{type: paragraph, segments:[{text,strong}]}`;
- `{type: unordered_list|ordered_list, items:[[segments...], ...]}`.

Keys/types are exact. Text is non-empty bounded Unicode scalar data. `strong:true` is accepted only at the exact approved segment positions; empty/adjacent equivalent segments, unknown marks/tags/attributes and structural drift fail. Package contains no HTML, href, class, style, event, aria, media path, template, Python or JavaScript.

The bounded host extractor isolates exactly one `.article-hero-copy > p` and the body between the approved hero section and `</article>`. It accepts presentation-only `.closing > p` wrappers only at exact frozen block positions: one final wrapper in nine artifacts, and the approved intermediate plus final wrappers in MAP-067; each becomes an ordinary paragraph. It rejects a missing/extra/reordered wrapper or content, any other wrapper/attribute, link/image/table/script/style/form, unapproved tag and any source/artifact drift. This extractor is fixed to the ten allowlisted artifacts and is not used at runtime.

There is deliberately no HTML entity decoder. Direct inspection proves zero `&` characters in all ten imported artifact intro/body regions and zero in the source title/H1 metadata used by the package. Any ampersand in those extracted regions — bare, named, decimal, hexadecimal, alias or malformed entity syntax — fails before text construction. UTF-8 scalar text otherwise remains literal; no whitespace/entity normalization or alias equivalence is allowed. Labelled selfchecks cover `&`, `&amp;`, `&#38;`, `&#x26;`, unknown/missing-semicolon aliases and NBSP entity attempts.

Product renderer receives only validated package data. It escapes every text segment, emits only `p/h2/ul/ol/li/strong`, renders intro as one `p`, then requires `restricted_clean(output) == output` independently for intro and main. Shared editor/sanitizer policy remains unchanged.

`initial_snapshot(service_detail)` supplies existing layout; only `intro_text`, `main_text`, H1/title/description change. Price remains the existing empty value. Generic public body already renders these fields, so no template or CSS patch is planned.

Foundation snapshot copy and post-snapshot manifest gain one exact path, `content/dev09h_service_details.json`. Static oracle requires all four exact migration package names simultaneously; wildcard/extension-wide JSON inclusion remains forbidden.

## Writer и exact-parent proof

`app/content/dev09_migration_apply.py` gains `apply_service_details()` and narrowly scoped package/renderer helpers only. Entry stays default-off and exact UNIT `estakada_foundation_unit/app_migrator`. Actual `current_database/current_user` is still the first SQL inside one atomic transaction before locks and mutation.

Under existing content→auth lock order, both parents must be complete exact hidden DEV-09G aggregates produced from the same `_read_service_roots_package()` and `_service_root_payload()` data used as child-order authority. Parent payload, PRIMARY route, position, revision/state/draft/pin/metadata/reservation/audit must match; parents are never rewritten. Before child preflight, every child descriptor is again bound to the exact parent tile `(position,name,url)` from that validated package. MAP-002, article package, DEV-09E package and unrelated service pages are not required or read.

Only two cohort states are accepted:

- all ten absent → exhaustive UUID/route/sibling-position/reservation/audit preflight, then create all ten in package order;
- all ten exact → zero-write replay.

Any mixed state, partial/extra related row, changed payload/parent/position/route/audit/reservation or UUID/URL collision fails with full state unchanged. Existing `_create_aggregate` and `_exact_aggregate` receive already validated payloads; no registry/schema dispatch/generic importer is added. Synthetic failure during page10 rolls back all ten and preserves both parents. Two real concurrent calls yield one create and one exact replay.

## Public boundary

Production pages stay hidden. Test-only published fixtures prove generic HTTP output preserves exact intro/main semantic order for all ten pages, including unordered list, ordered list and strong segments. No hero image, works, price, form or script appears. Unsafe stored HTML returns503/no-store before partial intro/body output. Existing public body/template/CSS are regression-tested but not modified.

## Приёмочные сценарии до кода

- `MIGH-001`: host validator pins MAP/RTE, existing DEV-09G package and exact10 sources/artifacts; requires exact MAP IDs, URLs, type/template/state/source SHA and exact parent tile `(position,name,url)` for every child. Source supplies one exact title/H1/empty description; artifact authority is limited to approved intro/body.
- `MIGH-002`: bounded artifact extraction proves exact one hero paragraph and exact ordered block/segment facts for every page. Missing/extra/reordered heading/paragraph/list/item/strong segment, altered valid text or wrapper fails with labelled error; header/footer/works/media never enter package. Any bare/named/decimal/hex/malformed entity ampersand fails under the zero-entity contract; no decoder/normalizer exists.
- `MIGH-003`: all files are exact allowlisted contained regular non-links and use fixed MAP256/RTE512/parent-package16/source64/artifact64/new-package96KiB caps before read, strict UTF-8 and pinned SHA. Escape/link/reparse/nonregular/oversize/short-read/CR/invalid UTF-8/duplicate-key and cap-boundary cases fail; tool performs zero writes/network/child process.
- `MIGH-004`: canonical package has exact10 fixed UUID/URL/parent/position/name/H1/title/empty-description/hidden descriptors bound to DEV-09G parent tiles, exact intro/blocks and no price/media/HTML. Unknown keys/types/counts, duplicate identities/routes/positions, parent-tile reorder/name/path drift, MAP-032/table/media facts or package drift fail closed.
- `MIGH-005`: renderer emits only `p/h2/ul/ol/li/strong`, escapes every segment, preserves approved order/strong boundaries and requires sanitizer equality for both fields. Independent quote/script/style/class/event/on*/aria/link/template/control/unpaired-surrogate and structure mutations cannot reach output; shared policy is unchanged.
- `MIGH-006`: disabled flag, non-test environment, wrong configured DB/user and wrong actual identity stop before package/locks/mutation; exact active owner `nesadmin` is required.
- `MIGH-007`: exact MAP-012 and MAP-014 parent aggregates plus exact child binding to each validated parent tile permit create; missing/partial/changed either parent or tile-order/name/path mismatch refuses with complete state unchanged and never rewrites a parent. MAP-002/articles/DEV-09E/unrelated service pages are not prerequisites.
- `MIGH-008`: all-absent creates exactly ten complete hidden aggregates with exact PRIMARY routes, parents, sparse positions, revision/state/draft/pin/metadata/reservations/audits and no grants/media/price/publication/children; public tree excludes them.
- `MIGH-009`: all-exact replay has zero mutation. Every one-present/mixed boundary plus partial/extra related rows and UUID/route/target/position/audit/reservation collisions refuses with full-state equality.
- `MIGH-010`: synthetic page10 failure rolls back all ten and preserves both parents/all prior state; two real concurrent calls produce one create and one exact replay.
- `MIGH-011`: test-only published fixtures return200 with exact intro/main semantic content for all10 and representative ul/ol/strong cases; no media/price/works. Unsafe stored intro or main returns503/no-store with no partial page-specific text. Existing generic public/CSP/layout behavior remains unchanged.
- `MIGH-012`: foundation snapshot/manifest contains and hashes exactly four migration JSON paths with static no-wildcard oracle. Host/focused tests, DEV-09B/09E/09G create+replay regression, shared policy/public tests, full guard, Django check, migration no-changes and diff-check pass; foundation stops. No persistent/production apply, publication, live access or new schema/dependency/runtime/background layer occurs.

## Порядок после plan approval

1. Bounded host validator and reviewed canonical package; add the one exact fourth package path/oracle.
2. Failing focused tests for package/rendering/parents/all-absent/all-exact/mixed/rollback/concurrency/public boundary.
3. Minimal existing-writer extension only; no public template/CSS change.
4. Host/focused/full guard/Django/migrations/diff and independent code review.
