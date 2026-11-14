# TEST-09 — план ограниченного harness

Статус D-1026, 2026-11-14: read-only preflight в `scripts/test09.ps1` independently `APPROVED`, P1/P2/P3=0. Offline `-StaticTest` PASS 17/17 без Docker; live preflight и Docker-регрессии не запускались по границе Q003. Следующий gate — owner `TEST09-Q004=1` на один read-only preflight; физический запуск по-прежнему требует отдельного `TEST09-Q002=1`.

## Архитектура без второго framework

Предлагаются только три test-only файла/изменения:

1. `scripts/test09.ps1` — host coordinator с закрытыми `ValidateSet`; нет `all`, произвольных команд, путей, shell-строк или wildcard.
2. `tools/test09-load.mjs` — Node built-ins/fetch HTTP generator для exact loopback origin и фиксированных NORMAL/SCAN/MIXED профилей; без Playwright, браузера, child process и file writes.
3. `tools/test09-storage-probe.py` — one-shot Python probe, mounted read-only и запускаемый только внутри pinned test image. Он принимает closed scenario ID, использует fixed `/t09` owned mount и импортирует существующие Django/product функции; произвольный path/SQL/module/callable не принимает.

Product routes, settings, models, migrations, management commands, services и Docker Compose не меняются. Старые Playwright acceptance specs остаются историческими oracle и не входят в запуск.

## Закрытые команды coordinator

`scripts/test09.ps1 -Package` допускает только:

- `preflight` — read-only identity/capacity/backend checks;
- `atomic` — T09-A;
- `shared-quota` и `service-quota` — две части T09-B;
- `html-enospc` и `log-quota` — две части T09-C;
- `perf-normal`, `perf-scan`, `perf-mixed` и `perf-failure` — T09-D;
- `cleanup-audit` — только проверка/удаление exact owned run resources после их ID/label/path validation.

Каждый mutating package требует canonical run UUID, fresh source snapshot, exact package-specific manifest и отсутствия другого active TEST-09 run. Fixed evidence root: `T:\nestakada\work\test09\runs\<32-lowercase-hex-uuid>`. Каждый предок от `T:\nestakada\work` до run root обязан быть обычным каталогом без reparse point; run root создаётся только после такой проверки. Coordinator не принимает target path, rate, duration, byte cap, Docker args или test name от CLI: значения закреплены reviewed manifest/profile.

## Feasibility stop-gate до кода физических fault

Первым разрешено реализовать только read-only `preflight`, и только после одобрения плана и явного `TEST09-Q003=1`.

`T09H-001`: подтвердить pinned image IDs, Docker engine, stopped foundation, workspace/root containment и отсутствие running TEST-09 resources. Preflight не создаёт/запускает контейнеры и volume.

`T09H-002`: проверить, что будущий `/t09` является отдельным owned mount с independently enforced capacity, а не каталогом workspace, Docker data root или системного диска. Свободное место host записывается числом, но не считается лимитом.

`T09H-003`: для HTML допускается bounded tmpfs только если measured current+previous+candidate укладываются в заранее рассчитанный memory budget и не приближаются к host pressure. Для log quota tmpfs1GiB запрещён; нужен отдельно ограниченный disk-backed backend.

`T09H-004`: если Windows/Docker Desktop не предоставляет проверяемый disk-backed hard cap для log volume, вернуть `T09_STORAGE_BACKEND_UNAVAILABLE` и остановить log-quota scope. Не создавать sparse substitute, не заполнять Docker VHDX/T:/workspace и не считать synthetic ENOSPC физическим.

`T09H-005`: preflight не создаёт большой файл, не запускает Django/DB/load и не меняет Docker/WSL/system settings. Любая установка/настройка нового storage backend требует отдельного owner proposal. Реализация preflight не разрешает его запуск: после code review владелец отдельно принимает `TEST09-Q004=1`.

## Общая изоляция mutating probes

Каждый mutating scenario использует отдельную новую БД с exact именем `estakada_t09_<32-lowercase-hex-uuid>`; имя не передаётся извне. Существующий PostgreSQL superuser credential монтируется только в отдельный closed one-shot bootstrap/cleanup process и никогда не виден product probe, migration container или load probe. Fixed parameterized SQL до create проверяет exact name, отсутствие строки в `pg_database`, ожидаемого owner и отсутствие collision; после create сохраняет exact name+OID+owner. Миграции и synthetic fixture выполняет `app_migrator`, product operation — `app_runtime`. Первый SQL каждого соединения сохраняет `current_database()` и `current_user`; несовпадение даёт `BLOCKED` до mutation. Постоянные `estakada_foundation` и `estakada_foundation_unit` запрещены как target и проверяются admission guard. БД не переиспользуется между сценариями.

