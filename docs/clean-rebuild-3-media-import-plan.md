# REBUILD-3 — минимальная media schema и одноразовый coherent importer

Дата: 2026-11-17. Plan ID: `RB3-MEDIA-IMPORT-001`. Статус: **plan/code-only gate approved; RB3-IMP-001/002/003/004 independently APPROVED 0/0/0 D-1434/D-1436/D-1437/D-1438; RB3-IMP-005 concrete-adapter remediation steps1–2 APPROVED D-1440/D-1441, step3 active; runtime0**.

## 1. Цель и authority

REBUILD-3 добавляет только недостающую target schema для media/gallery/SiteSettings и один project-owned disposable importer, чтобы перенести утверждённый snapshot в новую пустую DB+media pair. Основания:

- `docs/clean-rebuild-architecture.md` §§3, 7.1–7.2, 7.5;
- `docs/clean-rebuild-content-contract.md` — exact19 payload schemas, contextual slots и literal SiteSettings;
- `docs/clean-rebuild-transfer-contract.md` — freeze, public/private split, disposable target, seal/cleanup;
- `docs/clean-rebuild-baseline-evidence.md` — DBPRE29, exact112 Pages/exact115 Route-map rows, exact301/56,134,441 bytes, gallery17/214/41,176,391 bytes, staff/grant mappability и один deferred unmatched source;
- `docs/clean-rebuild-media-db-reconciliation-result-review.md` — duplicate identities remain distinct, unmatched eligible asset cannot be excluded, candidate-only65 remain filesystem authority.

Этот план не открывает implementation, dependency install, Docker/DB/media runtime, source freeze, target creation, importer execution, transfer, cutover or live.

## 2. Exact scope

### 2.1. Новый `modules.media`

Only three models; `MediaFolder`, `PageMediaHome`, identity/file-key reservation, deletion workflow rows, upload job, generic metadata and storage-provider tables are absent.

1. `Asset`
   - UUID `id`;
   - closed `purpose=CONTENT|SITE_ASSET|GALLERY_ORIGINAL`;
   - required lowercase `source_sha256`; imported and future uploaded sources always have a verified source hash;
   - `state=STAGED|READY` only;
   - `created_at` UTC for bounded future STAGED cleanup;
   - DB closed-purpose/state/hash constraints.

2. `AssetFile`
   - UUID `id`, FK `asset→Asset CASCADE`;
   - `kind=PRIVATE_SOURCE|MAIN|PREVIEW|LEGACY_PUBLIC`;
   - normalized relative `storage_key` max1024, globally unique;
   - lowercase SHA-256, positive `byte_size`;
   - closed `mime_type=image/jpeg|image/png|image/webp|image/svg+xml`;
   - for byte-preserved imported JPEG/PNG/WebP, `width` and `height` are either both null when no approved dimension authority exists or both positive integers ≤10,000 when supplied by an approved package; partial/zero/boolean/out-of-range dimensions are rejected. Exact reviewed trusted SVG files keep both null;
   - unique `(asset,kind)`; PRIVATE_SOURCE must live only under `private/sources/`, public kinds only under `img/`;
   - gallery originals use `LEGACY_PUBLIC` and preserve bytes; imported design files use their manifest kind. No decode/encode/dedup in REBUILD-3.

3. `AssetUsage`
   - UUID `id`, FK `asset→Asset CASCADE`;
   - closed `scope=PAGE_CURRENT|PAGE_PREVIOUS|SITE_SETTINGS`;
   - required `target_uuid` and canonical `slot` max100;
   - non-negative `position`: scalar slots require0, ordered arrays use contiguous 0..n−1;
   - unique `(scope,target_uuid,slot,position)` and `(scope,target_uuid,slot,asset)`;
   - `target_uuid` is the Page UUID for PAGE_CURRENT/PAGE_PREVIOUS and the SiteSettings UUID for SITE_SETTINGS;
   - slot/cardinality/position is accepted only by the existing exact content/SiteSettings registry; arbitrary strings, gaps, repeated Asset within one slot and cross-module FK are absent;
   - only READY Asset may be referenced, enforced by importer/service validation because a DB CHECK cannot inspect another row.

