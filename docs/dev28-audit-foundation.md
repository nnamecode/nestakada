# DEV-28 — основа безопасного аудита

2026-10-30. Реализация в пределах разрешённой очереди DEV-02/DEV-28. Основания: D-102, D-112, REQ-038/AC-038, описание AuditEvent в архитектуре и §2 analytics-runtime-detail.md. Состояние задач и решение о начале кода фиксирует координатор.

## API и состав

`audit.apps.AuditConfig` добавляется в INSTALLED_APPS; `audit.formatters.SafeJsonFormatter` применяется к обработчикам process logging. Импорт formatter не импортирует модели и не пишет в БД.

`audit.services.record_event` принимает только явно перечисленные параметры:

- `category`, `event_code`, `level`, `source`, `result` — словарь из audit.constants и стабильный код, заданный вызывающим кодом, не пользовательским текстом.
- `actor_id` — положительный внутренний integer ID; `object_ref` — положительный integer ID либо объект UUID, `object_kind` — технический тип объекта; текст/URL/номер телефона как ссылка не принимаются. В БД ссылка канонизируется как id:123 или uuid:….
- `request_id`, `event_id` — типизированные UUID; event_id по умолчанию генерируется однократно. Внутренний BigAuto PK используется как cursor, UUID — единый ID события между источниками.
- `ip_address` — только корректный IP при явном `ip_related=True`. Источник IP должен быть доверенно установлен вызывающим кодом, не взят произвольно из forwarded-заголовка. Правил определения клиентского IP или новых HTTP middleware здесь нет.

AuditEvent содержит ровно девять категорий D-102, уровень/источник/результат, aware timestamp, безопасные ссылки и необязательный связанный IP. FK на ещё не реализованных пользователей/контент нет: удаление будущего пользователя/объекта не каскадирует историю. Нет свободного message/context/body JSON-поля. Сервис выполняет один INSERT, участвует в транзакции вызывающего кода и возвращает сохранённый ORM-объект. Ошибки/неизвестные параметры не выдаются за успешную запись, повторов и неявной записи во второй источник нет. Уникальность event_id защищена БД.

`Model.save` допускает только добавление и валидирует поля. Это ограничение API модели; оно не является обещанием абсолютной DB-immutability против raw SQL или QuerySet.update. Доменная защита удаления/retention/cursors/ручного удаления остаётся соответствующими последующими модулями.

## Process formatter

Formatter сериализует фиксированную схему, не вызывает getMessage/str/repr для msg, args, request, неизвестных extras или exception/stack. В JSON попадают только нормализованные ссылки/словарные поля. Некорректный record приводит к постоянному безопасному LOG_RECORD_REJECTED, а не исключению formatter с опасным стандартным logging fallback.

Для FOUNDATION-011: передать `event_code="FOUNDATION-LOG-BENIGN"` в LogRecord extra и настоящий synthetic payload с семью полями в msg/args/extras. Formatter оставляет event_code, а payload не сериализует. Никакой проверки особых строк canary в реализации нет.

В обычном неструктурированном process record остаётся PROCESS_MESSAGE, безопасный уровень и UTC instant; исходный текст/trace не печатается. Это сознательный минимум безопасного process logging, не полноценная диагностика/каталог кодов всей системы. События приложения должны задавать постоянные коды и необходимые структурные refs.

## Проверки и границы

Добавлены содержательные unit/privacy и PostgreSQL integration tests: nested canaries/exception/args/URL, запрет repr, malformed records, typed refs/IP, девять категорий, единичная запись, rollback, propagation DB error, duplicate ID, отказ свободного payload, immutable save API и DB choice constraint. Исполнение выполняет координатор в согласованном Docker; этот документ не утверждает прохождение до полученного результата.

Не реализованы панель логов, файлы/сегменты/ротация/квоты, очистка/retention, Telegram/outbox/notification cycles, полные AC-038/OPS или функциональность бизнес-модулей. Нет views/admin/публичных endpoints, фоновых задач или сбора настоящих заявок. Старый сайт/VPS не затрагиваются.

Фактический результат 2026-10-30: общие 21 unit/integration PASS, 11 FOUNDATION PASS; реальные runtime INSERT/read/rollback и запрет DDL подтверждены. DEV-REV-001–005 исправлены, независимый отчёт — [dev02-dev28-review.md](dev02-dev28-review.md). Полный объём логов остаётся за пределами DEV-28.

DEV-03,D-320: в audit0002 добавлены occurrence_count (строгий положительный int,default1) и count_is_lower_bound(defaultFalse) для bounded агрегатов без JSON/raw payload. Переполнение честно маркируется нижней границей; auth service публикует первые значимые события и итоговые группы перед очисткой. Финальные75unit с прежними audit/privacy проверками прошли; [dev03-auth.md](dev03-auth.md).
