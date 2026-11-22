# REBUILD-4 — confirmed ordinary leaf Page delete plan

Дата: 2026-11-21. ID: `RB4-SLICE-004F-PAGE-DELETE`. Статус: **source complete D-1838; plan and final source review APPROVED0/0/0; exact12/diff-check PASS; Docker/PostgreSQL runtime0 pending separate reviewed run plan and explicit owner permission**.

## Purpose and authority

Это следующий независимый незаблокированный инкремент после завершённого Page Create и source-complete Page Reorder. Он реализует только подтверждённое владельцем удаление одной обычной leaf Page по D-047/D-048, D-112, D-1219, D-241 и `PGLC-009..012`.

Успешная операция одной transaction удаляет exact Page, все принадлежащие ей Route, единственный PageContent вместе с `current + previous`, PageGrant и только `PAGE_CURRENT/PAGE_PREVIOUS` AssetUsage этой Page. Один `PAGE_DELETED` audit и новый `SiteSettings.structure_generation` сохраняются. Asset, AssetFile, физические файлы, usages других targets/scopes, audit history, siblings, parent и любые другие Page остаются.

Срез не удаляет subtree, не переносит детей, не нормализует sibling positions, не создаёт redirect/tombstone, не очищает physical media и не переиспользует URL как часть delete. `gallery_album` и любая Page с gallery ownership удаляются только будущей gallery-owned командой; обычная pages-команда отказывает. URL/public navigation после commit являются обычной read projection: бывшие exact routes отсутствуют и возвращают 404.

В scope нет model/migration/dependency, generic lifecycle/workflow, receipt/identity table, background cleanup, JavaScript/modal, bulk delete, API, B002, Docker/runtime, browser, live/deploy или push.

## Fixed command contract

Одна публичная pages-owned команда для обычной Page:

```text
delete_leaf_page(
  actor_id,
  session_generation,
  page_id,
  base_structure_generation,
  expected_name,
  expected_primary_path,
  expected_composition_digest,
  current_password,
) -> DeleteResult(page_id, structure_generation, already_deleted)
```

До DB команда принимает только UUID-compatible `page_id`, positive non-bool integer generation, exact strings name/path/password и lowercase 64-hex digest. Name ограничен модельным максимумом500, PRIMARY path2048, password4096. Ничто не trim-ится, не нормализуется и не отражается в ошибке или audit. Password никогда не входит в DTO, digest, log или exception detail.

Outer `transaction.atomic()` использует порядок:

1. `lock_staff_session(actor_id, session_generation)` и active OWNER check;
2. повторная проверка `actor.check_password(current_password)` на уже locked User;
3. singleton `SiteSettings` lock;
4. lookup/lock exact target Page by UUID;
5. if Page is absent, bounded audit replay branch described below, before ordinary stale-CAS;
6. if Page exists, exact `locked SiteSettings.structure_generation == base_structure_generation` before any composition/media lock;
7. direct-child absence query under the same structural lock;
8. Route → PageContent → PageGrant в стабильном UUID order;
9. media participant locks exact expected+actual Asset union, затем exact Page AssetUsage rows;
10. deletion, structure generation update and audit append.

Employee/direct non-owner command получает `FORBIDDEN` до SiteSettings/Page/media query. Wrong password получает тот же fixed `CURRENT_PASSWORD_INVALID`, writes0; password hash/session drift is already closed by the locked staff-session contract. Missing/ambiguous SiteSettings is unavailable. For an existing Page, stale structure generation returns `STALE_STRUCTURE` with mutation/audit0 before Route/Content/Grant/media access. Structural writers serialize through SiteSettings, while Page row lock plus FK `PROTECT`/CASCADE and final zero-child proof prevent a late child from being silently included.

## Canonical locked composition

GET preview и POST command используют один pure pages projector над locked rows. Его canonical UTF-8 JSON имеет fixed domain/version `estakada.page-delete-composition@1`, sorted keys, compact separators, NFC-preserving values and no floats; digest is lowercase SHA-256 over those bytes.

