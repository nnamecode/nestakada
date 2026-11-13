# DEV-09M: объединённый остаток страниц услуг

Дата: 2026-11-13. `DEV09M-Q001=1`–`Q004=1` утверждены владельцем. Область содержит 25 точных URL, 24 объекта Page и 25 Route. D-952: repeat data review P2=1 owner-paused after second MAP015 header finding; other findings closed, writer code не начат. Recommended Q005 literal-only patch.

## Пауза D-944

При чтении существующих планов второй раз повторена эквивалентная Windows-ошибка `rg`: wildcard был передан внутри path argument (`app/content/test_dev09*` / ранее `docs/*selection*.md`), и Windows вернул «Синтаксическая ошибка в имени файла, имени папки или метке тома». Оба вызова успели вернуть другую нужную read-only выдачу, файлов не меняли, но третья однотипная попытка запрещена.

Проверено: exact25 approval D-943 сохранён; product code/package/DB/foundation не начаты. Безопасное возобновление после owner response: использовать literal directory `app/content` и только glob filters `-g "test_dev09*.py" -g "dev09*.py"`, затем завершить acceptance/plan. Альтернатива — перечислить точные файлы из уже полученного `rg --files` списка.

## Проверенный остаток

Сверены pinned `docs/analytics-route-map.csv` (115 строк) и принятые packages DEV-09B/E/G/H/I/J/K + DEV-10 gallery. Regex-инвентаризация package MAP IDs дала 75 покрытых строк и 40 формально оставшихся.

Из этих 40:

- MAP-017/018 — query-состояния gallery root/page2, уже функционально закрытые DEV-10 и не требующие второго migration package;
- MAP-004 actions, MAP-005 reviews и MAP-007 contacts — отдельные публичные области; reviews отложен COOKIE-Q001, contacts зависит от LEGAL, actions требует отдельной продуктовой сверки;
- 10 legacy URL без утверждённого дизайна: MAP-003/009/033/039/044/045/049/078/090/097;
- остаются ровно 25 обязательных service URL с утверждёнными artifacts/структурой.

## `DEV09M-Q001=1` — единый exact25 URL / exact24 Page

### Кузовная ветвь, 12 URL / 12 Page

MAP-010 parent `/services/kuzovnoj-remont/` и exact11 children MAP-019–029. Parent и дети создаются только одной атомарной группой; children раньше parent не появляются.

### Остальные сложные услуги, 13 URL / 12 Page

- MAP-015, MAP-016, MAP-032, MAP-038, MAP-083 — «Другие услуги»;
- MAP-041 — «Плановое ТО»;
- MAP-058, MAP-068, MAP-069, MAP-089 — «Ремонт»;
- MAP-073 — «Диагностика»;
- MAP-115 canonical `/services/avtomojka` и MAP-088 legacy exact-200 alias `/services/drugie-uslugi/avtomojka` — один Page автомойки и два Route, с canonical на MAP-115 по уже принятой D-822 SEO-схеме.

## Правила без раздувания

1. Расширить один существующий bounded DEV-09 host validator/writer; не создавать новый importer, model, migration, API, cache, worker, scheduler или runtime service.
2. Один canonical package exact24 Page / exact25 Route с двумя внутренними группами (bodywork12 + complex12 Page), но одна implementation/review chain вместо новых микропакетов.
3. Источник сохраняет обязательные старые тексты, цены и точный порядок по D-023. Approved artifact задаёт визуальную структуру. Если artifact пропустил цену (MAP-038/073), source-authoritative price возвращается, а не исчезает.
4. Multi-table/interleaved/surcharge/nested-heading структуры описываются закрытой per-page последовательностью разрешённых paragraph/heading/list/table blocks. Source/artifact HTML целиком не импортируется; templates/JS/unknown tags/attributes не исполняются.
5. Использовать существующие Page/version/Route/content schema и sanitizer. Таблицы генерируются code-owned renderer из проверенных literal cells; произвольный HTML из source не сохраняется.
6. Все24 Page остаются hidden. Persistent apply, publication, grants, production/live и изменение старого сайта не входят.
7. Новые иллюстрации и public enablement не входят в content pass. Gallery originals не затрагиваются. Media slots добавляются позже по D-025, не копируются из source как обход решения.
8. All24 Page + all25 Route absent → одна atomic create; all24 Page + all25 Route exact → zero-write replay; mixed/collision/unknown child/late failure/concurrent writer → полный отказ/rollback.
9. Exact URL, parent/position, h1, source/artifact SHA, block order, table count/rows/cells and full aggregate фиксируются до кода. Caps и cap+1 tests обязательны.

## Почему не предлагается меньше

DEV-09L уже доказал нерентабельность восьмого микропакета ради двух страниц и новых grammars. После DEV-10 зависимости gallery/media больше не оправдывают дробление service content. Exact25 даёт достаточный однородный объём, чтобы один раз реализовать закрытые block variants и завершить обязательный service remainder.

## Почему не предлагается больше

Actions/reviews/contacts имеют самостоятельные product/legal/cookie gates. Legacy10 не имеют утверждённого дизайна, а две страницы вообще пусты; их включение заставило бы придумывать содержание. Gallery query states уже реализованы DEV-10. Добавление этих15 строк не завершит их зависимости, но размоет проверяемую область.

## Следующие gates после утверждения

1. Точные acceptance IDs и per-page structural manifest.
2. Минимальный implementation plan с exact files/commands/caps/rollback.
3. Независимое plan review.
4. Отдельное owner approval product code.

`DEV09M-Q001=2`: продолжить новые микропакеты или включить внешне заблокированные/legacy страницы сейчас. Не рекомендуется из-за повторного overhead и необходимости выдумывать незакрытые требования.
