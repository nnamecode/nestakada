# DEV29-Q031 — интеграция квалифицированного ключа в P29-A

Статус: предложение для независимого ревью и согласования владельца. Сейчас разрешены только подготовка документов и файловое ревью. Новую COW, код, private inputs, Prepare, Docker, PostgreSQL и SQL до ответа Q031 не создавать и не запускать. Старый сайт, VPS, production и push исключены.

## Основание и границы

Q030 доказал способ: writer10001:GID999 создаёт отдельную копию10001:999/0640, reader999 успешно открывает её; byte equality проверяется внутри writer. Его копия удалена и не может стать входом будущего PGRun. Исходные metadata/ACL/access-time и старые source/history сохранены.

База новой COW — Q026 package2489595e6c86e7ea797af0e2276786ea46e7742a696412faa2bcbe592eba299e и approved D-493/Q026 review-window contract (proposal a8752b727613d8cea522affb37f90b8e716beb3ef3dd41a3fe57bd6f1b0c5c76). Источник staging — frozen Q030 package80755384e7c750fd8e2b4c11e970a271398203050ea7e92c2558588af1a9be20. Пакеты/результаты/checkpoints/late opinions Q025–Q030 и исходный source31 fingerprint1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e сохраняются.

Разрешение предлагается только на оставшийся ограниченный проход INIT/C/T: actual1000/1001 capacity, исходные139 suite без skip, outer rollback, MAIN/архивы/корпус неизменны, два последовательных независимых witnesses, RO-after и terminal owned0. Старые5+8 probes не повторять. Это не закрытие всех P29-A/native leases/crash/APP и не разрешение публикации продукта.

## Почему нужен новый контракт

В старом Prepare прямой SHA исходного TLS key попадает в public plan.tls; verify заново читает исходный key и сравнивает SHA. privateFacts содержит обычные per-run inputs, но не TLS key. Простое удаление plan.tls[key] потеряет существующий content-drift guard. Supervisor mountDigest относится к PGDATA mount, contentDigest — к PGDATA-файлам; tmpfs server.key туда не входит.

Рекомендуется private Prepare-time origin commitment: один новый защищённый binary tag32B, не public digest. Host-код bounded читает original при Prepare/verify, как старый SHA-guard, и после qualification также staged copy. Это новый явно согласуемый input/способ integrity. Tag не означает recovery и не разрешает повторный Run.

RAM-only tag, созданный только после qualification, переносил бы точку content binding с Prepare на Run. Этот вариант здесь не выбирается, чтобы не ослаблять прежний ранний guard. Public SHA ключа также не сохраняется. До Q031 новые host-reads/private tag не разрешены.

## Выбранный порядок

Вариант staging до Prepare оставляет копию на время ожидания репетиции/review/dispatch. Выбирается Prepare с будущими фиксированными путями, а создание копии — внутри единственного нового Run до INIT-admission.

1. Новые root/runId/public/private namespaces; старая COW не переписывается. Код и тесты — только после согласования этого плана.
2. До любых native: согласованные приёмочные сценарии, syntax/static/offline PASS, независимый code review exact package. Затем одна NOAUTHORITY репетиция шести gates: каждый≤80с, единый recorder≤490с, отдельный review результата. Не выдавать synthetic/historical факты за live admission.
3. Один Prepare создаёт обычные per-run credentials/host-key как раньше. Фиксирует immutable keyPolicyCore, bounded читает original и создаёт private origin tag32B по контракту ниже. Подписывает prepared plan ПОСЛЕДНИМ, после tag readback/FD/ACL/identity проверок. Prospective stage descriptor остаётся STAGE_PENDING: fixed paths/profiles/10001:999/0640/nlink1/size≤8192/schemas/lease. TLS certificate SHA сохраняется, key SHA/tag/tagHash публично не записываются. Plan содержит только metadata reference private tag и неизменен после публикации.
4. Существующий nonnative readiness≤10с с NOAUTHORITY result и независимым prepared/readiness/dispatch review. Копии в это время нет.
5. Новый Run сначала выполняет обычные bounded preflight, Original-before и budget checks, которым не нужен key bind. Затем до mint INIT/network/DB фиксирует stage intent и начало нового copy lease, создаёт свежую копию методом Q030. Нельзя создавать DB или её сеть до положительной qualification.
6. Writer UID10001:GID999: только original file RO + новый owned private directory RW; CAPdropALL, no chown/chgrp/new capabilities. Exclusive/nofollow creation, fchmod только нового файла, bounded source/readback≤8192 и bytesEqual внутри RAM. Никаких raw secret streams, repr или content digest в output/ledger/Git. Writer удаляется до reader create.
7. Reader UID999:GID999 получает RO точно те файлы, которые нужны DB: staged key, database-ca, bootstrap-password, migrator-password и четыре public source/config binds supervisor/bootstrap.hba/runtime.hba/bootstrap.sql. Пути закреплены Prepare, произвольные bind overrides запрещены. Для каждого regular/non-symlink и stat/open-RDONLY/fstat/close без чтения байтов. Staged key строго10001:999/0640/nlink1; остальные файлы должны фактически открываться под999. Недоступность — FAIL без ACL/UID/fallback-copy исправлений. Все inspect projections заранее проверяются на≤4096bytes, при необходимости фиксированно разделяются без потери проверок.
8. Run загружает expected origin tag в private RAM при старте и проверяет original на каждом прежнем verify. После reader и его удаления MAC staged copy обязан совпасть с ТЕМ ЖЕ Prepare-time tag. Затем подписывается runtime qualification receipt. Перед DB create/start и при каждом verify original и copy проверяются вместе с host-key continuity. Drift/expiry/lossRAM закрывают dependent action, но не доказуемую safety cleanup.
9. DB остаётся999:999, PGDATA/tmpfs/caps прежние. RO key bind указывает только на этот SAME qualified artifact. Существующий supervisor копирует его в новый /var/run/postgresql/server.key и chmod600 до INITDB; этот поток не меняется.
10. Все шесть actual reviews START/INIT/PAYLOAD-C/C/PAYLOAD-T/T сохраняются. START обязательно включает live qualification/credential/integrity proof. Только runner принимает мнение: HMAC/schema/pins/expiry/CLOSED/result/final monotonic check после proof-write и непосредственно перед action. Reviewer публикует собственный source напрямую; root не копирует JSON и не ставит подпись за него.
11. Сначала terminal inner Run: rollback/witnesses, DB/helpers/network removal, Original-after, budget/retained proofs, все create intents закрыты, same-engine owned0 и signed inner result. Только после этого разрешены identity-checked unlink staged copy, nonrecursive removal пустого owned directory и удаление нового private origin tag после последних integrity checks. Пустой inventory при unresolved createIntent недостаточен. При неполном proof — UNPROVEN, не удалять неподтверждённый объект и не повторять Run.
12. Финальный composite result связывает inner result и stage cleanup. После удаления state KEY_CLOSED, дальнейшие DB действия запрещены; допустимы только закрытие безопасных metadata/report операций. Неполный terminal proof не является PASS.

