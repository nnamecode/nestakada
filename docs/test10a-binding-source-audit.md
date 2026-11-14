# TEST-10A — binding source audit

Статус D-1075, 2026-11-15: independently `APPROVED`, P1/P2/P3=0/0/0. Владелец разрешил следующий gate командой «Продолжай» после D-1074. Этот документ — read-only source map перед любой binding implementation. Product, fixture, registry JSON, validator, evidence policy и runtime не изменяются; Docker, Foundation, browser, HTTP и regression не запускались.

## Итог и no-bloat граница

- Request, UI-local и reference portions всех 40 binding IDs имеют существующий route/view, manual action либо exact reference source. State-transition source для row39 отсутствует; это явный `BLOCKED/source-gap`. Нового product endpoint ради сокрытия этого пробела не добавляется.
- Это только статическая достижимость source, не execution proof и не основание менять `implementationStatus=unbound`.
- Ни один из семи observers пока не имеет полного закрытого источника для утверждённого sink/output contract. Частичные model/helper candidates не считаются `bound`.
- Поэтому `registryReady=false`, bindings40/observers7 остаются unbound, Q003 и TEST-10 execution закрыты.
- Не возвращать retired writer/launcher и не строить новый browser/HTTP runner. Неполный observer даёт `BLOCKED`, а не фиктивный PASS.

## Exact40 source map

`source-ready` ниже означает только существование нужного production source/manual action. Dynamic CSRF, receipts, operation UUID, sessions, isolation, response class и oracle ещё должны быть доказаны будущим reviewed execution binding.

| # | Binding | Existing source | Static disposition |
|---:|---|---|---|
| 1 | `UI-013-SAFE` | `content.public_views.page`; manual rendered-page inspection | source-ready |
| 2 | `HTTP-013-ACTIVE` | `page_editor.views.check` | source-ready |
| 3 | `HTTP-013-HEADER` | public catch-all `content.public_views.page` | source-ready; exact response class still runtime evidence |
| 4 | `HTTP-013-FOOTER` | public catch-all `content.public_views.page` | source-ready; exact response class still runtime evidence |
| 5 | `UI-013-POSITIVE` | `page_editor.views.check` → `page_editor.views.save` | source-ready |
| 6 | `UI-014-OWNER-RESET` | `accounts.views.employee_password` | source-ready |
| 7 | `HTTP-014-OLD-SESSIONS` | `page_editor.editor_page.editor`; generation/session middleware | source-ready; aged session comes from fixture |
| 8 | `HTTP-014-SELF-CHANGE` | `accounts.views.employee_password` owner gate | source-ready |
| 9 | `HTTP-014-SELF-RECOVERY` | `accounts.views.login_view` | source-ready |
| 10 | `UI-014-NEW-LOGIN` | `accounts.views.login_view` | source-ready |
| 11 | `UI-015-UNSAVED` | `page_editor.editor_page.editor`; manual local input only | source-ready/manual; no mutation request |
| 12 | `HTTP-015-IDLE1801` | `page_editor.editor_page.editor`; controlled fixture session age | source-ready; boundary state comes from fixture |
| 13 | `HTTP-015-ABS43201` | `page_editor.editor_page.editor`; controlled fixture session age | source-ready; boundary state comes from fixture |
| 14 | `UI-015-RELOGIN` | `accounts.views.login_view` | source-ready |
| 15 | `HTTP-015-OTHER-DENY` | `page_editor.editor_page.editor` permission gate | source-ready |
| 16 | `UI-015-OWNER-REVOKE` | exact evidence reference `REV-E1`; no request | reference-ready only; depends on unbound `OBS-REV-E1` |
| 17 | `HTTP-015-REVOKED-DENY` | `page_editor.editor_page.editor` generation/grant gate | source-ready; depends on row30 transition |
| 18 | `UI-015-EXPLICIT-SAVE` | `page_editor.views.check` → `page_editor.views.save` | source-ready |
| 19 | `UI-021-HISTORY` | `page_versions.views.history` | source-ready |
| 20 | `UI-021-OWNER-CONTROL` | `page_versions.views.history` | source-ready |
| 21 | `HTTP-021-VISITOR` | `page_versions.views.history` protected boundary | source-ready; cache observer unbound |
| 22 | `HTTP-021-S-OTHER` | `page_versions.views.history` protected boundary | source-ready; cache observer unbound |
| 23 | `UI-022-COMPARE` | `page_versions.views.compare` | source-ready |
| 24 | `UI-022-CANCEL` | browser-native navigate away/back/cancel; no request binding | source-ready/manual |
| 25 | `UI-022-STAGE` | `page_versions.views.restore_prepare` → `restore_apply` | source-ready; ID is retained legacy label, no stage endpoint used |
| 26 | `UI-022-SAVE` | exact binding reference `UI-022-STAGE`; no request/second save | reference-ready only |
| 27 | `UI-022-OWNER-CONTROL` | `page_versions.views.compare` → `restore_prepare` → `restore_apply` | source-ready; protected observer unbound |
| 28 | `UI-023-INCOMPATIBLE` | `page_versions.views.restore_prepare` | source-ready; exact fail-closed response remains runtime binding |
| 29 | `UI-023-COMPARE-BEFORE-REVOKE` | `page_versions.views.compare` | source-ready |
| 30 | `UI-023-OWNER-REVOKE` | `accounts.views.employee_grant` → `accounts.services.set_grant` | source-ready; canonical `REV-E1` observer unbound |
| 31 | `UI-023-REVOKED` | `page_versions.views.restore_prepare` protected boundary | source-ready; depends on row30 transition |
| 32 | `UI-023-COMPATIBLE-CONTROL` | `page_versions.views.restore_prepare` → `restore_apply` | source-ready; protected observer unbound |
| 33 | `UI-104-NORMALISE` | `page_editor.views.check` | source-ready |
| 34 | `UI-104-POSITIVE` | `page_editor.views.check` → `page_editor.views.save` | source-ready |
| 35 | `UI-106-SAFE-LINKS` | `page_editor.views.check` → `page_editor.views.save`; manual public/history inspection | source-ready; client-network observer unbound |
| 36 | `HTTP-106-PROTECTED-SET` | `page_editor.views.check` only | source-ready; server-egress observer unbound |
| 37 | `UI-106-POSITIVE` | `page_editor.views.check` → `page_editor.views.save` | source-ready |
| 38 | `UI-118-VALIDATION` | `page_editor.views.check` | source-ready; browser-local retention remains manual |
| 39 | `UI-118-EXPIRY` | request sources: `page_editor.editor_page.editor` → `page_editor.views.check`; current fixture creates only already-aged sessions via `accounts.test_support.editor_session`/`page_editor.test10_fixture` | `BLOCKED/source-gap`: no existing callable ages the same active session after editor open |
| 40 | `UI-118-CONFLICT` | first `page_editor.views.check`; separate actor-session branch `page_editor.views.check` → `page_editor.views.save` advances current; first branch then calls `page_editor.views.save` with stale receipt/basis. Existing behavior is covered by `page_editor.test_save_http.SaveHttpTests.test_repeat_after_later_save_conflicts_and_does_not_rewind_current` | source-ready; browser-storage observer unbound |

