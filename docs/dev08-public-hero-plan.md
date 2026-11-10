# DEV-08H: main image hero утверждённых service-страниц

Дата: 2026-11-09
Основание: D-148–D-207, D-208, D-235, D-257, завершённый DEV-08G / D-718.

## Цель и граница

Подключить существующее `main_image` только для утверждённых типов внутренних service-страниц: `service_detail` и содержательный `service_section_overview`. При наличии main image ровно один обычный layout-блок `intro_text` проецируется на своём сохранённом месте как combined hero: тематическое изображение и полупрозрачная светлая вводная панель. Так сохраняются и D-148, и owner-controlled layout order.

`service_catalog`, `services_master_catalog`, `service_wash_legacy_alias`, статьи, главная и специальные страницы не получают универсальный hero. D-236 подтверждает фото и прайс автомойки, но не утверждает single-intro overlay composition; wash остаётся отдельным presentation-срезом. `preview_image` остаётся только будущим карточкам/превью. Каталоги без hero по D-171/D-200 не меняются. Breadcrumbs, service tiles, works block, SEO, перенос данных, gallery, forms и production не входят.

## Приёмочные сценарии

- `HERO-001`: у service detail/section с `main_image` и ровно одним непротектированным layout `intro_text` на месте этого блока выводится один `<section class="public-hero">`; последующие text/price/image blocks сохраняют точный layout order.
- `HERO-002`: hero использует только server-selected `/public-media/<FileUUID>/?page=<PageUUID>&slot=main_image`; AssetUUID, storage key, source URL и private metadata в HTML отсутствуют.
- `HERO-003`: `alt` экранируется как текст; closed alignment `left|center|right` управляет только object-position; nullable positive width/height становятся числовыми attributes, CSS удерживает изображение и панель в адаптивном контейнере.
- `HERO-004`: intro rich HTML проходит прежнюю equality/allowlist проверку и только затем передаётся как trusted HTML; template markers не исполняются. Protected intro, duplicate/missing intro при main image, неизвестная структура и unsafe HTML закрывают всю страницу503 без canary/FileUUID.
- `HERO-005`: service-страница без `main_image` сохраняет обычный intro text block. Main image у неутверждённого page kind, включая wash, не рисуется и не получает публичный media-доступ. Каталоги D-171/D-200 остаются без hero; preview image никогда не становится hero.
- `HERO-006`: resolver public-media принимает contextual slot `main_image` только у published current Page разрешённого kind, с exact current payload reference и exact `AssetUsage(current_page, PageUUID, main_image, AssetUUID)`. Wrong kind/page/slot, preview, old/unpublished/orphan отказываются404.
- `HERO-007`: READY/exact-one variant, is_legacy↔kind, MAIN-WebP/LEGACY_PUBLIC-JPEG|PNG и physical SHA/open остаются теми же, что DEV-08G. Missing/corrupt/ambiguous media закрывает page503 до template/partial HTML.
- `HERO-008`: main descriptor входит в существующий bounded DB capture → FS verify outside transaction → DB recapture/full stamp. Revision/publication/usage/file drift даёт один retry, затем503; initial invalid media остаётся404.
- `HERO-009`: общий ceiling остаётся 64 slots/64 unique files на Page и включает main image. 63 standalone + main работают; 64 standalone + main закрываются503 до `_open_media`. SQL queries остаются batch и bounded `unique assets + 1`, без N+1.
- `HERO-010`: queryless shared media, standalone embedded images, ALIAS, hidden blank200, redirects/unknown, ETag/304/HEAD, sessionless/no-write, text/price и guard не регрессируют.

## Минимальная реализация

- Общий immutable set разрешённых hero page kinds хранится рядом с public Page read policy и используется host capture, body projection и contextual media resolver.
- Существующий `PublicSharedHost` собирает `main_image` в тот же bounded slot→file mapping; новый query/storage/streaming слой не создаётся.
- Pure `project_body` выдаёт typed `PublicHeroBlock` вместо единственного обычного intro block. Template получает только frozen contextual URL и проверенные поля.
- Существующий `/public-media/<FileUUID>/` расширяется exact slot `main_image`; queryless shared contract не меняется.

Новых model/schema/migration/cache/worker/dependency/background/state-machine слоёв нет. До product code требуется independent plan review.

## Статус D-720

Первый plan review вернул один P1 без P2/P3: D-236 не утверждает для `service_wash_legacy_alias` именно single-intro overlay hero. Минимальная remediation исключает wash из HERO_KIND и оставляет его main image непубличным до отдельного presentation-решения. Scope DEV-08H теперь только `service_detail` и `service_section_overview`; repeat independent plan review обязателен до кода.

## Решение D-721

Repeat independent plan review `APPROVED`, новых P1/P2/P3 нет. WASH полностью исключён из hero и contextual main access; HERO-001–010 согласованы для `service_detail` и `service_section_overview`. Разрешена bounded реализация без новых runtime слоёв.

## Статус D-722

Focused implementation после одного fixture-only исправления PASS20/20 за121.307с; shared-public10/10 PASS96.752с. Independent code review вернул один P2, P1/P3 нет: absolute `.public-hero-copy` внутри `overflow:hidden` могла обрезать длинный разрешённый intro. Remediation: hero flex/grid, image остаётся absolute background, copy возвращается в normal flow и расширяет min-height; добавить long paragraph/list render и CSS contract oracle. Остальная реализация принята без замечаний.

## Итог D-723

Clipping remediation завершена: `.public-hero` использует flex, `.public-hero-copy` остаётся в normal flow и увеличивает высоту секции; длинный intro из 24 абзацев и списка проходит полный schema/current HTTP render, таблицы имеют ограниченный горизонтальный scroll. Repeat independent code review — `APPROVED`, новых P1/P2/P3 нет. Итоговые проверки: public-image20/20 за125.329с, shared-public10/10 за96.857с, public-layout18/18 за0.463с, guard271/271 за297.483с; Django check — 0 issues, `makemigrations --check --dry-run` — no changes, `git diff --check` — PASS. Exact kind/context/coherence/physical checks, общий ceiling64, SafeString boundary и exclusion WASH/article/catalog/preview сохранены. Новых model/schema/migration/cache/worker/dependency/background/state-machine слоёв нет; production/VPS/старый сайт не затронуты.
