# REF-05J — результат simple move

Дата: 2026-11-06.
Решение: D-623.
Статус: завершено, независимое review `APPROVED`, findings нет.
Среда: локальный изолированный `foundation-test`; production, VPS и старый сайт не затрагивались.

## Что изменено

- move подписывает actor, generation, page, operation, исходный parent, destination и три точных снимка;
- locked PostgreSQL `xmin` исходной/целевой sibling-групп и destination→root ancestry закрывает stale, ABA и concurrent double-submit;
- цикл проверяется сервером по фактической locked ancestry, включая перенос в себя/потомка;
- одна transaction меняет только parent/positions затронутых страниц, нормализует обе группы до `0..N-1` и пишет один `TREE_MOVE` audit;
- root и same-parent поддержаны, no-op и чужой destination/before отклоняются до записи;
- несвязанная ветка не делает форму устаревшей;
- новые `OperationReceipt`/`IdentityReservation` не создаются; lost response/repeat конфликтует;
- существующий legacy receipt направляется в прежний exact replay; rename/reorder не менялись.

## Проверки

- simple rename/reorder/move + legacy tree: 47/47 PASS, 54.166 с, с первой попытки;
- полный `content`: 102/102 PASS, 102.421 с;
- `media_library + page_versions`: 96/96 PASS, 137.758 с;
- `git diff --check`: PASS; только штатные предупреждения LF→CRLF;
- независимое review: `APPROVED`, MOVE-001–010 подтверждены, findings нет.

Read-only main test DB совпала с D-621: pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner-draft pins 1, receipts 396, identities 765, payload hashes valid. `/manage/login/` — HTTP 200.

## Следующий шаг

Текущий общий этап — REF-05/REF-5. Следующий ограниченный инкремент REF-05K — создание страницы и PRIMARY route, начиная с приёмочного плана. Publish/hide, URL change, delete и удаление legacy-кода не начинать; REF-Q004 закрыт.
