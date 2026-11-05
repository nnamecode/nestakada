# DEV29-Q031 — forensic review единственного failed Prepare

Reviewer: q026_result_auditor. Дата: 2026-11-05. Вывод: причина раннего FAIL установлена; PREPARED не достигнут. Новая Prepare invocation этим review НЕ разрешена.

Root: work/dev29-bounded-20261104-resume007. RunId: 35d97e6c-8049-48c4-8ab2-0ea3bdce9ed1.
Current package55: efc7d76f8b76e1966ba958eb7d174671650140f251a8de170a8481832cb05460.
Code-review document SHA256: f6b9a0b62b5ad5dab8b02fa3d5a63b7521415d55a8ba320d494ec16a680bc3a4.
Approved plan SHA256: df2c00f148f581c6f4113ccfe2febf4c76d385bfd2e36ccca87b3c44be184311.
Source55/code document/plan повторно проверены без изменений.

## Единственное исполнение и точная граница

По прямому наблюдению координатора: exact approved controller Prepare вызван один раз; exit1 за0.514с, stdout73bytes, stderr0. Readiness/Run/actual gates не запускались. Public root-prepare-001.stdout содержит только code HOST_ENTRY_FAILED/scope BOUND29-REAL-HOST/statusFAIL. Raw stdout SHA256 c774f0ea2fb968c01755378e413d8f43a74f9c94ee7dfa30a1d2f52d8a86b6a0.

Source: real-host/controller.mjs:44 prepare первым вызывает qualification('REHEARSAL'). В controller:210 qualification последовательно читает rehearsal result.json, recorder-ack.json и independent-review.json ДО проверки package и ДО возвращения в остальной Prepare. На начальном forensic snapshot первые два файла существовали с верными SHA, а rehearsal-NOAUTHORITY/independent-review.json отсутствовал. Координатор подтвердил: текстовый audit был APPROVED, machine handoff до попытки не был создан.

Следовательно первый обязательный отсутствующий input — public machine independent-review.json. Его read/regular-file check не мог пройти; private Prepare ветвь недостижима. Это failure closed prerequisite, не ошибка PostgreSQL/SQL/TLS-copy и не отказ HMAC/readiness.

Entry catch controller:213 публикует исходный message только если он соответствует закрытому uppercase-code regex. Filesystem error с path/errno не соответствует ему и превращается в HOST_ENTRY_FAILED. Оригинальный exception stack/errno не сохранён; ENOENT реконструируется из source order и подтверждённого отсутствия input, а не цитируется как сохранённый stderr. Typed public early-Prepare journal до qualification отсутствует. prepare-partial.json записывается лишь в более позднем private tag branch, сюда исполнение не дошло.

## Owned state: только exact metadata

Пути получены из frozen spec/controller/key-stage constants. Для каждого выполнен только lstat; ENOENT — штатный результат отсутствия, не retry/tool failure. До/после восстановления public gate namespaces остаются пустыми:

| Exact candidate path | Результат |
| --- | --- |
| resume007/real-host/run (ART) | ABSENT/ENOENT |
| work/dev15-20261102/private/bound29-35d97e6c-real (PRIV) | ABSENT/ENOENT |
| PRIV/tls-key-origin.tag | ABSENT/ENOENT |
| work/dev15-20261102/private/key29-35d97e6c-8049-48c4-8ab2-0ea3bdce9ed1 (STAGE) | ABSENT/ENOENT |
| STAGE/database-server-key (COPY) | ABSENT/ENOENT |

Таким образом candidate ART/private/stage trees0, tag/copy/plan0; private inputs этим Prepare не созданы. Иные private namespaces/родители не инвентаризировались; private содержимое, ключи, digests, ACL не читались. Cleanup/unlink не требуются и не выполнялись. CancelPrepared при отсутствии plan не является подходящей операцией и не запускался.

## Восстановленный public machine handoff

