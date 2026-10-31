# Локальный тестовый адаптер — этап 7

Дата: 2026-10-30. Основание: D-302/D-303/D-307/D-308. Только тестовые файлы; приложение Django, production-конфигурация, старый сайт и VPS не создаются и не меняются.

## Подготовленная часть

`acceptance/isolated-application-driver.js` реализует транспорт UI/HTTP, отдельные браузерные сессии ролей, чтение фактического DOM/JSON и обмен с локальным подготовщиком тестовых данных. Результаты не вычисляются по ожидаемому бизнес-правилу. driverKind и метки происхождения — декларации, не доказательство настоящего приложения: конкретные привязки и подготовщик требуют отдельного независимого ревью.

Полного работоспособного адаптера приложения пока нет. Не созданы local-bindings.json, local-fixture-bridge.mjs, local-fixture-settings.json: ещё нет разрешённого приложения, его моделей/URL/реального UI и согласованных версий. При их отсутствии работа завершается явной ошибкой, тестовый сайт/фиктивная БД не подставляются. Прежний APPLICATION_DRIVER_NOT_IMPLEMENTED относится к историческому прогону до появления транспортного модуля; сейчас отсутствие target даёт TEST_TARGET_UNCONFIGURED, отсутствие привязок — DRIVER_BINDINGS_NOT_CONFIGURED.

## Привязки и фактические действия

- Фиксированный JSON: schema=isolated-ui-http-v1, точный targetOrigin, profiles/profileSetups/operations/observations. Произвольный импорт, код/eval или выбор файла через env не поддерживаются. Секреты/пользовательские данные не входят в Git.
- HTTP с явным портом только на loopback/localhost/host.docker.internal. Preview :8765 исключён. Браузер блокирует чужой origin, WebSocket, service workers и скачивания. Прямой HTTP не следует внешним редиректам и не пересылает POST по307/308. Ограничение адресов не заменяет доказательства изоляции стенда и его БД.
- HTTP-действия — настоящие GET/POST; payload сохраняет пробелы/Unicode/границы/лишние поля, не очищается вместо сервера. `$ref`/`$lookup` читают fixture/аргументы, проход по prototype запрещён. Конкретные URL/поля/селекторы ещё не выбраны.
- UI — goto/fill/click/check через роли, подписи и testId настоящего интерфейса. Адаптер не использует setContent или бизнес-код в странице. Для серверного результата нужен наблюдаемый ответ с настроенным статусом и однозначным маркером/JSON-полем; один HTTP200 успехом операции не считается.
- type-unsaved-text и stage-page-version-restore могут иметь result.format=ui: считываются настоящие input/text/checked и сверяются с заданием действия. Результат **ui-observed**, а не accepted сервером. Обнаруженный во время операции запрос с изменяющим методом вызывает отказ; отсутствие любых серверных изменений дополнительно проверяется observe в самом сценарии.

## Открытый редактор и истечение сессии

page-history-restore и controlled-session-boundary требуют profileSetups для S-EDIT с настоящим открытием редактора и вводом несохранённого текста. Ввод после fill считывается из поля. Для controlled-session-boundary порядок:

1. reset, phase=before-ui: настоящие тестовые данные/сессия ещё свежие; evidence.preparationPhase=fresh-before-ui.
2. UI открывается под этой сессией, в поле вводится и считывается несохранённый текст.
3. reset, phase=after-ui: подготовщик меняет только тестовые часы/возраст сессии своего стенда, подтверждает тот же runId и evidence.preparationPhase=after-ui-finalized. Системные часы компьютера/сервера не меняются.
4. Лишь затем сценарий выполняет проверяемый запрос и читает ввод в уже открытой вкладке.

Ошибка подготовки блокирует дальнейшее использование драйвера. Открытие страницы уже после истечения срока вместо этого порядка не допускается. Конкретные подготовщики должны независимо доказать фазы/инварианты; одного поля evidence недостаточно.

## Подготовщик и наблюдение

