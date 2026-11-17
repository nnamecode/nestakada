# Аудит публичных шаблонов и CSS

Дата: 2026-11-16. Статус: статический bounded audit D-1212 завершён; продуктовый код не изменён.

## 1. Границы и источники истины

Аудит отвечает только за архитектуру публичного HTML/CSS и её соответствие утверждённой поставке. Тексты, точные URL, права, версии, публикация, media authorization и серверная безопасность не перепроектируются.

Порядок источников истины:

1. D-235 и `deliverables/estakada-static-site-new-2026-10-29-v3/` — утверждённая визуальная поставка главной и внутренних страниц.
2. `docs/design/public-light-v4-template.html` — точный эталон композиции главной.
3. Более поздние правила имеют приоритет над статическим макетом: D-936/D-941 не разрешают автоматически загружать внешние iframe/scripts и собирать реальные данные до legal/cookie/ready gate; D-1202 требует exact-six Header; D-1203 — внутреннюю ссылку логотипа `/`; D-1209/D-1210 сохраняют contextual media authorization.
4. Текущие `PageRevision`, Route и media bindings — источник содержимого и точных адресов, но не образец оформления.

## 2. Проверенная инвентаризация

| Факт | Значение |
|---|---:|
| Текущие страницы по D-1199 | 112 |
| Точные представления в canonical route map | 115 |
| Типы `Page.Kind` | 20 |
| HTML `index.html` в утверждённой v3-поставке | 91 |
| Полные v3-страницы | 84 |
| Redirect-placeholder в v3 | 7 |
| Route-map строк с прямым v3 markup | 86 |
| Route-map строк без v3-экрана | 22 |
| Route-map строк только с redirect-placeholder | 7 |

Разница 112/115 ожидаема: route map отдельно учитывает query/alias-представления галереи и автомойки. В v3 84 физических полных страницы обслуживают 86 route-map представлений.

Текущий runtime:

- один общий `content/public_page.html`, 8 136 байт и 34 `if/elif`;
- один отдельный include главной `_public_home.html`;
- один `content/public.css`, 26 541 байт, 90 уникальных классов и 16 media-query блоков;
- отдельный `public-shared.css`, 5 681 байт и 4 media-query блока, для Header/Footer;
- в `public.css` остаётся 3 201 байт старых `.public-home-*` правил, хотя текущая главная использует `.es-home/.es-*`;
- утверждённая v3-поставка содержит 18 CSS-вариантов среди 84 полных страниц. Их нельзя копировать как 84 независимых stylesheet: общий слой надо извлечь один раз, отличия оставить внутри семейств.

## 3. Фактические семейства

| Семейство | Route-map представлений | Типы | Утверждённый источник |
|---|---:|---|---|
| Главная | 1 | `home` | точный v4/v3 экран |
| Каталоги услуг | 3 | `services_master_catalog`, `service_catalog` | два точных каталога; `/services/` в v3 только redirect-placeholder |
| Страницы услуг | 58 | `service_section_overview`, `service_detail` | точные v3 экраны для всех 58 |
| Статьи и новости | 23 | `articles_catalog`, `article`, `legacy_news_catalog`, `legacy_news_article` | 19 точных экранов; 4 legacy-news без v3 |
| Специальные | 3 | `actions`, `reviews`, `contacts` | три точных самостоятельных экрана |
| Галерея | 20 | `gallery_catalog`, `gallery_album` | каталог точный; 6 album redirect-placeholder и 11 album без v3 |
| Legacy plain | 6 | partner/director/empty/construction/camera | v3 отсутствует |
| Legacy alias автомойки | 1 | `service_wash_legacy_alias` | должен переиспользовать семейство актуальной автомойки |

Эта группировка покрывает все 115 canonical route-map строк. Для 29 строк без самостоятельного готового экрана нужен не новый произвольный дизайн, а утверждённое правило наследования ближайшего семейства.

## 4. Подтверждённые проблемы

### AUD-F01 — универсальный runtime-шаблон не выражает утверждённые семейства

`public_page.html` различает главную, каталог галереи, альбом и несколько wrapper-классов, а остальные типы собирает из общих блоков `text/hero/price/image`. В утверждённой поставке существуют отдельные композиции `service-grid`, `article-grid`, `promo-card`, `video-card`, `contact-shell`, `album-grid`, `closing` и `works`. Generic renderer не может восстановить их только CSS-правилами.

### AUD-F02 — оформление зависит от случайной внутренней HTML-формы текста

Примеры:

- каталог услуг определяется сочетанием `page_kind + main_text`;
- reviews превращаются в карточки селекторами `.public-text-main_text ul/li/a`;
- actions и contacts получают только общий wrapper вокруг независимых text/image блоков.

Изменение корректного HTML редактором может поменять внешний вид без изменения типа страницы. Данные и презентация связаны неявно.

### AUD-F03 — CSS содержит одновременно старую и новую главную

Старые `.public-home-*` и новые `.es-home .es-*` правила поставляются вместе. Сейчас старый блок преимущественно не используется, но остаётся в cascade и в тестовых строковых ожиданиях. Это увеличивает риск случайных конфликтов и скрывает реальный источник стиля.

### AUD-F04 — специальные страницы перенесены лишь приблизительно

