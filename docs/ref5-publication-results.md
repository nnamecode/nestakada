# REF-05L — результат simple publish/hide

Дата: 2026-11-06.
Решения: D-626, D-627.
Статус: завершено, повторное независимое review `APPROVED`, findings нет.
Среда: локальный изолированный `foundation-test`; production, VPS и старый сайт не затрагивались.

## Что изменено

- владелец подтверждает отдельную команду publish либо hide; сотрудник и анонимный пользователь не получают доступ;
- token связывает actor/generation, страницу, operation, действие, locked PostgreSQL `xmin` страницы, точный PRIMARY route и current state, а также ID/hash текущей revision;
- одна transaction меняет только `Page.is_published` и добавляет один `TREE_PUBLISH` либо `TREE_HIDE` audit;
- новые `OperationReceipt`, `IdentityReservation`, intent, TRUST policy, APP cohort, EDGE gate и отдельное состояние навигации не создаются;
- `resolve_target` и динамический `public_tree` сразу отражают флаг; скрытие родителя не меняет флаг ребёнка, опубликованный ребёнок поднимается к ближайшему опубликованному предку;
- stale, ABA страницы/PRIMARY/current, concurrent submit, no-op, подмена action/page/token и повреждённый payload закрываются до изменения;
- при потере HTTP-ответа после реального commit форма 503 сохраняет только operation/token и CSRF: точный повтор конфликтует без второго audit или ledger;
- URL, содержимое, revisions/Stable/drafts/media, HTML-сборка/fallback и удаление не изменяются.

## Проверки

Первый focused-прогон выявил одну общую SQL-причину: при joined query системный `xmin` состояния требовал квалификации именем таблицы. После исправления продуктовые сценарии прошли; два последующих точечных сбоя относились только к тесту — неверному имени synthetic employee и неполному HTML-фрагменту в assertion. Каждый повтор выполнялся после нового свидетельства и отдельного исправления, одинаковая ошибка не повторялась.

Первое независимое review вернуло P2: название lost-response теста не соответствовало фактической обычной повторной отправке. Добавлен настоящий commit→новое DB connection→synthetic `DatabaseError`→HTTP 503→exact retry 409. Повторное review — `APPROVED`, новых findings нет.

- настоящий PUB-008 lost response: 1/1 PASS за 1.653 с;
- итоговый focused publication+admin tree: 19/19 PASS за 15.720 с;
- полный `content`: 119/119 PASS за 142.683 с;
- соседний `media_library + page_versions`: 96/96 PASS за 158.995 с;
- `makemigrations --check --dry-run`: `No changes detected`;
- `git diff --check`: PASS, только штатные предупреждения LF→CRLF;
- frozen run итогового content-снимка: `d6824da7-f024-4c83-818b-ca40ab2d4da2`.

Read-only main test DB совпала с D-625: pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner-draft pins 1, receipts 396, identities 765, payload hashes valid. `/manage/login/` — HTTP 200.

## Следующий шаг

Текущий общий этап — REF-05/REF-5. Следующий ограниченный инкремент REF-05M — изменение URL с сохранением точных legacy URL, начиная с отдельного приёмочного плана. Подтверждённое удаление страницы, HTML build/fallback и удаление legacy-кода не начаты; REF-Q004 закрыт.
