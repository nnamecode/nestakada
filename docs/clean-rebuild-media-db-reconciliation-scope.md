# REBUILD-1 media DB reconciliation scope

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-DB-RECON-SCOPE-001`.

## Цель

Одним будущим read-only aggregate envelope классифицировать две принятые OBSERVED аномалии:

- одна matched DB SHA+bytes pair имеет две AssetFile rows;
- одна unique DB SHA+bytes pair отсутствует в exact301.

Scope не раскрывает и не меняет descriptor/DB rows. Он не решает transfer автоматически и не создаёт exporter/manifest/remediation subsystem.

## Authority и execution boundary

Переиспользуются exact301 authority, existing eight-table media reader profile, one TLS connection и одна `REPEATABLE READ READ ONLY` transaction. Новых tables/grants/roles/dependencies нет. In-memory classification использует уже вычисленные candidate/file/usage CTE.

## Bounded reconciliation envelope

Для `duplicateMatched` разрешены только integer aggregates:

- pairGroups, fileRows, distinctAssets;
- readyRows, legacyRows;
- kind counts: privateSource/main/preview/legacyPublic;
- eligibleUsages, excludedUsages.

Для `unmatchedDb` разрешены те же aggregates. Дополнительно existing ordinary binding aggregates остаются `matched22` и `candidateOnly65`; нового per-file breakdown нет.

Path, key, SHA, byte size отдельного файла, UUID, asset/consumer ID, slot, source URL, provenance, row data, SQL и raw error запрещены. Все category sums проверяются арифметически до output.

## Decision rules после result review

- `unmatchedDb.eligibleUsages > 0`: descriptor нельзя исключать; нужен отдельный owner-gated source-resolution contract без автоматического allowlist growth.
- `unmatchedDb.eligibleUsages = 0`: возможное исключение обсуждается только после counts/kind/legacy review; DB не меняется.
- duplicate pair не копируется физически дважды автоматически; distinct asset/usage semantics сохраняются до target-schema/import decision.
- ordinary candidate-only65 не исключаются из-за отсутствия DB row: они уже приняты filesystem authority. Их будущая привязка определяется approved content/design contract, не legacy AssetUsage.
- любые unexpected group/row/category sums дают constant failure; не расширяют output или grants.

## Acceptance

- `RB1-MDB-RECON-AC-001`: same exact301/eight tables/TLS/RRRO/cleanup; grants0 new.
- `RB1-MDB-RECON-AC-002`: envelope содержит только две одинаковые aggregate sections и existing ordinary22/65.
- `RB1-MDB-RECON-AC-003`: kind sums=fileRows, ready/legacy≤fileRows, usage sums bounded; unexpected cardinality fails closed.
- `RB1-MDB-RECON-AC-004`: path/hash/bytes/ID/slot/source/provenance/row/SQL/raw error output0.
- `RB1-MDB-RECON-AC-005`: eligible unmatched blocks exclusion; no auto allowlist growth/DB mutation.
- `RB1-MDB-RECON-AC-006`: duplicate physical-copy and identity semantics remain undecided until target schema/import review.
- `RB1-MDB-RECON-AC-007`: ordinary65 retained as filesystem-authority candidates; no false deletion due DB absence.
- `RB1-MDB-RECON-AC-008`: no exporter/manifest/temp table/model/service/logger/framework/dependency; no-bloat.

Следующий gate: independent scope review. SQL implementation/runtime требуют subsequent reviewed candidate и fresh owner gate.
