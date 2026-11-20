# REBUILD-4 — минимальный lifecycle сотрудников

Дата: 2026-11-19. ID: `RB4-SLICE-003B-STAFF`. Статус: **code approved D-1672 review0/0/0, product0/no-bloat; exact111 PostgreSQL plan under independent review, runtime0**.

## 1. Причина и граница

PageGrant `003A` закрыт D-1665, а B002/public composition всё ещё требует отдельного production independent storage. Следующий полезный B002-independent срез — ранее отложенный `003B`: owner-only lifecycle существующей staff identity для роли `EMPLOYEE`.

Срез разрешает только создать сотрудника, установить ему новый пароль, деактивировать с атомарным отзывом всех grants и реактивировать без восстановления grants. Он не меняет OWNER, owner password/recovery, role или username существующего User; не добавляет email-login/confirmation, MFA, CAPTCHA, Profile, customer identity, permission matrix, grant history, deletion, bulk, search, pagination, API, JavaScript или generic user-management service.

## 2. Exact commands и ownership

Accounts владеет `create_employee` и `set_employee_password`. Pages владеет `deactivate_employee` и `reactivate_employee`, потому что только pages может транзакционно доказать/изменить состояние `PageGrant`; внутри одной outer transaction он использует узкие accounts participants, которые не импортируют pages, не открывают transaction и меняют только уже заблокированный User. Audit append остаётся последним участником.

Единый lock order сохраняется: actor+target User rows ascending UUID → affected Page rows ascending UUID → PageGrant rows in matching page order → audit. Accounts-only commands заканчиваются после User locks → audit. Actor каждый раз повторно проверяется как exact active OWNER `nesadmin` с current session generation; target всегда exact `EMPLOYEE`, never owner.

### Create

Owner заранее передаёт UUID, exact username и два одинаковых password values. Username проходит стандартные Django `User.username` max-length/UnicodeUsernameValidator/normalization rules, не равен `nesadmin`, unique case-sensitive DB value и не содержит edge whitespace; дополнительный alias/display/email не создаётся. Password проходит только текущие стандартные Django `AUTH_PASSWORD_VALIDATORS`, никогда не логируется и не попадает в audit/detail.

Одна accounts transaction creates active staff=true/superuser=false `EMPLOYEE`, generation1, empty email and standard Django password hash, then exactly one `STAFF_CREATED` audit `{generation:1}`. D-1668 fixes light semantics: any already-existing target UUID returns409+reload with mutation/audit0, regardless of matching request state. Username collision also returns409. Lost-response retry and concurrent identical create are intentionally indistinguishable and both observe conflict after the one winner. Password-hash verification, audit lookup, receipt/history and idempotent-success branch are absent.

### Set employee password

Owner задаёт новый password+confirmation для active или inactive EMPLOYEE и передаёт `base_user_generation`. Under User locks command rejects stale basis, validates password, sets the standard Django hash, increments generation exactly once and appends one `AUTH_PASSWORD_CHANGED` with new generation. Any old session becomes stale. A same-password request is rejected as `NO_CHANGE` before mutation/audit; lost-response retry with stale generation gets409+reload, not heuristic success. Owner password/self-target is excluded.

### Deactivate

Owner submits active EMPLOYEE UUID, `base_user_generation` and exact `base_grants_digest`. Digest is lowercase SHA-256 over exact UTF-8 bytes of canonical JSON plus LF: `{"domain":"estakada.staff-grants.v1","staff_id":"<lowercase-hyphenated-uuid>","grants":[{"page_id":"<lowercase-hyphenated-uuid>","groups":[<canonical JSON strings>]},...]}` + `\n`. Key order and separators are literal; grants sort by lowercase page UUID, each groups value is exactly one of `["prices"]`, `["text"]`, `["text","prices"]`; empty vector is exact `"grants":[]`. Mechanical empty, one-grant and multi-grant vectors independently reconstruct hash before code.

Pages transaction locks Users, then every referenced Page in ascending UUID and matching PageGrant rows; it reconstructs and compares the digest, deletes all and only target grants, calls accounts `deactivate_and_bump`, and appends one `STAFF_DEACTIVATED` with new generation and removed count. Fault rolls back grants/User/audit. Empty grant set is valid. Save-first/deactivate-first retains the approved User-first serialization: at most one earlier authorized save may commit; after deactivate no later save or private request succeeds.

