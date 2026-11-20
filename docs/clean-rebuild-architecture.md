# Чистая архитектура нового модульного монолита

Дата: 2026-11-16. Статус: **independent CRAR-REPEAT-003 APPROVED; owner REBUILD-Q001 и code gate остаются закрыты, код не начат**.

## 1. Цель

Сделать архитектуру, которую легко понимать, расширять и проверять, не превращая небольшой сайт в корпоративную платформу. Основа — dependency rule из Clean Architecture, применённая прагматично к Django-монолиту.

Главные свойства:

- бизнес-операции не живут во views, templates, signals и model `save()`;
- ядро не знает о конкретных функциях Эстакады, Dozvo, Telegram или Android;
- каждый модуль имеет явную область данных и маленький публичный API;
- внешние интерфейсы вызывают одни и те же use cases;
- новая функция добавляется новым модулем или расширением одного владельца данных, а не изменениями по всему проекту;
- архитектурные границы проверяются автоматически;
- абстракция создаётся только для реальной границы или второго потребителя.

## 2. Структура

```text
src/
  config/                       composition root
    settings/
    urls.py
    wiring.py

  modules/                      независимые Django applications
    accounts/
    pages/
    media/
    audit/
    gallery/
    requests/

  integrations/                 внешние адаптеры
    telegram.py

  themes/
    estakada/                    templates/CSS/JS/assets
```

Текущий продукт — только «Эстакада» и только её утверждённые модули. Будущий Dozvo не является вторым tenant/site внутри этого runtime и не требует общей платформы: владелец создаёт отдельную копию завершённого проекта «Эстакады», затем в той копии добавляет `modules/news`, `modules/events` и `themes/dozvo`. Личный кабинет при отдельном будущем решении добавляет в нужную копию `modules/customer_accounts`, `modules/vehicles`, `modules/appointments`; web cabinet и Android API являются разными входными адаптерами к одним use cases.

## 3. Единственное главное правило зависимостей

Разрешённое направление верхнего уровня: `config → modules`. Внутри `modules` действует следующий exact DAG; стрелка означает разрешённый import только публичного API модуля справа:

```text
config ──► accounts ──► audit
   │          │            ▲
   │          └────────────┘
   ├────► pages ─────► accounts
   │          ├─────► media ───► audit
   │          └─────► audit
   ├────► gallery ───► pages, media, audit
   ├────► requests ──► audit
   ├────► integrations/telegram
   └────► themes (только готовые view models)
```

`audit` не импортирует product modules; его публичный `ActorRef` принимает UUID+role snapshot без FK/import обратно в `accounts`. `media` импортирует только публичный `audit`, но не `pages/gallery`. `pages` импортирует публичные API `accounts`, `media`, `audit`. `gallery` является верхним feature-модулем и может импортировать публичные API `pages/media/audit`; обратных edges нет. `requests` импортирует `audit`, а свой `NotificationPort` объявляет внутри `requests`. Конкретный Telegram adapter передаёт `config`.

`kernel/` по умолчанию отсутствует и в REBUILD-2 не создаётся. Общий pure type/policy можно вынести туда позднее только когда одновременно доказано: два текущих модуля уже используют одну семантику; type не принадлежит одному consumer; код не знает Django/ORM/I/O/settings/environment/site/features; extraction удаляет реальное дублирование или dependency edge; есть маленький independent test. Module-specific DTO/errors/ports остаются у потребителя. Empty/placeholder kernel, общий `BaseService`, `Result`, `Repository`, generic ID/error hierarchy и перенос «на будущее» запрещены.

Запрещено:

- module импортирует private-файлы другого module;
- accounts/pages/media импортируют gallery/requests/news/events;
- `audit` импортирует accounts или любой другой product module;
- `media` импортирует pages/gallery, а pages импортирует gallery;
- Telegram импортируется непосредственно из request view/use case;
- templates обращаются к ORM или создают бизнес-решения;
- новый `src/` импортирует старый `app/`;
- общий `utils.py` становится свалкой межмодульной логики.

Если доказанный `kernel` когда-либо появляется, он является необязательным leaf: modules могут импортировать только его public pure values, а он импортирует только Python stdlib и никогда Django/modules/config/integrations/themes. Его появление требует обновить exact DAG и fitness check; существование пустого каталога само по себе считается failure.

`config` — единственное место, где конкретные реализации соединяются. Это composition root, а не бизнес-слой.

Acceptance:

- `KERNEL-AC-001`: clean skeleton не содержит `kernel/`, common/base/utils package или placeholder files;
- `KERNEL-AC-002`: `ActorRef` принадлежит audit, `NotificationPort` requests, остальные DTO/errors — своим consumers;
- `KERNEL-AC-003`: exact module DAG проходит без optional common layer и без private/cyclic imports;
- `KERNEL-AC-004`: будущий common type допускается только при двух текущих consumers, pure stdlib dependency и доказанном удалении duplication/edge;
- `KERNEL-AC-005`: optional kernel не содержит Django/I/O/config/site/ports и получает отдельный DAG/test review до использования.

## 4. Внутри одного модуля

Стартовая структура остаётся плоской:

```text
modules/pages/
  models.py       PostgreSQL representation и DB constraints
  policy.py       чистые правила/normalization, если они нужны
  commands.py     write use cases и transaction boundaries
  queries.py      read use cases/DTO projections
  views.py        HTTP input/output, без бизнес-решений
  urls.py
  forms.py
  templates/pages/
  tests/
```

Не каждый модуль обязан иметь каждый файл. Файл появляется только при наличии соответствующей ответственности.

### Команды

Одна пользовательская операция — одна именованная функция в `commands.py`, например:

- `save_page_content(...)`;
- `undo_last_page_save(...)`;
- `publish_page(...)`;
- `accept_service_request(...)`.

Внешняя команда-владелец операции определяет единственную `transaction.atomic()` boundary, проверяет права и возвращает маленький result DTO. Вызванные публичные participant-функции других модулей изменяют только таблицы своего модуля внутри уже открытой транзакции и не открывают независимую outer transaction. Nested savepoint допустим только как локальная техническая деталь с доказанным rollback, но не как второй commit boundary. View только разбирает HTTP, вызывает одну внешнюю команду и строит ответ.

### Запросы

`queries.py` читает ORM и возвращает DTO/view model. Templates и API не получают свободный QuerySet или model graph. Это позволяет позже подключить Android API к тем же данным без копирования правил.

### Модели

Модели содержат поля, constraints и небольшие локальные invariants. Они не запускают межмодульные workflow, сетевые вызовы, Telegram, файловую очистку или глобальные locks через переопределённый `save()`.

## 5. Публичные API модулей

Другой модуль может использовать только явно объявленные команды, запросы, DTO и разрешённые FK contracts. Private implementation импортировать нельзя.

