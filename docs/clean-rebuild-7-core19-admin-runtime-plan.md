# CORE-19 / RB7-ADMIN-RUNTIME-001 — сводная DB-backed приёмка admin runtime-хвостов

Итоговый статус: **CLOSED**. Единственный финальный owner-authorized confirmation: `CORE19_ADMIN_RUNTIME_OK tests=250 failures=0 errors=0 skips=0`; cleanup `containers=0 networks=0 volumes=0 staging=0`; independent final evidence review `APPROVED 0/0/0`.

Дата: 2026-11-25. Статус: plan/source/harness approved; runtime gate исчерпан. Новый owner-authorized run прошёл PostgreSQL boundary и остановился до app start/test DB/product execution на aggregate `CORE19_APP_BOUNDARY_MISMATCH`; cleanup exact0. Covered materially changed confirmation локализовала остановку до app start/test DB/product execution как `CORE19_APP_CAPABILITIES_MISMATCH`; cleanup exact0. Source-only probe доказал причину: PowerShell оборачивает корректный Docker `CapAdd: null` в массив с count1. Harness-only remediation считает только ненулевые capability-элементы; independent review APPROVED 0/0/0. Следующий отдельно разрешённый run прошёл обе container boundaries и остановился до app start/test DB/product execution на `CORE19_NETWORK_MEMBERSHIP_MISMATCH`; cleanup exact0. Source-only active-endpoint remediation прошла static checks и independent review APPROVED 0/0/0. Следующий отдельно разрешённый run дошёл до test runner и завершился `CORE19_TEST_RUNNER_FAILED`; cleanup exact0. Generic catch был безопасно разделён на семь runner stages; static checks и independent review APPROVED 0/0/0. Следующий отдельно разрешённый run локализовал unexpected exception как `CORE19_BOOTSTRAP_FAILED`, до check/discovery/test DB/suite; cleanup exact0. Bootstrap split прошёл static checks и independent review APPROVED 0/0/0. Следующий отдельно разрешённый run локализовал failure как `CORE19_DJANGO_SETUP_FAILED`; cleanup exact0. Closed exception classifier прошёл static checks и independent review APPROVED 0/0/0. Следующий отдельно разрешённый run доказал `CORE19_DJANGO_SETUP_MODULE_NOT_FOUND_FAILED`; cleanup exact0. Closed module-alias classifier прошёл static checks и independent review APPROVED 0/0/0. Следующий отдельно разрешённый run доказал `CORE19_DJANGO_SETUP_MODULE_NOT_FOUND_CONFIG_ROOT_FAILED`; cleanup exact0. Verified project-root import fix прошёл static checks и independent review APPROVED 0/0/0. Следующий отдельно разрешённый run прошёл bootstrap/check/migrations/discovery/test DB и выполнил suite, затем вернул aggregate `CORE19_SUITE_FAILED`; cleanup exact0. Closed suite-result classifier прошёл static checks и independent review APPROVED 0/0/0. Следующий отдельно разрешённый run доказал `CORE19_SUITE_ERRORS_MULTIPLE`; cleanup exact0. Multi-cohort safe-set прошёл static checks и independent review APPROVED 0/0/0. Следующий отдельно разрешённый run доказал exact error cohorts `L07_L21_L22`; cleanup exact0. Method-alias classifier прошёл static checks и independent review APPROVED 0/0/0. Следующий отдельно разрешённый run доказал `CORE19_SUITE_ERRORS_L21M001_L22M002_L22M004`; cleanup exact0, L07 не повторился. Closed error-type recorder прошёл static checks и independent review APPROVED 0/0/0. Следующий отдельно разрешённый run доказал `L21M001_INTEGRITY_ERROR` и `L22M002/L22M004_ATTRIBUTE_ERROR`; cleanup exact0. Three test-only fixes прошли static checks и independent review APPROVED 0/0/0. Следующий отдельно разрешённый run устранил прежние errors и вернул `CORE19_SUITE_FAILURES_UNMAPPED`; cleanup exact0. `_SubTest` parent mapping прошёл static checks и independent review APPROVED 0/0/0. Следующий отдельно разрешённый run доказал assertion failures `L03M024_L11M002_L12M009_L15M002_L29M004`; cleanup exact0. Assertion-line oracle exact64 cap прошёл repeat review APPROVED 0/0/0. Следующий отдельно разрешённый run локализовал lines `L03M024_N0673`, `L11M002_N0229`, `L12M009_N0266`, `L15M002_N0174`, `L29M004_N0176`; cleanup exact0. Four test-only stale expectations are remediated against later approved authority: Pages may import public `modules.media.api` but not models; SiteSettings source slice ends before adjacent public-logo projector; Audit checks injected `PRIVATE-DB`, not the approved constant word `PRIVATE`. Fifth finding is a product contract mismatch: `_validate_legacy_partner_url` accepts arbitrary HTTP although S2A requires strict HTTPS while D-023 preserves only six exact legacy HTTP URLs. Product fix is not started without a new owner decision. Runtime gate exhausted.

