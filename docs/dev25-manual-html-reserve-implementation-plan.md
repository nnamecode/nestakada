# DEV-25 — минимальный план реализации ручного HTML-резерва

Дата: 2026-11-12. Статус: final repeat plan review D-874 `APPROVED`, P1/P2/P3=0. Продуктовый код не начат. До реализации обязательно отдельное разрешение владельца на `DEV25-IMP-001–008`.

Основание: D-592, D-867, D-870, `docs/dev25-manual-html-reserve-scope-proposal.md`, REF-AC-017–019/021/032. DEV-26/27, Nginx, live/persistent apply и production в этот план не входят.

## 1. Граница реализации

Реализация остаётся частью существующего Django-процесса и использует текущие public/content/shared/media/auth/audit layers. Не добавляются package dependency, DB model/migration, API, cache, queue, worker, scheduler, crawler, Playwright, TRUST/head или второй renderer.

Новые файлы образуют обычный внутренний Python package `app/html_reserve/`, но он не регистрируется как отдельный Django app и не имеет models/migrations:

- `contracts.py` — immutable DTO, caps, canonical JSON, exact target/resource policies;
- `source.py` — bounded public dependency snapshot/stamp и exact route/gallery inventory;
- `storage.py` — trusted directory-fd operations, nonblocking lock, staging/generations и atomic pointer;
- `builder.py` — один synchronous orchestration flow;
- `views.py`, `urls.py` и existing-layer `accounts/templates/accounts/html_reserve.html` — owner status/build UI.

Точечные изменения существующих файлов:

- `content/public_views.py` и `service_requests/public.py` — закрытый internal reserve render entry, который всегда отключает форму;
- `media_library/services.py` — bounded attach/detach/reconcile только `RETAINED_HTML`;
- `accounts/templates/accounts/dashboard.html` — owner-only ссылка;
- `estakada/urls.py`, `estakada/settings/base.py`, audit constants/events — URL, закрытый root и фиксированные коды;
- тесты `html_reserve/test_*.py` и узкие affected public/media/admin regression tests.

Если реализация потребует ещё одну runtime-службу, таблицу состояния, универсальный URL crawler или новый public renderer, срез останавливается и возвращается владельцу как выход за scope.

## 2. Закрытые контракты

### 2.1. Числовые пределы

- `MAX_TARGETS = 512`;
- `MAX_RESOURCES = 1024`;
- `MAX_PAGES = 512`, `MAX_CURRENT_REVISIONS = 512`, `MAX_ROUTES = 512`;
- `MAX_PAGE_STATES = 512`, `MAX_PUBLIC_ASSETS = 1024`, `MAX_PUBLIC_ASSET_FILES = 1024`;
- `MAX_PUBLIC_USAGES = 4096`, `MAX_RETAINED_USAGES = 4096`, shared blocks/current revisions ровно два;
- `MAX_GENERATION_DIRS = 8`, `MAX_STAGING_DIRS = 4`, `MAX_POINTER_TEMPS = 2`, `MAX_ROOT_ENTRIES = 32`;
- `MAX_HTML_BYTES = 4 * 1024 * 1024` на response;
- `MAX_MANIFEST_BYTES = 2 * 1024 * 1024`;
- `MAX_GENERATION_BYTES = 512 * 1024 * 1024`;
- один `current`, не более одного `previous`, не более одного bounded staging/build под lock.

Каждый DB/filesystem enumeration использует closed count или `cap + 1`; превышение проваливает весь build, а не обрезает набор.

| Enumeration | Exact cap/oracle |
|---|---|
| `Page` | `MAX_PAGES + 1`; все rows unique/coherent |
| non-SYSTEM `Route` | `MAX_ROUTES + 1`; exact target/status/location set |
| `PageContentState` и selected current `PageRevision` | каждый `MAX_PAGE_STATES/MAX_CURRENT_REVISIONS + 1`; page/revision ownership exact |
| `SharedBlock` и selected current `SharedRevision` | ровно 2 каждого: header/footer |
| public `AssetUsage` (`CURRENT_PAGE`, `SHARED_BLOCK`) | `MAX_PUBLIC_USAGES + 1`; consumer/slot exact |
| referenced READY `Asset` | `MAX_PUBLIC_ASSETS + 1` |
| selected public `AssetFile` | `MAX_PUBLIC_ASSET_FILES + 1`; no private source |
| all `RETAINED_HTML` usages for reconciliation | `MAX_RETAINED_USAGES + 1`; grouped by generation UUID |
| root entries | `MAX_ROOT_ENTRIES + 1`; only closed filenames/types |
| generation/staging/pointer-temp entries | соответственно `8 + 1`, `4 + 1`, `2 + 1`; overflow fail closed before cleanup |

