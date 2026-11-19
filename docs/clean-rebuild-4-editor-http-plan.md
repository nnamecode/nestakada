# RB4 typed editor HTTP — scalar/rich vertical increment

Дата: 2026-11-18. ID: `RB4-EDITOR-HTTP-001A`. Статус: **independently APPROVED P1/P2/P3=0/0/0; implementation active, runtime0**.

## Scope and honest completion boundary

This is the next bounded part of approved `RB4-SLICE-001`. It adds only:

- authenticated/authorized GET `/manage/pages/<uuid>/`;
- owner Save of exact `seo`, `heading` and contract-declared rich fields;
- employee Save of exact `intro/body` only when current PageGrant contains `text` and the Page kind permits that group;
- owner-only Undo through the already tested PageCAS command;
- one local visual rich adapter selected by owner in `RB4-RICH-Q001`.

All19 payload kinds are readable and revalidated. Structured arrays (`service_refs`, `process_steps`, `brand_refs`, `review_refs`, `actions`, `reviews`, `links`), `price_rows` and media slots remain read-only and are copied from the current locked basis without client carriers. Price editing, structured repeaters and READY media selection form a later `001B` increment; this plan does not call the whole typed editor complete. It adds no generic form/schema builder, raw HTML mode, JSON editor, model, migration, dependency, second content representation or persistent editor state.

## Read and authorization

The pages-owned view uses the accounts session guard before page queries. OWNER may open any Page; EMPLOYEE requires an exact own PageGrant before content projection. The read requires exactly one PRIMARY Route, one PageContent, exact `Page.kind == payload.kind`, valid current payload and exact canonical hash. Any missing/corrupt composition returns one constant private503 with no partial payload. Foreign employee UUID returns constant403 with page data0.

The template shows read-only page name, PRIMARY path, kind, publication and generation. It never renders raw payload, author, media storage data or other grants. OWNER sees fixed Russian labels/counts for deferred structured/media fields, never JSON or payload carriers. EMPLOYEE DOM/context contains only the page header and currently granted editable `intro/body`; SEO/H1, structured/media field names, values, counts and carriers are absent. Current rich fragments are marked renderable only after exact server revalidation.

The current hash is not a visible content field. Exactly one hidden `base_current_hash` is nevertheless required in each action form as PageCAS basis. A private409 may return the current generation/hash only as conflict data for reload. Previous and unrelated hashes remain absent.

## Literal multipart wire

Save and Undo are POST-only, CSRF-protected and `multipart/form-data` with files0. Multipart avoids URL-encoding expansion while the canonical payload remains bounded to1MiB; JSON and urlencoded bodies are rejected. Framework `csrfmiddlewaretoken` is allowed once and separated from application cardinality.

Literal POST targets are `/manage/pages/<uuid>/save/` and `/manage/pages/<uuid>/undo/`. Every GET generates independent Save and Undo operation UUIDs; each form contains exactly its own operation UUID, base generation and base current hash. A network repeat of either submitted form retains that form's UUID. Save application keys are derived only from the server-known role, kind and fixed map:

- basis: `operation_id`, `base_generation`, `base_current_hash`;
- owner scalar keys: `seo.title`, `seo.description`, `seo.allow_index` with literal `0|1`, `heading.h1`;
- each allowed rich field has exact `rich.<field>.changed=0|1`; when `0`, `rich.<field>.value` must be absent and the server preserves the current value; when `1`, exactly one `rich.<field>.value` is required;
- employee receives only `intro/body` controls when exact text group is granted. SEO/H1 and every protected field are absent, not hidden;
- Undo has only basis keys.

Unknown/duplicate/missing key, files, invalid UUID/integer/hash/flag, value cap, wrong content type or Django body-limit/parser exception returns constant400 before command invocation. Field names/schema/kind/groups are never accepted from the client. The request contains no structured/media protected carrier.

On Save the adapter reloads and exact-validates the current server snapshot solely to assemble a candidate; it never compares submitted generation/hash to that snapshot and never decides freshness. OWNER deep-copies that snapshot and replaces only submitted scalar/rich fields. EMPLOYEE assembles the full exact `{intro, body}` patch from its validated snapshot plus submitted allowed changes; the command still copies all protected data from the locked actual current. Submitted basis passes unchanged to `save_page_content`. The command remains the only replay/conflict/stale/mutation authority and repeats actor/grant lock, CAS, validation, usages and audit atomically. A race after snapshot read and every stale distinct operation lose only at command CAS; retained same-operation replay reaches the command before changes are used. The adapter never writes directly.

## Selected local rich adapter

One local static JS file attaches only to server-marked rich controls. A user sees visual `contenteditable`, never source HTML. Literal controls are paragraph, H2, H3, bold, italic, underline, strike, ordered/unordered list, blockquote and link/unlink. Existing allowed table/sub/sup content can remain visible and its text can be edited, but this increment adds no table builder or extra toolbar controls.

