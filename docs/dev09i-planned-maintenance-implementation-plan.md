# DEV-09I: минимальный план переноса ветви «Плановое ТО»

Дата: 2026-11-10. Основание: D-023, D-176/D-177, D-181/D-182, D-185–D-188, D-203/D-204, D-208, D-235, D-773, selection D-774 и owner approval D-775. Статус: план и приёмочные сценарии записаны до product code; требуется independent plan review.

## Утверждённая граница exact9

| MAP | UUID | Kind | Parent | Position | Name |
|---|---|---|---|---:|---|
| MAP-011 | `4359fedb-0703-41a0-b76c-faaa165073ca` | `service_section_overview` | MAP-002 | 1 | Плановое ТО |
| MAP-030 | `49e44e5d-9bde-46e9-ac59-76118db6299d` | `service_detail` | MAP-011 | 0 | Техническое Обслуживание (ТО) |
| MAP-035 | `567db00e-f835-408f-9b39-f79e379b7cc3` | `service_detail` | MAP-011 | 1 | Замена масла в двигателе |
| MAP-046 | `66cbd76e-e2e8-46a0-a4e2-18b1533ee63f` | `service_detail` | MAP-011 | 3 | Замена салонного фильтра |
| MAP-051 | `39b0875f-2b79-46b5-8728-bd40a41184a1` | `service_detail` | MAP-011 | 4 | Замена тормозных колодок |
| MAP-054 | `c8d6af90-725e-458e-a88b-0ef188a922ae` | `service_detail` | MAP-011 | 5 | Замена тормозных дисков |
| MAP-060 | `fdf7901d-6699-4fc1-90a3-7e7bb37d5c04` | `service_detail` | MAP-011 | 6 | Замена техниченских жидкостей |
| MAP-063 | `95de515f-cfda-432f-8e6b-bce0b9808e75` | `service_detail` | MAP-011 | 7 | Замена свечей зажигания |
| MAP-074 | `f0a24fb2-6924-4b7f-af7a-2ea227196563` | `service_detail` | MAP-011 | 8 | Замена щёток стеклоочистетелей |

URL и позиции берутся из exact group position1 существующего `app/content/dev09e_services_catalog.json`. Отсутствующая sibling position2 — утверждённо исключённая MAP-041; она не создаётся, не уплощается и не меняет schema. Source supplies exact URL/title/H1/empty description; approved artifact supplies only one hero paragraph and ordered body blocks.

Все страницы остаются hidden. Hero images, works, other media, prices, grants, publication, MAP-041 и любые другие descendants не создаются.

## Архитектурная граница

Новая модель, таблица, миграция, dependency, universal parser/ETL, runtime registry/JSON loader, API, management command, cache, worker, scheduler или frontend component не создаются. Existing page/version aggregate, default-off UNIT-only gate, locks, exact replay, rollback, sanitizer and public renderer remain authoritative.

Чтобы не дублировать крупный DEV-09H validator, `tools/dev09-service-details.mjs` получает только второй literal cohort и два exact CLI actions `--emit-planned-maintenance` / `--check-planned-maintenance`; прежние `--emit`, `--check`, `--selfcheck` и DEV-09H результат остаются совместимыми. Нет arbitrary path/config/registry или cohort auto-discovery.

Product code получает один package reader/validator и `apply_planned_maintenance()`. Общая проверка text blocks и code-owned renderer выделяется из уже существующего DEV-09H кода ровно один раз и вызывается двумя фиксированными entrypoints; schema dispatch, plugin interface или generic importer не добавляются. Existing DEV-09H package hash/pages hash and create/replay behavior остаются regression boundary.

## Host authority и package

Новый canonical package `app/content/dev09i_planned_maintenance.json`:

- schema `dev09-planned-maintenance-v1`, policy `validated_approved_text_not_import_authority`;
- exact ordered9 pages и фиксированные UUID/kind/parent/position;
- inputs pin MAP, RTE и existing DEV-09E package SHA `beffdfdbacc6a24a71c68ee692f03be262f67745b8425e1ce9b204b8d15ca9e9`;
- package cap64KiB, UTF-8/LF/no CR, canonical JSON and pinned package/pages SHA after review;
- MAP/RTE caps256/512KiB, existing catalog20KiB, every exact source/artifact64KiB before read.

