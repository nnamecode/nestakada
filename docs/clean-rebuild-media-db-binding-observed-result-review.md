# REBUILD-1 media DB binding OBSERVED result review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-DB-BIND-OBSERVED-RESULT-REVIEW-001`.

Вердикт: **APPROVED — P1=0, P2=0, P3=0**, только как OBSERVED evidence.

Принятые факты:

- `RB1-MDB-OBS-DATA-001`: DB `237+1=238`;
- `RB1-MDB-OBS-DATA-002`: candidate `236+65=301`;
- `RB1-MDB-OBS-DATA-003`: gallery `214+0=214`;
- `RB1-MDB-OBS-DATA-004`: одна DB SHA+bytes pair представлена ровно двумя matched DB rows, поэтому DB rows237 против unique candidate pairs236;
- `RB1-MDB-OBS-DATA-005`: одна unique DB pair отсутствует в exact301; 65 candidate pairs отсутствуют в DB;
- matched candidate pairs: gallery214 + ordinary22; candidate-only65 все ordinary;
- remaining anomaly7=0, structure4=0; cleanup containers0/host-secret0.

Envelope bounded: paths/hashes/UUID/SQL/row values0. Exit0 означает доставку OBSERVED evidence, не successful binding/transfer acceptance.

До baseline acceptance требуется отдельный safe reconciliation duplicate matched DB pair и unmatched DB descriptor, затем owner decision по ordinary65. Allowlist auto-growth, DB fix, exporter/importer/Q002/target/transfer закрыты.
