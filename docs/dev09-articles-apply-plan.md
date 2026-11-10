# DEV-09C: атомарное применение первого пакета в изолированной БД

Дата: 2026-11-09. Статус: план до кода, требуется независимое ревью.

## Цель и граница

Реализовать один внутренний test-only service, который применяет только проверенный DEV-09B package `app/content/dev09b_articles_slice.json` в PostgreSQL test database:

- `MAP-001` `/`;
- `MAP-006` `/articles/`;
- `MAP-031` `/articles/zamena-masla-v-dvigatele`.

Все три Page создаются скрытыми в одной транзакции. Production, постоянная локальная БД, публикация, HTTP/UI/API, произвольный package path, общий importer/ETL, очередь, rollback-платформа и новые таблицы не входят.

## Запуск и блокировка окружения

- Новый `content.dev09_migration_apply.apply_articles_slice()` не принимает пути или данные от вызывающего кода.
- Доступ разрешён только когда `settings.ENVIRONMENT == "test"`, `settings.DEV09_MIGRATION_APPLY_ENABLED is True`, PostgreSQL settings target exact `estakada_foundation_unit` / `app_migrator`; иначе до чтения package и до DB query/mutation — `MIGRATION_APPLY_DISABLED`. После package validation первым SQL внутри transaction проверяется actual `SELECT current_database(), current_user = ('estakada_foundation_unit','app_migrator')`; несовпадение закрывает transaction до advisory/row locks и mutation.
- В base setting флаг всегда `False`; `local_http` и environment variables не могут его включить. Только focused tests временно задают `override_settings(DEV09_MIGRATION_APPLY_ENABLED=True)` после того, как Django test runner переключил connection на test database. Никакого автоматического или операторского запуска нет.
- В DEV-09C service исполняется только focused tests в Django test database. Операторский запуск против постоянной локальной БД требует отдельного следующего решения после code review.

## Package boundary

- Путь фиксирован рядом с модулем. Перед чтением: lexical expected path, `os.open(..., O_RDONLY|O_NOFOLLOW)`, `fstat` regular-file, bounded size `1..65536`, realpath exact expected.
- Exact reviewed package SHA-256: `6a899d6f4b4c1b89cb8a146012f0a8fffdd1a4682d85e08708f4c9fa188842a7`. Это внешний anchor writer-а, а не self-hash JSON.
- `.gitattributes` фиксирует exact package как `text eol=lf`; attribute и отсутствие CR проверяются вместе с SHA, чтобы обычный checkout при `core.autocrlf=true` не менял anchor.
- UTF-8 strict; duplicate JSON keys запрещены; closed top/page/source keys, exact schema/policy/input SHA, exact three page IDs/order/URLs/kinds/parents/positions/states и `is_published=false`.
- Любое расхождение закрывает весь вызов до транзакции. Writer не перечитывает HTML/MAP/RTE и не становится вторым crawler: их целостность уже закреплена DEV-09A/B и package SHA.

## DB transaction

В одном `transaction.atomic()`:

1. После actual DB/role identity check в порядке проекта берутся existing content advisory lock, затем auth advisory lock.
2. Требуется ровно активный owner profile `nesadmin`; пароль/сессия не нужны и новый пользователь не создаётся.
3. Перед записью пакет должен быть либо полностью отсутствующим, либо полностью существующим exact aggregate. Смешанное состояние `1/2 of 3` закрывается; partial continuation не создаётся.
4. При отсутствии до первой INSERT проверяются: каждый fixed Page UUID отсутствует одновременно в Page PK, Route PK и global IdentityReservation; target URL и `(parent, position)` свободны; нужные родители входят в пакет; для каждого target Page object_ref отсутствует orphan `MIGRATION_PAGE_IMPORTED` event.
5. Создаются exact Page, immutable legacy PRIMARY Route, initial PageRevision, PageContentState, OwnerDraft, VersionBasePin, RevisionMetadata и один bounded AuditEvent на Page: `category=PAGES_LINKS`, `code=MIGRATION_PAGE_IMPORTED`, `level=INFO`, `source=APPLICATION`, `result=SUCCESS`, `actor_id=nesadmin.pk`, `object_kind=page`, `object_ref=PageUUID`, `request_id/ip_address=null`, `occurrence_count=1`, `count_is_lower_bound=false`.
6. Главная/каталог получают пустой safe body. Для статьи каждый package paragraph экранируется `html.escape(..., quote=True)` и оборачивается только в `<p>...</p>`; исходный HTML не используется. Layout берётся из существующего `initial_snapshot`.
7. Любая ошибка package/owner/constraint/version/audit откатывает все три aggregate и события.

