# TEST-08 fixture — аудит фактической готовности

Дата: 2026-11-15. Статус: **fixture plan BLOCKED by product content gap; execution not started**.

## Проверенная граница

Сопоставлены `docs/analytics-route-map.csv` и только утверждённые canonical packages/writers DEV-09B/E/G/H/I/J/K/M, DEV-10 и DEV-12. Никакие source snapshots не превращались в тестовые страницы и никакой новый content format не предполагался.

- реестр содержит 114 старых URL и один approved extra `MAP-115`;
- canonical page packages покрывают 98 старых MAP и `MAP-115`;
- runtime/alias contracts отдельно покрывают `MAP-017` (`?page=1`), `MAP-018` (`?page=2`) и старый wash URL `MAP-088`;
- итоговая честная готовность: 101/114 старых URL и extra `MAP-115`; отсутствуют 13 старых URL.

## Exact13 без product binding

| MAP | URL | Область |
|---|---|---|
| MAP-003 | `/partners` | legacy links |
| MAP-004 | `/actions` | actions/media |
| MAP-005 | `/reviews` | reviews; external embeds remain off |
| MAP-007 | `/contacts` | contacts/media; public form remains off |
| MAP-009 | `/direct-contact` | legacy text; intake remains off |
| MAP-033 | `/news/okazanie-dopolnitelnyix-uslug` | legacy news |
| MAP-039 | `/news/atcz-estakada-podklyuchila-mnogokanalnyij-telefon` | legacy news |
| MAP-044 | `/nash-servisnyij-czentr` | legacy empty shell |
| MAP-045 | `/news/priobretenie-podemnika-do-10-tonn-dlya-remonta-malotonnazhnyix-avtomobilej` | legacy news |
| MAP-049 | `/about` | legacy empty shell |
| MAP-078 | `/news/` | legacy news catalog |
| MAP-090 | `/garantii` | legacy text |
| MAP-097 | `/cctv` | legacy schedule text; camera embed remains off |

Эти MAP встречаются только в аналитических/дизайн-документах и source evidence; в `app/` для них нет canonical package или binding. Это согласуется с D-802: DEV-09L был остановлен как последовательность дорогих micro-packages, а remaining-content pass отложен до готовности gallery/media.

## Почему fixture нельзя подделать

TEST-08 group1 требует все 114 прежних path+query. Test-only создание 13 страниц прямо из CSV/source HTML:

- сделало бы тест зелёным при отсутствующем продукте;
- нарушило бы D-023 и запрет произвольного HTML/template/JS;
- добавило бы скрытый второй content pipeline или универсальный importer;
- смешало бы fixture implementation с незавершённой DEV-09 product work.

Поэтому утверждённый D-1090 plan остаётся планом приёмки, но его precondition «собранный fixture из существующих packages» пока невыполним. Fixture code/config/run не разрешены.

## Рекомендуемый no-bloat путь

Следующий bounded этап — отдельный scope remaining-content exact13:

1. переиспользовать существующие Page/Route/version/media/public projection contracts;
2. сгруппировать 9 простых legacy/news shell/text страниц одним closed grammar, а MAP-004/005/007/009 — только в уже утверждённых default-off границах без форм, iframe, внешней сети и сбора ПД;
3. не создавать generic importer/parser/ETL, новый model/migration/dependency/API/worker;
4. сначала зафиксировать exact content/media/parent/navigation contracts и приёмочные сценарии, затем independent scope/plan review и отдельное owner permission на product code;
5. только после готовности exact13 вернуться к минимальному TEST-08 fixture plan.

Docker, Foundation, тесты, Playwright, сеть, БД, product code и live не запускались/не менялись. Одна вспомогательная PowerShell-строка вывода завершилась ошибкой форматирования после уже полученных счётчиков; эквивалентный повтор не выполнялся, результат подтверждён отдельными read-only источниками.
