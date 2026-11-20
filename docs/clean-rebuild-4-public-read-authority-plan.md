# REBUILD-4 — bounded public read authority

Дата: 2026-11-19. ID: `RB4-SLICE-004B-PUBLIC-READ`. Статус: **code APPROVED D-1694 review0/0/0, product0/no-bloat; exact10, PostgreSQL plan review next, runtime0**.

## Purpose and stop line

After D-1687 the smallest B002-independent increment is the pages-owned read authority required by D-052/D-238–D-240/D-244. It resolves an exact existing Route into a typed visibility result and projects automatic navigation with hidden-ancestor promotion. It performs no write and adds no public HTTP catch-all yet.

Deferring HTTP is deliberate: a catch-all before the published-page renderer would either expose a temporary placeholder or return a knowingly incomplete 503 for every valid published Page. This slice therefore supplies one exact authority to the later renderer instead of creating a temporary renderer, second routing model or duplicate navigation tree.

Out of scope: HTML/template/CSS/JS, shared Header exact-six, breadcrumbs, payload rendering, media open/storage, SEO/sitemap/robots, gallery, forms, create/move/reorder/URL/delete commands, B002/import, live/deploy/push. Model, migration, dependency, cache, snapshot table, generic resolver framework and background work changes0.

## Exact public API

One new module `modules.pages.public` exposes only frozen typed results and two functions:

```text
resolve_public_target(target: str) -> PublicBlank | PublicPage | PublicRedirect
project_public_navigation() -> tuple[PublicNavigationItem, ...]
```

Errors are closed typed `PublicReadError(code)` with only `NOT_FOUND` or `UNAVAILABLE`. The future HTTP adapter alone maps them to404/503 and maps `PublicBlank` to the D-052 zero-body200; this slice does not claim HTTP evidence.

### Exact target resolution

- Input is one exact `str`,1..2048 characters, beginning with one `/`, with no fragment, backslash, whitespace/control character, malformed percent escape or dot segment. Invalid input is `NOT_FOUND` before DB. The exact string, including case, percent spelling, trailing slash and query ordering, is looked up in the unique Route namespace; no normalization, redirect guessing or fallback.
- Unknown target is `NOT_FOUND`. Exactly found Route is revalidated through the existing Route contract with its Page.
- PRIMARY or ALIAS whose Page is hidden returns fieldless `PublicBlank` immediately after the one Route+Page query. It performs no PageContent, Asset, AssetUsage or navigation query and exposes no Page UUID/name/kind/target.
- PRIMARY or ALIAS whose Page is published uses the existing structure-generation capture described below, loads that Page's routes ordered by UUID, requires exactly one valid PRIMARY, and returns `PublicPage(page_id, kind, requested_target, primary_target, requested_mode)`. It does not load payload/media or claim renderability; the later coherent renderer owns those checks.
- REDIRECT, whether its Page is hidden or published, uses the same structure-generation capture, loads the same Page's routes ordered by UUID, requires one valid PRIMARY different from the redirect target and returns `PublicRedirect(primary_target)` directly. Chains and cross-Page redirects are impossible because Route links to Page, not another Route. Redirect HTTP status is not emitted in this slice.
- SYSTEM/fallback route type does not exist in the clean model. Any unknown mode/outcome, invalid PRIMARY, requested PRIMARY ambiguity or DB error is `UNAVAILABLE`, never partial output.

The initial exact-target Route+Page statement also annotates two scalar subqueries from SiteSettings: singleton row count and `structure_generation`. Count must be exactly1 and generation positive. Hidden PRIMARY/ALIAS returns after that one statement and needs no recapture. Published/redirect then performs the ordered same-Page routes query and finally reads the exact singleton generation again; missing/ambiguous/non-positive/mismatched final state is `UNAVAILABLE`. Because the initial Page/Route and initial generation share one SQL statement snapshot, a structural commit before, between or after later statements yields one committed state or mismatch, never an accepted hybrid. There is no lock or retry: the caller may retry as a new request.

