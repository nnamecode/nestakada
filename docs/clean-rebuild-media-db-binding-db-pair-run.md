# REBUILD-1 media DB binding DB-pair run

Дата: 2026-11-17. Run ID: `RB1-MEDIA-DB-BIND-RUN-004`.

Один owner-authorized pair-localized probe вернул:

```json
{"contract":"rb1-media-db-bind-v1","status":"FAIL","code":"DBPRE_FAILED_READ_CONTRACT_BINDING_DB"}
```

Source counts238/238/736, SQL/TLS/RRRO и envelope34 ранее прошли. Поскольку `DB matched + DB unmatched = AssetFile238`, код однозначно доказывает `DB matched < 238` и `DB unmatched > 0`: часть DB file SHA+bytes отсутствует в exact301. Actual counts не опубликованы; candidate/gallery groups после первой failing pair не оценивались. Facts/PASS0, retry0.

Postcondition: project containers0, host secret false; final clean.

Дальнейшее дробление constant codes по отдельным агрегатам отклонено как bloat. Следующий предлагаемый лёгкий путь — один reviewed bounded evidence envelope с шестью уже разрешёнными integer binding aggregates (DB matched/unmatched, candidate matched/only, gallery matched/missing), без hash/path/ID/row/raw error. Он заменит неверную expected hypothesis фактической матрицей; новый probe требует отдельного scope amendment/review/owner gate.