Отдельный OperationReceipt/ledger не создаётся. Идемпотентность определяется фиксированными Page UUID и exact aggregate replay. Для каждой Page повтор требует exact Page и ровно один legacy PRIMARY Route; ровно один initial revision/current state/owner draft/base pin/blank metadata; ровно две IdentityReservation с correct `pagerevision`/`ownerdraft` IDs и kinds; ровно один audit event с exact category/code/level/source/result/owner/object; ноль extra route/revision/state/draft/pin/metadata/protection/grant/stage/receipt/media-usage/migration-event rows для aggregate. Любое отличие закрывается `MIGRATION_EXISTING_CONFLICT`, ничего не пишет.

## Приёмочные сценарии

- `MIGW-001`: disabled flag, non-test environment либо settings target не exact `estakada_foundation_unit/app_migrator` отказывает до package read и DB query/mutation; actual DB/role mismatch отказывает первым SQL внутри transaction до locks/mutation; local_http/env не могут включить writer.
- `MIGW-002`: package LF attribute/absence of CR/path/type/size/realpath/SHA/UTF-8/duplicate-key/schema/exact-value corruption отказывает до DB transaction; byte SHA подтверждается после checkout policy.
- `MIGW-003`: без единственного active `nesadmin` owner вызов атомарно отказывает и никого не создаёт.
- `MIGW-004`: fresh apply создаёт exact hidden tree positions `0/4/0`, три immutable legacy PRIMARY routes и не добавляет публичных страниц.
- `MIGW-005`: каждый Page получает ровно initial revision sequence1, current state sequence1, matching owner draft/base pin/blank metadata, correct revision/draft IdentityReservation и один audit tuple `PAGES_LINKS/MIGRATION_PAGE_IMPORTED/INFO/APPLICATION/SUCCESS`, owner/page UUID, null request/IP, occurrence1/non-lower-bound; лишние связанные route/version/protection/grant/stage/receipt/usage/event строки отсутствуют.
- `MIGW-006`: deferred pages имеют empty main text; MAP-031 содержит exact три escaped `<p>` без script/template/arbitrary HTML и без media/price.
- `MIGW-007`: exact full replay возвращает `replayed=true`, не меняет ни одной строки, timestamp, sequence или audit count.
- `MIGW-008`: partial existing set, Page UUID collision в Page/Route/IdentityReservation, orphan migration event, URL/position conflict либо повреждение/лишняя связанная строка любого существующего aggregate закрывает вызов без mutation.
- `MIGW-009`: синтетическая ошибка на второй Page/version/audit откатывает первую Page и весь пакет.
- `MIGW-010`: два конкурентных вызова сериализуются existing locks: один создаёт, второй exact-replay; итог один aggregate/event на Page.
- `MIGW-011`: focused tests проверяют фактическую PostgreSQL test DB; Django check/migrations/no-changes и основной guard regression проходят после реализации.
- `MIGW-012`: service не имеет HTTP/management endpoint, произвольного path/data, network/subprocess/media write/delete/publish; persistent local/production apply остаётся отдельным решением.

## Не входит

Импорт остальных 112 MAP, заполнение deferred home/catalog, media, SEO, publication, employee grants, Stable/manual versions, универсальные recovery/rollback/continuation workflows и обход READY-04/MIG-01/ANA-Q041.
