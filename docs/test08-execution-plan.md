# TEST-08 — план выполнения exact10 групп базового MVP

Дата: 2026-11-15. Статус: **APPROVED**, independent final review
P1/P2/P3=`0/0/0`; implementation/run NOT_AUTHORIZED.

Основания: D-1090, D-1117, `docs/test08-base-mvp-plan.md`,
`docs/test08-fixture-plan.md`. Этот документ не разрешает код, Docker-запуск,
production, VPS, TEST-09/10, сбор ПД или публикацию.

## Цель и граница

Один именованный запуск должен собрать уже утверждённый TEST-08 fixture и в том
же Django test process выполнить ровно десять групп. Это проверка существующего
base-MVP, а не новый универсальный e2e framework.

Разрешаемая будущая реализация ограничена тремя существующими слоями:

1. `app/content/test_test08_fixture.py` — только передача caller-generated
   синтетических owner/employee credentials в памяти; значения не попадают в
   receipt, marker, лог или файл. Default builder contract сохраняется.
2. Новый `app/content/test_test08_execution.py` — один `TransactionTestCase`,
   два фиксированно упорядоченных test methods по существующему fixture-образцу.
   Первый держит один `build_test08_fixture()` context и выполняет десять
   закрытых helper-групп `T08-G01`…`T08-G10`; второй выполняется после
   `TransactionTestCase` teardown первого, проверяет exact zero DB/media state и
   только тогда печатает marker. Ручной `flush` или новый cleanup runner запрещён.
3. `scripts/test-editor.ps1` — только именованный suite `test08-execution`,
   closed marker/receipt validation, exact per-run disk-backed reserve mount и
   условный memory cap1536MiB только для этого suite. Другие suites сохраняют
   memory768MiB и `/tmp`128MiB.

Product views/models/migrations/settings/dependencies/templates/JS/commands,
новые endpoints, generic runner, browser driver и Playwright запрещены. Новый
test module использует только существующие HTTP routes/services и реальные
PostgreSQL/filesystem/media-worker границы foundation-test.

## Общий исполняемый контур

- Host helper готовит тот же exact236 unique source staging, который даёт
  exact237 logical/output media, и удаляет staging в `finally`.
- Wrapper принимает только active immutable foundation-test manifest, pinned
  image, internal DB network, readonly source/registries/secrets и существующий
  private media-worker exchange volume.
- Test создаёт credentials через `secrets`, передаёт их builder и открывает
  HTTP clients с `enforce_csrf_checks=True`, `HTTP_HOST=localhost`. Пароли,
  cookies, CSRF, HTML bodies и абсолютные пути не сериализуются.
- Все десять групп выполняются до выхода из builder context в первом методе.
  Любая exception делает общий запуск неуспешным. Builder удаляет временные
  media при выходе, Django teardown очищает DB; второй метод независимо
  подтверждает exact before state и отсутствие media root до marker.
- Разрешены только именованный вызов
  `scripts/test-editor.ps1 -Suite test08-execution` и встроенный Django Client.
  Wildcard, прямой широкий `manage.py test`, Playwright и реальный браузер
  запрещены.
- Stage9 regression evidence D-1084 переиспользуется и не запускается заново.
  Wrapper принимает его только с SHA256
  `2cc94996988a5ec5c7a2e143416a9034ea906bc0d29f6c8a306122a206b2a8da`.

## Независимые expected-oracles

HTTP actual не сравнивается с заново прочитанной текущей DB как с источником
истины. До DB writes test читает closed approved package descriptors, проверяет
их pinned SHA и строит immutable expected projection: identity, target, parent,
position, name/H1/title/description, content-shape и SEO flags. DB/HTTP являются
только actual. Route/media registries задают независимые exact sets.

Pinned inputs:

| Источник | SHA256 |
|---|---|
| `docs/analytics-route-map.csv` | `c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8` |
| `docs/analytics-media-evidence.csv` | `52823a26c535f6bcbb45601fccad630278d59d421ab5f87b25bb1390d28867ca` |
| `app/content/dev09b_articles_slice.json` | `2936561288256d42968363afe90147678aa6fc88bbdff9faf21fde1c2d986639` |
| `app/content/dev09e_services_catalog.json` | `beffdfdbacc6a24a71c68ee692f03be262f67745b8425e1ce9b204b8d15ca9e9` |
| `app/content/dev09g_service_roots.json` | `956c35fb5697acb23b039a980d1915228bd1100f1884ebece3fcd909ace365db` |
| `app/content/dev09h_service_details.json` | `439dea21aa4257e934e0781faec982bb05157d5a734171ced58086df4e8bd52a` |
| `app/content/dev09i_planned_maintenance.json` | `fa0e85ba9640ffa45916e810bece20e949698b3dbe82f9ead99750210b98a5cf` |
| `app/content/dev09j_leading_price_details.json` | `e091047ae5272fa9834d828d5ed73e1fbc914a41faa07e4367b9787ad0a8934d` |
| `app/content/dev09k_diagnostics_branch.json` | `9980c60a1a2ee354ef156c7f9695cfc76ec051f798dfe3610a95f3e29c473e67` |
| `app/content/dev09m_combined_services.json` | `3fb682d6a092d78439fa45b541668554d793490b41eb89d311359738053f8e01` |
| `app/content/dev09m_infographic_map019.json` | `fe083d206a72a3850bb30a554e57d375eba3338aacd87842c6c17f99a0f34954` |
| `app/content/dev09n_remaining_content.json` | `a47eb0118dd04ede21eebd995e870ddbf3d0895f7ad9e17f806b27babdccf3ed` |
| `app/content/dev10_gallery.json` | `9db5b026d6affa4668e2ca19268d8663355c1e22504f6aba6aa1676ed3d41b3b` |
| `app/content/dev12_home_profile.json` | `c12caba76e429ac11496b0a299f61919f7c8a1c200f494acb99e08baff9d4d56` |

Expected exact baseline: packages project112 pages/112 primary routes plus two
approved aliases =114 DB routes; registry exact115 includes the one runtime
page1 redirect. Gallery exact17 albums/214 originals. Home profile exact8
advantages,8 services,6 price groups/47 rows,6 works and15 design media.
Expected projection and sorted path-set SHA are saved before fixture mutation;
actual SHA alone никогда не является PASS-oracle.

## Точные группы и acceptance

Каждая группа возвращает только `PASS`, `PARTIAL` или `BLOCKED`. `PASS` возможен
лишь при выполнении всех перечисленных сценариев; первый mismatch завершает
именованный test с ID сценария.

### T08-G01 — Public URL/content

- `T08-G01-A`: registry hash и sorted set равны fixture contract: exact115
  literal request targets, без нормализации query и без подмены адресов.
- `T08-G01-B`: exact114 DB-backed targets отвечают 200 на literal GET.
- `T08-G01-C`: единственное исключение
  `/gallery-of-works/?page=1` отвечает 302 с exact `Location` на
  `/gallery-of-works/`, после чего корень отвечает 200. Ни один другой URL не
  засчитывается через redirect.
- `T08-G01-D`: для 200 response проверяются pinned package expected projection,
  canonical/indexing contract и отсутствие private/admin state; для gallery
  query применяется уже утверждённая noindex/canonical policy.

Evidence: route count115, status histogram, redirect count1, content/canonical
projection SHA и route-set SHA. Полные HTML bodies в receipt не входят.

### T08-G02 — Public composition/navigation

- `T08-G02-A`: Header и Footer присутствуют ровно по одному разу, используют
  текущие shared revisions и разрешённые локальные assets.
- `T08-G02-B`: опубликованное дерево, service catalogs/details, breadcrumbs и
  navigation совпадают с immutable package projection без duplicates.
- `T08-G02-C`: owner через существующий GET/POST confirmation flow временно
  скрывает назначенный leaf `/articles/zamena-masla-v-dvigatele`: literal public
  route становится blank200/noindex/no shared content, leaf исчезает из
  navigation, остальные package nodes сохраняют expected parent/order. Owner
  тем же flow публикует leaf обратно; public/navigation projection и
  publication flag возвращаются к exact before.
- `T08-G02-D`: responsive viewport/meta и approved CSS media-query markers
  присутствуют. Это проверка server markup/static contract, не TEST-10 и не
  заявление о реальном устройстве.

Evidence: page/tree/nav/breadcrumb counts и compact projection SHA.

### T08-G03 — Owner authentication/admin

- `T08-G03-A`: anonymous login GET 200; корректный owner POST с CSRF даёт 303,
  session rotation и private/no-store response; неверный пароль не входит в
  positive flow и не нужен для PASS этой группы.
- `T08-G03-B`: authenticated owner получает dashboard и owner-only employee,
  audit, request-settings и HTML-reserve routes; employee получает dashboard,
  но на owner-only routes — 403; anonymous — 401.
- `T08-G03-C`: logout POST с CSRF даёт 303, session перестаёт открывать private
  route. Затем создаётся новый owner session для последующих групп.

Evidence: status/cache/session-state vector без session IDs и credentials.

### T08-G04 — Employee permissions/editor

- `T08-G04-A`: employee открывает назначенную article page и разрешённое поле
  intro; другая page и защищённые операции закрыты.
- `T08-G04-B`: реальный editor check/save меняет только granted intro, сразу
  публикует результат и создаёт ровно одну automatic version; H1/title/URL,
  publication/tree/grants и protected fields не меняются.
- `T08-G04-C`: повтор старого base receipt получает controlled conflict без
  mutation.
