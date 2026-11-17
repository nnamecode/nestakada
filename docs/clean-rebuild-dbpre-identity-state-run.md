# DBPRE cleanup identity-state result

Дата: 2026-11-17. Evidence ID: `RB1-CLEANUP-RUN-004`.

Один owner-authorized changed DBPRE после `RB1-CLEANUP-PROOF-DIAG-REVIEW-001` завершился:

`{"contract":"rb1-dbpre-v1","status":"FAIL","code":"DBPRE_FAILED_CLEANUP_ROLE_IDENTITY_STATE"}`

Диагностика сработала и исключила session/relations/privileges/revoke-drop groups. Facts/PASS не принимаются, повтор не выполнялся.

Обязательный exact cleanup подтвердил остаточную роль по точному имени, безопасным flags/NOLOGIN/connlimit, одной exact settings row, memberships/ownerships/sessions0; literal revoke allowlist/schema/database и DROP прошли. Финал: `ROLE_CLEANUP=PASS`, project containers0, host secret0.

Manual cleanup не имеет сохранённого create receipt и потому не доказывает два runner-only equality: stored OID и exact `rolvaliduntil` microseconds. Следующий лёгкий путь — только статический разбор capture/parse/interpolation этих двух значений. Не повторять прежний OID/time runtime probe, не добавлять новые stage codes/logger/retry и не запускать DBPRE без remediation+review+fresh owner gate.
