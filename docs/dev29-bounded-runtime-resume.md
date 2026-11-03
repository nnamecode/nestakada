# DEV-29: новое однократное возобновление после раннего preflight FAIL

2026-11-04. **BOUND29-RUNTIME-RESUME-001 / проект DEV29-Q016. Не утверждено.** [Фактический отказ и независимое ревью](dev29-bounded-runtime-results.md). Старый Run не повторялся; его package/plan/receipts остаются неизменными.

## Причина отдельного согласования

Q014 разрешил конкретный root run `1e23c654-5baf-4b5e-a7b4-6235b1289c0a`. В согласованном плане прямо записано: «Не переиспользовать root run/attempt для автоматического повтора». Единственный Run завершился FAIL/PREFLIGHT, хотя INIT/C/T admissions ещё не выдавались. Доступность Docker сейчас подтверждена; историческая причина неизвестна из-за отсутствия failure trace. Поэтому не переименовывать прежний отказ в успешный preflight и не обходить wx/once guards.

## Конкретное предложение

Разрешить подготовку отдельной append-only копии и ровно один условный запуск прежней последовательности Q014 после всех gates:

- Новый root run: `7a0fbaff-d7de-4376-be5a-0cca5f04760e`, prefix `nestakada-bound29-7a0fbaff`.
- Новый public namespace: `work/dev29-bounded-20261104-resume001/`; новый private namespace: `work/dev15-20261102/private/bound29-7a0fbaff-real/`. Сейчас этих runtime namespaces/ключей/attempts не создавали.
- Новые synthetic passwords/identity/HMAC key и независимые once receipts; исходный fail result rawSHA `4760812586b8727d80ee3d666c55c17ae4c3bdda00d75fad64c0dbd936b93cc0` фиксируется как ancestry, а не полномочие старого Run. Существующие TLS inputs только readonly.
- Предыдущие28 inputs сохраняются. В новой копии разрешены только необходимые замены root/prefix/путей/authority bindings и bounded Docker failure trace; новые source hashes и весь delta проходят независимое ревью до Prepare/Run. Source31, продуктовые protocol/consumer/tests, старый local_trust runner, исходные DB и корпус не меняются.
- При Docker failure записать закрытую подписанную квитанцию по схеме ниже; содержимое stdout/stderr/Env/секретов в trace не копировать. В Git только итоговые hashes/выводы. Сохранение trace не продлевает deadline и не запускает повтор.

### Закрытая failure-trace схема

Envelope имеет ровно `payload/signature`; signature — HMAC нового host-key над canonical payload. Payload имеет ровно: `scope`, `runId`, `packageSha256`, `sourceFingerprint`, `proposalSha256`, `preparedPlanSha256`, `engine`, `stage`, `callNo`, `endpoint`, `safeArgv`, `startedUtc`, `durationMs`, `timeoutMs`, `dispatched`, `exitCode`, `errorCode`, `signal`, `stdout`, `stderr`, `stderrSummary`, `rawContentsOmitted`. Scope фиксирован `BOUND29-DOCKER-FAILURE`, runId равен новому7a0fbaff…; source31 и package/proposal/prepared-plan SHA связаны с новыми reviewed inputs. callNo целый≥1, строго растёт при каждом Docker call и не сбрасывается при смене стадии. Стадия — только PREFLIGHT/ORIGINAL_BEFORE/INIT/C/T/STOP/ORIGINAL_AFTER/TERMINAL; endpoint — только ранее закреплённый Desktop Linux npipe.

`engine` имеет ровно `expectedId/observedId/observedAtCallNo`: expectedId фиксирован прежним pinned engine ID; observedId и callNo — только из успешной свежей info-проверки, до неё null. Не выдавать expected ID за фактически наблюдённый. `safeArgv` имеет ровно `operation/targetKind/target/profileSha256`; operation — закрытый enum INFO/CONTAINER_LIST/CONTAINER_INSPECT/IMAGE_INSPECT/VOLUME_INSPECT/NETWORK_LIST/NETWORK_INSPECT/CONTAINER_CREATE/START_ATTACH/STOP/KILL/REMOVE/NETWORK_CREATE/NETWORK_REMOVE. target допускает только проверенные64hex IDs, exact pinned image IDs, exact original volume name, exact новые owned names либо null. Для create хранить operation и SHA reviewed profile, **никогда raw argv/bind paths/env/stdin**; неизвестное отображение — FAIL, не raw fallback.

exitCode — integer|null; errorCode — только нормализованный ENOENT/EACCES/EPERM/ETIMEDOUT/ENOBUFS/OTHER|null, без Error.message; signal — закрытый enum|null. durationMs/timeoutMs — неотрицательные целые из исходного monotonic deadline. `stdout/stderr` имеют ровно `bytes/sha256/complete` и описывают только реально полученные bytes; при timeout/output-limit complete=false, hash не выдаётся за полный поток. **Лимит сохранённого сырого stdout/stderr —0 байт**. stderrSummary — только DAEMON_UNAVAILABLE/TIMEOUT/NOT_FOUND/PERMISSION/INVALID_ARGUMENT/OUTPUT_LIMIT/OTHER/EMPTY по закрытым правилам распознавания; произвольный текст, пути, argv, URL, токены и secret-like строки не включаются. rawContentsOmitted=true. Максимум всей квитанции8KiB; отдельного stderr-файла нет.

