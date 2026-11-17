# Контракт типов содержимого и 115 публичных outcomes

Дата: 2026-11-16. Статус: **independent CRAR-REPEAT-003 APPROVED; owner REBUILD-Q001 и code gate остаются закрыты**.

Этот документ закрывает смысл `PageContent.current/previous`, редакторские поля и выбор публичного renderer для чистой пересборки. Он не разрешает product code, migrations, DB/media mutation или cutover.

## 1. Источники и полнота

Матрица публичных outcomes является точным join двух закрытых множеств:

1. `docs/analytics-route-map.csv`: ровно 115 строк `MAP-001..MAP-115`; ключ — `map_id`, exact transport input — `requested_path`, тип — `proposed_type`.
2. Таблица раздела 4: ровно 20 route outcome types. Из них 19 имеют собственный Page/content kind; `service_wash_legacy_alias` — только transport outcome, который использует canonical `service_detail` Page/payload без копии.

До REBUILD-2 read-only validator раскрывает диапазоны таблицы в literal sets и обязан доказать: `map_id` непрерывен и уникален; exact path+query уникален; memberships ровно 115; каждый MAP встречается ровно один раз; тип membership exact равен `analytics-route-map.csv.proposed_type`; все 20 outcome types используются; 19 payload kinds имеют ровно одну schema; alias указывает на canonical wash Page. Duplicate/missing/type mismatch, неизвестный renderer, fallback или выбор template/CSS/JS из данных блокирует baseline и import.

`analytics-route-map.csv` остаётся authority exact URL и legacy transport facts. Утверждённые D-235/v3 и `docs/design/public-light-v4-template.html` остаются visual authority. Более поздние privacy/legal/media решения имеют приоритет над статическим HTML.

## 2. Transport outcomes

| Класс | Exact строки | Контракт |
|---|---|---|
| `RENDER_PRIMARY` | Все строки, кроме перечисленных ниже | GET/HEAD по exact path возвращает renderer указанного типа; unknown method не пишет данные |
| `QUERY_VARIANT` | MAP-008 `/gallery-of-works/`, MAP-017 `?page=1`, MAP-018 `?page=2` | MAP-017 сохраняет наблюдавшийся redirect к canonical catalog; MAP-018 рендерит page 2; query allowlist закрыт |
| `RENDER_ALIAS` | MAP-088 `/services/drugie-uslugi/avtomojka` | Exact старый URL остаётся доступным и использует текущие данные автомойки без отдельной editable copy |
| `NEW_PRIMARY` | MAP-115 `/services/avtomojka` | Новый утверждённый exact URL использует те же текущие данные автомойки; не заменяет MAP-088 redirect-ом |

Redirect, alias, blank и query variant — transport outcomes, а не новые `Page.Kind`. `Route` выбирает outcome, но не template. Неизвестные path/query закрываются 404; известный outcome с invalid/missing typed payload закрывается 503 без generic render.

## 3. Общий versioned envelope

Каждый `current` и непустой `previous` — canonical JSON object:

```text
schema = "estakada.page-content"
schema_version = 1
kind = один из 19 literal payload kinds
fields = object, точная schema выбранного kind
```

Envelope не содержит revision ordinal, generation или timestamp. Единственная monotonic save/Undo axis — `PageContent.generation` из architecture §7.3; она хранится рядом с current/previous, передаётся отдельно для CAS и не входит в canonical payload/hash. Save увеличивает generation и создаёт новый current payload/hash. Undo снова увеличивает generation, но exact current/previous payload bytes, hashes и provenance меняются местами без reserialization, rehash или выпуска новой payload version.

Неизвестные ключи, неверные типы, лишние media slots и несовпадение `kind` с `Page.kind` запрещены. Import, write, read, public render и current→previous используют один validator; read не «чинит» данные и не выводит структуру из HTML. Rich-text поля проходят один малый allowlist sanitizer при записи/import и exact revalidation при чтении. Django templates, Python, JavaScript, CSS, имя renderer/template/asset и произвольные data attributes в payload запрещены.

Общие фиксированные группы полей:

- `seo`: `title`, `description`, `allow_index`;
- `heading`: `h1`;
- `rich`: bounded sanitized fragments `intro`, `body` там, где они указаны;
- `links`: только exact internal path либо явно разрешённый `https` URL соответствующего типа;
- `media_ref`: UUID существующего `Asset`, но только в именованном slot из таблицы.

`Page.name`, Route/URL, parent/position/publication, grants, SiteSettings и gallery ordering не входят в envelope и не могут быть восстановлены через Undo содержимого.

### 3.1. Единственные employee groups

Owner может менять все поля schema. Employee не получает field names напрямую: PageGrant содержит только закрытые enum groups:

- `text`: только `intro` и `body` у `service_section_overview`, `service_detail`, `article`, `legacy_news_article`;
- `prices`: только `price_rows` у `service_detail`.

`seo`, `heading`, home/contacts/reviews/actions/links/composition, media slots, gallery fields и все прочие fields owner-only. Unknown group/field, поле не того kind или лишний ключ отклоняет всю patch. Разрешение `text` не включает H1/SEO/media; `prices` не включает соседний текст. Save по-прежнему применяет patch к фактическому current под CAS из architecture §7.3.

### 3.2. Closed numeric limits

Limits считаются после Unicode NFC normalization; string length — Unicode code points, byte length — canonical UTF-8. Exact boundary принимается, cap+1 отвергается до DB/media mutation.

- canonical envelope максимум 1,048,576 bytes; unknown/duplicate JSON keys запрещены;
- каждый rich source и canonical result максимум 1,048,576 bytes; aggregate visible text максимум 200,000 code points, DOM nodes20,000, depth32;
- `seo.title`1..255, `seo.description`0..1,000, `heading.h1`1..255; generic label/title1..500, short caption0..1,000, long plain text0..4,000;
- internal path/approved `https` URL1..2,048 characters; UUID is lowercase canonical 36-character string;
- `links[]`≤64, `actions[]`≤32, `reviews[]`≤32; home `service_refs[]`≤12, `process_steps[]`≤12, `brand_refs[]`≤20, `review_refs[]`≤12;
- contextual media refs: `hero`≤1, `body[]`≤32, `works[]`≤32, `gallery[]`≤5, `service_cards[]`≤12, `process[]`≤12, `brand_logos[]`≤20, thumbnail/banner count не больше owning reviews/actions count; aggregate refs in one payload≤64;
- price schema: columns≤32, rows≤500, cells≤10,000; UUID IDs unique; column/row label≤500; text cell≤1,000; decimal amount 0..999,999,999.99 with at most 2 fractional digits; float запрещён.

Typed objects: action `{title≤500, body=rich, internal_url≤2048}`; review `{title≤500, https_url≤2048, caption≤1000}`; link `{label≤500, https_url≤2048}`; process step `{title≤500, body≤4000}`. `lead`, `about`, `contact_text`, `intro`, `body` являются rich fragments там, где перечислены таблицей; reference arrays содержат только UUID и не несут скрытого текста/layout.

### 3.3. Literal rich-text policy `estakada-rich-v1`

Разрешены только tags `{p,br,h2,h3,blockquote,ul,ol,li,strong,em,u,s,sub,sup,a,table,caption,thead,tbody,tr,th,td}`. Attributes: `a={href,title}`, `th={rowspan,colspan,scope}`, `td={rowspan,colspan}`; у остальных attributes нет. `rowspan/colspan` — canonical ASCII integer1..100, `scope` — `row|col`. `href` — normalized exact internal path либо `https`; `http`, protocol-relative, `javascript`, `data`, `file`, `mailto`, `tel` и redirects through user data запрещены.

`style`, `class`, `id`, wildcard/data/event attributes, comments, `img`, `iframe`, `svg`, `form`, executable/embed/template source запрещены. Alias tags `b/i` canonicalize to `strong/em`; any other sanitizer change makes import/write fail with review-required, а не молча меняет content. Canonical output обязан быть idempotent; read/render повторно валидируют exact canonical bytes. Images/links outside this policy существуют только как typed media/link fields. Это один фиксированный `nh3` call/profile, не перенос старого HTML carrier.

## 4. Закрытая матрица 20 outcome types / 19 payload kinds

Обозначения: `O` — owner-only; `O/E:text` и `O/E:prices` — employee только с exact PageGrant group; `—` — read-only projection. Неуказанного доступа нет.

