# REF-05L — простые publish/hide и автоматическая навигация

Дата: 2026-11-06. Статус: утверждён к реализации ответом владельца «Продолжай» после D-625.
Область: owner-only переключение `Page.is_published` для существующей страницы и проверка уже существующей динамической `public_tree`. URL change, delete, HTML build/fallback, schema и legacy-код вне инкремента.

## Что упрощаем

Для лайт-версии не создаём `PublicationIntent`, TRUST policy, APP cohort, EDGE gate, prepare/final receipts или отдельную таблицу навигации. Обычная публичная видимость определяется `Page.is_published`, точным PRIMARY route и текущей revision; навигация уже вычисляется из актуального дерева на чтении.

Это изменение локального нового сайта, не публикация на VPS/production и не переключение старого сайта. Ручной HTML-резерв и Nginx fallback относятся к REF-6 и здесь не реализуются.

## Приёмочные сценарии

- **PUB-001 — права и сессия.** GET/POST доступны только `nesadmin` с актуальными generation/editor-session и CSRF; сотрудник/анонимный/прямой запрос не меняют состояние.
- **PUB-002 — точное подтверждение.** Token связывает actor, generation, page, operation, действие publish/hide, locked PostgreSQL `xmin`, точный PRIMARY route и current revision ID/hash. Подмена action/page/token отклоняется.
- **PUB-003 — готовность.** Publish/hide допускаются только при ровно одном PRIMARY route и валидном current revision с совпадающим payload hash. Draft/Stable не подменяют current. Отсутствующая/повреждённая основа не меняет флаг.
- **PUB-004 — локальная транзакция.** Успех одной transaction меняет только `Page.is_published` и создаёт один `TREE_PUBLISH` либо `TREE_HIDE` audit. Name/kind/parent/position, routes, revisions/Stable/drafts/media неизменны.
- **PUB-005 — публичная выдача.** Publish атомарно переводит PRIMARY из hidden в published и добавляет страницу в `public_tree`; hide делает обратное. Отдельная navigation state/table отсутствует.
- **PUB-006 — скрытый родитель.** Hide родителя не меняет publication flags детей. Опубликованный ребёнок остаётся в `public_tree` под ближайшим опубликованным предком; повторный publish родителя возвращает естественную иерархию.
- **PUB-007 — stale/ABA/concurrency/no-op.** `xmin`+PRIMARY+current stamp отклоняет изменение page/URL/current после GET, ABA, второй concurrent submit и уже достигнутое состояние. Несвязанная ветка не инвалидирует форму.
- **PUB-008 — отсутствие ledger и rollback.** Новые `OperationReceipt`/`IdentityReservation` не создаются. Audit/DB failure откатывает флаг; lost response/repeat конфликтует, актуальный GET показывает состояние.
- **PUB-009 — границы.** Rename/reorder/move/create не меняются. Publish/hide не меняют URL, не запускают HTML build и не удаляют данные. URL change/delete и REF-Q004 закрыты.

## Проверка

Focused command/HTTP/fault/concurrency/navigation, затем весь `content`, затем `media_library + page_versions`. После — независимое review, read-only main DB/login и остановка `foundation-test`. Production, VPS и старый сайт не затрагивать.
