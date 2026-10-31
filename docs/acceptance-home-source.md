# Главная и источник цены: проверки до реализации

2026-10-30. D-255/256 с уточнением D-300, принятый пакет D-301 и PR-05 analytics-protocol-contracts.md, AC-012/AC-PRO-011/012, AT-012/411/412. Только этап7/D-308, без кода сайта или действий на старом сайте/VPS.

## Состав

`acceptance/home-source.spec.js`:7экземпляров.

- Действующий опубликованный источник:1000→1300 меняет ту же связанную сумму в реальном публичном HTML; ссылка/Asset/ID позиции остаются прежними.
- Две отдельные ветви:видимый→удалён и опубликованный→скрытый→удалён. Сравнивается фактическое состояние главной непосредственно перед удалением. Видимое не исчезает, уже скрытое не возвращается. Другой объект на том же URL/с той же подписью и новой ценой9900 не подхватывает связь.
- Снятие публикации без удаления скрывает последнюю доступную позицию/вкладку/блок по D-256; повторная публикация того же ID возвращает прежнюю связь.
- Удаление видимого источника и подтверждённая очистка реального orphan Asset не удаляет картинку, нужную главной. Проверяются сохранённая ссылка и реальные HTTP-байты через SHA/размер до/после.
- Два отказных варианта:остановка приложения или БД после удаления источника при готовой ночной копии. Через две действительные локальные проверки подтверждается reserve, главная отдаёт прежнюю позицию из того же набора, собственный удалённый URL404, активных технических токенов нет. После старта компонента защищённые бизнесданные совпадают с состоянием до отказа; удалённая запись не воскресает.

Это частичные assertions. Полные формы/взаимодействие в reserve, гонки удаления/публикации, отдельное удаление строки/всего непустого раздела, все price-варианты и ручная правка главной не закрыты этими7пробами.

## Future bindings/fixture

Профиль `home-source-single-published` создаёт локальные synthetic parent P-PRICE-PARENT и дочернюю P-PRICE-SOURCE без поддерева; числовую строку1000 без «от», одну связанную видимую позицию в единственной ценовой вкладке/блоке, собственную картинку и отдельный неиспользуемый файл для cleanup. Это специально узкие тестовые данные, не новые ограничения сайта. Один источник может представляться позицией/карточкой согласованного дизайна; селекторы не навязывают новый hero/markup. MAIN-SOURCE-SYNTHETIC-LABEL и mainCanary — тестовые метки, не продуктовые тексты.

`home-source-night-ready` добавляет тот же исходный набор плюс реальную завершённую валидированную ночную сборку, известный независимый head и нормальный controller. Перед reset требуется independently reviewed physical ARC-10 admission с fallback-control-v1. Никакой in-memory модели/ответов по expected, готовые файлы должны быть результатом настоящего job, а не сгенерированным тестом изображением ожидаемого сайта. Fault-команды — только существующий отдельный controlOrigin/свежий run permit, никогда production/VPS. Конкретной инфраструктуры пока нет и команды не запускаются.

Read-only наблюдения:

- `home-source-fixture`:sourcePageId/sourceRowId/homeItemId/assetId/sourceUrl/itemLabel/mainCanary и selectors(main,item,price,priceTab,priceBlock,technicalTokens). Селекторы — reviewed привязка к реальному HTML и всем активным защитным токенам формы, а не поля, добавленные сайту ради pass. parser не исполняет/не загружает HTML; JSfalse и abort routes/WS. Обязательные положительные исходные проверки исключают пустой/не тот блок. Собственная mainCanary всегда видима вне ценового блока.
- `home-source-item(itemId)` — actual-db собственное последнее представление:ID/label/href/priceText/assetId/visible и устойчивые sourcePageId/sourceRowId. Это семантическая проекция, не выбранная SQL-схема. После удаления связь не захватывается новым объектом; оставшийся sourceID не означает существующей страницы. Не сравниваем разрешённое предупреждение/признак lost-source как неизменный payload.
- `home-source-public-response(mode)` — actual-http GET главной через действующий normal/reserve front, status/body. Корректность содержимого проверяет собственный DOMParser в тесте, не bridge-вердикт. Нормализуются только пробелы, сравниваются текст/ссылки/изображения/фактическое отсутствие позиций, скрытые значения токенов не сравниваются побайтно. В reserve сравнивается позиция, а не изменившееся поведение формы с normal.
- `home-source-price-row(rowId)` — actual-db amount/revision; суммы канонические десятичные строки без валюты. `home-source-replacement(pageId)` — actual-db ID/url/published/amount нового реального объекта; `home-source-record(pageId)` — actual-db exists только по старому ID. Не подменять отсутствие страницы переадресацией/пустым ответом.
- `home-source-route-response(path)` — actual-http точного собственного URL, без скрытого follow redirect.
- `home-source-image-response(assetId)` — status, SHA256 и размер **реальных GET байтов**, не metadata/путь в БД. До/после должны соответствовать одному конкретному Asset; `asset` — существующее actual-db/files observation. Отдельный orphan действительно очищается, реальный used-файл не кандидат.
- `home-source-night-proof` — setId/createdByActualBuild/validationState=READY/sourcePageId с фактическими job/manifest/head свидетельствами; `home-source-served-set` — setId реально выбранного front набора, не desiredMode. Concrete provenance ещё требует независимого ревью.
- `home-source-business-state` — actual-db устойчивый before/after projection контента, Home representations/связей, историй, заявок/согласий и пользователей/прав/сессий, включая sourceExists=false. Не digest всей БД: readiness/log counters и служебные job times не считаются восстановлением бизнесданных. Чтение после фактической готовности перезапущенного компонента, без нового reset/seed/import/restore.

Действия — реальные owner UI/HTTP пути:existing prepare-delete-page/set-page-publication/create-page/publish-created-page/prepare-media-cleanup/confirm-media-cleanup-direct. Новые `confirm-page-delete-direct(page,confirmation,passwordRef)` сохраняет актуальное название/URL/состав истории/owner password требования и фактически удаляет только одну проверенную страницу. `update-home-source-price-direct(rowId,base,amount)` и `create-replacement-price-direct(pageId,amount)` — настоящие операции прайса. Никаких directDB мутаций вместо запросов, смены прав или обхода current revision/confirmation. Конкретные поля/эндпоинты ещё не выбраны и не реализуются на этапе7.

## Readiness

Приложение/bridge/bindings/controller/physical ARC-10 отсутствуют;7сценариев не исполнялись. Source/evidence flags требуют отдельного подтверждения при реальном подключении. Перечисление тестов/самопроверки инструмента не означают прошедшего AC. Старый сайт и VPS не изменяются. Этап7 остаётся в работе, этап8/production отдельно.
