# DEV-29: настоящая квота и полный guarded-набор P29-A

2026-11-03. **Предложение COMPLETE29-PLAN-001 для DEV29-Q013; реализация/запуск не разрешены этим документом.** Основания D-429, A29-001–008/P29-A05, принятые13 service cases и существующий receipt-guarded candidate runner WB15-004. Старый сайт/VPS не трогать.

## Что мешает завершению

Настоящая граница1000/1001 и свежий полный набор139 test-методов ещё не исполнены. Count/accounting injection из Q012 не заменяют эти свидетельства. Старый `tools/local_trust.mjs Tests` намеренно закрыт при capacity-attempt.json; удалять/переименовывать/подменять этот guard/attempt нельзя.

В проекте уже есть принятый `tools/test-trust-candidate-regressions.mjs`: successor guard проверяет signed CPA archive chain перед стандартным Django DiscoverRunner. Его старый запуск не повторять: он закреплён за source30/изменением consumer и историческим MAIN, а сейчас source31/MAIN Head13. Подтверждённая старая длительность131 теста160,534с, execution168526ms — ориентир бюджета, не PASS текущих139. Исторический capacity-профиль имел helper600с/host620с; это тоже не новый допуск.

## Рекомендуемый вариант без нового кластера

Использовать существующую disposable UNIT `test_estakada_trust`/OID52766/точный marker, предварительно пустую по7 journal tables с3 миграциями. Архивные корпусы остаются в прежних закрытых БД16387/32563. Не создавать/переименовывать/удалять БД, роли, тома или архивы. Исходные runner/compose/HBA/runtime manifest/env/credentials/старые пакеты не менять.

Новый конечный профиль в ignored `work/dev29-publication-20261103/pg-check/complete/` адаптирует **уже принятый receipt-guarded способ**, а не запускает raw `manage.py test` мимо защиты. Исторический local_trust Tests остаётся закрыт. Новый guard обязан отказать до первого fixture/setup/DDL без всех подписанных archival proofs и точного свежего UNIT/MAIN/archive baseline. Наличие receipt-файла само по себе недостаточно.

Новый root run `c5a2f73f-401e-4945-bb0a-88d4d17df43c`; отдельные fixed phase scopes `P29A-COMPLETE-CAPACITY-ADMISSION` и `P29A-COMPLETE-SUITE-ADMISSION`. Source31 остаётся byte-exact. Все старые source/receipts/locks/attempts/полные namespace manifests входят в preservation-only ancestry, не переисполняются/не переподписываются. Новые transient artifacts и phase receipts append-only.

Альтернатива — новый одноразовый PostgreSQL-кластер/том и новый набор ролей/секретов; он не нужен при проверенном guard текущей пустой UNIT и требует больше ресурсов/полномочий. Здесь он **не предлагается**. Ещё один малый mock/probe-пакет также не предлагается: он не закрывает остаток.

## Дополнительная защита MAIN на уровне PostgreSQL

Для этого временного DB-only запуска предлагается **новый readonly HBA overlay**, без правки `environment/trust/pg_hba.conf`. Только существующая temporary DB/internal network/volume/images; в resolved compose меняется один readonly bind HBA на новый immutable профиль. Rootfs/UID/caps/volumes/порты/остальные binds сохраняются. До up обязательно проверить rendered config и exact mount/content SHA, не полагаться на merge по предположению.

Новый HBA допускает TLS `trust_migrator` только в `test_estakada_trust`; подключения этой роли к MAIN/архивам/postgres/любому другому имени запрещены **самим сервером**. Не-TLS запрещён. Worker не получает bootstrap password, Docker socket, PGDATA или произвольные mounts. Это защищает MAIN и при новом thread/raw DB connection, независимо от Django hooks. PGAPPNAME связывает все допустимые worker connections с phase/run; чужая сессия до запуска — STOP, не kill.

**Точная first-match HBA-политика**, до запуска byte-checked в rendered mount и после старта сверенная с pg_hba_file_rules (включая отсутствие parse errors):

