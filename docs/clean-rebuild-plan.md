# План чистой пересборки с выборочным переносом

Дата: 2026-11-17. Статус: **REBUILD-2 COMPLETE D-1428; result review APPROVED 0/0/0; progress `27–30%`, remaining `23/30/44h`; one source blocker remains deferred to REBUILD-3 freeze; REBUILD-3 requires a separate scope/acceptance gate**.

Основание: D-1217 остановил template-first ремонт; D-1218/D-1219 сократили систему до простого Django-сайта и `current + previous`; D-1220 выбрал clean rebuild, D-1221 — прагматичные module boundaries, D-1222 — обязательный professional review, D-1223 — только Estakada без multi-site/Dozvo-кода, D-1224 — исходные findings. D-1225–D-1249 были remediation-кандидатами и закрыты независимым CRAR-REPEAT-003; этот verdict не заменяет согласование владельца и не разрешает реализацию. Новый runtime переносит только проверенные данные, дизайн, маленькие изолированные функции и полезные пользовательские проверки.

## 1. Что означает «с нуля»

С нуля создаются:

- новый Django runtime в отдельном source root;
- новая чистая схема PostgreSQL;
- новые модели и однонаправленные зависимости приложений;
- новый редактор фиксированных полей;
- новые публичные templates/CSS по утверждённому макету;
- новый одноразовый importer из нейтрального manifest;
- компактные acceptance tests пользовательских гарантий.

Не создаются заново:

- тексты, структура и точные URL;
- оригиналы галереи и остальные проверенные media;
- утверждённый дизайн;
- пользователи и назначения страниц;
- уже принятые правила безопасности и доступа;
- доказанные backup/restore операции;
- полезные маленькие валидаторы и транспортные функции после отдельной проверки.

Старые Django apps не импортируются новым runtime. Старый проект и его БД остаются read-only источником и средством отката до полной приёмки.

## 2. Целевая модульная структура

Полный dependency contract, ownership и внутреннее устройство модулей определяет `docs/clean-rebuild-architecture.md`. Новый final source root: `src/`. Старый `app/` остаётся неизменным до приёмки и отдельного удаления.

Закрытый контракт 20 transport outcome types / 19 independent payload kinds, 115 exact outcomes, editor groups, renderer families и media slots определяет `docs/clean-rebuild-content-contract.md`. До его автоматической проверки в REBUILD-1 нельзя создавать модели/importer/editor/public renderer.

Exact module DAG, FK/delete lifecycle и владельцы всех межмодульных транзакций зафиксированы в разделах 3 и 7 архитектуры. В REBUILD-1 они превращаются в маленькую проверяемую matrix; отдельный orchestration layer, repository/UoW, callback registry и event bus не создаются. Каждая write operation имеет одну outer `transaction.atomic()` у владельца use case; participants меняют только свои таблицы и не открывают независимую outer transaction.

```text
src/
  config/                 composition root: settings, URLs, wiring
  modules/
    accounts/             custom staff User, login, роли, throttle
    pages/                Page, Route, current+previous, PageGrant, SiteSettings
    media/                Asset, File, Usage, безопасная загрузка
    audit/                минимальный AuditEvent и safe logging
    gallery/              галерея и альбомы
    requests/             форма и закрытый список
  integrations/
    telegram.py           внешний notification adapter
  themes/
    estakada/              templates, partials, CSS, JS и визуальные assets
```

`kernel/` в clean skeleton отсутствует. Module-specific DTO/errors/ports живут у consuming module; optional pure common type появляется только после критериев `KERNEL-AC-001..005`, а не как заготовка.

Текущий rebuild создаёт только «Эстакаду». Будущий Dozvo создаётся отдельной копией завершённого проекта; уже в этой копии можно добавить через публичные API существующих модулей:

```text
modules/news/             новости и архив
modules/events/           афиша, предстоящие и прошедшие события
modules/customer_accounts/ клиентские аккаунты
modules/vehicles/         автомобили
modules/appointments/     записи и история
modules/mobile_api/       HTTP adapter для отдельного Android-проекта
themes/dozvo/             собственное оформление
```

Это не dynamic plugin/multi-site/tenant-платформа. В текущем runtime отсутствуют Dozvo code/settings/theme/tables/flags. Приложения в будущей копии явно подключаются в settings, root URLs и навигационной конфигурации. Exact DAG запрещает обратные/cyclic/private imports; межмодульное использование идёт только через публичные commands/queries/DTO. Тема не содержит бизнес-логику.

