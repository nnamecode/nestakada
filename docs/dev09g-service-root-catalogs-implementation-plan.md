# DEV-09G: минимальный план двух корневых каталогов услуг

Дата: 2026-11-10. Основание: owner approval MAP-012+MAP-014 после D-761, D-171, D-200, D-208, D-235 и завершённый DEV-09E. Статус: реализация завершена D-766; final independent code review `APPROVED`, P1/P2/P3=0.

## Цель и граница

Создать две скрытые CMS-страницы типа `service_catalog`:

- MAP-012 `/services/remont/`, UUID `729b10a3-709e-41c0-a71f-0d376a2b8586`, parent MAP-002, position 2, 17 утверждённых плиток;
- MAP-014 `/services/drugie-uslugi/`, UUID `ec990108-25c4-4ae9-961f-13487e63e938`, parent MAP-002, position 4, 5 утверждённых плиток.

Обе страницы остаются hidden. Срез не создаёт 22 дочерние страницы, не переносит hero/works/media/price/forms и не публикует данные. Живой сайт и persistent/local database не изменяются.

Не создаются model/table/migration, универсальный parser/ETL, runtime JSON loader, API, management command, cache, worker, schedule, dependency или frontend framework. Переиспользуются существующие package boundary, UNIT-only DB/role gate, locks, transaction, aggregate create/exact replay и safe public renderer.

## Источники и closed package

Host-only `tools/dev09-service-roots.mjs` читает только exact allowlist:

- MAP/RTE CSV с уже pinned SHA;
- source snapshots MAP-012 `ca4ab73dc69f37051a6f.html` SHA `249c910d6e6340f652587f14c3cdea20c5c7befe21adf9f42719f16e7bd289a5` и MAP-014 `32ee0e4b4942a75ffa9e.html` SHA `25a3204a9ddb323e93b37b60887d78c6680d3978d8026cb7c8818b1ad4eeb78d`;
- approved artifacts `work/remont.html` SHA `cf7352e8dd14cae5059b3bf583586f32266882b47a44eff3d5119269dd4564c3` и `work/drugie-uslugi.html` SHA `50c2c6c412d9ff93c7581816d7323eb541dc00c0b0878cca50ccadbc7446af1d`;
- new package `app/content/dev09g_service_roots.json`.

Каждый путь проходит lexical equality, repo containment, `lstat` regular/no-link-or-reparse, realpath equality, pre-read cap, strict UTF-8 and pinned SHA. Script has no network, child process or filesystem write; emit is stdout only. Это bounded validator двух страниц, не reusable scraper.

Package schema `dev09-service-roots-v1`, policy `validated_approved_artifact_not_import_authority`, LF/no CR, cap 16 KiB, exact ordered two pages. Для каждой страницы хранятся только fixed identity/source/artifact facts и ordered tiles `{name,href}`. H1/title/description:

- `Ремонт` / `Ремонт | Автосервис «Эстакада»` / empty;
- `Другие Услуги` / `Другие Услуги | Автосервис «Эстакада»` / empty.

Title authority is not the design artifact and does not make a new DEV-11/SEO decision. The host validator extracts one exact `<title>` from each pinned source snapshot and requires the values above under D-023; empty source descriptions are likewise preserved. Artifact authority remains limited to the approved tile selection/labels/order.

Intro, price, main/preview/embedded images are empty. Every href is an exact pinned internal path; schemes, `//`, query, fragment, backslash, controls and unknown keys/types are forbidden.

Artifact is the approved presentation/content authority only for the bounded tile selection. Validator proves artifact links exist in the pinned source/master cohort and encodes the approved differences explicitly, without fuzzy normalization:

- MAP-012 has exact17 paths/order; positions7/10 keep D-171 labels `Климат-контроль, Печка` and `АКПП/МКПП/РКПП/Вариатора` instead of source labels;
- MAP-014 has exact5 paths/order; source/master `Автомойка` is the one explicit D-200 exclusion and no other item may disappear/appear.

Selfchecks cover missing/extra/reordered tile, changed valid name/path, wrong approved substitution/exclusion, source title/description drift, MAP/RTE/source/artifact drift, path escape/link/nonregular/oversize/CR/UTF-8/duplicate keys and package shape.

The test foundation allowlist is extended by one exact path only: `content/dev09g_service_roots.json`. Snapshot copy and post-snapshot source manifest must contain and hash exactly all three migration packages: `dev09b_articles_slice.json`, `dev09e_services_catalog.json`, and `dev09g_service_roots.json`. Wildcard/extension-wide JSON inclusion is forbidden. A static harness oracle proves all three exact names are present in both copy and manifest cohorts.

## Writer и parent proof

`app/content/dev09_migration_apply.py` gains `apply_service_roots()` only. Entry remains default-off and exact test UNIT `estakada_foundation_unit/app_migrator`; actual database/user is still the first SQL inside one atomic transaction, before content→auth locks and mutation.

Direct parent proof reuses the existing validated DEV-09E boundary: `_read_services_package()`, exact `SERVICES_PAGE` descriptor and `_services_payload()`. Under the same locks MAP-002 must be the complete exact hidden aggregate. MAP-001/article package/other service roots are not read or required. Parent is never rewritten. Missing/partial/changed MAP-002 refuses with full state unchanged.

