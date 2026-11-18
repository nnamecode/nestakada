# REBUILD-1 media source verifier runtime result

Дата: 2026-11-17. Result ID: `RB1-MEDIA-SOURCE-RUN-001`.

Статус: **FAIL; independently observed final state clean; result not accepted**.

Owner gate: явное `Разрешаю один локальный запуск RB1-MEDIA-SOURCE-Q001`.

Frozen inputs перед запуском:

- `tools/rebuild-dbpre.ps1`: `66654f337b992927f91e24beb9698f4a8c255bf6`;
- `tools/rebuild-media-source.sql`: `0f99fa219679f775e34a10afc07156aafd594e1d`;
- cidfile preexists0.

Первая sandboxed invocation остановилась на precheck с `DBPRE_FAILED_PRECHECK`: Docker API вернул host-side `permission denied` к Docker Desktop named pipe. Docker/DB/verifier/media не запускались, project containers/verifier/cidfile/secret оставались0. После изменения условия на approved elevated Docker access выполнен ровно один фактический runtime.

Terminal envelope фактического run:

```json
{"contract":"rb1-media-source-v1","status":"FAIL","code":"DBPRE_FAILED_MEDIA_SOURCE_CLEANUP"}
```

Host wall time фактической invocation около27.8s. `RESOLVED` и descriptor facts не заявлены; raw key/SHA/bytes/rows/log отсутствуют. Automatic retry0.

Немедленная exact read-only post-run проверка с Docker access:

- compose project containers0;
- verifier exact manifest-runId-derived name0;
- verifier exact evidence label0;
- `rebuild-media-verifier.cid`0;
- host `rebuild-reader-password`0;
- exact `nestakada-foundation-dev-state` identity unchanged.

Это доказывает наблюдаемое final clean state, но не превращает terminal FAIL в RESOLVED и не доказывает, был ли exact descriptor успешно подтверждён до cleanup phase. Следующий шаг — independent result/code-path review; новый runtime требует нового owner gate и до review не предлагается.