После failed invocation назначенный q025_reviewer сам выполнил public result review и own wx/readback. Root не копировал/подписывал его мнение. Это отдельное post-failure действие, не повтор Prepare.

Exact artifact: rehearsal-NOAUTHORITY/independent-review.json, regular420bytes.
Raw SHA256: 3553db20fd7f0c9672dc603e80f0b7c02a2d92c034b034fb4a568f06508d1753.
Auditor независимо проверил exact9 fields и все условия frozen sampleGate: текущие run/package, NOAUTHORITY/APPROVED/findings[], scope/identity, result/ack bindings, успешный NOAUTH result, clock/exit-required flags и80/490 bounds. Pure gate PASS также независимо сообщил автор artifact; auditor runtime/CLI не вызывал.

Canonical contract real-host/review-contract.mjs sampleGate:
- Ровно scope,authority,reviewer,status,runId,packageSha256,resultSha256,ackSha256,findings. Дополнительные signature/schemaVersion/observedExit поля запрещены closed schema.
- Для REHEARSAL scope=BOUND29-REHEARSAL-REVIEW; authority=NOAUTHORITY; reviewer=/root/q025_reviewer; status=APPROVED; findings=[]. Run/package совпадают с указанными выше.
- resultSha256 — RAW bytes result.json: 9a963c58da7dedc8bcfe5fcd266e163b9b21f358f99769cfb43cf491dfad64a4.
- ackSha256 — RAW bytes recorder-ack.json: 4037a9d48b940f85347e770e0b996c8ca1627d05f50d93f1f3acd4bd8ab87038.
- Это не hash enriched stdout и не canonical payload hash. JSON key order machine review не является authority; closed parsed values/pins должны совпасть.

Expected writer фиксирован контрактом: q025_reviewer после собственного result review; root/auditor q026 не должны записывать его identity вместо него. Human audit q026 сам по себе не заменяет этот machine input. Теперь REHEARSAL machine prerequisite READY, но потраченная Prepare invocation не восстанавливается.

## Полная remaining handoff/readiness matrix

| Gate | Источник/producer и точный input | Текущее состояние |
| --- | --- | --- |
| Code | Current55 и active code-review pin; положительный marker координатора только на текущий пакет | READY, unchanged |
| Rehearsal result | result/ack и независимый human audit; machine review q025 по указанной exact9 schema | READY после post-failure восстановления |
| Prepare | Текущий frozen controller; public ART/plan.json signed envelope, keySchema KEYPG-PREPARED/v1; prospective stage и private tag создаются только внутри разрешённого Prepare | Первая invocation FAIL; plan ABSENT; новая invocation требует Q032 |
| Prepared-result review | Будущий InspectPrepared — readonly bounded summary, authority READ_ONLY_NOT_DISPATCH. Затем независимый фактический review результата и фиксация координатором | NOT_RUN. InspectPrepared сейчас запрещён: plan отсутствует |
| Readiness execution | Один будущий Readiness после успешного Prepare и prepared-result review. ART/readiness/transport-attempt.json; transport-result.json; recorder-ack.json; один finite parent<=10с | NOT_RUN; отсутствие файлов сейчас ожидаемо |
| Readiness machine review | ART/readiness/independent-review.json, direct own writer q025_reviewer | NOT_RUN; не заполнять заранее |
| Final dispatch review | Внешний независимый review prepared/readiness/freshness/headroom и решение координатора до Run | NOT_RUN; не является sample JSON |
| Actual6 reviews | После новых live requests: own outbox <requestId>-<kind>.json и один PublishReview на gate | NOT_RUN; заранее мнения не создавать |

Для READINESS machine review ровно те же9 fields, но scope=BOUND29-READINESS-REVIEW. AuthorityNOAUTHORITY/reviewerq025/statusAPPROVED/findings[]/currentrun/currentpackage сохраняются. resultSha256 и ackSha256 берутся из RAW будущих signed envelopes transport-result.json и recorder-ack.json, а не их payloads; будущие значения пока неизвестны. qualification('READINESS') выполняется первой строкой Run и внутри frozen transport автоматически проверяет подписи; manual private HMAC не требуется и не разрешается.

