# DEV-09E: минимальный план реализации `/services/`

Дата: 2026-11-09. Основание: утверждённый владельцем после D-754 макет `work/services.html`, UI-S052 и exact source MAP-002/RTE-002. Статус: реализовано и принято D-759; repeat independent code review `APPROVED`, P1/P2/P3=0.

## Цель и граница

Создать одну скрытую CMS-страницу MAP-002 `/services/` типа `services_master_catalog` с exact H1 и пятью группами/58 ссылками утверждённого макета. Реализация не публикует страницу, не создаёт 57 дочерних страниц, не переносит их тексты/цены/медиа и не меняет живой сайт.

Не создаются новая модель/таблица/миграция, универсальный parser/ETL, runtime JSON loader, API, management command, cache, worker, schedule или новый frontend framework. Существующие security gates, transaction/lock/replay и page-version aggregate переиспользуются.

## Данные

Новый небольшой versioned package `app/content/dev09e_services_catalog.json`:

- closed schema `dev09-services-catalog-v1`, policy `validated_package_not_import_authority`, cap 20 KiB, UTF-8/LF/no CR, pinned SHA-256;
- одна page: UUID `f39af842-05a7-4101-af9a-2fc320d457d0`, MAP-002, `/services/`, `services_master_catalog`, parent MAP-001 UUID `e80c3de1-feea-4847-b550-325a825ffc0e`, root position1, unpublished;
- exact source path/SHA, H1 `Услуги и цены автосервиса "Эстакада"`, title `Услуги | Автосервис «Эстакада»`, empty description, no media/price/intro;
- exactly5 ordered group objects. Each contains one root link and a closed ordered list of child links. Totals including roots:12/10/18/11/7=58;
- every name is plain text. Every href is an exact pinned internal path beginning with one `/`; schemes, `//`, query, fragment, backslash and controls are forbidden.

Package is not a new source of truth. Host-only `tools/dev09-services-catalog.mjs` pins current MAP/RTE/source hashes, extracts only the source extended catalog and proves exact decoded name+path+order, group boundaries and H1 before emitting/validating the package. It is a bounded one-page validator, not a reusable scraper.

The validator has an explicit read-only file boundary: exact allowlisted repo-relative MAP, RTE, pinned source and package paths; lexical path equality, resolved repo containment, `lstat` regular-file/no symlink-or-reparse check, pre-read caps, strict UTF-8 and pinned SHA before parsing. MAP/RTE/source/package each has its own proportionate cap. The script performs no network, child-process or filesystem write; generation is stdout reviewed into an `apply_patch`. Selfchecks cover path escape, link/symlink or non-regular input, oversize, CR/package, invalid UTF-8, duplicate keys and source/package shape mutations.

## Writer и безопасный HTML

`app/content/dev09_migration_apply.py` keeps the existing default-off UNIT-only entry boundary. A new `apply_services_catalog()` reuses `_enabled`, first-SQL DB/role identity check, advisory locks, exact owner `nesadmin`, audit and one atomic transaction.

Current aggregate helpers are article-payload-coupled through `_expected_payload()`/`_snapshot()`. They are changed narrowly to receive an already validated `Snapshot`/payload argument from their caller; they do not inspect page block/group shapes or dispatch by arbitrary schema. Existing article code passes its unchanged article payload, while the service wrapper passes its closed catalog payload. Existing article create/replay output is a mandatory regression. No generic importer/plugin/handler registry is introduced.

Before creation it requires the existing MAP-001 parent to match a fixed minimal in-code descriptor under the same locks: exact UUID/name/kind/root position/hidden state, primary legacy `/` route, initial revision/state/owner draft/pin/metadata/reservations/audit and exact initial payload. This check does not read or require the articles package and does not require the other19 article aggregates. Missing, partial or changed parent fails closed without mutation. A test proves exact MAP-001 alone succeeds while article pages are absent. For MAP-002 only all-absent creates once; all-exact replays without writes; any partial/conflicting page/route/reservation/audit/sibling-position state refuses.

The catalog package is converted by a closed renderer, not accepted as trusted HTML. It emits only `h2/a/strong/ul/li`, escapes link text and quoted href attributes, and then requires `restricted_clean(output) == output`. Stored links contain only their exact accessible names. Decorative numbering/arrows are catalog-scoped code-owned CSS counters/pseudo-elements; no decorative text/attribute is stored and the shared editor/sanitizer policy is not broadened. Tests prove no event/style/script/class/on*/aria attributes or non-internal-path injection become reachable. No arbitrary Django template, Python or JavaScript is stored.

