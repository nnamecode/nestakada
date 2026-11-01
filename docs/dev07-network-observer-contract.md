# DEV07 network — пассивный observer и overlay

2026-11-01. Короткий технический контракт до кода. Основания: dev07-network-checks.md62f670… и независимые NET001–006 в dev07-network-scenarios.md00ecda…. Только локальный test scope; product/production endpoints, ресурсы, body120 и child budgets не меняются. Подготовка observer не означает исполнения сценариев.

## Файлы и включение

Предлагаемая область исполнителя — только ignored `work/dev07-network-20261101/`: `network_observer.py`, `probe_settings.py`, `compose-network-probe.yaml`, `probe-nginx.conf`. Root создаёт/подтверждает каталог отдельно. QA владеет новыми harness/fixture adapter; прежний fixture772b… не редактируется. App/source и текущие overlays сохраняются неизменными.

`network_observer.py` монтируется RO как `/network-probe/network_observer.py`, settings — `/network-probe/probe_settings.py`; PYTHONPATH включает `/network-probe` перед прежними `/editor-probe:/app`. Прежний F `probe-config/probe_settings.py` монтируется дополнительно RO под точным именем `/network-probe/base_probe_settings.py`; новые settings делают `from base_probe_settings import *`, без циклического self-import. Прежний probe-config mount `/editor-probe` сохраняет probe_urls. Точный existing settings source hash root фиксирует до сборки. Добавляется только наружный `network_observer.NetworkObserverMiddleware`, остальные auth/session/CSRF/editor middleware сохраняют порядок. В middleware.__init__ вызывается install_once после Django setup: импорт actual views и установка observing wrappers, не ранний import models во время загрузки settings. Порядок/install count проверяется readiness.

Compose overlay app command — тот же Python/manage.py runserver0.0.0.0:8000 --noreload без --nothreading; pinned image, UID, readonly/caps/memory/CPU/pids/networks/ports прежние. Nginx копируется из принятого probe source, только exact check|save|draft location получает proxy_read_timeout150s при buffering off. App reader120s, клиентский drip5s и внешний safety watchdog180s различаются; новые ports/services/deps отсутствуют. `nginx -T` и actual command должны подтверждать это до первого теста.

## Attribution и observer API

Header `X-Estakada-Network-Probe` — ровно `<runHex>:<requestId>`, где runHex32lowercaseHEX совпадает с test-only `ESTAKADA_NETWORK_PROBE_RUN`, requestId — decimal1..32 без leading zero. Это correlation, не роль/подпись/допуск: header не выбирает путь, delays, exceptions или bypass. Invalid/неотносящийся к run header не получает record и не изменяет product response. Middleware сохраняет ID в ContextVar только на время request и reset в finally; wrappers таймера исполняются в request thread, _interrupt не патчится. Никаких cookie/CSRF/session/actor/Page/body/path/header values в observer JSON.

Внутренние функции: `install_once()` без аргументов и `NetworkObserverMiddleware(get_response)`. Публичного HTTP API нет. Thread-safe write lock защищает только краткую запись observer, никогда ожидание body/child/SQL. Оригиналы сохраняются один раз; повторная установка не оборачивает wrapper ещё раз. Ошибка readiness/install запрещает запуск сценария, но observer не формирует product refusal.

Фиксированные seams:

| Seam | Пассивное наблюдение |
|---|---|
| guards.EditorSlot.__enter__/__exit__ | original ровно1раз; acquired event только после настоящего enter; exit/fdNone после настоящего exit; Busy записывается по actual exception |
| page_editor.views.read_json_bytes | entry до original, exit/closed outcome после; реальные bytes возвращаются без копии/декодирования в observer |
| page_editor.views.normalize_input | entry/exit actual child invocation; alias общий для check/write, не заменять reader/command/result |
| guards._ReadDeadline.__enter__/__exit__ | original ровно1раз, фактический timer start и после exit: is_alive false, socket.fileno==-1, expired event; _interrupt/seconds/clock не меняются |
| outer middleware | request begin/end/actual response.status_code; finally attribution cleanup |

Обёртки сохраняют return value/exception/traceback и вызывают original ровно один раз даже при observer failure. Exit-флаги собираются только после real __exit__, не из предположения по HTTP status. Неполученный response после peer abort не выдумывается. Не измерять «child не запускался» одним PID sampling: record actual normalize entry должен оставаться0.

## Единственный IPC snapshot

Фиксированный path `/tmp/estakada-network-observer.json`, максимум65536 UTF8 bytes, mode0600, UID текущего app. До записи — сериализация bounded schema в RAM; temporary path `/tmp/estakada-network-observer.next` создаётся O_EXCL|O_NOFOLLOW|O_CLOEXEC0600, bounded write и atomic os.replace в том же tmpfs. Нет truncate чужого существующего inode, произвольных paths, history/log append, файлов request bodies или fsync-долговечности. Leftover .next/ошибка file validation — readiness failure, не самовольный recursive cleanup. Runtime counter state — один run, максимум32 records; повтор requestId либо превышение границы делает observer invalid для теста, product behaviour сохраняется.