Закрытые schema содержимого, полный join 20 типов с 115 transport outcomes, renderer families, editor groups и media slots определяет `docs/clean-rebuild-content-contract.md`. Этот документ является частью архитектурного контракта, а не подсказкой реализации. Generic JSON/page builder, вывод структуры из HTML и выбор template/CSS/JS из данных запрещены.

Не создаётся универсальная service bus или plugin registry. В первой версии допустимы прямые Python calls через публичный module API. Если второй потребитель действительно потребует стабильного interface, он выделяется тогда, а не заранее.

Примеры:

- `gallery` использует публичный media selection/usage API, но не знает storage paths;
- `requests` использует audit writer и `NotificationPort`, но не импортирует Telegram;
- `news` в Dozvo использует media и sanitizer contracts, не меняя pages/gallery;
- `mobile_api` вызывает commands/queries customer modules, не дублируя бизнес-логику.

## 6. Где интерфейс действительно нужен

Порты вводятся только для внешнего мира, который может отказать или замениться, и принадлежат потребляющему модулю:

- `modules.requests.contracts.NotificationPort` — Telegram сейчас, другой transport позже;
- Django storage interface — файлы;
- локальный clock protocol только внутри конкретного модуля, где правило зависит от времени.

Не вводятся repository interfaces поверх Django ORM, unit-of-work поверх `transaction.atomic()`, event bus, service locator, CQRS framework или dependency-injection container. Для этого проекта они добавят код, но не добавят независимость.

## 7. Данные и владение

Каждая таблица имеет одного владельца:

| Данные | Владелец |
|---|---|
| staff users, roles | accounts |
| PageGrant | pages |
| Page, Route, current/previous, SiteSettings | pages |
| Asset/File/Usage | media |
| albums/photo ordering | gallery |
| ServiceRequest/deletion ledger projection | requests |
| AuditEvent | audit |

Модуль не изменяет таблицу другого модуля напрямую. Межмодульная операция вызывает публичную participant-функцию владельца данных. Никаких универсальных identity/reservation/receipt tables, orchestration layer, callback registry или event bus.

### 7.1. Exact FK и delete lifecycle

| FK/ссылка | Правило |
|---|---|
| `Page.parent → Page` | `PROTECT`; удалить можно только leaf после повторной проверки отсутствия детей под lock |
| `Route.page → Page` | `CASCADE` только внутри подтверждённого удаления Page; отдельное удаление PRIMARY запрещено, alias/redirect меняются командой pages |
| `PageContent.page → Page` | `CASCADE`; current+previous удаляются только вместе с подтверждённым Page |
| `PageGrant.page → Page` | `CASCADE`; `PageGrant.staff → User` — `PROTECT`; PageGrant принадлежит pages |
| `GalleryAlbum.page → Page` | `PROTECT`; gallery-page удаляется только командой gallery, которая сначала удаляет album composition и затем вызывает pages participant |
| `GalleryPhoto.album → GalleryAlbum` | `CASCADE` внутри удаления album; `GalleryPhoto.asset → Asset` — `PROTECT` |
| `AssetFile.asset → Asset` | `CASCADE`; физические файлы удаляются только после commit и только для exact rows команды media |
| `AssetUsage.asset → Asset` | `CASCADE`; target хранится как closed enum scope + UUID без cross-module FK, чтобы media не импортировал pages/gallery |
| `AuditEvent.actor_uuid` | nullable UUID+role snapshot, без FK; staff деактивируется, а audit сохраняется |
| `ServiceRequest`/deletion ledger | только внутренние связи requests; нет FK на staff/Page/media |

Staff User в MVP не удаляется физически: owner может деактивировать сотрудника после снятия PageGrant. Asset нельзя удалить при любом usage. Обычная pages-команда удаления отказывает для gallery kind; gallery владеет своей композицией и вызывает узкий pages participant, поэтому циклического import нет.

### 7.2. Владельцы межмодульных операций

| Операция | Outer transaction owner | Participants и порядок |
|---|---|---|
| создать/rename/move/reorder/publish/hide/change URL обычной Page | pages | accounts actor check → pages locks/constraints → audit append |
| сохранить PageContent | pages | accounts lock+session generation actor → lock Page/PageGrant/PageContent → validate/CAS → media replace usages → audit append |
| owner Undo PageContent | pages | accounts actor → lock/swap current+previous → media replace usages обеих версий → audit append |
| подтвердить удаление обычной leaf Page | pages | accounts owner → lock exact composition/children → media usage check/drop → delete Page aggregate → audit append |
| изменить/удалить gallery album/page | gallery | accounts actor DTO from HTTP adapter → lock gallery composition → media usages → pages narrow leaf-delete participant → audit append |
| upload/replace/delete Asset | media | media staging/locks/rows/usages → audit append; filesystem finalize/cleanup по явному failure contract |
| принять заявку | requests | validate/throttle → ServiceRequest + safe audit in one commit; `on_commit` вызывает injected NotificationPort вне transaction |
| staff create/password | accounts | accounts rows+generation → audit append; employee role fixed, owner invariant unchanged |
| staff reactivate | pages | accounts lock/reactivate+bump participant → transactional PageGrant zero proof → audit append; grants remain empty |
| PageGrant create/change/revoke | pages | accounts lock target User+bump generation participant → lock Page/PageGrant → exact groups → audit append |
| staff deactivate with grants | pages | accounts lock target User → lock/delete all PageGrant → accounts deactivate+bump participant → audit append |

Participant API не вызывает внешний transport, не делает commit и не вызывает обратно владельца операции. Если операция не помещается в одну DB transaction из-за файловой системы или Telegram, DB commit остаётся единственным authority, а внешний шаг имеет отдельный зафиксированный failure contract; универсальный UoW/outbox для этого не создаётся без отдельного решения.

### 7.3. Current+previous: CAS, права и lost response

`PageContent` хранит единственную monotonic ось сохранения — `generation` вне content envelope и payload hash; также current payload/hash и provenance автора/времени создания содержимого; nullable previous payload/hash с provenance; один bounded `last_operation_id/action/result_generation/result_hash`. Отдельной revision ordinal/receipt/history table нет. Editor создаёт UUID `operation_id` до отправки; он не даёт прав и проверяется только после authentication/authorization.

Save содержит `operation_id`, exact `base_generation`, `base_current_hash` и patch по именованным editor groups из content contract. Pages-команда блокирует actor User, затем Page, PageGrant и PageContent, повторно проверяет session generation, active role, grant и content CAS. Совпавшие `last_operation_id` и action возвращают прежний result без mutation/audit; совпавший ID с другой action fail-closed возвращает constant `409 OPERATION_CONFLICT`, mutation/audit0. Для другого ID несовпавший base даёт `409 STALE_CONTENT` с текущими generation/hash; server не делает auto-merge или last-write-wins.

Owner меняет все разрешённые schema groups. Employee передаёт только patch разрешённых текущим PageGrant групп; protected groups копируются из фактического current без изменения. Лишняя/запрещённая группа отклоняет всю операцию до записи. Успешный save атомарно делает полный прежний current новым previous, строит новый current, увеличивает generation, пересчитывает current+previous media usages и пишет один safe AuditEvent.

