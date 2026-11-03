# DEV-15: сохранён второй тестовый корпус

2026-11-02, D-380/D-383, первая часть WB15-004. DEV-15 около92%, этап8 около28%. Архивирование принято отдельно от будущих регрессий кандидата.

## Фактически выполнено

Первый inspect остановился до подключения helper к БД: ModuleNotFoundError, catalogMutationAttempted=false, intent/receipt отсутствовали. Причина подтверждена эффективным Compose: init не монтировал /trust. Для metadata-probe добавлен только readonly mount проверенного исходника; исходный FAIL сохранён, исправленный ResumePreflight прошёл отдельное code-review.

В исправленном прогоне неверный OID и активная UNIT-сессия дали ожидаемые отказы. Каталог и полное состояние до/после отрицательных проверок совпали. Созданная контроллером сессия отменена только по своему PID/PGAPPNAME/query и завершена.

После закрытия новых подключений helper повторно снял readonly hash через уже открытое собственное подключение, сверил его с intent, закрыл подключение и выполнил RENAME. DROP/flush/table reset не выполнялись.

| Объект | Результат |
|---|---|
| Первый архив test_estakada_trust_cal_7e145c49 | OID16387, прежний raw SHA289e7b… и старая квитанция без изменений |
| Второй архив test_estakada_trust_cap_32563 | Сохранён прежний OID32563 и все данные |
| Новая test_estakada_trust | Новый OID52766, проверена пустота до init, postgres-owned marker |
| MAIN estakada_trust | Прежние данные/Head9/epoch2/v2dfdf4021… |

Второй архив содержит1000FINAL операций/4096адресов/1024tombstones/1policy/4credentials, Head2002/epoch1, logical30419077/reserve0. Полный raw SHA `19166edecd58c58befe979e3bc07881da92de3a8e97459ed34cce0da237d8f6a`; v2 `116bb54a5d5d8cc5aa2ff6a4b593c51202aece6accff2421c47b525b9cc4c6b7`; schema `4fb7464026b738b4bc9cfd1dd23657d5e0425c7b3f859e1d9a9ddb97495d4de7`.

Новая UNIT имеет marker `ESTAKADA-DEV15-CAPACITY:cdeb944a-b44c-4df2-ac8d-810db7b942db`. Это служебный nonce, не пароль. Роль migrator/runtime не владеет БД и не может подменить marker. Оба архива закрыты для подключений и недоступны обычным ролям.

## Подтверждение и сохранность

Тело успешного archive ACK не использовалось до отдельного recover-read. Recover вернул то же состояние без повторного RENAME/CREATE; затем исходный ACK сопоставлен с recover. Это контролируемое непрочтение ответа, не модель реальной потери пакетов.

Verify до signed receipt и до init подтвердил принадлежность новой UNIT. После подписанного receipt выполнен прежний init, затем повторная полная verify цепочки. Старые attempts, FAIL, receipt и frozen source не переписаны. Source30/config без расхождений, final stopped0/disabled.

Независимое result-review положительное: проверены четыре HMAC и связи с parent FAIL/intent/старой квитанцией/capacity B, SHA результата и receipt, данные/OID/hash/marker/закрытость/Stop. SHA отчёта `4513d8514975a2d3ba2a1f3fbdf11aacd1116df1bd56601d895fa29984fc6476`; SHA archive-capacity.json `e96cef8da74fad43b624feefcdd1ab8ff08304fcd7dd6a0998d98d467deaefe1`.

CPA15-001–004 подтверждены в выполненной области. Частичные аварийные состояния/unknown fresh и будущий preview не испытывались этим прогоном. Обычный Tests guard остаётся закрытым; его нельзя обходить ради запуска на новой UNIT. Следующий шаг — отдельный review закрытого preview-controller с полным archive verifier до/после регрессий и собственным source/evidence. WB15-004 целиком, WB15-005, MAIN activation/native/DEV-29 ещё не завершены. Старый сайт и VPS не затронуты.
