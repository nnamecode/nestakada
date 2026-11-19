# REBUILD-4 — лёгкая админка и fixed-field editor

Дата: 2026-11-18. ID: `RB4-ADMIN-EDITOR-001`. Статус: **D-1507 repeat plan review APPROVED 0/0/0 after owner-selected light option1; `RB4-SLICE-001` implementation active, runtime closed**.

## 1. Причина и последовательность

REBUILD-3 code/synthetic/media-schema gates закрыты through D-1504, но real coherent import остаётся B002-blocked до production independent storage. Ослаблять two-copy authority или строить локальный VHD/WSL слой запрещено решением D-1473.

Предлагаемый light path: не объявлять REBUILD-3 завершённым, а параллельно подготовить и после отдельного owner gate реализовать REBUILD-4 на уже утверждённых target models и isolated synthetic PostgreSQL fixtures. Финальная интеграционная приёмка REBUILD-4 всё равно ждёт exact imported dataset. Такой overlap не меняет data authority и не создаёт временный compatibility layer.

Исторические `docs/admin-design-brief.md` и `docs/admin-screen-scenarios.md` остаются источником UX-намерений, но их Stable/manual/drafts/history10, arbitrary formatting, backup dashboard и unpublished-white-page правила superseded D-1219 и clean-rebuild contracts. Они не являются кодовым контрактом новой версии.

## 2. Минимальный scope

1. Accounts-owned private login/logout на стандартной Django session: username+password, без MFA/email/CAPTCHA/social login. Session хранит exact `User.generation`; каждый private request до use case проверяет active role и exact generation, а protected write повторяет проверку под User lock.
   - D-1506 selected memory-only Nginx throttle: `map` gives exact POST `/manage/login/` the `$binary_remote_addr` key and all other methods an empty uncounted key; separate bounded zone `admin_login:1m`, `rate=1r/s`, `burst=5 nodelay`, excess status429. It is not shared with future request intake or other endpoints;
   - source, when required by the selected option, comes only from the D-1244 protected ingress: public Nginx strips client forwarding headers, uses canonical `$remote_addr`/`$binary_remote_addr`, and the app is reached through the protected Unix socket. Missing/malformed/list/direct ambiguity fails closed;
   - `AUTH_LOGIN_SUCCEEDED` обязан commit до выдачи session; failure остаётся denied при audit failure с constant technical error; logout уничтожает session даже при best-effort audit failure. Все private ответы `Cache-Control: private, no-store`.
2. Один server-rendered список страниц:
   - OWNER видит все страницы;
   - EMPLOYEE видит только страницы с `PageGrant`;
   - name, PRIMARY path, kind, publication, current generation и разрешённые groups;
   - без dashboard, counters, analytics и client-side data grid.
3. Один typed fixed-field editor по закрытым 19 payload kinds:
   - owner редактирует все разрешённые schema groups;
   - employee — только exact `text`/`prices` groups текущего grant;
   - arbitrary HTML/template/Python/JS/CSS, generic JSON editor и dynamic form schema отсутствуют.
4. Save и owner Undo используют exact `PAGECAS-001..007`: operation UUID, generation+hash CAS, current→previous/swap, media usages и один safe audit event в pages-owned transaction.
5. Owner-only fixed `SiteSettings` form с settings-generation CAS и выбором одного READY logo. Nullable legal/social остаются gated и не получают автоматическую публикацию.
6. Owner-only PageGrant set/revoke для existing EMPLOYEE и Page; mutation bumps target user generation and invalidates old sessions. Создание/reset/deactivation staff и structural Page lifecycle остаются отдельными bounded increments той же REBUILD-4 области, а не условием первого editor slice.
7. Media selection — bounded query существующих READY Assets через exact content slot registry:
   - Page slots допускают только approved READY purpose cohort конкретного slot; employee не видит и не меняет media fields;
   - SiteSettings logo — отдельный scalar READY `SITE_ASSET` flow;
   - selector возвращает только bounded public metadata/UUID и никогда не выдаёт `PRIVATE_SOURCE` storage key/hash/bytes;
   - upload/worker/delete, physical preview и gallery management не входят в первый slice; real preview/integration ждёт B002.

## 3. Первый bounded implementation slice

`RB4-SLICE-001` включает только login/logout, authorized page list, typed current read, Save и owner Undo. Он не включает SiteSettings mutation, grant administration, staff lifecycle, Page structure commands, upload, gallery UI, logs UI или public renderer.

