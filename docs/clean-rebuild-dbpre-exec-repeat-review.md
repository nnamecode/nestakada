# DBPRE runner repeat pre-execution review

Дата: 2026-11-16. Review ID: `RB1-EXEC-REVIEW-002`.

Вердикт: **CHANGES_REQUESTED — P1=0, P2=2, P3=0**.

Проверка выполнена read-only: edits0, runner/runtime0, Docker0, DB0, network0, tool errors0, cycle0.

## Закрыто

- `RB1-EXEC-P1-001` CLOSED: один reader `psql`, одна `REPEATABLE READ READ ONLY` transaction, identity/TLS assertion до subject CTE, stdout only29 facts.
- `RB1-EXEC-P1-002` CLOSED: exact-OID NOLOGIN и полный expected state proof до revoke/drop; mismatch откатывает DROP, exact-OID fallback делает NOLOGIN+literal revoke+fail-closed.

## Открыто

### `RB1-EXEC2-P2-001` — CREATE/TEMP скрыты datallowconn

В обоих global database proof blocks `CREATE` и `TEMP` проверяются только при `d.datallowconn=true`. На недоступной для подключения БД effective CREATE/TEMP могут остаться незамеченными, хотя контракт требует их ноль по всем БД.

Минимальная remediation: сохранить `datallowconn` только для effective CONNECT; убрать его только из CREATE/TEMP predicates в create и pre-DROP blocks.

Статус D-1267: **remediation candidate prepared, repeat review pending**. В обоих blocks CONNECT сохранил datallowconn, CREATE/TEMP проверяются по всем DB. Parser0/diff-check PASS; runner не исполнялся.

### `RB1-EXEC2-P2-002` — Mandatory binding до trap

`[Parameter(Mandatory=$true)]` обрабатывается до `trap` и `try`. Missing/unknown parameter способен вывести штатный PowerShell ErrorRecord/path вне bounded constant JSON. Supplied exact gate и DACL уже корректны.

Минимальная remediation: маленькая внешняя точка входа, перехватывающая binding edge cases, либо эквивалентный двухслойный entry без ослабления Mandatory semantics. Не создавать framework/launcher subsystem.

Статус D-1268: **same-file manual-args candidate applied; verification paused owner**. Pre-binding param block заменён exact two-argument parsing и одной failure function, без launcher. Parser0; четыре negative cases дали exit1/one-line, но две verification commands подряд были некорректны (empty wrapper, затем wrongly escaped expected JSON). По anti-loop третьей попытки нет; candidate не принят, correct gate/runtime0.

Статус D-1269: **remediation candidate verified, repeat review pending**. После owner resume прямой literal `-Unknown x` run без wrapper/regex/comparison дал exit1 и exact constant one-line JSON без ErrorRecord/path/stack/stdout. Correct gate/runtime0; external launcher0.

Итог D-1270: independent `RB1-EXEC-REVIEW-003` — **APPROVED P1/P2/P3=0/0/0**. Все четыре findings CLOSED; mechanical/no-bloat PASS; edits/runtime/Docker/DB/network0. Полный verdict: `docs/clean-rebuild-dbpre-exec-final-review.md`.

## Mechanical/no-bloat

- allowlist14 unique; facts29 unique = counts14 + structural4 + bytes6 + MAP5;
- reader1; RR/RO transaction1; compose only db/down;
- product/platform/state-machine additions0.

Следующий обязательный этап: fresh separate owner `RB1-READ-Q001` gate before one bounded actual run. Review approval не разрешает Docker/role/DB read автоматически.
