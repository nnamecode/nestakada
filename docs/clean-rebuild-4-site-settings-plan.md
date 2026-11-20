# REBUILD-4 — bounded SiteSettings core form

Дата: 2026-11-20. ID: `RB4-SLICE-002A-SITE-SETTINGS`. Статус: **source implementation and final repeat code review APPROVED 0/0/0; runtime0 pending owner gate**.

## Purpose and stop line

D-1730 closed the media-free legacy projection. A public catch-all still cannot render the approved shared Header/Footer coherently until the imported READY logo and storage authority exist, so HTTP/template work remains B002-bound. The smallest durable next product increment is the already planned SiteSettings mutation boundary on synthetic rows: one fixed private form and one literal READY `SITE_ASSET` logo selector. It is required by future Header/Footer and does not open or copy media bytes.

This slice edits exactly eight non-gated values: `organization_name`, `phone_display`, `phone_e164`, `address`, `opening_hours`, `contact_email`, `map_url`, `logo_asset_id`. Existing `legal_name`, `max_url` and `telegram_url` are preserved byte-for-value and are absent from the POST contract because their publication targets remain separately gated. No publication flag or feature flag is added to simulate those decisions.

Included files may be only one literal pages command module, the existing media public API, pages web/URL/template, the exact private-ingress body-cap allowlist and focused tests. Model, migration, dependency, upload/worker/delete, physical preview, storage open, AssetFile path/hash exposure, page/public HTTP, Header/Footer renderer, JS, generic selector/form builder, B002 materialization, live/deploy/push changes0.

## Exact command and transaction

Pages owns one explicit command:

```text
update_site_settings(
  actor_id, session_generation, base_settings_generation,
  organization_name, phone_display, phone_e164, address,
  opening_hours, contact_email, map_url, logo_asset_id
) -> SiteSettingsResult(settings_generation)
```

All arguments are scalar and explicit; dict patch, arbitrary field names and partial merge are absent. One transaction performs this order:

1. `accounts.lock_staff_session`, then exact active OWNER check;
2. lock the singleton SiteSettings row and compare positive integer `base_settings_generation`;
3. call one literal media participant that locks current+candidate Assets in UUID order, requires both READY `SITE_ASSET`, then locks every `AssetUsage(scope=SITE_SETTINGS,target_uuid=settings.id)` in deterministic UUID order;
4. compare that full locked usage set with exactly one row `(slot=logo, position=0, asset_id=current_logo_id)`; any missing, duplicate or extra slot/asset row fails closed instead of being ignored or repaired, including on the no-change path;
5. construct and fully validate the candidate SiteSettings while preserving `structure_generation`, `legal_name`, `max_url` and `telegram_url` exactly;
6. reject exact no-change without generation/audit mutation;
7. replace only the scalar logo usage when the logo changes, save the eight fields plus incremented `settings_generation`, and append exactly one `SITE_SETTINGS_CHANGED` audit with the new generation and absent target UUID.

Audit failure, validation failure, media failure or DB failure rolls back settings, usage and generation. This command never changes `structure_generation`, Page/PageContent/Route/Grant, staff generation or publication.

The media participant is literal `replace_site_logo_usage`; it is not a generic usage mutation API. It requires an outer transaction and has no commit/retry behavior of its own.

## Bounded private projection and HTTP

One route `/manage/settings/` supports GET and POST under the existing private session/cache boundary.

- OWNER GET receives the eight editable values, exact `settings_generation`, current logo and 1..64 selectable READY `SITE_ASSET` options ordered by Asset UUID.
- EMPLOYEE GET receives the same non-gated scalar values and current-logo public metadata read-only, but no selector options or mutation control.
- Anonymous is redirected by the existing session boundary; EMPLOYEE POST is constant403 before command invocation.
- OWNER POST accepts exact `application/x-www-form-urlencoded`, no files, one value for each of the nine command fields including `base_settings_generation`, optional single CSRF field, and no unknown/duplicate/noncanonical key.
- The existing private-ingress 4MiB body cap is extended by one literal `/manage/settings/` POST path; no new size-policy layer is added.

The literal media projection takes only `settings_id`, `current_logo_id` and an owner-options boolean; media imports no pages model. For both roles it first reads the full `SITE_SETTINGS/settings-id` usage set and requires exact equality with one `(logo,0,current_logo_id)` row. It then selects only READY `SITE_ASSET` rows with exactly one MAIN AssetFile and returns frozen `asset_id`, `mime_type`, `width`, `height`. It selects neither `storage_key`, SHA, byte size, PRIVATE_SOURCE nor file bytes. Owner options must contain 1..64 rows including current logo; zero, cap+1, missing/duplicate MAIN, wrong purpose/state, usage drift or current-logo absence fails the form closed. Employee GET resolves only the current logo through the same coherence and public-metadata rules. There is no pagination or fallback.