```text
local   all                  all              reject
hostnossl all                all  0.0.0.0/0   reject
hostnossl all                all  ::/0        reject
hostssl test_estakada_trust  trust_migrator 0.0.0.0/0 scram-sha-256
hostssl test_estakada_trust  trust_migrator ::/0      scram-sha-256
hostssl estakada_trust       postgres        0.0.0.0/0 scram-sha-256
hostssl estakada_trust       postgres        ::/0      scram-sha-256
hostssl all                 all             0.0.0.0/0 reject
hostssl all                 all             ::/0      reject
```

Никакого broad `hostssl all all ... scram/trust` или local trust fallback. Bootstrap на уровне сервера тоже может только MAIN: UNIT/postgres/оба архива/прочие DB запрещены, несмотря на superuser-флаг. До test write — negative role×DB×TLS matrix для обеих ролей, targets UNIT/MAIN/postgres/оба архива/неизвестное имя, TLS/non-TLS; допускаются только две указанные TLS пары. Проверка проводится по реально активному address family, правила второго family проверяются структурно без заявления неисполненного IPv6 runtime. Отсутствие соединения/SQL на запрещённых парах обязательно; закрытые архивы не открывать ради негативного теста. DB-only readiness не должна требовать authenticated local SQL; если существующая healthcheck несовместима с запретом local — STOP до мутации, не возвращать trust fallback.

Отдельному **readonly аудиторскому helper** разрешается существующий bootstrap credential только для fixed MAIN SELECT-аудита. Поскольку HBA закрывает MAIN для migrator, прежний MAIN-аудит этой ролью здесь невозможен. Аудитор: фиксированный MAIN target, TLS, read-only transaction/statement timeout, closed SELECT-only source, hash/count output, без тестовой fixture/DDL/DML/activation. UNIT audit остаётся migrator. Bootstrap credential не передаётся worker и не используется для изменения ACL/ролей/архивов. Только один helper одновременно; аудитор и mutating worker не работают вместе.

Это существующая привилегированная учётная запись postgres, **не новая роль с урезанными правами**. Readonly здесь обеспечивают PostgreSQL read-only transaction и проверенный closed SQL/source allowlist; отдельно проверяется transaction_read_only=on. SQL/targets от пользователя не принимаются, backend-control/COPY PROGRAM/произвольные функции не допускаются. Такое чтение требует явного Q013; до него credential для нового MAIN-аудита не используется.

До чтения/монтирования privileged secret проверяются closed audit intent, fixed MAIN target/ожидаемый OID16384/role, source/plan/HBA/DB+network IDs и readonly capabilities; повторная сверка — перед dispatch и после результата. После TLS connect, до чтения предметных строк, single-statement identity SELECT проверяет фактические database/OID/owner/current_user/session_user/TLS, затем transaction_read_only=on на том же соединении. Любое несовпадение закрывает соединение, не запускает другой target. Далее только literal single-statement SELECT allowlist, параметры не выбирают SQL/таблицу/БД. Auditing MAIN как postgres отмечается явно и не нормализует ничего, кроме ожидаемой смены audit actor.

Доступ к закрытым архивам не открывать даже временно. Guard проверяет HMAC/nonce/source/intent links исторических CPA receipts и актуальные OID/owner/marker/ALLOW_CONNECTIONS/CONNECT ACL catalogue facts. Их исторический raw content SHA — signed prior proof, **не новое чтение содержимого закрытой БД**. Сохранность обеспечивается неизменностью identities/closed ACL, запретом worker connections вне UNIT и запретом database/role/catalog mutations; fresh content rehash не выдумывается. MAIN fresh row/state hashes сравниваются с принятой точкой, нормализация касается только явно изменившейся audit actor identity, не OID/owner/marker/данных/TLS/schema.

## Фаза C — реальные1000 публикаций и отказ1001

Отдельный Python helper, exact UNIT/role/OID/marker/TLS/schema/source, single writer connection, advisory/table locks. `BoundedFixture` только builder; synthetic UNIT policy/lease/resource facts остаются явно service-only, native admission не заявляется. Внешняя atomic с безусловным rollback/reconnect; no runner/flush/migrate/reset/DDL/commit в этой фазе.