Projection includes:

- all Page fields: UUID, exact name, kind, parent UUID/null, position and publication;
- all Route rows sorted by UUID: UUID, mode, exact target and outcome; exactly one PRIMARY is required;
- PageContent generation, current hash/author/time, previous presence and hash/author/time, and all-or-none last-operation fields;
- every PageGrant sorted by UUID: grant UUID, staff UUID and exact ordered groups;
- every own AssetUsage in scopes `PAGE_CURRENT` and `PAGE_PREVIOUS`, sorted by `(scope, slot, position, asset UUID, usage UUID)`;
- child count, which must be exactly zero.

Raw payload, rendered HTML, password, usernames, AssetFile/storage paths and unrelated rows do not enter the digest. Before projection, current and optional previous payloads pass the exact kind schema and canonical hash checks. The expected media maps extracted from both validated payloads must equal the complete locked usage tuples; referenced assets must be exact READY/CONTENT. Missing content, invalid hashes/schema, incomplete previous tuple, missing/multiple PRIMARY, invalid Route outcome, unknown grant groups, usage mismatch, row cap or DB ambiguity fails closed and writes0.

Fixed cap+1 limits are Route512, PageGrant100 and own usages128; children use existence/one-row proof because any child refuses. Their authority is explicit: the accepted import has exact114 Route globally and existing public/tree readers already use the 512 graph ceiling; the only PageGrant writer selects from the existing exact100 active-employee management ceiling and `(staff,page)` is unique; the closed content validator permits at most64 media references in each of current and previous, hence at most128 own usages. A future URL/grant/content writer must preserve these producer ceilings or reopen Page Delete before it can create an undeletable legitimate aggregate. Crossing a cap is `DELETE_UNAVAILABLE`, never truncation. Acceptance covers cap−1/cap/cap+1 for every collection. The preview shows exact escaped name and PRIMARY, route counts by mode, children0, current/previous presence plus hashes, grant count and usage counts by version; it does not expose raw payload, staff identity or asset/storage identity.

Name and PRIMARY are separately typed confirmations even though both are also digest-bound. Any changed Page/route/content/grant/usage/child/generation between GET and POST produces fixed `DELETE_CONFIRMATION_STALE`; the user must reload and confirm the new composition.

## Media and gallery boundaries

The implementation may add only a narrow public media participant for this transaction:

```text
lock_page_usage_snapshot(page_id, expected_current, expected_previous)
  -> immutable exact rows/counts
delete_locked_page_usage_snapshot(snapshot) -> None
```

Both require an existing outer transaction. The first locks the complete expected+actual Asset union and exact two-scope usage set, proves READY/CONTENT and equality; the second deletes only the already locked exact usage UUID set after rechecking target/scopes. Preview calls only the first and writes0. POST uses the same snapshot in the same transaction. Generic target deletion, physical file cleanup and a new service/repository are forbidden.

Pages does not import `gallery`. `Page.kind == gallery_album` returns `GALLERY_DELETE_REQUIRED` before media/delete. An unexpected `GalleryAlbum.page` PROTECT is `DELETE_UNAVAILABLE` with full rollback. Exact static/model-metadata fitness allowlists all Page reverse relations and their deletion policy: `children` PROTECT, `routes` CASCADE, `content` CASCADE, `grants` CASCADE and `gallery_album` PROTECT; any new relation, changed `on_delete` or unexpected auto-created relation fails the build/review before source acceptance. This is a literal fitness assertion, not a runtime generic cascade walker. The later gallery-owned command must first lock/delete its album composition and then call a separately reviewed narrow pages participant; it is not implemented here.

