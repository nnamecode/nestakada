# DEV07-CLOSE-03 — результат исправления мобильной ширины

2026-11-01. По D-367 и [RP07-001–005](dev07-responsive-checks.md) CLOSE-03 завершён в ограниченной локальной области. Причина доказана DOM/A/B/A, минимальный CSS diff и инструмент прошли независимое ревью; verify5групп/45измерений успешен с первого запуска. DEV-07 около97%, этап8около20%; следующим остаётся CLOSE-04.

## Причина и исправление

Общая owner-навигация accounts/base.html содержит5ссылок. В manage.css она была flex-строкой без переноса. При viewport390 её clientWidth366, scrollWidth394, последняя ссылка доходила до405.9px, document scrollWidth406. На320/360/390 тот же дефект затрагивал owner dashboard, Header/Footer reads, owner editor/table и terminal UI. Employee dashboard/assigned editor/price-only без этой навигации уже помещались.

Временное constructed CSSStyleSheet правило на той же странице дало причинный A/B/A: document406→390→406, nav scroll394→366→394, flex nowrap→wrap→nowrap. После удаления временного листа baseline восстановился. Это диагностическое свидетельство DIAGNOSTIC_ONLY, не responsive PASS.

В продукт добавлена ровно одна строка в app/accounts/assets/manage.css:

```css
main>nav{flex-wrap:wrap}
```

Все1432 исходных байта сохранены, добавлено25байт; SHA256 нового файла `e1832996c64b92775087b038e807603690e3dda3dd6ac0af1f7d45df06329470`. Правило касается прямой общей навигации main. Clipping/overflow:hidden, перепроектирование редактора, изменения JS/шаблонов/данных/прав не применялись. Внутренняя прокрутка таблиц сохранена.

## Фактический verify

Обычный local_http/Nginx без QA URLConf/settings/image overlay. В verify нет временного CSS candidate. На каждой из ширин320/360/390/768/1280 проверены9экранных состояний:

| Группа | Состояния и результат |
|---|---|
| RP07-001 | Owner/employee dashboard, Header/Footer read:4состояния, все ссылки общей навигации в пределах экрана, Shared baseline неизменен. |
| RP07-002 | Owner/assigned editor:2состояния, toolbar/источник/поля/Check/Save доступны по ширине; права не подменяются. |
| RP07-003 | Price-only employee, прайс2колонки×3строки в RAM: на320 выполнена реальная горизонтальная прокрутка до последней ячейки; на360/390 она уже оставалась в конце, на768/1280 таблица помещается. Корень страницы не прокручивается горизонтально. |
| RP07-004 | Owner simple table, вставка и padding8 в RAM: таблица помещается на всех5ширинах, последняя ячейка доступна. Это не свидетельство переполнения сложной таблицы. |
| RP07-005 | Настоящая смена actor через logout/login и terminal Check: старое тело не отправлено, canary/поля очищены, сообщение и оставшиеся controls помещаются. |

Итого5групп PASS,45измерений; document/root width в каждом случае точно равна viewport, выходящих за экран controls0. Domain hash/version audit/Shared baseline неизменны. CSP/storage/inline/pageErrors/external request guards успешны, stderr0/failed=null.

Диагностика содержала45baseline наблюдений,18 из них с ожидаемым исходным overflow, и2дополнительных candidate/restored измерения. Эти47записей не суммируются с verify как количество приёмочных тестов. Диагностика и verify завершились с первого запуска каждый, без правок теста ради результата.

Root и независимый рецензент просмотрели6PNG: diagnostic editor390 baseline/candidate; финальные editor390/price320/terminal390/desktop1280. На мобильном ссылки переносятся, desktop остаётся одной строкой. Price320 показывает локально прокрученную таблицу, а не обрезание всего документа; terminal снимок без canary. Это Chromium viewport evidence, не физические телефоны и не полная TEST-10 browser/version матрица.

## Цепочка исходников и сохранность

Before run `22edc2a0-fc6f-4639-b219-ef9f10a77de9`,231app files, manifest SHA256 `2832ddd4478673c67c0882cea8c7afef3ca4404776d037417069148f7bbbc924`. After run `83135551-5ec5-46f3-8f9d-f7418335fdca`,231files, SHA256 `2d8186af6462e1856bd067b447d5a3b8098eb65d392f6ea9b6f51c8b7362f8c9`. Единственная дельта — accounts/assets/manage.css; оба immutable manifest и host/frozen hashes проверены независимо. Backend/другие JS не изменены, дополнительный backend-прогон из-за25CSS bytes не выполнялся. Прежние app782/base094/worker/ресурсные границы сохранены.

Финальный native run `4dc1874a-8530-45a5-9bdb-aaf9655f64c6`: cleanup closed, users/pages/versions/drafts/stages/pins/assets0; системный route и Shared baseline сохранены. Permanent identity tombstones711/192, operation receipts369, append-only audit885 не удалялись. Стенд остановлен, private files/named volumes сохранены. Старый сайт/VPS не затронуты; commit/push не выполнялись.

Локальные доказательства вне Git: work/dev07-responsive-20261101/{before-receipt.json,http-freeze.json,product-freeze.json,cohort-before.json,cohort-after.json,source-delta.json,diagnostic-summary.json,native-diag-first/host-report.json,native-diag-first/evidence/,native-verify-first/host-report.json,native-verify-first/evidence/,stop-final.txt,final-checks.json,final-preservation.json}. Неизменная fixture tools/editor_normal_http_fixture.py использована обоими запусками.

Остался CLOSE-04 — конечный normal-profile компонентный набор DEV-07 (Shared Apply, complex/history/restore, media и представительские MAX) и его ревью. TEST09/10, зависимые DEV и этап9/production этим не закрыты; публичный сайт/вся админка не объявляются полностью адаптивными по этим9состояниям.