Undo разрешён только owner с exact current generation/hash и непустым previous. Под тем же lock exact payload bytes/hash/provenance current и previous меняются местами без reserialization/rehash, generation растёт, usages и audit обновляются. Employee не видит кнопку и получает 403 server-side; partial employee Undo отсутствует. URL/tree/publication/SiteSettings/grants не входят в swap.

После потерянного ответа немедленный повтор того же `operation_id` и той же action возвращает сохранённый result без второй mutation. Если bounded last-operation slot уже заменён, сервер не может доказуемо отличить старый retry от нового запроса на той же stale base: любой несовпавший `operation_id` с устаревшими generation/hash получает единый `409 STALE_CONTENT` с текущими generation/hash и обязан reload; server не угадывает исход и не повторяет действие. Receipt/history/audit lookup и клиентский retry-флаг для различения не добавляются. Provenance содержимого сохраняется в current/previous при swap; actor/time самой mutation фиксируются только в AuditEvent, а last-operation slot содержит только ID/action/result generation/hash. Rich payload/ПД в audit не попадают.

Acceptance:

- `PAGECAS-001`: два save с одним base дают один success и один 409 без lost update;
- `PAGECAS-002`: employee patch не читает/не меняет protected groups и не может Undo;
- `PAGECAS-003`: owner Undo меняет current/previous местами, generation только растёт;
- `PAGECAS-004`: immediate same-ID+same-action retry возвращает прежний result без mutation/audit; same ID с другой action даёт `409 OPERATION_CONFLICT`, mutation/audit0;
- `PAGECAS-005`: retry после intervening mutation, как и любой другой неизвестный operation ID на stale base, даёт единый `409 STALE_CONTENT`+reload без повторения действия;
- `PAGECAS-006`: payloads, hashes, provenance, media usages и audit атомарны; fault оставляет прежнее состояние;
- `PAGECAS-007`: URL/tree/publication/grants/SiteSettings не меняются save/Undo.

### 7.4. Staff identity до первой migration

Accounts сразу объявляет `User(AbstractUser)` как `AUTH_USER_MODEL`; built-in User+Profile и поздняя смена user model запрещены. Минимальные добавления: UUID primary key, exact role `OWNER|EMPLOYEE` и positive `generation` для отзыва sessions после password/role/active/grant-sensitive изменений. Username/password/active/staff/session используют стандартные Django contracts; email не обязателен и не является способом входа/подтверждения.

Ровно один active OWNER имеет username `nesadmin`; это DB constraint/service invariant, проверяемый до owner-sensitive operation. Employee деактивируется, а не удаляется физически. PageGrant принадлежит pages и FK `PROTECT` указывает на staff User. Будущий customer identity не добавляется в эту таблицу: в отдельной будущей копии он получает отдельный module/model и не расширяет staff roles сейчас.

Нет Profile table, generic identity abstraction, social login, MFA, email confirmation или customer placeholders. `USER-AC-001..004`: AUTH_USER_MODEL существует до first migration; owner invariant; deactivation/session generation; отсутствие customer/auth expansion.

#### 7.4.1. PageGrant и отзыв sessions

`PageGrant` имеет unique `(staff_id, page_id)` и ровно `groups` как sorted non-empty subset closed enum `{text, prices}` из content contract. Grant допустим только active `EMPLOYEE`; owner не нуждается в grant. Empty desired groups означает revoke и удаляет row. Отдельных grant version/history/expiry/inheritance, wildcard page/field и deny-rules нет.

Pages владеет четырьмя owner-only commands: `set_page_grant(staff_id, page_id, desired_groups, base_user_generation, base_grant_hash)`, `revoke_page_grant(...)` как desired empty set, `deactivate_staff(staff_id, base_user_generation, base_grants_digest)` и `reactivate_staff(staff_id, base_user_generation)`. Accounts предоставляет только узкие participants `lock_staff_for_grant()` и `bump_generation()/deactivate_and_bump()/reactivate_and_bump()`; participant не открывает transaction, не импортирует pages и меняет только User.

Единый lock order для auth/grant-sensitive writes: все затронутые User rows в ascending UUID → Page в ascending UUID → PageGrant → PageContent → media usages → audit. Actor owner и target employee блокируются accounts participant в этом порядке; затем повторно проверяются owner session generation, target generation/active/role, Page kind и base grant hash. Password/reset/active operations используют тот же User-first order. Это сохраняет exact DAG `pages→accounts`, обратного import нет.

Успешный set/revoke в одной pages-owned transaction меняет/удаляет ровно один PageGrant, увеличивает target `User.generation` на 1 и пишет один safe AuditEvent. Успешная deactivation в одной pages-owned transaction удаляет все grants target employee, ставит `is_active=false`, увеличивает generation один раз и пишет один aggregate event с count без page names/content. Fault откатывает grants, User и audit целиком. Reactivation также имеет pages-owned outer transaction: после User-first locks она транзакционно доказывает PageGrant count0, вызывает accounts `reactivate_and_bump` participant и пишет audit; grants автоматически не восстанавливаются, generation увеличивается один раз, reverse accounts→pages import отсутствует.

Стандартная server-side session хранит exact User generation. Каждый private request до use case сравнивает session generation с текущей User; protected write повторяет проверку под User lock. После grant mutation/deactivation все прежние sessions target employee получают 401 на следующем private request. Новая login session видит только current grants.

Concurrent save/revoke сериализуются User-first: если save получил lock первым, он может завершить одну разрешённую mutation, затем revoke commit отзывает дальнейшие requests; если revoke получил lock первым, save после ожидания видит stale session generation/отсутствующий grant и не меняет content/usages/audit. Concurrent grant commands с одним base имеют одного winner, второй получает 409+reload. Exact lost-response retry без отдельной operation identity наблюдаемо неотличим от concurrent identical command, поэтому любой stale `base_user_generation/base_grant_hash`, включая такой retry, получает 409+reload и не повторяет mutation/audit. Operation receipt/history/audit lookup не добавляются.

Acceptance:

- `GRANT-AC-001`: only owner invokes grant/deactivate commands; employee/anonymous get 403/401 before mutation;
- `GRANT-AC-002`: only active EMPLOYEE receives exact non-empty subset `{text,prices}` valid for target Page kind; unknown/wildcard/empty row rejected;
- `GRANT-AC-003`: set/change/revoke atomically changes one grant, bumps target generation exactly once and appends one safe audit;
- `GRANT-AC-004`: deactivate atomically removes all target grants, sets inactive, bumps generation once; fault rolls back all three;
- `GRANT-AC-005`: reactivate restores no grants; new session starts with current empty/explicit grants only;
- `GRANT-AC-006`: every old target session is rejected after committed grant/deactivate/password/active generation bump;
- `GRANT-AC-007`: save-first vs revoke-first has the two exact serialized outcomes above, never unauthorized post-revoke mutation;
- `GRANT-AC-008`: two grant commands with one base yield one success/one 409; grant/user/audit never diverge;
- `GRANT-AC-009`: lost-response retry и concurrent identical loser с stale base одинаково получают 409+reload; mutation/audit0, operation identity/history0;
- `GRANT-AC-010`: lock-order fitness test proves User→Page→Grant→Content for grant, save, deactivate and password/active participants; reverse edge accounts→pages absent.

