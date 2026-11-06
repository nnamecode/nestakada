# REF-05K — результат simple create

Дата: 2026-11-06.
Решение: D-625.
Статус: завершено, независимое review `APPROVED`, findings нет.
Среда: локальный изолированный `foundation-test`; production, VPS и старый сайт не затрагивались.

## Что изменено

- owner create подписывает page/operation UUID, kind, parent и локальные parent/sibling `xmin` stamps;
- одна transaction создаёт hidden Page, точный PRIMARY route, initial revision/metadata/current state, owner draft+pin и один `TREE_CREATE` audit;
- URL проходит существующие new-target/scanner/private validators, ORM и UNIQUE без переписывания;
- заранее подписанный Page UUID служит natural result key для concurrent/lost-response replay;
- replay доказывается точными Page/PRIMARY, immutable initial revision, state и атомарным audit, без зависимости от изменяемого draft или переходного pin;
- новая команда не создаёт `OperationReceipt` и отдельную `tree_page` IdentityReservation;
- две существующие identity rows initial PageRevision/OwnerDraft пока сохраняются как schema-invariant до REF-Q004;
- preview остаётся read-only, созданная страница скрыта и открывается в живом owner draft;
- существующий legacy receipt направляется в старый exact replay.

## Проверки

Первый focused-прогон выявил одну общую ошибку пяти subtests: replay после редактирования draft зависел от уже удаляемого простым REF-4 `VersionBasePin`. Зависимость replay от draft/pin удалена; immutable evidence сохранено. Точечный повтор 1/1 PASS.

- simple/HTTP/legacy creation: 33/33 PASS, 55.044 с;
- полный `content`: 110/110 PASS, 110.787 с;
- `media_library + page_versions`: 96/96 PASS, 135.004 с;
- relation measurement: `OperationReceipt` delta 0, version identity delta соответствует двум существующим immutable record types;
- `git diff --check`: PASS; только штатные предупреждения LF→CRLF;
- независимое review: `APPROVED`, CREATE-001–010 подтверждены, findings нет.

Read-only main test DB совпала с D-623: pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner-draft pins 1, receipts 396, identities 765, payload hashes valid. `/manage/login/` — HTTP 200.

## Следующий шаг

Текущий общий этап — REF-05/REF-5. Следующий ограниченный инкремент REF-05L — publish/hide и автоматическая навигация, начиная с приёмочного плана. URL change, delete и удаление legacy-кода не начинать; REF-Q004 закрыт.
