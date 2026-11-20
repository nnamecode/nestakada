# RB4 SiteSettings PostgreSQL gate

Дата: 2026-11-20. ID: `RB4-SITE-SETTINGS-PG-001`. Статус: **completed D-1741; exact162 ACCEPTED_PASS, server gate closed, temporary runner removed/absent, rerun0**.

## Purpose and exact suite

One disposable PostgreSQL run executes the closed `RB4-LEGACY-PLAIN-PG-001` exact146 regression plus the existing pure model module `modules.pages.tests.test_site_settings` exact4 and the new literal modules `modules.pages.tests.test_site_settings_commands` exact7 and `modules.pages.tests.test_http_site_settings` exact5, total exact162. A guarded ordinary Django runner must discover162 before database creation. Success requires migrations, system check0, `Ran 162 tests`, failures/errors/skips0, standalone `OK`, app exit0 and destruction of only `estakada_site_settings_test`.

The added exact16 prove the fixed core8 model/command/HTTP contract, full scalar logo usage coherence, bounded READY `SITE_ASSET` metadata-only projection1..64, transaction rollback and PostgreSQL one-winner locking. Browser/media-byte/storage/public-renderer evidence is not claimed.

## Disposable boundary

- Reuse only installed pinned PostgreSQL image `sha256:de3d5ee…b6eef7` and approved app/test image `sha256:782f53c…e39986`; pull/build/install0.
- Fresh fixed names `rb4-site-settings-pg`, `rb4-site-settings-tests`, `rb4-site-settings-net` and one fresh run label.
- Internal bridge, ports0, named volumes0, Docker socket0; PostgreSQL data/socket/tmp and app tmp are tmpfs.
- Synthetic TLS certificate exact for the PostgreSQL container name; synthetic base `estakada_site_settings_base`, test DB `estakada_site_settings_test`, real/imported data0.
- PostgreSQL and app use read-only roots, dropped capabilities/no-new-privileges and bounded CPU/memory/PID limits. App runs UID10001 with exact current `src` mounted read-only.
- Fixed labels only; wildcard discovery, source copy, keepdb, filtering, retry and fallback0. Exact scoped-origin preflight checks nine fixed regular non-reparse files before Docker object creation.

## Evidence, cleanup and stop rule

Evidence is bounded to images2, names3, network/ports0, readiness<=30, origins9, discovery162, migrations/check, exact `Ran 162 tests` and `OK`, app exit state and cleanup. Raw environment, secrets, certificate key, full inspect and Docker IDs are not printed.

The coordinator records nullable object IDs, removes only identity-checked recorded app/PG containers and recorded endpoints0 network, removes the exact certificate-store leaf and a verified task directory below `work`. Any first runtime/coordinator/product error stops; no automatic retry or alternate boundary. Product source is frozen during the run. Model/migration/dependency/image/permanent-runner changes0; live/deploy/push remain closed.

Owner authorization was explicitly supplied for this SiteSettings Docker check. Execution begins only after independent plan/coordinator approval; a failed run consumes this authorization and requires result triage before any repeat.

Independent review found P1/P2=`1/1`: the success oracle accepted `OK (skipped=...)`, and the checked app exit state lacked a bounded evidence marker. The runner now requires standalone CR-tolerant `OK`, rejects all skip/expected-failure/unexpected-success summaries, and emits only the fixed checked exit/OOM/dead marker. Repeat review is `APPROVED`, P0/P1/P2=`0/0/0`, product findings0, privacy/cleanup/no-bloat/anti-loop PASS at exact runner SHA256 `D284B62E5EE90C128B1DBEA55454001C541D3CC84B57C5B18F8BC439E0DDFD81`.

## Run1 coordinator result and remediation

Owner-authorized run1 passed images2 and scoped origins9, then the network-create result was collapsed to the first character by the coordinator's PowerShell property/index expression. It stopped before the network marker, PostgreSQL, database creation, discovery or tests. The same latent defect affected future PG/app ID capture. Cleanup then reported one error and masked the primary identity error; post-run audit found containers0/task-directories0/certificates0 plus one exact internal endpoints0 labelled network. After a bounded JSON identity check that network was removed and networks_remaining0. Product run0, product findings0, retry0.

