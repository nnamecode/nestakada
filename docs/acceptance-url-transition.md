# Прерывание смены URL и незавершённая финализация

2026-10-30. D-301/302/303/305/308; analytics-html-reserve.md §6/11/12, AT204/212, AC-HTML-004/012. Только этап7, без приложения/миграций/контроллера продукта и без старого сайта/VPS.

`acceptance/url-transition.spec.js`:11экземпляров. Пять fault-boundaries×GET/HEAD плюс поздний worker, остановленный **до** допуска ответа. Это частичные assertions, не исполненные AC. Concrete app/bridge/controller/physical ARC-10 отсутствуют.

## Fixture и реальный источник данных

`url-transition-existing-redirect-night`:новая разрешённая P-URL-TRANSITION имеет настоящий READY-набор поA=`/acceptance/url-transition/a/`. Реальный ранее завершённый owner A→B создаёт входящийA→B;B без своего снимка. Изменение B→C — предмет текущей операции. Точные служебные paths только синтетические, legacyURL не переименовываются. Actual job/files/hash/head и первая смена должны быть доказаны при concretebinding review. Logical origin https://acceptance.invalid ни разу не запрашивается; фактическая сеть только собственные разрешённые localorigins. Время далеко от ночной сборки,30минутное продвижение не создаёт новый набор.

`url-transition-reserve-response(path,method)` — actual-http GET/HEAD к **тому же настоящему HTMLgate** на отдельной фиксированной локальной тестовой поверхности, пока admin-приложение доступно для owner/DBопераций. Это не поиск файла в обход gate, не вычисление статуса из registry и не новый productionendpoint. Действуют единая точка допуска, externalhead и настоящие headers/body/requestTarget/method. GET и HEAD — разные реальные методы, redirects не следуются. Независимое подтверждение физических границ ARC-10 обязательно до reset/fault; нужны fallback-control-v1 и url-transition-control-v1.

Read-only наблюдения:

- `url-transition-fixture`:pageId/setId/nightPath/currentPath/oldBodyCanary/mainCanary/trustedPublicOrigin, actualBuildReady/firstMoveCommitted с первичными свидетельствами. `url-transition-night-file`:реальные body/SHA256/path/pageId/setId существующего старого файлаA. Флаги сами не доказывают происхождение.
- `url-transition-db-state`:actual-db page{id,url,revision},history/redirects/receipts и protectedBusiness arrays. History/receipt содержат operationId, redirects — path/targetPageId/targetPath. Только семантическая проекция устойчивых данных, без таймеров/логов/счётчиков повторного чтения/wholeDBdigest. protectedBusiness включает прочий контент/связи/версии/заявки/согласия/права в собственной fixture; ID/hashбезсекретов. Before/after проверяет отсутствие чужой мутации. Не выдавать заранее ожидаемые arrays.
- `url-transition-operation(operationId)`:фактический receipt/operationjournal и DB/transaction evidence. state pending/complete/rejected/rolled-back; commitState not-started/rolled-back/committed/unknown. rollbackVerified=true — только доказанный откат/невступление в транзакцию при сверке актуальнойDB, не вывод из faultlabel или отсутствия новой ошибки. Для complete — реальная confirmedAdmissionSequence, общая с trace gate.
- `url-transition-fault-evidence`:собственный faultId/operationId/phase, реальные hitCount/handlerSettled/durableDenyConfirmed. handlerSettled подтверждает прекращение исходной попытки и отсутствие отложенного ещё возможного DBcommit в рамках этой попытки. Неподтверждённое завершение — readinesserror, не pass. Поздние независимые workers разбираются отдельной пробой.
- `url-transition-worker-response/state`:настоящий конкурентный HTTPзапрос к томуже gate и trace actualworker, held-before-admission/порядок sharedadmissionsequence/завершение или доказанное fencing. Trace не создаёт ответ по ожидаемому коду. Запрос начинается до подтверждения операции, но barrier расположен до точки допуска; уже допущенным ответам не запрещается завершиться (§6.2).

## Действия и fault-controls

Owner prepare-page-url-change/confirm-page-url-change — настоящие UI/HTTP handlers с актуальными правами/revision/занятостью. Подготовка показываетB/C и выдаёт устойчивый operationId/confirmation. Повтор **того же** confirm с теми же полями/подписанным подтверждением распознаётся по операции, не становится новой мутацией. `recheck-page-url-change(operationId)` — настоящее авторизованное действие «проверить результат», выполняющее предусмотренную сверку по фактуDB; не test-only командная запись бизнесданных.

