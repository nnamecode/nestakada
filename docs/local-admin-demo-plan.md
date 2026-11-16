# Локальная demo-база сайта и админки — план

Точка D-1179 (2026-11-16): real loopback GET+CSRF+POST with the generated
clipboard-only credential returned expected303 `/manage/`; password stayed
memory-only and the host variable was cleared. PowerShell's non-terminating
MaximumRedirection=0 warning was expected from intentionally disabled redirect,
while the exact response assertion printed `LOCAL_OWNER_LOGIN_HTTP_PASS`; no
retry and no product error. Local owner login operational. Browser inspection
next; credential rotation mandatory before VPS. Live/deploy/push absent.

Точка D-1178 (2026-11-16): owner explicitly requested a generated temporary
local-test password. A 20-character printable lower/upper/digit/punctuation
secret was generated in memory, applied through existing recover_owner service,
captured only into a task-specific host variable and Windows clipboard, then
the variable was cleared. Secret was not printed or placed in chat/env/argv/
file/Git. Safe state check: owner generation4, active/usable/role valid,
throttle0, recovery audit3. Browser verification pending; rotation mandatory
before VPS. No product feature, live, deploy or push.

Точка D-1177 (2026-11-16): prior `Ctrl+V` advice for Docker TTY may have
stored an invisible Unicode `Cc`, consistently explaining hidden verifier match
and browser mismatch. Central password admission now rejects only category `Cc`
before transaction; ordinary punctuation/non-`Cc` Unicode remains allowed.
Exact named `auth-login` 3/3 PASS1.045s on fresh `1b87115d...`; review
APPROVED0/0/0. Fresh dev `4aa18827-dd34-4a12-a072-78adbb8aeea5`. Owner must
recover using Shift+Insert/right-click, not Ctrl+V, then verify login. No live,
VPS, deploy or push.

Точка D-1176 (2026-11-16): after exact dev prefill, bounded safe diagnostic
twice proved user_found/identity/state true and password_match false. No raw
credential or length was logged. Temporary diagnostics removed, diagnostic
throttle cleared, audit retained, normal dev restarted as
`d8ebfd9b-18c7-4073-af6e-92d91bdf1855`. Password check will not be bypassed;
owner handoff requires the exact stored value or deliberate hidden interactive
`recover_owner`. Live/VPS/deploy/push remain closed.

Точка D-1175 (2026-11-16): real owner password independently matched stored hash,
but safe one-shot HTTP diagnostic showed failed request `user_found=False`; owner
password was not compared. Temporary diagnostic was removed and its local
throttle row cleared without deleting audit. Minimal reviewed remediation:
dev-only exact `nesadmin` prefill, outer username trim, escaped username-only
failure preservation, never password. Named `auth-login` 2/2 PASS0.873s on
fresh `4d3d4f14-e0de-4ae3-bfe7-d29130de6ca6`; review APPROVED0/0/0. Fresh dev
`9684e3b1-49c0-4575-af62-7fd48f1776af` confirms login200, exact prefill and no
password value. Owner login verification remains; live/VPS/deploy/push closed.

Дата: 2026-11-15. Статус: **D-1174 OPERATIONAL; STATUS FIX APPROVED 0/0/0; OWNER PASSWORD HANDOFF PENDING**.

D-1174: focused independent review `$home`→`$homeStatus` вернул
`APPROVED`, P1/P2/P3=`0/0/0`; JSON `home` и read-only Status contract
сохранены. Local demo operational. Остался только owner-run hidden interactive
`recover_owner`, затем real `nesadmin` login/dashboard check. Password не
принимается через chat/env/argv/file. Повторный Load не нужен и запрещён receipt.

D-1173: fresh dev foundation `ef2ae096-10f1-4cc3-8aec-b2c2159a41ae`;
Check PASS и ровно один Load PASS. Durable receipt run
`a73cd416-8429-4de0-9abd-e4053f1fc899` фиксирует pages112/routes115,
assets/files/media238 (45,094,933 bytes), users2/profiles2, requests0,
socialLinks0, owner `nesadmin`. `/`, `/contacts`, `/manage/login/` вернули200;
Status подтвердил active/home200/login200/receipt true; ожидаемый replay отказал
до mutation. Первый Status выявил reserved PowerShell `$HOME`; variable renamed
to `$homeStatus`, focused повтор PASS. Wrapper-only fix идёт на independent
review. Пароль остаётся unset до owner hidden interactive `recover_owner`;
password не проходит через chat/env/argv/file. Live/VPS/deploy/push отсутствуют.

