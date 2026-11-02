# DEV-15 — полный снимок журнала и стартовый клиент

Последующий D-378 аудит уточнил общий остаток DEV-15:4локальных блока и ориентир85–90% вместо предварительных95%. [Аудит](dev15-completion-audit.md), [независимое ревью](dev15-completion-review.md). Этот snapshot-срез и его97PASS/3TLSфазы остаются пройденными; DEV-29 не начат.

2026-11-02, D-377. Срез snapshot/startup проверен локально. Текущий этап8, DEV-15 в работе, около95%; этап8 около28% (8/29 основных DEV завершены локально).

## Область

Сценарии SS15-001–009 написаны до кода, независимое precode review положительное. Reader-only manifest с полным count/digest и bounded клиент детализируют принятый snapshot-протокол D-374; отдельного архитектурного согласования не требуется. Программы/образы/сети/тома/caps не добавлялись; MAIN с4операциями/head9/epoch2 и прежний архив60/15360 сохраняются. Старый сайт/VPS не затрагиваются.

Реализованы потоковый manifest под Head lock; строгая проверка всех страниц/head/counts/order/UUID/target bytes/page и whole digest; immutable canonical snapshot bytes. Сетевой запрос выполняет короткоживущий процесс того же Python в существующем контейнере256МиБ/PID64. Parent ограничивает абсолютный timeout6с/remaining30с и kill/reap, что охватывает DNS/TLS/slow drip. Ключ только через stdin; фиксированный child argv/origin/path и bounded output. При ошибке частичный результат не возвращается, бесконечного повтора нет.

Startup проверяет точный восстановленный cohort против свежего полного снимка. SnapshotReady не выдаётся за право публикации: htmlAdmission/workflowComplete всегда false. Реальные APP/main receipt/reconciliation/HTML gate не подключались. Потеря непрерывности не использует прежний ready-флаг. Обычный исправный Django не подключается к этому испытанию.

## Проверки и точка продолжения

После положительного code/QA gate выполнены **97 unit/integration PASS85.901с** (62baseline+35новых), source23files `3319caa3d158a3c75876cd05fe91a48f3716464604f15f255a70a618aa7d43fc`, run `3b18050c-e550-49cb-b70b-f1fd76b9ea26`. Прежний архив проверен до unit, запись disabled; затем Stop PASS. Actual PG+endpoint читали151routes+101tombstones тремя страницами, с независимым полным SHA и immutable результатом. Реальный child писал/flush byte каждые50мс; тот же production communicate/kill/reap завершил его по timeout0.3с, тест подтвердил elapsed<2с и reaped child. Порча/обрезка/дубли/перестановка/подмена hash/head/generation/старый cohort/ошибка сети остаются closed. Утечек секретов в argv/ошибках и произвольного worker command нет.

Unit budget295397234B; DBmemory.peak287252480B при512МиБ, OOM/oom_kill0. Рецензент независимо прочитал actual97, сверил все36source/config rows в conditional native gate — drift0. Новая проверка не переиспользует прежние62 PASS46.410с на source19c9….

Не утверждается прохождение всех600страниц/64МиБ вRAM256МиБ/за30с: это пределы отказа, полная MAX/capacity остаётся будущей проверкой. При deadline рабочее I/O прерывается, затем выполняется ограниченный kill/reap; пройденный тест отдельно ограничивает общую длительность этой cleanup-границы.

**Native PASS:3 фазы/7 экземпляров групп (3+1+3)/19 реальных HTTPS-запросов.** Read: fixedworker получил полный manifest→page→head, актуальный cohort дал только snapshotReady, настоящий прежний cohort из D-376 initialHead отклонён. Blocked: собственный ingress остановлен, реальная TLS-недоступность дала закрытый startup, один запрос без повтора. Restart: API действительно перезапущен с другим PID, ingress возвращён, свежий процесс клиента повторил полный TLS-проход/проверки. Ни сохранённый ready, ни старый head не дали HTML authority.

MAIN во всех фазах: та же incarnation, generation9/epoch2/ACTIVE, тот же head digest `b93c45da…`, полный persistent state digest `64dd0a52dc0732cbc004d09b21d87f17a82d08a0cd885fa9d57f0656bf47f2c4`; snapshot digest до/после restart `7b4cc7e863f99e314f9f442c8543ac4ced6618f9d8a733795a674eb761f4b9d6`. Counts3routes+1tombstone, все pending/terminal запреты сохранены; новых операций/записи/seed/reset нет. Нативная MAIN намеренно маленькая; три страницы151/101 проверены вUNIT через настоящую PG+endpoint, не выдаются за native multipage.

После front Stop прежний архив проверен тем же подписанным receipt/helper: OID16387,60operations/15360policies,head121 и rowsSHA289e7b0f… совпали полностью; подключения к архиву закрыты, UNIT OID32563 сохранён, noDROP/rename/flush. Внутренний и независимый внешний finallyStop PASS. General/test writes disabled, active permit остаётся `{}`; старый write one-shot не запускался.

Наблюдаемый native budget296711706B, DBdata281522176B, плановый предел2ГиБ без утверждения hard quota. Последние cgroup memory.peak: API98492416B, DB28241920B, ingress9105408B, OOM counters0; это последние периоды после restart, не whole-run максимум. Согласованные caps896МиБ/1.25CPU/PIDs/readonly binds/internal networks/no host ports сохранены. Проверка отсутствия сырых машинных secrets в текущих service logs пройдена.

Evidence: work/dev15-snapshot-20261102/native-report.json, resource-evidence.json, native-review-gate.json; unit-result/unit-budget с UUID3b18050c… в прежнем runtime. Итоговое независимое result/doc review — dev15-snapshot-review.md.

Полный DEV-15 не объявляется завершённым: перед переходом к DEV-29 нужна сверка оставшихся локальных условий write admission/квот/контрактов интеграции. Настоящие APP/gate/main restore/HTML serving, физический ARC-10/внешнее размещение/восстановление самой TRUST, полный MAX/PERF и production остаются отдельными воротами. Проверка snapshotReady не заменяет ни один из них.

Сохранность до изменений:71исходник/документ скопированы и сверены в work/dev15-snapshot-20261102/before/hashes.json. Ключи/private plans/история и DBvolume сохраняются, не попадают в Git; push не выполняется. Native byte/count/deadline caps — ограничения первого клиента, не обещание чтения предельных600страниц за30с. Полная capacity/performance и физическая свежесть/собственное восстановление внешней TRUST остаются отдельными.
