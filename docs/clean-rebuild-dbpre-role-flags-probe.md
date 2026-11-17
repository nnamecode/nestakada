# DBPRE role-flags same-transaction probe

Дата: 2026-11-17. Evidence ID: `RB1-ROLE-FLAGS-PROBE-001`.

Owner разрешил один изолированный catalog-only probe без subject-table read:

`CREATE ROLE ... LOGIN` → `ALTER ROLE ... NOLOGIN` → exact same seven safe flags + `connlimit=1` predicate в той же transaction → `DROP ROLE` → `COMMIT`.

Результат: `ROLE_FLAGS_SAME_TX=PASS`, `PROBE_ROLE_COUNT=0`, compose teardown PASS. Пользовательские таблицы не читались; DBPRE/facts/product0.

Вывод: ALTER visibility и сам flags predicate корректны. В runner marker ROLE_FLAGS расположен вне следующего большого PL/pgSQL `DO`, а следующие markers — внутри него. Поэтому failure до первого inner marker может означать compile/entry failure всего DO, а не false flags predicate. Дальнейшее дробление flags запрещено как bloat.

Следующий минимальный proposal: один catalog-only exact-structure probe полного cleanup DO на собственной роли с transaction rollback/drop/teardown, без reader aggregate и без вывода private data. Цель — проверить SQL compilation/entry. Требует отдельного owner gate.
