# DEV-15: локальный политический переход и точный повтор

## Текущий результат после D-390

Пауза DEV15-AD-RESUME-001 снята владельцем. Все 193 сохранённые SHA сверены; исправление прошло независимое code-review, 13 VM guard-проверок и AST четырёх встроенных Python-команд. Node controller — `5ba972d21ad1f05347a1a57f1eea86e95fce180adc73bf4620e95dde518f12d4`, guard-test — `86380e819df90c2264bbb51e2ba76cdb7025cd2e0b088ec099416def756269cb`; Python operator ee36… и продуктовый source 014efc… не менялись. Старые FAIL/gates/снимки сохранены.

Исправленный Prepare `80ec2fda-8dcb-4866-8333-c19a7ae80d26` — **PASS**. Реальная read-only проверка MAIN: OID16384, Head9/epoch2, 4 операции / 3 адреса / 1 tombstone / 2 recovery / 0 policy, 4 credential; full-state-v2 `dfdf4021db5dba1b807699b548e4370488fb3582e9c87734206f8f91ee3c6066`. Исторические ссылки — 3. Бизнес-состояние не менялось.

Оба архива прочитаны до и после: исходные OID/raw rows/v2 совпали, доступ снова закрыт; итоговый archive-proof SHA `a041996bf250e01a666260819848f0e16859ba4ee98295cf958d9db82dd46d14`. Catalog ALLOW_CONNECTIONS временно менялся для этих проверок, чтение строк было read-only; процедура не называется полностью read-only. Все три helper завершились exit0/OOMfalse; наблюдаемый максимум cgroup завершённого helper — 138407936 байт при лимите 268435456. Это отдельный период измерения, не сумма с прежними resource/TLS-прогонами.

Точный подписанный intent и baseline сохранены приватно до отправки. Подготовленный state SHA `1f2cd418060710d7ae14e143fbb94d760d6323a75c3304bc273c9541ddc13a3e`. На выходе именно Prepare было NOT_SENT, 0 контейнеров, disabled/пустой permit; ACLPrepared321/642 PASS. Этот результат и code-gate следующих Activate/точного Retry приняты независимым ревью.

### Фактические Activate и Retry

Activate `da1018a2-c983-4eb7-8b95-382af7873349` — **PASS, COMMITTED_VALIDATED, replay:false**. Тот же сохранённый intent создал одну append-only policy epoch1; Head9 перешёл в Head10, writer epoch2 сохранился. Прежние credentials/operations/routes/tombstone/recovery, pin и миграции совпали по полному защищённому digest; допустимый delta Head и charge новой policy проверен.

Retry `52978298-f8f0-47e2-b7e2-960b14c5121b` — **PASS, replay:true**. Вернулась та же квитанция ядра, полное состояние до/после Retry одинаково: policy1, Head10/epoch2, state-v2 `60e067e7a8efa143a2d21e3ee31b7bc42e5fc85c34560a53bb3e3b98554c0bc1`. Внешние подписанные записи Activate/Retry имеют разные phase/runId и собственные SHA; неизменность относится к вложенной квитанции перехода, а не к байтам этих разных отчётов.

| Отчёт | SHA-256 |
| --- | --- |
| Prepare 80ec2fda | `1311a3c98bfecad0c5b1db9c6674b200d12c55bbdfb0f51058fe249567820223` |
| Activate da1018a2 | `07ab9ff66510f923240c0a0b9cf16c6f14f8ea32bdfa3480f1c2b774dd07451b` |
| Retry 52978298 | `b7ce11a9e468d54db4417c65b05407a40c15fb4fccad31969e5f2ba663da5489` |

