# DEV-15 — допуск тестовой записи и fault/recovery: контракт до кода

2026-11-02, D-376 в пределах D-374. Это сценарии и техническое уточнение локального инкремента, не PASS. Ресурсы/образы/пакеты остаются прежними. Основной сайт, foundation, VPS и физический ARC-10 не затрагиваются.

## Граница допуска

Первый допуск предназначен только для заранее подготовленных синтетических HTTPS-проверок. Общий неограниченный persistent profile остаётся disabled. Закрытый readonly private permit подписывается HMAC-SHA256 существующим recovery-secret и связывает: имя локальной БД/инкарнацию, протокольную версию, полный SHA manifest исходников trust/, fingerprint применённых миграций/ограничений/триггеров, фактические unit/calibration/review evidence и согласованные caps. Не более16 заранее перечисленных operationId с точными credential/epoch/semantic phase fingerprints; expectedGeneration остаётся CAS-условием нового перехода, не частью semantic replay fingerprint. Отдельный короткий список recovery action IDs/fingerprints. ENV/параметр браузера или просто наличие JSON не разрешают запись.

Файл/caps/source/HMAC/доступный ID проверяются до SQL; identity/credential/epoch/schema и совпадение допуска повторно проверяются под Head lock. Чтения без permit сохраняются. Переход за пределы permit, подмена файла/фазы/кода/schema закрывают новую запись. Чужие запросы не могут выбрать путь permit, source или key. Подпись не заменяет свежесть БД и не разрешает rollback TRUST.

RAM/CPU/PID deployment связывается подписью и fingerprint конфигурации/фактического operator inspect. API до SQL читает собственные memory.max/cpu.max/pids.max; DB/ingress параметры проверяет издатель permit через принадлежащие этому стенду Docker containers. Сервер не заявляет, будто сам прочитал недоступный ему Docker socket/чужой cgroup.

TRUST_WRITE_PROFILE=disabled всегда запрещает запись. Значение local-test-permit лишь выбирает проверяющую ветку, без действительного permit прав нет. Это не ENV-переключатель общего разрешения. У permit максимум4 recovery action IDs, каждая квитанция до16КиБ; metadata учитывается в прежнем бюджете.

Первый permit выпускается при пустых MAIN Operation/RoutePolicy/RequestTombstone; следующие состояния содержат только operation/action IDs того же ограниченного test plan, проверяемые под Head lock. Обновление после rotation не расширяет общий набор IDs. Поэтому максимум16 сообщений по1МиБ и их стадий/правил ниже выбранного60-operation corpus; предельные4096refs и малые recovery receipts отдельно обосновываются/измеряются. Это ограничение испытания, не новое правило для будущих бизнес-операций. Само наличие прежней калибровки не разрешает общий профиль с10тыс операций.

## Сохранность и повторные unit

Исходная test_estakada_trust содержит сохранённый corpus60/15360/generation121 и не может быть flushed. Перед следующими unit — явная закрытая archive-команда: подлинный кластер/роль, исходные identity/counts/digest сверены с сохранённым report; нет активных сессий UNIT; **переименование** этой БД в фиксированное имя архива без DROP/перезаписи. Архив и его state проверяются после операции, сохраняется provenance receipt. Затем создаётся новая пустая БД с прежним точным UNIT именем в том же контейнере/бюджете. Tests разрешаются только при независимо проверенном сохранённом архиве; calibrationAttempted старого corpus не обнуляется. MAIN TRUST, его identity и ключи не сбрасываются. Процедура обратима, архив автоматически не чистится.

## Recovery только тестового writer

Локальные закрытые recovery-команды/endpoint используют существующую recovery-роль, HMAC permit и фиксированные action IDs. Additive миграция0002 может добавить минимальную immutable RecoveryReceipt в существующую TRUST PostgreSQL для точного повтора и выяснения неизвестного результата. Миграция0001/старые записи не переписываются. Квитанция не содержит raw keys/данных заявки; её размер/count ограничены permit и учитываются в прежнем служебном бюджете.

Fence атомарно отзывает прежний server-side credential, увеличивает writer_epoch/generation, переводит Head в FROZEN и сохраняет receipt. Точный повтор после lost ACK не увеличивает epoch ещё раз. Обычный writer не выполняет recovery и не получает свежий ключ из GET head.

Activate относится **только к изолированному synthetic TRUST writer**, не восстановлению APP/основной CMS. Требуются актуальная инкарнация/epoch/fence receipt, установленная новая private конфигурация credential и доказанная сверка фактических данных тестового журнала (head+полный согласованный digest/состав с независимым наблюдением), исключённый прежний API-процесс и новый загруженный config. Новый secret/id отличается от отозванного. Пока доказательство/конфигурация отсутствуют, Head остаётся FROZEN. Старые deny/pending/tombstone/terminal history не снимаются и не переписываются. Не выдавать этот тест за APP reconciliation, допуск HTML или полный внешний recovery TRUST.

