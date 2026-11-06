# REF-1 — инвентаризация текущей архитектуры

Дата: 2026-11-05. Статус: результат read-only анализа по D-597; целевой контракт вынесен в `docs/admin-architecture-v0.7.md`; продуктовый код, БД и окружение не изменялись.

## 1. Границы и метод

Проверены tracked-файлы, Django settings/URL, модели, миграции, runtime-imports, management-команды, окружение и тестовые области. Docker, PostgreSQL, секреты, ignored рабочие каталоги, старый сайт и VPS не открывались и не запускались. Поэтому документ фиксирует структуру кода и схемы миграций, но не утверждает фактическое число строк в локальной БД или файлов в MEDIA_ROOT.

## 2. Текущий runtime

Основной runtime — `app/estakada`. В `INSTALLED_APPS` включены Django auth/contenttypes/sessions и проектные `audit`, `content`, `accounts`, `media_library`, `page_versions`, `shared_content`, `page_editor`.

Middleware по порядку:

1. ранний `request_guard.ScannerMiddleware`;
2. стандартные Security/Session/Common;
3. `page_editor.EditorAdmissionMiddleware`;
4. `shared_content.SharedAdmissionMiddleware`;
5. CSRF и Authentication;
6. Clickjacking/CSP;
7. private cache/access и media body limit.

Корневой URL сейчас содержит только административные маршруты `/manage/...`: редактор, общие Header/Footer, медиатека, версии, вход/сотрудники/дерево. Полноценная публичная маршрутизация ещё не подключена. Это снижает риск рефакторинга: публичную выдачу, заявки и HTML fallback можно строить сразу по новой схеме.

Настройки уже сохраняют важные основы: `DEBUG=False`, PostgreSQL, TLS verification, bounded credential files, autoescape, CSRF/session cookie policy, CSP report-only, безопасный formatter, лимиты upload и закрытый `/manage/` namespace.

## 3. Размер областей

Статический подсчёт исходных строк Python/JS/HTML/CSS и файлов:

| Область | Файлов | Test-like | Строк | Вывод |
|---|---:|---:|---:|---|
| accounts | 33 | 1 | 1 339 | Ядро прав небольшое, session/resource accounting можно сократить |
| audit | 11 | 1 | 580 | Полезная компактная основа |
| content | 17 | 5 | 2 205 | Page/Route и начатый DEV-29 можно сохранить |
| editor_runtime | 6 | 2 | 886 | Отдельный child runtime — кандидат на удаление после упрощения редактора |
| media_library | 21 | 2 | 1 844 | Ядро оставить, permanent reservations упростить |
| page_editor | 60 | 25 | 38 794 | Самая крупная область; значительная часть — bundle и специализированные политики/тесты |
| page_versions | 34 | 5 | 2 241 | Ядро версий оставить, вспомогательные lifecycle-модели сократить |
| request_guard | 6 | 1 | 563 | Оставить как компактную защиту |
| shared_content | 52 | 12 | 9 090 | Главный кандидат на замену простой DB-реализацией |

Отдельно существуют 31 файл `trust/**`, 4 файла `environment/trust/**`, 52 trust-related инструмента и 59 файлов acceptance-harness. Они не равны production-функциям сайта.

## 4. Карта моделей и решение

### 4.1. Оставить

| Область | Модели/механизмы | Причина |
|---|---|---|
| content | `Page`, `Route`, UUID, tree/URL constraints | Основное состояние CMS и точные legacy URL |
| accounts | `UserProfile`, `PageGrant`, простой `LoginThrottle` | Две роли и права на страницы/поля |
| audit | `AuditEvent`, безопасный formatter/service | Важные действия и ошибки без ПД/секретов |
| page_versions | `PageRevision`, `PageContentState`, `RevisionMetadata`, `RevisionProtection`, `OwnerDraft` | Автоматические/ручные версии, Stable и черновик |
| media | `MediaFolder`, `PageMediaHome`, `Asset`, `AssetFile`, `AssetUsage` | Проверенные файлы и ссылки версий/страниц |
| request_guard | ранний scanner middleware/noise filter | Дешёвый отказ до сессии/БД |