The adapter does not use `execCommand`, CDN, package, plugin API, schema registry or background state. It uses Selection/Range and one deterministic DOM serializer over the existing `estakada-rich-v1` tag/attribute set. Text and attributes are escaped canonically; attribute order is fixed; href is internal or HTTPS; unknown node/attribute/URL blocks submission instead of being stripped. Paste is intercepted as plain text with deterministic paragraph/line-break output or rejected. Initial server content is exact-validated before safe render.

Unchanged controls send only `changed=0`, so browser DOM normalization can never rewrite stored canonical bytes. One `markDirty()` path is called by native input/IME and explicitly by every toolbar, link/unlink, paste and Selection/Range mutation; toolbar actions do not rely on the browser emitting `input`. Changed content is serialized to the hidden value carrier immediately before submission. Save is absent/disabled by default and enabled only after successful JS initialization. No-JS shows validated read-only rich content and no Save control. Crafted requests still meet the same server parser and existing exact validator; JS is convenience, not authority.

## Responses and command errors

Success uses POST/Redirect/GET back to the editor; a new operation UUID is issued only by the new GET. A network-level repeat of the same POST retains its submitted operation UUID and PageCAS replay semantics.

- `STALE_CONTENT` or `OPERATION_CONFLICT`: private409 with current generation/hash and reload link, mutation/audit0;
- `FORBIDDEN`: constant403; `PAGE_NOT_FOUND`: constant404;
- `AUTH_REQUIRED`/`STALE_SESSION`: flush/redirect login with private content0;
- malformed/`INVALID_OPERATION`/`INVALID_BASIS`/`INVALID_PATCH`/`INVALID_CONTENT`: constant400;
- `NO_PREVIOUS`: constant409;
- `CONTENT_MISSING`/`CONTENT_CORRUPT`/`MEDIA_NOT_READY`/unexpected command or audit fault: constant503 without exception detail;
- every response remains `private,no-store` through the existing middleware.

Undo control is rendered only to OWNER when previous exists and the exact previous payload/kind/hash also revalidate; corrupt previous makes the whole editor private503 rather than exposing a doomed action. Server authorization remains authoritative. Employee/direct Undo returns403. CSRF/method failure never invokes a command.

## Acceptance before code

- `RB4-EDHTTP-001`: anonymous/stale/foreign employee request reaches no PageContent projection; safe redirect/403 and no-store.
- `RB4-EDHTTP-002`: owner/employee GET returns exact permitted controls for all relevant kind/group combinations; protected keys, raw JSON/storage/private metadata absent; only action-form hidden basis hashes are present.
- `RB4-EDHTTP-003`: current kind/hash/rich/composition corruption returns constant503 before safe render or command.
- `RB4-EDHTTP-004`: malformed multipart cardinality, extra/duplicate keys, files, JSON/urlencoded and cap violations invoke command0 and mutate/audit0.
- `RB4-EDHTTP-005`: owner scalar/rich Save preserves every structured/media field exactly and closes through existing PageCAS generation/previous/hash/audit/usages.
- `RB4-EDHTTP-006`: employee text Save changes only granted intro/body; price-only/no grant/wrong kind/crafted protected key is denied whole-request with mutation0.
- `RB4-EDHTTP-007`: unchanged rich round-trip preserves exact stored bytes; deterministic changed serialization passes validator; every native/toolbar/link/paste mutation marks dirty; unsafe link/unknown node/attribute/forbidden paste/client bypass is blocked or server-rejected. Serializer behavior closes only in the separate browser-native gate, not the Django/PostgreSQL gate.
- `RB4-EDHTTP-008`: stale/concurrent/replay/operation-conflict mappings retain PageCAS outcomes and never merge silently.
- `RB4-EDHTTP-009`: owner Undo swaps exact content/provenance/usages; employee/missing previous/CSRF/method paths mutate0.
- `RB4-EDHTTP-010`: static DAG and no-bloat remain pages→accounts/media/audit, one local JS asset, dependency/model/migration/middleware/API framework/form builder/legacy import0.

## Verification and stop rule

Django client tests and static source inspection precede one separately authorized disposable PostgreSQL gate. No Python mirror, jsdom, Node runner or new JS test dependency is introduced. Deterministic serializer/Selection/Range/paste behavior requires a separate owner-authorized browser-native functional gate; responsive visual evidence may share that later browser session but remains a distinct claim. PostgreSQL/Django tests never claim serializer PASS. Nginx limiter/socket, structured fields, price/media editing, SiteSettings, grants/staff, public renderer, live/deploy and real imported data remain closed.

Stop and return to the owner if implementation requires a second content model, generic field registry/schema DSL, raw HTML fallback, external editor dependency, another middleware, client-side persistence, autosave, preview, draft/history/workflow, upload or API framework. The light compromise is to leave the disputed field read-only for `001B`, not create a placeholder abstraction.
