# Редактор прайса: типы значений, границы и права

2026-10-30. Этап7, D-254/255/257 и пакет D-301/302/303/305/308. Источник:analytics-content-detail.md §2/AC-DTL-005, REQ012/016. Только acceptance/документ, без сайта/миграций/production API или изменений старого сайта/VPS.

`acceptance/price-editor.spec.js`:**25частичных сценариев** AT105, права также дополняют AT016.

- 6типов/значений:пусто, текст с числом, ноль, «от»,0.01,999999999.99. Пустое/текстовое не превращается в числовойноль; отсутствие числовойцены не запрещает строку. Денежные значения проверяются точными целыми копейками BigInt, без float/округления.
- 5полных отказов:−0.01/Infinity/−Infinity/NaN/1000000000.00. Послеотказа price/state/public неизменны, допустимая0.01 темже handler принимается. Не вводится запрет экспонентной записи/новая локализацияввода — эти сценарии не описаны решением.
- 6граництаблицы:500/501строка,32/33колонки,10000/10005ячеек. Для cellcap используются прямоугольные500×20 и435×23; обе в остальных пределах. Ровно10001 не используется, чтобы не подменить превышениеcellcap возможным отдельным отказом неравной длиныстрок. Нет нового правила допустимости raggedgrid. При превышении нет усечения; затеммаленький2×2прайс реально сохраняется.
- 4проверки названия500/501символ и текстовойячейки1000/1001; полное сохранение/полный отказ с positiveконтролем.
- 4права:owner; assignedemployee с прайсомвыключенным поумолчанию; assigned с отдельным разрешением; сотрудник с разрешением на назначеннуюPage пробует другуюPage. В отказных ветвях тотже payload принимаетowner. Право не выводится из наличия кнопки.

Специальные правила суммглавной/осей/классов/минимумаизтекста иустойчивыйID источника — отдельный набор координатора. Здесьнет новойформулы/тарифов/обязательностиценыкаждойстроки.

## Реальные данные и привязки

`price-editor-isolated-table` — собственная синтетическаяPageP-PRICE с существующейстрокой/ячейкой и начальнойценой, отличной от всех positivecases (например9.99), отдельным ownerdraft/SEO/URL/Asset и историей. S-EDIT назначен на этуPage, прайсdefaultoff. Для role=employee-assigned-on подготовлена отдельнаяреальная pricegrant этойPage. Для employee-other-page S-EDIT сохраняет assignment+pricegrant наassignedPageId, а fixture.pageId/rowId/cellId/selectors относятся к другой реальнойP-PRICE-OTHER без assignment/grant. Ownerроль не требует employeegrant. Realidentity/grants проверяются при concretebinding review, не моделируются UIметкой.

`price-editor-fixture`:targetpageId/rowId/cellId/assignedPageId и фиксированныеreviewedселекторы конкретного прайса/cell/label/table/bodyrows/allcells. Селекторы выбирают один действительныйпубличныйварианттаблицы, не дублируют desktop/mobile представления и не включают стороннийпрайс/служебныеheaderrows. Они привязываются к реальнойразметке без требованияdata-атрибутов/новогоhero. Body rowlabels входят в построенный cellmatrix как первая текстоваяячейка, не скрытая дополнительнаяколонка.

`price-editor-state(page)` — actual-db revision/row{id,label}/cell{id,kind,amount,text,from},history и protectedFields(url,h1,title,description,publicText,draftText,grants,assetIds). Это семантическаяпроекция, не SQLсхема/модель/выборframework. Moneyamount — точнаядесятичнаястрока фактическогоDecimal, не float и не ожидаемое значение из args. Неприменимые поля могут бытьnull/отсутствовать;empty.amount не имеет числового значения. На обычномupdate сохраняются row/cell ID и protectedfields. Новая Pagehistory допускается по обычному правилу; при отказе весь устойчивый state прежний.

`price-editor-public-response(page)` — actual-http GET готовойPage/status/rawbody, не HTMLизпереданногоexpected. Тест сам читает поле/table через инертныйDOMParser в JSfalseконтексте с blockednetwork/WS. Empty допускает неперсональныйplaceholder, но не числовой0; text сохраняет текст; money считывается с русскимcurrency/пробельнымиразделителями и comma/dotdecimal, включая «от». Это parser тестовогосвидетельства, не новый механизм округления/форматированияпродукта. Сложныеформаты/диапазоны рассматриваютсядругими пробами.

Действия (только names тестового адаптера):

- `price-editor-update-cell(page,rowId,cellId,base,cell)` — реальныйcurrent owner/employee POST к обычному handler прайса. Cellсемантика `{kind:'empty'}`, `{kind:'text',text}`, `{kind:'money',amount,from}` переводится в фактическиеформовые/JSONполя без очистки/валидациивдрайвере; Infinity/отрицательное/oversize должны действительно дойти досервернойпроверки. Это не новый endpoint продукта/не directDBзапись.
- `price-editor-update-label(page,rowId,base,label)` — реальныйредакторназвания существующейстроки, без новойIDпоизменениюподписи.
- `price-editor-replace-table(page,base,cells)` — реальный handlerполнойправкипрайса с переданнымtypedmatrix. Bindingне уменьшает массив/не вставляетнедостающиеячейки, проверкаграниц происходит приложением. ActualгенерацияIDновыхстрок/ячеек внутриобычнойоперации не является навязанной SQLсхемой.
- `price-editor-table-shape(page)` — независимыйactualDB counts rows/columns/cells и cellsDigest. Digest — SHA256 UTF8 JSON фактически сохранённойсемантическойматрицы в порядкеотображения:ключиtextcell kind,text; moneycell kind,amount(канонически0.01),from. ID/производныедаты исключены. Тест отдельнохэширует свойисходныйtypedmatrix и сопоставляетcontent; publicDOMcounts проверяютсяизrawHTML. Это не хэш ожидаемогоinput, возвращённый bridge.
- `price-editor-permissions` — actualidentity/grant projection assignedPageIds/priceGrantedPageIds. Секреты/пароли отсутствуют; прававыданные конкретнойPage не переносятся поодинаковомуназванию.

Наблюдения и адаптер не реализуют бизнесправила. Фактическиеapp/fixture/fields/selectors/revision/identity/decimalnormalization/hashprojections ещё должны пройти независимоеreview. Большие10kтаблицы/ответы должны укладываться в существующие транспортныебюджеты без усечения, а actualDB shape — boundedcount/hash без выгрузкивсехpayload вstdio. Никакихновыхпакетов/внешнихподключений/productionнастроек.

## Готовность и пределы

Для синтетической emptyячейки нет числовойподписи/сноски внутри самойячейки:допускается пустота/прочерк/инойнечисловойplaceholderбезназначенияконкретноготекста. Проверяетсяне тольконераспознаваниеполнойстрокипарсеромсуммы, но иотсутствиенумерическогоотображениявнутриэтойячейки; «Цена:0₽»/«0₽*» не проходят какякобыпустота. Примечания/номерастрок не включаютсяfixtureселекторомвсамуemptyячейку. Это проверкаэтоговектора, не требованиепереписатьстарыйконтент/всеUIplaceholder.

Приложения/bridge/bindings нет,25сценариев **не исполнялись**. Node syntax/collection не являются пройденнымиAC. ПолныеAT105/016, все priceварианты/нормализации/точное10001/race/restore/importmaxlength/SQLdecimalprecision/oldпрайсы и реальные8browserfamilies отдельно. ПолныйTEST-07/UX-07 не закрывается; этап8/productionтребуетотдельногосогласованиявладельца. Старыйсайт/VPS не трогались.
