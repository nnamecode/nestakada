# REBUILD-1: baseline preflight evidence

Дата: 2026-11-17. Статус: **D-1358 ephemeral verifier review P1=3; docs remediation pending; REBUILD-1 incomplete**.

Основание: D-1251 открыл только ограниченный read-only REBUILD-1. Этот документ фиксирует статические authority-файлы, уже находящиеся в репозитории. Он не является migration snapshot, public manifest или `transfer-limits` и не разрешает product code, dependencies, migrations, target DB/media, importer, runtime, Docker, cutover, live/deploy или destructive actions.

## 1. Граница среза

Проверены только:

- canonical route map `docs/analytics-route-map.csv`;
- visual authority `docs/design/public-light-v4-template.html`;
- утверждённый content contract `docs/clean-rebuild-content-contract.md`;
- ровно 12 migration JSON в `app/content` и их существующий SHA-256 oracle `app/content/test_test08_execution.py::PACKAGE_SHA256`.

Не открывались source DB, private rows, Docker/runtime и media bytes. JSON payload не выводился и не переносился. Для среза действовали exact equality limits без headroom: 12 JSON, 827343 bytes суммарно, maximum single JSON 318359 bytes; route map — 115 rows и 121766 bytes. Эти числа защищают только повтор этой статической проверки и не подменяют будущие frozen `transfer-limits` из DB/media baseline.

## 2. Проверенные факты

| ID | Проверка | Результат |
|---|---|---|
| `RB1-STATIC-AC-001` | Route map имеет literal `MAP-001..MAP-115`, без missing/extra/duplicate IDs | PASS: 115/115, missing0, extra0 |
| `RB1-STATIC-AC-002` | Exact `requested_path` уникальны, `proposed_type` заполнен | PASS: paths115/115, blank types0 |
| `RB1-STATIC-AC-003` | Число transport outcome types совпадает с content contract | PASS: 20 |
| `RB1-STATIC-AC-004` | Package allowlist содержит ровно 12 JSON | PASS: dev09×10 + dev10×1 + dev12×1 |
| `RB1-STATIC-AC-005` | SHA-256 каждого JSON и route map совпадает с existing `PACKAGE_SHA256` oracle | PASS: 13/13 |
| `RB1-STATIC-AC-006` | Approved visual/content authorities имеют фиксируемые bytes и SHA-256 | PASS; digests ниже |

## 3. Authority digests

| Файл | Bytes | SHA-256 |
|---|---:|---|
| `docs/analytics-route-map.csv` | 121766 | `c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8` |
| `docs/design/public-light-v4-template.html` | 96432 | `998395a398f698287b6276794b95cb2b626f34dd353a908bb5ba87dc2a65e4e9` |
| `docs/clean-rebuild-content-contract.md` | 20227 | `663dbe232d56dd18ba7f6347173db0cbe72c5962b0ac26166f5d8f81ed68d7d8` |

| Migration JSON | Bytes | SHA-256 |
|---|---:|---|
| `dev09b_articles_slice.json` | 60804 | `2936561288256d42968363afe90147678aa6fc88bbdff9faf21fde1c2d986639` |
| `dev09e_services_catalog.json` | 10292 | `beffdfdbacc6a24a71c68ee692f03be262f67745b8425e1ce9b204b8d15ca9e9` |
| `dev09g_service_roots.json` | 5147 | `956c35fb5697acb23b039a980d1915228bd1100f1884ebece3fcd909ace365db` |
| `dev09h_service_details.json` | 55726 | `439dea21aa4257e934e0781faec982bb05157d5a734171ced58086df4e8bd52a` |
| `dev09i_planned_maintenance.json` | 43706 | `fa0e85ba9640ffa45916e810bece20e949698b3dbe82f9ead99750210b98a5cf` |
| `dev09j_leading_price_details.json` | 35299 | `e091047ae5272fa9834d828d5ed73e1fbc914a41faa07e4367b9787ad0a8934d` |
| `dev09k_diagnostics_branch.json` | 43141 | `9980c60a1a2ee354ef156c7f9695cfc76ec051f798dfe3610a95f3e29c473e67` |
| `dev09m_combined_services.json` | 318359 | `3fb682d6a092d78439fa45b541668554d793490b41eb89d311359738053f8e01` |
| `dev09m_infographic_map019.json` | 1453 | `fe083d206a72a3850bb30a554e57d375eba3338aacd87842c6c17f99a0f34954` |
| `dev09n_remaining_content.json` | 24799 | `a47eb0118dd04ede21eebd995e870ddbf3d0895f7ad9e17f806b27babdccf3ed` |
| `dev10_gallery.json` | 187260 | `9db5b026d6affa4668e2ca19268d8663355c1e22504f6aba6aa1676ed3d41b3b` |
| `dev12_home_profile.json` | 41357 | `c12caba76e429ac11496b0a299f61919f7c8a1c200f494acb99e08baff9d4d56` |

