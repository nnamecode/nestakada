# DEV07-D — стыковка черновиков и подготовленного восстановления

2026-10-31, D-335. Реализованная локальная область DEV-07: owner draft/create/update/edited apply/rebase/cancel и restore-stage с отдельным checked Save. Этап8 около20%, DEV-07 около80%, в работе. **290 тестов,16 прежних и9 новых Chromium/UI/HTTP групп PASS; независимое ревью без открытых подтверждённых блокеров в этой области.** Новых бизнес-правил, зависимостей, TTL и ресурсов не вводится. Основные маршруты/production не подключены; старый сайт и VPS не затронуты. Перед изменениями рабочее дерево было чистым, baseline09b16b7; отметка сохранена в work/dev07-draft-restore-20261031/.

## Источник и проверка

Для editor/state/check/save/draft используется закрытый query selector: current — пустой; owner-draft — ровно source=owner-draft, draftId=UUID, draftRevision=положительное целое; явный rebase дополнительно rebase=1 и targetCurrentId=UUID; restore-stage — ровно source=restore-stage, stageId=UUID. Дубли/неизвестные ключи запрещены. Техническая рамка selector256ASCIIбайт ограничивает только идентификаторы, не контент. PageInput source/basis/stage обязаны точно совпадать. В URL нет ввода, proof, CSRF или секретов.

SourceContext берётся из действительной серверной записи: current payload; exact owner draft id/revision/base/hash; либо candidate_for_stage с actor/Page/generation/held/base/grants/schema/source provenance. Protected layout определяется выбранным источником. Actual currentID хранится отдельно от draft base. До разбора большого тела — session/Page admission; locks отпущены во время одного child normalize и FS preflight. Родитель не разбирает большой JSON.

CheckReceipt связывает source selector/stamp, actual current context, grants/generation/policy и fingerprints. После child всё проверяется повторно. Check не изменяет draft/current/history. Snapshot собирает только сервер: фактический выбранный payload плюс проверенные изменения разрешённых полей. Employee stage использует точную существующую allowed-field projection.

## Запись и повтор

Draft POST добавляет operationId/checkReceipt/rebase:boolean. Создание из current допустимо только при отсутствии draft. Изменение — exact draftId/revision/base/hash; обычный draft-save может сохранять старую основу без публикации. Rebase только отдельным явным действием, без автоматического объединения с current. Режим rebase и показанный targetCurrentID связываются уже с check intention, receipt и fingerprint; обычный draft proof нельзя превратить в rebase сменой boolean последнего POST. PageInput.baseRevisionId остаётся old draft base, engine target берётся только из совпавшего подписанного серверного context. До подтверждения показывается сравнение current/draft и смысл переноса целого проверенного draft без merge. Смена current после сравнения/check даёт409 и требует нового явного действия. Точный закрытый selector rebase фиксирует разработчик до QA кода; технический способ не добавляет бизнес-правило.

Edited draft публикуется одним атомарным editor commit. Внутренний expected_draft_hash приходит от actual draft, не клиента. Обе фазы проверяют id/revision/base/hash/current/session/grants; итоговый проверенный Snapshot может отличаться от draft. Legacy commit без editor proof сохраняет прежнее требование равенства payload. Не выполняется предварительный draft-save перед publish. Новая automatic/current/usage/prune/receipt/audit и consume draft выполняются вместе. Stage consume/provenance сохраняет действующий engine и повторную whole compatibility проверку.

Exact replay проверяет action/actor/generation/Page/fingerprint при актуальных правах и сессии до lookup уже consumed source. Если source недоступен, save/draft получает только canReadSource=false и минимальный admission context; child строго декодирует DTO/selector и возвращает metadata/fingerprint, без нормализации/нового proof. Без совпадающей постоянной receipt новый write отклоняется409. GET/check при missing source отклоняются, не выдают старый payload. Нового idempotence TTL нет.

Draft save/cancel получают такие же session/fingerprint guards. Отмена — отдельный малый CSRF POST с exact ID/revision/generation/operationId, вне большого allowlist. Stage prepare/confirmation/cancel остаются существующими явными действиями DEV-05. GET stage/editor не публикует и не потребляет stage.

## Интерфейс и испытания

Owner current: отдельное сохранение черновика; отдельный вход в точный draft, явная отмена и rebase. Restore: подтверждённая подстановка, затем проверка и отдельное сохранение. Employee не получает даже наличие owner draft. Concurrent edits сохраняются в RAM; доказанный результат меняет UI basis только для отправленного намерения, неизвестный исход повторяется вручную с тем же замороженным body/context/UUID. Смена пользователя очищает прежние доступные копии ввода.

Приёмочные сценарии до кода: [dev07-draft-restore-checks.md](dev07-draft-restore-checks.md), D07-001–030. Все пока не выполнены. Нужны реальные PG/session/CSRF/child/atomic race/fault и отдельные Nginx/browser доказательства; синтетический callback не заменяет commit. Независимое ревью технического контракта и rebase binding — до реализации.

Независимый технический gate: рецензент подтвердил возможность реализации при уточнённой привязке rebase и исправлении D07-007 (разрешённая editor-правка отличается от неожиданного изменения server draft hash). Ранее действующий legacy strict API не ослабляется. Прочие источники/metadata-only replay/session/atomicity/provenance приняты для ограниченной локальной реализации и последующего ревью кода.

## Итоговые фактические проверки

