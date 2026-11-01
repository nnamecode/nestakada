# DEV07-RSV-UI — сохранение и неопределённый ответ

2026-11-01, D-351. DEV-07 около96%, этап8 около20%. Уточнение RSV-UI-001–005 из dev07-shared-reservation-scenarios.md до изменения shared editor.js/template; это существующая принятая политика Page editor, применённая к Header/Footer. Новых dependencies/ресурсов/серверов/сборки нет. Native проверки используют уже согласованный Docker Playwright1.64.1, без Windows npm.

## Состояние и отправка

В RAM вкладки: epoch, cleanEpoch, принятая Check proof с epoch/HTML, busy, единственный uncertain intent. Intent содержит action, operationId, полный immutable DTO/body/query и captured epoch. Никаких Web Storage/IndexedDB/URL для HTML/proof/CSRF или очереди публикаций. Input во время запроса меняет epoch и сбрасывает Check, но не заменяет frozen intent.

Check подтверждает только совпадающий epoch/input. Принятие нормализации остаётся явным действием и также требует неизменившегося исходного ввода. Draft/Apply требуют своей актуальной proof; Apply сохраняет существующее подтверждение владельца. Пока есть uncertain intent, новые Check/Save/Draft не отправляют новое намерение: сначала отдельная кнопка «Повторить проверку результата прежней отправки». Никакого автоматического retry. Кнопка повторяет тот же body/query/operationId, даже если пользователь уже напечатал другой текст; этот новый текст остаётся RAM/dirty и не подменяется прежним.

Сеть/неразобранный ответ/5xx или невалидный ACK дают UNKNOWN. Явный доказанный pre-admission отказ с server-written `operationNotStarted:true` очищает только первую известную попытку и старую proof, сохраняя ввод; одного4xx/кода ошибки недостаточно. После уже неизвестного исхода даже отказ нового ручного запроса до admission не доказывает отмену прежней отправки: uncertain остаётся, кроме проверенного terminal-aborted результата. Подтверждённый terminal-aborted409 с matching operationId/outcomeKnown:true закрывает uncertain, но не отмечает текст сохранённым; новая попытка требует ручной Check и нового intent.

## Подтверждение результата

Успех проверяет operationId/resultId/resultCode/replay/gone и server-written editorContext. Контекст — ровно baseRevisionId/sourceMode/draftBasis/stageId, canonical UUID и целые counters; apply указывает committed result ID/current, draft — committed draft ID/revision с прежней base. Старый receipt не получает новый latest draft counter. Gone либо legacy draft без достоверного ACK не очищает dirty и не делает implicit rebase; нужен явный актуальный источник.

После доказанного результата прежняя proof становится недействительной. Новый server ACK обновляет только основание последующих ручных проверок, не textarea. cleanEpoch меняется лишь если текущий epoch равен captured epoch успешной операции и результат доступен. При новом вводе во время отправки статус прямо говорит: прежняя операция подтверждена, новые изменения ещё не сохранены. Повтор/ACK не публикует их автоматически.

Старая/сменившаяся сессия не даёт отправить прежний proof под новой generation. При отказе входа текст остаётся, пользователь видит необходимость входа/проверки истории и актуального источника. Не объявлять отсутствие старого commit по одному401/403. Beforeunload предупреждает о dirty либо unresolved intent. Проверяемые сообщения не содержат private paths или сырые ответы сервера.

## Фактическая проверка после кода

RSV-UI-001–005 выполняются в настоящем Chromium с действующими авторизацией/CSRF и запросами через локальный Nginx. Управление delivery собственного ответа не подменяет серверный business Apply; oracle — фактические PostgreSQL/FS snapshots и HTTP result. Различать непотреблённый response и transport abort. Fixtures подготавливают только собственные synthetic данные и убирают их отдельно; браузер не получает Docker/DB credentials. Не переносить прежние Page browser PASS на эти новые случаи.

До браузерного прогона технически проверить существующий candidate app image782f53c4… на том же frozen source/caps/network: foundation base09433387… не содержит parser package. Временный test overlay меняет только образ локального app на уже согласованный candidate; source/security/resource/loopback guards сохраняются и явно фиксируются. Старый сайт/VPS/production не затрагиваются. Не выдавать framework либо изолированный JS model test за native HTTP проверку.