## Prepare-time integrity и signed schemas

Новый prepared schema KEYPG-PREPARED/v1 обязателен; legacy plan с просто удалённым key hash не принимается. Обычные privateFacts/host-key/per-run credential checks сохраняются. TLS origin tag — отдельный special private input, его нельзя пропускать через generic content-hash/export/retained mechanisms. Для него разрешена только signed reference metadata, не raw tag и не tagHash. Tag и host-key никогда не bind-mount в контейнеры.

Порядок без циклического hash: host-key → keyPolicyCore → original FD-read → tag → exclusive tag file → reference metadata → signed prepared plan. Immutable keyPolicyCore содержит run/package/owner/review/proposal pins, prospective source/stage/profile/size/lease policies и source core metadata/ACL. Он НЕ включает tag, tag reference metadata, final signature/prepared-plan hash или runtime qualification. CoreSha — hash этих публичных policy facts, не содержимого ключа.

Prepare через bounded descriptor-read≤8192 вычисляет HMAC-SHA256 существующим host-key: domain BOUND29/KEY-ORIGIN/v1 + runId + keyPolicyCoreSha + encodedLength + keyBytes, с однозначным length framing. Один domain/message используется и для original, и для staged copy. Original открывается только readonly; до bytes — non-reparse chain и FD identity/size/core/ACL checks, после — повторные checks. При drift plan не публикуется.

Ровно32 байта tag записываются exclusive в fixed newPRIV/tls-key-origin.tag; regular/nlink1/size32/nonreparse/ACL current-user+SYSTEM и FD identity/readback подтверждаются. Tag value не попадает в stdout/stderr/ledger/public plan/Git и не публикуется даже через свой hash. Это ЯВНО новый private persisted commitment, не скрытая RAM-only схема. Private tag не содержит plaintext TLS-key, но обрабатывается как чувствительный input.

Public plan.key содержит core/coreSha и originTagRef с fixed path/metadata/ACL, без содержимого. Существующий host-key guard проходит ДО tag checks. На старте Run protected tag читается descriptor-based ровно32 байта в private RAM; при последующих verify сверяются также его protected metadata и значение с cached expected tag. Source MAC проверяется НА КАЖДОМ прежнем verify, как старый original SHA-guard. После BOUND дополнительно сравнивается MAC staged copy с тем же expected Prepare tag. Это обнаруживает content drift даже при одинаковых size/mtime и сохраняет binding с момента Prepare. Buffers очищаются best effort, без обещания абсолютного RAM erasure.

KEYPG-QUAL-CORE/v1 включает run/package/source/proposal/prepared-plan pins, engine/endpoint, fixed profiles/path identifiers, originTagRef METADATA, source/core/ACL before/after, copy identity/metadata/ACL, writer/reader public evidence hashes, equality/open/credential-readability booleans и coordinator clock/lease fields. Whitelist metadata only, без key SHA/MAC/tag. Подписанный KEYPG-QUALIFIED/v1 добавляет originVerifiedSincePrepare/stageMatchesOriginCommitment и integrityMethod. Receipt append-only связан с prepared plan, но его одного недостаточно без live RAM state. START/review-facts обязаны проверить эту связь и актуальные guards.