Test-only review уточнение: initial review четырёх stale assertions вернул P2 на string-only media-model guard. Первая AST remediation всё ещё пропускала relative imports и `from modules import media`; repeat review P2. Финальная remediation нормализует `ImportFrom.level/module` через `resolve_name` относительно `public_api.__package__`, раскрывает aliases parent imports `modules`/`modules.media` и оставляет единственный допустимый module `modules.media.api`; repeat review APPROVED 0/0/0.

Owner-authorized product remediation сохраняет ровно шесть D-023 legacy HTTP strings через immutable exact allowlist и отправляет любое другое значение в существующий strict `validate_https`. Все шесть исключений проверяются внутри существующего `test_http_editor` method, произвольный HTTP остаётся закрыт до command invocation; exact34 и общая exact250 арифметика не изменены. Independent security/source review APPROVED 0/0/0. Следующий шаг требует отдельного owner gate на один bounded Docker/PostgreSQL confirmation; текущий runtime gate исчерпан.

## 1. Цель и authority

Одним локальным disposable PostgreSQL package закрыть остающиеся runtime-ветки Page Reorder, Move, Delete, URL Change и minimal Audit, не повторяя owner-paused host TLS/RNG, PowerShell task-directory или Unix-socket/readiness paths. Source authority остаётся в независимо одобренных slice-планах:

- `clean-rebuild-4-page-reorder-run-plan.md`;
- `clean-rebuild-4-page-move-run-plan.md`;
- `clean-rebuild-4-page-delete-pg-run-plan.md`;
- `clean-rebuild-4-page-url-change-pg-run-plan.md`;
- `clean-rebuild-4-audit-minimal-plan.md`.

Этот package не меняет product contracts и не возобновляет прежние coordinators. Materially different transport переиспользует уже успешно доказанную CORE-18 boundary: один fresh internal Docker network, один fresh GUID-owned PostgreSQL data volume и два fresh containers; PostgreSQL TCP доступен только внутри internal network, host ports0, TLS/certificate/RNG/socket/task-directory0.

Не входят: browser/media bytes, fixture/import/production data, public preview, LEGAL/intake activation, Telegram, external network, VPS, deploy, cutover, live, scheduler и persistent apply.

## 2. Exact suite — 35 literal labels / 250 methods

Accepted base17 = exact172:

1. `modules.accounts.tests.test_http_auth` — 16;
2. `modules.pages.tests.test_http_list` — 9;
3. `modules.pages.tests.test_http_editor` — 34;
4. `modules.pages.tests.test_commands` — 13;
5. `modules.pages.tests.test_grants` — 10;
6. `modules.pages.tests.test_http_grants` — 8;
7. `modules.pages.tests.test_staff_lifecycle` — 13;
8. `modules.pages.tests.test_http_staff` — 8;
9. `modules.pages.tests.test_publication` — 8;
10. `modules.pages.tests.test_http_publication` — 7;
11. `modules.pages.tests.test_public_read` — 10;
12. `modules.pages.tests.test_legacy_plain_projection` — 10;
13. `modules.pages.tests.test_site_settings` — 4;
14. `modules.pages.tests.test_site_settings_commands` — 7;
15. `modules.pages.tests.test_http_site_settings` — 5;
16. `modules.pages.tests.test_rename` — 6;
17. `modules.pages.tests.test_http_rename` — 4.

Five accepted Page slices = exact60:

