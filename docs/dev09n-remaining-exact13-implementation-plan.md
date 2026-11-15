# DEV-09N exact13 — минимальный implementation plan

Дата: 2026-11-15. Статус: **first review CHANGES_REQUESTED 0/2/0; remediation ready, repeat review pending; product code not started**. Scope authority: D-1095 и `docs/dev09n-remaining-exact13-scope-proposal.md`. Review: `docs/dev09n-remaining-exact13-plan-review.md`.

## Результат

Локально создать 13 hidden Page aggregates и exact7 READY media, доказать их replay/rollback/public projection на изолированной test DB. Persistent apply, publication, live/VPS и TEST-08 fixture не входят.

## Точные артефакты

Новые runtime/data/test files:

- `app/content/dev09n_remaining_content.json` — один closed package exact13/exact7;
- `scripts/check-dev09n-slice.mjs` — read-only host validator fixed authorities;
- `app/content/test_dev09n_remaining_content.py` — package/media/writer/public focused tests.

Изменяемые existing files:

- `app/page_versions/schema.py` — только optional `contacts_profile` для `Page.Kind.CONTACTS`, exact keys/values/caps;
- `app/content/dev09_migration_apply.py` — package loader/renderer, exact7 prepare/recovery, all13 writer/replay;
- `app/content/public_views.py` — typed contacts DTO and actions/reviews/contacts projection only;
- `app/content/templates/content/public_page.html` — three closed kind branches;
- `app/content/public.css` — kind-scoped responsive rules;
- `scripts/test-editor.ps1` — exact existing `dev09-services` suite addition;
- `scripts/local-foundation.ps1` — one literal package path/name in exact allowlists;
- stage documentation.

Любой иной product file требует остановки и amendment review. Новых model/migration/dependency/command/API/cache/worker/scheduler/JS files нет.

## Package contract

Schema `dev09n-remaining-content-v1` содержит exact13 ordered pages и exact7 media. Каждая page фиксирует literal UUID/MAP/URL/kind/parent/position/name/H1/title/description/source path+SHA, hidden status и discriminated profile:

- legacy/news: closed paragraph/list/link blocks; empty pages имеют exact empty blocks;
- actions: exact2 cards, fixed text/order and MED-0001/0002 image IDs;
- reviews: exact10 title+HTTPS video links, no remote image/embed;
- contacts: exact visible phone/address/hours/email, exact tel/mailto/HTTPS route link and MED-0004–0008 image IDs.

Package не хранит raw HTML, template fragments, Python или JavaScript. Pre-read caps по классам: package128 KiB; route-map128 KiB; route-evidence256 KiB; media-evidence256 KiB; каждый source/artifact128 KiB; каждый exact media256 KiB; все exact7 media вместе2 MiB. Structural caps: pages13/media7 exact; blocks64/page; links16/page; text leaf8 KiB; rendered body64 KiB/page; total rendered512 KiB. Для каждого числового класса synthetic exact-cap passes, cap+1 fails before parse/hash/write; actual pinned inputs дополнительно обязаны совпасть с exact bytes/SHA.

Host validator pins route map/evidence/media evidence SHA plus exact source/artifact/local media SHA, rejects symlink/traversal/non-regular/CR/invalid UTF-8/duplicate keys and performs writes/network/child-process0.

## Contacts typed boundary

`schema.validate()` permits `contacts_profile` iff `page_kind == contacts`. Exact keys: `phone_display`, `phone_href`, `address`, `hours`, `email_display`, `email_href`, `route_href`, `gallery_heading`. Values are package-authorized literals; `phone_href` exact `tel:+74991102552`, email href exact approved `mailto:`, route HTTPS with no userinfo/control/fragment. Unknown keys, other kinds, arbitrary tel/mailto, `javascript:` and `data:` fail `VERSIONS_INVALID_SNAPSHOT`.

Employee fields remain unchanged; this profile is owner/protected payload data and is never accepted from generic rich HTML. Public template receives a copied validated DTO, never reads package at runtime and never hardcodes contact values.

## Media protocol

`import_remaining_media(source_root, storage)` reuses existing MediaFolder/Asset/AssetFile/write_file/mark_ready lifecycle:

1. verify all seven source bytes/SHA before DB work;
2. create/replay/recover exact folder/assets/files independently to READY;
3. reject changed descriptors/manifest and non-STAGED/READY state;
4. interrupted execution may leave only exact recoverable STAGED/READY over-preparation;
5. no Page or public usage is created here.

`apply_remaining_content(storage)` first verifies physical manifests, then identity SQL and locks content→auth, recaptures exact READY descriptors, checks parents/positions/routes and performs one DB transaction for all13 Page/Route/revision/state/draft/pin/reservation/audit/usages. Exact replay writes0; mixed/extras refuse; late13/concurrency leave no partial Page aggregate. Prepared unused assets are not public.

## Public projection

- exact10 legacy/news use current generic body;
- actions branch renders exact2 local authorized images and text;
- reviews branch renders exact10 HTTPS anchors only; remote resources/iframe/script0;
- contacts branch renders typed facts/links and exact5 local images in a static grid; form/map embed/social/JS0;
- malformed typed profile/media/usage gives coherent503 before partial HTML;
- existing Header/Footer, breadcrumbs, navigation, canonical, sitemap, robots, GET/HEAD, 405, CSP/cache contracts remain unchanged.

## Срезы реализации

1. `DEV09N-IMP-001 — canonical data`: generate exact JSON only from pinned authorities; host validator syntax/selfcheck/actual PASS; independent data review before writer use.
2. `DEV09N-IMP-002 — failing schema/package tests`: add focused negatives for closed keys/caps/contacts schemes and exact13/exact7 identity; no product behavior yet.
3. `DEV09N-IMP-003 — contacts schema`: minimal `schema.py` addition, schema tests PASS; no sanitizer change.
4. `DEV09N-IMP-004 — exact7 media`: after owner code gate and fresh foundation, first add focused prepare/replay/recovery/physical/descriptor tests to `dev09-services` and record expected RED; only then minimal media code and GREEN of the same named suite.
5. `DEV09N-IMP-005 — all13 writer`: first add focused parent/atomic aggregate/usages/replay/mixed/late/concurrency tests and record expected RED through `dev09-services`; only then closed renderer/writer minimal code and GREEN.
6. `DEV09N-IMP-006 — public projection`: first add exact route/content/media/security/SEO/navigation tests and record expected RED through named `dev09-services` plus the individually affected public suite; only then three kind branches/template/CSS minimal code and GREEN; JavaScript0.
7. `DEV09N-IMP-007 — bounded verification`: only named wrapper suites `dev09-services`, `dev12-schema`, `public-read`, `public-http`, `public-nav`, `dev11`, `check`, `migrations`; no wildcard/direct broad manage.py/Playwright. Run only after fresh foundation calibration; host/Docker failure is environment evidence, not product failure.
8. `DEV09N-IMP-008 — independent code review`: P1/P2/P3, bounded remediation, repeat affected named suites; final approval still does not authorize persistent apply/publication.

## Stop and gates

First failure records cause and changed condition. Second equivalent failure stops without third attempt. Plan review is read-only. After plan `APPROVED`, owner must separately approve `DEV09N-IMP-001–008`; until then JSON/code/config/test execution are forbidden.
