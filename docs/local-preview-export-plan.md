# Локальный предпросмотр base-MVP — план экспорта

Дата: 2026-11-15. Статус: **IMPLEMENTED/REMEDIATED GREEN; FINAL REVIEW APPROVED (D-1148)**.

## 1. Цель и выбранный вариант

Владельцу нужен просмотр собранного base-MVP до VPS и production. Постоянный
локальный импорт сейчас небезопасен и не нужен: существующие DEV-09/10/12 apply
services намеренно разрешены только в Django test database, создают скрытые
страницы и не имеют operator endpoint. Ослаблять эти gates или добавлять общий
importer/management command запрещено.

Выбран минимальный вариант: в одном изолированном `TransactionTestCase`
переиспользовать `build_test08_fixture()` и существующий DEV-25 synchronous
HTML reserve build, сохранить одну самодостаточную generation в ignored
`work/local-preview/<runId>`, завершить test DB/fixture teardown, затем отдавать
только проверенные файлы отдельным host-only read-only HTTP server на
`127.0.0.1`.

Это визуальный локальный предпросмотр, а не persistent migration, acceptance,
DEV-26 fallback, production package или публикация.

## 2. Отклонённые варианты

- Не снимать `ENVIRONMENT=test`, DB-name/role и feature-flag guards с apply
  services: это открыло бы непроверенный постоянный импорт.
- Не держать test process/DB открытыми ради браузера и не добавлять wait-loop,
  daemon, watchdog или scheduler.
- Не возобновлять DEV-26 projection/Nginx delivery: он owner-DEFERRED D-923 и
  не нужен для локального визуального просмотра.
- Не использовать старый design-only `public-light-v4.html` как доказательство
  собранного продукта.
- Не добавлять Playwright, browser driver, API, model, migration, dependency,
  management command или новый product endpoint.

## 3. Exact implementation boundary

После отдельного owner code gate разрешены ровно три implementation files:

1. Новый `app/content/test_local_preview_export.py`:
   один `TransactionTestCase`, existing `build_test08_fixture()`, existing
   `html_reserve.build.run()`, одна generation; test DB и media fixture
   очищаются обычным teardown. Код продукта не меняется.
2. Existing `scripts/test-editor.ps1`:
   один named suite `local-preview-export`; переиспользует TEST-08 exact-SHA
   asset staging/mounts, создаёт exact per-run host directory, валидирует
   closed marker/receipt и только после success атомарно назначает ignored
   `work/local-preview/current.json`. Никаких wildcard/direct `manage.py`.
3. Новый `scripts/serve-local-preview.py`:
   stdlib-only foreground server, bind literal `127.0.0.1`, GET/HEAD only,
   exact path+query lookup из закрытого preview manifest, без directory listing,
   upload/write/proxy/external fetch/admin routes. Остановка — обычное завершение
   процесса; service/task/watchdog не регистрируются.

Документы plan/result и management entries не считаются runtime files. Любое
расширение implementation boundary требует нового review.

## 4. Export contract

Wrapper создаёт только новый каталог под ignored
`work/local-preview/runs/<runId>` и монтирует его RW в one-shot test container.
Parent/run/current paths проверяются как absolute descendants без reparse point;
runId — canonical UUID и ровно один direct child `runs/<runId>`; существующий
runId не перезаписывается. Inventory bounded: максимум exact3 run directories и
их суммарный размер не более768MiB. При достижении count/byte cap запуск
останавливается до создания каталога/current temp; автоматического удаления
старых runs нет, владелец позже явно выбирает удаляемый run. Свободное место
перед запуском — не менее 1GiB; один preview total cap256MiB, file cap8MiB,
files cap4096.

Test строит одну generation внутри fixture context и до teardown:

- повторно валидирует canonical `html-reserve-manifest-v1` через существующий
  `ReserveStore`/projection contract;
- требует exact139 public response targets текущего base-MVP:114 DB routes,
  generated gallery page1 redirect1, album query17 и page2-album query7;
  public resources only, request/client PII0 и external delivery0;
- сохраняет immutable `manifest.json`, `responses/`, `resources/` без
  переписывания HTML/media bytes;
- создаёт отдельный canonical `preview-index-v1.json`: runId, generation,
  exact canonical reserve manifest SHA, exact target/resource→relative leaf,
  status/location, content type, `x_robots_tag`, `security_policy_id`,
  `cache_policy_id`, bytes/SHA и totals. Top-level closed header policy содержит
  literal current `PUBLIC_CSP` и единственные mappings `public-v1` /
  `reserve-v1`; неизвестный policy ID отклоняется. Никаких credentials, cookies, CSRF, owner
  email setting, audit/request bodies или filesystem absolute paths.

Marker содержит только schema/runId/counts/totals/manifest+index SHA и
`fixtureAfter` closed zero vector. Wrapper принимает export только после
teardown0, exact SHA/size/count validation и отсутствия symlink/reparse/unknown
entries. Wrapper пишет canonical per-run `receipt.json` с exact index SHA после
первой validation, но run до окончания automated smoke имеет статус candidate и
ещё не является current/never-overwritten artifact. `current.json` на этом
этапе не трогается.

