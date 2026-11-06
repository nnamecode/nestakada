# REF-4 — простые owner draft

Дата: 2026-11-05.
Решение: D-608.
Среда: локальный изолированный `foundation-test`; production, VPS и старый сайт не затрагивались.
Ревью: повторное независимое code review — `APPROVED`.

## Граница инкремента

На простые команды переключены создание, обновление, rebase и отмена owner draft. Draft publish, restore-stage, ручные версии и Stable пока используют переходную реализацию.

Новый путь:

- допускает только владельца и повторно проверяет generation/editor session;
- проверяет точные draft id, revision, payload hash, base и current;
- выполняет media preflight вне транзакции и повторно проверяет evidence под блокировками;
- одной транзакцией создаёт или обновляет draft, синхронизирует media usages и пишет audit;
- при отмене одной транзакцией удаляет draft usages, старый pin и draft с audit;
- не создаёт новые `OperationReceipt` и `VersionBasePin`;
- лениво удаляет существующий legacy owner-draft pin при update, rebase или cancel;
- при повторе новой операции возвращает безопасный конфликт без второго изменения.

До нового маршрута проверяется существующий receipt. Поэтому старые `save_draft`, `rebase_draft` и `cancel_draft` продолжают replay с прежним результатом и без повторной записи.

## Проверки

- simple commands, полный draft/restore HTTP и реальная PostgreSQL concurrency: 30/30 PASS;
- create/update/rebase/cancel без нового receipt и pin;
- exact draft CAS, stale revision/base/hash и session/generation отказы;
- media evidence/usages и audit-fault rollback;
- legacy save/rebase HTTP replay сохраняет `result_id`, `draftBasis`, `baseRevisionId`, state и audit;
- legacy cancel receipt replay сохраняется;
- повтор новой операции не меняет draft второй раз;
- read-only сверка основной test-БД после тестов совпала с исходной: pages 6, revisions 22, states 6, Stable 0, drafts 1, consumed/held stages 3/0, owner-draft pins 1, receipts 396, identities 765, все payload hashes валидны;
- `/manage/login/`: HTTP 200;
- независимое повторное ревью: `APPROVED`, открытых замечаний нет.

## Точка продолжения

Текущий общий этап — REF-05/REF-4. Следующий ограниченный инкремент — упрощение draft publish и прямого restore без изменения manual/Stable. Старые модели, данные и код не удаляются до отдельного REF-Q004.
