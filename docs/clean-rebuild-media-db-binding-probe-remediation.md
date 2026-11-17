# REBUILD-1 media DB binding probe remediation

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-DB-BIND-PROBE-REMEDIATION-001`.

- `RB1-MDB-EXEC-P1-001`: CLOSED candidate — authority читается одним bounded `ReadAllBytes`, digest вычисляется из тех же bytes, затем strict UTF-8 decode и `ConvertFrom-Csv`; второго filesystem read нет.
- `RB1-MDB-EXEC-P1-002`: CLOSED candidate — key проверяется closed segment regex и длиной; private-source↔private path и legacy-public↔is_legacy двусторонние; legacy source SHA равен file SHA.
- `RB1-MDB-EXEC-P2-001`: CLOSED candidate — добавлены four bounded zero facts: current page/kind/sequence, newer initial|automatic, page without state, cross-block shared current.

Static evidence: parser0; ReadAllBytes1/Import-Csv0/ConvertFrom-Csv1/strict UTF-8 one; SQL facts34/unique34/struct4/placeholder1/RRRO1/rollback1; safe samples3/3 and unsafe0/6 accepted; diff-check PASS.

Runtime/DB/Docker0. Existing gates/grants/lifecycle/output/cleanup unchanged. Следующий gate — independent repeat pre-execution review; execution допустимо только при APPROVED0/0/0.
