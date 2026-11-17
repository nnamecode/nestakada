# Independent review: REBUILD-1 exact301 media SHA result

Дата: 2026-11-17. Review ID: `RB1-MEDIA-HASH-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P1=0, P2=1, P3=0**.

Finding `RB1-MEDIA-HASH-REV-P2-001`: result envelope и arithmetic согласованы, но workspace не содержит exact выполненный одноразовый scriptblock или его digest. Поэтому независимо не подтверждаются selector implementation, fail-closed containment/traversal, exact `FileStream` access/share, сравнение evidence bytes с stream length и bounded output во всех ветках.

Подтверждено без повторного media hashing:

- selector facts301/unique301/duplicates0;
- path-string rooted/traversal/outside-media0, malformed SHA/bytes0;
- total301/56134441, gallery214/41176391, ordinary87/14958050;
- envelope сообщает mismatch0/3504ms, но runtime claims ждут воспроизводимого command evidence;
- DB238 binding, manifest freeze, importer/exporter, target, WBS, Q002, product/live boundaries корректны;
- no-bloat PASS; reviewer edits/media hashing/Docker/DB/runtime/network0.

Минимальная remediation: без повторного чтения media bytes добавить exact выполненный scriptblock как неисполняемый appendix в существующий result evidence и зафиксировать его SHA-256. Постоянный scanner/tool не создавать.
