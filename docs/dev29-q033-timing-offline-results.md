# Q033: offline timing analysis

Дата: 2026-11-05. Статус: результаты анализа существующих данных; предложение следующего диагностического этапа НЕ является разрешением на его реализацию или запуск. Source59, validation inputs и operator не изменены. Новый native/PG/SQL/actual mode не выполнялся.

Доказано сильное давление на post-image окно55s: последовательные call-интервалы после image до отказа заняли54,841.2334ms. Точный winning absolute deadline и причина host latency остаются UNPROVEN. Наблюдение ~172,214ms оставшейся Prepared validity не доказывает причинность отказа.

## Основание и безопасные данные

Исходный immutable audit docs/dev29-acl-module-cycle-result-review.md, RAW SHA256 a286967672d3427dded9eb5f73a7f0dbe73472ff062d745cb453702fda215166. Его вердикты результата/очистки не переоцениваются. Новое уточнение ниже supersedes только формулировку о чистой native длительности4.182s; исходный отчёт не переписан.

Назначенный nonsecret result.json RAW69f7ae6122ff59d8b872ac68473a5e6cf0ac4fa407e7ba80fa274f190beb02f5 и key-stage.json RAW1d84bda081284bba4c100e1a67b3763d02db8759d099efad406115c681921f74 прочитаны только для безопасной проекции. Все32 именованных receipt из hostEvidenceLedger проверены по exact raw hash. Подписывающие ключи не читались, ручная HMAC-проверка не заявляется. Нет чтений key/tag/host-key/plan TLS/privateFacts/rawACL или raw streams.

Полная безопасная проекция и четыре source pins: ../work/dev29-q033-timing-offline-001/safe-timing-projection.json. Числа/гипотезы: timing-analysis.json;11 arithmetic assertions PASS: calculation-checks.json. Это проверки арифметики, а не повтор product/static suites.

## Clock и policy

В frozen key-stage/runner.mjs qualify() создаёт t0=io.now(), total=t0+180000 и initial deadline=t0+90000. После успешного image: workDeadline=min(imageReturnNow+55000,total-35000). Initial90 не остаётся отдельным глобальным180/900 таймером после этого присваивания.

35s — резерв относительно total:30s cumulative timedCleanup плюс5s для последующих терминальных действий/отчёта. timedCleanup устанавливает min(prior,total-5000,cleanupStart+max(0,30000-cleanupSpent)); finally сначала задаёт prior=total-5000. Это не отдельный35s timeout Docker и не гарантия успешной очистки при медленном host.

call() передаёт min(currentDeadline,total,began+requested), затем actual stageCallAdapter дополнительно применяет caller stageEnd; safety также ограничивается lease.cleanupDeadline(10000). processCall() использует min(receivedDeadline,nativeStart+requested). Никакие ограничения этим анализом не увеличиваются. Конкретные imageReturnNow/end/selected parent не сохранены.

Stage now и controller receipt recordedMonoMs в actual adapters используют performance.now() того же Node process. Awaited stage calls последовательны; их интервалы можно суммировать без перекрытия. UTC — отдельное представление времени, в monotonic residual math не подставлялось. Inner32 timestamps — моменты создания receipts, а не32 командные длительности.

## Измеренная стадия

| Интервал | Ledger rows | ms |
|---|---:|---:|
| До/включая image |0–4|22,249.9231|
| После image до failed host(writer) |5–16|54,841.2334|
| Cleanup после отказа |17–25|10,208.4753|
| Все26 call-интервалов |0–25|87,299.6318|
| Stage elapsed | |90,473.8230|
| Stage elapsed минус26 call-интервалов | |3,174.1912|
| timedCleanup elapsed | |10,825.8034|
| Cleanup elapsed минус cleanup calls | |617.3281|

Все эти residual — одинаковая stage clock domain. Они включают работу вне call: metadata/ACL/FD checks, directory/bookkeeping/checks и переходы, без точной разбивки. Их нельзя назвать pure guard либо Docker overhead. Post-image call-sum оставляет не более158.7666ms от55s для остальных действий этого окна. Поэтому55s pressure подтверждён нижней границей, но точка reset/actual selected end не записана: точный winner не восстановлен. Общий elapsed90.474s меньше180s;30s cleanup не исчерпан по recorded cleanupElapsed. Total180 либо cleanup35 exhaustion этими числами не подтверждаются.

