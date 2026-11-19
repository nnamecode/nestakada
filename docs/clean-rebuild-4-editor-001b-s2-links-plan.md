# RB4 typed editor 001B-S2A — literal partner links

Дата: 2026-11-19. ID: `RB4-EDITOR-001B-S2A-LINKS`. Статус: **code APPROVED by D-1607, P1/P2/P3=0/0/0, product0/no-bloat; runtime0, separate PG/browser gates pending**.

## 1. Boundary and no-bloat split

`S1-PROCESS` is closed by accepted PostgreSQL exact51 and Chromium exact8. The former `S2-REVIEWS-LINKS` marker cannot safely become one implementation:

- `legacy_partner_links.links[]` has exact object `{label, https_url}`, cap64 and no media;
- `reviews.reviews[]` has `{title, https_url, caption}`, cap32 and positional `media.thumbnail[]` with `thumbnail count ≤ reviews count`.

Reordering/removing reviews while preserving thumbnails can silently rebind positional images. Adding a media editor before B002 or inventing stable review IDs would expand the architecture. Therefore only `S2A-LINKS` is designed below. `S2B-REVIEWS` remains read-only until B002 or a separately approved exact thumbnail-position contract. `S3-ACTIONS`, `S4-REFS` and `001B-M` remain closed.

No shared repeater, schema/form DSL, field registry, generic URL-object editor, JSON carrier, media behavior or new dependency is introduced. The current authority contains exactly six partner links; this is the smallest useful uncoupled slice.

## 2. Exact product scope

Only active OWNER on the single page `kind == legacy_partner_links` sees and edits ordered `fields.links`. EMPLOYEE receives link names, values, count, carrier and DOM markers0 for any PageGrant. Other page kinds receive no links control or wire.

The literal control represents0..64 ordered objects. Each has required NFC/control-free `label` length1..500 Unicode code points and required strict canonical-contract `https_url` length1..2,048 code points. Existing server policy remains unchanged: absolute HTTPS with ASCII multi-label hostname, no credentials/port/fragment or malformed percent escape; decoded path forbids backslash, and decoded path+query forbid whitespace/control. Invalid host backslash fails hostname grammar. No new query-backslash restriction is introduced in this slice. UI supports add, remove, move up/down and editing only these two strings. Empty array is valid.

The server renders the existing six values only as escaped disabled inputs from a validated payload. No `maxlength` is used as code-point authority; the local adapter checks `[...value].length`, while the server remains sole authority for the complete HTTPS grammar. The adapter never navigates, fetches, previews or normalizes a submitted URL.

## 3. Literal multipart wire and command assembly

The existing multipart Save endpoint, CSRF, operation UUID, base generation/hash and PageCAS remain unchanged. For OWNER+`legacy_partner_links` only:

- `links.changed=0|1` occurs exactly once;
- with `0`, `links.item` is absent and current links are preserved exactly;
- with `1`, `links.item` repeats0..64 times in exact display order;
- each value is one `label<TAB>https_url` record with exactly one separator;
- tab/control characters are forbidden by the canonical plain/URL contract, so no escaping dialect or second representation exists.

On another role/kind every `links.*` key is unknown and rejects the whole request before command invocation. Duplicate flag, malformed record, cap65, invalid NFC/control/label or strict HTTPS URL, unknown key/file and role/kind forgery return constant400 with command/audit/mutation0.

For OWNER, the adapter deep-copies the validated current snapshot, applies existing scalar fields and only when `links.changed=1` replaces `fields.links`. The complete candidate passes `validate_payload` before `save_page_content`. PageCAS alone re-locks actor/current, resolves replay/stale/conflict, validates again, advances current/previous and writes one AuditEvent atomically. The HTTP adapter performs no direct model write or separate transaction.

Maximum links request is exact73 fields: `1 CSRF + 3 basis + 4 scalar + 1 links flag + 64 items`. Four-byte Unicode conservative item values occupy `64 × ((500 + 2,048) × 4 + 1 TAB) = 652,352` bytes; scalar values≤6,041, CSRF+basis≤183 and flag1. With conservative `256 × 73 parts + 76 closing` RFC-max-boundary overhead, total≤677,341 bytes. This is below existing4MiB and far below the existing10,600-field limit. Focused mechanical encoder proves exact73 and cap+1 ingress behavior; settings/middleware do not change.

## 4. Browser and fail-closed behavior

One local `partner-links-editor.js` attaches only to server-emitted `[data-links-control]`. It knows exact label+URL rows and add/remove/move; it reads no schema metadata and does not initialize reviews/actions/process/prices/media.

Template inputs/buttons start disabled, `links.changed=0`, carriers empty and Save disabled. After checking one exact control, exact direct-child structure and cap64, the script enables only its inputs, sets `data-links-ready="1"` on the exact form and marks dirty on the first edit/operation. Before submit it rechecks DOM ownership/order, NFC/control/code-point caps and emits only repeated hidden `links.item` carriers. It does not duplicate the full server URL policy or open the target; crafted/invalid URLs are rejected by the server.

Current final `editor.js` gains one explicit links-marker condition beside the literal process/price conditions. There is no adapter registry/event bus. Any applicable adapter failure leaves Save disabled and uses the existing safe private error. Without JavaScript the six links stay escaped read-only and Save remains unavailable.

## 5. Acceptance before code

- `RB4-EDLINK-001`: only OWNER+legacy_partner_links receives exact six link values/control/flag; employee and other kinds contain links name/value/count/carrier/marker0.
- `RB4-EDLINK-002`: `links.changed=0` during scalar Save preserves exact ordered links and forbids item carriers.
- `RB4-EDLINK-003`: OWNER saves empty, add/edit/remove/reorder and exact64 boundary; unrelated scalar/current/previous fields are correct.
- `RB4-EDLINK-004`: duplicate/missing flag, malformed/multiple-separator record, cap65, empty/over-cap/non-NFC/control label and non-HTTPS/credential/port/fragment/bad-percent/invalid-host/decoded-path-backslash/decoded-whitespace-control URLs reject before command with mutation/audit0; query-backslash is not a new rejection rule.
- `RB4-EDLINK-005`: valid Save advances current→previous/generation/hash once and one safe audit; stale/concurrent/replay/conflict retain PageCAS behavior; injected validation/audit/DB fault rolls back all.
- `RB4-EDLINK-006`: exact73/RFC-max mechanical wire proof fits existing10,600/4MiB; exact body cap+1 remains rejected by existing ingress guard.
- `RB4-EDLINK-007`: real Chromium proves escaped initial six, add/remove/move/edit, exact-order fixed wire, empty array,64 cap, code-point/NFC/control checks, dirty/readiness, no navigation, no-JS read-only and swapped/unsupported DOM fail-closed with carriers0.
- `RB4-EDLINK-008`: static inspection finds model/migration/dependency/shared repeater/form DSL/registry/JSON/URL policy mirror/reviews/actions/refs/media code0.

## 6. Verification and stop rules

After independent architecture review, any approved implementation is limited to fixed projection/dataclasses, one literal parser/candidate branch, one template section, one partner-links-only JS asset, one explicit readiness condition and focused tests. Static/code review precedes separately authorized PostgreSQL and real-Chromium gates.

Stop and return to the owner if `S2A` requests a shared row/repeater component, schema metadata, adapter registry, client copy of strict URL policy, preview/fetch, new dependency/model/migration/middleware/settings, reviews/actions/refs or media work. The light compromise is to leave a disputed URL or operation read-only. `S2B-REVIEWS` stays deferred rather than silently changing thumbnail associations.