18. `modules.pages.tests.test_create` — 8;
19. `modules.pages.tests.test_http_create` — 4;
20. `modules.pages.tests.test_reorder` — 8;
21. `modules.pages.tests.test_http_reorder` — 4;
22. `modules.pages.tests.test_delete` — 8;
23. `modules.pages.tests.test_http_delete` — 4;
24. `modules.pages.tests.test_move` — 8;
25. `modules.pages.tests.test_http_move` — 4;
26. `modules.pages.tests.test_url_change` — 8;
27. `modules.pages.tests.test_http_url_change` — 4.

Shared and Audit = exact13:

28. `modules.pages.tests.test_contract` — 4;
29. `modules.audit.tests.test_http` — 4;
30. `modules.audit.tests.test_retention` — 5 after the test-only concurrency addition below.

Five exact named schema/importer assertions = exact5:

31. `fitness.test_rebuild3_schema.Rebuild3SchemaSourceTests.test_page_url_authority_field_matches_ordinary_add_field_migration`;
32. `rebuild3_importer.tests.test_runtime_target.TargetProjectionTests.test_literal_projection_verifies_before_single_commit`;
33. `rebuild3_importer.tests.test_runtime_target.TargetCommittedReadbackTests.test_exact_committed_projection_returns_closed_proof_once`;
34. `rebuild3_importer.tests.test_runtime_target.TargetCommittedReadbackTests.test_any_row_or_count_drift_fails_closed`;
35. `rebuild3_importer.tests.test_runtime_target.TargetMigrationRunnerTests.test_exact_leaves_generated_alias_and_cleanup`.

Arithmetic: `172 + 60 + 13 + 5 = 250`. Coordinator must statically verify every module method count, exact35 closed labels and guarded Django discovery `250` before test DB creation. Wildcards, broad module discovery, filtering, reordering, keepdb and retry are forbidden.

## 3. Audit concurrency test-first addition

Only one test method is added to `modules.audit.tests.test_retention`; product code is unchanged unless the required RED proves a real defect and a separately reviewed plan amendment is accepted.

The PostgreSQL-only test creates 10,001 valid rows strictly older than the fixed cutoff plus exact boundary and recent controls. It uses a deterministic test-only contention oracle around the existing `QuerySet._fetch_all` boundary; product code and SQL remain unchanged:

1. worker1 opens its independent connection, records its backend PID, invokes ordinary `cleanup_audit`, completes the real `SELECT … FOR UPDATE` fetch and then holds the still-open transaction on a bounded `threading.Event` before delete;
2. only after worker1 reports locks acquired, worker2 opens a separate connection, records its backend PID and enters the same real `SELECT … FOR UPDATE` fetch;
3. a third observer connection performs a bounded exact-count polling loop over `pg_stat_activity` for the recorded worker2 PID and must observe `wait_event_type='Lock'` while worker1 remains held;
4. only that observed PostgreSQL lock-wait releases worker1; both ordinary commands then finish and every connection closes.

The test patch is thread-identity scoped and activates only for the exact AuditEvent `select_for_update` queryset with limit5,000. Unknown query/thread/re-entry fails closed. Events have fixed timeouts; observer probes have both an exact maximum count and monotonic deadline. It emits no PID, SQL, wait value or query output. Sleep, advisory lock, product seam and production setting changes are forbidden.

Required terminal facts:

- both invocations succeed with constant bounded output;
- exact two disjoint batches delete 5,000 rows each;
- exactly one original old row remains;
- exactly two `AUDIT_RETENTION_BATCH` rows exist, each with count5,000, aggregate10,000;
- duplicate target deletion0 and duplicate aggregate event0;
- exact boundary and recent controls remain;
- no table outside Audit changes.

Thread exceptions are converted to fixed test assertions and never printed by the runtime harness. Each worker and observer closes its DB connection. The test has bounded Event waits, observer probes and join timeouts and fails closed on a live thread. The explicit observed `wait_event_type='Lock'` proves PostgreSQL row-lock contention before release; terminal state proves serialized disjoint deletion. No `skip_locked`, advisory lock, sleep, scheduler or product seam is introduced speculatively.

## 4. Disposable topology

The implementation reuses the reviewed successful shape of `scripts/test-core18-runtime.ps1`, but receives a new CORE-19 script/settings marker and independent source review:

- exact currently installed PostgreSQL/app image IDs are captured and validated as immutable `sha256:<64hex>`; pull/build/install0;
- fresh GUID run token owns exactly one internal network, one labeled local volume, one PostgreSQL container and one app test container without auto-remove;
- pre-audit requires no resource with the exact run label/name;
- PostgreSQL UID/GID999, read-only root, PGDATA only in the owned volume, bounded tmpfs, `cap-drop ALL` plus the exact foundation-required capabilities `CHOWN,DAC_OVERRIDE,FOWNER,SETGID,SETUID`, no-new-privileges, memory/CPU/PID limits and ports0;
- app UID/GID10001, read-only root/source/lock mounts, cap-drop ALL, no-new-privileges, bounded tmpfs/resources and ports0;
- network inspect must prove `Internal=true`; only the two recorded containers may attach; host port bindings and extra networks are forbidden;
- synthetic DB/user/password only, no host secret file, no existing foundation/source DB, no media mount and no external network;
- new settings profile requires exact `ESTAKADA_CORE19_SYNTHETIC_RUNTIME=1`, uses only the fresh PostgreSQL service, and does not enable service requests or any production feature.

This topology is materially different from every paused branch: host TLS/RNG/certificate leaves0, PowerShell task directory0, Unix socket/shared volume0, existing foundation DB0. It does not claim that old transports are repaired; it supersedes them only for the single CORE-19 acceptance result.

## 5. Execution and evidence

One future owner-authorized run performs:

1. source regular/non-reparse checks, exact method counts, parser/static checks, pinned image/name/label/pre-audit;
2. create and record exact owned volume/network/PostgreSQL/app identities; the app remains inspectable after exit until `finally`;
3. bounded PostgreSQL readiness, exact internal-network/ports/mount/capability/state inspection;
4. `manage.py check` and `makemigrations --check --dry-run`;
5. exact35 discovery must equal250 before Django creates the sole test DB;
6. run exact250 once through a recording Django runner; require `TestResult.testsRun=250`, failures/errors/skips/expected-failures/unexpected-successes0, pre/post `pg_database` absence for the exact test DB and app exit0;
7. emit `CORE19_ADMIN_RUNTIME_OK tests=250` only after all result checks;
8. mandatory `finally` removes only exact recorded app/PG container IDs, then revalidates exact run label/token before removing exact network and volume;
9. post-audit requires `containers=0 networks=0 volumes=0 staging=0` for the run scope.

Output is bounded to safe stage/result/count codes. It never emits raw traceback, assertion value, SQL, rows, Page names/URLs, UUIDs, passwords, environment, Docker inspect/log dumps, host paths or payloads. The child test output may be captured to a bounded temporary container-local file only; it is never persisted on host. On nonzero, only a closed safe stage plus validated aggregate failure/error counts may leave the container.

No automatic retry. Initial stop-before-product may use at most one materially changed confirmation only under the permanent AGENTS rule; otherwise every next runtime needs a new owner decision. Equivalent failure twice triggers anti-loop and no third attempt.

## 6. Acceptance

| ID | Required proof |
|---|---|
| `RB7-ADM-001` | exact35 labels, exact250 method arithmetic and discovery before test DB |
| `RB7-ADM-002` | Page Reorder/Move/Delete/URL exact12 cohorts all PASS on PostgreSQL |
| `RB7-ADM-003` | accepted base/create regressions PASS; migrations/check0 and URL schema/importer exact5 PASS |
| `RB7-ADM-004` | Audit HTTP/retention exact8 plus one PostgreSQL two-command method that observes worker2 `wait_event_type='Lock'` before release and then proves disjoint exact batches PASS |
| `RB7-ADM-005` | fresh synthetic-only internal-network topology; ports/TLS/socket/taskdir/media/external/live0 |
| `RB7-ADM-006` | recorded-ID cleanup and post-audit containers/networks/volumes/staging exact0 |
| `RB7-ADM-007` | safe bounded evidence and no secret/private/runtime payload disclosure |

`CORE-19` becomes CLOSED only after plan review, test/harness source review, one accepted exact250 runtime result, exact cleanup and final independent evidence review. This does not close `CORE-20` owner acceptance and does not authorize VPS/production/deploy.

## 7. Gates

1. Independent architecture/concurrency/destructive/runtime/no-bloat review of this plan.
2. After approval, tests-first concurrency addition plus CORE-19 settings/harness implementation.
3. Independent source/harness review and static checks.
4. Separate explicit owner permission for one bounded Docker/PostgreSQL exact250 run.
5. Independent final evidence review before `CORE-19 CLOSED` and percentage change.
