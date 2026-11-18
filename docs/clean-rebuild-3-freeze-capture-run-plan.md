# REBUILD-3 — bounded production freeze capture entrypoint

Дата: 2026-11-18. ID: `RB3-FREEZE-CAPTURE-RUN-001`. Статус: **PLAN+CODE APPROVED 0/0/0; SYNTHETIC RUN3 PASS15/15; DB CAPTURE NOT AUTHORIZED**.

## 1. Причина и граница

D-1473 фиксирует вариант владельца: не строить VHD/WSL storage-layer, отложить B002 до production independently encrypted storage и продолжить статическую подготовку B001.

Approved `capture_source_authority()` и `compose_run_authority()` уже закрывают exact public capture→package→limits+digest, но production entrypoint отсутствует. Existing `SourceLifecycle.open(endpoint, evidence)` нельзя использовать для первого capture честно: `VerifiedLedgerEvidence.snapshot_id` требуется на входе до того, как новая PostgreSQL RRRO transaction сообщит свой unpredictable `snapshot_id`. Fabricated evidence запрещён.

Этот этап разрешает только plan и, после независимого одобрения, code-only bounded public capture entrypoint. Он не разрешает Python/Docker/DB/media execution, создание role/secret/package/file, ledger materialization, rebuild, cleanup, deploy, live или push.

## 2. Минимальная композиция

Без второго DB/security слоя existing `SourceLifecycle` получает один общий private session opener, которым пользуются два внутренних пути:

1. existing `open(endpoint, evidence)` сохраняет прежний exact API/поведение для текущего importer;
2. new `capture_run_authority(endpoint)` использует opener только внутри своего lexical scope и никогда не возвращает raw executor/session/lifecycle.

Оба пути используют один и тот же exact endpoint validation, fresh-only role/secret creation, literal grants, RRRO transaction, session proof и cleanup/drop/secret-delete. SQL, privileges, role name, TTL, secret rules и error categories не дублируются и не расширяются.

Единственная новая public функция `capture_run_authority(endpoint)`:

1. через private shared opener получает executor/session/lifecycle;
2. внутри того же закрытого function scope вызывает только `capture_source_authority(executor, session)`;
3. закрывает lifecycle на success и failure, не экспортируя ни один DB object;
4. только после доказанного successful close вызывает DB-free `compose_run_authority(capture)`;
5. возвращает только in-memory `(FreezePackage, ManifestLimits, digest)`.

Нет ledger argument, private `SourceReader`, staff/grant/request query, file persistence, serializer/loader, CLI/config/env, retry/resume, service, daemon или target mutation. Capture object и package не переживают process; future authorized rebuild должен выполнить capture и fresh actual run в одном stopped-writer process.

## 3. Security и snapshot boundary

- Capture path не создаёт `ProvidedLedgerVerifier` и не заявляет request-ledger proof.
- Raw executor/session/lifecycle не имеют public capture-return type; единственный caller — exact public four-query function, request count/private rows не читаются.
- Returned package digest binds exact facts read under one guarded snapshot, но не содержит и не идентифицирует `snapshot_id`; future actual-run evidence/`SourceReader` связывают fresh snapshot ID, а existing equality checks reject drift.
- Lifecycle закрывается сразу после exact public capture и до DB-free package composition; writer stop остаётся внешним обязательным gate.
- Any endpoint/session/query/composition/close ambiguity gives one safe failure and no returned authority.
- Existing `open(endpoint,evidence)` regression must remain byte/behavior compatible; actual-run snapshot binding will be resolved only when B002 resumes, not smuggled into B001.

## 4. Acceptance до кода

| ID | Scenario | Required result |
|---|---|---|
| `RB3-CAPRUN-AC-001` | Valid synthetic endpoint/connect, stopped-writer public rows exact112/114/238 | One shared lifecycle creates fresh RRRO session; exact capture closes role/secret/connection before DB-free compose returns package/limits/digest in memory |
| `RB3-CAPRUN-AC-002` | Inspect API and SQL/calls from `capture_run_authority` | Raw executor/session/lifecycle are never returned; only existing four guarded public queries plus existing lifecycle SQL; private staff/grant/request/ledger/target/file calls0 |
| `RB3-CAPRUN-AC-003` | Invalid endpoint, role/secret/session/query/composition failure | Safe existing error; lifecycle cleanup exactly once; result/package persistence0 |
| `RB3-CAPRUN-AC-004` | Lifecycle close/drop/secret-delete ambiguity after otherwise valid capture | No authority returned; constant capture cleanup error |
| `RB3-CAPRUN-AC-005` | Existing `SourceLifecycle.open(endpoint,evidence)` tests | Exact previous evidence wrapper, source session and cleanup semantics unchanged |
| `RB3-CAPRUN-AC-006` | Static scope inspection | One shared private opener + one orchestration function/focused tests only; capture DTO/dependency/config/CLI/framework/runtime0 |
| `RB3-CAPRUN-AC-007` | Attempt to persist capture/package or run without later B002 | API provides no persistence/execute path; B001 instance remains ephemeral and rebuild stays blocked |

## 5. No-bloat stop line

Rejected: public raw capture executor/DTO, a second connection implementation, generic lifecycle factory, capture protocol/plugin, manifest file, staging DB/table, job state, retry, daemon, Compose service or fabricated ledger evidence. If sharing the existing lifecycle requires materially wider refactor than one private opener, work stops for owner review rather than growing a new subsystem.

Independent plan R3 review approved AC001–007 with P1/P2/P3=0/0/0 after removing the public raw executor, correcting snapshot-digest scope and fixing close-before-compose order. Independent code R2 review approved P1/P2/P3=0/0/0 after BaseException-safe acquisition/close cleanup and focused regressions. Stable hashes: `runtime_source.py=85DA82ACA631AECBBC7200976CA1CA842D409F4B949827D44E5802D5758CA0BE`, `test_runtime_source.py=E495E5C7D0DB1D9F0BE87E3EB201D3B0767326645FD7F7127039790A5E56DC0C`. Synthetic tests and DB runtime remain separately closed.

D-1477 run3 used existing `nestakada-local/app-editor:candidate-d330`, current source readonly, network none, no DB/secrets, ephemeral `/tmp`; result `Ran 15 tests in 0.093s`, `OK`, exit0. The app image collection also proved the pinned `nh3` dependency is present. Corrected test hash is `933DBEB4456125E160B69B17C841BFEC7A6F4C78486DE54ABDB551DD48BA5DC2`; production hash remains unchanged. Real stopped-writer DB capture and package instance were not created.