## 3. Минимальная целевая модель

### 3.1. Контент

- `Page`: UUID, имя, тип, parent, position, publication.
- `Route`: exact target, PRIMARY/ALIAS/REDIRECT и связь со страницей.
- `PageContent`: page, current JSON, previous JSON/null, updated metadata.
- `SiteSettings`: exact literal v1 singleton из content contract — organization name, gated nullable legal name, phone display+E.164, address, hours, contact email, HTTPS map, nullable owner-approved MAX/Telegram и one READY logo; arbitrary settings/social/SEO JSON отсутствует.
- `PageGrant`: сотрудник, страница и разрешённые группы полей.

Save использует exact generation/hash CAS и одной pages-owned транзакцией сдвигает current→previous, применяя employee только разрешённые группы. Owner-only Undo с CAS меняет current/previous местами. Immediate retry того же operation ID возвращает прежний result; retry после intervening mutation получает stale+reload. Stable, manual revisions, drafts, произвольная история и отдельный receipt ledger отсутствуют.

### 3.2. Медиа

- `Asset`: UUID, назначение, source SHA, состояние.
- `AssetFile`: asset, variant, безопасный storage key, MIME, размеры и SHA.
- `AssetUsage`: current/previous/site/gallery usage.

Оригиналы `/gallery-of-works/` переносятся побайтно. Новый runtime не переносит старые reservation book, generic worker exchange/job protocol, protected cleanup lifecycle или HTML-reserve retention.

Для новых upload сохраняется только узкая утверждённая D-324 decode boundary: один fixed local worker без сети/секретов/БД, 512MiB/1CPU/15s/128MiB tmpfs, один job и fixed byte protocol. Это не старый generic worker exchange: queue/broker/retry/job tables/arbitrary commands отсутствуют. Exact input/output/EXIF/animation/pixel/side и STAGED→READY cleanup contract определён архитектурой.

### 3.3. Заявки

- одна `ServiceRequest` по closed fields из `docs/clean-rebuild-requests-contract.md`;
- D-1229 уже фиксирует minimal request scope; intake остаётся полностью default-off до LEGAL-01 и отдельного актуального owner enable gate;
- закрытые read-only list/detail для owner+staff, owner-only exact delete;
- DB commit является успехом приёма;
- после commit одна bounded best-effort Telegram-попытка;
- automatic retention older-than-30-days и UUID-only deletion ledger;
- email, CRM, status, assignee, notes, export, outbox и retry worker отсутствуют.

### 3.4. Безопасность

Используются стандартные Django auth/session/CSRF/password hashing/ORM/escaping. Дополнительно остаются server-side permissions, login/form throttling, bounded uploads, image decode validation, малый `nh3` allowlist, закрытые private responses, secrets из environment/secret files, CSP и отсутствие ПД в логах.

Не переносятся универсальные receipts, reservations, prepare/run/result state machines, глобальный content lock и собственная доказательная инфраструктура каждой операции.

## 4. Что переносится из старого проекта

### 4.1. Как данные и доказательства

- текущая read-only DB: authority фактического current, дерева, публикации, пользователей и прав;
- canonical route map и 12 migration JSON: независимая проверка структуры/текстов, не runtime dependency;
- media directory и контрольные суммы;
- утверждённые дизайн-макеты: visual authority;
- существующие acceptance facts exact URL/content/gallery.

### 4.2. Как маленькие code candidates после review

- точные URL validators и scanner-path classification;
- безопасный JSON formatter;
- идея `nh3.clean` с заново сокращённым allowlist;
- phone/form normalization;
- Telegram HTTPS transport без email-ветки;
- отдельные safe path/image dimension helpers;
- backup/restore scripts, если они не импортируют старые product apps.

Каждый кандидат переносится вместе с узким тестом и очищается от старых импортов. Если код проще переписать, он переписывается по поведению, а не копируется ради формальной экономии.

### 4.3. Что запрещено переносить целиком

- `content`, `page_versions`, `page_editor`, `shared_content`, `html_reserve`;
- старые models и migrations;
- editor bundle, child/carrier/admission, HTML parser и protected lifecycle;
- media reservation/worker/lifecycle subsystem;
- DEV09/DEV10/DEV12 apply и local-demo runtime;
- generic public template и текущий CSS monolith;
- старые внутренние harnesses и compatibility tests.

## 5. Нейтральный manifest и перенос данных

Полный freeze/snapshot/public-private/caps/import contract определяет `docs/clean-rebuild-transfer-contract.md`; этот раздел читается только вместе с ним.

