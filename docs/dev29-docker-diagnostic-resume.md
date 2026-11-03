# DEV-29: ограниченное возобновление диагностики Docker

2026-11-04. **R016-DOCKER-DIAG-RESUME-001 / предложение DEV29-Q017. Не утверждено.** Причина: [два timeout CONTAINER_LIST внутри единственного Q016 Run](dev29-bounded-resume-results.md), после которых задача приостановлена владельцу. Это предложение не возобновляет выполнение.

## Что разрешить

Только один read-only диагностический проход, чтобы отделить состояние Docker Desktop от поведения прежнего quiet/label запроса. Новый факт состояния берётся из другого источника; исходный `ps -aq --filter label=…` не повторяется.

1. Единственный UI source — **уже существующее главное native-окно приложения Docker Desktop с заголовком `Docker Desktop`, нижний левый status indicator Docker Engine**. Сначала read-only inventory подтверждает существование этого окна/приложения; при отсутствии/неоднозначной identity — STOP. Разрешены только foreground выбранного существующего окна и чтение этого индикатора; никаких clicks/навигации/settings/logs/Env/закрытия dialogs или запуска приложения. В report фиксируются UTC-время наблюдения и opaque surface identity/application/window title; screenshots не сохраняются в workspace/artifacts/Git.

   Закрытая интерпретация **определяет условие допуска, не утверждает наличие текста в текущей версии UI**: exact `Engine running` или `Docker Engine running` в указанном status indicator → RUNNING. Exact `Engine starting`/`Starting the Docker Engine...` → STARTING; `Resource Saver`/`Resource Saver mode` → RESOURCE_SAVER; `Engine stopped`/`Docker Engine stopped` → STOPPED. Иное/локализованное/нечитаемое/противоречивое состояние → UNKNOWN; нет окна/индикатора → UI_UNAVAILABLE. Только RUNNING допускает CLI; все остальные значения — STOP. Слово running в строке отдельного контейнера не является этим indicator. Не нажимать Start/Restart/Stop/Apply и не менять Docker/WSL/ACL/settings.
2. При подтверждённой готовности — ровно один иной, заранее фиксированный formatted local-npipe query:

   `docker.exe --host npipe:////./pipe/dockerDesktopLinuxEngine container ls --all --no-trunc --format "{{.ID}}"`

   Только ID проекция, без quiet-флага/label filter, inspect/Env/volume mounts/SQL. Docker override variables очищаются так же, как в принятом controller. Один async subprocess со stdin ignore, stdout/stderr pipe и hidden window; deadline45с, combined received-output cap64KiB, при cap/timeout останавливается только этот read-only CLI process, не daemon/контейнеры. Никаких повторов и увеличения лимита после ошибки. UI step≤60с, весь проход вместе с report≤120с. Если фиксированный UI source недоступен — STOP, без альтернативных blind probes.
3. Report имеет закрытые поля: `scope/createdUtc/ui/command/dispatched/exitCode/errorCode/signal/durationMs/timeoutMs/stdout/stderr/stderrSummary/count/status/rawContentsOmitted`. Scope=`R016-READONLY-DOCKER-DIAGNOSTIC`, ui=`surface/application/windowTitle/observedUtc/state`, command=`endpoint/argv`; argv равны единственной указанной команде и сохраняют planned command даже при UI STOP. dispatched boolean означает попытку штатного native subprocess, не доказательство доставки запроса daemon. status — только STOP_UI/PASS/FAIL; exitCode integer|null; errorCode — null/ENOENT/EACCES/EPERM/ETIMEDOUT/ENOBUFS/OTHER; signal — null/SIGTERM/SIGKILL/SIGINT/SIGABRT/SIGSEGV/SIGPIPE/SIGALRM/OTHER. Raw Error.message не сохраняется.

   При dispatched=false status=STOP_UI, ui.state≠RUNNING, exitCode/errorCode/signal/durationMs/count=null, stdout/stderr bytes0/empty-SHA256/complete=false, stderrSummary=EMPTY; timeoutMs=45000 остаётся planned limit. CLI не вызывается. При dispatched=true ui.state=RUNNING, durationMs неотрицательный integer и поля описывают фактическую попытку; status=PASS только при exit0/errorCode=null/signal=null и полном валидном stdout без cap/timeout. Иначе FAIL/count=null; неизвестные error/signal нормализуются OTHER, не произвольный текст.

   stdout/stderr=`bytes/sha256/complete` по фактически полученным buffers, без текста. При timeout/output-cap оба complete=false; hashes описывают только полученный prefix. При exit0/no error/no signal/полных потоках stdout нормализуется **только CRLF→LF** и должен состоять из0+ уникальных строк exact lowercase64hex, с допустимым одним завершающим LF; bare CR/иной текст/duplicates/over-cap означают FAIL. count задаётся только при полном валидном stdout, иначе null. stderrSummary — EMPTY/DAEMON_UNAVAILABLE/TIMEOUT/NOT_FOUND/PERMISSION/INVALID_ARGUMENT/OUTPUT_LIMIT/OTHER, без произвольного текста; rawContentsOmitted=true, raw persistence0bytes.

   Не сохранять raw IDs/output/screenshots/секреты. Единственный report≤8KiB записывается wx в существующий ignored `work/dev29-bounded-20261104-resume001/diagnostic-report-001.json`, без новых каталогов/ключей, один раз, в пределах total120с. Отказ записи — STOP/reportUnproven, без повторной записи. HMAC key/passwords не читать; это неподписанный диагностический отчёт, не admission/authority для SQL. Ни ошибка, ни PASS не разрешают второй CLI query.

После результата — независимое файловое ревью. Даже PASS означает только текущую доступность и иной формат запроса; прежний отказ не переписывается и историческая причина автоматически не считается доказанной.

## Границы

Никаких новых images/packages/инсталляций, изменений исходного кода/контроллеров, новых runtime namespaces/keys/Prepare/Run/INIT/C/T/SQL. Допустима только описанная diagnostic orchestration средствами tools; существующие файлы не перезаписываются. Не перезапускать Docker Desktop автоматически и не трогать чужие контейнеры. Старые roots/пакеты/receipts/корпус сохраняются. Исходный volume не подключается и не проверяется SQL. Старый сайт/VPS/production/push исключены. Дальнейший функциональный запуск потребует отдельного конкретного решения; данный вопрос его не разрешает.

Альтернатива — оставить паузу, владелец сам по своему решению проверяет/перезапускает Docker Desktop и сообщает изменившееся условие. Агент не делает этого за владельца.

## Вопрос владельцу

**DEV29-Q017:** разрешить возобновить только описанную read-only диагностику: сначала новый источник readiness в существующем интерфейсе Docker Desktop, затем при готовности один formatted inventory с45-секундным пределом и независимым ревью? Старый quiet/label query и полный Run не повторяются; код/SQL/настройки не меняются. До ответа R016 остаётся «Приостановлено владельцу».
