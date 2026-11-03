# DEV-29: результаты восьми residual service cases

2026-11-03. **Run8 PASS; REG29-ACTUAL-RESULT-REVIEW-001 APPROVED**. [Итоговое независимое ревью](dev29-residual-result-review.md). REG29-AC01–05 выполнены в фиксированной service-области. Основание Q012/D-428, [план](dev29-residual-plan.md), [code-review](dev29-residual-code-review.md), [actual start-review](dev29-residual-start-review.md), [actual payload-review](dev29-residual-payload-review.md). Ранее принятые5 PG-групп не повторялись.

| Case | Проверенное поведение | Probe / after-witness, ms |
|---|---|---|
| RG29-001-HIDDEN | Invalid/missing signed admission, environment alone, disabled/resource failure — deny до предметного SQL/ensure_connection | 7669 /4548 |
| RG29-001-LIVE | То же для wire-valid LIVE_NO_SET | 7165 /4229 |
| RG29-002-HIDDEN | Reader401, wrong epoch, revoked credential не дают write; correct writer/prepare replay | 7920 /4869 |
| RG29-002-LIVE | То же для LIVE_NO_SET | 8343 /4495 |
| RG29-003-HIDDEN | Completion reserve/отказ нового prepare/unknown/final/replay; explicit accounting/count injection, actual Operations2 | 12351 /4382 |
| RG29-003-LIVE | То же для LIVE_NO_SET | 11164 /4533 |
| RG29-004-HIDDEN | Lease revision без новой policy, stale lease deny, fence/reconciliation/activate replay, old credential revoked/new credential prepares | 8693 /4681 |
| RG29-004-LIVE | То же для LIVE_NO_SET | 8902 /4798 |

Каждый case — новый helper/BoundedFixture только как builder/внешняя atomic/forced rollback/reconnect. После каждого независимый read-only MAIN/UNIT/archive witness byte-equal baseline. Source31/UNIT52766/marker/schema/empty7journal tables/migrations3/sequence4true, MAIN state-v2b42ec332… и закрытые архивы16387/32563 сохранны. Raw row counters после каждого DML не зависят от Manager.count injection и ограничены2Operation/2AdmissionPolicy/2RecoveryReceipt на case.

Обязательные limitations: real1000CapacityProved=false/nativeLeaseProved=false/fullRegression=false/fixtureResourceFacts=true. Count/accounting injection только RG29-003; это unit boundary modeling, не прогон1000/1001 и не physical capacity PASS. Synthetic permit/resource/exclusion/lease proofs только tmpfs helper, working permit/credentials не менялись.

## Допуск, ресурсы и сохранение

Run45d7428f-a1f0-47e8-914e-66fbc9c041b8; canonical plan90114402d2f4a58407b0776370ffe102cacfe1643ae2770652284d7d91c78e2e. Code-review002/actual start/payload reviews APPROVED; offline3057/88/59/28/42 PASS. Prepare/Verify/Before/VerifyStart/DB-only restore/fresh baseline/Authorize/Payload/Run прошли последовательно. Один Run8, перед case previous PASS/after-witness и remaining≥200с; retry/продление timestamp отсутствуют. Signed result receipt и все send/output/phase/witness артефакты сохранены в ignored residual/run/.

Signed budget bytes: before341514648 /after-run342314307 /final342458659, каждый<2GiB. DB512MiB/.5CPU/PIDs128 и helper256MiB/.5CPU/PIDs64, helper60с/host90с/output1MiB сохранены. Physical WAL/dead pages не заявляются неизменными, физический диск не заполнялся. Перед Before отдельная readonly диагностика обнаружила project inventory latency19,4с; production deadlines/caps не изменялись, Before/VerifyStart PASS с первой попытки.

29 public inputs (код/план/ревью/owner/статический инвентарь/prior proof links) архивированы с SHA до правки bound docs. Product source31/runner/корпус/старые пакеты/receipts/locks неизменны; post-run Verify source/package/protected/full ancestry/prior-five PASS. Ключи/пароли не копировались и не отправлялись в Git.

## Stop

Удалены только own DB89ef1cefb874751c5f3b60b0b960b035f32bd722a4ad6f95b2ceb8bc1321bbc3 и networke933a41558560ccd383062b7533a89fc6702987bca98cc6ccd7a27118b730a18 после identity/labels/stop/notrunning/empty endpoint checks. RO After подтвердил PG18 clean shutdown и конечный бюджет. Read-only inventory0project containers/0trust networks/0run helpers, retained local volume с прежними project/volume/scope labels, permit{}. Cleanup record связывает result/final budget/source verification.

MAIN fixture writes, init/migrate/flush/runner/test lifecycle/1000-loop/16-revision loop/API/APP/ingress/pull/build/старый сайт/VPS/production/push не выполнялись. S.bootstrap внутри изолированной rollback fixture — согласованный synthetic builder, не штатная bootstrap/init команда стенда.

## Приёмка P29-A после этого участка

| Область | Статус и предел |
|---|---|
| A29-001–006 | Ранее принятые wire/service PG-свидетельства сохранены; Run8 дополняет профиль bounded writer/recovery для обоих publication policy |
| A29-007 | Частичное новое service coverage guards/roles/epoch/reserve/recovery/lease. Real1000/1001, full131/139 runner, migration, transport, native exclusion/restart/crash/concurrency по-прежнему NOT_RUN |
| A29-008 | Rollback/MAIN/UNIT/archive/source/config/guard/permit preservation/Stop для Run8 независимо приняты |

REG29-AC01–05 приняты итоговым независимым result-review в этой фиксированной области; полный P29-A и публикация Django не объявляются готовыми. Следующий участок этапа8 — конкретный безопасный вариант для оставшейся настоящей ёмкости и полного guarded-runner/regression evidence, с сохранением корпуса и без обхода защиты; отдельное согласование перед новыми ресурсами/полномочиями. Общий этап9 «Unit-тесты» после всей разработки. DEV-29 около35%, этап8 около31%, без повышения за инфраструктуру.
