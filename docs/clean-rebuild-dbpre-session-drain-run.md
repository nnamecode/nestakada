# DBPRE run after approved session drain

Дата: 2026-11-17. Evidence ID: `RB1-CLEANUP-RUN-003`.

Владелец отдельно разрешил один changed DBPRE после `RB1-CLEANUP-DRAIN-REVIEW-001` APPROVED. Единственный запуск завершился:

`{"contract":"rb1-dbpre-v1","status":"FAIL","code":"DBPRE_FAILED_CLEANUP_ROLE"}`

Session-drain inference runtime не подтвердилась. Facts/PASS не принимаются. Повтор не выполнялся.

Обязательный postcondition cleanup поднял только dev PostgreSQL, exact-проверил остаточную NOLOGIN-роль (flags, one exact settings row, memberships/ownerships/sessions0), literal-revoked allowlist/schema/database и удалил роль. Результат: `ROLE_CLEANUP=PASS`, project containers0, host secret0.

Задача приостановлена владельцу. Следующий возможный лёгкий путь — не новый logger/retry subsystem и не очередная гипотеза, а заранее рассмотренная bounded constant diagnostics для существующих cleanup proof stages. Новый DBPRE, Q002, product/runtime/live закрыты.
