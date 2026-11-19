# RB4 typed editor 001B — literal increments

Дата: 2026-11-19. ID: `RB4-EDITOR-001B`. Статус: **`001B-P` completed by D-1584: PostgreSQL exact47 and Chromium exact8 independently ACCEPTED 0/0/0; `001B-S/M` remain separate and closed**.

## 1. Boundary and order

`RB4-EDITOR-HTTP-001A` is closed by accepted PostgreSQL exact40 and real-Chromium exact8 evidence. The remaining typed fields are deliberately not one implementation package. They are three sequential literal increments:

1. `RB4-EDITOR-001B-P` — exact `price_rows` editor for `service_detail` and the already modelled employee `prices` grant;
2. `RB4-EDITOR-001B-S` — owner-only structured fields, planned later per literal field family;
3. `RB4-EDITOR-001B-M` — owner-only selection of existing READY CONTENT assets through an exact slot registry, planned only after its B002 data/read boundary is available.

Only `001B-P` is designed below. `001B-S` and `001B-M` are ordering markers, not permission to implement. They require their own acceptance plans and reviews. In particular, this document does not introduce a shared repeater, schema/form DSL, field registry, JSON editor, media preview, upload, import, gallery management or generic selector.

This ordering is the light path: PageCAS already owns a closed `prices` employee patch, whereas structures have several incompatible shapes and media needs READY-asset discovery. Combining them would create a generic form builder and is a stop condition.

## 2. `001B-P` exact product scope

The existing page editor gains one literal price-table control only when `Page.kind == service_detail`:

- OWNER sees and may edit `price_rows` together with the already allowed scalar/rich fields;
- EMPLOYEE sees it only when the exact current `PageGrant.groups` contains `prices`;
- an employee with both `text` and `prices` sees both literal controls and may submit either or both groups in one Save;
- a price-only employee receives no SEO, heading, rich, structured or media names, values, counts or carriers;
- all other page kinds have no price control or price wire.

The control represents the existing closed payload exactly: at most32 ordered columns `{id,label}`, at most500 ordered rows `{id,label,cells}`, and at most10,000 cells. A cell belongs to one existing column and is either literal `text` or literal decimal `amount` plus `from`. Existing UUIDs are preserved; new row/column UUIDs are generated locally with browser `crypto.randomUUID()` and remain untrusted input validated by the server. The UI supports add, remove and move for columns/rows, row/column labels, an absent/text/amount choice per cell, text, canonical decimal amount and the `from` flag. It adds no formulas, merged cells, currencies, units, formatting, bulk import/export or spreadsheet behavior.

Removing a column removes its cells from the submitted candidate. Removing a row removes that row. Empty arrays are valid. Reordering changes only array order. The local adapter never writes storage and has no autosave/draft/history state.

## 3. Literal wire and server assembly

The existing multipart Save endpoint, CSRF, independent operation UUID, base generation and current hash remain unchanged. JSON/urlencoded requests and files remain rejected. `price_rows` uses a compact price-only repeated-key wire, not JSON and not dynamic field names:

- `price.changed=0|1` occurs exactly once when the actor may edit prices;
- when `0`, every other `price.*` key is absent and the server preserves the current price bytes/semantics;
- when `1`, `price.column` repeats at most32 times in exact display order, each value being one tab-delimited `uuid<TAB>label` record;
- `price.row` repeats at most500 times in exact display order, each value being one `uuid<TAB>label` record;
- `price.cell` repeats at most10,000 times; each value is one closed tab-delimited record: `row_uuid<TAB>column_uuid<TAB>text<TAB>value` or `row_uuid<TAB>column_uuid<TAB>amount<TAB>decimal<TAB>0|1`;
- tab/control characters are already forbidden by the canonical plain-text contract, so there is no escaping dialect or alternate representation; an empty text cell ends at the final separator;
- an absent cell has no record. Duplicate row/column/cell identities and cell references outside the submitted rows/columns are forbidden.

The exact maximum Django field count for a price-capable owner request is `1 CSRF + 3 basis + 4 scalar + 2 rich flags + 2 rich values + 1 price flag + 32 columns + 500 rows + 10,000 cells = 10,545`; employee variants are smaller. The implementation may pin `DATA_UPLOAD_MAX_NUMBER_FIELDS=10_600`, never unbounded. The existing pre-CSRF private ingress middleware must reject missing/non-canonical `Content-Length` or a body over exact4MiB only on the literal page-Save route before body parsing. `DATA_UPLOAD_MAX_MEMORY_SIZE` is pinned to4MiB, files remain0, and a mechanical worst-case encoder test uses the RFC maximum boundary length to prove every canonical price payload whose complete JSON envelope is within the existing1MiB limit fits the4MiB multipart cap. No request may rely on browser-specific short boundaries.

After the bounded parser, the application accepts only the literal keys above and their exact cardinalities/caps. Unknown, malformed, out-of-cap or role/kind-forbidden keys reject the whole request with constant400 and command0. Cells for each row are assembled strictly in submitted `price.column` order while absent cells are skipped; multipart arrival order is never payload semantics. Field/schema/group names and caps never come from the client.

