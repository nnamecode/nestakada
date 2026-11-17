# Независимое review чистой пересборки

Дата: 2026-11-16. Проверены `docs/clean-rebuild-architecture.md` и `docs/clean-rebuild-plan.md` против действующих требований и фактической старой системы. Файлы продукта и БД не изменялись.

Вердикт: **CHANGES_REQUESTED — P1=5, P2=8, P3=2**. `REBUILD-Q001/Q002` закрыты до remediation и повторного независимого review.

Общее направление — чистая пересборка, модульный монолит, отказ от старых apps и enterprise-bloat — признано здравым. Текущие документы ещё не являются исполнимым контрактом: ключевые решения оставлены неоднозначными.

## P1 — блокирует реализацию

### CRAR-P1-001. Нет закрытого контракта типов содержимого и отображения

Один `current/previous JSON`, fixed editor и 5–6 families не задают schema/version/validator и точное отображение существующих 20 `Page.Kind`/115 outcomes. Не закрыты actions/reviews, YouTube, home, contacts, gallery query variants, legacy blank/alias и Header/Footer. Произвольный JSON может стать новым generic builder, HTML-shape inference — снова связать данные с представлением.

Remediation: исчерпывающая матрица `exact outcome → owner module → closed schema/version → editor fields → renderer family → media slots`, отдельно redirect/blank/render/query variant. Typed validators для import/write/read/current/previous и точный SiteSettings/Header/Footer authority; HTML-shape inference запрещён.

### CRAR-P1-002. Dependency rule не задаёт реальную DAG и transaction ownership

Диаграмма `config→modules→kernel` не описывает необходимые accounts/pages/media/audit/gallery/requests связи, public APIs/FK/delete lifecycle и владельца общей транзакции. Это допускает новые циклы.

Remediation: exact module dependency DAG, table/FK/delete ownership и owner каждого cross-module use case/transaction. Accounts владеет identity, pages — PageGrant; module-specific ports принадлежат consuming module; запрет nested independent transaction ownership.

### CRAR-P1-003. Current+previous не имеет concurrency/permission semantics

Не определены base version/hash, stale save, два редактора, lost response, author/time и права Undo. Employee global swap может восстановить защищённые поля или отменить чужое изменение. `AGENTS.md`/`pipeline.md` ещё содержат старые Stable/history требования.

Remediation: owner-only full Undo; employee save под lock/CAS применяет только разрешённые поля к актуальному current, stale base конфликтует. Зафиксировать version counter/hash, result after lost response, author/time/audit и atomic current/previous/media usages; синхронизировать authoritative instructions.

### CRAR-P1-004. Manifest/export не гарантирует coherent snapshot и privacy

Не заданы isolation/freeze DB↔media, private DACL/encryption/cleanup/caps, authority conflict и exact predecessor. Password hashes/requests/ledger нельзя смешивать с публичным manifest.

Remediation: public content manifest отдельно от private ephemeral transfer; предпочтительно reset/recovery вместо password hash serialization. Stopped/frozen writers, read-only repeatable DB snapshot, media before/after inventory, bounded schemas/caps, no-log/no-Git storage и guaranteed private artifact cleanup. Ambiguous predecessor/import conflict блокирует перенос.

### CRAR-P1-005. Requests противоречат MVP/legal instructions

DB+Telegram включены, но действующие инструкции оставляют intake до LEGAL gate/default-off и формы вне MVP. Не закреплены consent/retention/view/delete/Telegram policy.

Remediation: отдельное решение владельца об области формы; intake default-off до legal gate. Точные поля, consent evidence, privacy text, retention, employee/owner access, owner-only delete и Telegram policy; синхронизация AGENTS/pipeline.

## P2 — существенно исправить

### CRAR-P2-001. User model не выбран до первой migration

Нужно до REBUILD-2 выбрать minimal custom `User(AbstractUser)` либо обосновать built-in+profile и отделить будущую customer identity.

### CRAR-P2-002. Новая media decode boundary не определена

Нужны fixed raster formats, byte/pixel/decompression caps, EXIF policy, timeout/RSS и выбор bounded process либо обоснованного in-process decoder; staging→DB/file commit→cleanup.

### CRAR-P2-003. Telegram и deletion ledger guarantees неясны

Владелец выбирает at-most-once best-effort либо minimal pending/manual-resend/outbox. Для deletion ledger нужны authority, durability, retention, backup/restore order/reconciliation; tombstones применяются до открытия restored site.

### CRAR-P2-004. Quality attributes не измеримы

Нужна компактная таблица `stimulus → environment → response → measure` для latency/load, concurrent editors, RPO/RTO, upload/request limits и rollback window без выдуманной production capacity.

### CRAR-P2-005. Старый backup/restore не является доказательством новой схемы

Scripts — кандидаты, не готовая гарантия. Нужны новый schema/migration/code manifest, config/secrets inventory, deletion ledger и HTTP smoke.

### CRAR-P2-006. Не включён полный page lifecycle

Добавить ownership/AC для create/move/reorder/publish/hide/change URL/confirmed leaf delete/navigation; delete exact name+PRIMARY+composition, children refusal и atomic routes/current/previous/usages.

### CRAR-P2-007. Оценка преждевременна

33–50 часов считать preliminary/non-commitment. После REBUILD-1 нужен WBS по schemas/families/data cohorts/AC с optimistic/likely/risk range.

### CRAR-P2-008. Обязательный kernel может быть преждевременной абстракцией

Kernel разрешено оставить пустым/не создавать до реально общего pure value. Ports принадлежат consuming module; общий type появляется после доказанного повторного использования.

## P3 — точность документов

### CRAR-P3-001

В fitness checks осталось устаревшее `platform/base-module imports feature modules`; заменить exact dependency matrix.

### CRAR-P3-002

Статус clean rebuild plan должен отражать D-1222/D-1223, а не только D-1221.

## Обязательный порядок remediation

1. Typed content/outcome matrix.
2. Exact dependency/transaction ownership graph.
3. Current+previous concurrency/permissions.
4. Coherent public/private migration contract.
5. Explicit requests/legal scope.
6. Остальные P2/P3 и синхронизация AGENTS/pipeline.
7. Повторное независимое review.

До повторного `APPROVED` запрещены новый product code, migrations, dependency installation, DB/media mutation и local cutover.
