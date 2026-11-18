# REBUILD-1 media source verifier runtime result 003

Дата: 2026-11-17. Result ID: `RB1-MEDIA-SOURCE-RUN-003`.

Статус: **FAIL; exact stopped created verifier retained for owner-gated cleanup-only**.

Owner gate: fresh explicit `Разрешаю новый локальный запуск RB1-MEDIA-SOURCE-Q001`. Frozen runner `30a23982109ef34fe49b5422ada57406b9de35b7`; SQL `0f99fa219679f775e34a10afc07156aafd594e1d`. Prestate project0/verifier0/cid0.

Terminal envelope:

```json
{"contract":"rb1-media-source-v1","status":"FAIL","code":"DBPRE_FAILED_MEDIA_SOURCE_CLEANUP"}
```

Host wall≈15.12s; automatic retry0. Post-run exact facts:

- compose project containers0 and host reader secret0;
- state volume identity unchanged;
- exactly one verifier remains by exact manifest-derived name and evidence label;
- cidfile exists, exact64 lowercase ID grammar, inherited two-rule private ACL;
- cid ID, container full ID, exact name, evidence label and pinned image all match;
- container `running=false`, `status=created`, `exitCode=0`: attached start/media read not reached;
- network none, root read-only, logging none, user/resources/cap-drop/security/mount/tmpfs/argv prefix match reviewed values;
- inspect reports `CapAdd` count1 where implementation required count0; this caused pre-start identity refusal. Cleanup reused the same stricter full-config predicate, so safe exact ID/name/label/image container was intentionally retained.

No container log, DB row or media byte was read/published. Next mandatory action is separate owner-gated cleanup-only: revalidate cid ID + exact name + label + image, remove only this never-started container, prove absence, validate then delete cidfile. Broad cleanup/rerun prohibited. Code-path review follows after clean state.

Cleanup-only result D-1379: owner explicitly authorized exact RUN003 removal. Coordinator revalidated canonical cid grammar and exact full ID/name/label/pinned image plus `created/running=false`, removed only that container, proved exact ID/name/label absence, revalidated unchanged cid bytes and deleted literal cidfile. `CLEANUP_ONLY=PASS`; verifier0/cidfile0. Container was never started and held no writable state.
