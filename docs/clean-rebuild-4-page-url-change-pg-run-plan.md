# REBUILD-4 — Page URL Change PostgreSQL run

Дата: 2026-11-21. ID: `RB4-PAGE-URL-PG-001`. Статус: **draft остановлен на выборе нового transport; Docker/runtime 0**.

## Цель и граница

Один будущий локальный Docker/PostgreSQL запуск должен доказать независимо одобренный `RB4-SLICE-004G-PAGE-URL-CHANGE`. В запуск входят только migration drift, новые exact12 и 25 затронутых regression tests. Page Move/Reorder/Delete runtime diagnostics, host TLS/RNG investigation, media read, browser/live/deploy/push и повтор при ошибке не входят.

Transport пока намеренно не выбран: прежний internal-network TLS путь owner-paused на host TLS/RNG, а Page Delete socket-only путь owner-paused после PostgreSQL exit до readiness. Ни один из них нельзя молча повторить или переименовать. До отдельного решения владельца о materially different transport coordinator не готовится.

Источник фиксируется SHA-256 для каждого выбранного файла до создания контейнеров. Используются уже зафиксированные проектом Django/PostgreSQL images и принятые ограничения: внутренний isolated network, отдельные временные DB/volume/container names, non-root/resource limits, секрет только через ephemeral file/mount, отсутствие публикации портов, гарантированный cleanup и post-audit ноль созданных объектов. В evidence нет паролей, environment, raw SQL rows, payloads, пользовательских данных или полных exception/log dumps.

## Закрытый набор

Ожидается ровно `37` тест-методов:

- `src/modules/pages/tests/test_url_change.py` — 8;
- `src/modules/pages/tests/test_http_url_change.py` — 4;
- `src/modules/pages/tests/test_create.py` — 8;
- `src/modules/pages/tests/test_delete.py` — 8;
- `src/modules/pages/tests/test_contract.py` — 4;
- `fitness.test_rebuild3_schema.Rebuild3SchemaSourceTests.test_page_url_authority_field_matches_ordinary_add_field_migration` — 1;
- `rebuild3_importer.tests.test_runtime_target.TargetProjectionTests.test_literal_projection_verifies_before_single_commit` — 1;
- `rebuild3_importer.tests.test_runtime_target.TargetCommittedReadbackTests.test_exact_committed_projection_returns_closed_proof_once` — 1;
- `rebuild3_importer.tests.test_runtime_target.TargetCommittedReadbackTests.test_any_row_or_count_drift_fails_closed` — 1.
- `rebuild3_importer.tests.test_runtime_target.TargetMigrationRunnerTests.test_exact_leaves_generated_alias_and_cleanup` — 1.

До tests выполняются `manage.py check`, `makemigrations --check --dry-run` и миграция пустой test DB до leaf `pages.0003_page_primary_url_mutable`. Importer assertions обязаны доказать literal SQL `FALSE`, readback/digest false, invariant false-only и migration leaf `0003`. Test discovery обязан совпасть с literal37; любое расхождение закрывает запуск до tests.

## Результат и остановка

`PASS37` принимается только при migrations/check success, tests37/failures0/errors0, app/PG clean exit, cleanup0 и post-audit0. Любое иное состояние — `ACCEPTED_FAIL` или `UNDETERMINED` с фиксированной безопасной стадией; автоматического retry, diagnostic subdivision или guessed fix нет. Ошибка до product tests не разрешает повтор без нового свидетельства и решения владельца.

После независимого review этого плана coordinator может быть подготовлен и проверен статически, но Docker запускается только по отдельному явному разрешению владельца.
