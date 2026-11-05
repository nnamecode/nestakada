# Timing observation: minimal architecture proposal

Дата: 2026-11-05. Статус: DESIGN ONLY, не утверждённая реализация и не native grant. Область — будущая НОВАЯ public copy с offline fakeIO behavioural tests и независимым code review. Current frozen Q033 source59/validation/operator, timing analysis и все старые namespace неизменны. PG/Docker/SQL/Prepare/Run/native qualification допуск0.

## Цель и граница применимости

Снять наблюдения на существующих production seams без замены guard: разделить pre verify, deadline binding, transport dispatch/capture completion и post verify. Сторонний sidecar — только telemetry, не admission/signed receipt/review opinion/oracle. Не обещать fullguard dummy: полный production controller guard замкнут на действующие package/authority/private state, а qualifyForPg связывает metadata/directory/profile с module-level spec. Изолированная native инстанциация без original/privateFacts/signing ещё UNSUPPORTED.

Исходный timing report docs/dev29-q033-timing-offline-results.md RAW f6c9a19734e0e06f8bc844f11d5c7d94569bc1fcbb7b82ded50834730f1dfaed и evidence-manifest5154fb42ab2a956e59344806d3ce2daef541b1d3b14af1cb8a94933f93a695c6 сохраняются. Post-image ledger54.841s не раскрывает winning end; row4.182s включает guards. Этот дизайн не меняет их выводов.

## Source-derived boundary map

| Существующая граница | Clock/authority | Будущее наблюдение |
|---|---|---|
| key-stage/runner.mjs qualify()/call() | actual io.now(); в qualifyForPg performance.now того же Run Node | t0/total/initial deadline, image-reset snapshot, selected stage deadline; отдельная запись call seq/op/role с requested, began и тремя candidate ends |
| stageCallAdapter(hooks,transport) | guard/cancel authority сохраняется hooks.verify или hooks.safety | PRE_BEGIN/PRE_END; BOUND_BEGIN/BOUND_END; POST_BEGIN/POST_END и fixed outcome; никаких замен callback либо обработки guard error как success |
| real-host/controller.mjs qualifyKey hooks.boundDeadline | actual caller stageEnd; для safety min с lease.cleanupDeadline(10000) | фиксированные числовые candidates, результат того же min; не вычислять срок повторно для telemetry и не renew own limit |
| runner.mjs processCall() | started=performance.now(); end=min(receivedDeadline,started+requested) | транспортные candidates и passed end; NATIVE_DISPATCH около существующего spawn closure и CAPTURE_COMPLETE после того же h.done() |
| key-stage/capture.mjs capture() | переданный clock.now и end; kill/dispose/stream semantics неизменны | В этой минимальной версии capture НЕ меняется. Сохраняются его code/errorCode/signal/complete как закрытые поля, transient r.durationMs при возврате. Это capture interval, не обещание чистого OS/Docker service time |
| finally/timedCleanup и terminal/report | тот же stage clock; cleanupSpent, old deadlines | смена WORK/CLEANUP и числовые snapshots; safety и неизменный cleanup остаются при telemetry failure |

Существующие exports: stageCallAdapter, qualifyForPg в key-stage/runner.mjs; originSession/keyPolicyCore в real-host/key-origin.mjs; hostOriginIO/sameHostKey/guardHostKeyRead в real-host/key-host.mjs. Наличие этих primitives не означает exported constructor полного isolated production guard. Текущее hooks.verify в qualifyKey использует реальный keyState.verify и cancellation, safety — отдельные authority/identity checks. Их не заменять purpose branch, callback()=>PASS или сокращённым dummy guard.

## Минимальная будущая source delta

