# DEV07-N — результаты реальных сетевых проверок

2026-11-01, D-342. Ограниченный NET07-001–006 завершён локально, независимое ревью без блокеров. DEV-07 около94%, этап8 около20%.80 существующих изменённых/новых файлов сохранены в work/dev07-network-20261101/before; прежние результаты DEV07-F остаются отдельными cohort.

## Контракт до кода

- dev07-network-checks.md SHA62f670444bb74595b07322fd0699247e477cd54c7a7ea68bcc61d2d8eefc8c7f: реальные FR07-004/005 и границы тестового транспорта.
- Независимые dev07-network-scenarios.md SHA00ecda521350feb06d9ea156153e792a0b2ac6a5612bb509587573381ee36f1f: первый cohort NET07-001–006; поздний auth/полный Save с неизвестным ответом NET07-007/008 отдельно pending.
- dev07-network-observer-contract.md SHA004d28798bfedb02a0714d2fcecd86391087684ea1717f69e6cf27aa527032cf: пассивные actual seams, fixed32records/64KiB snapshot, корреляция без authority, реальные timer/duplicateFD flags, отсутствие raw input/credentials в evidence.
- Все три pre-code контракта прошли независимое ревью. Код продукта не менялся; фикстура772b02… сохраняется неизменной.

## Подготовленный тестовый профиль

Существующий Django runserver в отдельном ignored overlay работает с threads; точный большой editor location Nginx получил proxy_read_timeout150s. Реальный app body deadline120s и child384MiBAS/10CPU/20wall, один heavy slot, app768MiB/1CPU/pids128/read-only/non-root/CSP остаются прежними. Профиль испытаний не является решением о production сервере или изменением основной foundation-конфигурации. Альтернатива прямого app socket не доказывала бы весь ingress путь; условия объяснены владельцу до применения.

Observer4 ignored files source-reviewed: network_observer.py1ed961fd7ca0d3f49773633907d3def262248d18330ad5e92b484f63ec5efe92; settingsfa4de262…; compose603e879e…; nginxa5a6f737…. Exact Nginx delta только150s, AST2 PASS. Первоначальный Copy-Item denied не повторялся; nginx создан через уже работающий literal AddFile. Единственная лишняя пустая строка исправлена по точному diff, затем delta assertion PASS. Зависимые действия теперь выполняются только после проверки успешного exit.

Фактический preflight: исходный product source05c24609a2605d5fdf4352977f27ee883a543c9c0655a05c3f7946fc42796417 неизменён, image782f53c4…; actual command без --nothreading,805306368B/1CPU/128pids/readOnly. Nginx -T прошёл; observer ready=true/fault=false/installCount1/sequence1/records0 с совпадающим nonce и600/UID10001/nlink1. Артефакты work/dev07-network-20261101/{profile-first.json,nginx-effective-first.txt}; это readiness, не NET07 PASS.

## Исполнение

Первый actual NETWORK_6: **6/6 PASS**, exit0,27 traced requests из32, все завершены, observer sequence211/fault=false/installCount1. Product source05c24609a2605d5fdf4352977f27ee883a543c9c0655a05c3f7946fc42796417 и QA/config/foundation guards до/после равны. Новая оснастка: helper2d84521906ea413c7cb40f87b9653bc98d363af3a1be10930d1fb03baed6d691, probe79777019e2087322817e529fe1041127b96ced53df90a5eccc3d66a34607a193, host32c6b13a0af2b1c429ed778b72046ac3651240bbf26b70f7bc2e7d7e4bcde74b. Node2/ASThelper PASS; fixture772b02… не менялся. Артефакты: work/dev07-network-20261101/browser-first/host-report.json, socket-report.json и network-first.txt.

| ID | Фактический результат и граница |
|---|---|
| NET07-001 | Реальный Check и header-only visitor/foreign/invalid-CSRF early401/403; reader/child0 у недопущенных, content unchanged |
| NET07-002 / FR07-004 subset | Отдельные A/B connections: A actual partial read+flock, B check assigned employee/save owner/draft owner —503 EDITOR_BUSY до body/child. Обе domain advisory try-locks свободны, затем A200 и отдельный явный B success; один ожидаемый write/receipt |
| NET07-003 | Настоящий partial-then-complete Check200; последующий healthy200, timer joined/duplicateFD closed, no domain mutation. Это проверенная двухчастная передача, не вся latency матрица |
| NET07-004 / FR07-005 subset | Drip1byte/5s; **app408 EDITOR_BODY_TIMEOUT**, reader-start bracket120003/120002ms.8215B существенно меньше CL, dripFault=false; child0, expired=true, timerAlive=false/duplicateClosed=true/slotClosed=true, последующий healthy200. Лимит120 не патчился, proxy504 не засчитывался |
| NET07-005 / FR07-005 subset | Check8192/12203B, Save8192/13222B, draft8192/13378B оборваны до полного тела. Server400/outcomeBodyInvalid, child0/no mutation, timer/FD/slot закрыты, новые отдельные healthy действия проходят. Последний byte никогда не отправлялся; rollback после полного Save этим не обещается |
| NET07-006 | Native HTML RAM ввод пережил actual Busy; наблюдался один отказ без hidden POST, затем отдельный manual Check и явный Save — ровно одна версия с сохранённым вводом. CSP/inline-style/storage/pageerror invariants прошли, screenshots1280/390 сохранены |

Независимый рецензент лично сверил все27 observer rows, source/QA/container guards и финальный отчёт. Receipt/network oracle проверяет наличие токена, exact wire input hash/normalised result и принятие prepared proof реальными Save/draft. Это не независимый HMAC-пересчёт каждого A Check; crypto regressions остаются отдельным server207 cohort. Термин verified proof в исходном техническом предложении не расширяет фактическую область этих тестов.

CleanupClosed=true:0 live synthetic users/pages/versions/drafts/stages/pins/assets/files; SYSTEM route и permanent ledgers сохранены. PhysicalFiles пуст (фото не создавались), поэтому media corruption coverage не заявляется. Внешний watchdog180s и заранее заданное окно119..130s не заменяли app deadline. Ни таймер, ни child, ни reader results не подменялись. Ошибок suite/retry не было.

FR07-004/005 закрыты только в указанном subset. **Открыты** NET07-007 late auth/grant/session во время чтения, NET07-008 полностью отправленный Save+потерянный response/UNKNOWN/replay, все source/media/race сочетания, полная FD/temp/log-carrier матрица. Snapshot absence не выдаётся за отсутствие кратковременного temp-file; request close в проверенной форме не обещает все FIN/RST/network regimes. Этот threaded/proxy150 transport не принят за production profile; основная foundation-конфигурация не менялась. Далее — exact late-auth и UNKNOWN/replay сценарии по отдельному pre-code gate, затем оставшиеся DEV-07 функции/ресурсные матрицы.

Root подтвердил Stop exit0 и manifest.active=false; private files/volumes и source snapshots сохранены. Скриншот desktop просмотрен, mobile390 также сохранён. Diff-check PASS (generated bundle исключён как прежде; он в этой работе не менялся). Git не сбрасывался и push/commit не выполнялись. Старый сайт/VPS, новые программы/зависимости/порты и Telegram/production не использовались. Push только по сообщению владельца о конце смены.
