# Контракт минимальной заявки и legal gate

Дата: 2026-11-16. Статус: **утверждённый scope D-1229; архитектурная реализация требует повторного review и REBUILD-Q002**.

Владелец ответом «Продолжай» принял рекомендованный вариант CRAR-Q001/Q002: одна минимальная заявка остаётся в MVP, но полностью default-off до LEGAL-01 и отдельного разрешения включения; срок хранения — 30 дней, досрочное удаление owner-only. Документ не разрешает принимать реальные данные сейчас.

## 1. Поля и источник истины

`ServiceRequest` принадлежит `requests` и содержит только:

- UUID `id`, одновременно submission operation ID;
- `created_at` server time;
- обязательные bounded `name`, normalized `phone`;
- необязательные bounded `vehicle_make`, `vehicle_model`, `vehicle_year`, `comment`;
- `consent_text_version`, SHA-256 утверждённого consent/privacy текста и `consented_at`;
- Telegram attempt outcome enum `NOT_ATTEMPTED|IN_PROGRESS|SENT|FAILED` и safe attempted timestamp без response body/ПД.

Нет `updated_at`, status, assignee, notes, CRM fields, processing history, email, attachments, IP/user-agent fingerprint или произвольного JSON. PostgreSQL row является единственным authority успешного приёма.

Единственные input limits: URL-encoded body 1..8,192 bytes; `name` 1..100 characters; raw `vehicle_make` и `vehicle_model` по 0..100, `vehicle_year` пустой либо ровно 4 ASCII digits, весь canonical vehicle text ≤300; `comment` 0..4,000; `consent_text_version` 1..64; phone после допустимого форматирования обязан стать `+7` и ровно 10 digits. Trusted ingress из §1.1 ограничивает один canonical client IP до 1 request/s с Nginx `burst=5`; Django повторяет body/field validation до записи. Эти границы и cap+1 входят в `QA-REQUEST-001`; отдельный throttle service/CAPTCHA не создаются.

### 1.1. Trusted client-IP boundary

Текущий deployment имеет ровно одну доверенную цепочку: public client подключается непосредственно к Nginx; CDN, load balancer и внешний reverse proxy отсутствуют. Только Nginx слушает public TCP. Django application server слушает один filesystem Unix socket, доступный Nginx service identity и deployment operator, но не public network; отдельного TCP listener у приложения нет.

Для request POST Nginx до proxying удаляет/не пересылает входные `Forwarded`, `X-Forwarded-For`, `X-Real-IP` и `X-Estakada-Client-IP`, затем выставляет ровно один внутренний `X-Estakada-Client-IP: $remote_addr`. Client не может своим header изменить `$remote_addr`. Throttle key — Nginx `$binary_remote_addr`; exact route использует `limit_req_zone` rate `1r/s` и `limit_req burst=5 nodelay`. Один admissible request плюс не более пяти excess requests проходят немедленно, следующий до refill получает constant `429`; он не достигает Django и не создаёт DB/audit/Telegram action.

Django не читает client identity из `Forwarded`, `X-Forwarded-For`, `X-Real-IP` или socket `REMOTE_ADDR`. На включённом request POST он требует ровно одно значение внутреннего header, canonical IPv4/IPv6 без port/zone/comma, длиной ≤45, и доверяет ему только потому, что production endpoint достижим исключительно через protected Unix socket. Missing, duplicate/list, malformed header или TCP/direct-app deployment mismatch даёт fail-closed `400 INVALID_INGRESS` до body parsing и mutation. IP используется только в ingress shared-memory bucket и текущем request context: он не сохраняется в ServiceRequest, AuditEvent, error/report или endpoint access log; query/body/header values также не логируются.

Любое будущее добавление CDN/load balancer/другого proxy запрещает просто включить forwarded-header trust. Оно требует отдельного owner-approved exact trusted-hop/CIDR contract и spoof tests; до этого request intake остаётся off. Redis, DB throttle table, fingerprint/cookie/device identity и reusable proxy-chain parser не создаются.

