# DEV-08F: публичные layout и прайс

Дата: 2026-11-09
Основание: завершённый DEV-08E / D-706 и существующая закрытая `page-content-v1` schema.

## Цель и граница

Показывать текстовые и ценовые блоки строго в сохранённом порядке `payload.layout`, без новой модели, запросов или универсального page builder. Media/protected nodes остаются отдельным следующим срезом и до него закрывают опубликованную страницу как `503`.

## Приёмочные сценарии

- `LAY-001`: text-блоки выводят только указанное schema field и точно в порядке layout; сохранённый rich HTML проходит прежний equality guard и не исполняется как Django template.
- `LAY-002`: price-блок сохраняет порядок columns/rows, row label и соответствие по стабильному column UUID; ragged rows дают пустую ненумерованную ячейку, а не ноль.
- `LAY-003`: text cell экранируется; amount форматируется из canonical decimal string без float: пробельные тысячи, запятая, `₽`, и `от` только при `from=true`.
- `LAY-004`: `0`, `0.01`, `999999999.99`, пустая и текстовая ячейки не смешиваются и не получают выдуманную цену.
- `LAY-005`: `price=None`, пустой layout и пустая таблица дают корректный public200 без выдуманного содержимого.
- `LAY-006`: image/protected_ref или text protected_nodes закрываются `503` до отдельного media renderer; UUID/private metadata не выводятся.
- `LAY-007`: ALIAS, ETag/coherent shared capture, HEAD/no-write/session и blank hidden200 сохраняются.
- `LAY-008`: projection bounded существующими schema limits и не создаёт schema/table/cache/dependency/background слой.

## Итог D-708

DEV-08F завершён, независимое ревью `APPROVED`, замечаний P1/P2/P3 нет. Реализованы только pure typed projection и существующие template/CSS: text/price следуют layout, Decimal форматируется без float, price text экранируется, а media/protected/unknown закрываются `503` до формирования ответа.

Приёмка: `public-layout` 15/15 и полный guard 258/258 PASS; Django check PASS, migrations no changes, diff-check clean. Первый расширенный focused-прогон прошёл продуктовые assertions, но teardown обнаружил одинаковую позицию четырёх тестовых страниц; fixture исправлен уникальными позициями и после изменившегося условия повторный прогон прошёл. Новых моделей, запросов, schema, cache, dependencies или background process нет. Media, gallery, SEO, формы, fallback, migration и production исключены.
