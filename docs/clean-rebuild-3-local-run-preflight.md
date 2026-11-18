# REBUILD-3 — local run static preflight

Дата: 2026-11-18. ID: `RB3-RUN-PREFLIGHT-001`. Статус: **STATIC BLOCKED; runtime0**.

## 1. Разрешённая граница

D-1452 разрешил только bounded plan/static preflight следующего локального rebuild. Python/Django/Docker/БД/media не запускались; target DB/roles/files/results не создавались. Этот документ не является разрешением на execution, cleanup, deploy, live или push.

Цель preflight — доказать наличие всех уже утверждённых входных authority для одного вызова `run(config, evidence)` и остановиться до эффектов при отсутствии любого из них.

## 2. Подтверждённые факты

- Code-only adapter и entrypoint закрыты независимыми D-1440–D-1450; D-1452 закрыл whole slice без повторного review framework.
- Existing foundation PostgreSQL слушает только internal Docker network `nestakada-foundation-dev-db`; host DB port не публикуется. Это правильная граница, не дефект.
- Existing foundation private directory уже содержит owner-only DB CA/bootstrap secret authority. Secret bytes не читались и не выводились.
- Existing foundation source snapshot содержит Django application under `/app`; reviewed adapter находится отдельно in `src/rebuild3_importer`. Будущий runner может использовать один exact read-only adapter snapshot plus current `/app`, без нового image/service.
- Source media, target rebuild and result roots должны быть тремя exact trusted directory authorities. Target/result могут быть sibling mode0700/UID10001 directories in one dedicated ignored volume; source must be a separate read-only mode0700/UID10001 snapshot. Host bind permissions нельзя предполагать — их надо доказать before source/DB open.
- D-1468 approved the exact112 Page/exact114 stored Route/target media303 capture→package→limits+digest code path. A production instance still does not exist before its separately authorized stopped-writer capture; public outcomes remain115 because gallery page1 is derived.
- Production `VerifiedLedgerEvidence` authority отсутствует. Repository contains only synthetic test values; request contract deliberately keeps latest deletion ledger external to DB/restore. D-1439 forbids the adapter from inventing that external format.

## 3. Blockers

| ID | Состояние | Почему execution закрыт | Минимальное продолжение |
|---|---|---|---|
| `RB3-RUN-B001` | CODE READY / INSTANCE NOT MATERIALIZED | D-1468 approved literal capture→package→exact limits+digest; no production capture has run | Materialize only inside a separately authorized stopped-writer capture; no generic loader or fabricated rows |
| `RB3-RUN-B002` | BLOCKED | No independently verified zero-row ledger identity/generation/digest bound to the future source snapshot | Keep as a separate request-ledger authority gate. Do not fabricate a UUID/digest and do not weaken `VerifiedLedgerEvidence` |
| `RB3-RUN-B003` | DEFERRED after B001/B002 | Exact runner snapshot/network/root/secret layout is not yet materialized | One disposable launcher container on the existing internal DB network, exact read-only source/adapter/CA/admin-secret mounts, tmpfs ephemeral role secrets and one dedicated ignored rebuild volume; no Compose service or daemon |

## 4. No-bloat decision

Recommended light sequence:

1. Implement and independently review only `RB3-FREEZE-AUTHORITY-001`: one literal builder and synthetic/static tests for exact approved inputs.
2. Stop at `RB3-LEDGER-AUTHORITY-Q001`; reuse a separately approved ledger authority when it exists. Do not implement it inside the importer.
3. Only when B001+B002 are closed, prepare one bounded launcher and one fresh runtime gate.

Rejected as unnecessary growth: config framework, YAML/JSON runtime schema, plugin/transform registry, job/queue, retry/resume, new service, published DB port, new image solely for the runner, and a second copy of the historical DEV validators.

## 5. Acceptance before any runtime