1. В НОВОЙ public copy добавить маленький bounded observation recorder, отдельно зарегистрированный в manifest. Collector scope ТОЛЬКО qualifyForPg/key qualification, включая её собственный finally/owned cleanup. Вне этого окна не собираются full PG/controller/preflight/original probes/reviews: global guard timing claim исключён. Один record на stage io.call attempt; processCall/native phases прикрепляются к тому же sequence ID, не создают дублирующие records. Metadata/directory spans и четыре snapshots ограничены отдельно ниже. Существующий stageCallAdapter может получить только optional observation sink; return sink никогда не участвует в управлении. Snapshot/event передаются уже закрытыми числовыми/enum facts, без ссылки на hooks/b/result/raw buffers.
2. В qualify/call передать наблюдателю исходные значения actual min до вызова adapter: текущий stage deadline, total, began+requested. В controller hooks.boundDeadline записать вход d, сохранённый stageEnd и один уже вычисленный safety cleanup end там, где он реально участвует, затем вернуть ТОТ ЖЕ прежний min. Ни второго lease.deadline вызова, ни повторного now+timeout.
3. В adapter отметить pre/post границы, сохраняя тот же порядок и частоту вызовов. Guard exception пробрасывается тем же объектом; observation фиксируется в finally без подавления исходного exception. Transport вызывается только после тех же guards. Native result/error и cancel не преобразуются.
4. В processCall наблюдать existing started/end и spawn closure без новых запросов/inspect/listeners/таймеров. Сохранить returned capture durationMs до того места, где ledger сейчас его теряет; не менять capture implementation, RawBudget, parsing/release или process IO. Capture completion/dispose не называть child-exit timestamp; отсутствие точного timeout-fire остаётся явным gap.
5. Внутри guarded lifecycle нет observer filesystem IO, новых FD или файлового flush, включая после expiry. Только bounded RAM. Выбран operational-wire вариант: максимум одна fixed-prefix строка NOAUTHORITY_TIMING_V1 плюс compact closed JSON через УЖЕ открытый stdout, после существующих safety cleanup/result-persist попыток и возврата Run к CLI. Controller main сейчас await dispatchHostAction(...) затем console.log(stable(out)); новая trace emission располагается непосредственно перед прежним terminal JSON, не меняя JSON payload/bytes/exit decision. Если Run не вернулся после terminal attempts либо recorder недоступен, trace отсутствует и telemetry UNPROVEN. Production guard не меняется ради гарантии trace.

Это явный stdout wire delta будущей copy, не существующий native допуск. Trace emission best-effort: нет await drain/renew/timer/retry/нового FD/console inside per-call; ошибка observer emission не заменяет original result/exception и не препятствует cleanup. Не обещается доставка после crash/закрытия pipe или завершённого budget. Конкретное error-handled stdout write должно пройти behavioural review без изменения global stream policy; final JSON content неизменен, доставка stdout не гарантируется.

Existing operator уже сохраняет/drains full stdout с1MiB cap, live-forward only AWAIT_REVIEW, поэтому trace не выводится в model и не требует менять его forwarding. Если capture truncated/trace absent/partial/duplicate/invalid — telemetry UNPROVEN. Только отдельный bounded OFFLINE extractor ПОСЛЕ terminal capture создаёт public sidecar; он не выполняется в guarded lifecycle, не вызывает modes, signer/admission/private reads. Extractor новый validation input, не authority.

Добавленная работа может сократить фактический запас времени; нулевое latency influence невозможно гарантировать. Она не может продлить срок/разрешить новый dispatch или превратить fail в success. Deadline decisions и producer clock остаются прежними. Если telemetry overhead вызывает более ранний authoritative timeout, это сохраняемый FAIL, а не основание renew.

## Sidecar contract

Предлагаемая fixed schema NOAUTHORITY_TIMING/v1, authority NONE, clockOwner RUN_NODE_PERFORMANCE_V1. Public run/package pins допустимы как attribution, но не secret input или новый accepted proof. Runtime admission/review parsers должны отвергать эту schema.

Фиксированные labels: op из существующего stage allowlist, role NONE/WRITER/READER, mode WORK/SAFETY/CLEANUP, phase CALL/PRE/BOUND/NATIVE/CAPTURE/POST/TERMINAL, outcome OK/THREW/NATIVE_FAIL/NOT_REACHED/UNKNOWN. Код native failure только существующий finite transport enum, signal закрытый enum; произвольный exception.message/stack запрещён.

Одна mutable bounded call-record по sequence number содержит phase timestamps и vectors candidate ends. Native dispatch/completion/timeout/error/concurrent/incomplete flags обновляют ЭТОТ ЖЕ record; новых phase/native/error records нет. При отсутствии current stage-call ID transport observation не записывается, telemetry scope gap отмечается fixed flag. Никаких unbounded listeners/poll events в collector. До128 records и до65536 encoded UTF8 bytes всего trace, оба hard limits; overflow не вытесняет ранние records, а помечает DROPPED_OR_INVALID/UNPROVEN.

