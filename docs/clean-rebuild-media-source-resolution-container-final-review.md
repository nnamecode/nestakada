# REBUILD-1 ephemeral verifier final amendment review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-SOURCE-CONTAINER-REVIEW-003`.

Вердикт: **CHANGES_REQUESTED — P0=0, P1=0, P2=1**.

`RB1-MSRC-CONT-P1-004` CLOSED: pre-start mismatch, post-start `UNKNOWN_ISOLATED`, forbidden RESOLVED/stopped/final0, bounded cleanup и owner-gated cleanup-only recovery согласованы. Exact cidfile не содержит descriptor и остаётся лёгким cleanup receipt, не tracker.

## `RB1-MSRC-CONT-P2-005` — exact cidfile validation

Нужно одной нормой закрепить:

- exact canonical existing private parent, non-reparse, approved owner-only ACL;
- cidfile absent before create;
- after create regular non-reparse, same parent, exact ACL, bounded size;
- content exactly one full lowercase `[0-9a-f]{64}` ID и ровно одна утверждённая terminal newline form, без extra bytes/lines;
- containment/type/ACL повторяются before read и literal delete;
- validation failure forbids start; created exact-name container becomes cleanup-only case;
- delete only after exact container absence and repeated cidfile validation.

AC001–005/007–008 PASS, AC006 only CHANGES REQUIRED. Privacy/no-bloat PASS, overreach0, missing evidence1. Files edited0, DB/Docker/runtime/media reads0, tool errors0, cycle0.

Следующий owner-gated этап: только exact cidfile byte/type/ACL/containment rule, затем AC006-only repeat review. Transfer/Q002/product/live закрыты.