| Outcome type; exact MAP IDs | Владелец payload/schema | `fields` v1 и editor groups | Renderer | Media slots |
|---|---|---|---|---|
| `home`; 001 | pages / `home` | `seo(O), heading(O), lead(O), service_refs(O), process_steps(O), about(O), brand_refs(O), review_refs(O), contact_text(O)` | `home/v4` | `hero≤1`, `service_cards[]≤12`, `process[]≤12`, `works[]≤32`, `brand_logos[]≤20` |
| `services_master_catalog`; 002 | pages / same kind | `seo(O), heading(O), intro(O)`; child cards `—` Route/Page projection | `service_catalog/master` | none |
| `service_catalog`; 012,014 | pages / same kind | `seo(O), heading(O), intro(O)`; child cards `—` | `service_catalog/section` | `hero≤1` |
| `service_section_overview`; 010,011,013 | pages / same kind | `seo(O), heading(O), intro(O/E:text), body(O/E:text)`; child navigation `—` | `service_content/overview` | `hero≤1`, `works[]≤32` |
| `service_detail`; 015,016,019–030,032,034,035,038,040–042,046,047,050–052,054,055,058–060,062–064,066–069,073–075,079,080,083–085,089,091,094,095,098,101,104,107,115 | pages / same kind | `seo(O), heading(O), intro(O/E:text), body(O/E:text), price_rows(O/E:prices)` | `service_content/detail` | `hero≤1`, `body[]≤32`, `works[]≤32` |
| `articles_catalog`; 006 | pages / same kind | `seo(O), heading(O), intro(O)`; cards `—` Page/Route projection | `editorial/catalog` | card media `—` from article |
| `article`; 031,037,043,048,053,057,065,071,072,077,082,087,093,100,103,105,108,110 | pages / same kind | `seo(O), heading(O), intro(O/E:text), body(O/E:text)` | `editorial/detail` | `hero≤1`, `body[]≤32`, `works[]≤32` |
| `contacts`; 007 | pages / same kind | `seo(O), heading(O), intro(O), body(O)`; SiteSettings projection `—` | `contacts/default` | `gallery[]≤5`; external map disabled |
| `reviews`; 005 | pages / same kind | `seo(O), heading(O), intro(O), reviews[](O)` | `reviews/default` 3/2/1 | `thumbnail` count≤reviews≤32; no iframe |
| `actions`; 004 | pages / same kind | `seo(O), heading(O), intro(O), actions[](O)` | `actions/default` | `banner` count≤actions≤32 |
| `gallery_catalog`; 008,017,018 | gallery / `gallery_catalog` | pages envelope `seo(O),heading(O),intro(O)`; albums/photos/order `—` gallery tables | `gallery/catalog` | gallery-owned originals/derivatives only |
| `gallery_album`; 036,056,061,070,076,081,086,092,096,099,102,106,109,111–114 | gallery / `gallery_album` | `seo(O),heading(O),intro(O)`; identity/photos/order `—` gallery tables | `gallery/album` | gallery-owned originals/derivatives only |
| `legacy_partner_links`; 003 | pages / same kind | `seo(O),heading(O),links[](O)` | `legacy_plain/partner_list` | none |
| `legacy_director_message`; 009 | pages / same kind | `seo(O),heading(O),intro(O),body(O)` | `legacy_plain/text` | `hero≤1` only if baseline binds one |
| `legacy_news_article`; 033,039,045 | pages / same kind | `seo(O),heading(O),intro(O/E:text),body(O/E:text)` | `editorial/legacy_detail` | `hero≤1` only if baseline binds one |
| `legacy_empty_main`; 044,049 | pages / same kind | `seo(O),heading(O)`; body absent | `legacy_plain/empty` | none |
| `legacy_news_catalog`; 078 | pages / same kind | `seo(O),heading(O),intro(O)`; cards `—` Page/Route projection | `editorial/legacy_catalog` | child article media `—` |
| `service_wash_legacy_alias`; 088 | no payload; Route points to MAP-115 Page whose kind is `service_detail` | all fields `—`; no Page/content copy | `service_content/detail` using canonical payload | canonical wash slots only |
| `legacy_under_construction`; 090 | pages / same kind | `seo(O),heading(O),intro(O),body(O)` | `legacy_plain/text` | none unless baseline binds one |
| `legacy_camera_schedule_text`; 097 | pages / same kind | `seo(O),heading(O),intro(O),body(O)` | `legacy_plain/camera_text` | none |

Ranges above are literal set notation only where unambiguous; the exact membership and paths remain the 115 CSV rows. REBUILD-1 generates a checked expanded 115-row artifact from the join rather than maintaining a second hand-copied URL list.

## 5. SiteSettings, Header и Footer

`SiteSettings` — одна singleton row модуля `pages`, не page revision JSON и не generic key/value store. Помимо уже отдельного `structure_generation` из architecture §7.6 row имеет `settings_generation` positive bigint≥1 для CAS fixed-form edit. Literal public v1 schema:

| Поле | Тип/cardinality/null | Validation/cap | V1 authority |
|---|---|---|---|
| `organization_name` | text, scalar, required | 1..120 code points, control-free | `Автосервис «Эстакада»` из approved project identity |
| `legal_name` | text, scalar, nullable | if present 1..160 code points, control-free | null до LEGAL-01/отдельного publication proof; owner-confirmed value само по себе не разрешает render; ИНН/ОГРН сюда не входят |
| `phone_display` | text, scalar, required | 1..64 code points, control-free | D-927/D-1101 `+7 (499) 110-25-52` |
| `phone_e164` | ASCII text, scalar, required | regex `^\+[1-9][0-9]{7,14}$`, tel href только derived | D-927/D-1101 `+74991102552` |
| `address` | text, scalar, required | 1..255 code points, control-free | current approved `117105, Москва, Проспект 60-летия Октября, 15Б` |
| `opening_hours` | text, scalar, required | 1..128 code points, control-free | current baseline `Ежедневно с 9:00 до 21:00` |
| `contact_email` | normalized email text, scalar, required | 3..254 ASCII, one `@`, Django email validation; mailto only derived | current owner-confirmed `estakada10@yandex.ru` |
| `map_url` | URL, scalar, required | ≤2,048 chars, `https` only, absolute host, no userinfo/control/fragment | current approved Yandex organization route from frozen baseline |
| `max_url` | URL, scalar, nullable | if present: same strict `https` policy≤2,048 and exact owner-approved target | null по D-927 до отдельного ответа CONTACT-Q002 |
| `telegram_url` | URL, scalar, nullable | if present: same strict `https` policy≤2,048 and exact owner-approved target | null по D-927 до отдельного ответа CONTACT-Q003 |
| `logo_asset_id` | UUID FK→READY Asset, scalar, required | one declared `site_settings:logo` AssetUsage; `PROTECT` while referenced | exact approved logo Asset bound by REBUILD-1 baseline/import |

Unknown columns/JSON, arbitrary social arrays, QR target, map embed, organization SEO JSON and executable/HTML values are absent. Organization structured-data projection uses only `organization_name`, non-null separately permitted `legal_name`, phone, address, hours, contact email, `map_url`, fixed public-origin config and READY logo; Page SEO remains inside each typed page payload. `tel:` and `mailto:` links are derived from validated scalar fields, never separately editable. Nullable legal/social value becomes public only after its separate gate; null renders no placeholder/icon/link/structured-data property.

Only active OWNER may submit the fixed form with exact `base_settings_generation`; employee can read the typed values in private UI but cannot mutate. One pages transaction locks singleton, checks CAS and full schema, replaces `site_settings:logo` usage if needed, increments `settings_generation` once and writes one `SITE_SETTINGS_CHANGED` AuditEvent. Failure/stale/unknown field changes nothing. This does not change `structure_generation`, Page generation, current/previous or URLs.

Header is a projection of exact-six navigation entries selected by explicit code/config from published Route/Page plus exact SiteSettings phone/address/hours/non-null socials/logo; logo target is literal `/`. Footer is a fixed template projection of `organization_name`, permitted non-null `legal_name`, logo and approved navigation groups; it does not automatically expose every settings field. Contacts renderer reads contact fields from the same singleton instead of copying them into Page payload. Neither accepts arbitrary HTML, template source, script or per-page override; Page Undo does not affect them.

## 6. Validation and acceptance

- `CONTENT-AC-001`: expanded join contains memberships115/unique MAP115/unique paths115; every MAP appears once and membership type exact-equals CSV proposed_type. `MAP-031/053` occur only as `article`.
- `CONTENT-AC-002`: registry contains outcome types20 and independent payload kinds19; MAP-088 has no payload/Page copy and resolves to MAP-115 `service_detail` Page. Unknown/missing/duplicate type or renderer fails closed.
- `CONTENT-AC-003`: import/write/read/render validators accept the same valid fixtures and reject the same unknown keys/types/slots; envelope has no `content_version`/generation/timestamp, and Undo swaps exact payload bytes+hashes while only `PageContent.generation` grows.
- `CONTENT-AC-004`: editor exposes only groups allowed for role+PageGrant; executable source fields do not exist.
- `CONTENT-AC-005`: all 115 status/redirect/exact-path outcomes, visible content and publication facts match baseline.
- `CONTENT-AC-006`: media references resolve only through declared contextual slots; 214 gallery originals remain byte-identical.
- `CONTENT-AC-007`: actions/reviews/contacts do not activate external scripts, iframe or collection before their separate gates.
- `CONTENT-AC-008`: literal SiteSettings fields/cardinality/nullability/caps, owner-only CAS and READY logo usage are enforced; Header exact-six, Footer, contacts and organization projection read the same singleton and remain outside Page Undo.
- `CONTENT-AC-009`: every scalar/list/media/price/envelope/SiteSettings boundary and cap+1 is tested; unknown settings/social/SEO keys and invalid URL/email/E.164 fail before DB/media mutation.
- `CONTENT-AC-010`: literal `estakada-rich-v1` tags/attributes/URLs/node/depth/text limits are identical for import/write/read/render; forbidden markup and non-idempotent canonicalization fail closed.
