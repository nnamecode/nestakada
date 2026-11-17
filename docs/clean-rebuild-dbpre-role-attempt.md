# DBPRE ROLE-stage attempt and secret transport diagnosis

Дата: 2026-11-17. Evidence ID: `RB1-ROLE-RUN-001`.

Материально изменённый run после D-1276 завершился bounded `DBPRE_FAILED_ROLE`; reader/facts0. Cleanup-only catalog proof: exact role ABSENT, teardown PASS, host secret absent.

ROLE substep diagnosis без SQL/роли:

1. Host secret creation PASS; `docker cp` into read-only-rootfs container failed `PROBE_COPY`; teardown PASS, secret absent.
2. Stdin probe wrote through `docker exec -i`, but exact 96-byte/read check failed because PowerShell pipeline adds a transport newline; teardown PASS.
3. Changed `read/printf` probe intended to strip newline failed at `EXACT_WRITE`; teardown PASS.

Последние две stdin-remediation attempts исчерпали anti-loop allowance; третья запрещена. SQL/role/subject tables0, persistent mutation0.

Следующий безопасный вариант только после owner resume: static design/review маленькой .NET ProcessStartInfo stdin writer, которая пишет exact 96 chars без newline и возвращает bounded status; runtime probe/run закрыты до review. Не добавлять secret manager, mount subsystem, logs или framework.
