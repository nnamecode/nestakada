# DEV-29: ожидание готовности Docker и один новый изолированный прогон

2026-11-04. **BOUND29-READINESS-001 / предложение DEV29-Q022. Не утверждено владельцем.** Пока разрешены только документы и файловое ревью. Код, новую копию, Prepare, Docker, SQL и Run до ответа не запускать. Этап 8 — разработка сайта, около 31%; DEV-29 — около 35%.

## Основание

Причина R021 независимо установлена: первый запрос списка контейнеров запустил остановленный Docker Engine linux/wsl. Движок стал готов через 19,09 секунды, а оба запроса завершились по таймауту около 9 секунд. [Отчёт](dev29-docker-timeout-cause.md), raw SHA256 e3e5150c9f00f0c659949de8ff9d811c058492ec5b7dc13a895be18cc9541ded. На Q016 без начальных журналов этот вывод не распространяется.

[Предварительное предложение](dev29-docker-readiness-proposal.md), текущий raw SHA256 26763c0fe41699fd4a6887ab0e8beaddc5911f0ae5e322a2ea1159c83568e5ef, прошло повторное ревью. Прежний hash 3a473 относится к версии без последнего абзаца о сохранении диагностического корпуса. Старые FAIL, once-квитанции и пакеты остаются неизменными. Observer со статусом NOT_RUNTIME_QUALIFIED не используется и повторно не проверяется.

## Единственное увеличение времени ожидания

Только **первый read-only inventory в preflight** получает requested45000мс вместо10000мс. С существующим резервом 1000мс на trace native timeout будет не более44000мс. Это один прежний запрос, без polling и повтора:

ps -aq --no-trunc --filter label=bound29.run=NEW_RUN

Endpoint, filter, формат, spawnSync, обработка вывода и assertions остаются прежними. Первый info уже имел requested45000мс; его лимит не увеличивается. Все остальные inventory, включая STOP и TERMINAL, сохраняют requested10000мс/native≤8999мс. Новый default для них запрещён.

## Общий бюджет только двух начальных чтений

В существующем коде **нет общего deadline всего preflight**. Helper90 не является таким ограничением. Предлагается добавить новый бюджет только для пары: fresh info → проверка expected engine и существующая квитанция → первый inventory.

1. Сохранить previousCommandDeadline.
2. Один раз установить jointDeadline=min(monotonicNow+90000, previousCommandDeadline??Infinity).
3. Выполнить info(requested45000), его проверку и запись квитанции, затем inventory(requested45000). Ошибка первого шага запрещает второй.
4. Обе native-команды используют существующий расчёт min(per-call45с, jointRemaining)-1000мс. Время info, обработки и квитанции уменьшает остаток для inventory. Между запросами deadline не обновляется. Более короткий внешний deadline не продлевается.
5. До успешного выхода проверить joint deadline. Превышение бюджета означает FAIL, даже если процесс вернул exit0. В finally восстановить previousCommandDeadline при успехе, исключении или отмене.

После восстановления остальные preflight/helper/cleanup работают под прежними ограничениями. Это новый 90-секундный бюджет **READINESS_ONLY**, а не всего preflight. Он не обещает, что любой холодный запуск успеет. OS scheduling и ожидание завершения spawnSync после SIGTERM могут дать overhead; превышение нельзя выдавать за соблюдённый deadline или обещать принудительное мгновенное прерывание ОС.

Readiness выполняется до original-before, budget и INIT admission; фазовые TTL ещё не идут. Успешное чтение списка подтверждает доступность нужного API, а info подтверждает identity. UI и прежние результаты не заменяют эти проверки. Затем обязательны все остальные image/volume/source/resource/original/phase gates. Ошибка, частичный/невалидный ответ или неожиданные owned resources запрещают продолжение; parsing и assertions inventory не ослабляются.

## Новая копия и сохранность

- Root: 651e6a45-b963-4703-8263-93aec7d41a67; prefix: nestakada-bound29-651e6a45.
- Public namespace: work/dev29-bounded-20261104-resume003/.
- Private namespace: work/dev15-20261102/private/bound29-651e6a45-real/.

Эти namespaces пока не созданы. Основа — принятый пакет36 из resume002, SHA256 74e315a4f413665aeb07201c39fe8bbc68a1aa5fed43f526a2f8bed043877aa9. Fresh identity, credentials, key и once создаёт штатный Prepare после code review; прежние секреты, результаты и admissions не копируются. Доступ — штатным require_escalated при необходимости; отказ означает STOP, без изменения ACL вслепую.

Разрешённая дельта: необходимые root/prefix/namespace/authority/path/marker и производные SQL hashes; дополнительно readiness-логика в controller.mjs и её acceptance tests в host-test.mjs. Допустим тестируемый helper в том же контроллере с injected clock/callbacks, но без runtime-флага отключения guard. Не менять бизнес-SQL, остальные assertions, failure trace, зависимости, source31, product protocol/consumer/tests и старый local_trust Tests guard. Source31 fingerprint: 1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e.

Immediate ancestry связывает R021: prepared plan raw66b398642a2394986d42f070f5e1b8088cf94c7671b8899d68db1ce1c0bcaf64, result rawc64150d91a85fbc96024b9a663ce67a7d010cab1fcafcadb73320f8c03ce7537, package74e315. Зафиксировать hashes cause report e3e515, readiness proposal26763 и этого утверждённого плана. Новые package hashes и весь code delta проходят независимое ревью.

