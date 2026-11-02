# DEV-15 — локальный допуск записи и проверки отказов

2026-11-02, D-376. Локальный срез допуска записи/fault/recovery выполнен; полный DEV-15 и производственный допуск не завершены. DEV-15 около85%, этап8 около28% (8/29 основных DEV готовы локально, задачи разного размера).

## Сохранность прежнего набора (WP15-001)

Независимое ревью разрешило один отрицательный active-session запуск, затем ArchiveUnit, Stop, Start с disabled, unit и Stop. Выявленный до запуска недостаток finally исправлен: cleanup допускает все контейнеры с точными метками своего проекта, preflight остаётся DB-only.

Отрицательная проверка фактически PASS: `ARCHIVE_HAS_ACTIVE_SESSION`, тот же OID/имя БД, allowConnections=true, generation121, operations60, policies15360, tombstones0. Проверена отмена только собственного PID/application_name/UNIT. Архив не создавался, контейнеры остановлены. Свидетельство: work/dev15-write-20261102/archive-guard-report.json, SHA инструмента bcd1e5bf31a57969bcce14126e19d8cede15639d05f09bf5f03de0ac48fc7e7b.

Затем ArchiveUnit фактически PASS: прежняя БД переименована в `test_estakada_trust_cal_7e145c49`, OID16387 сохранён, полный измеренный SHA строк до/после совпал: `289e7b0f88c6add3e2ecebc4aa361eb62a0672ba3184c12812f87e7d766fb8d0`. Состав60/15360 и head121 сохранены; подключения к архиву закрыты, DROP не выполнялся. Новый UNIT OID32563 создан в том же кластере. Подписанная квитанция — work/dev15-20261102/runtime/archive-unit.json. После действия Stop выполнен.

Windows PowerShell5.1 отказал запуску обёртки до выполнения скрипта из-за ExecutionPolicy; cleanup-обёртка также не запускалась. Настройки Windows не менялись. Последующие действия выполнены напрямую существующим Node-инструментом, которому эта обёртка делегирует ArchiveUnit/Start/Tests/Stop; ветка ACL/Prepare не вызывалась. Это диагностический отказ способа запуска, а не неудавшаяся операция архивации.

## Новая реализация и unit

Подготовлены закрытый HMAC permit и additive0002 с неизменяемой recovery-квитанцией; исходная0001 сохранена. Допуск ограничивается одним планом с фиксированными IDs/fingerprints/source/schema/evidence/runtime/config/resource attestation. Общий профиль по умолчанию disabled.

Новый набор **62 unit/integration PASS за46.410с** на source `19c9c69d07936495b4fdda7d315668a3f41b77f07f665c34bcfc401ecdda31f7`. Run `f8f08573-512f-4881-99e1-1c6b55f1bdc6`: Start с disabled → независимая проверка сохранённого архива → Tests на новом UNIT → Stop. БД peak102195200B, OOM0; наблюдаемый общий бюджет295016212B. Старые20 unit и калибровка не подменяют этот запуск.

## Реальные локальные fault-проверки — PASS

После отдельного положительного code/QA gate выполнен один native run с hostSHA `9018ce3a6bca4bee371540ae695d5b1a8ace092c9a1eece6a28375141aefd3eb` и probeSHA `24f1794fde8598bbea67c128f6d42033a4cb861af16e880815ac2378e31c6f5d`, на том же product source. Проверено15 групп:

- Disabled и изменение разрешённого тела действительно запрещают запись.
- Полный HTTPS POST отправлен, заголовки получены, тело ответа не прочитано; SQL/status подтвердили commit. Точный повтор со старым CAS вернул прежнюю квитанцию без дубля.
- Реальный API restart сменил PID и сохранил полный state digest/квитанцию.
- Собственный PostgreSQL получил KILL; пока он выключен, запрос вернул503/TRUST_UNAVAILABLE. После старта того же контейнера/тома digest совпал. Это container crash, не физическое отключение питания.
- Fence увеличил epoch до2 и отозвал старый writer. Точный повтор fence не меняет состояние. Старый фактический secret со свежим epoch прошёл whitelist и получил авторитетный403/CREDENTIAL_REVOKED.
- Activate без reconciliation прошёл permit whitelist и получил409/RECOVERY_PRECONDITION_FAILED; FROZEN и digest сохранились.
- Прежний API остановлен/исключён, создан новый контейнер/runtime, загружен новый конфиг. Подписанное proof связывает настоящий old/new ID, полный head/state digest и конфиг. Activate и его exact replay успешны; новый writer пишет, прежний по-прежнему запрещён.
- Прежние terminal/pending запреты и tombstone сохранены; source/config drift0, проверка отсутствия сырых ключей и синтетических operation/plan IDs в текущих service logs пройдена.