### Reactivate

Pages-owned `reactivate_employee` accepts inactive EMPLOYEE plus `base_user_generation` and opens the outer transaction. It locks Users in canonical order, proves target PageGrant count0 under the same transaction, calls a narrow accounts `reactivate_and_bump` participant, then appends `STAFF_REACTIVATED`. While target User is locked, concurrent grant command cannot pass its User-first active check before the zero proof/commit. No grant is restored or created; accounts imports pages0 and no callback/UoW is added.

## 3. Fixed private HTTP/UI

- `/manage/staff/` — owner-only, private/no-store list ordered by exact stored `(username, UUID)` and capped at101 rows to accept at most100; username, UUID, active and generation only.
- `/manage/staff/new/` — GET/POST fixed create form: UUID, username, password, confirmation.
- `/manage/staff/<uuid>/password/` — GET/POST fixed employee password form with base generation.
- `/manage/staff/<uuid>/deactivate/` — GET exact grant count/digest confirmation; POST exact base generation+digest.
- `/manage/staff/<uuid>/reactivate/` — GET/POST exact base generation, only when inactive and grants0.

Anonymous/EMPLOYEE receives no staff projection. POST is form-urlencoded only, CSRF protected, reuses the current exact4MiB ingress body cap, exact keys/cardinality, files/JSON/unknown fields rejected before password verification or command. Success redirects to staff list. Stale/no-change returns private409+reload. Password values are never echoed after POST and never included in safe error/log/audit. A separate tighter password transport cap/policy is not added.

## 4. Acceptance before code

- `RB4-STAFF-001`: anonymous/EMPLOYEE cannot list/create/reset/deactivate/reactivate; projection/mutation/audit0.
- `RB4-STAFF-002`: create accepts only exact employee shape, standard username/password validation, generation1 and one safe audit; owner/reserved/duplicate/malformed inputs fail atomically.
- `RB4-STAFF-003`: any existing UUID or username collision returns409 with mutation/audit0; two identical/different creates on one UUID and two UUIDs colliding on username have one winner only and no duplicate User/audit.
- `RB4-STAFF-004`: password change for active/inactive EMPLOYEE bumps once and invalidates old sessions; owner/self/unknown/stale/same-password and audit fault mutate0.
- `RB4-STAFF-005 / GRANT-AC-004`: deactivate removes all grants, sets inactive, bumps once and writes one aggregate count audit; injected fault rolls back all.
- `RB4-STAFF-006 / GRANT-AC-005`: reactivate requires inactive+grants0, restores none, bumps once and writes one audit; old sessions/grants remain absent.
- `RB4-STAFF-007 / GRANT-AC-007`: save-first/deactivate-first yields only the two approved serialized outcomes and no unauthorized post-deactivate mutation.
- `RB4-STAFF-008 / GRANT-AC-010`: actual PostgreSQL proof confirms User ascending UUID → Page ascending UUID → Grant → audit and exact module DAG accounts→pages0.
- `RB4-STAFF-009`: fixed private/no-store views, caps, CSRF/method/wire and password non-reflection/log/audit rules fail closed.
- `RB4-STAFF-010`: static inspection finds model/migration/dependency/Profile/role editor/email/MFA/CAPTCHA/delete/bulk/search/API/JS/generic form-builder/UoW changes0.
- `RB4-STAFF-011`: two password changes on one base generation yield one success/one409; reactivate-vs-grant and reactivate-vs-deactivate serialize under User-first locks, preserve grants0 at reactivation commit and never activate with an old grant.
- `RB4-STAFF-012`: exact4MiB ingress and exact-key/cardinality rejection occur before password verification/hash work; no second password cap/policy is introduced.

## 5. Gates и stop rules

Independent plan review must first close command ownership, reactivation zero-grant authority, create replay safety, exact digest and concurrency. Only then may one bounded tests-first code package begin, followed by static/code review and a separately authorized disposable PostgreSQL regression. Browser testing is unnecessary because the flow is server-rendered/no-JS.

Stop for owner choice if implementation needs changing OWNER, owner password/recovery, username rename, employee delete, arbitrary roles/groups, email identity, generic user administration, Profile, new model/migration/dependency, grant history, B002/media/public composition or a reverse accounts→pages dependency. Light compromise: leave the disputed operation read-only/deferred while implementing only independently closed lifecycle commands.
