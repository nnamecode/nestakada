# Повторное независимое review чистой пересборки

Дата: 2026-11-16. Задача: `CRAR-REPEAT-001`. Проверены remediation D-1225–D-1237 относительно исходного `docs/clean-rebuild-architecture-review.md`, действующих требований и read-only фактов проекта. Reviewer не редактировал файлы и не запускал product/runtime/DB/Docker/network.

Вердикт: **CHANGES_REQUESTED — P1=3, P2=3, P3=1**.

`REBUILD-Q001/Q002`, product code, dependencies, migrations, DB/media mutation и cutover остаются закрыты. Восемь исходных P2, оба исходных P3 и два из пяти исходных P1 закрыты либо существенно конкретизированы; оставшиеся blockers и новые gaps требуют ещё одного bounded remediation+repeat review.

## 1. Исходные 15 findings

| Finding | Статус | Доказательство |
|---|---|---|
| `CRAR-P1-001` content/outcome contract | **OPEN** | Матрица содержит 117 memberships при 115 unique MAP: `MAP-031` и `MAP-053` входят и в `service_detail`, и в `article` (`clean-rebuild-content-contract.md`, строки 63/65), тогда как CSV относит оба только к `article`. Transport alias объявлен не Page.Kind, но находится среди 20 content types без independent payload. Большинство групп не имеет явных O/E permissions, numeric bounds и literal sanitizer allowlist. |
| `CRAR-P1-002` DAG/transactions | **OPEN** | Exact DAG/FK/основные transaction owners заданы, но `User.generation` обещан для grant-sensitive изменений, а create/change/revoke PageGrant и atomic accounts generation participant отсутствуют в operation table. |
| `CRAR-P1-003` current+previous | **CLOSED** | Generation/hash CAS, employee allowed patch, owner Undo, provenance, bounded lost-response и atomic usages/audit определены в architecture §7.3. |
| `CRAR-P1-004` coherent transfer | **OPEN** | Private stream требует «той же frozen source snapshot» после завершения исходной snapshot transaction (`clean-rebuild-transfer-contract.md` §6). DB import, media publication и private stream не имеют disposable run-target/failure boundary: partial target становится non-empty, а retry запрещён, поэтому `TRANSFER-AC-007` atomic claim не доказан. |
| `CRAR-P1-005` requests/legal | **CLOSED** | D-1229, default-off LEGAL gate, fields/consent/access/delete/retention/Telegram и REQUEST-AC определены. |
| `CRAR-P2-001` User model | **CLOSED** | Minimal custom User выбран до first migration; staff/customer separation определена. |
| `CRAR-P2-002` media decoder | **CLOSED** | Formats/bytes/pixels/EXIF/animation, isolated worker limits и STAGED→READY cleanup определены. |
| `CRAR-P2-003` Telegram/ledger | **CLOSED** | At-most-once CAS, transport limits, durable independent ledger и restore reconciliation определены. |
| `CRAR-P2-004` quality attributes | **CLOSED** | Измеримая latency/load/concurrency/limits/RPO/RTO/rollback matrix добавлена. |
| `CRAR-P2-005` new backup proof | **CLOSED с новыми P2 ниже** | Release/schema/migration/config-name manifest, ledger, isolated restore и HTTP smoke заданы; failure recovery требует уточнения. |
| `CRAR-P2-006` Page lifecycle | **CLOSED** | Семь owner commands, structural CAS, navigation, leaf delete и `PGLC-001..012` определены. |
| `CRAR-P2-007` estimate | **CLOSED** | Preliminary/non-commitment и пятистрочная O/L/R WBS после baseline определены. |
| `CRAR-P2-008` optional kernel | **CLOSED** | Kernel отсутствует по умолчанию; consumer-owned contracts и `KERNEL-AC-001..005` определены. |
| `CRAR-P3-001` exact fitness DAG | **CLOSED** | Fitness check содержит exact module DAG. |
| `CRAR-P3-002` plan status | **CLOSED** | Заголовок/основание плана отражают D-1222/D-1223/D-1224. |

