# REBUILD-1 media DB binding scope

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-DB-BIND-SCOPE-001`.

## Цель

Связать принятый exact301 filesystem oracle с source DB `Asset/AssetFile/AssetUsage` только агрегатно и read-only. Scope не создаёт exporter, manifest, temp table, новую роль, новую привилегию или product code.

## Authority и транспорт

- filesystem authority остаётся `docs/analytics-media-evidence.csv` SHA-256 `52823a26c535f6bcbb45601fccad630278d59d421ab5f87b25bb1390d28867ca` и принятый `RB1-MEDIA-HASH-001`;
- в SQL через stdin строится только in-memory literal `VALUES(sha256,byte_size,cohort)` exact301; path/source URL/UUID/slot не передаются и не выводятся;
- используется прежняя fresh JIT reader boundary: одна TLS connection, одна `REPEATABLE READ READ ONLY` transaction, прежние timeouts/output cap/cleanup;
- достаточно уже разрешённых таблиц: `media_library_asset`, `assetfile`, `assetusage`, `content_page`, `page_versions_pagecontentstate`, `pagerevision`, `shared_content_sharedblock`, `sharedrevision`. Reader grant не расширяется.

## Transfer-eligible usages

Новый runtime переносит current+previous. Каждая строка `AssetUsage` обязана попасть ровно в одну из двух групп.

Eligible:

1. `current_page` → существующая `content_page`;
2. `ordinary_version` или `stable_version` → selected current или selected previous revision из того же DBPRE snapshot;
3. `shared_block` → current revision существующего shared block.

Excluded:

1. `ordinary_version` или `stable_version` → revision вне selected current/previous;
2. `shared_block` → не-current revision;
3. `draft`;
4. `retained_html`.

Для этой partition достаточно уже разрешённых revision/page/shared tables: чтение `OwnerDraft` или reserve tables не требуется. Consumer existence проверяется только для `current_page`, `ordinary_version|stable_version` и `shared_block`; `draft` и `retained_html` остаются count-only excluded без проверки их consumer. Отсутствующая page/revision/shared consumer, неизвестный kind, пересечение групп или строка вне обеих групп считаются anomaly. Принимаются только `unclassified_usage=0` и `eligible_usage + excluded_usage = AssetUsage total`.

## Наблюдаемые inputs и гипотезы probe

Уже принятые filesystem evidence:

- exact301: 301 файл, 56 134 441 byte, authority digest из раздела выше;
- gallery cohort: 214 файлов, 41 176 391 byte;
- ordinary cohort: 87 файлов, 14 958 050 byte;
- SHA/size mismatch в принятом filesystem oracle: 0.

До фактического owner-gated DB probe следующие числа являются только ожидаемыми входами или проверяемой гипотезой, а не binding evidence:

- expected DB inputs: `Asset=238`, `AssetFile=238`, `AssetUsage=736`;
- expected binding hypothesis: `DB matched=238`, `gallery matched=214`;
- `candidate-only=63` — условная производная `301 - DB matched`, допустимая только после успешной unique SHA+bytes binding и подтверждения `DB matched=238`.

Фактическими DB/binding evidence эти значения становятся только после отдельного разрешённого probe и принятия его bounded результата.

## Fail-closed binding matrix

- probe ожидает Asset238, AssetFile238, AssetUsage736; любое расхождение закрывает run и не считается принятым evidence;
- каждая DB file descriptor имеет known kind, safe `img/` или `private/sources/` key, lowercase SHA-256 и non-negative bytes;
- каждый transfer-eligible asset READY и имеет file; legacy asset/source hash и `legacy-public` descriptor согласованы;
- каждая DB `(sha256,byte_size)` встречается ровно один раз в exact301 input; unmatched/duplicate DB descriptor блокирует run;
- exact214 gallery pairs должны дать 214 DB matches; candidate-only63 допустимо только как условный результат после подтверждённых DB matched238 и unique binding;
- eligible usage consumer существует в своей разрешённой selected cohort; orphan/unknown/ambiguous usage блокирует run;
- excluded usage rows не становятся transfer bindings и не расширяют target scope.

Если фактическая матрица не равна ожидаемой гипотезе `DB matched238 / candidate-only63 / gallery matched214`, run возвращает только constant failure и не расширяет allowlist автоматически.

## Bounded output

Разрешены только contract/status, elapsed и integer aggregates:

- totals Asset/AssetFile/AssetUsage;
- DB matched/unmatched, candidate matched/only, gallery matched/missing;
- eligible usage total и counts `current_page`/`ordinary_version`/`stable_version`/`shared_block`;
- excluded usage total и counts nonselected ordinary/stable, non-current shared, draft и retained;
- partition totals eligible/excluded/unclassified и equality с AssetUsage total;
- zero-anomaly counts descriptor/state/duplicate/orphan/no-file/unknown-kind/overlap/unclassified.

Path, UUID, source URL, slot, provenance, SQL, raw exception и per-row hash не выходят наружу. Missing column/table, count drift, timeout или anomaly дают один bounded constant code; stronger-role retry отсутствует.

## Acceptance

- `RB1-MDB-SCOPE-AC-001`: exact301 authority/digest и values schema закрыты; path/ID/private value transport0.
- `RB1-MDB-SCOPE-AC-002`: reader/tables/privileges/one connection/RRRO/timeouts/cap/cleanup не расширены.
- `RB1-MDB-SCOPE-AC-003`: eligible cohorts ровно current_page + selected current/previous ordinary|stable version + current shared_block.
- `RB1-MDB-SCOPE-AC-004`: excluded cohorts ровно nonselected ordinary|stable + non-current shared + draft + retained; OwnerDraft/reserve tables grant0; eligible+excluded=AssetUsage total и unclassified0.
- `RB1-MDB-SCOPE-AC-005`: 238/238/736 и binding matrix 238/63/214 явно expected до probe; actual evidence возникает только после owner-gated run; all anomaly counts0.
- `RB1-MDB-SCOPE-AC-006`: output только bounded aggregates/constants; paths/UUID/slots/per-row hashes/raw errors0.
- `RB1-MDB-SCOPE-AC-007`: any drift fails closed without allowlist growth, retry, copy/import/target mutation.
- `RB1-MDB-SCOPE-AC-008`: no-bloat — exporter/manifest/temp table/model/service/dependency0.

Следующий gate: independent read-only scope review. После APPROVED нужен отдельный owner gate на один catalog/aggregate binding probe; не на exporter/importer/Q002.
