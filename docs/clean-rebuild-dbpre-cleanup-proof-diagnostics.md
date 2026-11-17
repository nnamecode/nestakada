# DBPRE bounded cleanup-proof diagnostics

Дата: 2026-11-17. Contract ID: `RB1-CLEANUP-PROOF-DIAG-001`.

## Область

Только пять фиксированных диагностических групп внутри существующего role cleanup: `IDENTITY_STATE`, `SESSIONS`, `RELATIONS`, `PRIVILEGES`, `REVOKE_DROP`. Семантика proof, транзакции, revoke/drop и fallback не меняется. Raw PostgreSQL output, exception, path и stack наружу не передаются.

## Приёмочные сценарии

- `RB1-CPD-AC01`: checkpoint выбирается только из literal allowlist5; SQL/output не может сформировать произвольный внешний код.
- `RB1-CPD-AC02`: при native psql failure последний достигнутый checkpoint отображается в один соответствующий bounded JSON code.
- `RB1-CPD-AC03`: отсутствие/неизвестный checkpoint сохраняет общий `DBPRE_FAILED_CLEANUP_ROLE`.
- `RB1-CPD-AC04`: checkpoints стоят перед exact identity/state, bounded session drain, allowlist/relations, global privileges и literal revoke/drop соответственно.
- `RB1-CPD-AC05`: успешный cleanup, role fallback, остальные cleanup stages и first-failure-wins не меняются.
- `RB1-CPD-AC06`: stdout facts/PASS подавлены при любом cleanup failure; stderr содержит только один existing bounded JSON contract.
- `RB1-CPD-AC07`: нет logger, file diagnostics, retry, дополнительного Docker/psql процесса, функции или зависимости.
- `RB1-CPD-AC08`: remediation/review runtime0; новый DBPRE требует отдельного owner gate.

Следующий этап — независимое read-only review. Если диагностика не получает APPROVED, runtime остаётся закрыт.