Every path uses the existing exact allowlist, lexical containment, resolved containment, regular-file/no link-or-reparse, realpath equality, pre-read cap, strict UTF-8 and pinned SHA. The host tool performs no filesystem write, network or child process; emit writes stdout only.

DEV-09E group position1 must exactly equal name `Плановое ТО`, href `/services/planovoe-to/` and its approved nine items. MAP-011 binds to the group; each selected child binds to the exact item at position0/1/3/4/5/6/7/8. Position2 remains exact MAP-041 in authority but is forbidden in the new package. Package data cannot authorize its own navigation identity.

### Pinned source и artifact inputs

Это внешний literal oracle плана, а не значения, впервые объявляемые реализацией. Host specs обязаны совпасть с каждой строкой целиком и в этом MAP order.

| MAP | Source path | Source bytes / SHA-256 | Artifact path | Artifact bytes / SHA-256 |
|---|---|---|---|---|
| MAP-011 | `work/site-audit/crawl/77669bae3852b13314e0.html` | 28,371 / `b934ccbf5c023670a7e8eeafa21bc1ad9f1032c76f59cd59612d5463ab9b1417` | `work/planovoe-to.html` | 16,922 / `eda40902467de691997b9b298eee1e91977810ac1b645e7ce78599822c2086b7` |
| MAP-030 | `work/site-audit/crawl/2556b9176b5cb816433f.html` | 29,167 / `3c9b431766f080fb55f95ff00f0f74d1dd42802608130b3800d0a7a231a3f12e` | `work/texnicheskoe-obsluzhivanie-to.html` | 17,422 / `a3c090c2a39607973a1589fe05cda50c3fbabe5ce4792da9a378275a5d2335ed` |
| MAP-035 | `work/site-audit/crawl/b30c631211c590e04d91.html` | 28,923 / `0630b52094f80d14a336205679045529b6ff29ada781072e053510ea6d98b5b3` | `work/zamena-masla-v-dvigatele.html` | 17,361 / `1b8974d4259d254bdf6f10fc59fd54b725421e7c1d17674e1003d284244abbea` |
| MAP-046 | `work/site-audit/crawl/88d0ba56ce1cb4751c07.html` | 29,238 / `dbfa399b0d4199391661108756b1c28a9ba37fe205b5aef7662ec4ac82e982da` | `work/zamena-salonnogo-filtra.html` | 18,332 / `f065e7f860a57642358c05bdec5555e1f4996a6e1a6d005ec7589d3302ebc264` |
| MAP-051 | `work/site-audit/crawl/88121db29cfba38f0e76.html` | 28,169 / `cc7e40a53169a6f31e28d6c48592e572c8535dd8d671f970de6a30f2251849d1` | `work/zamena-tormoznyix-kolodok.html` | 17,173 / `1641cdb21f1a90108fe5e4a63694d45e8334f0800ed4fdf76a7de883781f22c2` |
| MAP-054 | `work/site-audit/crawl/74c95808646fb6aa90fc.html` | 29,739 / `a6c77866c6f271ea9ee759ae07425f525b202bac8b8d3bfe9fbab3c335bf0f9e` | `work/zamena-tormoznyix-diskov.html` | 18,808 / `75d93caf54a8a43093680d50ddf3125b45517d59716226fb881ebcbf360b0a5a` |
| MAP-060 | `work/site-audit/crawl/65ca2afaf8f57167194b.html` | 28,407 / `b6ded9c9626f9e1ac155e208d1733c3ca4d31f4726edc77247c9ec80657cd9ff` | `work/zamena-texnichenskix-zhidkostej.html` | 17,455 / `742255db022a453ed3492d7e34277ebe414865b587f71eedd77b6ab2b3774177` |
| MAP-063 | `work/site-audit/crawl/6470f9d3db3f6cf5dc09.html` | 28,730 / `8de6fd0a3da23c3171111d7b080026b587f64d3d7c2e7832eb26db7f73e52843` | `work/zamena-svechej-zazhiganiya.html` | 17,692 / `6db2f97b27d1ba73ad08b1571175ca1b7e6eeb1d69a631417a698cb44d8ad664` |
| MAP-074 | `work/site-audit/crawl/077f62dc5ea9aa94352e.html` | 28,187 / `b6968e5c2f65d6e1dcbb9dcad2aa8f23bd17729c185d1ffe6a46567ee748d92e` | `work/zamena-shhyotok-stekloochistetelej.html` | 17,100 / `db0e9a8993bd1e8ed018186f4f34cc6d0dcfb19692f62a396ce3160e73eaa64c` |

