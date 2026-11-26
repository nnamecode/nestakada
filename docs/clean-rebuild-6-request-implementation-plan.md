# CORE-18 / RB6-REQUEST-001 — implementation plan минимальной default-off заявки

Дата: 2026-11-25. Статус: `CORE-18 / RB6-REQUEST-001 CLOSED`, final evidence/release-gate review `APPROVED P0=0/P1=0/P2=0`. Source и remediations approved; bounded PostgreSQL/Linux confirmation: system/migration checks PASS, `148/148 OK`, generation diagnostics `13/13 OK`. Актуальный default-off exact115: `routes=115`, `requests=230`, form/submit disabled, request/projection rows0, audit mutation0, external network0. Exact cleanup: owned containers0, networks/volumes/staging created0, foundation DB bitmap exact. `RB6-REQ-AC-001..009` и `AC-010A` закрыты. Activation-only `AC-010B/AC-011`, LEGAL-01, real consent/privacy bytes, intake enable, production Nginx/socket/rate buckets, Telegram secret/network, external B002 ledger, scheduler, active-row transfer, VPS/deploy/cutover/live не входят и не блокируют CORE-18.

Authority: `docs/clean-rebuild-requests-contract.md` (D-1229). Этот plan не включает LEGAL-01, не утверждает production consent/privacy text, не включает реальный intake, не создаёт реальные заявки и не разрешает Telegram/network, Docker, production, VPS, deploy или чтение пользовательских данных.

## 1. Цель и closed scope

Добавить в новый `src/` один маленький Django app `modules.service_requests` с app label `service_requests` и таблицей `app.service_requests_servicerequest`, совместимой с уже закреплённой importer/source boundary. Публичный intake остаётся fail-closed `SERVICE_REQUESTS_ENABLED=False`; при false URL submission отсутствует, controls не рендерятся, DB/audit/network mutation невозможна.

В source scope входят только:

1. exact schema и validation минимальной заявки;
2. enabled-profile intake command с UUID replay/conflict и safe audit;
3. HOME form projection и exact POST endpoint, физически отсутствующие при default-off;
4. Telegram-only at-most-once adapter после commit;
5. owner+active staff read-only list/detail и owner-only exact delete;
6. canonical deletion-ledger interface, projection, retention и reconciliation/restore guard;
7. trusted ingress validation и closed tests;
8. migrations, templates и focused tests.

Не входят: email, status/assignee/notes/history, attachments, search/export, resend, retry/outbox/worker/scheduler, CAPTCHA, CRM, API, arbitrary JSON, IP persistence, generic notification/ledger/proxy framework, consent/legal wording, activation, real secrets/network/data.

## 2. Stable model boundary

`ServiceRequest` содержит только:

- client-provided UUID primary key `id`;
- server `created_at`;
- `name` max100;
- canonical `phone` exact `+7` plus ten digits;
- optional `vehicle_make`/`vehicle_model` max100, `vehicle_year` blank or exact four ASCII digits, canonical combined vehicle text max300;
- optional `comment` max4000;
- `consent_text_version` max64, lowercase SHA-256 `consent_text_sha256`, server `consented_at`;
- `telegram_outcome` exact `NOT_ATTEMPTED|IN_PROGRESS|SENT|FAILED` and nullable `telegram_attempted_at`.

No stored fingerprint field: replay fingerprint is recomputed canonically from the closed row fields and compared with the canonical submitted projection. No `updated_at`, source, IP, headers, session, response body or transport error is stored.

`ServiceRequestDeletionProjection` is separate rebuildable operational state with exactly two authority fields: unique monotonic `sequence` and unique request UUID. Deleted time, reason, previous hash and row hash remain only in the external canonical ledger. The projection contains no request content and cannot independently authorize deletion.

Migration dependencies are explicit: service request initial migration has no audit FK; runtime audit remains a transaction participant through the existing public API. No existing model/migration is edited.

