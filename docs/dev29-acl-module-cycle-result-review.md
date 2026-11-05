# Q033 — independent terminal Run result audit

Дата: 2026-11-05. Reviewer: q026_result_auditor.
Verdict: target Run FAIL. Corpus/original preservation PASS; owned-resource/stage/tag cleanup PASS. Underlying host latency and exact winning absolute deadline UNPROVEN. P29-A/PG qualification не завершена, новый Run не разрешён.

Exact package59 c281f40640f200c71e7ce084a3ded3885f49bb06728b373482c0f91ffdcbee44; RunId c5da12a9-5adf-47e6-8144-f0af13018ee6. Root invoked one reviewed operator/Run while Prepared admission remained valid (root witness ~172214ms remaining). Sole Run consumed; no retry/extra Prepare/Readiness/Inspect/Run. Actor reports actualInspect0/actualPublish0/opinions0. No AWAIT was emitted; the SQL conclusions below rely on control flow and receipts rather than notification absence alone.

## Terminal and signed result pins

Public q033-run001.capture-summary.json raw0b4605172f2227c9823e22fa341c2ca4d18be3501f309b72d0b64f11538cc71a: exit1/signal null/spawnErrorfalse. stdout481B raw86c763bf36e6c842bae0bf0a93f74668fc3149759b25c2633c45f0a405078065; stderr0 raw emptySHA. Capture truncation/io/forwarding errors false, no artificial timeout or controller kill by wrapper. Root observed session70077 terminal exit1.

Named nonsecret signed receipts in private bound29-c5da12a9-real:
- result.json raw69f7ae6122ff59d8b872ac68473a5e6cf0ac4fa407e7ba80fa274f190beb02f5: FAIL/phase PREFLIGHT/code KEYPG_QUALIFICATION; phases0/witnesses0/keyQualification absent.
- key-stage.json raw1d84bda081284bba4c100e1a67b3763d02db8759d099efad406115c681921f74: KEY29-RESULT FAIL/error KEY29_DEADLINE_OR_CANCEL,elapsed90473.82299999999ms.
- keypg-result.json raw571f47f96f374623efb6482a9f477f7e08f52b09ecff6d847a0c257d0855ab35: KEYPG-COMPOSITE/v1 FAIL,innerStatusFAIL,innerResultPersistedtrue,RAW_SIGNED_RECEIPT_BYTES/v1 binds exact inner raw receipt. keyCleanup PASS/state CLOSED; no qualification receipt. Recorded2026-11-05T00:56:24.256Z.

All32 inner hostEvidenceLedger entries match exact raw nonsecret receipt bytes; run/package/plan/engine bindings match, recorded monotonic order nondecreasing. These are content hashes of nonsecret evidence, not TLS/tag/private-input content hashes. No manual HMAC/signature key access; approved runtime persisted/readback contract and observed terminal capture provide the receipt provenance.

## Proved failing operation and timing limits

Stage ledger26 operations inspected using only closed op/role/dispatch/code/signal/complete/duration projections. Initial info/inventory/networks/volumes/image checks return0. One writer helper create0/start-attach0; public writer result PASS/error null,uid10001/gid999,createdtrue,bytesEqualtrue,sourceSize1704,file10001:999,mode416 decimal(0640),size1704,nlink1,regulartrue. Post-start meta/code0/code1 return0. The next host(writer) operation is dispatched,code null,errorCode ETIMEDOUT,signal SIGTERM,completefalse,duration4182.409199999995ms. Reader remains null; no reader create/start in ledger or intent registry.

Fixed host label is Docker inspect --format HOST of the owned writer. HOST is the metadata projection of identity,HostConfig,Mounts,NetworkSettings and Config.Labels; no key contents/Env/argv payloads were exposed. This is a metadata inspect timeout, not an observed Python writer/key-read failure. Successful writer alone does not qualify the full reader/DB binding packet.

Frozen key-stage/runner.mjs qualify initializes total180000ms and initial deadline90000ms, then after image assigns deadline=min(now+55000,total-35000). Per-call end is min(work deadline,total,began+requested), additionally clipped by existing caller/lease parents. The native4.182s timeout therefore reflects a remaining clipped call window, not a new nominal4.182s policy. Ledger does not serialize all absolute parent/end values, so which exact absolute minimum won remains UNPROVEN. Recorded stage command durations sum87299.63179999996ms; clocks and metadata/cleanup overhead are separate, not an invented exact deadline reconstruction.

