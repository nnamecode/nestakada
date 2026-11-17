# REBUILD-1 media DB binding probe candidate

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-DB-BIND-PROBE-001`.

## Реализация

Вместо второго дублирующего lifecycle-runner существующий `tools/rebuild-dbpre.ps1` получил закрытый gate/profile `RB1-MEDIA-BIND-Q001`. Прежний `RB1-READ-Q001` профиль сохранён. Новый профиль переиспользует проверенные precheck, exact secret transport, fresh JIT role, TLS connection1, cleanup proof/fallback и compose teardown.

Отличия media-binding профиля:

- exact grant только на утверждённые 8 таблиц;
- authority CSV проверяется по принятому SHA-256, выбирает exact301 и требует 301 уникальную SHA+bytes pair;
- SQL stdin получает только literal SHA/bytes/cohort values, без path/ID/source URL;
- `tools/rebuild-media-binding.sql` выполняет одну `REPEATABLE READ READ ONLY` transaction и возвращает ровно 30 bounded integer facts;
- runner принимает PASS только при 238/238/736, matched238/candidate-only63/gallery214 и всех anomaly0; drift возвращает constant failure без facts/allowlist growth/retry.

## Статические проверки

- PowerShell parser errors: 0;
- SQL facts: 30/30 unique; candidate placeholder1; RRRO1; rollback1;
- authority: rows301, unique SHA+bytes301, gallery214, digest exact;
- `git diff --check`: PASS.

## Границы

Новых dependencies, service, exporter, manifest, temp table, model или product code нет. DB/Docker/runtime ещё не запускались. Следующий обязательный шаг — independent pre-execution review; только APPROVED разрешает уже owner-gated один probe.
