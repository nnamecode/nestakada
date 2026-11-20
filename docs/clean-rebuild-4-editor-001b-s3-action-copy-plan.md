# RB4 typed editor 001B-S3A — fixed action copy

Дата: 2026-11-19. ID: `RB4-EDITOR-001B-S3A-ACTION-COPY`. Статус: **CODE APPROVED by D-1622, final P1/P2/P3=0/0/0 and no-bloat PASS; server exact59 plan review, runtime0**.

## 1. Boundary and no-bloat split

The current actions authority has exact two ordered `actions[]` and exact two ordered `media.banner[]`. Import authority constructs both arrays from the same ordered cards, so add/remove/reorder before B002 can silently rebind a banner to another action. A full action structure editor is therefore not safe now.

`S3` is split without inventing stable card IDs:

- `S3A-ACTION-COPY` edits only `title` and rich `body` at the existing fixed positions;
- count, order, each existing `internal_url` and all `media.banner[]` values remain unchanged;
- add/remove/reorder, URL editing/selection and media are deferred to B002/S4 or a separately approved exact association contract.

No shared repeater, nested form/schema DSL, rich-editor fork, adapter registry, JSON carrier, stable-ID migration, media picker or new dependency is introduced. If fixed-position preservation cannot be proved, actions remain read-only.

## 2. Exact product scope

Only active OWNER on `Page.kind == actions` receives the fixed action-copy control. EMPLOYEE receives action titles, bodies, URLs, counts, carriers and DOM markers0 for every PageGrant. Other kinds receive no action control or wire.

For each already validated current action, the server renders one escaped required title input, one existing-safe-rich control for body and the current internal URL as owner-only read-only context. There are no structural operation buttons. The current count may be0..32 and is fixed for the request snapshot; the present authority count is2.

Title retains the canonical required NFC/control-free cap500 code points. Body retains the existing canonical safe-rich grammar, aggregate visible-text/node limits and candidate envelope1MiB. Internal URL is never submitted or changed in S3A. The canonical validated fragment is rendered only as DOM inside the already accepted rich editing boundary; executable tags/attributes are absent, no source is evaluated or executed, and submission uses the one existing deterministic serializer.

## 3. Fixed-position multipart wire

The existing multipart Save endpoint, CSRF, operation UUID, base generation/hash and PageCAS remain unchanged. For OWNER+actions only, current positions `0..N-1` define an exact closed key set:

- `actions.<index>.title` occurs exactly once for every current position;
- `actions.<index>.body.changed=0|1` occurs exactly once;
- with `0`, `actions.<index>.body.value` is absent and the current body is preserved exactly;
- with `1`, `actions.<index>.body.value` occurs once and is capped at1,048,576 ingress bytes before canonical validation.

No client count, ID, order, internal URL or media value is accepted. Missing/extra/noncanonical index, duplicate title/flag/value, changed0+value, changed1 without value, unknown/file key or role/kind forgery rejects the complete request before command invocation. Dynamic names are not schema metadata: the server derives the one exact finite key set solely from the validated current snapshot and cap32.

The owner candidate deep-copies the validated current payload and replaces, at each same index, only title and optionally changed body. Existing `internal_url`, array length/order, media, intro and unrelated fields are preserved unless changed through their already approved controls. The complete candidate passes `validate_payload` before `save_page_content`; PageCAS re-locks and revalidates, retains replay/stale/conflict semantics, advances current/previous and writes one audit atomically. The adapter performs no direct model write or transaction.

At cap32, the exact maximum action-owner field count is106: `1 CSRF + 3 basis + 4 scalar + 1 intro flag + 1 intro value + 32 × (title + body flag + body value)`. A canonical complete candidate is already capped at1MiB; submitted content values are a subset of that UTF-8 envelope. Adding basis/CSRF/flags and conservative `256 × 106 + 76` RFC-max multipart overhead remains below1.1MiB, far under existing4MiB/10,600 limits. A focused mechanical encoder must prove the exact106 bound without changing settings/middleware.

## 4. Browser and fail-closed behavior

Action bodies reuse current `editor.js` and its current toolbar, selection, paste, serializer and safe-link rules byte-for-byte; no second sanitizer or serializer is added. One tiny `action-copy-editor.js` knows only the fixed direct-card/title shape, verifies exact current card indices/count≤32, enables title inputs and sets `data-actions-ready=1`. It has no row factory or operation handlers.

Template titles start disabled, rich bodies are initially read-only, carriers disabled and Save disabled. `action-copy-editor.js` loads before current `editor.js`; final readiness gains one explicit actions-marker condition beside price/process/links. Existing editor.js makes every server-emitted action body rich control editable and serializes only bodies whose exact changed flag is1. Failure of either adapter leaves Save disabled and exposes the existing safe private error. No JavaScript leaves titles/bodies read-only and Save unavailable.

## 5. Acceptance before code

- `RB4-EDACT-001`: only OWNER+actions receives exact two ordered titles/bodies plus owner-only read-only internal URLs; employee/other-kind disclosure0.
- `RB4-EDACT-002`: unchanged action bodies preserve exact bytes; title-only Save changes only the same-position title and preserves count/order/internal URLs/media.
- `RB4-EDACT-003`: body-only and title+body changes at both fixed positions pass existing rich validation and preserve exact banner association; current/previous and replay are correct.
- `RB4-EDACT-004`: valid server parser/candidate paths accept current count0 with no action keys and current count32 with the exact finite keys; a validated empty snapshot renders a ready zero-card control and ordinary owner scalar/intro Save succeeds. Missing/duplicate/extra/noncanonical index, an injected33rd position/context drift, malformed flag/value, invalid title/rich, unknown/file and role/kind forgery reject before command with mutation/audit0. A canonical payload with count33 is rejected before editor projection by existing validation.
- `RB4-EDACT-005`: valid Save advances once with one audit; stale/concurrent/replay/conflict and injected validation/audit/DB rollback retain PageCAS behavior.
- `RB4-EDACT-006`: mechanical parser/candidate oracles prove valid count0 and exact32, while exact106 worst-case multipart fits existing4MiB/10,600 and candidate remains under canonical1MiB; cap33/context drift is rejected and no settings change occurs.
- `RB4-EDACT-007`: real Chromium proves no-JS/final readiness, escaped UTF-8 titles, current rich editing/serialization, independent body flags, fixed order/count, no structural operations/navigation and swapped/unsupported DOM fail-closed with partial carriers0.
- `RB4-EDACT-008`: static inspection finds model/migration/dependency/shared repeater/nested builder/rich fork/JSON/stable IDs/URL mutation/media code0.

## 6. Gates and stop rules

After independent architecture review, implementation is limited to fixed projection/dataclasses, one exact current-index parser/candidate branch, one literal template section, one tiny title/readiness adapter, one final marker condition and focused tests. Static/code review precedes separately authorized PostgreSQL and real-Chromium gates.

Stop and return to the owner if S3A requires changing count/order/internal URL/banner, identifying cards across structural changes, a generic nested/repeater/form builder, a second rich policy, schema metadata, model/migration/dependency/settings/middleware or B002/media work. The light compromise is to leave disputed fields or all actions read-only.