Orphan/reconcile при любом превышении ничего частично не удаляет.

### 2.2. Source snapshot и stale

`source.capture()` под PostgreSQL transaction и `content.lock_content('default')` возвращает canonical bounded descriptor и SHA-256 stamp. Каждый queryset имеет свой `cap + 1` из пункта 2.1 и exact cardinality/coherence checks. Descriptor включает только влияющие на public bytes данные:

- все `Page`: id, parent, position, kind, name, publication;
- все non-SYSTEM `Route`: id, target с query, kind, page, legacy и вычисленные expected status/location;
- `PageContentState` и current `PageRevision`: id, sequence, schema version, payload hash и canonical validated payload digest;
- current `SharedBlock/SharedRevision`: ids, generation, schema/storage/payload descriptors;
- public `AssetUsage`, READY `Asset` и выбранные `AssetFile`: ids, kind/key/SHA-256/size без private source, плюс closed bare/contextual consumer class для каждого публичного file UUID;
- SEO/public origin/profile и versioned renderer policy identifiers;
- SHA-256 локальных public CSS/JS и shared static bytes.

Физические media/shared-file bytes не перечитываются для каждого status GET: их сохранённые descriptors входят в stamp. Во время build каждый реально копируемый файл читается no-follow и сверяется с descriptor digest/size. Изменение любого descriptor даёт `stale`; повреждение bytes проваливает build/resource validation.

Snapshot не включает draft/history/Stable как отдельные источники, audit, sessions, заявки и `RETAINED_HTML`, поэтому собственные reserve usages не меняют stamp.

### 2.3. Exact target set

Inventory содержит каждый bounded non-SYSTEM `Route.target`:

- published PRIMARY/ALIAS → exact rendered `200`;
- hidden PRIMARY/ALIAS → exact blank `200`;
- REDIRECT → `301` и exact PRIMARY `Location`;
- gallery-generated: root, exact `?page=1` → `302` root, `?page=2`, допустимые `?album=<slug>` и `?page=2&album=<slug>`;
- `?page=1&album=<slug>` и другие unknown/404 отсутствуют.

Manifest хранит exact request-target, status, location/content type, body digest/size и closed resource references. Query не используется как filesystem path: response лежит под digest-derived internal name, а mapping остаётся только в canonical manifest. DEV-26 позже определит Nginx delivery mapping, не меняя manifest semantics.

### 2.4. Internal reserve render

HTTP URLConf продолжает вызывать обычный `content.public_views.page(request)`. Builder вызывает отдельную Python-функцию `render_reserve(request)`, которая не зарегистрирована как URL и выбирается не через path/query/header/cookie/settings. Обе функции используют один внутренний renderer.

Builder никогда не передаёт owner/admin request. Для каждого validated exact target он создаёт новый минимальный anonymous internal GET: path/query только из inventory, пустые body/cookies/session/user/conditional headers, фиксированный host/origin из уже validated public SEO configuration и без `If-None-Match`. Internal request не может получить 304 и не наследует `/manage/`, cookie или заголовки нажавшего владельца; reserve capability передаётся отдельным Python context, не HTTP-данными.

Reserve branch для home/contacts получает `service_requests.public.disabled_form_for(target)` и никогда не вызывает intent issuance или CSRF token creation. Даже при включённом обычном intake output не содержит intent, token и working action. Внешний HTTP не может выбрать branch.

### 2.5. Resource policy

Stdlib HTML parser принимает только ожидаемые trusted-renderer tags/attributes и собирает same-origin fetchable resources: stylesheet/script/image и другие явно перечисленные embedded URLs. Разрешены только существующие `/static/public.css`, `/static/public-gallery.js`, `/static/public-home.js`, `/static/shared/<digest>/<name>` и две точные media-формы:

- bare `/public-media/<uuid>/` — только если UUID frozen source snapshot пометил реально публичным current/shared/home resource;
- contextual `/public-media/<uuid>/?page=<uuid>&slot=<closed>` — только при exact совпадении file/page/slot consumer из frozen snapshot.

Builder получает bytes через закрытое отображение на существующие Django resource functions/storage descriptors, без HTTP/network/DNS. Status/content type/size/digest проверяются. External/scheme-relative scripts, styles, fonts, images, iframe и form action запрещены.