- `T08-G04-D`: owner отзывает grant; уже открытая employee session больше не
  может сохранить. Grant затем возвращается существующим owner service для
  продолжения fixture, с новым generation.

Evidence: expected/actual status vector, revision delta и protected projection
before/after SHA.

### T08-G05 — Versions/restore

- `T08-G05-A`: owner создаёт manual named version и назначает одну Stable;
  employee видит ordinary/manual/Stable labels, но не может назначить или снять
  Stable.
- `T08-G05-B`: compare выполняется read-only для двух реальных revisions.
- `T08-G05-C`: employee direct restore создаёт новую current revision только с
  разрешённым intro; owner direct restore восстанавливает полный совместимый
  content profile. URL/tree/publication/grants/Stable/shared не меняются.
- `T08-G05-D`: после controlled saves остаются exact10 последних ordinary;
  самая старая ordinary удалена из лимита, manual и Stable сохранены.

Evidence: version-kind/count vector, compare digest, restore deltas и protected
projection SHA.

### T08-G06 — Media

- `T08-G06-A`: owner через реальный upload HTTP и foundation media-worker
  загружает один небольшой детерминированный synthetic PNG; ready main/preview
  проверяются по реальным bytes/dimensions. Неверные extension/MIME/oversize
  отклоняются до регистрации Asset.
- `T08-G06-B`: существующий media picker показывает asset только в допустимом
  контексте; editor replace меняет разрешённый slot и usage, не защищённые поля.
- `T08-G06-C`: cleanup prepare является read-only; late usage блокирует stale
  confirmation; после снятия только synthetic usage новый prepare/confirm
  удаляет synthetic asset и реальные bytes.
- `T08-G06-D`: exact214 gallery originals имеют те же byte sizes/SHA до и после;
  ни один из них не декодируется, не перекодируется и не удаляется.

Evidence: synthetic upload/usage/cleanup vector, original count214, aggregate
bytes и sorted SHA-set digest. Synthetic image bytes в receipt не входят.

### T08-G07 — Gallery/home/SEO

- `T08-G07-A`: gallery projection содержит exact17 albums и exact214 originals;
  root/page2 и canonical modal links отвечают по утверждённому query contract.
- `T08-G07-B`: home actual совпадает с pinned home package: exact8
  advantages,8 services,6 price groups/47 rows,6 works и15 design media в
  descriptor order; external embeds отсутствуют.
- `T08-G07-C`: title/description/H1/canonical/robots directives coherent для
  indexable и query pages; sitemap содержит exact indexable canonical targets,
  robots использует test deny-all profile без изменения production policy.

Evidence: album/photo/home/SEO counts и projection SHA.

### T08-G08 — Requests default-off

- `T08-G08-A`: home, contacts и service pages не содержат request form,
  submit intent, CSRF field или клиентские/application PII при intake off;
  утверждённые публичные реквизиты предприятия остаются видимыми.
- `T08-G08-B`: direct submit остаётся feature-disabled; ServiceRequest rows0,
  client/application PII rows0, external delivery0 и request-success audit0
  before/after. Счётчик сетевых попыток не заявляется.
- `T08-G08-C`: owner может читать private request email setting route;
  employee получает403, anonymous401. Значение не выводится в public response и
  не записывается в evidence.

Evidence: closed status/count vector и public absence digest. Реальные
клиентские/application PII rows0 и external delivery0; утверждённые публичные
реквизиты предприятия разрешены; private owner recipient не сериализуется;
network-attempt counter не заявляется.

### T08-G09 — Logs/readiness/local operations

- `T08-G09-A`: существующий owner audit list `/manage/audit/` private/no-store и
  read-only; employee403, anonymous401; сортировка newest-first и typed event
  projection проверяются на синтетических строках. Detail route не существует
  и не добавляется.
- `T08-G09-B`: existing `cleanup_audit` с fixed clock удаляет только события
  строго старше30 суток, сохраняет boundary/newer и не меняет другие таблицы.
- `T08-G09-C`: existing readiness command делает bounded read-only PostgreSQL
  check, возвращает success без stdout/stderr и без DB mutation.
- `T08-G09-D`: Docker rotation probe не повторяется. Wrapper сверяет SHA
  `environment/foundation/compose.yaml`
  (`e1015cd4c8ff1ceadd2a04fffbb1f49c8aade1621a6dd6363938e014c4df785a`)
  и approved `docs/ref6-log-rotation-results.md`
  (`4855e07d7f2e397b67a42fdbca51b86d5f8d2c934b8066596308003af40b1ce9`);
  PASS опирается на D-643 actual inspect/probe плюс неизменившийся exact config:
  `json-file`, `10m`, `3` только для app/db/ingress/media-worker.

