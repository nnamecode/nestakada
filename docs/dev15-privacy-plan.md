# DEV-15: границы HTTP и приватность ошибок

2026-11-03, продолжение D-380/D-395 по «Продолжай». RP15-018 и частичное наблюдение RP15-015. DEV-15 около97%, этап8 около28%. Это сценарии до кода/исполнения, не PASS.

Прежние2слота Python256МиБ/0.5CPU иNginx128МиБ/0.25CPU/PIDs64, exact nginx.conf/images/source30, прежняя internalAPI-сеть и принятые synthetic TLScerts поSHA. PostgreSQL/MAIN/UNIT/архивы не открываются, реальных credentials/ключей/MAINlease нет. Как в LD15, actual `views.endpoint` обслуживается test-only HTTPadapter/authspy/cursor-failclosed; дополнительно actualSafeFormatter и actualHTTPSReader. Это не полный штатный DjangoHTTP/SQL и не SQL/disktransaction rollback. Код продукта/лимиты/системные настройки не меняются.

| ID | Ожидаемое конечное наблюдение |
| --- | --- |
| PV15-001 | Content-Length1048577 с headers безbody даёт Nginx413/no-store/no-cookie до backend. Полный JSON ровно1048576байт доходит до actualendpoint/parse/validate и даёт400 INPUT_REJECTED, не413; сервисная функция/курсор0. Это положительная транспортная граница, не valid prepare DTO. |
| PV15-002 | Header value9000байт даёт Nginx400/431 до backend; normalcontrol200. |
| PV15-003 | Неполныйheader наTLS реально удерживается до server timeout около5с:408 либо явное закрытие с записью времени4–8с, backendcounter неизменен. Client-side timeout не считается PASS. |
| PV15-004 | ПолныеPOSTheaders/Content-Length1000 и отправленное неполноеbody удерживаются до server timeout около10с:408 либо serverclose9–13с, backendcounter прежний, normalcontrol200. Это server partial-body boundary/SQLspy0; состояние реальной operation/транзакция UNIT этим не проверяется. |
| PV15-005 | Canary вauth/URI/payload:401/400 безcanaryвresponse, no-store/no-cookie. В actual endpoint injectedDatabaseError/OSError→503 TRUST_UNAVAILABLE, unexpectedException→500 UNEXPECTED_FAILURE; response/logне раскрываетmessage/trace. |
| PV15-006 | Реально наблюдаемые safe failureevents AUTH_REJECTED/INPUT_REJECTED/TRUST_UNAVAILABLE/UNEXPECTED_FAILURE иPROCESS_MESSAGE сохраняются в private rawlogs. FormatactualSafeFormatter, не пустойlogger. Canary SQLexception/URI/auth/body/processmsg отсутствует в stdout/stderrAPI/Nginx. ActualHTTPSReader child, пишущий canary stderr, отвергается; его stderr не появляется у родителя. Этот искусственныйchild отличается от настоящего HTTPworker и помечается отдельно. |
| PV15-007 | Source30/config24/EV63/oldartifacts/originalcerts прежние;0контейнеров/permit{}/собственнаясетьудалена, privateACLowner/SYSTEM до outputs/после. Все rawcaptures/metadata остаются ignoredwork, настоящих секретов/данных нет. |

Один bounded набор после независимого plan/code-review, syntax/AST и exactgate. Использовать проверенный LD15controller с сохранённой предыдущей версией; менять только testharness. Clienttimeout14с дольше serverboundaries, любой client timeout — FAIL. Подготовить наблюдение server EOF/408 и доказательство неизменности backendcounters, не подменять ожиданием сна. Суммарная nativeфаза≤30с, число запросов/размеры ограничены; burst/load не повторять. До остановки ingress/API собрать их boundedlogs и metadata successfuldockerexec stderr, проверить canaries/безопасныеevents, затем guardedStop.

Независимый result-review обязан отделить actualcode от fixture. SQL/disk-injection наUNIT/RP15-015 иrecovery/отказныеокна007/019 остаются. ДляMAIN нуженновыйsignedcontext отHead13/b42ec…, старуюHead10baselineнеповторять. Старыйсайт/VPS/APP/DEV-29/production/push/новыеинструменты илиресурсыневходят. На первойошибке остановить текущийcase, диагностикадоисправления; AGENTS-stop при второмэквивалентномотказе.
