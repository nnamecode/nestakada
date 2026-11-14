# TEST-09 — план ограниченного harness

Статус D-1018, 2026-11-14. Владелец ответом «Продолжай» после прямого gate принял `TEST09-Q001=1`. Этот документ планирует bounded harness по D-1017, но не разрешает его реализацию или физический запуск. `TEST09-Q002` по-прежнему закрыт.

## Архитектура без второго framework

Предлагаются только три test-only файла/изменения:

1. `scripts/test09.ps1` — host coordinator с закрытым `ValidateSet`; нет `all`, произвольных команд, путей, shell-строк или wildcard.
2. `tools/test09-load.mjs` — Node built-ins/fetch HTTP generator для exact loopback origin и фиксированных NORMAL/SCAN/MIXED профилей; без Playwright, браузера, child process и file writes.
3. `tools/test09-storage-probe.py` — one-shot Python probe, mounted read-only и запускаемый только внутри pinned test image. Он принимает closed scenario ID, использует fixed `/t09` owned mount и импортирует существующие Django/product функции; произвольный path/SQL/module/callable не принимает.

Product routes, settings, models, migrations, management commands, services и Docker Compose не меняются. Старые Playwright acceptance specs остаются историческими oracle и не входят в запуск.

## Закрытые команды coordinator

`scripts/test09.ps1 -Package` допускает только:

- `preflight` — read-only identity/capacity/backend checks;
- `atomic` — T09-A;
- `shared-quota` и `service-quota` — две части T09-B;
- `html-enospc` и `log-quota` — две части T09-C;
- `perf-normal`, `perf-scan`, `perf-mixed` — T09-D;
- `cleanup-audit` — только проверка/удаление exact owned run resources после их ID/label/path validation.

Каждый mutating package требует canonical run UUID, fresh source snapshot, exact package-specific manifest и absence другого active TEST-09 run. Coordinator не принимает target path, rate, duration, byte cap, Docker args или test name от CLI: значения закреплены reviewed manifest/profile.

## Feasibility stop-gate до кода физических fault

Первым реализуется только read-only `preflight`.

`T09H-001`: подтвердить pinned image IDs, Docker engine, stopped foundation, workspace/root containment и отсутствие running TEST-09 resources.

`T09H-002`: проверить, что будущий `/t09` является отдельным owned mount с independently enforced capacity, а не каталогом workspace, Docker data root или системного диска. Свободное место host записывается числом, но не считается лимитом.

`T09H-003`: для HTML допускается bounded tmpfs только если measured current+previous+candidate укладываются в заранее рассчитанный memory budget и не приближаются к host pressure. Для log quota tmpfs1GiB запрещён; нужен отдельно ограниченный disk-backed backend.

`T09H-004`: если Windows/Docker Desktop не предоставляет проверяемый disk-backed hard cap для log volume, вернуть `T09_STORAGE_BACKEND_UNAVAILABLE` и остановить log-quota scope. Не создавать sparse substitute, не заполнять Docker VHDX/T:/workspace и не считать synthetic ENOSPC физическим.

`T09H-005`: preflight не создаёт большой файл, не запускает Django/DB/load и не меняет Docker/WSL/system settings. Любая установка/настройка нового storage backend требует отдельного owner proposal.

## T09-A — atomic

`T09H-006`: probe имеет exact scenario allowlist для существующих Save/draft-publish/direct-restore operations и фаз revision/media/current/audit. Он вызывает product functions напрямую внутри test process; не добавляет fault endpoint и не принимает import path/callable.

`T09H-007`: каждый scenario получает отдельную DB transaction fixture и fixed synthetic media root. Before/after projection включает current/history/draft/pins/usages/files/audit; failure обязан дать equality, positive control — exact expected delta.

Регрессии после изменения test-only harness: только named existing suites через `scripts/test-editor.ps1` (`failure`, `shared`, `public-image`, затем согласованный affected list), без wildcard/Playwright/прямого широкого Django запуска.

## T09-B — quota

`T09H-008`: shared-quota переиспользует product quota calculations и current test fixtures, но не старый Playwright driver. Closed scenarios: header/footer × count-full/bytes-insufficient × publish/restore; никаких новых лимитов или keep10.

`T09H-009`: service-quota включает только current `throttle-keys` и `temporary-bytes`. Receipt-count/bytes imports, fixtures and scenario IDs fail static admission. Protected projection содержит requests+intent_digest/media/good HTML set.

## T09-C — physical storage

`T09H-010`: HTML probe измеряет exact good-set/candidate bytes, вычисляет reviewed mount cap и получает реальный write/fsync/rename ENOSPC в одной named phase за run. Product `_fault` callbacks могут использоваться только для deterministic positioning before physical write, но не заменяют errno ENOSPC.

`T09H-011`: log-quota реализуется только после successful disk-backed hard-cap preflight и отдельного disk budget approval. Profiles79/81/96/76/74, concurrent rotation and no-space/rename-failure выполняются по одному fresh run; physical high-water считывается из filesystem, а не заявленного counter.

`T09H-012`: cleanup удаляет только exact owned container/volume/run directory после проверки resolved path, labels и manifest. При любой неоднозначности ресурсы сохраняются для владельца; broad recursive delete запрещён.

## T09-D — load без браузера

`T09H-013`: Node probe использует fixed loopback origin from signed run manifest, only allowlisted public scan paths и one pre-created synthetic owner read credential/session supplied through private mounted file. Secret/cookie не выводятся; external origin/redirect/network rejected.

`T09H-014`: rates/durations exact D-1017. Monotonic scheduler records intended/actual sends; bounded concurrency and per-request timeout prevent unbounded queue. Resource observer reads Docker stats/inspect and DB counters through closed coordinator operations, not through application test endpoints.

`T09H-015`: result JSON содержит only counts/timings/resource series/status classes/constant error codes/input hashes; no bodies, HTML, SQL, cookies, credentials, absolute paths, PII or original media.

## Anti-loop, cleanup и результаты

`T09H-016`: первая ошибка останавливает package и сохраняет safe evidence; повтор разрешён только после записанной причины и изменившегося условия. Вторая эквивалентная ошибка ставит package «Приостановлено владельцу»; третьей попытки нет.

`T09H-017`: one run = one package/scenario group. Нет автоматического перехода к следующему package после FAIL, cleanup ambiguity, OOM/restart или residue.

`T09H-018`: result status только `PASS|FAIL|BLOCKED`; отсутствие backend/метрики/phase evidence — `BLOCKED`, не skip/pass. TEST-09 AC не повышаются автоматически: после каждого пакета требуется evidence reconciliation и final exact7 review.

## Порядок реализации после review

1. Independent plan review этого документа; исправления до product/test code.
2. Реализовать только `preflight` и его offline/static tests; independent code review.
3. Выполнить read-only preflight после отдельного разрешения, без Q002 physical run.
4. Если storage backend пригоден — по одному реализовать T09-A, B, C-HTML, C-logs, D, каждый с tests-first/static review и отдельным code review.
5. Только после полного harness review и точного disk/time manifest запросить `TEST09-Q002=1` на physical execution.

Текущий следующий gate — independent plan review. Product/test harness code не начат; Docker и тесты не запускались.
