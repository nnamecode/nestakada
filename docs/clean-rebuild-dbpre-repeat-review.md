# D-1255/D-1256 DBPRE repeat review

Дата: 2026-11-16. Review ID: `RB1-DBPRE-REVIEW-002`.

Вердикт: **APPROVED — P1=0, P2=0, P3=0**.

Это approval только remediation-контрактов. Оно не разрешает создание/изменение `estakada_rebuild_reader`, actual DB read, private rows, media inventory, exporter/importer, target DB, WBS, product code или live/deploy.

## Findings

| Finding | Статус | Evidence |
|---|---|---|
| `RB1-REV-P1-001` reader membership/ownership/lifecycle | **CLOSED** | Fresh-only exact name+OID; DB-time+15m; membership both directions0; ownership0; exact CONNECT/USAGE/14 SELECT and negative privilege matrix; mandatory close→NOLOGIN→sessions0→literal revoke→conditional drop→secret deletion; ambiguity fail-closed without reuse/guess/drop. |
| `RB1-REV-P2-001` selected-author mappability | **CLOSED** | Exact current/immediate previous, staff_candidate/valid_staff, `DBPRE-MAP-001..005` zero counts for selected authors/staff/grant user/page; no IDs/rows/private values; same14 tables. |

Cross-contract PASS: current/previous selection совпадает с transfer rules; structural anomalies не маскируются; one memory-only fresh UUID map связывает grants/provenance; 15m validity запрещает новую authentication, не обрывает единственную уже открытую connection; excluded tables не потребовались.

## Mechanical/no-bloat

- `RB1-DBPRE-AC-001..008`: 8/8 unique;
- `DBPRE-MAP-001..005`: 5/5 unique;
- allowlist: 14/14 unique tables;
- `TRANSFER-AC-001..014`: 14/14 unique;
- `git diff --check` PASS, только существующие LF→CRLF warnings;
- reviewer edits0, DB/Docker/runtime/network0, tool errors/cycle0;
- no role manager, identity service, mapping/reconciliation table, migration platform, retry worker or new privilege area.

Следующий отдельный gate: owner permission на минимальную реализацию/исполнение exact temporary reader boundary. Создание роли и actual aggregate read не подразумеваются этим verdict и не должны сливаться с private/media/target/code stages.
