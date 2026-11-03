# P29-A: независимые code/result review

2026-11-03. Рецензент работал read-only; файлы не менял. Артефакт результата: `dev29-publication-results.md`, точные SHA трёх Python-файлов приведены в нём.

**P29-A-CODE-REVIEW-001 — APPROVED для standalone-проверок.** Замечаний P0–P3 нет. Проверены закрытый prepare route_publication, запрет LIVE_NO_SET в прежнем route_restriction, сохранение service-level report policy equality и PENDING_DENY. Consumer принимает journal data без HTML admission. Модель/constraints не требуют миграции. Conditional discovery определяет DB-классы при Django и не выдаёт их отсутствие на host за успешный DB-прогон.

**P29-A-RESULT-REVIEW-001 — APPROVED как частичный результат, не завершение P29-A.** Рецензент независимо повторил bundled Python -I -B: 4/4 PublicationWireTests OK (0.003s); AST parse 31 файлов PASS, git diff --check PASS. SHA protocol/consumer/test совпали с отчётом. Замечаний P0–P3 нет, ошибок инструментов не было.

Подтверждена честность матрицы: DB PENDING_DENY/report/replay/unknown/abort/rollback/admission и прежние регрессии не выполнены; свежая SQL-сохранность/permit не доказаны. Disk manifest не заменяет live evidence. Docker недоступен, сохранённый capacity-корпус защищён guard штатного Tests. Fixture не подменяет APP/cohort/EDGE. Дальше — отдельный конкретный способ изолированных DB-проверок с сохранением корпуса и review перед исполнением.
