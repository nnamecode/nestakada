# REBUILD-1 ephemeral verifier repeat amendment review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-SOURCE-CONTAINER-REVIEW-002`.

Вердикт: **CHANGES_REQUESTED — P0=0, P1=1, P2=0**.

Previous P1-001 sequence и P1-002 entrypoint CLOSED. P1-003 log/cap/exact identity закрыт, кроме одной ложной cleanup-гарантии.

## `RB1-MSRC-CONT-P1-004` — post-start ambiguity

При daemon/client ambiguity после успешного start нельзя доказать, что verifier остановлен. Правильный flow:

- inspect mismatch до start → container не запускается, state created/stopped;
- timeout/daemon ambiguity после start → `UNKNOWN_ISOLATED`, `RESOLVED` запрещён;
- RRRO/reader/DB cleanup продолжается только насколько однозначно возможно;
- final containers0 не заявляется до exact captured ID stopped/absent proof;
- constant cleanup failure владельцу; captured ID хранится только в local private cleanup state, не output/Git;
- после восстановления Docker — отдельный exact ID/name/label/image inspection+cleanup, broad cleanup и media retry0.

AC001–005/007–008 PASS, AC006 CHANGES REQUIRED. Privacy/no-bloat PASS. Missing evidence1, overreach0. Files edited0, DB/Docker/runtime/media reads0, tool errors0, cycle0.

Следующий owner-gated этап: заменить только stopped-гарантию на `UNKNOWN_ISOLATED`, затем repeat review. New service/script/watchdog0; transfer/Q002/product/live закрыты.
