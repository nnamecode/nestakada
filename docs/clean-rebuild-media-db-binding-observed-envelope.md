# REBUILD-1 media DB binding OBSERVED envelope amendment

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-DB-BIND-OBSERVED-ENVELOPE-001`.

## Контракт v3

`rb1-media-db-bind-v3` сохраняет hard fail-closed для:

- source counts238/238/736;
- usage unclassified0 и partition delta0;
- пяти binding arithmetic invariants;
- SQL/TLS/RRRO/envelope/output/cleanup mechanics.

После этих guards output содержит ровно 18 bounded integers:

- `binding`: six DB/candidate/gallery aggregates;
- `anomaly`: eight existing anomaly aggregates;
- `structure`: four existing structural aggregates.

Status=`PASS`, только если все anomaly8+structure4 равны0; иначе status=`OBSERVED`. `OBSERVED` означает безопасно зафиксированный drift для анализа, не acceptance, transfer/import permission или автоматическую remediation. Hash/path/ID/row/fact-name/SQL/raw error не выводятся.

Неиспользуемые constant codes CONTRACT_ANOMALY/CONTRACT_STRUCTURE удалены. SQL и internal facts не меняются; новый query/logger/exporter/manifest/framework отсутствует.

## Acceptance

- `RB1-MDB-OBS-AC-001`: output exact6+8+4 integers, private/per-row values0.
- `RB1-MDB-OBS-AC-002`: counts/usage/binding arithmetic remain hard failure before output.
- `RB1-MDB-OBS-AC-003`: PASS iff anomaly8+structure4 all0; otherwise OBSERVED.
- `RB1-MDB-OBS-AC-004`: OBSERVED не разрешает transfer/import/remediation.
- `RB1-MDB-OBS-AC-005`: SQL/grants/internal facts/cleanup/retry/old DBPRE unchanged.
- `RB1-MDB-OBS-AC-006`: unused diagnostic codes removed; no-bloat.
- `RB1-MDB-OBS-AC-007`: runtime/DB/Docker0; execution requires independent review and fresh owner gate.
