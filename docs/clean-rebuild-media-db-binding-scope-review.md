# Independent review: REBUILD-1 media DB binding scope

Дата: 2026-11-17. Review ID: `RB1-MEDIA-DB-BIND-SCOPE-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P1=1, P2=1, P3=0**.

`RB1-MDB-SCOPE-P1-001`: полное исключение `stable_version` может потерять media selected current/previous. Selected version eligible при `ordinary_version|stable_version`; shared eligible только для current shared revision. Nonselected ordinary/stable/shared плюс draft/retained — excluded. Обязательны `unclassified_usage=0` и `eligible + excluded = total`. Новые grants не нужны.

`RB1-MDB-SCOPE-P2-001`: DB Asset/File counts и filesystem301/gallery214 — observed inputs; matched238/gallery214 и conditional candidate-only63 — fail-closed hypothesis до probe. `AssetUsage736` требует принятой ссылки либо expected-маркировки.

Остальное подтверждено: existing grants/8 tables, TLS/RRRO/timeouts/output/cleanup и SHA+bytes+cohort input достаточны; anomaly counters/fail-closed/no retry/no-bloat подходят. Reviewer edits/Docker/DB/runtime/network/media reads0, errors0, cycle0.
