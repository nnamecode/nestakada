# DEV-15 — сохранённый набор предельной ёмкости

Обновление2026-11-02: A/B ниже сохраняют свой ограниченный PASS. Новый fixed TLS resume-003 получил SNAPSHOT_DEADLINE после manifest+45/52страниц; RP15-011 не принят. Сохранность после отказа отдельно подтверждена readonly UNIT/MAIN/архив/source/подписями. Факты — dev15-capacity-tls-results.md, следующий разбор — dev15-tls-deadline-investigation.md. Не заменять SQL2.775с TLS-результатом.

2026-11-02, D-380, DEV15-CLOSE-02, выбранные части RP15-008–012. Сохранный count/reserve/DTO/SQL-набор проверен A/B без сброса после первоначального отказа. Это не MAIN-активация и не полный CLOSE-02. DEV-15 около92%, этап8 около28%.

## Конечный набор и сохранность

План: 16 операций по256 уникальных адресов, затем983операции поодной отметке заявки и последняя с41отметкой. Итог — 1000операций, 4096текущих адресов и исторических ссылок, 1024tombstones. Ошибка4097-йссылки проверяется отдельно при16операциях;1025-яотметка — перед последней операцией, при999операциях. Конечный отказ новой1001-йоперации находится одновременно на count ceilings; независимая причина сверх1000не выдумывается.

Резерв заполняется реальными разрешёнными DTO без padding/повышения лимитов. При первом ожидаемом отказе проверяется неизменность состояния, UNKNOWN и завершение ранее принятых адресных операций освобождают резерв, тот же непринятый ID продолжается с новым CAS. После наполнения — точные prepare/unknown/terminal replay, полный state digest v2 и SQL-снимок5120items/52страницы с whole SHA. Фиксированный TLS-worker здесь NOT RUN: он отдельно прочитает этот сохранённый набор.

Старый архив60операций/15360адресов не изменяется. Точная UNIT перед bootstrap должна быть фактически пустой во всех7моделях и иметь actual current_database/test_estakada_trust и role trust_migrator. Используется тот же B.validator/S.mutate, signed policy/lease, без изменения caps. Code-owned UNIT context обходит только незавершённые финальные evidence. UNIT policy/evidence синтетические; это не настоящее разрешение MAIN.

Host создаёт helper без запуска и получает настоящий container ID, сохраняет private operator facts и HMAC signed capacity-attempt.json **до процесса**. Появление любой такой квитанции навсегда закрывает обычный local_trust Tests до отдельной проверенной процедуры архивирования. Сброс/удаление квитанции или корпуса не предусмотрены. Старый calibrationAttempted не меняется; старые Calibrate/ArchiveUnit не повторяются. Новая archive-процедура для сохранённого корпуса пока не реализована и не выдаётся за принятую.

Полные принятые synthetic payload/phases и admission prior state остаются в UNIT; UUID/phase data воспроизводятся из сохранённого operator.runtimeId/operationId и кода. Host сохраняет operator input; существующие ключи сохраняются. Это не заменяет RP15-019 pre-send evidence будущих MAIN/native операций.

## Code gate перед запуском

Helper — dev15_policy; host/controller/guard — координатор; независимое readonly code-review — dev15_review, без правок и запусков рецензента. CAP-REV-001 исправлен до запуска: измерение heap/index/TOAST использует фактическую schema trust, требует все7таблиц и неотрицательные числовые размеры. Новых блокеров для одного retained UNIT-прогона нет. Review gate с8SHA — ignored work/dev15-capacity-20261102/review-gate.json.

Node syntax checks и Python AST в прежнем pinned-образе без сети/данных PASS. Helper ограничен600с, host —620с, без автоматического продления/повышения ресурсов. API/ingress остановлены во время helper; DB512МиБ+tool256МиБ, прежние CPU/PIDs/read-only/internal network, без новых образов/программ/портов. Failure сохраняет частичный корпус, а не перезапускает опыт.

