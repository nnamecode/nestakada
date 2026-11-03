# DEV-15: полный TLS-снимок после исправления worker

2026-11-02, WB15-005/RP15-011, продолжение D-380/D-383 по поручению владельца «проверяй полный TLS-снимок под нагрузкой и проводи независимое ревью». DEV-15 около92%, этап8 около28%. Это проверки до исполнения, не PASS.

Все53текущих изменённых файла сохранены с SHA в ignored work/dev15-wb005-20261102/before. Предыдущие FAIL/attempt/receipt/source и131previewPASS сохраняются. Ни старый сайт, ни VPS не входят в работу.

## Границы

Тот же корпус1000FINAL/4096route/1024tomb теперь находится под именем test_estakada_trust_cap_32563, прежний OID32563. Политика внутри него исторически подписана для test_estakada_trust/source5fbc; она не переписывается. Тестовый read-only профиль отдельно связывает эти исторические данные с новым кодом source30/014efc… и его принятым131previewPASS. Это не runtime-write admission и не разрешение обойти validator записи.

Используются прежние три образа, сети и предел896МиБ/1.25CPU, без новых программ/томов/портов. Нагрузка — один полный максимально заполненный снимок, не поток произвольного числа клиентов. Клиент работает в API-контейнере и делит его256МиБ/.5CPU. Общие30с, request6с,54запроса/52страницы/5120items, pacing0.11с и no-retry сохраняются. SQL-only и прежний диагностическийPASS не заменяют этот прогон.

## Проверки

WT15-001: до запуска проверить source30/014efc…, consumer15e,131preview report/подписанныйattempt/точный перенос, обе архивные квитанции/intent/HMAC/связи, старые source30/5fbc и checkpoint capacityB. Одноразовый подписанный attempt и codegate привязывают новые инструменты, source и исторический snapshot. Обычный Tests остаётся закрытым; новой очистки UNIT нет.

WT15-002: при остановленном front полный chain verifier на историческом frozen source сверяет оба архива/MAIN и новуюUNIT52766/marker. Test-only ACL helper открывает только точный capacity-архив/OID32563. До открытия существует подписанный attempt с закрытой архивной квитанцией и ожидаемым catalog false/on; отсутствие сессий и фактический catalog проверяет helper. Первое краткое открытие нужно bootstrap для чтения ACL, обычные роли по-прежнему лишеныCONNECT; helper снова закрывает архив. Полученный ACL baseline и отдельный подписанный intent сохраняются до первогоGRANT, cleanup вооружён заранее. Первый архив и новаяUNIT не получают новых прав. Default readonly базы сохраняется; если для rowlock требуется writable transaction, допускается только сессионная настройка тестового API/helper в рамках прежнего минимального head(id) разрешения. Нельзя расширять SQL-права ради запуска.

WT15-003: temporary runtime получает прежний минимум CONNECT/USAGE, SELECT четырёх таблиц, UPDATE(id) только Head для SELECT FOR UPDATE. Реальные SSL/rollback-rowlock и42501 для UPDATE(mode)/INSERT обязательны. Остальные права, включаяMAINTAIN/sequence, закрыты. Архив не переименовывается/не очищается; effective ACL после испытания равен baseline, ALLOW_CONNECTIONS сноваfalse, default readonlyon. При unknown state отказ и отдельная ошибка восстановления, без удаления данных.

WT15-004: test-only API command проверяет actual archive name/OID/runtime-role/disabled/source014e до bind. Известная migration-check42501 проверяется явно, затем пропускается только повторный check_migrations этого тестового command. MAIN-команда прежняя. Readiness — socket/TLS безHTTP. Точные images/networks/mounts/caps/disabled проверены до нагрузки.

WT15-005: один реальный read_snapshot использует неизменныеHTTPSReader/worker/30/6. Проверяются exact Head2002/epoch1,54успешных запроса/52страницы/5120items и wholeSHA5933ad…; boundedtrace сохраняется и приFAIL. Historical source5fbc и actual source014e выводятся раздельно, sourceMatchesPolicy=true для нового кода не выдумывается. Не меняются сохранённаяpolicy и runtime-writevalidator.

WT15-006: сырые exit/error/signal/stdout/stderr сохраняются приватно до разбора, tmpfs-файлы извлекаются bounded O_NOFOLLOW reader до удаления API. CPU/memory/OOM/ID измеряются до/после; недоступная метрика не считаетсянулём. Нельзя запускать дополнительный256МиБ tool при работающем front. При host-timeout сначала остановить точный API и его дочерние процессы, затем запускать helper восстановления, не допуская overlap ресурсов.

WT15-007: даже приFAIL остановить front, восстановить effective ACL/закрытость архива, повторить полный chain verify на frozen5fbc, проверить workspace source/config. При успехе вернуть обычный MAIN API, проверить новыйID/actualDB/runtime-role/Head9/epoch2/disabled, затемStop0. Старые исходы не заменяются; независимые code/result review обязательны. MAIN activation/native/DEV-29/production не входят.

Независимое review плана принято. Уточнения codegate: baseline/intent отдельно фиксируют datallowconn=false и database default_transaction_read_only=on; ALTER DATABASE/ROLE SET readonly=off запрещён. Сессионный off только у точного тестового API/helper для rowlock. Перед открытием архива и после остановки API до восстановления/закрытия проверяются0сессий в этой БД. Новыеhelper/probe жёстко фиксируют и имяcap_32563, иOID32563. Read-binding замкнуто связывает HMAC старого архива/source5fbc с новымsource014efc/consumer15e/подписаннымpreviewattempt и SHA принятого131report; одного логического sourceMatchesPolicy недостаточно. Это охрана реализации прежнего тестового профиля, не новый ownergate.

Один новый измерительный прогон после codegate. Отказ сохраняется для диагностики; автоматических повторов доPASS и повышения лимитов нет. Остаточные проверкиRP15 и воспроизводимость описываются отдельно по результату, без объявления всегоDEV-15 готовым.