Итог MAIN: та же incarnation, generation0→9, writerEpoch1→2, ACTIVE;4 операции,3 route rules,1 tombstone,2 immutable recovery receipts. Фактический тестовый permit ограничен **6 operation IDs и3 action IDs**, ceiling16/4 не расширен. Общий неограниченный профиль не открывался. В конце test branch disabled, active permit очищен, данные/история/ключи сохранены; внутренний и независимый внешний Stop прошли.

Квота: logical37841B/reserved16708B; наблюдаемый бюджет296217958B при плановых2ГиБ, без утверждения hard filesystem quota. Согласованные Docker caps896МиБ/1.25CPU сохранены. Последние измерения после restart/recreate: API memory.peak87703552B, DB27054080B, ingress10022912B, OOM counters0. Эти пики относятся к последним процессным/cgroup периодам и **не являются максимумом за весь fault-run**. Новых пакетов/образов/лимитов нет.

Приватно до отправки сохранены точный план/новый ключ/начальные credentials, каждый actual request intent и оба полных signed permit; публичные receipts связывают точные bytes SHA. Секреты не выводились в stdout/Git. Get-Acl через WindowsPowerShell5.1/-Command сначала проверил30 созданных к тому моменту private файлов, затем все44 после окончания прогона: доступ только owner/SYSTEM. Это не изменение ExecutionPolicy. Оба сохранённых envelope повторно сверены по bytes SHA с публичными receipts; активный файл допуска содержит `{}`, Status подтвердил0 контейнеров/stopped/disabled.

Свидетельства: work/dev15-write-20261102/native-write-report.json, native-review-gate.json, permit-initial-receipt.json, permit-rotation-receipt.json, exclusion-evidence.json, native-resource-evidence.json, native-budget.json.

После native Stop отдельно выполнен разрешённый readonly archive verify: DB-only512МиБ + прежний init helper256МиБ, тот же signed receipt и pinned helper. Полное совпадение OID/counts/head/rowsSHA с исходным архивом подтверждено после реального DB KILL. Никаких unit/flush/rename/DROP; затем внутренний и внешний Stop PASS. Свидетельство: work/dev15-write-20261102/postfault-archive-report.json. Итоговое независимое result/doc review фиксируется в dev15-write-review.md.

Native-протокол: fullPOST→получены заголовки→тело намеренно не читается→независимый SQL/status→exact replay; API restart; KILL собственного контейнера PostgreSQL и возврат того же тома; fence/старый реальный secret со свежим epoch; отказ activate без reconciliation; новая private-конфигурация/проверенное исключение прежнего API/новый writer. Никаких команд старому сайту/VPS.

Уточнение последовательности rotation: replacement API создаётся с новым runtime и выбранной веткой local-test-permit, но старый permit не проходит runtime/config binding и запись закрыта. После установления настоящего ID новый API останавливается; permit записывается прямым изменением того же файла/inode, затем запускается тот же контейнер с теми же ENV/ID. Смена ENV после подписи вызвала бы пересоздание и недействительный ID; этого не делаем. Ingress пересоздаётся для актуального upstream. Не использовать atomic replace файла при сохранении старого bind.

Полный APP reconciliation, consumer gate, физическая независимость TRUST, его собственное восстановление, размещение/стоимость и production здесь не проверены. workflowComplete остаётся false. Архив/ключи/БД сохраняются; секреты и private evidence в Git не добавляются.
