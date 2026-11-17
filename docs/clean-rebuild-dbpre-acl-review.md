# DBPRE ACL root-cause review

Дата: 2026-11-17. Review ID: `RB1-ACL-REVIEW-001`.

Вердикт: **APPROVED — P1=0, P2=0, P3=0**.

- Root cause: Access-only security descriptor не загружал Owner; `GetOwner()` возвращал null и корректный ACL всегда отклонялся на PRECHECK.
- Fix: existing `GetAccessControl` запрашивает exact sections `Access, Owner`.
- Контракт не ослаблен: protected DACL; owner=current SID; exactly two explicit Allow FullControl CI+OI/PropagationNone ACE; only current SID + LocalSystem; duplicates/broad/inherited denied.
- Isolated exact AST function: PASS; owner loaded; protected true; explicit rules2.
- Другие runner invariants: parser0, facts29, MAP5, allowlist14, reader1, RRRO1, parameter blocks0, only-db/down — unchanged.
- No-bloat: одна секция security descriptor; functions/logs/launcher/framework/state-machine additions0.

Review read-only: edits0, runtime0, Docker0, DB0, network0, tool errors0, cycle0. Execution требует нового отдельного owner gate.
