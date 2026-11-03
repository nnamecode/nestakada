# DEV-15: HTTP-границы и приватность ошибок

2026-11-03, D-396/D-397, RP15-018/PV15-001–007. Первый bounded native-набор PASS; независимое итоговое result-review — **APPROVED в ограниченной HTTP/privacy fixture области**. DEV-15 около97%, этап8 около28%.

Проверены неизменный Nginx/config, actualendpoint/parse/validate/SafeFormatter иHTTPSReader в ограниченной test-only HTTPfixture. Прежние2слота256/128МиБ,0.5/0.25CPU/PIDs64 и synthetic TLScerts поSHA; без БД/реальныхcredentials/MAINlease/hostports/новыхресурсов/программ/измененийWindows. Старыйсайт/VPS не затронуты.

| ID | Фактический результат |
| --- | --- |
| PV15-001 | Headers Content-Length1048577 безbody→Nginx413/no-store/no-cookie, backendcounters прежние. Полный JSON1048576байт дошёл до actualendpoint/auth/parse/validate→400 INPUT_REJECTED, не413; service/cursor0. Это допустимая транспортная длина с неверным DTO, не успешная бизнес-операция. |
| PV15-002 | Header value9000байт→400/no-store/no-cookie до backend; normalcontrol200. |
| PV15-003 | Неполныйheader: реально получен SERVER_EOF через5.003589с, без HTTPответа. Это serverclose, не408 и не clienttimeout. Backendcounters неизменны. |
| PV15-004 | POSTheaders/Content-Length1000/неполноеbody: SERVER_EOF через10.012127с, без HTTPответа. До backend не дошёл, cursor0, normalcontrol200. Это серверная partial-body граница Nginx; реальная operation/SQL rollback этим не проверены. |
| PV15-005 | Семь canarycases:auth401/URI400/payload400/injectedSQL503/OS503/unexpected500/process200. Имена/значения всехresponseheaders иbody просканированы, canaries отсутствуют; no-store/no-cookie во всех7. |
| PV15-006 | В8реальных safe logevents: INPUT_REJECTED3, AUTH_REJECTED1, TRUST_UNAVAILABLE2, UNEXPECTED_FAILURE1, PROCESS_MESSAGE1. В6сохранённых captures (API+ingresslogs и4successfulexec stdout/stderr) canaries отсутствуют. ActualHTTPSReader отверг syntheticchild; его намеренный stderr не вышел к родителю. |
| PV15-007 | Source30 host/frozen/config24/EV63/originalcerts/manifest/env/прежнийMAINfinalSHA совпали. Финал0контейнеров/пустойpermit/собственнаясетьудалена. PrivateACL доoutputs2объекта/4правила, после17/34; owner/SYSTEM/reparse0. |

Run `8967c6d5-a8d5-4d96-80ce-36f1eafdb2a3`; native report `work/dev15-privacy-20261103/result-8967c6d5-a8d5-4d96-80ce-36f1eafdb2a3.json`, SHA `289a19af370e68722e613262950b285522b9767c9186617f3efa19d66f08f02d`. Две группы охватывают перечисленные HTTP/privacy controls, финальная сохранность проверена отдельно. Collector `final-result.json` SHA `a96b64f254532862a12b7ae43720e06ca67c1e1c65643f71866c9f2244c37d8d` независимо связал rawcases/HMAC syntheticintent/codegate/logevents/canaries/источники и фактический Stop. Исходные102Git-изменения сохранены до подготовки. Rawcaptures/синтетическиефикстуры/ключи остались в ignored private/work.

## Границы и продолжение

SQL/OS/unexpected exceptions намеренно вводились в test-only endpoint-функцию. Это проверка безопасной обработки exception, не фактическая поломка SQL/диска и не transaction rollback. Authactor и cursorinstrumentation синтетические; actualSafeFormatter/endpoint/reader не изменены. Child-команда только в отдельном probe-процессе заменена на fixture, печатающую canary вstderr; настоящий HTTPworker этим кейсом не объявлен проверенным повторно. Наблюдались безопасные события, утверждения logs0 нет.

БД не открывалась: последнее SQL-свидетельство MAIN — D-392/Head13/epoch2/policy1/v2b42ec…. Новый MAIN signed context нужен перед SQL/native продолжением; прежний Head10Prepare не повторять и данные не сбрасывать. Остались RP15-015 SQL/disk-error injection/атомарный rollback наUNIT и остатки recovery/отказныхокон RP15-007/019, включая соответствующие интеграционные transport controls. Штатный Django/auth/БД, полныеRP/DEV-15/APP/DEV-29/production этим не закрываются.
