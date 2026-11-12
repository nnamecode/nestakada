# DEV-13 — минимальный план реализации заявок

Дата: 2026-11-12. Статус: `DEV13-IMP-001–008` завершены локально по D-865; repeat independent code review `APPROVED`, P1/P2/P3=0. Реальные ПД/credentials/network/live и production включение остаются отдельными LEGAL/launch gates.

Основание: утверждённый D-856 scope, исправления D-857 и repeat scope review APPROVED D-858. План функционально закрывает прежние DEV-13/14/16 одним инкрементом. Реальные ПД, реальные внешние отправки, live/VPS/production и LEGAL-зависимый payload не разрешены.

## 1. Архитектурная граница

Добавляется одно обычное Django-приложение `service_requests` в существующий процесс и PostgreSQL. Оно переиспользует:

- `accounts.views.gate` и `accounts.services.is_owner` для закрытых прав;
- Django CSRF/session/signing/ORM/templates/email utilities;
- `audit.services.record_event` с `Source.NOTIFICATION` и существующими категориями/результатами;
- существующие public renderer/CSP/CSS и `/manage/` namespace;
- writable state volume `/var/lib/estakada` для bounded deletion ledger.

Не добавляются API, Django admin, cache, broker, queue/outbox, worker, scheduler, отдельный процесс, JavaScript формы, новая библиотека или сетевой сервис. Playwright не используется.

## 2. Точная минимальная схема

`service_requests.ServiceRequest`:

- `id`: UUID primary key, `default=uuid4`, не показывается посетителю;
- `created_at`: `DateTimeField(auto_now_add=True, db_index=True)`, единственная показываемая дата;
- `source`: choices `home|contacts`;
- `name`: `CharField(max_length=100)`;
- `phone`: `CharField(max_length=12)`, canonical `+7` и десять цифр;
- `car`: `CharField(max_length=300, blank=True)`;
- `comment`: `CharField(max_length=4000, blank=True)`; PostgreSQL enforce the agreed bound directly while the template still renders a textarea;
- `consent_version`: `CharField(max_length=64)`, до LEGAL-01 только фиксированный synthetic marker; это не объявляется окончательным юридическим доказательством;
- `intent_digest`: lowercase SHA-256 hex, `CharField(max_length=64, unique=True, editable=False)`.

DB constraints фиксируют известный source, exact phone pattern, непустые name/consent version и exact digest; composite index поддерживает `-created_at,-id`. `status`, `assignee`, `notes`, history, `updated_at` и delivery state отсутствуют.

`service_requests.RequestSettings`:

- singleton row с PK `1` и DB check `id=1`;
- `recipient_email`: `EmailField(max_length=254, blank=True)`;
- никаких SMTP/Telegram secrets/destination и временных полей в БД.

Одна новая миграция `service_requests/migrations/0001_initial.py`; существующие миграции не переписываются.

## 3. Публичный протокол без receipt-платформы

- Формы выводятся только для опубликованных `/` и `/contacts`; source вычисляется сервером из exact canonical route, а не доверяется отдельному полю пользователя.
- Base setting `SERVICE_REQUEST_INTAKE_ENABLED=False`. Synthetic integration tests включают его только через `override_settings`; local/live profile сам его не включает. До LEGAL-01 обычный экран показывает отключённую форму/нейтральный контактный fallback и не выдаёт рабочий intent.
- При включённом synthetic profile GET выдаёт Django-signed intent с random 128-bit nonce, exact source, synthetic consent version и issued-at. Срок проверки — 30 минут; secret/raw intent не журналируется и не пишется в URL. Exact home/contacts с активной формой обходят общий content-only ETag/304 path: всегда полный ответ с `Cache-Control: private, no-store` и `Vary: Cookie`. При default-off существующий public cache/ETag path не меняется. Для этого existing `shared_content.public_views.html_response` получает только узкий флаг dynamic-private, а не новую cache subsystem.
- POST endpoint — один exact `/request/submit/`, `application/x-www-form-urlencoded`, CSRF, body не более 8 KiB, allowlist и ровно одно значение каждого поля. Малый exact-path `RequestBodyLimitMiddleware` стоит перед CSRF, требует корректный numeric `Content-Length` `0..8192`, bounded читает и caches raw body и отклоняет mismatch/oversize/неподдерживаемый content type до `request.POST`; Nginx остаётся вторым пределом. Разрешены только `name`, `phone`, `car`, `comment`, `consent`, `intent` и CSRF.
- Имя и optional text нормализуются сервером с понятными whitespace/control/NUL rules; телефон принимает только согласованные формы `+7`/`8` со скобками, пробелами и дефисами и сохраняется как `+7XXXXXXXXXX`.
- Внутри `transaction.atomic()` выполняется INSERT с unique digest. Nested savepoint ловит только unique conflict digest; winner определяется фактом успешной вставки. Concurrent/duplicate loser читает существование digest, возвращает тот же нейтральный success и не получает/не раскрывает request UUID.
- Только insert winner после commit последовательно вызывает два независимых bounded transport adapters. Повтор accepted intent не вызывает их снова. Crash после commit до вызова может оставить уведомление недоставленным; без outbox это принятый честный предел.
- Результат — server-rendered `200` с `Cache-Control: no-store`; refresh/retry того же POST безопасен. Ошибки полей также `no-store`, сохраняют только безопасно экранированный ввод и не создают row/notification/audit с ПД.

