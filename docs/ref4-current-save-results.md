# REF-4 — простой current-source save страниц

Дата: 2026-11-05.
Решение: D-607.
Среда: локальный изолированный `foundation-test`; production, VPS и старый сайт не затрагивались.
Ревью: независимое code review — `APPROVED`.

## Граница инкремента

На простой путь переключено только сохранение страницы при условиях `action=save`, `source=current`, без draft, restore stage и rebase. Owner draft, stage restore, ручные версии и Stable продолжают переходно использовать прежние сервисы.

Новый current-save:

- повторно проверяет роль, PageGrant, `UserProfile.generation` и editor session;
- требует точный current/base и typed owner snapshot либо employee patch только разрешённых полей;
- выполняет media preflight вне транзакции и повторно проверяет evidence под блокировками;
- одной транзакцией создаёт automatic `PageRevision`, переключает current, обновляет ordinary/current usages, применяет Stable-aware лимит 10 и записывает audit;
- не создаёт новый универсальный `OperationReceipt`;
- при повторе уже применённого нового запроса возвращает безопасный base conflict без второй revision;
- до переключения проверяет существующий receipt, поэтому исторический fingerprinted replay сохраняется.

Переходно новая `PageRevision` ещё получает legacy `IdentityReservation` через модель. Старые receipts, identities, stages, pins, модели и код не удаляются до REF-Q004.

## Фактическая инвентаризация перед изменением

| Объект | Локальная test-БД |
|---|---:|
| Page | 6 |
| PageRevision | initial 6, automatic 16 |
| PageContentState | 6 |
| RevisionProtection | 0 |
| OwnerDraft | 1 |
| RestoreStage | consumed 3, held 0 |
| VersionBasePin | owner_draft 1 |
| OperationReceipt | 396 |
| IdentityReservation | 765 |
| Payload hashes | все валидны |

После тестов эти агрегаты не изменились.

## Проверки

- focused simple commands + HTTP routing: 4/4 PASS;
- полный переходный draft/restore HTTP-набор вместе с simple commands: 21/21 PASS;
- полный current-save HTTP-набор вместе с simple commands: 19/19 PASS;
- media/embedded rollback, missing-file repeat и реальная two-PG Save/cleanup concurrency: 5/5 PASS;
- owner и employee save, protected fields, denied field, audit rollback, current CAS;
- Stable остаётся вне ordinary limit, сохраняются 10 ordinary;
- существующий owner draft и его base pin сохраняются после current-save;
- old fingerprinted receipt replay сохраняется, новый receipt отсутствует;
- при параллельном cleanup PostgreSQL lock наблюдался фактически, cleanup отказан, физические файлы целы;
- `/manage/login/`: HTTP 200.

## Точка продолжения

Текущий общий этап — REF-05/REF-4. Следующий ограниченный инкремент — упрощение owner draft без изменения restore/manual/Stable. REF-Q004 остаётся закрыт.