## Фактический результат

Первый запуск контроллера завершён FAIL **до исполнения helper**: json.load ждал EOF у контейнера с открытым stdin. Наблюдались PID1_WAIT=anon_pipe_read, около6МиБ RAM и отсутствие CPU-работы. Контейнер остановлен, исходные report/attempt/operator/raw output сохранены. Capacity-код не выдаётся за выполненный этим запуском.

Исправлены bounded readline и завершающий newline; отдельный frame-smoke PASS. Первое продолжение остановилось ещё в предварительном Start: остался выключенный helper, который compose down без runner override не удалил. Этот отказ TRUST_STOP_BEFORE_START сохранён отдельно в capacity-resume-start-refusal.json с SHA; исходный EOF FAIL не заменён. Проверенный старый stopped/read-only helper удалён по точному ID/labels/image, без force/-v и без volume. Добавлен явный cleanup собственного helper после Stop. Это две разные выявленные причины до теста, а не повтор одного неизменённого действия.

Обе правки прошли независимое readonly-ревью. Режим ResumePreHelper допускает один запуск только после actual read-only proof: точные UNIT/OID32563/schema0003/роль и нулевые записи всех7таблиц, неизменные MAIN/старый архив. Исходный HMAC attempt, FAIL и входы сохраняются; отдельная linked HMAC resume-001 квитанция включает их SHA, empty proof и новый настоящий container/runtime/operator. Уже существующая resume-квитанция закрывает дальнейший повтор. Никакого сброса данных или старой квитанции нет.

Контролируемый старт действительно выполнил helper, но завершился exit1/OOMfalse; stdout/stderr attach transport оказались пустыми, container logs не были захвачены до удаления. Точная причина exit1 не доказана; общий отчёт остался FAIL CAPACITY_HOST_FAILED. Это ограничение диагностики явно сохранено, время600с не выдаётся за установленную причину. Исходные артефакты и gate-1 остаются под отдельными именами.

Отдельный actual REPEATABLE READ, READ ONLY audit после отказа: UNIT/OID32563, Head965/epoch1/ACTIVE,964операции PENDING_DENY,4096адресов/refs,948tombstones,4credentials/1policy/0recovery. Logical13189661/reserve16772006; state-v2 c32fe0a2ae263babdced45da4536609ea1a4ad7f24c1f97c3ff1ecaa37c524ff. Фактический source30/5fbcb9d9… совпадает с policy, schema4fb746…; MAIN после аудита сохранила прежние9/2/4/3/1/2/policy0 и оба full SHA. Исходный snapshot не сбрасывался. Evidence — post-failure-unit-audit.json/post-failure-main.json в ignored work/dev15-capacity-20261102.

Подготовлено сохранное продолжение того же набора двумя фиксированными частями A/B: dev15-capacity-continuation-plan.md. Оно не bootstrap/повтор с пустойБД и не новаяpolicy, ресурсы прежние/по600с, только две части. Новый host сохраняет Docker logs до parse/cleanup; каждый новый полный signed lease приватен до исполнения, вход/результат/межфазныйcheckpoint связаны HMAC. Независимый code gate положительный.

### A — фактический PASS

Часть A прошла за388.672с:1000операций,4096адресов/refs,1024tombstones,500FINAL/500PENDING. Head1502/epoch1, logical26322077/reserved4097000. Реальный отказ по резерву:16772006+8194>16777216 при свободном общем logical бюджете; полный state до/после отказа одинаков. Затем UNKNOWN route0 и500завершений, отдельные отказы4097-йссылки и1025-йотметки до исчерпания числа операций подтверждены. Новая policy/epoch не создавались. Fresh UNIT-проверка не выдаётся за отдельный эксперимент учёта4старыхMAINопераций.