Independent triage is `ACCEPTED_FAIL / CHANGES_REQUESTED`, P0/P1/P2=`0/2/1`, privacy/anti-loop PASS. The bounded coordinator remediation records the sole 64-hex candidate into each nullable network/PG/app ID before enforcing exact one-line output; preserves and rethrows the primary ErrorRecord after cleanup; and emits only fixed cleanup failure categories. Suite, images, TLS, permissions, tests and product sources are unchanged. A new SHA, syntax/diff check, repeat independent review and fresh explicit owner permission are mandatory before run2.

Repeat static review is `APPROVED`, P0/P1/P2=`0/0/0`, product findings0, privacy/cleanup/no-bloat/anti-loop PASS. PowerShell syntax and diff checks pass; exact leftovers are containers0/networks0. Approved runner SHA256 is `E3D54241FD92C1AE5700C71328CCECE912CA123D2C24A5D8B3047DDB091C8F08`. Run2 may execute only after a new explicit owner permission; run1 authority is not reusable.

## Run2 app-bootstrap result and remediation

Freshly authorized run2 passed images2, origins9, internal network/ports0 and PostgreSQL readiness4. The app then exited before discovery because it executed `/run/runner.py`; Python set `sys.path[0]` to `/run`, so the already mounted read-only `/app/config` was not importable despite workdir `/app`. Exact failure was `ModuleNotFoundError: config`. Discovery0, test DB0, tests0, product findings0. Automatic cleanup reported0 and the post-run audit confirmed containers/networks/task-directories/certificates0; retry0.

Independent triage is `ACCEPTED_FAIL / CHANGES_REQUESTED`, P0/P1/P2=`0/1/0`, with privacy/cleanup/anti-loop PASS. The sole remediation adds fixed `PYTHONPATH=/app` to the app container, explicitly binding imports to the existing approved read-only source mount. Runner code, exact162 labels/guard, PostgreSQL/TLS and cleanup are unchanged. A new SHA, syntax/diff check, repeat independent review and fresh explicit owner permission are mandatory before run3.

Repeat static review is `APPROVED`, P0/P1/P2=`0/0/0`, product findings0, privacy/cleanup/no-bloat/anti-loop PASS. Exactly one fixed `PYTHONPATH=/app` was added; no second `sys.path` mechanism exists. PowerShell syntax/diff checks pass and the approved runner SHA256 is `19AE94F23AB0CF81BCD03BBBDD668A9117359ADE4F0DCC9A90CFEB6D71D705B5`. Run3 requires a fresh explicit owner permission.

## Run3 product result and remediation

Freshly authorized run3 passed images2, origins9, internal network/ports0, PostgreSQL readiness4, exact discovery162, migrations and system check0. It ran all162 in80.234s and destroyed only `estakada_site_settings_test`; result was155 pass with failures5/errors2, all in the new SiteSettings modules. Cleanup0 and post-run leftovers containers/networks/task-directories/certificates0.

Independent triage is `ACCEPTED_FAIL / CHANGES_REQUESTED`, P0/P1/P2=`0/1/1`, product findings1 and test findings1. The product cause is that a newly constructed candidate with an existing PK still had `_state.adding=True`, so full unique validation treated every valid update as a second singleton and returned `INVALID_SETTINGS`; this explains six related symptoms including HTTP and concurrency. The test-only cause is a broad employee assertion that mistook the private shell's legal logout form for an edit form.

The bounded remediation validates the already locked persisted SiteSettings instance after in-memory core assignment, preserving full unique/schema validation before media/DB mutation and retaining the captured old logo ID for the later replacement. The HTTP test now checks absence of the three SiteSettings form controls rather than all forms. Private Django state hacks, disabled unique validation, new methods and scope expansion0. Independent code review and a fresh owner permission are required before another full exact162 run; no partial/diagnostic run is proposed.

