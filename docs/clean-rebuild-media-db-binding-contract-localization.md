# REBUILD-1 media DB binding contract localization

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-DB-BIND-CONTRACT-LOCALIZATION-001`.

## Кандидат

Существующие 23 media contract assertions без изменения значений сгруппированы в пять literal ordered cohorts:

- `COUNTS`: Asset238, AssetFile238, AssetUsage736;
- `BINDING`: DB matched/unmatched, candidate matched/only, gallery matched/missing;
- `USAGE`: unclassified0 и partition delta0;
- `ANOMALY`: восемь descriptor/state/file/consumer/kind/overlap anomalies0;
- `STRUCTURE`: четыре current/newer/page/shared structural guards0.

Перед каждой уже существующей группой устанавливается один allowlisted constant code `DBPRE_FAILED_READ_CONTRACT_<CATEGORY>`. Сравнения, expected values, SQL и success output не меняются. Failure по-прежнему не выводит values/facts/raw error и публикуется только после cleanup.

## Acceptance

- `RB1-MDB-CLOC-AC-001`: категорий ровно5 и все имена literal/allowlisted.
- `RB1-MDB-CLOC-AC-002`: assertions3+6+2+8+4=23, без пропуска/дублирования прежнего contract.
- `RB1-MDB-CLOC-AC-003`: порядок COUNTS→BINDING→USAGE→ANOMALY→STRUCTURE детерминирован.
- `RB1-MDB-CLOC-AC-004`: values/facts/raw error/SQL/path output0; query/grant/schema0.
- `RB1-MDB-CLOC-AC-005`: old DBPRE path и success/failure cleanup unchanged; retry/logger/framework0.
- `RB1-MDB-CLOC-AC-006`: runtime/DB/Docker0; repeat probe требует review и fresh owner gate.
