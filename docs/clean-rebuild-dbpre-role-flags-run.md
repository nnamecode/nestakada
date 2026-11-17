# DBPRE role-flags diagnostic run

Дата: 2026-11-17. Evidence ID: `RB1-CLEANUP-RUN-006`.

Один owner-authorized changed DBPRE после `RB1-ROLE-STATE-SUBCHECK-REVIEW-001` завершился:

`{"contract":"rb1-dbpre-v1","status":"FAIL","code":"DBPRE_FAILED_CLEANUP_ROLE_ROLE_FLAGS"}`

Facts/PASS не принимаются, повтор не выполнялся. Exact identity/OID и `ALTER NOLOGIN` достигнуты; `VALID_UNTIL` не достигнут, поэтому прежняя validity hypothesis не подтверждена.

Обязательный exact cleanup после rollback/fallback подтвердил exact safe flags, NOLOGIN, `connlimit=1`, non-null validity, settings/relations/sessions0 и literal revoke/drop PASS. Финал: containers0, host secret0.

Следующий минимальный proposal — не дробить seven flags на новые production codes. Один отдельно gated catalog-only probe создаёт собственную временную роль, выполняет LOGIN→ALTER NOLOGIN→тот же flags+connlimit predicate в одной transaction и гарантированно rollback/drop+teardown. Subject tables/rows, DBPRE facts, secret и product code не используются. После результата — статический remediation proposal/review; full DBPRE остаётся закрыт.
