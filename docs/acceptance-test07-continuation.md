# Продолжение подготовки тестов и независимого ревью TEST-07

### D-1006: per-AC reconciliation completion

The bounded TEST-07 evidence-reconciliation pass is complete for the full registry: `implementation-traceability.csv`, `acceptance-cases.csv` and `acceptance-automation-status.csv` each contain140 rows/140 unique AC, with zero missing/extra AC between them and140/140 `remaining` fields now carrying an individual D-977–D-1005 evidence decision. No generic pre-implementation message remains.

This is a documentation/evidence milestone, not acceptance completion. No AC was promoted to full PASS: persistent apply/publication, production/runtime topology, external monitoring/backup/LEGAL/network facts, TEST-09 physical/fault/load work, TEST-10 real-browser/device work and explicit requirements conflicts remain where recorded per row. Historical `automation_state`/`executable_ids` were deliberately preserved at103 `assertions_waiting_driver`,20 `partial_http`,17 `text_only`; changing that model requires a separate approved registry migration rather than silent recoloring.

No product, dependency, schema, container, live site or VPS change was made by D-976–D-1006, and no regression suite was rerun for the reconciliation. Existing named-suite evidence is referenced without being counted again. TEST-08/stage9 remains closed. The next no-bloat step is a bounded read-only gap register grouping the already recorded remaining work into owner decisions/requirements conflicts, launch-external gates, TEST-09 and TEST-10; it must not create new features or convert missing evidence into PASS.

### D-1005: DEV-13 exact13 evidence mapping

`AC-030` / `AT-030`, `AC-031` / `AT-031` and `AC-DTL-008` / `AT-108` have executed local synthetic partial evidence for the minimal form: exact required/optional fields, separate consent flag, closed unknown/duplicate keys and length/Unicode boundaries; +7/8 Russian-number normalization accepts approved separators and rejects foreign/additional/invalid forms without claiming ownership verification. Real PII, final LEGAL text/version, persistent enablement and production observation remain.

`AC-032` / `AT-032`, `AC-DTL-009` / `AT-109` and `AC-DTL-010` / `AT-110` have executed local partial PostgreSQL evidence: server-issued bounded intent, concurrent insert-winner, exact replay/lost-response convergence, one request+consent result and changed phone/text/consent-version conflicts without overwrite. Notification attempts belong only to the insert winner and fail independently after commit. Real network, Metrika goal behavior and live LEGAL consent remain gated.

`AC-DTL-011` / `AT-111` is deferred with an explicit requirements conflict: the older oracle requires a 30-minute issuance window and24-hour receipt semantics, while approved minimal D-859 deliberately did not restore the old receipt/cache/24-hour form contract. The current bounded signed intent/idempotency path must not be silently described as that legacy lifecycle; a future requirements decision is needed before promotion.

`AC-DTL-012` / `AT-112` has executed local partial negative evidence: public GET creates no request/result row, dynamic form responses are private/no-store and bypass304, exact pre-CSRF body limits and bounded write-cap/rate contracts fail closed without deleting existing requests. Full scanner/overflow execution with production Nginx and live token/CSRF cadence remains.

`AC-OPS-010` / `AT-310` has executed local supporting partial evidence for request write-cap races, ingress limits and bounded deletion-ledger caps/reconciliation; refusal is observable and existing requests are preserved. Physical receipt/throttle/temporary-space exhaustion across the production filesystem and cross-subsystem media/backup preservation remain TEST-09 work.

`AC-PRO-001` / `AT-401` has executed local partial no-JS/server evidence: when the synthetic gate is enabled the form has server-issued intent+CSRF, explicit POST and no GET-created request/receipt row; DEV-25 reserve output has no working form/intent/CSRF. Real enabled LEGAL/live public form remains off.

`AC-PRO-002` / `AT-402` has executed local partial cache-safety evidence: dynamic form GET is always private/no-store with Vary Cookie and bypasses shared ETag/304, so changed cookie/CSRF/consent cannot receive a stale304. The older positive conditional-304 matrix is not implemented for forms; production proxy behavior remains.

`AC-PRO-003` / `AT-403` has executed local partial evidence: a committed request whose response is lost is recognized by the same intent without a second row/notification winner, and changed context conflicts; fields, intent and result IDs are excluded from URL/analytics. Real Metrika/network execution remains.

`AC-PRO-004` / `AT-404` has executed local partial server evidence for genuine CSRF, private/no-store safe errors, exact intent replay and no duplicate after explicit retry. Preservation of the user's permissible input across an actual old-tab CSRF rotation and complete real-browser flow remains TEST-10/manual. Full PASS0; automation states/executable IDs remain unchanged, real intake stays default-off and no legacy receipt/cache/CRM/outbox/worker layer is restored.

### D-1004: DEV-05 exact12 evidence mapping

`AC-017` / `AT-017` has executed local partial evidence across DEV-07/REF-4: stale current/base and concurrent saves fail atomically, preserve the entered value for comparison, create no revision/audit side effect and require a fresh explicit Save. Complete production browser/session interruption and all migrated page types remain.

`AC-018` / `AT-018` has executed local partial evidence: an employee current-source Save changes only permitted fields, creates one immutable automatic revision, preserves an independent owner draft and protected fields, and rolls back on audit/media faults. Persistent public observation and full real-content role matrix remain.

`AC-019` / `AT-019` has executed local partial evidence for the exact ten ordinary revisions plus every Stable, Stable-aware pruning, manual revisions inside the ordinary limit, protected current/draft/stage/media bases and real concurrency/rollback. Production accumulated-history/resource behavior remains.

`AC-020` / `AT-020` has executed local partial evidence: only the owner may set Stable after an exact viewed stamp; demotion requires current password plus fresh composition and locked password-hash recheck, preserves the original date, does not publish or inherit the label and never removes current. Full production operator/browser flow remains.

`AC-021` / `AT-021` has executed local partial HTTP/UI evidence: an assigned employee can view ordinary/manual/Stable history and labels for the assigned Page, while visitor, foreign employee, draft/private source and guessed preview/media paths are denied with private/no-store responses. TEST-10 and persistent production data remain.

`AC-022` / `AT-022` and `AC-023` / `AT-023` have executed local partial compare/restore evidence: compare/prepare does not change current; direct restore and legacy replay apply only compatible permitted content in one transaction, preserving URL/tree/publication/rights/Stable/shared blocks and refusing missing media, lost rights or incompatible snapshots without partial mutation. Complete production open-tab/manual-copy behavior remains.

`AC-063` / `AT-063` and `AC-MAN-001` / `AT-701` have executed local partial evidence: owner manual snapshot copies the explicitly saved current revision rather than owner draft or unsaved input, records independent metadata/server authorship/time, does not publish, and never inherits Stable. Concurrent double submit converges to one row/audit. Persistent real editor observation remains.

`AC-MAN-002` / `AT-702` has executed local partial evidence: ordinary revision delete protects current, Stable, draft/stage/pin/media bases; Stable-vs-delete races, stale composition and audit rollback are closed, and physical/shared files remain. Whole-page deletion remains the separate DEV-29 command; production accumulated consumers remain.

`AC-MAN-003` / `AT-703` has executed local partial evidence for owner/employee/GET/CSRF boundaries, exact repeat/concurrency behavior, server-time ordering and the eleventh ordinary revision under Stable/current protection. Full production browser and long-running history remain.

`AC-DTL-019` / `AT-119` has executed local partial atomicity evidence across version/media Save, draft publish and direct restore: media preflight is revalidated under locks; audit/usage/revision/current mutations roll back together, and incompatible old snapshots are neither rewritten nor partially applied. Physical production storage failures and the complete TEST-09 matrix remain. Full PASS0; automation states/executable IDs remain unchanged, and the completed simple REF-4 path is used instead of restoring the legacy universal receipt workflow.

### D-1003: DEV-26 exact10 evidence mapping

`AC-HTML-001` / `AT-201` has local supporting partial evidence from DEV-12 stable-ID/frozen-home rules and DEV-25 immutable current/previous sets: deleting a source does not rewrite the prepared home, while its own live route state is independently known. No operational Nginx path serves the frozen home/404/blank200 matrix during an outage, and no DB restore is invoked.

`AC-HTML-002` / `AT-202` has local supporting partial evidence for stable Page identities, URL-reuse protection, exact route/query descriptors and old-validator invalidation. The old reserve allowance is not exercised against a newly created same-URL object through actual fallback delivery.

`AC-HTML-003` / `AT-203` and `AC-HTML-004` / `AT-204` remain deferred/assertion-only for their external prohibition protocol. Simple local delete/URL commands prove atomic stale/race/rollback behavior, and disconnected DEV-26 journal primitives exist, but there is no runtime external revoke/finalize authority, delayed worker or response-admission point to interrupt. The stopped heavy TRUST path is not substituted.

`AC-HTML-007` / `AT-207` has local partial build/projection evidence: DEV-25 creates an exact closed response/resource set without admin/history/private tokens, while DEV-26 IMP-001/002 validate bounded target/status/header projection and immutable copied releases. Actual Nginx GET/HEAD/304/POST/hidden/deleted/new-page behavior is absent; IMP-003 failed and was rolled back.

`AC-HTML-009` / `AT-209` and `AC-PRO-009` / `AT-409` remain deferred/assertion-only: selector/journal copy/reopen primitives are disconnected, but no signed external freshness head, simultaneous HTML/registry/local-DB rollback, restored-DB revoke reconciliation or controller restart exists. Static200 is not claimed as engine recovery.

