# REBUILD-1 media DB binding v3 run

Дата: 2026-11-17. Run ID: `RB1-MEDIA-DB-BIND-RUN-006`.

Один owner-authorized v3 probe вернул:

```json
{"contract":"rb1-media-db-bind-v3","status":"FAIL","code":"DBPRE_FAILED_READ_CONTRACT_BINDING"}
```

Counts238/238/736 и usage guards прошли. Failure возник в одном из five binding arithmetic invariants до OBSERVED output. Retry0. Postcondition: project containers0, host secret false; final clean.

Статическая причина: invariant `DB matched = candidate matched` корректен только при duplicate0, но DB/candidate duplicates входят в наблюдаемую anomaly group и могут быть ненулевыми. `gallery matched≤candidate matched` также не требуется для целостности transport envelope. Эти derived relations блокируют наблюдение drift, которое должны помогать интерпретировать.

Минимальная remediation: hard guards оставить только для трёх исчерпывающих сумм DB=AssetFile238, candidate=301, gallery=214. Equality/ordering оценивать на result review вместе с duplicate aggregates. SQL/output/grants не менять. Нужны static checks, independent review и fresh owner gate; автоматического retry нет.