### 7.5. Media decode boundary

Сохраняется утверждённый D-324 профиль новых загрузок:

- один JPEG/PNG/WebP до 1,000,000 bytes; multipart body до 11 MiB;
- decoded максимум 40,000,000 pixels и 10,000 px по стороне;
- extension, declared MIME и decoded format совпадают; GIF/APNG/animated WebP и повреждённые/active formats отвергаются;
- EXIF orientation применяется, затем EXIF/GPS/XMP/ICC/text metadata удаляются из public result;
- public outputs — newly encoded WebP max side 1920 и preview 480 без upscale, quality82; private source не имеет public URL;
- exact214 gallery originals являются отдельным byte-preserving import и decoder не вызывают.

Native decode/encode выполняет один fixed local worker, потому что 40 MP и codec parsing являются реальной memory/native-code boundary рядом с application secrets. Worker: network none, no Docker socket/DB/secrets/project media, non-root UID, readonly rootfs, cap-drop ALL, no-new-privileges, 512 MiB RAM, 1 CPU, pids64, 15 s wall budget, 128 MiB bounded tmpfs/exchange, строго один job. Protocol принимает только bytes+declared format и возвращает два bounded results+metadata; arbitrary path/URL/command отсутствуют.

Django до worker проверяет count/body/input bytes/extension/MIME magic. Worker до allocation проверяет dimensions/frame count/format; cgroup/RSS/time/tmpfs failure даёт reject. Timeout/unknown outcome не повторяется автоматически: exchange quarantined, worker должен вернуться в clean-ready state или быть заменён до нового job. Ни DB row, ни READY Asset при unknown/failure не создаются.

Успешный lifecycle минимален: private source и generated files пишутся в exact new staging; SHA/size/format проверяются; первая media transaction создаёт `STAGED` Asset/File rows; same-filesystem atomic rename публикует exact directory; вторая короткая transaction повторно сверяет files и переводит Asset в `READY`. Public/pages/gallery queries видят только READY. Fault до READY оставляет только bounded STAGED+exact directory, которые отдельная owner/retention cleanup удаляет после проверки age/state/containment; чужие files/usages не затрагиваются.

Worker не является queue/background platform: broker, scheduler, retries, job table, arbitrary transforms и remote API отсутствуют. Fitness checks доказывают actual container limits/isolation, positive max-profile decode, byte/pixel/side boundaries, metadata stripping, animation rejection, timeout/RSS/tmpfs failure, STAGED cleanup и отсутствие READY/DB/file leak.

### 7.6. Полный lifecycle Page и navigation

Структурные действия доступны только active OWNER; employee получает 403 и работает только через PageContent contract. Редкие owner mutations сериализуются одним существующим `SiteSettings.structure_generation`: команда принимает exact base generation, под `select_for_update` блокирует singleton и затронутые Page/Route rows в стабильном порядке, повторно проверяет права/constraints, увеличивает generation и пишет один safe AuditEvent в той же transaction. Stale base даёт 409+reload. Отдельные workflow/status/operation/receipt/tree-version tables не создаются.

Ровно семь pages-команд:

1. `create_page`: owner заранее создаёт UUID и выбирает один утверждённый kind, name, parent и свободный PRIMARY path. Новый Page всегда unpublished; current — один schema-valid initial payload выбранного kind, previous=null, media usages empty. Повтор существующего UUID с доказанным `PAGE_CREATED` audit возвращает existing Page, несовместимый kind даёт conflict. Автопредложение slug — UI helper, server всё равно валидирует exact path.
2. `rename_page`: меняет только `Page.name`; H1, SEO, kind, URL и content не переписываются. Пустое/oversize имя запрещено.
3. `move_page`: меняет parent и exact position, блокируя old/new sibling sets; self/descendant parent, unknown parent и cycle запрещены. URL самой Page и всех descendants не меняются.
4. `reorder_children`: принимает parent/null и полный exact ordered UUID list фактических direct children. Missing/extra/duplicate/foreign child отклоняет всю операцию; positions становятся contiguous без частичного порядка.
5. `set_publication`: меняет только boolean самой Page. Publish требует valid current schema, PRIMARY и все referenced READY media. Hide не меняет child flags/routes/content; exact URL скрытой Page даёт пустой HTTP 200 по D-052, а independently published children остаются public.
6. `change_primary_url`: только для созданной в новой системе Page; imported/protected legacy PRIMARY неизменяем. Новый exact path обязан быть свободен во всём Route namespace и пройти closed public-path validation. В одной transaction PRIMARY получает новый path, прежний path становится REDIRECT той же Page; все прежние redirects query-time ведут прямо на current PRIMARY, без redirect chains/cycles. Child URLs не меняются.
7. `delete_leaf_page`: отдельный owner POST с CSRF, текущим паролем, Page UUID, base structure generation и typed exact `name`, PRIMARY path и canonical composition digest. Confirmation показывает routes, children, current/previous presence+hashes, PageGrants и media-usage counts; любая перемена требует нового preview. Под lock children count должен быть 0, gallery kind удаляется только gallery-командой. Transaction удаляет exact Page routes, current+previous, grants и только её AssetUsage, затем Page; общие Asset/File и чужие usages сохраняются, physical media не очищается. Audit сохраняет `PAGE_DELETED`+UUID, поэтому immediate lost-response repeat может вернуть already-deleted; неизвестный UUID без такого audit даёт 404. Subtree/cascade-to-children отсутствует.

Navigation — read-only pages query, не вторая editable модель. Она выбирает published Pages, сортирует siblings по `(position, UUID)`, пропускает hidden ancestors и поднимает published descendants к ближайшему published ancestor по D-239/D-240. Созданная unpublished Page отсутствует; publish/hide/move/reorder отражаются сразу после commit. Fixed approved Header exact-six остаётся явной проекцией из content contract и автоматически не разрастается; автоматическое включение D-032 относится к соответствующим section/catalog navigation blocks. Breadcrumbs используют тот же ancestor projection, не меняя реальное parent.

Acceptance:

- `PGLC-001`: employee не вызывает ни одну structural command; owner stale generation получает 409 без mutation/audit;
- `PGLC-002`: create даёт unpublished Page+PRIMARY+valid current, previous=null/usages0; UUID replay не дублирует;
- `PGLC-003`: rename не меняет H1/SEO/URL/content, move не меняет ни один URL;
- `PGLC-004`: move cycle/self/unknown запрещены; concurrent structure commands имеют одного победителя;
- `PGLC-005`: reorder требует exact sibling set и атомарно создаёт contiguous positions;
- `PGLC-006`: publish invalid content/route/media запрещён; hide сохраняет child publication и даёт blank200 только exact hidden Page;
- `PGLC-007`: navigation автоматически включает published Page, исключает hidden и promotes published descendants; Header exact-six не меняется;
- `PGLC-008`: protected legacy PRIMARY изменить нельзя; new Page URL change создаёт direct 301 без chain/cycle/collision и не меняет child URLs;
- `PGLC-009`: delete preview и POST связаны с exact name+PRIMARY+composition+generation; drift/password/CSRF отказ не пишет данные;
- `PGLC-010`: non-leaf delete всегда отказывает; subtree не удаляется; gallery delete идёт через gallery owner;
- `PGLC-011`: successful leaf delete атомарно удаляет Page/routes/current/previous/grants/own usages, сохраняет shared files/usages и оставляет бывшие URLs 404;
- `PGLC-012`: fault откатывает весь aggregate; lost-response repeat не удаляет новую Page с переиспользованным URL.

### 7.7. Минимальный AuditEvent lifecycle

`AuditEvent` — одна append-only для product commands таблица модуля `audit`, а не event bus, технический лог, аналитика или юридически неизменяемый архив. Поля закрыты:

- UUID `id`, UTC `occurred_at` из server clock и enum `action`;
- `actor_kind=USER|SYSTEM|ANONYMOUS`; для USER обязательны `actor_uuid` и role snapshot `OWNER|EMPLOYEE`, для SYSTEM/ANONYMOUS эти поля null;
- `target_type=USER|PAGE|ASSET|GALLERY|SERVICE_REQUEST|SITE_SETTINGS|AUDIT`, nullable `target_uuid` и nullable `secondary_uuid`;
- canonical JSON `detail` ≤2,048 UTF-8 bytes, object depth1/≤8 keys, без arbitrary keys/text. Разрешены только `operation_id` UUID, `generation` non-negative integer, `groups` sorted subset `{text,prices}`, `count` integer 0..1,000,000, `state` closed action-specific enum, `reason` closed action-specific enum и SHA-256 `current_hash|previous_hash`.

DB constraints и один validator требуют допустимую actor/target/detail форму для каждого action. Запрещены content payloads, names/page titles, URLs/query, request name/phone/vehicle/comment/consent, submitted/stored login label, password/token/session, IP/User-Agent, media path/file bytes, Telegram payload/response, exception text/traceback и secrets. Staff/customer/request identity представлена только UUID; role snapshot остаётся после деактивации.

Closed v1 action enum:

- auth/accounts: `AUTH_LOGIN_SUCCEEDED`, `AUTH_LOGIN_FAILED`, `AUTH_LOGOUT`, `AUTH_PASSWORD_CHANGED`, `STAFF_CREATED`, `STAFF_REACTIVATED`, `STAFF_DEACTIVATED`;
- grants/pages/settings: `PAGE_GRANT_SET`, `PAGE_GRANT_REVOKED`, `PAGE_CREATED`, `PAGE_RENAMED`, `PAGE_MOVED`, `PAGE_REORDERED`, `PAGE_PUBLICATION_CHANGED`, `PAGE_URL_CHANGED`, `PAGE_CONTENT_SAVED`, `PAGE_CONTENT_UNDONE`, `PAGE_DELETED`, `SITE_SETTINGS_CHANGED`;
- media/gallery: `ASSET_UPLOADED`, `ASSET_REPLACED`, `ASSET_DELETED`, `GALLERY_CHANGED`, `GALLERY_DELETED`;
- requests/maintenance: `SERVICE_REQUEST_ACCEPTED`, `SERVICE_REQUEST_DELETED`, `SERVICE_REQUEST_RETENTION_BATCH`, `AUDIT_RETENTION_BATCH`.

Exact v1 target/detail matrix; все неуказанные detail keys запрещены:

| Actions | Target / secondary | Обязательный detail |
|---|---|---|
| `AUTH_LOGIN_SUCCEEDED`, `AUTH_LOGOUT` | USER / — | `{}` |
| `AUTH_LOGIN_FAILED` | USER с null UUID / — | `reason=INVALID_CREDENTIALS|THROTTLED|INACTIVE` |
| `AUTH_PASSWORD_CHANGED`, `STAFF_CREATED`, `STAFF_REACTIVATED` | USER / — | `generation` |
| `STAFF_DEACTIVATED` | USER / — | `generation`, `count` снятых grants |
| `PAGE_GRANT_SET` | PAGE / staff UUID | `generation` staff, non-empty `groups` |
| `PAGE_GRANT_REVOKED` | PAGE / staff UUID | `generation` staff, `groups=[]` |
| `PAGE_CREATED`, `PAGE_RENAMED`, `PAGE_MOVED`, `PAGE_REORDERED`, `PAGE_PUBLICATION_CHANGED`, `PAGE_URL_CHANGED`, `PAGE_DELETED` | PAGE / — | structure `generation`; additionally reorder `count`, publication `state=PUBLISHED|HIDDEN` |
| `PAGE_CONTENT_SAVED`, `PAGE_CONTENT_UNDONE` | PAGE / — | `operation_id`, content `generation`, `current_hash`; `previous_hash` required when previous exists and otherwise absent |
| `SITE_SETTINGS_CHANGED` | SITE_SETTINGS с null UUID / — | settings `generation` |
| `ASSET_UPLOADED`, `ASSET_REPLACED`, `ASSET_DELETED` | ASSET / — | `state=READY|DELETED` matching action |
| `GALLERY_CHANGED`, `GALLERY_DELETED` | GALLERY / — | composition `generation` |
| `SERVICE_REQUEST_ACCEPTED` | SERVICE_REQUEST / — | `{}`; actor ANONYMOUS |
| `SERVICE_REQUEST_DELETED` | SERVICE_REQUEST / — | `reason=OWNER`; actor USER/OWNER |
| `SERVICE_REQUEST_RETENTION_BATCH` | SERVICE_REQUEST с null UUID / — | `reason=RETENTION`, `count`; actor SYSTEM |
| `AUDIT_RETENTION_BATCH` | AUDIT с null UUID / — | `reason=RETENTION`, `count`; actor SYSTEM |

Успешная product mutation добавляет ровно одно соответствующее событие внутри той же outer DB transaction; audit insert failure откатывает mutation. Для upload/replace событие пишется только во второй media transaction вместе с exact переходом `STAGED→READY`; временный STAGED события успеха не имеет. Batch/deactivate события используют safe `count`, а не event на каждую строку. `PAGE_CREATED|PAGE_DELETED` с target UUID и `PAGE_GRANT_SET|PAGE_GRANT_REVOKED` с generation/groups поддерживают уже зафиксированные bounded lost-response checks; AuditEvent не становится general receipt store. Invalid/stale/denied product mutation audit не пишет. Успешный login выдаёт session только после `AUTH_LOGIN_SUCCEEDED`; failed login остаётся denied даже при сбое отдельной audit insert и пишет только constant technical error. Logout всегда уничтожает session, даже если его best-effort audit insert отказал. Automatic Telegram status transitions и read-only views событий не создают.

