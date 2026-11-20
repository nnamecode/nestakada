# REBUILD-4 — PageGrant для существующих сотрудников

Дата: 2026-11-19. ID: `RB4-SLICE-003A-PAGEGRANT`. Статус: **PLAN APPROVED by D-1646, P1/P2/P3=0/0/0, product0/no-bloat; bounded tests-first implementation active; runtime0**.

## 1. Причина и граница

`RB4-EDITOR-001B-S4/M`, reviews и structural actions остаются B002/public-authority-bound. Сам B002 требует отдельно предоставленного production independent storage и не может быть честно материализован локальным обходом. Следующий полезный независимый от media срез — уже предусмотренная часть `RB4-SLICE-003`: owner-only управление `PageGrant` для существующих сотрудников.

Этот этап не создаёт сотрудников, не меняет пароль/username/role, не реактивирует и не деактивирует User, не добавляет Profile, permission matrix, grant history/expiry/inheritance, bulk editor, API или JavaScript framework. Staff lifecycle остаётся отдельным `003B`. B002/public composition, Page structure, SiteSettings/logo, media, live/deploy и push не открываются.

## 2. Exact product scope

Только active OWNER может для одного существующего active `EMPLOYEE` и одной существующей Page:

- установить canonical `groups=["text"]`, `["prices"]` или `["text","prices"]`;
- заменить текущий grant на другой допустимый набор;
- отозвать доступ через exact empty desired groups, что удаляет `PageGrant` row;
- увидеть username, active state, current User generation, Page name/PRIMARY path/kind и текущие группы в private/no-store HTML.

`text` допустим только для `service_section_overview`, `service_detail`, `article`, `legacy_news_article`; `prices` — только для `service_detail`. Для остальных Page kind допустимый набор пуст и mutation controls отсутствуют. OWNER не получает grant; inactive employee, OWNER target, неизвестные UUID и неизвестные/несортированные/повторные group values отклоняются целиком.

## 3. Минимальная domain-композиция

Pages остаётся владельцем outer transaction и `PageGrant`. Accounts получает только узкий public participant, который внутри уже открытой transaction блокирует actor+target User в ascending UUID, повторно проверяет owner session generation, exact active OWNER invariant и target active EMPLOYEE, но не импортирует pages и не делает commit/audit.

Public pages API сохраняет две утверждённые команды: `set_page_grant(...)` принимает non-empty canonical desired groups, а узкий `revoke_page_grant(...)` передаёт empty desired groups в тот же private mutation core. Это не два use-case слоя и не дублирование transaction/validation logic. Обе принимают target staff UUID, Page UUID, `base_user_generation` и `base_grant_hash`.

Под единым lock order `User rows → Page → PageGrant → audit` команда:

1. повторно проверяет actor session и target generation;
2. блокирует Page и текущий grant;
3. вычисляет lowercase SHA-256 exact canonical ASCII/UTF-8 bytes. Present envelope имеет ровно bytes `{"domain":"estakada.page-grant.v1","staff_id":"<lowercase-hyphenated-uuid>","page_id":"<lowercase-hyphenated-uuid>","state":"PRESENT","groups":[<canonical JSON strings>]}` + LF; absent envelope отличается literal `"state":"ABSENT","groups":[]` + LF. Key order, separators, enum string order and final LF exact; alternate JSON serialization/uppercase UUID/whitespace absent. Mechanical test vectors independently reconstruct both hashes and prove present-empty cannot exist/collide with absent construction;
4. сравнивает exact base generation+hash;
5. проверяет группы против literal Page-kind policy;
6. создаёт/заменяет/удаляет ровно один grant;
7. увеличивает target `User.generation` ровно на1;
8. пишет один `PAGE_GRANT_SET` или `PAGE_GRANT_REVOKED` с existing safe audit shape.

Fault откатывает grant, generation и audit вместе. Content/Page/Route/media rows не меняются. После commit все прежние sessions target employee становятся stale и получают401 на следующем private request.

Fresh basis с desired state, уже равным current, возвращает409 `NO_CHANGE`+reload и пишет mutation/audit0; пустой revoke отсутствующего grant имеет тот же исход. Лишнее увеличение generation ради no-op запрещено.

First review proved the previously approved retry wording unimplementable without new identity: after first commit an exact lost-response retry and a concurrent identical command both observe generation=`base+1`, matching desired state and the same audit. The server cannot return success to one and409 to the other.