call() stores the returned row then invokes check() before command-budget/good-result validation. Thus expiry at post-await boundary surfaces KEY29_DEADLINE_OR_CANCEL while preserving native ETIMEDOUT/SIGTERM evidence. Cancellation is not independently evidenced and is not declared the cause. Many successful recorded metadata commands took ~4.3-5.7s, but why Docker/host operations had that latency is UNPROVEN. No raw stderr/private stream, new native probe or timeout/guard increase was used for diagnosis.

## PG/SQL and ownership conclusions

Frozen flow.mjs performs verify/preflight, RO OriginalBefore/budget, then mandatory qualifyKey/validateFlowQualification, before INIT admission/createNetwork/createDb/START review/startDb. The saved failed qualification stops at that boundary. Therefore target INIT/C/T admission/network/main DB/PG start/SQL worker payload1000/139 and actual six reviews were not reached. This is not a statement that no SQL of any kind ran: authorized RO original preservation probes did execute; their internal operations are separate from the unstarted target SQL phases. No fullPG/actual review-HMAC qualification is claimed.

Confirmed native ownership includes writer helper created/started and removed. Existing preflight/RO-original probe cleanup receipts are present in the32-entry ledger. No guessed aggregate create count is substituted for command evidence. Public intent names are KEYPG-RUN,KEYPG-STAGE,KEYPG-writer,ORIGINAL-before,ORIGINAL-after; immutable audit markers are retained and are not residual live resources. There is no reader intent. Inner terminal guards prove active owned resources zero, no pending network create and all requests closed; stage cleanup.terminaltrue closes its create intent. No manual intent deletion occurred.

## Preservation and cleanup

Inner originalPreserved=true,cleanupProved=true,terminalInventory.empty=true. Result OriginalBefore and OriginalAfter canonical snapshots both exist and compare equal. Named receipts recorded before00:53:56.822Z and after00:56:13.802Z. Both budget checks retain the same hostRoots and stay below their conservative limit. Stage source-before/source-after metadata-ACL fingerprints compare equal without exposing them; sourceUnchangedtrue.

Stage cleanup writertrue,readerfalse,fileAbsenttrue,directoryAbsenttrue,sourceUnchangedtrue,terminaltrue. readerfalse means no completed reader cleanup for an uncreated reader, not a demonstrated residual reader. Ledger after timeout shows writer remove0 and terminal inventory/network/volume checks0. Composite cleanup additionally requires signed persisted inner result, original preservation, terminal empty,closed requests/intents; closeAfterTerminal performs full keyState.verify,confirmed copy/directory absence,tagCheck and identity-bound tag unlink before CLOSED. One explicitly authorized named metadata check confirms commitment tag absent and stage directory absent; no file contents/digests or parent/private directory inventory read.

Ordinary prepared private inputs and audit receipts are retained by the existing design; this audit neither inventories nor deletes them. Existing old partial/private state is not silently cleaned. No reusable qualified stage artifact remains. Source/original guards were not bypassed for cleanup.

Prepared expiry00:55:16.882Z was not extended. Terminal occurred later, but recorded failure is stage qualification timeout, not an expiry error. Run admission occurred within the signed900s window; later guards/cleanup followed the unchanged admitted lifecycle. This timestamp observation does not convert Prepare validity into an invented physical TTL or prove host crash resilience.

## Safe next work

Only offline proposal/timing analysis from these pinned receipts: account for pre/post metadata calls under the post-image55s work cap and shorter parent budgets; preserve real closed capture boundaries and classify absent absolute-end telemetry honestly. If a change is proposed, review it before implementation/owner approval. Do not raise caps, skip host checks, replay the Run, recreate stage/tag or run latency diagnostics under this spent grant. New target PG work requires a separately reviewed owner decision.

Reviewer executed no modes/tests/PS/Docker/SQL/cleanup/retries; direct secret/tag/key bytes,content digests,rawACL/privateFacts reads0. Read only public captures, named nonsecret receipts/ledger and bounded source contracts plus one authorized tag/stage absence check. Tool/read errors0; NAV_NOT_FOUND navigation was normal data. Saved only this report.
