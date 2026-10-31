# Повторное использование URL и старый HTML

2026-10-30. Этап7, D-243/244/295/301/302/305/308; AC-HTML-002/AT-202 и §11–12 analytics-html-reserve.md. Только тесты/контракты, без реализации сайта, controller или изменений старого сайта/VPS.

## Подготовлено

`acceptance/url-reuse.spec.js`:16экземпляров — application/database × GET/HEAD × direct/encoded-unreserved/query/old-etag.

Одинаковая существенная последовательность каждого случая:

1. Существует новая синтетическая P `/acceptance/reuse-route/` с уникальным текстом и реальным валидированным ночным файлом этой точной инкарнации; normal GET200 — положительный контроль. Затем actual app stop/две проверки дают reserve: реальный200 P из ночного файла и его ETag сохраняются. После start/двух успешных проверок normal подтверждается, только потом P удаляется. Таким образом If-None-Match относится к **старому reserve-ответу**, а не только к независимому пространству ETag Django.
2. Владелец под актуальным подтверждением/паролем удаляет P. Фактическая запись отсутствует, точный URL404 без прежнего содержимого.
3. Владелец создаёт **новую** Q с другим ID на том же URL, сохраняет другой текст и публикует. Реальный normal GET200 показывает Q, не P. Между операциями нет новой ночной сборки; служебная политика указывает Q/LIVE_NO_SET при сохранённом файле P.
4. Только в допущенной изолированной инфраструктуре останавливается app или DB. Две фактические локальные проверки подтверждают reserve.
5. Точный URL нового Q, включая HEAD и старый If-None-Match, получает503 без Location/старого200/304/чужого тела. Ночной manifest/fileSha и objectID остались P: отсутствие старого тела не объясняется его удалением из fixture.

Для `%72` и неизвестного query `?acceptance_probe=1` принятый документ требует проверить отсутствие обхода допуска, но не задаёт единую нормализацию. Поэтому assertions **не утверждают**, что это обязательно тот же canonical URL: безопасный404/503 допустим в этой отрицательной частичной пробе. Если реальная политика отвечает301, допускается только непосредственный текущий Q путь и его отдельный503; Location может быть относительным или абсолютным на доверенном HTTPS-origin, без query/fragment/credentials. Перед полным AC нужна независимая проверка конкретной политики percent/query; нельзя выдать эти безопасные отказы за доказательство точной совместимости произвольных старых адресов. Регистр/слеш/double-encoding/значимые query галереи здесь не переназначаются.

## Future fixture/привязки

До `reset('url-reuse-existing-night')` требуется independently reviewed admission arc10Verified/isolatedInfrastructure/reviewedEvidenceId и fallback-control-v1. Профиль создаёт только собственное дерево P-URL-PARENT/P-URL-REUSE, уникальные тексты и настоящую завершённую ночную сборку. Дневное время контролируется в собственном тестовом процессе так, чтобы следующий scheduled build не подменил проверяемую ночь. Никаких generated-expected HTML, fakecontroller, реальных данных/интеграций или доступа к VPS.

- `url-reuse-fixture` — oldPageId/path и trustedPublicOrigin из доверенной конфигурации, не Host/query ответа; источник фактической созданной P. Никакого перехода к этому origin не делается: фактические probes всегда идут на изолированный local edge, HTTPS-origin нужен только для проверки Location. Текст P `URL-REUSE-OLD-P-NIGHT-CANARY`, текст Q `URL-REUSE-NEW-Q-CANARY` — только тестовые маркеры.
- `url-reuse-night-proof` — actual-file/manifest evidence:createdByActualBuild/validationState/setId/path/objectId/fileSha256 реального готового файла P. Хэш рассчитывается по прочитанным файлам, а не копируется из expected; конкретные job/manifest/head источники требуют ревью. Этот manifest не «переоформляется» на Q, не стирается и не пересобирается между проверками.
- `url-reuse-record(pageId)` — actual-db exists/path/revision для конкретного ID; удалённая P не подменяется Q по строке URL.
- `url-reuse-routing-state(path)` — actual current independent admission policy/object mapping:objectId Q, routeKind LIVE_NO_SET, nightObjectId P/nightSetId прежнего набора. Не «ожидаемый результат» из args.
- `url-reuse-route-response(path,method,headers)` — actual-http запрос через единую действующую edge-точку, **без follow redirects**, фиксированные GET/HEAD и If-None-Match. Возвращает status/body/headers и method/requestTarget/requestHeaders с фактически посланного запроса. Имена response/request headers — lowercase. HEAD body — реальные пустые байты ответа. Raw percent и query не удаляются транспортом: иначе это не проверка encoded/query. Любая обработка body для JSON должна сохранять исходный текст для поиска старого содержимого. Reader ограничивает origin собственным допущенным local target; только относительный path, без credentials/внешних redirect/request Host. Нового публичного endpoint сайта не создаётся.
- `create-page`, `publish-created-page`, `prepare-delete-page`, `confirm-page-delete-direct` — existing owner UI/HTTP actions с реальными revision/confirmation/current password проверками. Новый `save-created-page-text-direct(pageId,base,text)` — настоящий owner save endpoint для уже созданной Q; не SQL-мутация через fixture. Конкретные path/body/selectors появятся с приложением и проходят отдельное ревью.
- `fallback-control-state` и existing stop-isolated-component/advance-infrastructure-time используют собственный real controller с отдельным controlOrigin/свежими permits. Эти интерфейсы не реализуют продуктовый fallback.

## Readiness и ограничения

Приложения, bindings/bridge, controller и физического ARC-10 нет;16сценариев **не исполнялись**, полный AC не пройден. Evidence flags требуют проверки реального происхождения; source markers сами этого не доказывают. Получение503 не заменяет полный тест контактного резервного вида, всех приватных утечек/URL формы/бизнесданных. Полное удаление входящих редиректов проверяется другим поднабором. В этой последовательности deleted404 проверяется до создания Q в normal; отдельный длительный deleted404 при аварии/гонках ещё требуется в полном fault-наборе.

Существующие тесты и данные сохранены. Ни code сайта, ни старый сайт/VPS/ОС/БД не затрагиваются; этап8 и production отдельно.