Причина разбиения: это одна вертикаль `identity → authorized list → current → CAS write → audit/usages`, которую можно проверить без придумывания остальных экранов. Accounts владеет login/session/throttle и импортирует только public audit API; pages владеет list/read/save/undo и импортирует public accounts/media/audit APIs; audit остаётся leaf; config только связывает URL/views/settings. Private/cyclic imports, repository/UoW/service layer, API framework и SPA отсутствуют.

После закрытия slice1 последуют не более трёх bounded increments:

- `RB4-SLICE-002`: SiteSettings fixed form + READY logo selection;
- `RB4-SLICE-003`: PageGrant/staff minimal administration;
- `RB4-SLICE-004`: owner Page structure lifecycle PGLC-001..012.

## 4. Экранный контракт slice1

- `/manage/login/`: username, password, CSRF, одна submit button; generic invalid credentials response.
- `/manage/pages/`: простой адаптивный список, server-side authorization/filtering, link to exact editor.
- `/manage/pages/<uuid>/`: name/path/kind/publication read-only header; only schema-owned inputs; generation/hash hidden concurrency basis; Save. Owner additionally sees Undo only when previous exists.
- stale Save/Undo returns conflict page/message with reload action and never merges silently.
- server-side denial is authoritative; hiding a control is not authorization evidence.

Визуальная authority уже выбрана владельцем: направление «Мастерская» D-1180–D-1183, с последующими owner corrections D-1197/D-1198. Новый runtime повторно использует только approved visual contract: exact logo, светлый фон, orange/brown palette, верхняя адаптивная навигация, cards/forms/tables, root overflow0 и local scroll широких таблиц; список страниц показывает title + Edit, а detail остаётся внутри editor. Старые routes, models, JS, editor toolbar, Stable/manual/drafts/history, HTML mode и функциональные действия не переносятся. Target typed fields и current+previous являются единственной behavioral authority. ADMW-008 numeric 320/736/1024 evidence остаётся обязательной финальной проверкой нового shell, а не новым выбором дизайна.

## 5. Acceptance до кода

Auth acceptance (accounts-owned plus selected Nginx boundary):

| ID | Scenario | Expected |
|---|---|---|
| `RB4-AUTH-001` | Client spoofed/missing/malformed forwarding identity | D-1244 protected Unix-socket ingress only; reject before credential/audit/session mutation; raw source and submitted username absent from audit/log/response |
| `RB4-AUTH-002A` | Light option: repeated login POST from one canonical source | Nginx memory-only `1r/s`, `burst=5 nodelay`; excess denied before Django; different source independent; DB/network identifier persistence0 |
| `RB4-AUTH-002B` | Exact D-301 option: 4/5 failures,600s/900s,mixed usernames/sources | Remains closed until a separately reviewed schema/concurrency/privacy/retention/cap/backup contract is owner-approved |
| `RB4-AUTH-003` | Nginx denies excess login POST vs credential failure reaches Django | Nginx path returns429 with app/audit/session0; Django credential failure writes one safe `AUTH_LOGIN_FAILED`, issues no session and remains denied even if that audit write fails |
| `RB4-AUTH-004` | Successful owner/employee login | Active/role checked; `AUTH_LOGIN_SUCCEEDED` commits before session; session stores exact User UUID+generation; audit failure issues no session |
| `RB4-AUTH-005` | Every private request, then password/role/active/grant generation change | Active role and exact generation rechecked; stale session denied/terminated; protected write repeats under lock |
| `RB4-AUTH-006` | Failed login/logout with injected audit failure | Failed login stays denied with constant safe error; logout always destroys session; no credential/source/exception leakage |
| `RB4-AUTH-007` | Private GET/POST responses | `private,no-store`, CSRF/method/role checks and no private content in redirect/error |

| ID | Scenario | Expected |
|---|---|---|
| `RB4-AC-001` | Anonymous private URL | Redirect/login; private content absent; private/no-store headers |
| `RB4-AC-002` | Valid owner/employee login and logout | Exact selected `RB4-AUTH-001,002A,003–007`; historical `002B` closed; no custom auth framework |
| `RB4-AC-003` | Owner vs employee page list | Owner all; employee exact granted pages only; direct foreign UUID denied |
| `RB4-AC-004` | Typed editor GET | Exact current payload/generation/hash; only allowed fields rendered; arbitrary payload keys absent |
| `RB4-AC-005` | Owner Save | Full validation; current→previous; generation+hash advance; exact usages; one audit; atomic rollback on fault |
| `RB4-AC-006` | Employee Save allowed groups | Patch applies to actual current; protected groups byte/semantic unchanged; one atomic mutation |
| `RB4-AC-007` | Employee forbidden/extra group or direct crafted POST | Whole request denied before mutation/audit; no partial save |
| `RB4-AC-008` | Stale generation/hash or concurrent saves | One winner; loser `409 STALE_CONTENT`; no merge/lost update |
| `RB4-AC-009` | Same operation UUID immediate retry | Same prior result; mutation/audit not repeated |
| `RB4-AC-010` | Owner Undo with previous | Exact current/previous payload, hash, provenance swap; generation grows; usages/audit exact |
| `RB4-AC-011` | Employee Undo/direct POST or missing previous | 403/closed result; mutation0 |
| `RB4-AC-012` | Invalid kind/schema/rich text/media ref | Fail closed before DB/media mutation; page slots only READY approved purpose/slot cohort; employee media mutation0; PRIVATE_SOURCE metadata/bytes never exposed |
| `RB4-AC-013` | CSRF/method/session-generation revoke | Denied server-side; old employee session unusable after grant change |
| `RB4-AC-014` | Dependency/static inspection | audit→none; accounts→audit; pages→accounts/media/audit; config wiring only; public APIs only; legacy `app/` imports0; SPA/API/form-builder/cache/new subsystem0 |