Retained roots включают весь set предыдущего prepared plan, old bounded package, resume001, resume002, новые public/private roots и целиком work/dev29-docker-lifecycle-20261104-001/ с source/tests/summary/failed qualification. Nested roots дедуплицируются без потери корпуса. Старые подписанные результаты, trace, keys и историю не удалять ради прохождения budget. До и после считать volume allocation, все host roots, новые artifacts и reserve. Диагностический observer не импортировать и не использовать как proof.

## Приёмочные сценарии до реализации

- **R022-AC01 — холодный старт.** Быстрый info + inventory19.1с проходят под новым первым readiness budget; тот же сценарий с8999мс не проходит. Inventory сверх effective≤44с, error/nonzero/partial/invalid/owned conflict запрещает следующий шаг. Runtime/STOP/TERMINAL по-прежнему ограничены≤8999мс.
- **R022-AC02 — остаток времени.** Info/receipt, потратившие60с совместного бюджета90с, оставляют inventory native≤29с. Pre-trace расходы тоже учитываются. Нет reset между запросами; внешний deadline5с не расширяется до90с.
- **R022-AC03 — восстановление.** Previous deadline точно восстанавливается после успеха и каждой ошибки, включая storage/trace failure. После этого preflight helper сохраняет90с/work60/cleanup30, а STOP/TERMINAL — прежние9с. Новый лимит не просачивается в эти ветки.
- **R022-AC04 — обязательные допуски.** Readiness не продлевает TTL и не пропускает source/image/volume/memory/original/budget/role/marker/OID gates. INIT TTL выдаётся после preflight, RO-before и budget; INIT hard90 начинается в startDb. C/T fresh TTL и remaining850/490с неизменны.
- **R022-AC05 — once и сохранность.** Старые root/attempt/authority отклоняются, все retained roots учтены, source/старые packages/results неизменны. Нет retry, второго wake-query, посторонних ресурсов или удаления корпуса.
- **R022-AC06 — отказ.** Первая ошибка блокирует зависимые действия. Только оставшийся разрешённый bounded exact-owned cleanup и terminal same-engine proof; failed dispatched mutation не повторять. Empty terminal не переписывает aggregate FAIL/NOT PROVEN. Keys/raw logs/output не попадают в Git.

Проверяется реальный production path нового helper/параметра, а не отдельная имитация. Сначала syntax/static, затем clock/process acceptance и существующие offline-наборы последовательно после PASS, затем независимый code/delta review. Проверки новой копии ещё NOT_RUN; исторические86 не выдавать за новый результат. Не использовать live sleep19с для unit-проверок, не менять assertions/caps и не оживлять observer.

## Один условный lifecycle

Один ответ владельца должен охватить новую COW-копию и реализацию указанного изменения, проверки и code review, один Prepare, независимые prepared-result и dispatch reviews, максимум один условный Run INIT→C→T, rollback, dual witnesses и очистку. Технические reviews START/INIT/PAYLOAD-C/C/PAYLOAD-T/T≤120с обязательны по фактическим hashes, без preapproval. Они не требуют новых вопросов владельцу при неизменном scope. После ошибки/loop/drift нет разрешения на второй Run или расширение исправления.

Все прочие ограничения Q014/Q016/Q021 сохраняются. Exact raw hashes: Q014 bf9633c9afef1cad5a0b742b1c04ac6c66a39dd4c5e868e1598cfd75d4b2577b; Q016 3de6c955fa6436720b04ae3f09fbf78e03aaa966eb46a9b8a08121de07725e63; Q021 7353b8952d1db45981c8641b385c1ebb6bf7998a21307535acc85804060a2416. Исключения — только новые identity/authority bindings и явно описанные first-inventory45с/joint90с.

В частности сохраняются:

- pinned images/expected engine и endpoint; no pull/build/install/settings/WSL restart;
- исходный volume только в двух bounded RO volume-nocopy UID999 inspectors до/после, без SQL/запуска старого DB; новый DB только tmpfs PGDATA512MiB/run16/tmp32/shm16, memory=swap1GiB/CPU0.5/PIDs128;
- helper256MiB/CPU0.5/PIDs64/tmp32/shm16; rootfsRO/CAPdropALL/no-new-privileges/noports/loggingnone/restartno/internal network;
- VM available≥2GiB, persistent conservative budget<2GiB, new artifacts≤32MiB, streams≤1MiB, closed raw0/HMAC trace≤8KiB;
- INIT90с/TTL≤900с без renewal, C start remaining≥850с/T≥490с; host C620/T260/audit90 с30с на cleanup;
- C — настоящие1000/1001 с outer rollback, без cap lowering/bulk seed; T — исходные139 без skip/подмены, guarded new UNIT; два последовательных независимых witnesses, RO-after, terminal same-engine owned0 и fresh budget;
- старые5+8 probes не повторять; full P29-A/native leases/crash/APP не объявлять закрытыми заранее.

## Вопрос владельцу

**DEV29-Q022:** разрешить эту readiness-exception и весь один новый условный lifecycle с независимыми gates, rollback, сохранением корпуса и остановкой временного стенда? Старый сайт, VPS, production и push вне разрешения. До ответа новых packages/keys/Prepare/Docker/SQL/Run нет. Альтернатива — сохранить runtime на паузе.

После принятого результата — оценка фактической готовности P29-A, затем план P29-B/C/D/E. Общий этап9 начинается после завершения этапа8.
