# REBUILD-1 media source offline harness code review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-SOURCE-OFFLINE-HARNESS-CODE-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P1=3, P2=1, P3=0**.

- `P1-001`: tmpfs drift expected wrong phase code.
- `P1-002`: boundary fakes did not exact-check all args/global call order.
- `P1-003`: full argv/entrypoint counts, inspect count>1 and MemorySwap drift missing; last item revealed production inspect gap.
- `P2-001`: static guards used global string counts instead of scoped AST.

D-1392 remediation stays bounded: exact tmpfs case; one global canonical boundary queue and exact fake signatures/args; complete drift/count cases; scoped AST checks. Production change is exactly one `MemorySwap=128m` inspect assertion matching existing create arg. No new runtime branch/module/dependency.
