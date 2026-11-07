# REF-06C — результат простого закрытого readiness

Дата: 2026-11-06. Решение: D-641. Приёмочный контракт: READY-001–008 из `docs/ref6-readiness-plan.md`.

## Результат

Добавлена локальная Django management-команда `readiness` и стандартный Docker healthcheck только контейнеру `app`. Публичного URL, нового порта или Nginx location нет.

Команда открывает transaction, первым SQL переводит её в read-only, transaction-local задаёт statement timeout 2000 мс и выполняет параметризованный `SELECT 1`. Существующий connect timeout — 5 секунд; Docker timeout — 8 секунд. Успех завершается exit 0 без вывода. DB failure, timeout или неожиданный результат дают non-zero и только `READINESS_UNAVAILABLE` без исходной ошибки.

Healthcheck использует exec-form `CMD python -B manage.py readiness`, interval 30 секунд, start period 10 секунд и 3 Docker retries. `restart: no` сохранён. Команда ничего не переключает и не управляет fallback, restore или deployment.

## Проверки

- Focused command tests: 3/3 PASS за 1.938 с.
- Полный accounts-контур: 39/39 PASS за 13.154 с.
- Фактический app health: `healthy`, failing streak 0, exit 0, output пустой.
- Прямой runtime-smoke: exit 0, output пустой.
- Реальный отказ: при кратко остановленной локальной test DB команда завершилась exit 1 за 3.455 с и вывела только `CommandError: READINESS_UNAVAILABLE`; после запуска DB — exit 0 без вывода.
- `docker compose config` подтвердил exact CMD и 8s/30s/10s/3 только у app, `restart: no`.
- Статический поиск не нашёл readiness в URL/Nginx; HTTP `/readiness/` вернул обычный 404.
- `makemigrations --check --dry-run`: `No changes detected`; `git diff --check`: PASS.
- Основная локальная test-БД после повторяющихся healthchecks и failure/recovery неизменна: AuditEvent 967, pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner pins 1, receipts 396, identities 765.
- Независимое review: `APPROVED`, findings отсутствуют.

Новых моделей, миграций, dependencies, audit writes, retries внутри команды, daemon/service, ledger, state machine, signed admission, observer, Telegram или fallback control нет. Production, VPS и старый сайт не затрагивались. REF-Q004 закрыт.

## Следующая точка

Текущий этап — REF-06/REF-6. Следующий инкремент выбирается отдельно с учётом оставшихся зависимостей: настоящий HTML build требует публичный renderer; заявки требуют дизайн главной и LEGAL-01; полный logging scope и backup destination/ключ требуют отдельных решений.