Для доказательства размера предлагается конкретная compact wire record-array из12 полей: [type,seq,op,role,mode,outcome,error,signal,flags,timestamps,candidates,winnerMask]. type/op/role/mode/outcome/error/signal — finite integer codes0..255, seq0..127, flags/winnerMask0..65535. timestamps содержит максимум12, candidates максимум8 numeric/null slots. Числа сохраняют исходный double без округления для min/ties: finite, nonnegative, не выше Number.MAX_SAFE_INTEGER, JSON encoding каждого≤24 ASCII bytes; иначе telemetry UNPROVEN, не arbitrary string passthrough. Null занимает4 bytes. Словари enums фиксированы в versioned encoder/extractor, не передаются произвольными strings.

Max record JSON: scalar slots34 bytes, outer delimiters13, timestamps301, candidates201 =>549 bytes. С separator и запасом hard per-record limit576 bytes. Header/envelope/fixed prefix/newline ≤2048 UTF8 bytes включая public run/package attribution и bounded saturated counters/flags; никаких динамических словарей/diagnostic messages. Нарушение любого per-record/header bound даёт invalid telemetry. CLI trace не более65536 encoded bytes, включая все delimiters. Отдельный conservative temporary serialization/stream-queue budget≤256KiB остаётся ограниченным и не увеличивает native profile/capture caps.

CLOCK_UNPROVEN/OBSERVER_ERROR/BUFFER_FULL/EMISSION_UNPROVEN — закрытые telemetry flags, отдельные от production status. Sink не получает mutable production objects, ошибки наблюдения не подменяют исходные guards/returns/exception. Разрешён только finite summary/counts вне raw trace.

Forbidden: argv, Env, paths, container IDs/nonces, raw stdout/stderr, ACL/SIDs, privateFacts, tag/key/host-key bytes/content digests, HMAC/signature/authority/opinion. Telemetry sink не получает эти объекты. Никогда не читает private inputs ради наблюдения.

Каждый local min получает точные candidates из места actual computation и actual effective end. Proposed labels: STAGE_WORK, STAGE_TOTAL, CALL_REQUEST, CONTROLLER_STAGE_END, LEASE_CLEANUP_10S, TRANSPORT_REQUEST. Required candidate set определяется фактически выполненной веткой, не fabricated all-fields-null. При полном наборе, одинаковом clockOwner, valid finite numbers и captured actual comparison можно указать ALL tied minimum labels. Missing candidate/clock/span, mismatch effective min или неполная цепочка => winner UNPROVEN. Не восстанавливать parent UTC из mtime, не смешивать child/OS clocks, не считать later now+requested прежним end.

## Scope и source-derived producer bound (TO34-REV-001)

Считаются stage io.call ATTEMPTS, даже если guard/transport throws и старая ledger row не успела добавиться. Перед call precheck failure не создаёт io.call/native record; причина отражается в существующем terminal snapshot. Concurrent/incomplete/error состояния обновляют текущую запись; не порождают новые attempts. Здесь нет native retry, дополнительного create/start или cleanup polling.

В pinned runner qualify()/inspect()/removeActive()/finally только два role iterations (writer,reader), начальный и финальный циклы networks/volumes по2 значения. removeActive не содержит polling loop. Внеqualify controller cleanup/polling исключены из coverage. Все будущие новые loops/source deltas требуют заново доказать bound; не доверять числу58 при изменившемся producer.

| Producer component | Conservative maximum stage call records |
|---|---:|
| Initial engine/info, inventory, networks, volumes, image |5|
| Per role: engine1 + create1 + CREATED inspect4(meta/code0/code1/host) + engine1 + start1 + EXITED inspect4 |12 ×2 =24|
| Per-role removeActive: info/meta + optional running branch(info/stop/meta) + info/remove/inventory |8 ×2 =16|
| Finally recover, если unresolved create и active отсутствует |1|
| Finally removeActive, включая повтор safety cleanup после отказа per-role cleanup |8|
| Finally terminal engine/info + inventory + networks + volumes |4|
| Консервативный call upper bound |58|

Это upper bound, не утверждение совместимости всех максимумов: recover и некоторые active branches mutually exclusive. Ошибка обрезает основной префикс, после чего есть один finally; поэтому добавление всех finally maxima безопасно. Partial/incomplete create учтён recover1 и финальным remove8, failed cleanup может повториться только в этом finally. Arbitrary adversarial transport results могут включить Running branch, поэтому используется8, а не normal exited5. No extra attempts on observer/error events.

Отдельные noncall spans: максимум8 metadata operations — sourceBefore1, postimage source1, out1, per-role prestart source2, reader copyBefore/copyAfter2, final sourceAfter1. Directory operations максимум2 — createDirectory1 и один из retainDirectory/cleanDirectory/directoryAbsent1. Их внутренние ACL/FD substeps не создают records; наблюдается цельный span, не обещается детализация внутреннего native ACL времени. io.attempt/io.intent/result bookkeeping не являются отдельными percall records и остаются outside-call residual; если их потребуется instrument, это новый review scope.

