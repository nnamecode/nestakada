# DBPRE bootstrap invocation review

Дата: 2026-11-17. Review ID: `RB1-BOOTSTRAP-REVIEW-001`.

Вердикт: **APPROVED — P1=0, P2=0, P3=0**.

- One exact arguments array preserves `docker exec -i <container> psql -X -qAt -v ON_ERROR_STOP=1 -U postgres -d <database>`.
- SQL is stdin-only; stderr captured; failure constant-only; OID/cleanup success semantics preserved.
- Reader/TLS/PGPASSFILE unchanged; parser0/facts29/MAP5/RRRO1.
- No-bloat: local argument packaging only.

Reviewer first regex command failed due variable expansion; changed AST/literal retry PASS, cycle0. Review edits0/runtime0/Docker0/DB0/network0. Fresh execution gate required.
