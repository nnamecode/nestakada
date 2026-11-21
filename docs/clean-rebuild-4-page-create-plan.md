# REBUILD-4 — bounded owner Page create slice

Дата: 2026-11-20. ID: `RB4-SLICE-004D-PAGE-CREATE`. Статус: **D-1798 source implemented and independently APPROVED P0/P1/P2=0/0/0; PostgreSQL runtime not started and requires a separate reviewed run plan/owner permission**.

## Purpose and boundary

Это отдельный документационный этап после source-complete Page Move. Runtime Page Move остаётся приостановленным по anti-loop D-1793/D-1794; этот план не возобновляет его и не использует его runtime evidence.

Срез добавляет только owner-only создание одной новой скрытой `Page` с заранее созданным caller UUID, одним из уже утверждённых `PageKind`, exact name, optional existing parent и свободным exact PRIMARY path. Новая Page добавляется в конец выбранной sibling group. Создание arbitrary position не входит: после create для этого существует отдельный Move. Page сразу получает один schema-valid current payload, `previous=null`, generation1 и media usages0.

Новая Page всегда `is_published=false`. Create не публикует, не выдаёт PageGrant, не загружает media, не создаёт gallery composition, alias/redirect, child Page, slug, arbitrary initial content или второй workflow. Rename/move/reorder/publication/URL/delete остаются отдельными командами. Browser/live/deploy/push, Page Move runtime и B002 закрыты.

Срез переиспользует `Page`, `Route`, `PageContent`, `SiteSettings.structure_generation`, current+previous contract, existing content validator/hash, audit `PAGE_CREATED`, private/no-store ingress и public unpublished visibility. New model/migration/dependency/receipt/identity-reservation/xmin token/cache/background task/JavaScript/API/generic lifecycle framework нет.

## Fixed initial content contract

Один pages-owned pure builder создаёт initial payload для каждого literal member текущего `PageKind.values`; отдельного editable schema registry не появляется. Envelope exact:

```text
schema = "estakada.page-content"
schema_version = 1
kind = selected kind
fields.seo = {title: exact Page name, description: "", allow_index: false}
fields.heading = {h1: exact Page name}
```

До построения payload exact authority invariant требует `len(PageKind.values)==19`, `len(set(PageKind.values))==19` и `set(PageKind.values)==set(FIELD_SETS)`. `RICH_BY_KIND` и `MEDIA_SLOTS` могут быть только subsets этого exact set; каждый kind с полем `media` обязан иметь ровно одну `MEDIA_SLOTS[kind]`, а kind без поля `media` не может иметь media mapping. Остальные обязательные поля выводятся только из этих existing closed registries: rich fields — empty string; refs/steps/actions/reviews/links — empty list; price rows — empty columns/rows; every `hero` slot — null, other media slots — empty list. Builder обязан пройти existing `validate_payload(payload, kind)` и получить media set0; canonical hash вычисляется existing `canonical_payload_hash`. Unknown kind, любой registry drift, non-empty usages or invalid payload fail closed before write.

Имя как initial SEO title/H1 и `allow_index=false` являются предлагаемым минимальным create default. Это не меняет редактор: после создания owner может отдельно отредактировать current content, а publication остаётся отдельным решением.

## Command and transaction contract

Одна команда:

```text
create_page(
  actor_id,
  session_generation,
  page_id,
  base_structure_generation,
  kind,
  name,
  parent_id,
  primary_path,
) -> CreateResult(page_id, structure_generation, content_generation, current_hash, replayed)
```

До transaction команда принимает только UUID-compatible non-bool `page_id`, optional UUID-compatible non-bool `parent_id`, exact positive non-bool base, literal current `PageKind`, create-name length1..255 с остальными exact canonical `validate_page_name` rules и closed public PRIMARY path. `page_id == parent_id` запрещён. Усечение имени отсутствует; общий later rename по-прежнему может использовать model cap500, но initial create обязан одновременно поместить exact name в SEO title/H1 cap255. Path — NFC string 1..2048, начинается одним `/`, без scheme/netloc/query/fragment/backslash/control/whitespace/malformed percent encoding и decoded `.`/`..` segments. После strict percent validation server один раз получает decoded path только для validation: он не может быть exact `/manage` или начинаться `/manage/`, включая raw/encoded slash or letters such as `/%6danage/` and `/manage%2F...`. Stored target остаётся exact submitted string; decode/re-encode, trim, case folding, slash completion, slugification или redirect guess не выполняются. Exact uniqueness относится ко всему `Route.target` namespace.

