# DEV-29: безопасная диагностика жизненного цикла Docker CLI

2026-11-04. DIAG29-LIFECYCLE-001. Исполнение нового поручения владельца: «Продолжай: выясни причину таймаутов Docker, подготовь безопасную диагностику и проведи независимое ревью. Старый сайт и VPS не трогай.» Это возобновляет только диагностику; R021/полный PostgreSQL Run остаётся приостановлен. Сначала план/code/offline и независимое review, затем максимум одна описанная read-only проба. Никаких циклов и полного Run.

## Установленные факты и пределы

Q021 call2/4 timeout9010/9008мс, nativewait8999,0partial bytes, terminal0empty. Все3inventory используют одинаковые command/spawnSync/env/cwd/deadline; trace пишется после failure. Q020 отличается сразу transport/форматом/filter/45с/моментом и не доказывает причину. dispatched=true выставляется доinvoke; PID/spawn/exit/close events в старой trace нет. Startup/ожиданиеCLI/daemon/закрытиепотоков неразличимы. Отказы и frozen source/results не изменять.

Read-only metadata этой смены: DockerCLI29.9.2, Node24.22.1, saved Linux engine kernel WSL, overrideenv count0, localdocker.exe отсутствует. Путь executable найден Get-Command; его персональный absolute path в документы/reports не писать. Resource Saver видели на старом снимке, затем Engine running; фактическое состояние при failures неизвестно. Docker docs различает WSL(выход изSaver immediate) и Hyper-V(возможна задержка), поэтому вывод «точно холодный старт3–10с» не доказан. Источники: https://docs.docker.com/desktop/use-desktop/resource-saver/ ; https://nodejs.org/download/release/v26.8.2/docs/api/child_process.html (API events, не требование менять установленный Node24).

## Неизменяемая единственная команда

Executable docker.exe, безshell, cwd T:/nestakada, endpoint npipe:////./pipe/dockerDesktopLinuxEngine. Exact argv:

--host npipe:////./pipe/dockerDesktopLinuxEngine ps -aq --no-trunc --filter label=bound29.run=7ead868c-8fe8-4096-97c5-641d4c72efa3

Старый root здесь только read-only filter; его attempts/once/authority не используются/не открываются. Нет info/version/inspect/другогоquery/proxy/Envvalues/SQL/контейнеров/сетей/томов/UI/рестартов/settings. Не выполнять произвольные аргументы; closed allowlist compile-time. Parent env только inherited с удалением5DOCKER override names case-insensitive, values не сохранять. windowsHide=true; async spawn; stdin pipe немедленно EOF, stdout/stderr pipes безstdin payload. Это диагностическая смена transport с наблюдаемостью, не исправление runner/controller.

Native deadline8999мс от beforeSpawn monotonic, не45с. Combined received-output cap1MiB (не слабее прежнего maxBuffer), report≤8KiB; total≤30с включая завершение наблюдателя/запись, послеnative deadline максимум5с на ownchild termination observation. Один termination request SIGTERM только объекту child этой пробы при timeout/outputcap/streamerror; без stop/kill/rm Docker и повторногоchildkill. Не убивать daemon/посторонние PID. При невозможности доказать exit/close — UNPROVEN, зафиксировать terminationUnproven, abandon local observer без второгоquery. Forcedlocalstreamdispose не выдавать за naturalclose/complete. После первой ошибки только завершение наблюдения/сохранение отчёта, не следующий probe.

## Отдельные файлы и gates

Новый ignored namespace work/dev29-docker-lifecycle-20261104-001/: diagnose.mjs, diagnostic-test.mjs и краткий test summary; максимум128KiB всего. Старые packages/private/source31/runner не меняются. Реализация не импортирует frozen controller, не читает private/keys/config/daemonlogs. Доnativequery once attempt.json wx с фактическимstartedUtc + plan/source hash/command fingerprint/task authority; существующийattempt илиreport => STOP безquery. Нет auto-retry/перезаписи/fallback/ACL. Штатный exec_command require_escalated при необходимости для конкретной новой папки и запуска, безblindACLrepair.

После независимого plan/code review и успешных offline checks — ровно одна проба в рамках текущего диагностического поручения владельца. Не требуются повторные согласования уже разрешённой read-only диагностики при неизменномscope. Функциональный новыйRun/изменение лимитов/SQL/исправление контроллера требует отдельного решения и этим документом не разрешается.

## Report и критерии

Result.json one wx: schemaVersion1, scopeDIAG29-LIFECYCLE, authorityD457, planSha256/sourceSha256/commandSha256, startedUtc/createdUtc, nodeVersion, executableDockerCLI/cwdProjectRoot (минимальные identities), fixed endpoint/argv, transportASYNC_PIPE_EOF, timeoutMs8999/outputCapBytes1048576, dispatched, spawnObserved, eventTimesMs {spawn,firstStdout,firstStderr,exit,close,deadline,kill}, exitCode/signal/errorCode enums, deadlineReached/outputLimitReached/killRequested/killAccepted/observerAbandoned/terminationUnproven, durationMs, stdout/stderr {bytes,sha256,complete}, count(nullunlessvalidcomplete), statusPASS/FAIL/UNPROVEN, classification, rawContentsOmittedtrue. Keys/paths/rawmessages/rawIDs/stdout/stderr не записывать/печатать. Relative times monotonic actual, missing=null, их нельзя подменять временемзаписи. dispatched = попыткаspawn, spawnObserved только actualevent. Errorcode null/ENOENT/EACCES/EPERM/ETIMEDOUT/ENOBUFS/OTHER; signals closed normal list orOTHER. Отсутствующиеevents не изобретать. createdUtc отдельноеfacttime.

PASS только successfulspawn+exit0+naturalclose доdeadline/безcap/errors/abandon, полный stdout0+unique lower64hex lines, CRLF→LFonly/неболее1finalLF. count только приPASS. Streams complete только naturalclose безerror/timeout/cap/abandon. Hashes пофактическиполученнымbytes, не полномуunknownstream. Raw persistence0. Report write failure => reportUnproven без fallback/retry.

Classification по наблюдению: SPAWN_FAILURE при error доspawn; CHILD_WAIT если spawnесть/exitнет доdeadline; PIPE_CLOSE_WAIT если exitесть/closeнет кdeadline; CURRENT_QUERY_SUCCESS приPASS; PROCESS_FAILURE при exitnonzero/error/signal; OUTPUT_LIMIT приcap; OBSERVATION_UNPROVEN при неопределённом завершении. Это локализацияграницы, не утверждение APIrequestdelivery/daemonrootcause. PASS не докажет ошибкуsync-вызова: момент/внешнеесостояниеизменились. Childwait не отличает внутреннее ожиданиеCLI от daemon/network/plugin. Hypotheses сохранять как hypotheses.

DIAG29-AC01 closedargv/noshell/несекретныйreport/oldpackagesunchanged; AC02 spawnerror+exit+close sequence, exitbeforeclose/hangingpipes различимы; AC03 deadline/outputcap/streamerror killownchildonce и отсутствиеretry; AC04 stdoutvalidation/partialhash/completeness/countnull; AC05 once/reportfailure nooverwrite, source/planpins доdispatch. Offline mockedprocess/clock и при необходимости один inert Node child (неDocker) послеcode review; зависимыеchecksпоследовательно. Послеactualreport независимоеfile/resultreview безновогоquery/HMAC/keys. Готовность DEV-29≈35%/этап8≈31%, диагностическийуспехнеfunctionalPASS.
