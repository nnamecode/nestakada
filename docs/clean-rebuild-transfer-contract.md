# Контракт coherent переноса DB и media

Дата: 2026-11-17. Статус: **D-1284 full DBPRE FAIL-CLOSED at cleanup; no facts/PASS, exact final container/secret/role cleanup proved; runtime closed pending cleanup diagnosis**.

Документ разделяет публичный manifest и приватный одноразовый transfer. Он не разрешает запуск exporter/importer, создание новой БД, запись media или cutover.

## 1. Две разные операции

1. **REBUILD-1 baseline:** read-only доказательство authority, counts/digests, current+previous и media inventory. Target DB отсутствует; никаких данных не импортируется.
2. **REBUILD-3 migration freeze:** повтор baseline на остановленном source, затем один run с новым UUID, отдельной пустой target DB и отдельным media root читает public+разрешённые private rows из одной source snapshot transaction.

Baseline не считается migration snapshot. Любое изменение source после baseline требует нового freeze и нового набора digests перед import.

## 2. Freeze и coherent snapshot

Перед snapshot должны быть остановлены ingress, old app processes, workers, management commands и любые editor/import/cleanup jobs, способные писать source DB, request ledger или media. Exporter использует отдельную fresh-only read-only DB identity и одну PostgreSQL `REPEATABLE READ READ ONLY` transaction/connection. Reader must-not-preexist, имеет zero membership/ownership, exact effective CONNECT/USAGE/literal SELECT grants, connection limit1 и bounded validity; success/failure закрывает connection, ставит exact OID `NOLOGIN`, отзывает literal grants, conditionally drops только unchanged role и удаляет exact secret. Ambiguity оставляет role fail-closed, не переиспользует и не удаляет её догадкой. Эта transaction остаётся открытой до завершения чтения public manifest **и** private DB→DB stream текущего run; source runtime не запускается как библиотека, exporter читает таблицы явными queries.

Последовательность фиксирована:

1. доказать writer inventory = 0 и read-only DB identity;
2. построить `media_before`: только нормализованные relative paths, type, byte size и SHA-256; symlink/reparse/special files запрещены;
3. открыть одну DB snapshot transaction, прочитать public/private counts и public rows, зафиксировать snapshot ID;
4. построить `media_after` тем же scanner;
5. потребовать exact equality `media_before == media_after`;
6. записать canonical public manifest и aggregate receipt через atomic rename, не закрывая source transaction;
7. для REBUILD-1 без target завершить transaction; для migration freeze передать ту же connection/snapshot one-shot coordinator и закрыть только после private stream/target commit из §6–7.

Writer ambiguity, DB snapshot error, media drift, unreadable file, path escape, duplicate normalized path или count/cap mismatch отменяет snapshot целиком. Partial artifact не становится authoritative.

## 3. Public content manifest

Public manifest имеет собственную versioned closed schema и содержит только:

- schema/version, source snapshot ID и canonical digest;
- 115 exact route outcomes;
- Page identity/tree/order/publication;
- typed current и exact previous либо null;
- публичные SiteSettings/SEO/navigation facts;
- Asset/File/Usage metadata, relative paths, sizes и SHA-256;
- gallery albums/order и exact214 original inventory;
- section counts, byte totals и per-section digests.

Он не содержит users, password hashes, PageGrant, sessions, requests/ПД, deletion ledger, audit/log rows, secrets, absolute paths или file bytes. Сам data artifact остаётся в ignored local staging и не попадает в Git автоматически; в Git допустимы schema, aggregate counts/digests и synthetic fixtures без закрытых данных.

## 4. Exact current и previous

Для каждой Page:

- current authority — единственная строка `PageContentState.current_revision` той же Page;
- current revision должна иметь kind `initial|automatic`, valid schema/hash и не иметь более новой `initial|automatic` sequence;
- previous — строка той же Page с максимальной `sequence < current.sequence` среди kind `initial|automatic`;
- manual revisions, Stable protection, drafts, restore stages и metadata не участвуют;
- previous отсутствует только если меньшей current-capable revision нет.

