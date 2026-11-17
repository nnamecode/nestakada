# REBUILD-1 media DB binding OBSERVED result

Дата: 2026-11-17. Evidence ID: `RB1-MEDIA-DB-BIND-OBSERVED-001`.

Один owner-authorized changed v3 probe завершился exit0:

```json
{"contract":"rb1-media-db-bind-v3","status":"OBSERVED","source":"foundation-dev","elapsedMs":226,"binding":{"dbMatched":237,"dbUnmatched":1,"candidateMatched":236,"candidateOnly":65,"galleryMatched":214,"galleryMissing":0},"anomaly":{"candidateDuplicate":0,"dbPairDuplicate":1,"descriptor":0,"eligibleAssetState":0,"eligibleNoFile":0,"orphanConsumer":0,"unknownKind":0,"selectedOverlap":0},"structure":{"currentInvalid":0,"currentNewer":0,"pageWithoutState":0,"sharedCurrentInvalid":0}}
```

Counts238/238/736, usage guards и three exhaustive sums прошли. Gallery exact214 полностью matched. DB has matched237/unmatched1; candidate unique matches236/only65. Единственный ненулевой anomaly — `dbPairDuplicate=1`; он объясняет разницу 237 DB matched rows против 236 matched candidate pairs. Descriptor/state/file/consumer/kind/overlap и structure anomalies0.

Postcondition: project containers0, host secret false; final clean. Run1/retry0. Paths, IDs, hashes, rows, SQL и raw errors не выводились.

Статус: **OBSERVED evidence candidate, не accepted baseline**. Следующий gate — independent result review арифметики, semantics и границ. До него transfer/import/Q002/product/live закрыты.
