# DEV07-N2 — поздние права и потерянный ответ Save

2026-11-01. Только технический контракт до QA/review/code gate. NET007/008 продолжают реальные NETWORK_6, не меняют их прежние файлы/отчёты. Действуют прежние body120, child AS384/CPU10/wall20, app768MiB/1CPU/pids128, один slot, test-only threading/proxy150 и observer1ed961…; production server/old site/VPS не затрагиваются. Новых зависимостей, endpoint или таймеров нет. Scope — один current source и закрытый синтетический fixture run.

## 1. Настоящие действия владельца

Фактические accounts.urls/views/services уже предоставляют следующие owner-only POST. Это обычные form-urlencoded≤16KiB с действительной owner session и настоящим CSRF, не JSON/editor64MiB и не fixture mutation:

| Route под /manage/ | Закрытые поля | Фактическое действие |
|---|---|---|
| employees/<userId>/grants/ | page=UUID,action=revoke; для set — action=set и intro_text/main_text/price=on только выбранных прав | Revoke удаляет PageGrant, не меняя generation/session; set восстанавливает согласованный набор |
| employees/<userId>/password/ | password — новый известный тесту синтетический секрет | Active остаётся прежним; generation++, все AuthSession и native Session сотрудника удаляются |
| employees/<userId>/active/ | action=disable либо enable | Изменяет active и инвалидирует generation/sessions; дополнительный вариант, не первый N2 scope |

Successful owner response —303 Location /manage/employees/. Настоящие формы доступны на странице «Сотрудники и права»: grants form action, select[name=page], checkbox names, кнопки action=set/revoke; password form input[name=password]. До мутации проверяются exact target synthetic user/page из run, действие не относится к настоящему пользователю вне fixture. Password/CSRF/cookie остаются только private memory/существующем закрытом fixture-процессе, не в URL/логах/Git/observer JSON.

Прямой ORM update grant/session во время сценария запрещён. Read-only fixture witness может подтвердить фактические generation/active/hasGrant/allowedFields/sessionCount только для собственных синтетических actors, без password hash/session keys. Уже существующий seed/setup допустим как исходное состояние, но не заменяет owner HTTP action между barrier и завершением тела. Для cleanup сначала сохранить доказательства; обратное set/relogin выполняется настоящими действиями, прежний fixture772b… и его permanent-receipt cleanup правила не изменяются.

## 2. NET007 — два первых поздних отказа

**NET007-G: employee Check / полный отзыв назначения.** Реальным входом сотрудник имеет main_text grant. Сформировать допустимый PageInput текущего source с неизменным generation/base, новым безопасным plain main_text. Начать настоящий socket POST check с корреляцией, отправить только8192B из body>8192B. До owner action обязательны slotAcquired1, readerEnter1, deadlineEntered1, normalizeEnter0, настоящий NB slot conflict и свободные independent PG content/auth locks.

В другом owner connection отправить настоящий grants/revoke с действительным CSRF и дождаться303. Read-only witness подтверждает отсутствие PageGrant при прежних active/generation/sessionCount. Только после этого дослать оставшийся body A. Pre-read context сотрудника уже существовал, поэтому нормализация может реально запуститься; поздний свежий request_context/allowed_fields должен отказать. По нынешнему коду ожидается403 EDITOR_FIELDS_FORBIDDEN, без checkReceipt в response. Не требовать child0 для этого late сценария: это отличает его от early refusal.

**NET007-S: employee Save / инвалидирование сессии новым паролем.** После настоящего повторного назначения сотрудник получает новый действительный CheckReceipt; сформировать точный canonical Save body с новым operationId. Начать реальный partial-body Save и подтвердить тот же barrier. Owner POST password/ задаёт новый синтетический пароль;303 и read-only witness показывают generation+1, active=true, AuthSession/native Session прежнего входа отсутствуют. Затем дослать тело. views.write после настоящего normalize_input вызывает require_session(touch=False); ожидается401 EDITOR_SESSION_ENDED. Никакой commit/OperationReceipt для operationId не возникает.

Оба owner действия должны завершиться, пока A реально удерживает body slot: это одновременно проверяет отсутствие длинной content/auth transaction. При отпускании A после владельческого303 фиксируется порядок monotonic observer/HTTP events, а не надежда на sleep. Сценарий завершается намного раньше120, deadline не подменяется. При недоступном owner action тест останавливается с фактами, не снимает чужой lock и не редактирует БД для продолжения.

Для обоих отказов сравнить current pointer/payload/history ordinary+Stable/drafts/stages/pins/media usage+actual files и receipt set до/после, исключив ожидаемые account/grant/security-audit changes. domainHash сам по себе недостаточен: receipt rows сравниваются отдельно. Закрытый observer: real reader/normalizer завершены, slotExited1, timerAlive=false, duplicateClosed=true; healthy owner Check после отказа успешен. Для session случая новый вход сотрудника новым паролем получает новую generation; старый body/proof не переиспользуется для положительного нового Save. Broad field-only grant downgrade/disable/logout/source/media races остаются отдельно pending.

