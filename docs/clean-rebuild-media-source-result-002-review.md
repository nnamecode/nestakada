# REBUILD-1 media source runtime result 002 review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-SOURCE-RUN-002-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P1=2, P2=0, P3=0**.

- `RB1-MSRC-RUN002-P1-001`: DB-only scope exact-сравнивал full64 inspect ID с default short `docker ps -q` ID; deterministic START FAIL.
- `RB1-MSRC-RUN002-P1-002`: invalid-cid exact-name recovery требовал full64 regex от того же short output.

Остальные `docker ps -aq` используют только count и не требуют изменения. RUN002 final clean/reader0/verifier0/media0, privacy/retry0 подтверждены. No-bloat remediation D-1376 — ровно два `--no-trunc`, без helper/diagnostic expansion. Новый runtime требует fresh gate.
