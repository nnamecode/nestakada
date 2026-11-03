# DEV-15 — независимое ревью проверки ёмкости

2026-11-02, D-380, DEV15-CLOSE-02. Автор Python-helper — dev15_policy; host/controller и Tests guard — координатор; readonly-рецензент — dev15_review. Рецензент не изменял код и не запускал Docker/SQL/тесты.

Code gate для одного сохранённого UNIT-набора положительный. Проверены exact DB/роль/пустота, B.unit_calibration только для незавершённых evidence, неизменные caps, воспроизводимые fixtures, общий count corpus и отдельные ref/tomb отказы, резерв/UNKNOWN/finish/replay, SQL whole SHA, измерения и сохранность. SQL52страницы не объявляются TLS30с или полным RP15-011; свежий UNIT-набор не является отдельной проверкой включения4старыхMAINопераций в limits.

CAP-REV-001 закрыт до первого запуска: физический учёт исправлен с public на trust и требует ровно7таблиц с числовыми heap/index/TOAST. Python AST/Node syntax PASS, исходный gate с8SHA сохранён.

После первого pre-helper EOF-отказа отдельно проверены readline/newline fix, сохранение originalattempt/report/input и exact-empty UNIT guard. После другого раннего Start-отказа проверены сохранение preflightFAIL/gate1/SHA, targeted stoppedhelper removal без force/-v и финальный cleanup только своего helper по точным labels/image/read-only mounts без volumes. Данные БД не очищаются. Это проверки исправленных условий, а не скрытый reset одноразового корпуса.

**PREHELPERRESUME code gate положительный:** один resume-001 с отдельными fixed wx report/runner/gate/receipt, HMAC parent/131evidence/probe hash, actual empty UNIT/OID/schema/role и MAIN/archive preservation до нового create; linked receipt до исполнения. Originalattempt продолжает блокировать Tests. Если таблица непуста или resume-квитанция уже существует, запуск закрыт. Итоговый capacity result пока ожидается; успех контроллера не предрешён ревью.

DEV-15 около90%, этап8 около28%; старый сайт/VPS/MAIN admission не затронуты.

## Сохранное продолжение после фактического отказа

Readonly-аудит проверен независимо до исполнения: только SELECT/SHOW в явном REPEATABLE READ, READ ONLY, exactUNIT/role/OID, V2 frame-формула без Head FOR UPDATE, verifiers только внутри SHA. По замечанию рецензента source policy и actual source различаются в отчёте и сравниваются. Аудит установил964ALLPENDING/4096/948; точная причина прежнего exit1 не выдумывается.

Отдельный A/B code gate положительный. Рецензент прочитал весь новый helper/host/audit/guard: проверяются полный checkpoint и план сохранённых данных, каждый payload/phase/Head rolling chain/accounting/FK, original namespace/counter17+j, реальные новые runtime/container и приватные signed lease до исполнения. A/B имеют отдельные fixed wx receipts/reports; B требует HMAC checkpoint A с SHA входной квитанции и отчёта. Bootstrap/новаяpolicy/evidencebypass/reset отсутствуют, по600с/caps без повышения. После FAIL автоматическая следующая часть не разрешается. Docker logs сохраняются до parse/cleanup и дополнительно после Stop. Это code gate к двум частям того же корпуса, не capacity PASS/TLS/MAIN activation.

## Промежуточное result-review A

Положительное: actual388.672с/540обращений в mutation wrapper, включая3ожидаемыхотказа (537успешных:36prepare+500finish+1UNKNOWN). Head1502/epoch1,1000/4096/1024,500FINAL/500PENDING, logical26322077/reserved4097000 совпадают с after-readonlyAudit. Checkpoint report SHA589236… и receipt SHAc13b86… совпадают с файлами; checkpoint.finalAudit равен helper.finalAudit. Реальная reserve-граница, неизменность состояния при отказе, отсутствие новыхpolicy/сменыepoch и resource/main/archive/Stop факты подтверждены рецензентом по JSON. Рецензент ничего не исполнял. Блокеров перед уже проверенной B нет при её обязательной повторной HMAC/live-state проверке; RP010partial/TLSNOTRUN сохранены.

## Итоговое выбранное capacity result-review

**Положительное в ограниченной области.** B280.881с PASS,504обращения wrapper, включая один ожидаемый отказ (503успешных:500finish+3replay). B before-state соответствует подписанному A checkpoint; report/receipt/parent/helper SHA проверены по файлам. Итог Head2002/epoch1, logical30419077/reserve0,1000FINAL/4096адресов/refs/1024tombs/1policy и полный V2 SHA116bb54… совпадают с независимым after-readonlyAudit. SQL52страницы/5120items2.775с, digest5933ad… совпал. Main/archive B до/после идентичны, финал stopped/0/helperremoved.

Helper B peak99020800, DB330985472/OOM0, observed305217972байта подтверждены. Периоды A/B не смешиваются с неизвестным peak/причиной исходного exit1. Fresh UNIT selected RP008/009 PASS не подменяет legacy4inclusion; RP01064MiB/RP011TLS/весь RP012/native/MAINactivation остаются отдельными. Новых блокеров отчёта нет. Рецензент не исполнял код и не менял исходники. DEV-15 около92%, этап8 около28%.