Snapshots ровно четыре возможных слота: QUALIFY_BEGIN, POST_IMAGE_RESET, CLEANUP_ENTER, QUALIFY_END; некоторые error paths оставляют слот NOT_REACHED. Outer CLI emission status/terminal delivery — поля envelope, не дополнительные records. Итого58+8+2+4 =72 records максимум для данного collector scope, из128 остаётся56. При hard per-record576 и envelope2048:72×576+2048 =43520 UTF8 bytes, ниже65536 на22016. Это bound проектной finite schema, пока НЕ результат тестирования будущего encoder. Incomplete/throw/cleanup paths не получают иной unlimited encoding.

Обязательная будущая capacity qualification до implementation acceptance: source-used producer bound и longest success/error/Running/incomplete-create/finally-cleanup fakeIO paths; число records≤72 и каждый snapshot/nativeattach counted once; actual versioned encoder whole trace с worst-length permitted numeric values/finite enums/128th-invalid/overflow cases. Longest legal producer72 records должен сохранять early failed-writer и fullqual traces целиком ниже43520/65536, без повышения cap. Любой будущий native prequalification до этого остаётся запрещён.


## Точные восемь source mappings

Это описание frozen profiles, НЕ разрешение читать или монтировать реальные файлы. HERE_HOST = current COW real-host; REAL = current COW real; PRIV = private/bound29-c5da12a9-real; TLSROOT = work/dev15-20261102/private; COPY = TLSROOT/key29-c5da12a9-5adf-47e6-8144-f0af13018ee6/database-server-key. Все значения получены из публичного source, без private reads.

| Reader id (READER_BINDS order) | Source artifact | Reader target | DB target |
|---:|---|---|---|
|0|COPY|/probe/key|/run/secrets/database-server-key|
|1|TLSROOT/database-ca|/run/secrets/database-ca|/run/secrets/database-ca|
|2|PRIV/bootstrap-password|/run/secrets/bootstrap-password|/run/secrets/bootstrap-password|
|3|PRIV/migrator-password|/run/secrets/migrator-password|/run/secrets/migrator-password|
|4|REAL/bound-db-supervisor.sh|/tools/bound-db-supervisor.sh|/tools/bound-db-supervisor.sh|
|5|REAL/bootstrap.hba|/config/bootstrap.hba|/config/bootstrap.hba|
|6|REAL/runtime.hba|/config/runtime.hba|/config/runtime.hba|
|7|REAL/bootstrap.sql|/config/bootstrap.sql|/config/bootstrap.sql|

DBBINDS order иной: supervisor, три config, два password, CA, COPY. Тождество проверяется по source artifact и назначенной mapping, не по совпадению всех reader/DB targets: staged key intentionally /probe/key против DB /run/secrets/database-server-key. mountArgs задаёт readonly для всех DB binds; reader profile должен сохранить его exact read-only qualification, без profile mutation ради telemetry. pgReader() требует exact schema/id order/8files; pgReaderPassed() — regular, symlinkfalse, readable, openReadOnly, openedIdentityMatches, errno null для каждого. Observer не меняет и не заменяет эти proofs.

Windows dummy ACL нельзя считать автоматически равным production. hostOriginIO metadata predicate owner/current/SYSTEM должен сохраняться; существующие ACL не меняются для PASS. Fresh checked fixture creation policy и полная dummy guard state остаются отдельным неподтверждённым integration design, не частью этого observer proposal.

## E2E acceptance до реализации

TO34-A01: offline behavioural trace через ТОТ ЖЕ production stageCallAdapter с fake hooks/transport: verify→bound→transport→verify ровно один раз; safety сохраняет свой allowlist/authority order. Fake hooks здесь проверяют observer integration, не заявляют native fullguard qualification.

TO34-A02: pre guard throw => transport0/post0; original error object identity сохранена. Transport/post errors сохраняют исходный результат/exception/cleanup trace; cancellation rejection не становится success.

TO34-A03: fake clock на exact/after parent deadline, rolling own10 и shorter parent: observation не renew deadline, не вызывает deadline provider повторно и не разрешает новый action. All old timeout/cleanup limits unchanged.

