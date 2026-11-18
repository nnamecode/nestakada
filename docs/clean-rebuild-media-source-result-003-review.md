# REBUILD-1 media source runtime result 003 review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-SOURCE-RUN-003-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P1=2, P2=0, P3=0**.

- `RB1-MSRC-RUN003-P1-001`: PowerShell `@($null)` produced count1 for normative Docker `CapAdd:null`, causing deterministic false pre-start rejection.
- `RB1-MSRC-RUN003-P1-002`: pre-start cleanup reused full start-config predicate, stricter than approved exact parsed-ID/name/label/image cleanup identity.

Other nullable arrays are required nonempty and need no normalization. RUN003 cleanup-only PASS proves final clean only; verifier/media0. Privacy/retry0/no-bloat PASS.

D-1381 remediation: explicit true-empty CapAdd normalization; one narrow cleanup identity helper. Full config remains mandatory before/post start. Automatic cleanup requires a valid parsed cid matching the same full ID; invalid cid remains owner cleanup-only. Новый runtime требует fresh gate.
