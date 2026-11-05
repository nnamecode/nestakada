# DEV29-Q034 — independent timing analysis and proposal review

Дата: 2026-11-05. Reviewer: /root/q025_reviewer. Независим от авторов анализа, design и root plan; не автор исходного terminal audit.

Verdict: ANALYSIS APPROVED; DESIGN/PLAN PROPOSAL APPROVED. Remaining findings: []. Это техническое ревью предложения только future OFFLINE архитектуры, не решение владельца, не CODE APPROVED marker и не runtime admission.

## Exact reviewed inputs

- Analysis docs/dev29-q033-timing-offline-results.md: f6c9a19734e0e06f8bc844f11d5c7d94569bc1fcbb7b82ded50834730f1dfaed.
- Evidence manifest work/dev29-q033-timing-offline-001/evidence-manifest.json: 5154fb42ab2a956e59344806d3ce2daef541b1d3b14af1cb8a94933f93a695c6.
- Final design docs/dev29-timing-observation-design.md: 7e2b7fa4d0b8192dddddedd59e89cda46e7a6bb609aa084305cdca20a890053a.
- Final root plan docs/dev29-timing-observation-plan.md: b9ce57838a707483fc088300e0ffbf257d48f322215e2e7abd8f57c7f9063e35.
- Initial design fab0912010f1298651924e99b8f28ace36d54a7fe818b3ace58bd432684ca4b8 and plan4a1bdb80635797939b6f8ff74e5ade56b3a922b59b0b7a12d7b4969dd935600c were reviewed before R1 correction; they are not the approved final pins.

## Independent evidence checks

Все32 exact ledger-named nonsecret receipts самостоятельно проверены stat/rawSHA:32/32 MATCH. Использован только подтверждённый base directory, lexical containment, basename whitelist, regular/non-symlink/nlink1; directory listing и content output отсутствовали. Никаких key/tag/host-key/privateFacts/rawACL/TLS plan чтений или ручного HMAC.

Три public evidence file pins MATCH. Четыре source pins runner/capture/controller/flow MATCH; дополнительно spec и key-stage spec MATCH с design. Самостоятельно пересчитаны11 arithmetic predicates: PASS. Это арифметика сохранённых наблюдений, не product tests и не новые native calls.

Call intervals:87299.6318ms суммарно; post-image54841.2334ms; stage residual3174.1912ms; cleanup residual617.3281ms. Округления floating-point учтены. Receipt monotonic timestamps32/32 присутствуют и не убывают; это instants, а не32 durations.

Проверенный source подтверждает: qualify total180000/initial90000, post-image min(now+55000,total-35000), timedCleanup cumulative30000 и terminal reserve5000. Controller boundDeadline дополнительно сужает stageEnd и safety lease cleanup; processCall сужает min(receivedDeadline,nativeStart+requested). Эти значения анализом не увеличиваются.

Ledger duration4182.4092ms измеряет await io.call: stageCallAdapter включает pre verify, boundDeadline, transport и post verify. Чистое native Docker время и точный winning absolute deadline UNPROVEN. Наблюдаемая pressure55s доказана нижней границей, не точной причиной host latency. Prepared remaining validity не доказывает причинность. Исходный audit a286967672d3427dded9eb5f73a7f0dbe73472ff062d745cb453702fda215166 не переписан; новая correction ограничена ошибочным pure-native wording.

## TO34-REV-001 — CLOSED

Initial P2 finding: design line44 record contract и A04/A11 не определяли полный producer scope и normal-worst-case вместимость128 records/64KiB. One-record-per-call решал phase-event multiplication, но не доказывал сохранение полезной failed-writer/full-qualification trace.

Final design закрывает gap: scope только qualify и его owned cleanup; native/phase/error updates относятся к тому же call ID. Внешние controller calls/polling excluded и не заявляются покрытыми. Source-derived conservative maximum58 calls: initial5 + roles2×12 + per-role removeActive2×8 + recover1 + finally remove8 + terminal4. Проверены actual inspect/meta/code0/code1/host, engine/info, optional Running branch, два role iterations и единственный finally; polling/retry внутри этих producers нет. Добавлены metadata8 + directory2 + fixed snapshots4:72≤128. Это консервативный upper bound, совместимость всех maxima одновременно не требуется.

Compact record-array12 fields ограничивает finite enum codes, sequence, flags/mask,12 timestamps и8 candidates. Scalar34 + outer13 + timestamps301 + candidates201 =549 JSON bytes. С hard per-record576 и envelope2048:72×576+2048=43520<65536. Предел чисел finite/nonnegative/MAX_SAFE_INTEGER/encoding≤24 bytes; invalid values дают UNPROVEN, не строковый fallback. Longest legal path, failures/incomplete-create/finally cleanup, worst-length encoder и overflow tests явно обязательны до acceptance реализации, но ещё НЕ выполнены. Cap не повышен.

## Proposal feasibility and acceptance boundary

Перечисленные existing seams допускают observer-only source delta без guard replacement. Order/count/return/error identity/cancel/authoritative clocks и capture bytes должны сохраняться. Missing spans/candidates/crossclock/ties не превращаются в guessed winner. Реальный fullguard dummy остаётся UNSUPPORTED; export primitives не означают injectable isolated controller.

Точные восемь reader/DB mappings сверены с frozen specs, включая различие staged key /probe/key vs DB /run/secrets/database-server-key и read-only DB mountArgs. Observer не меняет schema/profile/SQL/worker/corpus/ACL и не читает реальные файлы ради наблюдения.

Выбран bounded RAM и единственная best-effort fixed-prefix trace после terminal attempts/Run return, перед прежним CLI JSON. Новых lifecycle FD/FS flush/per-call stdout/await drain/retry нет. Дополнительная latency возможна и не даёт renew. Процесс crash/pipe failure/отсутствующая trace честно оставляют telemetry UNPROVEN.

Frozen operator c29e9a5338f97b50db9f90d7669c7c928ed425072b8475d3da4f19f81439ffb3 самостоятельно сверён. Parser512 drops до newline и forwardит лишь exact AWAIT; capture1MiB/stream сохраняет prefix и продолжает drain. Совместимость terminal trace/normal JSON, temporary observer budget256KiB, quota и extractor rejection ещё требуют A11 fakeIO behavioral tests. Утверждение feasibility не является выполненным wire test.

Все11 TO34-A01…A11 рассмотрены: order/exception identity, deadlines/cancel, sink failures/overflow, on-off equivalence, min/ties/clocks, adapter/native distinction, privacy/NOAUTH parser rejection, mappings, exclusive copy/delta/dependencies, actual CLI/capture boundary. R1 добавляет mandatory capacity/encoder coverage. План последовательно требует syntax→focused→affected suites→static proof/freeze→independent whole-candidate review; исторические test counts не выдаются за новый прогон.

## Limits and work performed

Owner approval Q034 ещё требуется до new public copy/implementation. Нельзя создавать active authority marker, private/stage resources, machine opinions или запускать Rehearsal/Prepare/Inspect/Readiness/Cancel/Run/Docker/PS/PG/SQL/native. Для любого будущего runtime нужен отдельный concrete plan/review/owner grant. Старый сайт и VPS исключены.

В этом review выполнены только bounded public source/document reads, назначенные nonsecret receipt stat/hash, арифметика и запись этого документа. Implementation/source/validation/operator/old reports не изменены. Product/native tests0. Один CAP precheck до вывода был штатно разделён16+16; truncation/read/tool failures0, повторных execution attempts0.
