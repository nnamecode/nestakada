# REF-05I — результат simple reorder

Дата: 2026-11-05.
Решение: D-621.
Статус: завершено, независимое review `APPROVED`, findings нет.
Среда: локальный изолированный `foundation-test`; production, VPS и старый сайт не затрагивались.

## Что изменено

- новый reorder подписывает actor, generation, page, operation, исходный parent и digest полного sibling-набора;
- locked PostgreSQL `xmin` каждого sibling закрывает stale, ABA и concurrent double-submit без новой schema/table;
- одна транзакция нормализует только `Page.position` siblings до `0..N-1` и пишет один `TREE_REORDER` audit;
- чужой parent, чужой/целевой `before`, tampered token и фактический no-op отклоняются до записи;
- изменение несвязанной ветки больше не делает локальную reorder-форму устаревшей;
- новые `OperationReceipt` и `IdentityReservation` не создаются; повтор после успеха/потерянного ответа конфликтует;
- существующий legacy receipt направляется в старый exact replay; rename и move не менялись.

## Проверки

Первый узкий прогон нашёл одну общую ошибку сборки кода: return `prepare_rename` был ошибочно расположен после новой функции, поэтому rename GET возвращал `None`. Return перенесён в `prepare_rename` по traceback; состояние изменилось, после чего один повтор прошёл.

- simple rename/reorder + legacy tree: 39/39 PASS, 44.772 с;
- полный `content`: 94/94 PASS, 92.270 с;
- `media_library + page_versions`: 96/96 PASS, 136.766 с;
- `git diff --check`: PASS; только штатные предупреждения LF→CRLF;
- независимое review: `APPROVED`, RORDER-001–009 подтверждены, findings нет.

Read-only main test DB совпала с D-617: pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner-draft pins 1, receipts 396, identities 765, payload hashes valid. `/manage/login/` — HTTP 200.

## Следующий шаг

Текущий общий этап — REF-05/REF-5. Следующий ограниченный инкремент REF-05J — сначала записать приёмочные сценарии простой `move`-команды: две sibling-группы, защита от циклов, stale/ABA/concurrency, атомарная нормализация и audit rollback без новых receipts/identity. Delete и удаление legacy-кода не начинать; REF-Q004 закрыт.
