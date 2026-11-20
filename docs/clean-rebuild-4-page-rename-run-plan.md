# RB4 Page rename PostgreSQL gate

Дата: 2026-11-20. ID: `RB4-PAGE-RENAME-PG-001`. Статус: **D-1752 coordinator APPROVED P0/P1/P2=0/0/0 at SHA256 `C76DBAC65EFF9B7C17F86027D7C8BECEBD72792DB8356BC362D35DC176CBD6D0`; syntax/privacy/cleanup/no-bloat PASS; Docker/runtime0; fresh explicit owner permission required for one run**.

## Purpose and exact suite

Один disposable PostgreSQL run выполняет принятый SiteSettings exact162 regression и два новых literal modules Page rename exact10, всего exact172. Полный закрытый список из17 labels:

- `modules.accounts.tests.test_http_auth` —16;
- `modules.pages.tests.test_http_list` —9;
- `modules.pages.tests.test_http_editor` —34;
- `modules.pages.tests.test_commands` —13;
- `modules.pages.tests.test_grants` —10;
- `modules.pages.tests.test_http_grants` —8;
- `modules.pages.tests.test_staff_lifecycle` —13;
- `modules.pages.tests.test_http_staff` —8;
- `modules.pages.tests.test_publication` —8;
- `modules.pages.tests.test_http_publication` —7;
- `modules.pages.tests.test_public_read` —10;
- `modules.pages.tests.test_legacy_plain_projection` —10;
- `modules.pages.tests.test_site_settings` —4;
- `modules.pages.tests.test_site_settings_commands` —7;
- `modules.pages.tests.test_http_site_settings` —5;
- `modules.pages.tests.test_rename` —6;
- `modules.pages.tests.test_http_rename` —4.

Guarded ordinary Django5.2 runner обязан получить discovery exact172 до создания test DB. Success требует migrations applied, system check0, одной CR-tolerant timing-shaped строки `Ran 172 tests in <decimal>s`, отдельной standalone CR-tolerant строки `OK`, failures/errors/skips/expected-failures/unexpected-successes0, уничтожение только `estakada_page_rename_test`, app exit0/OOM0/dead0/`State.Error==""` и bounded marker `PASS172`.

Новые exact10 доказывают owner-only name validation/CAS/audit/rollback, command и GET↔rename PostgreSQL lock coherence, fixed private HTTP/CSRF/405/body cap/cache/no-reflection. Browser не нужен для fixed no-JavaScript form; public Route/renderer/navigation/media evidence не заявляется.

## Reused disposable boundary

Переиспользуется только независимо принятая финальная SiteSettings boundary по условиям, но не её удалённый runner и не прежнее разрешение:

- только уже установленные pinned PostgreSQL image `sha256:de3d5ee…b6eef7` и app/test image `sha256:782f53c…e39986`; pull/build/install0;
- fresh exact names `rb4-page-rename-pg`, `rb4-page-rename-tests`, `rb4-page-rename-net`, fresh label `nestakada.run=rb4-page-rename-pg-001-<uuid>`;
- internal bridge, ports0, named volumes0, Docker socket0; PostgreSQL data/socket/tmp и app tmp только tmpfs;
- synthetic TLS certificate только для exact PostgreSQL container name; synthetic base `estakada_page_rename_base`, test DB `estakada_page_rename_test`, real/imported data0;
- PostgreSQL/app readonly roots, cap-drop ALL, no-new-privileges, bounded CPU/memory/PID; app UID10001 и exact current `src` read-only;
- fixed labels only; wildcard discovery/source copy/filter/reorder/keepdb/retry/fallback0; `PYTHONPATH=/app` сохраняется.

Current-slice preflight до первого Docker object проверяет exact9 literal regular non-reparse source origins:

1. `src/config/urls.py`;
2. `src/modules/accounts/middleware.py`;
3. `src/modules/pages/commands.py`;
4. `src/modules/pages/web.py`;
5. `src/modules/pages/templates/pages/page_editor.html`;
6. `src/modules/pages/templates/pages/page_rename.html`;
7. `src/modules/pages/templates/pages/page_rename_conflict.html`;
8. `src/modules/pages/tests/test_rename.py`;
9. `src/modules/pages/tests/test_http_rename.py`.

Marker — только `RB4_PAGE_RENAME_ORIGINS_OK=9`. Coordinator дополнительно проверяет, что новые два literal modules дают ровно6+4 методов статически и guarded discovery остаётся authoritative172.

## Coordinator and evidence contract

Временный host coordinator создаётся только после одобрения этого плана. Он должен быть self-contained PowerShell, exact-SHA reviewed и удалён после independently accepted terminal result. Permanent runner artifact0.

Он переиспользует принятые границы SiteSettings run5:

- для каждого network/PG/app create output coordinator сначала находит единственный 64-hex candidate и немедленно записывает его по ссылке в nullable recorded ID, затем отдельно требует, чтобы весь output был ровно одной64hex строкой; поэтому warning/format rejection не может предшествовать identity-safe recording. Cleanup никогда не использует name fallback;
- PowerShell сохраняет global ErrorActionPreference, только один bounded `docker logs --tail 600 ... 2>&1` выполняет с local Continue, `$LASTEXITCODE` захватывается до finally, preference всегда восстанавливается; null/nonzero log exit fail closed;
- bounded output: origins9, images2, names3, internal network/ports0, PG tmpfs3/raw `Mounts=[]`/readiness≤30, app readonly-source/ports0, discovery172, migrations/check0, exact timing-shaped `Ran 172 tests in <decimal>s`, standalone `OK`, checked app marker `exit0/OOM0/dead0/error-empty` (только boolean empty proof, без raw `State.Error`), `PASS172`, cleanup categories0;
- запрещён вывод raw Env, secrets, certificate private key, passwords, full inspect, Docker IDs, paths, test payloads/names и unbounded logs;
- success parser отвергает skip/expected-failure/unexpected-success summaries и требует CR-tolerant standalone `OK`;
- source/test frozen на время run; model/migration/dependency/image/permanent artifact changes0.

Один `finally` recheck-ит exact recorded ID/name/run-label, останавливает только running recorded containers, удаляет app/PG по recorded IDs, доказывает их отсутствие, удаляет только recorded endpoints0 network, exact certificate leaf и verified task directory под `work`. Cleanup error не маскирует сохранённый primary ErrorRecord; выводятся только fixed cleanup failure categories.

## Stop rule and authorization

Любая первая coordinator/product/test/cleanup ошибка останавливает run для независимого result triage. Automatic retry, partial diagnostic container, alternate suite, fallback и повтор того же действия0. Failed run consumes permission; новый run возможен только после triage, materially changed reviewed condition и fresh explicit owner permission.

Этот документ не разрешает Docker. После independent plan review требуется отдельно подготовить и независимо проверить exact temporary coordinator. Только затем владелец может явно разрешить ровно один full exact172 run. Browser, media bytes/storage, live/deploy/push остаются закрыты.