## 6. Verification boundary

- Unit tests: closed payload/group validation, CAS/replay/Undo transitions and boundary errors.
- PostgreSQL integration: locks, concurrent winner, rollback, usages and audit atomicity.
- Django client HTTP: credentials, session/generation, audit failure, logout, CSRF, direct URL/role denial and fixed-form rendering; it does not claim Nginx limiter evidence.
- Static Nginx config proof plus a separately owner-gated isolated Nginx HTTP run covers exact POST-only `admin_login:1m`, `1r/s burst5 nodelay`, status429, GET uncounted, distinct canonical sources, spoof stripping/protected socket and app/audit/session0 on excess.
- Browser/responsive inspection uses the already approved Workshop visual authority and closes numeric ADMW-008 on 320/736/1024 after templates exist.
- Synthetic fixtures contain no copied users, passwords, media bytes or personal data. Real imported-data integration waits for B002.

## 7. No-bloat stop rules

Stop and return to owner if implementation requests any of: SPA/React/Vue, DRF/GraphQL, generic form/page builder, drafts/manual versions/Stable/history table, arbitrary rich editor, workflow/status engine, repository/UoW, event bus, async queue, cache, dashboard analytics, notification system, new storage layer or compatibility import from old `app/`.

Recommended compromise when a UI field is not fully agreed: omit it from the slice and keep the server contract closed. Do not add generic JSON or feature flags as placeholders.

## 8. Owner gate

`RB4-Q001`:

1. **Recommended/light:** keep REBUILD-3 real run parked at B002; reuse the already approved Workshop visual-only contract; choose memory-only Nginx login POST limiting `1r/s burst5` instead of the old persistent D-301 failure counter; after repeat plan approval, allow `RB4-SLICE-001` implementation on synthetic PostgreSQL. Completion/imported-data integration remains blocked until exact import.
2. Wait for production independent storage and complete real REBUILD-3 before any REBUILD-4 implementation.

`RB4-AUTH-Q001` decision D-1506:

- **A — SELECTED:** Nginx memory-only per-source login POST rate limit `1r/s burst5`; no Django throttle table, IP persistence, cleanup, backup or scheduler. This supersedes D-301 exact 5-failure/600s/900s behavior for the clean rebuild.
- **B — exact historical behavior:** retain D-301 5-failure/600s/900s semantics; first prepare and owner-approve a separate accounts schema, atomic concurrency, capacity, source representation, retention and backup contract. More code and operations; not approved here.

D-1506 approves the light scope/design/throttle choice and continuation to repeat plan review. Product code starts only after that review is APPROVED. Runtime, real DB/data mutation, live/deploy and push remain separately closed.

## 9. D-1511/D-1512 PAGECAS feasibility resolution

Independent pre-code review found that the single bounded `last_operation_*` slot cannot distinguish an old operation retry from a newly created request when both carry the same stale generation/hash after an intervening mutation. Both present an unknown operation UUID and identical stale base; audit is not a complete or unique receipt authority. No implementation may add a receipt/history table, audit lookup or second slot without a new owner decision.

D-1512 owner choice1 approves the light amendment: exact retained-operation replay is idempotent only when operation ID and stored action match; same retained ID with the other action fail-closed returns constant `409 OPERATION_CONFLICT`, mutation/audit0; every different operation ID with stale generation/hash returns one `409 STALE_CONTENT` plus current generation/hash and reload instruction, with mutation/audit0. The `PAGECAS-005` safety outcome (stale+reload, no repeat) remains, and its impossible distinct `STALE_OPERATION` label is removed. Request-only retry intent, receipt/history, audit lookup and a second slot are rejected.