`AC-HTML-010` / `AT-210` has local partial evidence: D-300 frozen home composition is not automatically hidden by source deletion, DEV-25 has no daytime partial rebuild mechanism, and unsafe editor markup/path input cannot become reserve execution. Actual emergency serving after deletion remains absent.

`AC-HTML-011` / `AT-211` has local supporting partial evidence from direct chain-free REF-5 URL redirects, DEV-25 exact route metadata and DEV-26 closed projection records. The required outage result `/a` current301 plus `/b` no-file503, hide/delete/reuse delivery and immediate redirect updates are not connected to Nginx.

`AC-HTML-012` / `AT-212` remains deferred/assertion-only: the simplified local URL command is atomic and repeat-safe, but no external prohibition/finalization/admission protocol or lagging delivery worker exists to interrupt at the specified boundaries. Full PASS0; automation states/executable IDs remain unchanged. D-923 no-bloat defer is preserved: no helper, njs, controller, TRUST service, state machine or operational Nginx change is restored.

### D-1002: DEV-11 exact10 evidence mapping

`AC-010` / `AT-010` and `AC-DTL-003` / `AT-103` have executed local partial evidence across typed Page snapshots, simple creation and public metadata: title/H1/description boundaries are closed, empty description omits the meta tag, literal values are escaped, and later name/body changes do not become SEO authority. Full old-value migration inventory, persistent apply and the complete owner accept/reject suggestion flow remain.

`AC-011` / `AT-011` has executed local partial evidence for explicit preview image → main image → none, with exact CURRENT_PAGE usage, READY variant, physical-byte and recapture checks; random embedded images are not selected. Noindex emits the approved header and omits canonical/og:url, while publication is separate. The confirmed common fallback image, persistent legacy settings and final owner UI remain.

`AC-061` / `AT-061` is a locally executed aggregate partial: canonical/Open Graph/X-Robots, coherent bounded sitemap, fixed robots profiles, gallery special routes, safe optional AutoRepair serialization and alt/media authorization are covered. Full launch data, production profile, enabled real AutoRepair facts, emergency SEO behavior and all special/legacy URLs remain.

`AC-SEO-001` / `AT-601` has executed local partial HTTP/projection evidence: trusted configured origin, ordinary self-canonical, exact CONTENT-WASH peer mapping, gallery canonical matrix, foreign Host/query/fragment refusal and both required wash URLs remaining200 are covered. The historical114-page canonical inventory and persistent migrated publication remain.

`AC-SEO-002` / `AT-602` has executed local partial sitemap evidence: published indexable canonical representatives are captured coherently from bounded Page/PRIMARY/ALIAS/state/current-revision sets; hidden/noindex/redirect/unknown aliases are excluded, change races fail503 and cap overflow does not truncate XML. Production data, final external crawl and launch scheduling/serving remain.

`AC-SEO-003` / `AT-603` has executed local partial evidence for exact deny-all and production robots bytes, allowed gallery query rules, no internal inventory, trusted-origin independence, HEAD and method boundaries, plus hidden/noindex HTTP headers. Actual production selection, proxy/static exposure and an external crawler check remain.

`AC-SEO-004` / `AT-604` has executed local partial evidence across DEV-10 root, direct `?page=2`, modal and17 album routes plus the closed canonical matrix: page2 is not redirected and album pages do not self-authorize the root incorrectly. Persistent gallery publication, confirmed page1 chain and complete launch crawl remain.

`AC-SEO-005` / `AT-605` has executed local negative/synthetic partial evidence: AutoRepair is absent by default, appears only for a coherent confirmed visible profile, uses a deterministic script-boundary-safe JSON-LD serializer, and editor/media rules protect schema/alt/viewport inputs. The real company profile intentionally remains disabled pending confirmed contacts; actual214 SHA and production page observation remain separate gates.

`AC-SEO-006` / `AT-606` has executed local partial construction evidence from DEV-11 metadata rules and DEV-25 exact reserve responses: noindex/canonical metadata is frozen coherently and invalid data fails closed. No running DEV-26 controller serves redirect/current/503 decisions during a real Django/DB failure, so the complete emergency scenario remains deferred. Full PASS0; automation states/executable IDs remain unchanged, and no AutoRepair/contact/external runtime is enabled.

### D-1001: DEV-29 exact9 evidence mapping

`AC-002` / `AT-002` has executed local partial public HTTP evidence for unknown, deleted and hidden page states, including fail-closed damaged routes/content and navigation suppression. Production cache/intermediary behavior, conditional-request leakage across every state and the emergency delivery path remain.

`AC-003` / `AT-003` has executed local partial evidence: publishing/hiding changes only the selected flag and audit; a published child below hidden/deep-hidden ancestors keeps its URL, publication and parent, remains readable and is promoted dynamically in navigation. Persistent real-tree apply/publication remains.

`AC-004` / `AT-004` has executed local partial evidence across simple create/reorder/move/rename and public navigation: new hidden aggregate position, explicit sibling order, hidden-ancestor promotion, stable URL and no name-based resort are covered with stale/ABA/concurrency/rollback guards. Full migrated tree and final admin/public visual order remain.

`AC-005` / `AT-005` has executed local partial deletion evidence: an existing or late-created child blocks leaf deletion without subtree mutation; after an exact fresh composition confirmation only the selected leaf is removed. Production data and the complete operator flow remain.

`AC-006` / `AT-006` and `AC-DTL-002` / `AT-102` have executed local partial evidence for deterministic proposed/exact local paths, occupied page/route/system conflicts, hidden atomic creation and rename/move preserving the stored URL. Legacy exact paths are package-tested separately; persistent migration and the full advertising/old-path inventory remain.

`AC-007` / `AT-007` has executed local partial normal-runtime evidence: repeated explicit URL changes update PRIMARY and create direct old-to-current redirects without chains; occupied/legacy targets, stale/ABA, races and rollback fail closed. Emergency HTML behavior, redirect handling during DB failure, protected advertising inventory and revoked-ID/head integration remain outside the completed simple command.

`AC-024` / `AT-024` has executed local partial evidence: owner/session/CSRF/current-password and exact name/PRIMARY/composition confirmation protect deletion; Page/routes/full history including Stable are removed atomically while subtree, assets/files, shared/retained references and append-only ledgers remain. Password-hash race, Page/Route ABA, late child, rollback, concurrency and lost response are covered. Production execution and external deletion/tombstone reconciliation remain.

`AC-PRO-010` / `AT-410` has executed local partial atomicity/result evidence from the simple delete command: audit/DB faults roll back, lost response/retry converges on the actual gone result, late child/stale composition blocks completion and a new Page at the former URL is not captured. No external prohibition/head receipt or delayed worker exists after the approved simplification, so those protocol branches remain unexecuted. Full PASS0; automation states/executable IDs remain unchanged and the stopped heavy TRUST architecture is not restored.

### D-1000: DEV-07 exact8 evidence mapping

`AC-013` / `AT-013` has broad executed local partial evidence: accepted formatting and complex tables survive Check, Save, history and selected restore; executable templates/scripts are rejected before publication. Header/Footer have independent owner-only current/draft/history/restore/cancel flows and management routes rather than standalone public page identities. Persistent real-content publication, complete public-page composition and TEST-10 remain.

`AC-054` / `AT-054` has executed local partial security evidence across the closed HTML parser/normalizer, active markup/template/style/unsafe-URL rejection, no-network link handling, protected media boundaries, self-CSP and response-header checks. Production `check --deploy`, the final policy after any approved external resources and complete upload/runtime inspection remain.

`AC-DTL-004` / `AT-104` has executed local partial evidence for allowed headings/marks/tables, source-byte/codepoint/node/depth boundaries, visible normalization before Save and two complex table corpora surviving history/restore without structural loss. Full imported-content corpus, production resource profile and real-browser matrix remain.

`AC-DTL-006` / `AT-106` has executed local partial evidence: internal, anchor and http/https links are normalized with safe attributes; javascript/data/file, controls, encoded bypasses, private/outside-root contexts and network fetching are refused. Full applied employee flow across migrated pages and browser/device acceptance remain.

`AC-DTL-015` / `AT-115` has executed local partial evidence: page history/restore does not roll back the independently current Header/Footer; current and historical shared revisions are separate, and restoring a literal old phone changes only the selected Header fragment while Footer stays current. Persistent real-site content and complete operator comparison on launch data remain.

`AC-DTL-016` / `AT-116` has executed local partial evidence for stale-base/concurrent shared conflicts, owner input preservation, draft isolation and public ETag invalidation after Header/Footer/navigation changes; a draft is never public. Production intermediary caching and the full public Page body remain.

`AC-DTL-017` / `AT-117` has executed local partial quota/lifecycle evidence: actual inventory and warnings are measured, current/history/pins/READY media survive refusal and cleanup boundaries, 10000 historical rows are not silently pruned and no unapproved keep10 rule is applied. The exact local256MiB profile is not a production-universal budget; physical production exhaustion, accumulated terminal-job debt and operator recovery remain TEST-09/launch work.

`AC-PRO-005` / `AT-405` has executed local partial evidence: an actual old literal phone is shown/restored as content, Footer and unrelated state remain unchanged, no placeholder registry is introduced, and template/corrupt trusted inputs fail closed rather than partially applying. Full migrated real Header comparison and production execution remain. Full PASS0; automation states/executable IDs remain unchanged. D-999 is resolved by exact-path inventory; no wildcard retry, product change or new feature was used.

### D-998: DEV-27 exact7 evidence mapping