Schema version1, точные top-level keys: `{version:1,run:runHex,ready:boolean,fault:boolean,sequence:uint,updatedMs:uint,installCount:1,requests:[record]}`. sequence растёт при snapshot update; updatedMs — monotonic milliseconds (safe integer), не wall clock. Record ровно `{id:uint,events:[uint×10],timesMs:[uint|null×10],status:uint|null,outcome:uint,timerAlive:boolean|null,duplicateClosed:boolean|null,expired:boolean|null,slotFdClosed:boolean|null}`. Массивы фиксированной длины, records сортируются по id; counters bounded safe integers, исключения/строки пользователя не сериализуются.

Event index:0requestBegin,1slotAcquired,2readerEnter,3deadlineEntered,4normalizeEnter,5normalizeExit,6readerExit,7deadlineExited,8slotExited,9requestEnd. events — фактическое число вызовов, timesMs — последний момент соответствующего события. Для begin/end длительности reader отдельно сохраняются до/после через эти индексы; один request вызывает reader/normalizer не более1раз в этих сценариях. Outcome enum:0none,1success,2busy,3bodyTimeout,4bodyInvalid,5transportUnavailable,6otherEditorFault,7otherException. Status — только actual HTTP100..599 или null. Ни произвольного exception.message, ни stack/raw URL.

Readiness: новый exclusive run/nonce, отсутствующий IPC/leftover до install, затем ready=true/fault=false/installCount1 и sequence progress на контрольном успешном request. Instrumentation failure никогда не заменяет оригинальный outcome; in-memory fault остаётся до конца run, при доступной записи публикуется fault=true. При невозможности самой записи harness обнаруживает stale/missing sequence/обязательный event в заранее bounded wait и завершает тест OBSERVER_NOT_READY. Последний старый ready snapshot не принимается как доказательство свежего этапа. Thread counters/atomic snapshot не добавляют sleeps/барьеров в product.

## Независимый fixture adapter

Предлагаемые новые fixed operations QA capsule (без изменения старого fixture): `network_observer_read`, `network_slot_try`, `network_pg_try`. Все только existing owned test app/DB; host controller исполняет статический helper под UID10001, runner не получает Docker socket/DB secrets. Read проверяет RO-no-follow regular UID/mode/nlink и≤64KiB, nonce/version/schema, возвращает только bounded JSON. Slot try проверяет тот же штатный slot inode и NB flock, сразу close/unlock в finally; он не является holder A. PG try в одном independent connection/transaction получает try_advisory_xact_lock7342810401→7342810301 и rollback, возвращает две boolean, без payload/credentials/постоянного lock.

Тестовый transport A удерживает настоящий reader неполным телом. Перед B обязательны acquired+readerEnter, deadlineEntered, normalizeEnter0, NB slot conflict и свободные PG domain locks. На Busy B — read/normalize0,503; после A completion — real normalize1 и проверенный ответ, затем явный отдельный B request с новым requestId. Пассивные counters сами не создают concurrency.

## Время и cleanup oracle

BODY_SECONDS остаётся120. ReaderEnter отмечает время до framing/guard construction, deadlineEntered — сразу после настоящего timer.start, поэтому начало отсчёта bracket между ними, не ровно TCP connect. Предлагаемый заранее заданный network tolerance: app408 приходит не ранее119s от readerEnter и не позднее130s от deadlineEntered; при задержке scheduler за пределами окна фиксируется inconclusive/failure, лимит не повышается и успех не объявляется. Guard expired=true, alive=false/duplicateClosed=true после real exit обязательны, child entry0 и slot exit1. Drip5s не продлевает deadline; ingress504/EOF не заменяют положительный app408.

Abort до Content-Length: response может отсутствовать, но reader/deadline/slot exit и timer/FD flags обязательны; healthy Check новым connection проходит. Complete Save+lost response остаётся UNKNOWN с exact operationId replay, не гарантированным rollback. Все собственные клиентские sockets закрываются перед FD-baseline сравнением. Request thread/DB keepalive FD учитываются отдельно от timer duplicate, не сравниваются одни голые FD номера. Ни temp-file absence по одному late snapshot, ни resource/MAX допуск эти counters не доказывают.

До code gate reviewer должен принять конкретные snapshot schema/seams и QA adapter operations. Затем root запускает actual configs/runtime; FR004/005 остаются pending до реального результата. Автор сейчас не пишет observer/config/harness и не запускает Docker/сокеты.
