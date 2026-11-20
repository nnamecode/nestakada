# REBUILD-4 — bounded owner publication slice

Дата: 2026-11-19. ID: `RB4-SLICE-004A-PUBLICATION`. Статус: **completed D-1687; code and PostgreSQL exact126 server gate independently accepted, product0/no-bloat, repeat0**.

## Purpose and boundary

This is the smallest B002-independent public-authority increment after D-1678. It implements only owner publish/hide for an already existing Page. It does not create, rename, move, reorder, change URL or delete a Page; it does not implement public rendering/navigation/blank200, media upload, gallery, refs, B002 materialization, real import, live/deploy or push.

The slice reuses the existing `SiteSettings.structure_generation` serialization authority, current PageContent validator/hash, Route model contract, media rows and AuditEvent. It adds no model, migration, dependency, operation receipt, workflow/status table, generic structural-command framework, form builder, cache, worker or JavaScript.

## Command and lock contract

One pages-owned command:

```text
set_page_publication(
  actor_id,
  session_generation,
  page_id,
  base_structure_generation,
  desired_published,
) -> PublicationResult(structure_generation, is_published)
```

`desired_published` must be exact bool and base generation an exact positive non-bool integer. Both branches start one outer `transaction.atomic()` and lock actor User through the existing accounts public session lock → exact singleton SiteSettings → target Page. They then recheck owner, base CAS and no-change.

- Hide (`desired_published=False`) immediately changes the flag/generation and appends audit. It does not query or require Route, PageContent, AssetUsage or Asset, so damaged/missing content, route or media cannot prevent emergency withdrawal.
- Publish (`desired_published=True`) continues with all target Route rows ordered by UUID → PageContent → one media proof participant → audit. Missing/corrupt content/route/media fails only this publish branch.

Missing/duplicate settings singleton, missing Page, stale base or DB ambiguity fail closed for both branches. Employee/non-owner is rejected before structural mutation.

No-op desired state returns `NO_CHANGE` without generation bump or audit. A successful change mutates only `Page.is_published`, increments `SiteSettings.structure_generation` once and appends one `PAGE_PUBLICATION_CHANGED` event targeting the Page with exact new structure `generation` and `state=PUBLISHED|HIDDEN`. Audit/media/DB fault rolls back Page, generation and audit together.

Publish additionally requires:

- current payload passes the existing closed validator for Page.kind;
- canonical current hash equals stored current hash;
- exactly one PRIMARY Route exists, has outcome equal to Page.kind, and its exact local target/mode pass the current Route contract;
- current media descriptor from the payload equals the complete `PAGE_CURRENT` usage projection by exact slot/position/Asset UUID;
- every referenced or actually projected Asset is still `READY` and `CONTENT` under media-owned locks.

The media proof is exactly one new media-owned public participant:

```text
verify_page_current_usages(page_id, expected_media) -> None
```

It requires an already open outer transaction, opens no transaction and performs no write. With the Page and PageContent already locked, it reads only IDs from actual `PAGE_CURRENT/target_uuid=page_id` rows to form the union of expected+actual Asset UUIDs, locks that complete Asset union in ascending UUID, then locks the complete actual usage rows in stable `(slot, position, asset_id, id)` order. It converts expected media through the same closed slot/position/UUID rules as `replace_page_usages`, compares the full ordered tuples `(slot, position, asset_id)` including missing/extra/reordered rows, and requires every union Asset to exist with exact `READY/CONTENT`. It reads no AssetFile, path or private storage and returns only success or constant `MediaUsageError`. This preserves the existing Page→Content→Asset→Usage order used by content Save; Page serialization prevents concurrent usage replacement between the initial ID read and locked comparison.

Hide deliberately does not depend on current payload/media health: emergency withdrawal must remain possible. It changes no child publication flag, Route, PageContent, PageGrant or media usage. D-052 blank200 and promoted published descendants are requirements for the later read-only public resolver/navigation slice, not falsely claimed by this command-only slice.

## Fixed private HTTP

One fixed owner-only no-JavaScript endpoint is added after existing page-editor routes:

- `GET /manage/pages/<uuid>/publication/` shows escaped Page name, current publication state and one form with exact hidden `base_structure_generation` and `desired_published` opposite to current;
- `POST` accepts only exact urlencoded keys plus one CSRF token. `desired_published` is one literal string, exactly `"1"` for publish or `"0"` for hide, converted to bool only after closed wire validation; `base_structure_generation` is one canonical positive ASCII decimal with no sign/leading zero. Any other spelling/value/duplicate is400 before command. The endpoint uses an exact publication-path extension of the existing private 4 MiB pre-body ingress boundary, invokes the one command and redirects to the existing editor on success;
- stale/no-change returns private409 conflict/reload, malformed wire400, unknown Page404, employee403, stale owner session redirects login, unexpected DB/media failure constant503;
- response is private/no-store through existing middleware; password/content/hash/media IDs are never reflected.

The existing page editor gets only one owner link to this fixed endpoint. Employee DOM has no link. No modal, list bulk action, search, API, JS or generic form helper is introduced.

## Acceptance before code

| ID | Scenario | Required result |
|---|---|---|
| `RB4-PUB-001` | anonymous/EMPLOYEE GET+POST | Authentication/403 before projection or mutation; employee DOM has no publication control |
| `RB4-PUB-002` | owner publishes valid hidden Page on current base | Page only becomes published; structure generation +1; one safe audit; content/routes/grants/usages/children unchanged |
| `RB4-PUB-003` | owner hides published Page with missing/corrupt PRIMARY, current content and media | Hide performs no Route/Content/media query and still succeeds atomically; child flags/routes/content/usages unchanged |
| `RB4-PUB-004` | stale generation, desired current state, two commands on one base | One winner maximum; stale/no-change409 semantics; second mutation/audit0 |
| `RB4-PUB-005` | missing/corrupt current payload/hash, missing/duplicate/wrong PRIMARY | Publish fails closed before mutation/audit; hide remains available |
| `RB4-PUB-006` | current media missing/extra/reordered/wrong slot, expected-or-actual Asset missing/non-READY/non-CONTENT | Publish fails and all state stays unchanged; participant proves full tuple/union, opens no transaction and writes0 |
| `RB4-PUB-007` | injected media/audit/DB fault | Page flag, structure generation and audit roll back together |
| `RB4-PUB-008` | GET/POST wire, CSRF, unknown/duplicate keys, desired other than exact `1|0`, noncanonical generation, wrong content type, exact4MiB cap | Closed400/403/404 before command as applicable; body cap before parser/command |
| `RB4-PUB-009` | actual PostgreSQL query/lock and DAG inspection | User → SiteSettings → Page → Route UUID order → Content → current usage/assets → audit; pages→accounts/media/audit only, reverse imports0 |
| `RB4-PUB-010` | static scope inspection | model/migration/dependency/receipt/generic framework/JS/public renderer/B002 changes0 |

Focused discovery target is exact15 methods: command/domain8 plus HTTP7. Runtime, exact count and regression cohort require a separate reviewed run plan and explicit owner permission after code review.

## No-bloat stop line

If publish integrity cannot reuse one narrow media participant and existing validators, stop before code rather than introducing a publication service, cached projection, storage probe or generic lifecycle framework. If exact Page blank200/navigation evidence is requested, defer it to the next public read slice instead of coupling anonymous rendering into this mutation package.