Unique `(page, sequence)`, Page FK, payload hash, schema и media usages проверяются. Missing/mismatched current, более новая non-current automatic, duplicate/impossible sequence, invalid payload/hash или неоднозначный predecessor блокирует конкретную Page и весь import. Timestamp и UUID ordering не используются как догадка.

## 5. Bounded schema и caps

REBUILD-1 создаёт reviewed `transfer-limits` только из frozen facts: exact count и maximum canonical bytes для каждой manifest section; exact total media file count/bytes; maximum single file size; exact214 count/bytes; maximum field/list sizes уже закрытых content schemas. Migration freeze обязан совпасть с этими values либо baseline пересогласуется. Автоматического headroom, truncation, sampling или «best effort» нет.

Exporter и importer читают bounded batches, считают canonical digests и отказываются до target mutation при превышении любого cap. Actual numeric values появляются только из REBUILD-1 evidence и не выдумываются архитектурой.

## 6. Private transfer без файла и без смены snapshot

Private artifact не создаётся. В migration run public import и private stream выполняются внутри одной target DB transaction. Private rows потоково читаются через ту же всё ещё открытую source connection/transaction и exact snapshot ID, из которой создан public manifest:

- source staff numeric key только как private in-memory join key; username/role/active state и PageGrant переносятся в fresh target staff UUID;
- только те active ServiceRequest rows, перенос которых отдельно разрешён; deletion ledger не идёт этим потоком и применяется из своей latest independent authority до target HTTP.

Source `auth_user.id` является numeric, а clean target User имеет UUID PK. В каждом disposable run importer создаёт fresh target UUID для каждой source staff row и держит exact source-key→target-UUID map только в process memory до commit/rollback; эта же map связывает PageGrant и разрешённую current/previous provenance. Missing, duplicate или unmapped key блокирует run. Map/source key не входят в public manifest, file, target mapping table, argv/stdout/stderr/audit/log; failed run теряет map вместе с disposable target. Deterministic UUID scheme, identity service и mapping model не создаются.

Password hashes, sessions и recovery tokens не сериализуются и не копируются. Target staff создаются с unusable password; owner проходит штатный local recovery, сотрудники — штатный reset/reprovision по отдельной процедуре. Private values не попадают в argv/stdout/stderr/audit/technical logs. Bounded batches не закрывают/заменяют source snapshot и не commit-ят target частями. После stream latest verified request ledger применяется внутри той же target transaction; missing/stale/corrupt ledger откатывает target DB.

Если прямой DB→DB stream технически невозможен, работа останавливается: encrypted private file/key/DACL/cleanup требуют нового отдельного owner решения. Не допускается fallback в JSON/CSV/plain temporary file.

## 7. Disposable run target, seal и cleanup

Каждая попытка генерирует новый UUID `run_id` и до чтения private values создаёт только:

- новую PostgreSQL database `estakada_rebuild_<uuid>` с exact expected owner и без connections;
- новый contained media directory `<approved-rebuild-root>/<uuid>/media` с owner-only DACL;
- безопасный run manifest без ПД: source snapshot/manifest digests, target names, phase `CREATED|SEALED|FAILED` и counts/digests.

Reuse run ID, existing/non-empty DB, existing/non-empty directory, symlink/reparse/path escape или target, на который указывает current runtime, блокирует run. Имена не задаются пользователем. Target никогда не обслуживает HTTP до separate cutover.

Сначала schema/caps/digests и source files проверяются read-only. Затем одна target DB transaction импортирует public rows, stream private rows из still-open source snapshot и применяет deletion ledger. Параллельно files копируются только в run media root с повторным SHA. Target transaction commit разрешён лишь после exact media inventory, DB constraints/current+previous/usages/counts/digests и ledger reconciliation; иначе rollback.