### 4.2. Упростить или заменить

| Текущее | Целевое состояние | Условие удаления старого |
|---|---|---|
| `AuthSession`, `AuthResourceState`, lower-bound counters | стандартные Django sessions + один `UserProfile.generation`, проверяемый на каждом закрытом запросе; реальный rate limit | REF-AC-031 проходит |
| `IdentityReservation`, `VersionBasePin`, многофазный `RestoreStage`, универсальный page `OperationReceipt` | одна транзакционная команда save/restore; DB constraints; receipt только где нужен публичный retry | версии/restore REF-AC проходят и данные сверены |
| media `IdentityReservation`, `FileKeyReservation` | UUID+UNIQUE, проверенный storage key и безопасная delete-команда | media/delete REF-AC проходят |
| `editor_runtime` child processing и множество carrier/admission слоёв | фиксированные поля и блоки, один server-side sanitizer/renderer | editor REF-AC-029 и XSS проходят |
| глобальный `CONTENT_LOCK` для всех записей | точечные `select_for_update()` и ограничения БД | concurrency/integrity tests проходят |

### 4.3. Shared Header/Footer

Сейчас приложение содержит девять основных shared-моделей: identity reservation, block, revision, draft, restore stage, base pin, receipt, cleanup job и budget. Кроме БД используются файловые blobs, journal, reservations, quota calibration, provenance, cleanup/reconcile и отдельный admission middleware. URL содержит edit/check/draft/apply/history/version/compare/stage/result/cleanup/diagnostics/reconcile.

Целевой минимальный набор:

- `SharedBlock` (`header`/`footer`, current revision);
- `SharedRevision` с inline нормализованным содержимым PostgreSQL;
- при необходимости один `SharedDraft` владельца;
- restore создаёт новую revision одной транзакцией;
- те же media usages, server-side sanitizer, audit и owner permissions.

К удалению после миграции: shared identity reservations, restore stages, pins, receipts, cleanup jobs, budget, journal, filesystem storage, reservations, quota, profiles, diagnostics/reconcile URL и `SharedAdmissionMiddleware`.

Существующие миграции `0001`–`0005` создают и расширяют эти данные. Безопасный путь — не переписывать применённые миграции: добавить новые forward migrations, скопировать/проверить inline-содержимое, переключить runtime, затем отдельной миграцией удалить старые поля/таблицы только после REF-Q004.

## 5. TRUST и тяжёлая обвязка

`trust/**` — отдельный Django-проект с собственными моделями Head, Credential, Operation, RoutePolicy, RequestTombstone, RecoveryReceipt и AdmissionPolicy, собственными URL `/v1/...`, PostgreSQL/ingress compose и management-командами.

Статический поиск не нашёл импорта `trust` из основного Django-приложения. Связи находятся в отдельном `environment/trust`, `scripts/local-trust.ps1` и trust-related `tools`. Следовательно:

- TRUST не нужен для загрузки текущего `app/estakada`;
- удаление возможно отдельной волной после подтверждения отсутствия CI/scripts зависимости;
- `trust/**`, `environment/trust/**`, 52 инструмента и связанные acceptance contracts — кандидаты REF-7;
- Git-история заменяет копию исходника в `archive/`.

DEV-29 checkpoints в tracked `tools/dev29` представлены тремя файлами; многочисленная историческая обвязка также распределена по trust tools и документам. Она не должна входить в целевой runtime/CI.

## 6. Новые простые области — миграция старых данных не нужна

### 6.1. Заявки

Модели заявок в основном приложении сейчас отсутствуют. Можно сразу создать минимальную схему:

- `ServiceRequest`: UUID, `created_at`, обязательные имя/телефон/согласие и согласованные необязательные поля;
- `RequestSettings`: singleton email получателя; Telegram destination/token и SMTP secrets только env;
- без status, assignee, notes, history, `updated_at`, CRM events и delivery-outbox;
- owner и employees имеют read-only доступ; delete/configure — только `nesadmin`;
- уведомления email/Telegram запускаются сразу после DB commit независимо; DB — источник истины.
- внешний append-only request deletion ledger хранит только UUID+время без ПД; он нужен только для reconciliation после restore и не является общей tombstone-платформой.

