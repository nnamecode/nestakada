# REBUILD-5 — public shell and exact HTTP dispatch

Дата: 2026-11-22. ID: `RB5-SLICE-001-PUBLIC-SHELL`. Статус: **APPROVED 0/0/0; tests-first source active**.

## Результат

Первая поставка REBUILD-5 добавляет в новую версию `src/` один общий публичный shell и exact HTTP dispatch поверх уже утверждённых `resolve_public_target`, `project_public_navigation` и `project_legacy_plain`. Она выводит четыре готовых media-free семейства: partner links, empty main, under construction и camera schedule text. Это основа для следующей поставки HOME v4, а не временная подмена главной.

Старый `app/` не импортируется и не запускается как новая версия. Новые model/migration/dependency/cache/service/repository/framework отсутствуют. Gallery, requests, external widgets, analytics, sitemap и остальные PageKind остаются следующим REBUILD-5/6 scope.

## Граница данных

1. `modules.pages.public_http` принимает только GET/HEAD. Остальные методы получают 405.
2. Exact target не реконструируется из декодированного Django `request.path`. Локальный и будущий production Nginx безусловно перезаписывает внутренний `X-Estakada-Request-Target` значением exact `$request_uri`, включая исходные case/percent spelling/query order. App не публикует порт на host и доступен только во внутренней Docker web-сети. View принимает одно полученное после overwrite ASCII value1..2048, проверяет valid percent escapes и совпадение безопасно decoded path с `request.path_info`, запрещает fragment/backslash/control/whitespace и передаёт header целиком в `resolve_public_target`. Transport/header envelope failure — missing, non-ASCII, over-cap, malformed percent или path mismatch — закрывается constant400 до DB. Coherent envelope, который authority признаёт domain-invalid/unknown, получает404. Client-supplied одноимённый header не проходит, потому что ingress его всегда заменяет; приложение не пытается угадывать число исходных client header по запятым, допустимым в URI.
3. `resolve_public_target` остаётся единственным Route authority:
   - `NOT_FOUND` → 404;
   - `UNAVAILABLE` → constant 503;
   - `PublicBlank` → zero-body 200 с `X-Robots-Tag: noindex, nofollow`;
   - `PublicRedirect` → direct 301 на canonical PRIMARY;
   - `PublicPage` передаётся только kind-specific projector.
4. В этом slice допускаются только четыре legacy-plain kind. Любой другой published kind получает constant 503, но не placeholder HTML.
5. Новый frozen `PublicSiteShell` DTO содержит только `organization_name`, `phone_display`, `phone_e164`, `address`, `opening_hours`, `map_url`, logo URL/MIME/width/height и exact-six menu. `contact_email`, settings/structure generation, model instances, asset/file hashes, storage root/key и audit/staff/session data в template context не передаются. После visible supported resolver, но до projector/media/navigation, shell читает exact singleton и внутренне фиксирует `(settings_generation, structure_generation, logo_asset_id)`. После всех projection calls он повторно читает те же три значения; mismatch/missing/duplicate даёт503. Hidden/redirect branches settings/navigation0. Поэтому settings/logo/structure commit между document projection и navigation либо полностью попадает в следующий request, либо закрывает текущий 503; old-document/new-menu hybrid запрещён.
6. Media-owned `project_public_site_logo(settings_id, logo_asset_id)` проверяет exact one SITE_SETTINGS/logo/position0 usage, READY SITE_ASSET и exact one MAIN `AssetFile`, возвращая frozen public metadata плюс exact `storage_key`. JPEG `.jpg/.jpeg` берётся только из validated storage key, не угадывается по MIME. URL равен `/media/` + exact `img/<uuid>/main.<ext>`; storage key остаётся вне template DTO после построения URL.
7. В том же coherent slice Nginx имеет case-sensitive regex location только для `/media/img/<canonical-lowercase-uuid>/main.(jpg|jpeg|png|webp|svg)` и отдельный `/media/` fallback404 до app proxy. Поскольку location сопоставляется с normalized URI, внутри accepted location второй return-only guard требует exact raw `$request_uri` по тому же canonical pattern без query; percent-encoded slash/dot, dot-segment и query получают404 до alias. Exact capture маппится в read-only public media root; preview/legacy-public/unknown extension/nested/arbitrary path не обслуживаются. Directory listing выключен, symlink traversal запрещён, MIME берётся из fixed allowlist без octet-stream fallback, nosniff включён. DB/import materializes public files по exact validated storage keys; acceptance сверяет bytes/SHA/MIME с `AssetFile`. Отсутствующий/drift file закрывает local preview readiness. Django media view и произвольное filesystem open отсутствуют; `/media/...` никогда не попадает в public catch-all.
8. Navigation authority фиксирует пять exact projection-root identities по stored Page name/PRIMARY: `(Акции,/actions)`, `(Галерея работ,/gallery-of-works/)`, `(Отзывы,/reviews)`, `(Статьи,/articles/)`, `(Контакты,/contacts)`. Missing/duplicate или присутствие только под visible navigation parent даёт503. Promotion через hidden ancestors принимается как projection-root, потому что это утверждённая semantics `project_public_navigation` и D-032; HTTP не создаёт второй Page/Route query для восстановления скрытого provenance. Code-owned header затем отображает approved D-145/D-146 exact-six labels/targets: `Услуги и цены → /#es-services`, `Акции → /actions`, `Наши работы → /gallery-of-works/`, `Отзывы → /reviews`, `Статьи → /articles/`, `Контакты → /contacts`. То есть stored `Галерея работ` намеренно отображается как header label `Наши работы`; service anchor не создаёт Route. Остальная automatic navigation может использоваться family templates позднее, но не меняет header exact-six.
9. Rich text `intro/body` уже проходит closed validator и рендерится только как marked-safe canonical stored fragment. Все scalar/labels/SEO по умолчанию autoescaped. Partner link получает `rel="noopener noreferrer"`; внешнее открытие не требует JS.
10. Если `project_legacy_plain()` после успешного resolver возвращает `PublicBlank` из-за concurrent hide, HTTP mapping совпадает с resolver-side blank: zero-body200, noindex/nofollow, no-store. Необходимый initial generation/settings snapshot уже мог быть прочитан, но logo/navigation/template calls0 и disclosure0; resolver-side blank по-прежнему shell snapshot0.

