# Repeated DBPRE cleanup-role failure

Дата: 2026-11-17. Evidence ID: `RB1-CLEANUP-RUN-002`.

## Runtime result

После D-1285 владелец разрешил один полный DBPRE. Первый вызов без повышенного Docker access остановился на PRECHECK из-за sandbox permission и ничего не изменил. Единственный materially different вызов с Docker access завершился:

`{"contract":"rb1-dbpre-v1","status":"FAIL","code":"DBPRE_FAILED_CLEANUP_ROLE"}`

После сообщения владельца, что Docker активен, остаточная точная NOLOGIN-роль была условно удалена, затем один явно возобновлённый запуск снова вернул тот же `DBPRE_FAILED_CLEANUP_ROLE`. Facts/PASS не приняты. Третий DBPRE запрещён.

Остаточная роль повторно удалена только после exact flags/settings/membership/ownership/session checks и literal revoke allowlist. Финальное подтверждённое состояние: project containers0, host secret0; role DROP PASS.

## Ограниченная диагностика

- один catalog-only predicate probe без чтения subject rows подтвердил `STATE/SETTINGS/SESSIONS/ALLOWLIST/RELATIONS/DB/SCHEMA/TABLE/SEQUENCE = PASS`; роль удалена в той же транзакции;
- первый отдельный OID/time probe получил syntax error из-за буквального `\$\$`; teardown PASS;
- один изменённый retry остановился на `ROUNDTRIP_PREEXISTING` из-за остаточной probe-роли;
- exact probe-role cleanup по NOLOGIN/2099/no-settings/no-relations прошёл; containers0;
- по anti-loop третья OID/time попытка запрещена, root-cause diagnosis приостановлен владельцу.

Новые функции, логгер, retry-framework и product code не добавлялись. Следующее возобновление должно выбрать новый статический способ диагностики или отдельно рассмотренный минимальный cleanup change; полный DBPRE остаётся закрыт до remediation, independent review и нового owner gate.