Asset deletion remains blocked while any `AssetUsage` or `GalleryPhoto.asset` exists. Product upload/replace/delete commands, worker and physical cleanup are later slices; REBUILD-3 only imports already verified bytes as READY.

### 2.2. Новый `modules.gallery`

1. `GalleryAlbum`: UUID `id`, OneToOne `page→Page PROTECT`, positive `generation` for gallery composition CAS/audit, non-negative `position`, unique position.
2. `GalleryPhoto`: UUID `id`, FK `album→GalleryAlbum CASCADE`, FK `asset→Asset PROTECT`, non-negative `position`, required normalized plain `alt` 1..1,000 code points; unique `(album,position)`.

Album Page owns name/URL/current content. Gallery tables own only album/photo order and alt. Source URL, local path, SHA and bytes do not duplicate into GalleryPhoto; they belong to the import manifest/AssetFile. Captions, EXIF, arbitrary metadata JSON and derivative tables are absent.

### 2.3. `pages.SiteSettings`

SiteSettings is included now only because its required logo needs a real `media.Asset` FK. It is one literal singleton, not key/value storage:

- UUID `id` plus unique/check `singleton_key=True` (at most one row; importer/service requires exactly one);
- positive `structure_generation` and `settings_generation`;
- exact fields and caps from content contract §5: organization/legal names, display/E.164 phone, address, opening hours, contact email, map/max/telegram URLs;
- `logo_asset→Asset PROTECT` and exact `SITE_SETTINGS/target_uuid/logo` AssetUsage;
- import requires READY logo and null gated legal/social values unless their separate authority exists.

No settings form, edit command, header/footer renderer or structural command is implemented in REBUILD-3.

### 2.4. Existing target data imported

One target transaction imports only the already approved target projections:

- staff with fresh UUIDs/unusable passwords and memory-only source-key map;
- PageGrant through that same map;
- Pages, Routes, exact current+previous plus provenance;
- SiteSettings singleton;
- distinct Asset identities, AssetFiles and exact contextual usages;
- GalleryAlbum17/GalleryPhoto214;
- no ServiceRequest rows: freeze must re-prove active requests=0. Any nonzero request/ledger condition blocks the run pending LEGAL-01 and a new scope decision;
- no old sessions, audit history, drafts, Stable/manual history, restore stages, reservations, logs or deletion workflow rows.

## 3. Import identity and file rules

- Public Page/Route/Asset/File/Gallery IDs come only from the closed manifest/approved packages and remain stable because payload refs depend on them.
- Candidate-only filesystem rows without an authority UUID receive one random UUIDv4 for Asset and one for AssetFile exactly once while the canonical public manifest is built. Package-bound IDs win when present. The allocated IDs are written into that manifest and every payload/usage/gallery reference in the same snapshot uses them; they are never derived from path/hash/content. Every fresh target attempt against the same unchanged manifest reuses these public IDs. Only a new coherent freeze and new canonical manifest may allocate new candidate-only public IDs. Staff UUIDs remain fresh per disposable target run.
- Source numeric staff keys never leave private memory; target staff UUIDs are fresh each run and never recorded in a mapping table/file/log.
- The duplicate DB pair remains two Assets with their separate usages. REBUILD-3 copies separate target keys; physical dedup/hardlinks/content-addressed storage are forbidden.
- Candidate-only65 receive only their already approved manifest identities; filesystem presence cannot create an Asset.
- The one unmatched eligible source is resolved only inside coherent freeze by its approved exact DB-key→contained regular file→size/SHA contract. Missing/ambiguous/drift blocks before target mutation; no search/fallback/allowlist growth.
- Exact214 gallery originals are copied byte-for-byte; upload decoder/worker is not invoked.
- Every target key is generated from the manifest Asset/File identity under the disposable run media root, not accepted from CLI/user input.

The counts are deliberately split instead of calling every layer `exact301`:

- accepted known unique-source cohort before freeze resolution: `301 files / 56,134,441 bytes`;
- coherent-freeze unique-source cohort after resolving the one unmatched file: `302 files / (56,134,441 + U) bytes`, where exact `U` and its SHA are fixed by the approved resolution contract;
- target AssetFile rows and physical copies: `303 files / (56,134,441 + U + D) bytes`, because the known duplicate source pair remains two target identities with two generated keys; exact duplicate size `D` and all three layer digests are fixed at freeze before target mutation.