| Runtime state | Stage и разрешённые действия |
| --- | --- |
| PENDING | TLS stage отсутствует; private origin tag уже valid. Только prospective/preflight и начало qualification; PG запрещён. |
| QUALIFYING | Только закреплённый owned partial/full stage текущего intent. Qualification и safety cleanup; PG запрещён. Unknown ownership не считается owned. |
| BOUND | Live receipt/RAM expected tag/host-key/original+copy integrity/metadata/lease обязательны; лишь тогда допустимы PG actions. |
| CLOSED | Stage и private tag удалены после terminal proof. PG запрещён, только terminal metadata/report. |
| UNPROVEN | Unknown ownership/intent/proof: нет dependent dispatch и небезопасного unlink; только доказуемые safety действия. |

Подписанный prospective STAGE_PENDING отображается в runtime PENDING, prepared plan не переписывается. После потери active attempt/RAM state нельзя загружать persisted tag как разрешение продолжить/resume; one-attempt и новые process/runId pins сохраняются. Safety cleanup проверяет code/authority/ownership/engine/intents, а не требует успешно пройти отказавший content guard. Наличие tag само по себе не admission.

Частичный Prepare имеет directory/tag intent и честный cleanup outcome; нет последнего signed plan — нет admission. Если identity не доказана, остаток не удаляется вслепую и отмечается UNPROVEN. Обычные старые per-run inputs и corpus не очищаются этим шагом.

Prepare→Run допускается только≤900с по signed issuedUtc/expiresUtc и существующим clock-sanity checks. Это НОВОЕ UTC validity window, не сравнение monotonic clocks разных процессов и не автоматический physical TTL файла. Backward/uncertain clock закрывает dispatch. Rehearsal/code review идут до Prepare, поэтому commitment в это ожидание не существует.

При отмене или expiry до Run предусмотрен один host-only CancelPrepared≤30с в рамках этого же ограниченного lifecycle: сначала append-only cancellation marker, блокирующий Run, затем identity/ownership-checked unlink нового tag. Никаких helper/PG/source-key writes. Остальные старые inputs сохраняются. После отказа/неизвестного исхода — UNPROVEN без слепого удаления. Без живого контроллера нельзя обещать автоматическую очистку tag; expired prepared plan не разрешает Run, остаток требует безопасной отмены. Наличие private commitment не добавляет recovery API.

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

Минимальные изменения новой COW: spec — prospective/qualified key bind и reader profile; controller — private origin commitment, tls Prepare/verify replacement, lease/qualification/cleanup/cancel; flow — qualification до INIT; review-facts — mandatory linked receipt; узкий adapter из Q030. SQL/workers/supervisor/capture/protocol функционально не менять; необходимые новые runId/pins отдельно доказать как разрешённую equivalence.

## Приёмка и будущий допуск

KEYPG-A01: после Prepare stage отсутствует, private tag32B valid и signed plan опубликован последним; public key digest/tag отсутствуют, ordinary privateFacts сохранены. A02: actual writer/reader/credential proofs на SAME artifact обязательны до INIT/DB. A03: FD host-read original/copy≤8192, tag-read32; original binding сохраняется от Prepare и проверяется на каждом verify, staged copy совпадает с тем же tag. A04: host-key/tag/RAM/receipt/clock drift закрывает PG, persisted tag не разрешает resume. A05: actual review120с/родительские deadlines не продляются. A06: copy lease3600/600 и prepared validity900 fail closed/no renew/retry. A07: R1/R2/sourcecore/ACL/atime/owned cleanup/old corpus сохранены; stage/tag удаляются только после holder/intents terminal proof. A08: bind defaults/profiles и projection budgets квалифицированы без weakening. A09: no secret output/invalid-stream-redaction, нет tag/tagHash/public key digest; special input исключён из generic exports. A10: code/rehearsal/prepared/readiness/dispatch/result reviews, onePrepare и atmostoneRun либо CancelPrepared; old5+8 не повторяются. A11: partial/unused/expired Prepare имеет cancellation/cleanup outcome, без обещания autoerase/crash recovery.

Будущий Q031 предлагается одним ответом явно согласовать private Prepare-time tag32B, bounded host-read original/staged copy без public digest, prepared900с/cancel и новый3600/600 copy lease, а также эту архитектуру и ограниченную реализацию/COW, приёмочные offline tests, независимый code review, один rehearsal, один Prepare/readiness либо безопасный CancelPrepared, независимые допуски, максимум один условный Run со свежим staging и INIT/C/T, rollback/сохранением корпуса/cleanup/result audit. До положительного независимого plan review вопрос владельцу не задавать. Пока нет ни такого review, ни ответа, код и ресурсы не трогать.
