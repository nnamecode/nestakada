# DEV-12 — минимальный план реализации core-главной

Статус: repeat independent plan review `APPROVED` в D-839, P1/P2/P3=0. Product code не начат; требуется отдельное разрешение владельца на `DEV12-IMP-001–008`.

Основание: D-145/D-146/D-208/D-222–D-235, D-254–D-256/D-290/D-300, D-834–D-837, `docs/dev12-home-scope-proposal.md`, H12-AT-001–010 и применимость RSP-AC D-835/D-836.

## 1. Результат и жёсткая граница

Собрать `/` в существующем public host из current verified `Page(kind=home)` revision: утверждённые core-секции v4, exact восемь service cards, шесть price groups максимум по восемь rows, шесть DEV-10 work cards и локальные `ОТЗЫВЫ` + `/reviews`. Существующие Header/Footer/navigation/SEO/media/version/Stable/concurrency механизмы переиспользуются.

Не создавать page-builder, block model/table, API, cache, queue, worker, scheduler, background refresh или второй version store. `es-service-contact`, форма/POST/PII, contact/social/QR, Яндекс/YouTube/analytics/external requests и real AutoRepair profile отсутствуют. Live/persistent apply/publication/VPS/HTML reserve не входят.

## 2. Authority и canonical input

- D-235 и `work/public-light-v4.html` — authority для порядка, видимых текстов и локальной композиции, с явными D-835 exceptions.
- `docs/analytics-route-map.csv` и уже принятые exact DEV-09 packages — authority существующих route/page identities; DEV-10 package — authority gallery album/page/file identities.
- Новый bounded `app/content/dev12_home_profile.json` — только проверенный migration input для создания первой home revision с профилем, не runtime source истины. После save/render единственный concrete authority — payload выбранной `PageRevision`; package не читается публичным запросом.
- Host validator фиксирует exact paths+SHA утверждённого v4 artifact, route map, перечисленных DEV-09 packages, DEV-10 package и каждого используемого design/media file. Никаких glob, directory scan, network, HTML execution или fuzzy URL/name matching.
- Начальный профиль связывает только уже существующие canonical `Page`/price-row UUID. Для ещё не перенесённой услуги строка имеет `source_page_id=null` и `source_row_id=null` и показывает явно сохранённый fallback. Null binding не ищет источник по URL/имени; позднее связывание — только explicit owner save. Это не выдаётся за завершённый dynamic source до появления источника.

## 3. Совместимое хранение

`page-content-v1` получает одно optional home-only поле `home_profile`. Старые snapshots без поля продолжают проходить неизменными; поле запрещено для всех `page_kind != home`. Внутри обязательно `schema=home-profile-v1` и exact keys; неизвестные/missing/duplicate keys, неверный тип, control chars, over-cap, внешний/query URL или неканонический UUID отклоняют весь snapshot.

Профиль ограничен:

- exact 8 advantages; 3 comparison cards, до 5 bullets в каждой; exact 5 process steps;
- exact 8 services;
- exact 6 price groups, 1–8 rows в каждой;
- exact 6 works;
- один local reviews descriptor;
- не более 32 profile image references, только на UUID из существующего `embedded_images`; общий media cap существующего public projection не повышается;
- plain labels до 160 символов, descriptions до 500, bullets до 300, URLs до 300 и только canonical internal absolute-path без query/fragment; числовые суммы не парсятся из свободного HTML.

Service/work/price item хранит stable local item UUID, fallback label/price text/internal URL/image reference, `fallback_visible` boolean и nullable binding. Binding либо полностью null, либо содержит exact canonical source Page UUID; price binding дополнительно exact source row UUID. Profile schema запрещает partial binding, duplicate item/source-row binding и повтор local item UUID.

Код владеет schema/caps/protected section order и шаблоном. Все concrete labels, amounts, paths, IDs и fallback находятся только в revision. Рендер/GET/HEAD/source delete/publication change никогда revision не изменяют.

## 4. Owner edit и версии

- Узко расширить existing page-editor input/check/save pipeline полем `home_profile`; оно предлагается только owner и только `kind=home`. Employee context никогда не содержит поле, direct forged employee request отклоняется до mutation.
- UI — закрытые повторяемые поля утверждённых fixed counts, без выбора template/CSS/JS/HTML. Binding выбирается только из bounded eligible current sources; сервер не доверяет submitted label/URL как доказательству источника.
- Existing operationId/check receipt, CSRF, session/generation, base revision, normalization, media evidence, transaction, automatic version, ten ordinary versions, manual/Stable, restore и optimistic concurrency сохраняются.
- Successful explicit owner save сохраняет проверенные owner-submitted static label/path/image fields, а после coherent source check фиксирует только server-derived bound price `amount/from` и source visibility как новый fallback. Если source успел измениться между check и commit, save отклоняется как stale, а не сохраняет смешанное состояние. Source projection при GET не записывается. Restore возвращает весь профиль/fallback из выбранной версии; Stable не наследуется автоматически.
- AssetUsage для profile images проходит существующий revision/draft/current lifecycle; deletion/pruning ordinary versions не удаляет Stable files. Employee grants не расширяются.