This is not automatic allowlist growth: row302 is admitted only by the one already approved unmatched DB identity, and row303 is only the second copy of the already approved duplicate identity. Gallery remains exact214 inside all layers.

Target `storage_key` is generated in one of two ASCII forms only: `img/<asset-uuid>/<kind>.<ext>` or `private/sources/<asset-uuid>/source.<ext>`, with lowercase canonical UUID/kind/extension. Source relative paths and generated keys use `/` only and NFC; empty/dot/dot-dot components, backslash, colon, percent escapes, controls/whitespace, reserved device names, trailing dot/space and NFC/casefold collisions are rejected. Before every read/write the canonical parent and each existing component must be contained, regular where applicable and non-link/reparse; final creation uses exclusive new paths. Extension, closed MIME and file magic must agree. SVG is accepted only for the exact reviewed three-file trusted-SVG cohort with pinned SHA/size, never from DB rows or user upload; no arbitrary SVG parsing/import is added.

## 4. One-shot importer boundary

The importer is one fixed offline coordinator plus small module-owned validators. It is not a reusable ETL framework.

Fixed sequence:

1. preflight reviewed code/contracts/migration leafs and exact caps;
2. prove old writers0 and create fresh read-only source identity;
3. compute `media_before`, open one source RRRO transaction, read public counts/rows and snapshot ID, compute equal `media_after`;
4. resolve the one deferred source within the same freeze evidence and produce the closed public manifest in ignored owner-only staging;
5. while the same source RRRO remains open, prove aggregate `active requests=0`, latest request-ledger identity/generation/digest validity, selected current/previous author mappability0, invalid staff role/profile0 and grant user/page mappability0; this reads no private values and any nonzero/ambiguity stops before target creation;
6. validate the complete public manifest and all source files/caps/hashes, including separate 301/302/303 arithmetic/digests, before target creation;
7. generate a new run UUID; create only a new empty `estakada_rebuild_<uuid>` DB and contained `<uuid>/media` root. Before migration, prove global/DB role matrix, remove the exact empty default `public` schema, create only owner-owned `app` and close PUBLIC/default privileges. Apply exact target migrations; then return migrator NOLOGIN/remove its secret and prove the actual post-migration table/sequence privilege matrix before any private-value read/importer LOGIN;
8. open one target transaction; import public rows, stream staff/grants from the still-open source snapshot, and apply the latest verified zero-row request ledger as an explicit no-op whose generation/digest is recorded only in the safe result;
9. copy files only into the disposable media root, re-hash, verify DB constraints/usages/current+previous/counts/digests; then commit target DB;
10. read back committed DB+media; only exact equality writes a flushed write-once `SEALED` safe result;
11. close source/target identities/secrets and keep old writers stopped for a separate owner decision.

Failure never resumes in place. It closes connections/private memory, marks `FAILED` only when unambiguous, and cleans only the exact disposable pair after identity/containment/owner/no-connection/no-pointer checks. Ambiguity remains isolated for owner inspection. No current pointer/runtime/Nginx/live setting is changed.

The public manifest contains no private rows/absolute paths/file bytes. Output/logging is limited to phase, safe error code, counts and digests. Arbitrary table/query/path/module/class/field/batch arguments, plugin hooks and custom transforms do not exist.

Database authority is closed and least-privilege:

- the already controlled local PostgreSQL administrative identity only creates/drops exact generated roles/database after collision/ownership checks; it never reads source/private application rows;
- one fresh target owner/migrator role is created NOLOGIN with `NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS`, connection limit1, no memberships and no source grants. The admin creates the exact target DB owned by this role, proves the standard default `public` schema is empty, drops only that schema, and creates only owner-owned `app`; the role then owns only that DB/`app` plus its migration-created objects and has required target-only DB `CONNECT|CREATE|TEMP` and schema ownership/DDL. LOGIN+random secret+bounded validity are enabled only for one exact migration connection, then immediately returned to NOLOGIN and the secret is removed. Exact role settings only: `search_path=app,pg_catalog`, `statement_timeout=5min`, `lock_timeout=5s`, `idle_in_transaction_session_timeout=1min`;
- one fresh target importer role is created NOLOGIN with the same seven negative global flags, connection limit1, no memberships, no ownership and no source grants. For the bounded import only it receives LOGIN+random secret+validity, DB `CONNECT` but no `CREATE|TEMP`, schema `USAGE` but no `CREATE`, and literal `SELECT|INSERT` only on the exact fixed target projection tables; `UPDATE|DELETE|TRUNCATE|REFERENCES|TRIGGER` and all sequence privileges are absent. Its exact settings are `search_path=app,pg_catalog`, `statement_timeout=15min`, `lock_timeout=5s`, `idle_in_transaction_session_timeout=1min`; then it returns to NOLOGIN before drop;
- before the migration connection, verify global flags/memberships/settings/DB ownership, revoke target DB `CONNECT|CREATE|TEMP` from PUBLIC, remove the empty default `public` schema, create `app`, revoke its PUBLIC privileges and set owner-specific default privileges so future app tables/sequences/functions/types grant PUBLIC nothing. Immediately after migrations and before any private read/importer LOGIN, return migrator NOLOGIN/remove its secret, revoke PUBLIC on the actual app objects, enumerate every table/sequence/owner/default privilege, and require the final owner/importer matrices above. Unexpected setting, membership, owner, grant, schema/object, default privilege or PUBLIC leakage blocks;
- role names are generated from run UUID, connection limit1, bounded validity; random secrets exist only in owner-only ignored files/tmpfs and never argv/output;
- after seal/failure, connections close, roles become NOLOGIN, literal grants are revoked and exact secrets are removed. The importer role is dropped when unchanged. On failed-run cleanup, the exact DB is dropped before its owner/migrator role; on successful SEALED isolation that owning NOLOGIN role necessarily remains bound to the retained DB until later promotion or exact-pair deletion. Cleanup first proves database owner, schema owner, role OIDs/config/membership, no active connections and no current/candidate pointer; ambiguity leaves the isolated pair and roles fail-closed for owner inspection.

## 5. Tests before implementation

All acceptance fixtures precede product/importer code. Static/synthetic tests run before any future source/target runtime. Exact runtime evidence requires a later owner gate.

- model constraints and migration source for media/gallery/SiteSettings;
- DAG: `media→audit`, `pages→accounts,media,audit`, `gallery→pages,media,audit`; private/reverse/cyclic imports fail;
- closed manifest parser rejects unknown/duplicate/private fields, absolute paths, invalid UTF-8, caps and digest drift;
- source staff map never serializes and missing/duplicate/unmapped provenance/grant fails;
- duplicate physical pair keeps two Asset identities/usages; unmatched absence fails; candidate-only filesystem extras do not import;
- exact current/previous and positioned usage reconciliation, SiteSettings logo usage, gallery17/214 generation/order/alt and byte identity;
- failure injection before target mutation, during DB import, file copy, before/after commit and before seal; no selectable partial target;
- exact cleanup refuses foreign/current/nonempty-ambiguous targets and cannot touch source/other run;
- request count0 gate; no request schema/data import in this slice;
- safe output scan proves private values, secrets, source numeric keys, absolute paths and file bytes absent.

## 6. Acceptance IDs

