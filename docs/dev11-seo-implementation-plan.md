# DEV-11 — минимальный план реализации SEO-профиля

Статус: D-832 от 2026-11-10. `DEV11-IMP-001–007` завершены локально; repeat independent code review `APPROVED`, P1=0/P2=0/P3=0. Final exact DEV11 50/50, calibration-aware public/shared14/14, full guard370/370, system check0, no migrations и diff PASS. Реальный AutoRepair профиль остаётся выключенным до подтверждённых DEV-12/CONTACT-01 данных; live/persistent apply/publication не выполнялись.

## 1. Замкнутая архитектурная граница

DEV-11 расширяет только существующие `content` public reader/shared host/views/template и URLConf. Current page payload остаётся единственным источником title/description/H1/indexing/images/alt; Page/Route/PageContentState/PageRevision и AssetUsage/AssetFile не меняются. Новые models, migrations, content schema, API, cache, queue, worker, scheduler, external dependency и свободно редактируемый canonical запрещены.

Добавляются две явные настройки, а не новый инструмент:

- `PUBLIC_ORIGIN`: абсолютный origin конкретной среды, без path/query/fragment/userinfo; normalised lowercase scheme/host, `https` обязателен вне локального профиля. Incoming Host/Forwarded/Referer никогда не являются fallback;
- `SEO_ROBOTS_PROFILE`: только `deny-all` для локальной/закрытой среды либо `production` для будущей production-конфигурации. Значение отсутствует/неизвестно — system check и endpoint fail closed.

Локальные compose/settings получают явные тестовые значения; production не меняется и не активируется. Альтернатива строить адреса из request rejected из-за Host poisoning; хранить origin/robots в БД не нужно.

## 2. Новые небольшие единицы кода

### 2.1. `content/public_seo.py`

Один pure/bounded модуль содержит:

- immutable `SeoMetadata` и `SeoImage` DTO;
- closed trusted-origin parser/builder;
- canonical projection по route/page/gallery request и exact CONTENT-WASH mapping;
- title/description/Open Graph projection;
- X-Robots decision;
- conditional AutoRepair JSON object builder с exact safe `application/ld+json` serialization boundary;
- sitemap aggregate capture/digest/XML projection;
- fixed robots text builder по двум профилям.

Модуль не принимает template name, raw HTML, arbitrary JSON-LD, external URL от редактора или SQL fragment.

### 2.2. Текущие public boundaries

- `PublicSharedHost.capture()` дополняет coherent host projection только выбранным SEO image slot: explicit `preview_image`, иначе `main_image`, иначе none. Файл проходит те же READY/current-page usage/exact variant/cap/recapture проверки; случайная embedded image не выбирается.
- media URL для OG использует existing contextual form `page=<page UUID>&slot=<preview_image|main_image>`. Exact `preview_image` добавляется не только в parser `media_response()`, но и в существующие `shared_content.public._page_media_usage/_capture_media`: current revision/hash, exact `CURRENT_PAGE` usage, READY/file descriptor и capture→open→recapture обязательны. Cross-page, wrong-slot и stale-preview дают404/503 по existing boundary. Другие неизвестные slot остаются404. Общий cap64 slots/files не повышается: выбранная SEO-картинка входит в существующий набор и дедуплицируется.
- для exact old CONTENT-WASH request `PublicSharedHost.capture()` отдельно захватывает только bounded peer descriptor нового `/services/avtomojka`: Page, exact PRIMARY, PageContentState/current PageRevision, `xmin`, schema/hash/indexing. Peer eligibility/stamp входит в существующий host projection и его повторный capture; full sitemap aggregate на HTML request не вызывается. Missing/hidden/noindex/corrupt peer сохраняет old200 без canonical; creation/drift between captures не даёт mixed-generation canonical.
- `public_views.page()` получает SEO DTO из уже coherent `PublicSharedHost`, передаёт escaped primitives в existing template и ставит X-Robots. Blank hidden200 остаётся body length0 и получает только HTTP `X-Robots-Tag: noindex, nofollow`; для него Header/Footer/template не запускаются.
- `public_page.html` добавляет description/canonical/Open Graph и conditional JSON-LD в head. Canonical/OG URLs code-owned. JSON-LD encoder принимает только validated typed object, вызывает deterministic `json.dumps(..., sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)`, затем заменяет literal `<`, `>`, `&`, U+2028 и U+2029 на JSON escapes `\\u003c`, `\\u003e`, `\\u0026`, `\\u2028`, `\\u2029`. Safe помечается только итоговая сериализованная строка внутри code-owned `<script type="application/ld+json">`; raw user string и raw `json.dumps` никогда не получают `mark_safe`.

## 3. Canonical и metadata matrix

