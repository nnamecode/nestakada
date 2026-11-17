# DBPRE cleanup substage codes

Дата: 2026-11-17. Contract ID: `RB1-CLEANUP-CODES-001`.

## Область

Только диагностическая детализация уже существующего fail-closed cleanup. Порядок действий и их семантика не меняются; новые логи, функции, зависимости и повторный DBPRE-запуск не добавляются.

## Приёмочные сценарии

- `RB1-CC-AC01`: ошибка точного удаления роли возвращает только `DBPRE_FAILED_CLEANUP_ROLE`.
- `RB1-CC-AC02`: ошибка удаления контейнерных файлов возвращает только `DBPRE_FAILED_CLEANUP_CONTAINER_FILES`.
- `RB1-CC-AC03`: ошибка удаления host secret возвращает только `DBPRE_FAILED_CLEANUP_HOST_SECRET`.
- `RB1-CC-AC04`: ошибка compose teardown возвращает только `DBPRE_FAILED_CLEANUP_COMPOSE`.
- `RB1-CC-AC05`: при нескольких ошибках сохраняется код первой по фактическому порядку cleanup; следующие best-effort действия всё равно выполняются.
- `RB1-CC-AC06`: stdout/facts/PASS при любой cleanup-ошибке не выдаются; stderr остаётся одним bounded JSON с allowlisted constant code.
- `RB1-CC-AC07`: успешный cleanup и коды основных стадий PRECHECK/START/ROLE/READ не меняются.

Следующий этап после статической проверки — независимое read-only review. Runtime/Docker/DB остаются закрыты до нового отдельного согласия владельца.