Одна outer `transaction.atomic()` использует lock order `User -> SiteSettings -> Page rows by UUID -> PageContent -> Route namespace check/write -> audit`. Active OWNER проверяется до structural reads; EMPLOYEE получает `FORBIDDEN` без SiteSettings/Page/Route/audit access. Затем блокируется singleton SiteSettings. Exact stale rejection выполняется только после bounded existing-UUID replay branch ниже: это делает immediate lost-response replay достижимым.

После settings lock команда читает максимум513 Page rows в stable UUID order. Count513 даёт unavailable. Для count<=512 полный in-memory parent graph обязан иметь existing/null parents, no self/cycle. Из него определяется наличие target UUID, requested parent и полный requested-parent/root sibling set. Затем target/parent/siblings блокируются одним deduplicated `select_for_update().order_by("id")`; после lock exact revalidation повторно сверяет target existence, parent relation, complete sibling membership и every position с discovery snapshot. Empty sibling group даёт new position0.

Далее команда проверяет replay до обычного stale rejection:

1. если Page UUID отсутствует — обычный create path;
2. если Page UUID существует, команда `select_for_update` блокирует его PageContent до чтения payload/usages и требует ровно один PRIMARY Route, ровно один PageContent и ровно один `PAGE_CREATED` audit для target UUID. Audit detail generation обязан равняться `base_structure_generation+1`, а locked current structure generation — быть не меньше audit generation. Exact `kind`, name, requested parent, PRIMARY path, unpublished state, current payload/hash/generation1/provenance actor, previous all-null, last-operation all-null и media usages0 должны совпадать с deterministic requested composition. Append-at-create invariant требует, чтобы target position был exact `max(sibling positions excluding target)+1`, либо0 при пустом remainder; changed/moved/reordered target therefore is not guessed as replay;
3. exact composition+audit proof возвращает existing DTO with audit generation and `replayed=true`, не увеличивает current structure generation и ничего не пишет; incompatible kind/request или любая mismatch/corruption даёт fixed conflict/unavailable, writes/audit0. Audit lookup — только bounded exact target/action proof, не общий receipt store;
4. только если Page UUID отсутствует, command требует `SiteSettings.structure_generation == base_structure_generation`; mismatch даёт `STALE_STRUCTURE`, mutation/audit0.

Для нового UUID optional parent должен существовать в уже discovered and revalidated locked graph. New position is `max(existing positions)+1`, а не sibling count; duplicate/gapped existing positions не нормализуются create-командой. Position overflow даёт typed unavailable. Existing non-deferrable unique `(parent, position)` остаётся authority; concurrent creates on one base have at most one winner because SiteSettings is global CAS.

После locked path namespace absence check transaction создаёт ровно Page, PRIMARY Route (`mode=PRIMARY`, `outcome=kind`) и PageContent generation1/current/provenance current actor+now, previous all-null, last-operation all-null. `full_clean()`/existing validators применяются к Route and content inputs before save. AssetUsage rows не создаются. Затем `structure_generation` растёт ровно на1 и пишется один safe `PAGE_CREATED` с target Page UUID и detail только `{"generation": new_structure_generation}`. Любой Page/Route/content/settings/audit/constraint fault откатывает весь aggregate.

## Fixed private HTTP

Один owner-only no-JavaScript endpoint `GET|POST /manage/pages/new/`:

- GET после immediate OWNER check в short transaction блокирует SiteSettings и читает at most513 Page rows в stable UUID order. Graph обязан иметь existing/null parents, no self/cycle. Сервер заранее генерирует canonical lowercase UUID `page_id`; form содержит exact hidden `page_id` and `base_structure_generation`, text `name`, closed `<select name="kind">`, closed `<select name="parent_id">` (`root` или canonical UUID) и text `primary_path`. Locks освобождаются до render;
- POST принимает only `application/x-www-form-urlencoded`, files0, exact single six command fields plus optional single CSRF. UUIDs canonical lowercase hyphenated; base canonical positive ASCII decimal; parent only `root` or canonical UUID. Duplicate/unknown keys, noncanonical tokens, wrong content type, multipart/file and body over4MiB give fixed400 before command;
- success302 идёт в existing editor новой Page. Exact replay success also302. Closed status mapping: malformed/noncanonical UUID/base/name/kind/parent token/public path and wire violations return fixed400 before command; stale generation, occupied path, unknown/self parent and incompatible-but-well-formed UUID reuse return private409 with exactly one reload link to create form; partial/corrupt replay aggregate, missing settings, corrupt/oversize graph, position overflow, registry drift, ambiguous DB or unexpected command fault return constant503;
- employee GET/POST —403 before structural query/command; anonymous/stale session use existing bare-login contract; CSRF failure framework403; valid-CSRF unsupported method —405 with `Allow: GET, POST`;
- endpoint входит в existing private/no-store and 4MiB ingress boundary with own fixed `INVALID_PAGE_CREATE_INPUT`. Errors never reflect submitted name/path/UUID.

