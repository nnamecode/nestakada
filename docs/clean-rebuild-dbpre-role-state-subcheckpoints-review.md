# Independent review: DBPRE role-state sub-checkpoints

Дата: 2026-11-17. Review ID: `RB1-ROLE-STATE-SUBCHECK-REVIEW-001`.

## Вердикт

**APPROVED — P1=0, P2=0, P3=0.**

`RB1-RSS-AC01..008` подтверждены. Exact order PASS: IDENTITY → exact name/OID → ALTER → ROLE_FLAGS → seven safe flags+connlimit → VALID_UNTIL → one exact epoch-microseconds equality → SETTINGS → later checkpoints.

Marker/candidate/mapping/external allowlist sets8 equal. Old ROLE_STATE refs0; unknown/no marker maps to generic cleanup-role code. Previous proof conjunction is preserved and only split diagnostically. Receipt epoch expression remains in create receipt and cleanup equality.

Cleanup stays one BEGIN/COMMIT transaction; fallback, literal revoke/drop and guards4 unchanged. Raw OID/validity/output stay internal. Functions10/bootstrap psql path1; no new process/logger/file/retry/dependency.

Механика: parser0; AC IDs8; markers8; candidate list8; mappings8; allowlist8; safe flags7; connlimit1; validity-in-flags0; exact validity equality1; generic default1; facts29/unique29; reader1; RRRO1.

No-bloat PASS: one checkpoint split into two literal diagnostic boundaries without new mechanism or layer.

Review: edits0, runtime0, Docker0, DB0, network0, tool errors0, cycle0. Новый DBPRE требует отдельного owner gate.