Independent remediation review is `APPROVED`, P0/P1/P2=`0/0/0`, product findings0 and test findings0. It confirms persisted-instance validation at `_state.adding=False`, mutation ordering, gated preservation and exact12 coverage; privacy/DAG/no-bloat/anti-loop PASS. Runner remains byte-unchanged at SHA256 `19AE94F23AB0CF81BCD03BBBDD668A9117359ADE4F0DCC9A90CFEB6D71D705B5`. A fresh owner permission is required for the next complete exact162 run.

## Run4 product-pass/test-oracle result

Freshly authorized run4 again passed images2, origins9, internal network/ports0, PostgreSQL readiness4, exact discovery162, migrations and system check0. It ran all162 in99.933s, destroyed the test DB and cleaned up with exact leftovers0. All prior146, model4, command7 and four of five SiteSettings HTTP tests passed; the sole failure expected unsupported PUT `405` but sent it without CSRF, so Django's earlier `CsrfViewMiddleware` correctly returned403 before `require_http_methods`.

Independent triage is `ACCEPTED_FAIL / CHANGES_REQUESTED`, P0/P1/P2=`0/0/1`, product findings0, test findings1, privacy/cleanup/anti-loop PASS. The one-line remediation supplies the already obtained CSRF token as `HTTP_X_CSRFTOKEN` only on the PUT assertion, allowing it to reach the exact405/Allow boundary while the separate tokenless POST continues to prove CSRF403 and command0. Product code, test methods/count, runner and runtime boundary are unchanged. Independent test-remediation review and fresh owner permission are required before another full exact162 gate.

Independent test-remediation review is `APPROVED`, P0/P1/P2=`0/0/0`, product findings0, test findings0, privacy/no-bloat/anti-loop PASS. Exact12 and runner SHA256 `19AE94F23AB0CF81BCD03BBBDD668A9117359ADE4F0DCC9A90CFEB6D71D705B5` remain unchanged. A fresh owner permission is required for the next full exact162 run.

## Run5 accepted pass

Freshly authorized run5 passed the complete boundary: images2, origins9, internal network/ports0, PostgreSQL readiness4, exact discovery162, migrations and system check0. Prior146 and SiteSettings16 passed; Django reported `Ran 162 tests in 103.249s` and standalone `OK`, with no skips, expected failures or unexpected successes. It destroyed only `estakada_site_settings_test`. App exit0/OOM0/dead0, `PASS162`, cleanup0 and post-run containers/networks/task-directories/certificates0 were confirmed.

Independent final result review is `ACCEPTED_PASS`, P0/P1/P2=`0/0/0`, product findings0, privacy/cleanup/no-bloat/anti-loop PASS. Server gate is CLOSED and rerun0. Conservative WBS is48–50%, remaining6/13/27 productive hours. After documentation records this evidence and exact SHA `19AE94F23AB0CF81BCD03BBBDD668A9117359ADE4F0DCC9A90CFEB6D71D705B5`, the temporary coordinator is removed; permanent runner0. Browser, media bytes/storage, public Header/Footer renderer, B002, live/deploy and push remain separately closed.

D-1740 cleanup note: the exact temporary coordinator still exists with the recorded SHA. Two `apply_patch` deletion attempts returned the same file-delete failure; anti-loop prohibited a third equivalent action or an unapproved switch to shell deletion. Cleanup is paused to the owner for one decision: authorize exact `Remove-Item -LiteralPath` for this single verified file, or explicitly retain it. The accepted server result and Docker leftovers0 are unchanged.

D-1741 cleanup closure: the owner authorized exact-file shell deletion. Exact path and SHA were rechecked; the first sandboxed `Remove-Item` was denied without mutation, and the same command under explicitly approved access removed only the verified file. `RUNNER_EXISTS=False`, permanent runner artifact0 and Docker leftovers0. D-1739 accepted result, rerun0 and conservative WBS remain unchanged.