`AC-046` / `AT-046` remains assertion-only/deferred for DEV-27: DEV-25 provides a valid local reserve set and DEV-26 IMP-001/002 retain disconnected projection/delivery preparation, but no operational Nginx/controller path serves it when Django/DB fails, verifies the switch notification or selects the contact 503 when no set exists. The failed IMP-003 experiment was rolled back and is not product evidence.

`AC-049` / `AT-049` is deferred with an explicit requirements conflict. The older oracle requires two application/DB successes before return and one notification; later approved D-896 scope chose per-request non-sticky fallback where the next normal upstream response immediately has priority, specifically without a state machine. D-923 then deferred DEV-26/27. Neither interpretation is silently passed or implemented.

`AC-OPS-003` / `AT-303`, `AC-OPS-005` / `AT-305` and `AC-PRO-006` / `AT-406` remain assertion-only/deferred: closed local readiness proves a single app+DB check, but there is no probe-ID/retry/streak state, isolated local/external stream, independently confirmed switch/return or notification delivery.

`AC-PRO-007` / `AT-407` has design-only arithmetic evidence for the PR-03 total of576 daily readiness HTTP/SELECT operations across two independent five-minute streams. No external service, real I/O cadence or state placement exists, so arithmetic is not execution evidence.

`AC-PRO-008` / `AT-408` remains assertion-only/deferred: there is no running controller to stop, supervise or distinguish from stale heartbeat/static200, and no restart path to inspect for data rollback. Full PASS0; automation states/executable IDs remain unchanged. D-923/no-bloat is preserved: no helper, state machine, scheduler, monitor, Nginx or notification subsystem is added.

### D-997: DEV-25 exact6 evidence mapping

`AC-047` / `AT-047` has executed local partial evidence: the owner-triggered synchronous build captures only published public dependencies, excludes history/admin/requests, rejects A/B source drift before activation and atomically keeps validated current/previous generations with exact retained media. A night-only schedule, proof that daytime changes never trigger a build, production durability and operational execution remain; DEV-25 intentionally contains no scheduler or worker.

`AC-048` / `AT-048` and `AC-HTML-008` / `AT-208` have executed local partial rendering/security evidence: reserve rendering is anonymous and unconditional, emits no working form, intent, CSRF token, private/admin/history data or external embedded channel, and the combined exact-set test preserves inert external navigation. Actual fallback POST behavior without/with JS, an already-open tab, a lost POST response, browser-persistence inspection and proof of no Telegram/email/other receiver require the not-activated DEV-26 delivery path and remain open.

`AC-HTML-005` / `AT-205` has executed local partial evidence: bounded public source descriptors/stamps cover page, shared, route, price and resource inputs; a second capture under the content lock rejects drift, including a real PostgreSQL mutation race, so an inconsistent generation is not activated. The complete simultaneous page/shared/price/unpublish matrix in a production-like build remains.

`AC-HTML-006` / `AT-206` has executed local partial evidence across immutable staging/generation storage, retained-reference transactions, pre/post-replace faults, child-process crash/reopen, cleanup refusal on ambiguity and current/previous preservation. Physical disk exhaustion at every named preparation/validation/retention/activation/cleanup phase and proving that a served previous set cannot bypass a revoked allowance remain; DEV-26 delivery is absent.

`AC-PRO-012` / `AT-412` has executed local partial evidence by combining DEV-12 stable-ID/frozen-home behavior with DEV-25 exact route/status generation and disabled reserve form. It does not demonstrate a real Django/DB outage, Nginx selection of the nightly home copy, the deleted route returning 404 through that fallback, or the full TEST-10 path. The frozen DEV25-IMP-007 evidence is exact44/44; final bounded remediation brought DEV-25 to52/52 and independent review `APPROVED`. Full PASS0; automation states/executable IDs remain unchanged, and no scheduler/controller/Nginx/live feature is added.

### D-996: DEV-14 exact5 evidence mapping

`AC-033` / `AT-033` has executed local partial evidence for the later approved D-596 model: owner and employee read-only list/detail, anonymous denial before data, escaped private/no-store responses and bounded pagination/query. Its older assigned-only/assignee/foreign-card oracle conflicts with D-596 employee access to all requests and cannot be promoted without requirements reconciliation. Telegram body safety is covered only by synthetic notification boundaries, not live delivery.

`AC-034` / `AT-034` and `AC-DTL-013` / `AT-113` are assertion-only/deferred: statuses, transition history, reopen confirmation, optimistic status conflicts and assignee changes were explicitly removed from the minimal no-CRM scope.

`AC-035` / `AT-035` is assertion-only/deferred: notes/contact corrections/history were explicitly removed; immutable original request and no-PII audit remain local supporting evidence but do not implement notes.

`AC-036` / `AT-036` is assertion-only/requirements-conflict: employee session disable/re-enable behavior is implemented, but reassignment of open requests and historical closed assignee require the removed assignment/status/history model. D-596 all-employee read-only access supersedes assigned-request visibility. Full PASS0; states/IDs unchanged and no CRM/status/assignee/notes/history subsystem is restored.

### D-995: DEV-06 exact5 evidence mapping

`AC-026` / `AT-026` has executed local partial evidence: real JPEG/PNG/WebP and exact1MB uploads, bytes/pixel/format/MIME/active-payload rejection, owner/CSRF/body-cap boundaries, private source, nosniff contextual output and worker codec/resource tests. Network-level worker-down/unknown-receipt, production storage/runtime and current vendor-risk release decision remain.

`AC-027` / `AT-027` has executed local partial evidence: stable PageMediaHome survives Page rename, direct/subfolder search is boundary-safe, prefix neighbor/traversal/symlink/hardlink escapes are rejected, and picker authorization is contextual. Full applied editor/history navigation and production filesystem traversal matrix remain.

`AC-028` / `AT-028` has executed local partial evidence across editor/media/version tests: owner changes one typed slot, previous Stable/draft/other usage retains immutable bytes, employee media keys are denied, cleanup cannot remove referenced assets, and contextual recapture fails closed on drift. Complete two-article+Stable+active HTML-set observation after persistent publication remains.

`AC-029` / `AT-029` has executed local partial evidence: six usage kinds, owner confirmation/generation/signature, late-reference race, physical unlink failure with honest pending+retry, concurrent attach/delete, actual byte counts and HTML-reserve generation retention. Production storage faults, all active generations/backup consumers and final cleanup operations remain.

`AC-DTL-007` / `AT-107` has executed local partial evidence: employee/visitor cannot inject or change media keys/src/alt/alignment; owner typed metadata replacement is allowed while old Stable/other-reference bytes remain. Whole214-original and all published HTML consumer hashes after real apply remain. Full PASS0; states/IDs unchanged and no new media subsystem added.

### D-994: DEV-03 exact5 evidence mapping

`AC-014` / `AT-014` has executed local partial evidence: owner creates employee and sets/resets password, employee direct self-reset/manage requests are denied, old sessions die after reset/disable, enable does not revive them, password input is hidden and secrets are absent from argv/audit/output. Production HTTPS/cookie profile and complete real-browser owner workflow remain.

`AC-015` / `AT-015` has executed local partial server evidence for idle30m and absolute12h boundaries, passive status not extending idle, malformed/old-generation sessions closing, and revoked rights checked on the next request. Preservation of unsaved editor input solely in an open real browser tab across expiry/different-user login and explicit resave remains manual/editor-browser acceptance.

`AC-016` / `AT-016` has executed local partial evidence: page-scoped grants, default price-off, immediate revoke, denial of home/protected/system types and forged direct fields; later editor suites enforce typed allowed areas/price boundaries. Full assigned text/link/price HTTP flow against persistently applied real pages remains.

`AC-DTL-001` / `AT-101` has local partial evidence across stale owner generation, revoked grants and editor save/base guards: outdated authorization or basis is refused without hidden partial mutation. The full two-open-editor compare/manual-transfer path remains.

`AC-DTL-018` / `AT-118` has local partial server/UI-contract evidence for session/conflict refusal and no server-side privilege carry-over; the exact unsaved-input-in-memory/no-localStorage-or-URL behavior across expiry/conflict/user switch still needs real browser/manual acceptance. First lookup named two nonexistent guessed test files; exact tracked tests were located without identical retry. Full PASS0; states/IDs unchanged.

### D-993: DEV-20 exact4 evidence mapping

`AC-041` / `AT-041` has executed local partial evidence: known scanner paths are rejected before body/session/auth/SQL with connection attempts0/SQL0, no cookies, bounded ten-key process counters, expected404 log suppression and compatibility with115 MAP/316 MED. Native scan windows prove useful requests still work and unexpected outcomes remain observable. Full TECH-06 peak, global history/Telegram and production WSGI logging remain.

`AC-052` / `AT-052` has executed local partial resource evidence from separate scan and mixed native runs: actual HTTP statuses, useful editor requests, container CPU/RAM/OOM/max-event observations and retained-domain checks. It is not the complete pre-agreed PERF-NORMAL/SCAN/MIXED/FAILURE profile, five-minute peak or VPS capacity test and gives no DDoS guarantee.

`AC-060` / `AT-060` has executed local partial evidence for5 failures per real IP, second-IP independence, success clearing only its source, rolling10-minute/15-minute limits, forwarded-header trust boundary, bounded key capacity and concurrent failure correctness; Nginx20/50rps and active8 are inspected/exercised. Background-job duplicate limits, all expensive-operation quotas and production proxy/shared-address topology remain.

`AC-OPS-009` / `AT-309` has executed local partial native evidence: N03/N04/N07 scanner/mixed windows, two real source IPs, SQL0, bounded process keys and measured useful-request/resources. Full10/50/100rps×5min, many-source zone churn and production execution remain. Full PASS0; states/IDs unchanged and no extra rate-limit platform is added.