| ID | Scenario | Required result |
|---|---|---|
| `RB3-RUN-AC-001` | Hash the exact adapter/app/authority snapshots before container creation | Every digest equals its independently reviewed value; unknown/extra source0 |
| `RB3-RUN-AC-002` | Build typed freeze authority offline from literal approved inputs | pages112/stored routes114/public URL outcomes115/source media238/package media65/target media303, gallery17/214, resolved unmatched exactly1; digest externally fixed before source open |
| `RB3-RUN-AC-003` | Verify latest external request ledger independently | Typed evidence has nonzero identity, generation≥1, exact digest, rows0 and later binds to the captured source snapshot; no ledger bytes/path in output |
| `RB3-RUN-AC-004` | Validate source/target/result/secret roots | Absolute non-link trusted owner-only directories/files, source and target disjoint, target/result initially empty, no foreign run entries |
| `RB3-RUN-AC-005` | Validate foundation identity without mutation | Exact active dev manifest/container/image/network/DB identity; app/ingress/writers stopped before future freeze; no host DB publication |
| `RB3-RUN-AC-006` | Any AC001–005 missing, stale or ambiguous | Stop before role/DB/directory/result creation with one safe fixed code; automatic retry0 |

## 6. Result and next gate

Static result: `BLOCKED/RB3_RUN_INPUT_AUTHORITY_MISSING`, specifically B001+B002. Product code finding0; tool-side informational Windows wildcard-path error1, no repeat attempted. Runtime/effects0.

Next bounded code-only proposal is `RB3-FREEZE-AUTHORITY-001`. It does not authorize ledger implementation or local rebuild execution.

## 7. D-1454 pause

The first builder inspection confirmed all exact112 page cohorts are already covered by the 12 literal package readers and existing payload functions, so the future builder need not duplicate schemas/renderers. Work then paused owner after two equivalent Windows wildcard-as-path `rg` errors (attempts2); code/runtime0. Resume only with exact paths or `rg -g`.

## 8. D-1455 design blocker

Exact-path continuation proved that the package also carries runtime-random source Route, revision/usage, shared and media identities which the 12 static JSON cannot provide. `RB3-FREEZE-AUTHORITY-Q001` therefore requires an owner choice before code:

1. recommended: one bounded read-only capture while writers remain stopped, build/digest the literal in-memory package, then use a fresh RRRO source lifecycle whose existing equality checks reject any drift;
2. refactor the approved builder to derive all bindings dynamically inside one snapshot, with a larger code/review surface.

Both retain separate ledger/runtime gates. No generic package format or persistent staging authority is proposed.

Owner selected option1 in D-1456. The first code-only candidate is an immutable repr-hidden `FreezeCapture` plus one function reusing the exact four existing guarded public queries; it requires pages112/stored routes114 and source assets/files238, and has no persistence or private query. The separate public acceptance remains 115 URL outcomes because gallery `?page=1` is a derived redirect. Literal 12-package composition is a separate next substep after independent capture review.

D-1457 closed that capture substep with independent P1/P2/P3=0/0/0. Package composition is now active code-only; fresh RRRO equality, ledger and runtime remain closed.

## 9. D-1460 Page/Route authority

`RB3-PAGE-ROUTE-AUTHORITY-001` independently approved the exact112 published Page and exact114 stored Route composition with P1/P2/P3=0/0/0. It reuses the 12 existing package readers/renderers, binds captured runtime identities, preserves home generation2 current+previous, includes only the two stored aliases, and explicitly excludes the derived gallery `?page=1` outcome from Route. B001 is therefore narrowed to the separate media/shared/package completion; ledger and runtime gates remain unchanged and closed.

## 10. D-1461 media dimension blocker

Static inspection found that the current manifest requires positive raster width/height, while capture, legacy DB rows, DEV media packages and the accepted CSV authority do not contain those facts. No value may be fabricated. Recommended light option1 makes dimensions nullable for byte-preserved imported raster rows while preserving exact SHA/bytes, MIME/extension and same-handle magic checks. Option2 adds a bounded image-header decoder or approved Pillow boundary plus a separate runtime media pass. No media composition code or runtime was performed pending the owner choice.

