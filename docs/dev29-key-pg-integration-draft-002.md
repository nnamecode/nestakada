# DEV29-Q031 — интеграция квалифицированного ключа в P29-A

Статус: предложение для независимого ревью и согласования владельца. Сейчас разрешены только подготовка документов и файловое ревью. Новую COW, код, private inputs, Prepare, Docker, PostgreSQL и SQL до ответа Q031 не создавать и не запускать. Старый сайт, VPS, production и push исключены.

## Основание и границы

Q030 доказал способ: writer10001:GID999 создаёт отдельную копию10001:999/0640, reader999 успешно открывает её; byte equality проверяется внутри writer. Его копия удалена и не может стать входом будущего PGRun. Исходные metadata/ACL/access-time и старые source/history сохранены.

База новой COW — Q026 package2489595e6c86e7ea797af0e2276786ea46e7742a696412faa2bcbe592eba299e и approved D-493/Q026 review-window contract (proposal a8752b727613d8cea522affb37f90b8e716beb3ef3dd41a3fe57bd6f1b0c5c76). Источник staging — frozen Q030 package80755384e7c750fd8e2b4c11e970a271398203050ea7e92c2558588af1a9be20. Пакеты/результаты/checkpoints/late opinions Q025–Q030 и исходный source31 fingerprint1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e сохраняются.

Разрешение предлагается только на оставшийся ограниченный проход INIT/C/T: actual1000/1001 capacity, исходные139 suite без skip, outer rollback, MAIN/архивы/корпус неизменны, два последовательных независимых witnesses, RO-after и terminal owned0. Старые5+8 probes не повторять. Это не закрытие всех P29-A/native leases/crash/APP и не разрешение публикации продукта.

## Почему нужен новый контракт

В старом Prepare прямой SHA исходного TLS key попадает в public plan.tls; verify заново читает исходный key и сравнивает SHA. privateFacts содержит обычные per-run inputs, но не TLS key. Простое удаление plan.tls[key] потеряет существующий content-drift guard. Supervisor mountDigest относится к PGDATA mount, contentDigest — к PGDATA-файлам; tmpfs server.key туда не входит.

Рекомендуется runtime-only keyed integrity в RAM нового Run. Альтернатива — persistent private commitment для восстановления — меняет digest persistence и recovery-контракт, здесь не выбирается. До Q031 ограниченное чтение staged key host-кодом не разрешено.

## Выбранный порядок

Вариант staging до Prepare оставляет копию на время ожидания репетиции/review/dispatch. Выбирается Prepare с будущими фиксированными путями, а создание копии — внутри единственного нового Run до INIT-admission.