## HTML/CSS

- Base template: semantic header/nav/main/footer, skip link, visible focus, Russian `lang`, viewport meta.
- Visual authority: approved D-145/D-146 light v4 — white/light-gray surfaces, black text, orange accent, compact layout and responsive 320/390/768/1024/1440 behavior.
- CSS is one pages-owned static file. No font/network dependency: initial shell uses a local system stack; exact font packaging may be added only with license/supply-chain evidence.
- Mobile navigation is native `<details>` in this slice, so the shell remains usable without JavaScript. No generic component library.
- SEO: exact title/description from projection; `robots=noindex,nofollow` when `allow_index=false`; canonical points to PRIMARY local target. Alias renders canonical PRIMARY; redirect never renders HTML.
- Public success response uses `Cache-Control: public, max-age=0, must-revalidate`; blank/400/404/503 use `no-store`. Public view/template не обращаются к `request.user`, session или messages, не создают session, не выставляют `Set-Cookie`/`Vary: Cookie`. Private `/manage/` behavior is unchanged.

## URL composition

Existing explicit `/manage/...` patterns stay first. Then:

```text
/media/img/<uuid>/main.<ext>  Nginx-only exact read-only public media
/<path:any exact path>    public_page_view
/                        public_page_view
```

The catch-all never handles `/manage/`; an explicit guard remains in the view as defense in depth. Static assets use Django static discovery in tests and the later local ingress in Docker.

## Acceptance before code

| ID | Scenario | Required result |
|---|---|---|
| `RB5-SHELL-001` | trusted ingress exact `$request_uri`, including case/order/percent spelling | overwritten internal header and exact Route lookup; missing/non-ASCII/over-cap/malformed-percent/path-mismatch header constant400 before DB; no normalization |
| `RB5-SHELL-002` | GET/HEAD for four supported kinds | 200 semantic shell; HEAD body0 with same status/headers |
| `RB5-SHELL-003` | coherent envelope with unknown/domain-invalid exact target, e.g. `/unknown/` or `/a/../b/` | constant404 from authority; contrast SHELL-001 transport400; private fields0 |
| `RB5-SHELL-004` | hidden PRIMARY/ALIAS or hide between resolver/projector | zero-body200, noindex/nofollow/no-store, no shell/settings/navigation disclosure |
| `RB5-SHELL-005` | REDIRECT | direct301 to PRIMARY; body/template/projector0 |
| `RB5-SHELL-006` | unsupported kind or projector/settings/navigation/media drift/concurrent settings or structure generation | constant503/no-store; barrier between document and navigation proves coherent shell or partial HTML0 |
| `RB5-SHELL-007` | coherent SiteSettings/logo projection and actual Nginx media read | exact allowlisted DTO and bytes/SHA/MIME; jpg/jpeg suffix exact; email/hash/key/root/private source0; traversal/symlink/missing/drift denied |
| `RB5-SHELL-008` | partner links and rich text | escaping/canonical-fragment boundary, fixed rel, no template/code execution |
| `RB5-SHELL-009` | SEO/canonical | exact title/description/index policy and canonical PRIMARY for alias |
| `RB5-SHELL-010` | 320/390/768/1024/1440 static/browser fixture | no horizontal overflow, visible focus, usable nav, stable header/footer |
| `RB5-SHELL-011` | public auth/session/cache and `/manage/` regression | public user/session/messages reads0, Set-Cookie/Vary:Cookie0; existing private routes/CSRF/cache unchanged |
| `RB5-SHELL-012` | static scope/ingress inspection | exact-six menu with accepted hidden-ancestor promotion; raw-target overwrite; app internal-only; strict main-file media regex plus fallback404 before proxy/catch-all; no model/migration/dependency/old-app import, write, external network or generic renderer framework |

Focused code target: one pages public HTTP/shell module, one narrow media public projection, base+legacy template, one CSS file, URL composition, local Nginx preview config and exact12 tests. Source uses no real media read. PostgreSQL/browser/Docker with a disposable exact fixture and actual read-only public media bind remains a later bounded run after source review.

## Следующие slices

1. `RB5-SLICE-002-HOME`: HOME projector/template against approved v4 and local media URLs, with external reviews/map/intake kept disabled by existing LEGAL gates.
2. `RB5-SLICE-003-FAMILIES`: services/catalog/detail, articles, contacts/reviews/actions and gallery shells grouped into 4–5 concrete templates.
3. `RB5-SLICE-004-OUTCOMES`: all115 URL outcomes, sitemap/robots and local Docker/browser preview.

FirstVDS, production B002, domain/TLS and deploy remain outside REBUILD-5 local source work.
