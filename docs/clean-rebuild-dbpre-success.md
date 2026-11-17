# REBUILD-1 source DB preflight result

Дата: 2026-11-17. Evidence ID: `RB1-DBPRE-PASS-001`.

После D-1305 owner разрешил ровно один changed DBPRE run с gate `RB1-READ-Q001`.

Безопасный result envelope:

| Поле | Результат |
|---|---|
| `contract` | `rb1-dbpre-v1` |
| `status` | `PASS` |
| `source` | `foundation-dev` |
| `factCount` | `29` |
| `elapsedMs` | `522` |

PASS означает, что в одном reader connection и одной `REPEATABLE READ READ ONLY` transaction получены ровно 29 allowlisted aggregate facts; `DBPRE-MAP-001..005`, `STRUCT-CURRENT-INVALID`, `STRUCT-CURRENT-NEWER` и `STRUCT-PAGE-WITHOUT-STATE` равны нулю. Raw rows, private values, source IDs, SQL и secret в result не выводились.

Обязательный cleanup завершился до выдачи PASS: exact temporary role была переведена в NOLOGIN, проверена, получила literal revoke и удалена в одной transaction; cleanup failure имел бы приоритет над PASS. После процесса независимо подтверждены `FINAL_CONTAINERS=0` и отсутствие фактического host secret `work/foundation/dev/private/rebuild-reader-password`.

Postcheck note: первая filesystem-проверка использовала устаревшее имя secret и не была засчитана. Следующая команда с правильным путём была отклонена до запуска, потому что координатор ошибочно добавил ненужный `docker run`; новый контейнер не создавался. Материально более безопасный filesystem-only `Test-Path` дал `FINAL_ACTUAL_SECRET=0`. DBPRE не повторялся.

Scope: один DBPRE; retry0; product/Q002/target DB/media/importer/live/deploy0. Новый logger/scanner/service/framework не добавлен.

Следующий gate: независимое read-only review результата и его соответствия `RB1-DBPRE-AC-001..008`. Новый DBPRE не нужен.
