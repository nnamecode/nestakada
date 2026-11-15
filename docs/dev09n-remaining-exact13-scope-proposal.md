# DEV-09N — bounded remaining-content exact13

Дата: 2026-11-15. Статус: **scope proposal; product code not started**. Основание: D-023, D-027, D-032, D-209–D-217, D-802, D-927, D-1089–D-1091.

## Цель

Закрыть только 13 отсутствующих старых URL, которые блокируют честную TEST-08 fixture. Не возвращать отложенные формы, сбор ПД, внешние widgets, analytics, MAX/Telegram/QR или универсальный importer.

Новые model/migration/page kind не нужны: `Page.Kind` уже содержит `PARTNERS`, `DIRECTOR`, `NEWS_ARTICLE`, `EMPTY`, `NEWS`, `CONSTRUCTION`, `CAMERA`, `ACTIONS`, `REVIEWS`, `CONTACTS`.

## Рекомендуемая минимальная архитектура

Один новый closed canonical package exact13 и одно bounded расширение существующего `dev09_migration_apply.py`:

- fixed MAP/UUID/URL/kind/parent/position/title/H1 и source/artifact SHA;
- discriminated per-kind payload без произвольного HTML/template/JavaScript;
- существующие Page/Route/revision/state/draft/pin/reservation/audit/media-usage contracts;
- default-off UNIT boundary, all13-absent/all13-exact, mixed-state refusal, one transaction, late rollback, concurrency one-create/one-replay;
- один host validator для fixed authorities/caps/hashes и focused tests; без generic parser/ETL/management endpoint;
- writer создаёт hidden aggregates; persistent apply/publication/live остаются отдельными gates.

Это один product slice, а не 13 micro-packages и не второй content pipeline.

## Cohort A — exact10 legacy/news

`MAP-003/009/033/039/044/045/049/078/090/097` используют только существующий безопасный body renderer:

- `/partners` — exact текст и 6 ссылок;
- `/direct-contact` — сохранённый текст без формы, POST и сбора данных;
- `/news/` — catalog parent, три exact news children;
- `/nash-servisnyij-czentr` и `/about` — намеренно пустой main внутри обычного public shell;
- `/garantii` — exact under-construction paragraph;
- `/cctv` — exact schedule text без камеры, iframe или внешнего script.

News children имеют единственного parent `MAP-078`; остальные страницы — top-level children утверждённого корня. Exact sibling positions/UUID фиксируются в implementation plan из route authority до кода, без вычисления из пользовательского ввода.

## Cohort B — exact3 designed pages в базовом профиле

### MAP-004 `/actions`

- две утверждённые карточки: скидка 10% за первое посещение и воскресная скидка 7%;
- только два локальных pinned assets MED-0001/0002 с уже зафиксированными bytes/SHA;
- лента «Акция» — безопасная template/CSS-разметка, без растра с текстом и без JavaScript.

### MAP-005 `/reviews`

- десять карточек в утверждённом порядке и с написанием «видео-отзыв»;
- в base-MVP каждая карточка — обычная явная внешняя ссылка на соответствующее видео;
- `iframe`, `youtube-nocookie` embed, thumbnail download, cookie/storage/fetch и autoplay отсутствуют. Полноценные players остаются будущим DEV-30/external-consent этапом, а не скрытым toggle/framework сейчас.

### MAP-007 `/contacts`

- подтверждённые телефон `+7 (499) 110-25-52`/`tel:+74991102552`, адрес, часы, email и обычная ссылка построения маршрута;
- ровно пять локальных pinned images MED-0004–0008 в responsive static grid; no slider/viewer JavaScript в этом bounded slice;
- form controls, request intent/POST, Yandex map script/iframe, Instagram, MAX, Telegram и QR отсутствуют;
- будущая рабочая форма остаётся gated D-027/LEGAL/DEV-13 launch profile; отсутствие формы не заменяется неактивным макетом.

Такой base profile сохраняет полезный публичный контент и точные URL, но не создаёт внешних запросов при загрузке страницы и не собирает ПД.

## Публичная проекция

- Cohort A использует существующий generic public body без нового template branch.
- Cohort B получает один узкий kind-dispatch в существующем public template и kind-scoped CSS; JavaScript0.
- Header/Footer, breadcrumbs, navigation auto-inclusion, canonical/SEO, 404/405/503, cache/CSP и media authorization переиспользуются.
- Текст/URL из package всегда экранируются; разрешены только fixed internal/external links и existing typed media slots.
- Никаких runtime package reads, dynamic templates, raw stored HTML, iframe/script/style/event attributes.

## Приёмочные сценарии до implementation plan

| ID | Ожидаемый результат |
|---|---|
| N13-AC-001 | Host validator подтверждает exact13 MAP/URL/kind/parent/source SHA и exact7 local media SHA; missing/extra/reordered/changed authority закрывается до output. |
| N13-AC-002 | Package принимает только closed keys, fixed caps/UUID/URLs и per-kind profile; arbitrary HTML, script, iframe, event/style/template values отклоняются. |
| N13-AC-003 | Default-off/wrong environment/DB/user даёт files0/SQL0/writes0; enabled writer first verifies DB identity and existing root. |
| N13-AC-004 | All13 absent создаются атомарно; all13 exact replay writes0; mixed/extra/collision/late failure/concurrency не оставляют частичных rows/files. |
| N13-AC-005 | Exact10 legacy/news routes дают expected 200, H1/body/link facts; two empty-main pages remain intentional 200 shells; news hierarchy/navigation exact. |
| N13-AC-006 | Actions render exact2 cards/assets/text/order with local authorized media and no JS/external request. |
| N13-AC-007 | Reviews render exact10 ordered links/titles; iframe/script/fetch/storage/autoplay0 and no remote resource loads in HTML. |
| N13-AC-008 | Contacts render confirmed facts, tel link, route link and exact5 local images; form controls/POST intent/map embed/MAX/TG/QR/JS0. |
| N13-AC-009 | Header/Footer/breadcrumb/navigation/canonical/sitemap/robots and hidden/public behavior remain coherent; unknown query/method and malformed aggregate fail closed. |
| N13-AC-010 | Named focused suites only through `scripts/test-editor.ps1`; no wildcard/direct broad `manage.py test`, Playwright, real network, persistent apply or live publication. |

## Явно исключено

Universal importer/parser/ETL/page builder; new model/migration/dependency/API/cache/queue/worker/scheduler; form/PII/intake; YouTube/Yandex embeds; external image/video downloads; analytics/cookies; contact social links not supplied by owner; contact slider; editing arbitrary templates/JS; production import/publication/VPS.

## Gate владельца

`DEV09N-Q001`: утвердить рекомендованный no-bloat scope exact13 и базовое представление Reviews/Contacts выше. После ответа «продолжай» — independent scope review; только после `APPROVED` готовится minimal implementation plan и отдельное разрешение на код.
