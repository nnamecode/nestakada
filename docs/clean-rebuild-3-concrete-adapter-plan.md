# REBUILD-3 — concrete one-shot adapter remediation

Дата: 2026-11-17. ID: `RB3-ADAPTER-001`. Статус: **code-only whole slice closed by owner option2 D-1452 on independently APPROVED D-1440–D-1450; D-1448 cleanup remains deliberately deferred/fail-closed to Q003; D-1451 WHOLE-001 remains paused/no-verdict rather than relabelled; product findings0, runtime0; next local rebuild execution plan/preflight is separately gated**.

## 1. Причина и граница

Whole-slice review RB3-IMP-005 установил P1: `SourceExecutor`, `LatestLedgerVerifier` и `RunOps` существуют только как Protocol/fakes, поэтому одобренные validators/coordinator ещё не образуют исполнимый importer.

D-1439 разрешает один project-owned concrete adapter. Он принимает уже независимо проверенный `VerifiedLedgerEvidence` только в памяти. Adapter не читает и не определяет формат external deletion ledger/backup, не создаёт ledger authority и не расширяет LEGAL-01. Runtime, Docker/DB/media mutation, freeze, target creation и execution по-прежнему требуют отдельного owner gate.

## 2. Минимальный состав

Ровно четыре code-owned части, без повторения доменных validators:

1. `runtime_source.py`: единственный lifecycle/factory создаёт fresh source identity, доказывает grants, открывает одну RRRO connection, возвращает concrete psycopg executor с captured backend PID+transaction ID+snapshot и единожды выполняет connection→NOLOGIN→sessions0→literal revoke→conditional exact drop→secret removal. `ProvidedLedgerVerifier` принимает один `VerifiedLedgerEvidence` только из Python call и привязывает его к captured snapshot; ledger argv/env/file отсутствуют. `runtime_target.RunOps.close_source_identity()` только делегирует этому lifecycle один раз.
2. `freeze.py`: fixed source-row→canonical public manifest builder. Он использует текущую RRRO, approved route/content/media/gallery packages и один resolved unmatched source; public IDs сохраняются в canonical manifest, staff/request/ledger values туда не входят. D-1458 distinguishes exact114 stored non-system Route rows from exact115 public URL outcomes: gallery `?page=1` is a derived redirect and is not a fabricated Route row.
3. `runtime_target.py`: concrete `RunOps` для generated disposable names only. Через psycopg administrative connection и Django `MigrationExecutor` создаёт/проверяет exact roles/database/schema, применяет текущие migrations, импортирует literal projections одной transaction, копирует/хеширует файлы под approved root, делает readback/seal/cleanup.
4. `run.py`: один callable `run(config: RunConfig, evidence: VerifiedLedgerEvidence)`. По D-1449 `RunConfig` — closed DTO с source/target endpoint (включая exact fixed DB authority, TLS CA и owner-only secret refs), одним уже типизированным in-memory `FreezePackage`, exact `ManifestLimits`, externally fixed expected package digest, source-media root, target-rebuild root и result root. Отдельный `canonical package root`/legacy JSON loader и неиспользуемый staging root не добавляются: 12 разнородных DEV JSON уже имеют собственные historical validators и не становятся вторым runtime format. Evidence передаётся только memory-to-memory вызывающим independently verified component; standalone CLI/env input отсутствует. CLI table/query/path/plugin/transform/batch overrides отсутствуют.

Новые library dependencies не добавляются: используются pinned Python/Django/psycopg/nh3 и stdlib.

## 3. Закрытые данные и преобразования

Source identity grants exactly `CONNECT` on the exact source DB, `USAGE` on schema `app`, table `SELECT` on `auth_user`, `accounts_userprofile`, `accounts_pagegrant`, `content_page`, `content_route`, `page_versions_pagecontentstate`, `page_versions_pagerevision`, `shared_content_sharedblock`, `shared_content_sharedrevision`, `media_library_mediafolder`, `media_library_pagemediahome`, `media_library_asset`, `media_library_assetfile`, `media_library_assetusage`; plus only column `SELECT(id)` on `service_requests_servicerequest`, read solely as aggregate `count(id)`. PUBLIC and other DB/schema privileges and all other non-system table/column/sequence privileges are0. Tests prove required CONNECT/USAGE/SELECT and every negative DB/schema/table/column/sequence case.

