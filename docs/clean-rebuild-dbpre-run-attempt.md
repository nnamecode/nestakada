# RB1-READ-Q001 run attempt

Дата: 2026-11-17. Result ID: `RB1-READ-RUN-001`.

Статус: **FAIL-CLOSED; ПРИОСТАНОВЛЕНО ВЛАДЕЛЬЦУ**.

## Попытки

1. Обычный запуск завершился exit1 с единственным `DBPRE_FAILED` за ~1s. Read-only диагностика доказала причину: sandbox denied Docker named pipe. Temporary host secret отсутствовал.
2. Единственный изменённый повтор с разрешённым локальным Docker снова завершился exit1 с тем же bounded constant JSON. Внутренняя стадия намеренно не раскрывается текущим failure channel.

Третья попытка запрещена anti-loop rule.

## Postcondition

- host secret `work/foundation/dev/private/rebuild-reader-password`: отсутствует;
- read-only Docker cleanup check вернул неполный вывод после `PROJECT_ALL:`; stopped/container state независимо не доказан;
- SQL не запускался отдельно, поэтому отсутствие/NOLOGIN temporary role независимо не доказано;
- aggregate facts не получены и PASS не заявляется.

## Следующий безопасный вариант

После решения владельца: одна materially different read-only postcondition check с жёстким timeout, затем статическая локализация стадии отказа через небольшой фиксированный stage code. Не запускать DBPRE повторно, не добавлять logs/framework/service и не выводить Docker/SQL errors, paths, secrets или rows.