D-1172: independent final diff review `APPROVED`, P1/P2/P3=`0/0/0`.
Accepted direct same-connection SQL identity admission before DB/FS mutation,
literal production/test tuples, exact6 bounded seam and restoration tests,
wrong DB/user pre-mutation oracles, minimal shared cardinalities and named-only
mapping. Test foundation stopped. Next approved bounded action: recreate fresh dev
foundation, wrapper `Check`, then one `Load`; live/VPS/deploy/push remain closed.

D-1171: owner resume получен. Fresh immutable test foundation
`13b01051-fa44-4556-948d-8096ce1be055` включил host fix. После подготовки
одноразовой fixture выполнен ровно один `scripts/test-editor.ps1 -Suite
local-admin-demo`: 8/8 PASS за 89.626s. Wrong SQL DB/user cases отказали до
mutation; success/error восстановили exact6 originals; rollback и shared
cardinality regressions прошли. Broad/direct/Playwright запусков не было.
Следующий gate — independent final diff review; Load до APPROVED закрыт.

D-1170: реализация direct SQL admission и exact6 seam добавлена. Первый named
run обнаружил misplaced `path.resolve()` в `_database_identity`; host source
исправлен. Повторный named run после восстановления fixture повторил ту же
`NameError`, потому что test foundation продолжал исполнять immutable snapshot,
созданный до исправления. Read-only сравнение `/app` и host подтвердило причину.
По anti-loop правилу третьего запуска нет. После явного resume: остановить и
создать fresh test foundation, подготовить fixture, выполнить один named
`local-admin-demo`, затем independent final diff review. До этого Load закрыт.

D-1167 возобновлён владельцем «Почини и Продолжай». Exhaustive scan exact
DEV09/gallery/home producer modules показал по два environment/DB guards:
`_enabled` и `_identity`, иных identity guards в этой границе нет. Минимальный
delta расширяет существующий loader-only context exact3→exact6; strict dev/main
DB/app_runtime admission остаётся до context, producer files не меняются.
До любой DB/FS mutation и до patch loader дополнительно выполняет на той же
connection прямой `SELECT current_database(), current_user` и требует literal
`(estakada_foundation, app_runtime)`; settings NAME/USER остаются отдельной
проверкой, но не считаются SQL identity proof. Test-mode core требует реальный
unit/migrator tuple и имеет wrong-database/wrong-user pre-mutation cases.
Acceptance сохраняет function references, моделирует actual dev identity result
`(estakada_foundation, app_runtime)` для original `_identity` и доказывает отказ
всех шести originals после success и inner-context exception. Load закрыт до
plan approval, fresh named GREEN и final diff approval; затем максимум одна
новая separately reviewed execution attempt.

D-1161 возобновлён владельцем словом «почини». Exact TEST-08 producers имеют
внутренние test-only guards, требующие ENV=test, unit DB и app_migrator даже
внутри fixture override; dev one-shot по дизайну использует ENV=dev, main DB и
app_runtime. Минимальный loader-only delta после уже выполненной strict runtime
admission временно patch-ит ровно `dev09_migration_apply._enabled`,
`dev10_gallery_apply._enabled`, `dev12_home_apply._enabled` только внутри той же
outer transaction/fixture context. Producer modules/guards не редактируются,
patch не охватывает admission и всегда снимается context manager. Acceptance
доказывает: assembly success; до/после loader каждый original guard в dev
отказывает; exception path также восстанавливает originals. Новый endpoint,
command/model/migration/dependency/general importer отсутствует. До plan review,
fresh named GREEN и final diff review Load запрещён; следующая execution будет
новой separately reviewed попыткой, не автоматическим retry.

Первый Load безопасно отказался `LOCAL_DEMO_NONEMPTY_DATABASE`. Read-only
projection доказал не user/content drift, а реальный migrated baseline:
deterministic empty Header/Footer blocks generation1/currentNULL, exact two
matching shared identities, singleton zero/unvetted budget и один сохраняемый
local failed-login audit event; business/content/users/media/request/session
counts0, SYSTEM `/manage/` exact1. Исправление не удаляет/пересоздаёт seeds и
не очищает audit. Loader exact-validates baseline, локально подменяет только
fixture `create` на reuse этих empty rows и нормализует только fixture first
before-count; helper file не меняется. Любой populated shared current/draft/
revision/usage или business row по-прежнему pre-mutation refusal. После delta
review нужны fresh named acceptance и только одна Load retry; одинаковый второй
Load refusal остановит работу владельцу.