## Exact7 observer gaps

| Observer | Existing candidate | Missing closed capability | Disposition |
|---|---|---|---|
| `OBS-014-SECRET-SINKS` | `audit.models.AuditEvent`, transient response/browser inspection, application process logs | one bounded source must cover all four sinks without persisting secret/log/body bytes | `BLOCKED`, keep unbound |
| `OBS-021-CACHE` | denial response headers; test-local `form-native.spec.js#noStore` | canonical derived projector for status/class/private/no-store without storing raw headers/body | `BLOCKED`, keep unbound |
| `OBS-022-PROTECTED-UNCHANGED` | content/page/version/grant/shared/media models | closed before/after snapshot and role-aware boolean projection for every approved field | `BLOCKED`, keep unbound |
| `OBS-106-CLIENT-NETWORK` | request events in `acceptance/isolated-application-driver.js` | approved manual-current-Chrome source producing only bounded method/path/status/origin; existing driver is Playwright-coupled and is not adopted | `BLOCKED`, keep unbound |
| `OBS-106-SERVER-EGRESS` | isolated foundation network policy only | actual complete server-egress observation for the tested interval; absence of fetching code is not runtime proof | `BLOCKED`, keep unbound |
| `OBS-118-BROWSER-STORAGE` | `acceptance/browser-memory.js#inspectBrowserPersistence` | approved non-Playwright manual-current-Chrome binding and complete output wrapper | `BLOCKED`, keep unbound |
| `OBS-REV-E1` | `accounts.models.PageGrant`, `accounts.models.UserProfile`, `audit.models.AuditEvent` | cursor-bounded before/after projector with concurrency/drift handling and exact safe tuple | `BLOCKED`, keep unbound |

## Recommended next step

Do not implement all seven observers as a new general framework. First independently review this source map. If approved, prepare one separate minimal observer-source plan that:

1. reuses existing product models/views and manual current-Chrome workflow;
2. defines exact source/output for each observer and leaves unavailable server-egress honestly `BLOCKED` unless an already existing bounded foundation capability is proven;
3. adds no endpoint, model, migration, dependency, service, writer, launcher or generic runner;
4. does not change registry statuses until every claimed source has focused tests and independent review;
5. keeps any future regression restricted to named suites through `scripts/test-editor.ps1`, without wildcard or Playwright.

No TEST-10 execution, fixture Prepare, evidence write or Q003 proposal is permitted by this audit.