Owner selected option1 in D-1462. Independent review approved the all-or-nothing optional raster dimension contract with P1/P2/P3=0/0/0; SHA/bytes/MIME/extension/magic and trusted-SVG boundaries remain unchanged. B001 now resumes at exact65 package-only media reconciliation; runtime remains closed.

## 11. D-1463 payload schema blocker

The literal readers correctly reconstruct source `page-content-v1`, but the D-1460 composition currently reuses that object as target payload even though RB3 accepts only `estakada.page-content@1`. A real package would therefore fail closed at `payload-envelope`; no runtime or target effect occurred. Recommended option1 is one closed per-kind old→new transformer with real-package coverage and no generic ETL/registry. Option2 temporarily carries two schemas and creates explicit conversion debt. Media completion pauses for the owner choice.

Owner selected option1. The candidate separates captured source payload/hash from target payload, adds one closed per-kind transformer and real-package coverage, but its independent content review did not start: the reviewer repeated the same false hash-mismatch claim twice while quoting the exact dispatched hashes. D-1464 anti-loop therefore pauses the task for owner direction; attempts2, findings/verdict0, runtime0.

Owner resumed with a different exact-path content reviewer. D-1465 closed the transformer after bounded fixes with P1/P2/P3=0/0/0: source hashes remain exact, target payloads are new-schema only, actual home history/actions/reviews/partners and the wash kind are covered, and no generic ETL/dual-schema layer was added. B001 resumes at exact media/shared/package completion; runtime remains closed.

## 12. D-1466 gallery usage ownership

Independent review approved the single-owner projection: exact214 legacy gallery page usages are consumed by exact214 unique GalleryPhoto asset/page pairs and do not create duplicate target AssetUsage rows. Every non-gallery eligible source usage still requires an exact binding, and any target PAGE_CURRENT overlap with gallery ownership fails. Media builder work continues code-only; runtime remains closed.

## 13. D-1467 media/shared package authority

Static downstream inspection corrected D-1466 before runtime: the gallery writer creates one eligible current Page usage and one eligible selected ordinary revision usage for every photo. Exact214 GalleryPhoto rows therefore consume exact428 source ledger rows as 214 closed pairs; the 214 draft rows remain excluded. No target gallery AssetUsage or compatibility ledger was added.

`RB3-MEDIA-AUTHORITY-002` then independently approved the one literal builder with P1/P2/P3=0/0/0. It reuses the pinned exact301 CSV and four existing package readers, preserves source238 identities, allocates package-only65 UUIDv4 once inside the package, produces target303 files/assets, resolves only the approved infographic, preserves the duplicate physical pair as separate identities, and builds literal SiteSettings/logo, gallery17/214 and semantic target usages30. Multiple old current/revision/shared ledgers may prove one target usage, but every eligible source row is covered exactly and the closed source-kind/scope matrix rejects impossible projections. Generic loader/registry/ETL/table/dependency0; runtime remains closed.

The next bounded code-only boundary is production `ManifestLimits` plus coherent package-digest handoff. Independently verified request-ledger evidence and any rebuild execution remain separate later gates.

## 14. D-1468 exact run authority and remaining choice

`RB3-RUN-AUTHORITY-002` independently approved the shared projection and `compose_run_authority()` with P1/P2/P3=0/0/0. Captured/fresh current and previous timestamps are package-digested and equality-checked. Exact limits are derived from the same package: section counts112/114/303/303/30/17/214, total bytes56,440,807, gallery bytes41,176,391, trusted SVG3 and exact maximum canonical bytes with the longest admitted snapshot ID. The test independently reconstructs the envelope and digest. Runtime remains0; the production package instance is intentionally not materialized before its owner-gated capture.

B002 remains the only authority-design blocker. Existing `app/service_requests/ledger.py` is an older per-UUID local deletion set; it has no independently backed identity/generation/digest/hash-chain and cannot be relabelled as `VerifiedLedgerEvidence`. D-1439 also forbids the importer from defining the external format.

`RB3-LEDGER-AUTHORITY-Q001`:

1. recommended/light: design and independently review a separate minimal durable zero-row genesis authority only for the current intake-default-off, source-request-count0 rebuild; it must have a nonzero identity, generation1, canonical digest, rows0, snapshot binding and an independently verified copy, and cannot authorize future nonzero request transfer or live intake;
2. defer the rebuild until the full production deletion-ledger authority and external encrypted location are implemented under the request/LEGAL launch gates.

Neither option is approved by this note. No ledger file, copy, key, runtime or rebuild was created.

Owner selected option1 in D-1469 for design/code only. `docs/clean-rebuild-3-zero-ledger-genesis-plan.md` now specifies one closed generation1/rows0 canonical genesis, externally pinned receipt and two owner-only copies on different filesystems. It explicitly cannot append, authorize nonzero requests/intake-on or replace the production encrypted deletion-ledger backup. B002 remains blocked until independent plan+code review and a separately authorized materialization/snapshot verification; runtime/files/keys/rebuild remain0.

D-1470 closed plan+code review with P1/P2/P3=0/0/0 after named-entry and ambiguous-close remediations. B002 is now **CODE READY / INSTANCE NOT MATERIALIZED**: Python/tests were not run and no real roots, genesis copies, receipt or snapshot evidence exist. Next explicit gate may run focused synthetic tests only; production materialization and rebuild execution remain separately closed.

D-1471 single authorized synthetic run passed 13/13, exit0, in an ephemeral no-network/read-only container; no DB or persistent authority was touched. B002 is now **CODE+TEST READY / INSTANCE NOT MATERIALIZED**. It remains blocked until a separately authorized operation provides two trusted owner-only roots on different `st_dev`, creates/verifies exact copies, pins the receipt through an approved trusted channel and later binds evidence to the stopped-writer source snapshot. Rebuild execution remains closed.

D-1472 read-only storage preflight found no admissible pair. Two existing Docker volumes both report `st_dev=2112`; a readonly `T:\\nestakada` bind reports distinct `st_dev=55` but Linux `uid=0/mode0777`, failing exact owner-only metadata. No persistent entry was created. B002 is **CODE+TEST READY / STORAGE BLOCKED**. Same-device copies or a platform-specific Windows-mode attestation would weaken the approved authority and are rejected. Recommended light path is an already existing second POSIX-compatible durable filesystem; otherwise defer to the full production independently encrypted storage. A custom VHD/WSL storage layer requires a separate owner decision because it materially expands setup and maintenance.

Owner selected the light defer path in D-1473. B002 remains blocked without a storage workaround. Static B001 inspection found that capture/compose functions are complete but no production capture entrypoint exists; existing `SourceLifecycle.open` requires snapshot-bound evidence before the fresh RRRO snapshot ID is known. `docs/clean-rebuild-3-freeze-capture-run-plan.md` proposes one shared lifecycle opener plus a ledger-free four-public-query capture wrapper with in-memory-only result. Runtime remains0 pending independent plan review.

D-1474 closed plan+code review P1/P2/P3=0/0/0 for the bounded capture entrypoint. It uses one private existing lifecycle opener; no executor/session/lifecycle escapes, exact public capture closes all DB authority before DB-free compose, and BaseException cleanup attempts every step. B001 is **CODE READY / TEST NOT RUN / INSTANCE NOT MATERIALIZED**. B002 remains storage-deferred. Synthetic fake-connection tests and any real DB capture remain separate runtime gates.

D-1475 records synthetic run1: exit1, 10 PASS/5 ERROR, all five before capture calls in Python3.14 mock string-target resolution. Production finding0; DB/network/persistence0. Test-only explicit imports+`patch.object` remediation is independently approved 0/0/0; production hash unchanged. B001 remains **CODE READY / SYNTHETIC RESULT NOT YET PASS / INSTANCE NOT MATERIALIZED**. A new owner permission is required for run2; no automatic repeat.

D-1476 records run2: collection failed before tests because generic `python-runtime` lacks pinned application dependency `nh3`; production/test functions did not execute. Independent diagnosis found code P1/P2/P3=0/0/0 and approved using the existing app-editor image rather than stubs, installs or code indirection. B001 remains **CODE READY / SYNTHETIC RESULT NOT YET PASS / INSTANCE NOT MATERIALIZED**. One app-editor run3 requires new owner permission; network/DB/project writes remain forbidden.

