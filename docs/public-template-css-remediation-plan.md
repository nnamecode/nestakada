# План исправления публичных шаблонов и CSS

Дата: 2026-11-16. Основание: D-1212/D-1213 и прямое утверждение владельцем family architecture и наследования маршрутов без standalone v3-экрана.

Статус: **SUPERSEDED D-1217; НЕ ИСПОЛНЯТЬ.** Владелец решил сначала упростить общую runtime-архитектуру. Product/test code по этому плану не начинался. Документ сохраняется только как историческая гипотеза, inventory требований и источник замечаний D-1215; новый template/CSS plan составляется после утверждения и реализации упрощённой архитектуры.

## 1. Цель

Заменить неявную generic-композицию одним закрытым серверным реестром презентаций и небольшим числом типизированных семейств. Внешний вид берётся из D-235/v3, содержимое — из существующей current revision. Точные URL, тексты, media identity, Header/Footer, CSP, роли, версии и публикация не переписываются.

## 2. Закрытая карта всех `Page.Kind`

| `Page.Kind` | Семейство | Вариант | Визуальный источник |
|---|---|---|---|
| `home` | `home` | `v4` | exact v4/v3 |
| `services_master_catalog` | `service_catalog` | `master` | наследует approved catalog grid; v3 entry был redirect-placeholder |
| `service_catalog` | `service_catalog` | `section` | exact v3 service-grid |
| `service_section_overview` | `service_content` | `overview` | exact v3 hero/content/navigation/works |
| `service_detail` | `service_content` | `detail` | exact v3 hero/content/price-optional/closing/works |
| `articles_catalog` | `editorial` | `catalog` | exact v3 article-grid |
| `article` | `editorial` | `detail` | exact v3 plain hero/content/works |
| `contacts` | `contacts` | `default` | exact v3 contact-shell/gallery с поздними external/form gates |
| `reviews` | `reviews` | `default` | exact v3 3/2/1 cards без automatic iframe по D-936 |
| `actions` | `actions` | `default` | exact v3 promo-card |
| `gallery_catalog` | `gallery` | `catalog` | exact v3 album-grid/modal |
| `gallery_album` | `gallery` | `album` | наследует gallery visual language; standalone no-JS content remains |
| `legacy_partner_links` | `legacy_plain` | `partner_list` | approved internal shell + stored list |
| `legacy_director_message` | `legacy_plain` | `text` | approved internal shell + stored text |
| `legacy_news_article` | `editorial` | `legacy_detail` | наследует approved article detail |
| `legacy_empty_main` | `legacy_plain` | `empty` | approved internal shell; пустота сохраняется, текст не выдумывается |
| `legacy_news_catalog` | `editorial` | `legacy_catalog` | наследует approved article catalog |
| `service_wash_legacy_alias` | `service_content` | `wash_alias` | presentation актуальной автомойки, exact old URL сохраняется |
| `legacy_under_construction` | `legacy_plain` | `text` | approved internal shell + stored text |
| `legacy_camera_schedule_text` | `legacy_plain` | `camera_text` | approved internal shell; external camera embed не добавляется |

Реестр обязан покрывать множество `Page.Kind.values` ровно, без generic fallback. Template/CSS names — константы кода. Payload, editor input и база данных не задают имя шаблона, CSS или JavaScript.

## 3. Целевая композиция

1. `public_page.html` остаётся document shell: SEO/head, approved shared Header/Footer и server-selected body include.
2. Breadcrumbs и H1 переходят в family partial: на approved home breadcrumbs отсутствуют, на внутренних страницах присутствуют.
3. Existing typed `text/hero/price/image`, gallery DTO, home DTO и contacts profile переиспользуются; для card/catalog/special layout добавляются только pure read projections из уже сохранённых данных.
4. Family include выбирается только из frozen registry. Missing/unknown family или несовместимый DTO даёт существующий closed 503.
5. Existing `/static/public.css` сохраняется как base/compatibility asset на время перехода. Семейные stylesheet выдаются только из allowlist и подключаются серверным presentation DTO. После полного GREEN base очищается от доказанно мёртвых family rules.
6. Никакого bundler/framework/package/CDN. CSS/JS остаются локальными; CSP не ослабляется.

## 4. Точная область файлов

Ожидаемая область после review:

- новый pure registry/projector в `app/content/public_presentation.py`;
- `app/content/public_views.py` — выбор presentation и закрытая передача template/assets;
- `app/estakada/urls.py` — только allowlisted family CSS endpoint, если review не выберет explicit fixed routes;
- `app/content/templates/content/public_page.html`;
- новые family partials в `app/content/templates/content/public/`;
- `app/content/public.css` как base во время миграции;
- family CSS в `app/content/assets/public/` либо рядом с существующим asset по итогам review;
- новые focused tests `app/content/test_public_presentation.py` и `app/content/test_public_families.py`;
- существующие public/home/gallery/navigation tests меняются только при замене устаревшего structural oracle эквивалентным новым.

Не входят models, migrations, editor/save protocol, page versions, auth/admin UI, dependencies, external network, live/VPS/deploy и content rewrite.

## 5. Baseline до первого product patch

Перед изменением runtime сохраняется машинная baseline для всех 115 canonical представлений:

- status и redirect target;
- normalized visible text digest без shared Header/Footer;
- ordered internal href set и exact primary URL;
- contextual media `(file identity, page, slot)` set;
- page kind/family mapping;
- наличие approved special markers у representative routes.

Baseline не содержит секретов, PII, оригиналы файлов или полный HTML и не отправляется наружу. Временный результат остаётся вне Git; в Git фиксируются только агрегаты и ожидаемые digest/ID, если они не раскрывают закрытые данные.

## 6. Приёмочные сценарии до кода