1. Новые root/runId/public/private namespaces; старая COW не переписывается. Код и тесты — только после согласования этого плана.
2. До любых native: согласованные приёмочные сценарии, syntax/static/offline PASS, независимый code review exact package. Затем одна NOAUTHORITY репетиция шести gates: каждый≤80с, единый recorder≤490с, отдельный review результата. Не выдавать synthetic/historical факты за live admission.
3. Один Prepare создаёт обычные per-run credentials/host-key как раньше. Подписывает prospective key descriptor со state STAGE_PENDING: fixed source/stage paths, profiles, expected10001:999/0640/nlink1/size≤8192, schemas, source metadata/ACL policy и lease policy. TLS certificate SHA остаётся; TLS-key SHA или RAM-tag в public plan не помещаются. Prepared plan неизменен после записи.
4. Существующий nonnative readiness≤10с с NOAUTHORITY result и независимым prepared/readiness/dispatch review. Копии в это время нет.
5. Новый Run сначала выполняет обычные bounded preflight, Original-before и budget checks, которым не нужен key bind. Затем до mint INIT/network/DB фиксирует stage intent и начало нового copy lease, создаёт свежую копию методом Q030. Нельзя создавать DB или её сеть до положительной qualification.
6. Writer UID10001:GID999: только original file RO + новый owned private directory RW; CAPdropALL, no chown/chgrp/new capabilities. Exclusive/nofollow creation, fchmod только нового файла, bounded source/readback≤8192 и bytesEqual внутри RAM. Никаких raw secret streams, repr или content digest в output/ledger/Git. Writer удаляется до reader create.
7. Reader UID999:GID999 получает RO точно те файлы, которые нужны DB: staged key, database-ca, bootstrap-password, migrator-password и четыре public source/config binds supervisor/bootstrap.hba/runtime.hba/bootstrap.sql. Пути закреплены Prepare, произвольные bind overrides запрещены. Для каждого regular/non-symlink и stat/open-RDONLY/fstat/close без чтения байтов. Staged key строго10001:999/0640/nlink1; остальные файлы должны фактически открываться под999. Недоступность — FAIL без ACL/UID/fallback-copy исправлений. Все inspect projections заранее проверяются на≤4096bytes, при необходимости фиксированно разделяются без потери проверок.
8. После reader и его удаления Run создаёт runtime-only integrity binding и подписывает отдельный qualification receipt. Перед DB create/start и при каждом прежнем verify проверяется новый binding. Любой drift/истечение/потеря RAM state закрывает dependent action.
9. DB остаётся999:999, PGDATA/tmpfs/caps прежние. RO key bind указывает только на этот SAME qualified artifact. Существующий supervisor копирует его в новый /var/run/postgresql/server.key и chmod600 до INITDB; этот поток не меняется.
10. Все шесть actual reviews START/INIT/PAYLOAD-C/C/PAYLOAD-T/T сохраняются. START обязательно включает live qualification/credential/integrity proof. Только runner принимает мнение: HMAC/schema/pins/expiry/CLOSED/result/final monotonic check после proof-write и непосредственно перед action. Reviewer публикует собственный source напрямую; root не копирует JSON и не ставит подпись за него.
11. Сначала terminal inner Run: rollback/witnesses, DB/helpers/network removal, Original-after, budget/retained proofs, все create intents закрыты, same-engine owned0 и signed inner result. Только после этого разрешён identity-checked unlink staged copy и nonrecursive removal пустого owned directory. Пустой inventory при unresolved createIntent недостаточен. При неполном proof — UNPROVEN, не удалять неподтверждённый объект и не повторять Run.
12. Финальный composite result связывает inner result и stage cleanup. После удаления state KEY_CLOSED, дальнейшие DB действия запрещены; допустимы только закрытие безопасных metadata/report операций. Неполный terminal proof не является PASS.

## Runtime integrity и signed schemas

Новый prepared schema KEYPG-PREPARED/v1 обязателен; legacy plan с удалённым key hash не принимается автоматически. Prospective descriptor сам по себе не разрешает DB. Обычные privateFacts/per-run input checks сохраняются; stage описывается отдельной state machine PENDING → QUALIFYING → BOUND → CLOSED. Failure/unknown intent → UNPROVEN. RAM loss запрещает продолжение/resume, но не блокирует разрешённую безопасную cleanup.

Qualification core KEYPG-QUAL-CORE/v1 содержит run/package/source/proposal/prepared-plan pins, engine/endpoint, fixed profile/path identifiers, source core metadata/ACL before/after, copy identity/metadata/ACL, writer/reader public evidence hashes, bytesEqual/open booleans, credential-readability records и coordinator clock/lease fields. Только whitelist metadata; ни key SHA/MAC, ни raw Env, ни key bytes. CoreSha — hash публичных facts, не содержимого ключа.

После qualification reviewed host-код однократно читает только staged copy через descriptor, bounded≤8192. До любых байтов: non-reparse path checks и fstat exact prepared/runtime host identity; после чтения — повторные identity/size/core/ACL checks. Исходный key host-код не читает. Вычисляется HMAC существующим private host-key с domain BOUND29/STAGE-INTEGRITY/v1, runId, coreSha и staged bytes, с однозначным length framing. Tag остаётся только в RAM, не сериализуется и не попадает в логи даже через свой hash. Буфер bytes очищается best effort; гарантированное стирание всех RAM-копий не обещается.