Only OWNER page list gets one literal `Создать страницу` link. Employee list DOM does not contain it. No slug helper is included in this first slice; architecture permits it only as optional UI helper, so exact manual path keeps the server contract smaller.

## Acceptance before code

| ID | Scenario | Required result |
|---|---|---|
| `RB4-CRT-001` | anonymous/stale/EMPLOYEE GET+POST, employee list and direct command | existing bare-login/403 before structural query/mutation; employee DOM has no create link; SiteSettings/Page/Route/audit access0 |
| `RB4-CRT-002` | OWNER creates each of exact current 19 PageKind values; name length255/256 | exact registry equality/subsets hold; each kind yields one unpublished Page+PRIMARY+valid current generation1/hash/provenance; previous/last-operation null; usages0; structure generation+1; one safe `PAGE_CREATED`; 255 accepted, 256 fixed invalid without truncation |
| `RB4-CRT-003` | root and existing parent with empty/gapped sibling positions | append at exact `max+1`; unrelated positions unchanged; no implicit reorder/normalization |
| `RB4-CRT-004` | lost response exact UUID/composition replay with old base after committed generation increment | replay branch precedes stale rejection; exact audit generation=`base+1`, locked content/usages and append invariant return same DTO `replayed=true`; writes/current-generation/new-audit0 |
| `RB4-CRT-005` | reused UUID with incompatible kind/name/parent/path/state/content/audit or partial aggregate | fixed conflict/unavailable; no guessed repair, disclosure, mutation or new audit |
| `RB4-CRT-006` | occupied Route target, raw/encoded reserved manage path, query/fragment, malformed encoding, dot segment, whitespace/backslash/non-NFC | decoded reservation catches `/%6danage/` and `/manage%2F...` without stored normalization; closed fixed400 vs occupied409; transaction unchanged |
| `RB4-CRT-007` | empty/root/existing/unknown/self parent, corrupt graph, 512/513 Page rows, position overflow | full graph discovery→affected UUID lock→exact membership/position revalidation; empty position0; exact bounded success/fixed409 or503 mapping; no partial aggregate |
| `RB4-CRT-008` | two creates or create versus any structural command on same base | at most one winner; loser stale with writes/audit0; global structure generation invalidates old forms |
| `RB4-CRT-009` | injected Page/Route/content/settings/audit/constraint fault | whole aggregate and generation roll back; Page UUID/path remain free unless pre-existing |
| `RB4-CRT-010` | GET concurrent with structural commit | one coherent old or new generation+parent graph snapshot; mixed form forbidden; generated UUID canonical and stable only within rendered form |
| `RB4-CRT-011` | HTTP wire/domain matrix: canonical/noncanonical UUID/base, invalid name/kind/path, occupied path, unknown parent, duplicate/unknown keys, wrong type/files, >4MiB, CSRF, PUT | exact fixed400/private409/constant503/framework403/405 table; pre-command cases command0 and submitted value reflection0 |
| `RB4-CRT-012` | static scope/DAG inspection and public read | lock order and bounded replay proof exact; unpublished Page absent publicly; models/migrations/dependencies/JS/API/cache/receipt/media rows/public renderer changes0 |

Focused source target: exact12 test methods, proposed command/domain8 plus HTTP4, with subtests covering exact19 kinds and closed matrices. Exact test count, PostgreSQL concurrency/constraint evidence and regression cohort require a separate reviewed run plan and fresh explicit owner permission after source review.

## No-bloat and stop line

If correct create requires a model/constraint change, generic Page lifecycle service, OperationReceipt/IdentityReservation, writable kind/schema registry, automatic slug/redirect, navigation table, arbitrary initial rich editor, media upload, JavaScript wizard or background workflow, stop before code and request a new architecture decision. This slice must not absorb reorder/publish/URL/delete/gallery/media operations.