## 2. Новые findings

### CRAR-R2-P2-001. Backup failure может оставить writes закрытыми

Architecture §14.2 открывает writes только после успешной внешней copy, но failure path не возвращает ingress к прежней valid generation. Недоступность external storage может бессрочно закрыть editor/request writes.

Minimal remediation: explicit `finally` сохраняет прежний catalog, завершает/изолирует exact staging, повторно доказывает отсутствие активного backup writer и открывает прежние write paths; integrity ambiguity остаётся fail-closed. `BACKUP-AC-006` отдельно считает raw restored rows до обязательных ledger/session/generation reconciliations.

### CRAR-R2-P2-002. Нет lifecycle минимального AuditEvent

Audit вызывается всеми mutations и используется для create/delete lost-response, но не заданы closed fields/event codes/detail caps, private access, retention/cleanup и backup policy.

Minimal remediation: один маленький action/security audit contract и AC; без общей logging/analytics/alerting platform.

### CRAR-R2-P2-003. Request throttle не связан с trusted client-IP boundary

Requests contract требует `1 request/s per source IP`, но не определяет, какой ingress устанавливает client IP и каким proxy headers доверяет Django. Возможны spoof/bypass либо один общий source для всех клиентов.

Minimal remediation: ingress удаляет входные forwarded headers и выставляет canonical client IP; Django доверяет только своему proxy/socket source. Добавить spoof и two-client AC без нового rate-limit service.

### CRAR-R2-P3-001. Две stale формулировки плана

`clean-rebuild-plan.md` всё ещё говорит «до CRAR-P1-005/legal решения», хотя D-1229 принят, и использует старое `base→optional` вместо exact DAG. Нужна только терминологическая синхронизация.

## 3. Минимальные P1 remediation

1. Убрать `MAP-031/053` из `service_detail`; validator доказывает ровно одно membership каждого MAP и equality CSV type. Развести transport alias и actual Page/content kind; для каждой editor group зафиксировать O/E, numeric caps и literal sanitizer policy.
2. Добавить pages-owned PageGrant create/change/revoke command с accounts generation participant, lock order, audit и concurrency AC либо убрать обещание grant-sensitive generation. Рекомендован первый вариант, потому что revoke обязан закрывать прежнюю session.
3. Freeze source держится до завершения public+private read либо создаётся один доказанно неизменный source snapshot. Каждый migration attempt использует новый disposable empty target DB/media; promotion только после public+private+ledger validation, failure изолирует/удаляет exact run target после containment proof. Универсальная migration state machine не создаётся.

## 4. Механические факты и review process

- CSV: rows115, unique MAP115, unique requested paths115, proposed types20.
- Document matrix: memberships117, unique MAP115; duplicates `MAP-031`, `MAP-053`; `service_detail`57 против CSV55.
- Referenced route map, design template и два old backup scripts существуют.
- Product/runtime/DB/Docker/network не запускались; reviewer files unchanged.
- `git diff --check` PASS с существующими CRLF warnings.
- Первая mechanical command ошиблась из-за PowerShell parsing `-join` как параметра `Sort-Object`; один изменённый повтор вынес join в отдельное выражение и успешно подтвердил counts. Эквивалентного второго сбоя/цикла не было.

## 5. Следующий обязательный порядок

1. P1 content matrix/permissions/bounds/sanitizer.
2. P1 PageGrant+session-generation transaction lifecycle.
3. P1 coherent disposable transfer run.
4. Три bounded P2 и одна P3 terminology correction.
5. Ещё одно независимое repeat review; только его verdict определяет дальнейший gate.

Ни один finding не требует event bus, repository/UoW, workflow engine, migration platform, backup service, logging platform или rate-limit service.
