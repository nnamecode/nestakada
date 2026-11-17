# Independent review: DBPRE identity sub-checkpoints

Дата: 2026-11-17. Review ID: `RB1-IDENTITY-SUBCHECK-REVIEW-001`.

## Вердикт

**APPROVED — P1=0, P2=0, P3=0.**

`RB1-ISC-AC01..008` подтверждены. Exact order PASS: IDENTITY marker → name/OID → ALTER NOLOGIN → ROLE_STATE marker → state/validity → SETTINGS marker → settings → SESSIONS → RELATIONS → PRIVILEGES → REVOKE_DROP. Failure самого ALTER остаётся в IDENTITY.

Markers7, literal candidate list7, internal mappings7 и external allowlist7 содержат одинаковое множество. Old IDENTITY_STATE refs0; unknown/no marker уходит в generic `DBPRE_FAILED_CLEANUP_ROLE`, raw captured output не возвращается.

Cleanup сохраняет одну BEGIN/COMMIT transaction. Receipt OID/validity, proofs, bounded session drain, revoke/drop, exact-OID fallback и guards4 не изменены. Epoch-microseconds expression остаётся в create receipt и cleanup proof; receipt variables имеют init+one assignment.

Механика: parser0; AC IDs8; markers7; mappings7; allowlist7; generic default1; cleanup BEGIN1/COMMIT1; fallback1; guards4; facts29/unique29; reader1; RRRO1.

No-bloat PASS: прежний checkpoint разделён на три literal boundary без нового процесса, функции, logger, file, retry, dependency, механизма или слоя.

Review: edits0, runtime0, Docker0, DB0, network0, tool errors0, cycle0. Новый DBPRE требует отдельного owner gate.