Dynamic fallback facts для bound items (`amount/from`, visibility) сервер выводит из coherent source capture; submitted JSON не является их доказательством. Static label/path/image остаются явным owner input и никогда не выводятся из source автоматически. Exact selected-source digest включается в существующий `CheckContext` и signed check receipt. Перед commit тот же helper под общим lock order content→auth повторно захватывает выбранные Pages, PRIMARY routes, states, current revisions и price rows; mismatch с receipt даёт stale/zero mutation. Профиль допускает максимум 64 unique selected sources (`cap+1=65`). Owner candidate picker использует owner-only bounded search: query до 100 символов, page size 20, fetch 21 для `has_next`, deterministic `(path,id)` order; без bulk list, external URL lookup или fuzzy auto-binding. Delete guard использует тот же capture/digest/visibility helper.

## 5. Public projection

Один home-specific pure projector принимает уже coherent public page revision и делает bounded capture связанных источников:

1. из profile собирает non-null unique source Page IDs и price row IDs;
2. одним bounded набором читает exact Pages/routes/current states/current revisions; hard caps: 64 Pages, 64 primary routes, 64 states, 64 revisions;
3. каждый source payload проходит existing strict schema/hash/current/page-kind verification;
4. source никогда автоматически не меняет service/work label, target, image/photo count либо price label/target: эти поля всегда owner-versioned в home profile. Только exact bound price-row `amount/from` проецируется динамически по D-255. Source visibility может скрывать связанную карточку/строку по D-256;
5. missing/deleted source использует revision fallback и `fallback_visible` по D-300; новый объект с тем же URL/name не связывается;
6. повторный identical capture и row-version digest обязаны совпасть, иначе весь response 503/no-store без partial body.

Unbound item всегда использует explicit saved fallback и помечается внутренне как unbound; это не auto lookup. Empty price group скрывается, если его bound items временно hidden; если все groups пусты, price section отсутствует. Удалённый source target не воскресает: fallback может сохранить approved display/path, но сам удалённый exact URL обслуживается обычным 404 route contract.

Чтобы ветвь visible→deleted сохранила последний вид, а hidden→deleted не вернула старую карточку, existing page-delete preflight получает bounded dependency guard: связанный source нельзя удалить, пока home revision fallback fields/`fallback_visible` не совпадают с coherent current projection источника. Владелец сначала явно сохраняет предложенную синхронизацию главной либо снимает binding, затем повторяет обычное подтверждение удаления. Delete transaction profile не меняет. Race после preflight закрывается повторной проверкой under lock; stale state отклоняет удаление целиком. Это расширение проверки удаления, не cascade и не новая dependency table.

Gallery works используют exact DEV-10 album IDs только для identity/visibility/delete guard; label/photo count/target/image берутся из owner-versioned home profile и не обновляются автоматически. Media files проходят existing contextual authorization, READY variant, physical verify, capture/recapture и общий cap; missing/corrupt/conflict даёт fail-closed 503, не partial layout.

Verified legacy home revision без `home_profile` — допустимая совместимая ветвь: `/` продолжает existing generic body render с обычными SEO/shared/media boundaries и без новых core-секций. Это не 500 и не частичная сборка home profile. Restore profile→legacy возвращает этот legacy view; только новый explicit owner save с valid profile снова включает core template.

Home template emits только Django-escaped plain text, fixed semantic tags и validated internal href. Rich text проходит только существующие safe fields/renderer. Никакие profile strings не становятся template name, class, style, script, SVG markup или `safe` HTML.

## 6. CSS и JavaScript

- Перенести только используемые v4 rules в home-scoped `public.css`; не копировать form/contact/map/external-review rules. Existing shared header/footer styles не дублировать.
- Один fixed local script: mobile menu и price tabs. Без fetch/XHR/WebSocket/storage/cookie/eval/Function/dynamic import/`innerHTML`; ссылки работают без JS, а все price groups доступны в no-JS layout.
- CSP остаётся local-only. Script обслуживается GET/HEAD, POST=405, exact content type/nosniff/cache policy; никакого inline script.

## 7. Initial package и writer

Default-off exact UNIT-only writer расширяет существующий DEV-09 apply path отдельной home operation:

- first SQL подтверждает UNIT identity; locks в существующем порядке content→auth;
- требует exact canonical home UUID/route `/`/kind/parent/position и current known revision; не создаёт вторую home page;
- проверяет все non-null bindings и уже READY media descriptors под lock;
- exact-before отдельно проверяет `OwnerDraft`: допустимы отсутствие draft либо draft, точно зеркалящий known current payload/hash/base. Mirror draft в той же DB transaction переводится на новый payload/hash/base, увеличивает revision, переносит pin на новый base и синхронизирует draft usages. Реально изменённый owner draft отклоняет operation без mutation;
- создаёт ровно одну automatic owner-authored revision/profile и синхронно current/version AssetUsage, а при mirror draft также draft usage/pin, в одной DB transaction;
- допускает только exact before → create либо exact after → zero-write replay; mixed/unknown state отклоняет;
- late failure полностью откатывает revision/state/draft/base pin/все затронутые usage ledgers; exact-after/replay включает их полное состояние; два concurrent запуска дают one create + one replay;
- не меняет publication, grants, source pages, source prices, aliases или files и не выполняется persistent/local-main автоматически.

