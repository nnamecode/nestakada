# DEV-29: независимое ревью lifecycle-диагностики

2026-11-04. /root/dev29_publication_review: PLAN APPROVED, P0–P2 blockers нет. Exact SHA90382746a92a0fcaa079cabbac1ca7113ea84b81e12c8f83ea4206357183e41a. Это scope нового read-only поручения D457, не разрешение функционального R021.

Один quiet read-only query/rootlabel/endpoint, async lifecycle metrics, native8999мс/combined1MiB/grace5с/total30с, capturedownchild killonce, raw0/exclusiveattempt+report. Causalclaims ограничены: PASS не объясняет прошлый sync failure, childwait не доказывает daemoncause. Старые packages/private/source/runner/SQL/settings исключены.

До probe обязательны implementation+offline mockedprocess/clock и inert Node child, отдельное code review. Code review должен проверить resolved fixed executable in-memory без личного пути в report, stdinEOF, monotonic timestamps, cap без накопления сверх1MiB, ownchild terminationonce/noPIDlookup и bounded abandonment без falseclose/terminationproof, deterministicclassification, pins непосредственно передspawn и wx/nooverwrite. Plan approval не заменяет эти gates или actualresult review.