TO34-A04: observer throw/invalidclock/record128 saturation/64KiB exhaustion/stdout emission/capture failure => production result/exception и safety cleanup те же, telemetry UNPROVEN. Deterministic maximum producer paths (success, final-role cleanup throw, incomplete create/recover, Running cleanup) доказывают call≤58/noncall10/snapshots4/total≤72; native phases attach sameID. Longest path byte-cap test сохраняет ранний failed writer record, all qualification records и terminal slots без eviction. Данные после лимита drain/drop без native kill/timeout changes.

TO34-A05: observer on/off fakeIO cases дают одинаковый guard/native call order, args/results/exception identities и closed capture result; recorder outputs не влияют на ветвление. При искусственном времени, потраченном на recorder, не появляется более позднее acceptance или extension.

TO34-A06: complete min/tie cases сохраняют все фактические candidate labels; missing clock/candidate, invalid numeric, crossclock и mismatch дают winner UNPROVEN, не guessed cause.

TO34-A07: adapter/transport spans различаются в synthetic known-duration fixture. Returned capture duration не подменяет await interval. Capture module bytes unchanged; processCall parsing/release/stream budget functional behaviour preserved.

TO34-A08: sentinel secrets в fake b/result/error/argv/env/privatefacts не попадают в record/summary; no arbitrary string passthrough. NOAUTHORITY schema не принимается admission/review parsерами, нет signer или accepted-proof output.

TO34-A09: exact8 mappings/schema/profile comparison против frozen specs; mutation source/target/RO/id/identity facts rejected прежними validators. Observer не читает/монтирует реальные источники и не меняет SQL/workers/corpus/UID/caps.

TO34-A10: новая copy absent/exclusive, explicit source/observer/fixture/extractor manifest + per-file delta; only syntax→observer focused→affected offline after PASS→independent code review. Все fixtures public test namespace, без fake active ART/run/rehearsal/private resources. Никаких native/modes/PG grants в этой фазе.

TO34-A11: actual CLI-boundary fakeIO test плюс production encoder capacity test доказывают whole-trace UTF8 bound с prefix/envelope/separators и worst permitted numbers/enums; max72×576+2048=43520≤65536, не только record count. Проверить concurrent/incomplete/error flags не создают дополнительных records. CLI-boundary fakeIO test доказывает cleanup/result-persist attempt precedes trace; terminal JSON payload/exit decision unchanged. Неуспешный/частичный stdout trace не вызывает FS opens/await drain/retry/guard bypass. Existing operator suppression допускает только AWAIT, trace только capture. Offline extractor rejects oversized/unknown/duplicate/incomplete trace и truncated capture, не создаёт admission. NOAUTHORITY trace максимум65536 encoded bytes включая prefix/envelope; record count128. Serialization и Node stream queue имеют отдельно ограниченный консервативный temporary budget до256KiB; это observer memory bound, не увеличение native profile/capture caps.

## Feasibility и следующий gate

Observer-only интеграция выполнима как отдельный reviewed future source delta на перечисленных seams; это design feasibility, не проверенный код. Native fullguard dummy остаётся UNSUPPORTED. Следующий шаг — независимое review данного proposal, затем отдельное решение о его offline implementation. Любой subsequent nonSQL/native diagnostic требует доказанной dummy isolation, отдельного concrete plan/review/owner approval. Новый PG Run, cap increase и purpose guard branch этим документом не предлагаются.

## Frozen source pins

- work/dev29-bounded-20261105-resume008/key-stage/runner.mjs — RAW SHA256 c0c0b34ebb317a7af66211842c54f0ea5174d8a383261704b28b4f4d11ed1fc4
- work/dev29-bounded-20261105-resume008/key-stage/capture.mjs — RAW SHA256 eb28a0a1a521946fe603a027bb1968ea6ff8af8a1a693c6fab9c9cf3aa0ff08d
- work/dev29-bounded-20261105-resume008/real-host/controller.mjs — RAW SHA256 acd225b1e79d8b8d59a4034f27b393541388e2ab41545d67eff55ad40d0a82f4
- work/dev29-bounded-20261105-resume008/real-host/flow.mjs — RAW SHA256 ba02a56b27ba63e8e6ed9992cd3454623c4b4f0164d0c4b57430ecfc9d7f8831
- work/dev29-bounded-20261105-resume008/real-host/spec.mjs — RAW SHA256 8e0b21bf1cdb25297808865bb58b25d131f89fef260efe7b71fc3e349193e402
- work/dev29-bounded-20261105-resume008/key-stage/spec.mjs — RAW SHA256 ccbe8d709e5d0675939a384aff7eff600b710a88b37c88a1e15755960fd75b52
