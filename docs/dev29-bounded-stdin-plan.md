# DEV-29: строгий stdin-профиль helper и один новый изолированный прогон

2026-11-04. **BOUND29-STDIN-001 / предложение DEV29-Q023. Не утверждено владельцем.** Только документы и файловое ревью. До ответа не менять код и не создавать новые package/private/Prepare/Docker/SQL/Run. Этап8≈31%, DEV-29≈35%.

## Доказанный блокер и точное исправление

[Q022](dev29-bounded-readiness-results.md) прошёл readiness и создал preflight helper, затем guard остановил выполнение доstart с HOST_COMMAND. Result raw112d2c1d15a638850ef56ee597dfcfcaf24d0eb33cc2b5c8c7db5466c55060ed, cleanup raw83dae816e98dab04edf443afd35a1c4e2546529fa89ee3e740bf101b27642bad. Независимый postmortem APPROVED, R022-REV-001 P1 открыт. Helper удалён; нового DB/network/SQL/INIT/C/T не было. One-shot Q022 исчерпан.

Сохранённый inspect дал OpenStdin=true, AttachStdin=true, StdinOnce=true. Все остальные пять command-полей совпали. В spec.mjs:48 universal StdinOnce=false противоречит собственному helperArgs --interactive. [Docker CLI v29.9.2](https://github.com/docker/cli/blob/v29.9.2/cli/command/container/opts.go#L691-L694) включает StdinOnce при OpenStdin&&AttachStdin; --interactive включает оба входных флага.

Предлагается **строгая замена одного ожидания**: StdinOnce должен быть равен Boolean(s.stdin) по неизменному reviewed profile. Для всех7 helper kinds с stdin требуется ровно true; для DB и обоих RO-inspectors безstdin — ровно false. OpenStdin уже сравнивается с тем же профилем. Остальные User/Tty/Entrypoint/Cmd и все isolation/ownership/mount/Env/state gates остаются exact.

Не удалять predicate, не разрешать «любой boolean», missing/undefined/string/number и не менять Docker create/start flags или протокол передачи/закрытия stdin. Не добавлять runtime-флаг обхода и не менять схемы profile/worker payload. Это исправление ошибочного ожидания, а не пропуск проверки фактического контейнера.

## Независимые fixtures и приёмка до реализации

Старый mock всегда ставил StdinOnce=false и поэтому не выявил ошибку. Его штатная модель должна соответствовать CLI, но tests не ограничиваются вычислением того же Boolean(s.stdin).

- **R023-AC01:** независимый literal typed fixture из фактического Q022 inspect (только безопасные command/stdin поля, безEnv/IDs/paths/credentials) с OpenStdin=true/AttachStdin=true/StdinOnce=true. Старый predicate отклоняет его; новый принимает при остальных валидных полях. Значения stdin fixture не генерировать из production profile. Источник связан с immutable cleanup rawSHA83dae….
- **R023-AC02:** все7 helper kinds принимают только StdinOnce=true. Отдельный flip вfalse, отсутствие поля, null/string/number и неверные OpenStdin/Tty/User/Entrypoint/Cmd отклоняются. Это не разрешение произвольной команды.
- **R023-AC03:** DB и RO-inspectors before/after принимают только StdinOnce=false; true и остальные неверные поля отклоняются. Create args/entrypoint/commands/caps/readonly mounts/network/user не меняются.
- **R023-AC04:** невалидный профиль по-прежнему блокирует start до SQL; уже зарегистрированный exact-owned id остаётся доступен bounded cleanup. Не менять lifecycle/cleanup registry или обходить ошибку. По отдельному API-признаку StdinOnce не считать контейнер полностью прошедшим остальные gates.
- **R023-AC05:** readinessPair из Q022 сохранён: только первый inventory requested45/native≤44с, пара info+inventory READINESS_ONLY90с с min(parent)/noreset/finallyrestore. Прочие inventory≤8999мс/helper90/INIT90/C620/T260/TTL/reviews прежние.
- **R023-AC06:** fresh root/once/owner/source/ancestry, полный retained budget и byte-preservation старого корпуса; ни source31/product/runner, ни SQL/assertions/caps других сценариев не меняются. Error/trace failure/drift запрещает зависимые шаги и повторный Run; только оставшийся разрешённый exact-owned cleanup/terminal proof.

Проверки последовательно: syntax/static → новые AC → все существующие offline-наборы без skip/изменения assertions → независимый code/delta review. Фактические количества новой копии ещё неизвестны. Host suite запускать прямо; отрицательные name-pattern не использовать как ограничение доступа. Если ancestry/retention test требует protected nonsecret ancestor result/cleanup, разрешён только стандартный hash/metadata-read этих конкретных receipts; keys/credentials/passwords не читать и не выводить. До Prepare нет нового private namespace.

## Новая append-only копия

Root241f54c3-9e72-47aa-9e50-8fafe19a3576, prefixnestakada-bound29-241f54c3. Public work/dev29-bounded-20261104-resume004/; private work/dev15-20261102/private/bound29-241f54c3-real/. Сейчас не созданы.

Основа — frozen resume003 package36 SHA78cc127f04887321a28fad68bcdbeb8115fa5e74afd208308b95f56bd64e2c8a. Разрешённая дельта: identity/root/prefix/paths/owner/authority/marker/производные SQL hashes и новый strict StdinOnce predicate вspec.mjs, соответствующие host-test fixtures/cases. Независимые typed fixtures можно хранить literal вhost-test, не менять manifest без необходимости. Controller readiness/flow/failure-trace/SQL semantics/прочие budgets и guards не менять, кроме нужных identity/ancestry bindings. Source31 fingerprint1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e и product protocol/consumer/tests/старый local_trust Tests guard неизменны.

Immediate ancestry: R022 prepared rawfaa3a6d67f5bb6ab033e7b67742d7d38a747c7c99ec09cab272777f29a3faec3, result raw112d2c1d15a638850ef56ee597dfcfcaf24d0eb33cc2b5c8c7db5466c55060ed, package78cc127f…, cleanup raw83dae816e98dab04edf443afd35a1c4e2546529fa89ee3e740bf101b27642bad. Сохранить bindings known causee3e515/readiness26763/Q022plan07c412 и нового утверждённого плана. Старые FAIL/receipts/keys/история не меняются и не являются новыми admissions.

Retained roots: весь set предыдущего prepared plan, old bounded, resume001/002/003, новый public/private и весь failed diagnostic namespace work/dev29-docker-lifecycle-20261104-001/. Nested dedup не исключает корпус; старые данные не удалять ради budget. До/после считать volume allocation, всеhost roots, new artifacts и reserve. Observer NOT_RUNTIME_QUALIFIED не импортировать, не испытывать повторно и не использовать как proof.

## Один условный lifecycle и сохранённые ограничения

Одним ответом предлагается разрешить только описанный stdin-profile fix/newCOW/tests/code review, один Prepare, независимые prepared-result/dispatch reviews и максимум один условный Run INIT→C→T с обязательными actual START/INIT/PAYLOAD-C/C/PAYLOAD-T/T reviews по hashes, rollback, dual witnesses и остановкой временного стенда. Технические gates при неизменном scope не требуют новых вопросов владельцу; их нельзя preapprove или пропускать. Ошибка завершает попытку, второго Run/расширенного fix этим ответом не разрешается.

Сохраняются exact Q022 architecture/rawSHA07c412cd04d86039eb670ee975d2c8b6998d182409d9e96c483af244b6dc9809 и его наследуемые Q014/Q016/Q021 ограничения, кроме нового per-profile StdinOnce ожидания и identity/authority:

- тот же Desktop Linux npipe/expected engine и pinned images, без pull/build/install/settings/WSL/перезапуска;
- исходный volume только вдвух boundedRO volume-nocopy UID999 inspectors до/после, безSQL/запускастарогоDB; новый DB вtmpfs PGDATA512MiB/run16/tmp32/shm16, memory=swap1GiB/CPU0.5/PIDs128;
- helper256MiB/CPU0.5/PIDs64/tmp32/shm16, rootfsRO/CAPdropALL/no-new-privileges/noports/loggingnone/restartno/internal network;
- VM available≥2GiB, conservative persistent<2GiB/new artifacts≤32MiB/streams≤1MiB/closed raw0 HMAC trace≤8KiB; недостаток=>NOT_RUN, безочисткистарого/увеличениялимита;
- INIT90с/TTL≤900с безrenewal, Cstartremaining≥850с/T≥490с; C620/T260/audit90 с30сcleanup; actual независимые reviews≤120с доstartclock/freshadmission;
- Cнастоящие1000/1001 сouterrollback, безbulkseed/caplowering; Tисходные139 безskip/подмены; guardednewUNIT, двапоследовательныхнезависимыхwitnesses, RO-after/terminalsame-engine owned0/freshbudget;
- старые5+8 probes не повторять; P29-A/nativeleases/crash/APP не объявлять завершёнными заранее. Ключи и rawlogs/output не отправлять вGit, ACL вслепую не менять, при отказе штатного доступа STOP.

## Вопрос владельцу

**DEV29-Q023:** разрешить точное исправление stdin-профиля и весь один новый ограниченный lifecycle с указанными reviews/rollback/сохранностью/cleanup? Старый сайт, VPS, production и push вне разрешения. До ответа — только план и независимое файловое ревью, без кода/новыхпакетов/keys/Prepare/Docker/SQL/Run. Альтернатива — сохранить выполнение на паузе.

Текущий этап8/DEV-29/P29-A. Следующий участок после принятого результата — оценка оставшихся P29-A требований и план P29-B/C/D/E; общий этап9 после разработки.
