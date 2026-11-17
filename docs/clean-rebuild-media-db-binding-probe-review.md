# REBUILD-1 media DB binding probe pre-execution review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-DB-BIND-PROBE-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P1=2, P2=1, P3=0**. Probe не исполнялся; owner-gated run не израсходован.

## Findings

- `RB1-MDB-EXEC-P1-001`: authority TOCTOU — CSV hash и `Import-Csv` используют два отдельных filesystem read. Нужно один раз прочитать bounded bytes, хэшировать именно их, строго декодировать и разобрать тем же buffer через `ConvertFrom-Csv`.
- `RB1-MDB-EXEC-P1-002`: prefix `LIKE` не доказывает safe storage key и пропускает `.`/`..`/invalid segments; `legacy-public ↔ is_legacy` проверяется односторонне. Нужен PostgreSQL regex, эквивалентный closed path validator, двусторонняя legacy consistency и source SHA equality.
- `RB1-MDB-EXEC-P2-001`: RRRO snapshot не повторяет structural guards current/page/shared authority. Нужны bounded zero facts для current page/kind/sequence, newer initial|automatic, page without state и cross-block shared current.

## Подтверждённые границы

Old DBPRE profile/contract/14-table allowlist preserved; new gate case-sensitive, exact8 grants and matching create/cleanup/fallback; parser0; facts30 unique; exact301 unique pairs and gallery214; one TLS RRRO connection/timeouts/cap; failure facts suppressed; cleanup-first/retry0. No-bloat PASS: второй lifecycle, dependency, service, exporter, manifest и temp table не появились.

Reviewer edits/runtime/DB/Docker/network/hash0. Следующий gate: только bounded remediation трёх findings, static checks и independent repeat pre-execution review. Фактический probe, Q002/product/live остаются закрыты.
