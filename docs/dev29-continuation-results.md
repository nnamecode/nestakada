# DEV-29: результаты четырёх оставшихся PostgreSQL-групп

2026-11-03. **PG29-003/004/005/006 PASS; CONTINUATION-ACTUAL-RESULT-REVIEW-001 APPROVED**. [Итоговое независимое ревью](dev29-continuation-result-review.md). Основания Q009/Q010/Q011, D-421/D-423/D-425, [принятый план](dev29-continuation-plan.md), [code-review](dev29-continuation-postgres-review.md), [start-review](dev29-continuation-start-review.md), [payload-review](dev29-continuation-payload-review.md).

PG29-001 независимо принята ранее через [bounded saved-result review](dev29-saved-result-review.md) и **не повторялась**. Новый run d43d7a21-2ec0-4652-9c9a-00e95272db8a никогда не допускал001/002/007. Все пять ограниченных групп Q009 теперь приняты, включая независимую сверку их связи. CONT29-001–005 и F29-001–005 выполнены в этой фиксированной области; полный P29-A не завершён.

| ID | Проверенный результат | Probe / after-witness, ms |
|---|---|---|
| PG29-003 | Unknown/status/abort/terminal replay сохраняют deny, не регрессируют | 5978 /4576 |
| PG29-004 | Реальные service snapshot/read/consumer принимают LIVE_NO_SET без HTML-допуска; повреждения отклоняются | 5469 /4473 |
| PG29-005 | Реальная SQLSTATE22012 после незакоммиченных записей полностью откатывает state/charge/reserve; sameUUID retry/replay корректны | 5438 /4880 |
| PG29-006 | Ограниченные прежние HIDDEN/DELETED/REDIRECT/tombstone/abort/replay сохраняются; LIVE_NO_SET запрещён старому kind | 5734 /4301 |

Все группы source31 `1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e`, отдельная внешняя atomic/безусловный rollback/reconnect/cleanup. После каждой — independent read-only witness MAIN/UNIT/архивного catalog, byte-equal fresh baseline; sequence UNIT4true, предметные7 таблиц пусты, migrations3. MAIN state-v2b42ec332… и rows2c7464d1… прежние; UNIT52766/marker/schema/rows25fe39a2… прежние; архивы16387/32563 остаются закрыты. Probe proof и signed result receipt сохранены локально в immutable work.

## Допуск и сохранение

Canonical plan SHA a7959d12560ff085b0e333357d9b6d16565e4678149582530e43e540497c30e2. Code-review002 APPROVED, offline2263/79/59/28 PASS. Prepare/Verify/Before/VerifyStart, independent actual start review, DB-only restore, fresh Baseline/Authorize, independent actual payload review и closed Payload issuer прошли последовательно. Run один, группы строго003/004/005/006, previous PASS/after-witness и remaining≥200с перед следующей. Нет старого Run/Continue/Measurement/первой группы, нет подмены timestamp/старых DB IDs.

Signed disk totals: before340,295,283; after-run340,855,471; final341,024,400байт — каждый<2,147,483,648. Caps DB512MiB/.5CPU/PIDs128, helper256MiB/.5CPU/PIDs64 неизменны. Physical WAL/dead pages не заявляются неизменными. Физический диск не заполнялся; SQL22012 — согласованная injection.

23 public authorization inputs побайтно архивированы с SHA в `work/dev29-publication-20261103/pg-check/continuation/run/authorization-inputs/`, manifest сохранён до изменения bound документов. Source/package/protected/ancestry/full old focused/принятый saved-first после Run снова Verify PASS. Приватные ключи/пароли не архивировались и не отправлялись в Git.

## Stop и границы

Удалены только проверенные own DB8f25760397f53d38a940d1ce49c494169dcf672c03ff6f18b4c3aa96ccc742d4 и network194a3f327258d89080a070b442583c2cc770dc20f18f4f45b09885adad7ea2ed, после identity/labels/stop/notrunning/empty endpoint checks. Read-only After подтвердил PG18 clean shutdown; итоговый inventory0project containers/0trust networks/0run helpers, exact retained volume local/labels и workingpermit{}. Cleanup receipt в run/cleanup.json, result + signed result-receipt и все send/output/witness/phase files сохраняются.

Продуктовый source в этой смене не менялся. MAIN fixture writes/flush/reset/init/migrate/API/APP/ingress/pull/build/production/push/старый сайт/VPS не выполнялись. Старый focused namespace и принятые prerequisites неизменны.

Это ограниченные service PostgreSQL-проверки, **не полный P29-A**, не полный regression/e2e и не работающая публикация Django/HTML/EDGE. PG29-002 не получает отдельный PASS за assertions001. Quota1000/007/admission/recovery/concurrency/crash/полные прежние регрессии остаются NOT_RUN; A29-007 открыт. Следующий участок внутри этапа8 — точный безопасный план остаточных P29-A проверок; далее отдельные P29-B/C/D/E по publication-plan. Общий следующий этап9 «Unit-тесты» наступает после всей разработки. DEV-29 около35%, этап8 около31%; проценты не повышены за тестовую инфраструктуру.