PostgreSQL и filesystem не объявляются общей ACID transaction. Безопасность достигается isolation disposable pair: после DB commit run остаётся недоступным и unsealed, пока DB/media read-back не совпадут с manifest. Только затем flushed write-once result переводит manifest в `SEALED`. Unknown/crash между commit и seal означает unsealed candidate: он никогда не выбирается и не продолжается, а целиком удаляется как failed run после cleanup preflight. Следующий attempt всегда получает новый run ID/empty pair.

Failure path сначала закрывает source/target connections и private memory, ставит safe `FAILED` result если это однозначно возможно, затем доказывает: exact generated DB/media names, containment/no-link, expected DB owner, no active connections и отсутствие current/candidate pointer. Только после этого drop/delete затрагивает весь disposable pair; ambiguity сохраняет isolated target и требует owner inspection, но всё равно не разрешает promotion/retry-in-place. Old DB/media/runtime, public manifest authority и другой run не изменяются.

Success path закрывает source transaction только после target DB commit и source/media final digest equality. Migration freeze writers остаются остановленными до local cutover decision. Если owner вместо cutover снова открывает old writers, sealed run немедленно считается stale/non-selectable и удаляется/сохраняется только как isolated evidence; новый cutover требует нового freeze/run.

Promotion — отдельное действие `REBUILD-Q003`: оно выбирает только exact `SEALED` DB+media pair с matching manifest/ledger/read-back. Сам transfer не меняет current pointer, Nginx, runtime settings или live target. Logs/result содержат только phase, counts, digests и error code.

## 8. Authority conflicts и acceptance

Source DB — authority фактического current/tree/publication/users/grants. Canonical route map, 12 migration JSON, approved design и media evidence — независимые oracles. Они не переписывают DB молча: любой URL/type/content/media conflict создаёт blocking report и требует решения владельца.

- `TRANSFER-AC-001`: writer inventory0, one read-only DB snapshot remains open through public+private reads, identical media before/after.
- `TRANSFER-AC-002`: public manifest schema rejects private fields and absolute paths.
- `TRANSFER-AC-003`: all Pages have unambiguous current and immediate previous/null by sequence rules.
- `TRANSFER-AC-004`: exact115 outcomes and exact214 originals match independent oracles.
- `TRANSFER-AC-005`: caps/counts/digests reject drift before target mutation.
- `TRANSFER-AC-006`: private staff/active-request values stream from exact public-manifest snapshot into one target transaction without password hashes/files/log output; latest independent request ledger reconciles before commit.
- `TRANSFER-AC-007`: every attempt has new UUID+empty isolated DB/media pair; reuse/non-empty/current target refuses before source private read.
- `TRANSFER-AC-008`: target current/previous/usages and copied file SHA match manifest; old source remains untouched.
- `TRANSFER-AC-009`: failed/unsealed run is never selectable; exact disposable pair cleanup cannot touch source/current/other run, ambiguity remains isolated.
- `TRANSFER-AC-010`: DB transaction commits only after public+private+ledger+media validation; seal requires post-commit DB/media read-back equality.
- `TRANSFER-AC-011`: crash after DB commit/before seal produces no resumable or selectable target; next attempt is a fresh empty pair.
- `TRANSFER-AC-012`: opening old writers invalidates any sealed candidate from that freeze; cutover requires a new coherent run.
- `TRANSFER-AC-013`: transfer never changes current pointer/runtime/Nginx; only separate `REBUILD-Q003` may select exact sealed pair.
- `TRANSFER-AC-014`: before freeze/target creation, aggregate zero-count checks prove selected current/previous authors, staff profile/role and grant user/page fully mappable; every source staff key then maps to exactly one fresh target UUID inside one disposable run, grants/provenance use that same memory-only map, and missing/duplicate/unmapped keys fail without file/table/log leakage.
