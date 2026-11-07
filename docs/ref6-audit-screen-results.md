# REF-06B — результат минимального экрана аудита

Дата: 2026-11-06. Решение: D-639. Приёмочный контракт: AUDIT-001–008 из `docs/ref6-audit-screen-plan.md`.

## Результат

В owner-навигацию добавлен read-only экран существующих безопасных `AuditEvent`. Доступ имеет только действующая owner-session `nesadmin`; anonymous получает 401, employee — 403 до чтения журнала. Ответы закрыты `private, no-store`.

Экран показывает максимум 50 событий от нового к старому и использует keyset cursor `before`. Разрешены только точные одиночные фильтры category/level/result и положительный bounded cursor. Время явно отображается в Europe/Moscow. Значения выводятся через autoescape; mutation-команд и произвольного поиска нет.

Новых моделей, миграций, событий, dependencies и фоновых задач нет. Файловые журналы, retention/rotation, Telegram, удаление категорий, отметка просмотра и badges не реализовывались: полный logging scope остаётся отдельным согласованием.

## Проверки

- Focused AUDIT-001–008: 5/5 PASS за 0.666 с.
- Существующий audit writer/formatter и полный accounts-контур: 58/58 PASS за 11.984 с.
- `makemigrations --check --dry-run`: `No changes detected`.
- `git diff --check`: PASS.
- Anonymous HTTP smoke `/manage/audit/`: 401, `private, no-store`.
- Основная локальная test-БД после smoke неизменна: AuditEvent 967, pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner pins 1, receipts 396, identities 765.
- Независимое review сначала нашло P1: hidden materialization 51-й записи. Query ограничен ровно `LIMIT 50`, SQL boundary добавлена в тест; повторное review — `APPROVED`, новых замечаний нет.

Ранний host `python` check не стартовал из-за отсутствия доступной команды. Первый Start через Windows PowerShell 5 остановился до контейнеров на несовместимом ACL API; принятый D-604 PowerShell 7 launcher создал стенд штатно. Два первых focused-прогона дали 4/5 из-за тестовых fixture/assertion; fixture приведён к typed writer contract, assertion ограничен секцией аудита, а выявленное UTC-отображение исправлено на Europe/Moscow. Продуктовый код в этих отказах не исполнял mutation.

Production, VPS и старый сайт не затрагивались. REF-Q004 остаётся закрытым.

## Следующая точка

Текущий этап — REF-06/REF-6. Следующий инкремент следует выбрать отдельно. HTML-резерв целесообразно реализовывать после появления настоящей публичной выдачи; заявки — только с синтетическими данными до LEGAL-01 и после дизайна главной. Полный logging scope требует отдельного согласования.