Подписанный KEYPG-QUALIFIED/v1 receipt включает core/coreSha и integrityMethod/initialCheckPassed, но НЕ сам tag. Он append-only связан с prepared plan. START/review-facts обязательно проверяют этот receipt и актуальный live state. При verify: metadata/identity/ACL + bounded HMAC comparison в RAM, затем final parent/lease monotonic check. Это сохраняет проверку содержимого даже при изменении байтов без изменения размера/mtime. Private tag и secret bytes никогда не передаются reviewer.

Граница защиты меняется явно: в новом Prepare содержимое исходного key ещё НЕ закреплено, проверяются только его core metadata/ACL. Первое связывание bytes происходит в Run при writer byte-equality qualification; runtime content-drift guard защищает staged artifact с этого момента. Это не эквивалент прежнего original-key SHA от момента Prepare. Metadata не доказывает отсутствие same-size/same-mtime изменения исходных bytes до qualification. Агент не пишет original и writer bind остаётся RO; внешнее изменение содержимого без metadata этим ранним этапом не обнаруживается. Владелец должен отдельно согласовать отложенную точку content binding. Если требуется прежняя точка Prepare-content commitment, этот вариант не утверждать: нужен отдельный private commitment/его policy review, без автоматического fallback.

Состояния verify разделены явно:

| Runtime state | Stage и допустимые действия |
| --- | --- |
| PENDING | Stage отсутствует. Только prospective/preflight и начало qualification; PG запрещён. |
| QUALIFYING | Допускается только закреплённый owned partial/full stage текущего intent. Только qualification и безопасная cleanup; PG запрещён. Неизвестная ownership не превращается в owned. |
| BOUND | Требуются live receipt, RAM integrity, metadata/ACL/identity и lease; лишь тогда допустимы PG actions. |
| CLOSED | Stage отсутствует после доказанного terminal cleanup. PG запрещён; только terminal metadata/report. |
| UNPROVEN | Неопределённые ownership/intent/proof: нет dependent dispatch и небезопасного unlink. Разрешены только доказуемые safety действия. |

Prospective prepared state STAGE_PENDING отображается в runtime PENDING, но prepared plan не переписывается. Отсутствие stage не является новым разрешением создать DB.

## Время: старые ограничения и новый copy lease

900с — TTL КАЖДОГО admission, не общий срок DB. READY ограничен90с; после READY старый PID1 проверяет liveness, автономного900-секундного таймера нет. Последующая жизнь ограничивается фазами/Stop. Этот план не выдаёт новый coordinator timer за native crash/lease qualification.

Все старые admission minimum/expiry, INIT90/C620/T260, review120с и shorter-parent wins остаются. Старого общего30с terminal-cleanup cap нет:30с входит в отдельные helper budgets. Их reserve не суммируется второй раз.

Предлагается НОВЫЙ невозобновляемый copy-phase lease3600с на одном monotonic clock нового Run, начиная непосредственно перед первым mkdir stage. workEnd=t0+3000с; последние600с зарезервированы на terminal cleanup, Original-after, inventory и удаление stage. Это требует отдельного согласования и может отказать медленному пути, который удовлетворил бы отдельным старым лимитам.

| Перечисленные source-grounded участки | Сумма потолков |
| --- | ---: |
| Stage qualification | 180с |
| Readiness pair + preflight helper | 90+90с |
| Original before/after captures | 180с |
| DB READY | 90с |
| INIT MAIN/matrix/worker/UNIT | 360с |
| C worker + witnesses | 620+180с |
| T worker + witnesses | 260+180с |
| Шесть actual reviews | 720с |
| Всего перечисленного | 2950с |

Это НЕ общий доказанный максимум: create/inspect/engine/host IO/final inventory не все включены; failure witnesses могут добавить180с. Предварительные preflight/Original-before идут до начала copy lease. Нельзя объявлять3600с гарантией прохождения all-max пути.