Чтение доступно только active OWNER через private/no-store list/detail с pagination ≤100 и фильтрами exact action/date/target UUID. Employee, anonymous и public API не читают; edit/delete-one/export/full-text/analytics отсутствуют. UI никогда не показывает сырой JSON как HTML и рендерит только typed safe fields.

Retention — 180 суток. Закрытая owner-owned/scheduled command без пользовательских path/filter/age аргументов под одним cutoff удаляет максимум 5,000 событий с `occurred_at < cutoff` за transaction и, если count>0, добавляет один `AUDIT_RETENTION_BATCH` с count. Boundary и более новые rows сохраняются; повтор идемпотентно продолжает следующий batch. Audit входит в обычный PostgreSQL dump, generation counts и encrypted external backup, но не имеет отдельного export/archive/ledger. Restore сначала проверяет raw audit count вместе с dump; cleanup не запускается до завершения restore acceptance и возврата scheduler.

Acceptance:

- `AUDIT-AC-001`: every successful listed product mutation commits exactly one valid action event atomically; injected audit failure rolls back mutation;
- `AUDIT-AC-002`: action enum, actor/target form and detail keys/types/caps are closed; unknown/oversize/nested/arbitrary detail is rejected;
- `AUDIT-AC-003`: audit rows contain no content, request ПД, credentials/session, network identifiers, paths, transport payloads, exception text or secrets;
- `AUDIT-AC-004`: PAGE/grant lost-response lookup uses exact action+target/generation/groups and cannot authorize an unrelated or intervening operation;
- `AUDIT-AC-005`: only active OWNER can read bounded no-store list/detail; employee/anonymous/export/edit/delete-one are denied;
- `AUDIT-AC-006`: cutoff boundary is retained, older rows delete in batches≤5,000 and one safe aggregate retention event is written only for nonzero count;
- `AUDIT-AC-007`: DB backup/restore preserves raw audit count before reconciliation/retention; no separate audit archive or deletion ledger exists;
- `AUDIT-AC-008`: login success is not issued without its audit event; failed login/logout remain safely denied/terminated when best-effort audit writing fails and emit no submitted identifier/ПД.

## 8. Модульность для Dozvo и будущего кабинета

Эта секция описывает пригодность архитектурных границ к будущему fork/copy, а не текущий scope. Новый runtime «Эстакады» не содержит Dozvo settings, theme, tables, migrations, feature flags, tenant/site selection или placeholder apps.

Модуль должен подключаться четырьмя явными действиями:

1. добавить Django app в site settings;
2. подключить его URL;
3. добавить его navigation entry в site config;
4. предоставить templates в выбранной theme.

`news` и `events` имеют собственные модели, commands, queries и templates. Они не превращаются в конфигурируемый generic page builder.

Клиентский кабинет отделён от staff accounts. Android — отдельный клиент. API является adapter: authentication, serialization и HTTP живут там, а appointments/vehicles/customer rules остаются в серверных modules и используются также web cabinet.

## 9. Контроль объёма кода

Coherent DB+media snapshot, exact current/previous projection, public/private separation, caps and cleanup are defined by `docs/clean-rebuild-transfer-contract.md`. Private data does not share the public manifest; password hashes are reset/recovered rather than serialized.

Minimal request fields, default-off LEGAL gate, 30-day retention, owner/staff access, owner-only delete and Telegram-only best-effort policy are defined by `docs/clean-rebuild-requests-contract.md`. No CRM workflow, email, outbox or retry worker is part of MVP.

Целевой размер первой версии, без migrations/vendor/generated/static media:

- product Python: ориентир 8–15 тысяч строк;
- JS: только меню, gallery interaction и минимальный editor behavior;
- одна реализация каждого use case;
- один renderer public/preview на family;
- один sanitizer policy;
- один media storage path;
- один Telegram adapter.

Это ориентир сложности, не формальная метрика качества. Нельзя дробить код на бессодержательные файлы ради красивого счётчика.

Перед добавлением abstraction задаются вопросы:

1. Есть ли сейчас два реальных потребителя или изменяемая внешняя граница?
2. Уменьшит ли abstraction число зависимостей?
3. Можно ли проверить её контракт независимо?

Если ответы отрицательные, abstraction не создаётся.

## 10. Архитектурные fitness checks

В обычный test/check workflow входят:

- AST/import check dependency directions;
- запрет любых imports из старого `app/`;
- exact DAG из §3: audit→none; accounts→audit; media→audit; pages→accounts/media/audit; gallery→pages/media/audit; requests→audit; private/cyclic imports absent;
- отсутствие network calls во views/models/transactions;
- transaction boundary только в commands;
- templates получают DTO, а не unrestricted QuerySet;
- `manage.py check` и migration drift check;
- security boundary tests;
- pre-first-migration custom User invariant и отсутствие staff/customer смешения;
- actual media-worker isolation/resource profile и STAGED→READY/cleanup faults;
- exact URL/data/media acceptance.

Не требуется новый тяжёлый инструмент: сначала достаточно небольшого project-owned import checker. Внешний dependency analyzer рассматривается только если собственный bounded check перестанет покрывать правила.

## 11. Решения, предотвращающие будущую переделку

- Site-specific визуальная тема отделена от данных и use cases.
- Web и будущий API вызывают общие commands/queries.
- News/events/customer features подключаются через public module APIs без обязательного общего слоя.
- PostgreSQL и Django остаются деталями modules, но не протекают в templates/API contracts.
- Внешние интеграции заменяемы через узкие ports.
- Architecture Decision Records фиксируют только действительно долговечные решения.
- У каждого нового feature сначала acceptance contract и owner данных, потом code.

## 12. Что намеренно не решается заранее

- точная модель новостей/афиши Dozvo;
- API authentication Android;
- customer privacy/legal lifecycle;
- push notifications;
- background jobs;
- multi-site/tenant engine;
- generic plugin marketplace.

Границы позволяют добавить это позже, но текущий проект не платит кодом за ещё не утверждённые функции.

## 13. Измеримые quality attributes

Числа latency/load ниже — предварительный release-candidate budget, а не обещание production capacity или SLA. Их проверяют на одном зафиксированном профиле контейнеров и компьютера, с warm PostgreSQL, loopback network, exact 115 transport outcomes и фактическим объёмом media из REBUILD-1; профиль, dataset digest и результаты входят в отчёт. После выбора VPS бюджет повторно калибруется без ослабления аппаратно-независимых правил целостности и безопасности.

