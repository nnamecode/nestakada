# P29-A: независимое ревью PostgreSQL-способа

Дата: 2026-11-03. Артефакт: `dev29-postgres-proposal.md`. PG29-PROPOSAL-REVIEW-001: **APPROVED для передачи владельцу на DEV29-Q006**. Это проверка реализуемости, не согласование вместо владельца и не допуск Docker/SQL.

Рецензент проверял документ read-only по фактическим RB15/RF15/FC15 probe, fixtures, настройкам TRUST и runner. Файлы не менял, Docker/БД не запускал, ошибок инструментов не было. Замечаний P0–P3 нет.

Подтверждены внешний rollback с независимым reconnect witness, отсутствие TransactionTestCase lifecycle/flush, реализуемость поздней SQLSTATE22012 injection, свежая проверка точных UNIT OID/owner/marker/schema/sequence/empty tables. MAIN только read-only; архивы остаются закрытыми и сверяются по catalog identities/прежним подписанным proofs. Candidate source имеет собственный перечень/fingerprint; исторические source/EV63 не переаттестуются новому коду.

Guard/runner/Start/Tests/Calibrate/ArchiveUnit, рабочие permit/lease не меняются и не вызываются. Прежние DB512/helper256, pinned images/internal network/read-only mounts сохраняются. Quota1000 требует оценки бюджета, при превышении deadline/caps — BLOCKED без mock PASS. BoundedFixture даёт service-level evidence; native lease/exclusion, полные регрессии, multiconnection/restart/crash/TLS-loss не доказаны.

До исполнения обязательны code/QA/VM-negative gates и отдельный точный runtime admission. Preservation failure важнее функционального PASS, auto-retry нет. Пакет ещё не реализован, PG29-001–008 NOT_RUN, P29-A не завершён. DEV-29 около35%, этап8 около31%.