For OWNER, the adapter deep-copies the validated current snapshot, applies existing scalar/rich changes and, only when changed, replaces `fields.price_rows`. For EMPLOYEE it creates only the already supported command patch `{prices: exact_price_rows}` and/or the existing `{text: ...}` patch for currently granted groups. The adapter validates the complete owner candidate or reconstructed employee candidate before invoking `save_page_content`; PageCAS alone re-locks actor/grant/current, decides replay/stale/conflict, validates again, advances current/previous, writes one audit event and updates usages atomically.

The adapter never compares basis values to decide freshness and never writes models directly. Request order is exact: session/role projection, bounded multipart parsing and complete role/wire/candidate validation, then the command. Only a valid request that reaches PageCAS can receive a retained same-operation replay before command CAS/current-candidate validation. A changed but valid UUID set in such a replay is ignored by the retained result; malformed repeated wire remains safe400 before the command.

## 4. Browser and no-JS behavior

One price-specific local adapter may be added beside the existing rich adapter. It is attached only to server-marked price controls and contains only price-table operations; it must not inspect arbitrary schema metadata or initialize other field types. The server emits escaped literal controls from an already validated payload, never raw payload JSON. Initialization requires `window.isSecureContext === true` and callable `crypto.randomUUID`; failure is closed and UUID fallback0.

Save is absent/disabled until every applicable local adapter initializes successfully. The price script is loaded first and sets one literal `data-price-ready="1"` marker on the exact form only after complete success. The existing rich script remains the final enabler and enables Save only when the price control is absent or that exact marker is present; there is no adapter registry or event bus. Any applicable adapter failure leaves Save disabled. Without JavaScript, price data is validated read-only and cannot be saved.

For a prices-only employee, Save stays disabled until the price control is dirty; `price.changed=0` is accepted only when a real allowed text group patch is also sent. No empty command patch and no no-op revision are created. Before submit the adapter verifies its exact DOM ownership, caps, UUID uniqueness, decimal/text shape and emits the fixed wire. The server remains the authority and rejects crafted requests. A separate browser-native exact suite is required for add/remove/move, cell-kind switching, dirty tracking, serialization, secure-context/randomUUID failure and fail-closed unsupported DOM; Django/PostgreSQL tests do not claim browser behavior.

## 5. Acceptance before code

- `RB4-EDPRICE-001`: only `service_detail` OWNER and employees with exact `prices` grant receive price controls; every other role/kind/grant has price value/name/carrier0.
- `RB4-EDPRICE-002`: unchanged `price.changed=0` preserves the exact current price structure through owner rich/scalar Save and employee text Save.
- `RB4-EDPRICE-003`: owner may save exact empty/boundary-valid columns, rows and both cell kinds; every unrelated structured/media field is preserved.
- `RB4-EDPRICE-004`: employee prices-only and text+prices patches change only currently granted groups; a revoked/foreign/price-on-wrong-kind request mutates/audits0.
- `RB4-EDPRICE-005`: exact10,545/10,600 field arithmetic and RFC-max-boundary4MiB representation proof pass; unknown/missing/extra keys, files, bad record shape/UUID/reference, duplicate IDs/cells, cap overflow, invalid text/decimal/from or forbidden group fail whole-request before command.
- `RB4-EDPRICE-006`: stale, concurrent, retained replay and operation-conflict outcomes remain the existing PageCAS outcomes with one winner and no merge/lost update.
- `RB4-EDPRICE-007`: valid Save advances current→previous/generation/hash once, writes one safe audit event and leaves exact media usages unchanged; injected validation/audit/DB fault rolls back all.
- `RB4-EDPRICE-008`: real Chromium proves literal add/remove/move, column cleanup, absent/text/amount switching, dirty tracking, cells serialized in column order, exact two-adapter readiness, prices-only no-op disabled, secure-context/randomUUID failure, no-JS read-only and unsupported DOM fail-closed.
- `RB4-EDPRICE-009`: static inspection finds model/migration/dependency/middleware/API framework/shared repeater/schema DSL/form builder/JSON carrier/draft/autosave/import/export0.

## 6. Verification and gates

Implementation, if approved, is one bounded `001B-P` package: fixed server projection/parser/candidate assembly, one literal template section, one price-only JS asset, a literal readiness check in the existing rich asset, exact bounded upload settings/pre-CSRF Save-route guard in the existing ingress middleware, and focused tests. It adds no middleware. First static and independent code review; then a separately authorized disposable PostgreSQL focused regression; then a separately authorized isolated real-Chromium price suite. Runtime evidence cannot be inferred from static review.

`001B-S` begins only after `001B-P` closes and gets a new literal-field plan. `001B-M` begins only after the READY selection source and B002 boundary are proven; it never exposes PRIVATE_SOURCE storage key/hash/bytes. Real imported-data integration, template responsive E2E, Nginx, live/deploy and push remain separate gates.

## 7. Stop rules and light compromises

Stop and return to the owner if `001B-P` requests a generic repeater/grid/spreadsheet component, schema-driven form, second content representation, hidden JSON payload, backend draft, bulk CSV/clipboard import, formulas, localization/currency model, new dependency/model/migration or media/structured-field work.

The light compromise for a disputed price behavior is to leave that operation read-only and keep the current exact payload, not add a generic abstraction. The light compromise for `001B-S` is separate literal controls per compatible field shape. The light compromise for `001B-M` is UUID selection from bounded public READY metadata without upload, preview pipeline or asset management.
