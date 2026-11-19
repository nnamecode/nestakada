# RB4 HTTP auth/session/page-list increment

Дата: 2026-11-18. ID: `RB4-HTTP-AUTH-LIST-001`. Статус: **approved plan; implementation repeat-review APPROVED 0/0/0; runtime0 pending isolated PostgreSQL gate**.

## Scope and sequence

This is the first bounded HTTP increment inside already approved `RB4-SLICE-001`. It implements only:

- accounts-owned `/manage/login/` GET+POST and POST-only `/manage/logout/`;
- exact Django session generation guard for every current private page request;
- pages-owned server-rendered `/manage/pages/` authorized list;
- config URL wiring and three minimal semantic templates.

Typed editor GET/forms, Save/Undo HTTP adapters, CSS/Workshop visual polish, Nginx config/runtime, SiteSettings, grants/staff, media selector, browser QA, public renderer and live/deploy remain later bounded increments. This split does not restore drafts/history/Stable and does not introduce a dashboard, SPA, API framework, generic JSON/form builder or middleware subsystem.

## Trusted ingress and login

Login GET requires no client identity and always returns a private/no-store form. Standard `SecurityMiddleware` remains first; it does not read body/session/credentials. One accounts-owned `PrivateIngressMiddleware` is the first project middleware immediately after Security and before Session/CSRF. It is deliberately not a generic policy framework: for exact POST `/manage/login/` it reads only `request.META`, validates the D-1244 projection and can return constant400 before Session/CSRF/body/auth use while its response still passes through SecurityMiddleware; on the response path it adds `Cache-Control: private, no-store` to every `/manage/` response, including CSRF/405/redirect/error responses. Its ingress rules are:

- incoming `Forwarded`, `X-Forwarded-For` and `X-Real-IP` keys must be absent;
- exactly one `X-Estakada-Client-IP` value is required, length1..45, with no comma/port/zone/whitespace;
- Python `ipaddress` must accept it and `str(parsed)` must equal the submitted canonical IPv4 or compressed lowercase IPv6;
- invalid/missing/list/spoof projection returns constant `400 INVALID_INGRESS`, body/username/password/audit/session mutation0.

The app never stores, logs or includes that IP in audit/response. Trust exists only because production app transport remains the separately verified protected Unix socket with no public TCP listener. Nginx stripping, canonical header injection and POST-only `1r/s burst5 nodelay`/429 are not claimed by this Django increment and remain a separate static+isolated runtime gate.

After CSRF acceptance, login permits only `application/x-www-form-urlencoded` wire input. Framework-owned `csrfmiddlewaretoken` is allowed separately and, when present, must occur once. Application keys are exactly one `username` and one `password`; `QueryDict.getlist()` length must equal1 for both. Duplicate/application-extra keys, files, JSON/other content type, empty/non-string value, username>150 or password>4096 produce the same safe malformed response, credential processing0 and audit0. A valid-shaped but invalid credential pair produces the same user-facing denial without echo and appends exactly one anonymous `AUTH_LOGIN_FAILED` with reason `INVALID_CREDENTIALS`, target UUID absent. If that audit append fails, login remains denied and returns one constant technical error; no session is issued.

For successful credentials, accounts opens one transaction, locks the exact User, rechecks active staff role, generation and the authenticated password-hash snapshot, then appends `AUTH_LOGIN_SUCCEEDED`. Only after that transaction commits does Django login rotate/create the session and store exact `staff_generation`. Audit/lock failure issues no session. No source identity or credentials enter audit/logs.

Logout accepts POST only. It captures only an already validated safe actor reference, destroys the Django session first, then attempts `AUTH_LOGOUT` best-effort. Audit failure never restores the session and produces no exception detail. GET logout is405.

## Session guard and private responses

Accounts exposes one narrow public decorator/helper used by pages views. It requires authenticated User, active staff role and exact integer `request.session["staff_generation"] == User.generation`. Failure calls Django logout/flush before redirecting to login and never evaluates the page query. It is a read guard only; protected writes continue to recheck under the existing User lock in `pages.commands`.

