# REF-05K — простое создание страницы и PRIMARY route

Дата: 2026-11-06. Статус: завершено по D-625; независимое review `APPROVED`.
Область: owner-only создание одной скрытой Page, одного точного PRIMARY route и обязательного начального revision/state/draft-агрегата. Publish/hide, последующее изменение URL, delete, schema и legacy-код вне инкремента.

## Что упрощаем

Старый create связывает локальную вставку с basis всего дерева, всех routes/current revisions и счётчика tree receipts, затем создаёт отдельные `tree_page` IdentityReservation и OperationReceipt. Новый путь использует заранее подписанный UUID страницы как естественный ключ результата, локальный снимок parent/siblings и фактические UNIQUE/route validators.

IdentityReservation, которые пока автоматически сопровождают immutable initial `PageRevision` и `OwnerDraft` в существующей модели версий, не удаляются в этом инкременте: их schema/данные можно чистить только после REF-Q004. Новый create не добавляет tree-specific reservation и operation receipt.

## Приёмочные сценарии

- **CREATE-001 — права и сессия.** GET/preview/save доступны только владельцу с актуальными generation/editor-session; authoritative проверка предшествует token. Сотрудник, CSRF bypass и прямой запрос не создают данных.
- **CREATE-002 — закрытые поля.** Token строго связывает actor, generation, page UUID, operation UUID, kind, parent и локальные stamps. POST не может подменить page/operation/kind/parent; `is_published`, route kind и другие защищённые поля отсутствуют в разрешённой форме.
- **CREATE-003 — точный URL.** Name/H1/title проходят существующие длины/Unicode-ограничения. URL принимается без переписывания только как допустимый новый локальный path, не scanner/private namespace; занятый target отклоняется по проверке и UNIQUE без SQL-конкатенации.
- **CREATE-004 — атомарный агрегат.** Одна transaction создаёт скрытую Page в конце выбранной sibling-группы, ровно один PRIMARY route, initial revision+metadata, current state, owner draft+pin и один `TREE_CREATE` audit. Ошибка любого шага откатывает всё.
- **CREATE-005 — локальный stale/ABA.** Locked PostgreSQL `xmin` parent и полный sibling snapshot отклоняют изменение/удаление parent и relevant sibling-набора, ABA и concurrent conflict. Несвязанная ветка и изменение её URL не инвалидируют форму.
- **CREATE-006 — конкурентный double-submit/lost response.** Заранее подписанный page UUID даёт ровно один агрегат/audit. Повтор того же результата распознаётся по exact Page/PRIMARY/immutable initial revision/audit и возвращает replay без второй записи; несовпадающий pre-existing UUID конфликтует.
- **CREATE-007 — отсутствие нового tree ledger.** Новый путь не создаёт OperationReceipt и отдельную IdentityReservation для Page/команды. Operation UUID, уже занятый legacy receipt/identity, и page UUID, занятый чужим объектом, конфликтуют.
- **CREATE-008 — редактор и скрытость.** Созданная страница не публикуется и не попадает в публичную навигацию; redirect открывает её живой owner draft. Сохранение текста использует уже принятый простой REF-4 путь.
- **CREATE-009 — preview.** Подсказка URL остаётся read-only, ничего не резервирует и не публикует; ручной URL обязателен, если безопасная подсказка невозможна. Ошибка сохраняет введённые значения без секретов.
- **CREATE-010 — совместимость.** Существующий legacy `tree_create` receipt направляется в старый exact replay; cross-action receipt конфликтует. Rename/reorder/move не меняются. Publish/URL change/delete и REF-Q004 закрыты.

## Проверка

Focused command/HTTP/fault/concurrency, затем весь `content`, затем `media_library + page_versions`. После — независимое review, read-only main DB/login и остановка `foundation-test`. Production, VPS и старый сайт не затрагивать.
