# REF-06E — фиксированная очистка AuditEvent старше 30 суток

Дата: 2026-11-06.
Основание: D-037/D-038, D-098, D-598, D-600, D-601, D-643.
Статус: приёмочный контракт записан до кода.

## Граница

Добавить одну закрытую Django management-команду `cleanup_audit`, которая в одной транзакции удаляет только `AuditEvent` с `occurred_at < now - 30 days`. Cutoff вычисляется один раз. Команда не принимает дату, категорию или произвольный фильтр.

В инкремент не входят scheduler/cron, UI-кнопка, ручное категорийное удаление, badges/mark-read, Telegram, новые event codes, файловые логи и backup. Автоматический ежедневный запуск на production согласуется при deployment.

## Приёмочные сценарии

- **RET-001 — exact retention.** Удаляются только события строго старше 30 суток; exact boundary и более новые сохраняются.
- **RET-002 — fixed command.** Нет параметров cutoff/category/IDs; пользователь не может расширить область удаления.
- **RET-003 — одна transaction.** Вычисленный cutoff применяется к одному atomic delete; DB failure откатывает действие.
- **RET-004 — audit only.** Страницы, версии, users, sessions и другие таблицы не меняются.
- **RET-005 — safe result.** Успех выводит только `AUDIT_RETENTION_OK deleted=N`; DB failure — non-zero `AUDIT_RETENTION_UNAVAILABLE`, без event data, SQL, DSN или exception text.
- **RET-006 — закрытая поверхность.** Команда не получает URL/view/Nginx location/port и не вызывается посетителем или сотрудником.
- **RET-007 — без ложного расписания.** В коде нет sleep/retry/background daemon; наличие команды не объявляется ежедневным production job.
- **RET-008 — без расширения.** Нет model/migration/dependency/service/volume/ledger/state machine/Telegram/UI mutation.

## Проверки

Focused PostgreSQL boundary/rollback/no-write tests, audit/accounts regressions, migration/diff checks, read-only main DB и независимое review. На основной test DB cleanup не запускать.