### D-992: DEV-19 exact4 evidence mapping

`AC-062` / `AT-062`, `AC-MAN-004` / `AT-704`, `AC-MAN-005` / `AT-705` and `AC-MAN-006` / `AT-706` are all assertion-only/deferred under the approved MVP simplification. They require owner-confirmed category-bound delete, new-event/other-category/protected-audit preservation, DB/file partial-operation reconciliation, physical1GiB behavior, retry identity, read cursor/badge and independent incident recovery.

The minimal owner read-only AuditEvent screen, strict older-than30-day DB cleanup and Docker technical rotation do not implement or substitute manual category deletion. No application bindings or fault execution exist for these four ACs. Full PASS0; states/IDs unchanged and no category-delete/reconciliation/read-state/incident subsystem is added.

### D-991: DEV-17 exact4 evidence mapping

`AC-038` / `AT-038` has executed local partial evidence: the exact nine approved categories, one-insert stable UUID, typed references, safe formatter rejecting raw/sensitive payloads, append-only model guards and owner-only bounded filtered read are tested. Per-category rotated files, storage-unavailable incomplete-vs-zero indication and full nine-source operational fixture remain.

`AC-039` / `AT-039` remains assertion-only/deferred by owner no-bloat decision D-925: badge999+, grouped exact count, read cursor and concurrent mark-read boundary are not implemented in the minimal read-only audit screen.

`AC-059` / `AT-059` has executed local partial evidence for aware server UTC, Europe/Moscow UI, stable sequence/order and manual dates not replacing server facts. Midnight-boundary profile and actual UTC/zoned audit export remain.

`AC-OPS-007` / `AT-307` has executed local partial evidence for exact nine categories, stable unique event IDs, duplicate refusal and sensitive-value suppression in event/process/admin output. Full code-by-category fixture and Telegram/diagnostic transport inspection remain. Full PASS0; states/IDs unchanged, no badges/read-state/files/Telegram/full category UX added.

### D-990: DEV-08 exact4 evidence mapping

`AC-009` / `AT-009` has broad local partial server-render evidence across safe public read/HTTP/navigation/shared blocks, service catalog/details, exact price layouts, DEV-12 home and DEV-10 gallery. It does not prove the full accepted desktop/tablet/phone visual composition for every type, remaining deferred assets/infographics or real content after persistent publication.

`AC-050` / `AT-050` has executed local partial HTTP evidence: composite ETag/no-cache/conditional GET+HEAD, page/shared Header/Footer/navigation changes invalidate validators, price/home source changes participate in the public stamp, public responses avoid session cookies, and private admin/request responses are no-store. Production intermediary/shared-cache behavior and every dynamic form context remain.

`AC-056` / `AT-056` and `AC-OPS-011` / `AT-311` remain manual-device blocked. No dated real matrix for eight browser families×current+two versions, Safari on real iPhone, MIUI and Samsung Internet has been executed. Django HTTP tests and Playwright are explicitly not substituted for device/browser acceptance. First lookup used nonexistent `test_public_nav.py`; exact `test_public_navigation.py` was located without identical retry. Full PASS0; states/IDs unchanged.

### D-989: DEV-24 exact3 evidence mapping

`AC-045` / `AT-045` has executed local partial evidence: closed readiness performs real app-process+target PostgreSQL `SELECT 1`, actual stopped DB returns bounded nonzero and restart returns success, with no writes or secret/raw-error output. Five-minute external scheduling, independent probe IDs, F/S streak state, two-failure/two-success notifications and static-reserve bypass remain assertion-only/unexecuted.

`AC-OPS-001` / `AT-301` has local negative evidence: readiness is a management command with no URL/Nginx location/port; `/readiness/` returns ordinary404, so an unauthenticated scan cannot invoke its DB SELECT or receive diagnostics. This is not the future authenticated external readiness endpoint; auth/forwarded-IP and daily external probe behavior remain.

`AC-OPS-002` / `AT-302` has executed local partial evidence: target DB stop gives constant failure in3.455s, transaction-local statement timeout2s/connect5s/Docker8s are bounded, recovery succeeds and persistent counts stay unchanged. Wrong-but-successful other DB, forced SQL over-budget and concurrent normal-user timeout isolation remain unexecuted. Full PASS0; states/IDs unchanged, no endpoint/observer/state machine added.

### D-988: DEV-16 exact3 evidence mapping

`AC-037` / `AT-037` has executed local partial evidence: owner-only POST+CSRF signed confirmation, employee/anonymous/GET refusal, idempotent single delete, bounded no-PII ledger, fault rollback/retry, concurrent convergence and restore reconciliation. Full PASS is additionally blocked by oracle drift: the older AC still requires repeated password, while later owner decision D-595 explicitly replaced it with ordinary signed confirmation without password. The implementation follows D-595; the acceptance oracle must be reconciled before status promotion. Real old-backup restore and LEGAL/live remain.

`AC-DTL-014` / `AT-114` has local partial deletion/tombstone evidence: repeated delete converges, restored row is removed by ledger reconciliation and request body is absent from the ledger. Its note/contact-correction branch is not implemented because the approved minimal DEV-13 scope removed notes/history/CRM; it cannot be claimed PASS without a requirements decision.

`AC-DTL-020` / `AT-120` has local partial authorization/atomicity evidence: direct non-POST and wrong role fail, owner confirmation is bounded, ledger/DB fault does not announce final success, stale/missing trusted ledger root fails closed. Full legal-consent/live production flow and external restore execution remain. Full PASS0; states/IDs unchanged.

### D-987: DEV-12 exact3 evidence mapping

`AC-012` / `AT-012` has executed local partial evidence: `test_dynamic_projection_changes_only_price_amount_and_visibility`, hidden-source and missing-source frozen-fallback tests, exact owner bind/unbind digest, delete guard and fixed public home rendering. Stable IDs prevent a new object at the same URL from inheriting a deleted source. Full AC remains open for persistent apply/publication and the complete normal→night-reserve route with deleted target404 in a launch-like environment.

`AC-DTL-005` / `AT-105` has executed local partial evidence from closed price policy/schema/source tests: exact Decimal without float, zero/text/empty/`from`, matrices/classes/axes, row identity, owner-only home profile and amount-only projection. Full role/HTTP price-edit path against applied published content and end-to-end main update remain.

`AC-PRO-011` / `AT-411` has executed local partial evidence: visible source requires exact visible fallback, hidden source requires explicitly saved hidden fallback, unbind removes dependency without URL/name capture, corrupt/racing home fails closed, retained asset/profile identity is protected. Actual published delete with all media/HTML consumers and launch-like observation remains. First test-file lookup used one nonexistent guessed filename; exact tracked home tests were located without identical retry. Full PASS0; states/IDs unchanged.

### D-986: DEV-30 exact2 evidence mapping

`AC-057` / `AT-057` остаётся deferred/text-only. D-291–293 фиксируют будущие visits/sources/phone-click/accepted-request goals, no PII/ID, Webvisor off and analytics failure nonblocking, но actual counter ownership/config/goals/legal fake sink and execution отсутствуют. COOKIE-Q001 intentionally keeps first launch free of Metrika/Yandex/YouTube; negative absence evidence не является analytics PASS.

`AC-OPS-012` / `AT-312` имеет local partial negative evidence: public/home tests require CSP `script-src 'self'`, no iframe/Yandex/YouTube, no public cookies/storage; HTML reserve rejects external fetch tags and preserves fixed public CSP. Full accepted/rejected consent/network/storage matrix and future optional-widget configuration remain deferred because no optional external runtime is enabled. Consent manager or analytics code is not added preemptively. Full PASS0; states/IDs unchanged.

### D-985: DEV-21 exact2 evidence mapping

`AC-042` / `AT-042` и `AC-OPS-006` / `AT-306` имеют только reviewed `acceptance-fallback-contracts.md` assertions для incident lifecycle:1000 repeats одного stable incident без шторма, второй critical другого component/code независимо, restart/read без ложного recovery, один verified recovery, lost ACK/delivery failure bounded and nonrecursive. Реальных incident controller/cycle/delivery bindings и исполнения нет.

Минимальные independent email/Telegram attempts DEV-13 относятся к сохранённой заявке и не являются доказательством этих technical-incident AC. Отказ от отдельной тяжёлой DEV-21 queue не превращает их в PASS: они явно остаются deferred/assertion-only до отдельного operational scope. Первое чтение предположило несуществующий DEV-13 results filename; tracked plan/decisions/tests были найдены по реестру файлов без одинакового повтора. Full PASS0; states/IDs unchanged.

### D-984: DEV-18 exact2 evidence mapping

`AC-040` / `AT-040` имеет executed local partial evidence D-643/D-645: actual Docker inspect and >35MiB synthetic probe prove `json-file` rotation `10m×3` for four runtime services; strict transactional `AuditEvent occurred_at < now−30days` cleanup preserves boundary/newer and rolls back on DB failure. Это не общий full AC: unified managed1GiB folder including temporary files, noise-first eviction, backup/external exclusion under pressure, daily target scheduler and operational observation отсутствуют.

`AC-OPS-008` / `AT-308` имеет reviewed assertion contract only for80/95/75%, rotation peak, concurrent write, no-space and nonrecursive error reporting. Actual OS folder/controller bindings, physical peak measurement and fault execution отсутствуют. Full PASS0; states/IDs unchanged, scheduler/collector/log platform не добавлены.