Текущие локальные CSS принимаются только если closed token check подтверждает отсутствие `url(` и `@import`; появление такого construct проваливает build до отдельного утверждения extractor. Фиксированные local JS сверяются по digest и fail closed при `fetch`, XHR, WebSocket, EventSource, sendBeacon, dynamic `import()` или иных утверждённых network primitives. Builder JS не исполняет.

Обычные `<a href>` и SEO metadata не загружаются. Они проверяются отдельной closed scheme/host policy: локальные exact targets либо уже разрешённые renderer-validated `http/https` navigation/SEO values без userinfo/control characters. JSON-LD сохраняется как inert script data и проходит существующий safe serializer; builder не следует его URL.

## 3. Trusted filesystem layout

Новая закрытая настройка: `HTML_RESERVE_ROOT = '/var/lib/estakada/html-reserve'`. Root заранее создаётся deployment-слоем, не самим web request. Build доступен только когда absolute root существует как real directory, принадлежит effective uid, имеет mode `0700`, не является symlink/reparse point и после resolve не совпадает/не вложен взаимно с workspace/base, media, static, request-ledger root или filesystem/drive root. Production mount/preflight относится к будущему launch gate.

Внутри root допускаются только:

```text
active.json
active.<generation-uuid>.tmp
build.lock
generations/<generation-uuid>/manifest.json + content/
staging/<generation-uuid>/...
```

Все операции идут через held directory fds, `O_NOFOLLOW|O_CLOEXEC`, regular-file/directory checks и closed names. Lock — `flock(LOCK_EX|LOCK_NB)` на заранее созданном `build.lock` mode `0600`; busy немедленно завершает второй build. Tests работают в Linux foundation; отсутствие безопасных primitives даёт fail-closed, а не fallback на небезопасный path API.

Каждый новый directory создаётся/проверяется mode `0700`; каждый новый файл создаётся `O_CREAT|O_EXCL`, mode `0600`, с bounded streaming SHA-256, `fsync(file)` и `fsync(parent)`. Staging не выдаётся как active. Cleanup удаляет только проверенные entries данного UUID под root, без glob/symlink traversal.

## 4. Authoritative activation protocol

`active.json` — единственная filesystem authority, canonical schema:

```json
{"schema":"html-reserve-active-v1","current":"<uuid-or-null>","previous":"<uuid-or-null>","current_manifest_sha256":"<hex-or-null>","previous_manifest_sha256":"<hex-or-null>"}
```

Manifest содержит generation UUID, build time, source stamp, exact responses/resources, retained asset ids и totals, но не absolute paths, usernames, cookies, tokens, HTML snippets или ПД. Для каждого target сохраняется закрытая response metadata: status/location/content type, exact nullable `X-Robots-Tag` (или validated robots class), versioned `security_policy_id` и `cache_policy_id`. `Set-Cookie`, `Vary`, private/no-store и любые неожиданные security/cache headers проваливают build; DEV-26 позже маппит только эти identifiers на выдачу, не изобретая policy заново.

Порядок под held nonblocking filesystem lock:

1. Проверить closed root inventory и directories mode `0700`. При самом первом build, только если root доказанно новый и содержит лишь safe precreated `build.lock` плюс пустые validated `staging/generations`, создать canonical empty `active.json` (`current=null`, `previous=null`) через temp+fsync+replace+root fsync. После bootstrap missing pointer всегда fail closed. Затем полностью проверить pointer, current/previous manifests и generation directories.
2. Распознать не более `MAX_POINTER_TEMPS` exact `active.<uuid>.tmp`. Temp не является authority и удаляется только если это regular mode `0600`, bounded canonical pointer с известной schema и UUID; malformed/unknown блокирует build. Bounded reconcile удаляет только generation/usages, UUID которых доказанно отсутствуют в validated active current/previous; active UUID никогда не очищается. Неоднозначность/overflow блокирует build без частичной очистки.
3. Снять source snapshot A.
4. Создать новый UUID staging, отрендерить exact set, скопировать/проверить resources, записать canonical manifest и пройти все validators/caps/private-leak checks.
5. Атомарно переименовать complete `staging/<uuid>` в immutable `generations/<uuid>` и fsync оба parent directories: source `staging` и destination `generations`. Этот каталог ещё не active.
6. Одной DB transaction через bounded `media_library.services` создать `RETAINED_HTML` usages нового UUID для exact referenced asset ids. Conflict/non-READY/limit откатывает transaction.
7. В финальной DB transaction взять `content.lock_content`, снять snapshot B и потребовать `A.stamp == B.stamp`. Пока advisory lock удерживается, перечитать/сверить static descriptors, сформировать новый pointer `current=new`, `previous=old current`, записать `active.<uuid>.tmp`, fsync и выполнить единственный atomic `os.replace`/dir-fd rename на `active.json`, затем fsync root. **Replace — authoritative activation point; успешный root fsync подтверждает durability.**
8. Если root fsync после replace ошибся, откат запрещён. Builder под тем же lock перечитывает и полностью валидирует pointer/manifests: видимый exact new generation UUID означает activated result с owner-visible durability warning и запретом слепого повтора; неоднозначный/unreadable pointer означает `result unknown`, а любой следующий status/build fail closed до безопасного validated reconcile. После confirmed activation generation считается успешным даже при потере HTTP-ответа или ошибке success-audit. По тому же UUID повторно не строится. Best-effort не применяется: отдельный bounded cleanup/reconcile на текущем или следующем build удаляет proven old-previous directory/usages; его ошибка показывается warning, но не откатывает active pointer.

