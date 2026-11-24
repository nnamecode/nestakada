# R7-LOCAL-001 — одноразовое локальное доказательство backup/restore

Статус: `R7-LOCAL-001` успешно завершён 23 ноября 2026 года. Generation-v5 tests внутри pinned image прошли `12/12 OK`; bounded confirmation run `31e34d12158246dc82ba3c9d4122c031` завершился `R7_LOCAL_RESTORE_PASS`. Empty disposable restore доказал semantic release/schema, raw table counts/content, READY-media exact265/48667032 bytes, audit 16-case behavior до reconciliation, sessions0, staff generation bump1, exact115, private denial, internal network и source post-audit. Cleanup wrapper и отдельный post-audit: `containers=0 database=0 staging=0 lock=0 bitmap=exact`; source DB работает, preview app/ingress остановлены. Independent source architecture/data repeat review до runtime и финальный evidence/release-gate review после runtime: оба `APPROVED P0=0/P1=0/P2=0`. `R7L-AC-001..007 PASS`; пакет закрыт. Этот результат закрывает только локальную часть `BACKUP-AC-001/005/006/008/009`; он не является production backup и не закрывает external copy, catalog/retention, scheduler, deletion ledger, intake reconciliation, local cutover или `REBUILD-Q003`. External copy, promotion, cutover и live не выполнялись.

## Результат и граница

Один project-owned wrapper держит atomic exclusive host lock до конца `finally` и на время capture останавливает exact текущие preview app/ingress, фиксируя их прежний bitmap. До, между и после capture stages closed PostgreSQL client inventory source DB обязан быть zero; source snapshots содержат per-table row-content digests сверх counts. Source PostgreSQL остаётся running и читается только через custom-format `pg_dump`; source media монтируется read-only, проверяется до archive и повторно против неизменившегося DB inventory. Candidate содержит dump, canonical release manifest, safe DB counts/content/schema digests, READY-media inventory, deterministic media archive и SHA-256 каждого artifact. Secrets, environment values, row payloads, абсолютные host paths и media bytes не попадают в Git/отчёт.

Restore создаёт только уникальную disposable DB `estakada_r7_<32hex>` и уникальный staging под `work/r7-local-001/staging/<uuid>`. До restore generation manifest повторно читается как closed exact name/size/SHA list. Dump восстанавливается без migrations, media archive распаковывается path-safe в новый root. До HTTP проверяются immutable app image digest, exact installed locked dependency versions, source/package digest, migration file/applied sets, PostgreSQL schema fingerprint, raw table counts/content digests и READY-media size/SHA. Затем только в restored DB удаляются sessions и для каждого staff доказывается увеличение generation ровно на один. Exact115 GET/HEAD и anonymous private denial выполняются без host port только в Docker network, заранее проверенной как `Internal=true`; HTTP helper сам не заявляет network telemetry.

Обязательный `finally` удаляет exact временный app container, exact disposable DB и staging только после проверки canonical workspace ancestry и всех descendant reparse/junction, затем возвращает оба preview app/ingress к exact pre-run bitmap, включая originally stopped. Только после этого он снимает host lock и допускает success receipt. Повторный source capture обязан совпасть с исходными release/capture/media digests; final physical media check использует исходный immutable inventory после доказанного равенства final DB inventory. Любая неоднозначность, неизвестный resource, symlink/reparse point, drift либо cleanup mismatch даёт failure; promotion, current pointer и retry-in-place отсутствуют.

## Результат generation-v2 confirmation

- `R7L-RUN-003-PREFLIGHT`: остановка до product execution, причина — existing source PostgreSQL был stopped; post-audit `containers=0 database=0 staging=0 lock=0`, media не читались.
- `R7L-RUN-003`: после отдельного разрешения владельца existing source PostgreSQL запущен; source-test `3/3 OK`; capture/dump/media/empty restore дошли до `restore-verify-database` и остановились на `django_content_type.app_label.attnum`.
- Exact failure: `R7_RESTORE_SCHEMA_COLUMNS_DJANGO_CONTENT_TYPE_APP_LABEL_ATTNUM_MISMATCH`. Raw catalog values, row payloads, secrets и host paths в отчёт не выводились.
- Exact cleanup: `containers=0 database=0 staging=0 bitmap=exact`; reconciliation, 16-case audit behavior и HTTP/exact115 не выполнялись, product result остаётся `UNDETERMINED`.
- Source-only вывод подтверждён remediation и independent review: абсолютный `attnum` не является restore-semantic invariant, потому что dropped-column slots сохраняются в source catalog, а логически эквивалентный empty restore не обязан воспроизводить прежние физические номера.

## Generation-v3 source remediation

