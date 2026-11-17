# REBUILD-1 ephemeral verifier amendment review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-SOURCE-CONTAINER-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P0=0, P1=3, P2=0**.

## Findings

### `RB1-MSRC-CONT-P1-001` — container sequence

`project containers0` до verifier launch невозможно совместить с открытой RRRO session: DB container уже работает. Правило: pre-run containers0; runner запускает только exact verified DB container; перед verifier допускается ровно DB container, app/worker/ingress/tools/verifier0; после rollback/cleanup снова containers0.

### `RB1-MSRC-CONT-P1-002` — exact entrypoint

Замена CMD не отменяет image ENTRYPOINT. Нужны static exact pinned image config check и explicit reviewed `--entrypoint` на Python executable, затем exact `-I -S -c` argv. Image/config/entrypoint mismatch fails before read.

### `RB1-MSRC-CONT-P1-003` — logs и exact cleanup

Добавить `--log-driver none`, constant-only exception handling и bounded stdout/stderr capture. `--rm` остаётся convenience; `finally` проверяет exact predetermined name + evidence label + captured container ID, удаляет только однозначно совпавший residual и доказывает absence. Ambiguity fail-closed без broad cleanup.

## Acceptance result

- `AC001`, `AC004`, `AC007`, `AC008`: PASS;
- `AC002`, `AC003`, `AC005`, `AC006`: CHANGES REQUIRED только по трём findings.

Image/volume/isolation/mount/stdin/dir-fd O_NOFOLLOW/exact301/no-bloat intent подтверждены. Missing evidence3, overreach0. Files edited0, DB/Docker/runtime/media reads0, tool errors0, cycle0.

Следующий owner-gated этап: только документационная remediation sequence/entrypoint/log-cleanup и repeat amendment review. Implementation/runtime/transfer/Q002/product/live закрыты.
