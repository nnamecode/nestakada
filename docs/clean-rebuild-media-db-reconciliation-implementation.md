# REBUILD-1 media DB reconciliation implementation candidate

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-DB-RECON-IMPLEMENTATION-001`.

Approved D-1344 scope реализован в существующих SQL/runner без нового процесса или файла данных.

Изменения:

- SQL добавляет internal CTE `duplicate_matched_pair/file` и `unmatched_db_pair/file`;
- facts34→56: recon22 unique, по11 на section;
- usage counts используют `EXISTS` по distinct asset membership и не умножаются duplicate file rows;
- runner проверяет pair/file/distinct/state/legacy/kind cardinality и category sums fail-closed;
- output добавляет exact `duplicateMatched` и `unmatchedDb`, по11 integers;
- schema version повышена v3→`rb1-media-db-bind-v4`; v3 historical evidence не переопределяется.

Static evidence: PowerShell parser0; SQL facts56/unique56; recon22/dup11/unmatched11; expectedFactCount56; output sections11+11; diff-check PASS.

SQL input, exact301, grants8, TLS/RRRO/timeouts, existing binding/anomaly/structure groups, cleanup/retry/old DBPRE unchanged. Path/hash/bytes/ID/slot/source/provenance/row/raw error output0.

Следующий gate: independent pre-execution review. Runtime/DB/Docker0; run requires fresh owner gate.