Handoff JSON прямо задаёт readiness when: after one approved Prepare and prepared-result review, before dispatch Run. В inspected approved entrypoints/handoff нет отдельного prepared-review.json или dispatch-review.json path/schema: это внешние documented independent gates. InspectPrepared не approval; NOAUTH sample не actual admission. Их наличие нельзя придумывать и нельзя считать их пройденными по machine review другого scope.

Для actual START/INIT/PAYLOAD-C/C/PAYLOAD-T/T source schema sourceGate закрыта12 полями: scope,reviewId,reviewer,runId,kind,status,packageSha256,sourceFingerprint,resultSha256,requestId,gateNonce,findings. Scope BOUND29-INDEPENDENT-SOURCE-REVIEW, reviewer q025; status APPROVED либо CHANGES_REQUIRED; resultSha256 — actual VALUE hash из соответствующего live request, не RAW NOAUTH result hash. Direct own writer выполняет InspectReview, own wx в ART/reviewer-outbox/<requestId>-<kind>.json, затем PublishReview. Root не копирует/не подписывает source. Publisher OPINION_RECORDED не заменяет runner acceptance/consume. Все120с/parent/clock/expiry guards и согласованные stage/key proofs сохраняются.

## One-Prepare контракт и recovery recommendation

Approved plan A10 дословно: «onePrepare и atmostoneRun либо CancelPrepared».
Operator sheet дословно: «Prepare — at most once; stage absent; private origin tag; signed plan last; validity 900 seconds.»
План не содержит исключения для failed public prerequisite/no private side effects. Единственная invocation уже была; отсутствие ART/PRIV не даёт auditor/координатору права повторить её. Сторонний root invocation record сохраняется, несмотря на отсутствие внутреннего attempt marker этой ранней ветви.

Рекомендуемый предмет отдельного Q032, не разрешение из этого отчёта:
1. Сохранить failed stdout, этот forensic review и restored own machine artifact; не повторять rehearsal и не менять старые результаты.
2. До owner question независимо проверить конкретный sameCOW recovery plan другой ролью. Source/code/plan pins и stat0 должны оставаться подтверждёнными; public prerequisite matrix — без пропусков.
3. Попросить явное разрешение ровно одной ДОПОЛНИТЕЛЬНОЙ Prepare invocation на том же frozen root/run/package, без новых architecture/code/ACL/privileges/COW и без дополнительного Run. Все оставшиеся Q031 gates и первоначальный максимум одного условного Run сохраняются.
4. Только после ответа — один root Prepare; при любой ошибке STOP/no automatic retry. Только после PREPARED — actual prepared-result review, readiness<=10с, direct own readiness machine review и отдельный dispatch review, прежде чем рассматривать Run.

Diagnostic gap можно воспроизвести offline на public dummy fixtures: missing machine file перед private callbacks должен fail closed с0 side effects; valid exact9 file допускает только дальнейшую mocked ветвь. Такой reproducer/улучшение typed early diagnostics здесь НЕ выполнялись; они не являются основанием нового live запуска и не должны незаметно менять approved package. Для текущей причины code patch не нужен: missing documented handoff уже восстановлен и проверен.

## Ограничения аудита

Private reads/bytes/digests/ACL edits/source edits/tests/InspectPrepared/Prepare retry/Readiness/Run/Docker/SQL не выполнялись. Ничего не unlink. Real tool/read ошибок в audit не было; ожидаемые metadata ENOENT отражены как stat0. Записан только этот forensic report; active code-review document и ownerline не изменены. Recovery recommendation остаётся предложением, не independent approval собственного нового плана и не owner grant.