Failed row16 host(writer): ETIMEDOUT/SIGTERM, code null, completefalse, durationMs4182.4092. Важно: call() измеряет await io.call(), а stageCallAdapter выполняет pre verify → transport → post verify. Следовательно4.1824092s — весь этот adapter interval, НЕ доказанное pure native Docker время. capture.mjs действительно создаёт transient r.durationMs, но ledger формирует свой durationMs и не сериализует native duration отдельно. В saved row stats нет elapsedMs/durationMs/wallMs. Native timeout доказан категорией результата, его чистая длительность и доли guards не доказаны. Более быстрые safety cleanup calls0.970–1.406s против work calls4.3–5.7s совместимы с guard overhead, но различаются и workload/моментом; причинного сравнения нет.

## Что дают32 inner receipts

Все32 recordedMonoMs присутствуют и не убывают. Первый10,959.2956, последний231,118.2139; span220,158.9183ms относится лишь к этим receipt instants, не ко всему Run. budget-1 recorded90,274.1104 → key-stage185,659.2201 =95,385.1097ms. За вычетом stage elapsed это4,911.2867ms вне измеренного stage elapsed внутри данного window. В него входят caller/receipt boundaries; это не native/guard decomposition и не точный stage start. Остальные31 inter-receipt gaps сохранены в evidence; их нельзя суммировать как командные durations или прибавлять к stage elapsed повторно.

Нет serialized stage t0/image reset/cleanup transition anchors, pre/post guard spans, effective command/parent absolute ends, timeout arm/fire/native end и selected minimum name. Поэтому не различены stage55, per-call request, caller/lease parent и конкретная задержка внутри guard/transport/postguard. Cancellation отдельно не доказана. Prepared expiry не следует смешивать с physical stage timer; сохранённый отказ — KEY29_DEADLINE_OR_CANCEL после native timeout, не отдельная expiry diagnosis.

## Проверенные гипотезы и предел

TIM33-H01:172s Prepared remaining caused failure — UNPROVEN. TIM33-H02:55s work pressure — supported lower bound, winner UNPROVEN. TIM33-H03:total180 exhaustion — не подтверждено. TIM33-H04:35s cleanup exhaustion — не подтверждено; reserve35 не равен timedCleanup limit30. TIM33-H05:pure native inspect4.182s — UNPROVEN, прежнее wording уточнено. TIM33-H06:full content guards объясняют work latency — правдоподобно, но без separated spans UNPROVEN.

Reader/writer/cleanup/target SQL facts остаются результатом прежнего независимого audit, не переисполнены этим анализом. Ошибок чтений/инструментов в анализе0; NAV_NOT_FOUND — обычные данные навигации.

## Минимальное следующее предложение, отдельно согласовать

Сначала рассмотреть независимый reviewed nonSQL diagnostic с PUBLIC nonsecret fixture и фиксированным NOAUTHORITY_TIMING/v1 sidecar. Он не может создавать admission/opinion/HMAC authority, читать original key/corpus/oldDB, вызывать Run/Prepare или менять frozen candidate. Никаких cap/deadline увеличений и retry; при неполном proof честный UNPROVEN.

Необходимая телеметрия одного процесса: monotonic preguard begin/end; requested/current stage/total/caller ends и selected minimum до dispatch; capture/native begin/end/timeout arm/fire; postguard begin/end; metadata/directory spans вне call. Фиксированные op/role labels и числовые поля; без raw paths/Env/ACL/secret digests/keys. Все overhead измеряются внутри прежних caps, sidecar не продлевает срок и не даёт разрешений.

Вариант без Docker (dummy guard-only) проверит стоимость Windows ACL/FD пути, но не отделит inspect/network/engine latency и не квалифицирует полную стадию. Предпочтителен отдельный ограниченный nonSQL diagnostic на одном disposable nonsecret helper с прежним pinned profile/caps и реальным inspect: pre/post guard применяются к dummy данным через reviewed production-used primitives; независимые clocks/сокращённые toy guards не подменяют проверку. Только такой согласованный эксперимент с отдельными spans способен сравнить guard и native inspect на одинаковой операции. Его resources/one-shot/owned cleanup и полный dummy guard scope ещё нужно конкретизировать и независимо review ДО owner runtime approval. Ничего из этого сейчас не реализовано/не запущено; это не новый PG Run план и не обещание, что latency будущего Run станет предсказуемой.
