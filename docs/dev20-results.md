# DEV-20 — результат локальной защиты от сканеров

2026-11-02. Основания: D-371/D-372, REQ-041/052/053/060, AC-041/052/060/OPS-009, dev20-proposal.md и SC20-001–012 из dev20-checks.md. DEV-20 завершён в согласованной локальной области: все7 HTTP-групп и95 unit/integration пройдены, итоговое независимое ревью положительное; локальный профиль допущен по D-372. Старый сайт/VPS не затронуты.

## Изменение

ScannerMiddleware первым отклоняет известные мусорные пути до тела, сессии, авторизации и SQL. Pure classifier используется и при проверке будущих публичных URL; исходные адреса не переписываются. Процессные счётчики имеют10 фиксированных ключей/ограниченную память, честно отмечают неполноту и сброс процесса. Они не заменяют будущую историю DEV-17/18/21.

Safe logging filter убирает только ожидаемые scanner404 из обоих Django logger. Неожиданные500/2xx, обычные404 и аудит сохраняются. Nginx ограничивает фактический IP20rps/burst60, общий поток50rps/burst100 и8 активных запросов;429 короткий/no-store/nodelay. Новые зоны3МиБ внутри прежних128МиБ. Прежние auth/body/editor caps сохранены; зависимости/образы/схема БД не добавлялись.

## Фактические проверки

Source238: `5b7e6d13e7e037eef31ccd8fd867ede5b995767d7fe9e2eb98f6e1adfba79dc3`. App image `782f53c4…`,85 package files verified, штатные local_http/main URLConf/Nginx без QA endpoints/settings overlay. Unit cohort `73c9f06a-780d-49ee-bcb8-0944ca79a529`.

- **95 tests PASS/20.052с:**20 новых request_guard и75 регрессий audit/content/accounts/foundation. SQL0 и попытки открытия соединения0 проверены отдельно;115MAP/316MED/543targets совместимы. Включены10тыс probe paths, окна/сaturation/contention/thread/fork и long-query/nonbrowser logging.
- **SC20-N01 PASS:**8 неполных запросов занимают active cap;8 location probes со второго фактического IP, начиная с девятого активного запроса, получают429/no-store. Обрыв освобождает допуск.
- **SC20-N02 PASS:** неполное тело закрыто через15028мс, наблюдаем EOF; последующий запрос проходит. Это interread timeout, не абсолютный срок slow-drip атаки.
- **SC20-N03 PASS:**90 сканов за253мс:65 коротких404/25 быстрых429. Подмена forwarded headers не создаёт новый IP-key; второй реальный source допускается.
- **SC20-N04 PASS:**61+61 запросов с двух source при concurrency≤6:121 scanner404/1 rate429, span425мс/start skew3мс. Ни один IP не превышал начальный burst61, active8 не исчерпан —429 доказывает общий rate cap. Отсутствие429 при медленном генераторе отдельно считалось бы неполным QA, не product PASS.
- **SC20-N05 PASS:**6 разных превышений прежних body caps→413, anonymous large-editor admission→401; настоящий owner login/editor Check/media работает, employee не читает owner draft, оригинал фото закрыт. Save не выполнялся.
- **SC20-N06 PASS:** при остановленной выделенной тестовой PostgreSQL авторизованное чтение→503,4 известных scanner paths→404/no-store без cookie. БД восстановлена; содержимое и файлы прежние.
- **SC20-N07 PASS:** авторизованное чтение настоящего редактора200 с marker `editor-initial-state` пересекается со90сканами на341мс. Сканы:65коротких404/25rate429; полезное чтение1144мс. После4с паузы повторное чтение200/marker за1110мс. Concurrency≤6, Save отсутствует, domain неизменен. Это отдельный mixed witness, не последовательный N05.

В scan-only окне модельные counts неизменны, structured process records0/canaryfalse. Сбор обоих Docker log потоков подтверждён отдельным настоящим ordinary404 positive control ДО scan окна. Counter exactness доказана в middleware framework, не фиктивным чтением счётчика из чужого CLI PID.

Первый native run `ba31eeed-2743-4818-a8cc-86739aaf7414`,6/6PASS, stderr0, nativeExit0/Stop0. App peak178941952B/805306368B, ingress10248192B/134217728B; OOM/max events0. CPU за130650мс: app28467367µs, ingress438851µs. Это whole-container scope с CLI helpers/наблюдением, не расход одного скана и не оценка мощности VPS.

Отдельный mixed run `6822dace-8e03-4308-b749-929f2f19a62f`, source cohort `80d37085-70b5-4822-aedc-754f709bc8b6`, тот же source238/5b7e6d13…. N07PASS/stderr0/mixedExit0/Stop0. App peak145641472B, ingress12853248B, CPU за42699мс:18584852µs/215534µs; OOM/max0. После Stop activefalse;238host/frozen SHA,4QA SHA и14исходных backup SHA сверены без расхождений. Ресурсные пределы и образы прежние.

## Матрица и границы

| Сценарии | Доказательство | Граница |
|---|---|---|
| SC20-001/002/003 |20 unit methods, real Django client/connection spies и SHA-mounted legacy CSV | Public positive200 по всем URL ещё DEV-08/29 |
| SC20-004/005 |10тыс paths, bounded counter state/threads/fork; native scan counts | Counters process-local; нет глобальной истории/Telegram |
| SC20-006/007 | Real LogRecord pipelines и native logs0/DB-down scanner404 | Production WSGI access logging проверяется при выборе runtime |
| SC20-008 | N03/N04 два настоящих source, forged-header negative control | Не5мин PERF-SCAN/не DDoS guarantee |
| SC20-009 | N01/N02 active/release/timeout, actual config fixed shared-zone sizes, pinned Nginx contract | Фактическое заполнение per-IP зоны множеством remote_addr не проводилось; many-source churn остаётся TEST-09 |
| SC20-010 |75 регрессий и N01/N05 inheritance/body/real auth/editor/media | Полный editor MAX был source-bound ранее; не объявляется заново весь набор на новом middleware |
| SC20-011 | N03/N04/N07 и resource evidence | Full10/50/100rps×5мин/mixed/VPS остаются TEST-09 |
| SC20-012 | Source/config/QA/images/caps guards, before/after retained domain и Stop0 | Положительное итоговое независимое ревью; локальный профиль допущен D-372 |

Сохранены Page versions core8/fmtA4/fmtB4/media3/foreign2/max1, Header/Footer по3 версии, current и system Route, файлы и owner draft. Не было reseed/reset/delete/Save. Все прежние изменения сохранены; Git push не выполнялся.

Private before/after/seed и сырые логи находятся только в ignored work. Проверенные evidence: `work/dev20-20261102/guard-first.txt`, `native-first/host-report.json`, `native-first/qa/` (точные3 QA файла первого запуска), `stop-after-native-first.txt`. SHA первого QA: fixture08e8c3f3…, probe883e5e9e…, host9da42644…; текущая смешанная проверка имеет собственный freeze и не переписывает первый результат.

Mixed evidence: `native-mixed-first/host-report.json`, `stop-after-mixed-first.txt`, `native-freeze.json` (fixture08e8c3f3…/основнойprobe883e5e9e…/mixedprobea9156ad8…/host50e12942…). Оба native отчёта содержат собственные source/config/QA hashes; это связанная проверка одного продукта, не один притворный монолитный запуск.