The implementation must amend every closed schema/DAG authority that the new app changes, rather than silently widening it:

- add `modules.service_requests.apps.ServiceRequestsConfig` to `INSTALLED_APPS` and the exact module-DAG allowlist/edge fitness tests;
- add literal project label `service_requests` and its migration leaf to generation-v5 migration/schema/table diagnostics;
- add exact target migration leaf to `rebuild3_importer.runtime_target.TARGET_MIGRATION_LEAVES` and its tests;
- include both request tables in migration/schema existence diagnostics, but do **not** add either table to `rebuild3_importer.runtime_target.TARGET_TABLES`, because that set grants importer `SELECT, INSERT`;
- add explicit tests that the importer target role receives no `SELECT`, `INSERT`, `UPDATE` or `DELETE` on either request table; any future active-row/projection transfer authority requires a separate owner-approved package;
- update zero-row importer/generation compatibility so request row count remains exact zero in current default-off sources;
- preserve the existing source-reader boundary: only the already approved `ServiceRequest.id` zero-row/count check is available; projection rows and active request content are not exported.

Transfer of any future active rows/ledger remains a separate owner gate under `clean-rebuild-transfer-contract.md` and is not implemented or inferred by this package.

## 3. Configuration and default-off topology

Base settings define exact `SERVICE_REQUESTS_ENABLED=False` unless the environment contains literal `true`. Unknown values fail closed. Enabled synthetic projection additionally requires exact form version, consent version, bounded synthetic consent/privacy UTF-8 text bytes, their lowercase SHA-256, Telegram secret-file paths/chat ID, primary deletion-ledger root and independently verified backup adapter configuration. Startup/profile validation proves `sha256(exact_text_bytes)==configured_hash`; the rendered checkbox/notice uses those exact bytes. Missing/invalid configuration makes intake unavailable and must not partially expose form or POST. Production consent bytes/version/hash do not exist in source defaults and may be supplied only by the later LEGAL-01 activation package after owner approval; no placeholder or general settings store is added.

`config.urls` inserts exact `/request/submit/` before the public catch-all only when settings are enabled and configuration validation succeeds. With default settings the pattern is absent, not a 503 feature stub. `public_page_view` supplies no form context when disabled; HOME template contains no enabled controls or endpoint token in rendered HTML.

Existing preview/cutover Nginx exact 404 rules remain unchanged. A future production-enable package must separately add the exact throttled location and protected Unix-socket header rewrite after LEGAL-01; source implementation does not weaken current 404 boundaries.

## 4. Intake command and replay

Exact URL-encoded form fields are: `form_version`, `submission_id`, `name`, `phone`, `vehicle_make`, `vehicle_model`, `vehicle_year`, `comment`, `consent_text_version`, `consent`. CSRF is mandatory. Body must be 1..8192 bytes before parsing; duplicate/extra/missing fields fail.

Normalization is deterministic and bounded:

- Unicode/control policy is explicit, no HTML acceptance; surrounding whitespace is stripped only where specified by tests;
- phone accepts the approved Russian display punctuation only and canonicalizes to exact `+7XXXXXXXXXX`; other country/prefix/count forms fail;
- consent must be one exact affirmative token; server injects the configured consent SHA and server timestamp;
- canonical replay fingerprint is SHA-256 over a fixed UTF-8/LF field envelope, computed in memory only.

One outer requests-owned `transaction.atomic()` first attempts the UUID insert inside one nested savepoint. The PostgreSQL unique primary-key conflict is caught outside that savepoint; the caller then performs a locked read of the now-committed exact UUID and compares the canonical fingerprint. The inserting transaction creates one safe anonymous `SERVICE_REQUEST_ACCEPTED` AuditEvent and registers `transaction.on_commit()` only after successful insert; the conflict path registers no callback. Equal existing projection returns accepted replay; any difference returns constant conflict. No `SELECT FOR UPDATE` claim is made for an absent row.