## 2. Default-off и LEGAL-01

До одновременного выполнения всех gates POST route не подключается, form controls не публикуются и реальные данные не принимаются:

1. владелец утверждает exact privacy/consent text и его version/hash;
2. текст сообщает purpose, fields, 30-day retention, доступ owner+staff и передачу копии в Telegram;
3. утверждены controller/contact details и процедура запроса удаления;
4. настроены production secrets Telegram и проверена private/no-log граница;
5. проходят security/privacy/retention/backup-restore tests;
6. владелец даёт отдельное актуальное разрешение включить intake.

Один feature setting допустим только как fail-closed deployment gate `SERVICE_REQUESTS_ENABLED=false`; это не multi-site feature framework. При false POST route отсутствует/404 и DB row/network attempt не создаются.

## 3. Приём и повтор

POST требует CSRF, exact form version, UUID submission ID, server-side validation и пройденный trusted-ingress throttle из §1.1. CAPTCHA не добавляется. Команда одной requests-owned transaction:

1. нормализует и валидирует поля/consent version;
2. по UUID проверяет existing row;
3. тот же UUID+тот же canonical fingerprint возвращает прежний accepted result без второй строки/Telegram;
4. тот же UUID с другими полями даёт conflict;
5. создаёт одну ServiceRequest и safe AuditEvent без ПД;
6. после успешного commit выполняет не более одной bounded Telegram-попытки.

DB commit означает success даже при Telegram failure. Клиент не получает transport details. Process crash между commit и callback может оставить `NOT_ATTEMPTED`; crash после claim может оставить `IN_PROGRESS`, то есть outcome unknown. Ни одно из этих состояний автоматически/вручную не повторяется. Владелец видит safe outcome в detail; resend не входит в MVP.

## 4. Telegram-only policy

Email отсутствует. Telegram adapter получает только после commit: request UUID/time, name, phone и заполненные vehicle/comment fields. Consent text/hash, IP, session, audit metadata и technical errors не отправляются. Bot token/chat ID — только secret environment/file; payload/Telegram response не логируются.

Перед сетью короткая transaction выполняет CAS `NOT_ATTEMPTED→IN_PROGRESS`; только победивший claimant отправляет сообщение. `IN_PROGRESS` никогда не claim-ится повторно. После terminal response отдельная короткая transaction меняет только `IN_PROGRESS→SENT|FAILED`. Ошибка финальной записи оставляет `IN_PROGRESS`; повтор запрещён. Concurrent callbacks/replayed POST не создают вторую попытку.

Transport использует только `https://api.telegram.org/bot<TOKEN>/sendMessage`, system trust store, proxy disabled, redirects forbidden, один total timeout 5 s и response body максимум 4096 bytes с exact JSON `ok=true`. Host/path/status/TLS/timeout/oversize/malformed response failure дают `FAILED` либо `IN_PROGRESS` при unknown outcome; token/chat ID/payload/response не входят в exception/log.

Гарантия — **at-most-once best effort**, не delivery. Она сознательно допускает `NOT_ATTEMPTED/IN_PROGRESS` при process/network/DB failure и не создаёт outbox, retry worker, manual resend или delivery receipt platform.

## 5. Закрытая админка и удаление

Owner и active staff читают list/detail read-only; ответы private/no-store, bounded pagination, без поиска по произвольному ПД. Только owner удаляет exact request после CSRF POST и актуального подтверждения UUID+created_at; повторный пароль не нужен. Employee delete/export отсутствуют.

Удаление использует request-specific ledger из раздела 6. Сначала durable tombstone становится authority, затем одна DB transaction обновляет ledger projection, удаляет ServiceRequest и пишет safe audit. Отдельное редактирование заявки отсутствует. Ledger/DB mismatch закрывает request list/intake до reconciliation.

## 6. Retention 30 дней