Каждая фаза сохранила оба архива, все helpers завершились exit0/OOMfalse. Наибольший наблюдаемый cgroup peak завершённого helper среди этих фаз — 150953984 байта при лимите 268435456; это максимум отдельных наблюдений, не общий одновременный пик среды. Финальный read-only сборщик проверил HMAC/связи intent/prepared-state/квитанций/сырых выходов и независимо пересчитал формулу Head digest. Сохранены оба прежних FAIL. Итог в `work/dev15-admission-20261102/final-result.json`, SHA `e102802ba61030558670a30deb109909b80193e6e9eda212343387a9619d026c`. Независимое итоговое result-review — **APPROVED**: проверены 9 сырых helper outputs, 27 HMAC/связей и 6 архивных proof, неизменность квитанции ядра/состояния при Retry, source/config/63 inputs и финальные ACL/закрытая запись. Это приёмка первого policy-перехода; весь DEV-15, HTTP-допуск и native-проверки не закрыты.

Текущее состояние: 0 контейнеров, writer disabled/permit пустой, manifest/source/config и все 63 provenance-входа неизменны; полный состав host/frozen source — прежние 30 Python-файлов. ACLFinal395/790 PASS, только владелец/SYSTEM, reparse0. Подготовленная политика не является run lease: HTTP-запись, native RP15-013–019, APP/DEV-29 и production здесь не включались. Следующая отдельная фаза — container-bound lease/exclusion и проверки сбоев после его включения по AD15-006/007. DEV-15 около 96%, этап 8 около 28%; старый сайт/VPS не затронуты.

Ниже — историческая пауза до D-390, а не текущий статус.

2026-11-02, D-389, AD15-001–008. DEV-15 около 96%, этап 8 около 28%. Статус — **Приостановлено владельцу, DEV15-AD-RESUME-001**.

Сохранены 77 существовавших Git-изменений перед работой. Подготовлены два операторских инструмента и отдельный тестовый helper UNKNOWN/terminal lost response/partial POST. Независимое ревью плана и кода выполнено; замечания и исправления перечислены в dev15-local-admission-review.md. Node syntax и Python AST принятых файлов проверены. Native helper не исполнялся и не доказывает полный RP15-013–015.

| Попытка | Результат | Реальная граница |
| --- | --- | --- |
| Prepare 9973c5b9 | FAIL, ADMIT_HOST_FAILED / NOT_SENT | Read-only config preflight не увидел migrate без tools-profile. БД/helper/активация не запускались. Причина подтверждена, узкая правка принята независимым ревью. |
| Prepare 0642d6c5 | FAIL, ADMIT_UNEXPECTED_SERVICE / NOT_SENT | Запущена и затем остановлена только собственная БД. Короткий ID от docker ps сравнивался с полным inspect.Id; helper не создавался. Finally повторил ту же проверку, поэтому работа приостановлена по AGENTS.md. |

Третьей попытки не было. Политика, ActivationIntent, lease, HTTP-запись и native-проверки не выполнялись; business state не подгонялся. Новый SQL-снимок MAIN/архивов не получен: archivesPreserved:false и ARCHIVE_PRESERVATION_NOT_PROVEN сохранены как реальные ограничения, а не переименованы в PASS. Архивные helpers не запускались и ALLOW_CONNECTIONS не меняли.

Последний отчёт подтверждает 0 собственных контейнеров, disabled/пустой permit, прежний manifest, source/config и 63 provenance-входа без изменений. Windows PowerShell 5.1 ACL до и после — 283 объекта / 566 правил, только владелец/SYSTEM, reparse 0. История EV15-пакета и все FAIL сохранены; ключи и приватные данные в Git не добавлялись. Старый сайт/VPS не затронуты; push не выполнялся.

Текущий Node SHA `220befbcd15c54eb5be797f1b046b91dd80d04b124ed16ba0c00650987fcffec`, Python operator SHA `ee36f319b737e0116629217721b018c9d0d841c33a5d0674aaf9eb26e983fcbc`, native helper SHA `2fa27d057f983750e69336458f613daf26219d4c14776a2148484bf3580e456b`. Принятое code-review не заменяет проваленный runtime результат. Исправление ID и finally ещё не реализовано.

План возобновления: work/dev15-admission-20261102/resume-plan.md. Сначала полные ID и отсутствие эквивалентного повтора раннего отказа, независимое ревью; затем один Prepare, реальная сохранность, тот же intent и операторский переход. Весь DEV-15 не завершён, к DEV-29 не переходить.
