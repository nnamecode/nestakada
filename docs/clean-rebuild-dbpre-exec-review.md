# DBPRE runner pre-execution review

Дата: 2026-11-16. Review ID: `RB1-EXEC-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P1=2, P2=2, P3=0**.

Review выполнен read-only. `tools/rebuild-dbpre.ps1` не запускался; Docker/DB/role/network не изменялись. `RB1-READ-Q001` остановлен и требует нового актуального owner approval после remediation+repeat review.

## Подтверждено

- exact gate/dev stopped manifest/project/db volume и only-db service scope;
- fresh 96-hex secret, fixed paths и cleanup intentions;
- CREATE ROLE transaction, DB-clock+15m, membership/ownership checks;
- facts29/29 unique = counts14 + structural4 + bytes6 + MAP5;
- current/previous/staff semantics и zero MAP5/structural checks;
- parser errors0; product/schema/dependencies unchanged; no new subsystem.

## Findings

### `RB1-EXEC-P1-001` — две TLS connections/snapshots

Identity и aggregate SQL вызываются двумя `psql` processes. Identity proof не относится к subject read connection, единый snapshot contract нарушен.

Минимальная remediation: один SQL script, один `psql`, один `BEGIN REPEATABLE READ READ ONLY`; identity/TLS assertion до первого subject CTE, stdout только 29 facts.

Статус D-1260: **remediation candidate prepared, repeat review pending**. Отдельные `$identitySql` и reader process удалены; assertion выполняется в `$aggregateSql` до subject CTE внутри единственной `REPEATABLE READ READ ONLY` transaction. Статически: parser0, reader call1, transaction1, stdout facts-only. Runner не исполнялся.

### `RB1-EXEC-P1-002` — DROP без полного повторного state proof

Cleanup повторно проверяет OID/membership/ownership, но не exact flags/limit/validity/settings/effective privileges.

Минимальная remediation: после exact-OID NOLOGIN/sessions0 и до revoke/drop перепроверить весь expected role/privilege state. Любое отличие запрещает DROP и оставляет exact OID NOLOGIN с literal revoke, secret deletion и fail-closed result.

Статус D-1261: **remediation candidate prepared, repeat review pending**. Cleanup фиксирует OID+validity при создании и до revoke/drop сверяет exact role attributes/settings/sessions/membership/ownership/current expected privileges. Mismatch откатывает DROP-path; fallback разрешает роль строго по OID, даже после rename, и выполняет NOLOGIN+literal revoke, после чего общий finally удаляет secrets и возвращает failure. Runner не исполнялся.

### `RB1-EXEC-P2-001` — privilege proof ограничен schema app

Не доказаны exact relkind14, отсутствие CONNECT к другим DB и privileges в других non-system schemas/relations/sequences.

Минимальная remediation: global non-system effective matrix, разрешающая только source CONNECT, app USAGE и SELECT exact14; catalog reads — явное proof-only исключение.

### `RB1-EXEC-P2-002` — DACL/failure channel

Protected ACL не исключает broad explicit ACE; uncaught PowerShell/ValidateSet errors могут вывести path/line.

Минимальная remediation: exact allowed DACL principals/rights; manual gate внутри protected flow; failure — bounded constant JSON/code + nonzero exit без ErrorRecord/stack/path.

Статус D-1264: **ПРИОСТАНОВЛЕН ВЛАДЕЛЬЦУ**. Read-only ACL inventory подтвердил protected DACL с exact current-user/LocalSystem FullControl inherited-to-children ACE. Две patch-попытки заменить pre-flow `ValidateSet` protected-flow exact check отклонены одной safety policy; вторая сохраняла Mandatory. По anti-loop rule третьей попытки нет. Код не изменён; требуется отдельное явное owner approval либо partial remediation с незакрытым binding leak.

## Mechanical/no-bloat

- parser0, tokens1625; facts29/unique29; allowlist14/unique14; MAP5; blocking structural3;
- output cap65536; compose only db/down; reviewer edits0/tool errors0/cycle0;
- fixes remain inside one PowerShell runner/literal SQL; no service/role manager/secret manager/queue/platform/table.

Статус D-1262: **`RB1-EXEC-P2-001` ПРИОСТАНОВЛЕН ВЛАДЕЛЬЦУ; candidate unaccepted**. Literal global checks внесены в create/pre-DROP blocks, но две mechanical verification commands подряд завершились ошибками самой команды. По anti-loop rule третьей попытки нет. Runner не исполнялся; возобновление только другим способом проверки после решения владельца.

Статус D-1263: **remediation candidate prepared, repeat review pending**. После owner resume literal search подтвердил два симметричных global proof blocks; parser0 и diff-check PASS. Разрешены только effective source CONNECT, app USAGE и exact14 relkind r/p SELECT; остальные non-system database/schema/relation/sequence privileges запрещены. Runner не исполнялся.

Статус D-1265: **`RB1-EXEC-P2-002` remediation candidate prepared, repeat review pending**. Mandatory сохранён; exact gate перенесён из pre-flow ValidateSet первой проверкой внутрь try. Exact protected DACL допускает только current SID и LocalSystem FullControl ACE. Negative invalid-gate execution: parser0, exit1, stdout0, exact constant JSON stderr, Docker/DB0.

Следующий ordered этап: independent repeat pre-execution review всех четырёх findings only. Все findings остаются candidates до review. Role/DB/media/private/export/target/product remain closed.