Все свидетельства — ignored work/dev07-draft-restore-20261031/. Это разные уровни проверки, не сумма закрытых AC.

| Набор | Факт | Свидетельство |
|---|---|---|
| Полная исправленная unit/integration/PG регрессия, включая17 новых HTTP,4 cancel,4 source и5 настоящих PG interleavings |290 PASS381.948с |all-tests-second.txt |
| Отдельный SQL/order source-admission с настоящим detector control |4 PASS7.307с |source-admission-first.txt |
| Прежний Chromium current-only cohort на новой сборке |16/16 PASS |browser-legacy-first/host-report.json |
| Новый Chromium draft/restore/rebase/cancel/unknown-result/in-flight typing |9/9 PASS, scope DRAFT_9 |browser-draft-second/host-report.json |
| Nginx anonymous-header-only: heavy401/413/TECL400 и small cancel413/TECL400 |PASS; не authorized максимум/slow proof |socket-report.json в обоих browser каталогах |

Один и тот же immutable app snapshot43a121a0-2ced-453f-ba5e-3bbefc121609 проверен в исправленном290 и обоих итоговых browser cohorts. Его source manifest SHA2564ea56d0b72b70aace5e8d445217669cc6399844640cd72750adc1156b74ff90f; все154app-файла после проверок совпадают с рабочей копией. Дополнительный freeze164файлов app/tools/runner/probe configuration: final-source-manifest.json, SHA256761fdc96ed94479dcecf94e36af01394ffa1669f5cdf3302472639f4a0511661. Итоговый новый probe0a2da7a146d32b2addbb5e2a38103e0aa4925bc5cd6811fbcdd537fca222ba6e, fixture11ccc78ab753793525437d0c2f95bc45568831c614cd079397fcec671894898c. Browser screenshots desktop/mobile просмотрены; горизонтального переполнения390px нет.

Оба итоговых browser writer остановлены до cleanup. Финальный cleanup: users/pages/versions/drafts/stages/pins=0, системный route225a6f2e-ac91-4af7-8656-6732c6b36c6d сохранён; version identity reservations215, media identities28, permanent receipts117, append-only audit301 сохранены. Стенд остановлен штатным wrapper с сохранением volumes/закрытых файлов.

Независимый рецензент подтвердил код, исправления и итоговые отчёты; открытых подтверждённых блокеров в этом локальном cohort нет. [Матрица D07](dev07-draft-restore-coverage.md) различает проверенные ветви и остаток:30новых методов и9browser groups не означают закрытие всех30D07, полного DEV-07/140AC или production admission.

## История диагностики (не итоговые PASS)

Первый backend checkpoint:16 настоящих PG/session/CSRF/child/engine HTTP-тестов PASS51.746с, immutable source e0a02fec-8302-43d0-ad03-bebef7e37afa. Локальное свидетельство: work/dev07-draft-restore-20261031/draft-http-first.txt. После него адресно сохранена прежняя формула fingerprint текущего режима для постоянных квитанций D-334; новые режимы связываются с source. Добавлены реальная legacy-replay regression и отдельный ранний cancel gate до CSRF. Новые21HTTP/admission,5конкурентных и browser прогоны ещё ожидаются; первыйPASS не объявляется результатом последнего source.

Первый полный286 завершился285PASS/1FAIL354.624с: устаревшее ожидание409 для forged source без selector; оно адресно исправлено на400, медиа409/state-invariants сохранены. Затем выявлена и исправлена загрузка полного payload до EditorSlot: middleware и default state читают только права/ID, большие source/check/write/editor/selected-state и сериализация захватывают slot раньше. Cancel имеет отдельный ранний owner/Page/JSON/16KiB/framing gate до CSRF, в Nginx отдельный16KiB buffered exact path; три больших пути не расширены.

Первый новый browser run остался FAIL без case-report: тестовый navigate оставлял once-dialog handler при навигации без confirm. При последующей отмене два handler принимали один dialog, второй Promise завершал Node вне общего catch. Диагностика первых4групп PASS имеет только scope DIAGNOSTIC_ONLY; отдельная реальная Chromium synthetic-проба показала7ожидаемых признаков до/после (не product proof). Исправлен только QA helper: named handler удаляется в finally, reject обрабатывается. Прежние FAIL/DIAG сохранены. Проверка nginx -t сначала выбрала default config; после чтения actual container Cmd проверена фактическая /preflight/nginx.conf, PASS. Ни одна из диагностических попыток не изменяла старый сайт/VPS.

Браузерная сборка0c4bec75dd92e6b809ce70c878879a0708d36924f0a03f313bcb34f823a08425,905046байт/49inputs; зависимости и ресурсы прежние. Эта сборка использована в обоих успешных итоговых browser cohorts.

## Остаток и продолжение

Stage→draft пока явно controlled capability409, без скрытого consume/перезаписи draft; stage→current прошёл отдельный положительный Save. Это временная граница когорты, не новое бизнес-ограничение. Продолжить DEV-07: protected media/узлы и reset оформления, общие Header/Footer/квоты, полноценный GUI больших прайсов/таблиц; незакрытые ветви D07 см. матрицу. Отдельно нужны authorized полные transport/compare GET/render, совокупная память/RSS/slow-abort/реальная сетевая конкуренция, другие браузеры. Прежний native advisory residual сохраняется. DEV-08/DEV-29 и production не начаты.