Новый ограниченный test-domain url-transition-control-v1 предоставляет только:

- `set-url-transition-fault(operationId,phase,fault=persistent-test-dependency-error)`/`clear-url-transition-fault(operationId,faultId)` — реальный ограниченный отказ зависимости/финализации:before-deny-write,after-deny-before-db,after-db-before-finalize,incoming-redirect-finalize,before-admission. Это физический IO/availability/instrumentation barrier, а не выдача заранее запрограммированного businessresponse. Контроллер должен доказать достижение соответствующей точки.
- `hold-url-transition-reconciliation(operationId)`/`release-url-transition-reconciliation(operationId,barrierId)` — удержание фоновой сверки, чтобы продвижение часов не имитировало автоматическое разрешение; operation state и DB не меняются контроллером.
- `hold-url-route-worker(operationId,path,phase=before-current-generation-admission)`/`release-url-route-worker(operationId,workerId)` — управляет только barrier собственной конкурентной HTTPпробы, не выдаёт старое разрешение и не публикует страницу.

Перед каждым control остаётся свежий isolated run/instance/admission/capability, fixed command allowlist и раздельный localcontrolOrigin. Root интегрирует клиентскиеguards, **конкретный контроллер не реализуется**. Никакой control-команды «сменитьURL», «применитьrollback», «вставитьreceipt», «финализироватьредиректы» нет.

## Ожидания и честные границы

После конечной доказанной сверки actualDBredirects проверяются по всем затронутымA/B/C и всем текущим входящим целевогоP, включая чужую targetPageId/дубликаты/лишнийredirectC:приcommit точныйнабор(A,P,C)/(B,P,C), приverifiedrollback только(A,P,B). Приcommit ровнооднаhistory/receiptсохраняется и послеrecheck, приrollback новаяhistory отсутствует. Это текущие активные связи, не архив/историяredirects. Неизвестный/pending не заставляем объявлять конечныйнабор.

Известные точки fault проверяются независимым actualDBчтением:after-deny-before-db сохраняет прежнюю page/revision и redirects, history этойоперации отсутствует. after-db-before-finalize/incoming-redirect-finalize/before-admission требуют фактическуюpageC/новуюrevision, ровнооднуhistory/receipt и плоские DBredirects A/B→C. Publicreceipt может консервативнооставатьсяpending/unknown; егоярлык не заменяет свидетельство commit. Отдельныйunknowncommit сценарий не подменяет эти известныеграницы и полностью не покрыт.

До успешной долговечной записи запрета основнаяDB не меняется; существующийA301B/B503 сохраняется,C404. После подтверждённого deny и прерывания затронутыеA/B/C недоступны503/no-store без выдуманногоLocation или старогоHTML. При известном commit страница действительноC и одна history/receipt; при доказанном некоммите —B. Unknown не маскируется выбранным ответом по имениstage.

Пока fault/reconciliationbarrier удержаны, повтор тогоже operationId возвращает pending и не дублирует данные;30минут сами не разрешаютHTML. После снятия технического отказа и явной ownerпроверки допустимы:подтверждённый commit с плоскимиA/B301C иC503; доказанный rollback/not-started с возвратомA301B/B503/C404; либо честно остающийсяunknown/pending с закрытымиaffectedpaths. Тест **не требует придуманного автоматического отката или обязательной успешной финализации**, если доказательства недоступны. Неизменные count≤1 и protectedBusiness обязательны.

Поздний worker, удержанный до admission, после подтверждения не выдаёт старый200/301наB:либо актуальный301C после новой проверки, либо503 с реальным fencing. Уже допущенные ранее ответы сюда не относятся. Главная сохраняет200/публичнуюметку.

Не покрыты все crash/kill/unknowncommit варианты, истечение/подмена подписанного подтверждения, изменение прав/занятости во время ожидания, все запросы/encoded/query/новая инкарнация и конкурентные сборки; прежние URL/reuse/fallback наборы сохраняются. 90секунд — бюджет тестового инструмента, не срок для владельца/продуктовыйSLA. Полные TEST-07/AC/UX-07/physical ARC-10 остаются открытыми.