Закрытая retention-команда без пользовательских аргументов вычисляет один aware cutoff `now - 30 days` и выбирает только `created_at < cutoff`. Для bounded batch она сначала durable публикует UUID tombstones, затем одной DB transaction обновляет projection, удаляет exact rows и пишет safe audit. Exact boundary и более новые rows сохраняются. Успех выводит только count; failure — constant error. Scheduler/deploy требуют отдельного operational решения; до его готовности intake gate не открывается.

Deletion authority — один append-only canonical ledger вне PostgreSQL restore set. Запись содержит только monotonic sequence, request UUID, deleted_at, reason `OWNER|RETENTION`, previous hash и row hash. Owner-only DACL, exclusive lock, append+flush/fsync и hash-chain обязательны. Перед признанием tombstone durable exact ledger generation/digest синхронно копируется и проверяется в независимом зашифрованном backup location; если location/lock/fsync/verify недоступны, delete/retention не начинается.

PostgreSQL хранит только rebuildable projection ledger sequence/UUID для быстрых constraints. Если durable tombstone записан, а DB transaction отказала, tombstone остаётся authority; requests subsystem fail-closed до idempotent reconciliation. Ledger не очищается автоматически и хранится весь срок жизни deployment/старых backups; UUID+время не содержат содержимого заявки. Это исключает отдельный retention algorithm и риск раннего удаления tombstone.

Backup catalog фиксирует ledger generation+digest, но DB backup не считается свежей authority ledger. Restore выполняется только изолированно: восстановить DB → загрузить latest independently verified ledger с generation не меньше catalog → проверить hash-chain → удалить все matching ServiceRequest и rebuild projection одной transaction → доказать tombstoned rows0 → только затем HTTP/readiness open. Missing/stale/corrupt ledger блокирует restore/cutover.

## 7. Backup, transfer и logs

Requests/ledger никогда не входят в public manifest. Existing active rows переносятся только private DB→DB stream по `clean-rebuild-transfer-contract.md` и только если frozen baseline показывает rows>0 и владелец отдельно разрешил их перенос. Latest external ledger переносится/проверяется отдельно и применяется до target HTTP; passwords/requests/ledger не смешиваются в artifact.

Audit/technical logs содержат только request UUID, action, result code и counts; name/phone/vehicle/comment/consent text/Telegram payload отсутствуют. Backup/restore tests используют synthetic ПД.

## 8. Acceptance

- `REQUEST-AC-001`: при default-off form controls/POST/table writes/network attempts отсутствуют.
- `REQUEST-AC-002`: invalid/oversize/stale-consent/throttled request не пишет DB/audit/Telegram.
- `REQUEST-AC-003`: valid submission создаёт ровно одну row; same UUID+fingerprint replay не дублирует.
- `REQUEST-AC-004`: concurrent callbacks дают один CAS claim и максимум один network attempt; SENT/FAILED/NOT_ATTEMPTED/IN_PROGRESS не меняют DB acceptance success.
- `REQUEST-AC-005`: logs/audit/errors не содержат ПД или Telegram payload/response.
- `REQUEST-AC-006`: anonymous не читает; staff read-only; owner-only exact delete создаёт tombstone.
- `REQUEST-AC-007`: owner/retention delete требует durable local+independent ledger до DB delete; failure не начинает deletion, DB failure после ledger закрывается reconciliation.
- `REQUEST-AC-008`: restore требует latest valid ledger, tombstoned rows0 и rebuilt projection до HTTP open; missing/stale/corrupt ledger закрывает restore.
- `REQUEST-AC-009`: email/status/assignee/notes/history/export/manual resend/outbox/worker отсутствуют.
- `REQUEST-AC-010`: spoofed forwarded/internal headers не меняют Nginx `$binary_remote_addr`; missing/list/malformed internal identity или direct-app mismatch fail closed before body/DB/audit/network.
- `REQUEST-AC-011`: two distinct IPv4/IPv6 clients have independent 1r/s burst5 buckets; saturating A does not throttle B, excess gets constant429, and neither IP is persisted or logged.