Real PostgreSQL concurrency tests use two independent transactions for both equal and mismatched payloads. They require row1/audit1/on-commit claim≤1, exact accepted+accepted-replay results for equal payload and exact accepted+conflict results for mismatch, without leaking raw values.

## 5. Telegram-only at-most-once

A short transaction performs conditional `NOT_ATTEMPTED -> IN_PROGRESS`, sets safe attempted time and returns a content snapshot only to the winning caller. No network occurs inside a DB transaction. Terminal update is conditional `IN_PROGRESS -> SENT|FAILED`; failure to persist terminal result leaves `IN_PROGRESS`. `IN_PROGRESS`, `SENT` and `FAILED` are never claimed again.

Transport uses standard library HTTPS only. Token must match closed ASCII `[1-9][0-9]{5,19}:[A-Za-z0-9_-]{20,200}` and chat ID `-?[1-9][0-9]{0,19}` before URL construction. The request has exact origin `https://api.telegram.org`, exact path `/bot<TOKEN>/sendMessage`, query/userinfo0, status200, proxy disabled, redirects disabled, system trust with hostname verification, one total timeout5 and streaming read of at most4097 bytes rejecting cap+1. Response must be one JSON object with exact `ok=true`; extra fields are ignored, non-object/false/malformed/oversize fails. Secret token is read only from the configured secret file. Exceptions are never stringified or logged and are replaced by constant safe outcomes. Payload/response/token/chat ID/row fields are never logged or written to AuditEvent. No email branch exists.

## 6. Private read/delete/retention boundary

Active OWNER and EMPLOYEE receive private/no-store list/detail only. Pagination is fixed and bounded; no arbitrary personal-data search. Employee has no mutation/export. Owner delete requires CSRF plus a signed exact request UUID+created_at confirmation; no repeat password.

Deletion uses one requests-owned sequence and three exact states derived from primary ledger, independent verification receipt and DB projection:

- `PRIMARY_PENDING`: exact new local generation/digest exists but independent receipt for that generation is absent; no DB deletion authority, whole requests subsystem closed;
- `INDEPENDENT_VERIFIED`: independent adapter proves the exact same generation/digest; DB projection/delete transaction may run;
- `PROJECTED`: DB projection contains the generation's exact sequence/UUID set and matching live rows are absent.

The sequence is:

1. acquire exact primary-ledger lock, verify its full hash-chain and compare current primary/independent/projection generations before any append;
2. append canonical tombstone `(sequence, UUID, deleted_at, reason, previous_hash, row_hash)` with exclusive no-follow write, flush/fsync file and parent, producing exact `PRIMARY_PENDING` generation/digest;
3. synchronously publish and read-verify that exact generation/digest through one narrow independent-backup adapter; absence/ambiguity retains `PRIMARY_PENDING`, performs no DB mutation and closes list/detail/intake/delete/retention;
4. only `INDEPENDENT_VERIFIED` permits one DB transaction to lock the request, insert exact sequence+UUID projection, delete the row and write safe AuditEvent;
5. DB failure leaves `INDEPENDENT_VERIFIED` ledger authoritative and subsystem closed until reconciliation reaches `PROJECTED`.

Recovery/reconciliation never appends a duplicate tombstone. It may only resume the exact already present generation/digest: publish/read-verify `PRIMARY_PENDING`, or apply an already `INDEPENDENT_VERIFIED` generation to DB. Different generation/digest, partial receipt or unknown state is terminal ambiguity with no automatic discovery/delete.

The source package defines the adapter protocol, a deterministic synthetic independently verified adapter for tests and a fail-closed disabled production implementation. Real independent encrypted storage materialization belongs to the separate VPS/B002 contour. Therefore default-off code can be complete while actual deletion/retention/intake enable remains impossible before that contour supplies reviewed authority.