Старый Python-код не вызывается новым importer. Отдельный read-only exporter создаёт только public bounded manifest и file inventory:

- schema/version и общий digest;
- Page UUID/name/kind/parent/position/publication;
- все exact routes и outcomes;
- current payload и непосредственно предшествующий сохранённый payload;
- SEO и фиксированные общие данные;
- assets/files/usages, relative paths, byte sizes и SHA-256;
- отдельно exact214 legacy gallery originals;

Users/roles/PageGrant и отдельно разрешённые existing requests передаются только private DB→DB stream без промежуточного файла и через ту же открытую source snapshot transaction, что создала public manifest. Password hashes/sessions/tokens не переносятся: target получает unusable passwords и штатные recovery/reset procedures. Requests scope определён D-1229, но их фактический перенос требует frozen rows>0 и отдельного разрешения; latest independent deletion ledger всегда reconciles before target commit.

Exporter проверяет current/previous связность и не изменяет старую DB. Public manifest не содержит secrets, users, hashes или ПД и автоматически не попадает в Git. Canonical JSON/route map сравниваются с manifest и сигнализируют drift, но не подменяют фактический current.

Каждый importer attempt создаёт новый UUID и отдельную пустую DB+media pair. Одна target DB transaction принимает public+private+ledger только после media validation; затем post-commit DB/media read-back публикует write-once `SEALED` result. PostgreSQL+filesystem не называются общей ACID transaction: failed/unsealed pair никогда не выбирается, не продолжается и после exact containment cleanup удаляется целиком; повтор всегда новый UUID/empty pair. Current runtime pointer меняется только отдельным `REBUILD-Q003`. Универсальная migration/idempotency platform не создаётся.

## 6. Приёмочные сценарии до кода

Перед реализацией фиксируется компактная matrix:

1. Все 115 известных transport outcomes совпадают: status/redirect/exact URL.
2. Для каждой страницы совпадают title/H1/current text/structure и публикация.
3. Previous — ровно непосредственная предыдущая сохранённая копия; save/undo атомарны.
4. Все media usages разрешаются; exact214 gallery originals совпадают побайтно/SHA.
5. Owner/employee access и field grants закрыты server-side; anonymous private access закрыт.
6. 5–6 public families соответствуют approved design на representative widths; остальные URL наследуют только утверждённое семейство.
7. Редактор открывает фактический current и сохраняет только разрешённые поля.
8. XSS/CSRF/SQLi/scanner/upload/login boundaries проходят focused tests.
9. Заявка сохраняется один раз, Telegram success/failure не меняет DB success; direct-client→Nginx→protected Unix socket boundary не доверяет client forwarding headers, throttles canonical peer independently и не сохраняет IP; ПД отсутствуют в audit/technical logs.
10. `BACKUP-AC-001`–`BACKUP-AC-011`: exact release/code/migrations/schema/config-name manifest связан с coherent DB+media generation; failure восстанавливает pre-run write bitmap, latest deletion ledger применяется, затем isolated readiness+115-route HTTP smoke проходит без сети.
11. `AUDIT-AC-001`–`AUDIT-AC-008`: один bounded owner-only AuditEvent lifecycle закрывает atomic action/security events, safe fields, retention180d и обычный DB backup без analytics/event/ledger platform.
12. Dependency check доказывает `config → modules`, exact module DAG из architecture, отсутствие placeholder kernel/private/cyclic imports и любых imports нового runtime из старого `app/`.
13. Старый runtime остаётся доступным для локального rollback до принятия cutover.
14. `QA-PERF-001`–`QA-ROLLBACK-001` из architecture проходят на зафиксированном RC-профиле; latency/load остаются локальными budgets, а integrity, limits, RPO/RTO и rollback gates не подменяются production SLA.
15. `PGLC-001`–`PGLC-012` закрывают owner-only create/rename/move/reorder/publication/URL/delete, employee denial, direct navigation projection и atomic current+previous/usages lifecycle.

## 7. Этапы и сроки

Все числа этого раздела до завершения `REBUILD-1` — **preliminary planning hypothesis, не срок, обещание или commitment**. Они включают реализацию, миграции, focused tests и review, но не ожидание ответов владельца, production deploy и будущие Dozvo/news/events/portal/API.