Старые TEST-04 receipt/cache/24-hour contracts не реализуются: они относятся к заменённой тяжёлой архитектуре. Нормативны REF-AC-022–026/030 и DEV13-AT-001–010; LEGAL-зависимые consent/payload части остаются partial/deferred.

## 4. Уведомления

`service_requests.notifications` имеет только закрытый fixed profile selector:

- `disabled` — fail-closed default;
- `synthetic` — два переданных тестом фиксированных in-process sinks, без сети;
- `live` — код пути Django SMTP и Telegram HTTPS на fixed API host, но настройка отвергается без отдельного `SERVICE_REQUEST_LEGAL_PROFILE` и bounded credential files. До выдачи live intent fail-closed проверяются exact approved LEGAL marker, непустой owner email и полная конфигурация обоих transports. В рамках DEV-13 live profile не включается и реальные credentials не создаются.

Нельзя задавать import path/callback/URL из окружения. SMTP password и Telegram bot token читаются только из bounded `/run/secrets` files существующим credential pattern; SMTP host/port/TLS имеют закрытую схему, Telegram chat ID — bounded env value. Telegram использует system TLS verification, exact `api.telegram.org` host и exact Bot API path, redirects off, environment proxies off, response body cap 4096 bytes и closed status/JSON parsing; URL/token и exception text никогда не журналируются. Telegram не использует HTML/Markdown parse mode. Email subject фиксирован кодом и не содержит user input. Timeout каждого канала не более 5 секунд.

До LEGAL-01 synthetic payload имеет marker и синтетические поля только в тесте. Финальный реальный состав не фиксируется DEV-13. Оба транспорта вызываются отдельными bounded guards, которые ловят ожидаемые и неожиданные `Exception` в своей границе и сначала собирают два результата; второй канал всегда вызывается после ошибки первого. Затем audit attempts выполняются отдельно для каждого результата. Audit failure не отменяет второй transport, не выходит в публичный response после commit и даёт только fixed safe technical fallback code через существующий formatter, без exception text/ПД. В структурированный аудит попадают только fixed code/channel result без recipient, request UUID, payload, phone, comment, exception text или credential path.

## 5. Закрытый раздел

Маршруты внутри `/manage/requests/`:

- GET списка: owner и активный employee, 25 строк, `-created_at,-id`, только bounded page number;
- GET карточки: те же роли; autoescaped original fields и одна дата `created_at` в Europe/Moscow;
- GET/POST settings: только owner; один recipient email, allowlist body, CSRF, audit, safe validation;
- GET delete confirmation и POST delete одной UUID: только owner. Повторный пароль, bulk action, edit/export/search отсутствуют.

Все ответы проходят existing `gate`, `private, no-store` и `Vary: Cookie`. Скрытие ссылки/кнопки дополняет, но не заменяет direct server permission. Dashboard получает одну ссылку «Заявки» для owner и employee; settings/delete видимы только owner.

## 6. Малый deletion ledger

Ledger — exact directory `SERVICE_REQUEST_DELETION_LEDGER_ROOT`, local default `/var/lib/estakada/request-deletions`, внутри существующего state volume. Production обязан смонтировать его как отдельное durable external storage до launch; потеря host/state не должна терять ledger вместе с восстанавливаемой DB-копией. Это append-only set immutable файлов `<request-uuid>.deleted`, а не БД/JSON-каталог/общая tombstone platform.

- Production Linux root открывается один раз как trusted directory fd с `O_DIRECTORY|O_NOFOLLOW`; `fstat` требует owner=current runtime UID и mode `0700` без group/other bits. Unsupported safe primitives закрывают operation ошибкой; обычный path-open fallback запрещён. Имя строится только из parsed UUID, а entry открывается/читается относительно удерживаемого directory fd.
- Первая запись создаётся относительно fd с `O_CREAT|O_EXCL|O_NOFOLLOW` mode `0600`, содержит exact schema marker, UUID и UTC deletion time без ПД, максимум 128 bytes; file и directory fsync выполняются до DB-delete.
- Существующая валидная запись того же UUID считается идемпотентным успехом; malformed/conflicting entry закрывает delete безопасной ошибкой.
- Owner delete берёт row lock, durable-записывает ledger, удаляет row и пишет audit в одной DB transaction. Fault после ledger/до commit оставляет row+ledger; повтор завершает delete. Fault после commit/до response даёт no row+ledger; повтор подтверждает уже достигнутое terminal state. No row+no ledger — 404, не ложный success.
- Management command `reconcile_request_deletions` через тот же held directory fd принимает максимум 10,000 canonical entries/1,280,000 total bytes и удаляет совпавшие restored rows DB batches максимум по 500 до открытия сайта. Unknown filename/type, symlink, malformed/over-cap ledger завершает command non-zero и блокирует restore opening.
- Ledger не удаляется и не попадает в DB+media backup. Срок его очистки и production restore wiring остаются LEGAL-01/launch gate; integration test доказывает synthetic old-backup reconciliation без изменения production.