### D-983: DEV-02 exact2 evidence mapping

`AC-053` / `AT-053` имеет executed local partial evidence D-316/317: FOUNDATION-001–011=11/11, strict Host/forwarded-header boundary, DEBUG=False/security settings, live Nginx→app fault behavior, CSRF middleware and deployment audit exit0 with only expected local-HTTP HSTS warning. Это не production-profile PASS: настоящий домен/TLS, production cookies/HSTS/proxy, полные role mutation/GET branches и release `check --deploy` остаются.

`AC-055` / `AT-055` имеет executed local partial evidence: DB без host port, separated bootstrap/migrator/runtime roles, runtime DDL denial, nonroot/readonly/cap-drop isolation, secret mounts/scan, immutable runtime locks/provenance/SBOM and reviewed base-image remediation. Full AC остаётся открыт для production exposure/config/source scan, staging-first release rehearsal and current vulnerability decision; vendor registry intentionally retains154 open+2 undetermined image/advisory matches. Full PASS0; historical states/IDs unchanged.

### D-982: LEGAL-01 and MONITOR-01 exact2 evidence mapping

`AC-058` / `AT-058` имеет local partial factual evidence: `docs/legal-form-drafts.md` фиксирует реквизиты ООО «Эстакада», состав/цель/сроки данных, выключенный intake и проекты отдельного согласия/политики; COOKIE-Q001 подтверждает первый запуск без Метрики/Яндекс/YouTube и без преждевременного consent manager. Full AC blocked до LEGAL-Q007–010, проверки FirstVDS/RKN/SMTP/external backup, профильного legal review, постоянных URL и фактической launch-конфигурации.

`AC-OPS-004` / `AT-304` имеет только design/assertion evidence: PR-03 разделяет local/external five-minute readiness streams и честно считает288+288=576 HTTP/SELECT в сутки; `acceptance-fallback-contracts.md` требует real I/O/virtual clock и запрещает подменять его арифметикой. Full AC blocked: внешний monitoring service/access/state placement/delivery не выбраны, реальные576 probes и fault-stand не исполнялись. Ни один сценарий не повышен до PASS; states/IDs не меняются.

### D-981: DEV-23 single-AC evidence mapping

`AC-044` / `AT-044` сопоставлен с `docs/ref6-local-restore-check-results.md`. REF-06G реально восстановил оба immutable generation `current|previous` в одноразовую network-none DB/media среду:42 tables,30 migrations,15 media files/6240 bytes; SHA/archive/path проверки, transactional `pg_restore`, unchanged main DB/catalog и zero residual containers/networks/volumes подтверждены, independent review APPROVED. Это local partial evidence. Full AC остаётся открыт для owner-confirmed production procedure, admin и external break-glass path, safety/rollback, tombstone/deletion ledger, session/rights reset, code-version compatibility и HTTP/public smoke. Первое чтение ошиблось только именем файла; после поиска фактического tracked path одинаковая ошибка не повторялась.

### D-980: DEV-22 single-AC evidence mapping

`AC-043` / `AT-043` сопоставлен с `docs/ref6-local-backup-results.md` и существующим BACKUP contract. REF-06F локально подтверждает два immutable current/previous поколения PostgreSQL+media, manifest/SHA, `pg_restore --list`/`tar --list`, atomic last-good retention при сбоях, отсутствие пяти foundation secrets и независимое review без findings. Это local partial evidence. Full AC blocked до семи внешних зашифрованных точек, отдельного ключа, расписания, наблюдаемого внешнего отказа и реального restore; локальный комплект не выдаётся за внешнюю/полную резервную систему.

### D-979: DEV-10 single-AC evidence mapping

`AC-008` / `AT-008` сопоставлен с уже завершённым локальным DEV-10 без нового запуска и без изменения продукта. Exact package summary и MEDIA-06 подтверждают17 альбомов/214 оригиналов и порядок; `test_g10_writer_002_create_exact_aggregate_and_zero_write_replay` подтверждает единый aggregate без копий; `test_g10_public_002_root_page2_and_modal_are_exact_bounded` и `test_g10_public_008_server_rendered_catalog_page2_modal_and_album` подтверждают root, direct `?page=2`, modal и17 самостоятельных album routes. Это local partial evidence, не полный PASS: persistent apply/publication, итоговая TEST-10 и responsive/manual acceptance остаются. Исторические `automation_state=text_only` и пустой `executable_ids` не переписываются без отдельного решения о модели реестра.

**Текущий D-976 (2026-11-13):** после owner-defer remaining23 INFOGRAPHICS и stage8 reconciliation D-975 выполнен новый read-only аудит TEST-07 без Playwright/широкого запуска. `implementation-traceability.csv`, `acceptance-cases.csv`, `acceptance-automation-status.csv` содержат exact140 rows/140 unique AC/140 unique case IDs; missing/extra между тремя реестрами0. Automation registry остаётся историческим:17 `text_only`,20 `partial_http`,103 `assertions_waiting_driver`; его сообщения «приложение отсутствует» нельзя считать актуальными после локальной реализации, но массово перекрашивать140 строк без per-AC evidence запрещено.

Первый bounded reconciliation slice — exact12 primary delivery `DEV-09`: `AC-001`, `AC-025`, `AC-051`, `AC-MIG-001–009`. Для10 (`AC-001`, `AC-025`, `AC-MIG-001–005`, `AC-MIG-007–009`) существуют локальные частичные доказательства DEV-09/10/MEDIA-06, включая exact URL/content packages, two-URL wash, gallery17/214 SHA evidence, source/media maps и price rows; ни один полный AC не объявлен PASS, потому что persistent apply/publication/READY и часть общесайтовой сверки отсутствуют. `AC-051` и `AC-MIG-006` отдельно blocked на фактической рекламной выгрузке ANA-Q041 и несвязанных URL; публичный crawl не подменяет эти факты. Следующий разрешённый TEST-07 инкремент — только per-AC evidence mapping этих12 строк к уже существующим named Django suites/doc evidence, затем review; новый framework/driver/Playwright/product endpoint не добавлять. TEST-08/этап9 остаются закрыты.

### D-977: DEV-09 exact12 evidence mapping

| AC | Локальное доказательство | Текущий вывод | Остаток до полного AC |
| --- | --- | --- | --- |
| AC-001 | DEV-09 package/create/replay; named `public-read`, `public-http`, `public-nav` suites | local partial | all114 exact paths, persistent apply и полное сравнение источника |
| AC-025 | DEV-10 `test_g10_writer_002_create_exact_aggregate_and_zero_write_replay`, `test_g10_public_002_root_page2_and_modal_are_exact_bounded`, `test_g10_public_008_server_rendered_catalog_page2_modal_and_album`; MEDIA-06 exact17/214 | local partial | persistent import/publication, READY и TEST-10 |
| AC-051 | локальный crawl/ZIP/packages не содержат рекламную выгрузку и неизвестные несвязанные URL | blocked | ANA-Q041 и внешние факты владельца |
| AC-MIG-001 | route-map115; DEV-09 packages и named public suites | local partial | all114 applied/published materials и исходные redirect chains |
| AC-MIG-002 | `test_migm_006_same_wash_page_primary_alias_http_and_canonical` | local partial | решение по рекламе/launch и persistent apply |
| AC-MIG-003 | DEV-10 `test_g10_writer_002_create_exact_aggregate_and_zero_write_replay`, `test_g10_public_001_closed_query_parser_and_page1_redirect`, `test_g10_public_002_root_page2_and_modal_are_exact_bounded`, `test_g10_public_008_server_rendered_catalog_page2_modal_and_album`; exact214 | local partial | production import/publication и TEST-10 |
| AC-MIG-004 | route evidence сохраняет cohort legacy10 | not PASS | representations/READY-06 и controlled import |
| AC-MIG-005 | MEDIA-06 path/bytes/SHA; gallery fail-closed tests; два документированных error URL | local partial | final bindings/application/cleanup READY |
| AC-MIG-006 | публичный crawl не подменяет рекламную выгрузку и дополнительные несвязанные пути | blocked | ANA-Q041 и внешние факты владельца |
| AC-MIG-007 | exact closed DEV-09 package/render tests | local partial | full60+legacy10 и READY-06 |
| AC-MIG-008 | exact DEV-09 price/table package tests | local partial | persistent placement и полное сравнение источника |
| AC-MIG-009 | MEDIA-06 exact binding/bytes/SHA; DEV-10 exact214 aggregate | local partial | persistent import и whole-site MEDIA-04 |

Значения `automation_state` и `executable_ids` в реестре намеренно оставлены без изменения: D-977 уточняет только поле остатка по уже имеющимся доказательствам и не выдаёт частичное локальное покрытие за полный PASS.

**Текущий D-315:** локальные base-image исправления и независимое ревью завершены; [результаты](base-image-security-remediation.md). Каталог1056/40, приложение/11FOUNDATIONнеисполнены; vendorостатокнеобнулён. Только следующий явный допуск владельца разрешает ограниченную DEV-02/28.

**Обновление D-313:** TEST-Q008 принят; локальный вход через Nginx проверен с компьютера и из Docker, изоляция/ограничения подтверждены независимо. [Итог](local-foundation-proxy-check.md). Базовые образы имеют открытый остаток безопасности; код сайта запрещён. Старые упоминания запрета подготовки/неработающего HTTP относятся к истории до D-312/313.