| ID | Stimulus | Environment | Required response | Measure |
|---|---|---|---|---|
| `QA-PERF-001` | Посетитель открывает public URL | Зафиксированный RC-профиль, warm DB; каждый из 115 outcomes запрошен минимум 5 раз после одного warm-up | Правильный status/redirect/body family, без записи и без `5xx` | server-side p95 ≤ 750 ms, каждый ответ ≤ 2 s; 0 неожиданных status/redirect и 0 `5xx` |
| `QA-LOAD-001` | 10 клиентов одновременно читают public URLs | Тот же RC-профиль; 1,000 GET/HEAD, равномерно по canonical public outcomes, без admin/upload | Сервис остаётся корректным, DB pool и память возвращаются к исходному steady state | p95 ≤ 1 s, каждый ответ ≤ 3 s, `5xx=0`, timeout=0; это только локальный low-load test, не оценка числа production-посетителей |
| `QA-EDIT-001` | Два редактора сохраняют один base одновременно | 20 независимых пар на RC-профиле; одинаковые generation/hash, разные operation ID | Ровно один save успешен, второй получает `409`; current/previous/usages/audit согласованы | 20/20 пар: success=1, stale=1, lost update=0, deadlock=0; каждая пара завершается ≤ 5 s |
| `QA-UPLOAD-001` | Staff загружает изображение на границе или за границей лимита | Один fixed isolated worker из §7.5 | Допустимый файл становится READY только после проверки/atomic finalize; oversize/bomb/animation/timeout не создаёт READY/DB usage | JPEG/PNG/WebP ≤ 1,000,000 B; multipart ≤ 11 MiB; ≤ 40 MP; сторона ≤ 10,000 px; frame count=1; worker ≤ 512 MiB/1 CPU/64 pids/15 s/tmpfs128 MiB; boundary и cap+1 проходят exact tests |
| `QA-REQUEST-001` | Посетитель отправляет заявку либо превышает предел | Intake отдельно разрешён после LEGAL-01; direct-client→Nginx→protected Unix socket boundary и Django включены | Только exact valid POST пишет одну row; spoofed/missing ingress identity, invalid/duplicate/throttled/oversize не пишет DB/audit/Telegram | body 1..8,192 B; name 1..100; raw vehicle make/model ≤100 каждый, year=4 ASCII digits, canonical vehicle total ≤300; comment ≤4,000; consent version 1..64; phone normalizes в `+7`+10 digits; `$binary_remote_addr` 1r/s, Nginx burst5; spoof+two-client+cap/cap+1+duplicate tests |
| `QA-BACKUP-001` | Автоматическая копия должна ограничить возможную потерю | После local cutover; PostgreSQL+READY media+catalog одной generation, deletion ledger берётся latest независимо; локальная и encrypted external destinations | Создаётся проверенная coherent generation; неполная/непроверенная generation не становится current | target RPO ≤ 24 h; минимум 7 суток сохранения; ежедневно digest/count verification; ledger generation не меньше catalog и tombstone durability остаётся синхронной по request contract |
| `QA-RESTORE-001` | Owner запускает восстановление после отказа | Изолированная пустая DB/media root, одна из последних 7 verified generations, latest valid deletion ledger; public HTTP закрыт | DB/media восстанавливаются, tombstones применяются, migrations/counts/SHA/115 outcomes проверяются до открытия HTTP | target RTO ≤ 4 h от подтверждённого старта до pass/fail отчёта; 100% DB checks, media SHA и route checks; одна ошибка оставляет HTTP закрытым |
| `QA-ROLLBACK-001` | После local cutover обнаружен критический дефект нового runtime | Старый runtime/DB/media read-only и новая coherent backup generation сохранены | Owner может выбрать старый runtime без преобразования или удаления старых данных | rollback rehearsal проходит до `REBUILD-Q003`; старые runtime/DB/media сохраняются минимум 7 полных суток после local cutover и дольше, пока нет owner acceptance + успешного new restore; удаление только через `REBUILD-Q004` |

`QA-PERF-001/QA-LOAD-001` не требуют отдельного observability/performance продукта: достаточно project-owned bounded runner и закрытого JSON summary без URL query, payload, ПД и response bodies. Если RC не проходит, сначала измеряется конкретный bottleneck; cache, queue, CDN, replica или новый service нельзя добавлять только ради достижения таблицы без отдельного решения.

## 14. Backup/restore proof новой системы

Старые `scripts/local-backup.ps1`, `scripts/local-restore-check.ps1` и их helpers — только code candidates. Их проверенные идеи (custom-format dump, SHA, atomic catalog, isolated restore, exact cleanup) можно перенести маленькими reviewed fragments, но старые success receipts не доказывают новую schema, migrations, code/config или HTTP.

### 14.1. Release manifest и состав generation

Каждый новый release до backup получает canonical `release-manifest.json` без секретов и ПД:

- manifest schema version и release ID;
- digest exact source/package, dependency lock и static files;
- exact Python/Django/PostgreSQL major+minor compatibility profile;
- ordered Django app+migration names и SHA-256 каждого migration file;
- normalized PostgreSQL schema fingerprint после migrations;
- content/route/media/request contract versions;
- closed inventory имён обязательных config keys, secret mounts и external destinations, только `required|optional` и type, без values/paths с username;
- deletion-ledger format version и required minimum generation rule.

Backup generation содержит PostgreSQL custom-format dump, canonical READY-media archive/inventory, release manifest, закрытый generation manifest с counts/byte sizes/SHA-256 и safe result. Secrets, environment values, logs, sessions export, absolute host paths и deletion-ledger bytes в generation не входят. Catalog хранит только generation ID/digest, release-manifest digest и observed deletion-ledger generation/digest; latest ledger остаётся отдельной authority по request contract.

### 14.2. Coherent backup без новой платформы

Один existing deployment wrapper перед maintenance фиксирует safe pre-run state: digest текущего verified catalog и exact enabled/disabled bitmap для editor/admin mutations, upload, request POST и scheduled cleanup/retention. Поэтому default-off request POST не может случайно включиться после backup. Wrapper входит в bounded write-maintenance, закрывает эти write paths, ждёт завершения текущих writes и доказывает writer inventory=0. Public GET может продолжаться. Затем один run:

1. сверяет deployed code/config-name inventory с release manifest и applied migrations;
2. снимает custom-format DB dump и READY-media inventory/archive;
3. повторно сверяет migration/schema fingerprint, media inventory и writer inventory до выхода из maintenance;
4. проверяет archive listings, counts и SHA и завершает immutable candidate generation, не меняя current catalog;
5. копирует тот же immutable candidate в локальное и отдельно зашифрованное внешнее место и проверяет digest read-back;
6. только после двух verified copies назначает generation current одним catalog atomic rename.

Maintenance завершается одним обязательным `finally` независимо от success, validation error, external-copy error или штатного прерывания wrapper. Он закрывает backup handles/processes, завершает либо после exact containment check удаляет/изолирует staging только текущего run, повторно доказывает отсутствие активного backup writer и проверяет catalog: на success — exact новый digest, до atomic catalog rename или на failure — exact сохранённый pre-run digest. Затем wrapper восстанавливает **ровно pre-run bitmap** write paths. Ошибка внешнего storage поэтому оставляет прежнюю valid generation current, но не оставляет ранее доступный editor/upload бессрочно закрытым и не включает ранее выключенный request POST/cleanup.

