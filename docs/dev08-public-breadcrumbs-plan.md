# DEV-08I: хлебные крошки из существующего public navigation snapshot

Дата: 2026-11-09
Основание: D-147, D-149–D-217, D-239/D-240, UX-07/D-235, завершённый DEV-08H/D-723.

## Цель и граница

Заменить временную служебную подпись имени над H1 на утверждённые хлебные крошки внутренних страниц. Крошки строятся только из уже захваченного и проверенного `PublicNavigationItem` snapshot того же `PublicSharedHost`; дополнительных SQL-запросов и второго дерева не появляется.

Каталоговые плитки и точные ссылки `/services/` зависят от DEV-09, галерея — от DEV-10, SEO — от DEV-11. Лёгкий аварийный 503 с подтверждённым телефоном относится к ручному HTML fallback D-592/CONTACT-01: отдельного отказоустойчивого snapshot телефона сейчас нет, поэтому env-настройка или дублирующий contact-store в DEV-08I не создаются. WASH, preview cards, works block, формы, production и перенос данных не входят.

## Приёмочные сценарии

- `CRUMB-001`: для опубликованной внутренней Page выводится один `<nav aria-label="Хлебные крошки">` непосредственно перед H1; временный `.public-name` больше не выводится.
- `CRUMB-002`: цепочка строится по `page_id → parent_id` только из immutable navigation snapshot, захваченного вместе с текущей Page; отдельного чтения Page/Route нет.
- `CRUMB-003`: все предки выводятся в порядке от видимого корня к текущей странице как проверенные внутренние ссылки; текущая страница выводится текстом без ссылки с `aria-current="page"`.
- `CRUMB-004`: PRIMARY и ALIAS одной Page дают одинаковую цепочку и primary-ссылки предков; redirect сохраняет прямой301 и крошки не строит.
- `CRUMB-005`: скрытый предок отсутствует, а опубликованный потомок использует уже promoted `parent_id` ближайшего видимого предка по D-240; реальное родительство и URL не меняются.
- `CRUMB-006`: имена автоматически экранируются шаблоном; HTML/template markers не исполняются, target берётся только из `_stored_target`-проверенного navigation DTO.
- `CRUMB-007`: отсутствие текущего page_id, дубликат page_id, отсутствующий заявленный parent, цикл либо неоднозначная цепочка закрывают всю опубликованную страницу503/no-store без частичного HTML. Hidden blank200, unknown404 и redirect301 обходят projection.
- `CRUMB-008`: корневая опубликованная Page получает только один current crumb; искусственная ссылка на саму себя и выдуманный «Главная» не добавляются. После DEV-09 реальный `/` появляется как обычный утверждённый предок там, где он задан деревом.
- `CRUMB-009`: CSS сохраняет перенос длинных названий, видимый focus для ссылок и разделители без включения их в accessible name; на ширине320px горизонтального overflow страницы нет.
- `CRUMB-010`: Header/Footer, top navigation `aria-current`, body layout/hero/media, ETag/304/HEAD, sessionless/no-write, exact404/503 и guard не регрессируют.

## Минимальная реализация

- В `content.public_shared` добавить frozen typed breadcrumb item и pure bounded projection из уже сохранённых `page`/`navigation`.
- `PublicSharedHost.body()` возвращает готовую tuple-цепочку вместе с прежними Page/navigation/media; DB capture и host digest не меняются, потому что исходный navigation snapshot уже входит в projection.
- Template выводит semantic nav/list перед H1; CSS добавляет только breadcrumb layout/focus/responsive правила.
- Проверки расширяют существующие public navigation/shared/http suites; новых suite runner, dependency или browser framework не требуется.

Новых model/schema/migration/query/cache/worker/dependency/background/state-machine слоёв нет. До product code требуется independent plan review.

## Решение D-725

Independent plan review — `APPROVED`, новых P1/P2/P3 нет. Подтверждены pure O(n)+O(depth) projection existing snapshot, одинаковая цепочка PRIMARY/ALIAS, promoted visible parent по D-240, validated PRIMARY links и fail-closed malformed chain до template. Разрешена реализация CRUMB-001–010 без новых runtime слоёв.

## Итог D-726

DEV-08I завершён; independent code review — `APPROVED`, новых P1/P2/P3 нет. Frozen breadcrumb DTO и pure map/parent walk вызываются после coherent Page/navigation capture и до media open; duplicate/missing current, missing parent и cycle закрываются503. Template использует semantic nav/ol, escaped links/text, text current с `aria-current` и `aria-hidden` separator; CSS фиксирует wrap и visible focus. Проверки: public-nav7/7 за0.500с, public-layout18/18 за0.590с, guard272/272 за306.756с; Django check0, migrations no changes, diff-check clean. Новых model/schema/migration/query/cache/worker/dependency/background/state-machine слоёв нет; production/VPS/старый сайт не затронуты.