The server template contains fixed labels/inputs and a select; image preview, upload, JavaScript, arbitrary metadata and data-selected template names0. All private responses remain `private, no-store`.

Exact HTTP outcomes are fixed:

| Condition | Result |
|---|---|
| Successful OWNER POST | `302` to exact `/manage/settings/` |
| Malformed/noncanonical/duplicate wire, invalid content type/file/body length/UUID or invalid core scalar | `400` plain `INVALID_SETTINGS_INPUT` |
| EMPLOYEE POST | `403` plain `FORBIDDEN`, command0 |
| Stale basis or exact no-change | `409` fixed `pages/site_settings_conflict.html` containing marker `SETTINGS_CONFLICT` and only a reload link to `/manage/settings/` |
| Missing/corrupt singleton, logo/usage/selector corruption, media/audit/DB fault | `503` plain `PRIVATE_DATA_UNAVAILABLE` |
| Missing/stale session | session cleared as applicable, `302` to exact `/manage/login/` |
| CSRF failure | framework `403`, command0 and no settings/media values |
| Unsupported method | framework `405`, `Allow: GET, POST`, command0 |

An exact same-logo POST succeeds only when at least one core scalar changes. A completely identical POST is `409 SETTINGS_CONFLICT` with mutation/audit0.

## Acceptance before code

| ID | Scenario | Required result |
|---|---|---|
| `RB4-SET-001` | OWNER vs EMPLOYEE vs anonymous GET | Owner exact fixed form+bounded options; employee read-only core/current logo; anonymous redirect; gated fields absent |
| `RB4-SET-002` | Valid owner update with changed logo, or same logo plus scalar change | Eight core values exact, generation+1, scalar usage exact, one safe audit; structure/Page/staff axes unchanged |
| `RB4-SET-003` | Stale basis or completely identical POST | exact409 conflict template; settings/usage/audit unchanged |
| `RB4-SET-004` | Employee/direct/stale session mutation | denied before media/settings mutation or audit |
| `RB4-SET-005` | Invalid text/E.164/email/HTTPS/UUID or attempt to submit gated/unknown field | whole request rejected; preserved gated values unchanged |
| `RB4-SET-006` | Candidate logo missing/STAGED/wrong-purpose or any missing/extra/drifted current usage | exact503; full usage-set comparison; no repair/partial mutation; GET also fails closed |
| `RB4-SET-007` | Selector exact1/64, zero, cap+1 or corrupt MAIN | valid bounded UUID+mime+dimensions only; zero/cap/corruption exact503; private fields/bytes absent |
| `RB4-SET-008` | Audit/media/DB fault | one atomic rollback across settings, generation and usage |
| `RB4-SET-009` | Two updates on one generation | one winner; one stale; no lost update or duplicate audit |
| `RB4-SET-010` | Success redirect and every fixed HTTP failure row above | exact status/body/location/Allow oracle; command0 on denied/malformed paths; private/no-store |
| `RB4-SET-011` | Static DAG and query surface | pages→accounts/media/audit only; media imports none from pages; no storage open/AssetFile private fields |
| `RB4-SET-012` | Scope inspection | model/migration/dependency/JS/public renderer/B002/upload/generic builder changes0 |

Focused target is exact12 new methods across one command/media test module and one HTTP test module, in addition to the existing four pure SiteSettings model-contract regressions. PostgreSQL runtime and browser are separate reviewed owner gates after independent code review; browser is not required for the fixed no-JS mutation semantics but remains required later for the shared admin shell/responsive visual gate.

## No-bloat compromise

If correct logo selection requires opening bytes, resolving a storage backend, adding pagination/search, exposing storage keys/hashes, or introducing a generic media selector, stop this slice. Keep the existing logo unchanged and defer selection/UI to B002 rather than add a temporary storage adapter. If review finds that non-gated scalar editing without the selector is still useful, the only allowed reduction is a core-fields-only form that preserves the logo and usage exactly; scope may not expand sideways.

Repeat independent D-1733 review is APPROVED with P1/P2/P3=0/0/0 and no-bloat PASS. It accepts full usage-set coherence on command/no-change/GET, the pages-independent media projection, exact HTTP matrix, selector1..64 and same-logo semantics. Lock order, privacy, DAG and exact12 coverage are sufficient. Tests-first implementation may start; runtime remains separately gated.

D-1734 source result: exact12 tests-first implementation is complete. Independent code review progressed `0/1/3 → 0/0/1 → APPROVED 0/0/0`, product findings0, with privacy/DAG/no-bloat/anti-loop PASS. Remediation fixed pre-validation media mutation ordering, proved changed-logo rollback and exact full-usage/cardinality failures, and pinned every fixed HTTP status/body/location/Allow/cache/command0 oracle. Static diff/scope checks pass; model/migration/dependency/storage/media-byte/public-renderer changes remain0. Docker/PostgreSQL runtime has not run and requires a fresh explicit owner permission.
