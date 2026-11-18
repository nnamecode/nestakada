# REBUILD-3 — snapshot-after-open ledger binding

Дата: 2026-11-18. ID: `RB3-RUN-SNAPSHOT-BIND-001`. Статус: **PLAN+CODE APPROVED 0/0/0; SYNTHETIC RUN2 PASS40/40; DB runtime0**.

## 1. Причина и граница

D-1478 продолжает code-only подготовку после D-1477. Current `run(config, evidence)` передаёт `VerifiedLedgerEvidence` в `SourceLifecycle.open()` до создания fresh PostgreSQL RRRO transaction, хотя exact `snapshot_id` появляется только после `SOURCE_SESSION_SQL`. Угадать или подставить snapshot ID запрещено; B002 storage остаётся deferred.

Этот этап разрешает plan и, только после независимого одобрения, bounded code-only binding. Он не разрешает Python/Docker/DB/media runtime, genesis materialization, target creation, rebuild, deploy, live или push.

## 2. Минимальная композиция

Один новый function boundary в `runtime_source.py`:

```text
open_source_bound(endpoint, bind_ledger) -> OpenSource
```

`bind_ledger` — один callable exact type contract `snapshot_id -> VerifiedLedgerEvidence`; это не registry/plugin и не получает executor, connection, credentials, endpoint или paths.

Порядок фиксирован:

1. private shared `_open_session` создаёт existing fresh-only role/secret и RRRO source session, но raw DB objects остаются внутри `runtime_source.py`;
2. function передаёт binder только exact returned `session.snapshot_id`;
3. binder вызывается ровно один раз и обязан вернуть `VerifiedLedgerEvidence`, проходящий один shared exact predicate: nonzero UUID identity, non-bool integer generation≥1, lowercase SHA-256 digest, non-bool exact row_count0 и exact same snapshot ID;
4. current full evidence predicate из `SourceReader` выносится в один module helper и используется здесь до `OpenSource`, без второго набора правил;
5. existing `ProvidedLedgerVerifier` принимает evidence и возвращается внутри `OpenSource`;
6. existing `SourceReader.preflight()` позднее one-shot потребляет тот же verifier, повторно применяет тот же shared predicate и независимо проверяет source request count0.

Existing `SourceLifecycle.open(endpoint, evidence)` сохраняется без изменения для совместимости и focused tests, но production `run()` переходит с pre-bound evidence на binder и вызывает только `open_source_bound`.

Future concrete launcher сможет передать один closure над already approved `verify_zero_genesis(primary_fd, independent_fd, receipt, snapshot_id)`. Этот этап не добавляет root/receipt в `RunConfig`, не открывает файлы и не материализует genesis.

## 3. Failure и cleanup

- Non-callable binder отклоняется до role/secret/connection.
- Binder получает только validated source snapshot string.
- Binder ordinary/BaseException, non-evidence, zero/wrong identity, bool/<1 generation, noncanonical digest, bool/nonzero row_count или snapshot mismatch закрывают executor/reader/role/admin/secret через existing BaseException-safe lifecycle; `OpenSource` не возвращается.
- Clean cleanup re-raises original BaseException; cleanup ambiguity becomes one constant `source-bind-cleanup-ambiguous`.
- Binder не повторяется автоматически; no retry/resume/cache.
- `run()` не создаёт target до existing source preflight; binder failure therefore remains pre-target.

## 4. Acceptance до кода

| ID | Scenario | Required result |
|---|---|---|
| `RB3-SBIND-AC-001` | Valid fake source creates snapshot S; binder returns exact evidence S | Binder called once with only S; returned `OpenSource.ledger` one-shot; later SourceReader accepts same S/rows0 |
| `RB3-SBIND-AC-002` | Binder non-callable | Fail before secret/connect; mutation0 |
| `RB3-SBIND-AC-003` | Binder returns non-evidence, zero identity, bool/<1 generation, uppercase/short/non-SHA digest, bool/nonzero row_count or snapshot T | One shared predicate rejects before OpenSource; full source lifecycle cleanup; no target/binder retry |
| `RB3-SBIND-AC-004` | Binder raises RuntimeError/KeyboardInterrupt/SystemExit | Full cleanup; original error re-raised only after clean cleanup; composition/target0 |
| `RB3-SBIND-AC-005` | Any cleanup step ambiguous after binder failure | Remaining cleanup steps attempted; constant bind-cleanup ambiguity; target0 |
| `RB3-SBIND-AC-006` | Existing `SourceLifecycle.open(endpoint,evidence)` suite | Exact previous behavior and error categories unchanged |
| `RB3-SBIND-AC-007` | `run()` composition inspection | Accepts binder, never accepts/fabricates pre-bound evidence; passes no DB/private object to binder; source preflight still precedes target preparation |
| `RB3-SBIND-AC-008` | Static scope/dependency inspection | One bind function + one factored existing evidence predicate + callable type alias/focused tests only; no duplicated validator, protocol class, registry, config field, persistence, dependency or runtime |

## 5. Stop line

Rejected: generic ledger provider interface, async callback, service/container, binder registry, config serialization, retries, cached evidence, snapshot prediction, raw DB return, or moving ledger verification into importer schemas. If exact callable wiring requires more than this one boundary and `run()` signature change, work stops for owner review.

Independent repeat plan review and code R2 review approved P1/P2/P3=0/0/0. Stable hashes: `source.py=EAB0EF6824B85744656F20C887F3100988EBF8B89CAEF3319B69D5E0F0B24580`, `runtime_source.py=7AF526A39F47B9D334E280CAA7375B1436F4398B99DB4CAC56FCA0E7E1C0823A`, `run.py=935B02FED11B48CF81320562982985C0427883C3688A77519DC2A2451E4FE375`, `test_runtime_source.py=5F4251BBE80E2596E115E4CC309999504638C419F49A59C7D796113798FB52B4`, `test_run.py=2DA35C30512B52C5694998733BEC0BD6A71BAB679C35F0E729FC0B426FFEA68F`. One shared snapshot/evidence predicate, binder cleanup and production run wiring are closed statically; tests/runtime remain separately gated.

D-1481 focused run2 used existing app-editor image with source readonly, network none, no DB/secrets and ephemeral `/tmp`; result `Ran 40 tests in 0.104s`, `OK`, exit0. It covers `test_source`, `test_runtime_source` and `test_run`, including shared predicates, malformed snapshot binder0, evidence fields, BaseException cleanup and production entrypoint wiring. Corrected `test_source.py=F88B95DD51A40D33BF62995A47C730B23F3B9193A551C22AF72CF160699D9FF4`; production hashes unchanged. Real DB/rebuild runtime remains0.
