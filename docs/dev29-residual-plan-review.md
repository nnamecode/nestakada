# DEV-29: независимое ревью следующего остаточного пакета P29-A

2026-11-03. **REG29-PLAN-REVIEW-001 APPROVED** как конкретное предложение для DEV29-Q012. Это не code/runtime approval и не решение вместо владельца. [План](dev29-residual-plan.md), reviewed raw SHA `baa2c5044694c4da2334f9eefe1dcb33fb295fd6836fa1a9ae31665e879fa484`.

Независимо проверен статический AST-инвентарь:7 файлов/11 классов/139 методов,131 прежний+8 publication (4 wire/4 DB). Report raw SHA `63c7ef492d7a2af208de6ba9dbbe13b83515f5e46906ad6bc0c7021e74df0db1`, current source hashes совпали. Tests executed/Docker/SQL0; AST-карта не названа функциональным PASS. Подтверждено существование указанных BoundedAdmissionTests методов и предметных guards/role/epoch/replay/reserve/recovery/lease assertions.

Приняты границы нового fixed run/scope и ровно4×HIDDEN/LIVE_NO_SET=8 отдельных cases. Payload wire-valid до admission negatives;0-query/ensure_connection assertions предусмотрены. На case≤2Operation/2AdmissionPolicy/2RecoveryReceipt, суммарно≤16successful prepares — это ограничения будущей реализации, проверяемые code-review, не фактические измерения готового probe.

Accounting/count injection явно отделены от реальной ёмкости, real1000CapacityProved=false; PG29-007/1000-loop/16-revision loop не вызываются, quotaEstimateAccepted не присваивается. Synthetic permit/resource facts/exclusion/lease/recovery являются service fixture, не native worker/process/restart/crash/concurrency/HTTP/full131/139 proof. Migration/transport и защищённый runner не вызываются/не меняются.

Builder-only fixture совместима с принятым outer atomic/forced rollback/doCleanups/close/reconnect pattern; test runner/lifecycle не подменяется. Источники31/guard/corpus/old packages/receipts/locks сохраняются. Fresh code/start/payload/result reviews, exact UNIT/MAIN/archive witnesses, TTL≤15min/remaining≥200s, caps/deadlines/2GiB и exact-own Stop заданы явно; при FAIL/expiry нет автоматического retry/продления.

Q009/Q011 не расширены молча: Q012 просит новый точный runtime grant, включая новые synthetic bounded admission/recovery cases. Новых findings нет. Рецензент не редактировал файлы, не выполнял Docker/SQL/keys/tests/Prepare. Предложение можно вынести владельцу; до ответа новый пакет и его Run не начинаются.
