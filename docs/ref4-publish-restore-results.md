# REF-4 — публикация owner draft и прямое восстановление

Дата: 2026-11-05.
Решение: D-613.
Среда: локальный изолированный `foundation-test`; production, VPS и старый сайт не затрагивались.
Ревью: повторное независимое code/test review — `APPROVED`.

## Граница инкремента

Публикация owner draft переключена на простую PostgreSQL-транзакцию без нового `OperationReceipt`. Новый UI восстановления больше не создаёт `RestoreStage`: после preview и явного подтверждения исторический источник повторно проверяется и одной транзакцией создаёт новую automatic revision, переключает current, синхронизирует media usages и пишет audit.

Сохранены:

- owner/employee права, generation и editor session;
- точные current/source/draft CAS-проверки и безопасный stale-отказ;
- текущий isolated normalizer и запрет несовместимого содержимого;
- media preflight вне транзакции и evidence под блокировками;
- защищённые layout, embedded media, H1 и URL при employee restore;
- Stable-aware pruning, атомарный audit и полный rollback;
- применение существующих held stages и точный replay старых receipts.

Новый publish/restore не создаёт receipt, stage или pin. Старые модели, данные и код не удалялись: REF-Q004 закрыт.

## Проверки

- исходные focused-сценарии: 9/9 PASS;
- финальный transition suite: 53/53 PASS, 123.120 с, exit 0;
- финальный media/embedded/final-media/real PostgreSQL concurrency suite: 51/51 PASS, 229.447 с, exit 0;
- owner HTTP direct restore создаёт ровно одну revision без stage/receipt/pin;
- current, grant и AuthSession stale не меняют business state; permission deny создаёт только одно ограниченное безопасное событие;
- отказ locked media evidence после реального preflight оставляет state, audit и manifests неизменными;
- employee restore меняет только разрешённый текст и сохраняет layout/embedded/H1;
- legacy held-stage consume и receipt replay остаются покрыты;
- read-only main test DB: pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner-draft pins 1, receipts 396, identities 765, все payload hashes валидны;
- `/manage/login/`: HTTP 200;
- независимый рецензент подтвердил закрытие прежнего P2, новых замечаний нет.

## Точка продолжения

Текущий общий этап — REF-05/REF-4. Следующий ограниченный инкремент REF-05G — сначала записать приёмочные сценарии для упрощения manual/Stable операций, сохранив owner-only права, Stable вне лимита и запрет её отдельного удаления. Старый код, таблицы и файлы не удалять до отдельного REF-Q004.