The first accounts middleware sets `private,no-store` for every `/manage/` response, including failures created before a view. Standard Django CSRF middleware remains authoritative; no `csrf_exempt`. Private content is absent from login redirects and failure bodies. Focused middleware tests use a body-stream/parser trap: invalid ingress must return400 while body read count remains0.

## Authorized page list

`/manage/pages/` is GET-only and server-rendered:

- OWNER sees every Page;
- EMPLOYEE sees only Pages with an exact own PageGrant;
- each row contains only page name, exact PRIMARY route target, kind, publication state, current generation and allowed groups (owner shown as full access; employee exact canonical grant groups);
- ordering is existing Page `(position,id)`; no search, filters, counters, pagination, dashboard or client data grid in this bounded increment;
- query/projection requires exactly one PRIMARY Route and one PageContent for every returned Page. Missing/ambiguous composition fails closed with a constant private technical response; it never shows a partial list;
- raw payload, hashes, author, media/private storage metadata and other staff/grants are not exposed.

Employee filtering happens in the database before projection. A foreign page therefore never enters the context; direct editor URL denial belongs to the next typed-editor increment.

## Acceptance before code

- `RB4-HTTPA-001`: login GET is CSRF-protected/private-no-store and contains only framework CSRF plus username/password inputs.
- `RB4-HTTPA-002`: first middleware returns constant400 for malformed/missing/spoofed ingress POST before body/session/auth/audit; a parser-trap proves body reads0. Canonical IPv4 and IPv6 reach downstream credential processing but IP is absent from DB/audit/response.
- `RB4-HTTPA-003`: CSRF-valid exact urlencoded pair reaches credential processing. Duplicate username/password/CSRF, extra field, file/JSON/other content type and cap violations produce one generic malformed response with credential/audit0. Only a valid-shaped invalid pair writes exactly one safe failed-login audit; audit fault remains denied with session0.
- `RB4-HTTPA-004`: successful owner/employee login commits success audit before session, stores exact generation and redirects to page list; injected audit failure leaves session unauthenticated.
- `RB4-HTTPA-005`: password/role/active/generation drift invalidates an existing session before page query and clears it; no private content in response.
- `RB4-HTTPA-006`: POST logout clears session with one audit; audit fault still clears; GET is405; CSRF failure mutates neither session nor audit.
- `RB4-HTTPA-007`: owner list returns all exact rows; employee list returns only own grants and groups; query count may be asserted bounded but no cache added.
- `RB4-HTTPA-008`: missing PRIMARY/PageContent or other composition ambiguity returns constant private technical response with partial rows0.
- `RB4-HTTPA-009`: anonymous/stale requests and all private errors/redirects include private,no-store and leak no page names/payload/hash/credentials/source.
- `RB4-HTTPA-010`: static DAG remains accounts→audit, pages→accounts/media/audit, config wiring only; the only new middleware is the accounts-owned exact-path ingress/no-store adapter. Legacy app imports, middleware framework/policy service, dashboard, generic editor/API/JS/dependency/migration0.

## Verification and gates

Code adds focused Django client tests with `enforce_csrf_checks=True`, audit fault injection and owner/employee fixtures. Static review precedes runtime. A later disposable PostgreSQL HTTP test gate requires explicit owner authorization. Nginx/static socket+limiter proof and browser/visual QA are separate later gates and cannot be claimed by Django client tests.

## No-bloat stop rule

Stop and return to the owner if this increment appears to require another custom middleware, a middleware framework, new model/migration, persistent throttle/IP state, custom auth backend, session table replacement, policy engine, repository/UoW, API framework, SPA/JS, generic form builder, caching, dashboard or compatibility import from `app/`. The light compromise is to omit the disputed UI capability until its next bounded increment, never to add a placeholder abstraction.
