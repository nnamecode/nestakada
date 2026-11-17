# DBPRE cleanup reader-session drain

Дата: 2026-11-17. Contract ID: `RB1-CLEANUP-DRAIN-001`.

## Основание

Два полных запуска завершились `DBPRE_FAILED_CLEANUP_ROLE`, при этом последующий exact manual cleanup проходил. Catalog-only probe без reader-сессии подтвердил все девять групп cleanup predicates и `DROP ROLE`. Exact role state/settings/privileges не меняются между read и cleanup; единственное зависящее от момента условие — исчезновение завершившейся reader-сессии из `pg_stat_activity`. Это обоснованная root-cause inference, а не принятый runtime PASS.

## Минимальная правка

В существующем cleanup SQL заменить мгновенный session assertion на bounded drain: максимум 20 итераций по 50 ms, с `pg_stat_clear_snapshot()` перед повторным чтением. После окна прежний fail-closed session assertion остаётся. Новых PowerShell-функций, процессов, логов, зависимостей или общего retry-механизма нет.

## Приёмочные сценарии

- `RB1-CD-AC01`: drain выполняется только после exact OID/name/state proof и `ALTER ROLE ... NOLOGIN`.
- `RB1-CD-AC02`: максимум 20 ожиданий по 50 ms; суммарное дополнительное окно не больше 1 секунды.
- `RB1-CD-AC03`: каждая итерация очищает cached statistics snapshot перед проверкой exact role name.
- `RB1-CD-AC04`: исчезнувшая сессия немедленно завершает drain; пустой список не создаёт обязательной задержки.
- `RB1-CD-AC05`: оставшаяся после bounded окна сессия по-прежнему вызывает `sessions` exception и `DBPRE_FAILED_CLEANUP_ROLE`.
- `RB1-CD-AC06`: role state/settings/privilege proofs, revoke/drop, остальные cleanup stages и first-failure codes не меняются.
- `RB1-CD-AC07`: remediation/review не запускают Docker, DB или полный DBPRE; runtime требует нового owner gate.

Архитектурная граница: если bounded drain не закрывает runtime failure, третьего автоматического изменения или запуска нет; требуется новый evidence-based путь.
