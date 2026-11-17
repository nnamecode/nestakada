# REBUILD-1 media DB binding v2 run

Дата: 2026-11-17. Run ID: `RB1-MEDIA-DB-BIND-RUN-005`.

Один owner-authorized v2 probe вернул:

```json
{"contract":"rb1-media-db-bind-v2","status":"FAIL","code":"DBPRE_FAILED_READ_CONTRACT_ANOMALY"}
```

Counts238/238/736 и usage guards (`unclassified=0`, `partition delta=0`) прошли. Минимум один из восьми anomaly aggregates ненулевой. Structure group и binding arithmetic после первой failing group не оценивались; six binding values не опубликованы. PASS/facts0, retry0.

Postcondition: project containers0, host secret false; final clean.

Дробление на восемь последовательных constant codes отклонено как bloat. Следующий предлагаемый bounded amendment — один reviewed `OBSERVED` drift-envelope с уже разрешёнными aggregate groups binding6/anomaly8/structure4, без hash/path/ID/row/raw error. PASS остаётся только при guards0. Новый run требует review и fresh owner gate.