Design media import — отдельная exact deterministic operation до home writer. Она переиспользует существующий lifecycle `STAGED → write_file → mark_ready`, фиксированные UUID/SHA/MIME/size/dimensions и idempotent exact replay. Сбой после physical write оставляет проверяемое recoverable STAGED состояние; повтор либо завершает тот же exact asset, либо безопасно отказывает при mismatch. DB rollback не объявляется откатом blob, orphan/mismatched file не замалчивается. Home writer файлов не создаёт и потребляет только уже READY exact assets. Нельзя создавать новый media subsystem. Canonical package и media paths добавляются в foundation только точными именами, без wildcard.

## 8. Приёмка до и после кода

| ID | Обязательное доказательство |
|---|---|
| DEV12-AT-001 | Legacy home snapshot без profile и все non-home snapshots остаются valid; profile на non-home, malformed/duplicate/over-cap/external/query inputs rejected. |
| DEV12-AT-002 | Exact canonical package даёт 8/3/5/8/6×1..8/6/local-review counts и только approved D-835 composition; host SHA/selfchecks PASS. |
| DEV12-AT-003 | Owner check receipt включает selected-source digest; final under-lock recapture, cap65 и drift rejection доказаны. Save/replay/draft/restore/Stable/concurrency сохраняют profile; employee/forged/direct request denied with zero mutation. |
| DEV12-AT-004 | Только bound price amount/from обновляется без home write; service/work и price label/target/image остаются owner-versioned. Hidden следует D-256; republish same ID returns. Delete guard требует exact saved current fallback+visibility: visible→deleted сохраняет вид, hidden→deleted остаётся hidden; race rolls back; reused URL/name не захватывается. |
| DEV12-AT-005 | Unbound rows never query by URL/name and render saved fallback; later binding changes only through owner save/version. |
| DEV12-AT-006 | Exact 8 services, 6 groups≤8 and 6 DEV-10 works have owner-versioned internal targets/order; source changes cannot rewrite labels/targets/images/counts; unknown/duplicate/mixed binding closes projection. |
| DEV12-AT-007 | Capture race/ABA, cap+1, schema/hash/current mismatch, corrupt/missing media give 503/no-store and no partial/canary body. |
| DEV12-AT-008 | GET/HEAD `/` bytes/headers coherent; POST rejected; hidden/damaged home follows existing contract; SEO/nav/header/footer regressions pass. |
| DEV12-AT-009 | HTML has no form/contact/map/Yandex/YouTube/social/QR/external request/real AutoRepair; only local `ОТЗЫВЫ` and exact `/reviews` link. |
| DEV12-AT-010 | Fixed JS/no-JS, keyboard/focus/aria and static CSS matrix satisfy applicable RSP AC; deferred AC remain N/A, no Playwright. |
| DEV12-AT-011 | Separate STAGED→physical→READY media import covers failure-after-write/recovery/replay. Home writer consumes READY only; absent/mirror/changed draft, pin/usages, create/replay/mixed/rollback/concurrency and exact foundation manifest pass. |
| DEV12-AT-011A | Current legacy home without profile, restore profile→legacy and later explicit save legacy→profile return safe exact views without 500/partial output. |
| DEV12-AT-012 | Focused tests, public/shared regression, full guard, Django check, `makemigrations --check --dry-run`, host checks and `git diff --check` pass with exact no-wildcard test paths. |

## 9. Реализация по ограниченным патчам

1. `DEV12-IMP-001`: exact read-only authority inventory; canonical package/tool/selfchecks; measured caps. Product runtime unchanged.
2. `DEV12-IMP-002`: optional home-only schema/profile validator and compatibility tests.
3. `DEV12-IMP-003`: owner-only existing editor field, bounded candidate search, signed source digest/check/save/version/restore tests.
4. `DEV12-IMP-004`: separate exact media lifecycle import, then default-off READY-only UNIT home writer with draft/pin/usage atomic tests.
5. `DEV12-IMP-005`: pure bounded source/home projector и bounded delete dependency guard с D-256/D-300/race tests.
6. `DEV12-IMP-006`: fixed template/CSS/local JS and HTTP/security/accessibility tests.
7. `DEV12-IMP-007`: exact focused/public/shared/full guard and system/migration/diff checks.
8. `DEV12-IMP-008`: independent code review, remediation and final repeat review.

После каждого патча запускать только его exact tests; full guard один раз после завершения кода и повторно только если remediation затрагивает общую границу. Playwright и поисковые wildcard не использовать. При второй эквивалентной ошибке остановиться по anti-loop и сообщить владельцу.

## 10. Gates

1. Independent plan review и исправление findings.
2. Final `APPROVED` плана.
3. Отдельное owner approval начала `DEV12-IMP-001–008`.
4. Product patches, проверки и independent code review.

До gate 3 product code запрещён.