Trace записывается только в новый protected ignored namespace, учитывается в прежних32MiB и в исходном deadline, не вызывает Docker и не изменяет TTL. Если trace не сохранилась/схема неизвестна — terminal FAIL/cleanup с отметкой отсутствия диагностического доказательства, не успех и не retry. Root cause не объявлять доказанной только по нормализованному summary.

Сбой trace не должен прервать уже начатый bounded safety cleanup: фиксируется diagnosticUnproven, новые SQL/фазы блокируются, выполняются только оставшиеся разрешённые Stop/kill/remove текущего owned lifecycle и terminal proof. Нельзя рекурсивно писать trace через Docker или повторно dispatch неуспешную mutation.

До кода фиксируются R016-AC01–04: (01) injected CLI timeout/exit/output-limit связываются с exact run/package/plan/engine/callNo, raw Env/argv/stdin/stdout/stderr не попадают в trace; (02) trace-storage failure блокирует дальнейшие фазы, но не safety cleanup, без рекурсии/retry/false PASS; (03) неизменность старых inputs/receipts/keys/source31 и включение всех старых/new roots в бюджет; (04) fresh once scopes/old root rejection, прежняя последовательность Q014/dual witnesses/terminal same-engine inventory. Проверки и новое независимое code review обязательны до Prepare; прежние Q014 функциональные сценарии остаются обязательными до SQL.

## Прежние ограничения обязательны

Те же имеющиеся pinned images без pull/build/install и без изменения Docker/WSL/ACL. DB memory=swap1GiB/CPU0,5/PIDs128; tmpfs parent PGDATA512MiB/run16/tmp32/shm16; helper256MiB/CPU0,5/PIDs64/tmp32/shm16; rootfsRO, CAPdropALL, no-new-privileges, noports/loggingnone/restartno, internal network. VM MemAvailable≥2GiB; persistent conservative budget<2GiB, новые artifacts≤32MiB, streams≤1MiB. При нехватке — NOT_RUN, без увеличения лимитов/удаления корпуса.

Список retained host roots строится из **всех roots прежнего prepared plan779285…**, затем добавляются новые accepted public/private roots. Прежний `work/dev29-bounded-20261103/` с QA/real/host/results и новый namespace учитываются оба; nested roots дедуплицируются без потери старого корпуса. Не брать только старый DEV15 closeout и новый namespace, исключая промежуточные retained пакеты. Перед запуском и после cleanup свежий бюджет включает исходный volume allocation, все retained roots, новые trace/ключи/receipts и прежний reserve.

Исходный том — только два bounded RO/volume-nocopy inspectors до/после, UID999, без SQL/подъёма старого DB. Новый DB никогда не получает старый volume. Bootstrap/runtime HBA, TLS/roles/marker/actual OID/system identity и source gates сохраняются. Никакой старый архив не открывается.

После нового code review — один Prepare и независимое prepared-result review; затем отдельный dispatch review, свежий preflight и original RO-before. Последовательность INIT → C → T; START/INIT/PAYLOAD-C/C/PAYLOAD-T/T independently reviewed по конкретным hashes, без auto-approval. C — настоящие1000/1001 с outer rollback, T — исходные139 без skip/подмены assertions и с guarded existing-new-UNIT. После send — два независимых последовательных witnesses. Старые5+8 service probes не повторять.

Once scopes/TTL≤900с/без renewal. Принятые более строгие start remaining C850/T490 секунд сохраняются; total host C620/T260/audit90 включает create/work/postinspect/cleanup, последние30с заранее выделены cleanup. INIT≤90с; reviews hard120с, до start clock/fresh C/T admissions. Неуспех/timeout/drift/OOM/ENOSPC — terminal FAIL и bounded exact owned cleanup, RO-after и последний same-engine/zero inventory; без второго dispatch. После реально начатого неуспешного cleanup mutation entry retry запрещён; отказ до dispatch не помечается выполненной mutation.

Само согласование не является успешным test result. C/T реально выполняются только после собственных gates; P29-A/fullRegression/native leases/restart/crash/APP не закрываются заранее. Старый сайт/VPS/production/push исключены.

## Вопрос владельцу

**DEV29-Q016:** разрешить подготовку описанной append-only копии с failure trace и один новый условный root run по прежнему Q014-процессу, с независимыми code/Prepare/start/payload/result reviews и обязательным cleanup? После gates разрешаются **только перечисленные временные owned DB/network/helpers нового run**; иные или постоянные ресурсы, SQL/запуск старого кластера, старый сайт/VPS и обход runner не разрешаются. Старый Run не повторяется. До ответа — только это предложение и независимое ревью.
