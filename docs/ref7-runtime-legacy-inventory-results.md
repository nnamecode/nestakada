# REF-07C: результат инвентаризации оставшегося legacy lifecycle

Дата: 2026-11-09
Основание: D-675, `docs/ref7-runtime-legacy-inventory-plan.md`.

## Итог

Read-only инвентаризация завершена. Удалять page lifecycle целиком сейчас нельзя. Для следующего отдельного инкремента выбран только узкий кандидат `REF-07D`: убрать из административного HTTP-интерфейса Header/Footer старые cleanup/diagnostics/result/legacy-restore endpoints и ссылки на них, не удаляя таблицы, строки, историю, blobs или storage-код.

Любая реализация REF-07D требует отдельного решения владельца и приёмочного плана до кода.

## Фактическое состояние

### Версии страниц

- `IdentityReservation`: 765 строк; новые простые операции не используют универсальную reservation book, но существующие строки читаются collision/replay guards и сохраняются при удалении страницы.
- `OperationReceipt`: 396 строк; новые простые save/draft/publish/restore/manual/Stable/tree операции их не создают, но действующие команды всё ещё читают старые receipts для точного replay и collision guard.
- `RestoreStage`: 3 строки, все terminal/consumed; код чтения старых стадий и проверки удаления страницы остаётся активным.
- `VersionBasePin`: 1 строка для owner draft; это действующая защита основы черновика, а не мёртвые данные.

Вывод: удаление этих моделей или общей совместимости сейчас затронуло бы сохранённую историю, replay/collision semantics либо защиту черновика. Это не безопасный следующий кандидат.

### Общие Header/Footer

- `SharedBlock`: 2; `SharedRevision`: 6, все `inline`.
- `SharedDraft`: 0; `SharedBasePin`: 0.
- `SharedRestoreStage`: 4, из них 2 `consumed` и 2 `released`; held стадий нет.
- `SharedCleanupJob`: 2, обе `complete`; незавершённых cleanup jobs нет.
- `SharedReceipt`: 36; `SharedIdentityReservation`: 96; `SharedBudget`: 1.
- Физическое хранилище содержит 6 сохранённых legacy blobs и не содержит journal. В БД нет ни одной file-backed revision или draft, поэтому эти blobs не читаются текущими шестью revisions, но в этой инвентаризации они не удалялись.

Нормальный apply/draft/publish/restore уже использует `simple_commands.py` и inline PostgreSQL. Новый legacy restore закрыт ответом 410. Однако переходная совместимость ещё не мертва полностью:

- простые insert revision/draft пока создают `SharedIdentityReservation`;
- `content.py` и public/history renderer сохраняют file-backed fallback;
- старые cleanup, diagnostics, result и stage-cancel URL остаются маршрутизированы;
- history показывает cleanup links/jobs;
- legacy commands/commits, quota/reservations/profile/storage связаны между собой и не должны удаляться одним механическим патчем.

## Следующий ограниченный кандидат: REF-07D

Сначала убрать только неиспользуемую административную поверхность старого lifecycle:

1. удалить cleanup/diagnostics/result/legacy restore prepare/cancel routes и соответствующие view/template links;
2. не менять обычные editor/check/draft/apply/history/version/compare/direct restore;
3. не менять session, generation, CSRF, owner gate, normalizer, media validation, audit, scanner или throttle;
4. не удалять модели, migrations, строки, blobs, storage fallback и backup;
5. до кода записать HTTP-сценарии: старые URL закрыты, обычный Header/Footer workflow и public rendering неизменны, история доступна, БД/media неизменны;
6. после реализации провести targeted и full shared regressions и независимое review.

После отдельного успешного REF-07D можно новой read-only проверкой определить следующий слой: прекращение новых `SharedIdentityReservation`, затем schema/storage cleanup. Эти действия нельзя автоматически включать в REF-07D.

## Безопасность и сохранность

REF-07C ничего не менял. SQL injection, ORM/parameter binding, CSRF, роли, sessions/generation, login throttle, audit, request scanner, private headers, normalizer и media checks не затронуты. Содержимое HTML, payload, персональные данные, cookies и секреты в отчёт не извлекались. Production/VPS/старый сайт не затрагивались.

## Приёмка REF-07C

- `R7C-I001` — PASS: page reads/writes классифицированы.
- `R7C-I002` — PASS: shared reads/writes и HTTP wiring классифицированы.
- `R7C-I003` — PASS: получены только агрегатные counts/status/storage-kind.
- `R7C-I004` — PASS: page simple paths не создают legacy receipts; shared simple paths всё ещё создают identities.
- `R7C-I005` — PASS: file-backed DB rows = 0; шесть blobs не читались и не удалялись.
- `R7C-I006` — PASS: security runtime исключён из кандидата.
- `R7C-I007` — PASS: выбран один ограниченный кандидат REF-07D.
- `R7C-I008` — PASS: foundation штатно остановлен; private files, named volumes и backup сохранены.
