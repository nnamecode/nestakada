# RB4 typed editor 001B-S4 — reference authority boundary

Дата: 2026-11-19. ID: `RB4-EDITOR-001B-S4-REFS`. Статус: **no-code/read-only defer APPROVED by D-1642, review0/0/0/product0/no-bloat; reopen only with B002/public per-field authority**.

## 1. Observed authority

The home payload schema contains three ordered canonical UUID arrays: `service_refs[]≤12`, `brand_refs[]≤20`, `review_refs[]≤12`. Current freeze/import authority emits all three as exact empty arrays. The canonical validator proves only UUID syntax, uniqueness and caps; it does not define target table, target kind, existence, route/content coherence, publication state or deletion behavior.

`Page` is the only plausible existing UUID target for service refs, but no approved allowlist says whether master/service catalogs, section overviews, details, hidden/unpublished pages or legacy service aliases may be selected. A JSON Page UUID has no database FK, reverse index or target lock in current PageCAS. The confirmed leaf Page deletion contract does not specify scanning/rejecting/removing JSON refs. Therefore a selector-only editor could accept a target that is concurrently deleted or later leave an untracked stale reference.

There is no Brand model/entity. Approved brand UI is a logo carousel/media composition and explicitly does not auto-create brand pages. The structured `reviews[]` items have no UUID, and approved homepage reviews use an official external widget plus a link to `/reviews`; there is no stable Review entity target. Treating media UUIDs, Page UUIDs or invented IDs as `brand_refs`/`review_refs` would silently choose a new content model.

## 2. No-code decision candidate

Keep all three ref arrays read-only and copied unchanged through owner Save/Undo exactly as today. The editor continues to show only deferred counts and accepts no ref carrier. Do not add a raw UUID input, Page selector, generic relation picker, target-kind registry, JSON reference index, new model/migration, backref scan, deletion cascade or public renderer assumption.

Move exact semantics to the smallest later authority that has real non-empty data and lifecycle rules:

- `service_refs`: after B002/full Page authority or public-home composition defines exact eligible kinds, route/publication visibility, PageCAS target locking and leaf deletion behavior;
- `brand_refs`: resolve together with brand logo media/composition; if no separate Brand entity is approved, retire or leave the empty field rather than invent one;
- `review_refs`: resolve with the accepted official-widget integration and `/reviews` composition; do not create local review identities solely for this editor.

This is a defer, not silent removal of the schema fields or product requirements. Current empty values remain canonical and migration-compatible.

## 3. Acceptance and reopen gate

- `RB4-REF-AUTH-001`: source/freeze evidence shows exact empty arrays and caps12/20/12.
- `RB4-REF-AUTH-002`: current code has UUID-shape validation but target-kind/existence/backref/deletion authority0.
- `RB4-REF-AUTH-003`: Brand entity0; local Review stable IDs0; approved brand/review composition does not justify Page UUID targets.
- `RB4-REF-AUTH-004`: no code/model/migration/dependency/selector/registry/index/cascade is added; existing owner/employee wire and PageCAS remain unchanged.
- `RB4-REF-AUTH-005`: reopening requires one approved per-field target contract with non-empty authority, exact UI projection, concurrent Save/Delete behavior and public consumption; fields may be split rather than forced through one generic abstraction.

## 4. Stop and no-bloat rule

Stop if `S4` requires guessing target kinds, exposing raw UUIDs, querying every possible content table, creating generic polymorphic refs, scanning all JSON on deletion or coupling editor implementation to unfinished public/media work. The light compromise is the present read-only count until a specific later field becomes independently implementable.