- `RB3-AC-001`: schema contains exactly Asset/AssetFile/AssetUsage, GalleryAlbum/GalleryPhoto and literal SiteSettings addition; forbidden placeholder/workflow/mapping/storage tables0.
- `RB3-AC-002`: DB constraints close purpose/state/kind/MIME/hash/size/dimension/key/position/uniqueness/FK/gallery-generation/singleton shapes; cross-row READY/exact-one/registry rules stay explicit service/import invariants.
- `RB3-AC-003`: exact module DAG passes; old `app/` imports0 and importer never imports source Django runtime.
- `RB3-AC-004`: manifest is closed, bounded and public-only; unknown/private/absolute/over-cap/drift rejects before target mutation.
- `RB3-AC-005`: exact112 Pages and exact115 Route-map rows validate with every current+previous/null/provenance/hash; old history/drafts/stages are absent.
- `RB3-AC-006`: fresh staff UUID memory map is one-to-one and binds provenance/grants without persistent mapping or password/session copy.
- `RB3-AC-007`: request rows must be0 and latest ledger valid; request/staff/provenance/grant aggregate ambiguity blocks before target creation/private-value read, and the verified ledger applies as a zero-row no-op before commit.
- `RB3-AC-008`: known source301/56,134,441, resolved unique source302/`+U`, target copies303/`+U+D`, separate digests and gallery214/41,176,391 match freeze evidence; unused16/error2/tree extras remain excluded.
- `RB3-AC-009`: duplicate pair preserves two Assets/usages/files/keys without dedup; unmatched eligible source resolves exact or whole run fails; candidate-only65 get package IDs or one-time manifest UUIDs stable across fresh target attempts for that manifest, never content-derived identities.
- `RB3-AC-010`: every copied file lands under exact disposable root, is regular/non-link, and matches size/SHA; gallery originals are byte-identical.
- `RB3-AC-011`: target AssetUsage target UUID/slot/position/cardinality matches PAGE_CURRENT/PAGE_PREVIOUS/SITE_SETTINGS registry without gaps/repeated asset; GalleryPhoto direct FK/generation/order/alt matches exact17/214 package.
- `RB3-AC-012`: SiteSettings is exactly one valid row with READY logo+usage and no generic JSON/unknown social/legal publication.
- `RB3-AC-013`: target DB commits only after public/private/files/usages/counts/digests pass; seal requires post-commit DB+media read-back equality.
- `RB3-AC-014`: failed/unsealed/unknown run is never selectable or resumed; next attempt uses a new empty pair.
- `RB3-AC-015`: cleanup is exact-pair only and fail-closed on identity/containment/ownership/connection/pointer ambiguity; source/current/other run unchanged.
- `RB3-AC-016`: importer changes no current pointer/runtime/Nginx/live config; only later `REBUILD-Q003` may select a SEALED pair.
- `RB3-AC-017`: safe outputs contain only phase/error code/counts/digests; private values, source keys, secrets, paths and bytes0.
- `RB3-AC-018`: no-bloat diff proves dependency only when separately approved for actual content validation, service/daemon/queue/worker/plugin/repository/UoW/dedup/framework0.
- `RB3-AC-019`: source reader, target owner/migrator and target importer have disjoint literal global flags, memberships, settings and effective DB/schema/table/sequence privileges; pre-migration DB/empty-public/app/default-privilege proof and post-migration actual-object proof both pass, PUBLIC leakage0, bounded LOGIN/secrets and exact OID/ownership cleanup; no generic privileged importer connection.

## 7. Proposed implementation slices after separate approval

1. `RB3-IMP-001`: tests-first media/gallery/SiteSettings models, migrations and DAG fitness.
2. `RB3-IMP-002`: closed public manifest DTO/parser and target projection validators; synthetic data only.
3. `RB3-IMP-003`: fixed source reader/private in-memory map and pre-target freeze checks; no execution.
4. `RB3-IMP-004`: disposable target coordinator, exact copy/seal/cleanup state machine; synthetic fakes first.
5. `RB3-IMP-005`: independent whole-slice code review and static/no-runtime proof.
6. Later separate runtime gates: isolated synthetic rehearsal first; coherent real freeze/import only after its own reviewed plan and explicit owner authorization.

Before implementation, exact reuse/addition of the content-validation dependency (notably `nh3`) requires a separate owner version/dependency acknowledgement. Pillow/codec worker is not required for byte-preserving REBUILD-3 import and stays deferred.

## 8. No-bloat stop rules

Stop and return to owner instead of expanding if implementation appears to require any of:

- general ETL/configurable mapping engine or second manifest format;
- persistent source→target identity table, receipt/event/job queue or resumable run;
- storage abstraction, remote object store, physical dedup/hardlinks or gallery derivatives;
- private temp JSON/CSV fallback instead of same-snapshot DB→DB stream;
- request import with nonzero rows before LEGAL-01;
- automatic allowlist growth/search for the unmatched asset;
- changes to current runtime, pointer, Nginx, source DB/media or live.

Light compromise in every case is fail-closed one-run code with fixed schemas and a new explicit owner decision only for the exact blocker.