The previously deferred JSON `service_refs/brand_refs/review_refs` lifecycle is not invented by delete. Delete performs no global JSON backref scan and does not infer inbound/outbound semantics. Safety relies on the accepted global invariant: freeze/import/create emit all three arrays empty, and every permitted Save/Undo/editor carrier can only preserve that empty authority and cannot make it nonempty. Static/acceptance evidence covers every allowed writer plus current and previous target payloads, not merely the Page being deleted. Any nonempty global authority or new writer is a stop condition requiring its own target/backref/concurrency decision before Page Delete implementation continues.

## Mutation and retry semantics

After every check succeeds, the transaction:

1. deletes only the locked two-scope AssetUsage snapshot;
2. explicitly deletes only the locked Route, PageContent and PageGrant UUID sets;
3. after an exact zero recheck for those rows and children, deletes Page itself; the static reverse-relation allowlist proves that no unknown CASCADE target can be collected;
4. increments locked `SiteSettings.structure_generation` exactly once;
5. appends exactly one `PAGE_DELETED`, target the deleted Page UUID, detail only `{"generation": new_generation}`.

Any media/delete/settings/audit fault rolls back every row, generation and audit together. Sibling positions deliberately remain unchanged; Page Reorder is the only normalization action.

No receipt or tombstone table is added. After OWNER/password and SiteSettings lock, Page existence is determined before ordinary structure CAS. If UUID is absent, command reads the bounded exact `PAGE_DELETED` audit for that UUID:

- exactly one structurally valid event whose `generation == base_structure_generation + 1` returns `already_deleted=true` and that recorded generation, writes0 even if later unrelated structural operations advanced current SiteSettings;
- no such audit returns `PAGE_NOT_FOUND`;
- malformed/ambiguous delete audit returns `DELETE_UNAVAILABLE`.

If the UUID exists, exact current generation must equal base before composition locks; an older `PAGE_DELETED` audit for that same UUID then refuses as identity ambiguity. Replay is keyed only by old UUID, never by URL, so a new Page with a formerly used URL and a different UUID is untouched. The already-deleted response does not claim that arbitrary confirmation strings were historically verified; it only safely confirms that the UUID is already gone after a fresh owner/password check.

## Fixed private HTTP

One fixed no-JavaScript endpoint:

- `GET /manage/pages/<uuid>/delete/` authenticates current OWNER, opens a short coherent preview transaction with the command lock/projection order, releases locks, then renders escaped fixed summary and one form;
- form contains hidden canonical `base_structure_generation` and `composition_digest`, text inputs `expected_name` and `expected_primary_path`, password `current_password` (`maxlength=4096`, `autocomplete=current-password`), and required literal checkbox/value `confirm_delete=1` beside exact button «Удалить страницу и current + previous»;
- `POST` accepts only `application/x-www-form-urlencoded`, files0, exact single keys above plus optional single CSRF token. Canonical generation is positive ASCII decimal without sign/leading zero; digest is lowercase64hex. Duplicate, missing, unknown or oversized values fail before command;
- success and `already_deleted` return302 to the existing page list. Stale composition/generation/name/PRIMARY returns409 with only one reload link to the same delete preview; wrong password/non-owner403; unknown UUID404; unavailable503;
- both methods use the existing private/no-store and exact4MiB pre-body boundary. All responses including redirect/error are `Cache-Control: private, no-store`; password and typed confirmations are never reflected;
- unsupported valid-CSRF unsafe method returns405 with `Allow: GET, POST`; missing/invalid CSRF POST is framework403 before command.

The existing owner list/editor may gain one literal «Удалить страницу» link. Employee DOM contains no link. No modal, client-side confirmation, generic form helper or bulk action is added.

Exact HTTP outcomes:

| Condition | Result |
|---|---|
| coherent ordinary leaf OWNER GET | `200`, one exact summary/form |
| successful delete or exact gone replay | `302`, exact Location page list |
| malformed wire/body cap | `400 INVALID_PAGE_DELETE_INPUT`, command0 |
| employee GET/POST or wrong current password | `403`, mutation/audit0 |
| unknown UUID without exact delete audit | `404 PAGE_NOT_FOUND` |
| stale generation/name/PRIMARY/composition or gained child | `409`, fixed reload-only conflict |
| `gallery_album` | `409 GALLERY_DELETE_REQUIRED`, mutation0 |
| corrupt/ambiguous aggregate, cap, protected ownership or DB/audit fault | `503 PRIVATE_DATA_UNAVAILABLE` |
| stale session | existing exact login redirect after logout |
| missing/invalid CSRF POST | framework `403`, command0 |
| valid-CSRF unsupported method | `405`, `Allow: GET, POST`, command0 |

## Acceptance before code

| ID | Scenario | Required result |
|---|---|---|
| `RB4-DEL-001` | anonymous/EMPLOYEE GET+POST and direct command | Existing authentication/403 before structural/media query or mutation; employee DOM delete control0 |
| `RB4-DEL-002` | coherent OWNER preview | Exact escaped name+PRIMARY and safe route/content/grant/usage counts/hashes; canonical digest independently reconstructed; writes0 |
| `RB4-DEL-003` | successful ordinary leaf delete | Exact Page/routes/current+previous/grants/own two-scope usages gone; generation +1; one safe `PAGE_DELETED`; former routes404 |
| `RB4-DEL-004` | preservation proof | Parent/siblings/positions/other Pages/routes/content/grants/usages, all Asset/AssetFile bytes/rows and SiteSettings values except generation are byte/value-identical |
| `RB4-DEL-005` | child appears before POST/concurrently | Locked final child proof refuses409; child/subtree and entire target aggregate remain; mutation/audit0 |
| `RB4-DEL-006` | wrong password, stale generation/name/PRIMARY/digest, altered route/content/grant/usage | Fixed denial/conflict, no durable mutation, fresh preview required; secrets/input never reflected or audited |
| `RB4-DEL-007` | gallery kind, unexpected gallery ownership or unknown protected relation | Ordinary command never imports/deletes gallery; known kind409, corrupt ownership503, rollback complete |
| `RB4-DEL-008` | invalid payload/hash/previous tuple/PRIMARY/route/grant/media; all ref writers/global empty invariant; Route/Grant/Usage cap−1/cap/cap+1 | No global backref scan; any nonempty authority stops implementation; producer-derived boundaries succeed/refuse exactly without truncation, partial cleanup or audit |
| `RB4-DEL-009` | fault at usage delete, aggregate delete, generation save or audit | Whole transaction rolls back to exact before-state |
| `RB4-DEL-010` | lost response/repeat, unknown UUID, reused old URL with new UUID | Exact audit-bound UUID replay writes0; unknown404; new Page is never selected/deleted by URL |
| `RB4-DEL-011` | two structural commands on one base and late FK child insert | At most one winner; loser writes0; no implicit child cascade; PostgreSQL lock/FK behavior proven |
| `RB4-DEL-012` | GET/POST wire, CSRF, duplicate/unknown keys, files, wrong content type, >4MiB, unsupported method and static DAG/model scope | Exact status matrix; User→SiteSettings→Page→Route/Content/Grant→Asset/Usage→audit; reverse `pages→gallery`0; literal Page reverse-relation/on_delete allowlist rejects drift; model/migration/dependency/receipt/JS/API/physical cleanup0 |

Focused discovery target is exact12 methods: domain/command8 plus HTTP4, with subtests for closed matrices. PostgreSQL concurrency, FK and rollback evidence requires a later separately reviewed run plan and fresh explicit owner permission after source review.

## No-bloat and stop line

Stop before code if ordinary deletion requires gallery imports/composition deletion, schema/migration, generic cascade walker, receipt/tombstone/identity registry, navigation cache, physical media cleanup, nonempty cross-page JSON-ref semantics, subtree/bulk delete or changes to imported legacy URL policy. Those are separate architectural/product decisions, not hidden extensions of this slice.

Plan and source-review gates are complete. Docker/PostgreSQL remains a later explicit gate after a separate run plan and independent review.