До шага 7 current/previous byte-identical. Crash после шага 5 оставляет только orphan generation; после шага 6 — orphan generation с безопасным over-retention; после шага 7 — корректный active current/previous и максимум over-retained old previous. Active generation никогда не остаётся без заранее committed retained refs.

## 5. UI, права и аудит

- `GET /manage/html-reserve/`: `@gate(owner=True)`, показывает current build date/age, current/previous UUID в сокращённом безопасном виде или нейтральный status, current source stamp comparison и `stale`; unsafe/unavailable root даёт закрытую ошибку без paths.
- `POST /manage/html-reserve/`: `@gate(owner=True)`, `@require_POST`, exact form `action=build`, CSRF, body/field limits через существующий `accounts.views.fields`; запускает один synchronous build.
- Сотруднику — server-side 403, anonymous — штатный 401/login; ссылка на dashboard только owner.
- Response не обещает успех по тайм-ауту: после exception endpoint под lock перечитывает validated active pointer/generation UUID и различает pre-activation failure, visible post-replace activation с durability warning и ambiguous `result unknown`. Unknown не разрешает новый build. Owner request нигде не используется для public rendering.
- Audit source `HTML_RESERVE`, category `BACKUP_MAINTENANCE`, fixed codes: `HTML_RESERVE_BUILD_STARTED`, `..._BUSY`, `..._SUCCEEDED`, `..._FAILED`, `..._RECONCILE_WARNING`; object ref — generation UUID только когда известен. Paths, targets, query, HTML, assets, exception text и secrets не пишутся.
- START audit failure блокирует build до filesystem mutation. FAILED/BUSY audit failure не вызывает небезопасный повтор. SUCCESS audit failure после activation возвращает success с owner-visible audit warning: активированное поколение не откатывается и не объявляется failed.
- Устойчивое поле «последняя попытка» не создаётся. Текущие дата/возраст/stale берутся из manifest+live stamp; ошибка видна в непосредственном ответе и существующем audit screen. При необходимости status читает только один latest bounded HTML_RESERVE audit row.

## 6. Срезы реализации

### DEV25-IMP-001 — pure contracts и exact inventory

Tests first для caps, canonical manifest/pointer JSON, exact non-SYSTEM Route/status/location, gallery allowlist и unknown exclusion, query-to-digest mapping, URL/resource policy. Реализовать `contracts.py` и read-only `source.py`; никаких файловых записей/UI.

Evidence: `DEV25-AT-002`, часть `AT-004/007`; no migrations, diff-check.

### DEV25-IMP-002 — trusted reserve renderer и resource capture

Добавить internal-only `render_reserve`, minimal anonymous request factory, disabled form DTO, stdlib HTML extraction и closed resource dispatch/copy. Проверить обычный public renderer без изменений, normal intake branch отдельно и reserve output при synthetic enabled intake. Покрыть bare shared/header/footer/home media, contextual body/gallery/SEO, CSS no-resource policy и fixed JS no-network policy.

Evidence: `DEV25-AT-005/007`, public/shared/gallery/home/service-request regression; no network.

### DEV25-IMP-003 — safe storage и immutable generation

Реализовать root preflight, canonical empty-pointer bootstrap, nonblocking flock, no-follow fd operations, staging writer, manifest/response-metadata validation, generation rename, orphan pointer-temp handling, active pointer read/write и exact enumeration caps. Controlled fault seams — fixed internal test callbacks, недоступные HTTP; real crash semantics проверяются отдельно child-process oracles IMP-004.

Evidence: traversal/symlink/reparse/unknown-entry/oversize/disk-write/fsync/rename faults, first bootstrap, missing-after-bootstrap, orphan temp и crash/reopen; active pointer пока не вызывается из UI.

### DEV25-IMP-004 — retained media lifecycle и activation

