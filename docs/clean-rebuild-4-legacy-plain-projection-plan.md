# REBUILD-4 — bounded legacy-plain public projection

Дата: 2026-11-20. ID: `RB4-SLICE-004C-LEGACY-PLAIN`. Статус: **code APPROVED 0/0/0; exact10/no-bloat PASS; PostgreSQL runtime separately gated**.

## Purpose and stop line

D-1715 closed exact Route visibility, but a public HTTP catch-all is still not coherent: every rendered page must use the approved shared Header/Footer and READY logo, while production-independent durable media storage `B002` remains deliberately deferred. Registering a catch-all now would create either a temporary logo-less layout or known 503 responses for valid published pages.

The smallest durable increment is therefore one pages-owned projection for the already closed, media-free `legacy_plain` payloads. It turns an already resolved `PublicPage` into an immutable typed document for the later public and preview templates. It does not emit HTML and does not introduce a renderer registry.

Included kinds are exactly:

- `legacy_partner_links`;
- `legacy_empty_main`;
- `legacy_under_construction`;
- `legacy_camera_schedule_text`.

`legacy_director_message` is excluded because its approved family may bind `hero`; all other19-kind payloads, shared layout, SiteSettings/logo, navigation selection, breadcrumbs, templates/CSS/JS, URL registration, HTTP status mapping, media open/storage, gallery, B002/import, live/deploy/push remain closed. Model, migration, dependency, cache, repository/UoW, plugin/registry and generic page-builder changes0.

## Exact public API

`modules.pages.public` adds one function and frozen DTOs only:

```text
project_legacy_plain(page: PublicPage)
  -> PublicBlank
   | PublicPartnerLinksDocument
   | PublicEmptyDocument
   | PublicLegacyTextDocument
```

Common SEO is a frozen `PublicSeo(title, description, allow_index)`. Partner links are frozen `PublicExternalLink(label, https_url)` tuples. `PublicLegacyTextDocument.kind` is restricted to the two literal text kinds above; it carries exact canonical rich `intro` and `body`. Documents retain `page_id`, `primary_target` and exact `h1`; they do not expose author, timestamps, previous revision, grants or ORM objects.

Unsupported kind is a caller-contract violation and fails closed as `PublicReadError("UNAVAILABLE")`; there is no fallback document.

## Coherent read boundary

The function never trusts the earlier `PublicPage` as permanent publication authority. One initial ORM statement reads the exact Page by `page_id` together with its one-to-one current PageContent and annotates SiteSettings singleton count plus `structure_generation`. It captures Page publication/kind and the current payload/hash in the same statement.

- Missing Page/content, hidden Page, wrong kind/identity or invalid settings singleton never leaks content. Hidden returns fieldless `PublicBlank`; every other inconsistency is `UNAVAILABLE`.
- The current hash is recomputed with the existing canonical hasher and the payload is revalidated by the one pages-owned validator before any DTO is built. Missing/corrupt/unknown fields or a media-bearing shape fail `UNAVAILABLE`; nothing is repaired.
- The Page's routes are loaded ordered by UUID and must contain exactly one valid PRIMARY whose exact target equals `page.primary_target`. The same result set must also contain exactly one valid route whose exact `target` and `mode` equal `page.requested_target` and `page.requested_mode`; a removed, retargeted or mode-changed alias therefore fails `UNAVAILABLE` instead of serving content from stale transport facts. Requested route data still does not select a template or payload.
- A final SiteSettings generation read must equal the annotated initial generation. A structure mutation between statements yields `UNAVAILABLE`; a content save after the initial statement does not mix revisions because payload and hash were captured together in that statement.
- The function performs exact3 statements: annotated Page+Content, routes, final generation. It writes0 and opens no Asset/AssetFile/AssetUsage/storage row.

An owner hide or other structure mutation committed after the initial statement but before the final generation read changes `structure_generation`, so this call fails `UNAVAILABLE`. Only a mutation committed after the successful final generation comparison may race with an already accepted document; the next call observes the hidden Page and returns blank. Adding locks, repeatable-read, cache or a public snapshot table for that final post-check window is rejected as disproportionate.

## Acceptance before code

| ID | Scenario | Required result |
|---|---|---|
| `RB4-LPLAIN-001` | hidden Page after an earlier published `PublicPage` result | fieldless `PublicBlank`; payload values absent from result |
| `RB4-LPLAIN-002` | exact partner payload with0/6/64 links | frozen ordered link DTOs; labels/HTTPS targets unchanged |
| `RB4-LPLAIN-003` | exact empty payload | SEO+H1-only frozen document; invented body/placeholder0 |
| `RB4-LPLAIN-004` | under-construction and camera text payloads | exact canonical rich intro/body and literal kind retained |
| `RB4-LPLAIN-005` | unsupported/media kind or Page/kind caller identity drift | `UNAVAILABLE`; fallback/partial document0 |
| `RB4-LPLAIN-006` | missing content, bad hash, invalid payload or kind mismatch | `UNAVAILABLE` before DTO; repair0 |
| `RB4-LPLAIN-007` | missing/duplicate/wrong PRIMARY, primary-target drift, or requested alias removed/retargeted/mode-changed | `UNAVAILABLE`; stale caller transport facts cannot substitute current Route authority |
| `RB4-LPLAIN-008` | SiteSettings missing/duplicate/invalid; structure generation changes before final comparison, including hide after initial capture | `UNAVAILABLE`; hybrid/stale output0. Mutation after the successful final comparison may affect only the next call |
| `RB4-LPLAIN-009` | actual query/fault boundary | exact3 statements on visible success; writes/media queries0; DB fault closed |
| `RB4-LPLAIN-010` | static DAG/scope inspection | pages-only reuse; HTTP/template/CSS/JS/model/migration/dependency/registry/B002 changes0 |

Focused target is exact10 methods in one new test module. Tests-first implementation starts only after independent plan approval. PostgreSQL/runtime remains a separate reviewed owner gate after code review.

## No-bloat compromise

If review shows that the DTO cannot remain useful without shared layout/logo or that correct projection requires any Asset/storage access, this slice is deferred with code0 and B002 becomes the next real prerequisite. Do not add a temporary logo path, placeholder renderer, generic dispatcher, second payload validator or catch-all to simulate progress.
