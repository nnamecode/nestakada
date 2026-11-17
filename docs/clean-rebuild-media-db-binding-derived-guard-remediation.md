# REBUILD-1 media DB binding derived-guard remediation

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-DB-BIND-DERIVED-GUARD-REMEDIATION-001`.

Run D-1339 доказал, что derived matched relations могут быть ложными при ненулевых duplicate aggregates и потому не должны блокировать OBSERVED evidence.

Удалены только:

- `DB matched = candidate matched`;
- `gallery matched ≤ candidate matched`.

Сохранены hard fail-closed exhaustive sums:

- DB matched + unmatched = AssetFile238;
- candidate matched + only = 301;
- gallery matched + missing = 214.

Equality/ordering интерпретируются на result review вместе с candidate/db duplicate counts. SQL, internal facts, v3 output18, grants, cleanup, retries и old DBPRE не меняются.

Acceptance:

- `RB1-MDB-DGR-AC-001`: derived guards removed2, stale references0.
- `RB1-MDB-DGR-AC-002`: exhaustive sum guards remain3 exactly.
- `RB1-MDB-DGR-AC-003`: OBSERVED may expose duplicate drift; PASS still requires duplicate0 via status calculation.
- `RB1-MDB-DGR-AC-004`: output/privacy/SQL/grants/cleanup/retry unchanged; no-bloat.
- `RB1-MDB-DGR-AC-005`: runtime/DB/Docker0; execution requires review and fresh owner gate.