Через production `S.mutate` выполнить **ровно1000 успешных prepare**, чередуя HIDDEN/LIVE_NO_SET, уникальные target/objectId/operationId. Никаких bulk_create/raw INSERT seeds/count patches/понижения B.CAPS/padding. Две первые операции (по одной policy) оставить pending; остальные998 завершить production report. Реальный SQL count=1000, обе policy представлены; route/reference count1000<4096, tombstones0<1024, logical+reserved<64MiB, completion reserve в пределах действующего cap — так отказ1001 изолирован от других ceilings.

Сохранить полный v2/state/count/charge/reserve/receipt digest до попытки1001. Ожидается COUNT_CAP_REACHED и exact state equality. При этом exact prepare replay обеих pending операций доступен; их committed report и terminal replay завершаются без новой Operation/потери истории, с прежними receipts. Затем1000 terminal operations/точные policy counts и неизменность реплеев. Только после доказательства — forced outer rollback, reconnect/independent after-witness; UNIT все rows/schema/sequence равны pre-capacity baseline, MAIN/архивы сохранны.

Result: real1000CapacityProved=true допускается **только** при этих фактах; countMocked=false/bulkSeed=false/nativeLeaseProved=false/durabilityProved=false. Это реальная PostgreSQL count boundary в одной outer transaction, не доказательство crash durability1000 committed операций. Физическое заполнение диска не выполняется. Не повторять старый PG29-007/старый Run.

## Фаза T — полный набор139 на source31

Допускается только после PASS фазы C, подписанного rollback/preservation result и независимого review. Новый phase admission/expiry, без переноса старого container ID/timestamp. Оба архива закрыты, UNIT снова пуста, MAIN прежний. Проверяются CPA chain, attempt history, exact OID/marker/schema/role/TLS и source перед первым setup/write. При любой неизвестной сохранности полный runner остаётся закрыт.

Запускается **стандартный Django DiscoverRunner** с исходными телами всех139 методов/fixtures, `keepdb=True`, без исключения/skip/подмены asserts и без старого source30 runner. Suite discovery обязана дать exact139 unique test IDs на source31 (131 старый+8 publication). Это фактическая проверка discovery, не присвоение PASS статическому AST. testsRun=139, failures/errors/skips/expectedFailures/unexpectedSuccesses=0; иначе FAIL, counts не корректировать ради успеха.

Guarded setup повторно проверяет target **до super/setup/первого DDL**, а не только после него как в историческом коде. Новый setup/reuse-existing hook должен работать только с уже подтверждённой UNIT и не создавать/drop БД; точную совместимость с закреплённым Django доказать offline/injected-IO до runtime. HBA запрещает nodb/MAIN соединения worker, поэтому инфраструктура подготовки не должна зависеть от них. Lifecycle тестов/fixtures остаётся настоящим; если это невозможно без изменения тестовых тел — STOP до SQL и новое предложение.

Разрешены flush/COMMIT/схемные migration fixture **только в UNIT**, включая реальный AdmissionPolicyMigrationTests0003→0002→0003 и обычные TransactionTestCase teardowns. Это осознанно отличается от прежних rollback probes и требует Q013. Соединения всех threads фазы проверяются по реальному DB identity/role/TLS; HBA остаётся независимым fence. Запрещены CREATE/DROP/ALTER DATABASE, role/system/ACL изменения, расширения для cross-DB доступа и подключения вне UNIT. Тесты concurrency/HTTPS, входящие в исходный suite, не заменяются mocks/одним соединением.

После success: UNIT сохраняет тот же OID/marker/owner, source-compatible schema0003,3migration names и пустые7journal tables. **Не обещать прежний raw SHA/sequence миграций**: настоящая migration fixture может их законно изменить. Новый фактический baseline/sequence фиксируется, setval/ручное восстановление не делать; старые receipts остаются историей и не становятся текущим допуском. MAIN/архивы/корпус/permissions неизменны. После failure/timeout partial UNIT не flush/repair вручную; guard остаётся закрыт, сохраняются evidence и Stop.

## Ресурсы, deadlines и gates

Существующие pinned images/зависимости, DB512MiB/.5CPU/PIDs128 + один helper256MiB/.5CPU/PIDs64, read-only rootfs/readonly source/secrets/tmpfs/логи/output limits без увеличения RAM/CPU/порта. Перед стартом fresh RO PG18 clean shutdown/initialized volume, zero exact-name+label inventory, resolved config/HBA/source/private input SHA и budget; затем independent actual start review/DB-only up без init/API/pull/build.

