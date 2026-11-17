# DBPRE cleanup-DO exact-structure probe

Дата: 2026-11-17. Evidence ID: `RB1-CLEANUP-DO-PROBE-001`.

Owner разрешил один изолированный catalog-only probe полного cleanup DO на собственной временной роли. SQL большого DO извлечён из `tools/rebuild-dbpre.ps1`; subject-table rows, reader aggregate, DBPRE и продуктовый код не запускались.

Критерии: временная роль отсутствует до запуска; exact cleanup-DO structure исполняется через bootstrap connection; после любого исхода роль отсутствует и compose остановлен; наружу выводятся только ограниченные диагностические строки.

Калибровка harness: sandbox-вызов остановился до compose из-за запрета Docker API. Разрешённый изменённый вызов выявил сохранённое PowerShell-экранирование `` `$ `` до SQL. Единственный изменённый повтор удалил только это экранирование и исполнил исходный DO.

Результат исходного SQL: notices `IDENTITY` и `ROLE_FLAGS`, затем PostgreSQL вернул `mismatched parentheses` на строке 27 DO. Статическая привязка: `tools/rebuild-dbpre.ps1:516` закрывает `NOT EXISTS` раньше времени, после чего строка 517 содержит лишнюю `)`. Это compile/entry defect большого DO и объясняет внешний код `DBPRE_FAILED_CLEANUP_ROLE_ROLE_FLAGS`: следующие markers находятся внутри некомпилируемого блока.

Постусловия: `PROBE_ROLE_COUNT=0`, `COMPOSE_DOWN_EXIT=0`. Данных сайта не читали; DBPRE/facts/product/live0.

Следующий минимальный этап: удалить одну лишнюю скобку, выполнить parser/static checks и независимое review. Новый диагностический механизм не нужен.
