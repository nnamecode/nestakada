# DEV-29: ограниченный временный PostgreSQL для завершения P29-A

2026-11-03. **BOUND29-PLAN-001 / предложение DEV29-Q014. Не утверждено; реализация и запуск этого профиля не начинались.** Основания D-431/D-432, COMP29-BOUND-001. Q013 остаётся согласованным, но его C/T закрыты обязательным физическим gate. Это отдельное архитектурное изменение, не ослабление того gate.

## Решение проблемы

У имеющегося named volume нет заданного в compose файлового предела, а max_wal_size не является hard limit. Конечные оценки роста WAL/TOAST/индексов и cleanup для Q013 не получены. Не продолжать тот же поиск без новых предпосылок и не заменять доказательство историческим PASS.

Предлагается **отдельный одноразовый кластер в ограниченном tmpfs**, без подключения старого тома к новому DB-контейнеру. Source31, прежний runner, attempts, signed CPA history, исходный кластер и корпуса сохраняются. Новый guard разрешает работу только с новой синтетической UNIT. Старый `local_trust Tests` остаётся закрыт.

Tmpfs — файловая система в памяти с заданным размером; данные исчезнут при удалении/остановке контейнера. Её расход входит в cgroup memory. Это прямой предел вместимости PGDATA, включая WAL, а не предположение о скорости WAL. Успех1000/139 в этом размере **ещё не доказан**: ENOSPC/OOM/timeout означают FAIL и остановку, без автоматического увеличения размера/повтора. [Официальная документация Docker tmpfs](https://docs.docker.com/engine/storage/tmpfs/).

Альтернативы: продолжить полное физическое доказательство текущего Q013 или создать новый persistent volume с проверенной filesystem quota. Первое пока не дало derivation, второе требует дополнительных дисковых/системных настроек. Tmpfs не требует установки ПО/изменения Docker Desktop/WSL/ACL и не меняет старый том. Сейчас никакие настройки не меняются.

## Точный предлагаемый профиль

Те же уже закреплённые PG18.6/Python/Django5.2.18 images и зависимости, без pull/build/install. Отдельные names/labels/run/namespace и одна новая internal network без host ports; не API/ingress/APP. Одновременно один DB и один helper. Inspector работает только до/после них.

Root run `1e23c654-5baf-4b5e-a7b4-6235b1289c0a`, public namespace `work/dev29-bounded-20261103/`, exact owned prefix `nestakada-bound29-1e23c654`. Раздельные signed once scopes `BOUND29-INIT`, `BOUND29-CAPACITY`, `BOUND29-SUITE`; новый RO intent на каждый из двух inspectors. INIT имеет hard90с/remaining≥110с, C/T — таблицу сроков ниже. Успех предыдущего gate и независимое ревью обязательны до следующего допуска. Не переиспользовать root run/attempt для автоматического повтора.

| Ресурс | Предложение |
|---|---|
| DB | memory=memory-swap=1073741824bytes, CPU0,5, PIDs128 |
| DB writable filesystems | `/var/lib/postgresql`512MiB, `/var/run/postgresql`16MiB, `/tmp`32MiB, `/dev/shm`16MiB |
| Helper/inspector | memory=memory-swap256MiB, CPU0,5, PIDs64; `/tmp`32MiB, `/dev/shm`16MiB |
| Остальное | UID/GID999 DB/inspector; helper10001; rootfsRO; CAPdropALL; no-new-privileges; logging driver none; restart=no |
| Source/config/secrets | Только exact readonly binds; никакого writable host bind/Docker socket/host root/PGDATA другого кластера |

Пиковый заявленный RAM cap DB+helper —1,25GiB вместо прежних768MiB. Сумма управляемых writable tmpfs DB+helper —624MiB; не выдавать только512MiB PGDATA за весь расход. Docker `memory-swap=memory` отключает доступ контейнера к swap при поддержке kernel/cgroup; отсутствие поддержки — отказ до init. До DB up свежая проверка доступной памяти Linux VM должна показать≥2GiB MemAvailable; иначе STOP без изменения Docker/WSL memory settings. OOM killer не отключать и приоритет процесса не повышать. Это не обещание отсутствия paging Windows/VM или неизменности физического Docker VHD. [Официальные ограничения памяти/swap](https://docs.docker.com/engine/containers/resource_constraints/).

Image объявляет `VOLUME /var/lib/postgresql`; tmpfs обязан закрыть **родительский путь целиком**. Mount только вложенного PGDATA запрещён: может остаться anonymous volume. Guard проверяет rendered config, inspect всех mounts/HostConfig.Tmpfs/ShmSize, отсутствие anonymous/named volumes и writable bind, rootfs/UID/caps/security/logdriver/resources, фактические mountinfo/statfs/size/тип и доступные writable пути. Служебные `/proc`/`sys`/`dev` и Docker-generated hosts/resolv files проверяются по закрытому allowlist; это не разрешение альтернативного пути для данных PG. Любое неизвестное writable data destination — DENY.

Фиксированный PGDATA `/var/lib/postgresql/18/docker`, data_directory внутри того же tmpfs. Никаких `--waldir`/POSTGRES_INITDB_WALDIR/внешних tablespaces/ссылок pg_wal/pg_tblspc за envelope. Проверка путей до сервера и через закрытый readonly catalogue/SHOW после старта; archive/restore commands, replication slots/backup/посторонние writers выключены. Не принимать пользовательские SQL/команды/параметры. Не выдавать superuser worker. Новая bootstrap роль только для закрытой инициализации/аудита этого кластера.

## Сохранение корпуса и бюджет

Прежний DB не запускается. До новой инициализации — отдельный readonly inspector исходного тома по exact volume identity/labels, image/command/user/caps. Том монтируется RO на `/var/lib/postgresql`, перекрывая image VOLUME; никакой entrypoint PostgreSQL. Только bounded pg_controldata/du и streaming file manifest+SHA, без SQL/копирования дампа/изменения файлов. Symlink/out-of-root/device/неожиданная структура — DENY; ключи/персональные данные/содержимое файлов в отчёт не выводятся. Манефест только в защищённом ignored storage, в Git — общий digest. Inspector удаляется до init.

После удаления нового стенда такой же RO inspector подтверждает тот же полный file-content manifest/ownership/modes и clean cluster control. Atime не является доказательством данных и не сравнивается; не заявлять fresh logical SQL hashes закрытых архивов. Если read-only инструмент/права не позволяют это выполнить — STOP, не менять ACL вслепую. Original volume никогда не подключается к новому DB или worker, запрещено открывать архивы или переписывать старые receipts.

Сохраняется прежний **persistent budget2GiB**: fresh allocation исходного тома + все прежние/new accepted host roots +16MiB reserve. Новые public/private артефакты имеют общий enforced byte cap32MiB (включая raw outputs/новые секреты/манифесты), каждый stream≤1MiB. Старые inputs immutable; no daemon logs через loggingnone. Init/worker/inspector outputs учитываются до записи; cap/parse/root drift — FAIL/Stop. Существующие image layers/глобальное состояние Docker/Windows не объявляются частью нового жёсткого лимита.

Дополнительно до запуска консервативно зарезервировать **B+1GiB DB+256MiB helper+32MiB новых artifacts+16MiB reserve<2GiB**, где B — fresh old volume+полные старые roots без двойного reserve. Так tmpfs/его metadata внутри cgroup уже покрыты полным RAM cap и не требуют исходной недоказанной формулы464MiB. Не считать tmpfs дважды внутри RAM cap. Это консервативный project-owned envelope, не физическая квота всего Docker VM/VHD. Если свежая B не помещается — NOT_RUN, без удаления корпуса/истории или роста лимита.

## Инициализация и новые полномочия

Отдельный новый ignored namespace и защищённые новые ephemeral passwords/identity/receipts, без копии содержимого оригинальных БД. Старые пароли postgres/migrator не передаются новому worker. TLS материалы допустимо использовать только readonly из ранее защищённого private storage, без публикации/копирования в public inputs. Перед секретами — проверка точного intent/source/targets/readonly mounts; недоступные права означают STOP, не ACL repair.

Новый контроллер проходит independent code/QA review до любых Docker create/init/SQL. Bootstrap нового кластера — явная отдельная фаза: пользователь999, initdb в новом tmpfs; temporary postmaster только Unix socket, `listen_addresses=''`; bootstrap HBA только `local all postgres peer`, остальные local/TCP reject. Ни worker, ни helper в этой фазе не создаются. Закрытый проверенный bootstrap SQL создаёт только новые estakada_trust/test_estakada_trust и служебные роли/права по минимальному списку. Никакого импорта original rows/архивов. Init/migration SQL разрешается только новому кластеру, всё DDL записывается в reviewed source allowlist.

Затем clean stop **postmaster внутри живого контейнера**, а не stop контейнера (иначе tmpfs исчезнет). Runtime postmaster запускается с immutable runtime HBA: local reject, non-TLS reject v4/v6, TLS migrator только новая UNIT, TLS bootstrap только новый MAIN, catch-all reject. Temporary peer не остаётся fallback. До test writes фактически проверить HBA rules/no errors, active-family role×DB×TLS negative matrix, новую identity/TLS/roles/marker/source/schema и отсутствие других sessions. Неисполненный IPv6 runtime не выдавать за PASS.

**Доверенный PID1 и переход без потери tmpfs (BOUND29-REV-001):** entrypoint нового DB — только `/bin/sh /tools/bound-db-supervisor.sh`, immutable readonly source с SHA в reviewed package/INIT intent. Он работает UID999/CAPdropALL/no-new-privileges и остаётся PID1, не `exec postgres` при bootstrap. Закрытый автомат: `INITDB → BOOTSTRAP_SOCKET_ONLY → CLEAN_CHILD_STOP → RUNTIME_TLS → FINAL_CLEAN_STOP`; нет команд от пользователя/worker/stdin, Docker socket/exec authority или повторного init на ошибке. Exact initdb/psql/postgres argv, два readonly HBA inputs и список допустимых metadata-команд фиксируются в code review. Использовать обычный postgres entrypoint вместо этого supervisor запрещено.

Каждый postmaster запускается **прямым дочерним foreground-процессом supervisor** с записанным PID; не daemon/detached `pg_ctl start`, чтобы supervisor мог корректно wait/reap child. Bootstrap child слушает только собственный Unix socket; закрытый psql payload завершается до остановки child. Supervisor отправляет SIGINT только отслеженному child, ждёт clean exit0≤10с и подтверждает clean pg_controldata. Затем, сохраняя себя/контейнер живым, запускает новый direct child с exact runtime argv/HBA. До/после перехода проверяются прежние mount ID/statfs/tmpfs size/PGDATA path и init nonce/system identifier; после clean bootstrap stop создаётся PGDATA content digest, который повторно проверяется непосредственно перед runtime child start. Не требовать равенства файлов до/после законных SQL/checkpoint: runtime сохраняет system identity, а изменяемые контрольные файлы получают новый честный digest.

Host до admission C проверяет тот же full container ID, State.Running, StartedAt, RestartCount0, mounts/resources/source hash и закрытые transition records. Локальные проверки supervisor не заменяют эту host-проверку. Unexpected PID1/child exit (даже0 вне ожидаемого clean stop), Docker stop/restart, orphan child, mount/system-ID/nonce drift, timeout/неполный record — terminal FAIL без C/T/нового init.

TERM/INT/HUP supervisor означают только окончательную остановку: прекратить переходы/новый SQL, forward SIGINT отслеженному postmaster, wait/reap≤10с, зафиксировать final clean control/digest **до выхода PID1**; при неизвестном состоянии — FAIL. Host final Stop≤15с, затем только exact owned full-ID kill/remove при незавершённом child. Никакого detach/оставления orphan. Child-stop при переходе не является Docker stop; final PID1 exit/container removal уничтожают tmpfs намеренно. Отсутствующий final clean record не становится success после удаления контейнера. Injected negatives обязательны: accidental container stop/restart между стадиями, сигнал/timeout при bootstrap/переходе/runtime, orphan/unexpected exit, подмена HBA/fallback и несовпадение control/mount/instance facts.

UNIT проходит разрешённые миграции0001–0003 только через новый receipt-guarded initializer, с target check **до первого DDL**. Новый MAIN имеет только отдельный синтетический baseline, не оригинальный Head13/b42. Старые OID16384/52766/16387/32563 нельзя присваивать новым DB или нормализовать как прежние. Новые IDs/marker/server system identifier фиксируются в собственных signed receipts. CPA/source/namespace proofs остаются preservation ancestry, не authority изменения старого кластера.

## Приёмочные проверки до и после реализации

BOUND29-AC01: offline negative/injected-IO сценарии до runtime — неверные mounts/image/PGDATA/ссылки/HBA/identity/chain/source/caps/swap, чужой DB/сессия, excess output/host budget, timeout/ENOSPC/OOM/partial result/unknown backend/cleanup; ни один не dispatch SQL до target gate. Квоту проверять mountinfo/statfs/resource facts, не физическим заполнением диска.

BOUND29-AC02: сохранность старого корпуса/истории/source/runner, pre/post RO file proof и persistent budget, отсутствие подключения original volume к новому DB. Старые5+8 probes не повторять.

BOUND29-AC03: фаза C — настоящие1000 production prepare, HIDDEN/LIVE_NO_SET, default caps,2pending+998completed, отказ1001 именно COUNT_CAP_REACHED/exact state equality, prepare/terminal replay/completion, outer rollback+reconnect independent witness. Без bulk seed/count injection/cap lowering. Native leases/crash durability не заявляются.

BOUND29-AC04: только после C PASS/rollback/witness/independent result-review — T, exact139 original Django tests (131+8), no skip/error/failure, guarded existing-new-UNIT setup **до DDL**, без nodb/MAIN/создания/удаления DB тестовым runner. Настоящие fixtures/concurrency/HTTPS/flush/migration0003→0002→0003; исходные тела/assertions/order не изменяются. UNIT migration IDs/sequence после T честно новый baseline, не setval repair.

BOUND29-AC05: отдельные signed once admissions фаз/source/package/HBA/input digests, без timestamp renewal/retry. C600/620с, admission remaining≥730с; T240/260с≥370с, TTL≤900с. Init/каждый RO inspector/audit≤90с, отдельные bounded start gates. C session-only idle timeout30с/statement5с/lock1с; T исходные session options. Observability/Stop остаются, но вместо ACK safety derivation464MiB используется independently validated tmpfs/cgroup envelope; это явная замена architecture Q013, не удаление проверки из старого кода. OOM/ENOSPC не safety PASS и не functional PASS; только фиксированный FAIL+cleanup без autogrow/retry.

После каждого send независимый readonly witness новой UNIT/нового MAIN. После T/FAIL — exact owned DB/helper/network stop/remove, tmpfs уничтожен, оригинальный том сохранён,0owned containers/networks/helpers, public/private evidence retained within cap, independent final review. Чужие ресурсы/процессы не удалять. Не переживать restart/crash durable testing: исчезновение tmpfs — ожидаемое ограничение, отдельные P29-B/C/D/E остаются впереди.

Только фактический C/T PASS позволяет готовить исходную матрицу P29-A/A29-001–008 для отдельного независимого принятия; новый синтетический стенд не является восстановлением/проверкой production. DEV-29 остаётся около35%, этап8 «Разработка сайта» около31%; не начислять готовность за предложение. Общий этап9 следует после этапа8.

**DEV29-Q014:** разрешить конкретную смену локального тестового профиля: новый ephemeral PG18 кластер в tmpfs512MiB, DB RAM1GiB + один helper256MiB без swap/портов, закрытый bootstrap новых synthetic DB/ролей/миграций, старый том только для двух RO inspectors, и обе последовательные C/T проверки с code/start/payload/result reviews и обязательным Stop по этому плану? Старый сайт/VPS/production/push, изменение старых DB/runner/ACL/корпуса и новые packages/images вне разрешения. До ответа владельца — предложение/ревью, не реализация этого нового профиля.