Повторяющаяся граница: два последовательных запуска после test form-encoding
fix дали одинаковый owner-login результат `200` вместо expected `303`; третьей
попытки нет. Read-only diagnosis: test class не переопределяет local-http
`AUTH_TRUSTED_PROXY_HOST="ingress"`, а one-shot test container имеет только DB
network; `source_ip()` fail-closed при DNS failure. Рекомендуемое следующее
узкое действие после owner resume: test-only `AUTH_TRUSTED_PROXY_HOST=None`,
fresh named run once. Product login code не менять.

Owner возобновил работу словом «почини». Test-only override применён; первый
возобновлённый run подтвердил loader/login3/3, но exact renderer test fixture
до test body потребовал existing RC state mount. Wrapper-only quota mount
добавлен; следующая fresh named попытка прошла4/4 за50.304s. Repeated login
error не возник. Fixture staging cleanup прошёл. Persistent Load ещё0.

## Цель и граница

Владелец подтвердил создание локальной demo-базы, чтобы одновременно смотреть
перенесённый base-MVP и существующую админку до заказа VPS. Это не production
import, не общий importer и не новый пользовательский функционал.

Выбран минимальный одноразовый профиль:

- только активный `foundation-dev`, loopback `127.0.0.1:8766`;
- только пустая dev-БД после миграций и единственный системный route `/manage/`;
- повторное использование exact TEST-08 packages, route map и исходных media с
  уже закреплёнными size/SHA;
- один закрытый Python module без URL/management command/API и один host wrapper
  без произвольных paths/commands;
- постоянные demo DB/media остаются только в существующих dev volumes;
- заявки/SMTP/Telegram/analytics/external delivery выключены;
- TEST-08 synthetic Header/Footer используются только как временный assembler
  input и до publication заменяются validated current Header/Footer: настоящий
  телефон/адрес, неизвестные соцсети и QR отсутствуют, synthetic external href
  запрещены в current public revision;
- VPS/live/старый сайт, TEST-09/10 и release gates не меняются.

Логин владельца фиксирован существующим контрактом: `nesadmin`. Loader создаёт
его с криптографически случайным невыводимым паролем только для сборки. После
GREEN владелец сам запускает существующий `recover_owner` в интерактивной
локальной консоли и дважды вводит свой пароль скрыто. Пароль не передаётся в
чат, argv, env, receipt или Git.

## Exact implementation boundary

1. `app/content/local_admin_demo.py` — закрытая dev-only assembly entrypoint и
   core; нет HTTP surface и произвольных аргументов.
2. `app/content/test_local_admin_demo.py` — bounded DB/filesystem acceptance.
3. `app/shared_content/policy.py` — только Header socials cardinality `0|3`:
   unknown links can be absent per D-927; one/two remain invalid.
4. `app/shared_content/test_shared_http.py` — exact zero/one/two/three social
   policy/public regression.
5. `app/shared_content/public.py` — только public Header binding cardinality
   `1|4`: brand-only при socials0 либо brand+socials3; два/три invalid.
6. `app/shared_content/test_shared_public.py` — exact renderer regression для
   Header binding count1/2/3/4, без изменения URL/media semantics.
7. `scripts/prepare-local-admin-demo.ps1` — `Check|Status|Load`, exact manifest,
   container/network/volume/source/hash admission и one-shot container.
8. `scripts/test-editor.ps1` — только named `local-admin-demo` test mapping и
   reuse существующих readonly TEST-08 mounts.

Не добавляются model/migration/dependency/general seed/import command, daemon,
scheduler, UI button, backup format или production configuration.

## Transaction и filesystem

- Loader требует `ENVIRONMENT=dev`, exact main DB, closed admission env и
  runtime DB identity; unit/test/production отказываются до mutation.
- До mutation все business counts должны быть0; разрешён ровно один existing
  SYSTEM route `/manage/` с `page=NULL`. Его ID сохраняется, строка временно
  удаляется только внутри общей DB transaction и восстанавливается с тем же ID
  до commit, чтобы существующий exact TEST-08 assembler видел свой проверенный
  empty baseline.
- Final media root обязан отсутствовать/быть пустым. Existing assembler пишет
  во временный `/tmp` root. Пока context жив, loader enumerates only exact
  declared `AssetFile` rows, no-follow reads every regular source and copies it
  into exact UUID staging child existing state root with size/SHA checks and
  file+directory fsync. После выхода assembler temporary root обязан исчезнуть;
  staging повторно полностью проверяется и same-FS rename публикует final media
  root перед transaction commit. Fixture helper не меняется.
- Обычная ошибка откатывает DB и удаляет только exact own staging/final tree
  после lexical containment+lstat/reparse proof. Crash/identity ambiguity не
  вызывает broad cleanup: residue сохраняется и команда `BLOCKED`.