D-1477 run3 passed 15/15, exit0, in the existing app-editor image with no network/DB/secrets/project writes. B001 is now **CODE+SYNTHETIC-TEST READY / INSTANCE NOT MATERIALIZED**. A production capture is intentionally not run alone: its result is in-memory-only and must continue in the same stopped-writer process, while B002 storage/evidence remains deferred. No package/file/result authority was created.

D-1478 starts code-only correction of the remaining actual-run composition gap: pre-bound evidence cannot know the fresh RRRO snapshot ID. `docs/clean-rebuild-3-snapshot-ledger-bind-plan.md` limits the fix to one exact callable invoked after session creation and before source preflight, receiving only snapshot ID and returning existing evidence. Storage/materialization and runtime remain0 pending independent plan review.

D-1479 closes snapshot-bind plan+code review P1/P2/P3=0/0/0. Fresh session snapshot is validated before the one-call binder; full evidence is validated before OpenSource and again in SourceReader through shared predicates. Production `run()` now accepts the binder and cleans source/media on BaseException. B001/B002 instances remain unmaterialized; Python/DB runtime0. Focused synthetic tests require a separate owner gate.

D-1480 records snapshot-bind run1 39/40 and independent ACCEPTED_FAIL: the sole failure was a stale test expectation, not production. Test-only remediation proves SQL0 before preflight and exact SQL1 for invalid-ledger preflight; independently approved 0/0/0. B001 code remains unchanged; B002 storage remains deferred. Run2 requires new owner permission; DB runtime0.

D-1481 focused app-image run2 passed 40/40, exit0. Snapshot-after-open binding is code+synthetic closed: validated fresh snapshot reaches the binder once, full evidence is checked before OpenSource and by SourceReader, and cleanup is fail-closed. B001 is **CODE+TEST READY / INSTANCE NOT MATERIALIZED**. B002 is **CODE+TEST READY / STORAGE DEFERRED / INSTANCE NOT MATERIALIZED**. Real capture would be ephemeral and unusable without B002, so DB/rebuild runtime remains blocked and was not attempted.

D-1482 whole-slice static audit found no stale production caller of the replaced pre-bound evidence API. The 12-module importer suite is synthetic/fake/tempfile-only; one existing app-image invocation with network none, source readonly, `python -B` and tmpfs `/tmp` is the bounded sufficient regression. It remains a separate runtime gate. B001/B002 instances and DB/rebuild remain0.

D-1483 records authorized full synthetic run1: 138/166 PASS, 8 FAIL, 20 ERROR, with DB/network/persistent writes0. Independent triage reduces the result to one payload closed-schema production defect plus two stale/broken test helpers. Minimal three-edit remediation is prepared without new layers; independent review and a new owner gate are required before run2. B001/B002 instances and DB/rebuild remain0.

D-1484 closes remediation review APPROVED 0/0/0. Exact production branch, coordinator oracle and fake-cursor fixes introduce no new layer or dependency; runtime remains0 after edits. The only next execution is one separately authorized full synthetic run2 under the same no-network/read-only/tmpfs boundary. B001/B002 instances and DB/rebuild remain0.

D-1485 records full synthetic run2 at 160/166 PASS, with production findings0. Four failures are a command-layout defect caused by whole-src overlay; the other two are one missing test import and one stale exact error-code expectation. Run3 command must keep image `/app`, expose current importer/zero-ledger and docs through narrow read-only `/review` mounts, set current source before image content in `PYTHONPATH`, use UID10001 and retain no-network/read-only/tmpfs boundaries. Two test-only edits await review; B001/B002 instances and DB/rebuild remain0.

D-1486 closes the run2 remediation review APPROVED 0/0/0. The exact two test-only fixes and `/review` mount design introduce no image, dependency, copy or framework. Runtime remains0 after edits. One full synthetic run3 under the reviewed boundary is the next explicit owner gate; B001/B002 instances and DB/rebuild remain0.

