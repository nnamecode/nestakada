# Смена URL, редиректы и SEO ночного HTML

2026-10-30. D-243/244/295/300, пакет D-301, тесты D-302/303/308; ограничения D-305 сохраняются. Основания:analytics-html-reserve.md §10–12, analytics-seo-detail.md §8; AT007/211/606, AC-007/AC-HTML-011/AC-SEO-006.

## Подготовленные сценарии

`acceptance/url-reserve.spec.js`:12экземпляров, по6 для отказа application/database.

- Один переход новой разрешённой страницы A→B после ночной копииA, затем noindex и отказ:GET/HEAD с прежним ETag дают актуальный301 наB;B без собственной копии503/no-store, не старое телоA. Допустимая главная200. Это не переименование защищённого рекламного адреса D-023.
- Два переходаA→B→C; отдельно live/hidden/deleted. Старые A/B сразу ведут301 наC, включая нормальный режим. В reserve текущий liveC без копии503; hiddenC пустой200; удалённыеC/A/B404. Подтверждение удаления проверяется на текущийURL и полный фактический список редиректов. Успешное удаление не оставляет старый301/старое тело.
- Отдельно ужесточение index→noindex после сборки и обратное разрешение при сохранённом meta noindex. Реальное тело/единственный canonical сохраняются; текущий noindex усиливается HTTPзаголовком, старый meta noindex не исчезает. Любой распознанный HTTPcanonical не конфликтует с сохранённым. Неподтверждённый Sitemap503/no-store без непроверенногоXML, главная200. Сама выдачаHTML не восстанавливает бизнесданные.

Все12сценариев не исполнялись:нет приложения/bridge/bindings/контроллера/physical ARC-10. Пакет собирается отдельно, положительные прогоны AC не заявляются.

## Тестовые привязки

`url-route-night-ready` — настоящая изолированная fixture с новой P-URL по `/acceptance/url/a/`, разрешённой сменой URL, действующим прайсом/контентом/заявкой/согласием и пригодной главной; реальный job создаёт READY-набор наA. Опция indexable задаёт начальную разрешённость индексации до сборки. Текущие путиB/C свободны, не legacy. Контролируемое время далеко от следующей ночной сборки; дневные действия не создают новый набор. После каждого сценария уничтожается только собственная fixture.

`url-route-fixture` — actual-fixture/read-only свидетельства pageId/setId/nightPageId/nightPath/oldEtag/oldBodyCanary/mainCanary/createdByActualBuild/validatedState/trustedPublicOrigin. Logical canonical origin фиксирован в изолированной конфигурации как `https://acceptance.invalid` (зарезервированное имя, **сетевых запросов к нему нет**). Фактическая сеть — только проверенный локальный ESTAKADA_TEST_BASE_URL. Ожидаемый origin не берётся из Location или входного Host. Реальные job/files/manifest/head и отсутствие нового пригодного файлаB/C ещё проверяются при concretebinding review; markers не доказывают физические свойства.

`url-route-response(path,method,headers)` — только actual-http GET/HEAD к своему localfront, без follow redirects, с реальными status/body/lowercaseheaders. В тестах headers только If-None-Match. HEAD возвращает реальные пустые байты, не ответ GET с очищеннымbody. Bridge проверяет относительный путь/локальныйorigin/allowlistметода/заголовков, не ходит к logicalorigin и не читает statusизБД. Body и SEOметаданные разбираются тестом в JSfalse DOMParser с полностью запрещёнными сетью/WS, а не возвращаются как готовый результат проверки. Границы регистра/query/encoded нормализации отдельно в reuse контракте.

URLдействия:owner `prepare-page-url-change(page,base,requestedPath)` реально проверяет/показывает oldPath/newPath и выдаёт confirmation. `confirm-page-url-change(page,base,requestedPath,confirmation)` — настоящий текущий handler, повторные права/revision/занятость, внешний запрет/head/входящие редиректы по §11. Не заменять directDBupdate или test-controller URLмутацией. `page`, `seo-page-state`, `set-page-indexing-direct`, `set-page-publication`, `prepare-delete-page`, `confirm-page-delete-direct` — реальные существующие семантические интерфейсы; конкретные paths/fields не реализуются на этапе7. Deleteconfirmation.redirectPaths — полный список текущих входящих адресов, не заранее подставленное expected.

`url-route-business-state` — actual-db read-only устойчивые arrays pages/redirects/homeItems/versions/requests/consents собственногоrun. Содержат ID/revision/состояние/неперсональные hash-свидетельства действительных строк; не статический bool «restore не было» и не wholeDBdigest логов/таймеров. Обязательный положительный состав pages не пуст. Сравнение выполняется после фактического старта/готовности остановленного компонента без reseed/reset/restore; источник по своей неопределённости не объявляет равенство.

Для index-поднабора публичных индексируемых кандидатов ровно два:главная (всегдаindexable) и P-URL. Если отдельно доказанный текущий Sitemap доступен,200 разрешён: собственный XMLParser сверяет точный текущий состав (главная плюсA только при текущемindexable=true), namespace/структуру/отсутствие дублей. `url-route-sitemap-proof` — read-only актуальное независимое policygeneration и подтверждённое поколениеXML плюс SHA256 фактическойUTF8 XMLрепрезентации; тест сравнивает generation и хэш с собственным подсчётом полученногоbody. Это не вердикт bridge по ожидаемомуstatus. При отсутствии пригодного XML принимается503/no-store без XML. Смена индексации сама по себе не запрещает актуальныйXML200.

url-route-response также возвращает фактические requestTarget/method/requestHeaders; они сверяются с переданными запросами. 90секунд — только wall-time budget комплексного теста, не SLA/срок реакции владельца/новый параметр production.

Faults используют **существующий** fallback-control-v1:проверенный независимый ARC-10 допуск доreset, свежий scope/instance/admission перед stop/start/clockadvance, две реально завершённые локальные проверки и подтверждённый mode reserve. Никакого нового контроллера/productionконфига, минутногоопроса или применения к VPS.

## Незакрытые ветви

Полные AC007/211/606, отказные границы URL_CHANGE_PENDING/commit/finalize, receiptreplay/reconciliation и отставшие workers, новый подходящий ночной набор после переноса/гонка егоактивации, hostileHost/параметрыLocation/сложныйRFCLink, все зависимости/noindex/canonical/Sitemap состояния и фактическаяфизическаяпроверкаARC-10 ещё отдельно. Другие7partialHTTP проверки и существующиеSEO/fallback наборы сохраняются. Код сайта/живойсайт/VPS не трогаются.