Retention command has no user arguments, captures one aware `now-30d`, selects only `created_at < cutoff` and uses a fixed batch cap. Under one ledger lock it publishes all batch tombstones into one new primary generation, verifies that exact full generation independently, then one DB transaction inserts all exact sequence+UUID projection rows, deletes only the selected requests and writes one aggregate `SERVICE_REQUEST_RETENTION_BATCH` audit. It never loops the single-owner deletion primitive and never writes per-row retention audit. It prints only a count or constant error. Scheduler is absent.

Live reconciliation after a post-ledger DB failure validates the exact latest primary+independent generation/digest and full chain, then may idempotently apply tombstones to DB/projection in bounded transactions while the shared requests-subsystem guard continuously refuses list, detail, intake, delete and retention. Partial live progress never opens a request surface.

Isolated restore reconciliation is stricter and separate: with all HTTP/writers stopped it validates the full latest independently verified chain, then in **one** DB transaction clears/rebuilds the complete sequence+UUID projection and deletes every matching `ServiceRequest`. Any projection/delete/late failure rolls back the entire transaction. Restore writes no AuditEvent by contract; audit rows must remain unchanged. Only after commit does a separate read prove tombstoned live rows0 and exact projection equality, after which request readiness may open. Missing/stale/corrupt/ambiguous ledger or any mismatch leaves all request HTTP closed. Existing R7 scripts are changed only through their exact generation/importer authority updates described above; no live restore is run in the source package.

## 7. Trusted ingress

`PrivateIngressMiddleware` receives one narrowly named public-intake branch. Only enabled exact POST `/request/submit/` is admitted. Before accessing `request.POST` it requires canonical `CONTENT_LENGTH` 1..8192; rejects `Forwarded`, `X-Forwarded-For`, `X-Real-IP`; requires exactly one canonical `X-Estakada-Client-IP` IPv4/IPv6 value without whitespace, comma, zone or port. IP is neither persisted nor logged.

Source acceptance proves only fail-closed header/body validation. Enabled endpoint tests use synthetic trusted ingress; default-off tests prove route/form/DB/audit/network absence. The activation gate separately proves exact Nginx strip/set behavior, Unix-socket-only app topology, public TCP listener0, spoof cases and two independent IPv4/IPv6 client rate buckets. Until that runtime evidence exists the route remains absent even if all source tests pass.

## 8. Tests-first implementation slices

### `RB6-REQ-IMP-001` — schema/default-off

Write model/migration/config fitness tests first. Prove exact fields, choices, constraints, app/table identity, default false, route absent, rendered HOME controls absent, audit/network0.

### `RB6-REQ-IMP-002` — validation/intake/replay

Write pure normalization/fingerprint and command tests first: all limits/cap+1, phone matrix, consent/version/hash, exact UUID replay, mismatch conflict, concurrency shape, transaction rollback and safe audit. Then add enabled synthetic HTTP tests for CSRF, exact form fields, body cap, ingress, constant responses and no PII in audit.

### `RB6-REQ-IMP-003` — Telegram claim/adapter

Write tests first for one claim under concurrency, terminal CAS, crash states, no re-claim, closed token/chat-ID formats, exact origin/path/status200/query0/userinfo0/TLS/proxy/redirect/timeout/streaming cap+1 and exception redaction. Network is replaced by a local fake opener; real network0.

### `RB6-REQ-IMP-004` — private read/delete ledger

Write role/list/detail/delete and pure ledger tests first: bounds, no-store, staff read-only, owner exact confirmation, hash-chain, exclusive/no-follow/fsync, `PRIMARY_PENDING→INDEPENDENT_VERIFIED→PROJECTED`, independent verification refusal, exact-generation recovery, DB-after-ledger ambiguity and safe audit.

### `RB6-REQ-IMP-005` — retention/reconciliation/readiness

