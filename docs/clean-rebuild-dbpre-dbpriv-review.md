# DBPRE ROLE-stage database privilege review

Дата: 2026-11-17. Review ID: `RB1-DBPRIV-REVIEW-001`.

Вердикт: **APPROVED — P1=0, P2=0, P3=0**.

- Root cause: postgres has PUBLIC TEMPORARY but no effective PUBLIC CONNECT; old unconditional TEMP proof rolled back role creation. template0 has PUBLIC CONNECT but datallowconn=false.
- Create/pre-DROP predicates are symmetric.
- Source requires effective CONNECT and rejects exercisable CREATE/TEMP.
- Any other connectable DB with effective CONNECT is rejected; inaccessible PUBLIC privileges do not false-fail.
- Truth table/parser0/facts29/MAP5/allowlist14/reader1/RRRO1/only-db PASS.
- No-bloat: two local SQL predicates only.

Review read-only: edits0, runtime0, Docker0, DB0, network0, tool errors0, cycle0. Execution requires a fresh owner gate.