Measured maxima are29,739 source bytes and18,808 artifact bytes, both below the fixed64KiB per-file cap with margin. Selfcheck/check compares exact paths, bytes boundary and SHA above; no wildcard discovery is permitted.

## Closed extraction и renderer

The imported grammar remains plain `intro` plus ordered blocks:

- `{type:"heading", text}`;
- `{type:"paragraph", segments:[{text,strong}]}`;
- `{type:"unordered_list", items:[[segments...], ...]}`.

No ordered list is needed by exact9. Renderer still emits only escaped `p/h2/ul/li/strong`, independently requires `restricted_clean(output) == output` for intro and main and passes only trusted closed data into the existing snapshot schema. No HTML, href, class, style, event, aria, media path, template, Python or JavaScript is stored in package text fields.

The bounded extractor isolates exactly one `.article-hero-copy > p` and the body before `</article>`. Presentation-only artifact markup is allowed only as frozen facts for these nine exact files: `ul class="body-types"`, `p class="note"` and `div class="closing"><p>…</p></div>` at exact per-page positions. They normalize respectively to unordered list or ordinary paragraph; missing/extra/reordered class/wrapper or any other attribute fails. Header/footer/works/hero image never enter the package.

### Frozen ordered structure oracle

Positions are zero-based normalized block positions. Signatures use `H`=heading, `P`=ordinary paragraph and `U`=unordered list. Empty arrays are required facts, not omitted checks.

| MAP | Ordered block signature | `body-types` U positions | `note` P positions | `closing`→P positions |
|---|---|---|---|---|
| MAP-011 | `H,P,P,U,P` | `[3]` | `[]` | `[4]` |
| MAP-030 | `H,P,P,U,P` | `[3]` | `[]` | `[4]` |
| MAP-035 | `H,P,P,P,P` | `[]` | `[]` | `[4]` |
| MAP-046 | `H,P,P,P,H,P,P,U,P,P` | `[7]` | `[3,8]` | `[9]` |
| MAP-051 | `H,P,P,U,P` | `[3]` | `[]` | `[4]` |
| MAP-054 | `H,P,P,P,U,P,H,P,P` | `[4]` | `[5]` | `[8]` |
| MAP-060 | `H,P,P,H,U` | `[4]` | `[]` | `[]` |
| MAP-063 | `H,P,P,P,P` | `[]` | `[]` | `[4]` |
| MAP-074 | `H,P,P,P` | `[]` | `[]` | `[3]` |

These literals are independent expected data for extraction and negative selfchecks. The host must reject any signature or position difference before package comparison; package comparison then additionally freezes every exact text, item and strong-segment boundary.

Direct inspection proves zero ampersands in all imported intro/body regions. As in DEV-09H there is no entity decoder: any bare, named, numeric, hexadecimal, alias or malformed `&` fails before text construction. Exact9 additionally proves no imported `a/table/form/script/style/h3`, no numeric ₽/руб price expression and no ordered list. Unicode scalar validation occurs before sanitizer; control/unpaired-surrogate data fails with constant `MIGRATION_PACKAGE_INVALID`.

## Atomic writer

`apply_planned_maintenance()` stays default-off and accepts only test DB `estakada_foundation_unit`, user `app_migrator` and active owner `nesadmin`. Actual database identity remains the first SQL inside one transaction before locks or mutation; content→auth lock order is unchanged.

Under locks, exact MAP-002 is proved from the same validated DEV-09E package and `_services_payload()` used by existing migration code. Parent aggregate, route, initial revision/state/draft/pin/metadata/reservations/audit and hidden state must match; MAP-002 is never rewritten. The exact group/items are checked again before mutation.

Only two states are valid:

- all nine absent → exhaustive UUID/route/sibling-position/reservation/audit collision preflight, then create MAP-011 followed by its eight children inside the same transaction;
- all nine complete and exact → zero-write replay.

Any mixed/partial/extra related state, changed payload/parent/position/route/audit/reservation, collision, unexpected position2 page or authority drift fails with full state unchanged. Synthetic page9 failure rolls back all nine and preserves MAP-002. Two real concurrent calls produce one create and one exact replay.

