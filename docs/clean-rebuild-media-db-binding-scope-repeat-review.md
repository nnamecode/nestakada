# REBUILD-1 media DB binding scope repeat review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-DB-BIND-SCOPE-REPEAT-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P1=0, P2=1, P3=0**.

## Закрытые findings

- `RB1-MDB-SCOPE-P1-001` — CLOSED: selected current/previous допускает `ordinary_version|stable_version`; nonselected ordinary/stable, non-current shared, draft и retained явно excluded; partition требует equality с AssetUsage total и unclassified0.
- `RB1-MDB-SCOPE-P2-001` — CLOSED: filesystem evidence отделено от expected DB inputs и непроверенной binding hypothesis; candidate-only63 conditional, actual evidence только после owner-gated probe.

## Новый finding

- `RB1-MDB-SCOPE-R2-P2-001`: scope одновременно объявляет отсутствующего consumer anomaly для любого usage и запрещает OwnerDraft/reserve reads. Consumer existence нельзя и не нужно проверять для count-only `draft`/`retained_html`. Минимальная remediation: ограничить consumer existence check уже разрешёнными `current_page`, ordinary/stable revision и `shared_block`; draft/retained оставить count-only excluded.

## Границы review

No-bloat PASS: exact301 transport, existing eight-table subset, one TLS RRRO connection, timeouts/cap/cleanup и fail-closed/no-retry сохранены. Новых grants, exporter, manifest, temp table, model, service или dependency нет. Reviewer edits, DB, Docker, runtime, network и media hash: 0.

Следующий gate: только однострочная semantic remediation finding `RB1-MDB-SCOPE-R2-P2-001`, static check и independent repeat review. DB probe/Q002/product/live остаются закрыты.