До каждой mutation coordinator создаёт receipt через exclusive-create (`CreateNew`) в fixed run root: run UUID, exact DB name+OID+owner, container/volume IDs, labels, resolved run root и SHA-256 заранее reviewed immutable package/input manifest. Receipt немедленно fsync. Затем отдельный run/evidence manifest создаётся через `CreateNew` и включает receipt SHA-256; оба run-файла write-once, overwrite запрещён, взаимных hash-ссылок нет. Cleanup допускается только по exact receipt IDs после повторной identity/label/containment проверки и `lstat`/reparse-check exact root и каждого элемента удаляемого дерева. One-shot cleanup process получает superuser credential только для `DROP DATABASE` exact name при совпадении сохранённых name+OID+owner и только после сохранения evidence. Prefix search, enumeration-and-delete, drift/missing receipt и очистка неизвестного ресурса запрещены. При неоднозначности cleanup не выполняется, статус `BLOCKED`, evidence и ресурсы сохраняются владельцу.

## T09-A — atomic

`T09H-006`: probe имеет exact scenario allowlist для существующих Save/draft-publish/direct-restore operations и фаз revision/media/current/audit. Он вызывает product functions напрямую внутри test process; не добавляет fault endpoint и не принимает import path/callable.

`T09H-007`: каждый scenario получает fresh per-run DB по общей изоляции и fixed synthetic media root. Before/after projection включает current/history/draft/pins/usages/files/audit; failure обязан дать equality, positive control — exact expected delta.

После test-only изменения выполняются ровно named suites: `failure`, `shared-quota`, `shared`, `public-image`, `dev13`, `dev25`, `dev25-affected`, `guard`, `public-http`, `check`, `migrations`. Каждая запускается отдельной командой `scripts/test-editor.ps1 -Suite <exact-id>`. `-Suite all`, wildcard, Playwright и прямой Django test launch запрещены; широкий некалиброванный запуск не является ошибкой продукта.

## T09-B — quota

`T09H-008`: shared-quota переиспользует product quota calculations и current test fixtures, но не старый Playwright driver. Closed scenarios: header/footer × count-full/bytes-insufficient × publish/restore; никаких новых лимитов или keep10.

`T09H-009`: service-quota включает только current `throttle-keys` и `temporary-bytes`. Receipt-count/bytes imports, fixtures and scenario IDs fail static admission. Protected projection содержит requests+intent_digest/media/good HTML set.

## T09-C — physical storage

`T09H-010`: HTML probe измеряет exact good-set/candidate bytes и вычисляет reviewed mount cap. До реализации фиксируется матрица:

| Phase | Реальный capacity-consuming syscall | Требуемое evidence | Oracle |
|---|---|---|---|
| build | probe-local `build-leaf-call` immediately before exact `_write_file(parent_fd, leaf, body)`; wrapper records dir inode+leaf+body SHA-256 and delegates the real `os.write` | event fields, failing syscall=`write`, errno=`ENOSPC`, before/after bytes | good set unchanged |
| validate | нет capacity-consuming syscall в текущем validator | code-trace hash | `BLOCKED`; synthetic ENOSPC запрещён |
| media-retain | probe-local `media-write-new-call` immediately before exact `SharedStorage.write_new` with fixed synthetic body; wrapper records expected content-addressed leaf/body SHA-256 and delegates its real `os.write` | event fields, failing syscall=`write`, errno=`ENOSPC`, usages/files projection | DB/files rollback |
| activate | same-directory `os.replace` не гарантирует allocation/ENOSPC на принятом backend | code-trace hash | `BLOCKED`; отдельный calibration framework не добавляется |
| cleanup | текущая очистка не создаёт новый payload; qualifying syscall отсутствует | code-trace hash | `BLOCKED`; synthetic ENOSPC запрещён |

В каждом исполнимом сценарии package manifest фиксирует ровно один probe-local call event, один failing syscall и expected `ENOSPC`. Test-only wrapper только записывает закрытые поля события и вызывает оригинальный syscall; он не генерирует errno и не меняет product code. Если event/точный call не достигнут, это `BLOCKED`; если real syscall достигнут и вернул другой errno либо product projection нарушен, это `FAIL`. Если code hash изменился или phase не совершает указанный syscall, сценарий получает `BLOCKED` до нового review. Product `_fault` callbacks допускаются только для deterministic positioning до реального syscall.

