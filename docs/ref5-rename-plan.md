# REF-5 — простое переименование страницы

Дата: 2026-11-05. Статус: завершено по D-617; независимое review `APPROVED`.
Связанные требования: D-023, D-242, D-248, D-250, REF-AC-003, REF-AC-008, REF-AC-012, D-616.

## Граница

- Переключить только owner rename на простую PostgreSQL-транзакцию без нового `OperationReceipt` и `IdentityReservation`.
- Изменять только `Page.name`. Не менять URL/routes, kind, parent, sibling positions, publication, H1, SEO, revisions, drafts, Stable или media.
- Существующий `tree_rename` receipt до нового маршрута продолжает точный replay старой командой.
- Move/reorder, create/publish/hide/change URL/delete и удаление legacy-кода не входят.

## Приёмочные сценарии до кода

| ID | Сценарий | Обязательный результат |
|---|---|---|
| RENAME-001 | `nesadmin` открывает форму и задаёт допустимое новое название | Меняется только `Page.name`; одна bounded audit-запись `TREE_RENAME`; receipt/identity не создаются |
| RENAME-002 | Проверить URL, H1/SEO, kind, parent/order, publication, revisions/Stable/draft/media до и после | Все перечисленные данные идентичны; URL не пересчитывается из названия |
| RENAME-003 | Сотрудник/аноним/CSRF-bypass/лишнее поле/невалидное имя | 401/403/400; Page, routes, history, audit business-событий и legacy ledgers не меняются кроме bounded security denial |
| RENAME-004 | Страница переименована/перемещена/изменена после preview или пережила ABA | Signed PostgreSQL row-version CAS отклоняет старую форму 409 без частичной записи |
| RENAME-005 | Два одновременных POST одной формы | Ровно один меняет имя и пишет audit, второй получает конфликт; receipt/identity не создаются |
| RENAME-006 | Audit/DB failure после проверки | Изменение имени полностью откатывается; URL/tree/history неизменны |
| RENAME-007 | Повтор нового POST после успешной записи или потерянного HTTP-ответа | Новая mutation/audit не создаётся; ответ конфликтный, актуальное имя видно после refresh |
| RENAME-008 | POST с существующим legacy `tree_rename` receipt и точными прежними полями | Старый путь возвращает replay без новой mutation; чужой/cross-action consumed UUID отклоняется |

## Технический контур

- GET подписывает actor, generation, page UUID, operation UUID и exact row stamp. Stamp включает PostgreSQL `xmin` и безопасный digest текущих page/primary-route полей; `xmin` меняется при любом UPDATE и закрывает ABA без новой таблицы или generation-column.
- POST повторно проверяет owner generation/editor session, подпись, operation UUID и отсутствие любого существующего receipt/identity, блокирует страницу, сравнивает row stamp, валидирует name и выполняет `Page.save()` + audit в одной transaction.
- Новый operation UUID не хранится. Идемпотентность обеспечивают row CAS и запрет no-op; результат после сомнительного transport failure проверяется актуальным GET.

## Проверка

Узкие command/HTTP/concurrency/fault тесты RENAME-001–008; затем существующие content tree/create/media/page_versions регрессии, независимое review, read-only main DB и login smoke. Production, VPS и старый сайт не затрагивать.
