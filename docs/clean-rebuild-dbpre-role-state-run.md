# DBPRE role-state diagnostic run

Дата: 2026-11-17. Evidence ID: `RB1-CLEANUP-RUN-005`.

Один owner-authorized changed DBPRE после `RB1-IDENTITY-SUBCHECK-REVIEW-001` завершился:

`{"contract":"rb1-dbpre-v1","status":"FAIL","code":"DBPRE_FAILED_CLEANUP_ROLE_ROLE_STATE"}`

Facts/PASS не принимаются, повтор не выполнялся. Код доказывает: exact name/OID proof и `ALTER NOLOGIN` пройдены; SETTINGS и последующие группы не достигнуты.

Обязательный exact cleanup отдельно подтвердил safe role flags, NOLOGIN, `connlimit=1`, non-null validity, exact settings, memberships/ownerships/sessions0, затем literal revoke/drop PASS. Финал: containers0, host secret0.

Root cause остаётся внутри runner ROLE_STATE predicate. Следующий минимальный proposal — без изменения proof разделить его на `ROLE_FLAGS` (flags+connlimit) и `VALID_UNTIL` (exact receipt equality). Значения receipt/timestamp наружу не выводить; новые process/logger/retry не добавлять. Candidate, independent review и runtime остаются отдельными gates.
