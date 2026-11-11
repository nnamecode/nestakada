# DEV-11 — минимальный SEO-профиль без отдельной подсистемы

Статус: scope утверждён владельцем D-821 от 2026-11-10; independent scope review ожидается, product code не начат. Основания: D-023, D-243–D-253, D-301, D-592, REQ-010/011/061, AC-010/011/061, AC-SEO-001–006 и завершённые DEV-08/DEV-10.

## 1. Цель

Добавить обязательные SEO-ответы поверх существующих `Page`, `Route`, current revision и публичного renderer, не создавая отдельную SEO-платформу. Точные старые URL и HTTP-поведение остаются главнее canonical; SEO не становится авторизацией, публикацией или редиректом.

## 2. Что уже есть и переиспользуется

- current payload уже хранит отдельные `title`, `description`, `h1`, `indexing_allowed`, `main_image`, `preview_image` и alt конкретного использования;
- редактировать SEO-поля может владелец, сотрудник их не меняет;
- публичный reader уже даёт согласованный current revision, точный route, публикацию, media usages и fail-closed ответы;
- создание страницы уже предлагает отдельные H1/title и не переписывает их при rename;
- DEV-10 уже фиксирует root, `?page=1`, `?page=2`, modal query и 17 direct album URL;
- CSP, autoescape, contextual media URL и закрытые административные маршруты остаются прежними.

Поэтому не нужны новые модели/миграции, свободное поле canonical, SEO-сервис, Redis, XML-кэш, worker, очередь, scheduler, внешняя библиотека или отдельный UI-конструктор.

## 3. Минимальный текущий объём

### 3.1. HTML metadata

Один небольшой pure projection в существующем public layer строит только из проверенного `PublicPage` и доверенного origin:

- один `<title>` из сохранённого title с прежним fallback на name;
- один `<meta name="description">`, только если сохранённое description непустое;
- максимум один абсолютный `<link rel="canonical">` по закрытой матрице ниже;
- `X-Robots-Tag: noindex, follow` для опубликованной страницы с `indexing_allowed=False`;
- отсутствие запрещающего заголовка для обычной индексируемой страницы;
- `noindex, nofollow` для существующего скрытого пустого 200;
- безопасные Open Graph `og:title`, `og:description`, `og:url` и `og:image`, если соответствующее значение действительно есть. Картинка выбирается `preview_image → main_image → позднее утверждённая общая`; случайная embedded image не используется.

Origin задаётся одной обязательной доверенной настройкой среды и не берётся из Host/Forwarded/Referer. На локальном стенде используется явно заданный локальный origin.

### 3.2. Закрытая canonical-матрица

- обычная PRIMARY-страница и каждый direct album — self-canonical;
- `/gallery-of-works/` — self-canonical;
- `/gallery-of-works/?page=2` и её modal query — canonical корня галереи, сохраняя direct HTTP 200 и отдельный набор карточек;
- root modal query — canonical корня;
- exact `?page=1` остаётся 302 на root и не получает HTML metadata;
- публичная noindex-страница canonical не выводит;
- скрытый/404/503/301 canonical не выводят;
- неизвестные/лишние query остаются 404 и не очищаются в «правильный» canonical;
- legacy alias использует только закрытое code-owned соответствие; произвольного внешнего URL в редакторе нет. Для утверждённой пары CONTENT-WASH точное соответствие — `/services/drugie-uslugi/avtomojka` → `/services/avtomojka`: новый адрес получает self-canonical и является единственным XML-представителем. Canonical старого 200 выводится только когда новый представитель в том же согласованном снимке опубликован, indexable и исправен. Если цель отсутствует, hidden, noindex или повреждена, старый адрес сохраняет свой требуемый 200 без ложного canonical, а sitemap всей несогласованной alias-группы закрывается 503 вместо двух записей или частичного XML.

Canonical не меняет ответы, URL или навигацию и не создаёт новые редиректы.

### 3.3. `/sitemap.xml`

Один обычный Django GET/HEAD endpoint формирует XML непосредственно из одного bounded optimistic DB capture, а не вызывает отдельный public resolver для каждой страницы. Capture читает Page, PRIMARY/ALIAS Route, PageContentState и current PageRevision с системным row-version evidence, проверяет exact schema/payload hash, publication/indexing и закрытую canonical map, затем перед выдачей тем же bounded запросом повторно строит digest. Несовпадение первого и второго digest даёт 503. Так query rows не смешивают поколения, а новый service/cache не создаётся.

Из согласованного capture endpoint:

- включает только опубликованные, `indexing_allowed=True`, canonical-представители с допустимым публичным 200;
- включает root галереи и 17 direct albums после их публикации;
- исключает hidden/noindex/deleted/redirect/alias, admin/history/preview/health, query и modal варианты;
- URL строятся только от trusted origin; XML экранируется стандартным serializer;
- `lastmod` отсутствует, если нет отдельного подтверждённого времени значимого публичного изменения. Время запроса, импорта или сборки не подставляется;
- при duplicate/inconsistent route, corrupt revision, incoherent alias-group, превышении 50 000 URL/50 MiB либо optimistic recapture race выдаётся 503 без частичного XML;
- кэш, фоновые обновления и sitemap index в первой версии не создаются.

### 3.4. `/robots.txt`

