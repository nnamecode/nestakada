# RB4 typed rich-field wire decision

Дата: 2026-11-18. ID: `RB4-RICH-Q001`. Статус: **owner selected recommended option1 on 2026-11-18; bounded contract review active**.

## Why a decision is required

The approved payload contract stores exact canonical `estakada-rich-v1` HTML and already closes tags, attributes, URLs, caps and server validation. The admin contract simultaneously forbids arbitrary HTML, generic JSON/page builders and the historical raw HTML mode. It does not yet define the form wire that lets a person edit a rich fragment and deterministically produces canonical bytes again. Choosing that wire in code would be a new UX/architecture decision under D-041.

## Options

1. **Recommended light option — one local visual adapter.** Server renders literal fixed fields for the 19 known kinds. Only contract-declared rich fields receive one small local `contenteditable` control and deterministic allowlist DOM serializer; raw source is never shown. No CDN, dependency, framework, plugin API, block schema, persistent editor state or generic registry. Literal controls: paragraph, H2/H3, bold/italic/underline/strike, ordered/unordered list, blockquote and link/unlink. Existing allowed tables/sub/sup remain visible and text-editable but get no structure builder in this slice. Paste is plain text or rejected. Existing server validator remains authoritative; No-JS is read-only and Save is unavailable.
2. **Defer rich Save.** Implement no partial or raw-HTML workaround. Typed editor vertical slice remains open and work moves only to another separately approved area. GET/Undo-only scaffolding is not called a completed editor.

Raw restricted-HTML textarea is rejected because it recreates the excluded HTML mode. A structured block editor is rejected because it creates a second content representation and generic builder subsystem.

## Acceptance if option1 is selected

- literal server-owned field map; client cannot choose schema, path or field names;
- stored fragment is exactly revalidated before private render; corruption returns one private constant error;
- unchanged rich round-trip retains exact canonical bytes;
- deterministic serializer accepts only the literal allowlist and canonical attribute order/value rules; `innerHTML` is never authority and deprecated `execCommand` is not used;
- forbidden paste/node/attribute/link and server-bypass submission fail the whole Save without mutation/audit;
- employee form contains only exact granted `intro/body` and/or price controls; protected values are absent, not hidden carriers;
- cap/cap+1, CSRF, role/session, CAS/replay/stale, audit/usages and Undo guarantees remain the existing PageCAS authority;
- one local JS file only; design polish, media preview/upload, Nginx/browser/live remain later gates.

Independent architecture review classified the unresolved wire as P1 and browser normalization as P2, recommended option1 as the smallest clean compromise, and rejected raw HTML and block-builder alternatives. Product code/runtime0 pending owner answer.