Для закрытия остатка предлагаются **отдельные явно согласуемые временные профили**:

| Фаза | Helper hard limit | Host hard limit | Minimum admission remaining перед send |
|---|---:|---:|---:|
| C,1000/1001 |600с|620с|730с =620+90witness+20cleanup|
| T,139 tests |240с|260с|370с =260+90witness+20cleanup|
| Audit/metadata/witness |прежний bounded профиль|≤90с|cleanup-only после send допустим|

В фазе C session-only connect_timeout5с/statement_timeout5с/lock_timeout1с/idle_in_transaction_session_timeout30с: последний позволяет ограниченное ожидание resource ACK внутри outer transaction вместо исходных3с. Ролевые/DB defaults не менять, после close это не сохраняется. Фаза T оставляет исходные session options тестируемого source; не менять их ради PASS. Эти временные исключения также входят в Q013, не предоставлены прежним90с профилем.

Каждый phase admission TTL≤15мин, свой once lock/result/provenance/payload review. Без timestamp rewriting/автопродления/подмены нового профиля старым90с Run. Новый owner-ответ Q013 сразу охватывает обе условные фазы и независимые gates без промежуточных дополнительных вопросов при успехе. Неуспех C запрещает T. Если оставшегося времени недостаточно — STOP до send, без автоматического повторного допуска.

Общий предел **L=2147483648bytes** сохраняется. Измеряемый **currentTotal T=allocatedDBBytes+acceptedHostRootsBytes+16777216**; accepted roots — полный прежний перечень из принятого final budget, включая новые complete/public/private artifact roots, без исключения старой истории/логов. Перед C требуется **T+1073741824<L**:1GiB headroom входит в2GiB, не повышает лимит. Exact abort threshold **A=1610612736bytes (1,5GiB)**; при T≥A никакой новой мутации/ACK. Оставшиеся512MiB — safety margin, не разрешение продолжать до2GiB.

Supervisor измеряет allocated DB фиксированным readonly `du` в own DB container и все accepted host roots не реже **раз в5с**, timeout каждого collector≤3с. Parse failure/отрицательное число/изменившийся root set/возраст sample>5с — fail-closed без ACK и Stop. Output/log≤1MiB/helper, общий unmeasured собственный host artifact growth≤16MiB enforced byte counters; новые неподписанные входы не принимаются. Docker exec здесь только metadata, не дополнительный helper и не SQL.

Оба измерения выполняются независимо/параллельно с **общим wall-time budget≤3с на комплект**, не по3с последовательно. Проверка свежести и запись ACK≤1с после комплекта; суммарно<5с worker ACK wait. Если платформа не выдерживает эту границу в preflight/реальном мониторинге — DENY/STOP, не увеличение timeout; explicit DENY/EOF также не разрешают следующий SQL step.

Фаза C использует bounded progress/ACK protocol поверх exclusive owned Docker stdio: initial/readline framing≤1MiB, progress/ACK frame≤4096bytes с run/phase/sequence/plan/source и digest предыдущего frame. Worker не выполняет более **4 mutating service calls** после свежего ACK и ставит barrier также перед следующей мутацией при elapsed≥10с. Пока ACK нет, SQL mutations не исполняются; ожидание ACK≤5с, затем exception/forced rollback/close. Host не выдаёт ACK без свежих DB/host samples и T<A. Если progress отсутствует>15с — Stop; host Stop dispatch≤2с после threshold/stale detection, graceful≤1с затем собственный full-ID kill при необходимости. Если Docker control unavailable, worker ACK timeout всё равно прекращает выдачу новых SQL. Cleanup witness≤90с выполняется после прекращения/закрытия backend; неизвестная очистка остаётся FAIL, не success.

