# REBUILD-1 media DB reconciliation result

Дата: 2026-11-17. Evidence ID: `RB1-MEDIA-DB-RECON-OBSERVED-001`.

Один owner-authorized v4 probe exit0 вернул OBSERVED envelope:

```json
{"contract":"rb1-media-db-bind-v4","status":"OBSERVED","source":"foundation-dev","elapsedMs":468,"binding":{"dbMatched":237,"dbUnmatched":1,"candidateMatched":236,"candidateOnly":65,"galleryMatched":214,"galleryMissing":0},"anomaly":{"candidateDuplicate":0,"dbPairDuplicate":1,"descriptor":0,"eligibleAssetState":0,"eligibleNoFile":0,"orphanConsumer":0,"unknownKind":0,"selectedOverlap":0},"structure":{"currentInvalid":0,"currentNewer":0,"pageWithoutState":0,"sharedCurrentInvalid":0},"duplicateMatched":{"pairGroups":1,"fileRows":2,"distinctAssets":2,"readyRows":2,"legacyRows":0,"privateSource":0,"main":2,"preview":0,"legacyPublic":0,"eligibleUsages":4,"excludedUsages":2},"unmatchedDb":{"pairGroups":1,"fileRows":1,"distinctAssets":1,"readyRows":1,"legacyRows":0,"privateSource":0,"main":1,"preview":0,"legacyPublic":0,"eligibleUsages":2,"excludedUsages":1}}
```

Candidate interpretation:

- duplicate matched pair belongs to two distinct READY/non-legacy/main assets and serves 4 eligible + 2 excluded usages; physical bytes may deduplicate later, but identities/usages cannot be silently collapsed;
- unmatched DB pair belongs to one READY/non-legacy/main asset and serves 2 eligible + 1 excluded usages; it cannot be excluded from transfer scope;
- gallery214 remains complete; ordinary candidate-only65 remain filesystem authority;
- all other anomaly/structure counts0.

Postcondition: project containers0, host secret false; run1/retry0, final clean. Private/per-row values0.

Статус: OBSERVED evidence candidate pending independent result review. No DB/allowlist/target mutation or transfer permission.