After parent proof, both child IDs are locked. Only these states are accepted:

- both absent → exhaustive collision/sibling-position/reservation/audit preflight, then create both in package order;
- both exact → zero-write replay;
- one present, partial/extra related state, changed payload/route/position/parent/audit/reservation or UUID/URL collision → fail closed.

Both aggregates use the existing `_create_aggregate(page, actor, payload)` and `_exact_aggregate(page, actor, payload)`; no schema dispatch/registry/generic importer is added. A late failure on the second page rolls back both children and preserves the parent. Two real concurrent calls yield one create and one exact replay.

No `PageGrant`, child page, media usage, publication or persistent operation is created.

## Безопасный HTML и public presentation

Closed renderer accepts only the already validated page tile list and emits exactly one `ul`, N `li`, N `a` and N `strong`. It escapes link text and quoted href, then requires `restricted_clean(output) == output`. Stored data contains no class/style/event/aria/script/template/Python/JavaScript. Shared editor/sanitizer policy remains unchanged.

The public template adds `public-service-root-catalog` only for `page.page_kind == service_catalog` and `main_text`. Catalog-scoped CSS renders the approved tiles with CSS counters/pseudo arrows, visible focus, 4/3/1 columns and full untruncated text. Decoration is not stored and does not enter accessible link names. No hero/image/intro/works/form/video/price/script is introduced in this slice.

Production pages remain hidden. Django HTTP semantics are tested with test-only published fixtures for exact17 and exact5 links/order/names; unsafe stored HTML fails503 without partial catalog output. Real-browser QA is not claimed; owner decision to work without Playwright remains unchanged.

## Приёмочные сценарии до кода

- `MIGF-001`: host validator pins MAP/RTE, both source snapshots and both approved artifacts; exact MAP IDs/paths/H1/template/state are required. Each source must contain exactly one preserved D-023 title and empty description matching the package; artifact title is ignored as non-authoritative and no DEV-11 decision is made.
- `MIGF-002`: exact artifact extraction proves MAP-012 17 and MAP-014 5 ordered names+paths; only two D-171 label substitutions and one D-200 exclusion are accepted. Missing/extra/reordered/other changed name/path fails with labelled error.
- `MIGF-003`: all input/package files are exact allowlisted contained regular non-links, bounded before read, strict UTF-8 and SHA-pinned; escape/link/nonregular/oversize/short-read/CR/invalid UTF-8/duplicate-key cases fail before data can be used. Tool performs zero writes/network/child process.
- `MIGF-004`: canonical closed package has exact two UUIDs, parent MAP-002, positions2/4, hidden state, source-proven exact titles/H1/empty descriptions and exact17/5 artifact-approved tiles; unknown keys/types/counts/source/artifact facts fail closed.
- `MIGF-005`: renderer emits only `ul/li/a/strong`, escapes text/href, requires sanitizer equality and preserves exact accessible names without numbers/arrows. quote/script/event/style/class/on*/aria/scheme/query/fragment/backslash/control mutations cannot reach output; shared policy is unchanged.
- `MIGF-006`: disabled flag, non-test environment, wrong configured DB/user and wrong actual `current_database/current_user` stop before package/locks/mutation; exact active owner is required.
- `MIGF-007`: exact MAP-002 parent alone permits create without MAP-001/articles/other service roots; missing/partial/changed parent refuses with full state unchanged and is never rewritten.
- `MIGF-008`: both-absent creates exactly two complete hidden aggregates with exact legacy PRIMARY routes/positions/revision/state/draft/pin/metadata/reservations/audits, no grants/media/children; public tree excludes them.
- `MIGF-009`: both-exact replay has zero mutation. Mixed one-present, partial/extra related rows, UUID/route/target/position/audit/reservation collisions refuse with full state unchanged.
- `MIGF-010`: synthetic failure during second aggregate rolls back both children and preserves parent/all prior state; two real concurrent calls produce one create and one exact replay.
- `MIGF-011`: Django HTTP test-only published fixtures return200 with exact17/5 safe links and scoped class; CSS proves focus,4/3/1 and no fixed height/ellipsis. Wrong kind gets no class; unsafe content returns503 with no partial names.
- `MIGF-012`: foundation snapshot/source manifest includes and hashes the three exact migration JSON paths with no wildcard JSON admission. A static oracle proves the copy and manifest allowlists contain all three. Host/focused tests, existing article and DEV-09E create/replay regression, shared policy/public tests, full guard, Django check, migration no-changes and diff-check pass; foundation stops afterwards. No persistent/production apply, publication, live access, media transfer, new schema/dependency/runtime/background layer occurs.

## Порядок после plan approval

1. Host validator and reviewed canonical package; extend foundation copy/manifest by the one exact third JSON path and add the three-name static oracle.
2. Failing focused tests for package, approved differences, renderer, parent, atomic create/replay/rollback/concurrency and public contract.
3. Minimal writer/renderer/template/CSS patch with shared policy unchanged.
4. Focused tests, full guard, Django/migrations/diff and independent code review.