### Registry и fail-closed

- `PUBARCH-AC-001`: все 20 `Page.Kind` и все 115 canonical представлений получают ровно одно family/variant; unknown/missing/duplicate mapping закрывается до render.
- `PUBARCH-AC-002`: template, stylesheet и optional script принадлежат frozen allowlist; stored HTML/payload/URL не могут выбрать или изменить asset/template name.

### Общий shell

- `PUBARCH-AC-003`: Header exact-six и order/labels сохраняются, logo ведёт `/`, Footer един для всех families, internal pages имеют approved breadcrumbs, home breadcrumbs не имеет.
- `PUBARCH-AC-004`: SEO/CSP/cache/GET/HEAD/405/blank/unavailable/redirect contracts не меняются; session/write на anonymous GET не появляются.

### Содержимое и медиа

- `PUBARCH-AC-005`: baseline visible text, exact internal href и publication result совпадают до/после для всех 115 представлений; два legacy-empty остаются пустыми.
- `PUBARCH-AC-006`: contextual media set совпадает; gallery originals byte identity не меняется; wrong page/slot остаются closed.
- `PUBARCH-AC-007`: home exact21 contextual media отвечают 200 после закрытия D-1210; bare/wrong URLs не допускаются.

### Семейства и утверждённый дизайн

- `PUBARCH-AC-008`: home содержит exact approved nine-block order и responsive family markers без external iframe/script/form activation.
- `PUBARCH-AC-009`: service master/section catalogs используют approved card grid; service overview/detail используют hero/content/navigation-or-price/closing/works согласно variant, без HTML-shape inference.
- `PUBARCH-AC-010`: editorial catalog/detail и legacy news используют approved article grid/detail; actions/reviews/contacts используют свои approved typed structures, а не селекторы по случайному `ul/li/a`.
- `PUBARCH-AC-011`: gallery catalog/page2/modal и 17 standalone album URLs используют одно gallery family; no-JS exact links и originals сохраняются.
- `PUBARCH-AC-012`: partner/director/empty/construction/camera используют approved internal shell; camera/external embeds и новый текст не создаются.

### Responsive и очистка

- `PUBARCH-AC-013`: representatives на 1440/1024/736/390/320 имеют root `scrollWidth <= clientWidth`; Header/menu, tables, cards, gallery, images, request reserve и Footer не обрезаны.
- `PUBARCH-AC-014`: visual evidence покрывает минимум один route каждого family и каждый distinct variant; 115 HTTP routes проверяются автоматически, а не 115 ручными скриншотами.
- `PUBARCH-AC-015`: selector/template удаляется только после rendered-corpus proof, focused regression и independent review; stale `.public-home-*` не остаётся после final cleanup.
- `PUBARCH-AC-016`: owner/employee save сохраняет тот же payload; presentation fields отсутствуют в редакторе и executable source не появляется.

## 7. Representative visual matrix

| Variant | Route |
|---|---|
| home/v4 | `/` |
| service catalog/master | `/services/` |
| service catalog/section | `/services/remont/` |
| service overview | `/services/kuzovnoj-remont/` |
| service detail without assumed price | `/services/kuzovnoj-remont/polirovka-kuzova` |
| service detail with price | `/services/remont/remont-podveski` |
| wash current/legacy | `/services/avtomojka`, `/services/drugie-uslugi/avtomojka` |
| editorial catalog/detail | `/articles/`, `/articles/remont-akpp` |
| legacy news catalog/detail | `/news/`, `/news/okazanie-dopolnitelnyix-uslug` |
| actions | `/actions` |
| reviews | `/reviews` |
| contacts | `/contacts` |
| gallery catalog/page2 | `/gallery-of-works/`, `/gallery-of-works/?page=2` |
| gallery album | `/gallery-of-works/audi-a8-kuzovnoj-remont` |
| partner/plain | `/partners`, `/direct-contact` |
| empty | `/about`, `/nash-servisnyij-czentr` |
| construction/camera | `/garantii`, `/cctv` |

Каждый route проверяется на пяти ширинах только если его variant отличается. Общие siblings покрываются HTTP/fingerprint sweep; это ускорение не сокращает функциональный охват.

## 8. Порядок реализации и gates

1. `PUBARCH-IMP-001`: independent review этого плана; product/test code запрещён до `APPROVED`.
2. `PUBARCH-IMP-002`: baseline + expected RED registry/family tests.
3. `PUBARCH-IMP-003`: frozen registry/document shell/base CSS без переноса family visuals; focused GREEN и regression.
4. `PUBARCH-IMP-004`: home и service families; D-1210 закрывается внутри home gate, не обходится.
5. `PUBARCH-IMP-005`: editorial/actions/reviews/contacts.
6. `PUBARCH-IMP-006`: gallery и legacy inheritance.
7. `PUBARCH-IMP-007`: 115-route fingerprint/HTTP sweep, five-width representative matrix, full relevant regression.
8. `PUBARCH-IMP-008`: dead branch/CSS cleanup, repeat sweep и independent final review.

Каждый IMP имеет собственный expected RED, минимальный patch, fresh GREEN и diff review. Ошибка не исправляется массовой заменой соседнего семейства. Ни один промежуточный GREEN не означает live/deploy.

## 9. Review checklist

- Карта покрывает ровно 20 model kinds и 115 canonical representations.
- 29 routes без full v3 не получают самовольный новый дизайн.
- Dynamic include/asset не управляется данными страницы.
- Поздние privacy/legal/media решения имеют приоритет над HTML v3.
- Baseline сравнивает содержимое, URL и media, а не текущий ошибочный внешний вид.
- В плане нет нового framework, bundler, model, migration или внешней зависимости.
- Visual matrix доказывает geometry, а не только наличие media query строки.
