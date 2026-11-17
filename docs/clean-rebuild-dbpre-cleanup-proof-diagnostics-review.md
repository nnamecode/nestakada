# Independent review: DBPRE cleanup proof diagnostics

Дата: 2026-11-17. Review ID: `RB1-CLEANUP-PROOF-DIAG-REVIEW-001`.

## Вердикт

**APPROVED — P1=0, P2=0, P3=0.**

`RB1-CPD-AC01..008` подтверждены. Stage выбирается только из literal allowlist5, последовательный scan сохраняет последний достигнутый marker, а отсутствие/неизвестный marker уходит в generic `DBPRE_FAILED_CLEANUP_ROLE`. Все пять уникальных markers достижимы и стоят перед своими группами: IDENTITY_STATE, SESSIONS, RELATIONS, PRIVILEGES, REVOKE_DROP.

BEGIN/COMMIT, proofs, literal revoke/drop, exact-OID fallback и four first-failure cleanup guards сохранены. Raw captured output при failure не возвращается; exact mapping5 ведёт только во внешний allowlist5, после чего `Stop-DbpreFailure` выдаёт одну bounded JSON-строку до PASS/facts.

Механика: parser0; AC IDs8; markers5/unique5/order PASS; candidate list1; mappings5/external allowlist5/default1; bootstrap defs1/calls3; fallback1; guards4; facts29/unique29; reader1; RRRO1.

No-bloat PASS: пять `RAISE NOTICE`, bounded parser уже захваченного output и один exact switch; новых функций, процессов, logger, diagnostic file, retry, dependency или runtime-компонента нет.

Review: edits0, runtime0, Docker0, DB0, network0, tool errors0, cycle0. Новый DBPRE требует отдельного owner gate.
