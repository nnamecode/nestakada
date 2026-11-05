# DEV29-Q031 — независимое code rereview revision004

Независимый verdict: APPROVED. Findings: []. Reviewer: q026_result_auditor. Дата: 2026-11-05.

Одобрен только current package55 SHA256 efc7d76f8b76e1966ba958eb7d174671650140f251a8de170a8481832cb05460.
Root: work/dev29-bounded-20261104-resume007. RunId: 35d97e6c-8049-48c4-8ab2-0ea3bdce9ed1.
Исторические полные package pins и findings хранятся в отдельных review-001/002/003 архивах. Положительный runtime authority marker здесь намеренно не записан: координатор сначала проверяет независимый verdict и current package. Этот документ сам по себе не разрешает Prepare/native.

## Residual R2 CLOSED

integrityIoAdapter захватывает pre-action deadline до действия; post-check использует min(capturedEnd,current shorter parent), поэтому rolling own10 не продлевается. Если open вернулся после своего cap, FD закрывается ровно один раз до последующих fstat/read. Disposal close разрешён после expiry.

Prepare и Run действительно используют общий guardHostKeyRead. Его captured token проходит до/после regular-file проверки и фактического host-key read через production read callback; post-check не создаёт новый own10. Прочитанный temporary host-key buffer очищается в finally. Full host-key/tag/original/copy verification не заменён сокращённым guard.

Прочитаны meaningful behavioral cases с actual provider min(parent90,now+10): late open/fstat/read, late manual host-key read, valid5с, earlier/dynamically shortened parent и expired preaction. Late open имеет close1/read0; после отказавшего действия следующего I/O нет. Constant-only fixture больше не служит единственным доказательством этой границы.

Immediate parent checks вокруг Original-after verify/prove и после await сохранены. Закрытые R1 и R3–R7 не переоткрыты: affected integration и unchanged source closure подтверждены.

## Exact closure

Совпали семь переданных revision004 artifact pins, source55/package, baseline/handoff/original operator/addendum/plan pins. Checkpoint70 совпал полностью; delta ровно четыре заявленных source files. Функционально неизменённый runtime admission считает текущий packageFiles из source, не принимает исторический root manifest за текущий digest.

Совпали шесть current evidence hashes. Проверены37 captured reuse dependencies: actual/previous/current hashes равны, missing0/changed0/unknown0. Evidence разделяет130 current Node +24 reused Node +55 reused Python =209 distinct, skip0. Target3 входит в focused43 и повторно не прибавлен. Это evidence builder; reviewer тесты не перезапускал.

Review ultra-narrow: residual own10 и manual Prepare/Run host-key boundaries, affected integration/current admission/evidence. Неизменённые ранее закрытые области широко не перечитывались. Real tool/read ошибок при этом rereview не было.

## Границы verdict

Исходники и public evidence читались только для review. Код не изменялся; тесты не перезапускались; private/tag/key values не читались; Docker/PG/SQL/native не запускались. Записан только этот review-документ.

Actual ACL/FD behavior, transport timings и PG факты этим static/offline verdict не доказаны. Сохраняются root validation и все предусмотренные Q031 gates: независимые rehearsal/prepared/readiness/dispatch/result reviews и максимум один условный Run. Full verify Original-after, старые deadlines/caps/rollback/corpus/cleanup не отменяются.


## Фиксация координатором (2026-11-05)

KEYPG-CODE-REVIEW APPROVED

Только current package55 SHA256 efc7d76f8b76e1966ba958eb7d174671650140f251a8de170a8481832cb05460. Независимый verdict проверен по SHA256 fa920c6517f4f7c3f9b53daff38ab6377cd3ff6030c0b4deaeb07a7e511c047e; координатор отдельно проверил55 source hashes и7 artifact hashes revision004. Это code gate; NOAUTH rehearsal, prepared/readiness/dispatch и шесть actual review gates не заменяются. Native/SQL сами этим маркером не допускаются.