**Текущее состояние 30.10.2026:** TEST-Q006 принят D-310. [Единый пакет TEST-Q007](local-foundation-package.md) согласован D-311; независимое ревью R064/065 закрыто. Установки и код не разрешены. Каталог: 1056 экземпляров / 40 файлов; матрица 17 text_only / 7 partial_http / 116 assertions_waiting_driver. Это частичное авторство, не прохождение AC. 85 самопроверок драйвера прошли. Следующие абзацы с TEST-Q006 «на согласовании» и прежними числами — история до D-310; действующие зависимости в tasks.md. Код и установки по-прежнему запрещены.

Дата: 2026-10-30. Этап 7 в работе. Основания — D-301–D-305 и повторное поручение владельца продолжать тесты без кода нового сайта и без действий на старом сайте/VPS. Предыдущий проход сохранён в acceptance-test07-preflight.md; его семь первоначальных самопроверок — исторический результат, текущий ниже.

## Заключительный проход: решение по достаточности

2026-10-30:по прямому поручению владельца выполнен итоговый аудит без новых пачек тестов. [Пакет TEST-EXIT-20261030-01 / TEST-Q006](stage7-exit-review.md) и [20-rowregister](stage7-exit-register.csv) подготовлены на согласование. Независимый stage7_exit_audit закрыл R061–063 к предложению; пригодна только ограниченная локальная первая очередь после ENV-05/предложенныхARC-11/TEST-12 и отдельного разрешения8. ПолныйTEST-01/07 не завершён.

1043/39 и матрица140AT/140AC/63REQ,20text_only/7partial_http/113waitingdriver неизменны.83самопроверки/4документные проверки — прежние факты, не приложение. Новыхбиблиотек/установок/кода/измененийсервера нет. ДействующийDEV-02→TEST-01+ARC-10 сохраняется до ответа. Работа локально, безcommit/push.

Проверки exitпакета:20-rowregister точносовпадаетсcurrentAT/AC/states/delivery/supporting, заполненыконкретныемодульныеворота/роли; исходнаяdependencyDEV02сохранена. После синхронизации4document/изоляционных passed, skipped/unexpected/flaky0,3,096с: `test-results/acceptance/documents-stage7-exit-results.json`, `work/acceptance-documents-stage7-exit.txt`. git diff --check без ошибок. Это не прогонысайта и не новыеfeatureсценарии.

## Предыдущий проход: прайсы и связанные суммы главной

2026-10-30: добавлены25price-editor/11price-home. Пакет **1043 tests in 39 files**, collection exit0:work/acceptance-stage7-list-prices.txt. TEST-R060 исправлен и независимо закрыт. [Отчёт и ограничения](acceptance-prices-review.md).36сценариев сайта не исполнялись:нет приложения/bridge/bindings. Транспорт не менялся, прежние83selfchecks не повторялись и не суммируются с новойпартией.

Матрица140AT: **20 text_only /7 partial_http /113 assertions_waiting_driver**. Полные AC/UX-07/TEST-07 открыты. Старый сайт/VPS не менялись, код нового сайта не писался; работа сохранена локально без commit/push.

После синхронизации4document/изоляционных проверки passed, skipped/unexpected/flaky0,3,055с: `test-results/acceptance/documents-prices-results.json`, `work/acceptance-documents-prices.txt`. JS/PowerShell syntax и git diff --check без ошибок. ПрежниеID AT012/016 сохранены и дополнены прямымиcrosslinksпрайс-сценариев.

## Предыдущий проход: служебные квоты и сохранение версий

2026-10-30: добавлены4service-quota/15version-storage/3selfchecks. Пакет **1007 tests in 37 files**, collection exit0:work/acceptance-stage7-list-service-version.txt. TEST-R059 исправлен и независимо закрыт. **83driver-safety passed**, skipped/unexpected/flaky0,12,816с: test-results/acceptance/driver-service-version-results.json. [Отчёт и ограничения](acceptance-service-version-review.md).19сценариев сайта не исполнялись:нет приложения/bridge/bindings/controller/physicalARC10.

Матрица140AT: **21 text_only /7 partial_http /112 assertions_waiting_driver**. Полные AC/UX-07/TEST-07 открыты. Старый сайт/VPS не менялись, код нового сайта не писался; работа сохранена локально без commit/push.

После синхронизации4document/изоляционных проверки passed, skipped/unexpected/flaky0,2,849с: `test-results/acceptance/documents-service-version-results.json`, `work/acceptance-documents-service-version.txt`. JS/PowerShell syntax и git diff --check без ошибок.

## Предыдущий проход: прерывание фиксации URL

2026-10-30: добавлены11URL-transition/2selfchecks. Пакет **985 tests in 35 files**, collection exit0:work/acceptance-stage7-list-url-transition.txt. TEST-R056–058 исправлены и независимо закрыты. **80driver-safety passed**, skipped/unexpected/flaky0,13,021с: test-results/acceptance/driver-url-transition-results.json. [Отчёт и ограничения](acceptance-url-transition-review.md).11сценариев сайта не исполнялись:нет приложения/bridge/bindings/controller/physicalARC10.

Матрица140AT: **24 text_only /7 partial_http /109 assertions_waiting_driver**. Полные AC/UX-07/TEST-07 открыты. Старый сайт/VPS не менялись, код нового сайта не писался; работа сохранена локально без commit/push.

После синхронизации4document/изоляционных проверки passed, skipped/unexpected/flaky0,2,801с: `test-results/acceptance/documents-url-transition-results.json`, `work/acceptance-documents-url-transition.txt`. JS/PowerShell syntax и git diff --check без ошибок.

## Предыдущий проход: URL, редиректы и аварийный HTML

2026-10-30: добавлены12URL/reserve/SEO и16URLreuse. Пакет **972 tests in 34 files**, collection exit0:work/acceptance-stage7-list-url-reserve.txt. TEST-R055 исправлен и независимо закрыт. [Отчёт и ограничения](acceptance-url-reserve-review.md).28сценариев сайта не исполнялись:нет приложения/bridge/bindings/controller/physicalARC10. Транспорт не менялся, прежние78selfchecks не повторялись и не суммируются с новыми сценариями.

Матрица140AT: **26 text_only /7 partial_http /107 assertions_waiting_driver**. Полные AC/UX-07/TEST-07 открыты. Старый сайт/VPS не менялись, код нового сайта не писался; работа сохранена локально без commit/push.

После синхронизации4document/изоляционных проверки passed, skipped/unexpected/flaky0,2,941с: `test-results/acceptance/documents-url-reserve-results.json`, `work/acceptance-documents-url-reserve.txt`. JS/PowerShell syntax и git diff --check без ошибок.

## Предыдущий проход: главная после удаления источника и общие компоненты

2026-10-30: добавлены7home-source/4shared-component. Пакет **944 tests in 32 files**, collection exit0:work/acceptance-stage7-list-home-blocks.txt. TEST-R054 исправлен и независимо закрыт. [Отчёт и ограничения](acceptance-home-blocks-review.md).11сценариев сайта не исполнялись:нет приложения/bridge/bindings/controller/физического ARC-10. Транспорт не менялся, прежние78selfchecks не повторялись и не суммируются с новыми сценариями.

Матрица140AT: **29 text_only /7 partial_http /104 assertions_waiting_driver**. Полные AC/UX-07/TEST-07 открыты. Старый сайт/VPS не менялись, код нового сайта не писался; работа сохранена локально, без commit/push.

После синхронизации4document/изоляционных проверки passed, skipped/unexpected/flaky0,3,039с; `test-results/acceptance/documents-home-blocks-results.json`, `work/acceptance-documents-home-blocks.txt`. JS/PowerShell syntax и git diff --check без ошибок.

## Предыдущий проход: форма без JS, CSRF и кэш

2026-10-30: добавлены8native/CSRF,22cache и4selfchecks. Пакет **933 tests in 30 files**, TEST-R052–053 независимо закрыты. **78 driver-safety passed**, skipped/unexpected/flaky0,6,576с; JSON test-results/acceptance/driver-form-native-cache-results.json. Collection exit0:work/acceptance-stage7-list-form-native-cache.txt. [Отчёт и ограничения](acceptance-form-native-cache-review.md).

Матрица140AT: **33 text_only /7 partial_http /100 assertions_waiting_driver**. Новые30сценариев сайта не исполнялись:нет приложения/fixture bridge/bindings. Полные AC/UX-07/TEST-07/физический ARC-10 открыты; старый сайт/VPS не менялись, код нового сайта не писался.

После синхронизации4document/изоляционных самопроверки passed, skipped/unexpected/flaky0,2,985с: `test-results/acceptance/documents-form-native-cache-results.json`, `work/acceptance-documents-form-native-cache.txt`. JS/PowerShell syntax и git diff --check без ошибок. Текущая работа сохранена локально, commit/push в этой партии не выполнялись.

## Предыдущий проход: restore и частичная очистка логов

2026-10-30: добавлены10restore/2partial-log-delete/7selfchecks; прежний logging25→24 после удаления необоснованного password-case. Пакет **899 tests in 28 files**, TEST-R046–051 независимо закрыты.74driver-safety прошли; restore/удаления не исполнялись. [Отчёт и ограничения](acceptance-restore-log-review.md).

Матрица140AT: **35 text_only /7 partial_http /98 assertions_waiting_driver**. Только assertions/оснастка:нет реальных CLI/framework/CSRF/controller/bridge/OS/ключей и полного AC. Старый сайт/VPS не трогаем, код нового сайта не пишем; этап7/TEST-07/UX-07/физический ARC-10 продолжаются.

## Предыдущий проход: квота логов и фоновые отказы