До LEGAL-01 используются только синтетические данные.

### 6.2. HTML-резерв

Текущего production static reserve нет. Нужны owner-only build action, staging directory, validator, atomic `current`/`previous`, manifest/fingerprint и stale indicator. Nginx fallback проектируется без TRUST/head/state machine и только для public GET/HEAD на upstream failure/502/503/504.

### 6.3. Backup/restore

Production `BackupPoint` в основном app отсутствует. Целевой механизм — эксплуатационные команды/скрипты для одного локального и одного внешнего зашифрованного места, по два проверенных поколения `current`/`previous` PostgreSQL+media, checksums, краткий safe log, request deletion ledger и ручной restore runbook. Расписание требует отдельного решения.

## 7. URL и middleware после рефакторинга

Предлагаемый обязательный runtime:

- оставить scanner, Django security/session/CSRF/auth, CSP/private cache/access и media limit;
- заменить editor middleware одним bounded validator либо обычными view-level проверками;
- удалить shared admission middleware после переключения shared editor;
- добавить закрытый `/manage/requests/` read-only для owner/employee и owner-only delete/settings POST;
- добавить owner-only HTML build/status;
- публичные URL подключить через Page/Route без TRUST per-request gate;
- readiness — закрытый process+bounded `SELECT 1`, без state machine.

## 8. Тесты и инструменты

Сейчас acceptance содержит 40 `*.spec.js` и 59 файлов всего. После REF-3–REF-7:

Оставить/переписать под REF-AC: auth, foundation security, content lifecycle, editor safety/boundaries, media, public, URL, versions, form/request, fallback/HTML и restore smoke.

Удалить после замены: service quota, shared block/reservation/cleanup contracts, log quota/delete complexity, background jobs старой архитектуры, TRUST/driver safety и backup-platform contracts. Удаление старого теста допустимо только вместе с удаляемой функцией и после появления теста нового пользовательского правила.

Регулярный набор: unit+integration, полный Chromium, сокращённые Firefox/WebKit; security checks не сокращаются.

## 9. Порядок миграции без потери данных

1. Перед первым кодовым изменением получить REF-Q002/REF-Q003.
2. Зафиксировать read-only counts/fingerprints фактической тестовой БД и media только в отдельно разрешённом локальном запуске.
3. Добавлять новую схему рядом со старой; применённые migrations не переписывать.
4. Копировать shared inline data и связи media в транзакции; старые таблицы оставить read-only.
5. Переключить чтение, затем запись; пройти связанные REF-AC и сверку содержимого.
6. Упростить versions/accounts/media по одному модулю, не параллельно.
7. Добавить новые requests/HTML/backup области сразу по целевой схеме.
8. Только REF-Q004 разрешает drop таблиц, удаление файлов, compose, tools, dependencies и старых тестов.
9. После каждого удаления подтвердить отсутствие import/settings/URL/CI/env references.

## 10. Открытые факты перед реализацией

- фактические row counts и наличие file-backed shared revisions неизвестны без разрешённого DB/media read;
- точный production hosting/mail/Telegram/backup destination и расписание не выбраны;
- состав ПД в email/Telegram и юридические тексты ждут LEGAL-01;
- формат structured editor по каждому Page.Kind должен быть утверждён в REF-Q002;
- точный retention заявок, deletion-ledger записей и зашифрованных backup требует правового решения;
- финальный список удаляемых files/dependencies формируется после архитектурного review и static dependency check.

## 11. Вывод REF-1

Рефакторинг технически возможен без переписывания проекта с нуля. Наименее рискованный путь: сохранить core Page/Route/versions/media/audit/permissions, заменить shared subsystem и editor поэтапно, новые requests/HTML/backup сделать сразу простыми, затем удалить независимый TRUST и доказательную обвязку. Главный риск потери данных — shared file-backed revisions; он закрывается add-copy-verify-switch-remove, а не удалением на первом шаге.