Перед настоящей UI-подготовкой и сразу после неё `observe(ui-preparation-business-state)` читает actual-db: непустой список pages с id/revision/publicText/versions, полным сохранённым draft/защищёнными полями и историей. Наблюдение обязано охватывать все затрагиваемые страницы и возвращать детерминированный порядок, без меняющихся счётчиков аудита чтения. Сравнивается вся фактическая структура; изменяющие HTTP-запросы во время подготовки также вызывают отказ. Эти чтения выполняются до отдельной финализации времени. Проверки orchestration используют только транспортные callbacks, не модель сайта. Реальные bindings должны отдельно доказать полноту/синхронизацию наблюдения, включая отложенные операции редактора.

Только фиксированный .mjs внутри acceptance, отдельный Linux-процесс со stdio, без shell/наследования env с токенами. Команды reset/observe/close; act через него запрещён. Reset работает только с собственными синтетическими начальными данными. Observe читает настоящую БД/HTTP, не expected. Тестовое время/fault barriers — только в будущем согласованном изолированном контуре.

Протокол estakada-fixture-v1 связывает запрос/ответ случайным nonce, targetOrigin и runId. Ответ: ok/protocol/nonce/targetOrigin/runId/source/data/evidence. Reset требует actual-fixture/fixtureVersion, observe — actual-db/actual-http. Транспортный двойник fixture-transport-selfcheck.mjs имеет source=transport-selfcheck и не принимается как настоящая fixture.

Вход256КиБ, stdout/stderr по1МиБ, обычный срок8с. При ошибке/таймауте собственная группа процессов получает TERM, через100мс KILL; ожидается фактический close/исчезновение группы с границей1,5с. Подготовщик не должен отделять потомков в другие группы. При неподтверждённом завершении драйвер блокирует новые операции. Произвольный stderr/ошибки Playwright с введёнными значениями не копируются в отчёт; известные синтетические пароли/cookies/секреты скрываются. Конкретные наблюдения ещё требуют ревью на утечки.

## Настоящая отправка синтетических файлов

`upload-support.js` читает только обычные файлы собственного run из acceptance/generated-fixtures/{runId}/: realpath не выходит из каталога запуска, descriptor.path не выбирает произвольный файл проекта/профиля. runId ограничен безопасными символами. Имя/MIME/байты не преобразуются в допустимую серверу картинку; серверу передаётся именно тестовый источник. Файлы создаёт будущий изолированный fixture bridge; исходные фотографии людей/старого сайта сюда не копируются.

fixture.uploads[fileRef] содержит {path,name,mimeType}. HTTP binding с encoding=multipart задаёт поля body и соответствие files:{реальноеИмяПоля:fileRef}; это обычный multipart/form-data через Playwright, не новый JSON/base64 endpoint. Заголовок Content-Type вручную не задаётся, чтобы библиотека сформировала boundary. UI-step setInputFiles использует настоящий input; при автоматической отправке требуется явный responsePath/responseMethod, либо затем отдельный click с наблюдением фактического ответа. Реальные URL/имена полей/селекторы ещё не выбраны.

Контейнерный ресурсный guard —64МиБ на файл и суммарно64МиБ файлов на один multipart, до32частей с файлами и256КиБ имён/скалярных полей. Оставшийся суммарный бюджет проверяется по открытому fd **до чтения следующего файла**, рост/усечение файла обнаруживается. Это не бизнес-лимиты загрузки сайта: DRIVER_*_TRANSPORT_RESOURCE_LIMIT не принимается за отказ серверной валидации. Реальные форматы, MIME выхода, байтовые/пиксельные пределы, качество и positive upload-control ещё должны быть отдельно согласованы; кандидат JPEG/PNG/WebP не становится разрешённым по примеру fixture. Если принятая политика потребует большие тестовые файлы, транспортный бюджет пересматривается явно.

