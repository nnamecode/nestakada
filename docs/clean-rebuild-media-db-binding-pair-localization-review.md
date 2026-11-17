# REBUILD-1 media DB binding pair localization review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-DB-BIND-PAIR-LOCALIZATION-REVIEW-001`.

Вердикт: **APPROVED — P1=0, P2=0, P3=0**.

`RB1-MDB-PLOC-AC-001..006` подтверждены. BINDING разделён ровно на DB/CANDIDATE/GALLERY по два assertion; все 23 contract assertions сохранены unique; literal order детерминирован. Fact names/values, hashes, paths, SQL и row data не раскрываются. Остальные categories, expected values, SQL, grants, output, cleanup, retry и old profile unchanged.

No-bloat PASS. Reviewer tools/edits/runtime/DB/Docker/network0.

Следующий gate: fresh owner continuation на один changed probe; не автоматический retry и не exporter/importer/Q002/product/live.
