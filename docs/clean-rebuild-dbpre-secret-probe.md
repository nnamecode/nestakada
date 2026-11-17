# Exact-byte secret transport runtime probe

Дата: 2026-11-17. Evidence ID: `RB1-SECRET-PROBE-001`.

Scope: existing exact dev PostgreSQL service only; approved `Invoke-DockerInputExact` extracted from current runner AST; random lowercase hex96 payload held in memory only. SQL, role creation, subject tables and reader were not used.

Result:

- parser/function extraction PASS;
- exact stdin write PASS;
- container metadata exact `uid=999`, `gid=999`, `mode=600`, `size=96`;
- read as PostgreSQL UID999 PASS;
- container secret removed;
- compose teardown PASS;
- payload variable cleared.

No secret value, raw Docker stderr, SQL, error path, user row or subject aggregate was emitted. Next: independent read-only result review. Full DBPRE requires a fresh owner gate after review.
