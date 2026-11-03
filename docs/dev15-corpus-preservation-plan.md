# DEV-15: сохранить второй корпус перед регрессиями

2026-11-02, D-380, WB15-004. DEV-15 около 92%, этап 8 около 28%. Это исполнение предусмотренной процедуры сохранения второго корпуса в прежнем локальном TRUST, не новый компонент/зависимость/ресурс. Старый сайт, VPS, MAIN activation и DEV-29 не затрагиваются.

## Что сохраняется

Первый архив test_estakada_trust_cal_7e145c49 и его signed archive-unit.json неизменны. Нынешний UNIT test_estakada_trust/OID32563 содержит1000FINAL/4096routes/1024tombs/1policy, Head2002/epoch1, logical30419077/reserve0; полный v2 SHA116bb54a5d5d8cc5aa2ff6a4b593c51202aece6accff2421c47b525b9cc4c6b7. Его данные сохраняются RENAME в фиксированный test_estakada_trust_cap_32563, без DROP/flush/копирования таблиц. Новый пустой UNIT получает другой OID и marker с UUID точного операторского intent.

Старые attempts/FAIL/source snapshots/receipts/pin не удаляются и не переписываются. Для второго архива создаются отдельные signed intent/receipt. Старый freshUnitOid32563 становится историческим указателем на второй архив; проверка цепочки требует этот же OID у второго архива и новый distinct OID у disposable UNIT. Нельзя переписать старую квитанцию ради совпадения.

## Порядок

1. До изменений сохранить исходники и SHA/inventory. Подготовить новый закрытый helper и controller, независимое code-review и синтаксическая проверка до исполнения. Фиксированные MAIN/UNIT/два архива; никаких произвольных имён/SQL/секретов в выводе.
2. При disabled записи и остановленном front проверить source30/старые квитанции/ownership/images/caps. Новый helper использует существующий init-role/CA и только локальную DB-сеть; инструмент256МиБ/.5CPU + DB512МиБ/.5CPU внутри прежнего896МиБ/1.25CPU. Данные читаются через READ ONLY/REPEATABLE READ; raw-row SHA включает все столбцы8таблиц и миграции, v2 вычисляется теми же frame/metadata из сохранённого journal.state_v2 без подключения Django к БД. Verifier/payload участвуют только в хеше.
3. Получить inspect-состояние, сверить v2 с capacity B, MAIN v2/Head9/epoch2, первый архив с его подписанным raw-row SHA. Перед первой мутацией сохранить HMAC intent с UUID/source/helper/controller/gate/полным reference и SHA родителей.
4. До успешного archive проверить отказ неверного reference/OID и активной UNIT-сессии. При отказе original UNIT/name/OID/данные/allow_connections неизменны, второй архив отсутствует. Сессию-hold создаёт controller на фиксированном test UNIT, отменяет только собственный PGAPPNAME/PID/query; не завершать чужие сессии.
5. При отсутствии сессий закрыть UNIT для подключений, повторно проверить отсутствие сессий, RENAME, отозвать CONNECT у PUBLIC/runtime/migrator, установить readonly default. Проверить тот же OID/raw/v2/schema. Для чтения архива допускается краткое открытие только bootstrap-superuser; обычные роли по-прежнему без CONNECT. В finally вернуть ALLOW_CONNECTIONS false.
6. Создать новый пустой UNIT под прежним именем, поставить marker точного intent, проверить новый distinct OID/пустоту. CREATE DATABASE и marker не атомарны: неизвестный новый UNIT без marker не признавать своим и не удалять. Частичный отказ сохраняет архив/intent, закрывает известные архивы и блокирует Tests; автоматического повтора нет.
7. Отдельный recover-read после намеренно непрочитанного успешного archive ACK подтверждает завершённое состояние по исходному intent, marker, OID/raw/v2/legacy/MAIN; не повторяет RENAME/CREATE. Это потеря тела ответа проверяющим, не имитация сетевой потери. Только после независимого доказательства завершения записать signed receipt, затем init нового пустого UNIT и verify цепочки. Stop и result-review.
8. Существующий Tests guard не открывать одним наличием файла. Перед любым очистительным тестом требуются HMAC receipt, сохранность обоих архивов, closed ACL/ALLOW и точный новый UNIT OID/marker. Старый archive helper/receipt сохраняются; chain-aware verifier проверяет первый архив по тем же raw-row правилам и историческую связь OID, а не подменяет old freshUnitOid текущим.
9. Полный пакет кандидата готовить как отдельный preview из30сохранённых файлов, заменяя только consumer.py на SHA15e6c9… с проверкой каждого файла. Новые регрессии запускаются только на новом disposable UNIT через прежний migrator, без MAIN/runtime записи. Старые131PASS не присваиваются preview source. До интеграции — собственный test-result/source/evidence и независимое ревью. Отдельный WB15-005 затем проверяет полный TLS; source/policy запреты не ослаблять.

## Приёмочные наблюдения

CPA15-001: malformed reference/неверный OID отказывают до мутации и RENAME. CPA15-002: активная сессия даёт ожидаемый отказ с неизменностью UNIT и отсутствием второго архива, holder scoped cancelled/reaped. CPA15-003: archive сохраняет OID32563/raw/v2/schema и первый архив/MAIN, новый UNIT distinct/пуст.

CPA15-004: recover-read по тому же intent после непрочитанного ACK возвращает то же состояние, не создаёт третью БД. CPA15-005: signed receipt/цепочка/closed permissions проверяются до и после каждого будущего теста; wrong/missing receipt оставляет guard закрытым. CPA15-006: частичный отказ/незнакомый fresh UNIT не стирается и не считается успешным.

CPA15-007: preview diff ровно consumer.py, остальные29файлов идентичны frozen; тесты получают новый source SHA. CPA15-008: полные регрессии, source/config/privacy/ресурсы/архивы/MAIN до/после, Stop0/disabled и независимое review. Выполнение отмечать только по факту; негативные/fault/preview проверки не считать выполненными по наличию этого плана.

## Исправление предварительного запуска

Первый inspect завершился ModuleNotFoundError на REFERENCE_VALIDATION: catalogMutationAttempted=false/journalRowWrites=false, intent/receipt не создавались, Stop0. Фактический Compose с включённым tools-профилем подтвердил: init имеет working_dir /trust, но его отдельный список volumes не содержит /trust. Это не отказ сохранности/RENAME; исходный FAIL сохранён.

Только для вызова metadata-helper добавлен archive-tool.compose.yaml с readonly bind уже проверенного TRUST_SOURCE→/trust. Обычный init не меняется, новых секретов, ресурсов, сетей или программ нет. Проверены эффективные256МиБ/.5CPU/PIDs64. Один ResumePreflight/resume-001 допускается после code-review: он требует исходный FAIL до мутаций, отсутствие intent/receipt, закрытый стенд; пишет отдельные отчёт/gate/raw. Подписанный intent связывает новый запуск с SHA исходного FAIL. Старые свидетельства не заменяются.

Marker читается через shobj_description для shared database objects по [PostgreSQL18](https://www.postgresql.org/docs/18/functions-info.html#FUNCTIONS-INFO-COMMENT-TABLE). Empty ACL нормализуется до aclexplode; эти исправления проверены до первого runtime и не изменяют права.