- actions не имеет утверждённой связной `promo-card` композиции;
- reviews имитирует video cards через псевдоэлемент поверх списка, а не использует семейный template;
- contacts не воспроизводит утверждённые `contact-shell`, gallery и controlled external-map boundary;
- service/article pages не имеют общей утверждённой композиции `content-layout/article/closing/works`;
- catalog pages не используют утверждённые card DTO, а стилизуют rich HTML списки.

### AUD-F05 — 29 route-map представлений не имеют самостоятельного утверждённого HTML

22 отсутствуют в v3, ещё 7 являются redirect-placeholder. Это не разрешает изобретать оформление. До реализации требуется утвердить наследование: legacy text/news → editorial/plain; gallery albums → gallery family; `/services/` → service catalog; old wash URL → current wash service family.

### AUD-F06 — существующие проверки не являются визуальной приёмкой

Текущие Django-тесты проверяют строки CSS, порядок маркеров, HTTP и media contracts. `acceptance/public-contracts.spec.js` проверяет viewport/no-refresh/cache, а его документация прямо исключает реальную адаптивную компоновку. Screenshot/geometry matrix семейств на 1024/736/390/320 не закрыта.

### AUD-F07 — открытый D-1210 нельзя потерять при рефакторинге

Главная уже строит contextual media URLs, но exact21 oracle/GREEN и 21/21 HTTP ещё не завершены. Архитектурная работа обязана сохранить closed media endpoint и не заменять contextual URL на bare URL.

## 5. Рекомендуемая целевая архитектура

### 5.1 Серверный реестр презентаций

Добавить закрытое отображение `Page.Kind → presentation family + allowed variant`. Значение выбирает код, а не редактируемый HTML. Пользовательский контент не получает возможности задавать Django-template, CSS, JavaScript или имя файла.

### 5.2 Шаблоны

- один base document: metadata, approved shared Header/Footer, CSP-safe assets;
- общий page shell: breadcrumbs, full-width gutters, H1 contract;
- отдельные typed partials: home, service catalog, service content, editorial catalog/detail, actions, reviews, contacts, gallery catalog/album, legacy plain;
- общие блоки `works`, `closing`, price, safe media и request reserve переиспользуются, а не копируются по страницам;
- все тексты/URL/media приходят из существующих typed projections и current revision.

### 5.3 CSS

- shared Header/Footer остаётся отдельным защищённым shell asset;
- body CSS разделяется по base/components/families с явной областью классов;
- family stylesheet подключается только для выбранного сервером семейства;
- старые правила удаляются только после structural/visual equivalence;
- новый bundler, CSS framework и внешняя зависимость не требуются.

## 6. Предлагаемая последовательность реализации

1. `PUBARCH-01`: зафиксировать server-side family registry и 115-row mapping без изменения HTML.
2. `PUBARCH-02`: записать acceptance contracts и representative routes до product patch.
3. `PUBARCH-03`: перенести base shell и общие CSS-компоненты, сохранив Header/Footer/URL/media contracts.
4. `PUBARCH-04`: перенести service catalog + 58 service pages по утверждённой v3 композиции.
5. `PUBARCH-05`: перенести editorial family и три special pages.
6. `PUBARCH-06`: перенести gallery family и утвердить наследование 17 album routes.
7. `PUBARCH-07`: применить утверждённое наследование legacy routes; не сочинять отсутствующий контент.
8. `PUBARCH-08`: удалить доказанно неиспользуемый CSS и старые ветки только после полного GREEN.

## 7. Обязательные приёмочные сценарии перед кодом

- `PUBARCH-AC-001`: все 115 canonical представлений имеют ровно одно серверное семейство; неизвестный kind закрывается, а не попадает в generic fallback.
- `PUBARCH-AC-002`: Header exact-six, logo `/`, Footer и breadcrumbs одинаковы во всех семействах.
- `PUBARCH-AC-003`: тексты, exact URL, publication state и media identity до/после совпадают; gallery originals не меняются.
- `PUBARCH-AC-004`: representative route каждого семейства совпадает с утверждённой структурой v3 с учётом более поздних privacy/legal решений.
- `PUBARCH-AC-005`: все 115 GET/HEAD не получают template error, горизонтальный overflow или отсутствующий family asset.
- `PUBARCH-AC-006`: 1024/736/390/320 проверены для каждого семейства; Header/menu, tables, cards, media и footer остаются в viewport.
- `PUBARCH-AC-007`: home exact21 contextual media остаются authorized; wrong page/slot закрыты.
- `PUBARCH-AC-008`: внешние iframe/scripts/forms не активируются раньше своих legal/cookie/ready gates.
- `PUBARCH-AC-009`: owner/employee editor сохраняет тот же content payload; presentation family не редактируется как executable source.
- `PUBARCH-AC-010`: удалённые selectors/templates доказаны отсутствующими в rendered corpus и regressions до удаления.

## 8. Решение, требуемое до реализации

Нужно утвердить саму family architecture и правило для 29 представлений без полного v3-экрана. Рекомендация: не проводить новый дизайн-цикл, а наследовать ближайшее утверждённое семейство по таблице раздела 3. После утверждения сначала пишутся `PUBARCH-AC-001–010`, затем начинается product patch.