D-1487 records run3 at 162/166 PASS and the second equivalent four-error `content` environment cluster. Anti-loop pauses the task to the owner; run4 is forbidden until explicit resume. Static evidence corrects the image assumption: host `app` must be bound to `/app`, and package readers require sibling Django apps. Recommended light recovery is a reviewed standard readonly app bind plus tmpfs-only synthetic Django bootstrap; pure-reader refactor is larger and deferred. B001/B002 instances and DB/rebuild remain0.

D-1488 records owner resume for plan work only. Eight acceptance scenarios define the light run4 bootstrap: existing image, standard readonly app mount, current importer/docs precedence, two exclusive mode0600 synthetic credentials in tmpfs, isolated Django test profile and one inline `django.setup()+unittest` process. New files outside documentation, image/dependency/DB/pure-reader changes and runtime remain0. Independent review precedes any run4 permission.

D-1489 remediates first plan-review P1/P2/P3=1/1/1: writable exclusive credential creation now has exact post-close identity/mode/size proof; all12 module names and exact166 discovery guard are literal; `python3 -B` and no-bytecode environment are explicit. Architecture/scope unchanged, implementation/runtime0. Repeat review precedes any run4 permission.

D-1490 closes repeat plan review APPROVED 0/0/0. The lean inline bootstrap and standard readonly mounts satisfy RB3-RUN4-BOOT-001–008 without a launcher, settings module, image, dependency, DB or pure-reader refactor. Runtime remains0. One materially changed full synthetic run4 is the next explicit owner gate; B001/B002 instances and DB/rebuild remain0.

D-1491 records run4 exact166 at 163 PASS/3 ERROR. Bootstrap is closed; the three errors share one first-observed production adapter gap for approved MAP-044/MAP-049 empty legacy H1. Minimal page-name authority fallback is implemented only for empty `legacy_empty_main`, preserving source payload and strict target schema. Independent code review precedes any separately authorized run5; B001/B002 instances and DB/rebuild remain0.

D-1492 remediates the first H1 code-review P2 with one branch-local type/nonempty/edge-whitespace guard; global validator, source authority and architecture remain unchanged. Runtime0. Repeat review precedes any run5 permission; B001/B002 instances and DB/rebuild remain0.

D-1493 closes H1 code review APPROVED 0/0/0. The same12 suite gained exactly one focused test method, so successor run5 must guard exact167 while historical run4 exact166 remains correct. Count amendment review precedes any run5 permission; B001/B002 instances and DB/rebuild remain0.

D-1494 closes the successor-count review APPROVED 0/0/0. Production H1 fix, lean bootstrap and same12 exact167 guard are ready. Runtime remains0 after edits. One full synthetic run5 is the next explicit owner gate; B001/B002 instances and DB/rebuild remain0.

D-1495 records run5 exact167 at 165 PASS/2 FAIL. Both failures share one production home photo-strip omission. Minimal remediation prepends that approved asset to the existing works slot and requires full embedded coverage, preserving source29/736 and target30 authorities without a new slot/schema/layer. Independent code review precedes any run6; B001/B002 instances and DB/rebuild remain0.

D-1496 closes home-media code review APPROVED 0/0/0. One new focused method changes the same12 future run6 guard to exact168 while historical run5 exact167 remains correct. Count amendment review precedes any run6 permission; B001/B002 instances and DB/rebuild remain0.

D-1497 closes the exact168 amendment review APPROVED 0/0/0. Home-media fix, lean bootstrap and same12 exact168 guard are ready. Runtime remains0 after edits. One full synthetic run6 is the next explicit owner gate; B001/B002 instances and DB/rebuild remain0.

D-1498 closes `RB3-IMP-REGRESSION-001`: run6 PASS168/168 in4.989s, exit0, and independent result review ACCEPTED 0/0/0. H1 and home-media successor regressions pass with the full same12 cohort. Network/DB/persistent writes0; no repeat needed. B001/B002 instances remain0 and real capture/import/rebuild stays B002 storage-blocked.