Helper cgroup peak109228032/268435456байт, OOM0/PIDpeak6; DB cgroup peak355041280/536870912, OOM0 — отдельный период жизни DB. Observed budget304652768байт, не hard quota. MAIN и старый архив до/после одинаковы, Stop/0running/helper removed/MAIN permit пустой. Отчёт phase-a-report.json, входной receipt и отдельный HMAC checkpoint capacity-phase-a-checkpoint.json сохранены. Независимое interim result-review положительное: SHA отчёта/receipt и checkpoint/finalAudit совпадают.

### B — фактический PASS

B прошла за280.881с после code gate и положительного result-review A. HMAC checkpoint и живое состояние совпали. Все1000операций FINAL_RESTRICTION,4096адресов/refs,1024tombstones,1policy/4credentials/0recovery. Head2002/epoch1, logical30419077/reserved0, полный v2 `116bb54a5d5d8cc5aa2ff6a4b593c51202aece6accff2421c47b525b9cc4c6b7`. Новая policy, смена epoch и bootstrap не выполнялись.

Prepare/UNKNOWN/terminal exact replay на полном count не изменили состояние. Отказ новой1001-йоперации подтверждён с честным одновременным пересечением count ceilings. SQL-снимок5120items/52страницы прочитан за2.775с, whole SHA `5933ad132f7586c38996084248dd7cd90b7bd2fd8b3c5b0ef80ed51ff4625315`. Это прямое SQL/service чтение: fixed TLS worker и30сdeadline ещё NOT RUN.

Helper B cgroup peak99020800/268435456байт, OOM0/PIDpeak6; DB B peak330985472/536870912, OOM0. Это отдельные периоды A/B, не единый максимум исходного неотчитавшегося процесса. Observed budget305217972байта (DB278863872, host17965492, logs8388608), не hard quota. Семь heap/index/TOAST частей и temp/WAL counters измерены; весь RP15-012 не объявляется PASS.

MAIN и старый архив B до/после идентичны; Stop/0running/helperremoved/MAINpermit{} подтверждены. Новые полные envelopes/inputs и container logs сохранены приватно до parse/cleanup, исходные FAIL/attempt/resume/данные не стёрты. Evidence: phase-a-report.json, phase-b-report.json, runtime capacity-phase-a/b.json и отдельный HMAC checkpoint A. Product source30 остаётся5fbcb9d9… с прежним131UNIT PASS; новый product code не добавлялся.

Независимое итоговое result-review выбранного набора положительное. RP15-008/009 приняты только в явно измеренной области fresh UNIT; отдельное включение4старыхMAINопераций в ceilings не проверялось. RP15-010 logical64МиБ в этом retained corpus NOT RUN (ранний131UNIT accounting-injection — отдельное свидетельство); RP15-011 TLS и незакрытые RP15-012/native/MAIN activation остаются впереди. Обычные Tests по-прежнему заблокированы: сохранённый corpus нельзя очищать без отдельно проверенной archive-процедуры.

Финальная сверка:30host/frozen исходников и config drift0; HMAC всех5сохранённых attempt/resume/phase/checkpoint квитанций корректны, SHA связей A совпадают. Actual owned containers0 (включая stopped), MAIN permit пустой. Read-only ACL132элементов закрытого каталога: Allow только владелец/SYSTEM, Windows PowerShell5.1. Итоговый ignored artifact — work/dev15-capacity-20261102/final-capacity-evidence.json. Все3предшествующих FAIL-отчёта и partial-corpus audit сохранены отдельно. Git push не выполнялся.

RP15-011 TLS30с/реальный временный readonly UNIT API, отдельная64МиБграница, весь RP15-012 и native RP15-013–019 не заменяются SQL-чтением или предыдущим131UNIT PASS. Свежий UNIT-корпус также не является отдельным экспериментом включения прежних4MAINопераций в count limits: это остаётся отдельной границей. MAIN/public site/VPS/DEV29/HTML/production не затрагиваются.