D-1645 selects the light exact rule: every nonmatching `base_user_generation/base_grant_hash`, including a lost-response retry, returns409+reload with mutation/audit0. One winner/one409 remains exact. Operation UUID, receipt/history table, audit-contract expansion, generic audit lookup and heuristic retry detection are absent.

## 4. Fixed HTTP/UI

- `/manage/grants/` — owner-only список active employees с username и generation; employee/anonymous не получают private data.
- `/manage/grants/<staff_uuid>/` — owner-only список текущих grants и eligible Pages с name, PRIMARY path, kind и exact groups.
- `/manage/grants/<staff_uuid>/<page_uuid>/` — GET fixed form и POST одной mutation; CSRF, exact method, session generation, `base_user_generation`, `base_grant_hash`, repeated fixed `group=text|prices` only.

Списки server-rendered, private/no-store, сортированы стабильно и читают максимум101 employee и501 Page/grant projection, чтобы принять не более100/500; cap+1 закрывается generic503 без partial display. Пагинация/search/filter/bulk checkboxes не добавляются в этот срез. POST принимает только literal keys/cardinality, files/JSON/unknown fields rejected before command. Success redirects на target employee grant list; stale conflict возвращает409+reload.

UI скрывает недопустимую group для Page kind, но server literal policy остаётся authority. JavaScript не нужен; no-JS является основным flow.

## 5. Acceptance до кода

- `RB4-GRANT-001 / GRANT-AC-001`: anonymous/EMPLOYEE GET/POST не раскрывают staff/grant projection и mutate0; active OWNER only.
- `RB4-GRANT-002 / GRANT-AC-002`: только active EMPLOYEE target и exact Page-kind-compatible canonical subset `{text,prices}`; owner/inactive/unknown/wildcard/duplicate/order-invalid values rejected.
- `RB4-GRANT-003 / GRANT-AC-003`: set/change/revoke меняет ровно один grant, bumps target generation once и пишет ровно один typed safe audit; fault rolls back all.
- `RB4-GRANT-004 / GRANT-AC-006`: old target sessions fail401 after commit; owner actor session remains valid.
- `RB4-GRANT-005 / GRANT-AC-007`: save-first/revoke-first concurrency has the two approved serialized outcomes and no unauthorized post-revoke content mutation.
- `RB4-GRANT-006 / GRANT-AC-008`: two grant commands with one base produce one winner and one409; grant/User/audit never diverge.
- `RB4-GRANT-007 / GRANT-AC-009`: every stale base, including lost-response retry and concurrent identical loser, returns409+reload with mutation/audit0; replay identity/state0.
- `RB4-GRANT-008 / GRANT-AC-010`: lock-order test proves ascending Users→Page→Grant→audit and static DAG keeps accounts→pages0.
- `RB4-GRANT-009`: fixed GET/POST projection/wire, CSRF/method/private-no-store, cap/cap+1, unknown key/file/malformed hash/generation and direct foreign UUID paths fail closed.
- `RB4-GRANT-010`: static inspection finds model/migration/dependency/JavaScript/API/bulk matrix/history/expiry/inheritance/Profile/staff lifecycle/B002/media changes0.

`GRANT-AC-004/005` deactivation/reactivation are deliberately not claimed by `003A`; they remain `003B` acceptance.

## 6. Проверка и gates

Implementation, если план принят, ограничена: one accounts participant, two narrow public pages functions over one private mutation core, one literal policy/hash helper, three fixed server views/routes, one small template family and focused tests. Сначала tests-first domain/HTTP candidate, static checks и independent code review. Затем отдельно разрешённый disposable PostgreSQL regression; browser suite не нужна, потому что flow server-rendered/no-JS и не содержит client behavior.

Real imported-data integration всё ещё ждёт B002, но command/HTTP/concurrency можно доказать на synthetic PostgreSQL fixtures без старых usernames/passwords/ПД.

## 7. Stop rules и лёгкие компромиссы

Stop и owner review при запросе bulk grant matrix, multi-page transaction, arbitrary permission/group, role editor, staff create/password/deactivate/reactivate, grant history/expiry/inheritance, API/SPA, new model/migration/dependency или media/public composition.

Лёгкий компромисс для больших списков — отдельная будущая server pagination, а сейчас cap+1 refusal; для спорного staff lifecycle — оставить User unchanged и завершить только grant set/revoke; для B002 — продолжать defer, а не строить VHD/WSL/storage workaround.