Добавить bounded exact `RETAINED_HTML` attach/detach/reconcile в existing media service. Реализовать orchestration A/build/refs/B/atomic pointer/cleanup с одной authoritative activation point и generation UUID recovery. В isolated temporary root и test PostgreSQL отдельные child processes с закрытыми test-only patch hooks выполняют abrupt `os._exit` после generation rename, после committed retained refs, сразу после pointer replace и после успешного root fsync; новый process читает status/reconcile. Отдельная injection root-fsync failure после replace требует pointer re-read, тот же UUID, no rollback/no duplicate build и durability warning либо fail-closed unknown. Два отдельных process подтверждают nonblocking flock/busy. Child закрывает inherited DB connections перед работой. Это test harness, не runtime worker/service.

Evidence: `DEV25-AT-003/004/006`, real PostgreSQL transactions, source mutation race, faults before/after each durable boundary, cleanup refusal on ambiguity.

### DEV25-IMP-005 — owner UI/status/audit

Добавить owner-only GET/POST, dashboard link, private/no-store response, neutral status/error and fixed audit codes. Employee/anonymous/direct forged POST/GET-method/CSRF/extra field/body-limit checks.

Evidence: `DEV25-AT-001`, owner/employee/anonymous matrix, busy and lost-response result.

### DEV25-IMP-006 — combined security/content acceptance

Exact-set build на synthetic public fixture: route query/status/location, hidden blank и indexed/noindex response metadata, gallery/modal variants, self-contained bare+contextual local resources, external navigation kept inert, no external embedded resource, no admin/history/preview/PII/token/cookie/working form. Owner cookie/header/conditional ETag намеренно подмешиваются во входной admin request и не попадают в minimal internal GET/output; 304 невозможен. Tampered pointer/manifest/resource/private marker fail closed.

Evidence: `DEV25-AT-002/005/007/008`, REF-AC-017–019/021 partial REF-AC-032; HTML reserve explicitly not DB/media backup.

### DEV25-IMP-007 — frozen regression evidence

Запустить exact DEV-25 package, affected public/shared/media/accounts/audit/service-request tests, full guard, Django system check, migration consistency and `git diff --check`. Foundation остановить. Никаких live roots, real credentials, PII, network или persistent apply.

### DEV25-IMP-008 — independent code review

Независимый review проверяет security, exactness, filesystem/DB crash semantics, stale completeness, rights, audit safety, dead/duplicate architecture and test oracles. Все P1/P2/P3 исправляются bounded patches с targeted+full repeat; задача завершается только после final `APPROVED`.

## 7. Fault matrix, обязательная до кода

| Граница | Инъекция | Ожидаемый результат |
|---|---|---|
| Bootstrap / lock busy | new empty root, missing pointer after bootstrap, second process | Canonical empty pointer once; later missing fail closed; никакой second build |
| Capture/render | DB unavailable, 4xx/5xx, changed source | Current/previous и retained refs прежние |
| Staging write | short write, ENOSPC, fsync/manifest/resource failure | Current/previous прежние; bounded orphan cleanup |
| Generation rename | rename/fsync source/destination failure; abrupt child exit | Current/previous прежние; reopen sees only bounded orphan |
| Retained refs | DB error/non-READY/conflict; abrupt child exit after commit | Transaction rollback or safe over-retained orphan; reopen reconcile exact |
| Final recapture | stamp drift | Pointer не меняется; new usages/generation orphan-safe |
| Pointer temp/replace | write/fsync/replace failure до replace | Старый active byte-identical |
| Root fsync после pointer replace | injected fsync failure | Re-read same UUID → activated+durability warning/no retry; ambiguity → result unknown и build blocked |
| После успешного root fsync | abrupt child exit, response/audit/cleanup failure | Новый UUID confirmed active success on reopen; old previous может быть только over-retained |
| Reconcile | unknown/tampered/ambiguous UUID | Fail closed; current/previous никогда не удаляются |

## 8. Проверки и условия остановки

- PostgreSQL обязателен для integration/concurrency; SQLite не заменяет advisory/transaction tests.
- Никаких wildcard test discovery: запускать подтверждённые module paths и утверждённый full wrapper.
- Не применять миграции к persistent БД: миграций DEV-25 нет.
- Не создавать/менять production root, compose mount, Nginx или VPS в DEV-25.
- Повтор эквивалентной ошибки второй раз останавливает соответствующий срез по AGENTS.md; третьей попытки нет.
- После plan review `APPROVED` реализация всё равно не начинается без отдельного ответа владельца на gate `DEV25-IMP-001–008`.