Literal query groups: exact112 Page rows and exact114 stored non-system Route rows with tree+publication; the approved route map still has exact115 public outcomes because gallery `?page=1` is one derived redirect. Selected current+immediate previous payload/hash/time/generation; referenced shared current projections; media assets/files/usages/home bindings; staff/grant/provenance mappability/private stream; request-id count0. Builder exact-joins these facts to canonical route map, approved migration JSON, gallery/media evidence and resolved unmatched binding. Missing/extra/duplicate row, kind/URL/payload/media conflict or oracle mismatch blocks before manifest publication/target creation; DB/package facts are never silently rewritten.

- Source Page/Route/public media IDs остаются UUID. Numeric только source staff key; он существует лишь внутри `SourceReader` map.
- Each Page row gets exact positive integer `content_generation` beside `current`/`previous`. Payload envelope and payload SHA remain unchanged; canonical manifest digest is recalculated over the new closed row schema.
- Each non-null current/previous `created_at` is canonical UTC `YYYY-MM-DDTHH:MM:SS.ffffffZ` with exactly six fractional digits. Builder converts an aware source value to UTC once; parser rejects naive, offset, non-canonical, invalid-date and normalization-changing text before target creation.
- Current/previous author связывается только private stream; password hash/email/session/token не читаются. Target password ставится Django-unusable, email/имя-профиль пустые, role/active/generation — из approved private row.
- Target PageGrant получает fresh UUID and exact canonical groups; owner/inactive/nonmatching kind запрещены ранее pre-target gate и повторно adapter validation.
- Requests rows0; preverified latest ledger применяется как zero-row no-op. Никакого private JSON/CSV/temp fallback.
- Storage keys генерируются только существующим closed manifest rule. Source paths никогда не становятся target keys и не входят safe result.

## 4. Lifecycle и least privilege

Adapter реализует literal D-1433 role matrix, а не принимает grant list/config:

- fresh source reader identity: fixed allowlist, connection limit1, bounded validity, RRRO/TLS; success/failure close→NOLOGIN→sessions0→literal revoke→conditional exact drop→secret deletion;
- target owner/migrator and importer names derive only from run UUID; negative global flags/membership0/settings/PUBLIC/default privileges and pre/post-migration object matrix проверяются literal SQL;
- target importer получает LOGIN/secret только после migrations/privilege proof and before private read; после import возвращается NOLOGIN, secret removed;
- source transaction remains open through public builder/private stream and closes only after committed readback equality;
- no current/candidate pointer, HTTP, Nginx, live settings or old-writer restart.

## 5. Files, result и cleanup

- `RunConfig` has one approved absolute existing owner-only non-link `source_media_root` and a separate target rebuild root. Manifest source paths are relative-only canonical `/` components. Adapter walks components without following links, opens the final file no-follow, proves regular-file identity and containment, and reads size+SHA from that same handle while old writers remain0. No close/reopen-by-path verification. Target run path is exactly `<target_rebuild_root>/<run-uuid>/media`.
- Pre-target validates every source file/cap/hash. Copy uses exclusive creation, no overwrite/link/dedup, then byte count+SHA readback.
- On the same opened source handle, extension, declared MIME and literal magic bytes must agree. Byte-preserved imported raster dimensions may be null only as an all-or-nothing pair when no approved dimension authority exists; no values are guessed or decoded. SVG is accepted only when its SHA belongs to the manifest limits' exact reviewed trusted-SVG cohort and its safe SVG boundary passes; no decoder/codec/worker or MIME-guessing fallback is added.
- Result authority is generated only as `<result_root>/<run-uuid>/` under an approved owner-only non-link root. It has one write-once `CREATED` and exactly one write-once terminal `SEALED` or `FAILED`; exclusive same-directory temp, file flush, atomic rename and directory flush are mandatory. Unknown/extra/link/non-regular file or both terminals makes status `AMBIGUOUS`.
- Closed result fields: schema/version, phase, run UUID, generated DB/media identities, manifest digest, ledger identity/generation/digest, exact counts for pages/routes/current/previous/staff/grants/assets/files/usages/albums/photos and `site_settings=1`, DB projection digest, source-media digest, target-media digest and nullable fixed error code. CREATED requires known pre-target counts/digests and null target digests; FAILED follows its closed phase matrix; SEALED requires all counts/digests non-null and equal to readback.
- `SafeResult` and `ReadbackProof` are extended to this exact field/parity matrix before adapter code. Coordinator `record_sealed`, `seal_status` and later Q003 read the same terminal authority. Q003 selects only exact `CREATED+SEALED`, with `FAILED` absent and unknown files0.
- Any rollback/source/target identity/seal ambiguity isolates. Cleanup receives no arbitrary path/name and runs only after the complete `CleanupProof`; unknown/foreign/current pair is untouched.