- Сравниваемое поле `attnum` заменено на `ordinal` среди `NOT a.attisdropped` колонок; физический `attnum` остаётся только безопасным внутренним ключом PostgreSQL для `pg_attrdef`, `conkey` и детерминированной сортировки.
- Release schema поднята до `estakada.r7-local-generation-v3`; incomplete/extra field map продолжает fail closed, exact diagnostic может вернуть только whitelist-токен `ORDINAL`, но не catalog value.
- Tests покрывают identical pass, semantic ordinal contract, exact ordinal mismatch, exact другого field mismatch и incomplete shape. До изменения тестов прежняя generation-v2 форма прошла `3/3 OK`; generation-v3 tests пока не исполнены из-за отсутствия host Python и закрытого Docker.
- Independent architecture/data review: `APPROVED P0=0/P1=0/P2=0`; constraints, indexes, defaults и безопасная diagnostic boundary не ослаблены.
- Bounded generation-v3 confirmation был отдельно разрешён владельцем; его результат зафиксирован ниже. External copy, promotion, cutover и live не входили.

## Результат generation-v3 confirmation

- Preflight и generation-v3 diagnostic tests: `5/5 OK`; existing source PostgreSQL running, preview app/ingress stopped, temp resources zero.
- Capture/dump/media/empty restore прошли column fingerprint и дошли до constraint object gate.
- Exact failure: `R7_RESTORE_SCHEMA_CONSTRAINTS_MEDIA_ASSET_MEDIA_ASSET_PURPOSE_CLOSED_MISMATCH`. Constraint definition и catalog values в отчёт не выводились.
- Exact cleanup и post-audit: `containers=0 database=0 staging=0 lock=0 bitmap=exact`; source DB running, preview app/ingress stopped.
- Reconciliation, 16-case audit behavior и HTTP/exact115 не выполнялись. Повтор runtime без нового source evidence запрещён.
- Этот source-only proposal был реализован как generation-v4 и независимо одобрен; результат отдельного runtime confirmation зафиксирован ниже.

## Generation-v4 source remediation

- Constraint projection хранит отдельные SHA для `type/definition/deferrable/deferred/validated/noinherit/key_columns`; raw SQL definition и catalog values остаются только внутри capture manifest и никогда не попадают в diagnostic code/output.
- `constraintFieldComponents` имеет closed exact shape: те же tables и constraint objects, что `objectComponents`, и ровно семь whitelist fields с валидными SHA-256. Missing/extra/invalid shape fail closed.
- Exact mismatch может назвать безопасный field token, например `..._DEFINITION_MISMATCH`, но не сравниваемое значение.
- `audit_actor_shape` продолжает использовать `R7_AUDIT_ACTOR_SHAPE_BEHAVIOR_V1`; полная 16-case rollback-only behavior матрица остаётся обязательной до reconciliation.
- Tests расширены до восьми: прежние column/ordinal проверки, closed constraint contract, exact constraint definition mismatch и incomplete constraint shape. На source-only стадии они не исполнялись; перед отдельно разрешённым generation-v4 confirmation прошли `8/8 OK`.
- Independent architecture/data review: `APPROVED P0=0/P1=0/P2=0`; constraints/indexes/defaults и semantic ordinal не ослаблены.
- Bounded generation-v4 confirmation был отдельно разрешён владельцем; его результат зафиксирован ниже. External copy, promotion, cutover и live не входили.

## Результат generation-v4 confirmation

- Preflight и generation-v4 diagnostic tests: `8/8 OK`; temp resources zero, source PostgreSQL running, preview app/ingress stopped.
- Capture/dump/media/empty restore прошли column gate и локализовали constraint mismatch до exact field `definition`.
- Exact failure: `R7_RESTORE_SCHEMA_CONSTRAINTS_MEDIA_ASSET_MEDIA_ASSET_PURPOSE_CLOSED_DEFINITION_MISMATCH`. Definition value, row payloads, secrets и host paths не выводились.
- Exact cleanup/post-audit: `containers=0 database=0 staging=0 lock=0 bitmap=exact`; source DB running, preview app/ingress stopped.
- Reconciliation, 16-case audit behavior и HTTP/exact115 не выполнялись. Повтор runtime без нового source evidence запрещён.
- Evidence: PostgreSQL `pg_get_constraintdef` возвращает decompiled reconstruction, не original command; dump/reparse может переписать implicit casts в explicit без изменения смысла. Поэтому textual/decompiled definition equality не является устойчивым restore invariant.
- Этот source-only proposal реализован как generation-v5 с уточнением independent review: definition redaction разрешена только для CHECK; non-CHECK definitions остаются exact restore authority. Итог remediation зафиксирован ниже.

