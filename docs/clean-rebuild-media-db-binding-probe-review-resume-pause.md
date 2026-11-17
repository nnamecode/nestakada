# REBUILD-1 media DB binding probe resumed review pause

Дата: 2026-11-17. Review ID: `RB1-MEDIA-DB-BIND-PROBE-REVIEW-RESUME-001`.

Статус: **ПРИОСТАНОВЛЕНО ВЛАДЕЛЬЦУ; verdict не выдан**.

После явного owner resume начат fresh review cycle только с простыми `rg`. Первая strict-UTF8 проверка ошибочно использовала double-quoted `$false/$true/$bytes`; изменённый single-quoted retry прошёл. Затем в другой assertion family повторён тот же класс double-quoted `$bytes/$evidencePath` expansion. Это второй сбой класса; третьей попытки нет.

Успешно подтверждено до остановки: `ReadAllBytes` найден ровно в целевой функции, `Import-Csv` absent, `ConvertFrom-Csv` present, strict UTF-8 same-buffer present. Reviewer edits/runtime/DB/Docker/network0. Probe не исполнен.

Следующий безопасный вариант требует owner decision: координатор выполняет простые mechanical counts и передаёт рецензенту готовое evidence без reviewer shell-команд. Manual-only approval не рекомендуется.
