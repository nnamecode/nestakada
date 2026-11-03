# DEV-15 — первый инкремент рабочего допуска

История первого инкремента. Последующее продолжение с рабочими Policy/lease/ActivationIntent и UNIT131PASS — dev15-runtime-implementation-results.md/review.md; перечисленный ниже прежний остаток не является текущим статусом этих новых изменений.

2026-11-02, этап 8, D-380, DEV15-CLOSE-01. Реализация согласованного профиля возобновлена после окончания смены. Это результат ограниченного инкремента схемы и полной сверки, не завершение CLOSE-01 или RP15-001–020. DEV-15 примерно 85–90%, этап 8 около 28% (8 из 29 основных задач, разного размера).

## Изменения

- Additive `0003_admission_policy`: одна таблица AdmissionPolicy, уникальные UUID/epoch/policy digest/action ID, форма predecessor/первого legacy seal, версия сверки 2, учтённый размер 1–32768 байт, DB trigger против UPDATE/DELETE. Миграции 0001/0002 не изменены. Миграция не создаёт политику и не активирует запись.
- Schema fingerprint включает новую таблицу, constraints/indexes/triggers и ledger 0003; физический учёт включает её индексы/TOAST. Bootstrap отклоняет непустую историю допусков.
- Старая ветка trial проверяет наличие AdmissionPolicy под Head lock до повторной проверки membership/мутации. Наличие политики закрывает возврат к старому допуску; самостоятельного рабочего validator пока нет.
- Новый `state_v2` берёт общий Head lock, проверяет актуальность переданного Head, хеширует все persistent поля Head и шести остальных таблиц. Формат 2 имеет отдельный domain, length-prefixed canonical frames, явные таблицы/поля/число строк; UUID нормализуются. Cursor chunk=1, ограничены count и размер одной канонической строки. Verifier остаётся внутри SHA. Старый recovery v1 пока не переключён на этот модуль.

## Независимое ревью до испытаний

Исполнитель схемы — dev15_policy; digest/интеграция — координатор. Независимый readonly-рецензент dev15_review исходники не менял и тесты не запускал. Блокеров ограниченного disabled schema/UNIT-инкремента не найдено.

RP15-REV-001: первоначальные тесты не доказывали чувствительность полного digest к каждому persistent полю. До общего прогона добавлена mixed fixture со всеми таблицами, payload/phases/историей: контролируемая подмена каждого поля фактического cursor row меняет итоговый digest; Head проверяется через подмену locked row, verifier — реальным UPDATE. Неизменяемые DB guards для этого не отключаются. Рецензент проверил правку и закрыл замечание в ограниченной области.

## Испытания и сохранность

Docker Desktop после перерыва не был запущен; после запуска с необходимым доступом отвечает 29.9.2. Windows/пакеты/системные настройки не изменялись. TRUST исходно stopped/disabled/0 running. Исходная Git-копия чистая на ecd13d8; исходники перед испытаниями дополнительно сохранены в ignored work/dev15-runtime-20261102/foundation-source.

Source первого прогона: 27 Python-файлов, SHA `db52f96cba5f6d641c138257c97e4cbf5c48b4a57fd9a85c96b1b5011ca0fbd5`, run `c056f6ee-b017-467a-858a-5f60d36e76b9`. Guarded Start прошёл с disabled writes. После миграции MAIN сохраняет Head9/epoch2/ACTIVE, 4 операции/3 адреса/1 tombstone/2 recovery receipts, AdmissionPolicy=0. Прежний полный digest v1 совпадает: `64dd0a52dc0732cbc004d09b21d87f17a82d08a0cd885fa9d57f0656bf47f2c4`. Новый v2: `dfdf4021db5dba1b807699b548e4370488fb3582e9c87734206f8f91ee3c6066`. Это сверка сохранности, не рабочий recovery proof или разрешение HTML.

Первый общий UNIT-прогон на этом source: **109 тестов за 100.333 с, FAIL 1 / PASS 108**. Старый тест physical calibration ожидал ровно шесть relations; фактический учёт вернул семь после добавления AdmissionPolicy. Двенадцать новых проверок прошли. Исходный FAIL сохранён приватно: failure-c27de65a-5b58-4615-a544-f6fb11d98728.txt. Это первый отказ с установленной причиной, не основание повторять неизменённый запуск.

Исправлено только устаревшее утверждение в journal/tests.py: теперь требуется точный набор семи согласованных таблиц. Остальные assertions сохранены. Независимый рецензент проверил правку, блокеров повтора нет.

**Повтор: 109/109 PASS за 93.727 с** — 97 прежних и 12 новых тестов. Окончательный source27 SHA `6e79d19f6a37c76b1fcd48311a0061c7c60489811f5bbb1cf6d4d33b51652634`, run `c39a9456-3cbb-4bd9-aa75-cf9951e27b1e`. Первый FAIL сохраняется отдельно. Evidence: runtime/unit-result-c39a9456-3cbb-4bd9-aa75-cf9951e27b1e.json и unit-budget того же run в ignored work/dev15-20261102; сырые логи приватны. Старый архив проверен штатным signed guard перед каждым UNIT-прогоном; он не мигрировался и не очищался.

После повторного UNIT отдельный readonly MAIN-probe подтвердил те же full v1/v2 SHA, Head9/epoch2 и counts4/3/1/2, AdmissionPolicy0. Evidence: work/dev15-runtime-20261102/main-after-unit.json. DB cgroup peak111058944/536870912 байт, OOM/kill0, observed task/data/log-reservation budget279601713 байт. Это DB-пик данного запуска и наблюдаемый бюджет, не whole-helper peak/capacity PASS/физическая дисковая квота. Relations суммарно352256байт, новая таблица с индексами49152байт; MAIN database8443583байт.

Итоговый Stop выполнен с сохранением данных; независимое result-review положительное, блокеров ограниченного инкремента нет. Status: stopped, active=false, 0 running containers; writeMode=disabled, permit пустой. Policy/lease/ActivationIntent не выпускались. Финальная сверка 27 host/frozen исходников и конфигурации даёт drift0; evidence — work/dev15-runtime-20261102/final-source-evidence.json. Это завершение первого инкремента, не всей задачи DEV-15.

## Что остаётся

До завершения CLOSE-01 требуются рабочие closed Policy/Run lease/ActivationIntent, операторская атомарная активация и exact retry/latest chain, серверные count/charge/16-row проверки, интеграция v2 в recovery с явным отклонением v1 proof. Затем RP15 capacity/native/fault/transport/preservation по принятому конечному плану. Новая схема/тесты не выдаются за эти PASS.

Старые corpus/ключи/pin/история сохраняются. Старые одноразовые write/Calibrate не повторяются. Старый сайт/VPS/DEV-29/production не затронуты; push в этой смене не выполнялся.
