# REF-06E — результат фиксированной очистки AuditEvent

Дата: 2026-11-06. Решение: D-645. Приёмочный контракт: RET-001–008 из `docs/ref6-audit-retention-plan.md`.

## Результат

Добавлена закрытая management-команда `cleanup_audit`. Она один раз вычисляет aware cutoff `timezone.now() - 30 days` и в одной транзакции удаляет только `AuditEvent` с `occurred_at < cutoff`. Exact boundary и новые события сохраняются.

Команда не принимает дату, категорию, IDs или другой scope. Успех выводит только `AUDIT_RETENTION_OK deleted=N`; DB failure возвращает non-zero `AUDIT_RETENTION_UNAVAILABLE` без исходной ошибки. Публичного URL и автоматического расписания нет.

## Проверки

- Focused boundary/rollback/isolation tests: 3/3 PASS за 2.249 с.
- Audit writer/screen и полный accounts-контур: 64/64 PASS за 17.256 с.
- Failure test выполняет delete, затем поднимает DatabaseError и доказывает transaction rollback.
- `makemigrations --check --dry-run`: `No changes detected`; `git diff --check`: PASS.
- Статический поиск: нет refs команды в URL, Nginx или compose.
- Основная локальная test-БД не очищалась и неизменна: AuditEvent 967, pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner pins 1, receipts 396, identities 765.
- Независимое review: `APPROVED`, findings отсутствуют.

Scheduler/cron, retry/sleep, UI/category delete, badges/mark-read, Telegram, новые events, model/migration/dependency/service/volume/state machine не добавлены. Production, VPS и старый сайт не затрагивались. REF-Q004 закрыт.

## Следующая точка

Текущий этап — REF-06/REF-6. Ежедневный production schedule выбирается только на deployment. Оставшиеся HTML, заявки и backup требуют соответствующих renderer/legal/storage prerequisites.