Для каждого dispatch в frozen operation graph задаются operationBudget и reserve следующей обязательной dependency; неизвестный budget запрещает dispatch. Проверяются remainingWork≥operationBudget+nextDependencyReserve И старый admissionRemaining≥его прежний minimum. Это не обещание полного suffix success: при нехватке остатка новый action не начинается, запускается safety cleanup. Cleanup operations обрезаются remainingLease и своими старыми bounds. Все waits/reviews/storage checks включены, monotonic origins не переносятся; никакого renewal/retry. До и после opaque host IO проверяются clocks; мгновенное прерывание блокирующего IO не обещается.

Reserve600с — ограничение допустимых cleanup действий, не обещание успешного удаления при любой неисправности. При unresolved intent/неподтверждённом прекращении holder после срока — UNPROVEN и защищённая копия может остаться до отдельно согласованного восстановления. После смерти coordinator автоматическое удаление или DB stop не гарантируются. Эти crash/recovery-сценарии остаются за пределами этого прохода.

## Ресурсы и область изменений

Те же pinned PG/Python images, endpoint/engine, pullnever, noports/lognone/rootfsRO/capdropALL/no-new-privileges. DB1GiB/CPU0.5/PIDs128, PGDATA tmpfs512MiB/run16MiB/tmp32MiB/shm16MiB; старые PG helpers256MiB/CPU0.5/PIDs64. Stage helpers128MiB/CPU0.25/PIDs32/shm16MiB/networknone, последовательно без overlap с DB. Добавленные mount profiles строго whitelist; source original RO, только новый stage-dir RW writer, reader/DB file RO. Без новых зависимостей, сервисов, настроек Docker/WSL, capabilities или изменения original ACL.

VMavailable≥2GiB, conservative persistent<2GiB, новые artifacts≤32MiB, старые streams≤1MiB/trace≤8KiB; stage streams≤4096bytes. Original volume только два bounded RO UID999/volume-nocopy inspectors, старую DB не запускать. MAIN/архивы и corpus/late history/checkpoints включаются в retained snapshot.

Минимальные изменения новой COW: spec — prospective/qualified key bind и reader profile; controller — tls Prepare/verify replacement, RAM binding, lease/qualification/cleanup; flow — qualification до INIT; review-facts — mandatory linked receipt; узкий adapter из Q030. SQL/workers/supervisor/capture/protocol функционально не менять; необходимые новые runId/pins отдельно доказать как разрешённую equivalence.

## Приёмка и будущий допуск

KEYPG-A01: после Prepare stage отсутствует и ключевой digest не опубликован; ordinary privateFacts сохранены. A02: actual writer/reader/credential proofs на SAME artifact обязательны до INIT/DB. A03: bound FD host-read≤8192 только copy, integrity tag толькоRAM; одинаковый-size/mtime content drift обнаруживается. A04: lossRAM/receipt/pins/clock отвергает PG и не допускает resume. A05: реальные review gates120с/родительские лимиты не продляются. A06: новые lease/dependency budgets fail closed, нет renew/retry. A07: R1/R2/sourcecore/ACL/atime/owned cleanup и old corpus сохранены; stage удаляется лишь после всех holders/intents. A08: readonly bind type/default/propagation variants квалифицированы без weakening. A09: no-secret-output/invalid-stream-redaction, нет tag/digest serialization. A10: отдельные prepared/readiness/rehearsal/code/result reviews, onePrepare/atmostoneRun; раньше пройденные5+8 не повторяются.

Будущий Q031 предлагается одним ответом явно согласовать отложенное content binding, staged-key RAM-read/integrity и новый3600/600 copy lease, а также эту архитектуру и ограниченную реализацию/COW, приёмочные offline tests, независимый code review, один rehearsal, один Prepare/readiness, независимые допуски, максимум один условный Run со свежим staging и INIT/C/T, rollback/сохранением корпуса/cleanup/result audit. До положительного независимого plan review вопрос владельцу не задавать. Пока нет ни такого review, ни ответа, код и ресурсы не трогать.
