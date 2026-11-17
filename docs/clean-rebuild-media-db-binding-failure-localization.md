# REBUILD-1 media DB binding failure localization

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-DB-BIND-FAILURE-LOCALIZATION-001`.

## Статический вывод

`RB1-MEDIA-DB-BIND-RUN-001` вернул общий `DBPRE_FAILED_READ`. В runner этот код охватывал четыре последовательные границы, поэтому исторический envelope не позволяет безопасно различить:

1. `READ_SQL` — reader SQL/connection/timeout;
2. `READ_ENVELOPE` — syntax/duplicate/count parsing bounded facts;
3. `READ_CONTRACT` — expected matrix или anomaly/structural drift;
4. `READ_OUTPUT` — построение/cap финального JSON.

Raw stderr, SQL, факты или exception text для диагностики не нужны и не разрешены.

## Минимальный кандидат

Только media-binding profile получает четыре фиксированных внешних кода: `DBPRE_FAILED_READ_SQL`, `DBPRE_FAILED_READ_ENVELOPE`, `DBPRE_FAILED_READ_CONTRACT`, `DBPRE_FAILED_READ_OUTPUT`. Они назначаются перед уже существующими блоками. Старый `RB1-READ-Q001` сохраняет `DBPRE_FAILED_READ` и прежнее поведение.

Новых процессов, logger, retry, dependency, table/grant, SQL query или output field нет. Коды не раскрывают values и публикуются только после обязательного cleanup. Этот кандидат не разрешает повтор probe.

## Acceptance

- `RB1-MDB-LOC-AC-001`: external allowlist содержит ровно четыре новых constant media codes.
- `RB1-MDB-LOC-AC-002`: order SQL→ENVELOPE→CONTRACT→OUTPUT соответствует существующему control flow.
- `RB1-MDB-LOC-AC-003`: old DBPRE path остаётся на generic `DBPRE_FAILED_READ`.
- `RB1-MDB-LOC-AC-004`: raw error/SQL/facts on failure0; cleanup-first semantics unchanged.
- `RB1-MDB-LOC-AC-005`: runtime/DB/Docker/retry0; independent review обязателен до любого нового owner gate.
