# REBUILD-1 media DB binding evidence envelope amendment

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-DB-BIND-EVIDENCE-ENVELOPE-001`.

## Причина

Run D-1334 доказал, что expected hypothesis DB matched238/unmatched0 неверна. Продолжать дробить failure codes по одному aggregate отклонено как bloat. Фактическая binding matrix должна стать evidence, а не заранее заданным условием совпадения.

## Контракт v2

`rb1-media-db-bind-v2` принимает PASS только если:

- source counts остаются Asset238/AssetFile238/AssetUsage736;
- usage unclassified0 и partition delta0;
- восемь anomaly facts0;
- четыре structural facts0;
- binding arithmetic целостна: DB pair sum=AssetFile, candidate pair sum301, gallery pair sum214, DB matched=candidate matched, gallery matched≤candidate matched.

Expected binding values удалены из acceptance. Успешный output содержит только contract/status/source/elapsed и шесть integers:

- `dbMatched`, `dbUnmatched`;
- `candidateMatched`, `candidateOnly`;
- `galleryMatched`, `galleryMissing`.

Остальные внутренние 34 facts, hashes, paths, IDs, rows, SQL и raw errors не выводятся. Старый DBPRE success envelope остаётся прежним. Три временных pair-localization codes удалены; generic binding invariant code остаётся fail-closed.

## Acceptance

- `RB1-MDB-EV-AC-001`: v2 output имеет ровно six binding integers и no per-row/private values.
- `RB1-MDB-EV-AC-002`: counts/usage/anomaly/structure assertions остаются обязательными до PASS.
- `RB1-MDB-EV-AC-003`: five arithmetic invariants блокируют несогласованный envelope.
- `RB1-MDB-EV-AC-004`: expected binding hypothesis не используется как PASS predicate и заменяется фактическим evidence.
- `RB1-MDB-EV-AC-005`: old DBPRE contract/output unchanged; grants/SQL/cleanup/retry unchanged.
- `RB1-MDB-EV-AC-006`: temporary pair codes removed; no logger/exporter/manifest/framework/dependency.
- `RB1-MDB-EV-AC-007`: runtime/DB/Docker0; execution requires independent review and fresh owner gate.