12новых самопроверок проверяют собственные синтетические байты/пути/суммарный бюджет, реальный multipart на инертном локальном приёмнике байтов и File API настоящего браузера на синтетическом harness HTML. Приёмник не реализует правила сайта, а браузерный harness не выдаётся за UI приложения. Документация API: [APIRequestContext multipart](https://playwright.dev/docs/api/class-apirequestcontext#api-request-context-post-option-multipart), [Locator.setInputFiles](https://playwright.dev/docs/api/class-locator#locator-set-input-files), проверено2026-10-30; закреплённая версия D-303 не менялась.

Для фактических HTTP-заголовков result.fields может явно выбрать header из ограниченного списка cache-control/content-type/location/etag/last-modified/x-content-type-options/content-disposition. Cookie/Authorization и произвольные заголовки в это представление не включаются; значение берётся из ответа, не из HTML.

`response-safety.js` проверяет зарегистрированный fixture.logSensitiveCanaries в исходном ответе до маскирования отчёта: JSON values и инертно декодированные HTML text/attributes. Возвращаются только checkedCount/detected, а не найденные секреты. Это позволяет проверять настоящий redaction журналов, даже если тот же тестовый секрет адаптер скрывает в отчёте. Пустая/неверно связанная коллекция не доказывает безопасность; LOG-category требует непустой corpus/count и соответствие настоящему source-event. Две дополнительные самопроверки проверяют детектор на сырой/закодированной утечке и безопасном контроле.

## Запуск и границы

Для резервных копий и HTML-сборок fixed action→capability теперь разделён: backup-control-v1 и html-build-control-v1, прежний fallback-control-v1 сохраняет свои команды. Имена jobs/fault/barrier не задаются произвольным config/кодом из внешнего источника. На каждую команду свежий actual-http допуск обязан иметь **нужный домен**, fallback-only не даёт права запускать backup/build. Это только тестовый транспорт: сами builder/backup/controller/хранилища ещё отсутствуют.

К четырём correlation-связям run/operation/instance/admission добавлен обязательный x-estakada-test-capability в запросе **и ответе**. Управляющая служба атомарно проверяет актуальный допуск/домен/own-run scope до исполнения; отражение произвольного присланного заголовка не доказательство. Существующие concrete bindings ещё не создавались, поэтому готовый работающий controller этим изменением не обновлялся. Новые3самопроверки проверяют fixed domain map и отказ fallback-only admission для обоих новых доменов.

Для принятого конкурентного POST формы outcome=pending обозначает только **наблюдаемый промежуточный ответ**, не подтверждённое создание и не пятый статус Request. Валидатор требует явный marker/jsonEquals и определённый status; одного200/202 недостаточно. После pending тест сам выясняет действительное committed состояние и явно повторяет прежний intent без нового ключа; драйвер не превращает timeout в accepted и не запускает скрытый retry. Проверка декларации pending добавлена в driver-safety.

Общий read-only preflight до reset не является бессрочным разрешением команд. Перед каждой control-командой допуск повторно читается из actual-http уже с текущим runId; controlOrigin/instanceId/admissionGeneration/runId должны совпасть с заново выданной controlSession. Все четыре связи проверяются также в ответе. Реальный тестовый контроллер обязан **до исполнения** атомарно проверить run/instance/admission и отказать при устаревшем допуске; простое отражение присланных заголовков недопустимо. Его реализация/гонки смены экземпляра/отрицательные интеграционные пробы ещё требуют отдельного ревью и стенда. Кэшированного разрешения в клиентском адаптере нет.

Инфраструктурный preflight `inspectInfrastructureAdmission()` — отдельное read-only observe(infrastructure-admission) до reset, source=actual-http, без создания данных. Для fault-действий используется **control(action,args)**, а не act роли приложения. Опциональные controls/controlOrigin задают другой явный локальный HTTP-origin вне APP/EDGE; точное размещение/URL ещё не выбраны. Разрешён фиксированный набор тестовых fault-команд, только POST без редиректа, с собственной controlSession и фактическим допуском ARC-10/instanceId из независимого контура. Каждый запрос/ответ связан runId и случайным operationId через тестовые заголовки x-estakada-test-run/x-estakada-test-operation. Успех транспорта не заменяет последующие фактические проверки режима/SQL/ACK. Business act через этот канал запрещён; act(TEST-CONTROL,...) также отвергается. Конкретный controller/bridge/наблюдения не реализованы, независимость после остановки APP/EDGE ещё требуется доказать на изолированном стенде. Это тестовый протокол, не новая production-служба или API сайта.

run-container.ps1 копирует фиксированный список; три необязательных локальных файла — только обычные файлы без reparse point. Устаревшая копия убирается при отсутствии исходника. Профиль, Docker socket, приложение и VPS не монтируются; закреплённый образ D-303 не менялся.

driver-safety работает без сети и проверяет транспорт/ограничения, не AC сайта. application-contracts/form-contracts/content-lifecycle повторно не запускались с заранее отсутствующей зависимостью. Ни один полный AC, TEST-03/04/05/06/07, UX-07 или окончательный ARC-10 этим адаптером не закрывается. Текущие числа/ревью — acceptance-test07-continuation.md.

## Чтение памяти собственной вкладки

`editor-memory-state` объявляется только `{kind: "ui-memory"}` без кода/произвольных полей. Подмена fixture-read запрещена. `browser-memory.js` читает URL/ключи и значения localStorage/sessionStorage непосредственно из actor.page того же локального origin. Возвращает только source=actual-actor-browser и три boolean наличия canary, без содержимого/URL. Ошибки/чужой origin/about:blank не считаются пустым хранилищем. Проверяется буквальная строка и до двух URI-декодирований; transient/IndexedDB/CacheStorage/cookies/frames/произвольные кодировки не покрыты. [Сценарии и ограничения](acceptance-unsaved-editor.md). Две DRIVER-MEMORY самопроверки относятся к оснастке, не AC сайта.

## Раздельные допуски логов и фоновых работ

`log-maintenance-control-v1` связан только с fixed test-actions run/hold/release log maintenance, set/clear log storage fault и advance-log-test-time. `background-job-control-v1` — только start/hold/release isolated invocation, fail/clear own worker fault и advance-background-test-time. Точный перечень находится в driver-safety.js; команды не являются implementation/публичными endpoint сайта.

Обычный fallback permit и разрешение другого домена не дают эти права. Перед каждой командой сохраняются свежий actual-http допуск ARC-10, scope собственного run, instance/admission и проверка пяти correlation headers. Конкретный независимый контроллер ещё должен доказать ограничение своих volumes/workers/clock и атомарную проверку до исполнения. Пока он не создан, fault-команды не запускаются. Дополнительные4selfchecks подтверждают клиентское разделение допусков, не реальную изоляцию/квоту/остановку worker. [Контракты логов](acceptance-log-quota.md), [фоновых работ](acceptance-background-jobs.md).

## Допуски восстановления и частичной очистки

`restore-control-v1` допускает только fixed restore fault/external confirmation/identity recovery/probe preparation, `log-deletion-control-v1` — только set/clear fault файловой стадии собственной подтверждённой операции. Backup permit не разрешает restore; обычная log maintenance не разрешает manual delete faults. Реальные owner-confirmation/password/signed-command и проверка current run остаются внутри выбранной процедуры, не подменяются тестовым permit. Новые7selfchecks входят в74driver-safety; это оснастка, не исполненный restore/delete.

`provisionRestoreWriteProbe(operationId)` работает только в restore fixture с ещё не использованным OWNER-RESTORE-PROBE. Под свежим restore permit выдаётся защищённый одноразовый grant, из private fixture channel читается новая framework session/CSRF после invalidation. Старый cookie/другой run/operation/grant/actor/неактуальная sequence/чужой origin/постоянное browser-storage отвергаются. Только новый actorState переносится в fixture, затем его настоящий context создаётся обычным actorContext; права/бизнесданные метод не меняет. На ошибке fixture закрывается для дальнейших действий. Фактические controller/framework credentials, CSRF и scope cookie к конкретному POST/path/expiry до запуска требуют отдельного независимого ревью; единственная server session row или source marker не доказывают пригодность client request. [Restore контракт и ограничения](acceptance-restore-contracts.md), [очистка](acceptance-log-delete-failures.md).

## Сбои фиксации URL

Отдельный тестовый `url-transition-control-v1` допускает только6fixedactions: set-url-transition-fault, clear-url-transition-fault, hold-url-transition-reconciliation, release-url-transition-reconciliation, hold-url-route-worker, release-url-route-worker. Это инъекция локального отказа IO/барьеров собственногоrun/операции, не изменение URL/БД/receipt/прав и не завершение бизнесоперации. `confirm-page-url-change`/`reconcile-page-url-change` и произвольный DBupdate через control запрещены. OwnerUI/HTTP остаётся единственным тестовым путём самой мутации/явной сверки.

Fallback/backup/html-build/log/background/restore permits не дают этого допуска и наоборот; новый cap не позволяет остановить application без отдельного fallbackcap. Существуют прежние freshactual-http ARC-10/run/instance/admission и correlationchecks перед каждым вызовом. SAFE024-url-transition и SAFE032 проверяют клиентское разделение допусков, не физическийscope controller. Concretecontroller должен доказать whitelistстадий, scopeоперации, правдоподобные IOотказы/барьеры/lease worker, отсутствие post-close late work; пока его нет, команды не запускаются. [Контракт](acceptance-url-transition.md) описывает будущую оснастку без кода сайта.

## Служебные квоты и атомарное сохранение

`service-quota-control-v1` разрешает только run-isolated-service-cleanup/advance-service-test-time/drain-isolated-service-workers собственногоrun. Очистка затрагивает технически истёкшие записи/брошенныевременныефайлы, не рабочие заявки/согласия/используемые медиа/исправныйHTMLнабор и не меняет productionлимиты. `content-storage-control-v1` — только set-content-storage-fault/clear-content-storage-fault в реальных семантических точках version-persist/asset-reference-persist. Save/restore/удалениебизнесданных не допускаются через control.

Дваcap разделены между собой и со всеми прежнимиpermit. Перед каждой командой сохраняются свежие actual-http ARC-10/run/instance/admission/correlationchecks. SAFE024по двумcap и SAFE033 —3новые самопроверки клиентского guard; concretecontrollers/physicalscope/clock/cleanup/IOrollback ещё не доказаны. [Квоты](acceptance-service-quota.md), [версии](acceptance-version-storage.md). UIpreparation для sharedblocks требует actual-db pages+sharedBlocks проекцию в ui-preparation-business-state; существующийguard сравнивает весь объект, не толькоpages. Никаких новых UI-only businessactions/подмены DOM fixture-полями.

## Native форма и условные ответы

`openApplicationDriver({javaScriptEnabled:false})` передаёт строгий boolean в actual actor browser.newContext, включая UI-preparation. У существующих сценариев defaulttrue; inert response parser остаётся отдельным JSfalseконтекстом. Нет подмены настройки декларацией fixture. DRIVER-SAFE-028/029 проверяют строгий тип и настоящее отключение inlineJS/nativePOST на синтетическом HTML без сети.

Ответный Vary читается из фактического header. Новый `not-modified` строго ограничен HTTPGET с If-None-Match, без followRedirectGet, formatHTML и statuses[304]. Успех бизнесоперации по-прежнему требует действительного маркера/JSON;304 не означает принятой заявки. Пустой304 возвращается пустым даже после DOMParser; nonemptyraw отвергается. SAFE030/031 — самопроверки транспорта. [Контракты native](acceptance-form-native.md), [cache](acceptance-form-cache.md), [ревью/результаты](acceptance-form-native-cache-review.md). Реальных bindings/приложения нет, сценарии не исполнялись.

## D-315: источник сведений локальной основы

Текущие runtime образов определяет environment/foundation/runtime-images.lock.json; upstream images.lock.json описывает лишь buildmaterials. Для шести фиксированных process-read views сохраняются ограничения профиля/аргументов/source/runId; никаких произвольных команд или файловыхпутей от теста не добавлено. foundation-dependency-evidence сверяет реальные installeddistributions, archivechecksums, BuildKitreceipts и DockerreportedIDs отдельно отOCIconfig/exportdigests по текущему контракту foundation-security-checks.md. applicationImage — будущий реальный app, основанный на python-runtime; сам app и bridge пока отсутствуют. Нельзя выдавать preflight маркер/JSONилиlocks за runtimeповедение приложения.

## Исполненная локальная очередь D-316/D-317

DEV-02/DEV-28: 21 unit/integration и 11 FOUNDATION PASS; результат в [dev02-dev28-progress.md](dev02-dev28-progress.md), независимое ревью в [dev02-dev28-review.md](dev02-dev28-review.md). После Start test запускать `scripts/test-foundation.ps1`. Adapter foundation-fixture-bridge.mjs предназначен только для 11 readonly проверок: host process/SQL snapshot текущего run плюс живой HTTP. Wrapper закрепляет SHA guard в памяти и проверяет исходники, snapshot, manifest, контейнеры и Nginx до/после suite; прямой Playwright без guard не является приёмкой. Нет инспектора в приложении и Docker socket в runner.