| Этап | Результат | Предварительная гипотеза |
|---|---|---:|
| REBUILD-0. Архитектура, план и review | Утверждены dependency rule, module ownership/public APIs, data authority, acceptance matrix и cutover gates. | 3–5 ч |
| REBUILD-1. Read-only baseline/export contract | Exact DB/media inventory, manifest schema, 115-route and gallery SHA baseline. | 3–5 ч |
| REBUILD-2. Чистый skeleton/modules | Новый `src/`, composition root, accounts/pages/audit без placeholder kernel, current+previous и fitness checks. | 4–6 ч |
| REBUILD-3. Media и importer | Простая media schema, exporter/importer, clean-DB load, counts/SHA/current+previous verification. | 4–6 ч |
| REBUILD-4. Админка и редактор | Список страниц, fixed-field editor, grants, save/undo, SiteSettings и media selection. | 5–7 ч |
| REBUILD-5. Public/theme | Approved shell и 5–6 family templates/CSS, SEO/navigation/sitemap, all115 automated outcomes. | 7–10 ч |
| REBUILD-6. Gallery и requests | Exact gallery/album; DB/admin+Telegram form; security/failure cases. | 3–5 ч |
| REBUILD-7. Общая приёмка и local cutover | Full manifest parity, security, responsive, backup/restore; new runtime selected locally with rollback. | 4–6 ч |

Первоначальный коридор: **33–50 рабочих часов**; ранняя likely-гипотеза при чистом manifest и без скрытого data drift — **35–41 час**. До фактической WBS ниже эти числа нельзя использовать как дату готовности, остаток или процент выполнения. Дополнительное время закладывалось в upfront architecture review и fitness checks, а не в новые runtime-подсистемы.

### 7.1. Обязательный пересчёт после REBUILD-1

Baseline публикует один компактный `REBUILD-1-WBS` рядом с aggregate evidence, без task tracker/Gantt/estimation service. Каждая строка получает числовые `O/L/R` hours и ссылку на фактические counts/contracts:

| WBS group | Фактическая basis после REBUILD-1 | Что входит в оценку |
|---|---|---|
| `WBS-SCHEMA` | exact target apps/models/constraints/migrations и approved dependency list | skeleton/config, schema, commands/queries, migration+fitness checks |
| `WBS-FAMILY` | 20 transport outcome types / 19 independent payload kinds, их фактическая группировка в renderer families, editor groups/media slots и representative widths | typed validation, editor forms, templates/CSS/minimal JS, family acceptance |
| `WBS-DATA` | exact cohorts/counts/bytes/digests: routes/pages/current/previous/settings, ordinary media, exact214 originals, albums, staff/grants и отдельно разрешённые requests | exporter/importer, transforms, ambiguity/drift remediation, SHA/count verification |
| `WBS-AC` | закрытый список автоматических и ручных AC по contract ID, включая security/failure/concurrency/browser runs | tests, fixtures/runners, review remediation и evidence packaging |
| `WBS-OPS` | exact config/secret-name inventory, backup/restore/ledger/rollback/cutover steps | release manifest, isolated restore, RC quality run и local cutover rehearsal |

Для каждой строки:

- `O` — факты baseline согласованы, предусмотренный reuse-кандидат проходит review, одна реализация и один verification pass;
- `L` — наиболее вероятный путь с одним локальным remediation/review pass для известных сложных границ;
- `R` — известный data drift/ambiguity либо ещё один bounded remediation/re-import pass, но без будущих features/live/deploy;
- отдельно перечисляются assumptions, blockers и excluded scope; неизвестное не маскируется headroom;
- итоговые `O/L/R` — простая сумма пяти строк, без коэффициента «на всякий случай» и без преобразования часов в процент готовности.

Новая WBS заменяет ранние `33–50/35–41` как рабочую оценку только после независимой проверки counts, отсутствия двойного учёта и owner acknowledgement. Пересчёт затем нужен лишь при изменении approved scope, новом baseline drift, разделении renderer family, добавлении dependency или AC; он обновляет затронутые строки, а не создаёт новый плановый контур.

По решению владельца D-1336 после завершения каждого этапа `REBUILD-0`–`REBUILD-8` отчёт дополнительно содержит: диапазон оставшихся рабочих часов, ориентировочный процент выполненной работы, изменение против предыдущей оценки и явные exclusions. До принятия REBUILD-1-WBS процент остаётся только предварительным диапазоном. После WBS он вычисляется из одной и той же базы: `выполненные WBS-часы / (выполненные + оставшиеся WBS-часы)`, отдельно для optimistic/likely/risk; ожидание владельца, live/deploy и новый scope в процент не прячутся. Процент не заменяет статус acceptance gates.

Acceptance:

