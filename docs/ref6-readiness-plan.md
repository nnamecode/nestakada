# REF-06C — простой закрытый readiness

Дата: 2026-11-06.
Основание: D-598, D-600, D-601, D-639, DEV-24 и поручение владельца «Продолжай».
Статус: приёмочный контракт записан до кода.

## Граница

Добавить management-команду Django `readiness` и стандартный Docker healthcheck только контейнеру `app`. Публичного HTTP endpoint нет. Команда подтверждает, что процесс способен загрузить Django и выполнить один bounded параметризованный `SELECT 1` к основной PostgreSQL.

В инкремент не входят: запись в БД/audit, проверка media/email/Telegram/backup, подробная диагностика, retries внутри команды, streak/state machine, signed admission, отдельный health service, внешний observer, переключение HTML fallback или production deployment.

## Приёмочные сценарии

- **READY-001 — закрытая поверхность.** Readiness доступен только как локальная management-команда внутри app container; нового URL/view/Nginx location/порта нет.
- **READY-002 — process + DB.** Успех означает, что Django загрузился и PostgreSQL в read-only transaction вернула ровно integer `1` из параметризованного `SELECT`.
- **READY-003 — bounded.** DB connect использует существующий timeout 5 секунд; transaction получает local statement timeout 2 секунды; Docker healthcheck имеет timeout 8 секунд, один запуск и без внутренних retry/sleep.
- **READY-004 — no write.** Команда явно начинает transaction read-only и не создаёт/меняет/удаляет business rows, sessions или AuditEvent.
- **READY-005 — закрытый отказ.** DB/timeout/unexpected-result дают non-zero и только константу `READINESS_UNAVAILABLE`, без exception, DSN, SQL, credentials или DB error text.
- **READY-006 — Docker semantics.** Только `app` получает healthcheck; interval 30 секунд, start period 10 секунд и 3 внешних retries. Healthcheck ничего не перезапускает и не меняет `restart: no` локального профиля.
- **READY-007 — отказ не управляет сайтом.** Readiness не включает fallback, restore, deploy, Telegram или admission; это только стандартный статус контейнера.
- **READY-008 — без новой платформы.** Нет модели/миграции/dependency/daemon/очереди/ledger/состояния readiness.

## Проверки

Focused command tests на PostgreSQL и fault mock, compose config, existing foundation/accounts smoke, migration/diff checks, read-only main DB и независимое review.