Один фиксированный доверенный файл в коде, GET/HEAD only, `text/plain`:

- `User-agent: *` и абсолютная ссылка на `/sitemap.xml` от trusted origin;
- запреты `/manage/` и подтверждённых legacy CMS prefixes без перечисления секретных путей/ID;
- необходимые публичные CSS/JS/media не блокируются;
- общий query-запрет и только exact Allow для `/gallery-of-works/?page=1$` и `?page=2$` по принятому профилю;
- локальная/закрытая среда имеет явный отдельный deny-all профиль и не может незаметно стать production-профилем.

Robots не участвует в проверке прав: прямой запрос черновика/админки всё равно отклоняется сервером.

### 3.5. Schema.org AutoRepair

Реализуется только маленький доверенный serializer `application/ld+json`, без произвольного JSON/HTML из редактора. Он принимает типизированный подтверждённый business profile и умеет вывести одну организацию с постоянным `@id=<trusted-origin>/#auto-repair` на индексируемых home/contacts.

В локальной реализации профиль по умолчанию отсутствует, поэтому JSON-LD не выводится, а страницы продолжают отвечать 200. Активация выполняется позднее вместе с DEV-12/CONTACT-01, только когда подтверждённые и видимые на странице name, physical address и phone присутствуют и совпадают с типизированным профилем. Отсутствие или неподтверждённость любого из этих трёх обязательных значений выключает весь AutoRepair-узел. Отдельно могут отсутствовать только необязательные hours/geo/sameAs/logo/image; review, aggregateRating, Offer, priceRange и выдуманные сведения запрещены.

Так DEV-11 реализует и тестирует безопасную механику Schema, но не требует новой таблицы общих настроек и не вынуждает сейчас записывать реальные контактные данные.

### 3.6. Alt и viewport

Новая система alt не создаётся: используется существующий validated alt конкретного image usage, предел 300 символов и contextual media authorization. DEV-11 только проверяет, что metadata/Schema не меняют оригиналы и 214 gallery SHA. В шаблоне остаётся ровно один доверенный viewport; редактор его не меняет.

## 4. Приёмочные сценарии до кода

| ID | Сценарий | Связь |
|---|---|---|
| S11-AT-001 | Title/H1/description независимы; пустой description не создаёт meta, rename/body save их не переписывает | AT-010 |
| S11-AT-002 | Trusted origin устойчив к Host/Forwarded; вредная строка экранируется и не закрывает head/JSON-LD | AC-SEO-001/005 |
| S11-AT-003 | Один canonical по закрытой матрице ordinary/gallery/page2/modal/direct album/noindex/hidden/redirect/error | AT-604 |
| S11-AT-004 | Noindex public200 получает `noindex, follow`; hidden blank200 — `noindex, nofollow`; private остаётся закрытым | AT-061/603 |
| S11-AT-005 | Один bounded Page/PRIMARY+ALIAS/State/current Revision capture и optimistic digest recapture; sitemap exact set/exclusions, CONTENT-WASH mapping, escaping, GET/HEAD/POST405, duplicate/corrupt/incoherent alias/race/limit fail closed без partial XML | AT-011/602 |
| S11-AT-006 | Robots production/local profiles, exact gallery exceptions, public assets allowed, secrets не перечислены | AT-603 |
| S11-AT-007 | Open Graph использует explicit preview→main→approved common chain и contextual media URL; случайную картинку не берёт | AT-011 |
| S11-AT-008 | AutoRepair отсутствует при отсутствии любого подтверждённого видимого name/address/phone; synthetic complete profile даёт одну безопасную организацию, optional fields могут отсутствовать, запрещённых полей нет | AT-054/605 |
| S11-AT-009 | Employee tampering SEO/indexing/canonical/Schema отклонён без скрытой записи; owner noindex/reallow не переписывает тексты | AT-010/011/061 |
| S11-AT-010 | Existing public/gallery/media/security regressions, Django check, no migrations, diff check PASS; no live/persistent apply | pipeline 8/10 |

Аварийный HTML AC-SEO-006 остаётся интеграцией DEV-25/26: DEV-11 предоставляет metadata projection и XML/robots contract, но не создаёт fallback state machine.

## 5. Минимальная последовательность после согласования

1. Независимое ревью этого scope и точных acceptance boundaries.
2. Минимальный implementation plan с 5–7 небольшими срезами и отдельное разрешение владельца на product code.
3. Сначала failing focused tests, затем pure SEO projection и HTML headers.
4. Sitemap/robots endpoints без кэша и фоновых процессов.
5. Conditional AutoRepair serializer и synthetic tests, без реальных контактов.
6. Combined public/gallery/security regression, независимое code review.

## 6. Явно исключено

Свободно редактируемый canonical; keyword generator; автоматический рерайт; SEO-рекомендатор; rank tracking; Search Console/Метрика; внешний validator в runtime; Redis/cache invalidation; очередь/worker/scheduler; sitemap index до фактической необходимости; Schema для каждой услуги; reviews/ratings/Offer; аварийный proxy/fallback; публикация, VPS и реальные business credentials.

## 7. Вопрос на согласование

`DEV11-Q001`: **утверждено D-821**. Минимальный scope принят, включая условную реализацию AutoRepair без реальных данных до DEV-12/CONTACT-01 и без новой модели настроек.