- `EST-AC-001`: до REBUILD-1 все часы явно preliminary/non-commitment и не формируют launch date/progress percent;
- `EST-AC-002`: WBS имеет ровно пять групп schema/family/data/AC/ops и каждая связана с exact baseline facts;
- `EST-AC-003`: каждая группа имеет numeric O/L/R, assumptions/blockers/exclusions и не дублирует работу другой группы;
- `EST-AC-004`: risk включает только известный bounded rework; новая функция, live/deploy и ожидание owner считаются отдельно, не прячутся в запас;
- `EST-AC-005`: reviewed WBS total заменяет раннюю гипотезу только после owner acknowledgement; meaningful change обновляет только затронутые строки.
- `EST-AC-006`: после каждого завершённого REBUILD-этапа публикуются remaining-hours range и WBS-based progress range с delta/exclusions; до WBS они явно preliminary.

После принятого local cutover отдельный `REBUILD-8` удаляет старый runtime/schema/tests (**4–7 часов**). Он не блокирует готовность нового сайта и требует отдельного актуального подтверждения разрушительных целей. Live/deploy остаётся отдельным решением.

## 8. Контроль новых рисков

| Риск пересборки | Ограничение |
|---|---|
| Потеря URL/текста/media | Manifest + independent route/JSON/media SHA comparison до cutover. |
| Новый код повторит старую связанность | Static dependency rule, module ownership/public APIs, запрет imports из old app и exact DAG: `audit→none; accounts→audit; media→audit; pages→accounts/media/audit; gallery→pages/media/audit; requests→audit`; private/cyclic imports absent. |
| Перенос неверной previous | Exact per-page current predecessor proof; ambiguity blocks import. |
| Переписывание ослабит безопасность | Django defaults + focused boundary tests; переносится поведение, не сложность. |
| Два проекта разойдутся во время работ | Старый runtime read-only; один cutover baseline; контентные изменения на время миграции заморожены. |
| Слишком ранняя универсализация под Dozvo | Текущий продукт только Estakada; Dozvo позже отдельный fork/copy. Сейчас только здоровые module boundaries, без Dozvo code/theme/settings/tables/flags. |
| Ошибка backup оставит writes закрытыми | Один wrapper в обязательном `finally` проверяет прежний catalog и отсутствие backup writer, затем восстанавливает ровно pre-run enabled/disabled bitmap; ambiguity остаётся fail-closed для owner inspection. |
| Невозможность отката | Старая DB/media/runtime не удаляются до полной local acceptance и backup restore. |

## 9. Ворота

- `REBUILD-Q001`: **APPROVED D-1251** — владелец утвердил подход и список функций MVP; разрешены только REBUILD-0/1 read-only и review.
- `REBUILD-Q002`: после APPROVED плана и baseline владелец разрешает реализацию нового `src/`.
- D-1409 уточняет только смысл этого gate при D-1405: accepted baseline может содержать один explicit deferred unmatched-source blocker, а Q002 при отдельном owner approval разрешает только product-code implementation. Exporter/importer execution, target DB/media, coherent migration freeze, transfer и cutover требуют последующих отдельных gates; Q002 их не наследует.
- `REBUILD-Q003`: отдельное разрешение local cutover после полной приёмки; старый runtime сохраняется.
- `REBUILD-Q004`: отдельное destructive confirmation точных старых schema/files/tests после backup и rollback window.
- Production/live/deploy никогда не подразумеваются предыдущими воротами.

REBUILD-0 architecture/plan/review завершён D-1250/D-1251; static authority preflight D-1252 PASS. D-1253 DBPRE contract после D-1254 findings и D-1255/D-1256 remediation получил D-1257 APPROVED. D-1258 owner одобрил exact temporary reader boundary для JIT DBPRE; D-1173 populated dev DB является source, stale test исключён. D-1259 остановил фактический запуск: независимое review candidate-runner дало `CHANGES_REQUESTED` P1=2/P2=2, runner не исполнялся, ранее данное read approval исчерпано. D-1260/D-1261 подготовили P1 candidates: identity/TLS+facts используют одно соединение/snapshot; перед DROP заново доказывается exact role state и текущая expected privilege matrix, mismatch уходит в exact-OID fail-closed fallback. Следующий шаг — только P2-001 global non-system effective privilege proof, затем P2-002 и повторное независимое review; перед фактическим чтением потребуется новое согласие владельца. Product code, target DB/media, importer, runtime и cutover не начинаются без отдельных gates/`REBUILD-Q002`.
