# DEV-15: сохранность транзакций при ошибках

2026-11-03, D-398, RB15/RP15-015. Исправленный UNIT-набор PASS; итоговое независимое result-review — **APPROVED в ограниченной UNIT rollback области**. После принятия результата оценка DEV-15 около98%, этап8 около28%.

Реальный PostgreSQL и services.mutate проверены только на точной UNIT test_estakada_trust/OID52766 с прежним signedmarker/migrator/TLS. Использованы прежниеDB512МиБ/.5CPU и последовательные helper256МиБ/.5CPU/PIDs64. MAIN открывалась только readonly; writerlease/MAINactivation/HTTP-продукт не запускались. Физический диск не заполнялся, новых ресурсов/программ/зависимостей/измененийсервера нет.

| Сценарии | Фактическое наблюдение |
| --- | --- |
| RB15-001-ROUTE/TOMB | Prepare:до finalHead.save уже записаныoperation/preparephase и соответствующие2routes либо1tomb. Настоящий PostgreSQL SELECT1/0 дал SQLSTATE22012; serviceatomic rollback вернул полный before-state. |
| RB15-002-ROUTE/TOMB | Та же late-boundary с injectedOSErrorENOSPC28: полный rollback сохранён. Это имитация exception, не physicalENOSPC. |
| RB15-003-ROUTE/TOMB | Committed:доHead.save уже измененыoperation/phase иroutepolicy(когдаесть). Настоящий22012 откатил terminal:принятыйPENDING_DENY/tomb/резерв/receipts неизменны. |
| RB15-004-ROUTE/TOMB | TerminalENOSPCexception также сохранил прежнийdeny/reserve/историю. |
| RB15-005 | Во всех8ветвях повторялся тот жеDTO/UUID:8успешныхretry с единственнымHeadadvance;8exactreplay вернули тот жеphaseReceipt и не изменили full-state. |
| RB15-006 | Внешнийrollback+reconnect:UNITrows/counts/migrationsequence прежние. Независимый readonlyhelper до/после подтвердил UNIT OID/marker/schema/rows/sequence. MAINHead13/epoch2/policy1/v2b42ec… и обаархива сохранены; финал0контейнеров/permit{}. |

Before/after различаются только внутри незавершённых late-writes: зафиксированы реальные operation/phase и необходимыеroute/tombrows, промежуточный full-stateSHA отличается от baseline; после service rollback равен baseline. Fixture.setUp/start и все ветви находились внутри внешней rollbacktransaction. Test runner/flush/teardown/DROP/DELETE/миграции/resetsequences не вызывались. Восемь положительных UNITretry не являются записями MAIN или настоящими HTTP-операциями.

Run `d9473f0d-b2d1-40b3-a61d-313b33cebf15`, report `work/dev15-rollback-20261103/rollback-d9473f0d-b2d1-40b3-a61d-313b33cebf15-report.json`, SHA `47c7eb394c33fba8a8b486eec9ddea7042117845673dc9781ddda1d0d30e82df`. Collector `final-result.json` SHA `a398b3f76a20fb79fed21d62a62d27ba69647cb18616645f9da20cb290f432ca` отдельно сверил 7helperHMAC/input/output/CID/cgroup,8ветвей/4serverSQLerrors/4exceptioninjection/8retry/8replay, before/afterUNIT/MAIN/архивов и текущийStop. ArchiveproofSHA `a041996bf250e01a666260819848f0e16859ba4ee98295cf958d9db82dd46d14` совпал с прежним.

Source30 host/frozen/config24/EV63/manifest/env/keys прежние; исходные107Git-изменений сохранены, перед первымDBrun дополнительно111копий с SHA. PrivateACL890объектов/1780правил до и975/1950после, owner/SYSTEM/reparse0. Закрытый кодовыйgate и ресурсы оставались прежними, mount/helper/UI исправления не меняли продукт.

## Сохранённые отказы и границы

Первый run20e83112… остановился на readonlyaudit до подключенияUNIT: неверный путь к migrationpassword. Исправлено по фактическому Compose mount/env. Второй run12bfb3f9… получил protocolFault от ошибочно совмещённых policies/requestIds; статическая проверка подтвердила нарушение существующего validate. UNIT/MAIN/архивы после этого отказа независимо совпали. План исправлен до нового запуска: раздельные ROUTE/TOMB DTO, исходные RB15-001–004 сохранены как родительскиеID; validator не ослаблен. ОбаFAIL/raw/candidates/gates сохранены, не переименованы вPASS.

Финальный RB15 — настоящие UNIT-транзакции с искусственной точкой ошибки. Он не доказывает физическое переполнениеSSD, powerloss/внешнийrollbackTRUST, штатныйDjangoHTTP, Mainwriterlease или все RP15. Legacy-поля clonedcontroller `lease:NOT_IMPLEMENTED/native:NOT_RUN` описывают отсутствие выдачиlease/HTTP этим инструментом и не отменяют исторический D-392.

Далее остаточные RP15-007/019 recovery/отказныеокна и итоговая сверка соответствующих интеграционныхtransportcontrols/полногоDEV-15. Для новой MAINзаписи нужен актуальный signedcontext от принятой Head13/b42ec…, старый Head10Prepare запрещён. Старыйсайт/VPS/APP/DEV-29/production не затронуты.
