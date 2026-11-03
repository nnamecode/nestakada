# DEV-15: результат полных регрессий кандидата

2026-11-02, D-383, WB15-004, PC15-001–005. DEV-15 около92%, этап8 около28%.

После независимого code-review SHA `a31151f36c9a9504556e8fca424a1f11d0065351a0470ac2871df25a1e0e10f5` выполнен один положительный прогон отдельной копии. Предварительный missing-gate отказ сохранён отдельно и не создавал attempt/report. Bad signature/altered marker, аварийный timeout/reap и partial archive faults этим прогоном не испытывались.

В preview заменён только journal/consumer.py на SHA `15e6c9b25764eab698dac4e52f8cca804f4c339a271d83db521bdf0e8ee98d21`; остальные29файлов совпали с исходным frozen source. Новый source30 SHA `014efc288de0d32772fca15d63afbb0a4c23a9009ee6ef8bdc877cb1aa41c672`. До setup выполнены полные chain guards; suite count131 проверен до DBsetup, actual UNIT OID52766/роль/marker — после setup до test methods. Прежний source5fbc/131PASS154.169с не переименовывался в новые свидетельства.

Результат: **131/131 PASS за160.534с**, skipped0, exit0, полный execution168526мс. Это регрессии журнала TRUST, не полный e2e сайта и не доказательство TLS30с. Контейнер256МиБ/.5CPU/PIDs64/readonly, DB512МиБ/.5CPU, прежние образы/сети/тома. Лимит180с не повышался.

До начала, непосредственно перед setup и после удаления test-tool полный chain verifier вернул одинаковый report SHA `601f675e8969895c57ffa2e09eee6f07df0cd65c69225455bf4756725c6d4b71`: первый архив/OID16387, второй/OID32563 и MAIN неизменны; новая UNIT/OID52766 и marker прежние. Запись disabled, source/config drift0, Stop0, owned test-tool name/label0. Test-tool завершился сам, приватные inspect/logs сохранены до scoped rm без-v. Аварийный stop/reap остаётся проверкой кода, не фактически вызванной аварией.

Полные stdout/stderr/metadata/inspect остаются в ignored private/work. Отчёт work/dev15-corpus-20261102/candidate-test-report.json SHA `2df7b5435840cd87dd0c2714bc909b56a516bf3f212d3a5cd605bf29bfe63c3e`; подписанный attempt SHA `fdf6b259be79e550dccb76413bf1729a7a5fa33951e34f015e093073698c563e`; preview manifest SHA `dfabe77f3bac289e49fe124fd6a88f483f9de47721e45ddfe9af82c7bdbfa746`.

Независимое result-review положительное: HMAC/связи/gate/source/raw stdout/chain и cleanup проверены. Приватное raw execution168524мс и публичное168526мс сняты разными вызовами Date.now; разница2мс не влияет на131PASS. Peak памяти не измерен: к моменту диагностики test-tool уже завершился, inspect подтвердил exit0/OOMfalse. Лимит памяти не равен фактическому пику.

После принятия выполнен побайтный перенос consumer15e в локальный trust/journal/consumer.py с сохранением старого файла в ignored work. Все30локальных файлов совпали с preview, общий SHA014efc… тот же. Отдельный runtime после переноса не запускался, новый131PASS не приписывается интеграции. Артефакт candidate-integration.json связывает перенос с SHA принятого отчёта. Прежний runtime manifest/frozen source5fbc сохранён; следующий штатный Start создаст новый снимок. Рабочий допуск записи остаётся выключенным.

WB15-004 завершён в области сохранения второго корпуса, новых131регрессий и точного переноса кандидата; дополнительные fault-варианты плана явно не объявлены выполненными. WB15-005/fullTLS получает собственную цепочку чтения архива и source/evidence. Старый snapshot003FAIL не отменён, MAIN activation/native/DEV-29 не выполнены. Старый сайт/VPS не затронуты.
