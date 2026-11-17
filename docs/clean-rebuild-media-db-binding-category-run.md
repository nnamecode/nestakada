# REBUILD-1 media DB binding category-localized run

Дата: 2026-11-17. Run ID: `RB1-MEDIA-DB-BIND-RUN-003`.

Один owner-authorized changed probe вернул:

```json
{"contract":"rb1-media-db-bind-v1","status":"FAIL","code":"DBPRE_FAILED_READ_CONTRACT_BINDING"}
```

Доказано: SQL/TLS/RRRO, envelope34 и `COUNTS` прошли, следовательно Asset238/AssetFile238/AssetUsage736 совпали. Первое несовпадение находится в `BINDING`: DB matched/unmatched, candidate matched/only либо gallery matched/missing. `USAGE`, `ANOMALY`, `STRUCTURE` после первого отказа не оценивались. Facts/PASS0, retry0.

Postcondition: project containers0, host secret false; final clean.

Следующий минимальный путь — статически разделить только BINDING на три constant пары `DB`, `CANDIDATE`, `GALLERY`, без values/facts. Не добавлять query, raw output, retry или framework. Новый probe требует review и fresh owner gate.
