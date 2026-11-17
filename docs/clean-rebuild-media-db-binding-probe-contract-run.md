# REBUILD-1 media DB binding changed probe run

Дата: 2026-11-17. Run ID: `RB1-MEDIA-DB-BIND-RUN-002`.

После D-1329 owner разрешил ровно один changed probe. Результат:

```json
{"contract":"rb1-media-db-bind-v1","status":"FAIL","code":"DBPRE_FAILED_READ_CONTRACT"}
```

Это доказывает: reader SQL/TLS/RRRO и bounded envelope из 34 фактов завершились; отказ возник при сравнении с expected matrix/anomaly/structural zero contract. Facts/PASS не опубликованы и не приняты. Retry0.

Postcondition: project containers0, host secret false. Cleanup-specific failure отсутствует; final state clean.

Следующий минимальный путь — статически разделить только contract comparison на фиксированные категории `COUNTS`, `BINDING`, `USAGE`, `ANOMALY`, `STRUCTURE`, не публикуя values. Не добавлять raw facts/error logging, query, table/grant, retry или framework. Любой новый probe требует remediation review и fresh owner gate.
