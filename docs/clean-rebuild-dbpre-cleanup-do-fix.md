# DBPRE cleanup-DO parenthesis fix

Дата: 2026-11-17. Candidate ID: `RB1-CLEANUP-DO-FIX-001`.

Основание: `RB1-CLEANUP-DO-PROBE-001` доказал compile failure `mismatched parentheses`. В settings-проверке строка с `setconfig <@ ARRAY[...]` уже закрывает `NOT EXISTS`; следующая отдельная `)` была лишней.

Изменение: в `tools/rebuild-dbpre.ps1` удалена только лишняя закрывающая скобка. Предикаты, markers, transaction, fallback, reader/facts, роли и внешние коды не менялись. Новых функций, процессов, файлов runtime, зависимостей и диагностических механизмов нет.

Статические проверки:

- PowerShell parser errors: 0;
- исправленный settings fragment: ровно 1;
- cleanup SQL blocks: 1;
- cleanup marker declarations: 8;
- `git diff --check`: PASS;
- Docker/DB/DBPRE/subject rows/product/live: 0.

Следующий gate: независимое read-only review кандидата. Runtime DBPRE требует отдельного owner continuation после одобренного review.
