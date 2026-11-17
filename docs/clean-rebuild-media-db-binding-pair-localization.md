# REBUILD-1 media DB binding pair localization

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-DB-BIND-PAIR-LOCALIZATION-001`.

Шесть неизменных BINDING assertions разделены на три literal ordered pairs:

- `BINDING_DB`: DB matched238 / unmatched0;
- `BINDING_CANDIDATE`: candidate matched238 / only63;
- `BINDING_GALLERY`: gallery matched214 / missing0.

Остальные COUNTS/USAGE/ANOMALY/STRUCTURE assertions, expected values, SQL, output, grants и cleanup не меняются. Failure выдаёт только allowlisted constant category после cleanup; actual values/facts/raw error не публикуются.

Acceptance:

- `RB1-MDB-PLOC-AC-001`: binding pairs ровно3, assertions2+2+2=6 unique.
- `RB1-MDB-PLOC-AC-002`: order DB→CANDIDATE→GALLERY literal/deterministic.
- `RB1-MDB-PLOC-AC-003`: прежние 23 contract assertions остаются unique и полными.
- `RB1-MDB-PLOC-AC-004`: values/facts/raw error/SQL/path output0; query/grant/schema0.
- `RB1-MDB-PLOC-AC-005`: cleanup/old DBPRE/retry semantics unchanged; no-bloat.
- `RB1-MDB-PLOC-AC-006`: runtime/DB/Docker0; probe требует review и fresh owner gate.