## 3. NET008 — полное тело без потребления ответа

Первый manageable вариант — owner current Save, действующая неизменная session, отдельный operationId. Получить настоящий Check и явно принять canonical changes, затем сохранить в RAM точные body bytes, selector/query и заголовочные credentials. Никакой другой tab не редактирует source в этом сценарии. Перед Save observer/state фиксируют current/revision/receipt set и допустимые refs.

Новый raw TCP socket ставится в paused/read-disabled режим ДО отправки: не устанавливать response data handler, не вызывать read, не парсить reply. Отправить полное Content-Length тело через обычный socket write. Успех callback/отправленный byte count сам по себе не доказывает, что приложение прочитало всё тело. Поэтому независимый канал обязан увидеть actual readerExit1, normalizeEnter/Exit1, timer cleanup и затем durable OperationReceipt с exact operationId, actor/action/Page/generation/editor fingerprint и result revision. Наблюдатель не задерживает оригинальные функции и не подставляет commit.

После этого намеренно закрыть всё ещё paused socket, не потребляя response. Receiver kernel/Nginx могли уже принять или передать ответ; этот вариант НЕ доказывает отсутствие server write и не называется потерей пакета на сети. Он доказывает клиентскую неполученную/неразобранную прикладную квитанцию при настоящем commit. Независимый тестовый witness знает результат только для oracle; клиент по своему connection остаётся в UNKNOWN и не должен создавать новое намерение автоматически. Дополнительный вариант close между normalizeEnter и durable commit требует отдельного сценария и честного допуска как commit, так и rollback — он не заменяет детерминированный first scope.

Результат независимого durable witness не передаётся в Save request и не даёт роли/права. В настоящем отдельном HTTP POST отправляются точно те же сохранённые bytes/query/operationId/CheckReceipt с прежним actor/generation и действительной session. saving.commit_checked сначала делает replay_checked: fresh E.enter/fields/check_editor_session, затем exact action/actor/generation/Page/fingerprint receipt match, до нового media availability/worker-result admission. Изменившийся current/base после первого commit не препятствует законному replay.

Ожидается200, replay=true, тот же operation_id/result_id/result_code/gone что следует из настоящей durable row; ни второй automatic version, ни новая receipt, ни повторное consumption/pins/physical writes. Observer повторного запроса может показать реальный короткий child metadata path: не требовать child0 и не выдавать replay до decode как принятую реализацию. Исходный Save и replay получают разные trace request IDs, но один operationId. Никакой автоматический retry в приложении этим не добавляется.

### Отрицательные операции после примирения результата

- Тот же operationId при изменённых changes (остальные поля сохранены) —409 EDITOR_OPERATION_CONFLICT по permanent fingerprint, без мутации, а не повторный успех старого результата для другого запроса.
- Новый operationId с исходным уже устаревшим base/proof —409 EDITOR_BASE_CONFLICT, без дополнительной версии/receipt. Это целевой отрицательный тест, не рекомендуемый способ автоматического повтора UNKNOWN.
- Повтор при отозванных правах/сессии не обязан и не должен возвращать старый результат по одному UUID. Точный replay-after-revoke статус/матрица выносится отдельно; первый положительный NET008 сохраняет действующие права и session, чтобы не смешивать причины.

## 4. Harness/fixtures и границы свидетельств

Предлагаются только новые N2 wrapper/probe/fixture adapter после gate; frozen NETWORK_6 tools и original fixture772b… сохраняются. Новый read-only adapter может делегировать существующие snapshot/slot/PG operations и возвращать минимальный account+receipt witness для собственных fixture IDs; не добавляет ORM writers/auth capability. Owner HTTP действия находятся в runner, а credentials в private RAM. Никакого публичного test endpoint, interception fake reply, patched commit/worker/security или Docker socket/DB secret в браузерном runner.

Используется свежий networkRun32HEX и новый app observer instance для каждого actual attempt. Старый request counter не сбрасывается и не переиспользуется; до запуска распределить≤32 IDs, например1–6 для NET007 и7–10 для первого Save/replay/двух negatives. Preparation Check/owner form POST без trace header не создают сетевые trace rows. Header остаётся только correlation; права не зависят от него. Точный observer1ed schema/timer/FD flags без новых app fields достаточен; durable commit подтверждается независимым DB snapshot, не requestEnd200 в одиночку.

Максимум первого N2:2 late cases +1 lost-reply/replay case с двумя negative requests и healthy controls. Прочие NET007/008 сочетания остаются pending. Snapshot/source/image/config/fixture hashes, неувеличенные caps, monotonic event ordering, finite operation counts и cleanup всех own sockets/threads/children/private seed фиксируются в отчёте. Permanent identity/receipt rows не удаляются ради нулевого count: cleanup следует принятой политике fixture и отдельно показывает live consumers/files0, если применимо.

Код, runtime, конфигурации и исходные инструменты этим документом не изменены. Перед выполнением нужны независимые QA-сценарии, reviewer gate точного read-only adapter и отдельное root разрешение кода/стенда. Технический допуск не является приёмкой полного DEV-07 или production.
