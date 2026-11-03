# DEV-29: независимое ревью offline preflight Q013

2026-11-03. **COMP29-PREFLIGHT-REVIEW-001: APPROVED только для pure/offline слоя.** Автор — координатор; независимый рецензент `/root/dev29_publication_review` артефакты не редактировал. Основания: COMPLETE29-PLAN-001, ответ владельца Q013/D-431.

Проверенные ignored-артефакты:

| Файл в work/dev29-publication-20261103/pg-check/complete/ | Raw SHA256 |
|---|---|
| preflight.mjs | `98eca344e67ad62f99452a93fd93e21624da9fa17a658f3c0552470fa30e9107` |
| preflight-test.mjs | `9065295dc0f97211e984a2146809269fd2cf73fbe4fda9403ed4c7ff3f6eebfe` |

PLAN точно связан с SHA256 согласованного предложения `6c97ad9c7c0d340883b5d8f5e06121abee846b7bdab335b031a88d1651330e36`. HBA bytes проверяются в порядке first-match без broad/local fallback; raw HBA SHA256 `1b9fb6595cec5bb87f617b52a093f944a2a9bc2974d026d169a6d73b33b56646`.

Проверены closed sample/root inventory, safe integer bytes, свежесть≤5с, общий сбор≤3с, T<1,5GiB и строгое T+1GiB<2GiB перед C. Pure frame validator проверяет размер≤4096bytes, точные поля, run/phase/plan/source/sequence/previous digest и ≤4calls/≤10с. Он не выдаёт ACK и не заменяет реальный supervisor.

Координатор и рецензент независимо выполнили `node --test .../complete/preflight-test.mjs`: **4/4 PASS, failures/skips0**. Негативы: изменённый HBA/IPv6/order/fallback, stale/future/slow samples, drift/missing roots/invalid bytes, границы abort/headroom, foreign/replayed/malformed/oversized/burst frames. Это не полный набор139 и не PostgreSQL-проверки.

`runtimeGate(C/T)` безусловно запрещает запуск с `COMP29_PHYSICAL_BOUND_NOT_PROVEN`. Report честно содержит NOT_RUN/NOT_PROVEN/runtimeAdapter=false/sqlExecuted=false/dockerExecuted=false. Применимых замечаний к этому ограниченному слою нет.

**Не проверены и не реализованы:** parsed `pg_hba_file_rules`, реальная role×DB×TLS matrix, privileged audit, collectors/supervisor/ACK, guarded Django setup и runtime adapters. Физическая граница464MiB не доказана этим кодом или четырьмя тестами. Настоящие C/T остаются NOT_RUN; это не одобрение complete package или runtime Q013.

Технические отказы координатора: apply_patch не создал parent directory, после чего папка создана штатным `require_escalated` без ACL; первый sandbox Node runner получил spawn EPERM, повтор выполнен с изменившимся условием — штатной эскалацией — и прошёл. Эквивалентных повторных отказов не было. Защита продуктового runner не обходилась. Рецензент также запускал offline-тесты через штатную эскалацию. Docker/SQL/секреты не использовались.