`T09H-011`: log-quota реализуется только после successful disk-backed hard-cap preflight и отдельного disk budget approval. Profiles79/81/96/76/74, concurrent rotation and no-space/rename-failure выполняются по одному fresh run; physical high-water считывается из filesystem. Noise-first fixture обязателен: unrelated noise заполняет quota раньше protected/critical lines. Evidence содержит before/after count+bytes по классам; cleanup обязан сначала уменьшить noise и сохранить все protected/critical lines. Любая потеря protected/critical или уменьшение их раньше noise даёт `FAIL`. При потере/недоступности части источника результат не может быть честным zero/pass: `incomplete=true`, count nonzero если подтверждён, иначе count `unknown`, и общий статус `BLOCKED`.

`T09H-012`: до cleanup raw evidence копируется в fixed run root, формируется hash-bound evidence bundle (manifest, write-once receipts, projections, syscall/errno records, hashes), bundle и каталог fsync подтверждаются. Непосредственно перед удалением повторяются SHA-256 receipt/manifest и `lstat`/reparse-check всего exact удаляемого дерева; drift, missing entry или reparse point дают `BLOCKED/no delete`. Только затем разрешён exact cleanup по receipt. Volume нельзя удалить, если единственная копия evidence находится внутри него. Broad recursive delete запрещён.

## T09-D — load без браузера

`T09H-013`: Node probe использует fixed loopback origin from signed run manifest, only allowlisted public scan paths и one pre-created synthetic owner read credential/session supplied through private mounted file. Secret/cookie не выводятся; external origin/redirect/network rejected. Для `AC-HTML-006` manifest фиксирует exact previously-valid reserve delivery path, previous-set ID и manifest SHA-256; до revoke путь обязан отдать этот hash, после revoke тот же credential и exact path получают только ожидаемый denial, а previous HTML body/metadata/hash не выдаются. Иной результат — `FAIL`.

`T09H-014`: rates/durations exact D-1017. Monotonic scheduler records intended/actual sends; bounded concurrency and per-request timeout prevent unbounded queue. Resource observer reads Docker stats/inspect and DB counters through closed coordinator operations, not through application test endpoints. Для `AC-OPS-008` обязательны noise-first log source и oracle неполноты из T09H-011; без них пакет `BLOCKED`.

`T09H-015`: result JSON содержит only counts/timings/resource series/status classes/constant error codes/input hashes; no bodies, HTML, SQL, cookies, credentials, absolute paths, PII or original media. `perf-failure` — только локальный bounded subset: по одному fresh run для DB unavailable→recovery, Django unavailable→recovery, synthetic Telegram notification failure after committed request и lost response after committed request; каждый run не дольше 60 секунд, один induced failure, request timeout 5 секунд, recovery observation не дольше 30 секунд, без automatic retry. Disk и temporary-directory failure покрываются T09-C, но только где есть physical oracle. Внешний DEV26 controller/routing не входит и не имитируется. Даже полный PASS оставляет `AC-052` partial до будущего owner-authorized controller evidence; D-1017 PERF-FAILURE целиком локальным harness не закрывается.

## Anti-loop, cleanup и результаты

`T09H-016`: первая ошибка останавливает package и сохраняет safe evidence; повтор разрешён только после записанной причины и изменившегося условия. Вторая эквивалентная ошибка ставит package «Приостановлено владельцу»; третьей попытки нет.

`T09H-017`: one run = one package/scenario group. Нет автоматического перехода к следующему package после FAIL, cleanup ambiguity, OOM/restart или residue.

`T09H-018`: result status только `PASS|FAIL|BLOCKED`; отсутствие backend/метрики/phase evidence — `BLOCKED`, не skip/pass. TEST-09 AC не повышаются автоматически: после каждого пакета требуется evidence reconciliation и final exact7 review. Exact7 остаются `AC-052`, `AC-DTL-017`, `AC-DTL-019`, `AC-HTML-006`, `AC-OPS-008`, `AC-OPS-009`, `AC-OPS-010`; отсутствие любого обязательного oracle выше блокирует соответствующий AC.

## Порядок реализации после review

1. Повторное independent plan review этого remediation; исправления до product/test code.
2. Только после verdict `APPROVED` запросить у владельца `TEST09-Q003=1` на реализацию read-only preflight и его offline/static tests; это не разрешает запуск preflight.
3. Independent code review; затем запросить `TEST09-Q004=1` и только после него выполнить read-only preflight, без Q002 physical run.
4. Если storage backend пригоден, отдельно спланировать и согласовывать реализацию T09-A, B, C-HTML, C-logs, D; approval preflight не распространяется на эти packages.
5. Только после полного harness review и точного disk/time manifest запросить `TEST09-Q002=1` на physical execution.

Текущий следующий gate — owner `TEST09-Q004=1` на один read-only preflight. Docker-регрессии и physical packages не разрешены; Q002 закрыт.
