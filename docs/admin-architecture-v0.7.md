# Упрощённая архитектура системы v0.7

Дата: 2026-11-05. Статус: кандидат после REF-1/REF-2; требует независимого архитектурного ревью и решения REF-Q002 до изменения продуктового кода.

Эта версия полностью заменяет архитектурный контракт v0.6 в `docs/admin-architecture-draft.md`. Старый документ сохраняется только как история принятых ранее решений и не задаёт реализацию после D-589–D-598.

## 1. Назначение и границы

Первая версия — небольшая CMS автосервиса: один модульный Django-проект, одна PostgreSQL, серверные HTML/CSS-шаблоны, ограниченный JavaScript, одно media-хранилище и Nginx. Отдельные TRUST/head/admission сервисы, собственная backup-платформа, CRM, универсальный page builder и доказательные runtime-протоколы не входят в целевую архитектуру.

Неизменные требования:

- точные старые URL, структура и тексты;
- побайтная сохранность 214 legacy originals галереи;
- роли `nesadmin` и сотрудника, серверные права;
- версии, Stable, восстановление и лимит ordinary;
- безопасные media, SQLi/scanner/XSS/CSRF защита;
- аудит важных действий и технические журналы;
- резервная HTML-версия и полноценные backup PostgreSQL+media;
- реальные заявки только после LEGAL-01.

## 2. Компоненты runtime

1. Nginx: TLS, static/media, сетевые лимиты и HTML fallback.
2. Django: admin/public rendering, права, редактор, заявки и команды обслуживания.
3. PostgreSQL: авторитетное состояние страниц, версий, прав, заявок и аудита.
4. Media directory: файлы вне Git с метаданными/ссылками в PostgreSQL.
5. Operations directory: HTML `current/previous`, encrypted backup sets и request deletion ledger; не является публично редактируемым содержимым.

PostgreSQL закрыта от интернета. Секреты поставляются окружением/secret files и не хранятся в Git или контентных настройках.

## 3. Данные

### Контент

- `Page`, `Route`: дерево, тип, порядок, публикация и точные URL.
- `PageRevision`, `PageContentState`: immutable content revisions и current.
- `RevisionMetadata`, `RevisionProtection`: ручные метаданные и Stable.
- `OwnerDraft`: один закрытый черновик владельца при необходимости.
- `SharedBlock`, `SharedRevision`, `SharedDraft`: только Header/Footer, inline в PostgreSQL; без filesystem journal/quota/admission.

Restore всегда создаёт новую revision. Сотрудник меняет только разрешённые поля, никогда URL/структуру/Stable/чужой draft. Удаление всей страницы с историей — только `nesadmin` с актуальным подтверждением; поддерево не удаляется неявно.

### Пользователи и права

- стандартные Django User/session;
- `UserProfile(role, generation)`;
- `PageGrant` с разрешёнными полями;
- простой `LoginThrottle`.

При входе current generation записывается в session. Смена/сброс пароля, роли, активности или PageGrant увеличивает generation; старая session теряет доступ на следующем закрытом запросе. Отдельный реестр `AuthSession` не нужен.

### Медиа

- `MediaFolder`, `PageMediaHome`, `Asset`, `AssetFile`, `AssetUsage`;
- upload limits, decode/format validation, safe names and paths;
- usage защищает current, ordinary/manual/Stable, draft, Header/Footer и `current/previous` HTML reserve;
- 214 legacy originals сверяются по SHA и никогда не преобразуются.

Permanent UUID/file-key reservation tables не нужны; UUID+UNIQUE и service commands обеспечивают идентичность. Физическое удаление допускается только после повторной проверки всех usages.

### Заявки

`ServiceRequest` содержит UUID, `created_at`, согласованные поля и доказательство согласия. Нет status, assignee, notes, history или `updated_at`.

`RequestSettings` содержит один email, который меняет только `nesadmin`. SMTP credentials, Telegram bot token и chat ID находятся только в окружении.

Отправка формы:

1. проверить CSRF/rate limit/validation/idempotency;
2. атомарно сохранить заявку;
3. сразу после commit независимо попытаться отправить email и Telegram;
4. ошибка канала не удаляет заявку и не блокирует другой канал; в технический журнал не попадают ПД.

`nesadmin` и сотрудники видят заявки read-only с `private, no-store`. Настройки и удаление доступны только `nesadmin`. Delete требует owner session, CSRF, POST и подтверждение конкретной записи, но не повторный пароль.

Перед DB-delete UUID+время без ПД durable добавляются во внешний append-only request deletion ledger. Если ledger недоступен, delete не начинается. Restore применяет ledger до открытия сайта.

## 4. Редактор

Тип страницы определяет фиксированную схему: вводный текст, основной текст, цены, таблицы, изображения и небольшой утверждённый набор блоков. Произвольный layout, Django templates, Python, JavaScript и неизвестные HTML/attributes запрещены.