## 6. Tests before runtime

- manifest generation exact page/route/current/previous/generation/provenance/media/gallery/settings counts and digests;
- schema/model/migration parity and adapter INSERT column parity;
- source executor proves same PID/XID/snapshot for public and private, including empty rows;
- literal role/privilege SQL positive and every single privilege/membership/owner/settings negative;
- target migration alias points only to generated DB and exact migration leafs;
- failure injection at source/public build, identity creation, migration, public/private insert, each file, commit/readback/seal/cleanup;
- cap+1, count drift, source/media drift, collision, symlink/reparse/path escape, lost response and cleanup ambiguity;
- canonical UTC timestamp rejects naive/offset/noncanonical values; SiteSettings0/2, extension/MIME/magic mismatch and untrusted SVG fail pre-target/readback parity;
- output scan: passwords, usernames, numeric source keys, request values, secrets, absolute paths and file bytes0;
- independent stable-hash whole-slice review before any execution.

## 7. Acceptance

- `RB3-ADAPTER-AC-001`: no Protocol remains without exactly one project concrete implementation and one composition call path.
- `RB3-ADAPTER-AC-002`: each Page row carries exact positive `content_generation` outside payload envelope/SHA; manifest digest is recalculated and builder/target agree byte-for-byte.
- `RB3-ADAPTER-AC-003`: public builder and private reader use one captured source RRRO; public/private leakage0.
- `RB3-ADAPTER-AC-004`: literal target migrations/import rows match current models and six-model scope; requests rows0.
- `RB3-ADAPTER-AC-005`: exact least-privilege lifecycle closes source/target roles/connections/secrets on every observable path; ambiguity isolates.
- `RB3-ADAPTER-AC-006`: all files are contained regular non-links, copied exclusively and re-hashed; no dedup/overwrite/fallback.
- `RB3-ADAPTER-AC-007`: commit requires full DB+file verification; SEALED requires matching committed readback and exact ledger evidence.
- `RB3-ADAPTER-AC-008`: cleanup can affect only exact generated pair after complete proof; old/current/other run unchanged.
- `RB3-ADAPTER-AC-009`: no plugin/configurable ETL, repository/UoW, job/queue, retry/resume, persistent map or second manifest.
- `RB3-ADAPTER-AC-010`: Python/Django/Docker/DB/filesystem execution remains0 until separate reviewed runtime gate.

## 8. Порядок remediation

1. Add manifest `content_generation`, expanded closed SafeResult/ReadbackProof and focused schema/parity tests; independent repeat review.
2. Implement concrete source/public builder and synthetic static tests.
3. Implement literal target adapter/entrypoint and fault fakes.
4. Whole-slice independent review RB3-IMP-005; only then ask for isolated synthetic runtime gate.

Before that synthetic gate, owner must separately authorize rebuilding the foundation runtime image from the updated exact lock and verifying lock/receipt/import identity. Current receipt remains old; host-install fallback is forbidden.