- App container не используется для mutation. One-shot container: read-only
  root/source, UID10001, cap-drop ALL, no-new-privileges, fixed memory/CPU/PID,
  existing dev DB network/state volume, exact secret mounts, no external
  network and no Docker socket.
- Source root монтируется readonly, но loader читает только package-declared
  paths и проверяет exact bytes/SHA; route map отдельно SHA-pinned. Original
  gallery photos не преобразуются.
- После code review active dev обязательно штатно Stop/Start. Новый manifest
  должен содержать exact новые/изменённые app files и wrapper сверяет каждый
  manifest entry с current bytes/SHA перед one-shot; unexpected imported module
  или source drift закрывает Load.
- `/manage/` обход не является общим delete helper: внутри outer dev-only
  transaction loader делает `select_for_update` exact one SYSTEM row, сохраняет
  tuple `id,target,kind,page_id,is_legacy`, удаляет её только через base
  `models.QuerySet(model=Route, using='default')`, затем восстанавливает exact
  same tuple и сравнивает его до commit. Любая extra/missing/drift row — refusal.
- Local demo добавляет один owner-approved demo-only logo Asset/File из pinned
  `MED-0105` (30,190B/SHA `39feb78a...f319f5`) с fixed IDs recorded in code/tests.
  Current Header uses this logo, zero socials, real map/address and
  `+7 (499) 110-25-52`/`tel:+74991102552`; Footer uses the same logo. Итог
  assets/files238 и bytes45,094,933. Прежние synthetic shared revisions могут
  остаться только private history; public current and rendered responses must
  contain none of `synthetic`, `+70000000001`, `t.me/`, `max.ru/`,
  `instagram.com/`.

## Acceptance scenarios до исполнения

| ID | Сценарий | PASS |
|---|---|---|
| LAD-001 | wrong env/DB/admission/root | отказ до DB/FS mutation |
| LAD-002 | non-empty/foreign dev state | отказ, before/after projection equal |
| LAD-003 | fresh exact assembly | pages112, public routes114 + same `/manage/`, assets/files238, published112, requests0, delivery0 |
| LAD-004 | persistent media | count238/45,094,933B, every declared file regular and SHA-valid under final root |
| LAD-005 | credentials | users2/profiles2, owner `nesadmin`, password/employee secret absent from output; later recovery only interactive |
| LAD-006 | controlled late failure | DB rolls back to exact `/manage/` baseline; exact own staging/final removed; no foreign deletion |
| LAD-007 | success publication | canonical receipt exact counts/hashes/run UUID; final HTTP `/`, `/contacts`, `/manage/login/` return expected status |
| LAD-008 | replay | finished/non-empty demo refuses mutation; no duplicate or automatic reset |
| LAD-009 | host admission | inactive/wrong project/source/hash/container/volume/reparse/residue refuses before one-shot start |
| LAD-010 | cleanup boundary | no wildcard/broad recursive delete; ambiguity preserves evidence and fails |
| LAD-011 | current shared data | public Header/Footer use pinned logo, real phone/address and zero social links; no synthetic/external placeholder URL |
| LAD-012 | owner handoff | after hidden `recover_owner`, real `nesadmin` login succeeds and owner dashboard returns200/private/no-store; password is not recorded |
| LAD-013 | replay refusal | second `Load` is an expected pre-mutation refusal; DB/media projection and first receipt unchanged |

## Проверка и порядок

1. Independent plan review; code запрещён до `APPROVED`.
2. RED named `scripts/test-editor.ps1 -Suite local-admin-demo` only, then minimal
   implementation. Прямой широкий Django run, wildcard и Playwright запрещены.
3. Named regression only through `scripts/test-editor.ps1`; exact affected list
   is fixed after code diff, not `all`. Named `local-admin-demo` includes exact
   zero-social policy+renderer regressions; no wildcard/direct Django run.
4. Host `Check` runs actual read-only admission plus an in-memory negative matrix
   for wrong project/env/run/source hashes/paths/foreign IDs; static tests prove
   reparse and cleanup branches are fail-closed. Independent final diff review.
5. Только после GREEN/APPROVED — fresh dev Stop/Start, one `Check`, one `Status`,
   one `Load`, exact HTTP smoke, one expected replay-refusal and owner interactive
   `recover_owner` handoff followed by real login/dashboard check.

Любая вторая эквивалентная ошибка останавливает текущий этап владельцу; третьей
попытки нет. Preview8768 и dev8766 не считаются production и не публикуются во
внешнюю сеть.
