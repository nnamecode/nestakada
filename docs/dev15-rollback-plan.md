# DEV-15: атомарность при SQL/disk-error injection

2026-11-03, продолжение D-380/D-396 по «Продолжай». RP15-015; сценарии до кода/исполнения. DEV-15 около97%, этап8 около28%.

Только прежние PostgreSQL512МиБ/.5CPU и последовательный Pythonhelper256МиБ/.5CPU/PIDs64, без API/Nginx/hostports/новых образов/софта/ресурсов. UNIT строго test_estakada_trust/OID52766/прежний signed marker, migrator-role/TLS/пустые7journal tables/3migrations/foreignsessions0. Schema/source30/config24/EV63/контейнеры/том и оба архива проверяются до мутации. MAIN только readonly inspect: актуальный Head13/epoch2/policy1/v2b42ec… из D-392, без выдачи lease/activation/nativeHTTP.

Из проверенного operator-controller выделяется отдельный rollback-only инструмент с закрытой единственной командой. Prepare/Activate/Retry MAIN в нём не разрешаются. До запуска подписанный intent с исходнымиUNIT OID/marker, MAIN-снимком/прежним acceptedresult и точными helper/controller SHA. Исторический archive reference с Head9 остаётся историческим и не подменяет текущий MAIN; оба архива проверяются без сравнения MAIN с их старой Head9. Новая реальная MAIN запись/новый signed writer context не создаются.

Тестhelper использует уже принятый BoundedFixture: synthetic identity/credentials/UNIT activation/evidence bootstrap, actualservices.mutate/transactions/caps/CAS/binding. P.runtime_resource_facts подставляется штатной UNITfixture, не заявляется фактическим proof MAINlease. Никакого test runner/flush/DROP/DELETE/миграций/sequence reset: fixture.setUp/start только внутри внешней rollbacktransaction; doCleanups, но не TransactionTestCase teardown. Каждая ветвь дополнительно в savepoint с rollback.

| ID | Ожидаемое наблюдение |
| --- | --- |
| RB15-001 | prepare, отдельно ROUTE(2routes/0tombs) иTOMB(0routes/1tomb): допустимыйDTO иoperation/phase действительно записаны внутри транзакции до finalHead.save. В этой точке настоящий PostgreSQL SELECT1/0 даёт SQLSTATE22012. После serviceatomic rollback full-state-v2/rows/counts/reserve/Head равны before; новыхdeny/receipt нет. |
| RB15-002 | prepare:тот же late boundary, injectedOSError(errnoENOSPC28) вместо physical diskfull. Whole rollback равен before; это не физическое заполнение диска. |
| RB15-003 | committed, отдельно ROUTE/TOMB:принятый prepare уже защищает соответствующиеroutes либоtomb/reserve. После обновленияroute/operation/receipt, доHead.save — настоящийSQL22012. Послеrollback PENDING_DENY/резерв/tomb/все прежние данные неизменны. |
| RB15-004 | committed:аналогичная late ENOSPC-exception injection, принятыйdeny/reserve сохранён. |
| RB15-005 | После каждого отказа без новойUUID тот же DTO успешно повторяется один раз; затем exactretry возвращает тот же phaseReceipt/replayTrue без новогоHeadadvance/квоты. Positive unit operations отмечены как UNIT, не MAIN/API. |
| RB15-006 | Внешний rollback и reconnect: тот же UNIT OID/marker/schema/fullrawrows+counts/migrationsequence. Независимый readonly witness до/после через отдельный helper. MAIN актуальныйfullstatev2/обаархива закрыты и неизменны, source/config/EV63/keys прежние; Stop0/permit{}, privateACLowner/SYSTEM. |

Сбой доказывается только после реально наблюдённых SQLwrites late boundary, не одним exceptionmock доDML. Наружу только коды/счётчики/SHA, безsecret/verifier/payload/SQLtrace. Source/schema/условияUNIT сверять в child доsetUp и послеreconnect. При исключении гарантироватьouterrollback; неизвестное состояние UNIT не очищать, проверить read-only и остановиться. Никаких повторов отказавшего runTool автоматически. Exact gate, Node/Python syntax и independent code/resultreview до/после native обязательны.

RP15-007/019 recovery/отказныеокна и оставшиеся интеграционные transportcontrols не закрываются этим набором. Старыйсайт/VPS/APP/DEV-29/production/push не входят. Предпочтение владельца: сводку процентов поддерживать без повторного объявления этого в каждом сообщении.

Уточнение до исправленного запуска: каждый из RB15-001–004 имеет постоянные подслучаи `-ROUTE` и `-TOMB`, всего8ветвей при прежних60с/ресурсах. Протокол запрещает непустыеpolicies иrequestIds в однойprepareoperation; прежний смешанныйDTO был ошибкой теста, не требованием к продукту. Validate не ослабляется. Перед mutate каждыйDTO проверяется actualvalidate. Фактические прежние FAIL сохранены: первый readonlyaudit с невернымpasswordmount до подключенияUNIT; второй protocolFault из смешанногоDTO, независимые UNIT/MAIN/архивыbeforeafterсохранны. Теперь failures дополнительно содержат безопасные Fault.code/checkpoint; отдельный диагностическийDB-run не нужен, причина найдена статически.
