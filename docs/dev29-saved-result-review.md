# DEV-29: принятое ревью сохранённой первой PostgreSQL-группы

2026-11-03. **SAVED-FIRST-RESULT APPROVED** — SAVED-ACTUAL-RESULT-REVIEW-001 после возобновления Q010/D-423. Первая группа PG29-001 не повторялась; Docker/SQL/DB start отсутствовали. Документ фиксируется как вход нового continuation, дальнейшие результаты записываются отдельно.

SAVED-VALIDATOR-CODE-REVIEW-002 APPROVED: замечания SAVED-REV-001–004 закрыты. Валидатор связывает archived19/source/package/ancestry, historical baseline freshness/metrics, first-before, точные run/measured/cleanup ledgers, восемь HMAC и повторную сверку public inputs до/после позднего чтения ключа.36 offline checks PASS, real key/writes/Docker/SQL0. Первое code-review требовало исправлений, оно не выдаётся за первоначальный PASS.

Независимый actual `saved-review.mjs Check` PASS; программное сравнение всех20 полей с immutable `work/dev29-publication-20261103/pg-check/saved-review-result.json` — same=true. Никаких ключей в выводе, вывод ограничен компактной сводкой.

| Свидетельство | Значение |
|---|---|
| Run первой группы | c7c7e203-9a52-4cd7-b5ab-e9c46a7a975d |
| Plan canonical SHA | e87e5ac447ef46b0b1a5b8e23149a24e23ffe2432f3df3766acda933f746f320 |
| First-result raw SHA | 7038e705c5f58adcaa57158e7149afa6d1e84510d1f2a4df625cc070d1e804fc |
| Input manifest SHA | e648f607746e8e303428c0b88be49dfea9c2a2dfe2c020450d741e663b644848 |
| Source fingerprint | 1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e |
| Probe / witness | 6343 /4562ms; peaks51,519,488 /46,137,344байт; OOM0 |
| Signed budgets before / after001 / final | 339233627 /339095464 /339264390байт, каждый<2GiB |
| Rollback / preservation / cleanup record | Подтверждены; MAIN/UNIT/архивы равны исходному baseline |
| Current runtime authority | false: прежний допуск не разрешает новый запуск |

CONTINUATION-PLAN-REVIEW-001 APPROVED для [плана оставшихся четырёх групп](dev29-continuation-plan.md), raw SHA `8d6130f0e102d3a710594ebd6f8801afc5c9684f468d071ed603c682c92ed432`. Scope/новый run/no001/002/007/неизменность focused/fresh gates/≥200с/caps/rollback/witnesses/Stop/partial limitations приняты; это review плана, не actual runtime admission. Новых findings нет. Q009/Q010 разрешают реализацию этого ограниченного продолжения после указанных независимых gates без нового вопроса владельцу.

Ошибки инструментов рецензент сообщал: неправильный literal substring, отдельная PowerShell pipeline syntax, затем дочерний spawnSync EPERM и отдельное усечение длинной строки decisions. Эквивалентные действия не повторялись: actual Check выполнен прямым CLI, сравнение — компактным JSON. Повторного цикла после Q010 не зафиксировано. Старый сайт и VPS не затронуты.