2026-10-30: добавлены 9 log-quota/6 background-jobs/4 domain selfchecks. Пакет **881 tests in 26 files**; TEST-R040–045 независимо закрыты в уточнённой частичной области. 67 driver-safety прошли; это оснастка, не физические квоты/остановки работников. [Отчёт и ограничения](acceptance-quota-jobs-review.md).

Матрица140AT: **36 text_only /7 partial_http /97 assertions_waiting_driver**. Нет приложения/controller/bindings и доказанного OS/FS capture; полные AC/TEST-07/UX-07/физический ARC-10 не пройдены. Старый сайт/VPS не трогаем, код нового сайта не пишем.

## Предыдущий проход: вход и несохранённый текст

2026-10-30: добавлены12auth-login/10unsaved-editor/2memory selfchecks. Пакет **862 tests in 24 files**, TEST-R039 независимо закрыт. Свежие63driver-safety прошли; это оснастка, не исполнение новых входов/сохранений приложения. [Отчёт и ограничения](acceptance-auth-memory-review.md).

Матрица140AT: **38 text_only /7 partial_http /95 assertions_waiting_driver**. Браузерное чтение ограничено URL/localStorage/sessionStorage, не доказывает отсутствие transient/IndexedDB/сети. Реальные ingress/IP/CSRF/привязки ещё требуют независимой проверки. Приложение отсутствует, полный AC/TEST-07/UX-07/окончательный ARC-10 не пройден; старый сайт/VPS и код нового сайта не трогаем.

## Предыдущий проход: разметка, ссылки и время версий

2026-10-30: добавлены30editor-safety/4version-time. Пакет **838 tests in 22 files**. TEST-R036–038 исправлены и независимо закрыты:UTC без диктовки Z, экспорт аудита вместо версии, секунды UI необязательны. Новых существенных замечаний в целевой области нет. [Отчёт и ограничения](acceptance-editor-time-review.md).

Матрица140AT: **40 text_only /7 partial_http /93 assertions_waiting_driver**. Приложения/bindings нет, новые бизнес-сценарии не исполнялись. NoJS-парсер не доказывает runtime/CSP/SSRF; полные AC/TEST-07/UX-07/окончательный ARC-10 открыты. Старый сайт/VPS и код нового сайта не трогаем.

## Предыдущий проход: перенос и границы редактора

2026-10-30: добавлены14editor/14migration/1source-only. Пакет **804 tests in 20 files**. TEST-R033–035 исправлены и независимо закрыты; MAP-015/032 и старые цены/классы автомойки остаются отдельными неподготовленными ветвями. Source-only на16закреплённых HTML:1passed/0skipped/unexpected/flaky. Утренний harness:71passed, это оснастка, не AC сайта. [Отчёт и ограничения](acceptance-migration-editor-review.md).

Матрица140AT: **43 text_only /7 partial_http /90 assertions_waiting_driver**. Реальных импорта/бизнес-сценариев приложения нет: приложение/bindings/bridge отсутствуют. Полные AC/TEST-07/UX-07/окончательный ARC-10 открыты, этап7 продолжается; старый сайт/VPS и код нового сайта не трогаем.

## Предыдущий проход: резервные точки и ночной HTML

2026-10-30: добавлены23backup/12html-build и3самопроверки разделённых control-допусков. Целевое независимое ревью закрыло TEST-R029–032. Пакет: **775 tests in 17 files**. Свежие61driver-safety/4documents прошли без skipped/unexpected/flaky; это оснастка, не jobs/restore/AC приложения. [Отчёт и ограничения](acceptance-backup-html-review.md).

Матрица140AT: **49 text_only /7 partial_http /84 assertions_waiting_driver**. Конкретных bindings/сервисов/приложения/изолированного стенда нет, новый код сайта не пишется. Старый сайт/VPS/реальный Яндекс Диск не использовались. Полный restore/crypto-инструмент/physical quota/ARC-10/TEST-07/UX-07 ещё не готовы, этап7 продолжается.

## Предыдущий проход: окна формы и общие блоки

2026-10-30: добавлены20form-window/18shared-block сценариев и1самопроверка pending. Прежние74form assertions исправлены: private actual-db связь результата вместо публичного ID, разрешённый промежуточный pending не подменяется успехом. Целевое независимое ревью закрыло TEST-R024–028; [отчёт/артефакты/остаток](acceptance-form-blocks-review.md).

Пакет: **737 tests in 15 files**. Свежие58driver-safety и4documents прошли без skipped/unexpected/flaky; эти числа не суммируются с предыдущими67как разные проверки. Матрица: **55 text_only /7 partial_http /78 assertions_waiting_driver**, ни одного полного пройденного AC. Код сайта/VPS/живой сайт не затрагивались; приложения/bindings/стенда нет, этап7/TEST-07/UX-07/окончательный ARC-10 открыты.

## Предыдущий проход: SEO и обработка заявок

2026-10-30: добавлены26SEO/22request сценария, целевое независимое ревью закрыло TEST-R020–023. Пакет: **698 tests in 13 files**. Четыре существующие документные/изоляционные проверки повторены и прошли без skipped/unexpected/flaky; прежние67самопроверок транспорта/браузеров остаются историческим результатом. Матрица: **62 text_only /7 partial_http /71 assertions_waiting_driver**, ни одного полного пройденного AC. [Отчёт и ограничения](acceptance-seo-request-review.md).

Приложение/конкретные bindings/инфраструктура отсутствуют; новые бизнес-сценарии не исполнялись. Runtime/CSP/полная robots/restore/privacy не выданы за готовые. Старый сайт/VPS и код нового сайта не затрагивались. Этап7/полное TEST-07/UX-07/окончательный ARC-10 остаются открытыми.

## Предыдущий проход: медиа и журналы

2026-10-30: добавлены29media/25logging и14самопроверок транспорта. Полный пакет собирается: **650 tests in 11 files**; итоговый harness **67 passed**, без skipped/unexpected/flaky. Независимое целевое ревью TEST-R013–019 закрыто, новых существенных замечаний к этой области нет. Отчёт/артефакты и честные ограничения — [acceptance-media-logs-review.md](acceptance-media-logs-review.md).

Матрица140AT: **70 text_only /7 partial_http /63 assertions_waiting_driver**, ни одного полного пройденного AC. Конкретные bindings/fixture/приложение/инфраструктура отсутствуют. Неутверждённые форматы/лимиты загрузок не выданы за принятые правила; соответствующие положительные проверки отложены. Этап7 продолжается без кода сайта и действий на старом сайте/VPS; UX-07/окончательный ARC-10/полное TEST-07 не закрыты.

## Предыдущий проход после D-307/D-308

Владелец принял 58 UI-состояний/логическую схему и разрешил локальный тестовый адаптер с оставшимися проверками. UX-08 принят в документированной области; полный UX-07/окончательный ARC-10 не закрыты. Подготовлены:

| Поднабор | Экземпляров | Статус |
|---|---:|---|
| Прежние документы/браузеры | 10 | Самопроверки инструмента, не AC |
| driver-safety | 43 | Ограничения/stdio/остановка процесса/UI-подготовка/отдельный control-origin и допуск run/instance/admission |
| public-http | 117 | Прежний частичный HTTP |
| public-contracts | 252 | Прежние частичные metadata/cache/viewport |
| application-contracts | 27 | Утверждения, ожидающие привязок к приложению |
| form-contracts | 74 | Утверждения, ожидающие привязок к приложению |
| content-lifecycle | 33 | Новые частичные утверждения дерева/сессий/восстановления/ручных операций |
| fallback-contracts | 26 | Новые частичные утверждения логической аварийной схемы; исполнение за конкретным ARC-10 |
| Всего | **582** | Это тестовые экземпляры, не число пройденных требований |

Матрица140AT: **83 text_only /7 partial_http /50 assertions_waiting_driver**. AT-002 сохраняет partial_http и дополнен fallback-ветвями; состояние строки не означает полного покрытия. Ни один полный AC не пройден. Относительно предыдущих480 добавлены102экземпляра:43самопроверки драйвера,33lifecycle,26fallback. Прежние10служебных сохраняются.

Транспортный слой isolated-application-driver.js теперь есть. Он выполняет реальные UI/HTTP, не вычисляет бизнес-результаты; отдельный control-транспорт вне origin приложения предназначен только для изолированных fault-действий. Подробности/доказательства и ограничения — [local-test-adapter.md](local-test-adapter.md), [lifecycle](acceptance-content-lifecycle.md), [fallback](acceptance-fallback-contracts.md). Конкретные local-bindings.json/local-fixture-bridge.mjs/controlSession и приложение/инфраструктура ещё отсутствуют. При отсутствии зависимостей — явная ошибка, без фейкового сайта/скипов. Исторический APPLICATION_DRIVER_NOT_IMPLEMENTED ниже не является текущим состоянием модуля.

Финальные результаты 2026-10-30:

- Контейнерный `--list`: **582 tests in 9 files**, exit0; work/acceptance-stage7-list-adapter.txt. Сборка не выполняет операции сайта.
- Итоговый harness: **53 passed**, skipped/unexpected/flaky=0,53,9с; test-results/acceptance/harness-results.json и work/acceptance-harness-adapter-final.txt. Это43driver-safety+4документных+6браузерных самопроверок, не AC приложения.
- Проверены завершение обычного/игнорирующего TERM процесса, фактическое отсутствие PID/группы после отказа, очистка подписок, запрет UI-подготовки с мутацией, отдельный control-origin/allowlist и отклонение устаревших run/instance/admission/operation. Проверки протокола не доказывают реализацию будущего контроллера.
- Новые app/form/lifecycle/fallback assertions на отсутствующем стенде не запускались; повторять заведомо тот же отказ без изменившегося условия нельзя. Код нового сайта и production не затрагивались. Версии/образ D-303, системные настройки и внешние подключения не менялись.