## Automatic navigation projection

Navigation remains a projection, not editable storage:

- After reading the exact singleton structure generation, query1 reads at most513 Page rows ordered by UUID; more than512 is `UNAVAILABLE`. Query2 reads all PRIMARY routes for those Page IDs ordered by `(page_id, route UUID)`. A final generation read must equal the first before any output is returned. Other Route modes never create navigation entries.
- Every published Page requires exactly one revalidated PRIMARY matching its kind. Hidden Pages require no route and contribute no label/link.
- The full parent graph is validated in memory: parent must be in the captured set or null; self/cycle/disconnected ancestry is `UNAVAILABLE`. No DB recursion or per-row query.
- Published Pages are attached to their nearest published ancestor. Any number of hidden ancestors is skipped without changing stored parent. A published Page with no published ancestor becomes a root. Hidden descendants remain absent; independently published descendants remain visible.
- Each output sibling set is ordered exactly by stored `(position, UUID)`. Output is a frozen recursive `PublicNavigationItem(page_id, name, primary_target, children)` tuple. Projection writes0 and a subsequent commit is observed on the next call; no cache/version/snapshot is added.
- Fixed approved Header exact-six is not generated from this tree. The later family/catalog renderer may consume only its appropriate navigation block. Breadcrumbs may reuse the same validated capture later but are not implemented here.

The generation-before/after capture makes a structural commit between statements fail `UNAVAILABLE`; a commit wholly before or after the capture permits one committed state. Adding read locks, a database isolation change, global snapshots, cache or retry loop is disproportionate for rare owner mutations and forbidden in this slice.

## Acceptance before code

| ID | Scenario | Required result |
|---|---|---|
| `RB4-PREAD-001` | hidden PRIMARY and hidden ALIAS with missing/corrupt content/media | fieldless `PublicBlank`; exactly one Route+Page query; content/media/navigation reads0 |
| `RB4-PREAD-002` | published PRIMARY and ALIAS | same Page identity, exact requested mode/target and one validated canonical PRIMARY |
| `RB4-PREAD-003` | hidden/published REDIRECT | one direct canonical PRIMARY target; chain/cross-Page/target-equality impossible or closed unavailable |
| `RB4-PREAD-004` | malformed/unknown/deleted exact target | `NOT_FOUND`, no approximate match or private disclosure |
| `RB4-PREAD-005` | missing/wrong/corrupt PRIMARY or Route composition | `UNAVAILABLE`, partial result0 |
| `RB4-PREAD-006` | published roots/children and hidden nodes | only published entries; exact `(position, UUID)` order |
| `RB4-PREAD-007` | one/multiple hidden ancestors with published descendants | descendants promoted to nearest published ancestor/root; stored parent/flags unchanged |
| `RB4-PREAD-008` | cycle/missing ancestor/cap513/route drift or structure commit between capture statements | whole projection `UNAVAILABLE`, no partial tree/hybrid; concurrency barrier proves committed-state-or-unavailable |
| `RB4-PREAD-009` | actual query budget and fault injection | hidden short branch1 statement; published/redirect exact3 statements (annotated initial, routes, final generation); navigation exact4; writes0; DB fault closed |
| `RB4-PREAD-010` | static DAG/scope inspection | pages imports no web/shared/media; reverse imports0; model/migration/dependency/HTTP/template/framework changes0 |

Focused target is exact10 methods in one new test module. Tests-first code begins only after independent plan approval. PostgreSQL/runtime remains a separate reviewed owner gate after code review.

## No-bloat compromise

If a correct result requires rendering payloads, opening media, shared Header/Footer, catch-all URL registration or a second stored tree, stop and defer that part to the next coherent public-render integration. Do not add a generic repository/service/UoW, recursive SQL abstraction, cache or placeholder page to make this slice appear larger.
