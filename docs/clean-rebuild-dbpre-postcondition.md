# D-1271 DBPRE postcondition evidence

Дата: 2026-11-17. Evidence ID: `RB1-POST-001`.

Read-only bounded Docker inspection после owner resume:

- exact dev container `nestakada-foundation-dev-db`: absent;
- project lifecycle events in bounded queried window: 0;
- host secret `work/foundation/dev/private/rebuild-reader-password`: absent;
- PostgreSQL/runner/SQL не запускались.

Вывод: host/runtime stopped cleanup подтверждён. Состояние роли внутри preserved PostgreSQL volume read-only средствами без старта сервера не доказано. Events0 не заменяет catalog query; aggregate facts/PASS не заявляются.

Не создавать offline parser PostgreSQL storage. Минимальный следующий вариант требует отдельного owner gate: start only existing dev DB, catalog-only inspect exact role signature; если role absent — stop; если signature exact — NOLOGIN/literal revoke/drop; при любом mismatch — no mutation, stop и report. Subject tables/reader/aggregate/media/app не запускать.

## D-1274 cleanup-only catalog result

- started service: exact existing dev `db` only;
- SQL scope: `pg_roles`, exact name presence only;
- result: `ROLE_STATE=ABSENT`;
- mutation/new role/delete/subject-table read: 0;
- teardown: PASS.

Итог: D-1271 cleanup postcondition полностью доказан — dev container stopped after teardown, host secret absent, temporary role absent. Aggregate facts/PASS по-прежнему отсутствуют; third old-runner retry запрещён.
