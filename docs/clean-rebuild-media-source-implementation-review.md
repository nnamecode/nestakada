# REBUILD-1 media source verifier implementation review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-SOURCE-IMPLEMENTATION-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P1=3, P2=2, P3=0**.

Проверенный snapshot: `tools/rebuild-dbpre.ps1` `83010fa37594d54f49a3b54445385416efd8ce4c77e37e1f3d039a354f7473ca`; `tools/rebuild-media-source.sql` `7aa9c5dd8a83727d6a237539fc0a9b95ab12919f88e2074d9fc4fdfbe3481ff4`.

Findings:

- `RB1-MSRC-IMP-P1-001`: key grammar не отклоняла trailing dot и Windows device basename с extension.
- `RB1-MSRC-IMP-P1-002`: invalid cidfile мог оставить residual container без долговечной exact cleanup identity.
- `RB1-MSRC-IMP-P1-003`: final project/verifier/cidfile/volume postconditions выполнялись только после success.
- `RB1-MSRC-IMP-P2-001`: verifier stdout/stderr cap был post-hoc, а не streaming hard cap.
- `RB1-MSRC-IMP-P2-002`: inspect не сравнивал exact inline code и несколько HostConfig запретов.

Подтверждено: one TLS/RRRO snapshot, exact unmatched READY/nonlegacy/main usages2+1, memory/stdin-only descriptor, pinned image/state volume, DB-only sequence, create→inspect→start, cidfile grammar/ACL, O_NOFOLLOW one-fd size/SHA, UNKNOWN_ISOLATED, retry0/broad-cleanup0, old gates preserved, privacy/no-bloat PASS. Runtime/Docker/DB/media0, reviewer edits0.

Remediation D-1368 локальна: strict shared semantics во всех трёх key checks; manifest runId-derived recoverable exact name/evidence плюс exact-name cleanup; final postconditions для всех known outcomes кроме UNKNOWN_ISOLATED; fixed257 streaming readers; exact argv code/CapAdd0/privileged0/auto-remove0/restart=no. Новый service/image/script/dependency/state file отсутствует. Следующий шаг — repeat code review; runtime закрыт.