## 7. Точные изменения по срезам

### DEV13-IMP-001 — schema и pure policy

- создать app/models/migration, pure validators/normalizers и signed intent parser;
- добавить app в `INSTALLED_APPS`, все feature flags default-off;
- tests-first: limits, Unicode/control/NUL, phone matrix, intent tamper/source/30-minute boundary, DB constraints/unique digest;
- evidence: focused Django tests, `makemigrations --check --dry-run`, `check`, diff check.

### DEV13-IMP-002 — public render и atomic intake

- добавить fixed POST route до public catch-all;
- передать form DTO в existing public renderer только для exact home/contacts и добавить один autoescaped partial/CSS;
- реализовать insert winner/loser без receipt table и no-store responses;
- tests: DEV13-AT-001/002/003/010, CSRF/method/content-type/body/unknown+duplicate fields, pre-CSRF missing/invalid/mismatched/oversize Content-Length, concurrent PostgreSQL insert, multi-client ETag/cache isolation, no UUID/PII in response/log.

### DEV13-IMP-003 — два независимых транспорта

- fixed disabled/synthetic/live adapter boundary без новой dependency;
- insert winner calls only; loser sends zero; email/Telegram success/failure matrix and timeout;
- safe audit codes через existing audit service;
- tests: DEV13-AT-004 и partial REF-AC-023/024, transport+audit failure matrix включая unexpected exception; никакой реальной сети/credentials.

### DEV13-IMP-004 — read-only admin и owner setting

- list/detail/settings routes/templates и dashboard link;
- page cap25, stable order, bounded page parser, direct role checks;
- tests: DEV13-AT-005/006 и REF-AC-022/025/026 relevant branch; anonymous/disabled employee/employee POST/owner, private no-store, XSS autoescape, no search/export/mutation.

### DEV13-IMP-005 — convergent owner delete

- immutable per-UUID ledger entries через held directory fd, exact caps, owner confirm/POST service and reconciliation command;
- fault seams только для tests, не runtime settings/imports;
- tests: DEV13-AT-007/008, REF-AC-025/030, concurrent/replay, ledger unavailable/malformed, fault before/after commit, restore reconciliation, CSRF/GET/employee denied.

### DEV13-IMP-006 — security/ingress/fallback contracts

- добавить exact `/request/submit/` small-body/rate-limit location в local Nginx config; проверяется config contract, production включение остаётся launch gate;
- явно расширить public CSP директивой `form-action 'self'`, сохранив остальные текущие directives;
- подтвердить, что HTML reserve содержит disabled form и не включает intent/CSRF/ПД/ложный success;
- фактический HTML builder ещё отсутствует в текущем runtime: DEV-13 подтверждает default-off render contract, а его подключение к будущей ручной сборке остаётся обязательной проверкой DEV-15/DEV-20, не ложным PASS;
- tests: DEV13-AT-009/010, SQLi/XSS/scanner payloads, exact CSP `form-action 'self'` и regression остальных directives, sitemap/cache/log exclusions, request body caps, Telegram redirects/proxy-env/TLS/oversize response fail-closed.

### DEV13-IMP-007 — combined evidence

- fresh immutable foundation snapshot после остановки текущего старого snapshot;
- focused DEV-13 package, affected accounts/audit/content/public/request-guard tests, затем полный guard;
- Django check, no missing migration, PowerShell/Nginx syntax/config, no external network/secret scan, `git diff --check`;
- foundation stopped after checks; persistent/live/publication/VPS отсутствуют.

### DEV13-IMP-008 — независимое code review

- review correctness, permissions, SQLi/XSS/CSRF, PII/logging, concurrency/crash gaps, ledger/restore, notification boundaries and scope creep;
- исправить findings, повторить affected/full evidence и получить final `APPROVED` до завершения DEV-13.

## 8. Приёмочная связь

| Contract | Implementation |
|---|---|
| DEV13-AT-001/002 | IMP-001/002 |
| DEV13-AT-003 | IMP-001/002/003 |
| DEV13-AT-004 | IMP-003 |
| DEV13-AT-005/006 | IMP-004 |
| DEV13-AT-007/008 | IMP-005 |
| DEV13-AT-009/010 | IMP-002/006 |
| REF-AC-022/025/026 | IMP-002/004/005, synthetic |
| REF-AC-023/024 | IMP-003, payload partial до LEGAL-01 |
| REF-AC-030 | IMP-005, synthetic restore integration; production wiring later gate |

## 9. Стоп-условия

Работа останавливается владельцу при втором эквивалентном отказе без нового свидетельства, необходимости реальной сети/секретов/ПД, изменении LEGAL payload, production/VPS, новой зависимости или потребности вернуть queue/outbox/worker. Эти случаи не разрешаются словом «техническая деталь».

После `APPROVED` plan review требуется отдельное разрешение владельца на `DEV13-IMP-001–008`.