Preview и public используют один server-side normalizer/sanitizer/renderer. Отдельный child runtime и carrier/admission слои удаляются после прохождения REF-AC-029.

## 5. Транзакции

- `transaction.atomic()` на законченный domain command;
- `select_for_update()` только затрагиваемых Page/Route/revision/media/user rows;
- DB UNIQUE/CHECK/FK constraints;
- глобальный content advisory lock удаляется после concurrency tests;
- idempotency receipt сохраняется только для публичной заявки/другого запроса с потерянным ответом;
- owner-only команды одной транзакции не получают универсальный receipt protocol.

Ошибка не оставляет частично опубликованное состояние. Неизвестный исход не выдаётся за успех.

## 6. Логи

В PostgreSQL хранятся bounded `AuditEvent`: входы/отказы, права, страницы, версии/Stable, media, заявки, HTML build, backup/restore result и критические security events. Тела заявок/страниц, телефоны, passwords, tokens, cookies и request bodies не копируются.

Django/Nginx/PostgreSQL используют стандартные технические журналы с обычной ротацией и одним общим пределом, выбираемым перед deployment. `nesadmin` видит фильтруемый аудит и краткие технические ошибки/результаты обслуживания. Нет девяти физических потоков, segment manifests, LogReadCursor, ручного удаления категории, reconciliation или Telegram Outbox логов.

Известный scanner noise агрегируется ранним middleware до session/DB. Отказ technical log наблюдаем через stderr/service supervisor и не превращает безопасный ответ в утечку.

## 7. Резервный HTML

Только `nesadmin` вручную запускает build. Django рендерит разрешённые public GET во staging, проверяет полноту, private-data absence, ссылки и manifest; только полный PASS атомарно заменяет `current`, прежний становится `previous`. После публикации резерв помечается stale, но не собирается автоматически.

Nginx fallback применим только к public GET/HEAD при upstream failure/502/503/504. POST, `/manage/`, private paths и normal 404 не подменяются. Форма не принимает данные и предлагает согласованный контакт без ложного success. Возврат к Django автоматический после восстановления upstream.

## 8. Backup и restore

Отдельная эксплуатационная команда по согласованному позже расписанию создаёт PostgreSQL+media+manifest/checksums.

- одно локальное место: `current` и `previous` проверенные поколения;
- одно внешнее зашифрованное место: `current` и `previous`;
- новая копия не вытесняет previous до проверки;
- secrets хранятся отдельно;
- в админке только краткий последний result, без BackupPoint и shell execution.

Restore выполняется вручную по runbook сначала в изолированную DB/media: checksums, schema/migrations, counts, request deletion ledger и smoke. Production меняется только по отдельному разрешению владельца. Автоматического DB rollback и подписанного внешнего исполнителя нет.

Retention backup/ledger и обращение с ПД утверждаются LEGAL-01. Ключ внешнего шифрования проверяется вне рабочего сервера.

## 9. Readiness и отказ

Закрытый readiness проверяет процесс и bounded параметризованный `SELECT 1` с timeout. Он ничего не записывает, не раскрывает diagnostics и не управляет переключением/restore. Отдельный health service, streak/state machine и signed admission отсутствуют.

Отказ PostgreSQL делает динамические операции недоступными; public GET может получить последний исправный HTML. Отказ email/Telegram не теряет DB-заявку. Отказ backup не удаляет last good. Заполненный диск/rotation failure наблюдаемы.

## 10. Проверки и удаление старого кода

Авторитетный набор — REF-AC-001–033 из `docs/refactoring-acceptance.md`. Security checks SQLi/scanner/XSS/CSRF/permissions/uploads не сокращаются.

После прохождения замен и REF-Q004 из рабочей ветки удаляются:

- `trust/**`, `environment/trust/**`, trust tools/tests;
- shared journal/storage/reservations/quota/profiles/cleanup/diagnostics и middleware;
- старые session/resource accounting, identity reservations и универсальные receipts;
- old editor child/carrier/admission paths;
- obsolete acceptance contracts, compose/env/settings/dependencies.

Старый код не копируется в repository archive: восстановление обеспечивает Git. Применённые migrations не переписываются; новые migrations выполняют add-copy-verify-switch, а drop разрешён только REF-Q004.

## 11. Ворота

- REF-Q001: выполнено D-597, только документы REF-1/REF-2.
- REF-Q002: независимое APPROVED архитектуры v0.7, inventory и REF-AC; согласование владельцем точной схемы/миграции.
- REF-Q003: разрешение небольших кодовых инкрементов REF-3–REF-6.
- REF-Q004: отдельное разрешение удаления старого кода/таблиц/config/tests после доказанной замены.
- Production остаётся отдельным этапом 11.
