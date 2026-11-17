# Independent review: DBPRE cleanup reader-session drain

Дата: 2026-11-17. Review ID: `RB1-CLEANUP-DRAIN-REVIEW-001`. Contract: `RB1-CLEANUP-DRAIN-001`.

## Вердикт

**APPROVED — P1=0, P2=0, P3=0.**

Root-cause inference признана обоснованной и не считается runtime PASS: два одинаковых cleanup-role failure, exact manual cleanup после задержки PASS, catalog-only predicate probe без reader9/9 PASS; session visibility — единственное наблюдаемое time-dependent условие.

`RB1-CD-AC01..007` подтверждены. Exact name/OID, NOLOGIN, state и settings идут до drain. Ровно один loop `1..20`, один `pg_sleep(0.05)`, snapshot refresh перед каждой проверкой и ещё один перед финальным assertion; early exit расположен до sleep. После bounded окна прежний fail-closed `sessions` assertion сохранён. Allowlist14, relations/global privileges, literal revoke/drop и четыре first-failure cleanup code/guard не изменены.

Механика: parser0; cleanup block1; order PASS; loop1/clear2/sleep1; facts29; reader1; RRRO1. No-bloat PASS: только локальная loop-variable и bounded SQL loop в существующем cleanup; новых функций, процессов, логов, зависимостей или retry framework нет.

Первая review-команда получила Windows `os error 123` из-за недопустимого glob; один изменённый retry по точным файлам прошёл, повторной ошибки/цикла нет.

Review: edits0, runtime0, Docker0, DB0, network0. Новый DBPRE этим verdict не разрешён и требует отдельного owner gate.