Весь HTTP smoke выполняется на candidate до promotion. Для controlled tamper
wrapper сохраняет original bytes в bounded memory, заменяет ровно один declared
file, требует503, останавливает child в `finally` и восстанавливает исходные
bytes только в этом ещё не принятом candidate. Затем с нуля повторяются полные
tree/manifest/index/receipt SHA/size/count/no-link checks. Только после их PASS
wrapper пишет `current.<runId>.tmp` и atomic replace `current.json`; temp имеет
ровно своё имя и удаляется только по exact path. После promotion run
never-overwritten. При любой ошибке smoke/restore/revalidation promotion не
происходит и применяются failure-cleanup rules ниже.

На ошибке container сначала обязан завершиться и mount исчезнуть. Только затем
wrapper повторно разрешает absolute parent/run paths, требует canonical UUID
direct child, проверяет отсутствие reparse/symlink во всём дереве, exact
bounded grammar известных reserve/export/temp entries и отсутствие открытого
mount. Лишь после этого допускается recursive delete только незавершённого run.
При неизвестном entry, link, path ambiguity или невозможности доказать unmount
ничего рекурсивно не удаляется: каталог сохраняется для владельца, current не
меняется, а результат честно FAIL. Предыдущие runs и прочие dirty files не
трогаются; `git reset/checkout` запрещены.

## 5. Preview server contract

Server получает один explicit absolute run path, проверяет его принадлежность
`work/local-preview/runs`, no-follow regular canonical `receipt.json` и
`preview-index-v1.json`, exact receipt→index SHA, index→reserve-manifest SHA,
schema/caps и SHA каждого файла до bind. Receipt/index/headers загружаются один
раз в память до bind; последующая подмена host index не меняет running mapping.
Затем:

- слушает только `127.0.0.1`, default proposed port8768;
- сопоставляет literal request target `path + ?query` с index; query order не
  нормализует, неизвестное возвращает404;
- на каждом GET/HEAD открывает declared relative leaf только fd-relative/no-follow,
  требует regular file и exact size/SHA непосредственно перед отдачей; mismatch
  возвращает503 без bytes. Предварительная проверка не считается достаточной;
- выдаёт только manifest-declared responses/resources с закрытым Content-Type,
  `nosniff`; CSP берётся только из in-memory top-level header policy,
  robots/cache — из закрытых manifest policy IDs/index fields; 301/302 Location
  только local;
- private/manage/history/preview/admin/request submit paths отсутствуют в index
  и не могут быть прочитаны как файл;
- не читает Git, DB, environment secrets или произвольные paths, не пишет на
  диск и не выполняет исходящий network;
- не обещает DEV-26 outage semantics, TLS, production cookies/cache или
  real-device/browser acceptance.

## 6. Acceptance scenarios

- `LPREV-001`: suite запускается только exact
  `scripts/test-editor.ps1 -Suite local-preview-export`; direct broad tests,
  wildcard и Playwright0.
- `LPREV-002`: wrong DB/environment, changed package/SHA, unsafe mount/path,
  insufficient disk или pre-existing run закрываются до export mutation.
- `LPREV-003`: one-shot fixture строит exact139 responses по closed формуле
  `114+1+17+7` и self-contained bounded resources;
  manifest/index/files/totals/SHA согласованы.
- `LPREV-004`: после export fixture DB counts0, temporary media/staging removed;
  export остаётся только в ignored host run directory.
- `LPREV-005`: wrapper автоматически запускает server как foreground child на
  loopback ephemeral test port и проверяет GET/HEAD главной, service, article,
  contacts, gallery
  root/page2/album и единственного redirect дают manifest status/body/location;
  CSS/JS/images загружаются локально; Content-Type/nosniff/CSP/robots/cache
  headers exact. Child всегда останавливается в `finally`; ручной smoke после
  GREEN используется только для визуального просмотра и не заменяет assertions.
- `LPREV-006`: до current promotion wrapper smoke проверяет
  unknown/private/manage/POST/path
  traversal/encoded escape/range outside contract и literal query distinction;
  они не раскрывают файл и не создают запись. Post-bind controlled file
  replacement даёт503 по per-request size/SHA, не старые/подменённые bytes;
  original bytes восстанавливаются после остановки child, затем полный
  candidate повторно валидируется до atomic promotion.
- `LPREV-007`: server binds loopback only, external fetch0, client/application
  PII0, request rows0, disabled forms0; process stop не оставляет service/task.
- `LPREV-008`: повторный export создаёт новый candidate; только после полного
  automated smoke, restore и повторной closed validation он становится
  never-overwritten run. Atomic `current.json` меняется только после полного
  success, предыдущий run не
  удаляется автоматически. Exact3-runs/768MiB inventory cap отказывает до
  mutation; это bounded local artifact, не tamper-proof immutable storage.

## 7. Проверки и stop rule

Сначала independent plan review. Только `APPROVED` и отдельное простое
продолжение владельца открывают implementation. Затем RED contract tests →
minimal code → единственный named wrapper run → manual loopback smoke через
server → independent final diff review. Регрессии только через
`scripts/test-editor.ps1` с точными suite names; широкого запуска/Playwright нет.

Первая ошибка фиксируется с причиной. Повтор возможен только после
изменившегося условия. Вторая эквивалентная ошибка останавливает этап владельцу;
третьей попытки нет.

## 8. Не закрывает

План не закрывает TEST-07/09/10, MEDIA-04 actual import, persistent publication,
LEGAL/backup/monitoring, owner visual acceptance, VPS/TLS/DNS, RELEASE-01–03
или production permission. После успешного preview владелец отдельно решит,
нужны ли дизайн-исправления; они не включаются автоматически в export tooling.