No `PageGrant` is created. The page remains owner-controlled and hidden in this slice; employee assignment/editing and publication are not silently introduced.

## Public presentation

The existing public template adds a kind-specific class only when `page.page_kind == services_master_catalog`. `public.css` styles the closed semantic hierarchy to match the approved catalog: wide root heading-card and child tiles, catalog-scoped decorative counters/arrows, 4 columns desktop/3 tablet/1 mobile, visible focus, full untruncated text. No image, hero, intro, form, video, gallery, price or new script/dependency is added.

This slice uses no Playwright per owner decision. CSS layout is checked at source level, but semantic/safe rendering additionally has a Django HTTP oracle with a test-only published fixture built from the validated catalog payload: HTTP200, catalog class only for the correct kind, exact58 hrefs/accessibly named links in order, five groups and no partial/unsafe output. Production MAP-002 remains hidden. Real-browser acceptance is not claimed; TEST-10 remains later.

## Приёмочные сценарии до кода

- `MIGE-001`: host validator pins MAP/RTE/source SHA/H1 and proves exact5 groups/exact58 decoded names+paths+order; missing/extra/reordered/group-shift/name/path/entity variants fail with labelled errors.
- `MIGE-002`: validator accepts only exact allowlisted contained regular non-link MAP/RTE/source/package files, bounded before read, strict UTF-8 and read-only/no network/no child; path escape/link/nonregular/oversize/CR/UTF-8/duplicate-key cases fail. Package is closed v1, one exact page/group shape, canonical UUIDs/positions/counts, SHA/cap20KiB; unknown keys, wrong types/counts/source facts fail closed.
- `MIGE-003`: all names are escaped plain text and every href equals a pinned internal path; quote/script/event/style/class/on*/aria/scheme/query/fragment/backslash/control mutations cannot reach output. Shared editor/sanitizer attribute policy is unchanged.
- `MIGE-004`: renderer emits only `h2/a/strong/ul/li`, exact5 roots+53 children with accessible names containing no presentation numbers/arrows, and `restricted_clean(output)==output`; exact H1/title/empty intro/description/no price/media are preserved. Decorative numbers/arrows exist only in kind-scoped CSS.
- `MIGE-005`: disabled flag, non-test environment, wrong configured DB/user and wrong actual `current_database/current_user` stop before package/locks/mutation; exact active owner is required.
- `MIGE-006`: standalone fixed descriptor proves exact MAP-001 parent without reading articles package or requiring other article aggregates; exact parent alone permits create and is never rewritten, while missing/non-exact parent refuses with full state unchanged. No child service pages/routes or grants are created.
- `MIGE-007`: all-absent catalog creates one hidden complete aggregate+legacy primary route+initial revision/state/owner draft/pin/metadata/reservations/audit; public tree excludes it.
- `MIGE-008`: exact replay has zero mutation; partial aggregate, UUID/route/target/sibling/audit/reservation collisions and extra related rows fail closed with full state unchanged.
- `MIGE-009`: late synthetic failure rolls back the catalog aggregate completely while preserving the pre-existing parent and all prior state; two real concurrent calls yield one create and one exact replay.
- `MIGE-010`: Django HTTP with test-only published fixture returns200 and exact five semantic groups/58 safe ordered href+accessible-name links; catalog class applies only to `services_master_catalog`, with no partial output. Source assertions cover visible focus and CSS4/3/1/no fixed-height-or-ellipsis. Other page kinds and existing public tests are unchanged.
- `MIGE-011`: focused host/Python tests, unchanged shared editor-policy regression, existing article migration create/replay tests, relevant public tests, full guard, Django check, migration no-changes and diff-check pass; test foundation is stopped afterwards.
- `MIGE-012`: no persistent/local/production apply, publication, live-site access, media transfer, model/migration/dependency/API/command/cache/worker/scheduler addition occurs.

## Порядок реализации после plan approval

1. Host validator and canonical small package.
2. Failing focused tests for package/render/gates/replay/rollback/concurrency and public CSS/template contract.
3. Minimal extension of existing writer, closed catalog renderer and catalog-scoped public CSS; shared HTML policy remains unchanged.
4. Focused tests, then full regression guard and independent code review.