Write exact cutoff/batch/replay and chain/projection reconciliation tests first. Batch proves all tombstones then one independent verify then one DB transaction and one aggregate audit. Live reconciliation proves bounded idempotent progress with every request surface closed. Restore reconciliation proves one-transaction full projection rebuild+delete, injected late projection/delete failures with complete rollback, audit rows unchanged, and post-commit rows0 before readiness. Missing/stale/corrupt/backup-unverified ledger closes list/detail/intake/delete/retention/readiness. Scheduler0, actual external backup0.

### `RB6-REQ-IMP-006` — integration/static closure

Full source/schema/DAG/privacy tests, exact generation-v5 project labels/table diagnostics, importer target migration leaves/privileges/zero-row compatibility, `makemigrations --check`, system check, default-off public regression exact115, grep/static secret/PII/log checks and independent final code review. Runtime/PostgreSQL/Docker requires a separate owner gate after source approval.

## 9. Acceptance matrix

- `RB6-REQ-AC-001` → `REQUEST-AC-001`: default-off pattern/form/row/audit/network all absent.
- `RB6-REQ-AC-002` → `REQUEST-AC-002`: invalid/oversize/stale/duplicate fields reject before mutation.
- `RB6-REQ-AC-003` → `REQUEST-AC-003`: one canonical row; equal replay same result; mismatch conflict.
- `RB6-REQ-AC-004` → `REQUEST-AC-004`: one Telegram claim/attempt maximum; outcome does not change acceptance.
- `RB6-REQ-AC-005` → `REQUEST-AC-005`: no PII/secret/payload/response in logs, audit or safe errors.
- `RB6-REQ-AC-006` → `REQUEST-AC-006`: anonymous read0, staff read-only, owner exact delete only.
- `RB6-REQ-AC-007` → `REQUEST-AC-007`: primary+independent durable tombstone precedes DB delete; ambiguity closes.
- `RB6-REQ-AC-008` → `REQUEST-AC-008`: latest verified chain/projection and tombstoned rows0 precede readiness.
- `RB6-REQ-AC-009` → `REQUEST-AC-009`: forbidden product/platform surface absent.
- `RB6-REQ-AC-010A`: source proves spoof/missing/list/malformed internal header and invalid body length fail before parse/mutation.
- `RB6-REQ-AC-010B` → remaining `REQUEST-AC-010`: activation evidence separately proves Nginx strip/set, protected Unix socket and public app TCP listener0; route remains absent beforehand.
- `RB6-REQ-AC-011` → `REQUEST-AC-011`: two-client Nginx rate-bucket evidence is deferred to activation; source tests do not claim it and route remains absent.

## 10. Gates and completion

1. Independent architecture/security/privacy/data/destructive/no-bloat review of this plan; all findings close before code.
2. D-1229 plus owner `Продолжай` on the explicitly proposed CORE-18 stage authorize bounded tests-first source implementation IMP-001..006, not runtime or activation.
3. Independent source review after implementation and bounded remediation.
4. Separate owner permission is required for one bounded Linux-filesystem + PostgreSQL synthetic integration package. It must use a disposable ledger root and deterministic fake independently verified adapter; prove equal/mismatch concurrent intake, owner delete, batch retention, `PRIMARY_PENDING`, independent ambiguity, DB-after-ledger failure, bounded live reconciliation under closed surfaces, one-transaction restore reconciliation with injected late rollback, audit unchanged, stale/corrupt restore/readiness/list closure and exact cleanup. Real secret/network/data remain absent.
5. CORE-18 becomes CLOSED only after approved source and accepted bounded PostgreSQL/default-off HTTP plus Linux ledger integration evidence. It does not require or authorize LEGAL enable, Telegram live, real external ledger materialization or VPS.
6. Any real consent/legal material, Nginx enablement/topology/rate-bucket run, secret, Telegram network, production data or deployment requires later separate owner gates.

Same equivalent failure twice stops without a third attempt. No new dependency, framework, service, queue, scheduler, generic storage layer or public endpoint beyond the exact gated submission route may be introduced without plan amendment and repeat review.