## 4. Static authority вывод

Статические независимые oracles не конфликтуют: route map и 12 JSON совпали с существующими digests; visual authority и content contract зафиксированы как baseline candidates. No-bloat check: добавлен один evidence-документ; нового scanner/validator/service/registry/task tracker нет.

## 5. Source-DB identity preflight

Repository evidence показывает только две фактические application identities:

- `app_runtime` имеет `SELECT, INSERT, UPDATE, DELETE` на application tables;
- `app_migrator` владеет schema и выполняет migrations.

Ни одна не является отдельной least-privilege source reader. `SET TRANSACTION READ ONLY` и `PGOPTIONS=-c default_transaction_read_only=on` уже используются как полезные предохранители, но не превращают write-capable identity в отдельную read-only identity. До подключения требуется одна временная роль `estakada_rebuild_reader`: `LOGIN`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOINHERIT`, `NOREPLICATION`, `NOBYPASSRLS`, connection limit1, database `CONNECT`, schema `USAGE`, `SELECT` только на literal allowlist ниже; `default_transaction_read_only=on`, search path `pg_catalog,app`. Secret — exact bytes в защищённом host-private regular file, переданные через stdin в exact container tmpfs regular file; не Git/argv/output.

### 5.1. Fresh-only creation и effective privileges

Один privileged bounded controller до чтения source rows обязан:

1. проверить exact database/schema и отсутствие role name `estakada_rebuild_reader`; существующая роль любого состояния означает fail closed, без ALTER/reuse/drop;
2. создать роль только для этого DBPRE run с `VALID UNTIL = trusted database time + 15 minutes`; whole DBPRE остаётся≤30s;
3. доказать zero `pg_auth_members` rows, где reader является member **или** granted role; reader не владеет database/schema/table/sequence;
4. доказать effective privilege matrix: только `CONNECT` к exact source DB, `USAGE` schema `app`, `SELECT` на exact14 tables; database `CREATE|TEMP`, schema `CREATE`, table `INSERT|UPDATE|DELETE|TRUNCATE|REFERENCES|TRIGGER`, любые sequence privileges и любые privileges на прочие non-system tables — false;
5. только после matrix открыть reader TLS connection. Любая PUBLIC/membership/ownership leakage, unexpected object или privilege блокирует run; controller не пытается «починить» существующую роль.

`NOINHERIT` здесь только дополнительный flag: безопасность `SET ROLE` доказывает именно zero membership в обе стороны. Controller хранит role OID и credential path только в private memory; они не входят в result/log.

### 5.2. Mandatory lifecycle и cleanup

Один обязательный `finally` выполняется после success и любого normal failure:

1. закрыть единственную reader connection;
2. через privileged controller сверить exact role name+OID; при совпадении немедленно поставить `NOLOGIN`, затем потребовать active reader sessions0;
3. отозвать только literal CONNECT/USAGE/14 SELECT grants; broad `DROP OWNED`, wildcard и cleanup чужих объектов запрещены;
4. drop разрешён только если name+OID, flags, memberships0, ownership0 и effective privilege state всё ещё соответствуют этому run;
5. удалить exact container tmpfs secret/passfile и exact fresh host-private secret regular file; доказать role absent + secret absent.

Если identity/OID/state неоднозначны, role не переиспользуется и не удаляется догадкой: при доступном exact OID она остаётся `NOLOGIN` с отозванными literal grants; secret удаляется; результат fail closed и требует owner inspection. Если privileged cleanup недоступен, evidence недействительно, credential всё равно истекает не позднее 15 минут, а следующий run откажется из-за существующего role name. Никакого retry с stronger role или автоматического stale-role repair нет.

Исторически на D-1253 создание/изменение роли и чтение ещё не выполнялись. Фактический D-1306 preflight затем создал JIT role, прочитал только утверждённые aggregate facts из literal14 tables и завершил exact cleanup; raw/private rows не выводились.

## 6. Literal table и aggregate allowlist

Reader получает `SELECT` ровно на 14 source tables:

| Cohort | Literal tables | Разрешённый privacy-safe output |
|---|---|---|
| page/route | `content_page`, `content_route` | total/group counts, published/kind/legacy counts, structural anomaly counts |
| current/previous | `page_versions_pagerevision`, `page_versions_pagecontentstate` | counts, schema/kind groups, payload byte sum/max, missing/mismatched current/predecessor counts |
| shared | `shared_content_sharedblock`, `shared_content_sharedrevision` | counts, kind/storage groups, inline/file byte sum/max, current anomaly counts |
| media metadata | `media_library_mediafolder`, `media_library_pagemediahome`, `media_library_asset`, `media_library_assetfile`, `media_library_assetusage` | counts/status/kind groups, declared byte sum/max, orphan/usage anomaly counts; no file bytes |
| staff/grants | `auth_user`, `accounts_userprofile`, `accounts_pagegrant` | only total/active/role/grant-flag counts and orphan counts; no ID, username, name, email, password hash or row |

Explicitly отсутствуют в grant/query set: `service_requests_*` до отдельного LEGAL+owner permission; audit, sessions, login throttle/resource state; drafts, stages, receipts, protection/pins, reservations, cleanup/budget; `django_migrations`; любые неизвестные/new tables. Расширение требует нового reviewed allowlist, а не wildcard/introspection fallback.

## 7. Query и output envelope

- one TLS connection; before subject tables prove expected database/role booleans, TLS, `transaction_read_only=on`, isolation `repeatable read`;
- one explicit `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY`; fixed literal parameterized `SELECT` statements only, no ORM/source-runtime import/dynamic identifier;
- connect timeout5s, statement timeout2s, lock timeout250ms, idle-in-transaction timeout5s, whole preflight30s, result≤64KiB;
- stdout/result contains only contract version, query IDs, booleans, counts, byte totals/maxima and error code; no host/path/SQL/raw exception/row/private value;
- any missing table/column, privilege/identity/TLS/timeout/anomaly/cap mismatch closes connection and returns constant failure; no retry with stronger role.

- `RB1-DBPRE-AC-001`: `app_runtime`, `app_migrator` и pre-existing reader role rejected; reader создаётся fresh с exact flags, connection1 и DB-time+15m validity.
- `RB1-DBPRE-AC-002`: membership both directions0, DB/schema/table/sequence ownership0; name+OID remain bound to one run.
- `RB1-DBPRE-AC-003`: effective privileges are exactly CONNECT/USAGE/14 SELECT; all listed write/create/temp/sequence/other-table privileges false, including PUBLIC leakage.
- `RB1-DBPRE-AC-004`: subject reads use one TLS `REPEATABLE READ READ ONLY` transaction and fixed parameterized SELECT only.
- `RB1-DBPRE-AC-005`: excluded/unknown tables stay denied; no wildcard/introspection fallback or stronger-role retry.
- `RB1-DBPRE-AC-006`: output≤64KiB contains only contract/query IDs, booleans, counts, byte totals/maxima and constant error code; no private/raw/SQL/path/error value.
- `RB1-DBPRE-AC-007`: success and normal failure run exact `finally`: close→OID check→NOLOGIN→sessions0→literal revoke→conditional drop→exact secret deletion; role+secret absent on clean completion.
- `RB1-DBPRE-AC-008`: cleanup ambiguity never guesses/reuses/drops; exact role is left NOLOGIN/revoked where provable, secret removed, validity≤15m, evidence invalid and owner inspection required.

## 8. Source staff key → target UUID conflict

Static models reveal source `auth_user.id` is numeric, while clean target User has UUID PK. Transfer wording “staff UUID” therefore cannot describe a source field. Minimal candidate correction: during a disposable REBUILD-3 run, importer reads source numeric staff key only inside the private stream, creates one fresh target UUID per staff row, and retains an exact source-key→target-UUID map only in process memory until target commit/rollback. The same map binds PageGrant and allowed current/previous provenance. Missing/duplicate/unmapped source key blocks the run. Map, source key and private values never enter public manifest, files, argv/stdout/stderr/audit/logs; failed run loses map with its disposable target. No identity service, deterministic-ID scheme or mapping table is created.

### 8.1. Exact mappability aggregate set

В той же `REPEATABLE READ READ ONLY` transaction fixed queries сначала строят только внутренние CTE, не rows output:

- `selected_current`: exact `PageContentState.current_revision` joined к revision той же Page, kind `initial|automatic`, при отсутствии более новой current-capable sequence;
- `selected_previous`: для каждого valid current одна revision той же Page с maximum `sequence < current.sequence` среди kind `initial|automatic`, либо null;
- `staff_candidate`: union source user keys, которые имеют UserProfile, PageGrant, `is_staff|is_superuser`, либо являются author выбранного current/previous;
- `valid_staff`: candidate с существующей `auth_user` row и ровно одним UserProfile role `owner|employee`.

Output содержит только пять query IDs и integer counts; все обязаны быть zero:

| Query ID | Zero-count condition |
|---|---|
| `DBPRE-MAP-001` | selected current имеет null/nonpositive `author_id` либо author отсутствует в `valid_staff` |
| `DBPRE-MAP-002` | selected non-null previous имеет null/nonpositive `author_id` либо author отсутствует в `valid_staff` |
| `DBPRE-MAP-003` | `staff_candidate` не имеет ровно одной existing auth row + valid `owner|employee` profile |
| `DBPRE-MAP-004` | PageGrant user отсутствует в `valid_staff` |
| `DBPRE-MAP-005` | PageGrant page отсутствует в `content_page` |

Query не выводит source key, username, role, page/revision UUID или иной row value. Missing current/previous structural integrity остаётся отдельным уже заявленным anomaly count и также блокирует PASS; mappability не маскирует его inner join. Те же14 tables достаточны, grant/role/read lifecycle не расширяются.

`RB1-REV-P2-001` remediation candidate подготовлен: selected provenance, staff и grants обязаны быть полностью mappable до freeze/target creation. Он не разрешает target creation и не создаёт reconciliation/mapping subsystem.

## 9. Итог и следующий gate

Runtime evidence `RB1-DBPRE-PASS-001` (D-1306) теперь подтверждает contract `rb1-dbpre-v1`: source `foundation-dev`, ровно29 allowlisted aggregate facts, elapsed522ms, `DBPRE-MAP-001..005=0` и три structural anomaly facts=0. Cleanup завершён до PASS; containers0 и actual host secret0. Raw/private row values не выводились. До принятия evidence требуется независимое read-only result review; повторный DBPRE не нужен.

Repeat review `RB1-DBPRE-REVIEW-002` D-1257 дал APPROVED P1/P2/P3=0/0/0: оба findings CLOSED, mechanics8/5/14/14 и no-bloat PASS. D-1258 owner одобрил exact temporary reader boundary, но не actual subject-table read.

Read-only inventory до mutation установил: running containers0; preserved dev/test volumes; test containers `Exited 255`; test manifest stale `active=true`. D-1173 фиксирует fresh **dev** load как актуальный наполненный local source — pages112/routes115/assets238/requests0; test является тестовым контуром. Поэтому test DB не выбирается source authority и full foundation wrapper не запускается.

Исторически D-1259 остановил execution с P1=2/P2=2, а D-1260/D-1261 начали remediation one-connection/snapshot и exact cleanup proof. Последующие remediation/reviews закрыли эти findings; owner-gated D-1306 runner PASS подтверждает 29 aggregate facts и final cleanup. App/ingress/media-worker, media inventory, exporter, target DB, WBS, Q002 и product code остаются за пределами этого evidence.

## 10. Media baseline scope candidate

`RB1-MEDIA-SCOPE-001` D-1310 переиспользует DEV-10 package и `analytics-media-evidence.csv`: candidate exact301/56134441/max656254 = exact214 gallery originals +87 ordinary approved assets. Gallery package↔CSV tuples diff0, albums17/photos214, position base0/gaps0. Unused variants16/3318200 и historical HTTP404 rows2 исключены. Physical media tree не является allowlist; DB AssetFile238 не приравнивается к files301 без binding evidence. Проверены только registry/filesystem metadata; media bytes/SHA не пересчитывались. Scope требует independent review до отдельного bounded exact301 hash gate.

`RB1-MEDIA-HASH-001` D-1312 одним read-only pass пересчитал bytes/SHA exact301: total301/56134441, gallery214/41176391, ordinary87/14958050, mismatch0. Новый scanner/manifest не создан, per-file values не выводились. Result требует independent review; DB AssetFile238 path/usage binding и остальные REBUILD-1 gates не закрыты.
