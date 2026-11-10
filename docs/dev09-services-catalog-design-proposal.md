# DEV-09E: полный макет каталога `/services/`

Дата: 2026-11-09. Статус D-754: independent design review `APPROVED`, P1/P2/P3 нет; требуется явное согласование владельца до product code. Browser visual QA не выполнялась по решению владельца.

## Основание

MAP-002 сохраняет точный `/services/`, source SHA `e61fbaffbfea280abf1c9d3c1017174b8c22323bcc149c88e8bb013cbf9e1da7`, H1 `Услуги и цены автосервиса "Эстакада"` и исходные 58 ссылок. UI-S052/D-307 уже утверждает поведение: самостоятельный 200, common header/breadcrumbs/H1/catalog/footer, без meta-refresh, выдуманного hero и нового вводного текста. READY-06 остаётся открыт только из-за отсутствия полного визуального артефакта.

## Предлагаемый макет

Standalone artifact: `work/services.html`.

- Переиспользованы header/footer, typography, focus styles, widths и `.service-tile` из принятого `work/remont.html`; новый design system не создан.
- Main содержит только breadcrumbs `Главная / Услуги и цены`, exact source H1 и пять исходных групп в исходном порядке.
- Корень каждой группы — самостоятельная широкая кликабельная heading-card с orange top border, dark background и arrow. Под ним существующая grid плиток прямых услуг.
- Группы содержат соответственно 12/10/18/11/7 ссылок вместе с корневой heading-card: `Кузовной ремонт`, `Плановое ТО`, `Ремонт`, `Диагностика`, `Другие Услуги`; итого ровно 58.
- Desktop child grid — 4 колонки, tablet — 3, mobile — 1. На mobile heading уменьшается, но порядок и полный текст не скрываются.
- В main нет hero, изображений, описательного текста, цен, форм, видео, gallery cards или новых CTA. Нумерация и стрелки являются presentation-only; screen reader получает названия ссылок.
- Все exact old paths сохранены, включая различия trailing slash и исходные написания. Никакого исправления орфографии/URL на этом этапе нет.
- Header menu script унаследован только как поведение standalone mockup; это не новый runtime contract и не разрешение product implementation.

## Почему это рентабельно

Один согласованный catalog unlocks57 service routes. Альтернативные remaining branches сейчас дороже: actions зависит от banner media, reviews — от external video policy, contacts — от media/form/legal gates, gallery — от DEV-10/316 media evidence/17 album designs. До согласования MAP-002 package/writer не расширяются.

## Приёмочные сценарии дизайна

- `SVCAT-001`: source snapshot и MAP/RTE SHA/locator/H1 подтверждены; mockup не становится источником content truth.
- `SVCAT-002`: ровно5 groups и58 clickable service paths; decoded names, exact paths и order совпадают source без нормализации.
- `SVCAT-003`: `/services/` представлен самостоятельной страницей, не redirect/meta-refresh/home fragment.
- `SVCAT-004`: main содержит common breadcrumbs, exact H1 и catalog; hero/image/intro/form/video/gallery/price отсутствуют.
- `SVCAT-005`: root group links и child links визуально различимы, keyboard focus видим, arrows/numbers скрыты от accessibility tree как decoration.
- `SVCAT-006`: grid имеет4/3/1 columns на desktop/tablet/mobile; длинные названия не обрезаются CSS ellipsis или fixed height.
- `SVCAT-007`: header/footer переиспользуют утверждённый visual language; новых global components/dependencies/fonts/scripts нет.
- `SVCAT-008`: structural check подтверждает groups5/links58/mismatch0/main images0/hero0/exact H1/responsive rules; `git diff --check` clean.
- `SVCAT-009`: это design artifact, не Django template и не production deploy. Product plan/code начинается только после явного owner approval.

После owner approval отдельный DEV-09E implementation plan должен выбрать минимальную plain-data catalog schema и переиспользовать existing hidden UNIT-only package/writer; media и content дочерних service pages в этот первый catalog slice не смешиваются.
