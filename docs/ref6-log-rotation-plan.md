# REF-06D — стандартная ротация технических логов

Дата: 2026-11-06.
Основание: D-598, D-600, D-601, D-641 и ответ владельца «Продолжай» на REF6-Q001.
Статус: приёмочный контракт записан до кода.

## Граница

Для четырёх постоянных контейнеров локального foundation-профиля (`app`, `db`, `ingress`, `media-worker`) явно закрепить стандартный Docker `json-file` logging driver с `max-size=10m` и `max-file=3`. Это ограничивает технические stdout/stderr примерно 30 МиБ на контейнер без отдельного сервиса.

Инкремент не включает и не меняет: PostgreSQL `AuditEvent`, его retention, admin UI, Telegram, badges, отметку просмотра, удаление категорий, девять потоков, Nginx access log, unsafe raw URI error log, внешний log collector, shipping, поиск или alerting.

## Приёмочные сценарии

- **ROT-001 — точный scope.** Одинаковая настройка применяется только к `app`, `db`, `ingress`, `media-worker`; tool/one-shot services не превращаются в постоянные log sources.
- **ROT-002 — стандартный предел.** Driver exact `json-file`, `max-size` exact `10m`, `max-file` exact string `3`; unbounded/default driver не остаётся у четырёх runtime services.
- **ROT-003 — реальная ротация.** Изолированный synthetic container без сети/mounts/secrets пишет более 30 МиБ canary-строк; retained `docker logs` bounded и старейший canary отсутствует, newest присутствует.
- **ROT-004 — cleanup.** Synthetic container получает уникальное точное имя, не использует данные проекта и удаляется после проверки; при отказе результат не выдаётся за PASS.
- **ROT-005 — безопасность.** Настройка не включает отключённые Nginx access/raw error logs, не меняет safe formatter приложения и не печатает secrets/DSN/request bodies.
- **ROT-006 — независимость audit.** AuditEvent rows/schema/retention не меняются; просмотр и бизнес-аудит остаются REF-06B.
- **ROT-007 — runtime.** App healthcheck/readiness, сети, ports, mounts, users, caps, restart policy и команды контейнеров не меняются.
- **ROT-008 — без платформы.** Нет dependency/service/volume/DB model/migration/scheduler/Telegram/collector/state machine.

## Проверки

Compose config и actual inspect четырёх test containers; отдельный bounded synthetic rotation probe с cleanup; readiness/login smoke; migration/diff checks; read-only main DB и независимое review.