Большой раздел логов/Telegram из `docs/logging-proposal.md` не реализован и в
TEST-08 PASS не включается. Внешний monitor остаётся TEST-09/launch gate.

### T08-G10 — Manual HTML reserve

- `T08-G10-A`: anonymous status401, employee403, owner200/private; initial status
  честно показывает отсутствие generation.
- `T08-G10-B`: owner делает два реальных synchronous build POST с CSRF во
  временный `HTML_RESERVE_ROOT`; оба используют current fixture capture и
  existing renderer. Второй status показывает exact current и previous UUID.
- `T08-G10-C`: оба manifest проходят store validation, покрывают closed exact
  target set/status/Location, содержат только local self-contained resources и
  exact byte/file totals; retained-html usages совпадают с current+previous.
- `T08-G10-D`: HTML не содержит form/manage/history/preview, cookies, CSRF,
  synthetic credentials или request PII. После выхода temporary reserve bytes
  отсутствуют; fixture teardown убирает retained usages.

Nginx delivery/fallback, scheduled build, backup и production filesystem не
проверяются и остаются отдельными gates DEV-26/TEST-09/launch.

## Result marker и host receipt

Test печатает ровно один `TEST08_EXECUTION_RESULT=<base64url-json>` не длиннее
32768 символов. Closed schema `test08-execution-result-v1` содержит только:

- `runId`, четыре входных SHA и `routeSetSha256`;
- `fixtureBefore`, `fixtureAssembled`, `fixtureAfter` по уже утверждённому
  25-key count contract;
- массив ровно десяти объектов в порядке `T08-G01`…`T08-G10`. Closed объект
  каждой группы содержит `groupId`, тот же `fixtureRunId`, exact
  `scenarioIds`, sorted actor enum (`anonymous|owner|employee|system`),
  `paths={count,sha256}`, bounded typed `expected` и `actual` vectors,
  `before={counts,sha256}`, `after={counts,sha256}`, `projectionSha256` и
  `status`; неизвестный key/actor/vector shape запрещён;
- `allPassed=true` только при десяти `PASS`;
- `mediaBefore/mediaAfter`, `reserve` totals и `externalDelivery=0`.

Wrapper декодирует marker, отклоняет неизвестные/лишние keys, группы, порядок,
status, SHA, count drift, marker overflow и любой не-PASS. Финальный ignored
receipt `work/foundation/test/test08-results/<runId>-execution.json` создаётся
только после verified staging cleanup и `fixtureAfter==0`. Receipt path защищён
от escape/reparse, существующий файл не перезаписывается.

## Ресурсные пределы и остановка

- Suite сохраняет 1 CPU,128 pids, read-only root,no-new-privileges,internal
  network и `/tmp`128MiB. Только `test08-execution` получает memory/swap cap
  1536MiB; другие suites остаются768MiB.
- Wrapper создаёт exact host directory
  `work/foundation/test/test08-reserve/<runId>` только если path находится под
  validated parent, parent/target не reparse, target отсутствует и на томе
  свободно не менее1GiB. Directory bind-mount RW в `/test08-reserve`; это
  единственный writable reserve root. В `finally` wrapper проверяет тот же
  canonical path, удаляет только его и подтверждает отсутствие до receipt.
- Existing storage допускает максимум две активные generation по256MiB; wrapper
  дополнительно отклоняет host peak/final reserve usage >544MiB. Worst admitted
  memory accounting при pessimistic charged disk page cache: reserve544MiB +
  один Python `files` payload256MiB + fixture-media tmpfs45,221,681B оставляют
  более690MiB внутри cap1536MiB для Django/PostgreSQL client/overhead. Previous
  generation хранится на disk bind, не как второй Python payload. Actual
  generation1/generation2/host-peak bytes входят в receipt. Это test-only
  bounded placement, не product/runtime настройка.
- Synthetic upload ≤4 KiB; route targets115; groups10; reserve generations2;
  external delivery0; реальные данные клиента/заявки0. Утверждённые публичные
  реквизиты предприятия не считаются клиентскими ПД и сохраняются в content.
- При первой ошибке фиксируются scenario ID, безопасная причина и необходимое
  изменившееся условие. Вторая эквивалентная ошибка останавливает работу; третьей
  попытки нет. Docker/host failure не объявляется дефектом продукта.
- Общий TEST-08 PASS возможен только после независимого review этого плана,
  отдельного owner permission, реализации, named run и десяти PASS. Ни один
  документальный или fixture-only результат не заменяет execution evidence.

## Следующие gates

1. Независимое read-only review плана с P1/P2/P3 и no-bloat verdict.
2. При `APPROVED` — отдельное простое разрешение владельца на exact three-file
   реализацию и один именованный запуск.
3. После GREEN — независимое diff/evidence review. TEST-09/10, production,
   deployment и VPS этим не открываются.