Источник разрешения — локальный оператор/readonly permit, не произвольное поле proof=true от writer. Перезапись permit/credentials выполняется при остановленном API с сохранением прежней защищённой конфигурации; API и ingress пересоздаются последовательно, чтобы readonly bind не остался на старом inode и frontend не использовал прежний upstream. DBvolume/ключи TLS сохраняются.

Подписанная reconciliation включает exclusion: previousRuntimeId/previousContainerId/newRuntimeId/newContainerId/evidenceSha256. Предыдущий runtime связан с durable fence receipt, новый — с текущим API; пары различны. Издатель подписывает это только после реальной проверки остановки/исключения конкретного прежнего контейнера и загрузки нового config. Один новый UUID без такого operator evidence не является доказательством исключения.

## Приёмочные сценарии

| ID | Связи | Необходимое наблюдение |
|---|---|---|
| WP15-001 | SC15-001/016 | Archive guard до unit: исходный corpus действительно переименован/не уничтожен, count/digest/identity совпадают, новый UNIT пустой. Повтор/чужое имя/несовпадение/активная сессия не меняют данные. Tests не обходят preservation-флаг одной правкой manifest. |
| WP15-002 | SC15-002/013 | Без permit/неверная HMAC/schema/source/DB/incarnation/caps/evidence/лишние поля → закрытая запись; ENVtrue не помогает. Ранние отказы SQL0/connect0, без raw secrets. |
| WP15-003 | SC15-004/014 | Реальный TLS prepare→unknown/terminal/replay только заданного operationId/fingerprint. Чужой ID/другое тело/secret/роль/phase не пишут, head не меняется. Чтение работает при disabled permit. |
| WP15-004 | SC15-004/005 | Полный POST отправлен, клиент намеренно не получает тело ответа. Реальный commit выясняется независимым SQL/status; exact retry с прежним expectedGeneration возвращает сохранённый receipt без дубля/другого поколения. Это lost-response-body witness, не имитация kernel packet loss. |
| WP15-005 | SC15-005 | Реальный API restart после подтверждённого commit: новый процесс/readiness, прежние identity/receipt/history; exact replay без дубля. Fault только owned container, не endpoint продукта. |
| WP15-006 | SC15-005 | Реальный KILL собственной PostgreSQL/возврат того же volume: пока недоступна, безопасный отказ без ложного результата; после recovery зафиксированные head/receipt/deny прежние. Не объявлять container crash доказательством physical power loss. |
| WP15-007 | SC15-004/011 | Fence recovery-role, old actual writer-secret со свежим epoch отвергается. Exact negative-probe fingerprint заранее включён в synthetic permit, чтобы пройти его envelope и достичь авторитетной DB проверки: ожидается CREDENTIAL_REVOKED/WRITER_FENCED и неизменность Head, а не один PERMIT_MISMATCH. Wrong role/изменённый action/replay с иным fingerprint не увеличивают epoch; exact recovery replay возвращает прежний receipt. |
| WP15-008 | SC15-011/012/016 | Пока новая private конфигурация/полная local reconciliation/exclusion не подтверждены — activate отказ/FROZEN. Для проверки предусловия отдельный допустимый action/fingerprint проходит HMAC/whitelist и достигает реальной DB/reconciliation проверки; одна неверная подпись не подменяет этот отказ. Прежний ключ и rollback конфигурации не получают полномочий через свежий номер head. Лимиты16op/4actions не расширяются. |
| WP15-009 | SC15-011 | Установка нового key/profile при остановленном API, последовательное пересоздание API/ingress, реальные новый writer login/mutation и отказ старого secret. В observer нет raw tokens. Никаких изменений owner/employee паролей сайта. |
| WP15-010 | SC15-009/010 | Все прежние operation/denial/tombstone/terminal receipts и архив corpus сохранены при recovery. Новый writer не меняет прежний terminal и не восстанавливает удалённое/HTML по адресу. workflowComplete остаётся false. |
| WP15-011 | SC15-013 | Размер/число RecoveryReceipt и нового test permit ограничены в прежнем бюджете; CPU/RAM/PIDs/данные/логи измерены, OOM0. Новый schema fingerprint не позволяет молча использовать чужую калибровку; пригодность legacy corpus и малого разрешённого набора обоснована review. |
| WP15-012 | SC15-014 | Source/config drift, malformed query/body/permit/key, safe logger control/canaries: нет секретов/payload/URI в логах и отчётах; readonly mounts/internal nets/no host ports и default disabled сохраняются. |
| WP15-013 | SC15-015/016 | Итог: Stop, source/config/runtime hashes, архив/MAIN/test state сохранены. Ни fake gate ack, ни полный APP/restore/production PASS не выводятся из тестового permit. |

Сценарии подготовлены до реализации. После независимого precode review — код и unit, затем независимое code/QA review, только затем изготовление конкретного permit и реальные fault-проверки. Подпись permit не является самосогласованием: evidence и переходы проверяет независимый рецензент до активации. Постоянное production размещение/полная APP integration остаются за пределами D-376.
