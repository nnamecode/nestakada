# REF-4 — manual, Stable и ordinary revision delete

Дата: 2026-11-05.
Решение: D-615.
Среда: локальный изолированный `foundation-test`; production, VPS и старый сайт не затрагивались.
Ревью: повторное независимое code/test review — `APPROVED`.

## Результат

На простые PostgreSQL-транзакции без новых `OperationReceipt` переключены:

- создание manual revision из точного server-side current;
- изменение name/comment/manual date только с metadata generation CAS;
- назначение Stable после актуального просмотра;
- снятие Stable с повторным текущим паролем и locked password-hash recheck;
- отдельное подтверждённое удаление ordinary revision.

Manual operation UUID становится UUID создаваемой revision: двойной конкурентный POST физически не создаёт вторую строку. Stable и delete повторно проверяют signed stamp/composition и защищают current, Stable, pins, draft bases и media usages. Demote применяет лимит 10, не удаляя current или удерживаемые основы. Физические media files этими действиями не удаляются.

Существующие legacy receipts всех пяти действий продолжают точный replay. UUID существующего receipt нельзя переиспользовать для другого action. Старые таблицы, строки и код не удалялись; REF-Q004 закрыт.

## Проверки

- исправленный real concurrent manual double-submit: 1/1 PASS;
- полный `page_versions`: 57/57 PASS, 72.343 с, exit 0;
- media/embedded/final-media/real PostgreSQL concurrency: 52/52 PASS, 232.757 с, exit 0;
- metadata CAS сохраняет payload/current/Stable;
- stale/tampered view, composition, stamp, generation и password-hash change отклоняются атомарно;
- employee Stable denial создаёт только bounded security audit;
- limit10 сохраняет current, pin и draft base;
- current/Stable/pinned/draft-base revisions отдельно не удаляются;
- audit fault откатывает metadata, demote и delete;
- реальные usages проходят ordinary→Stable→ordinary→removed, physical manifests неизменны;
- legacy replay metadata/Stable/demote/delete и cross-action consumed UUID проверены;
- main test DB: pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner-draft pins 1, receipts 396, identities 765, payload hashes valid;
- `/manage/login/`: HTTP 200;
- повторный независимый review: `APPROVED`, открытых findings нет.

## Точка продолжения

REF-3 и функциональный REF-4 завершены. Текущий общий этап — REF-05; следующий ограниченный инкремент REF-05H начинает REF-5 simple DEV-29 с приёмочного плана переименования страницы. Точный URL, публикация, навигация, права и audit должны сохраниться; старый код и данные не удалять до REF-Q004.
