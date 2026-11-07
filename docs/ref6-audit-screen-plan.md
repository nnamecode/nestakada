# REF-06B — минимальный экран аудита

Дата: 2026-11-06.
Основание: D-598, D-600, D-601, D-637, REF-AC-033 и поручение владельца «Продолжай».
Статус: приёмочный контракт записан до кода.

## Граница

Добавить только owner-only read-only экран уже существующих безопасных записей `AuditEvent`. Экран не создаёт новые события, не меняет модель и не читает файловые журналы.

В инкремент не входят: девять физических потоков, счётчики непросмотренного, отметка просмотра, удаление событий/категорий, retention/rotation, Telegram, произвольный поиск, трассировки, request body, тексты страниц/заявок и технические файлы. Эти правила требуют отдельного согласования полного logging scope.

## Приёмочные сценарии

- **AUDIT-001 — доступ.** Только действующая owner-session пользователя `nesadmin` получает экран; anonymous получает 401, employee — 403 до чтения `AuditEvent`. Все ответы закрыты `private, no-store`.
- **AUDIT-002 — bounded read.** Один запрос читает не более 50 событий в порядке от нового к старому. Следующая страница использует только положительный integer cursor `before`; offset и неограниченная выборка отсутствуют.
- **AUDIT-003 — точные фильтры.** Разрешены только один `category`, `level`, `result` и `before` из закрытых choices/формата. Неизвестные, пустые, дублированные и лишние параметры дают безопасный 400 без отражения значения.
- **AUDIT-004 — полезные поля.** Экран показывает время Europe/Moscow, category/level/code/source/result, actor username или ID fallback, typed object reference, occurrence count/lower-bound, request ID и IP только когда они уже присутствуют в безопасной записи.
- **AUDIT-005 — escaping.** Все значения рендерятся стандартным autoescape; HTML/URL/секретоподобная строка из legacy row не исполняется и не создаёт ссылку.
- **AUDIT-006 — read-only.** GET экрана и фильтрация не создают, не обновляют и не удаляют `AuditEvent`; POST/PUT/PATCH/DELETE не разрешены. Форм mutation на экране нет.
- **AUDIT-007 — отказ.** Ошибка PostgreSQL даёт закрытый 503 без traceback, query/filter values и содержимого событий.
- **AUDIT-008 — без расширения архитектуры.** Нет миграций, новых dependencies, фоновых задач, Telegram, файловых потоков, retention или category state.

## Проверки

Focused HTTP/DB tests AUDIT-001–008 на PostgreSQL, существующие `audit` и `accounts` regressions, migration/diff checks, read-only main DB/login smoke и независимое review.