## Generation-v5 source remediation

- Raw `source_projection` и `sourceCaptureSha256` включают original constraint definitions. Wrapper сравнивает capture/final `release-manifest.json` exact, поэтому source drift остаётся fail-closed.
- Restore-semantic constraint row заменяет definition sentinel только для CHECK (`contype='c'`), где PostgreSQL decompiled rendering нестабилен. Foreign key и остальные non-CHECK definitions сохраняются без redaction; их target/actions и другие semantics остаются в общих, per-table, per-object и field hashes.
- `schemaFingerprint.sha256/components/tableComponents/objectComponents` используют semantic projection; `facts.releaseSha256` нормализует только `sourceCaptureSha256`. Любое другое stable schema/release изменение меняет hash и отклоняется.
- `verify_raw_snapshot` продолжает только после успешного semantic schema comparison; остальные release/facts/table counts/table content/media gates не изменены.
- Tests расширены до 12 и покрывают CHECK-vs-FK redaction, raw-only schema acceptance, полный snapshot path, прямую semantic release-hash нормализацию, stable schema/release hash rejection, exact non-CHECK definition mismatch и incomplete closed shapes.
- Первое independent review: `CHANGES_REQUIRED P0=0/P1=1/P2=1`; оба замечания исправлены. Repeat independent architecture/data review: `APPROVED P0=0/P1=0/P2=0`.
- На source-only стадии generation-v5 tests не исполнялись; перед отдельно разрешённым bounded confirmation они прошли `12/12 OK`. Результат runtime зафиксирован ниже; external copy, promotion, cutover и live не входили.

## Результат generation-v5 confirmation

- Preflight и source diagnostics: `12/12 OK`; temp containers/database/staging/lock zero, source PostgreSQL running, preview app/ingress stopped.
- Safe receipt: schema `estakada.r7-local-result-v1`, run `31e34d12158246dc82ba3c9d4122c031`; generation/release/raw-count/raw-content/media inventory SHA fields присутствуют и имеют closed SHA-256 форму.
- Empty restore: release/schema/counts/content/media identity PASS; READY-media `265` файлов / `48667032` байт.
- Restore-only reconciliation: sessions deleted `0`, staff generations bumped exactly `1`.
- Audit structural identity и 16-case rollback-only behavior gate PASS до reconciliation.
- HTTP: exact115 PASS, anonymous private denial PASS, Docker network internal PASS; host port/browser не использовались.
- Source post-audit PASS; external copy, promotion, current pointer, local cutover и live отсутствовали.
- Wrapper cleanup и отдельный post-audit: `containers=0 database=0 staging=0 lock=0 bitmap=exact`; source DB running, preview app/ingress stopped.
- `R7L-AC-001..007`: PASS. Product result для этого локального restore package — `PASS`; production backup/cutover readiness не заявляется.
- Финальный независимый evidence/release-gate review: `APPROVED P0=0/P1=0/P2=0`; документированный PASS не превышает receipt и исходный код, exclusions сохранены.

## Acceptance

- `R7L-AC-001`: release manifest связывает actual `src/`, R7 tools/plan, dependency lock+exact installed locked versions, immutable app image, Python/Django/PostgreSQL compatibility, migration files/applied set, общий, per-table и per-object schema hashes для columns/constraints/indexes и closed config-name inventory без values.
- `R7L-AC-002`: exclusive coordinator lock и app/ingress write paths закрыты перед capture; client inventory zero, before/after source release, DB row digests и READY-media inventory совпадают.
- `R7L-AC-003`: dump/media archive и manifests имеют checked size/SHA; incomplete candidate не используется.
- `R7L-AC-004`: empty disposable restore reproduces raw migrations/table counts/content digests/schema and READY-media bytes before reconciliation; exact `audit_actor_shape` дополнительно доказывается structural identity и полной матрицей 4 actor kinds × UUID present/absent × role present/absent, где каждая вставка rollback-only, а invalid обязан назвать exact constraint.
- `R7L-AC-005`: restored sessions become zero and every staff generation advances exactly once; source counts/content digests remain unchanged.
- `R7L-AC-006`: restored app passes exact115 GET/HEAD, redirect/canonical/cache/cookie checks and anonymous `/manage/pages/` denial; no host port/browser, inspected Docker network has `Internal=true`.
- `R7L-AC-007`: success/failure cleanup leaves temp containers0, disposable DB0, staging0, releases exact lock and restores exact preview bitmap.

Runtime requires a separate owner gate explicitly allowing Docker/PostgreSQL, bounded source-media read and exact staging/disposable-DB cleanup. Independent review must close data/destructive/containment findings before that gate.
