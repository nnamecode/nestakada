# REF-06F — результат локального backup current/previous

Дата: 2026-11-06. Решение: D-656. Приёмочный контракт: LBK-001–012 из `docs/ref6-local-backup-plan.md`.

## Результат

Добавлен закрытый host wrapper `scripts/local-backup.ps1` и ограниченный one-shot helper `tools/foundation_backup.sh`. Новый образ, daemon, Django model/UI, scheduler и backup-платформа не создавались. Закреплённый PostgreSQL image выполняет custom-format `pg_dump` ролью `app_migrator` с read-only session default, архивирует media и проверяет `pg_restore --list`, `tar --list` и SHA-256 до публикации. Secret читается из read-only файла во временный mode-0600 `.pgpass` в tmpfs и отсутствует в argv/output/manifest/archive.

Проверенные комплекты хранятся неизменяемыми каталогами `generations/<uuid>`. Flushed same-directory temporary file и atomic `File.Move`/`File.Replace` публикуют `catalog.json`, который назначает current/previous. Crash до replace оставляет прежний catalog authoritative; crash после replace — новый. Незавершённые staging/import/catalog artifacts и unreferenced поколения очищаются только по строгим contained names после проверки authoritative catalog. Ошибка post-publication cleanup даёт успешный результат `cleanup=pending`, а неоднозначный replace — честный `LOCAL_BACKUP_OUTCOME_UNKNOWN`.

Один per-environment `FileShare.None` lock сериализует backup и все foundation Start/Stop/UnitTests. Backup повторно сравнивает container id/running/restart/start/finish snapshot непосредственно перед publication. `Status` lock не создаёт и не берёт. Foundation удерживает handle через весь action и освобождает его единым `finally`, включая interactive error paths.

## Проверки

- Реальный holder: параллельный backup — exit1 `phase=lock`; foundation Stop отклонён до Docker mutation.
- Обратная гонка: foundation Start удерживал lock; backup после появления DB network/state — exit1 `phase=lock`; тот же Start завершился ready.
- Interactive error path: failing UnitTests при stopped foundation, затем немедленный exclusive reopen в том же PowerShell host — `INTERACTIVE_ERROR_RELEASE_OK`.
- Maintenance race: app запущен после появления staging; backup — exit1 `phase=maintenance-recheck`, staging0, authoritative catalog не изменился.
- Copy-first migration перенесла legacy current `818e2c86-6c38-4159-a05f-03e3633c48db` и previous `3cfce00b-86ed-4371-be60-8baa407353f8` до удаления legacy directories.
- Нормальная atomic publication: current `5adf6799-9797-49ac-b2ec-da22ea493868`, previous `818e2c86-6c38-4159-a05f-03e3633c48db`; старое `3cfce00b…` удалено только post-commit, cleanup `ok`.
- Network-none/read-only UID10001 verifier обоих catalog-referenced generations: SHA-256, `pg_restore --list`, `tar --list` — PASS.
- Exact scan значений пяти foundation secrets по backup storage — PASS; совпадений нет.
- Main test DB неизменна: AuditEvent 967, pages 6, revisions 22, states 6, drafts 1, restore stages 3, pins 1, receipts 396, identities 765.
- PowerShell/shell syntax и `git diff --check` — PASS. Foundation остановлен, named volumes и host generations сохранены.
- Независимое review после двух P1 и одного P2 remediation: `APPROVED`, findings отсутствуют.

External encrypted copy/key, schedule, restore execution, production/VPS, HTML reserve, requests и админский backup UI не входят в REF-06F. Локальный комплект не объявляется проверенным восстановлением.

## Следующая точка

Текущий этап — REF-06/REF-6. Следующий ограниченный инкремент выбирается отдельно по prerequisites: внешний backup требует storage/key, restore — отдельного изолированного runbook/test, HTML — настоящего public renderer, requests — LEGAL/design readiness. REF-Q004 закрыт.
