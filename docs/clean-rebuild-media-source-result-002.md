# REBUILD-1 media source verifier runtime result 002

Дата: 2026-11-17. Result ID: `RB1-MEDIA-SOURCE-RUN-002`.

Статус: **FAIL at START; final observed clean; media verifier/read not reached**.

Owner gate: fresh explicit `Разрешаю новый локальный запуск RB1-MEDIA-SOURCE-Q001`. Frozen runner `6aa64549a60526f669c6dbf3e791d79e2fac7b3a`; SQL `0f99fa219679f775e34a10afc07156aafd594e1d`. Prestate project0/verifier0/cid0.

Terminal envelope:

```json
{"contract":"rb1-media-source-v1","status":"FAIL","code":"DBPRE_FAILED_START"}
```

Host wall≈10.45s; automatic retry0. Immediate exact post-check: project containers0, exact verifier name/label0, cidfile0, host reader secret0, state volume identity unchanged.

Bounded Docker lifecycle metadata, без container logs/DB/media rows, доказали: exact DB container create/start; четыре bounded `pg_isready` attempts `2,2,1,0`; затем cleanup-file exec0, stop/die0/destroy. Reader role/secret bootstrap, RRRO session, verifier create/start и media read не достигнуты.

Static candidate cause: после successful ready runner получает full64 `$dbContainerId` через inspect, но `Assert-DbOnlyScope` использует `docker ps -aq` без `--no-trunc` и exact-сравнивает default short ID с full64. Та же short-ID assumption есть в invalid-cid exact-name recovery. Нужен independent code-path review до исправления; fresh runtime gate обязателен для нового run.