Независимый рецензент plan_reviewer прочитал адаптер/runner/safety/lifecycle/fallback и относящиеся контракты, ничего не редактировал и не запускал. Исполнитель stage7_remaining_ui подготовил33lifecycle/26fallback; координатор — транспорт/safety/подключение/реестры. Совместного редактирования одних файлов не было.

| ID | Приоритет | Исправление и итог целевой перепроверки |
|---|---|---|
| TEST-R005 | P2 | Таймаут ожидал только отправку TERM. Теперь собственная Linux-группа, TERM→KILL и ожидание close/исчезновения группы; при неопределённости блокировка драйвера. Независимо закрыто, исполнено в safety |
| TEST-R006 | P2 | UI без HTTP-ответа попадал в decode(undefined). Теперь ui-observed подтверждается фактическим DOM, не серверным accepted. Независимо закрыто |
| TEST-R007 | P2 | Для restore/session нужен уже открытый редактор. Реальные goto/fill выполняются до отдельной финализации возраста сессии; ошибка блокирует драйвер. Независимо закрыто |
| TEST-R008 | P2 | Подготовка ввода могла скрыть autosave. Теперь actual-db до/после и запрет изменяющих запросов; полнота/отложенные операции конкретных bindings за отдельным ревью. Независимо закрыто, orchestration проверен safety |
| TEST-R009 | P3 | Отрицательная проверка загрузки зависела от отсутствия настоящего private config. Используется отдельный отсутствующий тестовый вход, штатный config не трогается. Независимо закрыто |
| TEST-R010 | P2 | Fault-команды не должны идти через отключаемый APP/EDGE. Теперь отдельный control-origin/session и allowlist, act(TEST-CONTROL) запрещён. Независимо закрыто на уровне тестового транспорта |
| TEST-R011 | P2 | Два undefined могли дать ложный успех для поколений/ID/счётчиков/ledger. Теперь обязательны наличие/типы/допустимые значения. Независимо закрыто |
| TEST-R012 | P2 | Старый preflight не разрешает новые команды бессрочно. Перед каждой командой свежий actual-http допуск текущего run/instance/admission, четыре связи проверяются в запросе/ответе. Независимо закрыто на стороне тестового клиента; атомарная проверка до исполнения обязательна для будущей службы |

Новых существенных замечаний в этой целевой области нет. **Это не полное TEST-07:** реальное приложение, привязки/fixture/управляющая служба, физические примитивы и прочие ветви остаются неподготовленными. Самоконтроль/маркер/echo заголовков не подменяют независимое доказательство настоящих действий.

## Исторический результат предыдущего прохода

| Поднабор | Количество отдельных тестов | Фактический статус |
|---|---:|---|
| Harness: документы/изоляция | 4 | Пройдены |
| Harness: запуск браузера и инертный HTML-парсер, по две пробы Chromium/Firefox/WebKit | 6 | Пройдены с отключённым JavaScript, без сети |
| Прежний публичный HTTP | 117 | Частичные проверки; предыдущий первоначальный прогон — один красный guard и 116 невыполненных, не повторялся без нового стенда |
| Новые публичные HTML-контракты | 252 | Собираются; не выполнялись против приложения, которого пока нет |
| Права/версии/Stable/ручной снимок/статусы | 27 | Утверждения написаны; пробный прогон остановлен на первой отсутствующей зависимости |
| Поля, телефон, повторы обеих форм | 74 | Утверждения написаны и собираются; тот же отсутствующий адаптер, отдельного повторного отказа не запускали |
| Всего | **480** | Это количество тестовых экземпляров, а не пройденных требований |

Добавлены 356 экземпляров относительно первоначальных 124. Нормативные 63 REQ/140 AC и постоянные 140 AT не перенумерованы. [Матрица автоматизации](acceptance-automation-status.csv): **116 text_only / 7 partial_http / 17 assertions_waiting_driver**. Ни один полный AC не объявлен пройденным. Один составной AT имеет несколько параметризованных проверок и оставшиеся ветви; число 480 не заменяет исходную матрицу.

Публичный набор проверяет оба точных адреса автомойки, canonical галереи/page=2/17 альбомов, единственный viewport без запрета масштабирования, отсутствие meta-refresh и явный no-cache обычных опубликованных HTML. Реальное содержимое, альбомы/214 SHA, Schema/alt, noindex/hidden/private/аварийный режим и изменение валидаторов этим не проверены. Детали — acceptance-public-contracts.md.

App/form-набор содержит реальные будущие действия и конкретные утверждения, а не always-pass. Отдельный внутренний интерфейс описан в acceptance-application-driver.md. **Адаптер ещё отсутствует, поэтому это не готовые browser-e2e.** Имитатор бизнес-правил/сайта не создан. Нормализованные тестовые имена/поля не являются утверждением HTTP-API или ORM-моделей продукта. UI-адаптер остаётся за UX-08, инфраструктурные драйверы за ARC-10; сами согласования не пропущены.

## Независимое ревью

Публичный поднабор подготовил исполнитель stage7_public; app/form/helper/runner — координатор. Отдельный рецензент plan_reviewer читал новые файлы и соответствующие нормативные документы, ничего не редактировал и не запускал. Полное TEST-07 ему не предъявлялось как готовое.

| ID | Приоритет | Замечание | Исправление и независимая перепроверка |
|---|---|---|---|
| TEST-R004 | P2 | Защищённые поля пробовали строкой forged: неверный boolean/несуществующий Asset могли отклониться валидацией даже при ошибочных правах | Используются допустимые типы, противоположный boolean, другой существующий Asset. Тот же запрос принимается владельцем и реально меняет поле. Главная проверяется отдельно обычным текстовым полем. Независимо закрыто, новых замечаний по целевой области нет |

Дополнительно положительное чтение владельца подтверждает существование истории/заявки/заметки и canary перед отрицательной пробой другой роли. В контракте запрещено скрыто подменять положительный контроль другим серверным обработчиком. Если будущая согласованная реализация разделит действия по разным endpoint, тесты явно уточняются/перепроверяются; общего endpoint аналитика не требует.

Рецензент подтвердил соответствие публичных свойств, пределов и нормализации нормативным документам, честное разделение assertions/готового e2e, сетевые ограничения и новую матрицу. Полное TEST-07 остаётся открытым; маркер driverKind сам по себе не доказывает настоящую реализацию адаптера.

## Проверки и доказательства

- Финальное контейнерное перечисление: **480 tests in 6 files**, exit 0; work/acceptance-stage7-list-final.txt.
- Harness: **10 passed, 0 skipped/unexpected/flaky**, 51,99 с по JSON; test-results/acceptance/harness-results.json. Проверен и реальный DOMParser при отключённом JS во всех трёх движках; это не восемь реальных семейств браузеров сайта.
- App: exit 1, **APPLICATION_DRIVER_NOT_IMPLEMENTED**, 26 did not run. Прогон намеренно останавливается max-failures=1. JSON stats: unexpected=1, skipped=26; отдельное errors содержит только сообщение об остановке после максимального одного отказа. Это красный прогон, не успешная проверка приложения; test-results/acceptance/application-contracts-results.json, work/acceptance-application-initial.txt.
- Form: сборка проверена; исполнение не запускалось с заранее известной той же отсутствующей зависимостью. В direct-POST не требуется исполнение JS/реальная цель Метрики: для принятого намерения проверена лишь верхняя граница целей, полное AT-057 остаётся отдельно.
- Формат: git diff --check без ошибок. Первое локальное --list в обычной песочнице не смогло записать JSON (EPERM); повтор в согласованном контейнере с разрешённой записью прошёл. Это ограничение среды, не дефект сайта.

Вспомогательные JSON/подробные выводы вне Git. Версия инструмента/lock/digest не менялись. Новых зависимостей, глобальных установок, системных настроек, данных клиентов или внешних интеграций нет. При актуализации статусов обнаружена прежняя ошибка форматирования двух строк ворот в implementation-plan.md §3; ENV-05 и TEST-01/07 восстановлены без изменения согласованных условий и проверены рецензентом.

## Что требуется до завершения этапа

1. Довести полный UX-07 и конкретную схему ARC-09/10 **на бумаге/изолированно**, без действий на старом VPS. UX-08/логика приняты D-307; TEST-Q002/003 уже отвечены, повторно наличие/назначение сервера не спрашивать.
2. Подготовить и независимо проверить конкретные bindings/fixture bridge/наблюдения/controlSession к настоящему изолированному приложению после соответствующего разрешения. Транспорт уже подготовлен, бизнес-действия нельзя подменять записью БД/вычислением expected. Не создавать скрытые production endpoints. Приложение по-прежнему писать нельзя.
3. Подготовить остальные ветви каталога: медиа/дерево/восстановление, окна CSRF/receipt, ошибки/конкуренцию, логи/квоты/сканеры/ТГ, backup/restore/head/fallback и документальные/ручные проверки по назначению. Конкретные инфраструктурные сценарии не исполняются до ARC-10.
4. Передать полный код тестов и fixtures на TEST-07, явно отделяя ожидаемые первоначальные отказы из-за отсутствия приложения от дефектов самих тестов. Только после этого и отдельного разрешения владельца возможен этап 8.

Текущий результат — существенное продолжение этапа 7, **не его завершение**. Старый сайт, сервер, его файлы/БД/ОС/настройки и код нового сайта не изменялись.