## Foundation boundary

Snapshot copy and post-snapshot manifest add only exact `content/dev09i_planned_maintenance.json`. Static oracle requires all five explicit migration package names simultaneously; wildcard/extension-wide JSON inclusion remains forbidden. No persistent/local/production apply is performed.

## Приёмочные сценарии до кода

- `MIGI-001`: host validator pins the plan's exact ordered path/bytes/SHA table for MAP/RTE, DEV-09E package and nine sources/artifacts; proves parent group position1 and selected child item `(position,name,url)` bindings. Source supplies exact title/H1/empty description; artifacts supply only intro/body.
- `MIGI-002`: extractor compares every page against the plan's literal ordered block signature and exact `body-types`/`note`/`closing` position arrays before package comparison, then proves exact intro/block/item/strong facts. Missing/extra/reordered block/item/strong/class/wrapper, altered valid text, `a/table/form/script/style/h3/ol`, numeric price or any ampersand entity variant fails with labelled error.
- `MIGI-003`: all inputs are exact allowlisted contained regular non-links with fixed MAP256/RTE512/catalog20/source64/artifact64/package64KiB caps before read, strict UTF-8 and pinned SHA. Measured source/artifact maxima29,739/18,808 bytes, escape/link/reparse/nonregular/oversize/short-read/CR/invalid UTF-8/duplicate-key and cap-boundary cases are checked; tool has zero writes/network/child process.
- `MIGI-004`: canonical package has exact9 fixed UUID/URL/kind/parent/sparse-position/name/H1/title/empty-description/hidden descriptors, exact intro/blocks and no price/media/HTML. Unknown keys/types/counts, duplicate identity/route/position, MAP-041 inclusion and package/pages drift fail closed.
- `MIGI-005`: shared text renderer emits only `p/h2/ul/li/strong`, escapes every segment, preserves approved order/strong boundaries and requires sanitizer equality for intro/main. Quote/script/style/class/event/on*/aria/link/template/control/unpaired-surrogate mutations cannot reach output; DEV-09H exact renderer/package regression and shared policy remain unchanged.
- `MIGI-006`: disabled flag, non-test environment, wrong configured DB/user and wrong actual identity stop before package/locks/mutation; exact active owner `nesadmin` is required.
- `MIGI-007`: exact hidden MAP-002 plus exact DEV-09E group/items permit create and are never rewritten. Missing/partial/changed MAP-002, group/name/path/order drift or selected tile mismatch refuses with full state unchanged.
- `MIGI-008`: all-absent creates exactly nine complete hidden aggregates: MAP-011 under MAP-002 and eight children at sparse positions, exact PRIMARY routes, revisions/state/drafts/pins/metadata/reservations/audits and no grants/media/price/publication/MAP-041; public tree excludes them.
- `MIGI-009`: all-exact replay has zero mutation. Every one-present/mixed boundary plus partial/extra related rows and UUID/route/target/position/audit/reservation collisions refuses with full-state equality; unexpected position2 child is a collision.
- `MIGI-010`: synthetic page9 failure rolls back all nine and preserves MAP-002/all prior state; two real concurrent calls yield one create and one exact replay.
- `MIGI-011`: test-only published fixtures return200 with exact semantic intro/main for all nine and representative ul/strong/note-normalized cases, no media/price/works. Unsafe stored intro/main returns503/no-store without partial page text. Existing generic public/CSP/layout and DEV-09H public tests remain unchanged.
- `MIGI-012`: old and new host checks, focused tests, DEV-09B/09E/09G/09H create+replay regression, shared policy/public tests, full guard, Django check, migration no-changes, exact-five manifest and diff-check pass; foundation stops. No persistent/production apply, publication, live access or new schema/dependency/runtime/background layer occurs.

## Порядок после plan approval

1. Extend the existing host validator; review stdout; add one canonical package and exact fifth foundation path.
2. Add failing focused tests for package/renderer/parent/create/replay/mixed/collisions/rollback/concurrency/public boundary.
3. Minimal shared text-validation/renderer extraction and one exact9 apply entry.
4. Focused checks, one full guard, final checks and independent code review.

До independent plan review `APPROVED` и отдельной команды владельца product code не начинать.