Если exact pre-run state/catalog digest неизвестен, backup writer не завершён, staging/catalog имеет неоднозначную целостность или безопасное восстановление bitmap не подтверждено, `finally` остаётся fail-closed: writes не открываются, current pointer не угадывается, safe exit report требует owner inspection. Это аварийная неоднозначность, а не обычный failure path; retry-in-place, второй coordinator, daemon или backup state machine не добавляются.

Это один dump+media workflow, не scheduler/catalog service: запуск предоставляет обычный host scheduler, расписание и external destination утверждаются в launch configuration. Retention — минимум семь суток по `QA-BACKUP-001`; cleanup видит только verified catalog generations, не читает product tables и не удаляет latest valid ledger.

### 14.3. Изолированное восстановление

Restore принимает только exact generation ID и отдельно latest verified deletion ledger. Он работает в новой пустой DB/media root, с outbound network disabled и `SERVICE_REQUESTS_ENABLED=false`; source generation/read-only backup не изменяется.

Порядок fail-closed:

1. проверить generation/catalog/release-manifest digests, archive paths/types и config/secret **name/presence** inventory без вывода values;
2. запустить exact code/dependency release, чей digest указан в manifest; другой code release запрещён;
3. восстановить dump одной управляемой операцией и media в staging, проверить все SHA/counts;
4. потребовать exact equality applied migrations+file hashes и schema fingerprint; pending/extra/drift запрещены, migrations автоматически не накатываются;
5. проверить latest ledger chain/generation, удалить tombstoned ServiceRequest и rebuild projection по request contract;
6. в той же закрытой reconciliation phase удалить все Django session rows и увеличить `User.generation` всех staff, чтобы backup не оживил старый authenticated session;
7. запустить Django check и приложение только в isolated network; readiness должен дать 200;
8. выполнить exact 115 status/redirect public smoke, anonymous private denial и доказать request POST absent/404, outbound attempts=0;
9. остановить приложение, зафиксировать safe counts/digests/result и удалить только exact temporary restore staging после containment check.

Любая ошибка оставляет restored HTTP закрытым и не меняет current production/local target. Promotion/replacement, DNS/Nginx switch и production restore не входят в check и требуют отдельного owner action. Перед `REBUILD-Q003` один полный restore-check проходит из фактической внешней encrypted copy; после cutover — минимум раз в семь суток и после изменения schema/backup tooling.

Acceptance:

- `BACKUP-AC-001`: manifest связывает exact code/dependencies/migrations/schema/contracts/config-secret names без values/ПД;
- `BACKUP-AC-002`: bounded write-maintenance фиксирует pre-run catalog digest+write bitmap, а before/after checks доказывают coherent DB+READY-media generation;
- `BACKUP-AC-003`: incomplete/drifted/unverified generation не становится current, прежняя current сохраняется; catalog atomic rename выполняется только после двух verified copies;
- `BACKUP-AC-004`: local и encrypted external immutable copies имеют один verified digest;
- `BACKUP-AC-005`: restore отказывает при code/migration/schema/config-name mismatch до HTTP;
- `BACKUP-AC-006`: до ledger/session/generation reconciliation raw restore отдельно доказывает exact dump row counts и READY-media counts/SHA в empty target; reconciled counts затем проверяются отдельным следующим acceptance-сценарием;
- `BACKUP-AC-007`: latest independent deletion ledger применяется, tombstoned request rows=0, sessions=0 и staff generations увеличены до HTTP;
- `BACKUP-AC-008`: readiness200, exact115 transport smoke, private denial, request POST absent и network attempts0;
- `BACKUP-AC-009`: failure не меняет working target/source/catalog; temporary cleanup exact и bounded;
- `BACKUP-AC-010`: external full restore-check проходит до local cutover, затем weekly и после schema/tool change в пределах `QA-RESTORE-001`.
- `BACKUP-AC-011`: на success и обычном failure обязательный `finally` закрывает backup writers, ограничивает cleanup exact staging run, подтверждает expected catalog digest и восстанавливает ровно pre-run write bitmap; ambiguity оставляет writes fail-closed и требует owner inspection.

## 15. Стандарт профессионального архитектурного review

Документ не считается утверждённой архитектурой после одной авторской вычитки. До `REBUILD-Q001` review обязан проверить и письменно закрыть:

1. **System context и actors:** anonymous visitor, employee, owner, future customer, Telegram, PostgreSQL, media storage, Nginx и backup operator.
2. **Quality attributes:** простота изменений, безопасность, сохранность данных, доступность, производительность, наблюдаемость, тестируемость и восстанавливаемость; для каждого — конкретный сценарий, а не лозунг.
3. **Change scenarios:** добавить Dozvo news/events; добавить web cabinet и Android API; заменить Telegram; добавить новый page family; изменить media storage; восстановиться из backup.
4. **Dependency and ownership proof:** каждый import direction, table owner, transaction owner, public module API и forbidden dependency.
5. **Data lifecycle:** create/read/update/delete, current+previous, media usage, requests/PII, audit retention, backup/restore и destructive cleanup.
6. **Security review:** authentication, session, authorization, CSRF, XSS/sanitization, file handling, secrets, logging/error handling, network boundaries и future API boundary.
7. **Concurrency/failure analysis:** lost response, concurrent save/undo, duplicate request, Telegram failure, partial media write, DB failure and migration interruption.
8. **Operational model:** settings/secrets, migrations, static/media, health, logs, backup, restore, rollback and deploy checklist.
9. **Complexity audit:** каждая abstraction/module/port обязана иметь владельца, потребителя и удаляемую сложность; speculative layers отклоняются.
10. **Acceptance/fitness matrix:** архитектурное правило получает автоматическую проверку либо явно документированную ручную проверку.

Review выдаёт findings по приоритету, trade-off/risk register и один из вердиктов: `APPROVED`, `CHANGES_REQUESTED`, `REJECTED`. Product code до `APPROVED`, remediation и решения владельца не начинается.

### Первичные ориентиры

- Django 6.0 Applications: apps являются наборами функций и явно подключаются через application registry/settings/URLconf; initialization не должен зависеть от преждевременных model imports: https://docs.djangoproject.com/en/6.0/ref/applications/
- Django deployment checklist: production settings, secrets, HTTPS, error reporting и `manage.py check --deploy`: https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/
- OWASP ASVS 5.0.0: актуальные verification requirements для validation/business logic, files, authentication, sessions, authorization, configuration, data protection, secure architecture и logging: https://asvs.owasp.org/
- PostgreSQL 18 transaction isolation: явные гарантии/аномалии Read Committed, Repeatable Read и Serializable: https://www.postgresql.org/docs/current/transaction-iso.html

Эти источники не заменяют проектные решения и измерения. Точная версия Django/PostgreSQL и dependencies утверждаются отдельно после review; newer не считается автоматически better.