1. PRIMARY ordinary/direct album/root gallery: absolute self-canonical от `PUBLIC_ORIGIN`.
2. Root/modal gallery: canonical root gallery.
3. Exact page2 и page2/modal: canonical root gallery, сохраняя direct200 page2.
4. Exact page1: прежний 302 до renderer, metadata отсутствует.
5. Public `indexing_allowed=False`: 200 + `noindex, follow`, canonical и AutoRepair отсутствуют, OG может описывать публичную страницу без объявления индексируемого представителя только если accepted profile tests это подтверждают; иначе OG URL omitted. План по умолчанию выбирает более простой вариант: title/description остаются, canonical/og:url/AutoRepair отсутствуют.
6. Hidden blank200: empty body + `noindex, nofollow`; 404/503/301 не получают HTML metadata.
7. CONTENT-WASH old `/services/drugie-uslugi/avtomojka` получает canonical нового `/services/avtomojka` только если bounded peer descriptor в том же double-captured host stamp published/indexable/coherent. Новый адрес self-canonical/единственный sitemap representative. Missing/hidden/noindex/corrupt peer: old required200 без canonical; peer drift не выдаёт mixed-generation HTML; sitemap503 по отдельному aggregate capture.
8. Любой иной уже сохранённый публичный ALIAS сохраняет требуемый existing200, но не получает canonical/og:url и не может сам назначить представителя; external target, fragment, unknown query или inconsistent special mapping fail closed. Это уточнение D-831 сохраняет public navigation/старые URL без ослабления SEO-authority; query parser DEV-10 не расширяется.

Description meta/og:description отсутствуют при empty string. `title`, H1 и description не генерируются заново и не переписываются. Keywords не добавляются.

## 4. Coherent sitemap capture

`GET/HEAD /sitemap.xml` использует один bounded helper дважды:

1. Отдельные ordered queries имеют pre-read caps и materialize только `cap+1`: Page `50,000+1`, PRIMARY Route `50,000+1`, ALIAS Route `2+1`, PageContentState `50,000+1`, current PageRevision `50,000+1`. Closed alias overhead — ровно gallery page2 и CONTENT-WASH old alias; unknown/extra alias даёт503. Любое превышение отказывается до digest/XML. Для всех captured rows сохраняются IDs/fields и PostgreSQL `xmin::text` через уже применяемый в проекте `RawSQL`; current relation, exact one PRIMARY per represented Page, schema version, payload hash, target validity и canonical mapping проверяются.
2. Capture строит canonical representatives и deterministic digest из canonical JSON. Никаких per-page `resolve_target()` и N+1 запросов.
3. XML сериализуется в memory стандартным XML builder, UTF-8, fixed namespace/content type. Включаются только published/indexable/coherent canonical PRIMARY representatives; redirects/aliases/query/private/special endpoints исключены. Root gallery и direct albums попадают по общим правилам. `lastmod`, changefreq и priority пока отсутствуют.
4. До response тот же bounded helper делает второй capture. Digest обязан совпасть, иначе503. Изменение с возвратом A→B→A обнаруживается `xmin`/immutable revision identity.
5. Любой `cap+1`, 50 001st canonical representative или итоговый XML больше50MiB дают503; partial/truncated200 запрещён. Duplicate route/page/state/revision, unknown/extra ALIAS, corrupt payload/hash/schema и incoherent CONTENT-WASH group также503.

Ответы: GET200 body, HEAD200 empty body with exact GET Content-Length, POST405 `Allow: GET, HEAD`; `application/xml; charset=utf-8`, `Cache-Control: no-cache`, nosniff. Никакой фоновый XML/caching layer не создаётся.

## 5. Robots

`GET/HEAD /robots.txt` стоит в URLConf до catch-all и использует только `SEO_ROBOTS_PROFILE` + trusted origin.

- `deny-all`: `User-agent: *` + `Disallow: /`; без Sitemap, внутренних путей и production exceptions.
- `production`: code-owned `User-agent: *`, exact active `/manage/` и approved legacy CMS prefix rules, `Disallow: /*?`, exact `Allow` для gallery `?page=1$`/`?page=2$`, absolute Sitemap trusted origin. Публичные static/media paths не блокируются; секретные IDs/paths не перечисляются.

GET/HEAD200, POST405, `text/plain; charset=utf-8`, no-cache, nosniff. Unknown mode503. Robots не вызывает БД и не участвует в auth.

## 6. Conditional AutoRepair

`build_auto_repair(profile, visible_facts, page, origin)` — pure helper. Product integration до DEV-12 передаёт no profile/evidence, поэтому JSON-LD отсутствует. Отдельный exact encoder сериализует только результат этого helper по §2.2; `json_script` с неверным `application/json` и raw `mark_safe(json.dumps(...))` запрещены.

Synthetic complete profile проходит только если:

- page — published/indexable home или contacts;
- confirmed visible `name`, physical `address`, `telephone` непусты и exact match typed profile;
- `@context`, `@type=AutoRepair`, `@id=<origin>/#auto-repair`, `url=<origin>/` code-owned;
- optional hours/geo/sameAs/logo/image включаются только как separately confirmed typed values и safe public URLs.

Если любой mandatory fact отсутствует/не подтверждён/не виден — весь node отсутствует, page200 сохраняется. `review`, `aggregateRating`, `Offer`, `priceRange` и unknown keys отклоняются. Один и тот же `@id` не создаёт отдельную организацию на каждой странице.

## 7. Приёмочные сценарии и тесты до кода

| ID | Проверка | Связь |
|---|---|---|
| S11-AT-001 | Independent stored title/H1/description, empty description omission, rename/body save independence | AT-010 |
| S11-AT-002 | Exact trusted-origin validation; Host/Forwarded/Referer and CR/control/userinfo/path/query/fragment cannot alter URLs | AC-SEO-001 |
| S11-AT-003 | Canonical matrix ordinary/root/page2/modal/direct17/page1/noindex/hidden/errors/CONTENT-WASH/unknown alias | AT-604 |
| S11-AT-004 | X-Robots public noindex/hidden blank, private denial and no template/body leak | AT-061/603 |
| S11-AT-005 | Preview→main→none, `_page_media_usage/_capture_media` exact preview support, usage/file/contextual URL, cross-page/wrong-slot/stale negatives,64 cap unchanged, random embedded excluded, original SHA unchanged | AT-011/605 |
| S11-AT-006 | Sitemap exact set/order/exclusions/XML escaping/content type, GET/HEAD/POST, per-table Page/PRIMARY/ALIAS/State/Revision cap+1,50k/50MiB, duplicate/corrupt/alias/race/ABA503 | AT-011/602 |
| S11-AT-007 | Robots deny-all/production exact bytes, longest-match gallery exceptions, assets not blocked, no secret enumeration, methods/headers | AT-603 |
| S11-AT-008 | AutoRepair mandatory visible facts, exact ld+json MIME, `</script>`/`<!--`/`&`/U+2028/U+2029 escapes and JSON reparse, optional/forbidden keys, none-by-default200 | AT-054/605 |
| S11-AT-009 | Employee tampering of SEO/indexing/alt/profile refused; owner noindex/reallow does not rewrite text | AT-010/011/061 |
| S11-AT-010 | Ordinary public/gallery/media/security regressions, Django check, no migrations, manifest/diff checks; foundation stopped | pipeline 8/10 |

Unit tests cover pure origin/canonical/robots/Schema/XML decisions. Django HTTP tests prove actual headers/body/methods and coherent DB/media behavior. Existing acceptance Playwright files are not used; user-required no-Playwright boundary remains.

## 8. Минимальные задачи реализации

| ID | Изменение | Зависит от | Проверка |
|---|---|---|---|
| DEV11-IMP-001 | Closed settings/origin parser, SEO DTO and canonical/X-Robots pure matrix with failing tests first | D-821/D-822 | S11-AT-001–004 |
| DEV11-IMP-002 | Existing shared public capture + template/header integration; preview/main media slot without cap increase | IMP-001, DEV-08G/10 | S11-AT-001–005 |
| DEV11-IMP-003 | Bounded Page/Route/State/Revision sitemap capture, xmin digest recapture and XML endpoint | IMP-001 | S11-AT-003/006 |
| DEV11-IMP-004 | Fixed two-profile robots endpoint and exact Google-compatible gallery rules | IMP-001 | S11-AT-007 |
| DEV11-IMP-005 | Conditional safe AutoRepair serializer/integration, disabled real profile and synthetic evidence tests | IMP-001/002 | S11-AT-008/009 |
| DEV11-IMP-006 | Combined focused public/gallery/media/security regression and final evidence | IMP-001–005 | S11-AT-001–010 |
| DEV11-IMP-007 | Independent code review, fixes and bounded repeat verification | IMP-006 | pipeline stage 10 |

## 9. Явно отложено

Real AutoRepair activation/business data/brand fallback image до DEV-12/CONTACT-01; emergency HTML SEO coherence до DEV-25/26; Search Console/Metрика до DEV-30; lastmod до достоверного semantic timestamp; sitemap index/cache до фактического роста; external validators/real browsers до launch gates. Это не мешает обычным страницам отвечать200 и не разрешает выдумывать данные.

## 10. Ворота

1. Independent review этого плана: P1/P2/P3=0.
2. Отдельное явное разрешение владельца начать `DEV11-IMP-001–007`.
3. Реализация строго по малым срезам; следующий срез только после focused PASS.
4. Никакого live/persistent apply/publication/VPS.
