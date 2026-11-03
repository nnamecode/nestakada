# DEV-29: диагностика по снимку владельца

2026-11-04. R016-DOCKER-DIAG-RESUME-004 / DEV29-Q020 — предложение, не разрешение выполнения.

Новое свидетельство: после показанного Resource Saver mode владелец прислал второй снимок нижнего левого индикатора Docker Desktop с точным текстом Engine running. Время захвата снимка не известно; его получение не выдаётся за машинное наблюдение в конкретную UTC-секунду. Вложение не копировать в проект/Git. Q019 закончился UI capture timeout, CLI не запускался. Предыдущие root/Run остаются приостановленными.

Предлагается один всё ещё первый formatted read-only query из [Q017](dev29-docker-diagnostic-resume.md), rawSHA d84863fc7f77da4f643c551a82fd72ad81ca7b2cabfaccfdcdf2658043d8b518:

docker.exe --host npipe:////./pipe/dockerDesktopLinuxEngine container ls --all --no-trunc --format "{{.ID}}"

Изменение gate: вместо нового sky/UI чтения принять предоставленный владельцем снимок Engine running и его явный ответ Q020, подтверждающий сохранение этого состояния. Нет новой UI automation/foreground/capture/clicks. Если до dispatch появляется сообщение/свидетельство другого состояния, не запускать CLI. Q020 позволяет только одну новую bounded диагностическую попытку, не продлевает Q019 и не возобновляет функциональный R016.

До dispatch read-only precheck: proposal hash, report004 absent, существующий parent, штатный exec_command require_escalated доступен; без test-write/ACL/keys. Один async child_process.spawn, stdin ignore/stdout+stderr pipes/windowsHide, удалённые child env DOCKER_CONTEXT/DOCKER_HOST/DOCKER_TLS_VERIFY/DOCKER_CERT_PATH/DOCKER_API_VERSION. Deadline45с и combined received output64KiB; timeout/cap kill только этот CLI child, не daemon/контейнеры. Первая ошибка завершает попытку, retry/fallback нет. Общий deadline120с от начала попытки до report, без UI step. Не увеличивать deadlines.

Report004: work/dev29-bounded-20261104-resume001/diagnostic-report-004.json, одна wx запись через штатный exec_command require_escalated, ≤8KiB. Reports001–003 не создавать заново/не менять. Все16 closed top-level fields, command argv/endpoint, dispatched semantics, null/error/signal enums, strict stdout validation unique lowercase64hex/CRLF-only/single final LF, count only valid complete success, received-buffer hashes, complete flags and stderrSummary enums — как Q017. Никаких raw IDs/stdout/stderr/screenshots/keys/passwords/path metadata в файлах/выводе. Scope прежний R016-READONLY-DOCKER-DIAGNOSTIC, status PASS/FAIL при dispatch, STOP_UI только если новое свидетельство отменило gate до dispatch.

Явные поправки ui: surface=owner-attachment-db834f4a-dc58-4d42-b9e1-17c66c73ad4e, application=Docker Desktop, windowTitle=null (на crop отсутствует), observedUtc=null (capture time неизвестно), state=RUNNING по изображению. При отменённом gate state=UNKNOWN. createdUtc — фактическое время формирования отчёта, не время наблюдения. Ссылку на actual attachment/ответ Q020 и начало/elapsed попытки фиксировать отдельно в postmortem без копирования изображения/локального пути. Так закрываются Q019-RESULT-REV-001/002 без переписи report003. Неподписанный report не authority для SQL. Ошибка записи — reportUnproven, без перезаписи/резервного отчёта.

После результата независимое файловое ревью. PASS доказывает лишь доступность данного запроса в момент проверки, не причину прежних timeout. Нет нового code/Prepare/Root/Run/INIT/C/T/SQL, запуска/остановки контейнеров, настроек/установок/ACL. Source/runner/корпус/том/старый сайт/VPS не трогать. DEV-29 около35%, этап8 около31%.

DEV29-Q020: подтвердить, что индикатор остаётся Engine running, и разрешить ровно этот один read-only CLI query с report004 и независимым ревью? До ответа новых UI/Docker/report004 действий нет. Альтернатива — сохранить паузу.
