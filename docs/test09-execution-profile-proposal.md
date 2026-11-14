# TEST-09 — предложение ограниченного профиля исполнения

Статус D-1017, 2026-11-14. Это предложение профиля для exact7 AC из группы TEST-09: `AC-052`, `AC-DTL-017`, `AC-DTL-019`, `AC-HTML-006`, `AC-OPS-008`, `AC-OPS-009`, `AC-OPS-010`. Оно не разрешает запуск, создание fault-adapter, изменение продукта или использование VPS.

Цель — получить измерения физических отказов/нагрузки без второго тестового фреймворка и без возвращения удалённых receipt/CRM/fallback подсистем. Playwright не используется. Любые регрессионные Django-наборы при будущей работе запускаются только именованно через `scripts/test-editor.ps1`, без wildcard.

## Общие границы

- Только отдельный локальный TEST-09 snapshot/проект и синтетические данные; live/VPS/старый сайт/реальные ПД/gallery originals не используются.
- До каждого пакета: clean Git inventory, running containers0, свежий snapshot, точные owned container/volume IDs и read-only before-state.
- Fault действует только на отдельный owned test volume/path под ignored `work/test09/`; системный диск, корень workspace, Docker data root и чужие volumes не заполнять и не менять.
- Текущие Compose caps являются локальным измерительным профилем, не production guarantee: app768MiB/1CPU/PIDs128, DB1GiB/1CPU/PIDs128, ingress128MiB/0.25CPU/PIDs64.
- После каждого пакета: controlled stop, owned residue audit, before/after business projection и отдельный результат. Один PASS не переносится на другой пакет.
- Вторая эквивалентная ошибка останавливает весь текущий пакет владельцу; третьей попытки нет.
- Не создавать universal fault API, daemon, scheduler, monitoring stack или broad shell/DB mutation endpoint ради тестов.

## Пакет T09-A — atomic storage faults

AC: `AC-DTL-019`.

Минимальный scope: существующие Save, draft→publish и direct restore на синтетической странице с media usage. На отдельно подготовленной тестовой БД/медиа-зоне по одному разу отказать на границах revision create, media-link validation/write, current-state switch и audit write. Для каждого варианта — новый snapshot, не повторное «дожимание» повреждённого состояния.

PASS требует полного равенства before/after для current/history/draft/pins/media usages/audit при отказе и полного согласованного изменения при положительном control. Incompatible snapshot отклоняется без переписывания/частичного применения.

## Пакет T09-B — version/quota debt

AC: `AC-DTL-017`, `AC-OPS-010`.

1. Довести существующий shared-history профиль до уже принятого measured budget; следующая запись должна наблюдаемо отказать без удаления current/history/draft/Stable/pins/used media. Не вводить keep10 для shared history и не создавать новый quota service.
2. Проверить только существующие `throttle-keys` и `temporary-bytes`: заполнение/отказ/ограниченная очистка expired technical data, затем recovery control. Рабочие заявки с `intent_digest`, used media и единственная good HTML copy неизменны.
3. Исторические `receipt-count`/`receipt-bytes` из `acceptance/service-quota.spec.js` запрещены D-1016: их не запускать и не реализовывать.

PASS требует наблюдаемого bounded отказа, сохранности защищённых данных, отсутствия рекурсивного error growth и восстановления capacity только после удаления разрешённых expired technical entries.

## Пакет T09-C — physical ENOSPC и log quota

AC: `AC-HTML-006`, `AC-OPS-008`.

HTML reserve: на отдельном bounded test filesystem по одному разу получить реальный ENOSPC в фазах build, validate, media-retain, activate и cleanup. Размер volume вычисляется после измерения actual current/previous/candidate bytes; он не подбирается так, чтобы затронуть host/workspace. Каждый вариант начинается с двух проверенных good sets и отдельного revoked-route fixture.

Log quota: реальные точки79/81/96/76/74% вокруг принятых80/95/<75 на отдельной папке CAP=1,073,741,824 bytes; затем concurrent rotation peak и no-space/rename failure. Этот пакет физически требует более1GiB плюс заранее измеренный запас Docker/артефактов, поэтому до запуска обязательны отдельная проверка свободного места и явное разрешение владельца на точный disk budget. Sparse-only evidence не считается физическим пиком.

PASS требует сохранности current/previous, used media/requests/rights/backup fixtures, отсутствия неполного candidate activation, high-water≤1GiB для управляемой log folder и не-рекурсирующего наблюдаемого отказа.

## Пакет T09-D — PERF-NORMAL/SCAN/MIXED

AC: `AC-052`, `AC-OPS-009`.

Локальный профиль измеряет только текущий capped Foundation и не экстраполируется на FirstVDS:

1. `NORMAL`: пять минут, один полезный public GET/с; отдельно один owner read каждые5с, без записей/ПД.
2. `SCAN`: 10, затем50, затем100 known-scan requests/с, каждая ступень ровно пять минут и на свежем snapshot.
3. `MIXED`: сохранить NORMAL useful stream и повторить scan10/50/100 requests/с по пять минут на ступень; log rotation/HTML build добавляются только как отдельный заранее названный вариант, не одновременно по умолчанию.
4. На каждой ступени записать actual sent/received/status/p50/p95/p99, useful errors, known-scan SQL/session/AuditEvent counts, bounded-key/log growth, container CPU/RAM/PIDs/OOM/restarts и DB connections.

PASS не задаёт выдуманный latency SLO: useful responses должны сохранять корректность/права, known scans — SQL/session/AuditEvent-per-request=0, ключи/логи не растут линейно без bound, OOM/restart/необъяснённый useful error отсутствуют. 100rps — ступень измерения, не DDoS guarantee и не обещание production capacity.

## Порядок и stop-gates

Рекомендуемый порядок: T09-A → T09-B → T09-C HTML → T09-C logs → T09-D. Каждый следующий пакет требует успешного cleanup/residue audit предыдущего. T09-D не стартует после неисправленного physical-fault residue.

До любого исполнения нужны:

1. independent plan review этого профиля и точного будущего harness delta;
2. точный snapshot/owned-path/container/volume manifest без wildcard;
3. измеренный disk/time budget, особенно для log quota;
4. owner approval `TEST09-Q001=1` на реализацию bounded harness и отдельный `TEST09-Q002=1` непосредственно на физический запуск;
5. named regression list через `scripts/test-editor.ps1`; прямой широкий запуск и Playwright запрещены.

Текущий рекомендуемый gate — `TEST09-Q001=1`: принять профиль как основу будущего минимального harness. Это ещё не разрешает T09-A–D, Docker start, fault или нагрузку.
