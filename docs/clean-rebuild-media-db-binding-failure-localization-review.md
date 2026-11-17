# REBUILD-1 media DB binding failure localization review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-DB-BIND-FAILURE-LOCALIZATION-REVIEW-001`.

Вердикт: **APPROVED — P1=0, P2=0, P3=0**.

`RB1-MDB-LOC-AC-001..005` подтверждены. Добавлены только четыре allowlisted constant media codes в порядке SQL→ENVELOPE→CONTRACT→OUTPUT. Raw SQL/facts/path/exception/payload не раскрываются; cleanup-first и cleanup-failure dominance сохранены; success очищает code; old `RB1-READ-Q001` остаётся на generic `DBPRE_FAILED_READ`.

No-bloat PASS: retries/logger/process/query/grants/output schema не добавлены. Reviewer tools/edits/runtime/DB/Docker/network0.

Следующий gate: отдельное owner continuation на один changed media-binding probe. Approval не разрешает автоматический retry, exporter/importer/Q002/product/live.
