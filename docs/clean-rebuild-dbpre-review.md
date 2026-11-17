# D-1253 independent source-DB preflight review

Дата: 2026-11-16. Review ID: `RB1-DBPRE-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P1=1, P2=1, P3=0**.

Review выполнен независимо и read-only. Workspace, DB, Docker/runtime, network и product files не изменялись. Создание `estakada_rebuild_reader` и actual DB read не разрешены; после remediation и repeat review всё равно нужен отдельный owner gate.

## Подтверждено

- `app_runtime` имеет DML и непригоден как source reader; `app_migrator` владеет schema/migrations и также непригоден.
- Literal allowlist содержит 14/14 уникальных необходимых таблиц; расширение для findings не требуется.
- Requests/audit/session/throttle/drafts/stages/receipts/reservations корректно исключены.
- TLS + explicit repeatable-read/read-only transaction, fixed SELECT, timeouts, result≤64KiB, constant failure и no stronger-role fallback — подходящая bounded граница.
- Numeric source user key→fresh target UUID через process-memory-only map совместим с target User/PageGrant/provenance и не создаёт subsystem.

## Findings

### `RB1-REV-P1-001` — reader membership/ownership/lifecycle не закрыты

`NOINHERIT` не запрещает `SET ROLE` при membership. Contract не требует fresh-only creation, zero memberships в обе стороны, zero DB/schema/table/sequence ownership, exact effective privileges, bounded `VALID UNTIL` и обязательный cleanup.

Минимальная remediation: existing role fail-closed; zero membership/ownership; exact effective privileges только CONNECT/USAGE/14 SELECT; bounded validity; one `finally` close→NOLOGIN/revoke→drop→exact secret cleanup, ambiguity оставляет NOLOGIN для owner inspection. Role-management platform не нужна.

### `RB1-REV-P2-001` — не доказана mappability авторов current/previous

Source `PageRevision.author_id` — numeric без FK. DBPRE проверяет staff/grants и current/predecessor отдельно, но не требует zero unmapped authors именно выбранных current+immediate-previous revisions.

Минимальная remediation в существующем fixed aggregate set: zero counts для null/nonpositive/unmapped selected authors; staff без ровно одного valid UserProfile/role; PageGrant с unmapped user/page. Используются те же 14 tables, IDs/private values не выводятся.

## Mechanical/no-bloat

- allowlist14/unique14; `TRANSFER-AC-001..014` definitions14/unique14;
- product/runtime/DB/Docker/network untouched; reviewer edits0; tool errors/cycle0;
- оба исправления — fail-closed checks/cleanup в одном bounded runner, без identity service, mapping table, role manager, migration platform или retry framework.

Следующий ordered этап: remediation только `RB1-REV-P1-001`, затем отдельно P2 и repeat narrow review. Role mutation/DB read/private transfer/target/media/product code закрыты.