**Safety inequality до разрешения C:** максимум роста одного fixed service step≤32MiB, максимум4 steps=128MiB; pending DB/WAL/buffer/предвыделение≤256MiB; host growth≤16MiB; Stop/rollback cleanup growth≤64MiB. Итого **464MiB<512MiB margin**. Это требуемые admission bounds, не уже измеренные факты: code/QA должен обосновать их фиксированными DTO (prepare≤4096B/phase receipt≤65536B, одна policy), write-set/индексами/TOAST и текущими server facts. Перед C readonly проверяются block_size, wal_segment_size, shared_buffers64MiB, wal_buffers≤16MiB, max_wal_size128MiB/min32MiB, отсутствие retention/replication slots/backup/архивирования/чужих writers. **max_wal_size — мягкий ориентир, из него нельзя автоматически выводить256MiB hard bound**. Если конечный pending-growth bound не доказан, ACK не выдаётся и C остаётся NOT_RUN; нельзя повышать margin/cap или скрывать неизвестность.

Для T независимый code gate должен аналогично показать, что фиксированные139 исходных test bodies не могут увеличить disk>128MiB между5с samples; shared pending/host/cleanup bounds те же. Исторический PASS не является таким доказательством. Исходные тестовые тела/порядок/assertions/фикстуры не изменять ради resource checkpoints; если это невозможно совместить с bounded наблюдением, T остаётся NOT_RUN. Supervisor проходит реальные injected-IO negatives для stale/parse/timeout/burst/отсутствующего ACK/late stop/частичного output/unknown backend до любых SQL. Никакого физического заполнения диска, автоматического retry или пересогласования лимитов в коде.

Сначала code/QA review: HBA/credential separation, before-setup and all-connection target fences, wrong chain/marker/source/DB/foreign sessions, no count injection/bulk seed, full139 discovery/outcomes, signal/timeout/partial output/size budget/cleanup, once/non-retry/expiry. Зависимые steps — строго после успеха предыдущего, один исполнитель-координатор. Public inputs архивируются до правки bound docs; raw suite logs только в protected ignored private storage, в Git/чат только summaries/hashes. Secrets/passwords не копируются в public archive.

После каждой фазы fresh independent MAIN/UNIT/archive witness, resource/source/guard/ancestry recheck и независимый result-review. После завершения — exact own DB/network Stop/remove, volume retained, PG18 clean shutdown, final budget,0containers/0networks/helpers/permit{}. Новый HBA/пакет/evidence остаются immutable; старые env/manifest/HBA/runner/attempts не переписываются. Чужие процессы/сессии/ресурсы не удалять.

## Готовность и вопрос владельцу

COMP29-AC01: CPA successor guard и server MAIN fence доказаны до first write; AC02: real1000/1001/replay/default caps без mock/bulk с rollback; AC03: source31 exact139 original tests без skipped/failure; AC04: MAIN/archives/корпус/source/permissions сохранны, UNIT lifecycle changes явно учтены; AC05: budgets/time/HMAC/once/Stop и independent review. Сейчас всё NOT_RUN, подготовлен только план.

При успехе этих условий готовится итоговая матрица A29-001–008 и отдельное независимое принятие **P29-A в его исходной TRUST/unit-regression области**. APP publication/cohort/startup/restore/EDGE/native durability PUB29-019–022 относятся к последующим P29-B/C/D/E; их NOT_RUN не превращать в PASS и не расширять ими бесконечно этот участок. DEV-29 целиком не закрывается: текущий этап8 около31%, DEV-29 около35%, общий этап9 после всей разработки.

**DEV29-Q013:** согласовать ли подготовку и выполнение обеих фаз C/T с reviews/Stop по этому плану: readonly HBA overlay (migrator только UNIT, bootstrap только MAIN), отдельный SELECT-only MAIN auditor с существующим privileged credential, настоящий1000/1001 во внешнем rollback с600/620с и session idle timeout30с, полный guarded139 suite с240/260с и разрешённым lifecycle/migration только UNIT? Disk cap2GiB/abort1,5GiB/safety/ACK gates обязательны; при недоказанных bounds соответствующая фаза NOT_RUN. Без новых ролей/БД/томов/пакетов, без изменения исходного runner/корпуса/ACL, без открытия архивов, без MAIN writer/APP/старого сайта/VPS/production/push. Это новый точный профиль полномочий/времени, прежние Q009–Q012 его не разрешают. До ответа — только предложение и независимое review, код/контейнеры/SQL не начинать.
