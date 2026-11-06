# REF-05N — результат подтверждённого удаления страницы

Дата: 2026-11-06.
Решения: D-630–D-634.
Статус: завершено, независимое review `APPROVED`, открытых замечаний нет.
Среда: локальный изолированный `foundation-test`; production, VPS и старый сайт не затрагивались.

## Что изменено

- только `nesadmin` с актуальными generation/editor-session, CSRF, повторным текущим паролем и точным вводом названия/PRIMARY URL может удалить страницу;
- удаляется только leaf Page: любой существующий или поздно добавленный ребёнок закрывает операцию;
- signed confirmation связывает actor/generation/Page/operation и locked состав Page/routes/history/Stable/draft/stages/pins/grants/media home/usages;
- одна transaction удаляет Page, все её Route и всю историю, включая Stable, но сохраняет Asset, AssetFile, MediaFolder, чужие/shared/retained usages, audit, receipts и identities;
- смена password hash между внешней и locked-проверкой, stale/ABA Page и каждого PRIMARY/ALIAS/REDIRECT, новая revision, concurrency, rollback и lost response закрыты;
- повтор после commit безопасно подтверждает исчезновение того же UUID и не затрагивает новую страницу с прежним URL;
- новые OperationReceipt, IdentityReservation, tombstone или TRUST state не создаются.

## Проверки

- reviewer-добавления: 2/2 PASS;
- итоговый focused delete/admin tree/route models: 39/39 PASS за 19.509 с;
- полный `content`: 137/137 PASS за 154.017 с;
- неизменный соседний `media_library + page_versions`: 96/96 PASS за 134.077 с;
- `makemigrations --check --dry-run`: `No changes detected`;
- `git diff --check`: PASS, только штатные предупреждения LF→CRLF;
- независимое review: `APPROVED`, DEL-001–010 подтверждены, findings нет;
- финальный frozen run: `1a93152f-4970-4bd3-a167-2cd0275dc35b`.

Read-only main test DB совпала с D-629: pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner-draft pins 1, receipts 396, identities 765, invalid hashes 0. `/manage/login/` — HTTP 200.

## Следующий шаг

REF-5 функционально завершён. Следующий этап плана — REF-6, начиная с отдельного ограниченного инкремента и приёмочных сценариев. Удаление legacy-кода остаётся закрыто до REF-Q004.
