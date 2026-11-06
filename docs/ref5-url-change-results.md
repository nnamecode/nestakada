# REF-05M — результат simple URL change

Дата: 2026-11-06.
Решения: D-628, D-629.
Статус: завершено, независимое review `APPROVED`, findings нет.
Среда: локальный изолированный `foundation-test`; production, VPS и старый сайт не затрагивались.

## Что изменено

- только `nesadmin` с актуальными generation/editor-session и CSRF может открыть и применить отдельную команду URL;
- защищённый imported PRIMARY (`is_legacy=True`) отклоняется сервисом и не получает ссылку действия в дереве;
- token связывает actor/generation, Page/operation и locked PostgreSQL `xmin` Page+exact PRIMARY;
- новый target проходит существующий `Route.clean`: exact/new path, scanner/private namespace и глобальная UNIQUE-занятость всеми Route kind;
- одна transaction меняет target существующего PRIMARY, создаёт non-legacy REDIRECT со старого exact target на ту же Page и пишет один `TREE_URL_CHANGE` audit;
- повторные A→B→C не создают цепочки: существующие redirect той же Page вычисляют destination сразу через current PRIMARY;
- child URL, aliases, publication flag, revisions/Stable/drafts/media и прочие страницы не меняются;
- новые OperationReceipt/IdentityReservation/TRUST intents/state machine не создаются;
- stale/ABA/concurrency/no-op, audit rollback и настоящий lost-response 503→409 закрыты.

## Проверки

Первый focused-прогон дал 38/39 PASS. Единственная ошибка: `/manage/` правильно отклонялся моделью как private namespace, но сервис не преобразовывал этот `ValidationError` в закрытый пользовательский `400`. Добавлен preflight тем же `Route.clean()` до mutation; единственный повтор при изменившемся условии прошёл.

- итоговый focused URL change + admin tree + route models: 39/39 PASS за 18.215 с;
- полный `content`: 128/128 PASS за 138.850 с;
- соседний `media_library + page_versions`: 96/96 PASS за 134.251 с;
- `makemigrations --check --dry-run`: `No changes detected`;
- `git diff --check`: PASS, только штатные предупреждения LF→CRLF;
- независимое review: `APPROVED`, URLC-001–010 подтверждены, findings нет;
- frozen run: `76ee75ac-eb82-46ed-a080-d3c9815f3785`.

Read-only main test DB совпала с D-627: pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner-draft pins 1, receipts 396, identities 765, payload hashes valid. `/manage/login/` — HTTP 200.

## Следующий шаг

Текущий общий этап — REF-05/REF-5. Следующий и последний функциональный инкремент REF-05N — подтверждённое удаление страницы и всей её истории по D-047/D-048, начиная с короткого приёмочного плана опасной операции. HTML build/fallback и удаление legacy-кода не начаты; REF-Q004 закрыт.
